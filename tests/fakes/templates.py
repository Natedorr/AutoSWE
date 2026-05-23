"""Load canonical API response templates from fixtures.

Provides deep-copied templates (stripped of ``__meta``) so that fakes
build responses from the same source of truth as contract tests.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

_FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "api"


def load_template(provider: str, endpoint_name: str) -> Any:
    """Load and deep-copy a canonical API fixture template.

    Strips the ``__meta`` block.  For fixtures that use a ``data`` key
    (list endpoints), returns the ``data`` value directly.  For dict
    fixtures, returns all keys except ``__meta``.

    Args:
        provider: ``"github"`` or ``"azure"``
        endpoint_name: Fixture filename stem (e.g. ``"get_issue"``)

    Returns:
        A deep-copied response body ready to be mutated by the fake.
    """
    path = _FIXTURE_DIR / provider / f"{endpoint_name}.json"
    fixture = json.loads(path.read_text(encoding="utf-8"))

    if "data" in fixture:
        return copy.deepcopy(fixture["data"])
    return {k: v for k, v in fixture.items() if k != "__meta"}


# ----- convenience loaders ------------------------------------------

def github_user() -> dict:
    """Template for GET /user."""
    return load_template("github", "get_user")


def github_list_repos() -> list:
    """Template for GET /user/repos."""
    return load_template("github", "list_repos")


def github_list_repo_labels() -> list:
    """Template for GET /repos/{o}/{r}/labels."""
    return load_template("github", "list_repo_labels")


def github_list_issues() -> list:
    """Template for GET /repos/{o}/{r}/issues."""
    return load_template("github", "list_issues")


def github_get_issue() -> dict:
    """Template for GET /repos/{o}/{r}/issues/{n}."""
    return load_template("github", "get_issue")


def github_list_issue_comments() -> list:
    """Template for GET /repos/{o}/{r}/issues/{n}/comments."""
    return load_template("github", "list_issue_comments")


def github_list_issue_labels() -> list:
    """Template for GET /repos/{o}/{r}/issues/{n}/labels."""
    return load_template("github", "list_issue_labels")


def github_create_comment() -> dict:
    """Template for POST /repos/{o}/{r}/issues/{n}/comments."""
    return load_template("github", "create_comment")


def github_create_issue() -> dict:
    """Template for POST /repos/{o}/{r}/issues."""
    return load_template("github", "create_issue")


def github_add_assignees() -> dict:
    """Template for POST /repos/{o}/{r}/issues/{n}/assignees."""
    return load_template("github", "add_assignees")


def github_create_pull() -> dict:
    """Template for POST /repos/{o}/{r}/pulls."""
    return load_template("github", "create_pull")


def github_list_pulls() -> list:
    """Template for GET /repos/{o}/{r}/pulls."""
    return load_template("github", "list_pulls")


def azure_current_user() -> dict:
    """Template for GET current user."""
    return load_template("azure", "get_current_user")


def azure_list_repositories() -> dict:
    """Template for GET repos."""
    return load_template("azure", "list_repositories")


def azure_wiql_query() -> dict:
    """Template for POST WIQL."""
    return load_template("azure", "wiql_query")


def azure_workitems_batch() -> dict:
    """Template for GET workitems batch response."""
    return load_template("azure", "workitems_batch")


def azure_get_workitem() -> dict:
    """Template for GET workitem."""
    return load_template("azure", "get_workitem")


def azure_list_workitem_comments() -> dict:
    """Template for GET workitem comments."""
    return load_template("azure", "list_workitem_comments")


def azure_create_workitem_comment() -> dict:
    """Template for POST workitem comment."""
    return load_template("azure", "create_workitem_comment")


def azure_update_workitem() -> Any:
    """Template for PATCH workitem."""
    return load_template("azure", "update_workitem")


def azure_create_workitem() -> Any:
    """Template for POST create workitem."""
    return load_template("azure", "create_workitem")


def azure_list_pullrequests() -> dict:
    """Template for GET pullrequests."""
    return load_template("azure", "list_pullrequests")


def azure_create_pullrequest() -> dict:
    """Template for POST pullrequest."""
    return load_template("azure", "create_pullrequest")
