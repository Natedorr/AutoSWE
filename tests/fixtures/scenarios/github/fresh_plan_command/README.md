# fresh_plan_command

**Flow:** New issue with `/plan` in body → sync sets `autoswe:pending` → dispatch runs planner → `<AUTOSWE_PLAN>` posted → label → `autoswe:plan_ready`.

**What it tests:**
- Sync discovers slash command in issue body
- Queue task created with `pending_command = "/plan"`
- Planner invoked in `default` permission mode (read-only)
- PLAN_READY return value mapped to `autoswe:plan_ready` label
- Plan comment posted with bot marker
- Session ID saved to queue task
