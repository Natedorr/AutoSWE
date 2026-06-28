# Source: https://developers.openai.com/codex/use-cases/verified-operations-workflows/

Codex use cases[Codex](/assets/OAI_Codex-Lockup_Fallback_Black.svg)

Codex use case

# Run verified operations

Run repeatable workflows and verify the result.Difficulty**Intermediate**Time horizon**30m**

Use Codex to normalize inputs, run approved scripts or APIs, retry bounded failures, and verify the result from logs or artifacts before reporting back.

## Best for

- Operations tasks with structured inputs, explicit approval, and a result that should be auditable.
- Repeated workflows such as access updates, invite batches, quota changes, customer setup tasks, routing checks, and migration follow-ups.
- Teams that need Codex to run a narrow scope and report exactly what succeeded, failed, or needs a human decision.

# Contents
← All use cases[← All use cases](/codex/use-cases)Copy pageExport as PDF[Export as PDF](/codex/use-cases/verified-operations-workflows/?export=pdf)

Use Codex to normalize inputs, run approved scripts or APIs, retry bounded failures, and verify the result from logs or artifacts before reporting back.Intermediate30m

Related linksCodex plugins[Codex plugins](/codex/plugins)Codex automations[Codex automations](/codex/app/automations)Agent skills[Agent skills](/codex/skills)

## Best for

- Operations tasks with structured inputs, explicit approval, and a result that should be auditable.
- Repeated workflows such as access updates, invite batches, quota changes, customer setup tasks, routing checks, and migration follow-ups.
- Teams that need Codex to run a narrow scope and report exactly what succeeded, failed, or needs a human decision.

## Starter promptI need to run this workflow: Goal: [what should happen] Inputs: [CSV, Google Sheet, list, ticket, or file path] Approval or policy source: [Slack thread, doc, ticket, or none] Runner: [script, API, CLI, skill, or manual app workflow] Verification artifact: [result CSV, log, dashboard, screenshot, or other proof] Please: - inspect the inputs and ask only for missing required fields - normalize dates, amounts, owners, and IDs before running the workflow - run a dry run first when the workflow supports it - run only the approved scope - record one success or failure row per item - retry transient failures once without restarting successful rows - summarize totals, failures, retries, and verification artifacts Pause before irreversible actions or scope changes.Open in the Codex app[Open in the Codex app](codex://threads/new?prompt=I+need+to+run+this+workflow%3A%0A%0AGoal%3A+%5Bwhat+should+happen%5D%0AInputs%3A+%5BCSV%2C+Google+Sheet%2C+list%2C+ticket%2C+or+file+path%5D%0AApproval+or+policy+source%3A+%5BSlack+thread%2C+doc%2C+ticket%2C+or+none%5D%0ARunner%3A+%5Bscript%2C+API%2C+CLI%2C+skill%2C+or+manual+app+workflow%5D%0AVerification+artifact%3A+%5Bresult+CSV%2C+log%2C+dashboard%2C+screenshot%2C+or+other+proof%5D%0A%0APlease%3A%0A-+inspect+the+inputs+and+ask+only+for+missing+required+fields%0A-+normalize+dates%2C+amounts%2C+owners%2C+and+IDs+before+running+the+workflow%0A-+run+a+dry+run+first+when+the+workflow+supports+it%0A-+run+only+the+approved+scope%0A-+record+one+success+or+failure+row+per+item%0A-+retry+transient+failures+once+without+restarting+successful+rows%0A-+summarize+totals%2C+failures%2C+retries%2C+and+verification+artifacts%0A%0APause+before+irreversible+actions+or+scope+changes.)I need to run this workflow: Goal: [what should happen] Inputs: [CSV, Google Sheet, list, ticket, or file path] Approval or policy source: [Slack thread, doc, ticket, or none] Runner: [script, API, CLI, skill, or manual app workflow] Verification artifact: [result CSV, log, dashboard, screenshot, or other proof] Please: - inspect the inputs and ask only for missing required fields - normalize dates, amounts, owners, and IDs before running the workflow - run a dry run first when the workflow supports it - run only the approved scope - record one success or failure row per item - retry transient failures once without restarting successful rows - summarize totals, failures, retries, and verification artifacts Pause before irreversible actions or scope changes.

## Run operations you can audit

If you have repeatable operations you need to run regularly, such as giving access to a user, applying a batch update, or calling a script with different parameters for example, you can use Codex to automate it and give you an auditable output.

Use this workflow when Codex should run a repeatable operation and show you what happened with an artifact that counts as verification.

## Describe the task and inputs

- Give Codex the input table, files, tickets, or other list it should batch run the process on.
- Point it to the approval source or policy that defines the allowed scope, if applicable.
- Tell Codex which script, API, skill, CLI, or app workflow should do the work.
- Optionally, ask for a dry run when the workflow supports one.
- Ask Codex to run the batch operation and record one success or failure row per item.

Keep the scope narrow, and add instructions for Codex to run the operation only when it has all the required inputs. If a row is missing a required field, Codex should flag that row instead of guessing.

Connect the tools you use to run the operation withplugins[plugins](/codex/plugins), for example your ticketing system or your spreadsheet with list items.

## Require proof to verify the result

A useful operations run includes an artifact that you or a teammate can inspect, such as a result CSV, a log file, a dashboard link, a screenshot, a PR check, or any other proof that the operation was successful. When using the Codex app, you can inspect thisartifact[artifact](/codex/app/artifacts)directly in the artifact viewer after the run to verify the result.

## Turn the run into a reusable workflow

After the first successful run, ask Codex to capture the repeatable parts. For common workflows, this can become askill[skill](/codex/skills), or anautomation[automation](/codex/app/automations)that runs on a schedule.Turn this operations run into a [reusable Codex skill/an automation]. Capture: - required inputs - approval or policy source - runner command, API, skill, or app workflow - dry-run behavior if applicable - verification artifact - retry policy - final report format Keep the operation narrow and pause before irreversible actions.

For scheduled operations, use an automation only after the manual run produces reliable output. Keep sensitive actions that might affect access or data permanently draft-only unless you explicitly want Codex to take them.

## Related use cases

### Manage your inbox

Use Codex with Gmail to find emails that need attention, draft responses in your voice, pull...AutomationIntegrations[Manage your inboxUse Codex with Gmail to find emails that need attention, draft responses in your voice, pull...AutomationIntegrations](/codex/use-cases/manage-your-inbox)

### Prioritize Slack action items

Use Codex with Slack and the tools where work happens to find direct asks, implicit...AutomationIntegrations[Prioritize Slack action itemsUse Codex with Slack and the tools where work happens to find direct asks, implicit...AutomationIntegrations](/codex/use-cases/slack-action-triage)

### Set up a teammate

Connect the tools where work happens, teach one thread what matters, then add an automation...AutomationIntegrations[Set up a teammateConnect the tools where work happens, teach one thread what matters, then add an automation...AutomationIntegrations](/codex/use-cases/proactive-teammate)