"""Tests for the dispatch return-string → label mapping and related logic."""

from autoswe.orch.emit import _build_completion_comment
from autoswe.providers.factory import get_vcs
from autoswe.tracking.labels import _map_done_to_status, _verdict_field_to_status

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


def test_map_tests_failed():
    """Post-fix test gate red (Natedorr/testProject#20): non-terminal test_failed."""
    assert _map_done_to_label("TESTS_FAILED") == "autoswe:test_failed"
    detail = "suite failing (exit 1)\nFAILURES: tests/test_half.py::test_contract"
    assert _map_done_to_label(f"TESTS_FAILED\t{detail}\tabc1234") == "autoswe:test_failed"


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


# ---------------------------------------------------------------------------
# Review verdict gating — REVIEW_READY\t<text> maps by verdict
# ---------------------------------------------------------------------------

def test_map_review_lgtm_is_reviewed():
    body = "## Summary\n\nClean.\n\n## Verdict\n\n**LGTM**"
    assert _map_done_to_label(f"REVIEW_READY\t{body}") == "autoswe:reviewed"


def test_map_review_needs_changes_is_review_failed():
    body = "## Summary\n\nSome gaps.\n\n## Verdict\n\n**Needs changes** — see findings."
    assert _map_done_to_label(f"REVIEW_READY\t{body}") == "autoswe:review_failed"


def test_map_review_blocked_is_review_blocked():
    body = "## Summary\n\nBug.\n\n## Verdict\n\n**Blocked** — 1 CRITICAL finding."
    assert _map_done_to_label(f"REVIEW_READY\t{body}") == "autoswe:review_blocked"


def test_map_review_no_verdict_section_defaults_reviewed():
    """No ## Verdict section and no blocking tokens → reviewed (backward compat)."""
    body = "## Findings\n\nThe code has critical issues described below."
    assert _map_done_to_label(f"REVIEW_READY\t{body}") == "autoswe:reviewed"


def test_map_review_no_issues_found_is_reviewed():
    assert _map_done_to_label("REVIEW_READY\tLGTM, no issues found.") == "autoswe:reviewed"


def test_parse_review_verdict_ignores_body_tokens_outside_verdict():
    """'Blocked'/'Needs changes' in finding bodies must not gate when the
    Verdict section itself is LGTM."""
    from autoswe.tracking.labels import parse_review_verdict

    body = (
        "## Findings\n\n[MEDIUM] this would have blocked older clients.\n"
        "Needs changes were considered but rejected.\n\n"
        "## Verdict\n\n**LGTM**\n"
    )
    assert parse_review_verdict(body) == "reviewed"


def test_parse_review_verdict_blocked_beats_needs_changes():
    from autoswe.tracking.labels import parse_review_verdict

    body = "## Verdict\n\nBlocked. (Needs changes alone would not be enough.)"
    assert parse_review_verdict(body) == "review_blocked"


def test_map_random_string():
    assert _map_done_to_label("something random") == "autoswe:fixed"


# ---------------------------------------------------------------------------
# Structured verdict field — primary gate (issue #173 F-18)
# ---------------------------------------------------------------------------
# The reviewer's schema-validated ``verdict`` field is the primary gate. The
# markdown "## Verdict" regex is only the fallback when the field is absent.

def test_structured_verdict_blocked_gates_over_lgtm_text():
    """A blocking structured verdict gates even when the report text says LGTM.

    This is the core F-18 fix: previously only the text was read, so a report
    whose structured verdict was 'Blocked' but whose prose said LGTM would slip
    through to ``reviewed``. The structured field now wins.
    """
    body = "## Summary\n\nClean.\n\n## Verdict\n\n**LGTM**"
    assert _map_done_to_status(f"REVIEW_READY\t{body}", verdict="Blocked") == "review_blocked"


def test_structured_verdict_needs_changes_over_lgtm_text():
    body = "## Verdict\n\n**LGTM**"
    assert _map_done_to_status(f"REVIEW_READY\t{body}", verdict="needs changes") == "review_failed"


def test_structured_verdict_lgtm_maps_to_reviewed():
    assert _map_done_to_status("REVIEW_READY\twhatever", verdict="LGTM") == "reviewed"


def test_no_structured_verdict_falls_back_to_regex():
    """When verdict is None the markdown regex path is used (backward compat)."""
    body = "## Verdict\n\n**Blocked** — critical finding."
    assert _map_done_to_status(f"REVIEW_READY\t{body}", verdict=None) == "review_blocked"
    # Same body, but a structured LGTM verdict overrides the blocked text.
    assert _map_done_to_status(f"REVIEW_READY\t{body}", verdict="LGTM") == "reviewed"


def test_bare_review_ready_uses_structured_verdict():
    """A bare REVIEW_READY (no embedded text) still honours the structured field."""
    assert _map_done_to_status("REVIEW_READY", verdict="Blocked") == "review_blocked"
    # ...and without it, keeps the historical default.
    assert _map_done_to_status("REVIEW_READY", verdict=None) == "reviewed"


def test_verdict_field_to_status_is_conservative():
    """Unrecognised verdict values never block — they default to 'reviewed'."""
    assert _verdict_field_to_status("Blocked") == "review_blocked"
    assert _verdict_field_to_status("needs changes") == "review_failed"
    assert _verdict_field_to_status("LGTM") == "reviewed"
    assert _verdict_field_to_status("") == "reviewed"
    assert _verdict_field_to_status("sompletely unknown") == "reviewed"


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
        repo_cfg={"org": "my-org", "project": "my-project", "repo": "my-repo", "provider": "azure"},
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
        repo_cfg={"org": "my org", "project": "my project", "repo": "my#repo", "provider": "azure"},
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
# Provider URL construction — VCSProvider.commit_url / branch_url (issue #168)
# ---------------------------------------------------------------------------

def test_vcs_branch_url_azure_with_org_project_repo():
    """Azure with explicit org/project/repo keys."""
    url = get_vcs({
        "provider": "azure",
        "org": "my-org", "project": "my-project", "repo": "my-repo",
    }).branch_url("feature/branch")
    assert url == "https://dev.azure.com/my-org/my-project/_git/my-repo?version=GBfeature%2Fbranch"


def test_vcs_branch_url_azure_fallback_from_owner_repo():
    """Azure partition when only owner/repo are set (repos_cfg miss).

    This is the production path when build_repo_cfg's repos_cfg lookup misses.
    owner=org, repo="project/repo_name" → parsed into org/project/repo.
    """
    url = get_vcs({
        "owner": "my-org", "repo": "my-project/my-repo", "provider": "azure",
    }).branch_url("autoswe/issue-1")
    assert url == "https://dev.azure.com/my-org/my-project/_git/my-repo?version=GBautoswe%2Fissue-1"


def test_vcs_commit_url_github():
    url = get_vcs({
        "provider": "github", "owner": "alice", "repo": "demo",
    }).commit_url("abc1234")
    assert url == "https://github.com/alice/demo/commit/abc1234"


def test_vcs_commit_url_azure_with_org_project_repo():
    url = get_vcs({
        "provider": "azure",
        "org": "my-org", "project": "my-project", "repo": "my-repo",
    }).commit_url("abc1234")
    assert url == "https://dev.azure.com/my-org/my-project/_git/my-repo/commit/abc1234"


def test_vcs_commit_url_azure_fallback_from_owner_repo():
    """Azure commit URL partition when only owner/repo are set."""
    url = get_vcs({
        "owner": "my-org", "repo": "my-project/my-repo", "provider": "azure",
    }).commit_url("deadbeef")
    assert url == "https://dev.azure.com/my-org/my-project/_git/my-repo/commit/deadbeef"


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

def test_vcs_commit_url_azure_with_repo_id():
    """Azure commit URL uses repo UUID when repo_id is set (issue #52)."""
    url = get_vcs({
        "provider": "azure",
        "org": "natedorr", "project": "testProject",
        "repo": "testProject",
        "repo_id": "d512de06-9118-4a61-97f1-34938c662c41",
    }).commit_url("8a9a1bdb8d4ada31ba4c4b26d636a4dd3170d5a7")
    # UUID replaces repo display name in the _git/ path segment
    assert "_git/d512de06-9118-4a61-97f1-34938c662c41/commit/" in url
    assert url == "https://dev.azure.com/natedorr/testProject/_git/d512de06-9118-4a61-97f1-34938c662c41/commit/8a9a1bdb8d4ada31ba4c4b26d636a4dd3170d5a7"


def test_vcs_branch_url_azure_with_repo_id():
    """Azure branch URL uses repo UUID when repo_id is set (issue #52)."""
    url = get_vcs({
        "provider": "azure",
        "org": "natedorr", "project": "testProject",
        "repo": "testProject",
        "repo_id": "d512de06-9118-4a61-97f1-34938c662c41",
    }).branch_url("autoswe/issue-151")
    # UUID replaces repo display name in the _git/ path segment
    assert "_git/d512de06-9118-4a61-97f1-34938c662c41?version=" in url
    assert url == "https://dev.azure.com/natedorr/testProject/_git/d512de06-9118-4a61-97f1-34938c662c41?version=GBautoswe%2Fissue-151"


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
            "provider": "azure",
        },
    )
    assert "d512de06-9118-4a61-97f1-34938c662c41" in msg
    assert "github.com" not in msg.split("**Summary:**")[0]
