#!/usr/bin/env python3
"""Fetch details and comments for Azure DevOps work items.

Usage:
    python3 tests/helpers/ado_fetch_details.py [-r REPO_KEY] [WI1 WI2 ...]

Examples:
    python3 tests/helpers/ado_fetch_details.py 92 94 95
    python3 tests/helpers/ado_fetch_details.py -r natedorr/testProject/testProject 92 94
"""

import argparse
import json
import sys
from pathlib import Path

# Resolve repo root relative to this script
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from autoswe.core.config import load_config, load_repos_config
from autoswe.providers.factory import build_repo_cfg, get_tracker

DEFAULT_REPO = "natedorr/testProject/testProject"
DEFAULT_WIS = [92, 94, 95, 97, 98, 99, 100, 104, 109, 111]


def main():
    parser = argparse.ArgumentParser(description="Fetch ADO work item details")
    parser.add_argument("wis", nargs="*", type=int, default=DEFAULT_WIS,
                        help="Work item IDs to inspect (default: all test WIs)")
    parser.add_argument("-r", "--repo", default=DEFAULT_REPO,
                        help="Repo key in repos.json (default: %(default)s)")
    parser.add_argument("--json", dest="as_json", action="store_true",
                        help="Output as JSON instead of human-readable")
    args = parser.parse_args()

    cfg = load_config()
    repos_cfg = load_repos_config()

    if args.repo not in repos_cfg:
        print(f"Error: repo key '{args.repo}' not found in repos.json")
        print(f"Available keys: {', '.join(repos_cfg.keys())}")
        sys.exit(1)

    entry = repos_cfg[args.repo]
    owner = entry.get("org", "natedorr")
    project = entry.get("project", "testProject")
    repo_name = entry.get("repo", "testProject")

    repo_cfg = build_repo_cfg(owner, project, repo_name, cfg, repos_cfg, provider="azure")
    tracker = get_tracker(repo_cfg)

    print(f"Azure config: org={tracker._org}, project={tracker._project}")
    print(f"Repo key: {args.repo}")
    print("=" * 80)

    results = {}
    for iid in args.wis:
        print(f"\n{'=' * 80}")
        print(f"WORK ITEM #{iid}")
        print(f"{'=' * 80}")

        try:
            issue = tracker.fetch_issue(repo_cfg, iid)
            print(f"Title:  {issue.title}")
            print(f"Status: {issue.status}")
            print(f"Tags:   {getattr(issue, 'tags', getattr(issue, 'labels', []))}")
            print(f"State:  {issue.state}")
            body_preview = issue.body[:500] if issue.body else "(empty)"
            print(f"Body:   {body_preview}")

            comments = tracker.fetch_comments(repo_cfg, iid)
            print(f"\nComments ({len(comments)}):")
            for c in comments:
                marker = " [BOT]" if "<!-- autoswe-bot -->" in c.body else ""
                body_short = c.body[:400].replace("\n", " | ")
                print(f"  [{c.created_at}] {getattr(c, 'author_login', getattr(c, 'author', '?'))}{marker}: {body_short}")

            results[iid] = {
                "title": issue.title,
                "status": issue.status,
                "state": issue.state,
                "tags": getattr(issue, "tags", getattr(issue, "labels", [])),
                "comment_count": len(comments),
            }
        except Exception as e:
            print(f"Error: {e}")
            results[iid] = {"error": str(e)}

    print(f"\n{'=' * 80}")
    print("SUMMARY")
    print(f"{'=' * 80}")
    if args.as_json:
        print(json.dumps(results, indent=2))
    else:
        for iid, info in results.items():
            status = info.get("status", "ERROR")
            title = info.get("title", "?")
            print(f"  #{iid}: [{status}] {title}")


if __name__ == "__main__":
    main()
