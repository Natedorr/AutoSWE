# CLAUDE.md

This file provides guidance when working with code in this repository.

## Project Overview

autoSWE lets a user steer real coding from GitHub or Azure DevOps issue comments — without sitting in front of a terminal. It runs from cron, discovers issues carrying slash commands (`/plan`, `/fix`, `/review`, `/pr`, `/sync`, `/retry`, `/skip`, `/abort`), and drives them through a Claude Agent SDK workflow: Claude writes the plan and the code on a per-issue branch; the slash commands in the comments steer it. It is **queue-driven** — `data/queue.json` (the `autoswe_status` enum per task, derived from issue comments) is the source of truth for what runs; `autoswe:*` labels are a one-way mirror for humans and are never read back to make a decision. **Comment IDs are the state-machine identity unit** — watermarks (`last_dispatched_command_id`, `last_consumed_reply_id`) compare provider comment IDs, not timestamps. The intended deployment is a dedicated, isolated machine (the `/fix` agent runs with full permissions on purpose — see `docs/autoswe/safeguards.md`).

## Where to Look

All architecture, data shapes, and process documentation lives in `docs/autoswe/`. Edit there first.

| Topic | File |
|-------|------|
| Execution pipeline | [docs/autoswe/pipeline.md](docs/autoswe/pipeline.md) |
| Task handlers (plan, fix, PR, sync, retry) | [docs/autoswe/handlers.md](docs/autoswe/handlers.md) |
| Data shapes (queue.json + `autoswe_status`, NormalizedIssue, slugs) | [docs/autoswe/data-model.md](docs/autoswe/data-model.md) |
| Labels (read-only mirror of `autoswe_status`) | [docs/autoswe/labels.md](docs/autoswe/labels.md) |
| Slash commands | [docs/autoswe/slash-commands.md](docs/autoswe/slash-commands.md) |
| Configuration (env, repos.json, prompts) | [docs/autoswe/config.md](docs/autoswe/config.md) |
| Harness profiles (harnesses.json, backends) | [docs/autoswe/harnesses.md](docs/autoswe/harnesses.md) |
| Provider abstraction (GitHub, Azure) | [docs/autoswe/providers.md](docs/autoswe/providers.md) |
| Git worktrees | [docs/autoswe/git-worktrees.md](docs/autoswe/git-worktrees.md) |
| Safeguards (limits, loop protection) | [docs/autoswe/safeguards.md](docs/autoswe/safeguards.md) |
| Debugging & operations | [docs/autoswe/debugging.md](docs/autoswe/debugging.md) |
| Testing strategy | [docs/autoswe/testing.md](docs/autoswe/testing.md) |

## Working Rules for Claude

### Test Convention (MANDATORY)

When autoSWE processes an issue that touches any `autoswe/` module, the work **must include tests**. Specifically:

- New handler return values → `test_dispatch_status.py`
- New label transitions → `test_lifecycle_labels.py`
- New slash commands or parsing rules → `test_lifecycle_parse.py`
- New restart/resume logic → `test_sync_restart.py`
- New planner output patterns → `test_planner_returns.py`
- New reviewer output patterns → `test_reviewer_returns.py`
- New coder/ship behavior → `test_coder_returns.py` or `test_ship.py`
- New dispatch inner-loop logic → `test_dispatch_helpers.py`
- New sync behavior → `test_sync_helpers.py`
- New worktree operations → `test_worktree.py`
- New config options → `test_config.py`
- New harness config or backend factory logic → `test_config.py` or `test_backend_factory.py`
- Codex backend (JSONL parsing, subprocess, capabilities) → `test_codex_backend.py`
- Queue store invariants, crash recovery → `test_queue_store.py`
- PID contention, repo locks, concurrency races → `test_concurrency.py`
- Queue/API drift scenarios → `test_drift_detection.py`
- Fake protocol coverage, provider parity → `test_fake_parity.py`
- **Any bug fix that changes a full state transition** → add a row to `TRANSITIONS` in `tests/scenarios/transitions.py`. Use `scripts/capture_scenario.py` to seed from a real issue.

**Before marking an issue complete, run:**
```bash
pytest -q -m "not live"   # Must pass
ruff check autoswe tests  # Must be clean
```

### Test Markers

| Marker | Description | CI? |
|--------|-------------|-----|
| (default) | Offline tests — no network calls | Yes |
| `@pytest.mark.scenario` | Scenario-driven E2E tests (stateful fakes) | Yes |
| `@pytest.mark.live` | Hits real GitHub/Azure API via PAT | Only on master, with secret |

### Common Commands

```bash
# Activate venv first
source .venv/bin/activate        # Linux/macOS
.venv\Scripts\Activate.ps1       # Windows

python autoswe.py poller                          # single poller run: sync + dispatch
python autoswe.py poller --drain                  # keep processing until idle
python autoswe.py sync --repo owner/repo          # sync one repo
python autoswe.py dispatch                        # dispatch only (no sync)
python autoswe.py queue list                      # list all tasks
python autoswe.py queue status --repo O/R --issue N  # task details
```

### Debugging

- `tail -f logs/autoswe.log` — rotating debug log (1 MB, 3 backups). Per-issue logs live at `logs/<slug>/<slug>.log`
- `cat data/queue.json | jq` — inspect queue state
- `ls running/` — active PID and `.done` files
- To unstick a zombie `dispatched` issue: delete the `.pid` file, then `python autoswe.py sync --repo owner/repo`
- Session files: `~/.claude/projects/<encoded-worktree-path>/<session-id>.jsonl`
- See [docs/autoswe/debugging.md](docs/autoswe/debugging.md) for detailed troubleshooting.
