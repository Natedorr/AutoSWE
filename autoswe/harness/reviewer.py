"""Reviewer handler — read-only code review on feature branch.

Runs a fresh (non-resumable) Claude session with read-only tool access
to review the diff between the feature branch and its base branch.
The review report is persisted to ~/.claude/reviews/ and posted as
an issue comment. The next /fix or /plan auto-injects the report as
prompt context, then clears it (pop-after-first-use).
"""
from __future__ import annotations

import asyncio
import re
import subprocess
from pathlib import Path

from autoswe.core.config import resolve_harness
from autoswe.core.logging_utils import get_debug_logger, log
from autoswe.harness import runner
from autoswe.harness.ask_user_question import make_can_use_tool
from autoswe.harness.prompts import _find_plan_in_comments, build_review_prompt
from autoswe.harness.runner import HandlerResult
from autoswe.providers.factory import get_tracker
from autoswe.tracking.labels import parse_review_verdict
from autoswe.vcs.worktree import create_worktree, worktree_path

dbg = get_debug_logger()

_REVIEW_MAX_DIFF_LINES = 2000

# Canonical verdict tokens (must match parse_review_verdict's recognition of
# the "## Verdict" section: LGTM / Needs changes / Blocked).
_REVIEW_VERDICTS = ("LGTM", "Needs changes", "Blocked")

# Claude Agent SDK output_format payload for review runs (SDK >= 0.2.87).
# The full markdown report stays in `report` (posted as the review comment and
# persisted to ~/.claude/reviews/); `verdict` replaces the fragile
# "## Verdict" section scrape as the /pr gate (see _resolve_review_report).
REVIEW_OUTPUT_SCHEMA = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "verdict": {"type": "string", "enum": list(_REVIEW_VERDICTS)},
            "critical_count": {"type": "integer", "minimum": 0},
            "medium_count": {"type": "integer", "minimum": 0},
            "informational_count": {"type": "integer", "minimum": 0},
            "report": {"type": "string", "minLength": 1},
        },
        "required": ["verdict", "report"],
    },
}

# Trailing "## Verdict" section (heading to next heading or end of text).
# Stripped when the structured verdict replaces it, so the posted report never
# carries two verdict sections (or one contradicting the gated status).
_VERDICT_SECTION_RE = re.compile(
    r"^#{1,6}\s*Verdict\b.*?(?:\n#{1,6}\s|\Z)",
    re.MULTILINE | re.DOTALL | re.IGNORECASE,
)


def _resolve_review_report(result) -> tuple[str, str]:
    """Resolve (report_text, status) for a review RunResult.

    Returns the markdown report to post/persist and the gating status
    ("reviewed" / "review_failed" / "review_blocked") derived from the final
    report — so the logged status and the downstream
    ``_map_done_to_status`` gate always agree.

    Priority:
    1. ``result.structured_output`` (set by the Claude backend when the run
       used ``output_format`` with REVIEW_OUTPUT_SCHEMA, SDK >= 0.2.87) —
       schema-validated verdict + report. The report's trailing "## Verdict"
       section is stripped and, for a non-LGTM verdict, re-appended with the
       structured token, so the posted document carries exactly one verdict
       section that agrees with the gated status.
    2. Text fallback — the whole free-text response is the report. Kept
       intact so runs without structured output (old SDKs, backend without the
       "structured_output" capability, error subtypes) behave exactly as
       before.
    """
    so = getattr(result, "structured_output", None)
    if isinstance(so, dict):
        verdict = so.get("verdict")
        report = so.get("report")
        if verdict in _REVIEW_VERDICTS and isinstance(report, str) and report.strip():
            stripped = _VERDICT_SECTION_RE.sub("", report, count=1)
            if verdict != "LGTM":
                # Reinforce the verdict section for the (human-readable) report
                # so parse_review_verdict() on the stored text agrees with the
                # structured gate.
                stripped = stripped.rstrip() + f"\n\n## Verdict\n\n{verdict}\n"
            report_text = stripped.strip()
            dbg.debug("REVIEW: using structured verdict=%s (report=%d chars)", verdict, len(report))
            return report_text, parse_review_verdict(report_text)
        dbg.debug("REVIEW: structured_output present but unusable (verdict=%r, report=%r) — falling back to text",
                  verdict, (report or "")[:80])
    return result.text or "", parse_review_verdict(result.text or "")


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

    # 5. Read-only session (fresh, no resume).
    #    Structured output: when the backend supports it ("structured_output"
    #    capability — Claude Agent SDK >= 0.2.87), pass the review JSON Schema
    #    so the run ends in a validated {verdict, report}; otherwise (Codex,
    #    older SDKs) the run stays free-text and the verdict is parsed from
    #    the "## Verdict" section.
    state = {}
    cut = make_can_use_tool(task, repo_cfg, state, read_only=True)
    output_format = None
    if runner.backend_has_capability(harness, "structured_output"):
        output_format = REVIEW_OUTPUT_SCHEMA

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
            output_format=output_format,
        )
    except asyncio.TimeoutError:
        return HandlerResult("FAILED: timeout during review phase")
    except Exception as e:  # State-machine boundary -- any handler failure becomes a FAILED result for emit().
        return HandlerResult(f"FAILED: review error: {e}")

    log(f"[REVIEW] {task['id']} session={result.session_id} cost=${result.cost_usd or 0:.4f}")

    # 6. Resolve report + verdict (structured output preferred, text fallback).
    report_text, review_status = _resolve_review_report(result)
    log(f"[REVIEW] {task['id']} status={review_status} structured={'yes' if result.structured_output else 'no'}")

    # 7. Persist report to ~/.claude/reviews/<slug>.md
    review_path = _get_reviews_dir() / _review_filename(task["id"])
    review_path.write_text(report_text, encoding="utf-8")

    # 8. Return HandlerResult with review text embedded in done_content.
    #    done_content stays a plain "## Verdict"-style document so every
    #    downstream consumer (labels._map_done_to_status →
    #    parse_review_verdict, emit comment body) works unchanged.
    #    emit() will produce a post_comment effect → progress.finalize()
    #    patches the sticky progress comment in-place, consistent with all
    #    other handlers (plan, fix, sync, etc.).
    return HandlerResult(
        done_content="REVIEW_READY\t" + report_text,
        cost_usd=result.cost_usd,
        duration_seconds=result.duration_seconds,
        session_id=result.session_id,          # actual review session (not fix session)
        review_file_path=str(review_path),
    )


def _run_git(wt: Path, args: list[str]) -> str:
    """Run a git command in the worktree. Returns stdout."""
    result = subprocess.run(
        ["git", "-C", str(wt), *args],
        capture_output=True, text=True, timeout=30, check=True,
    )
    return result.stdout.strip()
