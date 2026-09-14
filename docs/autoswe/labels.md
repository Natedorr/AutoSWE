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
| `autoswe:reviewed` | `reviewed` | `ededed` | Review approved (LGTM) — `/pr` allowed |
| `autoswe:review_failed` | `review_failed` | `fbca04` | Review verdict "Needs changes" — `/pr` blocked until `/fix` |
| `autoswe:review_blocked` | `review_blocked` | `d73a4a` | Review verdict "Blocked" (CRITICAL findings) — `/pr` blocked until `/fix` |
| `autoswe:test_failed` | `test_failed` | `d73a4a` | Post-fix test gate red: fix was committed/pushed but the branch suite is failing — `/pr` blocked until `/fix` re-runs the gate green |
| `autoswe:ci_failed` | `ci_failed` | `d73a4a` | CI red on the pushed branch (remote build watch) — `/pr` blocked until CI is green or a human `/fix` addresses it |
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
- **→ waiting**: planner returned `"WAITING: …"` (MCP `post_question`, a standalone `AskUserQuestion` comment, or — deprecated fallback — an `<AUTOSWE_QUESTIONS>` block / no parseable plan).
- **→ COMPLETED statuses** (`fixed`/`synced`/`shipped`/`reviewed`): coder returned `"DONE*"` for `/fix` → `fixed`, or `/sync` succeeded → `synced`, or `/pr` succeeded → `shipped`, or `/review` returned an **LGTM** verdict → `reviewed`, or the issue was found closed at refresh time → `fixed`.
- **→ review_failed / review_blocked** (non-terminal resting states): `/review` returned a gating verdict. `_map_done_to_status` parses the `## Verdict` section of the review report — `Needs changes` → `review_failed`, `Blocked` → `review_blocked`. In both states `decide()` refuses `/pr`; a `/fix` is accepted (it addresses the findings and, via the `rereview_after_fix` flag, triggers an automatic re-review before shipping). See `handlers.md`.
- **→ test_failed** (non-terminal resting state — one of the two `RECOVERABLE_GATE_STATUSES`, issue #245 plan §2.5): the post-fix test gate ran the branch's test suite after commit/push and it was red. The coder returns `"TESTS_FAILED\t<detail>\t<sha>"` (the work is committed and pushed — a red gate never loses the agent's work), `emit()` persists the failure (`test_failed_sha`, `test_failure_detail`) and posts a comment. With `AUTO_FIX_ON_GATE_FAILURE` on (default), `decide()`'s `_decide_test_gate` helper auto-dispatches a `/fix` on the very next poll (no read step needed — the local signal is already known), sharing the `gate_attempt_count` budget and per-commit watermark with the CI signal below; once the budget is exhausted it stays parked with a one-time "budget exhausted" comment (`test_gate_limit_notified`) asking for a human `/fix`. `decide()` refuses `/pr` until a `/fix` re-runs the gate green; restarts from `test_failed` start a fresh attempt budget, like a review verdict. See `handlers.md` (post-fix test gate).
- **→ ci_failed** (non-terminal resting state — the other `RECOVERABLE_GATE_STATUSES` member, issue #245 plan §2.3-§2.5): the read-only CI watch (`providers.adapter.read_ci`, populates `World.ci`) observes a red build on a task resting in `fixed`/`shipped`/`synced`/`ci_failed` and no slash command arrived this poll. With `AUTO_FIX_ON_GATE_FAILURE` on (default), `decide()`'s `_decide_ci` helper auto-dispatches a `/fix` instead of parking the task, bounded by the four brakes in `safeguards.md`; `ci_failed` itself is now reached only when the shared gate auto-fix budget is exhausted (`mark_failed_limit(limit_reason="ci")`, asking for a human `/fix`) or `AUTO_FIX_ON_GATE_FAILURE=false` for the repo, in which case the task is parked directly with a comment carrying the failing checks and run link. A repeated identical failure (same head SHA) doesn't re-comment. `decide()` refuses `/pr` until CI goes green (auto-clears back to the pre-failure status with a "CI green" comment, or re-fires a deferred `create_pr` — see below) or a human `/fix`/`/retry` addresses it — restarts use the same `SHIPPING_BLOCKING_STATUSES` machinery as `test_failed`. A `CIStatus.state == "error"` (API unreachable) posts a one-time warning comment and leaves the status untouched — never a false pass or fail; `stale=True` also never triggers an auto-fix.
- **pr_deferred auto-resume** (issue #245 plan §2.6, no label change): when a `create_pr` effect's preflight defers on pending/failing/unreachable CI, the task stays at its current status (typically `fixed`) with `pr_deferred=True` instead of asking the user to re-post `/pr`. The next green CI observation makes `decide()` emit `Action(kind="retry_deferred_pr")`, re-firing `create_pr`; `find_existing_pr`'s idempotency guard makes the re-emit safe.
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
