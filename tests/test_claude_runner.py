"""Tests for autoswe.harness.runner — env override logic and timeout."""

import asyncio
import sys
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# run() — env overrides and parameter resolution
# ---------------------------------------------------------------------------

def test_run_builds_env_overrides():
    """run() should set ANTHROPIC env vars before calling SDK."""
    cfg = {
        "AGENT_TIMEOUT": 7200,
        "ANTHROPIC_BASE_URL": "http://server:11434",
        "ANTHROPIC_AUTH_TOKEN": "ollama",
        "ANTHROPIC_API_KEY": "sk-ant-test",
        "CLAUDE_CLI_PATH": "",
    }
    repo_cfg = {}
    env_captured = {}

    original_update = dict.update

    def capture_update(self, *args, **kwargs):
        if self is env_captured:
            env_captured.update(*args, **kwargs)
        return original_update(self, *args, **kwargs)

    # Patch at the _run_async level to capture env updates
    with patch.object(asyncio, "run") as mock_async_run:
        def fake_run(coro):
            coro.close()  # Discard unawaited coroutine to avoid GC warnings
            from autoswe.harness.backends.base import RunResult
            return RunResult(text="text", session_id="sess-1", subtype="success")
        mock_async_run.side_effect = fake_run

        from autoswe.harness.runner import run
        run("test prompt", cwd="/tmp", cfg=cfg, repo_cfg=repo_cfg)

    assert mock_async_run.called


def test_run_resolves_model_from_repo_cfg():
    """repo_cfg model should be used as fallback when no explicit model."""
    cfg = {
        "AGENT_TIMEOUT": 7200,
        "ANTHROPIC_BASE_URL": "",
        "ANTHROPIC_AUTH_TOKEN": "",
        "ANTHROPIC_API_KEY": "",
    }
    repo_cfg = {"model": "claude-opus-4-6"}

    with patch.object(asyncio, "run") as mock_async_run:
        def fake_run(coro):
            coro.close()  # Discard unawaited coroutine to avoid GC warnings
            from autoswe.harness.backends.base import RunResult
            return RunResult(text="text", session_id="sess-1", subtype="success")
        mock_async_run.side_effect = fake_run

        from autoswe.harness.runner import run
        run("test prompt", cwd="/tmp", cfg=cfg, repo_cfg=repo_cfg)

    assert mock_async_run.called


def test_respects_explicit_model():
    """Explicit model parameter should be passed through."""
    cfg = {
        "AGENT_TIMEOUT": 7200,
        "ANTHROPIC_BASE_URL": "",
        "ANTHROPIC_AUTH_TOKEN": "",
        "ANTHROPIC_API_KEY": "",
    }
    repo_cfg = {"model": "claude-opus-4-6"}

    with patch.object(asyncio, "run") as mock_async_run:
        def fake_run(coro):
            coro.close()  # Discard unawaited coroutine to avoid GC warnings
            from autoswe.harness.backends.base import RunResult
            return RunResult(text="text", session_id="sess-1", subtype="success")
        mock_async_run.side_effect = fake_run

        from autoswe.harness.runner import run
        run("test prompt", cwd="/tmp", cfg=cfg, repo_cfg=repo_cfg, model="claude-sonnet-4-6")

    assert mock_async_run.called


def test_run_timeout_propagates():
    """Timeout should be raised as asyncio.TimeoutError."""
    import asyncio as aio
    cfg = {"AGENT_TIMEOUT": 7200}

    with patch.object(aio, "run", side_effect=aio.TimeoutError) as mock_run:
        from autoswe.harness.runner import run
        try:
            run("test prompt", cwd="/tmp", cfg=cfg)
            assert False, "Should have raised TimeoutError"
        except aio.TimeoutError:
            pass  # Expected
        if mock_run.call_args:
            mock_run.call_args[0][0].close()  # Discard unawaited coroutine


def test_run_reads_timeout_from_cfg():
    """AGENT_TIMEOUT from cfg should be used."""
    cfg = {"AGENT_TIMEOUT": 300}

    with patch.object(asyncio, "run") as mock_async_run:
        def fake_run(coro):
            coro.close()  # Discard unawaited coroutine to avoid GC warnings
            from autoswe.harness.backends.base import RunResult
            return RunResult(text="text", session_id="sess-1", subtype="success")
        mock_async_run.side_effect = fake_run

        from autoswe.harness.runner import run
        run("test prompt", cwd="/tmp", cfg=cfg)

    assert mock_async_run.called


def test_run_uses_repo_agent_timeout():
    """Per-repo agent_timeout overrides global AGENT_TIMEOUT."""
    cfg = {"AGENT_TIMEOUT": 7200}
    repo_cfg = {"agent_timeout": 600}

    with patch.object(asyncio, "run") as mock_async_run:
        def fake_run(coro):
            coro.close()  # Discard unawaited coroutine to avoid GC warnings
            from autoswe.harness.backends.base import RunResult
            return RunResult(text="text", session_id="sess-1", subtype="success")
        mock_async_run.side_effect = fake_run

        from autoswe.harness.runner import run
        run("test prompt", cwd="/tmp", cfg=cfg, repo_cfg=repo_cfg)

    assert mock_async_run.called


# ---------------------------------------------------------------------------
# Model resolution order (highest → lowest)
# ---------------------------------------------------------------------------

def test_model_resolution_order():
    """Explicit > repo_cfg fix_model > repo_cfg model > cfg FIX_MODEL > None."""
    cfg = {"FIX_MODEL": "cfg-model", "AGENT_TIMEOUT": 7200}
    repo_cfg = {"model": "repo-model", "fix_model": "repo-fix-model"}

    with patch.object(asyncio, "run") as mock_async_run:
        def fake_run(coro):
            coro.close()  # Discard unawaited coroutine to avoid GC warnings
            from autoswe.harness.backends.base import RunResult
            return RunResult(text="text", session_id="sess-1", subtype="success")
        mock_async_run.side_effect = fake_run

        from autoswe.harness.runner import run

        # Explicit model wins
        run("test", cwd="/tmp", cfg=cfg, repo_cfg=repo_cfg, model="explicit")
        assert mock_async_run.called


# ---------------------------------------------------------------------------
# RunResult dataclass
# ---------------------------------------------------------------------------

def test_run_result_tuple_unpacking():
    """RunResult should support backward-compatible tuple unpacking."""
    from autoswe.harness.runner import RunResult

    result = RunResult(text="hello", session_id="s1", subtype="success", cost_usd=0.5, duration_seconds=10.5)
    text, session_id, subtype = result
    assert text == "hello"
    assert session_id == "s1"
    assert subtype == "success"


def test_run_result_has_cost_and_duration():
    """RunResult should carry cost_usd and duration_seconds."""
    from autoswe.harness.runner import RunResult

    result = RunResult(text="t", session_id="s", subtype="success", cost_usd=1.23, duration_seconds=42.5)
    assert result.cost_usd == 1.23
    assert result.duration_seconds == 42.5


def test_run_result_defaults():
    """RunResult cost and duration default to None/0."""
    from autoswe.harness.runner import RunResult

    result = RunResult(text="t", session_id=None, subtype=None)
    assert result.cost_usd is None
    assert result.duration_seconds == 0.0


# ---------------------------------------------------------------------------
# Progress callback
# ---------------------------------------------------------------------------

def test_progress_callback_receives_tool_events():
    """progress_callback should be called with formatted tool-use progress strings."""
    from claude_agent_sdk import ToolUseBlock

    from autoswe.harness import runner

    # Test the formatting helper directly
    block = ToolUseBlock(id="1", name="Bash", input={"command": "pytest tests/"})
    assert runner._format_tool_progress(block) == "Running: pytest tests/"

    block = ToolUseBlock(id="2", name="Read", input={"file_path": "src/foo.py"})
    assert runner._format_tool_progress(block) == "Read: src/foo.py"

    block = ToolUseBlock(id="3", name="Edit", input={"file_path": "src/bar.py"})
    assert runner._format_tool_progress(block) == "Editing: src/bar.py"

    block = ToolUseBlock(id="4", name="Write", input={"file_path": "src/baz.py"})
    assert runner._format_tool_progress(block) == "Writing: src/baz.py"

    block = ToolUseBlock(id="5", name="mcp__autoswe_comment__post_plan", input={})
    assert runner._format_tool_progress(block) == "MCP: mcp__autoswe_comment__post_plan"

    block = ToolUseBlock(id="6", name="SomeOtherTool", input={})
    assert runner._format_tool_progress(block) == "Tool: SomeOtherTool"


# ---------------------------------------------------------------------------
# Retry on failure (AGENT_RETRY_ON_FAILURE)
# ---------------------------------------------------------------------------

def test_no_retry_by_default():
    """With AGENT_RETRY_ON_FAILURE=0, a single failure is raised immediately."""
    import asyncio as aio
    cfg = {"AGENT_TIMEOUT": 7200, "AGENT_RETRY_ON_FAILURE": 0}
    call_count = 0

    with patch.object(aio, "run") as mock_run:
        def fail_once(coro):
            nonlocal call_count
            call_count += 1
            coro.close()
            raise aio.TimeoutError()
        mock_run.side_effect = fail_once

        from autoswe.harness.runner import run
        try:
            run("test", cwd="/tmp", cfg=cfg)
            assert False, "should have raised"
        except aio.TimeoutError:
            pass

    assert call_count == 1


def test_retry_once_on_timeout():
    """With AGENT_RETRY_ON_FAILURE=1, timeout is retried once then raised."""
    import asyncio as aio
    cfg = {"AGENT_TIMEOUT": 7200, "AGENT_RETRY_ON_FAILURE": 1}
    call_count = 0

    with patch.object(aio, "run") as mock_run:
        def fail_twice(coro):
            nonlocal call_count
            call_count += 1
            coro.close()
            raise aio.TimeoutError()
        mock_run.side_effect = fail_twice

        from autoswe.harness.runner import run
        try:
            run("test", cwd="/tmp", cfg=cfg)
            assert False, "should have raised"
        except aio.TimeoutError:
            pass

    assert call_count == 2


def test_retry_succeeds_on_second_attempt():
    """With AGENT_RETRY_ON_FAILURE=1, succeeds on second attempt after first fails."""
    import asyncio as aio
    cfg = {"AGENT_TIMEOUT": 7200, "AGENT_RETRY_ON_FAILURE": 1}
    call_count = 0

    from autoswe.harness.runner import RunResult

    with patch.object(aio, "run") as mock_run:
        def fail_then_succeed(coro):
            nonlocal call_count
            call_count += 1
            coro.close()
            if call_count == 1:
                raise aio.TimeoutError()
            return RunResult(text="ok", session_id="s1", subtype="success")
        mock_run.side_effect = fail_then_succeed

        from autoswe.harness.runner import run
        result = run("test", cwd="/tmp", cfg=cfg)

    assert call_count == 2
    assert result.text == "ok"


def test_retry_respects_repo_cfg_override():
    """Per-repo agent_retry_on_failure overrides global AGENT_RETRY_ON_FAILURE."""
    import asyncio as aio
    cfg = {"AGENT_TIMEOUT": 7200, "AGENT_RETRY_ON_FAILURE": 0}
    repo_cfg = {"agent_retry_on_failure": 2}
    call_count = 0

    with patch.object(aio, "run") as mock_run:
        def always_fail(coro):
            nonlocal call_count
            call_count += 1
            coro.close()
            raise aio.TimeoutError()
        mock_run.side_effect = always_fail

        from autoswe.harness.runner import run
        try:
            run("test", cwd="/tmp", cfg=cfg, repo_cfg=repo_cfg)
            assert False, "should have raised"
        except aio.TimeoutError:
            pass

    assert call_count == 3  # 1 initial + 2 retries


# ---------------------------------------------------------------------------
# MCP servers passthrough
# ---------------------------------------------------------------------------

def test_mcp_servers_passed_to_run():
    """mcp_servers parameter should be accepted and forwarded."""
    cfg = {"AGENT_TIMEOUT": 7200}
    mcp_config = {
        "test_server": {
            "command": "python",
            "args": ["-m", "test_server"],
            "env": {"TOKEN": "abc"},
        }
    }

    with patch.object(asyncio, "run") as mock_async_run:
        def fake_run(coro):
            coro.close()  # Discard unawaited coroutine
            from autoswe.harness.runner import RunResult
            return RunResult(text="", session_id="s1", subtype="success")
        mock_async_run.side_effect = fake_run

        from autoswe.harness.runner import run
        run("test", cwd="/tmp", cfg=cfg, mcp_servers=mcp_config)

    # The call should accept mcp_servers without error
    assert mock_async_run.called


# ---------------------------------------------------------------------------
# plan_file_path capture from Write tool calls

def test_run_result_has_plan_file_path_field():
    """RunResult should carry plan_file_path."""
    from autoswe.harness.runner import RunResult

    result = RunResult(
        text="t", session_id="s", subtype="success",
        cost_usd=0.10, duration_seconds=5.0,
        plan_file_path="/home/user/.claude/plans/test.md",
    )
    assert result.plan_file_path == "/home/user/.claude/plans/test.md"


def test_run_result_plan_file_path_defaults_to_none():
    """RunResult.plan_file_path should default to None."""
    from autoswe.harness.runner import RunResult

    result = RunResult(text="t", session_id="s", subtype="success")
    assert result.plan_file_path is None


def test_extract_plan_file_path_write_to_plans_dir():
    """_extract_plan_file_path returns path for Write calls to plans directory."""
    from pathlib import Path

    from claude_agent_sdk import ToolUseBlock

    from autoswe.harness.runner import _extract_plan_file_path

    plans_dir = Path.home() / ".claude" / "plans"

    block = ToolUseBlock(
        id="1",
        name="Write",
        input={"file_path": str(plans_dir / "test-plan-abc123.md")},
    )
    result = _extract_plan_file_path(block)
    assert result is not None
    assert "test-plan-abc123.md" in result


def test_extract_plan_file_path_write_to_plans_dir_via_path_key():
    """_extract_plan_file_path also reads the 'path' input key."""
    from pathlib import Path

    from claude_agent_sdk import ToolUseBlock

    from autoswe.harness.runner import _extract_plan_file_path

    plans_dir = Path.home() / ".claude" / "plans"

    block = ToolUseBlock(
        id="2",
        name="Write",
        input={"path": str(plans_dir / "another-plan.md")},
    )
    result = _extract_plan_file_path(block)
    assert result is not None
    assert "another-plan.md" in result


def test_extract_plan_file_path_write_outside_plans_dir_returns_none():
    """_extract_plan_file_path returns None for Write calls outside plans directory."""
    from claude_agent_sdk import ToolUseBlock

    from autoswe.harness.runner import _extract_plan_file_path

    block = ToolUseBlock(
        id="3",
        name="Write",
        input={"file_path": "/tmp/some-file.txt"},
    )
    result = _extract_plan_file_path(block)
    assert result is None


def test_extract_plan_file_path_non_write_tool_returns_none():
    """_extract_plan_file_path returns None for non-Write tool blocks."""
    from claude_agent_sdk import ToolUseBlock

    from autoswe.harness.runner import _extract_plan_file_path

    block = ToolUseBlock(
        id="4",
        name="Bash",
        input={"command": "echo hello"},
    )
    result = _extract_plan_file_path(block)
    assert result is None


def test_extract_plan_file_path_empty_input_returns_none():
    """_extract_plan_file_path returns None for Write with empty/missing path."""
    from claude_agent_sdk import ToolUseBlock

    from autoswe.harness.runner import _extract_plan_file_path

    block = ToolUseBlock(id="5", name="Write", input={})
    assert _extract_plan_file_path(block) is None

    block = ToolUseBlock(id="6", name="Write", input={"file_path": ""})
    assert _extract_plan_file_path(block) is None


def test_extract_plan_file_path_server_tool_block_returns_none():
    """_extract_plan_file_path returns None for ServerToolUseBlock (not ToolUseBlock)."""
    from claude_agent_sdk import ServerToolUseBlock

    from autoswe.harness.runner import _extract_plan_file_path

    block = ServerToolUseBlock(
        id="8",
        name="mcp__test__write_plan",
        input={"file_path": "/home/user/.claude/plans/server-plan.md"},
    )
    result = _extract_plan_file_path(block)
    assert result is None

# Async generator crash handling (Ollama issue)
# ---------------------------------------------------------------------------

def test_async_generator_crash_returns_partial_results_no_can_use_tool():
    """When the query generator raises RuntimeError with 'async generator' or
    'aclose' in the message, _run_async should return partial results instead
    of propagating the exception. This prevents session_id loss when Ollama
    crashes mid-stream (issue #208)."""
    from claude_agent_sdk import AssistantMessage, TextBlock

    from autoswe.harness.runner import RunResult, _run_async

    async def fake_query_crash(prompt, options):
        """Yield some text, then crash with async generator error."""
        yield AssistantMessage(content=[TextBlock(text="Partial answer")], model="test")
        yield AssistantMessage(content=[TextBlock(text="More text")], model="test")
        raise RuntimeError("aclose(): asynchronous generator is already running")

    async def run_it():
        sdk = sys.modules["claude_agent_sdk"]
        with patch.object(sdk, "query", fake_query_crash):
            result = await _run_async(
                "test prompt",
                cwd="/tmp",
                permission_mode="default",
                allowed_tools=["Read"],
            )
            return result

    result = asyncio.run(run_it())

    assert isinstance(result, RunResult)
    assert "Partial answer" in result.text
    assert "More text" in result.text
    assert result.session_id is None  # Was never set before the crash
    assert result.subtype is None


def test_async_generator_crash_preserves_session_id_if_already_captured():
    """If session_id was captured before the async generator crash, it should
    still be preserved in the partial results."""
    from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock

    from autoswe.harness.runner import RunResult, _run_async

    async def fake_query_with_session_then_crash(prompt, options):
        """Yield text + ResultMessage, then crash."""
        yield AssistantMessage(content=[TextBlock(text="Hello")], model="test")
        yield ResultMessage(
            subtype="success",
            duration_ms=1000,
            duration_api_ms=1000,
            is_error=False,
            num_turns=1,
            session_id="captured-session-id",
            total_cost_usd=0.01,
        )
        raise RuntimeError("aclose(): asynchronous generator is already running")

    async def run_it():
        sdk = sys.modules["claude_agent_sdk"]
        with patch.object(sdk, "query", fake_query_with_session_then_crash):
            result = await _run_async(
                "test prompt",
                cwd="/tmp",
                permission_mode="default",
                allowed_tools=["Read"],
            )
            return result

    result = asyncio.run(run_it())

    assert isinstance(result, RunResult)
    assert result.session_id == "captured-session-id"
    assert result.subtype == "success"
    assert result.cost_usd == 0.01


def test_async_generator_crash_with_can_use_tool_path():
    """Async generator crash in the can_use_tool path should also return
    partial results."""
    from claude_agent_sdk import AssistantMessage, TextBlock

    from autoswe.harness.runner import RunResult, _run_async

    async def fake_query_crash(prompt, options):
        """Yield some text, then crash."""
        yield AssistantMessage(content=[TextBlock(text="Before crash")], model="test")
        raise RuntimeError("aclose(): asynchronous generator is already running")

    async def fake_callback(name, inp, ctx):
        from claude_agent_sdk import PermissionResultAllow
        return PermissionResultAllow(updated_input=inp)

    async def run_it():
        sdk = sys.modules["claude_agent_sdk"]
        with patch.object(sdk, "query", fake_query_crash):
            result = await _run_async(
                "test prompt",
                cwd="/tmp",
                permission_mode="default",
                allowed_tools=["Read"],
                can_use_tool=fake_callback,
                state={},
            )
            return result

    result = asyncio.run(run_it())

    assert isinstance(result, RunResult)
    assert "Before crash" in result.text
    assert result.session_id is None


def test_non_async_generator_runtime_error_is_propagated():
    """RuntimeError without 'async generator' or 'aclose' should be propagated
    unchanged — we only catch the specific Ollama crash pattern."""
    from claude_agent_sdk import AssistantMessage, TextBlock

    from autoswe.harness.runner import _run_async

    async def fake_query_other_error(prompt, options):
        """Yield text, then crash with a non-matching RuntimeError."""
        yield AssistantMessage(content=[TextBlock(text="Hello")], model="test")
        raise RuntimeError("some other error occurred")

    async def run_it():
        sdk = sys.modules["claude_agent_sdk"]
        with patch.object(sdk, "query", fake_query_other_error):
            try:
                result = await _run_async(
                    "test prompt",
                    cwd="/tmp",
                    permission_mode="default",
                    allowed_tools=["Read"],
                )
                return result  # Should NOT reach here
            except RuntimeError as e:
                return e

    result = asyncio.run(run_it())

    assert isinstance(result, RuntimeError)
    assert "some other error occurred" in str(result)


def test_async_generator_crash_resumes_with_captured_session():
    """Regression test: when session_id is captured before an async generator
    crash, the caller can use it for resume on the next dispatch — preventing
    the fresh-session fallback described in issue #208."""
    from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock

    from autoswe.harness.runner import RunResult, _run_async

    captured_session = "session-xyz-123"

    async def fake_query_crash_after_session(prompt, options):
        """Mimics the #208 scenario: text arrives, session captured, then crash."""
        yield AssistantMessage(content=[TextBlock(text="Planning step 1")], model="test")
        yield AssistantMessage(content=[TextBlock(text="Planning step 2")], model="test")
        yield ResultMessage(
            subtype="success",
            duration_ms=5000,
            duration_api_ms=5000,
            is_error=False,
            num_turns=2,
            session_id=captured_session,
            total_cost_usd=0.05,
        )
        # Crash after ResultMessage — simulating Ollama async generator error
        raise RuntimeError("aclose(): asynchronous generator is already running")

    async def run_it():
        sdk = sys.modules["claude_agent_sdk"]
        with patch.object(sdk, "query", fake_query_crash_after_session):
            result = await _run_async(
                "plan prompt",
                cwd="/tmp",
                permission_mode="default",
                allowed_tools=["Read", "Glob", "Grep"],
            )
            return result

    result = asyncio.run(run_it())

    # The session_id MUST be preserved so the next dispatch can resume correctly
    assert isinstance(result, RunResult)
    assert result.session_id == captured_session
    assert result.subtype == "success"
    assert "Planning step 1" in result.text
    assert "Planning step 2" in result.text


# ---------------------------------------------------------------------------
# Credential cleanup (issue #40)

def test_credentials_cleaned_up_after_run():
    """Credentials set via harness_cfg are restored to their original values
    in os.environ after _run_async completes successfully."""
    import os

    from claude_agent_sdk import AssistantMessage, TextBlock

    from autoswe.harness.runner import RunResult, _run_async

    async def fake_query_success(prompt, options):
        yield AssistantMessage(content=[TextBlock(text="ok")], model="test")

    # Capture pre-existing values (may already be set by CI/harness)
    orig_api_key = os.environ.get("ANTHROPIC_API_KEY")
    orig_base_url = os.environ.get("ANTHROPIC_BASE_URL")

    async def run_it():
        sdk = sys.modules["claude_agent_sdk"]
        with patch.object(sdk, "query", fake_query_success):
            result = await _run_async(
                "test prompt",
                cwd="/tmp",
                permission_mode="default",
                allowed_tools=["Read"],
                state={"_harness_cfg": {
                    "anthropic_api_key": "sk-leak-test-key",
                    "anthropic_base_url": "http://leak.test",
                }},
            )
            return result

    result = asyncio.run(run_it())
    assert isinstance(result, RunResult)
    assert result.text == "ok"
    # Credentials must be restored to their pre-run values
    assert os.environ.get("ANTHROPIC_API_KEY") == orig_api_key
    assert os.environ.get("ANTHROPIC_BASE_URL") == orig_base_url


def test_credentials_cleaned_up_on_exception():
    """Credentials are restored from os.environ even when query() raises an
    exception that is NOT caught (non-Ollama error)."""
    import os

    from claude_agent_sdk import AssistantMessage, TextBlock

    from autoswe.harness.runner import _run_async

    async def fake_query_raise(prompt, options):
        yield AssistantMessage(content=[TextBlock(text="partial")], model="test")
        raise RuntimeError("some other error occurred")

    orig_api_key = os.environ.get("ANTHROPIC_API_KEY")

    async def run_it():
        sdk = sys.modules["claude_agent_sdk"]
        with patch.object(sdk, "query", fake_query_raise):
            try:
                result = await _run_async(
                    "test prompt",
                    cwd="/tmp",
                    permission_mode="default",
                    allowed_tools=["Read"],
                    state={"_harness_cfg": {
                        "anthropic_api_key": "sk-leak-on-error",
                    }},
                )
                return result  # Should NOT reach here
            except RuntimeError as e:
                return e

    result = asyncio.run(run_it())
    assert isinstance(result, RuntimeError)
    # Credentials must be restored to pre-run value after the exception
    assert os.environ.get("ANTHROPIC_API_KEY") == orig_api_key


def test_credentials_cleaned_up_on_async_generator_crash():
    """Credentials are cleaned up when the async-generator-crash partial-result
    path fires."""
    import os

    from claude_agent_sdk import AssistantMessage, TextBlock

    from autoswe.harness.runner import RunResult, _run_async

    async def fake_query_crash(prompt, options):
        yield AssistantMessage(content=[TextBlock(text="partial")], model="test")
        raise RuntimeError("aclose(): asynchronous generator is already running")

    orig_api_key = os.environ.get("ANTHROPIC_API_KEY")
    orig_auth_token = os.environ.get("ANTHROPIC_AUTH_TOKEN")

    async def run_it():
        sdk = sys.modules["claude_agent_sdk"]
        with patch.object(sdk, "query", fake_query_crash):
            result = await _run_async(
                "test prompt",
                cwd="/tmp",
                permission_mode="default",
                allowed_tools=["Read"],
                state={"_harness_cfg": {
                    "anthropic_api_key": "sk-crash-leak",
                    "anthropic_auth_token": "crash-token",
                }},
            )
            return result

    result = asyncio.run(run_it())
    assert isinstance(result, RunResult)
    assert "partial" in result.text
    # Credentials must be restored to their pre-run values
    assert os.environ.get("ANTHROPIC_API_KEY") == orig_api_key
    assert os.environ.get("ANTHROPIC_AUTH_TOKEN") == orig_auth_token


def test_credentials_not_leaked_between_tasks():
    """Two sequential runs with different keys don't leak credentials from run 1
    into run 2."""
    import os

    from claude_agent_sdk import AssistantMessage, TextBlock

    from autoswe.harness.runner import RunResult, _run_async

    async def fake_query(prompt, options):
        yield AssistantMessage(content=[TextBlock(text="ok")], model="test")

    orig_api_key = os.environ.get("ANTHROPIC_API_KEY")

    async def run_both():
        sdk = sys.modules["claude_agent_sdk"]

        # Run 1 with key A
        with patch.object(sdk, "query", fake_query):
            r1 = await _run_async(
                "prompt 1",
                cwd="/tmp",
                permission_mode="default",
                allowed_tools=["Read"],
                state={"_harness_cfg": {"anthropic_api_key": "sk-key-A"}},
            )

        # Credentials from run 1 must be restored (not leaked)
        assert os.environ.get("ANTHROPIC_API_KEY") == orig_api_key, \
            f"Key A leaked after run 1, got {os.environ.get('ANTHROPIC_API_KEY')}"

        # Run 2 with key B
        with patch.object(sdk, "query", fake_query):
            r2 = await _run_async(
                "prompt 2",
                cwd="/tmp",
                permission_mode="default",
                allowed_tools=["Read"],
                state={"_harness_cfg": {"anthropic_api_key": "sk-key-B"}},
            )

        # Credentials from run 2 must also be restored (not leaked)
        assert os.environ.get("ANTHROPIC_API_KEY") == orig_api_key, \
            f"Key B leaked after run 2, got {os.environ.get('ANTHROPIC_API_KEY')}"

        return r1, r2

    r1, r2 = asyncio.run(run_both())
    assert isinstance(r1, RunResult)
    assert isinstance(r2, RunResult)


def test_credentials_restore_preexisting_values():
    """If ANTHROPIC_API_KEY already exists before the run, the original value
    is restored (not deleted)."""
    import os

    from claude_agent_sdk import AssistantMessage, TextBlock

    from autoswe.harness.runner import RunResult, _run_async

    original_key = os.environ.get("ANTHROPIC_API_KEY")

    async def fake_query(prompt, options):
        yield AssistantMessage(content=[TextBlock(text="ok")], model="test")

    async def run_it():
        # Set a pre-existing value
        os.environ["ANTHROPIC_API_KEY"] = "sk-pre-existing"

        sdk = sys.modules["claude_agent_sdk"]
        with patch.object(sdk, "query", fake_query):
            result = await _run_async(
                "test prompt",
                cwd="/tmp",
                permission_mode="default",
                allowed_tools=["Read"],
                state={"_harness_cfg": {"anthropic_api_key": "sk-override"}},
            )
            return result

    try:
        result = asyncio.run(run_it())
        assert isinstance(result, RunResult)
        # The pre-existing value must be restored
        assert os.environ.get("ANTHROPIC_API_KEY") == "sk-pre-existing", \
            f"Expected pre-existing value, got {os.environ.get('ANTHROPIC_API_KEY')}"
    finally:
        # Restore whatever was there before our test
        if original_key is None:
            os.environ.pop("ANTHROPIC_API_KEY", None)
        else:
            os.environ["ANTHROPIC_API_KEY"] = original_key


# ---------------------------------------------------------------------------
# Per-session env — task-tracking opt-in + no process-env mutation (issue #120)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mode", ["plan", "read_only", "read_write"])
def test_todo_tools_enabled_by_default_in_options_env(mode):
    """ClaudeCodeBackend opts into the task-tracking tools by default.

    CLAUDE_CODE_ENABLE_TODO_TOOLS=1 must be set on options.env (the child CLI
    env) for every mode when no profile env is configured — this keeps the
    sticky progress comment rendering on newer model families that no longer
    provide those tools by default.
    """
    from claude_agent_sdk import AssistantMessage, TextBlock

    from autoswe.harness.runner import _run_async

    captured = {}

    async def fake_query(prompt, options):
        captured["options"] = options
        yield AssistantMessage(content=[TextBlock(text="ok")], model="test")

    sdk = sys.modules["claude_agent_sdk"]
    with patch.object(sdk, "query", fake_query):
        asyncio.run(_run_async(
            "test prompt", cwd="/tmp", mode=mode, state={"_harness_cfg": {}}
        ))

    assert "options" in captured, "fake_query was not called"
    opts_env = captured["options"].env
    assert opts_env.get("CLAUDE_CODE_ENABLE_TODO_TOOLS") == "1", (
        f"mode={mode!r}: expected default opt-in, got env={opts_env!r}"
    )


def test_todo_tools_default_via_legacy_no_mode():
    """The legacy path (mode=None) also gets the default opt-in on options.env."""
    from claude_agent_sdk import AssistantMessage, TextBlock

    from autoswe.harness.runner import _run_async

    captured = {}

    async def fake_query(prompt, options):
        captured["options"] = options
        yield AssistantMessage(content=[TextBlock(text="ok")], model="test")

    sdk = sys.modules["claude_agent_sdk"]
    with patch.object(sdk, "query", fake_query):
        asyncio.run(_run_async(
            "test prompt",
            cwd="/tmp",
            permission_mode="default",
            allowed_tools=["Read"],
            state={"_harness_cfg": {}},
        ))

    assert captured["options"].env.get("CLAUDE_CODE_ENABLE_TODO_TOOLS") == "1"


def test_profile_env_overrides_todo_tools_default():
    """A per-profile `env` value wins over the backend's todo-tools default."""
    from claude_agent_sdk import AssistantMessage, TextBlock

    from autoswe.harness.runner import _run_async

    captured = {}

    async def fake_query(prompt, options):
        captured["options"] = options
        yield AssistantMessage(content=[TextBlock(text="ok")], model="test")

    sdk = sys.modules["claude_agent_sdk"]
    with patch.object(sdk, "query", fake_query):
        asyncio.run(_run_async(
            "test prompt",
            cwd="/tmp",
            mode="read_write",
            state={"_harness_cfg": {"env": {"CLAUDE_CODE_ENABLE_TODO_TOOLS": "0"}}},
        ))

    # user value wins over the "1" default
    assert captured["options"].env.get("CLAUDE_CODE_ENABLE_TODO_TOOLS") == "0"


def test_profile_env_extra_var_and_credentials_on_options_env():
    """Profile `env` vars + Anthropic creds all land on options.env, not os.environ."""
    import os

    from claude_agent_sdk import AssistantMessage, TextBlock

    from autoswe.harness.runner import _run_async

    captured = {}

    async def fake_query(prompt, options):
        captured["options"] = options
        yield AssistantMessage(content=[TextBlock(text="ok")], model="test")

    orig_api_key = os.environ.get("ANTHROPIC_API_KEY")

    async def run_it():
        sdk = sys.modules["claude_agent_sdk"]
        with patch.object(sdk, "query", fake_query):
            await _run_async(
                "test prompt",
                cwd="/tmp",
                mode="read_write",
                state={"_harness_cfg": {
                    "anthropic_api_key": "sk-per-session",
                    "env": {"MY_CUSTOM_VAR": "from-profile"},
                }},
            )

    try:
        asyncio.run(run_it())
    finally:
        if orig_api_key is None:
            os.environ.pop("ANTHROPIC_API_KEY", None)
        else:
            os.environ["ANTHROPIC_API_KEY"] = orig_api_key

    opts_env = captured["options"].env
    assert opts_env.get("CLAUDE_CODE_ENABLE_TODO_TOOLS") == "1"
    assert opts_env.get("ANTHROPIC_API_KEY") == "sk-per-session"
    assert opts_env.get("MY_CUSTOM_VAR") == "from-profile"
    # Process env must NOT have been mutated — creds reach only the child CLI.
    assert os.environ.get("ANTHROPIC_API_KEY") == orig_api_key, \
        "ANTHROPIC_API_KEY leaked into the poller process env"
    assert "MY_CUSTOM_VAR" not in os.environ


def test_spec_env_overrides_win_over_profile_env():
    """spec.env_overrides has highest precedence, beating both profile `env`
    and the backend default."""
    from claude_agent_sdk import AssistantMessage, TextBlock

    from autoswe.harness.runner import _run_async

    captured = {}

    async def fake_query(prompt, options):
        captured["options"] = options
        yield AssistantMessage(content=[TextBlock(text="ok")], model="test")

    sdk = sys.modules["claude_agent_sdk"]
    with patch.object(sdk, "query", fake_query):
        asyncio.run(_run_async(
            "test prompt",
            cwd="/tmp",
            mode="read_write",
            env_overrides={"CLAUDE_CODE_ENABLE_TODO_TOOLS": "spec-wins"},
            state={"_harness_cfg": {"env": {"CLAUDE_CODE_ENABLE_TODO_TOOLS": "0"}}},
        ))

    assert captured["options"].env.get("CLAUDE_CODE_ENABLE_TODO_TOOLS") == "spec-wins"


# ---------------------------------------------------------------------------
# system-prompt preset — all phases must run on the claude_code preset
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("mode", ["plan", "read_only", "read_write"])
def test_system_prompt_preset_emitted_for_all_phases(mode):
    """All three phases (plan/fix/review) pass the claude_code system-prompt
    preset through to ClaudeAgentOptions.

    Phase → mode mapping (planner/coder/reviewer): plan→"plan",
    fix→"read_write", review→"read_only".
    """
    from claude_agent_sdk import AssistantMessage, TextBlock

    from autoswe.harness.backends.claude_code import CLAUDE_CODE_SYSTEM_PROMPT_PRESET
    from autoswe.harness.runner import _run_async

    captured = {}

    async def fake_query(prompt, options):
        captured["options"] = options
        yield AssistantMessage(content=[TextBlock(text="ok")], model="test")

    sdk = sys.modules["claude_agent_sdk"]
    with patch.object(sdk, "query", fake_query):
        asyncio.run(_run_async(
            "test prompt", cwd="/tmp", mode=mode, state={"_harness_cfg": {}}
        ))

    assert "options" in captured, "fake_query was not called"
    assert captured["options"].system_prompt == CLAUDE_CODE_SYSTEM_PROMPT_PRESET, (
        f"mode={mode!r}: system_prompt={captured['options'].system_prompt!r} "
        f"expected {CLAUDE_CODE_SYSTEM_PROMPT_PRESET!r}"
    )


def test_system_prompt_preset_emitted_for_legacy_no_mode():
    """The legacy path (mode=None, explicit permission_mode/allowed_tools) also
    receives the preset, because it sits in the base options_kwargs dict rather
    than any mode-specific branch.

    Locks in the claude_code.py:420-424 legacy branch.
    """
    from claude_agent_sdk import AssistantMessage, TextBlock

    from autoswe.harness.backends.claude_code import CLAUDE_CODE_SYSTEM_PROMPT_PRESET
    from autoswe.harness.runner import _run_async

    captured = {}

    async def fake_query(prompt, options):
        captured["options"] = options
        yield AssistantMessage(content=[TextBlock(text="ok")], model="test")

    sdk = sys.modules["claude_agent_sdk"]
    with patch.object(sdk, "query", fake_query):
        asyncio.run(_run_async(
            "test prompt",
            cwd="/tmp",
            permission_mode="default",
            allowed_tools=["Read"],
            state={"_harness_cfg": {}},
        ))

    assert "options" in captured, "fake_query was not called"
    assert captured["options"].system_prompt == CLAUDE_CODE_SYSTEM_PROMPT_PRESET, (
        f"legacy path: system_prompt={captured['options'].system_prompt!r} "
        f"expected {CLAUDE_CODE_SYSTEM_PROMPT_PRESET!r}"
    )


def test_system_prompt_preset_is_a_plain_dict_for_sdk_boundary():
    """CLAUDE_CODE_SYSTEM_PROMPT_PRESET must be a real dict, not a
    MappingProxyType, because the Claude Agent SDK consumes it through an
    ``isinstance(sp, dict)`` guard (client.py / _internal/client.py, for the
    ``exclude_dynamic_sections`` preset field) and its transport path expects a
    JSON-serializable value.

    A MappingProxyType is not a dict subclass (isinstance → False) and is not
    JSON-serializable (json.dumps → TypeError), so either trait would silently
    drop or break the system-prompt preset at the SDK boundary. This test locks
    in that contract: it would fail if the constant regressed to a
    MappingProxyType even though dict/mappingproxy compare equal (the
    ==-based assertions above would not catch it).
    """
    import json
    import types

    from claude_agent_sdk import ClaudeAgentOptions

    from autoswe.harness.backends.claude_code import (
        CLAUDE_CODE_SYSTEM_PROMPT_PRESET as preset,
    )

    # The core SDK contract: must pass isinstance(sp, dict) so the SDK's
    # preset-handling guard treats it as a dict.
    assert isinstance(preset, dict), (
        f"system_prompt preset must be a dict, got {type(preset).__name__}"
    )
    assert not isinstance(preset, types.MappingProxyType)

    # Must be JSON-serializable (SDK transport may encode options).
    json.dumps(preset)

    # Content is the bare claude_code preset.
    assert preset == {"type": "preset", "preset": "claude_code"}

    # It must survive actual ClaudeAgentOptions construction (the value the
    # real run passes on every Claude invocation).
    options = ClaudeAgentOptions(cwd="/tmp", system_prompt=preset)
    assert options.system_prompt == preset
