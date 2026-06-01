"""Codex backend — implements CodingBackend via ``codex exec --json``.

Shells out to the Codex CLI subprocess (no alpha SDK), maps a
harness-agnostic ``RunSpec`` to CLI flags, and parses the JSONL event
stream into a ``RunResult``.

**Capabilities (Phase 4, core run only):** ``mode``, ``resume``, ``progress_stream``.

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
from dataclasses import dataclass, field
from typing import Awaitable

from autoswe.core.logging_utils import log
from autoswe.harness.backends.base import RunResult, RunSpec
from autoswe.harness.backends.codex_pricing import estimate_cost

# ---------- Streaming accumulator ----------


@dataclass
class _CodexAccumulator:
    """Accumulates state during Codex JSONL streaming.

    Passed directly to ``_parse_jsonl_line`` so the parser mutates the
    accumulator in-place (avoids list-wrapper indirection).
    """

    text_chunks: list[str] = field(default_factory=list)
    session_id: str | None = None
    turn_failed: bool = False
    usage: list[dict] = field(default_factory=list)


# ---------- Mode → Codex sandbox mapping ----------

# RunSpec.mode → Codex --sandbox value
_MODE_SANDBOX = {
    "plan": "read-only",
    "read_only": "read-only",
    "read_write": "workspace-write",
}

# Matches RunSpec.max_turns default — only emit -c flag when the caller
# requests a value different from the default, keeping the command minimal.
_DEFAULT_MAX_TURNS = 200


def _mode_to_sandbox(mode: str | None) -> str:
    """Translate a RunSpec mode string to a Codex sandbox flag value."""
    if mode is None:
        # Default: read-only (safe default for unspecified intent)
        return "read-only"
    return _MODE_SANDBOX.get(mode, "read-only")


# ---------- JSONL line parser ----------


def _parse_jsonl_line(
    line: str,
    acc: _CodexAccumulator,
    callback,
) -> None:
    """Parse a single JSONL event line and update the accumulator in-place.

    *acc* is a ``_CodexAccumulator`` instance mutated by this function.
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
        if tid and not acc.session_id:
            acc.session_id = tid

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
                acc.text_chunks.append(text)
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

    elif etype == "item.delta":
        # Incremental content — append to last chunk if available
        delta = event.get("delta", "")
        if delta:
            if acc.text_chunks:
                acc.text_chunks[-1] += delta
            else:
                acc.text_chunks.append(delta)

    elif etype == "turn.failed":
        # error field is a dict with "message" key (live-verified)
        error_obj = event.get("error", {})
        error_msg = error_obj.get("message", str(error_obj)) if isinstance(error_obj, dict) else str(error_obj)
        log(f"[CODEX] turn.failed: {error_msg}")
        acc.turn_failed = True

    elif etype == "turn.completed":
        usage = event.get("usage", {})
        if usage:
            acc.usage.append(usage)
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

    ``cost_usd`` is an **estimate** derived from a maintained price table
    (``codex_pricing.py``). Returns ``None`` for unknown models — never
    guesses. Duration is tracked via ``time.monotonic()``.
    """

    CAPABILITIES: set[str] = {"mode", "resume", "progress_stream"}

    @classmethod
    def capabilities(cls) -> set[str]:
        return cls.CAPABILITIES.copy()

    def run(self, spec: RunSpec) -> Awaitable[RunResult]:
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
        resume = bool(spec.resume)

        # Resolve auth early (needed for command-building below).
        # --ignore-user-config is only safe when we supply an explicit API key.
        # Without a key we let codex use ~/.codex/config.toml (ollama provider, etc.).
        harness_cfg = (spec.state or {}).get("_harness_cfg") or {}
        has_api_key = bool(harness_cfg.get("openai_api_key") or harness_cfg.get("codex_api_key")
                           or os.environ.get("OPENAI_API_KEY") or os.environ.get("CODEX_API_KEY"))
        needs_ignore_user_config = has_api_key

        # Build the command
        cmd: list[str] = ["codex", "exec"]

        # --- Resume mode has a different flag set than exec ---
        # Verified against `codex exec resume --help`:
        #   Supported: --json, -m/--model, -c, --dangerously-bypass-approvals-and-sandbox,
        #              --ephemeral, --ignore-user-config, --ignore-rules, --last, --skip-git-repo-check
        #   NOT supported: --sandbox, -C/--cd
        if resume:
            cmd.extend(["resume", spec.resume])
            # Flags valid for both exec and resume
            cmd.extend(["--json"])
            if needs_ignore_user_config:
                cmd.append("--ignore-user-config")
            cmd.extend([
                "--ignore-rules",
                "--dangerously-bypass-approvals-and-sandbox",
                "--model", model,
            ])
        else:
            # Fresh exec — full flag set
            cmd.extend(["--json"])
            if needs_ignore_user_config:
                cmd.append("--ignore-user-config")
            cmd.extend([
                "--ignore-rules",
                "--sandbox", sandbox,
                "--dangerously-bypass-approvals-and-sandbox",
                "--model", model,
                "-C", spec.cwd,
            ])
            # Persist session files so resume (codex exec resume <id>) can restore context.

        # Limit turns to prevent runaway sessions (only add flag when non-default)
        if spec.max_turns and spec.max_turns != _DEFAULT_MAX_TURNS:
            cmd.extend(["-c", f"agent.max_turns={spec.max_turns}"])

        # Append the prompt behind `--` so prompts starting with `-` are safe
        cmd.extend(["--", spec.prompt])

        # Build environment
        env = dict(os.environ)
        if harness_cfg.get("openai_api_key"):
            env["OPENAI_API_KEY"] = harness_cfg["openai_api_key"]
        if harness_cfg.get("codex_api_key"):
            env["CODEX_API_KEY"] = harness_cfg["codex_api_key"]
        # Apply explicit env overrides (take precedence)
        if spec.env_overrides:
            env.update(spec.env_overrides)

        log(f"[CODEX] running model={model} sandbox={sandbox} "
            f"resume={'NEW' if not resume else spec.resume[:8]} "
            f"auth={'local' if not has_api_key else 'api_key'}")

        t0 = time.monotonic()

        # Start subprocess with streaming stdout/stderr
        # Resume runs: -C is not supported by `codex exec resume`, so pass cwd=
        # to ensure the subprocess operates in the correct worktree.
        # Fresh runs: -C is already in the command, cwd= is harmless (codex uses -C).
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.DEVNULL,  # Codex waits for stdin EOF before running
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=spec.cwd,
            )
        except FileNotFoundError as e:
            raise RuntimeError(
                "codex executable not found on PATH. "
                "Install with: npm i -g @openai/codex"
            ) from e

        # Accumulator for in-place mutation by _parse_jsonl_line
        acc = _CodexAccumulator()

        async def read_stderr() -> bytes:
            """Collect all stderr output (non-JSON progress/debug)."""
            if process.stderr:
                return await process.stderr.read()
            return b""

        async def read_stdout_jsonl() -> None:
            """Read stdout line-by-line, parse JSONL events, fire callbacks."""
            if process.stdout:
                while True:
                    raw = await process.stdout.readline()
                    if not raw:
                        break
                    text = raw.decode("utf-8", errors="replace")
                    _parse_jsonl_line(
                        text,
                        acc=acc,
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
        # asyncio.subprocess uses negative values for signal-killed processes
        # (e.g. -9 = SIGKILL, -15 = SIGTERM).  Positive values are normal
        # exit codes returned by the process itself.
        if returncode == 0 and not acc.turn_failed:
            subtype = "success"
        elif returncode == 0 and acc.turn_failed:
            subtype = "error"
        elif returncode is not None and returncode < 0:
            # Killed by signal (SIGKILL, SIGTERM, timeout)
            subtype = "killed"
        else:
            subtype = "error"

        # Estimate cost from accumulated token usage
        estimated_cost = estimate_cost(model, acc.usage)

        return RunResult(
            text="\n".join(acc.text_chunks),
            session_id=acc.session_id,
            subtype=subtype,
            cost_usd=estimated_cost,
            duration_seconds=duration,
            plan_file_path=None,
            plan_posted=False,
            question_posted=False,
        )
