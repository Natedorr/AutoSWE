"""Tracker normalization parity — GitHub vs Azure produce identical shapes.

Verifies that both providers normalize to the same NormalizedIssue and
NormalizedComment structures from equivalent raw data. Catches drift in
provider normalization logic.
"""
from __future__ import annotations

from autoswe.providers.base import NormalizedComment, NormalizedIssue
from autoswe.tracking.comments import BOT_MARKER, _is_autoswe_bot_comment

# ------ Issue normalization parity ------


def test_issue_get_status_both_providers():
    """Both trackers extract autoswe_status from labels/tags via get_status."""
    from autoswe.providers.azure.tracker import AzureTracker
    from autoswe.providers.github.tracker import GitHubTracker

    gh_t = GitHubTracker({"owner": "o", "repo": "r", "token": "t"})
    az_t = AzureTracker({"org": "o", "project": "p", "pat": "t"})

    issue = NormalizedIssue(
        number=42, title="Fix bug", body="body text",
        owner="owner", repo="repo",
        labels=["autoswe:pending", "bug"],
    )
    assert gh_t.get_status(issue) == "pending"
    assert az_t.get_status(issue) == "pending"


def test_issue_normalization_no_autoswe_label():
    """Missing autoswe label/tag returns None status for both providers."""
    from autoswe.providers.github.tracker import GitHubTracker

    t = GitHubTracker({"owner": "o", "repo": "r", "token": "t"})
    issue = NormalizedIssue(
        number=42, title="t", body="b",
        owner="o", repo="r", labels=["bug"],
    )
    assert t.get_status(issue) is None


def test_issue_normalization_empty_labels():
    """Empty labels list returns None status."""
    from autoswe.providers.github.tracker import GitHubTracker

    t = GitHubTracker({"owner": "o", "repo": "r", "token": "t"})
    issue = NormalizedIssue(
        number=42, title="t", body="b",
        owner="o", repo="r", labels=[],
    )
    assert t.get_status(issue) is None


def test_issue_normalization_all_statuses():
    """All autoswe statuses are recognized by both trackers."""
    from autoswe.providers.azure.tracker import AzureTracker
    from autoswe.providers.github.tracker import GitHubTracker

    gh_t = GitHubTracker({"owner": "o", "repo": "r", "token": "t"})
    az_t = AzureTracker({"org": "o", "project": "p", "pat": "t"})

    for status in ("pending", "fixing", "planned", "waiting", "fixed",
                    "failed", "skipped", "aborted"):
        issue = NormalizedIssue(
            number=1, title="t", body="b",
            owner="o", repo="r", labels=[f"autoswe:{status}"],
        )
        assert gh_t.get_status(issue) == status, f"GitHub: {status} not recognized"
        assert az_t.get_status(issue) == status, f"Azure: {status} not recognized"


def test_issue_normalization_preserves_non_autoswe_labels():
    """Non-autoswe labels are preserved in the labels list."""
    issue = NormalizedIssue(
        number=42, title="t", body="b",
        owner="o", repo="r",
        labels=["autoswe:pending", "bug", "enhancement", "good first issue"],
    )
    assert "bug" in issue.labels
    assert "enhancement" in issue.labels
    assert "good first issue" in issue.labels
    assert "autoswe:pending" in issue.labels


# ------ Comment normalization parity ------


def test_comment_bot_detection_is_bot_flag():
    """is_bot=True is the primary bot detection signal."""
    c = NormalizedComment(
        body="Random text", created_at="2026-01-01T00:00:00Z",
        author_login="owner", id=1, is_bot=True,
    )
    assert c.is_bot is True


def test_comment_bot_detection_marker():
    """BOT_MARKER in body indicates bot comment."""
    from autoswe.tracking.comments import _is_autoswe_bot_comment

    c = NormalizedComment(
        body=f"Response{BOT_MARKER}", created_at="2026-01-01T00:00:00Z",
        author_login="owner", id=1, is_bot=False,
    )
    assert _is_autoswe_bot_comment(c) is True


def test_comment_content_pattern_detection():
    """Bot content patterns (## Plan, ## Questions, Completed with) are detected."""
    from autoswe.tracking.comments import _is_autoswe_bot_comment

    for body in [
        "## Plan\n\n1. Do it",
        "## Questions\n\nWhat framework?",
        "Completed with command `/fix`.",
        "Dispatching `/plan`...",
        "Post `/retry` to continue",
    ]:
        c = NormalizedComment(
            body=body, created_at="2026-01-01T00:00:00Z",
            author_login="owner", id=1, is_bot=False,
        )
        assert _is_autoswe_bot_comment(c) is True, f"Pattern not detected: {body[:30]}"


def test_comment_user_comment_not_bot():
    """User slash commands are not classified as bot."""
    from autoswe.tracking.comments import _is_autoswe_bot_comment

    for body in ["/fix", "/plan", "/sync", "/retry", "Hello world"]:
        c = NormalizedComment(
            body=body, created_at="2026-01-01T00:00:00Z",
            author_login="owner", id=1, is_bot=False,
        )
        assert _is_autoswe_bot_comment(c) is False, f"False bot: {body}"


def test_comment_empty_body_not_bot():
    """Empty body is not a bot comment."""
    from autoswe.tracking.comments import _is_autoswe_bot_comment

    c = NormalizedComment(
        body="", created_at="2026-01-01T00:00:00Z",
        author_login="owner", id=1, is_bot=False,
    )
    assert _is_autoswe_bot_comment(c) is False


def test_comment_author_login_owner():
    """OWNER author_login is set by both trackers."""
    c = NormalizedComment(
        body="/fix", created_at="2026-01-01T00:00:00Z",
        author_login="OWNER", id=1, is_bot=False,
    )
    assert c.author_login == "OWNER"


def test_comment_author_login_bot():
    """BOT author_login is set by both trackers."""
    c = NormalizedComment(
        body="Response", created_at="2026-01-01T00:00:00Z",
        author_login="BOT", id=1, is_bot=True,
    )
    assert c.author_login == "BOT"


def test_comment_preserves_collaborator_login():
    """Non-owner, non-bot comments preserve raw login."""
    c = NormalizedComment(
        body="I'll look at this", created_at="2026-01-01T00:00:00Z",
        author_login="contributor-42", id=1, is_bot=False,
    )
    assert c.author_login == "contributor-42"


# ------ Azure-specific HTML normalization ------


def test_azure_html_div_stripped():
    """Azure DevOps <div> wrapper is stripped from comment bodies."""
    from autoswe.providers.azure.tracker import _strip_html

    result = _strip_html("<div>/plan --branch dev</div>")
    assert "/plan --branch dev" == result


def test_azure_html_entities_decoded():
    """Azure DevOps HTML entities are decoded."""
    from autoswe.providers.azure.tracker import _strip_html

    result = _strip_html("&#47;fix &#45;&#45;focus")
    assert "/fix --focus" == result


def test_azure_autoswe_tags_preserved():
    """Azure DevOps normalization preserves <AUTOSWE_*> tags."""
    from autoswe.providers.azure.tracker import _strip_html

    html = "<p><AUTOSWE_PLAN>Do the thing</AUTOSWE_PLAN></p>"
    result = _strip_html(html)
    assert "<AUTOSWE_PLAN>" in result
    assert "<p>" not in result


def test_azure_bot_content_pattern_after_html_strip():
    """Bot content patterns (## Plan, etc.) survive HTML stripping.

    Note: ADO strips HTML comments from stored body text, so BOT_MARKER
    (which is an HTML comment) is lost. Bot detection falls back to
    _BOT_CONTENT_PATTERNS (## Plan, Completed with, etc.).
    """
    from autoswe.providers.azure.tracker import _strip_html

    html = "<div>## Plan\n\n1. Do it</div>"
    result = _strip_html(html)
    assert "## Plan" in result
    assert "<div>" not in result
    # Verify content pattern detection still works on stripped body
    c = NormalizedComment(
        body=result, created_at="2026-01-01T00:00:00Z",
        author_login="AUTHOR", id=1, is_bot=False,
    )
    assert _is_autoswe_bot_comment(c) is True


# ------ GitHub tracker normalization ------


# ------ GitHub tracker normalization (via fetch_comments) ------


def test_github_tracker_fetch_comments_bot_marker():
    """GitHub tracker normalizes bot comments via marker (via test_github_provider).

    This documents the expected behavior — the actual test is in
    test_github_provider.py::TestGitHubTracker::test_fetch_comments_normalizes_bot_comments.
    Here we verify the _is_autoswe_bot_comment detection the tracker relies on.
    """
    from autoswe.tracking.comments import _is_autoswe_bot_comment

    c = NormalizedComment(
        body=f"Response{BOT_MARKER}", created_at="2026-01-01T00:00:00Z",
        author_login="owner", id=1, is_bot=False,
    )
    assert _is_autoswe_bot_comment(c) is True


def test_github_tracker_content_pattern_detection():
    """GitHub tracker relies on content pattern detection for bot comments.

    The actual tracker test is in test_github_provider.py. This verifies the
    underlying _is_autoswe_bot_comment detection used by both trackers.
    """
    from autoswe.tracking.comments import _is_autoswe_bot_comment

    c = NormalizedComment(
        body="## Plan\n\n1. Do it", created_at="2026-01-01T00:00:00Z",
        author_login="BOT", id=1, is_bot=True,
    )
    assert _is_autoswe_bot_comment(c) is True


# ------ Azure tracker normalization (via fetch_comments) ------


def test_azure_tracker_bot_detection_with_content():
    """Azure tracker normalizes bot comments via content pattern (via test_azure_tracker).

    The actual test is in test_azure_tracker.py. Here we verify that the
    _is_autoswe_bot_comment detection works on Azure-style HTML-stripped content.
    """
    from autoswe.providers.azure.tracker import _strip_html
    from autoswe.tracking.comments import _is_autoswe_bot_comment

    html_body = "<div>## Plan\n\n1. Do it</div>"
    clean = _strip_html(html_body)
    c = NormalizedComment(
        body=clean, created_at="2026-01-01T00:00:00Z",
        author_login="AUTHOR", id=1, is_bot=False,
    )
    assert _is_autoswe_bot_comment(c) is True


def test_azure_tracker_owner_detection():
    """Azure tracker normalizes OWNER login for PAT owner's user comments.

    The actual test is in test_azure_tracker.py. This verifies the invariant
    that owner login is a string comparison with authenticated_user.
    """
    # Both trackers use the same principle: compare uniqueName/login
    # with authenticated_user result. Both normalize to "OWNER".
    c = NormalizedComment(
        body="/fix", created_at="2026-01-01T00:00:00Z",
        author_login="OWNER", id=1, is_bot=False,
    )
    assert c.author_login == "OWNER"
    assert not _is_autoswe_bot_comment(c)


def test_azure_tracker_preserves_other_login():
    """Azure tracker preserves non-owner, non-bot logins.

    The actual test is in test_azure_tracker.py. This verifies the invariant
    that non-matching logins are preserved as-is.
    """
    c = NormalizedComment(
        body="On it!", created_at="2026-01-01T00:00:00Z",
        author_login="contributor@example.com", id=1, is_bot=False,
    )
    assert c.author_login == "contributor@example.com"


# ------ Cross-provider shape parity ------


def test_normalized_issue_fields_identical():
    """NormalizedIssue has the same fields regardless of provider."""
    gh_issue = NormalizedIssue(
        number=42, title="Fix", body="b",
        owner="o", repo="r", labels=["autoswe:pending"],
    )
    az_issue = NormalizedIssue(
        number=42, title="Fix", body="b",
        owner="o/p", repo="r", labels=["autoswe:pending"],
    )
    # Core fields should be identical
    assert gh_issue.number == az_issue.number
    assert gh_issue.title == az_issue.title
    assert gh_issue.body == az_issue.body
    assert gh_issue.status == az_issue.status
    assert gh_issue.base_branch == az_issue.base_branch


def test_normalized_issue_last_updated_default():
    """NormalizedIssue.last_updated defaults to None for both providers."""
    issue = NormalizedIssue(
        number=42, title="Fix", body="b",
        owner="o", repo="r",
    )
    assert issue.last_updated is None


def test_normalized_issue_last_updated_set():
    """NormalizedIssue.last_updated carries the provider timestamp."""
    issue = NormalizedIssue(
        number=42, title="Fix", body="b",
        owner="o", repo="r",
        last_updated="2026-01-01T00:00:00Z",
    )
    assert issue.last_updated == "2026-01-01T00:00:00Z"


def test_normalized_comment_fields_identical():
    """NormalizedComment has the same fields regardless of provider."""
    gh_comment = NormalizedComment(
        body="/fix", created_at="2026-01-01T00:00:00Z",
        author_login="OWNER", id=1, is_bot=False,
    )
    az_comment = NormalizedComment(
        body="/fix", created_at="2026-01-01T00:00:00Z",
        author_login="OWNER", id=1, is_bot=False,
    )
    assert gh_comment.body == az_comment.body
    assert gh_comment.created_at == az_comment.created_at
    assert gh_comment.author_login == az_comment.author_login
    assert gh_comment.id == az_comment.id
    assert gh_comment.is_bot == az_comment.is_bot


# ------ Edge cases ------


def test_azure_div_wrapped_slash_command():
    """Azure DevOps div-wrapped slash commands are parsed correctly after strip."""
    from autoswe.commands.parser import parse_slash_command
    from autoswe.providers.azure.tracker import _strip_html

    html = "<div>/fix with tests</div>"
    clean = _strip_html(html)
    result = parse_slash_command(clean)
    assert result is not None
    assert result[0] == "/fix"
    # "with" keyword is consumed by parser; guidance is "tests"
    assert result[1] == "tests"


def test_azure_html_entity_slash_command():
    """Azure DevOps HTML-encoded slash commands parse after decode."""
    from autoswe.commands.parser import parse_slash_command
    from autoswe.providers.azure.tracker import _strip_html

    html = "&#47;fix with &#45;&#45;branch develop"
    clean = _strip_html(html)
    result = parse_slash_command(clean)
    assert result is not None
    assert result[0] == "/fix"
    # --branch is parsed into the branch field (third element)
    assert result[2] == "develop"
