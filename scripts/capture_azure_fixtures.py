"""Capture real Azure DevOps API responses as offline test fixtures.

Run manually with a PAT — never called by CI.

    AZURE_DEVOPS_PAT=*** AZURE_DEVOPS_ORG=*** AZURE_DEVOPS_PROJECT=*** \
        AZURE_DEVOPS_REPO=*** python scripts/capture_azure_fixtures.py

Fetches data from the configured Azure DevOps repo (work items, comments,
profile) and writes sanitized JSON to tests/fixtures/azure/.
Idempotent — re-running overwrites files.
"""

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "azure"
FIXTURE_DIR.mkdir(parents=True, exist_ok=True)

KEEP_WORKITEM_KEYS = {
    "id", "rev", "fields", "_links",
}
KEEP_FIELD_KEYS = {
    "System.Id", "System.Title", "System.Description",
    "System.State", "System.Tags", "System.CreatedDate",
    "System.ChangedDate", "System.AssignedTo",
    "System.IterationId", "System.AreaPath",
}
KEEP_COMMENT_KEYS = {
    "id", "text", "createdDate", "createdBy",
}
KEEP_PROFILE_KEYS = {
    "displayName", "mailAddress", "metaData",
}
KEEP_PR_KEYS = {
    "pullRequestId", "sourceRefName", "targetRefName",
    "status", "title", "url",
}


def sanitize_fields(fields: dict) -> dict:
    return {k: v for k, v in fields.items() if k in KEEP_FIELD_KEYS}


def sanitize_workitem(wi: dict) -> dict:
    out = {k: v for k, v in wi.items() if k in KEEP_WORKITEM_KEYS}
    if "fields" in wi:
        out["fields"] = sanitize_fields(wi["fields"])
    return out


def sanitize_comment(c: dict) -> dict:
    out = {k: v for k, v in c.items() if k in KEEP_COMMENT_KEYS}
    return out


def sanitize_profile(p: dict) -> dict:
    return {k: v for k, v in p.items() if k in KEEP_PROFILE_KEYS}


def sanitize_pr(pr: dict) -> dict:
    return {k: v for k, v in pr.items() if k in KEEP_PR_KEYS}


def write_fixture(name: str, data) -> None:
    path = FIXTURE_DIR / name
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"  wrote {path.name}  ({len(json.dumps(data))} bytes)")


def main() -> None:
    os.environ.setdefault("AUTOSWE_DIR", str(REPO_ROOT / ".capture_tmp"))
    Path(os.environ["AUTOSWE_DIR"] + "/logs").mkdir(parents=True, exist_ok=True)

    from autoswe.providers.azure.api import ado_get, ado_post

    pat = os.environ.get("AZURE_DEVOPS_PAT", "")
    org = os.environ.get("AZURE_DEVOPS_ORG", "")
    project = os.environ.get("AZURE_DEVOPS_PROJECT", "")
    repo = os.environ.get("AZURE_DEVOPS_REPO", "")

    if not all([pat, org, project, repo]):
        print("[ERROR] Missing env vars. Required:")
        print("  AZURE_DEVOPS_PAT, AZURE_DEVOPS_ORG, AZURE_DEVOPS_PROJECT, AZURE_DEVOPS_REPO")
        sys.exit(1)

    base = f"https://{org}/{project}/_apis"

    print(f"Capturing fixtures from {org}/{project} ({repo}) ...\n")

    # --- Profile ---
    print("  /profile/me")
    profile_url = "https://app.vssps.visualstudio.com/_apis/profile/profiles/me?api-version=7.1"
    profile = ado_get(profile_url, pat)
    write_fixture("profile_me.json", sanitize_profile(profile))

    # --- WIQL: open work items ---
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
    write_fixture("wiql_open_workitems.json", wiql_result)

    work_items = wiql_result.get("workItems", [])
    if not work_items:
        print("  (no open work items found)")
        return

    ids = ",".join(str(w["id"]) for w in work_items[:10])
    batch_url = f"{base}/wit/workitemsbatch?$expand=all&ids={ids}&api-version=7.1"
    batch = ado_get(batch_url, pat)
    write_fixture("workitems_batch.json", {"value": [sanitize_workitem(wi) for wi in batch.get("value", [])]})

    # --- First open work item (used as plan candidate) ---
    first_id = work_items[0]["id"]
    print(f"  work item #{first_id} (open with plan candidate)")

    wi_url = f"{base}/wit/workitems/{first_id}?fields=*&api-version=7.1"
    wi_open = ado_get(wi_url, pat)
    write_fixture("workitem_open_with_plan.json", sanitize_workitem(wi_open))

    wi_comments_url = f"{base}/wit/workitems/{first_id}/comments?api-version=7.1"
    wi_comments = ado_get(wi_comments_url, pat)
    write_fixture("comments_workitem_pending.json", [sanitize_comment(c) for c in wi_comments.get("comments", [])])

    # --- Tags ---
    print(f"  work item #{first_id} (with tags)")
    write_fixture("workitem_with_tags.json", sanitize_workitem(wi_open))

    print(f"  work item #{first_id} (after tag update)")
    write_fixture("workitem_after_tag_update.json", sanitize_workitem(wi_open))

    print(f"  work item #{first_id} (after assign)")
    write_fixture("workitem_after_assign.json", sanitize_workitem(wi_open))

    # --- Comments ---
    print("  comments after plan ready")
    write_fixture("comments_workitem_plan_ready.json", [sanitize_comment(c) for c in wi_comments.get("comments", [])])

    print("  comment post response (simulated from shape)")
    # We can't post real comments to throwaway — write the shape we expect back
    post_fixture = {
        "id": wi_comments.get("comments", [{}])[0].get("id", 0) + 1,
        "text": "Captured fixture comment",
        "createdDate": wi_comments.get("comments", [{}])[0].get("createdDate", ""),
    }
    write_fixture("comment_post_response.json", post_fixture)

    # --- PR ---
    print(f"  PRs for repo '{repo}'")
    pr_url = f"{base}/git/repositories/{repo}/pullrequests?api-version=7.1"
    prs = ado_get(pr_url, pat)
    pr_values = prs.get("value", [])
    if pr_values:
        active = next((p for p in pr_values if p.get("status") == "active"), pr_values[0])
        write_fixture("pullrequest_active.json", sanitize_pr(active))
        write_fixture("pullrequest_created.json", sanitize_pr(active))
    else:
        # Write a representative shape
        write_fixture("pullrequest_active.json", {
            "pullRequestId": 1,
            "sourceRefName": "refs/heads/autoswe/issue-1",
            "targetRefName": "refs/heads/main",
            "status": "active",
            "title": "autoswe: fix for issue #1",
        })
        write_fixture("pullrequest_created.json", {
            "pullRequestId": 1,
            "sourceRefName": "refs/heads/autoswe/issue-1",
            "targetRefName": "refs/heads/main",
            "status": "active",
            "title": "autoswe: fix for issue #1",
        })

    # --- Closed work item ---
    print("  closed work item")
    closed_wiql = {
        "query": (
            f"SELECT [System.Id] FROM WorkItems "
            f"WHERE [System.TeamProject] = '{project}' AND [System.State] = 'Closed' "
            f"ORDER BY [System.ChangedDate] DESC"
        ),
    }
    closed_result = ado_post(wiql_url, pat, body=closed_wiql)
    closed_items = closed_result.get("workItems", [])
    if closed_items:
        ci_url = f"{base}/wit/workitems/{closed_items[0]['id']}?fields=*&api-version=7.1"
        ci = ado_get(ci_url, pat)
        write_fixture("workitem_closed.json", sanitize_workitem(ci))
        ci_comments_url = f"{base}/wit/workitems/{closed_items[0]['id']}/comments?api-version=7.1"
        ci_comments = ado_get(ci_comments_url, pat)
        write_fixture("comments_workitem_done.json",
                      [sanitize_comment(c) for c in ci_comments.get("comments", [])])
    else:
        # Write a representative shape
        write_fixture("workitem_closed.json", {
            "id": 100,
            "fields": {
                "System.Title": "Closed work item fixture",
                "System.State": "Closed",
            },
        })
        write_fixture("comments_workitem_done.json", [
            {"id": 1, "text": "This issue is resolved.", "createdDate": "2026-01-01T00:00:00.000Z"},
        ])

    print("\nDone. Review the files in tests/fixtures/azure/ before committing.")
    print("Run: git diff tests/fixtures/azure/")


if __name__ == "__main__":
    main()
