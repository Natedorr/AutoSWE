"""ensure_links — the idempotent cross-linkage writer (issue #245 §1.4).

Drives ``ensure_links`` with a scripted VCS mock and a mocked tracker and
asserts the *decisions* — which edges get written, which don't, and what is
persisted onto the queue entry — not the wire format (covered per-provider in
test_azure_vcs.py / test_azure_tracker.py).
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from autoswe.providers.base import Capability, LinkageState, NormalizedIssue
from autoswe.vcs.linkage import ensure_links, render_linkage_checklist


def _vcs(caps, *, get_linkage_state=None, branch_name="autoswe/issue-42"):
    vcs = MagicMock()
    vcs.capabilities.return_value = frozenset(caps)
    vcs.branch_name.return_value = branch_name
    vcs.get_linkage.return_value = get_linkage_state
    return vcs


def _task(**overrides):
    t = {"id": "o/r/42", "owner": "o", "repo": "r", "issue_number": 42, "pr_number": None}
    t.update(overrides)
    return t


def _repo_cfg():
    return {"provider": "github", "owner": "o", "repo": "r", "token": "t"}


# ---------------------------------------------------------------------------
# Steady state — fully linked task is a no-op
# ---------------------------------------------------------------------------

def test_ensure_links_no_op_when_fully_linked():
    vcs = _vcs(
        {Capability.PR_ISSUE_LINK, Capability.AUTO_CLOSE_ON_MERGE},
        get_linkage_state=LinkageState(
            branch_linked=True, pr_linked=True, closes_on_merge=True,
            pr_number=7, merge_state="clean",
        ),
    )
    task = _task(pr_number=7)

    state = ensure_links(task, _repo_cfg(), {}, phase="merge_observation", vcs=vcs)

    vcs.link_pr_to_issue.assert_not_called()
    vcs.link_branch_to_issue.assert_not_called()
    assert state is not None
    assert state.missing == ()
    assert task["linkage_missing"] == []
    assert task["linkage_state"]["pr_linked"] is True
    assert task["linkage_state"]["pr_number"] == 7


# ---------------------------------------------------------------------------
# Self-heal — a removed edge is re-established with a single write
# ---------------------------------------------------------------------------

def test_ensure_links_self_heals_removed_pr_link():
    vcs = _vcs(
        {Capability.PR_ISSUE_LINK},
        get_linkage_state=LinkageState(pr_number=7, pr_linked=False,
                                       missing=("pr_link", "closes")),
    )
    task = _task(pr_number=7)

    ensure_links(task, _repo_cfg(), {}, phase="pr_open", vcs=vcs)

    vcs.link_pr_to_issue.assert_called_once_with(42, 7)
    assert task["linkage_missing"] == ["closes"]
    assert task["linkage_state"]["pr_linked"] is True


def test_ensure_links_does_not_write_when_capability_declared_absent():
    vcs = _vcs(
        {Capability.MERGE_STATUS},  # no PR_ISSUE_LINK
        get_linkage_state=LinkageState(pr_number=7, pr_linked=False,
                                       missing=("pr_link", "closes")),
    )
    task = _task(pr_number=7)

    ensure_links(task, _repo_cfg(), {}, phase="pr_open", vcs=vcs)

    vcs.link_pr_to_issue.assert_not_called()
    assert "pr_link" in task["linkage_missing"]


# ---------------------------------------------------------------------------
# E5 close-on-merge — idempotent, capability-gated, opt-out respected
# ---------------------------------------------------------------------------

def _open_issue(state="open"):
    return NormalizedIssue(number=42, title="t", body="b", owner="o", repo="r", state=state)


def _tracker_mock(caps, issue_state="open"):
    tracker = MagicMock()
    tracker.capabilities.return_value = frozenset(caps)
    tracker.fetch_issue.return_value = _open_issue(issue_state)
    return tracker


def test_ensure_links_close_on_merge_owed_when_no_auto_close_cap():
    vcs = _vcs(
        {Capability.PR_ISSUE_LINK},
        get_linkage_state=LinkageState(pr_number=7, pr_linked=True,
                                       closes_on_merge=False, merged=True,
                                       merge_state="clean"),
    )
    tracker = _tracker_mock(frozenset())  # ADO-like: no AUTO_CLOSE_ON_MERGE
    task = _task(pr_number=7)

    with patch("autoswe.vcs.linkage.get_tracker", return_value=tracker):
        ensure_links(task, _repo_cfg(), {}, phase="merge_observation", vcs=vcs)

    tracker.close_issue.assert_called_once_with(42, reason="completed")
    assert "closes" not in task["linkage_missing"]


def test_ensure_links_repeated_merge_observation_does_not_reclose():
    vcs = _vcs(
        {Capability.PR_ISSUE_LINK},
        get_linkage_state=LinkageState(pr_number=7, pr_linked=True,
                                       closes_on_merge=False, merged=True,
                                       merge_state="clean"),
    )
    tracker = _tracker_mock(frozenset(), issue_state="closed")  # already terminal
    task = _task(pr_number=7)

    with patch("autoswe.vcs.linkage.get_tracker", return_value=tracker):
        ensure_links(task, _repo_cfg(), {}, phase="merge_observation", vcs=vcs)

    tracker.close_issue.assert_not_called()


def test_ensure_links_close_not_owed_when_closes_on_merge():
    vcs = _vcs(
        {Capability.PR_ISSUE_LINK, Capability.AUTO_CLOSE_ON_MERGE},
        get_linkage_state=LinkageState(pr_number=7, pr_linked=True,
                                       closes_on_merge=True, merged=True,
                                       merge_state="clean"),
    )
    tracker = _tracker_mock({Capability.AUTO_CLOSE_ON_MERGE})
    task = _task(pr_number=7)

    with patch("autoswe.vcs.linkage.get_tracker", return_value=tracker):
        ensure_links(task, _repo_cfg(), {}, phase="merge_observation", vcs=vcs)

    tracker.close_issue.assert_not_called()


def test_ensure_links_close_not_owed_when_not_merged():
    vcs = _vcs(
        {Capability.PR_ISSUE_LINK},
        get_linkage_state=LinkageState(pr_number=7, pr_linked=True,
                                       closes_on_merge=False, merged=False,
                                       merge_state="clean"),
    )
    tracker = _tracker_mock(frozenset())
    task = _task(pr_number=7)

    with patch("autoswe.vcs.linkage.get_tracker", return_value=tracker):
        ensure_links(task, _repo_cfg(), {}, phase="merge_observation", vcs=vcs)

    tracker.close_issue.assert_not_called()


def test_ensure_links_auto_close_opt_out_suppresses_close():
    vcs = _vcs(
        {Capability.PR_ISSUE_LINK},
        get_linkage_state=LinkageState(pr_number=7, pr_linked=True,
                                       closes_on_merge=False, merged=True,
                                       merge_state="clean"),
    )
    tracker = _tracker_mock(frozenset())
    task = _task(pr_number=7)

    with patch("autoswe.vcs.linkage.get_tracker", return_value=tracker):
        ensure_links(task, _repo_cfg(), {"AUTO_CLOSE_ON_MERGE": False},
                     phase="merge_observation", vcs=vcs)

    tracker.close_issue.assert_not_called()


def test_ensure_links_close_failure_records_closes_missing():
    vcs = _vcs(
        {Capability.PR_ISSUE_LINK},
        get_linkage_state=LinkageState(pr_number=7, pr_linked=True,
                                       closes_on_merge=False, merged=True,
                                       merge_state="clean"),
    )
    tracker = _tracker_mock(frozenset())
    tracker.close_issue.side_effect = RuntimeError("HTTP 500: boom")
    task = _task(pr_number=7)

    with patch("autoswe.vcs.linkage.get_tracker", return_value=tracker):
        ensure_links(task, _repo_cfg(), {}, phase="merge_observation", vcs=vcs)

    assert "closes" in task["linkage_missing"]


# ---------------------------------------------------------------------------
# E1 declared absence — ADO has no branch edge, so it is reported, not hidden
# ---------------------------------------------------------------------------

def test_azure_declared_branch_absence_recorded_in_missing():
    vcs = _vcs(
        {Capability.PR_ISSUE_LINK, Capability.MERGE_STATUS},  # ADO-like caps
        get_linkage_state=LinkageState(pr_number=7, pr_linked=True,
                                       missing=("branch", "closes")),
    )
    task = _task(pr_number=7)

    ensure_links(task, _repo_cfg(), {}, phase="merge_observation", vcs=vcs)

    assert "branch" in task["linkage_missing"]
    assert "closes" in task["linkage_missing"]
    assert "pr_link" not in task["linkage_missing"]


# ---------------------------------------------------------------------------
# Branch phase (E1)
# ---------------------------------------------------------------------------

def test_ensure_links_branch_phase_writes_when_capability_present():
    vcs = _vcs({Capability.BRANCH_LINK})
    task = _task()

    state = ensure_links(task, _repo_cfg(), {}, phase="branch", vcs=vcs, base_sha="abc123")

    vcs.link_branch_to_issue.assert_called_once_with(42, "abc123", "autoswe/issue-42")
    assert state.missing == ()
    assert "linkage_state" not in task  # branch phase persists nothing


def test_ensure_links_branch_phase_declared_absent_records_missing():
    vcs = _vcs({Capability.PR_ISSUE_LINK})  # no BRANCH_LINK
    task = _task()

    state = ensure_links(task, _repo_cfg(), {}, phase="branch", vcs=vcs, base_sha="abc123")

    vcs.link_branch_to_issue.assert_not_called()
    assert "branch" in state.missing


def test_ensure_links_branch_phase_no_base_sha_records_missing():
    vcs = _vcs({Capability.BRANCH_LINK})
    task = _task()

    state = ensure_links(task, _repo_cfg(), {}, phase="branch", vcs=vcs, base_sha=None)

    vcs.link_branch_to_issue.assert_not_called()
    assert "branch" in state.missing


# ---------------------------------------------------------------------------
# Degenerate inputs + checklist rendering
# ---------------------------------------------------------------------------

def test_ensure_links_none_task_returns_none():
    vcs = _vcs({Capability.PR_ISSUE_LINK})
    assert ensure_links(None, _repo_cfg(), {}, phase="pr_open", vcs=vcs) is None
    assert ensure_links({"owner": "o", "repo": "r"}, _repo_cfg(), {},
                        phase="pr_open", vcs=vcs) is None


def test_render_linkage_checklist_empty_without_state():
    assert render_linkage_checklist(_task()) == ""


def test_render_linkage_checklist_marks_edges():
    task = _task()
    task["linkage_state"] = {
        "branch_linked": False, "pr_linked": True, "closes_on_merge": False,
        "pr_number": 7, "merged": False, "merge_state": "clean",
    }
    task["linkage_missing"] = ["branch", "closes"]

    out = render_linkage_checklist(task)
    assert out.startswith("Linkage checklist:")
    assert "✗ (declared-unsupported or failed)" in out
    assert "E3 PR->issue" in out and "✓" in out
    assert "PR #7" in out
