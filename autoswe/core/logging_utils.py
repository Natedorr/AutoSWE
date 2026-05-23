import logging
import logging.handlers
from datetime import datetime, timezone
from pathlib import Path

from autoswe.core.slug import slug_to_filename


def log(msg: str) -> None:
    print(f"[{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}] {msg}", flush=True)
    # Also emit to the debug logger so per-issue handlers capture it.
    # Uses a direct getLogger call — safe even if init_debug_logger not yet called.
    try:
        logging.getLogger("autoswe.debug").info(msg)
    except Exception:
        pass  # logger not initialized or misconfigured — stdout is the safety net


def init_debug_logger(logs_dir: Path) -> logging.Logger:
    logger = logging.getLogger("autoswe.debug")
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    log_path = logs_dir / "autoswe.log"
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(
            log_path, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
    except OSError as e:
        logger.addHandler(logging.NullHandler())
        print(f"[WARN] could not open debug log {log_path}: {e}", flush=True)
        return logger
    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-8s %(funcName)s:%(lineno)d — %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )
    fmt.converter = __import__("time").gmtime
    handler.setFormatter(fmt)
    logger.addHandler(handler)
    stderr_handler = logging.StreamHandler()
    stderr_handler.setLevel(logging.WARNING)
    stderr_handler.setFormatter(fmt)
    logger.addHandler(stderr_handler)
    return logger


def _get_fmt():
    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-8s %(funcName)s:%(lineno)d — %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )
    fmt.converter = __import__("time").gmtime
    return fmt


def init_issue_logger(logs_dir: Path, slug: str) -> logging.Handler:
    """Add a handler that writes to logs/{slug}/{slug}.log.
    Returns the handler for later cleanup (pass to remove_issue_logger).

    The slug is sanitized (':' and '/' replaced with '_') so that Azure DevOps
    slugs like ``ado:org_proj_repo/70`` produce valid file paths.
    """
    logger = logging.getLogger("autoswe.debug")
    safe_slug = slug_to_filename(slug)
    issue_dir = logs_dir / safe_slug
    issue_dir.mkdir(parents=True, exist_ok=True)
    log_path = issue_dir / f"{safe_slug}.log"
    try:
        handler = logging.handlers.RotatingFileHandler(
            log_path, maxBytes=1_000_000, backupCount=2, encoding="utf-8"
        )
    except OSError as e:
        print(f"[WARN] could not open issue log {log_path}: {e}", flush=True)
        return None
    handler.setFormatter(_get_fmt())
    logger.addHandler(handler)
    return handler


def remove_issue_logger(handler: logging.Handler) -> None:
    """Remove and close a per-issue handler."""
    if handler is None:
        return
    logger = logging.getLogger("autoswe.debug")
    logger.removeHandler(handler)
    handler.close()
