"""GitHub provider adapter for the orchestrator.

Provides ``read_api`` (raw API -> ApiState) and ``apply_effect`` (Effect -> API call)
so the orchestrator can stay provider-agnostic.
"""
from __future__ import annotations

from autoswe.core.config import LOGS_DIR
from autoswe.core.logging_utils import init_debug_logger
from autoswe.orch.types import ApiState, Effect
from autoswe.providers.base import IssueTracker, NormalizedComment
from autoswe.providers.factory import get_vcs
from autoswe.providers.github.vcs import MissingScopeError
from autoswe.vcs.worktree import get_remote_branch_sha

dbg = init_debug_logger(LOGS_DIR)


def read_api(
    tracker: IssueTracker,
    repo_cfg: dict,
    cfg: dict,
    bot_ids: set[int] | None = None,
    prev_updated: dict[int, str | None] | None = None,
    force_fetch: set[int] | None = None,
) -> dict[int, ApiState]:
    """Fetch all open issues and their comments, returning an ApiState per issue number.

    Comments are already normalized by the GitHub tracker (no HTML wrapping,
    plain text bodies). The tracker returns clean text directly.

    ``bot_ids`` is the set of comment IDs we've posted (from queue bot_comment_ids).
    Used to set the is_bot flag on comments.

    ``prev_updated`` maps issue_number -> stored ``last_updated`` timestamp from
    the queue.  ``force_fetch`` is a set of issue numbers that must always fetch
    comments regardless of timestamp matching.

    When an issue's ``last_updated`` matches its stored value, the comment fetch
    is skipped and ``comments_fetched=False`` is set on the returned ApiState.
    """
    bot_ids = bot_ids or set()
    prev_updated = prev_updated or {}
    force_fetch = force_fetch or set()

    issues = tracker.list_open_issues(repo_cfg)
    open_prs = get_vcs(repo_cfg).find_existing_pr(repo_cfg, "") or None

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
                is_bot = c.id in bot_ids or c.author_login == "BOT"
                comments.append(
                    NormalizedComment(
                        body=c.body,
                        created_at=c.created_at,
                        author_login=c.author_login,
                        raw_author_login=c.raw_author_login,
                        id=c.id,
                        is_bot=is_bot,
                    )
                )
        else:
            comments = []

        pr_numbers: tuple[int, ...] = ()
        if open_prs:
            pr_numbers = (open_prs.number,) if open_prs.number else ()

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
    """Translate a single Effect into GitHub API calls."""
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
            # Enrich PR body if it only contains the bare "Fixes #N" text
            body = effect.pr_body or ""
            task_entry = queue.get(slug)
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
            pr_result = vcs.open_pull_request(
                repo_cfg,
                branch=branch,
                base=effect.pr_base or "main",
                title=effect.pr_title or "",
                body=body,
            )
            # Best-effort: link branch to issue in platform UI
            _try_link_branch_to_issue(vcs, repo_cfg, issue_num, branch,
                                     pr_head_sha=pr_result.head_sha)


def _try_link_branch_to_issue(vcs, repo_cfg: dict, issue_num: int, branch: str,
                              pr_head_sha: str | None = None) -> None:
    """Best-effort link branch to issue after PR creation (adapter path).

    When *pr_head_sha* is provided it is used as a fallback when the remote
    branch SHA cannot be fetched (e.g. the branch has not yet been pushed,
    or *git ls-remote* fails).

    Matches the error-handling pattern used in ship.py and coder.py:
    MissingScopeError is caught explicitly (PAT may lack check_runs scope),
    all other exceptions are logged at warning level.
    """
    owner = repo_cfg.get("owner", "")
    repo = repo_cfg.get("repo", "")
    token = repo_cfg.get("pat", "") or repo_cfg.get("token", "")
    provider = repo_cfg.get("provider", "github")
    if not owner or not repo:
        return
    commit_sha = get_remote_branch_sha(owner, repo, branch, token, provider)
    if not commit_sha and pr_head_sha:
        dbg.info("ADAPTER: using PR head_sha as fallback for branch linking")
        commit_sha = pr_head_sha
    if not commit_sha:
        dbg.warning("ADAPTER: cannot link branch — no commit SHA available")
        return
    try:
        vcs.link_branch_to_issue(issue_num, commit_sha, branch)
    except MissingScopeError:
        dbg.warning("ADAPTER: link_branch_to_issue skipped — PAT missing check_runs:write scope")
    except Exception as e:
        dbg.warning("link_branch_to_issue failed in adapter: %s", e, exc_info=True)
