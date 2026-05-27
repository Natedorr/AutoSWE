# Source: https://developers.openai.com/codex/use-cases/feedback-synthesis/

Codex use cases[Codex](/assets/OAI_Codex-Lockup_Fallback_Black.svg)

Codex use case

# Turn feedback into actions

Synthesize feedback from multiple sources into a reviewable artifact.Difficulty**Easy**Time horizon**30m**

Connect Codex to multiple data sources such as Slack, GitHub, Linear, or Google Drive to group feedback into a reviewable Google Sheet, Google Doc, Slack update, or recurring feedback check.

## Best for

- Analyzing feedback from Slack channels, issue threads, survey exports, support-ticket CSVs, or research notes.
- Teams that need to turn feedback into actionable insights.

# Contents
← All use cases[← All use cases](/codex/use-cases)Copy pageExport as PDF[Export as PDF](/codex/use-cases/feedback-synthesis/?export=pdf)

Connect Codex to multiple data sources such as Slack, GitHub, Linear, or Google Drive to group feedback into a reviewable Google Sheet, Google Doc, Slack update, or recurring feedback check.Easy30m

Related linksCodex plugins[Codex plugins](/codex/plugins)Codex automations[Codex automations](/codex/app/automations)Agent skills[Agent skills](/codex/skills)

## Best for

- Analyzing feedback from Slack channels, issue threads, survey exports, support-ticket CSVs, or research notes.
- Teams that need to turn feedback into actionable insights.

## Skills & Plugins

- Slack[Slack](https://github.com/openai/plugins/tree/main/plugins/slack)Read approved feedback channels or thread links.
- GitHub[GitHub](https://github.com/openai/plugins/tree/main/plugins/github)Read issues, PR comments, and discussion threads.
- Linear[Linear](https://github.com/openai/plugins/tree/main/plugins/linear)Read bug or feature queues.
- Google Drive[Google Drive](https://github.com/openai/plugins/tree/main/plugins/google-drive)Read feedback docs, exports, and folders, then create a Google Doc or Sheet.
- Google Sheets[Google Sheets](/codex/plugins)Create a feedback sheet the team can sort, comment on, and update.

Skill | Why use it
Slack[Slack](https://github.com/openai/plugins/tree/main/plugins/slack) | Read approved feedback channels or thread links.
GitHub[GitHub](https://github.com/openai/plugins/tree/main/plugins/github) | Read issues, PR comments, and discussion threads.
Linear[Linear](https://github.com/openai/plugins/tree/main/plugins/linear) | Read bug or feature queues.
Google Drive[Google Drive](https://github.com/openai/plugins/tree/main/plugins/google-drive) | Read feedback docs, exports, and folders, then create a Google Doc or Sheet.
Google Sheets[Google Sheets](/codex/plugins) | Create a feedback sheet the team can sort, comment on, and update.

## Starter promptCan you synthesize the beta feedback on [feature or product area] into a @google-sheets review sheet? Use these sources: - @slack [feedback channel or thread links] - @github [issue search or issue links] - @google-drive [survey export, notes doc, or Drive folder] In the sheet, group repeated feedback, include source links or IDs, mark confidence, and call out which items need product or engineering follow-up. Keep names and private quotes out of the visible summary unless I approve them. Do not post, send, create issues, or assign owners.Open in the Codex app[Open in the Codex app](codex://threads/new?prompt=Can+you+synthesize+the+beta+feedback+on+%5Bfeature+or+product+area%5D+into+a+%40google-sheets+review+sheet%3F%0A%0AUse+these+sources%3A%0A-+%40slack+%5Bfeedback+channel+or+thread+links%5D%0A-+%40github+%5Bissue+search+or+issue+links%5D%0A-+%40google-drive+%5Bsurvey+export%2C+notes+doc%2C+or+Drive+folder%5D%0A%0AIn+the+sheet%2C+group+repeated+feedback%2C+include+source+links+or+IDs%2C+mark+confidence%2C+and+call+out+which+items+need+product+or+engineering+follow-up.%0A%0AKeep+names+and+private+quotes+out+of+the+visible+summary+unless+I+approve+them.+Do+not+post%2C+send%2C+create+issues%2C+or+assign+owners.)Can you synthesize the beta feedback on [feature or product area] into a @google-sheets review sheet? Use these sources: - @slack [feedback channel or thread links] - @github [issue search or issue links] - @google-drive [survey export, notes doc, or Drive folder] In the sheet, group repeated feedback, include source links or IDs, mark confidence, and call out which items need product or engineering follow-up. Keep names and private quotes out of the visible summary unless I approve them. Do not post, send, create issues, or assign owners.

When feedback is spread across a Slack channel, a survey export, and a few issue threads, Codex can pull it together into a Google Sheet or Doc that the team can review.Your browser does not support the video tag.

## Create the first version

- Give Codex the feedback sources and one sentence of context.
- Ask for a Google Sheet or Doc with themes, evidence links, questions, and follow-ups.
- Use the same thread to turn the reviewed sheet into a Slack update or issue draft.
- Pin the thread and add an automation if the feedback source keeps changing.

Use the starter prompt on this page for the first pass. The sources can be plugin links, attached files, or files in Google Drive.

## Turn the sheet into the next draft

Once the sheet exists, use the same thread to make it useful for the next person. Ask Codex to add a column, split a theme, draft a Slack update, or turn a reviewed theme into an issue draft.Using the reviewed feedback sheet, draft a short Slack update. Audience: [team or channel] Include: - what changed - the top feedback themes - link to the sheet - the decision or follow-up needed Draft only. Do not post it.

## Keep a feedback channel current

For a Slack channel or issue queue that keeps getting new reports, pin the thread and ask Codex to check it on a schedule.Check this feedback source every [weekday morning / Monday / release day]. Source: [Slack channel, GitHub search, Linear view, or Google Drive folder] Use this reviewed Sheet or Doc as the running summary: [link] Only update me when there is a new theme, stronger evidence for an existing theme, or a source you cannot read. Keep the Sheet or Doc current. Do not post, send, create issues, or assign owners.

## Related use cases

### Coordinate new-hire onboarding

Use Codex to gather approved new-hire context, stage tracker updates, draft team-by-team...IntegrationsData[Coordinate new-hire onboardingUse Codex to gather approved new-hire context, stage tracker updates, draft team-by-team...IntegrationsData](/codex/use-cases/new-hire-onboarding)

### Query tabular data

Use Codex with a CSV, spreadsheet, dashboard export, Google Sheet, or local data file to...DataKnowledge Work[Query tabular dataUse Codex with a CSV, spreadsheet, dashboard export, Google Sheet, or local data file to...DataKnowledge Work](/codex/use-cases/analyze-data-export)

### Clean and prepare messy data

Drag in or mention a messy CSV or spreadsheet, describe the problems you see, and ask Codex...DataKnowledge Work[Clean and prepare messy dataDrag in or mention a messy CSV or spreadsheet, describe the problems you see, and ask Codex...DataKnowledge Work](/codex/use-cases/clean-messy-data)