# Spike — pi + pi-mcp-adapter (Phase 0)

One real `pi --mode json` run against an MCP server, to confirm the three
assumptions `PLAN-pi-mcp.md` Phase 1 rests on. **Run: 2026-09-07.**

## Environment

- pi `0.84.4`, host model via the `pi-local` profile: provider `ollama` →
  `qwen3.8:27b` through the LiteLLM shim (`http://linux-server1:4000`).
- `PI_CODING_AGENT_DIR` pointed at a throwaway agent dir (`/tmp/pi-mcp-spike/agent`)
  that mirrored `~/.pi/agent` (`settings.json` listing `npm:pi-mcp-adapter`,
  `models.json` for the local provider, symlinked `npm/` for the installed
  packages). The adapter is what registers MCP tools, so it must be loadable.
- Agent-dir `mcp.json` in the exact Phase 1 shape (server `autoswe_comment`,
  `toolPrefix: "mcp"`, `directTools: [post_plan, post_question, update_progress]`,
  `settings.freezeDirectTools/sampling/elicitation` set).

The spike server was a **correct** mcp-1.x server exposing the same three
`body`-only tools (`post_plan`, `post_question`, `update_progress`) — it answers
`tools/list`. It recorded each call to a log file instead of posting. This
matters, see "Correction" below.

The definitive run forced the model to call the tool under a `--tools` allowlist:

```
pi --provider ollama --model qwen3.8:27b --approve --mode json \
   --tools "read,mcp__autoswe_comment_post_plan" \
   --exclude-tools "ask_question" \
   -- "<prompt: call mcp__autoswe_comment_post_plan with body SPIKE-PROBE-7742-PLAN>"
```

## Confirmed

**1. Model-visible name is exactly `mcp__autoswe_comment_post_plan`.** ✅

The stream emitted:

```json
{"type":"tool_execution_start","toolCallId":"chatcmpl-tool-870be1c96d3741f4",
 "toolName":"mcp__autoswe_comment_post_plan","args":{"body":"SPIKE-PROBE-7742-PLAN"}}
```

So `toolPrefix: "mcp"` + `directTools` gives the direct tool the name
`mcp__<server>_<tool>` → `mcp__autoswe_comment_post_plan` (the adapter's
`formatToolName` uses the `"mcp"` prefix with server-mode normalization).

**2. The tool survives a `--tools` allowlist.** ✅

It was named explicitly in `--tools` (`read,mcp__autoswe_comment_post_plan`) and
was still registered, callable, and returned a result. This is the whole reason
Phase 2 must add the three prefixed names to `_MODE_TOOLS` for **every** mode:
pi's `--tools` is a hard allowlist, so an MCP direct tool that is not listed is
not in the model's tool set at all (the first probe, without the name in the
allowlist, saw only `read`).

**3. `tool_execution_start.args` carries `body` verbatim in `--mode json`.** ✅

`args` was `{"body": "SPIKE-PROBE-7742-PLAN"}` — the exact string the prompt
supplied, nothing added or omitted. So Phase 2 can read the body straight from
the `tool_execution_start` event to drive `plan_posted` / `question_posted` /
progress.

## Correction to the plan's assumptions

**The comment server as shipped does not answer `tools/list` under mcp 1.27.1.**

The plan says "the comment server stays the same Python MCP server both backends
already use; only the pi-side transport changes." That does not hold as-is:

- `mcp_servers/autoswe_comment_server.py` (mcp `<2`, the pinned line
  `mcp>=1.23.0,<2`) registers only `call_tool` handlers on the low-level
  `Server`. Probed over stdio, `tools/list` returns
  `{"error":{"code":-32601,"message":"Method not found"}}`.
- pi-mcp-adapter discovers tools via `tools/list`. A server that doesn't answer
  it registers **zero** direct tools, so the `mcp__autoswe_comment_*` names never
  exist and nothing in Phase 2 fires.

The Claude Code path doesn't need this (the SDK surfaces the tools), but the pi
path does. **This is outside Phase 1's scope** (Phase 1 is config-only; the
server is "untouched") and will need a fix before Phase 2 can use the real server
— e.g. a `tools/list` handler, or moving to mcp `>=2`'s `MCPServer` which
auto-registers the list. Recorded here so Phase 2 doesn't assume the three names
exist for free.
