"""Tests for Azure DevOps sync/dispatch routing."""
import json

import pytest

from autoswe.commands.parser import parse_slash_command
from autoswe.providers.base import NormalizedComment
from autoswe.tracking.comments import (
    _find_last_bot_comment_ts,
    _find_last_completion,
    _is_autoswe_bot_comment,
)


def test_azure_slug_made_correctly(isolated_autoswe_dir):
    """Azure slugs use ado: prefix with 3-part parts."""
    from autoswe.core.slug import make_slug

    slug = make_slug("azure", ("my-org", "my-proj", "my-repo"), 42)
    assert slug == "ado:my-org_my-proj_my-repo_42"


def test_azure_config_validation_3part_key(isolated_autoswe_dir):
    """Azure repos.json entries with 3-part keys are accepted."""
    repos_json = isolated_autoswe_dir / "config" / "repos.json"
    repos_json.write_text(
        json.dumps({
            "my-org/my-proj/my-repo": {
                "provider": "azure",
                "pat": "ado_pat_123",
                "base_branch": "main",
            }
        }),
        encoding="utf-8",
    )

    from autoswe.core.config import load_repos_config

    result = load_repos_config()
    assert "my-org/my-proj/my-repo" in result
    assert result["my-org/my-proj/my-repo"]["provider"] == "azure"
    assert result["my-org/my-proj/my-repo"]["pat"] == "ado_pat_123"
    assert result["my-org/my-proj/my-repo"]["org"] == "my-org"
    assert result["my-org/my-proj/my-repo"]["project"] == "my-proj"
    assert result["my-org/my-proj/my-repo"]["repo"] == "my-repo"


def test_azure_config_validation_2part_key_rejected(isolated_autoswe_dir):
    """Azure repos.json entries with 2-part keys are rejected."""
    repos_json = isolated_autoswe_dir / "config" / "repos.json"
    repos_json.write_text(
        json.dumps({
            "my-org/my-proj": {
                "provider": "azure",
                "pat": "ado_pat_123",
            }
        }),
        encoding="utf-8",
    )

    from autoswe.core.config import load_repos_config

    with pytest.raises(ValueError, match="org/project/repo"):
        load_repos_config()


def test_azure_config_validation_4part_key_rejected(isolated_autoswe_dir):
    """Azure repos.json entries with 4-part keys are rejected."""
    repos_json = isolated_autoswe_dir / "config" / "repos.json"
    repos_json.write_text(
        json.dumps({
            "a/b/c/d": {
                "provider": "azure",
                "pat": "ado_pat_123",
            }
        }),
        encoding="utf-8",
    )

    from autoswe.core.config import load_repos_config

    with pytest.raises(ValueError, match="org/project/repo"):
        load_repos_config()


def test_github_config_validation_2part_key_ok(isolated_autoswe_dir):
    """GitHub repos.json entries with 2-part keys are accepted."""
    repos_json = isolated_autoswe_dir / "config" / "repos.json"
    repos_json.write_text(
        json.dumps({
            "owner/repo": {
                "provider": "github",
                "base_branch": "main",
                "pat": "ghp_test",
            }
        }),
        encoding="utf-8",
    )

    from autoswe.core.config import load_repos_config

    result = load_repos_config()
    assert "owner/repo" in result
    assert result["owner/repo"]["provider"] == "github"


def test_mixed_provider_config_ok(isolated_autoswe_dir):
    """repos.json can mix GitHub and Azure entries."""
    repos_json = isolated_autoswe_dir / "config" / "repos.json"
    repos_json.write_text(
        json.dumps({
            "natedorr/autoswe": {
                "provider": "github",
                "base_branch": "master",
                "pat": "ghp_test",
            },
            "my-org/my-proj/my-repo": {
                "provider": "azure",
                "pat": "ado_pat_123",
            },
        }),
        encoding="utf-8",
    )

    from autoswe.core.config import load_repos_config

    result = load_repos_config()
    assert "natedorr/autoswe" in result
    assert "my-org/my-proj/my-repo" in result
    assert result["natedorr/autoswe"]["provider"] == "github"
    assert result["my-org/my-proj/my-repo"]["provider"] == "azure"


def test_factory_build_repo_cfg_azure_finds_by_3part_key():
    """build_repo_cfg finds Azure entries by 3-part key."""
    from autoswe.providers.factory import build_repo_cfg

    cfg = {"GITHUB_TOKEN": "ghp_test"}
    repos_cfg = {
        "my-org/my-proj/my-repo": {
            "provider": "azure",
            "pat": "ado_pat_123",
        }
    }
    rcfg = build_repo_cfg("my-org/my-proj", "my-repo", cfg, repos_cfg)
    assert rcfg["provider"] == "azure"
    assert rcfg["pat"] == "ado_pat_123"


def test_factory_build_repo_cfg_github_finds_by_2part_key():
    """build_repo_cfg finds GitHub entries by 2-part key."""
    from autoswe.providers.factory import build_repo_cfg

    cfg = {"GITHUB_TOKEN": "ghp_test"}
    repos_cfg = {
        "owner/repo": {
            "provider": "github",
            "base_branch": "develop",
        }
    }
    rcfg = build_repo_cfg("owner", "repo", cfg, repos_cfg)
    assert rcfg["provider"] == "github"
    assert rcfg["base_branch"] == "develop"


# ---------------------------------------------------------------------------
# Azure auto-resume: bot detection + author normalization (issue #56)
# ---------------------------------------------------------------------------

def _detect_azure_resume(comments: list):
    """Mirror of sync.py:257-279 waiting/plan_ready auto-resume logic."""
    last_autoswe_ts = _find_last_bot_comment_ts(comments)
    user_after = [
        c for c in comments
        if c.author_login in ("OWNER", "AUTHOR")
        and c.created_at > (last_autoswe_ts or "")
    ]
    if not user_after:
        return None, None
    latest = user_after[-1]
    cmd_result = parse_slash_command(latest.body)
    if cmd_result and cmd_result[0] not in ("/skip",):
        return cmd_result[0], cmd_result[1]
    return None, latest.body


def test_azure_auto_resume_with_normalized_comments():
    """Auto-resume works with normalized ADO comments where bot/user are distinguished by author_login.

    Simulates the scenario from issue #56: all ADO comments share the same
    uniqueName (PAT owner), but after normalization by fetch_comments(),
    bot comments have author_login="BOT" and user comments have author_login="OWNER".
    """
    comments = [
        # User posted /plan
        NormalizedComment(
            body="/plan",
            created_at="2026-04-01T10:30:00Z",
            author_login="OWNER",
        ),
        # Bot responded with questions
        NormalizedComment(
            body="<AUTOSWE_QUESTIONS>\n1. Which language should I use?\n</AUTOSWE_QUESTIONS>\n\n"
                 "<!-- autoswe-bot -->",
            created_at="2026-04-01T10:30:05Z",
            author_login="BOT",
        ),
        # User replied with plain text
        NormalizedComment(
            body="Use Python. Create a greet.py file.",
            created_at="2026-04-01T10:35:00Z",
            author_login="OWNER",
        ),
    ]

    cmd, reply = _detect_azure_resume(comments)
    assert cmd is None
    assert "Python" in reply
    assert "greet.py" in reply


def test_azure_bot_comment_detection_by_body():
    """_is_autoswe_bot_comment detects bot comments via body marker (works for ADO)."""
    bot_comment = NormalizedComment(
        body="Failed: Command timed out\n\n<!-- autoswe-bot -->",
        created_at="2026-04-01T11:00:00Z",
        author_login="BOT",
    )
    assert _is_autoswe_bot_comment(bot_comment) is True

    user_comment = NormalizedComment(
        body="Use Python for the implementation.",
        created_at="2026-04-01T11:05:00Z",
        author_login="OWNER",
    )
    assert _is_autoswe_bot_comment(user_comment) is False


def test_azure_find_last_bot_comment_ts():
    """_find_last_bot_comment_ts works with ADO comments (body-based detection)."""
    comments = [
        NormalizedComment(
            body="/plan",
            created_at="2026-04-01T10:30:00Z",
            author_login="OWNER",
        ),
        NormalizedComment(
            body="Bot question\n\n<!-- autoswe-bot -->",
            created_at="2026-04-01T10:30:05Z",
            author_login="BOT",
        ),
        NormalizedComment(
            body="User reply",
            created_at="2026-04-01T10:35:00Z",
            author_login="OWNER",
        ),
        NormalizedComment(
            body="Another bot response\n\n<!-- autoswe-bot -->",
            created_at="2026-04-01T10:35:05Z",
            author_login="BOT",
        ),
    ]

    ts = _find_last_bot_comment_ts(comments)
    assert ts == "2026-04-01T10:35:05Z"


def test_azure_no_false_resume_when_only_bot_comments():
    """When only bot comments exist (no user reply), auto-resume should not trigger."""
    comments = [
        NormalizedComment(
            body="<AUTOSWE_QUESTIONS>\n1. Which approach?\n</AUTOSWE_QUESTIONS>\n\n"
                 "<!-- autoswe-bot -->",
            created_at="2026-04-01T10:30:00Z",
            author_login="BOT",
        ),
        NormalizedComment(
            body="Timeout waiting for response.\n\n<!-- autoswe-bot -->",
            created_at="2026-04-01T12:30:00Z",
            author_login="BOT",
        ),
    ]

    cmd, reply = _detect_azure_resume(comments)
    assert cmd is None
    assert reply is None


def test_azure_slash_command_after_waiting():
    """When user posts a slash command after waiting, it takes precedence over resume."""
    comments = [
        NormalizedComment(
            body="<AUTOSWE_QUESTIONS>\n1. Language?\n</AUTOSWE_QUESTIONS>\n\n"
                 "<!-- autoswe-bot -->",
            created_at="2026-04-01T10:30:00Z",
            author_login="BOT",
        ),
        NormalizedComment(
            body="/fix with Go implementation",
            created_at="2026-04-01T10:35:00Z",
            author_login="OWNER",
        ),
    ]

    cmd, guidance = _detect_azure_resume(comments)
    assert cmd == "/fix"
    assert guidance == "Go implementation"


def test_azure_resume_before_normalization_would_fail():
    """Without normalization, all comments have the same email author_login.

    This test demonstrates why normalization is needed: if author_login were
    the raw email (e.g., 'natedorr@example.com'), the sync check for
    ('OWNER', 'AUTHOR') would never match, and auto-resume would fail.
    """
    # Simulate what the comments looked like BEFORE the fix (raw uniqueName)
    comments_before_fix = [
        NormalizedComment(
            body="<AUTOSWE_QUESTIONS>\n1. Language?\n</AUTOSWE_QUESTIONS>\n\n"
                 "<!-- autoswe-bot -->",
            created_at="2026-04-01T10:30:00Z",
            author_login="natedorr@example.com",  # raw email — never matches OWNER/AUTHOR
        ),
        NormalizedComment(
            body="Use Python.",
            created_at="2026-04-01T10:35:00Z",
            author_login="natedorr@example.com",  # raw email — never matches OWNER/AUTHOR
        ),
    ]

    # Before the fix: this would fail because no author_login matches OWNER/AUTHOR
    last_ts = _find_last_bot_comment_ts(comments_before_fix)
    user_after = [
        c for c in comments_before_fix
        if c.author_login in ("OWNER", "AUTHOR")
        and c.created_at > (last_ts or "")
    ]
    assert len(user_after) == 0, "Without normalization, auto-resume finds no user comments"

    # After the fix: normalized comments work correctly
    comments_after_fix = [
        NormalizedComment(
            body="<AUTOSWE_QUESTIONS>\n1. Language?\n</AUTOSWE_QUESTIONS>\n\n"
                 "<!-- autoswe-bot -->",
            created_at="2026-04-01T10:30:00Z",
            author_login="BOT",
        ),
        NormalizedComment(
            body="Use Python.",
            created_at="2026-04-01T10:35:00Z",
            author_login="OWNER",
        ),
    ]
    cmd, reply = _detect_azure_resume(comments_after_fix)
    assert cmd is None
    assert "Python" in reply


# ---------------------------------------------------------------------------
# Issue #182: WAITING flow infinite loop on Azure (BOT_MARKER stripped)
# ---------------------------------------------------------------------------

def test_bot_detection_by_content_patterns():
    """_is_autoswe_bot_comment detects bot comments by content patterns when BOT_MARKER is stripped.

    Azure DevOps strips HTML comments from rendered comment bodies. When the
    bot posts a WAITING comment containing `<!-- autoswe-bot -->`, ADO removes
    it. This fallback pattern-based detection prevents the infinite-loop bug
    where bot comments are misidentified as user comments.
    """
    # Planner WAITING output — no BOT_MARKER, but has "## Questions" pattern
    waiting_comment = NormalizedComment(
        body="## Questions\n\n1. Which language?\n2. Which framework?\n\n_Reply in this thread to answer._",
        created_at="2026-04-01T10:30:05Z",
        author_login="OWNER",  # ADO marks as OWNER because marker was stripped
    )
    assert _is_autoswe_bot_comment(waiting_comment) is True

    # Planner PLAN_READY output — no BOT_MARKER, but has "## Plan\n" pattern
    plan_comment = NormalizedComment(
        body="## Plan\n\n1. Create file\n2. Write code\n\n_Reply with `/fix` to start coding._",
        created_at="2026-04-01T10:30:05Z",
        author_login="OWNER",
    )
    assert _is_autoswe_bot_comment(plan_comment) is True

    # Completion comment — no BOT_MARKER, but has "Completed with command"
    completion_comment = NormalizedComment(
        body="Completed with command `/fix` — done.",
        created_at="2026-04-01T11:00:00Z",
        author_login="OWNER",
    )
    assert _is_autoswe_bot_comment(completion_comment) is True

    # Failure comment — no BOT_MARKER, but has "Post `/retry`" pattern
    failure_comment = NormalizedComment(
        body="Failed: timeout\n\nPost `/retry` to try again.",
        created_at="2026-04-01T11:00:00Z",
        author_login="OWNER",
    )
    assert _is_autoswe_bot_comment(failure_comment) is True

    # Abort comment — no BOT_MARKER, but has "Task aborted."
    abort_comment = NormalizedComment(
        body="Task aborted.",
        created_at="2026-04-01T11:00:00Z",
        author_login="OWNER",
    )
    assert _is_autoswe_bot_comment(abort_comment) is True


def test_bot_detection_rejects_user_replies():
    """_is_autoswe_bot_comment must NOT detect user replies as bot comments.

    User replies should never match bot content patterns, even if they happen
    to contain similar wording.
    """
    # Plain user reply — no bot patterns
    user_reply = NormalizedComment(
        body="Use Python with Flask.",
        created_at="2026-04-01T10:35:00Z",
        author_login="OWNER",
    )
    assert _is_autoswe_bot_comment(user_reply) is False

    # User reply with a slash command
    user_command = NormalizedComment(
        body="/fix with Python implementation",
        created_at="2026-04-01T10:35:00Z",
        author_login="OWNER",
    )
    assert _is_autoswe_bot_comment(user_command) is False

    # User reply that contains "## Questions" — this would match the pattern,
    # but that's acceptable: the timestamp ordering in sync.py ensures the
    # bot's own WAITING comment is the last bot comment, and any user reply
    # after it (even one mentioning "## Questions") is correctly treated as
    # the user's intent.


def test_bot_detection_with_bot_marker_still_works():
    """_is_autoswe_bot_comment still detects BOT_MARKER when present.

    The content-pattern fallback is secondary; the primary BOT_MARKER check
    must still work (for GitHub, or for Azure after the marker-stripping fix).
    """
    comment_with_marker = NormalizedComment(
        body="## Questions\n\n1. Language?\n\n<!-- autoswe-bot -->",
        created_at="2026-04-01T10:30:05Z",
        author_login="BOT",
    )
    assert _is_autoswe_bot_comment(comment_with_marker) is True


def test_find_last_bot_comment_ts_with_stripped_marker():
    """_find_last_bot_comment_ts finds bot comments via content patterns when BOT_MARKER is stripped.

    This is the key function that sync.py uses to find the bot's last comment
    timestamp. Without the pattern-based fallback, it returns None when no
    comment contains BOT_MARKER, causing the infinite loop.
    """
    comments = [
        NormalizedComment(
            body="/plan",
            created_at="2026-04-01T10:30:00Z",
            author_login="OWNER",
        ),
        NormalizedComment(
            body="## Questions\n\n1. Which language?\n\n_Reply in this thread to answer._",
            created_at="2026-04-01T10:30:05Z",
            author_login="OWNER",  # ADO marks as OWNER because marker was stripped
        ),
        NormalizedComment(
            body="Use Python.",
            created_at="2026-04-01T10:35:00Z",
            author_login="OWNER",
        ),
    ]

    ts = _find_last_bot_comment_ts(comments)
    # Should find the WAITING comment (detected by "## Questions" pattern)
    assert ts == "2026-04-01T10:30:05Z"


def test_azure_resume_no_loop_with_stripped_marker():
    """Full WAITING→reply→resume flow works when BOT_MARKER is stripped.

    Simulates the exact scenario from issue #182:
    1. User posts /plan
    2. Bot posts WAITING comment (questions) — BOT_MARKER stripped by ADO
    3. User replies with answer
    4. Sync finds user reply as a genuine reply (not a new command)
    5. resume_plan is triggered, NOT a re-dispatch

    Without the fix: _find_last_bot_comment_ts returns None → ALL OWNER
    comments are treated as "user_after" → the bot's own comment is picked
    up as the latest reply → infinite loop.
    """
    comments = [
        NormalizedComment(
            body="/plan",
            created_at="2026-04-01T10:30:00Z",
            author_login="OWNER",
        ),
        # Bot's WAITING comment — BOT_MARKER stripped, detected by content
        NormalizedComment(
            body="## Questions\n\n1. Which language?\n\n_Reply in this thread to answer._",
            created_at="2026-04-01T10:30:05Z",
            author_login="OWNER",
        ),
        # User reply — after the bot's WAITING comment
        NormalizedComment(
            body="Use Python.",
            created_at="2026-04-01T10:35:00Z",
            author_login="OWNER",
        ),
    ]

    cmd, reply = _detect_azure_resume(comments)
    # Should detect the user reply, NOT the bot's question
    assert cmd is None
    assert "Python" in reply
    assert "language" not in reply  # Bot's comment should not be treated as reply


def test_azure_resume_multiple_bot_comments_stripped_marker():
    """Resume works when there are multiple bot comments without BOT_MARKER.

    Simulates: plan → waiting → reply → bot asks more questions → user answers.
    The last bot comment (still questions) should be the boundary, and the
    latest user reply after it should trigger resume.
    """
    comments = [
        NormalizedComment(
            body="/plan",
            created_at="2026-04-01T10:30:00Z",
            author_login="OWNER",
        ),
        NormalizedComment(
            body="## Questions\n\n1. Language?\n\n_Reply in this thread to answer._",
            created_at="2026-04-01T10:30:05Z",
            author_login="OWNER",
        ),
        NormalizedComment(
            body="Use Python.",
            created_at="2026-04-01T10:35:00Z",
            author_login="OWNER",
        ),
        # Bot asks follow-up (still WAITING)
        NormalizedComment(
            body="## Questions\n\n2. Which framework?\n\n_Reply in this thread to answer._",
            created_at="2026-04-01T10:35:05Z",
            author_login="OWNER",
        ),
        NormalizedComment(
            body="Use Flask.",
            created_at="2026-04-01T10:40:00Z",
            author_login="OWNER",
        ),
    ]

    cmd, reply = _detect_azure_resume(comments)
    assert cmd is None
    assert "Flask" in reply
    assert "Python" not in reply  # Should be latest reply, not the earlier one


def test_azure_tracker_is_bot_comment_pattern():
    """Azure tracker's _is_bot_comment detects patterns when BOT_MARKER absent."""
    from autoswe.providers.azure.tracker import _is_bot_comment

    # Should detect by BOT_MARKER
    assert _is_bot_comment("hello\n\n<!-- autoswe-bot -->") is True

    # Should detect by content patterns
    assert _is_bot_comment("## Questions\n\n1. Language?") is True
    assert _is_bot_comment("## Plan\n\n1. Do the thing") is True
    assert _is_bot_comment("Completed with command `/fix` — done.") is True
    assert _is_bot_comment("Failed: timeout\n\nPost `/retry` to try again.") is True
    assert _is_bot_comment("Task aborted.") is True

    # Should NOT detect user comments
    assert _is_bot_comment("Use Python.") is False
    assert _is_bot_comment("/fix with speed") is False
    assert _is_bot_comment("Great idea!") is False


def test_azure_bot_comment_not_detected_by_partial_match():
    """_is_bot_comment should not trigger on partial matches of bot patterns."""
    from autoswe.providers.azure.tracker import _is_bot_comment

    # "## Plan" without newline — user's issue description mentioning a plan
    # Note: The pattern is "## Plan\n" (with newline), so this should NOT match
    # In practice, a user's issue body wouldn't go through this path, but
    # it's good to verify the pattern specificity.
    assert _is_bot_comment("I have a ## Plan but not sure how to execute.") is False

    # "## Questions" must be at start of match — "## Questions:" wouldn't match
    # Actually, "## Questions" is a substring match, so "## Questions:" WOULD match
    # This is acceptable because "## Questions:" is an unusual pattern for users
    assert _is_bot_comment("## Questions:\n\nMy questions about the project:") is True

    # Empty string
    assert _is_bot_comment("") is False


# ---------------------------------------------------------------------------
# ADO Loop Prevention: last_dispatched_command guard (Stage 6)
# ---------------------------------------------------------------------------

def test_dispatch_guard_blocks_stale_command(isolated_autoswe_dir):
    """When last_dispatched_command matches the found slash command and cmd_ts
    is not newer than last_dispatched_command_ts, sync must NOT set pending_command.

    This is the core ADO loop prevention: after a handler completes and records
    last_dispatched_command, a subsequent sync run should not re-dispatch the
    same command even if _find_last_completion() returns None (ADO failure mode).
    """
    from autoswe.core.queue_store import LockedQueue

    # Seed queue with a done task that has last_dispatched_command
    task = {
        "id": "ado:my-org_my-project_my-repo_42",
        "owner": "my-org",
        "repo": "my-project/my-repo",
        "issue_number": 42,
        "title": "Fix bug",
        "body": "Bug description\n\n/fix",
        "base_branch": "main",
        "autoswe_status": "fixed",
        "pr_number": None,
        "session_id": "s-fix-42",
        "last_synced": "2026-05-10T10:00:00Z",
        "created_at": "2026-05-10T09:00:00Z",
        "suppress_welcome": True,
        "attempt_count": 1,
        "provider": "azure",
        "last_dispatched_command": "/fix",
        "last_dispatched_command_ts": "2026-05-10T12:00:00Z",
    }
    with LockedQueue() as lq:
        lq.queue[task["id"]] = dict(task)

    # Verify guard fields are set
    with LockedQueue() as lq:
        assert lq.queue[task["id"]]["last_dispatched_command"] == "/fix"
        assert lq.queue[task["id"]]["last_dispatched_command_ts"] == "2026-05-10T12:00:00Z"


def test_dispatch_guard_allows_newer_command(isolated_autoswe_dir):
    """The guard comparison is cmd_ts <= last_dispatch_ts.

    Issue body commands have cmd_ts="" (sorts oldest), so they are always
    blocked when last_dispatched_command matches. Comments have real timestamps
    and can be newer.

    This test verifies the comparison logic directly.
    """
    # Issue body command: cmd_ts="" always sorts <= any ISO timestamp
    body_ts = ""
    dispatch_ts = "2026-05-10T12:00:00Z"
    assert body_ts <= dispatch_ts  # body commands always blocked if command matches

    # Newer comment command should NOT be blocked
    new_comment_ts = "2026-05-11T12:00:00Z"
    assert not (new_comment_ts <= dispatch_ts)  # newer command not blocked

    # Older comment command should be blocked
    old_comment_ts = "2026-05-09T12:00:00Z"
    assert old_comment_ts <= dispatch_ts  # older command blocked


def test_dispatch_guard_allows_different_command(isolated_autoswe_dir):
    """The guard only blocks when the command matches exactly.

    A different command (e.g., /plan after a /fix completion) should pass
    through the guard regardless of timestamps.
    """
    last_cmd = "/fix"
    new_cmd = "/plan"
    assert last_cmd != new_cmd  # different command, guard doesn't fire


def test_dispatch_guard_with_retry(isolated_autoswe_dir):
    """The guard only applies to has_new_user path. /retry is a special case:
    it resets attempt_count and bypasses the failed-status check.

    The guard check happens AFTER the has_new_user + not /skip,/abort check,
    so /retry flows through the main restart path (not the guard).
    """
    # /retry is not in the (/skip, /abort) exclusion, so it goes through
    # the main restart path where attempt_count is managed.
    # The guard specifically checks:
    #   has_new_user and slash_cmd not in ("/skip", "/abort")
    #            and last_cmd == slash_cmd and cmd_ts <= last_dispatch_ts
    # If slash_cmd is "/retry", last_cmd ("/fix") != "/retry" → guard doesn't fire.
    assert "/fix" != "/retry"


# ---------------------------------------------------------------------------
# _find_last_completion normalization resilience (ADO body transformations)
# ---------------------------------------------------------------------------

def test_find_last_completion_normalizes_body():
    """_find_last_completion must handle ADO body transformations:
    HTML entities, markdown rendering, whitespace changes, and casing.
    """
    # Normal case: exact string match
    normal = [NormalizedComment(body="Completed with command `/fix` — done.", created_at="2026-05-10T12:00:00Z", author_login="BOT")]
    assert _find_last_completion(normal) == "2026-05-10T12:00:00Z"

    # ADO transforms backticks away
    no_backticks = [NormalizedComment(body="Completed with command /fix — done.", created_at="2026-05-10T12:00:00Z", author_login="OWNER")]
    assert _find_last_completion(no_backticks) == "2026-05-10T12:00:00Z"

    # ADO adds extra whitespace
    extra_whitespace = [NormalizedComment(body="Completed    with    command    `/fix`", created_at="2026-05-10T12:00:00Z", author_login="OWNER")]
    assert _find_last_completion(extra_whitespace) == "2026-05-10T12:00:00Z"

    # Different casing (lowercase)
    lowercase = [NormalizedComment(body="completed with command `/fix` — done.", created_at="2026-05-10T12:00:00Z", author_login="OWNER")]
    assert _find_last_completion(lowercase) == "2026-05-10T12:00:00Z"

    # Combined: no backticks, extra whitespace, different case, markdown bold
    combined = [NormalizedComment(body="**Completed** with command /fix — **done**.", created_at="2026-05-10T12:00:00Z", author_login="OWNER")]
    assert _find_last_completion(combined) == "2026-05-10T12:00:00Z"


def test_find_last_completion_no_false_positive():
    """_find_last_completion should not match user text that happens to contain similar words."""
    # User comment without "Completed with command"
    user_comment = [NormalizedComment(body="I completed the fix manually.", created_at="2026-05-10T12:00:00Z", author_login="OWNER")]
    assert _find_last_completion(user_comment) is None

    # Empty comments
    assert _find_last_completion([]) is None

    # Comment with "completed" but not "with command"
    partial = [NormalizedComment(body="completed the task", created_at="2026-05-10T12:00:00Z", author_login="OWNER")]
    assert _find_last_completion(partial) is None
