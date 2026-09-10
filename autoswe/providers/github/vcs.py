"""GitHub VCSProvider — wraps existing autoswe.vcs modules."""
from __future__ import annotations

import json
import re
import subprocess

from autoswe.core.constants import GIT_TEXT_ARGS
from autoswe.core.logging_utils import get_debug_logger
from autoswe.core.redact import redact_outbound
from autoswe.providers.base import CIStatus, Capability, LinkageState, PRResult
from autoswe.tracking.api import gh_get, gh_post

dbg = get_debug_logger()

# check-run/status conclusions that block a PR vs. that count as a pass
_FAILURE_CONCLUSIONS = {"failure", "cancelled", "timed_out", "action_required"}
_SUCCESS_CONCLUSIONS = {"success", "neutral", "skipped"}

# GitHub declares every capability it can read/write: the branch link is the
# GraphQL createLinkedBranch mutation, the PR<->issue link is the closing
# keyword in the body, auto-close rides that same keyword, and CI / merge
# status are read from the checks API + PR payload.
_GITHUB_VCS_CAPS = frozenset(
    {
        Capability.BRANCH_LINK,
        Capability.PR_ISSUE_LINK,
        Capability.AUTO_CLOSE_ON_MERGE,
        Capability.CI_PER_COMMIT,
        Capability.CI_LOGS,
        Capability.MERGE_STATUS,
    }
)


def _issue_refs_in_body(body: str, issue_number: int) -> tuple[bool, bool]:
    """Inspect a PR body for references to *issue_number*.

    Returns ``(linked, closes)`` where:
    - *linked* is True if any association keyword references the issue
      (``refs`` / ``fixes`` / ``closes`` / ``resolves``) → ``pr_linked``;
    - *closes* is True if a *closing* keyword does → ``closes_on_merge``.

    GitHub auto-links on any keyword and auto-closes on a closing one; the
    keyword must sit at a word boundary and reference the exact issue number
    (case-insensitive, matching GitHub's own matching).
    """
    if not body:
        return False, False
    num = str(issue_number)
    if re.search(rf"\bfixes\s+#{num}\b", body, re.IGNORECASE) or \
       re.search(rf"\bcloses\s+#{num}\b", body, re.IGNORECASE) or \
       re.search(rf"\bresolves\s+#{num}\b", body, re.IGNORECASE):
        return True, True
    if re.search(rf"\brefs\s+#{num}\b", body, re.IGNORECASE):
        return True, False
    return False, False


class MissingScopeError(RuntimeError):
    """Raised when a GitHub API call fails due to missing PAT scopes."""


class GitHubVCS:
    """GitHub-backed VCS provider."""

    def __init__(self, repo_cfg: dict):
        self._repo_cfg = repo_cfg
        self._owner = repo_cfg.get("owner", "")
        self._repo = repo_cfg.get("repo", "")
        self._token = repo_cfg.get("pat", "") or repo_cfg.get("token", "")

    # ---- Protocol: VCSProvider ----

    def clone_url(self) -> str:
        """Return the full HTTPS clone URL with embedded token."""
        return f"https://x-access-token:{self._token}@github.com/{self._owner}/{self._repo}.git"

    def branch_name(self, issue_number: int) -> str:
        """Return the branch name for an issue."""
        return f"autoswe/issue-{issue_number}"

    def find_existing_pr(self, branch: str) -> PRResult | None:
        """Check if a PR for the branch already exists."""
        try:
            result = subprocess.run(
                ["gh", "pr", "list", "--repo", f"{self._owner}/{self._repo}",
                 "--head", branch, "--json", "number,url", "--limit", "1"],
                capture_output=True, text=True, timeout=30, **GIT_TEXT_ARGS,
            )
            if result.returncode != 0:
                pass  # fall through to API
            else:
                prs = json.loads(result.stdout or "[]")
                if prs:
                    return PRResult(number=prs[0]["number"], url=prs[0]["url"])
                return None
        except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
            pass  # fall through to API

        # API fallback when gh CLI is unavailable
        try:
            prs = gh_get(
                f"/repos/{self._owner}/{self._repo}/pulls?head={self._owner}:{branch}&state=open",
                self._token,
                max_retries=1,
            )
            if prs and isinstance(prs, list) and prs[0]:
                return PRResult(
                    number=prs[0]["number"],
                    url=prs[0]["html_url"],
                    head_sha=prs[0].get("head", {}).get("sha"),
                )
        except Exception:
            pass  # best-effort
        return None

    def open_pull_request(
        self,
        branch: str,
        base: str,
        title: str,
        body: str,
        issue_number: int | None = None,
    ) -> PRResult:
        """Open a GitHub pull request via gh CLI or API fallback.

        Extracts the PR's head commit SHA so callers can use it for
        branch-to-issue linking when the remote SHA is unavailable.

        *issue_number* is accepted for protocol parity with Azure (which
        writes it as ``workItemRefs``) but unused here — GitHub's
        PR<->issue link is the closing keyword already in *body* (edge E3).
        """
        # Redact worktree paths before posting
        safe_title = redact_outbound(title)
        safe_body = redact_outbound(body)

        # gh CLI
        try:
            result = subprocess.run(
                [
                    "gh", "pr", "create",
                    "--repo", f"{self._owner}/{self._repo}",
                    "--head", branch,
                    "--base", base,
                    "--title", safe_title,
                    "--body", safe_body,
                ],
                capture_output=True, text=True, timeout=60, **GIT_TEXT_ARGS,
            )
            if result.returncode == 0:
                url = result.stdout.strip()
                # gh CLI prints the new PR's URL, so the number is known from it
                # (GitHub URLs always end /pull/<number>). Persist it so the
                # caller can cache it on the queue entry (issue #193).
                number = None
                try:
                    number = int(url.rstrip("/").rsplit("/", 1)[-1])
                except ValueError:
                    pass
                head_sha = None
                # Best-effort: fetch PR details to get head SHA
                try:
                    pr_num_from_url = url.rstrip("/").split("/")[-1]
                    pr_details = gh_get(
                        f"/repos/{self._owner}/{self._repo}/pulls/{pr_num_from_url}",
                        self._token, max_retries=1,
                    )
                    head_sha = pr_details.get("head", {}).get("sha")
                    number = number or pr_details.get("number")
                except Exception:  # Best-effort SHA lookup — PR is valid even if we can't fetch head SHA
                    pass
                return PRResult(url=url, number=number, head_sha=head_sha)
            dbg.warning("gh pr create failed: %s", result.stderr)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            dbg.warning("gh CLI unavailable, falling back to API")

        # API fallback
        pr_data = gh_post(
            f"/repos/{self._owner}/{self._repo}/pulls",
            self._token,
            {
                "title": safe_title,
                "body": safe_body,
                "head": branch,
                "base": base,
            },
        )
        pr_num = pr_data.get("number")
        pr_url = pr_data.get("html_url", f"#{pr_num}")
        head_sha = pr_data.get("head", {}).get("sha")
        return PRResult(number=pr_num, url=pr_url, head_sha=head_sha)

    def link_branch_to_issue(
        self,
        issue_number: int,
        commit_sha: str,
        branch: str,
    ) -> None:
        """Link branch to issue via GitHub GraphQL ``createLinkedBranch`` mutation.

        Creates a branch ref pointed at *commit_sha* and links it to the issue
        so the branch appears in the issue's Development sidebar.  The branch
        ref is created **before** any push, so this must run at branch-creation
        time (see ``create_worktree``).

        *commit_sha* is the full base SHA to create the branch from (e.g. the
        tip of ``origin/main``).

        GraphQL returns HTTP 200 even on error, so the ``errors`` key is
        inspected: "already exists" is swallowed (idempotent re-link),
        permission errors surface as ``MissingScopeError``.
        """
        if not self._token:
            return  # cannot link without a token

        # 1. Fetch the issue node_id via REST
        try:
            issue_data = gh_get(
                f"/repos/{self._owner}/{self._repo}/issues/{issue_number}",
                self._token,
                max_retries=1,
            )
        except RuntimeError as e:
            raise RuntimeError(f"Failed to fetch issue {issue_number} node_id: {e}") from e

        issue_id = issue_data.get("node_id")
        if not issue_id:
            return  # no node_id — nothing to link

        # 2. POST the GraphQL createLinkedBranch mutation
        mutation = (
            "mutation($issueId: ID!, $oid: GitObjectID!, $name: String) {"
            "  createLinkedBranch(input: {issueId: $issueId, oid: $oid, name: $name}) {"
            "    linkedBranch { id ref { name } }"
            "  }"
            "}"
        )
        variables = {
            "issueId": issue_id,
            "oid": commit_sha,
            "name": branch,
        }
        try:
            result = gh_post(
                "/graphql",
                self._token,
                {"query": mutation, "variables": variables},
                max_retries=1,
                timeout=10,
            )
        except RuntimeError as e:
            err_str = str(e)
            # 403 → permission error
            if "403" in err_str:
                raise MissingScopeError(
                    "PAT missing permission to create linked branch "
                    "(needs contents + issues write scope)"
                ) from e
            raise

        # 3. GraphQL returns HTTP 200 even on error — inspect the "errors" key
        errors = result.get("errors", [])
        if not errors:
            return  # success — branch created and linked

        # "already exists" / "Reference already exists" → benign no-op (idempotent)
        for err in errors:
            msg = err.get("message", "").lower()
            if "already exists" in msg:
                return  # branch already linked — fine
            # Permission error from GraphQL
            if "permission" in msg or "forbidden" in msg or "not acceptable" in msg:
                raise MissingScopeError(
                    "PAT missing permission to create linked branch "
                    "(needs contents + issues write scope)"
                )

        # Unknown GraphQL error — re-raise so the caller knows
        raise RuntimeError(
            f"createLinkedBranch GraphQL error: "
            f"{[e.get('message', str(e)) for e in errors]}"
        )

    def commit_trailer(self, issue_number: int) -> str:
        """GitHub commit-message reference: ``Refs #N`` (E2)."""
        return f"Refs #{issue_number}"

    def link_pr_to_issue(self, issue_number: int, pr_number: int) -> None:
        """No-op on GitHub.

        The PR<->issue link is derived from the closing keyword already written
        into the PR body at open time — there is no separate machine-readable
        relation to establish (edge E3). ``ensure_links`` therefore never
        writes; ``get_linkage`` reads the link from the body instead.
        """

    def get_linkage(
        self,
        issue_number: int,
        branch: str,
        pr_number: int | None,
    ) -> LinkageState:
        """Read the current E1–E5 edges from the PR payload.

        With no PR open the result reports nothing established and lists
        ``pr``/``closes`` as missing (the PR edges don't exist yet). A missing
        or unresolvable PR surfaces as ``merged=False`` / ``merge_state="unknown"``
        rather than a fabricated pass.
        """
        missing: list[str] = []
        if pr_number is None:
            # No PR yet, so neither PR-derived edge (pr_link, closes) exists.
            # The branch edge (E1) is managed at worktree-creation time via
            # createLinkedBranch and is not re-observed here.
            return LinkageState(pr_linked=False, missing=("pr_link", "closes"))

        try:
            pr = gh_get(
                f"/repos/{self._owner}/{self._repo}/pulls/{pr_number}",
                self._token, max_retries=1,
            )
        except Exception:
            # The PR read could not be consulted — report unknown, don't guess.
            return LinkageState(
                pr_number=pr_number, merge_state="unknown",
                missing=("pr_link", "closes"),
            )

        body = pr.get("body") or ""
        linked, closes = _issue_refs_in_body(body, issue_number)
        head = (pr.get("head") or {})
        head_ref = head.get("ref", "")
        head_sha = head.get("sha")
        merged = bool(pr.get("merged"))

        # branch_linked: the PR's head ref is our work branch (E1 — the branch
        # is associated with the issue through the PR that was opened from it).
        branch_linked = bool(branch) and head_ref == branch

        # merge_state from the PR payload's mergeability fields.
        mergeable = pr.get("mergeable")
        mergeable_state = pr.get("mergeable_state", "")
        if merged:
            merge_state = "clean"
        elif mergeable is True or mergeable_state == "clean":
            merge_state = "clean"
        elif mergeable is False or mergeable_state == "dirty":
            merge_state = "conflicts"
        elif mergeable_state in ("behind", "unstable", "has_hooks", "blocked"):
            merge_state = "pending"
        else:
            merge_state = "unknown"

        if not linked:
            missing.append("pr_link")
        if not closes:
            missing.append("closes")

        return LinkageState(
            branch_linked=branch_linked,
            pr_linked=linked,
            closes_on_merge=closes,
            pr_number=pr_number,
            head_sha=head_sha,
            merge_state=merge_state,
            merged=merged,
            missing=tuple(missing),
        )

    def capabilities(self) -> frozenset[Capability]:
        return _GITHUB_VCS_CAPS

    def get_ci_status(self, branch: str, ref_sha: str | None = None) -> CIStatus:
        """Combine check-runs and legacy commit status into one CIStatus.

        Priority: any failure -> failure; else any queued/in_progress/pending
        -> pending; else >=1 completed-success -> success; else none.

        Fail-safe: when the CI API could not be consulted (unresolvable
        branch head, or both check-runs and legacy status errored with no
        fallback data), the result is ``state="error"`` — never a vacuous
        "none" pass. A check-runs 403 (the documented classic-PAT-on-private
        repo case) falls back to ``GET /actions/runs?head_sha=``.
        """
        sha = ref_sha
        if not sha:
            try:
                commit = gh_get(
                    f"/repos/{self._owner}/{self._repo}/commits/{branch}",
                    self._token, max_retries=1,
                )
                sha = commit.get("sha")
            except Exception:
                return CIStatus(state="error", summary="could not resolve branch head")
        if not sha:
            return CIStatus(state="error", summary="could not resolve branch head")

        failing: list[str] = []
        pending_count = 0
        success_count = 0
        neutral = 0
        total = 0
        url: str | None = None

        # Both sources are best-effort; ``check_runs_ok`` / ``legacy_ok``
        # track whether the *API* was consulted successfully. Only when
        # neither source answers do we report state="error" (fail-safe:
        # absence of data is not the same as absence of CI).
        check_runs_ok = False
        try:
            check_runs = gh_get(
                f"/repos/{self._owner}/{self._repo}/commits/{sha}/check-runs",
                self._token, max_retries=1,
            )
            for run in check_runs.get("check_runs", []):
                total += 1
                name = run.get("name", "check")
                if run.get("status") != "completed":
                    pending_count += 1
                elif run.get("conclusion") in _FAILURE_CONCLUSIONS:
                    failing.append(name)
                elif run.get("conclusion") in ("neutral", "skipped"):
                    neutral += 1
                elif run.get("conclusion") in _SUCCESS_CONCLUSIONS:
                    success_count += 1
            check_runs_ok = True
        except Exception as exc:
            if "HTTP 403" in str(exc):
                # Classic PAT on private repos: the Checks API answers 403
                # ("Resource not accessible by personal access token"), but
                # the Actions API is still reachable. Use the documented
                # PAT-friendly fallback.
                try:
                    runs = gh_get(
                        f"/repos/{self._owner}/{self._repo}/actions/runs"
                        f"?head_sha={sha}&per_page=100",
                        self._token, max_retries=1,
                    )
                    for run in runs.get("workflow_runs", []):
                        total += 1
                        name = run.get("name", "workflow")
                        conclusion = run.get("conclusion")
                        if conclusion is None:
                            pending_count += 1
                        elif conclusion in _FAILURE_CONCLUSIONS:
                            failing.append(name)
                        elif conclusion in ("neutral", "skipped"):
                            neutral += 1
                        elif conclusion in _SUCCESS_CONCLUSIONS:
                            success_count += 1
                        if run.get("html_url"):
                            url = run.get("html_url")
                    check_runs_ok = True
                except Exception:
                    pass  # fallback also failed — error below if legacy fails too

        try:
            status = gh_get(
                f"/repos/{self._owner}/{self._repo}/commits/{sha}/status",
                self._token, max_retries=1,
            )
            for s in status.get("statuses", []):
                total += 1
                context = s.get("context", "status")
                state = s.get("state")
                if state in ("failure", "error"):
                    # Both "failure" and "error" blocked the gate pre-hardening —
                    # a legacy status of "error" means the check itself errored,
                    # i.e. it verified nothing, so it must keep blocking rather
                    # than read as a neutral pass.
                    failing.append(context)
                elif state == "pending":
                    pending_count += 1
                elif state == "success":
                    success_count += 1
        except Exception:
            pass  # legacy status is supplementary — a failure here alone is
                  # not fatal if check-runs produced data

        # Fail-safe terminal rule: the check-runs source (direct or the
        # actions/runs fallback) is the authoritative "does CI exist" signal.
        # If it could NOT be consulted AND no checks of any kind surfaced
        # (total == 0), we cannot distinguish "no CI" from "couldn't read
        # CI" — report error rather than a vacuous "none" pass. When legacy
        # combined-status *did* surface checks (total > 0) that alone is a
        # real CI signal, so a verdict is returned from legacy even with
        # check_runs_ok False. An empty legacy read alone, however, is not
        # proof of no CI (Actions-only repos have none), hence the
        # ``total == 0`` guard.
        if not check_runs_ok and total == 0:
            return CIStatus(
                state="error", head_sha=sha, url=self.commit_url(sha),
                summary="could not read CI status (check endpoints unavailable)",
            )

        if failing:
            return CIStatus(
                state="failure", head_sha=sha, url=url or self.commit_url(sha),
                total=total, failing=failing, neutral=neutral,
                pending_count=pending_count,
                summary=f"{len(failing)} check(s) failing: {', '.join(failing)}",
            )
        if pending_count:
            return CIStatus(
                state="pending", head_sha=sha, url=url or self.commit_url(sha),
                total=total, neutral=neutral, pending_count=pending_count,
                summary=f"{pending_count} check(s) pending",
            )
        if success_count or neutral:
            # A check-run/action that concluded neutral/skipped verified nothing
            # but is not a failure — the commit still passes. Pre-hardening these
            # were folded into the success count; the only change is that they are
            # now reported separately in the summary. (Legacy-status "error" is
            # deliberately NOT counted here — it is a blocking failure, see above.)
            # Read naturally for a neutral-only commit (no "0 check(s) passed"):
            # lead with the passed count, and add the skipped/neutral count only
            # when there is one.
            parts = []
            if success_count:
                parts.append(f"{success_count} check(s) passed")
            if neutral:
                parts.append(f"{neutral} skipped/neutral")
            summary = ", ".join(parts)
            return CIStatus(
                state="success", head_sha=sha, url=url or self.commit_url(sha),
                total=total, neutral=neutral, summary=summary,
            )
        return CIStatus(
            state="none", head_sha=sha, url=self.commit_url(sha),
            total=total, neutral=neutral, summary="no checks found",
        )

    def commit_url(self, commit_sha: str) -> str | None:
        """Clickable GitHub commit URL, or None when owner/repo are unset."""
        if self._owner and self._repo:
            return f"https://github.com/{self._owner}/{self._repo}/commit/{commit_sha}"
        return None

    def branch_url(self, branch: str) -> str | None:
        """Clickable GitHub compare URL, or None when owner/repo are unset."""
        if self._owner and self._repo:
            return f"https://github.com/{self._owner}/{self._repo}/compare/{branch}"
        return None

    def worktree_path_parts(self) -> tuple[str, ...]:
        return (self._owner, self._repo)

    def resolve_repo_id(self) -> str | None:
        """GitHub needs no numeric repo identifier in URLs — no-op."""
        return None

    def slug_prefix(self) -> str:
        return "gh"

    def pid_prefix(self) -> str:
        return "gh_"

