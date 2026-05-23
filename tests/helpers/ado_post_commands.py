#!/usr/bin/env python3
"""Post slash commands / replies to Azure DevOps work items, optionally running the poller after each.

Usage:
    python3 tests/helpers/ado_post_commands.py [-r REPO_KEY] [--no-poller] [--dry-run]

Examples:
    # Post all default commands and run poller after each:
    python3 tests/helpers/ado_post_commands.py

    # Dry run — show what would be posted:
    python3 tests/helpers/ado_post_commands.py --dry-run

    # Post without running poller:
    python3 tests/helpers/ado_post_commands.py --no-poller

    # Custom list of work items:
    python3 tests/helpers/ado_post_commands.py --wis 92 94 95

The command list is embedded below. Edit COMMANDS to match your test scenario.
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from autoswe.core.config import load_config, load_repos_config  # noqa: E402
from autoswe.providers.factory import build_repo_cfg, get_tracker  # noqa: E402

DEFAULT_REPO = "natedorr/testProject/testProject"

# Edit this list for your test scenario
COMMANDS = [
    (92,  "/fix", "Basic /plan → post /fix"),
    (94,  "/fix", "Plan → Fix → /pr chain"),
    (95,  "/skip", "/skip after /plan"),
    (97,  "I'll keep it simple — just add a brief documentation improvement section to README.md covering the key points. Go ahead with whatever you think makes sense.", "Plan asks questions → reply"),
    (98,  "Proceed with the plan as outlined.", "Reply to WAITING → continue"),
    (99,  "/fix", "Plan → Reply with /fix"),
    (100, "Looks good, please go ahead with whatever you think is most useful.", "Plain text reply to plan_ready"),
    (104, "/abort", "/abort after plan"),
    (109, "/fix", "Close mid-flow detection"),
    (111, "/fix", "Plan → Fix → Second Fix"),
]

SUMMARY_FILE = REPO_ROOT / "tests" / "helpers" / "ado_post_summary.json"


def main():
    parser = argparse.ArgumentParser(description="Post commands to ADO work items")
    parser.add_argument("-r", "--repo", default=DEFAULT_REPO,
                        help="Repo key in repos.json (default: %(default)s)")
    parser.add_argument("--wis", nargs="+", type=int, default=None,
                        help="Override work item IDs (filters COMMANDS list)")
    parser.add_argument("--no-poller", action="store_true",
                        help="Skip running poller after each post")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be posted without posting")
    parser.add_argument("--delay", type=int, default=2,
                        help="Seconds between posts (default: 2)")
    args = parser.parse_args()

    # Filter COMMANDS if --wis specified
    if args.wis:
        commands = [(wi, cmd, desc) for wi, cmd, desc in COMMANDS if wi in args.wis]
    else:
        commands = COMMANDS

    cfg = load_config()
    repos_cfg = load_repos_config()

    if args.repo not in repos_cfg:
        print(f"Error: repo key '{args.repo}' not found in repos.json")
        sys.exit(1)

    entry = repos_cfg[args.repo]
    owner = entry.get("org", "natedorr")
    project = entry.get("project", "testProject")
    repo_name = entry.get("repo", "testProject")

    repo_cfg = build_repo_cfg(owner, project, repo_name, cfg, repos_cfg, provider="azure")
    tracker = get_tracker(repo_cfg)

    if args.dry_run:
        print("=== DRY RUN ===")
        for wi, cmd, desc in commands:
            cmd_preview = cmd[:80]
            print(f"  #{wi}: {desc}\n       → {cmd_preview}\n")
        print(f"Total: {len(commands)} posts")
        return

    summary = []
    for wi, cmd, desc in commands:
        print(f"\n{'=' * 80}")
        print(f"#{wi}: {desc}")
        print(f"Posting: {cmd[:100]}...")
        print(f"{'=' * 80}")

        # Post
        try:
            tracker.post_comment(repo_cfg, wi, cmd)
            print(f"✓ Posted on #{wi}")
        except Exception as e:
            print(f"✗ Post failed: {e}")
            summary.append({"wi": wi, "desc": desc, "posted": False, "error": str(e)})
            continue

        # Poller
        poller_info = {}
        if not args.no_poller:
            print("Running poller...")
            try:
                result = subprocess.run(
                    ["python3", "-u", str(REPO_ROOT / "autoswe.py"), "poller"],
                    cwd=str(REPO_ROOT),
                    capture_output=True, text=True, timeout=120,
                )
                stdout_tail = result.stdout[-600:] if result.stdout else ""
                print(f"Poller exit={result.returncode}")
                print(stdout_tail)
                poller_info = {"exit": result.returncode, "stdout_tail": stdout_tail}
            except subprocess.TimeoutExpired:
                print("✗ Poller timed out (120s)")
                poller_info = {"exit": "timeout"}
            except Exception as e:
                print(f"✗ Poller error: {e}")
                poller_info = {"exit": "error", "error": str(e)}

        summary.append({
            "wi": wi, "desc": desc, "command": cmd[:80],
            "posted": True, **poller_info,
        })

        time.sleep(args.delay)

    # Write summary
    SUMMARY_FILE.write_text(json.dumps(summary, indent=2))
    print(f"\n{'=' * 80}")
    print(f"Summary ({len(summary)}/{len(commands)} posted) → {SUMMARY_FILE}")
    for entry in summary:
        wi = entry.get("wi", "?")
        desc = entry.get("desc", "?")
        ok = "✓" if entry.get("posted") else "✗"
        print(f"  {ok} #{wi}: {desc}")


if __name__ == "__main__":
    main()
