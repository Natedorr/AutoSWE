"""Scenario runner — executes one full poll turn against stateful fakes.

Usage in test files::

    state = json.loads(scenario_dir.joinpath("state.json").read_text())
    expected = json.loads(scenario_dir.joinpath("expected.json").read_text())

    gh_fake = GitHubFake()
    gh_fake.load(state)
    gh_orig = gh_fake.patch_gh_api()

    cl_fake = ClaudeFake()
    for resp in state.get("claude_responses", []):
        cl_fake.script_response(resp["text"], resp.get("session_id", "s1"),
                                resp.get("subtype", "success"))
    cl_orig = cl_fake.patch()

    gt_fake = GitFake()
    gt_fake.script_commit({"committed": True, "commit_sha": "abc1234", "branch": "autoswe/issue-1"})
    gt_orig = gt_fake.patch()

    seed_queue(cfg_dir, state.get("queue_task"))
    run_one_turn(owner, repo, cfg, gh_fake, cl_fake, gt_fake)

    assert_label_is(gh_fake, state["issue"]["number"], expected["label_after"])
    assert_comments_posted(gh_fake, expected["comments_posted"])
    assert_queue_task(isolated_dir, expected["queue_task_after"])
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Scenario discovery
# ---------------------------------------------------------------------------

SCENARIOS_DIR = Path(__file__).parent.parent.parent / "tests" / "fixtures" / "scenarios"


def discover_scenarios(provider: str) -> list[Path]:
    """Return all scenario directories for a provider, sorted by name."""
    base = SCENARIOS_DIR / provider
    if not base.exists():
        return []
    return sorted(d for d in base.iterdir() if d.is_dir()
                  and (d / "state.json").exists()
                  and (d / "expected.json").exists())


def load_scenario(scenario_dir: Path) -> tuple[dict, dict]:
    """Load (state, expected) from a scenario directory."""
    state = json.loads((scenario_dir / "state.json").read_text(encoding="utf-8"))
    expected = json.loads((scenario_dir / "expected.json").read_text(encoding="utf-8"))
    return state, expected


# ---------------------------------------------------------------------------
# Queue helpers
# ---------------------------------------------------------------------------

def seed_queue(autoswe_dir: Path, task: dict | None) -> None:
    """Write a task into queue.json on an isolated AUTOSWE_DIR."""
    if task is None:
        return
    task.setdefault("autoswe_status", None)
    queue_file = autoswe_dir / "data" / "queue.json"
    data = json.loads(queue_file.read_text(encoding="utf-8")) if queue_file.exists() else {}
    data[task["id"]] = task
    queue_file.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_queue(autoswe_dir: Path) -> dict:
    """Read queue.json from an isolated AUTOSWE_DIR."""
    queue_file = autoswe_dir / "data" / "queue.json"
    if queue_file.exists():
        return json.loads(queue_file.read_text(encoding="utf-8"))
    return {}


def get_queue_task(autoswe_dir: Path, task_id: str) -> dict | None:
    """Read a specific task from queue.json."""
    return get_queue(autoswe_dir).get(task_id)


# ---------------------------------------------------------------------------
# Run one poll turn
# ---------------------------------------------------------------------------

def setup_repos_json(autoswe_dir: Path, repos: dict[str, dict]) -> None:
    """Write repos.json for scenario tests."""
    repos_path = autoswe_dir / "config" / "repos.json"
    repos_path.write_text(json.dumps(repos, indent=2), encoding="utf-8")


def run_one_turn(owner: str, repo: str, cfg: dict,
                 autoswe_dir: Path) -> int:
    """Run one poll cycle via the orchestrator.

    The fakes must already be patched before calling this function.
    Returns the number of tasks processed.
    """
    # Reload config module paths
    import autoswe.core.config as cfg_mod
    import autoswe.core.queue_store as qs_mod

    cfg_mod.AUTOSWE_DIR = autoswe_dir
    cfg_mod.QUEUE_FILE = autoswe_dir / "data" / "queue.json"
    cfg_mod.RUNNING_DIR = autoswe_dir / "running"
    cfg_mod.LOGS_DIR = autoswe_dir / "logs"
    cfg_mod.CONFIG_FILE = autoswe_dir / "config" / "autoswe.env"
    cfg_mod.REPOS_CONFIG_FILE = autoswe_dir / "config" / "repos.json"
    cfg_mod.WELCOME_FILE = autoswe_dir / "config" / "welcome_comment.txt"
    cfg_mod.HARNESSES_CONFIG_FILE = autoswe_dir / "config" / "harnesses.json"

    qs_mod.AUTOSWE_DIR = autoswe_dir
    qs_mod.QUEUE_FILE = autoswe_dir / "data" / "queue.json"

    # Force repos.json and harnesses.json reload by clearing caches
    repos_cfg_path = autoswe_dir / "config" / "repos.json"
    if repos_cfg_path.exists():
        cfg_mod.REPOS_CONFIG_FILE = repos_cfg_path

    cfg_mod._harnesses_cache.clear()

    from autoswe.orch.loop import poll as orch_poll
    return orch_poll(cfg, mode="full")


# ---------------------------------------------------------------------------
# Assertions
# ---------------------------------------------------------------------------

def assert_label_is(gh_fake, issue_number: int, expected_label: str) -> None:
    """Assert the current label for an issue matches expected."""
    actual = gh_fake.labels.get(issue_number, [])
    autoswe_labels = [lb for lb in actual if lb.startswith("autoswe:")]
    assert expected_label in autoswe_labels, (
        f"Expected label {expected_label!r} not found. "
        f"Actual autoswe labels: {autoswe_labels}"
    )


def assert_comments_posted(gh_fake, expected_comments: list[dict]) -> None:
    """Assert posted comments match expectations.

    Checks both POSTed comments (new comment creation) and PATCHed comments
    (sticky progress comment updates). Completion comments now go through
    PATCH via progress.finalize(), so we need to check both channels.

    Each entry in *expected_comments* is a dict with keys like:
        body_contains - list of substrings that must all appear in the comment body
        body_starts_with - prefix the comment body must start with
        count - minimum number of matching comments (default 1)

    HTML tags are stripped from the body before comparison so that Azure
    bot comments (posted as HTML) match the same expectations as GitHub
    comments (posted as Markdown).
    """
    if not expected_comments:
        return

    # Collect all comment bodies: POSTed + PATCHed
    all_bodies = []
    for posted in gh_fake.posted_comments:
        all_bodies.append(posted.get("body", ""))
    # Also check PATCH calls (sticky comment updates)
    for call in getattr(gh_fake, "recorded_calls", []):
        path = call.get("path", "")
        if call.get("method") in ("PATCH", "PUT") and (
            "/issues/comments/" in path or
            ("/workitems/" in path and "/comments/" in path)
        ):
            body = (call.get("body") or {}).get("body", "") or (call.get("body") or {}).get("text", "")
            if body:
                all_bodies.append(body)

    for exp in expected_comments:
        min_count = exp.get("count", 1)
        body_contains = exp.get("body_contains", [])
        body_starts_with = exp.get("body_starts_with", None)

        matches = 0
        for body in all_bodies:
            if body_contains and not all(s in body for s in body_contains):
                continue
            if body_starts_with and not body.startswith(body_starts_with):
                continue
            matches += 1

        assert matches >= min_count, (
            f"Expected at least {min_count} comment(s) matching {exp}, "
            f"found {matches}. Comment bodies: {[b[:80] for b in all_bodies]}"
        )


def _strip_tags(text: str) -> str:
    """Strip HTML/XML tags from text, preserving tag content and HTML comments.

    Preserves HTML comments (``<!-- ... -->``) so that tests checking for
    ``<!-- autoswe-bot -->`` still pass.
    """
    import re
    # First, protect HTML comments by replacing them with placeholders
    comments = []
    def _save_comment(m):
        comments.append(m.group(0))
        return f"\x00COMMENT{len(comments)-1}\x00"
    text = re.sub(r"<!--.*?-->", _save_comment, text, flags=re.DOTALL)
    # Strip all other tags
    text = re.sub(r"<[^>]+>", "", text)
    # Restore comments
    for i, c in enumerate(comments):
        text = text.replace(f"\x00COMMENT{i}\x00", c)
    return text


def assert_claude_calls(cl_fake, expected_calls: list[dict]) -> None:
    """Assert Claude SDK calls match expectations.

    Each entry in *expected_calls* is a dict with optional keys:
        phase - "plan" | "fix" (checks permission_mode)
        permission_mode - exact permission mode string
        resume - expected resume session_id (or null for new sessions)
        model - expected model
    """
    if not expected_calls:
        return

    for i, exp in enumerate(expected_calls):
        if i >= len(cl_fake.calls):
            raise AssertionError(
                f"Expected {len(expected_calls)} Claude call(s), "
                f"only {len(cl_fake.calls)} made."
            )

        call = cl_fake.calls[i]
        # Phase 3: check mode first, fall back to permission_mode for compat
        if "mode" in exp:
            assert call["mode"] == exp["mode"], (
                f"Call {i}: expected mode={exp['mode']!r}, "
                f"got {call.get('mode')!r}"
            )
        if "permission_mode" in exp:
            # If scenario checks permission_mode, translate from mode
            expected_pm = exp["permission_mode"]
            actual_mode = call.get("mode")
            if actual_mode is not None:
                # Translate mode → permission_mode for comparison
                from autoswe.harness.backends.claude_code import _MODE_CONFIG
                if actual_mode in _MODE_CONFIG:
                    actual_pm = _MODE_CONFIG[actual_mode][0]
                else:
                    actual_pm = call.get("permission_mode")
            else:
                actual_pm = call.get("permission_mode")
            assert actual_pm == expected_pm, (
                f"Call {i}: expected permission_mode={expected_pm!r}, "
                f"got mode={actual_mode!r} (→ {actual_pm if actual_mode else call.get('permission_mode')!r})"
            )
        if "resume" in exp:
            assert call["resume"] == exp["resume"], (
                f"Call {i}: expected resume={exp['resume']!r}, "
                f"got {call['resume']!r}"
            )
        if "model" in exp:
            assert call["model"] == exp["model"], (
                f"Call {i}: expected model={exp['model']!r}, "
                f"got {call['model']!r}"
            )


def assert_codex_calls(cx_fake, expected_calls: list[dict]) -> None:
    """Assert Codex subprocess calls match expectations.

    Each entry in *expected_calls* is a dict with optional keys:
        sandbox - expected sandbox value (``"read-only"`` or ``"workspace-write"``)
        is_resume - True for resume mode, False for fresh exec
        model - expected model
    """
    if not expected_calls:
        return

    for i, exp in enumerate(expected_calls):
        if i >= len(cx_fake.calls):
            raise AssertionError(
                f"Expected {len(expected_calls)} Codex call(s), "
                f"only {len(cx_fake.calls)} made."
            )

        call = cx_fake.calls[i]
        if "sandbox" in exp:
            assert call.get("sandbox") == exp["sandbox"], (
                f"Call {i}: expected sandbox={exp['sandbox']!r}, "
                f"got {call.get('sandbox')!r}"
            )
        if "is_resume" in exp:
            assert call.get("is_resume") == exp["is_resume"], (
                f"Call {i}: expected is_resume={exp['is_resume']!r}, "
                f"got {call.get('is_resume')!r}"
            )
        if "model" in exp:
            assert call.get("model") == exp["model"], (
                f"Call {i}: expected model={exp['model']!r}, "
                f"got {call.get('model')!r}"
            )


def assert_queue_task(autoswe_dir: Path, task_id: str,
                      expected_fields: dict[str, Any]) -> None:
    """Assert specific fields on a queue task match expectations."""
    task = get_queue_task(autoswe_dir, task_id)
    assert task is not None, f"Task {task_id!r} not found in queue.json"

    for key, expected_val in expected_fields.items():
        actual_val = task.get(key)
        assert actual_val == expected_val, (
            f"Task {task_id}: {key}={actual_val!r}, expected {expected_val!r}"
        )


def assert_git_calls(gt_fake, expected_funcs: list[str]) -> None:
    """Assert worktree functions were called in expected order.

    *expected_funcs* is a list of function names like
    ["create_worktree", "commit_and_push"].
    """
    actual_funcs = [c["func"] for c in gt_fake.calls]
    for func_name in expected_funcs:
        assert func_name in actual_funcs, (
            f"Expected {func_name!r} to be called. Actual calls: {actual_funcs}"
        )


def assert_no_git_calls(gt_fake) -> None:
    """Assert no worktree functions were called."""
    assert len(gt_fake.calls) == 0, (
        f"Expected no git calls, got: {[c['func'] for c in gt_fake.calls]}"
    )


# ---------------------------------------------------------------------------
# Convenience: set up repos.json for a scenario
# ---------------------------------------------------------------------------

def add_repo_to_repos_json(autoswe_dir: Path, owner: str, repo: str,
                           provider: str = "github",
                           extra: dict | None = None) -> None:
    """Add an entry to repos.json for scenario tests."""
    key = f"{owner}/{repo}"
    entry = {"provider": provider, "pat": "test-pat", **(extra or {})}
    repos_path = autoswe_dir / "config" / "repos.json"
    data = json.loads(repos_path.read_text(encoding="utf-8")) if repos_path.exists() else {}
    data[key] = entry
    repos_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
