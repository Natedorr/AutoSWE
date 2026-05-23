"""Structured recipe specs for ClaudeFake scripted responses.

A Recipe describes things Claude would do during a session — file writes,
deletes, shell commands, conflict resolution, auto-commits — so tests can
simulate Claude's Bash tool without invoking a real model.
"""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Recipe:
    """Structured spec for simulated Claude actions in a worktree.

    Attributes:
        writes: path → content dict; files written before any other action.
        deletes: list of relative paths to remove.
        shell: list of argv lists; each subprocess run sequentially.
        resolve_conflicts: path → resolved content; writes the content then
            ``git add``s each file (caller must still commit / continue).
        auto_commit: if set, runs ``git add -A`` then ``git commit -m <msg>``
            after all other actions.
        merge_continue: if True, runs ``git commit --no-edit`` after resolution
            (finalises an in-progress merge).
        rebase_continue: if True, runs ``git rebase --continue`` after resolution.
    """
    writes: dict[str, str] = field(default_factory=dict)
    deletes: list[str] = field(default_factory=list)
    shell: list[list[str]] = field(default_factory=list)
    resolve_conflicts: dict[str, str] | None = None
    auto_commit: str | None = None
    merge_continue: bool = False
    rebase_continue: bool = False


def _git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a git command in the given working directory."""
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        check=check,
        env={**os.environ, "GIT_EDITOR": ":"},
    )


def apply_recipe(cwd: Path, recipe: Recipe) -> None:
    """Apply every step in *recipe* inside the worktree at *cwd*."""
    # 1. File writes
    for rel, content in recipe.writes.items():
        p = cwd / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)

    # 2. Deletions
    for rel in recipe.deletes:
        p = cwd / rel
        if p.exists():
            p.unlink()

    # 3. Resolve conflicts (write content, then git add)
    if recipe.resolve_conflicts:
        for rel, content in recipe.resolve_conflicts.items():
            p = cwd / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
        # Stage all resolved files
        _git(cwd, "add", "-A")

    # 4. Shell commands
    for argv in recipe.shell:
        subprocess.run(
            argv,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
            env={**os.environ, "GIT_EDITOR": ":"},
        )

    # 5. Merge / rebase continue (before auto commit, which is independent)
    if recipe.merge_continue:
        _git(cwd, "commit", "--no-edit", "--no-verify")
    if recipe.rebase_continue:
        _git(cwd, "rebase", "--continue")

    # 6. Auto-commit (stages everything, commits with message)
    if recipe.auto_commit:
        _git(cwd, "add", "-A")
        _git(cwd, "commit", "-m", recipe.auto_commit, "--no-verify")
