---
name: Bug Report
about: Something in autoSWE is not working correctly
title: ""
labels: ["bug"]
assignees: []
---

## What Happened

<!-- Brief description of the bug -->

## Expected Behavior

<!-- What should have happened -->

## Reproduction Steps

1.
2.
3.

## Environment

- autoSWE version (commit or tag):
- Python version:
- OS:
- Provider: GitHub / Azure DevOps
- Claude model (if known):

## Task Details

- Target repo: `owner/repo`
- Issue / work-item number:
- `autoswe_status` (from `autoswe:*` label):
- Slash command that triggered it: `/plan` `/fix` `/pr` `/review` `/sync` `/retry` `/skip` `/abort`

---

## Diagnostics (run from the autoSWE install directory)

> **AI agents:** Use `docs/skills/autoswe-ops/SKILL.md` (user-invocable `autoswe-ops`) — it has every command you need. Run these on the machine where autoSWE is installed before posting or attaching the output.

### Queue entry (paste full output, redact PATs)

```bash
python autoswe.py queue status --repo OWNER/REPO --issue N | python -m json.tool
```

Key fields: `guard_blocked`, `autoswe_status`, `attempt_count`, `first_dispatched_at`, `last_dispatched_command`, `session_id`

### PID check — is something actually running?

```bash
# Active PID files
ls running/
# If a .pid exists for this task, check if the process is alive:
cat running/<slug>.pid
# Stale if the PID process is dead — delete it and re-sync

# Quick cleanup if the system crashed hard:
# POSIX:   ./cleanup.sh
# Windows: .\cleanup.ps1
```

### Logs (last 50 matching lines, redact tokens)

```bash
# Global log — search by repo+issue
grep "OWNER/REPO.*N" logs/autoswe.log | tail -50

# Per-issue log
ls logs/ && cat logs/<slug>/<slug>.log | tail -50

# Claude session file (from session_id in queue entry)
ls ~/.claude/projects/
```

**Log patterns to look for:**

| Pattern | Meaning |
|---------|---------|
| `[POLLER]` | Poller cycle info |
| `[SYNC]` | GitHub/Azure sync info |
| `[DISPATCH]` | Task dispatch decisions |
| `[DECIDE]` | State machine transitions (detailed) |
| `[CLAUDE]` | Session info — cost, duration, session ID |
| `[LIMIT]` | Guard/limit firings (max attempts, time limit) |
| `[LABEL]` | Label changes |

### Configuration (redact PATs and API keys)

```bash
# Runtime config — show non-secret keys only
grep -v 'TOKEN\|KEY\|PAT' config/autoswe.env

# Repo config
python -c "
import json
with open('config/repos.json') as f:
    r = json.load(f)
for k, v in r.items():
    if k.startswith('_'): continue
    print(f'{k}: provider={v.get(\"provider\")}, branch={v.get(\"branch\",\"main\")}')"
```

## Common Failure Mode Checklist

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Nothing happens after posting command | Poller not running | `python autoswe.py poller` |
| Stuck at RUNNING status (`planning`/`fixing`/etc.) | Process crashed, stale PID | Delete `.pid`, re-sync |
| `autoswe:failed` — max attempts | `attempt_count > MAX_ATTEMPTS` | Post `/retry` |
| `autoswe:failed` — time limit | `first_dispatched_at` > 2h ago | Post `/retry` |
| `autoswe:failed` — agent timeout | `AGENT_TIMEOUT` exceeded | Increase `agent_timeout` in repos.json |
| No dispatch, `pending` sits | `MAX_CONCURRENT` reached | Check `running/` |
| Command ignored | Repo locked by another task | Wait for current task to finish |
| Guard-blocked | `_guard_blocked: true` in queue | Only `/retry`, `/skip`, `/abort` work |

## Additional Context

<!-- Screenshots, related issues, config changes -->
