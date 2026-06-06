"""Test read_only enforcement during plan phase.

Verifies that the can_use_tool callback correctly blocks Write/Edit
operations during plan mode (#209) while allowing read operations,
TodoWrite, and the sub-agent task family (progress/orchestration tools).
"""

from __future__ import annotations

import asyncio

import pytest
from claude_agent_sdk import PermissionResultAllow, PermissionResultDeny

from autoswe.harness.ask_user_question import make_can_use_tool

# --========================================================================
# Fixtures
# --========================================================================

@pytest.fixture
def task():
    """Minimal task dict for the callback."""
    return {
        "owner": "test",
        "repo": "test-repo",
        "issue_number": 42,
        "id": "gh:test_test-repo_42",
        "_token": "test-token",
    }


@pytest.fixture
def repo_cfg():
    return {"provider": "github", "token": "test-token"}


@pytest.fixture
def callback(task, repo_cfg):
    """The read_only can_use_tool callback."""
    return make_can_use_tool(task, repo_cfg, {}, read_only=True)


@pytest.fixture
def context():
    """Dummy tool permission context."""
    return {}


# --========================================================================
# Direct tool blocking (Write, Edit) — TodoWrite is allowed (progress tracking)
# --========================================================================

@pytest.mark.parametrize("tool_name", ["Write", "Edit"])
def test_blocks_write_tools(tool_name, callback, context):
    """Write, Edit tools must be denied in read_only mode."""
    result = asyncio.run(
        callback(tool_name, {}, context)
    )
    assert isinstance(result, PermissionResultDeny)
    assert "planning" in result.message.lower()


def test_allows_todo_write(callback, context):
    """TodoWrite must be allowed in read_only mode (progress tracking, no repo mutation)."""
    result = asyncio.run(
        callback("TodoWrite", {}, context)
    )
    assert isinstance(result, PermissionResultAllow)


def test_allows_task_tools(callback, context):
    """PROGRESS_TOOLS must be allowed in read_only mode (orchestration, no repo mutation)."""
    from autoswe.harness.runner import PROGRESS_TOOLS
    for tool_name in PROGRESS_TOOLS:
        result = asyncio.run(
            callback(tool_name, {}, context)
        )
        assert isinstance(result, PermissionResultAllow), f"{tool_name} should be allowed"


def test_allows_read_tools(callback, context):
    """Read, Glob, Grep tools must pass through in read_only mode."""
    for tool_name in ["Read", "Glob", "Grep"]:
        result = asyncio.run(
            callback(tool_name, {}, context)
        )
        assert isinstance(result, PermissionResultAllow)


# --========================================================================
# Bash command blocking
# --========================================================================

def _run(callback, tool_name, input_data, context):
    """Helper to run async callback synchronously."""
    import asyncio

    return asyncio.run(callback(tool_name, input_data, context))


class TestBashFileMutationBlocking:
    """Bash commands that mutate files must be denied."""

    def test_blocks_sed_i(self, callback, context):
        result = _run(callback, "Bash", {"command": "sed -i 's/old/new/g' file.py"}, context)
        assert isinstance(result, PermissionResultDeny)

    def test_blocks_sed_i_bak(self, callback, context):
        result = _run(callback, "Bash", {"command": "sed -i.bak 's/old/new/g' file.py"}, context)
        assert isinstance(result, PermissionResultDeny)

    def test_blocks_shell_redirect(self, callback, context):
        result = _run(callback, "Bash", {"command": "echo 'data' > file.txt"}, context)
        assert isinstance(result, PermissionResultDeny)

    def test_blocks_shell_append(self, callback, context):
        result = _run(callback, "Bash", {"command": "echo 'data' >> file.txt"}, context)
        assert isinstance(result, PermissionResultDeny)

    def test_blocks_tee(self, callback, context):
        result = _run(callback, "Bash", {"command": "echo 'data' | tee file.txt"}, context)
        assert isinstance(result, PermissionResultDeny)

    def test_blocks_wget(self, callback, context):
        result = _run(callback, "Bash", {"command": "wget http://example.com/file.tar.gz"}, context)
        assert isinstance(result, PermissionResultDeny)

    def test_blocks_curl_o(self, callback, context):
        result = _run(callback, "Bash", {"command": "curl -o file.tar.gz http://example.com/file.tar.gz"}, context)
        assert isinstance(result, PermissionResultDeny)

    def test_blocks_python_write(self, callback, context):
        result = _run(callback, "Bash", {"command": "python3 -c \"open('file.txt','w').write('data')\""}, context)
        assert isinstance(result, PermissionResultDeny)

    def test_blocks_perl_i(self, callback, context):
        result = _run(callback, "Bash", {"command": "perl -i -pe 's/old/new/g' file.py"}, context)
        assert isinstance(result, PermissionResultDeny)


class TestBashReadOnlyAllowed:
    """Read-only Bash commands must pass through."""

    def test_allows_cat(self, callback, context):
        result = _run(callback, "Bash", {"command": "cat file.py"}, context)
        assert isinstance(result, PermissionResultAllow)

    def test_allows_grep(self, callback, context):
        result = _run(callback, "Bash", {"command": "grep -r 'pattern' ."}, context)
        assert isinstance(result, PermissionResultAllow)

    def test_allows_ls(self, callback, context):
        result = _run(callback, "Bash", {"command": "ls -la"}, context)
        assert isinstance(result, PermissionResultAllow)

    def test_allows_git_log(self, callback, context):
        result = _run(callback, "Bash", {"command": "git log --oneline -5"}, context)
        assert isinstance(result, PermissionResultAllow)

    def test_allows_git_status(self, callback, context):
        result = _run(callback, "Bash", {"command": "git status"}, context)
        assert isinstance(result, PermissionResultAllow)

    def test_allows_git_diff(self, callback, context):
        result = _run(callback, "Bash", {"command": "git diff HEAD~1"}, context)
        assert isinstance(result, PermissionResultAllow)

    def test_allows_redirect_to_devnull(self, callback, context):
        """Redirects to /dev/null should be allowed (they don't mutate files)."""
        result = _run(callback, "Bash", {"command": "cat file.py > /dev/null"}, context)
        assert isinstance(result, PermissionResultAllow)

    def test_blocks_echo_append(self, callback, context):
        """echo >> is blocked by the echo pattern (even to /dev/null).
        Known limitation: the echo pattern fires before the /dev/null exception."""
        result = _run(callback, "Bash", {"command": "echo 'test' >> /dev/null"}, context)
        # Currently blocked by the \becho\b.*>> pattern — this is a known limitation
        assert isinstance(result, PermissionResultDeny)


class TestBashGitWriteBlocking:
    """Git write operations must be denied."""

    def test_blocks_git_commit(self, callback, context):
        result = _run(callback, "Bash", {"command": "git commit -m 'fix'"}, context)
        assert isinstance(result, PermissionResultDeny)

    def test_blocks_git_push(self, callback, context):
        result = _run(callback, "Bash", {"command": "git push origin main"}, context)
        assert isinstance(result, PermissionResultDeny)

    def test_blocks_git_add(self, callback, context):
        result = _run(callback, "Bash", {"command": "git add ."}, context)
        assert isinstance(result, PermissionResultDeny)

    def test_blocks_git_merge(self, callback, context):
        result = _run(callback, "Bash", {"command": "git merge feature-branch"}, context)
        assert isinstance(result, PermissionResultDeny)

    def test_blocks_git_reset(self, callback, context):
        result = _run(callback, "Bash", {"command": "git reset HEAD~1"}, context)
        assert isinstance(result, PermissionResultDeny)

    def test_blocks_git_c_flag_commit(self, callback, context):
        """git -c flag + commit should still detect the write subcommand."""
        result = _run(callback, "Bash", {"command": "git -c core.autocrlf=input commit -am 'fix'"}, context)
        assert isinstance(result, PermissionResultDeny)


class TestAskUserQuestionPassthrough:
    """AskUserQuestion should be denied (to pause) even in read_only mode."""

    def test_denies_ask_user_question(self, callback, context, task):
        input_data = {
            "questions": [{
                "question": "What is the file path?",
                "options": [{"label": "src/main.py", "description": ""}],
            }]
        }
        result = _run(callback, "AskUserQuestion", input_data, context)
        assert isinstance(result, PermissionResultDeny)
        assert "paused" in result.message.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
