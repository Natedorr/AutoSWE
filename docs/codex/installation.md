# Installing Codex CLI

## System Requirements

| Requirement | Details |
|---|---|
| Operating systems | macOS 12+, Ubuntu 20.04+/Debian 10+, Windows 11 via WSL2 |
| Git (optional) | 2.23+ for built-in PR helpers |
| RAM | 4 GB minimum (8 GB recommended) |

## Installation Methods

### npm (recommended)

```bash
npm install -g @openai/codex
```

### Homebrew

```bash
brew install --cask codex
```

### curl install script

```bash
# macOS / Linux
curl -fsSL https://chatgpt.com/codex/install.sh | sh
```

### Windows PowerShell

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://chatgpt.com/codex/install.ps1 | iex"
```

### GitHub Releases

Download from [github.com/openai/codex/releases/latest](https://github.com/openai/codex/releases/latest):

| Platform | Archive |
|---|---|
| macOS Apple Silicon | `codex-aarch64-apple-darwin.tar.gz` |
| macOS x86_64 | `codex-x86_64-apple-darwin.tar.gz` |
| Linux x86_64 | `codex-x86_64-unknown-linux-musl.tar.gz` |
| Linux arm64 | `codex-aarch64-unknown-linux-musl.tar.gz` |

Extract, then rename the binary to `codex`.

## Build from Source

Codex is written in Rust:

```bash
git clone https://github.com/openai/codex.git
cd codex/codex-rs

# Install Rust toolchain
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
source "$HOME/.cargo/env"
rustup component add rustfmt
rustup component add clippy

# Install build helpers
cargo install --locked just
cargo install --locked cargo-nextest

# Build
cargo build

# Run
cargo run --bin codex -- "explain this codebase to me"
```

## Shell Completions

```bash
# Bash
codex completion bash >> ~/.bashrc

# Zsh
echo 'eval "$(codex completion zsh)"' >> ~/.zshrc

# Fish
codex completion fish > ~/.config/fish/completions/codex.fish
```

## Verification

```bash
codex --version
codex --ask-for-approval never "What instructions are loaded?"
```

## Logging

```bash
# Plaintext log for TUI
codex -c log_dir=./.codex-log
tail -F ./.codex-log/codex-tui.log

# Verbose logging
RUST_LOG=debug codex exec "explain this file"
```
