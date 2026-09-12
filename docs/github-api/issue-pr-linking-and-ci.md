# Issue ↔ Branch ↔ PR Linking & CI Results — Deep Dive

Deep-dive grounding reference for tooling that keeps issue → branch → PR → build fully linked on GitHub. Covers how the features work functionally, the exact REST/GraphQL endpoints, and a recommended linkage recipe.

Sources (verified 2026-09-09):
- Source: https://docs.github.com/en/rest/actions/workflow-runs
- Source: https://docs.github.com/en/rest/actions/artifacts
- Source: https://docs.github.com/en/rest/checks/runs
- Source: https://docs.github.com/en/rest/checks/suites
- Source: https://docs.github.com/en/rest/commits/statuses
- Source: https://docs.github.com/en/rest/issues/timeline
- Source: https://docs.github.com/en/rest/issues/issues
- Source: https://docs.github.com/en/rest/pulls/pulls
- Source: https://docs.github.com/en/enterprise/2.16/user/github/managing-your-work-on-github/closing-issues-using-keywords
- Source: https://docs.github.com/en/graphql/overview

All endpoint shapes below were verified live on 2026-09-09 against `Natedorr/FantasyFootballAgent` (read-only `gh api` / GraphQL) in addition to the official docs.

---

## 1. Viewing build / CI results

### 1.1 How it works (UI)

- **Actions tab** → run list: one row per workflow run, with the triggering branch/PR, event, status badge (queued / in progress / success / failure / cancelled), and duration.
- **Single run view** (`/actions/runs/{run_id}`): the graph of **jobs**; each job shows its **steps** with per-step status and logs; the **artifacts** tab lists uploadable files.
- **PR "Checks" section**: the PR page groups every check run + commit status on each head commit, with a pass/fail rollup and a "re-run" menu. This is the surface that blocks merge when required checks fail.
- **Commit page checks dropdown**: every commit shows its check runs/statuses; clicking one opens the job's run view.

### 1.2 REST endpoints for reading build results

Workflow runs:

| Method | Path | Key params | Key response fields |
|---|---|---|---|
| GET | `/repos/{owner}/{repo}/actions/runs` | `branch`, `event`, `status`, `conclusion`, `head_sha`, `check_suite_id`, `actor`, `created` (search syntax), `exclude_pull_requests`, `per_page`, `page` | `total_count`, `workflow_runs[]` |
| GET | `/repos/{owner}/{repo}/actions/runs/{run_id}` | — | full run object below |
| GET | `/repos/{owner}/{repo}/actions/runs/{run_id}/jobs` | `filter` (latest), `per_page`, `page` | `total_count`, `jobs[]` |
| GET | `/repos/{owner}/{repo}/actions/jobs/{job_id}` | — | job + `steps[]` + `check_run_url` |
| GET | `/repos/{owner}/{repo}/actions/jobs/{job_id}/logs` | — | redirect (302) to a signed log URL; follow with `-L` |
| GET | `/repos/{owner}/{repo}/actions/runs/{run_id}/logs` | — | redirect to zipped logs of the whole run |

**Workflow run object — the fields that matter:**

- `status`: `queued`, `in_progress`, `completed` (Actions also uses `requested`, `waiting`, `pending`, `action_required` for non-Actions apps)
- `conclusion`: `success`, `failure`, `neutral`, `cancelled`, `skipped`, `timed_out`, `stale` — only present when `status=completed`; **this is the pass/fail field**
- `event`: `push`, `pull_request`, `schedule`, `workflow_dispatch`, …
- `head_branch`, `head_sha`: the branch and commit this run built — **this is how you find "the build for this PR branch"** (query `?head_sha=` or `?branch=`)
- `pull_requests[]`: `id`, `number`, `head.ref`, `head.sha`, `base.ref`, `base.sha` — **the run → PR linkage** (empty array for plain pushes)
- `check_suite_id`, `check_suite_url`, `html_url`, `jobs_url`, `logs_url`, `artifacts_url` — follow these URLs instead of reconstructing paths
- `run_number`, `run_attempt`: the same `run_id` can have multiple attempts; `?filter=latest` on the jobs list returns the current attempt's jobs

Artifacts:

| Method | Path | Notes |
|---|---|---|
| GET | `/repos/{owner}/{repo}/actions/artifacts` | repo-wide; filter `name` |
| GET | `/repos/{owner}/{repo}/actions/runs/{run_id}/artifacts` | per run |
| GET | `/repos/{owner}/{repo}/actions/artifacts/{artifact_id}` | metadata: `name`, `size_in_bytes`, `archive_download_url`, `expires_at` (artifacts auto-expire; default 90 days) |
| GET | `/repos/{owner}/{repo}/actions/artifacts/{artifact_id}/{archive_format}` | download; `archive_format` is only ever `zip` in practice |

Check suites / check runs (richer than commit statuses; GitHub Apps and Actions use these):

| Method | Path | Key params / fields |
|---|---|---|
| GET | `/repos/{owner}/{repo}/commits/{ref}/check-suites` | `ref` = SHA / branch / tag. Returns `id`, `head_sha`, `head_branch`, `status`, `conclusion`, `app.slug`, `pull_requests[]` |
| GET | `/repos/{owner}/{repo}/check-suites/{check_suite_id}` | single suite |
| GET | `/repos/{owner}/{repo}/commits/{ref}/check-runs` | `check_name`, `filter` (`latest`, `all`, `newest`); returns `total_count`, `check_runs[]` |
| GET | `/repos/{owner}/{repo}/check-runs/{check_run_id}` | single run; **includes `pull_requests[]`** — this is how a check is tied back to the PR |

**Check run object — pass/fail fields:**

- `status`: `queued`, `in_progress`, `completed` (also `waiting`, `requested`, `pending`)
- `conclusion`: `success`, `failure`, `neutral`, `cancelled`, `skipped`, `timed_out`, `action_required`, `null`
- `pull_requests[]`: `id`, `number`, `head.ref/sha`, `base.ref/sha` (see fork caveat below)
- `output`: `title`, `summary`, `text`, `annotations_count`, `annotations_url`

Commit statuses (legacy API — third-party CI, codecov, etc.):

| Method | Path | Key fields |
|---|---|---|
| GET | `/repos/{owner}/{repo}/commits/{sha}/status` | **combined** status: `state` = `success` / `pending` / `failure`, plus `statuses[]` (each: `context`, `state`, `description`, `target_url`) |
| GET | `/repos/{owner}/{repo}/commits/{ref}/statuses` | individual statuses, reverse chronological; each has `context` (e.g. `ci/test`) |

### 1.3 Which fields tell you pass/fail

| Surface | "done?" | "passed?" |
|---|---|---|
| Workflow run | `status == "completed"` | `conclusion == "success"` |
| Check run | `status == "completed"` | `conclusion == "success"` |
| Check suite | `status == "completed"` | `conclusion == "success"` |
| Combined status | `state != "pending"` | `state == "success"` |
| Single commit status | — | `state == "success"` (per `context`) |

A PR's checks rollup = every check run + commit status on every head commit; one `failure` conclusion anywhere fails the rollup.

### 1.4 GraphQL equivalents

```graphql
{
  repository(owner: "Natedorr", name: "FantasyFootballAgent") {
    # by head SHA — "the build for this PR's tip commit"
    commit(oid: "f2ebbc…6761") {
      statusCheckRollup {
        states          # e.g. ["SUCCESS"] or ["FAILURE", "IN_PROGRESS"]
        contexts(first: 10) {
          nodes {
            ... on CheckRun {
              name
              status
              conclusion
              pullRequests(first: 3) { nodes { number } }   # check → PR link
            }
            ... on Status { context state }
          }
        }
      }
    }
    defaultBranchRef {
      target {
        history(first: 1) {
          nodes {
            checkSuites(first: 5) {
              nodes { id status conclusion pullRequests(first: 1) { nodes { number } } }
            }
          }
        }
      }
    }
  }
}
```

Notes: `Commit.statusCheckRollup` is the GraphQL way to get the PR checks-section rollup for any ref. Workflow run objects are reachable via `Workflow` → `runs`. The REST paths in 1.2 are simpler for polling; use GraphQL when you need one round-trip for rollup + linkages.

### 1.5 curl examples (read-only)

```curl
# All builds for a branch (this is how you find "the build for this PR branch")
curl -H "Authorization: token <TOKEN>" \
  "https://api.github.com/repos/Natedorr/FantasyFootballAgent/actions/runs?branch=main&per_page=5"

# Build for the exact head SHA of a PR
curl -H "Authorization: token <TOKEN>" \
  "https://api.github.com/repos/OWNER/REPO/actions/runs?head_sha=<HEAD_SHA>"

# One run, with the PR it belongs to
curl -H "Authorization: token <TOKEN>" \
  "https://api.github.com/repos/Natedorr/FantasyFootballAgent/actions/runs/34289754468"

# Jobs + steps + per-step logs
curl -H "Authorization: token <TOKEN>" \
  "https://api.github.com/repos/Natedorr/FantasyFootballAgent/actions/runs/34289754468/jobs"
curl -L -H "Authorization: token <TOKEN>" \
  "https://api.github.com/repos/Natedorr/FantasyFootballAgent/actions/jobs/102273440811/logs"

# Artifacts for the run
curl -H "Authorization: token <TOKEN>" \
  "https://api.github.com/repos/Natedorr/FantasyFootballAgent/actions/runs/34289754468/artifacts"

# Check runs on a commit (each entry carries pull_requests[])
curl -H "Authorization: token <TOKEN>" \
  "https://api.github.com/repos/Natedorr/FantasyFootballAgent/commits/f2ebbcd72ffcbbafff09700c8b0560e57e506761/check-runs"

# Combined status for a ref
curl -H "Authorization: token <TOKEN>" \
  "https://api.github.com/repos/Natedorr/FantasyFootballAgent/commits/f2ebbcd72ffcbbafff09700c8b0560e57e506761/status"
```

---

## 2. How issues get tied to branches and PRs

**GitHub has NO bidirectional link object.** There is no API to "link issue #N to branch X" or "to PR Y" as a first-class relation. The linkage you see in the UI ("Development" section, "linked pull requests") is **derived** from a small set of mechanisms:

### 2.1 Closing keywords (the only mechanism that auto-closes)

Keywords followed by an issue number, placed in a **PR description or a commit message**, create an association. When the PR (or commit) is **merged into the default branch**, GitHub closes the referenced issue(s) automatically.

Complete keyword list (verified from official docs):

```
close   closes   closed
fix     fixes    fixed
resolve  resolves  resolved
```

Nuances:

- **Only triggers on merge into the default branch.** A commit carrying `Fixes #45` on a non-default branch does NOT close the issue — the issue shows the commit as a "referenced" link with a tooltip instead. The close happens when the merge commit lands on the default branch.
- **"Closes #N" in the PR body vs in a commit message: both work.** Either one is sufficient. (Squash-merging with a generated commit message that loses the keyword still closes if the PR body had it.)
- **Cross-repo:** `Closes otheruser/otherrepo#76` closes that issue, provided you have push access to that repo.
- **Multiple issues:** the keyword must prefix *each* reference. `Closes #34 and #23` closes only #34.
- **`Refs` / `See` / `Related` are NOT closing keywords.** Bare `#123` and `Refs #123` are cross-references only.
- A keyword with no valid issue number (e.g. `Closes #99999`) just renders as text.

### 2.2 Cross-referencing

Any mention of an issue number (`#123`) or its URL anywhere — a PR body, PR/issue comment, commit message — creates a **timeline entry on both sides** (the mentioner and the mentioned). This is the `cross-referenced` / `CrossReferencedEvent` mechanism. It creates a visible link in the UI but **no automatic state change**: the issue stays open, and the PR doesn't even show "Development" association for plain mentions… actually it does — a plain `#123` mention in the PR body is enough to make the PR appear in the issue's Development section (as "connected"), but only a closing keyword makes it *close* on merge.

### 2.3 Branch naming — NOT interpreted by GitHub

**GitHub does not parse, validate, or interpret branch names.** A branch called `fix-123`, `autoswe/issue-123`, or `issue_123` has zero special meaning to the platform:

- No API field links a branch to an issue.
- Branch protection rules match branches by pattern, but that's unrelated to issues.
- The branch ↔ issue relationship shown in any tooling is **convention, enforced by tooling** (e.g., AutoSWE names branches `autoswe/issue-N` and recovers the link by regex).

**Implication for tooling:** if you want branch↔issue recovery independent of the PR body, you must implement it yourself: name the branch with a stable pattern (recommended: `autoswe/issue-{number}`) and parse it back out (see recipe in section 4).

### 2.4 Commit references ("Development" association)

Commits on the default branch whose messages reference an issue number appear under the issue's **Development** section. This is driven by the same `referenced` timeline event. It is display-only — no state change.

### 2.5 Resulting timeline (what a correctly linked fix looks like)

Live example, `Natedorr/FantasyFootballAgent` issue #18 ← branch `autoswe/issue-18` ← PR #19 ("Fixes #18: …"):

```
connected          <- PR opened (keyword association created)
cross-referenced   <- PR body mentions issue (source: PR #19)
closed             <- PR merged into default branch; auto-closed
referenced         <- merge commit f2ebbc… references issue on main
```

---

## 3. How a PR merge auto-updates the issue

### 3.1 What happens on merge

1. The merge (via UI, `gh pr merge`, or `PUT .../pulls/{pull_number}/merge`) lands a commit on the default branch.
2. GitHub scans the PR body and commit messages for closing keywords.
3. Each matching issue:
   - transitions to `state=closed` with `state_reason=completed`,
   - gets a `closed` timeline event,
   - shows the merged PR in its **Development** section (the PR itself shows `merged=true`, `mergeCommit`).
4. Issues that were merely referenced (no keyword) get `cross-referenced` timeline events and stay open.

### 3.2 The endpoint that triggers it

| Method | Path | Body | Notes |
|---|---|---|---|
| PUT | `/repos/{owner}/{repo}/pulls/{pull_number}/merge` | `sha` (optional precondition: head must match), `merge_method` (`merge`\|`squash`\|`rebase`), `commit_message` | Returns 204 on success; **this merge is what fires the auto-close** |
| GET | `/repos/{owner}/{repo}/pulls/{pull_number}/merge` | — | mergeability check: `mergeable`, `mergeable_state` |

### 3.3 Reading the relationship after the fact

REST — issue timeline (the authoritative record of the linkage):

| Method | Path | Key params | Key event names (`event` field) |
|---|---|---|---|
| GET | `/repos/{owner}/{repo}/issues/{issue_number}/timeline` | `per_page`, `page`, `exclude` (comma-separated event names) | `connected`, `cross-referenced` (with `source.issue.number` = the PR), `closed` (with `state_reason`), `referenced` (with `commit_id`), plus `labeled`, `commented`, `milestoned`, … |

Key fields on the timeline entries:

- `cross-referenced`: `source` object = `{ issue: { number, html_url, ... } }` — the PR number; `created_at`
- `closed`: `state_reason` (`completed` or `not_planned`), `actor`
- `connected`: marks the PR being linked into Development
- `referenced`: `commit_id` — the commit that mentioned the issue on the default branch

REST — issue object itself:

```
GET /repos/{owner}/{repo}/issues/{issue_number}
```

Key fields: `state` (`open`/`closed`), `state_reason` (`completed`, `not_planned`, `reopened`, `duplicate`, `null`), `closed_at`. Note: `state_reason` is `null` on closed *PRs* even after a clean merge — the reason is only populated on plain issues.

GraphQL — the compact, join-heavy alternative:

```graphql
{
  repository(owner: "Natedorr", name: "FantasyFootballAgent") {
    pullRequest(number: 19) {
      number
      merged              # Boolean
      mergedAt
      mergeCommit { oid } # the commit that landed on main
      closingIssuesReferences(first: 5) {
        nodes { number state title }   # <- THE issue link, directly
      }
    }
    issue(number: 18) {
      number
      state
      stateReason         # COMPLETED | NOT_PLANNED | DUPLICATE | null
      timelineItems(last: 20) {
        nodes {
          ... on ConnectedEvent     { createdAt isCrossRepository }
          ... on CrossReferencedEvent { createdAt willCloseTarget source { ... on PullRequest { number merged } } }
          ... on ClosedEvent        { createdAt stateReason }
          ... on ReferencedEvent    { createdAt commit { oid } }
          ... on IssueComment       { id }   # comments surface as IssueComment, NOT a *Event type
        }
      }
    }
  }
}
```

Verified field facts (2026-09-09, via schema introspection + live queries):

- `PullRequest.closingIssuesReferences` — the direct "which issues does this PR close" link. Only present/populated for closing-keyword associations.
- The issue timeline field on GraphQL is **`Issue.timelineItems`**, *not* `issueTimelineItems` (the latter does not exist on the schema). `timelineItems` does **not** accept `sortOrder`; paginate with `first`/`last`/`before`/`after` cursors. Its `nodes` is a union — select fields inside fragments only.
- `ClosedEvent` has `stateReason` but no `closedAt` (use `createdAt`). `ConnectedEvent` has `source`/`subject` but no `connectedAt` (use `createdAt`).
- There is no `CommentEvent` type; issue comments on the timeline are `IssueComment` objects.

Manual close via API (when you want auto-close semantics without relying on keywords — e.g. the PR body got scrubbed):

| Method | Path | Body |
|---|---|---|
| PATCH | `/repos/{owner}/{repo}/issues/{issue_number}` | `state: "closed"`, `state_reason: "completed"` (or `"not_planned"`) |

This produces the same `closed` timeline event and `state_reason` as an auto-close.

### 3.4 curl examples (read-only)

```curl
# Timeline of the linkage (find "connected", "cross-referenced", "closed")
curl -H "Authorization: token <TOKEN>" \
  "https://api.github.com/repos/Natedorr/FantasyFootballAgent/issues/18/timeline"

# Issue state + reason
curl -H "Authorization: token <TOKEN>" \
  "https://api.github.com/repos/Natedorr/FantasyFootballAgent/issues/18"
```

```graphql
# GraphQL (one query, full link state) — verify via:
gh api graphql -f query='
{ viewer { repository(name: "FantasyFootballAgent") {
  pullRequest(number: 19) { number merged mergedAt mergeCommit { oid }
    closingIssuesReferences(first: 5) { nodes { number state } } }
  issue(number: 18) { number state stateReason }
} } }'
```

---

## 4. Recommended linkage recipe (for tooling)

Steps to create a fully linked, auto-closing fix. Verified end-to-end on `Natedorr/FantasyFootballAgent` (issue #18 / branch `autoswe/issue-18` / PR #19).

**Step 1 — Branch naming convention (tooling-enforced, NOT platform-enforced).**
Create the work branch as `autoswe/issue-{issue_number}` (or `fix-{issue_number}` in single-word repos). GitHub does not read this name — *your* code does. Keep the regex simple: `^autoswe/issue-(\d+)$`. This is the recovery path if the PR body keyword ever goes missing.

**Step 2 — Create the PR with the closing keyword in the body.**

```
POST /repos/{owner}/{repo}/pulls
{
  "title": "Fixes #18: <concise summary>",
  "head": "autoswe/issue-18",
  "base": "main",
  "body": "Closes #18\n\n<details of the fix>\n\nRefs autoswe/issue-18"
}
```

Rules:
- Put `Closes #N` on its **own line** in the body (one keyword before *every* number you want closed; `Fixes`/`Resolves` are equivalent to `Closes`).
- Also include `Closes #N` in the **merge commit message** (works with all three `merge_method`s if the message is preserved) — belt-and-suspenders, since squash commit titles are generated from the PR title by default.
- A plain `Refs #N` gives the Development-section link **without** auto-close — use it for related-but-not-fixing work.

**Step 3 — Verify the link exists, before merging.**

```graphql
{ repository(owner: "OWNER", name: "REPO") {
  pullRequest(number: <PR>) {
    number
    closingIssuesReferences(first: 5) { nodes { number state } }   # must contain issue N, state OPEN
  }
}
```

REST fallback: `GET /repos/{owner}/{repo}/issues/{issue_number}/timeline` and look for a `cross-referenced` entry whose `source.issue.number == PR`, plus a `connected` entry. If `closingIssuesReferences` is empty, the keyword didn't register — fix the PR body (`PATCH /pulls/{pull_number}` with `body`) and re-check.

**Step 4 — Wait for CI.** Poll `GET /repos/{owner}/{repo}/actions/runs?head_sha=<head_sha>&per_page=1` (or the checks endpoints in section 1) until every run has `status=completed`; require `conclusion=success`.

**Step 5 — Merge (fires the auto-close).**

```
PUT /repos/{owner}/{repo}/pulls/{pull_number}/merge
{ "merge_method": "squash", "commit_message": "Fixes #18: <summary>" }
```

**Step 6 — Verify the close, post-merge.**

```
GET /repos/{owner}/{repo}/issues/{issue_number}   -> state == "closed", state_reason == "completed"
```

or GraphQL `issue(number: N) { state stateReason }` → `CLOSED` / `COMPLETED`.

**Failure mode: keyword missed in both body and commit message.** The PR still shows in Development (plain cross-reference), but the issue stays open. Recovery: (a) `PATCH /issues/{N}` with `state=closed, state_reason=completed`, or (b) fall back to branch-name parsing (`autoswe/issue-(\d+)`) to identify the issue, then do (a). Always prefer (a) over leaving the issue dangling.

---

## Caveats & gotchas (observed on this host, 2026-09-09)

1. **Checks API 403 with a classic PAT on private repos:** `GET /commits/{ref}/check-runs` and `check-suites` returned `403 "Resource not accessible by personal access token"` on a private repo from this host's `gh`-authed token, while the Actions runs endpoints worked fine. The Checks API reads need `checks:read` (GitHub App) or the PAT to have proper repo permission for that repo; if you hit this, fall back to `GET /actions/runs?head_sha=...` which carries `check_suite_id` and `pull_requests` anyway.
2. **Forks break the check→PR link:** per official docs, the Checks API only detects pushes in the repo where the check was created; pushes to a forked repo produce an **empty `pull_requests` array** on check runs/suites. For cross-fork PRs, resolve the PR yourself from `head.repo`/`head.ref`.
3. **GraphQL naming traps:** `Issue.timelineItems` (not `issueTimelineItems`); no `sortOrder` argument; `nodes` is a union so every selection must be inside a fragment; no `CommentEvent` type (comments are `IssueComment`).
4. **Keywords only fire on merge into the default branch** — a `Fixes #N` commit on a feature branch only shows a "referenced" tooltip, not a close.
5. **Artifacts expire** (`expires_at`, default 90 days) — persist anything you need before then.
6. **`state_reason` is `null` on closed PRs** — only plain issues carry `completed`/`not_planned`/`duplicate`. Don't use PR `state_reason` as a signal.
7. **Branch names are inert** — there is no branch↔issue API. The `autoswe/issue-N` convention is purely tooling-side; document it wherever the parser lives.
8. **`GET /actions/runs` caps filtered results at 1,000** when using `branch`/`head_sha`/`event`/`status`/`created` filters.
