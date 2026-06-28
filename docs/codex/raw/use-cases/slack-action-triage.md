# Source: https://developers.openai.com/codex/use-cases/slack-action-triage/

Codex use cases[Codex](/assets/OAI_Codex-Lockup_Fallback_Black.svg)

Codex use case

# Prioritize Slack action items

Turn Slack threads and DMs into a ranked queue of next steps.Difficulty**Easy**Time horizon**30m**

Use Codex with Slack and the tools where work happens to find direct asks, implicit follow-ups, resolved items, and the highest-impact next actions before drafting replies or handoffs.

## Best for

- People who get work through Slack and need Codex to separate live asks from already-handled chatter.
- Launch, community, support, product, and operations workstreams where context is split across DMs, channels, and threads.
- Teams that want a ranked action queue before drafting replies, handoffs, docs changes, or follow-up tasks.

# Contents
← All use cases[← All use cases](/codex/use-cases)Copy pageExport as PDF[Export as PDF](/codex/use-cases/slack-action-triage/?export=pdf)

Use Codex with Slack and the tools where work happens to find direct asks, implicit follow-ups, resolved items, and the highest-impact next actions before drafting replies or handoffs.Easy30m

Related linksCodex plugins[Codex plugins](/codex/plugins)Use Codex in Slack[Use Codex in Slack](/codex/integrations/slack)Codex automations[Codex automations](/codex/app/automations)

## Best for

- People who get work through Slack and need Codex to separate live asks from already-handled chatter.
- Launch, community, support, product, and operations workstreams where context is split across DMs, channels, and threads.
- Teams that want a ranked action queue before drafting replies, handoffs, docs changes, or follow-up tasks.

## Skills & Plugins

- Slack[Slack](https://github.com/openai/plugins/tree/main/plugins/slack)Search DMs, channels, thread replies, mentions, and shared context before deciding what still needs attention.
- Gmail[Gmail](https://github.com/openai/plugins/tree/main/plugins/gmail)Cross-check email when a Slack thread refers to an outreach, intro, or sent follow-up.
- Google Drive[Google Drive](https://github.com/openai/plugins/tree/main/plugins/google-drive)Read linked docs, decks, sheets, or source material when the Slack thread depends on an artifact.
- Google Calendar[Google Calendar](https://github.com/openai/plugins/tree/main/plugins/google-calendar)Check event timing when a thread depends on a meeting, launch, webinar, or deadline.

Skill | Why use it
Slack[Slack](https://github.com/openai/plugins/tree/main/plugins/slack) | Search DMs, channels, thread replies, mentions, and shared context before deciding what still needs attention.
Gmail[Gmail](https://github.com/openai/plugins/tree/main/plugins/gmail) | Cross-check email when a Slack thread refers to an outreach, intro, or sent follow-up.
Google Drive[Google Drive](https://github.com/openai/plugins/tree/main/plugins/google-drive) | Read linked docs, decks, sheets, or source material when the Slack thread depends on an artifact.
Google Calendar[Google Calendar](https://github.com/openai/plugins/tree/main/plugins/google-calendar) | Check event timing when a thread depends on a meeting, launch, webinar, or deadline.

## Starter promptCan you check @slack for messages to me about [workstream] from [time window] and return a ranked action queue? Look across DMs, group DMs, channel mentions, and threads. For each item, include: - source link or thread - what is being asked - whether it needs my reply, a person or lead, a docs or code change, or just a decision - why it matters - the recommended next step Before calling anything unresolved, read the latest thread replies and skip items that were already handled. Do not post messages directly but suggest drafts for my review.Open in the Codex app[Open in the Codex app](codex://threads/new?prompt=Can+you+check+%40slack+for+messages+to+me+about+%5Bworkstream%5D+from+%5Btime+window%5D+and+return+a+ranked+action+queue%3F%0A%0ALook+across+DMs%2C+group+DMs%2C+channel+mentions%2C+and+threads.%0A%0AFor+each+item%2C+include%3A%0A-+source+link+or+thread%0A-+what+is+being+asked%0A-+whether+it+needs+my+reply%2C+a+person+or+lead%2C+a+docs+or+code+change%2C+or+just+a+decision%0A-+why+it+matters%0A-+the+recommended+next+step%0A%0ABefore+calling+anything+unresolved%2C+read+the+latest+thread+replies+and+skip+items+that+were+already+handled.%0A%0ADo+not+post+messages+directly+but+suggest+drafts+for+my+review.)Can you check @slack for messages to me about [workstream] from [time window] and return a ranked action queue? Look across DMs, group DMs, channel mentions, and threads. For each item, include: - source link or thread - what is being asked - whether it needs my reply, a person or lead, a docs or code change, or just a decision - why it matters - the recommended next step Before calling anything unresolved, read the latest thread replies and skip items that were already handled. Do not post messages directly but suggest drafts for my review.

## Find the work hidden in Slack

Slack is often where a request starts, but not where the full context lives. A teammate might ask for a reply in a DM, clarify the real action in a thread, link a doc in a channel, and resolve the issue later without mentioning you again.

Use this workflow when you want Codex to read the Slack context, check whether the ask is still live, and return the few items that actually need your attention. The goal is to get a ranked action queue: what needs a reply, a decision, a person to contact, a doc update, or a handoff.

## Run the triage pass

- Give Codex a time window, workstream, person, channel, or topic.
- Ask it to search DMs, group DMs, channel mentions, and relevant thread replies.
- Have Codex read the latest thread tail before calling an item unresolved.
- Ask for a ranked queue sorted by urgency and impact.
- Ask Codex to draft the reply, handoff, or follow-up task.

After trying this and tweaking the flow to match your needs, you can turn it into athread automation[thread automation](/codex/app/automations#thread-automations)by asking Codex to do the same thing on a schedule.

## Ask for the right output

A useful triage result should explain why each item is still live. It should also skip old asks that someone answered later in the thread.

You should expect to see something like this:Codex

**Top action item:**Priya is asking for concrete customer examples, not just more ideas.

**Why it matters:**the launch update needs real people the team can contact this week.

**Evidence:**the original channel message asked for use cases, but the thread later says “please DM me if you have leads.”

**Next step:**reply with two named leads, or say you can be the example if that is more useful.

Good output makes the distinction explicit: an idea is different from a lead, a live ask is different from an FYI, and a request you already answered shouldn’t stay in the queue.

If you get too much noise or too few actionable items, tweak the prompt and if needed, mention specific slack channels you want Codex to pay attention to.

## Draft the follow-up

Once the queue is right, keep the action in the same thread. Ask Codex to draft a reply or handoff from the evidence it already gathered:Draft the Slack reply for each of these action items, using evidence from the triage pass. Do not post it directly, but suggest drafts for my review.

## Related use cases

### Set up a teammate

Connect the tools where work happens, teach one thread what matters, then add an automation...AutomationIntegrations[Set up a teammateConnect the tools where work happens, teach one thread what matters, then add an automation...AutomationIntegrations](/codex/use-cases/proactive-teammate)

### Turn meetings into follow-ups

Use Codex with Zoom transcripts and AI Companion summaries to draft customer follow-up...AutomationIntegrations[Turn meetings into follow-upsUse Codex with Zoom transcripts and AI Companion summaries to draft customer follow-up...AutomationIntegrations](/codex/use-cases/zoom-meeting-follow-ups)

### Coordinate new-hire onboarding

Use Codex to gather approved new-hire context, stage tracker updates, draft team-by-team...IntegrationsData[Coordinate new-hire onboardingUse Codex to gather approved new-hire context, stage tracker updates, draft team-by-team...IntegrationsData](/codex/use-cases/new-hire-onboarding)