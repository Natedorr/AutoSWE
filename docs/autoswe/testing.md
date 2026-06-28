# Testing

autoSWE uses an 11-layer test strategy, from canonical API fixtures to state-machine transitions to infrastructure edge cases. All offline tests run via `pytest -q -m "not live"`.

## Layer 0 — Canonical API Fixtures

**Location:** `tests/fixtures/api/{github,azure}/`
**Captured by:** `scripts/capture_api_fixtures.py`

Golden JSON snapshots of real API responses (issues, comments, labels, PRs, users). These are the source of truth for what the production APIs return.

**Re-capture:** Run `python scripts/capture_api_fixtures.py` with valid PAT tokens. The script hits real APIs, saves responses, and normalizes timestamps to stable values.

## Layer 1 — Fakes Serve from Fixtures

**Location:** `tests/fakes/templates.py`
**Tests:** `tests/test_fake_contract.py`

`templates.py` loads fixtures from Layer 0 as deep-copied templates. The `GitHubFake` and `AzureFake` build responses from these templates, overlaying mutable state (labels, comments) on top.

Contract tests verify every template matches the expected fixture shape (field names, types, nesting).

## Layer 2 — Pull-Phase Tests

**File:** `tests/test_pull_phase.py`

Parametrized tests over `["github", "azure"]` that verify the normalization contract:

- `NormalizedIssue` fields (number, title, body, state, labels, status)
- `NormalizedComment` author normalization (BOT, OWNER, AUTHOR, raw login)
- PR filtering (`is_pull_request` from GitHub `pull_request` key)
- Azure state mapping (Done/Closed → closed)
- HTML stripping on Azure descriptions
- Slash command parsing (`parse_slash_command`)

Key: comments must include `user` dicts with `login` (GitHub) or `createdBy.uniqueName` (Azure) for author normalization to work.

## Layer 2 — Decide Fixtures (Layer A)

**Location:** `tests/fixtures/decide/<scenario>/`
**Test:** `tests/test_decide.py`

Each scenario has `world.json` (API state, task state, config) and `expected_action.json` (the Action kind, branch, guidance, etc.). Tests load the JSON, construct `World`, call `decide(world)`, and assert the returned `Action` matches the expected one. Parametrized over all scenario directories.

## Layer 3 — Emit Fixtures (Layer C)

**Location:** `tests/fixtures/emit/<scenario>/`
**Test:** `tests/test_emit.py`

Each scenario has `action.json` (the Action), a handler result, and `expected_effects.json` (the Effects). Tests load the JSON, call `emit(action, result, world)`, and assert the returned Effects match.

## Layer 4 — State-Engine Transition Matrix

**Files:** `tests/scenarios/transitions.py`, `tests/test_transitions.py`

Declarative `TRANSITIONS` list, each row describing:
- **start**: state overlay on base template (issue body, labels, comments, queue task)
- **claude_responses**: scripted Claude responses
- **git_calls**: expected git function calls
- **expect**: assertions on outcomes (label, status, comments, Claude calls)

Test parametrizes over `TRANSITIONS × ["github", "azure"]`. The `_to_azure_state()` helper maps GitHub-flavoured rows to Azure shapes (work items, tags, createdBy).

### Writing a Transition Test

A transition test is a single Python dict appended to `TRANSITIONS` in `tests/scenarios/transitions.py`. The test runner in `test_transitions.py` handles all the plumbing: building state, patching fakes, running `orch.loop.poll()`, and asserting outcomes.

#### Row Structure

Every row has these keys:

| Key | Required | Description |
|-----|----------|-------------|
| `name` | Yes | Unique string identifier (e.g. `"planned_then_fix"`) |
| `description` | Yes | Human-readable one-liner |
| `start` | Yes | Dict overlaying the base template |
| `claude_responses` | No | List of scripted Claude responses |
| `git_calls` | No | List of expected git function names |
| `expect` | Yes | Dict of assertions |
| `skip_providers` | No | `["azure"]` or `["github"]` to skip a provider |

#### Building the `start` State

The `start` dict is **deep-merged** into `_GH_BASE` (a minimal issue with no labels, no comments, no queue task). Only provide keys that differ from the base:

```python
"start": {
    "issue": {"body": "/plan"},                    # override just the body
    "labels": ["autoswe:planned"],              # overlay labels
    "comments": [                                  # overlay comments
        {
            "body": "## Plan\n\n1. Do the thing\n\n<!-- autoswe-bot -->",
            "created_at": "2026-01-01T01:00:00Z",
            "author_association": "OWNER",
            "user": {"login": "owner", "id": 1, "type": "User"},
        },
        {
            "body": "/fix",
            "created_at": "2026-01-01T02:00:00Z",
            "author_association": "OWNER",
            "user": {"login": "owner", "id": 1, "type": "User"},
        },
    ],
    "queue_task": {                                # existing queue entry
        "id": "gh:owner_repo_42",
        "owner": "owner", "repo": "repo", "issue_number": 42,
        "title": "Test issue", "body": "/plan",
        "autoswe_status": "planned",
        "base_branch": "main",
        "attempt_count": 1,
        "first_dispatched_at": None,
        "session_id": "s-plan-42",
        "provider": "github",
    },
},
```

**Key rules:**
- All tests use issue #42, owner `"owner"`, repo `"repo"` — the base templates provide these defaults
- Comments MUST include `user` dicts with `login` for author normalization. Use `"OWNER"` association for the PAT owner, `"COLLABORATOR"` for others
- `queue_task` can be `None` (fresh issue) or a full task dict (existing task)
- Timestamps should be sequential and stable (e.g. `2026-01-01T01:00:00Z`, `T02:00:00Z`)

#### Scripting Claude Responses

The `claude_responses` list provides responses for each `runner.run()` call. Each response is:

```python
{"text": "<AUTOSWE_PLAN>1. Do the thing</AUTOSWE_PLAN>", "session_id": "s-plan-42", "subtype": "success"}
```

| Field | Description |
|-------|-------------|
| `text` | Full response body — include the XML tag wrapper (`<AUTOSWE_PLAN>`, `<AUTOSWE_QUESTIONS>`, or raw text for fix-phase DONE_SUMMARY) |
| `session_id` | Returned session ID (must match for resume transitions) |
| `subtype` | `"success"`, `"error"`, or `"timeout"` |

**Common response patterns:**

```python
# Plan succeeds
{"text": "<AUTOSWE_PLAN>1. Do the thing</AUTOSWE_PLAN>", "session_id": "s-plan-42", "subtype": "success"}

# Plan asks questions → waiting status
{"text": "<AUTOSWE_QUESTIONS>What framework?</AUTOSWE_QUESTIONS>", "session_id": "s-plan-42", "subtype": "success"}

# Fix succeeds (DONE_SUMMARY tab-separated format)
{"text": "DONE_SUMMARY\tFixed the bug\tabc1234", "session_id": "s-fix-42", "subtype": "success"}

# Fix fails
{"text": "error", "session_id": "s-fix-42", "subtype": "error"}
```

If a transition does NOT call Claude (e.g., `/skip`, `/abort`), omit `claude_responses` and use `"no_claude_calls": True` in `expect`.

#### Scripting Git Operations

```python
"git_calls": ["create_worktree", "commit_and_push"]
```

The test asserts these functions were called (order matters). The GitFake returns default success values unless you override them via `script_commit()` or `script_sync()` on the GitFake instance (transition tests use defaults).

| Git call | When to use |
|----------|-------------|
| `create_worktree` | Any transition that calls planner or coder (they both create worktrees) |
| `commit_and_push` | Fix transitions that produce code |
| `sync_branch` | `/sync` command transitions |

#### Writing Assertions (`expect`)

```python
"expect": {
    "label_after": "autoswe:fixed",           # final autoswe label
    "autoswe_status": "fixed",                # final queue status field
    "session_id": "s-fix-42",               # session_id in queue task
    "pending_command": None,                # pending_command in queue task
    "comment_contains": ["Completed", "Fixed"],  # substrings in posted comments
    "claude_permission": "bypassPermissions", # permission_mode on Claude call
    "no_claude_calls": True,                # assert zero Claude calls
    "no_git_calls": True,                   # assert zero git calls
    "first_dispatched_at_reset": True,      # assert clock was reset (bug #119)
},
```

| Field | Description |
|-------|-------------|
| `label_after` | The `autoswe:*` label on the issue after the turn |
| `autoswe_status` | The `autoswe_status` enum value in queue.json |
| `session_id` | The `session_id` field in the queue task |
| `pending_command` | The `pending_command` field in the queue task |
| `comment_contains` | List of substrings — each must appear in at least one posted/PATCHed comment |
| `claude_permission` | Exact `permission_mode` passed to Claude (e.g. `"plan"`, `"bypassPermissions"`) |
| `no_claude_calls` | If `True`, asserts `hw.claude.calls` is empty |
| `no_git_calls` | If `True`, asserts `hw.git.calls` is empty |
| `first_dispatched_at_reset` | If `True`, asserts `first_dispatched_at` was NOT the old fixture timestamp |

#### Full Example

```python
{
    "name": "planned_then_fix",
    "description": "Task at planned; user posts /fix → fixed",
    "start": {
        "issue": {"body": "/plan"},
        "labels": ["autoswe:planned"],
        "comments": [
            {
                "body": "## Plan\n\n1. Do the thing\n\n<!-- autoswe-bot -->",
                "created_at": "2026-01-01T01:00:00Z",
                "author_association": "OWNER",
                "user": {"login": "owner", "id": 1, "type": "User"},
            },
            {
                "body": "/fix",
                "created_at": "2026-01-01T02:00:00Z",
                "author_association": "OWNER",
                "user": {"login": "owner", "id": 1, "type": "User"},
            },
        ],
        "queue_task": {
            "id": "gh:owner_repo_42",
            "owner": "owner", "repo": "repo", "issue_number": 42,
            "title": "Test issue", "body": "/plan",
            "autoswe_status": "planned",
            "session_id": "s-plan-42",
            "base_branch": "main",
            "attempt_count": 1,
            "first_dispatched_at": None,
            "provider": "github",
        },
    },
    "claude_responses": [
        {"text": "DONE_SUMMARY\tApplied fix\tdef5678", "session_id": "s-fix-42", "subtype": "success"},
    ],
    "git_calls": ["create_worktree", "commit_and_push"],
    "expect": {
        "label_after": "autoswe:fixed",
        "autoswe_status": "fixed",
        "comment_contains": ["Completed with command", "Applied fix"],
        "claude_permission": "bypassPermissions",
    },
},
```

#### Azure Compatibility

By default, every transition runs for **both** providers. The `_to_azure_state()` helper in `transitions.py` automatically maps:
- `owner`/`repo` → `org`/`project`/`repo`
- `issue` → `work_item` (with `System.*` fields)
- `labels` → `tags` (semicolon-separated in `System.Tags`)
- Comment `body` → `text`, `created_at` → `createdDate`, `user.login` → `createdBy.uniqueName`
- `author_association: "OWNER"` → `createdBy.uniqueName: "owner@example.com"`
- `author_association: "COLLABORATOR"` → `createdBy.uniqueName: "collab@example.com"`

If a transition is provider-specific, add `"skip_providers": ["azure"]` (e.g., PR creation has a known Azure gap).

#### Running Transition Tests

```bash
# All transitions
pytest tests/test_transitions.py -v

# One specific transition
pytest tests/test_transitions.py -k "planned_then_fix" -v

# One transition for one provider
pytest tests/test_transitions.py -k "planned_then_fix and github" -v
```

#### Common Pitfalls

1. **Missing `user` dict in comments** → author normalization fails → slash commands aren't recognized as owner commands
2. **Wrong `author_association`** → must be `"OWNER"` for the PAT user, `"COLLABORATOR"` for non-owners
3. **Forgetting the XML tag wrapper** → Claude responses must include `<AUTOSWE_PLAN>`, `<AUTOSWE_QUESTIONS>`, or raw text with `DONE_SUMMARY` — the transition runner does NOT wrap them
4. **`session_id` mismatch** → for resume transitions (planned → fix), the Claude response session_id must differ from the plan session_id to simulate a new fix session
5. **Queue task field names** → use exact names from the data model (`autoswe_status`, `pending_command`, `attempt_count`, `first_dispatched_at`, `session_id`, `provider`)

## Layer 5 — Output-Call Contract Tests

**File:** `tests/test_output_contracts.py`

Verifies API request bodies match documented shapes:
- GitHub `PUT /labels` → `{"labels": [{"name": str}]}`
- GitHub `POST /comments` → `{"body": str}` with `<!-- autoswe-bot -->` footer
- GitHub `POST /pulls` → `{"title", "head", "base"}`
- Azure `PATCH /workitems` → JSON-Patch array, content-type `application/json-patch+json`
- Azure `POST /comments` → `{"text": str}` with `format=Markdown` query param

End-to-end tests via `patched_world` harness verify labels/tags are set during full poll turns.

**PR content tests** (`TestPRContent`) verify `open_pr()` for both GitHub and Azure:
- GitHub: asserts PR title/body content, idempotency (no duplicate PR when one exists)
- Azure: asserts work item link and title format, idempotency
- All use `unittest.mock.patch` on provider `_gh_request`/`_ado_request` to inspect the actual API call

**Pipeline content test** (`TestPipelineContent`) drives a full `/plan` → `/fix` → `/pr` lifecycle,
asserting posted comment content at each phase. It uses `assert_comments_posted` which checks
both POSTed comments and PATCHed sticky progress comments.

## Layer 6 — Harness Consolidation

**File:** `tests/scenarios/harness.py`

`patched_world()` context manager consolidates all monkeypatching:

```python
with patched_world("github", state=state, claude_responses=resp_list, scripted_git=["create_worktree"], isolated_dir=tmp_path) as hw:
    run_one_turn(owner, repo, cfg, tmp_path)
    # assert on hw.fake, hw.claude, hw.git
```

Patches in order: subprocess, concurrency, Claude runner, git worktree, gh_post_comment, API fake (_gh_request or _ado_request). Restores all on exit via `_PatchManager`.

Scenario test files (`test_scenarios_github.py`, `test_scenarios_azure.py`) use the harness and are ~100 lines each (down from ~170 lines of duplicated monkeypatching).

## Test Markers

| Marker | Description | CI? |
|--------|-------------|-----|
| (default) | Offline tests — no network | Yes |
| `@pytest.mark.scenario` | Scenario-driven E2E (stateful fakes) | Yes |
| `@pytest.mark.transition` | Transition matrix tests | Yes |
| `@pytest.mark.contract` | API fixture contract tests | Yes |
| `@pytest.mark.git_scenario` | Real-git fixture tests using GitWorld sandboxes | Yes |
| `@pytest.mark.live` | Hits real APIs via PAT | Only on master with secret |

## Layer 9 — Real-Git Fixtures

**Files:** `tests/git_fixtures.py`, `tests/test_git_scenarios.py`, `tests/fakes/claude_recipes.py`
**Marker:** `git_scenario`

Unlike the function-boundary fakes (`GitFake`, `ClaudeFake`), the real-git harness creates actual bare remotes, clones, and worktrees under `tmp_path`. Every git operation uses real `git` subprocess calls — no mocks. This catches scenarios that slip past mocks: push rejections, detached HEAD, dirty trees mid-flow, force-push outcomes, token rotation, fast-forward refusal, stale-worktree reuse with uncommitted changes, concurrent worktree access, merge-commit vs. amend detection, and Claude resolving real conflict markers.

### Architecture

- **`GitWorld`** (`tests/git_fixtures.py`) — creates a sandboxed git universe under `tmp_path`: bare remote + AUTOSWE_DIR tree + monkeypatched clone URLs. Exposes builder methods (`init_remote`, `push_commit_to_remote`, `make_worktree`) and state introspection (`merge_state`, `git_log`, `is_merge_commit`).
- **`Recipe`** (`tests/fakes/claude_recipes.py`) — structured spec for "things Claude would do": file writes, deletions, shell commands, conflict resolution, auto-commit. Applied in a real worktree before a `ClaudeFake` response is returned.
- **`ClaudeFake.script_recipe()`** — like `script_response`, but also applies a `Recipe` in `cwd` before returning. Lets tests express "Claude resolves foo.txt and finishes the merge" without a real model.

### Test coverage

`tests/test_git_scenarios.py` enumerates 40+ git states across groups:

| Group | Description | Tests |
|-------|------------|-------|
| A: Baselines | Fresh clone, branch reuse, commit/no-op | A1-A5 |
| B: Working tree | Dirty, untracked, gitignore, binary | B1-B6 |
| C: Divergence | Behind/ahead, amend, merge commit, FF | C1-C8 |
| D: Conflicts | Merge/rebase sync, resolve, binary conflicts, delete-vs-modify | D1-D10 |
| E: Branch/HEAD | Detached HEAD, deleted remote, branch detection, stale worktree | E1-E8 |
| F: Concurrency | Index lock | F1 |
| G: Auth | Token rotation, URL handling | G1-G2 |
| H: Content | Empty repo, mode changes | H1, H7 |
| I: In-progress | Merge/rebase in progress | I1-I2 |
| J: Failure injection | Network drop, permission denied | J1, J3 |

### Running

```bash
# All real-git scenario tests
pytest tests/test_git_scenarios.py -v

# One group
pytest tests/test_git_scenarios.py -k "TestConflicts" -v

# All tests including real-git
pytest -q -m "not live"
```

### What this catches

The function-boundary `GitFake` is fast but cannot catch: push rejections, detached HEAD, dirty trees mid-flow, force-push outcomes, token rotation, fast-forward refusal, stale-worktree reuse with uncommitted changes, merge-commit vs. amend detection, and real conflict-marker resolution. These are exactly the states that fail in production but slip past mocks.

### Resolved Degenerate States

The following were formerly xfail but now have explicit detection and clear `RuntimeError` messages:

- **H1**: Empty repo — raises `RuntimeError("has no commits on")` after clone/fetch
- **E6**: Nonexistent base_branch — when a distinct `default_branch` is available (e.g. `/plan --branch strategy/X` where `strategy/X` is new), the requested branch is auto-created from the default on origin and worktree creation proceeds (E6b). Only when there is no usable fallback (requested base == default, or default also missing) does it raise `RuntimeError("does not exist on origin")`
- **I1**: Merge in progress — raises `RuntimeError` for unresolved conflicts; commits cleanly when resolved
- **I2**: Rebase in progress — same pattern as I1
## Key Seams

The fakes monkeypatch these internal functions:

| Seam | Module | Fake |
|------|--------|------|
| `_gh_request` | `autoswe.tracking.api` | `GitHubFake` |
| `_ado_request` | `autoswe.providers.azure.api` | `AzureFake` |
| `runner.run` | `autoswe.harness.runner` | `ClaudeFake` |
| `asyncio.create_subprocess_exec` | `asyncio` | `CodexFake` |
| `worktree.*` | `autoswe.vcs.worktree` | `GitFake` |
| `gh_post_comment` | `autoswe.tracking.api` + import sites | harness |

### CodexFake — Subprocess-Level Fake

`tests/fakes/codex_fake.py` replaces `asyncio.create_subprocess_exec` with a stub returning a `FakeProcess` that feeds JSONL event lines. Unlike ClaudeFake (which patches `runner.run`), CodexFake lets the **real** factory → CodexBackend → JSONL parser → RunResult path run unmodified.

**How it works:**

1. `CodexFake.script_response(text, session_id, subtype)` builds JSONL lines matching the canonical Codex event format (`thread.started`, `item.completed`, `turn.completed` for success; `turn.failed` for error; returncode -9 for killed).
2. `patch()` monkeypatches `asyncio.create_subprocess_exec` with an async stub that returns a `FakeProcess` feeding the next scripted response.
3. `unpatch()` restores the real function.

**Builder API** (mirrors ClaudeFake so existing `claude_responses` dicts work verbatim):

```python
fake = CodexFake()
fake.script_response("text", session_id="s1", subtype="success")
fake.script_plan("1. Fix it", session_id="s-plan")
fake.script_questions("What?", session_id="s-plan")
fake.script_fail(session_id="s-err", error_msg="timeout")
fake.script_killed(session_id="s-kill")
```

**`.calls` tracking:** Each codex command is parsed and recorded as `{model, sandbox, resume, prompt_prefix, is_resume}`. Tests assert sandbox values (`read-only` for plan, `workspace-write` for fix) to verify mode→sandbox translation.

**Fidelity guard:** `tests/test_codex_fake.py` feeds CodexFake JSONL through the real `CodexBackend` and asserts the resulting `RunResult`. This pins the fake to the real parser — if the JSONL format changes, the fidelity test fails before transitions do.

### Backend Axis in Scenario Harness

The `patched_world()` context manager accepts a `backend` parameter (`"claude_code"` or `"codex"`). When set to `"codex"`:

- A `CodexFake` is created (not `ClaudeFake`) and patched at the subprocess level.
- `config/harnesses.json` is written with a `"codex"` profile.
- Config `PLAN_HARNESS`, `FIX_HARNESS`, `REVIEW_HARNESS` are set to `"codex"` so `resolve_harness()` returns CodexBackend for all phases.
- The `_harnesses_config` cache is cleared to pick up the test-specific config.

The `HarnessWorld` exposes `hw.codex` (the `CodexFake` instance) and `hw.backend` (`"codex"`). Use `assert_codex_calls(hw.codex, [{"sandbox": "read-only"}])` for per-backend assertions.

The transition test suite runs `CODEX_TRANSITIONS` (a curated subset of `TRANSITIONS`) against the Codex backend via `test_transition_codex`. Azure is excluded (GitHub-only) to keep the matrix manageable.

## Three-Layer Test Fixtures

The decide/emit fixture trees are the primary way to test the state machine:

- **`tests/fixtures/decide/`** — `world.json` → `expected_action.json`. Tests Layer A (decide). Each scenario constructs a `World` and verifies `decide()` returns the expected `Action`.
- **`tests/fixtures/emit/`** — `action.json` + result → `expected_effects.json`. Tests Layer C (emit). Each scenario verifies `emit()` produces the expected Effects.
- **`tests/fixtures/provider_adapter/`** — Adapter-specific read_api/apply_effect contract tests.

## Capturing a Scenario

Use `scripts/capture_scenario.py` to seed from a real issue:

```bash
python scripts/capture_scenario.py --provider github --issue 42 --output tests/fixtures/scenarios/github/my_scenario/
```

This creates `state.json` (API state + queue snapshot) and a template `expected.json`. Edit `expected.json` to match the desired outcomes.

## Layer 7 — Queue Store, Concurrency, and Drift

These layers test infrastructure concerns that don't fit the decide/run/emit model but are critical for correctness.

**Files:**

| File | Description |
|------|------------|
| `tests/test_queue_store.py` | LockedQueue invariants, atomic write crash recovery, JSON corruption recovery, transient field leakage, gh_closed behavior, lock contention, prune edge cases |
| `tests/test_concurrency.py` | PID collision (crashed process leaves .pid without .done), repo lock contention, MAX_CONCURRENT gate, comment ID backfill race, RUNNING states protection (comments arriving mid-run), welcome post interleaving |
| `tests/test_drift_detection.py` | Queue/API divergence scenarios: orphan RUNNING tasks, deleted plan comments, gh_closed reopen, bot_comment_ids backfill, deleted comment watermarks, closed PR tracking, label/queue status drift, author allowlist, auto-dispatch |
| `tests/test_fake_parity.py` | Verifies fakes implement the full IssueTracker and VCSProvider protocol; covers all GET/PUT/POST routes for both GitHub and Azure fakes; comment ID uniqueness; provider parity for shared operations |

**Key patterns:**

- **Queue store tests** use `LockedQueue` directly with `isolated_autoswe_dir` fixture. Simulate crash recovery by placing `.tmp` files on disk. Verify lock contention with threading.
- **Concurrency tests** use `running_dir` fixture (isolated `running/` directory). Write PID files, check `_is_task_running` and `_is_repo_locked`.
- **Drift tests** use `decide()` with `World` objects. Simulate queue/API divergence by constructing mismatched `ApiState` and `TaskState`.
- **Fake parity tests** construct real tracker and VCS instances with dict configs, then verify protocol method existence and call each route on the fakes.

## Layer 8 — Transition Matrix Edge Cases

Additional transition rows in `tests/scenarios/transitions.py` cover:

| Scenario | Description |
|----------|-------------|
| `attempt_limit_hit` | Task exceeds MAX_ATTEMPTS → failed status |
| `retry_resets_attempt_count` | `/retry` command resets attempt counter |
| `running_command_noop` | New command during RUNNING status → noop |
| `stale_command_suppressed` | Command ID below watermark → noop |
| `waiting_fix_command_resume` | `/fix` advances waiting → fixing |
| `completed_plain_reply_noop` | Non-command reply on COMPLETED task → noop |
| `null_advance_watermark` | New issue with auto_dispatch_new → advance_watermark |

## Azure Scenario Notes

- Repos.json key is 3-part: `"org/project/repo"`
- Work items use tags (not labels) — `System.Tags` field, semicolon-separated
- Comments use `text`, `createdDate`, `createdBy` fields (not `body`, `created_at`, `user`)
- `author_login` normalization matches `createdBy.uniqueName` against the PAT owner
- Patch content-type must be `application/json-patch+json`
