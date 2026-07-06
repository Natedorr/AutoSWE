"""Tests for autoswe.vcs.ship handler — PR creation return values."""

from unittest.mock import MagicMock, patch

import pytest

from autoswe.providers.base import PRResult
from autoswe.vcs.ship import _pr_ref


@pytest.fixture(autouse=True)
def _default_preflight_pass(monkeypatch):
    """Bypass the sync/CI preflight gate for tests that only assert PR content.

    Gate behavior itself is covered by TestOpenPrPreflightGate below.
    """
    monkeypatch.setattr("autoswe.vcs.ship.preflight_pr", lambda *a, **kw: (True, ""))


def make_task(pr_number=None):
    return {
        "id": "o_r_1",
        "owner": "o",
        "repo": "r",
        "issue_number": 1,
        "title": "Test issue",
        "body": "/fix",
        "base_branch": "main",
        "pr_number": pr_number,
        "_token": "ghp_fake",
    }


def _mock_vcs(pr_url=None, pr_num=None, raise_exc=None, existing_pr=None):
    """Build a mock VCS provider for open_pr tests."""
    mock = MagicMock()
    mock.find_existing_pr.return_value = existing_pr
    if raise_exc is not None:
        mock.open_pull_request.side_effect = raise_exc
    else:
        mock.open_pull_request.return_value = PRResult(
            url=pr_url or f"https://github.com/o/r/pull/{pr_num or 42}",
            number=pr_num,
        )
    return mock


def _mock_tracker(post_raise=None):
    """Build a mock IssueTracker for open_pr tests."""
    mock = MagicMock()
    if post_raise is not None:
        mock.post_comment.side_effect = post_raise
    return mock


# ---------------------------------------------------------------------------
# open_pr — gh CLI path (via VCS provider)
# ---------------------------------------------------------------------------

def test_open_pr_vcs_success(mock_gh_post_comment):
    """VCS provider opens PR → returns DONE with PR URL."""
    task = make_task()

    with patch("autoswe.vcs.ship.get_vcs") as mock_get_vcs, \
         patch("autoswe.vcs.ship.get_tracker") as mock_get_tracker:
        mock_get_vcs.return_value = _mock_vcs(pr_url="https://github.com/o/r/pull/42")
        mock_get_tracker.return_value = _mock_tracker()

        from autoswe.vcs.ship import open_pr
        result = open_pr(task, {"GITHUB_TOKEN": "tok"})

    assert result.startswith("DONE: PR")
    assert "github.com/o/r/pull/42" in result
    # Comment was posted via tracker, not gh_post_comment directly
    mock_get_tracker.return_value.post_comment.assert_called_once()


def test_open_pr_api_fallback_success(mock_gh_post_comment):
    """VCS provider API fallback creates PR → returns DONE with number."""
    task = make_task()

    with patch("autoswe.vcs.ship.get_vcs") as mock_get_vcs, \
         patch("autoswe.vcs.ship.get_tracker") as mock_get_tracker:
        mock_get_vcs.return_value = _mock_vcs(pr_url="#77", pr_num=77)
        mock_get_tracker.return_value = _mock_tracker()

        from autoswe.vcs.ship import open_pr
        result = open_pr(task, {"GITHUB_TOKEN": "tok"})

    assert result == "DONE: PR #77"


def test_open_pr_api_fallback_failure(mock_gh_post_comment):
    """VCS provider throws → returns FAILED."""
    task = make_task()

    with patch("autoswe.vcs.ship.get_vcs") as mock_get_vcs, \
         patch("autoswe.vcs.ship.get_tracker") as mock_get_tracker:
        mock_get_vcs.return_value = _mock_vcs(raise_exc=RuntimeError("API error"))
        mock_get_tracker.return_value = _mock_tracker()

        from autoswe.vcs.ship import open_pr
        result = open_pr(task, {"GITHUB_TOKEN": "tok"})

    assert result.startswith("FAILED:")
    assert "could not create PR" in result


# ---------------------------------------------------------------------------
# open_pr — PR body and title
# ---------------------------------------------------------------------------

def test_open_pr_uses_correct_branch_and_base(mock_gh_post_comment):
    """PR should use autoswe/issue-{N} branch and configured base_branch."""
    task = make_task()
    task["base_branch"] = "develop"

    with patch("autoswe.vcs.ship.get_vcs") as mock_get_vcs, \
         patch("autoswe.vcs.ship.get_tracker") as mock_get_tracker:
        mock_vcs = _mock_vcs()
        mock_get_vcs.return_value = mock_vcs
        mock_get_tracker.return_value = _mock_tracker()

        from autoswe.vcs.ship import open_pr
        open_pr(task, {"GITHUB_TOKEN": "tok"})

    call_kwargs = mock_vcs.open_pull_request.call_args
    assert call_kwargs[1]["branch"] == "autoswe/issue-1"
    assert call_kwargs[1]["base"] == "develop"


def test_open_pr_uses_plan_branch_over_base(mock_gh_post_comment):
    """plan_branch should override base_branch as PR target."""
    task = make_task()
    task["base_branch"] = "main"
    task["plan_branch"] = "feature-branch"

    with patch("autoswe.vcs.ship.get_vcs") as mock_get_vcs, \
         patch("autoswe.vcs.ship.get_tracker") as mock_get_tracker:
        mock_vcs = _mock_vcs()
        mock_get_vcs.return_value = mock_vcs
        mock_get_tracker.return_value = _mock_tracker()

        from autoswe.vcs.ship import open_pr
        open_pr(task, {"GITHUB_TOKEN": "tok"})

    call_kwargs = mock_vcs.open_pull_request.call_args
    assert call_kwargs[1]["base"] == "feature-branch"


def test_open_pr_comment_includes_footer(mock_gh_post_comment):
    """Completion comment should end with autoswe-bot footer."""
    task = make_task()

    with patch("autoswe.vcs.ship.get_vcs") as mock_get_vcs, \
         patch("autoswe.vcs.ship.get_tracker") as mock_get_tracker:
        mock_get_vcs.return_value = _mock_vcs()
        mock_get_tracker.return_value = _mock_tracker()

        from autoswe.vcs.ship import open_pr
        open_pr(task, {"GITHUB_TOKEN": "tok"})

    call_args = mock_get_tracker.return_value.post_comment.call_args
    body = call_args[0][2]
    assert "<!-- autoswe-bot -->" in body


# ---------------------------------------------------------------------------
# open_pr — idempotency (existing PR detection)
# ---------------------------------------------------------------------------

def test_open_pr_existing_pr_returns_done(mock_gh_post_comment):
    """find_existing_pr returns PR → open_pr returns DONE without creating."""
    task = make_task()
    existing = PRResult(
        url="https://github.com/o/r/pull/15",
        number=15,
    )

    with patch("autoswe.vcs.ship.get_vcs") as mock_get_vcs, \
         patch("autoswe.vcs.ship.get_tracker") as mock_get_tracker:
        mock_get_vcs.return_value = _mock_vcs(existing_pr=existing)
        mock_get_tracker.return_value = _mock_tracker()

        from autoswe.vcs.ship import open_pr
        result = open_pr(task, {"GITHUB_TOKEN": "tok"})

    assert result == "DONE: PR https://github.com/o/r/pull/15"
    # open_pull_request was NOT called — idempotent
    mock_get_vcs.return_value.open_pull_request.assert_not_called()
    # find_existing_pr WAS called
    mock_get_vcs.return_value.find_existing_pr.assert_called_once()
    # Comment posted about existing PR
    mock_get_tracker.return_value.post_comment.assert_called_once()
    comment_body = mock_get_tracker.return_value.post_comment.call_args[0][2]
    assert "Pull request already exists" in comment_body
    assert "pull/15" in comment_body


def test_open_pr_existing_pr_number_fallback(mock_gh_post_comment):
    """Existing PR with empty URL falls back to #number."""
    task = make_task()
    existing = PRResult(url="", number=99)

    with patch("autoswe.vcs.ship.get_vcs") as mock_get_vcs, \
         patch("autoswe.vcs.ship.get_tracker") as mock_get_tracker:
        mock_get_vcs.return_value = _mock_vcs(existing_pr=existing)
        mock_get_tracker.return_value = _mock_tracker()

        from autoswe.vcs.ship import open_pr
        result = open_pr(task, {"GITHUB_TOKEN": "tok"})

    assert result == "DONE: PR #99"
    mock_get_vcs.return_value.open_pull_request.assert_not_called()


def test_open_pr_no_existing_creates_new(mock_gh_post_comment):
    """find_existing_pr returns None → open_pr creates a new PR."""
    task = make_task()

    with patch("autoswe.vcs.ship.get_vcs") as mock_get_vcs, \
         patch("autoswe.vcs.ship.get_tracker") as mock_get_tracker:
        mock_get_vcs.return_value = _mock_vcs(
            pr_url="https://github.com/o/r/pull/42",
            existing_pr=None,
        )
        mock_get_tracker.return_value = _mock_tracker()

        from autoswe.vcs.ship import open_pr
        result = open_pr(task, {"GITHUB_TOKEN": "tok"})

    assert result == "DONE: PR https://github.com/o/r/pull/42"
    # find_existing_pr was called
    mock_get_vcs.return_value.find_existing_pr.assert_called_once()
    # open_pull_request was called because no PR existed
    mock_get_vcs.return_value.open_pull_request.assert_called_once()


# ---------------------------------------------------------------------------
# _pr_ref — PR URL redaction for safe log output
# ---------------------------------------------------------------------------

def test_pr_ref_github_url():
    """GitHub PR URL → PR#{number} without exposing repo path."""
    assert _pr_ref("https://github.com/owner/repo/pull/123") == "PR#123"


def test_pr_ref_azure_url():
    """Azure DevOps PR URL → PR#{number} without exposing org/project path."""
    assert _pr_ref("https://dev.azure.com/org/project/_git/repo/pullrequest/42") == "PR#42"


def test_pr_ref_hash_format():
    """Hash-prefixed number is normalized to PR# format (not returned as-is)."""
    assert _pr_ref("#99") == "PR#99"


def test_pr_ref_fallback_no_pattern():
    """URL without pull/pullrequest keyword falls back to last path segment."""
    assert _pr_ref("https://example.com/some/other/path/abc123") == "PR#abc123"


def test_pr_ref_empty_string():
    """Empty string is handled gracefully (reachable via existing.url or fallback)."""
    result = _pr_ref("")
    assert "PR" in result


def test_pr_ref_hash_none():
    """Hash-NONE string is handled gracefully (reachable when PRResult.number is None)."""
    result = _pr_ref("#None")
    assert result == "PR#None"


def test_pr_ref_empty_path():
    """URL with no path segments falls back to full URL."""
    result = _pr_ref("https://example.com")
    assert result.endswith("example.com")
    assert "#" in result


def test_pr_ref_does_not_leak_owner():
    """Redacted reference must not contain owner or repo name."""
    redacted = _pr_ref("https://github.com/internal-secret/repo/pull/7")
    assert "internal-secret" not in redacted
    assert "repo" not in redacted


def test_pr_ref_does_not_leak_azure_org():
    """Redacted reference must not contain Azure org or project name."""
    redacted = _pr_ref("https://dev.azure.com/my-org/my-proj/_git/repo/pullrequest/5")
    assert "my-org" not in redacted
    assert "my-proj" not in redacted
    assert "repo" not in redacted


def test_open_pr_log_redacted_url():
    """log() receives PR# reference, not full URL (security: avoid URL in logs)."""
    task = make_task()

    with patch("autoswe.vcs.ship.get_vcs") as mock_get_vcs, \
         patch("autoswe.vcs.ship.get_tracker") as mock_get_tracker, \
         patch("autoswe.vcs.ship.log") as mock_log:
        mock_get_vcs.return_value = _mock_vcs(
            pr_url="https://github.com/o/r/pull/42",
            existing_pr=None,
        )
        mock_get_tracker.return_value = _mock_tracker()

        from autoswe.vcs.ship import open_pr
        open_pr(task, {"GITHUB_TOKEN": "tok"})

    # log() received redacted PR reference
    log_call = mock_log.call_args[0][0]
    assert "PR#42" in log_call
    # Full URL should NOT appear in log
    assert "github.com" not in log_call
    assert "o/r/pull" not in log_call


def test_open_pr_existing_log_redacted():
    """Existing PR path also logs redacted reference."""
    task = make_task()
    existing = PRResult(
        url="https://github.com/o/r/pull/15",
        number=15,
    )

    with patch("autoswe.vcs.ship.get_vcs") as mock_get_vcs, \
         patch("autoswe.vcs.ship.get_tracker") as mock_get_tracker, \
         patch("autoswe.vcs.ship.log") as mock_log:
        mock_get_vcs.return_value = _mock_vcs(existing_pr=existing)
        mock_get_tracker.return_value = _mock_tracker()

        from autoswe.vcs.ship import open_pr
        open_pr(task, {"GITHUB_TOKEN": "tok"})

    log_call = mock_log.call_args[0][0]
    assert "PR#15" in log_call
    assert "github.com" not in log_call
    assert "o/r/pull" not in log_call


def test_open_pr_comment_includes_full_url():
    """User-facing comment still gets full URL for usability."""
    task = make_task()

    with patch("autoswe.vcs.ship.get_vcs") as mock_get_vcs, \
         patch("autoswe.vcs.ship.get_tracker") as mock_get_tracker:
        mock_get_vcs.return_value = _mock_vcs(
            pr_url="https://github.com/o/r/pull/42",
            existing_pr=None,
        )
        mock_get_tracker.return_value = _mock_tracker()

        from autoswe.vcs.ship import open_pr
        open_pr(task, {"GITHUB_TOKEN": "tok"})

    comment_body = mock_get_tracker.return_value.post_comment.call_args[0][2]
    assert "https://github.com/o/r/pull/42" in comment_body


# ---------------------------------------------------------------------------
# open_pr — rich PR body (issue #43)
# ---------------------------------------------------------------------------

def test_open_pr_rich_body_includes_issue_and_summary(mock_gh_post_comment):
    """PR body should include issue body and fix_summary when available."""
    task = make_task()
    task["body"] = "Something is broken and needs fixing"
    task["fix_summary"] = "Fixed the bug by updating the logic in module.py"

    with patch("autoswe.vcs.ship.get_vcs") as mock_get_vcs, \
         patch("autoswe.vcs.ship.get_tracker") as mock_get_tracker:
        mock_vcs = _mock_vcs()
        mock_get_vcs.return_value = mock_vcs
        mock_get_tracker.return_value = _mock_tracker()

        from autoswe.vcs.ship import open_pr
        open_pr(task, {"GITHUB_TOKEN": "tok"})

    call_kwargs = mock_vcs.open_pull_request.call_args
    pr_body = call_kwargs[1]["body"]
    assert "Fixes #1" in pr_body
    assert "**Issue:**" in pr_body
    assert "Something is broken and needs fixing" in pr_body
    assert "**Fix Summary:**" in pr_body
    assert "Fixed the bug by updating the logic in module.py" in pr_body
    assert "Opened by autoSWE." in pr_body


def test_open_pr_body_without_summary(mock_gh_post_comment):
    """PR body should include issue body even when fix_summary is absent."""
    task = make_task()
    task["body"] = "Missing feature X"

    with patch("autoswe.vcs.ship.get_vcs") as mock_get_vcs, \
         patch("autoswe.vcs.ship.get_tracker") as mock_get_tracker:
        mock_vcs = _mock_vcs()
        mock_get_vcs.return_value = mock_vcs
        mock_get_tracker.return_value = _mock_tracker()

        from autoswe.vcs.ship import open_pr
        open_pr(task, {"GITHUB_TOKEN": "tok"})

    call_kwargs = mock_vcs.open_pull_request.call_args
    pr_body = call_kwargs[1]["body"]
    assert "Fixes #1" in pr_body
    assert "**Issue:**" in pr_body
    assert "Missing feature X" in pr_body
    assert "**Fix Summary:**" not in pr_body
    assert "Opened by autoSWE." in pr_body


def test_open_pr_body_minimal_when_no_issue_body(mock_gh_post_comment):
    """PR body gracefully handles empty issue body and no fix_summary."""
    task = make_task()
    task["body"] = ""
    task["fix_summary"] = ""

    with patch("autoswe.vcs.ship.get_vcs") as mock_get_vcs, \
         patch("autoswe.vcs.ship.get_tracker") as mock_get_tracker:
        mock_vcs = _mock_vcs()
        mock_get_vcs.return_value = mock_vcs
        mock_get_tracker.return_value = _mock_tracker()

        from autoswe.vcs.ship import open_pr
        open_pr(task, {"GITHUB_TOKEN": "tok"})

    call_kwargs = mock_vcs.open_pull_request.call_args
    pr_body = call_kwargs[1]["body"]
    assert "Fixes #1" in pr_body
    assert "**Issue:**" not in pr_body
    assert "**Fix Summary:**" not in pr_body
    assert "Opened by autoSWE." in pr_body


# ---------------------------------------------------------------------------
# open_pr — preflight gate (branch sync + CI status)
# ---------------------------------------------------------------------------

class TestOpenPrPreflightGate:
    """open_pr() must consult preflight_pr() before creating/finding a PR."""

    def test_blocked_by_preflight_returns_failed(self, monkeypatch, mock_gh_post_comment):
        """preflight_pr() returning not-ok short-circuits with FAILED, no PR lookup."""
        monkeypatch.setattr(
            "autoswe.vcs.ship.preflight_pr",
            lambda *a, **kw: (False, "CI failing: 1 check(s) failing: build"),
        )
        task = make_task()

        with patch("autoswe.vcs.ship.get_vcs") as mock_get_vcs, \
             patch("autoswe.vcs.ship.get_tracker") as mock_get_tracker:
            mock_vcs = _mock_vcs()
            mock_get_vcs.return_value = mock_vcs
            mock_get_tracker.return_value = _mock_tracker()

            from autoswe.vcs.ship import open_pr
            result = open_pr(task, {"GITHUB_TOKEN": "tok"})

        assert result == "FAILED: CI failing: 1 check(s) failing: build"
        mock_vcs.find_existing_pr.assert_not_called()
        mock_vcs.open_pull_request.assert_not_called()
        mock_get_tracker.return_value.post_comment.assert_not_called()

    def test_passing_preflight_proceeds_to_create_pr(self, monkeypatch, mock_gh_post_comment):
        """preflight_pr() returning ok lets open_pr proceed as normal."""
        monkeypatch.setattr("autoswe.vcs.ship.preflight_pr", lambda *a, **kw: (True, ""))
        task = make_task()

        with patch("autoswe.vcs.ship.get_vcs") as mock_get_vcs, \
             patch("autoswe.vcs.ship.get_tracker") as mock_get_tracker:
            mock_vcs = _mock_vcs(pr_url="https://github.com/o/r/pull/42", existing_pr=None)
            mock_get_vcs.return_value = mock_vcs
            mock_get_tracker.return_value = _mock_tracker()

            from autoswe.vcs.ship import open_pr
            result = open_pr(task, {"GITHUB_TOKEN": "tok"})

        assert result == "DONE: PR https://github.com/o/r/pull/42"
        mock_vcs.open_pull_request.assert_called_once()

    def test_preflight_called_with_task_cfg_repo_cfg_and_progress_callback(self, mock_gh_post_comment):
        """open_pr threads its cfg/repo_cfg/progress_callback into preflight_pr."""
        task = make_task()
        progress = MagicMock()
        captured = {}

        def fake_preflight(t, c, rc, *, progress_callback=None, **kw):
            captured["task"] = t
            captured["cfg"] = c
            captured["repo_cfg"] = rc
            captured["progress_callback"] = progress_callback
            return True, ""

        with patch("autoswe.vcs.ship.preflight_pr", fake_preflight), \
             patch("autoswe.vcs.ship.get_vcs") as mock_get_vcs, \
             patch("autoswe.vcs.ship.get_tracker") as mock_get_tracker:
            mock_get_vcs.return_value = _mock_vcs()
            mock_get_tracker.return_value = _mock_tracker()

            from autoswe.vcs.ship import open_pr
            open_pr(task, {"GITHUB_TOKEN": "tok"}, progress_callback=progress)

        assert captured["task"] is task
        assert captured["cfg"] == {"GITHUB_TOKEN": "tok"}
        assert captured["repo_cfg"]["owner"] == "o"
        assert captured["progress_callback"] is progress
