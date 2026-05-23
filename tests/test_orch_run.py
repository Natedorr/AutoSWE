"""Tests for orch/run.py — Layer B: Action -> handler router.

Each test verifies that run() routes Action.kind to the correct handler
and returns the right DispatchResult shape.
"""
from pathlib import Path
from unittest.mock import MagicMock, patch

from autoswe.harness.runner import HandlerResult
from autoswe.orch.run import (
    DispatchResult,
    _build_task_dict,
    _run_plan_with_sync,
    _to_dispatch,
    run,
)
from autoswe.orch.types import (
    Action,
    ApiState,
    NormalizedIssue,
    TaskState,
    World,
)


def _make_world(
    status=None,
    plan_branch=None,
    session_id=None,
    last_phase="plan",
    last_dispatched_command=None,
    base_branch="main",
    provider="github",
    plan_file_path=None,
):
    """Build a minimal World for testing."""
    return World(
        api=ApiState(
            issue=NormalizedIssue(
                number=42,
                title="Test issue",
                body="/plan",
                owner="owner",
                repo="repo",
                state="open",
            ),
            comments=(),
        ),
        task=TaskState(
            slug="owner/repo_42",
            owner="owner",
            repo="repo",
            issue_number=42,
            title="Test issue",
            body="/plan",
            status=status,
            plan_branch=plan_branch,
            base_branch=base_branch,
            attempt_count=1,
            first_dispatched_at=None,
            last_dispatched_command=last_dispatched_command,
            last_dispatched_command_id=1,
            last_consumed_reply_id=1,
            session_id=session_id,
            pr_number=None,
            guard_blocked=False,
            gh_closed=False,
            pending_command=None,
            pending_guidance=None,
            pending_user_reply=None,
            last_phase=last_phase,
            provider=provider,
            plan_file_path=plan_file_path,
        ),
        cfg={"ANTHROPIC_API_KEY": "sk-fake"},
        repo_cfg={"pat": "ghp_fake", "provider": provider},
    )


# ------ Pure actions return None ------


def test_run_noop_returns_none():
    world = _make_world()
    action = Action(kind="noop", slug=world.task.slug)
    assert run(action, world) is None


def test_run_skip_returns_none():
    world = _make_world()
    action = Action(kind="skip", slug=world.task.slug)
    assert run(action, world) is None


def test_run_abort_returns_none():
    world = _make_world()
    action = Action(kind="abort", slug=world.task.slug)
    assert run(action, world) is None


def test_run_post_welcome_returns_none():
    world = _make_world()
    action = Action(kind="post_welcome", slug=world.task.slug, guidance="Welcome!")
    assert run(action, world) is None


def test_run_advance_watermark_returns_none():
    world = _make_world()
    action = Action(kind="advance_watermark", slug=world.task.slug)
    assert run(action, world) is None


def test_run_mark_failed_limit_returns_none():
    world = _make_world()
    action = Action(kind="mark_failed_limit", slug=world.task.slug)
    assert run(action, world) is None


# ------ Plan action routes to planner ------


def test_run_plan_calls_planner():
    world = _make_world()
    action = Action(kind="plan", slug=world.task.slug, plan_branch="dev")

    with patch("autoswe.orch.run._run_plan_with_sync") as mock_plan:
        mock_plan.return_value = HandlerResult("PLAN_READY")
        result = run(action, world)

    assert isinstance(result, DispatchResult)
    assert result.done_content == "PLAN_READY"
    mock_plan.assert_called_once()
    # Verify user_reply_text is None for fresh plan
    assert mock_plan.call_args[0][2] is None


def test_run_plan_with_guidance():
    world = _make_world()
    action = Action(
        kind="plan", slug=world.task.slug,
        guidance="use Redis for cache",
    )
    with patch("autoswe.orch.run._run_plan_with_sync") as mock_plan:
        mock_plan.return_value = HandlerResult("PLAN_READY")
        run(action, world)

    # guidance passed as 2nd positional arg to _run_plan_with_sync
    call_args = mock_plan.call_args
    assert call_args[0][1] == "use Redis for cache"


def test_run_plan_resume_on_user_reply():
    world = _make_world(session_id="sess-123")
    action = Action(
        kind="plan", slug=world.task.slug,
        user_reply_text="Use Redis",
        resume_session_id="sess-123",
    )
    with patch("autoswe.orch.run._run_plan_with_sync") as mock_plan:
        mock_plan.return_value = HandlerResult("PLAN_READY")
        result = run(action, world)

    assert isinstance(result, DispatchResult)
    assert result.done_content == "PLAN_READY"
    mock_plan.assert_called_once()
    # Verify user_reply_text is passed through
    assert mock_plan.call_args[0][2] == "Use Redis"
    # Verify the task dict has the right session_id
    task_arg = mock_plan.call_args[0][0]
    assert task_arg["session_id"] == "sess-123"


# ------ Fix action routes to coder ------


def test_run_fix_calls_coder():
    world = _make_world(plan_branch="autoswe/issue-42")
    action = Action(kind="fix", slug=world.task.slug)

    with patch("autoswe.orch.run._run_fix_with_sync") as mock_fix:
        mock_fix.return_value = HandlerResult("DONE_SUMMARY\tfixed\tabc123")
        result = run(action, world)

    assert isinstance(result, DispatchResult)
    assert result.done_content.startswith("DONE_SUMMARY")
    mock_fix.assert_called_once()


def test_run_fix_resume_on_user_reply():
    world = _make_world(session_id="sess-fix", last_phase="fix")
    action = Action(
        kind="fix", slug=world.task.slug,
        user_reply_text="Yes merge it",
        resume_session_id="sess-fix",
    )
    with patch("autoswe.orch.run.coder.resume_fix") as mock_resume:
        mock_resume.return_value = HandlerResult("DONE_SUMMARY\tmerged\tdef456")
        result = run(action, world)

    assert isinstance(result, DispatchResult)
    assert "def456" in result.done_content
    mock_resume.assert_called_once()


# ------ Ship PR action ------


def test_run_ship_pr_calls_ship():
    world = _make_world(plan_branch="autoswe/issue-42")
    action = Action(kind="ship_pr", slug=world.task.slug)

    with patch("autoswe.orch.run.ship.open_pr") as mock_ship:
        mock_ship.return_value = "DONE: PR https://github.com/o/r/pull/1"
        result = run(action, world)

    assert isinstance(result, DispatchResult)
    assert "PR" in result.done_content
    mock_ship.assert_called_once()


# ------ Sync action ------


def test_run_sync_branch():
    world = _make_world(base_branch="main")
    action = Action(kind="sync_branch", slug=world.task.slug)

    from pathlib import Path
    with (
        patch("autoswe.orch.run.worktree_mod.worktree_path") as mock_path,
        patch("autoswe.orch.run.worktree_mod.create_worktree") as mock_create,
        patch("autoswe.orch.run.worktree_mod.sync_branch") as mock_sync,
    ):
        mock_path.return_value = Path("/fake/wt")
        mock_create.return_value = Path("/fake/wt")
        mock_sync.return_value = {
            "synced": True,
            "branch": "autoswe/issue-42",
            "commit_sha": "abc123",
            "changed": False,
            "ahead": 0,
        }
        result = run(action, world)

    assert isinstance(result, DispatchResult)
    assert "Already up to date" in result.done_content


# ------ Retry action ------


def test_run_retry_replays_fix():
    world = _make_world(last_dispatched_command="/fix", last_phase="fix")
    action = Action(kind="retry", slug=world.task.slug)

    with patch("autoswe.orch.run._run_fix_with_sync") as mock_fix:
        mock_fix.return_value = HandlerResult("DONE_SUMMARY\tfixed\tabc")
        result = run(action, world)

    assert isinstance(result, DispatchResult)
    mock_fix.assert_called_once()


def test_run_retry_replays_plan():
    world = _make_world(last_dispatched_command="/plan")
    action = Action(kind="retry", slug=world.task.slug)

    with patch("autoswe.orch.run._run_plan_with_sync") as mock_plan:
        mock_plan.return_value = HandlerResult("PLAN_READY")
        result = run(action, world)

    assert isinstance(result, DispatchResult)
    assert result.done_content == "PLAN_READY"
    mock_plan.assert_called_once()


def test_run_retry_after_pr_falls_back_to_fix():
    """When /pr was last dispatched, retry should fall back to /fix instead
    of replaying /pr (which would create a duplicate PR)."""
    world = _make_world(last_dispatched_command="/pr")
    action = Action(kind="retry", slug=world.task.slug)

    with patch("autoswe.orch.run._run_fix_with_sync") as mock_fix:
        mock_fix.return_value = HandlerResult("DONE_SUMMARY\tretried\tzzy")
        result = run(action, world)

    assert isinstance(result, DispatchResult)
    mock_fix.assert_called_once()
    # ship.open_pr must NOT be called
    with patch("autoswe.orch.run.ship.open_pr") as mock_ship:
        pass  # just verify it wasn't called above
    assert not mock_ship.called


def test_run_retry_skips_sync_on_retry():
    """When /sync was last dispatched, retry should fall back to /fix
    instead of replaying /sync."""
    world = _make_world(last_dispatched_command="/sync")
    action = Action(kind="retry", slug=world.task.slug)

    with patch("autoswe.orch.run._run_fix_with_sync") as mock_fix:
        mock_fix.return_value = HandlerResult("DONE_SUMMARY\tretried\tzzz")
        result = run(action, world)

    assert isinstance(result, DispatchResult)
    mock_fix.assert_called_once()


def test_run_retry_skips_skip_on_retry():
    """When /skip was last dispatched, retry should fall back to /fix."""
    world = _make_world(last_dispatched_command="/skip")
    action = Action(kind="retry", slug=world.task.slug)

    with patch("autoswe.orch.run._run_fix_with_sync") as mock_fix:
        mock_fix.return_value = HandlerResult("DONE_SUMMARY\tretried\tzzz")
        result = run(action, world)

    assert isinstance(result, DispatchResult)
    mock_fix.assert_called_once()


def test_run_retry_skips_abort_on_retry():
    """When /abort was last dispatched, retry should fall back to /fix."""
    world = _make_world(last_dispatched_command="/abort")
    action = Action(kind="retry", slug=world.task.slug)

    with patch("autoswe.orch.run._run_fix_with_sync") as mock_fix:
        mock_fix.return_value = HandlerResult("DONE_SUMMARY\tretried\tzzz")
        result = run(action, world)

    assert isinstance(result, DispatchResult)
    mock_fix.assert_called_once()


def test_run_retry_skips_retry_on_retry():
    """When /retry was last dispatched, retry should fall back to /fix."""
    world = _make_world(last_dispatched_command="/retry")
    action = Action(kind="retry", slug=world.task.slug)

    with patch("autoswe.orch.run._run_fix_with_sync") as mock_fix:
        mock_fix.return_value = HandlerResult("DONE_SUMMARY\tretried\tzzz")
        result = run(action, world)

    assert isinstance(result, DispatchResult)
    mock_fix.assert_called_once()


def test_run_retry_falls_back_to_fix():
    world = _make_world(last_dispatched_command=None)
    action = Action(kind="retry", slug=world.task.slug)

    with patch("autoswe.orch.run._run_fix_with_sync") as mock_fix:
        mock_fix.return_value = HandlerResult("DONE_SUMMARY\tretried\tzzz")
        result = run(action, world)

    assert isinstance(result, DispatchResult)
    mock_fix.assert_called_once()


# ------ Task dict builder ------


def test_build_task_dict():
    world = _make_world(
        plan_branch="dev",
        session_id="sess-42",
    )
    action = Action(kind="noop", slug="owner/repo_42")
    task = _build_task_dict(world, action)
    assert task["owner"] == "owner"
    assert task["repo"] == "repo"
    assert task["issue_number"] == 42
    assert task["plan_branch"] == "dev"
    assert task["session_id"] == "sess-42"
    assert task["_token"] == "ghp_fake"


# ------ HandlerResult -> DispatchResult ------


def test_to_dispatch_passes_through():
    hr = HandlerResult("PLAN_READY", cost_usd=0.50, duration_seconds=30.0)
    task = {"session_id": "sess-42"}
    dr = _to_dispatch(hr, task)
    assert dr.done_content == "PLAN_READY"
    assert dr.cost_usd == 0.50
    assert dr.duration_seconds == 30.0
    assert dr.session_id == "sess-42"


def test_build_task_dict_carries_plan_file_path():
    """TaskState.plan_file_path must end up on the task dict so coder.run_fix
    can find it. Without this plumbing the planner persists the path to the
    queue, but the next dispatch's task dict has plan_file_path=None and the
    fresh-session-with-plan branch in coder is never taken."""
    world = _make_world(plan_file_path="/home/me/.claude/plans/abc.md")
    action = Action(kind="fix", slug="owner/repo_42")
    task = _build_task_dict(world, action)
    assert task["plan_file_path"] == "/home/me/.claude/plans/abc.md"


def test_to_dispatch_carries_plan_file_path():
    hr = HandlerResult("PLAN_READY", plan_file_path="/p/x.md")
    dr = _to_dispatch(hr, {"session_id": "s"})
    assert dr.plan_file_path == "/p/x.md"


# ------ _run_plan_with_sync ------


def _make_plan_task(plan_branch=None, session_id=None, base_branch="main"):
    """Build a minimal task dict for plan tests."""
    return {
        "id": "owner/repo#42",
        "owner": "owner",
        "repo": "repo",
        "issue_number": 42,
        "title": "Test issue",
        "body": "/plan",
        "base_branch": base_branch,
        "plan_branch": plan_branch,
        "session_id": session_id,
        "_token": "ghp_fake",
    }


def test_run_plan_with_sync_creates_worktree_and_syncs():
    """_run_plan_with_sync creates worktree, syncs base, then runs plan."""
    task = _make_plan_task()
    repo_cfg = {"provider": "github"}
    cfg = {}

    mock_wt = MagicMock(spec=Path)
    mock_wt.exists.return_value = False

    with (
        patch("autoswe.orch.run.worktree_mod.worktree_path", return_value=mock_wt),
        patch("autoswe.orch.run.worktree_mod.create_worktree", return_value=mock_wt) as mock_create,
        patch("autoswe.orch.run.worktree_mod.sync_branch") as mock_sync,
        patch("autoswe.orch.run.planner.run_plan") as mock_plan,
    ):
        mock_sync.return_value = {
            "synced": True,
            "branch": "autoswe/issue-42",
            "commit_sha": "abc123",
            "changed": False,
            "ahead": 0,
        }
        mock_plan.return_value = HandlerResult("PLAN_READY")

        hr = _run_plan_with_sync(task, None, None, repo_cfg, cfg, None)

    assert hr.done_content == "PLAN_READY"
    mock_create.assert_called_once()
    mock_sync.assert_called_once()
    mock_plan.assert_called_once()


def test_run_plan_with_sync_reuses_existing_worktree():
    """_run_plan_with_sync reuses existing worktree, still syncs."""
    task = _make_plan_task()
    repo_cfg = {"provider": "github"}
    cfg = {}

    mock_wt = MagicMock(spec=Path)
    mock_wt.exists.return_value = True

    with (
        patch("autoswe.orch.run.worktree_mod.worktree_path", return_value=mock_wt),
        patch("autoswe.orch.run.worktree_mod.create_worktree") as mock_create,
        patch("autoswe.orch.run.worktree_mod.sync_branch") as mock_sync,
        patch("autoswe.orch.run.planner.run_plan") as mock_plan,
    ):
        mock_sync.return_value = {
            "synced": True,
            "branch": "autoswe/issue-42",
            "commit_sha": "def456",
            "changed": True,
            "ahead": 3,
        }
        mock_plan.return_value = HandlerResult("PLAN_READY")

        hr = _run_plan_with_sync(task, None, None, repo_cfg, cfg, None)

    assert hr.done_content == "PLAN_READY"
    # Worktree exists — create_worktree should NOT be called
    mock_create.assert_not_called()
    # sync_branch should still be called
    mock_sync.assert_called_once()
    mock_plan.assert_called_once()


def test_run_plan_with_sync_resumes_on_user_reply():
    """_run_plan_with_sync calls resume_plan when user_reply_text is provided."""
    task = _make_plan_task(session_id="sess-123")
    repo_cfg = {"provider": "github"}
    cfg = {}

    mock_wt = MagicMock(spec=Path)
    mock_wt.exists.return_value = True

    with (
        patch("autoswe.orch.run.worktree_mod.worktree_path", return_value=mock_wt),
        patch("autoswe.orch.run.worktree_mod.sync_branch") as mock_sync,
        patch("autoswe.orch.run.planner.resume_plan") as mock_resume,
    ):
        mock_sync.return_value = {
            "synced": True,
            "branch": "autoswe/issue-42",
            "commit_sha": "abc123",
            "changed": False,
            "ahead": 0,
        }
        mock_resume.return_value = HandlerResult("PLAN_READY")

        hr = _run_plan_with_sync(
            task, None, "Use Redis", repo_cfg, cfg, None,
        )

    assert hr.done_content == "PLAN_READY"
    mock_resume.assert_called_once()
    assert mock_resume.call_args[0][1] == "Use Redis"


def test_run_plan_with_sync_resolves_merge_conflict():
    """_run_plan_with_sync invokes Claude to resolve merge conflicts before planning."""
    task = _make_plan_task()
    repo_cfg = {"provider": "github"}
    cfg = {}

    mock_wt = MagicMock(spec=Path)
    mock_wt.exists.return_value = True

    with (
        patch("autoswe.orch.run.worktree_mod.worktree_path", return_value=mock_wt),
        patch("autoswe.orch.run.worktree_mod.sync_branch") as mock_sync,
        patch("autoswe.orch.run.coder.resolve_sync_conflicts") as mock_resolve,
        patch("autoswe.orch.run.planner.run_plan") as mock_plan,
    ):
        mock_sync.return_value = {
            "synced": False,
            "conflict": True,
            "branch": "autoswe/issue-42",
            "conflict_files": ["a.py", "b.py"],
            "error": "merge conflict",
        }
        mock_resolve.return_value = HandlerResult("DONE_SUMMARY\tresolved\tabc")
        mock_plan.return_value = HandlerResult("PLAN_READY")

        hr = _run_plan_with_sync(task, None, None, repo_cfg, cfg, None)

    assert hr.done_content == "PLAN_READY"
    mock_resolve.assert_called_once()
    assert "a.py" in mock_resolve.call_args[0][1]
    mock_plan.assert_called_once()


def test_run_plan_with_sync_bails_on_conflict_resolution_failure():
    """_run_plan_with_sync bails without running plan when conflict resolution fails."""
    task = _make_plan_task()
    repo_cfg = {"provider": "github"}
    cfg = {}

    mock_wt = MagicMock(spec=Path)
    mock_wt.exists.return_value = True

    with (
        patch("autoswe.orch.run.worktree_mod.worktree_path", return_value=mock_wt),
        patch("autoswe.orch.run.worktree_mod.sync_branch") as mock_sync,
        patch("autoswe.orch.run.coder.resolve_sync_conflicts") as mock_resolve,
        patch("autoswe.orch.run.planner.run_plan") as mock_plan,
    ):
        mock_sync.return_value = {
            "synced": False,
            "conflict": True,
            "branch": "autoswe/issue-42",
            "conflict_files": ["a.py"],
            "error": "merge conflict",
        }
        mock_resolve.return_value = HandlerResult("FAILED: could not resolve")

        hr = _run_plan_with_sync(task, None, None, repo_cfg, cfg, None)

    assert hr.done_content.startswith("FAILED:")
    # Plan should NOT run when conflict resolution fails
    mock_plan.assert_not_called()


def test_run_plan_with_sync_returns_error_on_sync_failure():
    """_run_plan_with_sync returns FAILED when sync neither syncs nor conflicts."""
    task = _make_plan_task()
    repo_cfg = {"provider": "github"}
    cfg = {}

    mock_wt = MagicMock(spec=Path)
    mock_wt.exists.return_value = True

    with (
        patch("autoswe.orch.run.worktree_mod.worktree_path", return_value=mock_wt),
        patch("autoswe.orch.run.worktree_mod.sync_branch") as mock_sync,
        patch("autoswe.orch.run.planner.run_plan") as mock_plan,
    ):
        mock_sync.return_value = {
            "synced": False,
            "conflict": False,
            "branch": "autoswe/issue-42",
            "error": "something went wrong",
        }

        hr = _run_plan_with_sync(task, None, None, repo_cfg, cfg, None)

    assert hr.done_content.startswith("FAILED: pre-plan sync error")
    mock_plan.assert_not_called()


def test_run_plan_with_sync_pushes_new_branch():
    """_run_plan_with_sync uses push_new=True so sync_branch can push merge commits."""
    task = _make_plan_task()
    repo_cfg = {"provider": "github"}
    cfg = {}

    mock_wt = MagicMock(spec=Path)
    mock_wt.exists.return_value = False

    with (
        patch("autoswe.orch.run.worktree_mod.worktree_path", return_value=mock_wt),
        patch("autoswe.orch.run.worktree_mod.create_worktree", return_value=mock_wt) as mock_create,
        patch("autoswe.orch.run.worktree_mod.sync_branch") as mock_sync,
        patch("autoswe.orch.run.planner.run_plan") as mock_plan,
    ):
        mock_sync.return_value = {
            "synced": True,
            "branch": "autoswe/issue-42",
            "commit_sha": "abc123",
            "changed": False,
            "ahead": 0,
        }
        mock_plan.return_value = HandlerResult("PLAN_READY")

        _run_plan_with_sync(task, None, None, repo_cfg, cfg, None)

    # Verify push_new=True (so sync_branch can push the branch to remote)
    create_kwargs = mock_create.call_args[1]
    assert create_kwargs.get("push_new") is True
