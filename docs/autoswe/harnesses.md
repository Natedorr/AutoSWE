# Harness Configuration

## `config/harnesses.json` (gitignored, copy from `harnesses.json.example`)

Loaded by `core/config.py:load_harnesses_config()`. Keys starting with `_` are skipped.

A **harness profile** bundles a coding backend (`claude_code`, `codex`) with its model and any auth/runtime settings. Phases (`plan`, `fix`, `review`) reference a profile by name via `plan_harness`, `fix_harness`, or `review_harness` in `repos.json` (or `PLAN_HARNESS`, `FIX_HARNESS`, `REVIEW_HARNESS` in `autoswe.env`).

### Profile Schema

| Field | Required | Default | Description |
|-------|----------|---------|-----------|
| `backend` | **Yes** | — | Backend implementation: `"claude_code"` or `"codex"` |
| `model` | No for `claude_code`, **required** for `codex` | `""` | Model ID (e.g. `"claude-opus-4-8"`, `"gpt-5.6-terra"`). No default for `codex` — resolution fails if missing |
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
  "codex-gpt56-terra": {
    "backend": "codex",
    "model": "gpt-5.6-terra",
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
    "fix_harness": "codex-gpt56-terra",
    "review_harness": "claude-sonnet"
  }
}
```

Or globally in `autoswe.env`:
```
PLAN_HARNESS=claude-opus
FIX_HARNESS=codex-gpt56-terra
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
    "fix_harness": "codex-gpt56-terra",
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

**System prompt:** runs with the `claude_code` system-prompt preset
(`system_prompt={"type": "preset", "preset": "claude_code"}`), set in
`ClaudeCodeBackend`'s `options_kwargs` for every run. Without it the Agent SDK
falls back to a minimal prompt that covers tool calling but omits the preset's
tool-usage guidance, security/safety instructions, and working-directory /
environment context — all of which the plan/fix/review workflow implicitly
assumes. The **bare** preset is intentionally used (no `append`, no
`exclude_dynamic_sections`). Cache note: the preset embeds per-worktree context
(cwd, git status, platform) in the system prompt, so each fresh per-issue
worktree misses the prompt-cache prefix. Setting
`exclude_dynamic_sections: True` would make the system prompt static and let
consecutive issues share the cache prefix, at the cost of moving that context
into the first user message (marginally less authoritative). That lever is
deferred to a follow-up and is not enabled here.

#### `codex` (Phase 4)

Shells out to `codex exec --json`. Maps `RunSpec` to Codex flags (`--sandbox`, `--model`, `-C`, `--dangerously-bypass-approvals-and-sandbox`). Parses the JSONL event stream into a `RunResult`.

**Item/event types parsed** (issue #118): the current CLI emits `thread.started`, `turn.started`/`completed`/`failed`, and `item.*`/`turn.plan.updated` events. Item types handled: `agent_message`/`agentMessage` (primary `RunResult.text` source), `plan` (authoritative text → `RunResult.plan_text`), `reasoning`, `command_execution`, `file_change`, `mcp_tool_call`, `web_search` (progress only). `turn.plan.updated` and plan/reasoning deltas render as live progress. The parser normalizes names defensively so both snake_case and camelCase item types, and both dot/slash event spellings, are accepted regardless of CLI version. The legacy `todo_list`/`summary_output` items and the `item.delta`/`item.updated` events no longer exist in the current CLI and are no longer emitted.

**Requirements:** `codex` CLI on PATH (`npm i -g @openai/codex`). API key via `codex_api_key`, `openai_api_key`, or environment variable. For local providers (Ollama), configure via `~/.codex/config.toml` — no API key needed.

**Profile fields:**
- `backend`: `"codex"` (required)
- `model`: **required** Codex model ID (e.g. `"gpt-5.6-sol"`, `"gpt-5.6-terra"`, `"gpt-5.6-luna"`, `"gpt-5.5"`, `"qwen3.6:27b"` for Ollama). There is no built-in default — a missing `model` fails resolution with a `ValueError`
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
- **No system-prompt knob (asymmetry with `claude_code`):** Codex always uses its built-in system prompt; there is no equivalent of Claude Code's `claude_code` preset to select. The nearest levers (`AGENTS.md`, rules) are intentionally disabled via `--ignore-rules` / `--ignore-user-config` for reproducibility, so autoSWE cannot steer the Codex system prompt the way it can for Claude.
- ``cost_usd`` is an **estimate** from a maintained price table (`codex_pricing.py`). Returns ``None`` for unknown models — never guesses.
- ``plan_file_path`` is always ``None`` — Codex doesn't write to `~/.claude/plans/`.
- ``plan_posted`` / ``question_posted`` are always ``False`` — no MCP comment posting yet.
- Duration is tracked via ``time.monotonic()`` locally.

### Factory

Backend instances are created by `autoswe/harness/backends/factory.py:get_backend(harness_cfg)`. Dispatch on `harness_cfg["backend"]` field. Mirrors the provider factory pattern (`providers/factory.py`).

Unknown backend names raise `ValueError`. A `codex` profile without `model` also raises `ValueError` (no default model). Case-insensitive matching.

### Backward Compatibility

With **no** `harnesses.json` and **no** `{phase}_harness` keys, a full plan→fix→review cycle is byte-for-byte equivalent to the legacy path. `resolve_harness()` synthesizes `{"backend": "claude_code", "model": <existing_model>}` so the `PLAN_MODEL`/`FIX_MODEL`/`REVIEW_MODEL` resolution chain keeps working.
