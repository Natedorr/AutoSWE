"""Codex backend — implements CodingBackend via ``codex exec --json``.

Shells out to the Codex CLI subprocess (no alpha SDK), maps a
harness-agnostic ``RunSpec`` to CLI flags, and parses the JSONL event
stream into a ``RunResult``.

**Capabilities (Phase 4, core run only):** ``resume``, ``progress_stream``.

Future phases may add ``mcp`` (MCP comment posting) and structured
AskUserQuestion handling.  Until then those features degrade gracefully
— handlers fall back to text parsing when ``"mcp"`` is not advertised.
"""
from __future__ import annotations

import json
import os
import subprocess
import time

from autoswe.core.config import LOGS_DIR
from autoswe.core.logging_utils import init_debug_logger, log
from autoswe.harness.backends.base import RunResult, RunSpec

_dbg = init_debug_logger(LOGS_DIR)

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


# ---------- JSONL parser ----------


def _parse_jsonl_stream(stdout: str) -> tuple[str, str | None, float | None, float]:
    """Parse a Codex JSONL event stream into (text, session_id, cost_usd, duration_seconds).

    Walks the JSONL lines, collecting:
    - ``thread.started`` → thread_id (becomes session_id)
    - ``item.completed`` with type ``agent_message`` → text chunks
    - ``turn.completed`` → usage tokens (cost estimate placeholder) and duration

    Returns (text, session_id, cost_usd, duration_seconds).
    """
    text_chunks: list[str] = []
    session_id: str | None = None
    cost_usd: float | None = None
    start_time = time.monotonic()

    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue

        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            # Non-JSON line (progress, stderr leak) — skip
            continue

        etype = event.get("type", "")

        if etype == "thread.started":
            tid = event.get("thread_id")
            if tid and session_id is None:
                session_id = tid

        elif etype == "item.completed":
            item = event.get("item", {})
            item_type = item.get("type", "")

            if item_type == "agent_message":
                text = item.get("text", "")
                if text:
                    text_chunks.append(text)

        elif etype == "item.updated":
            # todo_list updates → progress callback handled in caller
            item = event.get("item", {})
            item_type = item.get("type", "")
            if item_type == "todo_list":
                # Emit todo_list progress for progress_callback
                pass  # handled in caller

        elif etype == "turn.completed":
            usage = event.get("usage", {})
            if usage:
                # Token counts available; actual cost depends on model pricing.
                # Store raw token count info for now — cost estimation can
                # be added when model pricing tables are available.
                input_tokens = usage.get("input_tokens", 0)
                output_tokens = usage.get("output_tokens", 0)
                # Rough estimate placeholder — real pricing added later
                # For now, cost_usd stays None (consistent with "no pricing yet")
                _ = input_tokens  # kept for future pricing calculation
                _ = output_tokens

        elif etype == "turn.failed":
            error = event.get("error", "")
            log(f"[CODEX] turn.failed: {error}")

        elif etype == "error":
            error = event.get("message", event.get("error", "unknown error"))
            log(f"[CODEX] error event: {error}")

    duration = time.monotonic() - start_time
    return "\n".join(text_chunks), session_id, cost_usd, duration


# ---------- CodexBackend ----------


class CodexBackend:
    """Codex CLI backend implementing CodingBackend.

    Shells out to ``codex exec --json`` (or ``codex exec resume`` for
    resumption), parses the JSONL event stream, and returns a RunResult.
    """

    CAPABILITIES: set[str] = {"resume", "progress_stream"}

    @classmethod
    def capabilities(cls) -> set[str]:
        return cls.CAPABILITIES.copy()

    def run(self, spec: RunSpec) -> object:
        """Execute the spec via Codex CLI.

        Returns an awaitable that resolves to a RunResult.

        The returned coroutine is synchronous under the hood (Codex CLI is
        a blocking subprocess), but wrapped in async to satisfy the
        CodingBackend Protocol which requires an awaitable (so the runner
        can apply asyncio.wait_for for timeouts).
        """
        return self._run_async(spec)

    async def _run_async(self, spec: RunSpec) -> RunResult:
        """Run Codex CLI subprocess. Returns a RunResult dataclass."""
        import asyncio

        return await asyncio.get_event_loop().run_in_executor(
            None, self._run_sync, spec
        )

    def _run_sync(self, spec: RunSpec) -> RunResult:
        """Synchronous Codex CLI execution."""
        sandbox = _mode_to_sandbox(spec.mode)
        model = spec.model or "gpt-5.4"

        # Build the command
        cmd: list[str] = ["codex", "exec"]

        # Resume mode
        if spec.resume:
            cmd.extend(["resume", spec.resume])

        # Flags
        cmd.extend([
            "--json",
            "--sandbox", sandbox,
            "--ask-for-approval", "never",
            "--model", model,
            "--cd", spec.cwd,
        ])

        # Append the prompt (for non-resume, it's the task; for resume,
        # it's the continuation instruction)
        cmd.append(spec.prompt)

        # Build environment
        env = dict(os.environ)
        # Auth: OPENAI_API_KEY or CODEX_API_KEY from profile or env
        harness_cfg = (spec.state or {}).get("_harness_cfg") or {}
        if harness_cfg.get("openai_api_key"):
            env["OPENAI_API_KEY"] = harness_cfg["openai_api_key"]
        if harness_cfg.get("codex_api_key"):
            env["CODEX_API_KEY"] = harness_cfg["codex_api_key"]
        # Apply explicit env overrides
        if spec.env_overrides:
            env.update(spec.env_overrides)

        # Max turns → config override (Codex uses max_turns config key)
        # Not a CLI flag — passed as --config if needed
        # For now, rely on Codex default turn limits.

        log(f"[CODEX] running model={model} sandbox={sandbox} "
            f"resume={'NEW' if not spec.resume else spec.resume[:8]}")

        t0 = time.monotonic()
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=spec.timeout,
                cwd=spec.cwd,
                env=env,
            )
        except subprocess.TimeoutExpired:
            log(f"[CODEX] timeout after {spec.timeout}s")
            raise
        except FileNotFoundError as e:
            raise RuntimeError(
                "codex executable not found on PATH. "
                "Install with: npm i -g @openai/codex"
            ) from e

        duration = time.monotonic() - t0

        if result.returncode != 0:
            stderr = result.stderr.strip()
            log(f"[CODEX] exit={result.returncode} stderr={stderr[:300]}")

        # Parse JSONL stdout
        text, session_id, cost_usd, _ = _parse_jsonl_stream(result.stdout)

        # Determine subtype from exit code
        if result.returncode == 0:
            subtype = "success"
        elif result.returncode < 0:
            subtype = "killed"
        else:
            subtype = "error"

        # Progress callback: fire a final summary if text was produced
        if spec.progress_callback and text:
            spec.progress_callback(f"Completed: {len(text)} chars")

        return RunResult(
            text=text,
            session_id=session_id,
            subtype=subtype,
            cost_usd=cost_usd,
            duration_seconds=duration,
            plan_file_path=None,
            plan_posted=False,
            question_posted=False,
        )
