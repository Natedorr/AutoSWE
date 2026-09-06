"""Tests for autoswe.harness.coder handler return values."""

from contextlib import ExitStack
from unittest.mock import patch

from autoswe.harness.runner import RunResult
from autoswe.harness.test_gate import GateResult


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
# F-10: handler no longer re-builds the base tool list / keys off normalized ok
# ---------------------------------------------------------------------------


def test_run_fix_passes_extra_tools_not_allowed_tools(tmp_path):
    """run_fix passes extra_tools (a list) and never the legacy allowed_tools.

    S6 / issue #169 F-10: the base read-write tool set comes from
    mode="read_write"; the handler forwards only genuinely-extra tools.
    """
    from autoswe.harness.coder import run_fix

    captured = {}

    def fake_run(prompt, **kwargs):
        captured.update(kwargs)
        return _r("DONE: no changes detected")

    stack = _patch_worktree(tmp_path)
    stack.enter_context(patch("autoswe.vcs.worktree.get_merge_conflict_files", return_value=[]))
    stack.enter_context(patch("autoswe.vcs.worktree.get_vcs", return_value=_fake_vcs()))
    stack.enter_context(patch("autoswe.harness.runner.run", side_effect=fake_run))
    stack.enter_context(patch("autoswe.harness.coder._finalize_fix", return_value=_r("DONE: no changes detected")))
    try:
        run_fix(make_task(), cfg={})
    finally:
        stack.close()

    assert "extra_tools" in captured, "run_fix must forward extra_tools to runner.run"
    assert isinstance(captured["extra_tools"], list)
    assert "allowed_tools" not in captured, (
        "run_fix must not re-build a base tool list as allowed_tools"
    )
    assert captured["mode"] == "read_write"


def test_run_fix_success_gate_uses_normalized_ok(tmp_path):
    """The success gate keys off RunResult.ok, not a literal subtype string.

    S6 / issue #169 F-10: ``_run_fix_session`` returns FAILED when
    ``not run_result.ok`` — so a result with ok=False must fail even when the
    subtype is a value that used to be compared to the literal "success".
    """
    from autoswe.harness.coder import run_fix

    # Subtype that is NOT "success" but ok=True → must proceed to finalize.
    finalize_calls = []

    def fake_run(prompt, **kwargs):
        return RunResult("done", "s1", "custom_ok", ok=True)

    def fake_finalize(*a, **k):
        finalize_calls.append(1)
        return "DONE: no changes detected"

    stack = _patch_worktree(tmp_path)
    stack.enter_context(_fetch_comments_patch())
    stack.enter_context(patch("autoswe.vcs.worktree.get_merge_conflict_files", return_value=[]))
    stack.enter_context(patch("autoswe.vcs.worktree.get_vcs", return_value=_fake_vcs()))
    stack.enter_context(patch("autoswe.harness.runner.run", side_effect=fake_run))
    stack.enter_context(patch("autoswe.harness.coder._finalize_fix", side_effect=fake_finalize))
    try:
        res = run_fix(make_task(), cfg={})
    finally:
        stack.close()

    content = res.done_content if hasattr(res, "done_content") else str(res)
    assert not content.startswith("FAILED"), f"ok=True must not be treated as failure: {content}"
    assert finalize_calls, "ok=True result must reach _finalize_fix"


def test_run_fix_ok_false_is_failed_even_if_subtype_says_success(tmp_path):
    """A result with ok=False is FAILED even if subtype reads like success."""
    from autoswe.harness.coder import run_fix

    def fake_run(prompt, **kwargs):
        return RunResult("looks fine", "s1", "success", ok=False)

    finalize_calls = []

    def fake_finalize(*a, **k):
        finalize_calls.append(1)
        return _r("DONE: no changes detected")

    stack = _patch_worktree(tmp_path)
    stack.enter_context(_fetch_comments_patch())
    stack.enter_context(patch("autoswe.vcs.worktree.get_merge_conflict_files", return_value=[]))
    stack.enter_context(patch("autoswe.vcs.worktree.get_vcs", return_value=_fake_vcs()))
    stack.enter_context(patch("autoswe.harness.runner.run", side_effect=fake_run))
    stack.enter_context(patch("autoswe.harness.coder._finalize_fix", side_effect=fake_finalize))
    try:
        res = run_fix(make_task(), cfg={})
    finally:
        stack.close()

    content = res.done_content if hasattr(res, "done_content") else str(res)
    assert content.startswith("FAILED"), f"ok=False must be FAILED, got: {content}"
    assert not finalize_calls, "ok=False must not reach _finalize_fix"


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


# ---------------------------------------------------------------------------
# Post-fix test gate (Natedorr/testProject#20): a red suite must never be
# marked terminal `fixed`. _finalize_fix runs the gate after commit/push and
# returns TESTS_FAILED when it is red, so the state machine lands in the
# non-terminal `test_failed` state.
# ---------------------------------------------------------------------------


def _finalize(task, tmp_path, gate):
    from autoswe.harness import coder
    with patch("autoswe.harness.coder.commit_and_push", return_value=FAKE_COMMIT_RESULT):
        with patch("autoswe.harness.coder.run_test_gate", return_value=gate) as mock_gate:
            hr = coder._finalize_fix(
                task, _r("Done."), tmp_path, "o", "r", 1, "master", "github", "tok",
                {}, {}, session_id="sess",
            )
    return hr, mock_gate


def test_finalize_fix_red_suite_returns_tests_failed(tmp_path):
    task = make_task()
    gate = GateResult(ok=False, ran=True, reason="suite failing (exit 1)",
                      output="assert 5.0 == 6.0", command="pytest", duration_seconds=1.0)
    hr, mock_gate = _finalize(task, tmp_path, gate)
    assert hr.done_content.startswith("TESTS_FAILED\t")
    assert "suite failing (exit 1)" in hr.done_content
    assert "assert 5.0 == 6.0" in hr.done_content
    # The committed sha is preserved after the last tab.
    assert hr.done_content.rstrip().endswith("abc1234")
    assert hr.session_id == "sess"
    mock_gate.assert_called_once()


def test_finalize_fix_green_suite_returns_done_summary(tmp_path):
    task = make_task()
    gate = GateResult(ok=True, ran=True, reason="suite green", command="pytest")
    hr, _ = _finalize(task, tmp_path, gate)
    assert hr.done_content.startswith("DONE_SUMMARY\t")
    assert hr.done_content.rstrip().endswith("abc1234")


def test_finalize_fix_skipped_gate_returns_done_summary(tmp_path):
    task = make_task()
    gate = GateResult(ok=True, ran=False, reason="no test suite detected")
    hr, _ = _finalize(task, tmp_path, gate)
    assert hr.done_content.startswith("DONE_SUMMARY\t")


def test_finalize_fix_no_changes_skips_gate(tmp_path):
    task = make_task()
    from autoswe.harness import coder
    with patch("autoswe.harness.coder.commit_and_push", return_value=NO_CHANGES_RESULT):
        with patch("autoswe.harness.coder.run_test_gate") as mock_gate:
            hr = coder._finalize_fix(
                task, _r("Done."), tmp_path, "o", "r", 1, "master", "github", "tok",
                {}, {}, session_id="sess",
            )
    assert hr.done_content == "DONE: no changes detected"
    mock_gate.assert_not_called()
