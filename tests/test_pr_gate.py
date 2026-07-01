"""Tests for autoswe.vcs.pr_gate — PR preflight gate (branch-sync + CI status)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from autoswe.harness.backends.base import HandlerResult
from autoswe.providers.base import CIStatus
from autoswe.vcs.pr_gate import _flag, preflight_pr
from tests.fakes.git_fake import GitFake


def make_task(issue_number=1):
    return {
        "id": "o_r_1",
        "owner": "o",
        "repo": "r",
        "issue_number": issue_number,
        "base_branch": "main",
        "_token": "tok",
    }


@pytest.fixture
def git_fake():
    fake = GitFake()
    mod, originals = fake.patch()
    yield fake
    fake.unpatch(mod, originals)


def _vcs(ci_state="none", **ci_kwargs):
    vcs = MagicMock()
    vcs.branch_name.side_effect = lambda n: f"autoswe/issue-{n}"
    vcs.get_ci_status.return_value = CIStatus(state=ci_state, **ci_kwargs)
    return vcs


# ---------------------------------------------------------------------------
# _flag — per-repo override resolution
# ---------------------------------------------------------------------------

def test_flag_uses_cfg_default_when_no_override():
    assert _flag("PR_REQUIRE_CI", {"PR_REQUIRE_CI": True}, {}) is True
    assert _flag("PR_REQUIRE_CI", {"PR_REQUIRE_CI": False}, {}) is False


def test_flag_missing_cfg_key_uses_default_true():
    assert _flag("PR_REQUIRE_CI", {}, {}) is True


def test_flag_repo_cfg_override_beats_cfg():
    assert _flag("PR_REQUIRE_CI", {"PR_REQUIRE_CI": True}, {"pr_require_ci": False}) is False
    assert _flag("PR_REQUIRE_SYNC", {"PR_REQUIRE_SYNC": False}, {"pr_require_sync": True}) is True


# ---------------------------------------------------------------------------
# preflight_pr — CI gate
# ---------------------------------------------------------------------------

def test_ci_success_passes(git_fake):
    task = make_task()
    vcs = _vcs(ci_state="success")
    ok, reason = preflight_pr(task, {}, {}, vcs=vcs)
    assert ok is True
    assert reason == ""


def test_ci_none_passes(git_fake):
    """No CI configured on the repo never blocks a PR."""
    task = make_task()
    vcs = _vcs(ci_state="none")
    ok, reason = preflight_pr(task, {}, {}, vcs=vcs)
    assert ok is True


def test_ci_pending_blocks(git_fake):
    task = make_task()
    vcs = _vcs(ci_state="pending", pending_count=2)
    ok, reason = preflight_pr(task, {}, {}, vcs=vcs)
    assert ok is False
    assert "pending" in reason.lower()
    assert "2" in reason


def test_ci_failure_blocks(git_fake):
    task = make_task()
    vcs = _vcs(ci_state="failure", failing=["build"], summary="1 check(s) failing: build")
    ok, reason = preflight_pr(task, {}, {}, vcs=vcs)
    assert ok is False
    assert "build" in reason


def test_ci_gate_disabled_ignores_failure(git_fake):
    task = make_task()
    vcs = _vcs(ci_state="failure", failing=["build"])
    ok, reason = preflight_pr(task, {"PR_REQUIRE_CI": False}, {}, vcs=vcs)
    assert ok is True
    vcs.get_ci_status.assert_not_called()


# ---------------------------------------------------------------------------
# preflight_pr — sync gate (do_sync=True, the /pr path)
# ---------------------------------------------------------------------------

def test_sync_disabled_skips_worktree_ops_entirely(git_fake):
    task = make_task()
    vcs = _vcs(ci_state="none")
    ok, reason = preflight_pr(task, {"PR_REQUIRE_SYNC": False}, {}, vcs=vcs, do_sync=True)
    assert ok is True
    assert git_fake.calls == []


def test_do_sync_false_skips_sync_even_when_enabled(git_fake):
    """The adapter's auto-PR path passes do_sync=False (branch already synced)."""
    task = make_task()
    vcs = _vcs(ci_state="none")
    ok, reason = preflight_pr(task, {"PR_REQUIRE_SYNC": True}, {}, vcs=vcs, do_sync=False)
    assert ok is True
    assert git_fake.calls == []


def test_sync_already_clean_proceeds_to_ci_check(git_fake):
    task = make_task()
    git_fake.script_sync({"synced": True, "conflict": False, "branch": "autoswe/issue-1", "ahead": 0})
    vcs = _vcs(ci_state="success")
    ok, reason = preflight_pr(task, {}, {}, vcs=vcs)
    assert ok is True
    vcs.get_ci_status.assert_called_once()


def test_sync_rebase_conflict_blocks(git_fake):
    task = make_task()
    git_fake.script_sync({
        "synced": False, "conflict": True, "rebase": True,
        "branch": "autoswe/issue-1", "ahead": 0, "conflict_files": ["a.py", "b.py"],
    })
    vcs = _vcs(ci_state="none")
    ok, reason = preflight_pr(task, {}, {}, vcs=vcs)
    assert ok is False
    assert "rebase conflict" in reason
    assert "a.py" in reason
    vcs.get_ci_status.assert_not_called()


def test_sync_error_blocks(git_fake):
    task = make_task()
    git_fake.script_sync({"synced": False, "conflict": False, "branch": "autoswe/issue-1",
                          "ahead": 0, "error": "fetch failed"})
    vcs = _vcs(ci_state="none")
    ok, reason = preflight_pr(task, {}, {}, vcs=vcs)
    assert ok is False
    assert "fetch failed" in reason


def test_sync_merge_conflict_resolved_by_claude_proceeds(git_fake):
    task = make_task()
    git_fake.script_sync({
        "synced": False, "conflict": True, "branch": "autoswe/issue-1",
        "ahead": 0, "conflict_files": ["a.py"],
    })
    vcs = _vcs(ci_state="success")

    with patch("autoswe.harness.coder.resolve_sync_conflicts") as mock_resolve:
        mock_resolve.return_value = HandlerResult("DONE_SUMMARY\tresolved\tabc123")
        ok, reason = preflight_pr(task, {}, {}, vcs=vcs)

    assert ok is True
    mock_resolve.assert_called_once()
    vcs.get_ci_status.assert_called_once()


def test_sync_merge_conflict_resolution_fails_blocks(git_fake):
    task = make_task()
    git_fake.script_sync({
        "synced": False, "conflict": True, "branch": "autoswe/issue-1",
        "ahead": 0, "conflict_files": ["a.py"],
    })
    vcs = _vcs(ci_state="success")

    with patch("autoswe.harness.coder.resolve_sync_conflicts") as mock_resolve:
        mock_resolve.return_value = HandlerResult("FAILED: could not resolve")
        ok, reason = preflight_pr(task, {}, {}, vcs=vcs)

    assert ok is False
    assert "sync conflict could not be resolved" in reason
    vcs.get_ci_status.assert_not_called()


def test_progress_callback_forwarded_on_conflict(git_fake):
    task = make_task()
    git_fake.script_sync({
        "synced": False, "conflict": True, "branch": "autoswe/issue-1",
        "ahead": 0, "conflict_files": ["a.py"],
    })
    vcs = _vcs(ci_state="none")
    progress = MagicMock()

    with patch("autoswe.harness.coder.resolve_sync_conflicts") as mock_resolve:
        mock_resolve.return_value = HandlerResult("DONE_SUMMARY\tresolved\tabc123")
        preflight_pr(task, {}, {}, vcs=vcs, progress_callback=progress)

    progress.assert_called_once()
    assert "conflict" in progress.call_args[0][0].lower()
