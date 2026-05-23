"""Diagnostic helpers for dispatch errors.

Captures system state, git state, and exception details when a dispatch
fails unexpectedly. Produces structured data and human-readable markdown
for posting as an error comment on the issue.
"""
from __future__ import annotations

import os
import platform
import subprocess
import sys
import traceback
from dataclasses import dataclass, field

from autoswe.tracking.comments import BOT_MARKER


@dataclass
class DispatchErrorContext:
    """Structured context captured when a dispatch fails."""

    exception_type: str = ""
    exception_message: str = ""
    traceback_lines: list[str] = field(default_factory=list)
    slug: str = ""
    worktree_path: str = ""
    worktree_exists: bool = False
    git_branch: str = ""
    git_status: str = ""
    git_log: str = ""
    system_memory: str = ""
    disk_usage: str = ""
    kernel_version: str = ""
    python_version: str = ""


def capture_dispatch_error(
    exc: Exception,
    slug: str,
    worktree: str | None,
) -> DispatchErrorContext:
    """Capture diagnostics after a dispatch failure.

    All subprocess calls are timeout-guarded (5s) and OSError-caught.
    Diagnostics failure does not prevent the error transition.
    """
    tb = traceback.format_exception(type(exc), exc, exc.__traceback__)

    ctx = DispatchErrorContext(
        exception_type=type(exc).__name__,
        exception_message=str(exc),
        traceback_lines=tb,
        slug=slug,
        worktree_path=worktree or "",
        worktree_exists=os.path.isdir(worktree) if worktree else False,
        python_version=sys.version.split()[0] if hasattr(sys, "version") else "",
        kernel_version=platform.release(),
    )

    # System memory
    ctx.system_memory = _get_memory_info()

    # Disk usage
    if worktree:
        parent = os.path.dirname(worktree) or "/"
        ctx.disk_usage = _get_disk_usage(parent)

    # Git diagnostics (if worktree exists and is a git repo)
    if ctx.worktree_exists:
        ctx.git_branch = _run_safe(worktree, ["git", "branch", "--show-current"])
        ctx.git_status = _run_safe(worktree, ["git", "status", "--short", "--branch"])
        ctx.git_log = _run_safe(worktree, ["git", "log", "--oneline", "-5"])

    return ctx


def format_error_comment(ctx: DispatchErrorContext) -> str:
    """Build a human-readable markdown error comment.

    Pure function — no I/O.
    """
    lines: list[str] = [
        "## Dispatch Error",
        "",
        "An infrastructure error occurred while processing this task.",
        "",
        f"**Exception:** `{ctx.exception_type}: {ctx.exception_message}`",
        "",
    ]

    # System info
    sys_parts = []
    if ctx.python_version:
        sys_parts.append(f"Python {ctx.python_version}")
    if ctx.kernel_version:
        sys_parts.append(f"Kernel {ctx.kernel_version}")
    if ctx.system_memory:
        sys_parts.append(ctx.system_memory)
    if ctx.disk_usage:
        sys_parts.append(ctx.disk_usage)

    if sys_parts:
        lines.append("**System:**")
        lines.append("")
        for part in sys_parts:
            lines.append(f"- {part}")
        lines.append("")

    # Git info
    if ctx.worktree_exists:
        lines.append("**Git:**")
        lines.append("")
        if ctx.git_branch:
            lines.append(f"- Branch: `{ctx.git_branch}`")
        if ctx.git_log:
            lines.append("- Recent commits:")
            lines.append("")
            lines.append("```")
            lines.append(ctx.git_log)
            lines.append("```")
            lines.append("")
        if ctx.git_status:
            lines.append("- Working tree status:")
            lines.append("")
            lines.append("```")
            lines.append(ctx.git_status)
            lines.append("```")
            lines.append("")
    elif ctx.worktree_path:
        lines.append(f"**Worktree:** `{ctx.worktree_path}` (not found)")
        lines.append("")

    # Traceback (first 20 lines)
    if ctx.traceback_lines:
        truncated = ctx.traceback_lines[:20]
        lines.append("**Traceback:**")
        lines.append("")
        lines.append("```")
        lines.extend(truncated)
        if len(ctx.traceback_lines) > 20:
            lines.append(f"... ({len(ctx.traceback_lines) - 20} more lines)")
        lines.append("```")
        lines.append("")

    lines.append("Post `/retry` to attempt again.")
    lines.append(BOT_MARKER)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _run_safe(cwd: str, cmd: list[str], timeout: float = 5.0) -> str:
    """Run a command safely, returning output or empty string on any failure."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout,
        )
        combined = result.stdout.strip()
        if not combined and result.stderr.strip():
            combined = result.stderr.strip()
        return combined
    except (subprocess.TimeoutExpired, OSError, FileNotFoundError):
        return ""


def _get_memory_info() -> str:
    """Read system memory from /proc/meminfo (Linux) or fall back to empty."""
    try:
        with open("/proc/meminfo", "r") as f:
            meminfo = f.readline().strip()  # MemTotal line
        return meminfo
    except (OSError, IOError):
        return ""


def _get_disk_usage(path: str) -> str:
    """Get disk usage string for the filesystem containing *path*."""
    try:
        st = os.statvfs(path)
        total_gb = (st.f_blocks * st.f_frsize) / (1024 ** 3)
        free_gb = (st.f_bfree * st.f_frsize) / (1024 ** 3)
        return f"Disk: {free_gb:.1f}GB free / {total_gb:.1f}GB total"
    except (OSError, TypeError, AttributeError):
        return ""
