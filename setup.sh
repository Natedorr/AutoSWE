#!/bin/bash
# setup.sh — autoSWE Interactive Setup Wizard
#
# Runs the first-run setup wizard to configure credentials and settings.
# Creates config/repos.json and config/autoswe.env.
#
# Usage:
#   ./setup.sh          # guided first-run setup
#   ./setup.sh --force  # overwrite existing config without prompting

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export AUTOSWE_DIR="${AUTOSWE_DIR:-$SCRIPT_DIR}"
AUTOSWE_PY="$AUTOSWE_DIR/autoswe.py"
PYTHON="${PYTHON:-python3}"

# Prefer venv if present
if [ -f "$AUTOSWE_DIR/.venv/bin/python" ]; then
    PYTHON="$AUTOSWE_DIR/.venv/bin/python"
fi

exec "$PYTHON" "$AUTOSWE_PY" setup "$@"
