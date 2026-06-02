"""Provider protocols and normalized dataclasses.

This module defines the abstraction layer between autoSWE orchestrator code
and individual backend implementations (GitHub, Azure DevOps, etc.).
Orchestrator code talks only to IssueTracker / VCSProvider returned by the
factory — never to backend-specific functions directly.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

# ---------------------------------------------------------------------------
# Normalized dataclasses — backends produce these; orchestrator consumes them
# ---------------------------------------------------------------------------

@dataclass
class NormalizedComment:
    """A comment on an issue/PR, provider-agnostic."""

    body: str
    created_at: str  # ISO 8601
    author_login: str = ""
    raw_author_login: str = ""  # original login before normalization (for allowlist)
    id: int | None = None       # provider's comment ID
    is_bot: bool = False        # set by adapter from bot_comment_ids membership


@dataclass
class NormalizedIssue:
    """An issue/bug/feature-request, provider-agnostic."""

    number: int
    title: str
    body: str
    owner: str       # org / project owner
    repo: str        # repo / team project
    state: str = "open"        # "open" or "closed"
    base_branch: str = "main"
    labels: list[str] = None
    status: str | None = None
    comments: list[NormalizedComment] = None
    is_pull_request: bool = False
    last_updated: str | None = None   # ISO 8601; GitHub updated_at / Azure System.ChangedDate
    creator_login: str = ""           # issue creator login for auto-assign

    def __post_init__(self):
        if self.labels is None:
            self.labels = []
        if self.comments is None:
            self.comments = []


@dataclass
class PRResult:
    """The outcome of opening a pull request."""

    url: str
    number: int | None = None
    head_sha: str | None = None  # PR head commit SHA for branch linking


# ---------------------------------------------------------------------------
# Protocols
# ---------------------------------------------------------------------------

@runtime_checkable
class IssueTracker(Protocol):
    """Issue tracking backend (GitHub issues, Azure work items, etc.)."""

    def list_open_issues(self, repo_cfg: dict) -> list[NormalizedIssue]:
        """Return all open issues for the repo that should be considered."""

    def fetch_issue(self, repo_cfg: dict, issue_number: int) -> NormalizedIssue:
        """Fetch a single issue by number."""

    def fetch_comments(self, repo_cfg: dict, issue_number: int) -> list[NormalizedComment]:
        """Fetch all comments on an issue."""

    def post_comment(self, repo_cfg: dict, issue_number: int, body: str) -> int | None:
        """Post a comment on an issue. Returns the comment ID, or None if unavailable."""

    def update_comment(self, repo_cfg: dict, issue_number: int, comment_id: int, body: str) -> None:
        """Edit an existing comment. Used for sticky progress updates."""

    def create_issue(self, repo_cfg: dict, title: str, body: str) -> int:
        """Create a new issue. Returns the issue number."""

    def set_status(self, repo_cfg: dict, issue_number: int, status: str) -> None:
        """Set the status label/tag on an issue.

        *GitHub* lazily ensures labels on first call per repo.
        """

    def get_status(self, issue: NormalizedIssue) -> str | None:
        """Return the current status string for an issue, or None if untracked."""

    def assign_to_user(self, repo_cfg: dict, issue_number: int, login: str | None) -> None:
        """Assign the issue to a user (idempotent)."""

    def authenticated_user(self, repo_cfg: dict) -> str:
        """Return the login of the authenticated user."""


@runtime_checkable
class VCSProvider(Protocol):
    """Version-control backend (GitHub, Azure Repos, etc.)."""

    def clone_url(self, repo_cfg: dict) -> str:
        """Return the full clone URL (with auth)."""

    def branch_name(self, issue_number: int) -> str:
        """Return the branch name for an issue."""

    def find_existing_pr(self, repo_cfg: dict, branch: str) -> PRResult | None:
        """Check if a PR for the branch already exists."""

    def open_pull_request(
        self,
        repo_cfg: dict,
        branch: str,
        base: str,
        title: str,
        body: str,
    ) -> PRResult:
        """Open a pull request. Returns PR info or raises on failure."""

    def link_branch_to_issue(
        self,
        issue_number: int,
        commit_sha: str,
        branch: str,
    ) -> None:
        """Link the branch to the issue in the platform's UI (optional, no-op default).

        Causes the branch to appear in the issue's Development section on GitHub.
        """
