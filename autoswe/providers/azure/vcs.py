"""Azure DevOps VCSProvider — wraps Azure Repos REST API.

Handles clone URLs, branch naming, PR discovery, and PR creation via the
Azure DevOps REST API.
"""
from __future__ import annotations

from autoswe.core.redact import redact_worktree_paths
from autoswe.providers.azure.api import _ado_api_version, _encode_path_segment, ado_get, ado_post
from autoswe.providers.base import PRResult, VCSProvider


class AzureVCS(VCSProvider):
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
        self._org = repo_cfg.get("org", "")
        self._project = repo_cfg.get("project", "")
        self._repo = repo_cfg.get("repo", "")
        self._pat = repo_cfg.get("pat") or repo_cfg.get("token", "")

        # Defensive fallback: when caller passes owner/repo instead of
        # org/project/repo (e.g. worktree.py inline repo_cfg dicts or
        # build_repo_cfg with 3-part Azure keys), parse from those fields.
        if not self._org or not self._project:
            owner = repo_cfg.get("owner", "")
            repo = repo_cfg.get("repo", "")
            # owner might be "org/proj" and repo might be the repo name
            if "/" in owner and "/" not in repo:
                org_part, _, proj_part = owner.partition("/")
                if org_part and proj_part:
                    self._org = org_part
                    self._project = proj_part
                    self._repo = repo
            # owner might be "org" and repo might be "project/repo"
            elif "/" in repo:
                proj_part, _, repo_part = repo.partition("/")
                if proj_part and repo_part:
                    self._org = owner
                    self._project = proj_part
                    self._repo = repo_part

        # URL-encode for safe use in REST API request URLs
        self._org_enc = _encode_path_segment(self._org)
        self._project_enc = _encode_path_segment(self._project)
        self._repo_enc = _encode_path_segment(self._repo)

    # ---- Protocol: VCSProvider ----

    def clone_url(self, repo_cfg: dict) -> str:
        """Return the full HTTPS clone URL with embedded PAT."""
        return (
            f"https://autoswe:{self._pat}@"
            f"dev.azure.com/{self._org}/{self._project}/_git/{self._repo}"
        )

    def branch_name(self, issue_number: int) -> str:
        """Return the branch name for an issue."""
        return f"autoswe/issue-{issue_number}"

    def find_existing_pr(self, repo_cfg: dict, branch: str) -> PRResult | None:
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
        repo_cfg: dict,
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
            "title": redact_worktree_paths(title),
            "description": redact_worktree_paths(body),
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
