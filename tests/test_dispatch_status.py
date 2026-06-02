"""Tests for the dispatch return-string → label mapping and related logic."""

from autoswe.orch.emit import _build_branch_url, _build_commit_url, _build_completion_comment
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
    assert "[Commit](https://dev.azure.com/my-org/my-project/_git/my-repo/commit/abc1234)" in msg
    assert "[View branch](https://dev.azure.com/my-org/my-project/_git/my-repo?version=GBautoswe%2Fissue-5)" in msg
    assert "github.com" not in msg.split("**Summary:**")[0]


def test_build_completion_comment_azure_fallback_owner_repo():
    """Azure branch URL works when repo_cfg only has owner/repo (no org/project).

    This is the production path when repos_cfg lookup in build_repo_cfg misses
    the entry — only owner=org and repo="project/repo_name" are available.
    The helper falls back to parsing owner/repo into org/project/repo.
    """
    msg = _build_completion_comment(
        pending_command="/fix",
        done_content="DONE_SUMMARY\tFixed\tabc1234",
        task_owner="my-org", task_repo="my-project/my-repo", issue_num=5,
        plan_branch=None, provider="azure",
        cost_usd=None, duration_seconds=None, session_id=None,
        # Only owner/repo — no explicit org/project keys (simulates repos_cfg miss)
        repo_cfg={"owner": "my-org", "repo": "my-project/my-repo", "provider": "azure"},
    )
    assert "dev.azure.com/my-org/my-project/_git/my-repo?version=GBautoswe%2Fissue-5" in msg
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
    """GitHub with missing repo_cfg: both commit and branch fall back to plain text."""
    msg = _build_completion_comment(
        pending_command="/fix",
        done_content="DONE_SUMMARY\tFixed\tabc1234",
        task_owner="o", task_repo="r", issue_num=1,
        plan_branch=None, provider="github",
        cost_usd=None, duration_seconds=None, session_id=None,
        repo_cfg=None,
    )
    # Both commit and branch links fall back to plain text when repo_cfg is None
    assert "Commit: abc1234" in msg
    assert "[Commit]" not in msg
    assert "Branch: autoswe/issue-1" in msg
    assert "[View branch]" not in msg


# ---------------------------------------------------------------------------
# _build_branch_url — provider URL construction
# ---------------------------------------------------------------------------

def test_build_branch_url_azure_with_org_project_repo():
    """Direct test: Azure with explicit org/project/repo keys."""
    url = _build_branch_url("azure", {
        "org": "my-org", "project": "my-project", "repo": "my-repo",
    }, "feature/branch")
    assert url == "https://dev.azure.com/my-org/my-project/_git/my-repo?version=GBfeature%2Fbranch"


def test_build_branch_url_azure_fallback_from_owner_repo():
    """Direct test: Azure fallback when only owner/repo are set (repos_cfg miss).

    This is the production path when build_repo_cfg's repos_cfg lookup misses.
    owner=org, repo="project/repo_name" → parsed into org/project/repo.
    """
    url = _build_branch_url("azure", {
        "owner": "my-org", "repo": "my-project/my-repo", "provider": "azure",
    }, "autoswe/issue-1")
    assert url == "https://dev.azure.com/my-org/my-project/_git/my-repo?version=GBautoswe%2Fissue-1"


def test_build_branch_url_azure_no_fallback_returns_none():
    """When repo_cfg has no usable Azure keys, returns None."""
    assert _build_branch_url("azure", {"owner": "x"}, "branch") is None
    assert _build_branch_url("azure", {}, "branch") is None


# ---------------------------------------------------------------------------
# _build_commit_url — provider URL construction
# ---------------------------------------------------------------------------

def test_build_commit_url_github():
    url = _build_commit_url("github", {
        "owner": "alice", "repo": "demo",
    }, "abc1234")
    assert url == "https://github.com/alice/demo/commit/abc1234"


def test_build_commit_url_github_no_repo_cfg():
    assert _build_commit_url("github", None, "abc1234") is None


def test_build_commit_url_azure_with_org_project_repo():
    url = _build_commit_url("azure", {
        "org": "my-org", "project": "my-project", "repo": "my-repo",
    }, "abc1234")
    assert url == "https://dev.azure.com/my-org/my-project/_git/my-repo/commit/abc1234"


def test_build_commit_url_azure_fallback_from_owner_repo():
    """Azure commit URL fallback when only owner/repo are set."""
    url = _build_commit_url("azure", {
        "owner": "my-org", "repo": "my-project/my-repo", "provider": "azure",
    }, "deadbeef")
    assert url == "https://dev.azure.com/my-org/my-project/_git/my-repo/commit/deadbeef"


def test_build_commit_url_azure_no_fallback_returns_none():
    assert _build_commit_url("azure", {"owner": "x"}, "abc") is None
    assert _build_commit_url("azure", {}, "abc") is None
    assert _build_commit_url("azure", None, "abc") is None


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


# ---------------------------------------------------------------------------
# Azure repo_id (UUID) in URLs — issue #52
# ---------------------------------------------------------------------------

def test_build_commit_url_azure_with_repo_id():
    """Azure commit URL uses repo UUID when repo_id is set (issue #52)."""
    url = _build_commit_url("azure", {
        "org": "natedorr", "project": "testProject",
        "repo": "testProject",
        "repo_id": "d512de06-9118-4a61-97f1-34938c662c41",
    }, "8a9a1bdb8d4ada31ba4c4b26d636a4dd3170d5a7")
    # UUID replaces repo display name in the _git/ path segment
    assert "_git/d512de06-9118-4a61-97f1-34938c662c41/commit/" in url
    assert url == "https://dev.azure.com/natedorr/testProject/_git/d512de06-9118-4a61-97f1-34938c662c41/commit/8a9a1bdb8d4ada31ba4c4b26d636a4dd3170d5a7"


def test_build_branch_url_azure_with_repo_id():
    """Azure branch URL uses repo UUID when repo_id is set (issue #52)."""
    url = _build_branch_url("azure", {
        "org": "natedorr", "project": "testProject",
        "repo": "testProject",
        "repo_id": "d512de06-9118-4a61-97f1-34938c662c41",
    }, "autoswe/issue-151")
    # UUID replaces repo display name in the _git/ path segment
    assert "_git/d512de06-9118-4a61-97f1-34938c662c41?version=" in url
    assert url == "https://dev.azure.com/natedorr/testProject/_git/d512de06-9118-4a61-97f1-34938c662c41?version=GBautoswe%2Fissue-151"


def test_build_commit_url_azure_fallback_without_repo_id():
    """Azure commit URL falls back to display name when repo_id is absent."""
    url = _build_commit_url("azure", {
        "org": "my-org", "project": "my-project", "repo": "my-repo",
    }, "abc1234")
    assert url == "https://dev.azure.com/my-org/my-project/_git/my-repo/commit/abc1234"


def test_build_branch_url_azure_fallback_without_repo_id():
    """Azure branch URL falls back to display name when repo_id is absent."""
    url = _build_branch_url("azure", {
        "org": "my-org", "project": "my-project", "repo": "my-repo",
    }, "feature/branch")
    assert url == "https://dev.azure.com/my-org/my-project/_git/my-repo?version=GBfeature%2Fbranch"


def test_build_completion_comment_azure_with_repo_id():
    """Completion comment uses repo UUID in commit/branch URLs (issue #52)."""
    msg = _build_completion_comment(
        pending_command="/fix",
        done_content="DONE_SUMMARY\tFixed the bug\tabc1234",
        task_owner="natedorr", task_repo="testProject", issue_num=5,
        plan_branch=None, provider="azure",
        cost_usd=None, duration_seconds=None, session_id=None,
        repo_cfg={
            "org": "natedorr", "project": "testProject", "repo": "testProject",
            "repo_id": "d512de06-9118-4a61-97f1-34938c662c41",
        },
    )
    assert "d512de06-9118-4a61-97f1-34938c662c41" in msg
    assert "github.com" not in msg.split("**Summary:**")[0]
