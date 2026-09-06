import re

from autoswe.core.logging_utils import get_debug_logger, log
from autoswe.tracking.api import gh_get, gh_get_all, gh_post, gh_put

dbg = get_debug_logger()

# Label constants — autoswe: prefix (lowercase to match GitHub conventions)
# Color families: blue (pending), orange (RUNNING), grey (COMPLETED),
#   yellow (waiting), red (failed/error), white (skipped), pink (aborted),
#   green (planned).
AUTOSWE_LABELS = {
    "autoswe:pending":    {"color": "0075ca", "description": "Ready to dispatch"},
    "autoswe:planning":   {"color": "d93f0b", "description": "Planning in progress"},
    "autoswe:fixing":     {"color": "d93f0b", "description": "Fix in progress"},
    "autoswe:syncing":    {"color": "d93f0b", "description": "Sync in progress"},
    "autoswe:reviewing":  {"color": "d93f0b", "description": "Review in progress"},
    "autoswe:shipping":   {"color": "d93f0b", "description": "PR creation in progress"},
    "autoswe:planned":    {"color": "0e8a16", "description": "Plan ready, waiting for /fix"},
    "autoswe:fixed":      {"color": "ededed", "description": "Fix completed"},
    "autoswe:synced":     {"color": "ededed", "description": "Sync completed"},
    "autoswe:shipped":    {"color": "ededed", "description": "PR created"},
    "autoswe:reviewed":   {"color": "ededed", "description": "Review approved (LGTM)"},
    "autoswe:review_failed":  {"color": "fbca04", "description": "Review found issues — needs /fix"},
    "autoswe:review_blocked": {"color": "d73a4a", "description": "Review blocked — critical findings, needs /fix"},
    "autoswe:test_failed":    {"color": "d73a4a", "description": "Fix pushed but test suite failing — needs /fix"},
    "autoswe:waiting":    {"color": "fbca04", "description": "Agent asked a question"},
    "autoswe:failed":     {"color": "d73a4a", "description": "Agent errored"},
    "autoswe:skipped":    {"color": "ffffff", "description": "Skipped by user"},
    "autoswe:aborted":    {"color": "e99695", "description": "Aborted by user"},
    "autoswe:error":      {"color": "b60205", "description": "Infrastructure error"},
}

_PREFIX = "autoswe:"

# The canonical set of autoswe_status values (no prefix).
# Used to validate every status write — catches typos before they drift.
VALID_STATUSES = frozenset(
    {"pending", "planning", "fixing", "syncing", "reviewing", "shipping",
     "planned", "fixed", "synced", "shipped", "reviewed",
     "review_failed", "review_blocked", "test_failed",
     "waiting", "failed", "skipped", "aborted", "error"}
)

# Status groupings — imported by decide/emit/loop instead of re-declaring sets.
RUNNING_STATUSES = frozenset({"planning", "fixing", "syncing", "reviewing", "shipping"})
COMPLETED_STATUSES = frozenset({"fixed", "synced", "shipped", "reviewed"})
TERMINAL_STATUSES = COMPLETED_STATUSES | frozenset({"failed", "skipped", "aborted", "error"})
# Non-terminal resting states a /review lands in when it found problems. The
# task is NOT done: /pr is blocked until the user posts /fix (which re-reviews).
REVIEW_BLOCKING_STATUSES = frozenset({"review_failed", "review_blocked"})

# Non-terminal resting states where shipping is blocked: the review verdicts
# (review_failed/review_blocked) plus the post-fix test gate (test_failed —
# the fix committed and pushed, but the branch suite is red). /pr is refused
# until a /fix re-runs the blocking check green; restarts start a fresh
# MAX_ATTEMPTS budget (the prior phase finished, the gate is a new signal).
SHIPPING_BLOCKING_STATUSES = REVIEW_BLOCKING_STATUSES | frozenset({"test_failed"})

# Action kind → status mappings (module-level to avoid per-call allocation)
_KIND_TO_RUNNING = {
    "plan": "planning",
    "fix": "fixing",
    "retry": "fixing",  # default: retry replays fix
    "sync_branch": "syncing",
    "ship_pr": "shipping",
    "review": "reviewing",
}
_KIND_TO_COMPLETED = {
    "plan": "planned",
    "fix": "fixed",
    "retry": "fixed",  # retry replays fix phase
    "sync_branch": "synced",
    "ship_pr": "shipped",
    "review": "reviewed",
}
# Slash command → action kind (shared by decide.py and normalize_legacy_status)
_CMD_TO_KIND = {
    "/plan": "plan",
    "/fix": "fix",
    "/pr": "ship_pr",
    "/sync": "sync_branch",
    "/retry": "retry",
    "/review": "review",
}


def running_status_for(kind: str, last_phase: str | None = None) -> str:
    """Return the RUNNING status for an action kind.

    For ``retry`` the status depends on ``last_phase`` (plan→planning, fix→fixing).
    """
    if kind == "retry" and last_phase == "plan":
        return "planning"
    return _KIND_TO_RUNNING.get(kind, "fixing")


def completed_status_for(kind: str) -> str:
    """Return the COMPLETED status for an action kind."""
    return _KIND_TO_COMPLETED.get(kind, "fixed")


def _kind_from_command(cmd: str | None) -> str:
    """Derive an action kind from a slash command string."""
    return _CMD_TO_KIND.get(cmd, "fix")


def normalize_legacy_status(status: str | None, last_dispatched_command: str | None = None) -> str | None:
    """Convert legacy status values (dispatched/done/plan_ready) to new names.

    Used when loading queue.json entries written by the old code. Derives the
    correct task-specific verb from ``last_dispatched_command`` when possible.
    """
    if status is None:
        return None
    if status == "plan_ready":
        return "planned"
    if status in ("dispatched", "done"):
        kind = _kind_from_command(last_dispatched_command)
        if status == "dispatched":
            return running_status_for(kind)
        return completed_status_for(kind)
    return status


def _validate_status(status: str) -> None:
    """Raise ValueError if *status* is not a known autoswe_status value.

    Accepts both bare forms ("done") and prefixed forms ("autoswe:done").
    """
    bare = status[len(_PREFIX):] if status.startswith(_PREFIX) else status
    if bare not in VALID_STATUSES:
        raise ValueError(f"Invalid autoswe_status: {status!r} — not in {sorted(VALID_STATUSES)}")


def _ensure_repo_labels(owner: str, repo: str, token: str) -> None:
    """Ensure all autoswe:* labels exist in the repo."""
    existing = gh_get_all(f"/repos/{owner}/{repo}/labels", token)
    existing_names = {lb["name"] for lb in existing}
    for name, props in AUTOSWE_LABELS.items():
        if name not in existing_names:
            gh_post(f"/repos/{owner}/{repo}/labels", token, {
                "name": name, "color": props["color"], "description": props["description"]
            })
            log(f"[LABEL] Created {name} in {owner}/{repo}")


def _set_autoswe_status(owner: str, repo: str, issue_number: int, status_label: str, token: str) -> None:
    """Set autoSWE status label, preserving non-status labels."""
    _validate_status(status_label)
    current = gh_get(f"/repos/{owner}/{repo}/issues/{issue_number}/labels", token)
    non_status = [lb["name"] for lb in current if not lb["name"].startswith(_PREFIX)]
    new_labels = [*non_status, status_label]
    gh_put(f"/repos/{owner}/{repo}/issues/{issue_number}/labels", token, {"labels": new_labels})
    log(f"[LABEL] {owner}/{repo}#{issue_number} -> {status_label}")


def _get_autoswe_status(labels: list):
    """Extract current status from labels list."""
    for label in labels:
        name = label if isinstance(label, str) else label.get("name", "")
        if name.startswith(_PREFIX):
            return name.replace(_PREFIX, "")
    return None


_VERDICT_RE = re.compile(r"#{1,6}\s*Verdict\b(.*?)(?:\n#{1,6}\s|\Z)", re.IGNORECASE | re.DOTALL)


def _verdict_field_to_status(verdict: str) -> str:
    """Map a reviewer's structured ``verdict`` field to an autoswe status.

    This is the primary gate when the reviewer produces schema-validated
    structured output (issue #173 F-18): it reads the one field designed for
    the gate instead of scraping markdown. The mapping is conservative —
    it only ever produces a *blocking* status when the verdict explicitly says
    so; an unrecognised value falls back to the non-gating ``"reviewed"``.
    """
    low = (verdict or "").strip().lower()
    if "block" in low:
        return "review_blocked"
    if "change" in low or "fail" in low or "request" in low:
        return "review_failed"
    return "reviewed"


def parse_review_verdict(review_text: str) -> str:
    """Map a review report's verdict to an autoswe status.

    Returns one of:
      * ``"reviewed"``       — LGTM / approved (or no blocking verdict found).
      * ``"review_failed"``  — "Needs changes" verdict (MEDIUM findings).
      * ``"review_blocked"`` — "Blocked" verdict (CRITICAL findings).

    The reviewer report ends with a ``## Verdict`` section reading one of
    ``LGTM`` / ``Needs changes`` / ``Blocked``. When that section is present we
    parse only its contents (so the words "Blocked"/"Needs changes" appearing
    inside finding descriptions don't trigger a false gate). When it is absent
    we scan the whole text but only react to the explicit verdict tokens,
    defaulting to ``"reviewed"`` so a review without a recognisable verdict
    keeps the historical (non-gating) behaviour.
    """
    text = review_text or ""
    m = _VERDICT_RE.search(text)
    scope = m.group(1) if m else text
    low = scope.lower()
    if re.search(r"\bblocked\b", low):
        return "review_blocked"
    if re.search(r"needs[\s-]*changes?\b", low):
        return "review_failed"
    return "reviewed"


def _map_done_to_status(done_content: str, kind: str = "fix", verdict: str | None = None) -> str:
    """Map handler return string to autoswe status (no prefix).

    The *kind* parameter determines which completed status to use for DONE*
    returns (e.g., "fixed" for fix, "synced" for sync_branch).

    For REVIEW_READY, the structured ``verdict`` field (from the reviewer's
    schema-validated output, issue #173 F-18) is the primary gate; the markdown
    "## Verdict" regex (``parse_review_verdict``) is only the fallback when the
    structured field is absent.
    """
    if done_content == "PLAN_READY":
        return "planned"
    elif done_content.startswith("REVIEW_READY\t"):
        review_text = done_content[len("REVIEW_READY\t"):]
        # Primary gate: the structured verdict, when present. A blocking
        # verdict transitions to a non-terminal review_failed/review_blocked
        # state so decide() can refuse /pr until a /fix addresses the findings.
        if verdict:
            return _verdict_field_to_status(verdict)
        # Fallback: no structured verdict (e.g. Codex/text path) — scrape the
        # markdown "## Verdict" section as before.
        return parse_review_verdict(review_text)
    elif done_content == "REVIEW_READY":
        # Bare REVIEW_READY (no embedded text). Still prefer the structured
        # verdict over the historical "approved" default.
        if verdict:
            return _verdict_field_to_status(verdict)
        return "reviewed"
    elif done_content.startswith("WAITING:"):
        return "waiting"
    elif done_content.startswith("FAILED:"):
        return "failed"
    elif done_content.startswith("TESTS_FAILED"):
        # Post-fix test gate red (Natedorr/testProject#20): the work was
        # committed/pushed but the branch suite is failing. Non-terminal —
        # the task stays restartable and /pr is blocked until a /fix clears
        # the gate.
        return "test_failed"
    elif done_content == "SKIPPED":
        return "skipped"
    elif done_content == "ABORTED":
        return "aborted"
    else:
        # DONE*, DONE_SUMMARY*, etc. → task-specific completed status
        return completed_status_for(kind)
