import subprocess
from pathlib import Path

from autoswe.core.config import AUTOSWE_DIR, LOGS_DIR
from autoswe.core.logging_utils import init_debug_logger, log
from autoswe.providers.factory import get_vcs

dbg = init_debug_logger(LOGS_DIR)


def get_remote_branch_sha(
    owner: str,
    repo: str,
    branch: str,
    token: str,
    provider: str = "github",
) -> str | None:
    """Get the SHA at the tip of a remote branch without cloning.

    Uses the VCS provider's ``clone_url()`` to get the correct HTTPS URL
    for the given provider (GitHub, Azure DevOps, etc.).
    """
    repo_cfg = {"owner": owner, "repo": repo, "token": token, "provider": provider}
    try:
        clone_url = get_vcs(repo_cfg).clone_url(repo_cfg)
    except Exception as e:
        dbg.debug("get_remote_branch_sha: clone_url failed: %s", e)
        return None
    try:
        result = subprocess.run(
            ["git", "ls-remote", clone_url, branch],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.split()[0]
    except Exception as e:
        dbg.debug("get_remote_branch_sha: ls-remote failed: %s", e)
    return None


def _worktrees_root(cfg: dict) -> Path:
    """Absolute path to the worktrees directory."""
    worktree_dir = cfg.get("WORKTREE_DIR", "worktrees")
    p = Path(worktree_dir)
    return p if p.is_absolute() else AUTOSWE_DIR / worktree_dir


def _repo_dir(owner: str, repo: str, cfg: dict, provider: str = "github") -> Path:
    """Return the per-repo worktree directory.

    Paths are provider-prefixed: ``gh-owner_repo`` for GitHub,
    ``ado-org_proj_repo`` for Azure DevOps.
    """
    parts = _provider_parts(provider, owner, repo)
    joined = "_".join(parts)
    return _worktrees_root(cfg) / joined


def _provider_parts(provider: str, owner: str, repo: str) -> tuple[str, ...]:
    """Return slug parts for the given provider.

    GitHub: (owner, repo)
    Azure:  (org, proj, repo) — owner is "org/proj"
    """
    if provider == "azure":
        if "/" in owner:
            org, _, proj = owner.partition("/")
            return (org, proj, repo)
        return (owner, repo)
    return (owner, repo)


def main_clone_path(owner: str, repo: str, cfg: dict, provider: str = "github") -> Path:
    return _repo_dir(owner, repo, cfg, provider) / "_main"


def worktree_path(owner: str, repo: str, issue_num: int, cfg: dict, provider: str = "github") -> Path:
    return _repo_dir(owner, repo, cfg, provider) / f"issue-{issue_num}"


def _run(args: list, cwd: Path = None, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=check)


def _get_default_branch(main: Path, base_branch: str) -> str:
    """Determine the repo's actual default branch for _main checkout.

    Fallback chain:
    1. origin/HEAD symbolic ref (e.g. "refs/heads/main")
    2. base_branch (from repos.json config — authoritative default)
    3. Check which of main/master exists via git ls-remote
    """
    # 1. Try origin/HEAD symbolic ref
    head = _run(
        ["git", "-C", str(main), "symbolic-ref", "--short", "origin/HEAD"],
        check=False,
    )
    if head.returncode == 0:
        ref = head.stdout.strip()
        branch = ref.replace("refs/heads/", "") if ref.startswith("refs/heads/") else ref
        if branch:
            return branch

    # 2. Fall back to configured base_branch
    if base_branch:
        return base_branch

    # 3. Last resort: check main then master via ls-remote
    for candidate in ("main", "master"):
        result = _run(
            ["git", "-C", str(main), "ls-remote", "--heads", "origin", candidate],
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return candidate

    return "main"  # ultimate fallback


def ensure_clone(
    owner: str, repo: str, token: str, cfg: dict,
    base_branch: str = "main", provider: str = "github",
    default_branch: str = None,
) -> None:
    """Ensure _main/ clone exists and is up to date."""
    main = main_clone_path(owner, repo, cfg, provider)
    repo_cfg = {"owner": owner, "repo": repo, "token": token, "provider": provider}
    clone_url = get_vcs(repo_cfg).clone_url(repo_cfg)
    if not main.exists():
        main.parent.mkdir(parents=True, exist_ok=True)
        log(f"[WORKTREE] Cloning {owner}/{repo} -> {main}")
        _run(["git", "clone", clone_url, str(main)])
        # Verify the repo has commits (empty repos have no branches to checkout)
        verify = _run(
            ["git", "-C", str(main), "rev-parse", "--verify", f"origin/{base_branch}"],
            check=False,
        )
        if verify.returncode != 0:
            raise RuntimeError(
                f"Repository {owner}/{repo} has no commits on '{base_branch}'; "
                "autoSWE requires an initialized repository."
            )
    else:
        # Update the remote URL so token stays current
        _run(["git", "-C", str(main), "remote", "set-url", "origin", clone_url])
        # Hard pull so _main is always current for new worktrees.
        # Use default_branch for _main checkout; fall back to auto-detection.
        # base_branch may be a custom --branch value that doesn't exist on _main.
        _run(["git", "-C", str(main), "fetch", "origin"])
        branch_for_main = default_branch or _get_default_branch(main, base_branch)

        # Verify the repo has commits on the target branch (empty repos have no refs)
        verify = _run(
            ["git", "-C", str(main), "rev-parse", "--verify", f"origin/{branch_for_main}"],
            check=False,
        )
        if verify.returncode != 0:
            raise RuntimeError(
                f"Repository {owner}/{repo} has no commits on '{branch_for_main}'; "
                "autoSWE requires an initialized repository."
            )

        _run(["git", "-C", str(main), "checkout", branch_for_main])
        _run(["git", "-C", str(main), "reset", "--hard", f"origin/{branch_for_main}"])


def get_merge_conflict_files(wt: Path) -> list[str]:
    """Return paths with conflict markers when a merge is in progress, else []."""
    result = _run(["git", "-C", str(wt), "diff", "--name-only", "--diff-filter=U"], check=False)
    output = result.stdout.strip()
    if not output:
        return []
    return [p.strip() for p in output.split("\n") if p.strip()]


def _git_operation_in_progress(wt: Path) -> str | None:
    """Return 'merge', 'rebase', or None.

    Detect via MERGE_HEAD (merge) and rebase-merge/rebase-apply dirs (rebase).
    Uses ``git rev-parse --git-path`` so it works for worktrees whose .git is a file.
    """
    # Check merge
    merge_head = _run(
        ["git", "-C", str(wt), "rev-parse", "-q", "--verify", "MERGE_HEAD"],
        check=False,
    )
    if merge_head.returncode == 0 and merge_head.stdout.strip():
        return "merge"

    # Check rebase — resolve rebase-merge and rebase-apply via git-path
    for subdir in ("rebase-merge", "rebase-apply"):
        git_path = _run(
            ["git", "-C", str(wt), "rev-parse", "--git-path", subdir],
            check=False,
        )
        if git_path.returncode == 0:
            path_str = git_path.stdout.strip()
            if path_str and Path(path_str).exists():
                return "rebase"

    return None


def _apply_pull_strategy(wt: Path, branch: str, strategy: str) -> list[str]:
    """Pull origin/<branch> into the worktree according to *strategy*.

    Returns list of conflicted files (only when strategy="merge" and conflicts exist).
    """
    if strategy == "none":
        return []

    _run(["git", "-C", str(wt), "fetch", "origin", branch])

    if strategy == "reset":
        _run(["git", "-C", str(wt), "reset", "--hard", f"origin/{branch}"])
        log(f"[WORKTREE] Reset {branch} to origin/{branch}")
        return []

    # strategy == "merge"
    merge_result = _run(
        ["git", "-C", str(wt), "merge", "--no-edit", f"origin/{branch}"],
        check=False,
    )
    if merge_result.returncode != 0:
        conflict_files = get_merge_conflict_files(wt)
        err = (merge_result.stdout + " " + merge_result.stderr).strip()
        log(f"[WORKTREE] Merge conflict pulling origin/{branch}: {err}")
        return conflict_files

    # Clean merge — push so origin and local stay in sync
    _run(["git", "-C", str(wt), "push", "origin", branch])
    log(f"[WORKTREE] Merged origin/{branch} into {branch} and pushed")
    return []


def create_worktree(
    owner: str, repo: str, issue_num: int, base_branch: str,
    token: str, cfg: dict, provider: str = "github",
    default_branch: str = None,
    pull_strategy: str = "reset",
    push_new: bool = False,
) -> Path:
    """Ensure worktree for the issue exists on branch autoswe/issue-{N}. Returns path.

    *pull_strategy* controls how ``origin/<branch>`` is brought in:
    - ``"reset"`` (default): ``git reset --hard origin/<branch>`` — clean start.
      Used by planner and ``/sync``.
    - ``"merge"``: ``git merge origin/<branch>`` — preserves local commits, pushes
      clean merges, leaves conflicts for the caller to resolve. Used by ``/fix``.
    - ``"none"``: no pull. Reserved for tests.
    *push_new* if True and the branch is newly created (not previously on remote),
    push it immediately so subsequent retries can fetch it. Used by the coder
    handler (`/fix`) to support the AskUserQuestion → WAITING → retry cycle.
    The planner (`/plan`) passes ``push_new=False`` since it makes no commits.
    """
    ensure_clone(owner, repo, token, cfg, base_branch, provider, default_branch=default_branch)
    main = main_clone_path(owner, repo, cfg, provider)
    repo_cfg = {"owner": owner, "repo": repo, "token": token, "provider": provider}
    branch = get_vcs(repo_cfg).branch_name(issue_num)
    wt = worktree_path(owner, repo, issue_num, cfg, provider)

    if wt.exists():
        log(f"[WORKTREE] Reusing {wt}")
        _apply_pull_strategy(wt, branch, pull_strategy)
        return wt

    # Check if branch already exists remotely
    result = _run(["git", "-C", str(main), "branch", "-r", "--list", f"origin/{branch}"], check=False)
    branch_exists = bool(result.stdout.strip())

    dbg.debug("WORKTREE: branch=%s exists=%s", branch, branch_exists)

    new_branch = False
    if branch_exists:
        _run(["git", "-C", str(main), "worktree", "add", str(wt), branch])
        _apply_pull_strategy(wt, branch, pull_strategy)
    else:
        new_branch = True
        # Verify base_branch exists on origin before creating worktree
        verify = _run(
            ["git", "-C", str(main), "rev-parse", "--verify", f"origin/{base_branch}"],
            check=False,
        )
        if verify.returncode != 0:
            raise RuntimeError(
                f"base branch '{base_branch}' does not exist on origin"
            )
        base_sha_result = _run(["git", "-C", str(main), "rev-parse", "--short", f"origin/{base_branch}"], check=False)
        base_sha = base_sha_result.stdout.strip() if base_sha_result.returncode == 0 else "unknown"
        log(f"[WORKTREE] {owner}/{repo}#{issue_num} branch={branch} forked_from={base_branch}@{base_sha}")
        _run(["git", "-C", str(main), "worktree", "add", str(wt), "-b", branch, f"origin/{base_branch}"])

    if new_branch and push_new:
        _run(["git", "-C", str(main), "push", "-u", "origin", branch])
        log(f"[WORKTREE] Pushed new branch {branch} -> origin (track=true)")

    log(f"[WORKTREE] Created {wt} on branch {branch}")
    return wt


def commit_and_push(wt: Path, owner: str, repo: str, issue_num: int, msg: str, base_branch: str = "main", provider: str = "github") -> dict:
    """Stage, commit (if changes), and push.

    Preserves Claude auto-commits as a commit trail rather than squashing:
    - If Claude auto-committed during the session, the last commit is amended
      with the proper message and all other auto-commits are kept intact.
    - If Claude did not auto-commit, working-tree changes are staged into a
      single new commit.

    Returns dict with:
      - committed: bool
      - commit_sha: str  (full SHA, present when committed)
      - branch: str      (branch name, e.g. "autoswe/issue-42")
    """
    repo_cfg = {"owner": owner, "repo": repo, "token": "", "provider": provider}
    branch = get_vcs(repo_cfg).branch_name(issue_num)
    dbg.debug("WORKTREE: commit_and_push msg=%s", msg)

    # Check for in-progress merge/rebase operations
    op = _git_operation_in_progress(wt)
    if op is not None:
        conflict_files = get_merge_conflict_files(wt)
        if conflict_files:
            raise RuntimeError(
                f"cannot commit: unresolved {op} conflicts in "
                f"{', '.join(conflict_files)}"
            )
        # Operation in progress but conflicts resolved — complete it
        # instead of amending across the in-progress state
        if op == "merge":
            _run(["git", "-C", str(wt), "commit", "--no-edit"])
            log("[WORKTREE] Completed in-progress merge")
        else:
            _run(["git", "-C", str(wt), "rebase", "--continue"], check=False)
            log("[WORKTREE] Completed in-progress rebase")

    # Fetch latest remote state (keeps token current, picks up prior pushes)
    _run(["git", "-C", str(wt), "fetch", "origin"], check=False)

    # If local branch is behind remote (prior push), rebase so worktree is current.
    # Without this, reused worktrees accumulate stale state between dispatch cycles.
    behind = _run(["git", "-C", str(wt), "log", f"HEAD..origin/{branch}", "--oneline"], check=False)
    if behind.stdout.strip():
        _run(["git", "-C", str(wt), "reset", "--hard", f"origin/{branch}"])
        log(f"[WORKTREE] Reset {branch} to match origin (was behind)")

    log(f"[WORKTREE] Starting commit_and_push on {branch}: msg={msg[:80]!r}")

    # Check if Claude Code already committed during this session.
    # Compare against origin/{branch} (not base_branch) so we only see commits
    # from the current dispatch cycle — after the reset-to-origin above,
    # anything ahead of origin/{branch} is new work from this session.
    # This preserves the commit trail: each /fix run adds its own commit(s)
    # rather than squashing everything into one.
    ahead = _run(["git", "-C", str(wt), "log", f"origin/{branch}..HEAD", "--oneline"], check=False)
    if ahead.stdout.strip():
        ahead_lines = ahead.stdout.strip().split("\n")
        count = len(ahead_lines)
        shas = [s.split()[0] for s in ahead_lines if s.strip()]
        log(f"[WORKTREE] Detected {count} agent commit(s) on {branch}: {shas}")
        dbg.debug("WORKTREE: %d auto-commits from session — preserving trail", count)
        # If HEAD is a merge commit (e.g., from resolving pull-conflicts),
        # skip the amend — push the merge commit as-is.
        parents_output = _run(["git", "-C", str(wt), "rev-list", "--parents", "-n", "1", "HEAD"]).stdout.strip().split()
        is_merge = len(parents_output) > 2  # commit hash + 2 or more parents
        if is_merge:
            log("[WORKTREE] HEAD is a merge commit — pushing without amend")
            _run(["git", "-C", str(wt), "push", "-f", "origin", branch])
        else:
            # Reword the last commit to use the proper "Fixes #N" message,
            # preserving all other auto-commits as individual commits.
            _run(["git", "-C", str(wt), "commit", "--amend", "-m", msg, "--no-edit"])
            log(f"[WORKTREE] Reworded last commit on {branch} ({count} commit(s) preserved)")
            _run(["git", "-C", str(wt), "push", "-f", "origin", branch])
            log(f"[WORKTREE] git push -f origin {branch}")
        commit_sha = _run(["git", "-C", str(wt), "rev-parse", "HEAD"]).stdout.strip()
        log(f"[WORKTREE] git commit ({commit_sha[:8]}) on {branch}: {msg[:60]!r}")
        return {"committed": True, "commit_sha": commit_sha, "branch": branch}

    _run(["git", "-C", str(wt), "add", "-A"])
    diff = _run(["git", "-C", str(wt), "diff", "--cached", "--quiet"], check=False)
    if diff.returncode == 0:
        log(f"[WORKTREE] No changes to commit in {wt}")
        return {"committed": False}
    _run(["git", "-C", str(wt), "commit", "-m", msg])
    _run(["git", "-C", str(wt), "push", "-u", "origin", branch])
    commit_sha = _run(["git", "-C", str(wt), "rev-parse", "HEAD"]).stdout.strip()
    dbg.debug("WORKTREE: committed and pushed %s sha=%s", branch, commit_sha)
    log(f"[WORKTREE] Committed and pushed {branch} ({commit_sha[:8]})")
    return {"committed": True, "commit_sha": commit_sha, "branch": branch}


def sync_branch(wt: Path, owner: str, repo: str, issue_num: int, base_branch: str = "main", provider: str = "github", cfg: dict = None) -> dict:
    """Merge or rebase the latest base branch into the worktree branch.

    Strategy is controlled by ``cfg["SYNC_STRATEGY"]``:
    - ``"merge"`` (default): ``git merge origin/{base}`` — append-only, no history rewrite.
    - ``"rebase"``: ``git rebase origin/{base}`` — linear history, force-pushes on success.

    On conflict, the worktree is LEFT in the conflicted state (no abort)
    so the caller can resolve conflicts and complete the merge/rebase commit.

    Returns dict with:
      - synced: bool     (True if merge/rebase succeeded, False on conflict)
      - conflict: bool   (True if conflicts exist in working tree)
      - branch: str      (branch name, e.g. "autoswe/issue-42")
      - ahead: int       (commits ahead of base branch after sync)
      - conflict_files: list[str]  (present only when conflict=True)
      - rebase: bool     (present only when strategy="rebase" and conflict=True)
    """
    repo_cfg = {"owner": owner, "repo": repo, "token": "", "provider": provider}
    branch = get_vcs(repo_cfg).branch_name(issue_num)
    strategy = (cfg or {}).get("SYNC_STRATEGY", "merge")
    dbg.debug("WORKTREE: sync_branch %s onto origin/%s (strategy=%s)", branch, base_branch, strategy)

    log(f"[WORKTREE] sync_branch {branch} onto origin/{base_branch}")

    # Check for in-progress merge/rebase operations
    op = _git_operation_in_progress(wt)
    if op is not None:
        conflict_files = get_merge_conflict_files(wt)
        if conflict_files:
            raise RuntimeError(
                f"cannot sync: unresolved {op} conflicts in "
                f"{', '.join(conflict_files)}"
            )
        # Operation in progress but conflicts resolved — complete it
        # before starting the sync
        if op == "merge":
            _run(["git", "-C", str(wt), "commit", "--no-edit"])
            log("[WORKTREE] Completed in-progress merge before sync")
        else:
            _run(["git", "-C", str(wt), "rebase", "--continue"], check=False)
            log("[WORKTREE] Completed in-progress rebase before sync")

    # Fetch latest remote state
    _run(["git", "-C", str(wt), "fetch", "origin"])

    # Capture HEAD before merge to detect if sync moved it
    head_before = _run(["git", "-C", str(wt), "rev-parse", "HEAD"]).stdout.strip()

    # Reset to origin/branch so local state matches remote before merging
    # Only reset if the remote ref exists — fresh branches haven't been pushed yet
    remote_exists = _run(
        ["git", "-C", str(wt), "show-ref", "--verify", f"refs/remotes/origin/{branch}"],
        check=False,
    )
    if remote_exists.returncode == 0:
        _run(["git", "-C", str(wt), "reset", "--hard", f"origin/{branch}"])
        log(f"[WORKTREE] Reset {branch} to origin/{branch}")
    else:
        log(f"[WORKTREE] origin/{branch} not found — skipping reset (new branch)")

    if strategy == "rebase":
        rebase_result = _run(
            ["git", "-C", str(wt), "rebase", f"origin/{base_branch}"],
            check=False,
        )
        if rebase_result.returncode != 0:
            # Conflict — leave worktree in rebase-in-progress state.
            conflict_files = get_merge_conflict_files(wt)
            err = (rebase_result.stdout + " " + rebase_result.stderr).strip()
            log(f"[WORKTREE] Rebase conflict on {branch}: {err}")
            return {
                "synced": False,
                "conflict": True,
                "branch": branch,
                "ahead": 0,
                "conflict_files": conflict_files,
                "rebase": True,
                "error": f"rebase conflict: {err}",
            }
        log(f"[WORKTREE] Rebased {branch} onto origin/{base_branch}")

        # Rebase rewrites history — push with --force-with-lease
        _run(["git", "-C", str(wt), "push", "--force-with-lease", "origin", branch])
        log(f"[WORKTREE] git push --force-with-lease origin {branch}")
    else:
        # Merge the latest base branch (append-only, no history rewrite)
        merge_result = _run(
            ["git", "-C", str(wt), "merge", "--no-edit", f"origin/{base_branch}"],
            check=False,
        )
        if merge_result.returncode != 0:
            # Conflict — leave worktree in conflicted merge state for caller to resolve.
            conflict_output = _run(
                ["git", "-C", str(wt), "diff", "--name-only", "--diff-filter=U"],
                check=False,
            )
            conflict_files = [
                f.strip() for f in conflict_output.stdout.strip().split("\n")
                if f.strip()
            ]
            err = (merge_result.stdout + " " + merge_result.stderr).strip()
            log(f"[WORKTREE] Merge conflict on {branch}: {err}")
            return {
                "synced": False,
                "conflict": True,
                "branch": branch,
                "ahead": 0,
                "conflict_files": conflict_files,
                "error": f"merge conflict: {err}",
            }

        log(f"[WORKTREE] Merged origin/{base_branch} into {branch}")

        # Plain push — merge is append-only so no force needed
        _run(["git", "-C", str(wt), "push", "origin", branch])
        log(f"[WORKTREE] git push origin {branch}")

    # Count commits ahead of base branch
    ahead = _run(["git", "-C", str(wt), "log", f"origin/{base_branch}..HEAD", "--oneline"], check=False)
    ahead_count = len(ahead.stdout.strip().split("\n")) if ahead.stdout.strip() else 0

    commit_sha = _run(["git", "-C", str(wt), "rev-parse", "HEAD"]).stdout.strip()
    head_after = _run(["git", "-C", str(wt), "rev-parse", "HEAD"]).stdout.strip()

    return {
        "synced": True, "conflict": False, "branch": branch,
        "ahead": ahead_count,
        "commit_sha": commit_sha,
        "changed": head_before != head_after,
    }


def fast_forward_worktree(wt: Path, branch: str) -> bool:
    """Fast-forward the worktree to origin/branch if it's behind.

    Fetches the branch, checks if local HEAD is behind origin, and if so,
    merges with --ff-only. Returns True on success (or if already current).

    Used by fix handlers to ensure the worktree is up-to-date before
    continuing a Claude session, so the agent doesn't operate on stale state.
    """
    old_sha_result = _run(["git", "-C", str(wt), "rev-parse", "--short", "HEAD"], check=False)
    old_sha = old_sha_result.stdout.strip() if old_sha_result.returncode == 0 else None

    _run(["git", "-C", str(wt), "fetch", "origin", branch], check=False)

    behind = _run(
        ["git", "-C", str(wt), "rev-list", "HEAD..origin/" + branch],
        check=False,
    )
    behind_shas = [s.strip() for s in behind.stdout.strip().split("\n") if s.strip()]

    if not behind_shas:
        log(f"[WORKTREE] {wt.name} already up-to-date with origin/{branch}")
        return True

    merge = _run(
        ["git", "-C", str(wt), "merge", "--ff-only", "origin/" + branch],
        check=False,
    )
    if merge.returncode != 0:
        err = (merge.stdout + merge.stderr).strip()
        log(f"[WORKTREE] Could not fast-forward {wt.name} to origin/{branch}: {err}")
        return False

    new_sha_result = _run(["git", "-C", str(wt), "rev-parse", "--short", "HEAD"], check=False)
    new_sha = new_sha_result.stdout.strip() if new_sha_result.returncode == 0 else None
    log(f"[WORKTREE] Fast-forwarded {wt.name} from {old_sha} to {new_sha} ({len(behind_shas)} commit(s))")
    return True
