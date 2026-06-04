"""Frozen dataclasses for the orchestrator.

Each type is an immutable snapshot at one boundary of the pipeline:
  ApiState  — what the provider API said (Layer A input)
  TaskState — what queue.json said at poll time (Layer A input)
  World     — the full picture (Layer A input)
  Action    — what to do (Layer A output)
  Result    — what Claude produced (Layer B output, re-exported from harness)
  Effect    — what to write back (Layer C output)
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

# Re-export the existing RunResult so types.py is self-contained
from autoswe.harness.runner import RunResult  # noqa: F401
from autoswe.providers.base import NormalizedComment, NormalizedIssue

# --------------------------------------------------------------------------
# Declarative field registry — single source of truth for TaskState ↔ queue
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class TaskField:
    """One persisted field: TaskState attr ↔ queue key ↔ default ↔ transform."""
    name: str                  # TaskState attribute name
    queue_key: str             # key in queue.json entry
    default: Any               # value used when the queue key is absent
    transform: Callable | None = None  # queue_value → TaskState field (e.g. list → tuple)


def _identity(v: Any) -> Any:
    return v


# Every TaskState field must appear exactly once in this list.
# Order matches the TaskState dataclass definition (required fields first,
# optional fields with defaults second).
TASK_FIELDS: tuple[TaskField, ...] = (
    # --- Required fields (no default in dataclass) ---
    TaskField("slug", "id", ""),
    TaskField("owner", "owner", ""),
    TaskField("repo", "repo", ""),
    TaskField("issue_number", "issue_number", 0),
    TaskField("title", "title", ""),
    TaskField("body", "body", ""),
    TaskField("status", "autoswe_status", None),
    TaskField("plan_branch", "plan_branch", None),
    TaskField("base_branch", "base_branch", "main"),
    TaskField("attempt_count", "attempt_count", 0),
    TaskField("first_dispatched_at", "first_dispatched_at", None),
    TaskField("last_dispatched_command", "last_dispatched_command", None),
    TaskField("last_dispatched_command_id", "last_dispatched_command_id", None),
    TaskField("last_consumed_reply_id", "last_consumed_reply_id", None),
    TaskField("session_id", "session_id", None),
    TaskField("pr_number", "pr_number", None),
    TaskField("guard_blocked", "_guard_blocked", False),
    TaskField("gh_closed", "gh_closed", False),
    TaskField("pending_command", "pending_command", None),
    TaskField("pending_guidance", "pending_guidance", None),
    TaskField("pending_user_reply", "pending_user_reply", None),
    # --- Optional fields (dataclass default) ---
    TaskField("suppress_welcome", "suppress_welcome", False),
    TaskField("welcome_comment_id", "welcome_comment_id", None),
    TaskField("bot_comment_ids", "bot_comment_ids", (),
              transform=lambda v: tuple(v) if isinstance(v, list) else v),
    TaskField("last_phase", "last_phase", "plan"),
    TaskField("resume_phase", "resume_phase", None),
    TaskField("created_at", "created_at", ""),
    TaskField("last_synced", "last_synced", ""),
    TaskField("provider", "provider", "github"),
    TaskField("creator_login", "creator_login", ""),
    TaskField("plan_file_path", "plan_file_path", None),
    TaskField("review_file_path", "review_file_path", None),
    TaskField("fix_summary", "fix_summary", ""),
)


@dataclass(frozen=True)
class ApiState:
    """Provider-agnostic snapshot of what was just fetched.

    Adapters produce this; nothing downstream knows whether labels came from
    GH labels or ADO tags. Comments are always clean text (HTML stripped,
    entities decoded, bot markers normalized).

    ``comments_fetched`` indicates whether the comments were actually fetched
    from the API, or whether this is a placeholder for a skipped (unchanged)
    issue.
    """
    issue: NormalizedIssue
    comments: tuple[NormalizedComment, ...]
    open_pr_numbers: tuple[int, ...] = ()
    comments_fetched: bool = True


@dataclass(frozen=True)
class TaskState:
    """Pure snapshot of the queue.json entry at poll time.

    All fields are named explicitly from the queue schema. Transient fields
    like _token, _comment_id, _minimal_posting are excluded — they belong in
    the dispatch runtime, not the decision boundary.
    """
    slug: str
    owner: str
    repo: str
    issue_number: int
    title: str
    body: str
    status: str | None              # autoswe_status
    plan_branch: str | None
    base_branch: str
    attempt_count: int
    first_dispatched_at: str | None
    last_dispatched_command: str | None
    last_dispatched_command_id: int | None
    last_consumed_reply_id: int | None
    session_id: str | None
    pr_number: int | None
    guard_blocked: bool
    gh_closed: bool
    pending_command: str | None
    pending_guidance: str | None
    pending_user_reply: str | None
    suppress_welcome: bool = False
    welcome_comment_id: int | None = None
    bot_comment_ids: tuple[int, ...] = ()
    last_phase: str = "plan"
    # Explicitly tracks which phase should resume after a user reply.
    # Set by emit() alongside last_phase. Used by _resume_kind() as the
    # authoritative source (falls back to last_phase if missing).
    resume_phase: str | None = None
    created_at: str = ""
    last_synced: str = ""
    provider: str = "github"
    creator_login: str = ""
    # Path to the ~/.claude/plans/<...>.md file the planner wrote on
    # PLAN_READY. Set by emit() in the queue_patch for "planned" and
    # consumed by run_fix to start a fresh session seeded with the plan.
    # Cleared by emit() when fix completes.
    plan_file_path: str | None = None
    # Path to the ~/.claude/reviews/<slug>.md file the reviewer wrote on
    # REVIEW_READY. Set by emit() when /review completes (reviewed status) and consumed by
    # build_fix_prompt / build_plan_prompt on the next /fix or /plan,
    # then cleared (pop-after-first-use lifecycle).
    review_file_path: str | None = None
    # Extracted from DONE_SUMMARY on fix/retry completion. Persisted in the
    # queue so PR creation can include it in the body.
    fix_summary: str = ""

    @classmethod
    def from_queue(cls, slug: str, entry: dict) -> TaskState:
        """Build a TaskState from a queue.json entry using TASK_FIELDS registry.

        Replaces the hand-written _build_poll_task constructor call.
        The ``slug`` positional is deprecated — reads from entry["id"] via
        the registry like every other field. This signature keeps the old
        caller (_build_poll_task) shape for the transition period.
        """
        kwargs: dict[str, Any] = {}
        for field in TASK_FIELDS:
            raw = entry.get(field.queue_key)
            if raw is None:
                kwargs[field.name] = field.default
            else:
                kwargs[field.name] = field.transform(raw) if field.transform else raw
        return cls(**kwargs)

    def to_handler_dict(self, repo_cfg: dict) -> dict:
        """Build the mutable task dict that handlers expect.

        Derived from TASK_FIELDS so every persisted field is included
        automatically. Two runtime extras are appended:
          ``id`` — human-readable ``owner/repo#N`` for logs and prompts
          ``_token`` — PAT from repo_cfg, injected at dispatch time
        """
        d: dict[str, Any] = {}
        for field in TASK_FIELDS:
            val = getattr(self, field.name)
            # Copy list-as-tuple fields back to list for handler mutability
            if field.name == "bot_comment_ids" and isinstance(val, tuple):
                val = list(val)
            d[field.queue_key] = val
        d["id"] = f"{self.owner}/{self.repo}#{self.issue_number}"
        d["_token"] = repo_cfg.get("pat") or repo_cfg.get("token", "")
        return d


@dataclass(frozen=True)
class World:
    """Full picture at the moment of decision.

    Passed to decide() and emit(). Everything the state machine needs,
    no I/O required.
    """
    api: ApiState
    task: TaskState
    cfg: dict
    repo_cfg: dict


@dataclass(frozen=True)
class Action:
    """What the control module should do next.

    Provider-agnostic. Cached at the test seam between Layer A (decide)
    and Layer B (run) / Layer C (emit).
    """
    kind: Literal[
        "plan", "fix", "ship_pr", "sync_branch",
        "retry", "skip", "abort", "noop",
        "post_welcome",
        "advance_watermark",
        "mark_failed_limit",
        "review",
    ]
    slug: str
    plan_branch: str | None = None
    guidance: str | None = None
    resume_session_id: str | None = None
    attempt_count: int = 0
    triggering_comment_id: int | None = None
    user_reply_text: str | None = None
    limit_reason: Literal["attempts", "time"] | None = None


@dataclass(frozen=True)
class Effect:
    """Provider-agnostic write. Translated by provider adapters.

    Each Effect is one API call or queue mutation. The adapter decides
    how to express it (GH labels vs ADO tags, markdown vs HTML, etc.).
    """
    kind: Literal[
        "post_comment", "update_comment", "set_status",
        "patch_queue", "assign", "create_pr", "noop",
    ]
    body: str | None = None
    comment_id: int | None = None
    status: str | None = None
    queue_patch: dict | None = None
    pr_title: str | None = None
    pr_body: str | None = None
    pr_head: str | None = None
    pr_base: str | None = None
