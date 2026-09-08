# Test project setup

The suite runs against **an existing test project** of yours — a GitHub repo or an Azure
DevOps repo you already own and don't mind churning. It does not create repos, and there is
no seeding script to run: everything below is a handful of small files openclaw can commit
through the provider API, plus config on the autoSWE box.

Use a project that exists for this and nothing else. The cases commit to its default branch,
open branches and PRs, and deliberately turn its test suite red.

---

## 1. Fixture files

Most cases only need a place to add a function. Four cases need a specific lever to exist in
the tree; without it they cannot reach the state they are testing.

Commit these on the **default branch** before the run (openclaw: one commit per file through
the contents API is fine).

| Path | Contents | Why it exists | Needed by |
|---|---|---|---|
| `src/toolbox.py` | a module with one trivial helper, e.g. `def double(n): return n * 2` | the target every "add a function" case edits | most cases |
| `tests/test_toolbox.py` | one passing test for that helper | gives the post-fix test gate something to run | most cases |
| `flag.txt` | the single word `green` | **test-gate lever** | [E2E-11](cases/E2E-11.md) |
| `tests/test_canary.py` | a test asserting `flag.txt` reads `green` | goes red the moment the flag changes → `test_failed` | [E2E-11](cases/E2E-11.md) |
| `conflict.md` | one line: `shared: baseline` | **conflict lever** — both sides edit line 1 | [E2E-07](cases/E2E-07.md) |
| `docs/notes.md` | anything, e.g. `# Notes` | clean-merge target for `/sync` | [E2E-06](cases/E2E-06.md) |
| `README.md` | anything, ending in a newline | the "nothing to do" target | [E2E-05](cases/E2E-05.md) |
| `pyproject.toml` | enough for `pytest` to resolve `tests/` | makes the test gate runnable at all | [E2E-11](cases/E2E-11.md) |
| CI workflow | see below | **CI-gate lever** | [E2E-16](cases/E2E-16.md) |

A second branch — `develop`, or any name other than the default — must exist for
[E2E-15](cases/E2E-15.md). Branch it off the default branch and leave it alone.

### The canary test

```python
# tests/test_canary.py
"""Post-fix test-gate lever: red whenever flag.txt does not read 'green'."""
from pathlib import Path


def test_flag_is_green():
    flag = Path(__file__).resolve().parent.parent / "flag.txt"
    assert flag.read_text().strip() == "green"
```

### The CI gate

[E2E-16](cases/E2E-16.md) needs a CI check that is **still pending** for a few minutes after a
push, so that a `/pr` arriving during that window is refused. It also needs that slow check to
fire for exactly one case and no other, or every case would sit behind it.

On GitHub, a workflow on `push` with two jobs does it: a fast one that runs the tests, and a
slow one that sleeps ~4 minutes but only when the pushed diff touches `ci_slow/**`. On Azure
DevOps, the same shape with a path filter on the pipeline trigger.

If your project already has CI that takes a few minutes on every push, you can skip the
special job and simply post E2E-16's `/pr` while the ordinary check is pending — but then
expect every other case to be gated by CI too, and set `PR_REQUIRE_CI=false` for the rest of
the run.

---

## 2. Config on the autoSWE box

`config/repos.json` — the entry for the test project:

```json
{
  "<owner>/<test-project>": {
    "provider": "github",
    "pat": "<pat>",
    "base_branch": "main",
    "auto_dispatch_new": false,
    "test_gate": true
  }
}
```

Azure DevOps uses the same fields under an `"org/project/repo"` key with
`"provider": "azure"`. See [`../../docs/autoswe/config.md`](../../docs/autoswe/config.md).

What the cases assume, in `config/autoswe.env`:

| Key | Value | Why |
|---|---|---|
| `MAX_CONCURRENT` | `1` | serialises the run so one case's phase can't starve another's |
| `MAX_ATTEMPTS` | `3` | [E2E-12](cases/E2E-12.md) counts attempts against exactly this |
| `AUTO_CREATE_PR` | `false` | every `/pr` in the suite must be an explicit, observable command |
| `PR_REQUIRE_SYNC`, `PR_REQUIRE_CI` | on (default) | [E2E-16](cases/E2E-16.md) needs the CI gate |
| `TEST_GATE` | on (default) | [E2E-11](cases/E2E-11.md) needs the post-fix gate |
| `ALLOWED_AUTHORS` | empty | except during [E2E-17b](cases/E2E-17b.md), which is scoped |

### Scoped config

Three cases need a config change that would distort every other case. Each one says so at the
top of its file, and each must be run **alone**, with the setting restored afterwards:

| Case | Change | Restore to |
|---|---|---|
| [E2E-12](cases/E2E-12.md) | `agent_timeout: 20` on the test project | the normal timeout |
| [E2E-17b](cases/E2E-17b.md) | `ALLOWED_AUTHORS=<owner-login>` | empty |
| [E2E-18](cases/E2E-18.md) | `auto_dispatch_new: true` | `false` |

If you would rather not touch config mid-run, give [E2E-12](cases/E2E-12.md) its own throwaway
project with the short timeout baked in permanently — that is the only case that needs an
agent phase to fail on demand, and a dedicated project is the cleanest way to get it.

---

## 3. Backend and provider

Which backend runs which phase is set by `plan_harness` / `fix_harness` / `review_harness` in
the repo entry, resolved against `config/harnesses.json`. See
[`../../docs/autoswe/harnesses.md`](../../docs/autoswe/harnesses.md).

Pick the combination for the pass you are running from [`MATRIX.md`](MATRIX.md), set it before
seeding the issues, and do not change it mid-pass.

---

## 4. Pre-flight

Before seeding, confirm:

- [ ] the fixture files above are on the default branch, and the second branch exists
- [ ] the test project's own test suite is **green** on the default branch (a red baseline
      makes [E2E-11](cases/E2E-11.md) meaningless and every other `/fix` look broken)
- [ ] the repo entry is in `config/repos.json` and autoSWE's poller is running
- [ ] the harnesses for this pass are bound and the models are reachable
- [ ] the account openclaw posts as can comment on the project's issues, and is either the
      issue author or has owner/collaborator standing — autoSWE ignores commands from
      everyone else
- [ ] no issues from a previous pass are still open with `autoswe:*` labels
