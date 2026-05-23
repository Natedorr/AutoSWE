"""Streaming Claude SDK fake — replaces claude_agent_sdk.query() at the generator level.

Unlike ClaudeFake (which replaces runner.run() with instant scripted responses),
this fake feeds the REAL _run_async() loop through the async generator interface.
This means the actual break-on-AskUserQuestion logic, ResultMessage capture, and
async generator crash handling all run against real code paths.

Usage:
    fake = StreamingClaudeFake()
    fake.script_text("Reading the codebase...")
    fake.script_tool("AskUserQuestion", {"questions": [...]})
    fake.script_result(session_id="sess-abc-123", subtype="success")

    async def my_callback(name, inp, ctx):
        return PermissionResultAllow(updated_input=inp)

    async def main():
        with fake.patch():
            result = await _run_async("prompt", cwd="/tmp",
                                       can_use_tool=my_callback, state={})
        print(result.session_id)  # "sess-abc-123"

    asyncio.run(main())

Can simulate:
- Normal completion (text + ResultMessage with session_id)
- AskUserQuestion interception (tool use → can_use_tool callback)
- Async generator crashes (RuntimeError with "aclose")
- Premature exits (no ResultMessage → session_id stays None)
- Plan file Write tool calls
- ServerToolUse (MCP tools)
"""

from __future__ import annotations

import sys
from contextlib import contextmanager
from typing import Any, AsyncIterator

from claude_agent_sdk import (
    AssistantMessage,
    ResultMessage,
    ServerToolUseBlock,
    TextBlock,
    ToolUseBlock,
)


class ScriptedMessage:
    """A single message to yield from the fake query generator."""
    pass


class ScriptedText(ScriptedMessage):
    """Yields AssistantMessage with TextBlock content."""
    def __init__(self, text: str, model: str = "claude-test", session_id: str | None = None):
        self.text = text
        self.model = model
        self.session_id = session_id

    def to_message(self) -> AssistantMessage:
        return AssistantMessage(
            content=[TextBlock(text=self.text)],
            model=self.model,
            session_id=self.session_id,
        )


class ScriptedToolUse(ScriptedMessage):
    """Yields AssistantMessage with ToolUseBlock."""
    def __init__(self, name: str, input_data: dict, tool_id: str | None = None, model: str = "claude-test", session_id: str | None = None):
        self.name = name
        self.input_data = input_data
        self.tool_id = tool_id or f"toolu_{id(self)}"
        self.model = model
        self.session_id = session_id

    def to_message(self) -> AssistantMessage:
        block = ToolUseBlock(id=self.tool_id, name=self.name, input=self.input_data)
        return AssistantMessage(content=[block], model=self.model, session_id=self.session_id)


class ScriptedServerToolUse(ScriptedMessage):
    """Yields AssistantMessage with ServerToolUseBlock (MCP tools)."""
    def __init__(self, name: str, input_data: dict, tool_id: str | None = None, model: str = "claude-test", session_id: str | None = None):
        self.name = name
        self.input_data = input_data
        self.tool_id = tool_id or f"stu_{id(self)}"
        self.model = model
        self.session_id = session_id

    def to_message(self) -> AssistantMessage:
        # ServerToolUseBlock has different constructor — adapt as needed
        block = ServerToolUseBlock(id=self.tool_id, name=self.name, input=self.input_data)
        return AssistantMessage(content=[block], model=self.model, session_id=self.session_id)


class ScriptedResult(ScriptedMessage):
    """Yields ResultMessage (terminal message with session_id)."""
    def __init__(
        self,
        session_id: str,
        subtype: str = "success",
        cost_usd: float = 0.0,
        duration_ms: int = 1000,
        num_turns: int = 1,
    ):
        self.session_id = session_id
        self.subtype = subtype
        self.cost_usd = cost_usd
        self.duration_ms = duration_ms
        self.num_turns = num_turns

    def to_message(self) -> ResultMessage:
        return ResultMessage(
            subtype=self.subtype,
            duration_ms=self.duration_ms,
            duration_api_ms=self.duration_ms,
            is_error=False,
            num_turns=self.num_turns,
            session_id=self.session_id,
            stop_reason="end_turn",
            total_cost_usd=self.cost_usd,
        )


class ScriptedCrash(ScriptedMessage):
    """Raises RuntimeError after yielding — simulates async generator crash."""
    def __init__(self, error: str = "aclose(): asynchronous generator is already running"):
        self.error = error

    def to_message(self) -> None:
        raise RuntimeError(self.error)


class StreamingClaudeFake:
    """Scripted async generator that replaces claude_agent_sdk.query()."""

    def __init__(self):
        self.script: list[ScriptedMessage] = []
        self.call_count = 0
        self.call_args: list[dict[str, Any]] = []

    # ---- Scripting helpers ----

    def script_text(self, text: str, model: str = "claude-test", session_id: str | None = None) -> "StreamingClaudeFake":
        self.script.append(ScriptedText(text, model, session_id))
        return self

    def script_tool(
        self,
        name: str,
        input_data: dict,
        tool_id: str | None = None,
        model: str = "claude-test",
        session_id: str | None = None,
    ) -> "StreamingClaudeFake":
        self.script.append(ScriptedToolUse(name, input_data, tool_id, model, session_id))
        return self

    def script_server_tool(
        self,
        name: str,
        input_data: dict,
        tool_id: str | None = None,
        model: str = "claude-test",
        session_id: str | None = None,
    ) -> "StreamingClaudeFake":
        self.script.append(ScriptedServerToolUse(name, input_data, tool_id, model, session_id))
        return self

    def script_result(
        self,
        session_id: str = "test-session-1",
        subtype: str = "success",
        cost_usd: float = 0.01,
        duration_ms: int = 1000,
        num_turns: int = 1,
    ) -> "StreamingClaudeFake":
        self.script.append(ScriptedResult(session_id, subtype, cost_usd, duration_ms, num_turns))
        return self

    def script_crash(
        self,
        error: str = "aclose(): asynchronous generator is already running",
    ) -> "StreamingClaudeFake":
        self.script.append(ScriptedCrash(error))
        return self

    # ---- Convenience builders ----

    def build_normal_response(
        self,
        text: str,
        session_id: str = "s-normal",
        subtype: str = "success",
    ) -> "StreamingClaudeFake":
        """Build a normal completion: text → result."""
        self.script_text(text)
        self.script_result(session_id, subtype)
        return self

    def build_question_flow(
        self,
        text_before: str = "Reading the codebase...",
        question_tool: str = "AskUserQuestion",
        question_input: dict | None = None,
        session_id: str | None = None,
        crash_after: bool = False,
    ) -> "StreamingClaudeFake":
        """Build a question-asking flow.

        If crash_after=True, simulates the #208 bug: generator crashes after
        AskUserQuestion fires and ResultMessage never arrives.
        If session_id is set, ResultMessage arrives with session_id.
        """
        self.script_text(text_before, session_id=session_id)
        self.script_tool(
            question_tool,
            question_input or {"questions": [{"question": "What should I do?"}]},
            session_id=session_id,
        )
        if crash_after:
            self.script_crash()
        elif session_id:
            self.script_result(session_id, "success")
        # If neither crash nor session_id: no ResultMessage (another way to lose session)
        return self

    def build_plan_flow(
        self,
        plan_text: str,
        session_id: str = "s-plan",
        use_write_tool: bool = True,
    ) -> "StreamingClaudeFake":
        """Build a plan completion: read → write plan file → result."""
        self.script_text("Reading project files...")
        if use_write_tool:
            self.script_tool("Write", {"path": "~/.claude/plans/test-plan.md", "content": plan_text})
        self.script_text(f"Plan written: {plan_text[:50]}...")
        self.script_result(session_id, "success", num_turns=3)
        return self

    def build_fix_flow(
        self,
        edit_text: str = "Editing source files...",
        session_id: str = "s-fix",
        num_edits: int = 1,
    ) -> "StreamingClaudeFake":
        """Build a fix completion: edit → commit → result."""
        for i in range(num_edits):
            self.script_tool("Edit", {"path": f"src/file{i}.py", "content": edit_text})
        self.script_result(session_id, "success", num_turns=num_edits + 1)
        return self

    # ---- Patching ----

    def _make_fake_query(self):
        """Create the fake query async generator."""
        fake = self

        async def fake_query(prompt: Any, options: Any = None) -> AsyncIterator[Any]:
            fake.call_count += 1
            # prompt can be a string or an async_generator — handle both
            if hasattr(prompt, '__name__') or str(type(prompt)).find('async_generator') >= 0:
                prompt_str = f"async_gen<{type(prompt).__name__}>"
            else:
                prompt_str = str(prompt or "")[:100]
            fake.call_args.append({
                "prompt_prefix": prompt_str,
                "options": str(options) if options else None,
            })
            for msg in fake.script:
                result = msg.to_message()
                if result is not None:
                    yield result

        return fake_query

    def patch(self):
        """Patch claude_agent_sdk.query with our fake generator.

        Returns (module, original_query) for manual unpatching.
        For context manager usage, use ``with fake:`` instead of ``with fake.patch():``.
        """
        sdk = sys.modules.get("claude_agent_sdk")
        if sdk is None:
            raise RuntimeError("claude_agent_sdk not loaded — import runner first")

        original = sdk.query
        sdk.query = self._make_fake_query()
        return sdk, original

    @contextmanager
    def patched(self):
        """Context manager: ``with fake.patched():``

        Patches claude_agent_sdk.query for the block and restores on exit.
        """
        sdk, original = self.patch()
        try:
            yield self
        finally:
            self.unpatch(sdk, original)

    def __enter__(self):
        sdk, original = self.patch()
        self._sdk = sdk
        self._original = original
        return self

    def __exit__(self, *exc):
        self.unpatch(self._sdk, self._original)

    def unpatch(self, module, original) -> None:
        module.query = original

    def reset(self) -> None:
        """Clear script and call history."""
        self.script.clear()
        self.call_count = 0
        self.call_args.clear()
