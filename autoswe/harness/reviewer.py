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

from autoswe.core.config import resolve_harness
from autoswe.core.logging_utils import get_debug_logger, log
from autoswe.harness import runner
from autoswe.harness.ask_user_question import make_can_use_tool
from autoswe.harness.prompts import _find_plan_in_comments, build_review_prompt
from autoswe.harness.runner import HandlerResult
from autoswe.harness.schemas import REVIEW_SCHEMA, output_format_for
from autoswe.providers.factory import get_tracker
from autoswe.vcs.worktree import create_worktree, ensure_worktree_unchanged, worktree_path

dbg = get_debug_logger()

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


def _report_text_from_result(result) -> str:
    """Choose the review report body, preferring structured output (issue #159).

    When the run was issued with a ``REVIEW_SCHEMA`` and the SDK returned a
    validated payload carrying a non-empty ``report_markdown``, that is the
    source of truth.  Otherwise fall back to the raw ``result.text`` (the
    pre-structured behavior) so a run that did not produce structured output
    still yields a report.
    """
    structured = getattr(result, "structured_output", None)
    if isinstance(structured, dict):
        report = str(structured.get("report_markdown") or "").strip()
        if report:
            return report
    return result.text or ""


def _verdict_from_result(result) -> str | None:
    """Extract the reviewer's structured verdict, if the run produced one.

    Reads the ``verdict`` field off the schema-validated structured output
    (REVIEW_SCHEMA).  Returns the stripped string, or ``None`` when the run
    had no structured output / no verdict — in that case the status gate falls
    back to the markdown "## Verdict" regex (issue #173 F-18).
    """
    structured = getattr(result, "structured_output", None)
    if isinstance(structured, dict):
        verdict = structured.get("verdict")
        if verdict is not None:
            verdict = str(verdict).strip()
            if verdict:
                return verdict
    return None


def run_review(
    task: dict,
    repo_cfg: dict,
    cfg: dict,
    guidance: str | None = None,
    *,
    progress_callback=None,
    wt=None,
) -> HandlerResult:
    """Run a read-only code review on the feature branch.

    When ``wt`` is provided (pre-synced worktree from the orchestrator), the
    handler skips its own worktree creation and uses the synced path directly.
    This mirrors the planner/coder pattern where _run_*_with_sync() ensures
    base→feature merge before the agent runs.

    Steps:
      1. Ensure worktree on autoswe/issue-{N} (or use pre-synced ``wt``)
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

    # 1. Worktree — reuse pre-synced from orchestrator, or create/reset locally
    if wt is not None:
        # Pre-synced worktree from orchestrator — reuse directly
        wt_path: Path = Path(wt)
    else:
        wt_path = worktree_path(owner, repo, issue_num, cfg or {}, provider)
        if wt_path.exists():
            log(f"[REVIEW] Reusing worktree {wt_path}")
        else:
            wt_path = create_worktree(
                owner, repo, issue_num, base_branch, token, cfg or {}, provider,
                default_branch=base_branch, pull_strategy="reset", push_new=False,
            )

    # 2. Compute diff
    try:
        diff_stat = _run_git(wt_path, ["diff", "--stat", f"origin/{base_branch}...HEAD"])
        diff_text = _run_git(wt_path, ["diff", f"origin/{base_branch}...HEAD"])
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
    except Exception as e:  # Provider resilience -- fetch_comments may fail (network, auth); proceed with empty plan.
        dbg.debug("REVIEW: fetch_comments failed: %s", e)
        comments = []
        plan_text = ""

    # 4. Build prompt
    prompt = build_review_prompt(
        task,
        repo_root=str(wt_path),
        repo_cfg=repo_cfg,
        plan_text=plan_text,
        diff_stat=diff_stat,
        diff_text=diff_text,
        guidance=guidance,
    )

    harness = resolve_harness("review", repo_cfg, cfg or {})
    review_model = harness.get("model")
    log(f"[REVIEW] {task['id']} session=NEW model={review_model or 'default'} diff_stat_lines={diff_stat.count(chr(10))}")

    # 5. Read-only session (fresh, no resume)
    state = {}
    cut = make_can_use_tool(task, repo_cfg, state, read_only=True)

    # Loudly degrade when the backend cannot enforce read-only access (issue
    # #166): the review session may still edit the worktree, so the post-run
    # ensure_worktree_unchanged backstop below is the real guarantee.
    if not runner.has_read_only_enforcement(harness):
        log(f"[WARN][REVIEW] {task['id']} backend '{harness.get('backend')}' has no read-only "
            f"enforcement (no 'mode'/'can_use_tool') — review edits will be rolled back "
            f"post-run (issue #166)")

    head_before = _get_git_head(wt_path)

    # Request a schema-validated review report when the resolved backend
    # supports it (issue #159). _report_text_from_result() prefers the
    # structured payload and falls back to result.text.
    review_output_format = (
        output_format_for(REVIEW_SCHEMA)
        if runner.backend_has_capability(harness, "structured_output")
        else None
    )

    try:
        result = runner.run(
            prompt,
            cwd=str(wt_path),
            cfg=cfg or {},
            repo_cfg=repo_cfg,
            resume=None,  # CRITICAL: one-off session
            model=review_model,
            mode="read_only",
            max_turns=80,
            can_use_tool=cut,
            state=state,
            progress_callback=progress_callback,
            harness_cfg=harness,
            output_format=review_output_format,
        )
    except asyncio.TimeoutError:
        return HandlerResult("FAILED: timeout during review phase")
    except Exception as e:  # State-machine boundary -- any handler failure becomes a FAILED result for emit().
        return HandlerResult(f"FAILED: review error: {e}")

    # Backstop: roll back any worktree edits the review session made (issue #166).
    # run_review previously had no equivalent check at all — a reviewer that
    # edited files (the normal agent case) would carry those edits into the next
    # phase. The worktree is pre-synced clean by the orchestrator, so anything
    # found here is an agent edit.
    ensure_worktree_unchanged(wt_path, head_before)

    log(f"[REVIEW] {task['id']} session={result.session_id} cost=${result.cost_usd or 0:.4f}")

    # Prefer the schema-validated report when present; fall back to the raw
    # text otherwise (issue #159). Both the file write and the done_content
    # use the same source of truth.
    report_text = _report_text_from_result(result)
    # The structured verdict (issue #173 F-18): the status gate reads this
    # before falling back to the markdown "## Verdict" regex.
    verdict = _verdict_from_result(result)

    # 6. Persist report to ~/.claude/reviews/<slug>.md
    review_path = _get_reviews_dir() / _review_filename(task["id"])
    review_path.write_text(report_text, encoding="utf-8")

    # 7. Return HandlerResult with review text embedded in done_content.
    #    emit() will produce a post_comment effect → progress.finalize()
    #    patches the sticky progress comment in-place, consistent with all
    #    other handlers (plan, fix, sync, etc.).
    return HandlerResult(
        done_content="REVIEW_READY\t" + report_text,
        cost_usd=result.cost_usd,
        duration_seconds=result.duration_seconds,
        session_id=result.session_id,          # actual review session (not fix session)
        review_file_path=str(review_path),
        verdict=verdict,
    )


def _run_git(wt: Path, args: list[str]) -> str:
    """Run a git command in the worktree. Returns stdout."""
    result = subprocess.run(
        ["git", "-C", str(wt), *args],
        capture_output=True, text=True, timeout=30, check=True,
    )
    return result.stdout.strip()


def _get_git_head(wt: Path) -> str | None:
    """Return git HEAD SHA of the worktree, or None on error."""
    result = subprocess.run(
        ["git", "-C", str(wt), "rev-parse", "HEAD"],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode == 0:
        return result.stdout.strip()
    return None
