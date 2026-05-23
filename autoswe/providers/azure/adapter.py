"""Azure DevOps provider adapter for the orchestrator.

Provides ``read_api`` (raw API -> ApiState) and ``apply_effect`` (Effect -> API call).

Critical fix for Bug 1: ``read_api`` strips HTML from **all** comments (not just
bot comments). Azure DevOps wraps rich-text user comments in ``<div>`` tags,
which broke slash-command parsing when the command text was inside the tags.
"""
from __future__ import annotations

import html

from autoswe.orch.types import ApiState, Effect
from autoswe.providers.azure.tracker import _strip_html
from autoswe.providers.base import IssueTracker, NormalizedComment
from autoswe.providers.factory import get_vcs
from autoswe.tracking.comments import BOT_MARKER


def _normalize_comment_body(body: str) -> str:
    """Normalize a comment body: decode entities, strip HTML tags.

    Strips HTML tags from all comments. Azure DevOps rich-text wraps user
    comments in ``<div>`` tags, and the tracker already strips HTML for bot
    comments. ``_strip_html`` is idempotent — safe to run on already-clean text.

    This is the structural fix for Bug 1 (branch lost in rich-text comment).
    """
    # Always decode HTML entities first (&#45; -> -, &amp; -> &, etc.)
    text = html.unescape(body or "")
    text = _strip_html(text)
    return text


def read_api(
    tracker: IssueTracker,
    repo_cfg: dict,
    cfg: dict,
    bot_ids: set[int] | None = None,
    prev_updated: dict[int, str | None] | None = None,
    force_fetch: set[int] | None = None,
) -> dict[int, ApiState]:
    """Fetch all open issues and their comments, returning an ApiState per issue number.

    Critical: strips HTML from **all** comment bodies (user and bot) so that
    slash-command parsing sees clean text. Fixes Bug 1 — branch lost in
    rich-text Azure DevOps comment wrapped in ``<div>``.

    ``bot_ids`` is the set of comment IDs we've posted (from queue bot_comment_ids).
    Used to set the is_bot flag on comments.

    ``prev_updated`` maps issue_number -> stored ``last_updated`` timestamp from
    the queue.  ``force_fetch`` is a set of issue numbers that must always fetch
    comments regardless of timestamp matching.

    When an issue's ``last_updated`` matches its stored value, the comment fetch
    is skipped and ``comments_fetched=False`` is set on the returned ApiState.
    """
    from autoswe.providers.azure.tracker import _is_bot_comment

    bot_ids = bot_ids or set()
    prev_updated = prev_updated or {}
    force_fetch = force_fetch or set()

    issues = tracker.list_open_issues(repo_cfg)

    # PR discovery per-issue happens at dispatch time; read_api just builds
    # the ApiState. The orchestrator fills in open_pr_numbers later.
    pr_numbers: tuple[int, ...] = ()

    result: dict[int, ApiState] = {}
    for issue in issues:
        num = issue.number

        # Skip rule: fetch comments iff any of:
        # - issue is new (not in prev_updated)
        # - issue is force-fetched
        # - no stored timestamp or provider gave no timestamp
        # - timestamp changed
        stored = prev_updated.get(num)
        current = issue.last_updated
        should_fetch = (
            num not in prev_updated
            or num in force_fetch
            or stored is None
            or current is None
            or current != stored
        )

        if should_fetch:
            raw_comments = tracker.fetch_comments(repo_cfg, num)
            comments: list[NormalizedComment] = []

            for c in raw_comments:
                is_bot = c.id in bot_ids or c.author_login == "BOT" or _is_bot_comment(c.body)
                body = _normalize_comment_body(c.body)

                if is_bot and not body.endswith(BOT_MARKER):
                    body = body.rstrip() + BOT_MARKER

                comments.append(
                    NormalizedComment(
                        body=body,
                        created_at=c.created_at,
                        author_login=c.author_login,
                        id=c.id,
                        is_bot=is_bot,
                    )
                )
        else:
            comments = []

        result[num] = ApiState(
            issue=issue,
            comments=tuple(comments),
            open_pr_numbers=pr_numbers,
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
) -> None:
    """Translate a single Effect into Azure DevOps API calls."""
    if effect.kind == "post_comment":
        comment_id = tracker.post_comment(repo_cfg, issue_num, effect.body or "")
        if comment_id:
            task = queue.get(slug)
            if task:
                task.setdefault("bot_comment_ids", []).append(comment_id)
    elif effect.kind == "update_comment":
        if effect.comment_id:
            tracker.update_comment(repo_cfg, issue_num, effect.comment_id, effect.body or "")
    elif effect.kind == "set_status":
        tracker.set_status(repo_cfg, issue_num, f"autoswe:{effect.status}")
    elif effect.kind == "patch_queue":
        if effect.queue_patch:
            task = queue.get(slug)
            if task:
                task.update(effect.queue_patch)
    elif effect.kind == "assign":
        login = effect.body
        if login:
            tracker.assign_to_user(repo_cfg, issue_num, login)
    elif effect.kind == "create_pr":
        vcs = get_vcs(repo_cfg)
        branch = effect.pr_head or ""
        existing = vcs.find_existing_pr(repo_cfg, branch)
        if existing is None:
            vcs.open_pull_request(
                repo_cfg,
                branch=branch,
                base=effect.pr_base or "main",
                title=effect.pr_title or "",
                body=effect.pr_body or "",
            )
