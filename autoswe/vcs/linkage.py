"""Idempotent cross-linkage writer (issue #245, plan §1.4).

One module, three call sites. ``ensure_links`` reads the current linkage via
``VCSProvider.get_linkage`` and issues only the writes for edges that are
missing, so it is a cheap no-op on the steady-state path and self-heals after
a crash or a hand-edited PR body. It is provider-agnostic: every write goes
through the protocol seam (``link_branch_to_issue`` / ``link_pr_to_issue`` /
``close_issue``), so no caller knows whether it is talking to GitHub or Azure —
the absence of a capability (e.g. ADO has no ``AUTO_CLOSE_ON_MERGE``) is what
decides the work, not a provider name.

Edge ownership by phase:
  - ``"branch"``            E1 issue→branch. Only this call site (worktree
    creation) establishes it, because the GitHub ``createLinkedBranch``
    mutation needs the base commit SHA and must run before the branch is
    pushed. ADO declares no ``BRANCH_LINK``, so this is a documented no-op
    there (see §1.3 of the plan + the live probe).
  - ``"pr_open"``           E3/E4 PR→issue (machine-readable). Writes
    ``link_pr_to_issue`` when the PR is not yet linked (no-op on GitHub, where
    the closing keyword in the body is the link).
  - ``"merge_observation"`` E5 merge→issue-closed. Self-heals E3, and if the
    platform does not auto-close (no ``AUTO_CLOSE_ON_MERGE``) — or the closing
    keyword failed to register — issues the explicit ``close_issue`` write.

``ensure_links`` persists the resulting ``LinkageState`` onto the queue entry
as ``linkage_state`` / ``linkage_missing`` (both registered in ``TASK_FIELDS``)
so ``queue status`` and ``/sync`` can render a per-task edge checklist.
"""
from __future__ import annotations

from dataclasses import asdict

from autoswe.core.logging_utils import get_debug_logger
from autoswe.providers.base import Capability, LinkageState
from autoswe.providers.factory import get_tracker, get_vcs

dbg = get_debug_logger()


def ensure_links(
    task: dict | None,
    repo_cfg: dict,
    cfg: dict | None,
    *,
    phase: str,
    vcs=None,
    base_sha: str | None = None,
) -> LinkageState | None:
    """Read current linkage and establish the edges *phase* owns.

    *task* is the queue entry (a mutable dict carrying at least
    ``issue_number``); the resulting ``LinkageState`` is persisted onto it as
    ``linkage_state`` / ``linkage_missing``. A ``None`` task (or one with no
    ``issue_number``) yields ``None`` — nothing to operate on.

    *vcs*, when given, is the already-resolved VCSProvider the caller holds
    (worktree / adapter / ship / loop all build one) — passing it in avoids a
    redundant client and keeps tests that patch that instance effective. When
    omitted it is resolved from *repo_cfg*.

    *base_sha* is the base commit SHA the ``branch`` phase needs to issue the
    GitHub ``createLinkedBranch`` mutation (which must run before the branch
    is pushed). Only the ``branch`` phase reads it.

    All edge writes are best-effort: a failed write is logged and recorded in
    ``LinkageState.missing`` rather than raised, so linkage bookkeeping never
    blocks the primary work (branch push / PR open / merge close) it
    accompanies.
    """
    cfg = cfg or {}
    if not task or "issue_number" not in task:
        return None

    issue_num = task["issue_number"]
    pr_number = task.get("pr_number")
    if vcs is None:
        vcs = get_vcs(repo_cfg)
    branch = vcs.branch_name(issue_num)
    caps = vcs.capabilities()

    if phase == "branch":
        # E1 is established once, at worktree creation, and only from the base
        # commit SHA — get_linkage cannot report it (no PR exists yet, so both
        # providers report branch_linked=False on the no-PR path). The caller
        # (worktree creation) holds a throwaway dict, not the queue entry, so
        # nothing is persisted here; the ADO branch-absence is surfaced by the
        # pr_open/merge_observation phases (which persist) and the welcome note.
        missing: list[str] = []
        _establish_branch(vcs, caps, base_sha or task.get("_base_sha"), issue_num, branch, missing)
        return LinkageState(missing=tuple(missing))

    # Read first — the steady-state path is a read plus no writes. With no PR
    # open the read is a cheap early-return (no network).
    state = vcs.get_linkage(issue_num, branch, pr_number)
    missing = list(state.missing)

    if phase in ("pr_open", "merge_observation"):
        _establish_pr_link(vcs, caps, state, issue_num, pr_number, missing)

    if phase == "merge_observation":
        if pr_number is not None:
            _maybe_close_on_merge(cfg, vcs, caps, state, repo_cfg, issue_num, missing)

    state.missing = tuple(dict.fromkeys(missing))  # de-dup, preserve order
    if isinstance(task, dict):
        task["linkage_state"] = asdict(state)
        task["linkage_missing"] = list(state.missing)
    return state


def render_linkage_checklist(task: dict) -> str:
    """Human-readable cross-linkage checklist for a task (issue #245 §1.4).

    Rendered from the persisted ``linkage_state`` / ``linkage_missing`` so an
    operator sees at a glance which of the edges E1–E5 exist on a task. A
    task with no linkage observation yet (no PR opened / merge-observed)
    renders nothing — the checklist is a property of a task that has a PR or
    has been merge-observed. Provider-agnostic: it reads the normalized state,
    not a provider field.
    """
    state = task.get("linkage_state")
    if not isinstance(state, dict):
        return ""
    missing = set(task.get("linkage_missing") or [])

    def mark(established: bool, edge: str) -> str:
        if established:
            return "✓"
        return "✗ (declared-unsupported or failed)" if edge in missing else "✗"

    lines = ["Linkage checklist:"]
    lines.append(f"  E1 issue→branch  : {mark(state.get('branch_linked', False), 'branch')}")
    lines.append(f"  E3 PR→issue      : {mark(state.get('pr_linked', False), 'pr_link')}")
    lines.append(f"  E5 close-on-merge: {mark(state.get('closes_on_merge', False), 'closes')}")
    if state.get("pr_number") is not None:
        lines.append(f"  PR #{state['pr_number']}: merged={state.get('merged', False)} "
                     f"merge_state={state.get('merge_state', 'unknown')}")
    return "\n".join(lines)


def _establish_branch(vcs, caps, base_sha, issue_num, branch, missing) -> None:
    """E1: establish the issue→branch link at worktree creation (best-effort)."""
    if Capability.BRANCH_LINK not in caps:
        # Declared absence — report it, never a silent skip (plan §1.3: the
        # operator sees this in the per-task checklist / welcome note, not
        # through a no-op that behaves like success).
        if "branch" not in missing:
            missing.append("branch")
        return
    if not base_sha:
        # No ref to link the branch from — the branch is not platform-linked.
        if "branch" not in missing:
            missing.append("branch")
        return
    try:
        vcs.link_branch_to_issue(issue_num, base_sha, branch)
    except Exception as e:  # noqa: BLE001 — a permission error or network failure
        # must not block the branch push.
        dbg.warning(
            "ensure_links: branch link failed for issue %d: %s: %s",
            issue_num, type(e).__name__, e,
        )
        if "branch" not in missing:
            missing.append("branch")


def _establish_pr_link(vcs, caps, state, issue_num, pr_number, missing) -> None:
    """E3/E4: establish the machine-readable PR→issue edge if it is missing."""
    if pr_number is None:
        # No PR yet — nothing to link. get_linkage already listed "pr_link".
        return
    if Capability.PR_ISSUE_LINK not in caps or state.pr_linked:
        return
    try:
        vcs.link_pr_to_issue(issue_num, pr_number)
        state.pr_linked = True
        # The link is now established; drop it from the missing list.
        if "pr_link" in missing:
            missing.remove("pr_link")
    except Exception as e:  # noqa: BLE001 — best-effort; record, don't raise.
        dbg.warning(
            "ensure_links: PR link failed for issue %d / PR %s: %s: %s",
            issue_num, pr_number, type(e).__name__, e,
        )
        if "pr_link" not in missing:
            missing.append("pr_link")


def _maybe_close_on_merge(cfg, vcs, caps, state, repo_cfg, issue_num, missing) -> None:
    """E5: explicitly close the issue when the platform will not do it itself.

    A merge closes the issue automatically only on platforms that declare
    ``AUTO_CLOSE_ON_MERGE`` (GitHub, via the closing keyword). ADO declares no
    such mechanic, so autoSWE issues the explicit ``close_issue`` write. On
    GitHub the write is a safety net for the (rare) case where the closing
    keyword failed to register.

    Idempotent: the current issue state is checked first and a terminal state
    means no write — so repeated merge-observations do not re-close.
    """
    if not state.merged:
        return
    if not cfg.get("AUTO_CLOSE_ON_MERGE", True):
        return  # operator opted out of auto-close
    # Owed? Always, if the platform has no auto-close mechanic; on GitHub only
    # when the closing keyword did not register (closes_on_merge is False).
    owed = (Capability.AUTO_CLOSE_ON_MERGE not in caps) or (not state.closes_on_merge)
    if not owed:
        return
    tracker = get_tracker(repo_cfg)
    try:
        issue = tracker.fetch_issue(issue_num)
    except Exception as e:  # noqa: BLE001 — cannot verify state; skip the close.
        dbg.warning(
            "ensure_links: could not read issue %d before close: %s: %s",
            issue_num, type(e).__name__, e,
        )
        if "closes" not in missing:
            missing.append("closes")
        return
    if issue.state == "closed":
        return  # already terminal — the close is owed but already done.
    try:
        tracker.close_issue(issue_num, reason="completed")
    except Exception as e:  # noqa: BLE001 — the tracker already reported it
        # (one-time operator comment on a 400); do not double-report here.
        dbg.warning(
            "ensure_links: close_issue(%d) failed: %s: %s",
            issue_num, type(e).__name__, e,
        )
        if "closes" not in missing:
            missing.append("closes")
        return
    if "closes" in missing:
        missing.remove("closes")
