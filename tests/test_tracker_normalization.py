"""Golden fixture tests for tracker API response normalization.

Validates that both GitHubTracker and AzureTracker correctly normalize
author_login values from raw API responses into the canonical set
{"BOT", "OWNER", "AUTHOR", <raw_login>}.

These tests use committed golden fixtures (real API response shapes) so that
if the provider normalization logic breaks, the tests fail — preventing
bugs like the author_login mismatch that caused /pr on done issues to
be silently ignored in production.
"""

import json
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Fixture loading
# ---------------------------------------------------------------------------

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "github"
ADO_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "azure"


def _load(name: str) -> dict | list:
    return json.loads(FIXTURE_DIR.joinpath(name).read_text(encoding="utf-8"))


def _load_ado(name: str) -> dict | list:
    return json.loads(ADO_FIXTURE_DIR.joinpath(name).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Contract: normalized author_login values
# ---------------------------------------------------------------------------

# These are the ONLY valid normalized author_login values for orchestrator use.
# Raw logins from contributors who are neither the token owner nor the issue
# author should pass through unchanged.
CANONICAL_AUTHORS = {"BOT", "OWNER", "AUTHOR"}


def _is_canonical(author_login: str) -> bool:
    return author_login in CANONICAL_AUTHORS


# ---------------------------------------------------------------------------
# GitHub tracker normalization
# ---------------------------------------------------------------------------

@pytest.mark.usefixtures("isolated_autoswe_dir")
class TestGitHubTrackerNormalization:
    """Golden fixture test: GitHubTracker.fetch_comments normalizes author_login."""

    def test_bot_comments_normalized_to_BOT(self, monkeypatch, gh_route_table):
        """Comments with BOT_MARKER in body → author_login='BOT'."""
        fixture = _load("issue_done_with_comments.json")
        comments_raw = fixture["comments"]

        # Mock _fetch_comments to return raw fixture data
        import autoswe.providers.github.tracker as gt_mod
        monkeypatch.setattr(
            gt_mod.gh_api, "_fetch_comments",
            lambda *a, **kw: comments_raw
        )
        # Mock _get_authenticated_user to return token owner
        monkeypatch.setattr(
            gt_mod, "_get_authenticated_user",
            lambda *a, **kw: fixture["__meta"]["token_owner_login"]
        )

        repo_cfg = {
            "owner": "Natedorr",
            "repo": "example-app",
            "token": "ghp_test",
            "provider": "github",
        }
        tracker = gt_mod.GitHubTracker(repo_cfg)

        # Set issue author so AUTHOR normalization works
        tracker.set_issue_author(fixture["__meta"]["issue_author_login"])

        normalized = tracker.fetch_comments(repo_cfg, 42)

        # Bot comments (with <!-- autoswe-bot -->) → "BOT"
        bot_comments = [c for c in normalized if "autoswe-bot" in c.body]
        for c in bot_comments:
            assert c.author_login == "BOT", (
                f"Bot comment should normalize to 'BOT', got '{c.author_login}'"
            )

    def test_token_owner_comments_normalized_to_OWNER(self, monkeypatch, gh_route_table):
        """Comments by the token owner → author_login='OWNER'."""
        fixture = _load("issue_done_with_comments.json")
        comments_raw = fixture["comments"]
        token_owner = fixture["__meta"]["token_owner_login"]

        import autoswe.providers.github.tracker as gt_mod
        monkeypatch.setattr(
            gt_mod.gh_api, "_fetch_comments",
            lambda *a, **kw: comments_raw
        )
        monkeypatch.setattr(
            gt_mod, "_get_authenticated_user",
            lambda *a, **kw: token_owner
        )

        repo_cfg = {
            "owner": "Natedorr",
            "repo": "example-app",
            "token": "ghp_test",
            "provider": "github",
        }
        tracker = gt_mod.GitHubTracker(repo_cfg)
        tracker.set_issue_author(fixture["__meta"]["issue_author_login"])

        normalized = tracker.fetch_comments(repo_cfg, 42)

        # Non-bot comments by token owner → "OWNER"
        # The "/fix with focus on session handling" comment is by Natedorr (OWNER)
        assert any(c.author_login == "OWNER" for c in normalized), (
            "Token owner comments should normalize to 'OWNER'"
        )

    def test_issue_author_comments_normalized_to_AUTHOR(self, monkeypatch, gh_route_table):
        """Comments by the issue author (different from token owner) → author_login='AUTHOR'."""
        fixture = _load("issue_done_with_comments.json")
        comments_raw = fixture["comments"]
        issue_author = fixture["__meta"]["issue_author_login"]

        import autoswe.providers.github.tracker as gt_mod
        monkeypatch.setattr(
            gt_mod.gh_api, "_fetch_comments",
            lambda *a, **kw: comments_raw
        )
        monkeypatch.setattr(
            gt_mod, "_get_authenticated_user",
            lambda *a, **kw: fixture["__meta"]["token_owner_login"]
        )

        repo_cfg = {
            "owner": "Natedorr",
            "repo": "example-app",
            "token": "ghp_test",
            "provider": "github",
        }
        tracker = gt_mod.GitHubTracker(repo_cfg)
        tracker.set_issue_author(issue_author)

        normalized = tracker.fetch_comments(repo_cfg, 42)

        # The "/pr" comment is by CollaboratorJane (issue author) → "AUTHOR"
        author_comments = [c for c in normalized if c.author_login == "AUTHOR"]
        assert any("/pr" in c.body for c in author_comments), (
            "Issue author's /pr comment should normalize to 'AUTHOR'"
        )

    def test_other_users_pass_through_unchanged(self, monkeypatch, gh_route_table):
        """Comments by non-owner, non-author users pass through raw login."""
        fixture = _load("issue_done_with_comments.json")
        comments_raw = fixture["comments"]

        import autoswe.providers.github.tracker as gt_mod
        monkeypatch.setattr(
            gt_mod.gh_api, "_fetch_comments",
            lambda *a, **kw: comments_raw
        )
        monkeypatch.setattr(
            gt_mod, "_get_authenticated_user",
            lambda *a, **kw: fixture["__meta"]["token_owner_login"]
        )

        repo_cfg = {
            "owner": "Natedorr",
            "repo": "example-app",
            "token": "ghp_test",
            "provider": "github",
        }
        tracker = gt_mod.GitHubTracker(repo_cfg)
        tracker.set_issue_author(fixture["__meta"]["issue_author_login"])

        normalized = tracker.fetch_comments(repo_cfg, 42)

        # RandomContributor's comment should pass through as raw login
        contrib_comments = [
            c for c in normalized if c.author_login == "RandomContributor"
        ]
        assert len(contrib_comments) == 1, (
            "Non-owner/non-author comments should pass through raw login"
        )
        assert contrib_comments[0].author_login == "RandomContributor"

    def test_full_normalization_round_trip(self, monkeypatch, gh_route_table):
        """All comments in the golden fixture normalize to expected values."""
        fixture = _load("issue_done_with_comments.json")
        comments_raw = fixture["comments"]

        import autoswe.providers.github.tracker as gt_mod
        monkeypatch.setattr(
            gt_mod.gh_api, "_fetch_comments",
            lambda *a, **kw: comments_raw
        )
        monkeypatch.setattr(
            gt_mod, "_get_authenticated_user",
            lambda *a, **kw: fixture["__meta"]["token_owner_login"]
        )

        repo_cfg = {
            "owner": "Natedorr",
            "repo": "example-app",
            "token": "ghp_test",
            "provider": "github",
        }
        tracker = gt_mod.GitHubTracker(repo_cfg)
        tracker.set_issue_author(fixture["__meta"]["issue_author_login"])

        normalized = tracker.fetch_comments(repo_cfg, 42)

        # Expected: BOT, OWNER, BOT, RandomContributor, AUTHOR
        expected = ["BOT", "OWNER", "BOT", "RandomContributor", "AUTHOR"]
        actual = [c.author_login for c in normalized]
        assert actual == expected, (
            f"Normalization mismatch: expected {expected}, got {actual}"
        )

        # Verify raw_author_login preserves original values
        expected_raw = [
            "Natedorr",           # bot comment by token owner
            "Natedorr",           # user comment by token owner
            "Natedorr",           # bot comment by token owner
            "RandomContributor",  # other user
            "CollaboratorJane",   # issue author
        ]
        actual_raw = [c.raw_author_login for c in normalized]
        assert actual_raw == expected_raw, (
            f"Raw author mismatch: expected {expected_raw}, got {actual_raw}"
        )

    def test_list_open_issues_caches_authors(self, monkeypatch, gh_route_table):
        """list_open_issues populates _issue_authors for later fetch_comments."""
        fixture = _load("issue_done_with_comments.json")

        import autoswe.providers.github.tracker as gt_mod

        def fake_gh_get_all(path, token):
            return [fixture["issue"]]

        monkeypatch.setattr(gt_mod.gh_api, "gh_get_all", fake_gh_get_all)

        repo_cfg = {
            "owner": "Natedorr",
            "repo": "example-app",
            "token": "ghp_test",
            "provider": "github",
        }
        tracker = gt_mod.GitHubTracker(repo_cfg)
        issues = tracker.list_open_issues(repo_cfg)

        assert len(issues) == 1
        assert tracker._issue_authors[issues[0].number] == "CollaboratorJane"

    def test_fetch_issue_caches_author(self, monkeypatch, gh_route_table):
        """fetch_issue caches issue author for later fetch_comments."""
        fixture = _load("issue_done_with_comments.json")

        import autoswe.providers.github.tracker as gt_mod

        def fake_gh_get(path, token):
            return fixture["issue"]

        monkeypatch.setattr(gt_mod.gh_api, "gh_get", fake_gh_get)

        repo_cfg = {
            "owner": "Natedorr",
            "repo": "example-app",
            "token": "ghp_test",
            "provider": "github",
        }
        tracker = gt_mod.GitHubTracker(repo_cfg)
        tracker.fetch_issue(repo_cfg, 42)

        assert tracker._issue_authors[42] == "CollaboratorJane"
        assert tracker._issue_author_login == "CollaboratorJane"

    def test_list_open_issues_populates_last_updated(self, monkeypatch, gh_route_table):
        """list_open_issues picks up updated_at into NormalizedIssue.last_updated."""
        fixture = _load("issue_done_with_comments.json")

        import autoswe.providers.github.tracker as gt_mod

        def fake_gh_get_all(path, token):
            return [fixture["issue"]]

        monkeypatch.setattr(gt_mod.gh_api, "gh_get_all", fake_gh_get_all)

        repo_cfg = {
            "owner": "Natedorr",
            "repo": "example-app",
            "token": "ghp_test",
            "provider": "github",
        }
        tracker = gt_mod.GitHubTracker(repo_cfg)
        issues = tracker.list_open_issues(repo_cfg)

        assert len(issues) == 1
        assert issues[0].last_updated == "2026-05-01T03:10:05Z"

    def test_fetch_issue_populates_last_updated(self, monkeypatch, gh_route_table):
        """fetch_issue picks up updated_at into NormalizedIssue.last_updated."""
        fixture = _load("issue_done_with_comments.json")

        import autoswe.providers.github.tracker as gt_mod

        def fake_gh_get(path, token):
            return fixture["issue"]

        monkeypatch.setattr(gt_mod.gh_api, "gh_get", fake_gh_get)

        repo_cfg = {
            "owner": "Natedorr",
            "repo": "example-app",
            "token": "ghp_test",
            "provider": "github",
        }
        tracker = gt_mod.GitHubTracker(repo_cfg)
        issue = tracker.fetch_issue(repo_cfg, 42)

        assert issue.last_updated == "2026-05-01T03:10:05Z"


# ---------------------------------------------------------------------------
# Azure tracker normalization
# ---------------------------------------------------------------------------

@pytest.mark.usefixtures("isolated_autoswe_dir")
class TestAzureTrackerNormalization:
    """Golden fixture test: AzureTracker.fetch_comments normalizes author_login."""

    def test_bot_comments_normalized_to_BOT(self, monkeypatch, ado_route_table):
        """Comments with BOT_MARKER in body → author_login='BOT'."""
        fixture = _load_ado("workitem_done_with_comments.json")
        comments_data = fixture["comments"]

        import autoswe.providers.azure.tracker as at_mod

        def fake_ado_get(path, pat):
            if "comments" in path:
                return comments_data
            return {}

        monkeypatch.setattr(at_mod, "ado_get", fake_ado_get)

        repo_cfg = {
            "org": "test-org",
            "project": "test-project",
            "pat": "fake_pat",
            "provider": "azure",
        }
        tracker = at_mod.AzureTracker(repo_cfg)

        # Mock authenticated_user to return the PAT owner
        monkeypatch.setattr(
            tracker, "authenticated_user",
            lambda *a: fixture["__meta"]["pat_owner_uniqueName"]
        )

        normalized = tracker.fetch_comments(repo_cfg, 42)

        # Bot comments (with <!-- autoswe-bot -->) → "BOT"
        bot_comments = [c for c in normalized if "autoswe-bot" in c.body]
        for c in bot_comments:
            assert c.author_login == "BOT", (
                f"Bot comment should normalize to 'BOT', got '{c.author_login}'"
            )

    def test_pat_owner_comments_normalized_to_OWNER(self, monkeypatch, ado_route_table):
        """Comments by the PAT owner → author_login='OWNER'."""
        fixture = _load_ado("workitem_done_with_comments.json")
        comments_data = fixture["comments"]
        pat_owner = fixture["__meta"]["pat_owner_uniqueName"]

        import autoswe.providers.azure.tracker as at_mod

        def fake_ado_get(path, pat):
            if "comments" in path:
                return comments_data
            return {}

        monkeypatch.setattr(at_mod, "ado_get", fake_ado_get)

        repo_cfg = {
            "org": "test-org",
            "project": "test-project",
            "pat": "fake_pat",
            "provider": "azure",
        }
        tracker = at_mod.AzureTracker(repo_cfg)
        monkeypatch.setattr(
            tracker, "authenticated_user",
            lambda *a: pat_owner
        )

        normalized = tracker.fetch_comments(repo_cfg, 42)

        # PAT owner's non-bot comments → "OWNER"
        assert any(
            c.author_login == "OWNER"
            for c in normalized
            if "autoswe-bot" not in c.body
        ), "PAT owner comments should normalize to 'OWNER'"

    def test_other_users_pass_through_unchanged(self, monkeypatch, ado_route_table):
        """Comments by non-PAT-owner users pass through raw uniqueName."""
        fixture = _load_ado("workitem_done_with_comments.json")
        comments_data = fixture["comments"]

        import autoswe.providers.azure.tracker as at_mod

        def fake_ado_get(path, pat):
            if "comments" in path:
                return comments_data
            return {}

        monkeypatch.setattr(at_mod, "ado_get", fake_ado_get)

        repo_cfg = {
            "org": "test-org",
            "project": "test-project",
            "pat": "fake_pat",
            "provider": "azure",
        }
        tracker = at_mod.AzureTracker(repo_cfg)
        monkeypatch.setattr(
            tracker, "authenticated_user",
            lambda *a: fixture["__meta"]["pat_owner_uniqueName"]
        )

        normalized = tracker.fetch_comments(repo_cfg, 42)

        # contributor@example.com is neither PAT owner nor issue author
        # Azure doesn't do AUTHOR normalization (no issue author context)
        other_comments = [
            c for c in normalized
            if c.author_login not in ("BOT", "OWNER")
        ]
        assert len(other_comments) > 0, (
            "Non-owner/non-bot comments should pass through"
        )
        assert other_comments[0].author_login == "contributor@example.com"

    def test_full_azure_normalization_round_trip(self, monkeypatch, ado_route_table):
        """All comments in the Azure golden fixture normalize correctly."""
        fixture = _load_ado("workitem_done_with_comments.json")
        comments_data = fixture["comments"]
        pat_owner = fixture["__meta"]["pat_owner_uniqueName"]

        import autoswe.providers.azure.tracker as at_mod

        def fake_ado_get(path, pat):
            if "comments" in path:
                return comments_data
            return {}

        monkeypatch.setattr(at_mod, "ado_get", fake_ado_get)

        repo_cfg = {
            "org": "test-org",
            "project": "test-project",
            "pat": "fake_pat",
            "provider": "azure",
        }
        tracker = at_mod.AzureTracker(repo_cfg)
        monkeypatch.setattr(
            tracker, "authenticated_user",
            lambda *a: pat_owner
        )

        normalized = tracker.fetch_comments(repo_cfg, 42)

        # Expected: BOT, OWNER, BOT, contributor@example.com, jane.doe@example.com
        expected_logins = [
            "BOT",                          # comment 1: bot welcome
            "OWNER",                        # comment 2: /fix by PAT owner
            "BOT",                          # comment 3: bot completion
            "contributor@example.com",      # comment 4: other user
            "jane.doe@example.com",         # comment 5: issue author (not normalized in Azure)
        ]
        actual = [c.author_login for c in normalized]
        assert actual == expected_logins, (
            f"Azure normalization mismatch: expected {expected_logins}, got {actual}"
        )

        # Verify raw_author_login preserves original uniqueName values
        expected_raw = [
            "natedorr@example.com",       # comment 1: bot by PAT owner
            "natedorr@example.com",       # comment 2: /fix by PAT owner
            "natedorr@example.com",       # comment 3: bot by PAT owner
            "contributor@example.com",    # comment 4: other user
            "jane.doe@example.com",       # comment 5: issue author
        ]
        actual_raw = [c.raw_author_login for c in normalized]
        assert actual_raw == expected_raw, (
            f"Azure raw author mismatch: expected {expected_raw}, got {actual_raw}"
        )

    def test_azure_to_normalized_populates_last_updated(self, monkeypatch, ado_route_table):
        """AzureTracker._to_normalized picks up System.ChangedDate."""
        fixture = _load_ado("workitem_done_with_comments.json")
        workitem = fixture["workitem"]

        import autoswe.providers.azure.tracker as at_mod

        repo_cfg = {
            "org": "test-org",
            "project": "test-project",
            "pat": "fake_pat",
            "provider": "azure",
        }
        tracker = at_mod.AzureTracker(repo_cfg)
        normalized = tracker._to_normalized(workitem)

        assert normalized.last_updated == "2026-05-01T03:10:05.000Z"

    def test_azure_fetch_issue_populates_last_updated(self, monkeypatch, ado_route_table):
        """AzureTracker.fetch_issue picks up System.ChangedDate."""
        fixture = _load_ado("workitem_done_with_comments.json")
        workitem = fixture["workitem"]

        import autoswe.providers.azure.tracker as at_mod

        def fake_ado_get(path, pat):
            return workitem

        monkeypatch.setattr(at_mod, "ado_get", fake_ado_get)

        repo_cfg = {
            "org": "test-org",
            "project": "test-project",
            "pat": "fake_pat",
            "provider": "azure",
        }
        tracker = at_mod.AzureTracker(repo_cfg)
        normalized = tracker.fetch_issue(repo_cfg, 42)

        assert normalized.last_updated == "2026-05-01T03:10:05.000Z"


# ---------------------------------------------------------------------------
# Cross-provider contract test
# ---------------------------------------------------------------------------

class TestCrossProviderContract:
    """Both providers must normalize BOT and OWNER consistently."""

    def test_both_providers_normalize_bot_comments(self, monkeypatch, gh_route_table, ado_route_table):
        """Bot comment detection works the same in both providers."""
        bot_comment_body = "Completed with command `/fix`\n<!-- autoswe-bot -->"

        # GitHub
        import autoswe.providers.github.tracker as gt_mod
        monkeypatch.setattr(
            gt_mod.gh_api, "_fetch_comments",
            lambda *a, **kw: [{
                "body": bot_comment_body,
                "created_at": "2026-01-01T00:00:00Z",
                "user": {"login": "Natedorr"},
            }]
        )
        monkeypatch.setattr(gt_mod, "_get_authenticated_user", lambda *a: "Natedorr")

        gh_tracker = gt_mod.GitHubTracker({
            "owner": "Natedorr", "repo": "test", "token": "ghp_test",
        })
        gh_normalized = gh_tracker.fetch_comments({}, 1)
        assert gh_normalized[0].author_login == "BOT"

        # Azure
        import autoswe.providers.azure.tracker as at_mod
        monkeypatch.setattr(
            at_mod, "ado_get",
            lambda *a: {
                "comments": [{
                    "text": bot_comment_body,
                    "createdDate": "2026-01-01T00:00:00Z",
                    "createdBy": {"uniqueName": "natedorr@example.com"},
                }]
            }
        )

        az_tracker = at_mod.AzureTracker({
            "org": "test-org", "project": "test-project", "pat": "fake_pat",
        })
        monkeypatch.setattr(
            az_tracker, "authenticated_user",
            lambda *a: "natedorr@example.com"
        )
        az_normalized = az_tracker.fetch_comments({}, 1)
        assert az_normalized[0].author_login == "BOT"

    def test_both_providers_normalize_owner_comments(self, monkeypatch, gh_route_table, ado_route_table):
        """Token owner / PAT owner normalization works in both providers."""
        user_comment_body = "/fix with performance focus"

        # GitHub
        import autoswe.providers.github.tracker as gt_mod
        monkeypatch.setattr(
            gt_mod.gh_api, "_fetch_comments",
            lambda *a, **kw: [{
                "body": user_comment_body,
                "created_at": "2026-01-01T00:00:00Z",
                "user": {"login": "Natedorr"},
            }]
        )
        monkeypatch.setattr(gt_mod, "_get_authenticated_user", lambda *a: "Natedorr")

        gh_tracker = gt_mod.GitHubTracker({
            "owner": "Natedorr", "repo": "test", "token": "ghp_test",
        })
        gh_normalized = gh_tracker.fetch_comments({}, 1)
        assert gh_normalized[0].author_login == "OWNER"

        # Azure
        import autoswe.providers.azure.tracker as at_mod
        monkeypatch.setattr(
            at_mod, "ado_get",
            lambda *a: {
                "comments": [{
                    "text": user_comment_body,
                    "createdDate": "2026-01-01T00:00:00Z",
                    "createdBy": {"uniqueName": "natedorr@example.com"},
                }]
            }
        )

        az_tracker = at_mod.AzureTracker({
            "org": "test-org", "project": "test-project", "pat": "fake_pat",
        })
        monkeypatch.setattr(
            az_tracker, "authenticated_user",
            lambda *a: "natedorr@example.com"
        )
        az_normalized = az_tracker.fetch_comments({}, 1)
        assert az_normalized[0].author_login == "OWNER"
