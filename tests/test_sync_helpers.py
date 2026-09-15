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

    def fake_read_api(tracker, *, bot_ids=None, prev_updated=None, force_fetch=None):
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

    monkeypatch.setattr(loop_mod, "read_api", fake_read_api)

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

    def fake_read_api(tracker, *, bot_ids=None, prev_updated=None, force_fetch=None):
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

    monkeypatch.setattr(loop_mod, "read_api", fake_read_api)

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
            "last_dispatched_command": "/fix",
            "attempt_count": 1,
            "last_dispatched_command_id": None,
            "last_consumed_reply_id": None,
            "last_synced": "2026-01-01T00:00:00Z",
            "created_at": "2026-01-01T00:00:00Z",
            "gh_closed": False,
        }

    import autoswe.orch.loop as loop_mod

    set_status_calls = []

    class FakeTracker:
        def set_status(self, issue_num, label):
            set_status_calls.append((issue_num, label))
        def post_comment(self, issue_num, body):
            pass
        def fetch_comments(self, *a, **kw):
            return []
        def slug_prefix(self):
            return "gh"

    import autoswe.providers.factory as factory_mod

    monkeypatch.setattr(loop_mod, "get_tracker", lambda r: FakeTracker())
    monkeypatch.setattr(factory_mod, "get_tracker", lambda r: FakeTracker())

    def fake_read_api(tracker, *, bot_ids=None, prev_updated=None, force_fetch=None):
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

    monkeypatch.setattr(loop_mod, "read_api", fake_read_api)

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


# ---------------------------------------------------------------------------
# gh_closed detection — no fabricated terminal on never-dispatched tasks
# ---------------------------------------------------------------------------
#
# Regression for issue #258: a queue entry whose issue dropped out of the
# open-issues list used to be marked gh_closed=True AND autoswe_status =
# completed_status_for(_kind_from_command(last_dispatched_command or "/fix"))
# unconditionally — a fresh, never-dispatched entry (last_dispatched_command
# is None) landed on "fixed" in the queue and as the autoswe:fixed GitHub
# label, a false terminal state that drivers skip.
# ---------------------------------------------------------------------------


def _seed_queue(isolated_autoswe_dir, task_id, **overrides):
    """Seed a queue entry for owner/repo#1 with the given overrides."""
    from autoswe.core.queue_store import LockedQueue

    entry = {
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
        "last_dispatched_command": None,
        "last_dispatched_command_id": None,
        "last_consumed_reply_id": None,
        "last_synced": "2026-01-01T00:00:00Z",
        "created_at": "2026-01-01T00:00:00Z",
        "gh_closed": False,
    }
    entry.update(overrides)
    with LockedQueue() as lq:
        lq.queue[task_id] = entry


def _read_queue(isolated_autoswe_dir, task_id):
    from autoswe.core.queue_store import LockedQueue

    with LockedQueue() as lq:
        return dict(lq.queue[task_id])


def _run_poll(isolated_autoswe_dir, monkeypatch, tmp_path, open_issues):
    """Run one sync-mode poll; return (set_status calls, clear_status calls)."""
    import autoswe.orch.loop as loop_mod
    import autoswe.providers.factory as factory_mod
    from autoswe.orch.types import ApiState
    from autoswe.providers.base import NormalizedIssue

    set_status_calls = []
    clear_status_calls = []

    class FakeTracker:
        def set_status(self, issue_num, label):
            set_status_calls.append((issue_num, label))

        def clear_status(self, issue_num):
            clear_status_calls.append(issue_num)

        def post_comment(self, issue_num, body):
            pass

        def fetch_comments(self, *a, **kw):
            return []

        def slug_prefix(self):
            return "gh"

    def fake_read_api(tracker, *, bot_ids=None, prev_updated=None, force_fetch=None):
        result = {}
        for num in open_issues:
            result[num] = ApiState(
                issue=NormalizedIssue(
                    number=num, title="Test", body="Body",
                    owner="owner", repo="repo", state="open",
                    is_pull_request=False, labels=[],
                    last_updated="2026-01-01T00:00:00Z",
                ),
                comments=(),
            )
        return result

    monkeypatch.setattr(loop_mod, "get_tracker", lambda r: FakeTracker())
    monkeypatch.setattr(factory_mod, "get_tracker", lambda r: FakeTracker())
    monkeypatch.setattr(loop_mod, "read_api", fake_read_api)

    loop_mod.poll(
        {
            "MAX_CONCURRENT": 1,
            "SILENT_REPORTING": True,
            "WORKTREE_DIR": str(tmp_path / "worktrees"),
        },
        mode="sync",
        repo_filter="owner/repo",
    )
    return set_status_calls, clear_status_calls


def test_single_poll_gh_closed_fresh_entry_stays_neutral(isolated_autoswe_dir, monkeypatch, tmp_path):
    """Never-dispatched entry whose issue closes → gh_closed set, status stays
    None, and NO terminal label is written (acceptance #4 for #258)."""
    import json

    repos_path = isolated_autoswe_dir / "config" / "repos.json"
    repos_path.write_text(
        json.dumps({"owner/repo": {"provider": "github", "pat": "fake", "base_branch": "main"}})
    )
    _seed_queue(isolated_autoswe_dir, "gh:owner_repo_1")

    # Poll where the issue is absent from the open-issues listing.
    set_status_calls, clear_status_calls = _run_poll(isolated_autoswe_dir, monkeypatch, tmp_path, open_issues=[])

    entry = _read_queue(isolated_autoswe_dir, "gh:owner_repo_1")
    assert entry["gh_closed"] is True
    assert entry["autoswe_status"] is None, (
        f"never-dispatched entry must stay neutral, got {entry['autoswe_status']!r}"
    )
    assert set_status_calls == [], (
        f"no terminal label may be written on a never-dispatched entry, "
        f"got {set_status_calls}"
    )
    assert clear_status_calls == [], (
        f"closed entries are skipped before the heal block; "
        f"no label clear expected, got {clear_status_calls}"
    )

    # Poll where the issue is back in the open set (reopen): still neutral,
    # still no label — Phase 3 must not re-mirror a fabricated terminal.
    set_status_calls, clear_status_calls = _run_poll(isolated_autoswe_dir, monkeypatch, tmp_path, open_issues=[1])

    entry = _read_queue(isolated_autoswe_dir, "gh:owner_repo_1")
    assert entry["gh_closed"] is False
    assert entry["autoswe_status"] is None
    assert set_status_calls == []
    assert clear_status_calls == [], (
        f"a never-poisoned entry must not trigger a label clear, "
        f"got {clear_status_calls}"
    )


def test_single_poll_gh_closed_dispatched_entry_maps_completed(isolated_autoswe_dir, monkeypatch, tmp_path):
    """Entry with a real dispatch whose issue closes → phase's COMPLETED
    status + label (existing behavior must be preserved). A real handler run
    always writes attempt_count (emit.py), so the entry carries it."""
    import json

    repos_path = isolated_autoswe_dir / "config" / "repos.json"
    repos_path.write_text(
        json.dumps({"owner/repo": {"provider": "github", "pat": "fake", "base_branch": "main"}})
    )
    _seed_queue(
        isolated_autoswe_dir, "gh:owner_repo_1",
        autoswe_status="fixing", last_dispatched_command="/fix", attempt_count=1,
    )

    set_status_calls, clear_status_calls = _run_poll(isolated_autoswe_dir, monkeypatch, tmp_path, open_issues=[])

    entry = _read_queue(isolated_autoswe_dir, "gh:owner_repo_1")
    assert entry["gh_closed"] is True
    assert entry["autoswe_status"] == "fixed"
    assert set_status_calls == [(1, "autoswe:fixed")]
    assert clear_status_calls == [], (
        f"the fabricated-completed path must not clear labels, "
        f"got {clear_status_calls}"
    )


def test_single_poll_gh_closed_refused_only_entry_status_unchanged(isolated_autoswe_dir, monkeypatch, tmp_path):
    """A task whose only recorded command was a REFUSAL (no agent run) →
    closing the issue must NOT fabricate a terminal: the REFUSED emit path
    writes last_dispatched_command (and the watermarks) without any run and
    without attempt_count, so the gate treats the entry as never-dispatched
    and leaves the existing status untouched (issue #258 follow-up)."""
    import json

    repos_path = isolated_autoswe_dir / "config" / "repos.json"
    repos_path.write_text(
        json.dumps({"owner/repo": {"provider": "github", "pat": "fake", "base_branch": "main"}})
    )
    _seed_queue(
        isolated_autoswe_dir, "gh:owner_repo_1",
        autoswe_status="failed", last_dispatched_command="/review",
        attempt_count=0,
    )

    set_status_calls, clear_status_calls = _run_poll(isolated_autoswe_dir, monkeypatch, tmp_path, open_issues=[])

    entry = _read_queue(isolated_autoswe_dir, "gh:owner_repo_1")
    assert entry["gh_closed"] is True
    assert entry["autoswe_status"] == "failed", (
        f"refused-only entry must keep its status (no fabricated terminal), "
        f"got {entry['autoswe_status']!r}"
    )
    assert set_status_calls == [], (
        f"no terminal label may be written on a refused-only entry, "
        f"got {set_status_calls}"
    )
    assert clear_status_calls == [], (
        f"closed entries are skipped before the heal block; "
        f"no label clear expected, got {clear_status_calls}"
    )


def test_single_poll_gh_closed_failed_dispatch_entry_status_unchanged(isolated_autoswe_dir, monkeypatch, tmp_path):
    """Entry with attempt_count > 0 but current status 'failed' (last
    dispatch produced no work) → closing the issue must NOT fabricate a
    terminal: the old code would map /fix → 'fixed' even though no diff
    was produced, which is the same false-terminal class as #258.
    The fix gates fabrication on the entry's current status being
    COMPLETED or RUNNING; 'failed' is neither, so status stays unchanged
    and no terminal label is written."""
    import json

    repos_path = isolated_autoswe_dir / "config" / "repos.json"
    repos_path.write_text(
        json.dumps({"owner/repo": {"provider": "github", "pat": "fake", "base_branch": "main"}})
    )
    _seed_queue(
        isolated_autoswe_dir, "gh:owner_repo_1",
        autoswe_status="failed", last_dispatched_command="/fix",
        attempt_count=1,
    )

    set_status_calls, clear_status_calls = _run_poll(isolated_autoswe_dir, monkeypatch, tmp_path, open_issues=[])

    entry = _read_queue(isolated_autoswe_dir, "gh:owner_repo_1")
    assert entry["gh_closed"] is True
    assert entry["autoswe_status"] == "failed", (
        f"failed-dispatch entry must keep its status (no fabricated terminal), "
        f"got {entry['autoswe_status']!r}"
    )
    assert set_status_calls == [], (
        f"no terminal label may be written when the last dispatch failed, "
        f"got {set_status_calls}"
    )
    assert clear_status_calls == [], (
        f"closed entries are skipped before the heal block; "
        f"no label clear expected, got {clear_status_calls}"
    )


def test_single_poll_heals_never_dispatched_entry_with_completed_status(isolated_autoswe_dir, monkeypatch, tmp_path):
    """Pre-#258 poison: open issue, never dispatched, but queue says 'fixed'
    (the fabricated terminal) → every poll heals it back to None."""
    import json

    repos_path = isolated_autoswe_dir / "config" / "repos.json"
    repos_path.write_text(
        json.dumps({"owner/repo": {"provider": "github", "pat": "fake", "base_branch": "main"}})
    )
    _seed_queue(
        isolated_autoswe_dir, "gh:owner_repo_1",
        autoswe_status="fixed", last_dispatched_command=None,
    )

    # Issue is open: the invariant heal must reset the fabricated terminal
    # AND clear the stale autoswe:* label off the live issue.
    set_status_calls, clear_status_calls = _run_poll(isolated_autoswe_dir, monkeypatch, tmp_path, open_issues=[1])
    entry = _read_queue(isolated_autoswe_dir, "gh:owner_repo_1")
    assert entry["autoswe_status"] is None, (
        f"fabricated terminal must be healed to neutral, got {entry['autoswe_status']!r}"
    )
    assert clear_status_calls == [1], (
        f"heal must clear the stale terminal label on the live issue, "
        f"got {clear_status_calls}"
    )
    assert set_status_calls == [], (
        f"healed entry must not trigger a status write, got {set_status_calls}"
    )

    # Re-opened after a close: gh_closed clears AND a still-poisoned status
    # is healed in the same poll.
    _seed_queue(
        isolated_autoswe_dir, "gh:owner_repo_1",
        autoswe_status="fixed", last_dispatched_command=None, gh_closed=True,
    )
    set_status_calls, clear_status_calls = _run_poll(isolated_autoswe_dir, monkeypatch, tmp_path, open_issues=[1])
    entry = _read_queue(isolated_autoswe_dir, "gh:owner_repo_1")
    assert entry["gh_closed"] is False
    assert entry["autoswe_status"] is None
    assert set_status_calls == []
    assert clear_status_calls == [1], (
        f"reopened poisoned entry must also have its stale label cleared, "
        f"got {clear_status_calls}"
    )


def test_single_poll_heal_skips_entry_with_dispatch_evidence(isolated_autoswe_dir, monkeypatch, tmp_path):
    """A queue entry with positive dispatch evidence (attempt_count > 0 or
    first_dispatched_at set) but no last_dispatched_command — e.g. a
    genuinely-completed "done" entry from an older queue version that
    normalize_legacy_status mapped to "fixed" — must NOT be demoted by the
    heal; only #258-fabricated poison (neither field set) is reset."""
    import json

    repos_path = isolated_autoswe_dir / "config" / "repos.json"
    repos_path.write_text(
        json.dumps({"owner/repo": {"provider": "github", "pat": "fake", "base_branch": "main"}})
    )

    # Case 1: attempt_count > 0 (written only by the dispatch path).
    _seed_queue(
        isolated_autoswe_dir, "gh:owner_repo_1",
        autoswe_status="fixed", last_dispatched_command=None, attempt_count=1,
    )
    set_status_calls, clear_status_calls = _run_poll(isolated_autoswe_dir, monkeypatch, tmp_path, open_issues=[1])
    entry = _read_queue(isolated_autoswe_dir, "gh:owner_repo_1")
    assert entry["autoswe_status"] == "fixed", (
        f"legacy completed entry with dispatch evidence must not be demoted, "
        f"got {entry['autoswe_status']!r}"
    )
    assert set_status_calls == [(1, "autoswe:fixed")], (
        f"only the Phase-3 mirror of autoswe:fixed may be written, "
        f"got {set_status_calls}"
    )
    assert clear_status_calls == [], (
        f"skipped heal must not clear the label, got {clear_status_calls}"
    )

    # Case 2: only first_dispatched_at set (the second disjunct).
    _seed_queue(
        isolated_autoswe_dir, "gh:owner_repo_1",
        autoswe_status="fixed", last_dispatched_command=None,
        first_dispatched_at="2026-01-02T00:00:00Z",
    )
    set_status_calls, clear_status_calls = _run_poll(isolated_autoswe_dir, monkeypatch, tmp_path, open_issues=[1])
    entry = _read_queue(isolated_autoswe_dir, "gh:owner_repo_1")
    assert entry["autoswe_status"] == "fixed", (
        f"entry with first_dispatched_at must not be demoted, "
        f"got {entry['autoswe_status']!r}"
    )
    assert set_status_calls == [(1, "autoswe:fixed")], (
        f"only the Phase-3 mirror of autoswe:fixed may be written, "
        f"got {set_status_calls}"
    )
    assert clear_status_calls == [], (
        f"skipped heal must not clear the label, got {clear_status_calls}"
    )


def test_single_poll_heal_skips_entry_with_bot_completion_comment(isolated_autoswe_dir, monkeypatch, tmp_path):
    """A non-welcome bot comment id in bot_comment_ids is dispatch evidence:
    every real Claude completion posts a bot comment that Phase 1 backfills,
    so a legacy completed entry with such an id must NOT be demoted."""
    import json

    repos_path = isolated_autoswe_dir / "config" / "repos.json"
    repos_path.write_text(
        json.dumps({"owner/repo": {"provider": "github", "pat": "fake", "base_branch": "main"}})
    )
    _seed_queue(
        isolated_autoswe_dir, "gh:owner_repo_1",
        autoswe_status="fixed", last_dispatched_command=None, bot_comment_ids=[999],
    )

    set_status_calls, clear_status_calls = _run_poll(isolated_autoswe_dir, monkeypatch, tmp_path, open_issues=[1])
    entry = _read_queue(isolated_autoswe_dir, "gh:owner_repo_1")
    assert entry["autoswe_status"] == "fixed", (
        f"entry with a bot completion comment must not be demoted, "
        f"got {entry['autoswe_status']!r}"
    )
    assert set_status_calls == [(1, "autoswe:fixed")], (
        f"only the Phase-3 mirror of autoswe:fixed may be written, "
        f"got {set_status_calls}"
    )
    assert clear_status_calls == [], (
        f"skipped heal must not clear the label, got {clear_status_calls}"
    )


def test_single_poll_heal_still_fires_with_welcome_only_bot_comment(isolated_autoswe_dir, monkeypatch, tmp_path):
    """The welcome comment is is_bot=True and gets backfilled into
    bot_comment_ids, so it is excluded from dispatch evidence: a #258-poisoned
    entry whose only bot comment is the welcome must still be healed to None."""
    import json

    repos_path = isolated_autoswe_dir / "config" / "repos.json"
    repos_path.write_text(
        json.dumps({"owner/repo": {"provider": "github", "pat": "fake", "base_branch": "main"}})
    )
    _seed_queue(
        isolated_autoswe_dir, "gh:owner_repo_1",
        autoswe_status="fixed", last_dispatched_command=None,
        bot_comment_ids=[42], welcome_comment_id=42,
    )

    set_status_calls, clear_status_calls = _run_poll(isolated_autoswe_dir, monkeypatch, tmp_path, open_issues=[1])
    entry = _read_queue(isolated_autoswe_dir, "gh:owner_repo_1")
    assert entry["autoswe_status"] is None, (
        f"welcome-only bot comment is not dispatch evidence; "
        f"poison must be healed, got {entry['autoswe_status']!r}"
    )
    assert set_status_calls == [], (
        f"healed entry must not trigger any status write, got {set_status_calls}"
    )
    assert clear_status_calls == [1], (
        f"heal must clear the stale terminal label on the live issue, "
        f"got {clear_status_calls}"
    )


def test_single_poll_heal_skips_legacy_completed_entry_with_pr_number(isolated_autoswe_dir, monkeypatch, tmp_path):
    """A legacy completed entry with no attempt_count, no
    first_dispatched_at, and no bot comments that records a real ship
    (pr_number set — written only by a completed handler run in emit.py)
    must NOT be demoted by the heal."""
    import json

    repos_path = isolated_autoswe_dir / "config" / "repos.json"
    repos_path.write_text(
        json.dumps({"owner/repo": {"provider": "github", "pat": "fake", "base_branch": "main"}})
    )
    _seed_queue(
        isolated_autoswe_dir, "gh:owner_repo_1",
        autoswe_status="fixed", last_dispatched_command=None, pr_number=42,
    )

    set_status_calls, clear_status_calls = _run_poll(isolated_autoswe_dir, monkeypatch, tmp_path, open_issues=[1])
    entry = _read_queue(isolated_autoswe_dir, "gh:owner_repo_1")
    assert entry["autoswe_status"] == "fixed", (
        f"legacy completed entry with pr_number must not be demoted, "
        f"got {entry['autoswe_status']!r}"
    )
    assert set_status_calls == [(1, "autoswe:fixed")], (
        f"only the Phase-3 mirror of autoswe:fixed may be written, "
        f"got {set_status_calls}"
    )
    assert clear_status_calls == [], (
        f"skipped heal must not clear the label, got {clear_status_calls}"
    )

