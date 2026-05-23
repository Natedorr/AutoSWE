# Git Worktrees

These are plain `git worktree`s — one working tree per issue, all sharing a single clone per repo. No custom concept here; the only conventions autoSWE adds are the directory layout and the `autoswe/issue-{N}` branch name.

## Directory Structure

```
{WORKTREE_DIR}/                          # default: {AUTOSWE_DIR}/worktrees/
  gh-owner_repo/                         # GitHub: provider-prefixed dir
    _main/                               # Canonical clone, always on base_branch, never edited by Claude
    issue-42/                            # Worktree for issue #42, branch: autoswe/issue-42
    issue-103/
  ado-org_proj_repo/                     # Azure: provider-prefixed dir
    _main/
    issue-7/
```

Path helpers (`vcs/worktree.py`):
- `_worktrees_root(cfg)` — resolves `WORKTREE_DIR` (absolute or relative to `AUTOSWE_DIR`)
- `_repo_dir(owner, repo, cfg, provider)` — per-repo directory (provider-prefixed)
- `main_clone_path(owner, repo, cfg, provider)` — `_repo_dir / "_main"`
- `worktree_path(owner, repo, issue_num, cfg, provider)` — `_repo_dir / "issue-{N}"`

## Lifecycle

### `ensure_clone(owner, repo, token, cfg, base_branch, provider)`

1. If `_main/` doesn't exist → `git clone` via VCS `clone_url()` (token embedded)
2. If `_main/` exists → `git remote set-url origin <url>` (keeps token current), then `fetch + checkout base_branch + reset --hard origin/{base_branch}`

### `create_worktree(owner, repo, issue_num, base_branch, token, cfg, provider)`

1. Calls `ensure_clone()` first
2. If worktree path exists → reuse it (no-op)
3. Checks if branch `autoswe/issue-{N}` exists on remote via VCS `branch_name()`
4. If branch exists → `git worktree add <path> <branch>`
5. If branch doesn't exist → `git worktree add <path> -b autoswe/issue-{N} origin/{base_branch}`

### `commit_and_push(wt, owner, repo, issue_num, msg, base_branch, provider)`

1. Fetch latest remote state
2. If local branch is behind remote (`HEAD..origin/{branch}`) → `reset --hard origin/{branch}`
3. If HEAD ahead of `origin/{branch}` (Claude auto-committed during this session) → amend the last commit's message with the proper "Fixes #N" message, preserving all other auto-commits as a commit trail
4. Otherwise → `git add -A`, check diff, commit, push `-u origin <branch>`
5. Returns `{"committed": bool, "commit_sha": str, "branch": str}`

### `sync_branch(wt, owner, repo, issue_num, base_branch, provider, cfg)`

Strategy is controlled by `cfg["SYNC_STRATEGY"]` (default: `"merge"`).

**Merge strategy** (`SYNC_STRATEGY=merge`, default):

1. `git fetch origin`
2. `git show-ref --verify refs/remotes/origin/{branch}` — check if remote ref exists
3. If remote ref exists → `git reset --hard origin/{branch}` (match remote before merge)
4. If remote ref doesn't exist → skip reset (fresh branch not yet pushed; see #240)
5. `git merge --no-edit origin/{base_branch}`
6. On success → `git push origin <branch>`, return `{"synced": True, "conflict": False, "branch": ..., "ahead": N}`
7. On conflict → leave worktree in conflicted state, return `{"synced": False, "conflict": True, "branch": ..., "conflict_files": [...]}`

**Rebase strategy** (`SYNC_STRATEGY=rebase`):

1. `git fetch origin`
2. `git show-ref --verify refs/remotes/origin/{branch}` — check if remote ref exists
3. If remote ref exists → `git reset --hard origin/{branch}` (match remote before rebase)
4. If remote ref doesn't exist → skip reset (fresh branch not yet pushed)
5. `git rebase origin/{base_branch}`
6. On success → `git push --force-with-lease origin <branch>`, return `{"synced": True, "conflict": False, "branch": ..., "ahead": N}`
7. On conflict → leave worktree in rebase-in-progress state, return `{"synced": False, "conflict": True, "branch": ..., "conflict_files": [...], "rebase": True}`

## Branch Naming

`autoswe/issue-{N}` is the only authoritative format. Both GitHub and Azure providers use the same convention (see `providers/github/vcs.py:32` and `providers/azure/vcs.py:65`).

## Garbage Collection

Worktrees are **never automatically deleted**. Once `issue-{N}/` is created, it persists on disk even after the issue is closed, done, or skipped. Manual cleanup requires deleting the worktree directory and the remote branch.

## Token Rewriting

`ensure_clone()` updates the remote URL on every call — this keeps the embedded PAT current when `autoswe.env` is rotated. Both `_main/` clone and all worktrees inherit the updated URL through `git remote set-url`.
