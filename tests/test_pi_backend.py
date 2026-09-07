"""Tests for autoswe.harness.backends.pi — PiBackend via faked subprocess.

All async tests fake ``asyncio.create_subprocess_exec`` (either through the
scripted ``PiFake`` or a controlled mock process) to emit canned ``--mode json``
output on the simulated stdout pipe.  No live pi calls are made.

Pure command-building / parsing helpers are tested directly; end-to-end
RunResult behavior is tested through the real factory → PiBackend → parser path.
"""
from __future__ import annotations

import asyncio
import json
import sys
from unittest.mock import AsyncMock, Mock, patch

import pytest

import autoswe.harness.backends.pi as _pi_mod
from autoswe.harness.backends.base import RunResult, RunSpec
from autoswe.harness.backends.pi import (
    _ALWAYS_EXCLUDED_TOOLS,
    _DEFAULT_TOOLS,
    _MAX_STREAM_BYTES,
    _MODE_TOOLS,
    PiBackend,
    _assistant_text,
    _build_argv,
    _excluded_tools_for_spec,
    _extract_cost,
    _parse_line,
    _PiAccumulator,
    _resolve_pi_executable,
    _tool_label,
    _tools_for_spec,
)

# The host model id used across the suite (any non-empty value works).
MODEL = "anthropic/claude-sonnet-4-5"


# ---------- Helpers ----------


def _spec(**overrides) -> RunSpec:
    """Build a minimal pi RunSpec with a model (the factory guard requires one)."""
    defaults = {
        "prompt": "test prompt",
        "cwd": "/tmp/repo",
        "model": MODEL,
        "mode": "read_write",
        "state": {"_harness_cfg": {"backend": "pi", "model": MODEL}},
    }
    defaults.update(overrides)
    return RunSpec(**defaults)


def _run(backend, spec):
    """Run a PiBackend spec inside a fresh event loop, return the coroutine result."""
    return asyncio.run(backend.run(spec))


def _run_pi(spec, fake, backend=None):
    """Run the real PiBackend under a patched PiFake subprocess; return (result, fake)."""
    backend = backend or PiBackend()

    async def _inner():
        with fake:
            return await backend.run(spec)

    return asyncio.run(_inner()), fake


def _mock_process(stdout: str = "", stderr: str = "", returncode: int = 0):
    """A controllable process whose stdout is line-oriented, stderr is chunked.

    Mirrors the shape of PiBackend's readers: ``stdout.readline()`` for the
    JSONL loop and ``stderr.read(n)`` for the chunked stderr collector.
    """

    class _Stdout:
        def __init__(self, data: bytes):
            self._lines = data.splitlines(keepends=True)
            self._pos = 0
            self._buf = data
            self._bpos = 0

        async def readline(self) -> bytes:
            if self._pos < len(self._lines):
                line = self._lines[self._pos]
                self._pos += 1
                return line
            return b""

        async def read(self, size: int = -1) -> bytes:
            out = self._buf[self._bpos:self._bpos + size]
            self._bpos += len(out)
            return out

    class _Stderr:
        def __init__(self, data: bytes):
            self._data = data
            self._pos = 0

        async def read(self, size: int = -1) -> bytes:
            out = self._data[self._pos:self._pos + size]
            self._pos += len(out)
            return out

    class _Process:
        def __init__(self):
            self.returncode = returncode
            self.stdout = _Stdout(stdout.encode())
            self.stderr = _Stderr(stderr.encode())
            self.killed = False

        def kill(self):
            self.killed = True

        async def wait(self) -> int:
            return returncode

    return _Process()


def _jsonl(*events: dict) -> str:
    """Build a JSONL string from a sequence of event dicts."""
    return "".join(json.dumps(e) + "\n" for e in events)


# ---------- Capabilities ----------


def test_pi_capabilities():
    """PiBackend advertises mode + resume + session_fork + progress_stream + mcp."""
    caps = PiBackend.capabilities()
    assert "mode" in caps
    assert "resume" in caps
    assert "session_fork" in caps
    assert "progress_stream" in caps
    # Phase 2: pi reaches the autoswe_comment MCP server via the
    # pi-mcp-adapter and parses its tool_execution_start events, so it now
    # advertises the "mcp" capability (turns on planner.py's has_mcp branch).
    assert "mcp" in caps
    # No native per-tool-approval callback; no plan-file output.
    assert "can_use_tool" not in caps
    assert "plan_permission" not in caps
    assert "plan_file" not in caps
    assert "structured_output" not in caps


def test_pi_capabilities_returns_copy():
    """capabilities() returns a copy, not the class-level set."""
    caps = PiBackend.capabilities()
    assert caps is not PiBackend.CAPABILITIES
    caps.add("__tamper__")
    assert "__tamper__" not in PiBackend.CAPABILITIES


def test_pi_retryable_subtypes():
    """PiBackend.retryable_subtypes() returns {'error', 'killed'}."""
    assert PiBackend.retryable_subtypes() == {"error", "killed"}


def test_pi_retryable_subtypes_returns_copy():
    """retryable_subtypes() returns a new set each call."""
    a = PiBackend.retryable_subtypes()
    b = PiBackend.retryable_subtypes()
    assert a is not b
    assert a is not PiBackend.RETRYABLE_SUBTYPES
    a.add("__tamper__")
    assert "__tamper__" not in b


def test_pi_retryable_exceptions():
    """PiBackend.retryable_exceptions() is (TimeoutError, OSError).

    pi has no SDK; its failure surface is the subprocess boundary (the same as
    Codex).  asyncio.TimeoutError is the runner's wall-clock timeout; OSError
    covers spawn-time failures from create_subprocess_exec (FileNotFoundError
    is an OSError subclass).
    """
    assert PiBackend.retryable_exceptions() == (asyncio.TimeoutError, OSError)


# ---------- Protocol conformance ----------


def test_pi_satisfies_protocol():
    """PiBackend should satisfy the CodingBackend Protocol shape."""
    assert hasattr(PiBackend, "capabilities")
    assert hasattr(PiBackend, "run")
    assert callable(PiBackend.capabilities)
    assert callable(PiBackend.run)


def test_pi_run_returns_awaitable():
    """run(spec) should return an awaitable (coroutine)."""
    backend = PiBackend()
    result = backend.run(_spec())
    assert asyncio.iscoroutine(result)
    result.close()


def test_pi_read_only_enforcement():
    """Because 'mode' is advertised, has_read_only_enforcement is True.

    This is the key difference from Codex: plan/review keep their guarantees
    instead of loudly degrading and relying on the worktree-rollback backstop.
    """
    from autoswe.harness.runner import has_read_only_enforcement

    assert has_read_only_enforcement({"backend": "pi", "model": MODEL}) is True


# ---------- Executable resolution ----------


def test_resolve_explicit_cli_path():
    """An explicit spec.cli_path wins over PATH lookup."""
    path, prefix = _resolve_pi_executable("/opt/pi/bin/pi")
    assert path == "/opt/pi/bin/pi"
    assert prefix == []


def test_resolve_path_lookup(monkeypatch):
    """No cli_path → shutil.which('pi') result is used."""
    monkeypatch.setattr(_pi_mod.shutil, "which", lambda name: "/usr/local/bin/pi")
    path, prefix = _resolve_pi_executable(None)
    assert path == "/usr/local/bin/pi"
    assert prefix == []


def test_resolve_bare_fallback(monkeypatch):
    """No cli_path, nothing on PATH → bare 'pi' (let the OS decide)."""
    monkeypatch.setattr(_pi_mod.shutil, "which", lambda name: None)
    path, prefix = _resolve_pi_executable("")
    assert path == "pi"
    assert prefix == []


def test_resolve_windows_cmd_shim(monkeypatch):
    """On native Windows a .cmd shim is invoked through `cmd /c`."""
    monkeypatch.setattr(_pi_mod.os, "name", "nt")
    path, prefix = _resolve_pi_executable("C:\\Users\\me\\npm\\pi.cmd")
    assert path == "C:\\Users\\me\\npm\\pi.cmd"
    assert prefix == ["cmd", "/c"]


def test_resolve_windows_bat_shim(monkeypatch):
    """On native Windows a .bat shim is also invoked through `cmd /c`."""
    monkeypatch.setattr(_pi_mod.os, "name", "nt")
    path, prefix = _resolve_pi_executable("C:\\Users\\me\\npm\\pi.BAT")
    assert path == "C:\\Users\\me\\npm\\pi.BAT"
    assert prefix == ["cmd", "/c"]


def test_resolve_non_shim_no_prefix_even_on_windows(monkeypatch):
    """A non-shim path never gets a prefix, even on Windows."""
    monkeypatch.setattr(_pi_mod.os, "name", "nt")
    path, prefix = _resolve_pi_executable("C:\\pi\\pi")
    assert path == "C:\\pi\\pi"
    assert prefix == []


def test_resolve_no_prefix_on_posix_shim(monkeypatch):
    """On POSIX a .cmd-suffixed path is NOT routed through cmd /c.

    The shim workaround is Windows-only (CreateProcess cannot run .cmd/.bat).
    """
    monkeypatch.setattr(_pi_mod.os, "name", "posix")
    path, prefix = _resolve_pi_executable("/opt/pi/pi.cmd")
    assert path == "/opt/pi/pi.cmd"
    assert prefix == []


# ---------- Mode → tools ----------


def test_tools_plan():
    assert _tools_for_spec(_spec(mode="plan")) == ["read", "grep", "find", "ls"]


def test_tools_read_only():
    assert _tools_for_spec(_spec(mode="read_only")) == ["read", "grep", "find", "ls"]


def test_tools_read_write(monkeypatch):
    monkeypatch.setattr(_pi_mod.os, "name", "posix")
    assert _tools_for_spec(_spec(mode="read_write")) == \
        ["read", "bash", "edit", "write", "grep", "find", "ls"]


def test_tools_unset_mode_defaults_to_read_write(monkeypatch):
    """An unset mode falls back to the read_write set (a /fix is full-work)."""
    monkeypatch.setattr(_pi_mod.os, "name", "posix")
    assert _tools_for_spec(_spec(mode=None)) == list(_DEFAULT_TOOLS)


def test_tools_windows_read_write_adds_powershell(monkeypatch):
    """On a Windows host read_write keeps powershell alongside bash."""
    monkeypatch.setattr(_pi_mod.os, "name", "nt")
    tools = _tools_for_spec(_spec(mode="read_write"))
    assert "powershell" in tools
    assert "bash" in tools


def test_mode_tools_map_read_only_recipes():
    """The mode→tools table encodes the documented read-only recipe.

    docs/pi/usage.md: ``pi --tools read,grep,find,ls`` is the read-only recipe;
    plan and read_only share it, while read_write adds the mutators.
    """
    assert _MODE_TOOLS["plan"] == ("read", "grep", "find", "ls")
    assert _MODE_TOOLS["read_only"] == ("read", "grep", "find", "ls")
    assert "bash" in _MODE_TOOLS["read_write"]
    assert "edit" in _MODE_TOOLS["read_write"]
    # The default fallback is the read_write set.
    assert _MODE_TOOLS["read_write"] == _DEFAULT_TOOLS


def test_max_stream_bytes_bound():
    """The stdout/stderr bound is 16 MB (mirrors codex.py)."""
    assert _MAX_STREAM_BYTES == 16 * 1024 * 1024


def test_tools_windows_read_only_no_powershell(monkeypatch):
    """powershell is only added for read_write, not the read-only modes."""
    monkeypatch.setattr(_pi_mod.os, "name", "nt")
    assert "powershell" not in _tools_for_spec(_spec(mode="read_only"))
    assert "powershell" not in _tools_for_spec(_spec(mode="plan"))


def test_tools_extra_tools_appended(monkeypatch):
    monkeypatch.setattr(_pi_mod.os, "name", "posix")
    tools = _tools_for_spec(_spec(mode="plan", extra_tools=["write", "web"]))
    assert tools == ["read", "grep", "find", "ls", "write", "web"]


def test_tools_extra_tools_deduped(monkeypatch):
    """extra_tools that duplicate a base tool are collapsed (order preserved)."""
    monkeypatch.setattr(_pi_mod.os, "name", "posix")
    tools = _tools_for_spec(_spec(mode="plan", extra_tools=["read", "web"]))
    assert tools.count("read") == 1
    assert tools == ["read", "grep", "find", "ls", "web"]


def test_tools_unknown_mode_falls_back_to_default(monkeypatch):
    """An unrecognized mode string falls back to the default (read_write) set."""
    monkeypatch.setattr(_pi_mod.os, "name", "posix")
    assert _tools_for_spec(_spec(mode="bogus_mode")) == list(_DEFAULT_TOOLS)


def _spec_with_comment_mcp(mode="read_write", **overrides):
    """A spec whose mcp_servers names autoswe_comment (the Phase 2 trigger)."""
    return _spec(
        mode=mode,
        mcp_servers={"autoswe_comment": {"command": sys.executable, "env": {}}},
        **overrides,
    )


def test_tools_mcp_comment_adds_three_names(monkeypatch):
    """Naming autoswe_comment adds the three tool names to the allowlist.

    pi's --tools is a hard allowlist, so the MCP direct tools must be listed
    to be visible at all — and they must be listed for EVERY mode, including
    the read-only plan/read_only sets.
    """
    monkeypatch.setattr(_pi_mod.os, "name", "posix")
    for mode in ("plan", "read_only", "read_write", None):
        tools = _tools_for_spec(_spec_with_comment_mcp(mode=mode))
        for name in _pi_mod._MCP_COMMENT_TOOL_NAMES:
            assert name in tools, (mode, tools)


def test_tools_mcp_comment_not_added_without_server(monkeypatch):
    """Without the autoswe_comment server, the MCP tool names stay out."""
    monkeypatch.setattr(_pi_mod.os, "name", "posix")
    tools = _tools_for_spec(_spec(mode="plan"))
    for name in _pi_mod._MCP_COMMENT_TOOL_NAMES:
        assert name not in tools


def test_tools_mcp_comment_other_server_does_not_add(monkeypatch):
    """A different MCP server is not a trigger; no comment tools are added."""
    monkeypatch.setattr(_pi_mod.os, "name", "posix")
    spec = _spec(
        mode="plan",
        mcp_servers={"some_other": {"command": "x", "env": {}}},
    )
    for name in _pi_mod._MCP_COMMENT_TOOL_NAMES:
        assert name not in _tools_for_spec(spec)


def test_tools_mcp_comment_dedupes_extra_tools(monkeypatch):
    """MCP tool names already in extra_tools are not duplicated."""
    monkeypatch.setattr(_pi_mod.os, "name", "posix")
    name = _pi_mod._MCP_COMMENT_TOOL_NAMES[0]
    tools = _tools_for_spec(_spec_with_comment_mcp(extra_tools=[name]))
    assert tools.count(name) == 1


# ---------- Excluded tools ----------


def test_excluded_always_has_ask_question():
    assert "ask_question" in _excluded_tools_for_spec(_spec())


def test_excluded_always_excluded_constant():
    assert _ALWAYS_EXCLUDED_TOOLS == ("ask_question",)


def test_excluded_disallowed_override_appended():
    tools = _excluded_tools_for_spec(_spec(disallowed_tools_override=["bash", "ask_question"]))
    assert "bash" in tools
    assert tools.count("ask_question") == 1
    # ask_question is first (always excluded), operator entries follow.
    assert tools[0] == "ask_question"


def test_excluded_none_override():
    assert _excluded_tools_for_spec(_spec(disallowed_tools_override=None)) == ["ask_question"]


# ---------- argv construction (pure) ----------


def _argv(spec=None, harness_cfg=None, session_id="sess-123",
          pi_path="pi", prefix_args=None):
    spec = spec or _spec()
    return _build_argv(spec, harness_cfg or {}, pi_path,
                       prefix_args or [], session_id)


def test_argv_fresh_session_id():
    cmd = _argv()
    assert "--mode" in cmd and cmd[cmd.index("--mode") + 1] == "json"
    assert "--session-id" in cmd
    assert cmd[cmd.index("--session-id") + 1] == "sess-123"
    assert "--session" not in cmd
    assert "--fork" not in cmd


def test_argv_resume_session():
    cmd = _argv(spec=_spec(resume="old-session"))
    assert "--session" in cmd
    assert cmd[cmd.index("--session") + 1] == "old-session"
    assert "--session-id" not in cmd
    assert "--fork" not in cmd


def test_argv_fork_session_id_and_resume():
    cmd = _argv(spec=_spec(resume="source-session", fork_session=True))
    assert "--fork" in cmd
    assert cmd[cmd.index("--fork") + 1] == "source-session"
    assert "--session-id" in cmd
    assert cmd[cmd.index("--session-id") + 1] == "sess-123"


def test_argv_fork_without_resume_treated_as_fresh():
    """fork_session without a resume is not a fork — it's a fresh run."""
    cmd = _argv(spec=_spec(fork_session=True))
    assert "--fork" not in cmd
    assert "--session-id" in cmd


def test_argv_model_and_provider_and_thinking():
    cmd = _argv(
        harness_cfg={"provider": "openai", "thinking": "high"},
    )
    assert cmd[cmd.index("--model") + 1] == MODEL
    assert cmd[cmd.index("--provider") + 1] == "openai"
    assert cmd[cmd.index("--thinking") + 1] == "high"


def test_argv_omits_empty_provider_thinking():
    cmd = _argv(harness_cfg={"provider": "", "thinking": "  "})
    assert "--provider" not in cmd
    assert "--thinking" not in cmd


def test_argv_tools_and_exclude_tools():
    monkeypatch_tools = _tools_for_spec(_spec(mode="read_only"))
    cmd = _argv(spec=_spec(mode="read_only"))
    tools_val = cmd[cmd.index("--tools") + 1]
    assert tools_val == ",".join(monkeypatch_tools)
    assert "--exclude-tools" in cmd
    assert "ask_question" in cmd[cmd.index("--exclude-tools") + 1]


def test_argv_approve_default_on():
    """Project trust defaults to on (dedicated-machine posture)."""
    assert "--approve" in _argv()


def test_argv_approve_off_via_profile():
    assert "--approve" not in _argv(harness_cfg={"approve_project": False})


def test_argv_api_key():
    cmd = _argv(harness_cfg={"api_key": "sk-test"})
    assert cmd[cmd.index("--api-key") + 1] == "sk-test"


def test_argv_no_api_key_when_unset():
    assert "--api-key" not in _argv()


def test_argv_system_prompt_and_append():
    cmd = _argv(harness_cfg={
        "system_prompt": "You are terse.",
        "append_system_prompt": "Extra context.",
        "session_dir": "/tmp/sessions",
    })
    assert cmd[cmd.index("--system-prompt") + 1] == "You are terse."
    assert cmd[cmd.index("--append-system-prompt") + 1] == "Extra context."
    assert cmd[cmd.index("--session-dir") + 1] == "/tmp/sessions"


def test_argv_omits_system_prompt_flags_when_unset():
    """Neither system-prompt flag is emitted when both fields are unset."""
    cmd = _argv()
    assert "--system-prompt" not in cmd
    assert "--append-system-prompt" not in cmd


def test_argv_omits_session_dir_when_unset():
    """No session_dir profile field → no --session-dir flag."""
    cmd = _argv()
    assert "--session-dir" not in cmd


def test_argv_includes_session_dir_when_set():
    """session_dir profile field maps to the --session-dir flag."""
    cmd = _argv(harness_cfg={"session_dir": "~/.pi/sessions"})
    assert cmd[cmd.index("--session-dir") + 1] == "~/.pi/sessions"


def test_argv_prompt_after_separator():
    cmd = _argv(spec=_spec(prompt="Fix the bug"))
    dash = cmd.index("--")
    assert cmd[dash + 1] == "Fix the bug"
    assert cmd[-1] == "Fix the bug"


def test_argv_prompt_starting_with_dash_safe():
    cmd = _argv(spec=_spec(prompt="-Fix the bug"))
    dash = cmd.index("--")
    assert cmd[dash + 1] == "-Fix the bug"


def test_argv_windows_prefix_precedes_pi():
    """A Windows .cmd shim prefix comes before the pi executable."""
    cmd = _argv(pi_path="C:\\pi\\pi.cmd", prefix_args=["cmd", "/c"])
    assert cmd[0] == "cmd" and cmd[1] == "/c" and cmd[2] == "C:\\pi\\pi.cmd"
    # The rest of the flags follow.
    assert "--mode" in cmd


# ---------- Cost extraction ----------


def test_extract_cost_top_level():
    assert _extract_cost({"usage": {"cost": {"total": 0.125}}}) == 0.125


def test_extract_cost_nested_on_message():
    assert _extract_cost({
        "message": {"usage": {"cost": {"total": 0.5}}},
    }) == 0.5


def test_extract_cost_int_total():
    """An integer total is coerced to float."""
    assert _extract_cost({"usage": {"cost": {"total": 0}}}) == 0.0


def test_extract_cost_absent():
    assert _extract_cost({"usage": {}}) is None
    assert _extract_cost({"usage": {"cost": {}}}) is None
    assert _extract_cost({}) is None


def test_extract_cost_non_numeric():
    assert _extract_cost({"usage": {"cost": {"total": "abc"}}}) is None
    assert _extract_cost({"usage": "not-a-dict"}) is None
    assert _extract_cost({"message": "not-a-dict"}) is None


# ---------- Assistant text extraction ----------


def test_assistant_text_joins_text_blocks():
    msg = {"content": [
        {"type": "text", "text": "First."},
        {"type": "thinking", "thinking": "internal"},
        {"type": "text", "text": "Second."},
    ]}
    assert _assistant_text(msg) == "First.\nSecond."


def test_assistant_text_excludes_non_text_blocks():
    msg = {"content": [
        {"type": "thinking", "thinking": "reasoning"},
        {"type": "toolcall", "name": "bash"},
    ]}
    assert _assistant_text(msg) == ""


def test_assistant_text_non_list_content():
    assert _assistant_text({"content": "not a list"}) == ""
    assert _assistant_text({}) == ""


def test_assistant_text_skips_empty_text():
    msg = {"content": [
        {"type": "text", "text": ""},
        {"type": "text", "text": "Only."},
    ]}
    assert _assistant_text(msg) == "Only."


# ---------- Tool label rendering ----------


def test_tool_label_bash():
    assert _tool_label({"toolName": "bash", "args": {"command": "ls -la"}}) == "bash ls -la"


def test_tool_label_powershell():
    assert _tool_label({"toolName": "powershell", "args": {"command": "Get-Process"}}) == \
        "powershell Get-Process"


def test_tool_label_edit_path():
    assert _tool_label({"toolName": "edit", "args": {"path": "/a/b.py"}}) == "edit /a/b.py"


def test_tool_label_write_file_path_alias():
    assert _tool_label({"toolName": "write", "args": {"file_path": "/c/d.py"}}) == \
        "write /c/d.py"


def test_tool_label_generic():
    assert _tool_label({"toolName": "grep", "args": {"pattern": "x"}}) == "grep"


def test_tool_label_non_dict_args():
    """Non-dict args degrade to an empty command (label is 'bash ' stripped is 'bash')."""
    # args is not a dict → treated as {} → no command → "bash " (trailing space
    # from the f-string; the parser only ever renders this for progress lines).
    label = _tool_label({"toolName": "bash", "args": "oops"})
    assert label.strip() == "bash"


def test_tool_label_bash_empty_command():
    assert _tool_label({"toolName": "bash", "args": {}}).strip() == "bash"


# ---------- _parse_line (unit) ----------


def test_parse_session_header_sets_id():
    acc = _PiAccumulator()
    _parse_line(json.dumps({"type": "session", "id": "abc123"}), acc, None)
    assert acc.session_id == "abc123"


def test_parse_session_header_missing_id():
    """A session header without an id leaves the pre-seeded id intact."""
    acc = _PiAccumulator()
    acc.session_id = "pinned"
    _parse_line(json.dumps({"type": "session", "version": 3}), acc, None)
    assert acc.session_id == "pinned"


def test_parse_session_header_id_cross_check_header_wins():
    """When the header id differs from the requested id, the header wins."""
    acc = _PiAccumulator()
    acc.session_id = "requested"
    _parse_line(json.dumps({"type": "session", "id": "actual"}), acc, None)
    assert acc.session_id == "actual"


def test_parse_message_update_text_delta_accumulates_and_fires():
    acc = _PiAccumulator()
    cb = Mock()
    _parse_line(json.dumps({
        "type": "message_update",
        "assistantMessageEvent": {"type": "text_delta", "contentIndex": 0, "delta": "Hel"},
    }), acc, cb)
    assert acc._delta_by_index[0] == ["Hel"]
    assert cb.called  # live progress fired on the first delta


def test_parse_message_update_multiple_content_index():
    """Deltas for different contentIndex are kept separate and in order."""
    acc = _PiAccumulator()
    _parse_line(json.dumps({
        "type": "message_update",
        "assistantMessageEvent": {"type": "text_delta", "contentIndex": 1, "delta": "B"},
    }), acc, None)
    _parse_line(json.dumps({
        "type": "message_update",
        "assistantMessageEvent": {"type": "text_delta", "contentIndex": 0, "delta": "A"},
    }), acc, None)
    # Index 0 before index 1 on reassembly.
    assert sorted(acc._delta_by_index) == [0, 1]
    assert acc._delta_by_index[0] == ["A"]
    assert acc._delta_by_index[1] == ["B"]


def test_parse_message_update_thinking_delta_progress_only():
    """thinking_delta fires progress but is NEVER accumulated into the text fallback."""
    acc = _PiAccumulator()
    cb = Mock()
    _parse_line(json.dumps({
        "type": "message_update",
        "assistantMessageEvent": {"type": "thinking_delta", "contentIndex": 0, "delta": "reason"},
    }), acc, cb)
    assert cb.called  # a 💭 progress line
    assert "💭" in cb.call_args[0][0]
    # Not accumulated — the text fallback must not leak reasoning.
    assert not acc._delta_by_index


def test_parse_message_update_captures_cost():
    acc = _PiAccumulator()
    _parse_line(json.dumps({
        "type": "message_update",
        "usage": {"cost": {"total": 0.01}},
        "assistantMessageEvent": {"type": "text_delta", "contentIndex": 0, "delta": "x"},
    }), acc, None)
    assert acc.cost_usd == 0.01


def test_parse_message_end_assistant_authoritative_text():
    acc = _PiAccumulator()
    _parse_line(json.dumps({
        "type": "message_end",
        "message": {"role": "assistant", "content": [{"type": "text", "text": "Done."}]},
    }), acc, None)
    assert acc.text == "Done."


def test_parse_message_end_non_assistant_ignored():
    """A toolResult/user message_end does not set the authoritative text."""
    acc = _PiAccumulator()
    _parse_line(json.dumps({
        "type": "message_end",
        "message": {"role": "toolResult", "content": "output"},
    }), acc, None)
    assert acc.text is None


def test_parse_message_end_captures_cost():
    acc = _PiAccumulator()
    _parse_line(json.dumps({
        "type": "message_end",
        "usage": {"cost": {"total": 0.7}},
        "message": {"role": "assistant", "content": []},
    }), acc, None)
    assert acc.cost_usd == 0.7


def test_parse_message_end_fires_progress():
    acc = _PiAccumulator()
    cb = Mock()
    _parse_line(json.dumps({
        "type": "message_end",
        "message": {"role": "assistant", "content": [{"type": "text", "text": "Final."}]},
    }), acc, cb)
    assert cb.called
    assert "Agent:" in cb.call_args[0][0]


def test_parse_tool_execution_start_fires():
    acc = _PiAccumulator()
    cb = Mock()
    _parse_line(json.dumps({
        "type": "tool_execution_start",
        "toolCallId": "t1", "toolName": "bash", "args": {"command": "make"},
    }), acc, cb)
    assert cb.called
    assert "Tool:" in cb.call_args[0][0]
    assert "bash make" in cb.call_args[0][0]


def test_parse_tool_execution_end_success_fires_done():
    acc = _PiAccumulator()
    cb = Mock()
    _parse_line(json.dumps({
        "type": "tool_execution_end",
        "toolCallId": "t1", "toolName": "bash", "args": {"command": "make"},
        "result": "ok", "isError": False,
    }), acc, cb)
    assert cb.called
    assert "Tool done:" in cb.call_args[0][0]
    assert not acc.has_error


def test_parse_tool_execution_end_is_error_sets_flag():
    """A tool result with isError: true flips the error flag (spec-documented tradeoff)."""
    acc = _PiAccumulator()
    cb = Mock()
    _parse_line(json.dumps({
        "type": "tool_execution_end",
        "toolCallId": "t1", "toolName": "grep", "args": {}, "isError": True,
    }), acc, cb)
    assert acc.has_error is True
    # A failing tool does not fire the "Tool done" success line.
    assert not any("Tool done" in c[0][0] for c in cb.call_args_list)


def test_parse_agent_end_sets_marker_and_cost():
    acc = _PiAccumulator()
    _parse_line(json.dumps({
        "type": "agent_end",
        "usage": {"cost": {"total": 1.5}},
        "messages": [],
    }), acc, None)
    assert acc.agent_end is True
    assert acc.cost_usd == 1.5


# ---------- MCP tool_execution_start classification (Phase 2) ----------


def test_parse_mcp_post_plan_direct_sets_flag():
    """A direct mcp__autoswe_comment_post_plan start sets plan_posted."""
    acc = _PiAccumulator()
    _parse_line(json.dumps({
        "type": "tool_execution_start",
        "toolCallId": "chatcmpl-tool-x",
        "toolName": "mcp__autoswe_comment_post_plan",
        "args": {"body": "1. Do the thing"},
    }), acc, Mock())
    assert acc.plan_posted is True
    assert acc.question_posted is False


def test_parse_mcp_post_question_direct_sets_flag():
    acc = _PiAccumulator()
    _parse_line(json.dumps({
        "type": "tool_execution_start",
        "toolName": "mcp__autoswe_comment_post_question",
        "args": {"body": "Which DB?"},
    }), acc, Mock())
    assert acc.question_posted is True
    assert acc.plan_posted is False


def test_parse_mcp_update_progress_direct_fires_progress():
    """update_progress fires the progress callback with its body."""
    acc = _PiAccumulator()
    cb = Mock()
    _parse_line(json.dumps({
        "type": "tool_execution_start",
        "toolName": "mcp__autoswe_comment_update_progress",
        "args": {"body": "Running: pytest tests/"},
    }), acc, cb)
    # The body is forwarded as a progress line (plus the generic Tool: line).
    assert any(c[0][0].startswith("Running: pytest") for c in cb.call_args_list)
    assert not acc.plan_posted
    assert not acc.question_posted


def test_parse_mcp_update_progress_empty_body_suppresses_progress():
    """An empty body suppresses the progress line (only the generic Tool: line fires).

    This is the AUTOSWE_SUPPRESS_POSTING boundary: when the comment server is in
    minimal-posting mode the model's update_progress carries no meaningful body,
    so the parser must NOT forward an empty progress line to the operator.
    """
    acc = _PiAccumulator()
    cb = Mock()
    _parse_line(json.dumps({
        "type": "tool_execution_start",
        "toolName": "mcp__autoswe_comment_update_progress",
        "args": {"body": ""},
    }), acc, cb)
    # No progress line derived from the (empty) body — only the generic
    # "Tool:" line fires (the callback is present).
    assert [c[0][0] for c in cb.call_args_list] == ["Tool: mcp__autoswe_comment_update_progress"]
    assert not acc.plan_posted
    assert not acc.question_posted


def test_parse_mcp_update_progress_absent_body_suppresses_progress():
    """update_progress with no body key suppresses the progress line."""
    acc = _PiAccumulator()
    cb = Mock()
    _parse_line(json.dumps({
        "type": "tool_execution_start",
        "toolName": "mcp__autoswe_comment_update_progress",
        "args": {},
    }), acc, cb)
    # Only the generic "Tool:" line fires; no body-derived progress line.
    assert [c[0][0] for c in cb.call_args_list] == ["Tool: mcp__autoswe_comment_update_progress"]


def test_parse_mcp_update_progress_no_callback_suppresses_silently():
    """With no callback, update_progress fires nothing (both lines are guarded)."""
    acc = _PiAccumulator()
    _parse_line(json.dumps({
        "type": "tool_execution_start",
        "toolName": "mcp__autoswe_comment_update_progress",
        "args": {"body": "Status: halfway"},
    }), acc, None)
    # Nothing to assert on the callback (it's None) — the parse must not raise,
    # and the body must NOT leak into plan/question flags.
    assert not acc.plan_posted
    assert not acc.question_posted


def test_parse_mcp_post_plan_generic_proxy_sets_flag():
    """The generic `mcp` proxy ({tool, args}) sets plan_posted too."""
    acc = _PiAccumulator()
    _parse_line(json.dumps({
        "type": "tool_execution_start",
        "toolName": "mcp",
        "args": {"tool": "post_plan", "args": {"body": "P"}},
    }), acc, Mock())
    assert acc.plan_posted is True


def test_parse_mcp_post_question_namespace_proxy_sets_flag():
    """The mcp__autoswe_comment namespace proxy ({tool, args}) sets question_posted."""
    acc = _PiAccumulator()
    _parse_line(json.dumps({
        "type": "tool_execution_start",
        "toolName": "mcp__autoswe_comment",
        "args": {"tool": "post_question", "args": {"body": "Q"}},
    }), acc, Mock())
    assert acc.question_posted is True


def test_parse_mcp_proxy_fully_qualified_tool_value_sets_flag():
    """A proxy whose `tool` is the fully-qualified name still classifies."""
    acc = _PiAccumulator()
    _parse_line(json.dumps({
        "type": "tool_execution_start",
        "toolName": "mcp",
        "args": {"tool": "mcp__autoswe_comment_post_plan",
                 "args": {"body": "P"}},
    }), acc, Mock())
    assert acc.plan_posted is True


def test_parse_mcp_proxy_json_string_args_sets_flag():
    """A proxy with a JSON-string `args` (the documented shape) is tolerated."""
    acc = _PiAccumulator()
    _parse_line(json.dumps({
        "type": "tool_execution_start",
        "toolName": "mcp__autoswe_comment",
        "args": {"tool": "post_plan", "args": json.dumps({"body": "P"})},
    }), acc, Mock())
    assert acc.plan_posted is True


def test_parse_mcp_unknown_proxy_tool_sets_no_flag():
    """A proxy calling a non-comment tool leaves the flags clear."""
    acc = _PiAccumulator()
    _parse_line(json.dumps({
        "type": "tool_execution_start",
        "toolName": "mcp",
        "args": {"tool": "bash", "args": {"command": "ls"}},
    }), acc, Mock())
    assert not acc.plan_posted
    assert not acc.question_posted


def test_parse_non_mcp_tool_execution_sets_no_flag():
    """An ordinary built-in tool start does not touch the MCP flags."""
    acc = _PiAccumulator()
    _parse_line(json.dumps({
        "type": "tool_execution_start",
        "toolName": "read",
        "args": {"path": "/etc/hosts"},
    }), acc, Mock())
    assert not acc.plan_posted
    assert not acc.question_posted


def test_parse_extension_error_sets_flag():
    acc = _PiAccumulator()
    _parse_line(json.dumps({"type": "extension_error", "error": "boom"}), acc, None)
    assert acc.has_error is True


def test_parse_error_event_sets_flag():
    acc = _PiAccumulator()
    _parse_line(json.dumps({"type": "error", "message": "bad"}), acc, None)
    assert acc.has_error is True


def test_parse_non_json_ignored():
    acc = _PiAccumulator()
    _parse_line("this is not json", acc, None)
    assert acc.text is None and acc.has_error is False


def test_parse_empty_line_ignored():
    acc = _PiAccumulator()
    _parse_line("   ", acc, None)
    assert acc.text is None


def test_parse_unknown_event_type_ignored():
    """High-volume events (turn_*, tool_execution_update, queue_update) are ignored."""
    acc = _PiAccumulator()
    for etype in ("agent_start", "turn_start", "turn_end",
                  "tool_execution_update", "queue_update", "compaction_start"):
        _parse_line(json.dumps({"type": etype, "x": 1}), acc, None)
    assert acc.text is None and not acc.has_error and not acc.agent_end


# ---------- End-to-end: text assembly ----------


def test_run_success_text_from_message_end():
    from tests.fakes.pi_fake import PiFake

    fake = PiFake()
    fake.script_response("Fix applied.", session_id="pi-1")
    result, _ = _run_pi(_spec(), fake)

    assert result.text == "Fix applied."
    assert result.subtype == "success"
    assert result.ok is True
    assert result.session_id == "pi-1"
    assert isinstance(result, RunResult)
    assert result.duration_seconds >= 0


def test_run_text_fallback_to_deltas_when_no_message_end():
    """A run that streams deltas but no message_end falls back to the deltas.

    pi_fake emits a success stream WITH a message_end, so use a controlled
    mock process: deltas only, no message_end, exit 0.
    """
    stream = _jsonl(
        {"type": "session", "id": "pi-d", "version": 3},
        {"type": "agent_start"},
        {"type": "message_update",
         "assistantMessageEvent": {"type": "text_delta", "contentIndex": 0, "delta": "Par"}},
        {"type": "message_update",
         "assistantMessageEvent": {"type": "text_delta", "contentIndex": 0, "delta": "tial"}},
        {"type": "agent_end"},
    )
    proc = _mock_process(stdout=stream, returncode=0)

    async def _run():
        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
            return await PiBackend().run(_spec())

    result = asyncio.run(_run())
    assert result.text == "Partial"
    assert result.subtype == "success"


def test_run_message_end_wins_over_deltas():
    """When both a delta and a message_end carry text, message_end wins (no mixing)."""
    stream = _jsonl(
        {"type": "session", "id": "pi-w", "version": 3},
        {"type": "message_update",
         "assistantMessageEvent": {"type": "text_delta", "contentIndex": 0, "delta": "stale"}},
        {"type": "message_end",
         "message": {"role": "assistant", "content": [{"type": "text", "text": "Authoritative"}]}},
    )
    proc = _mock_process(stdout=stream, returncode=0)

    async def _run():
        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
            return await PiBackend().run(_spec())

    result = asyncio.run(_run())
    assert result.text == "Authoritative"


def test_run_multi_block_text_reassembled_in_order():
    """A multi-block message (contentIndex 1 then 0) reassembles in index order."""
    stream = _jsonl(
        {"type": "session", "id": "pi-m", "version": 3},
        {"type": "message_update",
         "assistantMessageEvent": {"type": "text_delta", "contentIndex": 1, "delta": "second"}},
        {"type": "message_update",
         "assistantMessageEvent": {"type": "text_delta", "contentIndex": 0, "delta": "first"}},
        {"type": "agent_end"},
    )
    proc = _mock_process(stdout=stream, returncode=0)

    async def _run():
        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
            return await PiBackend().run(_spec())

    result = asyncio.run(_run())
    assert result.text == "first\nsecond"


# ---------- End-to-end: session id ----------


def test_run_session_id_from_header():
    from tests.fakes.pi_fake import PiFake

    fake = PiFake()
    fake.script_response("ok", session_id="pi-header")
    result, _ = _run_pi(_spec(), fake)
    assert result.session_id == "pi-header"


def test_run_session_id_header_wins_over_pinned():
    """If the header echoes a different id than we requested, the header wins."""
    stream = _jsonl(
        {"type": "session", "id": "header-id", "version": 3},
        {"type": "message_end",
         "message": {"role": "assistant", "content": [{"type": "text", "text": "ok"}]}},
    )
    proc = _mock_process(stdout=stream, returncode=0)

    async def _run():
        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
            return await PiBackend().run(_spec())

    result = asyncio.run(_run())
    assert result.session_id == "header-id"


def test_run_session_id_survives_premature_death():
    """No session header (process dies immediately) → the pinned id survives.

    Fresh run: pinned_id is a fresh uuid4 pre-seeded into the accumulator, so
    RunResult.session_id is still meaningful even with an empty stream.
    """
    proc = _mock_process(stdout="", returncode=-9)

    async def _run():
        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
            return await PiBackend().run(_spec())

    result = asyncio.run(_run())
    assert result.subtype == "killed"
    assert result.session_id  # non-empty: the pre-seeded uuid4


def test_run_resume_session_id_is_resumed_id():
    """A resume pre-seeds the resumed session id (not a fresh uuid4)."""
    proc = _mock_process(stdout="", returncode=0)

    async def _run():
        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
            return await PiBackend().run(_spec(resume="resumed-id-xyz"))

    result = asyncio.run(_run())
    assert result.session_id == "resumed-id-xyz"


def test_run_fork_session_id_is_new_not_source():
    """A fork pre-seeds a NEW uuid4, not the source session we branched from."""
    proc = _mock_process(stdout="", returncode=0)

    async def _run():
        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
            return await PiBackend().run(_spec(resume="source-id", fork_session=True))

    result = asyncio.run(_run())
    assert result.session_id
    assert result.session_id != "source-id"


# ---------- End-to-end: cost ----------


def test_run_cost_from_usage_total():
    from tests.fakes.pi_fake import PiFake

    fake = PiFake()
    fake.script_response("ok", session_id="pi-cost", cost_total=0.42)
    result, _ = _run_pi(_spec(), fake)
    assert result.cost_usd == 0.42


def test_run_cost_none_when_unreported():
    from tests.fakes.pi_fake import PiFake

    fake = PiFake()
    fake.script_response("ok", session_id="pi-nocost", cost_total=None)
    result, _ = _run_pi(_spec(), fake)
    assert result.cost_usd is None


def test_run_cost_from_agent_end():
    """The final agent_end carries the authoritative run-wide cost."""
    stream = _jsonl(
        {"type": "session", "id": "pi-cost2", "version": 3},
        {"type": "message_end",
         "message": {"role": "assistant", "content": [{"type": "text", "text": "ok"}]}},
        {"type": "agent_end", "usage": {"cost": {"total": 3.14}}, "messages": []},
    )
    proc = _mock_process(stdout=stream, returncode=0)

    async def _run():
        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
            return await PiBackend().run(_spec())

    result = asyncio.run(_run())
    assert result.cost_usd == 3.14


# ---------- Subtype matrix ----------


def test_run_subtype_success():
    from tests.fakes.pi_fake import PiFake
    fake = PiFake()
    fake.script_response("ok", session_id="s")
    result, _ = _run_pi(_spec(), fake)
    assert result.subtype == "success"
    assert result.ok is True


def test_run_subtype_error_on_nonzero_exit():
    proc = _mock_process(stdout="", returncode=2)

    async def _run():
        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
            return await PiBackend().run(_spec())

    result = asyncio.run(_run())
    assert result.subtype == "error"
    assert result.ok is False


def test_run_subtype_error_on_instream_error_rc0():
    """rc 0 + in-stream extension_error → subtype error (the has_error path)."""
    from tests.fakes.pi_fake import PiFake
    fake = PiFake()
    fake.script_fail(error_msg="quota exceeded")
    result, _ = _run_pi(_spec(), fake)
    assert result.subtype == "error"
    assert result.ok is False


def test_run_subtype_killed():
    from tests.fakes.pi_fake import PiFake
    fake = PiFake()
    fake.script_killed(session_id="s")
    result, _ = _run_pi(_spec(), fake)
    assert result.subtype == "killed"


def test_run_subtype_killed_text_fallback():
    """A killed run still reassembles its partial streamed text from deltas."""
    from tests.fakes.pi_fake import PiFake
    fake = PiFake()
    fake.script_killed(session_id="s", partial_text="Half done,")
    result, _ = _run_pi(_spec(), fake)
    assert result.subtype == "killed"
    assert result.text == "Half done,"


def test_run_iserror_tool_flips_success_to_error():
    """A tool result with isError: true flips an rc-0 run to subtype error.

    This is the documented tradeoff (memory: pi-backend-iserror-tradeoff): any
    failing tool, even a routine nonzero-exit grep, marks the run as errored.
    """
    stream = _jsonl(
        {"type": "session", "id": "pi-tool", "version": 3},
        {"type": "tool_execution_end",
         "toolCallId": "t1", "toolName": "bash", "args": {"command": "ls"}, "isError": True},
        {"type": "message_end",
         "message": {"role": "assistant", "content": [{"type": "text", "text": "done"}]}},
    )
    proc = _mock_process(stdout=stream, returncode=0)

    async def _run():
        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
            return await PiBackend().run(_spec())

    result = asyncio.run(_run())
    assert result.subtype == "error"
    assert result.text == "done"


# ---------- Timeout / kill ----------


def test_run_timeout_kills_and_raises():
    """asyncio.TimeoutError propagates after killing the process."""
    spec = _spec(timeout=0.05)

    proc = _mock_process(stdout="", returncode=-9)
    proc.killed = False

    async def blocking_read():
        await asyncio.sleep(999)

    proc.stdout.readline = blocking_read
    proc.stderr.read = AsyncMock(return_value=b"")

    async def _run():
        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
            return await PiBackend().run(spec)

    try:
        asyncio.run(_run())
        assert False, "Should have raised TimeoutError"
    except asyncio.TimeoutError:
        pass
    assert proc.killed is True


# ---------- Stream-size bounding ----------


def test_run_stdout_bound_truncates_and_errors(monkeypatch):
    """stdout exceeding _MAX_STREAM_BYTES sets the error flag → subtype error."""
    stream = _jsonl(
        {"type": "session", "id": "pi-big", "version": 3},
    )
    for _ in range(2000):
        stream += json.dumps({
            "type": "message_end",
            "message": {"role": "assistant",
                        "content": [{"type": "text", "text": "x" * 50}]},
        }) + "\n"

    proc = _mock_process(stdout=stream, returncode=0)
    small_limit = 500

    async def _run():
        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
            monkeypatch.setattr(_pi_mod, "_MAX_STREAM_BYTES", small_limit)
            return await PiBackend().run(_spec())

    result = asyncio.run(_run())
    assert result.subtype == "error"
    # Partial text collected before the limit.
    assert result.text


def test_run_stdout_bound_within_limit():
    """A small stream completes without hitting the limit."""
    stream = _jsonl(
        {"type": "session", "id": "pi-sm", "version": 3},
        {"type": "message_end",
         "message": {"role": "assistant", "content": [{"type": "text", "text": "ok"}]}},
        {"type": "agent_end"},
    )
    proc = _mock_process(stdout=stream, returncode=0)

    async def _run():
        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
            return await PiBackend().run(_spec())

    result = asyncio.run(_run())
    assert result.subtype == "success"
    assert result.session_id == "pi-sm"


def test_run_stderr_bound_truncates_no_crash(monkeypatch):
    """stderr exceeding the bound is truncated; the run still succeeds."""
    stream = _jsonl(
        {"type": "session", "id": "pi-err", "version": 3},
        {"type": "message_end",
         "message": {"role": "assistant", "content": [{"type": "text", "text": "ok"}]}},
    )
    proc = _mock_process(stdout=stream, stderr="X" * (64 * 1024), returncode=0)

    async def _run():
        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
            monkeypatch.setattr(_pi_mod, "_MAX_STREAM_BYTES", 1024)
            return await PiBackend().run(_spec())

    result = asyncio.run(_run())
    assert result.subtype == "success"


# ---------- Failure surfaces ----------


def test_run_not_found_raises_runtime_error():
    async def _run():
        with patch("asyncio.create_subprocess_exec",
                   AsyncMock(side_effect=FileNotFoundError("pi"))):
            return await PiBackend().run(_spec())

    with pytest.raises(RuntimeError) as exc:
        asyncio.run(_run())
    assert "pi" in str(exc.value).lower()
    assert "npm" in str(exc.value)


def test_run_spawn_permission_error_wrapped_as_oserror():
    """A PermissionError at spawn time is surfaced under the retryable OSError set."""
    async def _run():
        with patch("asyncio.create_subprocess_exec",
                   AsyncMock(side_effect=PermissionError("denied"))):
            return await PiBackend().run(_spec())

    with pytest.raises(OSError):
        asyncio.run(_run())


def test_run_missing_model_raises():
    """When spec.model is empty, run fails fast (no hardcoded default)."""
    spec = _spec()
    spec.model = None
    with pytest.raises(ValueError, match="missing required 'model'"):
        asyncio.run(PiBackend().run(spec))


# ---------- Subprocess invocation details ----------


def test_run_passes_cwd():
    """The subprocess is launched with cwd=spec.cwd (pi has no -C flag)."""
    proc = _mock_process(stdout=_jsonl(
        {"type": "session", "id": "s", "version": 3},
        {"type": "message_end",
         "message": {"role": "assistant", "content": [{"type": "text", "text": "ok"}]}},
    ), returncode=0)

    async def _run():
        mock_exec = AsyncMock(return_value=proc)
        with patch("asyncio.create_subprocess_exec", mock_exec):
            await PiBackend().run(_spec(cwd="/tmp/worktree"))
        return mock_exec

    mock_exec = asyncio.run(_run())
    assert mock_exec.call_args[1]["cwd"] == "/tmp/worktree"
    # pi does not use a -C flag (unlike Codex) — cwd is passed as a kwarg.
    assert "-C" not in mock_exec.call_args[0]


def test_run_env_agent_dir_maps_to_pi_coding_agent_dir(monkeypatch):
    """The agent_dir profile field maps to PI_CODING_AGENT_DIR."""
    proc = _mock_process(stdout=_jsonl(
        {"type": "session", "id": "s", "version": 3},
        {"type": "message_end",
         "message": {"role": "assistant", "content": [{"type": "text", "text": "ok"}]}},
    ), returncode=0)

    async def _run():
        mock_exec = AsyncMock(return_value=proc)
        spec = _spec(state={"_harness_cfg": {
            "backend": "pi", "model": MODEL, "agent_dir": "/tmp/agent-cfg"}})
        with patch("asyncio.create_subprocess_exec", mock_exec):
            await PiBackend().run(spec)
        return mock_exec.call_args[1]["env"]

    env = asyncio.run(_run())
    assert env["PI_CODING_AGENT_DIR"] == "/tmp/agent-cfg"


def test_run_env_agent_dir_absent_leaves_env_unset(monkeypatch):
    """No agent_dir field → PI_CODING_AGENT_DIR is not injected."""
    proc = _mock_process(stdout=_jsonl(
        {"type": "session", "id": "s", "version": 3},
        {"type": "message_end",
         "message": {"role": "assistant", "content": [{"type": "text", "text": "ok"}]}},
    ), returncode=0)

    async def _run():
        mock_exec = AsyncMock(return_value=proc)
        spec = _spec(state={"_harness_cfg": {"backend": "pi", "model": MODEL}})
        with patch("asyncio.create_subprocess_exec", mock_exec):
            await PiBackend().run(spec)
        return mock_exec.call_args[1]["env"]

    env = asyncio.run(_run())
    assert "PI_CODING_AGENT_DIR" not in env


def test_run_env_agent_dir_loses_to_profile_env(monkeypatch):
    """Precedence: profile `env` beats the agent_dir field on the same key.

    agent_dir maps to PI_CODING_AGENT_DIR but sits below profile `env`, so an
    operator can still redirect pi's config via
    ``"env": {"PI_CODING_AGENT_DIR": ...}``.
    """
    proc = _mock_process(stdout=_jsonl(
        {"type": "session", "id": "s", "version": 3},
        {"type": "message_end",
         "message": {"role": "assistant", "content": [{"type": "text", "text": "ok"}]}},
    ), returncode=0)

    async def _run():
        mock_exec = AsyncMock(return_value=proc)
        spec = _spec(state={"_harness_cfg": {
            "backend": "pi", "model": MODEL,
            "agent_dir": "/from/agent_dir",
            "env": {"PI_CODING_AGENT_DIR": "/from/profile_env"},
        }})
        with patch("asyncio.create_subprocess_exec", mock_exec):
            await PiBackend().run(spec)
        return mock_exec.call_args[1]["env"]

    env = asyncio.run(_run())
    assert env["PI_CODING_AGENT_DIR"] == "/from/profile_env"


def test_run_env_overrides_beat_profile_env_and_agent_dir(monkeypatch):
    """spec.env_overrides is the highest-precedence source on a shared key."""
    proc = _mock_process(stdout=_jsonl(
        {"type": "session", "id": "s", "version": 3},
        {"type": "message_end",
         "message": {"role": "assistant", "content": [{"type": "text", "text": "ok"}]}},
    ), returncode=0)

    async def _run():
        mock_exec = AsyncMock(return_value=proc)
        spec = _spec(
            env_overrides={"PI_CODING_AGENT_DIR": "/from/overrides"},
            state={"_harness_cfg": {
                "backend": "pi", "model": MODEL, "agent_dir": "/from/agent_dir"}},
        )
        with patch("asyncio.create_subprocess_exec", mock_exec):
            await PiBackend().run(spec)
        return mock_exec.call_args[1]["env"]

    env = asyncio.run(_run())
    assert env["PI_CODING_AGENT_DIR"] == "/from/overrides"


def test_run_env_profile_env_and_overrides_precedence(monkeypatch):
    """Env precedence: os.environ < agent_dir < profile 'env' < spec.env_overrides."""
    monkeypatch.setenv("_PI_TEST_VAR", "os-env")
    proc = _mock_process(stdout=_jsonl(
        {"type": "session", "id": "s", "version": 3},
        {"type": "message_end",
         "message": {"role": "assistant", "content": [{"type": "text", "text": "ok"}]}},
    ), returncode=0)

    async def _run():
        mock_exec = AsyncMock(return_value=proc)
        spec = _spec(
            state={"_harness_cfg": {
                "backend": "pi", "model": MODEL,
                "env": {"_PI_TEST_VAR": "profile-env", "ONLY_PROFILE": "p"}}},
            env_overrides={"_PI_TEST_VAR": "spec-override"},
        )
        with patch("asyncio.create_subprocess_exec", mock_exec):
            await PiBackend().run(spec)
        return mock_exec.call_args[1]["env"]

    env = asyncio.run(_run())
    # spec.env_overrides beats profile 'env'
    assert env["_PI_TEST_VAR"] == "spec-override"
    # profile 'env' var passes through
    assert env["ONLY_PROFILE"] == "p"


def test_run_api_key_not_injected_as_env(monkeypatch):
    """The api key is passed via --api-key flag, not guessed as a provider env var."""
    proc = _mock_process(stdout=_jsonl(
        {"type": "session", "id": "s", "version": 3},
        {"type": "message_end",
         "message": {"role": "assistant", "content": [{"type": "text", "text": "ok"}]}},
    ), returncode=0)

    async def _run():
        mock_exec = AsyncMock(return_value=proc)
        spec = _spec(state={"_harness_cfg": {
            "backend": "pi", "model": MODEL, "api_key": "sk-secret"}})
        with patch("asyncio.create_subprocess_exec", mock_exec):
            await PiBackend().run(spec)
        return mock_exec

    mock_exec = asyncio.run(_run())
    argv = mock_exec.call_args[0]
    assert "sk-secret" in argv  # the --api-key flag carries it
    env = mock_exec.call_args[1]["env"]
    # It must NOT be injected under a guessed provider env var name.
    assert env.get("ANTHROPIC_API_KEY") != "sk-secret"


# ---------- Phase 1: agent-dir mcp.json + comment-server env routing ----------


def _mcp_spec(comment_env=None, agent_dir="/tmp/agent-cfg-mcp"):
    """A spec whose mcp_servers names autoswe_comment with a per-task env block."""
    env = {"AUTOSWE_COMMENT_ID": "999", "AUTOSWE_PROVIDER": "github",
           "AUTOSWE_TOKEN": "ghp_tok", "AUTOSWE_SUPPRESS_POSTING": "1"}
    if comment_env is not None:
        env = comment_env
    return _spec(
        state={"_harness_cfg": {"backend": "pi", "model": MODEL, "agent_dir": agent_dir}},
        mcp_servers={"autoswe_comment": {"command": sys.executable, "args": ["-m", "x"],
                                         "env": env}},
    )


def test_pi_mcp_comment_env_routed_into_subprocess_env():
    """The autoswe_comment server env is merged into the pi subprocess env.

    Phase 1 routes the server's env into the subprocess (the pi-mcp-adapter
    inherits pi's process env into the server child) rather than into the
    mcp.json file — so the file never carries per-task values.
    """
    proc = _mock_process(stdout=_jsonl(
        {"type": "session", "id": "s", "version": 3},
        {"type": "message_end",
         "message": {"role": "assistant", "content": [{"type": "text", "text": "ok"}]}},
    ), returncode=0)

    async def _run():
        mock_exec = AsyncMock(return_value=proc)
        with patch("asyncio.create_subprocess_exec", mock_exec):
            await PiBackend().run(_mcp_spec())
        return mock_exec.call_args[1]["env"]

    env = asyncio.run(_run())
    assert env["AUTOSWE_COMMENT_ID"] == "999"
    assert env["AUTOSWE_PROVIDER"] == "github"
    assert env["AUTOSWE_TOKEN"] == "ghp_tok"
    assert env["AUTOSWE_SUPPRESS_POSTING"] == "1"


def test_pi_mcp_no_comment_server_no_env_route():
    """Without autoswe_comment in mcp_servers, no comment env is routed."""
    proc = _mock_process(stdout=_jsonl(
        {"type": "session", "id": "s", "version": 3},
        {"type": "message_end",
         "message": {"role": "assistant", "content": [{"type": "text", "text": "ok"}]}},
    ), returncode=0)

    async def _run():
        mock_exec = AsyncMock(return_value=proc)
        spec = _spec(state={"_harness_cfg": {"backend": "pi", "model": MODEL}})
        # A different MCP server only — not autoswe_comment.
        spec.mcp_servers = {"other_server": {"command": "x", "env": {"FOO": "bar"}}}
        with patch("asyncio.create_subprocess_exec", mock_exec):
            await PiBackend().run(spec)
        return mock_exec.call_args[1]["env"]

    env = asyncio.run(_run())
    # No autoswe_comment env routed. (FOO is not routed either — only the
    # autoswe_comment server's env is in scope for Phase 1.)
    assert "AUTOSWE_COMMENT_ID" not in env
    assert "AUTOSWE_SUPPRESS_POSTING" not in env


def test_pi_mcp_writes_agent_dir_mcp_json(tmp_path):
    """When autoswe_comment is present, <agent dir>/mcp.json is written with the server.

    The file carries only stable values (python path, repo root) — no per-task
    env. It merges with any pre-existing file, preserving operator entries.
    """
    agent_dir = tmp_path / "agent"
    agent_dir.mkdir()
    proc = _mock_process(stdout=_jsonl(
        {"type": "session", "id": "s", "version": 3},
        {"type": "message_end",
         "message": {"role": "assistant", "content": [{"type": "text", "text": "ok"}]}},
    ), returncode=0)

    async def _run():
        mock_exec = AsyncMock(return_value=proc)
        spec = _mcp_spec(agent_dir=str(agent_dir))
        with patch("asyncio.create_subprocess_exec", mock_exec):
            await PiBackend().run(spec)

    asyncio.run(_run())
    mcp_json = agent_dir / "mcp.json"
    assert mcp_json.exists()
    data = json.loads(mcp_json.read_text())
    server = data["mcpServers"]["autoswe_comment"]
    assert server["command"] == sys.executable
    assert server["args"] == ["-m", "mcp_servers.autoswe_comment_server"]
    assert server["toolPrefix"] == "mcp"
    assert server["directTools"] == ["post_plan", "post_question", "update_progress"]
    # Stable values only — no per-task env leaked into the file.
    assert "env" not in server
    assert data["settings"] == {"freezeDirectTools": True, "sampling": False, "elicitation": False}


def test_pi_mcp_merges_existing_agent_dir_mcp_json(tmp_path):
    """A pre-existing mcp.json's other servers and settings are preserved."""
    agent_dir = tmp_path / "agent"
    agent_dir.mkdir()
    agent_dir.joinpath("mcp.json").write_text(json.dumps({
        "mcpServers": {"other_server": {"command": "other", "args": []}},
        "settings": {"toolPrefix": "server"},
    }))
    proc = _mock_process(stdout=_jsonl(
        {"type": "session", "id": "s", "version": 3},
        {"type": "message_end",
         "message": {"role": "assistant", "content": [{"type": "text", "text": "ok"}]}},
    ), returncode=0)

    async def _run():
        mock_exec = AsyncMock(return_value=proc)
        spec = _mcp_spec(agent_dir=str(agent_dir))
        with patch("asyncio.create_subprocess_exec", mock_exec):
            await PiBackend().run(spec)

    asyncio.run(_run())
    data = json.loads((agent_dir / "mcp.json").read_text())
    # The operator's other server survives the merge.
    assert "other_server" in data["mcpServers"]
    # autoSWE adds its own.
    assert "autoswe_comment" in data["mcpServers"]
    # Settings are merged: operator's toolPrefix kept, autoSWE's flags added.
    assert data["settings"]["toolPrefix"] == "server"
    assert data["settings"]["freezeDirectTools"] is True


def test_pi_mcp_write_helper_no_agent_dir_is_noop(tmp_path):
    """_write_pi_mcp_json('') is a no-op — no agent_dir means no file written.

    When the agent_dir profile field is unset, pi's config lives in the default
    ~/.pi/agent; autoSWE does not relocate or write there.
    """
    from autoswe.harness.backends.pi import _write_pi_mcp_json

    # A blank agent_dir is a no-op: it must not raise or create anything.
    _write_pi_mcp_json("")
    _write_pi_mcp_json("   ")
    # Nothing was created in the temp dir.
    assert not (tmp_path / "mcp.json").exists()


def test_pi_mcp_env_routed_even_without_agent_dir():
    """The server env is routed into the subprocess even when agent_dir is unset.

    Routing and the file write are independent: the env always reaches the
    server child via the process env; only the file needs an agent dir.
    """
    proc = _mock_process(stdout=_jsonl(
        {"type": "session", "id": "s", "version": 3},
        {"type": "message_end",
         "message": {"role": "assistant", "content": [{"type": "text", "text": "ok"}]}},
    ), returncode=0)

    async def _run():
        mock_exec = AsyncMock(return_value=proc)
        spec = _spec(
            state={"_harness_cfg": {"backend": "pi", "model": MODEL}},  # no agent_dir
            mcp_servers={"autoswe_comment": {"command": sys.executable,
                                             "args": [], "env": {"AUTOSWE_COMMENT_ID": "777"}}},
        )
        with patch("asyncio.create_subprocess_exec", mock_exec):
            await PiBackend().run(spec)
        return mock_exec.call_args[1]["env"]

    env = asyncio.run(_run())
    assert env["AUTOSWE_COMMENT_ID"] == "777"


# ---------- Progress / MCP / misc result fields ----------


def test_run_progress_callback_fires_tool_and_agent_lines():
    from tests.fakes.pi_fake import PiFake

    fake = PiFake()
    fake.script_response("did it", session_id="s")
    cb = Mock()
    spec = _spec(progress_callback=cb)
    result, _ = _run_pi(spec, fake)

    fired = [c[0][0] for c in cb.call_args_list]
    # The assistant message_end fires an "Agent:" line; the text delta fires a
    # progress line too.
    assert any("Agent:" in line for line in fired)
    assert result.text == "did it"


def test_run_result_mcp_fields_default_false():
    """Without autoswe_comment tool calls, the MCP flags stay False.

    (plan_posted/question_posted now come from the stream when the comment
    server is active; a run that never calls those tools reports them False.)
    """
    from tests.fakes.pi_fake import PiFake

    fake = PiFake()
    fake.script_response("ok", session_id="s")
    result, _ = _run_pi(_spec(), fake)

    assert result.plan_posted is False
    assert result.question_posted is False
    assert result.plan_file_path is None
    assert result.structured_output is None


def test_run_mcp_post_plan_event_sets_plan_posted():
    """End-to-end: a direct post_plan event on the stream sets RunResult.plan_posted."""
    events = _jsonl(
        {"type": "session", "id": "s", "version": 3},
        {"type": "tool_execution_start",
         "toolCallId": "chatcmpl-tool-1",
         "toolName": "mcp__autoswe_comment_post_plan",
         "args": {"body": "1. Do the thing"}},
        {"type": "message_end",
         "message": {"role": "assistant", "content": [{"type": "text", "text": "done"}]}},
        {"type": "agent_end"},
    )
    proc = _mock_process(stdout=events, returncode=0)

    async def _run():
        mock_exec = AsyncMock(return_value=proc)
        with patch("asyncio.create_subprocess_exec", mock_exec):
            return await PiBackend().run(_spec_with_comment_mcp(mode="plan"))

    result = asyncio.run(_run())
    assert result.plan_posted is True
    assert result.question_posted is False
    assert result.ok is True


def test_run_mcp_post_question_event_sets_question_posted():
    """End-to-end: a proxy post_question event sets RunResult.question_posted."""
    events = _jsonl(
        {"type": "session", "id": "s", "version": 3},
        {"type": "tool_execution_start",
         "toolName": "mcp__autoswe_comment",
         "args": {"tool": "post_question", "args": {"body": "Which DB?"}}},
        {"type": "agent_end"},
    )
    proc = _mock_process(stdout=events, returncode=0)

    async def _run():
        mock_exec = AsyncMock(return_value=proc)
        with patch("asyncio.create_subprocess_exec", mock_exec):
            return await PiBackend().run(_spec_with_comment_mcp(mode="plan"))

    result = asyncio.run(_run())
    assert result.question_posted is True
    assert result.plan_posted is False


def test_run_mcp_update_progress_fires_callback_with_body():
    """End-to-end: update_progress forwards its body to the progress callback."""
    events = _jsonl(
        {"type": "session", "id": "s", "version": 3},
        {"type": "tool_execution_start",
         "toolName": "mcp__autoswe_comment_update_progress",
         "args": {"body": "Editing: src/foo.py"}},
        {"type": "agent_end"},
    )
    proc = _mock_process(stdout=events, returncode=0)
    cb = Mock()

    async def _run():
        mock_exec = AsyncMock(return_value=proc)
        spec = _spec_with_comment_mcp(progress_callback=cb)
        with patch("asyncio.create_subprocess_exec", mock_exec):
            return await PiBackend().run(spec)

    asyncio.run(_run())
    fired = [c[0][0] for c in cb.call_args_list]
    assert any("Editing: src/foo.py" in line for line in fired)


def test_run_mcp_tools_in_allowlist_when_server_named(monkeypatch):
    """When the server is named, the three tools are on the --tools allowlist."""
    monkeypatch.setattr(_pi_mod.os, "name", "posix")
    events = _jsonl({"type": "session", "id": "s", "version": 3}, {"type": "agent_end"})
    proc = _mock_process(stdout=events, returncode=0)

    async def _run():
        mock_exec = AsyncMock(return_value=proc)
        with patch("asyncio.create_subprocess_exec", mock_exec):
            await PiBackend().run(_spec_with_comment_mcp(mode="plan"))
        argv = mock_exec.call_args[0]
        return argv[argv.index("--tools") + 1]

    tools_val = asyncio.run(_run())
    tools = tools_val.split(",")
    for name in _pi_mod._MCP_COMMENT_TOOL_NAMES:
        assert name in tools
    # The read-only plan base set is still present (MCP tools are additive).
    assert "read" in tools


def test_run_mcp_tools_absent_when_server_not_named(monkeypatch):
    """Without the server, the MCP tools are not on the allowlist."""
    monkeypatch.setattr(_pi_mod.os, "name", "posix")
    events = _jsonl({"type": "session", "id": "s", "version": 3}, {"type": "agent_end"})
    proc = _mock_process(stdout=events, returncode=0)

    async def _run():
        mock_exec = AsyncMock(return_value=proc)
        with patch("asyncio.create_subprocess_exec", mock_exec):
            await PiBackend().run(_spec(mode="plan"))
        argv = mock_exec.call_args[0]
        return argv[argv.index("--tools") + 1].split(",")

    tools = asyncio.run(_run())
    for name in _pi_mod._MCP_COMMENT_TOOL_NAMES:
        assert name not in tools


def test_run_multiple_responses_in_order():
    from tests.fakes.pi_fake import PiFake

    fake = PiFake()
    fake.script_response("first", session_id="a")
    fake.script_response("second", session_id="b")
    spec = _spec()

    async def _run():
        with fake:
            backend = PiBackend()
            r1 = await backend.run(spec)
            r2 = await backend.run(spec)
            return r1, r2

    r1, r2 = asyncio.run(_run())
    assert r1.text == "first" and r1.session_id == "a"
    assert r2.text == "second" and r2.session_id == "b"
    assert len(fake.calls) == 2
