import json

import portalocker

from autoswe.core.config import AUTOSWE_DIR, QUEUE_FILE
from autoswe.core.logging_utils import get_debug_logger, log

dbg = get_debug_logger()


def _atomic_write(path, data) -> None:
    """Write JSON atomically via a temp file."""
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(path)
    except OSError as e:
        dbg.error("_atomic_write: failed to write %s: %s", path, e, exc_info=True)
        raise


def _load_json(path, default):
    if path.exists():
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError as e:
            dbg.warning("_load_json: corrupt JSON at %s (offset %d): %s", path, e.pos, e.msg)
            log(f"[WARN] corrupt JSON at {path}, resetting")
    return default


class LockedQueue:
    """Context manager that loads queue.json under a file lock (cross-platform)."""

    def __init__(self):
        self._lock_path = AUTOSWE_DIR / "data" / ".queue.lock"
        self._fh = None

    def __enter__(self):
        try:
            self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            dbg.error("LockedQueue: cannot create lock dir %s: %s",
                      self._lock_path.parent, e, exc_info=True)
            raise
        self._fh = open(self._lock_path, "a+")
        try:
            portalocker.lock(self._fh, portalocker.LOCK_EX)
        except portalocker.LockException as e:
            dbg.error("LockedQueue: lock failed on %s: %s", self._lock_path, e, exc_info=True)
            self._fh.close()
            raise
        self.queue = _load_json(QUEUE_FILE, {})
        return self

    def __exit__(self, *_):
        _atomic_write(QUEUE_FILE, self.queue)
        portalocker.unlock(self._fh)
        self._fh.close()


def load_queue() -> dict:
    """Load queue.json under a brief exclusive lock, then release it.

    The lock is held only long enough to read the file (issue #173 F-12): the
    caller does its (potentially long) work *without* holding the lock and
    persists via :func:`save_queue`.
    """
    with LockedQueue() as lq:
        return lq.queue


def save_queue(queue: dict) -> None:
    """Re-acquire the lock, merge *queue* onto the on-disk state, save, release.

    *queue* is the caller's in-memory snapshot loaded via :func:`load_queue` and
    mutated during the (lock-free) dispatch phase. Because the lock is released
    across the agent run (issue #173 F-12), a concurrent poller may have written
    to the same file while we worked. We therefore merge against a *fresh* read
    of the on-disk state rather than replacing it wholesale:

    * A slug the caller never touched is untouched (concurrent adds survive).
    * A slug the caller *did* touch: the caller's entry wins for the
      dispatch/status fields it owns (a given slug is dispatched by at most one
      poller at a time, guarded by the per-slug PID lock), BUT the append-only
      ``bot_comment_ids`` list is **unioned** with the on-disk value so
      comment IDs a concurrent poller appended between our load and save are
      not clobbered. (``bot_comment_ids`` is the one field written outside the
      PID guard — by the self-healing backfill and welcome paths — so a plain
      last-writer-wins whole-entry overwrite would silently drop those IDs.)
    """
    with LockedQueue() as lq:
        for slug, entry in queue.items():
            on_disk = lq.queue.get(slug)
            if on_disk is not None:
                # Preserve the caller's authoritative dispatch/status fields
                # while unioning the append-only comment-ID set.
                ours = list(entry.get("bot_comment_ids") or [])
                theirs = list(on_disk.get("bot_comment_ids") or [])
                entry["bot_comment_ids"] = list(dict.fromkeys(ours + theirs))
            lq.queue[slug] = entry
