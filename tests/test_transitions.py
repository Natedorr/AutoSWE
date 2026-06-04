"""State-engine transition matrix tests.

Drives each row from ``tests/scenarios/transitions.py`` through the
``patched_world`` harness for both GitHub and Azure providers, then asserts
the expected outcomes (label, queue status, comments, Claude calls, git calls).

Usage::

    pytest tests/test_transitions.py -v
    pytest tests/test_transitions.py -k "fresh_plan" -v
"""
from pathlib import Path

import pytest

from tests.scenarios.harness import (
    assert_claude_calls,
    assert_comments_posted,
    assert_git_calls,
    assert_label_is,
    assert_no_git_calls,
    assert_queue_task,
    build_test_cfg,
    patched_world,
    seed_queue,
    setup_repos,
)
from tests.scenarios.transitions import (
    CODEX_TRANSITIONS,
    TRANSITIONS,
    _permission_to_sandbox,
    build_azure_state,
    build_github_state,
    build_queue_task,
)

# ---------------------------------------------------------------------------
# Parametrization

transition_names = [row["name"] for row in TRANSITIONS]


def _get_row(name: str) -> dict:
    for row in TRANSITIONS:
        if row["name"] == name:
            return row
    raise ValueError(f"Unknown transition: {name!r}")


@pytest.mark.transition
@pytest.mark.parametrize("provider", ["github", "azure"])
@pytest.mark.parametrize("transition_name", transition_names)
def test_transition(
    transition_name: str,
    provider: str,
    isolated_autoswe_dir: Path,
):
    """Run one transition row through the full sync+dispatch cycle."""
    row = _get_row(transition_name)
    skip_providers = row.get("skip_providers", [])
    if provider in skip_providers:
        pytest.skip(f"{transition_name} skipped for {provider}: known limitation")
    expect = row.get("expect", {})

    state = build_github_state(row) if provider == "github" else build_azure_state(row)

    queue_task = build_queue_task(row, provider)

    # Seed queue
    seed_queue(isolated_autoswe_dir, queue_task)

    # Set up repos.json
    setup_repos(isolated_autoswe_dir, provider, state)

    cfg = build_test_cfg(isolated_autoswe_dir, provider)

    claude_responses = row.get("claude_responses", [])
    git_calls = row.get("git_calls", [])

    with patched_world(
        provider,
        state=state,
        claude_responses=claude_responses,
        scripted_git=git_calls,
        isolated_dir=isolated_autoswe_dir,
        row_meta=row.get("meta"),
    ) as hw:
        from tests.scenarios.runner import run_one_turn

        if provider == "github":
            owner, repo = state["owner"], state["repo"]
        else:
            owner, repo = state["org"], state["project"]

        run_one_turn(owner, repo, cfg, isolated_autoswe_dir)

    # ---- Assertions ----
    issue_num = 42  # All transitions use issue #42

    # Label assertion
    if "label_after" in expect:
        if provider == "github":
            from tests.scenarios.runner import assert_label_is
            assert_label_is(hw.fake, issue_num, expect["label_after"])
        else:
            _assert_azure_tag(hw.fake, issue_num, expect["label_after"])

    # Queue task assertions
    queue_fields = {}
    for key in ("autoswe_status", "session_id", "pending_command"):
        if key in expect:
            queue_fields[key] = expect[key]

    # first_dispatched_at_reset: verify it was cleared during sync restart
    if expect.get("first_dispatched_at_reset"):
        task_id = queue_task["id"] if queue_task else (
            f"gh:{state['owner']}_{state['repo']}_{issue_num}"
            if provider == "github"
            else f"ado:{state['org']}_{state['project']}/testrepo_{issue_num}"
        )
        from tests.scenarios.runner import get_queue_task
        actual_task = get_queue_task(isolated_autoswe_dir, task_id)
        # After dispatch, first_dispatched_at will be set to current time
        # The key assertion: it should NOT be the old timestamp from the fixture
        assert actual_task is not None, f"Task {task_id!r} not found in queue after transition"
        assert actual_task.get("first_dispatched_at") != "2026-01-01T07:00:00+00:00", (
            "first_dispatched_at should have been reset during sync restart "
            "(fix #119: plan_ready → pending phase transition)"
        )
    if queue_fields:
        task_id = queue_task["id"] if queue_task else (
            f"gh:{state['owner']}_{state['repo']}_{issue_num}"
            if provider == "github"
            else f"ado:{state['org']}_{state['project']}/testrepo_{issue_num}"
        )
        assert_queue_task(isolated_autoswe_dir, task_id, queue_fields)

    # Comment assertions
    if "comment_contains" in expect:
        assert_comments_posted(hw.fake, [{"body_contains": expect["comment_contains"]}])

    # Claude call assertions
    no_claude = expect.get("no_claude_calls", False)
    if no_claude:
        assert len(hw.claude.calls) == 0, "Expected no Claude calls"
    elif "claude_permission" in expect:
        assert_claude_calls(hw.claude, [{"permission_mode": expect["claude_permission"]}])

    # Git call assertions
    if git_calls:
        assert_git_calls(hw.git, git_calls)
    elif expect.get("no_git_calls"):
        assert_no_git_calls(hw.git)


# ---------------------------------------------------------------------------
# Codex backend — parametrized test

codex_transition_names = list(CODEX_TRANSITIONS)


@pytest.mark.transition
@pytest.mark.parametrize("transition_name", codex_transition_names)
def test_transition_codex(
    transition_name: str,
    isolated_autoswe_dir: Path,
):
    """Run a curated Codex transition row through the real CodexBackend.

    Verifies the orchestrator behaves correctly when driven by the Codex
    backend — end-to-end through CodexBackend → JSONL parser → RunResult
    → coder/planner/reviewer → emit → label/comment/queue.

    Azure is excluded to avoid the 4× matrix blowup; Codex + GitHub suffices
    to assert the backend-divergent paths (sandbox/mode, JSONL parsing).
    """
    row = _get_row(transition_name)
    expect = row.get("expect", {})
    provider = "github"

    state = build_github_state(row)
    queue_task = build_queue_task(row, provider)

    # Seed queue
    seed_queue(isolated_autoswe_dir, queue_task)

    # Set up repos.json
    setup_repos(isolated_autoswe_dir, provider, state)

    # Build config with codex backend
    cfg = build_test_cfg(isolated_autoswe_dir, provider, backend="codex")

    claude_responses = row.get("claude_responses", [])
    git_calls = row.get("git_calls", [])

    with patched_world(
        provider,
        state=state,
        claude_responses=claude_responses,
        scripted_git=git_calls,
        isolated_dir=isolated_autoswe_dir,
        row_meta=row.get("meta"),
        backend="codex",
    ) as hw:
        from tests.scenarios.runner import run_one_turn

        owner, repo = state["owner"], state["repo"]
        run_one_turn(owner, repo, cfg, isolated_autoswe_dir)

    # ---- Assertions (same as Claude, but with backend-aware checks) ----
    issue_num = 42

    # Label assertion
    if "label_after" in expect:
        assert_label_is(hw.fake, issue_num, expect["label_after"])

    # Queue task assertions
    queue_fields = {}
    for key in ("autoswe_status", "session_id", "pending_command"):
        if key in expect:
            queue_fields[key] = expect[key]

    if expect.get("first_dispatched_at_reset"):
        task_id = queue_task["id"] if queue_task else f"gh:{state['owner']}_{state['repo']}_{issue_num}"
        from tests.scenarios.runner import get_queue_task

        actual_task = get_queue_task(isolated_autoswe_dir, task_id)
        assert actual_task is not None
        assert actual_task.get("first_dispatched_at") != "2026-01-01T07:00:00+00:00"

    if queue_fields:
        task_id = queue_task["id"] if queue_task else f"gh:{state['owner']}_{state['repo']}_{issue_num}"
        assert_queue_task(isolated_autoswe_dir, task_id, queue_fields)

    # Comment assertions
    if "comment_contains" in expect:
        assert_comments_posted(hw.fake, [{"body_contains": expect["comment_contains"]}])

    # Codex call assertions (backend-aware)
    no_codex = expect.get("no_claude_calls", False)
    if no_codex:
        assert len(hw.codex.calls) == 0, "Expected no Codex calls"
    elif "claude_permission" in expect:
        # Translate claude_permission → expected sandbox
        expected_sandbox = _permission_to_sandbox(expect["claude_permission"])
        from tests.scenarios.runner import assert_codex_calls

        # Codex resume mode doesn't use --sandbox (the CLI doesn't support it).
        # If the first call is a resume, assert is_resume=True; otherwise assert sandbox.
        if hw.codex.calls and hw.codex.calls[0].get("is_resume"):
            assert_codex_calls(hw.codex, [{"is_resume": True}])
        else:
            assert_codex_calls(hw.codex, [{"sandbox": expected_sandbox}])

    # Git call assertions
    if git_calls:
        assert_git_calls(hw.git, git_calls)
    elif expect.get("no_git_calls"):
        assert_no_git_calls(hw.git)


# ---------------------------------------------------------------------------
# Azure helpers


def _assert_azure_tag(fake, wi_number: int, expected_label: str) -> None:
    """Assert autoswe tag on Azure work item."""
    tags_raw = fake.work_items.get(wi_number, {}).get("fields", {}).get("System.Tags", "")
    tags = [t.strip() for t in tags_raw.split(";") if t.strip()] if tags_raw else []
    autoswe_tags = [t for t in tags if t.startswith("autoswe:")]
    expected_tag = expected_label  # e.g. "autoswe:plan_ready"
    assert expected_tag in autoswe_tags, (
        f"Expected tag {expected_tag!r} not found. "
        f"Actual autoswe tags: {autoswe_tags}"
    )
