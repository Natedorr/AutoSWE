# Source: https://developers.openai.com/codex/cli/

Copy Page

Codex CLI is OpenAI’s coding agent that you can run locally from your terminal. It can read, change, and run code on your machine in the selected directory. It’sopen source[open source](https://github.com/openai/codex)and built in Rust for speed and efficiency.

ChatGPT Plus, Pro, Business, Edu, and Enterprise plans include Codex. Learn more aboutwhat’s included[what’s included](/codex/pricing).

## CLI setupChoose your package managernpmHomebrew

- 1

### Install

Install the Codex CLI withnpm.npm install commandnpm i -g @openai/codexCopy
- 2

### Run

Run Codex in a terminal. It can inspect your repository, edit files, and run commands.Run Codex commandcodexCopy

The first time you run Codex, you'll be prompted to sign in. Authenticate with your ChatGPT account or an API key.

See thepricing page[pricing page](/codex/pricing)if you're not sure which plans include Codex access.
- 3

### Upgrade

New versions of the Codex CLI are released regularly. See thechangelog[changelog](/codex/changelog)for release notes. To upgrade withnpm, run:npm upgrade commandnpm i -g @openai/codex@latestCopy

The Codex CLI is available on macOS, Windows, and Linux. On Windows, run Codex natively in PowerShell with the Windows sandbox, or use WSL2 when you need a Linux-native environment. For setup details, see theWindows setup guide[Windows setup guide](/codex/windows).

If you’re new to Codex, read thebest practices guide[best practices guide](/codex/learn/best-practices).

## Work with the Codex CLI

### Run Codex interactively

Run`codex`to start an interactive terminal UI (TUI) session.[Run Codex interactivelyRuncodexto start an interactive terminal UI (TUI) session.](/codex/cli/features#running-in-interactive-mode)

### Control model and reasoning

Use`/model`to switch between GPT-5.4, GPT-5.3-Codex, and other available models, or adjust reasoning levels.[Control model and reasoningUse/modelto switch between GPT-5.4, GPT-5.3-Codex, and other available models, or adjust reasoning levels.](/codex/cli/features#models-reasoning)

### Image inputs

Attach screenshots or design specs so Codex reads them alongside your prompt.[Image inputsAttach screenshots or design specs so Codex reads them alongside your prompt.](/codex/cli/features#image-inputs)

### Image generation

Generate or edit images directly in the CLI, and attach references when you want Codex to iterate on an existing asset.[Image generationGenerate or edit images directly in the CLI, and attach references when you want Codex to iterate on an existing asset.](/codex/cli/features#image-generation)

### Run local code review

Get your code reviewed by a separate Codex agent before you commit or push your changes.[Run local code reviewGet your code reviewed by a separate Codex agent before you commit or push your changes.](/codex/cli/features#running-local-code-review)

### Use subagents

Use subagents to parallelize complex tasks.[Use subagentsUse subagents to parallelize complex tasks.](/codex/subagents)

### Web search

Use Codex to search the web and get up-to-date information for your task.[Web searchUse Codex to search the web and get up-to-date information for your task.](/codex/cli/features#web-search)

### Codex Cloud tasks

Launch a Codex Cloud task, choose environments, and apply the resulting diffs without leaving your terminal.[Codex Cloud tasksLaunch a Codex Cloud task, choose environments, and apply the resulting diffs without leaving your terminal.](/codex/cli/features#working-with-codex-cloud)

### Scripting Codex

Automate repeatable workflows by scripting Codex with the`exec`command.[Scripting CodexAutomate repeatable workflows by scripting Codex with theexeccommand.](/codex/noninteractive)

### Model Context Protocol

Give Codex access to additional third-party tools and context with Model Context Protocol (MCP).[Model Context ProtocolGive Codex access to additional third-party tools and context with Model Context Protocol (MCP).](/codex/mcp)

### Approval modes

Choose the approval mode that matches your comfort level before Codex edits or runs commands.[Approval modesChoose the approval mode that matches your comfort level before Codex edits or runs commands.](/codex/cli/features#approval-modes)