"""Layer A: Pure state machine.

``decide(world) -> Action`` replaces every transition decision currently
inlined in sync.py and dispatch.py. No I/O — just matching on World and
returning an Action.

Tests live in tests/test_decide.py, parametrized over fixture JSON files.
"""
from __future__ import annotations

from datetime import datetime, timezone

from autoswe.commands.parser import parse_slash_command
from autoswe.core.logging_utils import log
from autoswe.orch.types import Action, World
from autoswe.tracking.comments import (
    _find_last_bot_comment_id,
    _find_last_completion_id,
)
from autoswe.tracking.labels import (
    COMPLETED_STATUSES,
    RUNNING_STATUSES,
    TERMINAL_STATUSES,
    _kind_from_command,
)

# States from which a completion comment ID is used as the reference watermark.
# Excludes "error" — error state uses last bot comment, not last completion.
_COMPLETED_OR_TERMINAL_FOR_WATERMARK = COMPLETED_STATUSES | frozenset({"failed", "skipped", "aborted"})

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_slash_command(
    comments: tuple,
    issue_body: str,
    bot_name: str,
    creator_login: str = "",
):
    """Find the latest slash command from comments, then issue body.

    Returns ((cmd, guidance, branch), author_login, raw_author_login, source_id).
    If the command comes from the issue body, author_login is the actual
    creator_login (for allowlist checking) and source_id is 0 (sorts older
    than any real comment ID). raw_author_login is the original login before
    normalization, used for allowlist matching.
    """
    for comment in sorted(comments, key=lambda c: c.created_at, reverse=True):
        result = parse_slash_command(comment.body, bot_name=bot_name)
        if result:
            slash_cmd, _, _ = result
            raw_author = getattr(comment, "raw_author_login", "")
            log(f"[DECIDE] found cmd={slash_cmd} id={comment.id or 0} author={comment.author_login}")
            return result, comment.author_login, raw_author, comment.id or 0
    result = parse_slash_command(issue_body or "", bot_name=bot_name)
    if result:
        slash_cmd, _, _ = result
        log(f"[DECIDE] found cmd={slash_cmd} (from issue body)")
        return result, creator_login, creator_login, 0
    return None, None, "", 0


def _is_author_allowed(
    author_login: str, cfg: dict, repo_cfg: dict, raw_author_login: str = "",
) -> bool:
    """Check if an author is allowed to trigger slash commands.

    Checks both the normalized ``author_login`` and the raw login
    (before OWNER/AUTHOR normalization) against the allowlist, so that
    ``ALLOWED_AUTHORS=Natedorr`` still matches when the comment author
    has been normalized to ``OWNER``.
    """
    allowed_raw = cfg.get("ALLOWED_AUTHORS", set())
    repo_override = repo_cfg.get("allowed_authors", "")
    repo_allowed = (
        {a.strip() for a in str(repo_override).split(",") if a.strip()}
        if repo_override
        else set()
    )
    active = repo_allowed or allowed_raw
    if not active:
        return True
    if author_login in active:
        return True
    if raw_author_login and raw_author_login in active:
        return True
    return False


def _has_user_reply_after(
    comments: tuple, after_id: int | str | None, last_consumed: int | str | None
) -> tuple | None:
    """Find the latest user comment after both watermarks.

    Returns the NormalizedComment or None.
    Uses is_bot flag as the sole source of truth for bot detection.

    Handles mixed watermark types: when the fallback returns a timestamp
    (str), compares by created_at. When IDs are available (int), compares
    by ID.
    """
    # Determine comparison mode: if after_id is int, compare by ID.
    # If after_id is str (timestamp fallback), compare by timestamp.
    use_ids = isinstance(after_id, int)

    if use_ids:
        user_after = [
            c
            for c in comments
            if not c.is_bot
            and c.id is not None
            and c.id > (after_id or 0)
            and c.id > (last_consumed or 0)
        ]
    else:
        # TODO: remove after queue migration — timestamp fallback for old queue entries
        after_ts = after_id or ""
        consumed_ts = last_consumed or ""
        user_after = [
            c
            for c in comments
            if not c.is_bot
            and c.created_at > after_ts
            and c.created_at > consumed_ts
        ]

    if user_after:
        return user_after[-1]
    return None


def _has_new_user_comment_after(comments: tuple, after_id: int | str | None) -> bool:
    """Check if any non-bot comment exists after the given watermark.

    Handles both ID (int) and timestamp (str) watermarks.
    """
    if isinstance(after_id, int):
        return any(
            not c.is_bot and c.id is not None and c.id > after_id
            for c in comments
        )
    # TODO: remove after queue migration — timestamp fallback for old queue entries
    after_ts = after_id or ""
    return any(
        not c.is_bot and c.created_at > after_ts
        for c in comments
    )


def _elapsed_hours_since(iso_ts: str | None) -> float | None:
    """Hours elapsed since iso_ts, or None if ts is unset."""
    if not iso_ts:
        return None
    try:
        dt = datetime.fromisoformat(iso_ts)
        return (datetime.now(timezone.utc) - dt).total_seconds() / 3600
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Terminal / guard helpers
# ---------------------------------------------------------------------------


def _check_restart_or_guard(
    world: World,
    slash_cmd: str,
    guidance: str | None,
    branch: str | None,
    cmd_author: str | None,
    cmd_id: int | None,
) -> Action | None:
    """Handle transitions from terminal states.

    Returns an Action if the transition is handled, None to fall through.
    """
    task = world.task
    api = world.api
    cfg = world.cfg
    repo_cfg = world.repo_cfg
    comments = api.comments
    status = task.status

    # Guard-blocked tasks skip the entire restart cycle unless /retry, /skip, or /abort
    if task.guard_blocked and slash_cmd not in ("/retry", "/skip", "/abort"):
        return Action(kind="noop", slug=task.slug)

    # Find the reference ID (bot completion or last bot comment)
    if status in _COMPLETED_OR_TERMINAL_FOR_WATERMARK:
        last_autoswe = _find_last_completion_id(comments)
    else:
        last_autoswe = _find_last_bot_comment_id(comments)

    has_new_user = _has_new_user_comment_after(comments, last_autoswe)
    log(f"[DECIDE] {task.slug} has_new_user={has_new_user} status={status}")

    # Terminal restart guard: when slash_cmd is None and has_new_user is True,
    # the restart block below dispatches _kind_from_command(None) = "fix".
    # To prevent accidental restarts from casual comments:
    #   - If an allowlist is configured, plain-text comments do NOT trigger restarts
    #     (explicit slash command required). Unauthorized authors are also blocked.
    #   - If no allowlist is configured, anyone can restart (original behavior).
    if has_new_user and slash_cmd is None:
        # Determine if an allowlist is active
        active_allowlist = cfg.get("ALLOWED_AUTHORS", set())
        repo_override = repo_cfg.get("allowed_authors", "")
        repo_allowed = (
            {a.strip() for a in str(repo_override).split(",") if a.strip()}
            if repo_override
            else set()
        )
        allowlist_active = bool(repo_allowed or active_allowlist)

        if allowlist_active:
            # Find the latest new non-bot comment to check its author
            new_comment = None
            if isinstance(last_autoswe, int):
                for c in comments:
                    if not c.is_bot and c.id is not None and c.id > (last_autoswe or 0):
                        new_comment = c
            else:
                after_ts = last_autoswe or ""
                for c in comments:
                    if not c.is_bot and c.created_at > after_ts:
                        new_comment = c
            if new_comment and not _is_author_allowed(
                new_comment.author_login or "", cfg, repo_cfg,
                getattr(new_comment, "raw_author_login", ""),
            ):
                log(f"[DECIDE] {task.slug} terminal restart blocked: new comment from {new_comment.author_login} not in allowlist")
                return Action(kind="noop", slug=task.slug)
            # Even if the author IS allowed, plain-text comment with no explicit
            # slash command does not trigger restart when allowlist is active.
            return Action(kind="noop", slug=task.slug)

    # Provider-agnostic guard: skip if this exact command was already dispatched
    # and the slash command isn't newer than our record.
    # Skip this guard for body-sourced commands (cmd_id=0) — they always exist
    # and shouldn't be treated as "already dispatched".
    last_cmd = task.last_dispatched_command
    last_dispatch_id = task.last_dispatched_command_id or 0
    if (
        cmd_id
        and cmd_id > 0
        and has_new_user
        and slash_cmd not in ("/skip", "/abort")
        and last_cmd == slash_cmd
        and cmd_id <= last_dispatch_id
    ):
        return Action(kind="noop", slug=task.slug)

    # /skip from terminal state
    if slash_cmd == "/skip" and status != "skipped":
        return Action(
            kind="skip",
            slug=task.slug,
            triggering_comment_id=cmd_id,
        )

    # /abort from terminal state (can't abort already-aborted/skipped, but CAN abort failed/error)
    if slash_cmd == "/abort" and status not in (COMPLETED_STATUSES | {"skipped", "aborted"}):
        return Action(
            kind="abort",
            slug=task.slug,
            triggering_comment_id=cmd_id,
        )

    # New user intent on a restartable command
    if has_new_user and slash_cmd not in ("/skip", "/abort"):
        # Calculate attempt count (used for limit checks and dispatch)
        # Slash commands reset to 1; plain-text replies keep their existing
        # behavior (handled elsewhere, not in this block).
        max_attempts = cfg.get("MAX_ATTEMPTS", 3)
        old_attempt = task.attempt_count
        attempt_count = 1
        if old_attempt != attempt_count:
            log(f"[DECIDE] {task.slug} attempt_count {old_attempt}->{attempt_count} (cmd={slash_cmd}, max={max_attempts})")

        # Guard: max attempts (checked before failed-task gate)
        if attempt_count > max_attempts and not task.guard_blocked:
            log(f"[LIMIT] {task.slug} guard fired: attempt_count={attempt_count} > MAX_ATTEMPTS={max_attempts}, first_dispatched_at={task.first_dispatched_at}")
            return Action(
                kind="mark_failed_limit",
                slug=task.slug,
                attempt_count=attempt_count,
                triggering_comment_id=cmd_id,
                limit_reason="attempts",
            )

        # Guard: time limit (checked before failed-task gate)
        if task.first_dispatched_at and not task.guard_blocked:
            max_total_hours = cfg.get("MAX_TOTAL_HOURS", 2)
            elapsed = _elapsed_hours_since(task.first_dispatched_at)
            if elapsed is not None and elapsed > max_total_hours:
                log(f"[LIMIT] {task.slug} guard fired: elapsed={elapsed:.1f}h > MAX_TOTAL_HOURS={max_total_hours}, first_dispatched_at={task.first_dispatched_at}")
                return Action(
                    kind="mark_failed_limit",
                    slug=task.slug,
                    attempt_count=attempt_count,
                    triggering_comment_id=cmd_id,
                    limit_reason="time",
                )

        # Failed and error issues only restart on explicit /retry
        if status in ("failed", "error") and slash_cmd != "/retry":
            return Action(kind="noop", slug=task.slug)

        plan_branch = branch or task.plan_branch

        kind = _kind_from_command(slash_cmd)
        log(f"[DECIDE] {task.slug} action={kind} attempt={attempt_count} resume_session_id={task.session_id}")
        return Action(
            kind=kind,
            slug=task.slug,
            plan_branch=plan_branch,
            guidance=guidance,
            attempt_count=attempt_count,
            triggering_comment_id=cmd_id,
            resume_session_id=task.session_id,
        )

    return None


# ---------------------------------------------------------------------------
# Main state machine
# ---------------------------------------------------------------------------


def decide(world: World) -> Action:
    """Return the Action for this poll cycle.

    Replaces every transition decision in sync.py and dispatch.py.
    Returns ``Action(kind="noop")`` if nothing should happen.
    """
    task = world.task
    api = world.api
    cfg = world.cfg
    repo_cfg = world.repo_cfg
    comments = api.comments
    bot_name = cfg.get("BOT_NAME", "autoswe")
    auto_dispatch_new = repo_cfg.get("auto_dispatch_new", False)

    # Find the latest slash command
    slash_result, cmd_author, cmd_raw_author, cmd_id = _find_slash_command(
        comments, api.issue.body or "", bot_name, api.issue.creator_login
    )
    slash_cmd, guidance, branch = slash_result if slash_result else (None, None, None)

    # Actor allowlist check
    slash_cmd_suppressed = False
    if slash_cmd and not _is_author_allowed(cmd_author or "", cfg, repo_cfg, cmd_raw_author or ""):
        slash_cmd, guidance, branch = None, None, None
        slash_result = None
        slash_cmd_suppressed = True

    # ------ No slash command ------
    if slash_cmd is None:
        status = task.status

        # auto_dispatch_new: no command, no status, suppress_welcome set
        # Do NOT fire if the only "command" was suppressed by allowlist —
        # an unauthorized user posting a command should not trigger processing.
        if (
            auto_dispatch_new
            and not slash_cmd_suppressed
            and status is None
            and task.suppress_welcome
        ):
            # Check if the issue creator is allowed
            creator = api.issue.creator_login or ""
            if not _is_author_allowed(creator, cfg, repo_cfg, creator):
                log(f"[DECIDE] {task.slug} ignoring: creator={creator} not in allowlist")
                return Action(kind="noop", slug=task.slug, triggering_comment_id=None)
            return Action(
                kind="advance_watermark",
                slug=task.slug,
                triggering_comment_id=None,
            )

        # waiting/planned: look for plain-text user reply
        if status in ("waiting", "planned"):
            last_consumed = task.last_consumed_reply_id or 0
            last_autoswe_id = _find_last_bot_comment_id(comments)

            # Bot detection failed (Azure DevOps failure mode) — skip
            if last_autoswe_id is None and status == "planned":
                return Action(kind="noop", slug=task.slug)

            reply = _has_user_reply_after(comments, last_autoswe_id, last_consumed)
            if reply:
                if not _is_author_allowed(
                    reply.author_login or "", cfg, repo_cfg,
                    getattr(reply, "raw_author_login", ""),
                ):
                    log(f"[DECIDE] {task.slug} reply from {reply.author_login} blocked: not in allowlist")
                    return Action(kind="noop", slug=task.slug)
                # Check if the reply itself contains a slash command
                cmd_result = parse_slash_command(reply.body, bot_name=bot_name)
                if cmd_result and cmd_result[0] not in ("/skip",):
                    # Slash command resets attempt_count to 1
                    new_count = 1
                    log(f"[DECIDE] {task.slug} attempt_count {task.attempt_count}->{new_count} (reply cmd={cmd_result[0]})")
                    return Action(
                        kind=_kind_from_command(cmd_result[0]),
                        slug=task.slug,
                        plan_branch=task.plan_branch,
                        guidance=cmd_result[1],
                        attempt_count=new_count,
                        triggering_comment_id=reply.id,
                        resume_session_id=task.session_id,
                    )
                else:
                    return Action(
                        kind=_resume_kind(task),
                        slug=task.slug,
                        plan_branch=task.plan_branch,
                        user_reply_text=reply.body or "",
                        attempt_count=task.attempt_count,
                        triggering_comment_id=reply.id,
                        resume_session_id=task.session_id,
                    )

        return Action(kind="noop", slug=task.slug)

    # ------ Has a slash command, task NOT in queue ------
    if task.status is None:
        if slash_cmd == "/skip":
            return Action(
                kind="skip",
                slug=task.slug,
                triggering_comment_id=cmd_id,
            )
        if slash_cmd == "/abort":
            return Action(
                kind="abort",
                slug=task.slug,
                triggering_comment_id=cmd_id,
            )
        log(f"[DECIDE] {task.slug} action={_kind_from_command(slash_cmd)} attempt=1 (fresh discovery)")
        return Action(
            kind=_kind_from_command(slash_cmd),
            slug=task.slug,
            plan_branch=branch,
            guidance=guidance,
            attempt_count=1,
            triggering_comment_id=cmd_id,
        )

    # ------ Has a slash command, task exists ------
    status = task.status

    # Terminal state -> restart / guard logic
    if status in TERMINAL_STATUSES:
        action = _check_restart_or_guard(
            world, slash_cmd, guidance, branch, cmd_author, cmd_id
        )
        if action is not None:
            return action

    # planned + slash command
    if status == "planned":
        if slash_cmd == "/skip":
            return Action(
                kind="skip",
                slug=task.slug,
                triggering_comment_id=cmd_id,
            )
        if slash_cmd == "/abort":
            return Action(
                kind="abort",
                slug=task.slug,
                triggering_comment_id=cmd_id,
            )

        if slash_cmd == "/plan":
            # /plan in planned: the plan was already posted.
            # If the /plan has a new branch AND is newer than the last dispatch,
            # re-plan with it. Otherwise noop — the plan is already ready.
            if (
                branch
                and branch != task.plan_branch
                and (cmd_id or 0) > (task.last_dispatched_command_id or 0)
            ):
                # Slash command resets attempt_count to 1
                new_count = 1
                log(f"[DECIDE] {task.slug} attempt_count {task.attempt_count}->{new_count} (re-plan branch={branch})")
                return Action(
                    kind="plan",
                    slug=task.slug,
                    plan_branch=branch,
                    guidance=guidance,
                    attempt_count=new_count,
                    triggering_comment_id=cmd_id,
                    resume_session_id=task.session_id,
                )
            # No branch change — check if there's a plain-text reply
            last_bot_id = _find_last_bot_comment_id(comments)
            if last_bot_id is None:
                return Action(kind="noop", slug=task.slug)
            reply = _has_user_reply_after(comments, last_bot_id, task.last_consumed_reply_id or 0)
            if reply is None or parse_slash_command(reply.body, bot_name=bot_name):
                return Action(kind="noop", slug=task.slug)
            if not _is_author_allowed(
                reply.author_login or "", cfg, repo_cfg,
                getattr(reply, "raw_author_login", ""),
            ):
                log(f"[DECIDE] {task.slug} reply from {reply.author_login} blocked: not in allowlist")
                return Action(kind="noop", slug=task.slug)
            return Action(
                kind=_resume_kind(task),
                slug=task.slug,
                plan_branch=task.plan_branch,
                user_reply_text=reply.body or "",
                attempt_count=task.attempt_count,
                triggering_comment_id=reply.id,
                resume_session_id=task.session_id,
            )

        else:
            last_bot_id = _find_last_bot_comment_id(comments)
            if last_bot_id is not None and isinstance(last_bot_id, int):
                # IDs available — check if this command was already dispatched
                if (cmd_id or 0) <= last_bot_id:
                    # Stale command — already acted on, fall through to reply detector
                    pass
                else:
                    # New command from planned — dispatch it
                    plan_branch = branch or task.plan_branch
                    old_attempt = task.attempt_count
                    # Slash command resets attempt_count to 1
                    attempt_count = 1
                    log(f"[DECIDE] {task.slug} attempt_count {old_attempt}->{attempt_count} (cmd={slash_cmd} from planned)")

                    if attempt_count > cfg.get("MAX_ATTEMPTS", 3):
                        log(f"[LIMIT] {task.slug} guard fired: attempt_count={attempt_count} > MAX_ATTEMPTS={cfg.get('MAX_ATTEMPTS', 3)}")
                        return Action(
                            kind="mark_failed_limit",
                            slug=task.slug,
                            attempt_count=attempt_count,
                            triggering_comment_id=cmd_id,
                            limit_reason="attempts",
                        )

                    return Action(
                        kind=_kind_from_command(slash_cmd),
                        slug=task.slug,
                        plan_branch=plan_branch,
                        guidance=guidance,
                        attempt_count=attempt_count,
                        triggering_comment_id=cmd_id,
                        resume_session_id=task.session_id,
                    )

    # waiting/planned -> check for user reply (also covers planned + /plan fallback)
    if status in ("waiting", "planned"):
        last_consumed = task.last_consumed_reply_id or 0
        last_autoswe_id = _find_last_bot_comment_id(comments)

        if last_autoswe_id is None and status == "planned":
            return Action(kind="noop", slug=task.slug)

        reply = _has_user_reply_after(comments, last_autoswe_id, last_consumed)
        if reply:
            if not _is_author_allowed(
                reply.author_login or "", cfg, repo_cfg,
                getattr(reply, "raw_author_login", ""),
            ):
                log(f"[DECIDE] {task.slug} reply from {reply.author_login} blocked: not in allowlist")
                return Action(kind="noop", slug=task.slug)
            cmd_result = parse_slash_command(reply.body, bot_name=bot_name)
            if cmd_result and cmd_result[0] not in ("/skip",):
                reply_branch = cmd_result[2] if len(cmd_result) > 2 else None
                # Use branch from the reply command; falls back to task plan_branch
                plan_branch = reply_branch or task.plan_branch
                # Slash command resets attempt_count to 1
                new_count = 1
                log(f"[DECIDE] {task.slug} attempt_count {task.attempt_count}->{new_count} (reply cmd={cmd_result[0]})")
                return Action(
                    kind=_kind_from_command(cmd_result[0]),
                    slug=task.slug,
                    plan_branch=plan_branch,
                    guidance=cmd_result[1],
                    attempt_count=new_count,
                    triggering_comment_id=reply.id,
                    resume_session_id=task.session_id,
                )
            else:
                return Action(
                    kind=_resume_kind(task),
                    slug=task.slug,
                    plan_branch=task.plan_branch,
                    user_reply_text=reply.body or "",
                    attempt_count=task.attempt_count,
                    triggering_comment_id=reply.id,
                    resume_session_id=task.session_id,
                )

        return Action(kind="noop", slug=task.slug)

    # Existing task with slash command but no status -> discover
    if status is None:
        if slash_cmd == "/skip":
            return Action(
                kind="skip",
                slug=task.slug,
                triggering_comment_id=cmd_id,
            )
        if slash_cmd == "/abort":
            return Action(
                kind="abort",
                slug=task.slug,
                triggering_comment_id=cmd_id,
            )
        # Slash command resets attempt_count to 1
        attempt_count = 1
        log(f"[DECIDE] {task.slug} action={_kind_from_command(slash_cmd)} attempt={attempt_count} (fresh discovery)")
        return Action(
            kind=_kind_from_command(slash_cmd),
            slug=task.slug,
            plan_branch=task.plan_branch or branch,
            guidance=guidance,
            attempt_count=attempt_count,
            triggering_comment_id=cmd_id,
            resume_session_id=task.session_id,
        )

    # RUNNING state with new command
    if status in RUNNING_STATUSES:
        # Already running — don't interrupt
        return Action(kind="noop", slug=task.slug)

    # Pending state — dispatch will handle it
    if status == "pending":
        return Action(
            kind=_kind_from_command(slash_cmd),
            slug=task.slug,
            plan_branch=task.plan_branch or branch,
            guidance=guidance,
            attempt_count=task.attempt_count or 1,
            triggering_comment_id=cmd_id,
            resume_session_id=task.session_id,
        )

    return Action(kind="noop", slug=task.slug)


def _resume_kind(task: "object") -> str:  # type: ignore[type-arg]  # noqa: ANN001
    """Determine the action kind for a user reply resume.

    If the last phase was 'fix', resume the fix. Otherwise resume plan.
    """
    if task.last_phase == "fix":
        return "fix"
    return "plan"
