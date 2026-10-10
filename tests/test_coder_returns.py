"""Tests for autoswe.harness.coder handler return values."""

import subprocess
from contextlib import ExitStack
from unittest.mock import patch

from autoswe.harness.runner import HandlerResult, RunResult
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


def _finalize_no_changes(task, tmp_path, gate, head_sha="0123456789abcdef0123456789abcdef01234567"):
    """Run _finalize_fix with commit_and_push reporting NO changes.

    The branch head is stubbed via _get_branch_head_sha (the real
    commit_and_push returns no sha on the no-changes path). Returns
    (HandlerResult, mock_gate).
    """
    from autoswe.harness import coder
    with patch("autoswe.harness.coder.commit_and_push", return_value=NO_CHANGES_RESULT):
        with patch("autoswe.harness.coder._get_branch_head_sha", return_value=head_sha):
            with patch("autoswe.harness.coder.run_test_gate", return_value=gate) as mock_gate:
                hr = coder._finalize_fix(
                    task, _r("Done."), tmp_path, "o", "r", 1, "master", "github", "tok",
                    {}, {}, session_id="sess",
                )
    return hr, mock_gate


def test_finalize_fix_no_changes_red_suite_returns_tests_failed(tmp_path):
    """Issue #276: no-changes + red gate must re-land test_failed, not fixed.

    A gate auto-fix that correctly declines to change an already-committed
    fix (fixture-driven red suite) must NOT be promoted out of test_failed —
    _finalize_fix runs the gate on the existing branch head and returns
    TESTS_FAILED with the head sha when it is red.
    """
    task = make_task()
    gate = GateResult(ok=False, ran=True, reason="suite failing (exit 1)",
                      output="assert flag == 'green'", command="pytest", duration_seconds=1.0)
    hr, mock_gate = _finalize_no_changes(task, tmp_path, gate)
    assert hr.done_content.startswith("TESTS_FAILED\t")
    assert "suite failing (exit 1)" in hr.done_content
    assert "assert flag == 'green'" in hr.done_content
    # The branch head is preserved after the last tab.
    assert hr.done_content.rstrip().endswith("0123456789abcdef0123456789abcdef01234567")
    assert hr.session_id == "sess"
    mock_gate.assert_called_once()


def test_finalize_fix_no_changes_green_suite_returns_no_changes_done(tmp_path):
    """No changes + green gate: the fix completes as a no-op (E2E-05)."""
    task = make_task()
    gate = GateResult(ok=True, ran=True, reason="suite green", command="pytest")
    hr, mock_gate = _finalize_no_changes(task, tmp_path, gate)
    assert hr.done_content == "DONE: no changes detected"
    mock_gate.assert_called_once()


def test_finalize_fix_no_changes_skipped_gate_returns_no_changes_done(tmp_path):
    """No changes + skipped (non-gating) gate: the fix completes as a no-op."""
    task = make_task()
    gate = GateResult(ok=True, ran=False, reason="no test suite detected")
    hr, mock_gate = _finalize_no_changes(task, tmp_path, gate)
    assert hr.done_content == "DONE: no changes detected"
    mock_gate.assert_called_once()


def test_finalize_fix_no_changes_red_suite_null_head_sha(tmp_path):
    """No changes + red gate + unresolvable head sha: still TESTS_FAILED.

    _get_branch_head_sha is best-effort — a None head must not raise; the
    sha slot is empty (emit's test_failed branch tolerates a missing sha).
    """
    task = make_task()
    gate = GateResult(ok=False, ran=True, reason="suite failing (exit 1)", command="pytest")
    hr, _ = _finalize_no_changes(task, tmp_path, gate, head_sha=None)
    assert hr.done_content.startswith("TESTS_FAILED\t")
    assert hr.done_content.endswith("\t")


def test_finalize_fix_run_gate_false_skips_gate(tmp_path):
    """run_gate=False (the rescue path) suppresses the post-commit gate re-run."""
    task = make_task()
    from autoswe.harness import coder
    with patch("autoswe.harness.coder.commit_and_push", return_value=FAKE_COMMIT_RESULT):
        with patch("autoswe.harness.coder.run_test_gate") as mock_gate:
            hr = coder._finalize_fix(
                task, _r("Done."), tmp_path, "o", "r", 1, "master", "github", "tok",
                {}, {}, session_id="sess", run_gate=False,
            )
    assert hr.done_content.startswith("DONE_SUMMARY\t")
    mock_gate.assert_not_called()


# ---------------------------------------------------------------------------
# Issue #222: configurable max_turns threading + error_max_turns rescue
# ---------------------------------------------------------------------------


def test_run_fix_threads_resolved_max_turns(tmp_path):
    """run_fix must hand the resolved max_turns to runner.run (default 200 unset)."""
    from autoswe.harness.coder import run_fix

    captured = {}

    def fake_run(prompt, **kwargs):
        captured.update(kwargs)
        return _r("DONE: no changes detected", session_id="s-new")

    task = make_task()
    stack = _patch_worktree(tmp_path)
    stack.enter_context(_fetch_comments_patch())
    stack.enter_context(patch("autoswe.vcs.worktree.get_merge_conflict_files", return_value=[]))
    stack.enter_context(patch("autoswe.vcs.worktree.get_vcs", return_value=_fake_vcs()))
    stack.enter_context(patch("autoswe.harness.runner.run", side_effect=fake_run))
    stack.enter_context(patch("autoswe.harness.coder._finalize_fix", return_value=_r("done", "s-new")))
    try:
        run_fix(task, None, {"provider": "github"}, {}, wt=tmp_path)
    finally:
        stack.close()

    assert "max_turns" in captured, "run_fix must forward a resolved max_turns"
    assert captured["max_turns"] == 200, f"unconfigured default must be 200, got {captured['max_turns']!r}"


def test_run_fix_threads_profile_max_turns(tmp_path):
    """A harness profile's max_turns must reach runner.run."""
    from autoswe.harness.coder import run_fix

    captured = {}

    def fake_run(prompt, **kwargs):
        captured.update(kwargs)
        return _r("DONE: no changes detected", session_id="s-new")

    task = make_task()
    stack = _patch_worktree(tmp_path)
    stack.enter_context(_fetch_comments_patch())
    stack.enter_context(patch("autoswe.vcs.worktree.get_merge_conflict_files", return_value=[]))
    stack.enter_context(patch("autoswe.vcs.worktree.get_vcs", return_value=_fake_vcs()))
    stack.enter_context(patch("autoswe.harness.runner.run", side_effect=fake_run))
    stack.enter_context(
        patch("autoswe.harness.coder._finalize_fix", return_value=_r("done", "s-new"))
    )
    stack.enter_context(
        patch(
            "autoswe.core.config.load_harnesses_config",
            return_value={"big-fix": {"backend": "claude_code", "model": "m", "max_turns": 500}},
        )
    )
    try:
        run_fix(task, None, {"provider": "github"}, {"FIX_HARNESS": "big-fix"}, wt=tmp_path)
    finally:
        stack.close()

    assert captured.get("max_turns") == 500, f"profile cap must win, got {captured.get('max_turns')!r}"


def test_run_fix_threads_per_repo_max_turns(tmp_path):
    """A per-repo agent_max_turns must reach runner.run."""
    from autoswe.harness.coder import run_fix

    captured = {}

    def fake_run(prompt, **kwargs):
        captured.update(kwargs)
        return _r("DONE: no changes detected", session_id="s-new")

    task = make_task()
    stack = _patch_worktree(tmp_path)
    stack.enter_context(_fetch_comments_patch())
    stack.enter_context(patch("autoswe.vcs.worktree.get_merge_conflict_files", return_value=[]))
    stack.enter_context(patch("autoswe.vcs.worktree.get_vcs", return_value=_fake_vcs()))
    stack.enter_context(patch("autoswe.harness.runner.run", side_effect=fake_run))
    stack.enter_context(
        patch("autoswe.harness.coder._finalize_fix", return_value=_r("done", "s-new"))
    )
    try:
        run_fix(task, None, {"provider": "github", "agent_max_turns": 321}, {}, wt=tmp_path)
    finally:
        stack.close()

    assert captured.get("max_turns") == 321, f"per-repo cap must reach the runner, got {captured.get('max_turns')!r}"


def _max_turns_rescue_stack(tmp_path, has_work, gate):
    """Shared patch stack for the error_max_turns rescue tests.

    Drives run_fix to a failed run_result (subtype=error_max_turns, ok=False),
    then lets _try_max_turns_rescue make the call: _worktree_has_committable_work
    and run_test_gate are stubbed per the scenario, and the real _finalize_fix is
    exercised (commit_and_push patched). Returns ``(stack, run_result, gate_mock)``:
    the shared ``run_test_gate`` patch lets a test assert how many times the
    gate was actually invoked (rescue runs it once; ``run_gate=False`` must
    prevent ``_finalize_fix`` from running it a second time).
    """
    run_result = RunResult(
        "reached the turn limit", session_id="s-cap", subtype="error_max_turns",
    )

    def fake_run(prompt, **kwargs):
        return run_result

    stack = _patch_worktree(tmp_path)
    stack.enter_context(_fetch_comments_patch())
    stack.enter_context(patch("autoswe.vcs.worktree.get_merge_conflict_files", return_value=[]))
    stack.enter_context(patch("autoswe.vcs.worktree.get_vcs", return_value=_fake_vcs()))
    stack.enter_context(patch("autoswe.harness.runner.run", side_effect=fake_run))
    stack.enter_context(
        patch("autoswe.harness.coder._worktree_has_committable_work", return_value=has_work)
    )
    gate_mock = stack.enter_context(
        patch("autoswe.harness.coder.run_test_gate", return_value=gate)
    )
    return stack, run_result, gate_mock


def test_max_turns_rescue_commits_when_diff_and_gate_green(tmp_path):
    """error_max_turns + committable work + green gate → commits and reaches fixed.

    The rescue must commit through the normal finalize path (DONE_SUMMARY, not
    FAILED) and not re-run the gate it just ran (the gate is invoked exactly
    once — by the rescue pre-check — not a second time by _finalize_fix).
    """
    from autoswe.harness.coder import run_fix

    gate = GateResult(ok=True, ran=True, reason="suite green", command="pytest")
    stack, _, gate_mock = _max_turns_rescue_stack(tmp_path, has_work=True, gate=gate)

    with stack:
        with patch("autoswe.harness.coder.commit_and_push",
                   return_value=FAKE_COMMIT_RESULT) as mock_commit:
            res = run_fix(make_task(), None, {"provider": "github"}, {}, wt=tmp_path)

    assert not res.done_content.startswith("FAILED"), f"rescue must not fail: {res.done_content}"
    assert res.done_content.startswith("DONE_SUMMARY\t"), f"rescue must finalize: {res.done_content}"
    mock_commit.assert_called_once(), "rescue must commit the partial run"
    # The rescue pre-check ran the gate exactly once; _finalize_fix(run_gate=False)
    # must not run it a second time.
    gate_mock.assert_called_once()


def test_max_turns_rescue_refuses_red_gate(tmp_path):
    """error_max_turns + committable work + RED gate → fails as usual, no commit.

    A red suite must never be committed as `fixed` — even when the agent ran out
    of turns after producing a diff.
    """
    from autoswe.harness.coder import run_fix

    gate = GateResult(ok=False, ran=True, reason="suite failing (exit 1)",
                      output="assert 5.0 == 6.0", command="pytest")
    stack, _, gate_mock = _max_turns_rescue_stack(tmp_path, has_work=True, gate=gate)
    with stack:
        with patch("autoswe.harness.coder.commit_and_push",
                   return_value=FAKE_COMMIT_RESULT) as mock_commit:
            res = run_fix(make_task(), None, {"provider": "github"}, {}, wt=tmp_path)

    assert res.done_content.startswith("FAILED"), f"red gate must fail: {res.done_content}"
    assert "error_max_turns" in res.done_content
    mock_commit.assert_not_called()
    gate_mock.assert_called_once()


def test_max_turns_rescue_refuses_when_no_work(tmp_path):
    """error_max_turns with an empty worktree → normal FAILED, no gate, no commit.

    The cap hit with nothing to ship: the committable-work check short-circuits
    before the gate ever runs.
    """
    from autoswe.harness.coder import run_fix

    gate = GateResult(ok=True, ran=True, reason="suite green", command="pytest")
    stack, _, gate_mock = _max_turns_rescue_stack(tmp_path, has_work=False, gate=gate)
    with stack:
        with patch("autoswe.harness.coder.commit_and_push",
                   return_value=FAKE_COMMIT_RESULT) as mock_commit:
            res = run_fix(make_task(), None, {"provider": "github"}, {}, wt=tmp_path)

    assert res.done_content.startswith("FAILED"), f"no work must fail: {res.done_content}"
    assert "error_max_turns" in res.done_content
    mock_commit.assert_not_called()
    gate_mock.assert_not_called()


def test_worktree_has_committable_work_degrades_on_git_failure(tmp_path):
    """The committable-work probe must never raise — a git failure means "no".

    The rescue only commits when work is present; a git timeout / ref error
    (large worktree, missing origin ref) must degrade to False rather than
    propagate out of the rescue and take the dispatch down.
    """
    from autoswe.harness import coder

    with patch("autoswe.harness.coder.subprocess.run",
               side_effect=subprocess.TimeoutExpired("git status", 10)):
        assert coder._worktree_has_committable_work(tmp_path, "autoswe/issue-1") is False


def test_worktree_has_committable_work_true_on_dirty_status(tmp_path):
    """Uncommitted changes in the worktree are committable work."""
    from autoswe.harness import coder

    def fake_run(args, **kwargs):
        import subprocess as sp
        if "status" in args:
            return sp.CompletedProcess(args, 0, stdout="M  src/main.py\n", stderr="")
        return sp.CompletedProcess(args, 0, stdout="", stderr="")

    with patch("autoswe.harness.coder.subprocess.run", side_effect=fake_run):
        assert coder._worktree_has_committable_work(tmp_path, "autoswe/issue-1") is True


def test_non_max_turns_failure_not_rescued(tmp_path):
    """Any other failing subtype (e.g. generic error) must NOT trigger a rescue.

    Only error_max_turns gets the commit-on-cap grace; a plain SDK error keeps
    the historical FAILED behavior.
    """
    from autoswe.harness.coder import run_fix

    run_result = RunResult("boom", session_id="s-err", subtype="error", ok=False)

    def fake_run(prompt, **kwargs):
        return run_result

    gate = GateResult(ok=True, ran=True, reason="suite green", command="pytest")
    stack = _patch_worktree(tmp_path)
    stack.enter_context(_fetch_comments_patch())
    stack.enter_context(patch("autoswe.vcs.worktree.get_merge_conflict_files", return_value=[]))
    stack.enter_context(patch("autoswe.vcs.worktree.get_vcs", return_value=_fake_vcs()))
    stack.enter_context(patch("autoswe.harness.runner.run", side_effect=fake_run))
    stack.enter_context(
        patch("autoswe.harness.coder._worktree_has_committable_work", return_value=True)
    )
    with stack:
        with patch("autoswe.harness.coder.commit_and_push",
                   return_value=FAKE_COMMIT_RESULT) as mock_commit:
            with patch("autoswe.harness.coder.run_test_gate", return_value=gate) as mock_gate:
                res = run_fix(make_task(), None, {"provider": "github"}, {}, wt=tmp_path)

    assert res.done_content.startswith("FAILED")
    mock_commit.assert_not_called()
    mock_gate.assert_not_called()


# ---------------------------------------------------------------------------
# Issue #275: MCP post_question on the fix path (pi fixer pauses → waiting)
# ---------------------------------------------------------------------------


def _question_stack(tmp_path, backend: str, run_result: RunResult,
                    harness_override=None):
    """Shared patch stack for the MCP question tests.

    Resolves the fix harness to *backend* (so the "mcp" capability gate is
    exercised against the real backend), stubs the worktree plumbing, and
    scripts runner.run to return *run_result*. Returns (stack, finalize_mock).
    """
    harness = harness_override or {"backend": backend, "model": "m"}

    def fake_run(prompt, **kwargs):
        return run_result

    stack = _patch_worktree(tmp_path)
    stack.enter_context(_fetch_comments_patch())
    stack.enter_context(patch("autoswe.vcs.worktree.get_merge_conflict_files", return_value=[]))
    stack.enter_context(patch("autoswe.vcs.worktree.get_vcs", return_value=_fake_vcs()))
    stack.enter_context(patch("autoswe.harness.runner.run", side_effect=fake_run))
    if harness is not None:
        stack.enter_context(
            patch("autoswe.harness.coder.resolve_harness", return_value=harness)
        )
    finalize_mock = stack.enter_context(
        patch("autoswe.harness.coder._finalize_fix",
              return_value=HandlerResult("DONE: no changes detected"))
    )
    return stack, finalize_mock


def test_run_fix_pi_mcp_question_returns_waiting(tmp_path):
    """pi fixer that posts a question via MCP → WAITING: questions.

    The pi backend has no can_use_tool interception, so RunResult.
    question_posted is the ONLY question signal; _run_fix_session must honor
    it (mirroring the planner's MCP branch) and pause instead of finalizing —
    the E2E-03b D-pi failure where /fix emitted `fixed` with zero changes
    and a dangling question (issue #275).
    """
    from autoswe.harness.coder import run_fix

    # The pi parser sets ok=True when the stream reaches agent_end — the
    # question-terminal semantics live in the handler, not the parser.
    rr = RunResult("Asked the user which file to edit.", "s-fix-q",
                   "success", question_posted=True)
    stack, finalize_mock = _question_stack(tmp_path, "pi", rr)
    with stack:
        with patch("autoswe.harness.coder.commit_and_push",
                   return_value=FAKE_COMMIT_RESULT) as mock_commit:
            res = run_fix(make_task(), None, {"provider": "github"}, {}, wt=tmp_path)

    assert res.done_content == "WAITING: questions", (
        f"question_posted on an mcp-capable backend must pause, got: {res.done_content!r}"
    )
    assert res.session_id == "s-fix-q", "the resumed session id must be preserved"
    assert not finalize_mock.called, "must not commit/push when waiting on a question"
    mock_commit.assert_not_called()


def test_run_fix_claude_code_mcp_question_returns_waiting(tmp_path):
    """Claude Code also advertises the "mcp" capability, so a fix session that
    calls MCP post_question pauses too — unifying both question routes
    (issue #275: the two routes must behave identically)."""
    from autoswe.harness.coder import run_fix

    rr = RunResult("Posted a question to the issue.", "s-fix-q",
                   "success", question_posted=True)
    stack, finalize_mock = _question_stack(tmp_path, "claude_code", rr)
    with stack:
        res = run_fix(make_task(), None, {"provider": "github"}, {}, wt=tmp_path)

    assert res.done_content == "WAITING: questions"
    assert res.session_id == "s-fix-q"
    finalize_mock.assert_not_called()


def test_run_fix_codex_question_posted_not_honored(tmp_path):
    """Codex advertises no "mcp" capability, so a (forced) question_posted flag
    must NOT pause the run — the documented straight-through behavior of
    E2E-03b pass B stands for codex."""
    from autoswe.harness.coder import run_fix

    rr = RunResult("Just did the fix.", "s-fix-cx", "success", question_posted=True)
    stack, finalize_mock = _question_stack(tmp_path, "codex", rr)
    with stack:
        finalize_mock.return_value = HandlerResult("DONE_SUMMARY\tfixed\tabc1234")
        res = run_fix(make_task(), None, {"provider": "github"}, {}, wt=tmp_path)

    assert not res.done_content.startswith("WAITING"), (
        f"codex must not pause on question_posted, got: {res.done_content!r}"
    )
    assert res.done_content == "DONE_SUMMARY\tfixed\tabc1234"
    finalize_mock.assert_called_once()


def test_run_fix_state_question_wins_over_mcp_flag(tmp_path):
    """When both signals are present, the can_use_tool state path wins
    (same precedence as the planner) — no double handling, one WAITING."""
    from autoswe.harness import coder

    rr = RunResult("Both signals.", "s-fix-both", "success", question_posted=True)

    def fake_run(prompt, **kwargs):
        if kwargs.get("state") is not None:
            kwargs["state"]["asked_question_md"] = "## Questions\n\nWhich approach?"
        return rr

    stack = _patch_worktree(tmp_path)
    stack.enter_context(_fetch_comments_patch())
    stack.enter_context(patch("autoswe.vcs.worktree.get_merge_conflict_files", return_value=[]))
    stack.enter_context(patch("autoswe.vcs.worktree.get_vcs", return_value=_fake_vcs()))
    stack.enter_context(patch("autoswe.harness.runner.run", side_effect=fake_run))
    stack.enter_context(
        patch("autoswe.harness.coder.resolve_harness",
              return_value={"backend": "claude_code", "model": "m"})
    )
    finalize_mock = stack.enter_context(patch("autoswe.harness.coder._finalize_fix"))
    with stack:
        res = coder.run_fix(make_task(), None, {"provider": "github"}, {}, wt=tmp_path)

    assert res.done_content == "WAITING: questions"
    finalize_mock.assert_not_called()


def test_run_fix_question_beats_failure_subtype(tmp_path):
    """A run that posted a question and THEN hit its turn cap still pauses.

    The MCP flag is checked before the ok check, matching the planner: with a
    question on the thread the run's authoritative outcome is "waiting on the
    user" and the session is resumable — the no-work error_max_turns FAILED
    path (and its rescue probe) must not fire.
    """
    from autoswe.harness.coder import run_fix

    rr = RunResult("Turns ran out.", "s-fix-cap", "error_max_turns",
                   ok=False, question_posted=True)
    stack, finalize_mock = _question_stack(tmp_path, "pi", rr)
    with stack:
        stack_work_probe = patch(
            "autoswe.harness.coder._worktree_has_committable_work", return_value=True
        )
        stack_work_probe.start()
        try:
            with patch("autoswe.harness.coder.commit_and_push",
                       return_value=FAKE_COMMIT_RESULT) as mock_commit:
                res = run_fix(make_task(), None, {"provider": "github"}, {}, wt=tmp_path)
        finally:
            stack_work_probe.stop()

    assert res.done_content == "WAITING: questions", (
        f"question must beat error_max_turns, got: {res.done_content!r}"
    )
    mock_commit.assert_not_called()
    finalize_mock.assert_not_called()


def test_resume_fix_mcp_question_returns_waiting(tmp_path):
    """A resumed fix that asks a second question via MCP pauses again —
    resume_fix shares _run_fix_session, so the same flag check applies."""
    from autoswe.harness.coder import resume_fix

    rr = RunResult("Another question.", "s-fix-resumed",
                   "success", question_posted=True)
    stack, finalize_mock = _question_stack(tmp_path, "pi", rr)
    with stack:
        res = resume_fix(
            make_task(session_id="s-fix-orig"), "Put it in src/toolbox.py.",
            {"provider": "github"}, {},
        )

    assert res.done_content == "WAITING: questions"
    assert res.session_id == "s-fix-resumed"
    finalize_mock.assert_not_called()


def test_resume_fix_prompt_names_backend_question_tool(tmp_path):
    """resume_fix names the question tool the way the resolved backend's
    adapter exposes it (Phase 3 pattern, mirroring planner.resume_plan) — a pi
    fixer only has the MCP tool, never a native AskUserQuestion."""
    from autoswe.harness.coder import resume_fix

    rr = RunResult("Done.", "s-fix-done", "success")
    prompts = []

    def fake_run(prompt, **kwargs):
        prompts.append(prompt)
        return rr

    stack = _patch_worktree(tmp_path)
    stack.enter_context(_fetch_comments_patch())
    stack.enter_context(patch("autoswe.vcs.worktree.get_merge_conflict_files", return_value=[]))
    stack.enter_context(patch("autoswe.vcs.worktree.get_vcs", return_value=_fake_vcs()))
    stack.enter_context(patch("autoswe.harness.runner.run", side_effect=fake_run))
    stack.enter_context(
        patch("autoswe.harness.coder.resolve_harness",
              return_value={"backend": "pi", "model": "m"})
    )
    with stack:
        resume_fix(
            make_task(session_id="s-fix-orig"), "src/toolbox.py.",
            {"provider": "github"}, {},
        )

    assert len(prompts) == 1
    prompt = prompts[0]
    # The real PiBackend names the tool without a double underscore (see
    # PiBackend.comment_tool_names); assert it is named and is the MCP comment
    # tool, not the native Claude spelling only.
    assert "post_question" in prompt, f"prompt must name the MCP question tool: {prompt[:300]!r}"
    assert "autoswe_comment" in prompt
    # The stop rule must be in the resume prompt too.
    assert "STOP" in prompt
