"""Redact local worktree paths before posting content to external services.

Prevents host filesystem paths from leaking into GitHub/Azure comments,
PR titles, and PR bodies.
"""
from __future__ import annotations

import os
import re


def _worktree_leaf() -> str:
    """Return the leaf directory name used for worktree storage."""
    worktree_dir = os.environ.get("WORKTREE_DIR", "worktrees")
    if worktree_dir.startswith("/") or (len(worktree_dir) > 1 and worktree_dir[1] == ":"):
        return worktree_dir.rstrip("/\\").rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    return worktree_dir


def redact_worktree_paths(text: str) -> str:
    """Mask local worktree root paths in *text* so they don't leak host info.

    Replaces any path token containing the worktree leaf directory so that
    everything up to (and including) the parent of the leaf becomes ``"..."``,
    preserving the relative tail after the leaf for readability.

    The ``leaf`` is derived from the ``WORKTREE_DIR`` environment variable
    (basename if absolute, else the value itself).

    Idempotent: text already carrying a ``".../`` prefix will not re-match.
    No-op when the text contains no worktree paths.
    """
    leaf = _worktree_leaf()

    # Build pattern: optional drive + one or more path segments + leaf + tail
    # Path segments are separator + non-whitespace/non-quote chars.
    _seg = r"[\\/][^\s'\"]*"
    _sep = r"[\\/]"

    pat = (
        r"(?:[A-Za-z]:)?"
        r"(?:" + _seg + r")+"
        + _sep + r"(?:" + re.escape(leaf) + r")"
        r"(" + _seg + r"(" + _seg + r")*)"
    )
    return re.sub(pat, lambda m: f".../{leaf}{m.group(1)}", text)
