"""Tests for autoswe.vcs.pr_gate — PR preflight gate (branch-sync + CI status)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from autoswe.harness.backends.base import HandlerResult
from autoswe.providers.base import CIStatus
from autoswe.vcs.pr_gate import _flag, _policy, preflight_pr
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


def test_ci_error_blocks_by_default(git_fake):
    """An unconsultable CI API (state='error') blocks the gate by default.

    Fail-safe: never treat a failed CI read as a pass.
    """
    task = make_task()
    vcs = _vcs(ci_state="error", summary="could not read CI status")
    ok, reason = preflight_pr(task, {}, {}, vcs=vcs)
    assert ok is False
    assert "PR_CI_ERROR_POLICY=block" in reason


def test_ci_error_blocks_when_policy_block(git_fake):
    task = make_task()
    vcs = _vcs(ci_state="error", summary="could not read CI status")
    ok, reason = preflight_pr(task, {"PR_CI_ERROR_POLICY": "block"}, {}, vcs=vcs)
    assert ok is False


def test_ci_error_passes_when_policy_open(git_fake):
    """PR_CI_ERROR_POLICY=open is the explicit opt-out to ship when CI can't
    be verified."""
    task = make_task()
    vcs = _vcs(ci_state="error", summary="could not read CI status")
    ok, reason = preflight_pr(task, {"PR_CI_ERROR_POLICY": "open"}, {}, vcs=vcs)
    assert ok is True
    assert reason == ""


def test_ci_error_repo_override_policy_open_beats_cfg(git_fake):
    """A per-repo pr_ci_error_policy override beats the cfg-level policy."""
    task = make_task()
    vcs = _vcs(ci_state="error", summary="could not read CI status")
    ok, reason = preflight_pr(
        task, {"PR_CI_ERROR_POLICY": "block"}, {"pr_ci_error_policy": "open"}, vcs=vcs,
    )
    assert ok is True


def test_ci_error_repo_override_typo_does_not_open_gate(git_fake):
    """A per-repo pr_ci_error_policy override that is a typo (e.g. 'blocked')
    must NOT silently open the gate: it is not a recognised value, so the gate
    falls back to the fail-safe default ('block') and still blocks on an
    unconsultable CI. A typo can't ship a PR on unconsultable CI."""
    task = make_task()
    vcs = _vcs(ci_state="error", summary="could not read CI status")
    ok, reason = preflight_pr(
        task, {"PR_CI_ERROR_POLICY": "block"}, {"pr_ci_error_policy": "blocked"}, vcs=vcs,
    )
    assert ok is False
    assert "PR_CI_ERROR_POLICY=block" in reason


def test_ci_error_cfg_unknown_value_does_not_open_gate(git_fake):
    """A cfg-level PR_CI_ERROR_POLICY that is not 'open'/'block' is an unknown
    value: the gate falls back to the fail-safe default ('block') and blocks
    on an unconsultable CI, rather than treating the typo as an opt-out."""
    task = make_task()
    vcs = _vcs(ci_state="error", summary="could not read CI status")
    ok, reason = preflight_pr(task, {"PR_CI_ERROR_POLICY": "blockish"}, {}, vcs=vcs)
    assert ok is False
    assert "PR_CI_ERROR_POLICY=block" in reason


def test_ci_error_empty_repo_override_falls_back_to_block(git_fake):
    """An empty-string per-repo override is not a recognised value: it falls
    back to the fail-safe default ('block'), so an unconsultable CI still
    blocks. Regression pin for the pre-existing '' -> default behaviour."""
    task = make_task()
    vcs = _vcs(ci_state="error", summary="could not read CI status")
    ok, reason = preflight_pr(
        task, {"PR_CI_ERROR_POLICY": "open"}, {"pr_ci_error_policy": ""}, vcs=vcs,
    )
    assert ok is False
    assert "PR_CI_ERROR_POLICY=block" in reason


def test_ci_stale_pending_blocks_with_note(git_fake):
    """A stale pending verdict (build predates branch head) blocks like an
    in-flight build, with a note explaining why."""
    task = make_task()
    vcs = _vcs(ci_state="pending", stale=True, pending_count=0)
    ok, reason = preflight_pr(task, {}, {}, vcs=vcs)
    assert ok is False
    assert "stale" in reason.lower()


def test_ci_stale_canceled_build_blocks_as_stale_not_failure(git_fake):
    """A stale *canceled* Azure build reaches the gate as a pending/stale
    verdict and blocks with the stale note — NOT as a permanent 'CI failing'
    failure (the issue's 'a stale canceled build no longer blocks forever')."""
    task = make_task()
    # The provider already reduced this to state=pending, stale=True (see
    # test_azure_vcs stale-canceled pin). The gate must block on staleness,
    # not surface it as a terminal failure.
    vcs = _vcs(ci_state="pending", stale=True, pending_count=0)
    ok, reason = preflight_pr(task, {}, {}, vcs=vcs)
    assert ok is False
    assert "stale" in reason.lower()
    assert "CI failing" not in reason


# ---------------------------------------------------------------------------
# preflight_pr — branch head resolution (ref_sha wiring for staleness)
# ---------------------------------------------------------------------------

def test_preflight_passes_resolved_branch_head_as_ref_sha():
    """The production call path resolves the worktree branch head and passes it
    as ``ref_sha`` so providers can claim build staleness end-to-end."""
    from autoswe.vcs import pr_gate

    task = make_task()
    vcs = _vcs(ci_state="success")

    with patch.object(pr_gate.worktree_mod, "worktree_path", return_value=Path("/tmp/wt-1")) as wt_p, \
         patch.object(pr_gate.worktree_mod, "resolve_branch_head", return_value="deadbeef") as rbh:
        ok, _ = preflight_pr(task, {}, {}, vcs=vcs, do_sync=False)

    assert ok is True
    # ref_sha was resolved and threaded into the CI read.
    vcs.get_ci_status.assert_called_once()
    (branch, ref_sha), _ = vcs.get_ci_status.call_args
    assert branch == "autoswe/issue-1"
    assert ref_sha == "deadbeef"
    assert wt_p.called and rbh.called


def test_preflight_ref_sha_none_when_head_unresolvable():
    """When the branch head can't be resolved (no worktree / dirty HEAD), the
    gate falls back to the exact no-ref_sha call — no staleness claim, no error."""
    from autoswe.vcs import pr_gate

    task = make_task()
    vcs = _vcs(ci_state="success")

    with patch.object(pr_gate.worktree_mod, "worktree_path", return_value=Path("/tmp/wt-1")), \
         patch.object(pr_gate.worktree_mod, "resolve_branch_head", return_value=None):
        ok, _ = preflight_pr(task, {}, {}, vcs=vcs, do_sync=False)

    assert ok is True
    (branch, ref_sha), _ = vcs.get_ci_status.call_args
    assert ref_sha is None


def test_preflight_ref_sha_none_without_owner_repo():
    """A task missing owner/repo can't locate a worktree, so ref_sha is None."""
    task = {"issue_number": 1, "base_branch": "main"}  # no owner/repo
    vcs = _vcs(ci_state="success")
    ok, _ = preflight_pr(task, {}, {}, vcs=vcs, do_sync=False)
    assert ok is True
    (_b, ref_sha), _ = vcs.get_ci_status.call_args
    assert ref_sha is None


# ---------------------------------------------------------------------------
# _policy — per-repo override resolution for string policies
# ---------------------------------------------------------------------------

def test_policy_defaults_when_neither_set():
    assert _policy("PR_CI_ERROR_POLICY", {}, {}, "block") == "block"


def test_policy_uses_cfg_value():
    assert _policy("PR_CI_ERROR_POLICY", {"PR_CI_ERROR_POLICY": "open"}, {}, "block") == "open"


def test_policy_repo_override_beats_cfg():
    assert _policy("PR_CI_ERROR_POLICY", {"PR_CI_ERROR_POLICY": "block"},
                   {"pr_ci_error_policy": "open"}, "block") == "open"


def test_policy_normalises_case_and_whitespace():
    assert _policy("PR_CI_ERROR_POLICY", {"PR_CI_ERROR_POLICY": "  OPEN  "}, {}, "block") == "open"


def test_policy_empty_value_falls_back_to_default():
    assert _policy("PR_CI_ERROR_POLICY", {"PR_CI_ERROR_POLICY": ""}, {}, "block") == "block"


def test_policy_unknown_value_falls_back_to_default():
    """An unknown value (not in *allowed*) is not silently accepted — it falls
    back to *default*, so a typo can't open the gate on unconsultable CI."""
    allowed = {"block", "open"}
    # cfg-level typo
    assert _policy("PR_CI_ERROR_POLICY", {"PR_CI_ERROR_POLICY": "blocked"}, {}, "block",
                   allowed=allowed) == "block"
    # per-repo override typo beats cfg, but is still an unknown value
    assert _policy("PR_CI_ERROR_POLICY", {"PR_CI_ERROR_POLICY": "block"},
                   {"pr_ci_error_policy": "openish"}, "block", allowed=allowed) == "block"
    # a valid normalised value still resolves normally
    assert _policy("PR_CI_ERROR_POLICY", {"PR_CI_ERROR_POLICY": "BLOCK"}, {}, "block",
                   allowed=allowed) == "block"
    assert _policy("PR_CI_ERROR_POLICY", {"PR_CI_ERROR_POLICY": " OPEN "}, {}, "block",
                   allowed=allowed) == "open"


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
    # Sync is off, so no sync worktree ops (clone/create/sync) happen. The CI
    # gate still resolves the branch head for staleness, which is a
    # worktree_path lookup — not a sync op.
    funcs = {c["func"] for c in git_fake.calls}
    assert funcs <= {"worktree_path"}


def test_do_sync_false_skips_sync_even_when_enabled(git_fake):
    """The adapter's auto-PR path passes do_sync=False (branch already synced)."""
    task = make_task()
    vcs = _vcs(ci_state="none")
    ok, reason = preflight_pr(task, {"PR_REQUIRE_SYNC": True}, {}, vcs=vcs, do_sync=False)
    assert ok is True
    # do_sync=False skips sync ops even though PR_REQUIRE_SYNC is on. Only the
    # CI gate's branch-head lookup may occur.
    funcs = {c["func"] for c in git_fake.calls}
    assert funcs <= {"worktree_path"}


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
