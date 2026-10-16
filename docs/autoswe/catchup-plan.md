# Plan: `/catchup` — sync two long-lived branches from a control issue

Status: **proposed** — implementation plan for the next agent. Delete or fold into
`handlers.md` / `slash-commands.md` once shipped.

## Problem

A downstream branch (typically `develop`) falls behind its upstream (typically
`master`). Today `/sync` can't help: it only merges `origin/{plan_branch or base_branch}`
into the *issue's own* work branch (`autoswe/issue-N`), and it is refused when the task
has no completed work (`slash-commands.md`, "no completed branch work to advance").

## Goal

A **control issue** — a mostly blank issue whose only job is to drive catch-ups:

> **Title:** Keep `develop` caught up with `master`
> **Body:** `/catchup --from master --into develop`

Each `/catchup` is **one manual run**: merge `origin/<from>` into a work branch cut from
`<into>`, resolve conflicts with the agent if needed, open (or update) a PR into `<into>`.
More catch-ups later = post `/catchup` again on the same issue.

### Explicit non-goals (decided — do not build)

- No `--watch` / automatic re-triggering, no SHA watermark, no interval throttle.
- No auto-creating control issues from `repos.json`.
- No rebase strategy for catch-ups (see "Merge, never rebase" below).

## User-facing behaviour

| Aspect | Behaviour |
|--------|-----------|
| Syntax | `/catchup --from <upstream> --into <downstream>` (body or comment, OWNER/AUTHOR only, line-start like every other command) |
| Sticky pair | First `/catchup` stores `sync_from` / `sync_into` on the task. A later bare `/catchup` reuses them; passing flags overrides them. |
| Missing pair | Bare `/catchup` with nothing stored → bot replies explaining the syntax; status unchanged. |
| Pre-states | Any — no prior plan/fix required (unlike `/sync`). Still refused when `guard_blocked` (post `/retry`), same as every other command. |
| Already up to date | `origin/<from>` is an ancestor of `origin/<into>` → comment "already up to date", status `caught_up`, no worktree, no PR. |
| Clean merge | Push `autoswe/issue-N`, open PR into `<into>`, status `caught_up`. |
| Conflicts | Agent resolves (catch-up–specific prompt), push, open PR. Resolution failure → `failed`, worktree left conflicted; `/retry` replays the catch-up. |
| Repeat while PR open | Same branch, more commits pushed, same PR (open_pr already finds an existing PR). |
| Repeat after PR merged | Branch was deleted (`purge_gone_branches`) → recreated from current `<into>`. |
| Body command | Body has no comment ID, so it triggers the **first** run only; repeats come from comments (existing #192 body-dedup semantics). |
| Issue lifecycle | Control issue stays **open** — skip linkage close-on-merge for catch-up tasks. |
| Duplicate guard | Refuse a `/catchup` whose `<into>` is already the `sync_into` of another *active* (running) catch-up task in the same repo: "already being caught up by #N". |
| PR note | PR body and completion comment say: **merge with a merge commit, not squash** — a squash leaves `<from>`'s commits out of `<into>`'s ancestry, so it stays "behind" and the same conflicts recur. |
| `--direct` | **Deferred / optional (phase 3).** Push the merge straight to `<into>` on a clean merge only, gated by repo config `ALLOW_DIRECT_BRANCH_SYNC` (default false). |

## Design notes

### Reuse, don't fork, the git plumbing

Almost everything exists:

- `worktree.create_worktree(owner, repo, issue_num, <into>, token, cfg, provider, default_branch=base_branch, pull_strategy="reset", push_new=True)` — cuts `autoswe/issue-N` from `<into>` (same call shape `_run_sync` uses with `sync_base`).
- `worktree.sync_branch(wt, owner, repo, issue_num, base_branch=<from>, provider, cfg)` — fetches, resets to `origin/autoswe/issue-N` when it exists (so repeats build on the open PR), merges `origin/<from>`, pushes, leaves conflicts in place. **Pass a cfg copy with `SYNC_STRATEGY="merge"` forced.**
- `coder.resolve_sync_conflicts(...)` — conflict resolution via the resolved `fix` harness. Needs a catch-up variant of the prompt (no plan text; context = "merging upstream `<from>` into downstream `<into>`; preserve downstream-only changes, take upstream fixes; do not invent features"). Its `sync_base` currently derives from `plan_branch or base_branch` (`coder.py:754`) — make it accept the base explicitly so the catch-up passes `<from>`.
- `ship.open_pr(task, cfg, repo_cfg, ...)` — PR target is hard-wired to `base_branch` (`ship.py:103-111`). Add an override: when `task.get("sync_into")` is set (or an explicit `target_branch=` kwarg — prefer the kwarg), target it. Keep the #260 "base missing on origin" fallback applying only to the default path.

### Merge, never rebase

Rebasing would rewrite the downstream work branch on top of `<from>` and, if squash/rebase
merged, break ancestry for every future catch-up. Force merge regardless of `SYNC_STRATEGY`.

### Up-to-date pre-check

Before creating a worktree, in the main clone (`main_clone_path` + `fetch_prune`):
`git rev-list --left-right --count origin/<into>...origin/<from>` → right count `0` means up
to date. Also verify both remote branches exist (`remote_branch_exists`) and reply with a
clear error if not. Put this in a new `worktree.branch_divergence(main, into, from_) -> tuple[int, int]` helper.

### Keep it out of the work-task paths

- Catch-up must **not** go through `_sync_before_dispatch` / `ensure_claude_md`.
- Don't run the CI watch on catch-up tasks unless trivially free (they're not in `CI_WATCH_STATUSES`, so this is the default — leave it that way).
- `/retry` on a failed catch-up replays `/catchup` (add `/catchup` to the substantive-command set `_run_retry` scans; it must not fall back to `/fix`).
- `/fix` / `/plan` / `/review` / `/pr` on a control issue: no special handling required, but the agent prompt would see a blank issue. Acceptable for v1; mention in docs that control issues are catch-up only.

## Implementation checklist

### 1. Command registry & parsing
- `autoswe/commands/parser.py`
  - Add `catchup` to `_SLASH_CMD_RE` (keep the `(?=\s|$|\`)` boundary so `/catchupfoo` doesn't match).
  - New helper `parse_catchup_args(guidance: str | None) -> tuple[str | None, str | None, bool]` returning `(from, into, direct)`, each branch validated with `_sanitize_branch_token`. **Do not change the `(cmd, guidance, branch)` 3-tuple** — many callers unpack it.
  - Update the `parse_slash_command` docstring command list.
- `autoswe/tracking/labels.py`: `_CMD_TO_KIND["/catchup"] = "catchup"`, `_KIND_TO_RUNNING["catchup"] = "catching_up"`, `_KIND_TO_COMPLETED["catchup"] = "caught_up"`; add `caught_up` to `COMPLETED_STATUSES` (wherever that set lives) and the label mirror table.
- `autoswe/orch/emit.py`: `_KIND_TO_COMMAND["catchup"] = "/catchup"`; completion handling alongside `sync_branch` (around `emit.py:95` and `:815`); persist `sync_from` / `sync_into` / `pr_number` / `pr_url` on the task; must **not** treat it as a coding kind for session checkpoints (see comment near `emit.py:669`).
- `autoswe/orch/types.py`: add `"catchup"` to `Action.kind`; add `sync_from: str | None = None`, `sync_into: str | None = None`, `direct: bool = False` to `Action`. Add `sync_from` / `sync_into` to the task view used by `World` if decide needs them.

### 2. Decide
- `autoswe/orch/decide.py`
  - Route `/catchup` → `Action(kind="catchup", sync_from=..., sync_into=...)` resolving flags-over-stored.
  - Exempt `catchup` from the "no completed work" refusal that blocks `/sync` from fresh/failed states (in `_check_restart_or_guard`). Keep the `guard_blocked` refusal.
  - Missing/invalid pair → `refused` action with an explanatory comment (reuse the existing refusal plumbing).
  - Duplicate guard: needs visibility of other tasks in the repo. If `World` doesn't carry that, do the check in `loop.py` before dispatch (or in `run.py` at start, returning a `FAILED:`-free refusal) — pick whichever keeps `decide` pure.

### 3. Run
- `autoswe/orch/run.py`
  - `if kind == "catchup": return _run_catchup(task, action, rc, cfg, progress_callback)` next to `sync_branch`.
  - `_run_catchup`: pre-check → (up to date ⇒ `DONE_SUMMARY`) → create worktree from `<into>` → `sync_branch(base=<from>, merge forced)` → on conflict `resolve_sync_conflicts(..., base=<from>, prompt=catchup)` → `ship.open_pr(..., target_branch=<into>)` → `DispatchResult(done_content=f"DONE_SUMMARY\t{summary}\t{sha}", pr_number=..., pr_url=...)`. Summary includes behind/ahead counts, conflict files resolved, PR link, and the merge-commit note.
  - Wrap in the same broad `except` → `FAILED:` as `_run_sync`.
  - `_run_retry`: treat `/catchup` as replayable.
- `autoswe/vcs/linkage.py`: skip `_maybe_close_on_merge` for tasks with `sync_into` set.

### 4. Worktree / ship / coder
- `autoswe/vcs/worktree.py`: `branch_divergence()` helper.
- `autoswe/vcs/ship.py`: `target_branch` kwarg; PR body note for catch-ups.
- `autoswe/harness/coder.py` + prompts (`config/` / `harness/prompts.py`): explicit base arg on `resolve_sync_conflicts`, catch-up prompt variant.

### 5. Config (phase 3 only)
- `autoswe/core/config.py`: `ALLOW_DIRECT_BRANCH_SYNC` (repo-level, default false). `docs/autoswe/config.md`.

### 6. Skills, prompts & user-facing text — hook `/catchup` in everywhere commands are listed
- `docs/skills/autoswe/SKILL.md`
  - Slash-command table (line ~40): add `/catchup --from <upstream> --into <downstream>`.
  - Running/terminal status lists (~130): add `catching_up` / `caught_up`.
  - Add a short "Control issues: keeping a branch caught up" workflow section (blank issue + `/catchup`, repeat to catch up again, merge-commit-not-squash).
  - Failed-task guidance (~174, ~201): `/retry` replays a failed catch-up; `/catchup` itself is allowed from any state.
- `docs/skills/autoswe-ops/SKILL.md`: how to inspect a catch-up task (`sync_from`/`sync_into` in `queue status`), and recovery for a conflicted catch-up worktree.
- `config/welcome_comment.txt` **and** the hard-coded fallback copy in `autoswe/orch/loop.py:~178` — add the `/catchup` line to both (they must stay in sync).
- `config/agent_prompt.txt`: its `/sync` paragraph is a command list for the agent — add a `/catchup` note (or confirm the file is legacy/unused and leave it, noting that in the PR).
- `README.md`: command table (~137) and feature bullets.
- `.github/ISSUE_TEMPLATE/feature_request.md`: slash-command checkbox list (line 24).
- `CLAUDE.md` project overview command list.
- `docs/autoswe/`: `slash-commands.md` (table row + regex line ~34), `handlers.md` (new `/catchup` section), `data-model.md` (`sync_from`, `sync_into`, new statuses), `labels.md` (`autoswe:catching_up` / `autoswe:caught_up`), `pipeline.md` if it enumerates kinds.
- `tests/e2e/cases/`: new `E2E-xx.md` for `/catchup` clean + conflict, registered in `cases/README.md` and `MANIFEST.json`.
- Grep for the old list to catch stragglers: `rg -n "/sync" --glob '!worktrees/**' --glob '!docs/claude-agent-sdk/**' --glob '!docs/codex/**'` and `rg -n "fix\|plan\|pr\|retry\|skip\|sync\|abort\|review"` regexes.

## Tests (per CLAUDE.md conventions)

| File | Cases |
|------|-------|
| `test_lifecycle_parse.py` | `/catchup --from master --into develop`; flags in either order; bare `/catchup`; invalid branch tokens; `/catchupfoo` not matched; backtick-prefixed form |
| `test_lifecycle_labels.py` | `catching_up` / `caught_up` mirrors; `/catchup` → `catchup` kind |
| `test_dispatch_status.py` | `DONE_SUMMARY` / `FAILED:` → status mapping for the new kind |
| `test_decide.py` + `tests/fixtures/decide/` | fresh control issue → catchup; bare with stored pair; bare without pair → refused; from `failed` → allowed; `guard_blocked` → refused |
| `test_emit.py` + `tests/fixtures/emit/` | catchup success persists `sync_from`/`sync_into`/`pr_*`; no session checkpoint |
| `test_worktree.py` / `test_git_scenarios.py` (`git_scenario`, `GitWorld`) | up to date; fast-forwardable; clean merge; conflicting merge; repeat with existing remote work branch; `SYNC_STRATEGY=rebase` still merges; `branch_divergence` counts |
| `test_ship.py` | `target_branch` override; default path unchanged; catch-up PR body note |
| `test_orch_run.py` | `_run_catchup` happy/conflict/resolution-failure/missing-branch paths; `/retry` replays `/catchup` |
| `test_coder_returns.py` | `resolve_sync_conflicts` with explicit base + catch-up prompt |
| `tests/scenarios/transitions.py` (both providers) | new → `/catchup` → `caught_up`; conflict → resolved → `caught_up`; resolution fails → `failed` → `/retry` → `caught_up`; second `/catchup` while PR open → same PR. Add the conflict rows to `CODEX_TRANSITIONS`. |
| `test_config.py` (phase 3) | `ALLOW_DIRECT_BRANCH_SYNC` parsing/default |

## Phasing

1. **Phase 1 — clean merges:** parser, labels, types, decide, `_run_catchup` (up-to-date + clean merge), `branch_divergence`, `ship` target override, close-on-merge skip, skills/docs/welcome text, tests.
2. **Phase 2 — conflicts:** catch-up conflict prompt, explicit base on `resolve_sync_conflicts`, `/retry` replay, conflict transition rows (+ Codex).
3. **Phase 3 — optional `--direct`:** config flag, clean-merge-only direct push, tests.

## Done criteria

- `pytest -q -m "not live"` green, `ruff check autoswe tests` clean (CLAUDE.md pre-checkin gate).
- Every place that lists slash commands (code registries, skills, welcome text, README, docs, issue template) includes `/catchup`.
- Manual E2E: blank issue with `/catchup --from master --into develop` against a repo where `develop` is behind → PR opened into `develop`; second `/catchup` updates the same PR.
