"""Tests for autoswe.tracking.progress — sticky progress comment."""

import time


def test_progress_create_posts_comment(github_fake):
    """create() should post an initial comment and return a comment ID."""
    github_fake.load({
        "owner": "o", "repo": "r", "issue": {"number": 42, "title": "T",
           "body": "B", "state": "open", "labels": [], "assignees": [],
           "created_at": "2026-01-01", "updated_at": "2026-01-01",
           "closed_at": None, "author_association": "OWNER",
           "comments": 0, "user": {"login": "o", "id": 1, "type": "User"}},
        "labels": [], "comments": [], "repo_labels": [],
    })

    # Patch the fake into the API module
    import autoswe.tracking.api as api_mod
    original = api_mod._gh_request
    api_mod._gh_request = github_fake.handle_request

    from autoswe.providers.github.tracker import GitHubTracker
    from autoswe.tracking.progress import ProgressComment

    try:
        tracker = GitHubTracker({"owner": "o", "repo": "r", "pat": "tok"})
        progress = ProgressComment(tracker, {"owner": "o", "repo": "r", "pat": "tok"}, 42)
        cid = progress.create("Starting fix...")
    finally:
        api_mod._gh_request = original

    from autoswe.tracking.comments import BOT_MARKER

    assert cid is not None
    assert progress.comment_id == cid
    assert len(github_fake.comments.get(42, [])) == 1
    posted = github_fake.comments[42][0]["body"]
    assert posted == "Starting fix...\n" + BOT_MARKER


def test_progress_update_applies_immediately(monkeypatch):
    """First update() after create should apply immediately (no throttle)."""
    updates = []

    class FakeTracker:
        def post_comment(self, repo_cfg, issue_num, body):
            return 999

        def update_comment(self, repo_cfg, issue_num, comment_id, body):
            updates.append({"id": comment_id, "body": body})

    from autoswe.tracking.comments import BOT_MARKER
    from autoswe.tracking.progress import ProgressComment

    tracker = FakeTracker()
    progress = ProgressComment(tracker, {}, 1)
    progress.create("initial")
    progress.update("updated")

    assert len(updates) == 1
    assert updates[0]["body"] == "updated\n" + BOT_MARKER


def test_progress_update_throttles(monkeypatch):
    """Rapid update() calls should coalesce — only the latest is kept."""
    updates = []

    class FakeTracker:
        def post_comment(self, repo_cfg, issue_num, body):
            return 999

        def update_comment(self, repo_cfg, issue_num, comment_id, body):
            updates.append(body)

    from autoswe.tracking.comments import BOT_MARKER
    from autoswe.tracking.progress import ProgressComment

    tracker = FakeTracker()
    progress = ProgressComment(tracker, {}, 1)
    progress.create("init")
    progress.update("first")
    # These should coalesce into "third" (latest)
    progress.update("second")
    progress.update("third")

    # Only "first" was applied immediately; "second" and "third" were coalesced
    assert updates == ["first\n" + BOT_MARKER]
    # Pending body should be "third"
    assert progress._pending_body == "third"


def test_progress_drain_applies_pending(monkeypatch):
    """drain() should apply the pending coalesced update."""
    updates = []

    class FakeTracker:
        def post_comment(self, repo_cfg, issue_num, body):
            return 999

        def update_comment(self, repo_cfg, issue_num, comment_id, body):
            updates.append(body)

    from autoswe.tracking.comments import BOT_MARKER
    from autoswe.tracking.progress import ProgressComment

    tracker = FakeTracker()
    progress = ProgressComment(tracker, {}, 1)
    progress.create("init")
    progress.update("first")
    progress.update("pending")

    assert updates == ["first\n" + BOT_MARKER]
    progress.drain()
    assert updates == ["first\n" + BOT_MARKER, "pending\n" + BOT_MARKER]


def test_progress_finalize_no_throttle(monkeypatch):
    """finalize() should write immediately regardless of throttle."""
    updates = []

    class FakeTracker:
        def post_comment(self, repo_cfg, issue_num, body):
            return 999

        def update_comment(self, repo_cfg, issue_num, comment_id, body):
            updates.append(body)

    from autoswe.tracking.comments import BOT_MARKER
    from autoswe.tracking.progress import ProgressComment

    tracker = FakeTracker()
    progress = ProgressComment(tracker, {}, 1)
    progress.create("init")
    progress.update("intermediate")
    progress.finalize("Done!")

    assert "Done!\n" + BOT_MARKER in updates


def test_progress_update_noop_without_comment_id(monkeypatch):
    """update() should be a no-op when create() was never called."""
    updates = []

    class FakeTracker:
        def update_comment(self, repo_cfg, issue_num, comment_id, body):
            updates.append(body)

    from autoswe.tracking.progress import ProgressComment

    tracker = FakeTracker()
    progress = ProgressComment(tracker, {}, 1)
    progress.update("should not apply")
    progress.finalize("should not apply either")

    assert updates == []


def test_progress_update_throttle_releases_after_interval(monkeypatch):
    """After MIN_UPDATE_INTERVAL_S, update should apply again."""
    from autoswe.tracking.progress import _MIN_UPDATE_INTERVAL_S, ProgressComment

    updates = []

    class FakeTracker:
        def post_comment(self, repo_cfg, issue_num, body):
            return 999

        def update_comment(self, repo_cfg, issue_num, comment_id, body):
            updates.append(body)

    from autoswe.tracking.comments import BOT_MARKER

    tracker = FakeTracker()
    progress = ProgressComment(tracker, {}, 1)
    progress.create("init")
    progress.update("first")

    assert updates == ["first\n" + BOT_MARKER]
    progress.update("second")
    assert updates == ["first\n" + BOT_MARKER]  # "second" coalesced

    # Advance time past throttle interval
    # Simpler: just set the timestamp directly (can't easily monkeypatch time.monotonic)
    progress._last_update = time.monotonic() - _MIN_UPDATE_INTERVAL_S - 1
    progress.update("after_delay")

    assert "after_delay\n" + BOT_MARKER in updates


def test_progress_create_gracefully_on_error(monkeypatch):
    """create() should return None and not raise when tracker fails."""
    class BrokenTracker:
        def post_comment(self, repo_cfg, issue_num, body):
            raise RuntimeError("API down")

        def update_comment(self, repo_cfg, issue_num, comment_id, body):
            pass

    from autoswe.tracking.progress import ProgressComment

    tracker = BrokenTracker()
    progress = ProgressComment(tracker, {}, 1)
    result = progress.create("initial")

    assert result is None
    assert progress.comment_id is None


def test_progress_update_comment_gracefully_on_error(monkeypatch):
    """update() should not raise when tracker fails."""
    class BrokenTracker:
        def post_comment(self, repo_cfg, issue_num, body):
            return 42

        def update_comment(self, repo_cfg, issue_num, comment_id, body):
            raise RuntimeError("API down")

    from autoswe.tracking.progress import ProgressComment

    tracker = BrokenTracker()
    progress = ProgressComment(tracker, {}, 1)
    progress.create("init")
    progress.update("should not raise")

    # No exception raised; update silently failed
    assert progress.comment_id == 42


def test_progress_flush_fallback_updates_comment_id():
    """When update_comment fails and post_comment succeeds, _comment_id updates
    to the new comment ID, preventing a cascade of orphan comments.

    Regression test for issue #38: extra comments appearing during Claude Code
    runs because the fallback post_comment's ID was never captured.
    """
    from autoswe.tracking.progress import ProgressComment

    class FallingBackTracker:
        def __init__(self):
            self.posts = []
            self.updates = []
            self._next_post_id = 100

        def post_comment(self, repo_cfg, issue_num, body):
            cid = self._next_post_id
            self._next_post_id += 1
            self.posts.append({"id": cid, "body": body})
            return cid

        def update_comment(self, repo_cfg, issue_num, comment_id, body):
            self.updates.append({"id": comment_id, "body": body})

    tracker = FallingBackTracker()
    progress = ProgressComment(tracker, {}, 1)

    # create() posts initial comment with ID 100
    progress.create("Starting...")
    assert progress.comment_id == 100
    assert len(tracker.posts) == 1

    # update_comment fails → fallback to post_comment creates ID 101
    original_update = tracker.update_comment

    def failing_update(*args, **kwargs):
        raise RuntimeError("API down")

    tracker.update_comment = failing_update
    progress.update("Step 1")

    # Should have fallen back to a new comment (ID 101)
    assert progress.comment_id == 101
    assert len(tracker.posts) == 2

    # Restore update_comment so subsequent calls succeed on the new comment
    tracker.update_comment = original_update
    progress._last_update = 0  # release throttle
    progress.update("Step 2")

    # Step 2 should target the NEW comment ID (101), not the old one (100)
    assert tracker.updates[-1]["id"] == 101


def test_progress_flush_fallback_no_new_id():
    """When update_comment fails and post_comment returns None, _comment_id
    is unchanged (no crash). Directly exercises _flush() to test the fallback
    path — not the update() early-exit path."""
    from autoswe.tracking.progress import ProgressComment

    class BrokenPostTracker:
        def post_comment(self, repo_cfg, issue_num, body):
            return None  # post succeeds but returns no ID

        def update_comment(self, repo_cfg, issue_num, comment_id, body):
            raise RuntimeError("API down")  # trigger fallback

    tracker = BrokenPostTracker()
    progress = ProgressComment(tracker, {}, 1)
    progress._comment_id = 42  # simulate an existing comment

    progress._flush("Step 1", force=True)  # directly exercise _flush

    assert progress.comment_id == 42  # unchanged, not None


def test_progress_flush_fallback_both_fail():
    """When both update_comment and post_comment fail, no crash and _comment_id
    is preserved."""
    from autoswe.tracking.progress import ProgressComment

    class TotallyBrokenTracker:
        def __init__(self):
            self.posts = []
            self.updates = []

        def post_comment(self, repo_cfg, issue_num, body):
            self.posts.append(body)
            raise RuntimeError("API down")

        def update_comment(self, repo_cfg, issue_num, comment_id, body):
            self.updates.append(body)

    tracker = TotallyBrokenTracker()
    progress = ProgressComment(tracker, {}, 1)

    # Simulate an existing comment ID (bypass broken create)
    progress._comment_id = 999

    # Make update_comment fail, then fallback post_comment also fails
    tracker.update_comment = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("API down"))
    progress.update("Step 1")

    # Should not crash; comment_id preserved at 999
    assert progress.comment_id == 999
    assert len(tracker.posts) == 1  # post_comment was attempted


# ---------------------------------------------------------------------------
# Provider update_comment tests
# ---------------------------------------------------------------------------

def test_github_tracker_update_comment():
    """GitHubTracker.update_comment should PATCH the comment via API."""
    from autoswe.providers.github.tracker import GitHubTracker

    tracker = GitHubTracker({"owner": "o", "repo": "r", "pat": "tok"})

    patched = []

    def fake_patch(path, token, body, **kwargs):
        patched.append({"path": path, "body": body})
        return {}

    import autoswe.tracking.api as api_mod
    original_patch = api_mod.gh_patch
    api_mod.gh_patch = fake_patch

    try:
        tracker.update_comment({"owner": "o", "repo": "r"}, 42, 123, "Updated body")
    finally:
        api_mod.gh_patch = original_patch

    assert len(patched) == 1
    assert "/issues/comments/123" in patched[0]["path"]
    assert patched[0]["body"]["body"] == "Updated body"


def test_azure_tracker_update_comment_patches():
    """AzureTracker.update_comment issues PATCH via ado_patch_json (not NotImplementedError)."""
    patch_calls = []

    def fake_ado_patch_json(path, pat, body):
        patch_calls.append({"path": path, "body": body})

    import autoswe.providers.azure.tracker as tracker_mod
    original = tracker_mod.ado_patch_json
    tracker_mod.ado_patch_json = fake_ado_patch_json

    try:
        from autoswe.providers.azure.tracker import AzureTracker

        tracker = AzureTracker({
            "org": "org", "project": "proj", "pat": "tok",
        })
        tracker.update_comment({}, 42, 999, "Updated body")
    finally:
        tracker_mod.ado_patch_json = original

    assert len(patch_calls) == 1
    assert "workitems/42/comments/999" in patch_calls[0]["path"]
    assert "format=Markdown" in patch_calls[0]["path"]
    assert patch_calls[0]["body"] == {"text": "Updated body"}


def test_progress_azure_no_duplicate_post_on_update():
    """Azure tracker update_comment succeeds — no fallback post_comment duplicates.

    Regression test: when update_comment raised NotImplementedError, ProgressComment
    fell back to post_comment, producing a new comment per progress update.
    """
    posted = []
    updated = []

    class AzureLikeTracker:
        def post_comment(self, repo_cfg, issue_num, body):
            posted.append(body)
            return len(posted)

        def update_comment(self, repo_cfg, issue_num, comment_id, body):
            updated.append(body)

    from autoswe.tracking.comments import BOT_MARKER
    from autoswe.tracking.progress import ProgressComment

    tracker = AzureLikeTracker()
    progress = ProgressComment(tracker, {}, 1)
    progress.create("Starting...")
    posts_after_create = len(posted)
    progress.update("Step 1")
    progress.update("Step 2")
    progress._last_update = 0  # force throttle release
    progress.update("Step 3")
    progress.finalize("Done.")

    assert len(posted) == posts_after_create, "no new posts after create"
    assert len(updated) >= 1
    assert updated[-1] == "Done.\n" + BOT_MARKER


def test_fake_github_patch_comment(github_fake):
    """GitHubFake should support PATCH /repos/{o}/{r}/issues/comments/{id}."""
    github_fake.load({
        "owner": "o", "repo": "r", "issue": {"number": 42, "title": "T",
           "body": "B", "state": "open", "labels": [], "assignees": [],
           "created_at": "2026-01-01", "updated_at": "2026-01-01",
           "closed_at": None, "author_association": "OWNER",
           "comments": 0, "user": {"login": "o", "id": 1, "type": "User"}},
        "labels": [], "comments": [], "repo_labels": [],
    })

    # Post a comment first
    comment = github_fake.handle_request(
        "POST", "/repos/o/r/issues/42/comments", "tok",
        body={"body": "original"},
    )
    cid = comment["id"]

    # Now PATCH it
    result = github_fake.handle_request(
        "PATCH", f"/repos/o/r/issues/comments/{cid}", "tok",
        body={"body": "patched"},
    )

    assert result["id"] == cid
    assert result["body"] == "patched"

    # Verify state was mutated
    stored = github_fake.comments[42][0]
    assert stored["body"] == "patched"


def test_github_tracker_post_comment_returns_id():
    """GitHubTracker.post_comment should return the comment ID."""
    from autoswe.providers.github.tracker import GitHubTracker

    tracker = GitHubTracker({"owner": "o", "repo": "r", "pat": "tok"})

    posted = []

    def fake_post(path, token, body, **kwargs):
        posted.append({"path": path, "body": body})
        return {"id": 42, "body": body.get("body", "")}

    import autoswe.tracking.api as api_mod
    original_post = api_mod.gh_post
    api_mod.gh_post = fake_post

    try:
        result = tracker.post_comment({"owner": "o", "repo": "r"}, 1, "Hello")
    finally:
        api_mod.gh_post = original_post

    assert result == 42
    assert posted[0]["body"]["body"] == "Hello"


# ---------------------------------------------------------------------------
# No duplicate comments on finalize (regression for double-post bug)
# ---------------------------------------------------------------------------

def test_progress_finalize_does_not_post_duplicate():
    """finalize() should only update the sticky comment, not post a new one.

    Regression test: dispatch.py used to call both progress.finalize(msg) and
    tracker.post_comment(...) — producing two identical bot comments per run.
    """
    posted_bodies = []
    updated_bodies = []

    class NoDuplicateTracker:
        def post_comment(self, repo_cfg, issue_num, body):
            posted_bodies.append(body)
            return 999  # comment ID

        def update_comment(self, repo_cfg, issue_num, comment_id, body):
            updated_bodies.append(body)

    from autoswe.tracking.comments import BOT_MARKER
    from autoswe.tracking.progress import ProgressComment

    tracker = NoDuplicateTracker()
    progress = ProgressComment(tracker, {}, 1)
    progress.create("Starting...")
    posts_after_create = len(posted_bodies)  # 1 from create()
    progress.update("Working...")
    progress.finalize("Completed with command `/fix`.")

    # finalize() should only update the sticky comment
    assert len(updated_bodies) >= 1
    assert updated_bodies[-1] == "Completed with command `/fix`.\n" + BOT_MARKER
    # No additional posts after create (update/finalize must not post)
    assert len(posted_bodies) == posts_after_create


# ---------------------------------------------------------------------------
# MCP comment server
# ---------------------------------------------------------------------------

def test_mcp_comment_server_imports():
    """MCP comment server module should be importable."""
    from mcp_servers import autoswe_comment_server

    assert hasattr(autoswe_comment_server, "server")
    assert autoswe_comment_server.server.name == "autoswe-comment"


def test_mcp_comment_server_has_tools():
    """MCP comment server should have registered tool handlers."""
    from mcp_servers import autoswe_comment_server

    # Verify the server module defines the expected tool functions
    assert hasattr(autoswe_comment_server, "update_progress")
    assert hasattr(autoswe_comment_server, "post_plan")
    assert hasattr(autoswe_comment_server, "post_question")


# ---------------------------------------------------------------------------
# Minimal posting mode
# ---------------------------------------------------------------------------

class _FakeTracker:
    def __init__(self):
        self.posts = []
        self.updates = []

    def post_comment(self, repo_cfg, issue_num, body):
        self.posts.append(body)
        return len(self.posts)  # incrementing fake comment ID

    def update_comment(self, repo_cfg, issue_num, comment_id, body):
        self.updates.append(body)


def test_progress_minimal_update_queues_only():
    """In minimal mode update() never calls update_comment — queues only."""
    from autoswe.tracking.progress import ProgressComment

    tracker = _FakeTracker()
    progress = ProgressComment(tracker, {}, 1, minimal=True)
    progress.create("initial")
    progress.update("step one")
    progress.update("step two")

    assert tracker.updates == [], "update_comment must not be called in minimal mode"
    assert progress._pending_body == "step two"


def test_progress_minimal_drain_flushes():
    """In minimal mode drain() flushes the last queued body via update_comment."""
    from autoswe.tracking.comments import BOT_MARKER
    from autoswe.tracking.progress import ProgressComment

    tracker = _FakeTracker()
    progress = ProgressComment(tracker, {}, 1, minimal=True)
    progress.create("initial")
    progress.update("step one")
    progress.update("final body")
    progress.drain()

    assert tracker.updates == ["final body\n" + BOT_MARKER]
    assert progress._pending_body is None


def test_progress_minimal_finalize_flushes():
    """In minimal mode finalize() still force-flushes immediately."""
    from autoswe.tracking.comments import BOT_MARKER
    from autoswe.tracking.progress import ProgressComment

    tracker = _FakeTracker()
    progress = ProgressComment(tracker, {}, 1, minimal=True)
    progress.create("initial")
    progress.update("intermediate")
    progress.finalize("Done!")

    assert tracker.updates == ["Done!\n" + BOT_MARKER]


def test_progress_minimal_two_api_calls_total():
    """Minimal mode: only one post (create) and one update (drain/finalize) total."""
    from autoswe.tracking.comments import BOT_MARKER
    from autoswe.tracking.progress import ProgressComment

    tracker = _FakeTracker()
    progress = ProgressComment(tracker, {}, 1, minimal=True)
    progress.create("Dispatching `/fix`…")
    for i in range(20):
        progress.update(f"Working… step {i}")
    progress.drain()

    assert len(tracker.posts) == 1, "exactly one POST (create)"
    assert tracker.posts[0] == "Dispatching `/fix`…\n" + BOT_MARKER
    assert len(tracker.updates) == 1, "exactly one PATCH (drain)"
    assert tracker.updates[0] == "Working… step 19\n" + BOT_MARKER


# ---------------------------------------------------------------------------
# BOT_MARKER tagging (infinite-loop bug fix)


def test_progress_create_tags_with_bot_marker():
    """create() should append BOT_MARKER so _is_autoswe_bot_comment detects it."""
    from autoswe.tracking.comments import BOT_MARKER

    class TagTracker:
        def post_comment(self, repo_cfg, issue_num, body):
            return self.posts.append(body) or 1

        def update_comment(self, repo_cfg, issue_num, comment_id, body):
            pass

        posts = []

    tracker = TagTracker()
    from autoswe.tracking.progress import ProgressComment

    progress = ProgressComment(tracker, {}, 1)
    progress.create("Dispatching `/plan`…")

    assert len(tracker.posts) == 1
    assert BOT_MARKER in tracker.posts[0]


def test_progress_update_tags_with_bot_marker():
    """update() should append BOT_MARKER to edited bodies."""
    from autoswe.tracking.comments import BOT_MARKER

    class TagTracker:
        def post_comment(self, repo_cfg, issue_num, body):
            return 1

        def update_comment(self, repo_cfg, issue_num, comment_id, body):
            self.updates.append(body)

        updates = []

    tracker = TagTracker()
    from autoswe.tracking.progress import ProgressComment

    progress = ProgressComment(tracker, {}, 1)
    progress.create("initial")
    progress.update("Running: pytest")

    assert len(tracker.updates) == 1
    assert BOT_MARKER in tracker.updates[0]


def test_progress_bot_marker_idempotent():
    """When body already contains BOT_MARKER, don't duplicate it."""
    from autoswe.tracking.comments import BOT_MARKER

    class TagTracker:
        def post_comment(self, repo_cfg, issue_num, body):
            self.posts.append(body)
            return 1

        def update_comment(self, repo_cfg, issue_num, comment_id, body):
            pass

        posts = []

    tracker = TagTracker()
    from autoswe.tracking.progress import ProgressComment

    progress = ProgressComment(tracker, {}, 1)
    progress.create("Body\n" + BOT_MARKER)

    assert len(tracker.posts) == 1
    assert tracker.posts[0].count(BOT_MARKER) == 1
    assert tracker.posts[0] == "Body\n" + BOT_MARKER


# ---------------------------------------------------------------------------
# ProgressState (todo list + last command rendering)


def _make_tool_use(name, input_, bid="tool_1"):
    """Build a minimal ToolUseBlock for testing."""
    from claude_agent_sdk import ToolUseBlock

    return ToolUseBlock(id=bid, name=name, input=input_)


def _make_tool_result(tool_use_id, content):
    """Build a minimal ToolResultBlock for testing."""
    from claude_agent_sdk import ToolResultBlock

    return ToolResultBlock(tool_use_id=tool_use_id, content=content)


def test_progress_state_todo_write_render():
    """TodoWrite snapshot should render markdown with correct status icons."""
    from autoswe.harness.runner import ProgressState

    ps = ProgressState()
    block = _make_tool_use("TodoWrite", {
        "todos": [
            {"content": "Read existing code", "status": "completed"},
            {"content": "Write tests", "status": "in_progress"},
            {"content": "Add tests", "status": "pending"},
        ],
    })
    ps.note_tool_use(block)
    body = ps.render()

    assert "### " in body
    assert "Todo List" in body
    assert "✅ Read existing code" in body
    assert "☐ Add tests" in body


def test_progress_state_in_progress_shows_active_form():
    """For in_progress items, render activeForm over content when present."""
    from autoswe.harness.runner import ProgressState

    ps = ProgressState()
    block = _make_tool_use("TodoWrite", {
        "todos": [
            {"content": "Run tests", "activeForm": "Running tests", "status": "in_progress"},
        ],
    })
    ps.note_tool_use(block)
    body = ps.render()

    assert "Running tests" in body
    # content should NOT appear when activeForm is present for in_progress
    for line in body.split("\n"):
        if "Run tests" in line and line.strip().startswith("-"):
            assert "Running tests" in line


def test_progress_state_no_todos_returns_last_command():
    """With no todos, render() returns the bare last-command string."""
    from autoswe.harness.runner import ProgressState

    ps = ProgressState()
    block = _make_tool_use("Bash", {"command": "pytest -q"})
    ps.note_tool_use(block)
    body = ps.render()

    assert body == "Running: pytest -q"
    assert "Todo List" not in body


def test_progress_state_last_command_under_todos():
    """When todos exist, last-command line appears below the todo block."""
    from autoswe.harness.runner import ProgressState

    ps = ProgressState()
    ps.note_tool_use(_make_tool_use("TodoWrite", {
        "todos": [
            {"content": "Step 1", "status": "completed"},
        ],
    }))
    ps.note_tool_use(_make_tool_use("Bash", {"command": "pytest -q"}, bid="tool_2"))
    body = ps.render()

    assert "### " in body
    assert "**Last command:**" in body
    assert "Running: pytest -q" in body


def test_progress_state_last_command_omitted_without_non_todo_tool():
    """Last command line is omitted until a non-todo tool runs."""
    from autoswe.harness.runner import ProgressState

    ps = ProgressState()
    ps.note_tool_use(_make_tool_use("TodoWrite", {
        "todos": [
            {"content": "Step 1", "status": "pending"},
        ],
    }))
    body = ps.render()

    assert "### " in body
    assert "Last command" not in body


def test_progress_state_nothing_to_show_returns_none():
    """When no todos and no last command, render() returns None."""
    from autoswe.harness.runner import ProgressState

    ps = ProgressState()
    assert ps.render() is None


def test_progress_state_note_tool_use_change_detection():
    """note_tool_use returns True only when rendered output actually changes."""
    from autoswe.harness.runner import ProgressState

    ps = ProgressState()
    # First call should change (None -> something)
    changed = ps.note_tool_use(_make_tool_use("Bash", {"command": "echo 1"}))
    assert changed is True
    # Same tool again — last_command already "Running: echo 1", no change
    changed = ps.note_tool_use(_make_tool_use("Bash", {"command": "echo 1"}, bid="tool_2"))
    assert changed is False
    # Different command should change
    changed = ps.note_tool_use(_make_tool_use("Bash", {"command": "echo 2"}, bid="tool_3"))
    assert changed is True


def test_progress_state_task_create_to_update_flow():
    """TaskCreate stashed, ToolResultBlock resolves id, TaskUpdate patches status."""
    from autoswe.harness.runner import ProgressState

    ps = ProgressState()

    # TaskCreate → stashed in _pending_creates, no render change yet
    create_block = _make_tool_use("TaskCreate", {"subject": "Fix bug"}, bid="create_1")
    changed = ps.note_tool_use(create_block)
    assert changed is False  # Task not registered yet, render stays None

    # ToolResultBlock resolves the task id
    result = _make_tool_result("create_1", "task-1")
    changed = ps.note_tool_result(result)
    assert changed is True  # Task now registered

    # TaskUpdate marks it in_progress
    update_block = _make_tool_use("TaskUpdate", {"taskId": "task-1", "status": "in_progress"})
    changed = ps.note_tool_use(update_block)
    assert changed is True
    body = ps.render()
    assert "Fix bug" in body

    # TaskUpdate marks it completed
    update_block = _make_tool_use("TaskUpdate", {"taskId": "task-1", "status": "completed"})
    ps.note_tool_use(update_block)
    body = ps.render()
    assert "✅" in body


def test_progress_state_task_delete_removal():
    """TaskUpdate with status=deleted removes the task."""
    from autoswe.harness.runner import ProgressState

    ps = ProgressState()

    create_block = _make_tool_use("TaskCreate", {"subject": "Temp task"}, bid="create_2")
    ps.note_tool_use(create_block)
    result = _make_tool_result("create_2", "task-2")
    ps.note_tool_result(result)

    body = ps.render()
    assert "Temp task" in body

    # Delete it
    delete_block = _make_tool_use("TaskUpdate", {"taskId": "task-2", "status": "deleted"})
    changed = ps.note_tool_use(delete_block)
    assert changed is True
    body = ps.render()
    assert body is None  # No tasks left, no last command


def test_progress_state_todo_write_replaces_tasks():
    """When TodoWrite is called, it replaces any Task-tool state for rendering."""
    from autoswe.harness.runner import ProgressState

    ps = ProgressState()

    # Set up Task-tool state
    create_block = _make_tool_use("TaskCreate", {"subject": "Task item"}, bid="create_3")
    ps.note_tool_use(create_block)
    result = _make_tool_result("create_3", "task-3")
    ps.note_tool_result(result)

    # TodoWrite snapshot should take over
    todo_block = _make_tool_use("TodoWrite", {
        "todos": [
            {"content": "Todo item", "status": "pending"},
        ],
    })
    ps.note_tool_use(todo_block)
    body = ps.render()

    assert "Todo item" in body
    assert "Task item" not in body


def test_progress_state_empty_todo_write_clears():
    """An empty TodoWrite list clears todo state and falls back to last command."""
    from autoswe.harness.runner import ProgressState

    ps = ProgressState()

    # Set up todos + last command
    ps.note_tool_use(_make_tool_use("TodoWrite", {
        "todos": [{"content": "Step 1", "status": "pending"}],
    }))
    ps.note_tool_use(_make_tool_use("Bash", {"command": "echo hi"}, bid="tool_b"))
    body = ps.render()
    assert "Todo List" in body

    # Empty TodoWrite should clear todos
    ps.note_tool_use(_make_tool_use("TodoWrite", {"todos": []}, bid="tool_c"))
    body = ps.render()
    assert body == "Running: echo hi"
    assert "Todo List" not in body


def test_progress_state_empty_todo_write_preserves_tasks():
    """An empty TodoWrite clears todos but preserves Task-tool state."""
    from autoswe.harness.runner import ProgressState

    ps = ProgressState()

    # Set up Task-tool state first
    create_block = _make_tool_use("TaskCreate", {"subject": "Task item"}, bid="create_empty")
    ps.note_tool_use(create_block)
    result = _make_tool_result("create_empty", "task-empty")
    ps.note_tool_result(result)

    # Empty TodoWrite should NOT clear Task-tool state (no real snapshot to replace with)
    ps.note_tool_use(_make_tool_use("TodoWrite", {"todos": []}, bid="tool_empty_clear"))

    # Should fall back to Task-tool state
    body = ps.render()
    assert "Task item" in body


def test_progress_state_task_id_json_parsing():
    """ToolResultBlock with JSON content should parse task id from task_id or id key."""
    from claude_agent_sdk import ToolResultBlock

    from autoswe.harness.runner import _parse_task_id

    # JSON string with task_id key
    block = ToolResultBlock(tool_use_id="x", content='{"task_id": "json-task-1"}')
    assert _parse_task_id(block) == "json-task-1"

    # JSON string with id key
    block = ToolResultBlock(tool_use_id="x", content='{"id": "json-task-2"}')
    assert _parse_task_id(block) == "json-task-2"

    # Plain string still works
    block = ToolResultBlock(tool_use_id="x", content="plain-id")
    assert _parse_task_id(block) == "plain-id"

    # Empty JSON string returns None
    block = ToolResultBlock(tool_use_id="x", content='""')
    assert _parse_task_id(block) is None


def test_progress_state_task_update_unknown_id_skipped():
    """TaskUpdate for an unknown taskId is skipped, no ghost task created."""
    from autoswe.harness.runner import ProgressState

    ps = ProgressState()

    # Update without prior TaskCreate + ToolResultBlock
    update_block = _make_tool_use("TaskUpdate", {"taskId": "unknown-1", "status": "in_progress"})
    changed = ps.note_tool_use(update_block)
    assert changed is False
    body = ps.render()
    assert body is None


def test_progress_state_server_tool_use_updates_last_command():
    """ServerToolUseBlock should also update last_command."""
    from claude_agent_sdk import ServerToolUseBlock

    from autoswe.harness.runner import ProgressState

    ps = ProgressState()
    block = ServerToolUseBlock(
        name="web_search",
        input={"query": "test"},
        id="server_1",
    )
    changed = ps.note_tool_use(block)
    assert changed is True
    body = ps.render()
    assert body is not None
    assert "Todo List" not in body
