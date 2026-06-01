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

from dataclasses import dataclass
from typing import Literal

# Re-export the existing RunResult so types.py is self-contained
from autoswe.harness.runner import RunResult  # noqa: F401
from autoswe.providers.base import NormalizedComment, NormalizedIssue  # noqa: F401


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
