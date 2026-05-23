#!/usr/bin/env python3
"""Review and advance Azure DevOps work items — fetch state, decide action, post, poll.

This is the "smart" version that inspects each work item's current state
and comments before deciding what to post, rather than blindly posting
pre-scripted commands.

Usage:
    python3 tests/helpers/ado_advance_tasks.py [-r REPO_KEY] [--dry-run] [WI ...]

Examples:
    # Review and advance all default test WIs:
    python3 tests/helpers/ado_advance_tasks.py

    # Dry run — inspect without posting:
    python3 tests/helpers/ado_advance_tasks.py --dry-run

    # Only specific WIs:
    python3 tests/helpers/ado_advance_tasks.py 92 94 104
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from autoswe.core.config import load_config, load_repos_config  # noqa: E402
from autoswe.providers.factory import build_repo_cfg, get_tracker  # noqa: E402

DEFAULT_REPO = "natedorr/testProject/testProject"
DEFAULT_WIS = [92, 94, 95, 97, 98, 99, 100, 104, 109, 111]

# Hints for what each WI is testing — guides the decision logic
WI_HINTS = {
    92:  "fix",      # Basic /plan → already has plan, post /fix
    94:  "fix",      # Plan → Fix → /pr chain
    95:  "skip",     # /skip after /plan
    97:  "reply",    # Plan asks questions → reply
    98:  "reply",    # WAITING → reply to continue
    99:  "fix",      # Plan → reply with /fix
    100: "reply",    # Plain text reply
    104: "abort",    # /abort after plan
    109: "fix",      # Close mid-flow
    111: "fix",      # Second fix
}


def decide_action(wi, hint, comments):
    """Decide what to post based on hint and comment history."""
    if hint == "fix":
        return "/fix"
    elif hint == "skip":
        return "/skip"
    elif hint == "abort":
        return "/abort"
    elif hint == "reply":
        # Check if bot asked questions
        for c in reversed(comments):
            if "AUTOSWE_QUESTIONS" in c.body or "Question" in c.body:
                return "Proceed with the plan as outlined."
        return "Please proceed with the implementation."
    return "/fix"


def main():
    parser = argparse.ArgumentParser(description="Review and advance ADO work items")
    parser.add_argument("wis", nargs="*", type=int, default=DEFAULT_WIS)
    parser.add_argument("-r", "--repo", default=DEFAULT_REPO)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-poller", action="store_true")
    parser.add_argument("--delay", type=int, default=3)
    args = parser.parse_args()

    cfg = load_config()
    repos_cfg = load_repos_config()

    if args.repo not in repos_cfg:
        print(f"Error: repo key '{args.repo}' not in repos.json")
        sys.exit(1)

    entry = repos_cfg[args.repo]
    owner = entry.get("org", "natedorr")
    project = entry.get("project", "testProject")
    repo_name = entry.get("repo", "testProject")

    repo_cfg = build_repo_cfg(owner, project, repo_name, cfg, repos_cfg, provider="azure")
    tracker = get_tracker(repo_cfg)

    print(f"Azure: org={tracker._org}, project={tracker._project}")
    print("=" * 80)

    for wi in args.wis:
        hint = WI_HINTS.get(wi, "fix")
        print(f"\n{'=' * 80}")
        print(f"#{wi} (hint: {hint})")
        print(f"{'=' * 80}")

        # Fetch
        try:
            issue = tracker.fetch_issue(repo_cfg, wi)
            print(f"  Title:  {issue.title}")
            print(f"  Status: {issue.status}")
            print(f"  Tags:   {getattr(issue, 'tags', getattr(issue, 'labels', []))}")
        except Exception as e:
            print(f"  Fetch error: {e}")
            continue

        try:
            comments = tracker.fetch_comments(repo_cfg, wi)
            print(f"  Comments: {len(comments)}")
        except Exception as e:
            print(f"  Comment fetch error: {e}")
            comments = []

        # Decide
        action = decide_action(wi, hint, comments)
        print(f"  → Action: {action[:80]}")

        if args.dry_run:
            print("  (dry run — not posting)")
            continue

        # Post
        try:
            tracker.post_comment(repo_cfg, wi, action)
            print("  ✓ Posted")
        except Exception as e:
            print(f"  ✗ Post error: {e}")
            continue

        # Poller
        if not args.no_poller:
            print("  Running poller...")
            try:
                result = subprocess.run(
                    ["python3", "-u", str(REPO_ROOT / "autoswe.py"), "poller"],
                    cwd=str(REPO_ROOT),
                    capture_output=True, text=True, timeout=120,
                )
                print(f"  Poller exit={result.returncode}")
                print(f"  {result.stdout[-400:]}")
            except subprocess.TimeoutExpired:
                print("  Poller timeout (120s)")
            except Exception as e:
                print(f"  Poller error: {e}")

        time.sleep(args.delay)

    print(f"\n{'=' * 80}")
    print("Done")


if __name__ == "__main__":
    main()
