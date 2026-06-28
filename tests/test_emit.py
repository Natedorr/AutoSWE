"""Layer C — emit() effect emission tests.

Each test loads a fixture from tests/fixtures/emit/<name>/:
  world.json           — World for emit()
  action.json          — Action to pass to emit()
  result.json          — DispatchResult (null for no-Claude actions)
  expected_effects.json — list of expected effect dicts

Effects are validated by kind + relevant fields (not exact equality):
  set_status     → status matches
  post_comment   → body contains all strings in `contains` list
  patch_queue    → queue_patch contains all key/value pairs from `patch_contains`
  create_pr      → pr_title, pr_head, pr_base match
  assign         → body matches
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from autoswe.orch.emit import emit
from autoswe.orch.run import DispatchResult
from autoswe.orch.types import (
    Action,
    ApiState,
    Effect,
    TaskState,
    World,
)
from autoswe.providers.base import NormalizedComment, NormalizedIssue

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "emit"


# ---------------------------------------------------------------------------
# Loaders
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
            id=c.get("id"),
            is_bot=c.get("is_bot", False),
        )
        for c in api_data.get("comments", [])
    )

    api = ApiState(
        issue=issue,
        comments=comments,
        open_pr_numbers=tuple(api_data.get("open_pr_numbers", [])),
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
        fix_summary=task_data.get("fix_summary", ""),
    )

    cfg = _default_cfg()
    cfg.update(data.get("cfg", {}))

    return World(
        api=api,
        task=task,
        cfg=cfg,
        repo_cfg=data.get("repo_cfg", {}),
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
    )


def _load_result(path: Path) -> DispatchResult | None:
    """Load a DispatchResult from JSON (null = no Claude run)."""
    raw = json.loads(path.read_text())
    if raw is None:
        return None
    return DispatchResult(
        done_content=raw["done_content"],
        cost_usd=raw.get("cost_usd"),
        duration_seconds=raw.get("duration_seconds", 0.0),
        session_id=raw.get("session_id"),
    )


def _default_cfg() -> dict:
    """Return a minimal config with sensible defaults for testing."""
    return {
        "MAX_ATTEMPTS": 3,
        "MAX_TOTAL_HOURS": 2,
        "MAX_CONCURRENT": 1,
        "AUTO_ASSIGN": False,
        "ASSIGN_USER": "",
        "SILENT_REPORTING": False,
        "BOT_NAME": "autoswe",
        "ALLOWED_AUTHORS": set(),
        "AUTO_CREATE_PR": False,
    }


# ---------------------------------------------------------------------------
# Effect assertion helpers
# ---------------------------------------------------------------------------


def assert_effect_matches(actual: Effect, expected: dict) -> None:
    """Assert that a single Effect matches the expected fixture dict.

    Matching rules per effect kind:
      set_status     → expected['status'] must match
      post_comment   → actual.body must contain all strings in expected['contains']
      patch_queue    → actual.queue_patch must contain all K/V from expected['patch_contains']
      create_pr      → pr_title, pr_head, pr_base must match
      assign         → body must match
    """
    assert actual.kind == expected["kind"], (
        f"effect kind: expected={expected['kind']!r} actual={actual.kind!r}"
    )

    kind = actual.kind

    if kind == "set_status":
        assert actual.status == expected["status"], (
            f"set_status: expected={expected['status']!r} actual={actual.status!r}"
        )

    elif kind == "post_comment":
        contains = expected.get("contains", [])
        if contains:
            for substring in contains:
                assert substring in (actual.body or ""), (
                    f"post_comment body missing {substring!r} in:\n{actual.body}"
                )

    elif kind == "patch_queue":
        patch_contains = expected.get("patch_contains", {})
        actual_patch = actual.queue_patch or {}
        for key, expected_val in patch_contains.items():
            actual_val = actual_patch.get(key)
            assert actual_val == expected_val, (
                f"patch_queue[{key!r}]: expected={expected_val!r} actual={actual_val!r}"
            )

    elif kind == "create_pr":
        if "pr_title" in expected:
            assert actual.pr_title == expected["pr_title"]
        if "pr_head" in expected:
            assert actual.pr_head == expected["pr_head"]
        if "pr_base" in expected:
            assert actual.pr_base == expected["pr_base"]

    elif kind == "assign" and "body" in expected:
        assert actual.body == expected["body"]


# ---------------------------------------------------------------------------
# Fixture discovery + test
# ---------------------------------------------------------------------------


def _discover_fixtures() -> list[Path]:
    if not FIXTURE_DIR.exists():
        return []
    return sorted(d for d in FIXTURE_DIR.iterdir() if d.is_dir())


@pytest.mark.parametrize("scenario", _discover_fixtures(), ids=lambda p: p.name)
def test_emit(scenario: Path):
    """Parametrized emit test: world + action + result -> expected effects."""
    world = _load_world(json.loads((scenario / "world.json").read_text()))
    action = _load_action(json.loads((scenario / "action.json").read_text()))
    result = _load_result(scenario / "result.json")
    expected_list = json.loads((scenario / "expected_effects.json").read_text())

    effects = emit(action, result, world)
    expected = [dict(e) for e in expected_list]

    _actual_desc = [f"{e.kind}({e.status or e.body or e.queue_patch or ''})" for e in effects]
    assert len(effects) == len(expected), (
        f"effect count: expected={len(expected)} actual={len(effects)}\n"
        f"actual effects: {_actual_desc}"
    )

    for _i, (actual, exp) in enumerate(zip(effects, expected, strict=True)):
        assert_effect_matches(actual, exp)


# ---------------------------------------------------------------------------
# Regression: Bug 3 — last_consumed_reply_ts must advance for every plan action
# ---------------------------------------------------------------------------


def test_plan_ready_persists_plan_file_path():
    """plan + PLAN_READY with a plan_file_path on DispatchResult must put it
    into the queue_patch so the next /fix can find it in TaskState and
    start a fresh session seeded with the plan file.

    Without this persistence, the planner sets ``task['plan_file_path']``
    on its local dict, that dict is thrown away after the dispatch, and
    ``coder.run_fix`` never sees it — so fix always resumes the plan
    session instead of starting fresh. This was the ADO-side regression
    that left /fix running with the wrong context after a steering /plan.
    """
    world = _load_world(json.loads(
        (FIXTURE_DIR / "plan_action_success" / "world.json").read_text()
    ))
    action = _load_action(json.loads(
        (FIXTURE_DIR / "plan_action_success" / "action.json").read_text()
    ))
    base_result = _load_result(FIXTURE_DIR / "plan_action_success" / "result.json")
    assert base_result is not None
    plan_path = "/home/me/.claude/plans/abc.md"
    result = DispatchResult(
        done_content=base_result.done_content,
        cost_usd=base_result.cost_usd,
        duration_seconds=base_result.duration_seconds,
        session_id=base_result.session_id,
        plan_file_path=plan_path,
    )

    effects = emit(action, result, world)
    patches = [e for e in effects if e.kind == "patch_queue"]
    assert patches, "plan_ready must emit a patch_queue effect"
    assert patches[0].queue_patch.get("plan_file_path") == plan_path


def test_fix_completion_clears_plan_file_path():
    """fix consumes the plan file, so its emit must clear plan_file_path."""
    world = _load_world(json.loads(
        (FIXTURE_DIR / "fix_action_done_summary" / "world.json").read_text()
    ))
    action = _load_action(json.loads(
        (FIXTURE_DIR / "fix_action_done_summary" / "action.json").read_text()
    ))
    result = _load_result(FIXTURE_DIR / "fix_action_done_summary" / "result.json")

    effects = emit(action, result, world)
    patches = [e for e in effects if e.kind == "patch_queue"]
    assert patches, "fix must emit a patch_queue effect"
    patch = patches[0].queue_patch or {}
    assert "plan_file_path" in patch, (
        "fix emit must explicitly clear plan_file_path (set to None)"
    )
    assert patch["plan_file_path"] is None


def test_bug3_watermark_advance_on_plan():
    """Structural regression: emit for plan success MUST advance watermark.

    Bug 3: dispatch.py only advanced last_consumed_reply_ts when
    pending_user_reply_ts was set. For plan actions, it wasn't, so the
    same /plan comment re-triggered on every poll cycle.
    """
    world = _load_world(json.loads(
        (FIXTURE_DIR / "plan_action_success" / "world.json").read_text()
    ))
    action = _load_action(json.loads(
        (FIXTURE_DIR / "plan_action_success" / "action.json").read_text()
    ))
    result = _load_result(FIXTURE_DIR / "plan_action_success" / "result.json")

    effects = emit(action, result, world)

    # Find the patch_queue effect
    patch_effects = [e for e in effects if e.kind == "patch_queue"]
    assert len(patch_effects) >= 1, "plan success must emit a patch_queue effect"

    # The watermark MUST advance — this is the structural fix for Bug 3
    patch = patch_effects[0].queue_patch or {}
    assert "last_consumed_reply_id" in patch, (
        "BUG 3 REGRESSION: plan emit must advance last_consumed_reply_id"
    )
    assert patch["last_consumed_reply_id"] == 1, (
        "watermark should advance to triggering_comment_id"
    )


# ---------------------------------------------------------------------------
# Regression: review_file_path must be cleared from queue after consumption
# ---------------------------------------------------------------------------


def test_fix_completion_clears_review_file_path():
    """fix consumes the review file via _pop_review_file, so its emit must
    clear review_file_path from the queue. Without this, a failed /fix
    followed by /retry would re-inject stale review findings."""
    world = _load_world(json.loads(
        (FIXTURE_DIR / "fix_action_done_summary" / "world.json").read_text()
    ))
    action = _load_action(json.loads(
        (FIXTURE_DIR / "fix_action_done_summary" / "action.json").read_text()
    ))
    result = _load_result(FIXTURE_DIR / "fix_action_done_summary" / "result.json")

    effects = emit(action, result, world)
    patches = [e for e in effects if e.kind == "patch_queue"]
    assert patches, "fix must emit a patch_queue effect"
    patch = patches[0].queue_patch or {}
    assert "review_file_path" in patch, (
        "fix emit must explicitly clear review_file_path (set to None)"
    )
    assert patch["review_file_path"] is None


def test_plan_completion_clears_review_file_path():
    """plan also consumes review_file_path via _pop_review_file, so its emit
    must clear review_file_path from the queue."""
    world = _load_world(json.loads(
        (FIXTURE_DIR / "plan_action_success" / "world.json").read_text()
    ))
    action = _load_action(json.loads(
        (FIXTURE_DIR / "plan_action_success" / "action.json").read_text()
    ))
    result = _load_result(FIXTURE_DIR / "plan_action_success" / "result.json")

    effects = emit(action, result, world)
    patches = [e for e in effects if e.kind == "patch_queue"]
    assert patches, "plan must emit a patch_queue effect"
    patch = patches[0].queue_patch or {}
    assert "review_file_path" in patch, (
        "plan emit must explicitly clear review_file_path (set to None)"
    )
    assert patch["review_file_path"] is None


def test_retry_clears_review_file_path():
    """retry also consumes review_file_path via _pop_review_file (replays
    fix/plan), so its emit must clear review_file_path from the queue."""
    world = _load_world(json.loads(
        (FIXTURE_DIR / "retry_clears_guard" / "world.json").read_text()
    ))
    action = _load_action(json.loads(
        (FIXTURE_DIR / "retry_clears_guard" / "action.json").read_text()
    ))
    result = _load_result(FIXTURE_DIR / "retry_clears_guard" / "result.json")

    effects = emit(action, result, world)
    patches = [e for e in effects if e.kind == "patch_queue"]
    assert patches, "retry must emit a patch_queue effect"
    patch = patches[0].queue_patch or {}
    assert "review_file_path" in patch, (
        "retry emit must explicitly clear review_file_path (set to None)"
    )
    assert patch["review_file_path"] is None


def test_review_preserves_status_only_emits_queue_patch():
    """A review action transitions to 'reviewed' status and emits
    post_comment + set_status + patch_queue."""
    # Build a world where task is already planned
    from autoswe.orch.types import ApiState, TaskState, World
    from autoswe.providers.base import NormalizedIssue

    review_path = "/tmp/review.md"
    issue = NormalizedIssue(
        number=42,
        title="Test",
        body="Test body",
        owner="owner",
        repo="repo",
        state="open",
    )
    api = ApiState(issue=issue, comments=(), open_pr_numbers=())
    task = TaskState(
        slug="gh:owner_repo_42",
        owner="owner",
        repo="repo",
        issue_number=42,
        title="Test",
        body="Test body",
        status="planned",
        plan_branch=None,
        base_branch="main",
        attempt_count=1,
        first_dispatched_at="2026-01-01T00:00:00Z",
        last_dispatched_command="/fix",
        last_dispatched_command_id=1,
        last_consumed_reply_id=1,
        session_id="fix-session",
        pr_number=None,
        guard_blocked=False,
        gh_closed=False,
        pending_command=None,
        pending_guidance=None,
        pending_user_reply=None,
    )
    world = World(api=api, task=task, cfg=_default_cfg(), repo_cfg={"pat": "tok"})

    action = Action(
        kind="review",
        slug="gh:owner_repo_42",
        triggering_comment_id=5,
    )
    result = DispatchResult(
        done_content="REVIEW_READY\tAll good, no issues found.",
        cost_usd=0.01,
        duration_seconds=10,
        session_id="review-session",
        review_file_path=review_path,
    )

    effects = emit(action, result, world)
    effect_kinds = [e.kind for e in effects]

    # Should have post_comment + set_status + patch_queue
    assert "post_comment" in effect_kinds, "Review must emit post_comment"
    assert "set_status" in effect_kinds, "Review must emit set_status"
    assert "patch_queue" in effect_kinds, "Review must emit patch_queue"

    set_status_effect = next(e for e in effects if e.kind == "set_status")
    assert set_status_effect.status == "reviewed", (
        "set_status should transition to 'reviewed'"
    )

    patch = next(e.queue_patch for e in effects if e.kind == "patch_queue")
    assert patch["autoswe_status"] == "reviewed", "Status should be 'reviewed'"
    assert patch["review_file_path"] == review_path
    assert patch["last_dispatched_command"] == "/review"


def test_review_preserves_status_includes_review_comment():
    """The review post_comment effect body must contain the ## Review header
    and the review text from done_content, so progress.finalize() patches
    the sticky comment with the formatted review report."""
    from autoswe.orch.types import ApiState, TaskState, World
    from autoswe.providers.base import NormalizedIssue

    review_text = "## Summary\n\nThe code looks clean. Minor style nit on line 42.\n\n## Verdict\n\nLGTM with minor notes."
    issue = NormalizedIssue(
        number=42,
        title="Test",
        body="Test body",
        owner="owner",
        repo="repo",
        state="open",
    )
    api = ApiState(issue=issue, comments=(), open_pr_numbers=())
    task = TaskState(
        slug="gh:owner_repo_42",
        owner="owner",
        repo="repo",
        issue_number=42,
        title="Test",
        body="Test body",
        status="planned",
        plan_branch=None,
        base_branch="main",
        attempt_count=1,
        first_dispatched_at="2026-01-01T00:00:00Z",
        last_dispatched_command="/fix",
        last_dispatched_command_id=1,
        last_consumed_reply_id=1,
        session_id="fix-session",
        pr_number=None,
        guard_blocked=False,
        gh_closed=False,
        pending_command=None,
        pending_guidance=None,
        pending_user_reply=None,
    )
    world = World(api=api, task=task, cfg=_default_cfg(), repo_cfg={"pat": "tok"})

    action = Action(
        kind="review",
        slug="gh:owner_repo_42",
        triggering_comment_id=5,
    )
    result = DispatchResult(
        done_content="REVIEW_READY\t" + review_text,
        cost_usd=0.02,
        duration_seconds=30,
        session_id="review-session",
        review_file_path="/tmp/review.md",
    )

    effects = emit(action, result, world)

    post_comment_effect = next(e for e in effects if e.kind == "post_comment")
    assert "## Review" in post_comment_effect.body, (
        "Review post_comment body must start with ## Review header"
    )
    assert review_text in post_comment_effect.body, (
        "Review post_comment body must contain the review text"
    )
    # Should also include metrics
    assert "Cost:" in post_comment_effect.body
    assert "Duration:" in post_comment_effect.body
    assert "Session:" in post_comment_effect.body


def test_review_on_done_includes_findings():
    """Regression: review on a done issue must include review findings in the
    comment, not just 'done.' text. Previously the advisory-only path only
    fired for plan_ready/waiting status, so reviews on done issues fell
    through to the completion-comment path which silently discarded findings.

    See: natedorr/autoswe#246
    """
    from autoswe.orch.types import ApiState, TaskState, World
    from autoswe.providers.base import NormalizedIssue

    review_text = "## Summary\n\nThe implementation looks good. Found 2 minor issues.\n\n1. Line 42: unused import\n2. Line 87: potential null dereference"
    issue = NormalizedIssue(
        number=245,
        title="Some issue",
        body="Test body",
        owner="natedorr",
        repo="autoswe",
        state="open",
    )
    api = ApiState(issue=issue, comments=(), open_pr_numbers=())
    task = TaskState(
        slug="gh:natedorr_autoswe_245",
        owner="natedorr",
        repo="autoswe",
        issue_number=245,
        title="Some issue",
        body="Test body",
        status="fixed",
        plan_branch="autoswe/issue-245",
        base_branch="main",
        attempt_count=1,
        first_dispatched_at="2026-01-01T00:00:00Z",
        last_dispatched_command="/fix",
        last_dispatched_command_id=1,
        last_consumed_reply_id=1,
        session_id="fix-session",
        pr_number=None,
        guard_blocked=False,
        gh_closed=False,
        pending_command=None,
        pending_guidance=None,
        pending_user_reply=None,
    )
    world = World(api=api, task=task, cfg=_default_cfg(), repo_cfg={"pat": "tok"})

    action = Action(
        kind="review",
        slug="gh:natedorr_autoswe_245",
        triggering_comment_id=10,
    )
    result = DispatchResult(
        done_content="REVIEW_READY\t" + review_text,
        cost_usd=1.86,
        duration_seconds=177,
        session_id="review-session",
        review_file_path="/tmp/review-245.md",
    )

    effects = emit(action, result, world)
    effect_kinds = [e.kind for e in effects]

    # Must have post_comment + set_status + patch_queue
    assert "post_comment" in effect_kinds
    assert "set_status" in effect_kinds
    assert "patch_queue" in effect_kinds

    # The review comment must include the findings, not just "done."
    post_comment_effect = next(e for e in effects if e.kind == "post_comment")
    assert "## Review" in post_comment_effect.body, (
        "Review on done issue must include ## Review header"
    )
    assert review_text in post_comment_effect.body, (
        "Review on done issue must include review findings text"
    )
    assert "done." not in post_comment_effect.body, (
        "Review on done issue must NOT fall through to bare 'done.' completion comment"
    )
    assert "Completed with command" not in post_comment_effect.body, (
        "Review on done issue should NOT use the completion comment template"
    )
    # Metrics should be present
    assert "Cost:" in post_comment_effect.body
    assert "Duration:" in post_comment_effect.body

    # Status transitions to 'reviewed'
    set_status_effect = next(e for e in effects if e.kind == "set_status")
    assert set_status_effect.status == "reviewed"

    # Queue patch sets 'reviewed' status
    patch = next(e.queue_patch for e in effects if e.kind == "patch_queue")
    assert patch["autoswe_status"] == "reviewed"
    assert patch["review_file_path"] == "/tmp/review-245.md"


def test_review_on_failed_transitions_to_reviewed_and_shows_findings():
    """Review on a failed issue transitions to 'reviewed' status and shows
    review findings."""
    from autoswe.orch.types import ApiState, TaskState, World
    from autoswe.providers.base import NormalizedIssue

    review_text = "## Findings\n\nThe code has critical issues."
    issue = NormalizedIssue(
        number=99,
        title="Bug",
        body="Body",
        owner="owner",
        repo="repo",
        state="open",
    )
    api = ApiState(issue=issue, comments=(), open_pr_numbers=())
    task = TaskState(
        slug="gh:owner_repo_99",
        owner="owner",
        repo="repo",
        issue_number=99,
        title="Bug",
        body="Body",
        status="failed",
        plan_branch=None,
        base_branch="main",
        attempt_count=2,
        first_dispatched_at="2026-01-01T00:00:00Z",
        last_dispatched_command="/fix",
        last_dispatched_command_id=1,
        last_consumed_reply_id=1,
        session_id=None,
        pr_number=None,
        guard_blocked=False,
        gh_closed=False,
        pending_command=None,
        pending_guidance=None,
        pending_user_reply=None,
    )
    world = World(api=api, task=task, cfg=_default_cfg(), repo_cfg={"pat": "tok"})

    action = Action(
        kind="review",
        slug="gh:owner_repo_99",
        triggering_comment_id=20,
    )
    result = DispatchResult(
        done_content="REVIEW_READY\t" + review_text,
        cost_usd=0.50,
        duration_seconds=60,
        session_id="review-session",
        review_file_path="/tmp/review-99.md",
    )

    effects = emit(action, result, world)

    # Review comment must include findings
    post_comment_effect = next(e for e in effects if e.kind == "post_comment")
    assert "## Review" in post_comment_effect.body
    assert review_text in post_comment_effect.body

    # Review always transitions to reviewed (terminal)
    set_status_effect = next(e for e in effects if e.kind == "set_status")
    assert set_status_effect.status == "reviewed"


def test_review_does_not_overwrite_queue_session_id():
    """Review must NOT overwrite the queue's session_id with its throwaway
    review session. The queue should keep the persistent fix session_id so
    subsequent /fix dispatches can resume the correct session."""
    from autoswe.orch.types import ApiState, TaskState, World
    from autoswe.providers.base import NormalizedIssue

    issue = NormalizedIssue(
        number=42,
        title="Test",
        body="Test body",
        owner="owner",
        repo="repo",
        state="open",
    )
    api = ApiState(issue=issue, comments=(), open_pr_numbers=())
    task = TaskState(
        slug="gh:owner_repo_42",
        owner="owner",
        repo="repo",
        issue_number=42,
        title="Test",
        body="Test body",
        status="planned",
        plan_branch=None,
        base_branch="main",
        attempt_count=1,
        first_dispatched_at="2026-01-01T00:00:00Z",
        last_dispatched_command="/fix",
        last_dispatched_command_id=1,
        last_consumed_reply_id=1,
        session_id="fix-session-34ac5c01",
        pr_number=None,
        guard_blocked=False,
        gh_closed=False,
        pending_command=None,
        pending_guidance=None,
        pending_user_reply=None,
    )
    world = World(api=api, task=task, cfg=_default_cfg(), repo_cfg={"pat": "tok"})

    action = Action(
        kind="review",
        slug="gh:owner_repo_42",
        triggering_comment_id=5,
    )
    result = DispatchResult(
        done_content="REVIEW_READY\tLGTM",
        cost_usd=0.01,
        duration_seconds=10,
        session_id="review-session-44315ceb",
        review_file_path="/tmp/review.md",
    )

    effects = emit(action, result, world)
    patch_effects = [e for e in effects if e.kind == "patch_queue"]
    assert len(patch_effects) >= 1, "Review must emit a patch_queue effect"
    patch = patch_effects[0].queue_patch

    assert "session_id" not in patch, (
        "Review must NOT include session_id in queue_patch — "
        "it should not overwrite the persistent fix session with a throwaway review session"
    )

    # The review comment should still show the review session ID (not fix session)
    post_comment_effect = next(e for e in effects if e.kind == "post_comment")
    assert "Session: review-session-44315ceb" in post_comment_effect.body, (
        "Review completion comment must show the review session ID"
    )
    assert "fix-session-34ac5c01" not in post_comment_effect.body, (
        "Review completion comment must NOT show the fix session ID"
    )


# ---------------------------------------------------------------------------
# Review verdict gating — emit() (issue: review verdict ignored)
# ---------------------------------------------------------------------------


def _review_emit_world(status: str = "planned", *, pr_number=None):
    from autoswe.orch.types import ApiState, TaskState, World
    from autoswe.providers.base import NormalizedIssue

    issue = NormalizedIssue(
        number=42, title="Test", body="Body", owner="owner", repo="repo", state="open",
    )
    api = ApiState(issue=issue, comments=(), open_pr_numbers=())
    task = TaskState(
        slug="gh:owner_repo_42", owner="owner", repo="repo", issue_number=42,
        title="Test", body="Body", status=status, plan_branch="autoswe/issue-42",
        base_branch="main", attempt_count=1, first_dispatched_at="2026-01-01T00:00:00Z",
        last_dispatched_command="/review", last_dispatched_command_id=1,
        last_consumed_reply_id=1, session_id="fix-session", pr_number=pr_number,
        guard_blocked=False, gh_closed=False, pending_command=None,
        pending_guidance=None, pending_user_reply=None,
    )
    return World(api=api, task=task, cfg=_default_cfg(), repo_cfg={"pat": "tok"})


def test_review_blocked_verdict_transitions_to_review_blocked():
    """A 'Blocked' verdict gates: status review_blocked, /pr gate note, no rereview flag set yet."""
    world = _review_emit_world()
    action = Action(kind="review", slug="gh:owner_repo_42", triggering_comment_id=5)
    review_text = "## Findings\n\n[CRITICAL] count_vowels misses uppercase.\n\n## Verdict\n\n**Blocked**"
    result = DispatchResult(
        done_content="REVIEW_READY\t" + review_text,
        cost_usd=0.5, duration_seconds=60, session_id="review-session",
        review_file_path="/tmp/review.md",
    )

    effects = emit(action, result, world)
    set_status = next(e for e in effects if e.kind == "set_status")
    assert set_status.status == "review_blocked"
    patch = next(e.queue_patch for e in effects if e.kind == "patch_queue")
    assert patch["autoswe_status"] == "review_blocked"
    assert patch["rereview_after_fix"] is False
    post = next(e for e in effects if e.kind == "post_comment")
    assert review_text in post.body
    assert "/pr` is disabled" in post.body


def test_review_needs_changes_verdict_transitions_to_review_failed():
    world = _review_emit_world()
    action = Action(kind="review", slug="gh:owner_repo_42", triggering_comment_id=5)
    review_text = "## Findings\n\n[MEDIUM] no test for main().\n\n## Verdict\n\n**Needs changes**"
    result = DispatchResult(
        done_content="REVIEW_READY\t" + review_text,
        cost_usd=0.5, duration_seconds=60, session_id="review-session",
        review_file_path="/tmp/review.md",
    )

    effects = emit(action, result, world)
    set_status = next(e for e in effects if e.kind == "set_status")
    assert set_status.status == "review_failed"
    post = next(e for e in effects if e.kind == "post_comment")
    assert "/pr` is disabled" in post.body


def test_fix_from_review_blocked_sets_rereview_and_skips_auto_pr():
    """A /fix dispatched from review_blocked flags re-review and must NOT auto-open a PR."""
    world = _review_emit_world(status="review_blocked")
    world.cfg["AUTO_CREATE_PR"] = True
    action = Action(kind="fix", slug="gh:owner_repo_42", triggering_comment_id=7)
    result = DispatchResult(
        done_content="DONE_SUMMARY\tFixed the vowel bug\tabc1234",
        cost_usd=1.0, duration_seconds=60, session_id="fix-session",
    )

    effects = emit(action, result, world)
    patch = next(e.queue_patch for e in effects if e.kind == "patch_queue")
    assert patch["rereview_after_fix"] is True, "fix from review_blocked must flag re-review"
    assert patch["autoswe_status"] == "fixed"
    pr_effects = [e for e in effects if e.kind == "create_pr"]
    assert len(pr_effects) == 0, "must not auto-open PR while a re-review is pending"


def test_fix_from_normal_state_clears_rereview_flag():
    """A /fix from a normal (planned) state does not set the re-review flag."""
    world = _review_emit_world(status="planned")
    action = Action(kind="fix", slug="gh:owner_repo_42", triggering_comment_id=7)
    result = DispatchResult(
        done_content="DONE_SUMMARY\tImplemented feature\tabc1234",
        cost_usd=1.0, duration_seconds=60, session_id="fix-session",
    )

    effects = emit(action, result, world)
    patch = next(e.queue_patch for e in effects if e.kind == "patch_queue")
    assert patch["rereview_after_fix"] is False


def test_fix_still_overwrites_queue_session_id():
    """Non-review actions (fix, plan) should still update session_id in
    the queue_patch when the handler returns one."""
    from autoswe.orch.types import ApiState, TaskState, World
    from autoswe.providers.base import NormalizedIssue

    issue = NormalizedIssue(
        number=42,
        title="Test",
        body="Test body",
        owner="owner",
        repo="repo",
        state="open",
    )
    api = ApiState(issue=issue, comments=(), open_pr_numbers=())
    task = TaskState(
        slug="gh:owner_repo_42",
        owner="owner",
        repo="repo",
        issue_number=42,
        title="Test",
        body="Test body",
        status="waiting",
        plan_branch="autoswe/issue-42",
        base_branch="main",
        attempt_count=1,
        first_dispatched_at="2026-01-01T00:00:00Z",
        last_dispatched_command="/fix",
        last_dispatched_command_id=1,
        last_consumed_reply_id=1,
        session_id="old-session",
        pr_number=None,
        guard_blocked=False,
        gh_closed=False,
        pending_command=None,
        pending_guidance=None,
        pending_user_reply=None,
    )
    world = World(api=api, task=task, cfg=_default_cfg(), repo_cfg={"pat": "tok"})

    action = Action(
        kind="fix",
        slug="gh:owner_repo_42",
        triggering_comment_id=5,
    )
    result = DispatchResult(
        done_content="DONE_SUMMARY\tfixed\tabc123",
        cost_usd=1.50,
        duration_seconds=120,
        session_id="new-fix-session",
    )

    effects = emit(action, result, world)
    patch_effects = [e for e in effects if e.kind == "patch_queue"]
    assert len(patch_effects) >= 1
    patch = patch_effects[0].queue_patch

    assert patch.get("session_id") == "new-fix-session", (
        "Fix must update session_id in queue_patch"
    )


# ---------------------------------------------------------------------------
# Regression #259 — first_dispatched_at not reset after terminal state
# ---------------------------------------------------------------------------


def test_review_on_done_resets_first_dispatched_at():
    """Regression #259: review on a terminal task must reset first_dispatched_at
    in the queue_patch. Without this, the review early return in emit()
    bypasses the terminal-status reset, leaving a stale timestamp that
    causes the time guard in decide.py to fire on follow-up commands
    posted hours after the original task completed.
    """
    from autoswe.orch.types import ApiState, TaskState, World
    from autoswe.providers.base import NormalizedIssue

    issue = NormalizedIssue(
        number=247,
        title="Some issue",
        body="Test body",
        owner="owner",
        repo="repo",
        state="open",
    )
    api = ApiState(issue=issue, comments=(), open_pr_numbers=())
    task = TaskState(
        slug="gh:owner_repo_247",
        owner="owner",
        repo="repo",
        issue_number=247,
        title="Some issue",
        body="Test body",
        status="fixed",
        plan_branch="autoswe/issue-247",
        base_branch="main",
        attempt_count=1,
        first_dispatched_at="2026-01-01T09:40:03Z",
        last_dispatched_command="/review",
        last_dispatched_command_id=1,
        last_consumed_reply_id=1,
        session_id="fix-session",
        pr_number=None,
        guard_blocked=False,
        gh_closed=False,
        pending_command=None,
        pending_guidance=None,
        pending_user_reply=None,
    )
    world = World(api=api, task=task, cfg=_default_cfg(), repo_cfg={"pat": "tok"})

    action = Action(
        kind="review",
        slug="gh:owner_repo_247",
        triggering_comment_id=5,
    )
    result = DispatchResult(
        done_content="REVIEW_READY\tLGTM, no issues found.",
        cost_usd=0.01,
        duration_seconds=10,
        session_id="review-session",
    )

    effects = emit(action, result, world)
    patch_effects = [e for e in effects if e.kind == "patch_queue"]
    assert len(patch_effects) >= 1, "Review must emit a patch_queue effect"
    patch = patch_effects[0].queue_patch

    assert patch.get("first_dispatched_at") is None, (
        "REGRESSION #259: review on done must reset first_dispatched_at to None. "
        "Without this, the time guard blocks follow-up commands posted hours after completion."
    )

    assert patch.get("autoswe_status") == "reviewed", (
        "Review transitions to 'reviewed' status"
    )


def test_mark_failed_limit_resets_first_dispatched_at():
    """Regression #259: mark_failed_limit must reset first_dispatched_at so
    that after /retry clears the guard, the time guard doesn't fire using
    the stale timestamp from the original run.
    """
    from autoswe.orch.types import ApiState, TaskState, World
    from autoswe.providers.base import NormalizedIssue

    issue = NormalizedIssue(
        number=42,
        title="Bug",
        body="Test body",
        owner="owner",
        repo="repo",
        state="open",
    )
    api = ApiState(issue=issue, comments=(), open_pr_numbers=())
    task = TaskState(
        slug="gh:owner_repo_42",
        owner="owner",
        repo="repo",
        issue_number=42,
        title="Bug",
        body="Test body",
        status="failed",
        plan_branch=None,
        base_branch="main",
        attempt_count=3,
        first_dispatched_at="2026-01-01T00:00:00Z",
        last_dispatched_command="/fix",
        last_dispatched_command_id=1,
        last_consumed_reply_id=1,
        session_id=None,
        pr_number=None,
        guard_blocked=False,
        gh_closed=False,
        pending_command=None,
        pending_guidance=None,
        pending_user_reply=None,
    )
    world = World(
        api=api,
        task=task,
        cfg={"MAX_ATTEMPTS": 3, "MAX_TOTAL_HOURS": 2},
        repo_cfg={"pat": "tok"},
    )

    action = Action(
        kind="mark_failed_limit",
        slug="gh:owner_repo_42",
        attempt_count=4,
        triggering_comment_id=2,
    )

    effects = emit(action, result=None, world=world)
    patch_effects = [e for e in effects if e.kind == "patch_queue"]
    assert len(patch_effects) >= 1, "mark_failed_limit must emit a patch_queue effect"
    patch = patch_effects[0].queue_patch

    assert patch.get("first_dispatched_at") is None, (
        "REGRESSION #259: mark_failed_limit must reset first_dispatched_at to None. "
        "Without this, /retry + subsequent command inherits a stale timestamp."
    )
    assert patch.get("_guard_blocked") is True
    assert patch.get("autoswe_status") == "failed"


# ---------------------------------------------------------------------------
# Issue #27 — resume_phase set by emit()
# ---------------------------------------------------------------------------


def test_plan_emit_sets_resume_phase():
    """Plan actions must set resume_phase='plan' in the queue patch so that
    _resume_kind uses the authoritative value, not a stale last_phase."""
    from autoswe.orch.types import ApiState, TaskState, World
    from autoswe.providers.base import NormalizedIssue

    issue = NormalizedIssue(number=42, title="T", body="B", owner="o", repo="r", state="open")
    api = ApiState(issue=issue, comments=(), open_pr_numbers=())
    task = TaskState(
        slug="gh:o_r_42", owner="o", repo="r", issue_number=42, title="T", body="B",
        status="waiting", plan_branch=None, base_branch="main", attempt_count=1,
        first_dispatched_at=None, last_dispatched_command="/plan",
        last_dispatched_command_id=1, last_consumed_reply_id=1, session_id="s1",
        pr_number=None, guard_blocked=False, gh_closed=False,
        pending_command=None, pending_guidance=None, pending_user_reply=None,
    )
    world = World(api=api, task=task, cfg=_default_cfg(), repo_cfg={"pat": "tok"})

    action = Action(kind="plan", slug="gh:o_r_42", triggering_comment_id=1)
    result = DispatchResult(
        done_content="PLAN_READY", cost_usd=0.1, duration_seconds=10, session_id="s1",
    )

    effects = emit(action, result, world)
    patches = [e for e in effects if e.kind == "patch_queue"]
    assert len(patches) >= 1
    patch = patches[0].queue_patch
    assert patch.get("resume_phase") == "plan", "plan emit must set resume_phase='plan'"
    assert patch.get("last_phase") == "plan", "plan emit must set last_phase='plan'"


def test_fix_emit_sets_resume_phase():
    """Fix actions must set resume_phase='fix' in the queue patch."""
    from autoswe.orch.types import ApiState, TaskState, World
    from autoswe.providers.base import NormalizedIssue

    issue = NormalizedIssue(number=42, title="T", body="B", owner="o", repo="r", state="open")
    api = ApiState(issue=issue, comments=(), open_pr_numbers=())
    task = TaskState(
        slug="gh:o_r_42", owner="o", repo="r", issue_number=42, title="T", body="B",
        status="planned", plan_branch="autoswe/issue-42", base_branch="main",
        attempt_count=1, first_dispatched_at=None, last_dispatched_command="/fix",
        last_dispatched_command_id=1, last_consumed_reply_id=1, session_id="s1",
        pr_number=None, guard_blocked=False, gh_closed=False,
        pending_command=None, pending_guidance=None, pending_user_reply=None,
    )
    world = World(api=api, task=task, cfg=_default_cfg(), repo_cfg={"pat": "tok"})

    action = Action(kind="fix", slug="gh:o_r_42", triggering_comment_id=2)
    result = DispatchResult(
        done_content="DONE_SUMMARY\tfixed\tabc123", cost_usd=1.0,
        duration_seconds=60, session_id="s-fix",
    )

    effects = emit(action, result, world)
    patches = [e for e in effects if e.kind == "patch_queue"]
    assert len(patches) >= 1
    patch = patches[0].queue_patch
    assert patch.get("resume_phase") == "fix", "fix emit must set resume_phase='fix'"
    assert patch.get("last_phase") == "fix", "fix emit must set last_phase='fix'"


def test_plan_waiting_emit_sets_resume_phase():
    """Plan returning WAITING must still set resume_phase='plan' so a
    subsequent user reply resumes planning, not fixing."""
    from autoswe.orch.types import ApiState, TaskState, World
    from autoswe.providers.base import NormalizedIssue

    issue = NormalizedIssue(number=42, title="T", body="B", owner="o", repo="r", state="open")
    api = ApiState(issue=issue, comments=(), open_pr_numbers=())
    task = TaskState(
        slug="gh:o_r_42", owner="o", repo="r", issue_number=42, title="T", body="B",
        status="waiting", plan_branch=None, base_branch="main", attempt_count=1,
        first_dispatched_at=None, last_dispatched_command="/plan",
        last_dispatched_command_id=1, last_consumed_reply_id=1, session_id="s1",
        pr_number=None, guard_blocked=False, gh_closed=False,
        pending_command=None, pending_guidance=None, pending_user_reply=None,
        last_phase="fix",       # stale — from a previous /fix
        resume_phase="fix",     # stale — from a previous /fix
    )
    world = World(api=api, task=task, cfg=_default_cfg(), repo_cfg={"pat": "tok"})

    action = Action(kind="plan", slug="gh:o_r_42", triggering_comment_id=3)
    result = DispatchResult(
        done_content="WAITING:What framework?", cost_usd=0.05,
        duration_seconds=5, session_id="s1",
    )

    effects = emit(action, result, world)
    patches = [e for e in effects if e.kind == "patch_queue"]
    assert len(patches) >= 1
    patch = patches[0].queue_patch
    assert patch.get("resume_phase") == "plan", (
        "plan WAITING must overwrite resume_phase to 'plan' — "
        "this is the regression fix for issue #27"
    )
    assert patch.get("autoswe_status") == "waiting"


def test_fix_waiting_emit_preserves_resume_phase_fix():
    """Fix returning WAITING (coder asked a question during fix) must keep
    resume_phase='fix' so a subsequent user reply resumes fixing, not planning."""
    from autoswe.orch.types import ApiState, TaskState, World
    from autoswe.providers.base import NormalizedIssue

    issue = NormalizedIssue(number=42, title="T", body="B", owner="o", repo="r", state="open")
    api = ApiState(issue=issue, comments=(), open_pr_numbers=())
    task = TaskState(
        slug="gh:o_r_42", owner="o", repo="r", issue_number=42, title="T", body="B",
        status="fixing", plan_branch="autoswe/issue-42", base_branch="main",
        attempt_count=1, first_dispatched_at=None, last_dispatched_command="/fix",
        last_dispatched_command_id=1, last_consumed_reply_id=1, session_id="s1",
        pr_number=None, guard_blocked=False, gh_closed=False,
        pending_command=None, pending_guidance=None, pending_user_reply=None,
    )
    world = World(api=api, task=task, cfg=_default_cfg(), repo_cfg={"pat": "tok"})

    action = Action(kind="fix", slug="gh:o_r_42", triggering_comment_id=2)
    result = DispatchResult(
        done_content="WAITING:Should I approach A or B?", cost_usd=0.50,
        duration_seconds=30, session_id="s1",
    )

    effects = emit(action, result, world)
    patches = [e for e in effects if e.kind == "patch_queue"]
    assert len(patches) >= 1
    patch = patches[0].queue_patch
    assert patch.get("resume_phase") == "fix", (
        "fix WAITING must preserve resume_phase='fix' — "
        "a user reply should resume fixing, not switch to planning"
    )
    assert patch.get("last_phase") == "fix"
    assert patch.get("autoswe_status") == "waiting"


# ---------------------------------------------------------------------------
# Issue #43 — fix_summary persistence + auto-create PR body/branch
# ---------------------------------------------------------------------------


def test_fix_completed_persists_fix_summary():
    """When fix completes with DONE_SUMMARY, fix_summary must be persisted
    in the queue_patch so PR creation can include it in the body."""
    from autoswe.orch.types import ApiState, TaskState, World
    from autoswe.providers.base import NormalizedIssue

    issue = NormalizedIssue(
        number=43, title="PR merge issue", body="The PR body is uninformative",
        owner="o", repo="r", state="open",
    )
    api = ApiState(issue=issue, comments=(), open_pr_numbers=())
    task = TaskState(
        slug="gh:o_r_43", owner="o", repo="r", issue_number=43,
        title="PR merge issue", body="The PR body is uninformative",
        status="fixing", plan_branch="autoswe/issue-43", base_branch="main",
        attempt_count=1, first_dispatched_at=None,
        last_dispatched_command="/fix", last_dispatched_command_id=1,
        last_consumed_reply_id=1, session_id="s-fix",
        pr_number=None, guard_blocked=False, gh_closed=False,
        pending_command=None, pending_guidance=None, pending_user_reply=None,
    )
    world = World(api=api, task=task, cfg=_default_cfg(), repo_cfg={"pat": "tok"})

    action = Action(kind="fix", slug="gh:o_r_43", triggering_comment_id=2)
    result = DispatchResult(
        done_content="DONE_SUMMARY\tRefactored PR body builder\tabc123",
        cost_usd=1.0, duration_seconds=60, session_id="s-fix",
    )

    effects = emit(action, result, world)
    patches = [e for e in effects if e.kind == "patch_queue"]
    assert len(patches) >= 1
    patch = patches[0].queue_patch
    assert patch.get("fix_summary") == "Refactored PR body builder", (
        "fix_summary must be extracted from DONE_SUMMARY and persisted"
    )


def test_fix_summary_not_set_on_failed():
    """fix_summary should NOT be set when the status is failed."""
    from autoswe.orch.types import ApiState, TaskState, World
    from autoswe.providers.base import NormalizedIssue

    issue = NormalizedIssue(
        number=43, title="PR merge issue", body="Body",
        owner="o", repo="r", state="open",
    )
    api = ApiState(issue=issue, comments=(), open_pr_numbers=())
    task = TaskState(
        slug="gh:o_r_43", owner="o", repo="r", issue_number=43,
        title="PR merge issue", body="Body",
        status="fixing", plan_branch="autoswe/issue-43", base_branch="main",
        attempt_count=1, first_dispatched_at=None,
        last_dispatched_command="/fix", last_dispatched_command_id=1,
        last_consumed_reply_id=1, session_id="s-fix",
        pr_number=None, guard_blocked=False, gh_closed=False,
        pending_command=None, pending_guidance=None, pending_user_reply=None,
    )
    world = World(api=api, task=task, cfg=_default_cfg(), repo_cfg={"pat": "tok"})

    action = Action(kind="fix", slug="gh:o_r_43", triggering_comment_id=2)
    result = DispatchResult(
        done_content="FAILED: something went wrong",
        cost_usd=0.5, duration_seconds=30, session_id="s-fix",
    )

    effects = emit(action, result, world)
    patches = [e for e in effects if e.kind == "patch_queue"]
    assert len(patches) >= 1
    patch = patches[0].queue_patch
    assert "fix_summary" not in patch, (
        "fix_summary must NOT be set on FAILED status"
    )


def test_retry_fix_persists_fix_summary():
    """retry->fix path also captures summary from DONE_SUMMARY."""
    from autoswe.orch.types import ApiState, TaskState, World
    from autoswe.providers.base import NormalizedIssue

    issue = NormalizedIssue(
        number=43, title="PR merge issue", body="Body",
        owner="o", repo="r", state="open",
    )
    api = ApiState(issue=issue, comments=(), open_pr_numbers=())
    task = TaskState(
        slug="gh:o_r_43", owner="o", repo="r", issue_number=43,
        title="PR merge issue", body="Body",
        status="failed", plan_branch="autoswe/issue-43", base_branch="main",
        attempt_count=2, first_dispatched_at=None,
        last_dispatched_command="/fix", last_dispatched_command_id=1,
        last_consumed_reply_id=1, session_id="s-fix",
        pr_number=None, guard_blocked=False, gh_closed=False,
        pending_command=None, pending_guidance=None, pending_user_reply=None,
    )
    world = World(api=api, task=task, cfg=_default_cfg(), repo_cfg={"pat": "tok"})

    action = Action(kind="retry", slug="gh:o_r_43", triggering_comment_id=3)
    result = DispatchResult(
        done_content="DONE_SUMMARY\tRetry fix summary\tdef456",
        cost_usd=1.5, duration_seconds=90, session_id="s-fix",
    )

    effects = emit(action, result, world)
    patches = [e for e in effects if e.kind == "patch_queue"]
    assert len(patches) >= 1
    patch = patches[0].queue_patch
    assert patch.get("fix_summary") == "Retry fix summary", (
        "retry emit must also persist fix_summary from DONE_SUMMARY"
    )


def test_auto_create_pr_uses_plan_branch():
    """Auto-created PRs must use plan_branch as pr_base (not base_branch)
    to respect the --branch flag from the original /plan command."""
    from autoswe.orch.types import ApiState, TaskState, World
    from autoswe.providers.base import NormalizedIssue

    issue = NormalizedIssue(
        number=43, title="PR merge issue", body="Body",
        owner="o", repo="r", state="open",
    )
    api = ApiState(issue=issue, comments=(), open_pr_numbers=())
    task = TaskState(
        slug="gh:o_r_43", owner="o", repo="r", issue_number=43,
        title="PR merge issue", body="Body",
        status="fixing", plan_branch="codex", base_branch="main",
        attempt_count=1, first_dispatched_at=None,
        last_dispatched_command="/fix", last_dispatched_command_id=1,
        last_consumed_reply_id=1, session_id="s-fix",
        pr_number=None, guard_blocked=False, gh_closed=False,
        pending_command=None, pending_guidance=None, pending_user_reply=None,
    )
    cfg = _default_cfg()
    cfg["AUTO_CREATE_PR"] = True
    world = World(api=api, task=task, cfg=cfg, repo_cfg={"pat": "tok"})

    action = Action(kind="fix", slug="gh:o_r_43", triggering_comment_id=2)
    result = DispatchResult(
        done_content="DONE_SUMMARY\tFixed it\tabc123",
        cost_usd=1.0, duration_seconds=60, session_id="s-fix",
    )

    effects = emit(action, result, world)
    pr_effects = [e for e in effects if e.kind == "create_pr"]
    assert len(pr_effects) == 1, "AUTO_CREATE_PR must emit create_pr effect"
    pr_effect = pr_effects[0]
    assert pr_effect.pr_base == "codex", (
        "auto-create PR must use plan_branch as pr_base, not base_branch"
    )
    assert pr_effect.pr_head == "autoswe/issue-43", (
        "auto-create PR head should be the autoswe/issue-N branch"
    )
    # PR body should include fix_summary
    assert "Fix Summary:" in (pr_effect.pr_body or ""), (
        "auto-create PR body should include fix_summary"
    )
    assert "Fixed it" in (pr_effect.pr_body or ""), (
        "auto-create PR body should contain the fix summary text"
    )


def test_auto_create_pr_body_includes_issue_body():
    """Auto-created PR body must include the issue body for reviewer context."""
    from autoswe.orch.types import ApiState, TaskState, World
    from autoswe.providers.base import NormalizedIssue

    issue = NormalizedIssue(
        number=43, title="PR merge issue", body="The original issue description here",
        owner="o", repo="r", state="open",
    )
    api = ApiState(issue=issue, comments=(), open_pr_numbers=())
    task = TaskState(
        slug="gh:o_r_43", owner="o", repo="r", issue_number=43,
        title="PR merge issue", body="The original issue description here",
        status="fixing", plan_branch=None, base_branch="main",
        attempt_count=1, first_dispatched_at=None,
        last_dispatched_command="/fix", last_dispatched_command_id=1,
        last_consumed_reply_id=1, session_id="s-fix",
        pr_number=None, guard_blocked=False, gh_closed=False,
        pending_command=None, pending_guidance=None, pending_user_reply=None,
    )
    cfg = _default_cfg()
    cfg["AUTO_CREATE_PR"] = True
    world = World(api=api, task=task, cfg=cfg, repo_cfg={"pat": "tok"})

    action = Action(kind="fix", slug="gh:o_r_43", triggering_comment_id=2)
    result = DispatchResult(
        done_content="DONE_SUMMARY\tApplied fix\tabc123",
        cost_usd=1.0, duration_seconds=60, session_id="s-fix",
    )

    effects = emit(action, result, world)
    pr_effects = [e for e in effects if e.kind == "create_pr"]
    assert len(pr_effects) == 1
    pr_body = pr_effects[0].pr_body or ""
    assert "The original issue description here" in pr_body, (
        "auto-create PR body must include issue body"
    )
    assert "**Issue:**" in pr_body
    assert "Opened by autoSWE." in pr_body


def test_fix_summary_preserves_tabs_in_summary():
    """Regression: fix_summary extraction must use rfind('\t') not split('\t')[0]
    to mirror _build_completion_comment. If the LLM summary contains a tab,
    split('[\t')[0] silently truncates the persisted value while the
    completion comment shows the full text — causing a mismatch."""
    from autoswe.orch.types import ApiState, TaskState, World
    from autoswe.providers.base import NormalizedIssue

    issue = NormalizedIssue(
        number=43, title="Tab issue", body="Body",
        owner="o", repo="r", state="open",
    )
    api = ApiState(issue=issue, comments=(), open_pr_numbers=())
    task = TaskState(
        slug="gh:o_r_43", owner="o", repo="r", issue_number=43,
        title="Tab issue", body="Body",
        status="fixing", plan_branch="autoswe/issue-43", base_branch="main",
        attempt_count=1, first_dispatched_at=None,
        last_dispatched_command="/fix", last_dispatched_command_id=1,
        last_consumed_reply_id=1, session_id="s-fix",
        pr_number=None, guard_blocked=False, gh_closed=False,
        pending_command=None, pending_guidance=None, pending_user_reply=None,
    )
    world = World(api=api, task=task, cfg=_default_cfg(), repo_cfg={"pat": "tok"})

    action = Action(kind="fix", slug="gh:o_r_43", triggering_comment_id=2)
    # DONE_SUMMARY with a tab IN the summary text (LLM output with tables etc.)
    # Format: DONE_SUMMARY\t<summary-with-tab>\t<commit-sha>
    result = DispatchResult(
        done_content="DONE_SUMMARY\tFixed bug in A\tand B\tabc123",
        cost_usd=1.0, duration_seconds=60, session_id="s-fix",
    )

    effects = emit(action, result, world)
    patches = [e for e in effects if e.kind == "patch_queue"]
    assert len(patches) >= 1
    patch = patches[0].queue_patch
    summary = patch.get("fix_summary", "")
    assert summary == "Fixed bug in A\tand B", (
        f"fix_summary must use rfind to preserve tabs in summary text. "
        f"Got: {summary!r}"
    )


def test_plan_branch_persisted_in_queue_patch():
    """When an Action has plan_branch set (e.g. /fix --branch develop),
    the emitted queue_patch must persist it so subsequent commands (/pr,
    /sync) use the correct base branch instead of falling back to 'main'."""
    from autoswe.orch.types import ApiState, TaskState, World
    from autoswe.providers.base import NormalizedIssue

    issue = NormalizedIssue(
        number=42, title="Bug", body="Body",
        owner="o", repo="r", state="open",
    )
    api = ApiState(issue=issue, comments=(), open_pr_numbers=())
    # Task does NOT have plan_branch yet (first dispatch with --branch)
    task = TaskState(
        slug="gh:o_r_42", owner="o", repo="r", issue_number=42,
        title="Bug", body="Body",
        status=None, plan_branch=None, base_branch="main",
        attempt_count=0, first_dispatched_at=None,
        last_dispatched_command=None, last_dispatched_command_id=None,
        last_consumed_reply_id=None, session_id=None,
        pr_number=None, guard_blocked=False, gh_closed=False,
        pending_command=None, pending_guidance=None, pending_user_reply=None,
    )
    world = World(api=api, task=task, cfg=_default_cfg(), repo_cfg={"pat": "tok"})

    # Action carries plan_branch from /fix --branch develop
    action = Action(
        kind="fix", slug="gh:o_r_42",
        plan_branch="develop",  # --branch value
        triggering_comment_id=1,
        attempt_count=1,
    )
    result = DispatchResult(
        done_content="DONE_SUMMARY\tFixed the bug\tabc123",
        cost_usd=1.0, duration_seconds=60, session_id="s-fix",
    )

    effects = emit(action, result, world)
    patches = [e for e in effects if e.kind == "patch_queue"]
    assert len(patches) >= 1
    patch = patches[0].queue_patch
    assert patch.get("plan_branch") == "develop", (
        f"plan_branch must be persisted in queue_patch. Got: {patch!r}"
    )


def test_plan_branch_used_for_auto_create_pr_base():
    """When AUTO_CREATE_PR is enabled and fix completes with plan_branch,
    the create_pr effect must use plan_branch as pr_base (not 'main')."""
    from autoswe.orch.types import ApiState, TaskState, World
    from autoswe.providers.base import NormalizedIssue

    issue = NormalizedIssue(
        number=42, title="Bug", body="Issue body",
        owner="o", repo="r", state="open",
    )
    api = ApiState(issue=issue, comments=(), open_pr_numbers=())
    task = TaskState(
        slug="gh:o_r_42", owner="o", repo="r", issue_number=42,
        title="Bug", body="Issue body",
        status="fixing", plan_branch="develop", base_branch="main",
        attempt_count=1, first_dispatched_at=None,
        last_dispatched_command="/fix", last_dispatched_command_id=1,
        last_consumed_reply_id=1, session_id="s-fix",
        pr_number=None, guard_blocked=False, gh_closed=False,
        pending_command=None, pending_guidance=None, pending_user_reply=None,
    )
    cfg = _default_cfg()
    cfg["AUTO_CREATE_PR"] = True
    world = World(api=api, task=task, cfg=cfg, repo_cfg={"pat": "tok"})

    action = Action(
        kind="fix", slug="gh:o_r_42",
        triggering_comment_id=2,
        attempt_count=1,
    )
    result = DispatchResult(
        done_content="DONE_SUMMARY\tFixed the bug\tabc123",
        cost_usd=1.0, duration_seconds=60, session_id="s-fix",
    )

    effects = emit(action, result, world)
    pr_effects = [e for e in effects if e.kind == "create_pr"]
    assert len(pr_effects) == 1, f"Expected create_pr effect, got: {[e.kind for e in effects]}"
    pr_effect = pr_effects[0]
    assert pr_effect.pr_base == "develop", (
        f"create_pr must use plan_branch as pr_base. Got pr_base={pr_effect.pr_base!r}"
    )
