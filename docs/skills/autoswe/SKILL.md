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

You are helping a user interact with **autoSWE** — a system that polls GitHub or Azure DevOps issues, dispatches Claude Code agents to plan and fix them, and manages the full lifecycle via slash commands posted as issue comments.

---

## Core Concept

autoSWE works entirely through **issue comments**. The user (or you, on their behalf) posts slash commands as comments on a GitHub or Azure DevOps issue. A background poller picks them up and dispatches Claude Code sessions that read the codebase, ask questions, implement fixes, and open PRs.

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
| `/review` | Run a code review on the current branch diff |
| `/pr` | Open a pull request from the task's work branch. Takes **no arguments** — see **Branch selection** below |
| `/sync` | Pull the branch from upstream to keep it up to date |
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
6. Claude edits code, runs tests → "autoswe:fixed"
       ↓
7. Post /review → "autoswe:reviewing" → "autoswe:reviewed"
       ↓
8. Post /pr → "autoswe:shipping" → "autoswe:shipped" (PR created)
```

**You can skip steps.** Post `/fix` directly if you don't need a plan first. Post `/pr` right after `/fix` if you don't want a review.

---

## Status Labels

autoSWE tracks progress via `autoswe:*` labels (GitHub) or tags (Azure DevOps):

| Status | Meaning | Color |
|--------|---------|-------|
| `autoswe:planning` | Planning session in progress | 🔶 orange |
| `autoswe:waiting` | Agent asked a question, waiting for your reply | 🟡 yellow |
| `autoswe:planned` | Plan posted, ready for `/fix` | 🟢 green |
| `autoswe:fixing` | Fix implementation in progress | 🔶 orange |
| `autoswe:fixed` | Fix completed | ⚪ grey |
| `autoswe:reviewing` | Code review in progress | 🔶 orange |
| `autoswe:reviewed` | Review completed | ⚪ grey |
| `autoswe:shipping` | PR creation in progress | 🔶 orange |
| `autoswe:shipped` | PR created | ⚪ grey |
| `autoswe:failed` | Agent errored out | 🔴 red |
| `autoswe:skipped` | Skipped by user | ⚪ white |
| `autoswe:aborted` | Aborted by user | 🩷 pink |
| `autoswe:error` | Infrastructure error | 🔴 dark red |

**Running statuses** (agent actively working): planning, fixing, syncing, reviewing, shipping  
**Terminal statuses** (done/stopped): fixed, synced, shipped, reviewed, failed, skipped, aborted, error

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
- **Failed tasks:** Post `/fix` or `/plan` to restart (carries the attempt counter forward) or `/retry` to restart with a fresh budget. Only those three restart a `failed`/`error` task; `/pr`, `/review`, and `/sync` are refused (no completed work to ship/review/sync)
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

---

## Troubleshooting (comment-level)

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Nothing happens after posting command | Poller not running | Someone needs to run `python3 autoswe.py poller` |
| Stuck on `autoswe:planning` | Agent timed out or errored | Check logs, post `/retry` |
| `autoswe:failed` | Agent hit max attempts or error | Post `/fix` or `/plan` to restart (or `/retry` for a fresh budget); `/pr`/`/review`/`/sync` are refused |
| Command ignored | Repo locked by another running task | Wait for current task to finish |
| Bot not responding to your comments | You're not in `ALLOWED_AUTHORS` | Ask admin to add you |
