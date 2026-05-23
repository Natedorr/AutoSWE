"""Fake parity audit — verify test fakes match real API shapes.

Batch 14 — Fake parity audit:
- Audit method-by-method against base.py IssueTracker and VCSProvider protocols
- Add missing methods to each fake
- Comment ID auto-increment uniqueness
- Scripted-failure mode for both fakes
- Protocol method existence assertions
"""
from __future__ import annotations

import inspect

from autoswe.providers.base import IssueTracker, VCSProvider
from tests.fakes.azure_fake import AzureFake
from tests.fakes.github_fake import GitHubFake

# ---------------------------------------------------------------------------
# Protocol method existence audit
# ---------------------------------------------------------------------------

class TestIssueTrackerProtocol:
    """Every IssueTracker protocol method must be callable on both adapters."""

    def test_github_tracker_has_all_protocol_methods(self):
        """GitHub IssueTracker implementation must have all protocol methods."""
        import autoswe.providers.github.tracker as gt_mod
        tracker = gt_mod.GitHubTracker({"owner": "o", "repo": "r", "token": "t"})
        for name, _ in inspect.getmembers(IssueTracker, predicate=inspect.isfunction):
            if name.startswith("_"):
                continue
            assert hasattr(tracker, name), f"GitHub tracker missing protocol method: {name}"
            assert callable(getattr(tracker, name)), f"GitHub tracker {name} not callable"

    def test_azure_tracker_has_all_protocol_methods(self):
        """Azure IssueTracker implementation must have all protocol methods."""
        import autoswe.providers.azure.tracker as at_mod
        tracker = at_mod.AzureTracker({"org": "o", "project": "p", "repo": "r", "pat": "t"})
        for name, _ in inspect.getmembers(IssueTracker, predicate=inspect.isfunction):
            if name.startswith("_"):
                continue
            assert hasattr(tracker, name), f"Azure tracker missing protocol method: {name}"
            assert callable(getattr(tracker, name)), f"Azure tracker {name} not callable"


class TestVcsProviderProtocol:
    """Every VCSProvider protocol method must be callable on both VCS implementations."""

    def test_github_vcs_has_all_protocol_methods(self):
        import autoswe.providers.github.vcs as gv_mod
        vcs = gv_mod.GitHubVCS({"owner": "o", "repo": "r", "token": "t"})
        for name, _ in inspect.getmembers(VCSProvider, predicate=inspect.isfunction):
            if name.startswith("_"):
                continue
            assert hasattr(vcs, name), f"GitHub VCS missing protocol method: {name}"
            assert callable(getattr(vcs, name)), f"GitHub VCS {name} not callable"

    def test_azure_vcs_has_all_protocol_methods(self):
        import autoswe.providers.azure.vcs as av_mod
        vcs = av_mod.AzureVCS({"org": "o", "project": "p", "repo": "r", "pat": "t"})
        for name, _ in inspect.getmembers(VCSProvider, predicate=inspect.isfunction):
            if name.startswith("_"):
                continue
            assert hasattr(vcs, name), f"Azure VCS missing protocol method: {name}"
            assert callable(getattr(vcs, name)), f"Azure VCS {name} not callable"


# ---------------------------------------------------------------------------
# Fake method coverage
# ---------------------------------------------------------------------------

class TestGitHubFakeCoverage:
    """GitHubFake must handle all API routes used by the adapter."""

    def test_handles_get_user(self, github_fake):
        resp = github_fake.handle_request("GET", "/user", "token")
        assert "login" in resp

    def test_handles_list_issues(self, github_fake):
        github_fake.load({
            "owner": "o", "repo": "r",
            "issue": {"number": 1, "title": "T", "body": "B", "state": "open",
                      "user": {"login": "owner", "id": 1, "type": "User"},
                      "labels": [], "assignees": [], "created_at": "", "updated_at": ""},
            "labels": [], "comments": [], "repo_labels": [],
        })
        resp = github_fake.handle_request("GET", "/repos/o/r/issues?state=open", "token")
        assert isinstance(resp, list)

    def test_handles_get_issue(self, github_fake):
        github_fake.load({
            "owner": "o", "repo": "r",
            "issue": {"number": 1, "title": "T", "body": "B", "state": "open",
                      "user": {"login": "owner", "id": 1, "type": "User"},
                      "labels": [], "assignees": [], "created_at": "", "updated_at": ""},
            "labels": [], "comments": [], "repo_labels": [],
        })
        resp = github_fake.handle_request("GET", "/repos/o/r/issues/1", "token")
        assert resp.get("number") == 1

    def test_handles_put_labels(self, github_fake):
        github_fake.load({
            "owner": "o", "repo": "r",
            "issue": {"number": 1, "title": "T", "body": "B", "state": "open",
                      "user": {"login": "owner", "id": 1, "type": "User"},
                      "labels": [], "assignees": [], "created_at": "", "updated_at": ""},
            "labels": [], "comments": [],
            "repo_labels": [{"name": "autoswe:done", "color": "ededed"}],
        })
        resp = github_fake.handle_request(
            "PUT", "/repos/o/r/issues/1/labels", "token",
            body={"labels": [{"name": "autoswe:done"}]},
        )
        assert resp == {}
        assert "autoswe:done" in github_fake.labels.get(1, [])

    def test_handles_post_comment_returns_id(self, github_fake):
        github_fake.load({
            "owner": "o", "repo": "r",
            "issue": {"number": 1, "title": "T", "body": "B", "state": "open",
                      "user": {"login": "owner", "id": 1, "type": "User"},
                      "labels": [], "assignees": [], "created_at": "", "updated_at": ""},
            "labels": [], "comments": [], "repo_labels": [],
        })
        resp = github_fake.handle_request(
            "POST", "/repos/o/r/issues/1/comments", "token",
            body={"body": "Test comment"},
        )
        assert "id" in resp
        assert resp["id"] is not None

    def test_handles_patch_comment(self, github_fake):
        github_fake.load({
            "owner": "o", "repo": "r",
            "issue": {"number": 1, "title": "T", "body": "B", "state": "open",
                      "user": {"login": "owner", "id": 1, "type": "User"},
                      "labels": [], "assignees": [], "created_at": "", "updated_at": ""},
            "labels": [],
            "comments": [{"id": 999, "body": "Old", "created_at": "",
                          "user": {"login": "bot", "id": 2, "type": "Bot"}}],
            "repo_labels": [],
        })
        resp = github_fake.handle_request(
            "PATCH", "/repos/o/r/issues/comments/999", "token",
            body={"body": "Updated text"},
        )
        assert resp.get("body") == "Updated text"

    def test_handles_post_assignees(self, github_fake):
        github_fake.load({
            "owner": "o", "repo": "r",
            "issue": {"number": 1, "title": "T", "body": "B", "state": "open",
                      "user": {"login": "owner", "id": 1, "type": "User"},
                      "labels": [], "assignees": [], "created_at": "", "updated_at": ""},
            "labels": [], "comments": [], "repo_labels": [],
        })
        resp = github_fake.handle_request(
            "POST", "/repos/o/r/issues/1/assignees", "token",
            body={"assignee": "testuser"},
        )
        assert "login" in resp

    def test_handles_create_pr(self, github_fake):
        github_fake.load({
            "owner": "o", "repo": "r",
            "issue": {"number": 1, "title": "T", "body": "B", "state": "open",
                      "user": {"login": "owner", "id": 1, "type": "User"},
                      "labels": [], "assignees": [], "created_at": "", "updated_at": ""},
            "labels": [], "comments": [], "repo_labels": [],
        })
        resp = github_fake.handle_request(
            "POST", "/repos/o/r/pulls", "token",
            body={"title": "PR", "head": "branch", "base": "main"},
        )
        assert "number" in resp

    def test_handles_authenticated_user(self, github_fake):
        resp = github_fake.handle_request("GET", "/user", "token")
        assert "login" in resp


class TestAzureFakeCoverage:
    """AzureFake must handle all API routes used by the adapter."""

    def test_handles_get_current_user(self, azure_fake):
        resp = azure_fake.handle_request(
            "GET", "https://dev.azure.com/org/proj/_users/me", "pat",
        )
        assert "uniqueName" in resp

    def test_handles_wiql(self, azure_fake):
        azure_fake.load({
            "org": "org", "project": "proj", "repo": "repo",
            "work_item": {"id": 1, "fields": {"System.Id": 1, "System.State": "Active",
                                               "System.Title": "T", "System.Description": "B"}},
            "tags": [], "comments": [],
        })
        resp = azure_fake.handle_request(
            "POST", "https://dev.azure.com/org/proj/_apis/wit/wiql", "pat",
            body={"query": {"cql": "State != Closed"}},
        )
        assert "workItems" in resp

    def test_handles_get_workitem(self, azure_fake):
        azure_fake.load({
            "org": "org", "project": "proj", "repo": "repo",
            "work_item": {"id": 1, "fields": {"System.Id": 1, "System.State": "Active",
                                               "System.Title": "T", "System.Description": "B"}},
            "tags": [], "comments": [],
        })
        resp = azure_fake.handle_request(
            "GET", "https://dev.azure.com/org/proj/_apis/wit/workitems/1", "pat",
        )
        assert resp.get("id") == 1

    def test_handles_patch_workitem(self, azure_fake):
        azure_fake.load({
            "org": "org", "project": "proj", "repo": "repo",
            "work_item": {"id": 1, "fields": {"System.Id": 1, "System.State": "Active",
                                               "System.Title": "T", "System.Tags": ""}},
            "tags": [], "comments": [],
        })
        resp = azure_fake.handle_request(
            "PATCH", "https://dev.azure.com/org/proj/_apis/wit/workitems/1", "pat",
            body=[{"op": "add", "path": "/fields/System.Tags", "value": "autoswe:done"}],
        )
        assert "autoswe:done" in resp.get("fields", {}).get("System.Tags", "")

    def test_handles_post_comment_returns_id(self, azure_fake):
        azure_fake.load({
            "org": "org", "project": "proj", "repo": "repo",
            "work_item": {"id": 1, "fields": {"System.Id": 1, "System.State": "Active",
                                               "System.Title": "T", "System.Description": "B"}},
            "tags": [], "comments": [],
        })
        resp = azure_fake.handle_request(
            "POST", "https://dev.azure.com/org/proj/_apis/wit/workitems/1/comments?api-version=7.1", "pat",
            body={"text": "Test comment"},
        )
        assert "id" in resp
        assert resp["id"] is not None

    def test_handles_patch_comment(self, azure_fake):
        azure_fake.load({
            "org": "org", "project": "proj", "repo": "repo",
            "work_item": {"id": 1, "fields": {"System.Id": 1, "System.State": "Active",
                                               "System.Title": "T", "System.Description": "B"}},
            "tags": [],
            "comments": [{"id": 999, "text": "Old", "createdDate": "2026-01-01T00:00:00Z",
                          "createdBy": {"uniqueName": "bot@example.com", "id": "2"}}],
        })
        resp = azure_fake.handle_request(
            "PATCH", "https://dev.azure.com/org/proj/_apis/wit/workitems/1/comments/999?api-version=7.1", "pat",
            body={"text": "Updated"},
        )
        assert resp.get("text") == "Updated"

    def test_handles_create_pr(self, azure_fake):
        azure_fake.load({
            "org": "org", "project": "proj", "repo": "repo",
            "work_item": {"id": 1, "fields": {"System.Id": 1, "System.State": "Active",
                                               "System.Title": "T", "System.Description": "B"}},
            "tags": [], "comments": [],
        })
        resp = azure_fake.handle_request(
            "POST", "https://dev.azure.com/org/proj/_apis/git/repositories/repo/pullrequests?api-version=7.1", "pat",
            body={"title": "PR", "sourceRefName": "branch", "targetRefName": "main"},
        )
        assert "pullRequestId" in resp

    def test_handles_authenticated_user(self, azure_fake):
        resp = azure_fake.handle_request(
            "GET", "https://dev.azure.com/org/_users/me", "pat",
        )
        assert "uniqueName" in resp

    def test_handles_list_repos(self, azure_fake):
        azure_fake.load({
            "org": "org", "project": "proj", "repo": "repo",
            "work_item": {"id": 1, "fields": {"System.Id": 1, "System.State": "Active",
                                               "System.Title": "T", "System.Description": "B"}},
            "tags": [], "comments": [],
        })
        resp = azure_fake.handle_request(
            "GET", "https://dev.azure.com/org/proj/_apis/git/repositories", "pat",
        )
        assert "value" in resp


# ---------------------------------------------------------------------------
# Comment ID uniqueness
# ---------------------------------------------------------------------------

class TestCommentIdUniqueness:
    """Comment ID auto-increment must be unique across calls."""

    def test_github_comment_ids_unique(self, github_fake):
        """GitHubFake must return unique IDs for each posted comment."""
        github_fake.load({
            "owner": "o", "repo": "r",
            "issue": {"number": 1, "title": "T", "body": "B", "state": "open",
                      "user": {"login": "owner", "id": 1, "type": "User"},
                      "labels": [], "assignees": [], "created_at": "", "updated_at": ""},
            "labels": [], "comments": [], "repo_labels": [],
        })
        ids = set()
        for i in range(5):
            resp = github_fake.handle_request(
                "POST", "/repos/o/r/issues/1/comments", "token",
                body={"body": f"Comment {i}"},
            )
            assert resp["id"] not in ids, f"Duplicate comment ID: {resp['id']}"
            ids.add(resp["id"])
        assert len(ids) == 5

    def test_azure_comment_ids_unique(self, azure_fake):
        """AzureFake must return unique IDs for each posted comment."""
        azure_fake.load({
            "org": "org", "project": "proj", "repo": "repo",
            "work_item": {"id": 1, "fields": {"System.Id": 1, "System.State": "Active",
                                               "System.Title": "T", "System.Description": "B"}},
            "tags": [], "comments": [],
        })
        ids = set()
        for i in range(5):
            resp = azure_fake.handle_request(
                "POST", "https://dev.azure.com/org/proj/_apis/wit/workitems/1/comments?api-version=7.1", "pat",
                body={"text": f"Comment {i}"},
            )
            assert resp["id"] not in ids, f"Duplicate comment ID: {resp['id']}"
            ids.add(resp["id"])
        assert len(ids) == 5

    def test_github_pr_numbers_unique(self, github_fake):
        """GitHubFake must return unique PR numbers for each created PR."""
        github_fake.load({
            "owner": "o", "repo": "r",
            "issue": {"number": 1, "title": "T", "body": "B", "state": "open",
                      "user": {"login": "owner", "id": 1, "type": "User"},
                      "labels": [], "assignees": [], "created_at": "", "updated_at": ""},
            "labels": [], "comments": [], "repo_labels": [],
        })
        numbers = set()
        for i in range(3):
            resp = github_fake.handle_request(
                "POST", "/repos/o/r/pulls", "token",
                body={"title": f"PR {i}", "head": f"branch-{i}", "base": "main"},
            )
            assert resp["number"] not in numbers
            numbers.add(resp["number"])

    def test_azure_pr_numbers_unique(self, azure_fake):
        """AzureFake must return unique PR IDs for each created PR."""
        azure_fake.load({
            "org": "org", "project": "proj", "repo": "repo",
            "work_item": {"id": 1, "fields": {"System.Id": 1, "System.State": "Active",
                                               "System.Title": "T", "System.Description": "B"}},
            "tags": [], "comments": [],
        })
        numbers = set()
        for i in range(3):
            resp = azure_fake.handle_request(
                "POST", "https://dev.azure.com/org/proj/_apis/git/repositories/repo/pullrequests?api-version=7.1", "pat",
                body={"title": f"PR {i}", "sourceRefName": f"branch-{i}", "targetRefName": "main"},
            )
            assert resp["pullRequestId"] not in numbers
            numbers.add(resp["pullRequestId"])


# ---------------------------------------------------------------------------
# Provider parity: GitHub vs Azure behavior
# ---------------------------------------------------------------------------

class TestProviderParity:
    """GitHub and Azure fakes must implement the same logical operations."""

    def test_both_set_status(self):
        """Both providers must support set_status (labels/tags)."""
        gh = GitHubFake()
        gh.load({
            "owner": "o", "repo": "r",
            "issue": {"number": 1, "title": "T", "body": "B", "state": "open",
                      "user": {"login": "owner", "id": 1, "type": "User"},
                      "labels": [], "assignees": [], "created_at": "", "updated_at": ""},
            "labels": [], "comments": [],
            "repo_labels": [{"name": "autoswe:done", "color": "ededed"}],
        })
        gh.handle_request("PUT", "/repos/o/r/issues/1/labels", "token",
                          body={"labels": [{"name": "autoswe:done"}]})
        assert "autoswe:done" in gh.labels.get(1, [])

        az = AzureFake()
        az.load({
            "org": "org", "project": "proj", "repo": "repo",
            "work_item": {"id": 1, "fields": {"System.Id": 1, "System.State": "Active",
                                               "System.Title": "T", "System.Tags": ""}},
            "tags": [], "comments": [],
        })
        az.handle_request("PATCH",
            "https://dev.azure.com/org/proj/_apis/wit/workitems/1", "pat",
            body=[{"op": "add", "path": "/fields/System.Tags", "value": "autoswe:done"}])
        tags = az.work_items[1]["fields"]["System.Tags"]
        assert "autoswe:done" in tags

    def test_both_post_comment(self):
        """Both providers must support post_comment with ID return."""
        gh = GitHubFake()
        gh.load({
            "owner": "o", "repo": "r",
            "issue": {"number": 1, "title": "T", "body": "B", "state": "open",
                      "user": {"login": "owner", "id": 1, "type": "User"},
                      "labels": [], "assignees": [], "created_at": "", "updated_at": ""},
            "labels": [], "comments": [], "repo_labels": [],
        })
        gh_resp = gh.handle_request("POST", "/repos/o/r/issues/1/comments", "token",
                                    body={"body": "Test"})
        assert "id" in gh_resp and gh_resp["id"] is not None

        az = AzureFake()
        az.load({
            "org": "org", "project": "proj", "repo": "repo",
            "work_item": {"id": 1, "fields": {"System.Id": 1, "System.State": "Active",
                                               "System.Title": "T", "System.Description": "B"}},
            "tags": [], "comments": [],
        })
        az_resp = az.handle_request("POST",
            "https://dev.azure.com/org/proj/_apis/wit/workitems/1/comments?api-version=7.1",
            "pat", body={"text": "Test"})
        assert "id" in az_resp and az_resp["id"] is not None

    def test_both_create_pr(self):
        """Both providers must support creating PRs."""
        gh = GitHubFake()
        gh.load({
            "owner": "o", "repo": "r",
            "issue": {"number": 1, "title": "T", "body": "B", "state": "open",
                      "user": {"login": "owner", "id": 1, "type": "User"},
                      "labels": [], "assignees": [], "created_at": "", "updated_at": ""},
            "labels": [], "comments": [], "repo_labels": [],
        })
        gh_resp = gh.handle_request("POST", "/repos/o/r/pulls", "token",
                                    body={"title": "PR", "head": "b", "base": "main"})
        assert "number" in gh_resp

        az = AzureFake()
        az.load({
            "org": "org", "project": "proj", "repo": "repo",
            "work_item": {"id": 1, "fields": {"System.Id": 1, "System.State": "Active",
                                               "System.Title": "T", "System.Description": "B"}},
            "tags": [], "comments": [],
        })
        az_resp = az.handle_request("POST",
            "https://dev.azure.com/org/proj/_apis/git/repositories/repo/pullrequests?api-version=7.1",
            "pat", body={"title": "PR", "sourceRefName": "b", "targetRefName": "main"})
        assert "pullRequestId" in az_resp

    def test_both_update_comment(self):
        """Both providers must support updating existing comments."""
        gh = GitHubFake()
        gh.load({
            "owner": "o", "repo": "r",
            "issue": {"number": 1, "title": "T", "body": "B", "state": "open",
                      "user": {"login": "owner", "id": 1, "type": "User"},
                      "labels": [], "assignees": [], "created_at": "", "updated_at": ""},
            "labels": [],
            "comments": [{"id": 999, "body": "Old", "created_at": "",
                          "user": {"login": "bot", "id": 2, "type": "Bot"}}],
            "repo_labels": [],
        })
        gh_resp = gh.handle_request("PATCH", "/repos/o/r/issues/comments/999", "token",
                                    body={"body": "Updated"})
        assert gh_resp.get("body") == "Updated"

        az = AzureFake()
        az.load({
            "org": "org", "project": "proj", "repo": "repo",
            "work_item": {"id": 1, "fields": {"System.Id": 1, "System.State": "Active",
                                               "System.Title": "T", "System.Description": "B"}},
            "tags": [],
            "comments": [{"id": 999, "text": "Old", "createdDate": "",
                          "createdBy": {"uniqueName": "bot@example.com", "id": "2"}}],
        })
        az_resp = az.handle_request("PATCH",
            "https://dev.azure.com/org/proj/_apis/wit/workitems/1/comments/999?api-version=7.1",
            "pat", body={"text": "Updated"})
        assert az_resp.get("text") == "Updated"
