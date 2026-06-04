"""Logging setup with sensitive-data redaction.

Provides ``init_debug_logger()`` (stdout + rotating file), per-issue handlers,
a module-level ``log()`` helper for user-facing stdout lines, and the
SensitiveLogFilter / SensitiveFormatter pair that mask credentials before any
formatter sees them.  Use ``get_debug_logger()`` to obtain the shared debug logger
without importing ``LOGS_DIR`` in every module.

The debug logger (name = ``autoswe.debug``) is intended for internal diagnostics.
Always use lazy %-style formatting with it (e.g. ``dbg.info("x=%s", x)``), so that
SensitiveLogFilter can mask format args before interpolation.  Reserve the
top-level ``log()`` helper for user-facing stdout lines that must be visible to
the operator regardless of log level.
"""
import logging
import logging.handlers
import re
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from autoswe.core.slug import slug_to_filename

# --- Sensitive data redaction ------------------------------------------------

MASK = "***REDACTED***"

# Compiled regex patterns for sensitive data detection, paired with their
# replacement values.  Most entries use a simple string replacement; the URL
# credential pattern uses a callable to preserve the parameter name.
# Minimum length thresholds prevent false positives on short alphanumeric strings.


def _replace_url_cred(m: re.Match[str]) -> str:
    """Replacement callable for URL credential patterns.

    Preserves the parameter name (e.g. ``?token=``) and replaces only the value.
    """
    return m.group(1) + MASK


_REDACTION_PATTERNS: list[re.Pattern[str]] = [
    # GitHub tokens: classic (ghp_), OAuth (gho_), user (ghu_), static (ghs_), refresh (ghr_)
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    # GitHub fine-grained PAT
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    # Anthropic API key
    re.compile(r"sk-ant-[A-Za-z0-9\-]{20,}"),
    # Generic "Token <value>" / "Bearer <value>" with long secrets (catches Azure PATs)
    re.compile(r"(?:[Bb]earer|[Tt]oken)\s+[A-Za-z0-9_\-\.]{20,}"),
    # Basic auth header (Azure DevOps base64-encoded credentials)
    re.compile(r"Basic\s+[A-Za-z0-9+/=]{20,}"),
    # URL credential parameters: ?pat=xxx, &token=xxx, ?password=xxx, etc.
    re.compile(r"([?&](?:pat|token|password|access_token|api_key)=)[^&\s]+", re.IGNORECASE),
]

# Replacement value for each entry in _REDACTION_PATTERNS (same index).
_REDACTION_REPLACEMENTS: list[str | Callable] = [
    MASK,  # GitHub tokens (ghp_, gho_, etc.)
    MASK,  # GitHub fine-grained PAT
    MASK,  # Anthropic API key
    MASK,  # Bearer/Token prefix
    MASK,  # Basic auth header
    _replace_url_cred,  # URL credentials (preserves param name)
]


def mask_sensitive(text: str | None) -> str | None:
    """Redact sensitive tokens/API keys from a string.

    Returns a copy of *text* with any detected credential pattern replaced by
    ``***REDACTED***``.  Safe to call on already-masked text (idempotent).
    """
    if not text:
        return text
    for pattern, replacement in zip(_REDACTION_PATTERNS, _REDACTION_REPLACEMENTS, strict=True):
        text = pattern.sub(replacement, text)
    return text


class SensitiveLogFilter(logging.Filter):
    """Logging filter that masks sensitive data in every log record's message
    and format args BEFORE the Formatter processes them.

    Scrubs the **rendered** message (via ``record.getMessage()``) so that tokens
    appearing in format-arg substitution are also caught.  After scrubbing,
    ``record.msg`` is replaced with the pre-rendered string and ``record.args``
    is cleared to prevent the Formatter from re-interpolating.

    Note: ``record.exc_text`` is NOT set at filter time (it's populated by the
    Formatter), so exception traceback masking is handled by
    :class:`SensitiveFormatter`.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        # First mask args individually so they don't leak if getMessage()
        # fails (e.g. mismatched format specs).
        if hasattr(record, "args") and record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: mask_sensitive(v) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, (tuple, list)):
                record.args = tuple(
                    mask_sensitive(a) if isinstance(a, str) else a
                    for a in record.args
                )

        # Scrub the rendered message — catches tokens from format-arg
        # substitution as well as hardcoded tokens in the message template.
        rendered = record.getMessage()
        scrubbed = mask_sensitive(rendered)
        if scrubbed != rendered:
            record.msg = scrubbed
            record.args = ()

        return True


class SensitiveFormatter(logging.Formatter):
    """Formatter that masks sensitive data in the final formatted output.

    This catches tokens that appear in exception tracebacks (``exc_text``),
    which are set by the Formatter AFTER the Filter runs and therefore
    cannot be masked by :class:`SensitiveLogFilter` alone.
    """

    def format(self, record: logging.LogRecord) -> str:
        result = super().format(record)
        return mask_sensitive(result)


def log(msg: str) -> None:
    """Print a timestamped line to stdout and emit to the debug logger.

    Intended for user-facing status lines (dispatch start/end, commit info).
    Use lazy %-style ``dbg.*`` calls for internal diagnostics so that format args
    pass through SensitiveLogFilter before interpolation.
    """
    masked = mask_sensitive(msg)
    print(f"[{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}] {masked}", flush=True)
    # Also emit to the debug logger so per-issue handlers capture it.
    # Uses a direct getLogger call — safe even if init_debug_logger not yet called.
    try:
        logging.getLogger("autoswe.debug").info(masked)
    except Exception:  # poller-resilience; stdout is the safety net
        pass


def init_debug_logger(logs_dir: Path) -> logging.Logger:
    """Build (once) the shared ``autoswe.debug`` logger.

    Subsequent calls return the existing instance without adding duplicate handlers.
    Prefer :func:`get_debug_logger()` in module-level code so modules don't need to
    import ``LOGS_DIR`` separately.
    """
    logger = logging.getLogger("autoswe.debug")
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    logger.addFilter(SensitiveLogFilter())
    log_path = logs_dir / "autoswe.log"
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(
            log_path, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
    except OSError as e:  # poller-resilience; fall back to NullHandler
        logger.addHandler(logging.NullHandler())
        print(f"[WARN] could not open debug log {log_path}: {e}", flush=True)
        return logger
    fmt = _get_fmt()
    handler.setFormatter(fmt)
    logger.addHandler(handler)
    stderr_handler = logging.StreamHandler()
    stderr_handler.setLevel(logging.WARNING)
    stderr_handler.setFormatter(_get_fmt())
    logger.addHandler(stderr_handler)
    return logger


def get_debug_logger(logs_dir: Path | None = None) -> logging.Logger:
    """Return the shared ``autoswe.debug`` logger, initializing it lazily.

    Modules should use this instead of calling ``init_debug_logger(LOGS_DIR)`` so
    they don't need to import ``LOGS_DIR`` at module level on every import.

    If *logs_dir* is not provided (or None), the default ``LOGS_DIR`` from config
    is used.  The logger name is always ``"autoswe.debug"``; calls are idempotent —
    subsequent invocations return the existing instance immediately without adding
    duplicate handlers.

    Returns a :class:`logging.Logger` configured with SensitiveLogFilter (so
    credentials in log messages and format args are masked before any handler)."""
    if logs_dir is None:
        # Deferred import to avoid circular dependency at module load time
        from autoswe.core.config import LOGS_DIR as default_logs_dir
        logs_dir = default_logs_dir

    existing = logging.getLogger("autoswe.debug")
    if existing.handlers:
        return existing
    return init_debug_logger(logs_dir)


def _get_fmt() -> SensitiveFormatter:
    """Build the standard log formatter with UTC datefmt."""
    fmt = SensitiveFormatter(
        "%(asctime)s %(levelname)-8s %(funcName)s:%(lineno)d — %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )
    fmt.converter = time.gmtime  # type: ignore[assignment]
    return fmt


def init_issue_logger(logs_dir: Path, slug: str) -> logging.Handler | None:
    """Add a handler that writes to logs/{slug}/{slug}.log.

    Returns the handler for later cleanup (pass to ``remove_issue_logger``).

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
    except OSError as e:  # poller-resilience; warn and return None
        print(f"[WARN] could not open issue log {log_path}: {e}", flush=True)
        return None
    handler.setFormatter(_get_fmt())
    logger.addHandler(handler)
    return handler


def remove_issue_logger(handler: logging.Handler | None) -> None:
    """Remove and close a per-issue handler."""
    if handler is None:
        return
    logger = logging.getLogger("autoswe.debug")
    logger.removeHandler(handler)
    handler.close()
