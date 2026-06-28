"""Tests for MCP comment server integration in planner and coder."""

import sys
from unittest.mock import patch

from autoswe.harness.runner import RunResult


def _r(text, session_id="sess", subtype="success"):
    return RunResult(text, session_id, subtype)


def make_task(comment_id=12345, token="ghp_fake", session_id=None):
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
        "_comment_id": comment_id,
    }


FETCH_COMMENTS_PATCH = patch("autoswe.tracking.api._fetch_comments", return_value=[])


# ---------------------------------------------------------------------------
# _build_mcp_servers helper
# ---------------------------------------------------------------------------

def test_build_mcp_servers_returns_config_with_comment_id():
    """_build_mcp_servers should return a config dict when comment_id is set."""
    from autoswe.harness.mcp_config import build_mcp_comment_server as _build_mcp_servers

    task = make_task(comment_id=12345)
    repo_cfg = {"provider": "github"}

    result = _build_mcp_servers(task, repo_cfg)

    assert result is not None
    assert "autoswe_comment" in result
    server = result["autoswe_comment"]
    assert server["command"] == sys.executable
    assert "-m" in server["args"]
    assert "mcp_servers.autoswe_comment_server" in server["args"]
    assert server["env"]["AUTOSWE_COMMENT_ID"] == "12345"
    assert server["env"]["AUTOSWE_PROVIDER"] == "github"
    assert server["env"]["AUTOSWE_OWNER"] == "o"
    assert server["env"]["AUTOSWE_REPO"] == "r"
    assert server["env"]["AUTOSWE_ISSUE_NUMBER"] == "1"
    assert server["env"]["AUTOSWE_TOKEN"] == "ghp_fake"


def test_build_mcp_servers_returns_none_without_comment_id():
    """_build_mcp_servers should return None when no comment_id is set."""
    from autoswe.harness.mcp_config import build_mcp_comment_server as _build_mcp_servers

    task = make_task(comment_id=None)
    # Remove the key entirely to simulate no sticky comment
    del task["_comment_id"]
    repo_cfg = {"provider": "github"}

    result = _build_mcp_servers(task, repo_cfg)
    assert result is None


def test_build_mcp_servers_azure_provider():
    """_build_mcp_servers should pass azure provider correctly."""
    from autoswe.harness.mcp_config import build_mcp_comment_server as _build_mcp_servers

    task = make_task(comment_id=99)
    repo_cfg = {"provider": "azure"}

    result = _build_mcp_servers(task, repo_cfg)
    assert result["autoswe_comment"]["env"]["AUTOSWE_PROVIDER"] == "azure"


# ---------------------------------------------------------------------------
# run_plan passes MCP servers to runner
# ---------------------------------------------------------------------------

def test_run_plan_passes_mcp_servers(tmp_path, mock_gh_post_comment):
    """run_plan should pass mcp_servers to runner.run when comment_id is set."""
    run_calls = []

    def fake_run(prompt, **kwargs):
        run_calls.append(kwargs)
        return _r("<AUTOSWE_PLAN>\nPlan\n</AUTOSWE_PLAN>")

    task = make_task(comment_id=42)

    with patch("autoswe.harness.planner.create_worktree", return_value=tmp_path):
        with patch("autoswe.harness.planner._find_latest_plan_file", return_value=None):
            with FETCH_COMMENTS_PATCH:
                with patch("autoswe.harness.runner.run", side_effect=fake_run):
                    from autoswe.harness.planner import run_plan
                    run_plan(task, {}, {"GITHUB_TOKEN": "tok"})

    assert "mcp_servers" in run_calls[0]
    assert run_calls[0]["mcp_servers"] is not None
    assert "autoswe_comment" in run_calls[0]["mcp_servers"]


def test_run_plan_no_mcp_servers_without_comment_id(tmp_path, mock_gh_post_comment):
    """run_plan should pass None for mcp_servers when no comment_id."""
    run_calls = []

    def fake_run(prompt, **kwargs):
        run_calls.append(kwargs)
        return _r("<AUTOSWE_PLAN>\nPlan\n</AUTOSWE_PLAN>")

    task = make_task(comment_id=None)
    del task["_comment_id"]

    with patch("autoswe.harness.planner.create_worktree", return_value=tmp_path):
        with patch("autoswe.harness.planner._find_latest_plan_file", return_value=None):
            with FETCH_COMMENTS_PATCH:
                with patch("autoswe.harness.runner.run", side_effect=fake_run):
                    from autoswe.harness.planner import run_plan
                    run_plan(task, {}, {"GITHUB_TOKEN": "tok"})

    assert run_calls[0]["mcp_servers"] is None


# ---------------------------------------------------------------------------
# Coder MCP integration
# ---------------------------------------------------------------------------

def test_coder_build_mcp_servers():
    """coder._build_mcp_servers should return config with comment_id."""
    from autoswe.harness.mcp_config import build_mcp_comment_server as _build_mcp_servers

    task = {
        "owner": "myorg",
        "repo": "myrepo",
        "issue_number": 7,
        "_token": "ghp_secret",
        "_comment_id": 555,
    }
    repo_cfg = {"provider": "github"}

    result = _build_mcp_servers(task, repo_cfg)

    assert result is not None
    server = result["autoswe_comment"]
    assert server["env"]["AUTOSWE_COMMENT_ID"] == "555"
    assert server["env"]["AUTOSWE_OWNER"] == "myorg"
    assert server["env"]["AUTOSWE_ISSUE_NUMBER"] == "7"


def test_coder_build_mcp_servers_none_without_comment_id():
    """coder._build_mcp_servers returns None without comment_id."""
    from autoswe.harness.mcp_config import build_mcp_comment_server as _build_mcp_servers

    task = {"owner": "o", "repo": "r", "issue_number": 1, "_token": "t"}
    result = _build_mcp_servers(task, {})
    assert result is None


def test_run_fix_passes_mcp_servers(tmp_path):
    """run_fix should pass mcp_servers to runner when comment_id is set."""
    run_calls = []

    def fake_run(prompt, **kwargs):
        run_calls.append(kwargs)
        return _r("Done.", "sess")

    task = make_task(comment_id=77)
    FAKE_COMMIT = {"committed": True, "commit_sha": "abc", "branch": "autoswe/issue-1"}

    with patch("autoswe.harness.coder.create_worktree", return_value=tmp_path):
        with FETCH_COMMENTS_PATCH:
            with patch("autoswe.harness.runner.run", side_effect=fake_run):
                with patch("autoswe.harness.coder.commit_and_push", return_value=FAKE_COMMIT):
                    from autoswe.harness.coder import run_fix
                    run_fix(task, cfg={})

    assert run_calls[0]["mcp_servers"] is not None
    assert "autoswe_comment" in run_calls[0]["mcp_servers"]


# ---------------------------------------------------------------------------
# Deprecated regex fallback warning
# ---------------------------------------------------------------------------

def test_extract_plan_output_logs_deprecation_for_plan_tag(tmp_path, mock_gh_post_comment):
    """Using <AUTOSWE_PLAN> tags should log a deprecation warning."""
    from autoswe.harness.planner import _extract_plan_output

    with patch("autoswe.harness.planner._find_latest_plan_file", return_value=None):
        with patch("autoswe.harness.planner.dbg.warning") as mock_warn:
            _extract_plan_output("<AUTOSWE_PLAN>\nX\n</AUTOSWE_PLAN>")

    assert mock_warn.called
    assert "deprecated" in mock_warn.call_args[0][0].lower()
    assert "post_plan" in mock_warn.call_args[0][0]


def test_extract_plan_output_logs_deprecation_for_questions_tag(tmp_path, mock_gh_post_comment):
    """Using <AUTOSWE_QUESTIONS> tags should log a deprecation warning."""
    from autoswe.harness.planner import _extract_plan_output

    with patch("autoswe.harness.planner._find_latest_plan_file", return_value=None):
        with patch("autoswe.harness.planner.dbg.warning") as mock_warn:
            _extract_plan_output("<AUTOSWE_QUESTIONS>\n1. Q?\n</AUTOSWE_QUESTIONS>")

    assert mock_warn.called
    assert "deprecated" in mock_warn.call_args[0][0].lower()
    assert "post_question" in mock_warn.call_args[0][0]


def test_extract_plan_output_no_deprecation_for_plan_file():
    """Plan file path should NOT trigger deprecation warning."""
    from unittest.mock import MagicMock

    from autoswe.harness.planner import _extract_plan_output

    plan_file = MagicMock()
    plan_file.read_text.return_value = "Plan content"

    with patch("autoswe.harness.planner._find_latest_plan_file", return_value=plan_file):
        with patch("autoswe.harness.planner.dbg.warning") as mock_warn:
            _extract_plan_output("some text")

    assert not mock_warn.called


# ---------------------------------------------------------------------------
# Plan detection in fix prompt (MCP + legacy)
# ---------------------------------------------------------------------------

def test_find_plan_in_comments_mcp_format():
    """_find_plan_in_comments should detect MCP-posted plans (## Plan header)."""
    from autoswe.harness.prompts import _find_plan_in_comments

    comments = [
        type("c", (), {"body": "Some other comment"})(),
        type("c", (), {"body": "## Plan\n\nStep 1: Fix A\nStep 2: Fix B\n\n_Reply with `/fix`..._"})(),
    ]

    result = _find_plan_in_comments(comments)
    assert "Step 1: Fix A" in result
    assert "Step 2: Fix B" in result
    # Should strip the "_Reply with" trailing line
    assert "_Reply with" not in result


def test_find_plan_in_comments_legacy_tag_format():
    """_find_plan_in_comments should detect legacy AUTOSWE_PLAN tags."""
    from autoswe.harness.prompts import _find_plan_in_comments

    comments = [
        type("c", (), {"body": "<AUTOSWE_PLAN>\nLegacy plan\n</AUTOSWE_PLAN>"})(),
    ]

    result = _find_plan_in_comments(comments)
    assert "Legacy plan" in result


def test_find_plan_in_comments_none_when_no_plan():
    """_find_plan_in_comments returns empty string when no plan found."""
    from autoswe.harness.prompts import _find_plan_in_comments

    comments = [
        type("c", (), {"body": "Just a regular comment"})(),
    ]
    result = _find_plan_in_comments(comments)
    assert result == ""


def test_find_plan_in_comments_none_on_empty_list():
    """_find_plan_in_comments returns empty string for None/empty input."""
    from autoswe.harness.prompts import _find_plan_in_comments

    assert _find_plan_in_comments(None) == ""
    assert _find_plan_in_comments([]) == ""


# ---------------------------------------------------------------------------
# Resume plan MCP prompt
# ---------------------------------------------------------------------------

def test_resume_plan_prompt_mentions_mcp_tools(tmp_path):
    """resume_plan should pass a prompt mentioning MCP tools."""
    prompts = []

    def fake_run(prompt, **kwargs):
        prompts.append(prompt)
        return _r("<AUTOSWE_PLAN>\nPlan\n</AUTOSWE_PLAN>")

    task = make_task(session_id="sess-1")

    with patch("autoswe.harness.planner.create_worktree", return_value=tmp_path):
        with patch("autoswe.harness.planner._find_latest_plan_file", return_value=None):
            with patch("autoswe.harness.runner.run", side_effect=fake_run):
                from autoswe.harness.planner import resume_plan
                resume_plan(task, "Use approach A.", {}, {})

    assert "mcp__autoswe_comment__post_plan" in prompts[0]
    assert "AskUserQuestion" in prompts[0]


# ---------------------------------------------------------------------------
# Inline comment MCP server config (Feature F)
# ------------------------------------------------------------------


def test_build_inline_comment_server_returns_config():
    """build_mcp_inline_comment_server returns config for GitHub with valid params."""
    from autoswe.harness.mcp_config import build_mcp_inline_comment_server

    task = make_task()
    rc = {"provider": "github"}
    result = build_mcp_inline_comment_server(task, rc, "abc123", 5)

    assert result is not None
    assert "autoswe_inline_comment" in result
    cfg = result["autoswe_inline_comment"]
    assert cfg["env"]["AUTOSWE_PR_NUMBER"] == "5"
    assert cfg["env"]["AUTOSWE_COMMIT_SHA"] == "abc123"
    assert cfg["env"]["AUTOSWE_OWNER"] == "o"


def test_build_inline_comment_server_none_for_azure():
    """Inline comment server is not built for Azure provider."""
    from autoswe.harness.mcp_config import build_mcp_inline_comment_server

    task = make_task()
    rc = {"provider": "azure"}
    result = build_mcp_inline_comment_server(task, rc, "abc123", 5)
    assert result is None


def test_build_inline_comment_server_none_without_sha():
    """Inline comment server requires a commit SHA."""
    from autoswe.harness.mcp_config import build_mcp_inline_comment_server

    task = make_task()
    rc = {"provider": "github"}
    result = build_mcp_inline_comment_server(task, rc, "", 5)
    assert result is None


def test_build_inline_comment_server_none_without_pr():
    """Inline comment server requires a PR number."""
    from autoswe.harness.mcp_config import build_mcp_inline_comment_server

    task = make_task()
    rc = {"provider": "github"}
    result = build_mcp_inline_comment_server(task, rc, "abc123", 0)
    assert result is None


def test_build_inline_comment_server_none_without_pr_none():
    """Inline comment server returns None when pr_number is None."""
    from autoswe.harness.mcp_config import build_mcp_inline_comment_server

    task = make_task()
    rc = {"provider": "github"}
    result = build_mcp_inline_comment_server(task, rc, "abc123", None)
    assert result is None


# ---------------------------------------------------------------------------
# MCP server body validation — post_plan / post_question
# ---------------------------------------------------------------------------

def test_mcp_post_plan_rejects_empty_body():
    """post_plan returns an error when body is empty."""
    import asyncio
    import importlib
    import os
    from unittest.mock import patch

    env = {
        "AUTOSWE_PROVIDER": "github",
        "AUTOSWE_OWNER": "o",
        "AUTOSWE_REPO": "r",
        "AUTOSWE_ISSUE_NUMBER": "1",
        "AUTOSWE_TOKEN": "tok",
        "AUTOSWE_COMMENT_ID": "",
        "AUTOSWE_SUPPRESS_POSTING": "1",
    }
    with patch.dict(os.environ, env):
        import mcp_servers.autoswe_comment_server as srv
        importlib.reload(srv)
        result = asyncio.run(srv.post_plan(body=""))

    assert any("cannot be empty" in c.text for c in result)


def test_mcp_post_plan_rejects_whitespace_body():
    """post_plan returns an error when body is whitespace-only."""
    import asyncio
    import importlib
    import os
    from unittest.mock import patch

    env = {
        "AUTOSWE_PROVIDER": "github",
        "AUTOSWE_OWNER": "o",
        "AUTOSWE_REPO": "r",
        "AUTOSWE_ISSUE_NUMBER": "1",
        "AUTOSWE_TOKEN": "tok",
        "AUTOSWE_COMMENT_ID": "",
        "AUTOSWE_SUPPRESS_POSTING": "1",
    }
    with patch.dict(os.environ, env):
        import mcp_servers.autoswe_comment_server as srv
        importlib.reload(srv)
        result = asyncio.run(srv.post_plan(body="   \n  "))

    assert any("cannot be empty" in c.text for c in result)


def test_mcp_post_question_rejects_empty_body():
    """post_question returns an error when body is empty."""
    import asyncio
    import importlib
    import os
    from unittest.mock import patch

    env = {
        "AUTOSWE_PROVIDER": "github",
        "AUTOSWE_OWNER": "o",
        "AUTOSWE_REPO": "r",
        "AUTOSWE_ISSUE_NUMBER": "1",
        "AUTOSWE_TOKEN": "tok",
        "AUTOSWE_COMMENT_ID": "",
        "AUTOSWE_SUPPRESS_POSTING": "1",
    }
    with patch.dict(os.environ, env):
        import mcp_servers.autoswe_comment_server as srv
        importlib.reload(srv)
        result = asyncio.run(srv.post_question(body=""))

    assert any("cannot be empty" in c.text for c in result)


def test_mcp_post_question_accepts_real_body():
    """post_question passes through with SUPPRESS_POSTING when body is non-empty."""
    import asyncio
    import importlib
    import os
    from unittest.mock import patch

    env = {
        "AUTOSWE_PROVIDER": "github",
        "AUTOSWE_OWNER": "o",
        "AUTOSWE_REPO": "r",
        "AUTOSWE_ISSUE_NUMBER": "1",
        "AUTOSWE_TOKEN": "tok",
        "AUTOSWE_COMMENT_ID": "",
        "AUTOSWE_SUPPRESS_POSTING": "1",
    }
    with patch.dict(os.environ, env):
        import mcp_servers.autoswe_comment_server as srv
        importlib.reload(srv)
        result = asyncio.run(srv.post_question(body="Is this approach correct?"))

    assert any("suppressed" in c.text for c in result)
