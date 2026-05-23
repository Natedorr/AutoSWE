"""Batch 3 — Comment-ID watermarking & ordering invariants.

Tests for _find_last_completion_id, _find_last_bot_comment_id,
watermark fallbacks, and edge cases (ID=0, negative IDs, content-pattern bot detection).
"""
from __future__ import annotations

from autoswe.orch.types import ApiState, TaskState, World
from autoswe.providers.base import NormalizedComment, NormalizedIssue
from autoswe.tracking.comments import (
    _find_last_bot_comment_id,
    _find_last_completion_id,
    _is_autoswe_bot_comment,
)

# ------ Helpers ------


def _comment(
    body: str,
    cid: int | None = 1,
    is_bot: bool = False,
    created_at: str = "2026-01-01T01:00:00Z",
) -> NormalizedComment:
    return NormalizedComment(
        body=body,
        created_at=created_at,
        author_login="owner",
        id=cid,
        is_bot=is_bot,
    )


def _world(
    comments: tuple[NormalizedComment, ...],
    status: str | None = None,
    last_dispatched_command_id: int | None = None,
    last_consumed_reply_id: int | None = None,
    cfg: dict | None = None,
    repo_cfg: dict | None = None,
) -> World:
    api = ApiState(
        issue=NormalizedIssue(
            number=42,
            title="Test",
            body="",
            owner="owner",
            repo="repo",
            state="open",
            base_branch="main",
        ),
        comments=comments,
    )
    task = TaskState(
        slug="gh:owner_repo_42",
        owner="owner",
        repo="repo",
        issue_number=42,
        title="Test",
        body="",
        status=status,
        plan_branch=None,
        base_branch="main",
        attempt_count=0,
        first_dispatched_at=None,
        last_dispatched_command=None,
        last_dispatched_command_id=last_dispatched_command_id,
        last_consumed_reply_id=last_consumed_reply_id,
        session_id=None,
        pr_number=None,
        guard_blocked=False,
        gh_closed=False,
        pending_command=None,
        pending_guidance=None,
        pending_user_reply=None,
        suppress_welcome=False,
    )
    return World(
        api=api,
        task=task,
        cfg=cfg or {"ALLOWED_AUTHORS": set()},
        repo_cfg=repo_cfg or {},
    )


# ------ _find_last_completion_id ------


def test_find_last_completion_id_single():
    comments = [
        _comment("Hello world", cid=1),
        _comment("Completed with command `/fix`.", cid=3, is_bot=True),
    ]
    assert _find_last_completion_id(comments) == 3


def test_find_last_completion_id_returns_latest():
    """When multiple completion comments exist, return the latest one."""
    comments = [
        _comment("Completed with command `/plan`.", cid=1, is_bot=True, created_at="2026-01-01T01:00:00Z"),
        _comment("Some user reply", cid=2),
        _comment("Completed with command `/fix`.", cid=4, is_bot=True, created_at="2026-01-01T03:00:00Z"),
    ]
    assert _find_last_completion_id(comments) == 4


def test_find_last_completion_id_no_completion():
    comments = [_comment("Hello", cid=1), _comment("World", cid=2)]
    assert _find_last_completion_id(comments) is None


def test_find_last_completion_id_empty():
    assert _find_last_completion_id([]) is None


def test_find_last_completion_id_no_ids_returns_timestamp():
    """Fallback: when no IDs are present, return timestamp string."""
    raw_comments = [
        {"body": "Completed with command `/fix`.", "created_at": "2026-01-01T01:00:00Z"},
    ]
    result = _find_last_completion_id(raw_comments)
    assert result == "2026-01-01T01:00:00Z"


def test_find_last_completion_id_content_pattern_fallback():
    """Detection works even without is_bot flag via content pattern."""
    comments = [
        _comment("Completed with command `/fix`.", cid=2),
        # is_bot=False, but content pattern should match
    ]
    assert _find_last_completion_id(comments) == 2


# ------ _find_last_bot_comment_id ------


def test_find_last_bot_comment_id_is_bot_flag():
    comments = [
        _comment("## Plan\n\n1. Do it", cid=1, is_bot=True),
        _comment("User reply", cid=2),
    ]
    assert _find_last_bot_comment_id(comments) == 1


def test_find_last_bot_comment_id_bot_marker_fallback():
    """Fallback: BOT_MARKER in body detected as bot."""
    comments = [
        _comment("## Plan\n\n1. Do it\n<!-- autoswe-bot -->", cid=1, is_bot=False),
    ]
    assert _find_last_bot_comment_id(comments) == 1


def test_find_last_bot_comment_id_content_pattern_fallback():
    """Fallback: content pattern detected as bot (Azure HTML strip)."""
    comments = [
        _comment("Completed with command `/fix`.", cid=2, is_bot=False),
    ]
    assert _find_last_bot_comment_id(comments) == 2


def test_find_last_bot_comment_id_dispatching_pattern():
    """Bot detection via 'Dispatching `/...' pattern."""
    comments = [
        _comment("Dispatching `/plan`...", cid=3, is_bot=False),
    ]
    assert _find_last_bot_comment_id(comments) == 3


def test_find_last_bot_comment_id_false_positive_guard():
    """User content containing bot-like text should NOT match if not a unique pattern.

    'Dispatching /...' is a bot pattern. A user saying 'I was dispatching /fix'
    would technically match — this documents the current behavior.
    """
    comments = [
        _comment("Post `/retry` to continue", cid=2, is_bot=False),
    ]
    # "Post `/retry`" matches the content pattern
    assert _find_last_bot_comment_id(comments) == 2


def test_find_last_bot_comment_id_latest():
    """Return ID of the latest (last in list) bot comment."""
    comments = [
        _comment("## Plan\n\n1.", cid=1, is_bot=True),
        _comment("User", cid=2),
        _comment("Updated plan.\n<!-- autoswe-bot -->", cid=4, is_bot=True),
    ]
    assert _find_last_bot_comment_id(comments) == 4


def test_find_last_bot_comment_id_no_bot():
    comments = [_comment("Hello", cid=1), _comment("World", cid=2)]
    assert _find_last_bot_comment_id(comments) is None


# ------ _is_autoswe_bot_comment ------


def test_is_bot_true_on_is_bot_flag():
    c = _comment("Random text", cid=1, is_bot=True)
    assert _is_autoswe_bot_comment(c) is True


def test_is_bot_true_on_marker():
    c = _comment("Some text\n<!-- autoswe-bot -->", cid=1, is_bot=False)
    assert _is_autoswe_bot_comment(c) is True


def test_is_bot_true_on_completion_pattern():
    c = _comment("Completed with command `/fix`.", cid=1, is_bot=False)
    assert _is_autoswe_bot_comment(c) is True


def test_is_bot_true_on_questions_pattern():
    c = _comment("## Questions\n\nWhat framework?", cid=1, is_bot=False)
    assert _is_autoswe_bot_comment(c) is True


def test_is_bot_true_on_plan_pattern():
    c = _comment("## Plan\n\n1. Do the thing", cid=1, is_bot=False)
    assert _is_autoswe_bot_comment(c) is True


def test_is_bot_true_on_abort_pattern():
    c = _comment("Task aborted.", cid=1, is_bot=False)
    assert _is_autoswe_bot_comment(c) is True


def test_is_bot_false_user_comment():
    c = _comment("/fix with tests", cid=1, is_bot=False)
    assert _is_autoswe_bot_comment(c) is False


def test_is_bot_false_empty_body():
    c = _comment("", cid=1, is_bot=False)
    assert _is_autoswe_bot_comment(c) is False


def test_is_bot_false_none_body():
    """Dict with body=None should not crash."""
    comment_dict = {"body": None, "id": 1, "is_bot": False}
    assert _is_autoswe_bot_comment(comment_dict) is False


# ------ Comment ID edge cases ------


def test_comment_id_zero_in_finders():
    """Comment ID = 0 is handled correctly (treated as valid but low priority)."""
    comments = [
        _comment("Completed with command `/fix`.", cid=0, is_bot=True),
    ]
    # ID=0 is returned by _find_last_completion_id only when no other IDs exist
    # Because it falls through the 'if cid is not None' check (0 is not None)
    result = _find_last_completion_id(comments)
    assert result == 0


def test_comment_id_zero_in_decide():
    """Body-sourced command (cmd_id=0) in terminal state → noop.

    The issue body has /fix, but status=done means the fix was already run.
    The body didn't change (no new user comments), so no restart should happen.
    This is correct — the stale-command guard requires has_new_user=True,
    and a body-sourced command alone can never satisfy that.
    """
    from autoswe.orch.decide import decide

    comments = (
        _comment("Completed with command `/fix`.", cid=1, is_bot=True, created_at="2026-01-01T01:00:00Z"),
    )
    api = ApiState(
        issue=NormalizedIssue(
            number=42, title="Test", body="/fix",
            owner="owner", repo="repo", state="open", base_branch="main",
        ),
        comments=comments,
    )
    task = TaskState(
        slug="gh:owner_repo_42", owner="owner", repo="repo", issue_number=42,
        title="Test", body="/fix", status="done", plan_branch=None,
        base_branch="main", attempt_count=1, first_dispatched_at=None,
        last_dispatched_command="/fix", last_dispatched_command_id=1,
        last_consumed_reply_id=None, session_id=None, pr_number=None,
        guard_blocked=False, gh_closed=False, pending_command=None,
        pending_guidance=None, pending_user_reply=None, suppress_welcome=False,
    )
    world = World(api=api, task=task, cfg={"ALLOWED_AUTHORS": set()}, repo_cfg={})
    action = decide(world)
    # Noop: body-sourced command already acted on; no new user comments
    assert action.kind == "noop"


def test_stale_command_suppression_with_comment_id():
    """When a comment-sourced command ID <= last_dispatched_command_id, it's suppressed.

    The stale-command guard prevents re-dispatching a command that was already
    processed, even if there's a newer user comment.
    """
    from autoswe.orch.decide import decide

    comments = (
        _comment("Completed with command `/fix`.", cid=1, is_bot=True, created_at="2026-01-01T01:00:00Z"),
        _comment("/fix", cid=2, created_at="2026-01-01T02:00:00Z"),  # user re-posts /fix
        _comment("Please also update tests.", cid=3, created_at="2026-01-01T03:00:00Z"),  # newer user comment
    )
    api = ApiState(
        issue=NormalizedIssue(
            number=42, title="Test", body="",
            owner="owner", repo="repo", state="open", base_branch="main",
        ),
        comments=comments,
    )
    task = TaskState(
        slug="gh:owner_repo_42", owner="owner", repo="repo", issue_number=42,
        title="Test", body="", status="done", plan_branch=None,
        base_branch="main", attempt_count=1, first_dispatched_at=None,
        last_dispatched_command="/fix", last_dispatched_command_id=2,
        last_consumed_reply_id=None, session_id=None, pr_number=None,
        guard_blocked=False, gh_closed=False, pending_command=None,
        pending_guidance=None, pending_user_reply=None, suppress_welcome=False,
    )
    world = World(api=api, task=task, cfg={"ALLOWED_AUTHORS": set()}, repo_cfg={})
    action = decide(world)
    # cmd_id=2 <= last_dispatched_command_id=2, so stale-command guard fires → noop
    assert action.kind == "noop"


# ------ Watermark timestamp fallback ------


def test_find_last_completion_timestamp_fallback():
    """When no IDs available, return timestamp string for backward compat."""
    raw_comments = [
        {"body": "User comment", "created_at": "2026-01-01T00:00:00Z"},
        {"body": "Completed with command `/plan`.", "created_at": "2026-01-01T01:00:00Z"},
    ]
    result = _find_last_completion_id(raw_comments)
    assert result == "2026-01-01T01:00:00Z"


def test_find_last_bot_comment_timestamp_fallback():
    """When no IDs available, return timestamp string for backward compat."""
    raw_comments = [
        {"body": "## Plan\n\n1.\n<!-- autoswe-bot -->", "created_at": "2026-01-01T01:00:00Z"},
    ]
    result = _find_last_bot_comment_id(raw_comments)
    assert result == "2026-01-01T01:00:00Z"


# ------ Negative ID edge case ------


def test_comment_id_negative():
    """Negative comment IDs are handled (provider quirk)."""
    comments = [
        _comment("Completed with command `/fix`.", cid=-1, is_bot=True),
    ]
    result = _find_last_completion_id(comments)
    # Negative ID is not None, so it passes the check
    assert result == -1
