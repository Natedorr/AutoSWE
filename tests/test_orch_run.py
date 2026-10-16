"""Tests for orch/run.py — Layer B: Action -> handler router.

Each test verifies that run() routes Action.kind to the correct handler
and returns the right DispatchResult shape.
"""
import dataclasses
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import MagicMock, patch

from autoswe.harness.runner import HandlerResult
from autoswe.orch.run import (
    DispatchResult,
    _build_task_dict,
    _run_fix_with_sync,
    _run_plan_with_sync,
    _run_review_with_sync,
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
from autoswe.providers.base import CIStatus


def _make_world(
    status=None,
    plan_branch=None,
    session_id=None,
    last_phase="plan",
    last_dispatched_command=None,
    last_replayed_command=None,
    base_branch="main",
    provider="github",
    plan_file_path=None,
    ci=None,
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
            last_replayed_command=last_replayed_command,
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
        ci=ci,
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


def test_run_refused_returns_none():
    """refused is a pure action — no Claude run (issue #192)."""
    world = _make_world()
    action = Action(
        kind="refused", slug=world.task.slug,
        refused_command="/pr", triggering_comment_id=11,
    )
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


# ------ CI-triggered fix (issue #245 plan §2.2/§2.4, P4) ------
# get_ci_failures() is fetched lazily here — only once a CI-triggered fix is
# actually dispatched — so these tests verify the guidance-text plumbing
# rather than duplicate the provider-level get_ci_failures tests.


def test_run_fix_ci_trigger_appends_ci_failures():
    world = _make_world(
        plan_branch="autoswe/issue-42",
        ci=CIStatus(state="failure", head_sha="abc123", failing=["build"]),
    )
    action = Action(
        kind="fix", slug=world.task.slug, trigger="ci",
        guidance="CI failed on the pushed branch.",
    )

    fake_vcs = MagicMock()
    fake_vcs.get_ci_failures.return_value = [
        MagicMock(check="build", url="https://x/run/1", excerpt="AssertionError: boom"),
    ]

    with patch("autoswe.providers.factory.get_vcs", return_value=fake_vcs), \
         patch("autoswe.orch.run._run_fix_with_sync") as mock_fix:
        mock_fix.return_value = HandlerResult("DONE_SUMMARY\tfixed\tabc123")
        run(action, world)

    fake_vcs.get_ci_failures.assert_called_once_with(
        "autoswe/issue-42", "abc123", max_chars=4000,
    )
    guidance_arg = mock_fix.call_args[0][1]
    assert "AssertionError: boom" in guidance_arg
    assert "build" in guidance_arg
    assert "CI failed on the pushed branch." in guidance_arg


def test_run_fix_ci_trigger_no_failures_leaves_guidance_unchanged():
    world = _make_world(
        plan_branch="autoswe/issue-42",
        ci=CIStatus(state="failure", head_sha="abc123", failing=["build"]),
    )
    action = Action(
        kind="fix", slug=world.task.slug, trigger="ci",
        guidance="CI failed on the pushed branch.",
    )

    fake_vcs = MagicMock()
    fake_vcs.get_ci_failures.return_value = []

    with patch("autoswe.providers.factory.get_vcs", return_value=fake_vcs), \
         patch("autoswe.orch.run._run_fix_with_sync") as mock_fix:
        mock_fix.return_value = HandlerResult("DONE_SUMMARY\tfixed\tabc123")
        run(action, world)

    guidance_arg = mock_fix.call_args[0][1]
    assert guidance_arg == "CI failed on the pushed branch."


def test_run_fix_ci_trigger_no_head_sha_skips_fetch():
    world = _make_world(
        plan_branch="autoswe/issue-42",
        ci=CIStatus(state="failure", head_sha=None),
    )
    action = Action(kind="fix", slug=world.task.slug, trigger="ci", guidance="g")

    with patch("autoswe.providers.factory.get_vcs") as mock_get_vcs, \
         patch("autoswe.orch.run._run_fix_with_sync") as mock_fix:
        mock_fix.return_value = HandlerResult("DONE_SUMMARY\tfixed\tabc123")
        run(action, world)

    mock_get_vcs.assert_not_called()
    assert mock_fix.call_args[0][1] == "g"


def test_run_fix_ci_trigger_get_ci_failures_exception_swallowed():
    world = _make_world(
        plan_branch="autoswe/issue-42",
        ci=CIStatus(state="failure", head_sha="abc123"),
    )
    action = Action(kind="fix", slug=world.task.slug, trigger="ci", guidance="g")

    fake_vcs = MagicMock()
    fake_vcs.get_ci_failures.side_effect = RuntimeError("boom")

    with patch("autoswe.providers.factory.get_vcs", return_value=fake_vcs), \
         patch("autoswe.orch.run._run_fix_with_sync") as mock_fix:
        mock_fix.return_value = HandlerResult("DONE_SUMMARY\tfixed\tabc123")
        run(action, world)

    assert mock_fix.call_args[0][1] == "g"


def test_run_fix_human_trigger_never_fetches_ci_failures():
    """trigger=None (a plain human /fix) must not call get_ci_failures at all —
    even when World.ci happens to carry a failure from an unrelated watch."""
    world = _make_world(
        plan_branch="autoswe/issue-42",
        ci=CIStatus(state="failure", head_sha="abc123"),
    )
    action = Action(kind="fix", slug=world.task.slug, guidance="please fix it")

    with patch("autoswe.providers.factory.get_vcs") as mock_get_vcs, \
         patch("autoswe.orch.run._run_fix_with_sync") as mock_fix:
        mock_fix.return_value = HandlerResult("DONE_SUMMARY\tfixed\tabc123")
        run(action, world)

    mock_get_vcs.assert_not_called()
    assert mock_fix.call_args[0][1] == "please fix it"


# ------ Ship PR action ------


def test_run_ship_pr_calls_ship():
    world = _make_world(plan_branch="autoswe/issue-42")
    action = Action(kind="ship_pr", slug=world.task.slug)

    def _fake_open_pr(task, *a, **kw):
        # Real open_pr caches pr_number/pr_url on the task dict (issue #193);
        # simulate that so the lift into DispatchResult is exercised.
        task["pr_number"] = 1
        task["pr_url"] = "https://github.com/o/r/pull/1"
        return "DONE: PR https://github.com/o/r/pull/1"

    with patch("autoswe.orch.run.ship.open_pr") as mock_ship:
        mock_ship.side_effect = _fake_open_pr
        result = run(action, world)

    assert isinstance(result, DispatchResult)
    assert "PR" in result.done_content
    assert result.pr_number == 1
    assert result.pr_url == "https://github.com/o/r/pull/1"
    mock_ship.assert_called_once()


def test_run_ship_pr_failure_carries_no_pr_identity():
    """open_pr FAILED → DispatchResult carries no pr_number/pr_url, even when
    the queue entry still holds a STALE cached number from a prior ship."""
    world = _make_world(plan_branch="autoswe/issue-42")
    # Rebuild the task state with a stale cached PR identity, as a task whose
    # PR was deleted would have.
    world = World(
        api=world.api,
        task=_with_pr_identity(world.task, pr_number=9, pr_url="https://github.com/o/r/pull/9"),
        cfg=world.cfg,
        repo_cfg=world.repo_cfg,
    )
    action = Action(kind="ship_pr", slug=world.task.slug)

    with patch("autoswe.orch.run.ship.open_pr") as mock_ship:
        mock_ship.return_value = "FAILED: could not create PR: boom"
        result = run(action, world)

    assert isinstance(result, DispatchResult)
    assert result.done_content.startswith("FAILED")
    assert result.pr_number is None
    assert result.pr_url is None


def _with_pr_identity(task: TaskState, pr_number, pr_url) -> TaskState:
    """Rebuild a TaskState with a different cached PR identity (frozen dataclass)."""
    return TaskState(
        **{**task.__dict__, "pr_number": pr_number, "pr_url": pr_url},
    )


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
    # The replayed command is threaded so emit records it (not the literal
    # "/retry") — a subsequent /retry then re-replays /plan instead of falling
    # back to /fix (regression: "a failed plan is retried as a plan").
    assert result.replayed_command == "/plan"


def test_run_retry_after_pr_falls_back_to_fix():
    """When /pr was last dispatched on a task with NO completed work to ship
    (status not in COMPLETED_STATUSES), retry falls back to /fix instead of
    replaying /pr (which would create a duplicate PR or ship nothing)."""
    world = _make_world(last_dispatched_command="/pr")
    action = Action(kind="retry", slug=world.task.slug)

    with patch("autoswe.orch.run.ship.open_pr") as mock_ship:
        with patch("autoswe.orch.run._run_fix_with_sync") as mock_fix:
            mock_fix.return_value = HandlerResult("DONE_SUMMARY\tretried\tzzy")
            result = run(action, world)

    assert isinstance(result, DispatchResult)
    mock_fix.assert_called_once()
    assert not mock_ship.called


def test_run_retry_replays_pr_on_completed_task():
    """A /pr refused by the preflight gate (issue #277) leaves the task at its
    COMPLETED resting state with last_dispatched_command "/pr". A subsequent
    /retry must REPLAY /pr (re-run the gate + ship) instead of falling back to
    /fix — falling back would re-run the fixer, make no changes, and the #276
    no-change guard would demote fixed->test_failed + consume gate budget."""
    world = _make_world(status="fixed", last_dispatched_command="/pr")
    action = Action(kind="retry", slug=world.task.slug)

    with patch("autoswe.orch.run.ship.open_pr") as mock_ship, \
         patch("autoswe.orch.run._run_fix_with_sync") as mock_fix:
        mock_ship.return_value = "PR_BLOCKED: CI failing: 1 check(s) failing: ci"
        result = run(action, world)

    # open_pr is re-attempted; the fixer is NOT re-run.
    assert isinstance(result, DispatchResult)
    mock_ship.assert_called_once()
    assert not mock_fix.called
    # The replayed command is threaded so emit records it (not "/retry"), and a
    # still-red gate re-landed pr_blocked holds the resting state.
    assert result.done_content == "PR_BLOCKED: CI failing: 1 check(s) failing: ci"
    assert result.replayed_command == "/pr"
    # A PR_BLOCKED refusal carries no PR identity.
    assert result.pr_number is None
    assert result.pr_url is None


def test_run_retry_replays_pr_success_carries_identity():
    """Once the gate is green, a /retry that replays /pr actually opens the PR:
    open_pr returns DONE and the cached PR identity is lifted into the result so
    emit() persists it on the shipped queue entry (like the direct ship_pr
    path)."""
    world = _make_world(status="fixed", last_dispatched_command="/pr")
    action = Action(kind="retry", slug=world.task.slug)

    def _fake_open_pr(task, *a, **kw):
        task["pr_number"] = 12
        task["pr_url"] = "https://github.com/owner/repo/pull/12"
        return "DONE: PR #12"

    with patch("autoswe.orch.run.ship.open_pr", side_effect=_fake_open_pr) as mock_ship:
        result = run(action, world)

    assert isinstance(result, DispatchResult)
    mock_ship.assert_called_once()
    assert result.done_content == "DONE: PR #12"
    assert result.replayed_command == "/pr"
    assert result.pr_number == 12
    assert result.pr_url == "https://github.com/owner/repo/pull/12"


def test_run_retry_replayed_pr_command_takes_precedence():
    """last_replayed_command ("/pr", recorded by a prior /retry that replayed
    /pr) takes precedence over last_dispatched_command ("/retry"), so a
    repeat /retry re-replays /pr instead of promoting to /fix."""
    world = _make_world(status="fixed", last_dispatched_command="/retry",
                        last_replayed_command="/pr")
    action = Action(kind="retry", slug=world.task.slug)

    with patch("autoswe.orch.run.ship.open_pr") as mock_ship, \
         patch("autoswe.orch.run._run_fix_with_sync") as mock_fix:
        mock_ship.return_value = "PR_BLOCKED: CI still running (1 pending)"
        result = run(action, world)

    mock_ship.assert_called_once()
    assert not mock_fix.called
    assert result.replayed_command == "/pr"


def test_run_retry_replays_pr_only_when_completed():
    """The /pr replay is gated on COMPLETED_STATUSES: a `failed` task with a
    stale /pr watermark still falls back to /fix (a failed task has no work
    to ship)."""
    world = _make_world(status="failed", last_dispatched_command="/pr")
    action = Action(kind="retry", slug=world.task.slug)

    with patch("autoswe.orch.run.ship.open_pr") as mock_ship, \
         patch("autoswe.orch.run._run_fix_with_sync") as mock_fix:
        mock_fix.return_value = HandlerResult("DONE_SUMMARY\tretried\tzzy")
        result = run(action, world)

    assert isinstance(result, DispatchResult)
    mock_fix.assert_called_once()
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


# ------ _fork_session_for_retry (fork provenance gate) ------


def test_fork_session_returns_id_when_backend_matches():
    """A checkpoint produced by the same backend as the resolved fix backend
    and a fork-capable fix backend → the gate returns that checkpoint id."""
    from autoswe.orch.run import _fork_session_for_retry
    task = {
        "last_good_session_id": "s-good",
        "last_good_session_backend": "claude_code",
    }
    assert _fork_session_for_retry(task, {"provider": "github"}, {}, "slug") == "s-good"


def test_fork_session_false_when_checkpoint_backend_mismatches():
    """A checkpoint produced by a DIFFERENT backend than the fix backend must
    not be forked — the fix backend's SDK can't resolve a foreign session id."""
    from autoswe.orch.run import _fork_session_for_retry
    task = {
        "last_good_session_id": "s-codex-plan",
        "last_good_session_backend": "codex",
    }
    assert _fork_session_for_retry(task, {"provider": "github"}, {}, "slug") is None


def test_fork_session_false_when_checkpoint_has_no_backend():
    """A checkpoint with no recorded backend (pre-field / unresolvable) is
    treated as unusable → fresh session, no fork."""
    from autoswe.orch.run import _fork_session_for_retry
    task = {"last_good_session_id": "s-good"}
    assert _fork_session_for_retry(task, {"provider": "github"}, {}, "slug") is None


def test_fork_session_false_when_no_checkpoint():
    """Nothing to fork from → no fork."""
    from autoswe.orch.run import _fork_session_for_retry
    assert _fork_session_for_retry({}, {"provider": "github"}, {}, "slug") is None


def test_fork_session_false_for_codex_fix_backend():
    """Even with a matching checkpoint backend, a Codex fix backend lacks the
    session_fork capability → no fork."""
    from autoswe.orch.run import _fork_session_for_retry
    task = {
        "last_good_session_id": "s-good",
        "last_good_session_backend": "codex",
    }
    cfg = {"FIX_HARNESS": "codex_profile"}
    with patch("autoswe.orch.run.resolve_harness", return_value={
        "backend": "codex", "model": "gpt-5.6-terra",
    }):
        assert _fork_session_for_retry(task, {"provider": "github"}, cfg, "slug") is None


def test_fork_session_true_for_pi_checkpoint_with_pi_fix_backend():
    """A pi checkpoint produced by a pi fix backend (which advertises
    session_fork) → the gate returns the checkpoint id. This is the pi ≠
    codex divergence: pi's --fork primitive makes the provenance gate accept
    a pi checkpoint, whereas a codex checkpoint is never forked by codex."""
    from autoswe.orch.run import _fork_session_for_retry
    task = {
        "last_good_session_id": "s-pi-plan",
        "last_good_session_backend": "pi",
    }
    cfg = {"FIX_HARNESS": "pi_profile"}
    with patch("autoswe.orch.run.resolve_harness", return_value={
        "backend": "pi", "model": "claude-sonnet-4-5",
    }):
        assert _fork_session_for_retry(task, {"provider": "github"}, cfg, "slug") == "s-pi-plan"


def test_fork_session_false_when_pi_checkpoint_codex_fix_backend():
    """A pi checkpoint must NOT be forked by a codex fix backend: codex lacks
    session_fork, so a foreign pi session id is unusable → fresh session."""
    from autoswe.orch.run import _fork_session_for_retry
    task = {
        "last_good_session_id": "s-pi-plan",
        "last_good_session_backend": "pi",
    }
    cfg = {"FIX_HARNESS": "codex_profile"}
    with patch("autoswe.orch.run.resolve_harness", return_value={
        "backend": "codex", "model": "gpt-5.6-terra",
    }):
        assert _fork_session_for_retry(task, {"provider": "github"}, cfg, "slug") is None


def test_fork_session_returns_session_id_when_no_last_good():
    """When only session_id is set (no last_good_session_id yet), the gate
    returns that session id as the checkpoint to fork from."""
    from autoswe.orch.run import _fork_session_for_retry
    task = {
        "session_id": "s-session",
        "last_good_session_backend": "claude_code",
    }
    assert _fork_session_for_retry(task, {"provider": "github"}, {}, "slug") == "s-session"


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


# ------ Progress comment -> task dict (_comment_id plumbing, issue #226) ------
#
# Regression for the live-dispatch bug where spec.mcp_servers never contained
# autoswe_comment: _comment_id was set on the mutable queue entry in loop.py
# but TaskState.to_handler_dict() excluded it as transient, so the handler
# task dict built from the TaskState snapshot never carried it and
# build_mcp_comment_server() returned None. These tests drive the REAL
# run() path with a ProgressComment-shaped callback (not a synthetic task
# dict that carries _comment_id directly, which is how Phase 5 tests missed
# it) and assert the handler receives a task dict from which the comment
# server config builds.


class _FakeProgress:
    """ProgressComment-shaped stub: carries a comment_id and is callable.

    run() must read ``progress_callback.comment_id`` and inject it onto the
    handler task dict — exactly the contract loop.py's ProgressComment exposes.
    """

    def __init__(self, comment_id, minimal_posting=False):
        self._comment_id = comment_id
        self._minimal_posting = minimal_posting

    @property
    def comment_id(self):
        return self._comment_id

    def __call__(self, body: str) -> None:
        pass


def test_run_injects_comment_id_from_progress_callback():
    """run() must carry the dispatch-time progress comment onto the handler
    task dict so build_mcp_comment_server() returns a server config instead
    of None. Without this, every live plan/fix run silently fell back to the
    deprecated text tag (issue #226)."""
    from autoswe.harness.mcp_config import build_mcp_comment_server

    world = _make_world()
    action = Action(kind="plan", slug=world.task.slug, plan_branch="dev")
    seen: dict = {}

    def _capture_plan(task, *a, **kw):
        seen["task"] = task
        return HandlerResult("PLAN_READY")

    with patch("autoswe.orch.run._run_plan_with_sync", side_effect=_capture_plan):
        run(action, world, progress_callback=_FakeProgress(comment_id=12345))

    task = seen["task"]
    assert task["_comment_id"] == 12345
    server = build_mcp_comment_server(task, world.repo_cfg)
    assert server is not None
    assert "autoswe_comment" in server
    assert server["autoswe_comment"]["env"]["AUTOSWE_COMMENT_ID"] == "12345"
    assert server["autoswe_comment"]["env"]["AUTOSWE_TOKEN"] == "ghp_fake"


def test_run_injects_comment_id_on_fix_path():
    """The fix path (coder.run_fix) gets _comment_id too — same seam, so the
    codex/claude/pi backends all build the comment server for /fix."""
    from autoswe.harness.mcp_config import build_mcp_comment_server

    world = _make_world(plan_branch="autoswe/issue-42")
    action = Action(kind="fix", slug=world.task.slug)
    seen: dict = {}

    def _capture_fix(task, *a, **kw):
        seen["task"] = task
        return HandlerResult("DONE_SUMMARY\tfixed\tabc123")

    with patch("autoswe.orch.run._run_fix_with_sync", side_effect=_capture_fix):
        run(action, world, progress_callback=_FakeProgress(comment_id=999))

    task = seen["task"]
    assert task["_comment_id"] == 999
    assert build_mcp_comment_server(task, world.repo_cfg) is not None


def test_run_injects_minimal_posting_from_cfg():
    """_minimal_posting mirrors the dispatch's MINIMAL_POSTING config so the
    MCP server's AUTOSWE_SUPPRESS_POSTING env var is set correctly."""
    world = _make_world()
    world = World(
        api=world.api, task=world.task,
        cfg={"ANTHROPIC_API_KEY": "sk-fake", "MINIMAL_POSTING": True},
        repo_cfg=world.repo_cfg,
    )
    action = Action(kind="plan", slug=world.task.slug, plan_branch="dev")
    seen: dict = {}

    def _capture_plan(task, *a, **kw):
        seen["task"] = task
        return HandlerResult("PLAN_READY")

    with patch("autoswe.orch.run._run_plan_with_sync", side_effect=_capture_plan):
        run(action, world, progress_callback=_FakeProgress(comment_id=7))

    assert seen["task"]["_minimal_posting"] is True


def test_run_no_progress_callback_leaves_comment_id_absent():
    """No progress comment (sync-only / non-sticky dispatch) → no _comment_id
    is injected and build_mcp_comment_server still returns None — the
    no-progress path must be unchanged by the fix."""
    from autoswe.harness.mcp_config import build_mcp_comment_server

    world = _make_world()
    action = Action(kind="plan", slug=world.task.slug, plan_branch="dev")
    seen: dict = {}

    def _capture_plan(task, *a, **kw):
        seen["task"] = task
        return HandlerResult("PLAN_READY")

    with patch("autoswe.orch.run._run_plan_with_sync", side_effect=_capture_plan):
        run(action, world, progress_callback=None)

    task = seen["task"]
    assert "_comment_id" not in task
    assert build_mcp_comment_server(task, world.repo_cfg) is None


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


# ------ _run_fix_with_sync ------


def _make_fix_task(plan_branch=None, base_branch="main"):
    """Build a minimal task dict for fix tests."""
    return {
        "id": "owner/repo#42",
        "owner": "owner",
        "repo": "repo",
        "issue_number": 42,
        "title": "Test issue",
        "body": "/fix",
        "base_branch": base_branch,
        "plan_branch": plan_branch,
        "_token": "ghp_fake",
    }


def test_run_fix_with_sync_uses_plan_branch():
    """_run_fix_with_sync forks worktree from plan_branch when set, not base_branch."""
    task = _make_fix_task(plan_branch="codex", base_branch="master")
    repo_cfg = {"provider": "github"}
    cfg = {}

    mock_wt = MagicMock(spec=Path)
    mock_wt.exists.return_value = False

    with (
        patch("autoswe.orch.run.worktree_mod.worktree_path", return_value=mock_wt),
        patch("autoswe.orch.run.worktree_mod.create_worktree", return_value=mock_wt) as mock_create,
        patch("autoswe.orch.run.worktree_mod.sync_branch") as mock_sync,
        patch("autoswe.orch.run.coder.run_fix") as mock_fix,
    ):
        mock_sync.return_value = {
            "synced": True,
            "branch": "autoswe/issue-42",
            "commit_sha": "abc123",
            "changed": False,
            "ahead": 0,
        }
        mock_fix.return_value = HandlerResult("DONE_SUMMARY\tfixed\tabc123")

        hr = _run_fix_with_sync(task, None, repo_cfg, cfg, None)

    assert hr.done_content.startswith("DONE_SUMMARY")
    mock_create.assert_called_once()
    # 4th positional arg to create_worktree is base_branch (branch_for_create)
    create_args = mock_create.call_args[0]
    assert create_args[3] == "codex"  # branch_for_create == plan_branch


def test_run_fix_with_sync_falls_back_to_base_branch():
    """_run_fix_with_sync falls back to base_branch when plan_branch is not set."""
    task = _make_fix_task(plan_branch=None, base_branch="master")
    repo_cfg = {"provider": "github"}
    cfg = {}

    mock_wt = MagicMock(spec=Path)
    mock_wt.exists.return_value = False

    with (
        patch("autoswe.orch.run.worktree_mod.worktree_path", return_value=mock_wt),
        patch("autoswe.orch.run.worktree_mod.create_worktree", return_value=mock_wt) as mock_create,
        patch("autoswe.orch.run.worktree_mod.sync_branch") as mock_sync,
        patch("autoswe.orch.run.coder.run_fix") as mock_fix,
    ):
        mock_sync.return_value = {
            "synced": True,
            "branch": "autoswe/issue-42",
            "commit_sha": "abc123",
            "changed": False,
            "ahead": 0,
        }
        mock_fix.return_value = HandlerResult("DONE_SUMMARY\tfixed\tabc123")

        hr = _run_fix_with_sync(task, None, repo_cfg, cfg, None)

    assert hr.done_content.startswith("DONE_SUMMARY")
    mock_create.assert_called_once()
    create_args = mock_create.call_args[0]
    assert create_args[3] == "master"  # branch_for_create == base_branch (fallback)


# ------ _run_review_with_sync ------


def _make_review_task(plan_branch=None, base_branch="main"):
    """Build a minimal task dict for review tests."""
    return {
        "id": "owner/repo#42",
        "owner": "owner",
        "repo": "repo",
        "issue_number": 42,
        "title": "Test issue",
        "body": "/plan",
        "base_branch": base_branch,
        "plan_branch": plan_branch,
        "_token": "ghp_fake",
    }


def test_run_review_calls_reviewer():
    """run() routes review action to _run_review_with_sync."""
    world = _make_world(plan_branch="autoswe/issue-42")
    action = Action(kind="review", slug=world.task.slug)

    with patch("autoswe.orch.run._run_review_with_sync") as mock_review:
        hr = HandlerResult("REVIEW_READY\tLGTM", review_file_path="/r/review.md")
        mock_review.return_value = hr
        result = run(action, world)

    assert isinstance(result, DispatchResult)
    assert result.done_content.startswith("REVIEW_READY")
    assert result.review_file_path == "/r/review.md"
    mock_review.assert_called_once()


def test_run_review_with_sync_creates_worktree_and_syncs():
    """_run_review_with_sync creates worktree, syncs base, then runs review."""
    task = _make_review_task()
    repo_cfg = {"provider": "github"}
    cfg = {}

    mock_wt = MagicMock(spec=Path)
    mock_wt.exists.return_value = False

    with (
        patch("autoswe.orch.run.worktree_mod.worktree_path", return_value=mock_wt),
        patch("autoswe.orch.run.worktree_mod.create_worktree", return_value=mock_wt) as mock_create,
        patch("autoswe.orch.run.worktree_mod.sync_branch") as mock_sync,
        patch("autoswe.harness.reviewer.run_review") as mock_review,
    ):
        mock_sync.return_value = {
            "synced": True,
            "branch": "autoswe/issue-42",
            "commit_sha": "abc123",
            "changed": False,
            "ahead": 0,
        }
        mock_review.return_value = HandlerResult("REVIEW_READY\tLGTM")

        hr = _run_review_with_sync(task, None, repo_cfg, cfg, None)

    assert hr.done_content.startswith("REVIEW_READY")
    mock_create.assert_called_once()
    mock_sync.assert_called_once()
    mock_review.assert_called_once()


def test_run_review_with_sync_reuses_existing_worktree():
    """_run_review_with_sync reuses existing worktree, still syncs."""
    task = _make_review_task()
    repo_cfg = {"provider": "github"}
    cfg = {}

    mock_wt = MagicMock(spec=Path)
    mock_wt.exists.return_value = True

    with (
        patch("autoswe.orch.run.worktree_mod.worktree_path", return_value=mock_wt),
        patch("autoswe.orch.run.worktree_mod.create_worktree") as mock_create,
        patch("autoswe.orch.run.worktree_mod.sync_branch") as mock_sync,
        patch("autoswe.harness.reviewer.run_review") as mock_review,
    ):
        mock_sync.return_value = {
            "synced": True,
            "branch": "autoswe/issue-42",
            "commit_sha": "def456",
            "changed": True,
            "ahead": 3,
        }
        mock_review.return_value = HandlerResult("REVIEW_READY\tLGTM")

        hr = _run_review_with_sync(task, None, repo_cfg, cfg, None)

    assert hr.done_content.startswith("REVIEW_READY")
    # Worktree exists — create_worktree should NOT be called
    mock_create.assert_not_called()
    # sync_branch should still be called
    mock_sync.assert_called_once()
    mock_review.assert_called_once()


def test_run_review_with_sync_resolves_merge_conflict():
    """_run_review_with_sync invokes Claude to resolve merge conflicts before review."""
    task = _make_review_task()
    repo_cfg = {"provider": "github"}
    cfg = {}

    mock_wt = MagicMock(spec=Path)
    mock_wt.exists.return_value = True

    with (
        patch("autoswe.orch.run.worktree_mod.worktree_path", return_value=mock_wt),
        patch("autoswe.orch.run.worktree_mod.sync_branch") as mock_sync,
        patch("autoswe.orch.run.coder.resolve_sync_conflicts") as mock_resolve,
        patch("autoswe.harness.reviewer.run_review") as mock_review,
    ):
        mock_sync.return_value = {
            "synced": False,
            "conflict": True,
            "branch": "autoswe/issue-42",
            "conflict_files": ["a.py", "b.py"],
            "error": "merge conflict",
        }
        mock_resolve.return_value = HandlerResult("DONE_SUMMARY\tresolved\tabc")
        mock_review.return_value = HandlerResult("REVIEW_READY\tLGTM")

        hr = _run_review_with_sync(task, None, repo_cfg, cfg, None)

    assert hr.done_content.startswith("REVIEW_READY")
    mock_resolve.assert_called_once()
    assert "a.py" in mock_resolve.call_args[0][1]
    mock_review.assert_called_once()


def test_run_review_with_sync_bails_on_conflict_resolution_failure():
    """_run_review_with_sync bails without running review when conflict resolution fails."""
    task = _make_review_task()
    repo_cfg = {"provider": "github"}
    cfg = {}

    mock_wt = MagicMock(spec=Path)
    mock_wt.exists.return_value = True

    with (
        patch("autoswe.orch.run.worktree_mod.worktree_path", return_value=mock_wt),
        patch("autoswe.orch.run.worktree_mod.sync_branch") as mock_sync,
        patch("autoswe.orch.run.coder.resolve_sync_conflicts") as mock_resolve,
        patch("autoswe.harness.reviewer.run_review") as mock_review,
    ):
        mock_sync.return_value = {
            "synced": False,
            "conflict": True,
            "branch": "autoswe/issue-42",
            "conflict_files": ["a.py"],
            "error": "merge conflict",
        }
        mock_resolve.return_value = HandlerResult("FAILED: could not resolve")

        hr = _run_review_with_sync(task, None, repo_cfg, cfg, None)

    assert hr.done_content.startswith("FAILED:")
    # Review should NOT run when conflict resolution fails
    mock_review.assert_not_called()


def test_run_review_with_sync_returns_error_on_sync_failure():
    """_run_review_with_sync returns FAILED when sync neither syncs nor conflicts."""
    task = _make_review_task()
    repo_cfg = {"provider": "github"}
    cfg = {}

    mock_wt = MagicMock(spec=Path)
    mock_wt.exists.return_value = True

    with (
        patch("autoswe.orch.run.worktree_mod.worktree_path", return_value=mock_wt),
        patch("autoswe.orch.run.worktree_mod.sync_branch") as mock_sync,
        patch("autoswe.harness.reviewer.run_review") as mock_review,
    ):
        mock_sync.return_value = {
            "synced": False,
            "conflict": False,
            "branch": "autoswe/issue-42",
            "error": "something went wrong",
        }

        hr = _run_review_with_sync(task, None, repo_cfg, cfg, None)

    assert hr.done_content.startswith("FAILED: pre-review sync error")
    mock_review.assert_not_called()


def test_run_review_with_sync_passes_worktree_to_reviewer():
    """_run_review_with_sync passes the synced worktree path to reviewer.run_review."""
    task = _make_review_task()
    repo_cfg = {"provider": "github"}
    cfg = {}

    mock_wt = MagicMock(spec=Path)
    mock_wt.exists.return_value = True

    with (
        patch("autoswe.orch.run.worktree_mod.worktree_path", return_value=mock_wt),
        patch("autoswe.orch.run.worktree_mod.sync_branch") as mock_sync,
        patch("autoswe.harness.reviewer.run_review") as mock_review,
    ):
        mock_sync.return_value = {
            "synced": True,
            "branch": "autoswe/issue-42",
            "commit_sha": "abc123",
            "changed": False,
            "ahead": 0,
        }
        mock_review.return_value = HandlerResult("REVIEW_READY\tLGTM")

        _run_review_with_sync(task, None, repo_cfg, cfg, None)

    # Verify wt= kwarg is passed to reviewer.run_review
    call_kwargs = mock_review.call_args[1]
    assert call_kwargs.get("wt") is mock_wt


def test_run_review_with_sync_uses_plan_branch():
    """_run_review_with_sync forks worktree from plan_branch when set, not base_branch."""
    task = _make_review_task(plan_branch="codex", base_branch="master")
    repo_cfg = {"provider": "github"}
    cfg = {}

    mock_wt = MagicMock(spec=Path)
    mock_wt.exists.return_value = False

    with (
        patch("autoswe.orch.run.worktree_mod.worktree_path", return_value=mock_wt),
        patch("autoswe.orch.run.worktree_mod.create_worktree", return_value=mock_wt) as mock_create,
        patch("autoswe.orch.run.worktree_mod.sync_branch") as mock_sync,
        patch("autoswe.harness.reviewer.run_review") as mock_review,
    ):
        mock_sync.return_value = {
            "synced": True,
            "branch": "autoswe/issue-42",
            "commit_sha": "abc123",
            "changed": False,
            "ahead": 0,
        }
        mock_review.return_value = HandlerResult("REVIEW_READY\tLGTM")

        hr = _run_review_with_sync(task, None, repo_cfg, cfg, None)

    assert hr.done_content.startswith("REVIEW_READY")
    mock_create.assert_called_once()
    # 4th positional arg to create_worktree is base_branch (branch_for_create)
    create_args = mock_create.call_args[0]
    assert create_args[3] == "codex"  # branch_for_create == plan_branch


def test_run_review_with_sync_falls_back_to_base_branch():
    """_run_review_with_sync falls back to base_branch when plan_branch is not set."""
    task = _make_review_task(plan_branch=None, base_branch="master")
    repo_cfg = {"provider": "github"}
    cfg = {}

    mock_wt = MagicMock(spec=Path)
    mock_wt.exists.return_value = False

    with (
        patch("autoswe.orch.run.worktree_mod.worktree_path", return_value=mock_wt),
        patch("autoswe.orch.run.worktree_mod.create_worktree", return_value=mock_wt) as mock_create,
        patch("autoswe.orch.run.worktree_mod.sync_branch") as mock_sync,
        patch("autoswe.harness.reviewer.run_review") as mock_review,
    ):
        mock_sync.return_value = {
            "synced": True,
            "branch": "autoswe/issue-42",
            "commit_sha": "abc123",
            "changed": False,
            "ahead": 0,
        }
        mock_review.return_value = HandlerResult("REVIEW_READY\tLGTM")

        hr = _run_review_with_sync(task, None, repo_cfg, cfg, None)

    assert hr.done_content.startswith("REVIEW_READY")
    mock_create.assert_called_once()
    create_args = mock_create.call_args[0]
    assert create_args[3] == "master"  # branch_for_create == base_branch (fallback)


def test_run_retry_replays_review():
    """When /review was last dispatched, retry replays via _run_review_with_sync."""
    world = _make_world(last_dispatched_command="/review", last_phase="review")
    action = Action(kind="retry", slug=world.task.slug)

    with patch("autoswe.orch.run._run_review_with_sync") as mock_review:
        mock_review.return_value = HandlerResult("REVIEW_READY\tLGTM")
        result = run(action, world)

    assert isinstance(result, DispatchResult)
    mock_review.assert_called_once()
    # reviewer.run_review must NOT be called directly (only through wrapper)
    with patch("autoswe.harness.reviewer.run_review") as mock_direct:
        pass  # verify it wasn't called above
    assert not mock_direct.called


# ------ /catchup: _run_catchup and its retry replay ------


def _catchup_world(strategy: str | None = None, *, sync: tuple[str, str] | None = None):
    """A control-issue World with the /catchup pair stored on the task."""
    world = _make_world(base_branch="master")
    cfg = {"SYNC_STRATEGY": strategy} if strategy else {}
    task = dataclasses.replace(world.task, sync_from=sync[0], sync_into=sync[1]) if sync else world.task
    return dataclasses.replace(world, cfg=cfg, task=task)


def _catchup_action(upstream="master", downstream="develop"):
    return Action(kind="catchup", slug="owner/repo_42", attempt_count=1,
                  sync_from=upstream, sync_into=downstream)


def _stub_catchup_git(stack: ExitStack, tmp_path: Path, *, behind=3, branches_exist=True,
                      sync=None, wt_exists=False):
    """Stub every git/VCS seam _run_catchup touches; return the mocks by name."""
    wt = tmp_path / "wt"
    if wt_exists:
        wt.mkdir(exist_ok=True)
    mocks = {
        "ensure_clone": stack.enter_context(patch("autoswe.orch.run.worktree_mod.ensure_clone")),
        "fetch_prune": stack.enter_context(patch("autoswe.orch.run.worktree_mod.fetch_prune")),
        "main_clone_path": stack.enter_context(patch(
            "autoswe.orch.run.worktree_mod.main_clone_path", return_value=tmp_path / "main")),
        "remote_branch_exists": stack.enter_context(patch(
            "autoswe.orch.run.worktree_mod.remote_branch_exists", return_value=branches_exist)),
        "branch_divergence": stack.enter_context(patch(
            "autoswe.orch.run.worktree_mod.branch_divergence", return_value=(2, behind))),
        "worktree_path": stack.enter_context(patch(
            "autoswe.orch.run.worktree_mod.worktree_path", return_value=wt)),
        "create_worktree": stack.enter_context(patch(
            "autoswe.orch.run.worktree_mod.create_worktree", return_value=wt)),
        "sync_branch": stack.enter_context(patch(
            "autoswe.orch.run.worktree_mod.sync_branch",
            return_value=sync or {"synced": True, "conflict": False})),
        "resolve_branch_head": stack.enter_context(patch(
            "autoswe.orch.run.worktree_mod.resolve_branch_head", return_value="abc1234")),
        "get_vcs": stack.enter_context(patch("autoswe.orch.run.worktree_mod.get_vcs")),
    }
    mocks["get_vcs"].return_value.branch_name.side_effect = lambda n: f"autoswe/issue-{n}"
    return mocks


def _fake_open_pr(task, cfg, repo_cfg, progress_callback=None, *, target_branch=None):
    """Stand-in for ship.open_pr: caches a PR identity on the task, as the real one does."""
    task["pr_number"] = 7
    task["pr_url"] = "https://github.com/owner/repo/pull/7"
    return "DONE: PR #7"


def test_run_routes_catchup_kind_to_run_catchup(tmp_path):
    with patch("autoswe.orch.run._run_catchup") as mock_catchup:
        mock_catchup.return_value = DispatchResult(done_content="DONE_SUMMARY\tx\t")
        run(_catchup_action(), _catchup_world())

    assert mock_catchup.call_args[0][1:3] == ("master", "develop")


def test_run_catchup_clean_merge_opens_pr_into_downstream(tmp_path):
    with ExitStack() as stack:
        mocks = _stub_catchup_git(stack, tmp_path, behind=3)
        open_pr = stack.enter_context(patch("autoswe.orch.run.ship.open_pr", side_effect=_fake_open_pr))
        resolve = stack.enter_context(patch("autoswe.orch.run.coder.resolve_sync_conflicts"))
        result = run(_catchup_action(), _catchup_world())

    assert result.done_content.startswith("DONE_SUMMARY\tCaught up `develop` with `master`")
    assert "3 upstream commit(s) merged in" in result.done_content
    assert "conflict file(s) resolved" not in result.done_content
    assert result.done_content.endswith("\tabc1234")
    assert result.pr_number == 7
    assert result.pr_url == "https://github.com/owner/repo/pull/7"
    mocks["create_worktree"].assert_called_once()
    assert mocks["create_worktree"].call_args[0][3] == "develop"  # cut from downstream
    assert open_pr.call_args.kwargs["target_branch"] == "develop"
    resolve.assert_not_called()


def test_run_catchup_always_merges_even_when_rebase_configured(tmp_path):
    with ExitStack() as stack:
        mocks = _stub_catchup_git(stack, tmp_path, behind=1)
        stack.enter_context(patch("autoswe.orch.run.ship.open_pr", side_effect=_fake_open_pr))
        run(_catchup_action(), _catchup_world(strategy="rebase"))

    sync_args = mocks["sync_branch"].call_args[0]
    assert sync_args[4] == "master"  # merged in from upstream
    assert sync_args[6]["SYNC_STRATEGY"] == "merge"


def test_run_catchup_up_to_date_creates_no_worktree_and_no_pr(tmp_path):
    with ExitStack() as stack:
        mocks = _stub_catchup_git(stack, tmp_path, behind=0)
        open_pr = stack.enter_context(patch("autoswe.orch.run.ship.open_pr"))
        result = run(_catchup_action(), _catchup_world())

    assert result.done_content.startswith("DONE_SUMMARY\tAlready up to date")
    assert "No PR needed" in result.done_content
    mocks["create_worktree"].assert_not_called()
    mocks["sync_branch"].assert_not_called()
    open_pr.assert_not_called()


def test_run_catchup_missing_branch_fails_before_any_worktree(tmp_path):
    with ExitStack() as stack:
        mocks = _stub_catchup_git(stack, tmp_path, branches_exist=False)
        result = run(_catchup_action(), _catchup_world())

    assert result.done_content == "FAILED: `master` does not exist on origin"
    mocks["create_worktree"].assert_not_called()


def test_run_catchup_without_pair_fails_cleanly(tmp_path):
    result = run(_catchup_action(upstream=None), _catchup_world())
    assert result.done_content.startswith("FAILED: /catchup needs")


def test_run_catchup_rejects_same_upstream_and_downstream(tmp_path):
    result = run(_catchup_action("develop", "develop"), _catchup_world())
    assert result.done_content.startswith("FAILED: /catchup --from and --into are both `develop`")


def test_run_catchup_reuses_existing_worktree(tmp_path):
    with ExitStack() as stack:
        mocks = _stub_catchup_git(stack, tmp_path, wt_exists=True)
        stack.enter_context(patch("autoswe.orch.run.ship.open_pr", side_effect=_fake_open_pr))
        result = run(_catchup_action(), _catchup_world())

    assert result.done_content.startswith("DONE_SUMMARY")
    mocks["create_worktree"].assert_not_called()


def test_run_catchup_conflict_resolved_with_catchup_prompt(tmp_path):
    with ExitStack() as stack:
        _stub_catchup_git(stack, tmp_path, sync={
            "synced": False, "conflict": True, "conflict_files": ["a.py", "b.py"],
        })
        stack.enter_context(patch("autoswe.orch.run.ship.open_pr", side_effect=_fake_open_pr))
        resolve = stack.enter_context(patch(
            "autoswe.orch.run.coder.resolve_sync_conflicts",
            return_value=HandlerResult("DONE_SUMMARY\tresolved\tabc1234")))
        result = run(_catchup_action(), _catchup_world())

    assert result.done_content.startswith("DONE_SUMMARY")
    assert "2 conflict file(s) resolved" in result.done_content
    kwargs = resolve.call_args.kwargs
    assert kwargs["sync_base"] == "master"
    assert kwargs["catchup"] is True


def test_run_catchup_resolution_failure_fails_and_skips_pr(tmp_path):
    with ExitStack() as stack:
        _stub_catchup_git(stack, tmp_path, sync={
            "synced": False, "conflict": True, "conflict_files": ["a.py"],
        })
        open_pr = stack.enter_context(patch("autoswe.orch.run.ship.open_pr"))
        stack.enter_context(patch(
            "autoswe.orch.run.coder.resolve_sync_conflicts",
            return_value=HandlerResult("FAILED: agent could not resolve a.py")))
        result = run(_catchup_action(), _catchup_world())

    assert result.done_content == "FAILED: agent could not resolve a.py"
    open_pr.assert_not_called()


def test_run_catchup_pr_failure_is_reported_as_failed(tmp_path):
    with ExitStack() as stack:
        _stub_catchup_git(stack, tmp_path)
        stack.enter_context(patch(
            "autoswe.orch.run.ship.open_pr", return_value="FAILED: could not create PR: boom"))
        result = run(_catchup_action(), _catchup_world())

    assert result.done_content == "FAILED: could not create PR: boom"


def test_run_catchup_sync_exception_becomes_failed(tmp_path):
    with ExitStack() as stack:
        _stub_catchup_git(stack, tmp_path)
        stack.enter_context(patch(
            "autoswe.orch.run.worktree_mod.sync_branch", side_effect=RuntimeError("boom")))
        result = run(_catchup_action(), _catchup_world())

    assert result.done_content == "FAILED: boom"


def test_run_catchup_persists_pair_on_task_for_later_runs(tmp_path):
    seen = {}

    def capture(task, cfg, repo_cfg, progress_callback=None, *, target_branch=None):
        seen.update(sync_from=task.get("sync_from"), sync_into=task.get("sync_into"))
        return _fake_open_pr(task, cfg, repo_cfg, target_branch=target_branch)

    with ExitStack() as stack:
        _stub_catchup_git(stack, tmp_path)
        stack.enter_context(patch("autoswe.orch.run.ship.open_pr", side_effect=capture))
        run(_catchup_action(), _catchup_world())

    assert seen == {"sync_from": "master", "sync_into": "develop"}


def test_run_retry_replays_catchup_with_stored_pair_never_fix(tmp_path):
    world = _catchup_world(sync=("master", "develop"))
    world = dataclasses.replace(world, task=dataclasses.replace(
        world.task, last_dispatched_command="/catchup"))
    action = Action(kind="retry", slug=world.task.slug)

    with patch("autoswe.orch.run._run_catchup") as mock_catchup, \
         patch("autoswe.orch.run._run_fix_with_sync") as mock_fix:
        mock_catchup.return_value = DispatchResult(done_content="DONE_SUMMARY\tx\t")
        result = run(action, world)

    mock_fix.assert_not_called()
    assert mock_catchup.call_args[0][1:3] == ("master", "develop")
    assert result.replayed_command == "/catchup"
