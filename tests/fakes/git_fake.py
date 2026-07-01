"""Mock for autoswe.vcs.worktree functions.

Records calls and returns scripted values.  Mocks at the worktree.py
function boundary rather than subprocess, so scenarios stay fast and
platform-independent.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


class GitFake:
    """Scripted git operations fake for worktree module.

    Attributes (mutable, for assertions):
        calls - list[dict]  every invocation (function name + args)
    """

    def __init__(self):
        self.calls: list[dict[str, Any]] = []
        self._worktree_paths: dict[str, Path] = {}
        self._branches: dict[str, str] = {}
        self._commits: list[dict[str, Any]] = []
        self._scripted_sync: list[dict] = []
        self._sync_index = 0
        self._scripted_commits: list[dict] = []
        self._commit_index = 0
        self._fail_creations: set[str] = set()

    def script_sync(self, result: dict) -> None:
        """Add a scripted result for the next sync_branch call."""
        self._scripted_sync.append(result)

    def script_commit(self, result: dict) -> None:
        """Add a scripted result for the next commit_and_push call."""
        self._scripted_commits.append(result)

    def script_create_fail(self, key: str) -> None:
        """Make the next create_worktree for *key* raise RuntimeError."""
        self._fail_creations.add(key)

    # ----- Replacements for worktree.py functions -----

    def worktree_path(self, owner: str, repo: str, issue_num: int,
                      cfg: dict, provider: str = "github") -> Path:
        """Pure computation — mirrors real worktree_path, just records the call.

        Returns a unique path guaranteed to NOT exist on disk, so that callers
        must call create_worktree() first (matching real-world behaviour).
        """
        import uuid
        self.calls.append({"func": "worktree_path", "owner": owner, "repo": repo,
                           "issue_num": issue_num, "provider": provider})
        key = f"{owner}/{repo}/{issue_num}"
        if key not in self._worktree_paths:
            self._worktree_paths[key] = Path(
                "/tmp/autoswe-fake-wt-nonexistent-" + uuid.uuid4().hex[:12]
            )
        return self._worktree_paths[key]

    def main_clone_path(self, owner: str, repo: str, cfg: dict,
                        provider: str = "github") -> Path:
        self.calls.append({"func": "main_clone_path", "owner": owner, "repo": repo,
                           "provider": provider})
        return Path(f"/tmp/fake-wt/{owner}/{repo}/_main")

    def ensure_clone(self, owner: str, repo: str, token: str, cfg: dict,
                     base_branch: str = "main", provider: str = "github",
                     default_branch: str | None = None) -> None:
        self.calls.append({"func": "ensure_clone", "owner": owner, "repo": repo,
                           "base_branch": base_branch, "provider": provider})

    def create_worktree(self, owner: str, repo: str, issue_num: int,
                        base_branch: str, token: str, cfg: dict,
                        provider: str = "github", default_branch: str | None = None,
                        pull_strategy: str = "reset", push_new: bool = False) -> Path:
        key = f"{owner}/{repo}/{issue_num}"
        self.calls.append({"func": "create_worktree", "owner": owner, "repo": repo,
                           "issue_num": issue_num, "base_branch": base_branch,
                           "provider": provider, "pull_strategy": pull_strategy})
        if key in self._fail_creations:
            raise RuntimeError(f"scripted worktree creation failure for {key}")
        wt = self.worktree_path(owner, repo, issue_num, cfg, provider)
        self._branches[key] = f"autoswe/issue-{issue_num}"
        wt.mkdir(parents=True, exist_ok=True)
        return wt

    def commit_and_push(self, wt: Path, owner: str, repo: str, issue_num: int,
                        msg: str, base_branch: str = "main",
                        provider: str = "github") -> dict:
        self.calls.append({"func": "commit_and_push", "wt": str(wt), "owner": owner,
                           "repo": repo, "issue_num": issue_num, "msg": msg,
                           "base_branch": base_branch, "provider": provider})
        result = (self._scripted_commits[self._commit_index]
                  if self._commit_index < len(self._scripted_commits)
                  else {"committed": True, "commit_sha": "abc1234",
                        "branch": f"autoswe/issue-{issue_num}"})
        self._commit_index += 1
        self._commits.append({"msg": msg, "result": result})
        return result

    def sync_branch(self, wt: Path, owner: str, repo: str, issue_num: int,
                    base_branch: str = "main", provider: str = "github", cfg: dict | None = None) -> dict:
        self.calls.append({"func": "sync_branch", "wt": str(wt), "owner": owner,
                           "repo": repo, "issue_num": issue_num,
                           "base_branch": base_branch, "provider": provider})
        result = (self._scripted_sync[self._sync_index]
                  if self._sync_index < len(self._scripted_sync)
                  else {"synced": True, "conflict": False,
                        "branch": f"autoswe/issue-{issue_num}", "ahead": 1,
                        "commit_sha": "abc1234", "changed": True})
        self._sync_index += 1
        return result

    def get_merge_conflict_files(self, wt: Path) -> list[str]:
        self.calls.append({"func": "get_merge_conflict_files", "wt": str(wt)})
        return []

    # ----- Patching -----

    _real_worktree_funcs = None  # Class-level cache of real worktree functions
    _WORKTREE_FUNC_NAMES = (
        "worktree_path", "main_clone_path", "ensure_clone",
        "create_worktree", "commit_and_push", "sync_branch",
    )

    @classmethod
    def _get_real_funcs(cls):
        """Return the real worktree functions, cached on first call.

        The cache is populated by patch() before it replaces module attributes,
        so it always contains the genuine functions.
        """
        if cls._real_worktree_funcs is None:
            import autoswe.vcs.worktree as wt_mod
            cls._real_worktree_funcs = {
                name: getattr(wt_mod, name) for name in cls._WORKTREE_FUNC_NAMES
            }
        return cls._real_worktree_funcs

    def patch(self):
        """Patch into autoswe.vcs.worktree.  Returns (module, dict_of_originals)."""
        import autoswe.vcs.worktree as wt_mod

        # Cache originals BEFORE replacing module attributes
        # so _get_real_funcs() always returns the genuine functions.
        self.__class__._get_real_funcs()
        originals = {name: getattr(wt_mod, name) for name in self._WORKTREE_FUNC_NAMES}

        wt_mod.worktree_path = self.worktree_path
        wt_mod.main_clone_path = self.main_clone_path
        wt_mod.ensure_clone = self.ensure_clone
        wt_mod.create_worktree = self.create_worktree
        wt_mod.commit_and_push = self.commit_and_push
        wt_mod.sync_branch = self.sync_branch

        # Patch into modules that import worktree
        import sys as _sys
        for mod_name in ("autoswe.harness.planner", "autoswe.harness.coder", "autoswe.orch.run",
                         "autoswe.vcs.pr_gate"):
            if mod_name in _sys.modules:
                mod = _sys.modules[mod_name]
                if hasattr(mod, "worktree_mod") or hasattr(mod, "worktree"):
                    for attr in ("worktree_mod", "worktree"):
                        if hasattr(mod, attr):
                            submodule = getattr(mod, attr)
                            for func_name in originals:
                                if hasattr(submodule, func_name):
                                    setattr(submodule, func_name, getattr(self, func_name))

        return wt_mod, originals

    def unpatch(self, module, originals: dict) -> None:
        """Restore worktree functions, always using the cached real functions."""
        real_funcs = self._get_real_funcs()
        for func_name in self._WORKTREE_FUNC_NAMES:
            setattr(module, func_name, real_funcs[func_name])
