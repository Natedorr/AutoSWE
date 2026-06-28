# AGENTS.md — Custom Instructions

Codex reads `AGENTS.md` files before doing any work, building an instruction chain.

## Discovery Precedence (highest → lowest)

1. **Global:** `~/.codex/AGENTS.override.md` (or `~/.codex/AGENTS.md` if override doesn't exist)
2. **Project root:** `AGENTS.override.md` → `AGENTS.md` → fallback filenames
3. **Current directory (walk down):** Same pattern per directory

Files closer to your working directory override earlier guidance (they appear later in the combined prompt). Codex stops at `project_doc_max_bytes` (32 KiB default).

## File Priority Per Directory

For each directory in the chain:
```
AGENTS.override.md → AGENTS.md → project_doc_fallback_filenames[...]
```

Codex includes **at most one file per directory**. Override files take precedence over regular ones.

## Example Setup

```
~/.codex/AGENTS.md              # Global defaults (always loaded first)
repo_root/AGENTS.md              # Repository norms
repo_root/services/payments/AGENTS.override.md  # Payments-specific rules
```

### Global (~/.codex/AGENTS.md)

```markdown
# Working Agreements

- Always run `npm test` after modifying JavaScript files.
- Prefer `pnpm` when installing dependencies.
- Ask for confirmation before adding new production dependencies.
```

### Repository Root (AGENTS.md)

```markdown
# Repository Expectations

- Run `npm run lint` before opening a pull request.
- Document public utilities in `docs/` when behavior changes.
```

### Nested Override (services/payments/AGENTS.override.md)

```markdown
# Payments Service Rules

- Use `make test-payments` instead of `npm test`.
- Never rotate API keys without notifying the security channel.
```

## Fallback Filenames

If your repo uses a different instruction filename:

```toml
# ~/.codex/config.toml
project_doc_fallback_filenames = ["TEAM_GUIDE.md", ".agents.md"]
project_doc_max_bytes = 65536
```

## Protected Paths

In the default `workspace-write` sandbox:
- `/.git` — read-only
- `/.agents` — read-only (if it exists as directory)
- `/.codex` — read-only (if it exists as directory)

## Hierarchical AGENTS.md

With the `child_agents_md` feature flag:

```toml
[features]
child_agents_md = true
```

Codex appends scope/precedence guidance to the user instructions message.

## Tips

- Use `/init` to generate an `AGENTS.md` scaffold in the current directory
- Restart Codex to pick up file changes
- Check `~/.codex/log/codex-tui.log` to audit loaded instruction files
- Empty files are skipped

## See Also

- [Configuration](./configuration.md)
- [Prompting](./prompting.md)
