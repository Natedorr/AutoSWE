# Labels — A Read-Only Mirror

## Labels Do Not Steer Anything

The run state for a task lives in `data/queue.json` as the `autoswe_status` enum (see `data-model.md`). That — together with `pending_command`, which is derived from issue comments — is what the dispatch loop reads.

`autoswe:*` labels on the issue are written by autoSWE *after* it changes `autoswe_status`, purely so a human can see what's going on. autoSWE never reads a label to decide what to do. **Adding, removing, or changing an `autoswe:*` label by hand has no effect on the workflow** — to steer a task, post a comment with a slash command.

(Historical note: an earlier design treated labels as the source of truth. That was reversed. The one sanctioned exception — seeding `autoswe_status` from a label for pre-existing tasks — has been retired; all deployed queues have been through that migration.)

Labels are set via `tracker.set_status()` → `IssueTracker` protocol: GitHub uses `PUT /repos/{o}/{r}/issues/{n}/labels` (replace whole label set); Azure uses JSON-Patch on `System.Tags`. Both fetch current, drop existing `autoswe:*`, keep everything else, write combined. So writing the mirror never clobbers a user's other labels.

## Label Schema

All labels use the `autoswe:` prefix. Defined in `tracking/labels.py:AUTOSWE_LABELS`. Each one maps 1:1 to an `autoswe_status` value.

| Label | `autoswe_status` | Color | Means |
|-------|------------------|-------|-------|
| `autoswe:pending` | `pending` | `0075ca` | Queued; the next dispatch run will pick it up |
| `autoswe:planning` | `planning` | `d93f0b` | Planning in progress |
| `autoswe:fixing` | `fixing` | `d93f0b` | Fix in progress |
| `autoswe:syncing` | `syncing` | `d93f0b` | Sync in progress |
| `autoswe:reviewing` | `reviewing` | `d93f0b` | Review in progress |
| `autoswe:shipping` | `shipping` | `d93f0b` | PR creation in progress |
| `autoswe:planned` | `planned` | `0e8a16` | Plan ready, waiting for /fix |
| `autoswe:fixed` | `fixed` | `ededed` | Fix completed |
| `autoswe:synced` | `synced` | `ededed` | Sync completed |
| `autoswe:shipped` | `shipped` | `ededed` | PR created |
| `autoswe:reviewed` | `reviewed` | `ededed` | Review completed |
| `autoswe:waiting` | `waiting` | `fbca04` | Claude asked a question; awaiting a reply |
| `autoswe:failed` | `failed` | `d73a4a` | Handler errored, or a limit guard tripped |
| `autoswe:skipped` | `skipped` | `ffffff` | `/skip` |
| `autoswe:aborted` | `aborted` | `e99695` | `/abort` |
| `autoswe:error` | `error` | `b60205` | Infrastructure error (dispatch crashed, OOM, etc.) |

## `autoswe_status` Transitions

The transitions below happen by writing `autoswe_status` in `queue.json`; the label is updated to match in the same step.

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

- **→ pending** (set by `decide()`):
  - first sight of an issue carrying a slash command (body or comment), or
  - a user comment with a slash command whose ID is *newer than `last_dispatched_command_id`*, on a task in a COMPLETED status (`fixed`/`synced`/`shipped`/`reviewed`)/`failed`/`skipped`/`planned`, or
  - any user reply on a task in `waiting`/`planned` (plain text → `pending_command = None`, `pending_user_reply = text`).
- **→ RUNNING statuses** (`planning`/`fixing`/`syncing`/`reviewing`/`shipping`; set by `_dispatch_task()`): only from a non-noop Action. PID file is created first, then the status flips. The specific running status depends on the action kind (`plan` → `planning`, `fix` → `fixing`, `sync_branch` → `syncing`, `review` → `reviewing`, `ship_pr` → `shipping`).
- **→ planned**: planner returned `"PLAN_READY"` (MCP `post_plan` fired, or — deprecated fallback — an `<AUTOSWE_PLAN>` block / native plan file).
- **→ waiting**: planner returned `"WAITING: …"` (MCP `post_question`, an AskUserQuestion, or — deprecated fallback — an `<AUTOSWE_QUESTIONS>` block / no parseable plan).
- **→ COMPLETED statuses** (`fixed`/`synced`/`shipped`/`reviewed`): coder returned `"DONE*"` for `/fix` → `fixed`, or `/sync` succeeded → `synced`, or `/pr` succeeded → `shipped`, or `/review` succeeded → `reviewed`, or the issue was found closed at refresh time → `fixed`.
- **→ failed**: handler returned `"FAILED: …"`, or `sync`'s attempt/time guard tripped.
- **→ skipped**: `/skip`.
- **→ aborted**: `/abort`.

RUNNING statuses are **protected**: `decide()` only re-opens a task from a COMPLETED status (`fixed`/`synced`/`shipped`/`reviewed`)/`failed`/`skipped`/`planned`/`waiting`, never from a RUNNING status — so a comment posted mid-run can't yank a task out from under the agent. (The label mirror inherits this; it's not the label doing the protecting.)

## Bot Comment Convention

Every comment autoSWE posts ends with `<!-- autoswe-bot -->` (`BOT_MARKER` in `tracking/comments.py`). This marker is a **fallback** for bot detection — the primary mechanism is `bot_comment_ids` in the queue row, which the adapter uses to set `NormalizedComment.is_bot`. The marker handles pre-existing bot comments from before the comment-ID schema change (see `docs/autoswe/data-model.md`).

### Detection Helpers

| Function | File | Purpose |
|----------|------|---------|
| `_is_autoswe_bot_comment(comment)` | `tracking/comments.py` | True if `is_bot` flag set or body contains `BOT_MARKER` or matches `_BOT_CONTENT_PATTERNS` |
| `_find_last_completion_id(comments)` | `tracking/comments.py` | Last `"Completed with command"` comment ID — restart anchor for COMPLETED statuses/`failed`/`skipped` |
| `_find_last_bot_comment_id(comments)` | `tracking/comments.py` | Last bot comment ID of any kind — auto-resume anchor for `waiting`/`planned` |
| `_find_last_completion(comments)` | `tracking/comments.py` | Timestamp fallback (legacy compat, TODO: remove after queue migration) |
| `_find_last_bot_comment_ts(comments)` | `tracking/comments.py` | Timestamp fallback (legacy compat, TODO: remove after queue migration) |
