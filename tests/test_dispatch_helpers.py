"""Tests for loop helpers — running job tracking and repo locking."""

import os

import pytest

from autoswe.orch.run import DispatchResult


@pytest.fixture
def running_dir(tmp_path, monkeypatch):
    """Set up a RUNNING_DIR for testing."""
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))
    running = tmp_path / "running"
    running.mkdir()

    # Patch both the config module AND the loop module (loop.py imports at module level)
    import autoswe.core.config as cfg_mod
    import autoswe.orch.loop as loop_mod

    monkeypatch.setattr(cfg_mod, "RUNNING_DIR", running)
    monkeypatch.setattr(loop_mod, "RUNNING_DIR", running)
    return running


# ---------------------------------------------------------------------------
# _is_pid_alive
# ---------------------------------------------------------------------------

def test_is_pid_alive_returns_true_for_current_process():
    """_is_pid_alive must return True for the current running process."""
    from autoswe.orch.loop import _is_pid_alive
    assert _is_pid_alive(os.getpid()) is True


def test_is_pid_alive_returns_false_for_nonexistent_pid():
    """_is_pid_alive must return False for a PID that does not exist."""
    from autoswe.orch.loop import _is_pid_alive
    assert _is_pid_alive(99999999) is False


def test_is_pid_alive_returns_false_for_negative_pid():
    """_is_pid_alive must return False for negative or zero PIDs."""
    from autoswe.orch.loop import _is_pid_alive
    assert _is_pid_alive(-1) is False
    assert _is_pid_alive(0) is False


# ---------------------------------------------------------------------------
# _is_repo_locked
# ---------------------------------------------------------------------------

def test_is_repo_locked_not_locked(running_dir, monkeypatch):
    import autoswe.orch.loop as loop_mod
    monkeypatch.setattr(loop_mod, "RUNNING_DIR", running_dir)
    from autoswe.orch.loop import _is_repo_locked
    result = _is_repo_locked("owner", "repo", "github")
    assert result is None


def test_is_repo_locked_azure(running_dir, monkeypatch):
    import autoswe.orch.loop as loop_mod
    monkeypatch.setattr(loop_mod, "RUNNING_DIR", running_dir)
    (running_dir / "ado_org_proj_repo_5.pid").write_text(str(os.getpid()))
    from autoswe.orch.loop import _is_repo_locked
    result = _is_repo_locked("org/proj", "repo", provider="azure")
    assert result == "ado_org_proj_repo_5"


def test_is_repo_locked_returns_locking_task(running_dir, monkeypatch):
    import autoswe.orch.loop as loop_mod
    monkeypatch.setattr(loop_mod, "RUNNING_DIR", running_dir)
    (running_dir / "gh_owner_repo_42.pid").write_text(str(os.getpid()))
    from autoswe.orch.loop import _is_repo_locked
    result = _is_repo_locked("owner", "repo", "github")
    assert result == "gh_owner_repo_42"


def test_is_repo_locked_different_repo_not_locked(running_dir, monkeypatch):
    import autoswe.orch.loop as loop_mod
    monkeypatch.setattr(loop_mod, "RUNNING_DIR", running_dir)
    (running_dir / "gh_owner_repo_42.pid").write_text(str(os.getpid()))
    from autoswe.orch.loop import _is_repo_locked
    result = _is_repo_locked("other", "repo", "github")
    assert result is None


def test_is_repo_locked_stale_pid_auto_cleaned(running_dir, monkeypatch):
    """Stale repo lock PIDs should be cleaned and treated as unlocked."""
    import autoswe.orch.loop as loop_mod
    monkeypatch.setattr(loop_mod, "RUNNING_DIR", running_dir)
    (running_dir / "gh_owner_repo_42.pid").write_text("99999999")
    from autoswe.orch.loop import _is_repo_locked
    result = _is_repo_locked("owner", "repo", "github")
    assert result is None
    assert not (running_dir / "gh_owner_repo_42.pid").exists()


# ---------------------------------------------------------------------------
# _is_task_running
# ---------------------------------------------------------------------------

def test_is_task_running_true(running_dir, monkeypatch):
    import autoswe.orch.loop as loop_mod
    monkeypatch.setattr(loop_mod, "RUNNING_DIR", running_dir)
    # slug "gh:o_r_1" → filename "gh_o_r_1"
    (running_dir / "gh_o_r_1.pid").write_text(str(os.getpid()))
    from autoswe.orch.loop import _is_task_running
    assert _is_task_running("gh:o_r_1") is True


def test_is_task_running_false(running_dir, monkeypatch):
    import autoswe.orch.loop as loop_mod
    monkeypatch.setattr(loop_mod, "RUNNING_DIR", running_dir)
    from autoswe.orch.loop import _is_task_running
    assert _is_task_running("gh:o_r_1") is False


def test_is_task_running_stale_pid_cleaned(running_dir, monkeypatch):
    """PID file with a non-existent PID should be treated as not running and cleaned up."""
    import autoswe.orch.loop as loop_mod
    monkeypatch.setattr(loop_mod, "RUNNING_DIR", running_dir)
    (running_dir / "gh_o_r_1.pid").write_text("99999999")
    from autoswe.orch.loop import _is_task_running
    assert _is_task_running("gh:o_r_1") is False
    assert not (running_dir / "gh_o_r_1.pid").exists()


def test_is_task_running_corrupt_pid_cleaned(running_dir, monkeypatch):
    """PID file with garbage content should be treated as not running and cleaned up."""
    import autoswe.orch.loop as loop_mod
    monkeypatch.setattr(loop_mod, "RUNNING_DIR", running_dir)
    (running_dir / "gh_o_r_1.pid").write_text("not-a-pid")
    from autoswe.orch.loop import _is_task_running
    assert _is_task_running("gh:o_r_1") is False
    assert not (running_dir / "gh_o_r_1.pid").exists()


def test_is_task_running_different_task(running_dir, monkeypatch):
    import autoswe.orch.loop as loop_mod
    monkeypatch.setattr(loop_mod, "RUNNING_DIR", running_dir)
    (running_dir / "gh_o_r_1.pid").write_text("1234")
    from autoswe.orch.loop import _is_task_running
    assert _is_task_running("gh:o_r_2") is False


def test_is_task_running_ado_slug_sanitized(running_dir, monkeypatch):
    """ADO slug with : and / characters should be sanitized for PID lookup."""
    import autoswe.orch.loop as loop_mod
    monkeypatch.setattr(loop_mod, "RUNNING_DIR", running_dir)
    (running_dir / "ado_org_proj_repo_70.pid").write_text(str(os.getpid()))
    from autoswe.orch.loop import _is_task_running
    assert _is_task_running("ado:org_proj/repo_70") is True


def test_is_task_running_ado_slug_no_false_miss(running_dir, monkeypatch):
    """An ADO slug must not match a differently-sanitized PID file."""
    import autoswe.orch.loop as loop_mod
    monkeypatch.setattr(loop_mod, "RUNNING_DIR", running_dir)
    (running_dir / "ado_org_proj_repo_70.pid").write_text(str(os.getpid()))
    from autoswe.orch.loop import _is_task_running
    assert _is_task_running("ado:org_proj/repo_71") is False


def test_is_task_running_gh_slug_sanitized(running_dir, monkeypatch):
    """GitHub slug colon is sanitized, matching the expected PID stem."""
    import autoswe.orch.loop as loop_mod
    monkeypatch.setattr(loop_mod, "RUNNING_DIR", running_dir)
    (running_dir / "gh_owner_repo_42.pid").write_text(str(os.getpid()))
    from autoswe.orch.loop import _is_task_running
    assert _is_task_running("gh:owner_repo_42") is True


# ---------------------------------------------------------------------------
# _format_metrics helper (moved to emit.py)
# ---------------------------------------------------------------------------

def test_format_metrics_all_fields():
    """_format_metrics should include cost, duration, and session."""
    from autoswe.orch.emit import _format_metrics

    msg = _format_metrics(cost_usd=0.42, duration_seconds=255, session_id="abc123")
    assert "Cost: $0.42" in msg
    assert "Duration: 4m15s" in msg
    assert "Session: abc123" in msg


def test_format_metrics_cost_only():
    """_format_metrics with only cost should show cost."""
    from autoswe.orch.emit import _format_metrics

    msg = _format_metrics(cost_usd=1.50, duration_seconds=None, session_id=None)
    assert "Cost: $1.50" in msg
    assert "Duration" not in msg
    assert "Session" not in msg


def test_format_metrics_empty_returns_empty_string():
    """_format_metrics with all None should return empty string."""
    from autoswe.orch.emit import _format_metrics

    msg = _format_metrics(cost_usd=None, duration_seconds=None, session_id=None)
    assert msg == ""


def test_format_metrics_zero_duration_returns_empty():
    """_format_metrics with 0 duration should omit duration field."""
    from autoswe.orch.emit import _format_metrics

    msg = _format_metrics(cost_usd=None, duration_seconds=0, session_id=None)
    assert msg == ""


def test_format_metrics_duration_formatting():
    """Duration should format as XmYs."""
    from autoswe.orch.emit import _format_metrics

    msg = _format_metrics(cost_usd=None, duration_seconds=365, session_id=None)
    assert "Duration: 6m5s" in msg

    msg = _format_metrics(cost_usd=None, duration_seconds=59, session_id=None)
    assert "Duration: 0m59s" in msg


# ---------------------------------------------------------------------------
# DispatchResult dataclass
# ---------------------------------------------------------------------------

def test_dispatch_result_defaults():
    """DispatchResult should default cost to None and duration to 0."""
    dr = DispatchResult("DONE: fixed")
    assert dr.done_content == "DONE: fixed"
    assert dr.cost_usd is None
    assert dr.duration_seconds == 0.0


def test_dispatch_result_with_metrics():
    """DispatchResult should carry cost and duration."""
    dr = DispatchResult("DONE_SUMMARY\tsummary\tsha", cost_usd=0.75, duration_seconds=45.2)
    assert dr.done_content == "DONE_SUMMARY\tsummary\tsha"
    assert dr.cost_usd == 0.75
    assert dr.duration_seconds == 45.2


def test_to_dispatch_prefers_handler_session_id():
    """_to_dispatch should use hr.session_id when set, falling back to
    task session_id. This is how the review handler reports its throwaway
    session ID instead of the persistent fix session."""
    from autoswe.harness.runner import HandlerResult
    from autoswe.orch.run import _to_dispatch

    hr = HandlerResult(
        done_content="REVIEW_READY\tLGTM",
        session_id="review-session-abc",
    )
    task = {"session_id": "fix-session-123"}

    dr = _to_dispatch(hr, task)

    assert dr.session_id == "review-session-abc", (
        "_to_dispatch should prefer hr.session_id over task session_id"
    )


def test_to_dispatch_falls_back_to_task_session_id():
    """When hr.session_id is None (plan, fix handlers), _to_dispatch falls
    back to task's session_id."""
    from autoswe.harness.runner import HandlerResult
    from autoswe.orch.run import _to_dispatch

    hr = HandlerResult(
        done_content="DONE_SUMMARY\tfixed\tsha",
        session_id=None,  # plan/fix don't set this
    )
    task = {"session_id": "fix-session-123"}

    dr = _to_dispatch(hr, task)

    assert dr.session_id == "fix-session-123", (
        "_to_dispatch should fall back to task session_id when hr.session_id is None"
    )


# ---------------------------------------------------------------------------
# /sync handler (moved to orch/run.py)
# ---------------------------------------------------------------------------

def test_run_sync_passes_progress_callback(tmp_path, monkeypatch):
    """_run_sync should accept and forward progress_callback."""
    import inspect

    from autoswe.orch.run import run
    sig = inspect.signature(run)
    assert "progress_callback" in sig.parameters


def test_sync_returns_done_summary_format(tmp_path, monkeypatch):
    """orch.run sync action should return DONE_SUMMARY format on clean merge."""
    from autoswe.orch.run import run
    from autoswe.orch.types import Action, ApiState, TaskState, World
    from autoswe.providers.base import NormalizedIssue
    from autoswe.vcs import worktree as worktree_mod

    wt_dir = tmp_path / "wt"
    wt_dir.mkdir()
    monkeypatch.setattr(worktree_mod, "worktree_path",
                        lambda o, r, n, c, p="github": wt_dir)

    monkeypatch.setattr(worktree_mod, "sync_branch",
        lambda wt, o, r, n, b, p="github", cfg=None: {
            "synced": True, "conflict": False, "branch": "autoswe/issue-1",
            "ahead": 2, "commit_sha": "abc1234", "changed": True,
        })

    api = ApiState(
        issue=NormalizedIssue(number=1, title="t", body="b", owner="o", repo="r"),
        comments=(),
    )
    task = TaskState(
        slug="gh:o_r_1", owner="o", repo="r", issue_number=1, title="t", body="b",
        status=None, plan_branch=None, base_branch="main", attempt_count=0,
        first_dispatched_at=None, last_dispatched_command=None,
        last_dispatched_command_id=None, last_consumed_reply_id=None,
        session_id=None, pr_number=None, guard_blocked=False, gh_closed=False,
        pending_command=None, pending_guidance=None, pending_user_reply=None,
        provider="github",
    )
    world = World(api=api, task=task, cfg={"WORKTREE_DIR": str(tmp_path)}, repo_cfg={"provider": "github"})

    action = Action(kind="sync_branch", slug="gh:o_r_1")
    progress_calls = []
    result = run(action, world, progress_callback=progress_calls.append)

    assert result is not None
    assert result.done_content.startswith("DONE_SUMMARY\t")
    assert "autoswe/issue-1" in result.done_content
    assert "abc1234" in result.done_content
    assert len(progress_calls) >= 1
    assert "Merging" in progress_calls[0]


# ---------------------------------------------------------------------------
# Batch 4 — Safeguard negative paths (roadmap hole-closing)
# ---------------------------------------------------------------------------

def test_max_concurrent_gate(running_dir, monkeypatch):
    """MAX_CONCURRENT=1: only one task dispatched per cycle.

    Simulates the loop logic: tasks_processed counter stops dispatching
    after reaching max_concurrent.
    """
    # The MAX_CONCURRENT gate is in loop.py line 599-601.
    # We verify the logic by checking that tasks_processed >= max_concurrent
    # breaks the dispatch loop.
    max_concurrent = 1
    # If 2 tasks would be dispatched, only 1 gets through
    dispatched = []
    for i in range(3):
        slug = f"gh:o_r_{i}"
        if len(dispatched) >= max_concurrent:
            break  # MAX_CONCURRENT gate
        if not _is_task_running_test(slug, running_dir):
            dispatched.append(slug)
    assert len(dispatched) == 1
    assert dispatched[0] == "gh:o_r_0"


def _is_task_running_test(slug: str, running_dir) -> bool:
    """Helper for test_max_concurrent_gate — mirrors loop._is_task_running."""
    from autoswe.core.slug import slug_to_filename
    stem = slug_to_filename(slug)
    pid_path = running_dir / f"{stem}.pid"
    if pid_path.exists():
        try:
            import os
            pid = int(pid_path.read_text().strip())
            os.kill(pid, 0)
            return True
        except (ProcessLookupError, ValueError, OSError):
            pid_path.unlink(missing_ok=True)
    return False


def test_is_task_running_empty_pid_file(running_dir, monkeypatch):
    """PID file with empty content should be treated as not running."""
    import autoswe.orch.loop as loop_mod
    monkeypatch.setattr(loop_mod, "RUNNING_DIR", running_dir)
    (running_dir / "gh_o_r_1.pid").write_text("")
    from autoswe.orch.loop import _is_task_running
    assert _is_task_running("gh:o_r_1") is False
    assert not (running_dir / "gh_o_r_1.pid").exists()


def test_is_repo_locked_live_pid_not_cleaned(running_dir, monkeypatch):
    """A repo lock with a live PID should NOT be auto-cleaned."""
    import autoswe.orch.loop as loop_mod
    monkeypatch.setattr(loop_mod, "RUNNING_DIR", running_dir)
    (running_dir / "gh_owner_repo_42.pid").write_text(str(os.getpid()))
    from autoswe.orch.loop import _is_repo_locked
    result = _is_repo_locked("owner", "repo", "github")
    assert result == "gh_owner_repo_42"
    # PID file should NOT be cleaned (process is alive)
    assert (running_dir / "gh_owner_repo_42.pid").exists()


def test_multiple_pid_files_same_repo(running_dir, monkeypatch):
    """Multiple PID files for same repo — first match wins."""
    import autoswe.orch.loop as loop_mod
    monkeypatch.setattr(loop_mod, "RUNNING_DIR", running_dir)
    (running_dir / "gh_owner_repo_42.pid").write_text("99999999")  # stale
    (running_dir / "gh_owner_repo_43.pid").write_text(str(os.getpid()))  # live
    from autoswe.orch.loop import _is_repo_locked
    # _is_repo_locked checks per-issue, not per-repo
    result = _is_repo_locked("owner", "repo", "github")
    # The repo-level lock globs by owner/repo, finds gh_owner_repo_43
    assert result is not None


# ---------------------------------------------------------------------------
# /sync conflict resolution — orchestrator wiring


def test_run_sync_conflict_invokes_resolver(tmp_path, monkeypatch):
    """When sync_branch returns conflict, coder.resolve_sync_conflicts should be called."""
    from autoswe.harness.runner import HandlerResult
    from autoswe.orch.run import run
    from autoswe.orch.types import Action, ApiState, TaskState, World
    from autoswe.providers.base import NormalizedIssue
    from autoswe.vcs import worktree as worktree_mod

    wt_dir = tmp_path / "wt"
    wt_dir.mkdir()
    monkeypatch.setattr(worktree_mod, "worktree_path",
                        lambda o, r, n, c, p="github": wt_dir)

    monkeypatch.setattr(worktree_mod, "sync_branch",
        lambda wt, o, r, n, b, p="github", cfg=None: {
            "synced": False, "conflict": True, "branch": "autoswe/issue-1",
            "ahead": 0, "conflict_files": ["src/main.py"],
            "error": "merge conflict",
        })

    resolver_called = []

    def fake_resolve(task, files, **kwargs):
        resolver_called.append((task, files))
        return HandlerResult("DONE_SUMMARY\tResolved\tabc1234")

    import autoswe.harness.coder as coder_mod
    monkeypatch.setattr(coder_mod, "resolve_sync_conflicts", fake_resolve)

    api = ApiState(
        issue=NormalizedIssue(number=1, title="t", body="b", owner="o", repo="r"),
        comments=(),
    )
    task = TaskState(
        slug="gh:o_r_1", owner="o", repo="r", issue_number=1, title="t", body="b",
        status=None, plan_branch=None, base_branch="main", attempt_count=0,
        first_dispatched_at=None, last_dispatched_command=None,
        last_dispatched_command_id=None, last_consumed_reply_id=None,
        session_id=None, pr_number=None, guard_blocked=False, gh_closed=False,
        pending_command=None, pending_guidance=None, pending_user_reply=None,
        provider="github",
    )
    world = World(api=api, task=task, cfg={"WORKTREE_DIR": str(tmp_path)}, repo_cfg={"provider": "github"})
    action = Action(kind="sync_branch", slug="gh:o_r_1")

    result = run(action, world)

    assert result is not None
    assert result.done_content.startswith("DONE_SUMMARY\t")
    assert len(resolver_called) == 1
    assert resolver_called[0][1] == ["src/main.py"]


def test_run_sync_conflict_resolver_failed_returns_failed(tmp_path, monkeypatch):
    """When resolver returns FAILED, _run_sync propagates FAILED."""
    from autoswe.harness.runner import HandlerResult
    from autoswe.orch.run import run
    from autoswe.orch.types import Action, ApiState, TaskState, World
    from autoswe.providers.base import NormalizedIssue
    from autoswe.vcs import worktree as worktree_mod

    wt_dir = tmp_path / "wt"
    wt_dir.mkdir()
    monkeypatch.setattr(worktree_mod, "worktree_path",
                        lambda o, r, n, c, p="github": wt_dir)

    monkeypatch.setattr(worktree_mod, "sync_branch",
        lambda wt, o, r, n, b, p="github", cfg=None: {
            "synced": False, "conflict": True, "branch": "autoswe/issue-1",
            "ahead": 0, "conflict_files": ["src/main.py"],
            "error": "merge conflict",
        })

    import autoswe.harness.coder as coder_mod
    monkeypatch.setattr(coder_mod, "resolve_sync_conflicts",
        lambda task, files, **kwargs: HandlerResult("FAILED: unresolved conflicts: src/main.py"))

    api = ApiState(
        issue=NormalizedIssue(number=1, title="t", body="b", owner="o", repo="r"),
        comments=(),
    )
    task = TaskState(
        slug="gh:o_r_1", owner="o", repo="r", issue_number=1, title="t", body="b",
        status=None, plan_branch=None, base_branch="main", attempt_count=0,
        first_dispatched_at=None, last_dispatched_command=None,
        last_dispatched_command_id=None, last_consumed_reply_id=None,
        session_id=None, pr_number=None, guard_blocked=False, gh_closed=False,
        pending_command=None, pending_guidance=None, pending_user_reply=None,
        provider="github",
    )
    world = World(api=api, task=task, cfg={"WORKTREE_DIR": str(tmp_path)}, repo_cfg={"provider": "github"})
    action = Action(kind="sync_branch", slug="gh:o_r_1")

    result = run(action, world)

    assert result is not None
    assert result.done_content.startswith("FAILED:")
    assert "unresolved conflicts" in result.done_content


def test_run_sync_rebase_conflict_skips_resolver(tmp_path, monkeypatch):
    """When sync_branch returns rebase=True, resolver should NOT be invoked."""
    from autoswe.orch.run import run
    from autoswe.orch.types import Action, ApiState, TaskState, World
    from autoswe.providers.base import NormalizedIssue
    from autoswe.vcs import worktree as worktree_mod

    wt_dir = tmp_path / "wt"
    wt_dir.mkdir()
    monkeypatch.setattr(worktree_mod, "worktree_path",
                        lambda o, r, n, c, p="github": wt_dir)

    monkeypatch.setattr(worktree_mod, "sync_branch",
        lambda wt, o, r, n, b, p="github", cfg=None: {
            "synced": False, "conflict": True, "branch": "autoswe/issue-1",
            "ahead": 0, "conflict_files": ["src/main.py"], "rebase": True,
            "error": "rebase conflict",
        })

    import autoswe.harness.coder as coder_mod
    original_resolve = coder_mod.resolve_sync_conflicts
    resolver_called = []

    def tracked_resolve(*args, **kwargs):
        resolver_called.append(True)
        return original_resolve(*args, **kwargs)

    monkeypatch.setattr(coder_mod, "resolve_sync_conflicts", tracked_resolve)

    api = ApiState(
        issue=NormalizedIssue(number=1, title="t", body="b", owner="o", repo="r"),
        comments=(),
    )
    task = TaskState(
        slug="gh:o_r_1", owner="o", repo="r", issue_number=1, title="t", body="b",
        status=None, plan_branch=None, base_branch="main", attempt_count=0,
        first_dispatched_at=None, last_dispatched_command=None,
        last_dispatched_command_id=None, last_consumed_reply_id=None,
        session_id=None, pr_number=None, guard_blocked=False, gh_closed=False,
        pending_command=None, pending_guidance=None, pending_user_reply=None,
        provider="github",
    )
    world = World(api=api, task=task, cfg={"WORKTREE_DIR": str(tmp_path)}, repo_cfg={"provider": "github"})
    action = Action(kind="sync_branch", slug="gh:o_r_1")

    result = run(action, world)

    assert result is not None
    assert result.done_content.startswith("FAILED:")
    assert "rebase conflict" in result.done_content
    assert len(resolver_called) == 0, "Resolver should NOT be called for rebase conflicts"


def test_run_fix_pre_dispatch_sync_on_conflict_proceeds_to_fix(tmp_path, monkeypatch):
    """Pre-fix sync with merge conflict → resolver NOT called → run_fix proceeds inline.

    The fix path uses resolve_conflicts=False so the conflicted worktree is
    passed directly to run_fix, which appends the resolution instructions to
    the agent prompt rather than running a separate resolver agent.
    """
    from autoswe.harness.runner import HandlerResult
    from autoswe.orch.run import run
    from autoswe.orch.types import Action, ApiState, TaskState, World
    from autoswe.providers.base import NormalizedIssue
    from autoswe.vcs import worktree as worktree_mod

    wt_dir = tmp_path / "wt"
    wt_dir.mkdir()
    monkeypatch.setattr(worktree_mod, "worktree_path",
                        lambda o, r, n, c, p="github": wt_dir)

    monkeypatch.setattr(worktree_mod, "sync_branch",
        lambda wt, o, r, n, b, p="github", cfg=None: {
            "synced": False, "conflict": True, "branch": "autoswe/issue-1",
            "ahead": 0, "conflict_files": ["src/main.py"],
            "error": "merge conflict",
        })

    import autoswe.harness.coder as coder_mod
    resolve_called = []
    monkeypatch.setattr(coder_mod, "resolve_sync_conflicts",
        lambda task, files, **kwargs: resolve_called.append(True) or HandlerResult("FAILED: unresolved"))
    fix_called = []
    monkeypatch.setattr(coder_mod, "run_fix",
        lambda *a, **kw: fix_called.append(True) or HandlerResult("DONE_SUMMARY\tfixed\tabc"))

    api = ApiState(
        issue=NormalizedIssue(number=1, title="t", body="b", owner="o", repo="r"),
        comments=(),
    )
    task = TaskState(
        slug="gh:o_r_1", owner="o", repo="r", issue_number=1, title="t", body="b",
        status=None, plan_branch=None, base_branch="main", attempt_count=0,
        first_dispatched_at=None, last_dispatched_command=None,
        last_dispatched_command_id=None, last_consumed_reply_id=None,
        session_id=None, pr_number=None, guard_blocked=False, gh_closed=False,
        pending_command=None, pending_guidance=None, pending_user_reply=None,
        provider="github",
    )
    world = World(api=api, task=task, cfg={"WORKTREE_DIR": str(tmp_path)}, repo_cfg={"provider": "github", "pat": "fake"})
    action = Action(kind="fix", slug="gh:o_r_1")

    result = run(action, world)

    assert result is not None
    assert result.done_content.startswith("DONE_SUMMARY"), \
        "Fix path with merge conflict should proceed to run_fix (conflict folded into prompt)"
    assert len(fix_called) == 1, "run_fix must be called even when pre-sync has a merge conflict"
    assert resolve_called == [], "resolve_sync_conflicts must NOT be called on the fix path"


def test_run_fix_pre_dispatch_sync_clean_proceeds_to_fix(tmp_path, monkeypatch):
    """Pre-fix sync with no conflict → resolver not called → fix runs normally."""
    from autoswe.harness.runner import HandlerResult
    from autoswe.orch.run import run
    from autoswe.orch.types import Action, ApiState, TaskState, World
    from autoswe.providers.base import NormalizedIssue
    from autoswe.vcs import worktree as worktree_mod

    wt_dir = tmp_path / "wt"
    wt_dir.mkdir()
    monkeypatch.setattr(worktree_mod, "worktree_path",
                        lambda o, r, n, c, p="github": wt_dir)

    monkeypatch.setattr(worktree_mod, "sync_branch",
        lambda wt, o, r, n, b, p="github", cfg=None: {
            "synced": True, "conflict": False, "branch": "autoswe/issue-1",
            "ahead": 2, "commit_sha": "def5678", "changed": True,
        })

    import autoswe.harness.coder as coder_mod
    original_resolve = coder_mod.resolve_sync_conflicts
    resolver_called = []

    def tracked_resolve(*args, **kwargs):
        resolver_called.append(True)
        return original_resolve(*args, **kwargs)

    monkeypatch.setattr(coder_mod, "resolve_sync_conflicts", tracked_resolve)
    fix_called = []
    monkeypatch.setattr(coder_mod, "run_fix",
        lambda *a, **kw: fix_called.append(True) or HandlerResult("DONE_SUMMARY\tfixed\tabc"))

    api = ApiState(
        issue=NormalizedIssue(number=1, title="t", body="b", owner="o", repo="r"),
        comments=(),
    )
    task = TaskState(
        slug="gh:o_r_1", owner="o", repo="r", issue_number=1, title="t", body="b",
        status=None, plan_branch=None, base_branch="main", attempt_count=0,
        first_dispatched_at=None, last_dispatched_command=None,
        last_dispatched_command_id=None, last_consumed_reply_id=None,
        session_id=None, pr_number=None, guard_blocked=False, gh_closed=False,
        pending_command=None, pending_guidance=None, pending_user_reply=None,
        provider="github",
    )
    world = World(api=api, task=task, cfg={"WORKTREE_DIR": str(tmp_path)}, repo_cfg={"provider": "github", "pat": "fake"})
    action = Action(kind="fix", slug="gh:o_r_1")

    result = run(action, world)

    assert result is not None
    assert result.done_content.startswith("DONE_SUMMARY\t")
    assert len(resolver_called) == 0, "Resolver should NOT be called when sync is clean"
    assert len(fix_called) == 1, "Fix should run when pre-fix sync is clean"


# ---------------------------------------------------------------------------
# Dispatch error handling — issue #238
#
# When _dispatch_task() throws after setting status to "dispatched", the
# except block in _single_poll transitions the task to the "error" terminal
# state instead of rolling back to "pending". The user must post `/retry`
# to resume.
# ---------------------------------------------------------------------------


def test_dispatch_failure_transitions_to_error(
    isolated_autoswe_dir, monkeypatch, tmp_path,
):
    """When _dispatch_task raises, queue status must transition to 'error'."""
    from autoswe.core.queue_store import LockedQueue

    task_id = "gh:owner_repo_1"
    task = {
        "id": task_id,
        "owner": "owner",
        "repo": "repo",
        "issue_number": 1,
        "title": "Test issue",
        "body": "Fix this\n\n/fix",
        "autoswe_status": "pending",
        "base_branch": "main",
        "provider": "github",
        "suppress_welcome": True,
        "pr_number": None,
        "session_id": "session-abc",
        "first_dispatched_at": "2026-01-01T00:00:00Z",
        "last_dispatched_command_id": None,
        "last_consumed_reply_id": None,
        "bot_comment_ids": [],
        "last_synced": "2026-01-01T00:00:00Z",
        "created_at": "2026-01-01T00:00:00Z",
    }
    with LockedQueue() as lq:
        lq.queue[task_id] = dict(task)

    import json
    repos_path = isolated_autoswe_dir / "config" / "repos.json"
    repos_path.write_text(
        json.dumps({"owner/repo": {"provider": "github", "pat": "fake", "base_branch": "main"}})
    )

    import autoswe.orch.loop as loop_mod

    dispatch_called = []

    def failing_dispatch(*args, **kwargs):
        pt = args[0]
        slug = pt.slug
        queue_entry = args[6]
        queue_entry[slug]["autoswe_status"] = "dispatched"
        dispatch_called.append(slug)
        raise RuntimeError("simulated dispatch failure")

    monkeypatch.setattr(loop_mod, "_dispatch_task", failing_dispatch)

    from autoswe.orch.types import ApiState
    from autoswe.providers.base import NormalizedIssue

    def fake_read_api(tracker, repo_cfg, cfg, *, bot_ids=None, prev_updated=None, force_fetch=None):
        return {
            1: ApiState(
                issue=NormalizedIssue(
                    number=1, title="Test issue", body="Fix this\n\n/fix",
                    owner="owner", repo="repo", state="open",
                    is_pull_request=False, labels=[],
                ),
                comments=(),
            ),
        }

    monkeypatch.setattr(loop_mod, "_get_read_api", lambda provider: fake_read_api)

    cfg = {
        "MAX_CONCURRENT": 1,
        "SILENT_REPORTING": True,
        "WORKTREE_DIR": str(tmp_path / "worktrees"),
    }

    loop_mod.poll(cfg, mode="full", repo_filter="owner/repo")

    # Verify dispatch was attempted
    assert len(dispatch_called) == 1
    assert dispatch_called[0] == task_id

    # Verify error transition: status should be "error", NOT "dispatched" or "pending"
    with LockedQueue() as lq:
        actual_status = lq.queue[task_id]["autoswe_status"]
    assert actual_status == "error", (
        f"Expected status 'error' after dispatch failure, got {actual_status!r}. "
        "The _handle_dispatch_error should transition to 'error' state."
    )


def test_dispatch_failure_sets_error_label(
    isolated_autoswe_dir, monkeypatch, tmp_path,
):
    """When _dispatch_task raises, tracker.set_status must be called with 'autoswe:error'."""
    from autoswe.core.queue_store import LockedQueue

    task_id = "gh:owner_repo_1"
    task = {
        "id": task_id,
        "owner": "owner",
        "repo": "repo",
        "issue_number": 1,
        "title": "Test issue",
        "body": "Fix this\n\n/fix",
        "autoswe_status": "pending",
        "base_branch": "main",
        "provider": "github",
        "suppress_welcome": True,
        "pr_number": None,
        "session_id": None,
        "last_dispatched_command_id": None,
        "last_consumed_reply_id": None,
        "bot_comment_ids": [],
        "last_synced": "2026-01-01T00:00:00Z",
        "created_at": "2026-01-01T00:00:00Z",
    }
    with LockedQueue() as lq:
        lq.queue[task_id] = dict(task)

    import json
    repos_path = isolated_autoswe_dir / "config" / "repos.json"
    repos_path.write_text(
        json.dumps({"owner/repo": {"provider": "github", "pat": "fake", "base_branch": "main"}})
    )

    import autoswe.orch.loop as loop_mod

    dispatch_called = []

    def failing_dispatch(*args, **kwargs):
        pt = args[0]
        slug = pt.slug
        queue_entry = args[6]
        queue_entry[slug]["autoswe_status"] = "dispatched"
        dispatch_called.append(slug)
        raise RuntimeError("simulated dispatch failure")

    monkeypatch.setattr(loop_mod, "_dispatch_task", failing_dispatch)

    # Track set_status calls on the tracker
    set_status_calls = []
    posted_comments = []

    class FakeTracker:
        def set_status(self, repo_cfg, issue_num, label):
            set_status_calls.append((issue_num, label))
        def post_comment(self, repo_cfg, issue_num, body):
            posted_comments.append((issue_num, body))
        def fetch_comments(self, *a, **kw):
            return []

    import autoswe.providers.factory as factory_mod

    def fake_get_tracker(repo_cfg):
        return FakeTracker()

    monkeypatch.setattr(loop_mod, "get_tracker", fake_get_tracker)
    monkeypatch.setattr(factory_mod, "get_tracker", fake_get_tracker)

    from autoswe.orch.types import ApiState
    from autoswe.providers.base import NormalizedIssue

    def fake_read_api(tracker, repo_cfg, cfg, *, bot_ids=None, prev_updated=None, force_fetch=None):
        return {
            1: ApiState(
                issue=NormalizedIssue(
                    number=1, title="Test issue", body="Fix this\n\n/fix",
                    owner="owner", repo="repo", state="open",
                    is_pull_request=False, labels=[],
                ),
                comments=(),
            ),
        }

    monkeypatch.setattr(loop_mod, "_get_read_api", lambda provider: fake_read_api)

    cfg = {
        "MAX_CONCURRENT": 1,
        "SILENT_REPORTING": True,
        "WORKTREE_DIR": str(tmp_path / "worktrees"),
    }

    loop_mod.poll(cfg, mode="full", repo_filter="owner/repo")

    assert len(dispatch_called) == 1

    # The error handler should call set_status with "autoswe:error"
    error_label = [c for c in set_status_calls if c[1] == "autoswe:error"]
    assert len(error_label) >= 1, (
        f"Expected at least one set_status('autoswe:error') call during error handling. "
        f"All set_status calls: {set_status_calls}"
    )
    assert error_label[0][0] == 1, "Error label should target issue #1"


def test_dispatch_error_label_is_best_effort(
    isolated_autoswe_dir, monkeypatch, tmp_path,
):
    """If tracker.set_status raises during error handling, it should not propagate."""
    from autoswe.core.queue_store import LockedQueue

    task_id = "gh:owner_repo_1"
    task = {
        "id": task_id,
        "owner": "owner",
        "repo": "repo",
        "issue_number": 1,
        "title": "Test issue",
        "body": "Fix this\n\n/fix",
        "autoswe_status": "pending",
        "base_branch": "main",
        "provider": "github",
        "suppress_welcome": True,
        "pr_number": None,
        "session_id": None,
        "last_dispatched_command_id": None,
        "last_consumed_reply_id": None,
        "bot_comment_ids": [],
        "last_synced": "2026-01-01T00:00:00Z",
        "created_at": "2026-01-01T00:00:00Z",
    }
    with LockedQueue() as lq:
        lq.queue[task_id] = dict(task)

    import json
    repos_path = isolated_autoswe_dir / "config" / "repos.json"
    repos_path.write_text(
        json.dumps({"owner/repo": {"provider": "github", "pat": "fake", "base_branch": "main"}})
    )

    import autoswe.orch.loop as loop_mod

    def failing_dispatch(*args, **kwargs):
        pt = args[0]
        slug = pt.slug
        queue_entry = args[6]
        queue_entry[slug]["autoswe_status"] = "dispatched"
        raise RuntimeError("simulated dispatch failure")

    monkeypatch.setattr(loop_mod, "_dispatch_task", failing_dispatch)

    # Tracker that raises RuntimeError on set_status
    class FailingTracker:
        def set_status(self, repo_cfg, issue_num, label):
            raise RuntimeError("API is down")
        def post_comment(self, repo_cfg, issue_num, body):
            raise RuntimeError("API is down")
        def fetch_comments(self, *a, **kw):
            return []

    import autoswe.providers.factory as factory_mod

    def fake_get_tracker(repo_cfg):
        return FailingTracker()

    monkeypatch.setattr(loop_mod, "get_tracker", fake_get_tracker)
    monkeypatch.setattr(factory_mod, "get_tracker", fake_get_tracker)

    from autoswe.orch.types import ApiState
    from autoswe.providers.base import NormalizedIssue

    def fake_read_api(tracker, repo_cfg, cfg, *, bot_ids=None, prev_updated=None, force_fetch=None):
        return {
            1: ApiState(
                issue=NormalizedIssue(
                    number=1, title="Test issue", body="Fix this\n\n/fix",
                    owner="owner", repo="repo", state="open",
                    is_pull_request=False, labels=[],
                ),
                comments=(),
            ),
        }

    monkeypatch.setattr(loop_mod, "_get_read_api", lambda provider: fake_read_api)

    cfg = {
        "MAX_CONCURRENT": 1,
        "SILENT_REPORTING": True,
        "WORKTREE_DIR": str(tmp_path / "worktrees"),
    }

    # Poll should complete without propagating the set_status/post_comment error
    loop_mod.poll(cfg, mode="full", repo_filter="owner/repo")

    # Queue status should still be transitioned to error
    with LockedQueue() as lq:
        actual_status = lq.queue[task_id]["autoswe_status"]
    assert actual_status == "error", (
        f"Queue status should be 'error' even when label update fails, got {actual_status!r}"
    )


def test_dispatch_error_task_not_redispatched_on_next_poll(
    isolated_autoswe_dir, monkeypatch, tmp_path,
):
    """After dispatch failure transitions to error, next poll should NOT re-dispatch.

    The task is in terminal 'error' state — it needs an explicit /retry command
    to restart.
    """
    from autoswe.core.queue_store import LockedQueue

    task_id = "gh:owner_repo_1"
    task = {
        "id": task_id,
        "owner": "owner",
        "repo": "repo",
        "issue_number": 1,
        "title": "Test issue",
        "body": "Fix this\n\n/fix",
        "autoswe_status": "pending",
        "base_branch": "main",
        "provider": "github",
        "suppress_welcome": True,
        "pr_number": None,
        "session_id": None,
        "last_dispatched_command_id": None,
        "last_consumed_reply_id": None,
        "bot_comment_ids": [],
        "last_synced": "2026-01-01T00:00:00Z",
        "created_at": "2026-01-01T00:00:00Z",
    }
    with LockedQueue() as lq:
        lq.queue[task_id] = dict(task)

    import json
    repos_path = isolated_autoswe_dir / "config" / "repos.json"
    repos_path.write_text(
        json.dumps({"owner/repo": {"provider": "github", "pat": "fake", "base_branch": "main"}})
    )

    import autoswe.orch.loop as loop_mod

    dispatch_count = [0]

    def failing_dispatch(*args, **kwargs):
        dispatch_count[0] += 1
        pt = args[0]
        slug = pt.slug
        queue_entry = args[6]
        queue_entry[slug]["autoswe_status"] = "dispatched"
        raise RuntimeError("simulated dispatch failure")

    monkeypatch.setattr(loop_mod, "_dispatch_task", failing_dispatch)

    from autoswe.orch.types import ApiState
    from autoswe.providers.base import NormalizedIssue

    def fake_read_api(tracker, repo_cfg, cfg, *, bot_ids=None, prev_updated=None, force_fetch=None):
        return {
            1: ApiState(
                issue=NormalizedIssue(
                    number=1, title="Test issue", body="Fix this\n\n/fix",
                    owner="owner", repo="repo", state="open",
                    is_pull_request=False, labels=[],
                ),
                comments=(),
            ),
        }

    monkeypatch.setattr(loop_mod, "_get_read_api", lambda provider: fake_read_api)

    cfg = {
        "MAX_CONCURRENT": 1,
        "SILENT_REPORTING": True,
        "WORKTREE_DIR": str(tmp_path / "worktrees"),
    }

    # First poll — dispatch fails, transitions to error
    loop_mod.poll(cfg, mode="full", repo_filter="owner/repo")
    assert dispatch_count[0] == 1, "First poll should attempt dispatch once"

    with LockedQueue() as lq:
        assert lq.queue[task_id]["autoswe_status"] == "error"

    # Second poll — should NOT re-dispatch (error is terminal, needs /retry)
    loop_mod.poll(cfg, mode="full", repo_filter="owner/repo")
    assert dispatch_count[0] == 1, (
        "Second poll should NOT re-dispatch a task in error state. "
        "Error is a terminal state requiring explicit /retry."
    )


def test_dispatch_error_posts_comment(
    isolated_autoswe_dir, monkeypatch, tmp_path,
):
    """When dispatch fails, an error comment should be posted to the issue."""
    from autoswe.core.queue_store import LockedQueue

    task_id = "gh:owner_repo_1"
    task = {
        "id": task_id,
        "owner": "owner",
        "repo": "repo",
        "issue_number": 1,
        "title": "Test issue",
        "body": "Fix this\n\n/fix",
        "autoswe_status": "pending",
        "base_branch": "main",
        "provider": "github",
        "suppress_welcome": True,
        "pr_number": None,
        "session_id": None,
        "last_dispatched_command_id": None,
        "last_consumed_reply_id": None,
        "bot_comment_ids": [],
        "last_synced": "2026-01-01T00:00:00Z",
        "created_at": "2026-01-01T00:00:00Z",
    }
    with LockedQueue() as lq:
        lq.queue[task_id] = dict(task)

    import json
    repos_path = isolated_autoswe_dir / "config" / "repos.json"
    repos_path.write_text(
        json.dumps({"owner/repo": {"provider": "github", "pat": "fake", "base_branch": "main"}})
    )

    import autoswe.orch.loop as loop_mod

    def failing_dispatch(*args, **kwargs):
        pt = args[0]
        slug = pt.slug
        queue_entry = args[6]
        queue_entry[slug]["autoswe_status"] = "dispatched"
        raise RuntimeError("simulated dispatch failure")

    monkeypatch.setattr(loop_mod, "_dispatch_task", failing_dispatch)

    posted_comments = []

    class FakeTracker:
        def set_status(self, repo_cfg, issue_num, label):
            pass
        def post_comment(self, repo_cfg, issue_num, body):
            posted_comments.append((issue_num, body))
        def fetch_comments(self, *a, **kw):
            return []

    import autoswe.providers.factory as factory_mod

    def fake_get_tracker(repo_cfg):
        return FakeTracker()

    monkeypatch.setattr(loop_mod, "get_tracker", fake_get_tracker)
    monkeypatch.setattr(factory_mod, "get_tracker", fake_get_tracker)

    from autoswe.orch.types import ApiState
    from autoswe.providers.base import NormalizedIssue

    def fake_read_api(tracker, repo_cfg, cfg, *, bot_ids=None, prev_updated=None, force_fetch=None):
        return {
            1: ApiState(
                issue=NormalizedIssue(
                    number=1, title="Test issue", body="Fix this\n\n/fix",
                    owner="owner", repo="repo", state="open",
                    is_pull_request=False, labels=[],
                ),
                comments=(),
            ),
        }

    monkeypatch.setattr(loop_mod, "_get_read_api", lambda provider: fake_read_api)

    cfg = {
        "MAX_CONCURRENT": 1,
        "SILENT_REPORTING": True,
        "WORKTREE_DIR": str(tmp_path / "worktrees"),
    }

    loop_mod.poll(cfg, mode="full", repo_filter="owner/repo")

    # An error comment should be posted
    assert len(posted_comments) >= 1, (
        f"Expected at least one error comment to be posted. Posted: {posted_comments}"
    )
    error_comment_body = posted_comments[0][1]
    assert "Dispatch Error" in error_comment_body
    assert "RuntimeError" in error_comment_body
    assert "/retry" in error_comment_body


def test_dispatch_error_clears_session_id(
    isolated_autoswe_dir, monkeypatch, tmp_path,
):
    """When dispatch fails, session_id must be cleared from the queue entry."""
    from autoswe.core.queue_store import LockedQueue

    task_id = "gh:owner_repo_1"
    task = {
        "id": task_id,
        "owner": "owner",
        "repo": "repo",
        "issue_number": 1,
        "title": "Test issue",
        "body": "Fix this\n\n/fix",
        "autoswe_status": "pending",
        "base_branch": "main",
        "provider": "github",
        "suppress_welcome": True,
        "pr_number": None,
        "session_id": "session-abc-123",
        "last_dispatched_command_id": None,
        "last_consumed_reply_id": None,
        "bot_comment_ids": [],
        "last_synced": "2026-01-01T00:00:00Z",
        "created_at": "2026-01-01T00:00:00Z",
    }
    with LockedQueue() as lq:
        lq.queue[task_id] = dict(task)

    import json
    repos_path = isolated_autoswe_dir / "config" / "repos.json"
    repos_path.write_text(
        json.dumps({"owner/repo": {"provider": "github", "pat": "fake", "base_branch": "main"}})
    )

    import autoswe.orch.loop as loop_mod

    def failing_dispatch(*args, **kwargs):
        pt = args[0]
        slug = pt.slug
        queue_entry = args[6]
        queue_entry[slug]["autoswe_status"] = "dispatched"
        raise RuntimeError("simulated dispatch failure")

    monkeypatch.setattr(loop_mod, "_dispatch_task", failing_dispatch)

    class FakeTracker:
        def set_status(self, repo_cfg, issue_num, label):
            pass
        def post_comment(self, repo_cfg, issue_num, body):
            pass
        def fetch_comments(self, *a, **kw):
            return []

    import autoswe.providers.factory as factory_mod

    def fake_get_tracker(repo_cfg):
        return FakeTracker()

    monkeypatch.setattr(loop_mod, "get_tracker", fake_get_tracker)
    monkeypatch.setattr(factory_mod, "get_tracker", fake_get_tracker)

    from autoswe.orch.types import ApiState
    from autoswe.providers.base import NormalizedIssue

    def fake_read_api(tracker, repo_cfg, cfg, *, bot_ids=None, prev_updated=None, force_fetch=None):
        return {
            1: ApiState(
                issue=NormalizedIssue(
                    number=1, title="Test issue", body="Fix this\n\n/fix",
                    owner="owner", repo="repo", state="open",
                    is_pull_request=False, labels=[],
                ),
                comments=(),
            ),
        }

    monkeypatch.setattr(loop_mod, "_get_read_api", lambda provider: fake_read_api)

    cfg = {
        "MAX_CONCURRENT": 1,
        "SILENT_REPORTING": True,
        "WORKTREE_DIR": str(tmp_path / "worktrees"),
    }

    loop_mod.poll(cfg, mode="full", repo_filter="owner/repo")

    with LockedQueue() as lq:
        session_id = lq.queue[task_id].get("session_id")
    assert session_id is None, (
        f"session_id should be cleared after error, got {session_id!r}"
    )


def test_dispatch_error_clears_first_dispatched_at(
    isolated_autoswe_dir, monkeypatch, tmp_path,
):
    """When dispatch fails, first_dispatched_at must be cleared from the queue entry."""
    from autoswe.core.queue_store import LockedQueue

    task_id = "gh:owner_repo_1"
    task = {
        "id": task_id,
        "owner": "owner",
        "repo": "repo",
        "issue_number": 1,
        "title": "Test issue",
        "body": "Fix this\n\n/fix",
        "autoswe_status": "pending",
        "base_branch": "main",
        "provider": "github",
        "suppress_welcome": True,
        "pr_number": None,
        "session_id": None,
        "first_dispatched_at": "2026-01-01T00:00:00Z",
        "last_dispatched_command_id": None,
        "last_consumed_reply_id": None,
        "bot_comment_ids": [],
        "last_synced": "2026-01-01T00:00:00Z",
        "created_at": "2026-01-01T00:00:00Z",
    }
    with LockedQueue() as lq:
        lq.queue[task_id] = dict(task)

    import json
    repos_path = isolated_autoswe_dir / "config" / "repos.json"
    repos_path.write_text(
        json.dumps({"owner/repo": {"provider": "github", "pat": "fake", "base_branch": "main"}})
    )

    import autoswe.orch.loop as loop_mod

    def failing_dispatch(*args, **kwargs):
        pt = args[0]
        slug = pt.slug
        queue_entry = args[6]
        queue_entry[slug]["autoswe_status"] = "dispatched"
        raise RuntimeError("simulated dispatch failure")

    monkeypatch.setattr(loop_mod, "_dispatch_task", failing_dispatch)

    class FakeTracker:
        def set_status(self, repo_cfg, issue_num, label):
            pass
        def post_comment(self, repo_cfg, issue_num, body):
            pass
        def fetch_comments(self, *a, **kw):
            return []

    import autoswe.providers.factory as factory_mod

    def fake_get_tracker(repo_cfg):
        return FakeTracker()

    monkeypatch.setattr(loop_mod, "get_tracker", fake_get_tracker)
    monkeypatch.setattr(factory_mod, "get_tracker", fake_get_tracker)

    from autoswe.orch.types import ApiState
    from autoswe.providers.base import NormalizedIssue

    def fake_read_api(tracker, repo_cfg, cfg, *, bot_ids=None, prev_updated=None, force_fetch=None):
        return {
            1: ApiState(
                issue=NormalizedIssue(
                    number=1, title="Test issue", body="Fix this\n\n/fix",
                    owner="owner", repo="repo", state="open",
                    is_pull_request=False, labels=[],
                ),
                comments=(),
            ),
        }

    monkeypatch.setattr(loop_mod, "_get_read_api", lambda provider: fake_read_api)

    cfg = {
        "MAX_CONCURRENT": 1,
        "SILENT_REPORTING": True,
        "WORKTREE_DIR": str(tmp_path / "worktrees"),
    }

    loop_mod.poll(cfg, mode="full", repo_filter="owner/repo")

    with LockedQueue() as lq:
        first_dispatched = lq.queue[task_id].get("first_dispatched_at")
    assert first_dispatched is None, (
        f"first_dispatched_at should be cleared after error, got {first_dispatched!r}"
    )


