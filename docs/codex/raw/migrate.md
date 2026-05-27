# Source: https://developers.openai.com/codex/migrate/

Copy Page

Use the import flow to bring your instructions, configuration, skills, MCP servers, hooks, subagents, and recent sessions from another agent into Codex. Codex migrates the parts it can handle directly and can open a follow-up thread to help migrate anything that remains.[Import from another agent in General settings](/images/codex/migrate/import-flow-light.png)[Import from another agent in General settings](/images/codex/migrate/import-flow-dark.png)[Import from another agent in General settings](/images/codex/migrate/import-flow-light.png)[Import from another agent in General settings](/images/codex/migrate/import-flow-dark.png)

## Start the migration

- Open**Settings**in the Codex app.
- On the**General**page, find**Import other agent setup**.
- Select**Import**or**Import again**.
- Review what Codex found, choose what to bring over, then select**Import**.
- After the import finishes, select**View imported files**if you want to inspect the result.

## How migration works

Codex checks both your user-level setup and the current project. User-level setup comes from files on your machine; project-level setup comes from files in the repository you have open.

When you import, Codex:

- Detects the setup it can find.
- Imports the selected items it can migrate directly.
- Checks again after the import finishes.
- Offers to continue the migration in a new thread if anything still needs follow-up work.

## What Codex can import

Detected setup | Codex destination
Instruction files | `AGENTS.md`[AGENTS.md](/codex/guides/agents-md)
`settings.json` | `config.toml`[config.toml](/codex/config-basic)
Skills | Codex skills[Codex skills](/codex/skills)
Recent sessions from the last 30 days | Codex threads and projects
MCP server configuration | Codex MCP configuration[Codex MCP configuration](/codex/mcp)
Hooks | Codex hooks[Codex hooks](/codex/hooks)
Slash commands | Codex skills[Codex skills](/codex/skills)
Subagents | Codex agents[Codex agents](/codex/subagents)

## Finish remaining setup in a new thread

Some detected setup does not have a clean one-to-one mapping into Codex. For those items, Codex can open a new thread with the`migrate-to-codex`[migrate-to-codex](https://github.com/openai/skills/tree/main/skills/.curated/migrate-to-codex)skill to help finish the migration.

When that happens, Codex shows the remaining setup and offers**Continue in Codex**.[Additional setup found after import](/images/codex/migrate/additional-setup-light.png)[Additional setup found after import](/images/codex/migrate/additional-setup-dark.png)[Additional setup found after import](/images/codex/migrate/additional-setup-light.png)[Additional setup found after import](/images/codex/migrate/additional-setup-dark.png)

If you continue, Codex opens a new thread with the remaining work already filled in. The thread keeps user-level setup separate from project-level setup so you can see where each remaining item belongs.[Follow-up migration task in Codex](/images/codex/migrate/continue-with-codex-light.png)[Follow-up migration task in Codex](/images/codex/migrate/continue-with-codex-dark.png)[Follow-up migration task in Codex](/images/codex/migrate/continue-with-codex-light.png)[Follow-up migration task in Codex](/images/codex/migrate/continue-with-codex-dark.png)

## What to review after import

Review any migrated setup before you rely on it, especially:

- Tool restrictions or permissions in imported skills and agents.
- MCP server settings that use custom authentication, headers, environment variables, or transports.
- Hooks whose behavior may differ in Codex.
- Plugins, marketplaces, or other remaining setup that needs manual follow-up.
- Prompt templates or command-style prompts that depend on arguments, shell interpolation, or file-path placeholders.

## After you switch

Once the import finishes, open one of your migrated projects and continue from there. If you are new to Codex, see thequickstart[quickstart](/codex/quickstart)for the rest of the setup flow.