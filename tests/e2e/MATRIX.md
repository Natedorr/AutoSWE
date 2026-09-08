# Permutations

One **pass** = one trip through the case list with one fixed combination of backends and one
provider. The case files describe behaviour that must be identical across passes; where a case
legitimately differs, it says so under *Backend notes*.

That equality is itself the assertion. A backend swap changes how a phase is executed — MCP vs
text parsing, forking vs resuming — and must not change the state machine it drives.

---

## The backend axis

Bound per phase in the repo entry (`plan_harness` / `fix_harness` / `review_harness`), resolved
against `config/harnesses.json` — see [`../../docs/autoswe/harnesses.md`](../../docs/autoswe/harnesses.md).

| Pass | plan | fix | review | What only this pass exercises |
|---|---|---|---|---|
| **A — Claude** | `claude_code` | `claude_code` | `claude_code` | MCP `post_plan` / `post_question`, `AskUserQuestion` interception, `fork_session` on `/retry` |
| **B — Codex** | `codex` | `codex` | `codex` | no MCP → planner text-parse fallback; no `session_fork` → resume in place; no read-only enforcement in the plan phase |
| **C — Mixed** | `codex` | `claude_code` | `claude_code` | `last_good_session_backend` provenance — a Codex checkpoint must never be resumed into the Claude SDK ([E2E-12](cases/E2E-12.md) is the whole reason this pass exists) |
| **D — pi** | `pi` | `pi` | `pi` | read-only via tool allowlist, session fork, MCP comment posting through the pi-mcp-adapter |

Run **A** first. It is the reference: if a case is red under A, it is a bug in autoSWE, not a
backend divergence. A case that is green under A and red under B, C or D is a backend-binding
bug, which is a different report — say which pass in the finding.

### Cases that differ by backend

Everything not listed here must produce an identical process in every pass.

| Case | Divergence |
|---|---|
| [E2E-02](cases/E2E-02.md) | Claude/pi reach `waiting` through the MCP question tool; Codex through the planner's text-parse fallback. Same state, different route. |
| [E2E-03b](cases/E2E-03b.md) | needs mid-`/fix` tool interception. Claude and pi only — on Codex it runs straight to `fixed`; score **skipped**, not failed. |
| [E2E-12](cases/E2E-12.md) | the `/retry` step: A and D fork the checkpoint session, B resumes in place, C must refuse the checkpoint outright. |

---

## The provider axis

The offline transition matrix already runs every row over both providers, so a live Azure pass
is about the **provider surfaces** the fakes stand in for: work-item comments, tags instead of
labels, and the JSON-Patch status write.

| Provider | Cases | When |
|---|---|---|
| GitHub | all | every pass |
| Azure DevOps | [01](cases/E2E-01.md), [09](cases/E2E-09.md), [11](cases/E2E-11.md), [12](cases/E2E-12.md) | once per release, on one backend |

Under Azure, `autoswe:*` **tags** carry exactly the values GitHub labels do, and every case
reads the same — substitute "tag" for "label" throughout. See
[`../../docs/autoswe/providers.md`](../../docs/autoswe/providers.md).

---

## Case groups

| Group | Cases | Notes |
|---|---|---|
| **Core** | [01](cases/E2E-01.md) [04](cases/E2E-04.md) [05](cases/E2E-05.md) [08](cases/E2E-08.md) | run first; if [01](cases/E2E-01.md) is red, stop — nothing downstream is meaningful |
| **Questions** | [02](cases/E2E-02.md) [03](cases/E2E-03.md) [03b](cases/E2E-03b.md) | the `waiting` state and both ways out of it |
| **Sync** | [06](cases/E2E-06.md) [07](cases/E2E-07.md) [07b](cases/E2E-07b.md) | 07b needs `SYNC_STRATEGY=rebase` — side pass |
| **Review** | [09](cases/E2E-09.md) [10](cases/E2E-10.md) [19](cases/E2E-19.md) | verdict classes are model judgment — see each case's soft-fail note |
| **Gates** | [11](cases/E2E-11.md) [16](cases/E2E-16.md) | the test gate and the CI gate |
| **Failure & guards** | [12](cases/E2E-12.md) | scoped config, run alone |
| **Steering** | [13](cases/E2E-13.md) [14](cases/E2E-14.md) [15](cases/E2E-15.md) | `/skip`, `/abort`, `--branch` |
| **Parsing** | [17](cases/E2E-17.md) [17b](cases/E2E-17b.md) [18](cases/E2E-18.md) | 17b and 18 are scoped, run alone |
| **Operator-assisted** | [OOB](cases/OOB.md) | needs a hand on the box; once per release |

Cases within a group are independent — seed and drive them in parallel. The three scoped cases
([12](cases/E2E-12.md), [17b](cases/E2E-17b.md), [18](cases/E2E-18.md)) change global config
and must run alone, with the config restored after.

---

## What no pass covers

- **Concurrency** — `MAX_CONCURRENT` and repo-lock races are not reproducible on demand against
  a live provider. Covered offline in `tests/test_concurrency.py`.
- **`error`** (an infrastructure crash) and the `MAX_TOTAL_HOURS` guard — both need a hand on
  the autoSWE box. See [`cases/OOB.md`](cases/OOB.md).
