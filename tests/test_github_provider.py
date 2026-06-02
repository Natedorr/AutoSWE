"""Tests for autoswe.providers.github — every Protocol method end-to-end."""
import subprocess
from unittest.mock import MagicMock

import pytest

from autoswe.providers.github.tracker import GitHubTracker
from autoswe.providers.github.vcs import GitHubVCS
from tests.conftest import load_fixture

# ============================================================================
# GitHubTracker tests
# ============================================================================

class TestGitHubTracker:

    @pytest.fixture
    def tracker(self, fake_token, monkeypatch):
        repo_cfg = {
            "owner": "natedorr",
            "repo": "autoswe",
            "token": fake_token,
        }
        return GitHubTracker(repo_cfg)

    @pytest.fixture
    def tracker_with_github_token(self, fake_token, monkeypatch):
        repo_cfg = {
            "owner": "o",
            "repo": "r",
            "pat": fake_token,
        }
        return GitHubTracker(repo_cfg)

    def test_resolve_token_prefers_repo_token(self, fake_token, monkeypatch):
        tracker = GitHubTracker({"owner": "o", "repo": "r", "token": "ghp_repo"})
        assert tracker._token == "ghp_repo"

    def test_resolve_token_uses_pat(self, fake_token, monkeypatch):
        tracker = GitHubTracker({"owner": "o", "repo": "r", "pat": "ghp_pat"})
        assert tracker._token == "ghp_pat"

    def test_list_open_issues(self, tracker, fake_token, mock_gh_request, gh_route_table):
        raw = load_fixture("issues_list.json")
        gh_route_table[("GET", "/repos/natedorr/autoswe/issues?state=open")] = raw

        issues = tracker.list_open_issues({})

        assert len(issues) == len(raw)
        for issue in issues:
            assert isinstance(issue.number, int)
            assert isinstance(issue.title, str)
            assert isinstance(issue.owner, str)
            assert issue.owner == "natedorr"
            assert issue.repo == "autoswe"

    def test_fetch_issue(self, tracker, fake_token, mock_gh_request, gh_route_table):
        raw = load_fixture("issue_42.json")
        gh_route_table[("GET", "/repos/natedorr/autoswe/issues/42")] = raw

        issue = tracker.fetch_issue({}, 42)

        assert issue.number == 42
        assert issue.title == raw["title"]
        assert issue.status == "pending"  # fixture has autoswe:pending label

    def test_fetch_issue_with_autoswe_label(self, tracker, fake_token, mock_gh_request, gh_route_table):
        issue_data = load_fixture("issue_42.json")
        issue_data["labels"] = [{"name": "autoswe:fixed"}, {"name": "bug"}]
        gh_route_table[("GET", "/repos/natedorr/autoswe/issues/42")] = issue_data

        issue = tracker.fetch_issue({}, 42)

        assert issue.status == "fixed"
        assert "bug" in issue.labels
        assert "autoswe:fixed" in issue.labels

    def test_fetch_comments(self, tracker, fake_token, mock_gh_request, gh_route_table):
        raw = load_fixture("comments_list.json")
        gh_route_table[("GET", "/repos/natedorr/autoswe/issues/42/comments")] = raw
        gh_route_table[("GET", "/user")] = {"login": "Natedorr"}

        comments = tracker.fetch_comments({}, 42)

        assert len(comments) == len(raw)
        for c in comments:
            assert isinstance(c.body, str)
            assert isinstance(c.created_at, str)
            assert isinstance(c.author_login, str)

    def test_fetch_comments_on_empty_list(self, tracker, fake_token, mock_gh_request, gh_route_table):
        gh_route_table[("GET", "/repos/natedorr/autoswe/issues/1/comments")] = []
        comments = tracker.fetch_comments({}, 1)
        assert comments == []

    def test_fetch_comments_normalizes_bot_comments(self, tracker, fake_token, mock_gh_request, gh_route_table):
        """Bot comments (body contains BOT_MARKER) get author_login='BOT'."""
        raw = [
            {
                "user": {"login": "Natedorr"},
                "created_at": "2026-05-01T02:05:41Z",
                "body": "autoSWE picked up this issue.\n\n<!-- autoswe-bot -->",
            },
        ]
        gh_route_table[("GET", "/repos/natedorr/autoswe/issues/42/comments")] = raw
        gh_route_table[("GET", "/user")] = {"login": "Natedorr"}

        comments = tracker.fetch_comments({}, 42)

        assert len(comments) == 1
        assert comments[0].author_login == "BOT"
        assert comments[0].raw_author_login == "Natedorr"

    def test_fetch_comments_normalizes_owner(self, tracker, fake_token, mock_gh_request, gh_route_table):
        """Comments by the authenticated token owner get author_login='OWNER'."""
        raw = [
            {
                "user": {"login": "Natedorr"},
                "created_at": "2026-05-01T02:10:00Z",
                "body": "/fix with performance focus",
            },
        ]
        gh_route_table[("GET", "/repos/natedorr/autoswe/issues/42/comments")] = raw
        gh_route_table[("GET", "/user")] = {"login": "Natedorr"}

        comments = tracker.fetch_comments({}, 42)

        assert len(comments) == 1
        assert comments[0].author_login == "OWNER"
        assert comments[0].raw_author_login == "Natedorr"

    def test_fetch_comments_preserves_raw_login(self, tracker, fake_token, mock_gh_request, gh_route_table):
        """Comments by other users preserve the raw login value."""
        raw = [
            {
                "user": {"login": "some-contributor"},
                "created_at": "2026-05-01T02:15:00Z",
                "body": "I'll take a look at this",
            },
        ]
        gh_route_table[("GET", "/repos/natedorr/autoswe/issues/42/comments")] = raw
        gh_route_table[("GET", "/user")] = {"login": "Natedorr"}

        comments = tracker.fetch_comments({}, 42)

        assert len(comments) == 1
        assert comments[0].author_login == "some-contributor"
        assert comments[0].raw_author_login == "some-contributor"

    def test_fetch_comments_bot_marker_takes_precedence(self, tracker, fake_token, mock_gh_request, gh_route_table):
        """Bot marker takes precedence over owner match — BOT wins over OWNER."""
        raw = [
            {
                "user": {"login": "Natedorr"},
                "created_at": "2026-05-01T02:05:41Z",
                "body": "Completed with command `/fix`\n\n<!-- autoswe-bot -->",
            },
        ]
        gh_route_table[("GET", "/repos/natedorr/autoswe/issues/42/comments")] = raw
        gh_route_table[("GET", "/user")] = {"login": "Natedorr"}

        comments = tracker.fetch_comments({}, 42)

        assert len(comments) == 1
        assert comments[0].author_login == "BOT"

    def test_fetch_comments_auth_failure_fallback(self, tracker, fake_token, mock_gh_request, gh_route_table):
        """When authenticated_user fails, bot comments still detected; others keep raw login."""
        raw = [
            {
                "user": {"login": "Natedorr"},
                "created_at": "2026-05-01T02:05:41Z",
                "body": "User comment no bot marker",
            },
            {
                "user": {"login": "Natedorr"},
                "created_at": "2026-05-01T02:06:00Z",
                "body": "Bot response\n\n<!-- autoswe-bot -->",
            },
        ]
        gh_route_table[("GET", "/repos/natedorr/autoswe/issues/42/comments")] = raw
        # Do NOT register /user route → authenticated_user will fail

        comments = tracker.fetch_comments({}, 42)

        assert len(comments) == 2
        # Bot comment still detected via marker
        assert comments[1].author_login == "BOT"
        # User comment falls back to raw login when auth fails
        assert comments[0].author_login == "Natedorr"

    def test_fetch_comments_mixed_authors(self, tracker, fake_token, mock_gh_request, gh_route_table):
        """A realistic mix of bot, owner, and contributor comments."""
        raw = [
            {
                "user": {"login": "Natedorr"},
                "created_at": "2026-05-01T02:05:41Z",
                "body": "autoSWE picked up this issue.\n\n<!-- autoswe-bot -->",
            },
            {
                "user": {"login": "Natedorr"},
                "created_at": "2026-05-01T02:10:00Z",
                "body": "/fix with performance focus",
            },
            {
                "user": {"login": "some-contributor"},
                "created_at": "2026-05-01T02:15:00Z",
                "body": "Looking into this",
            },
            {
                "user": {"login": "Natedorr"},
                "created_at": "2026-05-01T02:20:00Z",
                "body": "Fixed!\n\n<!-- autoswe-bot -->",
            },
        ]
        gh_route_table[("GET", "/repos/natedorr/autoswe/issues/42/comments")] = raw
        gh_route_table[("GET", "/user")] = {"login": "Natedorr"}

        comments = tracker.fetch_comments({}, 42)

        assert len(comments) == 4
        assert comments[0].author_login == "BOT"        # bot comment by owner
        assert comments[0].raw_author_login == "Natedorr"
        assert comments[1].author_login == "OWNER"      # user comment by owner
        assert comments[1].raw_author_login == "Natedorr"
        assert comments[2].author_login == "some-contributor"  # other user
        assert comments[2].raw_author_login == "some-contributor"
        assert comments[3].author_login == "BOT"        # bot comment by owner
        assert comments[3].raw_author_login == "Natedorr"

    def test_post_comment(self, tracker, mock_gh_post_comment):
        tracker.post_comment({}, 42, "Hello from autoSWE" + "<!-- autoswe-bot -->")
        assert len(mock_gh_post_comment.posted) == 1
        assert mock_gh_post_comment.posted[0]["issue_number"] == 42

    def test_set_status_ensures_labels_first(self, tracker, fake_token, mock_gh_request, gh_route_table):
        gh_route_table[("GET", "/repos/natedorr/autoswe/labels")] = []
        gh_route_table[("POST", "/repos/natedorr/autoswe/labels")] = {}
        gh_route_table[("GET", "/repos/natedorr/autoswe/issues/42/labels")] = []
        put_calls = []

        def capture_put(method, path, token, body):
            put_calls.append(body)
            return {}

        gh_route_table[("PUT", "/repos/natedorr/autoswe/issues/42/labels")] = capture_put

        tracker.set_status({}, 42, "autoswe:pending")

        assert len(put_calls) == 1
        assert "autoswe:pending" in put_calls[0]["labels"]

    def test_set_status_ensures_labels_only_once(self, tracker, fake_token, mock_gh_request, gh_route_table):
        gh_route_table[("GET", "/repos/natedorr/autoswe/labels")] = [
            {"name": name} for name in {"autoswe:pending", "autoswe:planning", "autoswe:fixing",
                                         "autoswe:syncing", "autoswe:reviewing", "autoswe:shipping",
                                         "autoswe:planned", "autoswe:fixed", "autoswe:synced",
                                         "autoswe:shipped", "autoswe:reviewed",
                                         "autoswe:waiting", "autoswe:failed", "autoswe:skipped",
                                         "autoswe:aborted", "autoswe:error"}
        ]
        gh_route_table[("GET", "/repos/natedorr/autoswe/issues/42/labels")] = []
        gh_route_table[("PUT", "/repos/natedorr/autoswe/issues/42/labels")] = {}
        post_label_calls = []

        def capture_post_label(method, path, token, body):
            post_label_calls.append(body)
            return {}

        gh_route_table[("POST", "/repos/natedorr/autoswe/labels")] = capture_post_label

        tracker.set_status({}, 42, "autoswe:pending")
        tracker.set_status({}, 42, "autoswe:fixed")

        assert len(post_label_calls) == 0, "Labels were already ensured on first call"

    def test_get_status_from_issue_with_label(self, tracker, fake_token, mock_gh_request, gh_route_table):
        from autoswe.providers.base import NormalizedIssue
        issue = NormalizedIssue(
            number=1, title="t", body="b", owner="o", repo="r",
            labels=["autoswe:failed", "bug"],
        )
        assert tracker.get_status(issue) == "failed"

    def test_get_status_from_issue_without_autoswe_label(self, tracker, fake_token, mock_gh_request, gh_route_table):
        from autoswe.providers.base import NormalizedIssue
        issue = NormalizedIssue(
            number=1, title="t", body="b", owner="o", repo="r",
            labels=["bug", "enhancement"],
        )
        assert tracker.get_status(issue) is None

    def test_assign_to_user(self, tracker, fake_token, mock_gh_request, gh_route_table):
        gh_route_table[("GET", "/repos/natedorr/autoswe/issues/42")] = {"assignees": []}
        assign_calls = []

        def capture_assign(method, path, token, body):
            assign_calls.append(body)
            return {}

        gh_route_table[("POST", "/repos/natedorr/autoswe/issues/42/assignees")] = capture_assign

        tracker.assign_to_user({}, 42, login="testuser")
        assert len(assign_calls) == 1
        assert assign_calls[0]["assignees"] == ["testuser"]

    def test_authenticated_user(self, tracker, fake_token, mock_gh_request, gh_route_table):
        gh_route_table[("GET", "/user")] = {"login": "testuser"}
        assert tracker.authenticated_user({}) == "testuser"

    def test_tracker_token_uses_pat_key(self, tracker_with_github_token, fake_token):
        assert tracker_with_github_token._token == fake_token


# ============================================================================
# GitHubVCS tests
# ============================================================================

class TestGitHubVCS:

    @pytest.fixture
    def vcs(self, fake_token):
        repo_cfg = {
            "owner": "natedorr",
            "repo": "autoswe",
            "token": fake_token,
        }
        return GitHubVCS(repo_cfg)

    def test_clone_url(self, vcs):
        url = vcs.clone_url({})
        assert "x-access-token:" in url
        assert "natedorr/autoswe" in url
        assert url.endswith(".git")

    def test_branch_name(self, vcs):
        assert vcs.branch_name(42) == "autoswe/issue-42"
        assert vcs.branch_name(1) == "autoswe/issue-1"

    def test_find_existing_pr_not_found(self, vcs, monkeypatch):
        """find_existing_pr returns None when gh CLI finds no PRs."""
        def fake_subprocess_run(args, **kwargs):
            result = MagicMock()
            result.returncode = 0
            result.stdout = "[]"
            return result

        monkeypatch.setattr("autoswe.providers.github.vcs.subprocess.run", fake_subprocess_run)
        result = vcs.find_existing_pr({}, "autoswe/issue-42")
        assert result is None

    def test_find_existing_pr_found(self, vcs, monkeypatch):
        """find_existing_pr returns PRResult when gh CLI finds a PR."""
        def fake_subprocess_run(args, **kwargs):
            result = MagicMock()
            result.returncode = 0
            result.stdout = '[{"number": 15, "url": "https://github.com/natedorr/autoswe/pull/15"}]'
            return result

        monkeypatch.setattr("autoswe.providers.github.vcs.subprocess.run", fake_subprocess_run)
        result = vcs.find_existing_pr({}, "autoswe/issue-42")
        assert result is not None
        assert result.number == 15
        assert "pull/15" in result.url

    def test_find_existing_pr_gh_cli_missing(self, vcs, monkeypatch):
        """find_existing_pr returns None when gh CLI is not installed."""
        def fake_subprocess_run(args, **kwargs):
            raise FileNotFoundError("gh not found")

        monkeypatch.setattr("autoswe.providers.github.vcs.subprocess.run", fake_subprocess_run)
        result = vcs.find_existing_pr({}, "autoswe/issue-42")
        assert result is None

    def test_find_existing_pr_timeout(self, vcs, monkeypatch):
        """find_existing_pr returns None when gh CLI times out."""
        def fake_subprocess_run(args, **kwargs):
            raise subprocess.TimeoutExpired("gh", 30)

        monkeypatch.setattr("autoswe.providers.github.vcs.subprocess.run", fake_subprocess_run)
        result = vcs.find_existing_pr({}, "autoswe/issue-42")
        assert result is None

    def test_open_pr_uses_api_fallback(self, vcs, fake_token, mock_gh_request, gh_route_table):
        gh_route_table[("POST", "/repos/natedorr/autoswe/pulls")] = {
            "number": 15,
            "html_url": "https://github.com/natedorr/autoswe/pull/15",
        }
        result = vcs.open_pull_request(
            {}, "autoswe/issue-42", "master",
            "Fixes #42: title", "body",
        )
        assert result.number == 15
        assert "pull/15" in result.url

    def test_link_branch_to_issue_calls_check_runs_api(self, vcs, fake_token, mock_gh_request, gh_route_table):
        gh_route_table[("POST", "/repos/natedorr/autoswe/check-runs")] = {
            "id": 999,
            "name": "autoSWE Fix #42",
        }

        vcs.link_branch_to_issue(42, "abc1234", "autoswe/issue-42")

        assert len(mock_gh_request.calls) == 1
        call = mock_gh_request.calls[0]
        assert call["method"] == "POST"
        assert call["path"] == "/repos/natedorr/autoswe/check-runs"
        assert call["body"]["name"] == "autoSWE Fix #42"
        assert call["body"]["head_sha"] == "abc1234"
        assert call["body"]["status"] == "completed"
        assert call["body"]["conclusion"] == "success"

    def test_link_branch_to_issue_no_op_without_token(self):
        """link_branch_to_issue returns without calling API when token is empty."""
        repo_cfg = {
            "owner": "natedorr",
            "repo": "autoswe",
            "token": "",
        }
        vcs = GitHubVCS(repo_cfg)
        # Should not raise, should be a no-op
        vcs.link_branch_to_issue(42, "abc1234", "autoswe/issue-42")

    def test_link_branch_to_issue_fails_fast_on_403(self, vcs, monkeypatch):
        """link_branch_to_issue uses max_retries=1 so 403 raises immediately
        without sleeping (regression for #75: 1h hang on check-runs 403)."""
        call_kwargs = {}

        def capture_gh_post(path, token, body, max_retries=3, timeout=30):
            call_kwargs.update({
                "max_retries": max_retries,
                "timeout": timeout,
                "path": path,
            })
            raise RuntimeError("GitHub API /check-runs -> HTTP 403: forbidden")

        monkeypatch.setattr("autoswe.providers.github.vcs.gh_post", capture_gh_post)

        from autoswe.providers.github.vcs import MissingScopeError

        with pytest.raises(MissingScopeError, match="PAT missing"):
            vcs.link_branch_to_issue(42, "abc1234", "autoswe/issue-42")

        # Verify it uses fail-fast settings
        assert call_kwargs["max_retries"] == 1, "Should use max_retries=1 for best-effort call"
        assert call_kwargs["timeout"] == 5, "Should use short timeout for best-effort call"
        assert "/check-runs" in call_kwargs["path"]

    def test_open_pr_api_returns_head_sha(self, vcs, fake_token, mock_gh_request, gh_route_table):
        """API fallback path extracts head.sha and includes it in PRResult."""
        gh_route_table[("POST", "/repos/natedorr/autoswe/pulls")] = {
            "number": 15,
            "html_url": "https://github.com/natedorr/autoswe/pull/15",
            "head": {"sha": "abcdef1234567890"},
        }
        result = vcs.open_pull_request(
            {}, "autoswe/issue-42", "master",
            "Fixes #42: title", "body",
        )
        assert result.number == 15
        assert result.head_sha == "abcdef1234567890"

    def test_link_branch_to_issue_recorded_in_fake(self, vcs, github_fake):
        """Using github_fake, verify check-runs POST is recorded with correct payload."""
        _, original = github_fake.patch()
        try:
            vcs.link_branch_to_issue(42, "abc1234", "autoswe/issue-42")
        finally:
            github_fake.unpatch(_, original)

        assert len(github_fake.check_runs) == 1
        cr = github_fake.check_runs[0]
        assert cr["name"] == "autoSWE Fix #42"
        assert cr["head_sha"] == "abc1234"
        assert cr["status"] == "completed"
        assert cr["conclusion"] == "success"
