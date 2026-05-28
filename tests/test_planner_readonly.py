"""Tests for read_only mode in can_use_tool (Safeguard 1).

When the plan phase runs with read_only=True, the can_use_tool callback
blocks Write and Edit tools and Bash git commit/push commands.
TodoWrite and the sub-agent task family (TaskCreate, etc.) are allowed —
they are progress/orchestration tools that do not mutate the repo.
This prevents the agent from implementing code during planning, even if
the CLI exits plan mode via the native ExitPlanMode command.
"""

from unittest.mock import patch


def test_git_commit_push_re_matches_commit():
    from autoswe.harness.ask_user_question import _GIT_COMMIT_PUSH_RE
    assert _GIT_COMMIT_PUSH_RE.search('git commit -m "fix"')
    assert _GIT_COMMIT_PUSH_RE.search("git commit --amend")
    assert _GIT_COMMIT_PUSH_RE.search("git commit --no-edit")


def test_git_commit_push_re_matches_push():
    from autoswe.harness.ask_user_question import _GIT_COMMIT_PUSH_RE
    assert _GIT_COMMIT_PUSH_RE.search("git push")
    assert _GIT_COMMIT_PUSH_RE.search("git push origin main")
    assert _GIT_COMMIT_PUSH_RE.search("git push -f")
    assert _GIT_COMMIT_PUSH_RE.search("git push --force")


def test_git_commit_push_re_matches_force_push():
    from autoswe.harness.ask_user_question import _GIT_COMMIT_PUSH_RE
    assert _GIT_COMMIT_PUSH_RE.search("git force-push")
    assert _GIT_COMMIT_PUSH_RE.search("git force push")


def test_git_commit_push_re_no_false_positives():
    from autoswe.harness.ask_user_question import _GIT_COMMIT_PUSH_RE
    assert not _GIT_COMMIT_PUSH_RE.search("git status")
    assert not _GIT_COMMIT_PUSH_RE.search("git log")
    assert not _GIT_COMMIT_PUSH_RE.search("git add -A")
    assert not _GIT_COMMIT_PUSH_RE.search("git diff --cached")
    assert not _GIT_COMMIT_PUSH_RE.search("git rev-parse HEAD")
    assert not _GIT_COMMIT_PUSH_RE.search("git remote set-url origin")
    assert not _GIT_COMMIT_PUSH_RE.search("python test.py")


def test_is_git_commit_push_helper():
    from autoswe.harness.ask_user_question import _is_git_commit_push
    assert _is_git_commit_push('git commit -m "hello"')
    assert _is_git_commit_push("git push origin autoswe/issue-138")
    assert not _is_git_commit_push("git log --oneline")
    assert not _is_git_commit_push("ls -la")


def test_is_git_write_blocks_subcommands_behind_top_level_flags():
    """The agent was bypassing the old regex by inserting `-c key=val`
    between `git` and the subcommand (e.g.
    `git -c core.autocrlf=input commit -am ...`). The subcommand-based
    check must look past those flags."""
    from autoswe.harness.ask_user_question import _git_subcommand, _is_git_write

    assert _git_subcommand("git -c core.autocrlf=input commit -am foo") == "commit"
    assert _git_subcommand("git -C /tmp/wt push origin main") == "push"
    assert _git_subcommand("git --no-pager log") == "log"
    assert _git_subcommand("git -c user.email=x@y -c user.name=z commit") == "commit"

    assert _is_git_write("git -c core.autocrlf=input commit -am 'plan work'")
    assert _is_git_write("git -C /tmp/wt push -f origin autoswe/issue-1")
    assert _is_git_write("git -c foo=bar reset --hard HEAD~1")
    assert _is_git_write("git checkout -b new-branch")
    assert _is_git_write("git merge origin/main")
    assert _is_git_write("git add -A")


def test_is_git_write_allows_read_only_subcommands():
    from autoswe.harness.ask_user_question import _is_git_write
    assert not _is_git_write("git log --oneline")
    assert not _is_git_write("git status")
    assert not _is_git_write("git diff --cached")
    assert not _is_git_write("git -c foo=bar log -5")
    assert not _is_git_write("git -C /tmp show HEAD")
    assert not _is_git_write("git rev-parse --abbrev-ref HEAD")
    assert not _is_git_write("ls -la")
    assert not _is_git_write("python test.py")
    assert not _is_git_write("")


def test_read_only_blocks_bash_git_with_top_level_flag(monkeypatch):
    """Regression: the agent's `git -c core.autocrlf=input commit -am ...`
    workaround for Windows line endings must be denied during plan."""
    from autoswe.harness.ask_user_question import make_can_use_tool

    state = {}
    cut = make_can_use_tool({}, {}, state, read_only=True)

    import asyncio

    from claude_agent_sdk import PermissionResultDeny

    async def run():
        return await cut(
            "Bash",
            {"command": "git -c core.autocrlf=input commit -am 'plan work'"},
            None,
        )

    assert isinstance(asyncio.run(run()), PermissionResultDeny)


def test_read_only_blocks_other_git_mutations():
    """Beyond commit/push, plan phase should deny reset, checkout, merge, etc."""
    from autoswe.harness.ask_user_question import make_can_use_tool

    state = {}
    cut = make_can_use_tool({}, {}, state, read_only=True)

    import asyncio

    from claude_agent_sdk import PermissionResultDeny

    async def deny_check(cmd):
        return await cut("Bash", {"command": cmd}, None)

    for cmd in (
        "git reset --hard HEAD~1",
        "git checkout -b new-branch",
        "git merge origin/main",
        "git rebase main",
        "git add -A",
        "git stash",
    ):
        result = asyncio.run(deny_check(cmd))
        assert isinstance(result, PermissionResultDeny), f"{cmd!r} should be denied"


def test_read_only_blocks_write_tool():
    """read_only=True should deny Write tool calls."""
    from autoswe.harness.ask_user_question import make_can_use_tool

    state = {}
    cut = make_can_use_tool({}, {}, state, read_only=True)

    import asyncio

    async def run():
        result = await cut("Write", {"file_path": "/tmp/test.py"}, None)
        return result

    result = asyncio.run(run())
    from claude_agent_sdk import PermissionResultDeny
    assert isinstance(result, PermissionResultDeny)


def test_read_only_blocks_edit_tool():
    """read_only=True should deny Edit tool calls."""
    from autoswe.harness.ask_user_question import make_can_use_tool

    state = {}
    cut = make_can_use_tool({}, {}, state, read_only=True)

    import asyncio

    async def run():
        result = await cut("Edit", {"file_path": "/tmp/test.py"}, None)
        return result

    result = asyncio.run(run())
    from claude_agent_sdk import PermissionResultDeny
    assert isinstance(result, PermissionResultDeny)


def test_read_only_allows_todo_write():
    """read_only=True should allow TodoWrite (progress tracking, no repo mutation)."""
    from autoswe.harness.ask_user_question import make_can_use_tool

    state = {}
    cut = make_can_use_tool({}, {}, state, read_only=True)

    import asyncio

    async def run():
        result = await cut("TodoWrite", {}, None)
        return result

    result = asyncio.run(run())
    from claude_agent_sdk import PermissionResultAllow
    assert isinstance(result, PermissionResultAllow)


def test_read_only_allows_task_tools():
    """read_only=True should allow PROGRESS_TOOLS (progress/orchestration, no repo mutation)."""
    from autoswe.harness.ask_user_question import make_can_use_tool
    from autoswe.harness.runner import PROGRESS_TOOLS

    state = {}
    cut = make_can_use_tool({}, {}, state, read_only=True)

    import asyncio

    from claude_agent_sdk import PermissionResultAllow

    async def run():
        results = {}
        for tool in PROGRESS_TOOLS:
            results[tool] = await cut(tool, {}, None)
        return results

    results = asyncio.run(run())
    for tool, result in results.items():
        assert isinstance(result, PermissionResultAllow), f"{tool} should be allowed in read_only"


def test_read_only_blocks_bash_git_commit():
    """read_only=True should deny Bash with git commit."""
    from autoswe.harness.ask_user_question import make_can_use_tool

    state = {}
    cut = make_can_use_tool({}, {}, state, read_only=True)

    import asyncio

    async def run():
        result = await cut("Bash", {"command": 'git commit -m "agent work"'}, None)
        return result

    result = asyncio.run(run())
    from claude_agent_sdk import PermissionResultDeny
    assert isinstance(result, PermissionResultDeny)


def test_read_only_blocks_bash_git_push():
    """read_only=True should deny Bash with git push."""
    from autoswe.harness.ask_user_question import make_can_use_tool

    state = {}
    cut = make_can_use_tool({}, {}, state, read_only=True)

    import asyncio

    async def run():
        result = await cut("Bash", {"command": "git push origin autoswe/issue-138"}, None)
        return result

    result = asyncio.run(run())
    from claude_agent_sdk import PermissionResultDeny
    assert isinstance(result, PermissionResultDeny)


def test_read_only_allows_read_tools():
    """read_only=True should allow Read, Glob, Grep tools."""
    from autoswe.harness.ask_user_question import make_can_use_tool

    state = {}
    cut = make_can_use_tool({}, {}, state, read_only=True)

    import asyncio

    async def run():
        results = {}
        for tool in ("Read", "Glob", "Grep"):
            results[tool] = await cut(tool, {"file_path": "/tmp/test.py"}, None)
        return results

    results = asyncio.run(run())
    from claude_agent_sdk import PermissionResultAllow
    for tool, result in results.items():
        assert isinstance(result, PermissionResultAllow), f"{tool} should be allowed"


def test_read_only_allows_bash_read_commands():
    """read_only=True should allow Bash with git log, git status, python."""
    from autoswe.harness.ask_user_question import make_can_use_tool

    state = {}
    cut = make_can_use_tool({}, {}, state, read_only=True)

    import asyncio

    async def run():
        results = {}
        commands = [
            "git log --oneline -5",
            "git status",
            "python3 math_demo.py",
            "ls -la",
            "git diff --cached",
        ]
        for cmd in commands:
            results[cmd] = await cut("Bash", {"command": cmd}, None)
        return results

    results = asyncio.run(run())
    from claude_agent_sdk import PermissionResultAllow
    for cmd, result in results.items():
        assert isinstance(result, PermissionResultAllow), f"Bash '{cmd}' should be allowed"


def test_read_only_off_allows_everything():
    """read_only=False (default) should not block any tools."""
    from autoswe.harness.ask_user_question import make_can_use_tool

    state = {}
    cut = make_can_use_tool({}, {}, state, read_only=False)

    import asyncio

    async def run():
        result = await cut("Write", {"file_path": "/tmp/test.py"}, None)
        return result

    result = asyncio.run(run())
    from claude_agent_sdk import PermissionResultAllow
    assert isinstance(result, PermissionResultAllow)


def test_run_plan_passes_read_only(tmp_path, mock_gh_post_comment):
    """run_plan should call make_can_use_tool with read_only=True."""
    from unittest.mock import patch

    from autoswe.harness.runner import RunResult

    make_calls = []

    def fake_make_can_use_tool(task, repo_cfg, state, *, on_post=None, read_only=False):
        make_calls.append(read_only)
        return lambda name, inp, ctx: __import__("asyncio").run_coroutine_threadsafe(
            __import__("claude_agent_sdk").PermissionResultAllow(updated_input=inp),
            None,
        ) if False else None  # never actually called

    def fake_run(prompt, **kwargs):
        return RunResult("<AUTOSWE_PLAN>\nPlan\n</AUTOSWE_PLAN>", "sess", "success")

    task = {
        "id": "o_r_1", "owner": "o", "repo": "r", "issue_number": 1,
        "title": "Test", "body": "/plan", "base_branch": "master",
        "session_id": None, "_token": "ghp_fake",
    }

    with patch("autoswe.harness.planner.create_worktree", return_value=tmp_path):
        with patch("autoswe.harness.planner._find_latest_plan_file", return_value=None):
            with patch("autoswe.tracking.api._fetch_comments", return_value=[]):
                with patch("autoswe.harness.planner.make_can_use_tool") as mock_make:
                    mock_make.return_value = None  # callback not invoked by mock runner
                    with patch("autoswe.harness.runner.run", side_effect=fake_run):
                        from autoswe.harness.planner import run_plan
                        run_plan(task, {}, {"GITHUB_TOKEN": "tok"})

    mock_make.assert_called_once()
    call_kwargs = mock_make.call_args
    assert call_kwargs.kwargs.get("read_only") is True, (
        "run_plan must pass read_only=True to make_can_use_tool"
    )


def test_resume_plan_passes_read_only(tmp_path, mock_gh_post_comment):
    """resume_plan should call make_can_use_tool with read_only=True."""
    from unittest.mock import patch

    from autoswe.harness.runner import RunResult

    def fake_run(prompt, **kwargs):
        return RunResult("<AUTOSWE_PLAN>\nPlan\n</AUTOSWE_PLAN>", "sess", "success")

    task = {
        "id": "o_r_1", "owner": "o", "repo": "r", "issue_number": 1,
        "title": "Test", "body": "/plan", "base_branch": "master",
        "session_id": "existing-sess", "_token": "ghp_fake",
    }

    with patch("autoswe.harness.planner.create_worktree", return_value=tmp_path):
        with patch("autoswe.harness.runner.run", side_effect=fake_run):
            with patch("autoswe.harness.planner.make_can_use_tool") as mock_make:
                mock_make.return_value = None
                from autoswe.harness.planner import resume_plan
                resume_plan(task, "Green!", {}, {"GITHUB_TOKEN": "tok"})

    mock_make.assert_called_once()
    call_kwargs = mock_make.call_args
    assert call_kwargs.kwargs.get("read_only") is True, (
        "resume_plan must pass read_only=True to make_can_use_tool"
    )


# ---------------------------------------------------------------------------
# File-mutation bypass tests (_is_file_mutation)
# ---------------------------------------------------------------------------


def test_is_file_mutation_sed_in_place():
    """sed -i variants should be detected as file mutations."""
    from autoswe.harness.ask_user_question import _is_file_mutation

    assert _is_file_mutation('sed -i "s/foo/bar/" file.py')
    assert _is_file_mutation('sed -i.bak "s/foo/bar/" file.py')
    assert _is_file_mutation("sed -i '' 's/foo/bar/' file.py")
    assert _is_file_mutation("sed -i '/pattern/i\\\\new line' file.txt")
    assert _is_file_mutation("sed -i '4i\\\\Favorite Color: Blue\\\\n' README.md")


def test_is_file_mutation_shell_redirects():
    """Shell redirect operators should be detected as file mutations."""
    from autoswe.harness.ask_user_question import _is_file_mutation

    assert _is_file_mutation("echo 'hello' > file.txt")
    assert _is_file_mutation("echo 'hello' >> file.txt")
    assert _is_file_mutation("cat input > output.txt")
    assert _is_file_mutation("python script.py > result.txt")
    assert _is_file_mutation("echo data >> log.txt")


def test_is_file_mutation_tee():
    """tee should be detected as file mutation."""
    from autoswe.harness.ask_user_question import _is_file_mutation

    assert _is_file_mutation("echo 'data' | tee file.txt")
    assert _is_file_mutation("cat input | tee -a output.txt")


def test_is_file_mutation_python_one_liners():
    """python -c with open/write should be detected as file mutation."""
    from autoswe.harness.ask_user_question import _is_file_mutation

    assert _is_file_mutation(
        "python -c \"open('file.txt','w').write('hello')\""
    )
    assert _is_file_mutation(
        "python3 -c \"f=open('x','a'); f.write('data')\""
    )
    assert _is_file_mutation("python -c 'open(\"f\",\"w\").write(\"x\")'")


def test_is_file_mutation_perl_in_place():
    """perl -i should be detected as file mutation."""
    from autoswe.harness.ask_user_question import _is_file_mutation

    assert _is_file_mutation("perl -i -pe 's/foo/bar/' file.txt")
    assert _is_file_mutation("perl -i.bak -pe 's/foo/bar/' file.txt")


def test_is_file_mutation_curl_download():
    """curl -o/-O should be detected as file mutation."""
    from autoswe.harness.ask_user_question import _is_file_mutation

    assert _is_file_mutation("curl -o output.tar.gz https://example.com/file.tar.gz")
    assert _is_file_mutation("curl -O https://example.com/file.tar.gz")


def test_is_file_mutation_wget():
    """wget should be detected as file mutation."""
    from autoswe.harness.ask_user_question import _is_file_mutation

    assert _is_file_mutation("wget https://example.com/file.tar.gz")
    assert _is_file_mutation("wget -O local.tar.gz https://example.com/remote.tar.gz")


def test_is_file_mutation_echo_append():
    """echo >> should be detected as file mutation."""
    from autoswe.harness.ask_user_question import _is_file_mutation

    assert _is_file_mutation('echo "line" >> file.txt')
    assert _is_file_mutation("echo data >> log.txt")


def test_is_file_mutation_no_false_positives():
    """Read-only commands should NOT be detected as file mutations."""
    from autoswe.harness.ask_user_question import _is_file_mutation

    # /dev/null is not a file mutation
    assert not _is_file_mutation("command > /dev/null")
    assert not _is_file_mutation("command 2> /dev/null")
    assert not _is_file_mutation("command >> /dev/null")
    assert not _is_file_mutation("command > /dev/null 2>&1")
    assert not _is_file_mutation("command >> /dev/stdout")

    # Read-only commands
    assert not _is_file_mutation("cat file.py")
    assert not _is_file_mutation("grep 'pattern' file.py")
    assert not _is_file_mutation("ls -la")
    assert not _is_file_mutation("ls")
    assert not _is_file_mutation("head -n 20 file.py")
    assert not _is_file_mutation("tail -n 20 file.py")
    assert not _is_file_mutation("wc -l file.py")
    assert not _is_file_mutation("stat file.py")
    assert not _is_file_mutation("file some.py")
    assert not _is_file_mutation("find . -name '*.py'")
    assert not _is_file_mutation("git log --oneline -5")
    assert not _is_file_mutation("git status")
    assert not _is_file_mutation("git diff")
    assert not _is_file_mutation("python3 -c 'print(42)'")
    assert not _is_file_mutation("python3 script.py")
    assert not _is_file_mutation("echo 'hello'")
    assert not _is_file_mutation("echo hello")
    assert not _is_file_mutation("curl -s https://example.com | grep something")
    assert not _is_file_mutation("tree -L 2")
    assert not _is_file_mutation("diff file1 file2")


def test_read_only_blocks_sed_i(monkeypatch):
    """read_only=True should deny sed -i via Bash (reproduction of issue #209)."""
    from autoswe.harness.ask_user_question import make_can_use_tool

    state = {}
    cut = make_can_use_tool({}, {}, state, read_only=True)

    import asyncio

    from claude_agent_sdk import PermissionResultDeny

    async def run():
        return await cut(
            "Bash",
            {"command": "sed -i '4i\\\\Favorite Color: Blue\\\\n' README.md"},
            None,
        )

    result = asyncio.run(run())
    assert isinstance(result, PermissionResultDeny)
    assert "File modifications" in result.message


def test_read_only_blocks_echo_append(monkeypatch):
    """read_only=True should deny echo >> file via Bash."""
    from autoswe.harness.ask_user_question import make_can_use_tool

    state = {}
    cut = make_can_use_tool({}, {}, state, read_only=True)

    import asyncio

    from claude_agent_sdk import PermissionResultDeny

    async def run():
        return await cut(
            "Bash",
            {"command": 'echo "data" >> config.json'},
            None,
        )

    result = asyncio.run(run())
    assert isinstance(result, PermissionResultDeny)
    assert "File modifications" in result.message


def test_read_only_blocks_python_file_write():
    """read_only=True should deny python -c with file writes."""
    from autoswe.harness.ask_user_question import make_can_use_tool

    state = {}
    cut = make_can_use_tool({}, {}, state, read_only=True)

    import asyncio

    from claude_agent_sdk import PermissionResultDeny

    async def run():
        return await cut(
            "Bash",
            {"command": "python -c \"open('file.txt','w').write('hello')\""},
            None,
        )

    result = asyncio.run(run())
    assert isinstance(result, PermissionResultDeny)
    assert "File modifications" in result.message


def test_read_only_blocks_curl_download():
    """read_only=True should deny curl -o via Bash."""
    from autoswe.harness.ask_user_question import make_can_use_tool

    state = {}
    cut = make_can_use_tool({}, {}, state, read_only=True)

    import asyncio

    from claude_agent_sdk import PermissionResultDeny

    async def run():
        return await cut(
            "Bash",
            {"command": "curl -o payload.json https://example.com/data"},
            None,
        )

    result = asyncio.run(run())
    assert isinstance(result, PermissionResultDeny)
    assert "File modifications" in result.message


def test_read_only_allows_dev_null_redirect():
    """read_only=True should allow commands redirecting to /dev/null."""
    from autoswe.harness.ask_user_question import make_can_use_tool

    state = {}
    cut = make_can_use_tool({}, {}, state, read_only=True)

    import asyncio

    from claude_agent_sdk import PermissionResultAllow

    async def run():
        results = {}
        for cmd in (
            "grep pattern file.py > /dev/null",
            "command 2> /dev/null",
            "command >> /dev/null",
            "command > /dev/null 2>&1",
        ):
            results[cmd] = await cut("Bash", {"command": cmd}, None)
        return results

    results = asyncio.run(run())
    for cmd, result in results.items():
        assert isinstance(result, PermissionResultAllow), (
            f"Bash '{cmd}' should be allowed (redirects to /dev/null)"
        )


def test_read_only_allows_simple_echo():
    """read_only=True should allow echo without file redirects."""
    from autoswe.harness.ask_user_question import make_can_use_tool

    state = {}
    cut = make_can_use_tool({}, {}, state, read_only=True)

    import asyncio

    from claude_agent_sdk import PermissionResultAllow

    async def run():
        return await cut("Bash", {"command": "echo 'hello world'"}, None)

    result = asyncio.run(run())
    assert isinstance(result, PermissionResultAllow)


def test_read_only_allows_bash_read_commands_still():
    """Existing read-only Bash commands must still work after adding file mutation guard."""
    from autoswe.harness.ask_user_question import make_can_use_tool

    state = {}
    cut = make_can_use_tool({}, {}, state, read_only=True)

    import asyncio

    from claude_agent_sdk import PermissionResultAllow

    async def run():
        results = {}
        commands = [
            "git log --oneline -5",
            "git status",
            "python3 math_demo.py",
            "ls -la",
            "git diff --cached",
            "cat file.py",
            "grep 'def ' file.py",
            "find . -name '*.py'",
            "head -20 README.md",
            "tree -L 2",
        ]
        for cmd in commands:
            results[cmd] = await cut("Bash", {"command": cmd}, None)
        return results

    results = asyncio.run(run())
    for cmd, result in results.items():
        assert isinstance(result, PermissionResultAllow), (
            f"Bash '{cmd}' should be allowed"
        )


def test_read_only_file_mutation_blocked_when_read_only_off():
    """File mutation commands should be ALLOWED when read_only=False (fix phase)."""
    from autoswe.harness.ask_user_question import make_can_use_tool

    state = {}
    cut = make_can_use_tool({}, {}, state, read_only=False)

    import asyncio

    from claude_agent_sdk import PermissionResultAllow

    async def run():
        results = {}
        commands = [
            'sed -i "s/foo/bar/" file.py',
            "echo 'data' >> log.txt",
            "python -c \"open('x','w').write('y')\"",
            "curl -o file.tar.gz https://example.com/file.tar.gz",
        ]
        for cmd in commands:
            results[cmd] = await cut("Bash", {"command": cmd}, None)
        return results

    results = asyncio.run(run())
    for cmd, result in results.items():
        assert isinstance(result, PermissionResultAllow), (
            f"Bash '{cmd}' should be allowed when read_only=False"
        )


# ---------------------------------------------------------------------------
# Fix 2: Agent tool must not be in plan-phase allowed_tools


def test_plan_phase_does_not_allow_agent_tool_run_plan(tmp_path, mock_gh_post_comment):
    """run_plan must NOT include 'Agent' in allowed_tools — Agent spawns
    sub-agents that bypass the read-only can_use_tool callback."""
    run_calls = []

    def fake_run(prompt, **kwargs):
        run_calls.append(kwargs)
        from autoswe.harness.runner import RunResult
        return RunResult("<AUTOSWE_PLAN>\nPlan\n</AUTOSWE_PLAN>", "sess", "success")

    task = {
        "id": "o_r_1", "owner": "o", "repo": "r", "issue_number": 1,
        "title": "Test", "body": "/plan", "base_branch": "master",
        "session_id": None, "_token": "ghp_fake",
    }

    with patch("autoswe.harness.planner.create_worktree", return_value=tmp_path):
        with patch("autoswe.harness.planner._find_latest_plan_file", return_value=None):
            with patch("autoswe.tracking.api._fetch_comments", return_value=[]):
                with patch("autoswe.harness.runner.run", side_effect=fake_run):
                    from autoswe.harness.planner import run_plan
                    run_plan(task, {}, {"GITHUB_TOKEN": "tok"})

    tools = run_calls[0]["allowed_tools"]
    assert "Agent" not in tools, (
        "Agent must not be in run_plan allowed_tools — it bypasses read-only containment"
    )


def test_plan_phase_does_not_allow_agent_tool_resume_plan(tmp_path, mock_gh_post_comment):
    """resume_plan must NOT include 'Agent' in allowed_tools."""
    run_calls = []

    def fake_run(prompt, **kwargs):
        run_calls.append(kwargs)
        from autoswe.harness.runner import RunResult
        return RunResult("<AUTOSWE_PLAN>\nPlan\n</AUTOSWE_PLAN>", "sess", "success")

    task = {
        "id": "o_r_1", "owner": "o", "repo": "r", "issue_number": 1,
        "title": "Test", "body": "/plan", "base_branch": "master",
        "session_id": "existing-sess", "_token": "ghp_fake",
    }

    with patch("autoswe.harness.planner.create_worktree", return_value=tmp_path):
        with patch("autoswe.harness.runner.run", side_effect=fake_run):
            from autoswe.harness.planner import resume_plan
            resume_plan(task, "Green!", {}, {"GITHUB_TOKEN": "tok"})

    tools = run_calls[0]["allowed_tools"]
    assert "Agent" not in tools, (
        "Agent must not be in resume_plan allowed_tools — it bypasses read-only containment"
    )


def test_plan_phase_allows_progress_tools(tmp_path, mock_gh_post_comment):
    """run_plan must include PROGRESS_TOOLS (TodoWrite, TaskCreate, etc.) in allowed_tools."""
    run_calls = []

    def fake_run(prompt, **kwargs):
        run_calls.append(kwargs)
        from autoswe.harness.runner import RunResult
        return RunResult("<AUTOSWE_PLAN>\nPlan\n</AUTOSWE_PLAN>", "sess", "success")

    task = {
        "id": "o_r_1", "owner": "o", "repo": "r", "issue_number": 1,
        "title": "Test", "body": "/plan", "base_branch": "master",
        "session_id": None, "_token": "ghp_fake",
    }

    with patch("autoswe.harness.planner.create_worktree", return_value=tmp_path):
        with patch("autoswe.harness.planner._find_latest_plan_file", return_value=None):
            with patch("autoswe.tracking.api._fetch_comments", return_value=[]):
                with patch("autoswe.harness.runner.run", side_effect=fake_run):
                    from autoswe.harness.planner import run_plan
                    run_plan(task, {}, {"GITHUB_TOKEN": "tok"})

    tools = run_calls[0]["allowed_tools"]
    from autoswe.harness.runner import PROGRESS_TOOLS
    for tool in PROGRESS_TOOLS:
        assert tool in tools, f"{tool} should be in plan allowed_tools"
