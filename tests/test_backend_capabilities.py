"""Tests for Phase 3 — generic intent (mode), capabilities, and backend neutrality.

Verifies:
- RunSpec.mode field and Mode type.
- ClaudeCodeBackend translates mode → permission_mode + tool sets.
- extra_tools and disallowed_tools_override work with mode.
- backend_has_capability() helper.
- Capability-aware plan result interpretation.
- backward_compatibility when mode is not set (legacy path).
"""
from unittest.mock import patch

# ---------- RunSpec.mode field ----------


def test_run_spec_has_mode_field():
    """RunSpec should have a mode field defaulting to None."""
    from autoswe.harness.backends.base import RunSpec

    spec = RunSpec(prompt="p", cwd="/tmp")
    assert spec.mode is None


def test_run_spec_mode_values():
    """RunSpec should accept plan, read_only, read_write modes."""
    from autoswe.harness.backends.base import RunSpec

    for m in ("plan", "read_only", "read_write"):
        spec = RunSpec(prompt="p", cwd="/tmp", mode=m)
        assert spec.mode == m


def test_run_spec_extra_tools():
    """RunSpec should accept extra_tools and disallowed_tools_override."""
    from autoswe.harness.backends.base import RunSpec

    spec = RunSpec(
        prompt="p",
        cwd="/tmp",
        mode="read_write",
        extra_tools=["CustomTool"],
        disallowed_tools_override=["AskUserQuestion"],
    )
    assert spec.extra_tools == ["CustomTool"]
    assert spec.disallowed_tools_override == ["AskUserQuestion"]


def test_mode_type_exported():
    """Mode type should be importable from backends and runner."""
    from autoswe.harness.backends import Mode
    from autoswe.harness.runner import Mode as RunnerMode

    # Both should be the same type
    assert Mode is RunnerMode


# ---------- ClaudeCodeBackend mode translation ----------


def test_claude_backend_has_mode_capability():
    """ClaudeCodeBackend should advertise 'mode' capability."""
    from autoswe.harness.backends.claude_code import ClaudeCodeBackend

    caps = ClaudeCodeBackend.capabilities()
    assert "mode" in caps
    assert "mcp" in caps
    assert "can_use_tool" in caps


def test_mode_plan_sets_permission_and_tools():
    """mode='plan' should translate to permission_mode='plan' + read-only tools."""
    from autoswe.harness.backends.claude_code import _MODE_CONFIG

    perm, tools, disallowed = _MODE_CONFIG["plan"]
    assert perm == "plan"
    assert "Read" in tools
    assert "Glob" in tools
    assert "Grep" in tools
    assert "Agent" not in tools
    assert "ExitPlanMode" in disallowed


def test_mode_read_write_sets_bypass_and_tools():
    """mode='read_write' should translate to bypassPermissions + full tools."""
    from autoswe.harness.backends.claude_code import _MODE_CONFIG

    perm, tools, disallowed = _MODE_CONFIG["read_write"]
    assert perm == "bypassPermissions"
    assert "Edit" in tools
    assert "Write" in tools
    assert "Bash" in tools
    assert "Agent" in tools
    assert "AskUserQuestion" in tools
    assert not disallowed


def test_mode_read_only_sets_plan_permission():
    """mode='read_only' should translate to permission_mode='plan' + read-only tools (no AskUserQuestion)."""
    from autoswe.harness.backends.claude_code import _MODE_CONFIG

    perm, tools, disallowed = _MODE_CONFIG["read_only"]
    assert perm == "plan"
    assert "Read" in tools
    assert "Edit" not in tools
    assert "Write" not in tools
    assert "Bash" not in tools
    assert "Agent" not in tools
    # read_only does NOT include AskUserQuestion (reviewer is autonomous)
    assert "AskUserQuestion" not in tools


def test_mode_includes_mcp_comment_tools():
    """All mode tool sets should include MCP comment tools."""
    from autoswe.harness.backends.claude_code import _MCP_COMMENT_TOOLS, _MODE_CONFIG

    for mode_name, (_perm, tools, _disallowed) in _MODE_CONFIG.items():
        for mcp_tool in _MCP_COMMENT_TOOLS:
            assert mcp_tool in tools, f"{mode_name} should include {mcp_tool}"


# ---------- Mode translation in _run_async ----------


def test_claude_backend_translates_mode_to_options():
    """When mode is set, ClaudeCodeBackend should use mode-derived config
    instead of legacy permission_mode/allowed_tools fields."""
    import asyncio

    from autoswe.harness.backends.base import RunSpec
    from autoswe.harness.backends.claude_code import ClaudeCodeBackend

    spec = RunSpec(
        prompt="p",
        cwd="/tmp",
        mode="plan",
        # Legacy fields should be ignored when mode is set
        permission_mode="bypassPermissions",
        allowed_tools=["Bash"],
    )
    backend = ClaudeCodeBackend()
    coro = backend.run(spec)

    # The coro should be an awaitable
    assert asyncio.iscoroutine(coro)
    coro.close()


def test_legacy_path_without_mode():
    """When mode is None, legacy permission_mode/allowed_tools should be used."""
    import asyncio

    from autoswe.harness.backends.base import RunSpec
    from autoswe.harness.backends.claude_code import ClaudeCodeBackend

    spec = RunSpec(
        prompt="p",
        cwd="/tmp",
        mode=None,
        permission_mode="bypassPermissions",
        allowed_tools=["Bash", "Read"],
    )
    backend = ClaudeCodeBackend()
    coro = backend.run(spec)

    assert asyncio.iscoroutine(coro)
    coro.close()


# ---------- backend_has_capability helper ----------


def test_backend_has_capability_claude_code():
    """backend_has_capability should return True for ClaudeCodeBackend caps."""
    from autoswe.harness.runner import backend_has_capability

    harness = {"backend": "claude_code"}
    assert backend_has_capability(harness, "mode")
    assert backend_has_capability(harness, "mcp")
    assert backend_has_capability(harness, "can_use_tool")
    assert backend_has_capability(harness, "resume")
    assert backend_has_capability(harness, "progress_stream")


def test_backend_has_capability_default():
    """backend_has_capability with None harness_cfg should default to Claude."""
    from autoswe.harness.runner import backend_has_capability

    assert backend_has_capability(None, "mode")
    assert backend_has_capability(None, "mcp")


def test_backend_has_capability_missing():
    """backend_has_capability should return False for unknown capability."""
    from autoswe.harness.runner import backend_has_capability

    harness = {"backend": "claude_code"}
    assert not backend_has_capability(harness, "nonexistent_capability")


# ---------- Capability-aware plan interpretation ----------


def test_interpret_plan_result_mcp_plan_posted(tmp_path):
    """When MCP is available and plan_posted=True, return PLAN_READY."""
    from autoswe.harness.planner import _interpret_plan_result
    from autoswe.harness.runner import RunResult

    result = RunResult("", "s", "success", plan_posted=True)
    harness = {"backend": "claude_code"}

    done, pf = _interpret_plan_result(result, state={}, harness=harness)
    assert done == "PLAN_READY"


def test_interpret_plan_result_mcp_question_posted(tmp_path):
    """When MCP is available and question_posted=True, return WAITING."""
    from autoswe.harness.planner import _interpret_plan_result
    from autoswe.harness.runner import RunResult

    result = RunResult("", "s", "success", question_posted=True)
    harness = {"backend": "claude_code"}

    done, pf = _interpret_plan_result(result, state={}, harness=harness)
    assert done.startswith("WAITING:")


def test_interpret_plan_result_state_question(tmp_path):
    """AskUserQuestion via state should always be detected (capability-independent)."""
    from autoswe.harness.planner import _interpret_plan_result
    from autoswe.harness.runner import RunResult

    result = RunResult("", "s", "success")
    state = {"asked_question_md": "## Question"}

    done, pf = _interpret_plan_result(result, state=state, harness={"backend": "claude_code"})
    assert done == "WAITING: questions"


def test_interpret_plan_result_fallback_to_text(tmp_path):
    """When no MCP flags set, fall back to text parsing."""
    from autoswe.harness.planner import _interpret_plan_result
    from autoswe.harness.runner import RunResult

    text = "<AUTOSWE_PLAN>\nStep 1\n</AUTOSWE_PLAN>"
    result = RunResult(text, "s", "success")
    harness = {"backend": "claude_code"}

    with patch("autoswe.harness.planner._find_latest_plan_file", return_value=None):
        done, pf = _interpret_plan_result(result, state={}, harness=harness)

    assert "PLAN_READY" in done
    assert done.startswith("_POST:")


def test_interpret_plan_result_mcp_beats_text(tmp_path):
    """When plan_posted=True, MCP path should take precedence over text."""
    from autoswe.harness.planner import _interpret_plan_result
    from autoswe.harness.runner import RunResult

    # Text also has a plan tag — but MCP should win
    text = "<AUTOSWE_PLAN>\nText plan\n</AUTOSWE_PLAN>"
    result = RunResult(text, "s", "success", plan_posted=True)
    harness = {"backend": "claude_code"}

    done, pf = _interpret_plan_result(result, state={}, harness=harness)
    assert done == "PLAN_READY"


def test_interpret_plan_result_non_mcp_backend_ignores_mcp_flags(tmp_path):
    """When a backend lacks the 'mcp' capability, plan_posted and
    question_posted flags are ignored and the handler falls back to
    text parsing (the Codex path before MCP support is added)."""
    from autoswe.harness.planner import _interpret_plan_result
    from autoswe.harness.runner import RunResult

    # Result claims MCP tools were used, but the backend doesn't support MCP
    text = "<AUTOSWE_PLAN>\nStep 1\n</AUTOSWE_PLAN>"
    result = RunResult(text, "s", "success", plan_posted=True, question_posted=True)

    # Patch where planner looks it up (via its `runner` module import)
    with patch("autoswe.harness.runner.backend_has_capability", return_value=False):
        done, pf = _interpret_plan_result(result, state={}, harness={"backend": "codex"})

    # plan_posted was ignored → fell through to text parsing → _POST:PLAN_READY
    assert "PLAN_READY" in done
    assert done.startswith("_POST:")


def test_interpret_plan_result_non_mcp_backend_uses_plan_file(tmp_path):
    """When a backend lacks 'mcp' but the RunResult has a valid plan_file_path,
    _interpret_plan_result should still detect it via the text-parse fallback.

    The non-MCP path goes through _extract_plan_output which returns a
    ``_POST:PLAN_READY\t<comment>`` tuple.  The plan_file_path is captured
    in the second return value either way (MCP or text-parse path).
    """
    from autoswe.harness.planner import _interpret_plan_result
    from autoswe.harness.runner import RunResult

    plan_file = tmp_path / "codex-plan.md"
    plan_file.write_text("# Plan from Codex\n\nStep 1: fix the bug")

    result = RunResult("", "s", "success", plan_file_path=str(plan_file))

    with patch.object(
        __import__("autoswe.harness.runner", fromlist=["backend_has_capability"]),
        "backend_has_capability", return_value=False,
    ):
        done, pf = _interpret_plan_result(result, state={}, harness={"backend": "codex"})

    # Non-MCP path uses _extract_plan_output → _POST:PLAN_READY\t<comment>
    assert done.startswith("_POST:PLAN_READY")
    assert "Plan from Codex" in done
    assert pf == str(plan_file)


# ---------- Runner.run() with mode ----------


def test_runner_run_accepts_mode():
    """runner.run() should accept mode parameter and pass it to RunSpec."""
    import asyncio

    from autoswe.harness.runner import RunResult, run

    cfg = {"AGENT_TIMEOUT": 7200, "CLAUDE_CLI_PATH": ""}

    with patch.object(asyncio, "run") as mock_run:
        def fake_run(coro):
            coro.close()
            return RunResult(text="ok", session_id="s1", subtype="success")
        mock_run.side_effect = fake_run

        run("test prompt", cwd="/tmp", cfg=cfg, mode="plan")

    assert mock_run.called


def test_runner_run_accepts_extra_tools():
    """runner.run() should accept extra_tools parameter."""
    import asyncio

    from autoswe.harness.runner import RunResult, run

    cfg = {"AGENT_TIMEOUT": 7200, "CLAUDE_CLI_PATH": ""}

    with patch.object(asyncio, "run") as mock_run:
        def fake_run(coro):
            coro.close()
            return RunResult(text="ok", session_id="s1", subtype="success")
        mock_run.side_effect = fake_run

        run("test prompt", cwd="/tmp", cfg=cfg, mode="read_write",
            extra_tools=["CustomTool"])

    assert mock_run.called


def test_runner_run_accepts_disallowed_tools_override():
    """runner.run() should accept disallowed_tools_override parameter."""
    import asyncio

    from autoswe.harness.runner import RunResult, run

    cfg = {"AGENT_TIMEOUT": 7200, "CLAUDE_CLI_PATH": ""}

    with patch.object(asyncio, "run") as mock_run:
        def fake_run(coro):
            coro.close()
            return RunResult(text="ok", session_id="s1", subtype="success")
        mock_run.side_effect = fake_run

        run("test prompt", cwd="/tmp", cfg=cfg, mode="read_write",
            disallowed_tools_override=["AskUserQuestion"])

    assert mock_run.called


# ---------- Mode tool set composition ----------


def test_mode_config_includes_progress_tools():
    """Plan and read_only modes should include PROGRESS_TOOLS."""
    from autoswe.harness.backends.base import PROGRESS_TOOLS
    from autoswe.harness.backends.claude_code import _MODE_CONFIG

    for mode_name in ("plan", "read_only"):
        _perm, tools, _disallowed = _MODE_CONFIG[mode_name]
        for tool in PROGRESS_TOOLS:
            assert tool in tools, f"{mode_name} should include {tool}"


def test_read_write_includes_agent_task_tools():
    """read_write mode should include all AGENT_TASK_TOOLS (includes Agent)."""
    from autoswe.harness.backends.base import AGENT_TASK_TOOLS
    from autoswe.harness.backends.claude_code import _MODE_CONFIG

    _perm, tools, _disallowed = _MODE_CONFIG["read_write"]
    for tool in AGENT_TASK_TOOLS:
        assert tool in tools, f"read_write should include {tool}"


def test_plan_includes_ask_user_question():
    """plan mode should include AskUserQuestion (planner can ask clarifying questions)."""
    from autoswe.harness.backends.claude_code import _MODE_CONFIG

    _perm, tools, _disallowed = _MODE_CONFIG["plan"]
    assert "AskUserQuestion" in tools


# ---------- plan_file capability ----------


def test_plan_file_capability_claude_code():
    """ClaudeCodeBackend must advertise the 'plan_file' capability."""
    from autoswe.harness.backends.claude_code import ClaudeCodeBackend

    assert "plan_file" in ClaudeCodeBackend.capabilities()


def test_plan_file_capability_codex():
    """CodexBackend must NOT advertise the 'plan_file' capability."""
    from autoswe.harness.backends.codex import CodexBackend

    assert "plan_file" not in CodexBackend.capabilities()


def test_interpret_plan_result_codex_prose_skips_fs_scan(tmp_path):
    """Codex backend + prose-only output must land on WAITING: see comment.

    Even when ~/.claude/plans/ contains a stale file from a prior run, the
    codex path must not post it — the filesystem scan is capability-gated.
    """
    from autoswe.harness.planner import _interpret_plan_result
    from autoswe.harness.runner import RunResult

    stale = tmp_path / "stale.md"
    stale.write_text("## Stale Plan\n\nStep from a different issue")

    result = RunResult("Just some prose output", "s1", "success", plan_file_path=None)

    with patch("autoswe.harness.planner._find_latest_plan_file", return_value=stale):
        done, pf = _interpret_plan_result(result, state={}, harness={"backend": "codex"})

    assert "WAITING: see comment" in done
    assert pf is None


def test_interpret_plan_result_claude_code_prose_uses_fs_scan(tmp_path):
    """Claude Code backend + prose-only output still scans ~/.claude/plans/."""
    from autoswe.harness.planner import _interpret_plan_result
    from autoswe.harness.runner import RunResult

    plan_file = tmp_path / "plan.md"
    plan_file.write_text("## Plan\n\nStep 1: do the thing")

    result = RunResult("Some prose output", "s1", "success", plan_file_path=None)

    with patch("autoswe.harness.planner._find_latest_plan_file", return_value=plan_file):
        done, pf = _interpret_plan_result(result, state={}, harness={"backend": "claude_code"})

    assert "PLAN_READY" in done
    assert pf == str(plan_file)
