# Operator-assisted cases

These two cannot be driven from the provider side: they need someone at the autoSWE box to
kill a process or change a limit mid-run. openclaw can create the issue and read the outcome,
but the middle step is a human's.

Run them once per release, not once per pass.

---

## OOB-1 — Infrastructure crash → `error`

**Setup:** an ordinary issue, same shape as [E2E-01](E2E-01.md).

| # | who | what |
|---|---|---|
| 1 | openclaw | posts `/fix` and waits for `autoswe:fixing` |
| 2 | **operator** | kills the dispatcher process mid-run |
| 3 | openclaw | waits for the next poll cycle |

**Expected:** the task lands on `autoswe:error` — an infrastructure failure, distinct from
`failed`, which means the agent ran and reported a failure. The progress comment posted before
the crash is still there, and a subsequent `/retry` **re-uses** that comment rather than
posting a fresh one.

**Why:** `error` is the only status reachable purely by the machine falling over, so it is the
only one no ordinary case can cover. The comment-reuse assertion is what keeps a crash loop
from burying an issue in progress comments.

---

## OOB-2 — The wall-clock guard

**Setup:** `MAX_TOTAL_HOURS` temporarily set very low (about 0.02 — roughly 70 seconds), on a
project where a phase will not finish that fast. Restore it afterwards.

| # | who | what |
|---|---|---|
| 1 | **operator** | lowers `MAX_TOTAL_HOURS` |
| 2 | openclaw | posts `/fix` on a fresh issue |
| 3 | openclaw | waits |

**Expected:** `autoswe:failed`, with a comment saying the time limit was exceeded — and the
comment must distinguish this from the attempt guard ([E2E-12](E2E-12.md)) and from an agent
timeout. Three different limits, three different messages.

**Why:** the time guard is the backstop for a task that neither finishes nor fails — the one
kind of runaway an attempt count cannot catch, because each individual attempt looks fine.

---

## Specified in

- [`safeguards.md`](../../../docs/autoswe/safeguards.md) — every limit and what trips it
- [`labels.md`](../../../docs/autoswe/labels.md) — `error` vs `failed`
- [`debugging.md`](../../../docs/autoswe/debugging.md) — recovering a task stuck after a crash
