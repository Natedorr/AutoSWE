# Task Handlers

`/plan`, `/fix`, and `/review` are the Claude-backed work — planning, coding, and code review. `/pr`, `/sync`, `/retry`, `/skip`, `/abort` are workflow plumbing borrowed from how you'd drive a branch by hand: a branch can be cut from a non-default parent, can drift from its base and need a sync, and a run can fail and need a retry. autoSWE just lets you do all of that from issue comments instead of a terminal.

Each handler returns a done-content string; the dispatch loop maps it to an `autoswe_status` (and mirrors that to the `autoswe:*` label — see `pipeline.md` Stage 6).

## `/plan` — `planner.run_plan(task, repo_cfg, cfg)`

- **Permission mode:** `plan` (read-only: `Read`, `Glob`, `Grep` + `AGENT_TASK_TOOLS` for progress tracking)
- **Prompt source:** `config/prompts/plan.txt` (loaded by `prompts.py:build_plan_prompt()`)
- **Model resolution:** `repo_cfg.plan_model` → `cfg.PLAN_MODEL` → SDK default
- **Worktree:** created via `create_worktree()` on `plan_branch` (or `base_branch`)
- **Flow:** Runs Claude in read-only mode over the repo. Parses response for `<AUTOSWE_PLAN>` or `<AUTOSWE_QUESTIONS>` XML blocks (regexes in `tracking/comments.py:_PLAN_RE`, `_QUESTIONS_RE`)
- **Returns:**
  - `"PLAN_READY"` — plan block found; posts plan as comment
  - `"WAITING: questions"` — questions block found; posts questions as comment
  - `"WAITING: see comment"` — no XML block; posts raw response as comment
  - `"FAILED: …"` — timeout or SDK error

## `resume_plan` — `planner.resume_plan(task, user_reply, repo_cfg, cfg)`

- **Permission mode:** `plan` (read-only + `AGENT_TASK_TOOLS`)
- **Prompt:** wraps user reply in resume prompt, asks Claude to continue planning
- **Session:** resumed via `task.session_id`
- **Returns:** same as `run_plan()` — `"PLAN_READY"`, `"WAITING: questions"`, `"WAITING: see comment"`, or `"FAILED: …"`

## `/fix` — `coder.run_fix(task, guidance, repo_cfg, cfg)`

- **Permission mode:** `bypassPermissions` (full access: `Read`, `Edit`, `Write`, `Bash`, `Glob`, `Grep` + `AGENT_TASK_TOOLS`)
- **Prompt source:** `config/prompts/fix.txt` (loaded by `prompts.py:build_fix_prompt()`)
- **Model resolution:** `repo_cfg.fix_model` → `cfg.FIX_MODEL` → SDK default
- **Worktree:** created via `create_worktree()` on `plan_branch` (or `base_branch`). When called from the orchestrator (`orch/run.py`), the worktree may be pre-created and pre-synced by `_run_fix_with_sync()` before `run_fix()` is invoked.
- **Pre-dispatch sync:** Before running Claude, `_run_fix_with_sync()` calls `worktree_mod.sync_branch()` to merge `origin/{base_branch}` into the feature branch. On conflict, `coder.resolve_sync_conflicts()` resolves via Claude. On resolution failure, the dispatch bails before running fix. On clean sync, the pre-synced worktree is passed to `run_fix()` via `wt=` parameter, which reuses it instead of re-creating.
- **Session strategy:**
  - If `task["plan_file_path"]` is set (written by planner when a native `~/.claude/plans/*.md` file exists), `/fix` starts a **fresh Claude session** and injects the plan file content into the prompt directly. `plan_file_path` is consumed (popped) on first use so subsequent `/fix` runs resume the fix session normally.
  - Otherwise, `/fix` resumes the previous session via `task["session_id"]` (the planner's session if this is the first fix, or the prior fix session on retry/iterate).
- **Flow:** Runs Claude with code-editing permissions in worktree. After session, `commit_and_push()` preserves Claude's auto-commits as a commit trail (amending the last commit with a proper "Fixes #N" message) and pushes. If Claude did not auto-commit, working-tree changes are staged into a single commit. Then `VCSProvider.link_branch_to_issue()` is called (best-effort) to link the branch to the issue in the platform's UI (e.g. GitHub Development section).
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

- **Permission mode:** `plan` (read-only: `Read`, `Glob`, `Grep` + `AGENT_TASK_TOOLS`)
- **Prompt source:** `config/prompts/review.txt` (loaded by `prompts.py:build_review_prompt()`)
- **Model resolution:** `repo_cfg.review_model` → `cfg.REVIEW_MODEL` → SDK default
- **Worktree:** accessed via `worktree_path()` on the feature branch. Does not create a new worktree — uses the existing one from `/plan` or `/fix`.
- **Session:** fresh one-off session (`resume=None`). Not resumable.
- **Flow:** Computes `git diff` between feature branch and base branch. Extracts plan text from bot comments (if any). Runs Claude in read-only mode with the review prompt. Parses response for required sections (Summary, Correctness, Security, Tests, Style, Suggestions, Verdict). Posts review as a comment prefixed with `## Review`. Persists review report to `~/.claude/reviews/<slug>.md`.
- **Returns:**
  - `"REVIEW_READY"` — review completed; posts review comment, writes file, transitions status to `reviewed`
  - `"FAILED: …"` — timeout or SDK error
- **Review injection:** On the next `/fix` or `/plan`, the review findings are injected into the prompt via the `## Review Findings` block. `review_file_path` follows a pop-after-first-use lifecycle — consumed by `build_fix_prompt()` / `build_plan_prompt()` and cleared after injection.
- **Guidance input:** `/review` accepts an optional `with <guidance>` modifier (e.g. `/review with focus on error handling`). The guidance text is passed as `pending_command` guidance to `run_review()`, which appends it to the review prompt so Claude focuses on the specified area. See `slash-commands.md` for the full syntax.
- **Terminal:** Transitions the task to `reviewed` status. The task can still be restarted with `/fix`, `/retry`, or other commands.

## Environment Override Path

All Claude-invoking handlers pass env overrides through `runner.run()`:

1. `repo_cfg.anthropic_base_url` → `ANTHROPIC_BASE_URL`
2. `repo_cfg.anthropic_auth_token` → `ANTHROPIC_AUTH_TOKEN`
3. `cfg.ANTHROPIC_API_KEY` → `ANTHROPIC_API_KEY`

Timeout: `repo_cfg.agent_timeout` → `cfg.AGENT_TIMEOUT` (default 7200s), enforced via `asyncio.wait_for()`.
