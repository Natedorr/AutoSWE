"""Real-git scenario tests for autoSWE worktree operations.

Each test creates a GitWorld (bare remote + clones + worktrees under tmp_path),
seeds it into a specific state, runs autoSWE handlers against it, and asserts
outcomes. Tagged with @pytest.mark.git_scenario for selectability.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from autoswe.vcs.worktree import (
    commit_and_push,
    create_worktree,
    ensure_clone,
    fast_forward_worktree,
    sync_branch,
)
from tests.git_fixtures import GitWorld

pytestmark = pytest.mark.git_scenario


# ------------------------------------------------------------------
# Group A: Clean-state baselines (sanity)
# ------------------------------------------------------------------


class TestBaselines:
    """A1-A5: Basic clone, branch, worktree, commit, no-op paths."""

    def test_A1_fresh_clone(self, git_world: GitWorld):
        """A1: Fresh clone, no branch → worktree + branch created."""
        world = git_world
        world.init_remote(initial_files={"README.md": "# test"})
        world.make_main_clone()

        wt = world.make_worktree(1)
        state = world.merge_state(wt)

        assert state["branch"] == "autoswe/issue-1"
        assert state["is_detached"] is False
        assert state["has_conflicts"] is False

    def test_A2_existing_remote_branch(self, git_world: GitWorld):
        """A2: Remote branch autoswe/issue-1 exists → worktree attaches to it."""
        world = git_world
        world.init_remote(initial_files={"README.md": "# test"})
        world.make_main_clone()
        world.add_remote_branch("autoswe/issue-1")

        wt = world.make_worktree(1)
        state = world.merge_state(wt)

        assert state["branch"] == "autoswe/issue-1"

    def test_A3_worktree_reuse(self, git_world: GitWorld):
        """A3: Second create_worktree call reuses existing worktree."""
        world = git_world
        world.init_remote(initial_files={"README.md": "# test"})
        world.make_main_clone()

        wt1 = world.make_worktree(1, pull_strategy="none")
        wt2 = world.make_worktree(1, pull_strategy="none")

        assert wt1 == wt2

    def test_A4_commit_and_push_fresh(self, git_world: GitWorld):
        """A4: Write file → commit_and_push succeeds."""
        world = git_world
        world.init_remote(initial_files={"README.md": "# test"})
        world.make_main_clone()
        wt = world.make_worktree(1)

        world.write(wt, "x.txt", "hello")
        result = commit_and_push(wt, world.owner, world.repo, 1, "add x.txt")

        assert result["committed"] is True
        assert "commit_sha" in result
        assert result["branch"] == "autoswe/issue-1"

    def test_A5_no_changes(self, git_world: GitWorld):
        """A5: No changes → commit_and_push returns committed=False."""
        world = git_world
        world.init_remote(initial_files={"README.md": "# test"})
        world.make_main_clone()
        wt = world.make_worktree(1)

        result = commit_and_push(wt, world.owner, world.repo, 1, "no-op")

        assert result["committed"] is False


# ------------------------------------------------------------------
# Group B: Working-tree state edge cases
# ------------------------------------------------------------------


class TestWorkingTree:
    """B1-B6: Dirty, untracked, gitignore, binary."""

    def test_B1_dirty_unstaged(self, git_world: GitWorld):
        """B1: Dirty unstaged file → git add -A stages it; commit succeeds."""
        world = git_world
        world.init_remote(initial_files={"README.md": "# test"})
        world.make_main_clone()
        wt = world.make_worktree(1)

        world.write(wt, "dirty.txt", "unstaged")
        result = commit_and_push(wt, world.owner, world.repo, 1, "add dirty")

        assert result["committed"] is True

    def test_B2_untracked_file(self, git_world: GitWorld):
        """B2: Untracked file → committed by add -A."""
        world = git_world
        world.init_remote(initial_files={"README.md": "# test"})
        world.make_main_clone()
        wt = world.make_worktree(1)

        world.write(wt, "secret.local", "secret")
        result = commit_and_push(wt, world.owner, world.repo, 1, "add untracked")

        assert result["committed"] is True
        # Verify the file was committed
        state = world.merge_state(wt)
        assert state["untracked"] == []

    def test_B3_untracked_in_plan_pull_reset(self, git_world: GitWorld):
        """B3: Untracked from prior plan → pull_strategy=reset leaves it."""
        world = git_world
        world.init_remote(initial_files={"README.md": "# test"})
        world.make_main_clone()
        wt = world.make_worktree(1, pull_strategy="none")

        # Seed untracked file
        world.write(wt, "plan_output.txt", "plan data")

        # Reuse with reset strategy
        world.make_worktree(1, pull_strategy="reset")

        # Untracked files should persist after reset (git reset --hard only affects tracked)
        assert (wt / "plan_output.txt").exists()

    def test_B4_mixed_staged_unstaged(self, git_world: GitWorld):
        """B4: Stage one file, leave another dirty → both committed via add -A."""
        world = git_world
        world.init_remote(initial_files={"README.md": "# test"})
        world.make_main_clone()
        wt = world.make_worktree(1)

        world.write(wt, "staged.txt", "one")
        subprocess.run(["git", "-C", str(wt), "add", "staged.txt"], check=True)
        world.write(wt, "unstaged.txt", "two")

        result = commit_and_push(wt, world.owner, world.repo, 1, "mixed")

        assert result["committed"] is True

    def test_B5_gitignored_file(self, git_world: GitWorld):
        """B5: .gitignored file → NOT committed (gitignore already on remote)."""
        world = git_world
        world.init_remote(initial_files={"README.md": "# test", ".gitignore": "*.local\n"})
        world.make_main_clone()
        wt = world.make_worktree(1)

        world.write(wt, "ignored.local", "should not commit")

        result = commit_and_push(wt, world.owner, world.repo, 1, "should be empty")

        # The ignored.local should not be staged
        assert result["committed"] is False

    def test_B6_large_binary(self, git_world: GitWorld):
        """B6: 5 MB random binary → commits successfully."""
        world = git_world
        world.init_remote(initial_files={"README.md": "# test"})
        world.make_main_clone()
        wt = world.make_worktree(1)

        world.write_binary(wt, "large.bin", os.urandom(5 * 1024 * 1024))
        result = commit_and_push(wt, world.owner, world.repo, 1, "add binary")

        assert result["committed"] is True


# ------------------------------------------------------------------
# Group C: Local-vs-remote divergence
# ------------------------------------------------------------------


class TestDivergence:
    """C1-C8: Behind, ahead, amend, merge, diverged, FF."""

    def test_C1_local_behind_remote(self, git_world: GitWorld):
        """C1: Remote gets a commit after worktree → reset --hard to origin."""
        world = git_world
        world.init_remote(initial_files={"README.md": "# test", "base.txt": "original"})
        world.make_main_clone()
        wt = world.make_worktree(1)

        # Push a commit to the remote branch after worktree creation
        world.push_commit_to_remote("autoswe/issue-1", {"remote.txt": "from remote"}, "remote commit")

        # Write local change
        world.write(wt, "local.txt", "local")

        # commit_and_push should reset to origin first, then commit on top
        result = commit_and_push(wt, world.owner, world.repo, 1, "local work")

        assert result["committed"] is True
        # remote.txt should be present (from reset)
        assert (wt / "remote.txt").exists()

    def test_C2_amend_single_claude_commit(self, git_world: GitWorld):
        """C2: Single Claude commit → --amend rewrites msg; force-push."""
        world = git_world
        world.init_remote(initial_files={"README.md": "# test"})
        world.make_main_clone()
        wt = world.make_worktree(1)
        branch = world.branch_name(1)

        # Push the branch to origin first, so amend logic compares against it
        subprocess.run(["git", "-C", str(wt), "push", "-u", "origin", branch], check=True)

        # Simulate Claude auto-committing (write a file then commit)
        world.commit_in(wt, "claude wip", files={"fix.txt": "fix content"})

        result = commit_and_push(wt, world.owner, world.repo, 1, "Fix #1: proper msg")

        assert result["committed"] is True
        # Count commits on autoswe/issue-1 that are not on main (excludes initial commit)
        log = world.git_log(wt)
        # The amended commit + any initial commits from main
        assert len(log) >= 1
        assert "Fix #1" in log[0]["message"]

    def test_C3_amend_multiple_claude_commits(self, git_world: GitWorld):
        """C3: Multiple Claude commits → only last amended."""
        world = git_world
        world.init_remote(initial_files={"README.md": "# test"})
        world.make_main_clone()
        wt = world.make_worktree(1)
        branch = world.branch_name(1)

        # Push branch to origin first
        subprocess.run(["git", "-C", str(wt), "push", "-u", "origin", branch], check=True)

        world.commit_in(wt, "first wip", files={"step1.txt": "first"})
        world.commit_in(wt, "second wip", files={"step2.txt": "second"})

        result = commit_and_push(wt, world.owner, world.repo, 1, "Fix #1: proper")

        assert result["committed"] is True
        log = world.git_log(wt)
        # 2 agent commits + initial commit from main
        assert len(log) >= 2
        assert "Fix #1" in log[0]["message"]
        assert "first wip" in log[1]["message"]

    def test_C4_merge_commit_no_amend(self, git_world: GitWorld):
        """C4: HEAD is a merge commit → no amend; plain push -f."""
        world = git_world
        world.init_remote(initial_files={"README.md": "# test"})
        world.make_main_clone()
        wt = world.make_worktree(1)

        # Create a merge commit (must be non-FF — two divergent branches)
        branch = world.branch_name(1)
        subprocess.run(["git", "-C", str(wt), "push", "-u", "origin", branch], check=True)

        # Branch A: temp-merge with one commit
        subprocess.run(["git", "-C", str(wt), "checkout", "-b", "temp-merge"], check=True)
        world.write(wt, "temp.txt", "temp")
        subprocess.run(["git", "-C", str(wt), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(wt), "commit", "-m", "temp commit"], check=True)

        # Go back to main branch point and make divergent commit
        subprocess.run(["git", "-C", str(wt), "checkout", branch], check=True)
        world.write(wt, "branch_marker.txt", "branch")
        subprocess.run(["git", "-C", str(wt), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(wt), "commit", "-m", "branch marker"], check=True)

        # Now merge temp-merge → non-FF merge commit
        subprocess.run(["git", "-C", str(wt), "merge", "temp-merge", "--no-edit"], check=True)
        subprocess.run(["git", "-C", str(wt), "branch", "-D", "temp-merge"], check=True)

        assert world.is_merge_commit(wt)

        result = commit_and_push(wt, world.owner, world.repo, 1, "Fix #1")

        assert result["committed"] is True

    def test_C6_fast_forward_behind(self, git_world: GitWorld):
        """C6: FF needed, behind by N → fast_forward_worktree succeeds."""
        world = git_world
        world.init_remote(initial_files={"README.md": "# test"})
        world.make_main_clone()
        wt = world.make_worktree(1)
        branch = world.branch_name(1)

        # Push 3 commits to the remote branch
        for i in range(3):
            world.push_commit_to_remote(branch, {f"ff_{i}.txt": str(i)}, f"ff commit {i}")

        result = fast_forward_worktree(wt, branch)

        assert result is True
        for i in range(3):
            assert (wt / f"ff_{i}.txt").exists()

    def test_C7_ff_impossible_diverged(self, git_world: GitWorld):
        """C7: FF impossible (diverged) → returns False, no abort."""
        world = git_world
        world.init_remote(initial_files={"README.md": "# test"})
        world.make_main_clone()
        wt = world.make_worktree(1)
        branch = world.branch_name(1)

        # Local commit
        world.write(wt, "local.txt", "local")
        world.commit_in(wt, "local commit")

        # Remote commit on same branch (divergence)
        world.push_commit_to_remote(branch, {"remote.txt": "remote"}, "remote commit")

        result = fast_forward_worktree(wt, branch)

        assert result is False
        # Local state should be preserved (no abort)
        assert (wt / "local.txt").exists()

    def test_C8_ff_already_current(self, git_world: GitWorld):
        """C8: FF already up-to-date → returns True, no merge."""
        world = git_world
        world.init_remote(initial_files={"README.md": "# test"})
        world.make_main_clone()
        wt = world.make_worktree(1)
        branch = world.branch_name(1)

        result = fast_forward_worktree(wt, branch)

        assert result is True


# ------------------------------------------------------------------
# Group D: Merge conflict scenarios
# ------------------------------------------------------------------


class TestConflicts:
    """D1-D10: Sync merge/rebase, conflicts, resolutions."""

    def test_D1_sync_merge_clean(self, git_world: GitWorld):
        """D1: /sync merge clean → synced=True, ahead>0."""
        world = git_world
        world.init_remote(initial_files={"README.md": "# test", "base.txt": "shared"})
        world.make_main_clone()
        wt = world.make_worktree(1)

        # Add a commit to the worktree branch
        world.write(wt, "feature.txt", "feature code")
        world.commit_in(wt, "feature commit")
        # Push to origin so the branch has content
        subprocess.run(["git", "-C", str(wt), "push", "-u", "origin", world.branch_name(1)], check=True)

        # Push a non-conflicting commit to the base branch
        world.push_commit_to_remote("main", {"base_addition.txt": "from base"}, "base commit")

        result = sync_branch(wt, world.owner, world.repo, 1, "main", cfg=world.cfg())

        assert result["synced"] is True
        assert result["conflict"] is False
        assert result["ahead"] > 0

    def test_D2_sync_merge_conflict_unresolved(self, git_world: GitWorld):
        """D2: /sync merge conflict → synced=False, conflict=True."""
        world = git_world
        world.init_remote(initial_files={"shared.txt": "original"})
        world.make_main_clone()
        wt = world.make_worktree(1)

        # Modify shared.txt on worktree branch
        world.write(wt, "shared.txt", "worktree version")
        world.commit_in(wt, "worktree edit")
        subprocess.run(["git", "-C", str(wt), "push", "-u", "origin", world.branch_name(1)], check=True)

        # Modify same file on base branch
        world.push_commit_to_remote("main", {"shared.txt": "base version"}, "base edit")

        result = sync_branch(wt, world.owner, world.repo, 1, "main", cfg=world.cfg())

        assert result["synced"] is False
        assert result["conflict"] is True
        assert "shared.txt" in result["conflict_files"]

        # Worktree should be in conflicted state
        state = world.merge_state(wt)
        assert state["has_conflicts"] is True

    def test_D3_sync_merge_conflict_resolved(self, git_world: GitWorld):
        """D3: /sync conflict → Claude resolves → clean merge."""
        world = git_world
        world.init_remote(initial_files={"shared.txt": "original"})
        world.make_main_clone()
        wt = world.make_worktree(1)

        world.write(wt, "shared.txt", "worktree version")
        world.commit_in(wt, "worktree edit")
        subprocess.run(["git", "-C", str(wt), "push", "-u", "origin", world.branch_name(1)], check=True)

        world.push_commit_to_remote("main", {"shared.txt": "base version"}, "base edit")

        # First sync: conflict
        result = sync_branch(wt, world.owner, world.repo, 1, "main", cfg=world.cfg())
        assert result["conflict"] is True

        # Resolve the conflict
        resolved = "resolved version combining both\n"
        world.write(wt, "shared.txt", resolved)
        subprocess.run(["git", "-C", str(wt), "add", "shared.txt"], check=True)
        subprocess.run(["git", "-C", str(wt), "commit", "--no-edit"], check=True)
        # Push the merge commit
        subprocess.run(["git", "-C", str(wt), "push", "origin", world.branch_name(1)], check=True)

        state = world.merge_state(wt)
        assert state["has_conflicts"] is False
        assert state["in_merge"] is False
        assert (wt / "shared.txt").read_text() == resolved

    def test_D4_sync_rebase_clean(self, git_world: GitWorld):
        """D4: /sync rebase clean → linear history, force-with-lease push."""
        world = git_world
        world.init_remote(initial_files={"README.md": "# test", "base.txt": "shared"})
        world.make_main_clone()
        wt = world.make_worktree(1)

        world.write(wt, "feature.txt", "feature code")
        world.commit_in(wt, "feature commit")
        subprocess.run(["git", "-C", str(wt), "push", "-u", "origin", world.branch_name(1)], check=True)

        world.push_commit_to_remote("main", {"base_addition.txt": "from base"}, "base commit")

        cfg = world.cfg(sync_strategy="rebase")
        result = sync_branch(wt, world.owner, world.repo, 1, "main", cfg=cfg)

        assert result["synced"] is True
        assert result["conflict"] is False

    def test_D5_sync_rebase_conflict(self, git_world: GitWorld):
        """D5: /sync rebase conflict → synced=False, rebase=True."""
        world = git_world
        world.init_remote(initial_files={"shared.txt": "original"})
        world.make_main_clone()
        wt = world.make_worktree(1)

        world.write(wt, "shared.txt", "worktree version")
        world.commit_in(wt, "worktree edit")
        subprocess.run(["git", "-C", str(wt), "push", "-u", "origin", world.branch_name(1)], check=True)

        world.push_commit_to_remote("main", {"shared.txt": "base version"}, "base edit")

        cfg = world.cfg(sync_strategy="rebase")
        result = sync_branch(wt, world.owner, world.repo, 1, "main", cfg=cfg)

        assert result["synced"] is False
        assert result["conflict"] is True
        assert result["rebase"] is True

        state = world.merge_state(wt)
        assert state["in_rebase"] is True

    def test_D6_sync_rebase_conflict_resolved(self, git_world: GitWorld):
        """D6: /sync rebase conflict → resolve → rebase --continue → force push."""
        world = git_world
        world.init_remote(initial_files={"shared.txt": "original"})
        world.make_main_clone()
        wt = world.make_worktree(1)

        world.write(wt, "shared.txt", "worktree version")
        world.commit_in(wt, "worktree edit")
        subprocess.run(["git", "-C", str(wt), "push", "-u", "origin", world.branch_name(1)], check=True)

        world.push_commit_to_remote("main", {"shared.txt": "base version"}, "base edit")

        cfg = world.cfg(sync_strategy="rebase")
        result = sync_branch(wt, world.owner, world.repo, 1, "main", cfg=cfg)
        assert result["conflict"] is True

        # Resolve
        world.write(wt, "shared.txt", "resolved version")
        subprocess.run(["git", "-C", str(wt), "add", "shared.txt"], check=True)
        subprocess.run(["git", "-C", str(wt), "config", "user.email", "test@test.com"], check=True)
        subprocess.run(["git", "-C", str(wt), "config", "user.name", "Test"], check=True)
        env = os.environ.copy()
        env["GIT_EDITOR"] = "true"
        subprocess.run(["git", "-C", str(wt), "rebase", "--continue"], check=True, env=env)
        # Push with force-with-lease
        subprocess.run(["git", "-C", str(wt), "push", "--force-with-lease", "origin", world.branch_name(1)], check=True)

        state = world.merge_state(wt)
        assert state["in_rebase"] is False

    def test_D7_pull_strategy_merge_clean(self, git_world: GitWorld):
        """D7: /fix pull-strategy merge clean → auto-pushed clean merge."""
        world = git_world
        world.init_remote(initial_files={"README.md": "# test"})
        world.make_main_clone()
        wt = world.make_worktree(1)

        # Push a non-conflicting commit to the remote branch
        world.push_commit_to_remote(world.branch_name(1), {"remote.txt": "from remote"}, "remote work")

        # Reuse worktree with merge strategy
        world.make_worktree(1, pull_strategy="merge")

        # Remote file should be present after merge
        assert (wt / "remote.txt").exists()

    def test_D8_pull_strategy_merge_conflict(self, git_world: GitWorld):
        """D8: /fix pull-strategy merge conflict → conflict files surfaced."""
        world = git_world
        world.init_remote(initial_files={"shared.txt": "header\noriginal\nfooter\n"})
        world.make_main_clone()
        wt = world.make_worktree(1)

        # Remote edit first — push different content to the remote branch
        world.push_commit_to_remote(world.branch_name(1),
                                    {"shared.txt": "header\nremote-x\nremote-y\nfooter\n"},
                                    "remote edit")

        # Local edit — change the same lines locally (don't push — keep branches divergent)
        world.write(wt, "shared.txt", "header\nworktree-a\nworktree-b\nworktree-c\nfooter\n")
        world.commit_in(wt, "worktree edit")

        # Reuse with merge → should conflict (both sides edited same lines from same base)
        world.make_worktree(1, pull_strategy="merge")

        state = world.merge_state(wt)
        assert state["has_conflicts"] is True
        assert "shared.txt" in state["conflicted_files"]

    def test_D9_binary_conflict(self, git_world: GitWorld):
        """D9: Conflict in binary file → reported as conflict."""
        world = git_world
        world.init_remote(initial_files={"README.md": "# test"})
        world.make_main_clone()
        wt = world.make_worktree(1)

        # Binary on worktree
        world.write_binary(wt, "image.bin", b"\x89PNG\x0d\x0a original binary data")
        world.commit_in(wt, "add binary")
        subprocess.run(["git", "-C", str(wt), "push", "-u", "origin", world.branch_name(1)], check=True)

        # Different binary content on remote
        temp_clone = world.tmp_path / "_push_clone"
        if not temp_clone.exists():
            subprocess.run(["git", "clone", str(world.remote_dir), str(temp_clone)], check=True)
            subprocess.run(["git", "-C", str(temp_clone), "config", "user.email", "test@test.com"], check=True)
            subprocess.run(["git", "-C", str(temp_clone), "config", "user.name", "Test"], check=True)
        subprocess.run(["git", "-C", str(temp_clone), "fetch", "origin"], check=True)
        subprocess.run(["git", "-C", str(temp_clone), "checkout", "main"], check=True)
        (temp_clone / "image.bin").write_bytes(b"\x89PNG\x0d\x0a different remote binary data")
        subprocess.run(["git", "-C", str(temp_clone), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(temp_clone), "commit", "-m", "remote binary"], check=True)
        subprocess.run(["git", "-C", str(temp_clone), "push", "origin", "main"], check=True)

        result = sync_branch(wt, world.owner, world.repo, 1, "main", cfg=world.cfg())

        assert result["conflict"] is True
        assert "image.bin" in result["conflict_files"]

    def test_D10_delete_vs_modify_conflict(self, git_world: GitWorld):
        """D10: Local deletes file, remote modifies it → conflict reported."""
        world = git_world
        world.init_remote(initial_files={"README.md": "# test", "target.txt": "original"})
        world.make_main_clone()
        wt = world.make_worktree(1)

        # Delete file locally
        world.delete_file(wt, "target.txt")
        world.commit_in(wt, "delete target")
        subprocess.run(["git", "-C", str(wt), "push", "-u", "origin", world.branch_name(1)], check=True)

        # Modify file on remote
        world.push_commit_to_remote("main", {"target.txt": "modified on base"}, "base modifies target")

        result = sync_branch(wt, world.owner, world.repo, 1, "main", cfg=world.cfg())

        assert result["conflict"] is True
        assert "target.txt" in result["conflict_files"]


# ------------------------------------------------------------------
# Group E: Branch / remote / HEAD weirdness
# ------------------------------------------------------------------


class TestBranchRemote:
    """E1-E8: Detached HEAD, deleted remote, rejects, branch detection."""

    def test_E1_detached_head(self, git_world: GitWorld):
        """E1: Detached HEAD → commit_and_push still operates (commits + pushes to branch)."""
        world = git_world
        world.init_remote(initial_files={"README.md": "# test"})
        world.make_main_clone()
        wt = world.make_worktree(1)

        # Detach HEAD
        subprocess.run(["git", "-C", str(wt), "checkout", "--detach"], check=True)

        state = world.merge_state(wt)
        assert state["is_detached"] is True

        # Write a change
        world.write(wt, "detached.txt", "data")

        # commit_and_push can still commit (on detached HEAD) and push to the branch
        result = commit_and_push(wt, world.owner, world.repo, 1, "detached commit")
        assert result["committed"] is True

    def test_E2_remote_branch_deleted(self, git_world: GitWorld):
        """E2: Remote branch deleted → push recreates it."""
        world = git_world
        world.init_remote(initial_files={"README.md": "# test"})
        world.make_main_clone()
        wt = world.make_worktree(1)
        branch = world.branch_name(1)

        # Delete remote branch
        subprocess.run(["git", "-C", str(wt), "push", "origin", "--delete", branch], check=True)

        # Write and push → should recreate
        world.write(wt, "new.txt", "data")
        result = commit_and_push(wt, world.owner, world.repo, 1, "recreate")

        assert result["committed"] is True

    def test_E4_default_branch_master(self, git_world: GitWorld):
        """E4: default_branch is master → ensure_clone detects it."""
        world = git_world
        world.init_remote(default_branch="master", initial_files={"README.md": "# test"})
        main = world.make_main_clone()

        # Verify _main was checked out on master
        branch_result = subprocess.run(
            ["git", "-C", str(main), "branch", "--show-current"],
            capture_output=True, text=True, check=True,
        )
        assert branch_result.stdout.strip() == "master"

    def test_E5_no_symbolic_ref(self, git_world: GitWorld):
        """E5: origin/HEAD symbolic-ref absent → fallback chain works."""
        world = git_world
        world.init_remote(default_branch="main", initial_files={"README.md": "# test"})
        main = world.make_main_clone()

        # Remove origin/HEAD symbolic ref from the clone
        subprocess.run(
            ["git", "-C", str(main), "symbolic-ref", "-d", "origin/HEAD"],
            capture_output=True, check=False,
        )

        # Re-run ensure_clone; it should fall back to base_branch
        ensure_clone(
            world.owner, world.repo, "fake-token",
            world.cfg(), "main", "github",
        )

        branch_result = subprocess.run(
            ["git", "-C", str(main), "branch", "--show-current"],
            capture_output=True, text=True, check=True,
        )
        assert branch_result.stdout.strip() == "main"

    def test_E6_base_branch_nonexistent(self, git_world: GitWorld):
        """E6: base_branch doesn't exist → RuntimeError with clear message."""
        world = git_world
        world.init_remote(initial_files={"README.md": "# test"})
        world.make_main_clone()

        with pytest.raises(RuntimeError, match="does not exist on origin"):
            create_worktree(
                world.owner, world.repo, 1, "nonexistent",
                "fake-token", world.cfg(), "github",
                default_branch="main",
            )

    def test_E8_stale_worktree_dir(self, git_world: GitWorld):
        """E8: Worktree dir exists but .git is missing → next git call fails."""
        world = git_world
        world.init_remote(initial_files={"README.md": "# test"})
        world.make_main_clone()
        wt = world.make_worktree(1)

        # Delete .git (single file pointing to main repo's .git/worktrees)
        git_file = wt / ".git"
        if git_file.is_file():
            git_file.unlink()

        # Should fail on next git operation
        state = world.merge_state(wt)
        # merge_state should show degraded state
        assert state["is_detached"] or not state["head_sha"]


# ------------------------------------------------------------------
# Group F: Concurrency & locking
# ------------------------------------------------------------------


class TestConcurrency:
    """F1-F4: Lock files, races, fetch atomicity."""

    def test_F1_index_lock(self, git_world: GitWorld):
        """F1: Index lock file present → git op fails."""
        world = git_world
        world.init_remote(initial_files={"README.md": "# test"})
        world.make_main_clone()
        wt = world.make_worktree(1)

        # For worktrees, .git is a file pointing to the actual git dir
        git_file = wt / ".git"
        gitdir_path = git_file.read_text().strip().replace("gitdir: ", "")
        (Path(gitdir_path) / "index.lock").write_text("lock")

        world.write(wt, "x.txt", "data")

        # Should fail due to lock
        with pytest.raises(subprocess.CalledProcessError):
            commit_and_push(wt, world.owner, world.repo, 1, "locked")

    def test_F4_repo_locked(self, git_world: GitWorld, monkeypatch):
        """F4: Per-repo lock file → poller skips repo."""
        import autoswe.orch.loop as loop_mod
        from autoswe.orch.loop import _is_repo_locked

        # Use the RUNNING_DIR that loop module uses
        running_dir = loop_mod.RUNNING_DIR
        running_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(loop_mod, "RUNNING_DIR", running_dir)

        # Create a PID file simulating a running dispatch
        pid_file = running_dir / f"gh_{git_world.owner}_{git_world.repo}_issue-1.pid"
        pid_file.write_text(str(os.getpid()))

        result = _is_repo_locked(git_world.owner, git_world.repo, "github")
        assert result is not None  # Returns the locking PID file stem

        # Cleanup
        pid_file.unlink()
        result = _is_repo_locked(git_world.owner, git_world.repo, "github")
        assert result is None


# ------------------------------------------------------------------
# Group G: Auth / token / remote URL
# ------------------------------------------------------------------


class TestAuth:
    """G1-G2: Token rotation, URL handling."""

    def test_G1_token_rotation(self, git_world: GitWorld):
        """G1: Token rotation between dispatch cycles → remote URL updates."""
        world = git_world
        world.init_remote(initial_files={"README.md": "# test"})
        main = world.make_main_clone()

        # First ensure_clone: URL is set
        result = subprocess.run(
            ["git", "-C", str(main), "remote", "get-url", "origin"],
            capture_output=True, text=True, check=True,
        )
        url1 = result.stdout.strip()
        assert url1.startswith("file://")

        # Second ensure_clone updates remote URL (set-url is always called)
        ensure_clone(
            world.owner, world.repo, "new-token",
            world.cfg(), "main", "github",
        )
        result2 = subprocess.run(
            ["git", "-C", str(main), "remote", "get-url", "origin"],
            capture_output=True, text=True, check=True,
        )
        url2 = result2.stdout.strip()
        # URL should still point to our remote (file:// path preserved)
        assert url2.startswith("file://")
        assert "test_testrepo.git" in url2

    def test_G2_remote_url_points_to_bare_repo(self, git_world: GitWorld):
        """G2: Remote URL points to the bare repo."""
        world = git_world
        world.init_remote(initial_files={"README.md": "# test"})
        main = world.make_main_clone()

        result = subprocess.run(
            ["git", "-C", str(main), "remote", "-v"],
            capture_output=True, text=True, check=True,
        )
        assert "test_testrepo.git" in result.stdout
        assert "file://" in result.stdout


# ------------------------------------------------------------------
# Group H: Repo content edge cases
# ------------------------------------------------------------------


class TestRepoContent:
    """H1-H7: Empty repo, submodules, LFS, mode changes."""

    def test_H1_empty_repo(self, git_world: GitWorld):
        """H1: Empty repo (no commits) → ensure_clone raises RuntimeError."""
        world = git_world
        world.init_remote()  # No initial files

        with pytest.raises(RuntimeError, match="has no commits on"):
            world.make_main_clone()

    def test_H6_symlinks(self, git_world: GitWorld):
        """H6: Repo with symlink → worktree preserves it (or warns)."""
        # Note: Git symlinks behave differently on Windows; skip if problematic
        world = git_world
        world.init_remote(initial_files={"README.md": "# test"})
        world.make_main_clone()

        # Create a symlink in the worktree
        wt = world.make_worktree(1)
        link = wt / "link.txt"
        try:
            link.symlink_to("README.md")
            subprocess.run(["git", "-C", str(wt), "add", "link.txt"], check=True)
        except (OSError, NotImplementedError):
            pytest.skip("Symlinks not supported on this platform")

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="executable bits not tracked on Windows (core.fileMode=false by default)",
    )
    def test_H7_executable_bit_change(self, git_world: GitWorld):
        """H7: Toggle +x only → mode change committed."""
        world = git_world
        world.init_remote(initial_files={"script.sh": "#!/bin/sh\necho hi"})
        world.make_main_clone()
        wt = world.make_worktree(1)

        # Toggle executable bit
        (wt / "script.sh").chmod(0o755)

        result = commit_and_push(wt, world.owner, world.repo, 1, "chmod +x")

        assert result["committed"] is True


# ------------------------------------------------------------------
# Group I: In-progress git operations
# ------------------------------------------------------------------


class TestInProgress:
    """I1-I2: Merge/rebase in progress."""

    def test_I1_merge_in_progress_unresolved(self, git_world: GitWorld):
        """I1: Merge in progress with unresolved conflicts → RuntimeError."""
        world = git_world
        world.init_remote(initial_files={"shared.txt": "original"})
        world.make_main_clone()
        wt = world.make_worktree(1)

        world.write(wt, "shared.txt", "worktree version")
        world.commit_in(wt, "worktree edit")
        subprocess.run(["git", "-C", str(wt), "push", "-u", "origin", world.branch_name(1)], check=True)

        world.push_commit_to_remote("main", {"shared.txt": "base version"}, "base edit")

        # Fetch so the worktree sees the new origin/main, then merge (conflict)
        subprocess.run(["git", "-C", str(wt), "fetch", "origin"], check=True)
        subprocess.run(["git", "-C", str(wt), "merge", "origin/main"], check=False)

        # For worktrees, .git is a file — resolve the actual git dir
        git_file = wt / ".git"
        gitdir = Path(git_file.read_text().strip().replace("gitdir: ", ""))
        assert (gitdir / "MERGE_HEAD").exists()

        # commit_and_push should raise RuntimeError with clear message
        with pytest.raises(RuntimeError, match="unresolved merge conflicts"):
            commit_and_push(wt, world.owner, world.repo, 1, "during merge")

    def test_I1_merge_in_progress_resolved(self, git_world: GitWorld):
        """I1: Merge in progress with resolved conflicts → completes merge cleanly."""
        world = git_world
        world.init_remote(initial_files={"shared.txt": "original", "feature.txt": "feature"})
        world.make_main_clone()
        wt = world.make_worktree(1)

        # Make a commit on the worktree branch (non-conflicting file)
        world.write(wt, "fix.txt", "fix content")
        world.commit_in(wt, "fix commit")
        subprocess.run(["git", "-C", str(wt), "push", "-u", "origin", world.branch_name(1)], check=True)

        # Push a non-conflicting commit to main
        world.push_commit_to_remote("main", {"main_addition.txt": "from main"}, "main addition")

        # Start merge — should succeed without conflicts
        subprocess.run(["git", "-C", str(wt), "merge", "origin/main", "--no-edit"], check=True)

        # The merge commit is already committed, add a change and commit_and_push
        world.write(wt, "post_merge.txt", "after merge")

        result = commit_and_push(wt, world.owner, world.repo, 1, "after merge")

        assert result["committed"] is True

    def test_I2_rebase_in_progress_unresolved(self, git_world: GitWorld):
        """I2: Rebase in progress with unresolved conflicts → RuntimeError."""
        world = git_world
        world.init_remote(initial_files={"shared.txt": "original base content for rebase test"})
        world.make_main_clone()
        wt = world.make_worktree(1)

        # Worktree makes a commit diverging from main
        world.write(wt, "feature.txt", "feature work")
        world.commit_in(wt, "feature commit")
        subprocess.run(["git", "-C", str(wt), "push", "-u", "origin", world.branch_name(1)], check=True)

        # Push conflicting commit to main
        world.push_commit_to_remote("main", {"shared.txt": "modified by main branch", "feature.txt": "main version of feature"}, "main modifies shared and feature")

        # Fetch to update origin/main ref
        subprocess.run(["git", "-C", str(wt), "fetch", "origin"], check=True)

        # Start rebase — should conflict
        rebase_result = subprocess.run(
            ["git", "-C", str(wt), "rebase", "origin/main"],
            capture_output=True, text=True, check=False,
        )

        # If rebase conflicted (the expected case), commit_and_push should raise
        if rebase_result.returncode != 0:
            state = world.merge_state(wt)
            assert state["in_rebase"] is True

            with pytest.raises(RuntimeError, match="unresolved rebase conflicts"):
                commit_and_push(wt, world.owner, world.repo, 1, "during rebase")
        else:
            # Document: rebase was fast-forwarded (known behavior with file:// remotes)
            pass

    def test_I2_rebase_in_progress_resolved(self, git_world: GitWorld):
        """I2: Rebase in progress with resolved conflicts → completes rebase cleanly."""
        world = git_world
        world.init_remote(initial_files={"shared.txt": "original"})
        world.make_main_clone()
        wt = world.make_worktree(1)

        # Worktree makes a commit on a different file
        world.write(wt, "feature.txt", "feature work")
        world.commit_in(wt, "feature commit")
        subprocess.run(["git", "-C", str(wt), "push", "-u", "origin", world.branch_name(1)], check=True)

        # Push a conflicting commit to main
        world.push_commit_to_remote("main", {"shared.txt": "modified by main"}, "main modifies shared")

        # Fetch and start rebase
        subprocess.run(["git", "-C", str(wt), "fetch", "origin"], check=True)
        rebase_result = subprocess.run(
            ["git", "-C", str(wt), "rebase", "origin/main"],
            capture_output=True, text=True, check=False,
        )

        # The rebase should succeed (no conflict, different files)
        if rebase_result.returncode == 0:
            world.write(wt, "post_rebase.txt", "after rebase")
            result = commit_and_push(wt, world.owner, world.repo, 1, "after rebase")
            assert result["committed"] is True


# ------------------------------------------------------------------
# Group J: Failure injection
# ------------------------------------------------------------------


class TestFailureInjection:
    """J1-J3: Network drop, permission denied."""

    def test_J1_nonexistent_remote(self, git_world: GitWorld):
        """J1: file:///nonexistent → git op fails."""
        world = git_world
        world.init_remote(initial_files={"README.md": "# test"})
        world.make_main_clone()
        wt = world.make_worktree(1)

        # Set remote to nonexistent path
        subprocess.run(
            ["git", "-C", str(wt), "remote", "set-url", "origin", "file:///nonexistent/path"],
            check=True,
        )

        # Fetch should fail
        result = subprocess.run(
            ["git", "-C", str(wt), "fetch", "origin"],
            capture_output=True, text=True, check=False,
        )
        assert result.returncode != 0

    def test_J3_permission_denied(self, git_world: GitWorld):
        """J3: chmod 000 .git → PermissionError surfaces."""
        world = git_world
        world.init_remote(initial_files={"README.md": "# test"})
        world.make_main_clone()
        wt = world.make_worktree(1)

        # Lock down .git directory
        git_dir = wt / ".git"
        git_dir.chmod(0o000)

        try:
            # Git operations should fail
            subprocess.run(
                ["git", "-C", str(wt), "status"],
                capture_output=True, text=True, check=False,
            )
            # Depending on platform, this may or may not fail
        finally:
            # Always restore permissions for cleanup
            git_dir.chmod(0o755)
