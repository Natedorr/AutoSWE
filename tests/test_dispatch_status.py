"""Tests for the dispatch return-string → label mapping and related logic."""

from autoswe.orch.emit import _build_completion_comment
from autoswe.tracking.labels import _map_done_to_status

# ---------------------------------------------------------------------------
# Return-string → label mapping
# ---------------------------------------------------------------------------

def _map_done_to_label(done_content: str):
    """Wrap _map_done_to_status, converting status to full label."""
    status = _map_done_to_status(done_content)
    return f"autoswe:{status}" if status else None


def test_map_plan_ready():
    assert _map_done_to_label("PLAN_READY") == "autoswe:planned"


def test_map_waiting():
    assert _map_done_to_label("WAITING: questions") == "autoswe:waiting"
    assert _map_done_to_label("WAITING: see comment") == "autoswe:waiting"


def test_map_failed():
    assert _map_done_to_label("FAILED: timeout during fix phase") == "autoswe:failed"
    assert _map_done_to_label("FAILED:") == "autoswe:failed"


def test_map_done_bare():
    assert _map_done_to_label("DONE") == "autoswe:fixed"


def test_map_done_with_detail():
    assert _map_done_to_label("DONE: no changes detected") == "autoswe:fixed"
    assert _map_done_to_label("DONE: worktree clean") == "autoswe:fixed"


def test_map_skipped():
    assert _map_done_to_label("SKIPPED") == "autoswe:skipped"


def test_map_aborted():
    assert _map_done_to_label("ABORTED") == "autoswe:aborted"


def test_map_done_summary():
    """DONE_SUMMARY should map to autoswe:fixed (default kind=fix)."""
    assert _map_done_to_label("DONE_SUMMARY\tsummary\tabc1234") == "autoswe:fixed"


def test_map_done_with_newline():
    assert _map_done_to_label("DONE\n") == "autoswe:fixed"


def test_map_waiting_with_no_reason():
    assert _map_done_to_label("WAITING: ") == "autoswe:waiting"


def test_map_failed_with_unicode():
    assert _map_done_to_label("FAILED: ƒśéźćźół") == "autoswe:failed"


def test_map_empty_string():
    assert _map_done_to_label("") == "autoswe:fixed"


def test_map_review_ready():
    assert _map_done_to_label("REVIEW_READY") == "autoswe:reviewed"


def test_map_random_string():
    assert _map_done_to_label("something random") == "autoswe:fixed"


# ---------------------------------------------------------------------------
# Completion comment content (pure-logic)
# ---------------------------------------------------------------------------

def test_completion_comment_for_done():
    pending_command = "/fix"
    done_content = "DONE: refactored the poller"
    suffix = done_content[5:].strip() if done_content.startswith("DONE:") else "done."
    msg = f"Completed with command `{pending_command}` — {suffix}"
    assert "Completed with command" in msg
    assert "/fix" in msg
    assert "refactored the poller" in msg


def test_completion_comment_bare_done():
    pending_command = "/plan"
    done_content = "DONE"
    suffix = done_content[5:].strip() if done_content.startswith("DONE:") else "done."
    msg = f"Completed with command `{pending_command}` — {suffix}"
    assert msg == "Completed with command `/plan` — done."


def test_failure_comment_content():
    done_content = "FAILED: timeout during fix phase"
    reason = done_content[7:].strip() if done_content.startswith("FAILED:") else done_content
    fail_msg = f"Failed: {reason}\n\nPost `/retry` to try again."
    assert "timeout during fix phase" in fail_msg
    assert "/retry" in fail_msg


def test_completion_comment_special_chars():
    pending_command = "/fix"
    done_content = 'DONE: added "quotes" and <brackets>'
    suffix = done_content[5:].strip() if done_content.startswith("DONE:") else "done."
    msg = f"Completed with command `{pending_command}` — {suffix}"
    assert "quotes" in msg
    assert "brackets" in msg


# ---------------------------------------------------------------------------
# _build_completion_comment (from emit.py)
# ---------------------------------------------------------------------------

def test_build_completion_comment_with_summary():
    msg = _build_completion_comment(
        pending_command="/fix",
        done_content="DONE_SUMMARY\tFixed the login bug\tabc1234",
        task_owner="alice", task_repo="demo", issue_num=42,
        plan_branch=None, provider="github",
        cost_usd=None, duration_seconds=None, session_id=None,
        repo_cfg={"owner": "alice", "repo": "demo"},
    )
    assert "Completed with command `/fix`" in msg
    assert "https://github.com/alice/demo/commit/abc1234" in msg
    assert "https://github.com/alice/demo/compare/autoswe/issue-42" in msg
    assert "Fixed the login bug" in msg
    assert "<!-- autoswe-bot -->" in msg


def test_build_completion_comment_fallback_for_bare_done():
    msg = _build_completion_comment(
        pending_command="/fix",
        done_content="DONE",
        task_owner="o", task_repo="r", issue_num=1,
        plan_branch=None, provider="github",
        cost_usd=None, duration_seconds=None, session_id=None,
    )
    assert "Completed with command `/fix` — done." in msg
    assert "<!-- autoswe-bot -->" in msg


def test_build_completion_comment_fallback_for_done_detail():
    msg = _build_completion_comment(
        pending_command="/fix",
        done_content="DONE: no changes detected",
        task_owner="o", task_repo="r", issue_num=1,
        plan_branch=None, provider="github",
        cost_usd=None, duration_seconds=None, session_id=None,
    )
    assert "Completed with command `/fix` — no changes detected" in msg


def test_build_completion_comment_truncates_long_summary():
    long_summary = "x" * 1500
    msg = _build_completion_comment(
        pending_command="/fix",
        done_content=f"DONE_SUMMARY\t{long_summary}\tabc1234",
        task_owner="o", task_repo="r", issue_num=1,
        plan_branch=None, provider="github",
        cost_usd=None, duration_seconds=None, session_id=None,
    )
    assert len(msg) < 2000
    assert "..." in msg


def test_build_completion_comment_multiline_summary():
    summary = "Fixed login\nAdded validation\nUpdated tests"
    msg = _build_completion_comment(
        pending_command="/fix",
        done_content=f"DONE_SUMMARY\t{summary}\tabc1234",
        task_owner="o", task_repo="r", issue_num=7,
        plan_branch=None, provider="github",
        cost_usd=None, duration_seconds=None, session_id=None,
    )
    assert "Fixed login" in msg
    assert "Added validation" in msg
    assert "Updated tests" in msg


def test_build_completion_comment_with_metrics():
    msg = _build_completion_comment(
        pending_command="/fix",
        done_content="DONE",
        task_owner="o", task_repo="r", issue_num=1,
        plan_branch=None, provider="github",
        cost_usd=0.42, duration_seconds=255, session_id="sess1",
    )
    assert "Cost: $0.42" in msg
    assert "Duration: 4m15s" in msg
    assert "Session: sess1" in msg


def test_build_completion_comment_azure_branch_url():
    msg = _build_completion_comment(
        pending_command="/fix",
        done_content="DONE_SUMMARY\tFixed the bug\tabc1234",
        task_owner="my-org", task_repo="my-project/my-repo", issue_num=5,
        plan_branch=None, provider="azure",
        cost_usd=None, duration_seconds=None, session_id=None,
        repo_cfg={"org": "my-org", "project": "my-project", "repo": "my-repo"},
    )
    assert "[View branch](https://dev.azure.com/my-org/my-project/_git/my-repo?version=GBautoswe%2Fissue-5)" in msg
    assert "github.com" not in msg.split("**Summary:**")[0]


def test_build_completion_comment_unknown_provider_fallback():
    msg = _build_completion_comment(
        pending_command="/fix",
        done_content="DONE_SUMMARY\tFixed\tabc1234",
        task_owner="o", task_repo="r", issue_num=1,
        plan_branch=None, provider="unknown",
        cost_usd=None, duration_seconds=None, session_id=None,
    )
    assert "Branch: autoswe/issue-1" in msg
    assert "[View branch]" not in msg


def test_build_completion_comment_azure_special_chars():
    msg = _build_completion_comment(
        pending_command="/fix",
        done_content="DONE_SUMMARY\tFixed\tabc1234",
        task_owner="my org", task_repo="my project/my#repo", issue_num=9,
        plan_branch=None, provider="azure",
        cost_usd=None, duration_seconds=None, session_id=None,
        repo_cfg={"org": "my org", "project": "my project", "repo": "my#repo"},
    )
    assert "dev.azure.com/my%20org/my%20project/_git/my%23repo" in msg
    # Branch name in query param is also URL-encoded
    assert "version=GBautoswe%2Fissue-9" in msg


def test_build_completion_comment_github_no_repo_cfg():
    """GitHub with missing repo_cfg: commit link still works (uses task_owner/repo),
    but branch link falls back to plain text."""
    msg = _build_completion_comment(
        pending_command="/fix",
        done_content="DONE_SUMMARY\tFixed\tabc1234",
        task_owner="o", task_repo="r", issue_num=1,
        plan_branch=None, provider="github",
        cost_usd=None, duration_seconds=None, session_id=None,
        repo_cfg=None,
    )
    # Commit link uses task_owner/task_repo directly (always available)
    assert "[Commit](https://github.com/o/r/commit/abc1234)" in msg
    # Branch link falls back to plain text when repo_cfg is None
    assert "Branch: autoswe/issue-1" in msg
    assert "[View branch]" not in msg


# ---------------------------------------------------------------------------
# /retry replay — find last substantive command
# ---------------------------------------------------------------------------

def _find_effective_command(comments: list):
    """Mirror of /retry logic."""
    from autoswe.commands.parser import parse_slash_command

    for c in reversed(comments):
        r = parse_slash_command(c.get("body", ""))
        if r and r[0] not in ("/retry", "/skip", "/abort"):
            return r
    return None


def test_retry_replays_last_fix():
    test_comments = [
        {"body": "/fix with logging improvements"},
        {"body": "Failed: timeout\n<!-- autoswe-bot -->"},
        {"body": "/retry"},
    ]
    result = _find_effective_command(test_comments)
    assert result is not None
    assert result[0] == "/fix"
    assert result[1] == "logging improvements"


def test_retry_replays_last_plan():
    test_comments = [
        {"body": "/plan"},
        {"body": "Failed: timeout\n<!-- autoswe-bot -->"},
        {"body": "/retry"},
    ]
    result = _find_effective_command(test_comments)
    assert result is not None
    assert result[0] == "/plan"


def test_retry_skips_retry_and_skip_commands():
    test_comments = [
        {"body": "/plan"},
        {"body": "/skip"},
        {"body": "/retry"},
    ]
    result = _find_effective_command(test_comments)
    assert result is not None
    assert result[0] == "/plan"


def test_retry_skips_abort_command():
    test_comments = [
        {"body": "/fix"},
        {"body": "/abort"},
        {"body": "/retry"},
    ]
    result = _find_effective_command(test_comments)
    assert result is not None
    assert result[0] == "/fix"


def test_retry_falls_back_to_fix_when_no_history():
    assert _find_effective_command([]) is None
    assert _find_effective_command([{"body": "/retry"}]) is None


# ---------------------------------------------------------------------------
# Bot content patterns
# ---------------------------------------------------------------------------

def test_bot_content_patterns_detect_sticky_dispatching():
    from autoswe.tracking.comments import _is_autoswe_bot_comment

    bodies = [
        "Dispatching `/plan`…",
        "Dispatching `/fix`…",
        "Resuming `plan` session…",
        "Resuming `fix` session…",
        "## Claude's response\n\nSome text here",
    ]
    for body in bodies:
        assert _is_autoswe_bot_comment({"body": body}) is True, f"Must detect: {body!r}"


def test_bot_content_patterns_ignore_user_text():
    from autoswe.tracking.comments import _is_autoswe_bot_comment

    bodies = [
        "Please use approach 2.",
        "I think we should fix this.",
        "/fix",
        "/plan",
        "Use Redis for the cache backend.",
    ]
    for body in bodies:
        assert _is_autoswe_bot_comment({"body": body}) is False, f"Must NOT detect: {body!r}"
