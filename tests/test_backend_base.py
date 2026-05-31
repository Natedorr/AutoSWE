"""Tests for the harness backend abstraction (Phase 1).

Verifies:
- ClaudeCodeBackend satisfies the CodingBackend Protocol.
- RunSpec dataclass carries all expected fields.
- RunResult re-exported from both runner.py and backends/base.py.
- runner.run() delegates to ClaudeCodeBackend and returns a RunResult.
- Backward-compatible re-exports (PROGRESS_TOOLS, AGENT_TASK_TOOLS,
  HandlerResult, ProgressState, _run_async, _extract_plan_file_path).
"""

import asyncio
from unittest.mock import patch

# ---------- CodingBackend Protocol conformance ----------


def test_claude_code_backend_has_capabilities():
    """ClaudeCodeBackend must implement capabilities() classmethod."""
    from autoswe.harness.backends.claude_code import ClaudeCodeBackend

    caps = ClaudeCodeBackend.capabilities()
    assert isinstance(caps, set)
    assert "mcp" in caps
    assert "can_use_tool" in caps
    assert "resume" in caps
    assert "progress_stream" in caps


def test_claude_code_backend_has_run_method():
    """ClaudeCodeBackend must have a run(spec) method returning an awaitable."""
    from autoswe.harness.backends.base import RunSpec
    from autoswe.harness.backends.claude_code import ClaudeCodeBackend

    backend = ClaudeCodeBackend()
    spec = RunSpec(prompt="test", cwd="/tmp")
    result = backend.run(spec)
    # Should return an awaitable (coroutine)
    assert asyncio.iscoroutine(result)
    # Clean up to avoid GC warnings
    if asyncio.iscoroutine(result):
        result.close()


def test_claude_code_backend_satisfies_protocol():
    """ClaudeCodeBackend should satisfy CodingBackend Protocol shape."""

    from autoswe.harness.backends.claude_code import ClaudeCodeBackend

    # Check the required methods exist
    assert hasattr(ClaudeCodeBackend, "capabilities")
    assert hasattr(ClaudeCodeBackend, "run")
    assert callable(ClaudeCodeBackend.capabilities)
    assert callable(ClaudeCodeBackend.run)


# ---------- RunSpec dataclass ----------


def test_run_spec_required_fields():
    """RunSpec requires prompt and cwd."""
    from autoswe.harness.backends.base import RunSpec

    spec = RunSpec(prompt="hello", cwd="/tmp")
    assert spec.prompt == "hello"
    assert spec.cwd == "/tmp"


def test_run_spec_defaults():
    """RunSpec optional fields have expected defaults."""
    from autoswe.harness.backends.base import RunSpec

    spec = RunSpec(prompt="p", cwd="/tmp")
    assert spec.model is None
    assert spec.resume is None
    # Phase 3: mode-based fields
    assert spec.mode is None
    assert spec.extra_tools is None
    assert spec.disallowed_tools_override is None
    # Legacy fields
    assert spec.permission_mode == "default"
    assert spec.allowed_tools is None
    assert spec.disallowed_tools is None
    assert spec.max_turns == 200
    assert spec.timeout == 7200
    assert spec.cli_path is None
    assert spec.env_overrides is None
    assert spec.mcp_servers is None
    assert spec.can_use_tool is None
    assert spec.progress_callback is None
    assert spec.state is None


def test_run_spec_custom_values():
    """RunSpec accepts all override values."""
    from autoswe.harness.backends.base import RunSpec

    spec = RunSpec(
        prompt="p",
        cwd="/cwd",
        model="custom-model",
        resume="sess-123",
        permission_mode="bypassPermissions",
        allowed_tools=["Read", "Edit"],
        disallowed_tools=["ExitPlanMode"],
        max_turns=100,
        timeout=3600,
        cli_path="/usr/bin/claude",
        env_overrides={"KEY": "val"},
        mcp_servers={"srv": {}},
        state={"key": "val"},
    )
    assert spec.model == "custom-model"
    assert spec.resume == "sess-123"
    assert spec.permission_mode == "bypassPermissions"
    assert spec.allowed_tools == ["Read", "Edit"]
    assert spec.disallowed_tools == ["ExitPlanMode"]
    assert spec.max_turns == 100
    assert spec.timeout == 3600
    assert spec.env_overrides == {"KEY": "val"}


# ---------- Re-export backward compatibility ----------


def test_run_result_reexport_from_runner():
    """RunResult must be importable from runner.py for backward compatibility."""
    from autoswe.harness.runner import RunResult

    result = RunResult(text="t", session_id="s", subtype="success")
    assert result.text == "t"
    assert result.session_id == "s"


def test_run_result_reexport_from_backends():
    """RunResult must be importable from backends.base."""
    from autoswe.harness.backends.base import RunResult

    result = RunResult(text="x", session_id=None, subtype=None)
    assert result.text == "x"


def test_handler_result_reexport_from_runner():
    """HandlerResult must be importable from runner.py."""
    from autoswe.harness.runner import HandlerResult

    hr = HandlerResult(done_content="PLAN_READY")
    assert hr.done_content == "PLAN_READY"


def test_progress_tools_reexport():
    """PROGRESS_TOOLS must be importable from runner.py."""
    from autoswe.harness.runner import PROGRESS_TOOLS

    assert "TodoWrite" in PROGRESS_TOOLS
    assert "TaskCreate" in PROGRESS_TOOLS


def test_agent_task_tools_reexport():
    """AGENT_TASK_TOOLS must be importable from runner.py."""
    from autoswe.harness.runner import AGENT_TASK_TOOLS

    assert "Agent" in AGENT_TASK_TOOLS
    assert "TodoWrite" in AGENT_TASK_TOOLS


def test_progress_state_reexport():
    """ProgressState must be importable from runner.py."""
    from autoswe.harness.runner import ProgressState

    ps = ProgressState()
    assert ps.todos is None


def test_parse_task_id_reexport():
    """_parse_task_id must be importable from runner.py."""
    from autoswe.harness.runner import _parse_task_id

    assert callable(_parse_task_id)


def test_extract_plan_file_path_reexport():
    """_extract_plan_file_path must be importable from runner.py."""
    from autoswe.harness.runner import _extract_plan_file_path

    assert callable(_extract_plan_file_path)


def test_run_async_reexport():
    """_run_async must be importable from runner.py for test code."""
    from autoswe.harness.runner import _run_async

    assert callable(_run_async)
    # Should be an async function
    import inspect
    assert inspect.iscoroutinefunction(_run_async)


# ---------- runner.run() delegates to backend ----------


def test_run_returns_run_result():
    """runner.run() must return a RunResult dataclass."""
    from autoswe.harness.runner import RunResult, run

    cfg = {"AGENT_TIMEOUT": 7200, "CLAUDE_CLI_PATH": ""}

    with patch.object(asyncio, "run") as mock_run:
        def fake_run(coro):
            coro.close()
            return RunResult(text="ok", session_id="s1", subtype="success")
        mock_run.side_effect = fake_run

        result = run("test prompt", cwd="/tmp", cfg=cfg)

    assert mock_run.called
    assert isinstance(result, RunResult)
    assert result.text == "ok"


def test_run_builds_run_spec():
    """runner.run() should build a RunSpec with resolved parameters."""
    from autoswe.harness.runner import run

    cfg = {
        "AGENT_TIMEOUT": 7200,
        "AGENT_RETRY_ON_FAILURE": 0,
        "ANTHROPIC_BASE_URL": "http://localhost:11434",
        "ANTHROPIC_AUTH_TOKEN": "",
        "ANTHROPIC_API_KEY": "test-key",
        "CLAUDE_CLI_PATH": "",
    }
    repo_cfg = {"model": "repo-model"}

    with patch.object(asyncio, "run") as mock_run:
        def fake_run(coro):
            coro.close()
            return ("t", "s", "success")
        mock_run.side_effect = fake_run

        run("p", cwd="/tmp", cfg=cfg, repo_cfg=repo_cfg)

    assert mock_run.called


def test_run_tuple_unpacking_still_works():
    """Back-compat: text, session_id, subtype = runner.run(...) must work."""
    from autoswe.harness.runner import RunResult, run

    cfg = {"AGENT_TIMEOUT": 7200, "CLAUDE_CLI_PATH": ""}

    with patch.object(asyncio, "run") as mock_run:
        def fake_run(coro):
            coro.close()
            return RunResult(text="hello", session_id="s1", subtype="success")
        mock_run.side_effect = fake_run

        result = run("test", cwd="/tmp", cfg=cfg)
        text, session_id, subtype = result

    assert text == "hello"
    assert session_id == "s1"
    assert subtype == "success"


# ---------- backends.__init__ convenience imports ----------


def test_backends_init_reexports():
    """backends.__init__ should re-export core types."""
    from autoswe.harness.backends import (
        AGENT_TASK_TOOLS,
        PROGRESS_TOOLS,
        HandlerResult,
        RunResult,
        RunSpec,
    )

    # Smoke test: all are callable/class types
    assert isinstance(RunResult(text="t", session_id=None, subtype=None), RunResult)
    assert isinstance(RunSpec(prompt="p", cwd="/c"), RunSpec)
    assert isinstance(HandlerResult(done_content="d"), HandlerResult)
    assert isinstance(PROGRESS_TOOLS, list)
    assert isinstance(AGENT_TASK_TOOLS, list)
