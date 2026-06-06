"""Tests for autoswe.core.redact — worktree path masking."""
from __future__ import annotations

from autoswe.core.redact import _worktree_leaf, redact_worktree_paths


class TestWorktreeLeaf:
    """_worktree_leaf() derives the leaf name from WORKTREE_DIR."""

    def test_default(self, monkeypatch):
        monkeypatch.delenv("WORKTREE_DIR", raising=False)
        assert _worktree_leaf() == "worktrees"

    def test_relative_custom(self, monkeypatch):
        monkeypatch.setenv("WORKTREE_DIR", "my_wt")
        assert _worktree_leaf() == "my_wt"

    def test_absolute_posix_leaf(self, monkeypatch):
        monkeypatch.setenv("WORKTREE_DIR", "/tmp/my_worktrees")
        assert _worktree_leaf() == "my_worktrees"

    def test_absolute_windows_leaf(self, monkeypatch):
        monkeypatch.setenv("WORKTREE_DIR", "C:\\dev\\wt")
        assert _worktree_leaf() == "wt"


class TestRedactWorktreePaths:
    """redact_worktree_paths(text) masks worktree root paths."""

    def test_posix_path(self, monkeypatch):
        monkeypatch.delenv("WORKTREE_DIR", raising=False)
        text = "/home/user/.autoswe/worktrees/gh-owner_repo/issue-5/module.py"
        result = redact_worktree_paths(text)
        assert result == ".../worktrees/gh-owner_repo/issue-5/module.py"
        assert "home" not in result
        assert ".autoswe" not in result

    def test_windows_drive_path(self, monkeypatch):
        monkeypatch.delenv("WORKTREE_DIR", raising=False)
        text = "C:\\Users\\dev\\.autoswe\\worktrees\\gh-o_r\\issue-1\\file.py"
        result = redact_worktree_paths(text)
        # Backslash paths preserve backslashes in the tail after masking
        assert result.startswith(".../worktrees")
        assert "Users" not in result
        assert "dev\\." not in result  # parent dirs masked

    def test_mixed_separators(self, monkeypatch):
        monkeypatch.delenv("WORKTREE_DIR", raising=False)
        # Agent output might mix / and \ on Windows
        text = "D:/project/worktrees/gh-o_r/issue-3\\autoswe\\harness/coder.py"
        result = redact_worktree_paths(text)
        assert ".../worktrees/" in result
        assert "gh-o_r/issue-3" in result or "gh-o_r\\issue-3" in result

    def test_custom_worktree_dir(self, monkeypatch):
        monkeypatch.setenv("WORKTREE_DIR", "my_wt")
        text = "/opt/agent/my_wt/gh-o_r/issue-10/core.py"
        result = redact_worktree_paths(text)
        assert result == ".../my_wt/gh-o_r/issue-10/core.py"
        assert "opt" not in result

    def test_multiple_paths(self, monkeypatch):
        monkeypatch.delenv("WORKTREE_DIR", raising=False)
        text = (
            "Error in /home/u/worktrees/gh-o_r/issue-1/a.py\n"
            "Also see /home/u/worktrees/gh-o_r/issue-1/b.py"
        )
        result = redact_worktree_paths(text)
        assert "home" not in result
        assert result.count(".../") == 2
        assert "gh-o_r/issue-1/a.py" in result
        assert "gh-o_r/issue-1/b.py" in result

    def test_no_path_unchanged(self, monkeypatch):
        monkeypatch.delenv("WORKTREE_DIR", raising=False)
        text = "This text has no worktree paths at all."
        assert redact_worktree_paths(text) == text

    def test_idempotent(self, monkeypatch):
        monkeypatch.delenv("WORKTREE_DIR", raising=False)
        text = "/home/user/worktrees/gh-o_r/issue-1/file.py"
        first = redact_worktree_paths(text)
        second = redact_worktree_paths(first)
        assert first == second
        assert first == ".../worktrees/gh-o_r/issue-1/file.py"

    def test_preserves_quotes(self, monkeypatch):
        monkeypatch.delenv("WORKTREE_DIR", raising=False)
        text = 'See file "/home/u/worktrees/gh-o_r/issue-1/mod.py" for details.'
        result = redact_worktree_paths(text)
        assert '"' in result
        assert ".../worktrees/gh-o_r/issue-1/mod.py" in result

    def test_path_in_code_block(self, monkeypatch):
        monkeypatch.delenv("WORKTREE_DIR", raising=False)
        text = (
            "```\n"
            "/home/u/worktrees/gh-o_r/issue-1/src/main.py\n"
            "```\n"
        )
        result = redact_worktree_paths(text)
        assert ".../worktrees/gh-o_r/issue-1/src/main.py" in result
        assert "home" not in result

    def test_short_path_no_replacement(self, monkeypatch):
        """A bare 'worktrees' without a leading separator should not match."""
        monkeypatch.delenv("WORKTREE_DIR", raising=False)
        text = "worktrees is a directory name"
        assert redact_worktree_paths(text) == text

    def test_absolute_custom_dir_posix(self, monkeypatch):
        """WORKTREE_DIR set to absolute POSIX path — leaf is extracted."""
        monkeypatch.setenv("WORKTREE_DIR", "/var/run/agent_cache")
        text = "/var/run/agent_cache/gh-o_r/issue-1/f.py"
        result = redact_worktree_paths(text)
        assert ".../agent_cache/" in result
        assert "var" not in result
