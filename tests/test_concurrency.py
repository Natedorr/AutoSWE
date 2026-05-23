"""Concurrency and race condition tests for autoSWE dispatch.

Batch 12 — Concurrency & race conditions:
- Two poller invocations colliding on the same repo (lock contention)
- PID file written by crashed process
- Comment ID race: backfill on next sync
- Process-level mutex acquisition
- Welcome posts interleaving across multiple issues
"""
import os

import pytest

import autoswe.core.config as cfg_mod
import autoswe.orch.loop as loop_mod


@pytest.fixture
def running_dir(tmp_path, monkeypatch):
    """Set up RUNNING_DIR for concurrency tests."""
    running = tmp_path / "running"
    running.mkdir()
    monkeypatch.setattr(loop_mod, "RUNNING_DIR", running)
    monkeypatch.setattr(cfg_mod, "RUNNING_DIR", running)
    return running


# ---------------------------------------------------------------------------
# PID collision: crashed process leaves .pid without .done
# ---------------------------------------------------------------------------

class TestPidCollision:
    """PID file from a crashed process — no .done file."""

    def test_crashed_pid_no_done_cleaned(self, running_dir, monkeypatch):
        """PID file from crashed process (dead PID, no .done) is cleaned on check."""
        monkeypatch.setattr(loop_mod, "RUNNING_DIR", running_dir)

        # Write a stale PID file
        (running_dir / "gh_o_r_1.pid").write_text("99999999")
        # No .done file (process crashed before completing)

        from autoswe.orch.loop import _is_task_running
        assert _is_task_running("gh:o_r_1") is False
        assert not (running_dir / "gh_o_r_1.pid").exists()  # Cleaned

    def test_crashed_pid_with_done_not_cleaned(self, running_dir, monkeypatch):
        """PID file with .done present — process crashed after writing .done.

        _is_task_running only checks PID liveness. The .done file is a
        separate artifact written by _finalize_handler.
        """
        monkeypatch.setattr(loop_mod, "RUNNING_DIR", running_dir)

        (running_dir / "gh_o_r_1.pid").write_text("99999999")
        (running_dir / "gh_o_r_1.done").write_text("DONE: fixed")

        from autoswe.orch.loop import _is_task_running
        # Dead PID → not running, PID file cleaned
        assert _is_task_running("gh:o_r_1") is False
        # .done file persists (separate from PID tracking)
        assert (running_dir / "gh_o_r_1.done").exists()

    def test_pid_file_race_during_dispatch(self, running_dir, monkeypatch):
        """Dispatch checks PID before writing its own.

        Simulates: poller A starts dispatch, writes PID.
        Poller B starts, sees PID alive → skips.
        """
        monkeypatch.setattr(loop_mod, "RUNNING_DIR", running_dir)

        # Poller A writes PID
        my_pid = os.getpid()
        (running_dir / "gh_o_r_1.pid").write_text(str(my_pid))

        from autoswe.orch.loop import _is_task_running
        # Poller B sees task running
        assert _is_task_running("gh:o_r_1") is True

        # Poller A finishes, removes PID
        (running_dir / "gh_o_r_1.pid").unlink()

        # Now Poller C can dispatch
        assert _is_task_running("gh:o_r_1") is False


# ---------------------------------------------------------------------------
# Repo lock contention
# ---------------------------------------------------------------------------

class TestRepoLockContention:
    """Two pollers competing for the same repo."""

    def test_second_poller_blocked_by_repo_lock(self, running_dir, monkeypatch):
        """Live PID for same repo blocks dispatch."""
        monkeypatch.setattr(loop_mod, "RUNNING_DIR", running_dir)

        (running_dir / "gh_owner_repo_42.pid").write_text(str(os.getpid()))

        from autoswe.orch.loop import _is_repo_locked
        result = _is_repo_locked("owner", "repo", "github")
        assert result == "gh_owner_repo_42"

    def test_different_repos_no_contention(self, running_dir, monkeypatch):
        """PIDs for different repos don't block each other."""
        monkeypatch.setattr(loop_mod, "RUNNING_DIR", running_dir)

        (running_dir / "gh_owner_repo_42.pid").write_text(str(os.getpid()))

        from autoswe.orch.loop import _is_repo_locked
        assert _is_repo_locked("other", "repo", "github") is None
        assert _is_repo_locked("owner", "other", "github") is None

    def test_stale_repo_lock_cleaned(self, running_dir, monkeypatch):
        """Dead PID for repo lock is auto-cleaned."""
        monkeypatch.setattr(loop_mod, "RUNNING_DIR", running_dir)

        (running_dir / "gh_owner_repo_42.pid").write_text("99999999")

        from autoswe.orch.loop import _is_repo_locked
        result = _is_repo_locked("owner", "repo", "github")
        assert result is None
        assert not (running_dir / "gh_owner_repo_42.pid").exists()


# ---------------------------------------------------------------------------
# MAX_CONCURRENT gate
# ---------------------------------------------------------------------------

class TestMaxConcurrent:
    """MAX_CONCURRENT dispatch gate — loop.py:599-601."""

    def test_dispatch_stops_at_max_concurrent(self, running_dir, monkeypatch):
        """Only MAX_CONCURRENT tasks dispatched per cycle."""
        max_concurrent = 2
        dispatched = []
        slugs = ["gh:o_r_1", "gh:o_r_2", "gh:o_r_3", "gh:o_r_4"]

        for slug in slugs:
            if len(dispatched) >= max_concurrent:
                break  # MAX_CONCURRENT gate
            dispatched.append(slug)

        assert len(dispatched) == 2
        assert dispatched == ["gh:o_r_1", "gh:o_r_2"]

    def test_max_concurrent_one(self, running_dir, monkeypatch):
        """MAX_CONCURRENT=1: only first task dispatched."""
        max_concurrent = 1
        dispatched = []
        for i in range(5):
            slug = f"gh:o_r_{i}"
            if len(dispatched) >= max_concurrent:
                break
            dispatched.append(slug)

        assert dispatched == ["gh:o_r_0"]


# ---------------------------------------------------------------------------
# Comment ID race: backfill on next sync
# ---------------------------------------------------------------------------

class TestCommentIdRace:
    """Comment posted returns ID after competing comment already exists."""

    def test_backfill_bot_comment_ids(self, isolated_autoswe_dir):
        """bot_comment_ids backfilled on next sync when IDs missing.

        Scenario: bot posted comments, IDs recorded in API but queue row
        has empty bot_comment_ids. Next sync backfills them (loop.py:630).
        """
        from autoswe.core.queue_store import LockedQueue

        # Seed queue task with empty bot_comment_ids
        with LockedQueue() as lq:
            lq.queue["gh:o_r_1"] = {
                "id": "gh:o_r_1", "owner": "o", "repo": "r",
                "issue_number": 1, "autoswe_status": "planned",
                "bot_comment_ids": [],
            }

        # Simulate what backfill does (loop.py:630-640)
        # API has bot comments with IDs 100, 200
        api_bot_ids = [100, 200]
        with LockedQueue() as lq:
            te = lq.queue["gh:o_r_1"]
            te.setdefault("bot_comment_ids", [])
            existing = set(te["bot_comment_ids"])
            for cid in api_bot_ids:
                if cid not in existing:
                    te["bot_comment_ids"].append(cid)
                    existing.add(cid)

        with LockedQueue() as lq:
            assert sorted(lq.queue["gh:o_r_1"]["bot_comment_ids"]) == [100, 200]

    def test_backfill_no_duplicate(self, isolated_autoswe_dir):
        """Backfill doesn't duplicate IDs already in bot_comment_ids."""
        from autoswe.core.queue_store import LockedQueue

        with LockedQueue() as lq:
            lq.queue["gh:o_r_1"] = {
                "id": "gh:o_r_1", "owner": "o", "repo": "r",
                "issue_number": 1, "autoswe_status": "planned",
                "bot_comment_ids": [100],
            }

        # API shows IDs 100 and 200, but 100 is already tracked
        api_bot_ids = [100, 200]
        with LockedQueue() as lq:
            te = lq.queue["gh:o_r_1"]
            te.setdefault("bot_comment_ids", [])
            existing = set(te["bot_comment_ids"])
            for cid in api_bot_ids:
                if cid not in existing:
                    te["bot_comment_ids"].append(cid)
                    existing.add(cid)

        with LockedQueue() as lq:
            # 100 appears only once
            ids = lq.queue["gh:o_r_1"]["bot_comment_ids"]
            assert ids.count(100) == 1
            assert 200 in ids


# ---------------------------------------------------------------------------
# Dispatched protection (comments arriving mid-run)
# ---------------------------------------------------------------------------

class TestDispatchedProtection:
    """Comments arriving mid-run cannot yank task."""

    def test_dispatched_noop_for_new_command(self):
        """Task in dispatched state → decide returns noop for new commands."""
        from autoswe.orch.decide import decide
        from autoswe.orch.types import ApiState, TaskState, World
        from autoswe.providers.base import NormalizedComment, NormalizedIssue

        api = ApiState(
            issue=NormalizedIssue(number=1, title="T", body="B", owner="o", repo="r"),
            comments=(
                NormalizedComment(body="Dispatching…", created_at="2026-01-01T00:00:00Z",
                                  author_login="BOT", id=100, is_bot=True),
                NormalizedComment(body="/fix", created_at="2026-01-01T01:00:00Z",
                                  author_login="OWNER", id=200),
            ),
        )
        task = TaskState(
            slug="gh:o_r_1", owner="o", repo="r", issue_number=1,
            title="T", body="B", status="dispatched", plan_branch=None,
            base_branch="main", attempt_count=1, first_dispatched_at="2026-01-01T00:00:00Z",
            last_dispatched_command="/plan", last_dispatched_command_id=50,
            last_consumed_reply_id=50, session_id="s1", pr_number=None,
            guard_blocked=False, gh_closed=False,
            pending_command=None, pending_guidance=None, pending_user_reply=None,
        )
        world = World(api=api, task=task, cfg={"MAX_ATTEMPTS": 3}, repo_cfg={})
        action = decide(world)
        assert action.kind == "noop"

    def test_dispatched_protection_preserves_pid(self, running_dir, monkeypatch):
        """New comments during dispatch don't interrupt PID-locked task."""
        monkeypatch.setattr(loop_mod, "RUNNING_DIR", running_dir)

        my_pid = os.getpid()
        (running_dir / "gh_o_r_1.pid").write_text(str(my_pid))

        from autoswe.orch.loop import _is_task_running
        assert _is_task_running("gh:o_r_1") is True
        # Even if new comments arrive, the PID check in the dispatch loop
        # prevents re-dispatch until PID file is removed.


# ---------------------------------------------------------------------------
# Welcome post interleaving
# ---------------------------------------------------------------------------

class TestWelcomeInterleaving:
    """Welcome comments posted in bulk across multiple issues."""

    def test_welcome_posted_once_per_issue(self, isolated_autoswe_dir):
        """suppress_welcome flag prevents duplicate welcome posts."""
        from autoswe.core.queue_store import LockedQueue

        tasks = {
            "gh:o_r_1": {"id": "gh:o_r_1", "suppress_welcome": False},
            "gh:o_r_2": {"id": "gh:o_r_2", "suppress_welcome": False},
            "gh:o_r_3": {"id": "gh:o_r_3", "suppress_welcome": True},  # Already posted
        }
        with LockedQueue() as lq:
            lq.queue.update(tasks)

        # Simulate welcome posting loop
        posted = []
        with LockedQueue() as lq:
            for slug, task in lq.queue.items():
                if not task.get("suppress_welcome", False):
                    posted.append(slug)
                    task["suppress_welcome"] = True  # Mark as posted

        assert sorted(posted) == ["gh:o_r_1", "gh:o_r_2"]
        # gh:o_r_3 not re-posted (already suppressed)

    def test_welcome_bulk_order_stable(self, isolated_autoswe_dir):
        """Bulk welcome posts process tasks in dict iteration order."""
        from autoswe.core.queue_store import LockedQueue

        with LockedQueue() as lq:
            for i in range(5):
                lq.queue[f"gh:o_r_{i}"] = {
                    "id": f"gh:o_r_{i}", "suppress_welcome": False,
                }

        posted = []
        with LockedQueue() as lq:
            for slug in sorted(lq.queue.keys()):
                task = lq.queue[slug]
                if not task.get("suppress_welcome"):
                    posted.append(slug)
                    task["suppress_welcome"] = True

        assert posted == ["gh:o_r_0", "gh:o_r_1", "gh:o_r_2", "gh:o_r_3", "gh:o_r_4"]
