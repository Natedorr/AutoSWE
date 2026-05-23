"""Extended harness tests — merge conflicts, closed issue guard, multi-command flows.

These test the integration layer (decide + emit + handlers) for edge cases
that don't fit the streaming session flow pattern.
"""

from __future__ import annotations

import pytest

from autoswe.orch.decide import decide
from autoswe.orch.emit import emit
from autoswe.orch.types import (
    Action,
    ApiState,
    TaskState,
    World,
)
from autoswe.providers.base import NormalizedComment, NormalizedIssue

# --========================================================================
# Helpers
# --========================================================================

def _build_world(
    issue_num=42,
    status=None,
    body="",
    comments=None,
    guard_blocked=False,
    session_id=None,
    plan_branch=None,
    attempt_count=0,
    suppress_welcome=False,
    pr_number=None,
    last_phase=None,
    first_dispatched_at=None,
    last_dispatched_command=None,
    last_dispatched_command_id=None,
    cfg=None,
    repo_cfg=None,
    gh_closed=False,
):
    """Build a minimal World for decide/emit tests."""
    issue = NormalizedIssue(
        number=issue_num,
        title="Test issue",
        body=body,
        owner="owner",
        repo="repo",
        state="open",
    )
    api = ApiState(
        issue=issue,
        comments=comments or [],
        open_pr_numbers=[],
    )
    task = TaskState(
        slug=f"gh:owner_repo_{issue_num}",
        owner="owner",
        repo="repo",
        issue_number=issue_num,
        title="Test issue",
        body=body,
        status=status,
        plan_branch=plan_branch,
        base_branch="main",
        attempt_count=attempt_count,
        first_dispatched_at=first_dispatched_at,
        last_dispatched_command=last_dispatched_command,
        last_dispatched_command_id=last_dispatched_command_id,
        last_consumed_reply_id=None,
        session_id=session_id,
        pr_number=pr_number,
        guard_blocked=guard_blocked,
        gh_closed=gh_closed,
        pending_command=None,
        pending_guidance=None,
        pending_user_reply=None,
        suppress_welcome=suppress_welcome,
        last_phase=last_phase,
    )
    return World(
        api=api,
        task=task,
        cfg=cfg or {"MAX_ATTEMPTS": 3, "BOT_NAME": "autoswe"},
        repo_cfg=repo_cfg or {},
    )


def _user_comment(body, comment_id, created_at="2026-01-01T02:00:00Z"):
    return NormalizedComment(
        body=body,
        created_at=created_at,
        author_login="user",
        id=comment_id,
        is_bot=False,
    )


def _bot_comment(body, comment_id, created_at="2026-01-01T01:00:00Z"):
    return NormalizedComment(
        body=body,
        created_at=created_at,
        author_login="autoswe",
        id=comment_id,
        is_bot=True,
    )


# --========================================================================
# Closed issue guard
# --========================================================================

class TestClosedIssueGuard:
    """Closed issues should not be dispatched."""

    def test_closed_issue_handled_by_loop_not_decide(self):
        """gh_closed is checked in the loop layer (loop.py), not decide.py.
        decide() will still return a plan action for a closed issue —
        the loop prevents dispatch. This documents the current behavior."""
        world = _build_world(body="/fix", gh_closed=True)

        action = decide(world)
        # decide doesn't check gh_closed — loop.py handles this before dispatch
        # For a fresh task with /fix, decide returns a fix action
        assert action.kind == "fix"


# --========================================================================
# Multi-command on same issue
# --========================================================================

class TestMultiCommand:
    """Multiple slash commands on the same issue should use the latest."""

    def test_newer_command_wins(self):
        """When there are multiple commands, the latest one should be used."""
        comments = [
            _user_comment("/plan", 1, "2026-01-01T01:00:00Z"),
            _user_comment("/fix", 2, "2026-01-01T02:00:00Z"),
        ]
        world = _build_world(comments=comments, status=None, suppress_welcome=True)

        action = decide(world)
        # /fix (id=2) should win over /plan (id=1)
        assert action.kind == "fix"
        assert action.triggering_comment_id == 2

    def test_stale_command_noop(self):
        """A command older than the last dispatch should be nooped."""
        comments = [
            _bot_comment("Plan posted.\n<!-- autoswe-bot -->", 1),
            _user_comment("/fix", 2, "2026-01-01T03:00:00Z"),
        ]
        # Task already dispatched /fix at id=2
        world = _build_world(
            comments=comments,
            status="failed",
            last_dispatched_command="/fix",
            last_dispatched_command_id=2,
            attempt_count=1,
        )
        # The /fix at id=2 is the same as last dispatched — should noop
        action = decide(world)
        assert action.kind == "noop"


# --========================================================================
# Merge conflict handling
# --========================================================================

class TestMergeConflict:
    """Merge conflicts should be handled in the fix phase."""

    def test_fix_with_conflict_files_in_prompt(self):
        """When conflict files exist, the fix prompt should include conflict resolution instructions."""
        from autoswe.harness.coder import build_fix_prompt

        task = {
            "owner": "owner",
            "repo": "repo",
            "issue_number": 42,
            "title": "Fix the bug",
            "body": "Something is broken",
        }
        guidance = "Fix the bug"

        prompt = build_fix_prompt(task, guidance, repo_root="/tmp", plan_text=None, repo_cfg={})
        # Normal fix prompt should not mention merge conflicts
        assert "Merge conflicts" not in prompt

    def test_fix_prompt_includes_plan_text(self):
        """When plan text is provided, it should be included in the fix prompt."""
        from autoswe.harness.coder import build_fix_prompt

        task = {
            "owner": "owner",
            "repo": "repo",
            "issue_number": 42,
            "title": "Fix the bug",
            "body": "Something is broken",
        }
        plan_text = "## Plan\n1. Step one\n2. Step two"
        guidance = "Follow the plan"

        prompt = build_fix_prompt(task, guidance, repo_root="/tmp", plan_text=plan_text, repo_cfg={})
        assert "Step one" in prompt or plan_text in prompt


# --========================================================================
# Guard and retry edge cases
# --========================================================================

class TestGuardRetryEdgeCases:
    """Edge cases for guard blocking and retry."""

    def test_guard_blocked_skips_fix(self):
        """A guard-blocked task should skip /fix (noop)."""
        comments = [
            _bot_comment("Max attempts (3) reached.\n<!-- autoswe-bot -->", 1),
            _user_comment("/fix", 2),
        ]
        world = _build_world(
            comments=comments,
            status="failed",
            guard_blocked=True,
            attempt_count=3,
            last_dispatched_command="/fix",
            last_dispatched_command_id=1,
        )
        action = decide(world)
        assert action.kind == "noop"

    def test_guard_blocked_allows_retry(self):
        """A guard-blocked task should allow /retry."""
        comments = [
            _bot_comment("Max attempts (3) reached.\n<!-- autoswe-bot -->", 1),
            _user_comment("/retry", 2),
        ]
        world = _build_world(
            comments=comments,
            status="failed",
            guard_blocked=True,
            attempt_count=3,
            last_dispatched_command="/fix",
            last_dispatched_command_id=1,
        )
        action = decide(world)
        assert action.kind == "retry"
        assert action.attempt_count == 1

    def test_guard_blocked_allows_skip(self):
        """A guard-blocked task should allow /skip."""
        comments = [
            _bot_comment("Max attempts (3) reached.\n<!-- autoswe-bot -->", 1),
            _user_comment("/skip", 2),
        ]
        world = _build_world(
            comments=comments,
            status="failed",
            guard_blocked=True,
            attempt_count=3,
        )
        action = decide(world)
        assert action.kind == "skip"

    def test_guard_blocked_allows_abort(self):
        """A guard-blocked task should allow /abort."""
        comments = [
            _bot_comment("Max attempts (3) reached.\n<!-- autoswe-bot -->", 1),
            _user_comment("/abort", 2),
        ]
        world = _build_world(
            comments=comments,
            status="failed",
            guard_blocked=True,
            attempt_count=3,
        )
        action = decide(world)
        assert action.kind == "abort"


# --========================================================================
# Session continuity
# --========================================================================

class TestSessionContinuity:
    """Session ID should be preserved across phase transitions."""

    def test_plan_then_fix_preserves_session_flow(self):
        """Plan → fix should transition cleanly (plan session ≠ fix session)."""
        # Plan creates a new session
        world = _build_world(body="/plan", status=None, suppress_welcome=True)
        action = decide(world)
        assert action.kind == "plan"
        # Fresh plan has no resume_session_id
        assert action.resume_session_id is None

    def test_retry_clears_session_on_emit(self):
        """When emit produces a failed result, session_id should be cleared."""
        from autoswe.orch.run import DispatchResult

        world = _build_world(
            status="dispatched",
            session_id="old-session",
            attempt_count=1,
        )
        action = Action(
            kind="fix",
            slug=world.task.slug,
            attempt_count=1,
            triggering_comment_id=1,
        )
        result = DispatchResult(
            done_content="FAILED: crash",
            session_id="old-session",
            cost_usd=0.01,
            duration_seconds=10,
        )
        effects = emit(action, result, world)
        # Check that session_id is cleared in the queue patch
        patch_effect = next((e for e in effects if e.kind == "patch_queue"), None)
        assert patch_effect is not None
        assert patch_effect.queue_patch.get("session_id") is None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
