from autoswe.core.logging_utils import log
from autoswe.tracking.api import gh_get, gh_post


def _get_authenticated_user(token: str):
    """Return the GitHub login of the authenticated user (from token)."""
    try:
        user = gh_get("/user", token)
        return user.get("login")
    except RuntimeError:
        return None


def _auto_assign_issue(owner: str, repo: str, issue_number: int, token: str, username: str = None) -> None:
    """Auto-assign the authenticated user to the issue so it shows in their todo list.
    Idempotent — skips if already assigned."""
    if not username:
        username = _get_authenticated_user(token)
    if not username:
        return
    try:
        current = gh_get(f"/repos/{owner}/{repo}/issues/{issue_number}", token)
        assignees = [a["login"] for a in current.get("assignees", [])]
        if username not in assignees:
            gh_post(f"/repos/{owner}/{repo}/issues/{issue_number}/assignees",
                    token, {"assignees": [username]})
            log(f"[ASSIGN] {owner}/{repo}#{issue_number} -> @{username}")
    except RuntimeError as e:
        log(f"[WARN] could not assign {owner}/{repo}#{issue_number}: {e}")
