# Harness Configuration

## `config/harnesses.json` (gitignored, copy from `harnesses.json.example`)

Loaded by `core/config.py:load_harnesses_config()`. Keys starting with `_` are skipped.

A **harness profile** bundles a coding backend (`claude_code`, `codex`) with its model and any auth/runtime settings. Phases (`plan`, `fix`, `review`) reference a profile by name via `plan_harness`, `fix_harness`, or `review_harness` in `repos.json` (or `PLAN_HARNESS`, `FIX_HARNESS`, `REVIEW_HARNESS` in `autoswe.env`).

### Profile Schema

| Field | Required | Default | Description |
|-------|----------|---------|-----------|
| `backend` | **Yes** | — | Backend implementation: `"claude_code"` or `"codex"` |
| `model` | No for `claude_code`, **required** for `codex` | `""` | Model ID (e.g. `"claude-opus-5"`, `"gpt-5.6-terra"`). No default for `codex` — resolution fails if missing |
| `timeout` | No | (from env) | Backend-specific timeout in seconds |
| `cli_path` | No | (from env) | Path to the CLI binary (e.g. `claude` or `codex`) |
| `codex_api_key` | No | — | API key for Codex backend (sets `CODEX_API_KEY` env var) |
| `openai_api_key` | No | — | Alternative API key for Codex backend (sets `OPENAI_API_KEY` env var) |
| `anthropic_base_url` | No | (from env) | Custom API endpoint (Claude Code only) |
| `anthropic_auth_token` | No | (from env) | Auth token (Claude Code only) |
| `anthropic_api_key` | No | (from env) | API key (Claude Code only) |
| `env` | No | — | Extra environment variables (a `{key: value}` map) merged into the backend's child process. Values override backend defaults; ``${VAR}``/``${VAR:-default}`` supported. See [Per-profile `env`](#per-profile-env) |

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
    "model": "claude-opus-5"
  },
  "claude-sonnet": {
    "backend": "claude_code",
    "model": "claude-sonnet-5"
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

### Per-profile `env`

Every profile accepts an optional `env` map of extra environment variables,
merged into the backend's child process. This is the hook for passing values
that the backend itself does not model as named fields (e.g. pointing Codex at
a self-hosted OpenAI-compatible endpoint via `OPENAI_API_BASE`).

- **Claude Code** — merged into the SDK `env` option, so the variables reach the
  spawned CLI only (never the poller's own process environment).
- **Codex** — merged into the `codex exec` subprocess environment.

**Precedence** (highest wins):

| Claude Code | Codex |
|-------------|-------|
| 1. `spec.env_overrides` (internal) | 1. `spec.env_overrides` (internal) |
| 2. profile `env` | 2. profile `env` |
| 3. backend defaults (e.g. `CLAUDE_CODE_ENABLE_TODO_TOOLS=1`, Anthropic creds) | 3. api-key fields (`OPENAI_API_KEY` / `CODEX_API_KEY`) |
| 4. inherited `os.environ` | 4. inherited `os.environ` |

So a profile `env` value overrides a backend default but loses to the internal
`env_overrides` seam. `${VAR}` / `${VAR:-default}` expansion is applied to `env`
values at load time, like every other profile string.

```json
{
  "claude-custom": {
    "backend": "claude_code",
    "model": "claude-opus-4-8",
    "env": { "CLAUDE_CODE_ENABLE_TODO_TOOLS": "1" }
  },
  "codex-custom": {
    "backend": "codex",
    "model": "custom-model",
    "env": { "OPENAI_API_BASE": "http://localhost:8080" }
  }
}
```

#### `claude_code` (current default)

Runs the Claude Agent SDK. Supports all capabilities: MCP servers, AskUserQuestion interception, plan file capture, progress streaming, session resume.

**Profile fields:** `backend`, `model`, `cli_path`, `anthropic_base_url`, `anthropic_auth_token`, `anthropic_api_key`, `timeout`, `env`.

**Task-tracking tools (default opt-in):** the backend sets
`CLAUDE_CODE_ENABLE_TODO_TOOLS=1` on the spawned CLI by default (via the SDK
`env` option). On Agent SDK ≥ 0.2.139 the task-tracking tools
(`TodoWrite`, `TaskCreate`, `TaskGet`, `TaskUpdate`, `TaskList`) are *not*
provided by default on the newer model families (Opus 4.8, Sonnet 5, …); this
opt-in restores them (honored when the CLI is ≥ v2.1.233). They are the
planner/coder's only live feedback — the sticky progress comment renders from
them. The tools also remain listed in the backend's tool lists as
belt-and-braces. A profile `env` entry can override the default (e.g.
`"env": {"CLAUDE_CODE_ENABLE_TODO_TOOLS": "0"}` to disable).

**Capabilities:** `mode`, `mcp`, `can_use_tool`, `plan_permission`, `resume`, `session_fork`, `progress_stream`, `plan_file`.

**Retryable subtypes:** `set()` — Claude Code retries on SDK exceptions (`_get_retryable_exceptions`), not return-value subtypes.

<a id="retry-semantics"></a>
**Retry semantics (fork-on-retry).** The Claude Agent SDK supports
`fork_session` / `resume_session_at` — a `/retry` can *branch* from the last
known-good session into a new session, leaving the original intact so a failed
retry can roll back to it. autoSWE maps the uniform `RunSpec.fork_session` flag
to this:

- **Checkpoint.** `emit()` records the run's `session_id` into the queue's
  `last_good_session_id` on every **non-failed** run that persists a session,
  **and** `last_good_session_backend` with the backend that produced it
  (the resolved phase harness's `backend`, e.g. `claude_code` / `codex`).
  Unlike `session_id`, it is **never cleared on `FAILED`** (the `FAILED` path
  nulls `session_id` so we don't resume a broken session). So the most recent
  good session — and which backend made it — always survives a failure.
- **Fork.** `_run_retry` replays the last substantive command. For a `/fix`
  replay it sets `fork_session=True` **iff** all three hold: the fix backend
  advertises `"session_fork"`, a checkpoint exists (`last_good_session_id` or
  `session_id`), and the checkpoint's recorded backend
  (`last_good_session_backend`) **matches the fix backend**. The last condition
  is the provenance gate: in a mixed per-phase config (e.g. Codex
  `plan_harness` + Claude `fix_harness`) a Codex plan's session id would
  otherwise be handed to the Claude SDK, which cannot resolve a foreign-backend
  session — so a mismatch (or a missing tag) falls back to a fresh session.
  `coder.run_fix` then resumes from `last_good_session_id` (not `session_id`,
  which is `None` after a failure) with `fork_session=True`, so the SDK opens
  a **new** session whose id becomes the new `session_id` while the original
  checkpoint stays resumable. With no usable checkpoint yet (first-ever
  failure) there is nothing to fork from → a fresh session.
- **Auto-restore.** Because the fork never mutates the original and a failed
  forked retry leaves `last_good_session_id` untouched, a repeated `/retry`
  keeps forking from the same good checkpoint until one succeeds — rollback is
  automatic and zero-effort.
- **SDK floor.** `fork_session` requires Agent SDK ≥ 0.2.137. The backend reads
  the installed distribution version and, on an older SDK, logs a warning and
  degrades to a plain in-place `resume` instead of passing an unknown option.
  The capability is still advertised; the guard is the runtime safety net.
- **Follow-up (out of scope here).** `resume_session_at` branches from an
  *earlier message*, not the whole session. That needs per-message
  "known-good" bookkeeping the queue schema does not track yet, so only
  fork-from-whole-session is wired now; the `"session_fork"` capability covers
  both.

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

**Repo content loading (MCP / hooks / skills).** The backend passes autoSWE's injected `mcp_servers` (the comment servers built by `autoswe/harness/mcp_config.py`) to `ClaudeAgentOptions` but leaves `strict_mcp_config` and `setting_sources` at their SDK defaults (`False` / all sources). The practical effect: inside a target repo's worktree, the SDK **also loads** the repo's `.mcp.json` servers, `.claude/settings.json` hooks, and `.claude/` skills/agents/commands — alongside autoSWE's own servers. This is by design (autoSWE runs on a dedicated, isolated machine; see [safeguards.md](safeguards.md#repo-supplied-mcp-servers-hooks-skills-and-tools-load-by-design)). autoSWE's injected servers are programmatic and therefore highest-precedence — a repo cannot shadow `autoswe_comment` / `autoswe_inline_comment`. No per-repo opt-out is currently exposed; if ever needed it would be `strict_mcp_config=True` + `setting_sources` without `"project"`.

#### `codex` (Phase 4)

Shells out to `codex exec --json`. Maps `RunSpec` to Codex flags (`--sandbox`, `--model`, `-C`, `--dangerously-bypass-approvals-and-sandbox`, `--output-last-message`). Parses the JSONL event stream into a `RunResult`, sourcing `RunResult.text` from the assistant's final message written via `--output-last-message` (falling back to the accumulated JSONL `agent_message` chunks when the file is absent or empty).

**Item/event types parsed** (issue #118): the current CLI emits `thread.started`, `turn.started`/`completed`/`failed`, and `item.*`/`turn.plan.updated` events. Item types handled: `agent_message`/`agentMessage` (primary `RunResult.text` source), `plan` (authoritative text → `RunResult.plan_text`), `reasoning`, `command_execution`, `file_change`, `mcp_tool_call`, `web_search` (progress only). `turn.plan.updated` and plan/reasoning deltas render as live progress. The parser normalizes names defensively so both snake_case and camelCase item types, and both dot/slash event spellings, are accepted regardless of CLI version. The legacy `todo_list`/`summary_output` items and the `item.delta`/`item.updated` events no longer exist in the current CLI and are no longer emitted.

**Requirements:** `codex` CLI on PATH (`npm i -g @openai/codex`). API key via `codex_api_key`, `openai_api_key`, or environment variable. For local providers (Ollama), configure via `~/.codex/config.toml` — no API key needed.

**Profile fields:**
- `backend`: `"codex"` (required)
- `model`: **required** Codex model ID (e.g. `"gpt-5.6-sol"`, `"gpt-5.6-terra"`, `"gpt-5.6-luna"`, `"gpt-5.5"`, `"qwen3.6:27b"` for Ollama). There is no built-in default — a missing `model` fails resolution with a `ValueError`
- `codex_api_key` or `openai_api_key`: API key for the provider (optional for local providers)
- `timeout`: Override the default timeout (optional)
- `env`: Extra environment variables (a `{key: value}` map) merged into the `codex exec` subprocess (optional). User values win over the api-key fields; see [Per-profile `env`](#per-profile-env)

**Capabilities (Phase 4, core run only):** `mode`, `resume`, `progress_stream`.

**Capabilities (not yet supported):** `mcp` (no MCP comment posting), `can_use_tool` (no per-tool gating), `plan_permission` (no dedicated plan mode), `session_fork` (no fork primitive). Handlers degrade gracefully when these are unavailable — e.g. the planner falls back to text parsing instead of MCP plan posting.

**Retry semantics (resume-in-place or fresh — no fork).** `codex exec resume
<id>` *continues* the existing session in place; Codex has no fork primitive
(analogous to the Claude SDK's `fork_session`). So a Codex `/retry` either
resumes the same session (mutating it) or starts a fresh one — it cannot
branch from a checkpoint while leaving the original intact. The backend does
not advertise `"session_fork"`, so `_run_retry`'s capability gate leaves
`fork_session` off and `RunSpec.fork_session` is ignored. See
[harnesses.md#retry-semantics](#retry-semantics) for the Claude fork-on-retry
contrast.

**Retryable subtypes:** `{"error", "killed"}` — Codex failure is return-value-driven (non-zero exit or `turn.failed`), not exception-driven. The runner inspects `RunResult.subtype` and retries when `AGENT_RETRY_ON_FAILURE > 0`. Override with `AGENT_RETRY_ON_SUBTYPE`.

**Mode → sandbox mapping:**
- `plan` / `read_only` → `--sandbox read-only`
- `read_write` → `--sandbox workspace-write`

**Command mapping:**
- Fresh run: `codex exec --json --sandbox <mode> --model <model> -C <cwd> --output-last-message <tmp> -- <prompt>` (session persisted)
- Resume: `codex exec resume <session_id> --json --model <model> --output-last-message <tmp>` (subprocess cwd set to worktree, as `-C` is unsupported by `codex exec resume`)

**Final-message capture (`--output-last-message`, issue #128).** Each run allocates a private temp file (`mkstemp`) and passes it as `--output-last-message`, which Codex writes the assistant's final message to. After the subprocess exits, that file is read back as the authoritative `RunResult.text` — more robust than assembling `agent_message` chunks from the JSONL stream, which is fragile across item-type renames. If the file is absent or whitespace-only (older CLI, a run that failed or was killed before emitting a final message), the backend falls back to the accumulated chunks, preserving the original behavior. The temp file is always cleaned up (including the timeout/kill path).

**Known limitations:**
- ``RunSpec.max_turns`` is **not honored** — Codex `exec` exposes no turn cap (the old `agent.max_turns` config key was removed; live-verified on codex-cli 0.150.1, where `-c agent.max_turns=N` is rejected under `--strict-config` and silently ignored otherwise). The effective anti-runaway guard is the wall-clock timeout (`timeout` profile field / `AGENT_TIMEOUT`).
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
