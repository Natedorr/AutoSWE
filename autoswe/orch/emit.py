"""Layer C: Pure effect emission.

``emit(action, result, world) -> tuple[Effect, ...]`` produces the list of
writes: post comments, set status, patch queue, etc. Provider-agnostic —
the adapter translates each Effect to the provider's API.

Tests live in tests/test_emit.py, parametrized over fixture JSON files.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from autoswe.core.logging_utils import log
from autoswe.orch.types import Action, Effect, World
from autoswe.tracking.comments import BOT_MARKER
from autoswe.tracking.labels import COMPLETED_STATUSES, TERMINAL_STATUSES, _map_done_to_status

if TYPE_CHECKING:
    from autoswe.orch.run import DispatchResult

# Action kind → slash command (mirror of _CMD_TO_KIND in labels.py)
_KIND_TO_COMMAND = {
    "plan": "/plan",
    "fix": "/fix",
    "ship_pr": "/pr",
    "sync_branch": "/sync",
    "retry": "/retry",
    "review": "/review",
}

# ---------------------------------------------------------------------------
# Comment builders (pure functions, no I/O)
# ---------------------------------------------------------------------------


def _format_metrics(cost_usd: float | None, duration_seconds: float | None, session_id: str | None) -> str:
    """Append cost/duration/session metrics to a completion comment."""
    parts = []
    if cost_usd is not None:
        parts.append(f"Cost: ${cost_usd:.2f}")
    if duration_seconds is not None and duration_seconds > 0:
        m, s = divmod(int(duration_seconds), 60)
        parts.append(f"Duration: {m}m{s}s")
    if session_id:
        parts.append(f"Session: {session_id}")
    if parts:
        return "\n\n" + " · ".join(parts) + "\n"
    return ""


def _build_completion_comment(
    pending_command: str,
    done_content: str,
    task_owner: str,
    task_repo: str,
    issue_num: int,
    plan_branch: str | None,
    provider: str,
    cost_usd: float | None,
    duration_seconds: float | None,
    session_id: str | None,
) -> str:
    """Build a completion comment from handler done_content.

    For DONE_SUMMARY produces a rich comment with commit link, branch link,
    and Claude's summary. For other DONE variants falls back to simpler format.
    """
    branch = plan_branch or f"autoswe/issue-{issue_num}"

    if done_content.startswith("DONE_SUMMARY\t"):
        rest = done_content[len("DONE_SUMMARY\t") :]
        tab_idx = rest.rfind("\t")
        if tab_idx >= 0:
            summary = rest[:tab_idx].strip()
            commit_sha = rest[tab_idx + 1 :].strip()
        else:
            summary = rest.strip()
            commit_sha = None

        lines = [f"Completed with command `{pending_command}`."]

        if commit_sha:
            if provider == "github":
                lines.append(f"[Commit](https://github.com/{task_owner}/{task_repo}/commit/{commit_sha})")
            elif provider == "azure":
                lines.append(f"Commit: {commit_sha}")
            else:
                lines.append(f"Commit: {commit_sha}")

            lines.append(f"[View branch](https://github.com/{task_owner}/{task_repo}/compare/{branch})")

        lines.append("")
        if len(summary) > 1200:
            summary = summary[:1197] + "... truncated"
        lines.append(f"**Summary:**\n\n{summary}")
    else:
        suffix = done_content[5:].strip() if done_content.startswith("DONE:") else "done."
        lines = [f"Completed with command `{pending_command}` — {suffix}"]

    body = "\n".join(lines)
    return body + _format_metrics(cost_usd, duration_seconds, session_id) + BOT_MARKER


# ---------------------------------------------------------------------------
# Effect emission
# ---------------------------------------------------------------------------


def emit(
    action: Action,
    result: "DispatchResult | None",
    world: World,
) -> tuple[Effect, ...]:
    """Return the Effects to apply after an Action ran.

    For actions that don't invoke Claude (skip, abort, noop, etc),
    result is None and we emit pure status/queue changes.
    """
    task = world.task
    cfg = world.cfg
    kind = action.kind

    # --- No-Claude actions (result is None) ---

    if kind == "noop":
        return ()

    if kind == "skip":
        return (
            Effect(kind="set_status", status="skipped"),
            Effect(
                kind="patch_queue",
                queue_patch={
                    "autoswe_status": "skipped",
                    "first_dispatched_at": None,
                    "pending_command": None,
                    "pending_guidance": None,
                },
            ),
        )

    if kind == "abort":
        return (
            Effect(kind="post_comment", body=f"Task aborted.{BOT_MARKER}"),
            Effect(kind="set_status", status="aborted"),
            Effect(
                kind="patch_queue",
                queue_patch={
                    "autoswe_status": "aborted",
                    "first_dispatched_at": None,
                    "pending_command": None,
                    "pending_guidance": None,
                },
            ),
        )

    if kind == "post_welcome":
        return (
            Effect(kind="post_comment", body=action.guidance or ""),
            Effect(
                kind="patch_queue",
                queue_patch={"suppress_welcome": True},
            ),
        )

    if kind == "advance_watermark":
        return (
            Effect(kind="set_status", status="pending"),
            Effect(
                kind="patch_queue",
                queue_patch={"autoswe_status": "pending"},
            ),
        )

    if kind == "mark_failed_limit":
        if action.limit_reason == "time":
            max_hours = cfg.get("MAX_TOTAL_HOURS", 2)
            msg = f"Time limit ({max_hours}h) reached. Post `/retry` to continue.{BOT_MARKER}"
        else:
            max_attempts = cfg.get("MAX_ATTEMPTS", 3)
            msg = f"Max attempts ({max_attempts}) reached. Post `/retry` to continue.{BOT_MARKER}"
        return (
            Effect(kind="post_comment", body=msg),
            Effect(kind="set_status", status="failed"),
            Effect(
                kind="patch_queue",
                queue_patch={
                    "autoswe_status": "failed",
                    "attempt_count": action.attempt_count,
                    "_guard_blocked": True,
                    "first_dispatched_at": None,
                    "pending_command": None,
                },
            ),
        )

    # --- Claude actions (result should be DispatchResult) ---

    if result is None:
        # Handler returned nothing unexpected — treat as noop
        return ()

    done = result.done_content
    new_status = _map_done_to_status(done, kind)
    session_id = result.session_id or task.session_id

    # --- Common queue patch for all Claude actions ---
    old_status = task.status

    pending_command = _KIND_TO_COMMAND.get(kind, "/fix")

    log(f"[EMIT] {task.slug} status {old_status}->{new_status} attempt={action.attempt_count}")
    queue_patch = {
        "autoswe_status": new_status,
        "last_dispatched_command": pending_command,
        "last_dispatched_command_id": action.triggering_comment_id,
        "last_consumed_reply_id": action.triggering_comment_id,
        "attempt_count": action.attempt_count,
        "pending_command": None,
        "pending_guidance": None,
        "pending_user_reply": None,
    }

    # Reset guard flag on retry so subsequent /fix is not blocked
    if kind == "retry":
        queue_patch["_guard_blocked"] = False

    # Update session_id if Claude returned one (skip for review — review
    # uses a throwaway session and should not overwrite the persistent fix session)
    if session_id and kind != "review":
        queue_patch["session_id"] = session_id

    # Set last_phase so resume knows which handler to call
    if kind in ("plan",):
        queue_patch["last_phase"] = "plan"
    elif kind in ("fix", "retry"):
        queue_patch["last_phase"] = "fix"

    # plan_file_path lifecycle:
    #  * plan + planned  -> persist the path the planner wrote
    #  * plan + waiting     -> leave existing value alone (mid-conversation)
    #  * fix / retry / sync -> always clear (consumed or no longer applicable)
    #  * terminal statuses  -> clear (the plan is no longer the current plan)
    if kind == "plan":
        if new_status == "planned" and result.plan_file_path:
            queue_patch["plan_file_path"] = result.plan_file_path
        elif new_status not in ("waiting",):
            queue_patch["plan_file_path"] = None
    elif kind in ("fix", "retry", "sync_branch", "ship_pr"):
        queue_patch["plan_file_path"] = None

    # review_file_path lifecycle:
    #  * review + REVIEW_READY -> persist the path the reviewer wrote
    #  * fix / plan / retry -> always clear (consumed by build_fix_prompt / build_plan_prompt)
    if kind == "review" and result.review_file_path:
        queue_patch["review_file_path"] = result.review_file_path
    elif kind in ("fix", "plan", "retry"):
        queue_patch["review_file_path"] = None

    # Reset first_dispatched_at on terminal statuses — must happen BEFORE
    # the review early return so that review-on-terminal (e.g. review on
    # a fixed task) also clears the stale timestamp. Without this, the time
    # guard in decide.py fires on follow-up commands posted hours after
    # the original task completed.
    if new_status in TERMINAL_STATUSES:
        queue_patch["first_dispatched_at"] = None

    # Review is now terminal — transitions to "reviewed".
    # Keep not clearing plan_file_path/session_id so a later /fix still has the plan.
    if kind == "review":
        review_text = done[len("REVIEW_READY\t"):] if done.startswith("REVIEW_READY\t") else ""
        metrics = _format_metrics(result.cost_usd, result.duration_seconds, session_id)
        review_comment = f"## Review\n\n{review_text}\n\n{metrics.strip()}{BOT_MARKER}" if metrics.strip() else f"## Review\n\n{review_text}\n\n{BOT_MARKER}"
        return (
            Effect(kind="post_comment", body=review_comment),
            Effect(kind="set_status", status=new_status),
            Effect(kind="patch_queue", queue_patch=queue_patch),
        )

    effects: list[Effect] = []

    # --- Post comment based on status ---
    # Note: for terminal statuses (fixed/failed/aborted), the caller
    # (_finalize_handler in loop.py) handles the sticky progress comment
    # finalization via progress.finalize(). emit() only records the status
    # change and queue patch here to avoid double-posting comments.

    if new_status == "planned":
        effects.append(Effect(kind="set_status", status="planned"))
        effects.append(Effect(kind="patch_queue", queue_patch=queue_patch))

    elif new_status == "waiting":
        effects.append(Effect(kind="set_status", status="waiting"))
        effects.append(Effect(kind="patch_queue", queue_patch=queue_patch))

    elif new_status in COMPLETED_STATUSES:
        comment = _build_completion_comment(
            pending_command=pending_command,
            done_content=done,
            task_owner=task.owner,
            task_repo=task.repo,
            issue_num=task.issue_number,
            plan_branch=task.plan_branch,
            provider=task.provider,
            cost_usd=result.cost_usd,
            duration_seconds=result.duration_seconds,
            session_id=session_id,
        )
        effects.append(Effect(kind="post_comment", body=comment))
        effects.append(Effect(kind="set_status", status=new_status))
        effects.append(Effect(kind="patch_queue", queue_patch=queue_patch))

        # Auto-create PR if fix completed and configured
        if kind in ("fix", "retry") and cfg.get("AUTO_CREATE_PR") and task.pr_number is None:
            branch = task.plan_branch or f"autoswe/issue-{task.issue_number}"
            effects.append(
                Effect(
                    kind="create_pr",
                    pr_title=f"Fixes #{task.issue_number}: {task.title}",
                    pr_body=f"Fixes #{task.issue_number}",
                    pr_head=branch,
                    pr_base=task.base_branch,
                )
            )

    elif new_status == "failed":
        reason = done[7:].strip() if done.startswith("FAILED:") else done
        fail_msg = f"Failed: {reason}\n\nPost `/retry` to continue.{BOT_MARKER}"
        effects.append(Effect(kind="post_comment", body=fail_msg))
        effects.append(Effect(kind="set_status", status="failed"))
        # Clear session_id on failure — the remote session is likely broken,
        # so the next retry should start fresh instead of resuming a stale session
        queue_patch["session_id"] = None
        effects.append(Effect(kind="patch_queue", queue_patch=queue_patch))

    elif new_status == "aborted":
        effects.append(Effect(kind="post_comment", body=f"Task aborted.{BOT_MARKER}"))
        effects.append(Effect(kind="set_status", status="aborted"))
        effects.append(Effect(kind="patch_queue", queue_patch=queue_patch))

    else:
        # Unknown status — just patch queue
        effects.append(Effect(kind="patch_queue", queue_patch=queue_patch))

    # --- Auto-assign ---
    if cfg.get("AUTO_ASSIGN"):
        # Only assign on first dispatch or phase transitions
        if task.status is None or task.status in ("planned",):
            assignee = cfg.get("ASSIGN_USER") or world.api.issue.creator_login or None
            if assignee:
                effects.append(Effect(kind="assign", body=assignee))

    return tuple(effects)
