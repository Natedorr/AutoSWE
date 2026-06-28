# Harness Configuration

## `config/harnesses.json` (gitignored, copy from `harnesses.json.example`)

Loaded by `core/config.py:load_harnesses_config()`. Keys starting with `_` are skipped.

A **harness profile** bundles a coding backend (`claude_code`, `codex`) with its model and any auth/runtime settings. Phases (`plan`, `fix`, `review`) reference a profile by name via `plan_harness`, `fix_harness`, or `review_harness` in `repos.json` (or `PLAN_HARNESS`, `FIX_HARNESS`, `REVIEW_HARNESS` in `autoswe.env`).

### Profile Schema

| Field | Required | Default | Description |
|-------|----------|---------|-----------|
| `backend` | **Yes** | — | Backend implementation: `"claude_code"` or `"codex"` |
| `model` | No | `""` | Model ID (e.g. `"claude-opus-4-8"`, `"gpt-5"`) |
| `timeout` | No | (from env) | Backend-specific timeout in seconds |
| `cli_path` | No | (from env) | Path to the CLI binary (e.g. `claude` or `codex`) |
| `codex_api_key` | No | — | API key for Codex backend (sets `CODEX_API_KEY` env var) |
| `openai_api_key` | No | — | Alternative API key for Codex backend (sets `OPENAI_API_KEY` env var) |
| `anthropic_base_url` | No | (from env) | Custom API endpoint (Claude Code only) |
| `anthropic_auth_token` | No | (from env) | Auth token (Claude Code only) |
| `anthropic_api_key` | No | (from env) | API key (Claude Code only) |

String values support ``${VAR}`` and ``${VAR:-default}`` environment variable
interpolation (expanded at load time from the current process environment).

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
    "fix_harness": "codex-gpt5",
    "review_harness": "claude-sonnet"
  }
}
```

Or globally in `autoswe.env`:
```
PLAN_HARNESS=claude-opus
FIX_HARNESS=codex-gpt5
```

### Mixing Backends

Different phases can use different backends. Common patterns:

- **Claude for plan, Codex for fix**: Claude's deeper reasoning for architecture, Codex for execution speed.
- **Codex for plan+fix, Claude for review**: Codex does the work, Claude provides the quality gate.
- **All Claude**: Full feature set (MCP, AskUserQuestion, plan files).
- **All Codex**: No Claude API dependency, but MCP/AskUserQuestion features degrade gracefully.

```json
{
  "owner/repo": {
    "provider": "github",
    "pat": "ghp_...",
    "plan_harness": "codex-4o",
    "fix_harness": "codex-gpt5",
    "review_harness": "claude-sonnet"
  }
}
```

### Backends

#### `claude_code` (current default)

Runs the Claude Agent SDK. Supports all capabilities: MCP servers, AskUserQuestion interception, plan file capture, progress streaming, session resume.

**Profile fields:** `backend`, `model`, `cli_path`, `anthropic_base_url`, `anthropic_auth_token`, `anthropic_api_key`, `timeout`.

**Capabilities:** `mode`, `mcp`, `can_use_tool`, `plan_permission`, `resume`, `progress_stream`.

**Retryable subtypes:** `set()` — Claude Code retries on SDK exceptions (`_get_retryable_exceptions`), not return-value subtypes.

#### `codex` (Phase 4)

Shells out to `codex exec --json`. Maps `RunSpec` to Codex flags (`--sandbox`, `--model`, `--cd`, `--ask-for-approval`). Parses the JSONL event stream into a `RunResult`.

**Requirements:** `codex` CLI on PATH (`npm i -g @openai/codex`). API key via `codex_api_key`, `openai_api_key`, or environment variable. For local providers (Ollama), configure via `~/.codex/config.toml` — no API key needed.

**Profile fields:**
- `backend`: `"codex"` (required)
- `model`: Codex model ID (e.g. `"gpt-5"`, `"gpt-4o"`, `"qwen3.6:27b"` for Ollama)
- `codex_api_key` or `openai_api_key`: API key for the provider (optional for local providers)
- `timeout`: Override the default timeout (optional)

**Capabilities (Phase 4, core run only):** `mode`, `resume`, `progress_stream`.

**Capabilities (not yet supported):** `mcp` (no MCP comment posting), `can_use_tool` (no per-tool gating), `plan_permission` (no dedicated plan mode). Handlers degrade gracefully when these are unavailable — e.g. the planner falls back to text parsing instead of MCP plan posting.

**Retryable subtypes:** `{"error", "killed"}` — Codex failure is return-value-driven (non-zero exit or `turn.failed`), not exception-driven. The runner inspects `RunResult.subtype` and retries when `AGENT_RETRY_ON_FAILURE > 0`. Override with `AGENT_RETRY_ON_SUBTYPE`.

**Mode → sandbox mapping:**
- `plan` / `read_only` → `--sandbox read-only`
- `read_write` → `--sandbox workspace-write`

**Command mapping:**
- Fresh run: `codex exec --json --sandbox <mode> --model <model> -C <cwd> -- <prompt>` (session persisted)
- Resume: `codex exec resume <session_id> --json --model <model>` (subprocess cwd set to worktree, as `-C` is unsupported by `codex exec resume`)

**Known limitations:**
- ``cost_usd`` is an **estimate** from a maintained price table (`codex_pricing.py`). Returns ``None`` for unknown models — never guesses.
- ``plan_file_path`` is always ``None`` — Codex doesn't write to `~/.claude/plans/`.
- ``plan_posted`` / ``question_posted`` are always ``False`` — no MCP comment posting yet.
- Duration is tracked via ``time.monotonic()`` locally.

### Factory

Backend instances are created by `autoswe/harness/backends/factory.py:get_backend(harness_cfg)`. Dispatch on `harness_cfg["backend"]` field. Mirrors the provider factory pattern (`providers/factory.py`).

Unknown backend names raise `ValueError`. Case-insensitive matching.

### Backward Compatibility

With **no** `harnesses.json` and **no** `{phase}_harness` keys, a full plan→fix→review cycle is byte-for-byte equivalent to the legacy path. `resolve_harness()` synthesizes `{"backend": "claude_code", "model": <existing_model>}` so the `PLAN_MODEL`/`FIX_MODEL`/`REVIEW_MODEL` resolution chain keeps working.
