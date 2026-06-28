# Provider Architecture

## Why the Abstraction Exists

autoSWE supports multiple backends (GitHub, Azure DevOps) through a provider protocol. The orchestrator (`orch/loop.py`) talks to adapters via two functions — `read_api()` and `apply_effect()` — returned by the factory. No orchestrator code calls backend-specific functions directly.

## Adapter Contract

Each provider implements two adapter functions:

### `read_api(tracker, repo_cfg, cfg, bot_ids) -> dict[int, ApiState]`

Fetches all open issues and their comments, returning `ApiState` objects keyed by issue number. Responsible for:

- Calling `tracker.list_open_issues()` and `tracker.fetch_comments()`
- Filtering out PRs
- Producing clean `NormalizedComment` objects with `id` and `is_bot` set from `bot_ids` membership
- Returning both the issue data and the comment data in a provider-agnostic shape

### `apply_effect(tracker, effect, repo_cfg, issue_num, queue, slug) -> None`

Translates a single `Effect` into the provider's API. The dispatch loop calls this function for each Effect returned by `emit()` (except `post_comment`, which goes to `ProgressComment.finalize()`).

## Effect → API Call Translation

| Effect.kind | Queue Field | GitHub | Azure |
|-------------|-------------|--------|-------|
| `set_status` | — | `PUT /issues/{n}/labels` (replace label set) | `PATCH /workitems/{n}` (JSON-Patch `System.Tags`) |
| `patch_queue` | In-process | Direct dict merge on `queue[slug]` | Same |
| `post_comment` | — | `POST /issues/{n}/comments` | `POST /workitems/{n}/comments?format=Markdown` |
| `update_comment` | — | `PATCH /issues/comments/{id}` | `PATCH /workitems/{n}/comments/{id}?format=Markdown` |
| `assign` | — | `POST /issues/{n}/assignees` | `PATCH /workitems/{n}` (JSON-Patch `System.AssignedTo`) |
| `create_pr` | — | `POST /pulls` (or `gh pr create`) | REST API `POST /pullrequests` |
| `noop` | — | (no-op) | (no-op) |

## Protocols (`providers/base.py`)

### `IssueTracker` (Protocol)

| Method | Returns | Description |
|--------|---------|-----------|
| `list_open_issues(repo_cfg)` | `list[NormalizedIssue]` | All open issues for the repo |
| `fetch_issue(repo_cfg, issue_number)` | `NormalizedIssue` | Single issue by number |
| `fetch_comments(repo_cfg, issue_number)` | `list[NormalizedComment]` | All comments on an issue |
| `post_comment(repo_cfg, issue_number, body)` | `int \| None` | Post a comment; returns comment ID |
| `update_comment(repo_cfg, issue_number, comment_id, body)` | `None` | Edit an existing comment |
| `create_issue(repo_cfg, title, body)` | `int` | Create new issue; returns issue number |
| `set_status(repo_cfg, issue_number, status)` | `None` | Set autoswe status label/tag |
| `get_status(issue)` | `str \| None` | Current status string or None |
| `assign_to_user(repo_cfg, issue_number, login)` | `None` | Assign issue to user (idempotent) |
| `authenticated_user(repo_cfg)` | `str` | Login of authenticated user |

### `VCSProvider` (Protocol)

| Method | Returns | Description |
|--------|---------|-----------|
| `clone_url(repo_cfg)` | `str` | Full clone URL with auth |
| `branch_name(issue_number)` | `str` | Branch name for issue (e.g., `autoswe/issue-42`) |
| `find_existing_pr(repo_cfg, branch)` | `PRResult \| None` | Existing PR for branch |
| `open_pull_request(repo_cfg, branch, base, title, body)` | `PRResult` | Open PR; raises on failure |
| `link_branch_to_issue(issue_number, commit_sha, branch)` | `None` | Link branch to issue in platform UI (no-op default for Azure) |


## Factory (`providers/factory.py`)

```python
get_tracker(repo_cfg) → IssueTracker    # reads repo_cfg["provider"]
get_vcs(repo_cfg) → VCSProvider         # reads repo_cfg["provider"]
build_repo_cfg(owner, repo, cfg, repos_cfg, provider) → dict
```

`repo_cfg["provider"]` selects the backend: `"github"` → `GitHubTracker`/`GitHubVCS`, `"azure"` → `AzureTracker`/`AzureVCS`. Missing or unknown provider raises `ValueError`.

`build_repo_cfg()` merges global config (GITHUB_TOKEN) with per-repo overrides from `repos.json`. For Azure, handles 3-part keys (`org/project/repo`).

Both trackers populate `NormalizedIssue.state` (`"open"` / `"closed"`) so the dispatch-time refresh can skip a task whose issue has been closed (`safeguards.md`).

## GitHub Implementation (`providers/github/`)

- **`tracker.py:GitHubTracker`** — wraps `tracking/api.py` helpers. Lazily ensures labels. Normalizes `author_login` to `BOT`/`OWNER`/`AUTHOR` in `fetch_comments()`. `state` comes straight from the issue's `state` field. All outbound comment bodies (POST/PATCH) are passed through `redact_worktree_paths()` to prevent leaking host filesystem paths into comments.
- **`vcs.py:GitHubVCS`** — HTTPS clone URL with `x-access-token:`, `gh pr create` with GitHub API fallback, `gh pr list` for existing PR check. PR title and body are redacted before creation. `link_branch_to_issue()` uses the GitHub GraphQL API (`createLinkedBranch` mutation) — fetches the issue `node_id` via REST, then POSTs to `/graphql`. Handles "already exists" errors as idempotent no-ops. Raises `MissingScopeError` on permission failures.
- **`adapter.py`** — `read_api()` and `apply_effect()` bridge the tracker/VCS to the orchestrator.

## Azure Implementation (`providers/azure/`)

- **`tracker.py:AzureTracker`** — WIQL for discovery, batch API for expand, tag-based label mirror (semicolons in `System.Tags`). Normalizes `author_login` same way as GitHub. `state` maps `System.State`: `Closed`/`Done`/`Removed` → `"closed"`, otherwise `"open"`. HTML stripping via `_StripHTML` parser preserves `<AUTOSWE_*>` tags. All outbound comment bodies are redacted via `redact_worktree_paths()`.
- **`vcs.py:AzureVCS`** — Azure Repos REST API for clone URL, PR creation, PR discovery. PAT embedded in HTTPS URL. PR title and body are redacted before creation. `link_branch_to_issue()` is a documented no-op (Azure DevOps has no equivalent feature).
- **`adapter.py`** — `read_api()` and `apply_effect()` bridge the tracker/VCS to the orchestrator. Sets `is_bot` from `bot_ids` membership and body marker fallback.

Both providers share `autoswe/issue-{N}` branch naming.

## Path Redaction (`core/redact.py`)

All outbound content posted to external services (comments, PR titles, PR bodies) is passed through `redact_worktree_paths(text)` before the API call. This prevents host filesystem paths from leaking into platform UI:

- Masks the worktree root path so everything up to the leaf directory becomes `".../`
- Respects `WORKTREE_DIR` (uses basename if absolute, e.g. `/tmp/my_wt` → `my_wt`)
- Idempotent — text with no worktree paths is returned unchanged
- Applied at every outbound boundary: `post_comment()`, `update_comment()`, `open_pull_request()`, and `gh_post_comment()`
