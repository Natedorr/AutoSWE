# Debugging & Operations

## Live Output

```bash
tail -f logs/autoswe.log         # Rotating debug log (1 MB, 3 backups)
ls logs/                          # Per-issue logs: logs/<slug>/<slug>.log
```

## Queue State

`data/queue.json` is the source of truth for runs — `autoswe_status` per task is what dispatch keys off (the `autoswe:*` labels just mirror it). When something looks stuck, trust this file, not the label on the issue.

```bash
cat data/queue.json | jq                              # Full queue
cat data/queue.json | jq 'to_entries[] | {k:.key, s:.value.autoswe_status, c:.value.pending_command}'
cat data/queue.json | jq 'to_entries[] | select(.value.autoswe_status=="planning" or .value.autoswe_status=="fixing" or .value.autoswe_status=="syncing" or .value.autoswe_status=="reviewing" or .value.autoswe_status=="shipping") | .key'   # what claims to be running
```

`queue.json` keeps every task it has ever seen (including COMPLETED (`fixed`/`synced`/`shipped`/`reviewed`)/`skipped`/`gh_closed`), so it grows over time. To prune terminal tasks (stop the poller first, take a backup):

```bash
cp data/queue.json data/queue.json.bak
jq 'with_entries(select(.value.autoswe_status as $s | ($s != "fixed" and $s != "synced" and $s != "shipped" and $s != "reviewed" and $s != "skipped") or (.value.gh_closed | not)))' data/queue.json.bak > data/queue.json
```

## Active Jobs

```bash
ls running/                      # .pid files = running, .done files = last handler result
cat running/gh_owner_repo_42.pid # Current process PID
cat running/gh_owner_repo_42.done  # Last handler return string
```

## Unsticking a Zombie RUNNING Task

A task stuck at a RUNNING status (`planning`/`fixing`/`syncing`/`reviewing`/`shipping`) means a run died without cleaning up.

1. Delete the PID file: `rm running/gh_owner_repo_42.pid`
2. Fix the status in the queue — either edit `data/queue.json` directly (set the task's `autoswe_status` to `failed` or `pending`), or re-sync and let it re-derive: `python autoswe.py sync --repo owner/repo`
3. Confirm: `python autoswe.py queue status --repo owner/repo --issue 42`

The dispatch loop auto-cleans stale PID files (dead process), so often step 1 alone plus the next cron firing is enough. Editing the `autoswe:*` label by hand does **nothing** — it's a mirror, not an input; fix `autoswe_status` instead.

## Nuclear Option: Full Reset

When the poller crashes hard (Python crash, SIGKILL, reboot mid-run, runaway Claude session), use the cleanup scripts to reset everything in one shot:

```bash
# POSIX (Linux/macOS)
./cleanup.sh

# Windows (PowerShell)
.\cleanup.ps1
```

What the scripts do (in order):
1. Kill **all** `claude` and `node` processes — deepest leaves first — **this WILL terminate your interactive Claude Code session** if one is running.
2. Kill the poller process tree bottom-up: `poller.sh`/`poller.ps1` parent plus all descendant processes (python, etc.). Killing the parent releases the flock on POSIX and the named mutex on Windows. Falls back to `python autoswe.py poller` if the shell wrapper is not found.
3. Release the flock file (`/tmp/autoswe.lock` on POSIX; named mutex auto-releases on Windows when holder dies — belt-and-suspenders).
4. Delete `running/*.pid`, `running/*.done`, `running/*.result.json`.

Scripts are idempotent — running on a clean system prints an all-zero summary and exits 0. They do **not** touch `data/queue.json`, worktrees, or session files.

## Claude Session Files

Session state lives at `~/.claude/projects/<encoded-worktree-path>/<session-id>.jsonl`. The `session_id` is stored in `queue.json` for each task. Use it to locate the session file for inspection.

## Common Failure Modes

| Symptom | Label | Likely Cause | Fix |
|---------|-------|------|--|
| Handler timed out | `autoswe:failed` | `AGENT_TIMEOUT` exceeded | Increase timeout in repos.json (`agent_timeout`) or env (`AGENT_TIMEOUT`) |
| Max attempts | `autoswe:failed` | `attempt_count > MAX_ATTEMPTS` | Post `/retry` to reset counter |
| Time limit | `autoswe:failed` | `first_dispatched_at` > 2h ago | Post `/retry` (resets timer), or post `/fix` from `planned` (phase transition resets timer) |
| Stale PID | stuck at RUNNING status | Process crashed without cleanup | Delete `.pid` file, re-sync |
| No dispatch | `autoswe:pending` sits | `MAX_CONCURRENT` reached | Check `running/` for active jobs |
| Wrong model | plan/fix uses unexpected model | Model resolution order | Check repos.json phase-specific → env phase-specific → repos.json generic |

## Testing

See [docs/autoswe/testing.md](testing.md) for the 11-layer test strategy, how to capture API fixtures, add transition-matrix rows, and write scenario tests. Quick ref:

```bash
pytest -q -m "not live"        # All offline tests
pytest -q -m scenario           # Scenario-driven E2E
pytest -q -m transition         # Transition matrix
pytest tests/test_queue_store.py   # Queue invariants, crash recovery
pytest tests/test_concurrency.py   # PID contention, repo locks
pytest tests/test_drift_detection.py  # Queue/API divergence scenarios
pytest tests/test_fake_parity.py   # Fake protocol coverage
python scripts/capture_api_fixtures.py  # Re-capture canonical fixtures
```

### Test File Overview

| File | What it covers |
|------|------------|
| `tests/test_transitions.py` | Full state transitions via `patched_world` harness |
| `tests/test_queue_store.py` | LockedQueue, atomic writes, corruption recovery |
| `tests/test_concurrency.py` | PID collision, repo locks, MAX_CONCURRENT |
| `tests/test_drift_detection.py` | Queue/API divergence, watermark drift, author allowlist |
| `tests/test_fake_parity.py` | Protocol completeness, route coverage |
| `tests/test_dispatch_status.py` | Handler return status mapping |
| `tests/test_lifecycle_parse.py` | Slash command parsing |
| `tests/test_worktree.py` | Worktree operations |
