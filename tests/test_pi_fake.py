"""Fidelity guard — pins PiFake to the real PiBackend parser.

Feeds PiFake-emitted ``--mode json`` lines through the real ``PiBackend.run``
and asserts the resulting ``RunResult`` (text, session_id, subtype, cost) and
the recorded argv.  This prevents the fake from silently drifting when the
parser or command mapping changes — the same contract as ``test_codex_fake.py``.

Every builder's emitted stream must parse to the expected RunResult fields;
the real parser runs unmodified (PiFake patches ``create_subprocess_exec``).
"""
from __future__ import annotations

import asyncio

from autoswe.harness.backends.base import RunSpec
from autoswe.harness.backends.pi import PiBackend
from tests.fakes.pi_fake import PiFake, _mcp_comment_tool_event, _tool_execution_start

MODEL = "anthropic/claude-sonnet-4-5"


def _spec(**overrides) -> RunSpec:
    defaults = {
        "prompt": "test prompt",
        "cwd": "/tmp",
        "model": MODEL,
        "mode": "read_write",
        "timeout": 30,
        "state": {"_harness_cfg": {"backend": "pi", "model": MODEL}},
    }
    defaults.update(overrides)
    return RunSpec(**defaults)


def _resume_spec(session_id: str) -> RunSpec:
    return _spec(resume=session_id, mode="read_write")


def _fork_spec(source_id: str) -> RunSpec:
    return _spec(resume=source_id, fork_session=True, mode="read_write")


def _run(spec, fake):
    async def _inner():
        with fake:
            return await PiBackend().run(spec)

    return asyncio.run(_inner())


class TestPiFakeFidelity:
    """Feed PiFake JSONL through the real PiBackend and assert RunResult."""

    def test_success_run_result(self):
        """script_response success → RunResult with text, session_id, subtype=success."""
        fake = PiFake()
        fake.script_response("Changed 3 files.", session_id="pi-abc")

        result = _run(_spec(), fake)

        assert result.text == "Changed 3 files."
        assert result.session_id == "pi-abc"
        assert result.subtype == "success"
        assert result.ok is True

    def test_fix_run_result(self):
        """script_fix → success with the summary text."""
        fake = PiFake()
        fake.script_fix(summary="Applied the patch.")

        result = _run(_spec(), fake)

        assert result.text == "Applied the patch."
        assert result.subtype == "success"

    def test_error_run_result(self):
        """script_fail → in-stream error → subtype=error, session preserved."""
        fake = PiFake()
        fake.script_fail(session_id="pi-err", error_msg="quota exceeded")

        result = _run(_spec(), fake)

        assert result.subtype == "error"
        assert result.ok is False
        assert result.session_id == "pi-err"

    def test_killed_run_result(self):
        """script_killed → returncode -9 → subtype=killed."""
        fake = PiFake()
        fake.script_killed(session_id="pi-kill")

        result = _run(_spec(), fake)

        assert result.subtype == "killed"
        assert result.session_id == "pi-kill"

    def test_plan_tags_in_text(self):
        """script_plan preserves AUTOSWE_PLAN tags in the assistant text.

        pi has no native plan item, so plan capture is text-pattern driven:
        the tags live in RunResult.text for the planner to parse.
        """
        fake = PiFake()
        fake.script_plan("1. Fix login\n2. Add tests", session_id="pi-plan")

        result = _run(_spec(), fake)

        assert "<AUTOSWE_PLAN>" in result.text
        assert "Fix login" in result.text
        assert result.subtype == "success"

    def test_questions_tags_in_text(self):
        """script_questions preserves AUTOSWE_QUESTIONS tags in the text."""
        fake = PiFake()
        fake.script_questions("Which framework do you prefer?")

        result = _run(_spec(), fake)

        assert "<AUTOSWE_QUESTIONS>" in result.text
        assert "Which framework do you prefer?" in result.text
        assert result.subtype == "success"

    def test_cost_carried_through(self):
        """A scripted cost_total is reported (not estimated) on RunResult.cost_usd."""
        fake = PiFake()
        fake.script_response("ok", session_id="pi-cost", cost_total=1.25)

        result = _run(_spec(), fake)

        assert result.cost_usd == 1.25


# ---------- argv / call fidelity ----------


class TestPiFakeCalls:
    """Assert PiFake.records the pi command flags the real backend emitted."""

    def test_fresh_call_argv(self):
        """A fresh run emits --session-id, the model, tools, --approve."""
        fake = PiFake()
        fake.script_response("ok", session_id="pi-fresh")

        _run(_spec(mode="read_only"), fake)

        assert len(fake.calls) == 1
        call = fake.calls[0]
        assert call["is_fresh"] is True
        assert call["is_resume"] is False
        assert call["is_fork"] is False
        assert call["mode"] == "json"
        assert call["model"] == MODEL
        # read_only mode → the read-only tool recipe.
        assert call["tools"] == "read,grep,find,ls"
        # ask_question is always excluded.
        assert "ask_question" in call["exclude_tools"]
        # Project trust defaults to on.
        assert call["approve"] is True
        # Prompt is captured after the -- separator.
        assert call["prompt_prefix"]

    def test_read_write_tools(self):
        """mode=read_write emits the full working tool set (posix: no powershell)."""
        from unittest.mock import patch

        import autoswe.harness.backends.pi as pi_mod

        fake = PiFake()
        fake.script_response("ok")

        # Pin the host to posix so the emitted tool set is deterministic.
        with patch.object(pi_mod.os, "name", "posix"):
            _run(_spec(mode="read_write"), fake)

        tools = fake.calls[0]["tools"].split(",")
        assert "bash" in tools
        assert "edit" in tools
        assert "write" in tools
        assert "powershell" not in tools

    def test_resume_call_argv(self):
        """A resume emits --session <id> (not --session-id/--fork)."""
        fake = PiFake()
        fake.script_response("resumed", session_id="pi-resume")

        _run(_resume_spec("source-xyz"), fake)

        call = fake.calls[0]
        assert call["is_resume"] is True
        assert call["resume"] == "source-xyz"
        assert call["is_fresh"] is False
        assert "session_id" not in call
        assert "fork" not in call

    def test_fork_call_argv(self):
        """A fork emits --fork <source> AND a fresh --session-id (the new id)."""
        fake = PiFake()
        fake.script_response("forked", session_id="pi-fork")

        _run(_fork_spec("source-abc"), fake)

        call = fake.calls[0]
        assert call["is_fork"] is True
        assert call["fork"] == "source-abc"
        # A new session id is pinned (distinct from the source).
        assert call["session_id"]
        assert call["session_id"] != "source-abc"
        assert call["is_resume"] is False  # --session (resume) is not emitted

    def test_api_key_in_argv_not_env(self):
        """api_key is emitted as --api-key and NOT guessed into the env."""
        fake = PiFake()
        fake.script_response("ok")

        _run(_spec(state={"_harness_cfg": {
            "backend": "pi", "model": MODEL, "api_key": "sk-fake-key"}}), fake)

        call = fake.calls[0]
        assert call["api_key"] == "sk-fake-key"

    def test_system_prompt_flags(self):
        """--system-prompt / --append-system-prompt / --session-dir are recorded."""
        fake = PiFake()
        fake.script_response("ok")

        _run(_spec(state={"_harness_cfg": {
            "backend": "pi", "model": MODEL,
            "system_prompt": "Be terse.",
            "append_system_prompt": "More.",
            "session_dir": "/tmp/pisessions",
            "provider": "openai",
            "thinking": "high",
        }}), fake)

        call = fake.calls[0]
        assert call["system_prompt"] == "Be terse."
        assert call["append_system_prompt"] == "More."
        assert call["session_dir"] == "/tmp/pisessions"
        assert call["provider"] == "openai"
        assert call["thinking"] == "high"

    def test_approve_off_via_profile(self):
        """approve_project=False drops the --approve flag."""
        fake = PiFake()
        fake.script_response("ok")

        _run(_spec(state={"_harness_cfg": {
            "backend": "pi", "model": MODEL, "approve_project": False}}), fake)

        assert fake.calls[0]["approve"] is False

    def test_multiple_responses_consumed_in_order(self):
        """Multiple scripted responses are consumed in call order."""
        fake = PiFake()
        fake.script_response("one", session_id="s1")
        fake.script_response("two", session_id="s2")
        fake.script_fail(session_id="s3")
        spec = _spec()

        async def _run_many():
            with fake:
                backend = PiBackend()
                r1 = await backend.run(spec)
                r2 = await backend.run(spec)
                r3 = await backend.run(spec)
                return r1, r2, r3

        r1, r2, r3 = asyncio.run(_run_many())

        assert (r1.text, r1.session_id) == ("one", "s1")
        assert (r2.text, r2.session_id) == ("two", "s2")
        assert r3.subtype == "error" and r3.session_id == "s3"
        assert len(fake.calls) == 3

    def test_session_header_id_echoed(self):
        """The emitted session header id matches the scripted session id.

        Pins the fake's fidelity: the parser cross-checks the header against
        the pinned id, and a matching header leaves the result id unchanged.
        """
        fake = PiFake()
        fake.script_response("ok", session_id="echo-123")

        result = _run(_spec(), fake)

        assert result.session_id == "echo-123"


class TestPiFakeMcpFixtures:
    """Canonical ``tool_execution_start`` fixture shapes (Phase 0 spike).

    These pin the raw fixture lines PiFake emits for the three autoswe_comment
    tools — the shapes observed in the Phase 0 spike (spike-pi-mcp.md) that the
    real parser must classify.  If a fixture drifts from the observed
    ``--mode json`` shape, these fail before any RunResult assertion does.
    """

    def test_tool_execution_start_direct_shape(self):
        """The direct tool shape carries the body verbatim in args."""
        ev = _tool_execution_start("mcp__autoswe_comment_post_plan", "PLAN BODY")
        assert ev == {
            "type": "tool_execution_start",
            "toolCallId": "chatcmpl-tool-1",
            "toolName": "mcp__autoswe_comment_post_plan",
            "args": {"body": "PLAN BODY"},
        }

    def test_mcp_comment_tool_event_direct(self):
        """post_plan direct → fully-qualified toolName, body verbatim."""
        ev = _mcp_comment_tool_event("post_plan", "The plan", proxy="direct")
        assert ev["toolName"] == "mcp__autoswe_comment_post_plan"
        assert ev["args"] == {"body": "The plan"}
        assert ev["type"] == "tool_execution_start"

    def test_mcp_comment_tool_event_generic_proxy(self):
        """Generic `mcp` proxy → args = {tool, args: {body}}."""
        ev = _mcp_comment_tool_event("post_question", "Which DB?", proxy="generic")
        assert ev["toolName"] == "mcp"
        assert ev["args"] == {"tool": "post_question", "args": {"body": "Which DB?"}}

    def test_mcp_comment_tool_event_namespace_proxy(self):
        """Namespace proxy → toolName mcp__autoswe_comment, args = {tool, args: {body}}."""
        ev = _mcp_comment_tool_event("update_progress", "halfway", proxy="namespace")
        assert ev["toolName"] == "mcp__autoswe_comment"
        assert ev["args"] == {"tool": "update_progress", "args": {"body": "halfway"}}

    def test_mcp_comment_tool_event_empty_body(self):
        """An empty body still produces a well-formed event (suppression case)."""
        ev = _mcp_comment_tool_event("update_progress", "", proxy="direct")
        assert ev["args"] == {"body": ""}


class TestPiFakeMcpFidelity:
    """Feed PiFake MCP builders through the real PiBackend and assert RunResult.

    Pins the end-to-end path (PiFake → real parser → RunResult) for the three
    autoswe_comment tools: the tool_execution_start event drives the
    plan_posted / question_posted flags and the update_progress body drives the
    progress callback — the same contract the planner's has_mcp branch relies on.
    """

    def test_script_mcp_plan_sets_plan_posted(self):
        """script_mcp_plan → RunResult.plan_posted=True, text is tag-free."""
        fake = PiFake()
        fake.script_mcp_plan("The plan body.", session_id="pi-plan",
                             text="Posted the plan to the issue.")

        result = _run(_spec(), fake)

        assert result.plan_posted is True
        assert result.question_posted is False
        assert result.session_id == "pi-plan"
        assert result.text == "Posted the plan to the issue."
        # The post_plan body rides the RunResult so the planner can finalize
        # the sticky planning comment in place (issue #241) — must come out of
        # the genuine parser, not the fake.
        assert result.plan_posted_body == "The plan body."

    def test_script_mcp_plan_generic_proxy_sets_plan_posted(self):
        """The generic `mcp` proxy shape also drives plan_posted."""
        fake = PiFake()
        fake.script_mcp_plan("The plan body.", session_id="pi-plan-g",
                             proxy="generic")

        result = _run(_spec(), fake)

        assert result.plan_posted is True

    def test_script_mcp_plan_namespace_proxy_sets_plan_posted(self):
        """The mcp__autoswe_comment namespace proxy also drives plan_posted."""
        fake = PiFake()
        fake.script_mcp_plan("The plan body.", session_id="pi-plan-n",
                             proxy="namespace")

        result = _run(_spec(), fake)

        assert result.plan_posted is True

    def test_script_mcp_question_sets_question_posted(self):
        """script_mcp_question → RunResult.question_posted=True."""
        fake = PiFake()
        fake.script_mcp_question("Which framework?", session_id="pi-q")

        result = _run(_spec(), fake)

        assert result.question_posted is True
        assert result.plan_posted is False

    def test_script_mcp_update_progress_fires_progress_callback(self):
        """script_mcp_update_progress → the progress callback receives the body."""
        fake = PiFake()
        fake.script_mcp_update_progress("Running: pytest tests/",
                                        session_id="pi-p")

        lines: list[str] = []
        result = _run(_spec(progress_callback=lines.append), fake)

        assert any("Running: pytest tests/" in ln for ln in lines), (
            f"update_progress body must reach the progress callback; got {lines!r}"
        )
        # The body must NOT leak into the plan/question flags.
        assert result.plan_posted is False
        assert result.question_posted is False

    def test_script_mcp_update_progress_empty_body_fires_no_body_line(self):
        """An empty update_progress body fires no body progress line (suppression).

        Pins the AUTOSWE_SUPPRESS_POSTING boundary end-to-end: a minimal-posting
        server's empty body must not leak a blank progress line to the operator.
        """
        fake = PiFake()
        fake.script_mcp_update_progress("", session_id="pi-p-empty")

        lines: list[str] = []
        _run(_spec(progress_callback=lines.append), fake)

        # The generic "Tool:" line fires (a callback is present), but no empty
        # body-derived progress line is emitted.
        assert not any(ln == "" for ln in lines)
        assert any(ln.startswith("Tool: ") for ln in lines)
