"""Layer A — decide() state machine tests.

Each test loads a fixture from tests/fixtures/decide/<name>/ :
  world.json          — ApiState + TaskState + cfg + repo_cfg
  expected_action.json — the Action decide() must return

Provider-agnostic: a decide test runs the same regardless of GH vs ADO origin.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from autoswe.orch.decide import decide
from autoswe.orch.types import (
    Action,
    ApiState,
    TaskState,
    World,
)
from autoswe.providers.base import NormalizedComment, NormalizedIssue

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
        created_at=task_data.get("created_at", ""),
        last_synced=task_data.get("last_synced", ""),
        provider=task_data.get("provider", "github"),
    )

    cfg = _default_cfg()
    cfg.update(data.get("cfg", {}))
    # Parse ALLOWED_AUTHORS from string if set
    if isinstance(cfg.get("ALLOWED_AUTHORS"), str):
        cfg["ALLOWED_AUTHORS"] = {a.strip() for a in cfg["ALLOWED_AUTHORS"].split(",") if a.strip()}

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
    world = _load_world(json.loads((scenario / "world.json").read_text()))
    expected = _load_action(json.loads((scenario / "expected_action.json").read_text()))
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
