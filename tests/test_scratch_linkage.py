"""Final probe for the 3 linkage rows — all providers. NOT a real test."""
import pytest
from pathlib import Path

from tests.scenarios.harness import (
    build_test_cfg, patched_world, seed_queue, setup_repos,
)
from tests.scenarios.transitions import build_azure_state, build_github_state, build_queue_task


def _run(provider, row, isolated_autoswe_dir, pulls=None, ci=None):
    from tests.scenarios.runner import run_one_turn, get_queue_task
    state = build_github_state(row) if provider == "github" else build_azure_state(row)
    if pulls is not None:
        state["pulls"] = pulls
    if ci is not None:
        state["ci_status"] = ci
    qtask = build_queue_task(row, provider)
    seed_queue(isolated_autoswe_dir, qtask)
    setup_repos(isolated_autoswe_dir, provider, state)
    cfg = build_test_cfg(isolated_autoswe_dir, provider)
    with patched_world(provider, state=state, claude_responses=[], scripted_git=[],
                       isolated_dir=isolated_autoswe_dir) as hw:
        owner, repo = (state["owner"], state["repo"]) if provider == "github" else (state["org"], state["project"])
        run_one_turn(owner, repo, cfg, isolated_autoswe_dir)
    tid = "gh:owner_repo_42" if provider == "github" else "ado:testorg_testproj/testrepo_42"
    t = get_queue_task(isolated_autoswe_dir, tid)
    if provider == "github":
        closed = hw.fake.issues[42].get("state") == "closed"
        refs = hw.fake.pulls.get(1, {}).get("workItemRefs")
    else:
        closed = hw.fake.work_items[42]["fields"].get("System.State") in ("Closed", "Done", "Removed")
        refs = hw.fake.pulls.get(1, {}).get("workItemRefs")
    return t, closed, refs, hw


# ---- Row 1: PR opened via /pr ----
_row1 = {
    "name": "r1", "start": {
        "issue": {"body": "Fix.\n\n/fix"},
        "labels": ["autoswe:fixed"],
        "comments": [
            {"body": "Completed with command `/fix` — DONE_SUMMARY\n\n<!-- autoswe-bot -->",
             "created_at": "2026-01-01T01:00:00Z", "author_association": "OWNER",
             "user": {"login": "owner", "id": 1, "type": "User"}},
            {"body": "/pr", "created_at": "2026-01-01T02:00:00Z", "author_association": "OWNER",
             "user": {"login": "owner", "id": 1, "type": "User"}},
        ],
        "queue_task": {"id": "gh:owner_repo_42", "owner": "owner", "repo": "repo", "issue_number": 42,
                       "title": "Test issue", "body": "Fix.", "autoswe_status": "fixed",
                       "base_branch": "main", "attempt_count": 1, "first_dispatched_at": None,
                       "session_id": "s-fix-prev", "pr_number": None, "provider": "github"},
    },
}


def test_row1(isolated_autoswe_dir: Path):
    for prov in ("github", "azure"):
        t, closed, refs, hw = _run(prov, _row1, isolated_autoswe_dir, ci="success")
        ls = t.get("linkage_state")
        print(f"\nR1 {prov}: status={t.get('autoswe_status')} pr={t.get('pr_number')} closed={closed}")
        print(f"   refs={refs}  linkage={ls}")
        print(f"   missing={t.get('linkage_missing')}")


# ---- Row 2: merged PR, NO closing keyword (close owed on both) ----
_row2 = {
    "name": "r2", "start": {
        "issue": {"body": "Fix."},
        "labels": ["autoswe:shipped"],
        "comments": [
            {"body": "Completed with command `/pr` — PR created\n\n<!-- autoswe-bot -->",
             "created_at": "2026-01-01T02:00:00Z", "author_association": "OWNER",
             "user": {"login": "owner", "id": 1, "type": "User"}},
        ],
        "queue_task": {"id": "gh:owner_repo_42", "owner": "owner", "repo": "repo", "issue_number": 42,
                       "title": "Test issue", "body": "Fix.", "autoswe_status": "shipped",
                       "base_branch": "main", "attempt_count": 1, "first_dispatched_at": None,
                       "last_dispatched_command": "/pr", "last_dispatched_command_id": 2,
                       "last_consumed_reply_id": 2, "session_id": "s-fix-prev",
                       "pr_number": 1, "provider": "github"},
    },
}


def test_row2(isolated_autoswe_dir: Path):
    # no closing keyword on github (body ""); azure has workItemRefs
    for prov in ("github", "azure"):
        pulls = {1: (
            {"number": 1, "merged": True, "body": "",
             "head": {"ref": "autoswe/issue-42", "sha": "cafebabe"},
             "base": {"ref": "main"}, "mergeable_state": "clean"}
            if prov == "github" else
            {"pullRequestId": 1, "isMerged": True, "headSha": "cafebabe",
             "sourceRefName": "refs/heads/autoswe/issue-42",
             "status": {"mergeStatus": "succeeded"}, "workItemRefs": [{"id": 42}]})}
        t, closed, refs, hw = _run(prov, _row2, isolated_autoswe_dir, pulls=pulls)
        print(f"\nR2 {prov}: closed={closed} linkage={t.get('linkage_state')}")
        print(f"   missing={t.get('linkage_missing')}")


# ---- Row 3: merged PR WITH closing keyword ----
_row3 = _row2  # same base; keyword differs by provider seed


def test_row3(isolated_autoswe_dir: Path):
    for prov in ("github", "azure"):
        pulls = {1: (
            {"number": 1, "merged": True, "body": "Fixes #42",
             "head": {"ref": "autoswe/issue-42", "sha": "cafebabe"},
             "base": {"ref": "main"}, "mergeable_state": "clean"}
            if prov == "github" else
            {"pullRequestId": 1, "isMerged": True, "headSha": "cafebabe",
             "sourceRefName": "refs/heads/autoswe/issue-42",
             "status": {"mergeStatus": "succeeded"}, "workItemRefs": [{"id": 42}]})}
        t, closed, refs, hw = _run(prov, _row3, isolated_autoswe_dir, pulls=pulls)
        print(f"\nR3 {prov}: closed={closed} linkage={t.get('linkage_state')}")
        print(f"   missing={t.get('linkage_missing')}")
