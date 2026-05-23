# fresh_plan_command

Azure variant: a new work item with `/plan` command in the body. Sync discovers it, sets `autoswe:pending` tag, and dispatch runs the planner which outputs a plan. Final tag should be `autoswe:plan_ready`.
