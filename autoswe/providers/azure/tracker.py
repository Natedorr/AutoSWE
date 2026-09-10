"""Azure DevOps IssueTracker — reads + writes (Stage 5).

Uses WIQL for discovery, work item API for reads/writes, and tag-based status
tracking (``autoswe:***`` tags).  Normalized dataclasses are returned so
orchestrator code is backend-agnostic.
"""
from __future__ import annotations

import html
import re
from html.parser import HTMLParser

from autoswe.core.logging_utils import get_debug_logger
from autoswe.core.redact import redact_outbound
from autoswe.providers.azure.api import (
    _ado_api_version,
    _encode_path_segment,
    _normalize_azure_parts,
    ado_get,
    ado_patch,
    ado_patch_json,
    ado_post,
    ado_post_patch,
)
from autoswe.providers.base import Capability, NormalizedComment, NormalizedIssue
from autoswe.tracking.comments import _BOT_CONTENT_PATTERNS, BOT_MARKER
from autoswe.tracking.labels import _validate_status

dbg = get_debug_logger()

_PREFIX = "autoswe:"

# ADO's batch work-item GET caps the number of ids per request (undocumented).
# Keep well under that cap — docs/azure-devops-api/list-work-items.md,
# Common Pitfalls #3 ("split into multiple requests").
_BATCH_CHUNK_SIZE = 100

# The terminal states the *read* side treats as closed, lifted out of the
# literals that used to be hard-coded in list_open_issues / _to_normalized
# (issue #245 §1.5). Covers Agile/CMMI (Closed), Basic/Scrum (Done), and
# Removed. Configurable per repo / globally as ``done_states``.
_DEFAULT_DONE_STATES = frozenset({"Closed", "Done", "Removed"})


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


class AzureTracker:
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
        # Accept the PAT under either key so hand-built repo_cfg dicts (e.g. the
        # MCP comment server, which keys it "token") authenticate correctly —
        # mirrors AzureVCS. (issue #168 F-06 regression)
        self._pat = repo_cfg.get("pat") or repo_cfg.get("token", "")
        self._authenticated_user: str | None = None
        self._resolved_repo_id: str | None = None
        # Cache of work-item-type → {category: state-name} from runtime state
        # discovery (issue #245 §1.5). Keyed per (project, type) so a second
        # close in the same poll doesn't re-query the states endpoint. A
        # ``None`` value is a negative cache for a failed/empty lookup.
        self._state_cache: dict[tuple[str, str], dict[str, str] | None] = {}
        # Single source of org/project/repo partition (issue #168 F-08):
        # build_repo_cfg normalises the main path; _normalize_azure_parts
        # covers inline throwaway repo_cfg dicts that skip build_repo_cfg.
        self._org, self._project, self._repo = _normalize_azure_parts(repo_cfg)

        # URL-encode for safe use in request URLs
        self._org_enc = _encode_path_segment(self._org)
        self._project_enc = _encode_path_segment(self._project)

    # ---- Repo ID resolution ----

    def resolve_repo_id(self) -> str | None:
        """Resolve the Git repository UUID for this repo (delegates to AzureVCS).

        The UUID lookup is VCS-side (``AzureVCS.resolve_repo_id``); this
        delegation keeps tracker-side callers working.
        """
        # Deferred import: factory imports this module.
        from autoswe.providers.factory import get_vcs
        return get_vcs(self._repo_cfg).resolve_repo_id()

    def slug_prefix(self) -> str:
        return "ado"

    def pid_prefix(self) -> str:
        return "ado_"

    # ---- Done-state resolution (issue #245 §1.5) ----

    def _done_states(self) -> frozenset[str]:
        """The terminal states the *read* side treats as closed.

        Lifted from config (``done_states`` on the repo_cfg — per-repo value
        beats the global seed ``build_repo_cfg`` sets) so a customized process
        that renames its terminal state is honoured on discovery, not just on
        close. Falls back to the historical hard-coded set.
        """
        raw = self._repo_cfg.get("done_states")
        if not raw:
            return _DEFAULT_DONE_STATES
        if isinstance(raw, (list, tuple, set, frozenset)):
            states = {str(s).strip() for s in raw if str(s).strip()}
        else:
            states = {s.strip() for s in str(raw).split(",") if s.strip()}
        return frozenset(states) or _DEFAULT_DONE_STATES

    def _state_category_map(self, work_item_type: str | None) -> dict[str, str] | None:
        """Map a work item type's states to their categories (cached).

        ``GET {org}/{project}/_apis/wit/workitemtypes/{type}/states`` returns
        one entry per state, each with a ``name`` and a ``category``
        (``Proposed`` / ``InProgress`` / ``Resolved`` / ``Completed`` /
        ``Removed``). Returns ``{category: state_name}`` (first wins on a
        category collision — the signal to set ``done_state`` explicitly) or
        ``None`` when the type is unknown or the lookup fails.
        """
        if not work_item_type:
            return None
        key = (self._project, work_item_type)
        if key in self._state_cache:
            return self._state_cache[key]
        path = _ado_api_version(
            f"https://dev.azure.com/{self._org_enc}/{self._project_enc}"
            f"/_apis/wit/workitemtypes/{_encode_path_segment(work_item_type)}/states"
        )
        try:
            raw = ado_get(path, self._pat)
        except Exception as e:
            dbg.warning(
                "state discovery failed for type %r: %s: %s",
                work_item_type, type(e).__name__, e,
            )
            self._state_cache[key] = None
            return None
        states = raw.get("value", raw) if isinstance(raw, dict) else raw
        mapping: dict[str, str] = {}
        for st in states or []:
            name = st.get("name")
            category = st.get("category")
            if name and category:
                mapping.setdefault(category, name)  # first-wins on a collision
        self._state_cache[key] = mapping or None
        return self._state_cache[key]

    def _resolve_done_state(self, issue_number: int, reason: str) -> str | None:
        """Resolve the single state value *close_issue* writes.

        Resolution order (issue #245 §1.5, first hit wins):
        1. per-repo / global ``done_state`` on the repo_cfg;
        2. runtime discovery — the ``Completed``-category state for the work
           item's type (the correct answer for any process, incl. custom);
        3. ``"Closed"`` fallback.

        For ``not_planned`` the write targets the ``Removed``-category state
        when the process has one, else the resolved done-state (a process may
        have no "removed" concept). Returns the state name, or None when no
        value could be determined (caller logs and skips rather than guessing).
        """
        configured = self._repo_cfg.get("done_state")
        if configured:
            configured = str(configured).strip()
            if configured:
                # Per-repo/global re-check at resolution (issue #245 §1.5): the
                # value written MUST be terminal per the read side, or the work
                # item is closed to a state the poller still reads as open and
                # is rediscovered forever. The global pair is validated at
                # config load; this catches a per-repo misconfiguration that
                # load_config never sees. A mismatch refuses the write rather
                # than guessing — it falls through to discovery / the fallback
                # below, which always produce a terminal state.
                terminal = self._done_states()
                if configured in terminal:
                    return configured
                dbg.warning(
                    "done_state=%r is not in the effective done_states %s; "
                    "refusing to write a non-terminal state (issue #245 §1.5) "
                    "— falling back to discovery",
                    configured, sorted(terminal),
                )

        # Runtime discovery needs the work item's type.
        try:
            issue = self.fetch_issue(issue_number)
        except Exception as e:
            dbg.warning(
                "close_issue: could not read work item %d for state discovery: %s: %s",
                issue_number, type(e).__name__, e,
            )
            return "Closed"

        categories = self._state_category_map(issue.work_item_type)
        if categories:
            if reason == "not_planned":
                removed = categories.get("Removed")
                if removed:
                    return removed
                return categories.get("Completed") or "Closed"
            completed = categories.get("Completed")
            if completed:
                return completed
        return "Closed"

    # ---- Protocol: IssueTracker ----

    def list_open_issues(self) -> list[NormalizedIssue]:
        """Return all open work items via WIQL + batch expand."""
        # Terminal states come from config (done_states) so a customized
        # process is honoured on discovery, not just on close (issue #245).
        terminal = ", ".join(f"'{s}'" for s in sorted(self._done_states()))
        wiql = {
            "query": (
                "SELECT [System.Id] FROM WorkItems "
                f"WHERE [System.State] NOT IN ({terminal}) "
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

        # De-dup ids up front (first occurrence wins) so no chunk request
        # carries duplicate IDs.
        seen: set[int] = set()
        id_list: list[int] = []
        for w in work_items:
            wid = w["id"]
            if wid not in seen:
                seen.add(wid)
                id_list.append(wid)

        # ADO caps the number of ids a single batch GET can carry; split into
        # chunks of _BATCH_CHUNK_SIZE and merge the responses.
        merged: list[dict] = []
        for start in range(0, len(id_list), _BATCH_CHUNK_SIZE):
            chunk = id_list[start:start + _BATCH_CHUNK_SIZE]
            ids_param = ",".join(str(i) for i in chunk)
            batch_path = _ado_api_version(
                f"https://dev.azure.com/{self._org_enc}/{self._project_enc}/_apis/wit/workitems"
                f"?ids={ids_param}&$expand=all"
            )
            batch_result = ado_get(batch_path, self._pat)
            merged.extend(batch_result.get("value", []))

        # De-dup merged items by id (first occurrence wins) and sort by id so
        # output ordering is deterministic regardless of chunk boundaries.
        merged_by_id: dict[int, dict] = {}
        for item in merged:
            merged_by_id.setdefault(item["id"], item)
        merged_sorted = sorted(merged_by_id.values(), key=lambda item: item["id"])

        return [self._to_normalized(item) for item in merged_sorted]

    def fetch_issue(self, issue_number: int) -> NormalizedIssue:
        """Fetch a single work item by number."""
        path = _ado_api_version(
            f"https://dev.azure.com/{self._org_enc}/{self._project_enc}/_apis/wit/workitems/{issue_number}"
            "?$expand=all"
        )
        raw = ado_get(path, self._pat)
        return self._to_normalized(raw)

    def fetch_comments(self, issue_number: int) -> list[NormalizedComment]:
        """Fetch all comments on a work item.

        Normalizes ``author_login`` for each comment so that orchestrator code
        (sync.py) can distinguish bot vs. user comments:

        - Bot comments (body matches ``_BOT_CONTENT_PATTERNS``) → ``"BOT"``
        - User comments matching the PAT authenticated user → ``"OWNER"``
        - Everything else → raw ``uniqueName`` (email)
        """
        # The work-item comments resource is under preview on hosted ADO:
        # stable 7.1 returns HTTP 400 asking for the -preview flag
        # (regression tracked in issue 022). format=Markdown so the `text`
        # field round-trips the stored Markdown.
        path = (
            f"https://dev.azure.com/{self._org_enc}/{self._project_enc}/_apis/wit/workitems/"
            f"{issue_number}/comments?format=Markdown&api-version=7.1-preview"
        )
        raw = ado_get(path, self._pat)
        comments_raw = raw.get("comments", [])

        # Resolve the authenticated PAT owner for comparison
        try:
            pat_owner = self.authenticated_user()
        except RuntimeError:  # ADO API lookup failure is non-fatal; skip OWNER normalization.
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

    def authenticated_user(self) -> str:
        """Return the email of the authenticated PAT owner.

        Primary: ADO Profile API (reliable, no dependency on work item existence).
        Fallback: work item #1 System.CreatedBy (legacy path).
        """
        if self._authenticated_user is not None:
            return self._authenticated_user

        # Primary: Profile API — works regardless of work item existence
        try:
            me_path = "https://app.vssps.visualstudio.com/_apis/profile/profiles/me?api-version=7.1"
            raw = ado_get(me_path, self._pat)
            # Documented profile fields first (docs/azure-devops-api/get-current-user.md:
            # displayName, publicAlias, emailAddress, coreRevision, timeStamp, id, revision);
            # principalName/uniqueName are legacy ADO Server/TFS profile shapes.
            self._authenticated_user = (
                raw.get("emailAddress", "")
                or raw.get("displayName", "")
                or raw.get("principalName", "")
                or raw.get("uniqueName", "")
            )
            if self._authenticated_user:
                return self._authenticated_user
        except RuntimeError:  # Profile API call failed; fall through to workitem fallback.
            pass

        # Fallback: work item #1 CreatedBy
        try:
            path = _ado_api_version(
                f"https://dev.azure.com/{self._org_enc}/{self._project_enc}/_apis/wit/workitems/1"
            )
            raw = ado_get(path, self._pat)
            created_by = raw.get("fields", {}).get("System.CreatedBy", {})
            self._authenticated_user = created_by.get("uniqueName", "")
        except RuntimeError:  # Work item lookup also failed; leave _authenticated_user as None.
            pass

        return self._authenticated_user or ""

    # ---- Write methods (Stage 5) ----

    def post_comment(self, issue_number: int, body: str) -> int | None:
        """Post a comment on a work item. Returns comment ID or None.

        Always uses ``format=Markdown`` so ADO renders headings, lists,
        links, bold, inline code, and other Markdown natively.
        """
        path = (
            f"https://dev.azure.com/{self._org_enc}/{self._project_enc}/_apis/wit/workitems/"
            f"{issue_number}/comments?format=Markdown&api-version=7.1-preview"
        )
        result = ado_post(path, self._pat, body={"text": redact_outbound(body)})
        return result.get("id") if result else None

    def update_comment(self, issue_number: int, comment_id: int, body: str) -> None:
        """Edit a comment on a work item via PATCH.

        ``PATCH .../comments/{id}`` has no refreshed reference page in
        docs/azure-devops-api/; the live round-trip test in
        tests/test_azure_live.py covers it. The comments resource is under
        preview on hosted ADO, so this uses 7.1-preview (regression tracked
        in issue 022).
        """
        path = (
            f"https://dev.azure.com/{self._org_enc}/{self._project_enc}/_apis/wit/workitems/"
            f"{issue_number}/comments/{comment_id}?format=Markdown&api-version=7.1-preview"
        )
        ado_patch_json(path, self._pat, body={"text": redact_outbound(body)})

    def create_issue(self, title: str, body: str) -> int:
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

    def close_issue(self, issue_number: int, reason: str = "completed") -> None:
        """Transition the work item to its done state (edge E5).

        Azure has no auto-close: merging a PR never changes the work item's
        ``System.State``, so this explicit write is the only way the work item
        reaches a terminal state (issue #245 §1.5). The state value is
        resolved per §1.5 (configured → runtime discovery → ``Closed``) and the
        write is a single ``System.State`` JSON-Patch op.

        A 400 from ADO (a process that forbids the direct jump, or one that
        requires ``System.Reason`` alongside the state) is logged with the
        discovered states and surfaced as a one-time operator comment — never
        retried with a different state. A wrong state write is worse than
        none, so we do not guess.
        """
        state = self._resolve_done_state(issue_number, reason)
        if not state:
            dbg.warning(
                "close_issue(%d): no done state resolvable for reason=%r; "
                "set done_state in repos.json", issue_number, reason,
            )
            return

        patch_path = _ado_api_version(
            f"https://dev.azure.com/{self._org_enc}/{self._project_enc}/_apis/wit/workitems/{issue_number}"
        )
        try:
            ado_patch(
                patch_path, self._pat,
                body=[{"op": "add", "path": "/fields/System.State", "value": state}],
            )
        except Exception as e:
            err = str(e)
            if "HTTP 400" in err:
                discovered = self._state_category_map(self._work_item_type(issue_number))
                available = (
                    ", ".join(sorted(discovered.values())) if discovered else "unknown"
                )
                dbg.warning(
                    "close_issue(%d): ADO rejected state %r (available: %s); "
                    "set done_state explicitly in repos.json",
                    issue_number, state, available,
                )
                self._post_done_state_hint(issue_number, state, available)
            else:
                raise

    def _work_item_type(self, issue_number: int) -> str | None:
        """Read the work item's ``System.WorkItemType`` (best-effort)."""
        try:
            return self.fetch_issue(issue_number).work_item_type
        except Exception:
            return None

    def _post_done_state_hint(self, issue_number: int, state: str, available: str) -> None:
        """Post a one-time operator note after a rejected done-state write.

        Guarded by a content marker in the existing bot comments so we never
        spam a hint on every poll while the work item stays open.
        """
        marker = "<AUTOSWE_DONE_STATE_HINT>"
        try:
            for c in self.fetch_comments(issue_number):
                if marker in (c.body or ""):
                    return
        except Exception:
            pass
        body = (
            f"{marker}\n\n"
            f"autoSWE could not transition this work item to **{state}** "
            f"(ADO rejected the state; available states: {available}). "
            f"Set `done_state` in `repos.json` for this repo to the state your "
            f"process uses for completion, then re-run `/sync`."
        )
        try:
            self.post_comment(issue_number, body)
        except Exception:
            pass

    def capabilities(self) -> frozenset[Capability]:
        """Declared ADO tracker capabilities.

        Azure declares none of the tracker-side capabilities: there is no
        auto-close mechanic (``AUTO_CLOSE_ON_MERGE``) — ``close_issue`` is the
        explicit write that replaces it, which is exactly why it is *not*
        declared here (issue #245 §1.5).
        """
        return frozenset()

    def set_status(self, issue_number: int, status: str) -> None:
        """Set the autoswe status tag on a work item (read-modify-write).

        GETs the current work item, strips existing autoswe:* tags,
        appends the new status tag, and PATCHes via JSON-Patch.

        The write is a two-op patch — ``remove`` then ``add`` on
        ``/fields/System.Tags``. ADO applies ``op: "add"`` on ``System.Tags``
        additively (it merges the value into the existing tag set instead of
        replacing the field), so a lone ``add`` re-merges the tags we just
        stripped and the status tags accumulate across transitions. Clearing
        the field first guarantees the written value is the complete tag set
        (issue #235).
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

        # PATCH via JSON-Patch: remove first, then add. ``add`` on System.Tags
        # is additive on the server (see docstring), so the ``remove`` is what
        # makes this a true replace of the tag set.
        patch_path = _ado_api_version(
            f"https://dev.azure.com/{self._org_enc}/{self._project_enc}/_apis/wit/workitems/{issue_number}"
        )
        ado_patch(
            patch_path, self._pat,
            body=[
                {"op": "remove", "path": "/fields/System.Tags"},
                {"op": "add", "path": "/fields/System.Tags", "value": "; ".join(new_tags)},
            ],
        )

    def normalize_comment_body(self, comment: NormalizedComment) -> tuple[str, bool]:
        """Return ``(body, is_bot)`` after provider-specific normalisation.

        Azure DevOps wraps rich-text user comments in ``<div>`` tags and stores
        HTML entities in the body, so decode entities and strip HTML tags
        (preserving ``<AUTOSWE_*>`` markers). Bot detection is content-based
        because ADO strips HTML comments from rendered bodies, so the
        BOT_MARKER alone is not reliable.
        """
        body = html.unescape(comment.body or "")
        body = _strip_html(body)
        return body, _is_bot_comment(body)

    def assign_to_user(self, issue_number: int, login: str | None) -> None:
        """Assign the work item to a user.

        If ``login`` is None, resolves to the authenticated PAT owner.
        Uses the email/UPN as the assigned-to value.
        """
        if login is None:
            login = self.authenticated_user()

        patch_path = _ado_api_version(
            f"https://dev.azure.com/{self._org_enc}/{self._project_enc}/_apis/wit/workitems/{issue_number}"
        )
        ado_patch(
            patch_path, self._pat,
            body=[{"op": "add", "path": "/fields/System.AssignedTo", "value": login}],
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
        # The terminal set is the same config-driven set close_issue writes
        # against (§1.5 invariant: the value written must be a member of the
        # set the read side treats as terminal, or the item re-discovers forever).
        state = "closed" if raw_state in self._done_states() else "open"
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
            work_item_type=fields.get("System.WorkItemType"),
        )
