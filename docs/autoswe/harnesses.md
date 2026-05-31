# Harness Configuration

## `config/harnesses.json` (gitignored, copy from `harnesses.json.example`)

Loaded by `core/config.py:load_harnesses_config()`. Keys starting with `_` are skipped.

A **harness profile** bundles a coding backend (`claude_code`, `codex`) with its model and any auth/runtime settings. Phases (`plan`, `fix`, `review`) reference a profile by name via `plan_harness`, `fix_harness`, or `review_harness` in `repos.json` (or `PLAN_HARNESS`, `FIX_HARNESS`, `REVIEW_HARNESS` in `autoswe.env`).

### Profile Schema

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `backend` | **Yes** | — | Backend implementation: `"claude_code"` or `"codex"` |
| `model` | No | `""` | Model ID (e.g. `"claude-opus-4-8"`, `"gpt-5"`) |
| `timeout` | No | (from env) | Backend-specific timeout in seconds |
| `cli_path` | No | (from env) | Path to the CLI binary (e.g. `claude` or `codex`) |
| `codex_api_key` | No | — | API key for Codex backend (sets `CODEX_API_KEY` env var) |
| `openai_api_key` | No | — | Alternative API key for Codex backend (sets `OPENAI_API_KEY` env var) |
| `anthropic_base_url` | No | (from env) | Custom API endpoint (Claude Code only) |
| `anthropic_auth_token` | No | (from env) | Auth token (Claude Code only) |
| `anthropic_api_key` | No | (from env) | API key (Claude Code only) |

### Resolution Order

For each phase, the harness profile is resolved in this order:

1. **Repo-specific harness**: `repos.json` entry field `{phase}_harness` (e.g. `plan_harness`)
2. **Global harness**: `autoswe.env` key `{PHASE}_HARNESS` (e.g. `PLAN_HARNESS`)
3. **Synthesized default**: `{"backend": "claude_code", "model": <legacy_model>}` — falls back to the existing `{phase}_model` / `{PHASE}_MODEL` resolution so legacy configurations work without `harnesses.json`

Code path: `config.py:resolve_harness()`.

### Example

```json
{
  "claude-opus": {
    "backend": "claude_code",
    "model": "claude-opus-4-8"
  },
  "claude-sonnet": {
    "backend": "claude_code",
    "model": "claude-sonnet-4-6"
  },
  "codex-gpt5": {
    "backend": "codex",
    "model": "gpt-5",
    "codex_api_key": "${CODEX_API_KEY}"
  }
}
```

Referenced in `repos.json`:
```json
{
  "owner/repo": {
    "provider": "github",
    "pat": "ghp_...",
    "plan_harness": "claude-opus",
    "fix_harness": "claude-sonnet",
    "review_harness": "claude-sonnet"
  }
}
```

Or globally in `autoswe.env`:
```
PLAN_HARNESS=claude-opus
FIX_HARNESS=claude-sonnet
```

### Backends

#### `claude_code` (current default)

Runs the Claude Agent SDK. Supports all capabilities: MCP servers, AskUserQuestion interception, plan file capture, progress streaming, session resume.

#### `codex` (Phase 4)

Shells out to `codex exec --json`. Maps `RunSpec` to Codex flags (`--sandbox`, `--model`, `--cd`, `--ask-for-approval`). Parses the JSONL event stream into a `RunResult`. Initially supports `resume` and `progress_stream` capabilities only (no MCP, no AskUserQuestion — degrades to text parsing).

### Factory

Backend instances are created by `autoswe/harness/backends/factory.py:get_backend(harness_cfg)`. Dispatch on `harness_cfg["backend"]` field. Mirrors the provider factory pattern (`providers/factory.py`).

### Backward Compatibility

With **no** `harnesses.json` and **no** `{phase}_harness` keys, a full plan→fix→review cycle is byte-for-byte equivalent to the legacy path. `resolve_harness()` synthesizes `{"backend": "claude_code", "model": <existing_model>}` so the `PLAN_MODEL`/`FIX_MODEL`/`REVIEW_MODEL` resolution chain keeps working.
