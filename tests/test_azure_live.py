"""Live Azure DevOps API tests — use PAT to validate fixture format.

Tests that hit the real Azure DevOps API use the PAT from env vars.
Marked with @pytest.mark.live so they are skipped by default in CI.

Run with:
    AZURE_DEVOPS_PAT=*** AZURE_DEVOPS_ORG=... AZURE_DEVOPS_PROJECT=... \
    AZURE_DEVOPS_REPO=... pytest -q -m live

Or run all (offline + live):
    pytest -q
"""

import json
import os
import time
from pathlib import Path
from urllib.parse import urlparse

import pytest

ADO_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "azure"


def _ado_live_config():
    """Build repo_cfg from env vars, falling back to autoswe.env via load_config."""
    # Try env vars first
    pat = os.environ.get("AZURE_DEVOPS_PAT", "")
    org = os.environ.get("AZURE_DEVOPS_ORG", "")
    project = os.environ.get("AZURE_DEVOPS_PROJECT", "")
    repo = os.environ.get("AZURE_DEVOPS_REPO", "")

    # Fall back to autoswe.env values
    from autoswe.core.config import load_config
    cfg = load_config()

    if not pat:
        pat = cfg.get("AZURE_DEVOPS_PAT", "")
    if not org:
        org = cfg.get("AZURE_DEVOPS_ORG", "natedorr")
    if not project:
        project = cfg.get("AZURE_DEVOPS_PROJECT", "testProject")
    if not repo:
        repo = cfg.get("AZURE_DEVOPS_REPO", "testProject")

    return {
        "provider": "azure",
        "org": org,
        "project": project,
        "repo": repo,
        "pat": pat,
    }


@pytest.fixture
def ado_live_cfg():
    """Return Azure repo_cfg from env or autoswe.env, or skip if not set."""
    cfg = _ado_live_config()
    if not cfg["pat"]:
        pytest.skip("AZURE_DEVOPS_PAT not set (env vars or autoswe.env)")
    return cfg


# ---------------------------------------------------------------------------
# Offline: Validate Azure fixture structure (no network)
# ---------------------------------------------------------------------------

def test_fixture_workitem_has_required_fields():
    """Work item fixture should have id and fields."""
    wi = json.loads((ADO_FIXTURE_DIR / "workitem_open_with_plan.json").read_text())
    assert "id" in wi
    assert "fields" in wi
    fields = wi["fields"]
    assert "System.Title" in fields


def test_fixture_closed_workitem_is_closed():
    """Closed work item fixture should have State=Closed."""
    wi = json.loads((ADO_FIXTURE_DIR / "workitem_closed.json").read_text())
    assert wi["fields"]["System.State"] == "Closed"


def test_fixture_workitem_with_tags_has_autoswe_tag():
    """Work item with tags fixture should have autoswe: tag."""
    wi = json.loads((ADO_FIXTURE_DIR / "workitem_with_tags.json").read_text())
    tags = wi["fields"]["System.Tags"]
    assert "autoswe:" in tags


def test_fixture_comments_have_required_fields():
    """Comment fixtures should have text and createdDate."""
    raw = json.loads(
        (ADO_FIXTURE_DIR / "comments_workitem_done.json").read_text()
    )
    # Fixture wraps comments in a "comments" key (ADO API shape)
    comments = raw.get("comments", raw if isinstance(raw, list) else [raw])
    for comment in comments:
        assert "text" in comment
        assert "createdDate" in comment


def test_fixture_pr_has_required_fields():
    """PR fixture should have pullRequestId and status."""
    raw = json.loads((ADO_FIXTURE_DIR / "pullrequest_active.json").read_text())
    # Fixture wraps PRs in a "value" key (ADO paged API shape)
    pr = raw["value"][0] if "value" in raw else raw
    required = {"pullRequestId", "status", "sourceRefName", "targetRefName"}
    assert required.issubset(pr.keys()), f"Missing: {required - pr.keys()}"


def test_fixture_profile_has_email():
    """Profile fixture should have emailAddress."""
    profile = json.loads((ADO_FIXTURE_DIR / "profile_me.json").read_text())
    assert "emailAddress" in profile


# ---------------------------------------------------------------------------
# Live: Hit real Azure DevOps API (skipped without env vars)
# ---------------------------------------------------------------------------

@pytest.mark.live
class TestLiveAzureAPI:
    """Hit real Azure DevOps API endpoints and validate response shape."""

    def test_authenticate_user(self, ado_live_cfg):
        from autoswe.providers.factory import get_tracker
        tracker = get_tracker(ado_live_cfg)
        email = tracker.authenticated_user(ado_live_cfg)
        assert email, "Should return authenticated user email"
        assert "@" in email, f"Email should contain @: {email}"

    def test_list_open_issues(self, ado_live_cfg):
        from autoswe.providers.factory import get_tracker
        tracker = get_tracker(ado_live_cfg)
        issues = tracker.list_open_issues(ado_live_cfg)
        assert isinstance(issues, list)
        if issues:
            wi = issues[0]
            assert wi.number > 0
            assert wi.title

    def test_fetch_issue(self, ado_live_cfg):
        from autoswe.providers.factory import get_tracker
        tracker = get_tracker(ado_live_cfg)
        # Use the first work item from the list
        issues = tracker.list_open_issues(ado_live_cfg)
        if issues:
            wi = tracker.fetch_issue(ado_live_cfg, issues[0].number)
            assert wi.number == issues[0].number
            assert wi.labels is not None

    def test_fetch_comments(self, ado_live_cfg):
        from autoswe.providers.factory import get_tracker
        tracker = get_tracker(ado_live_cfg)
        issues = tracker.list_open_issues(ado_live_cfg)
        if issues:
            comments = tracker.fetch_comments(ado_live_cfg, issues[0].number)
            assert isinstance(comments, list)
            if comments:
                c = comments[0]
                assert c.body is not None
                assert c.created_at is not None


@pytest.mark.live
class TestLiveAzureVCS:
    """Hit real Azure DevOps VCS endpoints."""

    def test_clone_url(self, ado_live_cfg):
        from autoswe.providers.factory import get_vcs
        vcs = get_vcs(ado_live_cfg)
        url = vcs.clone_url(ado_live_cfg)
        assert urlparse(url).hostname.endswith("dev.azure.com")
        assert f"/{ado_live_cfg['org']}/" in urlparse(url).path
        assert f"/{ado_live_cfg['project']}/" in urlparse(url).path

    def test_branch_name(self, ado_live_cfg):
        from autoswe.providers.factory import get_vcs
        vcs = get_vcs(ado_live_cfg)
        branch = vcs.branch_name(42)
        assert branch == "autoswe/issue-42"

    def test_find_existing_pr(self, ado_live_cfg):
        from autoswe.providers.factory import get_vcs
        vcs = get_vcs(ado_live_cfg)
        result = vcs.find_existing_pr(ado_live_cfg, "autoswe/issue-1")
        assert result is None or (
            hasattr(result, "url") and urlparse(result.url).hostname.endswith("dev.azure.com")
        )

    def test_get_status(self, ado_live_cfg):
        from autoswe.providers.base import NormalizedIssue
        from autoswe.providers.factory import get_tracker
        tracker = get_tracker(ado_live_cfg)
        # Status on untagged issue should be None
        issue = NormalizedIssue(
            number=1, title="test", body="",
            owner=ado_live_cfg["org"], repo=ado_live_cfg["project"],
            labels=[],
        )
        status = tracker.get_status(issue)
        assert status is None


@pytest.mark.live
class TestAzureWriteOps:
    """Write operations: create, comment, set_status, assign, open_pr."""

    def test_tracker_create_issue(self, ado_live_cfg):
        from autoswe.providers.factory import get_tracker
        tracker = get_tracker(ado_live_cfg)
        wid = tracker.create_issue(ado_live_cfg, "Live test issue", "Test body from pytest")
        assert isinstance(wid, int) and wid > 0

    def test_tracker_post_comment(self, ado_live_cfg):
        from autoswe.providers.factory import get_tracker
        tracker = get_tracker(ado_live_cfg)
        # Post a comment on issue #1 (should always exist)
        tracker.post_comment(ado_live_cfg, 1, "Live test comment from pytest")

    def test_tracker_set_status_transitions(self, ado_live_cfg):
        """Set status through multiple autoswe: transitions."""
        from autoswe.providers.factory import get_tracker
        tracker = get_tracker(ado_live_cfg)
        for status in ("pending", "dispatched", "done"):
            tracker.set_status(ado_live_cfg, 1, status)

    def test_tracker_assign_to_user(self, ado_live_cfg):
        from autoswe.providers.factory import get_tracker
        tracker = get_tracker(ado_live_cfg)
        # Assign to authenticated user (None resolves automatically)
        tracker.assign_to_user(ado_live_cfg, 1, None)

    def test_vcs_open_pull_request_roundtrip(self, ado_live_cfg):
        """Open a PR, verify it exists, then close it."""
        from autoswe.providers.azure.api import _ado_api_version, ado_post
        from autoswe.providers.factory import get_vcs
        vcs = get_vcs(ado_live_cfg)
        branch = f"autoswe/live-test-{int(time.time())}"
        pr = vcs.open_pull_request(
            ado_live_cfg, branch, "main", "Live test PR", "Test body from pytest"
        )
        assert pr.number is not None
        assert urlparse(pr.url).hostname.endswith("dev.azure.com")
        found = vcs.find_existing_pr(ado_live_cfg, branch)
        assert found is not None and found.number == pr.number
        # Close the PR
        close_path = _ado_api_version(
            f"https://dev.azure.com/{ado_live_cfg['org']}/{ado_live_cfg['project']}"
            f"/_apis/git/repositories/{ado_live_cfg['repo']}/pullrequests/{pr.number}"
        )
        ado_post(close_path, ado_live_cfg["pat"],
                 body={"status": "completed", "completionOptions": {"deleteSourceBranch": False}})

    def test_factory_sync_workflow(self, ado_live_cfg):
        """Full factory-based sync workflow."""
        from autoswe.providers.factory import get_tracker
        tracker = get_tracker(ado_live_cfg)
        issues = tracker.list_open_issues(ado_live_cfg)
        assert len(issues) > 0
        issue = tracker.fetch_issue(ado_live_cfg, issues[0].number)
        assert issue.title
        comments = tracker.fetch_comments(ado_live_cfg, issues[0].number)
        assert isinstance(comments, list)
        tracker.set_status(ado_live_cfg, 1, "pending")
        tracker.post_comment(ado_live_cfg, 1, "Live sync test comment")


@pytest.mark.live
class TestAzureSlug:
    """Slug helper roundtrip for Azure provider."""

    def test_slug_roundtrip(self):
        from autoswe.core.slug import make_slug
        slug = make_slug("azure", ("org", "repo"), 42)
        assert slug == "ado:org_repo_42"

    def test_slug_prefix_is_ado(self):
        from autoswe.core.slug import make_slug
        slug = make_slug("azure", ("org", "repo"), 1)
        assert slug.startswith("ado:")


@pytest.mark.live
class TestAzureEdgeCases:
    """Edge cases and error handling."""

    def test_bad_project_raises(self, ado_live_cfg):
        from autoswe.providers.azure.api import _ado_api_version, ado_get
        with pytest.raises(RuntimeError, match="HTTP"):
            ado_get(
                _ado_api_version(f"https://dev.azure.com/{ado_live_cfg['org']}/_apis/projects/INVALID"),
                ado_live_cfg["pat"],
            )

    def test_get_status_untagged_issue(self, ado_live_cfg):
        from autoswe.providers.base import NormalizedIssue
        from autoswe.providers.factory import get_tracker
        tracker = get_tracker(ado_live_cfg)
        issue = NormalizedIssue(
            number=1, title="test", body="",
            owner=ado_live_cfg["org"], repo=ado_live_cfg["project"],
            labels=[],
        )
        status = tracker.get_status(issue)
        assert status is None


# TestAzureFixtureConsistency class folded into tests/test_api_contract.py::TestAzureLiveShapeDrift
