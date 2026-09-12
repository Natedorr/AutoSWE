# Pi Coding Agent Documentation

Mirror of the packaged docs for Earendil's terminal coding agent
(`@earendil-works/pi-coding-agent`), used as the canonical reference for the
`pi` coding-backend workstream (`docs/autoswe/PLAN-pi-backend.md`).

> **Source:** `@earendil-works/pi-coding-agent@0.84.4/docs` — the `.md` files
> shipped inside the installed npm package, not a scrape of pi.dev. These are
> the canonical markdown pages, so they track the installed CLI exactly.
>
> **Refresh** (after bumping the package):
> ```bash
> cp $(npm root -g)/@earendil-works/pi-coding-agent/docs/{json,rpc,usage,sessions,session-format,providers,models,settings,environment-variables,security,extensions,sdk}.md docs/pi/
> ```
> Update the `@0.84.4` version pin above to whatever `pi --version` reports.

## Table of Contents

| Document | Description |
|---|---|
| [JSON Event Stream Mode](./json.md) | `--mode json` — one JSON object per line; the transport autoSWE drives |
| [RPC Mode](./rpc.md) | `--mode rpc` — bidirectional JSON-RPC protocol (noted as a follow-up) |
| [Using Pi](./usage.md) | CLI usage, flags, and non-interactive modes |
| [Sessions](./sessions.md) | `--session` / `--session-id` / `--fork` / `--no-session` / `--session-dir` |
| [Session File Format](./session-format.md) | On-disk session file layout |
| [Providers](./providers.md) | Built-in providers and model configuration |
| [Custom Models](./models.md) | Defining additional models |
| [Settings](./settings.md) | Global and project settings, including `defaultProjectTrust` |
| [Environment Variables](./environment-variables.md) | Env vars the agent reads |
| [Security](./security.md) | Trust model, project-local resource gating |
| [Extensions](./extensions.md) | Extension API (needed for the MCP follow-up) |
| [SDK](./sdk.md) | Programmatic access via `createAgentSession()`, `ModelRuntime`, sessions, tools, run modes |
