import asyncio
import subprocess
from pathlib import Path

from autoswe.core.logging_utils import get_debug_logger, log
from autoswe.harness import runner
from autoswe.harness.ask_user_question import make_can_use_tool
from autoswe.harness.mcp_config import build_mcp_comment_server, build_mcp_inline_comment_server
from autoswe.harness.prompts import build_conflict_resolution_prompt, build_fix_prompt
from autoswe.harness.runner import AGENT_TASK_TOOLS, HandlerResult
from autoswe.providers.factory import get_vcs
from autoswe.providers.github.vcs import MissingScopeError
from autoswe.vcs.worktree import (
    commit_and_push,
    create_worktree,
    fast_forward_worktree,
    get_merge_conflict_files,
    worktree_path,
)

dbg = get_debug_logger()

_scope_error_warned = False


_MCP_COMMENT_TOOL_PREFIX = "mcp__autoswe_comment__"
_MCP_COMMENT_TOOLS = [
    f"{_MCP_COMMENT_TOOL_PREFIX}update_progress",
    f"{_MCP_COMMENT_TOOL_PREFIX}post_plan",
    f"{_MCP_COMMENT_TOOL_PREFIX}post_question",
]

_MCP_INLINE_COMMENT_TOOLS = [
    "mcp__autoswe_inline_comment__post_inline_comment",
]


def _get_branch_head_sha(wt, branch: str) -> str | None:
    """Get the latest commit SHA on a branch."""
    try:
        result = subprocess.run(
            ["git", "-C", str(wt), "rev-parse", branch],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception as e:  # Best-effort branch SHA lookup; returns None on failure.
        dbg.debug("_get_branch_head_sha failed: %s", e)

    return None


def run_fix(task: dict, guidance: str | None = None, repo_cfg: dict | None = None, cfg: dict | None = None, *, progress_callback=None, wt=None) -> HandlerResult:
    """Run fix phase with bypassPermissions. Returns done-file content.

    Return format on success:
      - "DONE: no changes detected"  (no staged changes)
      - "DONE_SUMMARY\t<claude_summary_lines>\t<commit_sha>"  (committed changes)

    If *wt* is provided (pre-synced worktree path from the orchestrator),
    reuse it instead of calling create_worktree. The orchestrator may have
    already run sync_branch + conflict resolution before handing off here.
    """
    owner, repo, issue_num = task["owner"], task["repo"], task["issue_number"]
    base_branch = task.get("base_branch", "main")
    plan_branch = task.get("plan_branch") or base_branch
    token = task["_token"]
    session_id = task.get("session_id")
    provider = (repo_cfg or {}).get("provider", "github")

    if wt is not None:
        # Orchestrator already created/synced the worktree
        dbg.debug("FIX: reusing pre-synced worktree=%s", wt)
    else:
        wt = create_worktree(owner, repo, issue_num, plan_branch, token, cfg or {}, provider,
                             default_branch=base_branch, pull_strategy="merge", push_new=True)
        dbg.debug("FIX: worktree=%s", wt)

    # Check for merge conflicts produced by pull_strategy="merge"
    branch = f"autoswe/issue-{issue_num}"
    conflict_files = get_merge_conflict_files(wt)

    # Build MCP server config: comment server (always) + inline comment server (if PR exists)
    rc = repo_cfg or {}
    mcp_servers = build_mcp_comment_server(task, rc) or {}
    allowed_tools = ["Read", "Edit", "Write", "Bash", "Glob", "Grep", "AskUserQuestion", *_MCP_COMMENT_TOOLS, *AGENT_TASK_TOOLS]

    # Register inline comment server if an existing PR exists for this branch
    branch = f"autoswe/issue-{issue_num}"
    pr_number = task.get("pr_number")
    if not pr_number:
        try:
            _link_rc = dict(rc, token=token)
            existing_pr = get_vcs(_link_rc).find_existing_pr(rc, branch)
            if existing_pr and existing_pr.number:
                pr_number = existing_pr.number
        except Exception as e:  # Best-effort PR lookup — missing inline comment server is non-fatal.
            dbg.debug("find_existing_pr failed: %s", e)

    if pr_number:
        head_sha = _get_branch_head_sha(wt, branch)
        if head_sha:
            inline_cfg = build_mcp_inline_comment_server(task, rc, head_sha, pr_number)
            if inline_cfg:
                mcp_servers.update(inline_cfg)
                allowed_tools.extend(_MCP_INLINE_COMMENT_TOOLS)
                dbg.debug("FIX: inline comment server registered (pr=%d sha=%s)", pr_number, head_sha[:8])

    plan_file_path = task.pop("plan_file_path", None)
    plan_text_override = None
    use_fresh_session = False
    if plan_file_path:
        try:
            plan_text_override = Path(plan_file_path).read_text(encoding="utf-8")
            use_fresh_session = True
            dbg.debug("FIX: starting fresh session with plan from %s", plan_file_path)
        except OSError as e:
            dbg.warning("FIX: plan file %s unreadable (%s); recovering plan from comments", plan_file_path, e)
            use_fresh_session = True

    prompt = build_fix_prompt(task, guidance, repo_root=str(wt), plan_text=plan_text_override, repo_cfg=rc)

    if conflict_files:
        files_block = "\n".join(f"  - {f}" for f in conflict_files)
        prompt += (
            "\n\n## Merge conflicts to resolve first\n\n"
            f"Pulling `origin/autoswe/issue-{issue_num}` produced conflicts in:\n{files_block}\n\n"
            "Before doing anything else, read each conflicted file, reconcile the changes "
            "(remove all `<<<<<<<` / `=======` / `>>>>>>>` markers), then run:\n\n"
            "    git add -A && git commit --no-edit\n\n"
            "to complete the merge. Then proceed with the user's request."
        )

    fix_model = rc.get("fix_model") or cfg.get("FIX_MODEL") or None
    log(f"[FIX] {task['id']} session={'NEW' if use_fresh_session else 'RESUME'} session_id={session_id or 'none'} plan_file={plan_file_path or 'none'}")
    log(f"[FIX] {task['id']} model={fix_model or 'default'} guidance={str(guidance or '')[:200]!r} prompt_len={len(prompt)} conflict_files={len(conflict_files or [])}")
    dbg.debug("FIX: model=%s guidance=%s", fix_model or "default", guidance)

    state = {}
    cut = make_can_use_tool(task, repo_cfg or {}, state, on_post=progress_callback)

    try:
        run_result = runner.run(
            prompt,
            cwd=str(wt),
            cfg=cfg or {},
            repo_cfg=rc,
            resume=None if use_fresh_session else session_id,
            model=fix_model,
            mode="read_write",
            extra_tools=allowed_tools,
            mcp_servers=mcp_servers,
            progress_callback=progress_callback,
            can_use_tool=cut,
            state=state,
        )
    except asyncio.TimeoutError:
        return HandlerResult("FAILED: timeout during fix phase")
    except Exception as e:  # State-machine boundary — any SDK failure becomes a FAILED result.
        dbg.error("run_fix: SDK error: %s", e, exc_info=True)
        return HandlerResult(f"FAILED: {e}")

    log(f"[FIX] {task['id']} sdk subtype={run_result.subtype} session={run_result.session_id} duration={run_result.duration_seconds:.1f}s cost=${run_result.cost_usd or 0:.4f} text_chars={len(run_result.text or '')}")
    dbg.debug("FIX: sdk returned subtype=%s session=%s", run_result.subtype, run_result.session_id)
    dbg.debug("FIX OUTPUT (%d chars):\n%s", len(run_result.text or ""), (run_result.text or "")[:4000])

    if state.get("asked_question_md"):
        return HandlerResult(
            "WAITING: questions",
            cost_usd=run_result.cost_usd,
            duration_seconds=run_result.duration_seconds,
            session_id=run_result.session_id,
        )

    if run_result.subtype != "success":
        return HandlerResult(
            f"FAILED: agent ended with subtype={run_result.subtype}",
            session_id=run_result.session_id,
        )

    summary = _finalize_fix(
        task, run_result, wt, owner, repo, issue_num,
        guidance, base_branch, provider, token, repo_cfg, cfg or {},
        session_id=run_result.session_id,
    )

    return summary


def _finalize_fix(
    task: dict,
    run_result,
    wt: Path,
    owner: str,
    repo: str,
    issue_num: int,
    guidance: str,
    base_branch: str,
    provider: str,
    token: str,
    repo_cfg: dict,
    cfg: dict,
    *,
    session_id: str | None = None,
) -> HandlerResult:
    """Commit, push, and return the final HandlerResult after a successful fix run.

    Shared by run_fix and resume_fix to avoid duplicating the commit/push flow.
    """
    summary_lines = [line.strip() for line in run_result.text.split("\n") if line.strip()]
    summary_text = "\n".join(summary_lines[-10:]) if summary_lines else "Changes applied."

    subject = f"autoswe: {guidance[:60]}" if guidance else "autoswe: automated fix"
    body_text = "\n".join(summary_lines[-15:]) if summary_lines else ""
    if body_text:
        commit_msg = f"{subject}\n\n{body_text}\n\nFixes #{issue_num}"
    else:
        commit_msg = f"{subject}\n\nFixes #{issue_num}"

    log(f"[FIX] {task['id']} committing subject={subject!r}")
    dbg.debug("FIX: committing with subject=%r", subject)
    try:
        commit_result = commit_and_push(wt, owner, repo, issue_num, commit_msg, base_branch, provider)
    except Exception as e:  # Commit/push boundary — any provider or git error surfaces to the task result.
        dbg.error("_finalize_fix: commit/push failed: %s", e, exc_info=True)
        return HandlerResult(f"FAILED: commit/push error: {e}")

    if not commit_result["committed"]:
        log(f"[FIX] {task['id']} NO CHANGES DETECTED — worktree unmodified by session")
        return HandlerResult(
            "DONE: no changes detected",
            cost_usd=run_result.cost_usd,
            duration_seconds=run_result.duration_seconds,
            session_id=session_id,
        )

    # Best-effort: link branch to issue in platform UI (e.g. GitHub Development section)
    if cfg.get("LINK_BRANCH_TO_ISSUE", True):
        try:
            _link_repo_cfg = dict(repo_cfg or {}, token=token)
            get_vcs(_link_repo_cfg).link_branch_to_issue(
                issue_num, commit_result["commit_sha"], commit_result["branch"],
            )
        except MissingScopeError:
            global _scope_error_warned
            if not _scope_error_warned:
                _scope_error_warned = True
                log("[FIX] link_branch_to_issue skipped: PAT missing check_runs:write scope (set LINK_BRANCH_TO_ISSUE=false to silence)")
        except Exception as e:  # Provider call is best-effort; log warning and continue past it.
            dbg.warning("link_branch_to_issue failed: %s", e, exc_info=True)
    else:
        if not _scope_error_warned:
            _scope_error_warned = True
            log("[FIX] link_branch_to_issue disabled by LINK_BRANCH_TO_ISSUE=false")

    log(f"[FIX] {task['id']} committed sha={commit_result['commit_sha']} branch={commit_result['branch']}")
    return HandlerResult(
        f"DONE_SUMMARY\t{summary_text}\t{commit_result['commit_sha']}",
        cost_usd=run_result.cost_usd,
        duration_seconds=run_result.duration_seconds,
        session_id=session_id,
    )


def resume_fix(task: dict, user_text: str, repo_cfg: dict, cfg: dict, *, progress_callback=None) -> HandlerResult:
    """Resume fix session after user replies to an AskUserQuestion.

    Reattaches the prior session, feeds the user reply, and runs Claude
    until it either asks another question (WAITING again) or finishes
    the code changes (DONE_SUMMARY).
    """
    owner, repo, issue_num = task["owner"], task["repo"], task["issue_number"]
    base_branch = task.get("base_branch", "main")
    plan_branch = task.get("plan_branch") or base_branch
    token = task["_token"]
    session_id = task.get("session_id")
    provider = (repo_cfg or {}).get("provider", "github")

    wt = create_worktree(owner, repo, issue_num, plan_branch, token, cfg or {}, provider,
                         default_branch=base_branch, pull_strategy="merge", push_new=True)
    dbg.debug("FIX_RESUME: worktree=%s session=%s", wt, session_id)

    # Fast-forward worktree to origin/branch so the session operates on current state
    ff_branch = f"autoswe/issue-{issue_num}"
    fast_forward_worktree(wt, ff_branch)

    resume_prompt = (
        f"The user replied to your question(s):\n\n{user_text}\n\n"
        "Continue implementing the fix. You may call AskUserQuestion again "
        "if needed, or proceed to make the code changes.\n\n"
        "When done, summarize what you changed."
    )

    rc = repo_cfg or {}
    mcp_servers = build_mcp_comment_server(task, rc) or {}
    allowed_tools = ["Read", "Edit", "Write", "Bash", "Glob", "Grep", "AskUserQuestion", *_MCP_COMMENT_TOOLS, *AGENT_TASK_TOOLS]

    fix_model = rc.get("fix_model") or cfg.get("FIX_MODEL") or None
    log(f"[FIX] {task['id']} session=RESUME from={session_id} user_reply_chars={len(user_text)}")

    state = {}
    cut = make_can_use_tool(task, repo_cfg or {}, state, on_post=progress_callback)

    try:
        run_result = runner.run(
            resume_prompt,
            cwd=str(wt),
            cfg=cfg or {},
            repo_cfg=rc,
            resume=session_id,
            model=fix_model,
            mode="read_write",
            extra_tools=allowed_tools,
            mcp_servers=mcp_servers,
            progress_callback=progress_callback,
            can_use_tool=cut,
            state=state,
        )
    except asyncio.TimeoutError:
        return HandlerResult("FAILED: timeout during fix resume")
    except Exception as e:  # State-machine boundary — any SDK failure becomes a FAILED result.
        dbg.error("resume_fix: SDK error: %s", e, exc_info=True)
        return HandlerResult(f"FAILED: {e}")

    dbg.debug("FIX_RESUME: sdk returned subtype=%s session=%s", run_result.subtype, run_result.session_id)
    dbg.debug("FIX_RESUME OUTPUT (%d chars):\n%s", len(run_result.text or ""), (run_result.text or "")[:4000])

    if state.get("asked_question_md"):
        return HandlerResult(
            "WAITING: questions",
            cost_usd=run_result.cost_usd,
            duration_seconds=run_result.duration_seconds,
            session_id=run_result.session_id,
        )

    if run_result.subtype != "success":
        return HandlerResult(
            f"FAILED: agent ended with subtype={run_result.subtype}",
            session_id=run_result.session_id,
        )

    summary = _finalize_fix(
        task, run_result, wt, owner, repo, issue_num,
        None, base_branch, provider, token, repo_cfg, cfg or {},
        session_id=run_result.session_id,
    )

    return summary


def resolve_sync_conflicts(
    task: dict,
    conflict_files: list[str],
    *,
    repo_cfg: dict,
    cfg: dict,
    progress_callback=None,
) -> HandlerResult:
    """Resolve merge conflicts in an existing worktree using Claude.

    Operates on an already-conflicted worktree (left by sync_branch).
    Uses a focused conflict-resolution prompt seeded with the plan.
    Resumes the prior session for continuity.
    After Claude commits the merge, pushes and returns DONE_SUMMARY.

    Does NOT call create_worktree — resolves the existing path.
    Does NOT call fast_forward_worktree — would clobber conflicted state.
    Does NOT pop plan_file_path — only reads it; plan must persist for /fix.
    """
    owner, repo, issue_num = task["owner"], task["repo"], task["issue_number"]
    base_branch = task.get("base_branch", "main")
    session_id = task.get("session_id")
    provider = (repo_cfg or {}).get("provider", "github")
    rc = repo_cfg or {}

    # Resolve existing worktree — do NOT create a new one
    wt = worktree_path(owner, repo, issue_num, cfg or {}, provider)
    if not wt.exists():
        return HandlerResult(f"FAILED: worktree missing at {wt}; cannot resolve conflicts")

    dbg.debug("RESOLVE: worktree=%s session=%s conflicts=%d", wt, session_id, len(conflict_files))

    # Read plan file if available — do NOT pop it (persist for downstream /fix)
    plan_text = None
    plan_file_path = task.get("plan_file_path")
    if plan_file_path:
        try:
            plan_text = Path(plan_file_path).read_text(encoding="utf-8")
            dbg.debug("RESOLVE: plan from %s", plan_file_path)
        except OSError as e:
            dbg.warning("RESOLVE: plan file %s unreadable (%s)", plan_file_path, e)

    prompt = build_conflict_resolution_prompt(
        task, conflict_files, plan_text=plan_text, base_branch=base_branch, repo_cfg=rc,
    )

    # Focused tool set — no AskUserQuestion (keep autonomous), no inline comments
    mcp_servers = build_mcp_comment_server(task, rc) or {}
    allowed_tools = ["Read", "Edit", "Write", "Bash", "Glob", "Grep", *_MCP_COMMENT_TOOLS, *AGENT_TASK_TOOLS]

    log(
        f"[RESOLVE] {task['id']} session={'RESUME' if session_id else 'NEW'} "
        f"session_id={session_id or 'none'} conflicts={len(conflict_files)}"
    )

    fix_model = rc.get("fix_model") or cfg.get("FIX_MODEL") or None
    dbg.debug("RESOLVE: model=%s", fix_model or "default")

    state = {}
    cut = make_can_use_tool(task, repo_cfg or {}, state, on_post=progress_callback)

    try:
        run_result = runner.run(
            prompt,
            cwd=str(wt),
            cfg=cfg or {},
            repo_cfg=rc,
            resume=session_id,  # None if first conflict with no prior session
            model=fix_model,
            mode="read_write",
            extra_tools=allowed_tools,
            disallowed_tools_override=["AskUserQuestion"],
            mcp_servers=mcp_servers,
            progress_callback=progress_callback,
            can_use_tool=cut,
            state=state,
        )
    except asyncio.TimeoutError:
        return HandlerResult("FAILED: timeout during conflict resolution")
    except Exception as e:  # State-machine boundary — any SDK failure becomes a FAILED result.
        dbg.error("resolve_sync_conflicts: SDK error: %s", e, exc_info=True)
        return HandlerResult(f"FAILED: {e}")

    log(
        f"[RESOLVE] {task['id']} sdk subtype={run_result.subtype} "
        f"session={run_result.session_id} duration={run_result.duration_seconds:.1f}s"
    )

    if run_result.subtype != "success":
        return HandlerResult(
            f"FAILED: conflict resolution ended subtype={run_result.subtype}",
            cost_usd=run_result.cost_usd,
            duration_seconds=run_result.duration_seconds,
            session_id=run_result.session_id,
        )

    # Verify conflicts are actually cleared
    remaining = get_merge_conflict_files(wt)
    if remaining:
        files_list = ", ".join(remaining)
        return HandlerResult(
            f"FAILED: unresolved conflicts: {files_list}",
            cost_usd=run_result.cost_usd,
            duration_seconds=run_result.duration_seconds,
            session_id=run_result.session_id,
        )

    # Push the resolved merge commit
    repo_cfg_for_vcs = {"owner": owner, "repo": repo, "token": "", "provider": provider}
    branch = get_vcs(repo_cfg_for_vcs).branch_name(issue_num)
    try:
        subprocess.run(
            ["git", "-C", str(wt), "push", "origin", branch],
            capture_output=True, text=True, timeout=60, check=True,
        )
    except Exception as e:  # subprocess can raise TimeoutExpired, CalledProcessError, OSError
        return HandlerResult(
            f"FAILED: push after resolution failed: {e}",
            cost_usd=run_result.cost_usd,
            duration_seconds=run_result.duration_seconds,
            session_id=run_result.session_id,
        )

    # Get full commit SHA for linking
    try:
        full_sha_result = subprocess.run(
            ["git", "-C", str(wt), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10, check=True,
        )
        commit_sha = full_sha_result.stdout.strip()
    except Exception:  # Best-effort; fallback to short SHA below.
        commit_sha = None

    # Best-effort: link branch to issue in platform UI
    token = task.get("_token")
    if cfg.get("LINK_BRANCH_TO_ISSUE", True) and token:
        try:
            _link_repo_cfg = dict(rc, token=token)
            get_vcs(_link_repo_cfg).link_branch_to_issue(
                issue_num, commit_sha or "unknown", branch,
            )
        except Exception as e:
            dbg.warning("link_branch_to_issue failed: %s", e, exc_info=True)

    # Compute summary stats
    try:
        short_sha_result = subprocess.run(
            ["git", "-C", str(wt), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=10, check=True,
        )
        short_sha = short_sha_result.stdout.strip()
    except Exception:  # Subprocess call (git rev-parse) is best-effort; fallback to "unknown".
        short_sha = "unknown"

    try:
        ahead_result = subprocess.run(
            ["git", "-C", str(wt), "log", f"origin/{base_branch}..HEAD", "--oneline"],
            capture_output=True, text=True, timeout=10, check=False,
        )
        ahead_count = len(ahead_result.stdout.strip().split("\n")) if ahead_result.stdout.strip() else 0
    except Exception:  # Subprocess call (git log) is best-effort; fallback to 0.
        ahead_count = 0

    summary = (
        f"Resolved merge conflicts in {len(conflict_files)} file(s) "
        f"and merged origin/{base_branch} into {branch}. "
        f"{ahead_count} commits ahead."
    )

    return HandlerResult(
        f"DONE_SUMMARY\t{summary}\t{short_sha}",
        cost_usd=run_result.cost_usd,
        duration_seconds=run_result.duration_seconds,
        session_id=run_result.session_id,
    )
