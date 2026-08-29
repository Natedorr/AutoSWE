# Codex CLI Documentation

Comprehensive documentation for OpenAI's Codex CLI — a local coding agent.

> **Note:** Codex does **not** have a Python SDK. It is a Rust-based CLI/IDE tool. Programmatic integration points are `codex exec` (non-interactive mode), MCP servers, and the subagent system.

> **Site move:** The Codex docs moved from `developers.openai.com/codex` to **`learn.chatgpt.com/docs`** (old URLs redirect). This mirror was re-fetched from the new site on 2026-07-19 via `scripts/fetch_codex_docs.py`. The `raw/`, `integrations/` folders and some top-level files from the old structure are now superseded (see `whats-new.md` and the new sub-paths below).

## Table of Contents

| Document | Description |
|---|---|
| [Quickstart](./quickstart.md) | Install + first run across surfaces |
| [Codex CLI](./codex/cli.md) | Terminal usage, `codex exec` |
| [Codex IDE](./codex/ide.md) | IDE extension |
| [Codex cloud](./cloud.md) | Cloud environments, delegate work |
| [Codex SDK](./codex-sdk.md) | App Server / programmatic control |
| [Authentication](./auth.md) | Sign-in methods |
| [Configuration](./configuration.md) | config.toml reference — sandbox, MCP, profiles, agents |
| [Config file details](./config-file/config-reference.md) | Full config reference + sample |
| [AGENTS.md](./agent-configuration/agents-md.md) | Custom instructions, discovery, overrides |
| [Sandboxing & Security](./sandboxing.md) | Sandbox modes, approvals, network, protected paths |
| [Agent approvals & security](./agent-approvals-security.md) | Secure operation guide |
| [Security](./security.md) | Security docs landing (+ `security/` sub-pages) |
| [Rules](./agent-configuration/rules.md) | Command execution policy (prefix rules) |
| [Permission modes](./permission-modes.md) | Permission mode reference |
| [Slash / developer commands](./developer-commands-cli.md) | CLI command reference (+ flags in `reference/commands.md`) |
| [Subagents](./agent-configuration/subagents.md) | Parallel agents, custom agents |
| [Skills](./build-skills.md) | Task-specific instruction packages |
| [MCP](./extend/mcp.md) | Model Context Protocol — STDIO/HTTP servers |
| [Prompting](./prompting.md) | Prompt tips, context management |
| [Long-running work](./long-running-work.md) | Extended runs |
| [Models](./models.md) | Model reference |
| [Hooks](./hooks.md) | Hooks |
| [Memories](./customization/memories.md) | Memory/customization |
| [What's new](./whats-new.md) | Release notes |
| [Codex manual (condensed)](./codex-manual.md) | Single-file machine-oriented manual (~39k lines) |

Third-party integrations now live under `third-party/` (github, gitlab, linear, slack).

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

All documentation sourced from [learn.chatgpt.com/docs](https://learn.chatgpt.com/docs) (Codex docs index: [llms.txt](https://learn.chatgpt.com/docs/llms.txt)) and [github.com/openai/codex](https://github.com/openai/codex). Refresh with `python scripts/fetch_codex_docs.py`.
