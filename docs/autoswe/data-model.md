# Data Model

## `queue.json` — the Run Map

Stored at `data/queue.json`. Managed via `LockedQueue` (cross-platform file lock via `portalocker`). A dict keyed by task slug.

This file is **the source of truth for what autoSWE runs**. The poll loop writes it from issue comments; dispatch reads it. It is *also*, today, the de-facto history store — the poll loop upserts every issue it sees and never deletes a task, so `queue.json` accumulates COMPLETED (`fixed`/`synced`/`shipped`/`reviewed`)/`skipped`/`gh_closed` tasks indefinitely. The dispatch loop ignores those (only dispatches non-noop Actions), so they're harmless, but the file grows without bound. (Direction: the run map should only carry actionable tasks; long-term history, if it's wanted, belongs in a separate store or a periodic prune. See `debugging.md` for a manual prune.)

### The state field: `autoswe_status`

`autoswe_status` is the per-task state enum. It is **the value the dispatch loop keys off**. The `autoswe:*` label on the issue is set to mirror it (`labels.md`) — the label is output, never input.

| Value | Meaning | Dispatchable? |
|-------|---------|---|
| `null` / absent | Brand-new task with no command yet | No |
| `pending` | A command is queued (`pending_command` set) | **Yes** |
| `planning` | Planning in progress (agent run active) | No (protected) |
| `fixing` | Fix in progress (agent run active) | No (protected) |
| `syncing` | Sync in progress (agent run active) | No (protected) |
| `reviewing` | Review in progress (agent run active) | No (protected) |
| `shipping` | PR creation in progress (agent run active) | No (protected) |
| `planned` | Plan posted; waiting for `/fix` or a reply | No |
| `fixed` | Fix completed | No |
| `synced` | Sync completed | No |
| `shipped` | PR created | No |
| `reviewed` | Review completed | No |
| `waiting` | Claude asked a question; waiting for a reply | No |
| `failed` | Handler errored, or a limit guard tripped | No |
| `error` | Infrastructure error (dispatch crash, OOM, unhandled exception) | No |
| `skipped` | `/skip` | No |
| `aborted` | Explicit `/abort` | No |

A non-`pending` task only becomes dispatchable again when `decide()` flips it — which happens when a *new* user comment (newer comment ID than `last_consumed_reply_id`) carries a slash command, or when a user replies to a `waiting`/`planned` task. A blank/`null` status, or a non-`pending` status with no fresh command, just means "nothing to do this round" — a later poll can change that.

**Comment IDs are the unit of identity** for the state machine. Watermarks (`last_dispatched_command_id`, `last_consumed_reply_id`) compare provider comment IDs — not timestamps — so clock skew and identical-second ties cannot cause incorrect decisions.

### Persisted Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Provider-prefixed slug, e.g. `gh:owner_repo_42` or `ado:org_proj_repo_7` |
| `owner` | `str` | Repo owner (GitHub) or `org/proj` (Azure) |
| `repo` | `str` | Repo name |
| `issue_number` | `int` | Issue / work-item number |
| `title` | `str` | Issue title (refreshed each poll) |
| `body` | `str` | Issue body (refreshed each poll) |
| `base_branch` | `str` | Base branch from `repos.json`, else `main` |
| `plan_prompt` | `str` | Custom plan prompt path from `repos.json` (optional, resolved against AUTOSWE_DIR) |
| `fix_prompt` | `str` | Custom fix prompt path from `repos.json` (optional, resolved against AUTOSWE_DIR) |
| `review_prompt` | `str` | Custom review prompt path from `repos.json` (optional, resolved against AUTOSWE_DIR) |
| `conflict_resolution_prompt` | `str` | Custom conflict resolution prompt path from `repos.json` (optional, resolved against AUTOSWE_DIR) |
| `plan_branch` | `str` | Override branch from `/plan --branch <name>` (set once; later `--branch` flags ignored) |
| `provider` | `str` | `"github"` or `"azure"` |
| `autoswe_status` | `str \| None` | Run-state enum (see above). **Source of truth.** |
| `session_id` | `str` | Agent session ID (Claude Code or Codex); used to resume the planner/coder session |
| `attempt_count` | `int` | Dispatch attempts; incremented by `decide()` on each restart; reset to 1 by `/retry` |
| `first_dispatched_at` | `str` | ISO 8601; set on first dispatch, reset on terminal status (wall-clock guard anchor) |
| `last_dispatched_command` | `str \| None` | The slash command string last dispatched (e.g. `/plan`) |
| `last_dispatched_command_id` | `int \| None` | Comment ID of the slash command last dispatched |
| `last_consumed_reply_id` | `int \| None` | Comment ID of the latest user input folded into the state machine |
| `last_phase` | `str` | `"plan"` or `"fix"` — determines which handler to resume |
| `suppress_welcome` | `bool` | True once the welcome comment has been posted |
| `welcome_comment_id` | `int \| None` | Comment ID of the welcome message (if posted) |
| `progress_comment_id` | `int \| None` | Sticky progress comment ID for the in-flight dispatch. Cleared on any clean return (finalize), so it lingers **only** after a crash — a `/retry` from the `error` state re-uses this comment instead of posting a new one. See [handlers.md](handlers.md). |
| `bot_comment_ids` | `list[int]` | Every comment ID autoSWE has posted on this issue |
| `pr_number` | `int \| None` | Cached PR number |
| `fix_summary` | `str \| None` | Extracted from `DONE_SUMMARY` on fix/retry completion; persisted in the queue so PR creation can include it in the body |
| `rereview_after_fix` | `bool` | Set by `emit()` when a `/fix` dispatched from `review_failed`/`review_blocked` completes. `decide()` then auto-dispatches `/review` on the next poll (and `emit()` clears it when the review runs) so the gating verdict is re-checked before `/pr`. |
| `gh_closed` | `bool` | True once the issue is observed closed; cleared if it's reopened; task is never auto-purged |
| `created_at` | `str` | ISO 8601; when the task was first created |
| `last_synced` | `str` | ISO 8601; last poll time |
| `last_updated` | `str \| None` | ISO 8601; the provider's issue timestamp (`updated_at` / `System.ChangedDate`) last observed when comments were fetched and the issue was quiescent (noop). Used to skip comment fetches for unchanged issues. |
| `last_comment_sync` | `str \| None` | ISO 8601; last time comments were actually fetched from the API for this issue. |

### Transient Fields (set during poll, consumed by dispatch, NOT persisted)

| Field | Type | Description |
|-------|------|-------------|
| `pending_command` | `str` | The slash command to run next, derived from comments. Absent (None) ⇒ nothing to run unless `pending_user_reply` is set. |
| `pending_guidance` | `str` | Guidance text from `/fix with <guidance>` |
| `pending_user_reply` | `str` | The user's plain-text reply on a `waiting`/`planned` task. |
| `plan_file_path` | `str` | Absolute path to the native `~/.claude/plans/*.md` file written by the planner. Set by `planner.run_plan()` on `PLAN_READY`; consumed (popped) by `coder.run_fix()` on first use. |
| `review_file_path` | `str` | Absolute path to the `~/.claude/reviews/<slug>.md` file written by the reviewer. Set by `reviewer.run_review()` on `REVIEW_READY`; consumed (popped) by `build_fix_prompt()` / `build_plan_prompt()` on first use (pop-after-first-use lifecycle). |
| `_token` | `str` | GitHub or Azure PAT; injected at dispatch time, never written to disk |
| `_guard_blocked` | `bool` | Set when a limit guard trips; suppresses comment re-scans until a new command appears |
| `_comment_id` | `int` | Progress comment ID for the current in-flight dispatch (runtime mirror of the persisted `progress_comment_id`, passed to the MCP comment server as `AUTOSWE_COMMENT_ID`) |
| `_minimal_posting` | `bool` | Whether minimal posting is enabled for the current dispatch |

## Orchestrator Types (`autoswe/orch/types.py`)

All orchestrator types are **frozen dataclasses** — immutable snapshots at each pipeline boundary.

### `ApiState` — Provider API snapshot

```python
@dataclass(frozen=True)
class ApiState:
    issue: NormalizedIssue
    comments: tuple[NormalizedComment, ...]
    open_pr_numbers: tuple[int, ...] = ()
    comments_fetched: bool = True
```

`comments_fetched` indicates whether the comments were actually fetched from the API. When `False`, `comments` is empty and the issue was skipped because its `last_updated` timestamp matched the stored value (unchanged since last poll).

Produced by the adapter's `read_api()`. Everything the state machine needs from the provider, normalized to a provider-agnostic shape.

### `TaskState` — Queue snapshot

```python
@dataclass(frozen=True)
class TaskState:
    slug: str
    owner: str
    repo: str
    issue_number: int
    title: str
    body: str
    status: str | None               # autoswe_status
    plan_branch: str | None
    base_branch: str
    attempt_count: int
    first_dispatched_at: str | None
    last_dispatched_command: str | None
    last_dispatched_command_id: int | None
    last_consumed_reply_id: int | None
    session_id: str | None
    pr_number: int | None
    guard_blocked: bool
    gh_closed: bool
    pending_command: str | None
    pending_guidance: str | None
    pending_user_reply: str | None
    suppress_welcome: bool = False
    welcome_comment_id: int | None = None
    progress_comment_id: int | None = None
    bot_comment_ids: tuple[int, ...] = ()
    last_phase: str = "plan"
    resume_phase: str | None = None
    created_at: str = ""
    last_synced: str = ""
    provider: str = "github"
    creator_login: str = ""
    plan_file_path: str | None = None
    review_file_path: str | None = None
    fix_summary: str = ""
    rereview_after_fix: bool = False
```

Built from the queue entry by `TaskState.from_queue(slug, entry)` using the `TASK_FIELDS` registry in `types.py`. The registry is the single source of truth for field ↔ queue key ↔ default mappings — the drift test (`tests/test_no_field_drift.py`) fails CI if a field is added to one without the other. Transient fields (`_token`, `_comment_id`) are excluded — they belong in the dispatch runtime, not the decision boundary.

### `World` — Full decision context

```python
@dataclass(frozen=True)
class World:
    api: ApiState
    task: TaskState
    cfg: dict
    repo_cfg: dict
```

Passed to `decide()` and `emit()`. Everything the state machine needs, no I/O required.

### `Action` — What to do (Layer A output)

```python
@dataclass(frozen=True)
class Action:
    kind: Literal["plan", "fix", "ship_pr", "sync_branch",
                  "retry", "skip", "abort", "noop",
                  "post_welcome", "advance_watermark",
                  "mark_failed_limit",
                  "review"]
    slug: str
    plan_branch: str | None = None
    guidance: str | None = None
    resume_session_id: str | None = None
    attempt_count: int = 0
    triggering_comment_id: int | None = None
    user_reply_text: str | None = None
    limit_reason: Literal["attempts", "time"] | None = None
```

Provider-agnostic. Cached at the test seam between Layer A (decide) and Layer B (run) / Layer C (emit). `limit_reason` is set only on `kind="mark_failed_limit"` to record which guard tripped (attempt count vs. wall-clock).

### `Effect` — What to write back (Layer C output)

```python
@dataclass(frozen=True)
class Effect:
    kind: Literal["post_comment", "update_comment", "set_status",
                  "patch_queue", "assign", "create_pr", "noop"]
    body: str | None = None
    comment_id: int | None = None
    status: str | None = None
    queue_patch: dict | None = None
    pr_title: str | None = None
    pr_body: str | None = None
    pr_head: str | None = None
    pr_base: str | None = None
```

Each Effect is one API call or queue mutation. The adapter decides how to express it (GH labels vs ADO tags, markdown vs HTML, etc.).

### `DispatchResult` — Layer B output (defined in `autoswe/orch/run.py`)

```python
@dataclass(frozen=True)
class DispatchResult:
    done_content: str          # PLAN_READY, DONE_SUMMARY\t...\t<sha>, FAILED: ..., etc.
    cost_usd: float | None = None
    duration_seconds: float = 0.0
    session_id: str | None = None
    plan_file_path: str | None = None   # Set by planner on PLAN_READY
    review_file_path: str | None = None  # Set by reviewer on REVIEW_READY
```

Returned by `run()` for agent-backed actions; pure actions (skip, abort, noop, post_welcome, advance_watermark) return `None`. Note this dataclass lives in `orch/run.py`, *not* `orch/types.py` — `types.py` only re-exports `RunResult`. `run()` builds it from a `HandlerResult` via `_to_dispatch()`.

## Backend Contracts (`autoswe/harness/backends/base.py`)

The harness layer has two output dataclasses, both re-exported from `autoswe/harness/runner.py` for backward-compatible imports. See [harnesses.md](harnesses.md) for how backends are selected.

### `RunResult` — raw backend output

```python
@dataclass
class RunResult:
    text: str
    session_id: str | None
    subtype: str | None              # "success", "error", "error_max_turns", "timeout", …
    cost_usd: float | None = None
    duration_seconds: float = 0.0
    plan_file_path: str | None = None
    plan_posted: bool = False        # MCP post_plan fired (Claude Code only)
    question_posted: bool = False    # MCP post_question fired (Claude Code only)
```

What a `CodingBackend.run(spec)` returns — the unparsed result of one agent run. Supports tuple unpacking (`text, session_id, subtype = result`) for legacy callers. `plan_posted` / `question_posted` are only meaningful when the backend advertises the `"mcp"` capability; handlers gate on `runner.backend_has_capability(harness, "mcp")` before trusting them and fall back to text parsing otherwise.

### `HandlerResult` — interpreted handler output

```python
@dataclass
class HandlerResult:
    done_content: str                # PLAN_READY, DONE_SUMMARY\t...\t<sha>, FAILED: ..., etc.
    cost_usd: float | None = None
    duration_seconds: float = 0.0
    session_id: str | None = None
    plan_file_path: str | None = None
    review_file_path: str | None = None
```

What `planner` / `coder` / `reviewer` / `ship` return after interpreting a `RunResult` into a done-content verdict. `run()` (Layer B) converts it to a `DispatchResult` before handing off to `emit()`.

### `RunSpec` — backend invocation intent

`runner.run(...)` packs its kwargs into a `RunSpec` (also in `backends/base.py`) and dispatches to the resolved backend. The key field is **`mode`** — a generic intent string (`"plan"`, `"read_only"`, `"read_write"`) that each backend translates into its own configuration (Claude Code permission modes/tool sets, Codex `--sandbox` flags). It supersedes the legacy `permission_mode` + `allowed_tools` + `disallowed_tools` triple.

## Normalized Dataclasses (`autoswe/providers/base.py`)

### `NormalizedIssue`

```python
@dataclass
class NormalizedIssue:
    number: int
    title: str
    body: str
    owner: str                       # org / project owner
    repo: str                        # repo / team project
    state: str = "open"              # "open" or "closed"
    base_branch: str = "main"
    labels: list[str] = None
    status: str | None = None        # the autoswe:* label read off the issue
    comments: list[NormalizedComment] = None
    is_pull_request: bool = False
    last_updated: str | None = None  # ISO 8601; provider's issue change timestamp
```

`last_updated` is set from `updated_at` (GitHub) or `System.ChangedDate` (Azure) by the tracker's `_to_normalized()` method. The orchestrator uses it in `read_api()` to skip comment fetches for unchanged issues.

GitHub fills `state` from the issue's `state` field; Azure maps `System.State` (`Closed`/`Done`/`Removed` → `"closed"`, otherwise `"open"`).

### `NormalizedComment`

```python
@dataclass
class NormalizedComment:
    body: str
    created_at: str                  # ISO 8601
    author_login: str = ""           # "BOT", "OWNER", "AUTHOR", or raw login
    id: int | None = None            # provider's comment ID — state machine identity unit
    is_bot: bool = False             # set by adapter from bot_comment_ids membership
```

The `id` field is the **primary watermark** for the state machine. The `is_bot` flag is set by the adapter from `bot_comment_ids` membership (with body marker fallback for pre-existing bot comments). Orchestrator code uses `is_bot` exclusively — no content pattern matching in the decision layer.

### `PRResult`

```python
@dataclass
class PRResult:
    url: str
    number: int | None = None
```

## PID and Done Files (`running/` directory)

### `running/{slug_to_filename(slug)}.pid`

One line: the process PID. Created before the handler runs, deleted after. Used for concurrency control (`MAX_CONCURRENT` gate, `is_repo_locked()`, `is_task_running()`). Stale PID files (dead processes) are auto-cleaned.

### `running/{slug_to_filename(slug)}.done`

The raw handler return string (`"DONE_SUMMARY\t…\t<sha>"`, `"FAILED: timeout"`, …). A debugging artifact — not read by the pipeline.

### `running/{slug_to_filename(slug)}.result.json`

Structured JSON result file: command, status, done_content, duration, cost, commit_sha, pr_number, session_id.

## Slug Format (`autoswe/core/slug.py`)

```python
make_slug(provider, parts, issue_number) → str
slug_to_filename(slug) → str
```

- **GitHub:** `gh:owner_repo_N` → filename `gh_owner_repo_N`
- **Azure:** `ado:org_proj_repo_N` → filename `ado_org_proj_repo_N`
- `slug_to_filename()` replaces `:` → `_` and `/` → `_` for cross-platform safety
