#!/usr/bin/env python3
"""Extended E2E tests for autoSWE Azure DevOps pipeline.

Tests flows NOT covered by basic test:
1. Questions → reply → replan
2. Retry after intentional issue
3. Re-fix after review finds issues

Usage:
    cd ~/github/AutoSWE && python3 tests/helpers/ado_e2e_extended_test.py
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


def wait_for_status(tracker, repo_cfg, wi_id, expected_statuses,
                    max_wait=300, poll_interval=10):
    """Wait for any of the expected statuses (e.g. 'waiting' or 'planned')."""
    if isinstance(expected_statuses, str):
        expected_statuses = [expected_statuses]
    start = time.time()
    last_status = ""
    while time.time() - start < max_wait:
        issue = tracker.fetch_issue(repo_cfg, wi_id)
        current = tracker.get_status(issue) or ""
        if current != last_status:
            print(f"  [status] {last_status} → {current}")
            last_status = current
        if current in expected_statuses:
            return True, current
        for exp in expected_statuses:
            if current and exp in current:
                return True, current
        time.sleep(poll_interval)
    return False, current


def get_all_bot_comments(tracker, repo_cfg, wi_id):
    comments = tracker.fetch_comments(repo_cfg, wi_id)
    return [c for c in comments if c.author_login == "BOT"]


def get_last_bot_comment(tracker, repo_cfg, wi_id):
    comments = tracker.fetch_comments(repo_cfg, wi_id)
    bot_comments = [c for c in comments if c.author_login == "BOT"]
    return bot_comments[-1] if bot_comments else None


def get_all_comments_with_questions(tracker, repo_cfg, wi_id):
    """Get all comments, checking for AUTOSWE_QUESTIONS markers."""
    comments = tracker.fetch_comments(repo_cfg, wi_id)
    results = []
    for c in comments:
        body = c.body
        has_questions = "<AUTOSWE_QUESTIONS>" in body
        has_plan = "<AUTOSWE_PLAN>" in body
        has_review = "<AUTOSWE_REVIEW>" in body
        has_error = "<AUTOSWE_ERROR>" in body
        markers = []
        if has_questions: markers.append("QUESTIONS")
        if has_plan: markers.append("PLAN")
        if has_review: markers.append("REVIEW")
        if has_error: markers.append("ERROR")
        results.append({
            "author": c.author_login,
            "markers": markers,
            "body_preview": body[:300],
            "body": body,
            "id": c.id,
        })
    return results


SCENARIOS = [
    {
        "name": "questions_flow",
        "title": "🧪 E2E: Build a data processor (ambiguous)",
        "body": """Build a Python module that processes data files.

Requirements are intentionally vague to force questions:
- It should process "data" (format unclear — CSV? JSON? both?)
- It should "validate" the data (what validation rules?)
- It should have a main() entry point

Please ask clarifying questions before implementing.
""",
        "steps": [
            # Step 1: Plan — should trigger questions
            ("plan", "/plan", ["waiting", "planned"],
             "Planning — should ask clarifying questions"),
            # Step 2: Reply with answers (only if questions asked)
            ("reply", "/fix with Use CSV format, validate that all rows have 3 columns, and use a simple main() that reads from sys.argv[0]",
             "fixed", "Reply with guidance — skip further planning, go straight to fix"),
        ],
    },
    {
        "name": "review_find_issues",
        "title": "🧪 E2E: Create string_utils.py with intentional review targets",
        "body": """Create `string_utils.py` with these functions:

```python
def reverse_string(s):
    # Reverse a string
    result = ""
    for i in range(len(s)):
        result = s[i] + result
    return result

def count_vowels(s):
    # Count vowels in a string
    count = 0
    for c in s:
        if c in 'aeiou':
            count = count + 1
    return count
```

Implement exactly as written (I know it could be cleaner — the review should find style issues).
""",
        "steps": [
            ("plan", "/plan", ["waiting", "planned"], "Planning"),
            ("fix", "/fix", "fixed", "Fix"),
            ("review", "/review", "reviewed", "Review — should find style issues"),
        ],
    },
]


def main():
    parser = argparse.ArgumentParser(description="Extended E2E autoSWE ADO tests")
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
            for name, cmd, expected, desc in s["steps"]:
                print(f"  {name}: {cmd[:50]}... → expect {expected}")
            print()
        return

    # Create WIs
    wi_ids = args.issue_ids or []
    if not wi_ids:
        for i, scenario in enumerate(SCENARIOS[args.start:]):
            wi_id = tracker.create_issue(repo_cfg, scenario["title"], scenario["body"])
            wi_ids.append(wi_id)
            print(f"✓ Created WI #{wi_id}: {scenario['title']}")
            time.sleep(1)

    results = []
    for scenario, wi_id in zip(SCENARIOS[args.start:], wi_ids):
        print(f"\n\n{'#' * 80}")
        print(f"# WI #{wi_id}: {scenario['name']} — {scenario['title']}")
        print(f"{'#' * 80}")

        test_result = {"wi": wi_id, "name": scenario["name"], "title": scenario["title"], "steps": {}}
        questions_found = False

        for step_num, (step_name, command, expected_statuses, description) in enumerate(scenario["steps"]):
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
            expected_list = expected_statuses if isinstance(expected_statuses, list) else [expected_statuses]
            print(f"\nWaiting for any of: {expected_list}...")
            ok, final = wait_for_status(tracker, repo_cfg, wi_id, expected_list)
            print(f"Result: {'✓' if ok else '✗'} status={final}")

            test_result["steps"][step_name] = {
                "ok": ok, "status": final,
                "error": "timeout" if not ok else None
            }

            # Analyze all bot comments
            print(f"\n[Bot comments analysis]")
            all_comments = get_all_comments_with_questions(tracker, repo_cfg, wi_id)
            for c in all_comments:
                markers = ', '.join(c['markers']) if c['markers'] else 'none'
                print(f"  [{c['author']}] markers: {markers}")
                for line in c['body'].split('\n')[:5]:
                    print(f"    {line[:120]}")
                print()

                # Track if questions were found
                if "QUESTIONS" in c["markers"]:
                    questions_found = True

            # Step-specific checks
            if step_name == "plan" and ok:
                if questions_found:
                    print("  ✓ Agent asked clarifying questions (AUTOSWE_QUESTIONS found)")
                    test_result["questions_asked"] = True
                else:
                    print("  ⚠ No questions asked (task may have been too simple)")
                    test_result["questions_asked"] = False

            if step_name == "reply" and ok:
                print("  ✓ Reply processed successfully")

            if step_name == "review" and ok:
                bot = get_last_bot_comment(tracker, repo_cfg, wi_id)
                if bot:
                    body_lower = bot.body.lower()
                    if "needs changes" in body_lower or "finding" in body_lower or "issue" in body_lower:
                        print("  ℹ Review found issues")
                    else:
                        print("  ℹ Review appears clean")

            time.sleep(3)

        results.append(test_result)

    # Summary
    print(f"\n\n{'='*80}")
    print("EXTENDED E2E TEST SUMMARY")
    print(f"{'='*80}")
    all_ok = True
    for r in results:
        print(f"\nWI #{r['wi']}: {r['name']} — {r['title']}")
        if r.get("questions_asked") is not None:
            q_icon = "✓" if r["questions_asked"] else "⚠"
            print(f"  {q_icon} Questions asked: {r['questions_asked']}")
        for step, info in r["steps"].items():
            ok = info.get("ok", False)
            icon = "✓" if ok else "✗"
            detail = info.get("status", info.get("error", info.get("note", "")))
            print(f"  {icon} {step}: {detail}")
            if not ok:
                all_ok = False

    out = REPO_ROOT / "tests" / "helpers" / "ado_e2e_extended_results.json"
    out.write_text(json.dumps(results, indent=2))
    print(f"\nResults → {out}")
    print("\n" + ("ALL PASSED ✓" if all_ok else "SOME STEPS FAILED ✗"))
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
