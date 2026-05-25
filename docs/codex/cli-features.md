# CLI Features

## Interactive Mode (TUI)

```bash
codex                          # Interactive session
codex "Explain this codebase"  # With initial prompt
```

### Key Bindings

| Key | Action |
|---|---|
| `Enter` | Submit prompt / inject instructions while running |
| `Tab` | Queue follow-up for next turn |
| `Ctrl+L` | Clear terminal (keep conversation) |
| `Ctrl+O` | Copy latest output |
| `Ctrl+R` | Search prompt history |
| `Ctrl+G` | Open external editor |
| `Esc` (x2) | Edit previous message |
| `Up/Down` | Navigate draft history |

### TUI Features

- Syntax-highlighted code blocks and diffs (`/theme` to change)
- `@` — fuzzy file search to drop paths into prompt
- `!` prefix — run shell commands (e.g., `!ls`)
- Image paste support

### Session Resume

```bash
codex resume           # Pick recent session
codex resume --last    # Jump to most recent
codex resume --all     # Show all sessions
codex resume <id>      # Resume specific session
```

Non-interactive resume:

```bash
codex exec resume --last "Fix the race conditions you found"
codex exec resume <id> "Implement the plan"
```

## Models

```bash
codex --model gpt-5.5
```

Recommended model: `gpt-5.5`. Switch mid-session with `/model`.

### Fast Mode

```
/fast on     # Toggle Fast tier on
/fast off    # Toggle off
/fast status # Check current status
```

## Remote TUI

```bash
# App server
codex app-server --listen ws://127.0.0.1:4500

# Connect from another machine
codex --remote ws://127.0.0.1:4500

# With auth
codex app-server --listen ws://0.0.0.0:4500 \
  --ws-auth capability-token \
  --ws-token-file "$HOME/.codex/app-server-token"
```

## Image Input

```bash
codex -i screenshot.png "Explain this error"
codex --image img1.png,img2.jpg "Summarize these diagrams"
```

## Image Generation

Built-in via `gpt-image-2`. Use `$imagegen` in prompts or ask in natural language.

## Slash Commands

Quick keyboard-first control. Type `/` in the composer to open the popup.

### Essential Commands

| Command | Purpose |
|---|---|
| `/model` | Switch active model |
| `/fast` | Toggle Fast tier |
| `/plan` | Enter plan mode |
| `/goal` | Set persistent task goal |
| `/personality` | Communication style |
| `/permissions` | Sandbox/approval level |
| `/diff` | Show Git diff |
| `/review` | Code review |
| `/compact` | Summarize conversation |
| `/copy` | Copy output (`Ctrl+O`) |
| `/clear` | Clear + new chat |
| `/new` | Fresh conversation (same session) |
| `/agent` | Switch subagent thread |
| `/skills` | Browse available skills |
| `/mcp` | List MCP tools |
| `/status` | Session info + token usage |
| `/ps` | Background terminals |
| `/stop` | Stop background work |
| `/fork` | Fork conversation |
| `/side` | Ephemeral side conversation |
| `/quit` | Exit CLI |
| `/mention` | Attach file to conversation |
| `/approve` | Retry denied action |
| `/hooks` | Review lifecycle hooks |
| `/memories` | Configure memory |
| `/theme` | Syntax highlighting theme |
| `/keymap` | Remap shortcuts |

### Plan Mode

```
/plan                          # Enter plan mode
/plan Propose a migration plan # Inline prompt
```

### Goal Mode

```
/goal Finish migration and keep tests green    # Set goal
/goal                                          # View goal
/goal pause / resume / clear                   # Manage
```

Enable with `features.goals = true` if `/goal` doesn't appear.

### Review

```
/review                              # Default review
/review Focus on accessibility        # Custom instructions
```

Presets:
- Review against base branch
- Review uncommitted changes
- Review a commit
- Custom instructions

## Non-Interactive (exec)

```bash
codex exec "fix the CI failure"
codex exec --json "explain this file"  # JSON output
codex exec --model gpt-5.4 "..."       # Model override
```

## Feature Flags

```bash
codex features list              # Available flags
codex features enable unified_exec
codex features disable shell_snapshot
```

## Cloud Tasks

```bash
codex cloud                       # Interactive picker
codex cloud exec --env ENV_ID "Summarize open bugs"
codex cloud exec --env ENV_ID --attempts 3 "..."
```

## Multi-Root

```bash
codex --cd apps/frontend --add-dir ../backend --add-dir ../shared
```

## Profiles

```bash
codex --profile <name>   # Load saved profile
```

Define profiles in config:

```toml
[profiles.full_auto]
approval_policy = "on-request"
sandbox_mode = "workspace-write"
```

## See Also

- [Slash Commands](./slash-commands.md)
- [Configuration](./configuration.md)
- [Sandboxing](./sandboxing.md)
