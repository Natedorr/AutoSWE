"""Claude Code backend — implements CodingBackend using the Claude Agent SDK.

All Claude-specific execution logic (ClaudeAgentOptions construction, SDK
message streaming, ProgressState, plan-file capture) lives here.  runner.py
is now a thin dispatcher that delegates to this backend.

Phase 3: translates RunSpec.mode into Claude-specific permission_mode,
allowed_tools, and disallowed_tools.  Per-mode tool lists live here as the
canonical mapping, so handlers no longer carry Claude-specific tool names.
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable
from pathlib import Path

from autoswe.core.logging_utils import get_debug_logger, log
from autoswe.harness.backends.base import RunResult, RunSpec
from autoswe.harness.prompts import BOT_MARKER

_dbg = get_debug_logger()

_RETRYABLE_SDK_EXCEPTIONS: tuple = ()
_PLANS_DIR = Path.home() / ".claude" / "plans"

# ---------- Claude Code tool sets ----------
#
# These are Claude-Code-specific tool names and therefore live here — in the
# backend that actually consumes them — not in the harness-agnostic base
# (S6 / issue #169 F-10). runner.py and backends/__init__.py re-export them
# for back-compat so existing importers need no changes.

# Read-only-safe progress/orchestration tools (no repo mutation)
PROGRESS_TOOLS = [
    "TodoWrite",
    "TaskCreate", "TaskUpdate", "TaskGet", "TaskList", "TaskStop",
]

# Full agent toolset: includes sub-agent spawning. Only safe for fix/coder phases.
AGENT_TASK_TOOLS = [*PROGRESS_TOOLS, "Agent"]

# Claude Code's default system-prompt preset. When system_prompt is unset the
# SDK falls back to a minimal prompt that covers tool calling but omits the
# preset's tool-usage guidance, security/safety instructions, and
# working-directory/environment context. Setting the bare preset makes
# plan/fix/review run on the full Claude Code prompt.
#
# Plain dict (NOT MappingProxyType): the Agent SDK branches on
# ``isinstance(system_prompt, dict)`` (e.g. to read exclude_dynamic_sections),
# and a MappingProxyType fails that check even though it compares equal to a
# dict. Content-based equality with a plain dict still holds, so tests that
# assert ``system_prompt == CLAUDE_CODE_SYSTEM_PROMPT_PRESET`` are unaffected.
# The shared constant is only ever read by the SDK; call sites that build
# ``options_kwargs`` pass ``dict(CLAUDE_CODE_SYSTEM_PROMPT_PRESET)`` (a fresh
# copy) so the module-level object is never mutated.
CLAUDE_CODE_SYSTEM_PROMPT_PRESET = {
    "type": "preset", "preset": "claude_code",
}

# ---------- Mode → Claude Code mapping ----------

# MCP comment tool names (shared across plan/read_write modes).
# Defined here so handlers don't need to know about MCP tool naming.
_MCP_COMMENT_TOOLS = [
    "mcp__autoswe_comment__update_progress",
    "mcp__autoswe_comment__post_plan",
    "mcp__autoswe_comment__post_question",
]

# Base read-only tools (file inspection, search, progress tracking).
# Does NOT include AskUserQuestion — add via extra_tools if needed (planner).
_READ_ONLY_TOOLS = [
    "Read", "Glob", "Grep",
    *_MCP_COMMENT_TOOLS, *PROGRESS_TOOLS,
]

# Full read-write tools (everything the fix phase needs)
#
# NOTE on TaskOutput: the *deprecated* TaskOutput tool was removed in
# issue #132 (commit 8198408) — from the shared PROGRESS_TOOLS list (which
# feeds _READ_ONLY_TOOLS / _PLAN_TOOLS) and, because this read_write list is
# hand-maintained and does not spread PROGRESS_TOOLS, from this list with a
# separate edit. It is deliberately re-added here (S6 follow-up on issue
# #169): in the fix phase the coder may spawn background sub-agents via Agent
# and read their output directly through TaskOutput (Read remains the
# canonical fallback). read_only/plan still omit it, matching #132.
_READ_WRITE_TOOLS = [
    "Read", "Edit", "Write", "Bash", "Glob", "Grep",
    "AskUserQuestion", *_MCP_COMMENT_TOOLS,
    "TodoWrite", "TaskCreate", "TaskUpdate", "TaskGet",
    "TaskList", "TaskOutput", "TaskStop", "Agent",
]

# Plan mode tools (read-only + AskUserQuestion + plan MCP tools, Agent excluded).
# Planner needs AskUserQuestion to ask clarifying questions.
_PLAN_TOOLS = [
    "Read", "Glob", "Grep", "AskUserQuestion",
    *_MCP_COMMENT_TOOLS, *PROGRESS_TOOLS,
]

# Mode → (permission_mode, allowed_tools, disallowed_tools) mapping
# Values are tuples to prevent accidental mutation of tool lists.
_MODE_CONFIG = {
    "plan": ("plan", _PLAN_TOOLS, ("ExitPlanMode",)),
    "read_only": ("plan", _READ_ONLY_TOOLS, ()),
    "read_write": ("bypassPermissions", _READ_WRITE_TOOLS, ()),
}


# Minimum Agent SDK version that exposes ``fork_session`` (and
# ``resume_session_at``). ``claude-agent-sdk`` ships no pinned ``__version__``
# everywhere, so we read the installed distribution version defensively and
# treat an unreadable/unknown version as "new enough" (the capability is still
# advertised; the guard only degrades to plain resume on a *known* old SDK).
_FORK_MIN_SDK_VERSION = (0, 2, 137)

# Minimum Agent SDK version that exposes ``output_format`` on
# ``ClaudeAgentOptions`` and ``ResultMessage.structured_output``. Verified to
# be 0.2.137 — the same floor as ``fork_session`` (see requirements.txt /
# tests/test_sdk_version.py). On a *known* older SDK the guard degrades to a
# plain run (no output_format) rather than passing an unknown option.
_STRUCTURED_OUTPUT_MIN_SDK_VERSION = (0, 2, 137)


def _sdk_version_tuple() -> tuple | None:
    """Return the installed ``claude-agent-sdk`` (major, minor, patch), or None."""
    try:
        from importlib.metadata import version  # deferred import
        raw = version("claude-agent-sdk")
    except Exception:
        return None
    parts = raw.split(".")
    try:
        major, minor = int(parts[0]), int(parts[1])
    except (IndexError, ValueError):
        return None
    patch = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
    return (major, minor, patch)


def _sdk_supports_structured_output() -> bool:
    """Return True when the installed Agent SDK is new enough for ``output_format``.

    Reads the installed ``claude-agent-sdk`` distribution version lazily. Returns
    True when the version cannot be read so a fresh/edge install is not needlessly
    demoted; the guard only skips the option on a *known* old SDK.
    """
    ver = _sdk_version_tuple()
    if ver is None:
        return True
    return ver >= _STRUCTURED_OUTPUT_MIN_SDK_VERSION


def _sdk_supports_session_fork() -> bool:
    """Return True when the installed Agent SDK is new enough for ``fork_session``.

    Reads the installed ``claude-agent-sdk`` distribution version lazily (the
    SDK is a heavy, possibly-missing dependency). Returns True when the version
    cannot be read so a fresh/edge install is not needlessly demoted.
    """
    ver = _sdk_version_tuple()
    if ver is None:
        return True
    return ver >= _FORK_MIN_SDK_VERSION


def _get_retryable_exceptions() -> tuple:
    """Lazily build the tuple of SDK exception types to retry on.

    NOTE: All claude_agent_sdk imports in this module are deferred — the SDK is a
    heavy dependency that may not be installed (e.g., Codex-only deploys).  Lazy
    loads avoid slow cold-start and ImportError at module import time.
    """

    global _RETRYABLE_SDK_EXCEPTIONS
    if _RETRYABLE_SDK_EXCEPTIONS:
        return _RETRYABLE_SDK_EXCEPTIONS
    try:
        from claude_agent_sdk import ClaudeSDKError, CLIConnectionError, ProcessError  # deferred import: SDK may not be installed  # noqa: I001
        _RETRYABLE_SDK_EXCEPTIONS = (asyncio.TimeoutError, ProcessError, CLIConnectionError, ClaudeSDKError)
    except ImportError:
        _RETRYABLE_SDK_EXCEPTIONS = (asyncio.TimeoutError,)
    return _RETRYABLE_SDK_EXCEPTIONS


# ---------- Tool-use helpers ----------


def _format_tool_progress(block) -> str | None:
    """Format a tool-use block into a short progress string."""
    from claude_agent_sdk import ServerToolUseBlock, ToolUseBlock  # deferred import: SDK may not be installed

    if isinstance(block, ToolUseBlock):
        name = block.name
        inputs = block.input or {}
        if name == "Bash":
            cmd = inputs.get("command", "")
            return f"Running: {cmd[:80]}"
        elif name in ("Read", "Glob", "Grep"):
            path = inputs.get("file_path") or inputs.get("pattern") or inputs.get("path", "")
            return f"{name}: {path[:80]}"
        elif name == "Edit":
            path = inputs.get("file_path", "")
            return f"Editing: {path[:80]}"
        elif name == "Write":
            path = inputs.get("file_path", "")
            return f"Writing: {path[:80]}"
        elif name.startswith("mcp__"):
            # MCP tool: mcp__<server>__<tool>
            return f"MCP: {name}"
        else:
            return f"Tool: {name}"
    elif isinstance(block, ServerToolUseBlock):
        return f"Server tool: {block.name}"
    return None


def plan_file_dir() -> Path:
    """Return the native plan-file directory the Claude Code SDK writes to.

    The plan-file path is a Claude-Code-SDK concern (the SDK writes plan
    files to ``~/.claude/plans/`` natively), so this accessor lives here — the
    backend that owns the path — rather than in the harness-agnostic planner
    (S6 / issue #169 F-10). The planner reads it through this accessor, gated
    on the ``plan_file`` capability.
    """
    return _PLANS_DIR


def _extract_plan_file_path(block) -> str | None:
    """If *block* is a Write tool call targeting the plans directory, return its path.

    Returns None for non-Write blocks or Write calls outside the plans
    directory.  We accept both ``file_path`` and ``path`` input keys
    (the SDK / Claude CLI use either depending on version).
    """
    from claude_agent_sdk import ToolUseBlock  # deferred import: SDK may not be installed

    if not isinstance(block, ToolUseBlock) or block.name != "Write":
        return None

    inputs = block.input or {}
    path_str = inputs.get("file_path") or inputs.get("path", "")
    if not path_str:
        return None

    p = Path(path_str)
    try:
        resolved = p.resolve()
        if _PLANS_DIR in resolved.parents or resolved == _PLANS_DIR:
            return str(p)
    except (OSError, ValueError):
        # Path doesn't exist yet or can't be resolved — check the string
        # prefix as a best-effort heuristic
        if path_str.startswith(str(_PLANS_DIR)):
            return str(p)

    return None


def _parse_task_id(block):
    """Parse a task ID from a ToolResultBlock's content.

    Handles str, list of text blocks, or JSON-encoded forms.
    Returns None on failure (best-effort).
    """
    content = block.content
    if isinstance(content, str):
        stripped = content.strip()
        if not stripped:
            return None
        # Try JSON first in case it's '{"task_id": "..."}'
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, str) and parsed:
                return parsed.strip()
            if isinstance(parsed, dict):
                for key in ("task_id", "id"):
                    if parsed.get(key):
                        return str(parsed[key]).strip()
            # JSON parsed but yielded nothing useful — nothing to return
            return None
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
        return stripped
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict):
                text = item.get("text", "")
                if text:
                    return text.strip()
            elif isinstance(item, str) and item:
                return item.strip()
    log(f"[PROGRESS] failed to parse task id from ToolResultBlock: {content!r:.100}")
    return None


# ---------- Progress comment state machine ----------


class ProgressState:
    """Accumulates todo-state and last-command across the SDK message stream.

    Renders the full progress-comment body. Two item sources are supported:
    - ``todos``: snapshot from ``TodoWrite`` (primary, fully supported).
    - ``_tasks`` / ``_task_order``: accumulated from ``TaskCreate`` /
      ``TaskUpdate`` (fallback when the SDK exposes those tools).
    """

    _STATUS_ICON = {
        "completed": "✅",
        "in_progress": "🔧",
        "pending": "☐",
    }
    _TODO_HEADER = "📋"

    def __init__(self):
        self.todos: list | None = None  # TodoWrite snapshot
        self._tasks: dict = {}  # task_id -> dict
        self._task_order: list = []
        self._pending_creates: dict = {}  # block.id -> task info
        self.last_command: str | None = None
        self._last_render: str | None = None  # cached to avoid double-render

    # ---- Public API ----

    def note_tool_use(self, block) -> bool:
        """Process a ToolUseBlock.  Returns True if rendered output changed."""
        name = block.name

        if name == "TodoWrite":
            self._handle_todo_write(block)
        elif name == "TaskCreate":
            self._handle_task_create(block)
        elif name == "TaskUpdate":
            self._handle_task_update(block)
        else:
            cmd = _format_tool_progress(block)
            if cmd:
                self.last_command = cmd

        new = self.render()
        changed = new != self._last_render
        self._last_render = new
        return changed

    def note_tool_result(self, block) -> bool:
        """Process a ToolResultBlock.  Returns True if rendered output changed."""
        info = self._pending_creates.pop(block.tool_use_id, None)
        if info is not None:
            task_id = _parse_task_id(block)
            if task_id:
                info["task_id"] = task_id
                self._tasks[task_id] = info
                self._task_order.append(task_id)
        new = self.render()
        changed = new != self._last_render
        self._last_render = new
        return changed

    # ---- Handlers ----

    def _handle_todo_write(self, block):
        inputs = block.input or {}
        todos = inputs.get("todos")
        if isinstance(todos, list) and todos:
            self.todos = [
                {"content": t.get("content", ""), "activeForm": t.get("activeForm"), "status": t.get("status", "pending")}
                for t in todos
            ]
            # Task-tool state is stale only when TodoWrite provides a real snapshot
            self._tasks.clear()
            self._task_order.clear()
        elif isinstance(todos, list):
            self.todos = None

    def _handle_task_create(self, block):
        inputs = block.input or {}
        info = {
            "content": inputs.get("subject", ""),
            "activeForm": inputs.get("activeForm"),
            "status": "pending",
        }
        block_id = getattr(block, "id", None)
        if block_id:
            self._pending_creates[block_id] = info

    def _handle_task_update(self, block):
        inputs = block.input or {}
        task_id = inputs.get("taskId")
        if task_id is None:
            return
        status = inputs.get("status", "pending")
        if status == "deleted":
            self._tasks.pop(task_id, None)
            self._task_order = [t for t in self._task_order if t != task_id]
            return
        if task_id not in self._tasks:
            # Unknown task — skip rather than creating a ghost with empty content
            return
        task = self._tasks[task_id]
        if "subject" in inputs:
            task["content"] = inputs["subject"]
        if "activeForm" in inputs:
            task["activeForm"] = inputs["activeForm"]
        task["status"] = status

    # ---- Render ----

    def render(self) -> str | None:
        """Build the full comment body, or None when nothing to show."""
        items = self._get_items()
        if items:
            lines = [f"### {self._TODO_HEADER} Todo List", ""]
            for item in items:
                icon = self._STATUS_ICON.get(item["status"], self._STATUS_ICON["pending"])
                if item["status"] == "in_progress" and item.get("activeForm"):
                    text = item["activeForm"]
                else:
                    text = item["content"]
                lines.append(f"- {icon} {text}")
            if self.last_command:
                lines.append("")
                lines.append(f"**Last command:** `{self.last_command}`")
            return "\n".join(lines) + "\n"
        if self.last_command:
            return self.last_command
        return None

    def _get_items(self) -> list:
        if self.todos:
            return self.todos
        if self._task_order:
            return [self._tasks[tid] for tid in self._task_order if tid in self._tasks]
        return []


# ---------- ClaudeCodeBackend ----------


class ClaudeCodeBackend:
    """Claude Agent SDK backend implementing CodingBackend.

    Translates a RunSpec into ClaudeAgentOptions, streams the SDK message
    iterator, and returns a RunResult.
    """

    CAPABILITIES = {
        "mode",
        "mcp",
        "can_use_tool",
        "plan_permission",
        "resume",
        "session_fork",
        "progress_stream",
        "plan_file",
        "structured_output",
    }

    @classmethod
    def capabilities(cls) -> set[str]:
        return cls.CAPABILITIES.copy()

    @classmethod
    def retryable_subtypes(cls) -> set[str]:
        # Claude retries via SDK exceptions (retryable_exceptions), not subtypes.
        return set()

    @classmethod
    def retryable_exceptions(cls) -> tuple:
        # Claude retries on SDK exception types: TimeoutError + the Agent SDK
        # error classes, degrading to bare TimeoutError when the SDK is absent.
        return _get_retryable_exceptions()

    def run(self, spec: RunSpec) -> Awaitable[RunResult]:
        """Execute the spec via Claude Agent SDK.

        Returns an awaitable that resolves to a RunResult.
        """
        return self._run_async(spec)

    async def _run_async(self, spec: RunSpec) -> RunResult:
        """Run Claude Agent SDK. Returns a RunResult dataclass."""
        from claude_agent_sdk import (  # deferred import: SDK may not be installed
            AssistantMessage,
            ClaudeAgentOptions,
            ResultMessage,
            ServerToolUseBlock,
            TextBlock,
            ToolResultBlock,
            ToolUseBlock,
            UserMessage,
            query,
        )

        _resume_lbl = "NEW" if not spec.resume else spec.resume[:8]
        _fork_lbl = " fork" if (spec.fork_session and spec.resume) else ""
        log(f"[CLAUDE] starting cwd={spec.cwd} resume={_resume_lbl}{_fork_lbl} model={spec.model} mode={spec.mode}")

        # --- Build the per-session child-process env (no os.environ mutation) ---
        # The Claude Agent SDK merges this into the spawned CLI's environment,
        # so these values reach only the child CLI — never the poller's own
        # process env (credential isolation, task-tracking opt-in).
        harness_cfg = (spec.state or {}).get("_harness_cfg") or {}

        # Backend default: opt into the task-tracking tools. On Agent SDK
        # >= 0.2.139 these are NOT provided by default on the newer model
        # families (Opus 4.8, Sonnet 5, ...); CLAUDE_CODE_ENABLE_TODO_TOOLS=1
        # restores them (honor requires CLI >= v2.1.233). The sticky progress
        # comment renders from these tools, so opt in by default.
        #
        # Note: this 0.2.139 threshold is independent of _FORK_MIN_SDK_VERSION
        # (0.2.137) — that is the floor for the fork_session capability, a
        # different feature. The todo-tools default flips two patch levels
        # later; on a 0.2.137/0.2.138 install the env var is simply inert
        # (unknown option) and the sticky comment just doesn't render.
        env = {"CLAUDE_CODE_ENABLE_TODO_TOOLS": "1"}

        # Anthropic credentials from the harness profile.
        if harness_cfg.get("anthropic_base_url"):
            env["ANTHROPIC_BASE_URL"] = harness_cfg["anthropic_base_url"]
        if harness_cfg.get("anthropic_auth_token"):
            env["ANTHROPIC_AUTH_TOKEN"] = harness_cfg["anthropic_auth_token"]
        if harness_cfg.get("anthropic_api_key"):
            env["ANTHROPIC_API_KEY"] = harness_cfg["anthropic_api_key"]

        # Per-harness-profile `env` override (Part B): user values win over
        # backend defaults (including CLAUDE_CODE_ENABLE_TODO_TOOLS above).
        env.update(harness_cfg.get("env") or {})

        # Explicit spec-level overrides take highest precedence.
        if spec.env_overrides:
            env.update(spec.env_overrides)

        # Drop empty-string values (a blank credential must not clobber a
        # real one in the inherited environment).
        env = {k: v for k, v in env.items() if v}

        # --- Resolve permission_mode + tool lists from mode (Phase 3) ---
        if spec.mode is not None:
            _perm, _tools, _disallowed = _MODE_CONFIG[spec.mode]
            final_allowed = list(_tools)
            # Append extra_tools (e.g. inline comment MCP tools)
            if spec.extra_tools:
                final_allowed.extend(spec.extra_tools)
            # Remove disallowed_tools_override (e.g. exclude AskUserQuestion)
            if spec.disallowed_tools_override:
                _disallowed = list(_disallowed) + list(spec.disallowed_tools_override)
        else:
            # Legacy path: use explicit fields directly (backward compat)
            _perm = spec.permission_mode
            final_allowed = spec.allowed_tools or ["Read", "Glob", "Grep"]
            _disallowed = spec.disallowed_tools or []

        options_kwargs = {
            "cwd": spec.cwd,
            "resume": spec.resume,
            "permission_mode": _perm,
            "allowed_tools": final_allowed,
            "disallowed_tools": _disallowed,
            "max_turns": spec.max_turns,
            "model": spec.model or None,
            "cli_path": spec.cli_path or harness_cfg.get("cli_path"),
            "mcp_servers": spec.mcp_servers or {},
            "system_prompt": dict(CLAUDE_CODE_SYSTEM_PROMPT_PRESET),
        }

        # Structured output (issue #159): when the spec requests a JSON-Schema
        # validated payload, hand it to the SDK so the agent's result is
        # delivered on ``ResultMessage.structured_output``. Gated on an SDK new
        # enough for ``output_format``; on a known-old SDK we log and run
        # without it (the handler's text-pattern fallback then applies).
        if spec.output_format is not None:
            if _sdk_supports_structured_output():
                options_kwargs["output_format"] = spec.output_format
            else:
                log(
                    f"[CLAUDE] output_format requested but installed Agent SDK is "
                    f"older than {_STRUCTURED_OUTPUT_MIN_SDK_VERSION}; running without "
                    f"structured output (text-pattern fallback will apply)"
                )

        # Fork-on-retry: when the spec asks to fork off a resume session, branch
        # into a NEW session (fork_session=True) so the original stays intact for
        # rollback. Gated on a non-empty resume and an SDK new enough for
        # fork_session; on an older SDK we log and degrade to a plain resume
        # rather than passing an unknown option to the SDK.
        if spec.fork_session and spec.resume:
            if _sdk_supports_session_fork():
                options_kwargs["fork_session"] = True
            else:
                log(
                    f"[CLAUDE] fork_session requested but installed Agent SDK is "
                    f"older than {_FORK_MIN_SDK_VERSION}; degrading to plain resume "
                    f"(original session will be continued in place)"
                )

        # Per-session child-process env (see construction above). The SDK merges
        # this over the inherited environment for the spawned CLI only.
        options_kwargs["env"] = env

        # --- Setup phase: can_use_tool requires streaming prompt + hooks ---
        if spec.can_use_tool is not None:
            from claude_agent_sdk import HookMatcher  # deferred import: SDK may not be installed

            async def dummy_hook(input_data, tool_use_id, ctx):
                return {"continue_": True}

            options_kwargs["can_use_tool"] = spec.can_use_tool
            options_kwargs["hooks"] = {
                "PreToolUse": [HookMatcher(matcher=None, hooks=[dummy_hook])]
            }

            async def _prompt_stream():
                yield {"type": "user", "message": {"role": "user", "content": spec.prompt}}

            prompt_source = _prompt_stream()
        else:
            prompt_source = spec.prompt

        options = ClaudeAgentOptions(**options_kwargs)

        # --- Single message-processing loop ---
        text_chunks, session_id, subtype = [], None, None
        cost_usd = None
        duration_ms = 0
        captured_plan_file: str | None = None
        captured_plan_text: str | None = None
        plan_posted, question_posted = False, False
        structured_output: dict | None = None
        progress_state = ProgressState()

        def _question_asked() -> bool:
            return bool(spec.state and spec.state.get("asked_question_md"))

        try:
            async for msg in query(prompt=prompt_source, options=options):
                if isinstance(msg, AssistantMessage):
                    if session_id is None and msg.session_id:
                        session_id = msg.session_id
                    for block in msg.content:
                        if isinstance(block, TextBlock):
                            text_chunks.append(block.text)
                        elif isinstance(block, (ToolUseBlock, ServerToolUseBlock)):
                            if spec.progress_callback and not _question_asked() and progress_state.note_tool_use(block):
                                body = progress_state.render()
                                if body:
                                    spec.progress_callback(body)
                            if isinstance(block, ToolUseBlock):
                                if block.name == "mcp__autoswe_comment__post_plan":
                                    if (block.input or {}).get("body", "").strip():
                                        plan_posted = True
                                elif block.name == "mcp__autoswe_comment__post_question":
                                    if (block.input or {}).get("body", "").strip():
                                        question_posted = True
                                elif block.name == "ExitPlanMode":
                                    # ExitPlanMode is disallowed in plan mode, but the
                                    # tool-use block (with the plan markdown) still
                                    # appears in the stream. Capture it so the planner
                                    # can post the plan instead of "Tool: ExitPlanMode".
                                    exit_plan = (block.input or {}).get("plan", "").strip()
                                    if exit_plan:
                                        captured_plan_text = exit_plan
                                plan_path = _extract_plan_file_path(block)
                                if plan_path is not None:
                                    captured_plan_file = plan_path
                elif isinstance(msg, UserMessage):
                    if spec.progress_callback and not _question_asked():
                        for block in msg.content:
                            if isinstance(block, ToolResultBlock):
                                if progress_state.note_tool_result(block):
                                    body = progress_state.render()
                                    if body:
                                        spec.progress_callback(body)
                elif isinstance(msg, ResultMessage):
                    if session_id is None:
                        session_id = msg.session_id
                    subtype = msg.subtype
                    cost_usd = msg.total_cost_usd
                    duration_ms = msg.duration_ms
                    # Structured output (issue #159): the validated payload is
                    # only ever on the final result message. ``getattr`` guards
                    # against an SDK build predating the field (reads None).
                    # On ``error_max_structured_output_retries`` (or any
                    # success-without-structured-output) this is None, so the
                    # handler falls back to the text-pattern path.
                    so = getattr(msg, "structured_output", None)
                    if isinstance(so, dict):
                        structured_output = so
                    elif subtype == "error_max_structured_output_retries":
                        log(f"[CLAUDE] structured-output retries exhausted "
                            f"(session={session_id}); falling back to text-pattern path")
                    log(f"[CLAUDE] session={session_id} subtype={subtype} cost=${cost_usd or 0:.4f} duration={duration_ms/1000:.1f}s")

                # Break early when AskUserQuestion fired — prevents the agent from
                # running more tools after posting a question.
                if spec.state and spec.state.get("asked_question_md"):
                    break
        except (RuntimeError, Exception) as e:
            error_msg = str(e).lower()
            # Async generator crashes and "Claude Code returned an error result:
            # success" (SDK throws Exception on ollama even after a successful run).
            # In both cases we already captured the result via the message stream,
            # so return partial results rather than failing.
            if ("generator" in error_msg and ("async" in error_msg or "aclose" in error_msg)) \
               or "returned an error result" in error_msg:
                log(f"[CLAUDE] {type(e).__name__}: {e} — returning partial results "
                    f"(session_id={session_id}, subtype={subtype})")
            else:
                raise

        # Re-assert the question as the final sticky-comment content. Guards
        # against any progress update that fired in the same message as the
        # AskUserQuestion call (before the flag became visible to the loop).
        if _question_asked() and spec.progress_callback:
            spec.progress_callback(spec.state["asked_question_md"] + BOT_MARKER)

        return RunResult(
            text="\n".join(text_chunks),
            session_id=session_id,
            subtype=subtype,
            ok=(subtype == "success"),
            cost_usd=cost_usd,
            duration_seconds=duration_ms / 1000,
            plan_file_path=captured_plan_file,
            plan_posted=plan_posted,
            question_posted=question_posted,
            plan_text=captured_plan_text,
            structured_output=structured_output,
        )
