"""Tests for autoswe.harness.coder handler return values."""

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
# Fork-on-retry session source (issue #173 F-15)
# ---------------------------------------------------------------------------


def test_run_fix_fork_resumes_gate_validated_id(tmp_path):
    """The retry gate and the SDK must resume the same session id.

    When the FAILED path left session_id set to a *different* value than the
    checkpoint the retry gate validated (last_good_session_id), run_fix must
    hand the gate-validated id (fork_session_id) to the SDK, not session_id.
    """
    from autoswe.harness.coder import run_fix

    captured = {}

    def fake_run(prompt, **kwargs):
        captured.update(kwargs)
        return _r("DONE: no changes detected", session_id="s-new")

    task = make_task(session_id="s-stale-session")
    task["last_good_session_id"] = "s-checkpoint"

    stack = _patch_worktree(tmp_path)
    stack.enter_context(patch("autoswe.vcs.worktree.get_merge_conflict_files", return_value=[]))
    stack.enter_context(patch("autoswe.vcs.worktree.get_vcs", return_value=_fake_vcs()))
    stack.enter_context(patch("autoswe.harness.runner.run", side_effect=fake_run))
    stack.enter_context(patch("autoswe.harness.coder._finalize_fix", return_value=_r("DONE: no changes detected", "s-new")))
    try:
        run_fix(task, None, {"provider": "github"}, {},
                wt=tmp_path, fork_session=True, fork_session_id="s-checkpoint")
    finally:
        stack.close()

    assert captured["resume"] == "s-checkpoint", (
        f"run_fix must resume the gate-validated checkpoint, got {captured['resume']!r}"
    )
    assert captured["fork_session"] is True


def test_run_fix_fork_without_id_falls_back_to_last_good(tmp_path):
    """A caller that sets fork_session but not fork_session_id still resumes
    the last_good_session_id (backward-compatible path)."""
    from autoswe.harness.coder import run_fix

    captured = {}

    def fake_run(prompt, **kwargs):
        captured.update(kwargs)
        return _r("DONE: no changes detected", session_id="s-new")

    task = make_task(session_id=None)
    task["last_good_session_id"] = "s-checkpoint"

    stack = _patch_worktree(tmp_path)
    stack.enter_context(patch("autoswe.vcs.worktree.get_merge_conflict_files", return_value=[]))
    stack.enter_context(patch("autoswe.vcs.worktree.get_vcs", return_value=_fake_vcs()))
    stack.enter_context(patch("autoswe.harness.runner.run", side_effect=fake_run))
    stack.enter_context(patch("autoswe.harness.coder._finalize_fix", return_value=_r("DONE: no changes detected", "s-new")))
    try:
        run_fix(task, None, {"provider": "github"}, {},
                wt=tmp_path, fork_session=True)
    finally:
        stack.close()

    assert captured["resume"] == "s-checkpoint"


def _fake_vcs():
    from unittest.mock import MagicMock
    m = MagicMock()
    m.find_existing_pr.return_value = None
    return m


# ---------------------------------------------------------------------------
# Backend awareness (harness_cfg threading)


def test_run_fix_passes_harness_cfg(tmp_path):
    """run_fix must resolve harness and pass harness_cfg to runner.run."""
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

    assert len(run_calls) == 1
    harness_cfg = run_calls[0].get("harness_cfg")
    assert harness_cfg is not None, "harness_cfg should be passed to runner.run"
    assert harness_cfg.get("backend") == "claude_code", \
        f"Default backend should be claude_code, got {harness_cfg.get('backend')!r}"


def test_resume_fix_passes_harness_cfg(tmp_path):
    """resume_fix must resolve harness and pass harness_cfg to runner.run."""
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

    assert len(run_calls) == 1
    harness_cfg = run_calls[0].get("harness_cfg")
    assert harness_cfg is not None, "harness_cfg should be passed to runner.run"
    assert harness_cfg.get("backend") == "claude_code"


def _patch_resolve(tmp_path):
    """Set up mocks for resolve_sync_conflicts testing."""
    stack = ExitStack()
    stack.enter_context(patch("autoswe.harness.coder.worktree_path", return_value=tmp_path))
    stack.enter_context(patch("autoswe.harness.coder.get_merge_conflict_files", return_value=[]))
    stack.enter_context(_fetch_comments_patch())
    return stack


def test_resolve_sync_conflicts_passes_harness_cfg(tmp_path):
    """resolve_sync_conflicts must resolve harness and pass harness_cfg to runner.run."""
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

    assert len(run_calls) == 1
    harness_cfg = run_calls[0].get("harness_cfg")
    assert harness_cfg is not None, "harness_cfg should be passed to runner.run"
    assert harness_cfg.get("backend") == "claude_code"


def test_run_fix_appends_merge_conflict_block_when_worktree_conflicted(tmp_path):
    """run_fix appends the '## Merge conflicts to resolve first' block when the
    pre-synced worktree already contains conflict markers.

    Verifies the end-to-end path: _sync_before_dispatch (resolve_conflicts=False)
    leaves the worktree conflicted, then run_fix picks it up via get_merge_conflict_files.
    """
    task = make_task()
    prompts_seen = []

    def fake_run(prompt, **kwargs):
        prompts_seen.append(prompt)
        return _r("Done.")

    with ExitStack() as stack:
        stack.enter_context(patch("autoswe.harness.coder.create_worktree", return_value=tmp_path))
        stack.enter_context(patch("autoswe.harness.coder.fast_forward_worktree", return_value=True))
        stack.enter_context(_fetch_comments_patch())
        stack.enter_context(patch("autoswe.harness.runner.run", side_effect=fake_run))
        stack.enter_context(patch("autoswe.harness.coder.commit_and_push", return_value=FAKE_COMMIT_RESULT))
        # Simulate the worktree having conflict markers (as left by sync_before_dispatch)
        stack.enter_context(
            patch("autoswe.harness.coder.get_merge_conflict_files", return_value=["src/main.py"])
        )
        from autoswe.harness.coder import run_fix
        run_fix(task, cfg={})

    assert len(prompts_seen) == 1
    prompt = prompts_seen[0]
    assert "## Merge conflicts to resolve first" in prompt, \
        "run_fix must include the merge-conflict block when conflict files are present"
    assert "src/main.py" in prompt


def test_run_fix_codex_harness_cfg(tmp_path):
    """When FIX_HARNESS selects a codex profile, harness_cfg should reflect codex backend."""
    task = make_task()
    run_calls = []

    def fake_run(prompt, **kwargs):
        run_calls.append(kwargs)
        return _r("Done.")

    with _patch_worktree(tmp_path):
        with _fetch_comments_patch():
            with patch("autoswe.harness.runner.run", side_effect=fake_run):
                with patch("autoswe.harness.coder.commit_and_push", return_value=FAKE_COMMIT_RESULT):
                    with patch("autoswe.core.config.load_harnesses_config",
                               return_value={"codex-fix": {"backend": "codex", "model": "gpt-5.6-terra"}}):
                        from autoswe.harness.coder import run_fix
                        run_fix(task, cfg={"FIX_HARNESS": "codex-fix"})

    assert len(run_calls) == 1
    harness_cfg = run_calls[0].get("harness_cfg")
    assert harness_cfg is not None
    assert harness_cfg.get("backend") == "codex"
    assert harness_cfg.get("model") == "gpt-5.6-terra"
