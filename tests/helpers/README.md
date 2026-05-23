# Manual Test Helpers

These scripts hit **real** Azure DevOps / GitHub APIs. They are **not** run by pytest and should only be used intentionally during integration testing.

## Scripts

| Script | Purpose |
|---|---|
| `ado_helper.sh` | Bash CLI — create WIs, post comments, manage tags, run poller, wait for dispatch |
| `ado_fetch_details.py` | Inspect ADO work items (title, status, tags, comments) |
| `ado_post_commands.py` | Post pre-scripted commands to a list of WIs, optionally run poller |
| `ado_advance_tasks.py` | "Smart" version — inspects each WI state before deciding what to post |

## Quick Reference

```bash
# Inspect work items
python3 tests/helpers/ado_fetch_details.py 92 94

# Post commands (dry run first!)
python3 tests/helpers/ado_post_commands.py --dry-run
python3 tests/helpers/ado_post_commands.py

# Create a WI via bash
tests/helpers/ado_helper.sh create "Test issue" "Description here"
tests/helpers/ado_helper.sh comment 99 "/fix"
tests/helpers/ado_helper.sh tags 99
```

## Safety

- Always `--dry-run` first with the post/advance scripts
- These use the PAT from `config/repos.json` — real mutations happen
- Output files (`ado_post_summary.json`) are gitignored
