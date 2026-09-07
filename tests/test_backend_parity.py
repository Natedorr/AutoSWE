"""Backend parity contract — all three backends honor the same interface.

Mirrors the provider parity pattern (test_fake_parity.py, test_tracker_parity.py):
assert every CodingBackend implementation (claude_code, codex, pi) obeys the
RunSpec→RunResult contract and advertises honest capability sets.

Parity dimensions:
1. **Protocol conformance** — every class has ``capabilities()``,
   ``retryable_subtypes()`` and ``retryable_exceptions()`` and ``run()``.
2. **RunResult shape** — every backend returns the same dataclass, incl. the
   normalized ``ok`` flag (S6 / issue #169 F-10).
3. **Capability honesty** — advertised capabilities match what each backend
   actually supports (Claude = full feature set, Codex = resume + progress
   only, pi = mode + resume + session_fork + progress).
4. **Behavioral read-only** — a ``mode="plan"`` run cannot leave the worktree
   dirty, asserted the same way for EVERY backend (S6 / issue #169 F-21).
"""
from __future__ import annotations

import asyncio
import os
import subprocess
from dataclasses import asdict, fields
from unittest.mock import patch

import pytest

from autoswe.harness.backends.base import CodingBackend, RunResult, RunSpec

# ---------------------------------------------------------------------------
# 1. Protocol conformance
# ---------------------------------------------------------------------------

# The three backends held to the same contract. codex/pi are CLI backends that
# require a model in the profile; claude_code is SDK-based and takes none.
BACKENDS = ("claude_code", "codex", "pi")


def _harness_cfg(backend: str) -> dict:
    """A minimal valid harness profile for *backend* (what the factory needs)."""
    if backend == "codex":
        return {"backend": "codex", "model": "gpt-5.6-terra"}
    if backend == "pi":
        return {"backend": "pi", "model": "claude-sonnet-4-5"}
    return {"backend": "claude_code"}


def _backend_class(backend: str):
    """Return the backend class for a parity-axis name (via the factory's imports)."""
    if backend == "codex":
        from autoswe.harness.backends.codex import CodexBackend

        return CodexBackend
    if backend == "pi":
        from autoswe.harness.backends.pi import PiBackend

        return PiBackend
    from autoswe.harness.backends.claude_code import ClaudeCodeBackend

    return ClaudeCodeBackend


class TestProtocolConformance:
    """Every backend must satisfy the CodingBackend Protocol."""

    def test_claude_code_is_coding_backend(self):
        """ClaudeCodeBackend satisfies runtime_checkable CodingBackend."""
        from autoswe.harness.backends.claude_code import ClaudeCodeBackend

        backend = ClaudeCodeBackend()
        assert isinstance(backend, CodingBackend), (
            "ClaudeCodeBackend should satisfy CodingBackend Protocol"
        )

    def test_codex_is_coding_backend(self):
        """CodexBackend satisfies runtime_checkable CodingBackend."""
        from autoswe.harness.backends.codex import CodexBackend

        backend = CodexBackend()
        assert isinstance(backend, CodingBackend), (
            "CodexBackend should satisfy CodingBackend Protocol"
        )

    def test_pi_is_coding_backend(self):
        """PiBackend satisfies runtime_checkable CodingBackend."""
        from autoswe.harness.backends.pi import PiBackend

        backend = PiBackend()
        assert isinstance(backend, CodingBackend), (
            "PiBackend should satisfy CodingBackend Protocol"
        )

    @pytest.mark.parametrize("backend", BACKENDS)
    def test_have_capabilities_classmethod(self, backend):
        """Every backend exposes capabilities as a classmethod returning set."""
        cls = _backend_class(backend)
        assert hasattr(cls, "capabilities"), f"{cls.__name__} missing capabilities()"
        assert isinstance(cls.capabilities(), set), (
            f"{cls.__name__}.capabilities() must return a set"
        )

    @pytest.mark.parametrize("backend", BACKENDS)
    def test_have_retryable_exceptions_classmethod(self, backend):
        """Every backend exposes retryable_exceptions() returning a tuple.

        S6 / issue #169 F-09: the exception-based twin of
        ``retryable_subtypes()``.  Each backend declares its OWN retryable
        exception set; runner.run() must not hard-code Claude's tuple.
        """
        cls = _backend_class(backend)
        assert hasattr(cls, "retryable_exceptions"), (
            f"{cls.__name__} missing retryable_exceptions()"
        )
        ret = cls.retryable_exceptions()
        assert isinstance(ret, tuple), (
            f"{cls.__name__}.retryable_exceptions() must return a tuple"
        )
        for exc in ret:
            assert isinstance(exc, type) and issubclass(exc, BaseException), (
                f"{cls.__name__}.retryable_exceptions() yielded non-exception {exc!r}"
            )

    def test_codex_retryable_exceptions_are_its_own(self):
        """Codex retries on asyncio.TimeoutError / OSError, not on Claude's set.

        A backend-specific exception in Codex's own set should not be in
        Claude's set (and vice-versa for Claude's SDK exception types),
        proving the retry loop can pick the resolved backend's tuple
        without cross-contamination.
        """
        from autoswe.harness.backends.claude_code import ClaudeCodeBackend
        from autoswe.harness.backends.codex import CodexBackend

        codex_exc = CodexBackend.retryable_exceptions()
        claude_exc = ClaudeCodeBackend.retryable_exceptions()
        assert asyncio.TimeoutError in codex_exc
        assert OSError in codex_exc
        # Claude's exception set is SDK-specific and non-empty, distinct
        # from Codex's transport-level set (both non-empty, and they do not
        # share every member).
        assert len(claude_exc) > 0
        assert set(codex_exc) != set(claude_exc)

    @pytest.mark.parametrize("backend", BACKENDS)
    def test_have_run_method(self, backend):
        """Every backend has a run(spec) method returning an awaitable."""
        cls = _backend_class(backend)
        spec = RunSpec(prompt="test", cwd="/tmp")

        backend = cls()
        assert hasattr(backend, "run"), f"{cls.__name__} missing run()"
        assert callable(backend.run), f"{cls.__name__}.run not callable"
        coro = backend.run(spec)
        assert asyncio.iscoroutine(coro), (
            f"{cls.__name__}.run() must return an awaitable"
        )
        coro.close()

    @pytest.mark.parametrize("backend", BACKENDS)
    def test_capabilities_is_classmethod(self, backend):
        """capabilities() works on both the class and an instance."""
        cls = _backend_class(backend)
        class_caps = cls.capabilities()
        inst_caps = cls().capabilities()
        assert class_caps == inst_caps, (
            f"{cls.__name__}: class and instance capabilities() should match"
        )

    @pytest.mark.parametrize("backend", BACKENDS)
    def test_capabilities_returns_copy(self, backend):
        """capabilities() returns a copy so callers can't mutate shared state."""
        cls = _backend_class(backend)
        a = cls.capabilities()
        b = cls.capabilities()
        assert a is not b, "capabilities() should return a new set each call"
        a.add("__tamper__")
        assert "__tamper__" not in b

    @pytest.mark.parametrize("backend", BACKENDS)
    def test_have_comment_tool_names(self, backend):
        """Every backend exposes comment_tool_names() returning a role-keyed dict.

        Phase 3 (PLAN-pi-mcp.md): the single source of truth for MCP tool naming.
        The keys are the stable logical roles; the values are the full,
        backend-specific tool names the agent actually calls.
        """
        cls = _backend_class(backend)
        assert hasattr(cls, "comment_tool_names"), (
            f"{cls.__name__} missing comment_tool_names()"
        )
        names = cls.comment_tool_names()
        assert isinstance(names, dict), (
            f"{cls.__name__}.comment_tool_names() must return a dict"
        )
        expected_roles = {"post_plan", "post_question", "update_progress"}
        assert expected_roles <= set(names), (
            f"{cls.__name__}.comment_tool_names() missing roles: "
            f"{expected_roles - set(names)}"
        )
        for role, full in names.items():
            assert isinstance(full, str) and full, (
                f"{cls.__name__}.comment_tool_names()[{role!r}] must be a non-empty str"
            )

    @pytest.mark.parametrize("backend", BACKENDS)
    def test_comment_tool_names_returns_copy(self, backend):
        """comment_tool_names() returns a fresh dict so callers can't mutate it."""
        cls = _backend_class(backend)
        a = cls.comment_tool_names()
        b = cls.comment_tool_names()
        assert a is not b, "comment_tool_names() should return a new dict each call"
        a["__tamper__"] = "x"
        assert "__tamper__" not in b


# ---------------------------------------------------------------------------
# 1b. comment_tool_names value parity (Phase 3, PLAN-pi-mcp.md)
# ---------------------------------------------------------------------------


class TestCommentToolNamesParity:
    """Each backend names the autoswe_comment tools the way its adapter does.

    The names come from each backend's own allowlist constant, so the names the
    agent is granted, the names the stream parser matches, and the names the
    prompt references can never drift. This pins the *values* so a silent
    rename of an allowlist entry (which would break prompt rendering and/or
    stream detection) fails loudly here.
    """

    def test_claude_code_double_underscore_names(self):
        """Claude Code prefixes each tool with a double underscore."""
        from autoswe.harness.backends.claude_code import ClaudeCodeBackend

        assert ClaudeCodeBackend.comment_tool_names() == {
            "post_plan": "mcp__autoswe_comment__post_plan",
            "post_question": "mcp__autoswe_comment__post_question",
            "update_progress": "mcp__autoswe_comment__update_progress",
        }

    def test_pi_single_underscore_names(self):
        """pi's adapter uses toolPrefix 'mcp' + a single underscore."""
        from autoswe.harness.backends.pi import PiBackend

        assert PiBackend.comment_tool_names() == {
            "post_plan": "mcp__autoswe_comment_post_plan",
            "post_question": "mcp__autoswe_comment_post_question",
            "update_progress": "mcp__autoswe_comment_update_progress",
        }

    def test_codex_returns_claude_default(self):
        """Codex (no MCP) returns the Claude default so prompts render concretely."""
        from autoswe.harness.backends.base import CLAUDE_COMMENT_TOOL_NAMES
        from autoswe.harness.backends.codex import CodexBackend

        assert CodexBackend.comment_tool_names() == CLAUDE_COMMENT_TOOL_NAMES

    def test_pi_names_differ_from_claude(self):
        """The whole point of Phase 3: pi and Claude spell the names differently."""
        from autoswe.harness.backends.claude_code import ClaudeCodeBackend
        from autoswe.harness.backends.pi import PiBackend

        assert PiBackend.comment_tool_names() != ClaudeCodeBackend.comment_tool_names()

    def test_names_match_backend_allowlists(self):
        """The returned names must each be the backend's own allowlist spelling.

        Guards against the returned dict drifting from the allowlist constant the
        parser/allowlist actually use (the two must stay in lockstep).
        """
        from autoswe.harness.backends.claude_code import _MCP_COMMENT_TOOLS, ClaudeCodeBackend
        from autoswe.harness.backends.pi import _MCP_COMMENT_TOOL_NAMES, PiBackend

        assert set(ClaudeCodeBackend.comment_tool_names().values()) == set(_MCP_COMMENT_TOOLS)
        assert set(PiBackend.comment_tool_names().values()) == set(_MCP_COMMENT_TOOL_NAMES)

    def test_runner_dispatch_returns_backend_names(self):
        """runner.comment_tool_names() resolves through the factory per backend."""
        from autoswe.harness.runner import comment_tool_names

        assert comment_tool_names({"backend": "claude_code"})[
            "post_plan"
        ] == "mcp__autoswe_comment__post_plan"
        assert comment_tool_names(
            {"backend": "pi", "model": "claude-sonnet-4-5"}
        )["post_plan"] == "mcp__autoswe_comment_post_plan"

    def test_runner_dispatch_defaults_to_claude(self):
        """With no harness cfg, runner.comment_tool_names() gives the Claude default."""
        from autoswe.harness.backends.base import CLAUDE_COMMENT_TOOL_NAMES
        from autoswe.harness.runner import comment_tool_names

        assert comment_tool_names(None) == CLAUDE_COMMENT_TOOL_NAMES


# ---------------------------------------------------------------------------
# 2. RunResult shape parity
# ---------------------------------------------------------------------------


class TestRunResultShape:
    """Both backends must return RunResult with the same fields.

    The shared RunResult dataclass is the output contract.  Every backend
    returns an instance of the SAME dataclass, so the field set is identical
    by construction.  These tests verify that invariant explicitly.
    """

    def test_runresult_field_list(self):
        """RunResult has the expected set of fields."""
        expected = {
            "text", "session_id", "subtype", "cost_usd", "duration_seconds",
            "ok", "plan_file_path", "plan_posted", "question_posted", "plan_text",
            "structured_output",
        }
        actual = {f.name for f in fields(RunResult)}
        assert actual == expected, f"RunResult fields drifted: {actual ^ expected}"

    def test_runresult_default_values(self):
        """RunResult optional fields have sensible defaults."""
        r = RunResult(text="", session_id=None, subtype=None)
        assert r.cost_usd is None
        assert r.duration_seconds == 0.0
        assert r.plan_file_path is None
        assert r.plan_posted is False
        assert r.question_posted is False
        assert r.structured_output is None

    def test_runresult_ok_resolved_from_subtype(self):
        """When ``ok`` is not set, it falls back to subtype == 'success'."""
        assert RunResult(text="", session_id=None, subtype="success").ok is True
        assert RunResult(text="", session_id=None, subtype="error_max_turns").ok is False
        assert RunResult(text="", session_id=None, subtype=None).ok is False

    def test_runresult_ok_explicit_override(self):
        """An explicit ``ok`` wins over the subtype-derived default."""
        r = RunResult(text="", session_id=None, subtype="error_max_turns", ok=True)
        assert r.ok is True

    def test_runresult_tuple_unpacking(self):
        """RunResult supports tuple-style 3-element unpacking (back-compat)."""
        r = RunResult(
            text="hello",
            session_id="s1",
            subtype="success",
            cost_usd=0.01,
            duration_seconds=5.0,
        )
        text, session_id, subtype = r
        assert text == "hello"
        assert session_id == "s1"
        assert subtype == "success"

    def test_runresult_asdict_keys(self):
        """RunResult.asdict() produces the expected key set."""
        r = RunResult(
            text="t", session_id="s", subtype="success",
            cost_usd=0.1, duration_seconds=2.0,
        )
        d = asdict(r)
        expected_keys = {f.name for f in fields(RunResult)}
        assert set(d.keys()) == expected_keys


# ---------------------------------------------------------------------------
# 3. RunSpec compatibility
# ---------------------------------------------------------------------------


class TestRunSpecCompatibility:
    """Both backends must accept the same RunSpec without special-casing."""

    @pytest.mark.parametrize("backend", BACKENDS)
    def test_accept_minimal_spec(self, backend):
        """A spec with only prompt+cwd is valid for every backend."""
        cls = _backend_class(backend)
        spec = RunSpec(prompt="do the thing", cwd="/tmp")

        backend_obj = cls()
        coro = backend_obj.run(spec)
        assert asyncio.iscoroutine(coro)
        coro.close()

    @pytest.mark.parametrize("backend", BACKENDS)
    def test_accept_full_spec(self, backend):
        """A fully-populated RunSpec is accepted by every backend."""
        cls = _backend_class(backend)

        spec = RunSpec(
            prompt="implement feature",
            cwd="/tmp/repo",
            model="test-model",
            resume=None,
            mode="read_write",
            max_turns=100,
            timeout=300,
            env_overrides={"TEST_KEY": "test_val"},
            progress_callback=lambda x: None,
            state={"_harness_cfg": _harness_cfg(backend)},
        )

        backend_obj = cls()
        coro = backend_obj.run(spec)
        assert asyncio.iscoroutine(coro)
        coro.close()

    @pytest.mark.parametrize("backend", BACKENDS)
    def test_accept_resume_spec(self, backend):
        """A resume spec (session_id set) is accepted by every backend."""
        cls = _backend_class(backend)

        spec = RunSpec(
            prompt="continue",
            cwd="/tmp/repo",
            resume="session-abc-123",
            mode="read_write",
        )

        backend_obj = cls()
        coro = backend_obj.run(spec)
        assert asyncio.iscoroutine(coro)
        coro.close()

    @pytest.mark.parametrize("backend", BACKENDS)
    def test_accept_all_modes(self, backend):
        """All three mode values are accepted without raising."""
        cls = _backend_class(backend)

        for mode in ("plan", "read_only", "read_write"):
            spec = RunSpec(prompt="test", cwd="/tmp", mode=mode)
            backend_obj = cls()
            coro = backend_obj.run(spec)
            assert asyncio.iscoroutine(coro), (
                f"{cls.__name__} rejected mode={mode!r}"
            )
            coro.close()


# ---------------------------------------------------------------------------
# 4. Capability honesty
# ---------------------------------------------------------------------------


class TestCapabilityHonesty:
    """Each backend must advertise exactly the capabilities it supports.

    Claude Code = full feature set.
    Codex (Phase 4) = resume + progress_stream only.
    pi = mode + resume + session_fork + progress_stream.

    These tests encode the expected capability matrix so that when a backend
    gains or loses a capability, the test failure makes the drift obvious.
    """

    # Canonical capability universe (add here as new capabilities are defined)
    ALL_CAPABILITIES = frozenset({
        "mode",
        "mcp",
        "can_use_tool",
        "plan_permission",
        "resume",
        "session_fork",
        "progress_stream",
        "plan_file",
        "structured_output",
    })

    def test_claude_code_full_capabilities(self):
        """Claude Code advertises the complete capability set."""
        from autoswe.harness.backends.claude_code import ClaudeCodeBackend

        caps = ClaudeCodeBackend.capabilities()
        expected = {
            "mode", "mcp", "can_use_tool", "plan_permission",
            "resume", "session_fork", "progress_stream", "plan_file",
            "structured_output",
        }
        assert caps == expected, (
            f"ClaudeCodeBackend capabilities changed: got {caps}"
        )
        assert caps.issubset(self.ALL_CAPABILITIES), (
            "ClaudeCodeBackend advertises unknown capability"
        )

    def test_codex_phase4_capabilities(self):
        """Codex (Phase 4) advertises resume + progress_stream only.

        No "mode" (issue #166): Codex accepts RunSpec.mode for contract
        parity but performs no read-only enforcement, so it must not claim
        the capability. Plan/review rely on the post-run worktree backstop.
        """
        from autoswe.harness.backends.codex import CodexBackend

        caps = CodexBackend.capabilities()
        expected = {"resume", "progress_stream"}
        assert caps == expected, (
            f"CodexBackend capabilities changed: got {caps}"
        )
        assert "mode" not in caps, (
            "Codex must not advertise 'mode' without read-only enforcement (issue #166)"
        )
        assert caps.issubset(self.ALL_CAPABILITIES), (
            "CodexBackend advertises unknown capability"
        )

    def test_pi_capabilities(self):
        """PiBackend advertises mode + resume + session_fork + progress_stream + mcp.

        pi does REAL read-only enforcement via the ``--tools`` allowlist
        derived from RunSpec.mode (so it claims "mode", unlike Codex), and it
        has a fork primitive (``--fork``) that Codex lacks.  Phase 2 adds the
        "mcp" capability: pi reaches the autoswe_comment server through the
        pi-mcp-adapter and parses its tool_execution_start events into the
        RunResult.plan_posted / question_posted flags.  It still has no
        per-tool approval callback (``ask_question`` is excluded) and no
        plan-file / structured-output support.
        """
        from autoswe.harness.backends.pi import PiBackend

        caps = PiBackend.capabilities()
        expected = {"mode", "resume", "session_fork", "progress_stream", "mcp"}
        assert caps == expected, (
            f"PiBackend capabilities changed: got {caps}"
        )
        assert caps.issubset(self.ALL_CAPABILITIES), (
            "PiBackend advertises unknown capability"
        )

    def test_pi_lacks_mcp_and_claude_exclusives(self):
        """pi must NOT advertise capabilities it doesn't support.

        "mcp" is now supported (Phase 2) and therefore absent from this set;
        the remaining Claude-exclusive capabilities stay unsupported.
        """
        from autoswe.harness.backends.pi import PiBackend

        caps = PiBackend.capabilities()
        # No per-tool approval (ask_question is excluded in --mode json), no
        # plan-file or structured-output support.  "mcp" is now advertised.
        unsupported = {"can_use_tool", "plan_permission", "plan_file",
                       "structured_output"}
        overlap = caps & unsupported
        assert not overlap, (
            f"PiBackend advertises unsupported capabilities: {overlap}. "
            "Update this test when pi gains the capability."
        )

    def test_codex_lacks_claude_exclusives(self):
        """Codex must NOT advertise capabilities it doesn't support yet."""
        from autoswe.harness.backends.codex import CodexBackend

        caps = CodexBackend.capabilities()
        # Phase 4: Codex does NOT support these. 'mode' is Claude-exclusive
        # (issue #166): Codex accepts RunSpec.mode for contract parity but has
        # no read-only enforcement, so it must not claim the capability.
        # session_fork is Claude-exclusive: Codex has no fork primitive (resume in place or fresh).
        claude_exclusives = {
            "mode", "mcp", "can_use_tool", "plan_permission",
            "plan_file", "session_fork",
        }
        overlap = caps & claude_exclusives
        assert not overlap, (
            f"Codex advertises Claude-exclusive capabilities: {overlap}. "
            "Update this test when Codex gains the capability."
        )

    @pytest.mark.parametrize("backend", BACKENDS)
    def test_share_resume_and_progress(self, backend):
        """Every backend shares at least resume + progress_stream."""
        cls = _backend_class(backend)
        caps = cls.capabilities()
        assert "resume" in caps, f"{cls.__name__} should support resume"
        assert "progress_stream" in caps, (
            f"{cls.__name__} should support progress_stream"
        )

    @pytest.mark.parametrize("backend", BACKENDS)
    def test_no_stray_capabilities(self, backend):
        """No backend advertises a capability outside the known universe."""
        cls = _backend_class(backend)
        stray = cls.capabilities() - self.ALL_CAPABILITIES
        assert not stray, (
            f"{cls.__name__} advertises unknown capabilities: {stray}. "
            "Add them to ALL_CAPABILITIES in this test."
        )


# ---------------------------------------------------------------------------
# 4b. Retryable-subtypes parity
# ---------------------------------------------------------------------------


class TestRetryableSubtypesParity:
    """Each backend must implement retryable_subtypes() with the correct contract."""

    @pytest.mark.parametrize("backend", BACKENDS)
    def test_have_retryable_subtypes(self, backend):
        """Every backend exposes retryable_subtypes as a classmethod."""
        cls = _backend_class(backend)
        assert hasattr(cls, "retryable_subtypes"), (
            f"{cls.__name__} missing retryable_subtypes()"
        )
        result = cls.retryable_subtypes()
        assert isinstance(result, set), (
            f"{cls.__name__}.retryable_subtypes() must return a set"
        )

    def test_claude_retryable_subtypes_is_empty(self):
        """ClaudeCodeBackend.retryable_subtypes() returns empty (uses exceptions)."""
        from autoswe.harness.backends.claude_code import ClaudeCodeBackend

        assert ClaudeCodeBackend.retryable_subtypes() == set()

    def test_codex_retryable_subtypes(self):
        """CodexBackend.retryable_subtypes() returns {'error', 'killed'}."""
        from autoswe.harness.backends.codex import CodexBackend

        result = CodexBackend.retryable_subtypes()
        assert result == {"error", "killed"}, (
            f"CodexBackend.retryable_subtypes() changed: got {result}"
        )

    def test_pi_retryable_subtypes(self):
        """PiBackend.retryable_subtypes() returns {'error', 'killed'}.

        Same CLI-subprocess failure surface as Codex: a nonzero / in-stream
        error exits as subtype 'error', a signal kill as 'killed' — both
        retryable by the runner.
        """
        from autoswe.harness.backends.pi import PiBackend

        result = PiBackend.retryable_subtypes()
        assert result == {"error", "killed"}, (
            f"PiBackend.retryable_subtypes() changed: got {result}"
        )

    @pytest.mark.parametrize("backend", BACKENDS)
    def test_retryable_subtypes_returns_copy(self, backend):
        """retryable_subtypes() must return a copy so callers can't mutate state."""
        cls = _backend_class(backend)
        a = cls.retryable_subtypes()
        b = cls.retryable_subtypes()
        assert a is not b, f"{cls.__name__}.retryable_subtypes() must return a new set"
        a.add("__tamper__")
        assert "__tamper__" not in b


# ---------------------------------------------------------------------------
# 5. Factory + dispatcher integration parity
# ---------------------------------------------------------------------------


class TestFactoryParity:
    """Factory returns backends that pass the Protocol check."""

    def test_factory_claude_code_is_backend(self):
        """Factory claude_code backend satisfies CodingBackend."""
        from autoswe.harness.backends.factory import get_backend

        backend = get_backend({"backend": "claude_code"})
        assert isinstance(backend, CodingBackend)

    def test_factory_codex_is_backend(self):
        """Factory codex backend satisfies CodingBackend."""
        from autoswe.harness.backends.factory import get_backend

        backend = get_backend({"backend": "codex", "model": "gpt-5.6-terra"})
        assert isinstance(backend, CodingBackend)

    def test_factory_pi_is_backend(self):
        """Factory pi backend satisfies CodingBackend."""
        from autoswe.harness.backends.factory import get_backend

        backend = get_backend({"backend": "pi", "model": "claude-sonnet-4-5"})
        assert isinstance(backend, CodingBackend)

    def test_factory_default_is_claude_code(self):
        """Missing backend key defaults to claude_code."""
        from autoswe.harness.backends.claude_code import ClaudeCodeBackend
        from autoswe.harness.backends.factory import get_backend

        backend = get_backend({})
        assert isinstance(backend, ClaudeCodeBackend)

    @pytest.mark.parametrize("backend", BACKENDS)
    def test_factory_backends_return_runresult(self, backend):
        """Factory-produced backends accept RunSpec and return coroutine."""
        from autoswe.harness.backends.factory import get_backend

        backend_obj = get_backend(_harness_cfg(backend))
        spec = RunSpec(prompt="test", cwd="/tmp")
        coro = backend_obj.run(spec)
        assert asyncio.iscoroutine(coro), (
            f"Factory backend '{backend}' should return awaitable"
        )
        coro.close()


# ---------------------------------------------------------------------------
# 6. Runner dispatcher parity
# ---------------------------------------------------------------------------


class TestRunnerDispatcherParity:
    """runner.run() routes correctly for all backends."""

    def test_runner_backend_has_capability_claude(self):
        """backend_has_capability returns True for Claude features."""
        from autoswe.harness.runner import backend_has_capability

        harness = {"backend": "claude_code"}
        assert backend_has_capability(harness, "mode")
        assert backend_has_capability(harness, "mcp")
        assert backend_has_capability(harness, "resume")

    def test_runner_backend_has_capability_codex(self):
        """backend_has_capability returns correct values for Codex."""
        from autoswe.harness.runner import backend_has_capability

        harness = {"backend": "codex", "model": "gpt-5.6-terra"}
        # No "mode" (issue #166): Codex has no read-only enforcement.
        assert not backend_has_capability(harness, "mode")
        assert not backend_has_capability(harness, "mcp")
        assert not backend_has_capability(harness, "can_use_tool")
        assert not backend_has_capability(harness, "plan_permission")
        assert backend_has_capability(harness, "resume")
        assert backend_has_capability(harness, "progress_stream")

    def test_runner_backend_has_capability_pi(self):
        """backend_has_capability returns correct values for pi.

        pi advertises "mode" (real --tools allowlist enforcement) and
        "session_fork" (--fork) — both gaps Codex leaves open — plus
        resume + progress_stream + mcp (Phase 2).  It has no per-tool approval.
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

    def test_runner_backend_has_capability_unknown(self):
        """backend_has_capability handles unknown capability gracefully."""
        from autoswe.harness.runner import backend_has_capability

        harness = {"backend": "claude_code"}
        # Unknown capability — should return False, not crash
        assert not backend_has_capability(harness, "imaginary_feature")


# ---------------------------------------------------------------------------
# 7. Mode translation parity (each backend maps mode correctly)
# ---------------------------------------------------------------------------


class TestModeTranslationParity:
    """Each backend translates RunSpec.mode to its own config correctly.

    Claude Code: mode → permission_mode + tool lists.
    Codex: mode is accepted for contract parity but no longer maps to a
    ``--sandbox`` flag (issue #129 — the per-mode sandbox was dead weight,
    neutralized by the always-on bypass flag).
    pi: mode → a real ``--tools`` allowlist (the only CLI backend with
    genuine read-only enforcement).

    All three must handle all three modes without raising.
    """

    def test_claude_mode_config_coverage(self):
        """ClaudeCodeBackend _MODE_CONFIG covers all three modes."""
        from autoswe.harness.backends.claude_code import _MODE_CONFIG

        for mode in ("plan", "read_only", "read_write"):
            assert mode in _MODE_CONFIG, (
                f"ClaudeCodeBackend missing mode translation for {mode!r}"
            )
            perm, tools, disallowed = _MODE_CONFIG[mode]
            assert isinstance(perm, str), f"permission_mode for {mode!r} should be str"
            assert isinstance(tools, (list, tuple)), f"allowed_tools for {mode!r} should be iterable"
            assert isinstance(disallowed, (list, tuple)), (
                f"disallowed_tools for {mode!r} should be iterable"
            )
            assert len(tools) > 0, f"allowed_tools for {mode!r} should not be empty"

    def test_codex_has_no_sandbox_mapping(self):
        """Since issue #129 Codex no longer maps mode → --sandbox.

        The per-mode sandbox mapping was dead weight (the always-on bypass
        flag neutralized it). Confirm the module no longer exposes a
        mode→sandbox table or helper.
        """
        import autoswe.harness.backends.codex as codex_mod

        assert not hasattr(codex_mod, "_MODE_SANDBOX")
        assert not hasattr(codex_mod, "_mode_to_sandbox")

    def test_pi_mode_tools_coverage(self):
        """PiBackend _MODE_TOOLS covers all three modes with real enforcement.

        Unlike Codex, pi translates mode into a real ``--tools`` allowlist:
        plan/read_only get the documented read-only recipe, read_write gets
        the full working set, and ask_question is excluded from every allowlist
        (a non-interactive run would block on it — there is no per-tool
        approval in --mode json).
        """
        from autoswe.harness.backends.pi import _MODE_TOOLS, _tools_for_spec

        for mode in ("plan", "read_only", "read_write"):
            assert mode in _MODE_TOOLS, (
                f"PiBackend missing mode translation for {mode!r}"
            )
            tools = _MODE_TOOLS[mode]
            assert len(tools) > 0, f"--tools allowlist for {mode!r} should not be empty"
            assert "ask_question" not in tools, (
                f"ask_question must never be allowed (mode={mode!r})"
            )

        # plan and read_only must be the same read-only recipe (no write/bash).
        assert set(_MODE_TOOLS["plan"]) == set(_MODE_TOOLS["read_only"])
        read_only_set = set(_MODE_TOOLS["plan"])
        assert not ({"bash", "edit", "write"} & read_only_set), (
            "plan/read_only allowlist must exclude write-capable tools"
        )
        read_write_set = set(_MODE_TOOLS["read_write"])
        assert {"edit", "write", "bash"} <= read_write_set, (
            "read_write allowlist must include write-capable tools"
        )

        # spec.mode feeds the allowlist; an unset mode falls back to read_write.
        assert _tools_for_spec(RunSpec(prompt="p", cwd="/tmp", mode="plan")) == \
            list(_MODE_TOOLS["plan"])
        assert _tools_for_spec(RunSpec(prompt="p", cwd="/tmp", mode="read_only")) == \
            list(_MODE_TOOLS["read_only"])
        assert _tools_for_spec(RunSpec(prompt="p", cwd="/tmp", mode="read_write")) == \
            list(_MODE_TOOLS["read_write"])
        assert _tools_for_spec(RunSpec(prompt="p", cwd="/tmp")) == \
            list(_MODE_TOOLS["read_write"])


# ---------------------------------------------------------------------------
# 8. Behavioral read-only guarantee (S6 / issue #169 F-21)
# ---------------------------------------------------------------------------


def _make_real_git_repo(root, file_content="hello\n"):
    """Initialize a real git repo at *root* with one committed file.

    Returns the committed HEAD SHA.
    """
    root.joinpath("README.md").write_text(file_content, encoding="utf-8")
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@e",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@e", "GIT_EDITOR": ":"}

    def git(*args):
        subprocess.run(
            ["git", "-C", str(root), *args],
            check=True, capture_output=True, text=True, env=env,
        )

    git("init", "-q", "-b", "master")
    git("add", "README.md")
    git("commit", "-q", "-m", "init")
    return subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def _worktree_porcelain(root):
    """Return git status --porcelain output for *root*."""
    return subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain"],
        capture_output=True, text=True, check=True,
    ).stdout


class TestReadOnlyBehavioralParity:
    """The behavioral read-only guarantee, asserted identically on all backends.

    S6 / issue #169 F-21: no test previously asserted the *behavioral*
    property that a ``mode="plan"`` run cannot write to the worktree.  This
    is the single canonical copy of that assertion (previously duplicated in
    test_planner_readonly.py); it runs against every backend because the
    backstop — ``ensure_worktree_unchanged`` — is the actual guarantee and
    runs regardless of which backend performed the (unforced) read-only phase.
    """

    @pytest.mark.parametrize("backend", ["codex", "claude_code", "pi"])
    def test_plan_run_cannot_write_to_worktree(self, backend, tmp_path, mock_gh_post_comment):
        """A mode="plan" run must not leave the worktree dirty, on either backend.

        We simulate an agent that edits a file WITHOUT committing (the normal
        case a HEAD-only compare misses) by having the fake ``runner.run``
        write an untracked file into a REAL git worktree, then assert the real
        ``ensure_worktree_unchanged`` backstop rolled it back.
        """
        wt = tmp_path / "wt"
        wt.mkdir()
        head = _make_real_git_repo(wt)

        # Prove the worktree starts clean.
        assert _worktree_porcelain(wt) == ""

        def fake_run(prompt, **kwargs):
            # The agent edited a file but did not commit → worktree dirty, HEAD same.
            assert kwargs["mode"] == "plan"
            (wt / "agent_edit.py").write_text("x = 1\n", encoding="utf-8")
            from autoswe.harness.runner import RunResult
            return RunResult("<AUTOSWE_PLAN>\nPlan\n</AUTOSWE_PLAN>", "sess", "success")

        task = {
            "id": "o_r_1", "owner": "o", "repo": "r", "issue_number": 1,
            "title": "Test", "body": "/plan", "base_branch": "master",
            "session_id": None, "_token": "ghp_fake",
        }
        if backend == "codex":
            harness = {"backend": "codex", "model": "gpt-5.6-terra"}
        elif backend == "pi":
            harness = {"backend": "pi", "model": "claude-sonnet-4-5"}
        else:
            harness = {"backend": "claude_code"}

        with patch("autoswe.harness.planner.create_worktree", return_value=wt):
            with patch("autoswe.harness.planner._find_latest_plan_file", return_value=None):
                with patch("autoswe.tracking.api._fetch_comments", return_value=[]):
                    with patch(
                        "autoswe.harness.planner.resolve_harness", return_value=harness
                    ):
                        with patch("autoswe.harness.runner.run", side_effect=fake_run):
                            from autoswe.harness.planner import run_plan
                            run_plan(task, {}, {"GITHUB_TOKEN": "tok"})

        # The agent's uncommitted edit must have been rolled back — worktree clean.
        assert _worktree_porcelain(wt) == "", (
            f"[{backend}] plan run left the worktree dirty; backstop should roll back"
        )
        assert not (wt / "agent_edit.py").exists(), "agent edit must be removed"
        # HEAD is unchanged
        assert subprocess.run(
            ["git", "-C", str(wt), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip() == head
