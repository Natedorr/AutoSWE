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
from autoswe.providers.base import CIStatus, NormalizedComment, NormalizedIssue

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
    TaskField("last_good_session_id", "last_good_session_id", None),
    TaskField("last_good_session_backend", "last_good_session_backend", None),
    TaskField("last_replayed_command", "last_replayed_command", None),
    TaskField("pr_number", "pr_number", None),
    TaskField("guard_blocked", "_guard_blocked", False),
    TaskField("gh_closed", "gh_closed", False),
    TaskField("pending_command", "pending_command", None),
    TaskField("pending_guidance", "pending_guidance", None),
    TaskField("pending_user_reply", "pending_user_reply", None),
    # --- Optional fields (dataclass default) ---
    TaskField("suppress_welcome", "suppress_welcome", False),
    TaskField("welcome_comment_id", "welcome_comment_id", None),
    TaskField("progress_comment_id", "progress_comment_id", None),
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
    TaskField("rereview_after_fix", "rereview_after_fix", False),
    TaskField("pr_url", "pr_url", None),
    TaskField("linkage_state", "linkage_state", None),
    TaskField("linkage_missing", "linkage_missing", (),
              transform=lambda v: tuple(v) if isinstance(v, list) else v),
    TaskField("ci_last_checked", "ci_last_checked", None),
    TaskField("ci_status", "ci_status", None),
    TaskField("ci_failed_from_status", "ci_failed_from_status", None),
    TaskField("ci_last_notified_sha", "ci_last_notified_sha", None),
    TaskField("ci_error_notified", "ci_error_notified", False),
    TaskField("ci_error_notified_sha", "ci_error_notified_sha", None),
    # Shared recoverable-gate policy (issue #245 §2.5) — one counter and one
    # per-commit watermark drive auto-fix for BOTH test_failed (local test
    # gate) and ci_failed (remote CI watch). See orch/gate_policy.py.
    TaskField("gate_attempt_count", "gate_attempt_count", 0),
    TaskField("gate_last_fixed_sha", "gate_last_fixed_sha", None),
    # Local test-gate bookkeeping, parallel to the ci_* fields above but
    # specific to the test_failed signal.
    TaskField("test_failed_sha", "test_failed_sha", None),
    TaskField("test_failure_detail", "test_failure_detail", None),
    TaskField("test_gate_limit_notified", "test_gate_limit_notified", False),
    # pr_deferred (issue #245 §2.6): a create_pr effect blocked by pending/
    # failing/unreachable CI sets this instead of asking the user to re-post
    # /pr; the next green CI observation re-emits create_pr and clears it.
    TaskField("pr_deferred", "pr_deferred", False),
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
    # ID of the sticky progress comment for the current dispatch. Survives in
    # the queue only when a dispatch crashes (finalize clears it on any clean
    # return), so its presence together with an "error" status is the signal
    # that a /retry should re-use — not re-post — the sticky comment.
    progress_comment_id: int | None = None
    bot_comment_ids: tuple[int, ...] = ()
    last_phase: str = "plan"
    # Explicitly tracks which phase should resume after a user reply.
    # Set by emit() alongside last_phase. Used by _resume_kind() as the
    # authoritative source (falls back to last_phase if missing).
    resume_phase: str | None = None
    # Last known-good session checkpoint. Set by emit() on every non-failed run
    # that persists a session_id, and NEVER cleared on FAILED (unlike
    # session_id, which the FAILED path nulls out). This is what /retry forks
    # from on backends that advertise the "session_fork" capability, so a
    # failed retry leaves the checkpoint intact and the next /retry re-forks
    # from the same good session. Defaulted so positional TaskState(...)
    # construction in tests is unaffected.
    last_good_session_id: str | None = None
    # Which coding backend produced last_good_session_id (its "backend" field,
    # e.g. "claude_code" / "codex"). Set by emit() alongside the checkpoint so a
    # /retry only forks when the checkpoint's backend matches the phase's
    # resolved backend — a Codex plan's session must not be resumed by a Claude
    # fix (the SDK can't resolve a foreign-backend session id). Never cleared on
    # FAILED, mirroring last_good_session_id.
    last_good_session_backend: str | None = None
    # The slash command a /retry actually REPLAYED (after its fallback rules:
    # non-replayable -> /fix, /review on failed -> /fix). Set by emit() only for
    # kind="retry"; a subsequent /retry follows THIS (the last substantive command
    # that ran) instead of last_dispatched_command, which stays the literal
    # "/retry" so the re-dispatch dedup in decide() can match it. A plain
    # /plan / /fix / /review dispatch clears it (see emit()) so it never dangles
    # past the retry that set it. None otherwise.
    last_replayed_command: str | None = None
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
    # Set by emit() when a /fix dispatched from a review_failed/review_blocked
    # state completes. decide() then auto-dispatches a /review on the next poll
    # (and clears the flag) so the gating verdict is re-checked before /pr.
    rereview_after_fix: bool = False
    # Cached PR web URL, persisted alongside pr_number at ship time (issue #193).
    # pr_number is the machine-facing cache (idempotency, result.json); pr_url
    # is the human-facing link for operators inspecting queue.json.
    pr_url: str | None = None
    # Last observed LinkageState (as a dict) and its missing-edge names, set by
    # autoswe.vcs.linkage.ensure_links at branch/PR-open/merge-observation call
    # sites (issue #245 §1.4). Rendered as a checklist by `queue status` / `/sync`.
    linkage_state: dict | None = None
    linkage_missing: tuple[str, ...] = ()
    # Last-known CI observation, cached by autoswe.providers.adapter.read_ci
    # (issue #245 plan §2.2) — the watermark timestamp and the serialized
    # CIStatus. Rendered by ``/sync`` and ``queue status``; a value here
    # persists across cycles that don't re-consult the API (throttled).
    ci_last_checked: str | None = None
    ci_status: dict | None = None
    # CI-watch bookkeeping for the ci_failed status (issue #245 plan §2.3, P3).
    # ci_failed_from_status is the status to restore on a green build — set
    # when decide()/emit() first parks the task at ci_failed, cleared on
    # recovery. ci_last_notified_sha is the head_sha of the last failure
    # already surfaced as a comment, so an unchanged red build doesn't churn
    # a comment every poll. ci_error_notified is a one-time flag for the
    # "CI could not be consulted" warning, so an error streak comments once;
    # ci_error_notified_sha is the head_sha (possibly None) that flag was
    # raised for, so a new push during a persistent error streak still warns.
    ci_failed_from_status: str | None = None
    ci_last_notified_sha: str | None = None
    ci_error_notified: bool = False
    ci_error_notified_sha: str | None = None
    # Shared recoverable-gate auto-fix bookkeeping (issue #245 plan §2.5). One
    # counter, kept *separate* from attempt_count so a gate-triggered loop can
    # never consume the budget a human /fix depends on (brake 1), drives
    # auto-fix recovery for BOTH ci_failed and test_failed. Resets to 0 only
    # on a green signal (ci_recovered) or a human-dispatched Claude action
    # (emit()'s common patch); never on a push the agent itself made.
    # gate_last_fixed_sha is the per-commit watermark (brake 2): an auto-fix
    # is dispatched at most once per head/local commit, checked before the
    # counter so a lost/reset counter still can't loop on an unchanged commit.
    gate_attempt_count: int = 0
    gate_last_fixed_sha: str | None = None
    # Local test-gate (test_failed) bookkeeping, parallel to the ci_* fields
    # above. test_failed_sha is the commit the branch suite is currently red
    # for; test_failure_detail is the pytest output tail used to build the
    # auto-fix guidance; test_gate_limit_notified is a one-time flag so an
    # exhausted gate budget comments once, not every poll (mirrors
    # ci_error_notified).
    test_failed_sha: str | None = None
    test_failure_detail: str | None = None
    test_gate_limit_notified: bool = False
    # pr_deferred (issue #245 plan §2.6): a create_pr effect blocked by
    # pending/failing/unreachable CI sets this instead of asking the user to
    # re-post /pr; the next green CI observation re-emits create_pr.
    pr_deferred: bool = False

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
    # This poll's CI observation, or None when not consulted this cycle
    # (ineligible, CI_WATCH off, or throttled — issue #245 plan §2.2). A
    # distinct, checkable state from an actual CIStatus, mirroring the
    # ``comments_fetched`` idiom. decide() does not consume this yet (P2 is
    # report-only); it is plumbed through for /sync + queue status.
    ci: CIStatus | None = None


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
        "refused",
        "review",
        "ci_failed",
        "ci_recovered",
        "ci_error_warn",
        "retry_deferred_pr",
    ]
    slug: str
    plan_branch: str | None = None
    guidance: str | None = None
    resume_session_id: str | None = None
    attempt_count: int = 0
    triggering_comment_id: int | None = None
    user_reply_text: str | None = None
    limit_reason: Literal["attempts", "time", "ci", "gate"] | None = None
    # For kind="refused": the slash command that was refused
    # (e.g. "/pr" on a failed task, "/fix" on a guard-blocked task).
    # emit() uses it to pick the refusal message.
    refused_command: str | None = None
    # Set to "ci" or "gate" for a kind="fix" auto-dispatched by the shared
    # recoverable-gate policy (issue #245 plan §2.3-§2.5) — distinguishes it
    # from a human-triggered "fix" so emit() bumps the shared
    # gate_attempt_count / gate_last_fixed_sha watermark instead of the phase
    # attempt_count. "ci" is the remote CI watch (run() fetches and appends
    # get_ci_failures() text to the guidance); "gate" is the local post-fix
    # test gate (guidance is already fully assembled by decide()). None for
    # every human dispatch.
    trigger: Literal["ci", "gate"] | None = None


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
