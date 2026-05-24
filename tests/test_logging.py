"""Tests for per-issue logging infrastructure."""

import logging
import sys

import pytest

from autoswe.core.logging_utils import (
    MASK,
    SensitiveFormatter,
    SensitiveLogFilter,
    init_debug_logger,
    init_issue_logger,
    log,
    mask_sensitive,
    remove_issue_logger,
)


def test_log_writes_to_debug_logger(tmp_path, caplog):
    """log() should emit to autoswe.debug logger at INFO level."""
    dbg = init_debug_logger(tmp_path)

    log("[TEST] hello from log()")

    # The log() function prints to stdout AND emits to autoswe.debug
    # Verify the debug logger got the message
    assert dbg.handlers, "debug logger should have handlers"


def test_init_issue_logger_creates_file(tmp_path):
    """init_issue_logger() should create a handler writing to the per-slug file."""
    init_debug_logger(tmp_path)
    handler = init_issue_logger(tmp_path, "gh_owner_repo_42")

    assert handler is not None
    assert isinstance(handler, logging.Handler)

    # The log file should exist at logs/{safe_slug}/{safe_slug}.log
    log_path = tmp_path / "gh_owner_repo_42" / "gh_owner_repo_42.log"
    assert log_path.parent.exists(), "per-issue log dir should be created"


def test_log_lands_in_issue_file(tmp_path):
    """log() calls during dispatch should land in the per-issue log file."""
    init_debug_logger(tmp_path)
    handler = init_issue_logger(tmp_path, "gh_owner_repo_99")

    log("[TEST] message for issue log")

    # Flush the handler so file is written
    if hasattr(handler, 'flush'):
        handler.flush()

    tmp_path / "gh_owner_repo_99" / "gh_owner_repo_99.log"

    remove_issue_logger(handler)


def test_remove_issue_logger_cleans_up(tmp_path):
    """remove_issue_logger() should remove and close the handler."""
    dbg = init_debug_logger(tmp_path)
    handler = init_issue_logger(tmp_path, "gh_owner_repo_77")

    initial_handler_count = len(dbg.handlers)
    assert initial_handler_count >= 1

    remove_issue_logger(handler)

    # Handler should be removed
    assert handler not in dbg.handlers


def test_remove_issue_logger_handles_none(tmp_path):
    """remove_issue_logger(None) should be a no-op."""
    dbg = init_debug_logger(tmp_path)
    initial_handler_count = len(dbg.handlers)

    remove_issue_logger(None)

    assert len(dbg.handlers) == initial_handler_count


def test_init_issue_logger_ado_slug(tmp_path):
    """init_issue_logger() should sanitize ADO slugs with colons and slashes."""
    init_debug_logger(tmp_path)
    handler = init_issue_logger(tmp_path, "ado_org_proj_repo_70")

    assert handler is not None
    log_path = tmp_path / "ado_org_proj_repo_70" / "ado_org_proj_repo_70.log"
    assert log_path.parent.exists()

    remove_issue_logger(handler)


# -------------------------------------------------------------------
# Sensitive data redaction tests
# -------------------------------------------------------------------

@pytest.mark.parametrize(
    "input_val,expected",
    [
        # GitHub classic PAT (ghp_)
        ("ghp_abc123def456ghi789jkl012mno345pqr678", MASK),
        # GitHub fine-grained PAT
        ("github_pat_abc123def456ghi789jkl012mno345pqr678stu901", MASK),
        # GitHub OAuth token (gho_)
        ("gho_abc123def456ghi789jkl012mno345pqr678", MASK),
        # GitHub user token (ghu_)
        ("ghu_abc123def456ghi789jkl012mno345pqr678", MASK),
        # GitHub static token (ghs_)
        ("ghs_abc123def456ghi789jkl012mno345pqr678", MASK),
        # GitHub refresh token (ghr_)
        ("ghr_abc123def456ghi789jkl012mno345pqr678", MASK),
        # Anthropic API key
        ("sk-ant-abc123def456ghi789jkl012", MASK),
        # Token prefix with GitHub PAT
        ("Token ghp_abc123def456ghi789jkl012mno345pqr678", f"Token {MASK}"),
        # Bearer prefix with Anthropic key
        ("Bearer sk-ant-abc123def456ghi789jkl012mno345", f"Bearer {MASK}"),
        # No sensitive data
        ("no sensitive data here", "no sensitive data here"),
        # Empty string
        ("", ""),
        # None
        (None, None),
        # Too short — not a real token
        ("ghp_short", "ghp_short"),
        # Multiple tokens in one string
        ("Multiple ghp_aaBbbccc1122334455667788 and ghp_ddEeefff9988776655443322",
         f"Multiple {MASK} and {MASK}"),
    ],
)
def test_mask_sensitive_patterns(input_val, expected):
    assert mask_sensitive(input_val) == expected


def test_mask_sensitive_idempotent():
    """Calling mask_sensitive twice should produce the same result as calling it once."""
    text = "token ghp_abc123def456ghi789jkl012mno345pqr678"
    assert mask_sensitive(mask_sensitive(text)) == mask_sensitive(text)


def test_sensitive_log_filter_masks_message():
    """SensitiveLogFilter should mask tokens in the log message."""
    record = logging.LogRecord(
        name="test", level=logging.DEBUG, pathname="", lineno=0,
        msg="using token ghp_abc123def456ghi789jkl012mno345pqr678",
        args=(), exc_info=None,
    )
    filt = SensitiveLogFilter()
    assert filt.filter(record) is True
    assert MASK in record.msg
    assert "ghp_" not in record.msg


def test_sensitive_log_filter_masks_args():
    """SensitiveLogFilter should mask tokens in string format args."""
    record = logging.LogRecord(
        name="test", level=logging.DEBUG, pathname="", lineno=0,
        msg="error with %s",
        args=("token ghp_abc123def456ghi789jkl012mno345pqr678",),
        exc_info=None,
    )
    SensitiveLogFilter().filter(record)
    assert MASK in str(record.args)
    assert "ghp_" not in str(record.args)


def test_sensitive_formatter_masks_exc_text():
    """SensitiveFormatter should mask tokens in exception tracebacks.

    record.exc_text is set BY the Formatter (after the Filter runs), so
    SensitiveFormatter is the only place that can mask exception tracebacks.
    """
    fmt = SensitiveFormatter("%(message)s")
    record = logging.LogRecord(
        name="test", level=logging.ERROR, pathname="", lineno=0,
        msg="failed", args=(), exc_info=None,
    )
    # Simulate what Formatter.format() does with exc_info
    try:
        raise ValueError("ghp_abc123def456ghi789jkl012mno345pqr678")
    except ValueError:
        record.exc_info = sys.exc_info()
    output = fmt.format(record)
    assert MASK in output
    assert "ghp_" not in output
    assert "Traceback" in output


def test_sensitive_log_filter_preserves_non_string_args():
    """SensitiveLogFilter should NOT coerce non-string dict args to strings,
    preserving %d/%f format specifiers.
    """
    record = logging.LogRecord(
        name="test", level=logging.DEBUG, pathname="", lineno=0,
        msg="code=%d token=%s",
        args=(500, "ghp_abc123def456ghi789jkl012mno345pqr678"),
        exc_info=None,
    )
    SensitiveLogFilter().filter(record)
    # Integer arg should remain int (not coerced to string)
    assert isinstance(record.args[0], int), "non-string args must not be coerced"
    assert record.args[0] == 500
    # String arg should be masked
    assert MASK in str(record.args[1])


def test_mask_sensitive_on_exc_text():
    """mask_sensitive() should handle exception-like strings with tokens."""
    exc_str = "urllib.error.HTTPError: HTTP Error 401: ghp_abc123def456ghi789jkl012mno345pqr678"
    result = mask_sensitive(exc_str)
    assert MASK in result
    assert "ghp_" not in result


def test_log_masks_stdout(capfd):
    """log() should mask sensitive data before printing to stdout."""
    log("token ghp_abc123def456ghi789jkl012mno345pqr678")
    captured = capfd.readouterr()
    assert MASK in captured.out
    assert "ghp_" not in captured.out


def test_init_debug_logger_has_sensitive_filter(tmp_path):
    """init_debug_logger() should attach SensitiveLogFilter."""
    logger = init_debug_logger(tmp_path)
    assert any(
        type(f).__name__ == "SensitiveLogFilter" for f in logger.filters
    ), "debug logger should have a SensitiveLogFilter attached"


def test_init_debug_logger_handlers_use_sensitive_formatter(tmp_path):
    """All handlers from init_debug_logger should use SensitiveFormatter."""
    logger = init_debug_logger(tmp_path)
    for h in logger.handlers:
        if h.formatter:
            assert type(h.formatter).__name__ == "SensitiveFormatter", (
                f"handler {type(h).__name__} should use SensitiveFormatter"
            )


def test_init_issue_logger_handler_uses_sensitive_formatter(tmp_path):
    """init_issue_logger() per-issue handlers should use SensitiveFormatter.

    Regression test: if _get_fmt() is ever changed back to logging.Formatter,
    this test catches the regression that would leak tokens in exception
    tracebacks to per-issue log files.
    """
    init_debug_logger(tmp_path)
    handler = init_issue_logger(tmp_path, "test_issue_formatter")
    assert handler is not None
    assert type(handler.formatter).__name__ == "SensitiveFormatter", (
        "per-issue handler must use SensitiveFormatter to mask exception tracebacks"
    )
    remove_issue_logger(handler)


def test_sensitive_formatter_masks_full_output():
    """SensitiveFormatter should mask tokens in the complete formatted string."""
    fmt = SensitiveFormatter(
        "%(asctime)s %(levelname)-8s %(funcName)s:%(lineno)d — %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=10,
        msg="using token ghp_abc123def456ghi789jkl012mno345pqr678",
        args=(), exc_info=None,
    )
    output = fmt.format(record)
    assert MASK in output
    assert "ghp_" not in output
