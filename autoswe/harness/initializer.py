"""Auto-generate CLAUDE.md when missing.

Before a plan/fix/review dispatch, this module checks whether the target
worktree has a CLAUDE.md.  If not, it runs a short, backend-agnostic
coding session to analyze the repo and write one, so the coding agent has
a project guide for the session.

The file is **git-excluded, not committed**: ``autoswe.vcs.worktree``
writes ``CLAUDE.md`` into the shared repo-local git exclude (finding C2),
so it stays in the worktree for the agent but is never added to the
per-issue branch.  The ``commit_and_push`` call below is therefore a
natural no-op in the normal case (no non-excluded changes to commit) and
is kept only as a fallback should the exclude ever be absent.

The entire flow is **non-fatal**: any failure logs a warning and returns,
letting the actual dispatch proceed normally.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from autoswe.core.config import resolve_harness
from autoswe.core.logging_utils import get_debug_logger
from autoswe.harness import runner
from autoswe.harness.prompts import load_init_prompt
from autoswe.vcs.worktree import commit_and_push

if TYPE_CHECKING:
    from collections.abc import Callable

dbg = get_debug_logger()


def ensure_claude_md(
    task: dict,
    wt: Path,
    repo_cfg: dict,
    cfg: dict,
    *,
    phase: str,
    progress_callback: Callable[[str], None] | None = None,
) -> None:
    """Generate CLAUDE.md if missing, then commit & push to the issue branch.

    Args:
        task: Handler task dict (queue entry shape).
        wt: Worktree root path.
        repo_cfg: Per-repo configuration dict.
        cfg: Global configuration dict.
        phase: Coding phase ("plan", "fix", or "review") used to resolve
            the harness profile for the init session.
        progress_callback: Optional callback for progress messages.
    """
    # Explicit opt-out for test harnesses that use scripted Claude fakes.
    if os.environ.get("AUTOSWE_SKIP_INIT_SESSION"):
        return

    owner = task["owner"]
    repo = task["repo"]
    issue_num = task["issue_number"]
    base_branch = task.get("base_branch", "main")
    provider = repo_cfg.get("provider", "github")

    # Ensure the shared repo-local git exclude is in place BEFORE any session
    # runs. This is the reliable hook (runs on every phase, including reused
    # worktrees that never re-invoke ensure_clone): it keeps build artifacts and
    # the CLAUDE.md we're about to generate off the per-issue branch so the
    # reviewer never flags them (finding C2). No-op if the main clone is absent.
    from autoswe.vcs.worktree import _ensure_repo_exclude, main_clone_path

    main = main_clone_path(owner, repo, cfg, provider)
    if (main / ".git").exists():
        _ensure_repo_exclude(main)

    claude_md = wt / "CLAUDE.md"
    if claude_md.exists():
        return  # Already present — nothing to do

    try:
        if progress_callback:
            progress_callback("No CLAUDE.md found — generating project guide...")

        prompt = load_init_prompt(repo_cfg)

        harness = resolve_harness(phase, repo_cfg, cfg)

        run_result = runner.run(
            prompt,
            cwd=str(wt),
            cfg=cfg,
            repo_cfg=repo_cfg,
            mode="read_write",
            model=harness.get("model"),
            harness_cfg=harness,
            progress_callback=progress_callback,
        )

        dbg.debug(
            "init session completed: subtype=%s session=%s duration=%.1fs",
            run_result.subtype,
            run_result.session_id,
            run_result.duration_seconds,
        )

        if claude_md.exists():
            commit_and_push(
                wt,
                owner,
                repo,
                issue_num,
                "Add CLAUDE.md (autoswe init)",
                base_branch,
                provider,
            )
            dbg.debug("CLAUDE.md committed and pushed to %s/%s#%s", owner, repo, issue_num)
        else:
            dbg.debug("init session completed but CLAUDE.md was not written")

    except Exception as e:
        # Non-fatal: log and let the actual phase proceed
        dbg.error("ensure_claude_md failed (non-fatal): %s", e, exc_info=True)
