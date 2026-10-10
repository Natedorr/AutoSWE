"""Layer A — decide() state machine tests.

Each test loads a fixture from tests/fixtures/decide/<name>/ :
  world.json          — ApiState + TaskState + cfg + repo_cfg
  expected_action.json — the Action decide() must return

Provider-agnostic: a decide test runs the same regardless of GH vs ADO origin.
"""
from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

from autoswe.orch.decide import _resume_kind, decide
from autoswe.orch.types import (
    Action,
    ApiState,
    TaskState,
    World,
)
from autoswe.providers.base import CIStatus, NormalizedComment, NormalizedIssue
from autoswe.tracking.labels import CI_WATCH_STATUSES

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "decide"


# ---------------------------------------------------------------------------
# Fixture loaders
# ---------------------------------------------------------------------------


def _load_world(data: dict) -> World:
    """Construct a World from a fixture dict."""
    api_data = data["api"]
    task_data = data["task"]
    issue_data = api_data["issue"]

    issue = NormalizedIssue(
        number=issue_data["number"],
        title=issue_data.get("title", ""),
        body=issue_data.get("body", ""),
        owner=issue_data.get("owner", ""),
        repo=issue_data.get("repo", ""),
        state=issue_data.get("state", "open"),
        base_branch=issue_data.get("base_branch", "main"),
        labels=issue_data.get("labels", []),
        status=issue_data.get("status"),
        creator_login=issue_data.get("creator_login", ""),
    )

    comments = tuple(
        NormalizedComment(
            body=c["body"],
            created_at=c.get("created_at", ""),
            author_login=c.get("author_login", ""),
            raw_author_login=c.get("raw_author_login", ""),
            id=c.get("id"),
            is_bot=c.get("is_bot", False),
        )
        for c in api_data.get("comments", [])
    )

    api = ApiState(
        issue=issue,
        comments=comments,
    )

    task = TaskState(
        slug=task_data["slug"],
        owner=task_data.get("owner", ""),
        repo=task_data.get("repo", ""),
        issue_number=task_data.get("issue_number", 0),
        title=task_data.get("title", ""),
        body=task_data.get("body", ""),
        status=task_data.get("status"),
        plan_branch=task_data.get("plan_branch"),
        base_branch=task_data.get("base_branch", "main"),
        attempt_count=task_data.get("attempt_count", 0),
        first_dispatched_at=task_data.get("first_dispatched_at"),
        last_dispatched_command=task_data.get("last_dispatched_command"),
        last_dispatched_command_id=task_data.get("last_dispatched_command_id"),
        last_consumed_reply_id=task_data.get("last_consumed_reply_id"),
        session_id=task_data.get("session_id"),
        pr_number=task_data.get("pr_number"),
        guard_blocked=task_data.get("guard_blocked", False),
        gh_closed=task_data.get("gh_closed", False),
        pending_command=task_data.get("pending_command"),
        pending_guidance=task_data.get("pending_guidance"),
        pending_user_reply=task_data.get("pending_user_reply"),
        suppress_welcome=task_data.get("suppress_welcome", False),
        welcome_comment_id=task_data.get("welcome_comment_id"),
        bot_comment_ids=tuple(task_data.get("bot_comment_ids", [])),
        last_phase=task_data.get("last_phase", "plan"),
        resume_phase=task_data.get("resume_phase"),
        created_at=task_data.get("created_at", ""),
        last_synced=task_data.get("last_synced", ""),
        provider=task_data.get("provider", "github"),
        rereview_after_fix=task_data.get("rereview_after_fix", False),
        ci_failed_from_status=task_data.get("ci_failed_from_status"),
        ci_last_notified_sha=task_data.get("ci_last_notified_sha"),
        ci_error_notified=task_data.get("ci_error_notified", False),
        ci_error_notified_sha=task_data.get("ci_error_notified_sha"),
        gate_attempt_count=task_data.get("gate_attempt_count", 0),
        gate_last_fixed_sha=task_data.get("gate_last_fixed_sha"),
        test_failed_sha=task_data.get("test_failed_sha"),
        test_failure_detail=task_data.get("test_failure_detail"),
        test_gate_limit_notified=task_data.get("test_gate_limit_notified", False),
        pr_deferred=task_data.get("pr_deferred", False),
    )

    cfg = _default_cfg()
    cfg.update(data.get("cfg", {}))
    # Parse ALLOWED_AUTHORS from string if set
    if isinstance(cfg.get("ALLOWED_AUTHORS"), str):
        cfg["ALLOWED_AUTHORS"] = {a.strip() for a in cfg["ALLOWED_AUTHORS"].split(",") if a.strip()}

    ci_data = data.get("ci")
    ci = CIStatus(**ci_data) if ci_data is not None else None

    return World(
        api=api,
        task=task,
        cfg=cfg,
        repo_cfg=data.get("repo_cfg", {}),
        ci=ci,
    )


def _load_action(data: dict) -> Action:
    """Construct an Action from a fixture dict."""
    return Action(
        kind=data["kind"],
        slug=data["slug"],
        plan_branch=data.get("plan_branch"),
        guidance=data.get("guidance"),
        resume_session_id=data.get("resume_session_id"),
        attempt_count=data.get("attempt_count", 0),
        triggering_comment_id=data.get("triggering_comment_id"),
        user_reply_text=data.get("user_reply_text"),
        limit_reason=data.get("limit_reason"),
        refused_command=data.get("refused_command"),
        trigger=data.get("trigger"),
    )


def _default_cfg(overrides: dict | None = None) -> dict:
    """Return a minimal config with sensible defaults for testing."""
    cfg = {
        "MAX_ATTEMPTS": 3,
        "MAX_TOTAL_HOURS": 2,
        "MAX_CONCURRENT": 1,
        "AUTO_ASSIGN": True,
        "ASSIGN_USER": "",
        "SILENT_REPORTING": False,
        "BOT_NAME": "autoswe",
        "ALLOWED_AUTHORS": set(),
    }
    if overrides:
        cfg.update(overrides)
    return cfg


# ---------------------------------------------------------------------------
# Fixture discovery
# ---------------------------------------------------------------------------


def _discover_fixtures() -> list[Path]:
    if not FIXTURE_DIR.exists():
        return []
    return sorted(d for d in FIXTURE_DIR.iterdir() if d.is_dir())


@pytest.mark.parametrize("scenario", _discover_fixtures(), ids=lambda p: p.name)
def test_decide(scenario: Path):
    """Parametrized decide test: world.json -> expected_action.json."""
    world = _load_world(json.loads((scenario / "world.json").read_text(encoding="utf-8")))
    expected = _load_action(json.loads((scenario / "expected_action.json").read_text(encoding="utf-8")))
    actual = decide(world)

    # Compare the key fields that matter for the state machine
    assert actual.kind == expected.kind, f"kind: expected={expected.kind!r} actual={actual.kind!r}"
    assert actual.slug == expected.slug
    assert actual.plan_branch == expected.plan_branch, f"plan_branch: expected={expected.plan_branch!r} actual={actual.plan_branch!r}"
    assert actual.guidance == expected.guidance
    assert actual.attempt_count == expected.attempt_count, f"attempt_count: expected={expected.attempt_count} actual={actual.attempt_count}"
    assert actual.resume_session_id == expected.resume_session_id
    assert actual.user_reply_text == expected.user_reply_text
    assert actual.limit_reason == expected.limit_reason, f"limit_reason: expected={expected.limit_reason!r} actual={actual.limit_reason!r}"
    assert actual.refused_command == expected.refused_command, f"refused_command: expected={expected.refused_command!r} actual={actual.refused_command!r}"
    assert actual.trigger == expected.trigger, f"trigger: expected={expected.trigger!r} actual={actual.trigger!r}"


# ---------------------------------------------------------------------------
# World.ci is only consumed by decide() for tasks resting in a CI-watched
# status (fixed/shipped/synced/ci_failed — see CI_WATCH_STATUSES and
# _decide_ci; issue #245 plan §2.3, P3). For every other status/scenario in
# this fixture set it must remain inert, exactly as it was under P2 (report
# -only). This asserts BOTH that the default is None AND that populating it
# with a real CIStatus (any state) changes nothing for a non-watched task.
# The CI-watched statuses now legitimately change decide()'s output — those
# branches are covered by the dedicated ci_* fixtures instead.
# ---------------------------------------------------------------------------

def _non_ci_watched_fixtures() -> list[Path]:
    fixtures = []
    for scenario in _discover_fixtures():
        task = json.loads((scenario / "world.json").read_text(encoding="utf-8"))["task"]
        if task.get("status") not in CI_WATCH_STATUSES:
            fixtures.append(scenario)
    return fixtures


@pytest.mark.parametrize("scenario", _non_ci_watched_fixtures(), ids=lambda p: p.name)
@pytest.mark.parametrize(
    "ci",
    [
        CIStatus(state="failure", summary="1 check(s) failing: build"),
        CIStatus(state="success"),
        CIStatus(state="error"),
        CIStatus(state="pending"),
    ],
    ids=["failure", "success", "error", "pending"],
)
def test_decide_ignores_world_ci_outside_watch_statuses(scenario: Path, ci: CIStatus):
    """Populating World.ci must not change decide()'s output for a task whose
    status isn't in CI_WATCH_STATUSES — read_ci never populates world.ci for
    those in production, and _decide_ci short-circuits on the status check."""
    world = _load_world(json.loads((scenario / "world.json").read_text(encoding="utf-8")))
    assert world.ci is None  # default when the loader doesn't set it

    baseline = decide(world)
    with_ci = decide(dataclasses.replace(world, ci=ci))

    assert with_ci.kind == baseline.kind
    assert with_ci.slug == baseline.slug
    assert with_ci.plan_branch == baseline.plan_branch
    assert with_ci.guidance == baseline.guidance
    assert with_ci.attempt_count == baseline.attempt_count
    assert with_ci.resume_session_id == baseline.resume_session_id
    assert with_ci.user_reply_text == baseline.user_reply_text
    assert with_ci.limit_reason == baseline.limit_reason
    assert with_ci.refused_command == baseline.refused_command


# ---------------------------------------------------------------------------
# _resume_kind unit tests — Issue #27 regression
# ---------------------------------------------------------------------------

def test_resume_kind_resume_phase_plan_overrides_last_phase_fix():
    """resume_phase='plan' overrides last_phase='fix'. This is the core fix
    for issue #27: planning session resuming as 'fixing' after a question."""
    task = TaskState(
        slug="gh:owner_repo_42", owner="owner", repo="repo",
        issue_number=42, title="T", body="B", status="waiting",
        plan_branch=None, base_branch="main", attempt_count=1,
        first_dispatched_at=None, last_dispatched_command="/plan",
        last_dispatched_command_id=1, last_consumed_reply_id=1,
        session_id="s1", pr_number=None, guard_blocked=False,
        gh_closed=False, pending_command=None, pending_guidance=None,
        pending_user_reply=None,
        last_phase="fix",           # stale from a previous /fix dispatch
        resume_phase="plan",        # authoritative — planner was last to emit
    )
    assert _resume_kind(task) == "plan"


def test_resume_kind_resume_phase_fix():
    """resume_phase='fix' correctly returns 'fix'."""
    task = TaskState(
        slug="gh:owner_repo_42", owner="owner", repo="repo",
        issue_number=42, title="T", body="B", status="waiting",
        plan_branch=None, base_branch="main", attempt_count=1,
        first_dispatched_at=None, last_dispatched_command="/fix",
        last_dispatched_command_id=1, last_consumed_reply_id=1,
        session_id="s1", pr_number=None, guard_blocked=False,
        gh_closed=False, pending_command=None, pending_guidance=None,
        pending_user_reply=None,
        last_phase="fix",
        resume_phase="fix",
    )
    assert _resume_kind(task) == "fix"


def test_resume_kind_fallback_to_last_phase():
    """When resume_phase is None (old queue entry), fall back to last_phase."""
    task = TaskState(
        slug="gh:owner_repo_42", owner="owner", repo="repo",
        issue_number=42, title="T", body="B", status="waiting",
        plan_branch=None, base_branch="main", attempt_count=1,
        first_dispatched_at=None, last_dispatched_command="/fix",
        last_dispatched_command_id=1, last_consumed_reply_id=1,
        session_id="s1", pr_number=None, guard_blocked=False,
        gh_closed=False, pending_command=None, pending_guidance=None,
        pending_user_reply=None,
        last_phase="fix",
        resume_phase=None,
    )
    assert _resume_kind(task) == "fix"


def test_resume_kind_default_to_plan():
    """When both resume_phase and last_phase default, returns 'plan'."""
    task = TaskState(
        slug="gh:owner_repo_42", owner="owner", repo="repo",
        issue_number=42, title="T", body="B", status="waiting",
        plan_branch=None, base_branch="main", attempt_count=1,
        first_dispatched_at=None, last_dispatched_command=None,
        last_dispatched_command_id=None, last_consumed_reply_id=None,
        session_id=None, pr_number=None, guard_blocked=False,
        gh_closed=False, pending_command=None, pending_guidance=None,
        pending_user_reply=None,
    )
    assert _resume_kind(task) == "plan"


# ---------------------------------------------------------------------------
# Review verdict gating — decide() (issue: review verdict ignored)
# ---------------------------------------------------------------------------


def _review_world(status: str, comments: list[dict], *, rereview_after_fix: bool = False,
                  last_dispatched_command: str = "/review",
                  last_dispatched_command_id: int = 10) -> World:
    """Build a World for a review-gating scenario."""
    issue = NormalizedIssue(
        number=42, title="T", body="/plan", owner="owner", repo="repo", state="open",
    )
    api = ApiState(
        issue=issue,
        comments=tuple(
            NormalizedComment(
                body=c["body"], created_at=c.get("created_at", ""),
                author_login=c.get("author_login", "owner"),
                raw_author_login=c.get("raw_author_login", "owner"),
                id=c.get("id"), is_bot=c.get("is_bot", False),
            )
            for c in comments
        ),
    )
    task = TaskState(
        slug="gh:owner_repo_42", owner="owner", repo="repo", issue_number=42,
        title="T", body="/plan", status=status, plan_branch="autoswe/issue-42",
        base_branch="main", attempt_count=1, first_dispatched_at=None,
        last_dispatched_command=last_dispatched_command,
        last_dispatched_command_id=last_dispatched_command_id,
        last_consumed_reply_id=last_dispatched_command_id,
        session_id="s-fix-42", pr_number=None, guard_blocked=False,
        gh_closed=False, pending_command=None, pending_guidance=None,
        pending_user_reply=None,
        rereview_after_fix=rereview_after_fix,
    )
    return World(api=api, task=task, cfg=_default_cfg(), repo_cfg={})


def test_pr_blocked_when_review_blocked():
    """/pr on a review_blocked task must NOT ship — decide returns noop."""
    world = _review_world(
        "review_blocked",
        [
            {"body": "## Review\n\nBlocked.\n<!-- autoswe-bot -->", "created_at": "t1", "id": 10, "is_bot": True},
            {"body": "/pr", "created_at": "t2", "id": 11},
        ],
    )
    action = decide(world)
    assert action.kind == "noop", "review_blocked must block /pr"


def test_pr_blocked_when_review_failed():
    """/pr on a review_failed task must NOT ship — decide returns noop."""
    world = _review_world(
        "review_failed",
        [
            {"body": "## Review\n\nNeeds changes.\n<!-- autoswe-bot -->", "created_at": "t1", "id": 10, "is_bot": True},
            {"body": "/pr", "created_at": "t2", "id": 11},
        ],
    )
    action = decide(world)
    assert action.kind == "noop", "review_failed must block /pr"


def test_fix_allowed_from_review_blocked():
    """/fix on a review_blocked task dispatches a fix (so findings can be addressed)."""
    world = _review_world(
        "review_blocked",
        [
            {"body": "## Review\n\nBlocked.\n<!-- autoswe-bot -->", "created_at": "t1", "id": 10, "is_bot": True},
            {"body": "/fix", "created_at": "t2", "id": 11},
        ],
    )
    action = decide(world)
    assert action.kind == "fix"
    assert action.triggering_comment_id == 11


def test_auto_rereview_after_fix_from_review():
    """A completed fix flagged rereview_after_fix auto-dispatches /review."""
    world = _review_world(
        "fixed",
        [
            {"body": "## Review\n\nBlocked.\n<!-- autoswe-bot -->", "created_at": "t1", "id": 10, "is_bot": True},
            {"body": "/fix", "created_at": "t2", "id": 11},
            {"body": "Completed with command `/fix`.\n<!-- autoswe-bot -->", "created_at": "t3", "id": 12, "is_bot": True},
        ],
        rereview_after_fix=True,
        last_dispatched_command="/fix",
        last_dispatched_command_id=11,
    )
    action = decide(world)
    assert action.kind == "review", "fix completing with rereview flag must re-review"


def test_auto_rereview_suppressed_by_new_user_comment():
    """If the user posts a new command after the fix, auto-rereview yields to it."""
    world = _review_world(
        "fixed",
        [
            {"body": "## Review\n\nBlocked.\n<!-- autoswe-bot -->", "created_at": "t1", "id": 10, "is_bot": True},
            {"body": "/fix", "created_at": "t2", "id": 11},
            {"body": "Completed with command `/fix`.\n<!-- autoswe-bot -->", "created_at": "t3", "id": 12, "is_bot": True},
            {"body": "/skip", "created_at": "t4", "id": 13},
        ],
        rereview_after_fix=True,
        last_dispatched_command="/fix",
        last_dispatched_command_id=11,
    )
    action = decide(world)
    assert action.kind != "review", "a newer user command must take priority over auto-rereview"
