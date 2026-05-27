# Source: https://developers.openai.com/codex/use-cases/user-stories-to-ui-mocks/

Codex use cases[Codex](/assets/OAI_Codex-Lockup_Fallback_Black.svg)

Codex use case

# Turn user stories into UI mocks

Convert product feedback, issue threads, and design context into mockups your team can react to and implement.Difficulty**Easy**Time horizon**30m**

Use Codex to gather product feedback from Slack, Linear, Google Drive, normalize it into user stories and constraints, then generate UI mockups with ImageGen. When the direction is chosen, turn the mock into a working prototype.

## Best for

- Product teams turning scattered feedback into a visual direction for a feature.
- Design and engineering teams that want mockups grounded in source material before building.
- Teams who want to iterate fast based on user feedback.

# Contents
← All use cases[← All use cases](/codex/use-cases)Copy pageExport as PDF[Export as PDF](/codex/use-cases/user-stories-to-ui-mocks/?export=pdf)

Use Codex to gather product feedback from Slack, Linear, Google Drive, normalize it into user stories and constraints, then generate UI mockups with ImageGen. When the direction is chosen, turn the mock into a working prototype.Easy30m

Related linksCodex plugins[Codex plugins](/codex/plugins)

## Best for

- Product teams turning scattered feedback into a visual direction for a feature.
- Design and engineering teams that want mockups grounded in source material before building.
- Teams who want to iterate fast based on user feedback.

## Skills & Plugins

- Slack[Slack](https://github.com/openai/plugins/tree/main/plugins/slack)Search approved feedback channels and threads for user stories, pain points, quotes, and open questions.
- Linear[Linear](https://github.com/openai/plugins/tree/main/plugins/linear)Pull feature requests, bug reports, labels, priorities, and project context into the mock brief.
- Google Drive[Google Drive](https://github.com/openai/plugins/tree/main/plugins/google-drive)Read research notes, call summaries, docs, sheets, and slides that contain product feedback or design requirements.
- Figma[Figma](https://github.com/openai/plugins/tree/main/plugins/figma)Fetch design context, screenshots, and design-system references so mocks do not drift away from the product's visual language.
- ImageGenGenerate UI mockups, variations, and visual truth from the synthesized stories and design constraints.
- Build Web Apps[Build Web Apps](https://github.com/openai/plugins/tree/main/plugins/build-web-apps)Turn the selected mock into a working web prototype and verify the implementation against the mock.

Skill | Why use it
Slack[Slack](https://github.com/openai/plugins/tree/main/plugins/slack) | Search approved feedback channels and threads for user stories, pain points, quotes, and open questions.
Linear[Linear](https://github.com/openai/plugins/tree/main/plugins/linear) | Pull feature requests, bug reports, labels, priorities, and project context into the mock brief.
Google Drive[Google Drive](https://github.com/openai/plugins/tree/main/plugins/google-drive) | Read research notes, call summaries, docs, sheets, and slides that contain product feedback or design requirements.
Figma[Figma](https://github.com/openai/plugins/tree/main/plugins/figma) | Fetch design context, screenshots, and design-system references so mocks do not drift away from the product's visual language.
ImageGen | Generate UI mockups, variations, and visual truth from the synthesized stories and design constraints.
Build Web Apps[Build Web Apps](https://github.com/openai/plugins/tree/main/plugins/build-web-apps) | Turn the selected mock into a working web prototype and verify the implementation against the mock.

## Starter promptTurn this [user story/set of user feedbacks] into a UI mock for a feature that would solve the problem, using these sources as context: - @slack [channels or thread links] - @linear [issue links, project, team, or view] - @google-drive [research notes, survey export, doc, sheet, or slide deck] Do that while respecting the current design system and existing UI [provide Figma file or screenshot as reference].Open in the Codex app[Open in the Codex app](codex://threads/new?prompt=Turn+this+%5Buser+story%2Fset+of+user+feedbacks%5D+into+a+UI+mock+for+a+feature+that+would+solve+the+problem%2C+using+these+sources+as+context%3A%0A-+%40slack+%5Bchannels+or+thread+links%5D%0A-+%40linear+%5Bissue+links%2C+project%2C+team%2C+or+view%5D%0A-+%40google-drive+%5Bresearch+notes%2C+survey+export%2C+doc%2C+sheet%2C+or+slide+deck%5D%0A%0ADo+that+while+respecting+the+current+design+system+and+existing+UI+%5Bprovide+Figma+file+or+screenshot+as+reference%5D.)Turn this [user story/set of user feedbacks] into a UI mock for a feature that would solve the problem, using these sources as context: - @slack [channels or thread links] - @linear [issue links, project, team, or view] - @google-drive [research notes, survey export, doc, sheet, or slide deck] Do that while respecting the current design system and existing UI [provide Figma file or screenshot as reference].

## Introduction

Product teams often collect feedback from various sources, such as Slack threads, Linear issues, Google Drive docs or sheets, or customer-call notes. Sometimes, they have clear user stories illustrating a problem they want to solve, and sometimes, the context lives in those sources.

Codex can gather this context and turn it into a UI mock for a feature that would solve the problem, and once validated, can be implemented into the product.

## Generate visual truth

If you have a clear user story, you can start with that. If not, you can have a discussion with Codex first, gathering context from different sources and synthesizing it into a user story.

Then, you can ask Codex to use ImageGen to create a few mock directions. The mocks should preserve the product’s information architecture and design-system constraints.

If helpful, you can provide screenshots of the current UI or a Figma file as reference.

Do this until you are satisfied with the mock. The more scoped the changes are, the more likely Codex is to generate a mock that can be implemented directly.

## Move from mock to prototype

Use the final mock image that you want Codex to implement. Re-attach this image in a new turn rather than continuing the conversation directly. You can then ask Codex to implement the mock – optionally using theBuild Web Apps plugin[Build Web Apps plugin](/codex/plugins/build-web-apps)if you’re building a web app – to turn it into a working prototype:Use this image as a reference and implement in this repository this feature. Use this conversation as context to help you implement it with the right constraints. Minimize the creation of new components: explore the codebase and reuse existing components and design system when possible.

## Related use cases

### Generate slide decks

Use Codex to update existing presentations or build new decks by editing slides directly...DataIntegrations[Generate slide decksUse Codex to update existing presentations or build new decks by editing slides directly...DataIntegrations](/codex/use-cases/generate-slide-decks)

### Coordinate new-hire onboarding

Use Codex to gather approved new-hire context, stage tracker updates, draft team-by-team...IntegrationsData[Coordinate new-hire onboardingUse Codex to gather approved new-hire context, stage tracker updates, draft team-by-team...IntegrationsData](/codex/use-cases/new-hire-onboarding)

### Draft PRDs from internal context

Use Codex with the $documents skill and connected apps such as Linear, Slack, Notion or...IntegrationsKnowledge Work[Draft PRDs from internal contextUse Codex with the $documents skill and connected apps such as Linear, Slack, Notion or...IntegrationsKnowledge Work](/codex/use-cases/draft-prds-from-sources)