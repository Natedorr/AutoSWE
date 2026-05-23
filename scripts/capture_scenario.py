"""Capture a live issue as a scenario fixture skeleton.

Usage (GitHub):
    GITHUB_TOKEN=ghp_... python scripts/capture_scenario.py --provider github --repo owner/repo --issue 42 <scenario_name>

Usage (Azure):
    AZURE_DEVOPS_PAT=... python scripts/capture_scenario.py --provider azure --repo org/project/repo --issue 42 <scenario_name>

Fetches the live issue + labels + comments from the API, reads the
corresponding queue.json entry (if it exists), and writes:
  - tests/fixtures/scenarios/<provider>/<scenario_name>/state.json
  - tests/fixtures/scenarios/<provider>/<scenario_name>/expected.json (skeleton)
  - tests/fixtures/scenarios/<provider>/<scenario_name>/README.md

Sanitizes tokens, emails, and other sensitive fields.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

SCENARIOS_DIR = REPO_ROOT / "tests" / "fixtures" / "scenarios"

# Fields to strip from captured data
SENSITIVE_PATTERNS = [
    re.compile(r'gh[pousr]_[A-Za-z0-9_]+'),  # GitHub tokens
    re.compile(r'[^\s]+@[^\s]+\.[^\s]+'),     # emails
]

KEEP_USER_KEYS = {"login", "id", "type", "name"}
KEEP_LABEL_KEYS = {"id", "name", "color", "description"}
KEEP_ISSUE_KEYS = {
    "id", "number", "state", "title", "body", "labels", "assignees",
    "created_at", "updated_at", "closed_at", "author_association",
    "comments", "pull_request", "user",
}
KEEP_COMMENT_KEYS = {
    "id", "body", "user", "created_at", "updated_at",
    "author_association",
}

# Azure-specific
KEEP_ADO_FIELD_KEYS = {
    "System.Id", "System.Title", "System.Description",
    "System.State", "System.Tags", "System.CreatedDate",
    "System.ChangedDate", "System.AssignedTo",
}
KEEP_ADO_WI_KEYS = {"id", "rev", "fields"}
KEEP_ADO_COMMENT_KEYS = {"id", "text", "createdDate", "createdBy"}
KEEP_ADO_PROFILE_KEYS = {"displayName", "mailAddress", "id", "uniqueName"}


# ---------------------------------------------------------------------------
# Sanitization helpers

def sanitize_body(text: str) -> str:
    """Strip sensitive values from text bodies."""
    if not text:
        return text
    for pat in SENSITIVE_PATTERNS:
        text = pat.sub("[REDACTED]", text)
    return text


def sanitize_user(u: dict) -> dict:
    if not u:
        return u
    return {k: v for k, v in u.items() if k in KEEP_USER_KEYS}


def sanitize_label(lb: dict) -> dict:
    return {k: v for k, v in lb.items() if k in KEEP_LABEL_KEYS}


def sanitize_issue(issue: dict) -> dict:
    out = {k: v for k, v in issue.items() if k in KEEP_ISSUE_KEYS}
    out["body"] = sanitize_body(out.get("body", "") or "")
    if "user" in out:
        out["user"] = sanitize_user(out["user"])
    if "labels" in out:
        out["labels"] = [sanitize_label(lb) for lb in out["labels"]]
    if "assignees" in out:
        out["assignees"] = [sanitize_user(a) for a in out["assignees"]]
    return out


def sanitize_comment(c: dict) -> dict:
    out = {k: v for k, v in c.items() if k in KEEP_COMMENT_KEYS}
    out["body"] = sanitize_body(out.get("body", "") or "")
    if "user" in out:
        out["user"] = sanitize_user(out["user"])
    return out


def sanitize_ado_fields(fields: dict) -> dict:
    return {k: v for k, v in fields.items() if k in KEEP_ADO_FIELD_KEYS}


def sanitize_ado_wi(wi: dict) -> dict:
    out = {k: v for k, v in wi.items() if k in KEEP_ADO_WI_KEYS}
    if "fields" in out:
        out["fields"] = sanitize_ado_fields(out["fields"])
    return out


def sanitize_ado_comment(c: dict) -> dict:
    return {k: v for k, v in c.items() if k in KEEP_ADO_COMMENT_KEYS}


def sanitize_ado_profile(p: dict) -> dict:
    return {k: v for k, v in p.items() if k in KEEP_ADO_PROFILE_KEYS}


# ---------------------------------------------------------------------------
# Shared output writer

def _write_scenario(provider: str, scenario_name: str, state: dict, ident: str, extra_readme: str) -> None:
    """Write state.json, expected.json, README.md for a scenario."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    expected = {
        "label_after": "TODO: e.g. autoswe:plan_ready / autoswe:done / autoswe:waiting",
        "comments_posted": [
            # TODO: Fill in expected comment assertions
            # {"body_contains": ["## Plan", "<!-- autoswe-bot -->"], "count": 1},
        ],
        "queue_task_after": {
            # TODO: Fill in expected queue fields
            # "session_id": "s1",
            # "pending_command": None,
        },
        "claude_calls": [
            # TODO: Fill in expected Claude call assertions
            # {"permission_mode": "default", "resume": None},
        ],
        "git_calls": [
            # TODO: Fill in expected git operations
            # "create_worktree",
        ],
    }

    if provider == "github":
        test_file = "test_scenarios_github.py"
    else:
        test_file = "test_scenarios_azure.py"

    readme = (
        f"# {scenario_name}\n\n"
        f"Captured from `{ident}` on {now}.\n\n"
        f"{extra_readme}"
        f"## Setup\n"
        f"1. Fill in `claude_responses` in `state.json` with expected Claude SDK output.\n"
        f"2. Fill in `expected.json` with expected label, comments, queue state.\n"
        f"3. Run: `pytest -q -m scenario {test_file} -k {scenario_name}`\n"
    )

    scenario_dir = SCENARIOS_DIR / provider / scenario_name
    scenario_dir.mkdir(parents=True, exist_ok=True)

    state_path = scenario_dir / "state.json"
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    print(f"  wrote {state_path}")

    expected_path = scenario_dir / "expected.json"
    expected_path.write_text(json.dumps(expected, indent=2) + "\n", encoding="utf-8")
    print(f"  wrote {expected_path}")

    readme_path = scenario_dir / "README.md"
    readme_path.write_text(readme, encoding="utf-8")
    print(f"  wrote {readme_path}")

    print(f"\nDone. Fill in the TODOs in {expected_path} and the claude_responses in {state_path}.")
    print(f"Then run: pytest -q -m scenario {test_file} -k {scenario_name}")


# ---------------------------------------------------------------------------
# GitHub capture

def capture_github(token: str, repo_path: str, issue_number: int, scenario_name: str) -> None:
    from autoswe.core.config import load_config
    from autoswe.core.queue_store import QUEUE_FILE
    from autoswe.tracking.api import _fetch_comments, gh_get, gh_get_all

    cfg = load_config()
    if not token:
        token = cfg.get("GITHUB_TOKEN", "") or os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print("[ERROR] GITHUB_TOKEN not set. Export it or add it to config/autoswe.env.")
        sys.exit(1)

    owner, _, repo = repo_path.partition("/")
    if not repo:
        print(f"[ERROR] Invalid repo path: {repo_path!r}. Use 'owner/repo' format.")
        sys.exit(1)

    print(f"Capturing GitHub scenario from {owner}/{repo}#{issue_number} ...\n")

    # Fetch issue
    print(f"  GET /repos/{owner}/{repo}/issues/{issue_number}")
    issue_raw = gh_get(f"/repos/{owner}/{repo}/issues/{issue_number}", token)
    issue = sanitize_issue(issue_raw)

    labels = [lb["name"] for lb in issue.get("labels", [])]

    # Fetch comments
    print(f"  GET /repos/{owner}/{repo}/issues/{issue_number}/comments")
    comments_raw = _fetch_comments(owner, repo, issue_number, token)
    comments = [sanitize_comment(c) for c in comments_raw]

    # Fetch repo labels
    print(f"  GET /repos/{owner}/{repo}/labels")
    repo_labels_raw = gh_get_all(f"/repos/{owner}/{repo}/labels", token)
    repo_labels = [sanitize_label(lb) for lb in repo_labels_raw]

    # Read queue task if it exists
    queue_task = None
    slug = f"gh:{owner}_{repo}_{issue_number}"
    if QUEUE_FILE.exists():
        try:
            queue_data = json.loads(QUEUE_FILE.read_text())
            raw_task = queue_data.get(slug)
            if raw_task:
                queue_task = {k: v for k, v in raw_task.items()
                              if k not in ("_token", "comments")}
                if "body" in queue_task:
                    queue_task["body"] = sanitize_body(queue_task["body"])
        except (json.JSONDecodeError, OSError):
            pass

    # Fetch authenticated user
    print("  GET /user")
    auth_user = sanitize_user(gh_get("/user", token))

    state = {
        "provider": "github",
        "owner": owner,
        "repo": repo,
        "issue": issue,
        "labels": labels,
        "comments": comments,
        "repo_labels": repo_labels,
        "queue_task": queue_task,
        "authenticated_user": auth_user,
        "claude_responses": [],
    }

    extra = (
        f"**Current labels:** {labels or '(none)'}\n"
        f"**Issue title:** {issue.get('title', '(untitled)')}\n"
        f"**Comments:** {len(comments)}\n"
        f"**Queue task:** {'yes' if queue_task else 'no'}\n\n"
    )

    _write_scenario("github", scenario_name, state,
                     f"{owner}/{repo}#{issue_number}", extra)


# ---------------------------------------------------------------------------
# Azure capture

def capture_azure(pat: str, repo_path: str, issue_number: int, scenario_name: str) -> None:
    from autoswe.core.config import load_config
    from autoswe.core.queue_store import QUEUE_FILE
    from autoswe.providers.azure.api import _ado_api_version, ado_get

    cfg = load_config()
    if not pat:
        pat = cfg.get("AZURE_DEVOPS_PAT", "") or os.environ.get("AZURE_DEVOPS_PAT", "")
    if not pat:
        print("[ERROR] AZURE_DEVOPS_PAT not set. Export it or add it to config/autoswe.env.")
        sys.exit(1)

    parts = repo_path.rsplit("/", 2)
    if len(parts) == 3:
        org, project, repo = parts
    elif len(parts) == 2:
        org = cfg.get("AZURE_DEVOPS_ORG", "") or os.environ.get("AZURE_DEVOPS_ORG", "")
        project, repo = parts
    else:
        print(f"[ERROR] Invalid Azure repo path: {repo_path!r}. Use 'org/project/repo' or 'project/repo'.")
        sys.exit(1)

    base = f"https://dev.azure.com/{org}/{project}/_apis"

    print(f"Capturing Azure scenario from {org}/{project}/{repo}#{issue_number} ...\n")

    # Fetch work item
    print(f"  GET work item #{issue_number}")
    wi_url = _ado_api_version(f"{base}/wit/workitems/{issue_number}")
    wi_raw = ado_get(wi_url, pat)
    wi = sanitize_ado_wi(wi_raw)

    wi_fields = wi.get("fields", {})
    tags_raw = wi_fields.get("System.Tags", "")
    if tags_raw:
        tags = [t.strip() for t in tags_raw.split(";") if t.strip()]
    else:
        tags = []

    # Fetch comments
    print(f"  GET work item #{issue_number} comments")
    comments_url = f"{base}/wit/workitems/{issue_number}/comments?api-version=7.1-preview.4"
    comments_resp = ado_get(comments_url, pat)
    comments = [sanitize_ado_comment(c) for c in comments_resp.get("comments", [])]

    # Read queue task if it exists
    queue_task = None
    slug = f"ado:{org}_{project}/{repo}_{issue_number}"
    if QUEUE_FILE.exists():
        try:
            queue_data = json.loads(QUEUE_FILE.read_text())
            raw_task = queue_data.get(slug)
            if raw_task:
                queue_task = {k: v for k, v in raw_task.items()
                              if k not in ("_token", "comments")}
                if "body" in queue_task:
                    queue_task["body"] = sanitize_body(queue_task["body"])
        except (json.JSONDecodeError, OSError):
            pass

    # Fetch authenticated user (via work item's createdBy)
    created_by = wi_fields.get("System.CreatedBy", {})
    auth_user = sanitize_ado_profile(created_by) if created_by else {
        "uniqueName": "unknown@example.com", "id": "0",
    }

    state = {
        "provider": "azure",
        "org": org,
        "project": project,
        "repo": repo,
        "work_item": wi,
        "tags": tags,
        "comments": comments,
        "queue_task": queue_task,
        "authenticated_user": auth_user,
        "claude_responses": [],
    }

    extra = (
        f"**Current tags:** {tags or '(none)'}\n"
        f"**Work item title:** {wi_fields.get('System.Title', '(untitled)')}\n"
        f"**State:** {wi_fields.get('System.State', 'unknown')}\n"
        f"**Comments:** {len(comments)}\n"
        f"**Queue task:** {'yes' if queue_task else 'no'}\n\n"
    )

    _write_scenario("azure", scenario_name, state,
                     f"{org}/{project}/{repo}#{issue_number}", extra)


# ---------------------------------------------------------------------------
# Main

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Capture a live issue as a scenario fixture skeleton."
    )
    parser.add_argument("scenario_name", help="Name for the scenario directory")
    parser.add_argument("--provider", required=True, choices=["github", "azure"])
    parser.add_argument("--repo", required=True,
                        help="owner/repo for GitHub, or org/project/repo for Azure")
    parser.add_argument("--issue", type=int, required=True,
                        help="Issue/work-item number to capture")
    args = parser.parse_args()

    # Set up autoswe dir for config loading
    os.environ.setdefault("AUTOSWE_DIR", str(REPO_ROOT / ".capture_tmp"))
    Path(os.environ["AUTOSWE_DIR"] + "/logs").mkdir(parents=True, exist_ok=True)

    from autoswe.core.config import load_config
    cfg = load_config()

    if args.provider == "github":
        token = cfg.get("GITHUB_TOKEN", "") or os.environ.get("GITHUB_TOKEN", "")
        capture_github(token, args.repo, args.issue, args.scenario_name)
    else:
        pat = cfg.get("AZURE_DEVOPS_PAT", "") or os.environ.get("AZURE_DEVOPS_PAT", "")
        capture_azure(pat, args.repo, args.issue, args.scenario_name)


if __name__ == "__main__":
    main()
