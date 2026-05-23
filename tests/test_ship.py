"""Tests for autoswe.vcs.ship handler — PR creation return values."""

from unittest.mock import MagicMock, patch

from autoswe.providers.base import PRResult


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
