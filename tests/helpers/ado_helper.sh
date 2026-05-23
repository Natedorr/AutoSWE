#!/bin/bash
# ADO (Azure DevOps) test helper — manage work items via curl.
#
# Usage:
#   tests/helpers/ado_helper.sh [-r REPO_KEY] COMMAND [args...]
#
# Commands:
#   create <title> <description>       Create a new work item, prints WI ID
#   comment <wi> <text>                Post a comment
#   tags <wi>                          Show current tags
#   clear_tags <wi>                    Clear all tags
#   close <wi>                         Close the work item
#   reopen <wi>                        Reopen a closed work item
#   comments <wi>                      List comments
#   prs                                List active PRs
#   poller                             Run the poller (clears lock first)
#   wait_done <wi> [timeout]           Wait for dispatch to finish (default 600s)
#   queue_reset                        Reset queue.json and running/
#
# Examples:
#   tests/helpers/ado_helper.sh create "Test fix" "Fix bug X"
#   tests/helpers/ado_helper.sh comment 92 "/fix"
#   tests/helpers/ado_helper.sh tags 92
#   tests/helpers/ado_helper.sh -r natedorr/otherProject/otherProject comment 5 "/skip"

set -euo pipefail
export PATH="$HOME/.npm-global/bin:$PATH"

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

REPO_KEY="natedorr/testProject/testProject"
while getopts "r:" opt; do
  case $opt in
    r) REPO_KEY="$OPTARG" ;;
    *) ;;
  esac
done
shift $((OPTIND - 1))

PAT=$(python3 -c "
import json, sys
d = json.load(open('${REPO_ROOT}/config/repos.json'))
entry = d.get('${REPO_KEY}', {})
print(entry.get('pat', ''))
")

ORIG=$(python3 -c "
import json
d = json.load(open('${REPO_ROOT}/config/repos.json'))
entry = d.get('${REPO_KEY}', {})
print(entry.get('org', 'natedorr'))
")

PROJECT=$(python3 -c "
import json
d = json.load(open('${REPO_ROOT}/config/repos.json'))
entry = d.get('${REPO_KEY}', {})
print(entry.get('project', 'testProject'))
")

REPO_NAME=$(python3 -c "
import json
d = json.load(open('${REPO_ROOT}/config/repos.json'))
entry = d.get('${REPO_KEY}', {})
print(entry.get('repo', 'testProject'))
")

BASE="https://dev.azure.com/${ORIG}/${PROJECT}/_apis"

cmd=${1:-help}
shift || true

case $cmd in
  create)
    TITLE="$1"; DESC="$2"
    curl -s -X POST "$BASE/wit/workitems/\$Task?api-version=7.1" \
      -u ":$PAT" \
      -H "Content-Type: application/json-patch+json" \
      -d "[
        {\"op\":\"add\",\"path\":\"/fields/System.Title\",\"value\":\"$TITLE\"},
        {\"op\":\"add\",\"path\":\"/fields/System.Description\",\"value\":\"$DESC\"}
      ]" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['id'])"
    ;;
  comment)
    WI=$1; TEXT="$2"
    curl -s -X POST "$BASE/wit/workitems/$WI/comments?api-version=7.1" \
      -u ":$PAT" \
      -H "Content-Type: application/json" \
      -d "{\"text\":\"$TEXT\"}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('id','sent'))"
    ;;
  tags)
    WI=$1
    curl -s "$BASE/wit/workitems/$WI?fields=System.Tags&api-version=7.1" \
      -u ":$PAT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['fields'].get('System.Tags',''))"
    ;;
  clear_tags)
    WI=$1
    curl -s -X PATCH "$BASE/wit/workitems/$WI?api-version=7.1" \
      -u ":$PAT" \
      -H "Content-Type: application/json-patch+json" \
      -d '[{"op":"remove","path":"/fields/System.Tags"}]' > /dev/null
    echo "Tags cleared on #$WI"
    ;;
  close)
    WI=$1
    curl -s -X PATCH "$BASE/wit/workitems/$WI?api-version=7.1" \
      -u ":$PAT" \
      -H "Content-Type: application/json-patch+json" \
      -d '[{"op":"add","path":"/fields/System.State","value":"Closed"}]' > /dev/null
    echo "Closed #$WI"
    ;;
  reopen)
    WI=$1
    curl -s -X PATCH "$BASE/wit/workitems/$WI?api-version=7.1" \
      -u ":$PAT" \
      -H "Content-Type: application/json-patch+json" \
      -d '[{"op":"add","path":"/fields/System.State","value":"New"}]' > /dev/null
    echo "Reopened #$WI"
    ;;
  comments)
    WI=$1
    curl -s "$BASE/wit/workitems/$WI/comments?api-version=7.1" \
      -u ":$PAT" | python3 -c "
import sys,json
d=json.load(sys.stdin)
for c in d.get('comments',[]):
    author=c['parent'].get('fields',{}).get('System.AuthorizedDisplayName','?')
    print(f'[{author}] {c[\"text\"][:200]}')"
    ;;
  prs)
    curl -s "$BASE/git/repositories/${REPO_NAME}/pullrequests?searchCriteria.status=active&api-version=7.1" \
      -u ":$PAT" | python3 -c "
import sys,json
d=json.load(sys.stdin)
for pr in d.get('value',[]):
    print(f'PR #{pr[\"pullRequestId\"]}: {pr[\"title\"]} ({pr[\"sourceRefName\"]} -> {pr[\"targetRefName\"]})')"
    ;;
  poller)
    rm -f "$REPO_ROOT/.autoswe.lock"
    cd "$REPO_ROOT"
    bash poller.sh 2>&1 | tee -a logs/poller.log
    ;;
  wait_done)
    WI=$1
    TIMEOUT=${2:-600}
    PIDFILE="$REPO_ROOT/running/ado_${ORIG}_${PROJECT}_${REPO_NAME}_${WI}.pid"
    DONEFILE="$REPO_ROOT/running/ado_${ORIG}_${PROJECT}_${REPO_NAME}_${WI}.done"
    ELAPSED=0
    while [ $ELAPSED -lt $TIMEOUT ]; do
      if [ -f "$DONEFILE" ]; then
        echo "DONE after ${ELAPSED}s"
        exit 0
      fi
      if [ ! -f "$PIDFILE" ] && [ ! -f "$DONEFILE" ]; then
        if grep -q "issue-${WI}" "$REPO_ROOT/logs/autoswe.log" 2>/dev/null && \
           grep -q "issue-${WI}" "$REPO_ROOT/logs/poller.log" 2>/dev/null; then
          echo "PID gone after ${ELAPSED}s, checking status..."
          exit 0
        fi
      fi
      sleep 10
      ELAPSED=$((ELAPSED + 10))
    done
    echo "TIMEOUT after ${TIMEOUT}s"
    exit 1
    ;;
  queue_reset)
    echo '{}' > "$REPO_ROOT/data/queue.json"
    rm -f "$REPO_ROOT/running/"*
    echo "Queue reset"
    ;;
  help|*)
    echo "ADO test helper"
    echo ""
    echo "Usage: $0 [-r REPO_KEY] COMMAND [args...]"
    echo ""
    echo "Commands:"
    echo "  create <title> <desc>     Create work item"
    echo "  comment <wi> <text>       Post comment"
    echo "  tags <wi>                 Show tags"
    echo "  clear_tags <wi>           Clear tags"
    echo "  close <wi>                Close work item"
    echo "  reopen <wi>               Reopen work item"
    echo "  comments <wi>             List comments"
    echo "  prs                       List active PRs"
    echo "  poller                    Run poller"
    echo "  wait_done <wi> [timeout]  Wait for dispatch"
    echo "  queue_reset               Reset queue"
    ;;
esac
