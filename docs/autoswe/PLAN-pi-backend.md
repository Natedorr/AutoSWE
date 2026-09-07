# Plan — add `pi` as a first-class coding backend

Goal: `PiBackend` sits behind the existing `CodingBackend` protocol exactly like
`ClaudeCodeBackend` / `CodexBackend` — no handler changes, no new seams. Every
divergence is expressed through `capabilities()`, which the handlers already gate on
(`runner.backend_has_capability`, `runner.has_read_only_enforcement`).

## Host notes (2026-09-06, megibot / Linux)

- pi CLI **0.84.4** installed; `pi` resolves to `/home/megibot/.npm-global/bin/pi`
  (a plain node script, no `.cmd` shim — the `.cmd`/`.bat` resolution path in the
  plan is Windows-only but must still be implemented per spec).
- Package docs mirror (canonical source for Phase 0):
  `/home/megibot/.npm-global/lib/node_modules/@earendil-works/pi-coding-agent/docs/`
  All files needed for Phase 0 are present: `json.md`, `rpc.md`, `usage.md`,
  `sessions.md`, `session-format.md`, `providers.md`, `models.md`, `settings.md`,
  `environment-variables.md`, `security.md`, `extensions.md`.
- `docs/pi/` currently holds only `sdk.md` (an HTML scrape); the packaged docs are
  canonical and include every page the README lists as "not yet mirrored".
- `~/.pi/agent/auth.json` is currently empty — no live E2E; fixtures come from
  `docs/json.md` plus the packaged `.d.ts` types.
- Work lands on branch `pi` (PRs target `pi` during this workstream).

## What the docs establish (evidence)

- **Transport.** The SDK is TypeScript-only. The Python-side integration is the CLI, same
  shape as Codex: `pi --mode json "<prompt>"` emits one JSON object per line and exits
  (`docs/json.md`; `--mode json` is a non-interactive mode per `usage.md:126`).
  `--mode rpc` exists as a richer bidirectional protocol — noted as a follow-up, not used now.
- **Stream shape** (`json.md`): first line is the session header
  `{"type":"session","version":3,"id":"<uuid>","timestamp":..,"cwd":..}`, then
  `agent_start` / `turn_start` / `message_start` / `message_update` (delta-only, carries
  cumulative `usage`) / `message_end` (final authoritative message) / `turn_end` /
  `agent_end`, plus `tool_execution_start|update|end`.
- **Cost is reported, not estimated.** `Usage.cost.total` (USD) — `pi-ai/dist/types.d.ts:265`.
  No price table needed; nothing analogous to `codex_pricing.py`.
- **Real read-only enforcement.** `--tools <allowlist>` / `--exclude-tools <denylist>` over
  built-ins `read, bash, powershell, edit, write, grep, find, ls`. `pi --tools read,grep,find,ls`
  is the documented read-only recipe. This is the big difference from Codex: pi *can*
  advertise `"mode"`, so plan/review phases keep their guarantees instead of loudly degrading.
- **Sessions.** `--session-id <id>` (use/create an exact id), `--session <path|id>` (resume),
  `--fork <path|id>` (fork into a **new** session file, original intact), `--no-session`,
  `--session-dir`. The fork primitive maps directly onto `RunSpec.fork_session` — pi gets
  `session_fork`, which Codex lacks.
- **System prompt is steerable.** `--system-prompt` / `--append-system-prompt` — another
  Codex gap closed.
- **Project trust.** Non-interactive modes show no trust prompt and, with the default
  `defaultProjectTrust: ask`, **ignore project-local resources** unless `--approve` is passed
  (`usage.md:126`).
- **No MCP in core.** The `--mcp-config` flag on this machine comes from the third-party
  `npm:pi-mcp-adapter` package, which proxies MCP behind a single discovery tool — the agent
  would not see `mcp__autoswe_comment__post_plan` by name. So **no `mcp` capability in phase 1**
  (same graceful degrade as Codex). Follow-up path sketched below.
- **`ask_question` tool** exists (built-in, referenced in `sdk.md`) but there is no per-tool
  approval callback in `--mode json` — no `can_use_tool`, so no AskUserQuestion→`autoswe:waiting`
  interception. It must be **excluded** or a non-interactive run can block on it.

## Phase 0 — mirror the docs

1. Copy from the installed package into `docs/pi/`: `json.md`, `rpc.md`, `usage.md`,
   `sessions.md`, `session-format.md`, `providers.md`, `models.md`, `settings.md`,
   `environment-variables.md`, `security.md`, `extensions.md` (needed for the MCP follow-up).
   Overwrite `sdk.md` with the packaged copy (canonical markdown, not a readability scrape).
2. Rewrite `docs/pi/README.md`: source is now the **package mirror** at
   `@earendil-works/pi-coding-agent@0.84.4/docs`, with a one-line refresh command; replace the
   "not yet mirrored" list with a real TOC.

## Phase 1 — `autoswe/harness/backends/pi.py`

Mirrors `codex.py`'s structure (accumulator + line parser + async subprocess with bounded
concurrent stdout/stderr readers + timeout-kill), differing where pi is richer.

**Executable resolution (must not be skipped on Windows).** `pi` on PATH here is
`pi.cmd`; `asyncio.create_subprocess_exec` → `CreateProcess` will not run a `.cmd` shim.
Resolve via `spec.cli_path` → `shutil.which("pi")`; if the result ends in `.cmd`/`.bat`,
invoke through `cmd /c <path> ...`. (`codex.py` has the same latent gap — flag it, don't fix it here.)

**Command mapping**

| Case | argv |
|---|---|
| fresh | `pi --mode json --model <model> [--provider <p>] [--thinking <lvl>] --tools <derived> [--exclude-tools ask_question,...] [--approve] [--api-key <k>] --session-id <uuid4> [--append-system-prompt <t>] -- <prompt>` |
| resume | same, `--session <spec.resume>` instead of `--session-id` |
| fork | same, `--fork <spec.resume> --session-id <new uuid4>` (only when `spec.fork_session`) |

`cwd=spec.cwd` on the subprocess (pi has no `-C`). Prompt always behind `--`.
`RunSpec.max_turns` is a no-op (no turn cap in pi) — the guard is `spec.timeout`, documented
like Codex.

**Mode → tools** (`"mode"` capability, real enforcement)

| mode | `--tools` |
|---|---|
| `plan` | `read,grep,find,ls` |
| `read_only` | `read,grep,find,ls` |
| `read_write` | `read,bash,edit,write,grep,find,ls` (+`powershell` on Windows) |

`spec.extra_tools` appends; `spec.disallowed_tools_override` maps to `--exclude-tools`.
`ask_question` is always excluded (would block a non-interactive run).

**Parsing → `RunResult`**

- `type=="session"` → `session_id` (cross-checked against the uuid we passed; ours wins if the
  process dies before emitting the header — strictly better than Codex's parse-only path).
- `message_update` + `assistantMessageEvent.type in {text_delta, thinking_delta}` → progress
  callback + delta accumulation, keyed by `contentIndex`.
- `message_end` with `role=="assistant"` → authoritative text (replaces Codex's
  `--output-last-message` file trick); accumulated deltas are the fallback.
- `tool_execution_start|end` → progress lines (`Tool: bash …`, edit/write path rendering).
- `usage.cost.total` → `cost_usd` (real, provider-reported).
- `agent_end` → completion marker; `extension_error` and `isError` set the error flag.
- subtype: rc 0 and no error → `success`; rc < 0 → `killed`; else `error`.
  `retryable_subtypes() == {"error","killed"}`; `retryable_exceptions() == (asyncio.TimeoutError, OSError)`.
- `plan_file_path=None`, `plan_posted=False`, `question_posted=False`, `structured_output=None`.

**`capabilities()` → `{"mode", "resume", "session_fork", "progress_stream"}`**
Absent (graceful degrade already wired in the handlers): `mcp`, `can_use_tool`,
`plan_permission`, `plan_file` (so the planner's `~/.claude/plans` fs-scan stays skipped),
`structured_output` (planner/reviewer fall back to text-pattern parsing).
Because `"mode"` **is** advertised, `has_read_only_enforcement()` is True → no loud-degrade
warning and no reliance on `ensure_worktree_unchanged` rollback for plan/review.

## Phase 2 — config + factory

- `config.py`: `KNOWN_BACKENDS = {"claude_code", "codex", "pi"}`.
- `factory.py`: `pi` branch, deferred import, `model` required (→ `ValueError` like Codex;
  pi would otherwise silently pick a settings default — unacceptable for reproducibility).
- Profile fields: `backend`, `model`, `provider`, `api_key`, `thinking`, `cli_path`,
  `agent_dir` (→`PI_CODING_AGENT_DIR`), `session_dir`, `timeout`, `approve_project`
  (default `true` — dedicated-machine posture; pi ignores project resources without it),
  `system_prompt` / `append_system_prompt`, `env`.
  Env precedence identical to the other backends: `os.environ` < api-key field < profile `env`
  < `spec.env_overrides`. `${VAR}` expansion comes free from `_expand_env_dict`.
- `config/harnesses.json.example`: add `pi-opus`, `pi-gpt`, `pi-local` profiles.

## Phase 3 — tests (the mandatory gate)

- `tests/fakes/pi_fake.py` — `PiFake` patching `asyncio.create_subprocess_exec`, builder
  signatures mirroring `ClaudeFake`/`CodexFake` (`script_response`, `script_plan`,
  `script_questions`, `script_fix`, `script_fail`, `script_killed`) so existing transition-row
  response dicts feed it verbatim; emits real `--mode json` lines so the **real** parser runs;
  `.calls` records parsed argv.
- `tests/test_pi_backend.py` — flag mapping (fresh/resume/fork, mode→tools, `--approve`,
  api-key/env precedence, `.cmd` resolution), stream parsing (text assembly, session id,
  `cost.total`, tool progress), subtype matrix, timeout-kill, stream-size bounding.
- `tests/test_pi_fake.py` — fake-vs-real-parser fidelity.
- Extend `test_backend_parity.py`, `test_backend_capabilities.py`, `test_backend_factory.py`,
  `test_config.py`.
- `tests/scenarios/harness.py`: `backend="pi"` axis (`_setup_pi_harness`, `patch_pi`,
  `assert_pi_calls`) + `PI_TRANSITIONS` curated subset. Rows that matter because pi ≠ codex:
  a plan phase **with** read-only enforcement (no degrade warning, no rollback), and a
  `/retry` fork-from-checkpoint row (Codex can't fork; the `last_good_session_backend`
  provenance gate must accept `pi`).
- Gate before any commit: `pytest -q -m "not live"` and `ruff check autoswe tests`.

## Phase 4 — docs/autoswe

- `harnesses.md`: `#### pi` section in the same shape as `#### codex` — command mapping,
  profile fields, capabilities, retry semantics (fork), known limitations.
  Update the backend lists in the profile-schema table.
- `CLAUDE.md` + `docs/autoswe/README.md`: mention `pi` alongside `claude_code` / `codex`.
- `testing.md`: add `PiFake` to the fakes list and the new test files to the convention table.
- `safeguards.md`: note that pi enforces read-only via the tool allowlist (unlike Codex),
  while `read_write` grants `bash` — full access by design on the isolated host.

## Explicitly out of scope (follow-ups)

1. **MCP comment posting.** Two routes: `--mcp-config` via `npm:pi-mcp-adapter` (rejected for
   phase 1 — proxy indirection hides tool names), or ship a small pi **extension**
   (`--extension`) registering `post_plan` / `post_question` / `update_progress` tools that
   talk to the same Python servers. The latter is the real path to the `mcp` capability.
   Superseded by `PLAN-pi-mcp.md` (adapter route, agent-dir `mcp.json`, tool-name resolution).
2. **AskUserQuestion → `autoswe:waiting`.** Needs either that extension or `--mode rpc`.
3. **Structured output** — pi has no JSON-Schema-validated output; text fallback stands.
4. **`--plan` plan-mode extension** for a true `plan_permission` capability.
5. Live E2E (`e2e/`) coverage and a canonical `--mode json` fixture captured from a real
   authenticated run (`~/.pi/agent/auth.json` is currently empty, so phase-1 fixtures are
   built from `docs/json.md` plus the packaged `.d.ts` types).

## Issue breakdown (dispatched to AutoSWE, serial, PRs target `pi`)

| # | Title | Plan section | Depends on |
|---|---|---|---|
| 1 | Mirror pi docs into `docs/pi/` + rewrite README | Phase 0 | — |
| 2 | Add `PiBackend` (`autoswe/harness/backends/pi.py`) | Phase 1 | 1 |
| 3 | Register `pi` in config + factory + example profiles | Phase 2 | 2 |
| 4 | `PiFake` + `test_pi_backend.py` + `test_pi_fake.py` | Phase 3 (part A) | 2 |
| 5 | Extend parity/capabilities/factory/config tests + scenario axis | Phase 3 (part B) | 4 |
| 6 | `docs/autoswe` updates for the pi backend | Phase 4 | 2, 3 |

GitHub issues: #203–#208 in that order (label `backend-pi`).

## Dispatch protocol (this workstream) — read by the poller operator

Config: `MAX_CONCURRENT=1` in `config/autoswe.env` (poller lets exactly ONE
issue through at a time; no parallel worktrees).

Self-driving loop (Nate, 2026-09-06: the periodic task reviews the chain, does
the PR, updates/merges, and keeps moving to the next issue — no manual nudging).

The operator's periodic task (≈ every 10 min) advances the chain as far as it
can on every cycle. Each cycle: inspect chain state — queue status
(`autoswe.py queue status`), issue labels, open PRs, CI on the head branch —
then execute the FIRST applicable transition:

- **T1 — nothing in flight:** post `/fix --branch pi` on the next open issue
  in order (`autoswe:pending` or no autoswe status yet). Every fresh-issue
  dispatch carries `--branch pi` so the work branch is cut from — and its PR
  targets — `pi`, even if the config ever drifts. Correction passes on the
  same issue (`/fix with ...`) don't take the flag; the base is already locked.
- **T2 — issue at `autoswe:fixed`:** review the diff for real — read
  `autoswe/issue-N` vs `pi`, check acceptance criteria, run the issue's gate
  commands in the worktree. Clean → post `/pr`. Not clean → post
  `/fix with <specific correction>` (correction pass; counts against attempt
  limits) and do NOT post `/pr`.
- **T3 — PR open, CI green, review verdict clean:** merge into `pi` (squash),
  verify the merged commit on `pi`, confirm `autoswe:shipped`.
- **T4 — issue done (shipped/merged):** post `/fix --branch pi` on the next
  issue in order.

Rules:
- One issue in flight at a time (`MAX_CONCURRENT=1`). Never two commands on two
  issues in the same cycle; the poller picks up one new command per issue per
  cycle anyway.
- The review is real, never a rubber stamp: read the diff, run the gate
  (ruff/pytest per the issue), and treat the `/review` harness verdict as input
  — a verdict that disagrees with what the diff actually does means STOP and
  flag, not merge.
- Merge into `pi` only when review verdict is clean (no CRITICAL/MEDIUM)
  **and** CI is green. Only workstream issue PRs merge to `pi`; the `pi` →
  `master` merge happens only after all six issues (post-workstream, below).
- Stall handling: `guard_blocked`, `autoswe:failed`/`error`, review-vs-diff
  disagreement, or 2 consecutive cycles with no state change → stop, flag Nate
  with the diagnosis (logs, queue entry, last command), and wait for direction.
  Do not `/retry` past `MAX_ATTEMPTS`.
- Log each transition (time, issue, transition, verdict) to
  `memory/YYYY-MM-DD.md` so the chain is resumable from any cycle.

Order: #203 → #204 → #205 → #206 → #207 → #208.

### After all six are merged into `pi` (post-workstream steps, Nate)

1. Merge `pi` → `master`; set `config/repos.json` `Natedorr/AutoSWE.base_branch` back to `master`.
2. Point `Natedorr/testProject` at the pi backend: add live `pi` profiles to `config/harnesses.json` (backend=pi, model/provider/api_key per the profile fields in Phase 2) and set testProject's `plan_harness`/`fix_harness`/`review_harness` to the pi profile.
3. Start testing: E2E smoke test on `Natedorr/testProject` (seed issue + `/fix`), watch the poller log, verify the pi backend actually runs (first live use — no live fixture exists yet, so this also generates the canonical `--mode json` fixture).
