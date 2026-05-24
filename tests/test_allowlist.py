"""Tests for actor allowlist (Feature E)."""
from autoswe.orch.decide import _find_slash_command, _is_author_allowed
from autoswe.providers.base import NormalizedComment


def _cfg(global_allowed: set) -> dict:
    return {"ALLOWED_AUTHORS": global_allowed}


def _repo_cfg(allowed: str | set | None) -> dict:
    if allowed is None:
        return {}
    if isinstance(allowed, set):
        return {"allowed_authors": ",".join(allowed)}
    return {"allowed_authors": allowed}


class TestIsAuthorAllowed:
    """Test the _is_author_allowed helper."""

    def test_empty_allowlist_allows_all(self):
        """Empty allowlist means no restriction."""
        assert _is_author_allowed("anyone", _cfg(set()), _repo_cfg(None)) is True
        assert _is_author_allowed("malicious-user", _cfg(set()), _repo_cfg(None)) is True

    def test_global_allowlist_allows_matching(self):
        """Author in global allowlist is allowed."""
        allowed = {"nate", "alice", "bob"}
        assert _is_author_allowed("nate", _cfg(allowed), _repo_cfg(None)) is True
        assert _is_author_allowed("alice", _cfg(allowed), _repo_cfg(None)) is True

    def test_global_allowlist_blocks_non_matching(self):
        """Author not in global allowlist is blocked."""
        allowed = {"nate", "alice"}
        assert _is_author_allowed("malicious-user", _cfg(allowed), _repo_cfg(None)) is False

    def test_repo_override_takes_priority(self):
        """Repo-level override replaces global allowlist."""
        assert _is_author_allowed("alice", _cfg({"nate"}), _repo_cfg({"alice", "bob"})) is True
        assert _is_author_allowed("nate", _cfg({"nate"}), _repo_cfg({"alice", "bob"})) is False

    def test_empty_repo_override_uses_global(self):
        """Empty repo override falls back to global allowlist."""
        assert _is_author_allowed("nate", _cfg({"nate"}), {}) is True
        assert _is_author_allowed("other", _cfg({"nate"}), {}) is False

    def test_author_login_is_case_sensitive(self):
        """Author matching is case-sensitive."""
        assert _is_author_allowed("Nate", _cfg({"Nate"}), {}) is True
        assert _is_author_allowed("nate", _cfg({"Nate"}), {}) is False

    def test_body_sourced_creator_authorized(self):
        """Body-sourced command: creator in allowlist -> allowed.

        After fix, _find_slash_command returns creator_login instead of
        "AUTHOR", so _is_author_allowed correctly matches the real username.
        """
        assert _is_author_allowed("natedorr", _cfg({"natedorr", "alice"}), {}) is True

    def test_body_sourced_creator_unauthorized(self):
        """Body-sourced command: creator not in allowlist -> blocked."""
        assert _is_author_allowed("random-user", _cfg({"natedorr", "alice"}), {}) is False

    def test_owner_normalized_login_allowed(self):
        """OWNER normalized login matches explicit OWNER in allowlist."""
        assert _is_author_allowed("OWNER", _cfg({"OWNER"}), {}) is True
        # Without raw_author_login, OWNER does NOT match "natedorr"
        assert _is_author_allowed("OWNER", _cfg({"natedorr"}), {}) is False

    def test_author_normalized_login_in_allowlist(self):
        """AUTHOR in allowlist allows literal AUTHOR string."""
        assert _is_author_allowed("AUTHOR", _cfg({"AUTHOR"}), {}) is True

    def test_azure_email_in_allowlist(self):
        """Azure uses email/UPN as author_login - matches in allowlist."""
        assert _is_author_allowed("jane@example.com", _cfg({"jane@example.com"}), {}) is True
        assert _is_author_allowed("other@example.com", _cfg({"jane@example.com"}), {}) is False


class TestIsAuthorAllowedWithRawLogin:
    """Test raw_author_login support — the bug fix for #5."""

    def test_pat_owner_raw_login_matches_allowlist(self):
        """PAT owner "Natedorr" normalized to "OWNER" — raw login matches allowlist."""
        # This is the main bug fix: normalized "OWNER" does NOT match,
        # but raw "Natedorr" DOES match the allowlist.
        cfg = _cfg({"Natedorr"})
        # Without raw login, "OWNER" alone does NOT match
        assert _is_author_allowed("OWNER", cfg, {}, "") is False
        # With raw login, it DOES match
        assert _is_author_allowed("OWNER", cfg, {}, "Natedorr") is True

    def test_issue_author_raw_login_matches_allowlist(self):
        """Issue author normalized to "AUTHOR" — raw login matches allowlist."""
        cfg = _cfg({"CollaboratorJane"})
        assert _is_author_allowed("AUTHOR", cfg, {}, "") is False
        assert _is_author_allowed("AUTHOR", cfg, {}, "CollaboratorJane") is True

    def test_owner_explicit_in_allowlist_still_works(self):
        """Backward compat: explicit "OWNER" in allowlist still works."""
        cfg = _cfg({"OWNER"})
        assert _is_author_allowed("OWNER", cfg, {}, "Natedorr") is True

    def test_non_matching_user_still_blocked_with_raw(self):
        """User not in allowlist is still blocked even with raw login."""
        cfg = _cfg({"alice"})
        assert _is_author_allowed("OWNER", cfg, {}, "bob") is False
        assert _is_author_allowed("bob", cfg, {}, "bob") is False

    def test_empty_raw_login_no_effect(self):
        """Empty raw_author_login does not cause false match."""
        cfg = _cfg({"Natedorr"})
        assert _is_author_allowed("OWNER", cfg, {}, "") is False

    def test_azure_pat_owner_raw_email_matches(self):
        """Azure PAT owner email normalized to "OWNER" — raw email matches."""
        cfg = _cfg({"natedorr@example.com"})
        assert _is_author_allowed("OWNER", cfg, {}, "") is False
        assert _is_author_allowed("OWNER", cfg, {}, "natedorr@example.com") is True

    def test_empty_allowlist_with_raw_login(self):
        """Empty allowlist allows everyone regardless of raw login."""
        assert _is_author_allowed("OWNER", _cfg(set()), {}, "Natedorr") is True

    def test_repo_override_with_raw_login(self):
        """Repo-level override works correctly with raw login."""
        cfg = _cfg({"Natedorr"})
        repo = _repo_cfg({"CollaboratorJane"})
        # Global allowlist has "Natedorr", repo override has "CollaboratorJane"
        # OWNER normalized, raw is "Natedorr" → should be blocked (repo override wins)
        assert _is_author_allowed("OWNER", cfg, repo, "Natedorr") is False
        # But "CollaboratorJane" raw login should match repo override
        assert _is_author_allowed("AUTHOR", cfg, repo, "CollaboratorJane") is True


class TestFindSlashCommandRawAuthor:
    """Tests that _find_slash_command returns raw_author_login (4th value)."""

    def test_body_command_returns_creator_as_raw(self):
        """Body-sourced command returns creator_login as both author and raw."""
        result, author, raw_author, source_id = _find_slash_command(
            (), "Bug description\n/plan", "autoswe", creator_login="natedorr"
        )
        assert author == "natedorr"
        assert raw_author == "natedorr"
        assert source_id == 0
        assert result[0] == "/plan"

    def test_body_command_empty_creator_returns_empty_raw(self):
        """Body-sourced command with no creator returns empty raw."""
        result, author, raw_author, source_id = _find_slash_command(
            (), "/fix", "autoswe", creator_login=""
        )
        assert author == ""
        assert raw_author == ""
        assert result[0] == "/fix"

    def test_comment_command_returns_normalized_author_and_raw(self):
        """Comment-sourced: normalized author + raw_author_login from comment."""
        comments = (
            NormalizedComment(
                body="/fix with guidance",
                created_at="2026-01-01T00:00:00Z",
                author_login="OWNER",
                raw_author_login="Natedorr",
                id=42,
            ),
        )
        result, author, raw_author, source_id = _find_slash_command(
            comments, "", "autoswe", creator_login="natedorr"
        )
        assert author == "OWNER"
        assert raw_author == "Natedorr"
        assert source_id == 42

    def test_comment_command_without_raw_field(self):
        """Comment without raw_author_login field falls back to empty string."""
        comments = (
            NormalizedComment(
                body="/fix with guidance",
                created_at="2026-01-01T00:00:00Z",
                author_login="alice", id=42,
            ),
        )
        result, author, raw_author, source_id = _find_slash_command(
            comments, "", "autoswe", creator_login="natedorr"
        )
        assert author == "alice"
        assert raw_author == ""
        assert source_id == 42

    def test_no_command_returns_empty_raw(self):
        """No slash command returns (None, None, '', 0)."""
        result, author, raw_author, source_id = _find_slash_command(
            (), "Just a normal body", "autoswe", creator_login="natedorr"
        )
        assert result is None
        assert author is None
        assert raw_author == ""
        assert source_id == 0
