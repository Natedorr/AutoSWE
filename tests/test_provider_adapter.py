"""Provider adapter tests — read_api normalization and apply_effect translation.

Tests the two adapter functions per provider. Each assertion is one property
of the read/write boundary:

  read_api (input shape lockdown)
    - azure_div_wrapped_comment_unwrapped  — Bug 1 regression
    - azure_html_entities_decoded           — &#45;&#45;branch → --branch
    - azure_bot_marker_preserved            — bot comments keep marker after strip
    - github_comment_passthrough            — GH comments arrive clean, stay clean

  apply_effect (output shape lockdown)
    - set_status_github → PUT /issues/N/labels
    - set_status_azure  → PATCH work item System.Tags
    - post_comment_github → POST /issues/N/comments
    - post_comment_azure  → POST /comments?format=Markdown
    - patch_queue → queue mutation
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from autoswe.orch.types import Effect
from autoswe.providers.base import NormalizedComment, NormalizedIssue, PRResult
from autoswe.tracking.comments import BOT_MARKER

# ---------------------------------------------------------------------------
# read_api — input shape lockdown
# ---------------------------------------------------------------------------

# Simulated raw comment body from Azure DevOps rich-text comment editor.
# ADO wraps the text in <div> tags when the user posts from the rich editor.
_AZURE_DIV_WRAPPED = "<div>/plan --branch dev</div>"

# Simulated comment with HTML entities (ADO rich-text encoding)
_AZURE_ENTITIES = "&#47;fix with &#45;&#45;focus"


def _make_issue(number: int, title: str = "Test issue") -> NormalizedIssue:
    return NormalizedIssue(
        number=number, title=title, body="Body",
        owner="natedorr", repo="testProject",
    )


class TestReadApiAzure:
    """Azure adapter read_api tests — comment body normalization."""

    def _make_tracker(self, comments: list[NormalizedComment]) -> MagicMock:
        t = MagicMock()
        t.list_open_issues.return_value = [_make_issue(42)]
        t.fetch_comments.return_value = comments
        return t

    def test_div_wrapped_comment_unwrapped(self):
        """Bug 1 regression: ADO rich-text wraps user comments in <div>.

        After read_api, the comment body should have the <div> stripped
        so slash-command parsing sees clean text.
        """
        comments = [NormalizedComment(body=_AZURE_DIV_WRAPPED, created_at="2026-01-01T00:00:00Z", author_login="AUTHOR")]
        tracker = self._make_tracker(comments)
        repo_cfg = {"provider": "azure", "org": "natedorr", "project": "testProject", "repo": "testProject", "pat": "fake"}

        with patch("autoswe.providers.azure.adapter.get_vcs"):
            from autoswe.providers.azure.adapter import read_api
            api_states = read_api(tracker, repo_cfg, {})

        body = api_states[42].comments[0].body
        assert "/plan --branch dev" in body
        assert "<div>" not in body

    def test_html_entities_decoded(self):
        """ADO rich-text may encode characters as HTML entities."""
        comments = [NormalizedComment(body=_AZURE_ENTITIES, created_at="2026-01-01T00:00:00Z", author_login="AUTHOR")]
        tracker = self._make_tracker(comments)
        repo_cfg = {"provider": "azure", "org": "natedorr", "project": "testProject", "repo": "testProject", "pat": "fake"}

        with patch("autoswe.providers.azure.adapter.get_vcs"):
            from autoswe.providers.azure.adapter import read_api
            api_states = read_api(tracker, repo_cfg, {})

        body = api_states[42].comments[0].body
        assert "/fix with --focus" in body
        assert "&#45;" not in body
        assert "&#47;" not in body

    def test_bot_marker_preserved(self):
        """Bot comments should keep the autoswe-bot marker after HTML strip."""
        bot_body = "<div>## Plan\n\nSome plan text\n</div>\n<!-- autoswe-bot -->"
        comments = [NormalizedComment(body=bot_body, created_at="2026-01-01T00:00:00Z", author_login="BOT")]
        tracker = self._make_tracker(comments)
        repo_cfg = {"provider": "azure", "org": "natedorr", "project": "testProject", "repo": "testProject", "pat": "fake"}

        with patch("autoswe.providers.azure.adapter.get_vcs"):
            from autoswe.providers.azure.adapter import read_api
            api_states = read_api(tracker, repo_cfg, {})

        body = api_states[42].comments[0].body
        assert BOT_MARKER in body
        assert "<div>" not in body

    def test_clean_comment_passthrough(self):
        """A comment that's already clean text should come out unchanged."""
        clean = "/plan --branch main"
        comments = [NormalizedComment(body=clean, created_at="2026-01-01T00:00:00Z", author_login="AUTHOR")]
        tracker = self._make_tracker(comments)
        repo_cfg = {"provider": "azure", "org": "natedorr", "project": "testProject", "repo": "testProject", "pat": "fake"}

        with patch("autoswe.providers.azure.adapter.get_vcs"):
            from autoswe.providers.azure.adapter import read_api
            api_states = read_api(tracker, repo_cfg, {})

        assert api_states[42].comments[0].body == clean

    def test_skip_unchanged_issue(self):
        """When prev_updated matches, comments should be skipped."""
        issue = NormalizedIssue(
            number=42, title="T", body="B",
            owner="o", repo="r",
            last_updated="2026-01-01T00:00:00Z",
        )
        t = MagicMock()
        t.list_open_issues.return_value = [issue]

        repo_cfg = {"provider": "azure", "org": "natedorr", "project": "testProject", "repo": "r", "pat": "fake"}

        with patch("autoswe.providers.azure.adapter.get_vcs"):
            from autoswe.providers.azure.adapter import read_api
            api_states = read_api(
                t, repo_cfg, {},
                prev_updated={42: "2026-01-01T00:00:00Z"},
            )

        assert api_states[42].comments_fetched is False
        assert api_states[42].comments == ()
        t.fetch_comments.assert_not_called()

    def test_fetch_when_timestamp_changed(self):
        """When prev_updated differs from issue.last_updated, fetch comments."""
        issue = NormalizedIssue(
            number=42, title="T", body="B",
            owner="o", repo="r",
            last_updated="2026-01-02T00:00:00Z",
        )
        t = MagicMock()
        t.list_open_issues.return_value = [issue]
        t.fetch_comments.return_value = []

        repo_cfg = {"provider": "azure", "org": "natedorr", "project": "testProject", "repo": "r", "pat": "fake"}

        with patch("autoswe.providers.azure.adapter.get_vcs"):
            from autoswe.providers.azure.adapter import read_api
            api_states = read_api(
                t, repo_cfg, {},
                prev_updated={42: "2026-01-01T00:00:00Z"},
            )

        assert api_states[42].comments_fetched is True
        t.fetch_comments.assert_called_once()

    def test_force_fetch_overrides_skip(self):
        """force_fetch set overrides a matching timestamp."""
        issue = NormalizedIssue(
            number=42, title="T", body="B",
            owner="o", repo="r",
            last_updated="2026-01-01T00:00:00Z",
        )
        t = MagicMock()
        t.list_open_issues.return_value = [issue]
        t.fetch_comments.return_value = []

        repo_cfg = {"provider": "azure", "org": "natedorr", "project": "testProject", "repo": "r", "pat": "fake"}

        with patch("autoswe.providers.azure.adapter.get_vcs"):
            from autoswe.providers.azure.adapter import read_api
            api_states = read_api(
                t, repo_cfg, {},
                prev_updated={42: "2026-01-01T00:00:00Z"},
                force_fetch={42},
            )

        assert api_states[42].comments_fetched is True
        t.fetch_comments.assert_called_once()

    def test_new_issue_always_fetched(self):
        """An issue not in prev_updated should always be fetched."""
        issue = NormalizedIssue(
            number=42, title="T", body="B",
            owner="o", repo="r",
            last_updated="2026-01-01T00:00:00Z",
        )
        t = MagicMock()
        t.list_open_issues.return_value = [issue]
        t.fetch_comments.return_value = []

        repo_cfg = {"provider": "azure", "org": "natedorr", "project": "testProject", "repo": "r", "pat": "fake"}

        with patch("autoswe.providers.azure.adapter.get_vcs"):
            from autoswe.providers.azure.adapter import read_api
            api_states = read_api(t, repo_cfg, {}, prev_updated={})

        assert api_states[42].comments_fetched is True
        t.fetch_comments.assert_called_once()

    def test_no_last_updated_always_fetched(self):
        """When issue has no last_updated, always fetch comments."""
        issue = NormalizedIssue(
            number=42, title="T", body="B",
            owner="o", repo="r",
            last_updated=None,
        )
        t = MagicMock()
        t.list_open_issues.return_value = [issue]
        t.fetch_comments.return_value = []

        repo_cfg = {"provider": "azure", "org": "natedorr", "project": "testProject", "repo": "r", "pat": "fake"}

        with patch("autoswe.providers.azure.adapter.get_vcs"):
            from autoswe.providers.azure.adapter import read_api
            api_states = read_api(
                t, repo_cfg, {},
                prev_updated={42: "2026-01-01T00:00:00Z"},
            )

        assert api_states[42].comments_fetched is True
        t.fetch_comments.assert_called_once()

    def test_backward_compat_no_prev_updated(self):
        """Without prev_updated param, all issues are fetched (backward compat)."""
        issue = NormalizedIssue(
            number=42, title="T", body="B",
            owner="o", repo="r",
            last_updated="2026-01-01T00:00:00Z",
        )
        t = MagicMock()
        t.list_open_issues.return_value = [issue]
        t.fetch_comments.return_value = []

        repo_cfg = {"provider": "azure", "org": "natedorr", "project": "testProject", "repo": "r", "pat": "fake"}

        with patch("autoswe.providers.azure.adapter.get_vcs"):
            from autoswe.providers.azure.adapter import read_api
            api_states = read_api(t, repo_cfg, {})

        assert api_states[42].comments_fetched is True
        t.fetch_comments.assert_called_once()


class TestReadApiGitHub:
    """GitHub adapter read_api tests — comments already clean."""

    def test_github_clean_passthrough(self):
        """GitHub comments are plain text; adapter should pass through."""
        t = MagicMock()
        issue = _make_issue(7, title="Test")
        t.list_open_issues.return_value = [issue]
        t.fetch_comments.return_value = [
            NormalizedComment(body="/plan --branch dev", created_at="2026-01-01T00:00:00Z", author_login="AUTHOR"),
        ]
        repo_cfg = {"provider": "github", "owner": "owner", "repo": "repo", "pat": "fake"}

        with patch("autoswe.providers.github.adapter.get_vcs"):
            from autoswe.providers.github.adapter import read_api
            api_states = read_api(t, repo_cfg, {})

        assert api_states[7].comments[0].body == "/plan --branch dev"

    def test_github_skip_unchanged_issue(self):
        """When prev_updated matches, GitHub adapter should skip fetching."""
        issue = NormalizedIssue(
            number=7, title="T", body="B",
            owner="o", repo="r",
            last_updated="2026-01-01T00:00:00Z",
        )
        t = MagicMock()
        t.list_open_issues.return_value = [issue]

        repo_cfg = {"provider": "github", "owner": "o", "repo": "r", "pat": "fake"}

        with patch("autoswe.providers.github.adapter.get_vcs"):
            from autoswe.providers.github.adapter import read_api
            api_states = read_api(
                t, repo_cfg, {},
                prev_updated={7: "2026-01-01T00:00:00Z"},
            )

        assert api_states[7].comments_fetched is False
        assert api_states[7].comments == ()
        t.fetch_comments.assert_not_called()

    def test_github_fetch_when_changed(self):
        """When timestamp changed, GitHub adapter should fetch."""
        issue = NormalizedIssue(
            number=7, title="T", body="B",
            owner="o", repo="r",
            last_updated="2026-01-02T00:00:00Z",
        )
        t = MagicMock()
        t.list_open_issues.return_value = [issue]
        t.fetch_comments.return_value = []

        repo_cfg = {"provider": "github", "owner": "o", "repo": "r", "pat": "fake"}

        with patch("autoswe.providers.github.adapter.get_vcs"):
            from autoswe.providers.github.adapter import read_api
            api_states = read_api(
                t, repo_cfg, {},
                prev_updated={7: "2026-01-01T00:00:00Z"},
            )

        assert api_states[7].comments_fetched is True
        t.fetch_comments.assert_called_once()


# ---------------------------------------------------------------------------
# apply_effect — output shape lockdown
# ---------------------------------------------------------------------------

class TestApplyEffectGitHub:
    """GitHub adapter apply_effect tests."""

    def test_set_status(self):
        """Effect(set_status='planned') → tracker.set_status called with 'autoswe:planned'."""
        tracker = MagicMock()
        queue = {"gh__owner_repo_7": {"autoswe_status": None}}
        effect = Effect(kind="set_status", status="planned")

        from autoswe.providers.github.adapter import apply_effect
        apply_effect(tracker, effect, {"provider": "github"}, 7, queue, "gh__owner_repo_7")

        tracker.set_status.assert_called_once_with({"provider": "github"}, 7, "autoswe:planned")

    def test_post_comment(self):
        """Effect(post_comment) → tracker.post_comment called."""
        tracker = MagicMock()
        queue = {}
        effect = Effect(kind="post_comment", body="Plan posted.\n<!-- autoswe-bot -->")

        from autoswe.providers.github.adapter import apply_effect
        apply_effect(tracker, effect, {"provider": "github"}, 7, queue, "gh__owner_repo_7")

        tracker.post_comment.assert_called_once_with({"provider": "github"}, 7, "Plan posted.\n<!-- autoswe-bot -->")

    def test_patch_queue(self):
        """Effect(patch_queue) → queue[slug] updated."""
        tracker = MagicMock()
        queue = {"gh__owner_repo_7": {"autoswe_status": "pending", "last_consumed_reply_ts": ""}}
        effect = Effect(
            kind="patch_queue",
            queue_patch={"autoswe_status": "planned", "last_consumed_reply_ts": "2026-01-01T00:00:00Z"},
        )

        from autoswe.providers.github.adapter import apply_effect
        apply_effect(tracker, effect, {"provider": "github"}, 7, queue, "gh__owner_repo_7")

        assert queue["gh__owner_repo_7"]["autoswe_status"] == "planned"
        assert queue["gh__owner_repo_7"]["last_consumed_reply_ts"] == "2026-01-01T00:00:00Z"


class TestApplyEffectAzure:
    """Azure adapter apply_effect tests."""

    def test_set_status(self):
        """Effect(set_status) → tracker.set_status called with autoswe: prefix."""
        tracker = MagicMock()
        queue = {}
        effect = Effect(kind="set_status", status="failed")

        from autoswe.providers.azure.adapter import apply_effect
        apply_effect(tracker, effect, {"provider": "azure"}, 42, queue, "ado__owner_repo_42")

        tracker.set_status.assert_called_once_with({"provider": "azure"}, 42, "autoswe:failed")

    def test_post_comment(self):
        """Effect(post_comment) → tracker.post_comment called."""
        tracker = MagicMock()
        queue = {}
        effect = Effect(kind="post_comment", body="Max attempts reached.\n<!-- autoswe-bot -->")

        from autoswe.providers.azure.adapter import apply_effect
        apply_effect(tracker, effect, {"provider": "azure"}, 42, queue, "ado__owner_repo_42")

        tracker.post_comment.assert_called_once_with(
            {"provider": "azure"}, 42, "Max attempts reached.\n<!-- autoswe-bot -->"
        )


class TestApplyEffectCreatePr:
    """Provider-agnostic create_pr effect idempotency tests."""

    def test_github_create_pr_no_existing(self):
        """When no PR exists, GitHub adapter calls open_pull_request."""
        tracker = MagicMock()
        queue = {}
        vcs = MagicMock()
        vcs.find_existing_pr.return_value = None
        repo_cfg = {"provider": "github"}

        with patch("autoswe.providers.github.adapter.get_vcs", return_value=vcs):
            from autoswe.providers.github.adapter import apply_effect
            effect = Effect(
                kind="create_pr",
                pr_title="Fixes #1: Test",
                pr_body="Fixes #1",
                pr_head="autoswe/issue-1",
                pr_base="main",
            )
            apply_effect(tracker, effect, repo_cfg, 1, queue, "gh__owner_repo_1")

        vcs.find_existing_pr.assert_called_once()
        vcs.open_pull_request.assert_called_once()

    def test_github_create_pr_existing_skipped(self):
        """When PR exists, GitHub adapter skips open_pull_request."""
        tracker = MagicMock()
        queue = {}
        vcs = MagicMock()
        vcs.find_existing_pr.return_value = PRResult(
            url="https://github.com/o/r/pull/15",
            number=15,
        )
        repo_cfg = {"provider": "github"}

        with patch("autoswe.providers.github.adapter.get_vcs", return_value=vcs):
            from autoswe.providers.github.adapter import apply_effect
            effect = Effect(
                kind="create_pr",
                pr_title="Fixes #1: Test",
                pr_body="Fixes #1",
                pr_head="autoswe/issue-1",
                pr_base="main",
            )
            apply_effect(tracker, effect, repo_cfg, 1, queue, "gh__owner_repo_1")

        vcs.find_existing_pr.assert_called_once()
        # open_pull_request must NOT be called when PR exists
        vcs.open_pull_request.assert_not_called()

    def test_azure_create_pr_no_existing(self):
        """When no PR exists, Azure adapter calls open_pull_request."""
        tracker = MagicMock()
        queue = {}
        vcs = MagicMock()
        vcs.find_existing_pr.return_value = None
        repo_cfg = {"provider": "azure"}

        with patch("autoswe.providers.azure.adapter.get_vcs", return_value=vcs):
            from autoswe.providers.azure.adapter import apply_effect
            effect = Effect(
                kind="create_pr",
                pr_title="Fixes #1: Test",
                pr_body="Fixes #1",
                pr_head="autoswe/issue-1",
                pr_base="main",
            )
            apply_effect(tracker, effect, repo_cfg, 1, queue, "ado__owner_repo_1")

        vcs.find_existing_pr.assert_called_once()
        vcs.open_pull_request.assert_called_once()

    def test_azure_create_pr_existing_skipped(self):
        """When PR exists, Azure adapter skips open_pull_request."""
        tracker = MagicMock()
        queue = {}
        vcs = MagicMock()
        vcs.find_existing_pr.return_value = PRResult(
            url="https://dev.azure.com/o/p/_git/r/pr/15",
            number=15,
        )
        repo_cfg = {"provider": "azure"}

        with patch("autoswe.providers.azure.adapter.get_vcs", return_value=vcs):
            from autoswe.providers.azure.adapter import apply_effect
            effect = Effect(
                kind="create_pr",
                pr_title="Fixes #1: Test",
                pr_body="Fixes #1",
                pr_head="autoswe/issue-1",
                pr_base="main",
            )
            apply_effect(tracker, effect, repo_cfg, 1, queue, "ado__owner_repo_1")

        vcs.find_existing_pr.assert_called_once()
        # open_pull_request must NOT be called when PR exists
        vcs.open_pull_request.assert_not_called()


class TestApplyEffectCreatePrBranchLinking:
    """create_pr effect should link branch to issue after PR creation (issue #49)."""

    def test_github_create_pr_links_branch(self):
        """After creating a new PR, link_branch_to_issue should be called."""
        tracker = MagicMock()
        queue = {}
        link_calls = []

        class MockVCS:
            def find_existing_pr(self, *a, **kw):
                return None
            def open_pull_request(self, *a, **kw):
                return PRResult(url="https://github.com/o/r/pull/42", number=42)
            def link_branch_to_issue(self, issue_number, commit_sha, branch):
                link_calls.append((issue_number, commit_sha, branch))

        repo_cfg = {"provider": "github", "owner": "o", "repo": "r"}

        with patch("autoswe.providers.github.adapter.get_vcs", return_value=MockVCS()):
            with patch("autoswe.providers.github.adapter.get_remote_branch_sha",
                       return_value="abcdef1"):
                from autoswe.providers.github.adapter import apply_effect
                effect = Effect(
                    kind="create_pr",
                    pr_title="Fixes #1: Test",
                    pr_body="Fixes #1",
                    pr_head="autoswe/issue-1",
                    pr_base="main",
                )
                apply_effect(tracker, effect, repo_cfg, 1, queue, "gh__owner_repo_1")

        assert len(link_calls) == 1
        assert link_calls[0][0] == 1
        assert link_calls[0][1] == "abcdef1"
        assert link_calls[0][2] == "autoswe/issue-1"

    def test_github_create_pr_no_link_when_existing(self):
        """When PR already exists, link_branch_to_issue should NOT be called."""
        tracker = MagicMock()
        queue = {}
        link_calls = []

        class MockVCS:
            def find_existing_pr(self, *a, **kw):
                return PRResult(url="https://github.com/o/r/pull/15", number=15)
            def open_pull_request(self, *a, **kw):
                return PRResult(url="https://github.com/o/r/pull/42", number=42)
            def link_branch_to_issue(self, issue_number, commit_sha, branch):
                link_calls.append((issue_number, commit_sha, branch))

        repo_cfg = {"provider": "github", "owner": "o", "repo": "r"}

        with patch("autoswe.providers.github.adapter.get_vcs", return_value=MockVCS()):
            from autoswe.providers.github.adapter import apply_effect
            effect = Effect(
                kind="create_pr",
                pr_title="Fixes #1: Test",
                pr_body="Fixes #1",
                pr_head="autoswe/issue-1",
                pr_base="main",
            )
            apply_effect(tracker, effect, repo_cfg, 1, queue, "gh__owner_repo_1")

        # link_branch_to_issue should NOT be called when PR exists
        assert len(link_calls) == 0

    def test_github_create_pr_link_failure_does_not_break(self):
        """If link_branch_to_issue raises, apply_effect should not raise."""
        tracker = MagicMock()
        queue = {}

        class FailingVCS:
            def find_existing_pr(self, *a, **kw):
                return None
            def open_pull_request(self, *a, **kw):
                return PRResult(url="https://github.com/o/r/pull/42", number=42)
            def link_branch_to_issue(self, issue_number, commit_sha, branch):
                raise RuntimeError("API error")

        repo_cfg = {"provider": "github", "owner": "o", "repo": "r"}

        with patch("autoswe.providers.github.adapter.get_vcs", return_value=FailingVCS()):
            with patch("autoswe.providers.github.adapter.get_remote_branch_sha",
                       return_value="abcdef1"):
                from autoswe.providers.github.adapter import apply_effect
                effect = Effect(
                    kind="create_pr",
                    pr_title="Fixes #1: Test",
                    pr_body="Fixes #1",
                    pr_head="autoswe/issue-1",
                    pr_base="main",
                )
                # Should not raise
                apply_effect(tracker, effect, repo_cfg, 1, queue, "gh__owner_repo_1")

    def test_github_create_pr_missing_scope_error_handled(self):
        """MissingScopeError should be caught (not silently swallowed by generic except)."""
        tracker = MagicMock()
        queue = {}

        class MissingScopeVCS:
            def find_existing_pr(self, *a, **kw):
                return None
            def open_pull_request(self, *a, **kw):
                return PRResult(url="https://github.com/o/r/pull/42", number=42)
            def link_branch_to_issue(self, issue_number, commit_sha, branch):
                from autoswe.providers.github.vcs import MissingScopeError
                raise MissingScopeError("PAT missing check_runs:write scope")

        repo_cfg = {"provider": "github", "owner": "o", "repo": "r"}

        with patch("autoswe.providers.github.adapter.get_vcs", return_value=MissingScopeVCS()):
            with patch("autoswe.providers.github.adapter.get_remote_branch_sha",
                       return_value="abcdef1"):
                from autoswe.providers.github.adapter import apply_effect
                effect = Effect(
                    kind="create_pr",
                    pr_title="Fixes #1: Test",
                    pr_body="Fixes #1",
                    pr_head="autoswe/issue-1",
                    pr_base="main",
                )
                # Should not raise — MissingScopeError is caught
                apply_effect(tracker, effect, repo_cfg, 1, queue, "gh__owner_repo_1")

    def test_github_create_pr_no_link_when_sha_unknown(self):
        """When branch SHA fetch returns None, link_branch_to_issue is skipped."""
        tracker = MagicMock()
        queue = {}
        link_calls = []

        class MockVCS:
            def find_existing_pr(self, *a, **kw):
                return None
            def open_pull_request(self, *a, **kw):
                return PRResult(url="https://github.com/o/r/pull/42", number=42)
            def link_branch_to_issue(self, issue_number, commit_sha, branch):
                link_calls.append((issue_number, commit_sha, branch))

        repo_cfg = {"provider": "github", "owner": "o", "repo": "r"}

        with patch("autoswe.providers.github.adapter.get_vcs", return_value=MockVCS()):
            with patch("autoswe.providers.github.adapter.get_remote_branch_sha",
                       return_value=None):
                from autoswe.providers.github.adapter import apply_effect
                effect = Effect(
                    kind="create_pr",
                    pr_title="Fixes #1: Test",
                    pr_body="Fixes #1",
                    pr_head="autoswe/issue-1",
                    pr_base="main",
                )
                apply_effect(tracker, effect, repo_cfg, 1, queue, "gh__owner_repo_1")

        # Should NOT call link_branch_to_issue when SHA is unknown
        assert len(link_calls) == 0


class TestApplyEffectAzureCreatePr:
    """Azure adapter create_pr — link_branch_to_issue is a no-op for Azure."""

    def test_azure_create_pr_no_link_branch_call(self):
        """Azure adapter does NOT call link_branch_to_issue (documented no-op).

        Azure DevOps has no equivalent to GitHub's Development section, so
        link_branch_to_issue is a no-op. The adapter omits the call entirely
        to avoid dead code.
        """
        tracker = MagicMock()
        queue = {}
        link_calls = []

        class MockVCS:
            def find_existing_pr(self, *a, **kw):
                return None
            def open_pull_request(self, *a, **kw):
                return PRResult(
                    url="https://dev.azure.com/o/p/_git/r/pr/42",
                    number=42,
                )
            def link_branch_to_issue(self, issue_number, commit_sha, branch):
                link_calls.append((issue_number, commit_sha, branch))

        repo_cfg = {"provider": "azure", "org": "o", "project": "p", "repo": "r", "pat": "fake"}

        with patch("autoswe.providers.azure.adapter.get_vcs", return_value=MockVCS()):
            from autoswe.providers.azure.adapter import apply_effect
            effect = Effect(
                kind="create_pr",
                pr_title="Fixes #1: Test",
                pr_body="Fixes #1",
                pr_head="autoswe/issue-1",
                pr_base="main",
            )
            apply_effect(tracker, effect, repo_cfg, 1, queue, "ado__owner_repo_1")

        # Azure does not call link_branch_to_issue — it's a documented no-op
        assert len(link_calls) == 0

    def test_azure_create_pr_no_link_when_existing(self):
        """When PR already exists on Azure, open_pull_request is not called."""
        tracker = MagicMock()
        queue = {}
        open_calls = []

        class MockVCS:
            def find_existing_pr(self, *a, **kw):
                return PRResult(
                    url="https://dev.azure.com/o/p/_git/r/pr/15",
                    number=15,
                )
            def open_pull_request(self, *a, **kw):
                open_calls.append(True)
                return PRResult(
                    url="https://dev.azure.com/o/p/_git/r/pr/42",
                    number=42,
                )

        repo_cfg = {"provider": "azure", "org": "o", "project": "p", "repo": "r", "pat": "fake"}

        with patch("autoswe.providers.azure.adapter.get_vcs", return_value=MockVCS()):
            from autoswe.providers.azure.adapter import apply_effect
            effect = Effect(
                kind="create_pr",
                pr_title="Fixes #1: Test",
                pr_body="Fixes #1",
                pr_head="autoswe/issue-1",
                pr_base="main",
            )
            apply_effect(tracker, effect, repo_cfg, 1, queue, "ado__owner_repo_1")

        assert len(open_calls) == 0
