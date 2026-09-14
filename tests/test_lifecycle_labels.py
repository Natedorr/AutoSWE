"""Tests for label management helpers."""

from autoswe.tracking.assignment import _auto_assign_issue
from autoswe.tracking.labels import (
    AUTOSWE_LABELS,
    CI_WATCH_STATUSES,
    SHIPPING_BLOCKING_STATUSES,
    VALID_STATUSES,
    _ensure_repo_labels,
    _kind_from_command,
    _set_autoswe_status,
    _validate_status,
    completed_status_for,
)
from tests.conftest import load_fixture

# ---------------------------------------------------------------------------
# closed-issue status (gh_closed path, issue #173 F-11)
# ---------------------------------------------------------------------------

def test_closed_path_maps_command_to_correct_completed_status():
    """Closing an issue after /sync or /pr must not mislabel it as 'fixed'.

    The gh_closed path converts the last dispatched *command* to an action
    *kind* via _kind_from_command before calling completed_status_for.
    """
    # /sync → kind sync_branch → synced (NOT "fixed")
    assert completed_status_for(_kind_from_command("/sync")) == "synced"
    # /pr → kind ship_pr → shipped (NOT "fixed")
    assert completed_status_for(_kind_from_command("/pr")) == "shipped"
    # /plan → kind plan → planned
    assert completed_status_for(_kind_from_command("/plan")) == "planned"
    # /review → kind review → reviewed
    assert completed_status_for(_kind_from_command("/review")) == "reviewed"
    # /fix → kind fix → fixed
    assert completed_status_for(_kind_from_command("/fix")) == "fixed"
    # default (no last_dispatched_command) → /fix → fixed
    assert completed_status_for(_kind_from_command(None)) == "fixed"


def test_closed_path_stripped_command_used_to_be_wrong():
    """The old (buggy) mapping via lstrip('/') fell through to 'fixed'.

    Documents why _kind_from_command is required: "sync" and "pr" are not keys
    in _KIND_TO_COMPLETED, so completed_status_for returns the "fixed" default.
    """
    assert completed_status_for("sync") == "fixed"   # wrong, pre-fix behaviour
    assert completed_status_for("pr") == "fixed"     # wrong, pre-fix behaviour
    # The correct converter maps them properly:
    assert completed_status_for(_kind_from_command("/sync")) != "fixed"
    assert completed_status_for(_kind_from_command("/pr")) != "fixed"


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


# ---------------------------------------------------------------------------
# ci_failed status (issue #245 plan §2.3, P3)
# ---------------------------------------------------------------------------

def test_ci_failed_is_a_valid_status():
    """ci_failed must be registered so _validate_status accepts it (bare and prefixed)."""
    assert "ci_failed" in VALID_STATUSES
    _validate_status("ci_failed")
    _validate_status("autoswe:ci_failed")


def test_ci_failed_has_a_label():
    """autoswe:ci_failed must exist so _ensure_repo_labels / _set_autoswe_status work."""
    assert "autoswe:ci_failed" in AUTOSWE_LABELS
    assert AUTOSWE_LABELS["autoswe:ci_failed"]["color"]
    assert AUTOSWE_LABELS["autoswe:ci_failed"]["description"]


def test_ci_failed_blocks_shipping_like_test_failed():
    """ci_failed must gate /pr exactly like test_failed (issue #245 plan §2.3)."""
    assert "ci_failed" in SHIPPING_BLOCKING_STATUSES
    assert "test_failed" in SHIPPING_BLOCKING_STATUSES


def test_ci_failed_is_watched_by_the_ci_poll():
    """ci_failed stays in CI_WATCH_STATUSES so a stuck ci_failed task keeps
    being polled for recovery (green build clears it back)."""
    assert "ci_failed" in CI_WATCH_STATUSES


def test_set_autoswe_status_accepts_ci_failed(
    fake_token, mock_gh_request, gh_route_table
):
    gh_route_table[("GET", "/repos/o/r/issues/1/labels")] = [
        {"name": "autoswe:fixed"},
    ]
    put_calls = []

    def capture_put(method, path, token, body):
        put_calls.append(body)
        return {}

    gh_route_table[("PUT", "/repos/o/r/issues/1/labels")] = capture_put

    _set_autoswe_status("o", "r", 1, "autoswe:ci_failed", fake_token)

    new_labels = put_calls[0]["labels"]
    assert new_labels == ["autoswe:ci_failed"]
