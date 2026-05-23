#!/bin/bash
# poller.sh — autoSWE GitHub Poller
#
# Architecture:
# 1. Acquires flock on /tmp/autoswe.lock
# 2. Runs python3 autoswe.py poller which:
#    - Syncs GitHub issues
#    - Posts welcome comments
#    - Processes tasks one by one until queue empty
#
# To update autoSWE code: use ./update.sh (Linux) or update.bat (Windows)
#
# Cron: */10 * * * * /path/to/autoswe/poller.sh >> /path/to/autoswe/logs/poller.log 2>&1

set -euo pipefail

# Ensure npm global and local bins are in PATH (needed for cron which has minimal PATH)
export PATH="$HOME/.npm-global/bin:$PATH"

LOCKFILE="/tmp/autoswe.lock"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export AUTOSWE_DIR="${AUTOSWE_DIR:-$SCRIPT_DIR}"
AUTOSWE_PY="$AUTOSWE_DIR/autoswe.py"
PYTHON="${PYTHON:-python3}"

ts() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"; }

# Flock guard — non-blocking, skip if already running
exec 9>"$LOCKFILE"
if ! flock -n 9; then
    ts "[SKIP] poller already running (lockfile held)"
    exit 0
fi

ts "[START] poller run (acquired lock)"
trap 'ts "[ERROR] poller aborted unexpectedly at line $LINENO (exit $?)"' ERR

"$PYTHON" "$AUTOSWE_PY" poller --drain

ts "[DONE] poller run complete"
