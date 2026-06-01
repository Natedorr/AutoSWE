"""Tests for autoswe.vcs.worktree — path helpers and git operations."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _cfg(worktree_dir="worktrees"):
    return {"WORKTREE_DIR": worktree_dir}


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def test_worktrees_root_relative(tmp_path, monkeypatch):
    from autoswe.vcs.worktree import _worktrees_root
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))
    import autoswe.vcs.worktree as wt
    monkeypatch.setattr(wt, "AUTOSWE_DIR", tmp_path)
    result = _worktrees_root(_cfg())
    assert result == tmp_path / "worktrees"


def test_worktrees_root_absolute(tmp_path, monkeypatch):
    from autoswe.vcs.worktree import _worktrees_root
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))
    import autoswe.vcs.worktree as wt_mod
    monkeypatch.setattr(wt_mod, "AUTOSWE_DIR", tmp_path)
    abs_dir = str(tmp_path / "custom_wt")
    result = _worktrees_root(_cfg(worktree_dir=abs_dir))
    assert result == Path(abs_dir)


def test_main_clone_path(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))
    import autoswe.vcs.worktree as wt
    from autoswe.vcs.worktree import main_clone_path
    monkeypatch.setattr(wt, "AUTOSWE_DIR", tmp_path)
    result = main_clone_path("owner", "repo", _cfg())
    assert result == tmp_path / "worktrees" / "owner_repo" / "_main"


def test_worktree_path(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))
    import autoswe.vcs.worktree as wt
    from autoswe.vcs.worktree import worktree_path
    monkeypatch.setattr(wt, "AUTOSWE_DIR", tmp_path)
    result = worktree_path("owner", "repo", 42, _cfg())
    assert result == tmp_path / "worktrees" / "owner_repo" / "issue-42"


# ---------------------------------------------------------------------------
# ensure_clone
# ---------------------------------------------------------------------------

def test_ensure_clone_creates_when_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))
    import autoswe.vcs.worktree as wt
    monkeypatch.setattr(wt, "AUTOSWE_DIR", tmp_path)

    run_calls = []

    def fake_run(args, cwd=None, check=True):
        run_calls.append(args)
        result = MagicMock()
        result.returncode = 0
        result.stdout = ""
        return result

    with patch("autoswe.vcs.worktree._run", side_effect=fake_run):
        from autoswe.vcs.worktree import ensure_clone
        main = tmp_path / "worktrees" / "o_r" / "_main"
        main.parent.mkdir(parents=True, exist_ok=True)
        # Make _main appear to exist so clone is skipped but remote update runs
        main.mkdir(exist_ok=True)

        # Second call — should update remote
        ensure_clone("o", "r", "token", _cfg(), base_branch="main")

    # Check that remote set-url was called
    assert any("set-url" in " ".join(c) for c in run_calls)


# ---------------------------------------------------------------------------
# create_worktree
# ---------------------------------------------------------------------------

def test_create_worktree_returns_path(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))
    import autoswe.vcs.worktree as wt
    monkeypatch.setattr(wt, "AUTOSWE_DIR", tmp_path)

    run_calls = []

    def fake_run(args, cwd=None, check=True):
        run_calls.append(args)
        result = MagicMock()
        result.stdout = ""  # No remote branch exists
        result.returncode = 0
        return result

    main = tmp_path / "worktrees" / "o_r" / "_main"
    main.mkdir(parents=True, exist_ok=True)
    wt_path = tmp_path / "worktrees" / "o_r" / "issue-1"

    with patch("autoswe.vcs.worktree._run", side_effect=fake_run):
        from autoswe.vcs.worktree import create_worktree
        result = create_worktree("o", "r", 1, "main", "token", _cfg())

    assert result == wt_path
    # Should have called worktree add
    assert any("worktree" in " ".join(c) for c in run_calls)


def test_create_worktree_reuses_existing(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))
    import autoswe.vcs.worktree as wt
    monkeypatch.setattr(wt, "AUTOSWE_DIR", tmp_path)

    main = tmp_path / "worktrees" / "o_r" / "_main"
    main.mkdir(parents=True, exist_ok=True)
    wt_path = tmp_path / "worktrees" / "o_r" / "issue-1"
    wt_path.mkdir(parents=True, exist_ok=True)

    with patch("autoswe.vcs.worktree._run") as mock_run:
        mock_run.return_value.returncode = 0
        from autoswe.vcs.worktree import create_worktree
        result = create_worktree("o", "r", 1, "main", "token", _cfg())

    assert result == wt_path
    # Should NOT have called git worktree add since path exists
    assert not any("worktree" in " ".join(str(c)) for c in mock_run.call_args_list)


# ---------------------------------------------------------------------------
# commit_and_push
# ---------------------------------------------------------------------------

def test_commit_and_push_returns_dict_on_changes(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))

    run_calls = []

    def fake_run(args, cwd=None, check=True):
        run_calls.append(args)
        result = MagicMock()
        cmd = " ".join(args)
        # diff --cached --quiet returns non-zero (changes exist)
        if "--cached" in cmd:
            result.returncode = 1
        else:
            result.returncode = 0
        # rev-parse --short returns a SHA
        if "rev-parse" in cmd:
            result.stdout = "abc1234"
        else:
            result.stdout = ""
        return result

    wt_dir = tmp_path / "worktree"
    wt_dir.mkdir()

    with patch("autoswe.vcs.worktree._run", side_effect=fake_run):
        from autoswe.vcs.worktree import commit_and_push
        result = commit_and_push(wt_dir, "o", "r", 1, "test commit", "main")

    assert result["committed"] is True
    assert result["commit_sha"] == "abc1234"
    assert result["branch"] == "autoswe/issue-1"
    # Should have committed
    assert any("commit" in " ".join(c) for c in run_calls)


def test_commit_and_push_returns_dict_no_changes(tmp_path, monkeypatch):
    """Verify no commit when working tree is clean."""
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))

    run_calls = []

    def fake_run(args, cwd=None, check=True):
        run_calls.append(args)
        result = MagicMock()
        cmd = " ".join(args)
        # diff --cached --quiet returns zero (no changes)
        if "--cached" in cmd:
            result.returncode = 0
        else:
            result.returncode = 0
        result.stdout = ""
        return result

    wt_dir = tmp_path / "worktree"
    wt_dir.mkdir()

    with patch("autoswe.vcs.worktree._run", side_effect=fake_run):
        from autoswe.vcs.worktree import commit_and_push
        result = commit_and_push(wt_dir, "o", "r", 1, "test commit", "main")

    assert result["committed"] is False


def test_commit_and_push_pushes_after_commit(tmp_path, monkeypatch):
    """Verify push command is issued after commit."""
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))

    call_order = []

    def fake_run(args, cwd=None, check=True):
        call_order.append(list(args))  # store copy of args list
        result = MagicMock()
        cmd_str = " ".join(args)
        if "--cached" in cmd_str:
            result.returncode = 1  # changes exist
        else:
            result.returncode = 0
        result.stdout = ""
        return result

    wt_dir = tmp_path / "worktree"
    wt_dir.mkdir()

    with patch("autoswe.vcs.worktree._run", side_effect=fake_run):
        from autoswe.vcs.worktree import commit_and_push
        commit_and_push(wt_dir, "o", "r", 1, "test commit", "main")

    # Find commit and push by checking each arg list element-by-element
    commit_idx = next((i for i, c in enumerate(call_order) if "commit" in c), None)
    push_idx = next((i for i, c in enumerate(call_order) if "push" in c), None)
    assert commit_idx is not None
    assert push_idx is not None
    assert commit_idx < push_idx


def test_commit_and_push_preserves_auto_commits(tmp_path, monkeypatch):
    """Auto-commits from Claude session should be preserved as a trail, not squashed.

    Regression test for #78: previously all auto-commits were squashed via
    `git reset --soft`. Now the last commit is amended with the proper message
    and all other auto-commits remain intact.
    """
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))

    call_order = []

    def fake_run(args, cwd=None, check=True):
        call_order.append(list(args))
        result = MagicMock()
        cmd_str = " ".join(args)
        # After fetch + reset-to-origin, there are 2 auto-commits from this session
        if "origin/autoswe/issue-1..HEAD" in cmd_str:
            result.stdout = "aaa1111 fix typo\nbbb2222 fix logic\n"
        elif "rev-parse" in cmd_str:
            result.stdout = "def9876"
        else:
            result.stdout = ""
        result.returncode = 0
        return result

    wt_dir = tmp_path / "worktree"
    wt_dir.mkdir()

    with patch("autoswe.vcs.worktree._run", side_effect=fake_run):
        from autoswe.vcs.worktree import commit_and_push
        result = commit_and_push(wt_dir, "o", "r", 1, "Fixes #1: autoswe automated fix", "main")

    assert result["committed"] is True
    assert result["commit_sha"] == "def9876"
    assert result["branch"] == "autoswe/issue-1"

    # Should use --amend (not --soft reset squash)
    amend_calls = [c for c in call_order if "--amend" in c]
    assert len(amend_calls) == 1, f"Expected one --amend call, got {len(amend_calls)}"
    # Must NOT contain a reset --soft (squash) call
    soft_reset_calls = [c for c in call_order if "reset" in c and "--soft" in c]
    assert len(soft_reset_calls) == 0, "Should NOT reset --soft (squash) — commits must be preserved"

    # Must force-push after amend
    push_calls = [c for c in call_order if "push" in c and "-f" in c]
    assert len(push_calls) == 1, "Should force-push after amending"

    # The amend message must be the proper one
    amend_msg = " ".join(amend_calls[0])
    assert "Fixes #1: autoswe automated fix" in amend_msg


def test_commit_and_push_amend_uses_correct_message(tmp_path, monkeypatch):
    """The amended commit message should match the msg parameter."""
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))

    call_order = []

    def fake_run(args, cwd=None, check=True):
        call_order.append(list(args))
        result = MagicMock()
        cmd_str = " ".join(args)
        if "origin/autoswe/issue-42..HEAD" in cmd_str:
            result.stdout = "ccc3333 initial fix\n"
        elif "rev-parse" in cmd_str:
            result.stdout = "abc1234"
        else:
            result.stdout = ""
        result.returncode = 0
        return result

    wt_dir = tmp_path / "worktree"
    wt_dir.mkdir()

    expected_msg = "Fixes #42: autoswe automated fix"

    with patch("autoswe.vcs.worktree._run", side_effect=fake_run):
        from autoswe.vcs.worktree import commit_and_push
        commit_and_push(wt_dir, "o", "r", 42, expected_msg, "main")

    amend_calls = [c for c in call_order if "--amend" in c]
    assert len(amend_calls) == 1
    assert "-m" in amend_calls[0]
    assert expected_msg in amend_calls[0]


def test_commit_and_push_multi_fix_preserves_history(tmp_path, monkeypatch):
    """A second /fix should not re-squash commits from a previous /fix.

    After reset-to-origin matches the remote (simulating a reused worktree),
    the ahead check compares against origin/{branch} — not origin/{base_branch} —
    so commits from prior /fix runs are not included in the squash/amend range.
    """
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))

    call_order = []

    def fake_run(args, cwd=None, check=True):
        call_order.append(list(args))
        result = MagicMock()
        cmd_str = " ".join(args)
        # Simulating: local was NOT behind remote (prior push already landed)
        if "HEAD..origin/autoswe/issue-1" in cmd_str:
            result.stdout = ""  # not behind
        # After fetch + no reset, there's ONE new commit from this session.
        # Crucially, the ahead check uses origin/{branch}, NOT origin/{base_branch}.
        # So even if origin/autoswe/issue-1 has 5 commits ahead of main,
        # origin/autoswe/issue-1..HEAD only shows the new session commits.
        if "origin/autoswe/issue-1..HEAD" in cmd_str:
            result.stdout = "ddd4444 second fix round\n"
        elif "rev-parse" in cmd_str:
            result.stdout = "abc1234"
        else:
            result.stdout = ""
        result.returncode = 0
        return result

    wt_dir = tmp_path / "worktree"
    wt_dir.mkdir()

    with patch("autoswe.vcs.worktree._run", side_effect=fake_run):
        from autoswe.vcs.worktree import commit_and_push
        result = commit_and_push(wt_dir, "o", "r", 1, "Fixes #1: autoswe automated fix", "main")

    assert result["committed"] is True

    # Should amend, not squash
    amend_calls = [c for c in call_order if "--amend" in c]
    assert len(amend_calls) == 1

    # The ahead check should target origin/{branch}, NOT origin/{base_branch}
    ahead_checks = [c for c in call_order
                    if "log" in c and "origin/autoswe/issue-1..HEAD" in " ".join(c)]
    assert len(ahead_checks) == 1
    # Must NOT check origin/main..HEAD (that would re-squash prior history)
    base_ahead_checks = [c for c in call_order
                         if "log" in c and "origin/main..HEAD" in " ".join(c)]
    assert len(base_ahead_checks) == 0, "Must not check origin/main..HEAD — would re-squash history"


# ---------------------------------------------------------------------------
# sync_branch
# ---------------------------------------------------------------------------

def test_sync_branch_returns_dict(tmp_path, monkeypatch):
    """sync_branch should return synced=True with branch name."""
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))

    run_calls = []

    def fake_run(args, cwd=None, check=True):
        run_calls.append(args)
        result = MagicMock()
        result.returncode = 0
        result.stdout = ""  # No commits ahead of base
        return result

    wt_dir = tmp_path / "worktree"
    wt_dir.mkdir()

    with patch("autoswe.vcs.worktree._run", side_effect=fake_run):
        from autoswe.vcs.worktree import sync_branch
        result = sync_branch(wt_dir, "o", "r", 1, "main")

    assert result["synced"] is True
    assert result["branch"] == "autoswe/issue-1"
    assert result["ahead"] == 0
    # Should have called fetch, reset --hard, merge (not rebase), and plain push (no --force)
    assert any("fetch" in " ".join(c) for c in run_calls)
    assert any("reset" in " ".join(c) and "--hard" in " ".join(c) for c in run_calls)
    assert any("merge" in " ".join(c) and "origin/main" in " ".join(c) for c in run_calls)
    assert any("push" in " ".join(c) for c in run_calls)
    # Must NOT force-push (merge is append-only)
    assert not any("push" in " ".join(c) and "--force" in " ".join(c) for c in run_calls)


def test_sync_branch_counts_ahead_commits(tmp_path, monkeypatch):
    """sync_branch should count commits ahead of base branch."""
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))

    def fake_run(args, cwd=None, check=True):
        result = MagicMock()
        result.returncode = 0
        cmd_str = " ".join(args)
        if "origin/main..HEAD" in cmd_str:
            result.stdout = "abc1234 fix login\n"  # 1 commit ahead
        else:
            result.stdout = ""
        return result

    wt_dir = tmp_path / "worktree"
    wt_dir.mkdir()

    with patch("autoswe.vcs.worktree._run", side_effect=fake_run):
        from autoswe.vcs.worktree import sync_branch
        result = sync_branch(wt_dir, "o", "r", 42, "main")

    assert result["ahead"] == 1
    assert result["branch"] == "autoswe/issue-42"


def test_sync_branch_resets_to_origin(tmp_path, monkeypatch):
    """sync_branch should reset hard to origin/branch before rebasing."""
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))

    run_calls = []

    def fake_run(args, cwd=None, check=True):
        run_calls.append(args)
        result = MagicMock()
        result.returncode = 0
        result.stdout = ""
        return result

    wt_dir = tmp_path / "worktree"
    wt_dir.mkdir()

    with patch("autoswe.vcs.worktree._run", side_effect=fake_run):
        from autoswe.vcs.worktree import sync_branch
        sync_branch(wt_dir, "o", "r", 7, "main")

    # Find the reset call — should reset to origin/branch before rebasing
    reset_calls = [c for c in run_calls if "reset" in c and "--hard" in c]
    assert len(reset_calls) == 1
    reset_args = " ".join(reset_calls[0])
    assert "origin/autoswe/issue-7" in reset_args


def test_sync_branch_merges_onto_base(tmp_path, monkeypatch):
    """sync_branch should merge the latest base branch into the issue branch."""
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))

    run_calls = []

    def fake_run(args, cwd=None, check=True):
        run_calls.append(args)
        result = MagicMock()
        result.returncode = 0
        result.stdout = ""
        return result

    wt_dir = tmp_path / "worktree"
    wt_dir.mkdir()

    with patch("autoswe.vcs.worktree._run", side_effect=fake_run):
        from autoswe.vcs.worktree import sync_branch
        sync_branch(wt_dir, "o", "r", 7, "develop")

    # Should merge origin/develop (not rebase)
    merge_calls = [c for c in run_calls if "merge" in c and "--abort" not in c]
    assert len(merge_calls) == 1
    assert "origin/develop" in " ".join(merge_calls[0])
    assert "--no-edit" in " ".join(merge_calls[0])


def test_sync_branch_conflict_left_in_place(tmp_path, monkeypatch):
    """sync_branch should leave merge conflicts in place (no abort) for caller to resolve."""
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))

    def fake_run(args, cwd=None, check=True):
        result = MagicMock()
        # Match "git merge" subcommand specifically (not rev-parse --git-path rebase-merge)
        is_merge_cmd = "merge" in args and "rev-parse" not in args
        if is_merge_cmd and "--abort" not in args and "--no-edit" in args:
            # Simulate merge conflict
            result.returncode = 1
            result.stdout = ""
            result.stderr = "CONFLICT: content conflict in src/main.py"
        elif "diff" in args and "--name-only" in args and "--diff-filter=U" in args:
            # Unmerged (conflicted) files
            result.returncode = 0
            result.stdout = "src/main.py\nREADME.md\n"
        else:
            result.returncode = 0
            result.stdout = ""
        return result

    wt_dir = tmp_path / "worktree"
    wt_dir.mkdir()

    with patch("autoswe.vcs.worktree._run", side_effect=fake_run):
        from autoswe.vcs.worktree import sync_branch
        result = sync_branch(wt_dir, "o", "r", 7, "main")

    assert result["synced"] is False
    assert result["conflict"] is True
    assert "merge conflict" in result["error"].lower()
    assert result["conflict_files"] == ["src/main.py", "README.md"]
    assert result["branch"] == "autoswe/issue-7"
    # Verify no merge --abort was called (conflict state left for caller)


def test_sync_branch_skips_reset_when_remote_ref_missing(tmp_path, monkeypatch):
    """sync_branch should skip reset --hard origin/{branch} when the remote
    ref doesn't exist (fresh branch not yet pushed). Regression test for #240.
    """
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))

    run_calls = []

    def fake_run(args, cwd=None, check=True):
        run_calls.append(list(args))
        result = MagicMock()
        cmd = " ".join(args)
        # show-ref --verify returns non-zero when the remote ref doesn't exist
        if "show-ref" in cmd and "--verify" in cmd:
            result.returncode = 1
            result.stdout = ""
        else:
            result.returncode = 0
            result.stdout = ""
        return result

    wt_dir = tmp_path / "worktree"
    wt_dir.mkdir()

    with patch("autoswe.vcs.worktree._run", side_effect=fake_run):
        from autoswe.vcs.worktree import sync_branch
        result = sync_branch(wt_dir, "o", "r", 1, "main")

    assert result["synced"] is True
    assert result["branch"] == "autoswe/issue-1"

    # Must have called show-ref --verify
    show_ref_calls = [c for c in run_calls if "show-ref" in c and "--verify" in c]
    assert len(show_ref_calls) >= 1, "Must check remote ref with show-ref"
    assert "refs/remotes/origin/autoswe/issue-1" in " ".join(show_ref_calls[0])

    # Must NOT have called reset --hard origin/autoswe/issue-1
    reset_to_origin_calls = [
        c for c in run_calls
        if "reset" in c and "--hard" in c and "origin/autoswe/issue-1" in " ".join(c)
    ]
    assert len(reset_to_origin_calls) == 0, \
        f"Should NOT reset when remote ref missing, got {len(reset_to_origin_calls)} reset calls"


def test_sync_branch_does_reset_when_remote_ref_exists(tmp_path, monkeypatch):
    """sync_branch should reset --hard origin/{branch} when the remote ref exists."""
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))

    run_calls = []

    def fake_run(args, cwd=None, check=True):
        run_calls.append(list(args))
        result = MagicMock()
        cmd = " ".join(args)
        # show-ref --verify returns zero when the remote ref exists
        if "show-ref" in cmd and "--verify" in cmd:
            result.returncode = 0
            result.stdout = "abc123 refs/remotes/origin/autoswe/issue-1\n"
        else:
            result.returncode = 0
            result.stdout = ""
        return result

    wt_dir = tmp_path / "worktree"
    wt_dir.mkdir()

    with patch("autoswe.vcs.worktree._run", side_effect=fake_run):
        from autoswe.vcs.worktree import sync_branch
        result = sync_branch(wt_dir, "o", "r", 1, "main")

    assert result["synced"] is True

    # Must have called show-ref --verify
    show_ref_calls = [c for c in run_calls if "show-ref" in c and "--verify" in c]
    assert len(show_ref_calls) >= 1, "Must check remote ref with show-ref"

    # Must have called reset --hard origin/autoswe/issue-1
    reset_to_origin_calls = [
        c for c in run_calls
        if "reset" in c and "--hard" in c and "origin/autoswe/issue-1" in " ".join(c)
    ]
    assert len(reset_to_origin_calls) == 1, \
        f"Should reset when remote ref exists, got {len(reset_to_origin_calls)} reset calls"


# ---------------------------------------------------------------------------
# Azure DevOps worktree paths
# ---------------------------------------------------------------------------

def test_azure_repo_dir_3part(tmp_path, monkeypatch):
    """Azure worktree dir uses org_proj_repo path when owner contains slash."""
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))
    import autoswe.vcs.worktree as wt
    from autoswe.vcs.worktree import _repo_dir
    monkeypatch.setattr(wt, "AUTOSWE_DIR", tmp_path)
    result = _repo_dir("natedorr/testProject", "testProject", _cfg(), provider="azure")
    assert result == tmp_path / "worktrees" / "natedorr_testProject_testProject"


def test_azure_main_clone_path(tmp_path, monkeypatch):
    """Azure main clone path includes org_proj_repo in the directory name."""
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))
    import autoswe.vcs.worktree as wt
    from autoswe.vcs.worktree import main_clone_path
    monkeypatch.setattr(wt, "AUTOSWE_DIR", tmp_path)
    result = main_clone_path("natedorr/testProject", "testProject", _cfg(), provider="azure")
    assert result == tmp_path / "worktrees" / "natedorr_testProject_testProject" / "_main"


def test_azure_worktree_path(tmp_path, monkeypatch):
    """Azure worktree path includes org_proj_repo in the directory name."""
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))
    import autoswe.vcs.worktree as wt
    from autoswe.vcs.worktree import worktree_path
    monkeypatch.setattr(wt, "AUTOSWE_DIR", tmp_path)
    result = worktree_path("natedorr/testProject", "testProject", 70, _cfg(), provider="azure")
    assert result == tmp_path / "worktrees" / "natedorr_testProject_testProject" / "issue-70"


def test_azure_ensure_clone_inline_repo_cfg(tmp_path, monkeypatch):
    """AzureVCS handles worktree.py's inline repo_cfg with owner/repo pattern.

    Regression test: worktree.py creates repo_cfg inline without org/project/pat,
    using owner/repo instead. AzureVCS must fall back to parsing from those fields.
    """
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))
    import autoswe.vcs.worktree as wt
    monkeypatch.setattr(wt, "AUTOSWE_DIR", tmp_path)

    run_calls = []

    def fake_run(args, cwd=None, check=True):
        run_calls.append(args)
        result = MagicMock()
        result.returncode = 0
        result.stdout = ""
        return result

    main = tmp_path / "worktrees" / "natedorr_testProject_testProject" / "_main"
    main.mkdir(parents=True, exist_ok=True)

    with patch("autoswe.vcs.worktree._run", side_effect=fake_run):
        from autoswe.vcs.worktree import ensure_clone
        ensure_clone(
            "natedorr/testProject", "testProject", "ado_pat_123",
            _cfg(), base_branch="main", provider="azure",
        )

    # The remote set-url call should use the correct URL (no triple slashes)
    set_url_calls = [c for c in run_calls if "set-url" in " ".join(c)]
    assert len(set_url_calls) >= 1
    url_in_call = " ".join(set_url_calls[0])
    assert "dev.azure.com///_git/" not in url_in_call
    assert "dev.azure.com/natedorr/testProject/_git/testProject" in url_in_call


# ---------------------------------------------------------------------------
# _get_default_branch
# ---------------------------------------------------------------------------

def test_get_default_branch_origin_head(tmp_path, monkeypatch):
    """_get_default_branch reads origin/HEAD symbolic ref."""
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))
    import autoswe.vcs.worktree as wt
    monkeypatch.setattr(wt, "AUTOSWE_DIR", tmp_path)

    def fake_run(args, cwd=None, check=True):
        result = MagicMock()
        cmd_str = " ".join(args)
        if "symbolic-ref" in cmd_str:
            result.returncode = 0
            result.stdout = "refs/heads/develop\n"
        else:
            result.returncode = 1
            result.stdout = ""
        return result

    main = tmp_path / "_main"
    main.mkdir(parents=True)

    with patch("autoswe.vcs.worktree._run", side_effect=fake_run):
        from autoswe.vcs.worktree import _get_default_branch
        result = _get_default_branch(main, "main")

    assert result == "develop"


def test_get_default_branch_fallback_to_base_branch(tmp_path, monkeypatch):
    """Falls back to base_branch when origin/HEAD is missing."""
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))
    import autoswe.vcs.worktree as wt
    monkeypatch.setattr(wt, "AUTOSWE_DIR", tmp_path)

    def fake_run(args, cwd=None, check=True):
        result = MagicMock()
        result.returncode = 1  # symbolic-ref fails
        result.stdout = ""
        return result

    main = tmp_path / "_main"
    main.mkdir(parents=True)

    with patch("autoswe.vcs.worktree._run", side_effect=fake_run):
        from autoswe.vcs.worktree import _get_default_branch
        result = _get_default_branch(main, "master")

    assert result == "master"


def test_get_default_branch_ls_remote_fallback(tmp_path, monkeypatch):
    """Checks main/master via ls-remote as last resort when base_branch is empty."""
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))
    import autoswe.vcs.worktree as wt
    monkeypatch.setattr(wt, "AUTOSWE_DIR", tmp_path)

    call_count = [0]

    def fake_run(args, cwd=None, check=True):
        call_count[0] += 1
        result = MagicMock()
        cmd_str = " ".join(args)
        if "symbolic-ref" in cmd_str:
            result.returncode = 1
            result.stdout = ""
        elif "ls-remote" in cmd_str and "main" in cmd_str:
            result.returncode = 0
            result.stdout = "abc123\trefs/heads/main\n"
        else:
            result.returncode = 1
            result.stdout = ""
        return result

    main = tmp_path / "_main"
    main.mkdir(parents=True)

    with patch("autoswe.vcs.worktree._run", side_effect=fake_run):
        from autoswe.vcs.worktree import _get_default_branch
        result = _get_default_branch(main, "")

    assert result == "main"


# ---------------------------------------------------------------------------
# ensure_clone with custom branch
# ---------------------------------------------------------------------------

def test_ensure_clone_custom_branch_uses_default(tmp_path, monkeypatch):
    """ensure_clone with a custom base_branch uses default_branch for _main checkout."""
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))
    import autoswe.vcs.worktree as wt
    monkeypatch.setattr(wt, "AUTOSWE_DIR", tmp_path)

    run_calls = []

    def fake_run(args, cwd=None, check=True):
        run_calls.append(list(args))
        result = MagicMock()
        result.returncode = 0
        result.stdout = ""
        return result

    main = tmp_path / "worktrees" / "o_r" / "_main"
    main.mkdir(parents=True, exist_ok=True)

    with patch("autoswe.vcs.worktree._run", side_effect=fake_run):
        from autoswe.vcs.worktree import ensure_clone
        ensure_clone("o", "r", "token", _cfg(), base_branch="custom-branch",
                     default_branch="main")

    # Verify checkout uses "main" not "custom-branch"
    checkout_calls = [c for c in run_calls if "checkout" in c]
    assert len(checkout_calls) == 1
    assert "main" in checkout_calls[0], \
        f"_main should checkout 'main', got: {checkout_calls[0]}"
    assert "custom-branch" not in checkout_calls[0]


# ---------------------------------------------------------------------------
# create_worktree with custom branch and default_branch
# ---------------------------------------------------------------------------

def test_create_worktree_custom_branch_does_not_crash(tmp_path, monkeypatch):
    """End-to-end: custom base_branch passed to create_worktree, ensure_clone uses default."""
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))
    import autoswe.vcs.worktree as wt
    monkeypatch.setattr(wt, "AUTOSWE_DIR", tmp_path)

    run_calls = []

    def fake_run(args, cwd=None, check=True):
        run_calls.append(list(args))
        result = MagicMock()
        result.stdout = ""  # No remote branch exists
        result.returncode = 0
        return result

    main = tmp_path / "worktrees" / "o_r" / "_main"
    main.mkdir(parents=True, exist_ok=True)

    with patch("autoswe.vcs.worktree._run", side_effect=fake_run):
        from autoswe.vcs.worktree import create_worktree
        create_worktree("o", "r", 1, "custom-branch", "token", _cfg(),
                        default_branch="main")

    # _main should be checked out to "main"
    checkout_calls = [c for c in run_calls if "checkout" in c]
    assert len(checkout_calls) == 1
    assert "main" in checkout_calls[0]

    # worktree add should reference "custom-branch" as source
    wt_calls = [c for c in run_calls if "worktree" in c]
    assert len(wt_calls) == 1
    assert "custom-branch" in " ".join(wt_calls[0])


def test_create_worktree_explicit_default_branch(tmp_path, monkeypatch):
    """Explicit default_branch param works correctly with master repo."""
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))
    import autoswe.vcs.worktree as wt
    monkeypatch.setattr(wt, "AUTOSWE_DIR", tmp_path)

    run_calls = []

    def fake_run(args, cwd=None, check=True):
        run_calls.append(list(args))
        result = MagicMock()
        result.stdout = ""
        result.returncode = 0
        return result

    main = tmp_path / "worktrees" / "o_r" / "_main"
    main.mkdir(parents=True, exist_ok=True)

    with patch("autoswe.vcs.worktree._run", side_effect=fake_run):
        from autoswe.vcs.worktree import create_worktree
        create_worktree("o", "r", 42, "develop", "token", _cfg(),
                        default_branch="master")

    # _main checkout should be "master"
    checkout_calls = [c for c in run_calls if "checkout" in c]
    assert len(checkout_calls) == 1
    assert "master" in checkout_calls[0]

    # worktree source should be "develop"
    wt_calls = [c for c in run_calls if "worktree" in c]
    assert "develop" in " ".join(wt_calls[0])


# ---------------------------------------------------------------------------
# pull_strategy in create_worktree

def test_create_worktree_pull_strategy_reset_on_reuse(tmp_path, monkeypatch):
    """When pull_strategy='reset' and worktree exists, should reset to origin/branch."""
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))
    import autoswe.vcs.worktree as wt
    monkeypatch.setattr(wt, "AUTOSWE_DIR", tmp_path)

    run_calls = []

    def fake_run(args, cwd=None, check=True):
        run_calls.append(list(args))
        result = MagicMock()
        result.stdout = ""
        result.returncode = 0
        return result

    main = tmp_path / "worktrees" / "o_r" / "_main"
    main.mkdir(parents=True, exist_ok=True)
    wt_path = tmp_path / "worktrees" / "o_r" / "issue-1"
    wt_path.mkdir()

    with patch("autoswe.vcs.worktree._run", side_effect=fake_run):
        from autoswe.vcs.worktree import create_worktree
        create_worktree("o", "r", 1, "main", "token", _cfg(), pull_strategy="reset")

    # Should have fetch + reset --hard (from _apply_pull_strategy)
    fetch_calls = [c for c in run_calls if "fetch" in c and "origin" in " ".join(c)]
    assert len(fetch_calls) >= 1, "Should fetch origin"
    reset_calls = [c for c in run_calls if "reset" in c and "--hard" in c]
    assert len(reset_calls) >= 1, "Should reset --hard to origin/branch"


def test_create_worktree_pull_strategy_merge_on_reuse(tmp_path, monkeypatch):
    """When pull_strategy='merge' and worktree exists, should merge origin/branch."""
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))
    import autoswe.vcs.worktree as wt
    monkeypatch.setattr(wt, "AUTOSWE_DIR", tmp_path)

    run_calls = []

    def fake_run(args, cwd=None, check=True):
        run_calls.append(list(args))
        result = MagicMock()
        result.stdout = ""
        result.returncode = 0
        return result

    main = tmp_path / "worktrees" / "o_r" / "_main"
    main.mkdir(parents=True, exist_ok=True)
    wt_path = tmp_path / "worktrees" / "o_r" / "issue-1"
    wt_path.mkdir()

    with patch("autoswe.vcs.worktree._run", side_effect=fake_run):
        from autoswe.vcs.worktree import create_worktree
        create_worktree("o", "r", 1, "main", "token", _cfg(), pull_strategy="merge")

    # Should have fetch + merge (from _apply_pull_strategy)
    merge_calls = [c for c in run_calls if "merge" in c and "--no-edit" in c]
    assert len(merge_calls) >= 1, "Should merge origin/branch"
    push_calls = [c for c in run_calls if "push" in c]
    assert len(push_calls) >= 1, "Clean merge should push"


def test_create_worktree_pull_strategy_merge_conflict(tmp_path, monkeypatch):
    """When pull_strategy='merge' produces conflicts, should NOT push and leave conflicted state."""
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))
    import autoswe.vcs.worktree as wt
    monkeypatch.setattr(wt, "AUTOSWE_DIR", tmp_path)

    call_count = [0]

    def fake_run(args, cwd=None, check=True):
        call_count[0] += 1
        result = MagicMock()
        cmd = " ".join(args)
        if "merge" in cmd and "--no-edit" in cmd and "origin/autoswe" in cmd:
            # Simulate merge conflict
            result.returncode = 1
            result.stdout = ""
            result.stderr = "CONFLICT: content conflict in src/main.py"
        elif "diff" in cmd and "--diff-filter=U" in cmd:
            result.returncode = 0
            result.stdout = "src/main.py\n"
        else:
            result.returncode = 0
            result.stdout = ""
        return result

    main = tmp_path / "worktrees" / "o_r" / "_main"
    main.mkdir(parents=True, exist_ok=True)
    wt_path = tmp_path / "worktrees" / "o_r" / "issue-1"
    wt_path.mkdir()

    with patch("autoswe.vcs.worktree._run", side_effect=fake_run):
        from autoswe.vcs.worktree import create_worktree, get_merge_conflict_files
        create_worktree("o", "r", 1, "main", "token", _cfg(), pull_strategy="merge")
        # After creation, the worktree should have conflict markers
        # The fake doesn't create real files, but get_merge_conflict_files should return the conflicted list
        conflicts = get_merge_conflict_files(wt_path)
        assert "src/main.py" in conflicts


def test_get_merge_conflict_files_empty(tmp_path, monkeypatch):
    """get_merge_conflict_files returns [] when no conflicts."""
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))

    def fake_run(args, cwd=None, check=True):
        result = MagicMock()
        result.stdout = ""
        result.returncode = 1
        return result

    wt_dir = tmp_path / "wt"
    wt_dir.mkdir()

    with patch("autoswe.vcs.worktree._run", side_effect=fake_run):
        from autoswe.vcs.worktree import get_merge_conflict_files
        result = get_merge_conflict_files(wt_dir)

    assert result == []


def test_get_merge_conflict_files_populated(tmp_path, monkeypatch):
    """get_merge_conflict_files returns file list during conflict."""
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))

    def fake_run(args, cwd=None, check=True):
        result = MagicMock()
        result.stdout = "src/a.py\nsrc/b.py\n"
        result.returncode = 0
        return result

    wt_dir = tmp_path / "wt"
    wt_dir.mkdir()

    with patch("autoswe.vcs.worktree._run", side_effect=fake_run):
        from autoswe.vcs.worktree import get_merge_conflict_files
        result = get_merge_conflict_files(wt_dir)

    assert "src/a.py" in result
    assert "src/b.py" in result


def test_commit_and_push_logs_agent_commits(tmp_path, monkeypatch):
    """commit_and_push should log agent commit SHAs when detected via log()."""
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))
    import autoswe.vcs.worktree as wt
    monkeypatch.setattr(wt, "AUTOSWE_DIR", tmp_path)

    log_calls = []

    def fake_log(msg):
        log_calls.append(msg)

    call_index = [0]
    def fake_run(args, cwd=None, check=True):
        call_index[0] += 1
        result = MagicMock()
        result.returncode = 0
        if "fetch" in args:
            result.stdout = ""
        elif "log" in args and ".." in " ".join(args):
            result.stdout = "abc1234 autoswe: agent commit\n"
        elif "rev-list" in args:
            result.stdout = "abc1234\n"
        elif "rev-parse" in args:
            result.stdout = "abc1234def5678\n"
        elif "commit" in args:
            result.stdout = ""
        elif "push" in args:
            result.stdout = ""
        return result

    wt_dir = tmp_path / "wt"
    wt_dir.mkdir()

    with patch("autoswe.vcs.worktree._run", side_effect=fake_run):
        with patch("autoswe.vcs.worktree.log", side_effect=fake_log):
            from autoswe.vcs.worktree import commit_and_push
            commit_and_push(wt_dir, "o", "r", 1, "test commit", "main")

    # Should have logged the detected agent commit SHA
    agent_log = [m for m in log_calls if "agent commit" in m]
    assert len(agent_log) == 1, f"Expected agent commit log, got: {log_calls}"
    assert "abc1234" in agent_log[0]



# ---------------------------------------------------------------------------
# commit_and_push merge-commit guard


def test_commit_and_push_skips_amend_for_merge_commit(tmp_path, monkeypatch):
    """When HEAD is a merge commit, commit_and_push should push without amending."""
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))

    call_order = []

    def fake_run(args, cwd=None, check=True):
        call_order.append(list(args))
        result = MagicMock()
        cmd_str = " ".join(args)
        if "origin/autoswe/issue-1..HEAD" in cmd_str:
            result.stdout = "aaa1111 merge commit\n"
        elif "rev-list" in cmd_str and "--parents" in cmd_str:
            # Simulate merge commit: hash + 2 parents = 3 items
            result.stdout = "aaa1111 bbb2222 ccc3333\n"
        elif "rev-parse" in cmd_str:
            result.stdout = "def9876"
        else:
            result.stdout = ""
        result.returncode = 0
        return result

    wt_dir = tmp_path / "worktree"
    wt_dir.mkdir()

    with patch("autoswe.vcs.worktree._run", side_effect=fake_run):
        from autoswe.vcs.worktree import commit_and_push
        result = commit_and_push(wt_dir, "o", "r", 1, "test msg", "main")

    assert result["committed"] is True
    # Must NOT contain --amend
    amend_calls = [c for c in call_order if "--amend" in c]
    assert len(amend_calls) == 0, f"Must NOT amend merge commit, got {len(amend_calls)} amend calls"
    # Must push
    push_calls = [c for c in call_order if "push" in c]
    assert len(push_calls) >= 1


def test_commit_and_push_amends_normal_commit(tmp_path, monkeypatch):
    """When HEAD is NOT a merge commit, should amend normally."""
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))

    call_order = []

    def fake_run(args, cwd=None, check=True):
        call_order.append(list(args))
        result = MagicMock()
        cmd_str = " ".join(args)
        if "origin/autoswe/issue-1..HEAD" in cmd_str:
            result.stdout = "aaa1111 normal commit\n"
        elif "rev-list" in cmd_str and "--parents" in cmd_str:
            # Simulate normal commit: hash + 1 parent = 2 items
            result.stdout = "aaa1111 bbb2222\n"
        elif "rev-parse" in cmd_str:
            result.stdout = "def9876"
        else:
            result.stdout = ""
        result.returncode = 0
        return result

    wt_dir = tmp_path / "worktree"
    wt_dir.mkdir()

    with patch("autoswe.vcs.worktree._run", side_effect=fake_run):
        from autoswe.vcs.worktree import commit_and_push
        result = commit_and_push(wt_dir, "o", "r", 1, "test msg", "main")

    assert result["committed"] is True
    amend_calls = [c for c in call_order if "--amend" in c]
    assert len(amend_calls) == 1, "Should amend a normal commit"


# ---------------------------------------------------------------------------
# sync_branch returns commit_sha and changed


def test_sync_branch_returns_commit_sha_and_changed(tmp_path, monkeypatch):
    """sync_branch should return commit_sha and changed keys."""
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))

    rev_parse_count = [0]

    def fake_run(args, cwd=None, check=True):
        rev_parse_count[0] += 1
        result = MagicMock()
        result.returncode = 0
        cmd_str = " ".join(args)
        if "origin/main..HEAD" in cmd_str:
            result.stdout = "abc1234 fix\n"
        elif "rev-parse" in cmd_str:
            result.stdout = "abc1234"
        elif "rev-parse" in cmd_str and "HEAD" in cmd_str:
            # First call returns one SHA, second returns different (changed=True)
            if rev_parse_count[0] <= 2:
                result.stdout = "aaa1111"
            else:
                result.stdout = "bbb2222"
        else:
            result.stdout = ""
        return result

    wt_dir = tmp_path / "worktree"
    wt_dir.mkdir()

    with patch("autoswe.vcs.worktree._run", side_effect=fake_run):
        from autoswe.vcs.worktree import sync_branch
        result = sync_branch(wt_dir, "o", "r", 1, "main")

    assert result["synced"] is True
    assert "commit_sha" in result
    assert result["commit_sha"] == "abc1234"
    assert "changed" in result
    assert isinstance(result["changed"], bool)


def test_sync_branch_unchanged(tmp_path, monkeypatch):
    """sync_branch changed=False when HEAD doesn't move."""
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))

    def fake_run(args, cwd=None, check=True):
        result = MagicMock()
        result.returncode = 0
        cmd_str = " ".join(args)
        if "origin/main..HEAD" in cmd_str:
            result.stdout = ""
        elif "rev-parse" in cmd_str:
            result.stdout = "aaa1111"
        elif "rev-parse" in cmd_str:
            result.stdout = "aaa1111"  # Same SHA before and after
        else:
            result.stdout = ""
        return result

    wt_dir = tmp_path / "worktree"
    wt_dir.mkdir()

    with patch("autoswe.vcs.worktree._run", side_effect=fake_run):
        from autoswe.vcs.worktree import sync_branch
        result = sync_branch(wt_dir, "o", "r", 1, "main")

    assert result["synced"] is True
    assert result["changed"] is False


# ---------------------------------------------------------------------------
# create_worktree push_new parameter


def test_create_worktree_push_new_pushes_on_first_create(tmp_path, monkeypatch):
    """When push_new=True and branch doesn't exist remotely, should push it after creation."""
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))
    import autoswe.vcs.worktree as wt
    monkeypatch.setattr(wt, "AUTOSWE_DIR", tmp_path)

    run_calls = []

    def fake_run(args, cwd=None, check=True):
        run_calls.append(list(args))
        result = MagicMock()
        result.stdout = ""  # No remote branch exists
        result.returncode = 0
        return result

    main = tmp_path / "worktrees" / "o_r" / "_main"
    main.mkdir(parents=True, exist_ok=True)

    with patch("autoswe.vcs.worktree._run", side_effect=fake_run):
        from autoswe.vcs.worktree import create_worktree
        create_worktree("o", "r", 1, "main", "token", _cfg(), push_new=True)

    # Should have worktree add + push -u
    push_calls = [c for c in run_calls if "push" in c and "-u" in c]
    assert len(push_calls) == 1, f"Expected one push -u call, got {len(push_calls)}: {run_calls}"
    assert "autoswe/issue-1" in " ".join(push_calls[0])


def test_create_worktree_push_new_no_push_on_reuse(tmp_path, monkeypatch):
    """When push_new=True but worktree already exists (reuse path), should NOT push."""
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))
    import autoswe.vcs.worktree as wt
    monkeypatch.setattr(wt, "AUTOSWE_DIR", tmp_path)

    run_calls = []

    def fake_run(args, cwd=None, check=True):
        run_calls.append(list(args))
        result = MagicMock()
        result.stdout = ""
        result.returncode = 0
        return result

    main = tmp_path / "worktrees" / "o_r" / "_main"
    main.mkdir(parents=True, exist_ok=True)
    wt_path = tmp_path / "worktrees" / "o_r" / "issue-1"
    wt_path.mkdir()

    with patch("autoswe.vcs.worktree._run", side_effect=fake_run):
        from autoswe.vcs.worktree import create_worktree
        create_worktree("o", "r", 1, "main", "token", _cfg(), push_new=True)

    # Reuse path: should NOT have any push calls (only fetch + reset from pull_strategy)
    push_calls = [c for c in run_calls if "push" in c]
    assert len(push_calls) == 0, f"Reuse path should not push, got {len(push_calls)} push calls"


def test_create_worktree_push_new_default_false(tmp_path, monkeypatch):
    """Default push_new=False should not push the branch."""
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))
    import autoswe.vcs.worktree as wt
    monkeypatch.setattr(wt, "AUTOSWE_DIR", tmp_path)

    run_calls = []

    def fake_run(args, cwd=None, check=True):
        run_calls.append(list(args))
        result = MagicMock()
        result.stdout = ""  # No remote branch exists
        result.returncode = 0
        return result

    main = tmp_path / "worktrees" / "o_r" / "_main"
    main.mkdir(parents=True, exist_ok=True)

    with patch("autoswe.vcs.worktree._run", side_effect=fake_run):
        from autoswe.vcs.worktree import create_worktree
        create_worktree("o", "r", 1, "main", "token", _cfg())  # Default push_new=False

    # Should NOT have any push calls
    push_calls = [c for c in run_calls if "push" in c]
    assert len(push_calls) == 0, f"Default behavior should not push, got {len(push_calls)} push calls"


# ---------------------------------------------------------------------------
# Batch 6 — Worktree failure modes

def test_ensure_clone_clone_fails_propagates(tmp_path, monkeypatch):
    """ensure_clone raises when git clone fails."""
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))
    import autoswe.vcs.worktree as wt
    monkeypatch.setattr(wt, "AUTOSWE_DIR", tmp_path)

    call_count = [0]
    def fake_run(args, cwd=None, check=True):
        call_count[0] += 1
        cmd = " ".join(args)
        if "clone" in cmd:
            raise RuntimeError("git clone failed")
        return MagicMock()

    # Do NOT create _main — triggers clone path
    with patch("autoswe.vcs.worktree._run", side_effect=fake_run):
        with patch("autoswe.vcs.worktree.log"):
            from autoswe.vcs.worktree import ensure_clone
            with pytest.raises(RuntimeError, match="git clone failed"):
                ensure_clone("o", "r", "token", _cfg(), base_branch="main")

    # Clone should have been attempted
    assert call_count[0] >= 1


def test_ensure_clone_fetch_fails(tmp_path, monkeypatch):
    """ensure_clone raises when fetch fails on existing clone."""
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))
    import autoswe.vcs.worktree as wt
    monkeypatch.setattr(wt, "AUTOSWE_DIR", tmp_path)

    call_order = []
    def fake_run(args, cwd=None, check=True):
        call_order.append(" ".join(args))
        cmd = " ".join(args)
        if "fetch" in cmd:
            raise RuntimeError("fetch failed: network unreachable")
        return MagicMock()

    main = tmp_path / "worktrees" / "o_r" / "_main"
    main.mkdir(parents=True, exist_ok=True)

    with patch("autoswe.vcs.worktree._run", side_effect=fake_run):
        with patch("autoswe.vcs.worktree.log"):
            from autoswe.vcs.worktree import ensure_clone
            with pytest.raises(RuntimeError, match="network unreachable"):
                ensure_clone("o", "r", "token", _cfg(), base_branch="main")

    # set-url runs first, then fetch fails
    assert any("set-url" in c for c in call_order)
    assert any("fetch" in c for c in call_order)


def test_ensure_clone_reset_hard_fails(tmp_path, monkeypatch):
    """ensure_clone raises when reset --hard fails."""
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))
    import autoswe.vcs.worktree as wt
    monkeypatch.setattr(wt, "AUTOSWE_DIR", tmp_path)

    call_count = [0]
    def fake_run(args, cwd=None, check=True):
        call_count[0] += 1
        cmd = " ".join(args)
        if "reset" in cmd and "--hard" in cmd:
            raise RuntimeError("reset failed: lock timeout")
        result = MagicMock()
        result.returncode = 0
        result.stdout = ""
        return result

    main = tmp_path / "worktrees" / "o_r" / "_main"
    main.mkdir(parents=True, exist_ok=True)

    with patch("autoswe.vcs.worktree._run", side_effect=fake_run):
        with patch("autoswe.vcs.worktree.log"):
            from autoswe.vcs.worktree import ensure_clone
            with pytest.raises(RuntimeError, match="lock timeout"):
                ensure_clone("o", "r", "token", _cfg(), base_branch="main")


def test_create_worktree_existing_branch_path(tmp_path, monkeypatch):
    """When branch exists remotely, worktree is added without -b flag."""
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))
    import autoswe.vcs.worktree as wt
    monkeypatch.setattr(wt, "AUTOSWE_DIR", tmp_path)

    run_calls = []
    def fake_run(args, cwd=None, check=True):
        run_calls.append(list(args))
        result = MagicMock()
        cmd = " ".join(args)
        # branch -r --list shows the branch exists
        if "branch -r" in cmd:
            result.stdout = "  origin/autoswe/issue-1\n"
        else:
            result.stdout = ""
        result.returncode = 0
        return result

    main = tmp_path / "worktrees" / "o_r" / "_main"
    main.mkdir(parents=True, exist_ok=True)

    with patch("autoswe.vcs.worktree._run", side_effect=fake_run):
        with patch("autoswe.vcs.worktree.log"):
            from autoswe.vcs.worktree import create_worktree
            create_worktree("o", "r", 1, "main", "token", _cfg())

    # worktree add should NOT use -b (branch exists)
    wt_calls = [c for c in run_calls if "worktree" in c]
    assert len(wt_calls) == 1
    assert "-b" not in wt_calls[0], "Should not use -b for existing branch"
    assert "autoswe/issue-1" in wt_calls[0]


def test_create_worktree_new_branch_uses_minus_b(tmp_path, monkeypatch):
    """When branch doesn't exist remotely, worktree is added with -b flag."""
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))
    import autoswe.vcs.worktree as wt
    monkeypatch.setattr(wt, "AUTOSWE_DIR", tmp_path)

    run_calls = []
    def fake_run(args, cwd=None, check=True):
        run_calls.append(list(args))
        result = MagicMock()
        result.stdout = ""  # No remote branch
        result.returncode = 0
        return result

    main = tmp_path / "worktrees" / "o_r" / "_main"
    main.mkdir(parents=True, exist_ok=True)

    with patch("autoswe.vcs.worktree._run", side_effect=fake_run):
        with patch("autoswe.vcs.worktree.log"):
            from autoswe.vcs.worktree import create_worktree
            create_worktree("o", "r", 1, "main", "token", _cfg())

    # worktree add should use -b (new branch)
    wt_calls = [c for c in run_calls if "worktree" in c]
    assert len(wt_calls) == 1
    assert "-b" in wt_calls[0], "Should use -b for new branch"
    assert "origin/main" in " ".join(wt_calls[0])


def test_commit_and_push_no_changes_returns_false(tmp_path, monkeypatch):
    """commit_and_push returns committed=False when working tree is clean."""
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))

    def fake_run(args, cwd=None, check=True):
        result = MagicMock()
        cmd = " ".join(args)
        if "--cached" in cmd and "--quiet" in cmd:
            result.returncode = 0  # No diff = clean
        else:
            result.returncode = 0
        result.stdout = ""
        return result

    wt_dir = tmp_path / "worktree"
    wt_dir.mkdir()

    with patch("autoswe.vcs.worktree._run", side_effect=fake_run):
        with patch("autoswe.vcs.worktree.log"):
            from autoswe.vcs.worktree import commit_and_push
            result = commit_and_push(wt_dir, "o", "r", 1, "test", "main")

    assert result["committed"] is False
    assert "commit_sha" not in result


def test_commit_and_push_push_fails_raises(tmp_path, monkeypatch):
    """commit_and_push raises when push fails."""
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))

    def fake_run(args, cwd=None, check=True):
        result = MagicMock()
        cmd = " ".join(args)
        if "--cached" in cmd and "--quiet" in cmd:
            result.returncode = 1  # Changes exist
        elif "push" in cmd:
            raise RuntimeError("push failed: rejected")
        result.returncode = 0
        result.stdout = "abc1234"
        return result

    wt_dir = tmp_path / "worktree"
    wt_dir.mkdir()

    with patch("autoswe.vcs.worktree._run", side_effect=fake_run):
        with patch("autoswe.vcs.worktree.log"):
            from autoswe.vcs.worktree import commit_and_push
            with pytest.raises(RuntimeError, match="rejected"):
                commit_and_push(wt_dir, "o", "r", 1, "test", "main")


def test_sync_branch_conflict_returns_conflict_files(tmp_path, monkeypatch):
    """sync_branch returns conflict=True and lists conflicted files."""
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))

    def fake_run(args, cwd=None, check=True):
        result = MagicMock()
        is_merge_cmd = "merge" in args and "rev-parse" not in args
        if is_merge_cmd and "--no-edit" in args and "origin/main" in args:
            result.returncode = 1
            result.stdout = ""
            result.stderr = "CONFLICT: content conflict in src/main.py"
        elif "diff" in args and "--diff-filter=U" in args:
            result.returncode = 0
            result.stdout = "src/main.py\nconfig.json\n"
        else:
            result.returncode = 0
            result.stdout = ""
        return result

    wt_dir = tmp_path / "worktree"
    wt_dir.mkdir()

    with patch("autoswe.vcs.worktree._run", side_effect=fake_run):
        with patch("autoswe.vcs.worktree.log"):
            from autoswe.vcs.worktree import sync_branch
            result = sync_branch(wt_dir, "o", "r", 7, "main")

    assert result["synced"] is False
    assert result["conflict"] is True
    assert result["conflict_files"] == ["src/main.py", "config.json"]
    assert "merge conflict" in result["error"].lower()
    assert result["branch"] == "autoswe/issue-7"


def test_sync_branch_push_fails_after_merge(tmp_path, monkeypatch):
    """sync_branch raises when push fails after successful merge."""
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))

    def fake_run(args, cwd=None, check=True):
        result = MagicMock()
        cmd = " ".join(args)
        if "push" in cmd and "origin" in cmd and "autoswe" in cmd:
            raise RuntimeError("push failed: protected branch")
        result.returncode = 0
        result.stdout = ""
        return result

    wt_dir = tmp_path / "worktree"
    wt_dir.mkdir()

    with patch("autoswe.vcs.worktree._run", side_effect=fake_run):
        with patch("autoswe.vcs.worktree.log"):
            from autoswe.vcs.worktree import sync_branch
            with pytest.raises(RuntimeError, match="protected branch"):
                sync_branch(wt_dir, "o", "r", 1, "main")


def test_sync_branch_no_conflict_pushes_plain(tmp_path, monkeypatch):
    """sync_branch uses plain push (no force) after clean merge."""
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))

    run_calls = []
    def fake_run(args, cwd=None, check=True):
        run_calls.append(list(args))
        result = MagicMock()
        result.returncode = 0
        result.stdout = ""
        return result

    wt_dir = tmp_path / "worktree"
    wt_dir.mkdir()

    with patch("autoswe.vcs.worktree._run", side_effect=fake_run):
        with patch("autoswe.vcs.worktree.log"):
            from autoswe.vcs.worktree import sync_branch
            sync_branch(wt_dir, "o", "r", 1, "main")

    push_calls = [c for c in run_calls if "push" in c]
    assert len(push_calls) >= 1
    # Should NOT force-push (merge is append-only)
    for c in push_calls:
        assert "-f" not in c and "--force" not in c, "Sync should use plain push, not force"


def test_commit_and_push_resets_when_behind_origin(tmp_path, monkeypatch):
    """When worktree is behind origin, commit_and_push resets to origin first."""
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))

    run_calls = []
    def fake_run(args, cwd=None, check=True):
        run_calls.append(list(args))
        result = MagicMock()
        cmd = " ".join(args)
        if "HEAD..origin/autoswe/issue-1" in cmd:
            result.stdout = "old1234 prior commit\n"  # Behind origin
        elif "origin/autoswe/issue-1..HEAD" in cmd:
            result.stdout = ""  # After reset, nothing ahead
        elif "--cached" in cmd:
            result.returncode = 0  # Clean after reset
        else:
            result.stdout = ""
        result.returncode = 0
        return result

    wt_dir = tmp_path / "worktree"
    wt_dir.mkdir()

    with patch("autoswe.vcs.worktree._run", side_effect=fake_run):
        with patch("autoswe.vcs.worktree.log"):
            from autoswe.vcs.worktree import commit_and_push
            result = commit_and_push(wt_dir, "o", "r", 1, "test", "main")

    # Should have done reset --hard to origin
    reset_calls = [c for c in run_calls if "reset" in c and "--hard" in c]
    assert len(reset_calls) >= 1
    assert result["committed"] is False


def test_get_merge_conflict_files_with_empty_lines(tmp_path, monkeypatch):
    """get_merge_conflict_files handles trailing newlines and empty lines."""
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))

    def fake_run(args, cwd=None, check=True):
        result = MagicMock()
        result.stdout = "src/a.py\n\nsrc/b.py\n\n"  # Empty lines
        result.returncode = 0
        return result

    wt_dir = tmp_path / "wt"
    wt_dir.mkdir()

    with patch("autoswe.vcs.worktree._run", side_effect=fake_run):
        from autoswe.vcs.worktree import get_merge_conflict_files
        result = get_merge_conflict_files(wt_dir)

    assert "src/a.py" in result
    assert "src/b.py" in result
    assert "" not in result  # No empty strings


def test_create_worktree_pull_strategy_none(tmp_path, monkeypatch):
    """pull_strategy='none' should not fetch or reset in the pull strategy phase.

    Note: ensure_clone still does its own fetch, but the pull_strategy phase
    should be a no-op.
    """
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))
    import autoswe.vcs.worktree as wt
    monkeypatch.setattr(wt, "AUTOSWE_DIR", tmp_path)

    run_calls = []
    def fake_run(args, cwd=None, check=True):
        run_calls.append(list(args))
        result = MagicMock()
        result.stdout = ""
        result.returncode = 0
        return result

    main = tmp_path / "worktrees" / "o_r" / "_main"
    main.mkdir(parents=True, exist_ok=True)
    wt_path = tmp_path / "worktrees" / "o_r" / "issue-1"
    wt_path.mkdir()

    with patch("autoswe.vcs.worktree._run", side_effect=fake_run):
        with patch("autoswe.vcs.worktree.log"):
            from autoswe.vcs.worktree import create_worktree
            create_worktree("o", "r", 1, "main", "token", _cfg(), pull_strategy="none")

    # ensure_clone fetches, but pull_strategy='none' should NOT do merge or push
    merge_calls = [c for c in run_calls if "merge" in c]
    push_calls = [c for c in run_calls if "push" in c]
    # worktree add should NOT be called (path exists, reuse path)
    wt_add_calls = [c for c in run_calls if "worktree" in c]
    assert len(wt_add_calls) == 0, "Reuse path should not add worktree"
    assert len(merge_calls) == 0, "pull_strategy=none should not merge"
    assert len(push_calls) == 0, "pull_strategy=none should not push"


# ------ Git operation errors --- ---


def test_ensure_clone_git_timeout(tmp_path, monkeypatch):
    """ensure_clone raises when git operation times out."""
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))
    import autoswe.vcs.worktree as wt
    monkeypatch.setattr(wt, "AUTOSWE_DIR", tmp_path)

    main = tmp_path / "worktrees" / "o_r" / "_main"
    main.mkdir(parents=True, exist_ok=True)

    def fake_run(args, cwd=None, check=True):
        raise RuntimeError("git command timed out")

    with patch("autoswe.vcs.worktree._run", side_effect=fake_run):
        with patch("autoswe.vcs.worktree.log"):
            from autoswe.vcs.worktree import ensure_clone
            with pytest.raises(RuntimeError, match="timed out"):
                ensure_clone("o", "r", "token", _cfg(), base_branch="main")


def test_sync_branch_git_error(tmp_path, monkeypatch):
    """sync_branch raises on unexpected git error."""
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))

    def fake_run(args, cwd=None, check=True):
        raise RuntimeError("git: unable to resolve reference")

    wt_dir = tmp_path / "worktree"
    wt_dir.mkdir()

    with patch("autoswe.vcs.worktree._run", side_effect=fake_run):
        with patch("autoswe.vcs.worktree.log"):
            from autoswe.vcs.worktree import sync_branch
            with pytest.raises(RuntimeError, match="unable to resolve"):
                sync_branch(wt_dir, "o", "r", 1, "main")


def test_commit_and_push_git_lock_timeout(tmp_path, monkeypatch):
    """commit_and_push raises when git lock is held by another process."""
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))

    def fake_run(args, cwd=None, check=True):
        raise RuntimeError("Could not lock ref 'HEAD': Unable to lock")

    wt_dir = tmp_path / "worktree"
    wt_dir.mkdir()

    with patch("autoswe.vcs.worktree._run", side_effect=fake_run):
        with patch("autoswe.vcs.worktree.log"):
            from autoswe.vcs.worktree import commit_and_push
            with pytest.raises(RuntimeError, match="lock"):
                commit_and_push(wt_dir, "o", "r", 1, "test", "main")


def test_commit_and_push_azure_provider(tmp_path, monkeypatch):
    """commit_and_push works with Azure provider branch naming."""
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))

    run_calls = []
    def fake_run(args, cwd=None, check=True):
        run_calls.append(list(args))
        result = MagicMock()
        cmd = " ".join(args)
        if "autoswe/issue-70" in cmd and "log" in cmd:
            result.stdout = ""  # Not behind/ahead
            result.returncode = 0
        elif "--cached" in cmd and "--quiet" in cmd:
            result.returncode = 1  # Changes exist
            result.stdout = ""
        elif "rev-parse" in cmd:
            result.stdout = "abc1234"
            result.returncode = 0
        else:
            result.stdout = ""
            result.returncode = 0
        return result

    wt_dir = tmp_path / "worktree"
    wt_dir.mkdir()

    with patch("autoswe.vcs.worktree._run", side_effect=fake_run):
        with patch("autoswe.vcs.worktree.log"):
            from autoswe.vcs.worktree import commit_and_push
            result = commit_and_push(wt_dir, "org/proj", "repo", 70, "test", "main", provider="azure")

    assert result["committed"] is True
    assert result["branch"] == "autoswe/issue-70"


# ---------------------------------------------------------------------------
# fast_forward_worktree


def test_fast_forward_worktree_noop_when_current(tmp_path, monkeypatch):
    """When worktree is already at origin/branch, fast_forward_worktree is a no-op."""
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))

    log_calls = []
    def fake_log(msg):
        log_calls.append(msg)

    def fake_run(args, cwd=None, check=True):
        result = MagicMock()
        cmd = " ".join(args)
        if "rev-parse" in cmd:
            result.stdout = "abc1234"
        elif "rev-list" in cmd and "HEAD.." in cmd:
            result.stdout = ""  # Not behind
        else:
            result.stdout = ""
        result.returncode = 0
        return result

    wt_dir = tmp_path / "wt"
    wt_dir.mkdir()

    with patch("autoswe.vcs.worktree._run", side_effect=fake_run):
        with patch("autoswe.vcs.worktree.log", side_effect=fake_log):
            from autoswe.vcs.worktree import fast_forward_worktree
            result = fast_forward_worktree(wt_dir, "autoswe/issue-1")

    assert result is True
    assert any("already up-to-date" in m for m in log_calls)


def test_fast_forward_worktree_advances_when_behind(tmp_path, monkeypatch):
    """When worktree is behind origin/branch, should fast-forward."""
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))

    log_calls = []
    def fake_log(msg):
        log_calls.append(msg)

    call_count = [0]
    def fake_run(args, cwd=None, check=True):
        call_count[0] += 1
        result = MagicMock()
        " ".join(args)
        if call_count[0] == 1:
            # First rev-parse --short HEAD
            result.stdout = "aaa1111"
        elif call_count[0] == 2:
            # fetch
            result.stdout = ""
        elif call_count[0] == 3:
            # rev-list HEAD..origin/branch
            result.stdout = "bbb2222\nccc3333\n"  # 2 commits behind
        elif call_count[0] == 4:
            # merge --ff-only
            result.stdout = ""
        elif call_count[0] == 5:
            # rev-parse --short HEAD (new)
            result.stdout = "ddd4444"
        else:
            result.stdout = ""
        result.returncode = 0
        return result

    wt_dir = tmp_path / "wt"
    wt_dir.mkdir()

    with patch("autoswe.vcs.worktree._run", side_effect=fake_run):
        with patch("autoswe.vcs.worktree.log", side_effect=fake_log):
            from autoswe.vcs.worktree import fast_forward_worktree
            result = fast_forward_worktree(wt_dir, "autoswe/issue-1")

    assert result is True
    assert any("Fast-forwarded" in m for m in log_calls)


def test_fast_forward_worktree_warns_on_conflict(tmp_path, monkeypatch):
    """When merge --ff-only fails (diverged history), should warn and return False."""
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))

    log_calls = []
    def fake_log(msg):
        log_calls.append(msg)

    call_count = [0]
    def fake_run(args, cwd=None, check=True):
        call_count[0] += 1
        result = MagicMock()
        " ".join(args)
        result.returncode = 0  # default
        result.stdout = ""
        result.stderr = ""
        if call_count[0] == 1:
            result.stdout = "aaa1111"
        elif call_count[0] == 2:
            pass  # fetch
        elif call_count[0] == 3:
            result.stdout = "bbb2222\n"  # behind
        elif call_count[0] == 4:
            # merge --ff-only fails (not fast-forwardable)
            result.returncode = 1
            result.stderr = "error: Merge requires branch 'current' to be updated by a fast-forward."
        return result

    wt_dir = tmp_path / "wt"
    wt_dir.mkdir()

    with patch("autoswe.vcs.worktree._run", side_effect=fake_run):
        with patch("autoswe.vcs.worktree.log", side_effect=fake_log):
            from autoswe.vcs.worktree import fast_forward_worktree
            result = fast_forward_worktree(wt_dir, "autoswe/issue-1")

    assert result is False
    assert any("Could not fast-forward" in m for m in log_calls)
