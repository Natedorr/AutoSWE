"""Harness-agnostic backend interface.

RunSpec captures the intent of a coding phase (plan, fix, review) without
tying it to any specific agent.  CodingBackend is the Protocol every
backend must implement.  RunResult and HandlerResult are the shared output
contracts; they used to live in runner.py and are re-exported from there
for backward compatibility.

Phase 3 introduces *mode*: a generic intent string (``"plan"``, ``"read_only"``,
``"read_write"``) that replaces the Claude-specific triple of
``permission_mode`` + ``allowed_tools`` + ``disallowed_tools``.  Each backend
translates *mode* into its own configuration (e.g. Claude Code permission
modes vs. Codex sandbox flags).  Backends advertise what they support via
``capabilities()`` so handlers can degrade gracefully when a feature
(e.g. MCP comment posting) is unavailable.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

# ---------- Mode types ----------

# Mode strings shared by all backends. Each backend maps these to its own
# configuration (Claude Code permission modes, Codex sandbox flags, etc.).
Mode = Literal["plan", "read_only", "read_write"]

# ---------- Shared dataclasses ----------


@dataclass
class RunResult:
    """Result of a coding-backend query.

    Supports tuple-style unpacking for backward compatibility:
        text, session_id, subtype = result
    """
    text: str
    session_id: str | None
    subtype: str | None
    cost_usd: float | None = None
    duration_seconds: float = 0.0
    plan_file_path: str | None = None
    plan_posted: bool = False
    question_posted: bool = False
    # Plan markdown captured from an ExitPlanMode tool call. The model often
    # exits plan mode via the native ExitPlanMode tool (even though it is
    # disallowed, the tool-use block — and its plan content — still appears in
    # the stream). Capturing it here lets the planner post the plan as a comment
    # instead of leaking the bare "Tool: ExitPlanMode" progress line.
    plan_text: str | None = None

    def __iter__(self):
        """Allow tuple-style unpacking: text, session_id, subtype = result."""
        yield self.text
        yield self.session_id
        yield self.subtype


@dataclass
class HandlerResult:
    """Result of a dispatch handler (plan, fix, sync, abort, etc.).

    done_content: "DONE_SUMMARY\t...", "FAILED: ...", "PLAN_READY", etc.
    cost_usd: cost reported by the agent API (None for local overrides).
    duration_seconds: wall-clock time the agent spent running.
    session_id: the agent session ID for this handler run. All handlers
        (plan, fix, review, resolve) return the session_id from the SDK run.
        _to_dispatch passes it through to DispatchResult; emit() persists
        it to the queue via the queue_patch.
    plan_file_path: absolute path to the ~/.claude/plans/<...>.md file the
        planner wrote on PLAN_READY. Persisted to queue so the next /fix
        dispatch can start a fresh session seeded with it instead of
        resuming the plan session.
    review_file_path: absolute path to the ~/.claude/reviews/<slug>.md file
        the reviewer wrote on REVIEW_READY. Persisted to queue so the next
        /fix or /plan dispatch injects it as prompt context, then clears it.
    """
    done_content: str
    cost_usd: float | None = None
    duration_seconds: float = 0.0
    session_id: str | None = None
    plan_file_path: str | None = None
    review_file_path: str | None = None


# ---------- Tool sets (module-level constants) ----------

# Read-only-safe progress/orchestration tools (no repo mutation)
PROGRESS_TOOLS = [
    "TodoWrite",
    "TaskCreate", "TaskUpdate", "TaskGet", "TaskList", "TaskOutput", "TaskStop",
]

# Full agent toolset: includes sub-agent spawning. Only safe for fix/coder phases.
AGENT_TASK_TOOLS = [*PROGRESS_TOOLS, "Agent"]


# ---------- RunSpec ----------


@dataclass
class RunSpec:
    """Harness-agnostic intent captured from a handler call.

    All fields are optional except *prompt* and *cwd* so that backends can
    provide their own defaults (e.g. Codex sandbox mode from permission flags).

    **mode** (Phase 3, preferred): a generic intent string (``"plan"``,
    ``"read_only"``, ``"read_write"``) that the backend translates into its
    own configuration (permission modes, sandbox flags, tool sets).  When set
    it takes precedence over the legacy *permission_mode* / *allowed_tools* /
    *disallowed_tools* fields.

    **Legacy fields** (*permission_mode*, *allowed_tools*, *disallowed_tools*):
    kept for backward compatibility.  Ignored when *mode* is set.
    New code should use *mode* + *extra_tools* + *disallowed_tools_override*.
    """
    prompt: str
    cwd: str
    model: str | None = None
    resume: str | None = None

    # --- Phase 3: generic intent (preferred) ---
    mode: Mode | None = None  # "plan" | "read_only" | "read_write"
    extra_tools: list | None = None  # append to mode-derived tool list
    disallowed_tools_override: list | None = None  # remove from mode-derived tool list

    # --- Legacy fields (backward compat, ignored when mode is set) ---
    permission_mode: str = "default"
    allowed_tools: list | None = None
    disallowed_tools: list | None = None

    max_turns: int = 200
    timeout: int = 7200
    cli_path: str | None = None
    env_overrides: dict | None = None
    mcp_servers: dict | None = None
    can_use_tool: Callable | None = None  # async callable(name, input, ctx) -> PermissionResult
    progress_callback: Callable | None = None  # callable(str) for progress updates
    state: dict | None = None


# ---------- CodingBackend Protocol ----------


@runtime_checkable
class CodingBackend(Protocol):
    """Protocol every coding backend must implement.

    A backend translates a RunSpec (intent) into an execution and returns a
    RunResult.  The ``run()`` method returns an awaitable so the caller can
    wrap it in asyncio.wait_for (timeout) or retry logic.

    ``capabilities()`` is a classmethod returning the set of features this
    backend supports.  Standard capability strings:

    - ``"mode"``: backend supports RunSpec.mode and translates it to its
      own configuration (permission modes, sandbox flags, tool sets).
    - ``"mcp"``: backend supports MCP servers and can post plans/questions
      via MCP tools (``plan_posted`` / ``question_posted`` in RunResult).
    - ``"can_use_tool"``: backend supports a per-tool runtime callback
      (``can_use_tool`` in RunSpec) for fine-grained tool gating.
    - ``"plan_permission"``: backend supports a dedicated "plan" mode that
      uses plan-specific tool restrictions.
    - ``"resume"``: backend supports resuming a prior session.
    - ``"progress_stream"``: backend fires progress_callback with rendered
      todo/command updates during execution.
    - ``"plan_file"``: backend writes native plan files to ``~/.claude/plans/``;
      the ``_find_latest_plan_file`` filesystem-scan fallback in the planner is
      only meaningful for such backends.  Backends that lack this capability
      (e.g. Codex) never produce plan files there, so the scan is skipped to
      prevent cross-issue plan file pollution.
    """

    @classmethod
    def capabilities(cls) -> set[str]:
        """Return the set of supported capability strings."""
        ...

    @classmethod
    def retryable_subtypes(cls) -> set[str]:
        """Return the set of RunResult.subtype values that trigger a retry.

        Called by the runner when AGENT_RETRY_ON_FAILURE > 0.  Return an
        empty set (the default contract) to rely solely on exception-based
        retries.  Override in backends whose failures are return-value-driven
        rather than exception-driven (e.g. Codex exit-code failures).
        """
        ...

    def run(self, spec: RunSpec) -> Awaitable[RunResult]:
        """Execute the spec and return an awaitable yielding RunResult."""
        ...
