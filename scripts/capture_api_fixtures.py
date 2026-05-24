"""Capture live API responses as canonical test fixtures.

Generates one JSON file per endpoint in tests/fixtures/api/<provider>/.
Each file has a __meta block and the sanitized response body.

Usage:
    GITHUB_TOKEN=ghp_... python scripts/capture_api_fixtures.py --provider github
    AZURE_DEVOPS_PAT=... python scripts/capture_api_fixtures.py --provider azure
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

from autoswe.core.logging_utils import mask_sensitive  # noqa: E402

# Email-only pattern for fixture sanitization (not a credential, but still PII)
_SENSITIVE_EMAIL = re.compile(r'[^\s]+@[^\s]+\.[^\s]+')

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
KEEP_PR_KEYS = {
    "id", "number", "state", "title", "html_url", "created_at",
    "head", "base", "user",
}
KEEP_REPO_KEYS = {
    "id", "name", "full_name", "private", "owner",
    "html_url", "default_branch",
}

# Azure-specific
KEEP_ADO_FIELD_KEYS = {
    "System.Id", "System.Title", "System.Description",
    "System.State", "System.Tags", "System.CreatedDate",
    "System.ChangedDate", "System.AssignedTo",
    "System.IterationId", "System.AreaPath",
}
KEEP_ADO_WI_KEYS = {"id", "rev", "fields"}
KEEP_ADO_COMMENT_KEYS = {"id", "text", "createdDate", "createdBy"}
KEEP_ADO_PROFILE_KEYS = {"displayName", "mailAddress", "id", "uniqueName"}
KEEP_ADO_PR_KEYS = {
    "pullRequestId", "sourceRefName", "targetRefName",
    "status", "title", "url", "createdDate",
}
KEEP_ADO_REPO_KEYS = {
    "id", "name", "project", "defaultBranch", "url",
}


def sanitize_body(text: str) -> str:
    """Strip sensitive values from text bodies for fixture capture."""
    if not text:
        return text
    text = mask_sensitive(text)  # centralized credential masking
    text = _SENSITIVE_EMAIL.sub("***REDACTED***", text)  # email masking (not a credential)
    return text


def sanitize_gh_user(u: dict) -> dict:
    if not u:
        return u
    return {k: v for k, v in u.items() if k in KEEP_USER_KEYS}


def sanitize_gh_label(lb: dict) -> dict:
    return {k: v for k, v in lb.items() if k in KEEP_LABEL_KEYS}


def sanitize_gh_issue(issue: dict) -> dict:
    out = {k: v for k, v in issue.items() if k in KEEP_ISSUE_KEYS}
    out["body"] = sanitize_body(out.get("body", "") or "")
    if "user" in out:
        out["user"] = sanitize_gh_user(out["user"])
    if "labels" in out:
        out["labels"] = [sanitize_gh_label(lb) for lb in out["labels"]]
    if "assignees" in out:
        out["assignees"] = [sanitize_gh_user(a) for a in out["assignees"]]
    return out


def sanitize_gh_comment(c: dict) -> dict:
    out = {k: v for k, v in c.items() if k in KEEP_COMMENT_KEYS}
    out["body"] = sanitize_body(out.get("body", "") or "")
    if "user" in out:
        out["user"] = sanitize_gh_user(out["user"])
    return out


def sanitize_gh_pr(pr: dict) -> dict:
    out = {k: v for k, v in pr.items() if k in KEEP_PR_KEYS}
    if "user" in out:
        out["user"] = sanitize_gh_user(out["user"])
    return out


def sanitize_gh_repo(r: dict) -> dict:
    out = {k: v for k, v in r.items() if k in KEEP_REPO_KEYS}
    if "owner" in out:
        out["owner"] = sanitize_gh_user(out["owner"])
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


def sanitize_ado_pr(pr: dict) -> dict:
    return {k: v for k, v in pr.items() if k in KEEP_ADO_PR_KEYS}


def sanitize_ado_repo(r: dict) -> dict:
    return {k: v for k, v in r.items() if k in KEEP_ADO_REPO_KEYS}


def write_fixture(dir_path: Path, name: str, data, endpoint: str, method: str, doc_ref: str) -> None:
    out = {"__meta": {
        "endpoint": endpoint,
        "method": method,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "doc_ref": doc_ref,
    }}
    if isinstance(data, dict):
        out.update(data)
    else:
        out["data"] = data

    path = dir_path / f"{name}.json"
    path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"  wrote {path.name}")


def capture_github(token: str, repo_path: str, issue_num: int) -> None:
    from autoswe.tracking.api import _fetch_comments, gh_get, gh_get_all

    owner, _, repo = repo_path.partition("/")
    if not repo:
        owner, repo = "natedorr", "autoswe"

    out_dir = REPO_ROOT / "tests" / "fixtures" / "api" / "github"
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nCapturing GitHub API fixtures from {owner}/{repo} ...\n")

    # get_user
    print("  GET /user")
    user = gh_get("/user", token)
    write_fixture(out_dir, "get_user", sanitize_gh_user(user),
                  "GET /user", "GET", "docs/github-api/get-user.md")

    # list_repos
    print("  GET /user/repos?type=owner")
    repos = gh_get_all("/user/repos?type=owner", token)
    write_fixture(out_dir, "list_repos", [sanitize_gh_repo(r) for r in repos[:5]],
                  "GET /user/repos?type=owner", "GET", "docs/github-api/list-repos.md")

    # list_repo_labels
    print(f"  GET /repos/{owner}/{repo}/labels")
    repo_labels = gh_get_all(f"/repos/{owner}/{repo}/labels", token)
    write_fixture(out_dir, "list_repo_labels", [sanitize_gh_label(lb) for lb in repo_labels],
                  "GET /repos/{o}/{r}/labels", "GET", "docs/github-api/list-repo-labels.md")

    # list_issues
    print(f"  GET /repos/{owner}/{repo}/issues?state=open")
    issues = gh_get_all(f"/repos/{owner}/{repo}/issues?state=open", token)
    real_issues = [i for i in issues if not i.get("pull_request")]
    write_fixture(out_dir, "list_issues", [sanitize_gh_issue(i) for i in real_issues[:5]],
                  "GET /repos/{o}/{r}/issues?state=open", "GET", "docs/github-api/list-issues.md")

    # Pick an issue to use for single-issue fixtures
    target_issue = None
    if issue_num:
        target_issue = issue_num
    elif real_issues:
        target_issue = real_issues[0]["number"]

    if target_issue:
        # get_issue
        print(f"  GET /repos/{owner}/{repo}/issues/{target_issue}")
        issue = gh_get(f"/repos/{owner}/{repo}/issues/{target_issue}", token)
        write_fixture(out_dir, "get_issue", sanitize_gh_issue(issue),
                      "GET /repos/{o}/{r}/issues/{n}", "GET", "docs/github-api/get-issue.md")

        # list_issue_comments
        print(f"  GET /repos/{owner}/{repo}/issues/{target_issue}/comments")
        comments = _fetch_comments(owner, repo, target_issue, token)
        write_fixture(out_dir, "list_issue_comments",
                      [sanitize_gh_comment(c) for c in comments],
                      "GET /repos/{o}/{r}/issues/{n}/comments", "GET",
                      "docs/github-api/list-issue-comments.md")

        # list_issue_labels
        print(f"  GET /repos/{owner}/{repo}/issues/{target_issue}/labels")
        labels = gh_get(f"/repos/{owner}/{repo}/issues/{target_issue}/labels", token)
        write_fixture(out_dir, "list_issue_labels",
                      [sanitize_gh_label(lb) for lb in labels],
                      "GET /repos/{o}/{r}/issues/{n}/labels", "GET",
                      "docs/github-api/list-issue-labels.md")

        # create_comment (use the shape from a real comment, or a representative one)
        write_fixture(out_dir, "create_comment", {
            "id": 1000,
            "body": "Example comment body",
            "user": sanitize_gh_user(user),
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
            "author_association": "OWNER",
        }, "POST /repos/{o}/{r}/issues/{n}/comments", "POST",
                  "docs/github-api/create-comment.md")

        # replace_labels
        write_fixture(out_dir, "replace_labels", {},
                      "PUT /repos/{o}/{r}/issues/{n}/labels", "PUT",
                      "docs/github-api/replace-labels.md")

        # add_assignees
        write_fixture(out_dir, "add_assignees", {
            "login": "testowner", "id": 1, "type": "User",
        }, "POST /repos/{o}/{r}/issues/{n}/assignees", "POST",
                  "docs/github-api/add-assignees.md")

    # create_issue (representative shape)
    write_fixture(out_dir, "create_issue", sanitize_gh_issue({
        "id": 99999, "number": 99, "state": "open", "title": "New issue",
        "body": "Issue body", "labels": [], "assignees": [],
        "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z",
        "author_association": "OWNER", "comments": 0,
        "pull_request": None, "user": sanitize_gh_user(user),
    }), "POST /repos/{o}/{r}/issues", "POST", "docs/github-api/create-issue.md")

    # list_pulls / create_pull
    print(f"  GET /repos/{owner}/{repo}/pulls?state=open")
    pulls = gh_get_all(f"/repos/{owner}/{repo}/pulls?state=open", token)
    if pulls:
        write_fixture(out_dir, "list_pulls", [sanitize_gh_pr(p) for p in pulls[:3]],
                      "GET /repos/{o}/{r}/pulls?state=open", "GET",
                      "docs/github-api/list-pulls.md")
        write_fixture(out_dir, "create_pull", sanitize_gh_pr(pulls[0]),
                      "POST /repos/{o}/{r}/pulls", "POST",
                      "docs/github-api/create-pull.md")
    else:
        write_fixture(out_dir, "list_pulls", [],
                      "GET /repos/{o}/{r}/pulls?state=open", "GET",
                      "docs/github-api/list-pulls.md")
        write_fixture(out_dir, "create_pull", {
            "number": 1, "state": "open", "title": "PR title",
            "head": {"ref": "autoswe/issue-1"}, "base": {"ref": "main"},
            "user": sanitize_gh_user(user),
        }, "POST /repos/{o}/{r}/pulls", "POST",
                  "docs/github-api/create-pull.md")

    print("\nDone. Review tests/fixtures/api/github/ before committing.")


def capture_azure(cfg: dict) -> None:
    from autoswe.providers.azure.api import _ado_api_version, ado_get, ado_post

    pat = cfg["pat"]
    org = cfg["org"]
    project = cfg["project"]
    repo = cfg["repo"]

    base = f"https://dev.azure.com/{org}/{project}/_apis"

    out_dir = REPO_ROOT / "tests" / "fixtures" / "api" / "azure"
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nCapturing Azure DevOps API fixtures from {org}/{project} ({repo}) ...\n")

    # get_current_user — use work item #1 fallback (same as AzureTracker.authenticated_user)
    print("  GET work item #1 (authenticated_user fallback)")
    wi_1_url = f"https://dev.azure.com/{org}/{project}/_apis/wit/workitems/1?api-version=7.1"
    wi_1 = ado_get(wi_1_url, pat)
    created_by = wi_1.get("fields", {}).get("System.CreatedBy", {})
    profile_data = sanitize_ado_profile(created_by) if created_by else {"uniqueName": "testowner", "id": "1"}
    write_fixture(out_dir, "get_current_user", profile_data,
                  "GET /_apis/wit/workitems/1 (fallback)", "GET", "docs/azure-devops-api/get-user.md")

    # list_repositories
    print("  GET repos")
    repos_url = _ado_api_version(f"https://dev.azure.com/{org}/{project}/_apis/git/repositories")
    repos_resp = ado_get(repos_url, pat)
    write_fixture(out_dir, "list_repositories", {
        "count": len(repos_resp.get("value", [])),
        "value": [sanitize_ado_repo(r) for r in repos_resp.get("value", [])],
    }, "GET /_git/repositories", "GET", "docs/azure-devops-api/list-repositories.md")

    # WIQL query
    print("  WIQL open work items")
    wiql_url = f"{base}/wit/wiql?api-version=7.1"
    wiql_body = {
        "query": (
            f"SELECT [System.Id], [System.Title], [System.State], [System.Tags] "
            f"FROM WorkItems WHERE [System.TeamProject] = '{project}' "
            f"AND [System.State] <> 'Closed' ORDER BY [System.ChangedDate] DESC"
        ),
    }
    wiql_result = ado_post(wiql_url, pat, body=wiql_body)
    write_fixture(out_dir, "wiql_query", wiql_result,
                  "POST wit/wiql", "POST", "docs/azure-devops-api/wiql-query.md")

    work_items = wiql_result.get("workItems", [])
    if not work_items:
        print("  (no open work items found — writing empty fixtures)")
        # Still write the remaining fixtures with representative shapes
        _write_empty_azure_fixtures(out_dir, org, project, repo)
        return

    # workitems_batch
    ids = [w["id"] for w in work_items[:5]]
    batch_url = f"{base}/wit/workitemsbatch?api-version=7.1"
    batch = ado_post(batch_url, pat, body={"ids": ids, "$expand": "all"})
    write_fixture(out_dir, "workitems_batch", {
        "count": len(batch.get("value", [])),
        "value": [sanitize_ado_wi(wi) for wi in batch.get("value", [])],
    }, "POST wit/workitemsbatch", "POST", "docs/azure-devops-api/workitems-batch.md")

    # get_workitem (first open item)
    first_id = work_items[0]["id"]
    print(f"  GET work item #{first_id}")
    wi_url = _ado_api_version(f"{base}/wit/workitems/{first_id}")
    wi_open = ado_get(wi_url, pat)
    write_fixture(out_dir, "get_workitem", sanitize_ado_wi(wi_open),
                  "GET /_apis/wit/workitems/{n}", "GET", "docs/azure-devops-api/get-workitem.md")

    # list_workitem_comments
    print(f"  GET work item #{first_id} comments")
    comments_url = f"{base}/wit/workitems/{first_id}/comments?api-version=7.1-preview.4"
    comments_resp = ado_get(comments_url, pat)
    write_fixture(out_dir, "list_workitem_comments", {
        "count": len(comments_resp.get("comments", [])),
        "comments": [sanitize_ado_comment(c) for c in comments_resp.get("comments", [])],
    }, "GET /_apis/wit/workitems/{n}/comments", "GET",
                  "docs/azure-devops-api/list-workitem-comments.md")

    # create_workitem_comment (representative)
    first_comment = comments_resp.get("comments", [{}])[0] if comments_resp.get("comments") else {}
    write_fixture(out_dir, "create_workitem_comment", {
        "id": first_comment.get("id", 1000) + 1,
        "text": "Example comment text",
        "createdDate": first_comment.get("createdDate", "2026-01-01T00:00:00.000Z"),
        "createdBy": created_by if created_by else {"uniqueName": "testowner", "id": "1"},
    }, "POST /_apis/wit/workitems/{n}/comments", "POST",
                  "docs/azure-devops-api/create-workitem-comment.md")

    # update_workitem (representative JSON-Patch shape)
    write_fixture(out_dir, "update_workitem", [
        {"op": "replace", "path": "/fields/System.Tags", "value": "tag1; autoswe:pending"},
    ], "PATCH /_apis/wit/workitems/{n}", "PATCH",
                  "docs/azure-devops-api/update-workitem.md")

    # create_workitem (representative JSON-Patch shape)
    write_fixture(out_dir, "create_workitem", [
        {"op": "add", "path": "/fields/System.Title", "value": "New work item"},
        {"op": "add", "path": "/fields/System.Description", "value": "Description here"},
    ], "POST /_apis/wit/workitems/$Issue", "POST",
                  "docs/azure-devops-api/create-workitem.md")

    # list_pullrequests
    print(f"  GET PRs for repo '{repo}'")
    pr_url = f"{base}/git/repositories/{repo}/pullrequests?api-version=7.1"
    prs_resp = ado_get(pr_url, pat)
    pr_values = prs_resp.get("value", [])
    if pr_values:
        write_fixture(out_dir, "list_pullrequests", {
            "count": len(pr_values),
            "value": [sanitize_ado_pr(p) for p in pr_values[:3]],
        }, "GET /_git/repositories/{repo}/pullrequests", "GET",
                      "docs/azure-devops-api/list-pullrequests.md")
        write_fixture(out_dir, "create_pullrequest", sanitize_ado_pr(pr_values[0]),
                      "POST /_git/repositories/{repo}/pullrequests", "POST",
                      "docs/azure-devops-api/create-pullrequest.md")
    else:
        write_fixture(out_dir, "list_pullrequests", {"count": 0, "value": []},
                      "GET /_git/repositories/{repo}/pullrequests", "GET",
                      "docs/azure-devops-api/list-pullrequests.md")
        write_fixture(out_dir, "create_pullrequest", {
            "pullRequestId": 1,
            "sourceRefName": "refs/heads/autoswe/issue-1",
            "targetRefName": "refs/heads/main",
            "status": 3,
            "title": "autoswe: fix for issue #1",
            "url": f"https://dev.azure.com/{org}/{project}/_git/{repo}/pullrequest/1",
        }, "POST /_git/repositories/{repo}/pullrequests", "POST",
                      "docs/azure-devops-api/create-pullrequest.md")

    print("\nDone. Review tests/fixtures/api/azure/ before committing.")


def _write_empty_azure_fixtures(out_dir: Path, org: str, project: str, repo: str) -> None:
    """Write representative empty fixtures when no live data is available."""
    write_fixture(out_dir, "get_workitem", {
        "id": 1, "fields": {
            "System.Title": "Fixture work item",
            "System.State": "New",
            "System.Tags": "",
        },
    }, "GET /_apis/wit/workitems/{n}", "GET", "docs/azure-devops-api/get-workitem.md")
    write_fixture(out_dir, "list_workitem_comments", {
        "count": 0, "comments": [],
    }, "GET /_apis/wit/workitems/{n}/comments", "GET",
                  "docs/azure-devops-api/list-workitem-comments.md")
    write_fixture(out_dir, "create_workitem_comment", {
        "id": 1, "text": "Example comment", "createdDate": "2026-01-01T00:00:00.000Z",
    }, "POST /_apis/wit/workitems/{n}/comments", "POST",
                  "docs/azure-devops-api/create-workitem-comment.md")
    write_fixture(out_dir, "update_workitem", [
        {"op": "replace", "path": "/fields/System.Tags", "value": "tag1; autoswe:pending"},
    ], "PATCH /_apis/wit/workitems/{n}", "PATCH",
                  "docs/azure-devops-api/update-workitem.md")
    write_fixture(out_dir, "create_workitem", [
        {"op": "add", "path": "/fields/System.Title", "value": "New work item"},
        {"op": "add", "path": "/fields/System.Description", "value": "Description"},
    ], "POST /_apis/wit/workitems/$Issue", "POST",
                  "docs/azure-devops-api/create-workitem.md")
    write_fixture(out_dir, "list_pullrequests", {"count": 0, "value": []},
                  "GET /_git/repositories/{repo}/pullrequests", "GET",
                  "docs/azure-devops-api/list-pullrequests.md")
    write_fixture(out_dir, "create_pullrequest", {
        "pullRequestId": 1,
        "sourceRefName": "refs/heads/autoswe/issue-1",
        "targetRefName": "refs/heads/main",
        "status": 3,
        "title": "autoswe: fix for issue #1",
    }, "POST /_git/repositories/{repo}/pullrequests", "POST",
                  "docs/azure-devops-api/create-pullrequest.md")


def _azure_cfg():
    from autoswe.core.config import load_config, load_repos_config
    cfg = load_config()
    repos_cfg = load_repos_config()

    pat = os.environ.get("AZURE_DEVOPS_PAT", "") or cfg.get("AZURE_DEVOPS_PAT", "")
    org = os.environ.get("AZURE_DEVOPS_ORG", "") or cfg.get("AZURE_DEVOPS_ORG", "")
    project = os.environ.get("AZURE_DEVOPS_PROJECT", "") or cfg.get("AZURE_DEVOPS_PROJECT", "")
    repo = os.environ.get("AZURE_DEVOPS_REPO", "") or cfg.get("AZURE_DEVOPS_REPO", "")

    # Fall back to first Azure repo entry in repos.json
    if not all([org, project, repo]):
        for _key, entry in repos_cfg.items():
            if entry.get("provider", "").lower() == "azure":
                pat = pat or entry.get("pat", "")
                org = org or entry.get("org", org)
                project = project or entry.get("project", project)
                repo = repo or entry.get("repo", repo)
                break

    return {"pat": pat, "org": org, "project": project, "repo": repo}


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture live API responses as test fixtures.")
    parser.add_argument("--provider", required=True, choices=["github", "azure"])
    parser.add_argument("--repo", default="", help="owner/repo for GitHub, or org/project/repo for Azure")
    parser.add_argument("--issue", type=int, default=0, help="Issue/work-item number to use as target")
    args = parser.parse_args()

    # Load config from default AUTOSWE_DIR first, then set capture dir for logs
    from autoswe.core.config import load_config
    cfg = load_config()

    os.environ["AUTOSWE_DIR"] = str(REPO_ROOT / ".capture_tmp")
    Path(os.environ["AUTOSWE_DIR"] + "/logs").mkdir(parents=True, exist_ok=True)

    if args.provider == "github":
        token = cfg.get("GITHUB_TOKEN", "") or os.environ.get("GITHUB_TOKEN", "")
        if not token:
            print("[ERROR] GITHUB_TOKEN not set. Export it or add it to config/autoswe.env.")
            sys.exit(1)
        capture_github(token, args.repo, args.issue)
    elif args.provider == "azure":
        azure_cfg = _azure_cfg()
        if not azure_cfg["pat"]:
            print("[ERROR] AZURE_DEVOPS_PAT not set (env vars or autoswe.env).")
            sys.exit(1)
        if args.repo:
            parts = args.repo.rsplit("/", 2)
            if len(parts) == 3:
                azure_cfg["org"], azure_cfg["project"], azure_cfg["repo"] = parts
            elif len(parts) == 2:
                azure_cfg["project"], azure_cfg["repo"] = parts
        capture_azure(azure_cfg)


if __name__ == "__main__":
    main()
