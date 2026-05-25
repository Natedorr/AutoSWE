# Model Context Protocol (MCP)

MCP connects Codex to external tools and context — documentation servers, browsers, design tools, etc.

## Transport Types

| Type | Description |
|---|---|
| **STDIO** | Local process started by a command |
| **Streamable HTTP** | Remote server at an address |

Both support bearer token auth. HTTP servers also support OAuth (`codex mcp login`).

## Configuration

CLI and IDE extension share config from `~/.codex/config.toml` or `.codex/config.toml`.

### Via CLI

```bash
# Add STDIO server
codex mcp add context7 -- npx -y @upstash/context7-mcp

# Add with env vars
codex mcp add server-name --env VAR1=VALUE1 -- npx @server/mcp

# List / manage
codex mcp --help
/mcp              # (in TUI)
```

### Via config.toml

#### STDIO Server

```toml
[mcp_servers.context7]
command = "npx"
args = ["-y", "@upstash/context7-mcp"]
env = { MY_VAR = "value" }
env_vars = ["LOCAL_TOKEN", { name = "REMOTE_TOKEN", source = "remote" }]
cwd = "/path/to/project"
startup_timeout_sec = 10
tool_timeout_sec = 60
```

#### HTTP Server

```toml
[mcp_servers.figma]
url = "https://mcp.figma.com/mcp"
bearer_token_env_var = "FIGMA_OAUTH_TOKEN"
http_headers = { "X-Figma-Region" = "us-east-1" }
env_http_headers = { "Authorization" = "AUTH_TOKEN_VAR" }
```

#### Tool Policy

```toml
[mcp_servers.chrome_devtools]
url = "http://localhost:3000/mcp"
enabled_tools = ["open", "screenshot"]       # Allow list
disabled_tools = ["screenshot"]              # Deny list (applied after enabled)
default_tools_approval_mode = "prompt"       # "auto" | "prompt" | "approve"

[mcp_servers.chrome_devtools.tools.open]
approval_mode = "approve"                    # Per-tool override
```

#### Other Options

```toml
[mcp_servers.example]
enabled = true               # false to disable
required = true              # Fail startup if this server won't initialize
startup_timeout_sec = 20
tool_timeout_sec = 45
```

## OAuth

```bash
codex mcp login              # For servers supporting OAuth
```

Config overrides:

```toml
mcp_oauth_callback_port = 5555
mcp_oauth_callback_url = "https://devbox.example.internal/callback"
```

## Plugin MCP Servers

Plugins can bundle MCP servers. User config can still control them:

```toml
[plugins."sample@test".mcp_servers.sample]
enabled = true
default_tools_approval_mode = "prompt"
enabled_tools = ["read", "search"]

[plugins."sample@test".mcp_servers.sample.tools.search]
approval_mode = "approve"
```

## Popular MCP Servers

| Server | Purpose |
|---|---|
| [OpenAI Docs MCP](https://developers.openai.com/learn/docs-mcp) | Search OpenAI developer docs |
| [Context7](https://github.com/upstash/context7) | Up-to-date dev documentation |
| [Figma MCP](https://developers.figma.com/docs/figma-mcp-server/) | Access Figma designs |
| [Playwright MCP](https://www.npmjs.com/package/@playwright/mcp) | Browser control |
| [Chrome DevTools MCP](https://github.com/ChromeDevTools/chrome-devtools-mcp/) | Chrome inspection |
| [Sentry MCP](https://docs.sentry.io/product/sentry-mcp/) | Error logs |
| [GitHub MCP](https://github.com/github/github-mcp-server) | GitHub API (PRs, issues) |

## See Also

- [Configuration](./configuration.md)
- [CLI Features](./cli-features.md)
