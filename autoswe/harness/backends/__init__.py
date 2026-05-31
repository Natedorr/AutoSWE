"""Harness backend abstraction layer.

Re-exports the core types so callers can import from a stable path:
    from autoswe.harness.backends import RunSpec, RunResult, CodingBackend
"""
from autoswe.harness.backends.base import (
    AGENT_TASK_TOOLS,
    PROGRESS_TOOLS,
    CodingBackend,
    HandlerResult,
    RunResult,
    RunSpec,
)

__all__ = [
    "AGENT_TASK_TOOLS",
    "PROGRESS_TOOLS",
    "CodingBackend",
    "HandlerResult",
    "RunResult",
    "RunSpec",
]
