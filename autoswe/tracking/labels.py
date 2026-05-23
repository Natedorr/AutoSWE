from autoswe.core.config import LOGS_DIR
from autoswe.core.logging_utils import init_debug_logger, log
from autoswe.tracking.api import gh_get, gh_get_all, gh_post, gh_put

dbg = init_debug_logger(LOGS_DIR)

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
    "autoswe:reviewed":   {"color": "ededed", "description": "Review completed"},
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
     "waiting", "failed", "skipped", "aborted", "error"}
)

# Status groupings — imported by decide/emit/loop instead of re-declaring sets.
RUNNING_STATUSES = frozenset({"planning", "fixing", "syncing", "reviewing", "shipping"})
COMPLETED_STATUSES = frozenset({"fixed", "synced", "shipped", "reviewed"})
TERMINAL_STATUSES = COMPLETED_STATUSES | frozenset({"failed", "skipped", "aborted", "error"})

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
    new_labels = non_status + [status_label]
    gh_put(f"/repos/{owner}/{repo}/issues/{issue_number}/labels", token, {"labels": new_labels})
    log(f"[LABEL] {owner}/{repo}#{issue_number} -> {status_label}")


def _get_autoswe_status(labels: list):
    """Extract current status from labels list."""
    for label in labels:
        name = label if isinstance(label, str) else label.get("name", "")
        if name.startswith(_PREFIX):
            return name.replace(_PREFIX, "")
    return None


def _map_done_to_status(done_content: str, kind: str = "fix") -> str:
    """Map handler return string to autoswe status (no prefix).

    The *kind* parameter determines which completed status to use for DONE*
    returns (e.g., "fixed" for fix, "synced" for sync_branch).
    """
    if done_content == "PLAN_READY":
        return "planned"
    elif done_content == "REVIEW_READY" or done_content.startswith("REVIEW_READY\t"):
        return "reviewed"
    elif done_content.startswith("WAITING:"):
        return "waiting"
    elif done_content.startswith("FAILED:"):
        return "failed"
    elif done_content == "SKIPPED":
        return "skipped"
    elif done_content == "ABORTED":
        return "aborted"
    else:
        # DONE*, DONE_SUMMARY*, etc. → task-specific completed status
        return completed_status_for(kind)
