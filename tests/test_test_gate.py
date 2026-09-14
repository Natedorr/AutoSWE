"""Tests for autoswe.harness.test_gate — post-fix test gate (Natedorr/testProject#20).

The gate runs the repo's test suite in the worktree after commit/push and
before the task can reach the terminal ``fixed`` state. Run-tests use real
subprocesses in tmp directories (the gate is infrastructure: it shells out to
the repo's own test runner).
"""
from __future__ import annotations

import sys

import pytest

from autoswe.harness.test_gate import (
    GateResult,
    detect_python_suite,
    gate_enabled,
    resolve_test_command,
    run_test_gate,
)
from autoswe.orch.gate_policy import (
    auto_fix_on_gate_failure,
    build_gate_guidance,
    gate_max_fix_attempts,
)

PY = sys.executable


# ---------------------------------------------------------------------------
# gate_enabled — flag resolution
# ---------------------------------------------------------------------------


def test_gate_enabled_by_default():
    assert gate_enabled({}, {}) is True
    assert gate_enabled(None, None) is True


def test_gate_disabled_via_cfg():
    assert gate_enabled({"TEST_GATE": False}, {}) is False
    assert gate_enabled({"TEST_GATE": True}, {}) is True


def test_gate_repo_override_beats_cfg():
    assert gate_enabled({"TEST_GATE": True}, {"test_gate": False}) is False
    assert gate_enabled({"TEST_GATE": False}, {"test_gate": True}) is True


# ---------------------------------------------------------------------------
# detect_python_suite
# ---------------------------------------------------------------------------


def test_detect_empty_dir_is_false(tmp_path):
    assert detect_python_suite(tmp_path) is False


def test_detect_missing_dir_is_false(tmp_path):
    assert detect_python_suite(tmp_path / "nope") is False


@pytest.mark.parametrize("marker", [
    "conftest.py",
    "pytest.ini",
])
def test_detect_standalone_markers(tmp_path, marker):
    (tmp_path / marker).write_text("", encoding="utf-8")
    assert detect_python_suite(tmp_path) is True


def test_detect_pyproject_pytest_section(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\ntestpaths = ['tests']\n", encoding="utf-8",
    )
    assert detect_python_suite(tmp_path) is True


def test_detect_pyproject_without_pytest_section(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n", encoding="utf-8")
    assert detect_python_suite(tmp_path) is False


def test_detect_tests_dir_with_python(tmp_path):
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_a.py").write_text("def test_a(): pass\n", encoding="utf-8")
    assert detect_python_suite(tmp_path) is True


def test_detect_tests_dir_without_python(tmp_path):
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "readme.md").write_text("no python here", encoding="utf-8")
    assert detect_python_suite(tmp_path) is False


def test_detect_top_level_test_file(tmp_path):
    (tmp_path / "test_half.py").write_text("def test_half(): pass\n", encoding="utf-8")
    assert detect_python_suite(tmp_path) is True


def test_detect_requirements_pytest(tmp_path):
    (tmp_path / "requirements.txt").write_text("flask\npytest>=7\n", encoding="utf-8")
    assert detect_python_suite(tmp_path) is True


# ---------------------------------------------------------------------------
# resolve_test_command — precedence
# ---------------------------------------------------------------------------


def test_resolve_repo_command_wins(tmp_path):
    (tmp_path / "conftest.py").write_text("", encoding="utf-8")
    cmd, source = resolve_test_command(tmp_path, {"TEST_COMMAND": "echo g"}, {"test_command": "echo r"})
    assert cmd == "echo r"
    assert source == "repo_cfg"


def test_resolve_global_command_wins_over_detection(tmp_path):
    (tmp_path / "conftest.py").write_text("", encoding="utf-8")
    cmd, source = resolve_test_command(tmp_path, {"TEST_COMMAND": "echo g"}, {})
    assert cmd == "echo g"
    assert source == "cfg"


def test_resolve_detection_when_no_explicit(tmp_path):
    (tmp_path / "conftest.py").write_text("", encoding="utf-8")
    cmd, source = resolve_test_command(tmp_path, {}, {})
    assert cmd == f"{PY} -m pytest -q"
    assert source == "python-detect"


def test_resolve_none_when_bare(tmp_path):
    cmd, source = resolve_test_command(tmp_path, {}, {})
    assert cmd == ""
    assert source == "none"


def test_resolve_blank_repo_command_falls_through(tmp_path):
    cmd, source = resolve_test_command(tmp_path, {}, {"test_command": "   "})
    assert cmd == ""
    assert source == "none"


# ---------------------------------------------------------------------------
# run_test_gate — outcomes (real subprocesses)
# ---------------------------------------------------------------------------


def test_gate_disabled_skips(tmp_path):
    r = run_test_gate(tmp_path, {"TEST_GATE": False}, {})
    assert r.ok is True
    assert r.ran is False
    assert r.reason == "gate disabled"


def test_gate_no_command_skips(tmp_path):
    r = run_test_gate(tmp_path, {}, {})
    assert r.ok is True
    assert r.ran is False
    assert "no test suite" in r.reason


def test_gate_explicit_green(tmp_path):
    r = run_test_gate(tmp_path, {}, {"test_command": f"{PY} -c \"print('ok')\""})
    assert r.ok is True
    assert r.ran is True
    assert "ok" in r.output


def test_gate_explicit_red(tmp_path):
    r = run_test_gate(tmp_path, {}, {"test_command": f"{PY} -c \"import sys; sys.exit(3)\""})
    assert r.ok is False
    assert r.ran is True
    assert "exit 3" in r.reason
    assert r.command is not None


def test_gate_detection_red_suite(tmp_path):
    """The exact Natedorr/testProject#20 shape: a test file the implementation
    cannot satisfy makes the suite red regardless of what the fixer writes."""
    (tmp_path / "test_authoritative.py").write_text(
        "def test_half_ten_contract():\n    assert 5.0 == 6.0\n", encoding="utf-8",
    )
    r = run_test_gate(tmp_path, {}, {})
    assert r.ok is False
    assert r.ran is True
    assert "exit 1" in r.reason
    assert "test_half_ten_contract" in r.output


def test_gate_detection_green_suite(tmp_path):
    (tmp_path / "test_pass.py").write_text("def test_pass(): assert True\n", encoding="utf-8")
    r = run_test_gate(tmp_path, {}, {})
    assert r.ok is True
    assert r.ran is True


def test_gate_missing_module_is_non_gating(tmp_path):
    r = run_test_gate(tmp_path, {}, {"test_command": f"{PY} -m no_such_module_xyz -q"})
    assert r.ok is True
    assert r.ran is False
    assert "no_such_module_xyz" in r.reason


def test_gate_timeout_is_non_gating(tmp_path):
    r = run_test_gate(
        tmp_path, {"TEST_GATE_TIMEOUT": 1},
        {"test_command": f"{PY} -c \"import time; time.sleep(5)\""},
    )
    assert r.ok is True
    assert r.ran is False
    assert "timed out" in r.reason


def test_gate_output_tail_truncated(tmp_path):
    r = run_test_gate(tmp_path, {}, {"test_command": f"{PY} -c \"print('x'*10000)\""})
    assert r.ok is True
    assert len(r.output) < 3500  # capped by _OUTPUT_TAIL_CHARS + marker
    assert r.output.startswith("…")


def test_gate_result_is_dataclass_fields():
    g = GateResult(ok=True, ran=False, reason="x")
    assert g.command is None
    assert g.duration_seconds == 0.0
    assert g.output == ""


@pytest.mark.parametrize("bad", ["not-an-int", None, 0, -5])
def test_gate_timeout_bad_values_fall_back(tmp_path, bad):
    # Must not raise; must use the default (or 1s) timeout.
    r = run_test_gate(tmp_path, {}, {"test_command": f"{PY} -c \"pass\"", "test_gate_timeout": bad})
    assert r.ok is True


# ---------------------------------------------------------------------------
# Shared recoverable-gate policy (issue #245 §2.5) — gate unification.
#
# test_failed (this module's gate) and ci_failed (the remote CI watch) share
# one policy: the counter, the config switch, the budget, and the
# prompt-assembly helper below. These live in orch/gate_policy.py so both
# decide()'s CI branch and its local test-gate branch can reuse them without
# duplicating the failure-section logic.
# ---------------------------------------------------------------------------


def test_gate_max_fix_attempts_defaults_2():
    assert gate_max_fix_attempts({}, {}) == 2


def test_gate_max_fix_attempts_cfg_override():
    assert gate_max_fix_attempts({"GATE_MAX_FIX_ATTEMPTS": 5}, {}) == 5


def test_gate_max_fix_attempts_repo_override_beats_cfg():
    assert gate_max_fix_attempts(
        {"GATE_MAX_FIX_ATTEMPTS": 5}, {"gate_max_fix_attempts": 1},
    ) == 1


def test_gate_max_fix_attempts_bad_value_falls_back():
    assert gate_max_fix_attempts({"GATE_MAX_FIX_ATTEMPTS": "not-an-int"}, {}) == 2


def test_auto_fix_on_gate_failure_defaults_true():
    assert auto_fix_on_gate_failure({}, {}) is True


def test_auto_fix_on_gate_failure_cfg_override():
    assert auto_fix_on_gate_failure({"AUTO_FIX_ON_GATE_FAILURE": False}, {}) is False


def test_auto_fix_on_gate_failure_repo_override_beats_cfg():
    assert auto_fix_on_gate_failure(
        {"AUTO_FIX_ON_GATE_FAILURE": True}, {"auto_fix_on_gate_failure": False},
    ) is False


def test_build_gate_guidance_header_only():
    assert build_gate_guidance("CI failed on the pushed branch.") == "CI failed on the pushed branch."


def test_build_gate_guidance_with_failing_checks():
    guidance = build_gate_guidance("CI failed.", failing=["build", "lint"])
    assert guidance == "CI failed.\n\nFailing checks:\n- build\n- lint"


def test_build_gate_guidance_with_summary():
    guidance = build_gate_guidance("CI failed.", summary="1 check(s) failing: build")
    assert guidance == "CI failed.\n\n1 check(s) failing: build"


def test_build_gate_guidance_with_excerpt():
    guidance = build_gate_guidance("Test gate failed.", excerpt="assert 5.0 == 6.0")
    assert guidance == "Test gate failed.\n\n```\nassert 5.0 == 6.0\n```"


def test_build_gate_guidance_combines_all_sections():
    guidance = build_gate_guidance(
        "CI failed.", failing=["build"], summary="1 failing", excerpt="log tail",
    )
    assert guidance == (
        "CI failed.\n\nFailing checks:\n- build\n\n1 failing\n\n```\nlog tail\n```"
    )


def test_build_gate_guidance_local_and_remote_share_shape():
    """The same helper produces both a CI-style and a local-test-gate-style
    guidance block — one prompt-assembly helper, two signals (issue #245 §2.5)."""
    ci_guidance = build_gate_guidance(
        "CI failed on the pushed branch.", failing=["build"], summary="1 check(s) failing: build",
    )
    local_guidance = build_gate_guidance(
        "🧪 Test gate failed on the pushed branch.", excerpt="test_x FAILED",
    )
    assert ci_guidance.startswith("CI failed on the pushed branch.")
    assert local_guidance.startswith("🧪 Test gate failed on the pushed branch.")
    assert "test_x FAILED" in local_guidance
