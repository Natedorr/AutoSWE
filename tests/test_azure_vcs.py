"""Tests for autoswe.providers.azure.vcs — Azure DevOps VCSProvider."""
import pytest

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
    url = vcs.clone_url({})
    assert url == "https://autoswe:fake_pat_123@dev.azure.com/my-org/my-project/_git/my-repo"


def test_clone_url_contains_pat(vcs):
    url = vcs.clone_url({})
    assert "fake_pat_123" in url
    assert "dev.azure.com" in url


# -- branch_name --

def test_branch_name(vcs):
    assert vcs.branch_name(100) == "autoswe/issue-100"
    assert vcs.branch_name(1) == "autoswe/issue-1"


# -- find_existing_pr --

def test_find_existing_pr_found(vcs, mock_ado_request, ado_route_table):
    """find_existing_pr returns PRResult when an active PR exists."""
    fixture = load_ado_fixture("pullrequest_active.json")
    ado_route_table[("GET", "https://dev.azure.com/my-org/my-project/_apis/git/repositories/my-repo/pullrequests")] = fixture

    result = vcs.find_existing_pr({}, "autoswe/issue-100")

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

    result = vcs.find_existing_pr({}, "autoswe/issue-999")
    assert result is None


# -- open_pull_request --

def test_open_pull_request(vcs, mock_ado_request, ado_route_table):
    """open_pull_request creates a PR and returns PRResult."""
    fixture = load_ado_fixture("pullrequest_created.json")
    ado_route_table[("POST", "https://dev.azure.com/my-org/my-project/_apis/git/repositories/my-repo/pullrequests")] = fixture

    result = vcs.open_pull_request(
        {},
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
        {},
        branch="autoswe/issue-101",
        base="develop",
        title="Fix",
        body="body",
    )

    call = mock_ado_request.calls[0]
    assert call["body"]["sourceRefName"] == "refs/heads/autoswe/issue-101"
    assert call["body"]["targetRefName"] == "refs/heads/develop"


# -- clone_url with partial repo_cfg (worktree.py inline dict pattern) --

def test_clone_url_fallback_owner_slash_repo():
    """AzureVCS falls back to parsing org/project from owner='org/proj' + repo='name'."""
    vcs = AzureVCS({
        "owner": "natedorr/testProject",
        "repo": "testProject",
        "token": "fallback_pat",
        "provider": "azure",
    })
    url = vcs.clone_url({})
    assert url == "https://autoswe:fallback_pat@dev.azure.com/natedorr/testProject/_git/testProject"


def test_clone_url_fallback_repo_slash_pattern():
    """AzureVCS falls back to parsing project/repo from repo='project/repo'."""
    vcs = AzureVCS({
        "owner": "natedorr",
        "repo": "testProject/testProject",
        "token": "fallback_pat",
        "provider": "azure",
    })
    url = vcs.clone_url({})
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
    url = vcs.clone_url({})
    assert url == "https://autoswe:explicit_pat@dev.azure.com/my-org/my-project/_git/my-repo"


def test_clone_url_pat_falls_back_to_token():
    """AzureVCS uses 'token' field when 'pat' is not present."""
    vcs = AzureVCS({
        "owner": "org",
        "repo": "proj/repo",
        "token": "token_pat",
        "provider": "azure",
    })
    url = vcs.clone_url({})
    assert "token_pat" in url
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

    vcs.find_existing_pr({}, "autoswe/issue-100")

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

    result = vcs.find_existing_pr({}, "autoswe/issue-100")

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
    url = vcs.clone_url({})
    # clone_url uses raw values, not encoded
    assert "my org" in url
    assert "my project" in url


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
        {},
        branch="autoswe/issue-101",
        base="develop",
        title="Fix",
        body="body",
    )

    call = mock_ado_request.calls[0]
    assert call["body"]["targetRefName"] == "refs/heads/develop"
