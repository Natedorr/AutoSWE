"""Tests for autoswe.harness.backends.codex — CodexBackend via faked subprocess.

All tests mock ``subprocess.run`` to emit canned JSONL output.  No live
Codex calls are made.  The contract mirrors ``test_claude_runner.py`` and
``test_backend_base.py``: the same RunSpec → RunResult shape, just a
different backend.
"""
import json
import subprocess
from unittest.mock import Mock, patch

from autoswe.harness.backends.base import RunResult, RunSpec
from autoswe.harness.backends.codex import (
    CodexBackend,
    _mode_to_sandbox,
    _parse_jsonl_stream,
)

# ---------- Helpers ----------


def _jsonl(*events: dict) -> str:
    """Build a JSONL string from a sequence of event dicts."""
    return "\n".join(json.dumps(e) for e in events)


def _make_success_jsonl(
    thread_id: str = "thread-1",
    agent_text: str = "Fix applied successfully.",
    usage: dict | None = None,
) -> str:
    """Build a canonical success JSONL stream."""
    events = [
        {"type": "thread.started", "thread_id": thread_id},
        {"type": "turn.started"},
        {
            "type": "item.completed",
            "item": {
                "id": "item_1",
                "type": "agent_message",
                "text": agent_text,
            },
        },
    ]
    if usage is None:
        usage = {
            "input_tokens": 1000,
            "cached_input_tokens": 900,
            "output_tokens": 200,
            "reasoning_output_tokens": 0,
        }
    events.append({"type": "turn.completed", "usage": usage})
    return _jsonl(*events)


def _run_coro(backend, spec):
    """Helper: run a CodexBackend coroutine synchronously for testing."""
    import asyncio

    coro = backend.run(spec)
    try:
        return asyncio.run(coro)
    except RuntimeError as e:
        # "await" was used outside of running event loop — that's fine,
        # we used run_in_executor so it should work
        if "event loop" in str(e).lower():
            # Fallback: run the inner sync method directly
            return backend._run_sync(spec)
        raise


# ---------- Capabilities ----------


def test_codex_capabilities():
    """CodexBackend advertises resume and progress_stream only."""
    caps = CodexBackend.capabilities()
    assert "resume" in caps
    assert "progress_stream" in caps
    # Phase 4: no mcp, no can_use_tool, no plan_permission yet
    assert "mcp" not in caps
    assert "can_use_tool" not in caps
    assert "plan_permission" not in caps


def test_codex_capabilities_returns_copy():
    """capabilities() returns a copy, not the class-level set."""
    caps = CodexBackend.capabilities()
    assert caps is not CodexBackend.CAPABILITIES
    caps.add("fake")
    assert "fake" not in CodexBackend.capabilities()


# ---------- Protocol conformance ----------


def test_codex_satisfies_protocol():
    """CodexBackend should satisfy CodingBackend Protocol shape."""
    assert hasattr(CodexBackend, "capabilities")
    assert hasattr(CodexBackend, "run")
    assert callable(CodexBackend.capabilities)
    assert callable(CodexBackend.run)


def test_codex_run_returns_awaitable():
    """run(spec) should return an awaitable (coroutine)."""
    import asyncio

    backend = CodexBackend()
    spec = RunSpec(prompt="test", cwd="/tmp")
    result = backend.run(spec)
    assert asyncio.iscoroutine(result)
    result.close()


# ---------- Mode → sandbox mapping ----------


def test_mode_to_sandbox_plan():
    """mode='plan' → read-only sandbox."""
    assert _mode_to_sandbox("plan") == "read-only"


def test_mode_to_sandbox_read_only():
    """mode='read_only' → read-only sandbox."""
    assert _mode_to_sandbox("read_only") == "read-only"


def test_mode_to_sandbox_read_write():
    """mode='read_write' → workspace-write sandbox."""
    assert _mode_to_sandbox("read_write") == "workspace-write"


def test_mode_to_sandbox_none():
    """mode=None → read-only (safe default)."""
    assert _mode_to_sandbox(None) == "read-only"


def test_mode_to_sandbox_unknown():
    """Unknown mode → read-only (fail-safe)."""
    assert _mode_to_sandbox("unknown_mode") == "read-only"


# ---------- JSONL parser ----------


def test_parse_jsonl_basic():
    """Parse a minimal success stream."""
    jsonl = _jsonl(
        {"type": "thread.started", "thread_id": "t-42"},
        {"type": "turn.started"},
        {
            "type": "item.completed",
            "item": {"id": "i1", "type": "agent_message", "text": "Hello"},
        },
        {
            "type": "turn.completed",
            "usage": {
                "input_tokens": 100,
                "cached_input_tokens": 50,
                "output_tokens": 10,
                "reasoning_output_tokens": 0,
            },
        },
    )
    text, sid, cost, dur = _parse_jsonl_stream(jsonl)
    assert text == "Hello"
    assert sid == "t-42"
    assert cost is None  # Phase 4: no pricing yet
    assert dur >= 0


def test_parse_jsonl_multiple_agent_messages():
    """Multiple agent_message items are joined with newlines."""
    jsonl = _jsonl(
        {"type": "thread.started", "thread_id": "t-1"},
        {"type": "turn.started"},
        {
            "type": "item.completed",
            "item": {"id": "i1", "type": "agent_message", "text": "Part 1"},
        },
        {
            "type": "item.completed",
            "item": {"id": "i2", "type": "agent_message", "text": "Part 2"},
        },
        {
            "type": "turn.completed",
            "usage": {"input_tokens": 10, "output_tokens": 5},
        },
    )
    text, sid, _, _ = _parse_jsonl_stream(jsonl)
    assert text == "Part 1\nPart 2"
    assert sid == "t-1"


def test_parse_jsonl_empty_agent_text_ignored():
    """Agent messages with empty text are skipped."""
    jsonl = _jsonl(
        {"type": "thread.started", "thread_id": "t-1"},
        {"type": "turn.started"},
        {
            "type": "item.completed",
            "item": {"id": "i1", "type": "agent_message", "text": ""},
        },
        {
            "type": "item.completed",
            "item": {"id": "i2", "type": "agent_message", "text": "Real text"},
        },
        {
            "type": "turn.completed",
            "usage": {"input_tokens": 10, "output_tokens": 5},
        },
    )
    text, _, _, _ = _parse_jsonl_stream(jsonl)
    assert text == "Real text"


def test_parse_jsonl_non_json_lines_skipped():
    """Non-JSON lines (stderr leaks, progress) are skipped gracefully."""
    jsonl = (
        "some progress message\n"
        '{"type":"thread.started","thread_id":"t-1"}\n'
        "WARNING: something\n"
        '{"type":"turn.completed","usage":{"input_tokens":1,"output_tokens":1}}\n'
    )
    text, sid, _, _ = _parse_jsonl_stream(jsonl)
    assert sid == "t-1"
    assert text == ""


def test_parse_jsonl_turn_failed():
    """turn.failed event is logged but doesn't crash the parser."""
    jsonl = _jsonl(
        {"type": "thread.started", "thread_id": "t-1"},
        {"type": "turn.failed", "error": "Model not found"},
    )
    text, sid, _, _ = _parse_jsonl_stream(jsonl)
    assert sid == "t-1"
    assert text == ""


def test_parse_jsonl_error_event():
    """error event is logged but doesn't crash the parser."""
    jsonl = _jsonl(
        {"type": "thread.started", "thread_id": "t-1"},
        {"type": "error", "message": "Internal error"},
    )
    text, sid, _, _ = _parse_jsonl_stream(jsonl)
    assert sid == "t-1"


def test_parse_jsonl_no_thread_id():
    """Missing thread_id → session_id stays None."""
    jsonl = _jsonl(
        {"type": "thread.started"},
        {
            "type": "turn.completed",
            "usage": {"input_tokens": 1, "output_tokens": 1},
        },
    )
    _, sid, _, _ = _parse_jsonl_stream(jsonl)
    assert sid is None


# ---------- CodexBackend integration (mocked subprocess) ----------


def _mock_subprocess_run(returncode=0, stdout="", stderr=""):
    """Create a mock subprocess.run with the given output."""
    mock_result = Mock()
    mock_result.returncode = returncode
    mock_result.stdout = stdout
    mock_result.stderr = stderr
    return mock_result


def test_codex_basic_run():
    """Basic Codex run returns RunResult with parsed text and session_id."""
    backend = CodexBackend()
    spec = RunSpec(
        prompt="Fix the bug",
        cwd="/tmp/repo",
        model="gpt-5.4",
        mode="read_write",
    )

    jsonl = _make_success_jsonl(thread_id="sess-codex-1", agent_text="Bug fixed.")

    with patch("subprocess.run", return_value=_mock_subprocess_run(stdout=jsonl)):
        result = _run_coro(backend, spec)

    assert isinstance(result, RunResult)
    assert result.text == "Bug fixed."
    assert result.session_id == "sess-codex-1"
    assert result.subtype == "success"
    assert result.duration_seconds >= 0


def test_codex_run_calls_subprocess_with_correct_args():
    """CodexBackend builds the correct command-line for codex exec."""
    backend = CodexBackend()
    spec = RunSpec(
        prompt="Fix bug",
        cwd="/tmp/repo",
        model="gpt-5",
        mode="read_write",
        timeout=300,
    )

    jsonl = _make_success_jsonl()

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _mock_subprocess_run(stdout=jsonl)
        _run_coro(backend, spec)

    mock_run.assert_called_once()
    call_args = mock_run.call_args
    cmd = call_args[0][0] if call_args[0] else call_args[1].get("cmd", [])

    assert "codex" in cmd
    assert "exec" in cmd
    assert "--json" in cmd
    assert "--sandbox" in cmd
    assert "workspace-write" in cmd
    assert "--ask-for-approval" in cmd
    assert "never" in cmd
    assert "--model" in cmd
    assert "gpt-5" in cmd
    assert "--cd" in cmd
    assert "/tmp/repo" in cmd
    assert "Fix bug" in cmd


def test_codex_read_only_mode():
    """mode='read_only' produces --sandbox read-only."""
    backend = CodexBackend()
    spec = RunSpec(
        prompt="Review code",
        cwd="/tmp/repo",
        mode="read_only",
    )

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _mock_subprocess_run(
            stdout=_make_success_jsonl()
        )
        _run_coro(backend, spec)

    cmd = mock_run.call_args[0][0]
    assert cmd.count("--sandbox") == 1
    idx = cmd.index("--sandbox")
    assert cmd[idx + 1] == "read-only"


def test_codex_plan_mode():
    """mode='plan' produces --sandbox read-only."""
    backend = CodexBackend()
    spec = RunSpec(
        prompt="Plan the fix",
        cwd="/tmp/repo",
        mode="plan",
    )

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _mock_subprocess_run(
            stdout=_make_success_jsonl()
        )
        _run_coro(backend, spec)

    cmd = mock_run.call_args[0][0]
    idx = cmd.index("--sandbox")
    assert cmd[idx + 1] == "read-only"


def test_codex_resume_mode():
    """spec.resume produces 'codex exec resume <id>' command."""
    backend = CodexBackend()
    spec = RunSpec(
        prompt="Continue the fix",
        cwd="/tmp/repo",
        resume="sess-abc-123",
        mode="read_write",
    )

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _mock_subprocess_run(
            stdout=_make_success_jsonl()
        )
        _run_coro(backend, spec)

    cmd = mock_run.call_args[0][0]
    assert "resume" in cmd
    assert "sess-abc-123" in cmd


def test_codex_error_returncode():
    """Non-zero exit code → subtype='error'."""
    backend = CodexBackend()
    spec = RunSpec(prompt="Fix", cwd="/tmp", mode="read_write")

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _mock_subprocess_run(
            returncode=1,
            stdout="",
            stderr="Model not found",
        )
        result = _run_coro(backend, spec)

    assert result.subtype == "error"
    assert result.text == ""


def test_codex_timeout():
    """subprocess.TimeoutExpired is re-raised."""
    backend = CodexBackend()
    spec = RunSpec(prompt="Fix", cwd="/tmp", mode="read_write", timeout=60)

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="codex", timeout=60)

        import asyncio

        coro = backend.run(spec)
        try:
            asyncio.run(coro)
            assert False, "Should have raised TimeoutExpired"
        except subprocess.TimeoutExpired:
            pass  # expected


def test_codex_not_found():
    """FileNotFoundError → RuntimeError with install hint."""
    backend = CodexBackend()
    spec = RunSpec(prompt="Fix", cwd="/tmp", mode="read_write")

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = FileNotFoundError("codex")

        import asyncio

        coro = backend.run(spec)
        try:
            asyncio.run(coro)
            assert False, "Should have raised RuntimeError"
        except RuntimeError as e:
            assert "codex" in str(e).lower()
            assert "npm" in str(e)


def test_codex_default_model():
    """When spec.model is None, default to gpt-5.4."""
    backend = CodexBackend()
    spec = RunSpec(
        prompt="Fix",
        cwd="/tmp",
        model=None,
        mode="read_write",
    )

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _mock_subprocess_run(
            stdout=_make_success_jsonl()
        )
        _run_coro(backend, spec)

    cmd = mock_run.call_args[0][0]
    idx = cmd.index("--model")
    assert cmd[idx + 1] == "gpt-5.4"


def test_codex_env_openai_api_key_from_harness():
    """OPENAI_API_KEY from harness profile is passed to subprocess env."""
    backend = CodexBackend()
    spec = RunSpec(
        prompt="Fix",
        cwd="/tmp",
        mode="read_write",
        state={"_harness_cfg": {"openai_api_key": "sk-test-key-123"}},
    )

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _mock_subprocess_run(
            stdout=_make_success_jsonl()
        )
        _run_coro(backend, spec)

    # Check the env kwarg
    call_kwargs = mock_run.call_args[1]
    env = call_kwargs.get("env", {})
    assert env.get("OPENAI_API_KEY") == "sk-test-key-123"


def test_codex_env_codex_api_key_from_harness():
    """CODEX_API_KEY from harness profile takes precedence for codex auth."""
    backend = CodexBackend()
    spec = RunSpec(
        prompt="Fix",
        cwd="/tmp",
        mode="read_write",
        state={"_harness_cfg": {"codex_api_key": "csk-test-456"}},
    )

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _mock_subprocess_run(
            stdout=_make_success_jsonl()
        )
        _run_coro(backend, spec)

    call_kwargs = mock_run.call_args[1]
    env = call_kwargs.get("env", {})
    assert env.get("CODEX_API_KEY") == "csk-test-456"


def test_codex_env_overrides():
    """Explicit env_overrides are merged into subprocess env."""
    backend = CodexBackend()
    spec = RunSpec(
        prompt="Fix",
        cwd="/tmp",
        mode="read_write",
        env_overrides={"CUSTOM_VAR": "hello"},
    )

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _mock_subprocess_run(
            stdout=_make_success_jsonl()
        )
        _run_coro(backend, spec)

    call_kwargs = mock_run.call_args[1]
    env = call_kwargs.get("env", {})
    assert env.get("CUSTOM_VAR") == "hello"


def test_codex_progress_callback():
    """progress_callback is fired with completion summary."""
    backend = CodexBackend()
    callback = Mock()
    spec = RunSpec(
        prompt="Fix",
        cwd="/tmp",
        mode="read_write",
        progress_callback=callback,
    )

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _mock_subprocess_run(
            stdout=_make_success_jsonl(agent_text="Fix applied.")
        )
        _run_coro(backend, spec)

    callback.assert_called_once()
    assert "Completed" in callback.call_args[0][0]
    assert "chars" in callback.call_args[0][0]


def test_codex_progress_callback_no_text():
    """No progress callback fire when there's no text output."""
    backend = CodexBackend()
    callback = Mock()
    spec = RunSpec(
        prompt="Fix",
        cwd="/tmp",
        mode="read_write",
        progress_callback=callback,
    )

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _mock_subprocess_run(
            stdout=_make_success_jsonl(agent_text="")
        )
        _run_coro(backend, spec)

    callback.assert_not_called()


def test_codex_result_no_mcp_flags():
    """Phase 4: plan_posted and question_posted are always False."""
    backend = CodexBackend()
    spec = RunSpec(prompt="Plan", cwd="/tmp", mode="plan")

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _mock_subprocess_run(
            stdout=_make_success_jsonl()
        )
        result = _run_coro(backend, spec)

    assert result.plan_posted is False
    assert result.question_posted is False
    assert result.plan_file_path is None


# ---------- factory integration ----------


def test_factory_codex():
    """Factory returns CodexBackend for backend='codex'."""
    from autoswe.harness.backends.factory import get_backend

    backend = get_backend({"backend": "codex", "model": "gpt-5"})
    from autoswe.harness.backends.codex import CodexBackend

    assert isinstance(backend, CodexBackend)


def test_factory_codex_case_insensitive():
    """Factory accepts 'codex' in any case."""
    from autoswe.harness.backends.factory import get_backend

    for val in ("codex", "CODEX", "Codex"):
        backend = get_backend({"backend": val})
        from autoswe.harness.backends.codex import CodexBackend

        assert isinstance(backend, CodexBackend)


# ---------- backend_has_capability ----------


def test_backend_has_capability_codex():
    """backend_has_capability returns correct values for Codex."""
    from autoswe.harness.runner import backend_has_capability

    harness = {"backend": "codex"}
    assert backend_has_capability(harness, "resume")
    assert backend_has_capability(harness, "progress_stream")
    assert not backend_has_capability(harness, "mcp")
    assert not backend_has_capability(harness, "can_use_tool")
    assert not backend_has_capability(harness, "plan_permission")
    assert not backend_has_capability(harness, "mode")


# ---------- RunSpec → RunResult contract ----------


def test_codex_runresult_tuple_unpacking():
    """RunResult from Codex supports tuple unpacking (back-compat)."""
    backend = CodexBackend()
    spec = RunSpec(prompt="Fix", cwd="/tmp", mode="read_write")

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _mock_subprocess_run(
            stdout=_make_success_jsonl(
                thread_id="t-99", agent_text="Done"
            )
        )
        result = _run_coro(backend, spec)

    text, session_id, subtype = result
    assert text == "Done"
    assert session_id == "t-99"
    assert subtype == "success"
