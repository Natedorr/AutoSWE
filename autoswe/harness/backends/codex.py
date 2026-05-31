"""Codex backend — implements CodingBackend via ``codex exec --json``.

Shells out to the Codex CLI subprocess (no alpha SDK), maps a
harness-agnostic ``RunSpec`` to CLI flags, and parses the JSONL event
stream into a ``RunResult``.

**Capabilities (Phase 4, core run only):** ``resume``, ``progress_stream``.

Progress streaming uses ``asyncio.create_subprocess_exec`` with async
line-reading so that ``progress_callback`` fires with live todo/command
updates while the Codex CLI is running (not just after it finishes).

Future phases may add ``mcp`` (MCP comment posting) and structured
AskUserQuestion handling.  Until then those features degrade gracefully
— handlers fall back to text parsing when ``"mcp"`` is not advertised.
"""
from __future__ import annotations

import asyncio
import json
import os
import time

from autoswe.core.logging_utils import log
from autoswe.harness.backends.base import RunResult, RunSpec

# ---------- Mode → Codex sandbox mapping ----------

# RunSpec.mode → Codex --sandbox value
_MODE_SANDBOX = {
    "plan": "read-only",
    "read_only": "read-only",
    "read_write": "workspace-write",
}


def _mode_to_sandbox(mode: str | None) -> str:
    """Translate a RunSpec mode string to a Codex sandbox flag value."""
    if mode is None:
        # Default: read-only (safe default for unspecified intent)
        return "read-only"
    return _MODE_SANDBOX.get(mode, "read-only")


# ---------- JSONL line parser ----------


def _parse_jsonl_line(
    line: str,
    *,
    text_chunks: list[str],
    session_id: list[str | None],
    turn_failed: list[bool],
    callback,
) -> None:
    """Parse a single JSONL event line and update accumulators in-place.

    *text_chunks* and *session_id* are single-element lists so they can be
    mutated inside this function (convenient for the streaming reader).
    """
    line = line.strip()
    if not line:
        return

    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        # Non-JSON line (stderr leak, progress) — skip
        return

    etype = event.get("type", "")

    if etype == "thread.started":
        tid = event.get("thread_id")
        if tid and not session_id[0]:
            session_id[0] = tid

    elif etype == "item.started":
        item = event.get("item", {})
        item_type = item.get("type", "")
        # item.started is the "in progress" signal — fire progress
        if callback and item_type in ("agent_message", "command_execution", "summary_output"):
            info = item.get("text", item.get("command", ""))
            if info:
                callback(f"Working: {info[:120]}")

    elif etype == "item.completed":
        item = event.get("item", {})
        item_type = item.get("type", "")

        if item_type in ("agent_message", "summary_output"):
            text = item.get("text", "")
            if text:
                text_chunks.append(text)
                # Fire progress with the latest agent message
                if callback:
                    callback(f"Agent: {text[:120]}")
        elif item_type == "todo_list":
            # Render todo items as progress
            items = item.get("items", [])
            if callback and items:
                _fire_todo_progress(callback, items)

    elif etype == "item.updated":
        item = event.get("item", {})
        item_type = item.get("type", "")
        if item_type == "todo_list" and callback:
            items = item.get("items", [])
            if items:
                _fire_todo_progress(callback, items)

    elif etype == "turn.failed":
        error = event.get("error", "")
        log(f"[CODEX] turn.failed: {error}")
        turn_failed[0] = True

    elif etype == "turn.completed":
        usage = event.get("usage", {})
        if usage:
            log(f"[CODEX] turn.completed usage={usage}")

    elif etype == "error":
        error = event.get("message", event.get("error", "unknown error"))
        log(f"[CODEX] error event: {error}")


def _fire_todo_progress(callback, items: list[dict]) -> None:
    """Render a todo_list item array into a progress callback string."""
    parts = []
    for ti in items:
        status = "✅" if ti.get("completed") else "☐"
        parts.append(f"{status} {ti.get('text', '')}")
    callback("📋 " + " | ".join(parts))


# ---------- CodexBackend ----------


class CodexBackend:
    """Codex CLI backend implementing CodingBackend.

    Shells out to ``codex exec --json`` (or ``codex exec resume`` for
    resumption), streams the JSONL event lines for live progress, and
    returns a RunResult.
    """

    CAPABILITIES: set[str] = {"mode", "resume", "progress_stream"}

    @classmethod
    def capabilities(cls) -> set[str]:
        return cls.CAPABILITIES.copy()

    def run(self, spec: RunSpec) -> object:
        """Execute the spec via Codex CLI.

        Returns an awaitable that resolves to a RunResult.

        Uses ``asyncio.create_subprocess_exec`` so that ``progress_callback``
        fires with live updates while the Codex CLI is running.  The runner
        wraps this in ``asyncio.wait_for`` for timeouts.
        """
        return self._run_async(spec)

    async def _run_async(self, spec: RunSpec) -> RunResult:
        """Run Codex CLI subprocess with streaming JSONL. Returns RunResult."""
        sandbox = _mode_to_sandbox(spec.mode)
        model = spec.model or "gpt-5.4"

        # Build the command
        cmd: list[str] = ["codex", "exec"]

        # Resume mode
        if spec.resume:
            cmd.extend(["resume", spec.resume])

        # Flags — always ignore user config and rules for controlled automation
        cmd.extend([
            "--json",
            "--ignore-user-config",
            "--ignore-rules",
            "--sandbox", sandbox,
            "--ask-for-approval", "never",
            "--model", model,
            "--cd", spec.cwd,
        ])

        # Append the prompt (for non-resume, it's the task; for resume,
        # it's the continuation instruction)
        cmd.append(spec.prompt)

        # Ephemeral: don't persist session files (unless resuming, which needs them)
        if not spec.resume:
            cmd.append("--ephemeral")

        # Limit turns to prevent runaway sessions
        if spec.max_turns and spec.max_turns != 200:
            cmd.extend(["-c", f"agent.max_turns={spec.max_turns}"])

        # Build environment
        env = dict(os.environ)
        # Auth: OPENAI_API_KEY or CODEX_API_KEY from profile or env
        harness_cfg = (spec.state or {}).get("_harness_cfg") or {}
        if harness_cfg.get("openai_api_key"):
            env["OPENAI_API_KEY"] = harness_cfg["openai_api_key"]
        if harness_cfg.get("codex_api_key"):
            env["CODEX_API_KEY"] = harness_cfg["codex_api_key"]
        # Apply explicit env overrides (take precedence)
        if spec.env_overrides:
            env.update(spec.env_overrides)

        log(f"[CODEX] running model={model} sandbox={sandbox} "
            f"resume={'NEW' if not spec.resume else spec.resume[:8]}")

        t0 = time.monotonic()

        # Start subprocess with streaming stdout/stderr
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
        except FileNotFoundError as e:
            raise RuntimeError(
                "codex executable not found on PATH. "
                "Install with: npm i -g @openai/codex"
            ) from e

        # Accumulators (list-wrappers for in-place mutation in _parse_jsonl_line)
        text_chunks: list[str] = []
        session_id: list[str | None] = [None]
        turn_failed: list[bool] = [False]

        async def read_stderr() -> bytes:
            """Collect all stderr output (non-JSON progress/debug)."""
            if process.stderr:
                return await process.stderr.read()
            return b""

        async def read_stdout_jsonl() -> None:
            """Read stdout line-by-line, parse JSONL events, fire callbacks."""
            if process.stdout:
                while True:
                    line = await process.stdout.readline()
                    if not line:
                        break
                    text = line.decode("utf-8", errors="replace")
                    _parse_jsonl_line(
                        text,
                        text_chunks=text_chunks,
                        session_id=session_id,
                        turn_failed=turn_failed,
                        callback=spec.progress_callback,
                    )

        try:
            # Run stdout and stderr readers concurrently, with overall timeout.
            # read_stdout_jsonl drains stdout (JSONL); read_stderr collects stderr.
            # Once both finish, the process has exited.
            await asyncio.wait_for(
                asyncio.gather(
                    read_stdout_jsonl(),
                    read_stderr(),
                    return_exceptions=False,
                ),
                timeout=spec.timeout,
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            log(f"[CODEX] timeout after {spec.timeout}s — killed process")
            raise

        returncode = process.returncode
        duration = time.monotonic() - t0

        if returncode != 0:
            log(f"[CODEX] exit={returncode}")

        # Determine subtype from exit code and turn failures
        if returncode == 0 and not turn_failed[0]:
            subtype = "success"
        elif returncode == 0 and turn_failed[0]:
            subtype = "error"
        elif returncode < 0:
            subtype = "killed"
        else:
            subtype = "error"

        return RunResult(
            text="\n".join(text_chunks),
            session_id=session_id[0],
            subtype=subtype,
            cost_usd=None,  # Phase 4: no pricing tables yet
            duration_seconds=duration,
            plan_file_path=None,
            plan_posted=False,
            question_posted=False,
        )
