"""Auto-generate CLAUDE.md when missing.

Before a plan/fix/review dispatch, this module checks whether the target
worktree has a project guide: ``CLAUDE.md`` **or** ``AGENTS.md``.  A
committed ``AGENTS.md`` is treated as a valid existing guide — for
``claude_code`` (which reads ``CLAUDE.md`` only) a one-line ``@AGENTS.md``
import stub is written instead of a from-scratch generation, and for all
other backends the init session is skipped entirely: pi reads AGENTS.md
natively (``AGENTS.override.md > AGENTS.md > CLAUDE.md``), and Codex gets
no project guide from autoSWE at all (its rules are disabled via
``--ignore-rules``, see ``docs/autoswe/harnesses.md`` — a generated
CLAUDE.md would be unreadable to that session anyway).  When neither file
exists, a short, backend-agnostic coding session analyzes the repo and
writes a CLAUDE.md, so the coding agent has a project guide for the
session.

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


def _agents_md_tracked(wt: Path) -> bool:
    """Return True if ``AGENTS.md`` is tracked in the worktree's git index.

    The init flow only treats a *committed* AGENTS.md as an existing project
    guide — an untracked one (e.g. written mid-run by an agent deviating from
    the init prompt's "write CLAUDE.md") must not suppress init or seed the
    ``@AGENTS.md`` stub. ``git ls-files --error-unmatch`` returns rc 0 when
    tracked and rc 1 when the path is not in the index; any other result
    (malformed worktree, missing git, ...) falls back to plain file existence
    so a git hiccup can never wedge the init flow (non-fatal by design).
    """
    from autoswe.vcs.worktree import _run

    try:
        res = _run(
            ["git", "-C", str(wt), "ls-files", "--error-unmatch", "AGENTS.md"],
            check=False,
        )
    except Exception:
        # git missing / unrunnable — fall back to plain file existence
        return True
    if res.returncode in (0, 1):
        return res.returncode == 0
    return True  # caller guarantees the file exists; git status unknown


def ensure_claude_md(
    task: dict,
    wt: Path,
    repo_cfg: dict,
    cfg: dict,
    *,
    phase: str,
    progress_callback: Callable[[str], None] | None = None,
) -> None:
    """Generate CLAUDE.md if missing (or write the ``@AGENTS.md`` import stub),
    then commit & push to the issue branch.

    The import-stub path writes a one-line CLAUDE.md that is deliberately
    NOT committed — it is kept out of the branch by the repo exclude.

    Only a *tracked* (committed) ``AGENTS.md`` counts as an existing project
    guide: for non-``claude_code`` backends the init session is skipped
    entirely, and for ``claude_code`` the one-line ``@AGENTS.md`` import stub
    is written instead of a from-scratch generation. An untracked AGENTS.md
    falls through to the normal init path.

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
    # the CLAUDE.md we're about to generate (or import-stub) off the per-issue
    # branch so the reviewer never flags them (finding C2). No-op if the main
    # clone is absent.
    from autoswe.vcs.worktree import _ensure_repo_exclude, main_clone_path

    main = main_clone_path(owner, repo, cfg, provider)
    if (main / ".git").exists():
        _ensure_repo_exclude(main)

    claude_md = wt / "CLAUDE.md"
    if claude_md.exists():
        return  # Already present — nothing to do

    stub_failed = False
    agents_md = wt / "AGENTS.md"
    # Only a committed (git-tracked) AGENTS.md counts as an existing project
    # guide — an untracked one must not suppress init or seed the stub.
    if agents_md.exists() and _agents_md_tracked(wt):
        # The repo already ships a project guide. pi reads AGENTS.md natively
        # (AGENTS.override.md > AGENTS.md > CLAUDE.md); Codex gets no project
        # guide from autoSWE either — its rules are intentionally disabled via
        # --ignore-rules (see docs/autoswe/harnesses.md) — so a generated
        # CLAUDE.md would be unreadable to that session anyway. Skipping the
        # init session avoids wasted work writing a file the backend will never
        # read. claude_code reads CLAUDE.md only, so give it a one-line import
        # of the committed guide instead of regenerating one from scratch.
        # The stub is kept out of the branch by the repo exclude written
        # above — no commit is attempted.
        try:
            harness = resolve_harness(phase, repo_cfg, cfg)
            backend = harness.get("backend", "claude_code")
            if backend == "claude_code":
                claude_md.write_text("@AGENTS.md\n")
                dbg.debug(
                    "AGENTS.md present, claude_code backend — wrote @AGENTS.md import stub to %s",
                    claude_md,
                )
            else:
                dbg.debug(
                    "AGENTS.md present, backend=%s needs no CLAUDE.md from autoSWE — skipping init session",
                    backend,
                )
        except Exception as e:
            # Non-fatal: fall through to the init session below so the
            # dispatch still gets a project guide.
            stub_failed = True
            dbg.warning("AGENTS.md import-stub path failed (non-fatal), running init session: %s", e)
        else:
            return

    try:
        if progress_callback:
            if stub_failed:
                progress_callback("No CLAUDE.md and the AGENTS.md import stub failed — generating project guide...")
            else:
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
                cfg=cfg,
            )
            dbg.debug("CLAUDE.md committed and pushed to %s/%s#%s", owner, repo, issue_num)
        else:
            dbg.debug("init session completed but CLAUDE.md was not written")

    except Exception as e:
        # Non-fatal: log and let the actual phase proceed
        dbg.error("ensure_claude_md failed (non-fatal): %s", e, exc_info=True)
