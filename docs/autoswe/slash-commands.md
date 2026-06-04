# Slash Commands

Comments are the only steering input. A slash command at the start of a comment line (by the issue OWNER or AUTHOR) is what moves a task; an `autoswe:*` label is output only — adding or removing one by hand does nothing (`labels.md`). The "Pre-state"/"Post-state" columns below are `autoswe_status` values, which `sync`/`dispatch` write and the labels mirror.

## Command Table

| Command | Syntax | Pre-state | Post-state | Agent? | Who can issue |
|---------|--------|-----------|------------|---------|---------------|
| `/plan` | `/plan [--branch <name>]` | any | `planned` or `waiting` | Yes (read-only) | OWNER/AUTHOR |
| `/fix` | `/fix [--branch <name>] [with <guidance>]` | any | `fixed` or `failed` | Yes (write access) | OWNER/AUTHOR |
| `/pr` | `/pr` | `fixed` (with commits) | `shipped` | No | OWNER/AUTHOR |
| `/sync` | `/sync` | any (with worktree) | `synced` or `failed` | Only on conflict | OWNER/AUTHOR |
| `/retry` | `/retry` | `failed` | `pending` → handler → final state | Yes (replayed) | OWNER/AUTHOR |
| `/skip` | `/skip` | any | `skipped` | No | OWNER/AUTHOR |
| `/abort` | `/abort` | any | `aborted` | No | OWNER/AUTHOR |
| `/review` | `/review [with <guidance>]` | any | `reviewed` | Yes (read-only) | OWNER/AUTHOR |

## Parsing (`commands/parser.py:parse_slash_command()`)

Scans each line of text (issue body or comment). Commands must be at the **start of a line** (optional leading backtick). Embedded commands (e.g., `` Post `/retry` to try again ``) are ignored because they don't start a line.

Returns `(command, guidance, branch)` or `None`.

### Modifiers

| Modifier | Example | Effect |
|----------|---------|--------|
| `--branch <name>` | `/plan --branch develop` | Sets `plan_branch` on task (only if not already set — subsequent `--branch` flags are ignored) |
| `with <guidance>` | `/fix with performance focus` | Appends guidance to fix prompt via `{{GUIDANCE_BLOCK}}` |
| Both | `/fix --branch main with hotfix` | Branch + guidance combined |

### Regex Patterns

- Command: `r"/(?:fix|plan|pr|retry|skip|sync|abort)"` (case-insensitive, at line start)
- Branch: `r"--branch\s+([\w][\w\-./]+)"`

## Multi-Command-Last-Wins Rule

When multiple slash commands appear in comments (or the issue body), the **last** command in the file wins within a single text block. Across comments, the most recent comment with a slash command wins (`decide.py:_find_slash_command()` sorts comments by `created_at` descending, returns the first match).

## Auto-Resume Rule

When an issue is in `waiting` or `planned` state:

1. `decide()` finds the last bot comment ID (`_find_last_bot_comment_id()`)
2. Any non-bot user comment with an ID newer than both `last_consumed_reply_id` and the last bot comment ID triggers auto-resume
3. If the user comment contains a slash command → `Action(kind=that_command)`
4. If the user comment is plain text → `Action(kind=resume, user_reply_text=text)`
5. The dispatch loop runs the action and emits Effects that advance `autoswe_status`

## `/retry` Replay Semantics

When `/retry` action is run (`orch/run.py:_run_retry()`):

1. `decide()` sets `attempt_count = 1` (resets the counter)
2. `run()` looks at `last_dispatched_command` for the last substantive command (not `/pr`, `/sync`, `/retry`, `/skip`, or `/abort`)
3. Replays that command via the appropriate planner/coder/ship handler
