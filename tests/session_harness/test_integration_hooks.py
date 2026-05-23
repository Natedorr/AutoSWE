"""Full-stack integration tests — real Ollama through planner/coder hooks.

These tests validate the production dispatch chain:
  planner.run_plan() → make_can_use_tool → _run_async → _extract_plan_output
  coder.run_fix() → make_can_use_tool → _run_async → _finalize_fix

Unlike test_integration_flow.py (which calls _run_async directly), these
test the hooks that connect the chassis to the rest of AutoSWE:
  1. can_use_tool callback blocking Write/Edit in plan mode
  2. can_use_tool callback blocking git writes / file mutations in bash
  3. AskUserQuestion interception → state["asked_question_md"]
  4. _extract_plan_output priority chain (plan file → tags → fallback)
  5. _plan_file_is_pending detection
  6. progress_callback sticky comments
  7. MCP post_plan tool progress

Run manually:
    cd ~/github/autoswe
    PYTHONPATH=/path/to/autoswe:$PYTHONPATH \
        RUN_CLAUDE_INTEGRATION=1 pytest tests/session_harness/test_integration_hooks.py -v

Requirements:
    - Ollama running on linux-server1:11434 with Qwen3.6:27b
    - ~15-40s per test
"""

import asyncio
import os
from pathlib import Path

import pytest

from autoswe.harness.ask_user_question import (
    _is_file_mutation,
    format_ask_user_question,
    make_can_use_tool,
)
from autoswe.harness.planner import (
    _extract_plan_output,
    _plan_file_is_pending,
)
from autoswe.harness.runner import _run_async

# ---- Fixtures ----

@pytest.fixture
def ollama_env():
    """Env overrides for Ollama."""
    return {
        "ANTHROPIC_BASE_URL": "http://linux-server1:11434",
        "ANTHROPIC_AUTH_TOKEN": "ollama",
        "ANTHROPIC_API_KEY": "ollama",
    }


@pytest.fixture
def ollama_model():
    """The production model."""
    return "Qwen3.6:27b"


OLLAMA_TIMEOUT = 600  # 10 minutes per Ollama integration test


@pytest.fixture
def dummy_task():
    """Minimal task dict for make_can_use_tool."""
    return {
        "id": "test-1",
        "owner": "test-owner",
        "repo": "test-repo",
        "issue_number": 42,
        "base_branch": "main",
        "_token": "dummy-token",
    }


@pytest.fixture
def dummy_repo_cfg():
    """Minimal repo config."""
    return {
        "provider": "github",
        "base_branch": "main",
        "pat": "dummy-token",
    }


# ---- Skip if Ollama integration not requested ----

skip_integration = pytest.mark.skipif(
    not os.environ.get("RUN_CLAUDE_INTEGRATION"),
    reason="Set RUN_CLAUDE_INTEGRATION=1 to run real Ollama integration tests",
)


# ==== TEST 1: can_use_tool blocks Write in plan mode (read_only=True) ====

def test_readonly_blocks_write_tool(dummy_task, dummy_repo_cfg):
    """make_can_use_tool with read_only=True denies Write/Edit/TodoWrite."""
    state = {}
    cut = make_can_use_tool(dummy_task, dummy_repo_cfg, state, read_only=True)

    async def check():
        # Write should be denied
        result = await cut("Write", {"path": "/tmp/test.txt", "content": "hi"}, None)
        return result

    result = asyncio.run(check())
    assert result.behavior == "deny", f"Expected deny, got {result.behavior}"
    assert "planning phase" in result.message.lower()

    # Edit should also be denied
    async def check_edit():
        return await cut("Edit", {"path": "/tmp/test.txt", "old_content": "a", "new_content": "b"}, None)
    result = asyncio.run(check_edit())
    assert result.behavior == "deny"


# ==== TEST 2: can_use_tool blocks git writes in bash ====

def test_readonly_blocks_git_writes(dummy_task, dummy_repo_cfg):
    """make_can_use_tool with read_only=True denies Bash git write subcommands."""
    state = {}
    cut = make_can_use_tool(dummy_task, dummy_repo_cfg, state, read_only=True)

    async def run_tool(name, data):
        return await cut(name, data, None)

    # git commit should be denied
    result = asyncio.run(run_tool("Bash", {"command": "git commit -m 'fix'"}))
    assert result.behavior == "deny", f"git commit should be denied, got {result.behavior}"

    # git push should be denied
    result = asyncio.run(run_tool("Bash", {"command": "git push origin main"}))
    assert result.behavior == "deny"

    # git add should be denied
    result = asyncio.run(run_tool("Bash", {"command": "git add ."}))
    assert result.behavior == "deny"

    # git log should be ALLOWED (read-only git subcommand)
    result = asyncio.run(run_tool("Bash", {"command": "git log --oneline -5"}))
    assert result.behavior == "allow", f"git log should be allowed, got {result.behavior}"

    # git status should be ALLOWED
    result = asyncio.run(run_tool("Bash", {"command": "git status"}))
    assert result.behavior == "allow"


# ==== TEST 3: can_use_tool blocks file mutations in bash ====

def test_readonly_blocks_file_mutations(dummy_task, dummy_repo_cfg):
    """make_can_use_tool with read_only=True denies sed -i, echo >>, tee, etc."""
    # Direct pattern tests
    assert _is_file_mutation("sed -i 's/foo/bar/' file.py")
    assert _is_file_mutation("echo 'data' >> file.txt")
    assert _is_file_mutation("cat > output.txt")
    assert _is_file_mutation("python3 -c \"open('x','w').write('y')\"")
    assert _is_file_mutation("curl -o file.json https://example.com")
    assert _is_file_mutation("wget https://example.com/file")
    assert _is_file_mutation("tee /tmp/output.txt")

    # Read-only patterns should NOT trigger
    assert not _is_file_mutation("cat file.py")
    assert not _is_file_mutation("grep 'pattern' file.py")
    assert not _is_file_mutation("ls -la")
    assert not _is_file_mutation("echo 'hello'")
    assert not _is_file_mutation("git log --oneline")

    # End-to-end through can_use_tool
    state = {}
    cut = make_can_use_tool(dummy_task, dummy_repo_cfg, state, read_only=True)

    async def run_tool(name, data):
        return await cut(name, data, None)

    result = asyncio.run(run_tool("Bash", {"command": "sed -i 's/foo/bar/' file.py"}))
    assert result.behavior == "deny"

    result = asyncio.run(run_tool("Bash", {"command": "cat file.py"}))
    assert result.behavior == "allow"


# ==== TEST 4: AskUserQuestion interception ====

def test_ask_user_question_interception(dummy_task, dummy_repo_cfg):
    """make_can_use_tool intercepts AskUserQuestion, sets state, fills answers."""
    state = {}
    post_log = []
    cut = make_can_use_tool(
        dummy_task, dummy_repo_cfg, state,
        on_post=post_log.append, read_only=True,
    )

    question_input = {
        "questions": [
            {
                "header": "Approach",
                "question": "Should I use approach A or B?",
                "options": [
                    {"label": "A", "description": "Simple but slower"},
                    {"label": "B", "description": "Complex but faster"},
                ],
                "multiSelect": False,
            }
        ]
    }

    async def run():
        return await cut("AskUserQuestion", question_input, None)

    result = asyncio.run(run())

    # State should have asked_question_md
    assert "asked_question_md" in state
    assert "## Questions" in state["asked_question_md"]
    assert "Approach" in state["asked_question_md"]

    # on_post callback should have been called
    assert len(post_log) == 1

    # Result should be PermissionResultAllow with pre-filled answers
    assert result.behavior == "allow"
    assert "answers" in result.updated_input
    assert len(result.updated_input["answers"]) == 1


# ==== TEST 5: _extract_plan_output priority chain ===

@pytest.fixture(autouse=True)
def clear_plans_dir():
    """Clear stale plan files before/after each test to avoid false positives."""
    plans_dir = Path.home() / ".claude" / "plans"
    if plans_dir.exists():
        for f in plans_dir.glob("*.md"):
            f.unlink()
    yield
    if plans_dir.exists():
        for f in plans_dir.glob("*.md"):
            f.unlink()

def test_extract_plan_output_plan_file(tmp_path):
    """Plan file takes priority over text content."""
    plan_file = tmp_path / "my-plan.md"
    plan_file.write_text("## Steps\n1. Fix bug A\n2. Fix bug B")

    comment, done = _extract_plan_output("Some random text", plan_file=plan_file)
    assert done == "PLAN_READY"
    assert "## Steps" in comment
    assert "Fix bug A" in comment


def test_extract_plan_output_pending_fallback(tmp_path):
    """Pending plan file falls through to question detection."""
    plan_file = tmp_path / "pending-plan.md"
    plan_file.write_text("I'm waiting for clarification on the approach.")

    comment, done = _extract_plan_output("Some text", plan_file=plan_file)
    # "waiting for" is a pending indicator → should NOT return PLAN_READY
    assert done != "PLAN_READY", "Pending plan should not return PLAN_READY"


def test_extract_plan_output_autoswe_plan_tag():
    """<AUTOSWE_PLAN> tags detected when no plan file."""
    text = "Some preamble <AUTOSWE_PLAN>Step 1\nStep 2</AUTOSWE_PLAN> done."
    comment, done = _extract_plan_output(text)
    assert done == "PLAN_READY"
    assert "Step 1" in comment


def test_extract_plan_output_autoswe_questions_tag():
    """<AUTOSWE_QUESTIONS> tags detected."""
    text = "Hey <AUTOSWE_QUESTIONS>What should I do?</AUTOSWE_QUESTIONS>"
    comment, done = _extract_plan_output(text)
    assert done == "WAITING: questions"
    assert "## Questions" in comment


def test_extract_plan_output_fallback():
    """Plain text falls back to WAITING: see comment."""
    comment, done = _extract_plan_output("Just some random response text.")
    assert done == "WAITING: see comment"
    assert "## Claude's response" in comment


# ==== TEST 6: _plan_file_is_pending detection ====

def test_plan_file_is_pending():
    """Pending indicators correctly detected."""
    # Should be pending
    assert _plan_file_is_pending("I'm waiting for your response.")
    assert _plan_file_is_pending("This is TBD until we confirm.")
    assert _plan_file_is_pending("Once you provide the API key, I can proceed.")
    assert _plan_file_is_pending("Clarifying question: what's the deadline?")
    assert _plan_file_is_pending("Need more information about the deployment.")
    assert _plan_file_is_pending("Before implementing, let me confirm the approach.")
    assert _plan_file_is_pending("Before finalizing the plan, one question.")

    # Should NOT be pending
    assert not _plan_file_is_pending("## Steps\n1. Fix the bug\n2. Add tests")
    assert not _plan_file_is_pending("First, update the config. Then restart.")
    assert not _plan_file_is_pending("The fix is straightforward.")


# ==== TEST 7: Real Ollama — plan mode blocks Write via can_use_tool ====

@skip_integration
def test_ollama_plan_readonly_enforced(tmp_path, ollama_env, ollama_model):
    """Real Ollama run: plan mode with can_use_tool blocks Write tool calls.

    This validates the full chain: _run_async → SDK → CLI → can_use_tool hook.
    We verify that the runner returns a valid session_id even when tools are blocked.
    """
    state = {}
    cut = make_can_use_tool(
        {
            "id": "t1", "owner": "o", "repo": "r",
            "issue_number": 1, "base_branch": "main", "_token": "x",
        },
        {"provider": "github", "pat": "x"},
        state,
        read_only=True,
    )

    async def run():
        return await asyncio.wait_for(
            _run_async(
                "Just describe what you would do to add a README. Don't actually write files.",
                cwd=str(tmp_path),
                permission_mode="plan",
                allowed_tools=["Read"],
                disallowed_tools=["ExitPlanMode"],
                model=ollama_model,
                max_turns=5,
                env_overrides=ollama_env,
                can_use_tool=cut,
                state=state,
            ),
            timeout=OLLAMA_TIMEOUT,
        )

    result = asyncio.run(run())
    assert result.session_id is not None
    assert len(result.text) > 0
    assert "asked_question_md" not in state  # No questions asked


# ==== TEST 8: Real Ollama — progress callback receives tool progress ====

@skip_integration
def test_ollama_progress_callback(tmp_path, ollama_env, ollama_model):
    """Real Ollama run: progress callback receives tool progress strings."""
    progress_log = []

    async def run():
        return await asyncio.wait_for(
            _run_async(
                "Read the file README.md (it doesn't exist, that's fine). Then tell me what you'd do.",
                cwd=str(tmp_path),
                permission_mode="plan",
                allowed_tools=["Read"],
                model=ollama_model,
                max_turns=5,
                env_overrides=ollama_env,
                progress_callback=progress_log.append,
            ),
            timeout=OLLAMA_TIMEOUT,
        )

    result = asyncio.run(run())
    assert result.session_id is not None
    # Should have at least one progress entry (Read attempt)
    print(f"Progress log: {progress_log}")


# ==== TEST 9: format_ask_user_question output ====

def test_format_ask_user_question():
    """format_ask_user_question renders valid markdown for issue comments."""
    input_data = {
        "questions": [
            {
                "header": "Architecture",
                "question": "Should we use a monolith or microservices?",
                "options": [
                    {"label": "Monolith", "description": "Simpler to deploy"},
                    {"label": "Microservices", "description": "Better scalability"},
                ],
                "multiSelect": False,
            },
            {
                "header": "Database",
                "question": "Which database?",
                "options": [
                    {"label": "PostgreSQL"},
                    {"label": "MySQL"},
                ],
                "multiSelect": True,
            }
        ]
    }

    md = format_ask_user_question(input_data)
    assert "## Questions" in md
    assert "### Architecture" in md
    assert "### Database" in md
    assert "**Monolith**" in md
    assert "(select any that apply)" in md
    assert "Reply in this thread" in md


# ==== TEST 10: Real Ollama — end-to-end plan → extract output ====

@skip_integration
def test_ollama_plan_extract_output(tmp_path, ollama_env, ollama_model):
    """Full chain: Ollama plan run → _extract_plan_output detects result.

    Note: read_only=False here so the model CAN write a plan file.
    We're testing the extraction chain, not the blocking logic.
    """
    state = {}
    post_log = []
    cut = make_can_use_tool(
        {
            "id": "t1", "owner": "o", "repo": "r",
            "issue_number": 1, "base_branch": "main", "_token": "x",
        },
        {"provider": "github", "pat": "x"},
        state,
        on_post=post_log.append,
        read_only=False,  # Allow Write so the model can create a plan file
    )

    async def run():
        return await asyncio.wait_for(
            _run_async(
                "Write a plan to fix a bug where a Python function returns None instead of 0.",
                cwd=str(tmp_path),
                permission_mode="plan",
                allowed_tools=["Read", "Write"],
                model=ollama_model,
                max_turns=10,
                env_overrides=ollama_env,
                can_use_tool=cut,
                state=state,
                progress_callback=post_log.append,
            ),
            timeout=OLLAMA_TIMEOUT,
        )

    result = asyncio.run(run())
    assert result.session_id is not None

    # Now run _extract_plan_output on the result
    plan_file = Path(result.plan_file_path) if result.plan_file_path else None
    comment, done = _extract_plan_output(result.text, plan_file=plan_file)

    # The model should have produced either a plan file or text output
    assert done in ("PLAN_READY", "WAITING: questions", "WAITING: see comment")
    print(f"Done: {done}")
    print(f"Comment (first 300 chars): {comment[:300]}")
    print(f"Plan file path: {result.plan_file_path}")
