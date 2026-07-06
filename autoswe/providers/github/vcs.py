"""GitHub VCSProvider — wraps existing autoswe.vcs modules."""
from __future__ import annotations

import json
import subprocess

from autoswe.core.logging_utils import get_debug_logger
from autoswe.core.redact import redact_worktree_paths
from autoswe.providers.base import CIStatus, PRResult, VCSProvider
from autoswe.tracking.api import gh_get, gh_post

dbg = get_debug_logger()

# check-run/status conclusions that block a PR vs. that count as a pass
_FAILURE_CONCLUSIONS = {"failure", "cancelled", "timed_out", "action_required"}
_SUCCESS_CONCLUSIONS = {"success", "neutral", "skipped"}


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
                pass  # fall through to API
            else:
                prs = json.loads(result.stdout or "[]")
                if prs:
                    return PRResult(number=prs[0]["number"], url=prs[0]["url"])
                return None
        except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
            pass  # fall through to API

        # API fallback when gh CLI is unavailable
        try:
            prs = gh_get(
                f"/repos/{self._owner}/{self._repo}/pulls?head={self._owner}:{branch}&state=open",
                self._token,
                max_retries=1,
            )
            if prs and isinstance(prs, list) and prs[0]:
                return PRResult(
                    number=prs[0]["number"],
                    url=prs[0]["html_url"],
                    head_sha=prs[0].get("head", {}).get("sha"),
                )
        except Exception:
            pass  # best-effort
        return None

    def open_pull_request(
        self,
        repo_cfg: dict,
        branch: str,
        base: str,
        title: str,
        body: str,
    ) -> PRResult:
        """Open a GitHub pull request via gh CLI or API fallback.

        Extracts the PR's head commit SHA so callers can use it for
        branch-to-issue linking when the remote SHA is unavailable.
        """
        # Redact worktree paths before posting
        safe_title = redact_worktree_paths(title)
        safe_body = redact_worktree_paths(body)

        # gh CLI
        try:
            result = subprocess.run(
                [
                    "gh", "pr", "create",
                    "--repo", f"{self._owner}/{self._repo}",
                    "--head", branch,
                    "--base", base,
                    "--title", safe_title,
                    "--body", safe_body,
                ],
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode == 0:
                url = result.stdout.strip()
                head_sha = None
                # Best-effort: fetch PR details to get head SHA
                try:
                    pr_num_from_url = url.rstrip("/").split("/")[-1]
                    pr_details = gh_get(
                        f"/repos/{self._owner}/{self._repo}/pulls/{pr_num_from_url}",
                        self._token, max_retries=1,
                    )
                    head_sha = pr_details.get("head", {}).get("sha")
                except Exception:  # Best-effort SHA lookup — PR is valid even if we can't fetch head SHA
                    pass
                return PRResult(url=url, head_sha=head_sha)
            dbg.warning("gh pr create failed: %s", result.stderr)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            dbg.warning("gh CLI unavailable, falling back to API")

        # API fallback
        pr_data = gh_post(
            f"/repos/{self._owner}/{self._repo}/pulls",
            self._token,
            {
                "title": safe_title,
                "body": safe_body,
                "head": branch,
                "base": base,
            },
        )
        pr_num = pr_data.get("number")
        pr_url = pr_data.get("html_url", f"#{pr_num}")
        head_sha = pr_data.get("head", {}).get("sha")
        return PRResult(number=pr_num, url=pr_url, head_sha=head_sha)

    def link_branch_to_issue(
        self,
        issue_number: int,
        commit_sha: str,
        branch: str,
    ) -> None:
        """Link branch to issue via GitHub GraphQL ``createLinkedBranch`` mutation.

        Creates a branch ref pointed at *commit_sha* and links it to the issue
        so the branch appears in the issue's Development sidebar.  The branch
        ref is created **before** any push, so this must run at branch-creation
        time (see ``create_worktree``).

        *commit_sha* is the full base SHA to create the branch from (e.g. the
        tip of ``origin/main``).

        GraphQL returns HTTP 200 even on error, so the ``errors`` key is
        inspected: "already exists" is swallowed (idempotent re-link),
        permission errors surface as ``MissingScopeError``.
        """
        if not self._token:
            return  # cannot link without a token

        # 1. Fetch the issue node_id via REST
        try:
            issue_data = gh_get(
                f"/repos/{self._owner}/{self._repo}/issues/{issue_number}",
                self._token,
                max_retries=1,
            )
        except RuntimeError as e:
            raise RuntimeError(f"Failed to fetch issue {issue_number} node_id: {e}") from e

        issue_id = issue_data.get("node_id")
        if not issue_id:
            return  # no node_id — nothing to link

        # 2. POST the GraphQL createLinkedBranch mutation
        mutation = (
            "mutation($issueId: ID!, $oid: GitObjectID!, $name: String) {"
            "  createLinkedBranch(input: {issueId: $issueId, oid: $oid, name: $name}) {"
            "    linkedBranch { id ref { name } }"
            "  }"
            "}"
        )
        variables = {
            "issueId": issue_id,
            "oid": commit_sha,
            "name": branch,
        }
        try:
            result = gh_post(
                "/graphql",
                self._token,
                {"query": mutation, "variables": variables},
                max_retries=1,
                timeout=10,
            )
        except RuntimeError as e:
            err_str = str(e)
            # 403 → permission error
            if "403" in err_str:
                raise MissingScopeError(
                    "PAT missing permission to create linked branch "
                    "(needs contents + issues write scope)"
                ) from e
            raise

        # 3. GraphQL returns HTTP 200 even on error — inspect the "errors" key
        errors = result.get("errors", [])
        if not errors:
            return  # success — branch created and linked

        # "already exists" / "Reference already exists" → benign no-op (idempotent)
        for err in errors:
            msg = err.get("message", "").lower()
            if "already exists" in msg:
                return  # branch already linked — fine
            # Permission error from GraphQL
            if "permission" in msg or "forbidden" in msg or "not acceptable" in msg:
                raise MissingScopeError(
                    "PAT missing permission to create linked branch "
                    "(needs contents + issues write scope)"
                )

        # Unknown GraphQL error — re-raise so the caller knows
        raise RuntimeError(
            f"createLinkedBranch GraphQL error: "
            f"{[e.get('message', str(e)) for e in errors]}"
        )

    def get_ci_status(self, repo_cfg: dict, branch: str, ref_sha: str | None = None) -> CIStatus:
        """Combine check-runs and legacy commit status into one CIStatus.

        Priority: any failure -> failure; else any queued/in_progress/pending
        -> pending; else >=1 completed-success -> success; else none.
        """
        sha = ref_sha
        if not sha:
            try:
                commit = gh_get(
                    f"/repos/{self._owner}/{self._repo}/commits/{branch}",
                    self._token, max_retries=1,
                )
                sha = commit.get("sha")
            except Exception:
                return CIStatus(state="none", summary="could not resolve branch head")
        if not sha:
            return CIStatus(state="none", summary="could not resolve branch head")

        failing: list[str] = []
        pending_count = 0
        success_count = 0
        total = 0

        try:
            check_runs = gh_get(
                f"/repos/{self._owner}/{self._repo}/commits/{sha}/check-runs",
                self._token, max_retries=1,
            )
            for run in check_runs.get("check_runs", []):
                total += 1
                name = run.get("name", "check")
                if run.get("status") != "completed":
                    pending_count += 1
                elif run.get("conclusion") in _FAILURE_CONCLUSIONS:
                    failing.append(name)
                elif run.get("conclusion") in _SUCCESS_CONCLUSIONS:
                    success_count += 1
        except Exception:
            pass  # best-effort — treat as no check-runs available

        try:
            status = gh_get(
                f"/repos/{self._owner}/{self._repo}/commits/{sha}/status",
                self._token, max_retries=1,
            )
            for s in status.get("statuses", []):
                total += 1
                context = s.get("context", "status")
                state = s.get("state")
                if state in ("failure", "error"):
                    failing.append(context)
                elif state == "pending":
                    pending_count += 1
                elif state == "success":
                    success_count += 1
        except Exception:
            pass  # best-effort — treat as no legacy status available

        if failing:
            return CIStatus(
                state="failure", total=total, failing=failing, pending_count=pending_count,
                summary=f"{len(failing)} check(s) failing: {', '.join(failing)}",
            )
        if pending_count:
            return CIStatus(
                state="pending", total=total, pending_count=pending_count,
                summary=f"{pending_count} check(s) pending",
            )
        if success_count:
            return CIStatus(state="success", total=total, summary=f"{success_count} check(s) passed")
        return CIStatus(state="none", total=total, summary="no checks found")
