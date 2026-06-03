import contextlib
from urllib.parse import urlparse

from autoswe.core.config import LOGS_DIR
from autoswe.core.logging_utils import init_debug_logger, log
from autoswe.providers.base import PRResult
from autoswe.providers.factory import get_tracker, get_vcs
from autoswe.providers.github.vcs import MissingScopeError
from autoswe.vcs.worktree import get_remote_branch_sha

dbg = init_debug_logger(LOGS_DIR)

AUTOSWE_BOT_FOOTER = "\n<!-- autoswe-bot -->"


def _try_link_branch(
    vcs,
    owner: str,
    repo: str,
    issue_num: int,
    branch: str,
    token: str,
    cfg: dict,
    provider: str = "github",
    pr_result: PRResult | None = None,
) -> None:
    """Best-effort link branch to issue (same pattern as _finalize_fix).

    When *pr_result* is provided and its *head_sha* is set, it is used as a
    fallback when the remote branch SHA cannot be fetched (e.g. the branch
    has not yet been pushed, or *git ls-remote* fails).
    """
    if not cfg.get("LINK_BRANCH_TO_ISSUE", True):
        return
    commit_sha = get_remote_branch_sha(owner, repo, branch, token, provider)
    if not commit_sha and pr_result is not None and pr_result.head_sha:
        dbg.info("SHIP: using PR head_sha as fallback for branch linking")
        commit_sha = pr_result.head_sha
    if not commit_sha:
        dbg.warning("SHIP: cannot link branch — no commit SHA available")
        return
    try:
        vcs.link_branch_to_issue(issue_num, commit_sha, branch)
    except MissingScopeError:
        dbg.warning("SHIP: link_branch_to_issue skipped — PAT missing check_runs:write scope")
    except Exception as e:
        dbg.warning("link_branch_to_issue failed in ship: %s", e, exc_info=True)


def _pr_ref(pr_url: str) -> str:
    """Extract a redacted PR reference from a URL for safe log output.

    Avoids logging full PR URLs (which expose repo paths, branch names,
    and internal automation patterns) to plain text log files.
    """
    # Handle "#123" format — prefix with "PR" for consistency
    if pr_url.startswith("#"):
        return "PR" + pr_url
    # Try to extract PR number from common URL patterns
    parsed = urlparse(pr_url)
    path = parsed.path
    # GitHub: /{owner}/{repo}/pull/{number}
    # Azure: /{org}/{project}/_git/{repo}/pullrequest/{number}
    parts = path.strip("/").split("/")
    for idx, part in enumerate(parts):
        if part in ("pull", "pullrequest") and idx + 1 < len(parts):
            return f"PR#{parts[idx + 1]}"
    # Fallback: last non-empty path segment, then full URL
    last = next((p for p in reversed(parts) if p), pr_url)
    return f"PR#{last}"


def open_pr(task: dict, cfg: dict, repo_cfg: dict | None = None) -> str:
    """Open a PR from the worktree branch. Returns done-file content."""
    owner, repo, issue_num = task["owner"], task["repo"], task["issue_number"]
    token = task["_token"]
    base_branch = task.get("plan_branch") or task.get("base_branch", "main")
    branch = f"autoswe/issue-{issue_num}"
    title = task.get("title", f"Fix issue #{issue_num}")

    rcfg = repo_cfg or {"owner": owner, "repo": repo, "token": token}
    if "token" not in rcfg:
        rcfg["token"] = token
    if "owner" not in rcfg:
        rcfg["owner"] = owner
    if "repo" not in rcfg:
        rcfg["repo"] = repo
    vcs = get_vcs(rcfg)
    tracker = get_tracker(rcfg)

    dbg.debug("SHIP: branch=%s base=%s", branch, base_branch)

    # Build informative PR body from task data
    fix_summary = task.get("fix_summary", "") or ""
    issue_body = task.get("body", "") or ""
    body_parts = [f"Fixes #{issue_num}"]
    if issue_body:
        body_parts.append(f"**Issue:**\n\n{issue_body}")
    if fix_summary:
        body_parts.append(f"**Fix Summary:**\n\n{fix_summary}")
    body_parts.append("\nOpened by autoSWE.")
    pr_body = "\n\n".join(body_parts)

    # Idempotency: check if a PR already exists for this branch
    existing = vcs.find_existing_pr(rcfg, branch)
    if existing is not None:
        pr_url = existing.url or f"#{existing.number}"
        pr_ref = _pr_ref(pr_url)
        dbg.debug("SHIP: pr_url=%s", pr_url)
        log(f"[SHIP] PR already exists: {pr_ref} base={base_branch} head={branch}")
        with contextlib.suppress(Exception):
            tracker.post_comment(rcfg, issue_num,
                f"Pull request already exists: {pr_url}{AUTOSWE_BOT_FOOTER}")
        # Best-effort: link branch to issue
        provider = rcfg.get("provider", "github")
        _try_link_branch(vcs, owner, repo, issue_num, branch, token, cfg, provider)
        return f"DONE: PR {pr_url}"

    try:
        pr_result: PRResult = vcs.open_pull_request(
            rcfg,
            branch=branch,
            base=base_branch,
            title=f"Fixes #{issue_num}: {title}",
            body=pr_body,
        )
        pr_url = pr_result.url
        pr_ref = _pr_ref(pr_url)
        dbg.debug("SHIP: pr_url=%s", pr_url)
        log(f"[SHIP] PR created: {pr_ref} base={base_branch} head={branch}")
        with contextlib.suppress(Exception):
            tracker.post_comment(rcfg, issue_num,
               "Pull request opened: " + pr_url + AUTOSWE_BOT_FOOTER)
        # Best-effort: link branch to issue (pass pr_result for head_sha fallback)
        provider = rcfg.get("provider", "github")
        _try_link_branch(vcs, owner, repo, issue_num, branch, token, cfg, provider,
                         pr_result=pr_result)
        return f"DONE: PR {pr_url}"
    except Exception as e:
        dbg.error("open_pr: failed: %s", e, exc_info=True)
        return f"FAILED: could not create PR: {e}"
