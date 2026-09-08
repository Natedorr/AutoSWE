# Reporting findings

One issue per finding, filed in the **autoSWE repository** — not in the test project. The test
project's issue stays open with its label untouched: it is the evidence.

A finding is real when the observed behaviour contradicts the case file **and** the docs the
case file points at. If the docs say what happened is correct, the case file is what is wrong —
file that instead, against this directory.

---

## Template

```markdown
**Case:** E2E-NN — <case title>
**Pass:** A-claude | B-codex | C-mixed | D-pi
**Provider:** github | azure
**Test issue:** <link to the issue in the test project>
**Step:** <n> — <what openclaw posted>

### Expected
<the step's expected state and assertions, quoted from the case file>

### Observed
<the label that appeared, the comments autoSWE posted, the state of the branch/PR>

### Evidence
- label: `autoswe:<value>` at <time>
- comments: <links or quoted excerpts>
- branch `autoswe/issue-<N>`: <commits, or none>
- PR: <link, or none>

### Why this is wrong
<the doc line it contradicts — file and quote, e.g. docs/autoswe/labels.md: "decide() refuses
/pr in both gating states">

### Severity
blocking | wrong-state | cosmetic | soft
```

## Severity

| Level | Means |
|---|---|
| **blocking** | the case cannot proceed: a stall, a crash, `autoswe:error`, or a state the machine has no route out of |
| **wrong-state** | the case moved, but to the wrong state, or by the wrong route |
| **cosmetic** | right state, right route, but the visible narration is wrong — a missing refusal comment, a question folded into the progress comment, a wrong label |
| **soft** | a model-judgment assertion was not met. Report it, flag it for a human, and do not treat it as a regression on its own |

## Findings that are not bugs

- A **backend divergence** already documented in the case's *Backend notes* or in
  [`MATRIX.md`](MATRIX.md). If a case is green under pass A and red under another pass, that is
  a backend-binding report — say which pass, and do not file it as a state-machine bug.
- A **model doing a poor job of a trivial change**. The change is not what is under test. File
  it only if the poor output made the state machine take a wrong turn.
- A **stall caused by the poller being down**. Confirm autoSWE is actually running before
  reporting a case as stalled.

## The run summary

When the pass ends, post one summary — as a comment on the tracking issue, or as its own issue:

```markdown
## Live E2E pass <label> — <date>

Backends: plan=<...> fix=<...> review=<...> · Provider: <...> · Project: <owner/repo>

| Case | Verdict | Finding |
|---|---|---|
| E2E-01 | pass | |
| E2E-09 | fail | #<n> |
| E2E-03b | skipped | backend does not support it |

**<n> passed · <n> failed · <n> skipped · <n> stalled**
```

Verdicts: `pass`, `fail`, `soft` (passed with a model-judgment caveat), `skipped` (not
applicable to this pass), `stalled` (no progress across three wake-ups).

Then **delete the openclaw cron** — see [`README.md`](README.md) step 6.
