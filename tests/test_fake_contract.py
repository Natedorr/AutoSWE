"""Fake contract tests — ensure fake responses match canonical fixture shapes.

Drives every route of each fake (after loading initial state) and asserts that
the response contains at least all keys from the corresponding Layer-0 fixture
template at every nesting level.  Catches divergences when a template gains a
key but the fake doesn't propagate it.
"""
from __future__ import annotations

from typing import Any

import pytest

from tests.fakes import templates as T

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _keys_superset(actual: Any, expected: Any, path: str = "root") -> list[str]:
    """Return list of missing keys in *actual* compared to *expected*.

    For dicts: checks that every key in *expected* exists in *actual*.
    For lists: checks the first element if both are non-empty.
    For scalars: just checks matching types.
    """
    missing = []
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            missing.append(f"{path}: expected dict, got {type(actual).__name__}")
            return missing
        for key, exp_val in expected.items():
            if key not in actual:
                missing.append(f"{path}.{key}")
            else:
                missing.extend(_keys_superset(actual[key], exp_val, f"{path}.{key}"))
    elif isinstance(expected, list):
        if not isinstance(actual, list):
            missing.append(f"{path}: expected list, got {type(actual).__name__}")
        elif len(expected) > 0 and len(actual) > 0:
            missing.extend(_keys_superset(actual[0], expected[0], f"{path}[0]"))
    return missing


def _assert_shape(actual: Any, expected: Any, label: str) -> None:
    """Assert *actual* contains all keys from *expected*."""
    missing = _keys_superset(actual, expected, path=label)
    if missing:
        pytest.fail(f"{label} missing keys: {missing}")


# ---------------------------------------------------------------------------
# GitHub fake contract tests
# ---------------------------------------------------------------------------

_SAMPLE_STATE_GH = {
    "owner": "owner",
    "repo": "repo",
    "issue": {
        "id": 999999,
        "number": 42,
        "title": "Test issue",
        "body": "Body text",
        "state": "open",
        "labels": [],
        "assignees": [],
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
        "closed_at": None,
        "author_association": "OWNER",
        "comments": 0,
        "user": {"login": "owner", "id": 1, "type": "User"},
    },
    "labels": ["autoswe:pending"],
    "comments": [
        {
            "id": 1,
            "body": "Welcome comment",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
            "user": {"login": "owner", "id": 1, "type": "User"},
            "author_association": "OWNER",
        }
    ],
    "repo_labels": [
        {"id": 1, "name": "autoswe:pending", "color": "0075ca", "description": "Ready"},
        {"id": 2, "name": "autoswe:done", "color": "ededed", "description": "Done"},
    ],
}


class TestGitHubFakeContract:
    """GitHub fake responses must contain template keys."""

    def test_get_user(self, github_fake):
        github_fake.load(_SAMPLE_STATE_GH)
        resp = github_fake.handle_request("GET", "/user", "token")
        template = T.github_user()
        _assert_shape(resp, template, "get_user")

    def test_list_repos(self, github_fake):
        github_fake.load(_SAMPLE_STATE_GH)
        resp = github_fake.handle_request("GET", "/user/repos?type=owner", "token")
        template = T.github_list_repos()
        _assert_shape(resp, template, "list_repos")

    def test_list_repo_labels(self, github_fake):
        github_fake.load(_SAMPLE_STATE_GH)
        resp = github_fake.handle_request("GET", "/repos/owner/repo/labels", "token")
        # Template is a list of label dicts; fake returns from repo_labels state
        # Check that each item has all template label keys
        template = T.github_list_repo_labels()
        if template and resp:
            _assert_shape(resp[0], template[0], "list_repo_labels[0]")

    def test_create_repo_label(self, github_fake):
        github_fake.load(_SAMPLE_STATE_GH)
        resp = github_fake.handle_request(
            "POST", "/repos/owner/repo/labels", "token",
            body={"name": "new-label", "color": "abc123"},
        )
        # POST /labels returns the created label dict
        expected_keys = {"name", "color"}
        assert expected_keys.issubset(set(resp.keys())), f"Missing keys: {expected_keys - set(resp.keys())}"

    def test_list_issues(self, github_fake):
        github_fake.load(_SAMPLE_STATE_GH)
        resp = github_fake.handle_request(
            "GET", "/repos/owner/repo/issues?state=open", "token",
        )
        template = T.github_list_issues()
        _assert_shape(resp, template, "list_issues")

    def test_get_issue(self, github_fake):
        github_fake.load(_SAMPLE_STATE_GH)
        resp = github_fake.handle_request(
            "GET", "/repos/owner/repo/issues/42", "token",
        )
        template = T.github_get_issue()
        _assert_shape(resp, template, "get_issue")

    def test_get_issue_comments(self, github_fake):
        github_fake.load(_SAMPLE_STATE_GH)
        resp = github_fake.handle_request(
            "GET", "/repos/owner/repo/issues/42/comments", "token",
        )
        template = T.github_list_issue_comments()
        _assert_shape(resp, template, "get_issue_comments")

    def test_get_issue_labels(self, github_fake):
        github_fake.load(_SAMPLE_STATE_GH)
        resp = github_fake.handle_request(
            "GET", "/repos/owner/repo/issues/42/labels", "token",
        )
        template = T.github_list_issue_labels()
        if template and resp:
            _assert_shape(resp[0], template[0], "get_issue_labels[0]")

    def test_replace_labels(self, github_fake):
        github_fake.load(_SAMPLE_STATE_GH)
        resp = github_fake.handle_request(
            "PUT", "/repos/owner/repo/issues/42/labels", "token",
            body={"labels": [{"name": "autoswe:done"}]},
        )
        # PUT /labels returns empty dict
        assert resp == {}, f"Expected empty dict, got {resp}"

    def test_create_comment(self, github_fake):
        github_fake.load(_SAMPLE_STATE_GH)
        resp = github_fake.handle_request(
            "POST", "/repos/owner/repo/issues/42/comments", "token",
            body={"body": "Test comment"},
        )
        # handle_request returns the comment dict with an ID
        assert resp is not None
        assert "id" in resp
        assert resp["body"] == "Test comment"

    def test_add_assignees(self, github_fake):
        github_fake.load(_SAMPLE_STATE_GH)
        resp = github_fake.handle_request(
            "POST", "/repos/owner/repo/issues/42/assignees", "token",
            body={"assignees": ["testuser"]},
        )
        template = T.github_add_assignees()
        _assert_shape(resp, template, "add_assignees")

    def test_create_pull(self, github_fake):
        github_fake.load(_SAMPLE_STATE_GH)
        resp = github_fake.handle_request(
            "POST", "/repos/owner/repo/pulls", "token",
            body={"title": "Test PR", "head": "autoswe/issue-42", "base": "main"},
        )
        template = T.github_create_pull()
        _assert_shape(resp, template, "create_pull")

    def test_list_pulls(self, github_fake):
        """List pulls is empty before a PR is created — create one first."""
        github_fake.load(_SAMPLE_STATE_GH)
        github_fake.handle_request(
            "POST", "/repos/owner/repo/pulls", "token",
            body={"title": "Test PR", "head": "autoswe/issue-42", "base": "main"},
        )
        resp = github_fake.handle_request(
            "GET", "/repos/owner/repo/pulls?state=open", "token",
        )
        assert isinstance(resp, list) and len(resp) > 0
        template = T.github_create_pull()
        _assert_shape(resp[0], template, "list_pulls[0]")


# ---------------------------------------------------------------------------
# Azure fake contract tests
# ---------------------------------------------------------------------------

_SAMPLE_STATE_AZ = {
    "org": "testorg",
    "project": "testproject",
    "repo": "testrepo",
    "work_item": {
        "id": 42,
        "rev": 1,
        "fields": {
            "System.Id": 42,
            "System.AreaPath": "testproject",
            "System.Title": "Test work item",
            "System.State": "Active",
            "System.CreatedDate": "2026-01-01T00:00:00Z",
            "System.ChangedDate": "2026-01-01T00:00:00Z",
            "System.IterationId": "1",
        },
    },
    "tags": ["autoswe:pending"],
    "comments": [
        {
            "id": 1,
            "text": "Welcome comment",
            "createdDate": "2026-01-01T00:00:00Z",
            "createdBy": {
                "displayName": "Test User",
                "id": "test-id",
                "uniqueName": "test@example.com",
            },
        }
    ],
}


class TestAzureFakeContract:
    """Azure fake responses must contain template keys."""

    def test_get_current_user(self, azure_fake):
        azure_fake.load(_SAMPLE_STATE_AZ)
        resp = azure_fake.handle_request(
            "GET", "https://dev.azure.com/testorg/_users/me", "pat",
        )
        template = T.azure_current_user()
        _assert_shape(resp, template, "get_current_user")

    def test_list_repositories(self, azure_fake):
        azure_fake.load(_SAMPLE_STATE_AZ)
        resp = azure_fake.handle_request(
            "GET", "https://dev.azure.com/testorg/testproject/_apis/git/repositories", "pat",
        )
        template = T.azure_list_repositories()
        _assert_shape(resp, template, "list_repositories")

    def test_wiql_query(self, azure_fake):
        azure_fake.load(_SAMPLE_STATE_AZ)
        resp = azure_fake.handle_request(
            "POST", "https://dev.azure.com/testorg/testproject/_apis/wit/wiql", "pat",
            body={"query": {"cql": "State != Closed"}},
        )
        # WIQL returns {"workItems": [...]} — fake only serves that key
        assert "workItems" in resp
        assert isinstance(resp["workItems"], list)

    def test_get_workitem(self, azure_fake):
        azure_fake.load(_SAMPLE_STATE_AZ)
        resp = azure_fake.handle_request(
            "GET", "https://dev.azure.com/testorg/testproject/_apis/wit/workitems/42?fields=System.*", "pat",
        )
        template = T.azure_get_workitem()
        _assert_shape(resp, template, "get_workitem")

    def test_get_workitem_comments(self, azure_fake):
        azure_fake.load(_SAMPLE_STATE_AZ)
        resp = azure_fake.handle_request(
            "GET", "https://dev.azure.com/testorg/testproject/_apis/wit/workitems/42/comments?api-version=7.1-preview.4", "pat",
        )
        # Production reads: count, comments[].id, comments[].text, comments[].createdDate
        assert "count" in resp and "comments" in resp
        if resp["comments"]:
            c = resp["comments"][0]
            assert all(k in c for k in ("id", "text", "createdDate"))

    def test_create_workitem_comment(self, azure_fake):
        azure_fake.load(_SAMPLE_STATE_AZ)
        resp = azure_fake.handle_request(
            "POST", "https://dev.azure.com/testorg/testproject/_apis/wit/workitems/42/comments?api-version=7.1-preview.4", "pat",
            body={"text": "Test comment"},
        )
        # Production reads: id, text, createdDate
        assert all(k in resp for k in ("id", "text", "createdDate"))
        assert resp["text"] == "Test comment"

    def test_patch_workitem(self, azure_fake):
        azure_fake.load(_SAMPLE_STATE_AZ)
        resp = azure_fake.handle_request(
            "PATCH", "https://dev.azure.com/testorg/testproject/_apis/wit/workitems/42?api-version=7.1-preview.4", "pat",
            body=[{"op": "add", "path": "/fields/System.Tags", "value": "autoswe:dispatched"}],
        )
        # PATCH returns the workitem
        template = T.azure_get_workitem()
        _assert_shape(resp, template, "patch_workitem")

    def test_workitems_batch(self, azure_fake):
        azure_fake.load(_SAMPLE_STATE_AZ)
        resp = azure_fake.handle_request(
            "GET", "https://dev.azure.com/testorg/testproject/_apis/wit/workitems?ids=42&$expand=all&api-version=7.1", "pat",
        )
        template = T.azure_workitems_batch()
        _assert_shape(resp, template, "workitems_batch")

    def test_create_pullrequest(self, azure_fake):
        azure_fake.load(_SAMPLE_STATE_AZ)
        resp = azure_fake.handle_request(
            "POST", "https://dev.azure.com/testorg/testproject/_apis/git/repositories/testrepo/pullrequests?api-version=7.1", "pat",
            body={"title": "Test PR", "sourceRefName": "autoswe/issue-42", "targetRefName": "main"},
        )
        template = T.azure_create_pullrequest()
        _assert_shape(resp, template, "create_pullrequest")

    def test_list_pullrequests(self, azure_fake):
        """Create a PR first, then list."""
        azure_fake.load(_SAMPLE_STATE_AZ)
        azure_fake.handle_request(
            "POST", "https://dev.azure.com/testorg/testproject/_apis/git/repositories/testrepo/pullrequests?api-version=7.1", "pat",
            body={"title": "Test PR", "sourceRefName": "autoswe/issue-42", "targetRefName": "main"},
        )
        resp = azure_fake.handle_request(
            "GET", "https://dev.azure.com/testorg/testproject/_apis/git/repositories/testrepo/pullrequests?api-version=7.1", "pat",
        )
        template = T.azure_list_pullrequests()
        _assert_shape(resp, template, "list_pullrequests")

    def test_put_labels_bridge(self, azure_fake):
        """GitHub-style PUT /labels should update work item tags."""
        azure_fake.load(_SAMPLE_STATE_AZ)
        resp = azure_fake.handle_request(
            "PUT", "/repos/testorg/testproject/issues/42/labels", "pat",
            body={"labels": [{"name": "autoswe:done"}]},
        )
        assert resp == {}
        # Verify tag was updated
        wi = azure_fake.handle_request(
            "GET", "https://dev.azure.com/testorg/testproject/_apis/wit/workitems/42", "pat",
        )
        assert "autoswe:done" in wi.get("fields", {}).get("System.Tags", "")

    def test_workitem_1_fallback(self, azure_fake):
        """Work item #1 fallback for authenticated_user should return a valid shape."""
        azure_fake.load(_SAMPLE_STATE_AZ)
        resp = azure_fake.handle_request(
            "GET", "https://dev.azure.com/testorg/testproject/_apis/wit/workitems/1?fields=System.CreatedBy", "pat",
        )
        assert "id" in resp
        assert "fields" in resp
        assert "System.CreatedBy" in resp["fields"]


# ---------------------------------------------------------------------------
# patch/unpatch signature consistency
# ---------------------------------------------------------------------------

class TestPatchUnpatchConsistency:
    """Both fakes should expose consistent patch/unpatch signatures."""

    def test_github_fake_patch_returns_tuple(self, github_fake):
        module, original = github_fake.patch()
        assert hasattr(module, "_gh_request")
        github_fake.unpatch(module, original)

    def test_azure_fake_patch_returns_tuple(self, azure_fake):
        module, original = azure_fake.patch()
        assert hasattr(module, "_ado_request")
        azure_fake.unpatch(module, original)

    def test_github_fake_restores_original(self, github_fake):
        import autoswe.tracking.api as api_mod
        original = api_mod._gh_request
        module, orig = github_fake.patch()
        assert api_mod._gh_request is not original
        github_fake.unpatch(module, orig)
        assert api_mod._gh_request is original

    def test_azure_fake_restores_original(self, azure_fake):
        import autoswe.providers.azure.api as ado_mod
        original = ado_mod._ado_request
        module, orig = azure_fake.patch()
        assert ado_mod._ado_request is not original
        azure_fake.unpatch(module, orig)
        assert ado_mod._ado_request is original
