"""Bot comment detection and comment-utility helpers.

These functions operate on comment-like objects that can be either
`NormalizedComment` dataclasses or raw dict-shaped data from the
GitHub API (test fixtures). They use attribute access with dict fallback
so both shapes work.
"""
from __future__ import annotations

import re
from typing import Any

from autoswe.providers.base import NormalizedComment

BOT_MARKER = "<!-- autoswe-bot -->"

# T8: Type alias so the duck-typed accessors are properly annotated.
# NormalizedComment carries the canonical shape; dict[str, Any] covers
# raw API responses and test fixtures that don't go through the adapter.
CommentLike = NormalizedComment | dict[str, Any]


# ---------------------------------------------------------------------------
# Body normalization — shared by completion-detection functions (T7)
# ---------------------------------------------------------------------------


def _normalize_body(body: str) -> str:
    """Strip formatting chars and collapse whitespace for fuzzy matching.

    Used by ``_find_last_completion_id`` and ``_find_last_completion`` so the
    normalize-then-match logic lives in one place (T7 DRY refactor).
    """
    stripped = re.sub(r'[\`\*\_~]', '', body.lower())
    return re.sub(r'\s+', ' ', stripped)


# ---------------------------------------------------------------------------
# Accessors — work with NormalizedComment or raw dicts (fixtures)
# ---------------------------------------------------------------------------


def _get_body(comment: CommentLike) -> str:
    """Return the body string of a comment."""
    if hasattr(comment, "body"):
        return comment.body or ""
    return comment.get("body", "") or ""


def _get_created_at(comment: CommentLike) -> str:
    """Return the created_at ISO timestamp of a comment."""
    if hasattr(comment, "created_at"):
        return comment.created_at or ""
    return comment.get("created_at", "") or ""


def _get_id(comment: CommentLike) -> int | None:
    """Return the id of a comment."""
    if hasattr(comment, "id"):
        return comment.id
    return comment.get("id")


def _get_is_bot(comment: CommentLike) -> bool:
    """Return the is_bot flag of a comment."""
    if hasattr(comment, "is_bot"):
        return comment.is_bot
    return comment.get("is_bot", False)


# ---------------------------------------------------------------------------
# Bot comment detection
# ---------------------------------------------------------------------------

def _is_autoswe_bot_comment(comment: CommentLike) -> bool:
    """Check if a comment was posted by autoSWE.

    Primary check: is_bot flag (set by adapter from bot_comment_ids membership).
    Fallback: BOT_MARKER in the body (HTML comment footer).
    Secondary fallback: content-based pattern matching for environments that
    strip HTML comments (e.g. Azure DevOps). This fallback prevents the
    infinite-loop bug where bot comments are misidentified as user comments
    when the marker is stripped.
    """
    # First-class bot detection from adapter
    if _get_is_bot(comment):
        return True

    body = _get_body(comment)
    if BOT_MARKER in body:
        return True

    # Fallback: detect bot comments by content patterns.
    # These patterns are unique to autoSWE-posted comments and are unlikely
    # to appear in genuine user replies.
    return any(pattern in body for pattern in _BOT_CONTENT_PATTERNS)


# Content patterns that uniquely identify autoSWE bot comments.
# Used as a fallback when BOT_MARKER is stripped (e.g. Azure DevOps).
_BOT_CONTENT_PATTERNS = (
    "## Questions",             # planner WAITING output
    "## Plan\n",                # planner PLAN_READY output (## Plan followed by newline)
    "## Claude's response",     # planner WAITING:see comment fallback
    "Completed with command",   # dispatch completion comment
    "Post `/retry`",            # dispatch failure comment (partial — enough to be unique)
    "Task aborted.",            # dispatch abort comment
    "Dispatching `/",           # initial sticky body (e.g. "Dispatching `/plan`…")
    "Resuming `",               # initial sticky body for resume (e.g. "Resuming `plan` session…")
)


def _find_last_completion_id(comments: list[CommentLike]) -> int | None:
    """Find ID of the last completion comment.

    Normalizes the body before checking so ADO body transformations
    (HTML entities, markdown rendering, whitespace changes) don't break
    the string match.

    Fallback: if no IDs are found, returns the timestamp of the last
    completion comment (for backward compat with old queue entries and
    test fixtures that don't have comment IDs).
    """
    for comment in reversed(comments):
        body = _get_body(comment)
        normalized = _normalize_body(body)
        if 'completed with command' in normalized:
            cid = _get_id(comment)
            if cid is not None:
                return cid
    # Fallback: return timestamp for backward compat
    return _find_last_completion(comments)


def _find_last_bot_comment_id(comments: list[CommentLike]) -> int | None:
    """ID of the last bot comment (any type, not just completions).

    Fallback: if no IDs are found, returns the timestamp of the last
    bot comment (for backward compat with old queue entries and test
    fixtures that don't have comment IDs).
    """
    for comment in reversed(comments):
        if _is_autoswe_bot_comment(comment):
            cid = _get_id(comment)
            if cid is not None:
                return cid
    # Fallback: return timestamp for backward compat
    return _find_last_bot_comment_ts(comments)


_PLAN_RE = re.compile(r"<AUTOSWE_PLAN>(.*?)</AUTOSWE_PLAN>", re.DOTALL)
_QUESTIONS_RE = re.compile(r"<AUTOSWE_QUESTIONS>(.*?)</AUTOSWE_QUESTIONS>", re.DOTALL)


# ---------------------------------------------------------------------------
# Compatibility aliases — timestamp-based variants for legacy test files
# TODO: remove after queue migration
# ---------------------------------------------------------------------------

def _find_last_completion(comments: list[CommentLike]) -> str | None:
    """Timestamp of the last completion comment (compatibility alias).

    Used by legacy test files. Prefer `_find_last_completion_id` in new code.
    TODO: remove after queue migration.
    """
    for comment in reversed(comments):
        body = _get_body(comment)
        normalized = _normalize_body(body)
        if 'completed with command' in normalized:
            return _get_created_at(comment) or ""
    return None


def _find_last_bot_comment_ts(comments: list[CommentLike]) -> str | None:
    """Timestamp of the last bot comment (compatibility alias).

    Used by legacy test files. Prefer `_find_last_bot_comment_id` in new code.
    TODO: remove after queue migration.
    """
    for comment in reversed(comments):
        if _is_autoswe_bot_comment(comment):
            return _get_created_at(comment) or ""
    return None


