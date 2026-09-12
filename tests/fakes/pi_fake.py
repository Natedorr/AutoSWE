"""Scripted pi backend fake — subprocess level.

Replaces ``asyncio.create_subprocess_exec`` with a stub that returns a
prebuilt ``FakeProcess`` feeding ``--mode json`` event lines crafted to
exercise the real ``PiBackend`` stream parser (``_parse_line`` in
``autoswe/harness/backends/pi.py``).  Each call records the parsed command
in ``.calls`` for flag/session/tool assertions.

The emitted lines are *real* ``--mode json`` event shapes (session header,
agent/turn lifecycle, message_start/update/end, tool_execution_*,
agent_end, cumulative ``usage``) so the genuine parser runs unmodified —
the same fidelity contract as ``CodexFake``.

Builder signatures mirror ``ClaudeFake``/``CodexFake`` so the existing
transition-row ``claude_responses`` / ``codex_responses`` dicts can be fed
verbatim: ``script_response``, ``script_plan``, ``script_questions``,
``script_fix``, ``script_fail``, ``script_killed``.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

# Capture the real function at import time — before any test can patch.
# This is the only reference to the genuine function; patch/unpatch use it
# so the value is stable regardless of how many times the attribute is
# monkeypatched during the test run.
_REAL_CREATE = asyncio.create_subprocess_exec

# A deterministic timestamp for the session header (no Date.now in fakes —
# keeps emitted streams byte-stable across runs).
_FAKE_TIMESTAMP = "2026-01-01T00:00:00.000Z"


# ---------------------------------------------------------------------------
# JSONL line builders


def _event(obj: dict) -> str:
    """Serialize a ``--mode json`` event line."""
    return json.dumps(obj)


def _session_header(session_id: str, cwd: str = "/tmp") -> dict:
    """The first line of every ``--mode json`` stream (docs/pi/json.md)."""
    return {
        "type": "session",
        "version": 3,
        "id": session_id,
        "timestamp": _FAKE_TIMESTAMP,
        "cwd": cwd,
    }


def _usage(cost_total: float | None) -> dict | None:
    """A cumulative usage block carrying provider-reported cost.total.

    pi reports cost, not token estimates (docs/pi/json.md): the top-level
    ``usage`` field is the "latest cumulative provider-reported usage".
    Returns None when no cost is being reported so callers can omit the key
    entirely (mirrors a provider that only reports usage at completion).
    """
    if cost_total is None:
        return None
    return {"input": 10, "output": 5, "cost": {"total": cost_total}}


def _tool_execution_start(tool_name: str, body: str,
                          tool_call_id: str = "chatcmpl-tool-1") -> dict:
    """A canonical ``tool_execution_start`` event (spike-pi-mcp.md, fact 1/3).

    ``args`` carries ``body`` verbatim — the direct autoswe_comment tool shape.
    """
    return {
        "type": "tool_execution_start",
        "toolCallId": tool_call_id,
        "toolName": tool_name,
        "args": {"body": body},
    }


def _mcp_comment_tool_event(tool: str, body: str, proxy: str = "direct") -> dict:
    """A ``tool_execution_start`` for the autoswe_comment *tool* in *proxy* shape.

    ``proxy``:
      * ``"direct"``    → toolName is ``mcp__autoswe_comment_<tool>``, args = {body}
      * ``"generic"``   → toolName is ``"mcp"``, args = {tool, args: {body}}
      * ``"namespace"`` → toolName is ``"mcp__autoswe_comment"``, args = {tool, args: {body}}

    All three are the shapes the real parser must classify as the same call
    (Phase 2 of PLAN-pi-mcp.md).
    """
    if proxy == "direct":
        return _tool_execution_start(f"mcp__autoswe_comment_{tool}", body)
    tool_name = "mcp" if proxy == "generic" else "mcp__autoswe_comment"
    return {
        "type": "tool_execution_start",
        "toolCallId": "chatcmpl-tool-1",
        "toolName": tool_name,
        "args": {"tool": tool, "args": {"body": body}},
    }


def _build_success_jsonl(session_id: str, text: str,
                         cost_total: float | None = None,
                         tool_event: dict | None = None) -> list[str]:
    """``--mode json`` lines for a successful run yielding *text*.

    Mirrors the canonical stream (docs/pi/json.md Output Format):
    session header → agent_start → turn_start → message_start →
    message_update (delta-only, carries cumulative usage) → message_end
    (authoritative message) → turn_end → agent_end.

    When *tool_event* is given, it is emitted as a ``tool_execution_start``
    (the Phase 2 autoswe_comment shape) right before the message blocks, so
    the real parser sets the plan_posted / question_posted flags from it.
    """
    lines: list[str] = []
    lines.append(_event(_session_header(session_id)))
    lines.append(_event({"type": "agent_start"}))
    lines.append(_event({"type": "turn_start"}))
    if tool_event is not None:
        lines.append(_event(tool_event))
    lines.append(_event({
        "type": "message_start",
        "message": {"role": "assistant", "content": []},
    }))
    # message_update is delta-only.  Capture the latest cost from the
    # top-level usage block, then handle the text delta.
    if text:
        update: dict = {
            "type": "message_update",
            "assistantMessageEvent": {
                "type": "text_delta",
                "contentIndex": 0,
                "delta": text,
            },
        }
        usage = _usage(cost_total)
        if usage is not None:
            update["usage"] = usage
        lines.append(_event(update))
    # message_end carries the final authoritative assistant message.
    message = {"role": "assistant",
               "content": [{"type": "text", "text": text}] if text else []}
    end: dict = {"type": "message_end", "message": message}
    usage = _usage(cost_total)
    if usage is not None:
        end["usage"] = usage
    lines.append(_event(end))
    lines.append(_event({"type": "turn_end", "message": message, "toolResults": []}))
    lines.append(_event({"type": "agent_end", "messages": [message]}))
    return lines


def _build_error_jsonl(session_id: str, error_msg: str = "error") -> list[str]:
    """``--mode json`` lines for a run that failed mid-stream.

    An in-stream ``extension_error`` with exit 0 drives the parser's
    ``has_error`` flag → subtype "error" (rc 0 + has_error → error).  No
    agent_end is emitted, matching the "interrupted before completion" shape.
    """
    lines: list[str] = []
    lines.append(_event(_session_header(session_id)))
    lines.append(_event({"type": "agent_start"}))
    lines.append(_event({"type": "extension_error", "error": error_msg}))
    return lines


def _build_killed_jsonl(session_id: str, partial_text: str = "") -> list[str]:
    """``--mode json`` lines for a run killed before it emitted message_end.

    Emits the session header plus an in-progress assistant message with a
    text delta and no completion.  With a negative returncode the parser
    yields subtype "killed" and reassembles the partial text from the
    accumulated deltas (the message_end authoritative path is never reached).
    """
    lines: list[str] = []
    lines.append(_event(_session_header(session_id)))
    lines.append(_event({"type": "agent_start"}))
    lines.append(_event({"type": "turn_start"}))
    lines.append(_event({
        "type": "message_start",
        "message": {"role": "assistant", "content": []},
    }))
    if partial_text:
        lines.append(_event({
            "type": "message_update",
            "assistantMessageEvent": {
                "type": "text_delta",
                "contentIndex": 0,
                "delta": partial_text,
            },
        }))
    return lines


def _build_text_jsonl(session_id: str, text: str, subtype: str,
                      cost_total: float | None = None,
                      error_msg: str = "error",
                      tool_event: dict | None = None) -> list[str]:
    """Route to the success or error builder based on *subtype*."""
    if subtype == "success":
        return _build_success_jsonl(session_id, text, cost_total, tool_event)
    # error, error_max_turns, permission_denied → in-stream error, exit 0
    return _build_error_jsonl(session_id, error_msg)


# ---------------------------------------------------------------------------
# Fake async subprocess plumbing


class FakeStreamReader:
    """Async streamreader feeding lines from a prebuilt list."""

    def __init__(self, lines: list[str]):
        self._lines = [line.encode("utf-8") + b"\n" for line in lines]
        self._index = 0

    async def readline(self) -> bytes:
        """Return next line bytes, or b"" when exhausted (signals EOF)."""
        if self._index >= len(self._lines):
            return b""
        line = self._lines[self._index]
        self._index += 1
        return line

    async def read(self, size: int = -1) -> bytes:
        """Return remaining bytes (used for stderr — always b"")."""
        return b""


class FakeStdin:
    """Async stdin sink that records the bytes the backend writes to it.

    The PiBackend delivers the prompt over stdin (not the command line) so a
    /fix-sized prompt never hits Windows' ``cmd /c`` ~8191-char limit. This
    records what is written so tests can assert the prompt went to stdin
    (and that the command line stayed short). ``record`` is a callback handed
    the decoded prompt text so the owning call record can capture it.
    """

    def __init__(self, record=None):
        self._record = record
        self._buf = bytearray()
        self.closed = False

    def write(self, data: bytes) -> None:
        self._buf.extend(data)

    async def drain(self) -> None:
        """When all buffered data is "flushed", hand the prompt to record."""
        if self._record is not None and self._buf:
            self._record(self._buf.decode("utf-8"))

    def close(self) -> None:
        self.closed = True


class FakeProcess:
    """Subprocess stand-in for asyncio.create_subprocess_exec.

    The PiBackend reads ``process.stdout.readline()`` in a loop and
    ``process.stderr.read()`` concurrently, and writes the prompt to
    ``process.stdin`` (merged by pi into the initial message). This fake
    feeds prebuilt ``--mode json`` lines on stdout, empty stderr, and a
    stdin sink that records the written prompt via *record*.
    """

    def __init__(self, stdout_lines: list[str], returncode: int = 0,
                 record_prompt=None):
        self.stdout = FakeStreamReader(stdout_lines)
        self.stderr = FakeStreamReader([])  # stderr always empty
        self.stdin = FakeStdin(record=record_prompt)
        self.returncode = returncode
        self.killed = False

    def kill(self) -> None:
        """Record a kill — the process is already 'done'."""
        self.killed = True

    async def wait(self) -> int:
        """Return the canned returncode."""
        return self.returncode


# ---------------------------------------------------------------------------
# Command parser


# pi flags that take a following value.
_VALUE_FLAGS = (
    "--model",
    "--provider",
    "--thinking",
    "--tools",
    "--exclude-tools",
    "--api-key",
    "--session-id",
    "--session",
    "--fork",
    "--system-prompt",
    "--append-system-prompt",
    "--session-dir",
    "--mode",
)


def _parse_command(cmd: list[str]) -> dict:
    """Extract pi ``--mode json`` flags from a spawned argv.

    Records the session flags (``--session-id`` fresh / ``--session`` resume /
    ``--fork`` + ``--session-id`` fork), the tool allowlist/denylist, the
    project-trust ``--approve`` flag, the model/provider, the ``--api-key``
    value, and the flags' presence.  The prompt is NOT on the command line —
    the backend delivers it over stdin (pi merges piped stdin into the initial
    message), so it is recorded separately on the call dict under ``prompt``
    (populated by the FakeStdin sink) rather than parsed from argv.  This also
    means the command line stays short regardless of prompt length, which is
    exactly the property under test (Windows ``cmd /c`` caps the command line
    at ~8191 chars).  Convenience booleans ``is_fresh`` / ``is_resume`` /
    ``is_fork`` mirror the three session cases; ``prefix`` records a Windows
    ``["cmd", "/c"]`` shim prefix when one was prepended for a ``.cmd``/``.bat``
    executable.
    """
    result: dict[str, Any] = {"cmd": list(cmd)}

    # A Windows .cmd/.bat shim is invoked through `cmd /c <pi> ...`.
    prefix: list[str] = []
    start = 0
    if len(cmd) >= 3 and cmd[0] == "cmd" and cmd[1] == "/c":
        prefix = ["cmd", "/c"]
        start = 2
    result["prefix"] = prefix
    result["executable"] = cmd[start]

    flag_map = {
        "--model": "model",
        "--provider": "provider",
        "--thinking": "thinking",
        "--tools": "tools",
        "--exclude-tools": "exclude_tools",
        "--api-key": "api_key",
        "--session-id": "session_id",
        "--session": "resume",
        "--fork": "fork",
        "--system-prompt": "system_prompt",
        "--append-system-prompt": "append_system_prompt",
        "--session-dir": "session_dir",
        "--mode": "mode",
    }

    i = start
    while i < len(cmd):
        part = cmd[i]
        if part in flag_map:
            if i + 1 < len(cmd):
                result[flag_map[part]] = cmd[i + 1]
                i += 2
                continue
        elif part == "--approve":
            result["approve"] = True
            i += 1
            continue
        i += 1

    result.setdefault("approve", False)

    # The prompt is delivered over stdin, not the command line, so it is NOT
    # parsed from argv here. ``prompt`` / ``prompt_prefix`` are seeded empty and
    # filled in by the FakeStdin sink when the backend writes the prompt (see
    # FakeProcess / _make_process). This is the whole point of the stdin
    # transport: no matter how long the prompt is, it never appears in `cmd`,
    # so the command line stays under Windows' ~8191-char `cmd /c` limit.
    result["prompt"] = ""
    result["prompt_prefix"] = ""

    result["is_fork"] = "fork" in result
    result["is_resume"] = "resume" in result
    # Fresh: a pinned --session-id with no --fork/--session.
    result["is_fresh"] = ("session_id" in result
                          and "fork" not in result
                          and "resume" not in result)
    return result


# ---------------------------------------------------------------------------
# PiFake


class PiFake:
    """Scripted pi backend fake (subprocess level).

    Unlike ClaudeFake (which patches runner.run), PiFake patches
    ``asyncio.create_subprocess_exec`` so the real factory → PiBackend →
    ``--mode json`` parser → RunResult path runs unmodified.

    Can be used as a context manager (``with PiFake():``) to auto-patch/unpatch,
    or manually via ``patch()``/``unpatch()``.

    Attributes (mutable, for assertions):
        calls     - list[dict]  every pi command with parsed flags
    """

    def __init__(self):
        # (text, session_id, subtype, cost_total, error_msg)
        self._scripts: list[tuple[str, str, str, float | None, str]] = []
        # Per-script optional tool_execution_start event (Phase 2 MCP shapes).
        # Aligned with _scripts by index; None means no tool event.
        self._tool_events: list[dict | None] = []
        self._call_index = 0
        self.calls: list[dict[str, Any]] = []
        self._killed: list[bool] = []  # per-script: True → returncode -9
        self._patch_tuple = None  # (module, original) stored by patch()

    def __enter__(self):
        """Auto-patch on context manager entry."""
        self._patch_tuple = self.patch()
        return self

    def __exit__(self, *exc):
        """Auto-unpatch on context manager exit."""
        if self._patch_tuple:
            self.unpatch(*self._patch_tuple)
        return False

    # -- Builders (mirror ClaudeFake / CodexFake signatures) --

    def script_response(self, text: str, session_id: str = "s1",
                        subtype: str = "success",
                        cost_total: float | None = None,
                        error_msg: str = "error",
                        tool_event: dict | None = None) -> None:
        """Add a response to the script.  Order matters — each pi run consumes the next.

        *tool_event* is an optional ``tool_execution_start`` dict emitted
        alongside the response (the Phase 2 autoswe_comment shape) so the real
        parser sets plan_posted / question_posted from it.
        """
        self._scripts.append((text, session_id, subtype, cost_total, error_msg))
        self._killed.append(False)
        self._tool_events.append(tool_event)

    def script_mcp_plan(self, plan_body: str, session_id: str = "s1",
                        proxy: str = "direct", text: str = "") -> None:
        """Add a plan response that calls the autoswe_comment post_plan tool.

        The plan body is carried on the ``tool_execution_start`` event (the
        comment is posted via MCP, so the assistant text may be empty). *proxy*
        selects the tool-calling shape: ``"direct"`` (the
        ``mcp__autoswe_comment_post_plan`` name), ``"generic"`` (the ``mcp``
        proxy with ``{tool, args}``), or ``"namespace"`` (the
        ``mcp__autoswe_comment`` namespace proxy).
        """
        self.script_response(
            text, session_id=session_id,
            tool_event=_mcp_comment_tool_event("post_plan", plan_body, proxy),
        )

    def script_mcp_question(self, question_body: str, session_id: str = "s1",
                            proxy: str = "direct", text: str = "") -> None:
        """Add a plan response that calls the autoswe_comment post_question tool."""
        self.script_response(
            text, session_id=session_id,
            tool_event=_mcp_comment_tool_event("post_question", question_body, proxy),
        )

    def script_mcp_update_progress(self, body: str, session_id: str = "s1",
                                   text: str = "") -> None:
        """Add a response that calls the autoswe_comment update_progress tool."""
        self.script_response(
            text, session_id=session_id,
            tool_event=_mcp_comment_tool_event("update_progress", body, "direct"),
        )

    def script_plan(self, plan_text: str, session_id: str = "s1") -> None:
        """Add a plan-phase response.

        Wraps the plan in ``<AUTOSWE_PLAN>`` tags in the assistant message —
        the planner's tag parsing must keep working.  pi has no native
        ``plan`` item, so plan capture is text-pattern driven (unlike Codex's
        authoritative plan item).
        """
        self.script_response(
            f"<AUTOSWE_PLAN>{plan_text}</AUTOSWE_PLAN>",
            session_id=session_id,
        )

    def script_questions(self, questions: str, session_id: str = "s1") -> None:
        """Add a plan-phase response with questions."""
        self.script_response(
            f"<AUTOSWE_QUESTIONS>{questions}</AUTOSWE_QUESTIONS>",
            session_id=session_id,
        )

    def script_fix(self, summary: str = "Changes applied.",
                   session_id: str = "s1") -> None:
        """Add a fix-phase response."""
        self.script_response(summary, session_id=session_id, subtype="success")

    def script_fail(self, exc: Exception | None = None,
                    session_id: str = "s1",
                    error_msg: str = "error") -> None:
        """Schedule an in-stream error (extension_error → subtype "error")."""
        self.script_response(
            error_msg, session_id=session_id, subtype="error",
            error_msg=error_msg,
        )

    def script_killed(self, session_id: str = "s1", partial_text: str = "") -> None:
        """Schedule a killed response (returncode -9 → subtype "killed")."""
        self._scripts.append((partial_text, session_id, "killed", None, "error"))
        self._killed.append(True)

    # -- JSONL generator --

    def _next_jsonl(self) -> tuple[list[str], int]:
        """Build ``--mode json`` lines and returncode for the next scripted response."""
        if self._call_index >= len(self._scripts):
            return _build_success_jsonl("s-default", ""), 0

        text, session_id, subtype, cost_total, error_msg = self._scripts[self._call_index]
        is_killed = (self._call_index < len(self._killed)
                     and self._killed[self._call_index])
        tool_event = (self._tool_events[self._call_index]
                      if self._call_index < len(self._tool_events) else None)

        if is_killed:
            lines = _build_killed_jsonl(session_id, text)
            return lines, -9

        lines = _build_text_jsonl(session_id, text, subtype,
                                  cost_total=cost_total, error_msg=error_msg,
                                  tool_event=tool_event)
        return lines, 0

    # -- Patch plumbing --

    @classmethod
    def _get_real_create(cls):
        """Return the original ``asyncio.create_subprocess_exec``.

        The module-level ``_REAL_CREATE`` is captured once at import time —
        before any test can patch — so this always returns the genuine
        function regardless of how many times the attribute has been
        monkeypatched.
        """
        return _REAL_CREATE

    def patch(self):
        """Patch asyncio.create_subprocess_exec.

        Returns (module, original) for unpatching.
        """
        import asyncio

        self._saved_original = self._get_real_create()
        self._target_mod = asyncio

        def _make_process(cmd):
            """Build a FakeProcess for the next scripted response.

            Returns a FakeProcess directly (synchronous — the outer async stub
            handles the await).
            """
            # Record the parsed command
            call = _parse_command(list(cmd))
            self.calls.append(call)

            # Build the JSONL response
            lines, returncode = self._next_jsonl()
            self._call_index += 1
            # The prompt arrives on stdin, not argv: when the backend writes it
            # to the fake stdin, record it on the call dict so tests can assert
            # it (and confirm the command line stayed short).
            def _record_prompt(text: str) -> None:
                call["prompt"] = text
                call["prompt_prefix"] = text[:80]

            return FakeProcess(lines, returncode=returncode,
                               record_prompt=_record_prompt)

        async def fake_create_subprocess_exec(*cmd, **kwargs):
            return _make_process(cmd)

        asyncio.create_subprocess_exec = fake_create_subprocess_exec

        self._patch_tuple = (asyncio, self._saved_original)
        return asyncio, self._saved_original

    def unpatch(self, module=None, original=None) -> None:
        """Restore asyncio.create_subprocess_exec."""
        if module is None and self._patch_tuple:
            module, original = self._patch_tuple
        if module is not None:
            module.create_subprocess_exec = self._get_real_create()
