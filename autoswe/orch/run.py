"""Layer B: Claude runner wrapper.

``run(action, world) -> DispatchResult | None`` dispatches Action.kind
to the existing planner/coder/ship/worktree code. Returns None for pure
actions (skip/abort/noop/post_welcome/advance_watermark) that don't invoke
Claude.

The planner/coder/ship modules stay where they are — they sit inside
Layer B at the right seam already.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from autoswe.core.logging_utils import log
from autoswe.harness import coder, planner
from autoswe.harness.runner import HandlerResult
from autoswe.orch.types import Action, World
from autoswe.vcs import ship
from autoswe.vcs import worktree as worktree_mod

if TYPE_CHECKING:
    from collections.abc import Callable

# ---------------------------------------------------------------------------
# DispatchResult
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DispatchResult:
    """Result of running a Claude handler.

    Wraps the handler's done_content (PLAN_READY, DONE_SUMMARY, FAILED, etc.)
    along with cost/duration metrics. Passed to emit() which maps done_content
    to the appropriate Effects (status change, comments, queue patches).
    """
    done_content: str
    cost_usd: float | None = None
    duration_seconds: float = 0.0
    session_id: str | None = None
    plan_file_path: str | None = None
    review_file_path: str | None = None


# ---------------------------------------------------------------------------
# Task dict builder
# ---------------------------------------------------------------------------

def _build_task_dict(world: World, action: Action) -> dict:
    """Build the mutable task dict that existing handlers expect.

    Derived from the TASK_FIELDS registry via TaskState.to_handler_dict().
    Action fields (plan_branch, session_id) override TaskState when set.
    """
    task = world.task
    d = task.to_handler_dict(world.repo_cfg)
    # Action overrides (plan_branch from --branch flag, resume session)
    if action.plan_branch:
        d["plan_branch"] = action.plan_branch
    if action.resume_session_id:
        d["session_id"] = action.resume_session_id
    return d


# ---------------------------------------------------------------------------
# Action -> handler router
# ---------------------------------------------------------------------------

def run(
    action: Action,
    world: World,
    progress_callback: Callable[[str], None] | None = None,
) -> DispatchResult | None:
    """Run the Claude handler for this action.

    Returns None for pure actions (skip, abort, noop, post_welcome, etc)
    that don't invoke Claude. Returns DispatchResult for all Claude actions.
    """
    kind = action.kind

    # Pure actions — no Claude run
    if kind in (
        "noop", "skip", "abort", "post_welcome",
        "advance_watermark", "mark_failed_limit",
    ):
        return None

    task = _build_task_dict(world, action)
    cfg = world.cfg
    rc = world.repo_cfg
    guidance = action.guidance

    # Route to handler
    if kind == "plan":
        hr = _run_plan_with_sync(
            task, guidance, action.user_reply_text, rc, cfg,
            progress_callback=progress_callback,
        )
        return _to_dispatch(hr, task)

    if kind == "fix":
        if action.user_reply_text is not None:
            hr = coder.resume_fix(
                task, action.user_reply_text, rc, cfg,
                progress_callback=progress_callback,
            )
        else:
            hr = _run_fix_with_sync(
                task, guidance, rc, cfg,
                progress_callback=progress_callback,
            )
        return _to_dispatch(hr, task)

    if kind == "ship_pr":
        done = ship.open_pr(task, cfg, rc)
        return DispatchResult(done_content=done)

    if kind == "sync_branch":
        dr = _run_sync(task, rc, cfg, progress_callback)
        return dr

    if kind == "retry":
        dr = _run_retry(action, world, task, cfg, rc, progress_callback)
        return dr

    if kind == "review":
        hr = _run_review_with_sync(
            task, guidance, rc, cfg,
            progress_callback=progress_callback,
        )
        return _to_dispatch(hr, task, review_file_path=hr.review_file_path)

    log(f"[RUN] Unknown action kind {kind!r}, treating as /fix")
    hr = coder.run_fix(task, guidance, rc, cfg,
                       progress_callback=progress_callback)
    return _to_dispatch(hr, task)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_dispatch(hr: HandlerResult, task: dict, review_file_path: str | None = None) -> DispatchResult:
    """Convert HandlerResult (from planner/coder) to DispatchResult."""
    return DispatchResult(
        done_content=hr.done_content,
        cost_usd=hr.cost_usd,
        duration_seconds=hr.duration_seconds,
        session_id=hr.session_id or task.get("session_id"),
        plan_file_path=hr.plan_file_path,
        review_file_path=review_file_path or hr.review_file_path,
    )


def _run_sync(
    task: dict,
    repo_cfg: dict,
    cfg: dict,
    progress_callback: Callable[[str], None] | None,
) -> DispatchResult:
    """Handle the sync_branch action — merge base into feature branch."""
    # Deferred import: avoids circular dependency (run <- comments <-> providers).
    from autoswe.tracking.comments import BOT_MARKER

    owner, repo, issue_num = task["owner"], task["repo"], task["issue_number"]
    provider = repo_cfg.get("provider", "github")
    base_branch = task.get("base_branch", "main")
    token = task["_token"]
    wt = worktree_mod.worktree_path(owner, repo, issue_num, cfg, provider)
    if not wt.exists():
        wt = worktree_mod.create_worktree(
            owner, repo, issue_num, base_branch, token, cfg, provider,
            default_branch=base_branch, pull_strategy="reset", push_new=True,
        )
    try:
        if progress_callback:
            progress_callback(
                f"Merging `origin/{base_branch}` into "
                f"`{worktree_mod.get_vcs({'owner': owner, 'repo': repo, 'token': '', 'provider': provider}).branch_name(issue_num)}`"
                f"&hellip;{BOT_MARKER}"
            )
        result = worktree_mod.sync_branch(wt, owner, repo, issue_num, base_branch, provider, cfg)
        log(f"[SYNC] {task['id']} synced={result.get('synced')} conflict={result.get('conflict')} ahead={result.get('ahead', 0)}")
        if result.get("synced"):
            branch = result["branch"]
            commit_sha = result.get("commit_sha", "")
            changed = result.get("changed", False)
            ahead = result.get("ahead", 0)
            if changed:
                summary = (
                    f"Merged `origin/{base_branch}` into `{branch}`.\n\n"
                    f"{ahead} commits ahead of `{base_branch}` after sync."
                )
            else:
                summary = f"Already up to date with `origin/{base_branch}`."
            return DispatchResult(
                done_content=f"DONE_SUMMARY\t{summary}\t{commit_sha}",
            )
        elif result.get("conflict"):
            if result.get("rebase"):
                # Rebase conflict resolution is out of scope — deferred.
                # TODO: Implement rebase conflict resolution (iterative git rebase --continue loop).
                files = result.get("conflict_files", [])
                file_list = ", ".join(files) if files else "unknown files"
                return DispatchResult(
                    done_content=f"FAILED: rebase conflict in {file_list}",
                )
            # Merge conflict — invoke Claude to resolve
            files = result.get("conflict_files", [])
            if progress_callback:
                progress_callback(f"Merge conflict in {len(files)} file(s) — invoking Claude to resolve...")
            hr = coder.resolve_sync_conflicts(
                task, files, repo_cfg=repo_cfg, cfg=cfg, progress_callback=progress_callback,
            )
            return _to_dispatch(hr, task)
        else:
            return DispatchResult(
                done_content=f"FAILED: {result.get('error', 'sync failed')}",
            )
    except Exception as e:  # Poller resilience — any sync dispatch failure is caught and reported
        return DispatchResult(done_content=f"FAILED: {e}")


def _sync_before_dispatch(
    task: dict,
    repo_cfg: dict,
    cfg: dict,
    progress_callback: Callable[[str], None] | None,
    *,
    phase: str,
    branch_for_create: str,
) -> tuple:  # type: ignore[type-arg]
    """Ensure worktree, sync branch, resolve conflicts — shared prologue.

    Returns ``(wt, None)`` on success so the caller proceeds with the dispatch
    using the worktree path. Returns ``(wt, error_HandlerResult)`` if sync
    failed or conflict resolution could not complete, so the caller bails.
    """
    owner, repo, issue_num = task["owner"], task["repo"], task["issue_number"]
    provider = repo_cfg.get("provider", "github")
    base_branch = task.get("base_branch", "main")
    token = task["_token"]

    wt = worktree_mod.worktree_path(owner, repo, issue_num, cfg, provider)
    if not wt.exists():
        wt = worktree_mod.create_worktree(
            owner, repo, issue_num, branch_for_create, token, cfg, provider,
            default_branch=base_branch, pull_strategy="reset", push_new=True,
        )

    sync_result = worktree_mod.sync_branch(wt, owner, repo, issue_num, base_branch, provider, cfg)
    log(f"[SYNC] {task['id']} pre-{phase} synced={sync_result.get('synced')} conflict={sync_result.get('conflict')}")

    if sync_result.get("conflict") and not sync_result.get("rebase"):
        files = sync_result["conflict_files"]
        if progress_callback:
            progress_callback(f"Pre-{phase} sync conflict in {len(files)} file(s) — invoking Claude to resolve...")
        hr = coder.resolve_sync_conflicts(
            task, files, repo_cfg=repo_cfg, cfg=cfg, progress_callback=progress_callback,
        )
        if not (hr.done_content or "").startswith("DONE_SUMMARY"):
            return wt, hr
    elif not sync_result.get("synced") and not sync_result.get("conflict"):
        return wt, HandlerResult(f"FAILED: pre-{phase} sync error: {sync_result.get('error')}")

    return wt, None


def _run_fix_with_sync(
    task: dict,
    guidance: str,
    repo_cfg: dict,
    cfg: dict,
    progress_callback: Callable[[str], None] | None,
) -> HandlerResult:
    """Pre-dispatch sync before /fix, then run the fix handler."""
    base_branch = task.get("base_branch", "main")
    wt, err = _sync_before_dispatch(
        task, repo_cfg, cfg, progress_callback,
        phase="fix", branch_for_create=base_branch,
    )
    if err is not None:
        return err
    return coder.run_fix(
        task, guidance, repo_cfg, cfg, progress_callback=progress_callback, wt=wt,
    )


def _run_plan_with_sync(
    task: dict,
    guidance: str,
    user_reply_text: str | None,
    repo_cfg: dict,
    cfg: dict,
    progress_callback: Callable[[str], None] | None,
) -> HandlerResult:
    """Pre-dispatch sync before /plan, then run the plan handler."""
    base_branch = task.get("base_branch", "main")
    plan_branch = task.get("plan_branch") or base_branch
    wt, err = _sync_before_dispatch(
        task, repo_cfg, cfg, progress_callback,
        phase="plan", branch_for_create=plan_branch,
    )
    if err is not None:
        return err

    if user_reply_text is not None:
        return planner.resume_plan(
            task, user_reply_text, repo_cfg, cfg,
            progress_callback=progress_callback, wt=wt,
        )
    return planner.run_plan(
        task, repo_cfg, cfg, guidance,
        progress_callback=progress_callback, wt=wt,
    )


def _run_review_with_sync(
    task: dict,
    guidance: str,
    repo_cfg: dict,
    cfg: dict,
    progress_callback: Callable[[str], None] | None,
) -> HandlerResult:
    """Pre-dispatch sync before /review, then run the review handler."""
    base_branch = task.get("base_branch", "main")
    wt, err = _sync_before_dispatch(
        task, repo_cfg, cfg, progress_callback,
        phase="review", branch_for_create=base_branch,
    )
    if err is not None:
        return err
    # Deferred import: avoids loading reviewer module unless a review action is
    # dispatched; most tasks are plan/fix, so keeping this out of the fast path
    # improves cold-start.
    from autoswe.harness import reviewer
    return reviewer.run_review(
        task, repo_cfg, cfg, guidance,
        progress_callback=progress_callback, wt=wt,
    )


_NON_REPLAYABLE_COMMANDS = frozenset(("/pr", "/sync", "/skip", "/abort", "/retry"))

def _run_retry(
    action: Action,
    world: World,
    task: dict,
    cfg: dict,
    repo_cfg: dict,
    progress_callback: Callable[[str], None] | None,
) -> DispatchResult:
    """Handle retry — replay the last substantive command or resume from user reply.

    Non-replayable commands (/pr, /sync, /skip, /abort, /retry) are workflow
    plumbing. When one of them was the last dispatched command, fall back to
    replaying /fix so retry replays actual work (plan/fix/review) instead of
    re-creating a PR or re-syncing.
    """
    if action.user_reply_text is not None:
        # User replied to a question during a failed phase — resume
        last_phase = world.task.last_phase or "fix"
        if last_phase == "fix":
            hr = coder.resume_fix(
                task, action.user_reply_text, repo_cfg, cfg,
                progress_callback=progress_callback,
            )
        else:
            hr = planner.resume_plan(
                task, action.user_reply_text, repo_cfg, cfg,
                progress_callback=progress_callback,
            )
        return _to_dispatch(hr, task)

    # Look at what was last dispatched and replay it
    last_cmd = world.task.last_dispatched_command
    if last_cmd in _NON_REPLAYABLE_COMMANDS:
        last_cmd = "/fix"
    last_cmd = last_cmd or "/fix"
    if last_cmd == "/plan":
        hr = _run_plan_with_sync(task, action.guidance, None, repo_cfg, cfg,
                                  progress_callback=progress_callback)
    elif last_cmd == "/review":
        hr = _run_review_with_sync(task, action.guidance, repo_cfg, cfg,
                                   progress_callback=progress_callback)
    else:
        hr = _run_fix_with_sync(task, action.guidance, repo_cfg, cfg,
                                progress_callback=progress_callback)
    return _to_dispatch(hr, task)
