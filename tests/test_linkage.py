"""ensure_links — the idempotent cross-linkage writer (issue #245 §1.4).

Provider-agnostic: ``ensure_links`` talks only through the protocol seam
(``get_linkage`` / ``link_pr_to_issue`` / ``link_branch_to_issue``) and the
declared capabilities, so these tests drive it with a scripted VCS mock and a
mocked tracker and assert the *decisions* — which edges get written, which
don't, and what is persisted onto the queue entry — not the wire format (which
the per-provider files cover).

The invariant under test everywhere: reads come first, only *missing* edges are
written, and a steady-state task is a cheap no-op. Self-heal and declared
absence are both expressed through ``LinkageState.missing`` (edge *names*), so
the operator sees exactly what exists on a task — never a silent skip.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from autoswe.providers.base import Capability, LinkageState, NormalizedIssue
from autoswe.vcs.linkage import ensure_links, render_linkage_checklist


def _vcs(caps, *, get_linkage_state=None, branch_name="autoswe/issue-42"):
    """A scripted VCSProvider mock.

    ``caps`` must be a *real* frozenset — ``ensure_links`` does
    ``Capability.X in caps`` and a bare MagicMock answer would misbehave under
    the membership test.
    """
    vcs = MagicMock()
    vcs.capabilities.return_value = frozenset(caps)
    vcs.branch_name.return_value = branch_name
    vcs.get_linkage.return_value = get_linkage_state
    return vcs


def _task(**overrides):
    t = {"id": "o/r/42", "owner": "o", "repo": "r", "issue_number": 42,
         "pr_number": None}
    t.update(overrides)
    return t


def _repo_cfg():
    return {"provider": "github", "owner": "o", "repo": "r", "token": "t"}


# ---------------------------------------------------------------------------
# Steady state — fully linked task is a no-op
# ---------------------------------------------------------------------------

def test_ensure_links_no_op_when_fully_linked():
    """When every edge is established, ensure_links issues no writes at all."""
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
    # Persisted onto the queue entry for queue status / /sync.
    assert task["linkage_missing"] == []
    assert task["linkage_state"]["pr_linked"] is True
    assert task["linkage_state"]["pr_number"] == 7


# ---------------------------------------------------------------------------
# Self-heal — a removed edge is re-established with a single write
# ---------------------------------------------------------------------------

def test_ensure_links_self_heals_removed_pr_link():
    """A PR that lost its machine-readable link (hand-edited body / crash) is
    re-linked with exactly one write, and the edge drops out of missing."""
    vcs = _vcs(
        {Capability.PR_ISSUE_LINK},
        get_linkage_state=LinkageState(pr_number=7, pr_linked=False,
                                       missing=("pr_link", "closes")),
    )
    task = _task(pr_number=7)

    ensure_links(task, _repo_cfg(), {}, phase="pr_open", vcs=vcs)

    vcs.link_pr_to_issue.assert_called_once_with(42, 7)
    assert task["linkage_missing"] == ["closes"]  # pr_link healed away
    assert task["linkage_state"]["pr_linked"] is True


def test_ensure_links_does_not_write_when_capability_declared_absent():
    """A platform that declares no PR_ISSUE_LINK gets no link_pr_to_issue write —
    the absence is recorded in missing, never silently skipped as a no-op that
    looks like success."""
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
    return NormalizedIssue(number=42, title="t", body="b", owner="o", repo="r",
                           state=state)


def test_ensure_links_close_on_merge_owed_when_no_auto_close_cap():
    """A platform that does NOT declare AUTO_CLOSE_ON_MERGE owes the explicit
    close_issue write after a merge (this is the ADO case, edge E5)."""
    vcs = _vcs(
        {Capability.PR_ISSUE_LINK},  # no AUTO_CLOSE_ON_MERGE
        get_linkage_state=LinkageState(pr_number=7, pr_linked=True,
                                       closes_on_merge=False, merged=True,
                                       merge_state="clean"),
    )
    tracker = MagicMock()
    tracker.fetch_issue.return_value = _open_issue("open")
    task = _task(pr_number=7)

    with patch("autoswe.vcs.linkage.get_tracker", return_value=tracker):
        ensure_links(task, _repo_cfg(), {}, phase="merge_observation", vcs=vcs)

    tracker.close_issue.assert_called_once_with(42, reason="completed")
    assert "closes" not in task["linkage_missing"]


def test_ensure_links_repeated_merge_observation_does_not_reclose():
    """Idempotency: a second merge_observation where the issue is already
    terminal issues NO close write — repeated polls must not re-close."""
    vcs = _vcs(
        {Capability.PR_ISSUE_LINK},  # no AUTO_CLOSE_ON_MERGE -> close owed
        get_linkage_state=LinkageState(pr_number=7, pr_linked=True,
                                       closes_on_merge=False, merged=True,
                                       merge_state="clean"),
    )
    tracker = MagicMock()
    tracker.fetch_issue.return_value = _open_issue("closed")  # already terminal
    task = _task(pr_number=7)

    with patch("autoswe.vcs.linkage.get_tracker", return_value=tracker):
        ensure_links(task, _repo_cfg(), {}, phase="merge_observation", vcs=vcs)

    tracker.close_issue.assert_not_called()


def test_ensure_links_close_not_owed_when_closes_on_merge():
    """On a platform that DOES auto-close (GitHub) and the closing keyword
    registered (closes_on_merge=True), the close is not owed — no write."""
    vcs = _vcs(
        {Capability.PR_ISSUE_LINK, Capability.AUTO_CLOSE_ON_MERGE},
        get_linkage_state=LinkageState(pr_number=7, pr_linked=True,
                                       closes_on_merge=True, merged=True,
                                       merge_state="clean"),
    )
    tracker = MagicMock()
    task = _task(pr_number=7)

    with patch("autoswe.vcs.linkage.get_tracker", return_value=tracker):
        ensure_links(task, _repo_cfg(), {}, phase="merge_observation", vcs=vcs)

    tracker.close_issue.assert_not_called()


def test_ensure_links_close_not_owed_when_not_merged():
    """No merge observed → no close is owed regardless of the capability."""
    vcs = _vcs(
        {Capability.PR_ISSUE_LINK},  # no auto-close cap, so a merge WOULD owe
        get_linkage_state=LinkageState(pr_number=7, pr_linked=True,
                                       closes_on_merge=False, merged=False,
                                       merge_state="clean"),
    )
    tracker = MagicMock()
    task = _task(pr_number=7)

    with patch("autoswe.vcs.linkage.get_tracker", return_value=tracker):
        ensure_links(task, _repo_cfg(), {}, phase="merge_observation", vcs=vcs)

    tracker.close_issue.assert_not_called()


def test_ensure_links_auto_close_opt_out_suppresses_close():
    """AUTO_CLOSE_ON_MERGE=False in cfg opts out of the explicit close entirely —
    even on a platform that would otherwise owe it."""
    vcs = _vcs(
        {Capability.PR_ISSUE_LINK},
        get_linkage_state=LinkageState(pr_number=7, pr_linked=True,
                                       closes_on_merge=False, merged=True,
                                       merge_state="clean"),
    )
    tracker = MagicMock()
    task = _task(pr_number=7)

    with patch("autoswe.vcs.linkage.get_tracker", return_value=tracker):
        ensure_links(task, _repo_cfg(), {"AUTO_CLOSE_ON_MERGE": False},
                     phase="merge_observation", vcs=vcs)

    tracker.close_issue.assert_not_called()


def test_ensure_links_close_failure_records_closes_missing():
    """A failed close_issue write (non-400) is recorded in missing, not raised —
    linkage bookkeeping never blocks the merge it accompanies."""
    vcs = _vcs(
        {Capability.PR_ISSUE_LINK},
        get_linkage_state=LinkageState(pr_number=7, pr_linked=True,
                                       closes_on_merge=False, merged=True,
                                       merge_state="clean"),
    )
    tracker = MagicMock()
    tracker.fetch_issue.return_value = _open_issue("open")
    tracker.close_issue.side_effect = RuntimeError("HTTP 500: boom")
    task = _task(pr_number=7)

    with patch("autoswe.vcs.linkage.get_tracker", return_value=tracker):
        ensure_links(task, _repo_cfg(), {}, phase="merge_observation", vcs=vcs)

    assert "closes" in task["linkage_missing"]


# ---------------------------------------------------------------------------
# E1 declared absence — ADO has no branch edge, so it is reported, not hidden
# ---------------------------------------------------------------------------

def test_azure_declared_branch_absence_recorded_in_missing():
    """ADO declares no BRANCH_LINK: the branch edge is reported in
    ``linkage_missing`` (so the checklist/welcome note surfaces it) rather than
    being silently omitted. get_linkage on ADO always lists 'branch' + 'closes'
    as missing because neither is platform-managed."""
    vcs = _vcs(
        {Capability.PR_ISSUE_LINK, Capability.MERGE_STATUS},  # ADO-like caps
        get_linkage_state=LinkageState(pr_number=7, pr_linked=True,
                                       missing=("branch", "closes")),
    )
    task = _task(pr_number=7)

    ensure_links(task, _repo_cfg(), {}, phase="merge_observation", vcs=vcs)

    assert "branch" in task["linkage_missing"]
    assert "closes" in task["linkage_missing"]
    # The established pr_link is NOT reported missing.
    assert "pr_link" not in task["linkage_missing"]


# ---------------------------------------------------------------------------
# Degenerate inputs + checklist rendering
# ---------------------------------------------------------------------------

def test_ensure_links_none_task_returns_none():
    """A None task (or one without issue_number) yields None — nothing to do."""
    vcs = _vcs({Capability.PR_ISSUE_LINK})
    assert ensure_links(None, _repo_cfg(), {}, phase="pr_open", vcs=vcs) is None
    assert ensure_links({"owner": "o", "repo": "r"}, _repo_cfg(), {},
                        phase="pr_open", vcs=vcs) is None


def test_ensure_links_branch_phase_does_not_persist():
    """The branch phase runs at worktree creation on a throwaway dict, not the
    queue entry, so it returns a state but does not persist linkage_state."""
    # ADO-like: get_linkage reports the branch edge as missing (no BRANCH_LINK
    # capability), and since BRANCH_LINK is not declared there is no write.
    vcs = _vcs({Capability.PR_ISSUE_LINK},
               get_linkage_state=LinkageState(missing=("branch",)))
    task = _task()

    state = ensure_links(task, _repo_cfg(), {}, phase="branch",
                         vcs=vcs, base_sha="abc123")

    assert state is not None
    assert "branch" in state.missing
    vcs.link_branch_to_issue.assert_not_called()
    assert "linkage_state" not in task  # branch phase persists nothing


def test_render_linkage_checklist_empty_without_state():
    """A task with no persisted linkage_state renders nothing (no PR yet)."""
    assert render_linkage_checklist(_task()) == ""


def test_render_linkage_checklist_marks_edges():
    """render_linkage_checklist renders established edges as ✓ and missing
    declared-absences with the operator-facing annotation."""
    task = _task()
    task["linkage_state"] = {
        "branch_linked": False, "pr_linked": True, "closes_on_merge": False,
        "pr_number": 7, "merged": False, "merge_state": "clean",
    }
    task["linkage_missing"] = ["branch", "closes"]

    out = render_linkage_checklist(task)
    assert out.startswith("Linkage checklist:")
    # E1 absent + declared-unsupported annotation (in missing).
    assert "✗ (declared-unsupported or failed)" in out
    # E3 established.
    assert "E3 PR→issue" in out and "✓" in out
    # PR line present because pr_number is set.
    assert "PR #7" in out
