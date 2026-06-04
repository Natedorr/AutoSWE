"""Fidelity guard — pins CodexFake to the real CodexBackend parser.

Feeds CodexFake-emitted JSONL through the real ``CodexBackend._run_async``
and asserts the resulting ``RunResult`` (text, session_id, subtype, cost).
This prevents the fake from silently drifting when the parser changes.
"""
from __future__ import annotations

import asyncio

from autoswe.harness.backends.base import RunSpec
from tests.fakes.codex_fake import CodexFake


def _make_spec(cwd: str = "/tmp") -> RunSpec:
    """Build a minimal RunSpec for testing."""
    return RunSpec(
        prompt="test prompt",
        cwd=cwd,
        model="gpt-5.4",
        resume=None,
        mode="read_only",
        extra_tools=[],
        max_turns=200,
        timeout=30,
        state={"_harness_cfg": {"backend": "codex", "model": "gpt-5.4"}},
    )


def _make_resume_spec(session_id: str, cwd: str = "/tmp") -> RunSpec:
    """Build a resume-mode RunSpec."""
    return RunSpec(
        prompt="resume prompt",
        cwd=cwd,
        model="gpt-5.4",
        resume=session_id,
        mode="read_write",
        extra_tools=[],
        max_turns=200,
        timeout=30,
        state={"_harness_cfg": {"backend": "codex", "model": "gpt-5.4"}},
    )


def _run_async(coro):
    """Run an async coroutine in the current event loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestCodexFakeFidelity:
    """Feed CodexFake JSONL through the real CodexBackend and assert RunResult."""

    def test_success_run_result(self):
        """CodexFake success response → RunResult with text, session_id, subtype=success."""
        fake = CodexFake()
        fake.script_response("Changed 3 files.", session_id="thread-abc", subtype="success")

        spec = _make_spec()
        from autoswe.harness.backends.codex import CodexBackend

        async def _run():
            with fake:
                backend = CodexBackend()
                return await backend.run(spec)

        result = _run_async(_run())

        assert result.text == "Changed 3 files."
        assert result.session_id == "thread-abc"
        assert result.subtype == "success"

    def test_error_run_result(self):
        """CodexFake error response → RunResult with subtype=error."""
        fake = CodexFake()
        fake.script_fail(session_id="thread-err", error_msg="max turns exceeded")

        spec = _make_spec()
        from autoswe.harness.backends.codex import CodexBackend

        async def _run():
            with fake:
                backend = CodexBackend()
                return await backend.run(spec)

        result = _run_async(_run())

        assert result.subtype == "error"
        assert result.session_id == "thread-err"

    def test_killed_run_result(self):
        """CodexFake killed response → RunResult with subtype=killed."""
        fake = CodexFake()
        fake.script_killed(session_id="thread-kill")

        spec = _make_spec()
        from autoswe.harness.backends.codex import CodexBackend

        async def _run():
            with fake:
                backend = CodexBackend()
                return await backend.run(spec)

        result = _run_async(_run())

        assert result.subtype == "killed"
        assert result.session_id == "thread-kill"

    def test_plan_tags_in_text(self):
        """CodexFake plan response preserves AUTOSWE_PLAN tags in text."""
        fake = CodexFake()
        fake.script_plan("1. Fix login\n2. Add tests", session_id="s-plan")

        spec = _make_spec()
        from autoswe.harness.backends.codex import CodexBackend

        async def _run():
            with fake:
                backend = CodexBackend()
                return await backend.run(spec)

        result = _run_async(_run())

        assert "<AUTOSWE_PLAN>" in result.text
        assert "Fix login" in result.text
        assert result.subtype == "success"

    def test_question_tags_in_text(self):
        """CodexFake questions response preserves AUTOSWE_QUESTIONS tags."""
        fake = CodexFake()
        fake.script_questions("What framework?", session_id="s-plan")

        spec = _make_spec()
        from autoswe.harness.backends.codex import CodexBackend

        async def _run():
            with fake:
                backend = CodexBackend()
                return await backend.run(spec)

        result = _run_async(_run())

        assert "<AUTOSWE_QUESTIONS>" in result.text
        assert "What framework?" in result.text
        assert result.subtype == "success"

    def test_sandbox_from_mode(self):
        """CodexFake records sandbox flag from mode translation."""
        fake = CodexFake()
        fake.script_response("ok", session_id="s1")

        spec = RunSpec(
            prompt="plan prompt",
            cwd="/tmp",
            model="gpt-5.4",
            resume=None,
            mode="plan",
            extra_tools=[],
            max_turns=200,
            timeout=30,
            state={"_harness_cfg": {"backend": "codex", "model": "gpt-5.4"}},
        )

        from autoswe.harness.backends.codex import CodexBackend

        async def _run():
            with fake:
                backend = CodexBackend()
                return await backend.run(spec)

        _run_async(_run())

        assert len(fake.calls) == 1
        call = fake.calls[0]
        assert call["sandbox"] == "read-only"
        assert not call["is_resume"]

    def test_read_write_sandbox(self):
        """mode='read_write' → sandbox='workspace-write'."""
        fake = CodexFake()
        fake.script_response("ok", session_id="s1")

        spec = RunSpec(
            prompt="fix prompt",
            cwd="/tmp",
            model="gpt-5.4",
            resume=None,
            mode="read_write",
            extra_tools=[],
            max_turns=200,
            timeout=30,
            state={"_harness_cfg": {"backend": "codex", "model": "gpt-5.4"}},
        )

        from autoswe.harness.backends.codex import CodexBackend

        async def _run():
            with fake:
                backend = CodexBackend()
                return await backend.run(spec)

        _run_async(_run())

        assert fake.calls[0]["sandbox"] == "workspace-write"

    def test_resume_mode(self):
        """Resume mode → call recorded with session_id, no sandbox."""
        fake = CodexFake()
        fake.script_response("resumed", session_id="s-resume")

        spec = _make_resume_spec("session-123")

        from autoswe.harness.backends.codex import CodexBackend

        async def _run():
            with fake:
                backend = CodexBackend()
                return await backend.run(spec)

        result = _run_async(_run())

        assert result.text == "resumed"
        assert result.session_id == "s-resume"
        assert len(fake.calls) == 1
        assert fake.calls[0]["is_resume"]
        assert fake.calls[0]["resume"] == "session-123"
        # Resume mode should NOT have sandbox
        assert "sandbox" not in fake.calls[0]

    def test_multiple_responses(self):
        """Multiple scripted responses are consumed in order."""
        fake = CodexFake()
        fake.script_response("first", session_id="s1")
        fake.script_response("second", session_id="s2")

        spec = _make_spec()
        from autoswe.harness.backends.codex import CodexBackend

        async def _run():
            with fake:
                backend = CodexBackend()
                r1 = await backend.run(spec)
                r2 = await backend.run(spec)
                return r1, r2

        r1, r2 = _run_async(_run())

        assert r1.text == "first"
        assert r1.session_id == "s1"
        assert r2.text == "second"
        assert r2.session_id == "s2"
