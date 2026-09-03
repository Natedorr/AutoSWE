#!/usr/bin/env python3
"""End-to-end test of the full autoSWE Azure DevOps pipeline.

Creates simple work items and walks through every lifecycle stage:
  /plan → (questions → reply) → /fix → /review → refix → /pr

After each step the poller runs and this script verifies the result by
reading the work item comments and tags.

Usage:
    cd ~/github/AutoSWE && python3 tests/helpers/ado_e2e_test.py
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from autoswe.core.config import load_config, load_repos_config
from autoswe.providers.factory import build_repo_cfg, get_tracker


def get_tracker_instance():
    cfg = load_config()
    repos_cfg = load_repos_config()
    repo_cfg = build_repo_cfg(
        "Natedorr/testProject", "testProject", cfg, repos_cfg, provider="azure"
    )
    return get_tracker(repo_cfg), repo_cfg


def run_poller(timeout=300):
    result = subprocess.run(
        ["python3", "-u", str(REPO_ROOT / "autoswe.py"), "poller"],
        cwd=str(REPO_ROOT),
        capture_output=True, text=True, timeout=timeout,
    )
    return result.stdout, result.stderr, result.returncode


def wait_for_status(tracker, repo_cfg, wi_id, expected_status,
                    max_wait=300, poll_interval=10):
    start = time.time()
    last_status = ""
    while time.time() - start < max_wait:
        issue = tracker.fetch_issue(repo_cfg, wi_id)
        current = tracker.get_status(issue) or ""
        if current != last_status:
            print(f"  [status] {last_status} → {current}")
            last_status = current
        if current == expected_status:
            return True, current
        if current and expected_status in current:
            return True, current
        time.sleep(poll_interval)
    return False, current


def get_last_bot_comment(tracker, repo_cfg, wi_id):
    comments = tracker.fetch_comments(repo_cfg, wi_id)
    bot_comments = [c for c in comments if c.author_login == "BOT"]
    return bot_comments[-1] if bot_comments else None


def print_bot_summary(bot):
    if not bot:
        print("  [no bot comment]")
        return
    body = bot.body
    has_plan = "<AUTOSWE_PLAN>" in body
    has_questions = "<AUTOSWE_QUESTIONS>" in body
    has_commit = "commit" in body.lower() or "sha=" in body.lower()
    has_review = "<AUTOSWE_REVIEW>" in body
    has_pr = "pullrequest" in body.lower() or "PR #" in body
    has_error = "<AUTOSWE_ERROR>" in body

    markers = []
    if has_plan: markers.append("PLAN")
    if has_questions: markers.append("QUESTIONS")
    if has_commit: markers.append("COMMIT")
    if has_review: markers.append("REVIEW")
    if has_pr: markers.append("PR")
    if has_error: markers.append("ERROR")

    print(f"  Markers: {', '.join(markers) if markers else 'none'}")
    for line in body.strip().split('\n')[:8]:
        print(f"    {line[:120]}")


# ─── Test scenarios ─────────────────────────────────────────────────

SCENARIOS = [
    {
        "title": "🧪 E2E: Add greet(name) to hello.py",
        "body": "Create a Python file `hello.py` in the repo root with one function:\n```python\ndef greet(name: str) -> str:\n    return f\"Hello, {name}!\"\n```\nNothing else.",
        "steps": [
            ("plan", "/plan", "planned", "Planning phase"),
        ],
    },
    {
        "title": "🧪 E2E: Create math_ops.py with add/subtract",
        "body": "Create `math_ops.py` in the repo root:\n```python\ndef add(a, b):\n    return a + b\n\ndef subtract(a, b):\n    return a - b\n```\nJust these two functions.",
        "steps": [
            ("plan", "/plan", "planned", "Planning"),
            ("fix", "/fix", "fixed", "Fix"),
        ],
    },
    {
        "title": "🧪 E2E: Create clamp.py utility",
        "body": "Create `clamp.py` with:\n```python\ndef clamp(value, lo, hi):\n    return max(lo, min(value, hi))\n```\nOne function only.",
        "steps": [
            ("plan", "/plan", "planned", "Planning"),
            ("fix", "/fix", "fixed", "Fix"),
            ("review", "/review", "reviewed", "Review"),
            ("pr", "/pr", "shipped", "Create PR"),
        ],
    },
]


# ─── Main ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="E2E autoSWE ADO pipeline test")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-poller", action="store_true")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--issue-ids", nargs="+", type=int)
    args = parser.parse_args()

    tracker, repo_cfg = get_tracker_instance()

    if args.dry_run:
        print("=== DRY RUN ===\n")
        for i, s in enumerate(SCENARIOS[args.start:]):
            print(f"Scenario {i}: {s['title']}")
            for name, cmd, expected, _ in s["steps"]:
                print(f"  {name}: {cmd} → expect '{expected}'")
            print()
        return

    # Create work items
    wi_ids = args.issue_ids or []
    if not wi_ids:
        for i, scenario in enumerate(SCENARIOS[args.start:]):
            wi_id = tracker.create_issue(repo_cfg, scenario["title"], scenario["body"])
            wi_ids.append(wi_id)
            print(f"✓ Created WI #{wi_id}: {scenario['title']}")
            time.sleep(1)

    # Run tests
    results = []
    for scenario, wi_id in zip(SCENARIOS[args.start:], wi_ids):
        print(f"\n\n{'#' * 80}")
        print(f"# WI #{wi_id}: {scenario['title']}")
        print(f"{'#' * 80}")

        test_result = {"wi": wi_id, "title": scenario["title"], "steps": {}}

        for step_num, (step_name, command, expected, description) in enumerate(scenario["steps"]):
            print(f"\n{'='*80}")
            print(f"STEP {step_num+1}: {step_name.upper()} — {description}")
            print(f"{'='*80}")

            # Post command
            try:
                cid = tracker.post_comment(repo_cfg, wi_id, command)
                print(f"✓ Posted: {command[:60]}... (id={cid})")
            except Exception as e:
                print(f"✗ POST FAILED: {e}")
                test_result["steps"][step_name] = {"ok": False, "error": str(e)}
                continue

            if args.no_poller:
                test_result["steps"][step_name] = {"ok": True, "note": "no-poller"}
                time.sleep(3)
                continue

            # Run poller
            stdout, stderr, rc = run_poller()
            print(f"Poller rc={rc}")
            if args.debug:
                print(f"\n[stdout]\n{stdout}")
            else:
                for line in stdout.strip().split('\n')[-15:]:
                    if line.strip():
                        print(f"  {line}")

            # Wait for expected status
            print(f"\nWaiting for '{expected}'...")
            ok, final = wait_for_status(tracker, repo_cfg, wi_id, expected)
            print(f"Result: {'✓' if ok else '✗'} status={final}")

            test_result["steps"][step_name] = {
                "ok": ok, "status": final, "error": "timeout" if not ok else None
            }

            # Bot comment analysis
            bot = get_last_bot_comment(tracker, repo_cfg, wi_id)
            print(f"\n[Bot comment]")
            print_bot_summary(bot)

            # Step-specific checks
            if step_name == "plan" and ok and bot:
                if "<AUTOSWE_PLAN>" in bot.body:
                    print("  ✓ Contains AUTOSWE_PLAN marker")
                if "<AUTOSWE_QUESTIONS>" in bot.body:
                    print("  ✓ Agent asked clarifying questions")

            if step_name == "fix" and ok and bot:
                if "commit" in bot.body.lower():
                    print("  ✓ Fix committed")
                if "<AUTOSWE_ERROR>" in bot.body:
                    print("  ⚠ Fix had errors")

            if step_name == "review" and ok and bot:
                if "<AUTOSWE_REVIEW>" in bot.body:
                    print("  ✓ Contains AUTOSWE_REVIEW marker")
                if "needs changes" in bot.body.lower():
                    print("  ℹ Review found issues")

            if step_name == "pr" and ok and bot:
                if "pullrequest" in bot.body.lower():
                    print("  ✓ PR created")

            time.sleep(3)

        results.append(test_result)

    # Summary
    print(f"\n\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    all_ok = True
    for r in results:
        print(f"\nWI #{r['wi']}: {r['title']}")
        for step, info in r["steps"].items():
            ok = info.get("ok", False)
            icon = "✓" if ok else "✗"
            detail = info.get("status", info.get("error", info.get("note", "")))
            print(f"  {icon} {step}: {detail}")
            if not ok:
                all_ok = False

    out = REPO_ROOT / "tests" / "helpers" / "ado_e2e_results.json"
    out.write_text(json.dumps(results, indent=2))
    print(f"\nResults → {out}")

    print("\n" + ("ALL PASSED ✓" if all_ok else "SOME STEPS FAILED ✗"))
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
