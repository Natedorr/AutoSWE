"""Factory — dispatch repo_cfg to the correct provider implementation."""
from __future__ import annotations

from autoswe.providers.azure.tracker import AzureTracker
from autoswe.providers.azure.vcs import AzureVCS
from autoswe.providers.base import IssueTracker, VCSProvider
from autoswe.providers.github.tracker import GitHubTracker
from autoswe.providers.github.vcs import GitHubVCS

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_tracker(repo_cfg: dict) -> IssueTracker:
    """Return an IssueTracker for the given repo configuration.

    The ``provider`` field in repo_cfg selects the backend.
    """
    provider = repo_cfg.get("provider", "github").lower()
    if provider == "github":
        return GitHubTracker(repo_cfg)
    elif provider == "azure":
        return AzureTracker(repo_cfg)
    raise ValueError(f"Unknown provider: {provider}")


def get_vcs(repo_cfg: dict) -> VCSProvider:
    """Return a VCSProvider for the repo configuration."""
    provider = repo_cfg.get("provider", "github").lower()
    if provider == "github":
        return GitHubVCS(repo_cfg)
    elif provider == "azure":
        return AzureVCS(repo_cfg)
    raise ValueError(f"Unknown provider: {provider}")


# ---------------------------------------------------------------------------
# Helpers — build enriched repo_cfg from orchestrator args
# ---------------------------------------------------------------------------

def build_repo_cfg(owner: str, repo: str, cfg: dict, repos_cfg: dict | None = None,
                   provider: str | None = None) -> dict:
    """Build an enriched repo_cfg dict suitable for provider factory functions.

    Merges global config (GITHUB_TOKEN) with per-repo overrides and owner/repo.
    For Azure, repos_cfg keys are ``org/project/repo`` (3-part).

    If *provider* is given and the repos_cfg lookup misses (e.g. because dispatch
    only has a 2-part key for an Azure 3-part repo), use *provider* instead of
    defaulting to GitHub.
    """
    # Build all possible keys to check in repos_cfg
    repo_key = f"{owner}/{repo}"
    # The repo_key handles both 2-part ("owner/repo") and 3-part ("org/project/repo")
    # since f"{owner}/{repo}" produces the correct format in both cases.

    rcfg = {
        "owner": owner,
        "repo": repo,
        "provider": "github",
    }
    if repos_cfg and repo_key in repos_cfg:
        rcfg.update(repos_cfg[repo_key])
    # If the lookup missed and caller gave us a provider (e.g. from a task that
    # sync already set), trust it instead of the GitHub default.
    elif provider:
        rcfg["provider"] = provider
    # Ensure owner/repo override per-repo config.
    # For Azure, preserve the org/project/repo fields extracted from the 3-part
    # repos.json key — don't overwrite them with the generic owner/repo values.
    if rcfg.get("provider", "").lower() == "azure":
        rcfg["owner"] = owner
        # Only set rcfg["repo"] if it wasn't already set to a non-empty value
        # by the repos_cfg update (which provides the actual repo name for Azure)
        if not rcfg.get("repo"):
            rcfg["repo"] = repo
    else:
        rcfg["owner"] = owner
        rcfg["repo"] = repo
    return rcfg
