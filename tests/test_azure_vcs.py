"""Tests for autoswe.providers.azure.vcs — Azure DevOps VCSProvider."""
from urllib.parse import urlparse

import pytest

from autoswe.providers.azure.api import _ado_api_version, ado_patch_json
from autoswe.providers.azure.vcs import AzureVCS
from tests.conftest import load_ado_fixture


@pytest.fixture
def ado_vcs_repo_cfg():
    return {
        "provider": "azure",
        "org": "my-org",
        "project": "my-project",
        "repo": "my-repo",
        "pat": "fake_pat_123",
    }


@pytest.fixture
def vcs(ado_vcs_repo_cfg):
    return AzureVCS(ado_vcs_repo_cfg)


# -- clone_url --

def test_clone_url(vcs):
    url = vcs.clone_url()
    assert url == "https://autoswe:fake_pat_123@dev.azure.com/my-org/my-project/_git/my-repo"


def test_clone_url_contains_pat(vcs):
    url = vcs.clone_url()
    assert urlparse(url).password == "fake_pat_123"
    assert urlparse(url).hostname.endswith("dev.azure.com")


# -- branch_name --

def test_branch_name(vcs):
    assert vcs.branch_name(100) == "autoswe/issue-100"
    assert vcs.branch_name(1) == "autoswe/issue-1"


# -- find_existing_pr --

def test_find_existing_pr_found(vcs, mock_ado_request, ado_route_table):
    """find_existing_pr returns PRResult when an active PR exists."""
    fixture = load_ado_fixture("pullrequest_active.json")
    ado_route_table[("GET", "https://dev.azure.com/my-org/my-project/_apis/git/repositories/my-repo/pullrequests")] = fixture

    result = vcs.find_existing_pr("autoswe/issue-100")

    assert result is not None
    assert result.number == 42
    assert result.url == "https://dev.azure.com/my-org/my-project/_git/my-repo/pullrequest/42"

    # Verify query params include sourceRefName and status
    call = mock_ado_request.calls[0]
    assert "sourceRefName=refs/heads/autoswe/issue-100" in call["path"]
    assert "searchCriteria.status=active" in call["path"]


def test_find_existing_pr_none(vcs, mock_ado_request, ado_route_table):
    """find_existing_pr returns None when no active PR exists."""
    ado_route_table[("GET", "https://dev.azure.com/my-org/my-project/_apis/git/repositories/my-repo/pullrequests")] = {
        "count": 0,
        "value": []
    }

    result = vcs.find_existing_pr("autoswe/issue-999")
    assert result is None


# -- open_pull_request --

def test_open_pull_request(vcs, mock_ado_request, ado_route_table):
    """open_pull_request creates a PR and returns PRResult."""
    fixture = load_ado_fixture("pullrequest_created.json")
    ado_route_table[("POST", "https://dev.azure.com/my-org/my-project/_apis/git/repositories/my-repo/pullrequests")] = fixture

    result = vcs.open_pull_request(
        branch="autoswe/issue-101",
        base="main",
        title="Bug: fix crash on empty input",
        body="autoSWE fix for issue #101",
    )

    assert result is not None
    assert result.number == 43
    assert result.url == "https://dev.azure.com/my-org/my-project/_git/my-repo/pullrequest/43"

    # Verify request body
    call = mock_ado_request.calls[0]
    assert call["method"] == "POST"
    assert call["body"]["sourceRefName"] == "refs/heads/autoswe/issue-101"
    assert call["body"]["targetRefName"] == "refs/heads/main"
    assert call["body"]["title"] == "Bug: fix crash on empty input"
    assert call["body"]["description"] == "autoSWE fix for issue #101"


def test_open_pull_request_refs_prefix(vcs, mock_ado_request, ado_route_table):
    """open_pull_request prefixes branch names with refs/heads/."""
    fixture = load_ado_fixture("pullrequest_created.json")
    ado_route_table[("POST", "https://dev.azure.com/my-org/my-project/_apis/git/repositories/my-repo/pullrequests")] = fixture

    vcs.open_pull_request(
        branch="autoswe/issue-101",
        base="develop",
        title="Fix",
        body="body",
    )

    call = mock_ado_request.calls[0]
    assert call["body"]["sourceRefName"] == "refs/heads/autoswe/issue-101"
    assert call["body"]["targetRefName"] == "refs/heads/develop"


# -- open_pull_request: workItemRefs (edge E3) --

def test_open_pull_request_sets_work_item_refs(vcs, mock_ado_request, ado_route_table):
    """open_pull_request writes workItemRefs=[{id}] when an issue is given (edge E3).

    The Azure equivalent of GitHub's closing keyword: a machine-readable
    PR<->work-item link on the create payload.
    """
    fixture = load_ado_fixture("pullrequest_created.json")
    ado_route_table[("POST", "https://dev.azure.com/my-org/my-project/_apis/git/repositories/my-repo/pullrequests")] = fixture

    vcs.open_pull_request(
        branch="autoswe/issue-101",
        base="main",
        title="Fix",
        body="Fixes #101",
        issue_number=101,
    )

    call = mock_ado_request.calls[0]
    assert call["body"]["workItemRefs"] == [{"id": 101}]


def test_open_pull_request_omits_work_item_refs_when_no_issue(vcs, mock_ado_request, ado_route_table):
    """No issue_number means no workItemRefs key — the link edge is simply absent."""
    fixture = load_ado_fixture("pullrequest_created.json")
    ado_route_table[("POST", "https://dev.azure.com/my-org/my-project/_apis/git/repositories/my-repo/pullrequests")] = fixture

    vcs.open_pull_request(
        branch="autoswe/issue-101",
        base="main",
        title="Fix",
        body="body",
    )

    call = mock_ado_request.calls[0]
    assert "workItemRefs" not in call["body"]


# -- get_linkage: reads sourceRef / isMerged / status.mergeStatus (edges E4/E5) --

def _pr_detail(merge_status="succeeded", is_merged=False, source_ref="refs/heads/autoswe/issue-100"):
    """A PR-detail payload as the fake's detail route would serve it."""
    return {
        "pullRequestId": 42,
        "sourceRef": source_ref,
        "isMerged": is_merged,
        "status": {"mergeStatus": merge_status, "isMergeBlocked": False},
    }


def test_get_linkage_no_pr_is_unlinked(vcs, mock_ado_request, ado_route_table):
    """get_linkage(None) reports all edges missing and no PR number."""
    from autoswe.providers.base import Capability
    state = vcs.get_linkage(100, "autoswe/issue-100", None)
    assert state.pr_number is None
    assert state.pr_linked is False
    assert set(state.missing) == {"branch", "closes", "pr_link"}
    assert Capability.BRANCH_LINK not in vcs.capabilities()


def test_get_linkage_merges_merge_status_clean(vcs, mock_ado_request, ado_route_table):
    """status.mergeStatus=succeeded -> merge_state clean, PR detail read once."""
    base = "https://dev.azure.com/my-org/my-project/_apis/git/repositories/my-repo/pullrequests"
    # Workitems route is more specific; register it first so the static mock
    # (which matches by startswith and returns the FIRST hit) does not let the
    # detail prefix ``.../42`` shadow ``.../42/workitems``.
    ado_route_table[("GET", f"{base}/42/workitems")] = {"count": 1, "value": [{"id": "100"}]}
    ado_route_table[("GET", f"{base}/42")] = _pr_detail(merge_status="succeeded")

    state = vcs.get_linkage(100, "autoswe/issue-100", 42)

    assert state.pr_number == 42
    assert state.head_sha == "autoswe/issue-100"  # refs/heads/ stripped
    assert state.merged is False
    assert state.merge_state == "clean"
    assert state.pr_linked is True
    assert "pr_link" not in state.missing


def test_get_linkage_merge_status_conflicts(vcs, mock_ado_request, ado_route_table):
    """status.mergeStatus=conflicts -> merge_state conflicts."""
    base = "https://dev.azure.com/my-org/my-project/_apis/git/repositories/my-repo/pullrequests"
    ado_route_table[("GET", f"{base}/42/workitems")] = {"count": 1, "value": [{"id": "100"}]}
    ado_route_table[("GET", f"{base}/42")] = _pr_detail(merge_status="conflicts")

    state = vcs.get_linkage(100, "autoswe/issue-100", 42)
    assert state.merge_state == "conflicts"


def test_get_linkage_merged_pr_is_clean_and_linked(vcs, mock_ado_request, ado_route_table):
    """isMerged=True reports merged=True and merge_state clean regardless of status."""
    base = "https://dev.azure.com/my-org/my-project/_apis/git/repositories/my-repo/pullrequests"
    ado_route_table[("GET", f"{base}/42/workitems")] = {"count": 1, "value": [{"id": "100"}]}
    ado_route_table[("GET", f"{base}/42")] = _pr_detail(merge_status="queued", is_merged=True)

    state = vcs.get_linkage(100, "autoswe/issue-100", 42)
    assert state.merged is True
    assert state.merge_state == "clean"


def test_get_linkage_unlinked_pr_reports_pr_link_missing(vcs, mock_ado_request, ado_route_table):
    """A PR with no work items linked reports pr_link in missing (edge E3 unmet)."""
    base = "https://dev.azure.com/my-org/my-project/_apis/git/repositories/my-repo/pullrequests"
    ado_route_table[("GET", f"{base}/42/workitems")] = {"count": 0, "value": []}
    ado_route_table[("GET", f"{base}/42")] = _pr_detail(merge_status="succeeded")

    state = vcs.get_linkage(100, "autoswe/issue-100", 42)
    assert state.pr_linked is False
    assert "pr_link" in state.missing


def test_get_linkage_pr_read_failure_reports_all_missing(vcs, mock_ado_request, ado_route_table):
    """If the PR detail read raises, get_linkage degrades to all-edges-missing (no crash)."""
    base = "https://dev.azure.com/my-org/my-project/_apis/git/repositories/my-repo/pullrequests"

    def boom(method, path, pat, body):
        raise RuntimeError("Azure API /pullrequests/42 -> HTTP 500: server error")

    ado_route_table[("GET", f"{base}/42")] = boom

    state = vcs.get_linkage(100, "autoswe/issue-100", 42)
    # A failed detail read yields the unpopulated state: no PR number, not
    # merged, unknown merge state, and every edge reported missing.
    assert state.pr_number is None
    assert state.merged is False
    assert state.merge_state == "unknown"
    assert set(state.missing) == {"branch", "closes", "pr_link"}


# -- link_pr_to_issue: replace-semantics workItemRefs (edge E3) --

def test_link_pr_to_issue_posts_replace_semantics(vcs, mock_ado_request, ado_route_table):
    """link_pr_to_issue reads current refs, adds the id, and POSTs the full list."""
    base = "https://dev.azure.com/my-org/my-project/_apis/git/repositories/my-repo/pullrequests"
    # PR already linked to work item 7; we link it to 100.
    ado_route_table[("GET", f"{base}/42/workitems")] = {"count": 1, "value": [{"id": "7"}]}
    ado_route_table[("POST", f"{base}/42")] = {"pullRequestId": 42}

    vcs.link_pr_to_issue(100, 42)

    post = [c for c in mock_ado_request.calls if c["method"] == "POST"][0]
    # Replace semantics: the full desired list (7 + 100), sorted.
    assert post["body"]["workItemRefs"] == [{"id": 7}, {"id": 100}]


def test_link_pr_to_issue_no_op_when_already_linked(vcs, mock_ado_request, ado_route_table):
    """Already-linked PR: no update POST is issued (idempotent and cheap)."""
    base = "https://dev.azure.com/my-org/my-project/_apis/git/repositories/my-repo/pullrequests"
    ado_route_table[("GET", f"{base}/42/workitems")] = {"count": 1, "value": [{"id": "100"}]}
    ado_route_table[("POST", f"{base}/42")] = {"pullRequestId": 42}

    vcs.link_pr_to_issue(100, 42)

    assert not [c for c in mock_ado_request.calls if c["method"] == "POST"], \
        "link_pr_to_issue must not POST when the id is already present"


def test_link_pr_to_issue_degrades_on_read_failure(vcs, mock_ado_request, ado_route_table):
    """A failed work-items read yields an empty set -> the link is (re)established, no crash."""
    base = "https://dev.azure.com/my-org/my-project/_apis/git/repositories/my-repo/pullrequests"

    def boom(method, path, pat, body):
        raise RuntimeError("Azure API /pullrequests/42/workitems -> HTTP 500")

    ado_route_table[("GET", f"{base}/42/workitems")] = boom
    ado_route_table[("POST", f"{base}/42")] = {"pullRequestId": 42}

    vcs.link_pr_to_issue(100, 42)

    post = [c for c in mock_ado_request.calls if c["method"] == "POST"][0]
    assert post["body"]["workItemRefs"] == [{"id": 100}]


# -- clone_url with partial repo_cfg (worktree.py inline dict pattern) --

def test_clone_url_fallback_owner_slash_repo():
    """AzureVCS falls back to parsing org/project from owner='org/proj' + repo='name'."""
    vcs = AzureVCS({
        "owner": "natedorr/testProject",
        "repo": "testProject",
        "token": "fallback_pat",
        "provider": "azure",
    })
    url = vcs.clone_url()
    assert url == "https://autoswe:fallback_pat@dev.azure.com/natedorr/testProject/_git/testProject"


def test_clone_url_fallback_repo_slash_pattern():
    """AzureVCS falls back to parsing project/repo from repo='project/repo'."""
    vcs = AzureVCS({
        "owner": "natedorr",
        "repo": "testProject/testProject",
        "token": "fallback_pat",
        "provider": "azure",
    })
    url = vcs.clone_url()
    assert url == "https://autoswe:fallback_pat@dev.azure.com/natedorr/testProject/_git/testProject"


def test_clone_url_explicit_fields_take_precedence():
    """Explicit org/project/repo fields are used instead of fallback parsing."""
    cfg = {
        "owner": "ignored/owner",
        "repo": "ignored/repo",
        "org": "my-org",
        "project": "my-project",
        "pat": "explicit_pat",
    }
    cfg["repo"] = "my-repo"
    vcs = AzureVCS(cfg)
    url = vcs.clone_url()
    assert url == "https://autoswe:explicit_pat@dev.azure.com/my-org/my-project/_git/my-repo"


def test_clone_url_pat_falls_back_to_token():
    """AzureVCS uses 'token' field when 'pat' is not present."""
    vcs = AzureVCS({
        "owner": "org",
        "repo": "proj/repo",
        "token": "token_pat",
        "provider": "azure",
    })
    url = vcs.clone_url()
    assert urlparse(url).password == "token_pat"
    assert url == "https://autoswe:token_pat@dev.azure.com/org/proj/_git/repo"


def test_link_branch_to_issue_no_op(vcs):
    """link_branch_to_issue is a no-op for Azure DevOps."""
    # Should not raise, just pass
    vcs.link_branch_to_issue(42, "abc1234", "autoswe/issue-42")


# -- find_existing_pr query params --

def test_find_existing_pr_query_filters_by_branch(vcs, mock_ado_request, ado_route_table):
    """find_existing_pr sends sourceRefName and status=active in query params."""
    fixture = load_ado_fixture("pullrequest_active.json")
    ado_route_table[("GET", "https://dev.azure.com/my-org/my-project/_apis/git/repositories/my-repo/pullrequests")] = fixture

    vcs.find_existing_pr("autoswe/issue-100")

    call = mock_ado_request.calls[0]
    assert "sourceRefName=refs/heads/autoswe/issue-100" in call["path"]
    assert "searchCriteria.status=active" in call["path"]


def test_find_existing_pr_returns_first_active(vcs, mock_ado_request, ado_route_table):
    """find_existing_pr returns the first PR from the filtered result set."""
    # Multiple active PRs matching the same branch (server-side filtered)
    multi_pr = {
        "count": 2,
        "value": [
            {
                "pullRequestId": 42,
                "sourceRefName": "refs/heads/autoswe/issue-100",
                "status": "active",
                "url": "api-url-42",
            },
            {
                "pullRequestId": 43,
                "sourceRefName": "refs/heads/autoswe/issue-100",
                "status": "active",
                "url": "api-url-43",
            },
        ],
    }
    ado_route_table[("GET", "https://dev.azure.com/my-org/my-project/_apis/git/repositories/my-repo/pullrequests")] = multi_pr

    result = vcs.find_existing_pr("autoswe/issue-100")

    assert result is not None
    assert result.number == 42  # Returns first from filtered result


# -- clone_url uses raw org/project --

def test_clone_url_uses_raw_org_project():
    """clone_url uses raw org/project (not URL-encoded) for HTTPS clone.

    URL encoding is applied for API paths, but clone URLs use the raw values
    since the client handles encoding automatically.
    """
    vcs = AzureVCS({
        "org": "my org",
        "project": "my project",
        "repo": "repo",
        "pat": "fake_pat",
    })
    url = vcs.clone_url()
    # clone_url uses raw values, not encoded
    assert "/my org/" in urlparse(url).path
    assert "/my project/" in urlparse(url).path


# -- branch_name consistency --

def test_branch_name_consistent_across_providers():
    """Branch naming convention is consistent between GitHub and Azure."""
    from autoswe.providers.github.vcs import GitHubVCS

    gh_vcs = GitHubVCS({"owner": "o", "repo": "r", "token": "t"})
    az_vcs = AzureVCS({"org": "o", "project": "p", "repo": "r", "pat": "t"})

    for issue_num in [1, 42, 999]:
        assert gh_vcs.branch_name(issue_num) == az_vcs.branch_name(issue_num)
        assert gh_vcs.branch_name(issue_num) == f"autoswe/issue-{issue_num}"


# -- open_pull_request with develop base --

def test_open_pull_request_develop_base(vcs, mock_ado_request, ado_route_table):
    """open_pull_request works with non-main base branch."""
    fixture = load_ado_fixture("pullrequest_created.json")
    ado_route_table[("POST", "https://dev.azure.com/my-org/my-project/_apis/git/repositories/my-repo/pullrequests")] = fixture

    vcs.open_pull_request(
        branch="autoswe/issue-101",
        base="develop",
        title="Fix",
        body="body",
    )

    call = mock_ado_request.calls[0]
    assert call["body"]["targetRefName"] == "refs/heads/develop"


# -- close PR roundtrip: open then close via PATCH (issue #126) --


def test_close_pull_request_uses_patch_not_post(vcs, mock_ado_request, ado_route_table):
    """Closing a PR must be a PATCH to the PR resource, not a POST.

    Mirrors the live/diagnostic flow in tests/test_azure_live.py and
    scripts/test_azure_live.py: open a PR (POST), then set
    ``status: completed`` on the plain-JSON update resource (PATCH). Locks the
    close-step method and body so it cannot silently regress to POST.
    """
    base = "https://dev.azure.com/my-org/my-project/_apis/git/repositories/my-repo"
    created = load_ado_fixture("pullrequest_created.json")
    pr_number = created["pullRequestId"]  # 43

    ado_route_table[("POST", f"{base}/pullrequests")] = created
    ado_route_table[("PATCH", f"{base}/pullrequests/{pr_number}")] = {**created, "status": "completed"}

    # 1. Open the PR (POST create — correct).
    pr = vcs.open_pull_request(
        branch="autoswe/issue-126",
        base="main",
        title="Live test PR",
        body="Test body",
    )
    assert pr.number == pr_number

    # 2. Close it via the plain-JSON update resource (PATCH).
    close_path = _ado_api_version(f"{base}/pullrequests/{pr.number}")
    ado_patch_json(
        close_path,
        "fake_pat_123",
        body={"status": "completed", "completionOptions": {"deleteSourceBranch": False}},
    )

    create_call, close_call = mock_ado_request.calls[0], mock_ado_request.calls[1]
    assert create_call["method"] == "POST"
    # The close step must be PATCH, not POST.
    assert close_call["method"] == "PATCH"
    assert f"/pullrequests/{pr_number}" in close_call["path"]
    assert close_call["body"] == {
        "status": "completed",
        "completionOptions": {"deleteSourceBranch": False},
    }


# -- get_ci_status --

_BUILDS_PREFIX = "https://dev.azure.com/my-org/my-project/_apis/build/builds"


def test_get_ci_status_success(vcs, mock_ado_request, ado_route_table):
    ado_route_table[("GET", _BUILDS_PREFIX)] = {
        "count": 1,
        "value": [{"status": "completed", "result": "succeeded", "definition": {"name": "CI"}}],
    }

    ci = vcs.get_ci_status("autoswe/issue-100")

    assert ci.state == "success"


def test_get_ci_status_pending(vcs, mock_ado_request, ado_route_table):
    ado_route_table[("GET", _BUILDS_PREFIX)] = {
        "count": 1,
        "value": [{"status": "inProgress", "result": None, "definition": {"name": "CI"}}],
    }

    ci = vcs.get_ci_status("autoswe/issue-100")

    assert ci.state == "pending"
    assert ci.pending_count == 1


def test_get_ci_status_failure(vcs, mock_ado_request, ado_route_table):
    ado_route_table[("GET", _BUILDS_PREFIX)] = {
        "count": 1,
        "value": [{"status": "completed", "result": "failed", "definition": {"name": "CI"}}],
    }

    ci = vcs.get_ci_status("autoswe/issue-100")

    assert ci.state == "failure"
    assert ci.failing == ["CI"]


def test_get_ci_status_canceled_is_failure(vcs, mock_ado_request, ado_route_table):
    ado_route_table[("GET", _BUILDS_PREFIX)] = {
        "count": 1,
        "value": [{"status": "completed", "result": "canceled", "definition": {"name": "CI"}}],
    }

    ci = vcs.get_ci_status("autoswe/issue-100")

    assert ci.state == "failure"


def test_get_ci_status_no_builds_is_none(vcs, mock_ado_request, ado_route_table):
    ado_route_table[("GET", _BUILDS_PREFIX)] = {"count": 0, "value": []}

    ci = vcs.get_ci_status("autoswe/issue-100")

    assert ci.state == "none"


def test_get_ci_status_request_error_is_error(vcs, mock_ado_request, ado_route_table):
    """No route stubbed → request raises → error, not a vacuous 'none' pass.

    Fail-safe: the build API could not be consulted, so the result is
    ``state="error"`` — the gate blocks on it rather than shipping blind.
    """
    ci = vcs.get_ci_status("autoswe/issue-100")

    assert ci.state == "error"
    assert "could not query builds" in ci.summary


def test_get_ci_status_success_carries_head_sha_and_url(vcs, mock_ado_request, ado_route_table):
    ado_route_table[("GET", _BUILDS_PREFIX)] = {
        "count": 1,
        "value": [{"status": "completed", "result": "succeeded",
                   "sourceVersion": "ABC1234DEF", "id": 7,
                   "definition": {"name": "CI"}}],
    }

    ci = vcs.get_ci_status("autoswe/issue-100")

    assert ci.state == "success"
    assert ci.head_sha == "ABC1234DEF"
    assert ci.url == "https://dev.azure.com/my-org/my-project/_build/results?buildId=7"


def test_get_ci_status_stale_source_version_is_pending(vcs, mock_ado_request, ado_route_table):
    """Latest build predates the requested commit → stale, not green.

    A build that succeeded on an *older* commit is not evidence the current
    head is green — report pending + stale so the gate waits for a fresh
    build instead of a false green.
    """
    ado_route_table[("GET", _BUILDS_PREFIX)] = {
        "count": 1,
        "value": [{"status": "completed", "result": "succeeded",
                   "sourceVersion": "oldsha", "id": 7,
                   "definition": {"name": "CI"}}],
    }

    ci = vcs.get_ci_status("autoswe/issue-100", ref_sha="newsha")

    assert ci.state == "pending"
    assert ci.stale is True
    assert ci.head_sha == "oldsha"


def test_get_ci_status_stale_canceled_build_no_longer_blocks_as_failure(
    vcs, mock_ado_request, ado_route_table,
):
    """A stale canceled build is pending, not a permanent failure.

    The existing pin (fresh canceled → failure) is preserved; this covers the
    staleness flip: a canceled build for an *older* commit stops blocking the
    gate as a hard failure until a build for the requested head lands.
    """
    ado_route_table[("GET", _BUILDS_PREFIX)] = {
        "count": 1,
        "value": [{"status": "completed", "result": "canceled",
                   "sourceVersion": "oldsha", "id": 7,
                   "definition": {"name": "CI"}}],
    }

    ci = vcs.get_ci_status("autoswe/issue-100", ref_sha="newsha")

    assert ci.state == "pending"
    assert ci.stale is True


@pytest.mark.parametrize(
    "ref_sha",
    ["newsha", "NEWsha"],
    ids=["exact-case", "mixed-case"],
)
def test_get_ci_status_fresh_source_version_is_not_stale(
    vcs, mock_ado_request, ado_route_table, ref_sha,
):
    """A build on the *requested* commit is fresh, not stale.

    The staleness comparison is case-insensitive, so both an exact-case match
    and a mixed-case match on the same build read as a fresh verdict — the
    build's real result, not a pending/stale stand-in. This pins the match arm
    of the ``source_version.lower() != str(ref_sha).lower()`` comparison that
    the mismatch rows above only exercise in the other direction.
    """
    ado_route_table[("GET", _BUILDS_PREFIX)] = {
        "count": 1,
        "value": [{"status": "completed", "result": "succeeded",
                   "sourceVersion": "newsha", "id": 7,
                   "definition": {"name": "CI"}}],
    }

    ci = vcs.get_ci_status("autoswe/issue-100", ref_sha=ref_sha)

    assert ci.state == "success"
    assert ci.stale is False
    assert ci.head_sha == "newsha"


def test_get_ci_status_no_ref_sha_no_staleness_claim(vcs, mock_ado_request, ado_route_table):
    """Without ref_sha the provider can't claim staleness — fresh verdicts."""
    ado_route_table[("GET", _BUILDS_PREFIX)] = {
        "count": 1,
        "value": [{"status": "completed", "result": "succeeded",
                   "sourceVersion": "whatever", "id": 7,
                   "definition": {"name": "CI"}}],
    }

    ci = vcs.get_ci_status("autoswe/issue-100")

    assert ci.state == "success"
    assert ci.stale is False


def test_get_ci_status_source_version_missing_no_staleness_claim(
    vcs, mock_ado_request, ado_route_table,
):
    """Older pipelines omit sourceVersion → no staleness claim even with ref_sha."""
    ado_route_table[("GET", _BUILDS_PREFIX)] = {
        "count": 1,
        "value": [{"status": "completed", "result": "succeeded",
                   "id": 7, "definition": {"name": "CI"}}],
    }

    ci = vcs.get_ci_status("autoswe/issue-100", ref_sha="newsha")

    assert ci.state == "success"
    assert ci.stale is False
    assert ci.head_sha is None


# -- Stateful round-trip (pins the AzureFake workItemRefs change, edge E3) --

def test_azure_fake_round_trips_work_item_refs(azure_fake, monkeypatch):
    """The fake must round-trip workItemRefs so get_linkage sees the real link.

    ADO persists workItemRefs on PR create and exposes them via the
    ``.../pullrequests/{id}/workitems`` read endpoint. This test drives the
    *real* AzureVCS against the stateful fake and pins that behaviour, so the
    fake cannot silently stop reflecting the create-time link (which would
    make an already-linked PR look unlinked and force a redundant re-link).
    """
    import autoswe.providers.azure.api as ado_module
    azure_fake.load({
        "org": "testorg", "project": "testproj", "repo": "testrepo",
    })
    monkeypatch.setattr(ado_module, "_ado_request", azure_fake.handle_request)
    vcs = AzureVCS({
        "provider": "azure", "org": "testorg", "project": "testproj",
        "repo": "testrepo", "pat": "pat",
    })

    # 1. Create a PR WITH the work-item link -> the fake stores it.
    pr = vcs.open_pull_request(
        "autoswe/issue-42", "main", "Fixes #42", "Fixes #42", issue_number=42,
    )
    state = vcs.get_linkage(42, "autoswe/issue-42", pr.number)
    assert state.pr_linked is True, "create-time workItemRefs must be reflected by get_linkage"
    assert "pr_link" not in state.missing
    assert state.merged is False
    assert state.merge_state == "clean"


def test_azure_fake_unlinked_pr_self_heals_with_one_update(azure_fake, monkeypatch):
    """A PR created without refs looks unlinked; the heal is a single update.

    Pins the read-back + replace-semantics path: get_linkage reports the edge
    missing, then link_pr_to_issue issues exactly one update that carries the
    full desired ref list, after which get_linkage reports it linked.
    """
    import autoswe.providers.azure.api as ado_module
    azure_fake.load({
        "org": "testorg", "project": "testproj", "repo": "testrepo",
    })
    monkeypatch.setattr(ado_module, "_ado_request", azure_fake.handle_request)
    vcs = AzureVCS({
        "provider": "azure", "org": "testorg", "project": "testproj",
        "repo": "testrepo", "pat": "pat",
    })

    pr = vcs.open_pull_request("autoswe/issue-43", "main", "t", "body")

    # 2. No issue passed -> PR is unlinked; get_linkage reports pr_link missing.
    state = vcs.get_linkage(43, "autoswe/issue-43", pr.number)
    assert state.pr_linked is False
    assert "pr_link" in state.missing

    # 3. Heal: exactly one update POST, carrying the full ref list (replace).
    calls_before = len(azure_fake.recorded_calls)
    vcs.link_pr_to_issue(43, pr.number)
    updates = [
        c for c in azure_fake.recorded_calls[calls_before:]
        if c["method"] == "POST" and f"/pullrequests/{pr.number}?" in c["path"]
    ]
    assert len(updates) == 1, f"expected exactly one update POST, got {len(updates)}"
    assert updates[0]["body"]["workItemRefs"] == [{"id": 43}]

    # 4. The read-back now reports the edge as established.
    state = vcs.get_linkage(43, "autoswe/issue-43", pr.number)
    assert state.pr_linked is True
    assert "pr_link" not in state.missing
