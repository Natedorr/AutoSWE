"""Tests for runner.py can_use_tool threading."""

import asyncio
import sys
from unittest.mock import MagicMock, patch

from autoswe.harness.runner import RunResult


def test_run_async_breaks_on_asked_question_md():
    """When state['asked_question_md'] is set mid-stream, the query loop should
    break early — preventing the agent from running more tools after posting a
    question. This is the fix for: agent kept going after AskUserQuestion,
    eventually crashing on git fetch of a non-existent branch."""
    from claude_agent_sdk import AssistantMessage, TextBlock

    from autoswe.harness.runner import _run_async

    state = {}
    tools_after_question = []

    async def fake_query(prompt, options):
        """Yield messages; track which ones were consumed."""
        yield AssistantMessage(content=[TextBlock(text="Thinking...")], model="test")
        yield AssistantMessage(content=[TextBlock(text="About to ask...")], model="test")
        yield AssistantMessage(content=[TextBlock(text="Question posted")], model="test")
        state["asked_question_md"] = "## Questions\n\nTest question?"
        # These messages should NOT be consumed after the break:
        yield AssistantMessage(content=[TextBlock(text="Running git fetch...")], model="test")
        tools_after_question.append("git_fetch")
        msg = MagicMock()
        msg.session_id = "test-session"
        msg.subtype = "success"
        msg.total_cost_usd = 0.01
        msg.duration_ms = 5000
        yield msg

    async def fake_callback(name, inp, ctx):
        from claude_agent_sdk import PermissionResultAllow
        return PermissionResultAllow(updated_input=inp)

    async def run_it():
        # _run_async imports `query` via `from claude_agent_sdk import query`
        # inside the function body, so we patch on the SDK module itself.
        sdk = sys.modules["claude_agent_sdk"]
        with patch.object(sdk, "query", fake_query):
            result = await _run_async(
                "test prompt",
                cwd="/tmp",
                permission_mode="default",
                allowed_tools=["Read", "AskUserQuestion"],
                can_use_tool=fake_callback,
                state=state,
            )
            return result

    result = asyncio.run(run_it())

    # The loop should have broken before consuming the post-question messages
    assert not tools_after_question, (
        "The query loop did not break early — agent continued running tools "
        "after AskUserQuestion was posted"
    )
    # We should still get a valid RunResult
    assert isinstance(result, RunResult)
    assert "Thinking" in result.text or "Question" in result.text


def test_run_accepts_can_use_tool_param():
    """run() should accept can_use_tool and state parameters without error."""
    import inspect

    from autoswe.harness.runner import run

    sig = inspect.signature(run)
    params = list(sig.parameters.keys())
    assert "can_use_tool" in params
    assert "state" in params


def test_run_threads_can_use_tool():
    """When can_use_tool is provided, it is threaded through to _run_async."""
    cfg = {"AGENT_TIMEOUT": 7200, "CLAUDE_CLI_PATH": ""}

    with patch.object(asyncio, "run") as mock_run:
        def fake_run(coro):
            coro.close()
            from autoswe.harness.runner import RunResult
            return RunResult(text="", session_id="s1", subtype="success")
        mock_run.side_effect = fake_run

        from autoswe.harness.runner import run

        def fake_callback(name, inp, ctx):
            pass

        state = {}
        run("test", cwd="/tmp", cfg=cfg, can_use_tool=fake_callback, state=state)

    assert mock_run.called


def test_run_no_can_use_tool_back_compat():
    """When can_use_tool is absent, run() should work as before."""
    cfg = {"AGENT_TIMEOUT": 7200, "CLAUDE_CLI_PATH": ""}

    with patch.object(asyncio, "run") as mock_run:
        def fake_run(coro):
            coro.close()
            from autoswe.harness.runner import RunResult
            return RunResult(text="ok", session_id="s1", subtype="success")
        mock_run.side_effect = fake_run

        from autoswe.harness.runner import run
        result = run("test prompt", cwd="/tmp", cfg=cfg)

    assert mock_run.called
    assert result.text == "ok"


def test_run_result_back_compat():
    """RunResult should support tuple unpacking for back-compat callers."""
    from autoswe.harness.runner import RunResult

    result = RunResult(text="hello", session_id="s1", subtype="success")
    text, session_id, subtype = result
    assert text == "hello"
    assert session_id == "s1"
    assert subtype == "success"
