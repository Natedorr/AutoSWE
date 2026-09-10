# AutoSWE Azure DevOps Provider — Deep Code Review (Task 2 of 2)

Scope: the Azure DevOps provider (`autoswe/providers/azure/`) plus the shared
interface files (`providers/base.py`, `providers/adapter.py`,
`providers/factory.py`) reviewed **from the Azure side**. No files under
`autoswe/providers/github/` were modified; findings that also apply to the
GitHub provider are cross-referenced to `docs/autoswe/review-github-provider.md`
but the shared code is cited here independently.

Companion docs consulted: `docs/azure-devops-api/workitem-pr-linking-and-builds.md`
(ADO endpoint deep-dive), `docs/autoswe/review-github-provider.md` (format
parity + shared findings).

## 1. Architecture Map

### 1.1 Azure provider layer

| File | Role | Key symbols |
|---|---|---|
| `autoswe/providers/azure/api.py` | Thin ADO REST client | `_ado_request` (retry loop, api.py:69–124), `ado_get/ado_post/ado_patch/ado_patch_json` (:126–156), `ado_get_paged` continuationToken paging (:158–171), `_ado_api_version` (:33), `_normalize_azure_parts` (:41) |
| `autoswe/providers/azure/tracker.py` | `AzureTracker` — IssueTracker impl | `_is_bot_comment` (:36), `_StripHTML` (:50), `_strip_html` (:77), `list_open_issues` (WIQL, :133), `fetch_issue` (:182), `fetch_comments` (:191), `authenticated_user` (:267), `post_comment` (:309), `set_status` (tag read-modify-write, :352), `_to_normalized` (:430) |
| `autoswe/providers/azure/vcs.py` | `AzureVCS` — VCSProvider impl | `resolve_repo_id` (:61), `clone_url` (PAT-embedded, :146), `branch_name` (:153), `find_existing_pr` (:157), `open_pull_request` (:175), `link_branch_to_issue` (no-op, :201), `get_ci_status` (builds endpoint, :209) |
| `autoswe/providers/adapter.py` (shared) | Single `read_api` / `apply_effect` pair for **all** providers | comment-body normalisation delegated to `tracker.normalize_comment_body` (adapter.py:1–8 docstring) |
| `autoswe/providers/factory.py` (shared) | `TRACKERS` / `VCSS` registries; single construction point | — |

Auth: `api.py:79` — `base64.b64encode((":" + pat).encode())` basic auth; PAT
carried in every request header, and — the big Azure-specific difference —
**embedded in `clone_url()`** (vcs.py:146) so `git clone` works with zero
extra credential plumbing.

### 1.2 Orchestration layers consuming the providers

Same shared layers as the GitHub review (`docs/autoswe/review-github-provider.md` §1.2):
`orch/loop.py` (`_single_poll`, loop.py:729; `_MIRROR_STATUSES`, loop.py:50;
queue write point `save_queue` in `_drain_poll`), `orch/decide.py`
(author allowlist check against normalized + raw login, decide.py:73–75),
`orch/emit.py` (`create_pr` effect), `orch/run.py` (explicit `/pr` →
`ship.open_pr`), `vcs/pr_gate.py` (CI gate, pr_gate.py:61), `vcs/ship.py`
(`AUTOSWE_BOT_FOOTER`), `vcs/worktree.py` (`commit_and_push`, worktree.py:532).

### 1.3 Data flow for an Azure task

```
poll() → AzureTracker.list_open_issues (WIQL)
       → fetch_issue (work item, fields incl. System.ChangedDate)
       → fetch_comments (format=Markdown, api-version=7.1-preview)
             author normalization: BOT / OWNER / raw uniqueName (email)
       → decide() (slash command, allowlist incl. raw-login fallback)
emit → Effect → adapter.apply_effect → tracker.post_comment / set_status / vcs.open_pull_request
ship → pr_gate.preflight_pr → AzureVCS.get_ci_status (latest build for branch)
```

Status is carried as a **work item tag** (`autoswe:***`), not a state field —
`set_status` (:352) is a GET tags → strip `autoswe:*` → JSON-Patch
`remove`+`add` on `/fields/System.Tags` (two-op patch; ADO's `add` on
`System.Tags` is additive server-side, so the `remove` is what makes it a
true replace — issue #235, documented in the docstring).

## 2. Interface Integrity (Q2)

**Verdict: the shared Protocol/facade is intact on the Azure side.**

- `adapter.apply_effect` is the single `Effect`→provider seam for both
  providers (adapter.py docstring lines 1–8; `Effect.kind` values
  `post_comment | update_comment | set_status | patch_queue | assign |
  create_pr | noop` in `orch/types.py`). `grep` for direct
  `tracker.post_comment|vcs.open_pull_request` call sites outside
  adapter/ship finds none — Azure writes flow through the same
  `apply_effect` as GitHub.
- `read_api` is shared; its only provider-specific behaviour is comment
  normalisation, delegated to `tracker.normalize_comment_body`
  (azure/tracker.py:398–409: strip + `_is_bot_comment`). This delegation is
  exactly the design the adapter docstring promises.
- `factory.py` is the single registry; `AzureTracker`/`AzureVCS` are
  constructed from `repo_cfg` and hold org/project/repo/PAT — Protocol
  methods take no `repo_cfg` (base.py design note, issue #168 S5).
- Protocol surface coverage: every `IssueTracker` and `VCSProvider` method
  has an Azure implementation. The one deliberate hole is
  `link_branch_to_issue` — an explicit, documented no-op (vcs.py:201–206,
  "Azure DevOps does not have an equivalent feature"). That is a legitimate
  provider capability gap, **not** an interface break: the Protocol's
  fail-soft convention (missing impl → `None`/no-op rather than
  `AttributeError`) means the caller never sees an error. Note ADO *does*
  have branch/work-item linking (per the deep-dive, the "Development"
  control on a work item) — but wiring it would need the
  `git/branches/{branchName}/links` API, which is out of scope and the
  no-op is correct for the current use (AutoSWE's linking is best-effort
  telemetry, not a control dependency).
- The `comments_fetched` invariant and `ApiState` contract (GitHub review
  F-6) are shared code — cited there; the Azure `read_api` path goes through
  the same shared function, so no Azure-specific violation.

**One Azure-side integrity wrinkle** (F-4, below): Azure's
`fetch_comments` rewrites bot comment bodies (strip HTML, re-append
`BOT_MARKER`, tracker.py:226–236) *before* the orchestrator sees them, while
GitHub returns bodies as-is. The facade contract is therefore
"normalised text in, normalised text out" only because both sides
normalise; this asymmetry is documented and the downstream
(`is_bot_comment`, `_find_last_bot_comment_ts`) relies on the marker being
present after normalization — which the re-append guarantees. Fragile but
correct, and pinned by tests (`tests/test_azure_tracker.py`, 46 tests).

## 3. Azure-Specific Build Assessment (Q1)

### 3.1 `get_ci_status` — `autoswe/providers/azure/vcs.py:209–239`

Queries `/_apis/build/builds?branchName=refs/heads/{branch}&statusFilter=all&$top=1&queryOrder=queueTimeDescending`,
takes `value[0]`, and maps:

- `status in _PENDING_STATUSES` → `pending`
- `result in _FAILURE_RESULTS` → `failure`
- `result in _SUCCESS_RESULTS` → `success`
- anything else → `none` ("no build result")

Differences vs GitHub (review F-1/F-2/F-3 apply **in kind**):

- **Fail-open on API error, shared pattern.** `except Exception:
  return CIStatus(state="none", summary="could not query builds")`
  (vcs.py:~227–228) — an ADO auth/PAT/rate-limit failure becomes
  "no CI configured" and `pr_gate` (pr_gate.py:61) passes the gate
  vacuously. Same class as GitHub review F-2; the Azure test
  `test_get_ci_status_request_error_is_none` (test_azure_vcs.py:380)
  **pins this as contract**, exactly as `test_get_ci_status_unresolvable_sha_is_none`
  does on GitHub.
- **Single-build semantics.** `total=1` always; the latest build for the
  *branch* is the only signal. `ref_sha` is accepted for protocol parity
  and **explicitly unused** (vcs.py:215–217 docstring). Consequences:
  (a) a build queued *before* the latest push can gate on stale code;
  (b) there is no per-commit correlation — `sourceVersion` (commit SHA)
  is available on each build object (deep-dive §3) and could be compared
  against `ref_sha`, but isn't; (c) a definition with several required
  stages collapses to one boolean, fine at current scale (one pipeline
  per repo) but loses the "which job failed" granularity the summary
  carries only as the definition name.
- **`queueTimeDescending` + `statusFilter=all`** can pick up a build that
  was manually queued or cancelled long ago if no newer build exists —
  acceptable (latest is latest), but note `canceled` is mapped into
  failure (test: `test_get_ci_status_canceled_is_failure`,
  test_azure_vcs.py:361), so a stale cancelled build blocks `/pr`
  forever until someone reruns the pipeline. GitHub's legacy-status
  path behaves differently on `neutral` — another asymmetry worth
  noting in the parity table, not a bug on either side.

### 3.2 PR open / idempotency / linkage — `azure/vcs.py:157–199` + shared `adapter.py` / `ship.py`

- `find_existing_pr` (:157) filters the PR list API by
  `sourceRefName`; `open_pull_request` (:175) POSTs
  `sourceRefName/targetRefName/title/description` (both redacted via
  `redact_outbound`) and constructs the **web** URL by hand from
  org/project/repo/id rather than trusting the API's `url` field
  (which is the API URL) — correct call, and the deep-dive confirms the
  web-URL shape.
- **Work-item linkage: hypothesis (b) REFUTED.** `open_pull_request`
  attaches no work item (vcs.py:184–190 — only the four fields above), and
  `link_branch_to_issue` is a no-op (:201–206). ADO's PR API *does* accept
  `workItemRefs` on create (deep-dive), so the association between the
  PR and its work item is **not recorded in ADO** — the work item's
  "Development" control will show nothing. Combined with the
  `Fixes #{issue_num}` body convention (shared `adapter.py`/`ship.py`,
  confirmed for both paths — see GitHub review §3.2/§6), the only
  machine-readable link ADO has is… none: ADO does not auto-close work
  items from PR body `Fixes #` text the way GitHub does. **Net effect: on
  Azure, merging a PR does not close or update the work item; the
  `autoswe:***` status tag is what keeps the queue consistent**, and
  `loop.py`'s `System.ChangedDate`-based `force_fetch`
  (loop.py:825–826: `_status == "pending" or in RUNNING_STATUSES` →
  re-fetch) is doing more of the freshness job than it does on GitHub.
  This is a real operational gap (F-5).
- Idempotency, bot footer, and re-cache-on-PR-open (#193) are shared
  code (`ship.py`, `adapter.py`) — cited in the GitHub review; no Azure
  branch of that logic exists.

### 3.3 Read path — `azure/tracker.py`

- `list_open_issues` (WIQL, :133) and `fetch_issue` (:182) normalize into
  the same `NormalizedIssue`; `_to_normalized` maps
  `System.ChangedDate` → `last_updated` (tracker.py:449) — hypothesis (d)
  partially confirmed: the field is read and passed through, but grep
  shows **no Azure-side consumer that acts on `last_updated` staleness**;
  the poller's re-fetch decision is status-driven (loop.py:825), not
  timestamp-driven. On Azure, a work item edited by a human (status tag
  untouched, description refined) is invisible to the loop until its
  status changes — GitHub has the same property, but ADO work items are
  edited more often out-of-band, so the `ChangedDate` plumbing that
  exists but isn't used is a more conspicuous dead end here.
- **Hypothesis (d), `_StripHTML`/`_is_bot_comment` edge cases — CONFIRMED as designed, with two sharp edges:**
  1. `fetch_comments` requests `api-version=7.1-preview` and
     `format=Markdown` (tracker.py:200–205) because stable 7.1 returns
     HTTP 400 on the comments resource (issue 022 regression, documented
     inline). The **`-preview` pin is a version-lifetime risk**: if ADO
     graduates/removes the preview, `fetch_comments` hard-fails and every
     Azure repo drops out of the poller (no fallback to stable, no
     feature probe).
  2. Bot detection is marker-first, content-pattern-fallback
     (`_is_bot_comment`, tracker.py:36–48, using shared
     `_BOT_CONTENT_PATTERNS`), and for bot bodies HTML is stripped with
     `html.parser` then `BOT_MARKER` is re-appended (tracker.py:226–236).
     Two edge cases: a **user comment whose text matches a content
     pattern** is classified `BOT` (losing its real author — e.g. a human
     pasting AutoSWE output into a comment), and a bot body that already
     ends in the marker but contains it mid-body twice keeps both
     (harmless; `endswith` guard, :235). The pattern fallback also means
     the two providers can disagree on the same comment text (GitHub
     relies on the marker alone in the stable API) — a cross-provider
     parity wart, not a bug.
- `set_status` tag handling (:352–395): strips caller-supplied
  `autoswe:` prefix to prevent `autoswe:autoswe:pending`, preserves
  non-autoswe tags, and issues the two-op JSON-Patch. Solid; the only
  cost is a GET+PATCH per status transition (2 calls vs 1 on GitHub's
  labels API), which at current volume is noise.
- `post_comment` (:309) / `update_comment` (:322) return `int | None` /
  `None`; failures propagate as exceptions into `apply_effect` — i.e.
  **Azure comment failures are *not* swallowed the way GitHub's hand-rolled
  `gh_post_comment` is** (GitHub review F-4). The shared
  `contextlib.suppress(Exception)` at `ship.py`'s bot-footer call site
  still applies to both providers, but the tracker-level behaviour is
  more correct on Azure.

### 3.4 Test coverage (evidence)

| File | Tests | Notes |
|---|---|---|
| `tests/test_azure_api.py` | 18 | retry/429/backoff/paging unit tests |
| `tests/test_azure_tracker.py` | 46 | incl. status tag round-trips, comment normalization |
| `tests/test_azure_vcs.py` | 24 | incl. `test_get_ci_status_request_error_is_none` (:380 — fail-open pinned) and `test_get_ci_status_canceled_is_failure` (:361) |
| `tests/test_sync_azure.py` | 28 | sync-path specifics |
| `tests/test_azure_live.py` | 6 | all `@pytest.mark.live`; skipped by default in CI, need `AZURE_DEVOPS_PAT`+org/project/repo env; validate fixture format against the real API |
| comparison: `tests/test_github_provider.py` | 41 | — |

Offline coverage is good (116 tests across the four offline files); the
live suite is the honest check for the 7.1-preview pin and PAT-embedded
clone URLs, but it does not run in default CI.

## 4. CI Feedback-Loop Gap Analysis (Q3)

Everything in GitHub review §4 applies **verbatim on the shared layers**
(single `get_ci_status` consumer in `pr_gate.py`; `shipped` is a
terminal-ish status — `COMPLETED_STATUSES`, tracking/labels.py:47; no
`ci_failed` Effect kind; recovery is human `/retry` or `/pr`). The Azure
differences:

1. **The gate reads the *latest build for the branch*, not for the head
   commit.** So the "green then red" scenario has an extra variant:
   after the PR opens, a *new* build for the branch (from any push, or a
   teammate's other branch sharing the pipeline's queue ordering… in
   practice same branch) becomes the gate's answer. The watch design must
   therefore key on the **head SHA** and compare it to the build's
   `sourceVersion` — which the ADO builds API returns — rather than
   re-reading the branch's latest build. GitHub review §4.4 already says
   "key on the PR's head SHA"; on Azure that check is one field
   comparison away, on GitHub it needs the commit lookup.
2. **Build `canceled` = failure.** The CI-watch must treat a canceled
   build as red (matches current pin), so a cancelled pipeline blocks the
   task the same way a failed one does.
3. **No PR-merge-status signal available to the gate today.** ADO
   exposes `mergeStatus` (`succeeded`/`conflicts`/`queued`/…) on
   `GET .../pullRequests/{prId}/status` (deep-dive line 83). Neither
   provider currently reads mergeability at all; on Azure it would be the
   cheapest possible "is this PR mergeable" check for the watch pass.

**Recommended design (one line):** extend the shared CI-watch pass
(GitHub review §4.4 — poll each `shipped` task with `pr_number`, emit
`post_comment` + `patch_queue(ci_failed)` on red) with a provider hook
`get_ci_status_for_sha(branch, sha)` whose Azure impl compares the
latest build's `sourceVersion` to the PR head SHA (stale-build →
treat as `pending`, not `success`) and whose GitHub impl keeps today's
commit-scoped check-runs read — so one new Effect and one new status
serve both backends.

## 5. Prioritized Weaknesses

| # | Severity | Location | Issue | Remediation |
|---|---|---|---|---|
| F-5 | **High** | `azure/vcs.py:175–199` (no `workItemRefs`) + `:201–206` (no-op link) + no `Fixes #` auto-close on ADO | Merged PR neither closes nor links the work item; the only queue-consistency signal is the `autoswe:***` tag, and `System.ChangedDate` (read at tracker.py:449) has no consumer acting on out-of-band edits | Add `workItemRefs=[issue_number]` to the PR-create POST (one field); optionally add a `shipped`-task sweep in `poll()` that re-fetches work items whose `System.ChangedDate` > last poll and status moved out of `autoswe:*` |
| F-2a | **High** | `azure/vcs.py:~227–228` (`except Exception → state="none"`), pinned by `test_azure_vcs.py:380`; gate at `vcs/pr_gate.py:61` | CI gate fail-open: any ADO API error (bad PAT, 403, network) → "no CI" → PR opens vacuously. **SHARED** with GitHub review F-2 (same shared `pr_gate` decision, cited independently here) | Add `CIStatus.state="error"`; `pr_gate` blocks on `error` (or `PR_CI_ERROR_POLICY`); tests flip `test_get_ci_status_request_error_is_none` → `_is_error` |
| F-6 | **Medium** | `azure/tracker.py:200–205` (hard `api-version=7.1-preview` on comments) | Preview-version pin with no fallback/probe: graduation or removal of the preview breaks `fetch_comments` → all Azure repos silently drop from the poller (fetch failure per repo) | Probe stable `7.1` once (or per-repo, cached); fall back to stable when comments API answers 200; alert on 400 |
| F-7a | **Medium** | `azure/vcs.py:209–239` (`$top=1`, branch-only query; `ref_sha` unused, :215–217) | Gate decides on the branch's latest build regardless of head commit — stale-build false green/red possible; `canceled` stale build blocks `/pr` indefinitely | When `ref_sha` is supplied, compare build `sourceVersion` to it; mismatch → `pending` (build running for the right commit) rather than success/failure; add `sourceVersion` to `CIStatus` |
| F-8a | **Medium** | `azure/tracker.py:36–48` + :226–236 (content-pattern bot fallback) | User comment matching `_BOT_CONTENT_PATTERNS` is relabeled `BOT` (author lost, command ignored); providers can disagree on the same body vs GitHub's marker-only path | Marker-only for *authorship*; use content patterns only to *recover* bot-ness of markerless legacy bot posts where `createdBy` matches the bot identity (ADO exposes `createdBy` — use it) |
| F-9a | **Low** | `azure/api.py:69–124` (`_ado_request`) | PAT travels in every header **and** is embedded in `clone_url()` (vcs.py:146) → PAT sits in worktree remotes on disk; `git remote -v` / worktree snapshots leak it. `redact_outbound` covers outbound payloads, not local git config | After initial clone+push, rewrite remote to credential-less URL + git credential helper/store, or store PAT in a per-repo `~/.git-credentials` with restrictive perms; document rotation on PAT change |
| F-10a | **Low** | `azure/tracker.py:352–395` (`set_status` GET+PATCH) | Two API calls per status transition; non-atomic read-modify-write (a human editing tags between GET and PATCH loses their edit — `remove` then `add` overwrites the whole tag set) | Acceptable at current volume; if tag contention shows up, switch to a single `op:"replace"` JSON-Patch computed from server-side values, or move status to a dedicated ADO field |
| F-11a | **Info** | `azure/vcs.py:201–206` (`link_branch_to_issue` no-op) | ADO *does* support branch↔work-item links (Development control, deep-dive); no-op foregoes the "which ticket does this build cover" surface the deep-dive highlights | Optional: POST `git/branches/{branch}/links` when the branch is pushed; purely telemetry, no control dependency |

**SHARED with the GitHub review** (same shared code, both providers
affected — full detail in `docs/autoswe/review-github-provider.md`):
F-2a ↔ GitHub F-2 (fail-open CI gate; shared `pr_gate.py:61`), F-7a
context ↔ GitHub F-7 (no post-open CI loop at all — the Azure findings
above are the Azure-specific *variants* of that shared gap), plus the
shared-layer items GitHub F-4 (best-effort comment post at
`ship.py` suppress), F-6 (`comments_fetched` invariant), F-8
(`pr_gate._flag` casing), F-10 (no-inheritance Protocol). Azure-side
citations for each shared file/line appear above in §2–§4.

## 6. Evidence Log

| Command | Key output |
|---|---|
| `read` full: `azure/api.py`, `azure/tracker.py`, `azure/vcs.py`, `adapter.py`, `factory.py`, `base.py`, `vcs/pr_gate.py`, `vcs/ship.py`, `orch/{loop,decide,run,types}.py`, `tracking/comments.py` | All file:line citations above |
| `sed -n '69,171p' autoswe/providers/azure/api.py` | Hypothesis (a) confirmed: `base64.b64encode((":" + pat).encode())` at :79; 429 → `Retry-After`/`x-ms-retry-after-ms` (:104–113); 5xx backoff (:116); `ado_get_paged` `continuationToken` (:158–171) |
| `sed -n '175,320p' autoswe/providers/azure/vcs.py` | Hypothesis (b) **refuted**: `open_pull_request` body has exactly `sourceRefName/targetRefName/title/description`; no `workItemRefs`; `link_branch_to_issue` = no-op (:201–206); `get_ci_status` builds endpoint, `ref_sha` unused, `except Exception → CIStatus(state="none")` |
| `sed -n '191,260p' autoswe/providers/azure/tracker.py` | Hypothesis (d): `api-version=7.1-preview` + `format=Markdown` (:200–205); PAT-owner lookup failure non-fatal (:215); BOT re-append after `_strip_html` (:235–236); `System.ChangedDate` → `last_updated` (:449) |
| `grep -n "work_item\|workitem\|link" autoswe/providers/azure/vcs.py` | Only hits: the no-op method name/docstring — no linkage anywhere in the VCS provider |
| `grep -rn "get_ci_status" autoswe/` | Single consumer `vcs/pr_gate.py` — shared no-post-open-monitoring confirmed on the Azure side too |
| `grep -n "force_fetch" autoswe/orch/loop.py` | :50 `_MIRROR_STATUSES`; :729 `_single_poll`; :825–826 `pending`/running → `force_fetch.add(_inum)` — status-driven re-fetch, `ChangedDate` unused by loop |
| `pytest --collect-only -q` per file | test_azure_api 18, test_azure_tracker 46, test_azure_vcs 24, test_sync_azure 28, test_azure_live 6 (all `@pytest.mark.live`, skipped by default), test_github_provider 41 (comparison) |
| `read docs/autoswe/review-github-provider.md` | Format parity; shared-findings cross-reference (F-2/F-4/F-6/F-7/F-8/F-10); §4.4 watch design reused with Azure head-SHA variant |
| `read docs/azure-devops-api/workitem-pr-linking-and-builds.md` | `sourceVersion` on builds (§3); PR `status` endpoint `mergeStatus` (line 83); work item "Development" control (§1–2) — basis for F-5/F-11a and the §4 watch design |

**Constraints honored:** read-only review; exactly one file produced
(this report); nothing under `autoswe/providers/github/` touched; no
commits; no live API calls; no `pytest` execution beyond collection.

## 7. Summary for Report-Back

- **Interface integrity:** intact — `adapter.apply_effect`/`read_api` +
  `factory` registries are the single seams for both providers, and the
  Azure impls cover the full Protocol surface (one documented no-op:
  `link_branch_to_issue`).
- **Top findings:** F-5 (High, no work-item↔PR linkage, `Fixes #` has no
  auto-close effect on ADO), F-2a (High, CI gate fail-open, shared with
  GitHub F-2), F-6 (Medium, `7.1-preview` hard pin, no fallback), F-7a
  (Medium, branch-latest-build gating ignores head SHA + stale
  `canceled` build), F-8a (Medium, content-pattern bot detection
  mislabels human comments), F-9a (Low, PAT embedded in worktree remote
  URLs), F-10a (Low, tag read-modify-write), F-11a (Info, no branch links
  despite ADO support).
- **Surprises:** (1) the `System.ChangedDate` field is parsed and
  normalized (tracker.py:449) but **nothing in the loop consumes it** —
  dead plumbing that would be the natural fix for out-of-band work-item
  edits on Azure; (2) `canceled` is pinned as CI **failure**
  (test_azure_vcs.py:361), so a stale canceled build blocks `/pr`
  forever — stricter than GitHub's legacy `neutral` handling; (3) ADO
  comment API is stuck on a **preview** version (stable 7.1 returns 400 —
  issue 022), the single most fragile line in the whole provider.
- **CI-failure feedback loop (one line):** add a shared poll-time
  CI-watch pass for `shipped` tasks with a PR — Azure compares the
  branch's latest build `sourceVersion` to the PR head SHA (stale →
  `pending`), red → emit `post_comment` + `patch_queue(ci_failed)` so the
  existing `/retry`/`/pr`/allowlist/attempt-budget machinery absorbs it
  with no new transitions.
- **SHARED with GitHub review:** F-2 (fail-open CI gate,
  `pr_gate.py:61`), F-7 (no post-open CI loop — the Azure §4 variants),
  plus shared-layer items F-4 (suppress at `ship.py`), F-6
  (`comments_fetched`), F-8 (`_flag` casing), F-10 (Protocol
  no-inheritance).
