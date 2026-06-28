# Source: https://developers.openai.com/codex/use-cases/use-your-computer-with-codex/

Codex use cases[Codex](/assets/OAI_Codex-Lockup_Fallback_Black.svg)

Codex use case

# Use your computer with Codex

Let Codex click, type, and navigate apps on your Mac.Difficulty**Easy**Time horizon**5m**

Use Computer Use to hand off multi-step tasks across Mac apps, windows, and files.

## Best for

- Tasks that move across apps, windows, browser sessions, or local files on your Mac
- Work you want to hand off and let Codex continue in the background

# Contents
← All use cases[← All use cases](/codex/use-cases)Copy pageExport as PDF[Export as PDF](/codex/use-cases/use-your-computer-with-codex/?export=pdf)

Use Computer Use to hand off multi-step tasks across Mac apps, windows, and files.Easy5m

Related linksComputer Use[Computer Use](/codex/app/computer-use)Plugins[Plugins](/codex/plugins)Customize Codex[Customize Codex](/codex/concepts/customization)

## Best for

- Tasks that move across apps, windows, browser sessions, or local files on your Mac
- Work you want to hand off and let Codex continue in the background

## Starter prompt@Computer [do the task you want completed across your Mac] For example: - Play some music to help me focus. - Help me add my interview notes from Notes to Ashby. - Look through my Messages app for the trip ideas Brooke sent me this week, add the best options to a new note called "Yosemite ideas", and draft a reply back to her.Open in the Codex app[Open in the Codex app](codex://threads/new?prompt=%40Computer+%5Bdo+the+task+you+want+completed+across+your+Mac%5D%0A%0AFor+example%3A%0A-+Play+some+music+to+help+me+focus.%0A-+Help+me+add+my+interview+notes+from+Notes+to+Ashby.%0A-+Look+through+my+Messages+app+for+the+trip+ideas+Brooke+sent+me+this+week%2C+add+the+best+options+to+a+new+note+called+%22Yosemite+ideas%22%2C+and+draft+a+reply+back+to+her.)@Computer [do the task you want completed across your Mac] For example: - Play some music to help me focus. - Help me add my interview notes from Notes to Ashby. - Look through my Messages app for the trip ideas Brooke sent me this week, add the best options to a new note called "Yosemite ideas", and draft a reply back to her.

## Introduction

You can let Codex operate an app the same way you would: by clicking, seeing, and typing.Computer Use[Computer Use](/codex/app/computer-use)is useful when the task lives inside a normal app UI, even if that app does not have a dedicated plugin.

This works especially well for tasks that jump between apps or windows, such as collecting notes, updating a system of record, copying details from one place to another, or drafting a reply after checking context in a few different apps.

## How to use

- Install theComputer Use plugin[Computer Use plugin](/codex/app/computer-use).
- Start your request with`@Computer`, or mention a specific app such as`@Slack`or`@Messages`.
- Describe the task and the outcome you want.
- Approve access when Codex needs it, then let it continue the task in the background.

If you mention a specific app and a plugin exists for that app, Codex may prefer the plugin over Computer Use. That is usually what you want. If no plugin exists, Codex can fall back to Computer Use and operate the app directly.

For example:

- `@Computer Play some music to help me focus.`
- `@Computer Help me add my interview notes from Notes to Ashby.`
- `@Computer Go through my Slack and add reminders for everything I need to do by end of day.`

## Practical tips

### Choose the browser Codex should use

Computer Use takes control of the app it is operating. If you want to keep working in one browser while Codex browses in another, tell it which browser to use. You can also set a default incustomization[customization](/codex/concepts/customization), for example: “When using Computer Use for web browsing tasks, default to Chrome instead of Safari.”

### Avoid parallel runs in the same app

Do not run two Computer Use tasks against the same app at the same time. That makes it much harder for Codex to keep stable context about the current window and state.

### Stay signed in

For smoother runs, make sure you are already signed in to the apps and services you want Codex to use. If your Mac locks while Computer Use is running, the activity will stop.

## Good follow-ups

Once the task finishes, keep the same thread open if you want Codex to summarize what it changed, double-check the result, or turn the workflow into a more repeatable pattern throughcustomization[customization](/codex/concepts/customization).

## Suggested prompt

**Hand Off One Computer Task**@Computer [do the task you want completed across your Mac] For example: - Play some music to help me focus. - Help me add my interview notes from Notes to Ashby. - Look through my Messages app for the trip ideas Brooke sent me this week, add the best options to a new note called "Yosemite ideas", and draft a reply back to her.

## Related use cases

### Clean and prepare messy data

Drag in or mention a messy CSV or spreadsheet, describe the problems you see, and ask Codex...DataKnowledge Work[Clean and prepare messy dataDrag in or mention a messy CSV or spreadsheet, describe the problems you see, and ask Codex...DataKnowledge Work](/codex/use-cases/clean-messy-data)

### Complete tasks from messages

Use Computer Use to read one Messages thread, complete the task, and draft a reply.Knowledge WorkIntegrations[Complete tasks from messagesUse Computer Use to read one Messages thread, complete the task, and draft a reply.Knowledge WorkIntegrations](/codex/use-cases/complete-tasks-from-messages)

### Coordinate new-hire onboarding

Use Codex to gather approved new-hire context, stage tracker updates, draft team-by-team...IntegrationsData[Coordinate new-hire onboardingUse Codex to gather approved new-hire context, stage tracker updates, draft team-by-team...IntegrationsData](/codex/use-cases/new-hire-onboarding)