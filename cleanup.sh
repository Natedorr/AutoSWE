#!/bin/bash
# cleanup.sh - autoSWE Full Reset
#
# Kills stuck poller / claude / node processes, releases the flock, and clears
# running/ PID artifacts so the next cron firing comes up clean.
#
# WARNING: kills ALL `claude` and `node` processes for the user - including
# any interactive Claude Code session in another terminal.
#
# Idempotent - safe to run on a clean system (exits 0, all-zero summary).
#
# Cron or manual: ./cleanup.sh

# Deliberate: do NOT use `set -e` - individual step failures must not stop
# subsequent steps. Tolerate "no such process", missing files, etc.
set +e
set +u

LOCKFILE="/tmp/autoswe.lock"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export AUTOSWE_DIR="${AUTOSWE_DIR:-$SCRIPT_DIR}"
RUNNING_DIR="$AUTOSWE_DIR/running"

ts() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"; }

# Return all descendant PIDs of $1 (direct + transitive children)
get_children() {
    local parent=$1
    local children=$(pgrep -P "$parent" 2>/dev/null || true)
    for c in $children; do
        get_children "$c"
    done
    [ -n "$children" ] && echo "$children"
}

# -- Banner / Warning -- ---------------------------------------------------------
ts "============================================================"
ts "  autoSWE FULL RESET - cleaning up stuck poller state"
ts "============================================================"
ts "WARNING: this script will kill ALL `claude` and `node` processes,"
ts "         including any interactive Claude Code session."

# -- Counters -------------------------------------------------------------------
poller_killed=0
claude_node_killed=0
lock_removed="no"
pid_files=0
done_files=0
result_files=0

# -- Step 1: Kill all claude and node processes (deepest leaves first) ----------
for cmd in claude node; do
    pids="$(pgrep -x "$cmd" 2>/dev/null || true)"
    if [ -n "$pids" ]; then
        for p in $pids; do
            ts "KILL $cmd PID=$p"
            kill -KILL "$p" 2>/dev/null
            claude_node_killed=$((claude_node_killed + 1))
        done
    else
        ts "No $cmd processes found."
    fi
done

# -- Step 2: Kill poller process tree (bottom-up: children first, parent last) -
# poller.sh holds the flock on fd 9. Killing it releases the lock and lets init
# reap any zombie python children. We kill deepest descendants first so that
# parent processes can exit cleanly before we force them.

poller_sh_pids="$(pgrep -f 'poller\.sh' 2>/dev/null || true)"

if [ -n "$poller_sh_pids" ]; then
    # Collect all descendant PIDs, build a kill list (deepest first)
    all_pids="$poller_sh_pids"
    for parent in $poller_sh_pids; do
        descendants="$(get_children "$parent" || true)"
        for d in $descendants; do
            # Avoid duplicates
            case " $all_pids " in
                *" $d "*) ;;
                *) all_pids="$all_pids $d" ;;
            esac
        done
    done

    # Kill in reverse: deepest children first, poller.sh parents last
    # Rebuild list with parents at the end
    reverse_list=""
    for parent in $poller_sh_pids; do
        reverse_list="$reverse_list $parent"
    done
    for parent in $poller_sh_pids; do
        descendants="$(get_children "$parent" || true)"
        for d in $descendants; do
            reverse_list="$d $reverse_list"
        done
    done

    # TERM first, then KILL holdouts
    for p in $reverse_list; do
        ts "TERM poller-tree PID=$p"
        kill -TERM "$p" 2>/dev/null
    done
    sleep 1
    for p in $reverse_list; do
        if kill -0 "$p" 2>/dev/null; then
            ts "KILL poller-tree PID=$p"
            kill -KILL "$p" 2>/dev/null
            poller_killed=$((poller_killed + 1))
        else
            poller_killed=$((poller_killed + 1))
        fi
    done
    ts "Killed poller process tree (poller.sh + $poller_killed descendants)"
else
    # Fallback: no poller.sh found, try python autoswe.py poller directly
    pids="$(pgrep -f 'autoswe.py poller' 2>/dev/null || true)"
    if [ -n "$pids" ]; then
        for p in $pids; do
            ts "TERM poller PID=$p"
            kill -TERM "$p" 2>/dev/null
        done
        sleep 1
        for p in $pids; do
            if kill -0 "$p" 2>/dev/null; then
                ts "KILL poller PID=$p"
                kill -KILL "$p" 2>/dev/null
                poller_killed=$((poller_killed + 1))
            else
                poller_killed=$((poller_killed + 1))
            fi
        done
    else
        ts "No poller process tree found."
    fi
fi

# -- Step 3: Release flock file ------- -----------------------------------------------
if [ -f "$LOCKFILE" ]; then
    rm -f "$LOCKFILE"
    lock_removed="yes"
    ts "Removed lockfile $LOCKFILE"
else
    ts "Lockfile $LOCKFILE not present."
fi

# -- Step 4: Clear running/ --------- -------------------------------------------
if [ -d "$RUNNING_DIR" ]; then
    for f in "$RUNNING_DIR"/*.pid; do
        [ -f "$f" ] || continue
        rm -f "$f"
        pid_files=$((pid_files + 1))
    done
    for f in "$RUNNING_DIR"/*.done; do
        [ -f "$f" ] || continue
        rm -f "$f"
        done_files=$((done_files + 1))
    done
    for f in "$RUNNING_DIR"/*.result.json; do
        [ -f "$f" ] || continue
        rm -f "$f"
        result_files=$((result_files + 1))
    done
else
    ts "Running directory $RUNNING_DIR does not exist."
fi

# -- Summary ------- ----------------------------------------------
ts "------------------------------------------------------------"
ts "  SUMMARY"
ts "------------------------------------------------------------"
ts "  Poller processes killed : $poller_killed"
ts "  claude/node procs killed : $claude_node_killed"
ts "  Lockfile removed        : $lock_removed"
ts "  PID files deleted       : $pid_files"
ts "  DONE files deleted      : $done_files"
ts "  Result files deleted    : $result_files"
ts "============================================================"
ts "  Done - next poller run should start clean."
ts "============================================================"

exit 0
