"""Harness backend abstraction layer.

Re-exports the core types so callers can import from a stable path:
    from autoswe.harness.backends import RunSpec, RunResult, CodingBackend, Mode
"""
# Claude Code's tool-set constants live in claude_code.py (they are Claude-
# specific names, not part of the harness-agnostic base — S6 / issue #169
# F-10). Re-exported here for back-compat with importers that reach for them
# via the package.
from autoswe.harness.backends.base import (
    CodingBackend,
    HandlerResult,
    Mode,
    RunResult,
    RunSpec,
)
from autoswe.harness.backends.claude_code import AGENT_TASK_TOOLS, PROGRESS_TOOLS

__all__ = [
    "AGENT_TASK_TOOLS",
    "PROGRESS_TOOLS",
    "CodingBackend",
    "HandlerResult",
    "Mode",
    "RunResult",
    "RunSpec",
]
