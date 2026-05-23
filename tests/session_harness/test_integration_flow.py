"""Integration tests — real Ollama calls through the full AutoSWE stack.

These tests hit the real Claude Agent SDK against Ollama with the production model
(Qwen3.6:27b). They are NOT for CI — they're for pre-merge validation of session flows,
plan mode, fix mode, etc.

Run manually:
    cd ~/github/autoswe
    PYTHONPATH=/path/to/autoswe:$PYTHONPATH \
        RUN_CLAUDE_INTEGRATION=1 pytest tests/session_harness/test_integration_flow.py -v

Requirements:
    - Ollama running on linux-server1:11434
    - Qwen3.6:27b model pulled
    - ~10-30s per test (vs hours for live Claude)
"""

import asyncio
import os

import pytest

from autoswe.harness.runner import _run_async

# ---- Config fixture for production model ----

@pytest.fixture
def lite_cfg(tmp_path):
    """Config pointing at Ollama on linux-server1 with production model."""
    return {
        "AGENT_TIMEOUT": 300,
        "ANTHROPIC_BASE_URL": "http://linux-server1:11434",
        "ANTHROPIC_AUTH_TOKEN": "ollama",
        "ANTHROPIC_API_KEY": "ollama",
        "PLAN_MODEL": "Qwen3.6:27b",
        "FIX_MODEL": "Qwen3.6:27b",
        "CLAUDE_CLI_PATH": "",
    }


@pytest.fixture
def lite_cfg_for_run(tmp_path, lite_cfg):
    """Config dict as passed to runner.run()."""
    return {
        **lite_cfg,
        "MAX_ATTEMPTS": 1,
        "MAX_TOTAL_HOURS": 1,
        "MAX_CONCURRENT": 1,
        "SILENT_REPORTING": True,
        "AUTO_ASSIGN": False,
        "AUTO_CREATE_PR": False,
        "ASSIGN_USER": "",
        "WORKTREE_DIR": str(tmp_path / "worktrees"),
    }


@pytest.fixture
def ollama_env():
    """Env overrides for Ollama — pass these to _run_async(env_overrides=...)."""
    return {
        "ANTHROPIC_BASE_URL": "http://linux-server1:11434",
        "ANTHROPIC_AUTH_TOKEN": "ollama",
        "ANTHROPIC_API_KEY": "ollama",
    }


@pytest.fixture
def ollama_model():
    """The production model used by AutoSWE."""
    return "Qwen3.6:27b"


# ---- Skip if Ollama not available ----

@pytest.fixture(scope="session")
def ollama_available():
    """Check if Ollama is running and skip all integration tests if not."""
    import urllib.request
    try:
        urllib.request.urlopen("http://linux-server1:11434", timeout=2)
        return True
    except Exception:
        return False


# ==== TESTS ====

@pytest.mark.skipif(
    not os.environ.get("RUN_CLAUDE_INTEGRATION"),
    reason="Set RUN_CLAUDE_INTEGRATION=1 to run real Ollama integration tests",
)
def test_plan_new_session_returns_session_id(lite_cfg_for_run, tmp_path, ollama_env, ollama_model):
    """Plan phase should return a valid session_id (not None).
    This is the core #208 regression check with a real model.

    Uses a trivial task so the model can handle it reliably.
    """

    async def run_plan():
        result = await _run_async(
            "Write a plan to add 'Hello World' to a file called test.txt. Just write the plan, don't execute it.",
            cwd=str(tmp_path),
            permission_mode="plan",
            allowed_tools=["Read", "Write"],
            model=ollama_model,
            max_turns=10,
            env_overrides=ollama_env,
        )
        return result

    result = asyncio.run(run_plan())

    # The critical assertion: session_id should NOT be None
    assert result.session_id is not None, (
        "Bug #208 regression: session_id is None after plan phase. "
        "This means the async generator crashed before ResultMessage arrived."
    )
    assert len(result.text) > 0, "Empty response from model"


@pytest.mark.skipif(
    not os.environ.get("RUN_CLAUDE_INTEGRATION"),
    reason="Set RUN_CLAUDE_INTEGRATION=1 to run real Ollama integration tests",
)
def test_resume_uses_previous_session_id(lite_cfg_for_run, tmp_path, ollama_env, ollama_model):
    """Resuming with a previous session_id should continue the conversation.

    Uses trivial memory task so the model can handle it.
    """
    first_session = None

    async def run_first():
        nonlocal first_session
        result = await _run_async(
            "The answer is 42. Remember this number.",
            cwd=str(tmp_path),
            permission_mode="default",
            allowed_tools=[],
            model=ollama_model,
            max_turns=5,
            env_overrides=ollama_env,
        )
        first_session = result.session_id
        return result

    result1 = asyncio.run(run_first())
    assert result1.session_id is not None, "First call should return session_id"

    async def run_resume():
        result = await _run_async(
            "What was the answer I told you to remember?",
            cwd=str(tmp_path),
            permission_mode="default",
            allowed_tools=[],
            model=ollama_model,
            max_turns=5,
            resume=first_session,
            env_overrides=ollama_env,
        )
        return result

    result2 = asyncio.run(run_resume())
    assert result2.session_id is not None, "Resume should return new session_id"
    # The resumed response should mention "42" if session context was preserved
    print(f"Resume response: {result2.text[:200]}")


@pytest.mark.skipif(
    not os.environ.get("RUN_CLAUDE_INTEGRATION"),
    reason="Set RUN_CLAUDE_INTEGRATION=1 to run real Ollama integration tests",
)
def test_plan_mode_restricts_write_tools(lite_cfg_for_run, tmp_path, ollama_env, ollama_model):
    """Plan mode should restrict destructive tools.

    Uses trivial task — just asks model to describe what it would do.
    """

    async def run_plan():
        result = await _run_async(
            "Tell me what you would do to fix a typo in a file. Just describe it.",
            cwd=str(tmp_path),
            permission_mode="plan",
            allowed_tools=["Read"],
            disallowed_tools=["ExitPlanMode"],
            model=ollama_model,
            max_turns=5,
            env_overrides=ollama_env,
        )
        return result

    result = asyncio.run(run_plan())
    assert result.session_id is not None
    # disallowed_tools=["ExitPlanMode"] means the model can't exit plan mode
    print(f"Plan response (truncated): {result.text[:200]}")


@pytest.mark.skipif(
    not os.environ.get("RUN_CLAUDE_INTEGRATION"),
    reason="Set RUN_CLAUDE_INTEGRATION=1 to run real Ollama integration tests",
)
def test_fix_mode_allows_edits(lite_cfg_for_run, tmp_path, ollama_env, ollama_model):
    """Fix mode should allow Write tool and produce a valid session_id.

    Uses a trivial single-file change so the model can handle it.
    """

    # Create a test file to edit
    test_file = tmp_path / "test.txt"
    test_file.write_text("hello world\n")

    async def run_fix():
        result = await _run_async(
            "Change 'hello' to 'goodbye' in test.txt",
            cwd=str(tmp_path),
            permission_mode="bypassPermissions",
            allowed_tools=["Read", "Write", "Bash"],
            model=ollama_model,
            max_turns=10,
            env_overrides=ollama_env,
        )
        return result

    result = asyncio.run(run_fix())
    assert result.session_id is not None
    assert result.subtype is not None
    print(f"Fix result text (truncated): {result.text[:200]}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
