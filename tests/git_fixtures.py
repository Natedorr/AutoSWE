"""Real-git fixture builders for integration tests.

Creates bare remotes, working clones, and worktrees under a tmp_path.
Every git operation uses real ``git`` subprocess calls — no mocks.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


def _git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a git command in the given working directory."""
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        check=check,
        env={**os.environ, "GIT_EDITOR": ":"},
    )


def _git_global(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a git command without -C (operates on cwd)."""
    return subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        check=check,
        env={**os.environ, "GIT_EDITOR": ":"},
    )


class GitWorld:
    """A sandboxed git universe under one ``tmp_path``.

    Layout::

        <tmp_path>/
          remote/owner_repo.git              # bare repo (the "origin")
          worktrees/gh-owner_repo/_main      # main clone
          worktrees/gh-owner_repo/issue-N    # issue worktrees

    The constructor monkeypatches ``AUTOSWE_DIR`` and the GitHubProvider
    ``clone_url`` so that ``ensure_clone`` works without network access.
    """

    def __init__(self, tmp_path: Path, monkeypatch, owner: str = "test", repo: str = "testrepo"):
        self.tmp_path = tmp_path
        self.mp = monkeypatch
        self._owner = owner
        self._repo = repo
        self._default_branch = "main"

        # Directory layout
        self.remote_dir = tmp_path / "remote" / f"{self._owner}_{self._repo}.git"
        self._autoswe_dir = tmp_path / "autoswe"
        self._worktrees_dir = tmp_path / "worktrees"
        (self._autoswe_dir / "data").mkdir(parents=True, exist_ok=True)
        (self._autoswe_dir / "logs").mkdir(exist_ok=True)
        (self._autoswe_dir / "running").mkdir(exist_ok=True)
        (self._autoswe_dir / "config").mkdir(exist_ok=True)
        self._worktrees_dir.mkdir(parents=True, exist_ok=True)

        # Monkeypatch config paths so autoSWE uses our tmp_path
        import autoswe.core.config as cfg_mod
        import autoswe.core.queue_store as qs_mod

        self.mp.setenv("AUTOSWE_DIR", str(self._autoswe_dir))
        self.mp.setattr(cfg_mod, "AUTOSWE_DIR", self._autoswe_dir)
        self.mp.setattr(cfg_mod, "QUEUE_FILE", self._autoswe_dir / "data" / "queue.json")
        self.mp.setattr(cfg_mod, "RUNNING_DIR", self._autoswe_dir / "running")
        self.mp.setattr(cfg_mod, "LOGS_DIR", self._autoswe_dir / "logs")
        self.mp.setattr(cfg_mod, "CONFIG_FILE", self._autoswe_dir / "config" / "autoswe.env")
        self.mp.setattr(cfg_mod, "REPOS_CONFIG_FILE", self._autoswe_dir / "config" / "repos.json")

        self.mp.setattr(qs_mod, "AUTOSWE_DIR", self._autoswe_dir)
        self.mp.setattr(qs_mod, "QUEUE_FILE", self._autoswe_dir / "data" / "queue.json")

        # Patch worktree module
        import autoswe.vcs.worktree as wt_mod
        self.mp.setattr(wt_mod, "AUTOSWE_DIR", self._autoswe_dir)

        # Monkeypatch GitHubVCS.clone_url to return file:// path
        # (patched properly after init_remote, but set up a stub here)
        from autoswe.providers.github import vcs as gh_vcs

        def _fake_clone_url(_self, _repo_cfg: dict) -> str:
            return self.remote_url()

        self.mp.setattr(gh_vcs.GitHubVCS, "clone_url", _fake_clone_url)

    @property
    def owner(self) -> str:
        return self._owner

    @property
    def repo(self) -> str:
        return self._repo

    def remote_url(self) -> str:
        """Return file:// URL to the bare remote repo."""
        return f"file://{self.remote_dir.resolve()}"

    def cfg(self, sync_strategy: str = "merge") -> dict:
        """Return a pre-configured cfg dict pointing at our worktrees dir."""
        return {
            "WORKTREE_DIR": str(self._worktrees_dir),
            "SYNC_STRATEGY": sync_strategy,
        }

    # ------------------------------------------------------------------
    # Remote repo setup
    # ------------------------------------------------------------------

    def init_remote(self, *, default_branch: str = "main", initial_files: dict[str, str] | None = None) -> Path:
        """Create the bare remote repo and seed it with initial commits."""
        self._default_branch = default_branch
        self.remote_dir.mkdir(parents=True, exist_ok=True)

        _git(self.remote_dir, "init", "--bare", "--initial-branch", default_branch)

        # Create a temp clone to seed content
        temp_clone = self.tmp_path / "_temp_clone"
        _git_global("clone", str(self.remote_dir), str(temp_clone))
        _git(temp_clone, "config", "user.email", "test@test.com")
        _git(temp_clone, "config", "user.name", "Test")

        if initial_files:
            for path, content in initial_files.items():
                (temp_clone / path).parent.mkdir(parents=True, exist_ok=True)
                (temp_clone / path).write_text(content)
            _git(temp_clone, "add", "-A")
            _git(temp_clone, "commit", "-m", "Initial commit")
            _git(temp_clone, "push", "origin", default_branch)

        # Cleanup
        shutil.rmtree(temp_clone, ignore_errors=True)

        return self.remote_dir

    def push_commit_to_remote(self, branch: str, files: dict[str, str], message: str) -> str:
        """Push a new commit with given files to the remote on the specified branch.

        Returns the short SHA of the new commit.
        """
        temp_clone = self.tmp_path / "_push_clone"
        if not temp_clone.exists():
            _git_global("clone", str(self.remote_dir), str(temp_clone))
            _git(temp_clone, "config", "user.email", "test@test.com")
            _git(temp_clone, "config", "user.name", "Test")

        _git(temp_clone, "fetch", "origin")
        _git(temp_clone, "checkout", branch)

        for path, content in files.items():
            (temp_clone / path).parent.mkdir(parents=True, exist_ok=True)
            (temp_clone / path).write_text(content)

        _git(temp_clone, "add", "-A")
        _git(temp_clone, "commit", "-m", message)
        _git(temp_clone, "push", "origin", branch)

        sha_result = _git(temp_clone, "rev-parse", "--short", "HEAD")
        return sha_result.stdout.strip()

    def add_remote_branch(self, name: str, from_branch: str = "main") -> None:
        """Create a new remote branch from an existing branch."""
        temp_clone = self.tmp_path / "_branch_clone"
        if not temp_clone.exists():
            _git_global("clone", str(self.remote_dir), str(temp_clone))

        _git(temp_clone, "fetch", "origin")
        _git(temp_clone, "checkout", from_branch)
        _git(temp_clone, "checkout", "-b", name)
        _git(temp_clone, "push", "-u", "origin", name)

    # ------------------------------------------------------------------
    # Clone / worktree helpers (call production functions)
    # ------------------------------------------------------------------

    def make_main_clone(self) -> Path:
        """Invoke the production ensure_clone() and return the _main path."""
        from autoswe.vcs.worktree import ensure_clone, main_clone_path

        ensure_clone(
            self._owner, self._repo, "fake-token",
            self.cfg(), self._default_branch, "github",
        )
        main = main_clone_path(self._owner, self._repo, self.cfg(), "github")
        _git(main, "config", "user.email", "test@test.com")
        _git(main, "config", "user.name", "Test")
        return main

    def make_worktree(self, issue_num: int, *, base_branch: str = "main", pull_strategy: str = "reset") -> Path:
        """Invoke the production create_worktree() and return the worktree path."""
        from autoswe.vcs.worktree import create_worktree, worktree_path

        create_worktree(
            self._owner, self._repo, issue_num, base_branch,
            "fake-token", self.cfg(), "github",
            default_branch=self._default_branch,
            pull_strategy=pull_strategy,
            push_new=True,
        )
        return worktree_path(self._owner, self._repo, issue_num, self.cfg(), "github")

    # ------------------------------------------------------------------
    # Worktree manipulation helpers
    # ------------------------------------------------------------------

    def write(self, wt: Path, path: str, content: str) -> Path:
        """Write a file into the worktree. Returns the absolute file path."""
        fp = wt / path
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
        return fp

    def write_binary(self, wt: Path, path: str, data: bytes) -> Path:
        """Write binary content into the worktree."""
        fp = wt / path
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_bytes(data)
        return fp

    def delete_file(self, wt: Path, path: str) -> None:
        """Delete a file from the worktree."""
        (wt / path).unlink(missing_ok=True)

    def commit_in(self, wt: Path, message: str, *, files: dict[str, str] | None = None) -> str:
        """Optionally write files, stage everything, and commit. Returns short SHA."""
        if files:
            for path, content in files.items():
                self.write(wt, path, content)
        _git(wt, "add", "-A")
        _git(wt, "commit", "-m", message)
        sha_result = _git(wt, "rev-parse", "--short", "HEAD")
        return sha_result.stdout.strip()

    def branch_name(self, issue_num: int) -> str:
        """Return the autoswe branch name for an issue."""
        return f"autoswe/issue-{issue_num}"

    def worktree_path_for(self, issue_num: int) -> Path:
        """Return the expected worktree path for an issue."""
        return self._worktrees_dir / f"gh-{self._owner}_{self._repo}" / f"issue-{issue_num}"

    def main_clone_path(self) -> Path:
        """Return the expected _main clone path."""
        return self._worktrees_dir / f"gh-{self._owner}_{self._repo}" / "_main"

    # ------------------------------------------------------------------
    # State introspection
    # ------------------------------------------------------------------

    def _git_dir(self, wt: Path) -> Path | None:
        """Resolve the actual .git directory for a worktree or clone. Returns None if .git missing."""
        git_path = wt / ".git"
        if git_path.is_dir():
            return git_path
        if git_path.is_file():
            # Worktree: .git is a file like "gitdir: /path/to/main/.git/worktrees/<name>"
            try:
                content = git_path.read_text().strip()
                if content.startswith("gitdir: "):
                    return Path(content[len("gitdir: "):])
            except (FileNotFoundError, OSError):
                pass
        return None

    def merge_state(self, wt: Path) -> dict[str, Any]:
        """Return a flat dict describing the current worktree state.

        Keys:
            in_merge         - bool, MERGE_HEAD exists
            in_rebase        - bool, rebase-apply or rebase-merge exists
            has_conflicts    - bool, files with conflict markers
            conflicted_files - list[str], paths with U status
            head_sha         - str, short SHA of HEAD
            ahead_of_origin  - int, commits ahead of origin/branch
            behind_origin    - int, commits behind origin/branch
            is_detached      - bool, HEAD is not on a branch
            dirty            - bool, unstaged changes
            untracked        - list[str], untracked file paths
            untracked_files  - alias for untracked
            branch           - str, current branch name (or "" when detached)
        """
        git_dir = self._git_dir(wt)
        state: dict[str, Any] = {}

        # If .git is missing (stale worktree), return degraded state
        if git_dir is None:
            state["head_sha"] = ""
            state["is_detached"] = True
            state["branch"] = ""
            state["in_merge"] = False
            state["in_rebase"] = False
            state["has_conflicts"] = False
            state["conflicted_files"] = []
            state["ahead_of_origin"] = 0
            state["behind_origin"] = 0
            state["dirty"] = False
            state["untracked"] = []
            state["untracked_files"] = []
            return state

        # HEAD SHA
        sha_result = _git(wt, "rev-parse", "--short", "HEAD", check=False)
        state["head_sha"] = sha_result.stdout.strip() if sha_result.returncode == 0 else ""

        # Branch / detached check
        branch_result = _git(wt, "branch", "--show-current", check=False)
        branch = branch_result.stdout.strip() if branch_result.returncode == 0 else ""
        state["is_detached"] = not bool(branch)
        state["branch"] = branch

        # Merge in progress?
        state["in_merge"] = (git_dir / "MERGE_HEAD").exists()

        # Rebase in progress?
        state["in_rebase"] = (git_dir / "rebase-apply").exists() or (git_dir / "rebase-merge").exists()

        # Conflict files
        conflict_result = _git(wt, "diff", "--name-only", "--diff-filter=U", check=False)
        conflicted = [f.strip() for f in conflict_result.stdout.strip().split("\n") if f.strip()]
        state["has_conflicts"] = len(conflicted) > 0
        state["conflicted_files"] = conflicted

        # Ahead / behind of origin/branch
        if branch:
            ahead_result = _git(wt, "log", f"origin/{branch}..HEAD", "--oneline", check=False)
            behind_result = _git(wt, "log", f"HEAD..origin/{branch}", "--oneline", check=False)
            ahead_lines = [line for line in ahead_result.stdout.strip().split("\n") if line.strip()]
            behind_lines = [line for line in behind_result.stdout.strip().split("\n") if line.strip()]
            state["ahead_of_origin"] = len(ahead_lines)
            state["behind_origin"] = len(behind_lines)
        else:
            state["ahead_of_origin"] = 0
            state["behind_origin"] = 0

        # Dirty (unstaged changes)
        status_result = _git(wt, "status", "--porcelain", check=False)
        status_lines = status_result.stdout.strip().split("\n") if status_result.stdout.strip() else []
        state["dirty"] = any(line.startswith((" M", "M ")) for line in status_lines)

        # Untracked files
        state["untracked"] = [line[3:] for line in status_lines if line.startswith("??")]
        state["untracked_files"] = state["untracked"]

        return state

    def git_log(self, wt: Path, revision: str = "HEAD", max_count: int = 10) -> list[dict[str, str]]:
        """Return list of {sha, parents, message} for commits in revision."""
        result = _git(
            wt, "log", "-n", str(max_count), "--format=%h|%p|%s", revision, check=False,
        )
        commits = []
        if result.returncode == 0 and result.stdout.strip():
            for line in result.stdout.strip().split("\n"):
                parts = line.split("|", 2)
                if len(parts) == 3:
                    commits.append({
                        "sha": parts[0],
                        "parents": parts[1].split() if parts[1] else [],
                        "message": parts[2],
                    })
        return commits

    def is_merge_commit(self, wt: Path, sha: str = "HEAD") -> bool:
        """Check if a commit has more than one parent."""
        parents_output = _git(wt, "rev-list", "--parents", "-n", "1", sha).stdout.strip().split()
        return len(parents_output) > 2
