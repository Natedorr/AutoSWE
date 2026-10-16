---
name: autoswe
description: "Use autoSWE to automate code fixes via GitHub/Azure issues — slash commands, workflow, and best practices."
user-invocable: true
metadata:
  {
    "openclaw": {
      "requires": { "bins": ["python3"] }
    }
  }
---

# autoSWE — Automated Issue Resolution via Slash Commands

You are helping a user interact with **autoSWE** — a system that polls GitHub or Azure DevOps issues, dispatches a coding agent to plan and fix them (Claude Code by default; Codex or pi when the repo's harness profile says so), and manages the full lifecycle via slash commands posted as issue comments.

---

## Core Concept

autoSWE works entirely through **issue comments**. The user (or you, on their behalf) posts slash commands as comments on a GitHub or Azure DevOps issue. A background poller picks them up and dispatches agent sessions that read the codebase, ask questions, implement fixes, and open PRs.

**No direct API calls needed.** Everything happens through comments on the issue.

---

## Slash Commands

Post these as comments on the issue (at the start of a line):

| Command | What it does |
|---------|-------------|
| `/plan` | Start a planning session — Claude reads the codebase, asks clarifying questions, then posts a plan |
| `/plan --branch <name>` | Same as `/plan`, but cut the work branch from `<name>` instead of the repo's default branch (see **Branch selection** below) |
| `/fix` | Implement the fix — Claude gets code-writing permissions and edits the repo |
| `/fix with <guidance>` | Same as `/fix` but appends guidance to the prompt (e.g., `/fix with focus on edge cases`) |
| `/fix --branch <name>` | Same as `/fix`, but cut the work branch from `<name>` (see **Branch selection** below) |
| `/review [with <guidance>]` | Run a read-only code review on the current branch diff; `with <guidance>` adds focus |
| `/pr` | Open a pull request from the task's work branch. Takes **no arguments** — see **Branch selection** below |
| `/sync` | Pull the branch from upstream to keep it up to date |
| `/catchup --from <upstream> --into <downstream>` | Control issues only: merge `<upstream>` into a branch cut from `<downstream>` and open (or update) a PR into `<downstream>`. See **Control issues** below |
| `/retry` | Retry a failed task (resets attempt counter) |
| `/skip` | Skip this issue |
| `/abort` | Cancel the current task |

**Alias:** `@autoswe <guidance>` is equivalent to `/fix with <guidance>` (uses the configured bot name).

### Branch selection

autoSWE creates exactly **one work branch per issue** — `autoswe/issue-<N>` — and `/pr` always opens the pull request **from `autoswe/issue-<N>` back to the branch that work was based on**.

- `--branch <name>` (on `/plan` or `/fix`) picks the **base** to branch from. So `/fix --branch develop` means: cut `autoswe/issue-<N>` from `develop`, and the eventual PR targets `develop`.
- The base is **locked the first time it's set** — a later `--branch` on another comment is ignored. Set it on your very first `/plan` or `/fix`.
- Omit `--branch` to use the repo's configured default branch (often `main`).
- **`/pr` accepts no branch argument.** There is no way to open the PR onto a branch other than the one the work was based on — the head is always `autoswe/issue-<N>` and the base is always that starting branch.

---

### Control issues: keeping a branch caught up

A **control issue** is a mostly blank issue whose only job is to keep a downstream branch (typically `develop`) caught up with its upstream (typically `master`). The title and body don't matter; the command does:

```
/catchup --from master --into develop
```

- **One `/catchup` is one run.** autoSWE cuts `autoswe/issue-<N>` from `develop`, merges `origin/master` into it (Claude resolves any conflicts), and opens a PR into `develop`. If that PR is still open, the same branch and PR are updated.
- **To catch up again, comment `/catchup` on the same issue.** A bare `/catchup` reuses the `--from`/`--into` pair from the last run. Pass the flags again to change the pair.
- **Body vs. comment.** A `/catchup` in the issue body runs once, when autoSWE first picks the issue up. Every later run needs a comment.
- **Already up to date?** If `develop` already contains `master`, autoSWE says so and opens no PR. The task still lands in `caught_up`.
- **Any resting state.** `/catchup` doesn't need a plan or a fix first. It is still refused on a guard-blocked task (post `/retry`).
- **One catch-up per downstream branch.** If another control issue is already catching up `develop`, yours is refused until that run finishes.
- **Failed catch-up.** If conflict resolution fails, the task goes to `failed` and the worktree is left conflicted. `/retry` replays the catch-up.
- **Merge the PR with a merge commit, not a squash.** A squash leaves `master`'s commits out of `develop`'s history, so `develop` stays behind and the same conflicts come back next time.
- **The control issue stays open** after its PR merges.
- `--direct` (pushing the merge straight to `develop`) is not available yet. `/catchup --direct` is refused.

---

## Posting & Reading via the GitHub CLI (`gh`)

If you drive autoSWE with the `gh` CLI instead of the web UI, keep two things in mind.

**Posting a command** is just a comment — no special escaping needed beyond quoting the body:

```bash
gh issue comment <N> --repo OWNER/REPO --body '/fix with focus on edge cases'
```

**Colons in `gh` search queries will bite you.** Every autoSWE label contains a colon (`autoswe:planning`, `autoswe:fixed`, …). `gh search` and `gh issue list --search` read `key:value` as a search *qualifier*, so a bare `label:autoswe:planning` is mis-parsed — the second colon splits the value and you get no results (or an error). To filter issues by an autoSWE label:

- **Prefer `--label`, which takes the literal label** and does no query parsing:

  ```bash
  gh issue list --repo OWNER/REPO --label 'autoswe:planning'
  ```

- If you must use `--search`, **wrap the value in double quotes** so the second colon stays inside it:

  ```bash
  gh issue list --repo OWNER/REPO --search 'label:"autoswe:planning"'
  ```

- Always **single-quote the whole argument** so the shell doesn't split on the colon (or the `/` in `OWNER/REPO`).

---

## The Lifecycle

```
1. Issue created or discovered
       ↓
2. Post /plan → autoSWE posts "autoswe:planning" label
       ↓
3. Claude reads code, may ask questions → "autoswe:waiting" (you reply)
       ↓
4. Claude posts plan → "autoswe:planned"
       ↓
5. Post /fix → autoSWE posts "autoswe:fixing" label
       ↓
6. Claude edits code, runs tests → "autoswe:fixed" (or "autoswe:test_failed" if the suite is red: post `/fix` to re-run the gate)
       ↓
7. Post /review → "autoswe:reviewing" → "autoswe:reviewed" (or "autoswe:review_failed" / "autoswe:review_blocked": post `/fix` to address the findings)
       ↓
8. Post /pr → "autoswe:shipping" → "autoswe:shipped" (PR created)
```

**You can skip steps.** Post `/fix` directly if you don't need a plan first. Post `/pr` right after `/fix` if you don't want a review.

---

## Status Labels

autoSWE tracks progress via `autoswe:*` labels (GitHub) or tags (Azure DevOps):

| Status | Meaning | Color |
|--------|---------|-------|
| `autoswe:pending` | Queued; the next dispatch run picks it up | 🔵 blue |
| `autoswe:planning` | Planning session in progress | 🔶 orange |
| `autoswe:waiting` | Agent asked a question, waiting for your reply | 🟡 yellow |
| `autoswe:planned` | Plan posted, ready for `/fix` | 🟢 green |
| `autoswe:fixing` | Fix implementation in progress | 🔶 orange |
| `autoswe:fixed` | Fix completed | ⚪ grey |
| `autoswe:syncing` | Sync in progress | 🔶 orange |
| `autoswe:synced` | Sync completed | ⚪ grey |
| `autoswe:reviewing` | Code review in progress | 🔶 orange |
| `autoswe:reviewed` | Review completed | ⚪ grey |
| `autoswe:catching_up` | Catch-up merge in progress (control issues) | 🔶 orange |
| `autoswe:caught_up` | Catch-up PR opened or updated, or branch already up to date | ⚪ grey |
| `autoswe:review_failed` | Review found issues — post `/fix` | 🟡 yellow |
| `autoswe:review_blocked` | Review blocked on a critical finding — post `/fix` | 🔴 red |
| `autoswe:test_failed` | Fix pushed but the test suite is red — post `/fix` | 🔴 red |
| `autoswe:ci_failed` | CI is red on the pushed branch | 🔴 red |
| `autoswe:shipping` | PR creation in progress | 🔶 orange |
| `autoswe:shipped` | PR created | ⚪ grey |
| `autoswe:failed` | Agent errored out | 🔴 red |
| `autoswe:skipped` | Skipped by user | ⚪ white |
| `autoswe:aborted` | Aborted by user | 🩷 pink |
| `autoswe:error` | Infrastructure error | 🔴 dark red |

**Running statuses** (agent actively working): planning, fixing, syncing, catching_up, reviewing, shipping  
**Terminal statuses** (done/stopped): fixed, synced, caught_up, shipped, reviewed, failed, skipped, aborted, error

---

## Guiding the Agent Through Comments

### During Planning

The agent may ask clarifying questions via `AskUserQuestion`. These appear as structured comments with options. Reply in any of these ways:

- **Free text:** Just write your answer naturally
- **Option labels:** Reference the option exactly (e.g., "Usernames only (Recommended)")
- **Slash command in reply:** Reply with `/fix` directly to skip further planning

### During Fix

Add guidance by commenting:

```
/fix with focus on performance and thread safety
```

Or mid-flight, just comment with instructions — but only if the status is `waiting`:

```
Please also update the documentation for this change
```

### After Completion

When you see `autoswe:fixed`, you have options:
- `/review` — Run a review pass before shipping
- `/pr` — Skip review, go straight to PR
- `/fix with <guidance>` — Do another fix pass with new instructions
- `/retry` — Retry if something failed

---

## Guardrails

- **Max attempts:** Default 3 per issue (configurable via `MAX_ATTEMPTS`)
- **Time limit:** Default 2 hours total per issue (configurable via `MAX_TOTAL_HOURS`)
- **Guard block:** When limits are hit, the issue is locked. Only `/retry`, `/skip`, or `/abort` work; other commands are refused with a "post `/retry`" comment
- **Failed tasks:** Post `/fix` or `/plan` to restart (carries the attempt counter forward) or `/retry` to restart with a fresh budget. Only those three restart a `failed`/`error` task; `/pr`, `/review`, and `/sync` are refused (no completed work to ship/review/sync). `/catchup` is the exception: it is accepted from any resting state
- **Concurrent tasks:** Only one task per repo at a time (PID-based locking, default `MAX_CONCURRENT=1`)

---

## Configuration (for reference)

Key settings in `config/autoswe.env`:

| Setting | Default | Description |
|---------|---------|-------------|
| `MAX_ATTEMPTS` | 3 | Max retry attempts per issue |
| `MAX_TOTAL_HOURS` | 2 | Time budget per issue |
| `MAX_CONCURRENT` | 1 | Parallel tasks per repo |
| `AGENT_TIMEOUT` | 7200 | Per-session timeout (seconds) |
| `AUTO_CREATE_PR` | false | Auto-create PR after fix |
| `BOT_NAME` | autoswe | Bot mention name |
| `ALLOWED_AUTHORS` | (none) | Comma-separated allowed usernames |
| `SYNC_STRATEGY` | merge | `/sync` merges by default; `rebase` rewrites the work branch. `/catchup` always merges |
| `PR_REQUIRE_CI` | true | Defer PR creation while CI is pending or red |
| `CI_WATCH` | true | Watch CI on fixed and shipped branches |
| `AUTO_FIX_ON_GATE_FAILURE` | true | A red CI or red test gate auto-dispatches a `/fix`, bounded by the gate budget |

---

## Troubleshooting (comment-level)

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Nothing happens after posting command | Poller not running | Someone needs to run `python3 autoswe.py poller` |
| Stuck on `autoswe:planning` | Agent timed out or errored | Check logs, post `/retry` |
| `autoswe:failed` | Agent hit max attempts or error | Post `/fix` or `/plan` to restart (or `/retry` for a fresh budget); `/pr`/`/review`/`/sync` are refused |
| `/catchup` refused: needs both branches | No `--from`/`--into` pair in the comment, and none stored on the task yet | Post `/catchup --from <upstream> --into <downstream>` |
| `/catchup` refused: already being caught up | Another control issue is catching up the same downstream branch | Wait for that run to finish, then post `/catchup` again |
| `autoswe:test_failed` | Fix pushed but the test suite is red | Post `/fix` to re-run the gate; `/pr` is blocked until it is green |
| `autoswe:ci_failed` | CI is red on the pushed branch | With `AUTO_FIX_ON_GATE_FAILURE` on, a `/fix` is dispatched automatically; otherwise post `/fix` |
| Command ignored | Repo locked by another running task | Wait for current task to finish |
| Bot not responding to your comments | You're not in `ALLOWED_AUTHORS` | Ask admin to add you |
