"""Capture real GitHub API responses as offline test fixtures.

Run manually with a PAT — never called by CI.

    GITHUB_TOKEN=ghp_... python scripts/capture_github_fixtures.py

Fetches data from natedorr/autoswe (open issues, closed issues,
comments, labels, current user, owned repos) and writes sanitized JSON
to tests/fixtures/github/. Idempotent — re-running overwrites files.
"""

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "github"
FIXTURE_DIR.mkdir(parents=True, exist_ok=True)

OWNER = "natedorr"
REPO = "autoswe"

KEEP_USER_KEYS = {"login", "id", "type", "name", "html_url"}
KEEP_LABEL_KEYS = {"id", "name", "color", "description", "default"}
KEEP_ISSUE_KEYS = {
    "id", "number", "state", "title", "body", "labels", "assignees",
    "created_at", "updated_at", "closed_at", "html_url", "author_association",
    "comments",
}
KEEP_COMMENT_KEYS = {
    "id", "body", "user", "created_at", "updated_at",
    "author_association", "html_url",
}
KEEP_REPO_KEYS = {
    "id", "name", "full_name", "private", "owner",
    "html_url", "default_branch",
}


def sanitize_user(u: dict) -> dict:
    if not u:
        return u
    return {k: v for k, v in u.items() if k in KEEP_USER_KEYS}


def sanitize_label(lb: dict) -> dict:
    return {k: v for k, v in lb.items() if k in KEEP_LABEL_KEYS}


def sanitize_issue(issue: dict) -> dict:
    out = {k: v for k, v in issue.items() if k in KEEP_ISSUE_KEYS}
    if "user" in issue:
        out["user"] = sanitize_user(issue["user"])
    if "labels" in issue:
        out["labels"] = [sanitize_label(lb) for lb in issue["labels"]]
    if "assignees" in issue:
        out["assignees"] = [sanitize_user(a) for a in issue["assignees"]]
    return out


def sanitize_comment(c: dict) -> dict:
    out = {k: v for k, v in c.items() if k in KEEP_COMMENT_KEYS}
    if "user" in c:
        out["user"] = sanitize_user(c["user"])
    return out


def sanitize_repo(r: dict) -> dict:
    out = {k: v for k, v in r.items() if k in KEEP_REPO_KEYS}
    if "owner" in r:
        out["owner"] = sanitize_user(r["owner"])
    return out


def write_fixture(name: str, data) -> None:
    path = FIXTURE_DIR / name
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"  wrote {path.name}  ({len(json.dumps(data))} bytes)")


def main() -> None:
    os.environ.setdefault("AUTOSWE_DIR", str(REPO_ROOT / ".capture_tmp"))
    Path(os.environ["AUTOSWE_DIR"] + "/logs").mkdir(parents=True, exist_ok=True)

    from autoswe.core.config import load_config
    from autoswe.tracking.api import _fetch_comments, gh_get, gh_get_all

    cfg = load_config()
    token = cfg.get("GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print("[ERROR] GITHUB_TOKEN not set. Export it or add it to config/autoswe.env.")
        sys.exit(1)

    print(f"Capturing fixtures from {OWNER}/{REPO} ...\n")

    print("  /user")
    user = gh_get("/user", token)
    write_fixture("user_authenticated.json", sanitize_user(user))

    print("  /user/repos")
    repos = gh_get_all("/user/repos?type=owner", token)
    write_fixture("user_repos.json", [sanitize_repo(r) for r in repos[:5]])

    print(f"  /repos/{OWNER}/{REPO}/labels")
    repo_labels = gh_get_all(f"/repos/{OWNER}/{REPO}/labels", token)
    write_fixture("labels_list_repo.json", [sanitize_label(lb) for lb in repo_labels])

    open_issues = gh_get_all(f"/repos/{OWNER}/{REPO}/issues?state=open", token)
    real_issues = [i for i in open_issues if not i.get("pull_request")]

    plan_issue = next(
        (i for i in real_issues if "/plan" in (i.get("body") or "")), None
    ) or (real_issues[0] if real_issues else None)

    if plan_issue:
        print(f"  open issue #{plan_issue['number']} -> issue_open_with_plan.json")
        write_fixture("issue_open_with_plan.json", sanitize_issue(plan_issue))

        issue_labels = plan_issue.get("labels", [])
        write_fixture(
            "labels_list_issue_pending.json",
            [sanitize_label(lb) for lb in issue_labels],
        )

        comments = _fetch_comments(OWNER, REPO, plan_issue["number"], token)
        comments_clean = [sanitize_comment(c) for c in comments]
        if comments_clean:
            write_fixture("comments_waiting_state.json", comments_clean)
            write_fixture("comments_plan_ready_state.json", comments_clean)
    else:
        print("  (no open issues without PR; keeping existing fixtures)")

    closed_issues = gh_get_all(
        f"/repos/{OWNER}/{REPO}/issues?state=closed&per_page=10", token
    )
    real_closed = [i for i in closed_issues if not i.get("pull_request")]

    done_issue = None
    failed_issue = None
    for ci in real_closed:
        label_names = {lb.get("name", "") for lb in ci.get("labels", [])}
        if "autoswe:done" in label_names:
            if done_issue is None:
                done_issue = ci
        if "autoswe:failed" in label_names:
            if failed_issue is None:
                failed_issue = ci

    if real_closed and done_issue is None:
        done_issue = real_closed[0]

    if done_issue:
        print(f"  closed issue #{done_issue['number']} -> issue_closed.json")
        write_fixture("issue_closed.json", sanitize_issue(done_issue))

        done_comments = _fetch_comments(OWNER, REPO, done_issue["number"], token)
        if done_comments:
            write_fixture(
                "comments_done_state.json",
                [sanitize_comment(c) for c in done_comments],
            )

    if failed_issue:
        print(f"  failed issue #{failed_issue['number']} -> comments_failed_with_retry.json")
        fail_comments = _fetch_comments(OWNER, REPO, failed_issue["number"], token)
        if fail_comments:
            write_fixture(
                "comments_failed_with_retry.json",
                [sanitize_comment(c) for c in fail_comments],
            )

    print("\nDone. Review the files in tests/fixtures/github/ before committing.")
    print("Run: git diff tests/fixtures/github/")


if __name__ == "__main__":
    main()
