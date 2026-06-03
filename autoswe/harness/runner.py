"""Thin dispatcher for the coding harness.

Builds a RunSpec from its kwargs, delegates to a CodingBackend, and handles
retry / timeout / env-override logic shared by all backends.

All dataclasses and constants are re-exported here for backward compatibility
— handlers and tests still import from ``autoswe.harness.runner``.
"""
import asyncio

from autoswe.core.config import LOGS_DIR
from autoswe.core.logging_utils import init_debug_logger, log

# Re-export everything so existing importers need zero changes.
from autoswe.harness.backends.base import (  # noqa: F401
    AGENT_TASK_TOOLS,
    PROGRESS_TOOLS,
    HandlerResult,
    Mode,
    RunResult,
    RunSpec,
)
from autoswe.harness.backends.claude_code import (  # noqa: F401
    ClaudeCodeBackend,
    ProgressState,
    _extract_plan_file_path,
    _format_tool_progress,
    _parse_task_id,
)

dbg = init_debug_logger(LOGS_DIR)


def _get_retryable_exceptions() -> tuple:
    """Lazily build the tuple of SDK exception types to retry on."""

    from autoswe.harness.backends.claude_code import _get_retryable_exceptions as _backend_get

    return _backend_get()


def backend_has_capability(harness_cfg: dict, capability: str) -> bool:
    """Check if the backend for *harness_cfg* supports *capability*.

    Resolves the backend via the factory and checks its capabilities set.
    Defaults to ClaudeCodeBackend when *harness_cfg* is None.

    Use this before relying on capability-specific RunResult fields
    (e.g. check ``"mcp"`` before trusting ``plan_posted`` / ``question_posted``).
    """
    if harness_cfg is not None:
        from autoswe.harness.backends.factory import get_backend

        backend = get_backend(harness_cfg)
    else:
        backend = ClaudeCodeBackend()
    return capability in backend.capabilities()


# ---------- Backward-compatible shim ----------

# Tests and some internal code import `_run_async` directly. Provide a
# module-level async function with the same signature as the old one so
# existing callers (test_claude_runner.py, test_runner_can_use_tool.py)
# continue to work without changes.


async def _run_async(
    prompt: str,
    *,
    cwd: str,
    resume: str | None = None,
    mode: str | None = None,
    extra_tools: list | None = None,
    disallowed_tools_override: list | None = None,
    permission_mode: str = "default",
    allowed_tools: list | None = None,
    disallowed_tools: list | None = None,
    model: str | None = None,
    max_turns: int = 200,
    cli_path: str | None = None,
    env_overrides: dict | None = None,
    mcp_servers: dict | None = None,
    progress_callback=None,
    can_use_tool=None,
    state: dict | None = None,
):
    """Backward-compatible wrapper around ClaudeCodeBackend._run_async().

    Accepts the same keyword arguments as the original free function so
    existing test code imports and calls continue to work.
    """
    spec = RunSpec(
        prompt=prompt,
        cwd=cwd,
        model=model,
        resume=resume,
        mode=mode,
        extra_tools=extra_tools,
        disallowed_tools_override=disallowed_tools_override,
        permission_mode=permission_mode,
        allowed_tools=allowed_tools,
        disallowed_tools=disallowed_tools,
        max_turns=max_turns,
        cli_path=cli_path,
        env_overrides=env_overrides,
        mcp_servers=mcp_servers,
        progress_callback=progress_callback,
        can_use_tool=can_use_tool,
        state=state,
    )
    backend = ClaudeCodeBackend()
    return await backend._run_async(spec)



def run(
    prompt: str,
    *,
    cwd: str,
    cfg: dict,
    repo_cfg: dict | None = None,
    resume: str | None = None,
    # Phase 3: generic intent (preferred)
    mode: str | None = None,
    extra_tools: list | None = None,
    disallowed_tools_override: list | None = None,
    # Legacy fields (backward compat, ignored when mode is set)
    permission_mode: str = "default",
    allowed_tools: list | None = None,
    disallowed_tools: list | None = None,
    max_turns: int = 200,
    model: str | None = None,
    cli_path: str | None = None,
    env_overrides: dict | None = None,
    mcp_servers: dict | None = None,
    progress_callback=None,
    can_use_tool=None,
    state: dict | None = None,
    harness_cfg: dict | None = None,
):
    """Synchronous wrapper. Returns a RunResult dataclass.

    The dataclass supports backward-compatible tuple unpacking:
        text, session_id, subtype = runner.run(...)

    When *harness_cfg* is provided the backend is resolved via the factory
    (``get_backend()``).  When omitted the default is ``ClaudeCodeBackend``,
    preserving backward compatibility for callers that don't use harness
    profiles yet.

    **mode** (Phase 3, preferred): pass ``"plan"``, ``"read_only"``, or
    ``"read_write"`` instead of the legacy *permission_mode* /
    *allowed_tools* / *disallowed_tools* triple.
    """
    rc = repo_cfg or {}
    timeout = int(rc.get("agent_timeout", cfg.get("AGENT_TIMEOUT", 7200)))
    max_retries = int(rc.get("agent_retry_on_failure", cfg.get("AGENT_RETRY_ON_FAILURE", 0)))

    # Thread harness_cfg into spec.state so the backend can read
    # backend-specific fields (cli_path, anthropic_api_key, etc.).
    effective_state = state
    if harness_cfg is not None:
        effective_state = dict(state) if state else {}
        effective_state["_harness_cfg"] = harness_cfg

    spec = RunSpec(
        prompt=prompt,
        cwd=cwd,
        model=model,
        resume=resume,
        mode=mode,
        extra_tools=extra_tools,
        disallowed_tools_override=disallowed_tools_override,
        permission_mode=permission_mode,
        allowed_tools=allowed_tools,
        disallowed_tools=disallowed_tools,
        max_turns=max_turns,
        timeout=timeout,
        cli_path=cli_path,
        env_overrides=env_overrides,
        mcp_servers=mcp_servers,
        progress_callback=progress_callback,
        can_use_tool=can_use_tool,
        state=effective_state,
    )

    if harness_cfg is not None:
        from autoswe.harness.backends.factory import get_backend

        backend = get_backend(harness_cfg)
    else:
        backend = ClaudeCodeBackend()

    async def _with_timeout():
        return await asyncio.wait_for(
            backend.run(spec),
            timeout=timeout,
        )

    retryable = _get_retryable_exceptions()
    for attempt in range(max_retries + 1):
        try:
            return asyncio.run(_with_timeout())
        except retryable as e:
            if attempt < max_retries:
                log(f"[RUNNER] Attempt {attempt + 1} failed ({type(e).__name__}: {e}), retrying ({attempt + 2}/{max_retries + 1})")
            else:
                if isinstance(e, asyncio.TimeoutError):
                    log(f"[RUNNER] Timeout after {timeout}s (attempt {attempt + 1}/{max_retries + 1})")
                else:
                    log(f"[RUNNER] Agent failed after {attempt + 1} attempt(s): {type(e).__name__}: {e}")
                raise
