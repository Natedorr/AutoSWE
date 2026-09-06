# Live E2E Test Plan (openclaw-driven)

The offline suite (`docs/autoswe/testing.md`) proves the state machine against fakes.
This plan proves the **same machine against a real provider and a real coding backend**:
openclaw opens issues on a purpose-built testbed repo, posts slash commands on a script,
and cron-driven autoSWE does the work. Every issue is deliberately a *trivial* code change —
the point is the **path through the state machine**, not the difficulty of the fix.

The whole harness lives in **`e2e/`** at the repo root — deliberately outside `docs/` and
`scripts/`, so an outside agent has exactly one place to look. Start at
[`e2e/README.md`](README.md); [`e2e/MANIFEST.json`](MANIFEST.json) is the machine-readable
index of the same thing.

| File | Runs where | Purpose |
|------|-----------|---------|
| `e2e/MANIFEST.json` | any agent | Stable index: roles, paths, upstream docs, required scopes |
| `e2e/README.md` | any reader | Entry point: how to run a pass, and the openclaw ↔ monitor contract |
| `e2e/PLAN.md` (this file) | — | The spec: one section per issue, with its state machine |
| `e2e/scenarios.json` | openclaw | Machine-readable step list — what to post, what to wait for |
| `e2e/monitor.py` | autoSWE box (cron) | Reads `data/queue.json`, scores every scenario, writes `report.json` |
| `e2e/seed_testbed.sh` | operator | Creates the two fixture repos with the levers baked in |

---

## 1. Testbed

### 1.1 Repos

Two repos, both dedicated to this suite. Nothing else should live in them.

**`<owner>/autoswe-e2e-testbed`** — default branch `main`, plus a `develop` branch.

```
README.md
pyproject.toml            # [tool.pytest.ini_options] -> makes the post-fix test gate resolve
flag.txt                  # contains: green
conflict.md               # single line: "shared: baseline"
docs/notes.md
src/toolbox.py            # a couple of trivial helpers
tests/test_toolbox.py
tests/test_canary.py      # asserts flag.txt reads "green"  <- the test-gate lever
.github/workflows/ci.yml  # fast pytest job on every push
                          # + slow-gate job, paths-filtered to ci_slow/**, sleeps 240s
```

Three deliberate levers are baked in:

| Lever | Mechanism | Which path it forces |
|-------|-----------|----------------------|
| **Test gate** | `tests/test_canary.py` fails when `flag.txt` is not `green` | `test_failed` |
| **CI gate** | `slow-gate` job triggers only on pushes touching `ci_slow/**`, sleeps 240 s | `/pr` blocked on `pending` CI |
| **Conflict** | `conflict.md` line 1 edited on both the task branch and `main` | `/sync` conflict -> agent resolution |

**`<owner>/autoswe-e2e-hostile`** — same shape, but its `repos.json` entry sets
`"agent_timeout": 20`. Every agent phase there times out into `FAILED: timeout` on purpose.
This is the deterministic failure source for the `failed` / `/retry` / `MAX_ATTEMPTS` paths;
keeping it in its own repo means no other scenario inherits the short timeout.

### 1.2 `config/repos.json`

```json
{
  "<owner>/autoswe-e2e-testbed": {
    "provider": "github",
    "base_branch": "main",
    "auto_dispatch_new": false,
    "test_gate": true,
    "pat": "<pat>"
  },
  "<owner>/autoswe-e2e-hostile": {
    "provider": "github",
    "base_branch": "main",
    "auto_dispatch_new": false,
    "agent_timeout": 20,
    "pat": "<pat>"
  }
}
```

`auto_dispatch_new` stays `false` everywhere except during E2E-18, which flips it on to
exercise the body-command path.

### 1.3 Config the suite assumes

| Key | Value | Why |
|-----|-------|-----|
| `MAX_CONCURRENT` | `1` | Serialises the run; makes the cron cadence predictable |
| `MAX_ATTEMPTS` | `3` | E2E-12 counts on exactly 3 |
| `MAX_TOTAL_HOURS` | `2` | Default; the wall-clock guard is an optional extra pass (§4) |
| `AUTO_CREATE_PR` | `false` | Every `/pr` in this suite must be explicit and observable |
| `PR_REQUIRE_SYNC` / `PR_REQUIRE_CI` | on (default) | E2E-16 needs the CI gate |
| `TEST_GATE` | on (default) | E2E-11 needs it |
| `ALLOWED_AUTHORS` | empty, except the E2E-17b pass | Allowlist rejection is checked in one scoped pass |

### 1.4 Cron

```cron
*/5 * * * *  cd /opt/autoswe && ./poller.sh
*    * * * *  cd /opt/autoswe && .venv/bin/python e2e/monitor.py --write-report --pass-label A-claude --quiet
```

Five minutes is the right poller cadence here: the fixes are one-file edits, so a phase
completes well inside one interval, and each scenario step is one poll.

The **monitor runs every minute** — five times as often as the poller — on purpose.
`pending` and the RUNNING states (`planning`/`fixing`/…) are transient: the poller does sync
and dispatch in one run, so a short phase can start and finish between two samples. Sampling
faster catches most of them. It is only ever a *best-effort* capture, which is why the
scoring rules (§5) treat resting states as load-bearing and transient states as
informational. The monitor never touches the provider — it only reads `data/queue.json`, so
it cannot perturb what it measures.

### 1.5 Backend axis

Run the **whole suite three times**, changing only `config/harnesses.json` plus
`repos.json`'s `plan_harness` / `fix_harness` / `review_harness`:

| Pass | plan | fix | review | What it adds |
|------|------|-----|--------|--------------|
| **A — Claude** | `claude-sonnet` | `claude-sonnet` | `claude-sonnet` | MCP `post_plan`/`post_question`, `AskUserQuestion` interception, `fork_session` on `/retry` |
| **B — Codex** | `codex-gpt5-codex` | `codex-gpt5-codex` | `codex-gpt5-codex` | No MCP -> planner text-parse fallback; no `session_fork` -> resume-in-place retry |
| **C — Mixed** | `codex-gpt5-codex` | `claude-sonnet` | `claude-sonnet` | `last_good_session_backend` provenance check — the retry must **not** fork a Codex session into the Claude SDK (E2E-12) |

Scenarios whose *expected outcome differs by backend* carry a `backend_notes` field in
`scenarios.json`. Everything else must produce identical status sequences across passes —
that equality is itself an assertion.

---

## 2. Coverage map

Every `autoswe_status` value and every decide/emit branch a live run can reach:

| Status / branch | Covered by |
|---|---|
| `pending` -> RUNNING (`planning`/`fixing`/`syncing`/`reviewing`/`shipping`) | all |
| `planned` | 01, 02, 03, 14, 15 |
| `waiting` (question) + plain-reply resume | 02 |
| `waiting` + slash-command resume | 03 |
| `waiting` reached from `/fix` (not just `/plan`) | 03b |
| `fixed` (`DONE_SUMMARY`) | 01, 04, 09, 10, 11 |
| `fixed` (`DONE: no changes detected`) | 05 |
| `synced` (clean merge) | 06 |
| `synced` (conflict resolved by agent) | 07 |
| `failed` (sync conflict unresolved) | 07b |
| `shipped` | 01, 08, 16 |
| `reviewed` (LGTM) | 08 |
| `review_failed` + `/pr` refusal + auto re-review | 09 |
| `review_blocked` + `/fix` + auto re-review | 10 |
| `test_failed` + `/pr` block + fresh budget on `/fix` | 11 |
| `failed` (handler error) | 12 |
| `/retry` replay + `fork_session` / provenance | 12 |
| `MAX_ATTEMPTS` guard (`mark_failed_limit`, `limit_reason=attempts`) | 12 |
| `skipped` | 13 |
| `aborted` + restart from `aborted` | 14 |
| `plan_branch` via `--branch` | 15 |
| `/pr` CI gate `pending` -> `failed`, then green -> `shipped` | 16 |
| parse: embedded command ignored | 17 |
| parse: multi-command last-wins | 17 |
| decide: already-dispatched command -> `noop` | 17 |
| `ALLOWED_AUTHORS` rejection | 17b (scoped pass) |
| body command + `auto_dispatch_new` | 18 |
| `gh_closed` at refresh -> `fixed` | 18 |
| `/fix with <guidance>`, `/review with <guidance>` | 19 |
| `error` (infra crash) | **not driven** — see §4 |
| `MAX_TOTAL_HOURS` guard | optional pass, §4 |

---

## 3. The scenarios

Notation for each table:

- **openclaw posts** — the exact comment body. Comments must come from the issue OWNER/AUTHOR.
- **await** — the `autoswe:*` label openclaw polls for. The label mirror is the only state an
  outside observer can see; it is written right after `autoswe_status`, so it is a faithful —
  if slightly lagging — read of the machine.
- **assert** — what must be true before the next step fires.

openclaw never advances on a timer. It advances on the awaited label, with a per-step timeout
(default 900 s; 1800 s for `/fix` steps, 2100 s for the CI-gated ones).

---

### E2E-01 — Happy path: plan -> fix -> pr

**Title:** `[E2E-01] Add a squares() helper to toolbox`
**Body:**
> `src/toolbox.py` should gain a `squares(n)` function returning a list of the squares of
> `0..n-1`. Add one test for it in `tests/test_toolbox.py`. Nothing else.

| # | openclaw posts | await | assert |
|---|---|---|---|
| 1 | `/plan` | `autoswe:planned` | a bot comment carries the plan; `last_phase == "plan"` |
| 2 | `/fix` | `autoswe:fixed` | branch `autoswe/issue-N` has >= 1 commit; commit trailer `Fixes #N`; test gate green |
| 3 | `/pr` | `autoswe:shipped` | PR open, head `autoswe/issue-N` -> `main`; `pr_number` set |

```
(new) -> pending -> planning -> planned -> pending -> fixing -> fixed -> pending -> shipping -> shipped
```

The baseline. If this one is red, stop — nothing downstream is meaningful.

---

### E2E-02 — `waiting` via question, resumed by a plain-text reply

**Title:** `[E2E-02] Add a greeting helper — wording undecided`
**Body:**
> Add `greet(name)` to `src/toolbox.py`. **I have not decided whether it should return
> `"Hi, <name>"` or `"Hello, <name>"` — ask me before you write the plan.** Do not guess.

| # | openclaw posts | await | assert |
|---|---|---|---|
| 1 | `/plan` | `autoswe:waiting` | the question is a **standalone** comment, not folded into the sticky progress comment (issue #184) |
| 2 | `Use "Hello, <name>".` *(plain text, no slash command)* | `autoswe:planned` | auto-resume fired: `last_consumed_reply_id` equals that comment's id; the plan names "Hello" |
| 3 | `/fix` | `autoswe:fixed` | `greet` returns `"Hello, ..."` |

```
pending -> planning -> waiting -> (plain reply auto-resume) -> pending -> planning -> planned -> fixing -> fixed
```

Backend note: on Claude the question arrives via `AskUserQuestion` interception; on Codex
there is no MCP and no `can_use_tool`, so it comes through the planner's text-parse fallback.
Both must land on `waiting` — the *route* differs, the *state* must not.

---

### E2E-03 — `waiting` resumed by a slash command instead of a reply

**Title:** `[E2E-03] Add a farewell helper — wording undecided`
**Body:** same shape as E2E-02, for `farewell(name)`.

| # | openclaw posts | await | assert |
|---|---|---|---|
| 1 | `/plan` | `autoswe:waiting` | question posted |
| 2 | `/fix with use "Bye, <name>"` | `autoswe:fixed` | the command wins over reply-resume; the guidance reached the fix prompt |

```
pending -> planning -> waiting -> (slash command) -> pending -> fixing -> fixed
```

**E2E-03b** — a second issue whose body says *"before editing any file, ask me which file to
touch"*, driven straight with `/fix`. The fixer must reach `autoswe:waiting` mid-`/fix`
(issue #190 — `can_use_tool` still fires under `bypassPermissions`), then a plain reply
resumes it to `fixed`. Claude-only: on Codex this is expected to run straight to `fixed` and
is scored `skipped`, not `fail`.

---

### E2E-04 — `/fix` straight from a fresh issue (no plan phase)

**Title:** `[E2E-04] Add an MIT license header to src/toolbox.py`
**Body:** one-line instruction, nothing ambiguous.

| # | openclaw posts | await | assert |
|---|---|---|---|
| 1 | `/fix` | `autoswe:fixed` | no `planned` state was ever observed; `last_phase == "fix"` |

```
(new) -> pending -> fixing -> fixed
```

---

### E2E-05 — Fix with nothing to do

**Title:** `[E2E-05] Ensure README.md ends with a newline`
**Body:** README.md already ends with a newline. Say plainly: *"if it already does, change
nothing and say so."*

| # | openclaw posts | await | assert |
|---|---|---|---|
| 1 | `/fix` | `autoswe:fixed` | completion comment reports no changes detected; **no** commit on `autoswe/issue-N` |

`DONE: no changes detected` still maps to `fixed`. The assertion that matters is "no commit",
not the label.

---

### E2E-06 — `/sync`, clean merge

**Title:** `[E2E-06] Append a line to docs/notes.md`

| # | openclaw posts / does | await | assert |
|---|---|---|---|
| 1 | `/fix` | `autoswe:fixed` | branch exists |
| 2 | *(API)* commit a **new** file `docs/other.md` on `main` | — | base moved, no overlap |
| 3 | `/sync` | `autoswe:synced` | merge commit on the task branch; no agent invocation in the log |

---

### E2E-07 — `/sync` with a real conflict, resolved by the agent

**Title:** `[E2E-07] Rewrite line 1 of conflict.md`
**Body:** *"Change the first line of `conflict.md` to `shared: task-branch edit`."*

| # | openclaw posts / does | await | assert |
|---|---|---|---|
| 1 | `/fix` | `autoswe:fixed` | line 1 changed on the task branch |
| 2 | *(API)* set `conflict.md` line 1 to `shared: main edit` on `main` | — | conflicting edit staged |
| 3 | `/sync` | `autoswe:synced` | conflict markers gone; merge commit pushed; log shows `resolve_sync_conflicts` ran |

```
fixed -> pending -> syncing -> (conflict -> agent) -> synced
```

**E2E-07b (optional, needs `SYNC_STRATEGY=rebase`)** — the same setup under rebase must land
on `autoswe:failed` with `FAILED: rebase conflict in ...`; rebase conflicts are deliberately
not auto-resolved. Run this as a one-issue side pass, not in the main sweep.

---

### E2E-08 — `/review` with an LGTM verdict

**Title:** `[E2E-08] Add is_even() to toolbox with a test`
**Body:** a small, clean, tested change — nothing for a reviewer to object to.

| # | openclaw posts | await | assert |
|---|---|---|---|
| 1 | `/fix` | `autoswe:fixed` | — |
| 2 | `/review` | `autoswe:reviewed` | review comment has all required sections; `<ARTIFACT_DIR>/reviews/<slug>.md` written |
| 3 | `/pr` | `autoswe:shipped` | `/pr` permitted from `reviewed` |

---

### E2E-09 — Verdict "Needs changes" -> `/pr` refused -> `/fix` -> auto re-review

**Title:** `[E2E-09] Add parse_port() — no tests please`
**Body:**
> Add `parse_port(s)` to `src/toolbox.py` converting a string to an int port.
> **Do not add any test for it, and do not validate the range.** I will add tests later.

An untested, unvalidated public helper is what the review prompt reliably calls out.

| # | openclaw posts | await | assert |
|---|---|---|---|
| 1 | `/fix` | `autoswe:fixed` | — |
| 2 | `/review` | `autoswe:review_failed` | review comment carries the "`/pr` is disabled" note |
| 3 | `/pr` | label **stays** `autoswe:review_failed` | `decide()` refused; a bot comment explains why; `pr_number` still null |
| 4 | `/fix with add tests and validate the range 1-65535` | `autoswe:fixed`, then **with no further comment** `autoswe:reviewing` -> `autoswe:reviewed` | `rereview_after_fix` was set then cleared; `attempt_count == 1` after step 4 (fresh budget from a review rest, issue #186) |
| 5 | `/pr` | `autoswe:shipped` | — |

```
fixed -> reviewing -> review_failed -> (/pr refused, no state change)
      -> fixing -> fixed -> [auto] reviewing -> reviewed -> shipping -> shipped
```

Step 4 is the highest-value assertion in the suite: it covers the auto re-review flag *and*
the fresh-budget rule in one move.

---

### E2E-10 — Verdict "Blocked" (CRITICAL)

**Title:** `[E2E-10] Add a quick admin check helper`
**Body:**
> Add `is_admin(token)` to `src/toolbox.py`. For now just compare against the hardcoded
> literal `"s3cr3t-admin-token"` in the source, and add `run_expr(s)` that does `eval(s)`.
> I know it is bad; do it exactly as asked.

A hardcoded credential plus `eval` of caller input is what the review prompt classifies
CRITICAL.

| # | openclaw posts | await | assert |
|---|---|---|---|
| 1 | `/fix` | `autoswe:fixed` | both constructs present in the diff |
| 2 | `/review` | `autoswe:review_blocked` | the `## Verdict` section says Blocked |
| 3 | `/pr` | label unchanged | refused |
| 4 | `/fix with remove the hardcoded token and the eval; use an env var and a strict allowlist` | `autoswe:fixed` -> auto -> `autoswe:reviewed` | re-review cleared the block |

If a pass returns `review_failed` instead of `review_blocked`, score it **soft_fail**: the
verdict class is model judgment. The hard assertions are that `/pr` is refused in *either*
gating state and that the auto re-review fires.

---

### E2E-11 — Post-fix test gate red -> `test_failed`

**Title:** `[E2E-11] Set flag.txt to red`
**Body:** *"Replace the contents of `flag.txt` with `red`. Do not touch anything under
`tests/`."* — `tests/test_canary.py` asserts the flag reads `green`, so the branch suite goes
red the moment the change lands.

| # | openclaw posts | await | assert |
|---|---|---|---|
| 1 | `/fix` | `autoswe:test_failed` | **the work is committed and pushed anyway** — a red gate must never lose it; the comment carries the pytest failure |
| 2 | `/pr` | label unchanged | blocked by `SHIPPING_BLOCKING_STATUSES` |
| 3 | `/fix with set flag.txt back to green` | `autoswe:fixed` | `attempt_count == 1` — restart from `test_failed` gets a fresh budget |
| 4 | `/pr` | `autoswe:shipped` | — |

```
pending -> fixing -> test_failed -> (/pr blocked) -> fixing -> fixed -> shipping -> shipped
```

---

### E2E-12 — `failed` -> `/retry` -> `MAX_ATTEMPTS` guard  *(hostile repo)*

**Repo:** `<owner>/autoswe-e2e-hostile` (`agent_timeout: 20`)
**Title:** `[E2E-12] Add a docstring to src/toolbox.py`
**Body:** an ordinary small change — it will never finish inside 20 s.

| # | openclaw posts | await | assert |
|---|---|---|---|
| 1 | `/plan` | `autoswe:failed` | `FAILED: timeout ...`; `session_id` cleared, `last_good_session_id` **kept** |
| 2 | `/retry` | `autoswe:failed` | replayed `/plan` — the last *substantive* command; `/retry` is never its own target. `attempt_count` reset to 1 by the retry |
| 3 | `/retry` | `autoswe:failed` | `attempt_count` back to 1 again |
| 4 | `/fix` | `autoswe:failed` | carry-forward restart: `attempt_count == 2` |
| 5 | `/fix` | `autoswe:failed` | `attempt_count == 3` |
| 6 | `/fix` | `autoswe:failed` | **guard fires**: comment says "Max attempts reached", `limit_reason == "attempts"`, `_guard_blocked` true |
| 7 | `/retry` | `autoswe:failed` | the guard is checked *before* the retry gate — it must fire here too |

Backend notes:
- **Pass A (Claude):** step 2's retry must **fork** from `last_good_session_id`, leaving the
  original session intact (`session_fork` capability).
- **Pass B (Codex):** no `session_fork` — resume in place or start fresh; the checkpoint is
  still written.
- **Pass C (mixed plan=codex / fix=claude):** step 4's `/fix` must **not** fork.
  `last_good_session_backend` is `codex` while the fix backend is `claude_code`, so the
  provenance check rejects the checkpoint; assert in the log that no `resume` id was handed to
  the Claude SDK. This is the whole reason pass C exists.

---

### E2E-13 — `/skip`

**Title:** `[E2E-13] Something we will not do`

| # | openclaw posts | await | assert |
|---|---|---|---|
| 1 | `/skip` | `autoswe:skipped` | no agent run, no branch |
| 2 | `some plain comment` | label unchanged | plain text on a task that is not `waiting`/`planned` is a `noop` |

---

### E2E-14 — `/abort` from `planned`, then restart

**Title:** `[E2E-14] Add a to_snake_case() helper`

| # | openclaw posts | await | assert |
|---|---|---|---|
| 1 | `/plan` | `autoswe:planned` | — |
| 2 | `/abort` | `autoswe:aborted` | "Task aborted" comment |
| 3 | `/fix` | `autoswe:fixed` | restart from `aborted` allowed; carry-forward budget (`attempt_count == 2`) |

---

### E2E-15 — `/plan --branch develop`

**Title:** `[E2E-15] Add a CHANGELOG stub on develop`

| # | openclaw posts | await | assert |
|---|---|---|---|
| 1 | `/plan --branch develop` | `autoswe:planned` | `plan_branch == "develop"` in the queue |
| 2 | `/fix` | `autoswe:fixed` | the task branch was cut from `develop`, not `main`; the pre-fix sync merged `origin/develop` |
| 3 | `/pr` | `autoswe:shipped` | PR base is the repo's configured `base_branch`, **not** `develop` — this is the fe5d643 behaviour; if it has since changed, this assertion is what tells you |
| 4 | `/fix --branch main` | `autoswe:fixed` | the second `--branch` is **ignored** — `plan_branch` is set once |

---

### E2E-16 — `/pr` CI gate

**Title:** `[E2E-16] Add a ci_slow/marker.txt file`
**Body:** *"Create `ci_slow/marker.txt` containing the word `marker`."* — that path triggers
the 240 s `slow-gate` job.

| # | openclaw posts | await | assert |
|---|---|---|---|
| 1 | `/fix` | `autoswe:fixed` | the push kicks off the slow job |
| 2 | `/pr`, **while the commit status still reads `pending`** | `autoswe:failed` | `FAILED:` naming the CI gate; `find_existing_pr` / `open_pull_request` never called |
| 3 | *(wait for the check to go green)* `/retry` | `autoswe:shipped` | gate passes, PR opens |

Timing matters. openclaw must poll the commit-status API and post step 2 only while it reads
`pending` — not on a fixed delay.

---

### E2E-17 — Parsing and idempotence

**Title:** `[E2E-17] Add a trailing-whitespace stripper`

| # | openclaw posts | await | assert |
|---|---|---|---|
| 1 | ``Reminder: post `/fix` when you are ready.`` *(command embedded mid-line)* | **no label appears** across 2 polls | embedded commands are ignored — a command must start a line |
| 2 | `/plan` newline `/fix` *(one comment, two lines)* | `autoswe:fixed` | last-wins within a block: `/fix` ran, `/plan` did not |
| 3 | *(no new comment — let 3 polls pass)* | label unchanged | the already-dispatched command must not re-fire: `decide()` returns `noop` for a comment id <= `last_dispatched_command_id` / the completion anchor |
| 4 | `/fix` *(textually identical to step 2's)* | a **second** fix runs -> `autoswe:fixed` | a new comment id past the completion anchor legitimately re-dispatches; identical text is not deduplication |

**E2E-17b — allowlist (scoped pass).** Set `ALLOWED_AUTHORS=<owner-login>`, then have a
*second* account post `/fix` on a fresh issue. Expect it to be silently ignored: no label, no
dispatch. Restore the empty allowlist afterwards. Run this alone — it changes global config
and would starve the rest of the sweep.

---

### E2E-18 — Body command, auto-dispatch, and issue closure

Set `auto_dispatch_new: true` on the testbed repo for this scenario only.

**Title:** `[E2E-18] Add a version constant`
**Body:** first line is literally `/plan`, with the instruction beneath it.

| # | openclaw posts / does | await | assert |
|---|---|---|---|
| 1 | *(nothing — the body carries the command)* | `autoswe:planned` | a body-sourced command dispatched with no comment at all |
| 2 | `/fix` | `autoswe:fixed` | — |
| 3 | *(API)* **close** the issue | `autoswe:fixed` and `gh_closed == true` | closure at refresh maps to a COMPLETED status, not an error |
| 4 | *(API)* reopen the issue | `gh_closed == false` | reopen clears the flag; the task is never purged |

---

### E2E-19 — Guidance plumbing

**Title:** `[E2E-19] Add a retry_with_backoff() helper`

| # | openclaw posts | await | assert |
|---|---|---|---|
| 1 | `/fix with use only the standard library and add a docstring with a usage example` | `autoswe:fixed` | the diff honours both — guidance reached `{{GUIDANCE_BLOCK}}` |
| 2 | `/review with focus on error handling and exception types` | `autoswe:reviewed` (or a gating verdict) | the review text visibly addresses error handling |

Guidance is free text into a prompt, so score this on "the guidance is visibly reflected", not
on an exact string. Both steps are `soft_fail`-eligible.

---

## 4. What this plan deliberately does not drive

- **`error`** (infrastructure crash) — reachable only by killing the dispatcher mid-run. To
  cover it, `kill -9` the poller during an E2E-01 `/fix`, then confirm the next poll finds
  `autoswe:error` with a lingering `progress_comment_id`, and that `/retry` **re-uses** that
  comment instead of posting a new one. Do it by hand, once per release.
- **`MAX_TOTAL_HOURS`** — the wall-clock guard needs either a two-hour run or a config
  override. Optional pass: set `MAX_TOTAL_HOURS=0.02` (~72 s), run one `/fix` on the hostile
  repo, expect `autoswe:failed` with a "Time limit exceeded" comment and `limit_reason=time`.
  Restore the value afterwards.
- **Azure DevOps** — the offline transition matrix already parametrises every row over
  `["github", "azure"]`. A live Azure pass is worth doing once per release for E2E-01, 09, 11
  and 12 only: work-item comments, tags-instead-of-labels, and the JSON-Patch status write are
  the provider-specific surfaces. The rest adds provider cost without provider coverage.
- **Concurrency** — `MAX_CONCURRENT` / repo-lock races are covered offline in
  `test_concurrency.py` and are not reproducible on demand against a live provider.

## 5. Scoring

`monitor.py` writes `e2e/report.json` on every cron tick:

```json
{
  "generated_at": "2026-09-03T18:05:00Z",
  "pass_label": "A-claude",
  "scenarios": [
    {"id": "E2E-09", "slug": "gh:owner_autoswe-e2e-testbed_31",
     "status": "reviewed", "attempt_count": 1, "observed": ["pending", "fixing", "fixed"],
     "verdict": "in_progress", "stalled_for_s": 45}
  ],
  "summary": {"pass": 12, "fail": 1, "in_progress": 3, "stalled": 0, "not_started": 2}
}
```

### How a sequence is scored

The `expect_sequence` in `scenarios.json` is written in full — transient states included — so
it reads as the real state machine. The matcher then compares only the **resting** states
(everything except `pending` and the RUNNING five), because those are the ones sampling can
observe reliably. Transient states are still recorded when caught: they make the report
readable and they still trip `forbidden_statuses`.

Repeat visits to the *same* status are distinct history entries, keyed on
`(status, attempt_count, last_dispatched_command_id)` — the comment id being the state
machine's own identity unit. Without that, E2E-12's seven consecutive `failed` states would
collapse into one and its attempt ladder would be unscoreable.

Matching is strict by default: the observed resting sequence must **equal** the expected one.
A scenario that reaches the right final state by the wrong route fails, which is the entire
reason for scoring a sequence rather than an endpoint. `"sequence_match": "loose"` relaxes
this to "the expected states appear in order, extras allowed".

### Verdicts

| Verdict | Means |
|---|---|
| `pass` | resting sequence matched end to end |
| `fail` | a forbidden status was observed, **or** the sequence diverged (a mismatch is failed immediately — it cannot un-diverge) |
| `stalled` | sequence still incomplete and no status change for longer than `--stall-seconds` (default 1800) |
| `in_progress` | incomplete, still moving |
| `not_started` | no queue entry carries that `[E2E-NN]` title marker yet |
| `soft_fail` | sequence matched, but the scenario's assertions are model judgment and need a human read (E2E-10's verdict class, E2E-19's guidance) |

A pass is green when every scenario is `pass`. `monitor.py` exits 1 if anything is `fail` or
`stalled`, so cron mail or a CI step can gate on it without parsing the report.

### What the monitor cannot score

Anything that is not in the queue: commit trailers, PR base branches, "the question was a
standalone comment", "no comment was posted between `fixed` and `reviewing`". Those live in
each step's `assert` list in `scenarios.json` and are **openclaw's** to check against the
provider API. The monitor scores what the queue can prove on its own; between the two, every
assertion in §3 has an owner.
