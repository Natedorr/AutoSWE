"""Preflight gate for PR creation: branch-sync + CI-status checks.

Shared by explicit ``/pr`` (``ship.open_pr``) and auto-PR-after-``/fix``
(the ``create_pr`` effect applied in the provider adapters). Both gates
default to on and are controlled by ``PR_REQUIRE_SYNC`` / ``PR_REQUIRE_CI``
in ``cfg``, with optional per-repo overrides (same keys, lowercased) in
``repo_cfg``.

The CI gate treats ``CIStatus.state="error"`` (the CI API could not be
consulted — network failure, bad PAT, unresolvable head) as blocking by
default; the ``PR_CI_ERROR_POLICY`` key (``block`` | ``open``, default
``block``) is the explicit opt-out to let a PR through when CI cannot be
verified. A *stale* ``pending`` verdict (build predates the branch head)
blocks like an in-flight build.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from autoswe.core.logging_utils import get_debug_logger, log
from autoswe.providers.factory import get_vcs
from autoswe.vcs import worktree as worktree_mod

if TYPE_CHECKING:
    from collections.abc import Callable

dbg = get_debug_logger()


def _flag(name: str, cfg: dict, repo_cfg: dict, default: bool = True) -> bool:
    """Resolve a boolean flag: a per-repo override (lowercase key) beats cfg."""
    override = repo_cfg.get(name.lower())
    if override is not None:
        return bool(override)
    return bool(cfg.get(name, default))


def _policy(name: str, cfg: dict, repo_cfg: dict, default: str) -> str:
    """Resolve a string policy: a per-repo override (lowercase key) beats cfg.

    Mirrors ``_flag`` for non-boolean values (e.g. ``PR_CI_ERROR_POLICY``).
    The value is normalised (stripped, lowercased); an empty value falls back
    to *default* so a stray ``""`` override can't disable the policy.
    """
    value = repo_cfg.get(name.lower())
    if value is None:
        value = cfg.get(name)
    if value is None:
        return default
    normalized = str(value).strip().lower()
    return normalized or default


def preflight_pr(
    task: dict,
    cfg: dict,
    repo_cfg: dict,
    *,
    progress_callback: Callable[[str], None] | None = None,
    do_sync: bool = True,
    vcs=None,
) -> tuple[bool, str]:
    """Gate PR creation on branch sync and CI status.

    Returns ``(True, "")`` once every enabled gate passes, else
    ``(False, reason)`` describing which gate blocked the PR.

    *vcs*, when given, is used for the CI check instead of resolving a new
    provider instance — callers that already hold a VCSProvider (e.g. the
    adapters, which resolve one for ``find_existing_pr``) should pass it in
    so tests patching that instance take effect and no extra client is built.
    """
    issue_num = task["issue_number"]
    base_branch = task.get("plan_branch") or task.get("base_branch", "main")
    resolved_vcs = vcs or get_vcs(repo_cfg)
    branch = resolved_vcs.branch_name(issue_num)

    if do_sync and _flag("PR_REQUIRE_SYNC", cfg, repo_cfg):
        ok, reason = _sync_gate(task, repo_cfg, cfg, base_branch, progress_callback)
        if not ok:
            return False, reason

    if _flag("PR_REQUIRE_CI", cfg, repo_cfg):
        ci = resolved_vcs.get_ci_status(branch)
        if ci.state == "failure":
            return False, f"CI failing: {ci.summary}"
        if ci.state == "pending":
            stale_note = " (stale — build predates branch head)" if ci.stale else ""
            return False, f"CI still running ({ci.pending_count} pending) — retry /pr when green{stale_note}"
        if ci.state == "error" and _policy("PR_CI_ERROR_POLICY", cfg, repo_cfg, "block") == "block":
            # Fail-safe: an unconsultable CI API is not a pass.
            return False, f"CI status unavailable ({ci.summary}) — PR_CI_ERROR_POLICY=block"
        # "success", "none" (no CI configured), and (policy "open") "error" pass

    return True, ""


def _sync_gate(
    task: dict,
    repo_cfg: dict,
    cfg: dict,
    base_branch: str,
    progress_callback: Callable[[str], None] | None,
) -> tuple[bool, str]:
    """Ensure the worktree is synced with base; resolve merge conflicts via Claude."""
    from autoswe.harness import coder  # deferred: only needed when a conflict resolution runs

    owner, repo, issue_num = task["owner"], task["repo"], task["issue_number"]
    provider = repo_cfg.get("provider", "github")
    token = task.get("_token", "")

    wt = worktree_mod.worktree_path(owner, repo, issue_num, cfg, provider)
    if not wt.exists():
        wt = worktree_mod.create_worktree(
            owner, repo, issue_num, base_branch, token, cfg, provider,
            default_branch=base_branch, pull_strategy="reset", push_new=True,
        )

    result = worktree_mod.sync_branch(wt, owner, repo, issue_num, base_branch, provider, cfg)
    log(f"[PR_GATE] {task.get('id')} sync synced={result.get('synced')} conflict={result.get('conflict')}")

    if result.get("synced"):
        return True, ""

    if result.get("conflict"):
        if result.get("rebase"):
            files = result.get("conflict_files", [])
            file_list = ", ".join(files) if files else "unknown files"
            return False, f"branch behind base and rebase conflict in {file_list}"
        files = result.get("conflict_files", [])
        if progress_callback:
            progress_callback(f"Pre-PR sync conflict in {len(files)} file(s) — invoking Claude to resolve...")
        hr = coder.resolve_sync_conflicts(
            task, files, repo_cfg=repo_cfg, cfg=cfg, progress_callback=progress_callback,
        )
        if (hr.done_content or "").startswith("DONE_SUMMARY"):
            return True, ""
        return False, "branch behind base and sync conflict could not be resolved"

    return False, f"branch behind base and sync failed: {result.get('error', 'unknown error')}"
