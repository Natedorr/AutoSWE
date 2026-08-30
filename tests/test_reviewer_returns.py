"""Tests for autoswe.harness.reviewer handler return values."""

from contextlib import contextmanager
from unittest.mock import patch

from autoswe.harness.runner import RunResult


def _r(text, session_id="sess-review", subtype="success"):
    """Shorthand for RunResult(text, session_id, subtype)."""
    return RunResult(text, session_id, subtype)


def make_task(token="ghp_fake", session_id=None):
    return {
        "id": "o/r#1",
        "owner": "o",
        "repo": "r",
        "issue_number": 1,
        "title": "Test issue",
        "body": "Issue description.",
        "base_branch": "master",
        "session_id": session_id,
        "_token": token,
    }


@contextmanager
def _patch_worktree(tmp_path):
    """Context manager that patches worktree + review dir operations."""
    from pathlib import Path
    class FakePath(Path):
        def exists(self):
            return True
    fake = FakePath(tmp_path)
    reviews_dir = tmp_path / "reviews"
    reviews_dir.mkdir(parents=True, exist_ok=True)
    with patch("autoswe.harness.reviewer.worktree_path", return_value=fake):
        with patch("autoswe.harness.reviewer._get_reviews_dir", return_value=reviews_dir):
            yield tmp_path


FETCH_COMMENTS_PATCH = patch("autoswe.tracking.api._fetch_comments", return_value=[])


# ---------------------------------------------------------------------------
# run_review return values
# ---------------------------------------------------------------------------


def test_run_review_returns_review_ready(tmp_path, mock_gh_post_comment):
    """Happy path: run_review returns REVIEW_READY with review text embedded
    in done_content. The sticky progress comment is finalized by emit() →
    progress.finalize(), NOT by the reviewer posting directly."""
    review_text = "## Summary\n\nLooks good overall.\n\n## Verdict\n\nLGTM"
    task = make_task()

    with _patch_worktree(tmp_path):
        with patch("autoswe.harness.reviewer._run_git", return_value="file.py | 10 +++++++---\n1 file changed, 7 insertions(+), 3 deletions(-)"):
            with FETCH_COMMENTS_PATCH:
                with patch("autoswe.harness.runner.run", return_value=_r(review_text)):
                    from autoswe.harness.reviewer import run_review
                    result = run_review(task, {}, {"GITHUB_TOKEN": "tok"})

    assert result.done_content.startswith("REVIEW_READY\t")
    assert review_text in result.done_content
    assert result.review_file_path is not None
    # Reviewer should NOT post comments directly anymore — that's handled
    # by emit() → post_comment effect → progress.finalize()
    assert len(mock_gh_post_comment.posted) == 0


def test_run_review_uses_fresh_session(tmp_path, mock_gh_post_comment):
    """run_review calls runner.run with resume=None (one-off session)."""
    run_calls = []

    def fake_run(prompt, **kwargs):
        run_calls.append(kwargs)
        return _r("LGTM")

    task = make_task()

    with _patch_worktree(tmp_path):
        with patch("autoswe.harness.reviewer._run_git", return_value="stat"):
            with FETCH_COMMENTS_PATCH:
                with patch("autoswe.harness.runner.run", side_effect=fake_run):
                    from autoswe.harness.reviewer import run_review
                    run_review(task, {}, {"GITHUB_TOKEN": "tok"})

    assert run_calls[0]["resume"] is None


def test_run_review_is_read_only(tmp_path, mock_gh_post_comment):
    """run_review uses mode='read_only' (backend translates to plan permission + read-only tools) and read_only=True."""
    run_calls = []
    cut_calls = []

    def fake_cut(task, rc, state, read_only=False):
        cut_calls.append(read_only)
        return None

    def fake_run(prompt, **kwargs):
        run_calls.append(kwargs)
        return _r("LGTM")

    task = make_task()

    with _patch_worktree(tmp_path):
        with patch("autoswe.harness.reviewer._run_git", return_value="stat"):
            with FETCH_COMMENTS_PATCH:
                with patch("autoswe.harness.reviewer.make_can_use_tool", side_effect=fake_cut):
                    with patch("autoswe.harness.runner.run", side_effect=fake_run):
                        from autoswe.harness.reviewer import run_review
                        run_review(task, {}, {"GITHUB_TOKEN": "tok"})

    assert run_calls[0]["mode"] == "read_only"
    # Verify the backend maps mode="read_only" correctly
    from autoswe.harness.backends.claude_code import _MODE_CONFIG
    perm, tools, _disallowed = _MODE_CONFIG["read_only"]
    assert perm == "plan"
    assert "Read" in tools
    assert "Write" not in tools
    assert "Edit" not in tools
    assert "Bash" not in tools
    # Progress/task tools included
    from autoswe.harness.runner import PROGRESS_TOOLS
    for tool in PROGRESS_TOOLS:
        assert tool in tools, f"{tool} should be in read_only mode tools"
    assert "Agent" not in tools, (
        "Agent (sub-agent spawning) must not be available in a read-only review"
    )
    assert cut_calls[0] is True
    assert "AskUserQuestion" not in tools, (
        "Reviewer must not be able to ask questions — review session is "
        "one-shot and non-resumable; findings only."
    )


def test_run_review_includes_diff_in_prompt(tmp_path, mock_gh_post_comment):
    """run_review prompt contains the git diff."""
    diff_text = "diff --git a/file.py b/file.py\n+new line"
    run_calls = []

    def fake_run(prompt, **kwargs):
        run_calls.append(prompt)
        return _r("LGTM")

    task = make_task()

    with _patch_worktree(tmp_path):
        with patch("autoswe.harness.reviewer._run_git", return_value=diff_text):
            with FETCH_COMMENTS_PATCH:
                with patch("autoswe.harness.runner.run", side_effect=fake_run):
                    from autoswe.harness.reviewer import run_review
                    run_review(task, {}, {"GITHUB_TOKEN": "tok"})

    assert "new line" in run_calls[0]


def test_run_review_includes_plan_from_comments(tmp_path, mock_gh_post_comment):
    """run_review extracts plan from comments and includes it in prompt."""
    run_calls = []

    def fake_run(prompt, **kwargs):
        run_calls.append(prompt)
        return _r("LGTM")

    task = make_task()

    with _patch_worktree(tmp_path):
        with patch("autoswe.harness.reviewer._run_git", return_value="stat"):
            with patch("autoswe.tracking.api._fetch_comments", return_value=[
                {"body": "## Plan\n\nStep 1: Fix the bug\nStep 2: Add tests",
                 "created_at": "2026-01-01T01:00:00Z",
                 "user": {"login": "autoswe[bot]", "id": 1, "type": "Bot"},
                 "id": 999,
                 "author_association": "OWNER"},
            ]):
                with patch("autoswe.harness.runner.run", side_effect=fake_run):
                    from autoswe.harness.reviewer import run_review
                    run_review(task, {}, {"GITHUB_TOKEN": "tok"})

    assert "Step 1: Fix the bug" in run_calls[0]


def test_run_review_writes_file(tmp_path, mock_gh_post_comment):
    """run_review writes review file to ~/.claude/reviews/. Comment posting
    is handled by emit() → progress.finalize(), NOT by the reviewer directly."""
    review_text = "## Summary\n\nGood work.\n\n## Verdict\n\nLGTM"

    task = make_task()

    with _patch_worktree(tmp_path):
        with patch("autoswe.harness.reviewer._run_git", return_value="stat"):
            with FETCH_COMMENTS_PATCH:
                with patch("autoswe.harness.runner.run", return_value=_r(review_text)):
                    from autoswe.harness.reviewer import run_review
                    result = run_review(task, {}, {"GITHUB_TOKEN": "tok"})

    from pathlib import Path
    review_path = Path(result.review_file_path)
    assert review_path.exists()
    assert review_text in review_path.read_text()
    # Reviewer no longer posts comments directly
    assert len(mock_gh_post_comment.posted) == 0


def test_run_review_timeout_returns_failed(tmp_path, mock_gh_post_comment):
    """run_review returns FAILED on asyncio.TimeoutError."""
    import asyncio

    task = make_task()

    with _patch_worktree(tmp_path):
        with patch("autoswe.harness.reviewer._run_git", return_value="stat"):
            with FETCH_COMMENTS_PATCH:
                with patch("autoswe.harness.runner.run", side_effect=asyncio.TimeoutError()):
                    from autoswe.harness.reviewer import run_review
                    result = run_review(task, {}, {"GITHUB_TOKEN": "tok"})

    assert result.done_content.startswith("FAILED:")
    assert "timeout" in result.done_content.lower()


def test_run_review_sdk_error_returns_failed(tmp_path, mock_gh_post_comment):
    """run_review returns FAILED on SDK exception."""
    task = make_task()

    with _patch_worktree(tmp_path):
        with patch("autoswe.harness.reviewer._run_git", return_value="stat"):
            with FETCH_COMMENTS_PATCH:
                with patch("autoswe.harness.runner.run", side_effect=RuntimeError("SDK crash")):
                    from autoswe.harness.reviewer import run_review
                    result = run_review(task, {}, {"GITHUB_TOKEN": "tok"})

    assert result.done_content.startswith("FAILED:")
    assert "SDK crash" in result.done_content


# ---------------------------------------------------------------------------
# _truncate helper
# ---------------------------------------------------------------------------


def test_truncate_noop_when_short():
    from autoswe.harness.reviewer import _truncate

    short = "line1\nline2\nline3"
    assert _truncate(short, 10) == short


def test_truncate_cuts_long_text():
    from autoswe.harness.reviewer import _truncate

    long_text = "\n".join([f"line{i}" for i in range(100)])
    result = _truncate(long_text, 10)
    assert "line0" in result
    assert "line99" not in result
    assert "truncated" in result


# ---------------------------------------------------------------------------
# _pop_review_file helper
# ---------------------------------------------------------------------------


def test_pop_review_file_returns_text_and_clears_field(tmp_path):
    from autoswe.harness.prompts import _pop_review_file

    review_file = tmp_path / "review.md"
    review_file.write_text("Review findings here")
    task = {"review_file_path": str(review_file)}

    text = _pop_review_file(task)
    assert text == "Review findings here"
    assert task["review_file_path"] is None


def test_pop_review_file_empty_when_missing(tmp_path):
    from autoswe.harness.prompts import _pop_review_file

    task = {"review_file_path": str(tmp_path / "nonexistent.md")}
    assert _pop_review_file(task) == ""


def test_pop_review_file_empty_when_not_set():
    from autoswe.harness.prompts import _pop_review_file

    task = {}
    assert _pop_review_file(task) == ""


# ---------------------------------------------------------------------------
# Review BLOCK injection in fix/plan prompts
# ---------------------------------------------------------------------------


def test_review_block_injected_into_fix_prompt(tmp_path):
    """build_fix_prompt injects review findings when review_file_path is set."""
    from autoswe.harness.prompts import build_fix_prompt

    review_file = tmp_path / "review.md"
    review_file.write_text("Bug in auth.py:42")
    task = {
        "id": "o/r#1", "owner": "o", "repo": "r", "issue_number": 1,
        "title": "Test", "body": "Desc", "base_branch": "main",
        "review_file_path": str(review_file),
        "_token": "tok",
    }
    prompt = build_fix_prompt(task, comments=[])
    assert "Bug in auth.py:42" in prompt
    assert task["review_file_path"] is None  # popped


def test_review_block_injected_into_plan_prompt(tmp_path):
    """build_plan_prompt injects review findings when review_file_path is set."""
    from autoswe.harness.prompts import build_plan_prompt

    review_file = tmp_path / "review.md"
    review_file.write_text("Security issue in login")
    task = {
        "id": "o/r#1", "owner": "o", "repo": "r", "issue_number": 1,
        "title": "Test", "body": "Desc", "base_branch": "main",
        "review_file_path": str(review_file),
        "_token": "tok",
    }
    prompt = build_plan_prompt(task, comments=[])
    assert "Security issue in login" in prompt
    assert task["review_file_path"] is None  # popped


# ---------------------------------------------------------------------------
# REVIEW_MODEL resolution
# ---------------------------------------------------------------------------


def test_run_review_passes_review_model_from_cfg(tmp_path, mock_gh_post_comment):
    """run_review passes model=review_model when cfg['REVIEW_MODEL'] is set."""
    run_calls = []

    def fake_run(prompt, **kwargs):
        run_calls.append(kwargs)
        return _r("LGTM")

    task = make_task()
    cfg = {"GITHUB_TOKEN": "tok", "REVIEW_MODEL": "review-cfg-model"}

    with _patch_worktree(tmp_path):
        with patch("autoswe.harness.reviewer._run_git", return_value="stat"):
            with FETCH_COMMENTS_PATCH:
                with patch("autoswe.harness.runner.run", side_effect=fake_run):
                    from autoswe.harness.reviewer import run_review
                    run_review(task, {}, cfg)

    assert run_calls[0]["model"] == "review-cfg-model"


def test_run_review_repo_cfg_model_takes_precedence(tmp_path, mock_gh_post_comment):
    """repo_cfg['review_model'] takes precedence over cfg['REVIEW_MODEL']."""
    run_calls = []

    def fake_run(prompt, **kwargs):
        run_calls.append(kwargs)
        return _r("LGTM")

    task = make_task()
    repo_cfg = {"review_model": "repo-review-model"}
    cfg = {"GITHUB_TOKEN": "tok", "REVIEW_MODEL": "cfg-review-model"}

    with _patch_worktree(tmp_path):
        with patch("autoswe.harness.reviewer._run_git", return_value="stat"):
            with FETCH_COMMENTS_PATCH:
                with patch("autoswe.harness.runner.run", side_effect=fake_run):
                    from autoswe.harness.reviewer import run_review
                    run_review(task, repo_cfg, cfg)

    assert run_calls[0]["model"] == "repo-review-model"


def test_run_review_no_model_passes_none(tmp_path, mock_gh_post_comment):
    """When no REVIEW_MODEL is configured, model=None is passed."""
    run_calls = []

    def fake_run(prompt, **kwargs):
        run_calls.append(kwargs)
        return _r("LGTM")

    task = make_task()
    cfg = {"GITHUB_TOKEN": "tok"}

    with _patch_worktree(tmp_path):
        with patch("autoswe.harness.reviewer._run_git", return_value="stat"):
            with FETCH_COMMENTS_PATCH:
                with patch("autoswe.harness.runner.run", side_effect=fake_run):
                    from autoswe.harness.reviewer import run_review
                    run_review(task, {}, cfg)

    assert run_calls[0]["model"] is None


def test_run_review_returns_review_session_id(tmp_path, mock_gh_post_comment):
    """run_review returns HandlerResult with session_id set to the review
    session (not the fix session from the task dict). This ensures completion
    comments show the review session ID, not the persistent fix session ID."""
    review_text = "LGTM"
    review_session = "review-session-44315ceb"

    # Task has a fix session_id — review should NOT use it
    task = make_task(session_id="fix-session-34ac5c01")

    with _patch_worktree(tmp_path):
        with patch("autoswe.harness.reviewer._run_git", return_value="stat"):
            with FETCH_COMMENTS_PATCH:
                with patch("autoswe.harness.runner.run",
                           return_value=_r(review_text, session_id=review_session)):
                    from autoswe.harness.reviewer import run_review
                    result = run_review(task, {}, {"GITHUB_TOKEN": "tok"})

    assert result.session_id == review_session
    assert result.session_id != task["session_id"], (
        "review HandlerResult.session_id must be the review session, "
        "NOT the fix session from the task dict"
    )


# ---------------------------------------------------------------------------
# Fallback template placeholders
# ---------------------------------------------------------------------------


def test_fix_fallback_template_contains_guidance_and_review_blocks():
    """Both {{GUIDANCE_BLOCK}} and {{REVIEW_BLOCK}} must be present in the
    fix prompt fallback template, so guidance and review findings are never
    silently dropped."""
    # Force fallback by temporarily hiding the on-disk file
    import autoswe.harness.prompts as prompts_mod
    from autoswe.harness.prompts import load_fix_prompt
    original = prompts_mod.FIX_PROMPT_FILE
    try:
        # Fake non-existent path to force fallback
        from pathlib import Path
        prompts_mod.FIX_PROMPT_FILE = Path("/nonexistent/fix.txt")
        template = load_fix_prompt()
    finally:
        prompts_mod.FIX_PROMPT_FILE = original

    assert "{{GUIDANCE_BLOCK}}" in template, (
        "Fallback fix template must contain {{GUIDANCE_BLOCK}} placeholder"
    )
    assert "{{REVIEW_BLOCK}}" in template, (
        "Fallback fix template must contain {{REVIEW_BLOCK}} placeholder"
    )


def test_plan_fallback_template_contains_guidance_and_review_blocks():
    """Both {{GUIDANCE_BLOCK}} and {{REVIEW_BLOCK}} must be present in the
    plan prompt fallback template."""
    import autoswe.harness.prompts as prompts_mod
    from autoswe.harness.prompts import load_plan_prompt
    original = prompts_mod.PLAN_PROMPT_FILE
    try:
        from pathlib import Path
        prompts_mod.PLAN_PROMPT_FILE = Path("/nonexistent/plan.txt")
        template = load_plan_prompt()
    finally:
        prompts_mod.PLAN_PROMPT_FILE = original

    assert "{{GUIDANCE_BLOCK}}" in template, (
        "Fallback plan template must contain {{GUIDANCE_BLOCK}} placeholder"
    )
    assert "{{REVIEW_BLOCK}}" in template, (
        "Fallback plan template must contain {{REVIEW_BLOCK}} placeholder"
    )


# ---------------------------------------------------------------------------
# Full flow: queue → TaskState → task dict → prompt injection
# ---------------------------------------------------------------------------


def test_build_poll_task_includes_review_file_path():
    """_build_poll_task passes review_file_path from queue to TaskState."""
    from autoswe.orch.loop import _build_poll_task
    from autoswe.orch.types import ApiState
    from autoswe.providers.base import NormalizedIssue

    review_path = "/tmp/review.md"
    slug = "gh:owner_repo_1"
    queue = {
        slug: {
            "id": slug,
            "owner": "owner",
            "repo": "repo",
            "issue_number": 1,
            "title": "Test issue",
            "body": "Issue description.",
            "autoswe_status": "planned",
            "plan_branch": None,
            "base_branch": "main",
            "attempt_count": 0,
            "first_dispatched_at": None,
            "last_dispatched_command": "/fix",
            "last_dispatched_command_id": 1,
            "last_consumed_reply_id": None,
            "session_id": "some-session",
            "pr_number": None,
            "review_file_path": review_path,
            "created_at": "2026-01-01T00:00:00Z",
            "last_synced": "2026-01-01T00:00:00Z",
            "provider": "github",
        }
    }

    issue = NormalizedIssue(
        number=1,
        title="Test issue",
        body="Issue description.",
        owner="owner",
        repo="repo",
        state="open",
    )
    api = ApiState(issue=issue, comments=(), open_pr_numbers=())

    pt = _build_poll_task(queue, slug, api, {}, {})

    assert pt.task_state.review_file_path == review_path


def test_build_task_dict_includes_review_file_path_from_task_state():
    """_build_task_dict copies review_file_path from TaskState to task dict."""
    from autoswe.orch.run import _build_task_dict
    from autoswe.orch.types import Action, ApiState, TaskState, World
    from autoswe.providers.base import NormalizedIssue

    review_path = "/tmp/review.md"
    issue = NormalizedIssue(
        number=1,
        title="Test issue",
        body="Issue description.",
        owner="owner",
        repo="repo",
        state="open",
    )
    api = ApiState(issue=issue, comments=(), open_pr_numbers=())
    task = TaskState(
        slug="gh:owner_repo_1",
        owner="owner",
        repo="repo",
        issue_number=1,
        title="Test issue",
        body="Issue description.",
        status="plan_ready",
        plan_branch=None,
        base_branch="main",
        attempt_count=0,
        first_dispatched_at=None,
        last_dispatched_command="/fix",
        last_dispatched_command_id=1,
        last_consumed_reply_id=None,
        session_id="some-session",
        pr_number=None,
        guard_blocked=False,
        gh_closed=False,
        pending_command=None,
        pending_guidance=None,
        pending_user_reply=None,
        review_file_path=review_path,
    )
    world = World(api=api, task=task, cfg={}, repo_cfg={"pat": "tok"})
    action = Action(kind="fix", slug="gh:owner_repo_1")

    task_dict = _build_task_dict(world, action)

    assert task_dict["review_file_path"] == review_path


def test_full_review_injection_flow(tmp_path):
    """End-to-end: review_file_path flows through _build_poll_task, _build_task_dict,
    and gets injected into the fix prompt via _pop_review_file."""
    from autoswe.harness.prompts import build_fix_prompt
    from autoswe.orch.loop import _build_poll_task
    from autoswe.orch.run import _build_task_dict
    from autoswe.orch.types import Action, ApiState
    from autoswe.providers.base import NormalizedIssue

    # 1. Create review file
    review_file = tmp_path / "review.md"
    review_file.write_text("Bug found in auth.py:42 — null pointer")

    # 2. Queue with entry containing review_file_path
    slug = "gh:owner_repo_42"
    queue = {
        slug: {
            "id": slug,
            "owner": "owner",
            "repo": "repo",
            "issue_number": 42,
            "title": "Fix auth bug",
            "body": "Auth is broken",
            "autoswe_status": "planned",
            "plan_branch": None,
            "base_branch": "main",
            "attempt_count": 1,
            "first_dispatched_at": "2026-01-01T00:00:00Z",
            "last_dispatched_command": "/review",
            "last_dispatched_command_id": 2,
            "last_consumed_reply_id": 1,
            "session_id": "fix-session-123",
            "pr_number": None,
            "review_file_path": str(review_file),
            "created_at": "2026-01-01T00:00:00Z",
            "last_synced": "2026-01-01T00:00:00Z",
            "provider": "github",
        }
    }

    issue = NormalizedIssue(
        number=42,
        title="Fix auth bug",
        body="Auth is broken",
        owner="owner",
        repo="repo",
        state="open",
    )
    api = ApiState(issue=issue, comments=(), open_pr_numbers=())

    # 3. Build TaskState via _build_poll_task (loop layer)
    pt = _build_poll_task(queue, slug, api, {}, {"pat": "tok"})
    assert pt.task_state.review_file_path == str(review_file)

    # 4. Build task dict via _build_task_dict (run layer)
    action = Action(kind="fix", slug=slug)
    task_dict = _build_task_dict(pt.world, action)
    assert task_dict["review_file_path"] == str(review_file)

    # 5. Build fix prompt — review findings should be injected and file path cleared
    prompt = build_fix_prompt(task_dict, comments=[])
    assert "Bug found in auth.py:42" in prompt
    assert "null pointer" in prompt
    assert task_dict["review_file_path"] is None  # popped after first use


# ---------------------------------------------------------------------------
# Structured-output verdict (Claude Agent SDK >= 0.2.87, issue #130)
# ---------------------------------------------------------------------------

def test_run_review_passes_output_format_when_supported(tmp_path, mock_gh_post_comment):
    """run_review passes REVIEW_OUTPUT_SCHEMA as output_format when the backend
    advertises the 'structured_output' capability (Claude default harness)."""
    from autoswe.harness.reviewer import REVIEW_OUTPUT_SCHEMA

    run_calls = []

    def fake_run(prompt, **kwargs):
        run_calls.append(kwargs)
        return _r("## Verdict\n\nLGTM")

    task = make_task()
    with _patch_worktree(tmp_path):
        with patch("autoswe.harness.reviewer._run_git", return_value="stat"):
            with FETCH_COMMENTS_PATCH:
                with patch("autoswe.harness.runner.run", side_effect=fake_run):
                    from autoswe.harness.reviewer import run_review
                    run_review(task, {}, {"GITHUB_TOKEN": "tok"})

    assert "output_format" in run_calls[0], "output_format kwarg not passed to runner.run"
    assert run_calls[0]["output_format"] == REVIEW_OUTPUT_SCHEMA


def test_run_review_omits_output_format_when_unsupported(tmp_path, mock_gh_post_comment):
    """When the backend lacks the capability (Codex), output_format must be
    None so the run stays free-text (Codex has no structured output)."""
    run_calls = []

    def fake_run(prompt, **kwargs):
        run_calls.append(kwargs)
        return _r("## Verdict\n\nLGTM")

    task = make_task()
    with _patch_worktree(tmp_path):
        with patch("autoswe.harness.reviewer._run_git", return_value="stat"):
            with FETCH_COMMENTS_PATCH:
                with patch("autoswe.harness.runner.run", side_effect=fake_run):
                    with patch("autoswe.harness.reviewer.runner.backend_has_capability",
                               return_value=False):
                        from autoswe.harness.reviewer import run_review
                        run_review(task, {}, {"GITHUB_TOKEN": "tok"})

    assert run_calls[0].get("output_format") is None


def test_resolve_review_report_prefers_structured_verdict():
    """A schema-validated structured_output wins over the text verdict, and the
    report's own '## Verdict' section is stripped so the posted doc has exactly
    one (matching) verdict section."""
    from autoswe.harness.reviewer import _resolve_review_report

    report = "## Summary\n\nok\n\n## Verdict\n\nLGTM"
    result = RunResult(
        text=report, session_id="s", subtype="success",
        structured_output={"verdict": "Needs changes", "report": report},
    )
    report_out, status = _resolve_review_report(result)
    # Status is derived from the (corrected) report, so it agrees with the gate.
    assert status == "review_failed"
    # The stale "## Verdict\n\nLGTM" section is stripped and replaced with the
    # structured one so parse_review_verdict agrees with the gate.
    assert "LGTM" not in report_out
    assert "## Verdict" in report_out
    assert "Needs changes" in report_out


def test_resolve_review_report_structured_lgtm_reanchors_section():
    """LGTM structured verdict: the existing '## Verdict' section is stripped
    and re-appended with the structured token (as with every verdict), so the
    posted doc carries exactly one verdict section reading LGTM."""
    from autoswe.harness.reviewer import _resolve_review_report

    report = "## Summary\n\nfine\n\n## Verdict\n\nLGTM"
    result = RunResult(
        text=report, session_id="s", subtype="success",
        structured_output={"verdict": "LGTM", "report": report},
    )
    report_out, status = _resolve_review_report(result)
    assert status == "reviewed"
    # The verdict section survives (re-anchored to the structured token) and is
    # the single source parse_review_verdict reads.
    assert report_out.count("## Verdict") == 1
    assert "LGTM" in report_out


def test_resolve_review_report_lgtm_not_downgraded_by_blocking_word_in_body():
    """Regression (review finding #1): an LGTM structured verdict must NOT be
    flipped to review_blocked/review_failed just because the report body
    mentions 'Blocked'/'Needs changes'. The re-anchored '## Verdict' section is
    what parse_review_verdict reads, so body prose can't override the verdict."""
    from autoswe.harness.reviewer import _resolve_review_report

    body = "## Summary\n\nNo production impact.\n\n## Findings\n\nNo findings are Blocked.\n\n## Verdict\n\nLGTM"
    result = RunResult(
        text=body, session_id="s", subtype="success",
        structured_output={"verdict": "LGTM", "report": body},
    )
    report_out, status = _resolve_review_report(result)
    # Even though "Blocked" appears in the body prose, the gate must stay LGTM.
    assert status == "reviewed"
    # The verdict section still reads LGTM (body prose "Blocked" is not the gate).
    assert "## Verdict\n\nLGTM" in report_out


def test_resolve_review_report_falls_back_to_text_when_no_structured():
    """No structured_output (Codex / older SDK) -> whole text is the report and
    the verdict is scraped from the '## Verdict' section (historical path)."""
    from autoswe.harness.reviewer import _resolve_review_report

    text = "## Summary\n\nbug\n\n## Verdict\n\nBlocked"
    result = RunResult(text=text, session_id="s", subtype="success")
    report_out, verdict = _resolve_review_report(result)
    assert verdict == "review_blocked"
    assert report_out == text  # text returned verbatim on fallback


def test_resolve_review_report_unusable_structured_falls_back():
    """structured_output present but with an invalid verdict token must not be
    trusted -> fall back to text parsing."""
    from autoswe.harness.reviewer import _resolve_review_report

    text = "## Verdict\n\nBlocked"
    result = RunResult(
        text=text, session_id="s", subtype="success",
        structured_output={"verdict": "MAYBE", "report": "whatever"},
    )
    report_out, verdict = _resolve_review_report(result)
    assert verdict == "review_blocked"
    assert report_out == text


def test_structured_verdict_maps_to_status():
    """The structured verdict, embedded in done_content, gates /pr exactly like
    the text path: _map_done_to_status -> parse_review_verdict."""
    from autoswe.tracking.labels import _map_done_to_status

    report = "## Summary\n\nx\n\n## Verdict\n\nNeeds changes"
    result = RunResult(
        text=report, session_id="s", subtype="success",
        structured_output={"verdict": "Needs changes", "report": report},
    )
    from autoswe.harness.reviewer import _resolve_review_report
    report_out, status = _resolve_review_report(result)
    done = "REVIEW_READY\t" + report_out
    # done_content gate and the reported status agree.
    assert _map_done_to_status(done, kind="review") == "review_failed"
    assert status == "review_failed"
