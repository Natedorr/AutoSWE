# Unified Plan — Complete Cross-Linkage + CI Feedback Loop

**Status:** proposal / implementation plan. **Date:** 2026-09-09. **Branch:** `pi`.
**Inputs:** [review-github-provider.md](review-github-provider.md),
[review-azure-provider.md](review-azure-provider.md),
[../github-api/issue-pr-linking-and-ci.md](../github-api/issue-pr-linking-and-ci.md),
[../azure-devops-api/workitem-pr-linking-and-builds.md](../azure-devops-api/workitem-pr-linking-and-builds.md).

Two deliverables, one design:

1. **Linkage completeness** — every edge between issue/work item ↔ branch ↔ commit ↔ PR ↔ build
   that the platform supports is created by autoSWE, verified, and self-healed.
2. **CI feedback loop** — after a push, autoSWE reads the branch build; on red it feeds the real
   failure text back into a `/fix` run and retries, bounded by an attempt budget.

**The governing constraint (non-negotiable):** neither feature may introduce provider-specific
behaviour above the `autoswe/providers/` seam. Everything new is expressed as (a) a normalized
dataclass in `providers/base.py`, (b) a `VCSProvider`/`IssueTracker` protocol method, or (c) a
**declared capability**. `orch/`, `vcs/`, and `harness/` never learn the words "GitHub" or "Azure".

---

## 0. Why capabilities come first

The two platforms are *not* symmetric, and (pre-P0) the asymmetry was expressed as a **silent
no-op**: `AzureVCS.link_branch_to_issue` returned `None`, and a broken CI API call returned
`CIStatus(state="none")` which the gate read as "pass". (Since #244 the broken-API path returns
`CIStatus(state="error")`, which the gate blocks on — see §2.1.) `base.py` documents the
no-inheritance trade-off honestly, but the GitHub review's F-2 and the Azure review's F-2a are the
same bug wearing two hats: **absence and failure are indistinguishable at the seam.**

Homogenizing means making the difference *explicit and queryable*, not making it invisible. The
codebase already has exactly this idiom one layer over — `harness/backends` declares capabilities
(`session_fork`, MCP, read-only enforcement) and handlers degrade deliberately. Mirror it:

```python
# providers/base.py
class Capability(StrEnum):
    BRANCH_LINK         = "branch_link"          # issue/WI -> branch, platform-managed
    PR_ISSUE_LINK       = "pr_issue_link"        # PR -> issue/WI, machine-readable
    AUTO_CLOSE_ON_MERGE = "auto_close_on_merge"  # merge closes the issue, no extra call
    CI_PER_COMMIT       = "ci_per_commit"        # CI verdict addressable by SHA
    CI_LOGS             = "ci_logs"              # failure text retrievable via API
    MERGE_STATUS        = "merge_status"         # mergeability readable
```

Both protocols gain `capabilities() -> frozenset[Capability]`. `factory.get_vcs` asserts structural
Protocol conformance at construction (fail at wiring, not at dispatch) — closing GitHub review F-10.

| Capability | GitHub | Azure DevOps |
|---|---|---|
| `BRANCH_LINK` | ✅ GraphQL `createLinkedBranch` (implemented) | ⚠️ see §1.3 — verify `ArtifactLink` relation, else absent |
| `PR_ISSUE_LINK` | ✅ closing keyword in PR body | ✅ `workItemRefs` on PR create/update (**not implemented today**) |
| `AUTO_CLOSE_ON_MERGE` | ✅ `Fixes #N` | ❌ no mechanic exists — autoSWE must transition state explicitly |
| `CI_PER_COMMIT` | ✅ check-runs / `actions/runs?head_sha=` | ⚠️ builds are branch-queried; `sourceVersion` gives SHA correlation |
| `CI_LOGS` | ✅ jobs → steps → logs; annotations | ✅ timeline → task logs |
| `MERGE_STATUS` | ✅ `mergeable` / `mergeable_state` | ✅ `pullRequests/{id}/status.mergeStatus` |

Rule for consumers: **a missing capability produces a logged, user-visible one-time note — never a
silent skip and never a fabricated pass.**

---

## 1. Part One — Complete cross-linkage

### 1.1 The edge matrix

| # | Edge | GitHub mechanism | Azure mechanism | Today | Plan |
|---|---|---|---|---|---|
| E1 | issue → branch | `createLinkedBranch` GraphQL | Development control; no documented REST (§1.3) | GH ✅ / ADO ✖ | keep GH; probe ADO |
| E2 | commit → issue | `#N` / `Refs #N` in commit message | `#1234` in commit message (auto-trigger) | neither | **add trailer to `commit_and_push` message** |
| E3 | PR → issue | `Fixes #N` first line of body | `workItemRefs: [{id}]` on create/update | GH ✅ / ADO ✖ | **add ADO `workItemRefs`** |
| E4 | issue → PR (reverse view) | derived from E3 | derived from E3 | follows E3 | verification only |
| E5 | merge → issue closed | closing keyword, automatic | **nothing** — must PATCH `System.State` | GH ✅ / ADO ✖ | **add `close_issue`** |
| E6 | build → PR/commit | `check_runs[].pull_requests[]`, `actions/runs.head_sha` | build `sourceVersion` / `reasonFilter=pullRequest` | unused | consumed by Part Two |

Three real gaps, all Azure-side, all one-field fixes; plus one shared gap (E2) that costs a commit
trailer and buys the commit↔issue "Development" association on both platforms.

### 1.2 New protocol surface

```python
# providers/base.py
@dataclass
class LinkageState:                 # normalized answer to "how linked is this task?"
    branch_linked: bool = False
    pr_linked: bool = False         # PR <-> issue machine-readable link present
    closes_on_merge: bool = False   # merging will close the issue with no further action
    pr_number: int | None = None
    head_sha: str | None = None
    merge_state: Literal["clean", "conflicts", "pending", "unknown"] = "unknown"
    missing: tuple[str, ...] = ()   # edge names that could not be established

class VCSProvider(Protocol):
    def link_pr_to_issue(self, issue_number: int, pr_number: int) -> None: ...
    def get_linkage(self, issue_number: int, branch: str, pr_number: int | None) -> LinkageState: ...
    def commit_trailer(self, issue_number: int) -> str: ...   # "Refs #12" / "#12"

class IssueTracker(Protocol):
    def close_issue(self, issue_number: int, reason: str = "completed") -> None: ...
```

`commit_trailer()` is deliberately a provider method: the *convention* differs per platform and the
worktree layer must not know which. `close_issue` on GitHub is a real API call used only when
`AUTO_CLOSE_ON_MERGE` is absent or the keyword failed to register (`state=closed` +
`state_reason=completed|not_planned`); on Azure it PATCHes `System.State`, which needs §1.5.

### 1.3 Azure branch link — probe, don't assume

`workitem-pr-linking-and-builds.md` §2.2 states there is no REST endpoint for branch↔work-item
links. The generic relations API *may* accept an `ArtifactLink` relation with a
`vstfs:///Git/Ref/{projectId}%2F{repoId}%2FGB{branch}` URL. **This is unverified.** Action: one
`@pytest.mark.live` probe against the real org before writing any code path. If it works, ADO
declares `BRANCH_LINK` and gains a real `link_branch_to_issue`; if not, the no-op stays but becomes
a *declared* absence with a one-line note in the welcome comment, not silence (closes F-11a).

### 1.4 `ensure_links` — one idempotent module, three call sites

New `autoswe/vcs/linkage.py`:

```python
def ensure_links(task, repo_cfg, cfg, *, phase) -> LinkageState
```

Called at **branch create** (`worktree.create_worktree`, E1 — where the GitHub call already lives),
**PR open** (`adapter.apply_effect` create_pr and `ship.open_pr`, E3+E4), and **CI-green / merge
observation** (§2, E5). It calls `get_linkage()` first and issues only the writes for edges that are
missing → naturally idempotent, cheap on the steady-state path, and self-healing after a crash or a
hand-edited PR body.

Persisted on the queue entry (registered in `TASK_FIELDS`, the single source of truth for the
queue↔`TaskState` mapping):

```
linkage_state   : dict   # last LinkageState, for /sync reporting + heal decisions
linkage_missing : list   # declared-unsupported or failed edges (reported once)
```

`python autoswe.py queue status` and the `/sync` comment render this as a checklist, so an operator
can see at a glance which edges exist on a given task.

### 1.5 Azure done state — resolution order and the read/write invariant

Azure has no universal "done". The completed state depends on the **process template** and, in
Scrum, on the **work item type**:

| Process | Completed state | Notes |
|---|---|---|
| Basic | `Done` | To Do / Doing / Done |
| Agile | `Closed` | New / Active / Resolved / Closed — same for Bug, User Story, Task, Issue |
| Scrum | `Done` | PBI & Bug: New / Approved / Committed / Done / Removed; Task: To Do / In Progress / Done |
| CMMI | `Closed` | Proposed / Active / Resolved / Closed |
| Inherited / custom | anything | an org can rename or add states freely |

**autoSWE already hardcodes a done set — on the read side.** Two places assume it today:

- `azure/tracker.py:138` — the WIQL discovery query: `WHERE [System.State] NOT IN ('Closed','Done','Removed')`
- `azure/tracker.py:_to_normalized` — `state = "closed" if raw_state in ("Closed","Done","Removed")`

That set covers Agile/CMMI (`Closed`), Basic/Scrum (`Done`), and `Removed`, which is why the poller
works across processes today. It also creates a hard invariant the moment we start *writing* state:

> **The value `close_issue` writes MUST be a member of the set the read side treats as terminal.**
> Otherwise autoSWE closes the work item, the next poll still sees it as open, and it is rediscovered
> forever — a self-inflicted loop with a real cost per cycle.

So the two sides become one config pair, validated against each other at config load (a `done_state`
outside `done_states` is a startup error, not a runtime surprise):

- **`done_states`** — the terminal set for reads. Default `["Closed", "Done", "Removed"]`, i.e. the
  set already hardcoded, lifted into config. The literals in `tracker.py` are replaced by it.
- **`done_state`** — the single value writes use.

**Resolution order for `done_state`** (first hit wins):

1. **Per-repo** — `done_state` in the `repos.json` entry. This already works with no new plumbing:
   `factory.build_repo_cfg` does `rcfg.update(repos_cfg[repo_key])`, so any key in a repo's entry
   lands on `repo_cfg` verbatim. Same for `done_states`.
2. **Global** — `done_state` in cfg (env / config.json), resolved with the existing
   repo-override-beats-cfg helper (`pr_gate._flag`'s pattern, generalised to non-boolean values).
3. **Runtime discovery** — `GET {org}/{project}/_apis/wit/workitemtypes/{type}/states?api-version=7.1`
   returns each state with a `category` (`Proposed` / `InProgress` / `Resolved` / `Completed` /
   `Removed`). Pick the `Completed`-category state. This is the *correct* answer for any process,
   including custom ones, and it needs only `vso.work` read scope — unlike the process-level
   endpoint, which needs process admin. Cache per `(project, work item type)`; the type comes from
   `System.WorkItemType`, which means `_to_normalized` should start carrying it on `NormalizedIssue`
   (it does not today).
4. **Fallback** — `"Closed"`, with the failure handled loudly rather than by guessing: on a 400 from
   the PATCH, log the discovered state list and post a one-time comment telling the operator to set
   `done_state` in `repos.json`. autoSWE never retries a different state blindly — a state write is
   visible to humans and a wrong one is worse than none.

Two caveats that stay caveats: some processes require `System.Reason` alongside the state, and a
customized process can forbid a direct jump to Completed (transition rules). Both surface as a 400
with a rule-validation message, which is exactly what step 4 reports. If more than one state carries
the `Completed` category, discovery logs all of them and takes the first — that ambiguity is the
signal to set the value explicitly.

To keep the seam clean, none of this is visible above the provider: `IssueTracker.close_issue(
issue_number, reason)` takes GitHub's vocabulary (`completed` / `not_planned`), and the Azure
implementation maps `completed` → the resolved `done_state` and `not_planned` → the
`Removed`-category state (or `done_state` when the process has none).

---

---

## 2. Part Two — CI feedback loop

### 2.1 Hardening the signal first (blocking prerequisite)

> **Status (P0, #244):** the `CIStatus` hardening below — the `error`/`head_sha`/`stale`/`url`/
> `neutral` fields, the GH `actions/runs` 403 fallback, ADO `sourceVersion` staleness,
> `PR_CI_ERROR_POLICY`, and the two flipped fail-open tests — **is landed**. The `CIFailure` /
> `get_ci_failures()` feedback-text method (§2.1's last block) is **deliberately deferred** — it has
> no P0 consumer and would be dead code until the auto-fix loop lands.

An auto-fix loop built on a fail-open signal is worse than no loop: an API 403 currently reads as
"no CI" → "pass". Fix `CIStatus` before anything consumes it more widely.

```python
@dataclass
class CIStatus:
    state: Literal["success", "pending", "failure", "none", "error"]
    head_sha: str | None = None     # the commit this verdict is FOR
    stale: bool = False             # verdict is for a different commit than requested
    url: str | None = None          # clickable run / build
    total: int = 0
    failing: list[str] = ...
    neutral: int = 0                # counted, no longer collapsed into "none"
    pending_count: int = 0
    summary: str = ""
```

- `"error"` — the API could not be consulted. **Never** treated as pass, never triggers an auto-fix.
  `pr_gate` blocks on it, governed by `PR_CI_ERROR_POLICY = block|open` (default `block`).
- GitHub: unresolvable branch head → `error`, not `none`. Add the documented PAT-friendly fallback
  `GET /actions/runs?head_sha=…` when check-runs answers 403 (the private-repo + classic-PAT case
  the project's own doc records) — otherwise the gate is vacuous on the primary deployment.
- Azure: honour `ref_sha` — compare the latest build's `sourceVersion`; on mismatch return
  `stale=True` with `state="pending"` (a build for the right commit is presumably coming), never a
  false green or a false red. `canceled` stays failure (existing pin), but a *stale* canceled build
  no longer blocks forever.
- Tests `test_get_ci_status_unresolvable_sha_is_none` and
  `test_get_ci_status_request_error_is_none` flip to `…_is_error` — they currently pin the bug as
  contract, which is the single most important line of this plan.

New method for feedback text, symmetric across providers:

```python
@dataclass
class CIFailure:
    check: str            # job / task / definition name
    url: str | None
    excerpt: str          # trimmed log tail or annotation text

def get_ci_failures(self, branch, ref_sha=None, *, limit=3, max_chars=4000) -> list[CIFailure]
```

GitHub: `actions/runs/{id}/jobs` → failed steps → `logs` (plus check-run `output.annotations`).
Azure: `build/builds/{id}/timeline` → failed records → task logs. Both truncate provider-side so the
orchestrator receives one shape, already budgeted for a prompt.

### 2.2 Where the read happens (keeping `decide()` pure)

`decide()` is a pure function of `World` and must stay that way. So CI is read in the **read path**,
not inside the decision:

- New `adapter.read_ci(vcs, task_entry) -> CIStatus | None`, called from `_single_poll` **only** for
  eligible tasks: `status in CI_WATCH_STATUSES` (`fixed`, `shipped`, `synced`, `ci_failed`) **and**
  a branch exists. One API call per watched task per cycle, throttled by `CI_POLL_INTERVAL_SEC`
  (default 120) against a persisted `ci_last_checked` — so a `--drain` loop doesn't hammer the API.
- `World` gains `ci: CIStatus | None` (`None` = not consulted this cycle; a distinct, checkable
  state — mirroring the `comments_fetched` idiom rather than repeating its ambiguity).
- Failure text (`get_ci_failures`) is fetched **lazily in Layer B**, only when a CI-triggered fix is
  actually dispatched, so a red build already being handled costs no log downloads.

### 2.3 State machine

New status `ci_failed` (label `autoswe:ci_failed`, red, "CI red on pushed branch"):

- added to `VALID_STATUSES`, `AUTOSWE_LABELS`, and `SHIPPING_BLOCKING_STATUSES` (so `/pr` is refused
  while red, exactly like `test_failed`);
- **non-terminal** — the existing `_check_restart_or_guard` machinery already handles
  `SHIPPING_BLOCKING_STATUSES` for `/fix`, `/retry`, `/skip`, `/abort` and new-comment restarts, so
  a human keeps full manual control with zero new transitions.

`decide()` gains one branch, placed with the existing `rereview_after_fix` auto-dispatch (same
shape, same precedence — before the slash-command scan, and yielding to any newer user command):

| `world.ci.state` | Condition | Action |
|---|---|---|
| `failure` | budget left, `ci.head_sha != task.ci_last_fixed_sha`, no newer user comment | `Action(kind="fix", trigger="ci", guidance=<CI failure block>)` |
| `failure` | budget exhausted | `Action(kind="mark_failed_limit", limit_reason="ci")` → status `ci_failed`, comment asks for a human `/fix` |
| `failure` | `ci.head_sha == task.ci_last_fixed_sha` | noop — never re-fix the same commit twice |
| `pending` / `stale` | — | noop, no comment (no churn) |
| `error` | first occurrence | one-time warning comment, status untouched |
| `success` | `task.status == "ci_failed"` | clear back to the pre-failure status, comment "CI green" |
| `success` | `task.pr_deferred` | re-emit the `create_pr` effect (§2.6) |
| `None` | not consulted | noop |

`emit()` produces the comment (failing checks + excerpt + run link + `attempt n/N`), the
`set_status`, and a `patch_queue` for the CI bookkeeping. **No new `Effect` kind is required** —
`post_comment` / `set_status` / `patch_queue` / `create_pr` already cover it, which is the strongest
sign the design sits in the existing grain.

### 2.4 Attempt budget and loop protection

The dangerous failure mode is push → build → red → fix → push → red → … burning agent runs on a
flaky or agent-unfixable failure. Four independent brakes, defence in depth
(see [safeguards.md](safeguards.md)):

1. **`CI_MAX_FIX_ATTEMPTS`** (default 2) — a *separate* counter `ci_attempt_count`, not the phase
   `attempt_count`, so a CI loop cannot consume the budget a human `/fix` depends on.
2. **SHA watermark** — `ci_last_fixed_sha`. An auto-fix is dispatched at most once per head commit,
   which bounds the loop even if a counter is lost to a crash. This is the structural brake; the
   counter is the policy one.
3. **Reset rule** — `ci_attempt_count` resets to 0 only on a green build or a human command, never
   on a new push by the agent itself.
4. **Config gate** — `CI_AUTO_FIX`, **default on**, per-repo overridable. Turning it off
   downgrades the watch to detect-comment-and-set-`ci_failed`, with recovery via a human `/fix`
   — the escape hatch for a repo with a flaky or permanently red pipeline, not a rollout stage.

Also: never auto-fix on `state="error"`, and never on `stale=True`.

### 2.5 Unifying with the existing post-fix test gate

`harness/test_gate.py` already implements the local half of this loop: run tests after a fix, land
`test_failed` on red, block `/pr`, wait for a human `/fix`. `ci_failed` is its remote twin. Collapse
the recovery policy rather than growing a second one:

```
RECOVERABLE_GATE_STATUSES = {"test_failed", "ci_failed"}     # blocking, auto-fixable
```

Both share the counter (rename `ci_attempt_count` → `gate_attempt_count`), the same reset rule, the
same `AUTO_FIX_ON_GATE_FAILURE` switch, and the same prompt-assembly helper that turns a failure
(local pytest output or `CIFailure[]`) into the fix prompt's failure section. One policy, two
signals — cheap local gate first, remote gate second.

### 2.6 Bonus the watch unlocks: no more "retry `/pr` when green"

Today `pending` CI blocks the PR and tells the user to re-post `/pr`. With a watch running, record
`pr_deferred=True` instead and let the next green observation re-emit the `create_pr` effect. The
human step disappears; the existing idempotency guard (`find_existing_pr`) already makes the
re-emit safe.

---

## 3. Sequencing

Each phase is independently shippable, green-bar, and useful on its own.

| Phase | Content | Risk |
|---|---|---|
| **P0** | `CIStatus` hardening: `error` / `head_sha` / `stale` / `url` / `neutral`; GH `actions/runs` fallback; ADO `sourceVersion` correlation; `PR_CI_ERROR_POLICY`; flip the two fail-open tests | Low — the behaviour change is "the gate stops passing vacuously"; a bad PAT now blocks instead of shipping blind (intended, config-escapable) |
| **P1** | `Capability` enum + `capabilities()` + factory conformance assert; `LinkageState`; `linkage.py`; ADO `workItemRefs`; commit trailer (E2); `close_issue` + `done_state`; ADO branch-link live probe | Low — additive; each write is idempotent and best-effort |
| **P2** | `read_ci` + `World.ci` + throttle + `ci_last_checked`; **no decisions taken** — `/sync` and `queue status` merely report CI | Very low — read-only |
| **P3** | `ci_failed` status + label + `SHIPPING_BLOCKING_STATUSES`; comments; human `/fix` recovery | Medium — new status touches decide / emit / labels / queue |
| **P4** | `CI_AUTO_FIX`: auto-dispatch, budget, SHA watermark, `get_ci_failures` → prompt | Medium-high — spends agent runs. Ships **on**; the brakes in §2.4 are what make that safe, so P4 does not land until all four are tested (including the transition rows for budget-exhausted and same-SHA) |
| **P5** | Gate unification (§2.5); `pr_deferred` auto-resume (§2.6) | Low |

---

## 4. Configuration additions

| Key | Where | Default | Meaning |
|---|---|---|---|
| `PR_CI_ERROR_POLICY` | cfg + repo override | `block` | what a `CIStatus.error` does to the PR gate |
| `CI_WATCH` | cfg + repo | `true` | enable the poll-time CI read |
| `CI_POLL_INTERVAL_SEC` | cfg | `120` | per-task throttle on `read_ci` |
| `CI_AUTO_FIX` | cfg + repo | `true` | auto-dispatch `/fix` on red |
| `CI_MAX_FIX_ATTEMPTS` | cfg + repo | `2` | CI-triggered fix budget (separate from `MAX_ATTEMPTS`) |
| `CI_LOG_MAX_CHARS` | cfg | `4000` | failure text budget handed to the fix prompt |
| `LINK_COMMIT_TRAILER` | cfg | `true` | append the provider commit trailer (E2) |
| `AUTO_CLOSE_ON_MERGE` | cfg + repo | `true` | call `close_issue` where the platform won't |
| `done_state` | cfg + `repos.json` (Azure) | discovered, else `Closed` | state to write on close — see §1.5 |
| `done_states` | cfg + `repos.json` (Azure) | `["Closed", "Done", "Removed"]` | states autoSWE reads as terminal — see §1.5 |

Per-repo overrides keep using `pr_gate._flag`, extended to accept both casings and warn on unknown
keys (GitHub review F-8).

---

## 5. Testing plan

Per the mandatory convention table in `CLAUDE.md`:

| Change | Test file |
|---|---|
| `CIStatus` shape, GH check-runs / actions-runs fallback, `get_ci_failures` | `test_github_provider.py` |
| ADO `sourceVersion` staleness, `workItemRefs`, `close_issue`, branch-link probe | `test_azure_vcs.py`, `test_azure_tracker.py` |
| Gate behaviour on `error` / `stale`, `PR_CI_ERROR_POLICY`, `pr_deferred` | `test_pr_gate.py` |
| `read_ci` eligibility, throttle, `World.ci` plumbing, `apply_effect` linkage calls | `test_provider_adapter.py` |
| CI decide branches (all rows of §2.3) | `test_decide.py` + new `tests/fixtures/decide/ci_*.json` |
| `ci_failed` comments / effects, budget-exhausted path | `test_emit.py` + `tests/fixtures/emit/` |
| `autoswe:ci_failed` label + status mirroring | `test_lifecycle_labels.py` |
| Handler return values for a CI-triggered fix | `test_dispatch_status.py`, `test_coder_returns.py` |
| Gate unification, shared prompt assembly | `test_test_gate.py` |
| New config keys and repo overrides | `test_config.py` |
| Capability declarations + factory conformance | `test_provider_factory.py`, `test_fake_parity.py` |

**Mandatory additions:**

- `TRANSITIONS` rows in `tests/scenarios/transitions.py` — parametrised over `["github","azure"]` —
  for: red build → auto-fix; red build with budget exhausted → `ci_failed`; green after red →
  cleared; `error` → no action; stale build → no action; `/pr` refused while `ci_failed`. The backend
  axis (`CODEX_TRANSITIONS`) is not needed — nothing here is backend-divergent.
- **Canonical API fixtures** in `tests/fixtures/api/` for every new endpoint (GH `check-runs` 403,
  `actions/runs?head_sha`, `runs/{id}/jobs`, logs; ADO `builds` with `sourceVersion`, `timeline`, PR
  `workitems`, PR `status`), with `GitHubFake` / `AzureFake` serving from them so the fakes cannot
  drift from production payloads.
- **Live cases** in `tests/e2e/` for the two things offline tests cannot prove: the ADO branch-link
  probe, and a real red → auto-fix → green cycle on the test project.

---

## 6. Open questions / risks

1. **ADO branch links** — unverified (§1.3). Blocks nothing; resolve with the live probe before P1
   code.
2. **ADO done state** — process-dependent (§1.5). Resolution is config → discovery → `Closed`, and
   the write value is validated against the read-side terminal set at config load, because a
   mismatch causes permanent rediscovery of a closed work item. `System.Reason` requirements and
   transition rules in custom processes still surface as a 400; that path reports and stops rather
   than guessing another state.
3. **Cost.** Every auto-fix is a full agent run. `CI_MAX_FIX_ATTEMPTS=2` plus the SHA watermark caps
   it at two runs per commit per issue; the interaction with `MAX_ATTEMPTS` is deliberately
   decoupled (§2.4, brake 1).
4. **Flaky CI** burns the budget on a failure the agent cannot fix. Optional later refinement:
   require the same check to fail on two consecutive polls before dispatching. Not in P4 — measure
   first.
5. **Rate limits.** The watch adds one call per watched task per cycle, throttled. GitHub's
   `_gh_request` backoff already covers it and the Azure client retries 429 with `Retry-After`.
   Worth knowing: `_gh_request`'s primary-limit path can sleep in-process up to the reset window, so
   a large watch set on an exhausted token stalls a cycle rather than deferring — acceptable at
   current scale, revisit if the watch set grows.
6. **Comment noise.** Only state *changes* comment (red → `ci_failed`, green → cleared). `pending`,
   `stale`, and repeated identical failures stay silent.
7. Shared shipping-blocking semantics mean a repo with a permanently broken pipeline can wedge every
   task at `ci_failed`. `CI_WATCH=false` per repo is the escape hatch; the welcome comment should
   say so.

---

## 7. Docs to update alongside the code

`data-model.md` (queue fields: `ci_*`, `linkage_state`, `pr_deferred`), `labels.md`
(`autoswe:ci_failed`), `providers.md` (capabilities, new protocol methods, edge matrix),
`pipeline.md` (`read_ci` in the poll cycle), `handlers.md` (CI-triggered fix), `safeguards.md`
(the four brakes), `config.md` (§4 table), `testing.md` (new fixtures + transition rows).
