"""Provider registry + repo_cfg construction.

Adding a third provider now costs **one provider package** (a tracker + a VCS
with the ``normalize_comment_body`` / ``worktree_path_parts`` / URL hooks)
**plus one registry entry** here — no scattered if/elif edits outside the
provider package (issue #168, S5 "provider seam").
"""
from __future__ import annotations

from autoswe.providers.azure.tracker import AzureTracker
from autoswe.providers.azure.vcs import AzureVCS
from autoswe.providers.base import IssueTracker, VCSProvider
from autoswe.providers.github.tracker import GitHubTracker
from autoswe.providers.github.vcs import GitHubVCS

# ---------------------------------------------------------------------------
# Registry — the single place that knows which classes implement which name
# ---------------------------------------------------------------------------

TRACKERS: dict[str, type[IssueTracker]] = {
    "github": GitHubTracker,
    "azure": AzureTracker,
}

VCSS: dict[str, type[VCSProvider]] = {
    "github": GitHubVCS,
    "azure": AzureVCS,
}


def provider_names() -> list[str]:
    """All registered provider names (for CLI choices / validation)."""
    return sorted(TRACKERS)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_tracker(repo_cfg: dict) -> IssueTracker:
    """Return an IssueTracker for the given repo configuration.

    The ``provider`` field in repo_cfg selects the backend.
    """
    provider = repo_cfg.get("provider", "github").lower()
    try:
        return TRACKERS[provider](repo_cfg)
    except KeyError:
        raise ValueError(f"Unknown provider: {provider}") from None


def get_vcs(repo_cfg: dict) -> VCSProvider:
    """Return a VCSProvider for the repo configuration."""
    provider = repo_cfg.get("provider", "github").lower()
    try:
        return VCSS[provider](repo_cfg)
    except KeyError:
        raise ValueError(f"Unknown provider: {provider}") from None


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

    Azure normalisation (issue #168 F-08): for provider "azure", ``org``,
    ``project`` and ``repo`` are **always** populated on the returned dict,
    regardless of which shape the caller used (3-part repos.json key,
    ``owner="org/project"``, or ``repo="project/repo"``). Callers may rely on
    those keys without re-deriving them heuristically.
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

    prov = rcfg.get("provider", "github").lower()

    if prov == "azure":
        # Normalise Azure parts so org/project/repo are always present.
        # Callers reach here with one of:
        #   owner="org/project", repo="repo"         (3-part key split at "/")
        #   owner="org", repo="project/repo"         (repos.json 3-part value)
        #   org/project/repo already set by repos_cfg update (authoritative)
        org = rcfg.get("org", "")
        project = rcfg.get("project", "")
        repo_val = rcfg.get("repo", "")
        if not org or not project:
            if "/" in owner and "/" not in repo_val:
                org_part, _, proj_part = owner.partition("/")
                org, project = org_part, proj_part
            elif "/" in repo_val:
                proj_part, _, repo_part = repo_val.partition("/")
                org, project = owner, proj_part
                if repo_part:
                    repo_val = repo_part
        rcfg.update(owner=owner, repo=repo_val, org=org, project=project)
    else:
        # Ensure owner/repo override per-repo config.
        rcfg["owner"] = owner
        rcfg["repo"] = repo
    return rcfg
