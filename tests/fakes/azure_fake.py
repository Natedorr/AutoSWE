"""Stateful in-memory Azure DevOps API fake.

Parallel to ``github_fake.py`` but for the Azure DevOps provider.
Replaces ``autoswe.providers.azure.api._ado_request``.

Responses are built from canonical API fixtures (``tests/fakes/templates.py``)
with mutable state (work items, comments, etc.) overlaid on top.
"""
from __future__ import annotations

import copy
import re

from tests.fakes import templates as T

# Match work item paths in both full-URL and relative forms:
#   https://dev.azure.com/org/proj/_apis/wit/workitems/42
#   /org/proj/_apis/wit/workitems/42
_WORK_ITEM_RE = re.compile(r"/_apis/wit/workitems/(?P<num>\d+)")

# Match comment paths:
#   https://dev.azure.com/org/proj/_apis/wit/workitems/42/comments
_COMMENT_RE = re.compile(r"/_apis/wit/workitems/(?P<num>\d+)/comments")
# Match individual comment paths:
#   https://dev.azure.com/org/proj/_apis/wit/workitems/42/comments/999
_COMMENT_ID_RE = re.compile(r"/_apis/wit/workitems/(?P<num>\d+)/comments/(?P<cid>\d+)")

# Exact match for work item #1 (authenticated_user fallback)
_WI_1_RE = re.compile(r"/_apis/wit/workitems/1(?:[?/]|$)")


def _parse_ado_path(path: str) -> tuple[str, str, str] | None:
    """Return (org, project, repo) from an ADO API path, or None."""
    parts = path.strip("/").split("/")
    if len(parts) >= 2:
        return parts[0], parts[1], parts[2] if len(parts) > 2 else ""
    return None


# ---------------------------------------------------------------------------
# Fake
# ---------------------------------------------------------------------------

class AzureFake:
    """In-memory Azure DevOps API state machine.

    Attributes (mutable, for assertions):
        work_items - dict[int, dict]  work item payloads keyed by ID
        comments   - dict[int, list[dict]]  comments per work item
        pulls      - dict[int, dict]  PR payloads keyed by ID
        recorded_calls - list[dict]  every API call
        posted_comments - list[dict]  all POSTed comments
    """

    def __init__(self):
        self.work_items: dict[int, dict] = {}
        self.comments: dict[int, list[dict]] = {}
        self.pulls: dict[int, dict] = {}
        self.recorded_calls: list[dict] = []
        self.posted_comments: list[dict] = []
        self._next_pr_number = 1
        self._authenticated_user = T.azure_current_user()
        self._repos: list[dict] = []
        self._org = ""
        self._project = ""
        self._repo = ""

    # ------------------------------------------------------------------
    # Loading initial state from scenario fixtures
    # ------------------------------------------------------------------

    def load(self, state: dict) -> None:
        """Load a scenario snapshot for Azure DevOps.

        Expected keys: org, project, repo, work_item (dict), tags (list[str]),
        comments (list[dict]), authenticated_user (optional dict).
        """
        self._org = state.get("org", "")
        self._project = state.get("project", "")
        self._repo = state.get("repo", "")

        wi = state.get("work_item")
        wi_num = 1
        if wi:
            wi_num = wi.get("id", 1)
            self.work_items[wi_num] = copy.deepcopy(wi)
            self.work_items[wi_num]["fields"] = self.work_items[wi_num].get("fields", {})
            self.work_items[wi_num]["fields"]["System.Tags"] = "; ".join(
                state.get("tags", [])
            )

        self.comments[wi_num] = [copy.deepcopy(c) for c in state.get("comments", [])]
        # Assign deterministic IDs to pre-loaded comments
        for idx, c in enumerate(self.comments[wi_num], 1):
            if "id" not in c:
                c["id"] = idx

        if state.get("authenticated_user"):
            self._authenticated_user = copy.deepcopy(state["authenticated_user"])
        if state.get("repos"):
            self._repos = [copy.deepcopy(r) for r in state["repos"]]

    # ------------------------------------------------------------------
    # Patchable _ado_request replacement
    # ------------------------------------------------------------------

    def handle_request(self, method: str, path: str, pat: str, body: dict | None = None,
                       content_type: str = "application/json", max_retries: int = 3) -> dict:
        """Route an ADO API call and mutate state."""
        self.recorded_calls.append({
            "method": method,
            "path": path,
            "body": copy.deepcopy(body) if body else None,
            "pat": pat,
            "content_type": content_type,
        })

        # ---- Extract work item number early for later use ----
        wi_match = _WORK_ITEM_RE.search(path)
        comment_match = _COMMENT_RE.search(path)
        wi_num = None
        if wi_match:
            wi_num = int(wi_match.group("num"))
        if comment_match:
            wi_num = int(comment_match.group("num"))

        # ---- GET current user ----
        if "_apis/profile" in path or "/_users/me" in path:
            return copy.deepcopy(self._authenticated_user)

        # ---- GET repos (before more specific repository routes) ----
        if "git/repositories" in path and method == "GET" and "/pullrequests" not in path:
            repos = self._repos if self._repos else T.azure_list_repositories().get("value", [])
            return {"count": len(repos), "value": copy.deepcopy(repos)}

        # ---- GET comments on work item (before work item routes, more specific) ----
        if comment_match and method == "GET":
            comments_list = self.comments.get(wi_num, [])
            return {"count": len(comments_list),
                    "comments": copy.deepcopy(comments_list)}

        # ---- PATCH individual comment (before collection comment routes) ----
        comment_id_match = _COMMENT_ID_RE.search(path)
        if comment_id_match and method == "PATCH":
            cid_match = comment_id_match
            ci_num = int(cid_match.group("num"))
            cid = int(cid_match.group("cid"))
            comment_text = (body or {}).get("text", "")
            comments_list = self.comments.get(ci_num, [])
            for c in comments_list:
                if c.get("id") == cid:
                    c["text"] = comment_text
                    break
            return {"id": cid, "text": comment_text}

        # ---- POST comment on work item (before work item routes, more specific) ----
        if comment_match and method == "POST":
            comment_body = (body or {}).get("text", "")
            comment = copy.deepcopy(T.azure_create_workitem_comment())
            comment["id"] = len(self.recorded_calls) + 1000
            comment["text"] = comment_body
            comment["createdBy"] = copy.deepcopy(self._authenticated_user)
            self.comments.setdefault(wi_num, []).append(copy.deepcopy(comment))
            self.posted_comments.append({
                "org": self._org, "project": self._project, "repo": self._repo,
                "work_item": wi_num, "body": comment_body,
            })
            return comment

        # ---- GET work item #1 (authenticated_user fallback) -- exact match only ----
        if method == "GET" and _WI_1_RE.search(path):
            wi = self.work_items.get(1)
            if wi:
                return copy.deepcopy(wi)
            return {
                "id": 1,
                "fields": {
                    "System.CreatedBy": {
                        "uniqueName": self._authenticated_user.get("uniqueName", "testowner"),
                        "id": self._authenticated_user.get("id", "1"),
                    }
                },
            }

        # ---- GET single work item ----
        if wi_num is not None and method == "GET":
            wi = self.work_items.get(wi_num)
            if wi:
                return copy.deepcopy(wi)
            return {}

        # ---- PATCH work item (update fields/tags) ----
        if wi_num is not None and method in ("PATCH", "PUT"):
            if wi_num in self.work_items and body and isinstance(body, list):
                for op in body:
                    op_type = op.get("op", "")
                    op_path = op.get("path", "")
                    value = op.get("value")
                    if op_type in ("add", "replace") and op_path.startswith("/fields/"):
                        field = op_path.removeprefix("/fields/")
                        self.work_items[wi_num].setdefault("fields", {})[
                            field
                        ] = value
            return copy.deepcopy(self.work_items.get(wi_num, {}))

        # ---- POST WIQL query (list work items) ----
        if "wit/wiql" in path and method == "POST":
            items = []
            for num, wi in self.work_items.items():
                state_val = wi.get("fields", {}).get("System.State", "")
                if state_val.lower() not in ("closed", "done", "removed"):
                    items.append({"id": num})
            return {"workItems": items}

        # ---- GET work items (batch by ids, or list) ----
        if "wit/workitems" in path and "api-version" in path and method == "GET":
            # Extract ids from query param for batch fetch
            ids_param = None
            if "ids=" in path:
                for part in path.split("?"):
                    for param in part.split("&"):
                        if param.startswith("ids="):
                            ids_param = [int(x) for x in param.split("=")[1].split(",")]
                            break
            if ids_param is not None:
                items = [copy.deepcopy(self.work_items[nid]) for nid in ids_param if nid in self.work_items]
            else:
                items = []
                for _num, wi in self.work_items.items():
                    out = copy.deepcopy(wi)
                    if "fields" in out:
                        if "$filter" in path and "closed" in path:
                            if out["fields"].get("System.State", "").lower() == "closed":
                                items.append(out)
                        else:
                            items.append(out)
                    else:
                        items.append(out)
            return {"count": len(items), "value": items}

        # ---- PUT /repos/{o}/{r}/issues/{n}/labels (GitHub API path used by _set_autoswe_status) ----
        # This bridges GitHub-style label calls to Azure work item tags.
        if method == "PUT" and "/issues/" in path and "/labels" in path:
            m = re.search(r"/issues/(\d+)/labels", path)
            if m and body and "labels" in body:
                issue_n = int(m.group(1))
                label_names = [lb["name"] if isinstance(lb, dict) else lb
                               for lb in body["labels"]]
                if issue_n in self.work_items:
                    self.work_items[issue_n].setdefault("fields", {})[
                        "System.Tags"
                    ] = "; ".join(label_names)
            return {}

        # ---- POST PR ----
        if "git/repositories" in path and "/pullrequests" in path and method == "POST":
            pr_number = self._next_pr_number
            self._next_pr_number += 1
            pr_body = body or {}
            pr = copy.deepcopy(T.azure_create_pullrequest())
            pr["pullRequestId"] = pr_number
            pr["title"] = pr_body.get("title", pr.get("title", ""))
            pr["sourceRefName"] = f"refs/heads/{pr_body.get('sourceRefName', pr['sourceRefName'].removeprefix('refs/heads/'))}"
            pr["targetRefName"] = f"refs/heads/{pr_body.get('targetRefName', pr['targetRefName'].removeprefix('refs/heads/'))}"
            pr["url"] = f"https://dev.azure.com/{self._org}/{self._project}/_git/{self._repo}/pullrequest/{pr_number}"
            self.pulls[pr_number] = pr
            return pr

        # ---- GET PRs ----
        if "/pullrequests" in path and method == "GET":
            return {"count": len(self.pulls),
                    "value": [copy.deepcopy(pr) for pr in self.pulls.values()]}

        return {}

    _real_ado_request = None  # Class-level cache of the real _ado_request

    @classmethod
    def _get_real_request(cls):
        """Return the real _ado_request, cached on first call."""
        if cls._real_ado_request is None:
            import autoswe.providers.azure.api as ado_mod
            cls._real_ado_request = ado_mod._ado_request
        return cls._real_ado_request

    # ------------------------------------------------------------------
    # Monkeypatch helpers
    # ------------------------------------------------------------------

    def patch(self):
        """Patch into autoswe.providers.azure.api.  Returns (module, original)."""
        import autoswe.providers.azure.api as ado_mod

        # Cache original BEFORE replacing module attribute
        self.__class__._get_real_request()
        self._saved_original = ado_mod._ado_request
        ado_mod._ado_request = self.handle_request
        return ado_mod, self._saved_original

    def unpatch(self, module, original) -> None:
        """Restore _ado_request, always using the cached real function."""
        module._ado_request = self._get_real_request()
