"""Live GitHub API tests — use PAT to validate fixture format.

Tests that hit the real GitHub API use the PAT from autoswe.env.
Marked with @pytest.mark.live so they are skipped by default in CI.

Run with:
    pytest -q -m live
    # or run all (offline + live):
    pytest -q
"""

import json
import os
from pathlib import Path

import pytest

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "github"


@pytest.fixture
def live_token():
    """Return the GITHUB_TOKEN from env or autoswe.env, or skip if not set."""
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        try:
            from autoswe.core.config import load_config
            cfg = load_config()
            token = cfg.get("GITHUB_TOKEN", "")
        except Exception:
            pass
    if not token:
        pytest.skip("GITHUB_TOKEN not set")
    return token


# ---------------------------------------------------------------------------
# Offline: Validate fixture structure (no network)
# ---------------------------------------------------------------------------

def test_fixture_issue_has_required_fields():
    """Issue fixture should have all fields the code expects."""
    issue = json.loads((FIXTURE_DIR / "issue_open_with_plan.json").read_text())
    required = {"number", "state", "title", "body", "labels", "assignees",
                 "created_at", "updated_at", "html_url"}
    assert required.issubset(issue.keys()), f"Missing: {required - issue.keys()}"


def test_fixture_closed_issue_has_closed_at():
    """Closed issue fixture should have closed_at set."""
    issue = json.loads((FIXTURE_DIR / "issue_closed.json").read_text())
    assert issue["state"] == "closed"
    assert issue["closed_at"] is not None


def test_fixture_labels_are_dicts():
    """Labels in fixtures should be dicts with name field."""
    issue = json.loads((FIXTURE_DIR / "issue_open_with_plan.json").read_text())
    for label in issue["labels"]:
        assert isinstance(label, dict)
        assert "name" in label


def test_fixture_comments_have_required_fields():
    """Comment fixtures should have body and created_at."""
    comments = json.loads((FIXTURE_DIR / "comments_done_state.json").read_text())
    for comment in comments:
        assert "body" in comment
        assert "created_at" in comment


def test_fixture_failed_issue_has_failed_label():
    """Failed issue fixture should have autoswe:failed label."""
    issue = json.loads((FIXTURE_DIR / "issue_failed_7.json").read_text())
    label_names = {lb["name"] for lb in issue.get("labels", [])}
    assert "autoswe:failed" in label_names, f"Expected autoswe:failed label, got {label_names}"


def test_fixture_failed_comments_have_max_attempts():
    """Failed comments fixture should have a max-attempts or failure comment."""
    comments = json.loads((FIXTURE_DIR / "comments_failed_with_retry.json").read_text())
    bodies = [c.get("body", "") for c in comments]
    has_failure = any("Max attempts" in b or "Failed:" in b for b in bodies)
    assert has_failure, "Should have at least one failure comment"


def test_fixture_pr_has_required_fields():
    """PR fixture should have required fields."""
    pr = json.loads((FIXTURE_DIR / "pr_closed.json").read_text())
    required = {"number", "state", "title", "html_url"}
    assert required.issubset(pr.keys()), f"Missing: {required - pr.keys()}"


# ---------------------------------------------------------------------------
# Live: Hit real GitHub API (skipped without GITHUB_TOKEN)
# ---------------------------------------------------------------------------

@pytest.mark.live
class TestLiveGitHubAPI:
    """Hit real GitHub API endpoints and validate response shape."""

    def test_gh_get_user(self, live_token):
        user = self._gh_get("/user", live_token)
        assert "login" in user
        assert "id" in user
        assert "type" in user

    def test_gh_get_issue(self, live_token):
        issue = self._gh_get("/repos/natedorr/autoswe/issues/1", live_token)
        required = {"number", "state", "title", "body", "labels", "created_at",
                     "updated_at", "html_url", "author_association"}
        assert required.issubset(set(issue.keys()))
        for label in issue.get("labels", []):
            assert "name" in label
            assert "color" in label

    def test_gh_get_comments(self, live_token):
        from autoswe.tracking.api import _fetch_comments
        comments = _fetch_comments("natedorr", "autoswe", 1, live_token)
        assert isinstance(comments, list)
        if comments:
            for c in comments:
                assert "body" in c
                assert "created_at" in c
                assert "id" in c

    def test_gh_get_labels(self, live_token):
        labels = self._gh_get("/repos/natedorr/autoswe/issues/1/labels", live_token)
        assert isinstance(labels, list)
        for label in labels:
            assert "name" in label
            assert "color" in label

    def test_gh_paginate(self, live_token):
        from autoswe.tracking.api import gh_get_all
        issues = gh_get_all("/repos/natedorr/autoswe/issues?state=open", live_token)
        assert isinstance(issues, list)

    def test_gh_get_closed_issues(self, live_token):
        from autoswe.tracking.api import gh_get_all
        issues = gh_get_all(
            "/repos/natedorr/autoswe/issues?state=closed&per_page=10",
            live_token
        )
        real_closed = [i for i in issues if not i.get("pull_request")]
        assert len(real_closed) > 0, "Should have at least one closed issue"
        for issue in real_closed:
            assert issue["state"] == "closed"
            assert issue["closed_at"] is not None

    @staticmethod
    def _gh_get(path, token):
        from autoswe.tracking.api import gh_get
        return gh_get(path, token)


@pytest.mark.live
class TestLiveLifecycle:
    """Test lifecycle helpers with live GitHub data."""

    def test_parse_slash_from_real_issue(self, live_token):
        from autoswe.commands.parser import parse_slash_command
        from autoswe.tracking.api import gh_get
        issue = gh_get("/repos/natedorr/autoswe/issues/3", live_token)
        result = parse_slash_command(issue.get("body", ""))
        assert result is None or isinstance(result, tuple)

    def test_get_autoswe_status_from_real_labels(self, live_token):
        from autoswe.tracking.api import gh_get
        from autoswe.tracking.labels import _get_autoswe_status
        labels = gh_get("/repos/natedorr/autoswe/issues/1/labels", live_token)
        status = _get_autoswe_status(labels)
        assert status in (None, "done", "pending", "failed", "dispatched",
                           "waiting", "plan_ready", "skipped")


# TestFixtureConsistency class folded into tests/test_api_contract.py::TestGitHubLiveShapeDrift
