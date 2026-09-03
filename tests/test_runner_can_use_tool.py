"""Tests for runner.py can_use_tool threading."""

import asyncio
import sys
from unittest.mock import MagicMock, patch

import pytest

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


def test_run_shares_state_dict_with_backend_when_harness_cfg_set():
    """Regression (issue #184): with harness_cfg, runner.run must hand the
    backend the SAME state dict the caller passed in.

    The AskUserQuestion callback writes state["asked_question_md"] and the
    backend's stream loop gates progress updates, the early break, and the
    final question re-assert on that key. The old code copied the dict, so
    the backend never saw the key — the agent kept running to the internal
    StructuredOutput tool, whose progress event clobbered the coalesced
    question in the sticky comment before drain() flushed it.
    """
    from autoswe.harness import runner as runner_mod
    from autoswe.harness.runner import RunResult

    captured = {}

    class StubBackend:
        def capabilities(self):
            return set()

        def retryable_subtypes(self):
            return set()

        def retryable_exceptions(self):
            return ()

        def run(self, spec):
            captured["spec"] = spec

            async def _done():
                return RunResult(text="ok", session_id="s", subtype="success")

            return _done()

    state = {"caller_key": True}
    harness_cfg = {"backend": "claude_code"}
    with patch(
        "autoswe.harness.backends.factory.get_backend", return_value=StubBackend()
    ):
        result = runner_mod.run(
            "test", cwd="/tmp", cfg={}, state=state, harness_cfg=harness_cfg,
        )

    assert result.text == "ok"
    spec = captured["spec"]
    # The backend must see the caller's dict, not a copy.
    assert spec.state is state
    # Threading _harness_cfg in place is safe (fresh dict per session).
    assert state["_harness_cfg"] is harness_cfg
    assert state["caller_key"] is True


def test_run_shares_state_dict_without_harness_cfg():
    """Without harness_cfg, the caller's state dict is passed through as-is."""
    from autoswe.harness import runner as runner_mod
    from autoswe.harness.runner import RunResult

    captured = {}

    class StubBackend:
        def capabilities(self):
            return set()

        def retryable_subtypes(self):
            return set()

        def retryable_exceptions(self):
            return ()

        def run(self, spec):
            captured["spec"] = spec

            async def _done():
                return RunResult(text="ok", session_id="s", subtype="success")

            return _done()

    state = {}
    with patch(
        "autoswe.harness.backends.factory.get_backend", return_value=StubBackend()
    ):
        # harness_cfg omitted → default backend path is NOT used; the factory
        # is still resolved via the default-None branch… runner.run without
        # harness_cfg constructs ClaudeCodeBackend directly, so patch that.
        with patch.object(runner_mod, "ClaudeCodeBackend", return_value=StubBackend()):
            runner_mod.run("test", cwd="/tmp", cfg={}, state=state)

    assert captured["spec"].state is state


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


# ---------------------------------------------------------------------------
# SDK CanUseToolShadowedWarning suppression (issue #190)
#
# The SDK emits an advisory warning whenever can_use_tool is registered
# alongside options that *statically* shadow it (bypassPermissions /
# whole-tool allow entries). That advisory is a false positive for autoSWE's
# configurations: the tool sets are pre-approved by design, and the CLI
# still routes user-interaction tools (AskUserQuestion) to the callback
# even under bypassPermissions — so the fixer's AskUserQuestion →
# autoswe:waiting path works. The backend filters the advisory instead of
# letting one warning line into poller.log per dispatch (verified live
# against CLI 2.1.252).
# ---------------------------------------------------------------------------


def _shadows_warning_leaked(rec) -> list:
    """Return the CanUseToolShadowedWarning entries in a recwarn-style list."""
    from claude_agent_sdk import CanUseToolShadowedWarning

    return [w for w in rec if issubclass(w.category, CanUseToolShadowedWarning)]


def test_shadow_suppressor_filters_advisory_when_enabled():
    """_can_use_tool_shadowing_suppressed(True) swallows the advisory."""
    import warnings

    from claude_agent_sdk import CanUseToolShadowedWarning

    from autoswe.harness.backends.claude_code import (
        _can_use_tool_shadowing_suppressed,
    )

    with warnings.catch_warnings(record=True) as rec:
        warnings.simplefilter("always")
        with _can_use_tool_shadowing_suppressed(True):
            warnings.warn("shadowed", CanUseToolShadowedWarning, stacklevel=2)
    assert not _shadows_warning_leaked(rec)


def test_shadow_suppressor_is_noop_when_disabled():
    """_can_use_tool_shadowing_suppressed(False) must not filter anything —
    guards against a process-wide ignore that would also swallow the
    advisory on legitimate (non-autoSWE) configurations."""
    import warnings

    from claude_agent_sdk import CanUseToolShadowedWarning

    from autoswe.harness.backends.claude_code import (
        _can_use_tool_shadowing_suppressed,
    )

    with warnings.catch_warnings(record=True) as rec:
        warnings.simplefilter("always")
        with _can_use_tool_shadowing_suppressed(False):
            warnings.warn("shadowed", CanUseToolShadowedWarning, stacklevel=2)
    assert _shadows_warning_leaked(rec)


@pytest.mark.parametrize("mode", ["plan", "read_write"])
def test_run_with_callback_does_not_leak_shadow_warning(mode):
    """issue #190: a backend run that registers can_use_tool must not let
    the SDK's CanUseToolShadowedWarning advisory escape into the log.

    The fake query emits the advisory the way the real client does (at
    connect / first iteration, computed from the options). The backend's
    filter must swallow it for every phase that registers a callback
    (plan, read_only, and read_write all do — planner/coder/reviewer).
    """
    import warnings

    from claude_agent_sdk import AssistantMessage, CanUseToolShadowedWarning, TextBlock

    from autoswe.harness.backends.claude_code import ClaudeCodeBackend
    from autoswe.harness.runner import RunSpec

    async def fake_callback(name, inp, ctx):
        from claude_agent_sdk import PermissionResultAllow
        return PermissionResultAllow(updated_input=inp)

    captured = {}

    async def fake_query(prompt, options):
        captured["options"] = options
        # Mimic the real client: the advisory fires lazily at connect,
        # before any message is yielded.
        if options.can_use_tool is not None:
            warnings.warn(
                "can_use_tool will not be invoked (fake advisory)",
                CanUseToolShadowedWarning,
                stacklevel=2,
            )
        yield AssistantMessage(content=[TextBlock(text="ok")], model="test")

    spec = RunSpec(
        prompt="test", cwd="/tmp", mode=mode, can_use_tool=fake_callback, state={},
    )
    sdk = sys.modules["claude_agent_sdk"]

    def run_it():
        with patch.object(sdk, "query", fake_query):
            with warnings.catch_warnings(record=True) as rec:
                warnings.simplefilter("always")
                asyncio.run(ClaudeCodeBackend()._run_async(spec))
            return rec

    rec = run_it()

    assert "options" in captured, "fake_query was not called"
    # The callback still reaches the SDK options unchanged — the filter
    # only silences the advisory, it does not drop the capability.
    assert captured["options"].can_use_tool is fake_callback
    leaked = _shadows_warning_leaked(rec)
    assert not leaked, f"mode={mode!r}: advisory escaped the backend: {leaked}"


def test_shadow_warning_still_surfaces_without_callback():
    """The suppression is scoped to callback-registered runs: without
    can_use_tool the helper is a no-op and the advisory passes through
    (guards against a blanket process-wide ignore)."""
    import warnings

    from claude_agent_sdk import AssistantMessage, CanUseToolShadowedWarning, TextBlock

    from autoswe.harness.backends.claude_code import ClaudeCodeBackend
    from autoswe.harness.runner import RunSpec

    async def fake_query(prompt, options):
        warnings.warn(
            "can_use_tool will not be invoked (fake advisory)",
            CanUseToolShadowedWarning,
            stacklevel=2,
        )
        yield AssistantMessage(content=[TextBlock(text="ok")], model="test")

    spec = RunSpec(prompt="test", cwd="/tmp", mode="read_write", state={})
    sdk = sys.modules["claude_agent_sdk"]

    def run_it():
        with patch.object(sdk, "query", fake_query):
            with warnings.catch_warnings(record=True) as rec:
                warnings.simplefilter("always")
                asyncio.run(ClaudeCodeBackend()._run_async(spec))
            return rec

    rec = run_it()
    assert _shadows_warning_leaked(rec), "advisory should surface without a callback"

