"""Smoke tests for the full poll cycle across both providers.

Runs 2 scenarios per provider (GitHub + Azure) through the full
sync+dispatch pipeline via patched_world + run_one_turn.

Scenarios:
  - fresh_plan_command  : happy path, new issue -> planned
  - failed_then_retry   : error recovery, failed issue /retry -> done

Marked with @pytest.mark.smoke for selective running via:
  pytest -m smoke -v
"""
from pathlib import Path

import pytest

from tests.scenarios.harness import (
    assert_claude_calls,
    assert_comments_posted,
    assert_git_calls,
    assert_queue_task,
    build_test_cfg,
    load_scenario,
    make_task_id,
    patched_world,
    seed_queue,
    setup_repos,
)

SMOKE_SCENARIOS = [
    ("github", "fresh_plan_command"),
    ("github", "failed_then_retry"),
    ("azure", "fresh_plan_command"),
    ("azure", "failed_then_retry"),
]

_SCENARIOS_DIR = Path(__file__).parent / "fixtures" / "scenarios"


@pytest.mark.smoke
@pytest.mark.parametrize(
    ("provider", "scenario_name"),
    SMOKE_SCENARIOS,
    ids=lambda x: x if isinstance(x, str) else f"{x[0]}/{x[1]}",
)
def test_poll_smoke(
    provider: str,
    scenario_name: str,
    isolated_autoswe_dir: Path,
):
    """Run one full poll turn against stateful fakes for a smoke scenario."""
    scenario_dir = _SCENARIOS_DIR / provider / scenario_name
    state, expected = load_scenario(scenario_dir)

    task_id = make_task_id(provider, state)
    git_calls = expected.get("git_calls", [])
    claude_calls = expected.get("claude_calls", [])

    # Seed queue
    seed_queue(isolated_autoswe_dir, state.get("queue_task"))

    # Set up repos.json
    setup_repos(isolated_autoswe_dir, provider, state)

    cfg = build_test_cfg(isolated_autoswe_dir, provider)

    with patched_world(
        provider,
        state=state,
        claude_responses=state.get("claude_responses", []),
        scripted_git=git_calls,
        isolated_dir=isolated_autoswe_dir,
    ) as hw:
        if provider == "github":
            owner, repo = state["owner"], state["repo"]
        else:
            owner, repo = state["org"], state["project"]

        from tests.scenarios.runner import run_one_turn
        run_one_turn(owner, repo, cfg, isolated_autoswe_dir)

    # ---- Assert expected outcomes ----
    # Label/tag assertion
    if "label_after" in expected:
        if provider == "github":
            from tests.scenarios.runner import assert_label_is
            issue_number = state["issue"]["number"]
            assert_label_is(hw.fake, issue_number, expected["label_after"])
        else:
            _assert_azure_tag(hw.fake, state["work_item"]["id"], expected["label_after"])

    # Comment assertions
    assert_comments_posted(hw.fake, expected.get("comments_posted", []))

    # Claude call assertions
    assert_claude_calls(hw.claude, claude_calls)

    # Queue task assertions
    assert_queue_task(isolated_autoswe_dir, task_id, expected.get("queue_task_after", {}))

    # Git call assertions
    if git_calls:
        assert_git_calls(hw.git, git_calls)


def _assert_azure_tag(fake, wi_number: int, expected_label: str) -> None:
    """Assert autoswe tag on Azure work item."""
    tags_raw = fake.work_items.get(wi_number, {}).get("fields", {}).get("System.Tags", "")
    tags = [t.strip() for t in tags_raw.split(";") if t.strip()] if tags_raw else []
    autoswe_tags = [t for t in tags if t.startswith("autoswe:")]
    assert expected_label in autoswe_tags, (
        f"Expected tag {expected_label!r} not found. "
        f"Actual autoswe tags: {autoswe_tags}"
    )


def test_welcome_posted_before_handler_output(
    isolated_autoswe_dir: Path,
    monkeypatch,
):
    """Welcome comment is posted before the handler's output comment.

    Drives one poll with a fresh GitHub issue carrying /plan in the body
    via the fake provider. Asserts:
      (a) two bot comments exist
      (b) the welcome comment ID is the smaller of the two (= posted first)
      (c) suppress_welcome=True and autoswe_status="planned"
    """
    from tests.scenarios.harness import (
        build_test_cfg,
        patched_world,
        seed_queue,
        setup_repos,
    )

    state = {
        "owner": "owner",
        "repo": "repo",
        "issue": {
            "id": 1,
            "number": 42,
            "title": "Login is broken",
            "body": "Login is broken.\n\n/plan",
            "state": "open",
            "labels": [],
            "assignees": [],
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
            "closed_at": None,
            "author_association": "OWNER",
            "comments": 0,
            "user": {"login": "owner", "id": 1, "type": "User"},
            "pull_request": None,
        },
        "labels": [],
        "comments": [],
        "repo_labels": [],
        "authenticated_user": {"login": "owner", "id": 1, "type": "User"},
    }

    cfg = build_test_cfg(isolated_autoswe_dir, "github")
    # Override SILENT_REPORTING so welcome IS posted
    cfg["SILENT_REPORTING"] = False

    # No existing queue task — this is a fresh discovery
    seed_queue(isolated_autoswe_dir, None)

    # Set up repos.json
    setup_repos(isolated_autoswe_dir, "github", state)

    # Mock time.sleep to avoid the 10s throttle in _post_pending_welcomes
    import time as _time_mod
    monkeypatch.setattr(_time_mod, "sleep", lambda _s: None)

    with patched_world(
        "github",
        state=state,
        claude_responses=[
            {"text": "<AUTOSWE_PLAN>1. Fix login</AUTOSWE_PLAN>", "session_id": "s-plan-42", "subtype": "success"},
        ],
        scripted_git=["create_worktree"],
        isolated_dir=isolated_autoswe_dir,
    ) as hw:
        from tests.scenarios.runner import run_one_turn
        run_one_turn("owner", "repo", cfg, isolated_autoswe_dir)

    # ---- Assertions ----
    from tests.scenarios.runner import get_queue_task

    task_id = "gh:owner_repo_42"
    task = get_queue_task(isolated_autoswe_dir, task_id)
    assert task is not None, "Task not found in queue"

    # (c) suppress_welcome=True and autoswe_status="planned"
    assert task["autoswe_status"] == "planned", (
        f"Expected status=planned, got {task['autoswe_status']!r}"
    )
    assert task.get("suppress_welcome") is True, (
        f"Expected suppress_welcome=True, got {task.get('suppress_welcome')!r}"
    )

    # (a) Two bot comments exist (welcome + plan)
    # Check both the comments dict and posted_comments list
    all_bodies = [(pc.get("body", ""), None) for pc in hw.fake.posted_comments]
    for _ci, comments in hw.fake.comments.items():
        for c in comments:
            all_bodies.append((c.get("body", ""), c.get("id")))

    bot_bodies = [(body, cid) for body, cid in all_bodies if body and any(
        marker in body for marker in ["autoSWE", "## Plan", "autoswe-bot"]
    )]
    assert len(bot_bodies) >= 2, (
        f"Expected at least 2 bot comments, got {len(bot_bodies)}: "
        f"{[b[:60] for b, _ in bot_bodies]}"
    )

    # (b) Welcome comment posted before handler output
    welcome_id = None
    handler_id = None
    for body, cid in bot_bodies:
        if "autoSWE picked up this issue" in body:
            welcome_id = cid
        elif "## Plan" in body:
            handler_id = cid

    assert welcome_id is not None, (
        f"Welcome comment not found. Bodies: {[b[:60] for b, _ in bot_bodies]}"
    )
    assert handler_id is not None, (
        f"Plan comment not found. Bodies: {[b[:60] for b, _ in bot_bodies]}"
    )
    if welcome_id is not None and handler_id is not None:
        assert welcome_id < handler_id, (
            f"Welcome comment (id={welcome_id}) was not posted before "
            f"plan comment (id={handler_id})"
        )
