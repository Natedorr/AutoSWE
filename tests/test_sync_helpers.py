"""Tests for sync helper functions (welcomes, welcome-building).

All _sync_repo integration logic has moved to the orchestrator decide/emit
fixtures (tests/fixtures/decide/). This file retains only pure-function tests.
"""
from autoswe.orch.loop import _build_welcome_comment, _ensure_queue_entry

# ---------------------------------------------------------------------------
# _build_welcome_comment
# ---------------------------------------------------------------------------


def test_build_welcome_comment_includes_slash_command():
    """_build_welcome_comment should include the slash command."""
    comment = _build_welcome_comment("/fix", "with speed", "o_r_1")
    assert "/fix" in comment
    assert "autoswe-bot" in comment


def test_build_welcome_comment_uses_template():
    """_build_welcome_comment should use WELCOME_FILE if available."""
    comment = _build_welcome_comment("", "", "slug")
    assert "slug" in comment


# ---------------------------------------------------------------------------
# _single_poll skip-rule input building
#
# Regression tests for the stem_prefix bug: queue slugs use colons (gh:/ado:)
# but _is_repo_locked PID stems use underscores (gh_/ado_). The skip-rule
# input-building loop iterates queue keys (colons), so it must match with
# colons — otherwise prev_updated and force_fetch are always empty.
# ---------------------------------------------------------------------------


def test_single_poll_prev_updated_populated_from_queue_github(
    isolated_autoswe_dir, monkeypatch, tmp_path,
):
    """_single_poll must populate prev_updated from queue entries with colons."""
    import json

    from autoswe.core.queue_store import LockedQueue
    from autoswe.orch.types import ApiState
    from autoswe.providers.base import NormalizedIssue
    repos_path = isolated_autoswe_dir / "config" / "repos.json"
    repos_path.write_text(
        json.dumps({"owner/repo": {"provider": "github", "pat": "fake", "base_branch": "main"}})
    )

    # Seed queue with an existing entry using the correct slug format (colon)
    task_id = "gh:owner_repo_1"
    with LockedQueue() as lq:
        lq.queue[task_id] = {
            "id": task_id,
            "owner": "owner",
            "repo": "repo",
            "issue_number": 1,
            "title": "Test",
            "body": "Body",
            "autoswe_status": None,
            "last_updated": "2026-01-01T00:00:00Z",
            "last_comment_sync": None,
            "base_branch": "main",
            "provider": "github",
            "suppress_welcome": True,
            "pr_number": None,
            "welcome_comment_id": None,
            "bot_comment_ids": [],
            "last_dispatched_command_id": None,
            "last_consumed_reply_id": None,
            "last_synced": "2026-01-01T00:00:00Z",
            "created_at": "2026-01-01T00:00:00Z",
            "gh_closed": False,
        }

    import autoswe.orch.loop as loop_mod

    captured_args = {}

    def fake_read_api(tracker, repo_cfg, cfg, *, bot_ids=None, prev_updated=None, force_fetch=None):
        captured_args["prev_updated"] = prev_updated or {}
        captured_args["force_fetch"] = force_fetch or set()
        return {
            1: ApiState(
                issue=NormalizedIssue(
                    number=1, title="Test", body="Body",
                    owner="owner", repo="repo", state="open",
                    is_pull_request=False, labels=[],
                    last_updated="2026-01-01T00:00:00Z",
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

    loop_mod.poll(cfg, mode="sync", repo_filter="owner/repo")

    # prev_updated should contain the entry from the queue
    assert 1 in captured_args["prev_updated"], (
        "prev_updated should contain issue #1 from the queue entry. "
        "If empty, the stem_prefix matching is broken (colon vs underscore bug)."
    )
    assert captured_args["prev_updated"][1] == "2026-01-01T00:00:00Z"
    # Issue is not in pending/dispatched, so force_fetch should NOT contain it
    assert 1 not in captured_args["force_fetch"]


def test_single_poll_force_fetch_for_pending_tasks(
    isolated_autoswe_dir, monkeypatch, tmp_path,
):
    """Tasks with autoswe_status='pending' must be in force_fetch set."""
    import json

    from autoswe.core.queue_store import LockedQueue
    from autoswe.orch.types import ApiState
    from autoswe.providers.base import NormalizedIssue
    repos_path = isolated_autoswe_dir / "config" / "repos.json"
    repos_path.write_text(
        json.dumps({"owner/repo": {"provider": "github", "pat": "fake", "base_branch": "main"}})
    )

    task_id = "gh:owner_repo_1"
    with LockedQueue() as lq:
        lq.queue[task_id] = {
            "id": task_id,
            "owner": "owner",
            "repo": "repo",
            "issue_number": 1,
            "title": "Test",
            "body": "Body\n\n/fix",
            "autoswe_status": "pending",
            "last_updated": "2026-01-01T00:00:00Z",
            "last_comment_sync": None,
            "base_branch": "main",
            "provider": "github",
            "suppress_welcome": True,
            "pr_number": None,
            "welcome_comment_id": None,
            "bot_comment_ids": [],
            "last_dispatched_command_id": None,
            "last_consumed_reply_id": None,
            "last_synced": "2026-01-01T00:00:00Z",
            "created_at": "2026-01-01T00:00:00Z",
            "gh_closed": False,
        }

    import autoswe.orch.loop as loop_mod

    captured_args = {}

    def fake_read_api(tracker, repo_cfg, cfg, *, bot_ids=None, prev_updated=None, force_fetch=None):
        captured_args["prev_updated"] = prev_updated or {}
        captured_args["force_fetch"] = force_fetch or set()
        return {
            1: ApiState(
                issue=NormalizedIssue(
                    number=1, title="Test", body="Body\n\n/fix",
                    owner="owner", repo="repo", state="open",
                    is_pull_request=False, labels=[],
                    last_updated="2026-01-01T00:00:00Z",
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

    loop_mod.poll(cfg, mode="sync", repo_filter="owner/repo")

    # Issue #1 is pending → must be force-fetched
    assert 1 in captured_args["force_fetch"], (
        "pending task must be in force_fetch set"
    )
    assert 1 in captured_args["prev_updated"]


def test_single_poll_label_mirror_idempotent(
    isolated_autoswe_dir, monkeypatch, tmp_path,
):
    """Phase 3 label mirror should skip set_status when issue.status already matches queue status."""
    import json

    from autoswe.core.queue_store import LockedQueue
    from autoswe.orch.types import ApiState
    from autoswe.providers.base import NormalizedIssue
    repos_path = isolated_autoswe_dir / "config" / "repos.json"
    repos_path.write_text(
        json.dumps({"owner/repo": {"provider": "github", "pat": "fake", "base_branch": "main"}})
    )

    task_id = "gh:owner_repo_1"
    with LockedQueue() as lq:
        lq.queue[task_id] = {
            "id": task_id,
            "owner": "owner",
            "repo": "repo",
            "issue_number": 1,
            "title": "Test",
            "body": "Body",
            "autoswe_status": "fixed",
            "last_updated": "2026-01-01T00:00:00Z",
            "last_comment_sync": None,
            "base_branch": "main",
            "provider": "github",
            "suppress_welcome": True,
            "pr_number": None,
            "welcome_comment_id": None,
            "bot_comment_ids": [],
            "last_dispatched_command_id": None,
            "last_consumed_reply_id": None,
            "last_synced": "2026-01-01T00:00:00Z",
            "created_at": "2026-01-01T00:00:00Z",
            "gh_closed": False,
        }

    import autoswe.orch.loop as loop_mod

    set_status_calls = []

    class FakeTracker:
        def set_status(self, repo_cfg, issue_num, label):
            set_status_calls.append((issue_num, label))
        def post_comment(self, repo_cfg, issue_num, body):
            pass
        def fetch_comments(self, *a, **kw):
            return []

    import autoswe.providers.factory as factory_mod

    monkeypatch.setattr(loop_mod, "get_tracker", lambda r: FakeTracker())
    monkeypatch.setattr(factory_mod, "get_tracker", lambda r: FakeTracker())

    def fake_read_api(tracker, repo_cfg, cfg, *, bot_ids=None, prev_updated=None, force_fetch=None):
        return {
            1: ApiState(
                issue=NormalizedIssue(
                    number=1, title="Test", body="Body",
                    owner="owner", repo="repo", state="open",
                    is_pull_request=False,
                    labels=["autoswe:fixed"],
                    status="fixed",  # Already matches queue status
                    last_updated="2026-01-01T00:00:00Z",
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

    loop_mod.poll(cfg, mode="sync", repo_filter="owner/repo")

    # set_status should NOT be called because issue.status ("fixed") already
    # matches queue status ("fixed")
    assert len(set_status_calls) == 0, (
        f"set_status should be skipped when label already matches. "
        f"Called {len(set_status_calls)} times: {set_status_calls}"
    )


# ---------------------------------------------------------------------------
# _ensure_queue_entry — new fields
# ---------------------------------------------------------------------------


def test_ensure_queue_entry_includes_last_updated_fields():
    """New queue entries should include last_updated and last_comment_sync."""
    from autoswe.orch.types import ApiState
    from autoswe.providers.base import NormalizedIssue

    api = ApiState(
        issue=NormalizedIssue(
            number=1, title="T", body="B",
            owner="o", repo="r",
            last_updated="2026-01-01T00:00:00Z",
        ),
        comments=(),
    )
    queue = {}
    _ensure_queue_entry(
        queue, "gh__o_r_1", api, "o", "r", 1,
        "2026-01-01T00:00:00Z", "main", "github", False,
    )

    entry = queue["gh__o_r_1"]
    assert "last_updated" in entry
    assert entry["last_updated"] is None
    assert "last_comment_sync" in entry
    assert entry["last_comment_sync"] is None


def test_ensure_queue_entry_does_not_overwrite_existing():
    """_ensure_queue_entry should not clobber existing last_updated values."""
    from autoswe.orch.types import ApiState
    from autoswe.providers.base import NormalizedIssue

    api = ApiState(
        issue=NormalizedIssue(
            number=1, title="T", body="B",
            owner="o", repo="r",
            last_updated="2026-01-02T00:00:00Z",
        ),
        comments=(),
    )
    queue = {
        "gh__o_r_1": {
            "title": "Old title",
            "body": "Old body",
            "last_updated": "2026-01-01T00:00:00Z",
            "last_comment_sync": "2026-01-01T12:00:00Z",
        }
    }
    _ensure_queue_entry(
        queue, "gh__o_r_1", api, "o", "r", 1,
        "2026-01-02T00:00:00Z", "main", "github", False,
    )

    entry = queue["gh__o_r_1"]
    assert entry["title"] == "T"
    assert entry["last_updated"] == "2026-01-01T00:00:00Z"  # Not overwritten
    assert entry["last_comment_sync"] == "2026-01-01T12:00:00Z"


# ---------------------------------------------------------------------------
# _sync_before_dispatch
# ---------------------------------------------------------------------------

def _make_task():
    return {
        "id": "gh:o_r_1",
        "owner": "o",
        "repo": "r",
        "issue_number": 1,
        "title": "T",
        "body": "B",
        "base_branch": "main",
        "_token": "tok",
    }


def _patch_sync_before(tmp_path, sync_result, monkeypatch):
    """Return a context-manager stack that patches the sync_branch seams."""
    from contextlib import ExitStack
    from unittest.mock import patch

    stack = ExitStack()
    # worktree_path returns a path that already exists so create_worktree is skipped
    tmp_path.mkdir(parents=True, exist_ok=True)
    stack.enter_context(
        patch("autoswe.orch.run.worktree_mod.worktree_path", return_value=tmp_path)
    )
    stack.enter_context(
        patch("autoswe.orch.run.worktree_mod.sync_branch", return_value=sync_result)
    )
    return stack


def test_sync_before_dispatch_merge_conflict_resolve_false_returns_wt_none(tmp_path):
    """merge conflict + resolve_conflicts=False → (wt, None), no resolve_sync_conflicts call."""
    from unittest.mock import patch

    sync_result = {
        "synced": False,
        "conflict": True,
        "branch": "autoswe/issue-1",
        "ahead": 0,
        "conflict_files": ["src/a.py"],
    }
    resolve_calls = []

    with _patch_sync_before(tmp_path, sync_result, None):
        with patch("autoswe.orch.run.coder.resolve_sync_conflicts", side_effect=resolve_calls.append):
            from autoswe.orch.run import _sync_before_dispatch
            wt, err = _sync_before_dispatch(
                _make_task(), {}, {}, None,
                phase="fix", branch_for_create="main", resolve_conflicts=False,
            )

    assert err is None, "should proceed without error when resolve_conflicts=False"
    assert wt == tmp_path
    assert resolve_calls == [], "resolve_sync_conflicts must NOT be called"


def test_sync_before_dispatch_merge_conflict_resolve_true_calls_resolver(tmp_path):
    """merge conflict + resolve_conflicts=True → resolve_sync_conflicts is called (plan/review path)."""
    from unittest.mock import patch

    from autoswe.harness.runner import HandlerResult

    sync_result = {
        "synced": False,
        "conflict": True,
        "branch": "autoswe/issue-1",
        "ahead": 0,
        "conflict_files": ["src/a.py"],
    }

    def fake_resolve(task, files, **kwargs):
        return HandlerResult("DONE_SUMMARY\tok\t")

    with _patch_sync_before(tmp_path, sync_result, None):
        with patch("autoswe.orch.run.coder.resolve_sync_conflicts", side_effect=fake_resolve) as mock_resolve:
            from autoswe.orch.run import _sync_before_dispatch
            wt, err = _sync_before_dispatch(
                _make_task(), {}, {}, None,
                phase="plan", branch_for_create="main", resolve_conflicts=True,
            )

    assert err is None
    mock_resolve.assert_called_once()


def test_sync_before_dispatch_rebase_conflict_returns_failed_handler_result(tmp_path):
    """rebase conflict → HandlerResult with FAILED message instead of silent pass-through."""
    from autoswe.harness.runner import HandlerResult

    sync_result = {
        "synced": False,
        "conflict": True,
        "rebase": True,
        "branch": "autoswe/issue-1",
        "ahead": 0,
        "conflict_files": ["src/b.py"],
        "error": "rebase conflict: …",
    }

    with _patch_sync_before(tmp_path, sync_result, None):
        from autoswe.orch.run import _sync_before_dispatch
        wt, err = _sync_before_dispatch(
            _make_task(), {}, {}, None,
            phase="fix", branch_for_create="main",
        )

    assert err is not None, "rebase conflict must return an error HandlerResult"
    assert isinstance(err, HandlerResult)
    assert "FAILED" in (err.done_content or "")
    assert "rebase conflict" in (err.done_content or "").lower()
