# Source: https://developers.openai.com/codex/models/

Copy Page

## Recommended models[gpt-5.5](/images/api/models/gpt-5.5.jpg)gpt-5.5

OpenAI's newest frontier model for complex coding, computer use, knowledge work, and research workflows in Codex.codex -m gpt-5.5Copy commandCapabilitySpeedCodex CLI & SDKCodex app & IDE extensionCodex CloudChatGPT CreditsAPI Access[gpt-5.4](/images/api/models/gpt-5.4.jpg)gpt-5.4

Flagship frontier model for professional work that brings the industry-leading coding capabilities of GPT-5.3-Codex together with stronger reasoning, tool use, and agentic workflows.codex -m gpt-5.4Copy commandCapabilitySpeedCodex CLI & SDKCodex app & IDE extensionCodex CloudChatGPT CreditsAPI Access[gpt-5.4-mini](/images/api/models/gpt-5-mini.jpg)gpt-5.4-mini

Fast, efficient mini model for responsive coding tasks and subagents.codex -m gpt-5.4-miniCopy commandCapabilitySpeedCodex CLI & SDKCodex app & IDE extensionCodex CloudChatGPT CreditsAPI Access[gpt-5.3-codex](/images/codex/codex-wallpaper-1.webp)gpt-5.3-codex

Industry-leading coding model for complex software engineering. Its coding capabilities now also power GPT-5.4.codex -m gpt-5.3-codexCopy commandCapabilitySpeedCodex CLI & SDKCodex app & IDE extensionCodex CloudChatGPT CreditsAPI Access[gpt-5.3-codex-spark](/images/codex/codex-wallpaper-2.webp)gpt-5.3-codex-spark

Text-only research preview model optimized for near-instant, real-time coding iteration. Available to ChatGPT Pro users.codex -m gpt-5.3-codex-sparkCopy commandCapabilitySpeedCodex CLI & SDKCodex app & IDE extensionCodex CloudChatGPT CreditsAPI Access

For most tasks in Codex, start with`gpt-5.5`. It is strongest for complex coding, computer use, knowledge work, and research workflows. GPT-5.5 is currently available in Codex when you sign in with ChatGPT or API-key authentication. Use`gpt-5.4-mini`

when you want a faster, lower-cost option for lighter coding tasks or subagents. The`gpt-5.3-codex-spark`model is available in research preview for ChatGPT Pro subscribers and is optimized for near-instant, real-time coding iteration.

## Alternative models[gpt-5.2](/images/api/models/gpt-5.2.jpg)gpt-5.2

Previous general-purpose model for coding and agentic tasks, including hard debugging tasks that benefit from deeper deliberation.codex -m gpt-5.2Copy commandShow details

## Other models

When you sign in with ChatGPT, Codex works best with the models listed above.

You can also point Codex at any model and provider that supports either theChat Completions[Chat Completions](https://platform.openai.com/docs/api-reference/chat)orResponses APIs[Responses APIs](https://platform.openai.com/docs/api-reference/responses)to fit your specific use case.

Support for the Chat Completions API is deprecated and will be removed in future releases of Codex.

## Configuring models

### Configure your default local model

The Codex CLI and IDE extension use the same`config.toml`configuration file[configuration file](/codex/config-basic). To specify a model, add a`model`entry to your configuration file. If you don’t specify a model, the Codex app, CLI, or IDE Extension defaults to a recommended model.
````model="gpt-5.5"````

### Choosing a different local model temporarily

In the Codex CLI, you can use the`/model`command during an active thread to change the model. In the IDE extension, you can use the model selector below the input box to choose your model.

To start a new Codex CLI thread with a specific model or to specify the model for`codex exec`you can use the`--model`/`-m`flag:
````codex -m gpt-5.5````

### Choosing your model for cloud tasks

Currently, you can’t change the default model for Codex cloud tasks.