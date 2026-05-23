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
        assert _is_author_allowed("OWNER", _cfg({"natedorr"}), {}) is False

    def test_author_normalized_login_in_allowlist(self):
        """AUTHOR in allowlist allows literal AUTHOR string."""
        assert _is_author_allowed("AUTHOR", _cfg({"AUTHOR"}), {}) is True

    def test_azure_email_in_allowlist(self):
        """Azure uses email/UPN as author_login - matches in allowlist."""
        assert _is_author_allowed("jane@example.com", _cfg({"jane@example.com"}), {}) is True
        assert _is_author_allowed("other@example.com", _cfg({"jane@example.com"}), {}) is False


class TestFindSlashCommandCreatorLogin:
    """Tests that _find_slash_command returns creator_login for body commands."""

    def test_body_command_returns_creator_login(self):
        """Body-sourced command returns actual creator_login, not AUTHOR."""
        result, author, source_id = _find_slash_command(
            (), "Bug description\n/plan", "autoswe", creator_login="natedorr"
        )
        assert author == "natedorr"
        assert source_id == 0
        assert result[0] == "/plan"

    def test_body_command_returns_empty_when_no_creator(self):
        """Body-sourced command with no creator_login returns empty string."""
        result, author, source_id = _find_slash_command(
            (), "/fix", "autoswe", creator_login=""
        )
        assert author == ""
        assert result[0] == "/fix"

    def test_comment_command_returns_comment_author(self):
        """Comment-sourced command returns comment author, not creator_login."""
        comments = (
            NormalizedComment(
                body="/fix with guidance",
                created_at="2026-01-01T00:00:00Z",
                author_login="alice", id=42,
            ),
        )
        result, author, source_id = _find_slash_command(
            comments, "", "autoswe", creator_login="natedorr"
        )
        assert author == "alice"
        assert source_id == 42

    def test_no_command_returns_none(self):
        """No slash command returns (None, None, 0)."""
        result, author, source_id = _find_slash_command(
            (), "Just a normal body", "autoswe", creator_login="natedorr"
        )
        assert result is None
        assert author is None
        assert source_id == 0
