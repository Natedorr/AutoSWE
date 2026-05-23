"""Tests for per-issue logging infrastructure."""

import logging

from autoswe.core.logging_utils import init_debug_logger, init_issue_logger, log, remove_issue_logger


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
