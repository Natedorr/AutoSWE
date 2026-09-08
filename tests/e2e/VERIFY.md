# How to verify a step

A case passes by reaching the expected state **the right way**. Reaching `fixed` by a route the
case did not describe is a failure, not a pass — a wrong route landing on the right label is
exactly the bug class this suite exists to find.

Every observation below is available through the provider API. openclaw never needs access to
the autoSWE box, its logs, or `data/queue.json`.

---

## The five things to look at

| Evidence | Where | What it proves |
|---|---|---|
| **The `autoswe:*` label** (Azure: tag) | on the issue / work item | the current status. autoSWE writes it right after it writes the real status, so it is a faithful — slightly lagging — read of the state machine |
| **autoSWE's comments** | on the issue | which phase ran, what it decided, and why it refused something. Bot comments end with `<!-- autoswe-bot -->` |
| **The task branch** | `autoswe/issue-<N>` | whether work was committed, how many commits, what the diff and the commit trailers say |
| **The base branch and the PR** | the repo | whether `/pr` opened a PR, from what head, onto what base |
| **The CI checks** | commit status on the branch head | needed only by [E2E-16](cases/E2E-16.md) |

If the operator is on hand, `python autoswe.py queue status --repo <O/R> --issue <N>` shows the
queue row behind the label — attempt counters, session ids, watermarks. That is a debugging
aid, not a requirement: every case is written so its assertions are checkable from outside.

---

## Reading a label

A running phase — `autoswe:planning`, `fixing`, `syncing`, `reviewing`, `shipping` — means the
agent is working. **Wait.** Do not post the next command: the dispatcher deliberately refuses
to re-open a task from a running status, so a command posted now is not "queued", it is
consumed and discarded, and the case is spoiled.

A resting state — `planned`, `fixed`, `synced`, `shipped`, `reviewed`, `waiting`,
`review_failed`, `review_blocked`, `test_failed`, `failed`, `skipped`, `aborted`, `error` — is
where a step ends and the next one may be posted.

Between the two sits `autoswe:pending`: accepted, not yet started.

The full table, with what each value means, is in
[`../../docs/autoswe/labels.md`](../../docs/autoswe/labels.md). Read the row before judging a
state you did not expect.

Two label observations are findings in themselves:

- a status appearing that the case lists under **must never appear**, and
- a resting state that is not the one the step expected — even if it is "close"
  (`review_failed` where `review_blocked` was expected is a soft finding; `fixed` where
  `waiting` was expected is a hard one).

## Reading a comment

autoSWE narrates itself. A phase posts a progress comment while it works and a completion
comment when it stops, and a refusal — `/pr` blocked by a review verdict, a guard tripping —
always says so in a comment. If a case expects a refusal, the absence of that comment is a
finding even when the label is correct: silently ignoring a command and correctly refusing it
look the same from the label alone.

Two specific comment shapes carry their own assertions:

- **A question** ([E2E-02](cases/E2E-02.md), [E2E-03b](cases/E2E-03b.md)) must arrive as its
  own standalone comment, not folded into the sticky progress comment. A user cannot answer
  what they cannot see.
- **No comment at all** ([E2E-09](cases/E2E-09.md) step 4, [E2E-10](cases/E2E-10.md) step 4) is
  the assertion: an automatic re-review must fire with nothing posted between `fixed` and
  `reviewing`. A comment appearing there means something else triggered it.

## Reading the branch

`autoswe/issue-<N>`. What to check, per case:

- **a commit exists** — and for the "nothing to do" case ([E2E-05](cases/E2E-05.md)), that it
  does *not*
- **the commit trailer** names the issue (`Fixes #<N>`)
- **the diff does what the issue asked** — and only that
- **the branch's base** — [E2E-15](cases/E2E-15.md) cuts from a non-default branch
- **the work survived a red gate** — [E2E-11](cases/E2E-11.md)'s commit must be pushed even
  though the test gate failed. A red gate must never lose the agent's work.

## Reading the PR

Head is `autoswe/issue-<N>`. Base is the repo's **configured `base_branch`** — which is not
necessarily the branch the task was cut from; [E2E-15](cases/E2E-15.md) is the case that pins
this down.

When a case expects `/pr` to be refused, check all three: the label did not change, no PR was
opened, and a comment explains the refusal.

---

## Judging model output

Some assertions are about what a model wrote, not about what the state machine did. Those are
**soft**: score them on substance, not on an exact string, and say in the finding that a human
should confirm.

| Soft assertion | Case | What counts as met |
|---|---|---|
| the review verdict class | [E2E-10](cases/E2E-10.md) | `review_blocked` is expected; `review_failed` is acceptable. The hard part is that `/pr` is refused either way |
| guidance reached the prompt | [E2E-19](cases/E2E-19.md) | the diff and the review visibly reflect the guidance |
| the plan reflects the answer | [E2E-02](cases/E2E-02.md) | the plan names the wording that was given |

Everything else — labels, refusals, commits, PRs, comment counts — is hard. A hard assertion
that fails is a bug report.

---

## Before you file

Read the doc that specifies the behaviour, and quote it in the finding. Each case file lists
the relevant ones at the bottom.

| Question | Doc |
|---|---|
| What does this status mean, and what may follow it? | [`labels.md`](../../docs/autoswe/labels.md) |
| What does this phase actually do? | [`handlers.md`](../../docs/autoswe/handlers.md) |
| Should this comment have been treated as a command? | [`slash-commands.md`](../../docs/autoswe/slash-commands.md) |
| Was this refusal a guard doing its job? | [`safeguards.md`](../../docs/autoswe/safeguards.md) |
| Is this a backend difference rather than a bug? | [`harnesses.md`](../../docs/autoswe/harnesses.md) and [`MATRIX.md`](MATRIX.md) |
| Is this provider-specific? | [`providers.md`](../../docs/autoswe/providers.md) |

If the observed behaviour matches the docs and the case file is what is wrong, that is still a
finding — file it against the case file.
