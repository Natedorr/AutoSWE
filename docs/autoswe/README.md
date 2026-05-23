# autoSWE Process Documentation

This folder is the **authoritative source of truth** for how autoSWE works. Edit a topic file here when you change behavior — then derive `CLAUDE.md` and the repo-root `README.md` from this folder, not the other way around.

## What Drives autoSWE (read this first)

autoSWE is **queue-driven**, not label-driven:

- **Issue/work-item comments are the input.** Slash commands in comments (`/plan`, `/fix`, `/pr`, `/sync`, `/retry`, `/skip`, `/abort`) are how a user steers a task without touching a terminal.
- **`data/queue.json` is the run state.** Each task carries an `autoswe_status` enum (`null → pending → RUNNING (planning|fixing|syncing|reviewing|shipping) → COMPLETED (planned|fixed|synced|shipped|reviewed) | waiting | failed | skipped | aborted`) and, when a fresh command is detected, a `pending_command`. The dispatch loop reads this — nothing else — to decide what to run next.
- **`autoswe:*` labels are a one-way mirror for humans.** autoSWE writes them so a user can see state at a glance. autoSWE never *reads* a label to decide what to do. Adding or removing a label by hand changes nothing — steer with a comment.
- **The queue can go stale.** It is a snapshot from the last sync. Before autoSWE actually runs a task it re-fetches the issue (state + comments) and reconciles: closed → skip, new/edited/deleted comments → re-derive the command.

## Topics

| File | What it covers |
|------|----------------|
| [pipeline.md](pipeline.md) | End-to-end execution: cron → sync (build the run map) → quick posts → dispatch (rip through sessions) |
| [handlers.md](handlers.md) | Per-task handlers: plan, fix, PR, sync, retry, skip, abort |
| [data-model.md](data-model.md) | queue.json shape (`autoswe_status` enum), NormalizedIssue/Comment, slug format, PID/.done files |
| [labels.md](labels.md) | The `autoswe:*` labels as a read-only mirror of `autoswe_status`; bot-marker convention |
| [slash-commands.md](slash-commands.md) | User-facing commands, parsing, auto-resume, multi-command-last-wins |
| [config.md](config.md) | autoswe.env keys, repos.json fields, model resolution, prompt templates |
| [providers.md](providers.md) | IssueTracker/VCSProvider protocols, GitHub + Azure backends, factory |
| [git-worktrees.md](git-worktrees.md) | Per-repo clones, per-issue worktrees, branch naming, GC |
| [safeguards.md](safeguards.md) | MAX_CONCURRENT, MAX_ATTEMPTS, time limits, completion anchor |
| [debugging.md](debugging.md) | Live log inspection, queue state, unsticking zombies, session files |
| [testing.md](testing.md) | Test harness, pytest structure, test seams, CI strategy |
| [technical-reference.md](technical-reference.md) | Consolidated pipeline internals (CLI entry points, status transitions, three-layer architecture) |

## Derivation Rule

`CLAUDE.md` and the repo-root `README.md` are **downstream** of this folder. When you change code:

1. Update the relevant topic file(s) in this folder
2. If the change affects what Claude needs to know, update `CLAUDE.md`
3. If the change affects the quickstart or project intro, update `README.md`
