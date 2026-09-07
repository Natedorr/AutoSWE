#!/bin/bash
# setup.sh — autoSWE Interactive Setup Wizard
#
# Runs the first-run setup wizard to configure credentials and settings.
# Creates config/repos.json and config/autoswe.env.
#
# Usage:
#   ./setup.sh          # guided first-run setup
#   ./setup.sh --force  # overwrite existing config without prompting
#   ./setup.sh --no-warmup   # skip the pi-mcp cold-start warm-up

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export AUTOSWE_DIR="${AUTOSWE_DIR:-$SCRIPT_DIR}"
AUTOSWE_PY="$AUTOSWE_DIR/autoswe.py"
PYTHON="${PYTHON:-python3}"

# Prefer venv if present
if [ -f "$AUTOSWE_DIR/.venv/bin/python" ]; then
    PYTHON="$AUTOSWE_DIR/.venv/bin/python"
fi

# Run the setup wizard, preserving any user-supplied flags (e.g. --force).
"$PYTHON" "$AUTOSWE_PY" setup "$@"

# pi Phase 4 cold-start warm-up (docs/autoswe/PLAN-pi-mcp.md): populate each pi
# profile's mcp-cache.json so the first real run uses the direct
# mcp__autoswe_comment_* tools. Skips cleanly (exit 0) when no pi profile with
# an agent_dir is configured, so non-pi setups are unaffected. Skipped entirely
# with --no-warmup.
if [[ " $* " != *" --no-warmup "* ]]; then
    "$PYTHON" "$AUTOSWE_PY" warmup || echo "  pi-mcp warm-up not complete (first pi run will use proxy tool shapes)"
fi
