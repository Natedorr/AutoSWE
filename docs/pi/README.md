# Pi Coding Agent Documentation

Mirror of https://pi.dev/docs/latest — Earendil's terminal coding agent
(`@earendil-works/pi-coding-agent`). Scrape date: 2026-08-29.

> **No raw `.md` endpoint:** unlike learn.chatgpt.com, pi.dev redirects
> `*.md` URLs back to HTML, so these pages are converted from the rendered
> HTML (readability extraction), not fetched as canonical markdown. Refresh
> by re-scraping https://pi.dev/docs/latest/<page>.

## Table of Contents

| Document | Description |
|---|---|
| [SDK](./sdk.md) | Programmatic access via `createAgentSession()`, `ModelRuntime`, sessions, tools, extensions, run modes |

Pages on pi.dev not yet mirrored (scrape as needed for the `pi` backend):

- `quickstart`, `usage`, `sessions`, `session-format`
- `models`, `providers`, `custom-provider`, `llama-cpp`
- `settings`, `environment-variables`
- `extensions`, `skills`, `prompt-templates`, `themes`, `keybindings`
- `rpc`, `json` — JSON-RPC subprocess protocol (candidate integration path)
- `compaction`, `security`, `containerization`, `development`, `packages`
- `tui`, `shell-aliases`, `terminal-setup`, `tmux`, `termux`, `windows`
