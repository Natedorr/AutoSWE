"""I/O shell — replaces sync.py:sync_all + dispatch.py:cmd_dispatch.

``poll(cfg)`` is the main loop: load repos, read API, decide, run, emit,
apply. Each step calls into the pure functions in decide.py, run.py, emit.py.

CLI modes (controlled by ``mode`` param):
  ``full``   — sync + dispatch + run (default, used by ``poller``)
  ``sync``   — sync only: decide but don't run (used by ``sync``)
  ``drain``  — repeat ``full`` until idle (used by ``poller --drain``)
"""
from __future__ import annotations

import contextlib
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from autoswe.commands.parser import parse_slash_command
from autoswe.core.config import (
    LOGS_DIR,
    RUNNING_DIR,
    WELCOME_FILE,
    load_repos_config,
)
from autoswe.core.error_utils import capture_dispatch_error, format_error_comment
from autoswe.core.logging_utils import get_debug_logger, init_issue_logger, log, remove_issue_logger
from autoswe.core.queue_store import LockedQueue
from autoswe.core.slug import make_slug, slug_to_filename
from autoswe.orch.decide import decide
from autoswe.orch.emit import emit
from autoswe.orch.run import DispatchResult, run
from autoswe.orch.types import ApiState, TaskState, World
from autoswe.providers.azure.adapter import apply_effect as azure_apply_effect
from autoswe.providers.azure.adapter import read_api as azure_read_api
from autoswe.providers.azure.tracker import AzureTracker
from autoswe.providers.factory import build_repo_cfg, get_tracker
from autoswe.providers.github.adapter import apply_effect as gh_apply_effect
from autoswe.providers.github.adapter import read_api as gh_read_api
from autoswe.tracking.labels import (
    REVIEW_BLOCKING_STATUSES,
    RUNNING_STATUSES,
    TERMINAL_STATUSES,
    completed_status_for,
    normalize_legacy_status,
    running_status_for,
)
from autoswe.tracking.progress import ProgressComment

# Statuses whose label mirror is synced in Phase 3
_MIRROR_STATUSES = TERMINAL_STATUSES | {"planned", "waiting"} | REVIEW_BLOCKING_STATUSES

dbg = get_debug_logger()

AUTOSWE_BOT_FOOTER = "\n<!-- autoswe-bot -->"


# ---------------------------------------------------------------------------
# TaskState <-> queue bridge
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PollTask:
    """Mutable queue entry + immutable TaskState for one issue in one poll."""
    slug: str
    task_state: TaskState
    world: World


def _ensure_queue_entry(
    queue: dict,
    slug: str,
    api: ApiState,
    owner: str,
    repo: str,
    issue_number: int,
    now_iso: str,
    base_branch: str,
    provider: str,
    silent_reporting: bool,
) -> None:
    """Create the queue entry if it doesn't exist yet."""
    if slug in queue:
        # Update title/body from latest API read
        t = queue[slug]
        t["title"] = api.issue.title or t.get("title", "")
        t["body"] = api.issue.body or t.get("body", "")
        t["last_synced"] = now_iso
        return

    queue[slug] = {
        "id": slug,
        "owner": owner,
        "repo": repo,
        "issue_number": issue_number,
        "title": api.issue.title or "",
        "body": api.issue.body or "",
        "autoswe_status": None,
        "pr_number": None,
        "last_synced": now_iso,
        "created_at": now_iso,
        "suppress_welcome": silent_reporting,
        "base_branch": base_branch,
        "provider": provider,
        "welcome_comment_id": None,
        "bot_comment_ids": [],
        "last_dispatched_command_id": None,
        "last_consumed_reply_id": None,
        "last_updated": None,
        "last_comment_sync": None,
        "creator_login": api.issue.creator_login or "",
        "fix_summary": None,
    }
    log(f"[NEW] {slug} (no command, no label)")


def _build_poll_task(
    queue: dict,
    slug: str,
    api: ApiState,
    cfg: dict,
    repo_cfg: dict,
) -> PollTask:
    """Build TaskState + World from queue entry and API snapshot."""
    t = queue[slug]
    raw_status = t.get("autoswe_status")
    status = normalize_legacy_status(raw_status, t.get("last_dispatched_command"))
    # Update queue entry in-place if normalized
    if status != raw_status:
        t["autoswe_status"] = status
    # Override the registry-read status with the normalised value
    t["autoswe_status"] = status
    ts = TaskState.from_queue(slug, t)
    world = World(api=api, task=ts, cfg=cfg, repo_cfg=repo_cfg)
    return PollTask(slug=slug, task_state=ts, world=world)


# ---------------------------------------------------------------------------
# Welcome comment
# ---------------------------------------------------------------------------

def _build_welcome_comment(slash_cmd: str, guidance: str, slug: str, bot_name: str = "autoswe") -> str:
    """Build welcome comment for a newly discovered issue."""
    guidance_suffix = f" with {guidance}" if guidance else ""
    if WELCOME_FILE.exists():
        template = WELCOME_FILE.read_text()
    else:
        template = (
            "autoSWE picked up this issue (`{{SLUG}}`).\n\n"
            "**Available Commands:**\n"
            "- `/plan` - Start a planning session (reads code, asks questions, posts a plan)\n"
            "- `/plan --branch <name>` - Plan on a specific branch (default: main)\n"
            "- `/fix` - Implement the fix (runs Claude with code-editing permissions)\n"
            "- `/fix --branch <name>` - Fix on a specific branch (default: main)\n"
            "- `/fix with <guidance>` - Same as /fix but appends guidance to the prompt\n"
            "- `@{bot_name} <guidance>` - Short form for /fix with guidance\n"
            "- `/pr` - Open a pull request from the current branch\n"
            "- `/sync` - Pull the branch from upstream to keep it up to date\n"
            "- `/retry` - Retry a failed task (resets attempt counter)\n"
            "- `/skip` - Skip this issue\n"
            "- `/abort` - Cancel the current task\n\n"
            "You can add guidance: `/fix with performance focus`\n"
            "\n<!-- autoswe-bot -->"
        )
        template = template.replace("{bot_name}", bot_name)
    comment = (
        template.replace("{{SLUG}}", slug)
        .replace("{{SLASH_COMMAND}}", slash_cmd or "")
        .replace("{{GUIDANCE_SUFFIX}}", guidance_suffix)
    )
    if "<!-- autoswe-bot -->" not in comment:
        comment = comment + AUTOSWE_BOT_FOOTER
    return comment


# ---------------------------------------------------------------------------
# PID / running helpers
# ---------------------------------------------------------------------------

def _is_pid_alive(pid: int) -> bool:
    """Check if a PID is actually a running process."""
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes  # deferred import: Windows-only; kept local so this module imports cleanly on POSIX
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, OSError):
        return False


def _is_task_running(slug: str) -> bool:
    """Check if a task currently has a PID file for a running process."""
    pid_path = RUNNING_DIR / f"{slug_to_filename(slug)}.pid"
    if not pid_path.exists():
        return False
    try:
        pid = int(pid_path.read_text().strip())
        if _is_pid_alive(pid):
            return True
        # Stale PID — clean up
        pid_path.unlink(missing_ok=True)
        return False
    except (ValueError, FileNotFoundError, OSError):
        # Corrupt or gone — clean up
        pid_path.unlink(missing_ok=True)
        return False


def _is_repo_locked(owner: str, repo: str, provider: str) -> str | None:
    """Check if any other issue in this repo is currently running.

    Returns the stem of the locking PID file, or None.
    """
    if not RUNNING_DIR.exists():
        return None
    prefix = {"github": "gh_", "azure": "ado_"}.get(provider.lower(), "gh_")
    if provider.lower() == "azure" and "/" in owner:
        org, _, proj = owner.partition("/")
        stem_prefix = f"{prefix}{org}_{proj}_{repo}_"
    else:
        stem_prefix = f"{prefix}{owner}_{repo}_"
    for pid_path in RUNNING_DIR.iterdir():
        if pid_path.name.endswith(".pid") and pid_path.stem.startswith(stem_prefix):
            try:
                pid = int(pid_path.read_text().strip())
                if _is_pid_alive(pid):
                    return pid_path.stem
                # Dead PID — clean up
                pid_path.unlink(missing_ok=True)
            except (ValueError, FileNotFoundError, OSError):
                # Corrupt/gone — clean up
                pid_path.unlink(missing_ok=True)
    return None


# ---------------------------------------------------------------------------
# Provider adapter selectors
# ---------------------------------------------------------------------------

def _get_read_api(provider: str):
    if provider.lower() == "azure":
        return azure_read_api
    return gh_read_api


def _get_apply_effect(provider: str):
    if provider.lower() == "azure":
        return azure_apply_effect
    return gh_apply_effect


# ---------------------------------------------------------------------------
# Dispatch: run + emit + apply for a single action
# ---------------------------------------------------------------------------

def _dispatch_task(
    pt: PollTask,
    action,
    tracker,
    repo_cfg: dict,
    provider: str,
    cfg: dict,
    queue: dict,
    now_iso: str,
) -> None:
    """Run a Claude action, emit effects, and apply them.

    Creates PID file, sets running status, runs handler, emits effects,
    applies them, writes done/result files, cleans up.
    """
    slug = pt.slug
    world = pt.world
    task_entry = queue[slug]
    owner = world.task.owner
    repo = world.task.repo
    issue_num = world.task.issue_number

    RUNNING_DIR.mkdir(parents=True, exist_ok=True)
    pid_path = RUNNING_DIR / f"{slug_to_filename(slug)}.pid"
    try:
        pid_path.write_text(str(os.getpid()))
        log(f"[DISPATCH] Locked repo {owner}/{repo} (PID {os.getpid()})")
    except OSError as e:
        log(f"[ERROR] Failed to create PID file: {e}")
        return

    issue_handler = None
    try:
        issue_handler = init_issue_logger(LOGS_DIR, slug)

        # --- Set running status ---
        running = running_status_for(
            action.kind,
            task_entry.get("resume_phase") or task_entry.get("last_phase"),
        )
        try:
            tracker.set_status(repo_cfg, issue_num, f"autoswe:{running}")
        except RuntimeError as e:
            log(f"[WARN] could not set running label: {e}")

        task_entry["autoswe_status"] = running
        if task_entry.get("first_dispatched_at") is None:
            task_entry["first_dispatched_at"] = now_iso

        # --- Progress comment ---
        minimal = bool(cfg.get("MINIMAL_POSTING"))
        progress = ProgressComment(tracker, repo_cfg, issue_num, minimal=minimal)

        if action.user_reply_text is not None:
            progress.create(f"Resuming `{action.kind}` session&hellip;")
        else:
            progress.create(f"Dispatching `{action.kind}`&hellip;")

        if progress.comment_id:
            task_entry["_comment_id"] = progress.comment_id
            task_entry["_minimal_posting"] = minimal
            task_entry.setdefault("bot_comment_ids", []).append(progress.comment_id)

        # --- Run the action (Layer B) ---
        result = run(action, world, progress_callback=progress.update)

        # --- Emit effects (Layer C) ---
        effects = emit(action, result, world)

        # --- Apply effects ---
        # post_comment effects from emit() are used to finalize the sticky
        # progress comment in-place (not posted as a separate comment).
        apply_fn = _get_apply_effect(provider)
        for effect in effects:
            if effect.kind == "post_comment":
                progress.finalize(effect.body or "")
                log("[DISPATCH] Finalized sticky progress comment")
            else:
                try:
                    apply_fn(tracker, effect, repo_cfg, issue_num, queue, slug)
                except RuntimeError as e:
                    log(f"[WARN] failed to apply effect {effect.kind!r}: {e}")

        task_entry = queue[slug]

        if result is not None:
            _finalize_handler(slug, result, action, world, task_entry, tracker,
                              repo_cfg, issue_num, provider, cfg, progress)

    finally:
        remove_issue_logger(issue_handler)
        try:
            pid_path.unlink()
            log(f"[DISPATCH] Unlocked repo {owner}/{repo}")
        except FileNotFoundError:
            pass


def _finalize_handler(
    slug: str,
    result: DispatchResult,
    action,
    world: World,
    task_entry: dict,
    tracker,
    repo_cfg: dict,
    issue_num: int,
    provider: str,
    cfg: dict,
    progress: ProgressComment,
) -> None:
    """Post-run finalize: files, watermarks, transient cleanup.

    Progress comment finalization is handled by the effect apply loop
    (post_comment effects → progress.finalize()). This function handles
    what effects cannot — running files, watermarks, transient cleanup.
    """
    done_content = result.done_content
    new_status = task_entry.get("autoswe_status")

    # --- Drain progress comment for non-terminal statuses ---
    # Terminal statuses (fixed/failed/aborted) get their progress finalized
    # via post_comment effects in the apply loop. Non-terminal statuses
    # (planned, waiting) just drain any pending update.
    if new_status not in TERMINAL_STATUSES:
        progress.drain()

    # --- Log terminal status transition ---
    if new_status in TERMINAL_STATUSES:
        log(f"[DISPATCH] {slug} — terminal status: {new_status}")

    # --- Record dispatch timestamp ---
    # emit() sets last_dispatched_command and last_consumed_reply_id via patch_queue.
    # The ID-based watermark replaces the old timestamp approach.

    # --- Write done file ---
    done_path = RUNNING_DIR / f"{slug_to_filename(slug)}.done"
    with contextlib.suppress(OSError):
        done_path.write_text(done_content, encoding="utf-8")

    # --- Write structured result file ---
    result_path = RUNNING_DIR / f"{slug_to_filename(slug)}.result.json"
    try:
        commit_sha = None
        if done_content.startswith("DONE_SUMMARY\t"):
            rest = done_content[len("DONE_SUMMARY\t"):]
            tab_idx = rest.rfind("\t")
            if tab_idx >= 0:
                commit_sha = rest[tab_idx + 1:].strip()
        result_data = {
            "command": action.kind,
            "status": new_status,
            "done_content": done_content,
            "duration_seconds": round(result.duration_seconds, 2) if result.duration_seconds else None,
            "cost_usd": round(result.cost_usd, 4) if result.cost_usd is not None else None,
            "commit_sha": commit_sha,
            "pr_number": task_entry.get("pr_number"),
            "session_id": task_entry.get("session_id"),
        }
        result_path.write_text(json.dumps(result_data, indent=2), encoding="utf-8")
    except OSError:
        pass

    # --- Clear transient fields that dispatch consumed ---
    for field in ("pending_command", "pending_guidance", "pending_user_reply",
             "_token", "_comment_id", "_minimal_posting"):
        task_entry.pop(field, None)

    log(f"[DISPATCH] Task complete: {slug} -> {new_status} "
        f"attempt_count={task_entry.get('attempt_count', 0)} "
        f"guard_blocked={task_entry.get('_guard_blocked', False)} "
        f"first_dispatched_at={task_entry.get('first_dispatched_at', 'none')}")


# ---------------------------------------------------------------------------
# Dispatch error handling
# ---------------------------------------------------------------------------


def _handle_dispatch_error(
    slug: str,
    exc: Exception,
    tracker,
    repo_cfg: dict,
    issue_num: int,
    queue_entry: dict,
    cfg: dict,
    owner: str,
    repo: str,
    provider: str,
) -> None:
    """Handle a dispatch failure: capture diagnostics, post error comment, transition to error state.

    Transitions the task to the "error" terminal state instead of rolling
    back to "pending". The user must post `/retry` to resume.
    """
    # Get worktree path for diagnostics — always attempt, even without
    # plan_branch (e.g. early /plan failures). _worktree_path is a pure
    # function; failure is caught below.
    worktree = None
    if "WORKTREE_DIR" in cfg:
        # Deferred import: only needed for error diagnostics; avoids circular dependency.
        from autoswe.vcs.worktree import worktree_path as _worktree_path

        try:
            worktree = _worktree_path(
                owner, repo, queue_entry["issue_number"],
                cfg,
                provider=provider,
            )
        except Exception:  # Best-effort worktree path lookup for diagnostics; failure is harmless
            pass

    # 1. Capture diagnostics
    ctx = capture_dispatch_error(exc, slug, worktree)

    # 2. Post structured error comment (best effort)
    try:
        comment_body = format_error_comment(ctx)
        tracker.post_comment(repo_cfg, issue_num, comment_body)
        log(f"[ERROR] {slug}: posted error comment")
    except Exception as post_err:  # Post is best-effort; log and continue if the provider API fails
        dbg.error("dispatch error: failed to post comment for %s: %s", slug, post_err, exc_info=True)
        log(f"[ERROR] {slug}: failed to post error comment: {post_err}")

    # 3. Transition queue entry to "error" state
    # Phase 3's label mirror (below the dispatch loop) handles the
    # autoswe:error label for terminal statuses, so no duplicate call needed.
    queue_entry["autoswe_status"] = "error"
    queue_entry["session_id"] = None
    queue_entry["first_dispatched_at"] = None

    log(f"[ERROR] {slug}: transitioned to error state (exception: {type(exc).__name__}: {exc})")


# ---------------------------------------------------------------------------
# Welcome comments
# ---------------------------------------------------------------------------

def _post_pending_welcomes(
    queue: dict,
    repos_cfg: dict,
    cfg: dict,
    bot_name: str,
    silent_reporting: bool,
    active_slugs: set | None = None,
) -> None:
    """Post welcome comments to newly discovered issues that don't have one yet.

    *active_slugs* — set of slugs currently open in the API.  When provided,
    stale queue entries (issues closed on the platform between runs) are
    skipped so we don't post welcome comments to closed issues.
    """
    for slug, task in list(queue.items()):
        if task.get("suppress_welcome", False):
            continue
        # Skip stale entries not currently open in the API
        if active_slugs is not None and slug not in active_slugs:
            continue

        owner = task["owner"]
        repo = task["repo"]
        issue_num = task["issue_number"]
        provider = task.get("provider", "github")

        try:
            repo_cfg = build_repo_cfg(owner, repo, cfg, repos_cfg, provider=provider)
            tracker = get_tracker(repo_cfg)
            comments = tracker.fetch_comments(repo_cfg, issue_num)

            slash_result = None
            for comment in sorted(comments, key=lambda c: c.created_at, reverse=True):
                slash_result = parse_slash_command(comment.body, bot_name=bot_name)
                if slash_result:
                    break
            if slash_result is None:
                slash_result = parse_slash_command(task.get("body", ""), bot_name=bot_name)

            slash_cmd, guidance, _branch = slash_result if slash_result else (None, None, None)
            body = _build_welcome_comment(slash_cmd or "", guidance or "", task["id"], bot_name=bot_name)
            welcome_id = tracker.post_comment(repo_cfg, issue_num, body)
            task["suppress_welcome"] = True
            if welcome_id:
                task["welcome_comment_id"] = welcome_id
                task.setdefault("bot_comment_ids", []).append(welcome_id)
            log(f"[WELCOME] posted to {slug}")
            # Throttle welcome posts to avoid API rate limits (10s between each).
            time.sleep(10)
        except Exception as e:  # Per-repo resilience; one failed welcome must not block the rest.
            dbg.error("post_welcome_comments: failed for %s: %s", slug, e, exc_info=True)
            log(f"[WARN] welcome comment failed for {slug}: {e}")


# ---------------------------------------------------------------------------
# Main poll function
# ---------------------------------------------------------------------------

def _recover_orphaned_worktrees(cfg: dict, queue: dict, repos_cfg: dict) -> None:
    """Recover worktrees left dirty by SIGKILL'd dispatch processes.

    Runs at poll-cycle startup (inside the LockedQueue context, before dispatch).
    For each queue entry with a dead PID file:
    - Clears the stale PID.
    - Resets any RUNNING status to "pending" so decide() re-dispatches.
    - Depending on WORKTREE_ORPHAN_POLICY (default "commit"):
        "commit"   — stage, commit, and push orphaned changes so the next
                     dispatch's reset-to-origin keeps the work.
        "discard"  — hard-reset the worktree (no commit).
        "log_only" — log but take no git action.
    """
    if not RUNNING_DIR.exists():
        return

    policy = str(cfg.get("WORKTREE_ORPHAN_POLICY", "commit")).lower()

    for slug, task in list(queue.items()):
        pid_path = RUNNING_DIR / f"{slug_to_filename(slug)}.pid"
        if not pid_path.exists():
            continue

        try:
            pid = int(pid_path.read_text().strip())
        except (ValueError, OSError):
            pid_path.unlink(missing_ok=True)
            continue

        if _is_pid_alive(pid):
            continue  # live dispatch owns this entry

        # Dead PID — orphaned interrupted dispatch
        pid_path.unlink(missing_ok=True)
        log(f"[RECOVER] {slug}: cleared stale PID {pid}")

        owner = task.get("owner")
        repo = task.get("repo")
        issue_num = task.get("issue_number")
        provider = task.get("provider", "github")

        if not (owner and repo and issue_num):
            continue

        # Reset any running status so decide() will re-dispatch
        current_status = task.get("autoswe_status")
        if current_status in RUNNING_STATUSES:
            task["autoswe_status"] = "pending"
            log(f"[RECOVER] {slug}: reset status {current_status!r} → 'pending'")

        if policy == "log_only":
            log(f"[RECOVER] {slug}: policy=log_only, skipping worktree recovery")
            continue

        # Deferred worktree imports (avoids circular dependency at module load)
        try:
            from autoswe.vcs.worktree import (
                commit_and_push,
                ensure_clone,
                is_dirty,
                reset_clean,
                worktree_path,
            )
        except ImportError:
            dbg.error("recover: worktree module unavailable for %s", slug, exc_info=True)
            continue

        wt = worktree_path(owner, repo, issue_num, cfg, provider)
        if not wt.exists():
            log(f"[RECOVER] {slug}: worktree {wt} does not exist, skipping")
            continue

        if not is_dirty(wt):
            log(f"[RECOVER] {slug}: worktree clean, nothing to recover")
            continue

        try:
            repo_cfg = build_repo_cfg(owner, repo, cfg, repos_cfg)
        except Exception as e:
            dbg.error("recover: build_repo_cfg failed for %s: %s", slug, e, exc_info=True)
            log(f"[RECOVER] {slug}: could not build repo_cfg: {e}")
            continue

        repo_override = repos_cfg.get(f"{owner}/{repo}", {})
        base_branch = repo_override.get("base_branch", "main")

        if policy == "discard":
            try:
                from autoswe.providers.factory import get_vcs as _get_vcs
                branch = _get_vcs(repo_cfg).branch_name(issue_num)
                reset_clean(wt, branch)
                log(f"[RECOVER] {slug}: discarded orphaned changes")
            except Exception as e:
                dbg.error("recover: discard failed for %s: %s", slug, e, exc_info=True)
                log(f"[RECOVER] {slug}: discard failed: {e}")
            continue

        # Default policy: commit + push
        try:
            token = os.environ.get("PAT", "") or repo_cfg.get("pat", "")
            ensure_clone(owner, repo, token, cfg, base_branch=base_branch, provider=provider)
            msg = f"autoswe: recovered orphaned changes from interrupted run (issue #{issue_num})"
            commit_and_push(wt, owner, repo, issue_num, msg, base_branch, provider)
            log(f"[RECOVER] {slug}: committed and pushed orphaned changes")
        except Exception as e:
            dbg.error("recover: commit_and_push failed for %s: %s", slug, e, exc_info=True)
            log(f"[RECOVER] {slug}: commit_and_push failed: {e}")
            continue

        # Best-effort recovery comment
        try:
            tracker = get_tracker(repo_cfg)
            tracker.post_comment(
                repo_cfg, issue_num,
                f"**autoSWE recovery**: found orphaned changes from an interrupted run "
                f"— committed and pushed them to `autoswe/issue-{issue_num}`."
                f"{AUTOSWE_BOT_FOOTER}",
            )
        except Exception as e:
            dbg.error("recover: comment post failed for %s: %s", slug, e, exc_info=True)
            log(f"[RECOVER] {slug}: recovery comment failed: {e}")


def poll(cfg: dict, mode: str = "full", repo_filter: str | None = None) -> int:
    """Run one poll cycle: sync + decide + dispatch for all repos.

    Args:
        cfg: Global configuration dict from load_config().
        mode: ``"full"`` = sync + dispatch + run.
              ``"sync"`` = sync + decide only (no Claude run).
              ``"drain"`` = repeat full until idle.
        repo_filter: If set, only process this repo (``"owner/repo"`` format).

    Returns the number of tasks processed (actions that weren't noop).
    """
    if mode == "drain":
        return _drain_poll(cfg)
    return _single_poll(cfg, run_actions=mode != "sync", repo_filter=repo_filter)


def _single_poll(cfg: dict, *, run_actions: bool = True, repo_filter: str | None = None) -> int:
    """One pass over all repos: read API, decide, (optionally) run, emit, apply.

    Returns the number of tasks processed (actions that weren't noop).
    """
    repos_cfg = load_repos_config()
    repo_keys = [k for k in repos_cfg if not k.startswith("_")]

    if repo_filter:
        repo_keys = [k for k in repo_keys if k == repo_filter]

    if not repo_keys:
        log("[SYNC] No repos configured in repos.json — run 'python autoswe.py setup' to configure")
        return 0

    log(f"[SYNC] Using {len(repo_keys)} repo(s) from repos.json")

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    bot_name = cfg.get("BOT_NAME", "autoswe")
    max_concurrent = cfg.get("MAX_CONCURRENT", 1)
    silent_reporting = cfg.get("SILENT_REPORTING", False)

    tasks_processed = 0
    dispatched_this_cycle: set[str] = set()

    with LockedQueue() as lq:
        queue = lq.queue

        if run_actions and cfg.get("WORKTREE_DIR"):
            _recover_orphaned_worktrees(cfg, queue, repos_cfg)

        for repo_path in repo_keys:
            owner, _, repo = repo_path.partition("/")
            if not repo:
                log(f"[WARN] invalid repo key '{repo_path}', skipping")
                continue

            log(f"[SYNC] {owner}/{repo}")

            try:
                repo_cfg = build_repo_cfg(owner, repo, cfg, repos_cfg)
            except Exception as e:  # Config parse failure is per-repo; skip repo, continue to next.
                log(f"[ERROR] {owner}/{repo}: failed to build repo_cfg: {e}")
                continue

            tracker = get_tracker(repo_cfg)
            provider = repo_cfg.get("provider", "github")

            # Resolve repo UUID for Azure — web URLs require UUID, not display name
            if provider == "azure" and isinstance(tracker, AzureTracker):
                try:
                    repo_id = tracker.resolve_repo_id()
                    if repo_id:
                        repo_cfg["repo_id"] = repo_id
                except Exception as e:  # Azure repo_id resolution is optional — fallback to repo name
                    log(f"[WARN] {owner}/{repo}: failed to resolve repo_id ({type(e).__name__}: {e}), falling back to name")

            repo_override = repos_cfg.get(repo_path, {})
            base_branch = repo_override.get("base_branch", "main")

            # Fetch API state for this repo
            # Pass bot_ids from queue so adapters can set is_bot flags.
            # First poll after queue wipe relies on fallback (author_login == "BOT",
            # body marker check) — the backfill below self-heals after apply.
            try:
                read_api_fn = _get_read_api(provider)
                all_bot_ids = {
                    cid
                    for t in queue.values()
                    for cid in t.get("bot_comment_ids", [])
                }

                # Build skip-rule inputs from queue entries for this repo
                # Slugs in queue keys use colons (gh: / ado:) — see make_slug().
                # Do NOT confuse with PID-file stems which use underscores (gh_ / ado_)
                # via slug_to_filename() — that's what _is_repo_locked() uses.
                slug_prefix = {"github": "gh:", "azure": "ado:"}.get(provider.lower(), "gh:")
                if provider.lower() == "azure" and "/" in owner:
                    org, _, proj = owner.partition("/")
                    stem_prefix = f"{slug_prefix}{org}_{proj}_{repo}_"
                else:
                    stem_prefix = f"{slug_prefix}{owner}_{repo}_"

                prev_updated: dict[int, str | None] = {}
                force_fetch: set[int] = set()
                for _slug, _entry in queue.items():
                    if (_entry.get("owner") == owner and _entry.get("repo") == repo
                            and _slug.startswith(stem_prefix)):
                        _inum = _entry.get("issue_number")
                        if _inum is not None:
                            prev_updated[_inum] = _entry.get("last_updated")
                            _status = _entry.get("autoswe_status")
                            if _status == "pending" or _status in RUNNING_STATUSES:
                                force_fetch.add(_inum)

                api_states = read_api_fn(
                    tracker, repo_cfg, cfg,
                    bot_ids=all_bot_ids,
                    prev_updated=prev_updated,
                    force_fetch=force_fetch,
                )
            except RuntimeError as e:
                log(f"[ERROR] {owner}/{repo}: {e}")
                continue

            # Build set of genuinely open issue numbers for gh_closed detection
            open_issue_numbers = {
                api.issue.number
                for api in api_states.values()
                if not api.issue.is_pull_request and api.issue.state != "closed"
            }

            # --- Phase 0a: Ensure queue entries exist ---
            # Create queue entries for all open issues before Phase 0b (welcomes).
            # This ensures _post_pending_welcomes can find newly discovered tasks.
            active_slugs: set[str] = set()
            for issue_number, api in api_states.items():
                if api.issue.is_pull_request:
                    continue
                if api.issue.state == "closed":
                    continue
                slug = make_slug(provider, (owner, repo), issue_number)
                active_slugs.add(slug)
                _ensure_queue_entry(
                    queue, slug, api, owner, repo, issue_number,
                    now_iso, base_branch, provider, silent_reporting,
                )

            # --- Phase 0b: Post pending welcome comments before dispatch ---
            # Run after queue entries are ensured, so the welcome comment
            # is always the first bot comment on the issue.
            # The queue is mutated in-place; _build_poll_task reads the
            # updated suppress_welcome flag for each issue.
            if run_actions:
                _post_pending_welcomes(queue, repos_cfg, cfg, bot_name, silent_reporting,
                                       active_slugs=active_slugs)

            # --- Phase 1: Process open issues ---
            for issue_number, api in api_states.items():
                if api.issue.is_pull_request:
                    continue
                if api.issue.state == "closed":
                    continue  # handled by gh_closed detection below

                slug = make_slug(provider, (owner, repo), issue_number)

                # Ensure queue entry is up-to-date (title/body/last_synced)
                _ensure_queue_entry(
                    queue, slug, api, owner, repo, issue_number,
                    now_iso, base_branch, provider, silent_reporting,
                )

                # Build TaskState + World
                pt = _build_poll_task(queue, slug, api, cfg, repo_cfg)
                action = decide(pt.world)

                # Bookkeeping: update last_comment_sync and last_updated
                task_entry = queue[slug]
                if api.comments_fetched:
                    task_entry["last_comment_sync"] = now_iso
                    if action.kind == "noop":
                        task_entry["last_updated"] = api.issue.last_updated

                if action.kind == "noop":
                    continue

                # Sync-only mode: log decision but don't run
                if not run_actions:
                    log(f"[DISPATCH] {slug} would run {action.kind!r} (sync-only mode, skipping)")
                    continue

                # Concurrency gate
                if tasks_processed >= max_concurrent:
                    log(f"[DISPATCH] MAX_CONCURRENT ({max_concurrent}) reached, stopping dispatch")
                    break

                if _is_task_running(slug):
                    log(f"[DISPATCH] {slug} already running, skipping")
                    continue

                if slug in dispatched_this_cycle:
                    log(f"[DISPATCH] {slug} already dispatched this cycle — skipping")
                    continue

                repo_locked_by = _is_repo_locked(owner, repo, provider)
                if repo_locked_by:
                    log(f"[DISPATCH] {slug} skipped — repo in use by {repo_locked_by}")
                    continue

                # Dispatch
                tasks_processed += 1
                dispatched_this_cycle.add(slug)

                try:
                    _dispatch_task(pt, action, tracker, repo_cfg, provider, cfg, queue, now_iso)
                except Exception as e:  # Dispatch state-machine boundary; ANY failure must become a handled error.
                    dbg.error("poll: dispatch failed for %s: %s", slug, e, exc_info=True)
                    log(f"[ERROR] {slug}: dispatch failed: {e}")
                    _handle_dispatch_error(
                        slug=slug,
                        exc=e,
                        tracker=tracker,
                        repo_cfg=repo_cfg,
                        issue_num=queue[slug]["issue_number"],
                        queue_entry=queue[slug],
                        cfg=cfg,
                        owner=pt.task_state.owner,
                        repo=pt.task_state.repo,
                        provider=provider,
                    )

            # --- Observability: per-repo comment-fetch summary ---
            fetched_count = sum(
                1 for api in api_states.values()
                if not api.issue.is_pull_request
                and api.issue.state != "closed"
                and api.comments_fetched
            )
            total_open = sum(
                1 for api in api_states.values()
                if not api.issue.is_pull_request
                and api.issue.state != "closed"
            )
            log(f"[SYNC] {owner}/{repo}: fetched comments for {fetched_count}/{total_open} open issues")

            # --- Backfill bot_comment_ids (self-healing) ---
            # After dispatch-apply, any comments with is_bot=True but ID not yet
            # in bot_comment_ids get backfilled. Makes the system self-healing
            # on the first poll after a queue wipe.
            for issue_number, api in api_states.items():
                slug = make_slug(provider, (owner, repo), issue_number)
                if slug not in queue:
                    continue
                task_entry = queue[slug]
                task_entry.setdefault("bot_comment_ids", [])
                existing_ids = set(task_entry["bot_comment_ids"])
                for c in api.comments:
                    if c.is_bot and c.id and c.id not in existing_ids:
                        task_entry["bot_comment_ids"].append(c.id)
                        existing_ids.add(c.id)

            # --- Phase 2: gh_closed detection ---
            for slug in list(queue.keys()):
                task_entry = queue[slug]
                if task_entry["owner"] != owner or task_entry["repo"] != repo:
                    continue
                if task_entry["issue_number"] not in open_issue_numbers:
                    if not task_entry.get("gh_closed", False):
                        task_entry["gh_closed"] = True
                        closed_status = completed_status_for(
                            task_entry.get("last_dispatched_command", "/fix").lstrip("/")
                        )
                        task_entry["autoswe_status"] = closed_status
                        with contextlib.suppress(RuntimeError):
                            tracker.set_status(repo_cfg, task_entry["issue_number"], f"autoswe:{closed_status}")
                        log(f"[CLOSED] {slug} — issue closed on platform, marking {closed_status}")
                    continue
                if task_entry.get("gh_closed", False):
                    task_entry["gh_closed"] = False
                    log(f"[REOPENED] {slug} — issue reopened on platform")

            # --- Phase 3: Label mirror for terminal tasks ---
            # Only call set_status when the issue's current status (from labels/tags
            # refreshed by list_open_issues) differs from the queue status. This
            # avoids a write that would bump the provider's updated timestamp,
            # which would defeat the comment-fetch skip optimization.
            for slug in list(queue.keys()):
                task_entry = queue[slug]
                if task_entry["owner"] != owner or task_entry["repo"] != repo:
                    continue
                if task_entry["issue_number"] not in open_issue_numbers:
                    continue
                qs = task_entry.get("autoswe_status")
                if qs in _MIRROR_STATUSES:
                    api_state = api_states.get(task_entry["issue_number"])
                    if api_state is not None and api_state.issue.status != qs:
                        with contextlib.suppress(RuntimeError):
                            tracker.set_status(
                                repo_cfg, task_entry["issue_number"], f"autoswe:{qs}"
                            )

    return tasks_processed


def _drain_poll(cfg: dict) -> int:
    """Keep polling until no tasks are processed in a cycle.

    Returns total tasks processed across all cycles.
    """
    max_cycles = cfg.get("MAX_DRAIN_CYCLES", 50) or 50
    total = 0
    cycle = 0

    while cycle < max_cycles:
        cycle += 1
        log(f"[POLLER] Starting drain cycle {cycle} (max {max_cycles})")
        processed = _single_poll(cfg, run_actions=True)
        total += processed

        if processed == 0:
            log(f"[POLLER] No tasks processed, drain complete after {cycle} cycle(s)")
            break

        log(f"[POLLER] Cycle {cycle} complete, {processed} task(s)")

    if cycle >= max_cycles:
        log(f"[POLLER] Max cycles ({max_cycles}) reached, exiting drain")

    return total
