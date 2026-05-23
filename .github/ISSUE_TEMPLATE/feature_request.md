---
name: Feature Request
about: Propose a new feature or improvement for autoSWE
title: ""
labels: ["enhancement"]
assignees: []
---

## Problem This Solves

<!-- What gap or pain point does this address? -->

## Proposed Solution

<!-- How should this work? Describe the behavior from a user's perspective -->

## Impact Area

<!-- Which part of autoSWE does this affect? Check all that apply -->

- [ ] Poll / sync (issue discovery, queue building) — see [pipeline.md](../../docs/autoswe/pipeline.md)
- [ ] Dispatch / decide (state machine, watermark logic) — see [data-model.md](../../docs/autoswe/data-model.md)
- [ ] Handlers (plan, fix, review, PR, sync) — see [handlers.md](../../docs/autoswe/handlers.md)
- [ ] Slash commands (`/plan`, `/fix`, `/pr`, `/review`, `/sync`, `/retry`, `/skip`, `/abort`) — see [slash-commands.md](../../docs/autoswe/slash-commands.md)
- [ ] Labels / status mirror — see [labels.md](../../docs/autoswe/labels.md)
- [ ] Provider abstraction (GitHub, Azure DevOps, new provider) — see [providers.md](../../docs/autoswe/providers.md)
- [ ] Git worktrees — see [git-worktrees.md](../../docs/autoswe/git-worktrees.md)
- [ ] Safeguards / limits — see [safeguards.md](../../docs/autoswe/safeguards.md)
- [ ] Configuration (env, repos.json, prompts) — see [config.md](../../docs/autoswe/config.md)
- [ ] Debugging / logging / queue management — see [debugging.md](../../docs/autoswe/debugging.md)
- [ ] Skills (AI agent tools) — see [docs/skills/](../../docs/skills/)
- [ ] Testing — see [testing.md](../../docs/autoswe/testing.md)
- [ ] Other:

## Skills / AI Agent Context

> If this feature changes behavior an AI agent should know about, note which skill file needs updating:
>
> | Skill | File | Audience |
> |-------|------|---------|
> | `autoswe` | `docs/skills/autoswe/SKILL.md` | User-facing agent — slash commands, lifecycle, guardrails, troubleshooting |
> | `autoswe-ops` | `docs/skills/autoswe-ops/SKILL.md` | Host-level agent (OpenClaw on same machine) — queue, PID, logs, config, restart |

<!-- Does this change require updating either skill? -->

## Alternative Approaches

<!-- Are there other ways to solve this? -->

## Testing Considerations

<!-- Per CLAUDE.md: new handler return → `test_dispatch_status.py`, new labels → `test_lifecycle_labels.py`, new parse rules → `test_lifecycle_parse.py`, new restart logic → `test_sync_restart.py`, new state transition → add row to `tests/scenarios/transitions.py` -->

## References

<!-- Related docs, issues, or examples -->
