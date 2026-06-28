# Task Handlers

`/plan`, `/fix`, and `/review` are the Claude-backed work — planning, coding, and code review. `/pr`, `/sync`, `/retry`, `/skip`, `/abort` are workflow plumbing borrowed from how you'd drive a branch by hand: a branch can be cut from a non-default parent, can drift from its base and need a sync, and a run can fail and need a retry. autoSWE just lets you do all of that from issue comments instead of a terminal.

Each handler returns a `HandlerResult` (a done-content string plus cost/duration/session metadata); the dispatch loop maps `done_content` to an `autoswe_status` (and mirrors that to the `autoswe:*` label — see `pipeline.md` Stage 6).

## Harness & Backend Resolution

Every agent-backed handler (`plan`, `fix`, `review`, conflict resolution) follows the same two steps before invoking the agent:

1. **Resolve the harness profile** for the phase: `resolve_harness("plan" | "fix" | "review", repo_cfg, cfg)` (from `core/config.py`) returns the profile dict — `{"backend": ..., "model": ..., ...}`. The profile's `model` takes precedence over the legacy `{phase}_model` / `{PHASE}_MODEL` fallback chain.
2. **Invoke via the generic runner:** the handler calls `runner.run(..., mode=<intent>, harness_cfg=harness)`. `runner.run()` packs a `RunSpec` and dispatches to the resolved backend (`claude_code` or `codex`) through the factory. The `mode` strings are `"plan"` (plan), `"read_only"` (review), and `"read_write"` (fix/conflict resolution); each backend translates them into its own configuration. When `harness_cfg` is omitted, the runner defaults to `ClaudeCodeBackend`.

MCP-dependent behavior (plan/question posting) is gated on `runner.backend_has_capability(harness, "mcp")` — when the backend can't post via MCP (e.g. Codex), the handler falls back to text parsing. See [harnesses.md](harnesses.md).

## `/plan` — `planner.run_plan(task, repo_cfg, cfg)`

- **Mode:** `"plan"` (read-only: `Read`, `Glob`, `Grep` + `PROGRESS_TOOLS` for progress tracking). Claude Code translates this to its `plan` permission mode; Codex to a `read-only` sandbox.
- **Prompt source:** `config/prompts/plan.txt` (loaded by `prompts.py:build_plan_prompt()`)
- **Model resolution:** `resolve_harness("plan", …).model` → `repo_cfg.plan_model` → `cfg.PLAN_MODEL` → backend default
- **Worktree:** created via `create_worktree()` on `plan_branch` (or `base_branch`)
- **Flow:** Runs the agent in read-only mode over the repo. The **primary** signal is the MCP comment tools — `mcp__autoswe_comment__post_plan` → `PLAN_READY`, `mcp__autoswe_comment__post_question` → `WAITING` (gated on the backend's `"mcp"` capability). When MCP is unavailable (e.g. Codex) or wasn't used, `planner._interpret_plan_result()` falls back via `_extract_plan_output()`'s priority chain: (1) an explicit `Write` to `~/.claude/plans/*.md` captured during the run, (2) **ExitPlanMode plan text** — the model often exits plan mode through the native `ExitPlanMode` tool (which is disallowed, but its tool-use block, carrying the full plan markdown, still appears in the stream; the Claude Code backend captures it into `RunResult.plan_text`), (3) the **deprecated** `<AUTOSWE_PLAN>` / `<AUTOSWE_QUESTIONS>` XML blocks (regexes in `tracking/comments.py:_PLAN_RE`, `_QUESTIONS_RE`), (4) a filesystem scan for the latest `~/.claude/plans/*.md`, then (5) raw text. Capturing ExitPlanMode text fixes the case where a plan was written but only a bare `Tool: ExitPlanMode` progress line got posted.
- **Returns:**
  - `"PLAN_READY"` — plan block found; posts plan as comment
  - `"WAITING: questions"` — questions block found; posts questions as comment
  - `"WAITING: see comment"` — no XML block; posts raw response as comment
  - `"FAILED: …"` — timeout or SDK error

## `resume_plan` — `planner.resume_plan(task, user_reply, repo_cfg, cfg)`

- **Permission mode:** `plan` (read-only + `PROGRESS_TOOLS`)
- **Prompt:** wraps user reply in resume prompt, asks Claude to continue planning
- **Session:** resumed via `task.session_id`
- **Returns:** same as `run_plan()` — `"PLAN_READY"`, `"WAITING: questions"`, `"WAITING: see comment"`, or `"FAILED: …"`

## `/fix` — `coder.run_fix(task, guidance, repo_cfg, cfg)`

- **Mode:** `"read_write"` (full access: `Read`, `Edit`, `Write`, `Bash`, `Glob`, `Grep` + `AGENT_TASK_TOOLS`). Claude Code translates this to `bypassPermissions`; Codex to a `workspace-write` sandbox.
- **Prompt source:** `config/prompts/fix.txt` (loaded by `prompts.py:build_fix_prompt()`)
- **Model resolution:** `resolve_harness("fix", …).model` → `repo_cfg.fix_model` → `cfg.FIX_MODEL` → backend default
- **Worktree:** created via `create_worktree()` on `plan_branch` (or `base_branch`). When called from the orchestrator (`orch/run.py`), the worktree may be pre-created and pre-synced by `_run_fix_with_sync()` before `run_fix()` is invoked.
- **Pre-dispatch sync:** Before running Claude, `_run_fix_with_sync()` calls `worktree_mod.sync_branch()` to merge `origin/{base_branch}` into the feature branch. On conflict, `coder.resolve_sync_conflicts()` resolves via Claude. On resolution failure, the dispatch bails before running fix. On clean sync, the pre-synced worktree is passed to `run_fix()` via `wt=` parameter, which reuses it instead of re-creating.
- **Session strategy:**
  - If `task["plan_file_path"]` is set (written by planner when a native `~/.claude/plans/*.md` file exists), `/fix` starts a **fresh Claude session** and injects the plan file content into the prompt directly. `plan_file_path` is consumed (popped) on first use so subsequent `/fix` runs resume the fix session normally.
  - Otherwise, `/fix` resumes the previous session via `task["session_id"]` (the planner's session if this is the first fix, or the prior fix session on retry/iterate).
- **Flow:** Runs Claude with code-editing permissions in worktree. After session, `commit_and_push()` preserves Claude's auto-commits as a commit trail (amending the last commit with a proper "Fixes #N" message) and pushes. If Claude did not auto-commit, working-tree changes are staged into a single commit. Branch linking (when `LINK_BRANCH_TO_ISSUE=true`) happens at worktree creation time — see [git-worktrees.md](git-worktrees.md) `create_worktree()` step 6.
- **Returns:**
  - `"DONE_SUMMARY\t<summary>\t<sha>"` — changes committed (summary = last 10 non-empty lines of Claude output)
  - `"DONE: no changes detected"` — no staged changes
  - `"FAILED: …"` — timeout, SDK error, or commit/push failure

## `/pr` — `ship.open_pr(task, cfg, repo_cfg)`

- **No Claude invocation** — pure `VCSProvider.open_pull_request()` call.
- **Flow:** open the PR for `autoswe/issue-{N}` → `base_branch`; post a "Pull request opened" comment.
- **Returns:**
  - `"DONE: PR <url>"` — PR created
  - `"FAILED: could not create PR: …"` — VCS error
- **Direction:** because this needs no agent, `/pr` requests are meant to be resolved in the poller's quick-posts pass (`pipeline.md` Stage 4) rather than competing for a slot in the session loop. (Auto-PR after a successful `/fix` still happens inside the dispatch loop — see `pipeline.md` Stage 7.)

## `/sync` — inline in dispatch loop

- **Why:** a task branch falls behind its base over time; `/sync` brings it forward. Most of the operation is mechanical git — the *only* part that needs Claude is resolving merge conflicts, which is also the part you'd least want to do by hand.
- **No Claude invocation unless there are conflicts.**
- **Flow:** `worktree_mod.sync_branch()` merges `origin/{base_branch}` into the feature branch (strategy controlled by `cfg.SYNC_STRATEGY`).
  - Clean merge → `"DONE_SUMMARY\t...\tsha"`.
  - Merge conflicts → `coder.resolve_sync_conflicts()` runs Claude with `bypassPermissions` on the existing conflicted worktree, seeded with a focused conflict-resolution prompt (includes plan text if available, conflict file list, and instructions to resolve markers + `git add -A && git commit --no-edit`). After Claude resolves, the handler pushes the merge commit and returns `"DONE_SUMMARY\t...\tsha"`.
  - Rebase conflicts → returns `"FAILED: rebase conflict in ..."` (rebase conflict resolution is deferred).
  - Resolution failure → leaves conflicted worktree in place, returns `"FAILED: ..."`.
- **Returns:**
  - `"DONE_SUMMARY\t<summary>\t<sha>"` — clean merge or conflict resolved via Claude
  - `"FAILED: …"` — sync error, rebase conflict, or conflict-resolution failure
- **Key design:** The resolver resumes the task's prior session (`session_id`) for continuity. It reads (but does not consume) `plan_file_path` so the plan persists for downstream `/fix`. No `AskUserQuestion` — Claude must make its best call or fail.

## `/retry` — inline in dispatch loop

- **No handler function.** Dispatch scans comments for last substantive command (not `/pr`, `/sync`, `/retry`, `/skip`, or `/abort`), then calls `_run_handler(effective_cmd, effective_guid, task, repo_cfg, cfg)`
- **Returns:** same as the replayed handler

## `/skip` — inline in dispatch loop

- Sets label → `autoswe:skipped` via `tracker.set_status()`
- Returns `"SKIPPED"`

## `/abort` — inline in dispatch loop

- Sets label → `autoswe:aborted` via `tracker.set_status()`
- Posts "Task aborted" comment (via sticky progress comment finalize)
- Returns `"ABORTED"`

## `/review` — `reviewer.run_review(task, repo_cfg, cfg)`

- **Mode:** `"read_only"` (read-only: `Read`, `Glob`, `Grep` + `PROGRESS_TOOLS`). Translated per backend (Claude Code read-only tools; Codex `read-only` sandbox).
- **Prompt source:** `config/prompts/review.txt` (loaded by `prompts.py:build_review_prompt()`)
- **Model resolution:** `resolve_harness("review", …).model` → `repo_cfg.review_model` → `cfg.REVIEW_MODEL` → backend default
- **Worktree:** accessed via `worktree_path()` on the feature branch. Does not create a new worktree — uses the existing one from `/plan` or `/fix`.
- **Session:** fresh one-off session (`resume=None`). Not resumable.
- **Flow:** Computes `git diff` between feature branch and base branch. Extracts plan text from bot comments (if any). Runs Claude in read-only mode with the review prompt. Parses response for required sections (Summary, Correctness, Security, Tests, Style, Suggestions, Verdict). Posts review as a comment prefixed with `## Review`. Persists review report to `~/.claude/reviews/<slug>.md`.
- **Returns:** `"REVIEW_READY\t<full review text>"` (review completed; posts review comment, writes file) or `"FAILED: …"` (timeout or SDK error).
- **Verdict gating:** `_map_done_to_status()` runs `parse_review_verdict()` over the review text's `## Verdict` section and maps the outcome to a status:
  - **LGTM / approved** (or no recognizable verdict) → `reviewed` (terminal; `/pr` allowed).
  - **Needs changes** → `review_failed` (non-terminal; `/pr` blocked).
  - **Blocked** (CRITICAL findings) → `review_blocked` (non-terminal; `/pr` blocked).

  `parse_review_verdict` scopes to the `## Verdict` section so "Blocked"/"Needs changes" inside finding bodies don't false-trigger; the default is `reviewed` to preserve backward compatibility for reviews without a parseable verdict. In `review_failed`/`review_blocked`, `emit()` appends a "`/pr` is disabled" note to the review comment and `decide()` refuses `/pr`.
- **Auto re-review after `/fix`:** A `/fix` dispatched from `review_failed`/`review_blocked` sets the `rereview_after_fix` queue flag on completion (and suppresses `AUTO_CREATE_PR`). On the next poll, `decide()` auto-dispatches `/review` (clearing the flag in `emit()`'s review branch) so the gating verdict is re-checked before the code can ship.
- **Review injection:** On the next `/fix` or `/plan`, the review findings are injected into the prompt via the `## Review Findings` block. `review_file_path` follows a pop-after-first-use lifecycle — consumed by `build_fix_prompt()` / `build_plan_prompt()` and cleared after injection.
- **Guidance input:** `/review` accepts an optional `with <guidance>` modifier (e.g. `/review with focus on error handling`). The guidance text is passed as `pending_command` guidance to `run_review()`, which appends it to the review prompt so Claude focuses on the specified area. See `slash-commands.md` for the full syntax.

## Environment Override Path

All agent-invoking handlers route through `runner.run(..., harness_cfg=harness)`, which builds a `RunSpec` and dispatches to the resolved backend. Backend-specific auth/runtime settings come from the harness profile (see [harnesses.md](harnesses.md)) and, for Claude Code, the env-override chain:

1. `repo_cfg.anthropic_base_url` → `ANTHROPIC_BASE_URL`
2. `repo_cfg.anthropic_auth_token` → `ANTHROPIC_AUTH_TOKEN`
3. `cfg.ANTHROPIC_API_KEY` → `ANTHROPIC_API_KEY`

(The Codex backend uses `codex_api_key` / `openai_api_key` from the profile instead — or no key for local providers.)

Timeout: `repo_cfg.agent_timeout` → `cfg.AGENT_TIMEOUT` (default 7200s), enforced via `asyncio.wait_for()` around `backend.run(spec)`. `AGENT_RETRY_ON_FAILURE` controls retry attempts on retryable backend errors.
