# Subagents

Codex spawns specialized agents in parallel and collects their results. Enabled by default.

## How It Works

```
User asks for subagents
    ↓
Codex spawns N agents (parallel)
    ├── Agent 1: task A
    ├── Agent 2: task B
    └── Agent 3: task C
    ↓
All complete → consolidated response
```

**Codex only spawns subagents when you explicitly ask.** Each subagent consumes its own model + tool tokens.

## Built-in Agents

| Agent | Purpose |
|---|---|
| `default` | General-purpose fallback |
| `worker` | Implementation and fixes |
| `explorer` | Read-heavy codebase exploration |

## Custom Agents

### Create a Custom Agent

Add TOML files under `~/.codex/agents/` (personal) or `.codex/agents/` (project):

```toml
# .codex/agents/reviewer.toml

name = "reviewer"
description = "PR reviewer focused on correctness, security, and missing tests."
developer_instructions = """
Review code like an owner.
Prioritize correctness, security, behavior regressions, and missing test coverage.
Lead with concrete findings, include reproduction steps when possible.
"""
model = "gpt-5.4"
model_reasoning_effort = "high"
sandbox_mode = "read-only"
nickname_candidates = ["Atlas", "Delta", "Echo"]
```

### Required Fields

| Field | Type | Purpose |
|---|---|---|
| `name` | string | Agent identifier |
| `description` | string | When Codex should use this agent |
| `developer_instructions` | string | Core behavior instructions |

### Optional Fields

| Field | Type | Purpose |
|---|---|---|
| `nickname_candidates` | string[] | Display names for spawned instances |
| `model` | string | Override model for this agent |
| `model_reasoning_effort` | string | `low` / `medium` / `high` |
| `sandbox_mode` | string | Sandbox for this agent |
| `mcp_servers` | table | MCP server config |
| `skills.config` | array | Skill overrides |

Custom agents with names matching built-in agents (`explorer`, `worker`, `default`) **override** the built-in.

## Global Subagent Settings

```toml
[agents]
max_threads = 6              # Concurrent threads (default: 6)
max_depth = 1                # Nesting depth (default: 1)
job_max_runtime_seconds = 1800  # Per-worker timeout
```

**Warning:** Raising `max_depth` can turn broad delegation into repeated fan-out. Use `max_threads` to cap concurrent threads.

## Using Subagents

### Prompt Example

```
Review this branch against main. Spawn one agent per point and summarize:
1. Security issues
2. Code quality
3. Bugs
4. Race conditions
5. Test flakiness
6. Maintainability
```

### CLI Control

```
/agent          # Switch between active agent threads
/ps             # Check background terminals
/stop           # Stop all background terminals
```

## CSV Fan-Out Jobs

Use `spawn_agents_on_csv` for batch parallel work:

```
Create /tmp/components.csv with columns path,owner (one row per component).

Then call spawn_agents_on_csv with:
- csv_path: /tmp/components.csv
- id_column: path
- instruction: "Review {path} owned by {owner}. Return JSON with keys path, risk, summary, follow_up."
- output_csv_path: /tmp/components-review.csv
- output_schema: { path: string, risk: string, summary: string, follow_up: string }
```

## Multi-Agent Patterns

### PR Review (3 agents)

| Agent | Role | Model |
|---|---|---|
| `pr_explorer` | Map codebase, gather evidence | `gpt-5.3-codex-spark` |
| `reviewer` | Find correctness/security risks | `gpt-5.4` |
| `docs_researcher` | Verify framework APIs via MCP | `gpt-5.4-mini` |

### Frontend Debug (3 agents)

| Agent | Role |
|---|---|
| `code_mapper` | Trace failing UI flow in code |
| `browser_debugger` | Reproduce issue, capture evidence |
| `ui_fixer` | Implement smallest fix |

## Inheritance

- Subagents inherit parent's sandbox policy and approval settings
- Parent turn's live overrides (`/permissions`, `--yolo`) apply to children
- Individual agents can override sandbox (e.g., `sandbox_mode = "read-only"`)

## See Also

- [Configuration](./configuration.md)
- [Skills](./skills.md)
- [Prompting](./prompting.md)
