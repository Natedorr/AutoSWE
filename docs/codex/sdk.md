# OpenAI Codex SDK Reference

> Comprehensive reference for both the TypeScript and Python SDKs, built from source code and documentation crawled from the [openai/codex](https://github.com/openai/codex) repository.
> 
> Raw source files: [`docs/codex/raw/sdk/`](raw/sdk/)
> Crawled: 2026-05-26

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [TypeScript SDK](#typescript-sdk)
  - [Installation](#installation-ts)
  - [Codex Class](#codex-class-ts)
  - [Thread Class](#thread-class-ts)
  - [Thread Options](#thread-options-ts)
  - [Turn Options](#turn-options-ts)
  - [Events](#events-ts)
  - [Thread Items](#thread-items-ts)
  - [Structured Output](#structured-output-ts)
  - [Streaming](#streaming-ts)
  - [Samples](#typescript-samples)
- [Python SDK](#python-sdk)
  - [Installation](#installation-py)
  - [Codex (sync)](#codex-class-py)
  - [AsyncCodex](#asynccodex-class-py)
  - [Thread / AsyncThread](#thread-class-py)
  - [TurnHandle / AsyncTurnHandle](#turnhandle-class-py)
  - [TurnResult](#turnresult-py)
  - [Input Types](#input-types-py)
  - [Approval Modes](#approval-modes-py)
  - [Login Methods](#login-methods-py)
  - [Errors & Retry](#errors-and-retry-py)
- [Comparison: TypeScript vs Python](#comparison)
- [MCP Server Integration](#mcp-server-integration)
- [CLI Config Overrides](#cli-config-overrides)

---

## Architecture Overview

Both SDKs wrap the Codex CLI (`codex` executable) and communicate via **JSONL over stdin/stdout**.

```
┌─────────────────┐
│   Your Code     │
│  (TypeScript /  │
│   Python)       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   SDK Wrapper   │
│  Codex/Thread/  │
│  TurnHandle     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  codex CLI      │
│  (Rust binary)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   app-server    │
│  (JSON-RPC v2)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  OpenAI API     │
│  (GPT-4/Codex)  │
└─────────────────┘
```

The **TypeScript SDK** uses `child_process.spawn` to run the CLI with `--experimental-json` and streams JSONL events.

The **Python SDK** communicates with the local `app-server` via JSON-RPC over stdin/stdout, providing both synchronous and asynchronous APIs.

---

## TypeScript SDK

**Package:** `@openai/codex-sdk`  
**License:** Apache-2.0  
**Engine:** Node.js >= 18  
**Repository:** https://github.com/openai/codex/tree/main/sdk/typescript

<a id="installation-ts"></a>
### Installation

```bash
npm install @openai/codex-sdk
```

Requires `@openai/codex` (the CLI) to be installed with optional dependencies for platform-specific binaries.

<a id="codex-class-ts"></a>
### Codex Class

```typescript
import { Codex } from "@openai/codex-sdk";
```

The main entry point. Wraps the `codex` CLI executable.

```typescript
const codex = new Codex(options?: CodexOptions);
```

**Constructor Options (`CodexOptions`):**

| Option | Type | Description |
|--------|------|-------------|
| `codexPathOverride` | `string` | Override path to the `codex` executable |
| `baseUrl` | `string` | Override OpenAI API base URL (passed as `--config openai_base_url=...`) |
| `apiKey` | `string` | API key (injected as `CODEX_API_KEY` env var) |
| `config` | `CodexConfigObject` | JSON object of `--config key=value` overrides, serialized as TOML literals |
| `env` | `Record<string, string>` | Environment variables for the CLI process. If provided, does NOT inherit from `process.env`. |

**Methods:**

| Method | Return | Description |
|--------|--------|-------------|
| `startThread(options?: ThreadOptions)` | `Thread` | Start a new conversation thread |
| `resumeThread(id: string, options?: ThreadOptions)` | `Thread` | Resume an existing thread by ID (persisted in `~/.codex/sessions`) |

**Quickstart:**

```typescript
import { Codex } from "@openai/codex-sdk";

const codex = new Codex();
const thread = codex.startThread();
const turn = await thread.run("Diagnose the test failure and propose a fix");

console.log(turn.finalResponse);
console.log(turn.items);

// Multi-turn: continue the same conversation
const nextTurn = await thread.run("Implement the fix");
```

<a id="thread-class-ts"></a>
### Thread Class

Represents a conversation thread. One thread can have multiple consecutive turns.

```typescript
type Input = string | UserInput[];

type UserInput =
  | { type: "text"; text: string }
  | { type: "local_image"; path: string };
```

**Methods:**

| Method | Return | Description |
|--------|--------|-------------|
| `run(input: Input, turnOptions?: TurnOptions)` | `Promise<Turn>` | Execute a turn synchronously (buffers until completion) |
| `runStreamed(input: Input, turnOptions?: TurnOptions)` | `Promise<StreamedTurn>` | Execute a turn with streaming events (async generator) |

**Return Types:**

```typescript
type Turn = RunResult = {
  items: ThreadItem[];
  finalResponse: string;
  usage: Usage | null;
};

type StreamedTurn = RunStreamedResult = {
  events: AsyncGenerator<ThreadEvent>;
};
```

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `id` | `string \| null` | Thread ID, populated after the first turn starts |

<a id="thread-options-ts"></a>
### Thread Options

```typescript
type ThreadOptions = {
  model?: string;                        // Model to use (e.g. "gpt-5.4")
  sandboxMode?: SandboxMode;             // Sandbox level
  workingDirectory?: string;             // Working directory (must be a Git repo by default)
  skipGitRepoCheck?: boolean;            // Skip the Git repository check
  modelReasoningEffort?: ModelReasoningEffort;  // Reasoning effort level
  networkAccessEnabled?: boolean;        // Allow network access in workspace-write sandbox
  webSearchMode?: WebSearchMode;         // Web search mode
  webSearchEnabled?: boolean;            // Legacy web search toggle (maps to webSearchMode)
  approvalPolicy?: ApprovalMode;         // Approval policy
  additionalDirectories?: string[];      // Additional directories for sandbox access
};

type ApprovalMode = "never" | "on-request" | "on-failure" | "untrusted";
type SandboxMode = "read-only" | "workspace-write" | "danger-full-access";
type ModelReasoningEffort = "minimal" | "low" | "medium" | "high" | "xhigh";
type WebSearchMode = "disabled" | "cached" | "live";
```

<a id="turn-options-ts"></a>
### Turn Options

```typescript
type TurnOptions = {
  outputSchema?: unknown;    // JSON schema for structured output
  signal?: AbortSignal;      // AbortSignal to cancel the turn
};
```

<a id="events-ts"></a>
### Events

The SDK emits 8 types of `ThreadEvent`s, based on `codex-rs/exec/src/exec_events.rs`:

| Event Type | Event String | Description |
|------------|-------------|-------------|
| `ThreadStartedEvent` | `"thread.started"` | First event; contains `thread_id` |
| `TurnStartedEvent` | `"turn.started"` | New turn started |
| `TurnCompletedEvent` | `"turn.completed"` | Turn finished; includes `usage` |
| `TurnFailedEvent` | `"turn.failed"` | Turn failed with `error` |
| `ItemStartedEvent` | `"item.started"` | New item added (typically "in progress") |
| `ItemUpdatedEvent` | `"item.updated"` | Item updated (e.g., todo list progress) |
| `ItemCompletedEvent` | `"item.completed"` | Item reached terminal state |
| `ThreadErrorEvent` | `"error"` | Fatal error from the stream |

```typescript
type Usage = {
  input_tokens: number;
  cached_input_tokens: number;
  output_tokens: number;
  reasoning_output_tokens: number;
};
```

<a id="thread-items-ts"></a>
### Thread Items

8 types of `ThreadItem`:

| Item Type | Description |
|-----------|-------------|
| `AgentMessageItem` | Agent's response text (natural language or JSON) |
| `ReasoningItem` | Agent's reasoning summary |
| `CommandExecutionItem` | Command executed by the agent (with command, output, exit_code, status) |
| `FileChangeItem` | File changes by the agent (add/delete/update with path and status) |
| `McpToolCallItem` | MCP tool call (server, tool, arguments, result/error, status) |
| `WebSearchItem` | Web search request (query) |
| `TodoListItem` | Agent's running todo list (items with text and completed flag) |
| `ErrorItem` | Non-fatal error surfaced as an item |

<a id="structured-output-ts"></a>
### Structured Output

Request the agent to produce JSON conforming to a schema:

```typescript
const schema = {
  type: "object",
  properties: {
    summary: { type: "string" },
    status: { type: "string", enum: ["ok", "action_required"] },
  },
  required: ["summary", "status"],
  additionalProperties: false,
};

const turn = await thread.run("Summarize repository status", { outputSchema: schema });
console.log(turn.finalResponse); // JSON string matching schema
```

Zod support via `zod-to-json-schema`:

```typescript
import z from "zod";
import zodToJsonSchema from "zod-to-json-schema";

const schema = z.object({
  summary: z.string(),
  status: z.enum(["ok", "action_required"]),
});

const turn = await thread.run("Summarize repository status", {
  outputSchema: zodToJsonSchema(schema, { target: "openAi" }),
});
```

<a id="streaming-ts"></a>
### Streaming

```typescript
const { events } = await thread.runStreamed("Diagnose the test failure");

for await (const event of events) {
  switch (event.type) {
    case "item.completed":
      console.log("item", event.item);
      break;
    case "turn.completed":
      console.log("usage", event.usage);
      break;
    case "item.updated":
      if (event.item.type === "todo_list") {
        console.log("Todo list:", event.item.items);
      }
      break;
  }
}
```

<a id="typescript-samples"></a>
### Samples

| Sample | Description |
|--------|-------------|
| `basic_streaming.ts` | Interactive REPL with full event handling |
| `structured_output.ts` | JSON schema structured output |
| `structured_output_zod.ts` | Zod-based schema structured output |

---

## Python SDK

**Package:** `openai-codex`  
**Version:** 0.131.0a4 (alpha)  
**License:** Apache-2.0  
**Requires:** Python >= 3.10  
**Runtime Dependency:** `openai-codex-cli-bin==0.131.0a4`  
**Repository:** https://github.com/openai/codex/tree/main/sdk/python

<a id="installation-py"></a>
### Installation

```bash
pip install openai-codex
```

Requires the `openai-codex-cli-bin` runtime package to be installed (comes as a dependency).

<a id="codex-class-py"></a>
### Codex (sync)

```python
from openai_codex import Codex

with Codex() as codex:
    # ... use codex
```

`Codex()` is **eager**: it starts the app-server transport and calls `initialize` in `__init__`.

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `metadata` | `InitializeResponse` | Server info, API version, capabilities |

**Methods:**

| Method | Description |
|--------|-------------|
| `login_api_key(api_key: str)` | Authenticate with API key |
| `login_chatgpt()` → `ChatgptLoginHandle` | Start browser-based ChatGPT login |
| `login_chatgpt_device_code()` → `DeviceCodeLoginHandle` | Start device-code login |
| `account(refresh_token=False)` → `GetAccountResponse` | Read current account state |
| `logout()` | Clear session |
| `close()` | Close the app-server connection |
| `models(include_hidden=False)` → `ModelListResponse` | List available models |

**Thread Methods:**

| Method | Description |
|--------|-------------|
| `thread_start(model, sandbox, approval_mode, cwd, base_instructions, developer_instructions, config, personality, model_provider, ephemeral, service_name, service_tier, session_start_source, thread_source)` → `Thread` | Create a new thread |
| `thread_resume(thread_id, ...)` → `Thread` | Resume an existing thread |
| `thread_list(archived, cursor, cwd, limit, model_providers, search_term, sort_direction, sort_key, source_kinds)` → `ThreadListResponse` | List threads |
| `thread_fork(thread_id, ...)` → `Thread` | Fork a thread from a checkpoint |
| `thread_archive(thread_id)` → `ThreadArchiveResponse` | Archive a thread |
| `thread_unarchive(thread_id)` → `Thread` | Unarchive a thread |

**Quickstart:**

```python
from openai_codex import Codex

with Codex() as codex:
    thread = codex.thread_start(model="gpt-5.4", config={"model_reasoning_effort": "high"})
    result = thread.run("Say hello in one sentence.")
    print(result.final_response)
```

<a id="asynccodex-class-py"></a>
### AsyncCodex

```python
import asyncio
from openai_codex import AsyncCodex

async def main():
    async with AsyncCodex() as codex:
        thread = await codex.thread_start(model="gpt-5.4")
        result = await thread.run("Hello from async.")
        print(result.final_response)

asyncio.run(main())
```

`AsyncCodex` is an async mirror of `Codex` with identical API shape. All methods are `async`. It initializes **lazily** on context entry or first awaited API call.

<a id="thread-class-py"></a>
### Thread / AsyncThread

**Thread methods:**

| Method | Return | Description |
|--------|--------|-------------|
| `run(input, approval_mode, cwd, effort, model, output_schema, personality, sandbox_policy, service_tier, summary)` | `TurnResult` | Execute a turn and collect result |
| `turn(input, ...)` | `TurnHandle` | Start a turn, get handle for streaming/steering |
| `read(include_turns=False)` | `ThreadReadResponse` | Read thread contents |
| `set_name(name)` | `ThreadSetNameResponse` | Rename thread |
| `compact()` | `ThreadCompactStartResponse` | Start thread compaction |

**Thread properties:**

| Property | Type | Description |
|----------|------|-------------|
| `id` | `str` | Thread ID |

**Multi-turn example:**

```python
with Codex() as codex:
    thread = codex.thread_start(model="gpt-5.4")
    first = thread.run("Summarize Rust ownership in 2 bullets.")
    second = thread.run("Now explain it to a Python developer.")
```

<a id="turnhandle-class-py"></a>
### TurnHandle / AsyncTurnHandle

Low-level turn control. Use when you need streaming, steering, or interrupting.

| Method | Return | Description |
|--------|--------|-------------|
| `steer(input)` | `TurnSteerResponse` | Send steering input to an in-progress turn |
| `interrupt()` | `TurnInterruptResponse` | Interrupt a running turn |
| `stream()` | `Iterator[Notification]` | Stream raw notifications for this turn |
| `run()` | `TurnResult` | Collect turn result from the stream |

**Streaming example:**

```python
with Codex() as codex:
    thread = codex.thread_start(model="gpt-5.4")
    turn = thread.turn("Explain SIMD in 3 bullets.")
    
    for event in turn.stream():
        if event.method == "item/agentMessage/delta":
            print(event.payload.delta, end="", flush=True)
        if event.method == "turn/completed":
            print(f"\nTurn {event.payload.turn.status.value}")
```

**Steering example:**

```python
with Codex() as codex:
    thread = codex.thread_start(model="gpt-5.4")
    turn = thread.turn("Count from 1 to 40 with commas.")
    turn.steer("Keep it brief and stop after 10 numbers.")
```

<a id="turnresult-py"></a>
### TurnResult

```python
@dataclass
class TurnResult:
    id: str
    status: TurnStatus                    # "completed" | "failed" | "interrupted"
    error: TurnError | None
    started_at: int | None
    completed_at: int | None
    duration_ms: int | None
    final_response: str | None            # None if no final-answer item
    items: list[ThreadItem]
    usage: ThreadTokenUsage | None
```

<a id="input-types-py"></a>
### Input Types

```python
from openai_codex import (
    TextInput, ImageInput, LocalImageInput, SkillInput, MentionInput
)

# Plain string shorthand
thread.run("Hello")

# Structured inputs
thread.run([
    TextInput("Describe this image"),
    ImageInput("https://example.com/image.png"),
])

thread.run([
    TextInput("Analyze this screenshot"),
    LocalImageInput("/path/to/screenshot.png"),
])
```

| Input Type | Wire Format | Description |
|------------|-------------|-------------|
| `TextInput` | `{"type": "text", "text": ...}` | Plain text |
| `ImageInput` | `{"type": "image", "url": ...}` | Remote image URL |
| `LocalImageInput` | `{"type": "localImage", "path": ...}` | Local file path |
| `SkillInput` | `{"type": "skill", "name": ..., "path": ...}` | Reference a skill |
| `MentionInput` | `{"type": "mention", "name": ..., "path": ...}` | Mention a file/path |

<a id="approval-modes-py"></a>
### Approval Modes

```python
from openai_codex import ApprovalMode

ApprovalMode.auto_review   # Ask for approval on escalated requests, auto-reviewer handles them
ApprovalMode.deny_all      # Never request approval (deny all escalated actions)
```

<a id="login-methods-py"></a>
### Login Methods

```python
# API key login (synchronous, no handle)
codex.login_api_key("sk-...")

# Browser-based ChatGPT login
login = codex.login_chatgpt()
print(login.auth_url)         # URL to open in browser
completed = login.wait()      # Blocks until login completes
print(completed.success)

# Device-code login
login = codex.login_chatgpt_device_code()
print(login.verification_url)  # URL to visit
print(login.user_code)         # Code to enter
completed = login.wait()

# Check account state
account = codex.account()
```

<a id="errors-and-retry-py"></a>
### Errors & Retry

```python
from openai_codex import (
    retry_on_overload,
    JsonRpcError, ServerBusyError,
    is_retryable_error,
)

# Automatic retry with exponential backoff + jitter
result = retry_on_overload(
    lambda: thread.turn("Some query.").run(),
    max_attempts=3,
    initial_delay_s=0.25,
    max_delay_s=2.0,
)

# Check if an error is retryable
if is_retryable_error(exc):
    # retry logic
```

**Error types:**

| Error Class | Description |
|-------------|-------------|
| `AppServerError` | Generic app-server error |
| `TransportClosedError` | Transport disconnected |
| `JsonRpcError` | Base JSON-RPC error |
| `ParseError` | JSON parse error |
| `InvalidRequestError` | Invalid request |
| `MethodNotFoundError` | Method not found |
| `InvalidParamsError` | Invalid parameters |
| `InternalRpcError` | Internal server error |
| `ServerBusyError` | Server overloaded (retryable) |
| `AppServerRpcError` | App-server specific RPC error |
| `RetryLimitExceededError` | All retry attempts exhausted |

---

## Comparison

| Feature | TypeScript SDK | Python SDK |
|---------|---------------|------------|
| **Package** | `@openai/codex-sdk` | `openai-codex` |
| **Transport** | CLI via `child_process.spawn` + JSONL | app-server via JSON-RPC v2 |
| **Sync API** | `Codex` + `Thread.run()` | `Codex` + `Thread.run()` |
| **Async API** | Native async/await (async generators) | `AsyncCodex` + `AsyncThread` |
| **Streaming** | `runStreamed()` → async generator | `turn().stream()` → iterator |
| **Input Types** | `string`, `{text}`, `{local_image}` | `str`, `TextInput`, `ImageInput`, `LocalImageInput`, `SkillInput`, `MentionInput` |
| **Structured Output** | `TurnOptions.outputSchema` | `output_schema` kwarg on `run()`/`turn()` |
| **Login Methods** | Via `apiKey` option / env var | `login_api_key()`, `login_chatgpt()`, `login_chatgpt_device_code()` |
| **Thread Management** | `startThread()`, `resumeThread()` | `thread_start()`, `thread_resume()`, `thread_fork()`, `thread_archive()`, `thread_unarchive()`, `thread_list()` |
| **Turn Controls** | `signal: AbortSignal` | `steer()`, `interrupt()`, `stream()` |
| **Sandbox Modes** | `read-only`, `workspace-write`, `danger-full-access` | Via `sandbox` parameter |
| **Approval Modes** | `never`, `on-request`, `on-failure`, `untrusted` | `auto_review`, `deny_all` |
| **Retry** | Manual (AbortSignal for cancellation) | `retry_on_overload()`, `is_retryable_error()` |
| **Config Overrides** | `config` option (JSON → TOML) | `config` dict on thread/turn methods |
| **Multi-turn** | Reuse same `Thread` instance | Reuse same `Thread` instance |
| **Thread ID** | Auto-assigned after first turn | Returned by `thread_start()` |
| **Concurrency** | Multiple threads per `Codex` instance | Multiple concurrent turns via turn ID routing |
| **Min Runtime** | Node.js 18+ | Python 3.10+ |

---

## MCP Server Integration

The Codex CLI supports MCP (Model Context Protocol) tool calls. When the agent invokes an MCP tool, you'll receive an `McpToolCallItem`:

```typescript
type McpToolCallItem = {
  id: string;
  type: "mcp_tool_call";
  server: string;           // MCP server name
  tool: string;             // Tool name
  arguments: unknown;       // Tool arguments
  result?: {                // Success response
    content: McpContentBlock[];
    _meta?: unknown;
    structured_content: unknown;
  };
  error?: {                 // Failure response
    message: string;
  };
  status: "in_progress" | "completed" | "failed";
};
```

MCP servers are configured via the Codex CLI configuration. The SDK itself does not directly manage MCP servers — they are configured at the app-server/CLI level.

---

## CLI Config Overrides

### TypeScript

```typescript
const codex = new Codex({
  config: {
    show_raw_agent_reasoning: true,
    sandbox_workspace_write: { network_access: true },
  },
});
```

The SDK accepts a JSON object, flattens it into dotted paths, and serializes values as TOML literals before passing them as `--config key=value` flags.

### Python

```python
thread = codex.thread_start(
    model="gpt-5.4",
    config={"model_reasoning_effort": "high"}
)
```

The `config` dict is passed as a JSON object to the app-server.

---

## Raw Files

All raw source files, documentation, and examples are stored in [`docs/codex/raw/sdk/`](raw/sdk/). See the [index](raw/sdk/README.md) for the complete file listing.
