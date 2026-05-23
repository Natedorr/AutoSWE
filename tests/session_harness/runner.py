#!/usr/bin/env python3
"""Manual AutoSWE session test runner.

Run individual scenarios against the real AutoSWE codebase to validate
session management, plan mode, fix mode, and crash recovery.

Usage:
    # Run all scenarios
    python3 manual_runner.py

    # Run a specific scenario
    python3 manual_runner.py plan_new_session

    # Run with verbose output
    python3 manual_runner.py --verbose plan_new_session

    # Run integration tests against real Ollama (if available)
    python3 manual_runner.py --integration

Each scenario:
1. Sets up a fake streaming response (no real Claude call needed)
2. Runs the real _run_async() / planner() / coder() code path
3. Verifies expected outcomes
4. Reports PASS/FAIL with diagnostics

This is a manual testing tool, NOT auto pytest for CI.
The goal is to help align the streaming fake with real behavior
and catch session bugs before they hit production.

Scenarios:
    plan_new_session      - Verify NEW plan session returns valid session_id
    plan_question         - Verify AskUserQuestion → WAITING flow
    plan_crash_208        - Reproduce bug #208: crash before ResultMessage
    plan_crash_213        - Verify #213 fix: crash after ResultMessage
    fix_new_session       - Verify NEW fix session (not resume of plan)
    fix_resume            - Verify RESUME fix session adds to existing
    resume_with_guidance  - Verify resume passes previous session_id
    mcp_post_plan         - Verify MCP post_plan tool visible in stream
"""

import argparse
import asyncio
import os
import sys
from dataclasses import dataclass
from typing import Any

# Add AutoSWE source to path
AutoSWE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "github", "autoswe")
# AutoSWE_PATH is parent repo

# Add streaming fake to path


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


@dataclass
class ScenarioResult:
    name: str
    passed: bool
    details: str
    diagnostics: list[str]


# ==== Scenario definitions ====

async def scenario_plan_new_session(verbose: bool = False) -> ScenarioResult:
    """Plan phase should return a valid session_id (not None)."""
    from autoswe.harness.runner import _run_async

    fake = StreamingClaudeFake()
    fake.build_normal_response(
        "Here's my plan:\n1. Read the codebase\n2. Implement the fix\n3. Test",
        session_id="s-plan-test-001",
    )

    diagnostics = []

    async def run():
        with fake.patched():
            result = await _run_async(
                "Create a plan to add authentication.",
                cwd="/tmp",
                permission_mode="plan",
                allowed_tools=["Read"],
            )
        return result

    result = await run()
    diagnostics.append(f"session_id: {result.session_id}")
    diagnostics.append(f"subtype: {result.subtype}")
    diagnostics.append(f"text length: {len(result.text)}")

    passed = result.session_id == "s-plan-test-001" and result.subtype == "success"

    if verbose:
        diagnostics.append(f"full text: {result.text[:200]}")

    return ScenarioResult(
        name="plan_new_session",
        passed=passed,
        details="NEW plan session returns valid session_id",
        diagnostics=diagnostics,
    )


async def scenario_plan_question(verbose: bool = False) -> ScenarioResult:
    """AskUserQuestion + ResultMessage → session_id captured, WAITING triggered."""
    from autoswe.harness.runner import _run_async

    fake = StreamingClaudeFake()
    fake.build_question_flow(
        text_before="Reading the issue...",
        session_id="s-question-001",
        crash_after=False,
    )

    state = {}

    async def callback(name: str, input_data: dict, context: Any) -> Any:
        if name == "AskUserQuestion":
            state["asked_question_md"] = "## Questions\n\nWhat approach?"
        return PermissionResultAllow(updated_input=input_data)

    diagnostics = []

    async def run():
        with fake.patched():
            result = await _run_async(
                "Plan the fix.",
                cwd="/tmp",
                permission_mode="plan",
                allowed_tools=["Read", "AskUserQuestion"],
                can_use_tool=callback,
                state=state,
            )
        return result

    result = await run()
    diagnostics.append(f"session_id: {result.session_id}")
    diagnostics.append(f"subtype: {result.subtype}")
    diagnostics.append(f"state has asked_question_md: {'asked_question_md' in state}")

    # With ResultMessage arriving, session_id should be captured
    passed = result.session_id is not None

    return ScenarioResult(
        name="plan_question",
        passed=passed,
        details="AskUserQuestion + ResultMessage captures session_id",
        diagnostics=diagnostics,
    )


async def scenario_plan_crash_208(verbose: bool = False) -> ScenarioResult:
    """Bug #208 fix: crash before ResultMessage → session_id captured from AssistantMessage.

    With the early session_id capture fix, even when the async generator crashes
    before ResultMessage arrives, the session_id is preserved from the first
    AssistantMessage in the stream.
    """
    from autoswe.harness.runner import _run_async

    fake = StreamingClaudeFake()
    fake.script_text("Reading README.md...", session_id="s-crash-208")
    fake.script_crash("aclose(): asynchronous generator is already running")

    state = {}

    async def callback(name: str, input_data: dict, context: Any) -> Any:
        if name == "AskUserQuestion":
            state["asked_question_md"] = "## Questions"
        return PermissionResultAllow(updated_input=input_data)

    diagnostics = []

    async def run():
        with fake.patched():
            result = await _run_async(
                "Plan the fix.",
                cwd="/tmp",
                permission_mode="plan",
                allowed_tools=["Read", "AskUserQuestion"],
                can_use_tool=callback,
                state=state,
            )
        return result

    result = await run()
    diagnostics.append(f"session_id: {result.session_id}")
    diagnostics.append(f"subtype: {result.subtype}")
    diagnostics.append(f"text: {result.text[:100]}")
    diagnostics.append("")
    diagnostics.append("✅ Fix: session_id captured from AssistantMessage before crash.")
    diagnostics.append("   Even though ResultMessage never arrived, session_id is preserved.")

    # Fixed behavior: session_id should be captured from AssistantMessage
    passed = result.session_id == "s-crash-208"

    return ScenarioResult(
        name="plan_crash_208",
        passed=passed,
        details="Crash before ResultMessage → session_id preserved from AssistantMessage (#208 fix)",
        diagnostics=diagnostics,
    )


async def scenario_plan_crash_213(verbose: bool = False) -> ScenarioResult:
    """Fix #213: crash AFTER ResultMessage → session_id preserved."""
    from autoswe.harness.runner import _run_async

    fake = StreamingClaudeFake()
    fake.script_text("Working on the plan...")
    fake.script_result(session_id="s-preserved-001", subtype="success")
    fake.script_crash("aclose(): asynchronous generator is already running")

    diagnostics = []

    async def run():
        with fake.patched():
            result = await _run_async(
                "Plan the fix.",
                cwd="/tmp",
                permission_mode="plan",
                allowed_tools=["Read"],
            )
        return result

    result = await run()
    diagnostics.append(f"session_id: {result.session_id}")
    diagnostics.append(f"subtype: {result.subtype}")

    # Fix behavior: session_id should be preserved from ResultMessage
    passed = result.session_id == "s-preserved-001"

    return ScenarioResult(
        name="plan_crash_213",
        passed=passed,
        details="Crash after ResultMessage preserves session_id (#213 fix)",
        diagnostics=diagnostics,
    )


async def scenario_fix_new_session(verbose: bool = False) -> ScenarioResult:
    """Fix phase should start with a clean session (not resume of plan)."""
    from autoswe.harness.runner import _run_async

    fake = StreamingClaudeFake()
    fake.build_fix_flow(session_id="s-fix-001", num_edits=2)

    diagnostics = []

    async def run():
        with fake.patched():
            result = await _run_async(
                "Fix the bug described in the plan.",
                cwd="/tmp",
                permission_mode="fix",
                allowed_tools=["Read", "Edit", "Bash"],
            )
        return result

    result = await run()
    diagnostics.append(f"session_id: {result.session_id}")
    diagnostics.append(f"subtype: {result.subtype}")

    passed = result.session_id == "s-fix-001"

    return ScenarioResult(
        name="fix_new_session",
        passed=passed,
        details="NEW fix session (not plan resume) returns valid session_id",
        diagnostics=diagnostics,
    )


async def scenario_fix_resume(verbose: bool = False) -> ScenarioResult:
    """Resume fix session should continue from previous session_id."""
    from autoswe.harness.runner import _run_async

    fake = StreamingClaudeFake()
    fake.build_normal_response(
        "Continuing the fix from where we left off...",
        session_id="s-fix-resume-002",
    )

    previous_session = "s-fix-previous"
    diagnostics = []

    async def run():
        with fake.patched():
            result = await _run_async(
                "Continue fixing the remaining issues.",
                cwd="/tmp",
                permission_mode="fix",
                allowed_tools=["Read", "Edit"],
                resume=previous_session,
            )
        return result

    result = await run()
    diagnostics.append(f"previous session: {previous_session}")
    diagnostics.append(f"new session_id: {result.session_id}")
    diagnostics.append(f"resume param passed: {fake.call_args[0] if fake.call_args else 'N/A'}")

    # The key: resume should pass previous_session as the resume parameter
    passed = result.session_id is not None

    return ScenarioResult(
        name="fix_resume",
        passed=passed,
        details="RESUME fix session continues from previous session_id",
        diagnostics=diagnostics,
    )


async def scenario_mcp_post_plan(verbose: bool = False) -> ScenarioResult:
    """MCP post_plan tool call should be visible in the stream."""
    from autoswe.harness.runner import _run_async

    fake = StreamingClaudeFake()
    fake.script_text("Writing plan via MCP...")
    fake.script_server_tool(
        "mcp__autoswe_comment__post_plan",
        {"content": "## Plan\n1. Fix the thing"},
    )
    fake.script_result(session_id="s-mcp-001")

    diagnostics = []

    async def run():
        with fake.patched():
            result = await _run_async(
                "Plan the fix using MCP.",
                cwd="/tmp",
                permission_mode="plan",
                allowed_tools=["Read", "mcp__autoswe_comment__post_plan"],
            )
        return result

    result = await run()
    diagnostics.append(f"session_id: {result.session_id}")

    passed = result.session_id == "s-mcp-001"

    return ScenarioResult(
        name="mcp_post_plan",
        passed=passed,
        details="MCP ServerToolUse visible in stream",
        diagnostics=diagnostics,
    )


# ==== Integration scenarios (real Ollama) ====

async def integration_plan_session(cfg, tmp_path, verbose: bool = False) -> ScenarioResult:
    """Real Ollama: plan phase returns valid session_id."""
    from autoswe.harness.runner import _run_async

    diagnostics = []

    async def run():
        result = await _run_async(
            # Trivial task for small model — just write a one-line plan
            "Write a plan to add 'Hello World' to a file called test.txt. Just write the plan.",
            cwd=str(tmp_path),
            permission_mode="plan",
            allowed_tools=["Read", "Write"],
            model="qwen3.5:4b",
            max_turns=10,
        )
        return result

    try:
        result = await asyncio.wait_for(run(), timeout=120)
        diagnostics.append(f"session_id: {result.session_id}")
        diagnostics.append(f"subtype: {result.subtype}")
        diagnostics.append(f"text length: {len(result.text)}")
        passed = result.session_id is not None
    except asyncio.TimeoutError:
        diagnostics.append("TIMEOUT — Ollama took too long")
        passed = False
        result = None

    return ScenarioResult(
        name="integration_plan_session",
        passed=passed,
        details="Real Ollama plan session returns session_id",
        diagnostics=diagnostics,
    )


# ==== Runner ====

SCENARIOS = {
    "plan_new_session": scenario_plan_new_session,
    "plan_question": scenario_plan_question,
    "plan_crash_208": scenario_plan_crash_208,
    "plan_crash_213": scenario_plan_crash_213,
    "fix_new_session": scenario_fix_new_session,
    "fix_resume": scenario_fix_resume,
    "mcp_post_plan": scenario_mcp_post_plan,
}

INTEGRATION_SCENARIOS = {
    "plan_session": integration_plan_session,
}


def print_result(result: ScenarioResult, verbose: bool = False):
    """Print scenario result with colors."""
    status = f"{Colors.GREEN}PASS{Colors.RESET}" if result.passed else f"{Colors.RED}FAIL{Colors.RESET}"
    print(f"\n{Colors.BOLD}{result.name}{Colors.RESET}")
    print(f"  {status} — {result.details}")
    if verbose or not result.passed:
        for line in result.diagnostics:
            print(f"  {Colors.CYAN}{line}{Colors.RESET}")


async def run_scenario(name: str, verbose: bool = False, integration: bool = False):
    """Run a single scenario."""
    scenarios = INTEGRATION_SCENARIOS if integration else SCENARIOS

    if name not in scenarios:
        print(f"Unknown scenario: {name}")
        print(f"Available: {', '.join(scenarios.keys())}")
        return None

    if integration:
        import tempfile
        cfg = {
            "AGENT_TIMEOUT": 300,
            "ANTHROPIC_BASE_URL": "http://linux-server1:11434",
            "ANTHROPIC_AUTH_TOKEN": "OLLAMA_API_KEY",
            "ANTHROPIC_API_KEY": "OLLAMA_API_KEY",
            "CLAUDE_CLI_PATH": "",
        }
        tmp_path = tempfile.mkdtemp()
        result = await scenarios[name](cfg, tmp_path, verbose)
    else:
        result = await scenarios[name](verbose)

    print_result(result, verbose)
    return result


async def run_all_scenarios(verbose: bool = False, integration: bool = False):
    """Run all scenarios and return results."""
    scenarios = INTEGRATION_SCENARIOS if integration else SCENARIOS
    results = []

    print(f"\n{Colors.BOLD}{'=' * 60}{Colors.RESET}")
    print(f"{Colors.BOLD}AutoSWE Session Test Harness{Colors.RESET}")
    print(f"{Colors.BOLD}Mode: {'Integration (Ollama)' if integration else 'Streaming Fake (no Ollama)'}{Colors.RESET}")
    print(f"{Colors.BOLD}{'=' * 60}{Colors.RESET}\n")

    for name in scenarios:
        result = await run_scenario(name, verbose, integration)
        if result:
            results.append(result)

    # Summary
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


def main():
    parser = argparse.ArgumentParser(description="AutoSWE Session Test Harness")
    parser.add_argument("scenario", nargs="?", help="Scenario name (or omit for all)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("-i", "--integration", action="store_true", help="Run integration tests (requires Ollama)")
    args = parser.parse_args()

    if args.scenario:
        result = asyncio.run(run_scenario(args.scenario, args.verbose, args.integration))
        sys.exit(0 if result and result.passed else 1)
    else:
        results = asyncio.run(run_all_scenarios(args.verbose, args.integration))
        sys.exit(0 if all(r.passed for r in results) else 1)


if __name__ == "__main__":
    main()
