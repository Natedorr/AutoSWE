"""Codex backend — implements CodingBackend via ``codex exec --json``.

Shells out to the Codex CLI subprocess (no alpha SDK), maps a
harness-agnostic ``RunSpec`` to CLI flags, and parses the JSONL event
stream into a ``RunResult``.

**Capabilities (Phase 4, core run only):** ``mode``, ``resume``, ``progress_stream``.

Progress streaming uses ``asyncio.create_subprocess_exec`` with async
line-reading so that ``progress_callback`` fires with live plan/command
updates while the Codex CLI is running (not just after it finishes).

**Wire format — both casings accepted.** The refreshed Codex CLI emits
item types in snake_case (``agent_message``, ``command_execution``) while the
app-server item reference names the same types in camelCase
(``agentMessage``, ``commandExecution``) and uses slash-style event names
(``item/plan/delta``, ``turn/plan/updated``). The parser normalizes event and
item names defensively so that either spelling (and both dot/slash event
forms) is handled, regardless of CLI version. ``agent_message``/``agentMessage``
remains the primary source for ``RunResult.text``; the authoritative ``plan``
item populates ``RunResult.plan_text``. The legacy ``todo_list``,
``summary_output`` items and the ``item.delta`` / ``item.updated`` events no
longer exist in the current CLI and are no longer emitted.

Future phases may add ``mcp`` (MCP comment posting) and structured
AskUserQuestion handling.  Until then those features degrade gracefully
— handlers fall back to text parsing when ``"mcp"`` is not advertised.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from collections.abc import Awaitable
from dataclasses import dataclass, field

from autoswe.core.logging_utils import log
from autoswe.harness.backends.base import RunResult, RunSpec
from autoswe.harness.backends.codex_pricing import estimate_cost

# Max bytes allowed on stdout/stderr pipes before we truncate and
# flag the turn as failed.  Prevents pipe-buffer deadlock (~64KB on
# Linux) and unbounded memory growth when the child process produces
# pathological output.
_MAX_STREAM_BYTES = 16 * 1024 * 1024  # 16 MB


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
    # Authoritative plan item text (last item.completed plan item wins).
    # Populated onto RunResult.plan_text; never mixed into text_chunks so it
    # does not pollute RunResult.text (the planner's tag/prose parsing runs on
    # result.text).
    plan_text: str | None = None
    # Per-item-id streaming agent-message text (item/agentMessage/delta).
    # Used only as a fallback when the item.completed carries empty text.
    _agent_delta_by_id: dict[str, str] = field(default_factory=dict)
    # Per-item-id cumulative character position streamed so far (delta progress
    # throttling; see _fire_delta_progress).
    _delta_streamed: dict[str, int] = field(default_factory=dict)
    # Per-item-id cumulative position at which delta progress last fired.
    _delta_fired_at: dict[str, int] = field(default_factory=dict)


# ---------- Name normalization (both-casing tolerance) ----------

# The CLI emits snake_case item/event types while the app-server reference
# uses camelCase item names and slash-style event names. Normalizing to a
# single canonical form lets one comparison table cover every spelling.


def _norm_event_type(etype: str) -> str:
    """Normalize an event type: lowercase, slashes → dots, drop underscores.

    Stripping underscores makes ``item.agent_message.delta`` ≡
    ``item.agentMessage.delta`` ≡ ``item.agentmessage.delta``.  So
    ``item/plan/delta`` → ``item.plan.delta`` and
    ``event.turn.plan.updated`` → ``turn.plan.updated``.
    """
    s = etype.strip().lower().replace("/", ".").replace("_", "")
    if s.startswith("event."):
        s = s[len("event."):]
    return s


def _norm_item_type(itype: str) -> str:
    """Normalize an item type: lowercase, drop underscores.

    So ``agent_message`` ≡ ``agentMessage`` ≡ ``agentmessage`` and
    ``command_execution`` ≡ ``commandExecution``.
    """
    return itype.strip().lower().replace("_", "")


# ---------- Bypass approvals / sandbox ----------

# Codex runs on autoSWE target a dedicated, isolated machine (see
# docs/autoswe/safeguards.md), so the default posture is full bypass. The
# bypass is no longer implicit: it is derived from an explicit profile flag
# (``bypass_approvals``, default true) with an environment-variable override,
# so the "full access" intent is intentional rather than buried in the flag
# list.
#
# RunSpec.mode is still accepted (contract parity with claude_code) but no
# longer maps to a ``--sandbox`` value. Emitting a per-mode ``--sandbox`` was
# dead weight: the bypass flag always neutralized it, so plan/review runs got
# full access regardless. With the mapping removed, the emitted flag set now
# matches the documented intent.
_BYPASS_APPROVALS_AND_SANDBOX = "--dangerously-bypass-approvals-and-sandbox"
# Env override for operators who want to disable the bypass on a shared host.
_BYPASS_ENV_VAR = "CODEX_BYPASS_APPROVALS_AND_SANDBOX"


def _bypass_approvals(harness_cfg: dict | None) -> bool:
    """Resolve whether to emit the bypass-approvals-and-sandbox flag.

    Precedence (highest wins):
    1. Profile ``bypass_approvals`` (explicit bool from harnesses.json)
    2. ``CODEX_BYPASS_APPROVALS_AND_SANDBOX`` env var ("1"/"true" → True,
       "0"/"false" → False, case-insensitive; unset → fall through)
    3. Default: ``True`` (dedicated isolated machine — see safeguards.md).
    """
    if harness_cfg and "bypass_approvals" in harness_cfg:
        return bool(harness_cfg["bypass_approvals"])
    env_val = os.environ.get(_BYPASS_ENV_VAR)
    if env_val is not None:
        return env_val.strip().lower() in ("1", "true", "yes", "on")
    return True


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

    etype = _norm_event_type(event.get("type", ""))

    if etype == "thread.started":
        tid = event.get("thread_id")
        if tid and not acc.session_id:
            acc.session_id = tid

    elif etype == "item.started":
        item = event.get("item", {})
        item_type = _norm_item_type(item.get("type", ""))
        # item.started is the "in progress" signal — fire progress.  The
        # deltas (plan / reasoning / agentMessage) handle their own progress,
        # so no progress fires for plan/reasoning starts here.
        if callback:
            if item_type in ("agentmessage", "commandexecution"):
                info = item.get("text") or item.get("command", "")
                if info:
                    callback(f"Working: {info[:120]}")
            elif item_type == "filechange":
                paths = _file_change_paths(item)
                if paths:
                    callback(f"Working: {paths[:120]}")
            elif item_type == "mcptoolcall":
                server = item.get("server", "")
                tool = item.get("tool", "")
                label = f"{server}.{tool}" if server or tool else "tool"
                callback(f"MCP: {label[:120]}")
            elif item_type == "websearch":
                query = item.get("query", "")
                if query:
                    callback(f"Searching: {query[:120]}")

    elif etype == "item.completed":
        item = event.get("item", {})
        item_type = _norm_item_type(item.get("type", ""))
        item_id = item.get("id", "")

        if item_type == "agentmessage":
            # Primary RunResult.text source. Prefer the completed item's
            # authoritative text; fall back to the streamed deltas only when
            # the completed item carries empty text (the docs warn that the
            # final item may not exactly equal the concatenated deltas).
            text = item.get("text", "") or ""
            if not text and item_id:
                text = acc._agent_delta_by_id.pop(item_id, "")
            else:
                acc._agent_delta_by_id.pop(item_id, None)
            if text:
                acc.text_chunks.append(text)
                if callback:
                    callback(f"Agent: {text[:120]}")

        elif item_type == "plan":
            # Authoritative plan item — capture onto RunResult.plan_text
            # (last completion wins per docs).  Never appended to
            # text_chunks so it does not pollute RunResult.text.
            text = item.get("text", "") or ""
            if text:
                acc.plan_text = text
                if callback:
                    callback(f"📝 Plan: {text[:120]}")

        elif item_type == "reasoning":
            summary = (item.get("summary") or "")
            if summary and callback:
                callback(f"💭 {summary[:120]}")

        elif item_type == "commandexecution":
            exit_code = item.get("exitCode", item.get("exit_code"))
            if callback and exit_code is not None:
                command = item.get("command", "")
                label = f"{command[:80]}" if command else "command"
                callback(f"⌨ {label} (exit {exit_code})")

    elif etype == "turn.plan.updated":
        # turn/plan/updated — render the plan step list as progress.
        if callback:
            _fire_plan_progress(
                callback,
                event.get("plan", []),
                explanation=event.get("explanation"),
            )

    elif etype == "item.agentmessage.delta" or etype == "item.delta":
        # Incremental agent-message text.  item/agentMessage/delta carries the
        # item-scoped id/type; a bare item.delta falls back to the same.
        item_id = _delta_item_id(event)
        delta = _delta_payload(event)
        if delta and item_id:
            acc._agent_delta_by_id[item_id] = acc._agent_delta_by_id.get(item_id, "") + delta

    elif etype == "item.plan.delta":
        # Plan text stream — progress only, no RunResult impact.
        _fire_delta_progress(acc, callback, event, "📝 ")

    elif etype in ("item.reasoning.summarytextdelta", "item.reasoning.textdelta"):
        # Reasoning summary stream — progress only.
        _fire_delta_progress(acc, callback, event, "💭 ")

    # item.commandExecution.outputDelta / item.fileChange.outputDelta are
    # intentionally ignored (high-volume, no progress value).

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


def _delta_payload(event: dict) -> str:
    """Extract the text delta from a delta event (either casing)."""
    delta = event.get("delta")
    if isinstance(delta, str):
        return delta
    # Some delta events carry the text under a nested "text" key.
    return event.get("text", "") or ""


def _delta_item_id(event: dict) -> str:
    """Resolve the item id a delta event belongs to.

    Prefers an explicit ``itemId``/``item_id``; falls back to the id inside a
    nested ``item`` object; otherwise returns "" (delta ignored).
    """
    item_id = event.get("itemId") or event.get("item_id") or ""
    if item_id:
        return item_id
    item = event.get("item")
    if isinstance(item, dict):
        return item.get("id", "")
    return ""


def _file_change_paths(item: dict) -> str:
    """Render a file_change item's changed paths as a compact label."""
    changes = item.get("changes", [])
    paths: list[str] = []
    for c in changes:
        if isinstance(c, dict):
            p = c.get("path")
            if p:
                paths.append(p)
    return ", ".join(paths)


# turn.plan.updated step status → progress icon (shared by _fire_plan_progress).
_PLAN_STATUS_ICON = {"completed": "✅", "inprogress": "▶", "pending": "☐"}


def _fire_plan_progress(callback, plan: list[dict], explanation: str | None = None) -> None:
    """Render a turn.plan.updated step list into a progress callback string.

    Status mapping: completed → ✅, inProgress → ▶, pending → ☐.  An optional
    *explanation* prefixes the line.
    """
    if not plan:
        return
    parts = []
    for step in plan:
        if not isinstance(step, dict):
            continue
        icon = _PLAN_STATUS_ICON.get(str(step.get("status", "")).strip().lower(), "☐")
        parts.append(f"{icon} {step.get('step', step.get('text', ''))}")
    if not parts:
        return
    prefix = f"📝 {explanation} — " if explanation else "📋 "
    callback(prefix + " | ".join(parts))


def _fire_delta_progress(acc: _CodexAccumulator, callback, event: dict, prefix: str) -> None:
    """Fire throttled progress for a plan/reasoning delta event.

    Progress lines are fire-and-forget; bounding output matters.  Fires on the
    first delta for an item and again once the accumulated text has grown by
    ~80 chars since the last fire.
    """
    if not callback:
        return
    item_id = _delta_item_id(event)
    if not item_id:
        return
    delta = _delta_payload(event)
    if not delta:
        return
    # Throttle on cumulative growth: re-fire once ~80 chars have streamed
    # since the last progress line for this item.  Track two positions:
    #   _delta_streamed — total chars streamed so far (running total)
    #   _delta_fired_at — the streamed position at which progress last fired
    # Firing when (streamed - fired_at) >= 80 means small deltas (the common
    # case) still surface progress as they accumulate, instead of only when a
    # single delta happens to be >= 80 chars.
    streamed = acc._delta_streamed.get(item_id, 0) + len(delta)
    acc._delta_streamed[item_id] = streamed
    fired_at = acc._delta_fired_at.get(item_id, -1)
    if fired_at < 0 or streamed - fired_at >= 80:
        acc._delta_fired_at[item_id] = streamed
        callback(f"{prefix}{delta[:120]}")


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
    RETRYABLE_SUBTYPES: set[str] = {"error", "killed"}

    @classmethod
    def capabilities(cls) -> set[str]:
        return cls.CAPABILITIES.copy()

    @classmethod
    def retryable_subtypes(cls) -> set[str]:
        return cls.RETRYABLE_SUBTYPES.copy()

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
        # Codex has no built-in default model — a profile/spec must name one.
        # The factory enforces this at resolution time; this guard protects
        # direct CodexBackend().run(spec) calls that bypass the factory.
        model = str(spec.model or "").strip()
        if not model:
            raise ValueError(
                "Codex harness profile is missing required 'model'. "
                "Set it to a current Codex model, e.g. 'gpt-5.6-sol', 'gpt-5.6-terra', "
                "'gpt-5.6-luna', or 'gpt-5.5'."
            )
        resume = bool(spec.resume)

        # Resolve auth early (needed for command-building below).
        # --ignore-user-config is only safe when we supply an explicit API key.
        # Without a key we let codex use ~/.codex/config.toml (ollama provider, etc.).
        harness_cfg = (spec.state or {}).get("_harness_cfg") or {}
        has_api_key = bool(harness_cfg.get("openai_api_key") or harness_cfg.get("codex_api_key")
                           or os.environ.get("OPENAI_API_KEY") or os.environ.get("CODEX_API_KEY"))
        needs_ignore_user_config = has_api_key

        # Explicit bypass decision (default on — dedicated isolated machine).
        bypass = _bypass_approvals(harness_cfg)

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
            cmd.extend(["--ignore-rules"])
            if bypass:
                cmd.append(_BYPASS_APPROVALS_AND_SANDBOX)
            cmd.extend(["--model", model])
        else:
            # Fresh exec — full flag set
            cmd.extend(["--json"])
            if needs_ignore_user_config:
                cmd.append("--ignore-user-config")
            cmd.extend(["--ignore-rules"])
            if bypass:
                cmd.append(_BYPASS_APPROVALS_AND_SANDBOX)
            cmd.extend(["--model", model, "-C", spec.cwd])
            # Persist session files so resume (codex exec resume <id>) can restore context.

        # No turn cap is emitted: `codex exec` has no max_turns key (live-verified
        # on codex-cli 0.150.1 — `-c agent.max_turns=N` errors under
        # --strict-config and is silently ignored otherwise). RunSpec.max_turns
        # is a no-op for this backend; the anti-runaway guard is the wall-clock
        # timeout applied below (spec.timeout).

        # Append the prompt behind `--` so prompts starting with `-` are safe
        cmd.extend(["--", spec.prompt])

        # Build environment
        env = dict(os.environ)
        if harness_cfg.get("openai_api_key"):
            env["OPENAI_API_KEY"] = harness_cfg["openai_api_key"]
        if harness_cfg.get("codex_api_key"):
            env["CODEX_API_KEY"] = harness_cfg["codex_api_key"]
        # Per-harness-profile `env` override (Part B): user values win over the
        # harness api-key fields above (precedence: os.environ < api-key fields
        # < profile "env" < spec.env_overrides).
        env.update(harness_cfg.get("env") or {})
        # Apply explicit env overrides (take precedence)
        if spec.env_overrides:
            env.update(spec.env_overrides)

        log(f"[CODEX] running model={model} bypass={bypass} "
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
            """Collect stderr output in chunks, bounded by _MAX_STREAM_BYTES.

            After the limit is hit, the pipe is drained (discarding data) so the
            child process does not block on a full pipe buffer.
            """
            if not process.stderr:
                return b""
            chunks: list[bytes] = []
            total_bytes = 0
            while True:
                chunk = await process.stderr.read(64 * 1024)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > _MAX_STREAM_BYTES:
                    log(f"[CODEX] stderr exceeded {_MAX_STREAM_BYTES} bytes — truncating")
                    # Drain remaining data without accumulating to prevent deadlock
                    while True:
                        leftover = await process.stderr.read(64 * 1024)
                        if not leftover:
                            break
                    break
                chunks.append(chunk)
            return b"".join(chunks)

        async def read_stdout_jsonl() -> None:
            """Read stdout line-by-line, parse JSONL events, fire callbacks.

            Bounded by _MAX_STREAM_BYTES to prevent pipe-buffer deadlock
            and unbounded memory growth.  After the limit is hit, the pipe
            is drained (discarding data) so the child process does not block
            on a full pipe buffer.
            """
            if process.stdout:
                total_bytes = 0
                while True:
                    raw = await process.stdout.readline()
                    if not raw:
                        break
                    total_bytes += len(raw)
                    if total_bytes > _MAX_STREAM_BYTES:
                        log(f"[CODEX] stdout exceeded {_MAX_STREAM_BYTES} bytes — truncating stream")
                        acc.turn_failed = True
                        # Drain remaining data without parsing to prevent deadlock.
                        # Use read() not readline() — if the child writes
                        # non-newline data, readline() would block forever.
                        while True:
                            leftover = await process.stdout.read(64 * 1024)
                            if not leftover:
                                break
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
            plan_text=acc.plan_text,
        )
