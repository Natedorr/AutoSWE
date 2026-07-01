"""Sticky progress comment — one comment, edited live during dispatch.

Posts an initial comment at dispatch start, throttles edits to max 1 per 10s,
and finalizes with the completion body when the handler returns.
"""
from __future__ import annotations

import time

from autoswe.core.logging_utils import get_debug_logger, log
from autoswe.tracking.comments import BOT_MARKER

_dbg = get_debug_logger()


def _tag(body: str) -> str:
    """Idempotently append BOT_MARKER so every outbound comment is detectable."""
    if BOT_MARKER not in body:
        body = body.rstrip() + "\n" + BOT_MARKER
    return body


_MIN_UPDATE_INTERVAL_S = 10


class ProgressComment:
    """Manage a single sticky progress comment for a dispatch.

    Usage:
        progress = ProgressComment(tracker, repo_cfg, issue_num)
        progress.create("Starting fix...")
        progress.update("Running: pytest tests/")
        # ... handler runs ...
        progress.finalize("Completed with command `/fix` ...")

    On providers that support comment editing (GitHub), edits the sticky
    comment in-place. On providers that don't (Azure), falls back to posting
    a new comment so the final message is never lost.
    """

    def __init__(self, tracker, repo_cfg: dict, issue_num: int, *, minimal: bool = False):
        self._tracker = tracker
        self._repo_cfg = repo_cfg
        self._issue_num = issue_num
        self._comment_id: int | None = None
        self._last_update: float = 0.0
        self._pending_body: str | None = None
        self._minimal = minimal

    @property
    def comment_id(self) -> int | None:
        return self._comment_id

    def create(self, initial_body: str) -> int | None:
        """Post the initial progress comment. Returns comment ID or None."""
        try:
            self._comment_id = self._tracker.post_comment(
                self._repo_cfg, self._issue_num, _tag(initial_body),
            )
            log(f"[PROGRESS] POST comment={self._comment_id}")
            return self._comment_id
        except Exception:  # Progress comment creation is best-effort; handler should continue
            _dbg.warning("progress: create comment failed", exc_info=True)
            return None

    def adopt(self, comment_id: int, resume_body: str) -> int | None:
        """Re-use an already-posted sticky comment instead of posting a new one.

        Used on a /retry after a crashed dispatch: the prior attempt's sticky
        comment is refreshed in place so the retry writes to the same comment
        the user is already watching. Falls back to create() if the edit fails
        (e.g. the comment was deleted).
        """
        self._comment_id = comment_id
        log(f"[PROGRESS] ADOPT comment={comment_id}")
        try:
            self._tracker.update_comment(
                self._repo_cfg, self._issue_num, comment_id, _tag(resume_body),
            )
            self._last_update = time.monotonic()
            return comment_id
        except Exception:  # Comment gone/uneditable — post a fresh one so nothing is lost
            _dbg.warning("progress: adopt failed, posting new comment", exc_info=True)
            self._comment_id = None
            return self.create(resume_body)

    def update(self, body: str) -> None:
        """Queue a throttled edit. At most one edit per 10s.

        Intermediate calls coalesce — only the latest body is kept,
        applied on the next eligible edit.
        """
        if self._comment_id is None:
            return
        if self._minimal:
            self._pending_body = body
            return
        now = time.monotonic()
        if now - self._last_update < _MIN_UPDATE_INTERVAL_S:
            self._pending_body = body
            return
        self._flush(body)

    def finalize(self, body: str) -> None:
        """Write the final body (no throttle). Called after handler returns."""
        if self._comment_id is not None:
            self._flush(body, force=True)

    def _flush(self, body: str, *, force: bool = False) -> None:
        if not force and time.monotonic() - self._last_update < _MIN_UPDATE_INTERVAL_S:
            return
        tagged = _tag(body)
        log(f"[PROGRESS] PATCH comment={self._comment_id} body_len={len(tagged)} preview={tagged[:100]!r}")
        try:
            self._tracker.update_comment(self._repo_cfg, self._issue_num, self._comment_id, tagged)
            self._last_update = time.monotonic()
            self._pending_body = None
        except Exception:  # Provider doesn't support comment editing; post a new comment instead
            _dbg.warning("progress: update_comment failed, falling back to post_comment", exc_info=True)
            try:
                new_id = self._tracker.post_comment(self._repo_cfg, self._issue_num, tagged)
                if new_id is not None:
                    self._comment_id = new_id
                    log(f"[PROGRESS] Switched to fallback comment={new_id}")
                self._last_update = time.monotonic()
                self._pending_body = None
            except Exception:  # Both update and fallback post failed — silently give up
                _dbg.warning("progress: fallback post_comment also failed", exc_info=True)

    def drain(self) -> None:
        """Apply any pending coalesced update. Call before finalize."""
        if self._pending_body:
            self._flush(self._pending_body, force=True)
