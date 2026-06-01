"""Claude Code backend — implements CodingBackend using the Claude Agent SDK.

All Claude-specific execution logic (ClaudeAgentOptions construction, SDK
message streaming, ProgressState, plan-file capture) lives here.  runner.py
is now a thin dispatcher that delegates to this backend.

Phase 3: translates RunSpec.mode into Claude-specific permission_mode,
allowed_tools, and disallowed_tools.  Per-mode tool lists live here as the
canonical mapping, so handlers no longer carry Claude-specific tool names.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Awaitable

from autoswe.core.config import LOGS_DIR
from autoswe.core.logging_utils import init_debug_logger, log
from autoswe.harness.backends.base import PROGRESS_TOOLS, RunResult, RunSpec

_dbg = init_debug_logger(LOGS_DIR)

_RETRYABLE_SDK_EXCEPTIONS: tuple = ()
_PLANS_DIR = Path.home() / ".claude" / "plans"

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


def _get_retryable_exceptions() -> tuple:
    """Lazily build the tuple of SDK exception types to retry on."""
    import asyncio

    global _RETRYABLE_SDK_EXCEPTIONS
    if _RETRYABLE_SDK_EXCEPTIONS:
        return _RETRYABLE_SDK_EXCEPTIONS
    try:
        from claude_agent_sdk import ClaudeSDKError, CLIConnectionError, ProcessError
        _RETRYABLE_SDK_EXCEPTIONS = (asyncio.TimeoutError, ProcessError, CLIConnectionError, ClaudeSDKError)
    except ImportError:
        _RETRYABLE_SDK_EXCEPTIONS = (asyncio.TimeoutError,)
    return _RETRYABLE_SDK_EXCEPTIONS


# ---------- Tool-use helpers ----------


def _format_tool_progress(block) -> str | None:
    """Format a tool-use block into a short progress string."""
    from claude_agent_sdk import ServerToolUseBlock, ToolUseBlock

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


def _extract_plan_file_path(block) -> str | None:
    """If *block* is a Write tool call targeting the plans directory, return its path.

    Returns None for non-Write blocks or Write calls outside the plans
    directory.  We accept both ``file_path`` and ``path`` input keys
    (the SDK / Claude CLI use either depending on version).
    """
    from claude_agent_sdk import ToolUseBlock

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
                    if key in parsed and parsed[key]:
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
        "progress_stream",
    }

    @classmethod
    def capabilities(cls) -> set[str]:
        return cls.CAPABILITIES.copy()

    def run(self, spec: RunSpec) -> Awaitable[RunResult]:
        """Execute the spec via Claude Agent SDK.

        Returns an awaitable that resolves to a RunResult.
        """
        return self._run_async(spec)

    async def _run_async(self, spec: RunSpec) -> RunResult:
        """Run Claude Agent SDK. Returns a RunResult dataclass."""
        from claude_agent_sdk import (
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

        log(f"[CLAUDE] starting cwd={spec.cwd} resume={'NEW' if not spec.resume else spec.resume[:8]} model={spec.model} mode={spec.mode}")

        # --- Apply Anthropic env vars from harness profile ---
        harness_cfg = (spec.state or {}).get("_harness_cfg") or {}
        _claude_env = {}
        if harness_cfg.get("anthropic_base_url"):
            _claude_env["ANTHROPIC_BASE_URL"] = harness_cfg["anthropic_base_url"]
        if harness_cfg.get("anthropic_auth_token"):
            _claude_env["ANTHROPIC_AUTH_TOKEN"] = harness_cfg["anthropic_auth_token"]
        if harness_cfg.get("anthropic_api_key"):
            _claude_env["ANTHROPIC_API_KEY"] = harness_cfg["anthropic_api_key"]
        # Merge with spec.env_overrides (explicit overrides take precedence)
        _env_to_set = {}
        if _claude_env or spec.env_overrides:
            merged_env = dict(_claude_env)
            merged_env.update(spec.env_overrides or {})
            _env_to_set = {k: v for k, v in merged_env.items() if v}

        # Snapshot original values so we can restore them (credential cleanup)
        _original_env = {k: os.environ.get(k) for k in _env_to_set}

        try:
            if _env_to_set:
                os.environ.update(_env_to_set)

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
            }

            # --- Setup phase: can_use_tool requires streaming prompt + hooks ---
            if spec.can_use_tool is not None:
                from claude_agent_sdk import HookMatcher

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
            plan_posted, question_posted = False, False
            progress_state = ProgressState()

            try:
                async for msg in query(prompt=prompt_source, options=options):
                    if isinstance(msg, AssistantMessage):
                        if session_id is None and msg.session_id:
                            session_id = msg.session_id
                        for block in msg.content:
                            if isinstance(block, TextBlock):
                                text_chunks.append(block.text)
                            elif isinstance(block, (ToolUseBlock, ServerToolUseBlock)):
                                if spec.progress_callback and progress_state.note_tool_use(block):
                                    body = progress_state.render()
                                    if body:
                                        spec.progress_callback(body)
                                if isinstance(block, ToolUseBlock):
                                    if block.name == "mcp__autoswe_comment__post_plan":
                                        plan_posted = True
                                    elif block.name == "mcp__autoswe_comment__post_question":
                                        question_posted = True
                                    plan_path = _extract_plan_file_path(block)
                                    if plan_path is not None:
                                        captured_plan_file = plan_path
                    elif isinstance(msg, UserMessage):
                        if spec.progress_callback:
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

            return RunResult(
                text="\n".join(text_chunks),
                session_id=session_id,
                subtype=subtype,
                cost_usd=cost_usd,
                duration_seconds=duration_ms / 1000,
                plan_file_path=captured_plan_file,
                plan_posted=plan_posted,
                question_posted=question_posted,
            )
        finally:
            # Restore original environment — prevents credential leakage between tasks
            for k, v in _original_env.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
