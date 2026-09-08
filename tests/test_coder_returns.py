"""Tests for autoswe.harness.coder handler return values."""

import subprocess
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
