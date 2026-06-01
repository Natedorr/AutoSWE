"""Tests for autoswe.harness.coder handler return values."""

import asyncio
from contextlib import ExitStack
from unittest.mock import patch

from autoswe.harness.runner import RunResult


def _r(text, session_id="sess", subtype="success"):
    """Shorthand for RunResult(text, session_id, subtype)."""
    return RunResult(text, session_id, subtype)


def make_task(session_id=None):
    return {
        "id": "o_r_1",
        "owner": "o",
        "repo": "r",
        "issue_number": 1,
        "title": "Test fix",
        "body": "/fix",
        "base_branch": "master",
        "session_id": session_id,
        "_token": "ghp_fake",
    }


def _patch_worktree(tmp_path):
    stack = ExitStack()
    stack.enter_context(patch("autoswe.harness.coder.create_worktree", return_value=tmp_path))
    stack.enter_context(patch("autoswe.harness.coder.fast_forward_worktree", return_value=True))
    return stack


def _fetch_comments_patch():
    """Return a fresh patch instance for _fetch_comments.

    Using a factory function avoids the leak that occurs when reusing a single
    module-level ``patch`` object across many tests (patch.start()/stop() via
    ExitStack does not fully clean up internal _patching bookkeeping, leaving
    the target permanently mocked for subsequent tests).
    """
    return patch("autoswe.tracking.api._fetch_comments", return_value=[])


FAKE_COMMIT_RESULT = {
    "committed": True,
    "commit_sha": "abc1234",
    "branch": "autoswe/issue-1",
}

NO_CHANGES_RESULT = {"committed": False}


# ---------------------------------------------------------------------------
# run_fix return values
# ---------------------------------------------------------------------------

def test_run_fix_returns_done_summary_when_committed(tmp_path):
    task = make_task()

    with _patch_worktree(tmp_path):
        with _fetch_comments_patch():
            with patch("autoswe.harness.runner.run", return_value=_r("Changed 3 files.", "sess-1")):
                with patch("autoswe.harness.coder.commit_and_push", return_value=FAKE_COMMIT_RESULT):
                    from autoswe.harness.coder import run_fix
                    result = run_fix(task, cfg={})

    assert result.done_content.startswith("DONE_SUMMARY\t")
    assert "Changed 3 files." in result.done_content
    assert "\tabc1234" in result.done_content
    assert task["session_id"] == "sess-1"


def test_run_fix_returns_done_no_changes(tmp_path):
    task = make_task()

    with _patch_worktree(tmp_path):
        with _fetch_comments_patch():
            with patch("autoswe.harness.runner.run", return_value=_r("No changes needed.", "sess-2")):
                with patch("autoswe.harness.coder.commit_and_push", return_value=NO_CHANGES_RESULT):
                    from autoswe.harness.coder import run_fix
                    result = run_fix(task, cfg={})

    assert result.done_content == "DONE: no changes detected"


def test_run_fix_returns_failed_on_non_success_subtype(tmp_path):
    task = make_task()

    with _patch_worktree(tmp_path):
        with _fetch_comments_patch():
            with patch("autoswe.harness.runner.run", return_value=_r("", "sess-3", "error")):
                with patch("autoswe.harness.coder.commit_and_push", return_value=NO_CHANGES_RESULT):
                    from autoswe.harness.coder import run_fix
                    result = run_fix(task, cfg={})

    assert result.done_content.startswith("FAILED:")
    assert "subtype" in result.done_content


def test_run_fix_returns_failed_on_timeout(tmp_path):
    task = make_task()

    with _patch_worktree(tmp_path):
        with _fetch_comments_patch():
            with patch("autoswe.harness.runner.run", side_effect=asyncio.TimeoutError()):
                from autoswe.harness.coder import run_fix
                result = run_fix(task, cfg={})

    assert result.done_content.startswith("FAILED:")
    assert "timeout" in result.done_content.lower()


def test_run_fix_returns_failed_on_commit_error(tmp_path):
    task = make_task()

    with _patch_worktree(tmp_path):
        with _fetch_comments_patch():
            with patch("autoswe.harness.runner.run", return_value=_r("Done.", "sess-4")):
                with patch("autoswe.harness.coder.commit_and_push", side_effect=RuntimeError("git push failed")):
                    from autoswe.harness.coder import run_fix
                    result = run_fix(task, cfg={})

    assert result.done_content.startswith("FAILED:")
    assert "commit/push" in result.done_content


def test_run_fix_passes_guidance_in_prompt(tmp_path):
    task = make_task()
    run_calls = []

    def fake_run(prompt, **kwargs):
        run_calls.append(prompt)
        return _r("Done.")

    with _patch_worktree(tmp_path):
        with _fetch_comments_patch():
            with patch("autoswe.harness.runner.run", side_effect=fake_run):
                with patch("autoswe.harness.coder.commit_and_push", return_value=FAKE_COMMIT_RESULT):
                    from autoswe.harness.coder import run_fix
                    run_fix(task, guidance="with extra logging", cfg={})

    assert "extra logging" in run_calls[0]


def test_run_fix_uses_mode_read_write(tmp_path):
    """Fix phase should use mode='read_write' (backend translates to bypassPermissions + full tools)."""
    task = make_task()
    run_calls = []

    def fake_run(prompt, **kwargs):
        run_calls.append(kwargs)
        return _r("Done.")

    with _patch_worktree(tmp_path):
        with _fetch_comments_patch():
            with patch("autoswe.harness.runner.run", side_effect=fake_run):
                with patch("autoswe.harness.coder.commit_and_push", return_value=FAKE_COMMIT_RESULT):
                    from autoswe.harness.coder import run_fix
                    run_fix(task, cfg={})

    assert run_calls[0]["mode"] == "read_write"
    # Verify the backend maps mode="read_write" to bypassPermissions
    from autoswe.harness.backends.claude_code import _MODE_CONFIG
    perm, tools, _disallowed = _MODE_CONFIG["read_write"]
    assert perm == "bypassPermissions"
    assert "Agent" in tools
    assert "Edit" in tools
    assert "Bash" in tools


# ---------------------------------------------------------------------------
# Edge cases for coder
# ---------------------------------------------------------------------------

def test_run_fix_starts_fresh_session_when_plan_file_path_set(tmp_path):
    """When plan_file_path is set, runner should start fresh (resume=None) and use plan file text."""
    plan_file = tmp_path / "plan.md"
    plan_file.write_text("PLAN BODY: do the thing")
    task = make_task(session_id="old-plan-sess")
    task["plan_file_path"] = str(plan_file)
    run_calls = []

    def fake_run(prompt, **kwargs):
        run_calls.append({"prompt": prompt, **kwargs})
        return _r("Done.", "new-fix-sess")

    with _patch_worktree(tmp_path):
        with _fetch_comments_patch():
            with patch("autoswe.harness.runner.run", side_effect=fake_run):
                with patch("autoswe.harness.coder.commit_and_push", return_value=FAKE_COMMIT_RESULT):
                    from autoswe.harness.coder import run_fix
                    run_fix(task, cfg={})

    assert run_calls[0]["resume"] is None
    assert "PLAN BODY: do the thing" in run_calls[0]["prompt"]
    assert "plan_file_path" not in task


def test_run_fix_resumes_session_when_no_plan_file_path(tmp_path):
    """Without plan_file_path on task, runner should resume the prior session."""
    task = make_task(session_id="sess-prev")
    run_calls = []

    def fake_run(prompt, **kwargs):
        run_calls.append(kwargs)
        return _r("Done.", "sess-new")

    with _patch_worktree(tmp_path):
        with _fetch_comments_patch():
            with patch("autoswe.harness.runner.run", side_effect=fake_run):
                with patch("autoswe.harness.coder.commit_and_push", return_value=FAKE_COMMIT_RESULT):
                    from autoswe.harness.coder import run_fix
                    run_fix(task, cfg={})

    assert run_calls[0]["resume"] == "sess-prev"


def test_run_fix_starts_fresh_session_when_plan_file_missing(tmp_path):
    """If plan_file_path points to a nonexistent file, start a fresh session.

    The plan is recovered from issue comments by build_fix_prompt, but the
    session must be fresh so the fix template gives an explicit implement
    instruction (not a resumed plan session that re-describes the plan).
    """
    task = make_task(session_id="sess-prev")
    task["plan_file_path"] = str(tmp_path / "nonexistent.md")
    run_calls = []

    def fake_run(prompt, **kwargs):
        run_calls.append(kwargs)
        return _r("Done.", "sess-new")

    with _patch_worktree(tmp_path):
        with _fetch_comments_patch():
            with patch("autoswe.harness.runner.run", side_effect=fake_run):
                with patch("autoswe.harness.coder.commit_and_push", return_value=FAKE_COMMIT_RESULT):
                    from autoswe.harness.coder import run_fix
                    run_fix(task, cfg={})

    assert run_calls[0]["resume"] is None


def test_run_fix_resumes_with_session_id(tmp_path):
    """If task has a session_id, it should be passed to resume."""
    task = make_task(session_id="prev-sess")
    run_calls = []

    def fake_run(prompt, **kwargs):
        run_calls.append(kwargs)
        return _r("Changed files.", "new-sess")

    with _patch_worktree(tmp_path):
        with _fetch_comments_patch():
            with patch("autoswe.harness.runner.run", side_effect=fake_run):
                with patch("autoswe.harness.coder.commit_and_push", return_value=FAKE_COMMIT_RESULT):
                    from autoswe.harness.coder import run_fix
                    run_fix(task, cfg={})

    assert run_calls[0]["resume"] == "prev-sess"


def test_run_fix_mode_provides_full_tool_set(tmp_path):
    """Fix phase mode='read_write' provides editing tools + MCP comment tools + Agent."""
    task = make_task()
    run_calls = []

    def fake_run(prompt, **kwargs):
        run_calls.append(kwargs)
        return _r("Done.")

    with _patch_worktree(tmp_path):
        with _fetch_comments_patch():
            with patch("autoswe.harness.runner.run", side_effect=fake_run):
                with patch("autoswe.harness.coder.commit_and_push", return_value=FAKE_COMMIT_RESULT):
                    from autoswe.harness.coder import run_fix
                    run_fix(task, cfg={})

    assert run_calls[0]["mode"] == "read_write"
    # Verify the backend maps mode="read_write" to full tool set
    from autoswe.harness.backends.claude_code import _MODE_CONFIG
    _perm, tools, _disallowed = _MODE_CONFIG["read_write"]
    allowed = set(tools)
    assert "Edit" in allowed
    assert "Bash" in allowed
    assert "Write" in allowed
    assert "mcp__autoswe_comment__update_progress" in allowed
    from autoswe.harness.runner import AGENT_TASK_TOOLS
    for tool in AGENT_TASK_TOOLS:
        assert tool in allowed, f"{tool} should be in read_write mode tools"



def test_run_fix_updates_task_session_id(tmp_path):
    """Task session_id should be updated with new session from SDK."""
    task = make_task(session_id="old-sess")

    with _patch_worktree(tmp_path):
        with _fetch_comments_patch():
            with patch("autoswe.harness.runner.run", return_value=_r("Done.", "new-sess")):
                with patch("autoswe.harness.coder.commit_and_push", return_value=FAKE_COMMIT_RESULT):
                    from autoswe.harness.coder import run_fix
                    run_fix(task, cfg={})

    assert task["session_id"] == "new-sess"


def test_run_fix_non_success_subtype_details(tmp_path):
    """Non-success subtype should include the subtype value in error."""
    task = make_task()

    with _patch_worktree(tmp_path):
        with _fetch_comments_patch():
            with patch("autoswe.harness.runner.run", return_value=_r("", "sess", "permission_denied")):
                with patch("autoswe.harness.coder.commit_and_push", return_value=NO_CHANGES_RESULT):
                    from autoswe.harness.coder import run_fix
                    result = run_fix(task, cfg={})

    assert result.done_content.startswith("FAILED:")
    assert "permission_denied" in result.done_content


def test_run_fix_with_empty_guidance(tmp_path):
    """Empty guidance should not add a GUIDANCE_BLOCK."""
    task = make_task()
    run_calls = []

    def fake_run(prompt, **kwargs):
        run_calls.append(prompt)
        return _r("Done.")

    with _patch_worktree(tmp_path):
        with _fetch_comments_patch():
            with patch("autoswe.harness.runner.run", side_effect=fake_run):
                with patch("autoswe.harness.coder.commit_and_push", return_value=FAKE_COMMIT_RESULT):
                    from autoswe.harness.coder import run_fix
                    run_fix(task, guidance="", cfg={})

    prompt = run_calls[0]
    # Empty guidance should result in empty GUIDANCE_BLOCK or no "Guidance:" prefix
    assert "Guidance: " not in prompt or "Guidance: \n\n" in prompt or prompt.count("Guidance:") == 0


def test_run_fix_uses_plan_branch_over_base(tmp_path):
    """plan_branch should override base_branch for the worktree."""
    task = make_task()
    task["plan_branch"] = "develop"
    worktree_calls = []

    def fake_worktree(owner, repo, issue_num, base_branch, token, cfg, provider="github", **kwargs):
        worktree_calls.append(base_branch)
        return tmp_path

    with patch("autoswe.harness.coder.create_worktree", side_effect=fake_worktree):
        with _fetch_comments_patch():
            with patch("autoswe.harness.runner.run", return_value=_r("Done.")):
                with patch("autoswe.harness.coder.commit_and_push", return_value=FAKE_COMMIT_RESULT):
                    from autoswe.harness.coder import run_fix
                    run_fix(task, cfg={})

    assert worktree_calls[0] == "develop"


# ---------------------------------------------------------------------------
# Path sanitization
# ---------------------------------------------------------------------------

def test_sanitize_paths_replaces_absolute_with_relative():
    from autoswe.harness.prompts import _sanitize_paths

    result = _sanitize_paths(
        "Edit `/home/user/repo/autoswe/cli.py` to add the flag.",
        "/home/user/repo",
    )
    assert "autoswe/cli.py" in result
    assert "/home/user/repo" not in result


def test_sanitize_paths_replaces_bare_repo_root():
    from autoswe.harness.prompts import _sanitize_paths

    result = _sanitize_paths(
        "The repo is at /home/user/repo. Edit the file there.",
        "/home/user/repo",
    )
    assert "/home/user/repo" not in result
    assert ". Edit the file" in result  # . replaces path, period remains


def test_sanitize_paths_handles_nested_paths():
    from autoswe.harness.prompts import _sanitize_paths

    result = _sanitize_paths(
        "See /home/user/repo/tests/test_foo.py and /home/user/repo/autoswe/bar.py",
        "/home/user/repo",
    )
    assert "tests/test_foo.py" in result
    assert "autoswe/bar.py" in result
    assert "/home/user/repo" not in result


def test_sanitize_paths_no_false_positives():
    from autoswe.harness.prompts import _sanitize_paths

    # Path that looks similar but is a different repo
    result = _sanitize_paths(
        "/home/user/repo-extra/file.txt",
        "/home/user/repo",
    )
    assert result == "/home/user/repo-extra/file.txt"


def test_sanitize_paths_empty_inputs():
    from autoswe.harness.prompts import _sanitize_paths

    assert _sanitize_paths("", "/home/user/repo") == ""
    assert _sanitize_paths("hello", None) == "hello"
    assert _sanitize_paths("", None) == ""


def test_sanitize_paths_in_prompt(tmp_path):
    """Sanitization should strip absolute paths from the built prompt."""
    task = make_task()
    task["body"] = f"Edit `{tmp_path}/autoswe/cli.py` to add a flag."
    run_calls = []

    def fake_run(prompt, **kwargs):
        run_calls.append(prompt)
        return _r("Done.")

    with _patch_worktree(tmp_path):
        with _fetch_comments_patch():
            with patch("autoswe.harness.runner.run", side_effect=fake_run):
                with patch("autoswe.harness.coder.commit_and_push", return_value=FAKE_COMMIT_RESULT):
                    from autoswe.harness.coder import run_fix
                    run_fix(task, cfg={})

    assert str(tmp_path) not in run_calls[0]
    assert "autoswe/cli.py" in run_calls[0]


def test_run_fix_uses_base_branch_when_no_plan_branch(tmp_path):
    """When plan_branch is not set, fall back to base_branch."""
    task = make_task()
    task["base_branch"] = "main"
    worktree_calls = []

    def fake_worktree(owner, repo, issue_num, base_branch, token, cfg, provider="github", **kwargs):
        worktree_calls.append(base_branch)
        return tmp_path

    with patch("autoswe.harness.coder.create_worktree", side_effect=fake_worktree):
        with _fetch_comments_patch():
            with patch("autoswe.harness.runner.run", return_value=_r("Done.")):
                with patch("autoswe.harness.coder.commit_and_push", return_value=FAKE_COMMIT_RESULT):
                    from autoswe.harness.coder import run_fix
                    run_fix(task, cfg={})

    assert worktree_calls[0] == "main"


def test_plan_extracted_from_comments(tmp_path):
    """AUTOSWE_PLAN blocks in comments should be injected into the fix prompt."""
    task = make_task()
    fake_comments = [
        {
            "user": {"login": "bot"},
            "created_at": "2026-01-01T00:00:00Z",
            "body": "## Plan\n<AUTOSWE_PLAN>Step 1: Fix file A\nStep 2: Fix file B</AUTOSWE_PLAN>",
        },
    ]
    run_calls = []

    def fake_run(prompt, **kwargs):
        run_calls.append(prompt)
        return _r("Done.")

    fake_comments_patch = patch("autoswe.tracking.api._fetch_comments", return_value=fake_comments)

    with _patch_worktree(tmp_path):
        with fake_comments_patch:
            with patch("autoswe.harness.runner.run", side_effect=fake_run):
                with patch("autoswe.harness.coder.commit_and_push", return_value=FAKE_COMMIT_RESULT):
                    from autoswe.harness.coder import run_fix
                    run_fix(task, cfg={})

    assert "Plan to implement:" in run_calls[0]
    assert "Step 1: Fix file A" in run_calls[0]
    assert "Step 2: Fix file B" in run_calls[0]


# ---------------------------------------------------------------------------
# Branch linking tests
# ---------------------------------------------------------------------------

def test_run_fix_links_branch_on_successful_commit(tmp_path):
    """link_branch_to_issue should be called after a successful commit."""
    task = make_task()
    link_calls = []

    class FakeVCS:
        def link_branch_to_issue(self, issue_number, commit_sha, branch):
            link_calls.append((issue_number, commit_sha, branch))

    with _patch_worktree(tmp_path):
        with _fetch_comments_patch():
            with patch("autoswe.harness.runner.run", return_value=_r("Done.", "sess")):
                with patch("autoswe.harness.coder.commit_and_push", return_value=FAKE_COMMIT_RESULT):
                    with patch("autoswe.harness.coder.get_vcs", return_value=FakeVCS()):
                        from autoswe.harness.coder import run_fix
                        run_fix(task, cfg={})

    assert len(link_calls) == 1
    assert link_calls[0][0] == 1  # issue_number
    assert link_calls[0][1] == "abc1234"  # commit_sha
    assert link_calls[0][2] == "autoswe/issue-1"  # branch


def test_run_fix_does_not_link_branch_when_no_changes(tmp_path):
    """link_branch_to_issue should NOT be called when commit detects no changes."""
    task = make_task()
    link_calls = []

    class FakeVCS:
        def link_branch_to_issue(self, issue_number, commit_sha, branch):
            link_calls.append((issue_number, commit_sha, branch))

    with _patch_worktree(tmp_path):
        with _fetch_comments_patch():
            with patch("autoswe.harness.runner.run", return_value=_r("Done.", "sess")):
                with patch("autoswe.harness.coder.commit_and_push", return_value=NO_CHANGES_RESULT):
                    with patch("autoswe.harness.coder.get_vcs", return_value=FakeVCS()):
                        from autoswe.harness.coder import run_fix
                        result = run_fix(task, cfg={})

    assert result.done_content == "DONE: no changes detected"
    assert len(link_calls) == 0


def test_run_fix_link_branch_failure_does_not_fail_fix(tmp_path):
    """If link_branch_to_issue raises, the fix should still return DONE_SUMMARY."""
    task = make_task()

    class FailingVCS:
        def link_branch_to_issue(self, issue_number, commit_sha, branch):
            raise RuntimeError("API down")

    with _patch_worktree(tmp_path):
        with _fetch_comments_patch():
            with patch("autoswe.harness.runner.run", return_value=_r("Done.", "sess")):
                with patch("autoswe.harness.coder.commit_and_push", return_value=FAKE_COMMIT_RESULT):
                    with patch("autoswe.harness.coder.get_vcs", return_value=FailingVCS()):
                        from autoswe.harness.coder import run_fix
                        result = run_fix(task, cfg={})

    assert result.done_content.startswith("DONE_SUMMARY\t")


# ---------------------------------------------------------------------------
# Commit message content (Phase 2 — descriptive messages)
# ---------------------------------------------------------------------------

def test_run_fix_commit_message_uses_guidance(tmp_path):
    """Commit message subject should include guidance text when provided."""
    task = make_task()
    commit_calls = []

    def fake_commit_and_push(wt, owner, repo, issue_num, msg, base_branch, provider="github"):
        commit_calls.append(msg)
        return FAKE_COMMIT_RESULT

    with _patch_worktree(tmp_path):
        with _fetch_comments_patch():
            with patch("autoswe.harness.runner.run", return_value=_r("Fixed it.")):
                with patch("autoswe.harness.coder.commit_and_push", side_effect=fake_commit_and_push):
                    from autoswe.harness.coder import run_fix
                    run_fix(task, guidance="add retry logic", cfg={})

    assert commit_calls, "commit_and_push was not called"
    msg = commit_calls[0]
    assert msg.startswith("autoswe: add retry logic"), \
        f"Subject should start with guidance, got: {msg!r}"


def test_run_fix_commit_message_default_when_no_guidance(tmp_path):
    """Without guidance, commit message should use the default subject."""
    task = make_task()
    commit_calls = []

    def fake_commit_and_push(wt, owner, repo, issue_num, msg, base_branch, provider="github"):
        commit_calls.append(msg)
        return FAKE_COMMIT_RESULT

    with _patch_worktree(tmp_path):
        with _fetch_comments_patch():
            with patch("autoswe.harness.runner.run", return_value=_r("Done.")):
                with patch("autoswe.harness.coder.commit_and_push", side_effect=fake_commit_and_push):
                    from autoswe.harness.coder import run_fix
                    run_fix(task, guidance=None, cfg={})

    assert commit_calls
    msg = commit_calls[0]
    assert msg.startswith("autoswe: automated fix"), \
        f"Default subject should be 'autoswe: automated fix', got: {msg!r}"


def test_run_fix_commit_message_refs_issue(tmp_path):
    """Commit message footer should use 'Refs #N' (not 'Fixes #N')."""
    task = make_task()
    commit_calls = []

    def fake_commit_and_push(wt, owner, repo, issue_num, msg, base_branch, provider="github"):
        commit_calls.append(msg)
        return FAKE_COMMIT_RESULT

    with _patch_worktree(tmp_path):
        with _fetch_comments_patch():
            with patch("autoswe.harness.runner.run", return_value=_r("Done.")):
                with patch("autoswe.harness.coder.commit_and_push", side_effect=fake_commit_and_push):
                    from autoswe.harness.coder import run_fix
                    run_fix(task, cfg={})

    assert commit_calls
    msg = commit_calls[0]
    assert "Refs #1" in msg, f"Footer should say 'Refs #1', got: {msg!r}"
    assert "Fixes #1" not in msg, f"Should NOT say 'Fixes #1' (closes the issue), got: {msg!r}"


def test_run_fix_commit_message_includes_session_output(tmp_path):
    """Commit message body should include tail of Claude's session output."""
    task = make_task()
    commit_calls = []

    def fake_commit_and_push(wt, owner, repo, issue_num, msg, base_branch, provider="github"):
        commit_calls.append(msg)
        return FAKE_COMMIT_RESULT

    session_text = "\n".join(f"Line {i}" for i in range(20))

    with _patch_worktree(tmp_path):
        with _fetch_comments_patch():
            with patch("autoswe.harness.runner.run", return_value=_r(session_text)):
                with patch("autoswe.harness.coder.commit_and_push", side_effect=fake_commit_and_push):
                    from autoswe.harness.coder import run_fix
                    run_fix(task, cfg={})

    assert commit_calls
    msg = commit_calls[0]
    assert "Line 19" in msg, "Commit body should include last lines of session output"


# ---------------------------------------------------------------------------
# HandlerResult carries cost and duration
# ---------------------------------------------------------------------------

def test_run_fix_returns_cost_and_duration(tmp_path):
    """run_fix should propagate cost_usd and duration_seconds from RunResult."""
    task = make_task()

    with _patch_worktree(tmp_path):
        with _fetch_comments_patch():
            with patch("autoswe.harness.runner.run",
                       return_value=RunResult("Done.", "sess", "success", cost_usd=1.23, duration_seconds=120.7)):
                with patch("autoswe.harness.coder.commit_and_push", return_value=FAKE_COMMIT_RESULT):
                    from autoswe.harness.coder import run_fix
                    result = run_fix(task, cfg={})

    assert result.done_content.startswith("DONE_SUMMARY\t")
    assert result.cost_usd == 1.23
    assert result.duration_seconds == 120.7


def test_run_fix_returns_zero_cost_when_none(tmp_path):
    """run_fix should pass None cost when the API doesn't report one."""
    task = make_task()

    with _patch_worktree(tmp_path):
        with _fetch_comments_patch():
            with patch("autoswe.harness.runner.run",
                       return_value=RunResult("Done.", "sess", "success", cost_usd=None, duration_seconds=0.0)):
                with patch("autoswe.harness.coder.commit_and_push", return_value=FAKE_COMMIT_RESULT):
                    from autoswe.harness.coder import run_fix
                    result = run_fix(task, cfg={})

    assert result.done_content.startswith("DONE_SUMMARY\t")
    assert result.cost_usd is None
    assert result.duration_seconds == 0.0


# ---------------------------------------------------------------------------
# pull_strategy="merge" and conflict-folding


def test_run_fix_passes_pull_strategy_merge(tmp_path):
    """run_fix should call create_worktree with pull_strategy='merge'."""
    task = make_task()
    worktree_kwargs = []

    def fake_worktree(*args, **kwargs):
        worktree_kwargs.append(kwargs)
        return tmp_path

    with patch("autoswe.harness.coder.create_worktree", side_effect=fake_worktree):
        with _fetch_comments_patch():
            with patch("autoswe.harness.runner.run", return_value=_r("Done.")):
                with patch("autoswe.harness.coder.commit_and_push", return_value=FAKE_COMMIT_RESULT):
                    from autoswe.harness.coder import run_fix
                    run_fix(task, cfg={})

    assert len(worktree_kwargs) == 1
    assert worktree_kwargs[0].get("pull_strategy") == "merge"


def test_run_fix_folds_conflict_files_into_prompt(tmp_path):
    """When get_merge_conflict_files returns files, the prompt should include
    merge conflict resolution instructions."""
    task = make_task()
    run_calls = []

    def fake_run(prompt, **kwargs):
        run_calls.append(prompt)
        return _r("Done.")

    with _patch_worktree(tmp_path):
        with _fetch_comments_patch():
            with patch("autoswe.harness.coder.get_merge_conflict_files",
                       return_value=["src/main.py", "src/utils.py"]):
                with patch("autoswe.harness.runner.run", side_effect=fake_run):
                    with patch("autoswe.harness.coder.commit_and_push", return_value=FAKE_COMMIT_RESULT):
                        from autoswe.harness.coder import run_fix
                        run_fix(task, guidance="fix login", cfg={})

    assert len(run_calls) == 1
    prompt = run_calls[0]
    assert "Merge conflicts to resolve first" in prompt
    assert "src/main.py" in prompt
    assert "src/utils.py" in prompt
    assert "git add -A && git commit --no-edit" in prompt


def test_run_fix_no_conflict_prompt_when_clean(tmp_path):
    """When get_merge_conflict_files returns [], no conflict block in prompt."""
    task = make_task()
    run_calls = []

    def fake_run(prompt, **kwargs):
        run_calls.append(prompt)
        return _r("Done.")

    with _patch_worktree(tmp_path):
        with _fetch_comments_patch():
            with patch("autoswe.harness.coder.get_merge_conflict_files", return_value=[]):
                with patch("autoswe.harness.runner.run", side_effect=fake_run):
                    with patch("autoswe.harness.coder.commit_and_push", return_value=FAKE_COMMIT_RESULT):
                        from autoswe.harness.coder import run_fix
                        run_fix(task, cfg={})

    assert len(run_calls) == 1
    prompt = run_calls[0]
    assert "Merge conflicts to resolve first" not in prompt


# ---------------------------------------------------------------------------
# AskUserQuestion support


def test_run_fix_ask_user_question_returns_waiting(tmp_path):
    """When AskUserQuestion fires during fix, run_fix returns WAITING without commit."""
    task = make_task()

    def fake_run(prompt, **kwargs):
        kwargs["state"]["asked_question_md"] = "## Questions"
        return _r("", "sess-1", "success")

    with _patch_worktree(tmp_path):
        with _fetch_comments_patch():
            with patch("autoswe.harness.runner.run", side_effect=fake_run):
                with patch("autoswe.harness.coder.commit_and_push", return_value=FAKE_COMMIT_RESULT):
                    from autoswe.harness.coder import run_fix
                    result = run_fix(task, cfg={})

    assert result.done_content.startswith("WAITING:")


def test_run_fix_records_last_phase_fix(tmp_path):
    """run_fix should set last_phase=fix on the task."""
    task = make_task()

    with _patch_worktree(tmp_path):
        with _fetch_comments_patch():
            with patch("autoswe.harness.runner.run", return_value=_r("Done.", "sess-1")):
                with patch("autoswe.harness.coder.commit_and_push", return_value=FAKE_COMMIT_RESULT):
                    from autoswe.harness.coder import run_fix
                    run_fix(task, cfg={})

    assert task.get("last_phase") == "fix"


def test_run_fix_ask_user_question_in_mode(tmp_path):
    """AskUserQuestion should be included in mode='read_write' tool set for fix phase."""
    task = make_task()
    run_calls = []

    def fake_run(prompt, **kwargs):
        run_calls.append(kwargs)
        return _r("Done.")

    with _patch_worktree(tmp_path):
        with _fetch_comments_patch():
            with patch("autoswe.harness.runner.run", side_effect=fake_run):
                with patch("autoswe.harness.coder.commit_and_push", return_value=FAKE_COMMIT_RESULT):
                    from autoswe.harness.coder import run_fix
                    run_fix(task, cfg={})

    assert run_calls[0]["mode"] == "read_write"
    from autoswe.harness.backends.claude_code import _MODE_CONFIG
    _perm, tools, _disallowed = _MODE_CONFIG["read_write"]
    assert "AskUserQuestion" in tools


def test_resume_fix_uses_mode_read_write(tmp_path):
    """resume_fix should use mode='read_write' with AGENT_TASK_TOOLS."""
    task = make_task(session_id="sess-previous")
    run_calls = []

    def fake_run(prompt, **kwargs):
        run_calls.append(kwargs)
        return _r("Done.", "sess-new")

    with _patch_worktree(tmp_path):
        with _fetch_comments_patch():
            with patch("autoswe.harness.runner.run", side_effect=fake_run):
                with patch("autoswe.harness.coder.commit_and_push", return_value=FAKE_COMMIT_RESULT):
                    from autoswe.harness.coder import resume_fix
                    resume_fix(task, "Answer to question.", {}, {})

    assert run_calls[0]["mode"] == "read_write"
    from autoswe.harness.backends.claude_code import _MODE_CONFIG
    _perm, tools, _disallowed = _MODE_CONFIG["read_write"]
    from autoswe.harness.runner import AGENT_TASK_TOOLS
    for tool in AGENT_TASK_TOOLS:
        assert tool in tools, f"{tool} should be in read_write mode tools"


def test_resolve_sync_conflicts_uses_mode_read_write(tmp_path):
    """resolve_sync_conflicts should use mode='read_write' with disallowed_tools_override=['AskUserQuestion']."""
    task = make_task()
    run_calls = []

    def fake_run(prompt, **kwargs):
        run_calls.append(kwargs)
        return _r("Resolved.", "s1", "success")

    with _patch_resolve(tmp_path):
        with patch("autoswe.harness.runner.run", side_effect=fake_run):
            with patch("autoswe.harness.coder.subprocess.run") as mock_run:
                mock_run.returncode = 0
                mock_run.stdout = "abc1234"
                from autoswe.harness.coder import resolve_sync_conflicts
                resolve_sync_conflicts(
                    task, ["src/main.py"], repo_cfg={"provider": "github"}, cfg={},
                )

    assert run_calls[0]["mode"] == "read_write"
    assert run_calls[0]["disallowed_tools_override"] == ["AskUserQuestion"]
    # Verify AGENT_TASK_TOOLS in read_write mode (minus AskUserQuestion)
    from autoswe.harness.backends.claude_code import _MODE_CONFIG
    _perm, tools, base_disallowed = _MODE_CONFIG["read_write"]
    from autoswe.harness.runner import AGENT_TASK_TOOLS
    for tool in AGENT_TASK_TOOLS:
        assert tool in tools, f"{tool} should be in read_write mode tools"


def test_resume_fix_resumes_session(tmp_path):
    """resume_fix should pass session_id to runner.resume."""
    task = make_task(session_id="sess-previous")
    run_calls = []

    def fake_run(prompt, **kwargs):
        run_calls.append(kwargs)
        return _r("Done.", "sess-new")

    with _patch_worktree(tmp_path):
        with _fetch_comments_patch():
            with patch("autoswe.harness.runner.run", side_effect=fake_run):
                with patch("autoswe.harness.coder.commit_and_push", return_value=FAKE_COMMIT_RESULT):
                    from autoswe.harness.coder import resume_fix
                    resume_fix(task, "Answer to question.", {}, {})

    assert run_calls[0]["resume"] == "sess-previous"


def test_resume_fix_ask_user_question_double_wait(tmp_path):
    """resume_fix can ask another question, returning WAITING again."""
    task = make_task(session_id="sess-previous")

    def fake_run(prompt, **kwargs):
        kwargs["state"]["asked_question_md"] = "## Questions"
        return _r("", "sess-1", "success")

    with _patch_worktree(tmp_path):
        with _fetch_comments_patch():
            with patch("autoswe.harness.runner.run", side_effect=fake_run):
                with patch("autoswe.harness.coder.commit_and_push", return_value=FAKE_COMMIT_RESULT):
                    from autoswe.harness.coder import resume_fix
                    result = resume_fix(task, "Answer.", {}, {})

    assert result.done_content.startswith("WAITING:")
    assert task.get("last_phase") == "fix"


def test_resume_fix_completes_on_success(tmp_path):
    """resume_fix should complete with DONE_SUMMARY on success."""
    task = make_task(session_id="sess-previous")

    with _patch_worktree(tmp_path):
        with _fetch_comments_patch():
            with patch("autoswe.harness.runner.run", return_value=_r("Applied changes.", "sess-new")):
                with patch("autoswe.harness.coder.commit_and_push", return_value=FAKE_COMMIT_RESULT):
                    from autoswe.harness.coder import resume_fix
                    result = resume_fix(task, "Answer to question.", {}, {})

    assert result.done_content.startswith("DONE_SUMMARY")


# ---------------------------------------------------------------------------
# MissingScopeError and LINK_BRANCH_TO_ISSUE


def test_run_fix_missing_scope_error_terse_log(tmp_path):
    """When link_branch_to_issue raises MissingScopeError, a single terse log line is emitted."""
    # Reset the module-level flag so the log fires for this test
    import autoswe.harness.coder as coder_mod
    coder_mod._scope_error_warned = False

    task = make_task()

    from autoswe.providers.github.vcs import MissingScopeError

    class FailingVCS:
        def link_branch_to_issue(self, issue_number, commit_sha, branch):
            raise MissingScopeError("PAT missing check_runs:write scope")

    with _patch_worktree(tmp_path):
        with _fetch_comments_patch():
            with patch("autoswe.harness.runner.run", return_value=_r("Done.", "sess")):
                with patch("autoswe.harness.coder.commit_and_push", return_value=FAKE_COMMIT_RESULT):
                    with patch("autoswe.harness.coder.get_vcs", return_value=FailingVCS()):
                        with patch("autoswe.harness.coder.log") as mock_log:
                            from autoswe.harness.coder import run_fix
                            result = run_fix(task, cfg={})

    assert result.done_content.startswith("DONE_SUMMARY\t")
    # Should have logged the terse scope error message
    log_calls = [c[0] for c in mock_log.call_args_list]
    assert any("check_runs:write" in str(c) for c in log_calls), \
        f"Should log terse scope error, got: {log_calls}"


def test_run_fix_link_branch_skipped_when_flag_false(tmp_path):
    """When LINK_BRANCH_TO_ISSUE=false, link_branch_to_issue is not called."""
    # Reset the module-level flag
    import autoswe.harness.coder as coder_mod
    coder_mod._scope_error_warned = False

    task = make_task()
    link_calls = []

    class FakeVCS:
        def link_branch_to_issue(self, issue_number, commit_sha, branch):
            link_calls.append((issue_number, commit_sha, branch))

    with _patch_worktree(tmp_path):
        with _fetch_comments_patch():
            with patch("autoswe.harness.runner.run", return_value=_r("Done.", "sess")):
                with patch("autoswe.harness.coder.commit_and_push", return_value=FAKE_COMMIT_RESULT):
                    with patch("autoswe.harness.coder.get_vcs", return_value=FakeVCS()):
                        from autoswe.harness.coder import run_fix
                        result = run_fix(task, cfg={"LINK_BRANCH_TO_ISSUE": False})

    assert result.done_content.startswith("DONE_SUMMARY\t")
    assert len(link_calls) == 0, "link_branch_to_issue should NOT be called when flag is false"


# ---------------------------------------------------------------------------
# resolve_sync_conflicts handler


def _patch_resolve(tmp_path):
    """Set up mocks for resolve_sync_conflicts testing."""
    stack = ExitStack()
    stack.enter_context(patch("autoswe.harness.coder.worktree_path", return_value=tmp_path))
    stack.enter_context(patch("autoswe.harness.coder.get_merge_conflict_files", return_value=[]))
    stack.enter_context(_fetch_comments_patch())
    return stack


def test_resolve_sync_conflicts_success_returns_done_summary(tmp_path):
    """On success with no remaining conflicts, return DONE_SUMMARY."""
    task = make_task(session_id="s1")
    task["plan_branch"] = "main"

    class _FakeSubprocResult:
        returncode = 0
        stdout = ""
        stderr = ""

    def _fake_subprocess_run(args, **kwargs):
        r = _FakeSubprocResult()
        if "rev-parse" in args:
            r.stdout = "abc1234"
        elif "log" in args:
            r.stdout = "abc1234 fix\n"
        return r

    with _patch_resolve(tmp_path):
        with patch("autoswe.harness.runner.run", return_value=_r("Resolved.", "s2", "success")):
            with patch("autoswe.harness.coder.subprocess.run", side_effect=_fake_subprocess_run):
                with patch("autoswe.harness.coder.get_vcs") as mock_vcs:
                    mock_vcs.return_value.branch_name.return_value = "autoswe/issue-42"
                    from autoswe.harness.coder import resolve_sync_conflicts
                    result = resolve_sync_conflicts(
                        task, ["src/main.py"], repo_cfg={"provider": "github"}, cfg={},
                    )

    assert result.done_content.startswith("DONE_SUMMARY\t")
    assert "Resolved merge conflicts" in result.done_content
    assert "abc1234" in result.done_content


def test_resolve_sync_conflicts_unresolved_returns_failed(tmp_path):
    """When Claude leaves conflict markers, return FAILED."""
    task = make_task()

    with _patch_resolve(tmp_path):
        # Override to return remaining conflicts
        with patch("autoswe.harness.coder.get_merge_conflict_files",
                   return_value=["src/main.py"]):
            with patch("autoswe.harness.runner.run",
                       return_value=_r("Resolved.", "s2", "success")):
                from autoswe.harness.coder import resolve_sync_conflicts
                result = resolve_sync_conflicts(
                    task, ["src/main.py"], repo_cfg={"provider": "github"}, cfg={},
                )

    assert result.done_content.startswith("FAILED:")
    assert "unresolved conflicts" in result.done_content


def test_resolve_sync_conflicts_subtype_error_returns_failed(tmp_path):
    """Non-success subtype from runner → FAILED."""
    task = make_task()

    with _patch_resolve(tmp_path):
        with patch("autoswe.harness.runner.run",
                   return_value=_r("", "s1", "error_max_turns")):
            from autoswe.harness.coder import resolve_sync_conflicts
            result = resolve_sync_conflicts(
                task, ["src/main.py"], repo_cfg={"provider": "github"}, cfg={},
            )

    assert result.done_content.startswith("FAILED:")
    assert "error_max_turns" in result.done_content


def test_resolve_sync_conflicts_seeds_plan_in_prompt(tmp_path):
    """When task has plan_file_path, plan text should be in the prompt."""
    plan_file = tmp_path / "plan.md"
    plan_file.write_text("PLAN BODY: do the thing")
    task = make_task()
    task["plan_file_path"] = str(plan_file)
    run_calls = []

    def fake_run(prompt, **kwargs):
        run_calls.append(prompt)
        return _r("Resolved.", "s1", "success")

    with _patch_resolve(tmp_path):
        with patch("autoswe.harness.runner.run", side_effect=fake_run):
            with patch("autoswe.harness.coder.subprocess.run") as mock_run:
                mock_run.returncode = 0
                mock_run.stdout = "abc1234"
                from autoswe.harness.coder import resolve_sync_conflicts
                resolve_sync_conflicts(
                    task, ["src/main.py"], repo_cfg={"provider": "github"}, cfg={},
                )

    assert "PLAN BODY: do the thing" in run_calls[0]
    assert "active plan" in run_calls[0]


def test_resolve_sync_conflicts_does_not_pop_plan_file_path(tmp_path):
    """plan_file_path must persist after resolution (contrast with run_fix which pops it)."""
    plan_file = tmp_path / "plan.md"
    plan_file.write_text("PLAN BODY")
    task = make_task()
    task["plan_file_path"] = str(plan_file)

    with _patch_resolve(tmp_path):
        with patch("autoswe.harness.runner.run", return_value=_r("Resolved.", "s1", "success")):
            with patch("autoswe.harness.coder.subprocess.run") as mock_run:
                mock_run.returncode = 0
                mock_run.stdout = "abc1234"
                from autoswe.harness.coder import resolve_sync_conflicts
                resolve_sync_conflicts(
                    task, ["src/main.py"], repo_cfg={"provider": "github"}, cfg={},
                )

    assert "plan_file_path" in task
    assert task["plan_file_path"] == str(plan_file)


def test_resolve_sync_conflicts_resumes_session_when_present(tmp_path):
    """When task has session_id, runner.run should be called with resume=session_id."""
    task = make_task(session_id="s-prev")
    run_calls = []

    def fake_run(prompt, **kwargs):
        run_calls.append(kwargs)
        return _r("Resolved.", "s-new", "success")

    with _patch_resolve(tmp_path):
        with patch("autoswe.harness.runner.run", side_effect=fake_run):
            with patch("autoswe.harness.coder.subprocess.run") as mock_run:
                mock_run.returncode = 0
                mock_run.stdout = "abc1234"
                from autoswe.harness.coder import resolve_sync_conflicts
                resolve_sync_conflicts(
                    task, ["src/main.py"], repo_cfg={"provider": "github"}, cfg={},
                )

    assert run_calls[0]["resume"] == "s-prev"


def test_resolve_sync_conflicts_starts_fresh_when_no_session(tmp_path):
    """When task has no session_id, resume=None."""
    task = make_task(session_id=None)
    run_calls = []

    def fake_run(prompt, **kwargs):
        run_calls.append(kwargs)
        return _r("Resolved.", "s-new", "success")

    with _patch_resolve(tmp_path):
        with patch("autoswe.harness.runner.run", side_effect=fake_run):
            with patch("autoswe.harness.coder.subprocess.run") as mock_run:
                mock_run.returncode = 0
                mock_run.stdout = "abc1234"
                from autoswe.harness.coder import resolve_sync_conflicts
                resolve_sync_conflicts(
                    task, ["src/main.py"], repo_cfg={"provider": "github"}, cfg={},
                )

    assert run_calls[0]["resume"] is None


def test_resolve_sync_conflicts_missing_worktree_returns_failed(tmp_path):
    """When worktree path doesn't exist, return FAILED."""
    task = make_task()
    fake_missing = tmp_path / "nonexistent"

    with patch("autoswe.harness.coder.worktree_path", return_value=fake_missing):
        from autoswe.harness.coder import resolve_sync_conflicts
        result = resolve_sync_conflicts(
            task, ["src/main.py"], repo_cfg={"provider": "github"}, cfg={},
        )

    assert result.done_content.startswith("FAILED:")
    assert "worktree missing" in result.done_content


def test_resolve_sync_conflicts_no_ask_user_question(tmp_path):
    """resolve_sync_conflicts should use disallowed_tools_override=['AskUserQuestion'] to exclude it."""
    task = make_task()
    run_calls = []

    def fake_run(prompt, **kwargs):
        run_calls.append(kwargs)
        return _r("Resolved.", "s1", "success")

    with _patch_resolve(tmp_path):
        with patch("autoswe.harness.runner.run", side_effect=fake_run):
            with patch("autoswe.harness.coder.subprocess.run") as mock_run:
                mock_run.returncode = 0
                mock_run.stdout = "abc1234"
                from autoswe.harness.coder import resolve_sync_conflicts
                resolve_sync_conflicts(
                    task, ["src/main.py"], repo_cfg={"provider": "github"}, cfg={},
                )

    assert run_calls[0]["mode"] == "read_write"
    disallowed_override = run_calls[0].get("disallowed_tools_override", [])
    assert "AskUserQuestion" in disallowed_override
    # The backend will remove AskUserQuestion from read_write tools
    from autoswe.harness.backends.claude_code import _MODE_CONFIG
    _perm, tools, _base_disallowed = _MODE_CONFIG["read_write"]
    effective = [t for t in tools if t not in disallowed_override]
    assert "AskUserQuestion" not in effective
    assert "Edit" in effective
    assert "Bash" in effective


def test_resolve_sync_conflicts_push_failure_returns_failed(tmp_path):
    """When push after resolution fails, return FAILED."""
    task = make_task()
    import subprocess as sub

    with _patch_resolve(tmp_path):
        with patch("autoswe.harness.runner.run", return_value=_r("Resolved.", "s1", "success")):
            with patch("autoswe.harness.coder.subprocess.run",
                       side_effect=sub.SubprocessError("push failed")):
                from autoswe.harness.coder import resolve_sync_conflicts
                result = resolve_sync_conflicts(
                    task, ["src/main.py"], repo_cfg={"provider": "github"}, cfg={},
                )

    assert result.done_content.startswith("FAILED:")
    assert "push after resolution failed" in result.done_content


def test_resolve_sync_conflicts_persists_session_id(tmp_path):
    """Resolver should persist the session_id from runner.run result."""
    task = make_task(session_id="s-prev")

    with _patch_resolve(tmp_path):
        with patch("autoswe.harness.runner.run", return_value=_r("Resolved.", "s-new", "success")):
            with patch("autoswe.harness.coder.subprocess.run") as mock_run:
                mock_run.returncode = 0
                mock_run.stdout = "abc1234"
                from autoswe.harness.coder import resolve_sync_conflicts
                resolve_sync_conflicts(
                    task, ["src/main.py"], repo_cfg={"provider": "github"}, cfg={},
                )

    assert task["session_id"] == "s-new"


def test_resolve_sync_conflicts_passes_harness_model(tmp_path):
    """resolve_sync_conflicts must forward the model from the harness profile.

    Regression: the harness was resolved but the model was never passed to
    runner.run, so conflict resolution silently used the wrong model.
    """
    task = make_task(session_id="s1")
    captured = {}

    def _capture_run(prompt, **kw):
        captured["model"] = kw.get("model")
        from autoswe.harness.backends.base import RunResult
        return RunResult(text="ok", session_id="s-new", subtype="success")

    with _patch_resolve(tmp_path):
        with patch("autoswe.harness.runner.run", side_effect=_capture_run):
            with patch("autoswe.harness.coder.subprocess.run") as mock_run:
                mock_run.returncode = 0
                mock_run.stdout = "abc1234"
            with patch("autoswe.harness.coder.get_vcs") as mock_vcs:
                mock_vcs.return_value.branch_name.return_value = "autoswe/issue-42"
                from autoswe.harness.coder import resolve_sync_conflicts
                resolve_sync_conflicts(
                    task, ["src/main.py"],
                    repo_cfg={"provider": "github", "fix_model": "repo-model"},
                    cfg={"FIX_MODEL": "global-model"},
                )

    # Harness profile model (via resolve_harness) should be forwarded.
    # The synthesized default picks repo_cfg fix_model > cfg FIX_MODEL > None.
    assert captured["model"] == "repo-model"


# ---------------------------------------------------------------------------
# Codex backend — success path (no MCP)


def test_run_fix_codex_done_summary(tmp_path):
    """When harness_cfg uses Codex backend (no MCP), a successful fix run
    with summary text → DONE_SUMMARY."""
    task = make_task()

    with _patch_worktree(tmp_path):
        with _fetch_comments_patch():
            # Codex backend returns subtype="success" + summary text
            with patch("autoswe.harness.runner.run", return_value=_r("Changed 2 files.", "sess-codex", "success")):
                with patch("autoswe.harness.coder.commit_and_push", return_value=FAKE_COMMIT_RESULT):
                    from autoswe.harness.coder import run_fix
                    result = run_fix(task, cfg={})

    assert result.done_content.startswith("DONE_SUMMARY\t")
    assert "Changed 2 files." in result.done_content
    assert task["session_id"] == "sess-codex"
