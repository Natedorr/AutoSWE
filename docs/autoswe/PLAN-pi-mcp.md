# Plan — give `pi` the `mcp` capability via `npm:pi-mcp-adapter`

Goal: `PiBackend` advertises the `mcp` capability, so plan/question detection stops
depending on `<AUTOSWE_PLAN>` tag-scraping and `planner.py`'s `has_mcp` branch
turns on for pi. The comment server stays the same Python MCP server both backends
already use; only the pi-side transport changes (agent-dir `mcp.json` + tool-name
resolution). Follow-up #1 from `PLAN-pi-backend.md` ("Explicitly out of scope").
Work lands on branch `pi` (PRs target `pi` during this workstream).

## Phases

### Phase 0 — spike (one real pi run)

Confirm the model-visible name is exactly `mcp__autoswe_comment_post_plan`, that it
survives a `--tools` allowlist, and that `tool_execution_start.args` carries `body`
verbatim in `--mode json`. Everything below assumes these three.

### Phase 1 — config, not code

Generate `<agent dir>/mcp.json` — not `.mcp.json` in the target worktree, which would
pollute the repo under test and trip project trust. The harness profile already has
an `agent_dir` field mapping to `PI_CODING_AGENT_DIR`, so an autoSWE-owned agent dir
is the natural home:

```json
{"mcpServers": {"autoswe_comment": {
    "command": "${AUTOSWE_PYTHON}", "args": ["-m", "mcp_servers.autoswe_comment_server"],
    "cwd": "${AUTOSWE_REPO_ROOT}", "toolPrefix": "mcp",
    "directTools": ["post_plan", "post_question", "update_progress"]}},
   "settings": {"freezeDirectTools": true, "sampling": false, "elicitation": false}}
```

Only stable values interpolate here (python path, repo root). `mcp_config.py` keeps
building the same dict it builds today; `PiBackend` routes its env block into the
subprocess env instead of into this file.
`mcp_servers/autoswe_comment_server.py` is untouched — same tools, same provider
tracker, same redaction, both backends.

### Phase 2 — PiBackend

`spec.mcp_servers` currently ignored; make it the trigger. When it names
`autoswe_comment`: ensure the agent-dir `mcp.json`, merge the server's env into the
child env, and add the three prefixed names to `_MODE_TOOLS` for every mode. In
`_parse_line`, branch `tool_execution_start` on them → `plan_posted` /
`question_posted` / progress-callback with the body. Parse the two proxy shapes
(`mcp` and the `mcp__autoswe_comment` namespace proxy, both `{tool, args}`) as a
fallback so a cold cache still works instead of silently reverting to tag-scraping.
`CAPABILITIES` gains `"mcp"` — which is the whole point: `planner.py:104`'s
`has_mcp` branch turns on for pi and plan/question detection stops depending on
`<AUTOSWE_PLAN>`.

### Phase 3 — tool-name resolution

Add `comment_tool_names()` to the backend contract returning
`{"post_plan": <full name>, …}`; `coder.py:_MCP_COMMENT_TOOLS` and the planner read
it instead of the hardcoded prefix. Prompts get `{{POST_PLAN_TOOL}}` /
`{{POST_QUESTION_TOOL}}` placeholders defaulting to the Claude names, so existing
custom prompt files in `config/prompts/` keep working unchanged.

### Phase 4 — cold-start + version floor

First run against a new server has no cache entry, so add a warm-up to
`setup.ps1`/`setup.sh` plus a preflight in `PiBackend` that logs loudly when
`mcp-cache.json` lacks `autoswe_comment` (that's the run that will fall back). And
a pi-mcp-adapter version floor test alongside `test_cli_version.py` — naming, cache
hashing, and env passthrough are adapter internals we're now depending on.

### Phase 5 — tests (per the CLAUDE.md table)

- `test_pi_backend.py` (argv tool names, env merge, direct + proxy event → flags,
  suppression)
- `test_pi_fake.py` + canonical `tool_execution_start` fixture lines
- `test_backend_capabilities.py` / `test_backend_parity.py` (pi now has `mcp`)
- `test_planner_returns.py` (pi returns `PLAN_READY` with no tag in the text)
- a `TRANSITIONS` row on the existing pi scenario axis
- `test_config.py` for the `mcp.json` builder

### Phase 6 — docs

`harnesses.md` capability matrix + a "pi gets MCP via pi-mcp-adapter" section
spelling out the env-vs-config-hash rule (it's the kind of thing that silently
regresses), `testing.md` fixtures, `CLAUDE.md` backend blurb.

## Deferred

`autoswe_inline_comment` — identical mechanism, separate issue.
