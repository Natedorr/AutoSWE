import asyncio
import subprocess
from pathlib import Path
from typing import Optional

from autoswe.core.config import LOGS_DIR, resolve_harness
from autoswe.core.logging_utils import init_debug_logger, log
from autoswe.harness import runner
from autoswe.harness.ask_user_question import make_can_use_tool
from autoswe.harness.mcp_config import build_mcp_comment_server
from autoswe.harness.prompts import BOT_MARKER, build_plan_prompt
from autoswe.harness.runner import HandlerResult
from autoswe.providers.factory import get_tracker
from autoswe.tracking.comments import _PLAN_RE, _QUESTIONS_RE
from autoswe.vcs.worktree import create_worktree

dbg = init_debug_logger(LOGS_DIR)


def _interpret_plan_result(result, state, harness: dict) -> tuple[str, Optional[str]]:
    """Interpret a plan-phase RunResult, returning (done_content, plan_file_path).

    Checks MCP-specific fields (plan_posted, question_posted) only when the
    backend advertises the ``"mcp"`` capability.  Falls back to text parsing
    (``_extract_plan_output``) when MCP is unavailable or flags are not set.

    Returns a tuple of (done_content, plan_file_path).  Callers should use
    these to construct the HandlerResult.
    """
    # 1. AskUserQuestion via can_use_tool callback (always available)
    if state.get("asked_question_md"):
        return "WAITING: questions", None

    has_mcp = runner.backend_has_capability(harness, "mcp")

    if has_mcp:
        # 2. MCP post_question → WAITING
        if result.question_posted:
            return "WAITING: questions", None

        # 3. MCP post_plan → PLAN_READY
        if result.plan_posted:
            plan_file_path: Optional[str] = None
            if result.plan_file_path:
                pf = Path(result.plan_file_path)
                if pf.exists():
                    plan_text = pf.read_text(encoding="utf-8").strip()
                    if not _plan_file_is_pending(plan_text):
                        plan_file_path = str(pf)
            return "PLAN_READY", plan_file_path

    # 4. Text-parse fallback (always available)
    plan_file: Optional[Path] = (
        Path(result.plan_file_path) if result.plan_file_path else None
    )
    comment, done_content, used_file = _extract_plan_output(result.text, plan_file=plan_file)

    plan_file_path: Optional[str] = None
    if done_content == "PLAN_READY" and used_file is not None:
        plan_file_path = str(used_file)

    # Return comment as part of done_content for _post_and_return
    return f"_POST:{done_content}\t{comment}", plan_file_path


def _get_plans_dir() -> Path:
    """Return the Claude Code plan file directory."""
    return Path.home() / ".claude" / "plans"


def _find_latest_plan_file() -> Optional[Path]:
    """Find the most recently created plan file in ~/.claude/plans/.

    Returns None if the directory does not exist or contains no .md files.
    """
    plans_dir = _get_plans_dir()
    if not plans_dir.exists():
        return None
    md_files = sorted(plans_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not md_files:
        return None
    return md_files[0]


def _plan_file_is_pending(plan_text: str) -> bool:
    """Check if a plan file is actually a placeholder waiting for user input.

    When the model asks questions via MCP post_question but then continues
    and writes a premature plan file, the file will contain indicators like
    'waiting', 'pending', 'TBD', 'once you provide', etc.
    """
    lower = plan_text.lower()
    pending_indicators = [
        "waiting for",
        "pending ",
        "tbd",
        "once you provide",
        "once the user",
        "before finalizing",
        "before implementing",
        "clarifying question",
        "need more information",
    ]
    return any(indicator in lower for indicator in pending_indicators)


def _extract_plan_output(text: str, plan_file: Path = None) -> tuple[str, str, Optional[Path]]:
    """Return (comment_body, done_content, used_file_path) using the output priority chain.

    The third element is the Path of the plan file used (when content came from
    a file), or None when content came from tags / raw text.

    Priority:
    1. Captured plan file (from Write tool call) -> "## Plan" + "PLAN_READY" + path (unless pending)
    2. <AUTOSWE_PLAN> tags in text -> "## Plan" + "PLAN_READY" + None
    3. <AUTOSWE_QUESTIONS> tags in text -> "## Questions" + "WAITING: questions" + None
    4. Filesystem scan (_find_latest_plan_file) -> "## Plan" + "PLAN_READY" + path (last resort)
    5. Fallback -> "## Claude's response" + "WAITING: see comment" + None

    Tags (steps 2-3) are checked BEFORE the filesystem scan (step 4) to avoid
    picking up another session's plan file during concurrent execution.
    (Regression fix for issue #36 — plan file collision.)
    """
    # 1. Check for captured plan file path (from Write tool call — per-session)
    captured_file = plan_file
    try:
        if captured_file is not None and captured_file.exists():
            plan_text = captured_file.read_text(encoding="utf-8").strip()
            # If the plan file is a placeholder waiting for user input,
            # fall through to check for tags instead of returning PLAN_READY
            if _plan_file_is_pending(plan_text):
                dbg.debug("PLAN: plan file detected as pending (waiting for user input) — falling through to tag detection")
            else:
                comment = f"## Plan\n\n{plan_text}\n\n_Reply with `/fix` to start coding._"
                return comment, "PLAN_READY", captured_file
    except FileNotFoundError:
        captured_file = None

    # 2. Check for <AUTOSWE_PLAN> tags (session-correct, before filesystem scan)
    plan_m = _PLAN_RE.search(text or "")
    questions_m = _QUESTIONS_RE.search(text or "")

    if plan_m:
        dbg.warning("PLAN: deprecated <AUTOSWE_PLAN> tag used — migrate to mcp__autoswe_comment__post_plan tool")
        plan_text = plan_m.group(1).strip()
        comment = f"## Plan\n\n{plan_text}\n\n_Reply with `/fix` to start coding._"
        return comment, "PLAN_READY", None
    elif questions_m:
        dbg.warning("PLAN: deprecated <AUTOSWE_QUESTIONS> tag used — migrate to mcp__autoswe_comment__post_question tool")
        q_text = questions_m.group(1).strip()
        comment = f"## Questions\n\n{q_text}\n\n_Reply in this thread to answer._"
        return comment, "WAITING: questions", None

    # 3. Filesystem scan — true last resort (may return another session's file)
    fs_file: Optional[Path] = None
    try:
        fs_file = _find_latest_plan_file()
    except Exception:
        fs_file = None
    if fs_file is not None:
        plan_text = fs_file.read_text(encoding="utf-8").strip()
        if not _plan_file_is_pending(plan_text):
            comment = f"## Plan\n\n{plan_text}\n\n_Reply with `/fix` to start coding._"
            return comment, "PLAN_READY", fs_file

    # 4. Raw text fallback
    comment = f"## Claude's response\n\n{text or '(no response)'}"
    return comment, "WAITING: see comment", None


def _post_and_return(task: dict, comment_body: str, done_content: str, repo_cfg: dict, *, progress_callback=None) -> str:
    # If the MCP server already handled posting (post_plan/post_question were called),
    # the progress comment was updated in-place — don't post again.
    # Only post as a fallback when:
    #  1. progress_callback is None (no sticky comment system), OR
    #  2. The output came from a deprecated XML tag / native plan file (MCP tools were never called)
    if progress_callback is not None:
        # Try to push the fallback text through the sticky progress callback.
        # If the MCP tool was already called during the session, the sticky comment
        # already has the right content — this just sets a final fallback.
        progress_callback(comment_body + BOT_MARKER)
        return done_content

    # No progress system available — fall back to posting a new comment
    rc = dict(repo_cfg)
    rc.setdefault("owner", task.get("owner", ""))
    rc.setdefault("repo", task.get("repo", ""))
    rc.setdefault("pat", task.get("_token", ""))
    tracker = get_tracker(rc)
    try:
        tracker.post_comment(rc, task["issue_number"], comment_body + BOT_MARKER)
    except Exception as e:
        dbg.error("planner: comment failed: %s", e)
    return done_content


def _get_git_head(wt: Path) -> Optional[str]:
    """Return git HEAD SHA of the worktree, or None on error."""
    result = subprocess.run(
        ["git", "-C", str(wt), "rev-parse", "HEAD"],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode == 0:
        return result.stdout.strip()
    return None


def _ensure_worktree_unchanged(wt: Path, head_before: Optional[str]) -> None:
    """Reset the worktree if the agent modified it during plan phase."""
    head_after = _get_git_head(wt)
    if head_before and head_after and head_before != head_after:
        log(f"[WARN] Plan session modified worktree ({head_before[:8]} -> {head_after[:8]}). Resetting.")
        subprocess.run(["git", "-C", str(wt), "reset", "--hard", head_before], timeout=10, check=False)
        subprocess.run(["git", "-C", str(wt), "clean", "-fd"], timeout=10, check=False)


def run_plan(task: dict, repo_cfg: dict, cfg: dict, guidance: str = None, *, progress_callback=None, wt=None) -> str:
    """Run plan phase. Returns done-file content string.

    When *wt* is provided (e.g. from the sync-wrapped orchestrator), the
    pre-synced worktree is used directly without creating a new one.
    """
    owner, repo, issue_num = task["owner"], task["repo"], task["issue_number"]
    base_branch = task.get("base_branch", "main")
    plan_branch = task.get("plan_branch") or base_branch
    token = task["_token"]
    provider = repo_cfg.get("provider", "github")

    if wt is None:
        wt = create_worktree(owner, repo, issue_num, plan_branch, token, cfg or {}, provider,
                             default_branch=base_branch, pull_strategy="reset", push_new=False)
    dbg.debug("PLAN: worktree=%s", wt)
    prompt = build_plan_prompt(task, repo_root=str(wt), repo_cfg=repo_cfg, guidance=guidance)

    harness = resolve_harness("plan", repo_cfg, cfg or {})
    plan_model = harness.get("model")
    log(f"[PLAN] {task['id']} session=NEW model={plan_model or 'default'} guidance_len={len(guidance or '')}")
    dbg.debug("PLAN: model=%s guidance=%s", plan_model or "default", guidance)

    state = {}
    cut = make_can_use_tool(task, repo_cfg, state, on_post=progress_callback, read_only=True)

    head_before = _get_git_head(wt)

    try:
        result = runner.run(
            prompt,
            cwd=str(wt),
            cfg=cfg or {},
            repo_cfg=repo_cfg,
            model=plan_model,
            mode="plan",
            mcp_servers=build_mcp_comment_server(task, repo_cfg),
            progress_callback=progress_callback,
            can_use_tool=cut,
            state=state,
            harness_cfg=harness,
        )
    except asyncio.TimeoutError:
        return HandlerResult("FAILED: timeout during plan phase")
    except Exception as e:
        dbg.error("run_plan: SDK error: %s", e, exc_info=True)
        return HandlerResult(f"FAILED: {e}")

    _ensure_worktree_unchanged(wt, head_before)

    log(f"[PLAN] {task['id']} session={result.session_id} subtype={result.subtype} duration={result.duration_seconds:.1f}s cost=${result.cost_usd or 0:.4f}")
    dbg.debug("PLAN: sdk returned subtype=%s session=%s len=%d", result.subtype, result.session_id, len(result.text or ""))
    dbg.debug("PLAN OUTPUT (%d chars):\n%s", len(result.text or ""), (result.text or "")[:4000])
    if result.session_id:
        task["session_id"] = result.session_id
    task["last_phase"] = "plan"

    done_content, plan_file_path = _interpret_plan_result(result, state, harness)

    # Helper returns "WAITING..." directly, or "_POST:done_content\tcomment" for posting
    if done_content.startswith("_POST:"):
        inner_done, comment = done_content[len("_POST:"):].split("\t", 1)
        if plan_file_path:
            task["plan_file_path"] = plan_file_path
        _post_and_return(task, comment, inner_done, repo_cfg, progress_callback=progress_callback)
        log(f"[PLAN] {task['id']} complete done={inner_done} plan_file={plan_file_path or 'none'}")
        return HandlerResult(
            inner_done,
            cost_usd=result.cost_usd,
            duration_seconds=result.duration_seconds,
            plan_file_path=plan_file_path,
        )

    if done_content == "PLAN_READY" and plan_file_path:
        task["plan_file_path"] = plan_file_path
        log(f"[PLAN] {task['id']} complete done=PLAN_READY plan_file={plan_file_path}")
    return HandlerResult(
        done_content,
        cost_usd=result.cost_usd,
        duration_seconds=result.duration_seconds,
        plan_file_path=plan_file_path,
    )


def resume_plan(task: dict, user_text: str, repo_cfg: dict, cfg: dict, *, progress_callback=None, wt=None) -> str:
    """Resume plan session after user reply. Returns done-file content string.

    When *wt* is provided (e.g. from the sync-wrapped orchestrator), the
    pre-synced worktree is used directly without creating a new one.
    """
    owner, repo, issue_num = task["owner"], task["repo"], task["issue_number"]
    base_branch = task.get("base_branch", "main")
    plan_branch = task.get("plan_branch") or base_branch
    token = task["_token"]
    session_id = task.get("session_id")
    provider = repo_cfg.get("provider", "github")

    if wt is None:
        wt = create_worktree(owner, repo, issue_num, plan_branch, token, cfg or {}, provider,
                             default_branch=base_branch, pull_strategy="reset", push_new=False)
    dbg.debug("PLAN_RESUME: worktree=%s session=%s", wt, session_id)

    resume_prompt = (
        f"The user replied to your last question(s):\n\n{user_text}\n\n"
        "Continue planning. If you now have enough information, call the "
        "`mcp__autoswe_comment__post_plan` tool with your plan.\n\n"
        "If you need clarification, use the `AskUserQuestion` tool — "
        "the user will reply via an issue comment and your session will resume.\n\n"
        "Fallback (only if MCP tools are unavailable): output a <AUTOSWE_PLAN> or "
        "<AUTOSWE_QUESTIONS> block."
    )

    harness = resolve_harness("plan", repo_cfg, cfg or {})
    plan_model = harness.get("model")
    log(f"[PLAN] {task['id']} session=RESUME from={session_id} reply_chars={len(user_text)}")

    state = {}
    cut = make_can_use_tool(task, repo_cfg, state, on_post=progress_callback, read_only=True)

    head_before = _get_git_head(wt)

    try:
        result = runner.run(
            resume_prompt,
            cwd=str(wt),
            cfg=cfg or {},
            repo_cfg=repo_cfg,
            resume=session_id,
            model=plan_model,
            mode="plan",
            mcp_servers=build_mcp_comment_server(task, repo_cfg),
            progress_callback=progress_callback,
            can_use_tool=cut,
            state=state,
            harness_cfg=harness,
        )
    except asyncio.TimeoutError:
        return HandlerResult("FAILED: timeout during plan resume")
    except Exception as e:
        dbg.error("resume_plan: SDK error: %s", e, exc_info=True)
        return HandlerResult(f"FAILED: {e}")

    _ensure_worktree_unchanged(wt, head_before)

    dbg.debug("PLAN_RESUME: sdk returned subtype=%s session=%s len=%d", result.subtype, result.session_id, len(result.text or ""))
    dbg.debug("PLAN_RESUME OUTPUT (%d chars):\n%s", len(result.text or ""), (result.text or "")[:4000])
    if result.session_id:
        task["session_id"] = result.session_id
    task["last_phase"] = "plan"

    done_content, plan_file_path = _interpret_plan_result(result, state, harness)

    if done_content.startswith("_POST:"):
        inner_done, comment = done_content[len("_POST:"):].split("\t", 1)
        if plan_file_path:
            task["plan_file_path"] = plan_file_path
        _post_and_return(task, comment, inner_done, repo_cfg, progress_callback=progress_callback)
        log(f"[PLAN] {task['id']} resume complete done={inner_done} plan_file={plan_file_path or 'none'}")
        return HandlerResult(
            inner_done,
            cost_usd=result.cost_usd,
            duration_seconds=result.duration_seconds,
            plan_file_path=plan_file_path,
        )

    if done_content == "PLAN_READY" and plan_file_path:
        task["plan_file_path"] = plan_file_path
        log(f"[PLAN] {task['id']} resume complete done=PLAN_READY plan_file={plan_file_path}")
    return HandlerResult(
        done_content,
        cost_usd=result.cost_usd,
        duration_seconds=result.duration_seconds,
        plan_file_path=plan_file_path,
    )
