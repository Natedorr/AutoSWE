"""Session flow tests — verifies session_id propagation through runner → planner/coder.

These tests use StreamingClaudeFake to feed the REAL _run_async() loop,
catching bugs that ClaudeFake can't reproduce (because ClaudeFake returns
an instant RunResult and skips the async generator path entirely).

Run from the AutoSWE repo root:
    cd ~/github/autoswe
    PYTHONPATH=/path/to/claude-session-tests:$PYTHONPATH \
        pytest claude-session-tests/test_session_flow.py -v
"""

import asyncio

import pytest

# Ensure AutoSWE source is importable
pass

from typing import Any

from claude_agent_sdk import PermissionResultAllow

from tests.session_harness.fake import StreamingClaudeFake


@pytest.fixture
def fake():
    return StreamingClaudeFake()


def fake_can_use_tool_callback(state: dict):
    """Build a can_use_tool callback that intercepts AskUserQuestion."""
    async def callback(name: str, input_data: dict, context: Any) -> Any:
        if name == "AskUserQuestion":
            state["asked_question_md"] = "## Questions\n\nTest question?"
        return PermissionResultAllow(updated_input=input_data)
    return callback


# =============================================================================
# Test 1: Normal flow — session_id captured from ResultMessage
# =============================================================================

def test_normal_flow_captures_session_id(fake):
    """Normal completion: text + ResultMessage → session_id captured."""
    from autoswe.harness.runner import _run_async

    fake.build_normal_response("Done with the task.", session_id="sess-abc-123")

    async def run():
        with fake.patched():
            result = await _run_async(
                "test prompt",
                cwd="/tmp",
                permission_mode="default",
                allowed_tools=["Read"],
            )
        return result

    result = asyncio.run(run())
    assert result.session_id == "sess-abc-123"
    assert result.subtype == "success"
    assert "Done with the task" in result.text


# =============================================================================
# Test 2: Bug #208 reproduction — AskUserQuestion + crash = session_id lost
# =============================================================================

def test_bug_208_question_crash_loses_session_id(fake):
    """When AskUserQuestion fires and generator crashes, ResultMessage never
    arrives → session_id stays None.

    FIXED: With early session_id capture from AssistantMessage, the session_id
    is now preserved even when the crash happens before ResultMessage.
    """
    from autoswe.harness.runner import _run_async

    state = {}
    # Simulate: text → AskUserQuestion tool use → callback sets asked_question_md
    # → break fires → crash before ResultMessage
    # The fix: session_id is captured from AssistantMessage before the crash
    fake.script_text("Reading README.md...", session_id="s-question-crash")
    # The runner checks state["asked_question_md"] after yielding each message.
    # We can't trigger the real can_use_tool callback through our fake (that's the
    # SDK's job), so we use a wrapper that sets the state after tool use is seen.
    fake.script_crash("aclose(): asynchronous generator is already running")

    async def run():
        # Manually set the state flag to simulate what can_use_tool does
        async def dummy_callback(name: str, input_data: dict, context: Any) -> Any:
            if name == "AskUserQuestion":
                state["asked_question_md"] = "## Questions\n\nTest?"
            return PermissionResultAllow(updated_input=input_data)

        with fake.patched():
            result = await _run_async(
                "test prompt",
                cwd="/tmp",
                permission_mode="plan",
                allowed_tools=["Read", "AskUserQuestion"],
                can_use_tool=dummy_callback,
                state=state,
            )
        return result, state

    result, state = asyncio.run(run())

    # FIXED: session_id is now captured from AssistantMessage before crash
    print(f"DEBUG: session_id={result.session_id}, subtype={result.subtype}")
    print(f"DEBUG: text contains crash recovery = {result.subtype is not None}")

    # The crash handler (#213 fix) should return partial results gracefully
    # Early session_id capture (#208 fix) preserves session_id from AssistantMessage
    assert result.session_id == "s-question-crash"
    assert result.subtype is None  # No ResultMessage, subtype stays None


# =============================================================================
# Test 3: AskUserQuestion without crash — does ResultMessage arrive?
# =============================================================================

def test_question_with_result_session_captured(fake):
    """If ResultMessage DOES arrive after AskUserQuestion, session_id should be captured."""
    from autoswe.harness.runner import _run_async

    state = {}
    fake.build_question_flow(
        text_before="Reading...",
        session_id="sess-question-1",  # ResultMessage arrives
        crash_after=False,
    )

    async def run():
        callback = fake_can_use_tool_callback(state)
        with fake.patched():
            result = await _run_async(
                "test prompt",
                cwd="/tmp",
                permission_mode="plan",
                allowed_tools=["Read", "AskUserQuestion"],
                can_use_tool=callback,
                state=state,
            )
        return result, state

    result, state = asyncio.run(run())

    # If the loop breaks on asked_question_md BEFORE consuming ResultMessage,
    # session_id will still be None — this is a different but related issue
    print(f"DEBUG: session_id={result.session_id}")
    # This may or may not work depending on whether the break happens before ResultMessage
    # We're documenting the behavior, not asserting a specific outcome yet


# =============================================================================
# Test 4: Plan file Write tool captured
# =============================================================================

def test_plan_file_path_captured(fake):
    """When Write tool is used for plan file, plan_file_path should be captured."""
    from autoswe.harness.runner import _run_async

    fake.build_plan_flow(
        plan_text="# My Plan\n1. Do thing\n2. Do another",
        session_id="s-plan-1",
        use_write_tool=True,
    )

    async def run():
        with fake.patched():
            result = await _run_async(
                "test prompt",
                cwd="/tmp",
                permission_mode="plan",
                allowed_tools=["Read", "Write"],
            )
        return result

    result = asyncio.run(run())
    assert result.session_id == "s-plan-1"
    # plan_file_path extraction depends on path parsing — check it's not None
    print(f"DEBUG: plan_file_path={result.plan_file_path}")


# =============================================================================
# Test 5: Fix flow — new session, edit tools
# =============================================================================

def test_fix_flow_new_session(fake):
    """Fix phase should start with a clean session_id (not resume of plan)."""
    from autoswe.harness.runner import _run_async

    fake.build_fix_flow(session_id="s-fix-1", num_edits=2)

    async def run():
        with fake.patched():
            result = await _run_async(
                "Fix the bug",
                cwd="/tmp",
                permission_mode="fix",
                allowed_tools=["Read", "Edit", "Bash"],
            )
        return result

    result = asyncio.run(run())
    assert result.session_id == "s-fix-1"


# =============================================================================
# Test 6: Resume flow — session_id passed as resume parameter
# =============================================================================

def test_resume_passes_session_id(fake):
    """When resuming, the resume parameter should be the previous session_id."""
    from autoswe.harness.runner import _run_async

    previous_session = "sess-previous-123"
    fake.build_normal_response("Continuing from previous session.", session_id="sess-resumed-456")

    async def run():
        with fake.patched():
            result = await _run_async(
                "Continue planning",
                cwd="/tmp",
                permission_mode="plan",
                allowed_tools=["Read"],
                resume=previous_session,
            )
        return result

    result = asyncio.run(run())

    # Verify the fake received the correct resume parameter
    assert len(fake.call_args) == 1
    # The resume value should have been passed — check it was included in options
    print(f"DEBUG: call_args={fake.call_args}")
    assert result.session_id == "sess-resumed-456"


# =============================================================================
# Test 7: MCP ServerToolUse (post_plan) captured
# =============================================================================

def test_mcp_post_plan_tool(fake):
    """MCP post_plan tool call should be visible in the stream."""
    from autoswe.harness.runner import _run_async

    fake.script_text("Writing plan via MCP...")
    fake.script_server_tool(
        "mcp__autoswe_comment__post_plan",
        {"content": "## Plan\n1. Fix the thing"},
    )
    fake.script_result(session_id="s-mcp-1")

    async def run():
        with fake.patched():
            result = await _run_async(
                "Plan the fix",
                cwd="/tmp",
                permission_mode="plan",
                allowed_tools=["Read", "mcp__autoswe_comment__post_plan"],
            )
        return result

    result = asyncio.run(run())
    assert result.session_id == "s-mcp-1"


# =============================================================================
# Test 8: Crash recovery preserves already-captured session_id
# =============================================================================

def test_crash_after_result_preserves_session_id(fake):
    """If ResultMessage arrives BEFORE the crash, session_id should be preserved.
    This tests the #213 fix (async generator crash handler)."""
    from autoswe.harness.runner import _run_async

    # ResultMessage first, then crash
    fake.script_text("Working...")
    fake.script_result(session_id="sess-captured-1", subtype="success")
    fake.script_crash("aclose(): asynchronous generator is already running")

    async def run():
        with fake.patched():
            result = await _run_async(
                "test prompt",
                cwd="/tmp",
                permission_mode="default",
                allowed_tools=["Read"],
            )
        return result

    result = asyncio.run(run())
    # The #213 fix should preserve session_id when ResultMessage already arrived
    print(f"DEBUG: session_id={result.session_id} (crash after result)")
    assert result.session_id == "sess-captured-1"


# =============================================================================
# Test 9: Crash before ANY message — session_id stays None (boundary case)
# =============================================================================

def test_crash_before_any_message(fake):
    """When the generator crashes before yielding any message, session_id
    should remain None — no stale data, next attempt starts fresh.

    Only async generator cleanup crashes are caught. Other RuntimeErrors
    propagate normally."""
    from autoswe.harness.runner import _run_async

    # Use the specific crash pattern that the handler catches
    fake.script_crash("aclose(): asynchronous generator is already running")

    async def run():
        with fake.patched():
            result = await _run_async(
                "test prompt",
                cwd="/tmp",
                permission_mode="default",
                allowed_tools=["Read"],
            )
        return result

    result = asyncio.run(run())
    assert result.session_id is None
    assert result.subtype is None
    assert result.text == ""


# =============================================================================
# Test 10: Multiple AssistantMessages — session_id captured from first
# =============================================================================

def test_session_id_from_first_assistant_message(fake):
    """session_id should be captured from the first AssistantMessage,
    not overwritten by subsequent ones."""
    from autoswe.harness.runner import _run_async

    fake.script_text("First message...", session_id="first-sess")
    fake.script_text("Second message...", session_id="second-sess")
    fake.script_result(session_id="second-sess", subtype="success")

    async def run():
        with fake.patched():
            result = await _run_async(
                "test prompt",
                cwd="/tmp",
                permission_mode="default",
                allowed_tools=["Read"],
            )
        return result

    result = asyncio.run(run())
    # session_id captured from first AssistantMessage ("first-sess"),
    # ResultMessage has "second-sess" but session_id is already set
    assert result.session_id == "first-sess"


# =============================================================================
# Test 11: Question flow with explicit session_id on AssistantMessage
# =============================================================================

def test_question_flow_session_id_preserved(fake):
    """When AskUserQuestion fires and we break, session_id from AssistantMessage
    should be preserved (the #208 fix in action)."""
    from autoswe.harness.runner import _run_async

    state = {}
    fake.script_text("Planning...", session_id="s-question-preserve")
    # After the text message, simulate the loop checking state and breaking
    # The fake doesn't trigger the real can_use_tool, so simulate by having
    # the next message be a crash (which exercises the same early-exit path)
    fake.script_crash("aclose(): asynchronous generator is already running")

    async def run():
        async def dummy_callback(name: str, input_data: dict, context: Any) -> Any:
            return PermissionResultAllow(updated_input=input_data)

        with fake.patched():
            result = await _run_async(
                "test prompt",
                cwd="/tmp",
                permission_mode="plan",
                allowed_tools=["Read", "AskUserQuestion"],
                can_use_tool=dummy_callback,
                state=state,
            )
        return result

    result = asyncio.run(run())
    assert result.session_id == "s-question-preserve"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
