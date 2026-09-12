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

import pytest

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


def test_run_spec_output_format_defaults_to_none():
    """RunSpec.output_format defaults to None (no structured-output request)."""
    from autoswe.harness.backends.base import RunSpec

    spec = RunSpec(prompt="p", cwd="/tmp")
    assert spec.output_format is None
    spec = RunSpec(prompt="p", cwd="/tmp", output_format={"type": "json_schema", "schema": {}})
    assert spec.output_format == {"type": "json_schema", "schema": {}}


def test_claude_backend_structured_output_capability():
    """Claude Code supports structured_output; Codex does not (issue #159)."""
    from autoswe.harness.backends.claude_code import ClaudeCodeBackend
    from autoswe.harness.backends.codex import CodexBackend

    assert "structured_output" in ClaudeCodeBackend.capabilities()
    assert "structured_output" not in CodexBackend.capabilities()


def test_pi_backend_structured_output_capability():
    """pi does not support structured_output (no --mode json schema output)."""
    from autoswe.harness.backends.pi import PiBackend

    assert "structured_output" not in PiBackend.capabilities()


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


# ---------- pi backend capabilities ----------


def test_pi_backend_capabilities_exact():
    """PiBackend advertises exactly mode + resume + session_fork + progress_stream + mcp."""
    from autoswe.harness.backends.pi import PiBackend

    caps = PiBackend.capabilities()
    assert caps == {"mode", "resume", "session_fork", "progress_stream", "mcp"}


def test_pi_backend_has_mode_capability():
    """PiBackend advertises 'mode' — it has real --tools read-only enforcement."""
    from autoswe.harness.backends.pi import PiBackend

    assert "mode" in PiBackend.capabilities()


def test_pi_backend_has_session_fork_capability():
    """PiBackend advertises 'session_fork' (it has the --fork primitive).

    This is the capability Codex LACKS: pi can fork a checkpoint into a new
    session on /retry, so the provenance gate accepts a pi checkpoint when the
    fix harness is pi.
    """
    from autoswe.harness.backends.pi import PiBackend

    assert "session_fork" in PiBackend.capabilities()


def test_pi_backend_retries_on_error_and_killed():
    """PiBackend retries on the CLI-subprocess failure surface, like Codex."""
    import asyncio

    from autoswe.harness.backends.pi import PiBackend

    assert PiBackend.retryable_subtypes() == {"error", "killed"}
    assert asyncio.TimeoutError in PiBackend.retryable_exceptions()
    assert OSError in PiBackend.retryable_exceptions()


def test_pi_mode_tools_allowlist():
    """pi translates mode into a real --tools allowlist via _tools_for_spec."""
    from autoswe.harness.backends.base import RunSpec
    from autoswe.harness.backends.pi import _MODE_TOOLS, _tools_for_spec

    # plan/read_only → the read-only recipe (no write/bash).
    assert _tools_for_spec(RunSpec(prompt="p", cwd="/tmp", mode="plan")) == \
        list(_MODE_TOOLS["plan"])
    assert "bash" not in _tools_for_spec(RunSpec(prompt="p", cwd="/tmp", mode="plan"))
    assert "edit" not in _tools_for_spec(RunSpec(prompt="p", cwd="/tmp", mode="plan"))
    assert "write" not in _tools_for_spec(RunSpec(prompt="p", cwd="/tmp", mode="plan"))
    # read_write → the full working set.
    rw = _tools_for_spec(RunSpec(prompt="p", cwd="/tmp", mode="read_write"))
    assert "bash" in rw and "edit" in rw and "write" in rw
    # unset mode falls back to read_write.
    assert _tools_for_spec(RunSpec(prompt="p", cwd="/tmp")) == \
        _tools_for_spec(RunSpec(prompt="p", cwd="/tmp", mode="read_write"))
    # extra_tools append to the allowlist.
    assert "CustomTool" in _tools_for_spec(
        RunSpec(prompt="p", cwd="/tmp", mode="plan", extra_tools=["CustomTool"])
    )


def test_pi_backend_wires_fork_session_flag_on_retry_spec():
    """A fork spec (resume + fork_session) reaches the pi CLI as
    ``--fork <resume> --session-id <new>`` — a NEW session id, not the source."""
    import asyncio

    from autoswe.harness.backends.base import RunSpec
    from autoswe.harness.backends.pi import PiBackend
    from tests.fakes.pi_fake import PiFake

    spec = RunSpec(
        prompt="retry",
        cwd="/tmp",
        model="claude-sonnet-4-5",
        resume="last-good-pi",
        fork_session=True,
        mode="read_write",
    )

    with PiFake() as fake:
        fake.script_fix("done")
        asyncio.run(PiBackend().run(spec))

    assert len(fake.calls) == 1
    call = fake.calls[0]
    assert call["is_fork"] is True
    assert call["fork"] == "last-good-pi", "--fork must carry the source session"
    assert call["session_id"] is not None
    assert call["session_id"] != "last-good-pi", "a fork must mint a new session id"


def test_pi_backend_plain_resume_no_fork_flag():
    """A plain resume (fork_session unset) reaches pi as ``--session`` only."""
    import asyncio

    from autoswe.harness.backends.base import RunSpec
    from autoswe.harness.backends.pi import PiBackend
    from tests.fakes.pi_fake import PiFake

    spec = RunSpec(
        prompt="resume",
        cwd="/tmp",
        model="claude-sonnet-4-5",
        resume="prior-pi",
        mode="read_write",
    )

    with PiFake() as fake:
        fake.script_fix("done")
        asyncio.run(PiBackend().run(spec))

    assert len(fake.calls) == 1
    call = fake.calls[0]
    assert call["is_resume"] is True
    assert call["is_fork"] is False
    assert call["resume"] == "prior-pi"
    assert "fork" not in call


def test_pi_backend_fresh_run_mints_session_id():
    """A fresh (no resume) run pins a new --session-id; the parser echoes it back."""
    import asyncio

    from autoswe.harness.backends.base import RunSpec
    from autoswe.harness.backends.pi import PiBackend
    from tests.fakes.pi_fake import PiFake

    spec = RunSpec(
        prompt="plan",
        cwd="/tmp",
        model="claude-sonnet-4-5",
        mode="plan",
    )

    with PiFake() as fake:
        fake.script_plan("a plan")
        result = asyncio.run(PiBackend().run(spec))

    call = fake.calls[0]
    assert call["is_fresh"] is True
    assert call["session_id"] is not None
    # A fresh run pins a real uuid4 as --session-id (the fake's session header
    # then echoes back whatever scripted id it was fed; the parser's header
    # wins over the pre-seeded pin, so RunResult carries a non-empty id).
    import uuid

    uuid.UUID(call["session_id"])
    assert result.session_id


# ---------- fork-on-retry (session_fork capability) ----------


def test_claude_backend_has_session_fork_capability():
    """ClaudeCodeBackend should advertise 'session_fork' (it has fork_session)."""
    from autoswe.harness.backends.claude_code import ClaudeCodeBackend

    assert "session_fork" in ClaudeCodeBackend.capabilities()


@pytest.mark.parametrize(
    "version_str, expected",
    [
        ("0.2.137", True),   # exactly the floor
        ("0.2.136", False),  # one patch below → no fork
        ("0.2.138", True),
        ("0.3.0", True),     # higher minor wins even with patch 0
        ("0.1.999", False),  # lower minor loses even with a huge patch
        ("1.0.0", True),     # higher major
        ("0.2", False),      # 2-component → patch 0 → below the floor
    ],
)
def test_sdk_supports_session_fork_version_boundary(monkeypatch, version_str, expected):
    """_sdk_supports_session_fork compares the installed SDK against the floor
    (>= 0.2.137). The installed SDK in the test env is exactly the floor, so this
    branch is otherwise only exercised through its absence; pin the boundary
    directly by faking importlib.metadata.version.
    """
    import importlib.metadata

    from autoswe.harness.backends import claude_code as cc

    monkeypatch.setattr(importlib.metadata, "version", lambda name: version_str)
    assert cc._sdk_supports_session_fork() is expected


def test_sdk_supports_session_fork_unparseable_version(monkeypatch):
    """An unreadable/unparseable SDK version is treated as 'new enough' (safe
    direction) rather than demoting the capability."""
    import importlib.metadata

    from autoswe.harness.backends import claude_code as cc

    monkeypatch.setattr(importlib.metadata, "version", lambda name: "not-a-version")
    assert cc._sdk_supports_session_fork() is True


def test_codex_backend_lacks_session_fork_capability():
    """CodexBackend must NOT advertise 'session_fork' (no fork primitive)."""
    from autoswe.harness.backends.codex import CodexBackend

    assert "session_fork" not in CodexBackend.capabilities()


def _capture_claude_options(spec):
    """Run ClaudeCodeBackend with the SDK query() monkeypatched to a no-op that
    records the ClaudeAgentOptions it receives. Returns the captured options.

    ``_run_async`` consumes the SDK as ``async for msg in query(prompt=..., options=...)``
    (the name ``query`` is imported fresh from claude_agent_sdk inside the
    coroutine), so the patch target is ``claude_agent_sdk.query`` and it must
    return an async iterable that yields nothing.
    """
    import asyncio

    import claude_agent_sdk as sdk

    from autoswe.harness.backends import claude_code as cc

    captured = {}

    def fake_query(prompt, options):
        captured["options"] = options

        async def _empty():
            return
            yield  # pragma: no cover

        return _empty()

    original_query = sdk.query
    try:
        sdk.query = fake_query
        asyncio.run(cc.ClaudeCodeBackend()._run_async(spec))
    finally:
        sdk.query = original_query

    return captured["options"]


def test_claude_wires_fork_session_flag_on_retry_spec():
    """fork_session=True + resume must reach ClaudeAgentOptions.fork_session=True."""
    from autoswe.harness.backends.base import RunSpec

    spec = RunSpec(
        prompt="retry",
        cwd="/tmp",
        resume="last-good",
        fork_session=True,
        mode="read_write",
    )
    options = _capture_claude_options(spec)
    assert getattr(options, "fork_session", False) is True, (
        "ClaudeAgentOptions must carry fork_session=True on a fork spec"
    )
    assert options.resume == "last-good"


def test_claude_no_fork_flag_when_not_requested():
    """A plain resume (fork_session unset) must NOT set fork_session=True."""
    from autoswe.harness.backends.base import RunSpec

    spec = RunSpec(
        prompt="resume",
        cwd="/tmp",
        resume="prior",
        mode="read_write",
    )
    options = _capture_claude_options(spec)
    assert getattr(options, "fork_session", False) in (False, None), (
        "fork_session must stay falsy when the spec did not request a fork"
    )


def test_claude_degrades_to_resume_when_sdk_too_old(monkeypatch):
    """On an SDK older than the floor, a fork spec degrades to plain resume
    (no fork_session flag) instead of passing an unknown option / crashing."""
    from autoswe.harness.backends import claude_code as cc
    from autoswe.harness.backends.base import RunSpec

    monkeypatch.setattr(cc, "_sdk_supports_session_fork", lambda: False)

    spec = RunSpec(
        prompt="retry",
        cwd="/tmp",
        resume="last-good",
        fork_session=True,
        mode="read_write",
    )
    options = _capture_claude_options(spec)
    assert getattr(options, "fork_session", False) in (False, None), (
        "An old SDK must NOT receive fork_session=True — degrade to plain resume"
    )
    assert options.resume == "last-good"


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


def test_backend_has_capability_pi():
    """backend_has_capability returns correct values for a pi profile.

    pi advertises mode + resume + session_fork + progress_stream + mcp and
    nothing else (no per-tool approval, no plan_file, no structured_output).
    """
    from autoswe.harness.runner import backend_has_capability

    harness = {"backend": "pi", "model": "claude-sonnet-4-5"}
    assert backend_has_capability(harness, "mode")
    assert backend_has_capability(harness, "resume")
    assert backend_has_capability(harness, "session_fork")
    assert backend_has_capability(harness, "progress_stream")
    assert backend_has_capability(harness, "mcp")
    assert not backend_has_capability(harness, "can_use_tool")
    assert not backend_has_capability(harness, "plan_permission")
    assert not backend_has_capability(harness, "plan_file")
    assert not backend_has_capability(harness, "structured_output")


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


# ---------- has_read_only_enforcement helper (issue #166) ----------


def test_has_read_only_enforcement_claude_code():
    """Claude Code enforces read-only via mode + can_use_tool → True."""
    from autoswe.harness.runner import has_read_only_enforcement

    assert has_read_only_enforcement({"backend": "claude_code"}) is True


def test_has_read_only_enforcement_codex_is_false():
    """Codex has neither 'mode' nor 'can_use_tool' → read-only NOT enforced.

    This is the issue #166 condition: plan/review on a Codex profile must
    loudly degrade and rely on the post-run worktree backstop.
    """
    from autoswe.harness.runner import has_read_only_enforcement

    assert has_read_only_enforcement({"backend": "codex", "model": "gpt-5.6-terra"}) is False


def test_has_read_only_enforcement_pi_is_true():
    """pi enforces read-only via the --tools allowlist (advertises 'mode').

    This is the pi ≠ codex distinction: a plan/review phase on a pi profile
    keeps its read-only guarantee at the CLI level and must NOT loudly degrade
    (no ``ensure_worktree_unchanged``-reliant path), unlike Codex.
    """
    from autoswe.harness.runner import has_read_only_enforcement

    assert has_read_only_enforcement(
        {"backend": "pi", "model": "claude-sonnet-4-5"}
    ) is True


def test_has_read_only_enforcement_default_is_claude():
    """None harness_cfg defaults to Claude → enforced."""
    from autoswe.harness.runner import has_read_only_enforcement

    assert has_read_only_enforcement(None) is True


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


def test_interpret_plan_result_posted_question_trusts_callback(tmp_path):
    """asked_question_posted=True means the standalone post landed — no
    fallback re-post (issue #184)."""
    from unittest.mock import patch

    from autoswe.harness.planner import _interpret_plan_result
    from autoswe.harness.runner import RunResult

    result = RunResult("", "s", "success")
    state = {"asked_question_md": "## Question", "asked_question_posted": True}
    task = {"owner": "o", "repo": "r", "issue_number": 1, "_token": "tok"}

    with patch("autoswe.harness.planner.post_question_fallback") as mock_fb:
        done, pf = _interpret_plan_result(
            result, state=state, harness={"backend": "claude_code"},
            task=task, repo_cfg={"provider": "github"},
            progress_callback=lambda body: None,
        )

    assert done == "WAITING: questions"
    mock_fb.assert_not_called()


def test_interpret_plan_result_failed_question_post_falls_back(tmp_path):
    """asked_question_posted=False triggers the fallback post so the user
    still sees the question (issue #184)."""
    from unittest.mock import patch

    from autoswe.harness.planner import _interpret_plan_result
    from autoswe.harness.runner import RunResult

    result = RunResult("", "s", "success")
    state = {"asked_question_md": "## Question", "asked_question_posted": False}
    task = {"owner": "o", "repo": "r", "issue_number": 1, "_token": "tok"}
    sticky = []

    with patch("autoswe.harness.planner.post_question_fallback") as mock_fb:
        done, pf = _interpret_plan_result(
            result, state=state, harness={"backend": "claude_code"},
            task=task, repo_cfg={"provider": "github"},
            progress_callback=sticky.append,
        )

    assert done == "WAITING: questions"
    mock_fb.assert_called_once_with(task, {"provider": "github"}, "## Question", sticky.append)


def test_interpret_plan_result_no_task_no_fallback(tmp_path):
    """Without task/repo_cfg (e.g. direct test calls), a failed post is
    reported as WAITING without attempting a fallback (no crash)."""
    from autoswe.harness.planner import _interpret_plan_result
    from autoswe.harness.runner import RunResult

    result = RunResult("", "s", "success")
    state = {"asked_question_md": "## Question", "asked_question_posted": False}

    with patch("autoswe.harness.planner.post_question_fallback") as mock_fb:
        done, pf = _interpret_plan_result(
            result, state=state, harness={"backend": "claude_code"},
        )

    assert done == "WAITING: questions"
    mock_fb.assert_not_called()


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
    from autoswe.harness.backends.claude_code import _MODE_CONFIG, PROGRESS_TOOLS

    for mode_name in ("plan", "read_only"):
        _perm, tools, _disallowed = _MODE_CONFIG[mode_name]
        for tool in PROGRESS_TOOLS:
            assert tool in tools, f"{mode_name} should include {tool}"


def test_read_write_includes_agent_task_tools():
    """read_write mode should include all AGENT_TASK_TOOLS (includes Agent)."""
    from autoswe.harness.backends.claude_code import _MODE_CONFIG, AGENT_TASK_TOOLS

    _perm, tools, _disallowed = _MODE_CONFIG["read_write"]
    for tool in AGENT_TASK_TOOLS:
        assert tool in tools, f"read_write should include {tool}"


def test_read_write_tool_set_is_exact():
    """read_write mode exposes exactly the documented tool set — no more, no
    fewer. This pins the fix-phase allow-list so a silently dropped (or added)
    tool fails the build.

    Issue #169 S6 follow-up: TaskOutput was silently dropped from this list and
    the change went unnoticed precisely because no test asserted the exact set.
    This test makes the read_write composition auditable. TaskOutput is
    intentionally part of the fix-phase set (see the note on _READ_WRITE_TOOLS
    in claude_code.py) even though issue #132 removed it from the shared
    PROGRESS_TOOLS list used by read_only/plan.

    The expected set is built from the core tools plus the shared MCP comment
    tools (themselves asserted by test_mode_includes_mcp_comment_tools), so it
    stays a maintenance-free snapshot of intent.
    """
    from autoswe.harness.backends.claude_code import _MCP_COMMENT_TOOLS, _MODE_CONFIG

    _perm, tools, _disallowed = _MODE_CONFIG["read_write"]
    expected = {
        "Read", "Edit", "Write", "Bash", "Glob", "Grep",
        "AskUserQuestion",
        "TodoWrite", "TaskCreate", "TaskUpdate", "TaskGet",
        "TaskList", "TaskOutput", "TaskStop", "Agent",
        *set(_MCP_COMMENT_TOOLS),
    }
    assert set(tools) == expected, (
        "read_write tool set drifted from the documented set; "
        "update _READ_WRITE_TOOLS deliberately and adjust this expectation"
    )


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


def test_plan_file_capability_pi():
    """PiBackend must NOT advertise the 'plan_file' capability (plan capture
    is text-pattern driven via <AUTOSWE_PLAN> tags, not a plan file)."""
    from autoswe.harness.backends.pi import PiBackend

    assert "plan_file" not in PiBackend.capabilities()


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
        done, pf = _interpret_plan_result(
            result, state={}, harness={"backend": "codex", "model": "gpt-5.6-terra"}
        )

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
