# Source: https://developers.openai.com/codex/quickstart/

Copy Page

Every ChatGPT plan includes Codex.

You can also use Codex with API credits by signing in with an OpenAI API key.

## SetupChoose an optionAppRecommendedIDE extensionCodex in your IDECLICodex in your terminalCloudCodex in your browser

The Codex app is available on macOS and Windows.

Most Codex app features are available on both platforms. Platform-specific exceptions are noted in the relevant docs.

- 

Download and install the Codex app

Download the Codex app for macOS or Windows. Choose the Intel build if you’re using an Intel-based Mac.Download for macOS (Apple Silicon)[Download for macOS (Apple Silicon)](https://persistent.oaistatic.com/codex-app-prod/Codex.dmg)Download for macOS (Intel)[Download for macOS (Intel)](https://persistent.oaistatic.com/codex-app-prod/Codex-latest-x64.dmg)Need a different operating system?Download forWindows[Download forWindows](https://get.microsoft.com/installer/download/9PLM9XGG6VKS?cid=website_cta_psi)

Get notified for Linux[Get notified for Linux](https://openai.com/form/codex-app/)
- 

Open Codex and sign in

Once you downloaded and installed the Codex app, open it and sign in with your ChatGPT account or an OpenAI API key.

If you sign in with an OpenAI API key, some functionality such ascloud threads[cloud threads](/codex/prompting#threads)might not be available.
- 

Select a project

Choose a project folder that you want Codex to work in.

If you used the Codex app, CLI, or IDE Extension before you’ll see past projects that you worked on.
- 

Send your first message

After choosing the project, make sure**Local**is selected to have Codex work on your machine and send your first message to Codex.

You can ask Codex anything about the project or your computer in general. Here are some examples:Tell me about this projectCopiedBuild a classic Snake game in this repo.CopiedFind and fix bugs in my codebase with minimal, high-confidence changes.Copied

If you need more inspiration, exploreCodex use cases[Codex use cases](/codex/use-cases). If you’re new to Codex, read thebest practices guide[best practices guide](/codex/learn/best-practices).

Install the Codex extension for your IDE.

- 

Install the Codex extension

Download it for your editor:

- Download for Visual Studio Code[Download for Visual Studio Code](vscode:extension/openai.chatgpt)
- Download for Cursor[Download for Cursor](cursor:extension/openai.chatgpt)
- Download for Windsurf[Download for Windsurf](windsurf:extension/openai.chatgpt)
- Download for Visual Studio Code Insiders[Download for Visual Studio Code Insiders](https://marketplace.visualstudio.com/items?itemName=openai.chatgpt)
- 

Open the Codex panel

Once installed, the Codex extension appears in the sidebar alongside your other extensions. It may be hidden in the collapsed section. You can move the Codex panel to the right side of the editor if you prefer.
- 

Sign in and start your first task

Sign in with your ChatGPT account or an API key to get started.

Codex starts in Agent mode by default, which lets it read files, run commands, and write changes in your project directory.Tell me about this projectCopiedBuild a classic Snake game in this repo.CopiedFind and fix bugs in my codebase with minimal, high-confidence changes.Copied
- 

Use Git checkpoints

Codex can modify your codebase, so consider creating Git checkpoints before and after each task so you can easily revert changes if needed. If you’re new to Codex, read thebest practices guide[best practices guide](/codex/learn/best-practices).Learn more about the Codex IDE extension[Learn more about the Codex IDE extension](/codex/ide)

The Codex CLI is supported on macOS, Windows, and Linux.

- 

Install the Codex CLI

Install with npm:
````npminstall-g@openai/codex````

Install with Homebrew:
````brewinstallcodex````

- 

Run`codex`and sign in

Run`codex`in your terminal to get started. You’ll be prompted to sign in with your ChatGPT account or an API key.
- 

Ask Codex to work in your current directory

Once authenticated, you can ask Codex to perform tasks in the current directory.Tell me about this projectCopiedBuild a classic Snake game in this repo.CopiedFind and fix bugs in my codebase with minimal, high-confidence changes.Copied
- 

Use Git checkpoints

Codex can modify your codebase, so consider creating Git checkpoints before and after each task so you can easily revert changes if needed. If you’re new to Codex, read thebest practices guide[best practices guide](/codex/learn/best-practices).Learn more about the Codex CLI[Learn more about the Codex CLI](/codex/cli)

Use Codex in the cloud atchatgpt.com/codex[chatgpt.com/codex](https://chatgpt.com/codex).

- 

Open Codex in your browser

Go tochatgpt.com/codex[chatgpt.com/codex](https://chatgpt.com/codex). You can also delegate a task to Codex by tagging`@codex`in a GitHub pull request comment (requires signing in to ChatGPT).
- 

Set up an environment

Before starting your first task, set up an environment for Codex. Open the environment settings atchatgpt.com/codex[chatgpt.com/codex](https://chatgpt.com/codex/settings/environments)and follow the steps to connect a GitHub repository.
- 

Launch a task and monitor progress

Once your environment is ready, launch coding tasks from theCodex interface[Codex interface](https://chatgpt.com/codex). You can monitor progress in real time by viewing logs, or let tasks run in the background.Tell me about this projectCopiedExplain the top failure modes of my application's architecture.CopiedFind and fix bugs in my codebase with minimal, high-confidence changes.Copied
- 

Review changes and create a pull request

When a task completes, review the proposed changes in the diff view. You can iterate on the results or create a pull request directly in your GitHub repository.

Codex also provides a preview of the changes. You can accept the PR as is, or check out the branch locally to test the changes:
````gitfetchgitcheckout<branch-name>````
Learn more about Codex cloud[Learn more about Codex cloud](/codex/cloud)

## Next stepsLearn more about the Codex app

Use the Codex app to work with your local projects.[Learn more about the Codex appUse the Codex app to work with your local projects.](/codex/app)Migrate to Codex

Move supported instruction files, MCP server configuration, skills, and subagents into Codex.[Migrate to CodexMove supported instruction files, MCP server configuration, skills, and
subagents into Codex.](/codex/migrate)