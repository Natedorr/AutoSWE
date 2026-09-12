# Work Items ↔ Branches ↔ PRs ↔ Builds — Deep Dive (Azure DevOps)

Deep-dive grounding reference for tooling that keeps work item → branch → PR → build fully linked on Azure DevOps, and for reading build/pipeline results via REST. Companion to the GitHub equivalent ([../github-api/issue-pr-linking-and-ci.md](../github-api/issue-pr-linking-and-ci.md)). Covers the functional mechanics, the exact REST endpoints (all `api-version=7.1`), and a recommended linkage recipe.

Sources (verified 2026-09-09):
- Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/git/pull-request-work-items/list?view=azure-devops-rest-7.1
- Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/wit/work-items/update?view=azure-devops-rest-7.1
- Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/wit/work-item-relation-types/list?view=azure-devops-rest-7.1
- Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/wit/reporting-work-item-links/get?view=azure-devops-rest-7.1
- Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/build/builds/list?view=azure-devops-rest-7.1
- Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/build/builds/get?view=azure-devops-rest-7.1
- Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/pipelines/runs/list?view=azure-devops-rest-7.1
- Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/pipelines/runs/get?view=azure-devops-rest-7.1
- Source: https://learn.microsoft.com/en-us/azure/devops/boards/backlogs/connect-work-items-to-git-dev-ops?view=azure-devops
- Source: https://learn.microsoft.com/en-us/azure/devops/boards/queries/link-type-reference?view=azure-devops

All auth below is the standard `Authorization: Basic base64(:PAT)` (see [azure-devops-api-reference.md](azure-devops-api-reference.md)); curl examples use `curl -u ":$ADO_PAT"`.

---

## 1. Viewing build / pipeline results

### 1.1 How it works (UI)

- **Pipelines portal** (`/_pipelines`): one card per pipeline; the run list shows trigger (push / PR / schedule), branch, and a pass/fail badge. A single run page shows **stages → jobs → steps** with per-step status and logs; artifacts are downloadable from the run.
- **Build summary page**: besides stages/jobs it shows **Associated work items** — work items linked to the Git commits this build integrated. This is the surface that proves "which ticket does this build cover".
- **Pull request page**: CI policies run as PR validation; the PR shows build results for its head ref and blocks merge on failure (when required).
- **Work item "Development" control**: the reverse direction — a work item shows its linked branches, commits, PRs, and builds in one place.

### 1.2 Two API families: Build service vs Pipelines service

Azure DevOps has **two parallel REST families** for build results. Classic (v1) pipelines live under the **Build** service; YAML pipelines additionally expose a slimmer **Pipelines** service. Both work for YAML pipelines today; the Build service is the superset (richer filters, logs, artifacts).

Build service (classic + YAML):

| Method | Path | Key params | Key response fields |
|---|---|---|---|
| GET | `/{org}/{project}/_apis/build/builds` | `branchName`, `definitions`, `reasonFilter`, `statusFilter`, `resultFilter`, `buildNumber`, `minTime`, `maxTime`, `repositoryId`, `maxBuildsPerDefinition`, `queryOrder`, `$top`, `continuationToken` | `Build[]` (no envelope beyond `count`) |
| GET | `/{org}/{project}/_apis/build/builds/{buildId}` | `propertyFilters` | full `Build` object |

**Build object — the fields that matter:**

- `status`: `none`, `inProgress`, `completed`, `cancelling`, `postponed`, `notStarted`, `all` (`BuildStatus`)
- `result`: `none`, `succeeded`, `partiallySucceeded`, `failed`, `canceled` (`BuildResult`) — **the pass/fail field, only meaningful when `status=completed`**
- `sourceBranch` (e.g. `refs/heads/autoswe/issue-18`), `sourceVersion` (commit SHA) — **how you find "the build for this branch"**
- `reason`: `none`, `manual`, `individualCI`, `batchedCI`, `schedule`, `pullRequest`, `buildCompletion`, `resourceTrigger`, `userCreated`, … — **`reason=pullRequest` is how you find "the builds triggered by this PR"**
- `repository`: `id`, `name`, `type`, `defaultBranch`, `url`
- `queueTime`, `startTime`, `finishTime`, `buildNumber`, `uri`/`url` (UI link), `logs` (`id`, `url`)
- `parameters`, `triggerInfo` (source-provider info about what triggered it)

Pipelines service (YAML only):

| Method | Path | Key params | Key response fields |
|---|---|---|---|
| GET | `/{org}/{project}/_apis/pipelines/{pipelineId}/runs` | `pipelineId` only — returns **top 10000 runs**, no filters, no continuationToken in 7.1 | `Run[]` |
| GET | `/{org}/{project}/_apis/pipelines/{pipelineId}/runs/{runId}` | — | full `Run` object |

**Run object:**

- `state`: `unknown`, `inProgress`, `canceling`, `completed` (`RunState`)
- `result`: `unknown`, `succeeded`, `failed`, `canceled` (`RunResult`) — pass/fail; note there is **no `partiallySucceeded`** here (use the Build service if you need it)
- `resources.repositories`: map of `RepositoryResource` — each has `refName` (branch), `version` (SHA), `repository.type` (`azureReposGit`, `gitHub`, `gitHubEnterprise`, …) — **this is the run → branch/repo linkage**
- `pipeline`: `id`, `name`, `folder`, `revision`; plus `createdDate`, `finishedDate`, `variables`, `templateParameters`, `url`

### 1.3 Which fields tell you pass/fail

| Surface | "done?" | "passed?" |
|---|---|---|
| Build (classic + YAML) | `status == "completed"` | `result == "succeeded"` |
| YAML run (Pipelines service) | `state == "completed"` | `result == "succeeded"` |

Gate rules of thumb:

- `result == "partiallySucceeded"` = compilation succeeded but downstream steps (usually tests) failed → **treat as failure**.
- `reason == "pullRequest"` → the build was queued by a PR (this is the "CI on my PR" signal).
- `reason == "individualCI"` / `batchedCI` → push-triggered build on a branch.
- To find the build for a PR's head branch: `GET /_apis/build/builds?branchName=refs/heads/<branch>&reasonFilter=pullRequest&$top=1` — or filter by `statusFilter=completed` and check `sourceVersion` against the PR's `lastMergeSourceCommit`.

### 1.4 Related PR-side endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/{org}/{project}/_apis/git/repositories/{repo}/pullRequests/{prId}/status` | PR merge status: `isMergeSourceAhead`, `isTargetBranchAhead`, `isInSync`, `mergeStatus` (`notApplicable` / `succeeded` / `failed` / `conflicts` / `queued`), `mergeId` after merge |
| GET | `/{org}/{project}/_apis/git/repositories/{repo}/pullRequests/{prId}/statuses` | Custom PR statuses (check-style, see [list-pull-request-statuses.md](list-pull-request-statuses.md)) |
| POST | same path | Set a custom PR status (see [create-pull-request-status.md](create-pull-request-status.md)) |

### 1.5 curl examples (read-only)

```bash
# All PR-triggered builds for a branch (find "the CI for this PR")
curl -u ":$ADO_PAT" \
  "https://dev.azure.com/{org}/{project}/_apis/build/builds?branchName=refs/heads/autoswe/issue-18&reasonFilter=pullRequest&$top=5&api-version=7.1"

# Latest completed build for a branch
curl -u ":$ADO_PAT" \
  "https://dev.azure.com/{org}/{project}/_apis/build/builds?branchName=refs/heads/main&statusFilter=completed&queryOrder=queueTimeDescending&$top=1&api-version=7.1"

# One build in full (check status/result/sourceVersion)
curl -u ":$ADO_PAT" \
  "https://dev.azure.com/{org}/{project}/_apis/build/builds/4521?api-version=7.1"

# YAML pipeline runs (pipelineId from the pipeline's URL or definition)
curl -u ":$ADO_PAT" \
  "https://dev.azure.com/{org}/{project}/_apis/pipelines/3/runs?api-version=7.1"
curl -u ":$ADO_PAT" \
  "https://dev.azure.com/{org}/{project}/_apis/pipelines/3/runs/987?api-version=7.1"

# PR merge state (conflicts / ahead / in-sync)
curl -u ":$ADO_PAT" \
  "https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repo}/pullRequests/42/status?api-version=7.1"
```

---

## 2. How work items get tied to branches and PRs

**Azure DevOps has no single bidirectional link object either** — but unlike GitHub, it has **first-class, platform-managed development links**. The "Development" control on the work item form aggregates several distinct link types. There is no REST object called "development links"; you assemble them from the endpoints below.

### 2.1 Automatic linking triggers

Per the official docs ("Drive Git development from work items"), development links appear on a work item when:

1. **A branch, commit, or pull request is created from the work item** (Development control / Actions → New branch / New pull request). Creating a branch from a work item links them **automatically**; a PR opened from that branch carries the association.
2. **The work item ID is referenced in a commit, pull request, or other Git/TFVC operation** — e.g. a commit message containing `#1234` (the ID, with or without `refs/heads`-style prefixes — the platform parses work-item-number references), or a PR description listing the work item.
3. **A link is added manually** from the Development section, the Links tab, or via the API (section 4).

**Supported artifact link types:** `Branch`, `Build`, `Changeset`, `Commit`, `Found in build`, `Integrated in build`, `Pull Request`, `Versioned Item`. (`Integrated in build` also works for GitHub repos with YAML pipelines.)

### 2.2 Per-artifact mechanics

**Branch → work item**

- The ONLY platform-managed auto-link for branches is "branch created from the work item". A branch named `autoswe/issue-1234` that is pushed some other way gets **no automatic link** — the platform does not parse branch names (same as GitHub).
- There is **no REST endpoint that links a branch to a work item** in either direction. Tooling must (a) create the branch through the work item's URL/flow when possible, or (b) enforce a naming convention and keep the mapping in its own store (see recipe, step 1).

**Commit → work item**

- A commit whose message references a work item ID gets a `Commit` link to that work item automatically (push to an Azure Repos Git repo). This is the equivalent of GitHub's commit cross-reference.
- No REST endpoint exists to add commit links directly; they're derived from the reference in the commit message (or `workItemRefs` at PR level).

**Pull request → work item (the one with full REST support)**

| Method | Path | Notes |
|---|---|---|
| GET | `/{org}/{project}/_apis/git/repositories/{repo}/pullRequests/{prId}/workitems` | **Read** work items associated with the PR. Returns `ResourceRef[]` — each item is `{ "id": "<workItemId as string>", "url": "https://dev.azure.com/{org}/_apis/wit/workItems/{id}" }`. Note the lowercase `workitems` path segment. Available since 4.1, current through 7.2. Scope: `vso.code` (read). |
| POST | `/{org}/{project}/_apis/git/repositories/{repo}/pullRequests` | **Create** PR with links via `workItemRefs: [{ "id": 1234 }]` in the body (see [create-pull-request.md](create-pull-request.md)) |
| PUT/PATCH | `/{org}/{project}/_apis/git/repositories/{repo}/pullRequests/{prId}` | **Update** PR with the same `workItemRefs` field (see [update-pull-request.md](update-pull-request.md)) |
| GET | `/{org}/{project}/_apis/git/repositories/{repo}/pullRequests/{prId}?include=workItemRefs` | Alternative read path via the PR object (see [get-pull-request.md](get-pull-request.md)) |

**There is no POST/DELETE on the `.../pullRequests/{prId}/workitems` endpoint** — the work-items association is read-only there. To add or remove links after creation, re-PUT the PR with the full desired `workItemRefs` array (it's a replace-semantics field on update).

**`transitionWorkItems`** (create/update PR body field, default `true`): when the PR's status changes, linked work items are transitioned to the corresponding state (e.g. PR becomes `active` → work item moves to `Active` in Agile). This is a *lifecycle nudge*, not a completion mechanism — merging the PR does **not** complete the work item (section 3).

### 2.3 Generic work item relation APIs (the "link engine")

Everything else — hyperlinks, work-item-to-work-item links, custom relation types — goes through the work item's `relations` array using JSON Patch:

| Method | Path | Purpose |
|---|---|---|
| PATCH | `/{org}/{project}/_apis/wit/workitems/{id}` | Add/remove/update relations and fields. Body: JSON Patch array, `Content-Type: application/json-patch+json` (see [update-work-item.md](update-work-item.md)) |
| GET | `/{org}/{project}/_apis/wit/workitems/{id}?$expand=relations` | Read a work item with its relations included (`$expand`: `None`, `Relations`, `Fields`, `Links`, `All`) |
| GET | `/{org}/_apis/wit/workItemRelationTypes` | List the 18 relation types with `referenceName` + attributes (`usage`, `topology`, `directional`, `acyclic`, `singleTarget`, `oppositeEndReferenceName`) |
| GET | `/{org}/{project}/_apis/wit/reporting/workitemlinks` | Enumerate links across work items (reporting). Params: `linkTypes`, `types`, `continuationToken`, `startDateTime`, `$top`. Org-level scope; this is how tooling lists "all links of type X" |

**Add a link** (JSON Patch, `op: add` on `/relations/-`):

```bash
# Hyperlink (any URL — e.g. merge-commit URL or a GitHub PR)
curl -u ":$ADO_PAT" -X PATCH \
  "https://dev.azure.com/{org}/{project}/_apis/wit/workitems/1234?api-version=7.1" \
  -H "Content-Type: application/json-patch+json" \
  -d '[
    { "op": "test", "path": "/rev", "value": 7 },
    { "op": "add", "path": "/relations/-",
      "value": { "rel": "Hyperlink",
                 "url": "https://dev.azure.com/{org}/{project}/_git/{repo}/pullRequest/42" } }
  ]'

# Work item → work item (Related; note the full relation reference name)
# { "op": "add", "path": "/relations/-",
#   "value": { "rel": "System.LinkTypes.Related",
#              "url": "https://dev.azure.com/{org}/_apis/wit/workItems/5678",
#              "attributes": { "comment": "duplicate of" } } }
```

Notes:

- `rel` values: `Hyperlink` for URLs; for work-item links use the **reference name** from the relation-types list (e.g. `System.LinkTypes.Related`, `System.LinkTypes.Dependency` for Successor/Predecessor, `Microsoft.VSTS.Common.Affects-Forward`, `Microsoft.VSTS.Common.TestedBy-Forward`). The docs examples show both `System.LinkTypes.Related` and the `-forward` spelling (`System.LinkTypes.Dependency-forward`) accepted — the canonical forms are what `workItemRelationTypes` returns, so query that endpoint rather than hardcoding.
- Pairing a `test` on `/rev` gives optimistic concurrency — the PATCH fails cleanly if the item changed under you.
- Removing a relation: `op: remove` on `/relations/{index}` (find the index via a GET with `$expand=relations` first).

### 2.4 Key relation types (verified from `workItemRelationTypes` + link-type reference)

| Reference name | UI name | Topology | Use |
|---|---|---|---|
| `System.LinkTypes.Hierarchy-Forward` / `-Reverse` | Child / Parent | Tree | One parent, many children; Excel bulk-edit same-project only |
| `System.LinkTypes.Related` | Related | Network | Nondirectional same-level links |
| `System.LinkTypes.Dependency` | Successor / Predecessor | Dependency | Ordering; circular refs rejected |
| `System.LinkTypes.Duplicate-Forward` / `-Reverse` | Duplicate / Duplicate of | Tree | Dup tracking; one Duplicate per item |
| `Microsoft.VSTS.Common.Affects-Forward` / `-Reverse` | Affects / Affected by | Dependency | Change requests ↔ requirements |
| `Microsoft.VSTS.Common.TestedBy-Forward` / `-Reverse` | Tested by / Tests | Dependency | Test cases ↔ work items |
| `Hyperlink` | (UI: hyperlink) | Network (counted) | Any URL, incl. network shares |

Cross-service: a **GitHub link type** connects work items to GitHub commits/issues/PRs when the org has a GitHub connection — a separate mechanism from Azure Repos auto-linking.

---

## 3. How a PR merge auto-updates work items (TL;DR: it doesn't close them)

**The single biggest difference from GitHub: Azure DevOps has no closing-keyword mechanic and does NOT auto-complete work items on merge.** There is no API parameter, no commit-message convention, and no PR-description syntax that moves a work item to a done state when a PR merges. The merge endpoint (see [merge-pull-request.md](merge-pull-request.md)) takes `mergeStrategy`, `deleteSourceBranch`, `mergeCommitMessage`, `completedBy`, `keepExistingFiles` — nothing about work items.

### 3.1 What actually happens on merge

1. `PATCH .../pullRequests/{prId}/complete` lands the merge commit on the target branch.
2. The **work item keeps its current state** (e.g. still `Active`). No state transition, no "closed" flag — work items don't even have a GitHub-style `state`; `System.State` is a per-process value (`New`/`Active`/`Resolved`/`Closed` in Agile, etc.).
3. The work item's **Development** section gains/retains the `Pull Request` link, and after the build integrates the commit, an **`Integrated in build`** link (plus `Found in build` for test runs) appears on the work item.
4. The build's summary page shows the work item under **Associated work items** — derived from the commit↔work-item links, not from the PR.

So after a merge: linked ✅, done ❌. Completion is always an explicit act.

### 3.2 What the platform DOES do automatically (and what it doesn't)

| Event | Automatic? |
|---|---|
| PR created → linked WI transitions to `Active` | ✅ when `transitionWorkItems=true` (default) |
| PR created → `Pull Request` development link on WIs | ✅ |
| Commit message references WI ID → `Commit` link | ✅ (Azure Repos) |
| Branch created from WI → `Branch` link | ✅ |
| PR merged → WI state → done/closed | ❌ **Never.** Manual only. |
| PR merged → closing-keyword scan of PR body/commit messages | ❌ The mechanic doesn't exist |
| Build completes → `Integrated in build` link on WIs (via commits) | ✅ |
| Build result reflected as check on the PR | ✅ as PR policy / build validation |

### 3.3 How to complete work items (the explicit paths)

1. **API (what AutoSWE should do):** JSON Patch the state field directly.

```bash
# Move WI to the done-state for its process (Agile example;
# use the correct state name for the team's process — CMMI: "Closed")
curl -u ":$ADO_PAT" -X PATCH \
  "https://dev.azure.com/{org}/{project}/_apis/wit/workitems/1234?api-version=7.1" \
  -H "Content-Type: application/json-patch+json" \
  -d '[
    { "op": "test", "path": "/rev", "value": 7 },
    { "op": "add", "path": "/fields/System.State", "value": "Resolved" },
    { "op": "add", "path": "/fields/System.Reason", "value": "Done" }
  ]'
```

   Caveat: state names and required transitions are **process-dependent** (Agile vs CMMI vs Scrum variants) and some processes require passing through intermediate states or setting `System.Reason`. Query the work item type's allowed transitions (`GET /_apis/wit/processes/{processId}/workItemTypes/{type}`) before hardcoding; use `bypassRules=true` only as a last resort.

2. **Azure Pipelines integration:** a YAML pipeline can update work items as part of the run — the official mechanism is "Configure pipelines to support work tracking" (source link above), e.g. the `updateWorkItems` setting in a `publish`/`test` step, which drives work items based on run results. This is the closest built-in analogue to GitHub auto-close, but it's opt-in pipeline configuration, not a merge-time default.

3. **UI:** manual state change on the work item or board drag.

---

## 4. Recommended linkage recipe (for tooling)

Steps to create a fully linked fix on Azure DevOps, mirroring the GitHub recipe.

**Step 1 — Branch naming convention (tooling-enforced, NOT platform-enforced).**
Create the work branch as `autoswe/wi-{workItemId}`. Azure DevOps does not read this name — *your* code does. Keep the regex simple: `^autoswe/wi-(\d+)$`. This is the recovery path if the PR link ever goes missing. (Alternative: create the branch through the work item's Development control so the `Branch` link is platform-managed — only possible via UI/portal URL flows, not a clean REST call.)

**Step 2 — Reference the work item in every commit message.**

```
#1234 fix: handle empty roster in align_team
```

Prefixing `#<workItemId>` gets the commit an automatic `Commit` development link on the work item — this is also what makes the build's "Associated work items" section populated.

**Step 3 — Create the PR with `workItemRefs`.**

```bash
curl -u ":$ADO_PAT" -X POST \
  "https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repo}/pullRequests?api-version=7.1" \
  -H "Content-Type: application/json" \
  -d '{
    "sourceRefName": "refs/heads/autoswe/wi-1234",
    "targetRefName": "refs/heads/main",
    "title": "Fix align_team empty roster",
    "description": "Fixes work item #1234",
    "workItemRefs": [ { "id": 1234 } ]
  }'
```

Notes:

- `workItemRefs` is the write path for PR→WI links (create or update). The description mentioning `#1234` is belt-and-suspenders — the platform also parses references in PR text.
- `transitionWorkItems` defaults to `true`: the WI transitions to `Active` on PR creation. Set it `false` if the automation owns state transitions.

**Step 4 — Verify the link exists, before merging.**

```bash
# PR side: must contain { "id": "1234", "url": ".../wit/workItems/1234" }
curl -u ":$ADO_PAT" \
  "https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repo}/pullRequests/42/workitems?api-version=7.1"

# Work item side (the relation appears on the WI as a Pull Request development link)
curl -u ":$ADO_PAT" \
  "https://dev.azure.com/{org}/{project}/_apis/wit/workitems/1234?api-version=7.1&$expand=relations"
```

If empty, re-PUT the PR with `workItemRefs` (replace semantics) and re-check.

**Step 5 — Wait for CI.**

```bash
# Poll until a PR-triggered build for the head branch completes
curl -u ":$ADO_PAT" \
  "https://dev.azure.com/{org}/{project}/_apis/build/builds?branchName=refs/heads/autoswe/wi-1234&reasonFilter=pullRequest&statusFilter=completed&$top=1&api-version=7.1"
```

Require `status=completed` **and** `result=succeeded` (`partiallySucceeded` = tests failed → treat as failure). Confirm `sourceVersion` is the PR's current head commit before trusting it.

**Step 6 — Merge.**

```bash
curl -u ":$ADO_PAT" -X PATCH \
  "https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repo}/pullRequests/42/complete?api-version=7.1" \
  -H "Content-Type: application/json" \
  -d '{ "mergeStrategy": "squash", "deleteSourceBranch": true }'
```

**Step 7 — Complete the work item explicitly (ADO won't).**

```bash
# 1) set state (process-appropriate; Agile example)
PATCH /_apis/wit/workitems/1234  ->  [ { op:add, path:/fields/System.State, value:"Resolved" }, { op:add, path:/fields/System.Reason, value:"Done" } ]

# 2) optional: pin the merge back-reference as a Hyperlink
PATCH /_apis/wit/workitems/1234  ->  [ { op:add, path:/relations/-, value:{ rel:"Hyperlink", url:"https://dev.azure.com/{org}/{project}/_git/{repo}/pullRequest/42" } } ]
```

**Step 8 — Verify post-merge.**

```bash
GET /_apis/wit/workitems/1234?api-version=7.1
  -> fields["System.State"] == "Resolved"
     relations include the Pull Request link and (after build integration) Integrated in build
```

**Failure mode: link missing at merge time.** The PR merges fine but the work item stays unlinked and open. Recovery order: (a) re-PUT the PR with `workItemRefs` (development links survive on closed PRs), (b) fall back to branch-name parsing (`^autoswe/wi-(\d+)$`) to identify the work item, (c) PATCH the state change from step 7. Prefer (c) over leaving the work item dangling — there is no auto-close to save you.

---

## Caveats & gotchas

1. **No auto-close, ever.** Merging a PR (UI or API) does not change work item state. Any tooling ported from GitHub's closing-keyword model must explicitly PATCH `System.State` after merge (recipe step 7).
2. **The PR work-items endpoint is read-only.** `GET .../pullRequests/{id}/workitems` (lowercase `workitems`) exists; there is no POST/PATCH/DELETE variant in the 7.1 docs. Writes go through `workItemRefs` on the PR create/update body.
3. **`workItemRefs` on update is replace-semantics** — send the complete desired list, not a delta.
4. **The List response returns `ResourceRef[]` with `id` as a *string*** (`"1234"`, not `1234`) plus a `url` ending in `/wit/workItems/1234`. Parse accordingly.
5. **No REST branch↔work-item link API.** The `Branch` development link only exists when the branch is created from the work item (UI flow). Naming conventions are tooling-side — document them wherever the parser lives.
6. **Auto commit-linking requires the reference in the commit message** (Azure Repos). Squash-merging preserves it if the squash message keeps `#<id>`; a generated squash message that drops it loses future commit→WI association (existing links are not retroactively removed).
7. **`partiallySucceeded` is a failure for gating purposes** (build compiled, tests failed). A gate that only checks `result == "succeeded"` handles this correctly; one that checks "not failed" does not.
8. **Two build API families.** YAML pipelines are visible under both `/_apis/build/builds` (rich) and `/_apis/pipelines/{id}/runs` (slim). The Pipelines runs list has no filter params and caps at 10000 runs in 7.1; use the Build service for anything you need to filter by branch/PR/time.
9. **Work item states are process-scoped.** `Resolved`/`Closed`/`Done` are not universal — the team's process (and its state workflow) defines valid states and transitions. Query the work item type definition before writing states; use `validateOnly=true` to dry-run a patch.
10. **JSON Patch content type is mandatory** (`application/json-patch+json`) on work item creates/updates, and `test` on `/rev` is the concurrency guard.
11. **`workItemRelationTypes` is the source of truth for `rel` names** (18 types). Don't hardcode `System.LinkTypes.*` strings across projects — query the endpoint, since custom processes can add/rename relation types.
12. **Reporting links endpoint** (`GET /_apis/wit/reporting/workitemlinks`) is the way to enumerate "all links of type X" across the project (continuation-token paginated) — useful for auditing link integrity at scale.
13. **`api-version=7.1`** throughout; the PR work-items list is supported from `4.1` through `7.2`, so it is stable, not preview.
