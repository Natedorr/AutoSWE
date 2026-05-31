"""Backend parity contract — Claude Code vs Codex honor the same interface.

Mirrors the provider parity pattern (test_fake_parity.py, test_tracker_parity.py):
assert both CodingBackend implementations obey the RunSpec→RunResult contract
and advertise honest capability sets.

Three parity dimensions:
1. **Protocol conformance** — both classes have ``capabilities()`` and ``run()``.
2. **RunResult shape** — both backends return dataclasses with identical fields.
3. **Capability honesty** — advertised capabilities match what each backend
   actually supports (Claude = full feature set, Codex = resume + progress only).
"""
from __future__ import annotations

import asyncio
from dataclasses import asdict, fields

from autoswe.harness.backends.base import CodingBackend, RunResult, RunSpec

# ---------------------------------------------------------------------------
# 1. Protocol conformance
# ---------------------------------------------------------------------------


class TestProtocolConformance:
    """Both backends must satisfy the CodingBackend Protocol."""

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

    def test_both_have_capabilities_classmethod(self):
        """Both backends expose capabilities as a classmethod returning set."""
        from autoswe.harness.backends.claude_code import ClaudeCodeBackend
        from autoswe.harness.backends.codex import CodexBackend

        for cls in (ClaudeCodeBackend, CodexBackend):
            assert hasattr(cls, "capabilities"), f"{cls.__name__} missing capabilities()"
            assert isinstance(cls.capabilities(), set), (
                f"{cls.__name__}.capabilities() must return a set"
            )

    def test_both_have_run_method(self):
        """Both backends have a run(spec) method returning an awaitable."""
        from autoswe.harness.backends.claude_code import ClaudeCodeBackend
        from autoswe.harness.backends.codex import CodexBackend

        spec = RunSpec(prompt="test", cwd="/tmp")

        for cls in (ClaudeCodeBackend, CodexBackend):
            backend = cls()
            assert hasattr(backend, "run"), f"{cls.__name__} missing run()"
            assert callable(backend.run), f"{cls.__name__}.run not callable"
            coro = backend.run(spec)
            assert asyncio.iscoroutine(coro), (
                f"{cls.__name__}.run() must return an awaitable"
            )
            coro.close()

    def test_capabilities_is_classmethod(self):
        """capabilities() works on both the class and an instance."""
        from autoswe.harness.backends.claude_code import ClaudeCodeBackend
        from autoswe.harness.backends.codex import CodexBackend

        for cls in (ClaudeCodeBackend, CodexBackend):
            class_caps = cls.capabilities()
            inst_caps = cls().capabilities()
            assert class_caps == inst_caps, (
                f"{cls.__name__}: class and instance capabilities() should match"
            )

    def test_capabilities_returns_copy(self):
        """capabilities() returns a copy so callers can't mutate shared state."""
        from autoswe.harness.backends.claude_code import ClaudeCodeBackend
        from autoswe.harness.backends.codex import CodexBackend

        for cls in (ClaudeCodeBackend, CodexBackend):
            a = cls.capabilities()
            b = cls.capabilities()
            assert a is not b, "capabilities() should return a new set each call"
            a.add("__tamper__")
            assert "__tamper__" not in b


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
            "plan_file_path", "plan_posted", "question_posted",
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

    def test_runresult_tuple_unpacking(self):
        """RunResult supports tuple-style 3-element unpacking (back-compat)."""
        r = RunResult(
            text="hello",
            session_id="s1",
            subtype="success",
            cost_usd=0.01,
            duration_seconds=5.0,
        )
        text, session_id, subtype = r  # noqa: FAB319 (intentional unpacking test)
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

    def test_both_accept_minimal_spec(self):
        """A spec with only prompt+cwd is valid for both backends."""
        from autoswe.harness.backends.claude_code import ClaudeCodeBackend
        from autoswe.harness.backends.codex import CodexBackend

        spec = RunSpec(prompt="do the thing", cwd="/tmp")

        for cls in (ClaudeCodeBackend, CodexBackend):
            backend = cls()
            coro = backend.run(spec)
            assert asyncio.iscoroutine(coro)
            coro.close()

    def test_both_accept_full_spec(self):
        """A fully-populated RunSpec is accepted by both backends."""
        from autoswe.harness.backends.claude_code import ClaudeCodeBackend
        from autoswe.harness.backends.codex import CodexBackend

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
            state={"_harness_cfg": {}},
        )

        for cls in (ClaudeCodeBackend, CodexBackend):
            backend = cls()
            coro = backend.run(spec)
            assert asyncio.iscoroutine(coro)
            coro.close()

    def test_both_accept_resume_spec(self):
        """A resume spec (session_id set) is accepted by both backends."""
        from autoswe.harness.backends.claude_code import ClaudeCodeBackend
        from autoswe.harness.backends.codex import CodexBackend

        spec = RunSpec(
            prompt="continue",
            cwd="/tmp/repo",
            resume="session-abc-123",
            mode="read_write",
        )

        for cls in (ClaudeCodeBackend, CodexBackend):
            backend = cls()
            coro = backend.run(spec)
            assert asyncio.iscoroutine(coro)
            coro.close()

    def test_both_accept_all_modes(self):
        """All three mode values are accepted without raising."""
        from autoswe.harness.backends.claude_code import ClaudeCodeBackend
        from autoswe.harness.backends.codex import CodexBackend

        for mode in ("plan", "read_only", "read_write"):
            spec = RunSpec(prompt="test", cwd="/tmp", mode=mode)
            for cls in (ClaudeCodeBackend, CodexBackend):
                backend = cls()
                coro = backend.run(spec)
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
        "progress_stream",
    })

    def test_claude_code_full_capabilities(self):
        """Claude Code advertises the complete capability set."""
        from autoswe.harness.backends.claude_code import ClaudeCodeBackend

        caps = ClaudeCodeBackend.capabilities()
        expected = {
            "mode", "mcp", "can_use_tool", "plan_permission",
            "resume", "progress_stream",
        }
        assert caps == expected, (
            f"ClaudeCodeBackend capabilities changed: got {caps}"
        )
        assert caps.issubset(self.ALL_CAPABILITIES), (
            "ClaudeCodeBackend advertises unknown capability"
        )

    def test_codex_phase4_capabilities(self):
        """Codex (Phase 4) advertises resume + progress_stream only."""
        from autoswe.harness.backends.codex import CodexBackend

        caps = CodexBackend.capabilities()
        expected = {"resume", "progress_stream"}
        assert caps == expected, (
            f"CodexBackend capabilities changed: got {caps}"
        )
        assert caps.issubset(self.ALL_CAPABILITIES), (
            "CodexBackend advertises unknown capability"
        )

    def test_codex_lacks_claude_exclusives(self):
        """Codex must NOT advertise capabilities it doesn't support yet."""
        from autoswe.harness.backends.codex import CodexBackend

        caps = CodexBackend.capabilities()
        # Phase 4: Codex does NOT support these
        claude_exclusives = {"mode", "mcp", "can_use_tool", "plan_permission"}
        overlap = caps & claude_exclusives
        assert not overlap, (
            f"Codex advertises Claude-exclusive capabilities: {overlap}. "
            "Update this test when Codex gains the capability."
        )

    def test_both_share_resume_and_progress(self):
        """Both backends share at least resume + progress_stream."""
        from autoswe.harness.backends.claude_code import ClaudeCodeBackend
        from autoswe.harness.backends.codex import CodexBackend

        shared = ClaudeCodeBackend.capabilities() & CodexBackend.capabilities()
        assert "resume" in shared, "Both backends should support resume"
        assert "progress_stream" in shared, "Both backends should support progress_stream"

    def test_no_stray_capabilities(self):
        """No backend advertises a capability outside the known universe."""
        from autoswe.harness.backends.claude_code import ClaudeCodeBackend
        from autoswe.harness.backends.codex import CodexBackend

        for cls in (ClaudeCodeBackend, CodexBackend):
            stray = cls.capabilities() - self.ALL_CAPABILITIES
            assert not stray, (
                f"{cls.__name__} advertises unknown capabilities: {stray}. "
                "Add them to ALL_CAPABILITIES in this test."
            )


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

        backend = get_backend({"backend": "codex"})
        assert isinstance(backend, CodingBackend)

    def test_factory_default_is_claude_code(self):
        """Missing backend key defaults to claude_code."""
        from autoswe.harness.backends.claude_code import ClaudeCodeBackend
        from autoswe.harness.backends.factory import get_backend

        backend = get_backend({})
        assert isinstance(backend, ClaudeCodeBackend)

    def test_factory_backends_return_runresult(self):
        """Factory-produced backends accept RunSpec and return coroutine."""
        from autoswe.harness.backends.factory import get_backend

        for backend_name in ("claude_code", "codex"):
            backend = get_backend({"backend": backend_name})
            spec = RunSpec(prompt="test", cwd="/tmp")
            coro = backend.run(spec)
            assert asyncio.iscoroutine(coro), (
                f"Factory backend '{backend_name}' should return awaitable"
            )
            coro.close()


# ---------------------------------------------------------------------------
# 6. Runner dispatcher parity
# ---------------------------------------------------------------------------


class TestRunnerDispatcherParity:
    """runner.run() routes correctly for both backends."""

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

        harness = {"backend": "codex"}
        assert not backend_has_capability(harness, "mode")
        assert not backend_has_capability(harness, "mcp")
        assert not backend_has_capability(harness, "can_use_tool")
        assert not backend_has_capability(harness, "plan_permission")
        assert backend_has_capability(harness, "resume")
        assert backend_has_capability(harness, "progress_stream")

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
    Codex: mode → --sandbox flag.

    Both must handle all three modes without raising.
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
            assert isinstance(tools, list), f"allowed_tools for {mode!r} should be list"
            assert isinstance(disallowed, list), (
                f"disallowed_tools for {mode!r} should be list"
            )
            assert len(tools) > 0, f"allowed_tools for {mode!r} should not be empty"

    def test_codex_mode_sandbox_coverage(self):
        """CodexBackend _MODE_SANDBOX covers all three modes."""
        from autoswe.harness.backends.codex import _MODE_SANDBOX

        for mode in ("plan", "read_only", "read_write"):
            assert mode in _MODE_SANDBOX, (
                f"CodexBackend missing mode translation for {mode!r}"
            )
            sandbox = _MODE_SANDBOX[mode]
            assert sandbox in ("read-only", "workspace-write"), (
                f"Unexpected sandbox value for {mode!r}: {sandbox!r}"
            )

    def test_mode_readonly_equivalence(self):
        """plan and read_only both map to read-only sandbox for Codex."""
        from autoswe.harness.backends.codex import _MODE_SANDBOX

        assert _MODE_SANDBOX["plan"] == "read-only"
        assert _MODE_SANDBOX["read_only"] == "read-only"

    def test_mode_readwrite_is_workspace(self):
        """read_write mode maps to workspace-write sandbox for Codex."""
        from autoswe.harness.backends.codex import _MODE_SANDBOX

        assert _MODE_SANDBOX["read_write"] == "workspace-write"

    def test_mode_none_defaults_safe(self):
        """Unspecified mode defaults to read-only (safe) for Codex."""
        from autoswe.harness.backends.codex import _mode_to_sandbox

        assert _mode_to_sandbox(None) == "read-only"
        assert _mode_to_sandbox("unknown_mode") == "read-only"
