# Configuration

Codex uses TOML configuration files at two levels:

| Scope | Location | Purpose |
|---|---|---|
| **User** | `~/.codex/config.toml` | Global settings, auth, profiles |
| **Project** | `.codex/config.toml` | Repo-scoped overrides (trusted projects only) |

Project config **cannot** override provider, auth, notification, profile, or telemetry keys.

## Quick Start

```toml
# ~/.codex/config.toml

# Active model
model = "gpt-5.5"

# Approval policy: "on-request" | "never" | "untrusted"
approval_policy = "on-request"

# Sandbox mode: "workspace-write" | "read-only" | "danger-full-access"
sandbox_mode = "workspace-write"

# Web search: "cached" (default) | "live" | "disabled"
web_search = "cached"
```

## Sandbox & Network

```toml
# Enable network access in workspace-write mode
[sandbox_workspace_write]
network_access = true

# Network proxy (domain allowlist)
[features.network_proxy]
enabled = true
domains = { "api.openai.com" = "allow", "example.com" = "deny" }
```

## Profiles

Save reusable configurations:

```toml
[profiles.full_auto]
approval_policy = "on-request"
sandbox_mode = "workspace-write"

[profiles.readonly_quiet]
approval_policy = "never"
sandbox_mode = "read-only"
```

Select with `codex --profile full_auto`.

## Subagent Settings

```toml
[agents]
max_threads = 6        # Concurrent agent threads (default: 6)
max_depth = 1          # Nesting depth (default: 1)
job_max_runtime_seconds = 1800  # Per-worker timeout
```

## Model Context Protocol (MCP)

```toml
# STDIO server
[mcp_servers.context7]
command = "npx"
args = ["-y", "@upstash/context7-mcp"]
env_vars = ["LOCAL_TOKEN"]

# HTTP server
[mcp_servers.figma]
url = "https://mcp.figma.com/mcp"
bearer_token_env_var = "FIGMA_OAUTH_TOKEN"

# Per-tool approval
[mcp_servers.chrome_devtools]
url = "http://localhost:3000/mcp"
enabled_tools = ["open", "screenshot"]
default_tools_approval_mode = "prompt"

[mcp_servers.chrome_devtools.tools.open]
approval_mode = "approve"
```

### CLI MCP Management

```bash
# Add a server
codex mcp add context7 -- npx -y @upstash/context7-mcp

# List servers
/mcp  # (in TUI)

# Help
codex mcp --help
```

## Skills Configuration

Disable a skill without deleting it:

```toml
[[skills.config]]
path = "/path/to/skill/SKILL.md"
enabled = false
```

## Custom Agents

Define custom agents under `~/.codex/agents/` (global) or `.codex/agents/` (project):

```toml
# ~/.codex/agents/reviewer.toml

name = "reviewer"
description = "PR reviewer focused on correctness, security, and missing tests."
developer_instructions = """
Review code like an owner.
Prioritize correctness, security, behavior regressions, and missing test coverage.
"""
model = "gpt-5.4"
model_reasoning_effort = "high"
sandbox_mode = "read-only"
nickname_candidates = ["Atlas", "Delta", "Echo"]
```

## Project Instructions Discovery

```toml
# Fallback filenames
project_doc_fallback_filenames = ["TEAM_GUIDE.md", ".agents.md"]

# Max combined instruction bytes (default: 32768)
project_doc_max_bytes = 65536
```

## Features (Feature Flags)

```bash
# List available features
codex features list

# Enable/disable
codex features enable unified_exec
codex features disable shell_snapshot
codex features enable goals
```

## Automatic Approval Review

```toml
approval_policy = "on-request"
approvals_reviewer = "auto_review"
```

Routes eligible approval requests through a reviewer agent before execution.

## CLI Shortcuts

Override config with `-c` flags:

```bash
codex \
  -c 'features.network_proxy=true' \
  -c 'sandbox_workspace_write.network_access=true' \
  -c 'model=gpt-5.4' \
  "explain this codebase"
```

## Code Home

```bash
# Use a different config/home directory
CODEX_HOME=$(pwd)/.codex codex exec "List active instruction sources"
```

## See Also

- [AGENTS.md](./agents-md.md)
- [Sandboxing & Security](./sandboxing.md)
- [Skills](./skills.md)
- [Subagents](./subagents.md)
- [MCP](./mcp.md)
