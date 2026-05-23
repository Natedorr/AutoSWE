#!/bin/bash
# update.sh — Pull latest autoSWE code from origin/master
#
# Safely updates the autoSWE installation without disrupting running polls.
# Usage:
#   ./update.sh          # pull latest code
#   ./update.sh --force  # discard local changes if there are any
#
# Run this before restarting cron or your poller after a deployment.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FORCE=false

for arg in "$@"; do
    case "$arg" in
        --force) FORCE=true ;;
    esac
done

ts() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"; }

cd "$SCRIPT_DIR"

# Check if we have a git remote
if ! git remote -v | grep -q origin; then
    ts "[ERROR] No git remote 'origin' configured. Is this a clone of the repo?"
    exit 1
fi

# Check for uncommitted changes
if ! git diff --quiet 2>/dev/null || ! git diff --cached --quiet 2>/dev/null; then
    ts "[WARN] Uncommitted changes detected."
    if [ "$FORCE" = true ]; then
        ts "[INFO] --force: discarding local changes..."
        git reset --hard HEAD
    else
        ts "[ABORT] Commit or stash your changes first, or use --force to discard."
        exit 1
    fi
fi

ts "[UPDATE] Fetching latest from origin/master..."
if ! git fetch origin master; then
    ts "[ERROR] Fetch failed. Check network connectivity."
    exit 1
fi

# Check if we're already up to date
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/master)

if [ "$LOCAL" = "$REMOTE" ]; then
    ts "[INFO] Already up to date (commit $LOCAL)"
    exit 0
fi

ts "[UPDATE] Updating to $(git log --oneline origin/master -1 | cut -d' ' -f1)"
if ! git reset --hard origin/master; then
    ts "[ERROR] Reset failed."
    exit 1
fi

# If venv exists, reinstall deps in case requirements changed
if [ -f ".venv/bin/python" ]; then
    ts "[UPDATE] Reinstalling pip dependencies..."
    .venv/bin/pip install -q -r requirements.txt 2>/dev/null || true
    ts "[INFO] Dependencies updated."
elif [ -f "requirements.txt" ]; then
    ts "[INFO] No venv detected. Run: python -m venv .venv \u0026\u0026 source .venv/bin/activate \u0026\u0026 pip install -r requirements.txt"
fi

ts "[DONE] Updated successfully."
