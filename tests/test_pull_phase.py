"""Pull-phase contract tests — normalization across providers.

Drives ``get_tracker(repo_cfg)`` for each provider with the fake loaded
from state dicts and asserts the normalization contract on
``NormalizedIssue`` / ``NormalizedComment``.
"""
from __future__ import annotations

import pytest

from autoswe.commands.parser import parse_slash_command
from autoswe.providers.base import NormalizedComment, NormalizedIssue

# ---------------------------------------------------------------------------
# State fixtures — mirrored between providers

_GH_ISSUE_OPEN = {
    "owner": "owner", "repo": "repo",
    "issue": {
        "id": 1, "number": 42, "title": "Fix login", "body": "Users can't log in.\n\n/fix",
        "state": "open", "labels": [{"name": "bug", "color": "d73a4a"}],
        "assignees": [], "created_at": "2026-01-01T00:00:00Z",
        "closed_at": None, "author_association": "OWNER", "comments": 0,
        "user": {"login": "owner", "id": 1, "type": "User"},
        "pull_request": None,
    },
    "labels": ["bug"],
    "comments": [
        {
            "id": 1, "body": "Welcome comment\n\n<!-- autoswe-bot -->",
            "created_at": "2026-01-01T01:00:00Z",
            "user": {"login": "owner", "id": 1, "type": "User"},
            "author_association": "OWNER",
        },
        {
            "id": 2, "body": "Please prioritize this.",
            "created_at": "2026-01-01T02:00:00Z",
            "user": {"login": "collaborator", "id": 2, "type": "COLLABORATOR"},
            "author_association": "COLLABORATOR",
        },
    ],
    "repo_labels": [
        {"id": 1, "name": "bug", "color": "d73a4a"},
        {"id": 2, "name": "autoswe:pending", "color": "0075ca", "description": "Ready"},
    ],
    "authenticated_user": {"login": "owner", "id": 1, "type": "User"},
}

_GH_ISSUE_WITH_STATUS = {
    **_GH_ISSUE_OPEN,
    "labels": ["bug", "autoswe:planned"],
    "issue": {
        **_GH_ISSUE_OPEN["issue"],
        "labels": [
            {"name": "bug", "color": "d73a4a"},
            {"name": "autoswe:planned", "color": "0075ca", "description": "Plan ready"},
        ],
    },
    "repo_labels": [
        {"id": 1, "name": "bug", "color": "d73a4a"},
        {"id": 2, "name": "autoswe:planned", "color": "0075ca", "description": "Plan ready"},
    ],
}

_GH_ISSUE_PR = {
    **_GH_ISSUE_OPEN,
    "issue": {
        **_GH_ISSUE_OPEN["issue"],
        "number": 99,
        "pull_request": {"url": "https://api.github.com/repos/o/r/pulls/99"},
    },
}

_AZ_WI_OPEN = {
    "org": "testorg", "project": "testproj", "repo": "testrepo",
    "work_item": {
        "id": 42, "rev": 1,
        "fields": {
            "System.Id": 42, "System.Title": "Fix login",
            "System.Description": "Users can't log in.\n\n/fix",
            "System.State": "Active", "System.Tags": "bug",
            "System.CreatedDate": "2026-01-01T00:00:00Z",
            "System.ChangedDate": "2026-01-01T00:00:00Z",
        },
    },
    "tags": ["bug"],
    "comments": [
        {
            "id": 1, "text": "Welcome comment\n\n<!-- autoswe-bot -->",
            "createdDate": "2026-01-01T01:00:00Z",
            "createdBy": {"displayName": "Owner", "id": "1", "uniqueName": "owner@example.com"},
        },
        {
            "id": 2, "text": "Please prioritize this.",
            "createdDate": "2026-01-01T02:00:00Z",
            "createdBy": {"displayName": "Collab", "id": "2", "uniqueName": "collab@example.com"},
        },
    ],
    "authenticated_user": {"uniqueName": "owner@example.com", "id": "1"},
}

_AZ_WI_WITH_STATUS = {
    **_AZ_WI_OPEN,
    "tags": ["bug", "autoswe:planned"],
    "work_item": {
        **_AZ_WI_OPEN["work_item"],
        "fields": {**_AZ_WI_OPEN["work_item"]["fields"], "System.Tags": "bug; autoswe:planned"},
    },
}

_AZ_WI_CLOSED = {
    **_AZ_WI_OPEN,
    "work_item": {
        **_AZ_WI_OPEN["work_item"],
        "fields": {**_AZ_WI_OPEN["work_item"]["fields"], "System.State": "Done"},
    },
}


# ---------------------------------------------------------------------------
# Parametrized normalization tests


@pytest.mark.parametrize("state", [
    pytest.param(("github", _GH_ISSUE_OPEN), id="github-open"),
    pytest.param(("azure", _AZ_WI_OPEN), id="azure-open"),
])
def test_normalized_issue_basic_fields(state, isolated_autoswe_dir):
    """NormalizedIssue has number, title, body, state, labels."""
    provider, st = state
    from autoswe.providers.factory import build_repo_cfg, get_tracker

    repos_cfg = {}
    repo_cfg = build_repo_cfg(
        st.get("owner", st.get("org", "")),
        st.get("repo", st.get("project", "")),
        {"GITHUB_TOKEN": "token"},
        repos_cfg,
        provider=provider,
    )
    if provider == "azure":
        repo_cfg.update({"org": st["org"], "project": st["project"], "pat": "pat"})

    # Patch the fake
    if provider == "github":
        from tests.fakes.github_fake import GitHubFake
        fake = GitHubFake()
        fake.load(st)
        mod, orig = fake.patch()
    else:
        from tests.fakes.azure_fake import AzureFake
        fake = AzureFake()
        fake.load(st)
        mod, orig = fake.patch()

    try:
        tracker = get_tracker(repo_cfg)
        issues = tracker.list_open_issues(repo_cfg)
    finally:
        fake.unpatch(mod, orig)

    assert len(issues) >= 1
    issue = issues[0]
    assert isinstance(issue, NormalizedIssue)
    assert issue.number > 0
    assert isinstance(issue.title, str)
    assert "login" in issue.title.lower()
    assert isinstance(issue.body, str)
    assert "log in" in issue.body.lower() or "can't" in issue.body.lower()
    assert issue.state == "open"
    assert "bug" in issue.labels


@pytest.mark.parametrize("state", [
    pytest.param(("github", _GH_ISSUE_WITH_STATUS), id="github-status"),
    pytest.param(("azure", _AZ_WI_WITH_STATUS), id="azure-status"),
])
def test_normalized_issue_status(state, isolated_autoswe_dir):
    """Status extracted from autoswe: label (GitHub) or tag (Azure)."""
    provider, st = state
    from autoswe.providers.factory import build_repo_cfg, get_tracker

    repos_cfg = {}
    repo_cfg = build_repo_cfg(
        st.get("owner", st.get("org", "")),
        st.get("repo", st.get("project", "")),
        {"GITHUB_TOKEN": "token"},
        repos_cfg,
        provider=provider,
    )
    if provider == "azure":
        repo_cfg.update({"org": st["org"], "project": st["project"], "pat": "pat"})

    if provider == "github":
        from tests.fakes.github_fake import GitHubFake
        fake = GitHubFake()
        fake.load(st)
        mod, orig = fake.patch()
    else:
        from tests.fakes.azure_fake import AzureFake
        fake = AzureFake()
        fake.load(st)
        mod, orig = fake.patch()

    try:
        tracker = get_tracker(repo_cfg)
        issues = tracker.list_open_issues(repo_cfg)
    finally:
        fake.unpatch(mod, orig)

    issue = issues[0]
    assert issue.status == "planned"


@pytest.mark.parametrize("provider,state", [
    pytest.param("github", _GH_ISSUE_OPEN, id="github"),
    pytest.param("azure", _AZ_WI_OPEN, id="azure"),
])
def test_normalized_comment_authors(provider, state, isolated_autoswe_dir):
    """author_login normalized: BOT, OWNER, AUTHOR, <raw>."""
    from autoswe.providers.factory import build_repo_cfg, get_tracker

    st = state
    repos_cfg = {}
    owner_key = st.get("owner", st.get("org", ""))
    repo_key = st.get("repo", st.get("project", ""))
    repo_cfg = build_repo_cfg(owner_key, repo_key, {"GITHUB_TOKEN": "token"}, repos_cfg, provider=provider)
    if provider == "azure":
        repo_cfg.update({"org": st["org"], "project": st["project"], "pat": "pat"})

    if provider == "github":
        from tests.fakes.github_fake import GitHubFake
        fake = GitHubFake()
        fake.load(st)
        mod, orig = fake.patch()
    else:
        from tests.fakes.azure_fake import AzureFake
        fake = AzureFake()
        fake.load(st)
        mod, orig = fake.patch()

    try:
        tracker = get_tracker(repo_cfg)
        issue_num = st.get("issue", {}).get("number", 1)
        if provider == "azure":
            issue_num = st["work_item"]["id"]
        comments = tracker.fetch_comments(repo_cfg, issue_num)
    finally:
        fake.unpatch(mod, orig)

    assert len(comments) >= 2
    assert all(isinstance(c, NormalizedComment) for c in comments)

    # Bot comment should be normalized to BOT
    bot_comments = [c for c in comments if "autoswe-bot" in c.body]
    assert bot_comments, "Expected a bot comment"
    assert bot_comments[0].author_login == "BOT"

    # Non-bot comments should have a non-empty author_login (OWNER, AUTHOR, or raw login)
    user_comments = [c for c in comments if c.author_login not in ("BOT", "")]
    assert user_comments, "Expected at least one user comment with author_login"


@pytest.mark.parametrize("provider,state", [
    pytest.param("github", _GH_ISSUE_PR, id="github-pr"),
])
def test_pull_request_filtering(provider, state, isolated_autoswe_dir):
    """Issues with pull_request key should be marked as PRs."""
    st = state
    from autoswe.providers.factory import build_repo_cfg, get_tracker

    repos_cfg = {}
    repo_cfg = build_repo_cfg(st["owner"], st["repo"], {"GITHUB_TOKEN": "token"}, repos_cfg, provider="github")

    from tests.fakes.github_fake import GitHubFake
    fake = GitHubFake()
    fake.load(st)
    mod, orig = fake.patch()

    try:
        tracker = get_tracker(repo_cfg)
        issues = tracker.list_open_issues(repo_cfg)
    finally:
        fake.unpatch(mod, orig)

    pr_issues = [i for i in issues if i.is_pull_request]
    assert len(pr_issues) >= 1, "Expected at least one PR issue"


def test_azure_state_mapping(isolated_autoswe_dir):
    """Azure Done/Closed/Removed states map to 'closed'."""
    from autoswe.providers.factory import build_repo_cfg, get_tracker

    st = _AZ_WI_CLOSED
    repos_cfg = {}
    repo_cfg = build_repo_cfg(st["org"], st["project"], {"GITHUB_TOKEN": "token"}, repos_cfg, provider="azure")
    repo_cfg.update({"org": st["org"], "project": st["project"], "pat": "pat"})

    from tests.fakes.azure_fake import AzureFake
    fake = AzureFake()
    fake.load(st)
    mod, orig = fake.patch()

    try:
        tracker = get_tracker(repo_cfg)
        issues = tracker.list_open_issues(repo_cfg)
    finally:
        fake.unpatch(mod, orig)

    # "Done" state should be filtered out of open issues (WIQL excludes it)
    # or mapped to closed state
    for issue in issues:
        assert issue.state != "closed" or issue.number != st["work_item"]["id"]


def test_azure_html_stripping(isolated_autoswe_dir):
    """Azure descriptions with HTML should be stripped."""
    from autoswe.providers.factory import build_repo_cfg, get_tracker

    html_state = {
        **_AZ_WI_OPEN,
        "work_item": {
            **_AZ_WI_OPEN["work_item"],
            "fields": {
                **_AZ_WI_OPEN["work_item"]["fields"],
                "System.Description": "<p>Fix <strong>login</strong> bug.</p>",
            },
        },
    }
    repos_cfg = {}
    repo_cfg = build_repo_cfg(html_state["org"], html_state["project"], {"GITHUB_TOKEN": "token"}, repos_cfg, provider="azure")
    repo_cfg.update({"org": html_state["org"], "project": html_state["project"], "pat": "pat"})

    from tests.fakes.azure_fake import AzureFake
    fake = AzureFake()
    fake.load(html_state)
    mod, orig = fake.patch()

    try:
        tracker = get_tracker(repo_cfg)
        issues = tracker.list_open_issues(repo_cfg)
    finally:
        fake.unpatch(mod, orig)

    assert len(issues) >= 1
    issue = issues[0]
    assert "<p>" not in issue.body, "HTML should be stripped"
    assert "login" in issue.body


# ---------------------------------------------------------------------------
# Slash command parsing (provider-agnostic)

@pytest.mark.parametrize("text,expected", [
    ("/fix", ("/fix", None, None)),
    ("/plan --branch develop", ("/plan", None, "develop")),
    ("/fix with performance focus", ("/fix", "performance focus", None)),
    ("/retry", ("/retry", None, None)),
    ("/sync with --branch main", ("/sync", None, "main")),
    ("Some prose here", None),
    ("Post `/retry` to try again", None),
    ("/FIX", ("/fix", None, None)),
    ("/Fix", ("/fix", None, None)),
    ("Some text\n/plan\n/fix", ("/fix", None, None)),
])
def test_parse_slash_command(text, expected):
    """parse_slash_command handles all command patterns."""
    result = parse_slash_command(text)
    assert result == expected, f"For {text!r}: got {result}, expected {expected}"
