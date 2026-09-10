"""Capability declarations — providers make absence queryable, not silent (issue #245 §1).

The two platforms are not symmetric. Declaring capabilities turns the old
silent no-ops into deliberate, queryable degradations: a consumer gates on a
capability and logs a one-time note when it is absent, rather than fabricating
a pass. These tests pin the declared sets so a provider cannot silently drop
or add a capability without the suite noticing.
"""
from __future__ import annotations

from autoswe.providers.azure.tracker import AzureTracker
from autoswe.providers.azure.vcs import AzureVCS
from autoswe.providers.base import Capability
from autoswe.providers.github.tracker import GitHubTracker
from autoswe.providers.github.vcs import GitHubVCS


def _gh_vcs():
    return GitHubVCS({"owner": "o", "repo": "r", "token": "t"})


def _az_vcs():
    return AzureVCS({"org": "o", "project": "p", "pat": "t"})


def _gh_tracker():
    return GitHubTracker({"owner": "o", "repo": "r", "token": "t"})


def _az_tracker():
    return AzureTracker({"org": "o", "project": "p", "pat": "t"})


# ---------------------------------------------------------------------------
# VCS capability sets (edges E1–E5 live here)
# ---------------------------------------------------------------------------

def test_github_vcs_declares_all_capabilities():
    """GitHub is the fully-connected platform: every edge is platform-managed.

    BRANCH_LINK, PR_ISSUE_LINK, AUTO_CLOSE_ON_MERGE, CI_PER_COMMIT, CI_LOGS and
    MERGE_STATUS are all supported, so the set is exactly the full enum.
    """
    assert _gh_vcs().capabilities() == frozenset(Capability)
    assert set(_gh_vcs().capabilities()) == {
        Capability.BRANCH_LINK,
        Capability.PR_ISSUE_LINK,
        Capability.AUTO_CLOSE_ON_MERGE,
        Capability.CI_PER_COMMIT,
        Capability.CI_LOGS,
        Capability.MERGE_STATUS,
    }


def test_azure_vcs_declares_exact_capability_set():
    """Azure declares PR/CI/merge edges but NOT branch or auto-close.

    ADO has no platform-managed issue→branch link (BRANCH_LINK absent — the
    branch is only recoverable by name, E1 declared absence) and merge does not
    auto-close the work item (AUTO_CLOSE_ON_MERGE absent — the tracker must
    close it, E5). It does expose the machine-readable PR↔work-item link
    (PR_ISSUE_LINK), per-commit CI, CI logs, and mergeability (MERGE_STATUS).
    """
    caps = _az_vcs().capabilities()
    assert caps == frozenset({
        Capability.PR_ISSUE_LINK,
        Capability.CI_PER_COMMIT,
        Capability.CI_LOGS,
        Capability.MERGE_STATUS,
    })
    # The declared absences — the whole point of the model.
    assert Capability.BRANCH_LINK not in caps
    assert Capability.AUTO_CLOSE_ON_MERGE not in caps


def test_capability_sets_are_disjoint_on_the_asymmetric_edges():
    """The two platforms differ exactly on the two non-symmetric edges.

    Guard against a future provider 'fixing' an absence without updating the
    model: if GitHub ever lost one of these or Azure gained one, the intended
    asymmetry is broken.
    """
    gh = _gh_vcs().capabilities()
    az = _az_vcs().capabilities()
    assert gh - az == {
        Capability.BRANCH_LINK,
        Capability.AUTO_CLOSE_ON_MERGE,
    }
    assert az - gh == frozenset()  # Azure never claims something GitHub lacks


# ---------------------------------------------------------------------------
# Tracker capability sets
# ---------------------------------------------------------------------------

def test_github_tracker_declares_auto_close_on_merge():
    """GitHub closes the issue when the PR merges — no explicit close call needed."""
    assert _gh_tracker().capabilities() == frozenset({Capability.AUTO_CLOSE_ON_MERGE})


def test_azure_tracker_declares_no_capabilities():
    """Azure's tracker declares nothing: merge does not close the work item, so
    ``close_issue`` is a real write the operator/tracker must perform (E5)."""
    assert _az_tracker().capabilities() == frozenset()


# ---------------------------------------------------------------------------
# Fake parity — every provider instance (real and fake) exposes the method
# ---------------------------------------------------------------------------

def test_every_provider_instance_exposes_capabilities():
    """Fake-parity: the ``capabilities`` method exists on every provider instance
    we build in tests, so a fake that omits it cannot silently diverge from the
    real provider's declared-absence semantics."""
    for inst in (_gh_vcs(), _az_vcs(), _gh_tracker(), _az_tracker()):
        assert callable(getattr(inst, "capabilities"))
        assert isinstance(inst.capabilities(), frozenset)
