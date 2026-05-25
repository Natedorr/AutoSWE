# Authentication

Codex supports two authentication methods:

## ChatGPT Subscription (Default)

Run `codex` and select **Sign in with ChatGPT**. Works with Plus, Pro, Business, Edu, or Enterprise plans.

This is the easiest path — no API key management needed.

## API Key

Set the `OPENAI_API_KEY` environment variable:

```bash
export OPENAI_API_KEY="sk-proj-..."
codex "explain this codebase"
```

API key auth is required for:
- Headless/CI environments
- Non-ChatGPT subscription billing
- `codex exec` in automation pipelines

## Configuration

Auth settings live in `~/.codex/config.toml`. Codex stores credentials securely per-platform.

### Logging Out

```bash
# Via TUI
/logout

# CLI
codex --logout
```

## See Also

- [Installation](./installation.md)
- [Configuration](./configuration.md)
