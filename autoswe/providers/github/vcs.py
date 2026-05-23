"""GitHub VCSProvider — wraps existing autoswe.vcs modules."""
from __future__ import annotations

import json
import subprocess

from autoswe.core.config import LOGS_DIR
from autoswe.core.logging_utils import init_debug_logger
from autoswe.providers.base import PRResult, VCSProvider
from autoswe.tracking.api import gh_post

dbg = init_debug_logger(LOGS_DIR)


class MissingScopeError(RuntimeError):
    """Raised when a GitHub API call fails due to missing PAT scopes."""


class GitHubVCS(VCSProvider):
    """GitHub-backed VCS provider."""

    def __init__(self, repo_cfg: dict):
        self._repo_cfg = repo_cfg
        self._owner = repo_cfg.get("owner", "")
        self._repo = repo_cfg.get("repo", "")
        self._token = repo_cfg.get("pat", "") or repo_cfg.get("token", "")

    # ---- Protocol: VCSProvider ----

    def clone_url(self, repo_cfg: dict) -> str:
        """Return the full HTTPS clone URL with embedded token."""
        return f"https://x-access-token:{self._token}@github.com/{self._owner}/{self._repo}.git"

    def branch_name(self, issue_number: int) -> str:
        """Return the branch name for an issue."""
        return f"autoswe/issue-{issue_number}"

    def find_existing_pr(self, repo_cfg: dict, branch: str) -> PRResult | None:
        """Check if a PR for the branch already exists."""
        try:
            result = subprocess.run(
                ["gh", "pr", "list", "--repo", f"{self._owner}/{self._repo}",
                 "--head", branch, "--json", "number,url", "--limit", "1"],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode != 0:
                return None
            prs = json.loads(result.stdout or "[]")
            if prs:
                return PRResult(number=prs[0]["number"], url=prs[0]["url"])
            return None
        except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
            return None

    def open_pull_request(
        self,
        repo_cfg: dict,
        branch: str,
        base: str,
        title: str,
        body: str,
    ) -> PRResult:
        """Open a GitHub pull request via gh CLI or API fallback."""
        # gh CLI
        try:
            result = subprocess.run(
                [
                    "gh", "pr", "create",
                    "--repo", f"{self._owner}/{self._repo}",
                    "--head", branch,
                    "--base", base,
                    "--title", title,
                    "--body", body,
                ],
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode == 0:
                url = result.stdout.strip()
                return PRResult(url=url)
            dbg.warning("gh pr create failed: %s", result.stderr)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            dbg.warning("gh CLI unavailable, falling back to API")

        # API fallback
        pr_data = gh_post(
            f"/repos/{self._owner}/{self._repo}/pulls",
            self._token,
            {
                "title": title,
                "body": body,
                "head": branch,
                "base": base,
            },
        )
        pr_num = pr_data.get("number")
        pr_url = pr_data.get("html_url", f"#{pr_num}")
        return PRResult(number=pr_num, url=pr_url)

    def link_branch_to_issue(
        self,
        issue_number: int,
        commit_sha: str,
        branch: str,
    ) -> None:
        """Link branch to issue via GitHub Checks API.

        Creates a check run on the commit, which causes GitHub to show the
        branch in the issue's Development section.
        """
        if not self._token:
            return  # cannot link without a token

        try:
            gh_post(
                f"/repos/{self._owner}/{self._repo}/check-runs",
                self._token,
                {
                    "name": f"autoSWE Fix #{issue_number}",
                    "head_sha": commit_sha,
                    "status": "completed",
                    "conclusion": "success",
                    "output": {
                        "title": f"autoSWE Fix #{issue_number}",
                        "summary": f"Branch linked by autoSWE for issue #{issue_number}",
                    },
                },
                max_retries=1,
                timeout=5,
            )
        except RuntimeError as e:
            if "403" in str(e):
                raise MissingScopeError(
                    "PAT missing check_runs:write scope"
                ) from e
            raise
