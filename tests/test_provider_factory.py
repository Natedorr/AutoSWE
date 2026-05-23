"""Tests for autoswe.providers.factory — dispatch on provider field."""
import pytest

from autoswe.providers.azure.tracker import AzureTracker
from autoswe.providers.azure.vcs import AzureVCS
from autoswe.providers.base import IssueTracker, VCSProvider
from autoswe.providers.factory import build_repo_cfg, get_tracker, get_vcs
from autoswe.providers.github.tracker import GitHubTracker
from autoswe.providers.github.vcs import GitHubVCS


def test_get_tracker_defaults_to_github():
    """When provider field is missing, factory defaults to GitHub."""
    repo_cfg = {"owner": "o", "repo": "r"}
    tracker = get_tracker(repo_cfg)
    assert isinstance(tracker, GitHubTracker)
    assert isinstance(tracker, IssueTracker)


def test_get_tracker_github_by_name():
    """Explicit provider: github returns GitHubTracker."""
    repo_cfg = {"owner": "o", "repo": "r", "provider": "github"}
    tracker = get_tracker(repo_cfg)
    assert isinstance(tracker, GitHubTracker)


def test_get_tracker_github_case_insensitive():
    """provider field is case-insensitive."""
    for val in ("GitHub", "GITHUB", "gItHuB"):
        repo_cfg = {"owner": "o", "repo": "r", "provider": val}
        tracker = get_tracker(repo_cfg)
        assert isinstance(tracker, GitHubTracker)


def test_get_vcs_defaults_to_github():
    """When provider field is missing, VCS factory defaults to GitHub."""
    repo_cfg = {"owner": "o", "repo": "r"}
    vcs = get_vcs(repo_cfg)
    assert isinstance(vcs, GitHubVCS)
    assert isinstance(vcs, VCSProvider)


def test_get_vcs_github_by_name():
    """Explicit provider: github returns GitHubVCS."""
    repo_cfg = {"owner": "o", "repo": "r", "provider": "github"}
    vcs = get_vcs(repo_cfg)
    assert isinstance(vcs, GitHubVCS)


def test_unknown_provider_raises_value_error_tracker():
    """get_tracker raises ValueError for unknown providers."""
    with pytest.raises(ValueError, match="Unknown provider"):
        get_tracker({"owner": "o", "repo": "r", "provider": "bitbucket"})


def test_unknown_provider_raises_value_error_vcs():
    """get_vcs raises ValueError for unknown providers."""
    with pytest.raises(ValueError, match="Unknown provider"):
        get_vcs({"owner": "o", "repo": "r", "provider": "gitlab"})


# ---------------------------------------------------------------------------
# Azure DevOps provider dispatch
# ---------------------------------------------------------------------------

def test_get_tracker_azure_by_name():
    """Explicit provider: azure returns AzureTracker."""
    repo_cfg = {"org": "o", "project": "p", "repo": "r", "provider": "azure", "pat": "fake_pat"}
    tracker = get_tracker(repo_cfg)
    assert isinstance(tracker, AzureTracker)
    assert isinstance(tracker, IssueTracker)


def test_get_tracker_azure_case_insensitive():
    """provider field is case-insensitive for azure."""
    for val in ("azure", "Azure", "AZURE"):
        repo_cfg = {"org": "o", "project": "p", "repo": "r", "provider": val, "pat": "fake_pat"}
        tracker = get_tracker(repo_cfg)
        assert isinstance(tracker, AzureTracker)


def test_get_vcs_azure_by_name():
    """Explicit provider: azure returns AzureVCS."""
    repo_cfg = {"org": "o", "project": "p", "repo": "r", "provider": "azure", "pat": "fake_pat"}
    vcs = get_vcs(repo_cfg)
    assert isinstance(vcs, AzureVCS)
    assert isinstance(vcs, VCSProvider)


def test_get_vcs_azure_case_insensitive():
    """provider field is case-insensitive for azure VCS."""
    for val in ("azure", "Azure", "AZURE"):
        repo_cfg = {"org": "o", "project": "p", "repo": "r", "provider": val, "pat": "fake_pat"}
        vcs = get_vcs(repo_cfg)
        assert isinstance(vcs, AzureVCS)


# ---------------------------------------------------------------------------
# build_repo_cfg helper
# ---------------------------------------------------------------------------

def test_build_repo_cfg_github_defaults():
    """build_repo_cfg defaults provider to github."""
    rcfg = build_repo_cfg("owner", "repo", {}, {})
    assert rcfg["provider"] == "github"
    assert rcfg["owner"] == "owner"
    assert rcfg["repo"] == "repo"
    assert "GITHUB_TOKEN" not in rcfg


def test_build_repo_cfg_github_with_repos_cfg():
    """build_repo_cfg merges per-repo overrides for GitHub."""
    cfg = {"GITHUB_TOKEN": "ghp_123"}
    repos_cfg = {
        "owner/repo": {
            "provider": "github",
            "base_branch": "develop",
            "model": "claude-sonnet-4-6",
        }
    }
    rcfg = build_repo_cfg("owner", "repo", cfg, repos_cfg)
    assert rcfg["provider"] == "github"
    assert rcfg["base_branch"] == "develop"
    assert rcfg["model"] == "claude-sonnet-4-6"
    assert rcfg["owner"] == "owner"
    assert rcfg["repo"] == "repo"


def test_build_repo_cfg_azure_3part_key():
    """build_repo_cfg handles Azure 3-part keys (org/project/repo)."""
    cfg = {"GITHUB_TOKEN": "ghp_123"}
    repos_cfg = {
        "my-org/my-proj/my-repo": {
            "provider": "azure",
            "pat": "ado_pat_123",
            "base_branch": "main",
        }
    }
    rcfg = build_repo_cfg("my-org/my-proj", "my-repo", cfg, repos_cfg)
    assert rcfg["provider"] == "azure"
    assert rcfg["pat"] == "ado_pat_123"
    assert rcfg["owner"] == "my-org/my-proj"
    assert rcfg["repo"] == "my-repo"


def test_build_repo_cfg_azure_finds_by_full_key():
    """build_repo_cfg finds Azure entry by full key."""
    cfg = {"GITHUB_TOKEN": "ghp_123"}
    repos_cfg = {
        "my-org/my-proj/my-repo": {
            "provider": "azure",
            "pat": "ado_pat_123",
        }
    }
    # Full key should match directly
    rcfg = build_repo_cfg("my-org/my-proj", "my-repo", cfg, repos_cfg)
    assert rcfg["provider"] == "azure"
    assert rcfg["pat"] == "ado_pat_123"


def test_build_repo_cfg_azure_preserves_org_project_repo():
    """build_repo_cfg preserves org/project/repo from repos_cfg for Azure.

    Regression test: previously, rcfg["repo"] was unconditionally overwritten
    with the raw 'repo' arg (e.g. 'testProject/testProject'), clobbering the
    actual repo name from repos_cfg. This caused malformed clone URLs with
    triple slashes (dev.azure.com///_git/...).
    """
    cfg = {"GITHUB_TOKEN": "ghp_123"}
    # This mirrors what load_repos_config() does: extracts org/project/repo
    # from the 3-part key and stores them in the entry dict.
    repos_cfg = {
        "natedorr/testProject/testProject": {
            "provider": "azure",
            "org": "natedorr",
            "project": "testProject",
            "repo": "testProject",
            "pat": "ado_pat_123",
        }
    }
    # Simulates what happens when sync_all dispatches with
    # owner="natedorr", repo="testProject/testProject"
    rcfg = build_repo_cfg("natedorr", "testProject/testProject", cfg, repos_cfg)
    assert rcfg["provider"] == "azure"
    assert rcfg["org"] == "natedorr"
    assert rcfg["project"] == "testProject"
    assert rcfg["repo"] == "testProject"  # Must NOT be "testProject/testProject"
    assert rcfg["owner"] == "natedorr"
    assert rcfg["pat"] == "ado_pat_123"


def test_build_repo_cfg_azure_vcs_produces_valid_clone_url():
    """End-to-end: build_repo_cfg + AzureVCS produces a valid clone URL.

    Regression test for the triple-slash clone URL bug.
    """
    cfg = {"GITHUB_TOKEN": "ghp_123"}
    repos_cfg = {
        "natedorr/testProject/testProject": {
            "provider": "azure",
            "org": "natedorr",
            "project": "testProject",
            "repo": "testProject",
            "pat": "ado_pat_123",
        }
    }
    rcfg = build_repo_cfg("natedorr", "testProject/testProject", cfg, repos_cfg)
    vcs = get_vcs(rcfg)
    url = vcs.clone_url(rcfg)
    assert "dev.azure.com///_git/" not in url
    assert url == "https://autoswe:ado_pat_123@dev.azure.com/natedorr/testProject/_git/testProject"
