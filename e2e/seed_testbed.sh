#!/usr/bin/env bash
# Seed the live E2E testbed repos. Run once per pass (or after --reset).
#
#   ./seed_testbed.sh <owner> [testbed-name] [hostile-name]
#
# Requires: gh CLI, authenticated as the account autoSWE steers with.
# Creates both repos, pushes the fixture tree, and adds the `develop` branch.
set -euo pipefail

OWNER="${1:?usage: seed_testbed.sh <owner> [testbed] [hostile]}"
TESTBED="${2:-autoswe-e2e-testbed}"
HOSTILE="${3:-autoswe-e2e-hostile}"
WORK="$(mktemp -d)"

seed_tree() {
  local dir="$1"
  mkdir -p "$dir"/{src,tests,docs,.github/workflows}

  cat > "$dir/README.md" <<'EOF'
# autoSWE live E2E testbed

Fixture repo for `e2e/PLAN.md`. Everything here exists to make
one state-machine path deterministic. Do not use it for anything else.
EOF

  cat > "$dir/pyproject.toml" <<'EOF'
[project]
name = "autoswe-e2e-testbed"
version = "0.0.1"

[tool.pytest.ini_options]
testpaths = ["tests"]
EOF

  # The test-gate lever: tests/test_canary.py goes red when flag.txt != green.
  printf 'green\n' > "$dir/flag.txt"
  # The sync-conflict lever: both sides edit line 1.
  printf 'shared: baseline\n' > "$dir/conflict.md"
  printf '# Notes\n' > "$dir/docs/notes.md"

  cat > "$dir/src/toolbox.py" <<'EOF'
"""Trivial helpers. E2E issues add one function at a time to this module."""


def double(n: int) -> int:
    return n * 2
EOF

  cat > "$dir/tests/test_toolbox.py" <<'EOF'
from src.toolbox import double


def test_double():
    assert double(3) == 6
EOF

  cat > "$dir/tests/test_canary.py" <<'EOF'
"""Post-fix test-gate lever: red whenever flag.txt does not read 'green'."""
from pathlib import Path


def test_flag_is_green():
    flag = Path(__file__).resolve().parent.parent / "flag.txt"
    assert flag.read_text().strip() == "green"
EOF

  # CI gate lever: the slow job only fires for pushes touching ci_slow/**,
  # so exactly one scenario (E2E-16) ever sees a `pending` commit status.
  cat > "$dir/.github/workflows/ci.yml" <<'EOF'
name: ci
on: [push]

jobs:
  fast:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install pytest && pytest -q

  slow-gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - id: changed
        run: |
          if git diff --name-only HEAD~1 HEAD | grep -q '^ci_slow/'; then
            echo "hit=true" >> "$GITHUB_OUTPUT"
          fi
      - if: steps.changed.outputs.hit == 'true'
        run: sleep 240
EOF
}

create_repo() {
  local name="$1"
  local dir="$WORK/$name"
  seed_tree "$dir"
  (
    cd "$dir"
    git init -q -b main
    git add -A
    git commit -qm "Seed live E2E testbed fixtures"
    gh repo create "$OWNER/$name" --private --source=. --push
    git checkout -qb develop
    git push -q -u origin develop
    git checkout -q main
  )
  echo "created $OWNER/$name"
}

create_repo "$TESTBED"
create_repo "$HOSTILE"

cat <<EOF

Both repos are up. Now add to config/repos.json:

  "$OWNER/$TESTBED": { "provider": "github", "base_branch": "main",
                       "auto_dispatch_new": false, "test_gate": true, "pat": "<pat>" },
  "$OWNER/$HOSTILE": { "provider": "github", "base_branch": "main",
                       "auto_dispatch_new": false, "agent_timeout": 20, "pat": "<pat>" }

then point scenarios.json's "repos" block at them.
EOF
