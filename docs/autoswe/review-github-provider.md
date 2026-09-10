# AutoSWE GitHub Provider — Deep Code Review (Task 1 of 2)

**Scope:** GitHub provider build only (`autoswe/providers/github/`, plus the shared
interface files `autoswe/providers/base.py`, `adapter.py`, `factory.py`, and the
provider-agnostic consumers `autoswe/vcs/pr_gate.py`, `autoswe/vcs/ship.py`,
`autoswe/tracking/api.py`, and the orchestrator layers `autoswe/orch/`).
**Mode:** read-only review. Nothing under `autoswe/providers/azure/` was modified.
**Date:** 2026-09-09. Repo state: branch checked out at `2127682` (Azure deep-dive docs),
working tree clean except untracked `cron/`, `e2e/`, `notes.md`.

---

## 1. Architecture Map

### 1.1 Provider layer

```
autoswe/providers/
  base.py       — Protocols: IssueTracker (~15 methods), VCSProvider (~13 methods)
                  dataclasses: NormalizedComment, NormalizedIssue, PRResult,
                  CIStatus(state: success|pending|failure|none)
  adapter.py    — read_api() + apply_effect(); the ONLY code that translates
                  World/Effect into provider calls
  factory.py    — TRACKERS/VCSS name→class registries; get_tracker, get_vcs,
                  build_repo_cfg
  github/
    tracker.py  — GitHubTracker: wraps autoswe.tracking.{api,assignment,labels};
                  _ensure_repo_labels lazily cached
    vcs.py      — GitHubVCS (338 lines): gh-CLI-first with REST/GraphQL fallback;
                  get_ci_status combines Checks API + legacy commit-status
  azure/        — (out of scope for this review)
```

### 1.2 Orchestration layers that consume the providers

```
orch/loop.py    — poll(): load repos → adapter.read_api → decide → run →
                  emit → adapter.apply_effect → save_queue
orch/decide.py  — pure state machine decide(world) → Action
orch/emit.py    — emit(action, result, world) → list[Effect]
orch/run.py     — Layer B runner wrapper; dispatches to planner/coder/ship/worktree
vcs/ship.py     — open_pr(): preflight_pr → vcs.open_pull_request → comment
vcs/pr_gate.py  — preflight_pr(): branch-sync gate + CI gate (ONLY consumer
                  of VCSProvider.get_ci_status in the codebase)
tracking/api.py — raw GitHub REST with rate-limit/backoff handling (_gh_request)
```

**Effect kinds** (`orch/types.py`): `post_comment`, `update_comment`, `set_status`,
`patch_queue`, `assign`, `create_pr`, `noop`. There is **no** `ci_failure_requeue`
or any CI-feedback Effect kind — relevant to §4.

### 1.3 Data flow for a GitHub task

1. `poll()` → `adapter.read_api(tracker, ...)` → `list_open_issues()` +
   per-issue `fetch_comments()` (skipped when `last_updated` unchanged;
   `comments_fetched=False`, empty comment tuple — adapter.py:30–120).
2. `decide(world)` → `Action` (slash-command match, status machine,
   attempt budget with `MAX_ATTEMPTS`, allowlist enforcement).
3. `run(action, world)` → `DispatchResult` (pure actions → `None`).
4. `emit(action, result, world)` → `list[Effect]` including the auto-PR
   `create_pr` effect when `kind in (fix, retry) and AUTO_CREATE_PR and
   task.pr_number is None and not rereview_pending` (emit.py:~554).
5. `adapter.apply_effect(...)` per effect — the `create_pr` branch
   (adapter.py:142–200) re-runs `preflight_pr(do_sync=False, vcs=vcs)`,
   idempotency-checks via `vcs.find_existing_pr(branch)`, opens via
   `vcs.open_pull_request(...)` with `Fixes #N` on its own first line,
   and caches `pr_number`/`pr_url` on the queue entry in the same cycle
   (issue #193 fix).

---

## 2. Interface Integrity (Q2)

**Verdict: the Protocol/facade abstraction is structurally intact — high
integrity, with one documented trade-off that creates a silent-failure class.**

Evidence:

1. **Single translation point.** `adapter.apply_effect` is the only code path
   from `Effect` to provider calls, and it calls only `tracker.*` / `vcs.*`
   protocol methods (`post_comment`, `update_comment`, `set_status`, `assign`,
   `find_existing_pr`, `open_pull_request`, `link_branch_to_issue`,
   `branch_name`). No orchestrator code reaches past the facade to call
   `autoswe.tracking.api` or `gh`-CLI directly — the only raw-API exceptions are
   inside the provider implementations themselves, as they should be.
2. **Single registry.** `factory.py` holds the `TRACKERS`/`VCSS` dicts;
   `get_tracker`/`get_vcs` are the sole construction points. `ship.py` and
   `pr_gate.py` both resolve providers through `get_vcs(repo_cfg)` and both
   derive the branch from the same `vcs.branch_name(issue_num)` — the
   "branch convention owned by the provider (single source: F-05)" invariant
   holds, and the `ship.open_pr`/`preflight_pr` agreement is explicitly
   documented (ship.py docstring, PR target = `base_branch`, never
   `plan_branch`, issue #196).
3. **Normalized boundary types.** `NormalizedIssue`/`NormalizedComment` with
   `raw_author_login` + `author_login` split, `normalize_comment_body` hook for
   provider-specific body handling (GitHub: identity; Azure: HTML decode),
   bot-marker re-appended post-normalisation (adapter.py:78–100) — the
   Azure-strips-HTML-comment problem is handled at the seam, not in callers.
4. **Known intentional weakness — no Protocol inheritance.** `base.py`'s
   docstring states concrete classes deliberately do *not* inherit the
   Protocols, so a missing implementation returns `None`/silent skip instead
   of `AttributeError`. This is a deliberate trade-off (forward-compat for
   partial providers), and it *works*: `AzureVCS.link_branch_to_issue()` is a
   documented no-op and the adapter does not branch on provider name
   (adapter.py:120–122). The risk is latent: a future provider that silently
   misses, e.g., `get_ci_status` would surface as a `None` CI status, not a
   type error. `typing.Protocol` + `runtime_checkable` is available but was
   consciously not used; treat as accepted risk, not a defect.

**No facade bypasses, no provider leakage, no duplicated normalisation found.**

---

## 3. GitHub-Specific Build Assessment (Q1)

### 3.1 `get_ci_status` — `autoswe/providers/github/vcs.py:241–312`

Combines Checks API (`/commits/{sha}/check-runs`) and legacy combined
(`/commits/{sha}/status`). Priority: any failure → `failure`; else any
non-completed → `pending`; else ≥1 success → `success`; else `none`.

Findings (all confirmed by reading):

- **F-1 (high).** Unresolvable branch head returns
  `CIStatus(state="none", summary="could not resolve branch head")`
  (vcs.py:~256–258). `none` is **treated as pass** by the CI gate
  (pr_gate.py:~61: `"success" and "none" (no CI configured) both pass`).
- **F-2 (high).** Both API calls are wrapped in `except Exception: pass`
  ("best-effort — treat as no check-runs available"). A 403, 404, network
  error, or rate-limit exhaustion on *both* endpoints yields `total=0` →
  `state="none"` → gate passes. **The project's own reference doc
  (`docs/github-api/issue-pr-linking-and-ci.md`, Caveat #1) records that the
  Checks API returns 403 "Resource not accessible by personal access token"
  on private repos with a classic PAT — while the Actions runs endpoints work
  fine.** So on a private repo with a classic PAT, the CI gate is
  *vacuously satisfied on every dispatch*: the failure mode is silent and
  deterministic, not occasional.
- **F-3 (medium).** Conclusions `neutral` / `skipped` / `cancelled`-adjacent
  outcomes: `cancelled` and `timed_out` are in `_FAILURE_CONCLUSIONS`, but a
  commit whose only check concluded `neutral` or `skipped` yields
  `success_count=0, total>0` → `state="none"` → pass. `none` conflates
  "no CI configured" with "checks exist but verified nothing" — the gate
  cannot distinguish them.
- **API-choice gap.** The documented, PAT-friendly endpoint
  `GET /actions/runs?head_sha=...` (which also carries `pull_requests[]`
  linkage and a single `conclusion` field) is *not* used as a fallback. The
  implementation picks exactly the endpoint pair that the project's own doc
  flags as 403-prone for the primary deployment (PAT + private repos).

### 3.2 PR open / idempotency / linkage — `adapter.py:142–200`, `ship.py`

- **(c) verified: PR body carries the closing keyword.** `Fixes #{issue_num}`
  is the first line in all three paths: `emit.py` auto-PR effect body
  (emit.py:~557–563), `adapter.apply_effect` create_pr branch
  (adapter.py:161–179, with backwards-compat enrichment of the bare
  `"Fixes #N"` body using queue `body`/`fix_summary`), and
  `ship.open_pr` (ship.py:~107–113). This satisfies GitHub's
  closing-keyword-on-merge auto-close per the reference recipe (§2.1 of
  docs/github-api/issue-pr-linking-and-ci.md).
- **Idempotency is solid.** Both explicit `/pr` (`ship.open_pr`) and
  auto-PR (`adapter.create_pr`) call `find_existing_pr(branch)` before
  opening; the existing-PR path re-caches `pr_number`/`pr_url` (issue #193)
  rather than re-opening. Crash-between-create-and-save is handled.
- **`link_branch_to_issue` (vcs.py:~195–235)** is *not* a silent no-op —
  verified: it raises `MissingScopeError` on 403/permission GraphQL errors
  and on unknown errors, and only treats "already exists" as a benign no-op.
  It runs `max_retries=1, timeout=10` per its best-effort contract.
- **F-4 (medium).** `gh_post_comment` in `tracking/api.py` is hand-rolled
  (its own `urlopen`, no backoff, no Retry-After handling) and *swallows*
  HTTP errors (`dbg.warning` + `[WARN] comment post failed`). Bot
  acknowledgement comments (e.g. "Pull request opened: …") are best-effort,
  while the state transition is not — a comment POST failure leaves the task
  `shipped` with no user-visible marker; downstream bot-ordering detection
  (`_find_last_bot_comment_id`) then relies on the fallback path. Comment
  posts also bypass `_gh_request`'s rate-limit logic entirely, so a
  403-secondary-limit during a comment POST is a hard silent drop, while the
  adjacent read call would have backed off.
- **F-5 (low).** `find_existing_pr` is gh-CLI-first (tested:
  `test_find_existing_pr_gh_cli_missing`, `_timeout`) with REST fallback
  (`test_open_pr_uses_api_fallback`) — reasonable, but the CLI path and the
  REST path have different failure semantics (timeout → treated as
  not-found vs. raised), which is only safe because the caller treats
  not-found as "open new" and a duplicate-PR error then surfaces as
  `FAILED: could not create PR` — recoverable but noisy.

### 3.3 Read path — `adapter.read_api`

- **(e) staleness assessment.** Comment fetch is skipped when
  `issue.last_updated == stored` → `comments=[]`, `comments_fetched=False`.
  On GitHub, any new comment bumps `updated_at`, so the skip is sound for
  *new* comments. The risk is the watermark, not the timestamp: correctness
  depends entirely on `last_consumed_reply_id`/watermark being persisted in
  the queue before the next cycle; if queue state is lost or a comment is
  posted within the same second as `updated_at` granularity (GitHub
  timestamps are second-granular), one fetch cycle can miss a command and
  it is picked up on the *next* comment — i.e. delayed, not lost, provided
  the watermark persists. `force_fetch` exists as an override. **F-6 (low):**
  acceptable, but the invariant "decide() must respect `comments_fetched`"
  is enforced only by test discipline (adapter.py:144–192 tests), not by
  type — an `ApiState` with `comments=()` is indistinguishable from "fetched
  and empty" to any new consumer.
- `gh_get_all` pagination (tracking/api.py) follows `per_page=100` until an
  empty page with **no page cap** — unbounded on pathological comment counts;
  each page is a rate-limited call.
- Rate-limit handling in `_gh_request` is good: archived-repo 403 short
  circuit, Retry-After parsing clamped to [1, 300]s, exponential backoff
  bounded by `max_retries`. Note the primary-limit path sleeps
  `max(60, reset - now)` — a poller cycle can block up to the full rate-limit
  window in-process (no yield-to-next-cycle), which is fine at this scale but
  worth knowing.

### 3.4 Test coverage (evidence)

| File | Tests | Notes |
|---|---|---|
| `tests/test_github_provider.py` | 41 | Tracker token resolution, comment normalisation (incl. bot-marker precedence, mixed authors, auth-failure fallback), label ensure-once, VCS: gh-CLI missing/timeout/fallback, `link_branch_to_issue` 403/idempotent/unknown-error, `get_ci_status` success/pending/failure-priority/legacy/no-checks/**unresolvable-sha→none**/explicit-ref |
| `tests/test_pr_gate.py` | 16 | Flag resolution (repo override beats cfg), CI success/none/pending/failure/disabled, sync clean/conflict/error/Claude-resolution paths |
| `tests/test_provider_adapter.py` | ~20 | Azure normalisation, `read_api` skip/fetch/force/new/backward-compat, every `apply_effect` kind incl. `create_pr` deferred-on-pending/failing and proceeds-on-success |
| `tests/test_provider_factory.py` | — | Registry resolution |
| `tests/test_api_contract.py` | fixtures + live | Fixture contract tests **and** `TestGitHubLiveShapeDrift` (live-token-gated superset checks vs. the real API) |
| `tests/test_emit.py` | 41 | Effect emission incl. auto-PR gating, `rereview_after_fix` clearing (issue #195), test_failed gate |
| `tests/test_decide.py` | 10 (parametrized) | Fixture-driven state machine |
| `tests/test_orch_run.py` | 58 | Dispatch layer incl. `ship.open_pr` wiring |

Coverage of the *current* contract is strong — including tests that pin
**fail-open** behavior as the expected contract (`test_get_ci_status_
unresolvable_sha_is_none`, `test_ci_none_passes`). That is itself a finding:
the tests codify F-1 as intentional without the caveat that "none" also
means "the API call failed".

---

## 4. CI Feedback-Loop Gap Analysis (Q3)

### 4.1 What exists today

CI is consulted **exactly once, before the PR is opened**, on both open
paths:

- explicit `/pr` → `run.py` → `ship.open_pr()` → `preflight_pr(do_sync=True)`
- auto-PR after `/fix`/`/retry` → `emit` `create_pr` effect →
  `adapter.apply_effect` → `preflight_pr(do_sync=False, vcs=vcs)`

Both gate on `PR_REQUIRE_CI` (default **on**). Outcomes: `failure` → block,
comment "PR deferred — CI failing… Post `/pr` when ready"; `pending` →
block, "retry /pr when green"; `success`/`none` → pass and open.

### 4.2 What does NOT exist (verified by grep + read)

- **No post-open monitoring.** `get_ci_status` has exactly one consumer
  (`vcs/pr_gate.py`) in the entire codebase. After `create_pr` is applied,
  the task transitions to `shipped` (a `COMPLETED_STATUS`,
  `tracking/labels.py:47`) and `decide()` returns `noop` in that state with
  no command. Nothing re-reads CI, checks mergeability, watches for the
  `Fixes #N` auto-close, or detects a post-open CI failure.
- **No CI-failure Effect kind.** `orch/types.py` has no
  `ci_failure_requeue`/`set_ci_status` Effect; `emit` has no CI-driven
  branch. There is no state for "PR open, CI red" — the task simply sits
  `shipped`.
- **No automatic re-dispatch on red.** Recovery is human-driven: post
  `/retry` (re-runs the fix; note the `create_pr` effect only fires when
  `task.pr_number is None`, so no new PR effect is emitted — the existing PR
  refreshes implicitly because the coder pushes to the same
  `autoswe/issue-N` branch) or post `/pr` (re-runs preflight against the
  *current* branch head; passes if CI is green now, reuses the existing PR).
- **No auto-merge path at all** — merge is always human. That is a
  deliberate safety choice and fine; the gap is not "auto-merge", it is
  "**nobody tells anyone CI went red**".

### 4.3 Consequences

A PR that opens green and then goes red (required checks added, flake
becoming a regression, base-branch dependency change) produces: no comment,
no state change, no attempt-budget interaction, silent forever until a human
looks at the PR. The issue stays open (auto-close fires only on merge), the
task stays `shipped` in the queue, and the poller's per-cycle cost for it
remains ~zero — the failure is invisible to the system that is supposed to
drive the next step.

### 4.4 Recommended design (one line)

> Add a **CI-watch pass** to `poll()`: for each queue entry with
> `pr_number` set and status `shipped`, call `vcs.get_ci_status(head_sha)`;
> on `completed+failure` emit `post_comment` + `patch_queue` to a new
> `ci_failed` status (and clear it back to `shipped` on green) so the
> existing `/retry`/`/pr` machinery — allowlists, attempt budgets,
> `SHIPPING_BLOCKING_STATUSES` guards — handles the rest without new
> transitions.

Implementation notes: reuse `preflight_pr`'s `get_ci_status` call shape
(pr_gate.py already resolves `vcs` from `repo_cfg`); key on the PR's head
SHA, not the branch name, to avoid re-reading during pushes; gate the watch
behind a `PR_CI_WATCH` flag (default off first, mirroring how
`PR_REQUIRE_CI` overridability works via `pr_gate._flag`); and make
`CIStatus.state` distinguish `error` from `none` (see F-1/F-2) so the watch
can't inherit the fail-open behavior.

---

## 5. Prioritized Weaknesses

| # | Severity | Location | Issue | Remediation |
|---|---|---|---|---|
| F-2 | **High** | `providers/github/vcs.py:~262–312` (`except Exception: pass`) + `vcs.py:~247–258` + `pr_gate.py:~55–61` | CI gate fail-open: API error (incl. the documented classic-PAT-on-private-repo Checks-API 403, `docs/github-api/issue-pr-linking-and-ci.md` Caveat #1) → `state="none"` → gate passes vacuously | Add `state="error"` to `CIStatus`; let `pr_gate` treat `error` as blocking (or configurable `PR_CI_ERROR_POLICY=open\|block`); fall back to `GET /actions/runs?head_sha=` (PAT-friendly, documented) when check-runs return 403 |
| F-1 | **High** | `providers/github/vcs.py:~256–258` | "could not resolve branch head" → `"none"` (pass) even though the branch should exist; conflates error with no-CI | Same as F-2: distinguish unresolvable-head from no-checks; unresolvable-head on an expected branch is an error condition, not an absence |
| F-7 | **High** | whole orchestrator (`orch/loop.py`, `emit.py`, `decide.py`) | No post-open CI feedback loop (§4): `get_ci_status` has one consumer; a green-open PR that later fails is invisible; no `ci_failed` state, no Effect kind | CI-watch pass in `poll()` emitting `post_comment` + `patch_queue(ci_failed)`; new `ci_failed` status feeding existing `/retry`/`/pr` guards |
| F-4 | **Medium** | `tracking/api.py:gh_post_comment` | Hand-rolled `urlopen` with no backoff/Retry-After; HTTP errors swallowed silently; comment posts bypass `_gh_request` rate-limit logic while the read path honors it — asymmetric failure behavior; state transitions land while ack comments drop | Route comment POSTs through `_gh_request`; raise (or return status) so `apply_effect` can log/compensate; keep the current `contextlib.suppress` at ship.py call sites only where truly best-effort is intended |
| F-3 | **Medium** | `providers/github/vcs.py:~270–312` + `_FAILURE_CONCLUSIONS`/`_SUCCESS_CONCLUSIONS` | `neutral`/`skipped`-only commits → `none` → pass; `none` conflates "no CI" with "checks exist but verified nothing" | Count `neutral`/`skipped` explicitly; report them in `summary`; optionally a `PR_STRICT_CI` flag that fails when total>0 but success_count==0 |
| F-6 | **Low** | `providers/adapter.py:~60–120` (`read_api` skip rule) + `ApiState` | `comments_fetched` invariant enforced only by tests; `comments=()` is ambiguous to new consumers; watermark persistence is the real safety net | Make the contract explicit — e.g. `ApiState` constructor asserting `comments == ()` only when `comments_fetched is False`, or a typed sentinel; document in `base.py` |
| F-8 | **Low** | `pr_gate.py:_flag` | Per-repo overrides must use lowercase keys; a typed config key (e.g. `PR_REQUIRE_CI` in repo_cfg) is silently ignored and the gate defaults to on | Accept both casings, or validate known keys with a warning on unknowns in `build_repo_cfg` |
| F-9 | **Low** | `tracking/api.py:gh_get_all` | Unbounded pagination (no page cap) — pathological issues can loop; each page is a rate-limited call | Cap pages (e.g. 100) with a warning, or stream with a configurable limit |
| F-10 | **Info** | `providers/base.py` (doc) | Deliberate no-inheritance Protocol design → missing impl = silent `None`, not `AttributeError`; documented, accepted, but the fail-open CI path shows the class of bug it enables | Optional: `runtime_checkable` conformance assertion at factory construction time (fail at wiring, not at dispatch) |

---

## 6. Evidence Log

| Command | Key output |
|---|---|
| `git log --oneline -5`; `git status` | HEAD `2127682` (Azure deep-dive docs); untracked `cron/`, `e2e/`, `notes.md`; tree otherwise clean |
| `ls autoswe/providers autoswe/providers/github autoswe/orch autoswe/vcs` | Layout per §1.1–1.3 |
| `read` full: `base.py`, `adapter.py`, `factory.py`, `github/tracker.py`, `github/vcs.py`, `pr_gate.py`, `ship.py`, `orch/{types,loop,decide,emit,run}.py`, `tracking/api.py` | All file:line citations above |
| `sed -n '195,338p' autoswe/providers/github/vcs.py` | Confirmed F-1/F-2/F-3: unresolvable-head → `none` (two sites); `except Exception: pass` on both endpoints; neutral/skipped fall through to `none` |
| `sed -n '1,80p' autoswe/vcs/pr_gate.py` | Confirmed gate: `failure`→block, `pending`→block "retry /pr when green", comment `# "success" and "none" (no CI configured) both pass` (~line 61) |
| `grep -n "open_pull_request\|open_pr\|create_pr" autoswe/ -r` | Call sites: `ship.py:134/150`, `adapter.py:144/176`, `orch/types.py:276`, `orch/emit.py:569`, `orch/run.py:141` — no other consumers |
| `grep -rn "get_ci_status" autoswe/` | Single consumer: `autoswe/vcs/pr_gate.py` → confirms §4.2 "no post-open monitoring" |
| `sed -n '120,200p' autoswe/providers/adapter.py` | Confirmed (c): `Fixes #{issue_num}` first line in PR body (adapter.py:163, 176–180); idempotent re-cache path (issue #193) |
| `sed -n '120,200p' autoswe/vcs/ship.py` | Confirmed same body convention; `find_existing_pr` before open; broad `except` → `FAILED: could not create PR` |
| `sed -n '195,235p' autoswe/providers/github/vcs.py` | Confirmed (d): `link_branch_to_issue` raises `MissingScopeError`/`RuntimeError`; only "already exists" is a no-op; `max_retries=1, timeout=10` |
| `grep -n "def test" tests/test_github_provider.py tests/test_pr_gate.py tests/test_provider_adapter.py` | 41 / 16 / ~20 tests; incl. `test_get_ci_status_unresolvable_sha_is_none` (:583), `test_ci_none_passes` (test_pr_gate.py:70) — fail-open pinned as contract |
| `grep -c "def test" tests/test_emit.py tests/test_decide.py tests/test_orch_run.py` | 41 / 10 (parametrized fixtures) / 58 |
| `grep -rn "COMPLETED_STATUSES\s*=" autoswe/` | `tracking/labels.py:47`: `{"fixed","synced","shipped","reviewed"}` — `shipped` is terminal-ish for dispatch, confirming no post-open re-check in the state machine |
| `read docs/github-api/issue-pr-linking-and-ci.md` | Caveat #1 (Checks API 403 with classic PAT on private repos; use `/actions/runs?head_sha=`) — the documented condition that F-2 silently converts into a pass |
| `sed -n '540,620p' autoswe/orch/emit.py` | Confirmed auto-PR effect fires only when `task.pr_number is None`; `test_failed` gate keeps task restartable; `rereview_after_fix` clearing (issue #195) |

**Commands NOT run (read-only scope):** no `pytest`, no live API calls, no
modifications to any file.

---

## 7. Summary for Report-Back

- **Interface integrity:** the Protocol/facade abstraction in
  `base.py`/`adapter.py`/`factory.py` is intact — `apply_effect` is the single
  `Effect`→provider seam, the factory is the single registry, branch
  convention and PR-identity caching are single-sourced, and the one design
  trade-off (no Protocol inheritance → silent `None`) is documented and
  currently benign, but it is the enabler of the top CI finding.
- **Top findings:** F-2/F-1 (CI gate fail-open on API error, incl. the
  documented PAT+private-repo 403 — the gate is vacuous on the primary
  deployment), F-7 (no post-open CI feedback loop; `get_ci_status` has one
  consumer), F-4 (comment POSTs bypass rate-limit machinery and swallow
  errors asymmetrically with reads), F-3 (neutral/skipped-only checks pass as
  "none"), F-6 (`comments_fetched` invariant unenforced), F-8/F-9 (config-key
  casing, unbounded pagination).
- **Most surprising:** (1) the project's *own* reference doc warns about the
  exact 403 that `except Exception: pass` turns into a silent CI pass;
  (2) the test suite pins the fail-open behavior as the expected contract
  (`unresolvable_sha_is_none`, `ci_none_passes`) — the tests made the risk
  look intentional; (3) the `create_pr` effect's `task.pr_number is None`
  guard means a red PR can never trigger a re-PR from a fix — the loop
  assumes PR==branch and never re-validates the head.
- **CI-feedback-loop design (one line):** a `poll()`-resident CI-watch pass
  that calls `get_ci_status(head_sha)` for every `shipped` task with
  `pr_number` and patches it to a new `ci_failed` status (plus a comment) on
  red, handing off to the existing `/retry`/`/pr`/attempt-budget machinery.
