# autoSWE live E2E suite — START HERE

This directory is a **corpus of test cases**, not a program. There is nothing to install, no
cron file to edit, and no script to run. Every case is one markdown file under
[`cases/`](cases/) that says three things:

1. the **issue** to create in your test project,
2. the **comments** to post on it, in order, and
3. the **process autoSWE must follow** in response — the labels, the comments, the branch, the
   PR — with the reason each step must happen and the doc that specifies it.

An agent (referred to throughout as **openclaw**) creates those issues in a real GitHub or
Azure DevOps project, wakes up on its own schedule, pushes each case one step further, checks
what autoSWE actually did against the case file, and files a bug when the two disagree. When
every case has finished, the agent turns its own schedule off.

Everything openclaw needs is in this directory. Everything it checks against is in
[`../../docs/autoswe/`](../../docs/autoswe/) — that is the spec for how autoSWE is supposed
to behave, and a finding is only real if it contradicts one of those docs.

| File | What it is |
|------|-----------|
| `README.md` (this file) | The runbook: the loop openclaw runs, start to finish |
| [`SETUP.md`](SETUP.md) | What the test project must contain before a run, and the config a run assumes |
| [`MATRIX.md`](MATRIX.md) | The permutations — backend × phase split × provider — and which cases each one needs |
| [`VERIFY.md`](VERIFY.md) | How to check a step: what evidence to gather, and what each observation proves |
| [`REPORTING.md`](REPORTING.md) | How to write up a finding, with the template |
| [`MANIFEST.json`](MANIFEST.json) | The same index, machine-readable, with stable paths |
| [`cases/`](cases/) | One file per test case — the issue, the steps, the expected process |

---

## The loop

### 0. Before anything — prepare the project

Read [`SETUP.md`](SETUP.md). It lists the fixture files the test project needs (a canary test,
a conflict file, a slow CI job) and the config the cases assume. openclaw can create the
fixture files itself through the provider API; the config knobs in `config/repos.json` and
`config/harnesses.json` belong to whoever runs the autoSWE box.

Then read [`MATRIX.md`](MATRIX.md) and decide which **pass** you are running — which backend
is bound to which phase, and against which provider. One pass = one trip through the case
list. The case files are permutation-independent except where they say otherwise.

### 1. Set up the wake-up schedule

openclaw creates **its own** recurring schedule — an openclaw cron — for the duration of the
run. Nothing on the autoSWE box changes: autoSWE's poller is already running there on
whatever cadence the operator set, and this suite neither needs nor touches it.

A **10–15 minute** wake-up is the right cadence. autoSWE's poller typically runs every five
minutes and a `/fix` on these deliberately tiny changes takes a few minutes, so waking much
faster mostly finds work still in flight; waking much slower makes a full pass take a day.

The schedule's prompt should be, in substance: *"read `tests/e2e/README.md` and advance the
live E2E run."* Everything else is in this directory.

### 2. Seed the issues

Create one issue per case in the pass, using the **exact title and body** from the case file.

The title must keep its `[E2E-NN]` prefix — that marker is how every later wake-up finds the
issue again and knows which case file governs it. Nothing else identifies it.

Create them all up front, or in batches — but do **not** post the first command yet. Several
cases assume the issue sits untouched until its first comment, and one case
([E2E-18](cases/E2E-18.md)) is specifically about what happens when it does not.

Keep a small run log of `case id → issue number` (a scratch file, or a comment on a tracking
issue — openclaw's choice). Every wake-up starts by reading it.

### 3. Each wake-up: advance every case by one step

For each case that is not yet finished:

1. Read the case file and the run log to find which step the case is on.
2. Look at the issue: its `autoswe:*` label, the comments autoSWE has posted, and — where the
   case asks for it — the branch, the commits, and the PR.
3. **Still running?** (a `autoswe:planning` / `fixing` / `syncing` / `reviewing` / `shipping`
   label, or the previous step's expected resting label has not appeared yet) → leave it
   alone and come back next wake-up. Never post the next command over a running phase; the
   dispatcher deliberately ignores comments posted mid-run, and doing it hides the very
   behaviour the case is testing.
4. **Reached the expected state?** → check the step's assertions ([`VERIFY.md`](VERIFY.md)),
   record the result, then post the next step's comment.
5. **Reached a different state?** → that is a finding. Write it up
   ([`REPORTING.md`](REPORTING.md)) and mark the case failed; do not keep driving it.
6. **Stuck?** — no label change for **three consecutive wake-ups** on a step that should have
   moved — report it as a stall and stop driving that case.

Advance on **observed state**, never on elapsed time. The label is the state machine talking;
a timer is a guess.

### 4. Verify what autoSWE actually did

A case is not passed by reaching the right label. It is passed by reaching it **the right
way** — the route matters more than the endpoint, because a wrong route that lands on the
right label is exactly the class of bug this suite exists to catch.

[`VERIFY.md`](VERIFY.md) says how to gather the evidence and what each observation proves.
Read the docs it points at before judging anything: `docs/autoswe/labels.md` for what a status
means, `docs/autoswe/handlers.md` for what each phase does, `docs/autoswe/slash-commands.md`
for how a comment is parsed, `docs/autoswe/safeguards.md` for the guards.

### 5. Report findings

File one issue per finding, in the autoSWE repository — not in the test project. Use the
template in [`REPORTING.md`](REPORTING.md): what the case expected, what actually happened,
the evidence, and the doc line the behaviour contradicts.

Keep the test-project issue open and its label untouched. It is the evidence.

### 6. Finish: turn the schedule off

When every case in the pass is passed, failed, or reported as stalled:

1. Post the run summary — the pass label, the per-case verdict, and links to every finding.
2. **Delete the openclaw cron.** It exists only for the duration of a run. A schedule left
   running after a pass will keep waking up against issues nobody is watching.

If the next pass is a different permutation from [`MATRIX.md`](MATRIX.md), start over at step
0 with fresh issues. Never re-drive the issues from a previous pass: their comment history is
already past the state each case starts from, and autoSWE's own watermarks
(`last_dispatched_command_id`, `last_consumed_reply_id`) make a second run through the same
issue mean something different from the first.

---

## What this suite is for

The offline suite ([`../../docs/autoswe/testing.md`](../../docs/autoswe/testing.md)) proves
the state machine against fakes: fast, deterministic, and blind to everything real. This suite
proves the same machine against a real provider and a real coding backend — real comment ids,
real labels, real branches, real model output.

Every case here is a deliberately trivial code change. The difficulty is never the point; the
**path through the state machine** is. When a case finds a bug, the fix belongs in both
places: add the transition row offline in `tests/scenarios/transitions.py`, and keep the case
here so the live path stays covered.
