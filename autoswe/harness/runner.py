import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path

from autoswe.core.config import LOGS_DIR
from autoswe.core.logging_utils import init_debug_logger, log

_RETRYABLE_SDK_EXCEPTIONS: tuple = ()
_PLANS_DIR = Path.home() / ".claude" / "plans"

# Read-only-safe progress/orchestration tools (no repo mutation)
PROGRESS_TOOLS = [
    "TodoWrite",
    "TaskCreate", "TaskUpdate", "TaskGet", "TaskList", "TaskOutput", "TaskStop",
]

# Full agent toolset: includes sub-agent spawning. Only safe for fix/coder phases.
AGENT_TASK_TOOLS = [*PROGRESS_TOOLS, "Agent"]


def _get_retryable_exceptions() -> tuple:
    """Lazily build the tuple of SDK exception types to retry on."""
    global _RETRYABLE_SDK_EXCEPTIONS
    if _RETRYABLE_SDK_EXCEPTIONS:
        return _RETRYABLE_SDK_EXCEPTIONS
    try:
        from claude_agent_sdk import ClaudeSDKError, CLIConnectionError, ProcessError
        _RETRYABLE_SDK_EXCEPTIONS = (asyncio.TimeoutError, ProcessError, CLIConnectionError, ClaudeSDKError)
    except ImportError:
        _RETRYABLE_SDK_EXCEPTIONS = (asyncio.TimeoutError,)
    return _RETRYABLE_SDK_EXCEPTIONS

dbg = init_debug_logger(LOGS_DIR)


@dataclass
class RunResult:
    """Result of a Claude Agent SDK query.

    Supports tuple-style unpacking for backward compatibility:
        text, session_id, subtype = result
    """
    text: str
    session_id: str | None
    subtype: str | None
    cost_usd: float | None = None
    duration_seconds: float = 0.0
    plan_file_path: str | None = None
    plan_posted: bool = False
    question_posted: bool = False

    def __iter__(self):
        """Allow tuple-style unpacking: text, session_id, subtype = result."""
        yield self.text
        yield self.session_id
        yield self.subtype


@dataclass
class HandlerResult:
    """Result of a dispatch handler (plan, fix, sync, abort, etc.).

    done_content: "DONE_SUMMARY\t...", "FAILED: ...", "PLAN_READY", etc.
    cost_usd: cost reported by the Claude API (None for local overrides).
    duration_seconds: wall-clock time the agent spent running.
    session_id: the Claude session ID for this handler run. Set by the
        reviewer (throwaway session) so completion comments show the correct
        session. Plan/fix handlers leave this None — they update the task's
        session_id in-place and _to_dispatch falls back to task.get("session_id").
    plan_file_path: absolute path to the ~/.claude/plans/<...>.md file the
        planner wrote on PLAN_READY. Persisted to queue so the next /fix
        dispatch can start a fresh session seeded with it instead of
        resuming the plan session.
    review_file_path: absolute path to the ~/.claude/reviews/<slug>.md file
        the reviewer wrote on REVIEW_READY. Persisted to queue so the next
        /fix or /plan dispatch injects it as prompt context, then clears it.
    """
    done_content: str
    cost_usd: float | None = None
    duration_seconds: float = 0.0
    session_id: str | None = None
    plan_file_path: str | None = None
    review_file_path: str | None = None


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


# ---------- Progress comment state machine ----------


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


# ---------- Progress comment state machine end ----------


async def _run_async(
    prompt: str,
    *,
    cwd: str,
    resume: str = None,
    permission_mode: str = "default",
    allowed_tools: list = None,
    disallowed_tools: list = None,
    model: str = None,
    max_turns: int = 200,
    cli_path: str = None,
    env_overrides: dict = None,
    mcp_servers: dict = None,
    progress_callback=None,
    can_use_tool=None,
    state: dict = None,
):
    """Run Claude Agent SDK. Returns a RunResult dataclass.

    Args:
        mcp_servers: Dict of MCP server configs passed to ClaudeAgentOptions.
        progress_callback: Optional callable(str) invoked with tool-use progress
            messages (e.g. "Running: python test.py", "Reading: src/foo.py").
        can_use_tool: Optional async callback for AskUserQuestion interception.
            When provided, uses streaming-input mode and dummy PreToolUse hook.
        state: Mutable dict shared with handler for can_use_tool communication.
    """
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

    log(f"[CLAUDE] starting cwd={cwd} resume={'NEW' if not resume else resume[:8]} model={model} allowed_tools={len(allowed_tools or [])}")
    if env_overrides:
        os.environ.update({k: v for k, v in env_overrides.items() if v})

    options_kwargs = {
        "cwd": cwd,
        "resume": resume,
        "permission_mode": permission_mode,
        "allowed_tools": allowed_tools or ["Read", "Glob", "Grep"],
        "disallowed_tools": disallowed_tools or [],
        "max_turns": max_turns,
        "model": model or None,
        "cli_path": cli_path or None,
        "mcp_servers": mcp_servers or {},
    }

    if can_use_tool is not None:
        from claude_agent_sdk import HookMatcher

        async def dummy_hook(input_data, tool_use_id, ctx):
            return {"continue_": True}

        options_kwargs["can_use_tool"] = can_use_tool
        options_kwargs["hooks"] = {
            "PreToolUse": [HookMatcher(matcher=None, hooks=[dummy_hook])]
        }

        async def _prompt_stream():
            yield {"type": "user", "message": {"role": "user", "content": prompt}}

        options = ClaudeAgentOptions(**options_kwargs)

        text_chunks, session_id, subtype = [], None, None
        cost_usd = None
        duration_ms = 0
        captured_plan_file: str | None = None
        plan_posted, question_posted = False, False
        progress_state = ProgressState()

        try:
            async for msg in query(prompt=_prompt_stream(), options=options):
                if isinstance(msg, AssistantMessage):
                    # Capture session_id early from the first AssistantMessage.
                    # This way we still have it even when AskUserQuestion fires
                    # and we break before ResultMessage arrives (fixes #208).
                    if session_id is None and msg.session_id:
                        session_id = msg.session_id
                    for block in msg.content:
                        if isinstance(block, TextBlock):
                            text_chunks.append(block.text)
                        elif isinstance(block, (ToolUseBlock, ServerToolUseBlock)):
                            if progress_callback and progress_state.note_tool_use(block):
                                body = progress_state.render()
                                if body:
                                    progress_callback(body)
                            if isinstance(block, ToolUseBlock):
                                if block.name == "mcp__autoswe_comment__post_plan":
                                    plan_posted = True
                                elif block.name == "mcp__autoswe_comment__post_question":
                                    question_posted = True
                                plan_path = _extract_plan_file_path(block)
                                if plan_path is not None:
                                    captured_plan_file = plan_path
                elif isinstance(msg, UserMessage):
                    if progress_callback:
                        for block in msg.content:
                            if isinstance(block, ToolResultBlock):
                                if progress_state.note_tool_result(block):
                                    body = progress_state.render()
                                    if body:
                                        progress_callback(body)
                elif isinstance(msg, ResultMessage):
                    if session_id is None:
                        session_id = msg.session_id
                    subtype = msg.subtype
                    cost_usd = msg.total_cost_usd
                    duration_ms = msg.duration_ms
                    log(f"[CLAUDE] session={session_id} subtype={subtype} cost=${cost_usd or 0:.4f} duration={duration_ms/1000:.1f}s")

                # Break early when AskUserQuestion fired — prevents the agent from
                # running more tools (Bash, git fetch, etc.) after posting a question.
                # The handler checks state["asked_question_md"] and returns WAITING.
                if state and state.get("asked_question_md"):
                    break
        except RuntimeError as e:
            error_msg = str(e).lower()
            if "generator" in error_msg and ("async" in error_msg or "aclose" in error_msg):
                log(f"[CLAUDE] Async generator crash: {e} — returning partial results "
                    f"(session_id={session_id}, subtype={subtype})")
            else:
                raise
    else:
        options = ClaudeAgentOptions(**options_kwargs)

        text_chunks, session_id, subtype = [], None, None
        cost_usd = None
        duration_ms = 0
        captured_plan_file: str | None = None
        plan_posted, question_posted = False, False
        progress_state = ProgressState()

        try:
            async for msg in query(prompt=prompt, options=options):
                if isinstance(msg, AssistantMessage):
                    # Capture session_id early from the first AssistantMessage.
                    # This way we still have it even when AskUserQuestion fires
                    # and we break before ResultMessage arrives (fixes #208).
                    if session_id is None and msg.session_id:
                        session_id = msg.session_id
                    for block in msg.content:
                        if isinstance(block, TextBlock):
                            text_chunks.append(block.text)
                        elif isinstance(block, (ToolUseBlock, ServerToolUseBlock)):
                            if progress_callback and progress_state.note_tool_use(block):
                                body = progress_state.render()
                                if body:
                                    progress_callback(body)
                            if isinstance(block, ToolUseBlock):
                                if block.name == "mcp__autoswe_comment__post_plan":
                                    plan_posted = True
                                elif block.name == "mcp__autoswe_comment__post_question":
                                    question_posted = True
                                plan_path = _extract_plan_file_path(block)
                                if plan_path is not None:
                                    captured_plan_file = plan_path
                elif isinstance(msg, UserMessage):
                    if progress_callback:
                        for block in msg.content:
                            if isinstance(block, ToolResultBlock):
                                if progress_state.note_tool_result(block):
                                    body = progress_state.render()
                                    if body:
                                        progress_callback(body)
                elif isinstance(msg, ResultMessage):
                    if session_id is None:
                        session_id = msg.session_id
                    subtype = msg.subtype
                    cost_usd = msg.total_cost_usd
                    duration_ms = msg.duration_ms
                    log(f"[CLAUDE] session={session_id} subtype={subtype} cost=${cost_usd or 0:.4f} duration={duration_ms/1000:.1f}s")
        except RuntimeError as e:
            error_msg = str(e).lower()
            if "generator" in error_msg and ("async" in error_msg or "aclose" in error_msg):
                log(f"[CLAUDE] Async generator crash: {e} — returning partial results "
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


def run(
    prompt: str,
    *,
    cwd: str,
    cfg: dict,
    repo_cfg: dict = None,
    resume: str = None,
    permission_mode: str = "default",
    allowed_tools: list = None,
    disallowed_tools: list = None,
    max_turns: int = 200,
    model: str = None,
    mcp_servers: dict = None,
    progress_callback=None,
    can_use_tool=None,
    state: dict = None,
):
    """Synchronous wrapper. Returns a RunResult dataclass.

    The dataclass supports backward-compatible tuple unpacking:
        text, session_id, subtype = runner.run(...)
    """
    rc = repo_cfg or {}
    timeout = int(rc.get("agent_timeout", cfg.get("AGENT_TIMEOUT", 7200)))
    max_retries = int(rc.get("agent_retry_on_failure", cfg.get("AGENT_RETRY_ON_FAILURE", 0)))
    model = model or rc.get("model") or None
    cli_path = cfg.get("CLAUDE_CLI_PATH") or None

    env_overrides = {}
    base_url = rc.get("anthropic_base_url") or cfg.get("ANTHROPIC_BASE_URL")
    auth_token = rc.get("anthropic_auth_token") or cfg.get("ANTHROPIC_AUTH_TOKEN")
    api_key = cfg.get("ANTHROPIC_API_KEY")
    if base_url:
        env_overrides["ANTHROPIC_BASE_URL"] = base_url
    if auth_token:
        env_overrides["ANTHROPIC_AUTH_TOKEN"] = auth_token
    if api_key:
        env_overrides["ANTHROPIC_API_KEY"] = api_key

    async def _with_timeout():
        return await asyncio.wait_for(
            _run_async(
                prompt,
                cwd=cwd,
                resume=resume,
                permission_mode=permission_mode,
                allowed_tools=allowed_tools,
                disallowed_tools=disallowed_tools,
                model=model,
                max_turns=max_turns,
                cli_path=cli_path,
                env_overrides=env_overrides,
                mcp_servers=mcp_servers,
                progress_callback=progress_callback,
                can_use_tool=can_use_tool,
                state=state,
            ),
            timeout=timeout,
        )

    retryable = _get_retryable_exceptions()
    for attempt in range(max_retries + 1):
        try:
            return asyncio.run(_with_timeout())
        except retryable as e:
            if attempt < max_retries:
                log(f"[CLAUDE] Attempt {attempt + 1} failed ({type(e).__name__}: {e}), retrying ({attempt + 2}/{max_retries + 1})")
            else:
                if isinstance(e, asyncio.TimeoutError):
                    log(f"[CLAUDE] Timeout after {timeout}s (attempt {attempt + 1}/{max_retries + 1})")
                else:
                    log(f"[CLAUDE] Agent failed after {attempt + 1} attempt(s): {type(e).__name__}: {e}")
                raise
