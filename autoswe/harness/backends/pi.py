"""Pi backend — implements CodingBackend via ``pi --mode json``.

Shells out to the pi CLI subprocess, maps a harness-agnostic ``RunSpec`` to
CLI flags, and parses the JSON event stream (one JSON object per line on
stdout) into a ``RunResult``.  This is the Python-side integration for pi:
the official SDK is TypeScript-only, so the CLI is the transport (the same
shape as the Codex backend).  ``pi --mode json "<prompt>"`` emits the stream
and exits on completion (``docs/pi/json.md``).

**Capabilities (Phase 1):** ``mode``, ``resume``, ``session_fork``,
``progress_stream``.

Unlike Codex, pi performs **real read-only enforcement**: a tool *allowlist*
(``--tools``) over the built-in tools is derived from ``RunSpec.mode``, so a
plan/read_only phase is restricted at the CLI level.  Because the ``"mode"``
capability is advertised, ``has_read_only_enforcement`` is True — plan/review
keep their guarantees instead of loudly degrading and relying on the
worktree-rollback backstop.

``cost_usd`` is **reported, not estimated**: the stream carries
``usage.cost.total`` (USD, provider-reported), so there is no price table
analogous to ``codex_pricing.py``.

**Session identity.** pi can be pinned to an exact session id
(``--session-id``), resumed (``--session``), or forked into a new session
(``--fork <id> --session-id <new>``).  We pre-seed the accumulator with the
id we pass so that even if the process dies before emitting the ``session``
header, ``RunResult.session_id`` is still the id we requested — strictly
better than Codex's parse-only path, which returns ``None`` in that case.

Progress streaming uses ``asyncio.create_subprocess_exec`` with bounded,
concurrent stdout/stderr readers so ``progress_callback`` fires with live
updates while the pi CLI is running (not just after it finishes), and the
overall wall-clock guard is ``spec.timeout`` (pi has no turn cap, so
``RunSpec.max_turns`` is a no-op — documented like Codex).
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import time
import uuid
from collections.abc import Awaitable
from dataclasses import dataclass, field

from autoswe.core.logging_utils import log
from autoswe.harness.backends.base import RunResult, RunSpec
from autoswe.harness.mcp_config import autoswe_repo_root, pi_mcp_comment_server, pi_mcp_json_path

# Max bytes allowed on stdout/stderr pipes before we truncate and flag the
# turn as failed.  Prevents pipe-buffer deadlock (~64KB on Linux) and
# unbounded memory growth when the child produces pathological output.
# Mirrors codex.py's bound.
_MAX_STREAM_BYTES = 16 * 1024 * 1024  # 16 MB

# The built-in tool allowlist per mode.  ``read_only``/``plan`` get the
# documented read-only recipe (``docs/pi/usage.md``); ``read_write`` gets the
# full working set.  ``powershell`` (Windows-only built-in) is added for
# read_write so a Windows host keeps its shell.
_MODE_TOOLS: dict[str, tuple[str, ...]] = {
    "plan": ("read", "grep", "find", "ls"),
    "read_only": ("read", "grep", "find", "ls"),
    "read_write": ("read", "bash", "edit", "write", "grep", "find", "ls"),
}
# Default tool allowlist when RunSpec.mode is unset (fresh interactive-ish
# run): the read_write set, since a /fix run is a full-work phase.
_DEFAULT_TOOLS = _MODE_TOOLS["read_write"]

# ask_question is ALWAYS excluded: there is no per-tool approval callback in
# --mode json (no "can_use_tool" capability), so a non-interactive run can
# block on it indefinitely.  It is appended to the --exclude-tools list
# unconditionally, independent of spec.disallowed_tools_override.
_ALWAYS_EXCLUDED_TOOLS = ("ask_question",)


# ---------- Streaming accumulator ----------


@dataclass
class _PiAccumulator:
    """Accumulates state during pi --mode json streaming.

    Passed directly to ``_parse_line`` so the parser mutates the accumulator
    in-place (avoids list-wrapper indirection).  Mirrors _CodexAccumulator.
    """

    # Authoritative text: the last assistant message_end's text content wins.
    # Set in _parse_line; used directly for RunResult.text when present.
    text: str | None = None
    # Session id. Pre-seeded with the id we passed to --session-id/--session
    # so it survives a premature process death (before the session header).
    session_id: str | None = None
    # Live cost: the latest cumulative usage.cost.total seen on any event that
    # carries a usage block.  message_update carries it on every delta (may be
    # zero until completion); agent_end / message_end carry the final value.
    cost_usd: float | None = None
    # Error flag: set by extension_error events and isError tool results.
    has_error: bool = False
    # Completion marker: set when agent_end is seen.  Used only for logging —
    # the subtype is derived from the exit code, not this flag.
    agent_end: bool = False
    # Per-contentIndex accumulated delta text.  Fallback source for
    # RunResult.text when no message_end carried assistant text (e.g. the
    # process was killed mid-stream).  Keyed by the delta's contentIndex so a
    # multi-block message (text + thinking interleaved) is reassembled in order.
    _delta_by_index: dict[int, list[str]] = field(default_factory=dict)
    # Per-contentIndex cumulative character position for delta-progress
    # throttling (see _fire_delta_progress).
    _delta_streamed: dict[int, int] = field(default_factory=dict)
    _delta_fired_at: dict[int, int] = field(default_factory=dict)


def _extract_cost(event: dict) -> float | None:
    """Pull usage.cost.total out of any event carrying a ``usage`` block.

    ``message_update`` events carry the latest cumulative usage on every
    delta (docs/pi/json.md: "The top-level usage field contains the latest
    cumulative provider-reported usage"); ``message_end`` / ``agent_end``
    messages carry the final value on the assistant message.  Returns None
    when the shape is absent or not a number (providers report cost as a
    float; a missing cost object is tolerated).
    """
    usage = event.get("usage")
    if isinstance(usage, dict):
        cost = usage.get("cost")
        if isinstance(cost, dict):
            total = cost.get("total")
            if isinstance(total, (int, float)):
                return float(total)
    # agent_end / message_end carry usage nested on the message object.
    message = event.get("message")
    if isinstance(message, dict):
        usage = message.get("usage")
        if isinstance(usage, dict):
            cost = usage.get("cost")
            if isinstance(cost, dict):
                total = cost.get("total")
                if isinstance(total, (int, float)):
                    return float(total)
    return None


# ---------- Command construction ----------


def _write_pi_mcp_json(agent_dir: str) -> None:
    """Write the autoswe_comment server into the pi agent-dir ``mcp.json``.

    Only called when a run names the ``autoswe_comment`` MCP server. The
    file is written only when the agent_dir profile field is set (pi's config
    lives in the default ``~/.pi/agent`` otherwise; autoSWE does not relocate
    or clobber a host's default agent dir).

    Merge semantics: autoSWE manages only its own ``autoswe_comment`` entry and
    its own top-level ``settings`` — any other servers or settings an operator
    put in a shared agent dir are preserved. The ``pi-local`` profile points the
    agent dir at ``~/.pi/agent``, which may already carry unrelated MCP
    servers, so a wholesale overwrite would silently drop them. The file only
    ever carries stable values (python path, repo root) — it does not change
    between issues, so rewriting it is idempotent.

    Best-effort: a write failure (e.g. the agent dir is read-only) is logged,
    not raised — Phase 1's acceptance is config generation, and pi still runs
    fine without the MCP server (its tools just are not yet in the allowlist,
    which is Phase 2).
    """
    if not str(agent_dir).strip():
        return
    import sys

    agent_dir = str(agent_dir).strip()
    path = pi_mcp_json_path(agent_dir)
    try:
        os.makedirs(agent_dir, mode=0o700, exist_ok=True)
    except OSError as e:
        log(f"[PI] cannot create agent dir {agent_dir} for mcp.json: {e}")
        return

    try:
        existing = {}
        if path.exists():
            with open(path, encoding="utf-8") as f:
                existing = json.load(f)
        if not isinstance(existing, dict):
            existing = {}
    except (OSError, json.JSONDecodeError) as e:
        # A corrupt/unreadable existing file would otherwise crash every pi run;
        # start fresh rather than die. The autoswe_comment entry is authoritative.
        log(f"[PI] could not read existing {path} ({e}); rewriting")
        existing = {}

    servers = existing.get("mcpServers")
    if not isinstance(servers, dict):
        servers = {}
    # cwd is the autoSWE checkout root (where the mcp_servers package lives),
    # not pi's subprocess cwd (the target worktree).
    servers["autoswe_comment"] = pi_mcp_comment_server(sys.executable, autoswe_repo_root())
    existing["mcpServers"] = servers

    # Preserve operator settings, then ensure autoSWE's own (non-interactive:
    # freeze direct tools, no sampling/elicitation).
    settings = existing.get("settings")
    if not isinstance(settings, dict):
        settings = {}
    settings.update({"freezeDirectTools": True, "sampling": False, "elicitation": False})
    existing["settings"] = settings

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2)
            f.write("\n")
        log(f"[PI] wrote autoswe_comment config to {path}")
    except OSError as e:
        log(f"[PI] could not write mcp.json at {path}: {e}")


def _resolve_pi_executable(cli_path: str | None) -> tuple[str, list[str]]:
    """Resolve the pi executable path.

    Precedence: ``spec.cli_path`` (an explicit profile path) → ``shutil.which``
    for ``"pi"`` on PATH → bare ``"pi"`` (let the OS/PATH decide).

    On Windows the npm install resolves to a ``.cmd``/``.bat`` shim, which
    ``asyncio.create_subprocess_exec`` (→ CreateProcess) cannot run directly.
    In that case we invoke through ``cmd /c <path> ...``.  Returns a tuple of
    ``(argv[0], prefix_args)`` where *prefix_args* is prepended to the flag
    list (``["cmd", "/c"]`` for a Windows shim, else empty).

    NOTE: codex.py has the same latent .cmd/.bat gap — its ``cmd`` argv is a
    bare ``"codex"`` and would fail the same way on a Windows npm install.
    Per plan, we flag it here but do NOT fix it in this issue.
    """
    path = (cli_path or "").strip()
    if not path:
        path = shutil.which("pi") or "pi"
    # On native Windows (os.name == "nt") the npm install resolves to a
    # .cmd/.bat shim that CreateProcess cannot run directly — invoke through
    # `cmd /c`.
    if os.name == "nt" and path.lower().endswith((".cmd", ".bat")):
        return path, ["cmd", "/c"]
    return path, []


def _tools_for_spec(spec: RunSpec) -> list[str]:
    """Derive the --tools allowlist from RunSpec.mode + extra_tools.

    The base allowlist comes from spec.mode (falling back to the read_write
    set when mode is unset).  spec.extra_tools appends additional tools.
    Duplicates are collapsed while preserving order.

    On Windows, read_write additionally grants ``powershell`` (the native
    shell built-in) so a Windows host keeps its shell alongside bash.
    """
    mode = spec.mode or "read_write"
    base = list(_MODE_TOOLS.get(mode, _DEFAULT_TOOLS))
    if os.name == "nt" and mode == "read_write":
        # On a Windows host the read_write mode keeps powershell in addition
        # to the cross-platform set (the native shell built-in).
        if "powershell" not in base:
            base.append("powershell")
    for tool in spec.extra_tools or []:
        if tool and tool not in base:
            base.append(tool)
    return base


def _excluded_tools_for_spec(spec: RunSpec) -> list[str]:
    """Build the --exclude-tools denylist.

    ask_question is always excluded (would block a non-interactive run);
    spec.disallowed_tools_override adds operator-supplied entries.  Duplicates
    are collapsed while preserving order.
    """
    tools: list[str] = list(_ALWAYS_EXCLUDED_TOOLS)
    for tool in spec.disallowed_tools_override or []:
        if tool and tool not in tools:
            tools.append(tool)
    return tools


def _build_argv(
    spec: RunSpec,
    harness_cfg: dict,
    pi_path: str,
    prefix_args: list[str],
    session_id: str,
) -> list[str]:
    """Build the full argv for a pi --mode json run.

    | Case | session flags |
    |---|---|
    | fresh | ``--session-id <uuid4>`` |
    | resume | ``--session <spec.resume>`` |
    | fork  | ``--fork <spec.resume> --session-id <new uuid4>`` (only when spec.fork_session) |

    The session_id passed in is the id we pinned (fresh/fork) or the resumed
    id — it is pre-seeded into the accumulator so RunResult.session_id is
    always meaningful even on a premature death.
    """
    # prefix_args (e.g. ["cmd", "/c"] for a Windows .cmd/.bat shim) must come
    # *before* the pi path so the command reads `cmd /c <pi> --mode json ...`.
    cmd = [*prefix_args, pi_path]

    # --mode json: non-interactive JSON-line stream (docs/pi/json.md).
    cmd.extend(["--mode", "json"])

    # Model / provider / thinking.  pi resolves a settings default when no
    # model is given; the factory enforces model presence for reproducibility,
    # but we still guard here for direct PiBackend().run(spec) calls.
    model = str(spec.model or "").strip()
    if model:
        cmd.extend(["--model", model])
    provider = str(harness_cfg.get("provider") or "").strip()
    if provider:
        cmd.extend(["--provider", provider])
    thinking = str(harness_cfg.get("thinking") or "").strip()
    if thinking:
        cmd.extend(["--thinking", thinking])

    # Tool allowlist + denylist (real read-only enforcement via "mode").
    tools = _tools_for_spec(spec)
    if tools:
        cmd.extend(["--tools", ",".join(tools)])
    excluded = _excluded_tools_for_spec(spec)
    if excluded:
        cmd.extend(["--exclude-tools", ",".join(excluded)])

    # Project trust.  Non-interactive modes default to defaultProjectTrust:
    # ask and IGNORE project-local resources unless --approve is passed
    # (docs/pi/usage.md:126).  The dedicated-machine posture is to trust.
    if bool(harness_cfg.get("approve_project", True)):
        cmd.append("--approve")

    # API key (overrides environment).  The env-precedence handling for the
    # key also happens in the subprocess env below; the --api-key flag makes
    # it explicit and wins over env vars per docs/pi/usage.md.
    api_key = str(harness_cfg.get("api_key") or "").strip()
    if api_key:
        cmd.extend(["--api-key", api_key])

    # Session flags (fresh / resume / fork).
    if spec.fork_session and spec.resume:
        cmd.extend(["--fork", spec.resume, "--session-id", session_id])
    elif spec.resume:
        cmd.extend(["--session", spec.resume])
    else:
        cmd.extend(["--session-id", session_id])

    # System prompt: --system-prompt replaces the default prompt entirely
    # (context files and skills are still appended); --append-system-prompt
    # adds to it.  Both are another Codex gap closed by pi.
    system_prompt = str(harness_cfg.get("system_prompt") or "").strip()
    if system_prompt:
        cmd.extend(["--system-prompt", system_prompt])
    append_prompt = str(harness_cfg.get("append_system_prompt") or "").strip()
    if append_prompt:
        cmd.extend(["--append-system-prompt", append_prompt])

    # Session storage directory (overrides the PI_CODING_AGENT_SESSION_DIR
    # env var, which the runner builds from the agent_dir / session_dir
    # profile fields below).
    session_dir = str(harness_cfg.get("session_dir") or "").strip()
    if session_dir:
        cmd.extend(["--session-dir", session_dir])

    # Prompt always behind -- so prompts starting with '-' are safe.
    cmd.extend(["--", spec.prompt])
    return cmd


# ---------- Stream parsing ----------


def _assistant_text(message: dict) -> str:
    """Extract text content from an assistant message's content blocks.

    AssistantMessage.content is a list of typed blocks; the text blocks are
    ``{"type": "text", "text": ...}``.  Thinking blocks and tool calls are
    excluded — only natural-language text feeds RunResult.text.
    """
    content = message.get("content")
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            text = block.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "\n".join(p for p in parts if p)


def _tool_label(event: dict) -> str:
    """Render a tool_execution event as a compact progress label.

    bash → the command; edit/write → the file path; anything else → a generic
    label.  ``args`` is a free-form object, so each tool is read defensively.
    """
    tool = event.get("toolName", "tool")
    args = event.get("args") or {}
    if not isinstance(args, dict):
        args = {}
    if tool in ("edit", "write"):
        path = args.get("path") or args.get("file_path") or ""
        return f"{tool} {path}".strip()
    if tool in ("bash", "powershell"):
        command = args.get("command") or ""
        return f"bash {command}" if tool == "bash" else f"{tool} {command}"
    return str(tool)


def _fire_delta_progress(acc: _PiAccumulator, callback, index: int, delta: str) -> None:
    """Fire throttled progress for a text/thinking delta event.

    Progress lines are fire-and-forget; bounding output matters.  Fires on the
    first delta for a content index and again once the accumulated text has
    grown by ~80 chars since the last fire (mirrors codex._fire_delta_progress).
    """
    if not callback or not delta:
        return
    streamed = acc._delta_streamed.get(index, 0) + len(delta)
    acc._delta_streamed[index] = streamed
    fired_at = acc._delta_fired_at.get(index, -1)
    if fired_at < 0 or streamed - fired_at >= 80:
        acc._delta_fired_at[index] = streamed
        callback(delta[:120])


def _parse_line(line: str, acc: _PiAccumulator, callback) -> None:
    """Parse a single JSON stream line and update the accumulator in-place.

    *acc* is a ``_PiAccumulator`` instance mutated by this function.
    """
    line = line.strip()
    if not line:
        return
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        # Non-JSON line (stderr leak, progress) — skip.
        return
    if not isinstance(event, dict):
        return

    etype = event.get("type", "")

    if etype == "session":
        # Session header: authoritative source of the session id.  We pre-seed
        # the accumulator with the id we passed on --session-id/--session, so
        # when pi actually runs it echoes back that same id (confirmation).
        # If the header carries a *different* id, the header wins (it reflects
        # the session pi really used) and we log the mismatch.  If the process
        # dies before emitting the header, the pre-seeded id survives —
        # strictly better than a parse-only path that would return None.
        header_id = event.get("id")
        if header_id:
            header_id = str(header_id)
            if acc.session_id is not None and header_id != acc.session_id:
                log(f"[PI] session header id {header_id[:8]} != requested "
                    f"{acc.session_id[:8]} — using header id")
            acc.session_id = header_id

    elif etype == "message_update":
        # Delta-only event.  Capture the latest cost from the top-level usage
        # block, then handle text/thinking deltas for live text + progress.
        cost = _extract_cost(event)
        if cost is not None:
            acc.cost_usd = cost
        ame = event.get("assistantMessageEvent")
        if isinstance(ame, dict):
            sub = ame.get("type", "")
            index = ame.get("contentIndex", 0)
            if not isinstance(index, int):
                index = 0
            delta = ame.get("delta")
            if sub == "text_delta" and isinstance(delta, str) and delta:
                # Natural-language text: accumulate for the RunResult.text
                # fallback AND fire live progress.
                acc._delta_by_index.setdefault(index, []).append(delta)
                _fire_delta_progress(acc, callback, index, delta)
            elif sub == "thinking_delta" and isinstance(delta, str) and delta:
                # Reasoning: progress-only, NEVER accumulated into the text
                # fallback.  message_end's text blocks already exclude
                # thinking content, so the fallback must match — folding
                # thinking in would leak internal reasoning into
                # RunResult.text on a run killed before message_end
                # (mirrors codex, where reasoning deltas are progress-only).
                if callback:
                    callback(f"💭 {delta[:120]}")

    elif etype == "message_end":
        message = event.get("message")
        if isinstance(message, dict):
            # Authoritative text source (docs/pi/json.md).  Only the assistant
            # role's text feeds RunResult.text; toolResult/user are ignored.
            if message.get("role") == "assistant":
                text = _assistant_text(message)
                if text:
                    acc.text = text
                    if callback:
                        callback(f"Agent: {text[:120]}")
            # The final message carries the authoritative cost.
            cost = _extract_cost(event)
            if cost is not None:
                acc.cost_usd = cost

    elif etype in ("tool_execution_start", "tool_execution_end"):
        if etype == "tool_execution_start":
            if callback:
                callback(f"Tool: {_tool_label(event)}")
        else:
            # End: surface a failing tool so the operator sees it live.  Per
            # the plan, a tool result carrying isError: true sets the run's
            # error flag (mirrors how a tool failure is a signal something
            # went wrong).  Tradeoff: a routine nonzero-exit tool (e.g. a
            # grep that matches nothing) also flips the subtype to "error" —
            # accepted per the explicit spec ("extension_error and isError set
            # the error flag").
            if event.get("isError"):
                log(f"[PI] tool {event.get('toolName')} failed (isError)")
                acc.has_error = True
            elif callback:
                callback(f"Tool done: {_tool_label(event)}")

    elif etype == "agent_end":
        acc.agent_end = True
        # agent_end carries the final cumulative cost across the whole run.
        cost = _extract_cost(event)
        if cost is not None:
            acc.cost_usd = cost

    elif etype == "extension_error":
        err = event.get("error", "unknown extension error")
        log(f"[PI] extension_error: {err}")
        acc.has_error = True

    elif etype == "error":
        # Generic error event (defensive; pi's documented stream has no such
        # type, but tolerate it like codex does).
        err = event.get("message", event.get("error", "unknown error"))
        log(f"[PI] error event: {err}")
        acc.has_error = True

    # tool_execution_update / turn_* / message_start / queue_update /
    # compaction_* are intentionally ignored (high-volume or no progress value).


# ---------- PiBackend ----------


class PiBackend:
    """pi CLI backend implementing CodingBackend.

    Shells out to ``pi --mode json`` (or its resume/fork flag variants),
    streams the JSON event lines for live progress, and returns a RunResult.

    ``cost_usd`` is provider-reported (``usage.cost.total``) — no estimate.
    Duration is tracked via ``time.monotonic()``.
    """

    # "mode" is advertised: pi enforces read-only via the tool allowlist
    # derived from RunSpec.mode, so has_read_only_enforcement() is True.
    CAPABILITIES: set[str] = {"mode", "resume", "session_fork", "progress_stream"}
    RETRYABLE_SUBTYPES: set[str] = {"error", "killed"}

    @classmethod
    def capabilities(cls) -> set[str]:
        return cls.CAPABILITIES.copy()

    @classmethod
    def retryable_subtypes(cls) -> set[str]:
        return cls.RETRYABLE_SUBTYPES.copy()

    @classmethod
    def retryable_exceptions(cls) -> tuple:
        # pi has no SDK; its failure surface is the subprocess boundary, same
        # as Codex.  asyncio.TimeoutError is the runner's wall-clock timeout
        # (wait_for); OSError covers spawn-time failures from
        # create_subprocess_exec (PermissionError, a missing/incompatible
        # executable, etc.).  FileNotFoundError is an OSError subclass.
        return (asyncio.TimeoutError, OSError)

    def run(self, spec: RunSpec) -> Awaitable[RunResult]:
        """Execute the spec via the pi CLI.

        Returns an awaitable that resolves to a RunResult.

        Uses ``asyncio.create_subprocess_exec`` so that ``progress_callback``
        fires with live updates while the pi CLI is running.  The runner wraps
        this in ``asyncio.wait_for`` for timeouts.
        """
        harness_cfg = (spec.state or {}).get("_harness_cfg") or {}

        # Decide the session id up front so the accumulator is pre-seeded
        # with it (survives a premature death before the session header).
        #   fork  -> a NEW uuid4 (the forked session's id; spec.resume is the
        #            source we branch from, NOT this run's identity).
        #   resume-> spec.resume (we continue the existing session in place).
        #   fresh -> a new uuid4.
        fork = bool(spec.fork_session and spec.resume)
        if spec.resume and not fork:
            pinned_id = spec.resume
        else:
            pinned_id = str(uuid.uuid4())

        async def _wrapped() -> RunResult:
            return await self._run_async(spec, harness_cfg, pinned_id, fork)

        return _wrapped()

    async def _run_async(
        self, spec: RunSpec, harness_cfg: dict, pinned_id: str, fork: bool
    ) -> RunResult:
        """Run the pi CLI subprocess with streaming JSON.  Returns RunResult.

        ``pinned_id`` is the session id we pin this run to: ``spec.resume``
        for a resume, a fresh uuid4 for a fork (the forked session's new id)
        or a fresh run.  It is pre-seeded into the accumulator so
        ``RunResult.session_id`` is meaningful even if the process dies before
        emitting the session header.
        """
        # pi resolves a settings default model when none is given.  The
        # factory enforces model presence for reproducibility; this guard
        # protects direct PiBackend().run(spec) calls that bypass the factory.
        model = str(spec.model or "").strip()
        if not model:
            raise ValueError(
                "pi harness profile is missing required 'model'. "
                "Set it to a current model, e.g. a provider/model pattern like "
                "'anthropic/claude-sonnet-4-5' or a configured model id."
            )

        pi_path, prefix_args = _resolve_pi_executable(spec.cli_path)
        cmd = _build_argv(spec, harness_cfg, pi_path, prefix_args, pinned_id)

        # Build environment.  Precedence identical in spirit to the other
        # backends: os.environ < named profile fields < profile "env" <
        # spec.env_overrides.  Two notes that make pi's chain slightly
        # different:
        #   - The API key is NOT injected as an env var: pi's ``--api-key``
        #     flag (emitted above from the same harness_cfg) already carries
        #     it and "overrides environment variables" (docs/pi/usage.md), so
        #     guessing a provider-specific env var name would be redundant
        #     and unverified.
        #   - The agent_dir profile field IS a named env field: it maps to
        #     PI_CODING_AGENT_DIR (pi's config-directory override; default
        #     ~/.pi/agent).  It sits below profile "env", so an operator can
        #     still redirect pi's config via ``"env": {"PI_CODING_AGENT_DIR": …}``.
        env = dict(os.environ)
        agent_dir = str(harness_cfg.get("agent_dir") or "").strip()
        if agent_dir:
            env["PI_CODING_AGENT_DIR"] = agent_dir
        env.update(harness_cfg.get("env") or {})
        if spec.env_overrides:
            env.update(spec.env_overrides)

        # Phase 1 of PLAN-pi-mcp.md: when the run names the autoswe_comment MCP
        # server, give pi the server config in its agent dir (the
        # pi-mcp-adapter reads <agent dir>/mcp.json) and route the server's own
        # env into this subprocess instead of into the file. The adapter
        # inherits pi's process env into the MCP server child (resolveEnv), so
        # the per-task vars set here reach the server without the config file
        # ever changing between issues. The file only carries stable values.
        # (Phase 2 adds the mcp__autoswe_comment_* tool names to the allowlist
        # and parses the tool_execution events; until then the server is set up
        # but its tools are not yet in the --tools allowlist.)
        mcp_servers = spec.mcp_servers or {}
        comment_cfg = mcp_servers.get("autoswe_comment") if isinstance(mcp_servers, dict) else None
        if isinstance(comment_cfg, dict):
            server_env = comment_cfg.get("env") or {}
            if isinstance(server_env, dict):
                env.update(server_env)
            _write_pi_mcp_json(agent_dir)

        log(
            f"[PI] running model={model} "
            f"session={'NEW' if not spec.resume else spec.resume[:8]} "
            f"fork={'yes' if fork else 'no'} tools={'yes'}"
        )

        t0 = time.monotonic()

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=spec.cwd,
            )
        except FileNotFoundError as e:
            raise RuntimeError(
                "pi executable not found on PATH. "
                "Install with: npm i -g @earendil-works/pi-coding-agent"
            ) from e
        except (PermissionError, OSError) as e:
            # Surface spawn-time failures under the backend's retryable
            # exception set so the runner retries instead of crashing.
            raise OSError(f"failed to spawn pi executable: {e}") from e

        acc = _PiAccumulator()
        # Pre-seed the session id so a premature death still reports it.
        acc.session_id = pinned_id

        async def read_stderr() -> bytes:
            """Collect stderr output in chunks, bounded by _MAX_STREAM_BYTES.

            After the limit is hit, the pipe is drained (discarding data) so
            the child process does not block on a full pipe buffer.
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
                    log(f"[PI] stderr exceeded {_MAX_STREAM_BYTES} bytes — truncating")
                    while True:
                        leftover = await process.stderr.read(64 * 1024)
                        if not leftover:
                            break
                    break
                chunks.append(chunk)
            return b"".join(chunks)

        async def read_stdout_jsonl() -> None:
            """Read stdout line-by-line, parse JSON events, fire callbacks.

            Bounded by _MAX_STREAM_BYTES to prevent pipe-buffer deadlock and
            unbounded memory growth.  After the limit is hit, the pipe is
            drained (discarding data) so the child does not block.
            """
            if process.stdout:
                total_bytes = 0
                while True:
                    raw = await process.stdout.readline()
                    if not raw:
                        break
                    total_bytes += len(raw)
                    if total_bytes > _MAX_STREAM_BYTES:
                        log(f"[PI] stdout exceeded {_MAX_STREAM_BYTES} bytes — truncating stream")
                        acc.has_error = True
                        while True:
                            leftover = await process.stdout.read(64 * 1024)
                            if not leftover:
                                break
                        break
                    text = raw.decode("utf-8", errors="replace")
                    _parse_line(text, acc=acc, callback=spec.progress_callback)

        try:
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
            log(f"[PI] timeout after {spec.timeout}s — killed process")
            raise

        returncode = process.returncode
        duration = time.monotonic() - t0

        if returncode != 0:
            log(f"[PI] exit={returncode}")

        # Determine subtype from exit code and in-stream errors.
        # asyncio.subprocess uses negative values for signal-killed processes
        # (e.g. -9 = SIGKILL, -15 = SIGTERM).  Positive values are normal exit
        # codes returned by the process itself.
        if returncode == 0 and not acc.has_error:
            subtype = "success"
        elif returncode == 0 and acc.has_error:
            subtype = "error"
        elif returncode is not None and returncode < 0:
            subtype = "killed"
        else:
            subtype = "error"

        # Assemble the text: prefer the authoritative message_end assistant
        # text; fall back to the accumulated deltas (e.g. a run killed before
        # message_end).  message_end "replaces" the deltas — we never mix
        # authoritative text with partial deltas.
        if acc.text:
            text = acc.text
            source = "message_end"
        else:
            # Reassemble deltas in contentIndex order for the fallback path.
            fallback_parts: list[str] = []
            for index in sorted(acc._delta_by_index):
                chunk = "".join(acc._delta_by_index[index]).strip()
                if chunk:
                    fallback_parts.append(chunk)
            text = "\n".join(fallback_parts)
            source = "delta fallback"
        log(f"[PI] RunResult.text from {source} ({len(text)} chars)")

        # The agent_end event is the stream's completion marker.  Absence on a
        # nonzero/killed exit is the expected "interrupted mid-stream" signal;
        # log it so an operator debugging a short run can see the stream never
        # reached agent_end.
        if returncode != 0 and not acc.agent_end:
            log(f"[PI] stream did not reach agent_end (exit={returncode})")

        return RunResult(
            text=text,
            session_id=acc.session_id,
            subtype=subtype,
            ok=(subtype == "success"),
            cost_usd=acc.cost_usd,
            duration_seconds=duration,
            plan_file_path=None,
            plan_posted=False,
            question_posted=False,
            structured_output=None,
        )
