"""Post-fix test gate — run the repo's test suite in the worktree before a
``/fix`` can be marked done (``autoswe:fixed``).

Motivation: the fix agent's job ends at commit/push, and no test suite is run
(or checked) anywhere in the ``/fix`` path before the terminal label is set —
a branch whose suite is guaranteed red was silently marked ``autoswe:fixed``
(Natedorr/testProject#20). The gate closes that hole: a red suite can never be
silently marked "done".

Placement: ``coder._finalize_fix`` runs the gate *after* ``commit_and_push``
so the agent's work is never lost to a red gate — the branch keeps the work
and the task lands in the non-terminal ``test_failed`` state (a comment shows
the failure, ``/pr`` is blocked until a ``/fix`` re-runs the gate green).

Outcomes:

* green   — suite passes → the fix completes normally (``DONE_SUMMARY``)
* red     — suite fails → the handler returns
            ``TESTS_FAILED\\t<detail>\\t<sha>``, which the state machine maps
            to ``autoswe:test_failed``
* skipped — the gate is disabled, no command could be resolved, or the suite
            could not run (pytest not installed, timeout, …) → log a warning
            only; an infrastructure problem must not block the pipeline
            (same spirit as the ``PR_REQUIRE_CI`` "no CI → pass" rule)

Command resolution (first match wins):

1. ``repo_cfg["test_command"]`` or ``cfg["TEST_COMMAND"]`` — an explicit shell
   command, run in the worktree root
2. Python detection: a pytest signal in the worktree (``conftest.py``,
   ``pytest.ini``, ``pyproject.toml`` with ``[tool.pytest]``, ``setup.cfg``
   with ``[tool:pytest]``, ``tox.ini`` with ``[pytest]``, a
   ``requirements*.txt`` pinning pytest, a ``tests/`` or ``test/`` directory
   containing ``.py`` files, or a top-level ``test_*.py`` file) →
   ``<python> -m pytest -q``
3. nothing → skip

Configuration:

* ``TEST_GATE`` (env, default ``true``) / ``repo_cfg["test_gate"]`` — enable/disable
* ``TEST_GATE_TIMEOUT`` (env, default ``600`` s) / ``repo_cfg["test_gate_timeout"]``
"""
from __future__ import annotations

import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from autoswe.core.logging_utils import get_debug_logger, log

dbg = get_debug_logger()

_DEFAULT_TIMEOUT_S = 600
# Tail size kept for the handler result / issue comment.
_OUTPUT_TAIL_CHARS = 3000

# pytest exit code 5: "no tests were collected" — there is nothing to gate on.
_PYTEST_NO_TESTS_EXIT = 5

# ``No module named x`` / ``No module named 'x'`` on stderr means the runner
# (or the suite's own deps) is missing — an infrastructure problem, not a
# red suite. The -m form has no quotes; import errors inside a script do.
_NO_MODULE_RE = re.compile(r"No module named\s+[\"']?([A-Za-z0-9_.\-]+)")

_REQ_PYTEST_RE = re.compile(r"(^|\n)\s*pytest\b")


@dataclass
class GateResult:
    """Outcome of one post-fix test gate run.

    *ok* is True whenever the gate does NOT block the fix (green suite or any
    skip). *ran* distinguishes "the suite actually ran and passed" from the
    skipped variants, so callers can log the difference.
    """
    ok: bool
    ran: bool
    reason: str
    output: str = ""
    command: str | None = None
    duration_seconds: float = 0.0


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def gate_enabled(cfg: dict | None, repo_cfg: dict | None) -> bool:
    """Resolve the gate switch: per-repo override (lowercase key) beats cfg."""
    override = (repo_cfg or {}).get("test_gate")
    if override is not None:
        return bool(override)
    return bool((cfg or {}).get("TEST_GATE", True))


def _gate_timeout(cfg: dict | None, repo_cfg: dict | None) -> int:
    override = (repo_cfg or {}).get("test_gate_timeout")
    if override is not None:
        try:
            return max(1, int(override))
        except (TypeError, ValueError):
            dbg.warning("test_gate_timeout %r is not an integer; using default", override)
    try:
        return max(1, int((cfg or {}).get("TEST_GATE_TIMEOUT", _DEFAULT_TIMEOUT_S)))
    except (TypeError, ValueError):
        return _DEFAULT_TIMEOUT_S


# ---------------------------------------------------------------------------
# Command resolution
# ---------------------------------------------------------------------------


def detect_python_suite(wt: Path) -> bool:
    """Heuristically detect a pytest-based suite in *wt* (root level only).

    Conservative on purpose: the gate only auto-runs pytest when the worktree
    unambiguously looks like a Python project that uses pytest. Non-Python
    repos must set an explicit ``test_command`` to be gated.
    """
    if not wt.is_dir():
        return False
    if (wt / "conftest.py").is_file() or (wt / "pytest.ini").is_file():
        return True
    for name, needle in (
        ("pyproject.toml", "[tool.pytest"),
        ("setup.cfg", "[tool:pytest]"),
        ("tox.ini", "[pytest]"),
    ):
        path = wt / name
        if path.is_file():
            try:
                if needle in path.read_text(encoding="utf-8", errors="replace"):
                    return True
            except OSError:
                pass
    for path in wt.glob("requirements*.txt"):
        try:
            if _REQ_PYTEST_RE.search(path.read_text(encoding="utf-8", errors="replace")):
                return True
        except OSError:
            pass
    for name in ("tests", "test"):
        dir_path = wt / name
        if dir_path.is_dir() and any(dir_path.glob("*.py")):
            return True
    return bool(any(wt.glob("test_*.py")))


def resolve_test_command(wt: Path, cfg: dict | None, repo_cfg: dict | None) -> tuple[str, str]:
    """Return ``(command, source)`` for the gate.

    *source* is one of ``"repo_cfg"``, ``"cfg"``, ``"python-detect"``,
    ``"none"`` (with an empty command).
    """
    repo_cmd = (repo_cfg or {}).get("test_command")
    if isinstance(repo_cmd, str) and repo_cmd.strip():
        return repo_cmd.strip(), "repo_cfg"
    global_cmd = (cfg or {}).get("TEST_COMMAND")
    if isinstance(global_cmd, str) and global_cmd.strip():
        return global_cmd.strip(), "cfg"
    if wt.is_dir() and detect_python_suite(wt):
        return f"{sys.executable} -m pytest -q", "python-detect"
    return "", "none"


# ---------------------------------------------------------------------------
# Gate runner
# ---------------------------------------------------------------------------


def _tail(text: str | None, limit: int = _OUTPUT_TAIL_CHARS) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return "…" + text[-limit:]


def run_test_gate(
    wt: Path,
    cfg: dict | None,
    repo_cfg: dict | None,
    *,
    progress_callback=None,
) -> GateResult:
    """Run the post-fix test gate in *wt*.

    Never raises — every failure mode maps to a ``GateResult`` so the caller
    (``coder._finalize_fix``) only has to check ``ok``.
    """
    if not gate_enabled(cfg, repo_cfg):
        return GateResult(ok=True, ran=False, reason="gate disabled")

    command, source = resolve_test_command(wt, cfg, repo_cfg)
    if not command:
        dbg.debug("TEST GATE: skipped — no test command resolvable in %s", wt)
        return GateResult(ok=True, ran=False, reason="no test suite detected")

    timeout = _gate_timeout(cfg, repo_cfg)
    if progress_callback:
        progress_callback(f"Running test gate: `{command[:80]}` …")
    log(f"[GATE] running test gate: {command!r} (source={source}, timeout={timeout}s) in {wt}")

    start = time.monotonic()
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=str(wt),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        reason = f"test gate timed out after {timeout}s"
        dbg.warning("TEST GATE: %s — skipping (non-gating)", reason)
        return GateResult(
            ok=True, ran=False, reason=reason, command=command,
            duration_seconds=round(time.monotonic() - start, 2),
        )
    except OSError as e:
        reason = f"test gate could not run: {e}"
        dbg.warning("TEST GATE: %s — skipping (non-gating)", reason)
        return GateResult(
            ok=True, ran=False, reason=reason, command=command,
            duration_seconds=round(time.monotonic() - start, 2),
        )
    duration = round(time.monotonic() - start, 2)
    combined = "\n".join(
        part for part in (proc.stdout, proc.stderr) if part and part.strip()
    )
    output = _tail(combined)

    if proc.returncode == 0:
        log(f"[GATE] suite green ({duration}s)")
        return GateResult(
            ok=True, ran=True, reason="suite green",
            output=output, command=command, duration_seconds=duration,
        )

    # No tests collected (pytest exit 5) → nothing to gate on.
    if proc.returncode == _PYTEST_NO_TESTS_EXIT:
        dbg.warning("TEST GATE: pytest collected no tests (exit 5) — passing")
        return GateResult(
            ok=True, ran=False, reason="no tests collected (pytest exit 5)",
            output=output, command=command, duration_seconds=duration,
        )

    # Runner (or suite dependency) missing → infrastructure problem, not a
    # red suite. Only applied when the runner never started (no stdout) — a
    # suite that did start and errored on an import is a real failure.
    if not (proc.stdout or "").strip():
        missing = _NO_MODULE_RE.search(proc.stderr or "")
        if missing:
            reason = f"module '{missing.group(1)}' is not importable — gate skipped"
            dbg.warning("TEST GATE: %s — skipping (non-gating)", reason)
            return GateResult(
                ok=True, ran=False, reason=reason, output=output,
                command=command, duration_seconds=duration,
            )

    reason = f"suite failing (exit {proc.returncode})"
    log(f"[GATE] suite RED ({duration}s, exit {proc.returncode})")
    return GateResult(
        ok=False, ran=True, reason=reason,
        output=output, command=command, duration_seconds=duration,
    )
