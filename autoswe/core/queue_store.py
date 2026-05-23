import json

import portalocker

from autoswe.core.config import AUTOSWE_DIR, LOGS_DIR, QUEUE_FILE
from autoswe.core.logging_utils import init_debug_logger, log

dbg = init_debug_logger(LOGS_DIR)


def _atomic_write(path, data) -> None:
    """Write JSON atomically via a temp file."""
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(data, indent=2))
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
