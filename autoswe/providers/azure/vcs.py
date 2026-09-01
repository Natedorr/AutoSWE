"""Azure DevOps VCSProvider — wraps Azure Repos REST API.

Handles clone URLs, branch naming, PR discovery, and PR creation via the
Azure DevOps REST API.
"""
from __future__ import annotations

from autoswe.core.logging_utils import get_debug_logger
from autoswe.core.redact import redact_outbound
from autoswe.providers.azure.api import (
    _ado_api_version,
    _encode_path_segment,
    _normalize_azure_parts,
    ado_get,
    ado_post,
)
from autoswe.providers.base import CIStatus, PRResult

dbg = get_debug_logger()

# Azure Pipelines build statuses/results
_PENDING_STATUSES = {"notStarted", "inProgress", "postponed", "cancelling"}
_FAILURE_RESULTS = {"failed", "canceled"}
_SUCCESS_RESULTS = {"succeeded", "partiallySucceeded"}


class AzureVCS:
    """Azure DevOps-backed VCS provider.

    ``repo_cfg`` must contain::

        {
            "provider": "azure",
            "org": "my-org",
            "project": "my-project",
            "repo": "my-repo",       # repo name within the project
            "pat": "azure_pat_here",
        }
    """

    def __init__(self, repo_cfg: dict):
        self._repo_cfg = repo_cfg
        self._pat = repo_cfg.get("pat") or repo_cfg.get("token", "")
        # Single source of org/project/repo partition (issue #168 F-08):
        # build_repo_cfg normalises the main path; _normalize_azure_parts
        # covers inline throwaway repo_cfg dicts that skip build_repo_cfg.
        self._org, self._project, self._repo = _normalize_azure_parts(repo_cfg)
        # Raw owner, kept only for the filesystem worktree layout when the
        # config is a degenerate 2-part shape (owner="o", repo="r") that
        # _normalize_azure_parts cannot split into org/project/repo.
        self._owner = repo_cfg.get("owner", "")

        # URL-encode for safe use in REST API request URLs
        self._org_enc = _encode_path_segment(self._org)
        self._project_enc = _encode_path_segment(self._project)
        self._repo_enc = _encode_path_segment(self._repo)

    # ---- Repo ID resolution (moved from AzureTracker; VCS-side since it
    # feeds web-URL construction) ----

    def resolve_repo_id(self) -> str | None:
        """Resolve the Git repository UUID for this repo.

        Azure DevOps web URLs require the repo UUID (not the display name)
        in the `_git/{repo-id}/...` path segment. This method queries the
        repos API, finds the repo matching self._repo by name, and returns
        its UUID. Result is cached on first successful call.

        Returns the UUID string, or None if lookup fails.
        """
        # The poll loop resolves the UUID once per repo and writes it back onto
        # repo_cfg["repo_id"] (loop.py) so every downstream URL builder reuses
        # it without a fresh API call. Prefer that shared value; it is also how
        # offline tests seed the UUID without hitting the network.
        seeded = self._repo_cfg.get("repo_id")
        if seeded:
            self._resolved_repo_id = seeded
            return seeded
        if getattr(self, "_resolved_repo_id", None) is not None:
            return self._resolved_repo_id
        try:
            repos_path = _ado_api_version(
                f"https://dev.azure.com/{self._org_enc}/{self._project_enc}/_apis/git/repositories"
            )
            result = ado_get(repos_path, self._pat)
            for repo_entry in result.get("value", []):
                if repo_entry.get("name", "").lower() == self._repo.lower():
                    self._resolved_repo_id = repo_entry.get("id", "")
                    return self._resolved_repo_id
        except RuntimeError as e:  # ADO API raises RuntimeError on HTTP error.
            dbg.warning(
                "resolve_repo_id: failed to resolve UUID for %s/%s: %s: %s",
                self._org, self._project, type(e).__name__, e,
            )
        return None

    def slug_prefix(self) -> str:
        return "ado"

    def pid_prefix(self) -> str:
        return "ado_"

    def worktree_path_parts(self) -> tuple[str, ...]:
        """Path parts for worktree/clone directories: (org, project, repo).

        For a fully-normalised config (from ``build_repo_cfg``) this is the
        three-part (org, project, repo). For a degenerate 2-part throwaway
        config (owner="o", repo="r") that never reached normalisation, fall
        back to (owner, repo) so the on-disk layout matches the pre-seam
        convention rather than collapsing to ``_repo``.
        """
        if not self._org and not self._project and self._owner:
            return (self._owner, self._repo)
        return (self._org, self._project, self._repo)

    def commit_url(self, commit_sha: str) -> str | None:
        """Clickable Azure DevOps commit URL, or None when parts are unset.

        Uses the resolved repo UUID when available, else the repo name.
        """
        org, project, repo = self._org, self._project, self._repo
        if org and project and repo:
            repo_id = self.resolve_repo_id()
            repo_e = _encode_path_segment(repo_id or repo)
            return (
                f"https://dev.azure.com/{_encode_path_segment(org)}/"
                f"{_encode_path_segment(project)}/_git/{repo_e}/commit/{commit_sha}"
            )
        return None

    def branch_url(self, branch: str) -> str | None:
        """Clickable Azure DevOps branch-view URL, or None when parts are unset."""
        org, project, repo = self._org, self._project, self._repo
        if org and project and repo:
            repo_id = self.resolve_repo_id()
            repo_e = _encode_path_segment(repo_id or repo)
            branch_e = _encode_path_segment(branch)
            return (
                f"https://dev.azure.com/{_encode_path_segment(org)}/"
                f"{_encode_path_segment(project)}/_git/{repo_e}?version=GB{branch_e}"
            )
        return None

    # ---- Protocol: VCSProvider ----

    def clone_url(self) -> str:
        """Return the full HTTPS clone URL with embedded PAT."""
        return (
            f"https://autoswe:{self._pat}@"
            f"dev.azure.com/{self._org}/{self._project}/_git/{self._repo}"
        )

    def branch_name(self, issue_number: int) -> str:
        """Return the branch name for an issue."""
        return f"autoswe/issue-{issue_number}"

    def find_existing_pr(self, branch: str) -> PRResult | None:
        """Check if an active PR for the branch already exists."""
        path = _ado_api_version(
            f"https://dev.azure.com/{self._org_enc}/{self._project_enc}/_apis/git/repositories/"
            f"{self._repo_enc}/pullrequests"
            f"?searchCriteria.sourceRefName=refs/heads/{branch}"
            f"&searchCriteria.status=active"
        )
        result = ado_get(path, self._pat)
        prs = result.get("value", [])
        if prs:
            pr = prs[0]
            return PRResult(
                number=pr.get("pullRequestId"),
                url=pr.get("url", ""),
            )
        return None

    def open_pull_request(
        self,
        branch: str,
        base: str,
        title: str,
        body: str,
    ) -> PRResult:
        """Open a pull request in Azure Repos."""
        path = _ado_api_version(
            f"https://dev.azure.com/{self._org_enc}/{self._project_enc}/_apis/git/repositories/"
            f"{self._repo_enc}/pullrequests"
        )
        pr_data = {
            "sourceRefName": f"refs/heads/{branch}",
            "targetRefName": f"refs/heads/{base}",
            "title": redact_outbound(title),
            "description": redact_outbound(body),
        }
        result = ado_post(path, self._pat, body=pr_data)
        # ADO returns the API URL in "url"; construct the clickable web URL instead
        pr_id = result.get("pullRequestId")
        return PRResult(
            number=pr_id,
            url=f"https://dev.azure.com/{self._org}/{self._project}/_git/{self._repo}/pullrequest/{pr_id}" if pr_id else "",
        )

    def link_branch_to_issue(
        self,
        issue_number: int,
        commit_sha: str,
        branch: str,
    ) -> None:
        """Azure DevOps does not have an equivalent feature — no-op."""

    def get_ci_status(self, branch: str, ref_sha: str | None = None) -> CIStatus:
        """Return CI status from the most recent Azure Pipelines build for *branch*.

        ``ref_sha`` is unused — Azure Pipelines builds are queried by branch,
        not commit SHA (kept for VCSProvider protocol parity with GitHub).
        """
        path = _ado_api_version(
            f"https://dev.azure.com/{self._org_enc}/{self._project_enc}/_apis/build/builds"
            f"?branchName=refs/heads/{branch}&statusFilter=all&$top=1"
            f"&queryOrder=queueTimeDescending"
        )
        try:
            result = ado_get(path, self._pat)
        except Exception:
            return CIStatus(state="none", summary="could not query builds")

        builds = result.get("value", [])
        if not builds:
            return CIStatus(state="none", summary="no builds found")

        latest = builds[0]
        name = (latest.get("definition") or {}).get("name", "build")
        status = latest.get("status")
        build_result = latest.get("result")

        if status in _PENDING_STATUSES:
            return CIStatus(state="pending", total=1, pending_count=1, summary=f"build '{name}' in progress")
        if build_result in _FAILURE_RESULTS:
            return CIStatus(state="failure", total=1, failing=[name], summary=f"build '{name}' failed")
        if build_result in _SUCCESS_RESULTS:
            return CIStatus(state="success", total=1, summary=f"build '{name}' succeeded")
        return CIStatus(state="none", total=1, summary="no build result")
