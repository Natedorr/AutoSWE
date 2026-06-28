# Codex CLI Documentation

Comprehensive documentation for OpenAI's Codex CLI — a local coding agent.

> **Note:** Codex does **not** have a Python SDK. It is a Rust-based CLI/IDE tool. Programmatic integration points are `codex exec` (non-interactive mode), MCP servers, and the subagent system.

## Table of Contents

| Document | Description |
|---|---|
| [Overview](./overview.md) | What is Codex, architecture, key facts |
| [Installation](./installation.md) | Install methods, build from source, completions |
| [Authentication](./authentication.md) | ChatGPT subscription vs API key |
| [Configuration](./configuration.md) | config.toml reference — sandbox, MCP, profiles, agents |
| [AGENTS.md](./agents-md.md) | Custom instructions, discovery, overrides |
| [Sandboxing & Security](./sandboxing.md) | Sandbox modes, approvals, network, protected paths |
| [Rules](./rules.md) | Command execution policy (prefix rules) |
| [CLI Features](./cli-features.md) | Interactive mode, exec, remote TUI, images |
| [Slash Commands](./slash-commands.md) | Full slash command reference |
| [Subagents](./subagents.md) | Parallel agents, custom agents, CSV fan-out |
| [Skills](./skills.md) | Task-specific instruction packages |
| [MCP](./mcp.md) | Model Context Protocol — STDIO/HTTP servers |
| [Prompting](./prompting.md) | Prompt tips, goal mode, context management |
| [Workflows](./workflows.md) | Bug fixing, review, refactoring, prototyping |

## Quick Start for AutoSWE Integration

```bash
# Install
npm install -g @openai/codex

# Auth (API key for CI/automation)
export OPENAI_API_KEY="sk-proj-..."

# Run non-interactively
codex exec --model gpt-5.5 --sandbox workspace-write \
  --ask-for-approval never \
  "Fix the failing test in tests/test_core.py"

# With JSON output for parsing
codex exec --json "Explain the architecture of ~/github/AutoSWE"
```

## Source

All documentation sourced from [developers.openai.com/codex](https://developers.openai.com/codex) and [github.com/openai/codex](https://github.com/openai/codex).
