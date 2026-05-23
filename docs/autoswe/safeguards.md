# Safeguards

## Deployment Model (the first "safeguard")

autoSWE runs Claude with `bypassPermissions` + `Bash` for `/fix` (and `/sync` conflict resolution) **on purpose**. The expectation is that it runs on a **dedicated, isolated machine** that does nothing else: it can clone repos, write to `autoswe/issue-*` branches, and push them — and that's the whole blast radius. Don't run autoSWE on a shared workstation, a build box with secrets for other systems, or anywhere a compromised agent run could do damage beyond "messed up a feature branch." The free-permissions choice is only safe under that assumption — treat the isolation as a hard requirement, not a nice-to-have.

The orchestrator's own privilege split still holds inside that machine:

- `/plan` and `resume_plan` → `permission_mode="plan"`, `allowed_tools=["Read", "Glob", "Grep"]` + `AGENT_TASK_TOOLS` — read-only (native plan mode produces plan files in `~/.claude/plans/`). `Write`/`Edit` remain blocked by the `can_use_tool` callback.
- `/fix` → `permission_mode="bypassPermissions"`, `allowed_tools=["Read", "Edit", "Write", "Bash", "Glob", "Grep"]` + `AGENT_TASK_TOOLS` — full access.
- `/sync` conflict resolution → same as `/fix`.
- `/review` → `permission_mode="plan"`, `allowed_tools=["Read", "Glob", "Grep"]` + `AGENT_TASK_TOOLS` — read-only.

`AGENT_TASK_TOOLS` (`TodoWrite`, `TaskCreate`, `TaskUpdate`, `TaskGet`, `TaskList`, `TaskOutput`, `TaskStop`, `Agent`) are progress/orchestration tools available in all phases. They do not themselves grant repo write access (though a sub-agent spawned via `Agent` inherits the same `can_use_tool` callback, so `Write`/`Edit` denials still apply in read-only phases).

## Who Can Steer

Slash commands are only honored from users in the `ALLOWED_AUTHORS` allowlist (global config or per-repo `allowed_authors` override). An empty allowlist (the default) allows everyone. When an allowlist is set:

- Slash commands from unauthorized users are silently ignored (both in comments and issue body)
- Issues created by unauthorized users are silently skipped — autoSWE will not process them
- `auto_dispatch_new` respects the allowlist — unauthorized creators' issues are not auto-dispatched

A label is never a steering input (`labels.md`).

## `MAX_CONCURRENT` PID-File Gate

`count_running_jobs()` counts `.pid` files in `running/` whose processes are actually alive; the dispatch loop breaks immediately once `count >= MAX_CONCURRENT` (default 1). Stale PID files (dead processes) are auto-cleaned. Additionally `is_repo_locked(owner, repo, provider)` blocks a second task in the same repo from running concurrently (matches the slug-prefix `.pid` pattern).

## `MAX_ATTEMPTS` Per Issue

`attempt_count` is incremented by `decide()` each time it detects a restart. When `attempt_count > MAX_ATTEMPTS` (default 3), `decide()` returns `Action(kind="mark_failed_limit")` — `emit()` produces a "Max attempts reached" comment, sets `autoswe_status = "failed"`, and sets `_guard_blocked = True` so comment re-scans stop until a new command appears. `/retry` resets `attempt_count` to 1.

## `MAX_TOTAL_HOURS` Wall Clock

`first_dispatched_at` is set on first dispatch. `decide()` checks `(now - first_dispatched_at) / 3600 > MAX_TOTAL_HOURS` (default 2). If exceeded → `Action(kind="mark_failed_limit")`, which emits "Time limit exceeded" comment, `autoswe_status = "failed"`, `_guard_blocked = True`.

`first_dispatched_at` is reset to `None` in two situations:
- **Terminal status completion** (`orch/emit.py`): after any COMPLETED status (`fixed`/`synced`/`shipped`/`reviewed`), `failed`, `error`, `skipped`, or `aborted` — each new dispatch cycle gets a fresh timer. The `patch_queue` Effect sets `first_dispatched_at: None`.
- **Phase transition** (`orch/decide.py`): when restarting from `planned` or a RUNNING status — each pipeline phase (plan → fix → pr) gets its own timer so the time limit measures the current phase, not the cumulative time of completed phases (fixes #119).

## `AGENT_TIMEOUT` Per Claude Session

`asyncio.wait_for(coro, timeout=AGENT_TIMEOUT)` in `runner.py`. Default 7200 s (2 h); per-repo override via `repos.json` → `agent_timeout`. On timeout the handler returns `"FAILED: timeout during …"`.

## Comment-ID Restart Anchor

Every successful dispatch posts a `"Completed with command …"` comment. `decide()` uses `_find_last_completion_id()` to find its comment ID. A slash command whose ID is *≤ the last completion comment ID* is ignored — this is what stops a stale command from re-firing every poll. Auto-resume for `waiting`/`planned` uses the looser `_find_last_bot_comment_id()` (last bot comment ID of any kind) as its anchor.

Additionally, `last_dispatched_command_id` and `last_consumed_reply_id` are ID-based watermarks in the queue row — the state machine compares comment IDs (integers), not timestamps. This eliminates clock-skew bugs and identical-second ties.

## Staleness Refresh Before Running

The queue is a snapshot from the last poll. Before `_dispatch_task` actually runs a task, the poll loop **re-fetches the issue** (state + comments) via `read_api()` and reconciles:

- `issue.state == "closed"` → don't run the agent; set `autoswe_status = "fixed"` and `gh_closed = True`, then move on. (The COMPLETED status here means *autoSWE is done with it* — the issue being "closed" is a separate lifecycle on the tracker side, not something autoSWE owns.)
- comments changed since last poll → `decide()` re-evaluates from the fresh API data; if the command is now stale (comment ID ≤ `last_dispatched_command_id`), returns `noop`.

This is the safety net for the gap between "poll built the map" and "dispatch acts on it."

## RUNNING States Are Protected

`decide()` only re-opens a task from a COMPLETED status (`fixed`/`synced`/`shipped`/`reviewed`)/`failed`/`error`/`skipped`/`planned`/`waiting` — never from a RUNNING status (`planning`/`fixing`/`syncing`/`reviewing`/`shipping`). So a comment posted while an agent run is in flight can't pull the task out from under it; it'll be picked up on the *next* poll after the run finishes. (The `autoswe:*` label mirror inherits this; the protection is in `autoswe_status`, not the label.)

## Closed-Issue Handling (two paths)

1. **At sync time:** an issue that has dropped out of `list_open_issues()` → `gh_closed = True` in the queue. The task is never purged; if the issue is reopened, `gh_closed` is set back to `False`.
2. **At dispatch time (refresh):** see "Staleness Refresh" above — a task that was `pending` at sync but whose issue is now closed is not run; it's marked as a COMPLETED status + `gh_closed`.
