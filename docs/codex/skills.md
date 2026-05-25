# Skills

Skills are task-specific instruction packages that extend Codex with reliable workflows.

## What Are Skills?

A skill is a directory with a `SKILL.md` file plus optional scripts and references:

```
my-skill/
├── SKILL.md              # Required: instructions + metadata
├── scripts/              # Optional: executable code
├── references/           # Optional: documentation
├── assets/               # Optional: templates, resources
└── agents/
    └── openai.yaml       # Optional: UI metadata + dependencies
```

### SKILL.md Format

```yaml
---
name: skill-name
description: Explain exactly when this skill should and should not trigger.
---

Skill instructions for Codex to follow.
```

## Discovery Locations

| Scope | Location | Use |
|---|---|---|
| REPO (CWD) | `$CWD/.agents/skills` | Folder-specific skills |
| REPO (parent) | `$CWD/../.agents/skills` | Shared parent skills |
| REPO (root) | `$REPO_ROOT/.agents/skills` | Repo-wide skills |
| USER | `$HOME/.agents/skills` | Personal skills |
| ADMIN | `/etc/codex/skills` | Machine-wide skills |
| SYSTEM | Bundled with Codex | Built-in skills |

## Invocation

- **Explicit:** Include skill in prompt, or use `/skills` / `$` to mention
- **Implicit:** Codex matches task description against skill descriptions

## Creating Skills

```bash
$skill-creator   # Built-in guided creator
```

Or create manually — just a folder with a `SKILL.md`.

## Installing Skills

```bash
$skill-installer linear   # Example: install Linear skill
```

## Disabling Skills

```toml
# ~/.codex/config.toml
[[skills.config]]
path = "/path/to/skill/SKILL.md"
enabled = false
```

## UI Metadata (agents/openai.yaml)

```yaml
interface:
  display_name: "Display Name"
  short_description: "Short description"
  icon_small: "./assets/small-logo.svg"
  icon_large: "./assets/large-logo.png"
  brand_color: "#3B82F6"
  default_prompt: "Default prompt text"

policy:
  allow_implicit_invocation: false

dependencies:
  tools:
    - type: "mcp"
      value: "openaiDeveloperDocs"
      transport: "streamable_http"
      url: "https://developers.openai.com/mcp"
```

## Best Practices

- Keep each skill focused on **one job**
- Prefer instructions over scripts unless deterministic behavior is needed
- Write imperative steps with explicit inputs and outputs
- Front-load key use cases in descriptions for implicit matching
- Test trigger behavior against skill descriptions

## Plugins vs Skills

- **Skills** — authoring format for reusable workflows
- **Plugins** — installable distribution unit (can bundle multiple skills + MCP servers + app integrations)

## Built-in Skills

- `$skill-creator` — Create new skills
- `$skill-installer` — Install skills from registries
- `$imagegen` — Image generation
- `$plan` — Planning workflows

## See Also

- [Configuration](./configuration.md)
- [Subagents](./subagents.md)
