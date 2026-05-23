# Execution Pipeline

## The Model

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
 ──────────────────►  decide() ───Action──► run() ──DispatchResult──► emit() ──Effects──► apply_effect()
       │                 │ (pure)            │ (Claude)                  │ (pure)
       └── World ◀───────────────────────────────────────────────────────┘
```

- **Layer A (decide):** `decide(World) -> Action` — pure state machine. No I/O. Reads `World` (API snapshot + queue state + config) and returns what to do.
- **Layer B (run):** `run(Action, World) -> DispatchResult` — Claude runner wrapper. Invokes planner/coder/ship modules. Returns handler output with cost/duration metrics.
- **Layer C (emit):** `emit(Action, DispatchResult, World) -> tuple[Effect, ...]` — pure effect emission. Maps handler output to status changes, comments, queue patches, and PR creations.

Each layer boundary is cached as a test seam — see `testing.md`.

## Stage 1 — Entry Point

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

## Stage 2 — Poller Wrapper

`poller.sh` (Linux, `flock`) and `poller.ps1` (Windows, `System.Threading.Mutex`) provide a process-level mutex so two cron firings can't overlap — a firing that finds a run in progress simply exits. Both fetch+reset the autoSWE repo to `origin/master`, then invoke `python autoswe.py poller --drain`.

## Stage 3 — Sync: Read API + Decide (`orch.loop._single_poll`)

For each repo in `repos.json` (or auto-discovered owned repos):

1. **Fetch API state** via `read_api(tracker, repo_cfg, cfg, bot_ids, prev_updated, force_fetch)` — the provider adapter fetches issues and comments, producing `ApiState` objects keyed by issue number. Comments carry `id` and `is_bot` set from `bot_comment_ids` membership (or body marker fallback). For issues whose `last_updated` timestamp matches the stored value (and are not in `force_fetch`), the comment fetch is skipped — `comments_fetched=False` and `comments` is empty. This avoids N API calls per poll for idle issues.

2. **For each open issue** (skipping PRs and closed issues):
   - Ensure queue entry exists (`_ensure_queue_entry`), upserting title/body/base_branch.
   - Build `TaskState` + `World` from queue entry and API snapshot.
   - Call `decide(world)` — Layer A returns an `Action`.
   - If comments were fetched this poll, update `last_comment_sync` on the queue entry. If `decide` returned `noop`, also advance `last_updated` to the issue's current provider timestamp — this enables the skip optimization on the next poll.

3. **`noop` actions** are logged and skipped. Non-noop actions proceed to dispatch (Stage 4).

4. **`post_welcome` actions** are collected and posted in Phase 4 after all decides complete.

**Input:** issue tracker API + current queue.json. **Output:** queue.json with up-to-date tasks; `Action`s ready for dispatch.

## Stage 4 — Dispatch: Run + Emit + Apply (`orch.loop._dispatch_task`)

For each non-noop `Action`:

```
1. Create running/{slug}.pid          # concurrency gate
2. Set RUNNING status + autoswe:* label # mirror for humans
3. Post progress comment              # "Dispatching `/plan`…"
4. result = run(action, world)        # Layer B — Claude handler
5. effects = emit(action, result, world)  # Layer C — pure
6. For each effect:
     post_comment → progress.finalize()   # update sticky comment in-place
     other → apply_effect()               # adapter → API call
7. _finalize_handler()                # done files, watermarks, transient cleanup
8. Delete PID file
```

The **progress comment** (via `tracking.progress.ProgressComment`) is a sticky comment: created with the dispatch status text, updated during the Claude run, then finalized with the completion/failure message. The comment ID is tracked in `bot_comment_ids`. When the run emits a todo list (via `TodoWrite` or `TaskCreate`/`TaskUpdate`), the comment body is rendered as a structured **Todo List** + **Last Command** markdown block instead of a bare tool-name string.

**Input:** queue.json (tasks with non-noop Actions). **Output:** handler result → effects applied → `autoswe_status` transition → mirrored label → bot comment.

## Stage 4.5 — Sync Conflict Resolution

When `/sync` or pre-dispatch `/fix` sync produces merge conflicts:

```
sync_branch() → conflict=True
  → coder.resolve_sync_conflicts(task, conflict_files)
    → Claude resolves markers in existing worktree
    → git add -A && git commit --no-edit (Claude executes)
    → handler pushes origin {branch}
    → DONE_SUMMARY or FAILED
  /sync: DONE_SUMMARY → synced status; FAILED → failed status
  /fix: DONE_SUMMARY → proceed to coder.run_fix(); FAILED → bail before fix
```

Key rules:
- Worktree is left in conflicted state on failure (not aborted) for debugging.
- Rebase conflicts are not resolved — return FAILED immediately (deferred).
- Resolver resumes the task's prior session for continuity.
- Plan file is read but not consumed (persists for downstream `/fix`).

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

## Stage 6 — Auto-PR

After a successful `/fix` (`autoswe_status → fixed`), if `AUTO_CREATE_PR=true` and no PR exists for the branch, `emit()` includes a `create_pr` Effect. The adapter translates it to the provider's PR creation API.

## Stage 7 — Post-Poll Bookkeeping

After all dispatches in a cycle:

1. **Backfill `bot_comment_ids`** — Any comment with `is_bot=True` but ID not yet in the queue row gets backfilled. Makes the system self-healing on the first poll after a queue wipe.

2. **`gh_closed` detection** — Issues that dropped out of the open-issues list get `gh_closed = True` and `autoswe_status = "fixed"`. Reopened issues clear the flag.

3. **Label mirror** — Terminal statuses (`fixed`, `synced`, `shipped`, `reviewed`, `failed`, `skipped`, `aborted`, `planned`, `waiting`, `error`) have their `autoswe:*` label synced on the issue. The mirror is idempotent: `set_status` is only called when the issue's current status (from labels/tags refreshed by `list_open_issues`) differs from the queue status. This avoids a write that would bump the provider's `updated_at` timestamp and defeat the comment-fetch skip optimization.

4. **Welcome comments** — `_post_pending_welcomes()` posts the welcome message to newly discovered issues, capturing the returned comment ID in `welcome_comment_id` and `bot_comment_ids`.
