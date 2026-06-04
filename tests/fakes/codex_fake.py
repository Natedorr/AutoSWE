"""Scripted Codex backend fake — subprocess level.

Replaces ``asyncio.create_subprocess_exec`` with a stub that returns a
prebuilt ``FakeProcess`` feeding JSONL event lines crafted to exercise the
real ``CodexBackend._parse_jsonl_line`` parser.  Each call records the
parsed command in ``.calls`` for permission/mode assertions.

Builder signatures mirror ``ClaudeFake`` so the existing ``claude_responses``
dicts from transition rows can be fed verbatim.
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

# ---------------------------------------------------------------------------
# JSONL line builders


def _event(obj: dict) -> str:
    """Serialize a JSONL event line."""
    return json.dumps(obj)


def _build_success_jsonl(session_id: str, text: str) -> list[str]:
    """JSONL lines for a successful run yielding *text*."""
    lines: list[str] = []
    lines.append(_event({"type": "thread.started", "thread_id": session_id}))
    lines.append(_event({
        "type": "item.completed",
        "item": {"type": "agent_message", "text": text},
    }))
    lines.append(_event({"type": "turn.completed", "usage": {"input_tokens": 100, "output_tokens": 50}}))
    return lines


def _build_error_jsonl(session_id: str, error_msg: str = "error") -> list[str]:
    """JSONL lines for a run that failed mid-turn (subtype → "error")."""
    lines: list[str] = []
    lines.append(_event({"type": "thread.started", "thread_id": session_id}))
    lines.append(_event({"type": "turn.failed", "error": {"message": error_msg}}))
    return lines


def _build_text_jsonl(session_id: str, text: str, subtype: str) -> list[str]:
    """Route to success or error builder based on *subtype*."""
    if subtype == "success":
        return _build_success_jsonl(session_id, text)
    # error, error_max_turns, permission_denied, killed → turn.failed
    return _build_error_jsonl(session_id, subtype)


# ---------------------------------------------------------------------------
# Fake async subprocess plumbing


class FakeStreamReader:
    """Async streamreader feeding lines from a prebuilt list."""

    def __init__(self, lines: list[str]):
        self._lines = [line.encode("utf-8") + b"\n" for line in lines]
        self._index = 0
        self._exhausted = False

    async def readline(self) -> bytes:
        """Return next line bytes, or b"" when exhausted (signals EOF)."""
        if self._index >= len(self._lines):
            return b""
        line = self._lines[self._index]
        self._index += 1
        return line

    async def read(self) -> bytes:
        """Return remaining bytes (used for stderr — always b"")."""
        return b""


class FakeProcess:
    """Subprocess stand-in for asyncio.create_subprocess_exec.

    The CodexBackend reads ``process.stdout.readline()`` in a loop and
    ``process.stderr.read()`` concurrently. This fake feeds prebuilt
    JSONL lines on stdout and empty stderr.
    """

    def __init__(self, stdout_lines: list[str], returncode: int = 0):
        self.stdout = FakeStreamReader(stdout_lines)
        self.stderr = FakeStreamReader([])  # stderr always empty
        self.returncode = returncode

    def kill(self) -> None:
        """No-op — process is already 'done'."""

    async def wait(self) -> int:
        """Return the canned returncode."""
        return self.returncode


# ---------------------------------------------------------------------------
# Command parser


def _parse_command(cmd: list[str]) -> dict:
    """Extract model, sandbox, resume, prompt_prefix from a codex exec command."""
    result: dict[str, Any] = {}
    i = 0
    while i < len(cmd):
        part = cmd[i]
        if part == "--model" and i + 1 < len(cmd):
            result["model"] = cmd[i + 1]
            i += 2
            continue
        if part == "--sandbox" and i + 1 < len(cmd):
            result["sandbox"] = cmd[i + 1]
            i += 2
            continue
        if part == "resume" and i > 0 and cmd[i - 1] == "exec":
            # Resume mode: next arg is the session id
            if i + 1 < len(cmd):
                result["resume"] = cmd[i + 1]
            i += 2
            continue
        i += 1

    # Prompt is after "--"
    try:
        sep_idx = cmd.index("--")
        result["prompt_prefix"] = (cmd[sep_idx + 1] if sep_idx + 1 < len(cmd) else "")[:80]
    except ValueError:
        result["prompt_prefix"] = ""

    result["is_resume"] = "resume" in result
    return result


# ---------------------------------------------------------------------------
# CodexFake


class CodexFake:
    """Scripted Codex backend fake (subprocess level).

    Unlike ClaudeFake (which patches runner.run), CodexFake patches
    ``asyncio.create_subprocess_exec`` so the real factory → CodexBackend
    → JSONL parser → RunResult path runs unmodified.

    Can be used as a context manager (``with CodexFake():``) to auto-patch/unpatch.
    Or manually via ``patch()``/``unpatch()``.

    Attributes (mutable, for assertions):
        calls     - list[dict]  every codex command with parsed kwargs
    """

    def __init__(self):
        self._scripts: list[tuple[str, str, str]] = []  # (text, session_id, subtype)
        self._call_index = 0
        self.calls: list[dict[str, Any]] = []
        self._raises: list[Exception] = []
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

    # -- Builders (mirror ClaudeFake signatures) --

    def script_response(self, text: str, session_id: str = "s1",
                        subtype: str = "success") -> None:
        """Add a response to the script.  Order matters — each codex run consumes the next."""
        self._scripts.append((text, session_id, subtype))
        self._killed.append(False)

    def script_plan(self, plan_text: str, session_id: str = "s1") -> None:
        """Add a plan-phase response."""
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
        """Schedule an error response (subtype → "error" → coder maps → FAILED)."""
        self.script_response(
            error_msg, session_id=session_id, subtype="error",
        )

    def script_killed(self, session_id: str = "s1") -> None:
        """Schedule a killed response (returncode -9 → subtype "killed")."""
        self._scripts.append(("", session_id, "killed"))
        self._killed.append(True)

    # -- JSONL generator --

    def _next_jsonl(self) -> tuple[list[str], int]:
        """Build JSONL lines and returncode for the next scripted response."""
        if self._call_index >= len(self._scripts):
            return _build_success_jsonl("s-default", ""), 0

        text, session_id, subtype = self._scripts[self._call_index]
        is_killed = self._killed[self._call_index] if self._call_index < len(self._killed) else False

        if is_killed:
            # Killed: thread.started + no completion
            lines = [_event({"type": "thread.started", "thread_id": session_id})]
            return lines, -9

        lines = _build_text_jsonl(session_id, text, subtype)
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
            self.calls.append(_parse_command(list(cmd)))

            # Build the JSONL response
            lines, returncode = self._next_jsonl()
            self._call_index += 1
            return FakeProcess(lines, returncode=returncode)

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
