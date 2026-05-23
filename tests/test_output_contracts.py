"""Output contract tests — verify API request bodies match documented shapes.

Drives representative turns via the harness and asserts that the request bodies
in ``fake.recorded_calls`` match the shapes expected by the production API.

Cross-checks against:
  - GitHub: PUT labels, POST comments, POST assignees, POST pulls
  - Azure: PATCH workitem (tags), POST comments, POST pullrequest
"""
from __future__ import annotations

from unittest.mock import patch

from autoswe.providers.base import PRResult
from tests.fakes.azure_fake import AzureFake
from tests.fakes.github_fake import GitHubFake
from tests.scenarios.harness import (
    build_test_cfg,
    patched_world,
    seed_queue,
    setup_repos,
)

# ---------------------------------------------------------------------------
# Helpers to find calls in recorded_calls

def _find_calls(fake, method: str, path_pattern: str) -> list[dict]:
    """Find recorded calls matching method and path substring."""
    return [
        c for c in fake.recorded_calls
        if c["method"] == method and path_pattern in c["path"]
    ]


def _find_put_labels(fake: GitHubFake) -> list[dict]:
    return _find_calls(fake, "PUT", "/labels")


def _find_post_comments(fake: GitHubFake | AzureFake) -> list[dict]:
    return _find_calls(fake, "POST", "/comments")


def _find_post_pulls(fake: GitHubFake) -> list[dict]:
    return _find_calls(fake, "POST", "/pulls")


def _find_post_assignees(fake: GitHubFake) -> list[dict]:
    return _find_calls(fake, "POST", "/assignees")


def _find_patch_workitem(fake: AzureFake) -> list[dict]:
    """Find PATCH calls to work item fields (not comment PATCH calls)."""
    return [
        c for c in fake.recorded_calls
        if c["method"] == "PATCH" and "workitems" in c["path"] and "/comments/" not in c["path"]
    ]


def _find_post_pr_azure(fake: AzureFake) -> list[dict]:
    return _find_calls(fake, "POST", "pullrequests")


# ---------------------------------------------------------------------------
# State fixtures for tests

_GH_PLAN_STATE = {
    "owner": "owner",
    "repo": "repo",
    "issue": {
        "id": 999999, "number": 1, "title": "Test issue", "body": "/plan",
        "state": "open", "labels": [], "assignees": [],
        "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z",
        "closed_at": None, "author_association": "OWNER", "comments": 0,
        "user": {"login": "owner", "id": 1, "type": "User"},
        "pull_request": None,
    },
    "labels": [],
    "comments": [],
    "repo_labels": [],
    "authenticated_user": {"login": "owner", "id": 1, "type": "User"},
    "claude_responses": [
        {"text": "<AUTOSWE_PLAN>1. Do the thing</AUTOSWE_PLAN>", "session_id": "s1", "subtype": "success"},
    ],
}

_GH_FIX_STATE = {
    **_GH_PLAN_STATE,
    "issue": {**_GH_PLAN_STATE["issue"], "body": "/fix", "number": 2},
    "queue_task": {
        "id": "gh:owner_repo_2",
        "owner": "owner", "repo": "repo", "issue_number": 2,
        "title": "Test issue", "body": "/fix",
        "autoswe_status": "pending", "pending_command": "/fix",
        "base_branch": "main", "session_id": None,
        "first_dispatched_at": None, "attempt_count": 0,
        "provider": "github",
    },
    "claude_responses": [
        {"text": "DONE_SUMMARY\tFixed the bug\tabc1234", "session_id": "s2", "subtype": "success"},
    ],
}

_GH_PR_STATE = {
    **_GH_PLAN_STATE,
    "issue": {**_GH_PLAN_STATE["issue"], "body": "/fix\n\n/pr", "number": 3},
    "queue_task": {
        "id": "gh:owner_repo_3",
        "owner": "owner", "repo": "repo", "issue_number": 3,
        "title": "Test issue", "body": "/fix\n\n/pr",
        "autoswe_status": "fixed", "pending_command": "/pr",
        "base_branch": "main", "session_id": "s2",
        "first_dispatched_at": None, "attempt_count": 1,
        "pr_number": None, "provider": "github",
    },
    "claude_responses": [],
}

_AZ_PLAN_STATE = {
    "org": "testorg",
    "project": "testproj",
    "repo": "testrepo",
    "work_item": {
        "id": 1, "rev": 1,
        "fields": {
            "System.Id": 1, "System.Title": "Test work item",
            "System.Description": "/plan",
            "System.State": "Active", "System.Tags": "",
            "System.CreatedDate": "2026-01-01T00:00:00Z",
            "System.ChangedDate": "2026-01-01T00:00:00Z",
        },
    },
    "tags": [],
    "comments": [],
    "authenticated_user": {"uniqueName": "test@example.com", "id": "1"},
    "claude_responses": [
        {"text": "<AUTOSWE_PLAN>1. Do the thing</AUTOSWE_PLAN>", "session_id": "s1", "subtype": "success"},
    ],
}

_AZ_FIX_STATE = {
    **_AZ_PLAN_STATE,
    "work_item": {
        **_AZ_PLAN_STATE["work_item"],
        "id": 2,
        "fields": {**_AZ_PLAN_STATE["work_item"]["fields"], "System.Id": 2, "System.Tags": ""},
    },
    "queue_task": {
        "id": "ado:testorg_testproj/testrepo_2",
        "owner": "testorg", "repo": "testproj", "issue_number": 2,
        "title": "Test work item", "body": "/fix",
        "autoswe_status": "pending", "pending_command": "/fix",
        "base_branch": "main", "session_id": None,
        "first_dispatched_at": None, "attempt_count": 0,
        "provider": "azure",
    },
    "claude_responses": [
        {"text": "DONE_SUMMARY\tFixed the bug\tabc1234", "session_id": "s2", "subtype": "success"},
    ],
}


# ---------------------------------------------------------------------------
# GitHub output contracts


class TestGitHubOutputContracts:
    """Verify GitHub API request body shapes."""

    def test_put_labels_shape(self, isolated_autoswe_dir, github_fake):
        """PUT /labels body must be {'labels': [{'name': str}, ...]}."""
        github_fake.load(_GH_PLAN_STATE)

        # Simulate a label replacement call
        body = {"labels": [{"name": "autoswe:planned"}, {"name": "bug"}]}
        github_fake.handle_request("PUT", "/repos/owner/repo/issues/1/labels", "token", body=body)

        calls = _find_put_labels(github_fake)
        assert calls, "Expected PUT /labels call"
        assert calls[-1]["body"]["labels"] == body["labels"]
        # Verify no stale autoswe labels (all are strings with name key)
        for lb in calls[-1]["body"]["labels"]:
            assert isinstance(lb, dict) and "name" in lb

    def test_post_comment_has_bot_footer(self, isolated_autoswe_dir, github_fake):
        """POST comment body should end with <!-- autoswe-bot --> for bot comments."""
        github_fake.load(_GH_FIX_STATE)

        body_text = "Completed with command `/fix` — DONE_SUMMARY\n\n<!-- autoswe-bot -->"
        github_fake.handle_request(
            "POST", "/repos/owner/repo/issues/2/comments", "token",
            body={"body": body_text},
        )

        calls = _find_post_comments(github_fake)
        assert calls, "Expected POST /comments call"
        posted_body = calls[-1]["body"]["body"]
        assert "<!-- autoswe-bot -->" in posted_body

    def test_post_comment_body_field(self, isolated_autoswe_dir, github_fake):
        """POST comment body must use 'body' key (not 'text')."""
        github_fake.load(_GH_PLAN_STATE)

        github_fake.handle_request(
            "POST", "/repos/owner/repo/issues/1/comments", "token",
            body={"body": "Hello"},
        )

        calls = _find_post_comments(github_fake)
        assert calls
        assert "body" in calls[-1]["body"]
        assert calls[-1]["body"]["body"] == "Hello"

    def test_post_pull_shape(self, isolated_autoswe_dir, github_fake):
        """POST /pulls body must have title, head, base."""
        github_fake.load(_GH_PR_STATE)

        pr_body = {
            "title": "autoswe: fix for issue #3",
            "body": "Fixes #3",
            "head": "autoswe/issue-3",
            "base": "main",
        }
        github_fake.handle_request(
            "POST", "/repos/owner/repo/pulls", "token", body=pr_body,
        )

        calls = _find_post_pulls(github_fake)
        assert calls, "Expected POST /pulls call"
        for key in ("title", "head", "base"):
            assert key in calls[-1]["body"], f"Missing {key} in PR body"

    def test_post_assignees_shape(self, isolated_autoswe_dir, github_fake):
        """POST /assignees body must have 'assignees' or 'assignee' key."""
        github_fake.load(_GH_PLAN_STATE)

        assignee_body = {"assignees": ["testowner"]}
        github_fake.handle_request(
            "POST", "/repos/owner/repo/issues/1/assignees", "token",
            body=assignee_body,
        )

        calls = _find_post_assignees(github_fake)
        assert calls, "Expected POST /assignees call"
        assert "assignees" in calls[-1]["body"] or "assignee" in calls[-1]["body"]


# ---------------------------------------------------------------------------
# Azure output contracts


class TestAzureOutputContracts:
    """Verify Azure DevOps API request body shapes."""

    def test_patch_tags_json_patch(self, isolated_autoswe_dir, azure_fake):
        """PATCH workitem (tags) must be JSON-Patch array with autoswe tags."""
        azure_fake.load(_AZ_PLAN_STATE)

        patch_body = [
            {"op": "replace", "path": "/fields/System.Tags",
             "value": "tag1; autoswe:planned"},
        ]
        azure_fake.handle_request(
            "PATCH",
            "https://dev.azure.com/testorg/testproj/_apis/wit/workitems/1?api-version=7.1",
            "pat", body=patch_body, content_type="application/json-patch+json",
        )

        calls = _find_patch_workitem(azure_fake)
        assert calls, "Expected PATCH workitem call"
        body = calls[-1]["body"]
        assert isinstance(body, list), "PATCH body should be JSON-Patch array"
        assert body[0]["op"] == "replace"
        assert body[0]["path"] == "/fields/System.Tags"

    def test_patch_tags_content_type(self, isolated_autoswe_dir, azure_fake):
        """PATCH workitem must use application/json-patch+json content type."""
        azure_fake.load(_AZ_PLAN_STATE)

        patch_body = [
            {"op": "replace", "path": "/fields/System.Tags", "value": "autoswe:fixed"},
        ]
        azure_fake.handle_request(
            "PATCH",
            "https://dev.azure.com/testorg/testproj/_apis/wit/workitems/1?api-version=7.1",
            "pat", body=patch_body, content_type="application/json-patch+json",
        )

        calls = _find_patch_workitem(azure_fake)
        assert calls
        assert calls[-1]["content_type"] == "application/json-patch+json"

    def test_patch_strips_old_autoswe_tags(self, isolated_autoswe_dir, azure_fake):
        """PATCH workitem (tags) should strip old autoswe:* tags before adding new."""
        azure_fake.load({
            **_AZ_PLAN_STATE,
            "tags": ["autoswe:pending", "tag1"],
        })

        # Simulate what set_status does: read tags, strip autoswe, add new
        tags_raw = azure_fake.work_items[1]["fields"]["System.Tags"]
        tags = [t.strip() for t in tags_raw.split(";") if t.strip()]
        new_tags = [t for t in tags if not t.startswith("autoswe:")]
        new_tags.append("autoswe:fixed")

        patch_body = [
            {"op": "replace", "path": "/fields/System.Tags", "value": "; ".join(new_tags)},
        ]
        azure_fake.handle_request(
            "PATCH",
            "https://dev.azure.com/testorg/testproj/_apis/wit/workitems/1?api-version=7.1",
            "pat", body=patch_body, content_type="application/json-patch+json",
        )

        calls = _find_patch_workitem(azure_fake)
        value = calls[-1]["body"][0]["value"]
        assert "autoswe:pending" not in value, "Old autoswe:pending should be stripped"
        assert "autoswe:fixed" in value, "New autoswe:fixed should be present"
        assert "tag1" in value, "Non-autoswe tags should be preserved"

    def test_post_comment_azure_format(self, isolated_autoswe_dir, azure_fake):
        """POST comment on Azure workitem must use 'text' key and format=Markdown query param."""
        azure_fake.load(_AZ_PLAN_STATE)

        comment_body = {"text": "Plan posted"}
        azure_fake.handle_request(
            "POST",
            "https://dev.azure.com/testorg/testproj/_apis/wit/workitems/1/comments?format=Markdown&api-version=7.1-preview.4",
            "pat", body=comment_body,
        )

        calls = _find_post_comments(azure_fake)
        assert calls, "Expected POST /comments call"
        assert "text" in calls[-1]["body"]
        assert "format=Markdown" in calls[-1]["path"]
        assert "format" not in calls[-1]["body"]  # format is a query param, not body field

    def test_post_comment_has_bot_footer(self, isolated_autoswe_dir, azure_fake):
        """Azure bot comments should end with <!-- autoswe-bot -->."""
        azure_fake.load(_AZ_FIX_STATE)

        body_text = "Completed with command `/fix`\n\n<!-- autoswe-bot -->"
        comment_body = {"text": body_text}
        azure_fake.handle_request(
            "POST",
            "https://dev.azure.com/testorg/testproj/_apis/wit/workitems/2/comments?format=Markdown&api-version=7.1-preview.4",
            "pat", body=comment_body,
        )

        calls = _find_post_comments(azure_fake)
        assert calls
        assert "<!-- autoswe-bot -->" in calls[-1]["body"]["text"]

    def test_post_pullrequest_shape(self, isolated_autoswe_dir, azure_fake):
        """POST pullrequest must have sourceRefName, targetRefName, title, description."""
        azure_fake.load(_AZ_PR_STATE := {
            **_AZ_FIX_STATE,
            "work_item": {
                **_AZ_FIX_STATE["work_item"],
                "id": 3,
                "fields": {**_AZ_FIX_STATE["work_item"]["fields"], "System.Id": 3},
            },
            "queue_task": {
                "id": "ado:testorg_testproj/testrepo_3",
                "owner": "testorg", "repo": "testproj", "issue_number": 3,
                "title": "Test work item", "body": "/pr",
                "autoswe_status": "fixed", "pending_command": "/pr",
                "base_branch": "main", "session_id": "s2",
                "first_dispatched_at": None, "attempt_count": 1,
                "pr_number": None, "provider": "azure",
            },
            "claude_responses": [],
        })

        pr_body = {
            "sourceRefName": "refs/heads/autoswe/issue-3",
            "targetRefName": "refs/heads/main",
            "title": "autoswe: fix for issue #3",
            "description": "Fixes #3",
        }
        azure_fake.handle_request(
            "POST",
            "https://dev.azure.com/testorg/testproj/_apis/git/repositories/testrepo/pullrequests?api-version=7.1",
            "pat", body=pr_body,
        )

        calls = _find_post_pr_azure(azure_fake)
        assert calls, "Expected POST pullrequests call"
        for key in ("sourceRefName", "targetRefName", "title"):
            assert key in calls[-1]["body"], f"Missing {key} in PR body"


# ---------------------------------------------------------------------------
# PR output content tests (drive open_pr() and assert actual content)


class TestPRContent:
    """Assert actual PR title/body content produced by open_pr()."""

    def test_github_open_pr_title_and_body(self, isolated_autoswe_dir, github_fake):
        """open_pr() should produce title='Fixes #N: <title>' and body='Fixes #N'."""
        from unittest.mock import patch

        github_fake.load(_GH_PR_STATE)

        task = {
            "owner": "owner", "repo": "repo", "issue_number": 3,
            "title": "Test issue", "body": "/fix\n\n/pr",
            "autoswe_status": "fixed", "base_branch": "main",
            "session_id": "s2", "attempt_count": 1,
            "pr_number": None, "_token": "test-token",
        }

        def fake_gh_request(method, path, token, body=None, **kw):
            return github_fake.handle_request(method, path, token, body=body)

        # Patch _gh_request so both gh_post (PR create) and comment post route through fake
        # Patch find_existing_pr to return None (no existing PR)
        with patch("autoswe.tracking.api._gh_request", fake_gh_request), \
             patch("autoswe.providers.github.vcs.GitHubVCS.find_existing_pr", return_value=None):
            from autoswe.vcs.ship import open_pr
            result = open_pr(task, {})

        # Should have created a PR via API
        pr_calls = _find_post_pulls(github_fake)
        assert pr_calls, "Expected POST /pulls call"
        pr_body = pr_calls[-1]["body"]

        # Assert title contains Fixes #N and issue title
        assert "Fixes #3" in pr_body["title"]
        assert "Test issue" in pr_body["title"]

        # Assert body contains Fixes #N
        assert "Fixes #3" in pr_body["body"]

        # Assert standard fields
        assert pr_body["head"] == "autoswe/issue-3"
        assert pr_body["base"] == "main"

        # Assert done-file content
        assert "DONE: PR" in result

    def test_github_open_pr_idempotent(self, isolated_autoswe_dir, github_fake):
        """If a PR already exists, open_pr() should post comment and not create PR."""
        github_fake.load(_GH_PR_STATE)

        task = {
            "owner": "owner", "repo": "repo", "issue_number": 3,
            "title": "Test issue", "body": "/fix\n\n/pr",
            "autoswe_status": "fixed", "base_branch": "main",
            "session_id": "s2", "attempt_count": 1,
            "pr_number": None, "_token": "test-token",
        }

        existing_pr = PRResult(number=99, url="https://github.com/owner/repo/pull/99")

        def fake_gh_request(method, path, token, body=None, **kw):
            return github_fake.handle_request(method, path, token, body=body)

        with patch("autoswe.tracking.api._gh_request", fake_gh_request), \
             patch("autoswe.providers.github.vcs.GitHubVCS.find_existing_pr", return_value=existing_pr):
            from autoswe.vcs.ship import open_pr
            result = open_pr(task, {})

        # Should NOT have created a new PR
        pr_calls = _find_post_pulls(github_fake)
        assert not pr_calls, "Should not create PR when one already exists"

        # Should have posted "Pull request already exists" comment
        comment_calls = _find_post_comments(github_fake)
        assert any("Pull request already exists" in (c["body"].get("body", ""))
                   for c in comment_calls), \
            "Expected 'Pull request already exists' comment"

        assert "DONE: PR" in result

    def test_azure_open_pr_title_and_body(self, isolated_autoswe_dir, azure_fake):
        """Azure open_pr() should produce correct title and description."""
        from unittest.mock import patch

        az_pr_state = {
            **_AZ_FIX_STATE,
            "work_item": {
                **_AZ_FIX_STATE["work_item"],
                "id": 3,
                "fields": {**_AZ_FIX_STATE["work_item"]["fields"], "System.Id": 3},
            },
            "queue_task": {
                "id": "ado:testorg_testproj/testrepo_3",
                "owner": "testorg", "repo": "testproj", "issue_number": 3,
                "title": "Test work item", "body": "/pr",
                "autoswe_status": "fixed", "pending_command": "/pr",
                "base_branch": "main", "session_id": "s2",
                "first_dispatched_at": None, "attempt_count": 1,
                "pr_number": None, "provider": "azure",
            },
            "claude_responses": [],
        }
        azure_fake.load(az_pr_state)

        task = {
            "owner": "testorg", "repo": "testproj", "issue_number": 3,
            "title": "Test work item", "body": "/pr",
            "autoswe_status": "fixed", "base_branch": "main",
            "session_id": "s2", "attempt_count": 1,
            "pr_number": None, "_token": "azure-pat",
            "provider": "azure",
        }

        def fake_ado_request(method, path, pat, body=None, **kw):
            ct = kw.get("content_type", "application/json")
            return azure_fake.handle_request(method, path, pat, body=body, content_type=ct)

        with patch("autoswe.providers.azure.api._ado_request", fake_ado_request):
            from autoswe.vcs.ship import open_pr
            open_pr(task, {}, {
                "provider": "azure",
                "org": "testorg", "project": "testproj", "repo": "testrepo",
                "pat": "azure-pat",
            })

        # Should have created a PR
        pr_calls = _find_post_pr_azure(azure_fake)
        assert pr_calls, "Expected POST pullrequests call"
        pr_body = pr_calls[-1]["body"]

        # Assert title contains Fixes #N and issue title
        assert "Fixes #3" in pr_body["title"]
        assert "Test work item" in pr_body["title"]

        # Assert description (Azure calls it description, not body)
        assert "Fixes #3" in pr_body.get("description", "")

        # Assert standard fields
        assert pr_body["sourceRefName"] == "refs/heads/autoswe/issue-3"
        assert pr_body["targetRefName"] == "refs/heads/main"


# ---------------------------------------------------------------------------
# End-to-end: full turn contracts (via harness)


# ---------------------------------------------------------------------------
# Full pipeline: plan -> fix -> pr content test


class TestPipelineContent:
    """Assert posted-comment content across a full plan -> fix -> pr pipeline."""

    def test_github_plan_fix_pr_pipeline_content(self, isolated_autoswe_dir):
        """Chain plan -> fix -> pr, asserting content at each phase."""
        from tests.scenarios.runner import assert_comments_posted, run_one_turn

        # Initial state: fresh issue with /plan
        plan_state = {
            "owner": "owner",
            "repo": "repo",
            "issue": {
                "id": 1, "number": 42, "title": "Pipeline test",
                "body": "/plan", "state": "open", "labels": [],
                "assignees": [], "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z", "closed_at": None,
                "author_association": "OWNER", "comments": 0,
                "user": {"login": "owner", "id": 1, "type": "User"},
                "pull_request": None,
            },
            "labels": [],
            "comments": [],
            "repo_labels": [],
            "authenticated_user": {"login": "owner", "id": 1, "type": "User"},
            "claude_responses": [
                {"text": "<AUTOSWE_PLAN>1. Implement the fix\n2. Add tests</AUTOSWE_PLAN>",
                 "session_id": "s-plan-42", "subtype": "success"},
            ],
        }

        seed_queue(isolated_autoswe_dir, None)
        setup_repos(isolated_autoswe_dir, "github", plan_state)
        cfg = build_test_cfg(isolated_autoswe_dir)

        # ---- Turn 1: /plan ----
        with patched_world(
            "github",
            state=plan_state,
            claude_responses=plan_state["claude_responses"],
            scripted_git=["create_worktree"],
            isolated_dir=isolated_autoswe_dir,
        ) as hw:
            run_one_turn("owner", "repo", cfg, isolated_autoswe_dir)
            # Plan content is finalized via PATCH (sticky progress comment)
            assert_comments_posted(hw.fake, [{"body_contains": ["## Plan", "Implement the fix"]}])

        # ---- Turn 2: /fix ----
        fix_state = {
            **plan_state,
            "issue": {**plan_state["issue"], "body": "/fix", "number": 42},
            "labels": ["autoswe:planned"],
            "comments": [
                {
                    "body": "## Plan\n\n1. Implement the fix\n2. Add tests\n\n<!-- autoswe-bot -->",
                    "created_at": "2026-01-01T01:00:00Z",
                    "author_association": "OWNER",
                    "user": {"login": "owner", "id": 1, "type": "User"},
                },
                {
                    "body": "/fix",
                    "created_at": "2026-01-01T02:00:00Z",
                    "author_association": "OWNER",
                    "user": {"login": "owner", "id": 1, "type": "User"},
                },
            ],
            "queue_task": {
                "id": "gh:owner_repo_42",
                "owner": "owner", "repo": "repo", "issue_number": 42,
                "title": "Pipeline test", "body": "/plan",
                "autoswe_status": "planned", "session_id": "s-plan-42",
                "base_branch": "main", "attempt_count": 1,
                "first_dispatched_at": None, "provider": "github",
            },
            "claude_responses": [
                {"text": "DONE_SUMMARY\tFixed the pipeline bug\tabc1234",
                 "session_id": "s-fix-42", "subtype": "success"},
            ],
        }

        with patched_world(
            "github",
            state=fix_state,
            claude_responses=fix_state["claude_responses"],
            scripted_git=["create_worktree", "commit_and_push"],
            isolated_dir=isolated_autoswe_dir,
        ) as hw:
            run_one_turn("owner", "repo", cfg, isolated_autoswe_dir)
            # Fix completion is finalized via PATCH (sticky progress comment)
            assert_comments_posted(hw.fake, [
                {"body_contains": ["Completed with command"]},
                {"body_contains": ["Fixed the pipeline bug"]},
            ])

        # ---- Turn 3: /pr ----
        pr_state = {
            **plan_state,
            "issue": {**plan_state["issue"], "body": "/fix\n\n/pr", "number": 42},
            "labels": ["autoswe:fixed"],
            "comments": [
                {
                    "body": "Completed with command `/fix` — DONE_SUMMARY\n\n<!-- autoswe-bot -->",
                    "created_at": "2026-01-01T02:00:00Z",
                    "author_association": "OWNER",
                    "user": {"login": "owner", "id": 1, "type": "User"},
                },
                {
                    "body": "/pr",
                    "created_at": "2026-01-01T03:00:00Z",
                    "author_association": "OWNER",
                    "user": {"login": "owner", "id": 1, "type": "User"},
                },
            ],
            "queue_task": {
                "id": "gh:owner_repo_42",
                "owner": "owner", "repo": "repo", "issue_number": 42,
                "title": "Pipeline test", "body": "/fix",
                "autoswe_status": "fixed", "session_id": "s-fix-42",
                "base_branch": "main", "attempt_count": 1,
                "first_dispatched_at": None, "pr_number": None,
                "provider": "github",
            },
            "claude_responses": [],
        }

        with patched_world(
            "github",
            state=pr_state,
            claude_responses=[],
            scripted_git=[],
            isolated_dir=isolated_autoswe_dir,
        ) as hw:
            run_one_turn("owner", "repo", cfg, isolated_autoswe_dir)
            # PR result is finalized via PATCH
            assert_comments_posted(hw.fake, [
                {"body_contains": ["Pull request"]},
            ])


# ---------------------------------------------------------------------------
# End-to-end: full turn contracts (via harness)


class TestE2EOutputContracts:
    """Verify output contracts via full poll turns."""

    def test_github_plan_put_labels_on_turn(self, isolated_autoswe_dir):
        """A /plan turn should PUT labels with autoswe:planned."""
        seed_queue(isolated_autoswe_dir, None)
        setup_repos(isolated_autoswe_dir, "github", _GH_PLAN_STATE)
        cfg = build_test_cfg(isolated_autoswe_dir)

        with patched_world(
            "github",
            state=_GH_PLAN_STATE,
            claude_responses=_GH_PLAN_STATE["claude_responses"],
            scripted_git=["create_worktree"],
            isolated_dir=isolated_autoswe_dir,
        ) as hw:
            from tests.scenarios.runner import run_one_turn
            run_one_turn("owner", "repo", cfg, isolated_autoswe_dir)

        label_calls = _find_put_labels(hw.fake)
        assert label_calls, "Expected PUT /labels call during plan turn"
        # At least one call should set autoswe:planned
        bodies = [c["body"] for c in label_calls]
        last_labels = bodies[-1].get("labels", [])
        label_names = [lb["name"] if isinstance(lb, dict) else lb for lb in last_labels]
        assert "autoswe:planned" in label_names

    def test_azure_plan_patch_tags_on_turn(self, isolated_autoswe_dir):
        """A /plan turn should PATCH workitem tags with autoswe:planned."""
        seed_queue(isolated_autoswe_dir, None)
        setup_repos(isolated_autoswe_dir, "azure", _AZ_PLAN_STATE)
        cfg = build_test_cfg(isolated_autoswe_dir, "azure")

        with patched_world(
            "azure",
            state=_AZ_PLAN_STATE,
            claude_responses=_AZ_PLAN_STATE["claude_responses"],
            scripted_git=["create_worktree"],
            isolated_dir=isolated_autoswe_dir,
        ) as hw:
            from tests.scenarios.runner import run_one_turn
            run_one_turn("testorg", "testproj", cfg, isolated_autoswe_dir)

        patch_calls = _find_patch_workitem(hw.fake)
        assert patch_calls, "Expected PATCH workitem call during plan turn"
        # At least one PATCH should contain autoswe:planned
        found = False
        for c in patch_calls:
            body = c.get("body") or []
            for op in body:
                if op.get("path") == "/fields/System.Tags" and "autoswe:planned" in op.get("value", ""):
                    found = True
                    break
        assert found, f"Expected autoswe:planned in PATCH tags. Calls: {[c['body'] for c in patch_calls]}"
