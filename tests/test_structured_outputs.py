"""Tests for schema-validated structured output on plan/review (issue #159).

Covers:
- the JSON Schemas themselves (shape + ``output_format_for``),
- the Claude backend passing ``output_format`` to the SDK ``query()`` and
  capturing ``ResultMessage.structured_output`` onto ``RunResult``,
- graceful degrade on ``error_max_structured_output_retries`` / missing value,
- the planner preferring a valid structured payload over the text/MCP chain,
- the reviewer preferring a structured report over raw text,
- the capability gate (Claude advertises it, Codex does not).

The backend-level tests follow the established ``patch.object(sdk, "query",
fake_query)`` pattern from ``test_claude_runner.py``.
"""
import asyncio
import sys
from contextlib import contextmanager
from unittest.mock import patch

from claude_agent_sdk import ResultMessage

from autoswe.harness.runner import RunResult

# Local copies of the planner/reviewer test fixtures (those modules are not
# importable across test files in this suite — no ``tests/__init__.py``). The
# shapes match tests/test_planner_returns.py and tests/test_reviewer_returns.py.

_FETCH_COMMENTS_PATCH = patch("autoswe.tracking.api._fetch_comments", return_value=[])


def _plan_task():
    return {
        "id": "o_r_1", "owner": "o", "repo": "r", "issue_number": 1,
        "title": "Test", "body": "/plan", "base_branch": "master",
        "session_id": None, "_token": "ghp_fake",
    }


def _review_task():
    return {
        "id": "o/r#1", "owner": "o", "repo": "r", "issue_number": 1,
        "title": "Test issue", "body": "Issue description.", "base_branch": "master",
        "session_id": None, "_token": "ghp_fake",
    }


@contextmanager
def _patch_plan_worktree(tmp_path, fs_file=None):
    with patch("autoswe.harness.planner.create_worktree", return_value=tmp_path):
        with patch("autoswe.harness.planner._find_latest_plan_file", return_value=fs_file):
            yield tmp_path


@contextmanager
def _patch_review_worktree(tmp_path):
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


def _result_message(session_id="sess", subtype="success", structured_output=None):
    """Build a minimal ResultMessage as the backend's stream would yield."""
    return ResultMessage(
        subtype=subtype,
        duration_ms=1000,
        duration_api_ms=900,
        is_error=False,
        num_turns=1,
        session_id=session_id,
        total_cost_usd=0.01,
        structured_output=structured_output,
    )


# ---------------------------------------------------------------------------
# Schemas + output_format_for
# ---------------------------------------------------------------------------


def test_plan_schema_is_draft07_object_with_required_flag():
    from autoswe.harness.schemas import PLAN_SCHEMA

    assert PLAN_SCHEMA["type"] == "object"
    assert "is_plan_ready" in PLAN_SCHEMA["required"]
    props = PLAN_SCHEMA["properties"]
    assert props["is_plan_ready"]["type"] == "boolean"
    assert props["plan_markdown"]["type"] == "string"
    assert props["question_markdown"]["type"] == "string"
    # `format` keyword is deliberately avoided (not enforced by the SDK, and
    # older CLIs rejected any schema containing it).
    for prop in props.values():
        assert "format" not in prop


def test_review_schema_is_draft07_object_with_required_report():
    from autoswe.harness.schemas import REVIEW_SCHEMA

    assert REVIEW_SCHEMA["type"] == "object"
    assert "report_markdown" in REVIEW_SCHEMA["required"]
    assert REVIEW_SCHEMA["properties"]["report_markdown"]["type"] == "string"
    assert REVIEW_SCHEMA["properties"]["verdict"]["type"] == "string"
    # verdict is optional (not required)
    assert "verdict" not in REVIEW_SCHEMA["required"]


def test_output_format_for_returns_json_schema_option_shape():
    from autoswe.harness.schemas import PLAN_SCHEMA, output_format_for

    of = output_format_for(PLAN_SCHEMA)
    assert of["type"] == "json_schema"
    assert of["schema"] is PLAN_SCHEMA
    # Fresh top-level dict each call (callers may hand it to the SDK directly).
    assert output_format_for(PLAN_SCHEMA) == of
    assert output_format_for(PLAN_SCHEMA) is not of


# ---------------------------------------------------------------------------
# Capability gate
# ---------------------------------------------------------------------------


def test_claude_backend_advertises_structured_output_capability():
    from autoswe.harness.backends.claude_code import ClaudeCodeBackend

    assert "structured_output" in ClaudeCodeBackend.capabilities()


def test_codex_backend_does_not_advertise_structured_output_capability():
    from autoswe.harness.backends.codex import CodexBackend

    assert "structured_output" not in CodexBackend.capabilities()


def test_runresult_structured_output_defaults_to_none():
    from autoswe.harness.runner import RunResult

    assert RunResult("text", "s", "success").structured_output is None


# ---------------------------------------------------------------------------
# Claude backend: output_format -> options.query, and capture structured_output
# ---------------------------------------------------------------------------


def test_backend_passes_output_format_to_query_options():
    """When spec.output_format is set, ClaudeAgentOptions.output_format matches."""
    from unittest.mock import patch

    from autoswe.harness.runner import _run_async

    captured = {}

    async def fake_query(prompt, options):
        captured["options"] = options
        yield _result_message(structured_output={"is_plan_ready": True, "plan_markdown": "plan"})

    expected = {"type": "json_schema", "schema": {"type": "object"}}
    sdk = sys.modules["claude_agent_sdk"]
    with patch.object(sdk, "query", fake_query):
        asyncio.run(_run_async(prompt="p", cwd="/tmp", output_format=expected))

    assert captured["options"].output_format == expected


def test_backend_omits_output_format_when_unset():
    """No spec.output_format -> the option is not set on ClaudeAgentOptions."""
    from unittest.mock import patch

    from autoswe.harness.runner import _run_async

    captured = {}

    async def fake_query(prompt, options):
        captured["options"] = options
        yield _result_message()

    sdk = sys.modules["claude_agent_sdk"]
    with patch.object(sdk, "query", fake_query):
        asyncio.run(_run_async(prompt="p", cwd="/tmp"))

    assert getattr(captured["options"], "output_format", None) is None


def test_backend_captures_structured_output_on_runresult():
    """ResultMessage.structured_output round-trips onto RunResult.structured_output."""
    from unittest.mock import patch

    from autoswe.harness.runner import RunResult, _run_async

    payload = {"is_plan_ready": True, "plan_markdown": "# Plan", "question_markdown": ""}

    async def fake_query(prompt, options):
        yield _result_message(structured_output=payload)

    sdk = sys.modules["claude_agent_sdk"]
    with patch.object(sdk, "query", fake_query):
        result = asyncio.run(_run_async(prompt="p", cwd="/tmp"))

    assert isinstance(result, RunResult)
    assert result.structured_output == payload


def test_backend_drops_structured_output_on_retries_exhausted():
    """subtype error_max_structured_output_retries + no value -> None (text fallback)."""
    from unittest.mock import patch

    from autoswe.harness.runner import _run_async

    async def fake_query(prompt, options):
        # A failed structured-output run: the CLI re-prompted to its limit and
        # gave up, so there is no structured_output.
        yield _result_message(subtype="error_max_structured_output_retries", structured_output=None)

    sdk = sys.modules["claude_agent_sdk"]
    with patch.object(sdk, "query", fake_query):
        result = asyncio.run(_run_async(prompt="p", cwd="/tmp"))

    assert result.structured_output is None
    assert result.subtype == "error_max_structured_output_retries"


def test_backend_success_without_structured_output_is_none():
    """success subtype but no structured_output value -> None (graceful degrade)."""
    from unittest.mock import patch

    from autoswe.harness.runner import _run_async

    async def fake_query(prompt, options):
        yield _result_message(subtype="success", structured_output=None)

    sdk = sys.modules["claude_agent_sdk"]
    with patch.object(sdk, "query", fake_query):
        result = asyncio.run(_run_async(prompt="p", cwd="/tmp"))

    assert result.structured_output is None


# ---------------------------------------------------------------------------
# Planner prefers a valid structured payload (and falls back otherwise)
# ---------------------------------------------------------------------------


def test_interpret_structured_plan_ready():
    from autoswe.harness.planner import _interpret_structured_plan

    comment, done, plan_file = _interpret_structured_plan(
        {"is_plan_ready": True, "plan_markdown": "# My Plan\n\nStep 1", "question_markdown": ""}
    )
    assert done == "PLAN_READY"
    assert plan_file is None
    assert "# My Plan" in comment
    assert "Step 1" in comment


def test_interpret_structured_plan_questions():
    from autoswe.harness.planner import _interpret_structured_plan

    comment, done, plan_file = _interpret_structured_plan(
        {"is_plan_ready": False, "question_markdown": "Which approach?"}
    )
    assert done == "WAITING: questions"
    assert plan_file is None
    assert "Which approach?" in comment


def test_interpret_structured_plan_malformed_returns_none():
    from autoswe.harness.planner import _interpret_structured_plan

    # Ready but no plan body -> unusable -> fall through to the next source.
    assert _interpret_structured_plan({"is_plan_ready": True, "plan_markdown": "   "}) is None
    # Questions but no question body -> unusable.
    assert _interpret_structured_plan({"is_plan_ready": False, "question_markdown": ""}) is None
    # Not a dict at all.
    assert _interpret_structured_plan(None) is None
    assert _interpret_structured_plan("garbage") is None


def test_plan_interpret_mcp_posted_wins_over_structured(tmp_path, mock_gh_post_comment):
    """MCP plan_posted=True already posted the comment -> no double-post.

    When the backend posted the plan via the ``post_plan`` MCP tool during the
    run, the plan comment is already on the thread. The structured payload must
    NOT be re-posted on top of it (issue #159): the handler returns a bare
    ``PLAN_READY`` (not ``_POST:``) and issues no second comment.
    """
    structured = {"is_plan_ready": True, "plan_markdown": "Structured plan body", "question_markdown": ""}
    task = _plan_task()

    with _patch_plan_worktree(tmp_path):
        with _FETCH_COMMENTS_PATCH:
            with patch("autoswe.harness.runner.run",
                       return_value=RunResult("", "sess", "success", plan_posted=True,
                                              structured_output=structured)):
                from autoswe.harness.planner import run_plan
                result = run_plan(task, {}, {"GITHUB_TOKEN": "tok"})

    # Bare PLAN_READY — NOT the "_POST:" form that would trigger a 2nd comment.
    assert result.done_content == "PLAN_READY"
    assert not mock_gh_post_comment.posted, (
        "MCP already posted the plan; handler must not re-post the structured body"
    )


def test_plan_interpret_structured_beats_text_when_no_mcp(tmp_path, mock_gh_post_comment):
    """With no MCP flags set, the structured payload is posted (and wins over tags)."""
    structured = {"is_plan_ready": True, "plan_markdown": "Structured plan body", "question_markdown": ""}
    task = _plan_task()
    text = "<AUTOSWE_PLAN>\nFrom tags\n</AUTOSWE_PLAN>"

    with _patch_plan_worktree(tmp_path):
        with _FETCH_COMMENTS_PATCH:
            with patch("autoswe.harness.planner._find_latest_plan_file", return_value=None):
                with patch("autoswe.harness.runner.run",
                           return_value=RunResult(text, "sess", "success",
                                                  structured_output=structured)):
                    from autoswe.harness.planner import run_plan
                    result = run_plan(task, {}, {"GITHUB_TOKEN": "tok"})

    assert result.done_content == "PLAN_READY"
    # The structured body is posted, not the tag-parsed body.
    assert "Structured plan body" in mock_gh_post_comment.posted[0]["body"]
    assert "From tags" not in mock_gh_post_comment.posted[0]["body"]


def test_plan_interpret_structured_waiting(tmp_path, mock_gh_post_comment):
    """is_plan_ready False -> WAITING with the structured questions posted."""
    structured = {"is_plan_ready": False, "plan_markdown": "", "question_markdown": "Approach A or B?"}
    task = _plan_task()

    with _patch_plan_worktree(tmp_path):
        with _FETCH_COMMENTS_PATCH:
            with patch("autoswe.harness.runner.run",
                       return_value=RunResult("", "sess", "success", structured_output=structured)):
                from autoswe.harness.planner import run_plan
                result = run_plan(task, {}, {"GITHUB_TOKEN": "tok"})

    assert result.done_content.startswith("WAITING:")
    assert "Approach A or B?" in mock_gh_post_comment.posted[0]["body"]


def test_plan_interpret_falls_back_when_structured_missing(tmp_path, mock_gh_post_comment):
    """structured_output None -> the existing text-tag chain still applies."""
    task = _plan_task()
    text = "<AUTOSWE_PLAN>\nFrom tags\n</AUTOSWE_PLAN>"

    with _patch_plan_worktree(tmp_path):
        with _FETCH_COMMENTS_PATCH:
            with patch("autoswe.harness.planner._find_latest_plan_file", return_value=None):
                with patch("autoswe.harness.runner.run",
                           return_value=RunResult(text, "sess", "success", structured_output=None)):
                    from autoswe.harness.planner import run_plan
                    result = run_plan(task, {}, {"GITHUB_TOKEN": "tok"})

    assert result.done_content == "PLAN_READY"
    assert "From tags" in mock_gh_post_comment.posted[0]["body"]


# ---------------------------------------------------------------------------
# Reviewer prefers a structured report, falls back to result.text
# ---------------------------------------------------------------------------


def test_report_text_prefers_structured_report():
    from autoswe.harness.reviewer import _report_text_from_result
    from autoswe.harness.runner import RunResult

    result = RunResult("raw text", "s", "success",
                       structured_output={"report_markdown": "Structured report", "verdict": "LGTM"})
    assert _report_text_from_result(result) == "Structured report"


def test_report_text_falls_back_to_raw_text_when_structured_absent():
    from autoswe.harness.reviewer import _report_text_from_result
    from autoswe.harness.runner import RunResult

    assert _report_text_from_result(RunResult("raw", "s", "success")) == "raw"
    # Structured present but report_markdown empty -> fall back to raw.
    assert _report_text_from_result(
        RunResult("raw", "s", "success", structured_output={"report_markdown": "  "})
    ) == "raw"


def test_run_review_uses_structured_report(tmp_path, mock_gh_post_comment):
    """When structured_output carries report_markdown, that (not result.text) is posted+filed."""
    task = _review_task()

    with _patch_review_worktree(tmp_path):
        with patch("autoswe.harness.reviewer._run_git", return_value="stat"):
            with _FETCH_COMMENTS_PATCH:
                with patch("autoswe.harness.runner.run",
                           return_value=RunResult("IGNORE ME raw text", "s", "success",
                                                  structured_output={"report_markdown": "Structured review body",
                                                                     "verdict": "LGTM"})):
                    from autoswe.harness.reviewer import run_review
                    result = run_review(task, {}, {"GITHUB_TOKEN": "tok"})

    assert result.done_content.startswith("REVIEW_READY\t")
    assert "Structured review body" in result.done_content
    assert "IGNORE ME raw text" not in result.done_content
    # The review file holds the structured report, not the raw text.
    from pathlib import Path
    assert "Structured review body" in Path(result.review_file_path).read_text()


def test_run_review_falls_back_to_raw_text(tmp_path, mock_gh_post_comment):
    """No structured_output -> result.text is used (unchanged behavior)."""
    task = _review_task()
    text = "## Summary\n\nraw review"

    with _patch_review_worktree(tmp_path):
        with patch("autoswe.harness.reviewer._run_git", return_value="stat"):
            with _FETCH_COMMENTS_PATCH:
                with patch("autoswe.harness.runner.run", return_value=RunResult(text, "s", "success")):
                    from autoswe.harness.reviewer import run_review
                    result = run_review(task, {}, {"GITHUB_TOKEN": "tok"})

    assert result.done_content.startswith("REVIEW_READY\t")
    assert "raw review" in result.done_content
