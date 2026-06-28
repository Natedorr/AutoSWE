# Source: https://developers.openai.com/codex/cli/slash-commands/

Copy Page

Slash commands give you fast, keyboard-first control over Codex. Type`/`in the composer to open the slash popup, choose a command, and Codex will perform actions such as switching models, adjusting permissions, or summarizing long conversations without leaving the terminal.

This guide shows you how to:

- Find the right built-in slash command for a task
- Steer an active session with commands like`/model`,`/fast`,`/personality`,`/permissions`,`/approve`,`/raw`,`/agent`, and`/status`

## Built-in slash commands

Codex ships with the following commands. Open the slash popup and start typing the command name to filter the list.

When a task is already running, you can type a slash command and press`Tab`to queue it for the next turn. Codex parses queued slash commands when they run, so command menus and errors appear after the current turn finishes. Slash completion still works before you queue the command.

Command | Purpose | When to use it
`/permissions`[/permissions](#update-permissions-with-permissions) | Set what Codex can do without asking first. | Relax or tighten approval requirements mid-session, such as switching between Auto and Read Only.
`/ide`[/ide](#include-ide-context-with-ide) | Include open files, current selection, and other IDE context. | Pull editor context into the next prompt without re-explaining what’s open in your IDE.
`/keymap`[/keymap](#remap-tui-shortcuts-with-keymap) | Remap TUI keyboard shortcuts. | Inspect and persist custom shortcut bindings in`config.toml`.
`/vim`[/vim](#toggle-vim-mode-with-vim) | Toggle Vim mode for the composer. | Switch between Vim normal/insert behavior and the default composer editing mode.
`/sandbox-add-read-dir`[/sandbox-add-read-dir](#grant-sandbox-read-access-with-sandbox-add-read-dir) | Grant sandbox read access to an extra directory (Windows only). | Unblock commands that need to read an absolute directory path outside the current readable roots.
`/agent`[/agent](#switch-agent-threads-with-agent) | Switch the active agent thread. | Inspect or continue work in a spawned subagent thread.
`/apps`[/apps](#browse-apps-with-apps) | Browse apps (connectors) and insert them into your prompt. | Attach an app as`$app-slug`before asking Codex to use it.
`/plugins`[/plugins](#browse-plugins-with-plugins) | Browse installed and discoverable plugins. | Inspect plugin tools, install suggested plugins, or manage plugin availability.
`/hooks`[/hooks](#review-hooks-with-hooks) | Review lifecycle hooks. | Inspect configured hooks, trust new or changed hooks, or disable non-managed hooks before they run.
`/clear`[/clear](#clear-the-terminal-and-start-a-new-chat-with-clear) | Clear the terminal and start a fresh chat. | Reset the visible UI and conversation together when you want a fresh start.
`/compact`[/compact](#keep-transcripts-lean-with-compact) | Summarize the visible conversation to free tokens. | Use after long runs so Codex retains key points without blowing the context window.
`/copy`[/copy](#copy-the-latest-response-with-copy) | Copy the latest completed Codex output. | Grab the latest finished response or plan text without manually selecting it. You can also press`Ctrl+O`.
`/diff`[/diff](#review-changes-with-diff) | Show the Git diff, including files Git isn’t tracking yet. | Review Codex’s edits before you commit or run tests.
`/exit`[/exit](#exit-the-cli-with-quit-or-exit) | Exit the CLI (same as`/quit`). | Alternative spelling; both commands exit the session.
`/experimental`[/experimental](#toggle-experimental-features-with-experimental) | Toggle experimental features. | Enable optional features such as subagents from the CLI.
`/approve`[/approve](#approve-an-auto-review-denial-with-approve) | Approve one retry of a recent auto review denial. | Retry a command or action that the auto reviewer denied.
`/memories`[/memories](#configure-memories-with-memories) | Configure memory use and generation. | Turn memory injection or memory generation on or off without leaving the TUI.
`/skills`[/skills](#use-skills-with-skills) | Browse and use skills. | Improve task-specific behavior by selecting a relevant local skill.
`/hooks`[/hooks](#view-lifecycle-hooks-with-hooks) | View and manage lifecycle hooks. | Inspect hook configuration loaded into the current session.
`/feedback`[/feedback](#send-feedback-with-feedback) | Send logs to the Codex maintainers. | Report issues or share diagnostics with support.
`/init`[/init](#generate-agentsmd-with-init) | Generate an`AGENTS.md`scaffold in the current directory. | Capture persistent instructions for the repository or subdirectory you’re working in.
`/logout`[/logout](#sign-out-with-logout) | Sign out of Codex. | Clear local credentials when using a shared machine.
`/mcp`[/mcp](#list-mcp-tools-with-mcp) | List configured Model Context Protocol (MCP) tools. | Check which external tools Codex can call during the session; add`verbose`for server details.
`/mention`[/mention](#highlight-files-with-mention) | Attach a file to the conversation. | Point Codex at specific files or folders you want it to inspect next.
`/model`[/model](#set-the-active-model-with-model) | Choose the active model (and reasoning effort, when available). | Switch between general-purpose models (`gpt-4.1-mini`) and deeper reasoning models before running a task.
`/fast`[/fast](#toggle-fast-mode-with-fast) | Toggle a Fast service tier when the model catalog exposes one. | Turn the current model’s Fast tier on or off, or check whether the thread is using it.
`/plan`[/plan](#switch-to-plan-mode-with-plan) | Switch to plan mode and optionally send a prompt. | Ask Codex to propose an execution plan before implementation work starts.
`/goal`[/goal](#set-or-view-a-task-goal-with-goal) | Set, pause, resume, view, or clear a task goal. | Give Codex a persistent target to track while a larger task runs.
`/personality`[/personality](#set-a-communication-style-with-personality) | Choose a communication style for responses. | Make Codex more concise, more explanatory, or more collaborative without changing your instructions.
`/ps`[/ps](#check-background-terminals-with-ps) | Show experimental background terminals and their recent output. | Check long-running commands without leaving the main transcript.
`/stop`[/stop](#stop-background-terminals-with-stop) | Stop all background terminals. | Cancel background terminal work started by the current session.
`/fork`[/fork](#fork-the-current-conversation-with-fork) | Fork the current conversation into a new thread. | Branch the active session to explore a new approach without losing the current transcript.
`/side`[/side](#start-a-side-conversation-with-side) | Start an ephemeral side conversation. | Ask a focused follow-up without disrupting the main thread’s transcript.
`/raw`[/raw](#toggle-raw-scrollback-with-raw) | Toggle raw scrollback mode. | Make terminal selection and copying less formatted while reviewing long output.
`/resume`[/resume](#resume-a-saved-conversation-with-resume) | Resume a saved conversation from your session list. | Continue work from a previous CLI session without starting over.
`/new`[/new](#start-a-new-conversation-with-new) | Start a new conversation inside the same CLI session. | Reset the chat context without leaving the CLI when you want a fresh prompt in the same repo.
`/quit`[/quit](#exit-the-cli-with-quit-or-exit) | Exit the CLI. | Leave the session immediately.
`/review`[/review](#ask-for-a-working-tree-review-with-review) | Ask Codex to review your working tree. | Run after Codex completes work or when you want a second set of eyes on local changes.
`/status`[/status](#inspect-the-session-with-status) | Display session configuration and token usage. | Confirm the active model, approval policy, writable roots, and remaining context capacity.
`/debug-config`[/debug-config](#inspect-config-layers-with-debug-config) | Print config layer and requirements diagnostics. | Debug precedence and policy requirements, including experimental network constraints.
`/statusline`[/statusline](#configure-footer-items-with-statusline) | Configure TUI status-line fields interactively. | Pick and reorder footer items (model/context/limits/git/tokens/session) and persist in config.toml.
`/title`[/title](#configure-terminal-title-items-with-title) | Configure terminal window or tab title fields interactively. | Pick and reorder title items such as project, status, thread, branch, model, and task progress.
`/theme`[/theme](#choose-a-syntax-theme-with-theme) | Choose a syntax-highlighting theme. | Preview and persist a terminal syntax-highlighting theme.

`/quit`and`/exit`both exit the CLI. Use them only after you have saved or committed any important work.

Use`/permissions`to adjust what Codex can do without asking first. Use`/approve`only when you need to retry a recent action that automatic review denied.

## Control your session with slash commands

The following workflows keep your session on track without restarting Codex.

### Set the active model with`/model`

- Start Codex and open the composer.
- Type`/model`and press Enter.
- Choose a model such as`gpt-4.1-mini`or`gpt-4.1`from the popup.

Expected: Codex confirms the new model in the transcript. Run`/status`to verify the change.

### Toggle Fast mode with`/fast`

- Type`/fast on`,`/fast off`, or`/fast status`.
- If you want the setting to persist, confirm the update when Codex offers to save it.

Expected: Codex reports whether the current model’s Fast service tier is on or off for the current thread. In the TUI footer, you can also show a Fast mode status-line item with`/statusline`.

Fast tier commands are catalog-driven. If the current model doesn’t advertise a Fast tier, Codex won’t show`/fast`.

### Set a communication style with`/personality`

Use`/personality`to change how Codex communicates without rewriting your prompt.

- In an active conversation, type`/personality`and press Enter.
- Choose a style from the popup.

Expected: Codex confirms the new style in the transcript and uses it for later responses in the thread.

Codex supports`friendly`,`pragmatic`, and`none`personalities. Use`none`to disable personality instructions.

If the active model doesn’t support personality-specific instructions, Codex hides this command.

### Switch to plan mode with`/plan`

- Type`/plan`and press Enter to switch the active conversation into plan mode.
- Optional: provide inline prompt text (for example,`/plan Propose a migration plan for this service`).
- You can paste content or attach images while using inline`/plan`arguments.

Expected: Codex enters plan mode and uses your optional inline prompt as the first planning request.

While a task is already running,`/plan`is temporarily unavailable.

### Set or view a task goal with`/goal`

- Type`/goal <objective>`to set the goal, for example`/goal Finish the migration and keep tests green`.
- Type`/goal`to view the current goal.
- Use`/goal pause`,`/goal resume`, or`/goal clear`to pause, resume, or remove it.

Expected: Codex keeps the goal attached to the active thread while work continues.

Goal objectives must be non-empty and at most 4,000 characters. For longer instructions, put the details in a file and point the goal at that file.

### Toggle experimental features with`/experimental`

- Type`/experimental`and press Enter.
- Toggle the features you want (for example, Apps or Smart Approvals), then restart Codex if the prompt asks you to.

Expected: Codex saves your feature choices to config and applies them on restart.

### Approve an auto review denial with`/approve`

Use`/approve`when the automatic reviewer denied a recent action and you want Codex to retry it once.

- Type`/approve`.
- Confirm the retry when Codex shows the relevant denied action.

Expected: Codex retries that denied action once under the current session policy.

### Configure memories with`/memories`

- Type`/memories`.
- Choose whether Codex should use existing memories, generate new memories, or keep memory behavior disabled.

Expected: Codex updates the relevant memory settings for future sessions.

### Use skills with`/skills`

- Type`/skills`.
- Pick the skill you want Codex to apply.

Expected: Codex inserts the selected skill context so the next request follows that skill’s instructions.

### View lifecycle hooks with`/hooks`

- Type`/hooks`.
- Review the loaded lifecycle hook configuration.

Expected: Codex shows the hooks that can run in the current session.

### Clear the terminal and start a new chat with`/clear`

- Type`/clear`and press Enter.

Expected: Codex clears the terminal, resets the visible transcript, and starts a fresh chat in the same CLI session.

UnlikeCtrl+L,`/clear`starts a new conversation.

Ctrl+Lonly clears the terminal view and keeps the current chat. Codex disables both actions while a task is in progress.

### Update permissions with`/permissions`

- Type`/permissions`and press Enter.
- Select the approval preset that matches your comfort level, for example`Auto`for hands-off runs or`Read Only`to review edits.

Expected: Codex announces the updated policy. Future actions respect the updated approval mode until you change it again.

### Include IDE context with`/ide`

- Type`/ide`.
- Add optional inline text if you want to explain what Codex should do with the current IDE selection or open files.

Expected: Codex includes available IDE context in the next prompt.

### Toggle Vim mode with`/vim`

- Type`/vim`.
- Continue editing in the composer.

Expected: Codex toggles composer Vim mode for the current session. To make Vim mode the default for new sessions, set`tui.vim_mode_default = true`in`config.toml`.

### Copy the latest response with`/copy`

- Type`/copy`and press Enter.

Expected: Codex copies the latest completed Codex output to your clipboard.

If a turn is still running,`/copy`uses the latest completed output instead of the in-progress response. The command is unavailable before the first completed Codex output and immediately after a rollback.

You can also pressCtrl+Ofrom the main TUI to copy the latest completed response without opening the slash command menu.

### Toggle raw scrollback with`/raw`

- Type`/raw`,`/raw on`, or`/raw off`.

Expected: Codex toggles raw scrollback mode, which makes terminal selection and copying more direct. You can also use the defaultAlt+Rbinding or persist the default with`tui.raw_output_mode = true`.

### Grant sandbox read access with`/sandbox-add-read-dir`

This command is available only when running the CLI natively on Windows.

- Type`/sandbox-add-read-dir C:\absolute\directory\path`and press Enter.
- Confirm the path is an existing absolute directory.

Expected: Codex refreshes the Windows sandbox policy and grants read access to that directory for later commands that run in the sandbox.

### Inspect the session with`/status`

- In any conversation, type`/status`.
- Review the output for the active model, approval policy, writable roots, and current token usage.

Expected: You see a summary like what`codex status`prints in the shell, confirming Codex is operating where you expect.

### Inspect config layers with`/debug-config`

- Type`/debug-config`.
- Review the output for config layer order (lowest precedence first), on/off state, and policy sources.

Expected: Codex prints layer diagnostics plus policy details such as`allowed_approval_policies`,`allowed_sandbox_modes`,`mcp_servers`,`rules`,`enforce_residency`, and`experimental_network`when configured.

Use this output to debug why an effective setting differs from`config.toml`.

### Configure footer items with`/statusline`

- Type`/statusline`.
- Use the picker to toggle and reorder items, then confirm.

Expected: The footer status line updates immediately and persists to`tui.status_line`in`config.toml`.

Available status-line items include model, model+reasoning, context stats, rate limits, git branch, token counters, session id, current directory/project root, and Codex version.

### Configure terminal title items with`/title`

- Type`/title`.
- Use the picker to toggle and reorder items, then confirm.

Expected: The terminal window or tab title updates immediately and persists to`tui.terminal_title`in`config.toml`.

Available title items include app name, project, spinner, status, thread, git branch, model, and task progress.

### Choose a syntax theme with`/theme`

- Type`/theme`.
- Preview a theme from the picker, then confirm.

Expected: Codex updates syntax highlighting and persists the choice to`tui.theme`in`config.toml`.

### Remap TUI shortcuts with`/keymap`

Use`/keymap`to inspect, update, and persist keyboard shortcut bindings for the TUI.

- Type`/keymap`.
- Pick the shortcut context and action you want to change.
- Enter the new binding or remove the existing one.

Expected: Codex updates the active keymap and writes the custom binding to`tui.keymap`in`config.toml`.

Key bindings use names such as`ctrl-a`,`shift-enter`, and`page-down`. Context-specific bindings override`tui.keymap.global`; an empty binding list unbinds the action.

### Check background terminals with`/ps`

- Type`/ps`.
- Review the list of background terminals and their status.

Expected: Codex shows each background terminal’s command plus up to three recent, non-empty output lines so you can gauge progress at a glance.

Background terminals appear when`unified_exec`is in use; otherwise, the list may be empty.

### Stop background terminals with`/stop`

- Type`/stop`.
- Confirm if Codex asks before stopping the listed terminals.

Expected: Codex stops all background terminals for the current session.`/clean`is still available as an alias for`/stop`.

### Keep transcripts lean with`/compact`

- After a long exchange, type`/compact`.
- Confirm when Codex offers to summarize the conversation so far.

Expected: Codex replaces earlier turns with a concise summary, freeing context while keeping critical details.

### Review changes with`/diff`

- Type`/diff`to inspect the Git diff.
- Scroll through the output inside the CLI to review edits and added files.

Expected: Codex shows changes you’ve staged, changes you haven’t staged yet, and files Git hasn’t started tracking, so you can decide what to keep.

### Highlight files with`/mention`

- Type`/mention`followed by a path, for example`/mention src/lib/api.ts`.
- Select the matching result from the popup.

Expected: Codex adds the file to the conversation, ensuring follow-up turns reference it directly.

### Start a new conversation with`/new`

- Type`/new`and press Enter.

Expected: Codex starts a fresh conversation in the same CLI session, so you can switch tasks without leaving your terminal.

Unlike`/clear`,`/new`doesn’t clear the current terminal view first.

### Resume a saved conversation with`/resume`

- Type`/resume`and press Enter.
- Choose the session you want from the saved-session picker.

Expected: Codex reloads the selected conversation’s transcript so you can pick up where you left off, keeping the original history intact.

### Fork the current conversation with`/fork`

- Type`/fork`and press Enter.

Expected: Codex clones the current conversation into a new thread with a fresh ID, leaving the original transcript untouched so you can explore an alternative approach in parallel.

If you need to fork a saved session instead of the current one, run`codex fork`in your terminal to open the session picker.

### Start a side conversation with`/side`

Use`/side`to start an ephemeral fork from the current conversation without switching away from the main task.

- Type`/side`to open a side conversation.
- Optionally add inline text, for example`/side Check whether this plan has an obvious risk`.
- Return to the parent thread after the focused detour finishes.

Expected: Codex opens a side conversation whose transcript is separate from the parent thread. While you are in side mode, the TUI continues to show parent-thread status so you can see whether the main task is still running.

`/side`is unavailable inside another side conversation and during review mode.

### Generate`AGENTS.md`with`/init`

- Run`/init`in the directory where you want Codex to look for persistent instructions.
- Review the generated`AGENTS.md`, then edit it to match your repository conventions.

Expected: Codex creates an`AGENTS.md`scaffold you can refine and commit for future sessions.

### Ask for a working tree review with`/review`

- Type`/review`.
- Follow up with`/diff`if you want to inspect the exact file changes.

Expected: Codex summarizes issues it finds in your working tree, focusing on behavior changes and missing tests. It uses the current session model unless you set`review_model`in`config.toml`.

### List MCP tools with`/mcp`

- Type`/mcp`.
- Review the list to confirm which MCP servers and tools are available.

Expected: You see the configured Model Context Protocol (MCP) tools Codex can call in this session.

Use`/mcp verbose`to include detailed server diagnostics. If you pass anything other than`verbose`, Codex shows the command usage.

### Browse apps with`/apps`

- Type`/apps`.
- Pick an app from the list.

Expected: Codex inserts the app mention into the composer as`$app-slug`, so you can immediately ask Codex to use it.

### Browse plugins with`/plugins`

- Type`/plugins`.
- Choose a marketplace tab, then pick a plugin to inspect its capabilities or available actions.

Expected: Codex opens the plugin browser so you can review installed plugins, discoverable plugins that your configuration allows, and installed plugin state. PressSpaceon an installed plugin to toggle its enabled state.

### Review hooks with`/hooks`

- Type`/hooks`.
- Choose a hook event to inspect the matching handlers.
- Trust, disable, or re-enable non-managed hooks as needed.

Expected: Codex opens the hook browser so you can review configured lifecycle hooks. Managed hooks appear as managed and can’t be disabled from the user hook browser.

### Switch agent threads with`/agent`

- Type`/agent`and press Enter.
- Select the thread you want from the picker.

Expected: Codex switches the active thread so you can inspect or continue that agent’s work.

### Send feedback with`/feedback`

- Type`/feedback`and press Enter.
- Follow the prompts to include logs or diagnostics.

Expected: Codex collects the requested diagnostics and submits them to the maintainers.

### Sign out with`/logout`

- Type`/logout`and press Enter.

Expected: Codex clears local credentials for the current user session.

### Exit the CLI with`/quit`or`/exit`

- Type`/quit`(or`/exit`) and press Enter.

Expected: Codex exits immediately. Save or commit any important work first.