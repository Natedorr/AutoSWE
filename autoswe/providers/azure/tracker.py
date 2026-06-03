"""Azure DevOps IssueTracker — reads + writes (Stage 5).

Uses WIQL for discovery, work item API for reads/writes, and tag-based status
tracking (``autoswe:***`` tags).  Normalized dataclasses are returned so
orchestrator code is backend-agnostic.
"""
from __future__ import annotations

import html
import re
from html.parser import HTMLParser

from autoswe.providers.azure.api import (
    _ado_api_version,
    _encode_path_segment,
    ado_get,
    ado_patch,
    ado_patch_json,
    ado_post,
    ado_post_patch,
    dbg,
)
from autoswe.providers.base import IssueTracker, NormalizedComment, NormalizedIssue
from autoswe.tracking.comments import _BOT_CONTENT_PATTERNS, BOT_MARKER
from autoswe.tracking.labels import _validate_status

_PREFIX = "autoswe:"


def _is_bot_comment(body: str) -> bool:
    """Check if a comment body was posted by autoSWE.

    Checks BOT_MARKER first, then falls back to content patterns
    (Azure DevOps strips HTML comments from rendered bodies).
    """
    if BOT_MARKER in body:
        return True
    return any(pattern in body for pattern in _BOT_CONTENT_PATTERNS)


_AUTOSWE_TAG_RE = re.compile(r"</?AUTOSWE_\w+>")


class _StripHTML(HTMLParser):
    """Minimal HTML → text converter that preserves <AUTOSWE_*> tags.

    Strips standard HTML tags (``<p>``, ``<br>``, ``<b>``, etc.) while
    preserving custom autoSWE tags like ``<AUTOSWE_PLAN>`` and
    ``<AUTOSWE_QUESTIONS>`` that the orchestrator uses for parsing.
    """
    def __init__(self):
        super().__init__()
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs):
        if tag.upper().startswith("AUTOSWE_"):
            # HTMLParser lowercases tag names; preserve uppercase for autoSWE tags
            self._parts.append(f"<{tag.upper()}>")

    def handle_endtag(self, tag: str):
        if tag.upper().startswith("AUTOSWE_"):
            self._parts.append(f"</{tag.upper()}>")

    def handle_data(self, data: str):
        self._parts.append(data)

    def get_text(self) -> str:
        return "".join(self._parts)


def _strip_html(html: str) -> str:
    p = _StripHTML()
    p.feed(html)
    return p.get_text()


class AzureTracker(IssueTracker):
    """Azure DevOps-backed issue tracker.

    ``repo_cfg`` must contain::

        {
            "provider": "azure",
            "org": "my-org",
            "project": "my-project",
            "pat": "azure_pat_here",
        }
    """

    def __init__(self, repo_cfg: dict):
        self._repo_cfg = repo_cfg
        self._org = repo_cfg.get("org", "")
        self._project = repo_cfg.get("project", "")
        self._repo = repo_cfg.get("repo", "")
        self._pat = repo_cfg.get("pat", "")
        self._authenticated_user: str | None = None
        self._resolved_repo_id: str | None = None

        # Defensive fallback: when caller passes owner/repo instead of
        # org/project (e.g. from build_repo_cfg or other callers), parse
        # from those fields if they look like Azure 3-part components.
        if not self._org or not self._project:
            owner = repo_cfg.get("owner", "")
            repo = repo_cfg.get("repo", "")
            if "/" in owner and "/" not in repo:
                org_part, _, proj_part = owner.partition("/")
                if org_part and proj_part:
                    self._org = org_part
                    self._project = proj_part
            elif "/" in repo:
                proj_part, _, _repo_part = repo.partition("/")
                if proj_part:
                    self._org = owner
                    self._project = proj_part
                    if _repo_part:
                        self._repo = _repo_part

        # URL-encode for safe use in request URLs
        self._org_enc = _encode_path_segment(self._org)
        self._project_enc = _encode_path_segment(self._project)

    # ---- Repo ID resolution ----

    def resolve_repo_id(self) -> str | None:
        """Resolve the Git repository UUID for this repo.

        Azure DevOps web URLs require the repo UUID (not the display name)
        in the `_git/{repo-id}/...` path segment. This method queries the
        repos API, finds the repo matching self._repo by name, and returns
        its UUID. Result is cached on first successful call.

        Returns the UUID string, or None if lookup fails.
        """
        if self._resolved_repo_id is not None:
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
        except Exception as e:
            dbg.warning(
                "resolve_repo_id: failed to resolve UUID for %s/%s: %s: %s",
                self._org, self._project, type(e).__name__, e,
            )
        return None

    # ---- Protocol: IssueTracker ----

    def list_open_issues(self, repo_cfg: dict) -> list[NormalizedIssue]:
        """Return all open work items via WIQL + batch expand."""
        wiql = {
            "query": (
                "SELECT [System.Id] FROM WorkItems "
                "WHERE [System.State] NOT IN ('Closed','Done','Removed') "
                f"AND [System.TeamProject] = '{self._project}'"
            ),
        }
        wiql_path = _ado_api_version(
            f"https://dev.azure.com/{self._org_enc}/{self._project_enc}/_apis/wit/wiql?$top=2000"
        )
        result = ado_post(wiql_path, self._pat, body=wiql)
        work_items = result.get("workItems", [])
        if not work_items:
            return []

        id_list = [w["id"] for w in work_items]
        ids_param = ",".join(str(i) for i in id_list)
        batch_path = _ado_api_version(
            f"https://dev.azure.com/{self._org_enc}/{self._project_enc}/_apis/wit/workitems"
            f"?ids={ids_param}&$expand=all"
        )
        batch_result = ado_get(batch_path, self._pat)
        batch_items = batch_result.get("value", [])

        return [self._to_normalized(item) for item in batch_items]

    def fetch_issue(self, repo_cfg: dict, issue_number: int) -> NormalizedIssue:
        """Fetch a single work item by number."""
        path = _ado_api_version(
            f"https://dev.azure.com/{self._org_enc}/{self._project_enc}/_apis/wit/workitems/{issue_number}"
            "?$expand=all"
        )
        raw = ado_get(path, self._pat)
        return self._to_normalized(raw)

    def fetch_comments(self, repo_cfg: dict, issue_number: int) -> list[NormalizedComment]:
        """Fetch all comments on a work item.

        Normalizes ``author_login`` for each comment so that orchestrator code
        (sync.py) can distinguish bot vs. user comments:

        - Bot comments (body matches ``_BOT_CONTENT_PATTERNS``) → ``"BOT"``
        - User comments matching the PAT authenticated user → ``"OWNER"``
        - Everything else → raw ``uniqueName`` (email)
        """
        preview_path = (
            f"https://dev.azure.com/{self._org_enc}/{self._project_enc}/_apis/wit/workitems/"
            f"{issue_number}/comments?api-version=7.1-preview.4"
        )
        raw = ado_get(preview_path, self._pat)
        comments_raw = raw.get("comments", [])

        # Resolve the authenticated PAT owner for comparison
        try:
            pat_owner = self.authenticated_user(repo_cfg)
        except Exception:
            pat_owner = None

        results = []
        for c in comments_raw:
            body = html.unescape(c.get("text", "") or "")
            author_raw = c.get("createdBy", {}).get("uniqueName", "")

            # Normalize author_login for sync.py compatibility.
            # Azure DevOps strips HTML comments from rendered bodies, so the
            # BOT_MARKER check is augmented with content-based pattern detection.
            if _is_bot_comment(body):
                author_login = "BOT"
                # Bot comments may contain HTML tags from older versions of the
                # bot that posted via format=Html. Strip them so orchestrator
                # code sees clean text. BOT_MARKER re-appended below.
                body = _strip_html(body)
                # Re-append marker that _strip_html removes (HTMLParser drops
                # comments).  The marker is needed by is_bot_comment() and
                # _find_last_bot_comment_ts() in tracking/comments.py.
                if not body.endswith(BOT_MARKER):
                    body = body.rstrip() + BOT_MARKER
            elif pat_owner and author_raw == pat_owner:
                author_login = "OWNER"
            else:
                author_login = author_raw

            results.append(
                NormalizedComment(
                    body=body,
                    created_at=c.get("createdDate", ""),
                    author_login=author_login,
                    raw_author_login=author_raw,
                    id=c.get("id"),
                )
            )
        return results

    # ---- Pure helpers (no network) ----

    @staticmethod
    def _extract_status(labels: list[str]) -> str | None:
        """Extract autoswe status from a list of labels/tags."""
        for label in labels:
            if label.startswith(_PREFIX):
                return label.replace(_PREFIX, "", 1)
        return None

    def get_status(self, issue: NormalizedIssue) -> str | None:
        """Extract autoswe status from labels (tags)."""
        return self._extract_status(issue.labels)

    def authenticated_user(self, repo_cfg: dict) -> str:
        """Return the email of the authenticated PAT owner.

        Primary: ADO Profile API (reliable, no dependency on work item existence).
        Fallback: work item #1 System.CreatedBy (legacy path).
        """
        if self._authenticated_user is not None:
            return self._authenticated_user

        # Primary: Profile API — works regardless of work item existence
        try:
            me_path = "https://app.vssps.visualstudio.com/_apis/profile/profiles/me?api-version=7.1-preview.1"
            raw = ado_get(me_path, self._pat)
            self._authenticated_user = (
                raw.get("principalName", "")
                or raw.get("uniqueName", "")
                or raw.get("emailAddress", "")
                or raw.get("displayName", "")
            )
            if self._authenticated_user:
                return self._authenticated_user
        except Exception:
            pass

        # Fallback: work item #1 CreatedBy
        try:
            path = _ado_api_version(
                f"https://dev.azure.com/{self._org_enc}/{self._project_enc}/_apis/wit/workitems/1"
            )
            raw = ado_get(path, self._pat)
            created_by = raw.get("fields", {}).get("System.CreatedBy", {})
            self._authenticated_user = created_by.get("uniqueName", "")
        except Exception:
            pass

        return self._authenticated_user or ""

    # ---- Write methods (Stage 5) ----

    def post_comment(self, repo_cfg: dict, issue_number: int, body: str) -> int | None:
        """Post a comment on a work item. Returns comment ID or None.

        Always uses ``format=Markdown`` so ADO renders headings, lists,
        links, bold, inline code, and other Markdown natively.
        """
        path = (
            f"https://dev.azure.com/{self._org_enc}/{self._project_enc}/_apis/wit/workitems/"
            f"{issue_number}/comments?format=Markdown&api-version=7.1-preview.4"
        )
        result = ado_post(path, self._pat, body={"text": body})
        return result.get("id") if result else None

    def update_comment(self, repo_cfg: dict, issue_number: int, comment_id: int, body: str) -> None:
        """Edit a comment on a work item via PATCH."""
        path = (
            f"https://dev.azure.com/{self._org_enc}/{self._project_enc}/_apis/wit/workitems/"
            f"{issue_number}/comments/{comment_id}?format=Markdown&api-version=7.1-preview.4"
        )
        ado_patch_json(path, self._pat, body={"text": body})

    def create_issue(self, repo_cfg: dict, title: str, body: str) -> int:
        """Create a new work item (Issue type) in Azure DevOps.

        Returns the work item ID (issue number).
        """
        path = _ado_api_version(
            f"https://dev.azure.com/{self._org_enc}/{self._project_enc}/_apis/wit/workitems/$Issue"
        )
        payload = [
            {"op": "add", "path": "/fields/System.Title", "value": title},
            {"op": "add", "path": "/fields/System.Description", "value": body},
        ]
        result = ado_post_patch(path, self._pat, body=payload)
        return result["id"]

    def set_status(self, repo_cfg: dict, issue_number: int, status: str) -> None:
        """Set the autoswe status tag on a work item (read-modify-write).

        GETs the current work item, strips existing autoswe:* tags,
        appends the new status tag, and PATCHes via JSON-Patch.
        """
        _validate_status(status)
        # Read current tags
        get_path = _ado_api_version(
            f"https://dev.azure.com/{self._org_enc}/{self._project_enc}/_apis/wit/workitems/"
            f"{issue_number}?fields=System.Tags"
        )
        raw = ado_get(get_path, self._pat)
        tags_raw = raw.get("fields", {}).get("System.Tags", "") or ""
        tags = [t.strip() for t in tags_raw.split(";") if t.strip()] if tags_raw else []

        # Strip old autoswe:* tags, append new one
        # Normalize: callers may pass "pending" or "autoswe:pending" (the latter
        # is what the orchestrator always sends), so strip the prefix if present
        # before prepending it — prevents double-prefix like "autoswe:autoswe:pending".
        normalized_status = status[len(_PREFIX):] if status.startswith(_PREFIX) else status
        new_tags = [t for t in tags if not t.startswith(_PREFIX)]
        new_tags.append(f"{_PREFIX}{normalized_status}")

        # PATCH via JSON-Patch
        patch_path = _ado_api_version(
            f"https://dev.azure.com/{self._org_enc}/{self._project_enc}/_apis/wit/workitems/{issue_number}"
        )
        ado_patch(
            patch_path, self._pat,
            body=[{"op": "replace", "path": "/fields/System.Tags", "value": "; ".join(new_tags)}],
        )

    def assign_to_user(self, repo_cfg: dict, issue_number: int, login: str | None) -> None:
        """Assign the work item to a user.

        If ``login`` is None, resolves to the authenticated PAT owner.
        Uses the email/UPN as the assigned-to value.
        """
        if login is None:
            login = self.authenticated_user(repo_cfg)

        patch_path = _ado_api_version(
            f"https://dev.azure.com/{self._org_enc}/{self._project_enc}/_apis/wit/workitems/{issue_number}"
        )
        ado_patch(
            patch_path, self._pat,
            body=[{"op": "replace", "path": "/fields/System.AssignedTo", "value": login}],
        )

    # ---- Internal helpers ----

    def _to_normalized(self, raw: dict) -> NormalizedIssue:
        """Convert a raw ADO work item to NormalizedIssue."""
        fields = raw.get("fields", {})
        title = fields.get("System.Title", "")
        description = fields.get("System.Description", "") or ""
        tags_raw = fields.get("System.Tags", "") or ""
        labels = [t.strip() for t in tags_raw.split(";") if t.strip()] if tags_raw else []
        raw_state = fields.get("System.State", "New")
        state = "closed" if raw_state in ("Closed", "Done", "Removed") else "open"
        return NormalizedIssue(
            number=raw["id"],
            title=title,
            body=_strip_html(html.unescape(description)),
            owner=self._org,
            repo=self._project,
            state=state,
            base_branch="main",
            labels=labels,
            status=self._extract_status(labels),
            last_updated=fields.get("System.ChangedDate"),
            creator_login=fields.get("System.CreatedBy", {}).get("uniqueName", ""),
        )
