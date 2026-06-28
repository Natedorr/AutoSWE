# Sandbox, Approvals & Security

## Two-Layer Security Model

| Layer | What It Controls |
|---|---|
| **Sandbox mode** | What Codex can *technically* do (filesystem, network) |
| **Approval policy** | When Codex must *ask you* before acting |

## Sandbox Modes

| Mode | Description |
|---|---|
| `workspace-write` (default) | Read/edit/run commands in workspace. Network off by default. |
| `read-only` | Browse files only. Must approve edits and commands. |
| `danger-full-access` (`--yolo`) | No sandbox, no approvals. **Not recommended.** |

```bash
codex --sandbox workspace-write --ask-for-approval on-request
codex --sandbox read-only --ask-for-approval on-request
codex --sandbox danger-full-access  # DANGER
```

## Approval Policies

| Policy | Behavior |
|---|---|
| `on-request` | Ask before sandbox escapes, network, untrusted commands |
| `untrusted` | Auto-edit files, but ask before running untrusted commands |
| `never` | No prompts. Works with all sandbox modes. |
| `granular` | Per-category control (see below) |

### Granular Policy

```toml
approval_policy = { granular = {
  sandbox_approval = true,
  rules = true,
  mcp_elicitations = true,
  request_permissions = false,
  skill_approval = false
} }
```

## Automatic Approval Review

```toml
approval_policy = "on-request"
approvals_reviewer = "auto_review"
```

Routes eligible approvals through a reviewer agent that checks for:
- Data exfiltration
- Credential probing
- Persistent security weakening
- Destructive actions

Risk levels: `low` (auto-allow) → `medium` (auto-allow) → `high` (requires authorization) → `critical` (denied)

## Network Access

### Basic Toggle

```toml
[sandbox_workspace_write]
network_access = true
```

### Network Proxy (Domain Allowlist)

```toml
[features.network_proxy]
enabled = true
domains = { "api.openai.com" = "allow", "example.com" = "deny" }
```

Domain rules:
- Exact hosts match only themselves
- `*.example.com` matches subdomains, not the apex
- `**.example.com` matches both apex and subdomains
- Global `*` allows any public host (treat with caution)
- `deny` always wins over `allow`

### Local/Private Destinations

By default, `allow_local_binding = false` blocks loopback, link-local, and private IPs. Add explicit allow rules or set `allow_local_binding = true` to override.

## Shell Command Rules

Rules live in `.rules` files under `rules/` alongside config layers.

```starlark
# ~/.codex/rules/default.rules

prefix_rule(
  pattern = ["gh", "pr", "view"],
  decision = "prompt",
  justification = "Viewing PRs is allowed with approval",
  match = [
    "gh pr view 7888",
    "gh pr view --repo openai/codex",
  ],
  not_match = [
    "gh pr --repo openai/codex view 7888",
  ],
)
```

### Decisions

| Decision | Behavior |
|---|---|
| `allow` | Run outside sandbox without prompting |
| `prompt` | Prompt before each invocation |
| `forbidden` | Block without prompting |

When multiple rules match, the **most restrictive** decision wins.

### Testing Rules

```bash
codex execpolicy check --pretty \
  --rules ~/.codex/rules/default.rules \
  -- gh pr view 7888 --json title,body,comments
```

## Web Search Control

```toml
web_search = "cached"   # default — pre-indexed results
web_search = "live"     # real-time fetch (--search flag)
web_search = "disabled" # turn off
```

## Common Combinations

| Intent | Flags |
|---|---|
| Auto (preset) | `--sandbox workspace-write --ask-for-approval on-request` |
| Safe read-only | `--sandbox read-only --ask-for-approval on-request` |
| CI read-only | `--sandbox read-only --ask-for-approval never` |
| Edit + untrusted prompt | `--sandbox workspace-write --ask-for-approval untrusted` |
| Auto-review | `--sandbox workspace-write --ask-for-approval on-request -c approvals_reviewer=auto_review` |
| Full access | `--dangerously-bypass-approvals-and-sandbox` |

## Testing Locally

```bash
# macOS
codex sandbox macos [--permissions-profile <name>] [COMMAND...]

# Linux
codex sandbox linux [--permissions-profile <name>] [COMMAND...]

# Windows (WSL2)
codex sandbox windows [--permissions-profile <name>] [COMMAND...]
```

## Platform-Specific Sandbox

| OS | Mechanism |
|---|---|
| macOS | Seatbelt (`sandbox-exec`) |
| Linux | `bwrap` + seccomp |
| Windows (WSL2) | Linux sandbox (bwrap) |
| Windows (native) | Windows Sandbox (unelevated/elevated) |

## Dev Containers

Reference implementation: [openai/codex/.devcontainer](https://github.com/openai/codex/tree/main/.devcontainer)

Use `--sandbox danger-full-access` inside containers where Docker provides the outer isolation boundary.

## See Also

- [Configuration](./configuration.md)
- [Rules](./rules.md)
- [AGENTS.md](./agents-md.md)
