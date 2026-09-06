# Provider Architecture

## Why the Abstraction Exists

autoSWE supports multiple backends (GitHub, Azure DevOps) through a provider protocol. The orchestrator (`orch/loop.py`) talks to providers through a **single shared adapter** — `read_api()` and `apply_effect()` in `providers/adapter.py` — plus the `IssueTracker` / `VCSProvider` protocol objects returned by the factory registry. No orchestrator code calls backend-specific functions directly.

Because the write path (`Effect`) only ever calls `tracker.*` / `vcs.*` protocol methods, there is **one** `apply_effect` for every provider. `read_api` is likewise shared; its only provider-specific behaviour is comment-body normalisation, delegated to a `tracker.normalize_comment_body(comment)` hook.

## Adapter Contract

One shared module, `providers/adapter.py`, exposes two functions:

### `read_api(tracker, repo_cfg, cfg, bot_ids, prev_updated, force_fetch) -> dict[int, ApiState]`

Fetches all open issues and their comments, returning `ApiState` objects keyed by issue number. Responsible for:

- Calling `tracker.list_open_issues()` and `tracker.fetch_comments()`
- Normalising each comment body via `tracker.normalize_comment_body(comment)` (the provider-specific hook — identity for GitHub, HTML/entity stripping + content-based bot detection for Azure) and setting `is_bot` from `bot_ids` membership or the body marker
- Returning both the issue data and the comment data in a provider-agnostic shape

### `apply_effect(tracker, effect, repo_cfg, issue_num, queue, slug, cfg=None) -> None`

Translates a single `Effect` into the provider's API. The dispatch loop calls this function for each Effect returned by `emit()` (except `post_comment`, which goes to `ProgressComment.finalize()`). It is provider-agnostic — it branches on `Effect.kind`, never on provider.

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

Both protocols are `@runtime_checkable` `Protocol`s kept purely for structural `isinstance` checks. The concrete provider classes do **not** inherit from them (inheriting a Protocol gives every declared method an empty body, so a missing implementation would silently return `None` instead of raising `AttributeError`).

No method takes a `repo_cfg` argument: the provider instance is constructed from a `repo_cfg` and already holds everything it needs, so passing the config at every call site was inert.

### `IssueTracker` (Protocol)

| Method | Returns | Description |
|--------|---------|-----------|
| `list_open_issues()` | `list[NormalizedIssue]` | All open issues for the repo |
| `fetch_issue(issue_number)` | `NormalizedIssue` | Single issue by number |
| `fetch_comments(issue_number)` | `list[NormalizedComment]` | All comments on an issue |
| `post_comment(issue_number, body)` | `int \| None` | Post a comment; returns comment ID |
| `update_comment(issue_number, comment_id, body)` | `None` | Edit an existing comment |
| `create_issue(title, body)` | `int` | Create new issue; returns issue number |
| `set_status(issue_number, status)` | `None` | Set autoswe status label/tag |
| `get_status(issue)` | `str \| None` | Current status string or None |
| `assign_to_user(issue_number, login)` | `None` | Assign issue to user (idempotent) |
| `authenticated_user()` | `str` | Login of authenticated user |
| `normalize_comment_body(comment)` | `tuple[str, bool]` | Provider-specific body cleanup; returns `(body, is_bot)` |
| `slug_prefix()` | `str` | Queue-slug prefix for this provider (`gh` / `ado`) |
| `pid_prefix()` | `str` | PID-file stem prefix for this provider (`gh_` / `ado_`) |

### `VCSProvider` (Protocol)

| Method | Returns | Description |
|--------|---------|-----------|
| `clone_url()` | `str` | Full clone URL with auth |
| `branch_name(issue_number)` | `str` | Branch name for issue — the single source of the branch convention (e.g., `autoswe/issue-42`) |
| `find_existing_pr(branch)` | `PRResult \| None` | Existing PR for branch |
| `open_pull_request(branch, base, title, body)` | `PRResult` | Open PR; raises on failure |
| `link_branch_to_issue(issue_number, commit_sha, branch)` | `None` | Link branch to issue in platform UI (no-op default for Azure) |
| `get_ci_status(branch, ref_sha=None)` | `CIStatus` | Combined CI status for the branch head — used by `vcs/pr_gate.py` to gate `/pr` |
| `commit_url(commit_sha)` | `str \| None` | Clickable URL for a commit, or None |
| `branch_url(branch)` | `str \| None` | Clickable URL for a branch, or None |
| `worktree_path_parts()` | `tuple[str, ...]` | Path parts for worktree/clone dirs — GitHub `(owner, repo)`, Azure `(org, project, repo)` |
| `resolve_repo_id()` | `str \| None` | Platform-specific repo id for URLs (Azure: Git repo UUID; GitHub: no-op) |
| `slug_prefix()` / `pid_prefix()` | `str` | Queue-slug / PID-file stem prefixes |

`CIStatus` (`providers/base.py`) is a provider-agnostic dataclass: `state` (`"success" \| "pending" \| "failure" \| "none"`), `total`, `failing: list[str]`, `pending_count`, `summary`. `"none"` means no CI is configured on the repo — treated as a pass so autoSWE never blocks forever on repos without checks.


## Registry (`providers/factory.py`)

```python
TRACKERS: dict[str, type] = {"github": GitHubTracker, "azure": AzureTracker}
VCSS:     dict[str, type] = {"github": GitHubVCS,     "azure": AzureVCS}

provider_names()  → list[str]      # sorted registry keys (CLI choices / validation)
get_tracker(repo_cfg) → IssueTracker    # registry lookup by repo_cfg["provider"]
get_vcs(repo_cfg)     → VCSProvider     # registry lookup by repo_cfg["provider"]
build_repo_cfg(owner, repo, cfg, repos_cfg, provider) → dict
```

The registry is the **single place** that knows which concrete classes implement which provider name — there is no `if/elif` on the provider anywhere else. `get_tracker` / `get_vcs` are one-line `registry[provider](repo_cfg)` lookups; the CLI's `--provider` choices come from `provider_names()`. Missing or unknown provider raises `ValueError`.

Adding a third provider now costs **one provider package** (a tracker + a VCS, each supplying the `normalize_comment_body` / `worktree_path_parts` / URL / slug-prefix hooks) **plus one entry in each registry dict** — no scattered edits outside the provider package.

`build_repo_cfg()` merges global config (GITHUB_TOKEN) with per-repo overrides from `repos.json`. For Azure it **always** normalises `org`/`project`/`repo` onto the returned dict, so callers never re-derive them heuristically.

Both trackers populate `NormalizedIssue.state` (`"open"` / `"closed"`) so the dispatch-time refresh can skip a task whose issue has been closed (`safeguards.md`).

## GitHub Implementation (`providers/github/`)

- **`tracker.py:GitHubTracker`** — wraps `tracking/api.py` helpers. Lazily ensures labels. Normalizes `author_login` to `BOT`/`OWNER`/`AUTHOR` in `fetch_comments()`. `state` comes straight from the issue's `state` field. All outbound comment bodies (POST/PATCH) are passed through `redact_outbound()` to prevent leaking host filesystem paths or credential-bearing URLs into comments.
- **`vcs.py:GitHubVCS`** — HTTPS clone URL with `x-access-token:`, `gh pr create` with GitHub API fallback, `gh pr list` for existing PR check. PR title and body are redacted before creation. `link_branch_to_issue()` uses the GitHub GraphQL API (`createLinkedBranch` mutation) — fetches the issue `node_id` via REST, then POSTs to `/graphql`. Handles "already exists" errors as idempotent no-ops. Raises `MissingScopeError` on permission failures. `get_ci_status()` combines check-runs (`GET /commits/{sha}/check-runs`) and the legacy combined status (`GET /commits/{sha}/status`): any failure/cancelled/timed_out/action_required conclusion wins, else any non-completed run is `pending`, else `success` if at least one check passed, else `none`. `normalize_comment_body()` is identity (GitHub comments arrive clean). `commit_url()` / `branch_url()` build the `github.com` links; `worktree_path_parts()` is `(owner, repo)`.

## Azure Implementation (`providers/azure/`)

- **`tracker.py:AzureTracker`** — WIQL for discovery, batch API for expand (chunked at 100 ids/request, then merged, de-duped, and sorted by id — `list-work-items.md` Common Pitfalls #3), tag-based label mirror (semicolons in `System.Tags`). Normalizes `author_login` same way as GitHub. `state` maps `System.State`: `Closed`/`Done`/`Removed` → `"closed"`, otherwise `"open"`. HTML stripping via `_StripHTML` parser preserves `<AUTOSWE_*>` tags. All outbound comment bodies are redacted via `redact_outbound()`. `normalize_comment_body()` is where the provider-specific read-path cleanup lives: HTML/entity unescaping + div unwrapping + re-appending the bot marker on bot comments.
- **`vcs.py:AzureVCS`** — Azure Repos REST API for clone URL, PR creation, PR discovery. PAT embedded in HTTPS URL. PR title and body are redacted before creation. `link_branch_to_issue()` is a documented no-op (Azure DevOps has no equivalent feature). `get_ci_status()` queries the most recent Azure Pipelines build for the branch (`GET .../_apis/build/builds?branchName=...`); `notStarted`/`inProgress` → `pending`, `failed`/`canceled` → `failure`, `succeeded`/`partiallySucceeded` → `success`, no builds → `none`. `commit_url()` / `branch_url()` build `dev.azure.com` links (URL-encoding each path segment, using the resolved repo UUID when available); `worktree_path_parts()` is `(org, project, repo)`.

Both providers own their branch convention via `VCSProvider.branch_name()` — the single source of the `autoswe/issue-{N}` name, so `ship.open_pr` and `pr_gate.preflight_pr` can no longer disagree.

## Path Redaction (`core/redact.py`)

All outbound content posted to external services (comments, PR titles, PR bodies) is passed through `redact_outbound(text)` before the API call. This is a single chokepoint that applies **both** transforms in one pass, so no future caller can bypass either:

- `redact_worktree_paths(text)` — masks the worktree root path so everything up to the leaf directory becomes `".../`
- `mask_sensitive(text)` — scrubs credential-bearing URLs (`scheme://user:secret@host`, including `https://user@host`) and known token patterns (GitHub tokens, Bearer/Basic, `?token=`/`?pat=`/etc.) that would otherwise leak from `CalledProcessError` messages and git stderr into the posted comment

The worktree path transform runs first, then `mask_sensitive`. Both are idempotent — text with no worktree paths or credentials is returned unchanged. `redact_outbound` is applied at every outbound boundary: `post_comment()`, `update_comment()`, `open_pull_request()`, and `gh_post_comment()`.
