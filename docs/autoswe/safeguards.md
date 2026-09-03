# Safeguards

## Deployment Model (the first "safeguard")

autoSWE runs the coding agent with full read/write/`Bash` access for `/fix` (and `/sync` conflict resolution) **on purpose**. The expectation is that it runs on a **dedicated, isolated machine** that does nothing else: it can clone repos, write to `autoswe/issue-*` branches, and push them — and that's the whole blast radius. Don't run autoSWE on a shared workstation, a build box with secrets for other systems, or anywhere a compromised agent run could do damage beyond "messed up a feature branch." The free-permissions choice is only safe under that assumption — treat the isolation as a hard requirement, not a nice-to-have.

The orchestrator's own privilege split still holds inside that machine. Handlers express intent as a generic **`mode`** (see [harnesses.md](harnesses.md)) plus *genuinely-extra* `extra_tools`; the backend translates `mode` into its own tool sets. The tool lists below describe the **Claude Code backend's** translation (these constants live in `backends/claude_code.py`, not the harness-agnostic base — S6 / issue #169 F-10):

- `/plan` and `resume_plan` → `mode="plan"`, tools `["Read", "Glob", "Grep"]` + `PROGRESS_TOOLS` — read-only. Claude Code: plan permission mode (native plan files in `~/.claude/plans/`), with `Write`/`Edit` blocked by the `can_use_tool` callback and `Agent` excluded so sub-agents can't bypass containment.
- `/fix` → `mode="read_write"` — full access (the backend supplies `["Read", "Edit", "Write", "Bash", "Glob", "Grep"]` + the agent/progress tools; the handler adds only the inline-comment tool when a PR exists). Claude Code: `bypassPermissions`. The `can_use_tool` callback still intercepts `AskUserQuestion` under `bypassPermissions` (the CLI routes user-interaction tools to the callback even when allow rules match), so the fixer can pause via `autoswe:waiting` — the SDK's `CanUseToolShadowedWarning` for this setup is a false positive and is filtered in the backend (issue #190).
- `/sync` conflict resolution → same as `/fix` (minus `AskUserQuestion`, kept autonomous via `disallowed_tools_override`).
- `/review` → `mode="read_only"`, tools `["Read", "Glob", "Grep"]` + `AGENT_TASK_TOOLS` — read-only.

**Claude Code** translates `mode` into a permission mode + tool sets, so the read-only guarantee for `/plan` and `/review` is enforced by gating each tool call via `can_use_tool`.

**Codex** takes a different posture (issue #129): it does **not** translate `mode` into a `--sandbox` level. `mode` is still accepted for contract parity with Claude Code, but it has no effect on the Codex CLI flags — the previous per-mode `--sandbox` mapping was removed because it was dead weight (the always-on bypass flag neutralized it). Instead every Codex run (all modes, fresh and resume) emits `--dangerously-bypass-approvals-and-sandbox` by default, granting full write + network access. That is controlled by the explicit `bypass_approvals` profile flag (default `true`) / `CODEX_BYPASS_APPROVALS_AND_SANDBOX` env var — see the "Sandbox / bypass policy (issue #129)" section in [harnesses.md](harnesses.md#codex-phase-4). So for Codex, the machine-isolation boundary above **is** the real boundary: `bypass_approvals: false` is the escape hatch for shared hosts, but even then Codex falls back to its own default sandbox/approval policy rather than a per-mode read-only sandbox.

### Repo-supplied MCP servers, hooks, skills, and tools load by design

The Claude Code backend runs on the Claude Agent SDK's default settings: it passes its own `mcp_servers` (the `autoswe_comment` and, when a PR exists, `autoswe_inline_comment` comment servers from `autoswe/harness/mcp_config.py`) but **does not** set `strict_mcp_config` (default `False`) or `setting_sources` (default = all sources). As a result, when the agent runs inside a target repo's worktree, the SDK *also* loads that repo's:

- `.mcp.json` → additional MCP servers and their tools
- `.claude/settings.json` → hooks (e.g. `PreToolUse` shell commands) that run in the session
- `.claude/skills`, `.claude/agents`, `.claude/commands`, and `CLAUDE.md` → project instructions and on-demand skills

This is **intentional, not accidental**. autoSWE's deployment model (above) is a dedicated, isolated machine, so untrusted-repo MCP servers and hooks executing inside autoSWE sessions is acceptable *by design* — the blast radius is still "a repo we already chose to process, on a machine that does nothing else." The same reasoning justifies the free `Bash`/edit permissions: isolation, not tool gating, is the boundary.

**autoSWE's own MCP servers use unique names, so collisions are not expected in practice.** They are passed via `options.mcp_servers` (the `autoswe_comment` / `autoswe_inline_comment` names) and a target repo's `.mcp.json` servers load alongside them. The shipped SDK docs (per `docs/claude-agent-sdk/mcp.md`, "Scope hierarchy and precedence") only rank *file* scopes (local > project > user > plugin > claude.ai connectors); they do not specify the precedence between a programmatic `options.mcp_servers` entry and a same-named `.mcp.json` entry. If a collision ever becomes a concern, use a name distinct from the repo's — the autoSWE server names are stable, so this is a one-time rename.

**Opting a repo out (not wired up yet).** Loading a repo's MCP/hook/skill content is the default and there is currently no autoSWE config switch for it. If that is ever needed, the one-line SDK change to make a single run ignore all filesystem MCP/settings for that repo is to pass `strict_mcp_config=True` **and** `setting_sources` without `"project"` to `ClaudeAgentOptions` in `autoswe/harness/backends/claude_code.py` (see `docs/claude-agent-sdk/agent-sdk/mcp.md` and `docs/claude-agent-sdk/agent-sdk/claude-code-features.md`). That would drop the repo's `.mcp.json` servers and `.claude/settings.json` hooks while keeping autoSWE's injected servers.

On the **Claude Code backend**, `PROGRESS_TOOLS` (`TodoWrite`, `TaskCreate`, `TaskUpdate`, `TaskGet`, `TaskList`, `TaskStop`) are available in every phase. `AGENT_TASK_TOOLS = [*PROGRESS_TOOLS, "Agent"]` is used only for `/fix`, `/sync` conflict resolution, and `/review` — phases where sub-agent spawning is needed and safe. Plan phase uses `PROGRESS_TOOLS` directly to prevent `Agent` sub-agent escapes. Both constants live in `backends/claude_code.py` (Claude-specific tool names) and are re-exported from the `backends` package for importers that reach for them there; the harness-agnostic base no longer defines them (S6 / issue #169 F-10).

## Who Can Steer

Slash commands are only honored from users in the `ALLOWED_AUTHORS` allowlist (global config or per-repo `allowed_authors` override). An empty allowlist (the default) allows everyone. When an allowlist is set:

- Slash commands from unauthorized users are silently ignored (both in comments and issue body)
- Issues created by unauthorized users are silently skipped — autoSWE will not process them
- `auto_dispatch_new` respects the allowlist — unauthorized creators' issues are not auto-dispatched

A label is never a steering input (`labels.md`).

## `MAX_CONCURRENT` PID-File Gate

`count_running_jobs()` counts `.pid` files in `running/` whose processes are actually alive; the dispatch loop breaks immediately once `count >= MAX_CONCURRENT` (default 1). Stale PID files (dead processes) are auto-cleaned. Additionally `is_repo_locked(owner, repo, provider)` blocks a second task in the same repo from running concurrently (matches the slug-prefix `.pid` pattern).

## `MAX_ATTEMPTS` Per Issue

`attempt_count` is a **retry budget**: it bounds how many times work that keeps failing gets re-run, not how many phases an issue goes through. `decide()` computes it per restart as follows:

- **Fresh budget (→ 1)**: restarting from a *successful* rest — any completed status (`fixed`/`synced`/`shipped`/`reviewed`) or a review verdict resting state (`review_failed`/`review_blocked`). The previous phase finished, so the follow-up work (`/fix` after `review_failed`, `/pr` after `fixed`, …) starts at 1. This is what keeps the ordinary plan→fix→review→fix lifecycle from burning the budget (issue #186: the old carry-forward saturated the default of 3 on a healthy cycle and blocked the very `/fix` that addresses the review finding).
- **Carry forward (previous + 1, floored at 1)**: restarting from a *failing or neutral* rest (`failed`/`error`/`skipped`/`aborted`) or from `planned` (re-plan churn). This is the path the guard actually fires on.
- **`/retry` (→ 1)**: explicit reset.

Because the counter carries forward only across failing/neutral rests, when it already equals `MAX_ATTEMPTS` (default 3) the next *carry-forward* restart computes `attempt_count = MAX_ATTEMPTS + 1 > MAX_ATTEMPTS` and `decide()` returns `Action(kind="mark_failed_limit", limit_reason="attempts")` — `emit()` produces a "Max attempts reached" comment, sets `autoswe_status = "failed"`, and sets `_guard_blocked = True` so comment re-scans stop until a new command appears. The attempts guard is checked **before** the "failed/error only restart on `/retry`" gate, so it fires on both the `/fix`-again and `/retry` loops, not just `/retry`.

## `MAX_TOTAL_HOURS` Wall Clock

`first_dispatched_at` is set on first dispatch. `decide()` checks `(now - first_dispatched_at) / 3600 > MAX_TOTAL_HOURS` (default 2). If exceeded → `Action(kind="mark_failed_limit")`, which emits "Time limit exceeded" comment, `autoswe_status = "failed"`, `_guard_blocked = True`.

`first_dispatched_at` is reset to `None` in two situations:
- **Terminal status completion** (`orch/emit.py`): after any COMPLETED status (`fixed`/`synced`/`shipped`/`reviewed`), `failed`, `error`, `skipped`, or `aborted` — each new dispatch cycle gets a fresh timer. The `patch_queue` Effect sets `first_dispatched_at: None`.
- **Phase transition** (`orch/decide.py`): when restarting from `planned` or a RUNNING status — each pipeline phase (plan → fix → pr) gets its own timer so the time limit measures the current phase, not the cumulative time of completed phases (fixes #119).

## `AGENT_TIMEOUT` Per Agent Session

`asyncio.wait_for(backend.run(spec), timeout=AGENT_TIMEOUT)` in `harness/runner.py`. Default 7200 s (2 h); per-repo override via `repos.json` → `agent_timeout`. On timeout the handler returns `"FAILED: timeout during …"`.

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
