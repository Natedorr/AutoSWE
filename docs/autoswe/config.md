# Configuration

## SDK & Claude Code CLI version floor

autoSWE runs the `claude_code` backend on the Python Claude Agent SDK, which bundles a
Claude Code CLI. `requirements.txt` pins **`claude-agent-sdk >= 0.2.137`** (lower bound,
no cap) — the lowest release whose bundled CLI can run the current model generation.
The **tested combo** is that floor against Claude Code CLI **v2.1.251**.

- Python Agent SDK floor: **`>= 0.2.137`** (clears `fork_session`, the
  `output_tokens_details` / `origin` / `ConversationResetMessage` fields, and bundles a
  CLI that runs the 5.x models).
- Claude Code CLI floor: the SDK's bundled CLI is sufficient, but if you pin your own
  `claude` binary (`CLAUDE_CLI_PATH`) use **`v2.1.233`** or later — that is the
  `CLAUDE_CODE_ENABLE_TODO_TOOLS` floor and also satisfies the Opus 5 floor
  (`v2.1.219`). Sonnet 5 needs `v2.1.197` or later.

`tests/test_sdk_version.py` fails with an actionable message if the installed
`claude-agent-sdk` drops below the pinned floor; it skips when the SDK is not installed
(e.g. Codex-only deploys).

## GitHub API version pin

Every autoSWE call to the GitHub REST API sends a pinned
`X-GitHub-Api-Version` header. The value lives in a single named constant,
`GH_API_VERSION = "2022-11-28"`, in `autoswe/core/constants.py`, and is imported
by every call site:

- `autoswe/tracking/api.py` (`_gh_request`, `gh_post_comment`)
- `autoswe/commands/setup.py` (`_gh_verify`, `_gh_default_branch`)
- `mcp_servers/autoswe_comment_server.py` and `mcp_servers/autoswe_inline_comment_server.py`

**Why pin at all:** GitHub's default REST API version drifts over time. Pinning
makes autoSWE's behavior reproducible regardless of what GitHub serves by
default, and turns "keep up with GitHub" into a one-line change to a single
constant instead of a multi-file string hunt.

**Re-check cadence:** when GitHub announces a new recommended
`X-GitHub-Api-Version` (it appears in the refreshed endpoint docs vendored
under `docs/github-api/` — e.g. the `2026-03-10` note in
`docs/github-api/assignees.md`), check whether any endpoint autoSWE actually
calls has started *requiring* the newer version. If not, leave the pin as is.
If one does, bump `GH_API_VERSION` in `autoswe/core/constants.py` — one place.
`tests/test_api_version.py` fails if a call site reintroduces the bare literal
or if the value documented here stops matching the constant.

> `docs/github-api/README.md` is a vendored snapshot of GitHub's own docs — its
> `2022-11-28` mention is GitHub's text, not an autoSWE recommendation, and is
> intentionally left unedited.

## `config/autoswe.env` (gitignored, copy from `autoswe.env.example`)

Loaded by `core/config.py:load_config()`. Env vars take precedence over file values; file values override defaults.

| Key | Default | Description |
|-----|---------|-------------|
| `MAX_CONCURRENT` | `1` | Max simultaneous agent jobs |
| `MAX_ATTEMPTS` | `3` | Retry budget per issue: consecutive re-runs of failing work (from `failed`/`error`/`skipped`/`aborted` or `planned` restarts) before failing. Restarting from a successful rest (`fixed`/`synced`/`shipped`/`reviewed`, `review_failed`/`review_blocked`) starts a fresh budget |
| `MAX_TOTAL_HOURS` | `2` | Max total time per issue in hours |
| `AGENT_TIMEOUT` | `7200` | Max Claude session runtime in seconds (2 hours) |
| `AGENT_RETRY_ON_FAILURE` | `0` | Auto-retry failed handler runs (0 = disabled) |
| `AGENT_RETRY_ON_SUBTYPE` | `""` | Comma-separated list of `RunResult.subtype` values that trigger a retry (e.g. `"error,killed"`). When set, overrides the backend's default retryable-subtype set. Empty string = use backend default (Codex: `"error,killed"`; Claude Code: `""` — relies on exception-based retry). |
| `WORKTREE_ORPHAN_POLICY` | `commit` | Policy when a worktree is left dirty by a SIGKILL'd dispatch: `"commit"` = commit + push orphaned changes before re-dispatch; `"discard"` = hard-reset; `"log_only"` = log but take no git action. |
| `MAX_DRAIN_CYCLES` | `50` | Max drain cycles for `poller --drain` |
| `WORKTREE_DIR` | `worktrees` | Worktree root (relative to AUTOSWE_DIR, or absolute path) |
| `SILENT_REPORTING` | `false` | Skip welcome comments |
| `MINIMAL_POSTING` | `false` | Collapse dispatch to 2 API calls: one POST on start, one PATCH with the final result |
| `AUTO_ASSIGN` | `true` | Auto-assign issues to their creator on pickup |
| `ASSIGN_USER` | `""` | Override assignee target (defaults to issue creator) |
| `AUTO_CREATE_PR` | `false` | Automatically create a PR after a successful `/fix` |
| `CLAUDE_CLI_PATH` | `""` | Pin a specific `claude` binary |
| `PLAN_MODEL` | `""` | Model for `/plan` phase (legacy — superseded by `PLAN_HARNESS`) |
| `FIX_MODEL` | `""` | Model for `/fix` phase (legacy — superseded by `FIX_HARNESS`) |
| `REVIEW_MODEL` | `""` | Model for `/review` phase (legacy — superseded by `REVIEW_HARNESS`) |
| `PLAN_HARNESS` | `""` | Named harness profile for `/plan` phase (from `harnesses.json`) |
| `FIX_HARNESS` | `""` | Named harness profile for `/fix` phase |
| `REVIEW_HARNESS` | `""` | Named harness profile for `/review` phase |
| `ANTHROPIC_AUTH_TOKEN` | `""` | e.g. `"ollama"` for local Ollama server |
| `ANTHROPIC_API_KEY` | `""` | Anthropic API key |
| `ANTHROPIC_BASE_URL` | `""` | e.g. `http://localhost:11434` |
| `BOT_NAME` | `autoswe` | Bot identifier used in label prefix and comment markers |
| `ALLOWED_AUTHORS` | `""` | Comma-separated list of allowed author logins (empty = no restriction). Controls who can trigger slash commands AND who can create issues that autoSWE processes. For GitHub, use usernames (e.g. "natedorr"). For Azure, use UPN/email (e.g. "jane@example.com") |
| `LINK_BRANCH_TO_ISSUE` | `true` | Link feature branches to issues in the provider UI (e.g. GitHub Development sidebar). When `true`, the branch is linked at worktree creation time via GraphQL `createLinkedBranch` (GitHub only; no-op for Azure). Requires a PAT with `contents` + `issues` write scope; on a PAT lacking that scope the link is skipped (best-effort) and PR creation is unaffected. Defaults to `true` — set `LINK_BRANCH_TO_ISSUE=false` to opt out. |
| `SYNC_STRATEGY` | `merge` | Strategy for `/sync`: `"merge"` (append-only merge commit) or `"rebase"` (linear history, force-pushes) |
| `PR_REQUIRE_SYNC` | `true` | Gate `/pr` (and auto-PR) on the feature branch being in sync with its base. When behind, `pr_gate.preflight_pr()` runs the same sync used by `/sync`, resolving merge conflicts via `coder.resolve_sync_conflicts()`; if sync can't complete cleanly, the PR is blocked with `FAILED: <reason>`. Set `false` to skip this check entirely. |
| `PR_REQUIRE_CI` | `true` | Gate `/pr` (and auto-PR) on CI status via `VCSProvider.get_ci_status()`. `pending` or `failure` blocks the PR; `success` or `none` (no CI configured on the repo) passes. Set `false` to skip this check entirely. |
| `TEST_GATE` | `true` | Post-fix test gate (Natedorr/testProject#20): after the fix agent commits/pushes, `coder._finalize_fix` runs the repo's test suite in the worktree before the task can reach terminal `fixed`. A red suite lands the task in the non-terminal `test_failed` status (a comment carries the failure, `/pr` is blocked, `/fix`/`/retry` restart with a fresh attempt budget). Skips (no resolvable command, missing runner, timeout, no tests collected) are non-gating. Set `false` to disable. |
| `TEST_GATE_TIMEOUT` | `600` | Post-fix test gate timeout in seconds. A timeout is non-gating (skip + warning). |
| `TEST_COMMAND` | `""` | Explicit test command run in the worktree root for the post-fix test gate (e.g. `pytest -q`, `npm test`). Resolution order: per-repo `test_command` → `TEST_COMMAND` → Python/pytest detection in the worktree → skip. Blank = rely on per-repo / detection only. |
| `AUTO_PURGE_BRANCHES` | `false` | Opt-in heartbeat cleanup of worktrees whose remote `autoswe/issue-{N}` branch no longer exists. When `true`, each poll cycle prunes a repo's remote-tracking refs (`git fetch --prune`) and removes any `issue-{N}/` worktree dir + local branch whose remote branch is gone — e.g. a merged-and-auto-deleted PR. In-flight tasks (live PID) and dirty worktrees are always skipped; a failed `fetch --prune` makes the whole step a no-op. Only the worktree dir + local branch are removed — `queue.json` is left to the separate `queue prune` job. See [git-worktrees.md](git-worktrees.md). |

**Integer keys re-parsed:** After loading the file, `AGENT_TIMEOUT`, `AGENT_RETRY_ON_FAILURE`, `MAX_ATTEMPTS`, `MAX_TOTAL_HOURS`, `MAX_CONCURRENT`, `MAX_DRAIN_CYCLES`, and `TEST_GATE_TIMEOUT` are cast to `int` (`config.py:51-55`).

**Boolean keys re-parsed:** `SILENT_REPORTING`, `MINIMAL_POSTING`, `AUTO_ASSIGN`, `AUTO_CREATE_PR`, `LINK_BRANCH_TO_ISSUE`, `PR_REQUIRE_SYNC`, `PR_REQUIRE_CI`, `AUTO_PURGE_BRANCHES`, and `TEST_GATE` are compared to `"true"` (case-insensitive) after file load.

**Per-repo overrides:** `pr_gate._flag()` checks `repo_cfg` first — a lowercase `pr_require_sync` / `pr_require_ci` key in a `repos.json` entry overrides the global `autoswe.env` value for that repo only (same pattern as `plan_model`/`fix_model` overrides).

## `config/repos.json` (gitignored, copy from `repos.json.example`)

Loaded by `core/config.py:load_repos_config()`. Keys starting with `_` are skipped.

### GitHub Entry (`"owner/repo"`)

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `provider` | **Yes** | — | `"github"` or `"azure"` |
| `pat` | **Yes** | — | PAT token with `repo` scope |
| `base_branch` | No | `"main"` | Base branch for worktrees |
| `model` | No | `""` | Generic model (fallback for both phases) |
| `plan_model` | No | `""` | Model for `/plan` phase (legacy — superseded by `plan_harness`) |
| `fix_model` | No | `""` | Model for `/fix` phase (legacy — superseded by `fix_harness`) |
| `review_model` | No | `""` | Model for `/review` phase (legacy — superseded by `review_harness`) |
| `plan_harness` | No | `""` | Named harness profile for `/plan` phase (from `harnesses.json`) |
| `fix_harness` | No | `""` | Named harness profile for `/fix` phase |
| `review_harness` | No | `""` | Named harness profile for `/review` phase |
| `agent_timeout` | No | (from env) | Per-repo agent timeout in seconds |
| `plan_prompt` | No | `config/prompts/plan.txt` | Custom plan prompt file path (relative to AUTOSWE_DIR, or absolute) |
| `fix_prompt` | No | `config/prompts/fix.txt` | Custom fix prompt file path (relative to AUTOSWE_DIR, or absolute) |
| `review_prompt` | No | `config/prompts/review.txt` | Custom review prompt file path (relative to AUTOSWE_DIR, or absolute) |
| `conflict_resolution_prompt` | No | `config/prompts/conflict_resolution.txt` | Custom conflict resolution prompt file path (relative to AUTOSWE_DIR, or absolute) |
| `anthropic_base_url` | No | (from env) | Per-repo API endpoint |
| `anthropic_auth_token` | No | (from env) | Per-repo auth token |
| `auto_dispatch_new` | No | `false` | On a brand-new issue with no slash command, set `autoswe_status = pending` anyway (treated as a default `/fix`) instead of waiting for a command |
| `allowed_authors` | No | `""` | Comma-separated list of allowed author logins (overrides global `ALLOWED_AUTHORS`). Controls who can trigger slash commands and whose issues are processed |
| `test_command` | No | (from `TEST_COMMAND`) | Post-fix test gate command run in the worktree root (e.g. `pytest -q`, `npm test`). Wins over global `TEST_COMMAND` and Python detection — see `handlers.md` (post-fix test gate) |
| `test_gate` | No | (from `TEST_GATE`) | Enable/disable the post-fix test gate for this repo |
| `test_gate_timeout` | No | (from `TEST_GATE_TIMEOUT`) | Test-suite timeout in seconds for this repo |

### Azure Entry (`"org/project/repo"`)

Same fields as GitHub (`pat` is required for both GitHub and Azure entries).

Keys are validated: missing ``provider`` raises ``ValueError``, any entry without ``pat`` raises ``ValueError``, Azure entries without 3-part key raise ``ValueError`` (``config.py:85-111``).

## `config/harnesses.json` (gitignored, copy from `harnesses.json.example`)

Loaded by ``core/config.py:load_harnesses_config()``. Keys starting with ``_`` are skipped.

Defines **named harness profiles** that bundle a coding backend (``claude_code``, ``codex``) with its model and auth/runtime settings. Phases reference a profile by name via ``plan_harness``, ``fix_harness``, or ``review_harness`` in repos.json (or ``PLAN_HARNESS``, ``FIX_HARNESS``, ``REVIEW_HARNESS`` in autoswe.env).

Each profile requires a ``backend`` field (``"claude_code"`` or ``"codex"``). ``model`` is required for ``codex`` profiles (no built-in default); optional otherwise. Other optional fields: ``timeout``, ``cli_path``, ``api_key_env``, ``anthropic_base_url``, ``anthropic_auth_token``, ``env`` (a ``{key: value}`` map of extra environment variables merged into the backend's child process — see [harnesses.md](harnesses.md#per-profile-env)).

Full documentation: [harnesses.md](harnesses.md).

## Harness Resolution (highest → lowest priority)

For each phase (plan, fix, review):

1. ``repos.json`` phase-specific harness: ``plan_harness``, ``fix_harness``, or ``review_harness`` → looks up profile in ``harnesses.json``
2. ``autoswe.env`` phase-specific harness: ``PLAN_HARNESS``, ``FIX_HARNESS``, or ``REVIEW_HARNESS`` → looks up profile in ``harnesses.json``
3. Synthesized default: ``{"backend": "claude_code", "model": <phase_model>}`` — falls back to the legacy model resolution below

## Model Resolution Order (legacy, highest → lowest priority)

(Used when no harness profile is set, or inside a synthesized default profile.)

1. ``repos.json`` phase-specific: ``plan_model`` (for `/plan`), ``fix_model`` (for `/fix`), or ``review_model`` (for `/review`)
2. ``autoswe.env`` phase-specific: ``PLAN_MODEL``, ``FIX_MODEL``, or ``REVIEW_MODEL``
3. ``repos.json`` generic: ``model``
4. Backend default (e.g. Claude Code's built-in default model; Codex has no built-in default — its profile must set ``model``)

Code path: ``config.py:resolve_harness()`` → ``config.py:load_harnesses_config()``. Model fallback inside synthesized profile uses the same chain as handlers (e.g. ``planner.py``, ``coder.py``, ``reviewer.py``).

## Prompt Templates

### `config/prompts/plan.txt`

Variables: `{{OWNER}}`, `{{REPO}}`, `{{ISSUE_NUMBER}}`, `{{TITLE}}`, `{{BODY}}`, `{{COMMENTS}}`, `{{BASE_BRANCH}}`

### `config/prompts/fix.txt`

Variables: `{{OWNER}}`, `{{REPO}}`, `{{ISSUE_NUMBER}}`, `{{TITLE}}`, `{{BODY}}`, `{{COMMENTS}}`, `{{GUIDANCE_BLOCK}}`, `{{PLAN}}`

The `{{PLAN}}` variable is extracted from existing bot comments by `prompts.py:_find_plan_in_comments()` (newest first): primarily an MCP-posted plan comment (body starting with `## Plan`), falling back to the deprecated `<AUTOSWE_PLAN>` block.

### `config/prompts/review.txt`

Variables: `{{OWNER}}`, `{{REPO}}`, `{{ISSUE_NUMBER}}`, `{{TITLE}}`, `{{BODY}}`, `{{PLAN}}`, `{{DIFF_STAT}}`, `{{DIFF}}`, `{{GUIDANCE_BLOCK}}`, `{{BASE_BRANCH}}`

### `config/prompts/conflict_resolution.txt`

Variables: `{{OWNER}}`, `{{REPO}}`, `{{ISSUE_NUMBER}}`, `{{TITLE}}`, `{{BODY}}`, `{{PLAN}}`, `{{CONFLICT_FILES}}`, `{{BASE_BRANCH}}`

### Per-Repo Prompt Overrides

Each repos.json entry can include `plan_prompt`, `fix_prompt`, `review_prompt`, and `conflict_resolution_prompt` keys to point to custom prompt files. Paths are resolved relative to `AUTOSWE_DIR` unless absolute. If the override file is missing, the bundled default in `config/prompts/*.txt` is used. This lets users maintain a custom methodology (e.g. gstack-inspired prompts) without modifying AutoSWE source.

```json
{
  "natedorr/edgarFiling": {
    "provider": "github",
    "pat": "ghp_...",
    "plan_prompt": "config/prompts/edgar-plan.txt",
    "review_prompt": "config/prompts/edgar-review.txt",
    "fix_prompt": "config/prompts/edgar-fix.txt"
  }
}
```

### `config/welcome_comment.txt`

Variables: `{{SLUG}}`, `{{SLASH_COMMAND}}`, `{{GUIDANCE_SUFFIX}}`
