# ⭐ AutoSWE ⭐ — AI Coding from Issues, Not Terminals

Your issue tracker is your IDE. Post a command on a GitHub or Azure DevOps issue. A PR appears when you're done.

autoSWE connects your issue tracker (the frontend) to Claude Code on your own hardware (the backend). It replaces the interactive coding TUI with a browser-based workflow — manage your entire development cycle from issue comments without touching a terminal.

**Your hardware. Your tokens. Your setup. No cloud service in the middle.**

---

## The Problem It Solves

Today's AI coding agents force you into their world: their web UI, their pricing, their model choices, their infrastructure. Your code leaves your network. You pay per-seat markups. You're locked into whatever models they support.

autoSWE flips it. Your issue tracker becomes the control surface. Claude Code runs on your machine with your API keys. The agent reads your codebase, writes the fix, and opens a PR — all while you manage everything from the web interface you already use.

## What It Does

autoSWE bridges the gap between **project management** and **code execution**:

| Your Side (Browser) | autoSWE (Your Machine) |
|---|---|
| Post `/fix` on an issue | Polls the issue, detects the command |
| Answer questions inline | Asks Claude Code clarifying questions |
| Review a PR | Claude Code reads codebase, writes fix, commits, pushes branch |
| Merge when ready | Opens PR, posts progress updates |

It handles the hard parts that interactive agents can't:
- **Parallel issue work** — multiple issues, multiple branches, coordinated through the queue
- **Merge conflict resolution** — sync upstream changes automatically, resolve conflicts with Claude
- **Branch management** — isolated git worktrees per issue, nothing touches your main branch
- **Sub-branch workflows** — review before ship, retry failed attempts, sync mid-fix
- **Human-in-the-loop** — Claude asks questions when stuck, you answer in the issue thread, work resumes

## How It Works

```
Issue Tracker (GitHub / Azure DevOps)     autoSWE (Your Machine)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━    ━━━━━━━━━━━━━━━━━━━━━━━━━
                                                         
  Post /plan on issue ──────────────►  Poller detects command
                                       │
                                       ▼
                                  Claude reads codebase
                                       │
                                       ▼
                                  Posts structured plan on issue
                                       │
  Review plan, reply if needed ──────►  Claude incorporates feedback
                                       │
  Post /fix ───────────────────────►  Claude writes code in isolated worktree
                                       │
                                       ▼
                                  Commits + pushes branch
                                       │
                                       ▼
                                  Auto-creates PR ────────────► Review in browser
                                       │
  Merge PR ──────────────────────────   Done
```

That's the full workflow. No terminal. No cloud agent service. No data leaving your network.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Your Issue Tracker                   │
│              (GitHub / Azure DevOps Web UI)             │
└────────────────────┬────────────────────────────────────┘
                     │ Slash commands in comments
                     ▼
┌─────────────────────────────────────────────────────────┐
│                     autoSWE Poller                      │
│  ┌──────────┐    ┌──────────┐    ┌──────────────────┐   │
│  │  Sync    │───►│  Decide  │───►│   Claude Code    │   │
│  │(read API)│    │(state    │    │   (your machine) │   │
│  │          │    │ machine) │    │                  │   │
│  └──────────┘    └──────────┘    └────────┬─────────┘   │
│                                           │             │
│  ┌───────────┐    ┌──────────┐            │             │
│  │ Apply     │◄───│  Emit    │◄───────────┘             │
│  │(API write)│    │(effects) │                          │
│  └───────────┘    └──────────┘                          │
└─────────────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│                   Git Worktrees                         │
│              (isolated per-issue branches)              │
└─────────────────────────────────────────────────────────┘
```

Three pure layers separated by frozen dataclasses:
1. **Decide** — pure state machine (what should happen next?)
2. **Run** — coding-backend invocation (the actual work; Claude Code or Codex behind one `CodingBackend` protocol)
3. **Emit** — pure effect emission (status changes, comments, PRs)

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/natedorr/autoswe ~/autoswe
cd ~/autoswe
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Run the setup wizard
./setup.sh

# 3. Start the poller (or add to cron for continuous operation)
./poller.sh
```

The setup wizard walks you through API keys, repo configuration, and model selection. The poller handles everything else — add it to cron for continuous operation.

To update autoSWE later: `./update.sh` (Linux) or `update.bat` (Windows).

### Your First Fix

1. Open a GitHub or Azure DevOps issue in a configured repo
2. Comment `/plan` — autoSWE reads your codebase and posts a structured fix plan
3. Comment `/fix` — Claude Code writes the code in an isolated worktree
4. Review the auto-created PR in your browser
5. Merge when you're satisfied

That's it. The issue tracker is your development workflow.

## Slash Commands

| Command | What It Does |
|---------|---|
| `/plan` | Claude reads your codebase and posts a structured fix plan |
| `/fix` | Claude executes the fix — reads code, edits files, commits to branch |
| `/review` | Claude reviews the diff before shipping |
| `/pr` | Opens a pull request for the completed fix |
| `/sync` | Rebases worktree onto upstream, resolves conflicts with Claude |
| `/retry` | Retries a failed fix attempt |
| `/skip` | Skip this issue |
| `/abort` | Cancel the current run |

Commands work on both issue bodies and comments. You reply to Claude's questions inline — same thread, same context.

## Why autoSWE

| Cloud Coding Agents | autoSWE |
|---|---|
| Your code goes to a third-party API | Everything stays on your machine |
| Black-box pricing, per-seat billing | You pay only for your own API tokens |
| Limited to their supported models | Use Claude, Codex, or any model you configure |
| Shared infrastructure | Dedicated machine, full isolation |
| Vendor lock-in | Open-source, self-hosted, yours to modify |
| Interactive TUI — one task at a time | Issue tracker — manage multiple issues from your browser |
| No merge/sync workflows | Full branch management with conflict resolution |

**Full visibility** — every step is a comment on your issue. Plans, questions, commits, failures — nothing happens in a black box.

**Safe by design** — edits happen in isolated git worktrees. Nothing touches your main branch until you merge a PR.

**Queue-driven** — autoSWE maintains a task queue from issue comments. It processes work sequentially with concurrency controls, so you can queue up fixes and let it work through them.

## Safety

- **Isolated worktrees** — edits never touch your main branch
- **Concurrency limits** — configurable parallelism, per-repo locks
- **Attempt limits** — auto-fail after N attempts to prevent token burning
- **Time limits** — runs auto-fail after configurable timeout (default 2 hours)
- **Read-only planning** — `/plan` can only read code, never write
- **Human authorization** — only the issue owner can issue commands

## Pluggable Backends

The agent that does the coding isn't hard-wired. A **harness profile** binds each phase (`plan` / `fix` / `review`) to a backend and a model, so you can mix and match:

| Backend | What it runs | Notes |
|---|---|---|
| `claude_code` | Claude Agent SDK (default) | Full feature set — MCP, inline clarifying questions, plan capture, session resume |
| `codex` | OpenAI Codex CLI (`codex exec`) | No Anthropic dependency; MCP/question features degrade gracefully |

Run plan on Claude and fix on Codex, go all-Codex to drop the Anthropic dependency, or point a profile at a local Ollama model — it's per-phase, per-repo. See [Harnesses & Backends](docs/autoswe/harnesses.md).

## Requirements

- Python 3.10+
- Git
- A coding backend: **Claude Code CLI** (ships with autoSWE, needs an Anthropic API key) and/or the **Codex CLI** (`npm i -g @openai/codex`, needs an OpenAI/Codex key — or a local provider)
- GitHub PAT with `repo` scope (or Azure DevOps PAT)

## Configuration

Three files, everything else is automatic:

- **`config/autoswe.env`** — API keys, concurrency, timeouts, per-phase model/harness selection
- **`config/repos.json`** — which repos to watch, per-repo PATs and overrides
- **`config/harnesses.json`** — named backend profiles (optional; without it, defaults to Claude Code)

Run `./setup.sh` for a guided first-time configuration. Run `./setup.sh --force` to reconfigure.

## Documentation

- [Pipeline Architecture](docs/autoswe/pipeline.md)
- [Configuration](docs/autoswe/config.md)
- [Harnesses & Backends](docs/autoswe/harnesses.md)
- [Safeguards](docs/autoswe/safeguards.md)
- [Providers (GitHub, Azure)](docs/autoswe/providers.md)
- [Git Worktrees](docs/autoswe/git-worktrees.md)
- [Debugging](docs/autoswe/debugging.md)
- [Testing](docs/autoswe/testing.md)

---

_Built for teams that want AI-assisted development without surrendering their code to a cloud service._
