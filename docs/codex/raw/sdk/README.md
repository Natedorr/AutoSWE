# OpenAI Codex SDK — Crawled Documentation Index

**Crawled:** 2026-05-26  
**Source:** https://github.com/openai/codex/tree/main/sdk

This directory contains raw source files, documentation, and examples crawled from the OpenAI Codex repository for the autoSWE project.

---

## Directory Structure

```
raw/sdk/
├── README.md                          ← This index file
├── typescript/                        ← TypeScript SDK
│   ├── README.md                      ← SDK README
│   ├── package.json                   ← NPM package metadata (@openai/codex-sdk)
│   ├── codex.ts                       ← Codex class (main entry point)
│   ├── codexOptions.ts                ← CodexOptions type definition
│   ├── thread.ts                      ← Thread class (run, runStreamed)
│   ├── threadOptions.ts               ← ThreadOptions, SandboxMode, ApprovalMode, WebSearchMode
│   ├── turnOptions.ts                 ← TurnOptions (outputSchema, signal)
│   ├── events.ts                      ← ThreadEvent types (8 event types)
│   ├── items.ts                       ← ThreadItem types (8 item types)
│   ├── exec.ts                        ← CodexExec (CLI process spawning, config serialization)
│   ├── index.ts                       ← Public exports
│   ├── outputSchemaFile.ts            ← Structured output schema temp file handling
│   ├── basic_streaming.ts             ← Sample: interactive streaming REPL
│   ├── structured_output.ts           ← Sample: JSON schema output
│   ├── structured_output_zod.ts       ← Sample: Zod-based schema output
│   └── helpers.ts                     ← Sample helper functions
│
└── python/                            ← Python SDK
    ├── README.md                      ← SDK README
    ├── pyproject.toml                 ← Project metadata (openai-codex 0.131.0a4)
    ├── api-reference.md               ← Full API reference documentation
    ├── getting-started.md             ← Installation + usage guide
    ├── faq.md                         ← FAQ / common pitfalls
    ├── __init__.py                    ← Package exports
    ├── api.py                         ← Codex, AsyncCodex, Thread, AsyncThread, TurnHandle, AsyncTurnHandle
    ├── async_client.py                ← AsyncAppServerClient (async wrapper around sync client)
    ├── _approval_mode.py              ← ApprovalMode enum (auto_review, deny_all)
    ├── _inputs.py                     ← Input types (TextInput, ImageInput, LocalImageInput, SkillInput, MentionInput)
    ├── _login.py                      ← Login handles (ChatGPT browser login, device code login)
    ├── _message_router.py             ← Turn notification routing
    ├── _run.py                        ← TurnResult, event collection helpers
    ├── _runtime_setup.py              ← Runtime configuration setup
    └── examples/                      ← 15 example programs
        ├── README.md                  ← Examples index
        ├── _bootstrap.py              ← Shared bootstrap code
        ├── 01_quickstart_sync.py      ← Basic sync usage
        ├── 01_quickstart_async.py     ← Basic async usage
        ├── 02_turn_run_sync.py        ← Turn execution
        ├── 03_stream_sync.py          ← Streaming events
        ├── 04_metadata_sync.py        ← Server metadata inspection
        ├── 05_existing_thread_sync.py ← Resume existing thread
        ├── 06_lifecycle_sync.py       ← Full thread lifecycle (start, fork, archive, resume)
        ├── 07_image_sync.py           ← Image input
        ├── 08_local_image_sync.py     ← Local image file input
        ├── 09_async_parity.py         ← Async/sync parity
        ├── 10_retry_sync.py           ← Error handling and retry
        ├── 11_cli_mini_app_sync.py    ← CLI mini-app
        ├── 12_kitchen_sink_sync.py    ← Turn params kitchen sink
        ├── 13_model_select_sync.py    ← Model selection and turn params
        ├── 14_turn_controls_sync.py   ← Turn steering and interrupt
        └── 15_login_sync.py           ← Login and account management
```

## Source URLs

### TypeScript SDK
| File | Source URL |
|------|-----------|
| `codex.ts` | https://raw.githubusercontent.com/openai/codex/main/sdk/typescript/src/codex.ts |
| `codexOptions.ts` | https://raw.githubusercontent.com/openai/codex/main/sdk/typescript/src/codexOptions.ts |
| `thread.ts` | https://raw.githubusercontent.com/openai/codex/main/sdk/typescript/src/thread.ts |
| `threadOptions.ts` | https://raw.githubusercontent.com/openai/codex/main/sdk/typescript/src/threadOptions.ts |
| `turnOptions.ts` | https://raw.githubusercontent.com/openai/codex/main/sdk/typescript/src/turnOptions.ts |
| `events.ts` | https://raw.githubusercontent.com/openai/codex/main/sdk/typescript/src/events.ts |
| `items.ts` | https://raw.githubusercontent.com/openai/codex/main/sdk/typescript/src/items.ts |
| `exec.ts` | https://raw.githubusercontent.com/openai/codex/main/sdk/typescript/src/exec.ts |
| `index.ts` | https://raw.githubusercontent.com/openai/codex/main/sdk/typescript/src/index.ts |
| `outputSchemaFile.ts` | https://raw.githubusercontent.com/openai/codex/main/sdk/typescript/src/outputSchemaFile.ts |
| `package.json` | https://raw.githubusercontent.com/openai/codex/main/sdk/typescript/package.json |
| `README.md` | https://raw.githubusercontent.com/openai/codex/main/sdk/typescript/README.md |

### TypeScript SDK Samples
| File | Source URL |
|------|-----------|
| `basic_streaming.ts` | https://raw.githubusercontent.com/openai/codex/main/sdk/typescript/samples/basic_streaming.ts |
| `structured_output.ts` | https://raw.githubusercontent.com/openai/codex/main/sdk/typescript/samples/structured_output.ts |
| `structured_output_zod.ts` | https://raw.githubusercontent.com/openai/codex/main/sdk/typescript/samples/structured_output_zod.ts |
| `helpers.ts` | https://raw.githubusercontent.com/openai/codex/main/sdk/typescript/samples/helpers.ts |

### Python SDK
| File | Source URL |
|------|-----------|
| `api.py` | https://raw.githubusercontent.com/openai/codex/main/sdk/python/src/openai_codex/api.py |
| `async_client.py` | https://raw.githubusercontent.com/openai/codex/main/sdk/python/src/openai_codex/async_client.py |
| `_approval_mode.py` | https://raw.githubusercontent.com/openai/codex/main/sdk/python/src/openai_codex/_approval_mode.py |
| `_inputs.py` | https://raw.githubusercontent.com/openai/codex/main/sdk/python/src/openai_codex/_inputs.py |
| `_login.py` | https://raw.githubusercontent.com/openai/codex/main/sdk/python/src/openai_codex/_login.py |
| `_message_router.py` | https://raw.githubusercontent.com/openai/codex/main/sdk/python/src/openai_codex/_message_router.py |
| `_run.py` | https://raw.githubusercontent.com/openai/codex/main/sdk/python/src/openai_codex/_run.py |
| `__init__.py` | https://raw.githubusercontent.com/openai/codex/main/sdk/python/src/openai_codex/__init__.py |
| `api-reference.md` | https://raw.githubusercontent.com/openai/codex/main/sdk/python/docs/api-reference.md |
| `getting-started.md` | https://raw.githubusercontent.com/openai/codex/main/sdk/python/docs/getting-started.md |
| `faq.md` | https://raw.githubusercontent.com/openai/codex/main/sdk/python/docs/faq.md |
| `pyproject.toml` | https://raw.githubusercontent.com/openai/codex/main/sdk/python/pyproject.toml |
| `README.md` | https://raw.githubusercontent.com/openai/codex/main/sdk/python/README.md |

### Python SDK Examples (15 total)
All examples sourced from `https://raw.githubusercontent.com/openai/codex/main/sdk/python/examples/<dir>/`.

## File Counts

| Category | TypeScript | Python |
|----------|-----------|--------|
| Source files | 11 | 9 |
| Documentation | 1 (README) | 4 (README + docs) |
| Examples/Samples | 4 | 15 + README |
| Config | 1 (package.json) | 1 (pyproject.toml) |
| **Total** | **17** | **30** |
