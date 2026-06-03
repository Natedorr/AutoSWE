"""Stateful in-memory GitHub API fake.

Replaces ``autoswe.tracking.api._gh_request`` so that outbound calls
(PUT labels, POST comments, etc.) persist state that subsequent sync or
dispatch cycles can read back.  Each scenario loads its initial snapshot
via ``.load(state_dict)``; after the turn the test asserts the recorded
calls and mutated state.

Responses are built from canonical API fixtures (``tests/fakes/templates.py``)
with mutable state (labels, comments, etc.) overlaid on top.
"""
from __future__ import annotations

import copy
import re

from tests.fakes import templates as T

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REPOS_RE = re.compile(r"^/repos/([^/]+)/([^/]+)")


def _owner_repo(path: str) -> tuple[str, str] | None:
    """Return (owner, repo) from a path like /repos/o/r/..., or None."""
    m = _REPOS_RE.match(path)
    if m:
        return m.group(1), m.group(2)
    return None


def _issue_number(path: str) -> int | None:
    """Return issue number from .../issues/N or .../issues/N/..., or None."""
    parts = path.split("/")
    for i, p in enumerate(parts):
        if p == "issues" and i + 1 < len(parts):
            try:
                return int(parts[i + 1])
            except ValueError:
                pass
    return None


def _label_dict(name: str) -> dict:
    """Build a minimal label dict."""
    return {"name": name, "color": "000000"}


def _resolve_label(repo_labels: list[dict], name: str) -> dict:
    """Find a full label dict from repo_labels, or build a minimal one."""
    for lb in repo_labels:
        if lb.get("name") == name:
            return lb
    return _label_dict(name)


# ---------------------------------------------------------------------------
# Fake
# ---------------------------------------------------------------------------

class GitHubFake:
    """In-memory GitHub API state machine.

    Attributes (mutable, for assertions):
        issues  - dict[int, dict]     issue payloads keyed by number
        labels  - dict[int, list[str]] current label names per issue
        comments - dict[int, list[dict]] comment payloads per issue
        repo_labels - dict[str, list[dict]] repo label definitions keyed by "owner/repo"
        pulls   - dict[int, dict]     PR payloads keyed by number
        recorded_calls - list[dict]   every API call (method, path, body)
        posted_comments - list[dict]  all POSTed comments with owner/repo/issue
    """

    def __init__(self):
        self.issues: dict[int, dict] = {}
        self.labels: dict[int, list[str]] = {}
        self.comments: dict[int, list[dict]] = {}
        self.repo_labels: dict[str, list[dict]] = {}
        self.pulls: dict[int, dict] = {}
        self.recorded_calls: list[dict] = []
        self.posted_comments: list[dict] = []
        self.inline_comments: list[dict] = []
        self.check_runs: list[dict] = []
        self._next_pr_number = 1
        self._authenticated_user = T.github_user()
        self._owned_repos: list[dict] = []

    # ------------------------------------------------------------------
    # Loading initial state from scenario fixtures
    # ------------------------------------------------------------------

    def load(self, state: dict) -> None:
        """Load a scenario snapshot (from state.json).

        Expected keys in *state*:
            owner, repo, issue (dict), labels (list[str]), comments (list[dict]),
            repo_labels (list[dict]), authenticated_user (optional dict),
            owned_repos (optional list).
        """
        owner = state.get("owner", "")
        repo = state.get("repo", "")
        issue_payload = state.get("issue")
        issue_num = issue_payload.get("number", 1) if issue_payload else 1

        if issue_payload:
            self.issues[issue_num] = copy.deepcopy(issue_payload)
            self.labels[issue_num] = list(state.get("labels", []))

        self.comments[issue_num] = [copy.deepcopy(c) for c in state.get("comments", [])]
        # Assign deterministic IDs to pre-loaded comments
        for idx, c in enumerate(self.comments[issue_num], 1):
            if "id" not in c:
                c["id"] = idx
        repo_key = f"{owner}/{repo}"
        self.repo_labels[repo_key] = [copy.deepcopy(lb) for lb in state.get("repo_labels", [])]
        # Now resolve labels on the issue payload from repo_labels
        if issue_payload:
            self.issues[issue_num]["labels"] = [
                copy.deepcopy(_resolve_label(self.repo_labels[repo_key], lb))
                for lb in self.labels[issue_num]
            ]

        if state.get("authenticated_user"):
            self._authenticated_user = copy.deepcopy(state["authenticated_user"])
        if state.get("owned_repos"):
            self._owned_repos = [copy.deepcopy(r) for r in state["owned_repos"]]

    def add_issue(self, number: int, payload: dict, labels: list[str],
                  comments: list[dict] | None = None) -> None:
        """Add (or replace) an issue manually (convenience for tests)."""
        self.issues[number] = copy.deepcopy(payload)
        self.labels[number] = list(labels)
        self.issues[number]["labels"] = [
            copy.deepcopy(_resolve_label(next(iter(self.repo_labels.values())) if self.repo_labels else [], lb))
            for lb in labels
        ]
        if comments:
            self.comments[number] = [copy.deepcopy(c) for c in comments]
            for idx, c in enumerate(self.comments[number], 1):
                if "id" not in c:
                    c["id"] = idx

    # ------------------------------------------------------------------
    # Patchable _gh_request replacement
    # ------------------------------------------------------------------

    def handle_request(self, method: str, path: str, token: str,
                       body: dict | None = None, max_retries: int = 3,
                       timeout: float = 30) -> dict:
        """Route an API call and mutate state.

        Returns the response body (same shape as the real _gh_request).
        """
        self.recorded_calls.append({
            "method": method,
            "path": path,
            "body": copy.deepcopy(body) if body else None,
            "token": token,
        })

        owner_repo = _owner_repo(path)
        issue_num = _issue_number(path)

        # ---- GET /user ----
        if path == "/user" and method == "GET":
            return copy.deepcopy(self._authenticated_user)

        # ---- GET /user/repos?type=owner ----
        if path.startswith("/user/repos") and method == "GET":
            if self._owned_repos:
                return copy.deepcopy(self._owned_repos)
            return T.github_list_repos()

        # ---- GET /repos/{o}/{r}/labels ----
        if method == "GET" and re.match(r"^/repos/[^/]+/[^/]+/labels$", path) and owner_repo:
            key = f"{owner_repo[0]}/{owner_repo[1]}"
            if key in self.repo_labels:
                return copy.deepcopy(self.repo_labels[key])
            return T.github_list_repo_labels()

        # ---- POST /repos/{o}/{r}/labels (ensure label creation) ----
        if method == "POST" and re.match(r"^/repos/[^/]+/[^/]+/labels$", path):
            if owner_repo and body:
                key = f"{owner_repo[0]}/{owner_repo[1]}"
                if key not in self.repo_labels:
                    self.repo_labels[key] = []
                new_label = {"name": body.get("name", ""), "color": body.get("color", "000000")}
                names = {lb["name"] for lb in self.repo_labels[key]}
                if new_label["name"] not in names:
                    self.repo_labels[key].append(new_label)
                return copy.deepcopy(new_label)

        # ---- GET /repos/{o}/{r}/issues?...  (paginated list) ----
        if method == "GET" and path.startswith("/repos/") and "/issues?" in path:
            if owner_repo:
                key = f"{owner_repo[0]}/{owner_repo[1]}"
                results = []
                for num, issue in self.issues.items():
                    if issue.get("state") == "closed":
                        continue
                    out = copy.deepcopy(issue)
                    current_labels = self.labels.get(num, [])
                    out["labels"] = [copy.deepcopy(_resolve_label(self.repo_labels.get(key, []), lb)) for lb in current_labels]
                    results.append(out)
                return results

        # ---- GET /repos/{o}/{r}/issues/{n} ----
        if method == "GET" and issue_num is not None and f"/issues/{issue_num}" in path:
            # Distinguish comments path
            if f"/issues/{issue_num}/comments" in path:
                return copy.deepcopy(self.comments.get(issue_num, []))
            if f"/issues/{issue_num}/labels" in path:
                current = self.labels.get(issue_num, [])
                repo_key = f"{owner_repo[0]}/{owner_repo[1]}" if owner_repo else ""
                return [copy.deepcopy(_resolve_label(self.repo_labels.get(repo_key, []), lb)) for lb in current]
            if f"/issues/{issue_num}/assignees" in path:
                issue = self.issues.get(issue_num)
                if issue:
                    return copy.deepcopy(issue.get("assignees", []))
                return []
            # Single issue GET
            issue = self.issues.get(issue_num)
            if issue:
                out = copy.deepcopy(issue)
                current_labels = self.labels.get(issue_num, [])
                repo_key = f"{owner_repo[0]}/{owner_repo[1]}" if owner_repo else ""
                out["labels"] = [copy.deepcopy(_resolve_label(self.repo_labels.get(repo_key, []), lb)) for lb in current_labels]
                return out
            return {}

        # ---- PUT /repos/{o}/{r}/issues/{n}/labels ----
        if method == "PUT" and issue_num is not None and f"/issues/{issue_num}/labels" in path:
            if body and "labels" in body:
                self.labels[issue_num] = [lb["name"] if isinstance(lb, dict) else lb
                                          for lb in body["labels"]]
                if issue_num in self.issues:
                    repo_key = f"{owner_repo[0]}/{owner_repo[1]}" if owner_repo else ""
                    self.issues[issue_num]["labels"] = [
                        copy.deepcopy(_resolve_label(self.repo_labels.get(repo_key, []), lb))
                        for lb in self.labels[issue_num]
                    ]
            return {}

        # ---- POST /repos/{o}/{r}/issues/{n}/comments ----
        if method == "POST" and issue_num is not None and f"/issues/{issue_num}/comments" in path:
            comment_body = ""
            if isinstance(body, dict) and "body" in body:
                comment_body = body["body"]
            elif isinstance(body, str):
                comment_body = body
            comment = copy.deepcopy(T.github_create_comment())
            comment["id"] = len(self.recorded_calls) + 1000
            comment["body"] = comment_body
            comment["user"] = copy.deepcopy(self._authenticated_user)
            self.comments.setdefault(issue_num, []).append(copy.deepcopy(comment))
            posted_info = {"owner": owner_repo[0] if owner_repo else "",
                           "repo": owner_repo[1] if owner_repo else "",
                           "issue_number": issue_num,
                           "body": comment_body}
            self.posted_comments.append(posted_info)
            return comment  # returns comment dict with ID

        # ---- PATCH/PUT /repos/{o}/{r}/issues/comments/{id} ----
        if method in ("PATCH", "PUT") and "/issues/comments/" in path:
            comment_id_str = path.split("/issues/comments/")[1].split("?")[0].split("/")[0]
            try:
                comment_id = int(comment_id_str)
            except ValueError:
                return {}
            new_body = (body or {}).get("body", "")
            for _issue_num, comments in self.comments.items():
                for c in comments:
                    if c.get("id") == comment_id:
                        c["body"] = new_body
                        return copy.deepcopy(c)
            return {}

        # ---- POST /repos/{o}/{r}/issues/{n}/assignees ----
        if method == "POST" and issue_num is not None and f"/issues/{issue_num}/assignees" in path:
            login = (body or {}).get("assignee") or (body or {}).get("assignees", ["testowner"])[0]
            assignee = copy.deepcopy(T.github_add_assignees())
            assignee["login"] = login
            if issue_num in self.issues:
                self.issues[issue_num].setdefault("assignees", []).append(
                    copy.deepcopy(assignee)
                )
            return assignee

        # ---- POST /repos/{o}/{r}/pulls ----
        if method == "POST" and "/pulls" in path:
            pr_number = self._next_pr_number
            self._next_pr_number += 1
            pr_body = body or {}
            pr = copy.deepcopy(T.github_create_pull())
            pr["number"] = pr_number
            pr["title"] = pr_body.get("title", pr.get("title", ""))
            pr["head"]["ref"] = pr_body.get("head", pr["head"]["ref"])
            pr["base"]["ref"] = pr_body.get("base", pr["base"]["ref"])
            pr["user"] = copy.deepcopy(self._authenticated_user)
            pr_url = f"https://github.com/{owner_repo[0] if owner_repo else 'o'}/{owner_repo[1] if owner_repo else 'r'}/pull/{pr_number}"
            pr["url"] = pr_url
            pr["html_url"] = pr_url
            self.pulls[pr_number] = pr
            return pr

        # ---- GET /repos/{o}/{r}/pulls?... ----
        if method == "GET" and "/pulls?" in path:
            return [copy.deepcopy(pr) for pr in self.pulls.values()]

        # ---- GET /repos/{o}/{r}/pulls/{n} ----
        if method == "GET" and re.match(r"^/repos/[^/]+/[^/]+/pulls/\d+", path):
            parts = path.split("/")
            if len(parts) >= 7:
                try:
                    pr_num = int(parts[6])
                    pr = self.pulls.get(pr_num)
                    if pr:
                        return copy.deepcopy(pr)
                except ValueError:
                    pass
            return {}

        # ---- POST /repos/{o}/{r}/pulls/{n}/comments (inline review) ----
        if method == "POST" and "/pulls/" in path and "/comments" in path:
            parts = path.split("/")
            if len(parts) >= 8:
                try:
                    pr_num = int(parts[6])
                except ValueError:
                    pass
                else:
                    comment_body = ""
                    comment_file = ""
                    comment_line = None
                    if isinstance(body, dict):
                        comment_body = body.get("body", "")
                        comment_file = body.get("path", "")
                        comment_line = body.get("line")
                    inline = {
                        "pr_number": pr_num,
                        "body": comment_body,
                        "path": comment_file,
                        "line": comment_line,
                        "owner": owner_repo[0] if owner_repo else "",
                        "repo": owner_repo[1] if owner_repo else "",
                    }
                    self.inline_comments.append(inline)
                    return {
                        "html_url": f"https://github.com/{owner_repo[0] if owner_repo else 'o'}/{owner_repo[1] if owner_repo else 'r'}/pull/{pr_num}/files#L{comment_line or 1}",
                        "id": len(self.recorded_calls) + 2000,
                    }
            return {}

        # POST /repos/{o}/{r}/check-runs
        if method == "POST" and "/check-runs" in path:
            check_run = {
                "id": len(self.recorded_calls) + 3000,
                "name": (body or {}).get("name", ""),
                "head_sha": (body or {}).get("head_sha", ""),
                "status": (body or {}).get("status", "completed"),
                "conclusion": (body or {}).get("conclusion", "success"),
            }
            self.check_runs.append(check_run)
            return check_run

        # Unhandled route — return empty dict so tests don't crash silently
        return {}

    # ------------------------------------------------------------------
    # Monkeypatch helpers
    # ------------------------------------------------------------------

    _real_gh_request = None  # Class-level cache of the real _gh_request

    @classmethod
    def _get_real_request(cls):
        """Return the real _gh_request, cached on first call.

        Caching ensures we always restore to the actual function even if a
        previous test leaked a mock (test-isolation resilience).
        """
        if cls._real_gh_request is None:
            import autoswe.tracking.api as api_mod
            cls._real_gh_request = api_mod._gh_request
        return cls._real_gh_request

    def patch(self):
        """Patch into autoswe.tracking.api.  Returns (module, original)."""
        import autoswe.tracking.api as api_mod

        # Cache original BEFORE replacing module attribute
        self.__class__._get_real_request()
        self._saved_original = api_mod._gh_request
        api_mod._gh_request = self.handle_request
        return api_mod, self._saved_original

    def unpatch(self, module, original) -> None:
        """Restore _gh_request, always using the cached real function.

        Using the cached real function (rather than whatever was saved at
        patch time) prevents leaked mocks from propagating across tests.
        """
        module._gh_request = self._get_real_request()
