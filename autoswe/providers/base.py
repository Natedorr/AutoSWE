"""Provider protocols and normalized dataclasses.

This module defines the abstraction layer between autoSWE orchestrator code
and individual backend implementations (GitHub, Azure DevOps, etc.).
Orchestrator code talks only to IssueTracker / VCSProvider instances returned
by the factory — never to backend-specific functions directly.

Design notes (issue #168, S5 "provider seam"):
- Protocol methods do NOT take a ``repo_cfg`` argument: the provider instance
  is constructed from a repo_cfg and already holds everything it needs.
  Passing the config at every call site was inert (both concrete classes
  ignored it) and invited bugs where a differently-shaped config silently
  resolved to the constructor's repo.
- The concrete provider classes intentionally do NOT inherit from these
  Protocols. Inheriting from a Protocol gives every declared method an empty
  body, so a missing implementation returns ``None`` at runtime instead of
  raising ``AttributeError``. The ``@runtime_checkable`` Protocols are kept
  purely for structural ``isinstance`` checks.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable

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


@dataclass
class CIStatus:
    """Combined CI status for a branch head, provider-agnostic.

    ``state`` priority when reducing multiple checks: any failure wins,
    else any pending/in-progress wins, else success if at least one check
    passed, else "none" (no CI configured — never blocks a PR).
    """

    state: Literal["success", "pending", "failure", "none"]
    total: int = 0
    failing: list[str] = field(default_factory=list)
    pending_count: int = 0
    summary: str = ""


# ---------------------------------------------------------------------------
# Protocols
# ---------------------------------------------------------------------------

@runtime_checkable
class IssueTracker(Protocol):
    """Issue tracking backend (GitHub issues, Azure work items, etc.).

    All methods read their repo identity from the instance (constructed via
    ``get_tracker(repo_cfg)``), so no method takes a repo_cfg.
    """

    def list_open_issues(self) -> list[NormalizedIssue]:
        """Return all open issues for the repo that should be considered."""

    def fetch_issue(self, issue_number: int) -> NormalizedIssue:
        """Fetch a single issue by number."""

    def fetch_comments(self, issue_number: int) -> list[NormalizedComment]:
        """Fetch all comments on an issue."""

    def post_comment(self, issue_number: int, body: str) -> int | None:
        """Post a comment on an issue. Returns the comment ID, or None if unavailable."""

    def update_comment(self, issue_number: int, comment_id: int, body: str) -> None:
        """Edit an existing comment. Used for sticky progress updates."""

    def create_issue(self, title: str, body: str) -> int:
        """Create a new issue. Returns the issue number."""

    def set_status(self, issue_number: int, status: str) -> None:
        """Set the status label/tag on an issue.

        *GitHub* lazily ensures labels on first call per repo.
        """

    def get_status(self, issue: NormalizedIssue) -> str | None:
        """Return the current status string for an issue, or None if untracked."""

    def assign_to_user(self, issue_number: int, login: str | None) -> None:
        """Assign the issue to a user (idempotent)."""

    def authenticated_user(self) -> str:
        """Return the login of the authenticated user."""

    def normalize_comment_body(self, comment: NormalizedComment) -> tuple[str, bool]:
        """Normalise a raw comment body for the orchestrator.

        Returns ``(body, is_bot)``: the provider-specific text cleanup
        (identity for GitHub; HTML/entity stripping + content-based bot
        detection for Azure) plus any provider-level bot signal. The shared
        ``read_api`` applies this per comment so the read path stays
        single-sourced.
        """

    def slug_prefix(self) -> str:
        """Return the queue-slug prefix for this provider (``gh`` / ``ado``)."""

    def pid_prefix(self) -> str:
        """Return the PID-file stem prefix for this provider (``gh_`` / ``ado_``)."""


@runtime_checkable
class VCSProvider(Protocol):
    """Version-control backend (GitHub, Azure Repos, etc.).

    All methods read their repo identity from the instance (constructed via
    ``get_vcs(repo_cfg)``), so no method takes a repo_cfg.
    """

    def clone_url(self) -> str:
        """Return the full clone URL (with auth)."""

    def branch_name(self, issue_number: int) -> str:
        """Return the branch name for an issue — the single source of the
        branch convention for the whole codebase."""

    def find_existing_pr(self, branch: str) -> PRResult | None:
        """Check if a PR for the branch already exists."""

    def open_pull_request(
        self,
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

    def get_ci_status(self, branch: str, ref_sha: str | None = None) -> CIStatus:
        """Return the combined CI status for a branch head.

        *ref_sha* pins the check to a specific commit; when omitted, the
        provider resolves the current tip of *branch*. A repo with no CI
        configured returns ``CIStatus(state="none")`` — treated as a pass by
        callers so autoSWE doesn't block forever on repos without checks.
        """

    def commit_url(self, commit_sha: str) -> str | None:
        """Return a clickable URL for *commit_sha*, or None if unavailable."""

    def branch_url(self, branch: str) -> str | None:
        """Return a clickable URL for *branch* (branch view / compare), or None."""

    def worktree_path_parts(self) -> tuple[str, ...]:
        """Return the path parts for worktree/clone directories.

        GitHub: ``(owner, repo)``; Azure: ``(org, project, repo)``.
        """

    def resolve_repo_id(self) -> str | None:
        """Return a platform-specific repo identifier for URLs, or None.

        Azure DevOps web URLs require the Git repository UUID in the
        ``_git/{repo-id}`` path segment; GitHub needs no such identifier.
        """

    def slug_prefix(self) -> str:
        """Return the queue-slug prefix for this provider (``gh`` / ``ado``)."""

    def pid_prefix(self) -> str:
        """Return the PID-file stem prefix for this provider (``gh_`` / ``ado_``)."""
