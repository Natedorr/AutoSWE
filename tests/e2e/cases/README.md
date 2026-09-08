# The cases

One file per test case. Each one is self-contained: the issue to create, the comments to post
in order, the process autoSWE must follow in response, and the docs that specify it.

Start at [`../README.md`](../README.md) for how these are driven.

| Case | What it covers | Notes |
|---|---|---|
| [E2E-01](E2E-01.md) | `/plan` → `/fix` → `/pr`, the happy path | run first |
| [E2E-02](E2E-02.md) | a question, answered by a plain reply | |
| [E2E-03](E2E-03.md) | a question, answered by a slash command instead | |
| [E2E-03b](E2E-03b.md) | a question asked mid-`/fix` | Claude and pi only |
| [E2E-04](E2E-04.md) | `/fix` with no plan phase | |
| [E2E-05](E2E-05.md) | a fix with nothing to do | |
| [E2E-06](E2E-06.md) | `/sync`, clean merge | |
| [E2E-07](E2E-07.md) | `/sync` with a conflict the agent resolves | |
| [E2E-07b](E2E-07b.md) | a rebase conflict, which must fail loudly | scoped, run alone |
| [E2E-08](E2E-08.md) | `/review` approving | |
| [E2E-09](E2E-09.md) | review needs changes → `/pr` refused → auto re-review | highest value |
| [E2E-10](E2E-10.md) | review blocked on a critical finding | |
| [E2E-11](E2E-11.md) | the post-fix test gate goes red | |
| [E2E-12](E2E-12.md) | failure, `/retry`, and the attempt guard | scoped, run alone |
| [E2E-13](E2E-13.md) | `/skip`, and inert plain text | |
| [E2E-14](E2E-14.md) | `/abort` and restart | |
| [E2E-15](E2E-15.md) | `--branch`, and the PR base | |
| [E2E-16](E2E-16.md) | `/pr` blocked by pending CI | timing-sensitive |
| [E2E-17](E2E-17.md) | command parsing and idempotence | |
| [E2E-17b](E2E-17b.md) | the author allowlist | scoped, run alone |
| [E2E-18](E2E-18.md) | a body command, and closing the issue | scoped, run alone |
| [E2E-19](E2E-19.md) | `with <guidance>` reaching the prompt | soft assertions |
| [OOB](OOB.md) | crash → `error`, and the wall-clock guard | needs the operator |

## Writing a new case

Copy the shape of [E2E-01](E2E-01.md):

- a header table — group, which passes it applies to, scoped config, whether it runs alone
- **The issue** — the exact title (keeping the `[E2E-NN]` prefix) and body
- **The process** — one row per step: what openclaw posts, the label to wait for, what to check
- **Status path** — the full sequence, so a wrong route is visible
- **Must never appear** — statuses that make the case a failure on sight
- **Why this case exists** — the behaviour under test, in prose. Without this an agent cannot
  tell a real finding from a cosmetic difference
- **Specified in** — the docs the assertions come from

Add it to the table above, to [`../MANIFEST.json`](../MANIFEST.json), and to the group table in
[`../MATRIX.md`](../MATRIX.md). Keep each case to one behaviour: a case that tests two things
cannot tell you which one broke.
