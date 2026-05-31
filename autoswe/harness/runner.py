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


# ---------- Backward-compatible shim ----------

# Tests and some internal code import `_run_async` directly. Provide a
# module-level async function with the same signature as the old one so
# existing callers (test_claude_runner.py, test_runner_can_use_tool.py)
# continue to work without changes.


async def _run_async(
    prompt: str,
    *,
    cwd: str,
    resume: str = None,
    permission_mode: str = "default",
    allowed_tools: list = None,
    disallowed_tools: list = None,
    model: str = None,
    max_turns: int = 200,
    cli_path: str = None,
    env_overrides: dict = None,
    mcp_servers: dict = None,
    progress_callback=None,
    can_use_tool=None,
    state: dict = None,
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
    repo_cfg: dict = None,
    resume: str = None,
    permission_mode: str = "default",
    allowed_tools: list = None,
    disallowed_tools: list = None,
    max_turns: int = 200,
    model: str = None,
    mcp_servers: dict = None,
    progress_callback=None,
    can_use_tool=None,
    state: dict = None,
):
    """Synchronous wrapper. Returns a RunResult dataclass.

    The dataclass supports backward-compatible tuple unpacking:
        text, session_id, subtype = runner.run(...)
    """
    rc = repo_cfg or {}
    timeout = int(rc.get("agent_timeout", cfg.get("AGENT_TIMEOUT", 7200)))
    max_retries = int(rc.get("agent_retry_on_failure", cfg.get("AGENT_RETRY_ON_FAILURE", 0)))
    model = model or rc.get("model") or None
    cli_path = cfg.get("CLAUDE_CLI_PATH") or None

    env_overrides = {}
    base_url = rc.get("anthropic_base_url") or cfg.get("ANTHROPIC_BASE_URL")
    auth_token = rc.get("anthropic_auth_token") or cfg.get("ANTHROPIC_AUTH_TOKEN")
    api_key = cfg.get("ANTHROPIC_API_KEY")
    if base_url:
        env_overrides["ANTHROPIC_BASE_URL"] = base_url
    if auth_token:
        env_overrides["ANTHROPIC_AUTH_TOKEN"] = auth_token
    if api_key:
        env_overrides["ANTHROPIC_API_KEY"] = api_key

    spec = RunSpec(
        prompt=prompt,
        cwd=cwd,
        model=model,
        resume=resume,
        permission_mode=permission_mode,
        allowed_tools=allowed_tools,
        disallowed_tools=disallowed_tools,
        max_turns=max_turns,
        timeout=timeout,
        cli_path=cli_path,
        env_overrides=env_overrides or None,
        mcp_servers=mcp_servers,
        progress_callback=progress_callback,
        can_use_tool=can_use_tool,
        state=state,
    )

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
                log(f"[CLAUDE] Attempt {attempt + 1} failed ({type(e).__name__}: {e}), retrying ({attempt + 2}/{max_retries + 1})")
            else:
                if isinstance(e, asyncio.TimeoutError):
                    log(f"[CLAUDE] Timeout after {timeout}s (attempt {attempt + 1}/{max_retries + 1})")
                else:
                    log(f"[CLAUDE] Agent failed after {attempt + 1} attempt(s): {type(e).__name__}: {e}")
                raise
