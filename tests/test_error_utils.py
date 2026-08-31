"""Tests for autoswe/core/error_utils.py — dispatch error diagnostics."""
from __future__ import annotations

import subprocess

from autoswe.core.error_utils import (
    DispatchErrorContext,
    capture_dispatch_error,
    format_error_comment,
)
from autoswe.tracking.comments import BOT_MARKER

# ---------------------------------------------------------------------------
# capture_dispatch_error
# ---------------------------------------------------------------------------


def test_capture_dispatch_error_captures_traceback():
    """capture_dispatch_error should capture exception type, message, and traceback."""
    try:
        raise ValueError("test error message")
    except ValueError as exc:
        ctx = capture_dispatch_error(exc, "gh:owner_repo_1", None)

    assert ctx.exception_type == "ValueError"
    assert ctx.exception_message == "test error message"
    assert len(ctx.traceback_lines) > 0
    assert any("ValueError" in line for line in ctx.traceback_lines)
    assert any("test error message" in line for line in ctx.traceback_lines)
    assert ctx.slug == "gh:owner_repo_1"
    assert ctx.worktree_path == ""
    assert ctx.worktree_exists is False


def test_capture_dispatch_error_with_worktree(tmp_path):
    """capture_dispatch_error should capture git info from an existing worktree."""
    wt = tmp_path / "worktree"
    wt.mkdir()
    subprocess.run(["git", "init", str(wt)], capture_output=True, timeout=5)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=wt, capture_output=True, timeout=5)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=wt, capture_output=True, timeout=5)
    (wt / "README.md").write_text("hello")
    subprocess.run(["git", "add", "README.md"], cwd=wt, capture_output=True, timeout=5)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=wt, capture_output=True, timeout=5)

    try:
        raise RuntimeError("worktree error")
    except RuntimeError as exc:
        ctx = capture_dispatch_error(exc, "gh:owner_repo_1", str(wt))

    assert ctx.worktree_exists is True
    assert ctx.worktree_path == str(wt)
    assert ctx.git_branch == "master" or ctx.git_branch == "main"
    assert "initial" in ctx.git_log
    assert ctx.exception_type == "RuntimeError"


def test_capture_dispatch_error_missing_worktree():
    """capture_dispatch_error should record worktree non-existence."""
    try:
        raise FileNotFoundError("no worktree")
    except FileNotFoundError as exc:
        ctx = capture_dispatch_error(exc, "gh:owner_repo_1", "/nonexistent/path")

    assert ctx.worktree_path == "/nonexistent/path"
    assert ctx.worktree_exists is False
    assert ctx.git_branch == ""
    assert ctx.git_log == ""
    assert ctx.git_status == ""


def test_capture_dispatch_error_no_worktree_path():
    """capture_dispatch_error with worktree=None should not crash."""
    try:
        raise OSError("no worktree path")
    except OSError as exc:
        ctx = capture_dispatch_error(exc, "gh:owner_repo_2", None)

    assert ctx.worktree_path == ""
    assert ctx.worktree_exists is False
    assert ctx.git_branch == ""


def test_capture_dispatch_error_includes_system_info():
    """capture_dispatch_error should include python version and kernel."""
    try:
        raise SystemError("test")
    except SystemError as exc:
        ctx = capture_dispatch_error(exc, "gh:owner_repo_1", None)

    assert ctx.python_version != ""
    assert ctx.kernel_version != ""


def test_capture_dispatch_error_system_memory_populated(tmp_path):
    """system_memory and disk_usage must be populated (not just non-raising).

    Regression test for issue #173 F-24: on the documented Windows host the
    /proc/meminfo + os.statvfs path raised and both fields were silently
    empty, so the System section dropped out of the error comment.
    """
    worktree = tmp_path / "wt"
    worktree.mkdir()

    try:
        raise RuntimeError("boom")
    except RuntimeError as exc:
        ctx = capture_dispatch_error(exc, "gh:owner_repo_1", str(worktree))

    assert ctx.system_memory, "system_memory must be populated on this platform"
    assert ctx.system_memory != "Memory: unavailable on this platform", (
        f"system_memory fell back to the unavailable marker: {ctx.system_memory!r}"
    )
    assert ctx.disk_usage, "disk_usage must be populated when a worktree is given"
    assert "Disk:" in ctx.disk_usage, f"unexpected disk_usage shape: {ctx.disk_usage!r}"
    # The formatted comment should surface the populated System section.
    body = format_error_comment(ctx)
    assert "**System:**" in body


def test_get_memory_info_always_populated():
    """_get_memory_info must never return the empty string (issue #173 F-24)."""
    from autoswe.core.error_utils import _get_memory_info

    assert _get_memory_info() != ""


def test_get_disk_usage_always_populated(tmp_path):
    """_get_disk_usage must never return the empty string (issue #173 F-24)."""
    from autoswe.core.error_utils import _get_disk_usage

    assert _get_disk_usage(str(tmp_path)) != ""


def test_get_disk_usage_unreadable_path_reports_unavailable(tmp_path, monkeypatch):
    """When disk stats can't be read, the field still reports something."""
    from autoswe.core import error_utils

    def _boom(_):
        raise OSError("no such filesystem")

    monkeypatch.setattr("shutil.disk_usage", _boom)
    out = error_utils._get_disk_usage("/definitely/not/here")
    assert out != ""
    assert "unavailable" in out


# ---------------------------------------------------------------------------
# format_error_comment
# ---------------------------------------------------------------------------


def test_format_error_comment_includes_retry_instruction():
    """format_error_comment should include /retry instruction and BOT_MARKER."""
    ctx = DispatchErrorContext(
        exception_type="RuntimeError",
        exception_message="something broke",
        traceback_lines=["File 'x.py', line 1", "RuntimeError: something broke"],
        slug="gh:owner_repo_1",
        python_version="3.12",
        kernel_version="6.1.0",
    )
    body = format_error_comment(ctx)

    assert BOT_MARKER in body
    assert "/retry" in body
    assert "something broke" in body


def test_format_error_comment_includes_system_info():
    """format_error_comment should include system info section."""
    ctx = DispatchErrorContext(
        exception_type="RuntimeError",
        exception_message="test",
        traceback_lines=["line1"],
        slug="gh:owner_repo_1",
        python_version="3.12",
        kernel_version="6.1.0",
        system_memory="MemTotal: 16384000 kB",
        disk_usage="Disk: 50.0GB free / 100.0GB total",
    )
    body = format_error_comment(ctx)

    assert "Python 3.12" in body
    assert "Kernel 6.1.0" in body
    assert "MemTotal" in body
    assert "Disk:" in body


def test_format_error_comment_includes_git_info():
    """format_error_comment should include git info when worktree exists."""
    ctx = DispatchErrorContext(
        exception_type="RuntimeError",
        exception_message="test",
        traceback_lines=["line1"],
        slug="gh:owner_repo_1",
        worktree_path="/some/path",
        worktree_exists=True,
        git_branch="autoswe/issue-1",
        git_log="abc123 initial\n\ndef456 fix typo",
        git_status=" M README.md",
        python_version="3.12",
    )
    body = format_error_comment(ctx)

    assert "autoswe/issue-1" in body
    assert "initial" in body
    assert " M README.md" in body


def test_format_error_comment_includes_traceback():
    """format_error_comment should include traceback (truncated after 20 lines)."""
    lines = [f"Line {i}" for i in range(30)]
    ctx = DispatchErrorContext(
        exception_type="ValueError",
        exception_message="test",
        traceback_lines=lines,
        slug="gh:owner_repo_1",
    )
    body = format_error_comment(ctx)

    assert "Line 0" in body
    assert "Line 19" in body
    assert "10 more lines" in body
    assert "Line 29" not in body  # truncated


def test_format_error_comment_missing_worktree_shows_not_found():
    """format_error_comment should note when worktree path doesn't exist."""
    ctx = DispatchErrorContext(
        exception_type="RuntimeError",
        exception_message="test",
        traceback_lines=["line1"],
        slug="gh:owner_repo_1",
        worktree_path="/nonexistent",
        worktree_exists=False,
    )
    body = format_error_comment(ctx)

    assert "/nonexistent" in body
    assert "not found" in body


def test_format_error_comment_empty_system_info_omits_section():
    """format_error_comment should omit system section when no info available."""
    ctx = DispatchErrorContext(
        exception_type="RuntimeError",
        exception_message="test",
        traceback_lines=[],
        slug="gh:owner_repo_1",
    )
    body = format_error_comment(ctx)

    assert "**System:**" not in body
    assert BOT_MARKER in body
    assert "/retry" in body
