"""Capability declarations — providers make absence queryable, not silent (issue #245 §0).

Declaring capabilities turns the old silent no-ops into deliberate, queryable
degradations: a consumer gates on a capability rather than fabricating a pass.
These tests pin the declared sets so a provider cannot silently drop or add a
capability without the suite noticing.
"""
from __future__ import annotations

from autoswe.providers.azure.tracker import AzureTracker
from autoswe.providers.azure.vcs import AzureVCS
from autoswe.providers.base import Capability, IssueTracker, VCSProvider
from autoswe.providers.factory import get_tracker, get_vcs
from autoswe.providers.github.tracker import GitHubTracker
from autoswe.providers.github.vcs import GitHubVCS


def _gh_vcs():
    return GitHubVCS({"owner": "o", "repo": "r", "token": "t"})


def _az_vcs():
    return AzureVCS({"org": "o", "project": "p", "repo": "r", "pat": "t"})


def _gh_tracker():
    return GitHubTracker({"owner": "o", "repo": "r", "token": "t"})


def _az_tracker():
    return AzureTracker({"org": "o", "project": "p", "repo": "r", "pat": "t"})


# ---------------------------------------------------------------------------
# VCS capability sets
# ---------------------------------------------------------------------------

def test_github_vcs_declares_all_capabilities():
    """GitHub is the fully-connected platform: every edge is supported."""
    assert _gh_vcs().capabilities() == frozenset(Capability)


def test_azure_vcs_declares_exact_capability_set():
    """Azure declares PR/CI/merge edges but NOT branch-link.

    ADO has no verified platform-managed issue->branch link (BRANCH_LINK
    absent — unverified per plan §1.3, so the declared-absent no-op stays).
    """
    caps = _az_vcs().capabilities()
    assert caps == frozenset({
        Capability.PR_ISSUE_LINK,
        Capability.CI_PER_COMMIT,
        Capability.CI_LOGS,
        Capability.MERGE_STATUS,
    })
    assert Capability.BRANCH_LINK not in caps


def test_vcs_capability_sets_differ_exactly_on_branch_link():
    """The two platforms differ exactly on the unverified branch-link edge."""
    gh = _gh_vcs().capabilities()
    az = _az_vcs().capabilities()
    assert gh - az == {Capability.BRANCH_LINK, Capability.AUTO_CLOSE_ON_MERGE}
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
# Fake parity — every provider instance exposes capabilities()
# ---------------------------------------------------------------------------

def test_every_provider_instance_exposes_capabilities():
    for inst in (_gh_vcs(), _az_vcs(), _gh_tracker(), _az_tracker()):
        assert callable(inst.capabilities)
        assert isinstance(inst.capabilities(), frozenset)


# ---------------------------------------------------------------------------
# Factory conformance — get_vcs/get_tracker assert structural protocol match
# ---------------------------------------------------------------------------

def test_get_tracker_conforms_to_protocol_for_both_providers():
    assert isinstance(
        get_tracker({"owner": "o", "repo": "r", "provider": "github", "token": "t"}),
        IssueTracker,
    )
    assert isinstance(
        get_tracker({"org": "o", "project": "p", "repo": "r", "provider": "azure", "pat": "t"}),
        IssueTracker,
    )


def test_get_vcs_conforms_to_protocol_for_both_providers():
    assert isinstance(
        get_vcs({"owner": "o", "repo": "r", "provider": "github", "token": "t"}),
        VCSProvider,
    )
    assert isinstance(
        get_vcs({"org": "o", "project": "p", "repo": "r", "provider": "azure", "pat": "t"}),
        VCSProvider,
    )
