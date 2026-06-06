# Configuration

## `config/autoswe.env` (gitignored, copy from `autoswe.env.example`)

Loaded by `core/config.py:load_config()`. Env vars take precedence over file values; file values override defaults.

| Key | Default | Description |
|-----|---------|-------------|
| `MAX_CONCURRENT` | `1` | Max simultaneous agent jobs |
| `MAX_ATTEMPTS` | `3` | Max restart attempts per issue before failing |
| `MAX_TOTAL_HOURS` | `2` | Max total time per issue in hours |
| `AGENT_TIMEOUT` | `7200` | Max Claude session runtime in seconds (2 hours) |
| `AGENT_RETRY_ON_FAILURE` | `0` | Auto-retry failed handler runs (0 = disabled) |
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
| `LINK_BRANCH_TO_ISSUE` | `false` | Link feature branches to issues in the provider UI (e.g. GitHub Development sidebar). When `true`, the branch is linked at worktree creation time via GraphQL `createLinkedBranch` (GitHub only; no-op for Azure). Requires a PAT with `contents` + `issues` write scope. Defaults to `false` — only enable if you use the Development sidebar. |
| `SYNC_STRATEGY` | `merge` | Strategy for `/sync`: `"merge"` (append-only merge commit) or `"rebase"` (linear history, force-pushes) |

**Integer keys re-parsed:** After loading the file, `AGENT_TIMEOUT`, `AGENT_RETRY_ON_FAILURE`, `MAX_ATTEMPTS`, `MAX_TOTAL_HOURS`, `MAX_CONCURRENT`, and `MAX_DRAIN_CYCLES` are cast to `int` (`config.py:51-55`).

**Boolean keys re-parsed:** `SILENT_REPORTING`, `MINIMAL_POSTING`, `AUTO_ASSIGN`, `AUTO_CREATE_PR`, and `LINK_BRANCH_TO_ISSUE` are compared to `"true"` (case-insensitive) after file load.

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

### Azure Entry (`"org/project/repo"`)

Same fields as GitHub (`pat` is required for both GitHub and Azure entries).

Keys are validated: missing ``provider`` raises ``ValueError``, any entry without ``pat`` raises ``ValueError``, Azure entries without 3-part key raise ``ValueError`` (``config.py:85-111``).

## `config/harnesses.json` (gitignored, copy from `harnesses.json.example`)

Loaded by ``core/config.py:load_harnesses_config()``. Keys starting with ``_`` are skipped.

Defines **named harness profiles** that bundle a coding backend (``claude_code``, ``codex``) with its model and auth/runtime settings. Phases reference a profile by name via ``plan_harness``, ``fix_harness``, or ``review_harness`` in repos.json (or ``PLAN_HARNESS``, ``FIX_HARNESS``, ``REVIEW_HARNESS`` in autoswe.env).

Each profile requires a ``backend`` field (``"claude_code"`` or ``"codex"``). Optional fields: ``model``, ``timeout``, ``cli_path``, ``api_key_env``, ``anthropic_base_url``, ``anthropic_auth_token``.

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
4. Backend default (e.g. Claude Code's or Codex's built-in default model)

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
