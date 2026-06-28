#!/usr/bin/env python3
"""azure_test_issue.py — Create a test work item on Azure DevOps and post comments.

Usage:
    python scripts/azure_test_issue.py create          # Create test issue
    python scripts/azure_test_issue.py post <id> <text>   # Post comment on issue
    python scripts/azure_test_issue.py status <id>      # Show issue + comments
    python scripts/azure_test_issue.py list             # List recent issues
"""
import sys
from pathlib import Path

# Ensure repo root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from autoswe.core.config import load_config, load_repos_config
from autoswe.providers.factory import build_repo_cfg, get_tracker

REPO_KEY = "natedorr/testProject/testProject"


def get_tracker_and_cfg():
    cfg = load_config()
    repos_cfg = load_repos_config()
    # For Azure 3-part key: owner=org, repo=project/repo
    parts = REPO_KEY.split("/")
    owner = parts[0]  # org
    repo = "/".join(parts[1:])  # project/repo
    repo_cfg = build_repo_cfg(owner, repo, cfg, repos_cfg)
    tracker = get_tracker(repo_cfg)
    return tracker, repo_cfg


def cmd_create():
    tracker, repo_cfg = get_tracker_and_cfg()
    title = "[autoSWE Test] Sample bug — add greeting function"
    body = (
        "## Description\n"
        "This is a test issue for the autoSWE pipeline.\n\n"
        "## Task\n"
        "Create a new file `greeting.py` in the root of the project that contains:\n"
        "1. A function `greet(name: str) -> str` that returns `\"Hello, <name>!\"`\n"
        "2. A `__main__` block that calls `greet(\"World\")` and prints the result\n\n"
        "## Acceptance Criteria\n"
        "- The file exists and is importable\n"
        "- Running `python greeting.py` prints `Hello, World!`\n"
        "- Type hints are included\n"
    )
    issue_id = tracker.create_issue(repo_cfg, title, body)
    print(f"Created issue #{issue_id}: {title}")
    return issue_id


def cmd_post(issue_id: int, text: str):
    """Post arbitrary text as a comment on an issue."""
    tracker, repo_cfg = get_tracker_and_cfg()
    cid = tracker.post_comment(repo_cfg, issue_id, text)
    print(f"Posted comment on issue #{issue_id} (comment_id={cid}): {text[:60]}...")


def cmd_status(issue_id: int):
    tracker, repo_cfg = get_tracker_and_cfg()
    issue = tracker.fetch_issue(repo_cfg, issue_id)
    print(f"Issue #{issue.number}: {issue.title}")
    print(f"  State: {issue.state}")
    print(f"  Status (autoswe): {issue.status or 'none'}")
    print(f"  Labels: {issue.labels}")
    comments = tracker.fetch_comments(repo_cfg, issue_id)
    print(f"  Comments ({len(comments)}):")
    for c in comments:
        bot = "[bot]" if c.is_bot else "[user]"
        preview = c.body[:80].replace("\n", " ")
        print(f"    {bot} [{c.id}] {c.author_login}: {preview}")


def cmd_list():
    tracker, repo_cfg = get_tracker_and_cfg()
    issues = tracker.list_open_issues(repo_cfg)
    print(f"Open issues ({len(issues)}):")
    for iss in sorted(issues, key=lambda i: i.number, reverse=True)[:10]:
        status = iss.status or "none"
        print(f"  #{iss.number} [{status}] {iss.title}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    action = sys.argv[1]
    if action == "create":
        cmd_create()
    elif action == "post" and len(sys.argv) >= 4:
        cmd_post(int(sys.argv[2]), " ".join(sys.argv[3:]))
    elif action == "status" and len(sys.argv) >= 3:
        cmd_status(int(sys.argv[2]))
    elif action == "list":
        cmd_list()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
