# Codex CLI — Overview

## What is Codex?

Codex CLI is a **local coding agent** from OpenAI. It runs on your machine, reads your codebase, makes edits, and runs shell commands — all under your control via sandboxing and approval policies.

It is available in three forms:
1. **Codex CLI** — Terminal-based agent (this documentation)
2. **Codex IDE Extension** — VS Code, Cursor, Windsurf plugin
3. **Codex App** — Desktop app (`codex app`) and web (chatgpt.com/codex)

## Key Facts for AutoSWE Integration

| Detail | Value |
|---|---|
| Language | Written in **Rust** |
| Installation | `npm install -g @openai/codex` or Homebrew or curl script |
| Configuration | `~/.codex/config.toml` (user) or `.codex/config.toml` (project) |
| Authentication | ChatGPT subscription OR `OPENAI_API_KEY` |
| **Python SDK** | **Does not exist.** Codex is a CLI/IDE tool, not a library. |
| Automation | `codex exec` for non-interactive/scripted use |
| API surface | MCP server, subagent spawning, `codex exec --json` |

## No Python SDK

OpenAI has not released a Python SDK for Codex. If you want programmatic control:

- **`codex exec`** — Run Codex non-interactively from scripts/CI. Captures stdout as JSON or text.
- **MCP Server** — Codex can run as an MCP server for external agent orchestration.
- **Subagent system** — Codex spawns specialized agents (worker, explorer, custom) with parallel execution.
- **CLI flags** — `--model`, `--sandbox`, `--ask-for-approval`, `--cd`, `--add-dir`, `--search`.

## Architecture

```
User Prompt
    ↓
Codex Agent (local, sandboxed)
    ├── Model (gpt-5.5, gpt-5.4, gpt-5.3-codex-spark, etc.)
    ├── Tools (file read/write, shell exec, web search, MCP)
    ├── Subagents (parallel workers)
    └── Skills (task-specific instruction packages)
    ↓
Sandbox + Approval Policy
    ↓
Changes to working tree
```

## Official Resources

- **Documentation:** [developers.openai.com/codex](https://developers.openai.com/codex)
- **GitHub:** [github.com/openai/codex](https://github.com/openai/codex)
- **Skills registry:** [agentskills.io](https://agentskills.io)
