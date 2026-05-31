"""Tests for autoswe.harness.planner handler return values."""

from contextlib import contextmanager
from unittest.mock import patch

from autoswe.harness.runner import RunResult


def _r(text, session_id="sess", subtype="success"):
    """Shorthand for RunResult(text, session_id, subtype)."""
    return RunResult(text, session_id, subtype)


def make_task(token="ghp_fake", session_id=None):
    return {
        "id": "o_r_1",
        "owner": "o",
        "repo": "r",
        "issue_number": 1,
        "title": "Test",
        "body": "/plan",
        "base_branch": "master",
        "session_id": session_id,
        "_token": token,
    }


@contextmanager
def _patch_worktree(tmp_path):
    """Context manager that patches create_worktree and suppresses plan file detection."""
    with patch("autoswe.harness.planner.create_worktree", return_value=tmp_path):
        with patch("autoswe.harness.planner._find_latest_plan_file", return_value=None):
            yield tmp_path


FETCH_COMMENTS_PATCH = patch("autoswe.tracking.api._fetch_comments", return_value=[])


# ---------------------------------------------------------------------------
# run_plan return values
# ---------------------------------------------------------------------------

def test_run_plan_returns_plan_ready_on_plan_block(tmp_path, mock_gh_post_comment):
    claude_text = "Thinking...\n<AUTOSWE_PLAN>\nStep 1: do stuff\n</AUTOSWE_PLAN>"
    task = make_task()

    with _patch_worktree(tmp_path):
        with FETCH_COMMENTS_PATCH:
            with patch("autoswe.harness.runner.run", return_value=_r(claude_text, "sess-1")):
                from autoswe.harness.planner import run_plan
                result = run_plan(task, {}, {"GITHUB_TOKEN": "tok"})

    assert result.done_content == "PLAN_READY"
    assert task["session_id"] == "sess-1"
    assert len(mock_gh_post_comment.posted) == 1
    assert "Step 1" in mock_gh_post_comment.posted[0]["body"]
    assert "<!-- autoswe-bot -->" in mock_gh_post_comment.posted[0]["body"]


def test_run_plan_returns_waiting_on_questions_block(tmp_path, mock_gh_post_comment):
    claude_text = "Let me ask:\n<AUTOSWE_QUESTIONS>\n1. Which approach?\n</AUTOSWE_QUESTIONS>"
    task = make_task()

    with _patch_worktree(tmp_path):
        with FETCH_COMMENTS_PATCH:
            with patch("autoswe.harness.runner.run", return_value=_r(claude_text, "sess-2")):
                from autoswe.harness.planner import run_plan
                result = run_plan(task, {}, {"GITHUB_TOKEN": "tok"})

    assert result.done_content.startswith("WAITING:")
    assert len(mock_gh_post_comment.posted) == 1
    assert "Which approach" in mock_gh_post_comment.posted[0]["body"]


def test_run_plan_returns_waiting_when_no_block(tmp_path, mock_gh_post_comment):
    claude_text = "I looked at the code and here is my analysis."
    task = make_task()

    with _patch_worktree(tmp_path):
        with FETCH_COMMENTS_PATCH:
            with patch("autoswe.harness.runner.run", return_value=_r(claude_text, "sess-3")):
                from autoswe.harness.planner import run_plan
                result = run_plan(task, {}, {"GITHUB_TOKEN": "tok"})

    assert result.done_content.startswith("WAITING:")


def test_run_plan_returns_failed_on_timeout(tmp_path, mock_gh_post_comment):
    import asyncio
    task = make_task()

    with _patch_worktree(tmp_path):
        with FETCH_COMMENTS_PATCH:
            with patch("autoswe.harness.runner.run", side_effect=asyncio.TimeoutError()):
                from autoswe.harness.planner import run_plan
                result = run_plan(task, {}, {"GITHUB_TOKEN": "tok"})

    assert result.done_content.startswith("FAILED:")
    assert "timeout" in result.done_content.lower()


def test_run_plan_returns_failed_on_sdk_error(tmp_path, mock_gh_post_comment):
    task = make_task()

    with _patch_worktree(tmp_path):
        with FETCH_COMMENTS_PATCH:
            with patch("autoswe.harness.runner.run", side_effect=RuntimeError("SDK crashed")):
                from autoswe.harness.planner import run_plan
                result = run_plan(task, {}, {"GITHUB_TOKEN": "tok"})

    assert result.done_content.startswith("FAILED:")
    assert "SDK crashed" in result.done_content


# ---------------------------------------------------------------------------
# resume_plan return values
# ---------------------------------------------------------------------------

def test_resume_plan_returns_plan_ready(tmp_path, mock_gh_post_comment):
    claude_text = "<AUTOSWE_PLAN>\nDo X then Y.\n</AUTOSWE_PLAN>"
    task = make_task(session_id="sess-existing")

    with _patch_worktree(tmp_path):
        with patch("autoswe.harness.runner.run", return_value=_r(claude_text, "sess-new")):
            from autoswe.harness.planner import resume_plan
            result = resume_plan(task, "Use approach A.", {}, {"GITHUB_TOKEN": "tok"})

    assert result.done_content == "PLAN_READY"
    assert task["session_id"] == "sess-new"


def test_resume_plan_passes_session_id_to_runner(tmp_path, mock_gh_post_comment):
    run_calls = []

    def fake_run(prompt, **kwargs):
        run_calls.append(kwargs)
        return _r("<AUTOSWE_PLAN>\nPlan\n</AUTOSWE_PLAN>", "new-sess")

    task = make_task(session_id="original-sess")

    with _patch_worktree(tmp_path):
        with patch("autoswe.harness.runner.run", side_effect=fake_run):
            from autoswe.harness.planner import resume_plan
            resume_plan(task, "My answer.", {}, {"GITHUB_TOKEN": "tok"})

    assert run_calls[0]["resume"] == "original-sess"


# ---------------------------------------------------------------------------
# Edge cases for planner
# ---------------------------------------------------------------------------

def test_run_plan_records_plan_file_path_on_plan_ready(tmp_path, mock_gh_post_comment):
    """When run_plan produces PLAN_READY from a valid plan file, task['plan_file_path'] is set."""
    plan_file = tmp_path / "my-plan.md"
    plan_file.write_text("# My Plan\n\nStep 1: do stuff")
    task = make_task()

    with _patch_worktree(tmp_path):
        with FETCH_COMMENTS_PATCH:
            with patch("autoswe.harness.planner._find_latest_plan_file", return_value=plan_file):
                with patch("autoswe.harness.runner.run", return_value=_r("", "sess-1")):
                    from autoswe.harness.planner import run_plan
                    result = run_plan(task, {}, {"GITHUB_TOKEN": "tok"})

    assert result.done_content == "PLAN_READY"
    assert task.get("plan_file_path") == str(plan_file)


def test_run_plan_does_not_record_plan_file_when_pending(tmp_path, mock_gh_post_comment):
    """When the plan file is a pending placeholder, task['plan_file_path'] is NOT set."""
    plan_file = tmp_path / "pending-plan.md"
    plan_file.write_text("# Plan\n\nWaiting for user to provide more information.")
    task = make_task()
    claude_text = "<AUTOSWE_PLAN>\nActual plan\n</AUTOSWE_PLAN>"

    with _patch_worktree(tmp_path):
        with FETCH_COMMENTS_PATCH:
            with patch("autoswe.harness.planner._find_latest_plan_file", return_value=plan_file):
                with patch("autoswe.harness.runner.run", return_value=_r(claude_text)):
                    from autoswe.harness.planner import run_plan
                    result = run_plan(task, {}, {"GITHUB_TOKEN": "tok"})

    assert result.done_content == "PLAN_READY"
    assert "plan_file_path" not in task


def test_run_plan_does_not_record_plan_file_on_waiting(tmp_path, mock_gh_post_comment):
    """When planner returns WAITING (questions, no plan file), task['plan_file_path'] is NOT set."""
    task = make_task()
    claude_text = "<AUTOSWE_QUESTIONS>\n1. Which approach?\n</AUTOSWE_QUESTIONS>"

    with _patch_worktree(tmp_path):
        with FETCH_COMMENTS_PATCH:
            with patch("autoswe.harness.runner.run", return_value=_r(claude_text)):
                from autoswe.harness.planner import run_plan
                result = run_plan(task, {}, {"GITHUB_TOKEN": "tok"})

    assert result.done_content.startswith("WAITING:")
    assert "plan_file_path" not in task


def test_run_plan_both_plan_and_questions(tmp_path, mock_gh_post_comment):
    """When both blocks exist, <AUTOSWE_PLAN> takes precedence."""
    claude_text = "<AUTOSWE_QUESTIONS>\n1. Question?\n</AUTOSWE_QUESTIONS>\n<AUTOSWE_PLAN>\nDo X\n</AUTOSWE_PLAN>"
    task = make_task()

    with _patch_worktree(tmp_path):
        with FETCH_COMMENTS_PATCH:
            with patch("autoswe.harness.runner.run", return_value=_r(claude_text)):
                from autoswe.harness.planner import run_plan
                result = run_plan(task, {}, {"GITHUB_TOKEN": "tok"})

    assert result.done_content == "PLAN_READY"


def test_run_plan_questions_only(tmp_path, mock_gh_post_comment):
    """Only <AUTOSWE_QUESTIONS> block should return WAITING."""
    claude_text = "<AUTOSWE_QUESTIONS>\n1. Approach A or B?\n2. Testing strategy?\n</AUTOSWE_QUESTIONS>"
    task = make_task()

    with _patch_worktree(tmp_path):
        with FETCH_COMMENTS_PATCH:
            with patch("autoswe.harness.runner.run", return_value=_r(claude_text)):
                from autoswe.harness.planner import run_plan
                result = run_plan(task, {}, {"GITHUB_TOKEN": "tok"})

    assert result.done_content.startswith("WAITING:")
    assert len(mock_gh_post_comment.posted) == 1
    assert "Approach A or B" in mock_gh_post_comment.posted[0]["body"]


def test_resume_plan_returns_waiting_on_more_questions(tmp_path, mock_gh_post_comment):
    """Resume can still ask more questions."""
    claude_text = "<AUTOSWE_QUESTIONS>\n2. Follow-up question?\n</AUTOSWE_QUESTIONS>"
    task = make_task(session_id="sess-existing")

    with _patch_worktree(tmp_path):
        with patch("autoswe.harness.runner.run", return_value=_r(claude_text, "sess-2")):
            from autoswe.harness.planner import resume_plan
            result = resume_plan(task, "Answer to question 1.", {}, {"GITHUB_TOKEN": "tok"})

    assert result.done_content.startswith("WAITING:")


def test_run_plan_empty_text_from_sdk(tmp_path, mock_gh_post_comment):
    """Empty SDK response should return WAITING with no response message."""
    task = make_task()

    with _patch_worktree(tmp_path):
        with FETCH_COMMENTS_PATCH:
            with patch("autoswe.harness.runner.run", return_value=_r("")):
                from autoswe.harness.planner import run_plan
                result = run_plan(task, {}, {"GITHUB_TOKEN": "tok"})

    assert result.done_content.startswith("WAITING:")
    assert "(no response)" in mock_gh_post_comment.posted[0]["body"]


def test_run_plan_uses_mode_plan(tmp_path, mock_gh_post_comment):
    """Plan phase should use mode='plan' (backend translates to read-only tools + MCP comment tools)."""
    run_calls = []

    def fake_run(prompt, **kwargs):
        run_calls.append(kwargs)
        return _r("<AUTOSWE_PLAN>\nPlan\n</AUTOSWE_PLAN>")

    task = make_task()

    with _patch_worktree(tmp_path):
        with FETCH_COMMENTS_PATCH:
            with patch("autoswe.harness.runner.run", side_effect=fake_run):
                from autoswe.harness.planner import run_plan
                run_plan(task, {}, {"GITHUB_TOKEN": "tok"})

    # Phase 3: handler passes mode="plan", backend translates to permission+tools
    assert run_calls[0]["mode"] == "plan"
    # Verify the backend maps mode="plan" correctly
    from autoswe.harness.backends.claude_code import _MODE_CONFIG
    perm, tools, disallowed = _MODE_CONFIG["plan"]
    assert perm == "plan"
    assert "Read" in tools
    assert "Glob" in tools
    assert "Grep" in tools
    assert "Agent" not in tools
    assert "ExitPlanMode" in disallowed
    # MCP comment tools included
    assert "mcp__autoswe_comment__post_plan" in tools
    assert "mcp__autoswe_comment__post_question" in tools
    # PROGRESS_TOOLS included
    from autoswe.harness.runner import PROGRESS_TOOLS
    for tool in PROGRESS_TOOLS:
        assert tool in tools, f"{tool} should be in plan mode tools"


def test_resume_plan_uses_mode_plan(tmp_path, mock_gh_post_comment):
    """Resume plan phase should use mode='plan' (same tool set as run_plan)."""
    run_calls = []

    def fake_run(prompt, **kwargs):
        run_calls.append(kwargs)
        return _r("<AUTOSWE_PLAN>\nPlan\n</AUTOSWE_PLAN>")

    task = make_task(session_id="sess-existing")

    with _patch_worktree(tmp_path):
        with patch("autoswe.harness.runner.run", side_effect=fake_run):
            from autoswe.harness.planner import resume_plan
            resume_plan(task, "Use approach A.", {}, {"GITHUB_TOKEN": "tok"})

    assert run_calls[0]["mode"] == "plan"
    # Verify PROGRESS_TOOLS included, Agent excluded
    from autoswe.harness.backends.claude_code import _MODE_CONFIG
    _perm, tools, _disallowed = _MODE_CONFIG["plan"]
    from autoswe.harness.runner import PROGRESS_TOOLS
    for tool in PROGRESS_TOOLS:
        assert tool in tools, f"{tool} should be in plan mode tools"
    assert "Agent" not in tools


def test_run_plan_uses_plan_branch_in_prompt(tmp_path, mock_gh_post_comment):
    """plan_branch should override base_branch in the plan prompt."""
    run_calls = []

    def fake_run(prompt, **kwargs):
        run_calls.append({"prompt": prompt})
        return _r("<AUTOSWE_PLAN>\nPlan\n</AUTOSWE_PLAN>")

    task = make_task()
    task["plan_branch"] = "develop"

    with _patch_worktree(tmp_path):
        with FETCH_COMMENTS_PATCH:
            with patch("autoswe.harness.runner.run", side_effect=fake_run):
                from autoswe.harness.planner import run_plan
                run_plan(task, {}, {"GITHUB_TOKEN": "tok"})

    assert "develop" in run_calls[0]["prompt"]
    assert "master" not in run_calls[0]["prompt"]


# ---------------------------------------------------------------------------
# Path sanitization
# ---------------------------------------------------------------------------

def test_sanitize_paths_replaces_absolute_with_relative():
    from autoswe.harness.prompts import _sanitize_paths

    result = _sanitize_paths(
        "Edit `/home/user/repo/autoswe/cli.py` to add the flag.",
        "/home/user/repo",
    )
    assert "autoswe/cli.py" in result
    assert "/home/user/repo" not in result


def test_sanitize_paths_no_false_positives():
    from autoswe.harness.prompts import _sanitize_paths

    result = _sanitize_paths(
        "/home/user/repo-extra/file.txt",
        "/home/user/repo",
    )
    assert result == "/home/user/repo-extra/file.txt"


def test_run_plan_sanitizes_absolute_paths_in_prompt(tmp_path, mock_gh_post_comment):
    """Absolute paths in issue body should be replaced with relative paths."""
    run_calls = []

    def fake_run(prompt, **kwargs):
        run_calls.append(prompt)
        return _r("<AUTOSWE_PLAN>\nPlan\n</AUTOSWE_PLAN>")

    task = make_task()
    task["body"] = f"Edit `{tmp_path}/autoswe/cli.py` to add a flag."

    with _patch_worktree(tmp_path):
        with FETCH_COMMENTS_PATCH:
            with patch("autoswe.harness.runner.run", side_effect=fake_run):
                from autoswe.harness.planner import run_plan
                run_plan(task, {}, {"GITHUB_TOKEN": "tok"})

    assert str(tmp_path) not in run_calls[0]
    assert "autoswe/cli.py" in run_calls[0]


# ---------------------------------------------------------------------------
# mode="plan" — regression tests (Phase 3)
# ---------------------------------------------------------------------------

def test_run_plan_uses_mode_plan_regression(tmp_path, mock_gh_post_comment):
    """Plan phase should use mode='plan' (backend translates to permission_mode='plan')."""
    run_calls = []

    def fake_run(prompt, **kwargs):
        run_calls.append(kwargs)
        return _r("<AUTOSWE_PLAN>\nPlan\n</AUTOSWE_PLAN>")

    task = make_task()

    with _patch_worktree(tmp_path):
        with FETCH_COMMENTS_PATCH:
            with patch("autoswe.harness.runner.run", side_effect=fake_run):
                from autoswe.harness.planner import run_plan
                run_plan(task, {}, {"GITHUB_TOKEN": "tok"})

    assert run_calls[0]["mode"] == "plan"


def test_resume_plan_uses_mode_plan_regression(tmp_path, mock_gh_post_comment):
    """Resume plan should also use mode='plan'."""
    run_calls = []

    def fake_run(prompt, **kwargs):
        run_calls.append(kwargs)
        return _r("<AUTOSWE_PLAN>\nPlan\n</AUTOSWE_PLAN>")

    task = make_task(session_id="sess-existing")

    with _patch_worktree(tmp_path):
        with patch("autoswe.harness.runner.run", side_effect=fake_run):
            from autoswe.harness.planner import resume_plan
            resume_plan(task, "Use approach A.", {}, {"GITHUB_TOKEN": "tok"})

    assert run_calls[0]["mode"] == "plan"


# ---------------------------------------------------------------------------
# Plan file extraction — fallback chain
# ---------------------------------------------------------------------------

def test_find_latest_plan_file_none_when_dir_missing():
    """_find_latest_plan_file returns None when ~/.claude/plans/ doesn't exist."""
    from unittest.mock import MagicMock
    mock_dir = MagicMock()
    mock_dir.exists.return_value = False

    with patch("autoswe.harness.planner._get_plans_dir", return_value=mock_dir):
        from autoswe.harness.planner import _find_latest_plan_file
        result = _find_latest_plan_file()
    assert result is None


def test_find_latest_plan_file_none_when_dir_empty():
    """_find_latest_plan_file returns None when ~/.claude/plans/ has no .md files."""
    from unittest.mock import MagicMock
    mock_dir = MagicMock()
    mock_dir.exists.return_value = True
    mock_dir.glob.return_value = []

    with patch("autoswe.harness.planner._get_plans_dir", return_value=mock_dir):
        from autoswe.harness.planner import _find_latest_plan_file
        result = _find_latest_plan_file()
    assert result is None


def test_run_plan_plan_file_takes_precedence(tmp_path, mock_gh_post_comment):
    """When both plan file and <AUTOSWE_PLAN> tags exist, plan file content wins."""
    plan_file = tmp_path / "native-plan.md"
    plan_file.write_text("# Native Plan\n\nStep 1: from plan file")

    task = make_task()
    claude_text = "<AUTOSWE_PLAN>\nStep from XML tags\n</AUTOSWE_PLAN>"

    with _patch_worktree(tmp_path):
        with FETCH_COMMENTS_PATCH:
            with patch("autoswe.harness.planner._find_latest_plan_file", return_value=plan_file):
                with patch("autoswe.harness.runner.run", return_value=_r(claude_text)):
                    from autoswe.harness.planner import run_plan
                    result = run_plan(task, {}, {"GITHUB_TOKEN": "tok"})

    assert result.done_content == "PLAN_READY"
    assert "from plan file" in mock_gh_post_comment.posted[0]["body"]
    assert "from XML tags" not in mock_gh_post_comment.posted[0]["body"]


def test_run_plan_no_plan_file_falls_back_to_tags(tmp_path, mock_gh_post_comment):
    """When no plan file exists, falls back to <AUTOSWE_PLAN> XML tag parsing."""
    task = make_task()
    claude_text = "<AUTOSWE_PLAN>\nStep from XML tags\n</AUTOSWE_PLAN>"

    with _patch_worktree(tmp_path):
        with FETCH_COMMENTS_PATCH:
            with patch("autoswe.harness.planner._find_latest_plan_file", return_value=None):
                with patch("autoswe.harness.runner.run", return_value=_r(claude_text)):
                    from autoswe.harness.planner import run_plan
                    result = run_plan(task, {}, {"GITHUB_TOKEN": "tok"})

    assert result.done_content == "PLAN_READY"
    assert "from XML tags" in mock_gh_post_comment.posted[0]["body"]


def test_run_plan_no_plan_file_no_tags_falls_back_to_questions(tmp_path, mock_gh_post_comment):
    """When no plan file and no <AUTOSWE_PLAN>, falls back to <AUTOSWE_QUESTIONS>."""
    task = make_task()
    claude_text = "<AUTOSWE_QUESTIONS>\n1. Which approach?\n</AUTOSWE_QUESTIONS>"

    with _patch_worktree(tmp_path):
        with FETCH_COMMENTS_PATCH:
            with patch("autoswe.harness.planner._find_latest_plan_file", return_value=None):
                with patch("autoswe.harness.runner.run", return_value=_r(claude_text)):
                    from autoswe.harness.planner import run_plan
                    result = run_plan(task, {}, {"GITHUB_TOKEN": "tok"})

    assert result.done_content.startswith("WAITING:")
    assert "Which approach" in mock_gh_post_comment.posted[0]["body"]


def test_run_plan_no_plan_file_no_tags_falls_back_to_raw(tmp_path, mock_gh_post_comment):
    """When nothing matches, falls back to raw text as 'Claude's response'."""
    task = make_task()
    claude_text = "Here is my analysis of the code."

    with _patch_worktree(tmp_path):
        with FETCH_COMMENTS_PATCH:
            with patch("autoswe.harness.planner._find_latest_plan_file", return_value=None):
                with patch("autoswe.harness.runner.run", return_value=_r(claude_text)):
                    from autoswe.harness.planner import run_plan
                    result = run_plan(task, {}, {"GITHUB_TOKEN": "tok"})

    assert result.done_content.startswith("WAITING:")
    assert "Claude's response" in mock_gh_post_comment.posted[0]["body"]
    assert "Here is my analysis" in mock_gh_post_comment.posted[0]["body"]


def test_resume_plan_plan_file_priority(tmp_path, mock_gh_post_comment):
    """resume_plan also uses the plan file -> tags -> raw priority chain."""
    plan_file = tmp_path / "resumed-plan.md"
    plan_file.write_text("# Updated Plan\n\nStep 1: after user answered")

    task = make_task(session_id="sess-existing")
    claude_text = "Thanks for the answer. Here's the updated plan."

    with _patch_worktree(tmp_path):
        with patch("autoswe.harness.planner._find_latest_plan_file", return_value=plan_file):
            with patch("autoswe.harness.runner.run", return_value=_r(claude_text, "sess-new")):
                from autoswe.harness.planner import resume_plan
                result = resume_plan(task, "Use approach A.", {}, {"GITHUB_TOKEN": "tok"})

    assert result.done_content == "PLAN_READY"
    assert "after user answered" in mock_gh_post_comment.posted[0]["body"]
    assert "Thanks for the answer" not in mock_gh_post_comment.posted[0]["body"]


def test_extract_plan_output_unit():
    """Direct unit test for _extract_plan_output without runner/worktree."""
    from autoswe.harness.planner import _extract_plan_output

    # Fallback: empty text -> WAITING with "(no response)"
    with patch("autoswe.harness.planner._find_latest_plan_file", return_value=None):
        comment, done = _extract_plan_output("")
        assert done == "WAITING: see comment"
        assert "(no response)" in comment

    # Fallback: raw text -> WAITING
    with patch("autoswe.harness.planner._find_latest_plan_file", return_value=None):
        comment, done = _extract_plan_output("Some analysis.")
        assert done == "WAITING: see comment"
        assert "Some analysis." in comment

    # XML plan tags work without plan file
    with patch("autoswe.harness.planner._find_latest_plan_file", return_value=None):
        comment, done = _extract_plan_output("<AUTOSWE_PLAN>\nDo X\n</AUTOSWE_PLAN>")
        assert done == "PLAN_READY"
        assert "Do X" in comment

    # XML questions work without plan file
    with patch("autoswe.harness.planner._find_latest_plan_file", return_value=None):
        comment, done = _extract_plan_output("<AUTOSWE_QUESTIONS>\n1. Q?\n</AUTOSWE_QUESTIONS>")
        assert done == "WAITING: questions"
        assert "Q?" in comment


# ---------------------------------------------------------------------------
# HandlerResult carries cost and duration
# ---------------------------------------------------------------------------

def test_run_plan_returns_cost_and_duration(tmp_path, mock_gh_post_comment):
    """run_plan should propagate cost_usd and duration_seconds from RunResult."""
    claude_text = "<AUTOSWE_PLAN>\nStep 1\n</AUTOSWE_PLAN>"
    task = make_task()

    with _patch_worktree(tmp_path):
        with FETCH_COMMENTS_PATCH:
            with patch("autoswe.harness.runner.run",
                       return_value=RunResult(claude_text, "sess", "success", cost_usd=0.42, duration_seconds=30.5)):
                from autoswe.harness.planner import run_plan
                result = run_plan(task, {}, {"GITHUB_TOKEN": "tok"})

    assert result.done_content == "PLAN_READY"
    assert result.cost_usd == 0.42
    assert result.duration_seconds == 30.5


def test_resume_plan_returns_cost_and_duration(tmp_path, mock_gh_post_comment):
    """resume_plan should propagate cost_usd and duration_seconds from RunResult."""
    claude_text = "<AUTOSWE_PLAN>\nStep 1\n</AUTOSWE_PLAN>"
    task = make_task(session_id="sess-existing")

    with _patch_worktree(tmp_path):
        with patch("autoswe.harness.runner.run",
                   return_value=RunResult(claude_text, "sess-new", "success", cost_usd=0.10, duration_seconds=15.0)):
            from autoswe.harness.planner import resume_plan
            result = resume_plan(task, "Answer.", {}, {"GITHUB_TOKEN": "tok"})

    assert result.done_content == "PLAN_READY"
    assert result.cost_usd == 0.10
    assert result.duration_seconds == 15.0


# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# AskUserQuestion support


def test_run_plan_ask_user_question_returns_waiting(tmp_path, mock_gh_post_comment):
    """When AskUserQuestion is called, run_plan should return WAITING: questions."""
    task = make_task()
    state = {}

    def fake_callback(name, inp, ctx):
        from claude_agent_sdk import PermissionResultAllow, PermissionResultDeny
        if name == "AskUserQuestion":
            state["asked_question_md"] = "## Questions"
            return PermissionResultDeny(message="posted")
        return PermissionResultAllow(updated_input=inp)

    def fake_run(prompt, **kwargs):
        state["asked_question_md"] = "## Questions"
        return _r("", "sess-1", "success")

    with _patch_worktree(tmp_path):
        with FETCH_COMMENTS_PATCH:
            with patch("autoswe.harness.runner.run", side_effect=fake_run):
                with patch("autoswe.harness.planner.make_can_use_tool", return_value=fake_callback):
                    from autoswe.harness.planner import run_plan
                    result = run_plan(task, {}, {"GITHUB_TOKEN": "tok"})

    assert result.done_content.startswith("WAITING:")


def test_run_plan_records_last_phase_plan(tmp_path, mock_gh_post_comment):
    """run_plan should set last_phase=plan on the task."""
    task = make_task()

    with _patch_worktree(tmp_path):
        with FETCH_COMMENTS_PATCH:
            with patch("autoswe.harness.runner.run",
                       return_value=_r("<AUTOSWE_PLAN>" + chr(10) + "Plan" + chr(10) + "</AUTOSWE_PLAN>")):
                from autoswe.harness.planner import run_plan
                run_plan(task, {}, {"GITHUB_TOKEN": "tok"})

    assert task.get("last_phase") == "plan"


def test_resume_plan_records_last_phase_plan(tmp_path, mock_gh_post_comment):
    """resume_plan should set last_phase=plan on the task."""
    task = make_task(session_id="sess-existing")

    with _patch_worktree(tmp_path):
        with patch("autoswe.harness.runner.run",
                   return_value=_r("<AUTOSWE_PLAN>" + chr(10) + "Plan" + chr(10) + "</AUTOSWE_PLAN>")):
            from autoswe.harness.planner import resume_plan
            resume_plan(task, "Answer.", {}, {"GITHUB_TOKEN": "tok"})

    assert task.get("last_phase") == "plan"


def test_run_plan_ask_user_question_in_mode(tmp_path, mock_gh_post_comment):
    """AskUserQuestion should be included in mode='plan' tool set (planner can ask questions)."""
    run_calls = []

    def fake_run(prompt, **kwargs):
        run_calls.append(kwargs)
        return _r("<AUTOSWE_PLAN>" + chr(10) + "Plan" + chr(10) + "</AUTOSWE_PLAN>")

    task = make_task()

    with _patch_worktree(tmp_path):
        with FETCH_COMMENTS_PATCH:
            with patch("autoswe.harness.runner.run", side_effect=fake_run):
                from autoswe.harness.planner import run_plan
                run_plan(task, {}, {"GITHUB_TOKEN": "tok"})

    assert run_calls[0]["mode"] == "plan"
    from autoswe.harness.backends.claude_code import _MODE_CONFIG
    _perm, tools, _disallowed = _MODE_CONFIG["plan"]
    assert "AskUserQuestion" in tools


def test_run_plan_mode_excludes_exit_plan_mode(tmp_path, mock_gh_post_comment):
    """mode='plan' should translate to ExitPlanMode in disallowed_tools (via backend)."""
    run_calls = []

    def fake_run(prompt, **kwargs):
        run_calls.append(kwargs)
        return _r("<AUTOSWE_PLAN>" + chr(10) + "Plan" + chr(10) + "</AUTOSWE_PLAN>")

    task = make_task()

    with _patch_worktree(tmp_path):
        with FETCH_COMMENTS_PATCH:
            with patch("autoswe.harness.runner.run", side_effect=fake_run):
                from autoswe.harness.planner import run_plan
                run_plan(task, {}, {"GITHUB_TOKEN": "tok"})

    assert run_calls[0]["mode"] == "plan"
    # Verify the backend maps mode="plan" to disallow ExitPlanMode
    from autoswe.harness.backends.claude_code import _MODE_CONFIG
    _perm, _tools, disallowed = _MODE_CONFIG["plan"]
    assert "ExitPlanMode" in disallowed


# ---------------------------------------------------------------------------
# Guidance in plan prompt


def test_build_plan_prompt_includes_guidance():
    """build_plan_prompt should include guidance text in the prompt."""
    from autoswe.harness.prompts import build_plan_prompt

    task = {
        "owner": "o",
        "repo": "r",
        "issue_number": 1,
        "title": "Test",
        "body": "Some issue",
        "base_branch": "main",
    }

    prompt = build_plan_prompt(
        task, repo_root="/tmp", guidance="use a functional approach",
        comments=[],
    )
    assert "Guidance from the issue author:" in prompt
    assert "use a functional approach" in prompt


def test_build_plan_prompt_no_guidance_empty_block():
    """build_plan_prompt with no guidance should produce an empty GUIDANCE_BLOCK."""
    from autoswe.harness.prompts import build_plan_prompt

    task = {
        "owner": "o",
        "repo": "r",
        "issue_number": 1,
        "title": "Test",
        "body": "Some issue",
        "base_branch": "main",
    }

    prompt = build_plan_prompt(task, repo_root="/tmp", guidance=None, comments=[])
    # The guidance block should be empty — no "Guidance from" text
    assert "Guidance from the issue author" not in prompt


def test_run_plan_passes_guidance_to_prompt(tmp_path, mock_gh_post_comment):
    """run_plan should forward guidance to build_plan_prompt, which includes it in the prompt."""
    run_calls = []

    def fake_run(prompt, **kwargs):
        run_calls.append({"prompt": prompt})
        return _r("<AUTOSWE_PLAN>\nPlan\n</AUTOSWE_PLAN>")

    task = make_task()

    with _patch_worktree(tmp_path):
        with FETCH_COMMENTS_PATCH:
            with patch("autoswe.harness.runner.run", side_effect=fake_run):
                from autoswe.harness.planner import run_plan
                run_plan(task, {}, {"GITHUB_TOKEN": "tok"}, guidance="use a functional approach")

    assert len(run_calls) == 1
    assert "Guidance from the issue author:" in run_calls[0]["prompt"]
    assert "use a functional approach" in run_calls[0]["prompt"]


def test_run_plan_no_guidance_empty_block(tmp_path, mock_gh_post_comment):
    """run_plan without guidance should not include guidance in prompt."""
    run_calls = []

    def fake_run(prompt, **kwargs):
        run_calls.append({"prompt": prompt})
        return _r("<AUTOSWE_PLAN>\nPlan\n</AUTOSWE_PLAN>")

    task = make_task()

    with _patch_worktree(tmp_path):
        with FETCH_COMMENTS_PATCH:
            with patch("autoswe.harness.runner.run", side_effect=fake_run):
                from autoswe.harness.planner import run_plan
                run_plan(task, {}, {"GITHUB_TOKEN": "tok"})

    assert len(run_calls) == 1
    assert "Guidance from the issue author" not in run_calls[0]["prompt"]


# ---------------------------------------------------------------------------
# Plan file path capture from SDK tool calls

def test_run_plan_uses_plan_file_path_from_runner_result(tmp_path, mock_gh_post_comment):
    """When RunResult includes plan_file_path, planner uses it instead of filesystem scan."""
    plan_file = tmp_path / "captured-plan.md"
    plan_file.write_text("# Captured Plan\n\nStep 1: from captured path")
    task = make_task()

    captured_runner_result = RunResult(
        text="",
        session_id="sess-1",
        subtype="success",
        plan_file_path=str(plan_file),
    )

    with _patch_worktree(tmp_path):
        with FETCH_COMMENTS_PATCH:
            # _find_latest_plan_file returns a DIFFERENT file — but the
            # captured plan_file_path from the runner should take precedence
            decoy_file = tmp_path / "decoy-plan.md"
            decoy_file.write_text("# Decoy\n\nNot this one")
            with patch("autoswe.harness.planner._find_latest_plan_file", return_value=decoy_file):
                with patch("autoswe.harness.runner.run", return_value=captured_runner_result):
                    from autoswe.harness.planner import run_plan
                    result = run_plan(task, {}, {"GITHUB_TOKEN": "tok"})

    assert result.done_content == "PLAN_READY"
    assert "from captured path" in mock_gh_post_comment.posted[0]["body"]
    assert "Decoy" not in mock_gh_post_comment.posted[0]["body"]
    assert task.get("plan_file_path") == str(plan_file)


def test_run_plan_falls_back_to_filesystem_when_no_plan_file_path(tmp_path, mock_gh_post_comment):
    """When RunResult has no plan_file_path, planner falls back to _find_latest_plan_file."""
    filesystem_file = tmp_path / "fallback-plan.md"
    filesystem_file.write_text("# Fallback Plan\n\nFound by filesystem scan")
    task = make_task()

    captured_runner_result = RunResult(
        text="",
        session_id="sess-1",
        subtype="success",
        plan_file_path=None,  # No captured path
    )

    with _patch_worktree(tmp_path):
        with FETCH_COMMENTS_PATCH:
            with patch("autoswe.harness.planner._find_latest_plan_file", return_value=filesystem_file):
                with patch("autoswe.harness.runner.run", return_value=captured_runner_result):
                    from autoswe.harness.planner import run_plan
                    result = run_plan(task, {}, {"GITHUB_TOKEN": "tok"})

    assert result.done_content == "PLAN_READY"
    assert "Found by filesystem scan" in mock_gh_post_comment.posted[0]["body"]


def test_run_plan_falls_back_to_tags_when_no_plan_file(tmp_path, mock_gh_post_comment):
    """When both captured path and filesystem scan fail, falls back to XML tags."""
    task = make_task()
    claude_text = "<AUTOSWE_PLAN>\nFallback to XML tags\n</AUTOSWE_PLAN>"

    captured_runner_result = RunResult(
        text=claude_text,
        session_id="sess-1",
        subtype="success",
        plan_file_path=None,
    )

    with _patch_worktree(tmp_path):
        with FETCH_COMMENTS_PATCH:
            with patch("autoswe.harness.planner._find_latest_plan_file", return_value=None):
                with patch("autoswe.harness.runner.run", return_value=captured_runner_result):
                    from autoswe.harness.planner import run_plan
                    result = run_plan(task, {}, {"GITHUB_TOKEN": "tok"})

    assert result.done_content == "PLAN_READY"
    assert "Fallback to XML tags" in mock_gh_post_comment.posted[0]["body"]


def test_resume_plan_uses_plan_file_path_from_runner_result(tmp_path, mock_gh_post_comment):
    """resume_plan also uses captured plan_file_path from RunResult."""
    plan_file = tmp_path / "resumed-captured-plan.md"
    plan_file.write_text("# Resumed Plan\n\nStep 1: after user reply")
    task = make_task(session_id="sess-existing")

    captured_runner_result = RunResult(
        text="",
        session_id="sess-new",
        subtype="success",
        plan_file_path=str(plan_file),
    )

    with _patch_worktree(tmp_path):
        with patch("autoswe.harness.planner._find_latest_plan_file", return_value=None):
            with patch("autoswe.harness.runner.run", return_value=captured_runner_result):
                from autoswe.harness.planner import resume_plan
                result = resume_plan(task, "Use approach A.", {}, {"GITHUB_TOKEN": "tok"})

    assert result.done_content == "PLAN_READY"
    assert "after user reply" in mock_gh_post_comment.posted[0]["body"]


def test_extract_plan_output_with_plan_file_parameter(tmp_path):
    """_extract_plan_output uses the provided plan_file parameter first."""
    from autoswe.harness.planner import _extract_plan_output

    # When plan_file is provided and valid, use it
    plan_file = tmp_path / "test-captured-plan.md"
    plan_file.write_text("# Test Plan\n\nSteps here.")

    with patch("autoswe.harness.planner._find_latest_plan_file") as mock_find:
        comment, done = _extract_plan_output("some text", plan_file=plan_file)
        assert done == "PLAN_READY"
        assert "Steps here" in comment
        # _find_latest_plan_file should NOT have been called
        mock_find.assert_not_called()


def test_extract_plan_output_falls_back_when_plan_file_none(tmp_path):
    """_extract_plan_output falls back to _find_latest_plan_file when plan_file=None."""
    from autoswe.harness.planner import _extract_plan_output

    fallback_file = tmp_path / "fallback-plan.md"
    fallback_file.write_text("# Fallback\n\nFallback content.")

    with patch("autoswe.harness.planner._find_latest_plan_file", return_value=fallback_file):
        comment, done = _extract_plan_output("text", plan_file=None)
        assert done == "PLAN_READY"
        assert "Fallback content" in comment


def test_extract_plan_output_falls_back_when_plan_file_not_found(tmp_path):
    """_extract_plan_output falls back to _find_latest_plan_file when plan_file doesn't exist."""
    from autoswe.harness.planner import _extract_plan_output

    missing_file = tmp_path / "does-not-exist.md"
    fallback_file = tmp_path / "fallback-plan.md"
    fallback_file.write_text("# Fallback\n\nFallback.")

    with patch("autoswe.harness.planner._find_latest_plan_file", return_value=fallback_file):
        comment, done = _extract_plan_output("text", plan_file=missing_file)
        assert done == "PLAN_READY"
        assert "Fallback" in comment


# ---------------------------------------------------------------------------
# push_new=False — plan phase must not create remote branches

def test_run_plan_does_not_push_new_branch(tmp_path, mock_gh_post_comment):
    """run_plan must pass push_new=False to create_worktree so the remote branch
    is NOT created during the read-only plan phase."""
    create_worktree_calls = []

    def fake_create_worktree(*args, **kwargs):
        create_worktree_calls.append(kwargs)
        return tmp_path

    def fake_run(prompt, **kwargs):
        return _r("<AUTOSWE_PLAN>\nPlan\n</AUTOSWE_PLAN>")

    task = make_task()

    with patch("autoswe.harness.planner.create_worktree", side_effect=fake_create_worktree):
        with patch("autoswe.harness.planner._find_latest_plan_file", return_value=None):
            with FETCH_COMMENTS_PATCH:
                with patch("autoswe.harness.runner.run", side_effect=fake_run):
                    from autoswe.harness.planner import run_plan
                    run_plan(task, {}, {"GITHUB_TOKEN": "tok"})

    assert len(create_worktree_calls) == 1
    assert create_worktree_calls[0].get("push_new") is False, \
        "run_plan must use push_new=False to avoid creating remote branches during planning"


def test_resume_plan_does_not_push_new_branch(tmp_path, mock_gh_post_comment):
    """resume_plan must pass push_new=False to create_worktree so the remote branch
    is NOT created during the read-only plan resume phase."""
    create_worktree_calls = []

    def fake_create_worktree(*args, **kwargs):
        create_worktree_calls.append(kwargs)
        return tmp_path

    def fake_run(prompt, **kwargs):
        return _r("<AUTOSWE_PLAN>\nPlan\n</AUTOSWE_PLAN>")

    task = make_task(session_id="sess-existing")

    with patch("autoswe.harness.planner.create_worktree", side_effect=fake_create_worktree):
        with patch("autoswe.harness.planner._find_latest_plan_file", return_value=None):
            with patch("autoswe.harness.runner.run", side_effect=fake_run):
                from autoswe.harness.planner import resume_plan
                resume_plan(task, "Use approach A.", {}, {"GITHUB_TOKEN": "tok"})

    assert len(create_worktree_calls) == 1
    assert create_worktree_calls[0].get("push_new") is False, \
        "resume_plan must use push_new=False to avoid creating remote branches during planning"


# ---------------------------------------------------------------------------
# Fix 1: resume_plan disallows ExitPlanMode (via mode="plan")

def test_resume_plan_disallows_exit_plan_mode(tmp_path, mock_gh_post_comment):
    """resume_plan should use mode='plan' which includes ExitPlanMode in disallowed_tools (via backend)."""
    run_calls = []

    def fake_run(prompt, **kwargs):
        run_calls.append(kwargs)
        return _r("<AUTOSWE_PLAN>\nPlan\n</AUTOSWE_PLAN>")

    task = make_task(session_id="sess-existing")

    with _patch_worktree(tmp_path):
        with patch("autoswe.harness.runner.run", side_effect=fake_run):
            from autoswe.harness.planner import resume_plan
            resume_plan(task, "Answer.", {}, {"GITHUB_TOKEN": "tool"})

    assert run_calls[0]["mode"] == "plan"
    from autoswe.harness.backends.claude_code import _MODE_CONFIG
    _perm, _tools, disallowed = _MODE_CONFIG["plan"]
    assert "ExitPlanMode" in disallowed


# ---------------------------------------------------------------------------
# Fix 3: MCP post_plan / post_question detection in RunResult


def test_run_plan_returns_plan_ready_on_post_plan_tool_use(tmp_path, mock_gh_post_comment):
    """When RunResult has plan_posted=True, run_plan should return PLAN_READY
    even without plan file or XML tags."""
    task = make_task()

    with _patch_worktree(tmp_path):
        with FETCH_COMMENTS_PATCH:
            with patch("autoswe.harness.runner.run",
                       return_value=RunResult("", "sess-1", "success", plan_posted=True)):
                from autoswe.harness.planner import run_plan
                result = run_plan(task, {}, {"GITHUB_TOKEN": "tok"})

    assert result.done_content == "PLAN_READY"


def test_run_plan_returns_waiting_on_post_question_tool_use(tmp_path, mock_gh_post_comment):
    """When RunResult has question_posted=True, run_plan should return WAITING: questions."""
    task = make_task()

    with _patch_worktree(tmp_path):
        with FETCH_COMMENTS_PATCH:
            with patch("autoswe.harness.runner.run",
                       return_value=RunResult("", "sess-1", "success", question_posted=True)):
                from autoswe.harness.planner import run_plan
                result = run_plan(task, {}, {"GITHUB_TOKEN": "tok"})

    assert result.done_content.startswith("WAITING:")
    assert "questions" in result.done_content


def test_resume_plan_returns_plan_ready_on_post_plan_tool_use(tmp_path, mock_gh_post_comment):
    """When RunResult has plan_posted=True, resume_plan should return PLAN_READY."""
    task = make_task(session_id="sess-existing")

    with _patch_worktree(tmp_path):
        with patch("autoswe.harness.runner.run",
                   return_value=RunResult("", "sess-new", "success", plan_posted=True)):
            from autoswe.harness.planner import resume_plan
            result = resume_plan(task, "Answer.", {}, {"GITHUB_TOKEN": "tok"})

    assert result.done_content == "PLAN_READY"


def test_resume_plan_returns_waiting_on_post_question_tool_use(tmp_path, mock_gh_post_comment):
    """When RunResult has question_posted=True, resume_plan should return WAITING: questions."""
    task = make_task(session_id="sess-existing")

    with _patch_worktree(tmp_path):
        with patch("autoswe.harness.runner.run",
                   return_value=RunResult("", "sess-new", "success", question_posted=True)):
            from autoswe.harness.planner import resume_plan
            result = resume_plan(task, "Answer.", {}, {"GITHUB_TOKEN": "tok"})

    assert result.done_content.startswith("WAITING:")
    assert "questions" in result.done_content


def test_run_plan_question_posted_beats_plan_posted(tmp_path, mock_gh_post_comment):
    """When both flags are True, question_posted takes priority (WAITING over PLAN_READY)."""
    task = make_task()

    with _patch_worktree(tmp_path):
        with FETCH_COMMENTS_PATCH:
            with patch("autoswe.harness.runner.run",
                       return_value=RunResult("", "sess-1", "success", plan_posted=True, question_posted=True)):
                from autoswe.harness.planner import run_plan
                result = run_plan(task, {}, {"GITHUB_TOKEN": "tok"})

    assert result.done_content.startswith("WAITING:")
    assert "questions" in result.done_content

