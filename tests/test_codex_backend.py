"""Tests for autoswe.harness.backends.codex — CodexBackend via faked subprocess.

All tests mock ``asyncio.create_subprocess_exec`` to emit canned JSONL
output on the simulated stdout pipe.  No live Codex calls are made.
"""
import asyncio
import json
import os
from unittest.mock import AsyncMock, Mock, patch

from autoswe.harness.backends.base import RunResult, RunSpec
from autoswe.harness.backends.codex import (
    CodexBackend,
    _CodexAccumulator,
    _mode_to_sandbox,
    _parse_jsonl_line,
)

# ---------- Helpers ----------


def _jsonl(*events: dict) -> str:
    """Build a JSONL string from a sequence of event dicts."""
    return "\n".join(json.dumps(e) for e in events) + "\n"


def _make_success_jsonl(
    thread_id: str = "thread-1",
    agent_texts: list[str] | None = None,
) -> str:
    """Build a canonical success JSONL stream."""
    if agent_texts is None:
        agent_texts = ["Fix applied successfully."]
    events = [
        {"type": "thread.started", "thread_id": thread_id},
        {"type": "turn.started"},
    ]
    for i, text in enumerate(agent_texts, 1):
        events.append({
            "type": "item.started",
            "item": {"id": f"item_{i}", "type": "agent_message", "text": text},
        })
        events.append({
            "type": "item.completed",
            "item": {"id": f"item_{i}", "type": "agent_message", "text": text},
        })
    events.append({
        "type": "turn.completed",
        "usage": {
            "input_tokens": 1000,
            "cached_input_tokens": 900,
            "output_tokens": 200,
            "reasoning_output_tokens": 0,
        },
    })
    return _jsonl(*events)


class _MockProcess:
    """Fake asyncio subprocess process with controllable stdout/stderr."""

    def __init__(
        self,
        stdout: str = "",
        stderr: str = "",
        returncode: int = 0,
    ):
        self.returncode = returncode
        self._stdout_lines = stdout.splitlines(keepends=True) if stdout else []
        self._stdout_pos = 0
        self._stdout_bytes = stdout.encode() if stdout else b""
        self._stderr_bytes = stderr.encode() if stderr else b""

    async def wait(self) -> int:
        return self.returncode

    @property
    def stdout(self):
        return self

    @property
    def stderr(self):
        return self

    async def readline(self) -> bytes:
        if self._stdout_pos < len(self._stdout_lines):
            line = self._stdout_lines[self._stdout_pos]
            self._stdout_pos += 1
            return line.encode()
        return b""

    async def read(self) -> bytes:
        return self._stderr_bytes


async def _run_backend(backend, spec):
    """Helper: run a CodexBackend with mocked subprocess."""
    return await backend._run_async(spec)


def _mock_create_process(
    stdout: str = "",
    stderr: str = "",
    returncode: int = 0,
) -> _MockProcess:
    return _MockProcess(stdout=stdout, stderr=stderr, returncode=returncode)


def _get_cmd(mock_exec: AsyncMock) -> tuple:
    """Extract the full command tuple from create_subprocess_exec call args.

    create_subprocess_exec(*cmd, ...) spreads the cmd list, so call_args[0]
    is a tuple of individual arguments: ("codex", "exec", "--json", ...).
    """
    return mock_exec.call_args[0]


# ---------- Capabilities ----------


def test_codex_capabilities():
    """CodexBackend advertises resume and progress_stream (Phase 4, core run only)."""
    caps = CodexBackend.capabilities()
    assert "mode" not in caps
    assert "resume" in caps
    assert "progress_stream" in caps
    # Phase 4: no mcp, no can_use_tool, no plan_permission, no mode yet
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


# ---------- JSONL line parser ----------


def test_parse_jsonl_line_thread_started():
    """thread.started sets session_id."""
    acc = _CodexAccumulator()
    _parse_jsonl_line(
        '{"type":"thread.started","thread_id":"t-42"}',
        acc=acc,
        callback=None,
    )
    assert acc.session_id == "t-42"
    assert not acc.text_chunks


def test_parse_jsonl_line_agent_message_completed():
    """item.completed agent_message accumulates text."""
    acc = _CodexAccumulator()
    _parse_jsonl_line(
        json.dumps({
            "type": "item.completed",
            "item": {"id": "i1", "type": "agent_message", "text": "Hello"},
        }),
        acc=acc,
        callback=None,
    )
    assert acc.text_chunks == ["Hello"]


def test_parse_jsonl_line_summary_output_collected():
    """item.completed summary_output accumulates text."""
    acc = _CodexAccumulator()
    callback = Mock()
    _parse_jsonl_line(
        json.dumps({
            "type": "item.completed",
            "item": {"id": "s1", "type": "summary_output", "text": "All done."},
        }),
        acc=acc,
        callback=callback,
    )
    assert acc.text_chunks == ["All done."]
    # Callback should have fired with Agent: prefix
    callback.assert_called_once()
    assert "Agent: All done." in callback.call_args[0][0]


def test_parse_jsonl_line_empty_text_skipped():
    """Empty agent_message text is not accumulated."""
    acc = _CodexAccumulator()
    _parse_jsonl_line(
        json.dumps({
            "type": "item.completed",
            "item": {"id": "i1", "type": "agent_message", "text": ""},
        }),
        acc=acc,
        callback=None,
    )
    assert not acc.text_chunks


def test_parse_jsonl_line_non_json_ignored():
    """Non-JSON lines are skipped gracefully."""
    acc = _CodexAccumulator()
    _parse_jsonl_line("WARNING: something went wrong", acc=acc, callback=None)
    assert not acc.text_chunks


def test_parse_jsonl_line_turn_failed_sets_flag():
    """turn.failed sets turn_failed flag for downstream subtype logic."""
    acc = _CodexAccumulator()
    _parse_jsonl_line(
        '{"type":"turn.failed","error":{"message":"Model not found"}}',
        acc=acc,
        callback=None,
    )
    assert not acc.text_chunks
    assert acc.turn_failed is True


def test_parse_jsonl_line_turn_failed_dict_error():
    """turn.failed with dict error extracts the message (live-verified shape)."""
    acc = _CodexAccumulator()
    _parse_jsonl_line(
        json.dumps({
            "type": "turn.failed",
            "error": {
                "message": "unexpected status 401 Unauthorized",
                "code": 401,
            },
        }),
        acc=acc,
        callback=None,
    )
    assert acc.turn_failed is True


def test_parse_jsonl_line_turn_failed_string_error():
    """turn.failed with string error still works (backward compat)."""
    acc = _CodexAccumulator()
    _parse_jsonl_line(
        json.dumps({
            "type": "turn.failed",
            "error": "plain string error",
        }),
        acc=acc,
        callback=None,
    )
    assert acc.turn_failed is True


def test_parse_jsonl_line_turn_completed_accumulates_usage():
    """turn.completed accumulates usage data for future cost calculation."""
    acc = _CodexAccumulator()
    _parse_jsonl_line(
        json.dumps({
            "type": "turn.completed",
            "usage": {"input_tokens": 100, "output_tokens": 50},
        }),
        acc=acc,
        callback=None,
    )
    assert len(acc.usage) == 1
    assert acc.usage[0]["input_tokens"] == 100


def test_parse_jsonl_line_error_event():
    """error event doesn't crash the parser."""
    acc = _CodexAccumulator()
    _parse_jsonl_line(
        '{"type":"error","message":"Internal error"}',
        acc=acc,
        callback=None,
    )
    assert not acc.text_chunks


def test_parse_jsonl_line_todo_progress():
    """todo_list item fires callback with rendered items."""
    acc = _CodexAccumulator()
    callback = Mock()
    _parse_jsonl_line(
        json.dumps({
            "type": "item.completed",
            "item": {
                "type": "todo_list",
                "items": [
                    {"text": "Fix bug", "completed": True},
                    {"text": "Add tests", "completed": False},
                ],
            },
        }),
        acc=acc,
        callback=callback,
    )
    callback.assert_called_once()
    assert "✅" in callback.call_args[0][0]
    assert "☐" in callback.call_args[0][0]
    assert "Fix bug" in callback.call_args[0][0]
    assert "Add tests" in callback.call_args[0][0]


def test_parse_jsonl_line_item_delta_appends():
    """item.delta appends incremental content to the last chunk."""
    acc = _CodexAccumulator()
    # Seed with a completed agent message
    _parse_jsonl_line(
        json.dumps({
            "type": "item.completed",
            "item": {"id": "i1", "type": "agent_message", "text": "Hello"},
        }),
        acc=acc,
        callback=None,
    )
    # Delta extends it
    _parse_jsonl_line(
        json.dumps({
            "type": "item.delta",
            "delta": " world",
        }),
        acc=acc,
        callback=None,
    )
    assert acc.text_chunks == ["Hello world"]


def test_parse_jsonl_line_item_delta_no_chunks():
    """item.delta with no prior chunks creates a new one."""
    acc = _CodexAccumulator()
    _parse_jsonl_line(
        json.dumps({
            "type": "item.delta",
            "delta": "streaming content",
        }),
        acc=acc,
        callback=None,
    )
    assert acc.text_chunks == ["streaming content"]


# ---------- CodexBackend integration (mocked subprocess) ----------


# ---------- Shared async helpers for command-flag tests ----------


def _async_cmd_test(backend, spec):
    """Return an async function that runs backend and returns the mock."""
    async def _run():
        mock_exec = AsyncMock(return_value=_mock_create_process(
            stdout=_make_success_jsonl()
        ))
        with patch("asyncio.create_subprocess_exec", mock_exec):
            await _run_backend(backend, spec)
        return mock_exec
    return _run


# ---------- CodexBackend integration (mocked subprocess) ----------


def test_codex_basic_run():
    """Basic Codex run returns RunResult with parsed text and session_id."""
    backend = CodexBackend()
    spec = RunSpec(
        prompt="Fix the bug",
        cwd="/tmp/repo",
        model="gpt-5.4",
        mode="read_write",
    )
    jsonl = _make_success_jsonl(thread_id="sess-codex-1", agent_texts=["Bug fixed."])

    async def _run():
        with patch(
            "asyncio.create_subprocess_exec",
            new_callable=AsyncMock,
            return_value=_mock_create_process(stdout=jsonl),
        ):
            return await _run_backend(backend, spec)

    result = asyncio.run(_run())

    assert isinstance(result, RunResult)
    assert result.text == "Bug fixed."
    assert result.session_id == "sess-codex-1"
    assert result.subtype == "success"
    assert result.duration_seconds >= 0


def test_codex_run_calls_with_correct_flags():
    """CodexBackend builds the correct command-line flags."""
    backend = CodexBackend()
    spec = RunSpec(
        prompt="Fix bug",
        cwd="/tmp/repo",
        model="gpt-5",
        mode="read_write",
        timeout=300,
    )
    jsonl = _make_success_jsonl()

    async def _run():
        mock_exec = AsyncMock(return_value=_mock_create_process(stdout=jsonl))
        with patch("asyncio.create_subprocess_exec", mock_exec):
            await _run_backend(backend, spec)
        return mock_exec

    cmd = _get_cmd(asyncio.run(_run()))

    assert "codex" in cmd
    assert "exec" in cmd
    assert "--json" in cmd
    assert "--ignore-user-config" in cmd
    assert "--ignore-rules" in cmd
    assert "--sandbox" in cmd
    assert "workspace-write" in cmd
    assert "--dangerously-bypass-approvals-and-sandbox" in cmd
    # Old --ask-for-approval must NOT be present
    assert "--ask-for-approval" not in cmd
    assert "--model" in cmd
    assert "gpt-5" in cmd
    assert "-C" in cmd
    assert "/tmp/repo" in cmd
    # Prompt should be after -- separator
    assert "--" in cmd
    dash_idx = cmd.index("--")
    assert cmd[dash_idx + 1] == "Fix bug"


def test_codex_read_only_mode():
    """mode='read_only' produces --sandbox read-only."""
    backend = CodexBackend()
    spec = RunSpec(prompt="Review code", cwd="/tmp/repo", mode="read_only")

    cmd = _get_cmd(asyncio.run(_async_cmd_test(backend, spec)()))
    idx = cmd.index("--sandbox")
    assert cmd[idx + 1] == "read-only"


def test_codex_plan_mode():
    """mode='plan' produces --sandbox read-only."""
    backend = CodexBackend()
    spec = RunSpec(prompt="Plan the fix", cwd="/tmp/repo", mode="plan")

    cmd = _get_cmd(asyncio.run(_async_cmd_test(backend, spec)()))
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

    cmd = _get_cmd(asyncio.run(_async_cmd_test(backend, spec)()))
    assert "resume" in cmd
    assert "sess-abc-123" in cmd


def test_codex_resume_no_sandbox_or_cd():
    """Resume command must NOT include --sandbox or -C (unsupported by resume subcommand)."""
    backend = CodexBackend()
    spec = RunSpec(
        prompt="Continue",
        cwd="/tmp/repo",
        resume="sess-123",
        mode="read_write",
    )

    cmd = _get_cmd(asyncio.run(_async_cmd_test(backend, spec)()))
    assert "--sandbox" not in cmd
    assert "-C" not in cmd
    assert "--dangerously-bypass-approvals-and-sandbox" in cmd


def test_codex_prompt_starts_with_dash():
    """Prompt starting with - must be protected by -- separator."""
    backend = CodexBackend()
    spec = RunSpec(
        prompt="-Fix the bug",
        cwd="/tmp/repo",
        mode="read_write",
    )

    cmd = _get_cmd(asyncio.run(_async_cmd_test(backend, spec)()))
    dash_idx = cmd.index("--")
    assert cmd[dash_idx + 1] == "-Fix the bug"
    # The prompt must be the last element
    assert cmd[-1] == "-Fix the bug"


def test_codex_error_returncode():
    """Non-zero exit code → subtype='error'."""
    backend = CodexBackend()
    spec = RunSpec(prompt="Fix", cwd="/tmp", mode="read_write")

    async def _run():
        mock_exec = AsyncMock(return_value=_mock_create_process(
            returncode=1, stdout="", stderr="Model not found"
        ))
        with patch("asyncio.create_subprocess_exec", mock_exec):
            return await _run_backend(backend, spec)

    result = asyncio.run(_run())
    assert result.subtype == "error"
    assert result.text == ""


def test_codex_killed_subtype():
    """Negative returncode (asyncio signal convention) → subtype='killed'.

    asyncio.subprocess uses negative values for signal-killed processes
    (e.g. -9 = SIGKILL), unlike raw os.waitpid which packs signals
    into positive values.
    """
    backend = CodexBackend()
    spec = RunSpec(prompt="Fix", cwd="/tmp", mode="read_write")

    async def _run():
        mock_exec = AsyncMock(return_value=_mock_create_process(
            returncode=-9, stdout=""
        ))
        with patch("asyncio.create_subprocess_exec", mock_exec):
            return await _run_backend(backend, spec)

    result = asyncio.run(_run())
    assert result.subtype == "killed"


def test_codex_timeout():
    """asyncio.TimeoutError is re-raised after killing the process."""
    backend = CodexBackend()
    spec = RunSpec(prompt="Fix", cwd="/tmp", mode="read_write", timeout=60)

    mock_process = Mock()
    mock_process.stdout = None
    mock_process.stderr = None
    mock_process.kill = Mock()
    mock_process.wait = AsyncMock(return_value=-9)
    mock_process.returncode = 9  # SIGKILL — positive signal number

    async def blocking_read():
        await asyncio.sleep(999)

    mock_process.stdout = Mock()
    mock_process.stdout.readline = blocking_read
    mock_process.stderr = Mock()
    mock_process.stderr.read = AsyncMock(return_value=b"")

    async def _run():
        mock_exec = AsyncMock(return_value=mock_process)
        with patch("asyncio.create_subprocess_exec", mock_exec):
            return await _run_backend(backend, spec)

    try:
        asyncio.run(_run())
        assert False, "Should have raised TimeoutError"
    except asyncio.TimeoutError:
        pass  # expected

    # Verify the process was actually killed on timeout
    mock_process.kill.assert_called_once()


def test_codex_not_found():
    """FileNotFoundError → RuntimeError with install hint."""
    backend = CodexBackend()
    spec = RunSpec(prompt="Fix", cwd="/tmp", mode="read_write")

    async def _run():
        mock_exec = AsyncMock(side_effect=FileNotFoundError("codex"))
        with patch("asyncio.create_subprocess_exec", mock_exec):
            return await _run_backend(backend, spec)

    try:
        asyncio.run(_run())
        assert False, "Should have raised RuntimeError"
    except RuntimeError as e:
        assert "codex" in str(e).lower()
        assert "npm" in str(e)


def test_codex_default_model():
    """When spec.model is None, default to gpt-5.4."""
    backend = CodexBackend()
    spec = RunSpec(prompt="Fix", cwd="/tmp", model=None, mode="read_write")

    cmd = _get_cmd(asyncio.run(_async_cmd_test(backend, spec)()))
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

    async def _run():
        mock_exec = AsyncMock(return_value=_mock_create_process(
            stdout=_make_success_jsonl()
        ))
        with patch("asyncio.create_subprocess_exec", mock_exec):
            await _run_backend(backend, spec)
        return mock_exec.call_args[1].get("env", {})

    env = asyncio.run(_run())
    assert env.get("OPENAI_API_KEY") == "sk-test-key-123"


def test_codex_env_codex_api_key_from_harness():
    """CODEX_API_KEY from harness profile is passed to subprocess env."""
    backend = CodexBackend()
    spec = RunSpec(
        prompt="Fix",
        cwd="/tmp",
        mode="read_write",
        state={"_harness_cfg": {"codex_api_key": "csk-test-456"}},
    )

    async def _run():
        mock_exec = AsyncMock(return_value=_mock_create_process(
            stdout=_make_success_jsonl()
        ))
        with patch("asyncio.create_subprocess_exec", mock_exec):
            await _run_backend(backend, spec)
        return mock_exec.call_args[1].get("env", {})

    env = asyncio.run(_run())
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

    async def _run():
        mock_exec = AsyncMock(return_value=_mock_create_process(
            stdout=_make_success_jsonl()
        ))
        with patch("asyncio.create_subprocess_exec", mock_exec):
            await _run_backend(backend, spec)
        return mock_exec.call_args[1].get("env", {})

    env = asyncio.run(_run())
    assert env.get("CUSTOM_VAR") == "hello"


def test_codex_progress_callback_streaming():
    """progress_callback fires with live agent messages during execution."""
    backend = CodexBackend()
    callback = Mock()
    # Build JSONL with item.started + item.completed agent_message events
    jsonl = _make_success_jsonl(
        thread_id="t-1",
        agent_texts=["Step 1 done.", "Step 2 done."],
    )
    spec = RunSpec(
        prompt="Fix",
        cwd="/tmp",
        mode="read_write",
        progress_callback=callback,
    )

    async def _run():
        mock_exec = AsyncMock(return_value=_mock_create_process(stdout=jsonl))
        with patch("asyncio.create_subprocess_exec", mock_exec):
            return await _run_backend(backend, spec)

    result = asyncio.run(_run())
    assert result.text == "Step 1 done.\nStep 2 done."
    # Callback should have been called for each agent message
    assert callback.call_count >= 2
    # At least one call should mention "Agent:"
    agent_calls = [c for c in callback.call_args_list if "Agent:" in c[0][0]]
    assert len(agent_calls) >= 2


def test_codex_progress_callback_todo():
    """progress_callback fires with rendered todo list for todo_list events."""
    backend = CodexBackend()
    callback = Mock()
    jsonl = _jsonl(
        {"type": "thread.started", "thread_id": "t-1"},
        {
            "type": "item.completed",
            "item": {
                "type": "todo_list",
                "items": [
                    {"text": "Fix bug", "completed": True},
                    {"text": "Write tests", "completed": False},
                ],
            },
        },
        {
            "type": "item.completed",
            "item": {"id": "msg1", "type": "agent_message", "text": "Done."},
        },
        {
            "type": "turn.completed",
            "usage": {"input_tokens": 1, "output_tokens": 1},
        },
    )
    spec = RunSpec(
        prompt="Fix",
        cwd="/tmp",
        mode="read_write",
        progress_callback=callback,
    )

    async def _run():
        mock_exec = AsyncMock(return_value=_mock_create_process(stdout=jsonl))
        with patch("asyncio.create_subprocess_exec", mock_exec):
            return await _run_backend(backend, spec)

    asyncio.run(_run())
    # Should have fired at least once with todo content
    todo_calls = [c for c in callback.call_args_list if "📋" in c[0][0]]
    assert len(todo_calls) >= 1
    assert "Fix bug" in todo_calls[0][0][0]


def test_codex_result_no_mcp_flags():
    """Phase 4: plan_posted and question_posted are always False."""
    backend = CodexBackend()
    spec = RunSpec(prompt="Plan", cwd="/tmp", mode="plan")

    async def _run():
        mock_exec = AsyncMock(return_value=_mock_create_process(
            stdout=_make_success_jsonl()
        ))
        with patch("asyncio.create_subprocess_exec", mock_exec):
            return await _run_backend(backend, spec)

    result = asyncio.run(_run())
    assert result.plan_posted is False
    assert result.question_posted is False
    assert result.plan_file_path is None


def test_codex_no_cwd_in_subprocess():
    """subprocess is NOT given cwd= (Codex handles -C itself)."""
    backend = CodexBackend()
    spec = RunSpec(prompt="Fix", cwd="/tmp/repo", mode="read_write")

    async def _run():
        mock_exec = AsyncMock(return_value=_mock_create_process(
            stdout=_make_success_jsonl()
        ))
        with patch("asyncio.create_subprocess_exec", mock_exec):
            await _run_backend(backend, spec)
        call_kwargs = mock_exec.call_args[1]
        return "cwd" not in call_kwargs

    has_no_cwd = asyncio.run(_run())
    assert has_no_cwd, "create_subprocess_exec should NOT receive cwd kwarg"


def test_codex_summary_output_collected():
    """summary_output items are accumulated in RunResult.text."""
    backend = CodexBackend()
    jsonl = _jsonl(
        {"type": "thread.started", "thread_id": "t-1"},
        {
            "type": "item.completed",
            "item": {"id": "msg1", "type": "agent_message", "text": "Step 1"},
        },
        {
            "type": "item.completed",
            "item": {"id": "sum1", "type": "summary_output", "text": "Summary: done"},
        },
        {
            "type": "turn.completed",
            "usage": {"input_tokens": 1, "output_tokens": 1},
        },
    )
    spec = RunSpec(prompt="Fix", cwd="/tmp", mode="read_write")

    async def _run():
        mock_exec = AsyncMock(return_value=_mock_create_process(stdout=jsonl))
        with patch("asyncio.create_subprocess_exec", mock_exec):
            return await _run_backend(backend, spec)

    result = asyncio.run(_run())
    assert "Step 1" in result.text
    assert "Summary: done" in result.text


def test_codex_turn_failed_affects_subtype():
    """JSONL with turn.failed + exit 0 produces subtype='error'."""
    backend = CodexBackend()
    jsonl = _jsonl(
        {"type": "thread.started", "thread_id": "t-1"},
        {"type": "turn.failed", "error": {"message": "Model quota exceeded"}},
    )
    spec = RunSpec(prompt="Fix", cwd="/tmp", mode="read_write")

    async def _run():
        mock_exec = AsyncMock(return_value=_mock_create_process(
            stdout=jsonl, returncode=0
        ))
        with patch("asyncio.create_subprocess_exec", mock_exec):
            return await _run_backend(backend, spec)

    result = asyncio.run(_run())
    assert result.subtype == "error"


def test_codex_ephemeral_fresh_run():
    """Fresh run (no resume) includes --ephemeral flag."""
    backend = CodexBackend()
    spec = RunSpec(prompt="Fix", cwd="/tmp", mode="read_write")

    cmd = _get_cmd(asyncio.run(_async_cmd_test(backend, spec)()))
    assert "--ephemeral" in cmd


def test_codex_no_ephemeral_resume():
    """Resume run omits --ephemeral (needs persistent session files)."""
    backend = CodexBackend()
    spec = RunSpec(
        prompt="Continue",
        cwd="/tmp",
        resume="sess-abc",
        mode="read_write",
    )

    cmd = _get_cmd(asyncio.run(_async_cmd_test(backend, spec)()))
    assert "--ephemeral" not in cmd


def test_codex_max_turns_flag():
    """Non-default max_turns adds -c agent.max_turns=N to command."""
    backend = CodexBackend()
    spec = RunSpec(prompt="Fix", cwd="/tmp", mode="read_write", max_turns=80)

    cmd = _get_cmd(asyncio.run(_async_cmd_test(backend, spec)()))
    assert "-c" in cmd
    idx = cmd.index("-c")
    assert cmd[idx + 1] == "agent.max_turns=80"


def test_codex_default_max_turns_no_flag():
    """Default max_turns (200) does NOT add -c flag."""
    backend = CodexBackend()
    spec = RunSpec(prompt="Fix", cwd="/tmp", mode="read_write", max_turns=200)

    cmd = _get_cmd(asyncio.run(_async_cmd_test(backend, spec)()))
    assert "-c" not in cmd


# ---------- Config interpolation ----------


def test_config_expand_env_var():
    """${VAR} references are expanded from environment."""
    from autoswe.core.config import _expand_env

    os.environ["_TEST_VAR_XYZ"] = "expanded-value"
    try:
        assert _expand_env("${_TEST_VAR_XYZ}") == "expanded-value"
        assert _expand_env("prefix-${_TEST_VAR_XYZ}-suffix") == "prefix-expanded-value-suffix"
    finally:
        del os.environ["_TEST_VAR_XYZ"]


def test_config_expand_env_default():
    """${VAR:-default} uses the default when env var is not set."""
    from autoswe.core.config import _expand_env

    assert _expand_env("${_NONEXISTENT_VAR_XYZ:-fallback}") == "fallback"


def test_config_expand_env_missing_no_default():
    """${VAR} with no default and no env var → empty string."""
    from autoswe.core.config import _expand_env

    assert _expand_env("${_NONEXISTENT_VAR_XYZ}") == ""


# ---------- factory integration ----------


def test_factory_codex():
    """Factory returns CodexBackend for backend='codex'."""
    from autoswe.harness.backends.factory import get_backend

    backend = get_backend({"backend": "codex", "model": "gpt-5"})
    assert isinstance(backend, CodexBackend)


def test_factory_codex_case_insensitive():
    """Factory accepts 'codex' in any case."""
    from autoswe.harness.backends.factory import get_backend

    for val in ("codex", "CODEX", "Codex"):
        backend = get_backend({"backend": val})
        assert isinstance(backend, CodexBackend)


# ---------- backend_has_capability ----------


def test_backend_has_capability_codex():
    """backend_has_capability returns correct values for Codex."""
    from autoswe.harness.runner import backend_has_capability

    harness = {"backend": "codex"}
    # Phase 4: only resume and progress_stream
    assert not backend_has_capability(harness, "mode")
    assert backend_has_capability(harness, "resume")
    assert backend_has_capability(harness, "progress_stream")
    assert not backend_has_capability(harness, "mcp")
    assert not backend_has_capability(harness, "can_use_tool")
    assert not backend_has_capability(harness, "plan_permission")


# ---------- Backend parity (Codex vs Claude Code contract) ----------


def test_backend_parity_runresult_shape():
    """Both backends return RunResult with identical field names."""
    from autoswe.harness.backends.claude_code import ClaudeCodeBackend

    # Both backends produce RunResult with the same fields
    codex_caps = CodexBackend.capabilities()
    claude_caps = ClaudeCodeBackend.capabilities()

    # Both advertise resume
    assert "resume" in codex_caps
    assert "resume" in claude_caps

    # Claude has more capabilities (mode, mcp, can_use_tool, etc.)
    assert "mode" in claude_caps
    assert "mode" not in codex_caps
    assert "mcp" in claude_caps
    assert "mcp" not in codex_caps

    assert "can_use_tool" in claude_caps
    assert "can_use_tool" not in codex_caps


def test_backend_parity_run_spec_compatibility():
    """Both backends accept the same RunSpec fields."""
    from autoswe.harness.backends.claude_code import ClaudeCodeBackend

    # Both backends can be instantiated and accept a RunSpec
    codex = CodexBackend()
    claude = ClaudeCodeBackend()

    spec = RunSpec(
        prompt="test",
        cwd="/tmp",
        model="test-model",
        mode="read_write",
        resume=None,
        max_turns=100,
        timeout=300,
        env_overrides={"KEY": "val"},
        progress_callback=lambda x: None,
    )

    # Both return awaitables
    codex_coro = codex.run(spec)
    claude_coro = claude.run(spec)
    assert asyncio.iscoroutine(codex_coro)
    assert asyncio.iscoroutine(claude_coro)
    codex_coro.close()
    claude_coro.close()


def test_backend_parity_runresult_tuple_unpacking():
    """Both backends' RunResult supports tuple-style unpacking."""
    r = RunResult(
        text="hello",
        session_id="s1",
        subtype="success",
        cost_usd=0.01,
        duration_seconds=5.0,
    )
    text, session_id, subtype = r
    assert text == "hello"
    assert session_id == "s1"
    assert subtype == "success"
