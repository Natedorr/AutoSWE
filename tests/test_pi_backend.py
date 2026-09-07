"""Tests for autoswe.harness.backends.pi — profile-field wiring (Phase 2).

Covers the config→argv/env surface that `factory.py` + `config.py` hand to
`PiBackend`: the `agent_dir` → `PI_CODING_AGENT_DIR` env mapping, the
`session_dir` / `system_prompt` / `append_system_prompt` CLI flags, and the
env precedence order. Deeper stream-parsing / subprocess fidelity is the next
issue (Phase 3, `PiFake`).
"""
from __future__ import annotations

import asyncio

from autoswe.harness.backends.base import RunSpec
from autoswe.harness.backends.pi import PiBackend, _build_argv


def _spec(**kw):
    base = {"prompt": "do the thing", "cwd": "/tmp", "model": "claude-sonnet-4-5"}
    base.update(kw)
    return RunSpec(**base)


# ---------------------------------------------------------------------------
# _build_argv flag mapping for the Phase-2 profile fields
# ---------------------------------------------------------------------------

def test_argv_includes_session_dir_when_set():
    """session_dir profile field maps to the --session-dir flag."""
    cfg = {"session_dir": "~/.pi/sessions"}
    argv = _build_argv(_spec(), cfg, "pi", [], "sess-1")
    assert argv[argv.index("--session-dir") + 1] == "~/.pi/sessions"


def test_argv_omits_session_dir_when_unset():
    """No session_dir → no --session-dir flag."""
    argv = _build_argv(_spec(), {}, "pi", [], "sess-1")
    assert "--session-dir" not in argv


def test_argv_includes_system_prompt_when_set():
    """system_prompt profile field maps to the --system-prompt flag."""
    cfg = {"system_prompt": "you are terse"}
    argv = _build_argv(_spec(), cfg, "pi", [], "sess-1")
    assert argv[argv.index("--system-prompt") + 1] == "you are terse"


def test_argv_includes_append_system_prompt_when_set():
    """append_system_prompt profile field maps to --append-system-prompt."""
    cfg = {"append_system_prompt": "always run the tests"}
    argv = _build_argv(_spec(), cfg, "pi", [], "sess-1")
    assert argv[argv.index("--append-system-prompt") + 1] == "always run the tests"


def test_argv_omits_system_prompt_when_unset():
    """Neither system-prompt flag is emitted when both fields are unset."""
    argv = _build_argv(_spec(), {}, "pi", [], "sess-1")
    assert "--system-prompt" not in argv
    assert "--append-system-prompt" not in argv


def test_argv_api_key_flag_from_profile():
    """api_key profile field maps to the --api-key flag."""
    cfg = {"api_key": "sk-test"}
    argv = _build_argv(_spec(), cfg, "pi", [], "sess-1")
    assert argv[argv.index("--api-key") + 1] == "sk-test"


def test_argv_approve_default_true():
    """approve_project defaults to True → --approve is emitted (dedicated-machine
    posture; pi ignores project resources without it)."""
    argv = _build_argv(_spec(), {}, "pi", [], "sess-1")
    assert "--approve" in argv


def test_argv_no_approve_when_false():
    """approve_project=False drops the --approve flag."""
    argv = _build_argv(_spec(), {"approve_project": False}, "pi", [], "sess-1")
    assert "--approve" not in argv


# ---------------------------------------------------------------------------
# agent_dir → PI_CODING_AGENT_DIR env + precedence
# ---------------------------------------------------------------------------

class _FakeProcess:
    """Minimal subprocess fake: capture the env it was spawned with, then emit a
    minimal JSON stream and exit 0 so _run_async can return a RunResult."""

    def __init__(self, captured):
        self._captured = captured
        self.returncode = 0

    async def wait(self):
        return self.returncode

    def kill(self):
        pass


class _FakeStream:
    def __init__(self, lines):
        self._lines = lines

    async def readline(self):
        if self._lines:
            return self._lines.pop(0)
        return b""

    async def read(self, n):
        return b""


def _spawn_fake(captured):
    """Build a fake process whose stdout is a one-line success stream and stderr
    is empty; record the spawned env in *captured*."""

    async def fake_create(*args, **kwargs):
        captured["env"] = dict(kwargs.get("env") or {})
        captured["argv"] = list(args)
        proc = _FakeProcess(captured)
        proc.stdout = _FakeStream([b'{"type": "agent_end", "usage": {"cost": {"total": 0.1}}}\n'])
        proc.stderr = _FakeStream([])
        return proc

    return fake_create


def test_agent_dir_maps_to_pi_coding_agent_dir():
    """agent_dir profile field is exported to PI_CODING_AGENT_DIR on the child."""
    backend = PiBackend()
    captured = {}
    spec = _spec(state={"_harness_cfg": {"agent_dir": "/custom/agent"}})

    async def drive():
        from unittest.mock import patch
        with patch("asyncio.create_subprocess_exec", _spawn_fake(captured)):
            return await backend.run(spec)

    result = asyncio.run(drive())
    assert result.subtype == "success"
    assert captured["env"]["PI_CODING_AGENT_DIR"] == "/custom/agent"


def test_agent_dir_loses_to_profile_env():
    """Precedence: profile `env` beats the agent_dir field (os.environ < api-key
    field < profile env < spec.env_overrides)."""
    backend = PiBackend()
    captured = {}
    spec = _spec(state={"_harness_cfg": {
        "agent_dir": "/from/agent_dir",
        "env": {"PI_CODING_AGENT_DIR": "/from/profile_env"},
    }})

    async def drive():
        from unittest.mock import patch
        with patch("asyncio.create_subprocess_exec", _spawn_fake(captured)):
            return await backend.run(spec)

    asyncio.run(drive())
    assert captured["env"]["PI_CODING_AGENT_DIR"] == "/from/profile_env"


def test_env_overrides_beats_profile_env():
    """spec.env_overrides is the highest-precedence source and wins over both the
    agent_dir field and profile `env`."""
    backend = PiBackend()
    captured = {}
    spec = _spec(
        env_overrides={"PI_CODING_AGENT_DIR": "/from/overrides"},
        state={"_harness_cfg": {"agent_dir": "/from/agent_dir"}},
    )

    async def drive():
        from unittest.mock import patch
        with patch("asyncio.create_subprocess_exec", _spawn_fake(captured)):
            return await backend.run(spec)

    asyncio.run(drive())
    assert captured["env"]["PI_CODING_AGENT_DIR"] == "/from/overrides"


def test_agent_dir_absent_leaves_env_unset():
    """No agent_dir field → PI_CODING_AGENT_DIR is not injected."""
    backend = PiBackend()
    captured = {}
    spec = _spec(state={"_harness_cfg": {}})

    async def drive():
        from unittest.mock import patch
        with patch("asyncio.create_subprocess_exec", _spawn_fake(captured)):
            return await backend.run(spec)

    asyncio.run(drive())
    assert "PI_CODING_AGENT_DIR" not in captured["env"]
