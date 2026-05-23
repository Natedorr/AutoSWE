"""Extended manual scenarios — comprehensive feature coverage for the action harness.

Tests every major code path in the Claude chassis:
1. Plan file detection (Write to plans dir)
2. Progress callback (tool progress strings)
3. Disallowed tools
4. Multi-turn conversation (multiple AssistantMessages)
5. Error result subtype
6. Empty text result
7. Plan file path extraction edge cases
8. Cost and duration tracking
9. Model override
10. Max turns
11. Resume with guidance
12. Crash mid-text (partial text preserved)

Run:
    PYTHONPATH="$PYTHONPATH:$(pwd)" python3 tests/session_harness/runner_extended.py
"""

import asyncio
import os

from claude_agent_sdk import PermissionResultAllow

from tests.session_harness.fake import StreamingClaudeFake

# ==== Result colors ====

class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def result(name, passed, details, diagnostics):
    from dataclasses import dataclass
    @dataclass
    class R:
        name: str
        passed: bool
        details: str
        diagnostics: list
    return R(name, passed, details, diagnostics)


def print_result(r, verbose=False):
    status = f"{Colors.GREEN}PASS{Colors.RESET}" if r.passed else f"{Colors.RED}FAIL{Colors.RESET}"
    print(f"\n{Colors.BOLD}{r.name}{Colors.RESET}")
    print(f"  {status} — {r.details}")
    if verbose or not r.passed:
        for line in r.diagnostics:
            print(f"  {Colors.CYAN}{line}{Colors.RESET}")


# --========================================================================
# 1. Plan file detection — Write to plans dir → plan_file_path captured
# --========================================================================

async def scenario_plan_file_detection():
    """When the model uses Write to ~/.claude/plans/, plan_file_path is captured."""
    from autoswe.harness.runner import _run_async

    plans_dir = os.path.expanduser("~/.claude/plans")
    plan_path = f"{plans_dir}/test-plan.md"

    fake = StreamingClaudeFake()
    fake.script_text("Writing the plan...")
    fake.script_tool("Write", {"path": plan_path, "content": "# Plan\n1. Fix it"})
    fake.script_result(session_id="s-plan-file-001", num_turns=2)

    async def run():
        with fake.patched():
            return await _run_async(
                "Create a plan.",
                cwd="/tmp",
                permission_mode="plan",
                allowed_tools=["Read", "Write"],
            )

    r = await run()
    diag = [f"session_id: {r.session_id}", f"plan_file_path: {r.plan_file_path}"]
    passed = r.plan_file_path is not None and "test-plan.md" in r.plan_file_path

    return result("plan_file_detection", passed, "Write to plans dir captured", diag)


# --========================================================================
# 2. Progress callback — tool progress strings emitted
# --========================================================================

async def scenario_progress_callback():
    """Progress callback receives tool progress strings for each tool use."""
    from autoswe.harness.runner import _run_async

    fake = StreamingClaudeFake()
    fake.script_text("Starting analysis...")
    fake.script_tool("Read", {"file_path": "src/main.py"})
    fake.script_tool("Bash", {"command": "python3 -c 'print(1+1)'"})
    fake.script_tool("Edit", {"path": "src/main.py", "old_content": "x=1", "new_content": "x=2"})
    fake.script_result(session_id="s-progress-001", num_turns=3)

    progress_log = []

    async def run():
        with fake.patched():
            return await _run_async(
                "Fix the code.",
                cwd="/tmp",
                permission_mode="fix",
                allowed_tools=["Read", "Edit", "Bash"],
                progress_callback=progress_log.append,
            )

    await run()
    diag = [f"progress calls: {len(progress_log)}", *progress_log]
    # Should have at least 3 progress entries (Read, Bash, Edit)
    passed = len(progress_log) >= 3 and any("Read" in p for p in progress_log)

    return result("progress_callback", passed, "Tool progress strings emitted", diag)


# --========================================================================
# 3. Disallowed tools — explicit tool blocking
# --========================================================================

async def scenario_disallowed_tools():
    """disallowed_tools list is passed to ClaudeAgentOptions."""
    from autoswe.harness.runner import _run_async

    fake = StreamingClaudeFake()
    fake.script_text("Plan written.")
    fake.script_result(session_id="s-disallow-001")

    async def run():
        with fake.patched():
            return await _run_async(
                "Create a plan.",
                cwd="/tmp",
                permission_mode="plan",
                allowed_tools=["Read", "Write"],
                disallowed_tools=["Bash", "Edit"],
            )

    r = await run()
    # Check that the options were created with disallowed_tools
    # We can verify indirectly — the call_args capture the options string
    args_str = str(fake.call_args)
    passed = r.session_id == "s-disallow-001" and "Bash" in args_str

    diag = [f"session_id: {r.session_id}", f"disallowed in options: {'Bash' in args_str}"]
    return result("disallowed_tools", passed, "disallowed_tools passed to SDK", diag)


# --========================================================================
# 4. Multi-turn conversation — multiple AssistantMessages, text accumulates
# --========================================================================

async def scenario_multi_turn():
    """Multiple AssistantMessage text blocks accumulate correctly."""
    from autoswe.harness.runner import _run_async

    fake = StreamingClaudeFake()
    fake.script_text("Step 1: Analyzing the issue.")
    fake.script_tool("Read", {"file_path": "src/main.py"})
    fake.script_text("Step 2: Found the bug on line 42.")
    fake.script_tool("Read", {"file_path": "src/utils.py"})
    fake.script_text("Step 3: Here's the fix.")
    fake.script_result(session_id="s-multi-001", num_turns=5)

    async def run():
        with fake.patched():
            return await _run_async(
                "Find and fix the bug.",
                cwd="/tmp",
                permission_mode="fix",
                allowed_tools=["Read", "Edit"],
            )

    r = await run()
    diag = [f"text: {r.text[:200]}", f"session_id: {r.session_id}"]
    # All three text blocks should be in the result
    passed = "Step 1:" in r.text and "Step 2:" in r.text and "Step 3:" in r.text

    return result("multi_turn", passed, "Multiple text blocks accumulated", diag)


# --========================================================================
# 5. Error result subtype — failed sessions return correct subtype
# --========================================================================

async def scenario_error_subtype():
    """Failed sessions return subtype='error' and preserve session_id."""
    from autoswe.harness.runner import _run_async

    fake = StreamingClaudeFake()
    fake.script_text("Attempting fix...")
    fake.script_result(session_id="s-error-001", subtype="error", num_turns=1)

    async def run():
        with fake.patched():
            return await _run_async(
                "Fix the bug.",
                cwd="/tmp",
                permission_mode="fix",
                allowed_tools=["Read", "Edit"],
            )

    r = await run()
    diag = [f"session_id: {r.session_id}", f"subtype: {r.subtype}"]
    passed = r.session_id == "s-error-001" and r.subtype == "error"

    return result("error_subtype", passed, "Error subtype preserved", diag)


# --========================================================================
# 6. Empty text result — session with no text, just a result
# --========================================================================

async def scenario_empty_text():
    """Sessions with no text content still return valid session_id."""
    from autoswe.harness.runner import _run_async

    fake = StreamingClaudeFake()
    fake.script_result(session_id="s-empty-001", subtype="success")

    async def run():
        with fake.patched():
            return await _run_async(
                "Do nothing.",
                cwd="/tmp",
                permission_mode="plan",
                allowed_tools=["Read"],
            )

    r = await run()
    diag = [f"text: '{r.text}'", f"session_id: {r.session_id}"]
    passed = r.session_id == "s-empty-001" and r.text == ""

    return result("empty_text", passed, "Empty text with valid session_id", diag)


# --========================================================================
# 7. Cost and duration tracking — RunResult has cost/duration from ResultMessage
# --========================================================================

async def scenario_cost_tracking():
    """RunResult captures cost_usd and duration_seconds from ResultMessage."""
    from autoswe.harness.runner import _run_async

    fake = StreamingClaudeFake()
    fake.script_text("Fix applied.")
    fake.script_result(session_id="s-cost-001", cost_usd=2.50, duration_ms=3500)

    async def run():
        with fake.patched():
            return await _run_async(
                "Fix it.",
                cwd="/tmp",
                permission_mode="fix",
                allowed_tools=["Read"],
            )

    r = await run()
    diag = [f"cost_usd: {r.cost_usd}", f"duration_seconds: {r.duration_seconds}"]
    passed = r.cost_usd == 2.50 and abs(r.duration_seconds - 3.5) < 0.01

    return result("cost_tracking", passed, "Cost and duration captured", diag)


# --========================================================================
# 8. Crash mid-text — partial text preserved after crash
# --========================================================================

async def scenario_crash_mid_text():
    """When crash happens mid-stream, all text before crash is preserved."""
    from autoswe.harness.runner import _run_async

    fake = StreamingClaudeFake()
    fake.script_text("First part of the plan.")
    fake.script_text("Second part of the plan.")
    fake.script_crash("aclose(): async generator crash — unexpected disconnect")
    fake.script_text("This should not appear.")

    async def run():
        with fake.patched():
            return await _run_async(
                "Write a plan.",
                cwd="/tmp",
                permission_mode="plan",
                allowed_tools=["Read"],
            )

    r = await run()
    diag = [f"text: {r.text[:200]}", f"session_id: {r.session_id}"]
    passed = "First part" in r.text and "Second part" in r.text and "This should not" not in r.text

    return result("crash_mid_text", passed, "Partial text preserved on crash", diag)


# --========================================================================
# 9. Resume with session ID — previous session passed to SDK
# --========================================================================

async def scenario_resume_session():
    """Resume param correctly passes previous session_id to SDK."""
    from autoswe.harness.runner import _run_async

    fake = StreamingClaudeFake()
    fake.script_text("Continuing from previous session...")
    fake.script_result(session_id="s-resume-new-001")

    prev_session = "s-previous-session-xyz"

    async def run():
        with fake.patched():
            return await _run_async(
                "Continue the fix.",
                cwd="/tmp",
                permission_mode="fix",
                allowed_tools=["Read", "Edit"],
                resume=prev_session,
            )

    r = await run()
    # Verify the resume parameter was passed
    args_str = str(fake.call_args)
    diag = [f"session_id: {r.session_id}", f"resume in options: {'s-previous-session-xyz' in args_str}"]
    passed = "s-previous-session-xyz" in args_str

    return result("resume_session", passed, "Resume ID passed to SDK", diag)


# --========================================================================
# 10. can_use_tool callback wiring — callback is passed to SDK options
# --========================================================================

async def scenario_callback_wiring():
    """Verify that can_use_tool callback is wired into ClaudeAgentOptions.

    Note: The fake yields messages directly, so the SDK's internal tool-use
    loop doesn't actually invoke can_use_tool. This test verifies the
    callback is passed through to the options correctly.
    """
    from autoswe.harness.runner import _run_async

    fake = StreamingClaudeFake()
    fake.script_text("Reading code...")
    fake.script_tool("AskUserQuestion", {
        "questions": [{
            "header": "Approach",
            "question": "Which approach?",
            "options": [{"label": "A", "description": "Simple"}],
            "multiSelect": False,
        }]
    }, session_id="s-ask-001")
    fake.script_result(session_id="s-ask-001")

    callback_invoked = []

    async def callback(name, input_data, context):
        callback_invoked.append(name)
        return PermissionResultAllow(updated_input=input_data)

    async def run():
        with fake.patched():
            return await _run_async(
                "Plan the fix.",
                cwd="/tmp",
                permission_mode="plan",
                allowed_tools=["Read", "AskUserQuestion"],
                can_use_tool=callback,
                state={},
            )

    r = await run()
    args_str = str(fake.call_args)
    diag = [
        f"session_id: {r.session_id}",
        f"can_use_tool in options: {'can_use_tool' in args_str}",
        f"hooks in options: {'hooks' in args_str}",
        f"PreToolUse in options: {'PreToolUse' in args_str}",
    ]
    # The runner wires can_use_tool + PreToolUse dummy hook when can_use_tool is provided
    passed = r.session_id == "s-ask-001" and "can_use_tool" in args_str and "PreToolUse" in args_str

    return result("callback_wiring", passed, "can_use_tool wired to SDK options", diag)


# --========================================================================
# 11. ServerToolUse (MCP) — MCP tool calls visible in stream
# --========================================================================

async def scenario_mcp_tool():
    """MCP ServerToolUse blocks are processed without errors."""
    from autoswe.harness.runner import _run_async

    fake = StreamingClaudeFake()
    fake.script_text("Preparing plan...")
    fake.script_server_tool("mcp__autoswe_comment__post_plan", {"content": "# Plan\n1. Fix bug"})
    fake.script_server_tool("mcp__autoswe_comment__post_question", {"content": "Any concerns?"})
    fake.script_result(session_id="s-mcp-002", num_turns=3)

    progress_log = []

    async def run():
        with fake.patched():
            return await _run_async(
                "Plan with MCP tools.",
                cwd="/tmp",
                permission_mode="plan",
                allowed_tools=["Read", "mcp__autoswe_comment__post_plan", "mcp__autoswe_comment__post_question"],
                progress_callback=progress_log.append,
            )

    r = await run()
    diag = [f"session_id: {r.session_id}", f"progress: {progress_log}"]
    passed = r.session_id == "s-mcp-002"

    return result("mcp_tool", passed, "MCP ServerToolUse processed", diag)


# --========================================================================
# 12. Write tool outside plans dir — NOT captured as plan_file_path
# --========================================================================

async def scenario_write_outside_plans():
    """Write to a non-plans path should NOT set plan_file_path."""
    from autoswe.harness.runner import _run_async

    fake = StreamingClaudeFake()
    fake.script_text("Editing code...")
    fake.script_tool("Write", {"path": "/tmp/fix.patch", "content": "--- old\n+++ new"})
    fake.script_result(session_id="s-noplan-001", num_turns=2)

    async def run():
        with fake.patched():
            return await _run_async(
                "Write a patch.",
                cwd="/tmp",
                permission_mode="fix",
                allowed_tools=["Read", "Write"],
            )

    r = await run()
    diag = [f"plan_file_path: {r.plan_file_path}", f"session_id: {r.session_id}"]
    passed = r.plan_file_path is None and r.session_id == "s-noplan-001"

    return result("write_outside_plans", passed, "Non-plan Write not captured", diag)


# --========================================================================
# 13. Model override — model param passed through
# --========================================================================

async def scenario_model_override():
    """Model parameter is passed to ClaudeAgentOptions."""
    from autoswe.harness.runner import _run_async

    fake = StreamingClaudeFake()
    fake.script_text("Done.")
    fake.script_result(session_id="s-model-001")

    async def run():
        with fake.patched():
            return await _run_async(
                "Quick task.",
                cwd="/tmp",
                permission_mode="plan",
                allowed_tools=["Read"],
                model="claude-sonnet-4-20250514",
            )

    r = await run()
    args_str = str(fake.call_args)
    diag = [f"session_id: {r.session_id}", f"model in options: {'claude-sonnet-4-20250514' in args_str}"]
    passed = "claude-sonnet-4-20250514" in args_str

    return result("model_override", passed, "Model param passed to SDK", diag)


# --========================================================================
# 14. Max turns — max_turns param passed through
# --========================================================================

async def scenario_max_turns():
    """max_turns parameter is passed to ClaudeAgentOptions."""
    from autoswe.harness.runner import _run_async

    fake = StreamingClaudeFake()
    fake.script_text("Done.")
    fake.script_result(session_id="s-maxturns-001")

    async def run():
        with fake.patched():
            return await _run_async(
                "Quick task.",
                cwd="/tmp",
                permission_mode="plan",
                allowed_tools=["Read"],
                max_turns=50,
            )

    r = await run()
    args_str = str(fake.call_args)
    diag = [f"session_id: {r.session_id}", f"max_turns in options: {'max_turns=50' in args_str}"]
    passed = "max_turns=50" in args_str

    return result("max_turns", passed, "max_turns param passed to SDK", diag)


# ==== Runner ====

ALL_SCENARIOS = [
    scenario_plan_file_detection,
    scenario_progress_callback,
    scenario_disallowed_tools,
    scenario_multi_turn,
    scenario_error_subtype,
    scenario_empty_text,
    scenario_cost_tracking,
    scenario_crash_mid_text,
    scenario_resume_session,
    scenario_callback_wiring,
    scenario_mcp_tool,
    scenario_write_outside_plans,
    scenario_model_override,
    scenario_max_turns,
]


async def run_all():
    results = []
    print(f"\n{Colors.BOLD}{'=' * 60}{Colors.RESET}")
    print(f"{Colors.BOLD}Extended Feature Test Harness — {len(ALL_SCENARIOS)} scenarios{Colors.RESET}")
    print(f"{Colors.BOLD}{'=' * 60}{Colors.RESET}\n")

    for scenario_fn in ALL_SCENARIOS:
        r = await scenario_fn()
        print_result(r, verbose=True)
        results.append(r)

    passed = sum(1 for r in results if r.passed)
    total = len(results)
    print(f"\n{Colors.BOLD}{'=' * 60}{Colors.RESET}")
    if passed == total:
        print(f"{Colors.GREEN}{Colors.BOLD}All {total} scenarios passed ✓{Colors.RESET}")
    else:
        print(f"{Colors.YELLOW}{Colors.BOLD}{passed}/{total} scenarios passed{Colors.RESET}")
        for r in results:
            if not r.passed:
                print(f"  {Colors.RED}✗ {r.name}{Colors.RESET}")
    print(f"{Colors.BOLD}{'=' * 60}{Colors.RESET}")

    return results


if __name__ == "__main__":
    asyncio.run(run_all())
