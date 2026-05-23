"""Reviewer handler — read-only code review on feature branch.

Runs a fresh (non-resumable) Claude session with read-only tool access
to review the diff between the feature branch and its base branch.
The review report is persisted to ~/.claude/reviews/ and posted as
an issue comment. The next /fix or /plan auto-injects the report as
prompt context, then clears it (pop-after-first-use).
"""
from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

from autoswe.core.config import LOGS_DIR
from autoswe.core.logging_utils import init_debug_logger, log
from autoswe.harness import runner
from autoswe.harness.ask_user_question import make_can_use_tool
from autoswe.harness.prompts import _find_plan_in_comments, build_review_prompt
from autoswe.harness.runner import AGENT_TASK_TOOLS, HandlerResult
from autoswe.providers.factory import get_tracker
from autoswe.vcs.worktree import create_worktree, worktree_path

dbg = init_debug_logger(LOGS_DIR)

_REVIEW_MAX_DIFF_LINES = 2000


def _get_reviews_dir() -> Path:
    """Return the review reports directory."""
    d = Path.home() / ".claude" / "reviews"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _review_filename(task_id: str) -> str:
    """Sanitize task_id (owner/repo#N) for use as a filename."""
    return task_id.replace("/", "_").replace("#", "_") + ".md"


def _truncate(text: str, max_lines: int) -> str:
    """Truncate text to max_lines, appending a warning if cut."""
    lines = text.split("\n")
    if len(lines) <= max_lines:
        return text
    return "\n".join(lines[:max_lines]) + f"\n\n... (truncated, {len(lines) - max_lines} more lines)"


def run_review(
    task: dict,
    repo_cfg: dict,
    cfg: dict,
    guidance: str = None,
    *,
    progress_callback=None,
) -> HandlerResult:
    """Run a read-only code review on the feature branch.

    Steps:
      1. Ensure worktree on autoswe/issue-{N}
      2. Compute git diff (base_branch..HEAD, stat + full)
      3. Extract plan text from issue comments
      4. Build review prompt (issue + plan + diff)
      5. Run Claude SDK fresh session, read-only
      6. Persist report to ~/.claude/reviews/<slug>.md
      7. Return HandlerResult(REVIEW_READY\t<text>, review_file_path=...)
         emit() produces a post_comment effect that patches the sticky
         progress comment in-place via progress.finalize().
    """
    owner, repo, issue_num = task["owner"], task["repo"], task["issue_number"]
    base_branch = task.get("base_branch", "main")
    token = task["_token"]
    provider = repo_cfg.get("provider", "github")

    # 1. Worktree — reuse if present, create if missing
    wt = worktree_path(owner, repo, issue_num, cfg, provider)
    if wt.exists():
        log(f"[REVIEW] Reusing worktree {wt}")
    else:
        wt = create_worktree(
            owner, repo, issue_num, base_branch, token, cfg, provider,
            default_branch=base_branch, pull_strategy="reset", push_new=False,
        )

    # 2. Compute diff
    try:
        diff_stat = _run_git(wt, ["diff", "--stat", f"origin/{base_branch}...HEAD"])
        diff_text = _run_git(wt, ["diff", f"origin/{base_branch}...HEAD"])
        diff_text = _truncate(diff_text, _REVIEW_MAX_DIFF_LINES)
    except subprocess.CalledProcessError as e:
        diff_stat = "(no diff)"
        diff_text = f"(diff failed: {e.stderr or str(e)})"
        log(f"[REVIEW] git diff failed for {task['id']}: {e}")

    # 3. Extract plan from comments
    rc = dict(repo_cfg)
    rc.setdefault("owner", owner)
    rc.setdefault("repo", repo)
    rc.setdefault("pat", token)
    tracker = get_tracker(rc)
    try:
        comments = tracker.fetch_comments(rc, issue_num)
        plan_text = _find_plan_in_comments(comments)
    except Exception as e:
        dbg.debug("REVIEW: fetch_comments failed: %s", e)
        comments = []
        plan_text = ""

    # 4. Build prompt
    prompt = build_review_prompt(
        task,
        repo_root=str(wt),
        repo_cfg=repo_cfg,
        plan_text=plan_text,
        diff_stat=diff_stat,
        diff_text=diff_text,
        guidance=guidance,
    )

    review_model = repo_cfg.get("review_model") or cfg.get("REVIEW_MODEL") or None
    log(f"[REVIEW] {task['id']} session=NEW model={review_model or 'default'} diff_stat_lines={diff_stat.count(chr(10))}")

    # 5. Read-only session (fresh, no resume)
    state = {}
    cut = make_can_use_tool(task, repo_cfg, state, read_only=True)

    try:
        result = runner.run(
            prompt,
            cwd=str(wt),
            cfg=cfg,
            repo_cfg=repo_cfg,
            resume=None,  # CRITICAL: one-off session
            model=review_model,
            permission_mode="plan",
            allowed_tools=["Read", "Glob", "Grep", *AGENT_TASK_TOOLS],
            max_turns=80,
            can_use_tool=cut,
            state=state,
            progress_callback=progress_callback,
        )
    except asyncio.TimeoutError:
        return HandlerResult("FAILED: timeout during review phase")
    except Exception as e:
        dbg.error("run_review: SDK error: %s", e, exc_info=True)
        return HandlerResult(f"FAILED: {e}")

    log(f"[REVIEW] {task['id']} session={result.session_id} cost=${result.cost_usd or 0:.4f}")

    # 6. Persist report to ~/.claude/reviews/<slug>.md
    review_path = _get_reviews_dir() / _review_filename(task["id"])
    review_path.write_text(result.text, encoding="utf-8")

    # 7. Return HandlerResult with review text embedded in done_content.
    #    emit() will produce a post_comment effect → progress.finalize()
    #    patches the sticky progress comment in-place, consistent with all
    #    other handlers (plan, fix, sync, etc.).
    return HandlerResult(
        done_content="REVIEW_READY\t" + result.text,
        cost_usd=result.cost_usd,
        duration_seconds=result.duration_seconds,
        session_id=result.session_id,          # actual review session (not fix session)
        review_file_path=str(review_path),
    )


def _run_git(wt: Path, args: list[str]) -> str:
    """Run a git command in the worktree. Returns stdout."""
    result = subprocess.run(
        ["git", "-C", str(wt)] + args,
        capture_output=True, text=True, timeout=30, check=True,
    )
    return result.stdout.strip()
