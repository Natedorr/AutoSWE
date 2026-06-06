"""Tests for runner.run() subtype-based retry logic (Part 1 of Codex retry gap fix).

Verifies:
- CodexFake returning subtype="error" then "success" is retried when
  AGENT_RETRY_ON_FAILURE=1.
- No retry fires when max_retries=0 (loop runs once).
- AGENT_RETRY_ON_SUBTYPE override narrows the retryable set (e.g. "error"
  only → "killed" is not retried).
- Claude backend (empty retryable_subtypes) does not retry on subtypes even
  when AGENT_RETRY_ON_FAILURE=1.
"""
from __future__ import annotations

import asyncio
from unittest.mock import patch

from autoswe.harness.backends.base import RunResult, RunSpec

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cfg(retries: int = 1, subtype_override: str = "") -> dict:
    cfg: dict = {"AGENT_TIMEOUT": 30, "AGENT_RETRY_ON_FAILURE": retries}
    if subtype_override:
        cfg["AGENT_RETRY_ON_SUBTYPE"] = subtype_override
    return cfg


def _make_result(subtype: str) -> RunResult:
    return RunResult(text=f"run-{subtype}", session_id=None, subtype=subtype)


class _SequenceBackend:
    """Backend that returns pre-configured RunResults in sequence."""

    def __init__(self, subtypes: list[str]):
        self._results = [_make_result(s) for s in subtypes]
        self._idx = 0

    @classmethod
    def capabilities(cls) -> set[str]:
        return {"mode", "resume", "progress_stream"}

    @classmethod
    def retryable_subtypes(cls) -> set[str]:
        return {"error", "killed"}

    def run(self, spec: RunSpec):
        async def _go():
            result = self._results[self._idx]
            self._idx = min(self._idx + 1, len(self._results) - 1)
            return result
        return _go()


# ---------------------------------------------------------------------------
# Subtype retry — Codex-style backend
# ---------------------------------------------------------------------------


def test_runner_retries_on_error_subtype():
    """error subtype triggers retry when AGENT_RETRY_ON_FAILURE=1."""
    from autoswe.harness import runner

    backend = _SequenceBackend(["error", "success"])
    calls: list[str] = []

    original_run = backend.run
    def tracking_run(spec):
        coro = original_run(spec)
        calls.append("call")
        return coro
    backend.run = tracking_run

    # Patch get_backend so runner.run() uses our sequence backend
    with patch("autoswe.harness.runner.ClaudeCodeBackend", return_value=backend):
        result = runner.run(
            "test",
            cwd="/tmp",
            cfg=_cfg(retries=1),
        )

    assert result.subtype == "success", f"Expected success after retry, got {result.subtype}"
    assert len(calls) == 2, f"Expected 2 calls (1 retry), got {len(calls)}"


def test_runner_no_retry_when_max_retries_zero():
    """No retry fires when AGENT_RETRY_ON_FAILURE=0 even for error subtype."""
    from autoswe.harness import runner

    backend = _SequenceBackend(["error", "success"])
    calls: list[str] = []

    original_run = backend.run
    def tracking_run(spec):
        coro = original_run(spec)
        calls.append("call")
        return coro
    backend.run = tracking_run

    with patch("autoswe.harness.runner.ClaudeCodeBackend", return_value=backend):
        result = runner.run(
            "test",
            cwd="/tmp",
            cfg=_cfg(retries=0),
        )

    assert result.subtype == "error", "Should return first result with no retry"
    assert len(calls) == 1, f"Expected 1 call (no retry), got {len(calls)}"


def test_runner_retries_on_killed_subtype():
    """killed subtype triggers retry when AGENT_RETRY_ON_FAILURE=1."""
    from autoswe.harness import runner

    backend = _SequenceBackend(["killed", "success"])
    calls: list[str] = []

    original_run = backend.run
    def tracking_run(spec):
        coro = original_run(spec)
        calls.append("call")
        return coro
    backend.run = tracking_run

    with patch("autoswe.harness.runner.ClaudeCodeBackend", return_value=backend):
        result = runner.run(
            "test",
            cwd="/tmp",
            cfg=_cfg(retries=1),
        )

    assert result.subtype == "success"
    assert len(calls) == 2


def test_runner_subtype_override_narrows_set():
    """AGENT_RETRY_ON_SUBTYPE='error' means 'killed' is NOT retried."""
    from autoswe.harness import runner

    # Backend would retry "killed" by default, but override limits to "error"
    backend = _SequenceBackend(["killed", "success"])
    calls: list[str] = []

    original_run = backend.run
    def tracking_run(spec):
        coro = original_run(spec)
        calls.append("call")
        return coro
    backend.run = tracking_run

    with patch("autoswe.harness.runner.ClaudeCodeBackend", return_value=backend):
        result = runner.run(
            "test",
            cwd="/tmp",
            cfg=_cfg(retries=1, subtype_override="error"),
        )

    assert result.subtype == "killed", "killed should not be retried when override='error'"
    assert len(calls) == 1


def test_runner_subtype_override_enables_retry():
    """AGENT_RETRY_ON_SUBTYPE='error' retries error subtype."""
    from autoswe.harness import runner

    backend = _SequenceBackend(["error", "success"])
    calls: list[str] = []

    original_run = backend.run
    def tracking_run(spec):
        coro = original_run(spec)
        calls.append("call")
        return coro
    backend.run = tracking_run

    with patch("autoswe.harness.runner.ClaudeCodeBackend", return_value=backend):
        result = runner.run(
            "test",
            cwd="/tmp",
            cfg=_cfg(retries=1, subtype_override="error"),
        )

    assert result.subtype == "success"
    assert len(calls) == 2


def test_runner_no_subtype_retry_for_claude_backend():
    """ClaudeCodeBackend has empty retryable_subtypes — no subtype retry fires."""
    from autoswe.harness import runner
    from autoswe.harness.backends.claude_code import ClaudeCodeBackend

    # ClaudeCodeBackend.retryable_subtypes() returns set()
    assert ClaudeCodeBackend.retryable_subtypes() == set()

    results = [_make_result("error"), _make_result("success")]
    call_count = [0]

    def fake_asyncio_run(coro):
        coro.close()
        r = results[min(call_count[0], len(results) - 1)]
        call_count[0] += 1
        return r

    with patch.object(asyncio, "run", side_effect=fake_asyncio_run):
        result = runner.run(
            "test",
            cwd="/tmp",
            cfg=_cfg(retries=1),
        )

    assert result.subtype == "error", "Claude should not retry on subtype"
    assert call_count[0] == 1


def test_runner_success_subtype_no_retry():
    """success subtype never triggers retry regardless of settings."""
    from autoswe.harness import runner

    backend = _SequenceBackend(["success", "success"])
    calls: list[str] = []

    original_run = backend.run
    def tracking_run(spec):
        coro = original_run(spec)
        calls.append("call")
        return coro
    backend.run = tracking_run

    with patch("autoswe.harness.runner.ClaudeCodeBackend", return_value=backend):
        result = runner.run(
            "test",
            cwd="/tmp",
            cfg=_cfg(retries=2),
        )

    assert result.subtype == "success"
    assert len(calls) == 1, "success should not trigger retry"


def test_runner_exhausts_retries_returns_last_result():
    """When all retries fail, the last RunResult is returned (no raise for subtype failures)."""
    from autoswe.harness import runner

    backend = _SequenceBackend(["error", "error", "error"])
    calls: list[str] = []

    original_run = backend.run
    def tracking_run(spec):
        coro = original_run(spec)
        calls.append("call")
        return coro
    backend.run = tracking_run

    with patch("autoswe.harness.runner.ClaudeCodeBackend", return_value=backend):
        result = runner.run(
            "test",
            cwd="/tmp",
            cfg=_cfg(retries=2),
        )

    # 3 attempts (initial + 2 retries), final result is returned not raised
    assert result.subtype == "error"
    assert len(calls) == 3
