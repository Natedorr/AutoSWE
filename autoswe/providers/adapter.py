"""Provider adapter — the single ``read_api`` / ``apply_effect`` pair.

The write path is provider-agnostic: an ``Effect`` only ever calls
``tracker.*`` and ``vcs.*`` protocol methods, so there is one
``apply_effect`` for every provider. ``read_api`` is likewise shared; its only
provider-specific behaviour is comment-body normalisation, which is delegated
to ``tracker.normalize_comment_body`` (GitHub: identity; Azure: HTML/entity
stripping + content-based bot detection).

Adding a third provider therefore costs one tracker/vcs pair (each providing
the ``normalize_comment_body`` hook) plus one registry entry — nothing else.
"""
from __future__ import annotations

import contextlib
from dataclasses import asdict
from datetime import datetime, timezone

from autoswe.core.config import resolve_flag
from autoswe.core.logging_utils import get_debug_logger
from autoswe.orch.types import ApiState, Effect
from autoswe.providers.base import CIStatus, IssueTracker, NormalizedComment, VCSProvider
from autoswe.providers.factory import get_vcs
from autoswe.tracking.comments import BOT_MARKER, record_bot_comment_id
from autoswe.tracking.labels import CI_WATCH_STATUSES
from autoswe.vcs.linkage import ensure_links
from autoswe.vcs.pr_gate import preflight_pr

dbg = get_debug_logger()


def _ci_poll_interval_sec(cfg: dict, repo_cfg: dict) -> int:
    """Resolve CI_POLL_INTERVAL_SEC: a per-repo override beats cfg."""
    for source in (repo_cfg.get("ci_poll_interval_sec"), cfg.get("CI_POLL_INTERVAL_SEC")):
        if source is None:
            continue
        try:
            return int(source)
        except (TypeError, ValueError):
            continue
    return 120


def read_ci(
    vcs: VCSProvider,
    task_entry: dict,
    cfg: dict,
    repo_cfg: dict,
    *,
    now: datetime | None = None,
) -> CIStatus | None:
    """Read CI status for one watched task — report-only (issue #245 plan §2.2).

    Eligible only when ``autoswe_status`` is in ``CI_WATCH_STATUSES`` and a
    branch can be resolved for the task, and only when ``CI_WATCH`` is on
    (cfg, per-repo override). Throttled by ``CI_POLL_INTERVAL_SEC`` against
    the persisted ``ci_last_checked`` watermark on *task_entry*, so a
    ``--drain`` loop makes at most one API call per watched task per
    interval.

    On an actual read, caches the result on *task_entry* as ``ci_status``
    (a dict) and refreshes ``ci_last_checked``, so ``/sync`` and
    ``queue status`` can render the last-known state even on cycles that
    don't re-consult the API.

    Returns ``None`` when CI was NOT consulted this cycle (ineligible,
    disabled, or throttled) — a distinct, checkable state from an actual
    ``CIStatus`` (mirrors the ``comments_fetched`` idiom). Never makes a
    decision; ``decide()`` does not consume this value yet.
    """
    if not resolve_flag("CI_WATCH", cfg, repo_cfg, default=True):
        return None
    if task_entry.get("autoswe_status") not in CI_WATCH_STATUSES:
        return None

    branch = task_entry.get("plan_branch")
    if not branch:
        try:
            branch = vcs.branch_name(task_entry["issue_number"])
        except Exception:
            return None
    if not branch:
        return None

    now = now or datetime.now(timezone.utc)
    last_checked = task_entry.get("ci_last_checked")
    if last_checked:
        try:
            last_dt = datetime.fromisoformat(str(last_checked).replace("Z", "+00:00"))
            elapsed = (now - last_dt).total_seconds()
        except ValueError:
            elapsed = None  # malformed watermark -> treat as due
        if elapsed is not None and elapsed < _ci_poll_interval_sec(cfg, repo_cfg):
            return None

    try:
        status = vcs.get_ci_status(branch)
    except Exception as e:  # defensive — providers already fail-safe internally
        dbg.warning("read_ci: %s: get_ci_status failed: %s", task_entry.get("id", branch), e)
        return None

    task_entry["ci_last_checked"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    task_entry["ci_status"] = asdict(status)
    return status


def render_ci_status(task: dict) -> str:
    """Human-readable CI-watch summary for a task (issue #245 plan §2.2).

    Rendered from the cached ``ci_status`` / ``ci_last_checked`` fields that
    ``read_ci`` persists — the last observation made, which may predate the
    current cycle when throttled or when the task isn't currently eligible.
    Report-only: no status changes or decisions are implied. Returns ``""``
    when CI has never been consulted for this task.
    """
    status = task.get("ci_status")
    if not isinstance(status, dict):
        return ""
    lines = [f"CI watch: {status.get('state', 'unknown')}"]
    if status.get("stale"):
        lines[0] += " (stale)"
    if status.get("summary"):
        lines.append(f"  {status['summary']}")
    if status.get("url"):
        lines.append(f"  {status['url']}")
    if task.get("ci_last_checked"):
        lines.append(f"  last checked: {task['ci_last_checked']}")
    return "\n".join(lines)


def read_api(
    tracker: IssueTracker,
    bot_ids: set[int] | None = None,
    prev_updated: dict[int, str | None] | None = None,
    force_fetch: set[int] | None = None,
) -> dict[int, ApiState]:
    """Fetch all open issues and their comments, returning an ApiState per issue.

    Provider-specific comment normalisation is delegated to
    ``tracker.normalize_comment_body`` so the read path stays single-sourced.

    ``bot_ids`` is the set of comment IDs we've posted (from queue
    bot_comment_ids). Used to set the is_bot flag on comments.

    ``prev_updated`` maps issue_number -> stored ``last_updated`` timestamp from
    the queue.  ``force_fetch`` is a set of issue numbers that must always fetch
    comments regardless of timestamp matching.

    When an issue's ``last_updated`` matches its stored value, the comment fetch
    is skipped and ``comments_fetched=False`` is set on the returned ApiState.
    """
    bot_ids = bot_ids or set()
    prev_updated = prev_updated or {}
    force_fetch = force_fetch or set()

    # Whether the provider advances the issue's updated timestamp when a
    # comment is posted.  The "unchanged timestamp -> skip" shortcut below is
    # only sound when that is true (GitHub: a comment bumps `updated_at`).  On
    # Azure DevOps a comment does NOT bump `System.ChangedDate`, so relying on
    # it means a user's new `/fix`/`/pr` is never re-fetched and the poller
    # stalls (issue: comments not seen after autoSWE's own tag write advanced
    # the stored timestamp).  Providers without the capability default to True
    # so the GitHub fast path is unchanged.
    comments_bump = getattr(tracker, "comments_bump_updated", True)

    issues = tracker.list_open_issues()

    result: dict[int, ApiState] = {}
    for issue in issues:
        num = issue.number

        # Skip rule: fetch comments iff any of:
        # - issue is new (not in prev_updated)
        # - issue is force-fetched
        # - no stored timestamp or provider gave no timestamp
        # - timestamp changed
        # - provider doesn't bump the timestamp on comments (Azure) — the
        #   timestamp can't signal a new comment, so always re-fetch
        stored = prev_updated.get(num)
        current = issue.last_updated
        should_fetch = (
            num not in prev_updated
            or num in force_fetch
            or stored is None
            or current is None
            or current != stored
            or not comments_bump
        )

        if should_fetch:
            raw_comments = tracker.fetch_comments(num)
            comments: list[NormalizedComment] = []
            for c in raw_comments:
                is_bot = c.id in bot_ids or c.author_login == "BOT"
                body, provider_is_bot = tracker.normalize_comment_body(c)
                is_bot = is_bot or provider_is_bot

                # Ensure the marker is present on bot comments so downstream
                # marker-based detection keeps working after normalisation
                # (Azure DevOps strips HTML comments from rendered bodies).
                if is_bot and not body.endswith(BOT_MARKER):
                    body = body.rstrip() + BOT_MARKER

                comments.append(
                    NormalizedComment(
                        body=body,
                        created_at=c.created_at,
                        author_login=c.author_login,
                        raw_author_login=c.raw_author_login,
                        id=c.id,
                        is_bot=is_bot,
                    )
                )
        else:
            comments = []

        result[num] = ApiState(
            issue=issue,
            comments=tuple(comments),
            comments_fetched=should_fetch,
        )
    return result


def apply_effect(
    tracker: IssueTracker,
    effect: Effect,
    repo_cfg: dict,
    issue_num: int,
    queue: dict,
    slug: str,
    cfg: dict | None = None,
) -> None:
    """Translate a single Effect into provider API calls.

    Provider-agnostic: only ``tracker.*`` / ``vcs.*`` protocol methods are
    called. Azure DevOps has no Development-section equivalent —
    ``AzureVCS.link_branch_to_issue()`` is a documented no-op, so nothing here
    branches on provider.
    """
    if effect.kind == "post_comment":
        comment_id = tracker.post_comment(issue_num, effect.body or "")
        if comment_id:
            task = queue.get(slug)
            if task:
                record_bot_comment_id(task, comment_id)
    elif effect.kind == "update_comment":
        if effect.comment_id:
            tracker.update_comment(issue_num, effect.comment_id, effect.body or "")
    elif effect.kind == "set_status":
        tracker.set_status(issue_num, f"autoswe:{effect.status}")
    elif effect.kind == "patch_queue":
        if effect.queue_patch:
            task = queue.get(slug)
            if task:
                task.update(effect.queue_patch)
    elif effect.kind == "assign":
        login = effect.body
        if login:
            tracker.assign_to_user(issue_num, login)
    elif effect.kind == "create_pr":
        vcs = get_vcs(repo_cfg)
        branch = effect.pr_head or ""
        task_entry = queue.get(slug)
        if cfg is not None and task_entry is not None:
            ok, reason = preflight_pr(task_entry, cfg, repo_cfg, do_sync=False, vcs=vcs)
            if not ok:
                # pr_deferred (issue #245 §2.6): record it on the task instead
                # of asking the human to re-post /pr — the next green CI
                # observation re-emits this create_pr effect (decide()'s
                # retry_deferred_pr row), and find_existing_pr below already
                # makes that re-emit idempotent.
                task_entry["pr_deferred"] = True
                with contextlib.suppress(Exception):
                    comment_id = tracker.post_comment(
                        issue_num,
                        f"PR deferred — {reason}. Will retry automatically once CI is green.{BOT_MARKER}",
                    )
                    record_bot_comment_id(task_entry, comment_id)
                return
        existing = vcs.find_existing_pr(branch)
        if existing is None:
            # Enrich PR body if it only contains the bare "Fixes #N" text
            body = effect.pr_body or ""
            if task_entry and not body:
                body = f"Fixes #{issue_num}"
            elif task_entry and body == f"Fixes #{issue_num}":
                # Backwards compat: old emit code produced bare body.
                # Rebuild from queue entry data if available.
                issue_body = task_entry.get("body", "") or ""
                fix_summary = task_entry.get("fix_summary", "") or ""
                body_parts = [f"Fixes #{issue_num}"]
                if issue_body:
                    body_parts.append(f"**Issue:**\n\n{issue_body}")
                if fix_summary:
                    body_parts.append(f"**Fix Summary:**\n\n{fix_summary}")
                body_parts.append("\nOpened by autoSWE.")
                body = "\n\n".join(body_parts)
            pr = vcs.open_pull_request(
                branch=branch,
                base=effect.pr_base or "main",
                title=effect.pr_title or "",
                body=body,
            )
            if task_entry is not None and pr is not None:
                # Persist the PR identity in the same cycle that created it
                # (issue #193) — the patch_queue effect already advanced the
                # status; this write lands in the same queue dict and is
                # saved by the cycle's save_queue().
                if pr.number is not None:
                    task_entry["pr_number"] = pr.number
                if pr.url:
                    task_entry["pr_url"] = pr.url
            if task_entry is not None:
                with contextlib.suppress(Exception):
                    ensure_links(task_entry, repo_cfg, cfg, phase="pr_open", vcs=vcs)
        elif task_entry is not None:
            # Idempotent skip: the PR already exists but the queue entry lost
            # its cached identity (e.g. a crash between create and save).
            # Re-cache it so consumers see pr_number without re-querying.
            if existing.number is not None:
                task_entry["pr_number"] = existing.number
            if existing.url:
                task_entry["pr_url"] = existing.url
            with contextlib.suppress(Exception):
                ensure_links(task_entry, repo_cfg, cfg, phase="pr_open", vcs=vcs)
