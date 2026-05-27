# Source: https://developers.openai.com/codex/use-cases/automation-bug-triage/

Codex use cases[Codex](/assets/OAI_Codex-Lockup_Fallback_Black.svg)

Codex use case

# Automate bug triage

Turn daily bug reports into a prioritized list, then automate the sweep.Difficulty**Intermediate**Time horizon**1h**

Ask Codex to check recent alerts, issues, failed checks, logs, and chat reports, tune the list in one thread, then run that sweep on a schedule.

## Best for

- Teams that track bugs across Sentry alerts, Slack threads, Linear issues, GitHub issues, failing PR checks, support tickets, or logs.
- Triage workflows you want to run manually in one Codex thread before scheduling as an automation.

# Contents
← All use cases[← All use cases](/codex/use-cases)Copy pageExport as PDF[Export as PDF](/codex/use-cases/automation-bug-triage/?export=pdf)

Ask Codex to check recent alerts, issues, failed checks, logs, and chat reports, tune the list in one thread, then run that sweep on a schedule.Intermediate1h

Related linksCodex automations[Codex automations](/codex/app/automations)Codex plugins[Codex plugins](/codex/plugins)Codex MCP[Codex MCP](/codex/mcp)Use Codex in Linear[Use Codex in Linear](/codex/integrations/linear)

## Best for

- Teams that track bugs across Sentry alerts, Slack threads, Linear issues, GitHub issues, failing PR checks, support tickets, or logs.
- Triage workflows you want to run manually in one Codex thread before scheduling as an automation.

## Skills & Plugins

- GitHub[GitHub](https://github.com/openai/plugins/tree/main/plugins/github)Read issues, pull requests, comments, review threads, and failed checks when GitHub is part of your bug intake.
- Sentry[Sentry](https://github.com/openai/skills/tree/main/skills/.curated/sentry)Inspect production errors, stack traces, affected releases, and event context when alerts are part of the sweep.
- Slack[Slack](https://github.com/openai/plugins/tree/main/plugins/slack)Read the channels or threads where teammates report bugs and prepare a draft summary for a team channel.
- Linear[Linear](https://github.com/openai/plugins/tree/main/plugins/linear)Read bug queues, find existing issues, draft updates, or prepare linked follow-up tickets after the triage pass.

Skill | Why use it
GitHub[GitHub](https://github.com/openai/plugins/tree/main/plugins/github) | Read issues, pull requests, comments, review threads, and failed checks when GitHub is part of your bug intake.
Sentry[Sentry](https://github.com/openai/skills/tree/main/skills/.curated/sentry) | Inspect production errors, stack traces, affected releases, and event context when alerts are part of the sweep.
Slack[Slack](https://github.com/openai/plugins/tree/main/plugins/slack) | Read the channels or threads where teammates report bugs and prepare a draft summary for a team channel.
Linear[Linear](https://github.com/openai/plugins/tree/main/plugins/linear) | Read bug queues, find existing issues, draft updates, or prepare linked follow-up tickets after the triage pass.

## Starter promptRun a bug triage sweep for [repo/service/team] covering the last [time window]. Use these plugins: [@Sentry / @Slack / @Linear / @GitHub / none] Input sources: - Sentry: [project / alert link / none] - Slack: [channel / thread links / none] - Linear: [team / project / view / issue query / none] - GitHub: [repo / issue query / PR checks / none] - Other: [logs / support tickets / deploy link / dashboard / attached file / none] Output format: First, name any input source you could not access. Then return a prioritized list of bugs, sorted from P0 to P3. If you find no bugs, say: No qualifying bugs found. For each bug, include: - Priority: P0, P1, P2, or P3 - Title - Evidence (links or short citations) - Recommended next action Rules: - Do not post, create, assign, label, close, rerun, or edit anything. - Group duplicate reports under one bug. - Keep observed evidence separate from guesses.Open in the Codex app[Open in the Codex app](codex://threads/new?prompt=Run+a+bug+triage+sweep+for+%5Brepo%2Fservice%2Fteam%5D+covering+the+last+%5Btime+window%5D.%0A%0AUse+these+plugins%3A+%5B%40Sentry+%2F+%40Slack+%2F+%40Linear+%2F+%40GitHub+%2F+none%5D%0A%0AInput+sources%3A%0A-+Sentry%3A+%5Bproject+%2F+alert+link+%2F+none%5D%0A-+Slack%3A+%5Bchannel+%2F+thread+links+%2F+none%5D%0A-+Linear%3A+%5Bteam+%2F+project+%2F+view+%2F+issue+query+%2F+none%5D%0A-+GitHub%3A+%5Brepo+%2F+issue+query+%2F+PR+checks+%2F+none%5D%0A-+Other%3A+%5Blogs+%2F+support+tickets+%2F+deploy+link+%2F+dashboard+%2F+attached+file+%2F+none%5D%0A%0AOutput+format%3A%0AFirst%2C+name+any+input+source+you+could+not+access.%0AThen+return+a+prioritized+list+of+bugs%2C+sorted+from+P0+to+P3.%0AIf+you+find+no+bugs%2C+say%3A+No+qualifying+bugs+found.%0A%0AFor+each+bug%2C+include%3A%0A-+Priority%3A+P0%2C+P1%2C+P2%2C+or+P3%0A-+Title%0A-+Evidence+%28links+or+short+citations%29%0A-+Recommended+next+action%0A%0ARules%3A%0A-+Do+not+post%2C+create%2C+assign%2C+label%2C+close%2C+rerun%2C+or+edit+anything.%0A-+Group+duplicate+reports+under+one+bug.%0A-+Keep+observed+evidence+separate+from+guesses.)Run a bug triage sweep for [repo/service/team] covering the last [time window]. Use these plugins: [@Sentry / @Slack / @Linear / @GitHub / none] Input sources: - Sentry: [project / alert link / none] - Slack: [channel / thread links / none] - Linear: [team / project / view / issue query / none] - GitHub: [repo / issue query / PR checks / none] - Other: [logs / support tickets / deploy link / dashboard / attached file / none] Output format: First, name any input source you could not access. Then return a prioritized list of bugs, sorted from P0 to P3. If you find no bugs, say: No qualifying bugs found. For each bug, include: - Priority: P0, P1, P2, or P3 - Title - Evidence (links or short citations) - Recommended next action Rules: - Do not post, create, assign, label, close, rerun, or edit anything. - Group duplicate reports under one bug. - Keep observed evidence separate from guesses.

## How to use

Ask Codex to check the places where bugs already appear: Sentry alerts, Linear issues, GitHub issues, PR checks, deploy logs, support tickets, and Slack threads. Start with one manual sweep, tune the report in-thread, then run it on a schedule.

Use one Codex thread for the whole triage loop:

- Run an on-demand sweep and get a draft list.
- Review the list and give feedback in that same thread.
- Turn that same thread into an automation.
- Optional: ask Codex to draft Linear issues, Slack updates, GitHub comments, or handoff notes when you are confident in the report.

Before you start, install theplugins[plugins](/codex/plugins)Codex needs, such as Sentry, Slack, Linear, or GitHub. In the starter prompt, replace the bracketed plugin list with real`@`plugin chips. Then replace each bracketed source with the exact place to search: a Sentry project or alert URL, Slack channel or thread, Linear team, view, or query, GitHub repo, issue query, or PR check, deploy link, log file, support queue, or dashboard.

## Phase 1: Run the sweep

Start Codex from the repo that owns the bugs when local context helps: tests, repo tooling, build checks, or CI failures. You can also run the sweep from any repo if your bug sources are available through plugins, connectors, MCP servers, links, exports, pasted logs, or attachments.

Run the starter prompt above first. Keep only the plugins and sources that are part of your sweep.

For example, a filled-in prompt can name the plugins and the exact queues, channels, or repos you want in the sweep.[A Codex prompt that mentions Slack, Linear, and GitHub plugins and lists the exact sources to check for a bug triage sweep](/images/codex/use-cases/bug-automation-light.png)[A Codex prompt that mentions Slack, Linear, and GitHub plugins and lists the exact sources to check for a bug triage sweep](/images/codex/use-cases/bug-automation-dark.png)[A Codex prompt that mentions Slack, Linear, and GitHub plugins and lists the exact sources to check for a bug triage sweep](/images/codex/use-cases/bug-automation-light.png)[A Codex prompt that mentions Slack, Linear, and GitHub plugins and lists the exact sources to check for a bug triage sweep](/images/codex/use-cases/bug-automation-dark.png)

## Phase 2: Make the report useful

Before you automate, make sure the report is useful enough to read every day.

A useful first run has:

- High-signal bugs sorted from P0 to P3.
- Duplicate reports are grouped under one bug.
- Each bug has linked evidence or short citations.
- Guesses are separated from observed facts.
- Each bug has a short recommended next action.

Tune the report in the same thread before you automate it. You can ask Codex to:

- Check one more source before ranking the list.
- Drop noisy alerts that the team already knows about.
- Only return P0 and P1 bugs.
- Merge Slack reports, Sentry alerts, and GitHub failures when they point to the same bug.
- Show the single best link for each bug.
- Add enough evidence that someone else can reproduce or route the issue.

## Phase 3: Automate it

When the on-demand report is useful, stay in the same thread and turn it into an automation. Codex can use what you refined in the thread to write the recurring automation prompt.

**Create the automation**Create a bug triage automation from the workflow we refined in this thread. Schedule: [every hour / every weekday morning / daily] Use the same sources, priority rules, duplicate grouping, evidence style, and P0-P3 report format from this thread. When you write the automation prompt, include the plugin mentions or connected-source instructions the scheduled run needs to read those sources again. Keep the automation draft-only. Do not post, create, assign, label, close, rerun, start fixes, or edit code. Before you create it, show me the automation prompt, schedule, sources, and action policy.

## Phase 4: Route follow-ups

Once the scheduled report is useful, decide where the work should go next. Codex can draft a Slack update for a team channel, write Linear issues for the bugs you want to track, write GitHub comments for a failing PR, or produce a handoff for whoever is on call.Update this bug triage automation. After each run, draft the follow-up I need: - Slack update for [channel] - Linear issues for [which bugs should become issues] - GitHub comment for [issue / PR / failing check] - Handoff note for [team / on-call / owner] Rules: - Draft the follow-up in Codex first. - Do not post to Slack, create Linear issues, or comment on GitHub until I explicitly approve that action. - Include links to existing Linear, GitHub, Slack, or alert sources when available. - Keep draft-only behavior for any action not explicitly approved.

## Tech stack

Need

Default options

Why it's needed

Need

Where bug context gathers

Default options

Sentry alerts, Slack channels, Linear views, GitHub issues, PR checks, support queues, on-call notes, logs, dashboards, and deploy notes

Why it's needed

Name the exact queues, channels, views, repos, alert links, dashboards, and files Codex should sweep.

Need

How Codex reads it

Default options

Plugins[Plugins](/codex/plugins)for Slack, Linear, GitHub, and Sentry; connectors;MCP servers[MCP servers](/codex/mcp); repo CLIs; links; exports; attachments; and pasted logs

Why it's needed

Install the existing integration when there is one. Build or configure a small MCP server, CLI, export, or dashboard link for internal sources Codex cannot read yet.

Need | Default options | Why it's needed
Where bug context gathers | Sentry alerts, Slack channels, Linear views, GitHub issues, PR checks, support queues, on-call notes, logs, dashboards, and deploy notes | Name the exact queues, channels, views, repos, alert links, dashboards, and files Codex should sweep.
How Codex reads it | Plugins[Plugins](/codex/plugins)for Slack, Linear, GitHub, and Sentry; connectors;MCP servers[MCP servers](/codex/mcp); repo CLIs; links; exports; attachments; and pasted logs | Install the existing integration when there is one. Build or configure a small MCP server, CLI, export, or dashboard link for internal sources Codex cannot read yet.

## Related use cases

### QA your app with Computer Use

Use Computer Use to exercise key flows, catch issues, and finish with a bug report.AutomationQuality[QA your app with Computer UseUse Computer Use to exercise key flows, catch issues, and finish with a bug report.AutomationQuality](/codex/use-cases/qa-your-app-with-computer-use)

### Add evals to your AI application

Ask Codex to inspect your AI application, identify the behavior you want to evaluate, and...EvaluationQuality[Add evals to your AI applicationAsk Codex to inspect your AI application, identify the behavior you want to evaluate, and...EvaluationQuality](/codex/use-cases/ai-app-evals)

### Clean and prepare messy data

Drag in or mention a messy CSV or spreadsheet, describe the problems you see, and ask Codex...DataKnowledge Work[Clean and prepare messy dataDrag in or mention a messy CSV or spreadsheet, describe the problems you see, and ask Codex...DataKnowledge Work](/codex/use-cases/clean-messy-data)