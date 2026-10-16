---
name: autoswe-ops
description: "Host-level operations for autoSWE — queue management, log inspection, debugging, and maintenance when OpenClaw runs on the same machine as autoSWE."
user-invocable: true
metadata:
  {
    "openclaw": {
      "requires": { "bins": ["python3"] }
    }
  }
---

# autoSWE — Host Operations & Debugging

You are running on the **same machine** as autoSWE. Use these quick-reference commands to diagnose, unblock, and maintain the system.

---

## Quick Reference

| Goal | Command |
|------|---------|
| **Run poller once** | `python3 autoswe.py poller` |
| **Run poller (drain mode)** | `python3 autoswe.py poller --drain` |
| **Sync only (no dispatch)** | `python3 autoswe.py sync` |
| **Dispatch only (no sync)** | `python3 autoswe.py dispatch` |
| **List queue** | `python3 autoswe.py queue list` |
| **Filter queue by status** | `python3 autoswe.py queue list --status fixing` |
| **Single task status** | `python3 autoswe.py queue status --repo OWNER/REPO --issue 123` |
| **Azure task status** | `python3 autoswe.py queue status --repo org/project/repo --issue 123 --provider azure` |
| **Prune old tasks** | `python3 autoswe.py queue prune --older-than-days 30` |
| **Prune (dry run)** | `python3 autoswe.py queue prune --older-than-days 30 --dry-run` |

---

## Is Something Running? (PID Lock Check)

autoSWE uses a PID file to prevent concurrent tasks on the same repo. If the poller says nothing to dispatch but an issue is clearly pending:

```bash
# Check if a Claude Code session is actively running
ls -la /running/

# PID file blocks new dispatches for that repo
cat /running/<repo-slug>.pid

# If the process is dead but PID file remains, stale lock:
kill -0 $(cat /running/<repo-slug>.pid) 2>/dev/null && echo "ALIVE" || echo "STALE"

# Remove stale PID file (ONLY if the process is actually dead):
rm /running/<repo-slug>.pid
```

---

## Catch-up Tasks (`/catchup`)

A control issue's queue entry records the pair its last `/catchup` ran with:

```bash
python3 autoswe.py queue status --repo OWNER/REPO --issue 123 | python3 -m json.tool

# - "sync_from" / "sync_into": the upstream and downstream of the last /catchup
# - "autoswe_status": "catching_up" while running; "caught_up" when the PR is open or updated, or the branch was already up to date
# - "pr_number" / "pr_url": the catch-up PR (absent when already up to date)
```

**A catch-up stuck in `catching_up`** is a running status like any other. Use the zombie-task recovery in `debugging.md` (delete the `.pid`, then re-sync). While it is stuck it also blocks other control issues from catching up the same `sync_into` branch.

**A catch-up whose conflict resolution failed** leaves the issue's worktree mid-merge. To inspect it, run `git -C <worktree> status`. Then either resolve and commit the merge by hand, push, and post `/retry`, or run `git merge --abort` and post `/retry` to replay the catch-up from scratch.

---

## Check if a Task Is Blocked

```bash
# Look at the queue entry for a specific issue
python3 autoswe.py queue status --repo OWNER/REPO --issue 123 | python3 -m json.tool

# Key fields to check:
# - "guard_blocked": true → task hit MAX_ATTEMPTS or MAX_TOTAL_HOURS (locked)
# - "autoswe_status": "failed"/"error" → needs /retry
# - "attempt_count": how many attempts have been used
# - "first_dispatched_at": if this is old, time guard may have fired
# - "last_dispatched_command": what command was last run
# - "pr_number": PR number if one was created
```

**Guard-blocked tasks** ignore all commands except `/retry`, `/skip`, `/abort`.

---

## Reset a Stuck or Blocked Task

To reset a task that's stuck (guard-blocked, stale time guard, etc.):

```bash
# 1. Look at the raw queue entry
python3 autoswe.py queue status --repo OWNER/REPO --issue 123

# 2. Edit queue.json directly to reset fields
#    (Back up first!)
cp /data/queue.json \
   /data/queue.json.bak

# 3. Use python to patch the task:
python3 -c "
import json
with open('/data/queue.json') as f:
    q = json.load(f)
slug = 'gh:owner_repo_123'  # adjust: gh:<owner>_<repo>_<issue>; Azure is ado:<org>_<project>_<repo>_<issue>
if slug in q:
    q[slug]['guard_blocked'] = False
    q[slug]['autoswe_status'] = None
    q[slug]['attempt_count'] = 0
    q[slug]['first_dispatched_at'] = None
    q[slug]['last_dispatched_command'] = None
    q[slug]['last_dispatched_command_id'] = None
    q[slug]['session_id'] = None
    print('Reset', slug)
with open('/data/queue.json', 'w') as f:
    json.dump(q, f, indent=2)
"

# 4. Run sync to refresh labels
python3 autoswe.py sync

# 5. Post /fix comment on the issue to restart
```

---

## Log Inspection

```bash
# Main logs directory
ls -lt /logs/

# Latest log file
tail -200 /logs/autoswe.log

# Search for specific errors
grep -i "error\|failed\|timeout" /logs/autoswe.log | tail -50

# Search for a specific issue
grep "OWNER/REPO.*123" /logs/autoswe.log | tail -30

# Claude Code session logs
ls -lt ~/.claude/sessions/

# Plan files (if planner wrote one)
ls -lt ~/.claude/plans/

# Review files (backend-neutral: $AUTOSWE_DIR/artifacts/reviews, defaults to <repo-root>/artifacts/reviews)
ls -lt "${AUTOSWE_DIR:-}"/artifacts/reviews/
```

**Key log patterns:**
- `[POLLER]` — Poller cycle info
- `[SYNC]` — GitHub/Azure sync info
- `[DISPATCH]` — Task dispatch decisions
- `[DECIDE]` — State machine transitions (very detailed)
- `[CLAUDE]` — Claude Code session info (cost, duration, session ID)
- `[LIMIT]` — Guard/limit firings (max attempts, time limit)
- `[LABEL]` — Label changes
- `[CATCHUP]` — `/catchup` pre-check, sync, conflict resolution and PR outcome

---

## Configuration Check

```bash
# Runtime config
cat /config/autoswe.env

# Repo configuration (PATs, branch overrides, auto-dispatch)
cat /config/repos.json

# Plan prompt
cat /config/prompts/plan.txt

# Fix prompt
cat /config/prompts/fix.txt

# Review prompt
cat /config/prompts/review.txt

# Conflict-resolution prompt (used by /sync and /catchup)
cat /config/prompts/conflict_resolution.txt

# Welcome comment
cat /config/welcome_comment.txt
```

---

## Common Failure Scenarios

### Claude Code Timeout / SDK Connection Error

```bash
# Check if Claude CLI is installed and reachable
which claude
claude --version

# Check if API key is set
echo $ANTHROPIC_API_KEY | head -c 10

# Check if custom base URL is configured
grep ANTHROPIC_BASE_URL /config/autoswe.env

# Test API connectivity
curl -s -o /dev/null -w "%{http_code}" https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -d '{"model":"claude-sonnet-4-20250514","max_tokens":1,"system":"test","messages":[]}'
```

### Agent Running Too Long

```bash
# Check for long-running Claude Code processes
ps aux | grep -i "claude" | grep -v grep

# Kill a stuck Claude Code session (LAST RESORT)
kill -9 <PID>

# Clean up stale PID file
rm /running/<repo-slug>.pid
```

### Poller Not Picking Up New Issues

```bash
# 1. Check the queue
python3 autoswe.py queue list

# 2. Force sync
python3 autoswe.py sync

# 3. Check for label issues — the poller only picks up issues with autoswe:* labels
#    If no autoswe:pending label, the issue won't be in the queue
#    Fix: manually add autoswe:pending label to the issue

# 4. Check repos.json — is the repo configured?
python3 -c "
import json
with open('/config/repos.json') as f:
    r = json.load(f)
for k, v in r.items():
    if k.startswith('_'): continue
    print(f'{k}: provider={v.get(\"provider\")}, pat={str(v.get(\"pat\",\"\"))[:8]}...')
"
```

### OOM / Memory Issues

```bash
# Check current memory usage
free -h
cat /proc/meminfo | head -5

# Check for zombie Claude processes
ps aux --sort=-rss | head -20

# Kill all Claude Code processes (emergency)
pkill -f "claude.*agent" || true

# Clean worktrees to free disk
du -sh /worktrees/*/
```

---

## Worktree Management

Each dispatched task gets a git worktree:

```bash
# List active worktrees
cd  && git worktree list

# Remove stale worktree (if task is done but worktree remains)
git worktree remove /worktrees/<branch> --force

# Inspect a worktree
ls -la /worktrees/autoswe/issue-123/
```

---

## Full System Restart

```bash
# 1. Kill running processes
pkill -f "claude.*agent" || true

# 2. Clean stale PID files
find /running/ -name "*.pid" -exec rm {} \;

# 3. Reset queue (optional — only if queue is corrupted)
cp /data/queue.json.bak \
   /data/queue.json

# 4. Full sync + dispatch
cd 
python3 autoswe.py poller --drain
```

---

## Cron / Scheduled Polling

If autoSWE is set up with a cron job, check it:

```bash
# System crontab (fallback)
crontab -l 2>/dev/null | grep autoswe
```

If autoSWE isn't running on a schedule, set up a recurring cron:

```bash
# Schedule: every 10 minutes
# Payload: python3 autoswe.py poller
```

---

## Filing a Bug Report

You are on the host machine — you have direct access to all the logs, queue state, and config. **Gather diagnostics before filing** so the maintainer (or an AI agent reviewing the issue) can start with a full picture.

### What to Collect

1. **Queue entry** — full output, redacted:
   ```bash
   python3 autoswe.py queue status --repo OWNER/REPO --issue N | python3 -m json.tool
   ```
   Redact `_token` or any PAT values.

2. **Log tail** — last 50 lines matching the issue:
   ```bash
   grep "OWNER/REPO.*N" logs/autoswe.log | tail -50
   ```
   Per-issue log: `logs/<slug>/<slug>.log`

3. **PID state** — is something stuck?
   ```bash
   ls -la running/
   ```

### Redaction Rules (MANDATORY)

Before pasting any output into a GitHub issue:

- **Delete lines containing** `TOKEN`, `KEY`, `PAT`, `x-api-key`, `Authorization: bearer`
- **Never paste full config files** — use `grep -v 'TOKEN\|KEY\|PAT' config/autoswe.env` for runtime config
- **In `repos.json`** — redact the `pat` field; keep `provider`, `branch`, and prompt paths
- **In session files** (`~/.claude/sessions/`) — redact any `ANTHROPIC_API_KEY` or base URL overrides
- **Keep** session IDs from the queue entry (they're references, not secrets)
- **Keep** `autoswe_status`, `attempt_count`, `guard_blocked`, `slug` — they're diagnostic, not sensitive

### Use the Template

Open a new issue on the autoSWE repo and select the **Bug Report** template (`.github/ISSUE_TEMPLATE/bug_report.md`). It has a diagnostics section with every command above pre-filled. Fill in each section with your redacted output.

### `gh` CLI note (colons in labels)

If you use the GitHub CLI here, remember every autoSWE label carries a colon (`autoswe:failed`, `autoswe:fixing`, …), which collides with `gh`'s `key:value` search-qualifier parsing. To list autoSWE issues, filter with `--label` (literal, no parsing) rather than `--search`:

```bash
# Right: --label takes the literal label
gh issue list --repo OWNER/REPO --label 'autoswe:failed'

# If you must use search, quote the value so the second colon stays inside it
gh issue list --repo OWNER/REPO --search 'label:"autoswe:failed"'
```

Single-quote the whole argument so the shell doesn't split on the colon or the `/` in `OWNER/REPO`.
