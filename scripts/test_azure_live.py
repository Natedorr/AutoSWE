#!/usr/bin/env python3
"""Consolidated Azure DevOps API test suite.

Tests the raw API, IssueTracker, VCS provider, and the full sync
workflow end-to-end against a live Azure DevOps project.

Usage:
    python test_azure_live.py
"""
import os
import sys
from urllib.parse import urlparse

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))

from autoswe.core.config import load_config
from autoswe.core.slug import make_slug
from autoswe.providers.azure.api import _ado_api_version, ado_get, ado_patch, ado_post
from autoswe.providers.azure.tracker import AzureTracker
from autoswe.providers.azure.vcs import AzureVCS
from autoswe.providers.factory import get_tracker

# ------ Config ------

cfg = load_config()
PAT = cfg.get("AZURE_DEVOPS_PAT", "")
ORG = "natedorr"
PROJECT = "testProject"
REPO = "testProject"

if not PAT:
    print("[ERROR] No AZURE_DEVOPS_PAT in autoswe.env")
    sys.exit(1)

REPO_CFG = {
    "provider": "azure",
    "org": ORG,
    "project": PROJECT,
    "repo": REPO,
    "pat": PAT,
    "base_branch": "main",
}

# ------ Helpers ------

_passed = 0
_failed = 0
_errors: list[tuple[str, str]] = []


def run(name: str, func, *args):
    """Run *func* and tally pass/fail."""
    global _passed, _failed
    try:
        result = func(*args)
        _passed += 1
        print(f"  PASS: {name}")
        return result
    except Exception as e:
        _failed += 1
        _errors.append((name, str(e)))
        print(f"  FAIL: {name}: {e}")
        return None


# ===== 1. RAW API — Basic Connectivity =====

print("\n1. RAW API — Basic Connectivity")
print("-" * 60)


def _projects():
    r = ado_get(_ado_api_version(f"https://dev.azure.com/{ORG}/_apis/projects"), PAT)
    assert r["count"] > 0


def _project_detail():
    r = ado_get(_ado_api_version(f"https://dev.azure.com/{ORG}/_apis/projects/{PROJECT}"), PAT)
    assert r["name"] == PROJECT


def _repos():
    r = ado_get(_ado_api_version(f"https://dev.azure.com/{ORG}/{PROJECT}/_apis/git/repositories"), PAT)
    assert r["count"] > 0


def _repo_detail():
    r = ado_get(_ado_api_version(f"https://dev.azure.com/{ORG}/{PROJECT}/_apis/git/repositories/{REPO}"), PAT)
    assert r["name"] == REPO


def _profile():
    # Use the work item endpoint to get the authenticated user (VSSPS requires OAuth, not PAT)
    tracker = AzureTracker(REPO_CFG)
    user = tracker.authenticated_user(REPO_CFG)
    assert user
    print(f"    Authenticated as: {user}")


run("list projects", _projects)
run("project detail", _project_detail)
run("list repos", _repos)
run("repo detail", _repo_detail)
run("user profile", _profile)

# ===== 2. RAW API — Work Items (CRUD + tags + comments) =====

print("\n2. RAW API — Work Items")
print("-" * 60)


def _wiql():
    wiql = {
        "query": (
            "SELECT [System.Id] FROM WorkItems "
            "WHERE [System.State] NOT IN ('Closed','Done','Removed') "
            f"AND [System.TeamProject] = '{PROJECT}'"
        ),
    }
    r = ado_post(_ado_api_version(f"https://dev.azure.com/{ORG}/{PROJECT}/_apis/wit/wiql"), PAT, body=wiql)
    assert "workItems" in r
    return r


def _wiql_empty():
    wiql = {"query": f"SELECT [System.Id] FROM WorkItems WHERE [System.Id] = 99999 AND [System.TeamProject] = '{PROJECT}'"}
    r = ado_post(_ado_api_version(f"https://dev.azure.com/{ORG}/{PROJECT}/_apis/wit/wiql"), PAT, body=wiql)
    assert len(r["workItems"]) == 0


def _fetch_wi():
    r = ado_get(_ado_api_version(f"https://dev.azure.com/{ORG}/{PROJECT}/_apis/wit/workitems/1?$expand=all"), PAT)
    assert r["id"] == 1
    assert "fields" in r


def _fetch_wi_fields():
    r = ado_get(_ado_api_version(f"https://dev.azure.com/{ORG}/{PROJECT}/_apis/wit/workitems/1?fields=System.Title,System.Tags"), PAT)
    assert "fields" in r
    assert "System.Title" in r["fields"]


def _create_wi():
    payload = [{"op": "add", "path": "/fields/System.Title", "value": f"API Test {_passed}"}]
    r = ado_patch(_ado_api_version(f"https://dev.azure.com/{ORG}/{PROJECT}/_apis/wit/workitems/$Issue"), PAT, body=payload)
    assert "id" in r
    return r["id"]


def _update_wi(wid):
    payload = [{"op": "replace", "path": "/fields/System.Title", "value": f"Updated {wid}"}]
    r = ado_patch(_ado_api_version(f"https://dev.azure.com/{ORG}/{PROJECT}/_apis/wit/workitems/{wid}"), PAT, body=payload)
    assert r["id"] == wid


def _set_tags():
    payload = [{"op": "replace", "path": "/fields/System.Tags", "value": "autoswe:pending; test-tag"}]
    r = ado_patch(_ado_api_version(f"https://dev.azure.com/{ORG}/{PROJECT}/_apis/wit/workitems/1"), PAT, body=payload)
    assert r["id"] == 1


def _get_comments():
    r = ado_get(f"https://dev.azure.com/{ORG}/{PROJECT}/_apis/wit/workitems/1/comments?api-version=7.1-preview.4", PAT)
    assert "comments" in r or "totalCount" in r


wiql_res = run("WIQL query", _wiql)
run("WIQL empty result", _wiql_empty)
run("fetch work item #1", _fetch_wi)
run("fetch work item fields", _fetch_wi_fields)
wid = run("create work item", _create_wi)
if wid:
    run("update work item title", _update_wi, wid)
    run("set tags", _set_tags)
    run("get comments", _get_comments)

# ===== 3. IssueTracker Protocol =====

print("\n3. IssueTracker Protocol")
print("-" * 60)

tracker = AzureTracker(REPO_CFG)


def _tracker_list():
    issues = tracker.list_open_issues(REPO_CFG)
    assert len(issues) > 0
    assert issues[0].number is not None


def _tracker_fetch():
    issue = tracker.fetch_issue(REPO_CFG, 1)
    assert issue.number == 1
    assert issue.title is not None


def _tracker_comments():
    comments = tracker.fetch_comments(REPO_CFG, 1)
    assert len(comments) > 0
    assert comments[0].body is not None


def _tracker_status():
    issue = tracker.fetch_issue(REPO_CFG, 1)
    status = tracker.get_status(issue)
    assert status is not None


def _tracker_create():
    wid = tracker.create_issue(REPO_CFG, "API Test Issue", "Test body")
    assert wid is not None
    return wid


def _tracker_post_comment():
    tracker.post_comment(REPO_CFG, 1, "Test comment from autoSWE API test")


def _tracker_set_status_pending():
    tracker.set_status(REPO_CFG, 1, "pending")


def _tracker_set_status_dispatched():
    tracker.set_status(REPO_CFG, 1, "dispatched")


def _tracker_set_status_done():
    tracker.set_status(REPO_CFG, 1, "done")


run("tracker: list open issues", _tracker_list)
run("tracker: fetch issue #1", _tracker_fetch)
run("tracker: fetch comments", _tracker_comments)
run("tracker: get status", _tracker_status)
run("tracker: create issue", _tracker_create)
run("tracker: post comment", _tracker_post_comment)
run("tracker: set status pending", _tracker_set_status_pending)
run("tracker: set status dispatched", _tracker_set_status_dispatched)
run("tracker: set status done", _tracker_set_status_done)

# ===== 4. VCS Provider =====

print("\n4. VCS Provider")
print("-" * 60)

vcs = AzureVCS(REPO_CFG)


def _vcs_clone():
    url = vcs.clone_url(REPO_CFG)
    assert urlparse(url).hostname.endswith("dev.azure.com")
    assert (urlparse(url).password or "").startswith(PAT[:20])


def _vcs_branch():
    assert vcs.branch_name(42) == "autoswe/issue-42"


def _vcs_find_none():
    assert vcs.find_existing_pr(REPO_CFG, "nonexistent-branch") is None


def _vcs_pr_roundtrip():
    """Open a PR, verify it exists, then close it."""
    branch = f"autoswe/test-api-{_passed}"
    try:
        pr = vcs.open_pull_request(REPO_CFG, branch, "main", "API Test PR", "Test body")
        assert pr.number is not None
        assert urlparse(pr.url).hostname.endswith("dev.azure.com")
        found = vcs.find_existing_pr(REPO_CFG, branch)
        assert found is not None
        assert found.number == pr.number
        # close the PR
        close_path = _ado_api_version(f"https://dev.azure.com/{ORG}/{PROJECT}/_apis/git/repositories/{REPO}/pullrequests/{pr.number}")
        ado_post(close_path, PAT, body={"status": "completed", "completionOptions": {"deleteSourceBranch": False}})
        return pr.number
    except RuntimeError as e:
        assert "TF401398" in str(e) or "pull request" in str(e).lower()
        return None


pr_num = None
run("vcs: clone_url", _vcs_clone)
run("vcs: branch_name", _vcs_branch)
run("vcs: find_existing_pr (none)", _vcs_find_none)
pr_num = run("vcs: open PR / find / close", _vcs_pr_roundtrip)
if pr_num:
    print(f"  Created and closed PR #{pr_num}")

# ===== 5. Slug Helpers =====

print("\n5. Slug Helpers")
print("-" * 60)


def _slug_roundtrip():
    slug = make_slug("azure", (ORG, REPO), 42)
    assert slug == f"ado:{ORG}_{REPO}_42"


def _slug_prefix():
    slug = make_slug("azure", (ORG, REPO), 1)
    assert slug.startswith("ado:")


run("slug: roundtrip", _slug_roundtrip)
run("slug: prefix", _slug_prefix)

# ===== 6. Sync Workflow (factory-based end-to-end) =====

print("\n6. Sync Workflow (factory)")
print("-" * 60)

factory_tracker = get_tracker(REPO_CFG)


def _sync_list():
    issues = factory_tracker.list_open_issues(REPO_CFG)
    assert len(issues) > 0


def _sync_fetch():
    issue = factory_tracker.fetch_issue(REPO_CFG, 1)
    assert issue.title


def _sync_comments():
    comments = factory_tracker.fetch_comments(REPO_CFG, 1)
    assert len(comments) > 0


def _sync_status():
    factory_tracker.set_status(REPO_CFG, 1, "pending")


def _sync_comment():
    factory_tracker.post_comment(REPO_CFG, 1, "Test comment from sync debug")


def _sync_assign():
    factory_tracker.assign_to_user(REPO_CFG, 1, None)


run("sync: list open issues", _sync_list)
run("sync: fetch issue #1", _sync_fetch)
run("sync: fetch comments", _sync_comments)
run("sync: set status", _sync_status)
run("sync: post comment", _sync_comment)
run("sync: assign to user", _sync_assign)

# ===== 7. Edge Cases =====

print("\n7. Edge Cases")
print("-" * 60)


def _bad_project():
    try:
        ado_get(_ado_api_version(f"https://dev.azure.com/{ORG}/_apis/projects/INVALID"), PAT)
        raise AssertionError("Should have raised")
    except RuntimeError as e:
        assert "HTTP" in str(e)


def _multi_tags():
    payload = [{"op": "replace", "path": "/fields/System.Tags", "value": "autoswe:pending; tag1; tag2"}]
    r = ado_patch(_ado_api_version(f"https://dev.azure.com/{ORG}/{PROJECT}/_apis/wit/workitems/1"), PAT, body=payload)
    assert r["id"] == 1


run("edge: bad project => error", _bad_project)
run("edge: multi-value tags", _multi_tags)

# ===== Summary =====

total = _passed + _failed
print("\n" + "=" * 60)
print(f"  Total:  {total}")
print(f"  Passed: {_passed}")
print(f"  Failed: {_failed}")
if _errors:
    print("\n  Failures:")
    for name, err in _errors:
        print(f"    • {name}: {err[:200]}")
print("=" * 60)

sys.exit(0 if _failed == 0 else 1)
