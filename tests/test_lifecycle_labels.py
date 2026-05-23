"""Tests for label management helpers."""

from autoswe.tracking.assignment import _auto_assign_issue
from autoswe.tracking.labels import (
    AUTOSWE_LABELS,
    _ensure_repo_labels,
    _set_autoswe_status,
)
from tests.conftest import load_fixture

# ---------------------------------------------------------------------------
# _set_autoswe_status
# ---------------------------------------------------------------------------

def test_set_autoswe_status_preserves_non_autoswe_labels(
    fake_token, mock_gh_request, gh_route_table
):
    """Non-autoswe labels must survive a status change."""
    gh_route_table[("GET", "/repos/natedorr/autoswe/issues/42/labels")] = (
        load_fixture("labels_list_issue_pending.json")
    )
    put_calls = []

    def capture_put(method, path, token, body):
        put_calls.append(body)
        return {}

    gh_route_table[("PUT", "/repos/natedorr/autoswe/issues/42/labels")] = capture_put

    _set_autoswe_status("natedorr", "autoswe", 42, "autoswe:fixed", fake_token)

    assert len(put_calls) == 1
    new_labels = put_calls[0]["labels"]
    assert "autoswe:fixed" in new_labels
    assert "bug" in new_labels
    assert "autoswe:pending" not in new_labels


def test_set_autoswe_status_replaces_old_autoswe_label(
    fake_token, mock_gh_request, gh_route_table
):
    gh_route_table[("GET", "/repos/o/r/issues/1/labels")] = [
        {"name": "autoswe:fixing"},
        {"name": "enhancement"},
    ]
    put_calls = []

    def capture_put(method, path, token, body):
        put_calls.append(body)
        return {}

    gh_route_table[("PUT", "/repos/o/r/issues/1/labels")] = capture_put

    _set_autoswe_status("o", "r", 1, "autoswe:fixed", fake_token)

    new_labels = put_calls[0]["labels"]
    autoswe_labels_in_result = [lb for lb in new_labels if lb.startswith("autoswe:")]
    assert autoswe_labels_in_result == ["autoswe:fixed"]


# ---------------------------------------------------------------------------
# _ensure_repo_labels
# ---------------------------------------------------------------------------

def test_ensure_repo_labels_creates_missing(
    fake_token, mock_gh_request, gh_route_table
):
    """Should POST labels that are missing from the repo."""
    gh_route_table[("GET", "/repos/o/r/labels")] = [
        {"name": "autoswe:pending"},
        {"name": "autoswe:done"},
    ]
    created = []

    def capture_post(method, path, token, body):
        created.append(body["name"])
        return {}

    gh_route_table[("POST", "/repos/o/r/labels")] = capture_post

    _ensure_repo_labels("o", "r", fake_token)

    expected_missing = set(AUTOSWE_LABELS.keys()) - {"autoswe:pending", "autoswe:done"}
    assert set(created) == expected_missing


def test_ensure_repo_labels_idempotent_when_all_exist(
    fake_token, mock_gh_request, gh_route_table
):
    gh_route_table[("GET", "/repos/o/r/labels")] = [
        {"name": name} for name in AUTOSWE_LABELS
    ]
    post_calls = []

    def capture_post(method, path, token, body):
        post_calls.append(body)
        return {}

    gh_route_table[("POST", "/repos/o/r/labels")] = capture_post

    _ensure_repo_labels("o", "r", fake_token)

    assert post_calls == [], "No labels should be created when all exist"


# ---------------------------------------------------------------------------
# _auto_assign_issue
# ---------------------------------------------------------------------------

def test_auto_assign_issue_assigns_when_not_assigned(
    fake_token, mock_gh_request, gh_route_table
):
    gh_route_table[("GET", "/repos/o/r/issues/5")] = {"assignees": []}
    assign_calls = []

    def capture_post(method, path, token, body):
        assign_calls.append(body)
        return {}

    gh_route_table[("POST", "/repos/o/r/issues/5/assignees")] = capture_post

    _auto_assign_issue("o", "r", 5, fake_token, username="testuser")

    assert len(assign_calls) == 1
    assert assign_calls[0]["assignees"] == ["testuser"]


def test_auto_assign_issue_skips_when_already_assigned(
    fake_token, mock_gh_request, gh_route_table
):
    gh_route_table[("GET", "/repos/o/r/issues/5")] = {
        "assignees": [{"login": "testuser"}]
    }
    assign_calls = []

    def capture_post(method, path, token, body):
        assign_calls.append(body)
        return {}

    gh_route_table[("POST", "/repos/o/r/issues/5/assignees")] = capture_post

    _auto_assign_issue("o", "r", 5, fake_token, username="testuser")

    assert assign_calls == [], "Should skip if user already assigned"
