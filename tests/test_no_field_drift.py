"""Drift guard — every TaskState field is backed by the TASK_FIELDS registry.

Prevents the circular-PR bug: adding a field to TaskState without updating
the queue key mapping, handler dict, or docs.

Runs as part of the default test suite (no special marker).
"""
from __future__ import annotations

import inspect
from typing import Any

from autoswe.orch.types import TASK_FIELDS, TaskState

# -----------------------------------------------------------------
# Helper: inspect the TaskState dataclass
# -----------------------------------------------------------------

def _taskstate_field_names() -> list[str]:
    """Return the list of field names defined on the TaskState dataclass."""
    return list(TaskState.__dataclass_fields__.keys())


def _taskstate_excludes() -> set[str]:
    """Field names that are classmethods/properties, not dataclass fields."""
    return {"from_queue", "to_handler_dict"}


# -----------------------------------------------------------------
# Test 1: Every TaskState field appears in TASK_FIELDS
# -----------------------------------------------------------------

def test_all_taskstate_fields_in_registry():
    """Fails CI if a TaskState field is missing from TASK_FIELDS."""
    dc_fields = set(_taskstate_field_names())
    reg_fields = {f.name for f in TASK_FIELDS}
    missing = dc_fields - reg_fields
    assert not missing, (
        f"TaskState field(s) missing from TASK_FIELDS registry: {missing}\n"
        f"Add them to TASK_FIELDS in autoswe/orch/types.py"
    )


def test_all_registry_fields_in_taskstate():
    """Fails CI if TASK_FIELDS references a non-existent TaskState field."""
    dc_fields = set(_taskstate_field_names())
    reg_fields = {f.name for f in TASK_FIELDS}
    extra = reg_fields - dc_fields
    assert not extra, (
        f"TASK_FIELDS references non-existent TaskState field(s): {extra}"
    )


# -----------------------------------------------------------------
# Test 2: Fully-populated queue dict round-trips (no silent fallback)
# -----------------------------------------------------------------

def _fully_populated_entry() -> dict[str, Any]:
    """Return a queue entry with every field set to a non-default sentinel."""
    return {
        "id": "gh:owner_repo_42",
        "owner": "acme",
        "repo": "widget",
        "issue_number": 99,
        "title": "Sentinel title",
        "body": "Sentinel body",
        "autoswe_status": "pending",
        "plan_branch": "my-branch",
        "base_branch": "develop",
        "attempt_count": 7,
        "first_dispatched_at": "2025-01-01T00:00:00Z",
        "last_dispatched_command": "/fix",
        "last_dispatched_command_id": 111,
        "last_consumed_reply_id": 222,
        "session_id": "sess-abc",
        "pr_number": 5,
        "_guard_blocked": True,
        "gh_closed": True,
        "pending_command": "/plan",
        "pending_guidance": "be fast",
        "pending_user_reply": "use logging",
        "suppress_welcome": True,
        "welcome_comment_id": 333,
        "bot_comment_ids": [10, 20, 30],
        "last_phase": "fix",
        "resume_phase": "plan",
        "created_at": "2024-01-01T00:00:00Z",
        "last_synced": "2025-06-01T00:00:00Z",
        "provider": "azure",
        "creator_login": "alice",
        "plan_file_path": "/tmp/plan.md",
        "review_file_path": "/tmp/review.md",
        "fix_summary": "fixed the thing",
    }


def test_roundtrip_no_silent_default():
    """Every populated field must be read — none should silently fall back to default."""
    entry = _fully_populated_entry()
    ts = TaskState.from_queue("gh:owner_repo_42", entry)

    for field in TASK_FIELDS:
        queue_val = entry.get(field.queue_key)
        state_val = getattr(ts, field.name)

        if queue_val is None:
            # Absent key → default is expected
            assert state_val == field.default, (
                f"{field.name}: queue key {field.queue_key!r} absent, "
                f"got {state_val!r} (expected default {field.default!r})"
            )
        else:
            # Present key → must match (after transform)
            expected = field.transform(queue_val) if field.transform else queue_val
            assert state_val == expected, (
                f"{field.name}: queue has {queue_val!r}, TaskState has {state_val!r}, "
                f"expected {expected!r}"
            )


# -----------------------------------------------------------------
# Test 3: to_handler_dict keys are backed by TASK_FIELDS + known extras
# -----------------------------------------------------------------

# Known runtime extras injected by to_handler_dict (not from registry)
_HANDLER_RUNTIME_EXTRAS = {"id", "_token"}


def test_handler_dict_keys_backed_by_registry():
    """Every key emitted by to_handler_dict is backed by TASK_FIELDS or a known extra."""
    entry = _fully_populated_entry()
    ts = TaskState.from_queue("gh:owner_repo_42", entry)
    handler = ts.to_handler_dict({"pat": "fake-token"})

    reg_queue_keys = {f.queue_key for f in TASK_FIELDS}
    allowed_keys = reg_queue_keys | _HANDLER_RUNTIME_EXTRAS

    stray = set(handler.keys()) - allowed_keys
    assert not stray, (
        f"to_handler_dict emitted key(s) not in TASK_FIELDS or runtime extras: {stray}"
    )

    # Reverse check: all registry keys should be present
    missing = reg_queue_keys - set(handler.keys())
    assert not missing, (
        f"to_handler_dict missing registry key(s): {missing}"
    )

    # Runtime extras must be present
    for extra in _HANDLER_RUNTIME_EXTRAS:
        assert extra in handler, f"to_handler_dict missing runtime extra {extra!r}"


# -----------------------------------------------------------------
# Test 4: TASK_FIELDS has no duplicate names or queue_keys
# -----------------------------------------------------------------

def test_registry_no_duplicate_names():
    """Each TaskState field name appears exactly once in TASK_FIELDS."""
    names = [f.name for f in TASK_FIELDS]
    assert len(names) == len(set(names)), "Duplicate field names in TASK_FIELDS"


def test_registry_no_duplicate_queue_keys():
    """Each queue key appears exactly once in TASK_FIELDS."""
    keys = [f.queue_key for f in TASK_FIELDS]
    assert len(keys) == len(set(keys)), "Duplicate queue keys in TASK_FIELDS"


# -----------------------------------------------------------------
# Test 5: from_queue signature is stable (classmethod, takes slug + entry)
# -----------------------------------------------------------------

def test_from_queue_signature():
    """from_queue must be a classmethod taking (cls, slug, entry)."""
    sig = inspect.signature(TaskState.from_queue.__func__)
    params = list(sig.parameters.keys())
    assert params == ["cls", "slug", "entry"], (
        f"from_queue signature changed: {params}"
    )
