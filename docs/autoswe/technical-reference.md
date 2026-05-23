# Technical Reference

Deep-dive technical details about the autoSWE pipeline, architecture, and internal mechanics.

> This document was split from the original README for developers who need implementation details. See [README.md](../README.md) for the product overview and quick start.

---

## Pipeline Overview

autoSWE runs from cron. Each run does two things, in order:

1. **Sync** — `orch.loop.poll()` reads every tracked issue's comments via provider adapters and builds `data/queue.json`: per-task `autoswe_status` + (when a fresh slash command is present) the pending action. This is the only place the queue is *written from the outside world*. Also: post any quick comments that don't need Claude (welcome messages, limit-exceeded notices).

2. **Dispatch** — For tasks with actionable decisions, `decide()` returns an `Action`; `run()` invokes Claude; `emit()` produces `Effect`s; the adapter applies them to the provider API.

Labels (`autoswe:*`) are written at the end of each step so a human can see state. They are never read back to decide anything.

```
CRON (e.g. every 10 min)
  → poller.sh (flock) / poller.ps1 (named mutex)   # one run at a time
    → git fetch + reset --hard origin/master
      → python autoswe.py poller --drain
        → orch.loop._drain_poll()
          → orch.loop._single_poll()
            1. For each repo: read_api()            # provider → ApiState
            2. For each issue: decide(World)        # Layer A — World → Action
            3. For each non-noop Action:
               a. acquire PID file                   # concurrency gate
               b. set RUNNING status (planning/fixing/etc)
               c. run(action, world)                # Layer B — Claude handler
               d. emit(action, result, world)       # Layer C — Action+Result → Effects
               e. apply_effect() per effect          # adapter → API calls
               f. release PID file
            4. Backfill bot_comment_ids              # self-heal first poll after wipe
            5. gh_closed detection & label mirror
            6. _post_pending_welcomes()             # first-time welcome (no Claude)
```

## Three-Layer Architecture

The pipeline is split into three pure layers separated by frozen dataclasses:

```
  I/O (adapters)        Layer A         Layer B        Layer C         I/O (adapters)
 ──────────────────►  decide() ──Action──► run() ──DispatchResult──► emit() ──Effects──► apply_effect()
       │                 │ (pure)            │ (Claude)                  │ (pure)
       └── World ◀───────────────────────────────────────────────────────┘
```

- **Layer A (decide):** `decide(World) -> Action` — pure state machine. No I/O. Reads `World` (API snapshot + queue state + config) and returns what to do.
- **Layer B (run):** `run(Action, World) -> DispatchResult` — Claude runner wrapper. Invokes planner/coder/ship modules. Returns handler output with cost/duration metrics.
- **Layer C (emit):** `emit(Action, DispatchResult, World) -> tuple[Effect, ...]` — pure effect emission. Maps handler output to status changes, comments, queue patches, and PR creations.

Each layer boundary is cached as a test seam — see [testing.md](testing.md).

## CLI Entry Points

`autoswe.py` → `autoswe/cli.py:main()` delegates to subcommands:

| Subcommand | Description |
|------------|-------------|
| `poller [--drain] [--max-cycles N]` | Full run: sync + dispatch. `--drain` loops until idle. |
| `sync [--all] [--repo OWNER/REPO]` | Build/refresh the queue only (no Claude runs). |
| `dispatch` | Dispatch loop only (no sync). |
| `setup [--force]` | Interactive first-run setup wizard. `--force` overwrites existing config. |
| `queue list [--status X]` | Print queue tasks, optionally filtered by `autoswe_status`. |
| `queue status --repo O/R --issue N` | Print full task dict for one issue. |
| `queue prune [--older-than-days N] [--dry-run]` | Remove old done/skipped/closed tasks. `--dry-run` lists without deleting. |

## Poller Wrapper

`poller.sh` (Linux, `flock`) and `poller.ps1` (Windows, `System.Threading.Mutex`) provide a process-level mutex so two cron firings can't overlap — a firing that finds a run in progress simply exits. Both fetch+reset the autoSWE repo to `origin/master`, then invoke `python autoswe.py poller --drain`.

## Handler Return → Status Mapping

The `emit()` layer maps `DispatchResult.done_content` to status transitions:

| Handler Return | `autoswe_status` | Mirrored Label | Comment Posted |
|----------------|------------------|----------------|----------------|
| `"PLAN_READY"` | `planned` | `autoswe:planned` | Plan comment (posted by handler) |
| `"REVIEW_READY"` | `reviewed` | `autoswe:reviewed` | Review comment (posted by handler) |
| `"WAITING: …"` | `waiting` | `autoswe:waiting` | Questions comment (posted by handler) |
| `"DONE*"` (from `/fix`) | `fixed` | `autoswe:fixed` | Completion comment with commit link |
| `"DONE*"` (from `/sync`) | `synced` | `autoswe:synced` | Completion comment with commit link |
| `"DONE*"` (from `/pr`) | `shipped` | `autoswe:shipped` | Completion comment with PR link |
| `"FAILED: …"` | `failed` | `autoswe:failed` | Failure comment with `/retry` prompt |
| `"SKIPPED"` | `skipped` | `autoswe:skipped` | — |
| `"ABORTED"` | `aborted` | `autoswe:aborted` | Abort comment |

`"REVIEW_READY"` transitions to `reviewed` — it is now a terminal status. See `labels.py:_map_done_to_status()` and `orch/emit.py`.

`"DONE*"` means any return starting with `DONE` — `"DONE_SUMMARY\t…\t<sha>"`, `"DONE: no changes detected"`, `"DONE: synced …"`, `"DONE: PR …"`.

## Auto-PR

After a successful `/fix` (`autoswe_status → fixed`), if `AUTO_CREATE_PR=true` and no PR exists for the branch, `emit()` includes a `create_pr` Effect. The adapter translates it to the provider's PR creation API.

## Post-Poll Bookkeeping

After all dispatches in a cycle:

1. **Backfill `bot_comment_ids`** — Any comment with `is_bot=True` but ID not yet in the queue row gets backfilled. Makes the system self-healing on the first poll after a queue wipe.
2. **`gh_closed` detection** — Issues that dropped out of the open-issues list get `gh_closed = True` and `autoswe_status = "fixed"`. Reopened issues clear the flag.
3. **Label mirror** — Terminal statuses (`fixed`, `synced`, `shipped`, `reviewed`, `failed`, `skipped`, `aborted`, `planned`, `waiting`) have their `autoswe:*` label synced on the issue.
4. **Welcome comments** — `_post_pending_welcomes()` posts the welcome message to newly discovered issues, capturing the returned comment ID in `welcome_comment_id` and `bot_comment_ids`.

## Status Transitions

```
                                                                ┌──→ planned ──→ pending ──┐
                                                                │         ↑                 │
   (new) ──→ pending ──→ planning/fixing/syncing/reviewing ──→ waiting ──→ pending
                      │  /shipping                           │                   │
                      ├──→ fixed/synced/shipped/reviewed ─────────────────────────┤
                      └──→ failed ───────────────────────────────────────────────┤
                      │                                                          │
                      └────────────── skipped ───────────────────────────────────┘
```

- **→ pending** (set by `decide()`): First sight of an issue carrying a slash command (body or comment), or a user comment with a slash command whose ID is newer than `last_dispatched_command_id`, or any user reply on a task in `waiting`/`planned`.
- **→ RUNNING statuses** (`planning`/`fixing`/`syncing`/`reviewing`/`shipping`; set by `_dispatch_task()`): Only from a non-noop Action. PID file is created first, then the status flips. The specific running status depends on the action kind.
- **→ planned**: Planner returned `"PLAN_READY"` (`<AUTOSWE_PLAN>` block found).
- **→ waiting**: Planner returned `"WAITING: …"` (`<AUTOSWE_QUESTIONS>` block, or no XML block).
- **→ COMPLETED statuses** (`fixed`/`synced`/`shipped`/`reviewed`): Coder returned `"DONE*"` for `/fix` → `fixed`, or `/sync` succeeded → `synced`, or `/pr` succeeded → `shipped`, or `/review` succeeded → `reviewed`, or the issue was found closed at refresh time → `fixed`.
- **→ failed**: Handler returned `"FAILED: …"`, or sync's attempt/time guard tripped.
- **→ skipped**: `/skip`.
- **→ aborted**: `/abort`.

RUNNING statuses are **protected**: `decide()` only re-opens a task from a COMPLETED status (`fixed`/`synced`/`shipped`/`reviewed`)/`failed`/`skipped`/`planned`/`waiting`, never from a RUNNING status — so a comment posted mid-run can't yank a task out from under the agent.

## Bot Comment Convention

Every comment autoSWE posts ends with `<!-- autoswe-bot -->` (`BOT_MARKER` in `tracking/comments.py`). This marker is a **fallback** for bot detection — the primary mechanism is `bot_comment_ids` in the queue row.

---

_For safeguards, configuration, provider details, and testing — see the sibling docs in this directory._
