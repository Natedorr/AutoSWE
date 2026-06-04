"""GitHub IssueTracker — wraps existing autoswe.tracking modules."""
from __future__ import annotations

from autoswe.core.logging_utils import get_debug_logger
from autoswe.providers.base import IssueTracker, NormalizedComment, NormalizedIssue
from autoswe.tracking import api as gh_api
from autoswe.tracking.assignment import _auto_assign_issue, _get_authenticated_user
from autoswe.tracking.comments import BOT_MARKER
from autoswe.tracking.labels import (
    _ensure_repo_labels,
    _get_autoswe_status,
    _set_autoswe_status,
)

dbg = get_debug_logger()

_PREFIX = "autoswe:"


class GitHubTracker(IssueTracker):
    """GitHub-backed issue tracker.

    Resolves token from ``repo_cfg.get("token")``, falling back to
    ``cfg["GITHUB_TOKEN"]`` passed through repo_cfg.  ``set_status`` lazily
    calls ``_ensure_repo_labels`` on first call per repo (caches the result
    on the tracker instance).
    """

    def __init__(self, repo_cfg: dict):
        self._repo_cfg = repo_cfg
        self._owner = repo_cfg.get("owner", "")
        self._repo = repo_cfg.get("repo", "")
        self._token = self._resolve_token(repo_cfg)
        self._labels_ensured: bool = False
        self._authenticated_login: str | None = None
        self._issue_author_login: str | None = None
        self._issue_authors: dict[int, str] = {}

    @staticmethod
    def _resolve_token(repo_cfg: dict) -> str:
        """Return the GitHub token from repo_cfg, preferring 'pat' then 'token' alias."""
        return repo_cfg.get("pat", "") or repo_cfg.get("token", "")

    def _ensure_labels(self) -> None:
        """Ensure autoSWE labels exist in the repo (idempotent, cached)."""
        if self._labels_ensured:
            return
        _ensure_repo_labels(self._owner, self._repo, self._token)
        self._labels_ensured = True

    # ---- Protocol: IssueTracker ----

    def list_open_issues(self, repo_cfg: dict) -> list[NormalizedIssue]:
        """Return open issues from GitHub API."""
        raw = gh_api.gh_get_all(
            f"/repos/{self._owner}/{self._repo}/issues?state=open",
            self._token,
        )
        issues = []
        for issue in raw:
            num = issue.get("number")
            author = issue.get("user", {}).get("login", "")
            if num is not None and author:
                self._issue_authors[num] = author
            issues.append(self._to_normalized(issue))
        return issues

    def fetch_issue(self, repo_cfg: dict, issue_number: int) -> NormalizedIssue:
        """Fetch a single issue by number."""
        raw = gh_api.gh_get(
            f"/repos/{self._owner}/{self._repo}/issues/{issue_number}",
            self._token,
        )
        # Cache the issue author login for author normalization in fetch_comments
        issue_author = raw.get("user", {}).get("login", "")
        if issue_author:
            self._issue_author_login = issue_author
            self._issue_authors[issue_number] = issue_author
        return self._to_normalized(raw)

    def fetch_comments(self, repo_cfg: dict, issue_number: int) -> list[NormalizedComment]:
        """Fetch all comments on an issue.

        Normalizes ``author_login`` for each comment so that orchestrator code
        (sync.py) can distinguish bot vs. user comments:

        - Bot comments (body contains ``<!-- autoswe-bot -->``) → ``"BOT"``
        - User comments matching the authenticated token owner → ``"OWNER"``
        - User comments matching the issue author → ``"AUTHOR"``
        - Everything else → raw ``login`` value
        """
        raw = gh_api._fetch_comments(self._owner, self._repo, issue_number, self._token)

        # Resolve the authenticated user login for comparison
        auth_login = self._resolve_auth_user()

        # Get issue author from cache (populated by list_open_issues or fetch_issue)
        issue_author = self._issue_authors.get(issue_number) or self._issue_author_login

        results = []
        for c in raw:
            body = c.get("body", "") or ""
            raw_login = c.get("user", {}).get("login", "")

            # Normalize author_login for sync.py compatibility
            if BOT_MARKER in body:
                author_login = "BOT"
            elif auth_login and raw_login == auth_login:
                author_login = "OWNER"
            elif issue_author and raw_login == issue_author:
                author_login = "AUTHOR"
            else:
                author_login = raw_login

            results.append(
                NormalizedComment(
                    body=body,
                    created_at=c.get("created_at", ""),
                    author_login=author_login,
                    raw_author_login=raw_login,
                    id=c.get("id"),
                )
            )
        return results

    def set_issue_author(self, login: str | None) -> None:
        """Set the issue author login for author normalization in fetch_comments.

        Call this before fetch_comments to enable AUTHOR normalization.
        """
        self._issue_author_login = login

    def _resolve_auth_user(self) -> str | None:
        """Return the GitHub login of the authenticated user (lazy, cached)."""
        if self._authenticated_login is not None:
            return self._authenticated_login
        try:
            self._authenticated_login = _get_authenticated_user(self._token) or None
        except Exception:  # API call is optional — failure just means AUTHOR normalization is skipped
            self._authenticated_login = None
        return self._authenticated_login

    def post_comment(self, repo_cfg: dict, issue_number: int, body: str) -> int | None:
        """Post a comment on a GitHub issue. Returns comment ID or None."""
        raw = gh_api.gh_post(
            f"/repos/{self._owner}/{self._repo}/issues/{issue_number}/comments",
            self._token,
            body={"body": body},
        )
        return raw.get("id") if raw else None

    def update_comment(self, repo_cfg: dict, issue_number: int, comment_id: int, body: str) -> None:
        """Edit an existing comment on a GitHub issue."""
        gh_api.gh_patch(
            f"/repos/{self._owner}/{self._repo}/issues/comments/{comment_id}",
            self._token,
            body={"body": body},
        )

    def create_issue(self, repo_cfg: dict, title: str, body: str) -> int:
        """Create a new GitHub issue. Returns the issue number."""
        raw = gh_api.gh_post(
            f"/repos/{self._owner}/{self._repo}/issues",
            self._token,
            body={"title": title, "body": body},
        )
        return raw["number"]

    def set_status(self, repo_cfg: dict, issue_number: int, status: str) -> None:
        """Set autoSWE status label, ensuring labels exist first."""
        self._ensure_labels()
        _set_autoswe_status(self._owner, self._repo, issue_number, status, self._token)

    def get_status(self, issue: NormalizedIssue) -> str | None:
        """Return current status from labels, or None."""
        return _get_autoswe_status(issue.labels)

    def assign_to_user(self, repo_cfg: dict, issue_number: int, login: str | None) -> None:
        """Assign the issue to a user (idempotent)."""
        _auto_assign_issue(self._owner, self._repo, issue_number, self._token, username=login)

    def authenticated_user(self, repo_cfg: dict) -> str:
        """Return the GitHub login of the authenticated user."""
        user = _get_authenticated_user(self._token)
        return user or ""

    # ---- Internal helpers ----

    def _to_normalized(self, raw: dict) -> NormalizedIssue:
        """Convert a raw GitHub issue dict to NormalizedIssue."""
        labels_raw = raw.get("labels", [])
        labels = [lb["name"] for lb in labels_raw] if labels_raw else []
        status = _get_autoswe_status(labels)
        return NormalizedIssue(
            number=raw["number"],
            title=raw["title"],
            body=raw.get("body", "") or "",
            owner=self._owner,
            repo=self._repo,
            state=raw.get("state", "open"),
            base_branch=raw.get("base_branch", "main"),
            labels=labels,
            status=status,
            is_pull_request=raw.get("pull_request") is not None,
            last_updated=raw.get("updated_at"),
            creator_login=raw.get("user", {}).get("login", ""),
        )
