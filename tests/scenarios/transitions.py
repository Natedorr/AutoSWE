"""Declarative state-engine transition matrix.

Each row describes a starting state, an event (slash command or user reply),
the expected Claude responses, and the outcomes (label, queue fields, comments).

The test file ``test_transitions.py`` parametrises over ``TRANSITIONS × providers``
and drives each row through ``patched_world`` + ``run_one_turn``.

GitHub is the canonical flavour; ``_to_azure_state`` below maps a row to
Azure DevOps shapes (work items, tags instead of labels, different comment
fields).
"""
from __future__ import annotations

import copy
from typing import Any

# ---------------------------------------------------------------------------
# Transition row type

# A row dict has the following keys:
#   name            - str, unique identifier
#   start           - dict: initial state overlay on the base template
#   event           - dict: kind ("command" | "user_reply") + value
#   claude_responses - list[dict]: scripted Claude responses
#   expect          - dict: assertions on outcomes
#   git_calls       - list[str]: expected git function calls
#   tags            - dict: optional meta (e.g. "requires_first_dispatched")


# ---------------------------------------------------------------------------
# Base templates (minimal state for a fresh issue)

_GH_BASE: dict = {
    "owner": "owner",
    "repo": "repo",
    "issue": {
        "id": 1,
        "number": 42,
        "title": "Test issue",
        "body": "Issue description.",
        "state": "open",
        "labels": [],
        "assignees": [],
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
        "closed_at": None,
        "author_association": "OWNER",
        "comments": 0,
        "user": {"login": "owner", "id": 1, "type": "User"},
        "pull_request": None,
    },
    "labels": [],
    "comments": [],
    "repo_labels": [],
    "authenticated_user": {"login": "owner", "id": 1, "type": "User"},
}

_AZ_BASE: dict = {
    "org": "testorg",
    "project": "testproj",
    "repo": "testrepo",
    "work_item": {
        "id": 42,
        "rev": 1,
        "fields": {
            "System.Id": 42,
            "System.Title": "Test issue",
            "System.Description": "Issue description.",
            "System.State": "Active",
            "System.Tags": "",
            "System.CreatedDate": "2026-01-01T00:00:00Z",
            "System.ChangedDate": "2026-01-01T00:00:00Z",
        },
    },
    "tags": [],
    "comments": [],
    "authenticated_user": {"uniqueName": "owner@example.com", "id": "1"},
}


# ---------------------------------------------------------------------------
# Helpers

def _deepmerge(base: dict, overlay: dict) -> dict:
    """Deep-merge overlay into a copy of base. Returns merged dict."""
    result = copy.deepcopy(base)
    for key, val in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deepmerge(result[key], val)
        else:
            result[key] = copy.deepcopy(val)
    return result


def _to_azure_state(gh_state: dict) -> dict:
    """Convert a GitHub-flavoured state dict to Azure DevOps shapes.

    Maps:
      - owner → org/project
      - issue → work_item (number → id, body → System.Description, labels → tags)
      - labels → tags (list[str])
      - comments (body, created_at, user.login) → (text, createdDate, createdBy)
      - authenticated_user → Azure shape
    """
    az = copy.deepcopy(_AZ_BASE)

    wi = az["work_item"]
    gh_issue = gh_state.get("issue", {})

    wi["id"] = gh_issue.get("number", 42)
    wi["fields"]["System.Id"] = gh_issue.get("number", 42)
    wi["fields"]["System.Title"] = gh_issue.get("title", "Test issue")
    wi["fields"]["System.Description"] = gh_issue.get("body", "Issue description.")

    state_val = gh_issue.get("state", "open")
    wi["fields"]["System.State"] = "Closed" if state_val == "closed" else "Active"

    labels = gh_state.get("labels", [])
    az["tags"] = list(labels)
    wi["fields"]["System.Tags"] = "; ".join(labels) if labels else ""

    comments = gh_state.get("comments", [])
    az["comments"] = []
    for i, c in enumerate(comments):
        az_comment = {
            "id": i + 1,
            "text": c.get("body", ""),
            "createdDate": c.get("created_at", "2026-01-01T01:00:00Z"),
            "createdBy": {
                "displayName": "Owner",
                "id": "1",
                "uniqueName": "owner@example.com",
            },
        }
        # Preserve author association info for normalization
        assoc = c.get("author_association", "OWNER")
        if assoc == "COLLABORATOR":
            az_comment["createdBy"] = {
                "displayName": "Collab",
                "id": "2",
                "uniqueName": "collab@example.com",
            }
        az["comments"].append(az_comment)

    auth_user = gh_state.get("authenticated_user")
    if auth_user:
        az["authenticated_user"] = {
            "uniqueName": "owner@example.com",
            "id": "1",
        }

    return az


# ---------------------------------------------------------------------------
# Transition rows


TRANSITIONS: list[dict[str, Any]] = [
    # ---- Fresh issue transitions ----
    {
        "name": "fresh_plan_command",
        "description": "No existing task; /plan in body → planned",
        "start": {
            "issue": {"body": "Fix login.\n\n/plan"},
            "queue_task": None,
        },
        "claude_responses": [
            {"text": "<AUTOSWE_PLAN>1. Do the thing</AUTOSWE_PLAN>", "session_id": "s-plan-42", "subtype": "success"},
        ],
        "git_calls": ["create_worktree"],
        "expect": {
            "label_after": "autoswe:planned",
            "autoswe_status": "planned",
            "session_id": "s-plan-42",
            "pending_command": None,
            "comment_contains": ["## Plan", "Do the thing"],
            "claude_permission": "plan",
        },
    },
    {
        "name": "fresh_fix_command",
        "description": "No existing task; /fix in body → fixed",
        "start": {
            "issue": {"body": "Fix login.\n\n/fix"},
            "queue_task": None,
        },
        "claude_responses": [
            {"text": "DONE_SUMMARY\tFixed the bug\tabc1234", "session_id": "s-fix-42", "subtype": "success"},
        ],
        "git_calls": ["create_worktree", "commit_and_push"],
        "expect": {
            "label_after": "autoswe:fixed",
            "autoswe_status": "fixed",
            "pending_command": None,
            "comment_contains": ["Completed with command", "Fixed the bug"],
            "claude_permission": "bypassPermissions",
        },
    },
    {
        "name": "fresh_skip_command",
        "description": "No existing task; /skip → skipped immediately",
        "start": {
            "issue": {"body": "Not needed.\n\n/skip"},
            "queue_task": None,
        },
        "git_calls": [],
        "expect": {
            "label_after": "autoswe:skipped",
            "autoswe_status": "skipped",
            "no_claude_calls": True,
        },
    },
    {
        "name": "fresh_abort_command",
        "description": "No existing task; /abort → aborted (dispatch processes /abort)",
        "start": {
            "issue": {"body": "/abort"},
            "queue_task": None,
        },
        "git_calls": [],
        "expect": {
            # /abort on a fresh issue: sync treats it like a regular command
            # and sets pending. Dispatch then processes /abort → aborted.
            # The _map_done_to_status maps ABORTED → "aborted".
            "label_after": "autoswe:aborted",
            "autoswe_status": "aborted",
            "comment_contains": ["Task aborted"],
        },
    },
    {
        "name": "fresh_no_command",
        "description": "Plain issue with no slash command → untracked (null status)",
        "start": {
            "issue": {"body": "Just a description, no command."},
            "queue_task": None,
        },
        "git_calls": [],
        "expect": {
            "autoswe_status": None,
            "no_claude_calls": True,
        },
    },
    {
        "name": "fresh_plan_with_questions",
        "description": "Plan returns questions → waiting status",
        "start": {
            "issue": {"body": "/plan"},
            "queue_task": None,
        },
        "claude_responses": [
            {"text": "<AUTOSWE_QUESTIONS>What framework?</AUTOSWE_QUESTIONS>", "session_id": "s-plan-42", "subtype": "success"},
        ],
        "git_calls": ["create_worktree"],
        "expect": {
            "label_after": "autoswe:waiting",
            "autoswe_status": "waiting",
            "session_id": "s-plan-42",
            "comment_contains": ["What framework?"],
            "claude_permission": "plan",
        },
    },
    {
        "name": "fresh_fix_fails",
        "description": "/fix returns FAILED → failed status with retry hint",
        "start": {
            "issue": {"body": "/fix"},
            "queue_task": None,
        },
        "claude_responses": [
            {"text": "error", "session_id": "s-fix-42", "subtype": "error"},
        ],
        "git_calls": ["create_worktree"],
        "expect": {
            "label_after": "autoswe:failed",
            "autoswe_status": "failed",
            "comment_contains": ["Failed:", "/retry"],
        },
    },
    # ---- Resume transitions ----
    {
        "name": "plan_ready_then_fix",
        "description": "Task at planned; user posts /fix → fixed",
        "start": {
            "issue": {"body": "/plan"},
            "labels": ["autoswe:planned"],
            "comments": [
                {
                    "body": "## Plan\n\n1. Do the thing\n\n<!-- autoswe-bot -->",
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
                "title": "Test issue", "body": "/plan",
                "autoswe_status": "planned",
                "session_id": "s-plan-42",
                "base_branch": "main",
                "attempt_count": 1,
                "first_dispatched_at": None,
                "provider": "github",
            },
        },
        "claude_responses": [
            {"text": "DONE_SUMMARY\tApplied fix\tdef5678", "session_id": "s-fix-42", "subtype": "success"},
        ],
        "git_calls": ["create_worktree", "commit_and_push"],
        "expect": {
            "label_after": "autoswe:fixed",
            "autoswe_status": "fixed",
            "comment_contains": ["Completed with command", "Applied fix"],
            "claude_permission": "bypassPermissions",
        },
    },
    {
        "name": "plan_ready_user_plain_reply",
        "description": "Task at planned; user plain reply → resume plan",
        "start": {
            "issue": {"body": "/plan"},
            "labels": ["autoswe:planned"],
            "comments": [
                {
                    "body": "## Plan\n\n1. Initial plan\n\n<!-- autoswe-bot -->",
                    "created_at": "2026-01-01T01:00:00Z",
                    "author_association": "OWNER",
                    "user": {"login": "owner", "id": 1, "type": "User"},
                },
                {
                    "body": "Please also consider mobile support.",
                    "created_at": "2026-01-01T02:00:00Z",
                    "author_association": "OWNER",
                    "user": {"login": "owner", "id": 1, "type": "User"},
                },
            ],
            "queue_task": {
                "id": "gh:owner_repo_42",
                "owner": "owner", "repo": "repo", "issue_number": 42,
                "title": "Test issue", "body": "/plan",
                "autoswe_status": "planned",
                "session_id": "s-plan-42",
                "base_branch": "main",
                "attempt_count": 1,
                "first_dispatched_at": None,
                "provider": "github",
            },
        },
        "claude_responses": [
            {"text": "<AUTOSWE_PLAN>1. Do the thing\n2. Add mobile</AUTOSWE_PLAN>", "session_id": "s-plan-42", "subtype": "success"},
        ],
        "git_calls": ["create_worktree"],
        "expect": {
            "label_after": "autoswe:planned",
            "autoswe_status": "planned",
            "session_id": "s-plan-42",
            "comment_contains": ["## Plan", "Add mobile"],
            "claude_permission": "plan",
        },
    },
    {
        "name": "waiting_user_plain_reply",
        "description": "Task at waiting; user reply → resume plan",
        "start": {
            "issue": {"body": "/plan"},
            "labels": ["autoswe:waiting"],
            "comments": [
                {
                    "body": "What framework should we use?\n\n<!-- autoswe-bot -->",
                    "created_at": "2026-01-01T01:00:00Z",
                    "author_association": "OWNER",
                    "user": {"login": "owner", "id": 1, "type": "User"},
                },
                {
                    "body": "Use Django.",
                    "created_at": "2026-01-01T02:00:00Z",
                    "author_association": "OWNER",
                    "user": {"login": "owner", "id": 1, "type": "User"},
                },
            ],
            "queue_task": {
                "id": "gh:owner_repo_42",
                "owner": "owner", "repo": "repo", "issue_number": 42,
                "title": "Test issue", "body": "/plan",
                "autoswe_status": "waiting",
                "session_id": "s-plan-42",
                "base_branch": "main",
                "attempt_count": 1,
                "first_dispatched_at": None,
                "provider": "github",
            },
        },
        "claude_responses": [
            {"text": "<AUTOSWE_PLAN>1. Use Django\n2. Implement</AUTOSWE_PLAN>", "session_id": "s-plan-42", "subtype": "success"},
        ],
        "git_calls": ["create_worktree"],
        "expect": {
            "label_after": "autoswe:planned",
            "autoswe_status": "planned",
            "session_id": "s-plan-42",
            "comment_contains": ["## Plan", "Use Django"],
            "claude_permission": "plan",
        },
    },
    {
        "name": "waiting_user_posts_fix",
        "description": "Task at waiting; user posts /fix → dispatched as fix",
        "start": {
            "issue": {"body": "/plan"},
            "labels": ["autoswe:waiting"],
            "comments": [
                {
                    "body": "What framework?\n\n<!-- autoswe-bot -->",
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
                "title": "Test issue", "body": "/plan",
                "autoswe_status": "waiting",
                "session_id": "s-plan-42",
                "base_branch": "main",
                "attempt_count": 1,
                "first_dispatched_at": None,
                "provider": "github",
            },
        },
        "claude_responses": [
            {"text": "DONE_SUMMARY\tJust do it\tabc1234", "session_id": "s-fix-42", "subtype": "success"},
        ],
        "git_calls": ["create_worktree", "commit_and_push"],
        "expect": {
            "label_after": "autoswe:fixed",
            "autoswe_status": "fixed",
            "comment_contains": ["Completed with command"],
            "claude_permission": "bypassPermissions",
        },
    },
    # ---- Restart / retry transitions ----
    {
        "name": "failed_then_retry",
        "description": "Failed task; /retry → re-dispatches (replays last substantive cmd)",
        "start": {
            "issue": {"body": "/fix"},
            "labels": ["autoswe:failed"],
            "comments": [
                {
                    "body": "Failed: timeout\n\nPost `/retry` to try again.\n\n<!-- autoswe-bot -->",
                    "created_at": "2026-01-01T01:00:00Z",
                    "author_association": "OWNER",
                    "user": {"login": "owner", "id": 1, "type": "User"},
                },
                {
                    "body": "/retry",
                    "created_at": "2026-01-01T02:00:00Z",
                    "author_association": "OWNER",
                    "user": {"login": "owner", "id": 1, "type": "User"},
                },
            ],
            "queue_task": {
                "id": "gh:owner_repo_42",
                "owner": "owner", "repo": "repo", "issue_number": 42,
                "title": "Test issue", "body": "/fix",
                "autoswe_status": "failed",
                "base_branch": "main",
                "attempt_count": 1,
                "first_dispatched_at": None,
                "provider": "github",
            },
        },
        "claude_responses": [
            {"text": "DONE_SUMMARY\tFixed\tabc1234", "session_id": "s-fix-42", "subtype": "success"},
        ],
        "git_calls": ["create_worktree", "commit_and_push"],
        "expect": {
            "label_after": "autoswe:fixed",
            "autoswe_status": "fixed",
            "comment_contains": ["Completed with command"],
        },
    },
    {
        "name": "failed_plain_command_ignored",
        "description": "Failed task; plain /fix (not /retry) → ignored",
        "start": {
            "issue": {"body": "/fix"},
            "labels": ["autoswe:failed"],
            "comments": [
                {
                    "body": "Failed: error\n\nPost `/retry` to try again.\n\n<!-- autoswe-bot -->",
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
                "title": "Test issue", "body": "/fix",
                "autoswe_status": "failed",
                "base_branch": "main",
                "attempt_count": 1,
                "first_dispatched_at": None,
                "provider": "github",
            },
        },
        "expect": {
            "autoswe_status": "failed",
            "no_claude_calls": True,
        },
    },
    {
        "name": "done_then_new_fix",
        "description": "Fixed task; new /fix from user → re-dispatches",
        "start": {
            "issue": {"body": "Bug fix.\n\n/fix"},
            "labels": ["autoswe:fixed"],
            "comments": [
                {
                    "body": "Completed with command `/fix` — fixed.\n\n<!-- autoswe-bot -->",
                    "created_at": "2026-01-01T01:00:00Z",
                    "author_association": "OWNER",
                    "user": {"login": "owner", "id": 1, "type": "User"},
                },
                {
                    "body": "/fix with extra guidance",
                    "created_at": "2026-01-01T02:00:00Z",
                    "author_association": "OWNER",
                    "user": {"login": "owner", "id": 1, "type": "User"},
                },
            ],
            "queue_task": {
                "id": "gh:owner_repo_42",
                "owner": "owner", "repo": "repo", "issue_number": 42,
                "title": "Test issue", "body": "Bug fix.",
                "autoswe_status": "fixed",
                "base_branch": "main",
                "attempt_count": 1,
                "first_dispatched_at": None,
                "session_id": "s-fix-prev",
                "provider": "github",
            },
        },
        "claude_responses": [
            {"text": "DONE_SUMMARY\tExtra fix\tdef5678", "session_id": "s-fix-42", "subtype": "success"},
        ],
        "git_calls": ["create_worktree", "commit_and_push"],
        "expect": {
            "label_after": "autoswe:fixed",
            "autoswe_status": "fixed",
            "comment_contains": ["Completed with command", "Extra fix"],
        },
    },
    # ---- Sync transitions ----
    {
        "name": "fresh_sync_command",
        "description": "No existing task; /sync in body → synced",
        "start": {
            "issue": {"body": "Needs sync.\n\n/sync"},
            "queue_task": None,
        },
        "git_calls": ["create_worktree", "sync_branch"],
        "expect": {
            "label_after": "autoswe:synced",
            "autoswe_status": "synced",
            "comment_contains": ["Completed with command", "commits ahead"],
        },
    },
    {
        "name": "sync_with_existing_task",
        "description": "Existing pending task; /sync → dispatched → done",
        "start": {
            "issue": {"body": "/sync"},
            "labels": ["autoswe:pending"],
            "comments": [],
            "queue_task": {
                "id": "gh:owner_repo_42",
                "owner": "owner", "repo": "repo", "issue_number": 42,
                "title": "Test issue", "body": "/sync",
                "autoswe_status": "pending",
                "pending_command": "/sync",
                "base_branch": "main",
                "attempt_count": 0,
                "first_dispatched_at": None,
                "provider": "github",
            },
        },
        "git_calls": ["create_worktree", "sync_branch"],
        "expect": {
            "label_after": "autoswe:synced",
            "autoswe_status": "synced",
            "comment_contains": ["Completed with command", "commits ahead"],
        },
    },
    # ---- Guard transitions ----
    {
        "name": "attempt_count_resets_from_plan_ready",
        "description": "Task at planned with high attempt_count; /fix resets to 1 and dispatches successfully",
        "start": {
            "issue": {"body": "/fix"},
            "labels": ["autoswe:planned"],
            "comments": [
                {
                    "body": "## Plan\n\n1. Do the thing\n\n<!-- autoswe-bot -->",
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
                "title": "Test issue", "body": "/fix",
                "autoswe_status": "planned",
                "base_branch": "main",
                "attempt_count": 3,
                "first_dispatched_at": None,
                "provider": "github",
            },
        },
        "claude_responses": [
            {"text": "DONE_SUMMARY\tApplied fix\tdef5678", "session_id": "s-fix-42", "subtype": "success"},
        ],
        "git_calls": ["create_worktree", "commit_and_push"],
        "expect": {
            "label_after": "autoswe:fixed",
            "autoswe_status": "fixed",
            "comment_contains": ["Completed with command", "Applied fix"],
            "claude_permission": "bypassPermissions",
        },
    },
    # ---- PR transition ----
    {
        "name": "done_then_pr",
        "description": "Fixed task; /pr from user → PR opened",
        "skip_providers": ["azure"],
        "start": {
            "issue": {"body": "Fix.\n\n/fix"},
            "labels": ["autoswe:fixed"],
            "comments": [
                {
                    "body": "Completed with command `/fix` — DONE_SUMMARY\n\n<!-- autoswe-bot -->",
                    "created_at": "2026-01-01T01:00:00Z",
                    "author_association": "OWNER",
                    "user": {"login": "owner", "id": 1, "type": "User"},
                },
                {
                    "body": "/pr",
                    "created_at": "2026-01-01T02:00:00Z",
                    "author_association": "OWNER",
                    "user": {"login": "owner", "id": 1, "type": "User"},
                },
            ],
            "queue_task": {
                "id": "gh:owner_repo_42",
                "owner": "owner", "repo": "repo", "issue_number": 42,
                "title": "Test issue", "body": "Fix.",
                "autoswe_status": "fixed",
                "base_branch": "main",
                "attempt_count": 1,
                "first_dispatched_at": None,
                "session_id": "s-fix-prev",
                "pr_number": None,
                "provider": "github",
            },
        },
        "expect": {
            "label_after": "autoswe:shipped",
            "autoswe_status": "shipped",
            "comment_contains": ["Completed with command", "/pr"],
        },
    },
    # ---- Skip on existing task ----
    {
        "name": "existing_task_skip",
        "description": "Existing task at any status; /skip → skipped",
        "start": {
            "issue": {"body": "/plan"},
            "labels": ["autoswe:planned"],
            "comments": [
                {
                    "body": "## Plan\n\n1. Do the thing\n\n<!-- autoswe-bot -->",
                    "created_at": "2026-01-01T01:00:00Z",
                    "author_association": "OWNER",
                    "user": {"login": "owner", "id": 1, "type": "User"},
                },
                {
                    "body": "/skip",
                    "created_at": "2026-01-01T02:00:00Z",
                    "author_association": "OWNER",
                    "user": {"login": "owner", "id": 1, "type": "User"},
                },
            ],
            "queue_task": {
                "id": "gh:owner_repo_42",
                "owner": "owner", "repo": "repo", "issue_number": 42,
                "title": "Test issue", "body": "/plan",
                "autoswe_status": "planned",
                "base_branch": "main",
                "attempt_count": 1,
                "first_dispatched_at": None,
                "session_id": "s-plan-42",
                "provider": "github",
            },
        },
        "expect": {
            "label_after": "autoswe:skipped",
            "autoswe_status": "skipped",
            "no_claude_calls": True,
        },
    },
    # ---- Bug #119: first_dispatched_at reset on plan_ready → fix transition ----
    {
        "name": "plan_ready_then_fix_with_old_dispatch_time",
        "description": "Bug #119: planned with old first_dispatched_at; /fix should reset clock and NOT fire time limit",
        "start": {
            "issue": {"body": "/plan"},
            "labels": ["autoswe:planned"],
            "comments": [
                {
                    "body": "## Plan\n\n1. Do the thing\n\n<!-- autoswe-bot -->",
                    "created_at": "2026-01-01T01:00:00Z",
                    "author_association": "OWNER",
                    "user": {"login": "owner", "id": 1, "type": "User"},
                },
                {
                    "body": "/fix",
                    "created_at": "2026-01-01T12:00:00Z",
                    "author_association": "OWNER",
                    "user": {"login": "owner", "id": 1, "type": "User"},
                },
            ],
            "queue_task": {
                "id": "gh:owner_repo_42",
                "owner": "owner", "repo": "repo", "issue_number": 42,
                "title": "Test issue", "body": "/plan",
                "autoswe_status": "planned",
                "session_id": "s-plan-42",
                "base_branch": "main",
                "attempt_count": 1,
                # first_dispatched_at is 5h ago — well beyond 2h MAX_TOTAL_HOURS
                "first_dispatched_at": "2026-01-01T07:00:00+00:00",
                "provider": "github",
            },
        },
        "claude_responses": [
            {"text": "DONE_SUMMARY\tApplied fix\tdef5678", "session_id": "s-fix-42", "subtype": "success"},
        ],
        "git_calls": ["create_worktree", "commit_and_push"],
        "expect": {
            "label_after": "autoswe:fixed",
            "autoswe_status": "fixed",
            "first_dispatched_at_reset": True,
            "comment_contains": ["Completed with command", "Applied fix"],
            "claude_permission": "bypassPermissions",
        },
    },
    # ---- Bug #183: /abort after plan_ready → aborted status (not failed) ----
    {
        "name": "plan_ready_then_abort",
        "description": "Bug #183: Task at planned; user posts /abort → aborted (not failed)",
        "start": {
            "issue": {"body": "/plan"},
            "labels": ["autoswe:planned"],
            "comments": [
                {
                    "body": "## Plan\n\n1. Do the thing\n\n<!-- autoswe-bot -->",
                    "created_at": "2026-01-01T01:00:00Z",
                    "author_association": "OWNER",
                    "user": {"login": "owner", "id": 1, "type": "User"},
                },
                {
                    "body": "/abort",
                    "created_at": "2026-01-01T02:00:00Z",
                    "author_association": "OWNER",
                    "user": {"login": "owner", "id": 1, "type": "User"},
                },
            ],
            "queue_task": {
                "id": "gh:owner_repo_42",
                "owner": "owner", "repo": "repo", "issue_number": 42,
                "title": "Test issue", "body": "/plan",
                "autoswe_status": "planned",
                "session_id": "s-plan-42",
                "base_branch": "main",
                "attempt_count": 1,
                "first_dispatched_at": None,
                "provider": "github",
            },
        },
        "git_calls": [],
        "expect": {
            "label_after": "autoswe:aborted",
            "autoswe_status": "aborted",
            "no_claude_calls": True,
            "comment_contains": ["Task aborted"],
        },
    },
    {
        "name": "aborted_then_fix_restart",
        "description": "Aborted task; /fix from user → re-dispatches as new attempt",
        "start": {
            "issue": {"body": "/plan"},
            "labels": ["autoswe:aborted"],
            "comments": [
                {
                    "body": "Task aborted.\n<!-- autoswe-bot -->",
                    "created_at": "2026-01-01T02:00:00Z",
                    "author_association": "OWNER",
                    "user": {"login": "owner", "id": 1, "type": "User"},
                },
                {
                    "body": "/fix",
                    "created_at": "2026-01-01T03:00:00Z",
                    "author_association": "OWNER",
                    "user": {"login": "owner", "id": 1, "type": "User"},
                },
            ],
            "queue_task": {
                "id": "gh:owner_repo_42",
                "owner": "owner", "repo": "repo", "issue_number": 42,
                "title": "Test issue", "body": "/plan",
                "autoswe_status": "aborted",
                "base_branch": "main",
                "attempt_count": 1,
                "first_dispatched_at": None,
                "provider": "github",
            },
        },
        "claude_responses": [
            {"text": "DONE_SUMMARY\tApplied fix\tdef5678", "session_id": "s-fix-42", "subtype": "success"},
        ],
        "git_calls": ["create_worktree", "commit_and_push"],
        "expect": {
            "label_after": "autoswe:fixed",
            "autoswe_status": "fixed",
            "comment_contains": ["Completed with command", "Applied fix"],
            "claude_permission": "bypassPermissions",
        },
    },
    # ---- Batch 11: Multi-turn workflow scenarios ----
    {
        "name": "attempt_limit_hit",
        "description": "Guard-blocked task with /fix (not /retry) → stays blocked, requires /retry",
        "start": {
            "issue": {"body": "/fix"},
            "labels": ["autoswe:failed"],
            "comments": [
                {
                    "body": "Max attempts (3) reached. Post `/retry` to continue.\n<!-- autoswe-bot -->",
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
                "title": "Test issue", "body": "/fix",
                "autoswe_status": "failed",
                "base_branch": "main",
                "attempt_count": 3,
                "first_dispatched_at": None,
                "_guard_blocked": True,
                "provider": "github",
            },
        },
        "expect": {
            "autoswe_status": "failed",
            "no_claude_calls": True,
        },
    },
    {
        "name": "retry_resets_attempt_count",
        "description": "/retry from failed state resets attempt count and re-dispatches",
        "start": {
            "issue": {"body": "/fix"},
            "labels": ["autoswe:failed"],
            "comments": [
                {
                    "body": "Failed: timeout\n\nPost `/retry` to continue.\n<!-- autoswe-bot -->",
                    "created_at": "2026-01-01T01:00:00Z",
                    "author_association": "OWNER",
                    "user": {"login": "owner", "id": 1, "type": "User"},
                },
                {
                    "body": "/retry",
                    "created_at": "2026-01-01T02:00:00Z",
                    "author_association": "OWNER",
                    "user": {"login": "owner", "id": 1, "type": "User"},
                },
            ],
            "queue_task": {
                "id": "gh:owner_repo_42",
                "owner": "owner", "repo": "repo", "issue_number": 42,
                "title": "Test issue", "body": "/fix",
                "autoswe_status": "failed",
                "base_branch": "main",
                "attempt_count": 2,
                "last_dispatched_command": "/fix",
                "first_dispatched_at": None,
                "provider": "github",
            },
        },
        "claude_responses": [
            {"text": "DONE_SUMMARY\tFixed\tabc1234", "session_id": "s-fix-42", "subtype": "success"},
        ],
        "git_calls": ["create_worktree", "commit_and_push"],
        "expect": {
            "label_after": "autoswe:fixed",
            "autoswe_status": "fixed",
            "comment_contains": ["Completed with command"],
        },
    },
    {
        "name": "dispatched_command_noop",
        "description": "Task in planning state; new /fix command → noop",
        "start": {
            "issue": {"body": "/plan"},
            "labels": ["autoswe:planning"],
            "comments": [
                {
                    "body": "Dispatching `plan`&hellip;\n<!-- autoswe-bot -->",
                    "created_at": "2026-01-01T00:30:00Z",
                    "author_association": "OWNER",
                    "user": {"login": "owner", "id": 1, "type": "User"},
                },
                {
                    "body": "/fix",
                    "created_at": "2026-01-01T01:00:00Z",
                    "author_association": "OWNER",
                    "user": {"login": "owner", "id": 1, "type": "User"},
                },
            ],
            "queue_task": {
                "id": "gh:owner_repo_42",
                "owner": "owner", "repo": "repo", "issue_number": 42,
                "title": "Test issue", "body": "/plan",
                "autoswe_status": "planning",
                "base_branch": "main",
                "attempt_count": 1,
                "first_dispatched_at": "2026-01-01T00:30:00Z",
                "last_dispatched_command": "/plan",
                "provider": "github",
            },
        },
        "expect": {
            "autoswe_status": "planning",
            "no_claude_calls": True,
        },
    },
    {
        "name": "stale_command_suppressed",
        "description": "Re-issued /plan with older ID → suppressed by watermark",
        "start": {
            "issue": {"body": "/plan"},
            "labels": ["autoswe:planned"],
            "comments": [
                {
                    "body": "Completed with command `/plan`.\n<!-- autoswe-bot -->",
                    "created_at": "2026-01-01T01:00:00Z",
                    "author_association": "OWNER",
                    "user": {"login": "owner", "id": 1, "type": "User"},
                },
                {
                    "body": "/plan",
                    "created_at": "2026-01-01T00:00:00Z",  # Older than completion
                    "author_association": "OWNER",
                    "user": {"login": "owner", "id": 1, "type": "User"},
                },
            ],
            "queue_task": {
                "id": "gh:owner_repo_42",
                "owner": "owner", "repo": "repo", "issue_number": 42,
                "title": "Test issue", "body": "/plan",
                "autoswe_status": "planned",
                "base_branch": "main",
                "attempt_count": 1,
                "first_dispatched_at": None,
                "last_dispatched_command": "/plan",
                "last_dispatched_command_id": 999,
                "provider": "github",
            },
        },
        "expect": {
            "autoswe_status": "planned",
            "no_claude_calls": True,
        },
    },
    {
        "name": "waiting_fix_command_resume",
        "description": "Task at waiting; user posts /fix → dispatched as fix (resume)",
        "start": {
            "issue": {"body": "/plan"},
            "labels": ["autoswe:waiting"],
            "comments": [
                {
                    "body": "What should the branch be named?\n<!-- autoswe-bot -->",
                    "created_at": "2026-01-01T00:30:00Z",
                    "author_association": "OWNER",
                    "user": {"login": "owner", "id": 1, "type": "User"},
                },
                {
                    "body": "/fix",
                    "created_at": "2026-01-01T01:00:00Z",
                    "author_association": "OWNER",
                    "user": {"login": "owner", "id": 1, "type": "User"},
                },
            ],
            "queue_task": {
                "id": "gh:owner_repo_42",
                "owner": "owner", "repo": "repo", "issue_number": 42,
                "title": "Test issue", "body": "/plan",
                "autoswe_status": "waiting",
                "session_id": "s-plan-42",
                "base_branch": "main",
                "attempt_count": 1,
                "first_dispatched_at": None,
                "provider": "github",
            },
        },
        "claude_responses": [
            {"text": "DONE_SUMMARY\tJust do it\tabc1234", "session_id": "s-fix-42", "subtype": "success"},
        ],
        "git_calls": ["create_worktree", "commit_and_push"],
        "expect": {
            "label_after": "autoswe:fixed",
            "autoswe_status": "fixed",
            "comment_contains": ["Completed with command"],
            "claude_permission": "bypassPermissions",
        },
    },
    {
        "name": "done_plain_reply_noop",
        "description": "Fixed task; plain reply (no command) → noop (need explicit command)",
        "start": {
            "issue": {"body": "Bug."},
            "labels": ["autoswe:fixed"],
            "comments": [
                {
                    "body": "Completed with command `/fix`.\n<!-- autoswe-bot -->",
                    "created_at": "2026-01-01T01:00:00Z",
                    "author_association": "OWNER",
                    "user": {"login": "owner", "id": 1, "type": "User"},
                },
                {
                    "body": "Thanks, this looks good!",
                    "created_at": "2026-01-01T02:00:00Z",
                    "author_association": "OWNER",
                    "user": {"login": "owner", "id": 1, "type": "User"},
                },
            ],
            "queue_task": {
                "id": "gh:owner_repo_42",
                "owner": "owner", "repo": "repo", "issue_number": 42,
                "title": "Test issue", "body": "Bug.",
                "autoswe_status": "fixed",
                "base_branch": "main",
                "attempt_count": 1,
                "first_dispatched_at": None,
                "provider": "github",
            },
        },
        "expect": {
            "autoswe_status": "fixed",
            "no_claude_calls": True,
        },
    },
    {
        "name": "null_advance_watermark",
        "description": "Task status=null, suppress_welcome=True, auto_dispatch_new → advance_watermark",
        "start": {
            "issue": {"body": "Just a bug description."},
            "labels": [],
            "comments": [],
            "queue_task": {
                "id": "gh:owner_repo_42",
                "owner": "owner", "repo": "repo", "issue_number": 42,
                "title": "Test issue", "body": "Just a bug description.",
                "autoswe_status": None,
                "base_branch": "main",
                "attempt_count": 0,
                "first_dispatched_at": None,
                "suppress_welcome": True,
                "provider": "github",
            },
        },
        "expect": {
            "autoswe_status": None,
            "no_claude_calls": True,
        },
    },
    # ---- Sync conflict resolution transitions ----
    {
        "name": "sync_conflict_resolved",
        "description": "Issue with prior plan; /sync produces conflict; Claude resolves; status → synced",
        "meta": {"script_sync_conflict": True},
        "start": {
            "issue": {"body": "Fix needed.\n\n/sync"},
            "labels": ["autoswe:planned"],
            "comments": [
                {
                    "body": "## Plan\n\n1. Fix the thing\n\n<!-- autoswe-bot -->",
                    "created_at": "2026-01-01T01:00:00Z",
                    "author_association": "OWNER",
                    "user": {"login": "owner", "id": 1, "type": "User"},
                },
                {
                    "body": "/sync",
                    "created_at": "2026-01-01T03:00:00Z",
                    "author_association": "OWNER",
                    "user": {"login": "owner", "id": 1, "type": "User"},
                },
            ],
            "queue_task": {
                "id": "gh:owner_repo_42",
                "owner": "owner", "repo": "repo", "issue_number": 42,
                "title": "Test issue", "body": "Fix needed.",
                "autoswe_status": "planned",
                "session_id": "s-plan-42",
                "base_branch": "main",
                "attempt_count": 1,
                "first_dispatched_at": None,
                "provider": "github",
            },
        },
        "claude_responses": [
            {"text": "Resolved conflicts.", "session_id": "s-resolve-42", "subtype": "success"},
        ],
        "git_calls": ["worktree_path", "sync_branch", "get_merge_conflict_files"],
        "expect": {
            "label_after": "autoswe:synced",
            "autoswe_status": "synced",
            "comment_contains": ["Completed with command", "Resolved merge conflicts"],
        },
    },
    {
        "name": "sync_conflict_unresolved",
        "description": "Claude fails to resolve merge conflict; status → failed; conflict files reported",
        "meta": {"script_sync_conflict": True},
        "start": {
            "issue": {"body": "Fix needed.\n\n/sync"},
            "labels": ["autoswe:planned"],
            "comments": [
                {
                    "body": "## Plan\n\n1. Fix the thing\n\n<!-- autoswe-bot -->",
                    "created_at": "2026-01-01T01:00:00Z",
                    "author_association": "OWNER",
                    "user": {"login": "owner", "id": 1, "type": "User"},
                },
                {
                    "body": "/sync",
                    "created_at": "2026-01-01T03:00:00Z",
                    "author_association": "OWNER",
                    "user": {"login": "owner", "id": 1, "type": "User"},
                },
            ],
            "queue_task": {
                "id": "gh:owner_repo_42",
                "owner": "owner", "repo": "repo", "issue_number": 42,
                "title": "Test issue", "body": "Fix needed.",
                "autoswe_status": "planned",
                "session_id": "s-plan-42",
                "base_branch": "main",
                "attempt_count": 1,
                "first_dispatched_at": None,
                "provider": "github",
            },
        },
        "claude_responses": [
            {"text": "error", "session_id": "s-resolve-42", "subtype": "error_max_turns"},
        ],
        "git_calls": ["worktree_path", "sync_branch"],
        "expect": {
            "label_after": "autoswe:failed",
            "autoswe_status": "failed",
            "comment_contains": ["Failed:", "/retry"],
        },
    },
    # ---- Review transitions ----
    {
        "name": "waiting_then_review",
        "description": "Task at waiting; user posts /review → review completes → returns to waiting",
        "meta": {"script_review": True},
        "start": {
            "issue": {"body": "/plan"},
            "labels": ["autoswe:waiting"],
            "comments": [
                {
                    "body": "What approach?\n\n<!-- autoswe-bot -->",
                    "created_at": "2026-01-01T01:00:00Z",
                    "author_association": "OWNER",
                    "user": {"login": "owner", "id": 1, "type": "User"},
                },
                {
                    "body": "/review",
                    "created_at": "2026-01-01T02:00:00Z",
                    "author_association": "OWNER",
                    "user": {"login": "owner", "id": 1, "type": "User"},
                },
            ],
            "queue_task": {
                "id": "gh:owner_repo_42",
                "owner": "owner", "repo": "repo", "issue_number": 42,
                "title": "Test issue", "body": "/plan",
                "autoswe_status": "waiting",
                "session_id": "s-plan-42",
                "base_branch": "main",
                "attempt_count": 1,
                "first_dispatched_at": None,
                "provider": "github",
            },
        },
        "claude_responses": [
            {"text": "## Summary\n\nGood.\n\n## Verdict\n\nLGTM", "session_id": "s-review-42", "subtype": "success"},
        ],
        "git_calls": ["worktree_path"],
        "expect": {
            "label_after": "autoswe:reviewed",
            "autoswe_status": "reviewed",
            "comment_contains": ["## Review", "LGTM"],
            "claude_permission": "plan",
        },
    },
    {
        "name": "plan_ready_then_review",
        "description": "Task at planned; user posts /review → review completes → reviewed (terminal)",
        "meta": {"script_review": True},
        "start": {
            "issue": {"body": "/plan"},
            "labels": ["autoswe:planned"],
            "comments": [
                {
                    "body": "## Plan\n\n1. Do the thing\n\n<!-- autoswe-bot -->",
                    "created_at": "2026-01-01T01:00:00Z",
                    "author_association": "OWNER",
                    "user": {"login": "owner", "id": 1, "type": "User"},
                },
                {
                    "body": "/review",
                    "created_at": "2026-01-01T02:00:00Z",
                    "author_association": "OWNER",
                    "user": {"login": "owner", "id": 1, "type": "User"},
                },
            ],
            "queue_task": {
                "id": "gh:owner_repo_42",
                "owner": "owner", "repo": "repo", "issue_number": 42,
                "title": "Test issue", "body": "/plan",
                "autoswe_status": "planned",
                "session_id": "s-plan-42",
                "base_branch": "main",
                "attempt_count": 1,
                "first_dispatched_at": None,
                "provider": "github",
            },
        },
        "claude_responses": [
            {"text": "## Summary\n\nGood.\n\n## Verdict\n\nLGTM", "session_id": "s-review-42", "subtype": "success"},
        ],
        "git_calls": ["worktree_path"],
        "expect": {
            "label_after": "autoswe:reviewed",
            "autoswe_status": "reviewed",
            "comment_contains": ["## Review", "LGTM"],
            "claude_permission": "plan",
        },
    },
    {
        "name": "planned_then_review",
        "description": "Task at planned; user posts /review → review completes → reviewed (terminal)",
        "meta": {"script_review": True},
        "start": {
            "issue": {"body": "/plan"},
            "labels": ["autoswe:planned"],
            "comments": [
                {
                    "body": "## Plan\n\n1. Implement the feature\n\n<!-- autoswe-bot -->",
                    "created_at": "2026-01-01T01:00:00Z",
                    "author_association": "OWNER",
                    "user": {"login": "owner", "id": 1, "type": "User"},
                },
                {
                    "body": "/review",
                    "created_at": "2026-01-01T02:00:00Z",
                    "author_association": "OWNER",
                    "user": {"login": "owner", "id": 1, "type": "User"},
                },
            ],
            "queue_task": {
                "id": "gh:owner_repo_42",
                "owner": "owner", "repo": "repo", "issue_number": 42,
                "title": "Test issue", "body": "/plan",
                "autoswe_status": "planned",
                "session_id": "s-plan-42",
                "base_branch": "main",
                "attempt_count": 1,
                "first_dispatched_at": None,
                "provider": "github",
            },
        },
        "claude_responses": [
            {"text": "## Summary\n\nPlan looks solid.\n\n## Verdict\n\nLGTM", "session_id": "s-review-42", "subtype": "success"},
        ],
        "git_calls": ["worktree_path"],
        "expect": {
            "label_after": "autoswe:reviewed",
            "autoswe_status": "reviewed",
            "comment_contains": ["## Review", "LGTM"],
            "claude_permission": "plan",
        },
    },
]


# ---------------------------------------------------------------------------
# Provider state builder

def build_github_state(row: dict) -> dict:
    """Build a complete GitHub state dict from a transition row."""
    start = row.get("start", {})
    return _deepmerge(_GH_BASE, start)


def build_azure_state(row: dict) -> dict:
    """Build a complete Azure state dict from a transition row.

    Starts from the GitHub overlay, then converts to Azure shapes.
    """
    gh_state = build_github_state(row)
    return _to_azure_state(gh_state)


def build_queue_task(row: dict, provider: str) -> dict | None:
    """Extract and adjust the queue_task from a row for the given provider."""
    task = row.get("start", {}).get("queue_task")
    if task is None:
        return None
    task = copy.deepcopy(task)
    if provider == "azure":
        task["id"] = "ado:testorg_testproj/testrepo_42"
        task["owner"] = "testorg"
        task["repo"] = "testproj"
        task["provider"] = "azure"
    else:
        task["id"] = "gh:owner_repo_42"
        task["owner"] = "owner"
        task["repo"] = "repo"
        task["provider"] = "github"
    return task
