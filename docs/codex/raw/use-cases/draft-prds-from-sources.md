# Source: https://developers.openai.com/codex/use-cases/draft-prds-from-sources/

Codex use cases[Codex](/assets/OAI_Codex-Lockup_Fallback_Black.svg)

Codex use case

# Draft PRDs from internal context

Create product requirements documents from Linear, Slack, source documents, and meeting notes.Difficulty**Easy**Time horizon**30m**

Use Codex with the $documents skill and connected apps such as Linear, Slack, Notion or Google Drive to create a reviewable PRD with the expected sections, a timeline, decisions, open questions, and a source appendix.

## Best for

- Product teams turning planning context into a PRD, proposal, launch brief, or decision memo.
- PMs who need to draft a PRD quickly after aligning with the team in internal discussions.

# Contents
← All use cases[← All use cases](/codex/use-cases)Copy pageExport as PDF[Export as PDF](/codex/use-cases/draft-prds-from-sources/?export=pdf)

Use Codex with the $documents skill and connected apps such as Linear, Slack, Notion or Google Drive to create a reviewable PRD with the expected sections, a timeline, decisions, open questions, and a source appendix.Easy30m

Related linksCodex plugins[Codex plugins](/codex/plugins)Agent skills[Agent skills](/codex/skills)Codex app[Codex app](/codex/app)

## Best for

- Product teams turning planning context into a PRD, proposal, launch brief, or decision memo.
- PMs who need to draft a PRD quickly after aligning with the team in internal discussions.

## Skills & Plugins

- DocumentsCreate, edit, and verify a DOCX when the PRD should become a polished file instead of chat text.
- Slack[Slack](https://github.com/openai/plugins/tree/main/plugins/slack)Read product discussions, launch threads, decision notes, and follow-up questions from approved channels or thread links.
- Linear[Linear](https://github.com/openai/plugins/tree/main/plugins/linear)Read projects, issues, priorities, acceptance criteria, and open work that should shape the PRD.
- Google Drive[Google Drive](https://github.com/openai/plugins/tree/main/plugins/google-drive)Read planning docs, research notes, specs, exported meeting notes, and source folders.
- Notion[Notion](https://github.com/openai/plugins/tree/main/plugins/notion)Read roadmap pages, project notes, meeting notes, and team wikis that should shape the PRD.

Skill | Why use it
Documents | Create, edit, and verify a DOCX when the PRD should become a polished file instead of chat text.
Slack[Slack](https://github.com/openai/plugins/tree/main/plugins/slack) | Read product discussions, launch threads, decision notes, and follow-up questions from approved channels or thread links.
Linear[Linear](https://github.com/openai/plugins/tree/main/plugins/linear) | Read projects, issues, priorities, acceptance criteria, and open work that should shape the PRD.
Google Drive[Google Drive](https://github.com/openai/plugins/tree/main/plugins/google-drive) | Read planning docs, research notes, specs, exported meeting notes, and source folders.
Notion[Notion](https://github.com/openai/plugins/tree/main/plugins/notion) | Read roadmap pages, project notes, meeting notes, and team wikis that should shape the PRD.

## Starter promptUse $documents to create a PRD for [feature or product area] from @linear [project or milestone], @slack [channel or thread], and @google-drive or @notion [planning docs, research notes, meeting notes, or source folder]. Include the problem, users, goals/non-goals, requirements, UX, technical considerations, metrics, launch plan, risks, open questions, decisions, timeline, and source appendix. Cite the sources behind requirement-level claims. If sources disagree, call out the conflict instead of choosing silently. Draft only. Do not post, update Linear, or share the document until I approve it.Open in the Codex app[Open in the Codex app](codex://threads/new?prompt=Use+%24documents+to+create+a+PRD+for+%5Bfeature+or+product+area%5D+from+%40linear+%5Bproject+or+milestone%5D%2C+%40slack+%5Bchannel+or+thread%5D%2C+and+%40google-drive+or+%40notion+%5Bplanning+docs%2C+research+notes%2C+meeting+notes%2C+or+source+folder%5D.%0A%0AInclude+the+problem%2C+users%2C+goals%2Fnon-goals%2C+requirements%2C+UX%2C+technical+considerations%2C+metrics%2C+launch+plan%2C+risks%2C+open+questions%2C+decisions%2C+timeline%2C+and+source+appendix.%0A%0ACite+the+sources+behind+requirement-level+claims.+If+sources+disagree%2C+call+out+the+conflict+instead+of+choosing+silently.+Draft+only.+Do+not+post%2C+update+Linear%2C+or+share+the+document+until+I+approve+it.)Use $documents to create a PRD for [feature or product area] from @linear [project or milestone], @slack [channel or thread], and @google-drive or @notion [planning docs, research notes, meeting notes, or source folder]. Include the problem, users, goals/non-goals, requirements, UX, technical considerations, metrics, launch plan, risks, open questions, decisions, timeline, and source appendix. Cite the sources behind requirement-level claims. If sources disagree, call out the conflict instead of choosing silently. Draft only. Do not post, update Linear, or share the document until I approve it.

## Introduction

Before working on a new product or feature, it’s common to draft a product requirements document (PRD) to align on the scope and requirements. Most often than not, the context needed to write that PRD is already available in the team’s internal systems: tickets on Linear, discussions on Slack, drafts in Notion or Google Drive, etc. Codex can gather this context and draft a PRD that you can review and iterate on, while keeping the source trail visible.Your browser does not support the video tag.

## Choose the sources

Start with the sources you want Codex to use: the Linear project, the Slack planning channel or thread, and any Drive docs, Notion pages, meeting notes, or local files that should be cited in the PRD. You should also clearly outline the PRD sections you expect, such as the problem, users, requirements, UX, tech, launch plan, timeline, or decisions.

- Start with`$documents`when the output should be a real DOCX.
- Name the sources directly: the Linear project or milestone, the Slack channel or thread, and the docs or notes Codex should cite.
- Give Codex the PRD section contract.
- Review the source appendix first, then the requirements and open questions.
- Use the same thread to resolve gaps, tighten scope, and prepare the handoff.

## Refine in the same thread

Use the starter prompt on this page for the first draft. If something is missing, point Codex at the missing source instead of starting over.

## Check the source trail

Before sharing the PRD, ask Codex to list the claims with weak or missing support, the unresolved questions, and the decisions it treated as confirmed. If the source appendix does not make those easy to audit, keep refining the same thread before exporting or posting anything.

### Suggested prompt

**Check the Source Trail**Before I share this PRD, check the source trail. List: - requirements with weak or missing source support - open questions that still need an owner or decision - decisions you treated as confirmed - any claims that should move out of the PRD and into open questions Keep the source appendix linked and easy to audit.

## Related use cases

### Coordinate new-hire onboarding

Use Codex to gather approved new-hire context, stage tracker updates, draft team-by-team...IntegrationsData[Coordinate new-hire onboardingUse Codex to gather approved new-hire context, stage tracker updates, draft team-by-team...IntegrationsData](/codex/use-cases/new-hire-onboarding)

### Prepare meeting briefs

Use Codex with Calendar, Drive, Slack, and Gmail to gather approved sources before a...IntegrationsKnowledge Work[Prepare meeting briefsUse Codex with Calendar, Drive, Slack, and Gmail to gather approved sources before a...IntegrationsKnowledge Work](/codex/use-cases/meeting-prep-briefs)

### Run event playbooks

Use Codex with Slack, Google Drive, and Calendar to gather planning context, draft...IntegrationsKnowledge Work[Run event playbooksUse Codex with Slack, Google Drive, and Calendar to gather planning context, draft...IntegrationsKnowledge Work](/codex/use-cases/event-launch-playbooks)