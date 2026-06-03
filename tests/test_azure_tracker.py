"""Tests for autoswe.providers.azure.tracker — ADO IssueTracker (reads + writes)."""
import pytest

from autoswe.providers.azure.tracker import (
    BOT_MARKER,
    AzureTracker,
    _strip_html,
)
from autoswe.providers.base import NormalizedIssue
from tests.conftest import load_ado_fixture

# ---------------------------------------------------------------------------
# _strip_html
# ---------------------------------------------------------------------------

def test_strip_html_simple():
    assert _strip_html("<p>Hello</p>") == "Hello"


def test_strip_html_nested():
    assert _strip_html("<div><p>text <b>bold</b></p></div>") == "text bold"


def test_strip_html_empty():
    assert _strip_html("") == ""


def test_strip_html_none_tags():
    assert _strip_html("plain text") == "plain text"


def test_strip_html_preserves_autoswe_tags():
    """_strip_html preserves <AUTOSWE_*> tags while stripping HTML tags."""
    html = "<p><AUTOSWE_QUESTIONS>\n1. What language?\n</AUTOSWE_QUESTIONS></p>"
    result = _strip_html(html)
    assert "<AUTOSWE_QUESTIONS>" in result
    assert "</AUTOSWE_QUESTIONS>" in result
    assert "1. What language?" in result
    assert "<p>" not in result


def test_strip_html_preserves_autoswe_plan():
    """_strip_html preserves <AUTOSWE_PLAN> tags."""
    html = "<b><AUTOSWE_PLAN>Do the thing</AUTOSWE_PLAN></b>"
    result = _strip_html(html)
    assert result == "<AUTOSWE_PLAN>Do the thing</AUTOSWE_PLAN>"


# ---------------------------------------------------------------------------
# AzureTracker — read-only methods
# ---------------------------------------------------------------------------

@pytest.fixture
def ado_repo_cfg():
    return {
        "provider": "azure",
        "org": "my-org",
        "project": "my-project",
        "pat": "fake_pat_123",
    }


@pytest.fixture
def tracker(ado_repo_cfg):
    return AzureTracker(ado_repo_cfg)


# -- list_open_issues --

def test_list_open_issues_empty(tracker, mock_ado_request, ado_route_table):
    """Empty WIQL result returns no issues."""
    ado_route_table[("POST", "https://dev.azure.com/my-org/my-project/_apis/wit/wiql")] = {"workItems": []}

    result = tracker.list_open_issues({})
    assert result == []


def test_list_open_issues(tracker, mock_ado_request, ado_route_table):
    """Full WIQL → batch GET → normalized issues."""
    wiql_result = load_ado_fixture("wiql_open_workitems.json")
    batch_result = load_ado_fixture("workitems_batch.json")

    ado_route_table[("POST", "https://dev.azure.com/my-org/my-project/_apis/wit/wiql")] = wiql_result
    ado_route_table[("GET", "https://dev.azure.com/my-org/my-project/_apis/wit/workitems?ids=")] = batch_result

    result = tracker.list_open_issues({})

    assert len(result) == 2
    assert result[0].number == 100
    assert result[0].title == "Feature: add login page"
    assert "login" in result[0].body.lower()
    assert "autoswe:pending" in result[0].labels
    assert result[0].status == "pending"

    assert result[1].number == 101
    assert result[1].status == "fixed"


# -- fetch_issue --

def test_fetch_issue(tracker, mock_ado_request, ado_route_table):
    raw = load_ado_fixture("workitem_open_with_plan.json")
    profile = load_ado_fixture("profile_me.json")

    ado_route_table[("GET", "https://dev.azure.com/my-org/my-project/_apis/wit/workitems/100")] = raw
    ado_route_table[("GET", "https://app.vssps.visualstudio.com/_apis/profile")] = profile

    result = tracker.fetch_issue({}, 100)

    assert result.number == 100
    assert result.title == "Feature: add login page"
    assert result.status == "planned"
    assert result.is_pull_request is False  # Always False for ADO


# -- fetch_comments --

def test_fetch_comments_pending(tracker, mock_ado_request, ado_route_table):
    raw = load_ado_fixture("comments_workitem_pending.json")
    workitem = load_ado_fixture("workitem_open_with_plan.json")

    ado_route_table[("GET", "https://dev.azure.com/my-org/my-project/_apis/wit/workitems/100/comments")] = raw
    ado_route_table[("GET", "https://dev.azure.com/my-org/my-project/_apis/wit/workitems/1")] = workitem

    result = tracker.fetch_comments({}, 100)

    assert len(result) == 2
    assert result[0].body == "/plan --branch develop"
    # User comment (matches PAT owner) → OWNER
    assert result[0].author_login == "OWNER"
    assert "autoswe-bot" in result[1].body
    # Bot comment (contains marker) → BOT
    assert result[1].author_login == "BOT"


def test_fetch_comments_empty(tracker, mock_ado_request, ado_route_table):
    ado_route_table[("GET", "https://dev.azure.com/my-org/my-project/_apis/wit/workitems/99/comments")] = {
        "comments": []
    }

    result = tracker.fetch_comments({}, 99)
    assert result == []


def test_fetch_comments_same_author_normalization(tracker, mock_ado_request, ado_route_table):
    """When all comments share the same PAT author, bot/user must still be distinguished.

    This is the bug from issue #56: ADO returns the same uniqueName for all comments
    because they're all posted via the same PAT. The fix normalizes author_login
    based on body content (bot marker) and authenticated user comparison.
    """
    raw = load_ado_fixture("comments_workitem_waiting_same_author.json")
    workitem = load_ado_fixture("workitem_open_with_plan.json")

    ado_route_table[("GET", "https://dev.azure.com/my-org/my-project/_apis/wit/workitems/70/comments")] = raw
    ado_route_table[("GET", "https://dev.azure.com/my-org/my-project/_apis/wit/workitems/1")] = workitem

    result = tracker.fetch_comments({}, 70)

    assert len(result) == 3
    # Comment 1: "/plan" — user comment matching PAT owner → OWNER
    assert result[0].body == "/plan"
    assert result[0].author_login == "OWNER"
    # Comment 2: Bot question — contains <!-- autoswe-bot --> → BOT
    assert "<AUTOSWE_QUESTIONS>" in result[1].body
    assert result[1].author_login == "BOT"
    # Comment 3: User reply — matches PAT owner, no bot marker → OWNER
    assert result[2].body == "Use Python. Create a greet.py file."
    assert result[2].author_login == "OWNER"


def test_fetch_comments_bot_marker_takes_precedence(tracker, mock_ado_request, ado_route_table):
    """Bot marker in body takes precedence over authenticated user match.

    When the PAT owner posts a bot comment (autoSWE uses the PAT to post),
    the BOT marker should classify it as BOT, not OWNER.
    """
    raw = {
        "comments": [
            {
                "id": 1,
                "text": "Completed with command `/fix`\n\n<!-- autoswe-bot -->",
                "createdBy": {
                    "displayName": "Nate Dorr",
                    "uniqueName": "natedorr@example.com"
                },
                "createdDate": "2026-04-01T11:30:00Z"
            },
        ]
    }
    workitem = load_ado_fixture("workitem_open_with_plan.json")

    ado_route_table[("GET", "https://dev.azure.com/my-org/my-project/_apis/wit/workitems/50/comments")] = raw
    ado_route_table[("GET", "https://dev.azure.com/my-org/my-project/_apis/wit/workitems/1")] = workitem

    result = tracker.fetch_comments({}, 50)

    assert len(result) == 1
    assert result[0].author_login == "BOT"


def test_fetch_comments_auth_fallback_preserves_raw(tracker, mock_ado_request, ado_route_table):
    """When authenticated_user fails, comments without bot marker keep raw uniqueName."""
    raw = {
        "comments": [
            {
                "id": 1,
                "text": "User reply text",
                "createdBy": {
                    "displayName": "Nate Dorr",
                    "uniqueName": "natedorr@example.com"
                },
                "createdDate": "2026-04-01T10:35:00Z"
            },
            {
                "id": 2,
                "text": "Bot response\n\n<!-- autoswe-bot -->",
                "createdBy": {
                    "displayName": "Nate Dorr",
                    "uniqueName": "natedorr@example.com"
                },
                "createdDate": "2026-04-01T10:35:05Z"
            },
        ]
    }
    # No workitem route → authenticated_user fails
    # Don't register workitems/1, so authenticated_user will raise

    ado_route_table[("GET", "https://dev.azure.com/my-org/my-project/_apis/wit/workitems/50/comments")] = raw

    result = tracker.fetch_comments({}, 50)

    assert len(result) == 2
    # Bot comment still detected via marker
    assert result[1].author_login == "BOT"
    # User comment falls back to raw uniqueName when auth fails
    assert result[0].author_login == "natedorr@example.com"


def test_fetch_comments_decodes_html_entities_in_branch_flag(
    tracker, mock_ado_request, ado_route_table
):
    """HTML-encoded --branch in ADO comments is decoded so the parser can match it.

    Azure DevOps may return --branch as &#45;&#45;branch in the text field.
    html.unescape() in fetch_comments() decodes this so parse_slash_command
    can extract the branch name.
    """
    raw = {
        "comments": [
            {
                "id": 1,
                "text": "&#47;fix &#45;&#45;branch test-branch-6",
                "createdBy": {
                    "displayName": "Nate Dorr",
                    "uniqueName": "natedorr@example.com",
                },
                "createdDate": "2026-04-01T10:30:00Z",
            },
        ],
    }
    workitem = load_ado_fixture("workitem_open_with_plan.json")

    ado_route_table[
        ("GET", "https://dev.azure.com/my-org/my-project/_apis/wit/workitems/100/comments")
    ] = raw
    ado_route_table[
        ("GET", "https://dev.azure.com/my-org/my-project/_apis/wit/workitems/1")
    ] = workitem

    result = tracker.fetch_comments({}, 100)

    assert len(result) == 1
    assert result[0].body == "/fix --branch test-branch-6"


def test_fetch_comments_decodes_named_html_entities(
    tracker, mock_ado_request, ado_route_table
):
    """Named HTML entities like &amp; &lt; &gt; &hellip; are decoded."""
    raw = {
        "comments": [
            {
                "id": 1,
                "text": "Fix bug &amp; edge cases: handle &lt;input&gt; validation &hellip;",
                "createdBy": {
                    "displayName": "User",
                    "uniqueName": "user@example.com",
                },
                "createdDate": "2026-04-01T10:30:00Z",
            },
        ],
    }
    workitem = load_ado_fixture("workitem_open_with_plan.json")

    ado_route_table[
        ("GET", "https://dev.azure.com/my-org/my-project/_apis/wit/workitems/100/comments")
    ] = raw
    ado_route_table[
        ("GET", "https://dev.azure.com/my-org/my-project/_apis/wit/workitems/1")
    ] = workitem

    result = tracker.fetch_comments({}, 100)

    assert result[0].body == "Fix bug & edge cases: handle <input> validation …"


def test_fetch_comments_plain_text_unchanged(
    tracker, mock_ado_request, ado_route_table
):
    """Comments without HTML entities pass through unchanged."""
    raw = {
        "comments": [
            {
                "id": 1,
                "text": "/fix --branch develop",
                "createdBy": {
                    "displayName": "Nate Dorr",
                    "uniqueName": "natedorr@example.com",
                },
                "createdDate": "2026-04-01T10:30:00Z",
            },
        ],
    }
    workitem = load_ado_fixture("workitem_open_with_plan.json")

    ado_route_table[
        ("GET", "https://dev.azure.com/my-org/my-project/_apis/wit/workitems/100/comments")
    ] = raw
    ado_route_table[
        ("GET", "https://dev.azure.com/my-org/my-project/_apis/wit/workitems/1")
    ] = workitem

    result = tracker.fetch_comments({}, 100)

    assert result[0].body == "/fix --branch develop"


# -- get_status --

def test_get_status_pending(tracker):
    issue = NormalizedIssue(
        number=1, title="t", body="b", owner="o", repo="r",
        labels=["autoswe:pending", "bug"],
    )
    assert tracker.get_status(issue) == "pending"


def test_get_status_no_autoswe_label(tracker):
    issue = NormalizedIssue(
        number=1, title="t", body="b", owner="o", repo="r",
        labels=["bug", "enhancement"],
    )
    assert tracker.get_status(issue) is None


def test_get_status_empty_labels(tracker):
    issue = NormalizedIssue(
        number=1, title="t", body="b", owner="o", repo="r",
    )
    assert tracker.get_status(issue) is None


# -- authenticated_user --

def test_authenticated_user_cached(tracker, mock_ado_request, ado_route_table):
    profile = load_ado_fixture("profile_me.json")
    ado_route_table[("GET", "https://app.vssps.visualstudio.com/_apis/profile")] = profile

    first = tracker.authenticated_user({})
    second = tracker.authenticated_user({})

    assert first == "natedorr@example.com"
    assert first == second
    # Should only call once — cached (Profile API succeeds, no fallback needed)
    assert len(mock_ado_request.calls) == 1


# -- is_pull_request always False --

def test_is_pull_request_false(tracker, mock_ado_request, ado_route_table):
    raw = load_ado_fixture("workitem_open_with_plan.json")
    profile = load_ado_fixture("profile_me.json")

    ado_route_table[("GET", "https://dev.azure.com/my-org/my-project/_apis/wit/workitems/100")] = raw
    ado_route_table[("GET", "https://app.vssps.visualstudio.com/_apis/profile")] = profile

    result = tracker.fetch_issue({}, 100)
    assert result.is_pull_request is False


# -- author_association mapping --

def test_author_association_owner(tracker, mock_ado_request, ado_route_table):
    """Issue created by same user as PAT owner → OWNER."""
    profile = load_ado_fixture("profile_me.json")
    raw = load_ado_fixture("workitem_open_with_plan.json")  # createdBy matches profile

    ado_route_table[("GET", "https://dev.azure.com/my-org/my-project/_apis/wit/workitems/100")] = raw
    ado_route_table[("GET", "https://app.vssps.visualstudio.com/_apis/profile")] = profile

    _ = tracker.fetch_issue({}, 100)


# -- write methods (Stage 5) --

# -- post_comment --

def test_post_comment(tracker, mock_ado_request, ado_route_table):
    """post_comment sends a POST to the comments endpoint with format=Markdown query param."""
    comment_response = load_ado_fixture("comment_post_response.json")
    ado_route_table[("POST", "https://dev.azure.com/my-org/my-project/_apis/wit/workitems/100/comments")] = comment_response

    tracker.post_comment({}, 100, "This is a test comment")

    assert len(mock_ado_request.calls) == 1
    call = mock_ado_request.calls[0]
    assert call["method"] == "POST"
    assert "workitems/100/comments" in call["path"]
    assert "format=Markdown" in call["path"]
    assert call["body"] == {"text": "This is a test comment"}


def test_post_comment_preserves_newlines_in_markdown(tracker, mock_ado_request, ado_route_table):
    """post_comment preserves newlines and Markdown formatting via format=Markdown query param.

    The Azure DevOps Comments API requires ``format`` as a query parameter
    (case-sensitive ``Markdown``), not a body field.  With the correct query
    parameter, newlines, lists, bold, links, etc. are preserved as expected.
    """
    comment_response = load_ado_fixture("comment_post_response.json")
    ado_route_table[("POST", "https://dev.azure.com/my-org/my-project/_apis/wit/workitems/100/comments")] = comment_response

    body = (
        "autoSWE picked up this issue (`ado:org_proj_71`).\n\n"
        "**Available Commands:**\n"
        "- `/plan` - Start a planning session\n"
        "- `/fix` - Implement the fix\n"
        "- `/pr` - Open a pull request\n\n"
        "You can add guidance: `/fix with performance focus`\n"
        "\n<!-- autoswe-bot -->"
    )

    tracker.post_comment({}, 100, body)

    assert len(mock_ado_request.calls) == 1
    call = mock_ado_request.calls[0]
    # Bot comments use format=Markdown — ADO renders markdown natively
    assert "format=Markdown" in call["path"]
    assert "format" not in call["body"]  # format must NOT be in the body
    # Body should be raw markdown — no HTML conversion
    assert call["body"]["text"] == body
    assert BOT_MARKER in call["body"]["text"]
    assert call["body"]["text"].endswith(BOT_MARKER)


# -- set_status --

def test_set_status_preserves_non_autoswe_tags(tracker, mock_ado_request, ado_route_table):
    """set_status strips autoswe:* tags and appends new status, preserving others."""
    raw = load_ado_fixture("workitem_with_tags.json")
    patch_response = {"id": 100, "rev": 6}

    ado_route_table[("GET", "https://dev.azure.com/my-org/my-project/_apis/wit/workitems/100")] = raw
    ado_route_table[("PATCH", "https://dev.azure.com/my-org/my-project/_apis/wit/workitems/100")] = patch_response

    tracker.set_status({}, 100, "fixed")

    # Should do a GET (read tags) then a PATCH (write new tags)
    assert len(mock_ado_request.calls) == 2
    get_call = mock_ado_request.calls[0]
    assert get_call["method"] == "GET"
    assert "fields=System.Tags" in get_call["path"]

    patch_call = mock_ado_request.calls[1]
    assert patch_call["method"] == "PATCH"
    patch_body = patch_call["body"]
    assert len(patch_body) == 1
    assert patch_body[0]["op"] == "replace"
    assert patch_body[0]["path"] == "/fields/System.Tags"
    # Should have feature; bug; autoswe:fixed (no autoswe:pending)
    new_tags = patch_body[0]["value"]
    assert "feature" in new_tags
    assert "bug" in new_tags
    assert "autoswe:fixed" in new_tags
    assert "autoswe:pending" not in new_tags


def test_set_status_no_existing_tags(tracker, mock_ado_request, ado_route_table):
    """set_status works when there are no existing tags."""
    raw = {"id": 100, "fields": {"System.Tags": ""}}
    patch_response = {"id": 100, "rev": 2}

    ado_route_table[("GET", "https://dev.azure.com/my-org/my-project/_apis/wit/workitems/100")] = raw
    ado_route_table[("PATCH", "https://dev.azure.com/my-org/my-project/_apis/wit/workitems/100")] = patch_response

    tracker.set_status({}, 100, "pending")

    assert len(mock_ado_request.calls) == 2
    patch_call = mock_ado_request.calls[1]
    assert patch_call["body"] == [{"op": "replace", "path": "/fields/System.Tags", "value": "autoswe:pending"}]


def test_set_status_with_full_label_no_double_prefix(tracker, mock_ado_request, ado_route_table):
    """set_status with full label (autoswe:pending) doesn't produce double prefix.

    The orchestrator (dispatch.py, sync.py) calls set_status with the full
    label string like 'autoswe:pending', not a bare status name. This test
    ensures the Azure tracker normalizes it correctly.
    """
    raw = {"id": 100, "fields": {"System.Tags": ""}}
    patch_response = {"id": 100, "rev": 2}

    ado_route_table[("GET", "https://dev.azure.com/my-org/my-project/_apis/wit/workitems/100")] = raw
    ado_route_table[("PATCH", "https://dev.azure.com/my-org/my-project/_apis/wit/workitems/100")] = patch_response

    tracker.set_status({}, 100, "autoswe:pending")

    patch_call = mock_ado_request.calls[1]
    tag_value = patch_call["body"][0]["value"]
    assert tag_value == "autoswe:pending"
    assert "autoswe:autoswe:pending" not in tag_value


def test_set_status_full_label_replaces_old_full_label(tracker, mock_ado_request, ado_route_table):
    """set_status with full label replaces old full label correctly."""
    raw = {"id": 100, "fields": {"System.Tags": "feature; bug; autoswe:pending"}}
    patch_response = {"id": 100, "rev": 3}

    ado_route_table[("GET", "https://dev.azure.com/my-org/my-project/_apis/wit/workitems/100")] = raw
    ado_route_table[("PATCH", "https://dev.azure.com/my-org/my-project/_apis/wit/workitems/100")] = patch_response

    tracker.set_status({}, 100, "autoswe:fixing")

    patch_call = mock_ado_request.calls[1]
    tag_value = patch_call["body"][0]["value"]
    assert "autoswe:fixing" in tag_value
    assert "autoswe:pending" not in tag_value
    assert "feature" in tag_value
    assert "bug" in tag_value


# -- assign_to_user --

def test_assign_to_user_explicit_login(tracker, mock_ado_request, ado_route_table):
    """assign_to_user with explicit login uses it directly."""
    patch_response = load_ado_fixture("workitem_after_assign.json")
    ado_route_table[("PATCH", "https://dev.azure.com/my-org/my-project/_apis/wit/workitems/100")] = patch_response

    tracker.assign_to_user({}, 100, "dev@example.com")

    assert len(mock_ado_request.calls) == 1
    call = mock_ado_request.calls[0]
    assert call["method"] == "PATCH"
    assert call["body"] == [{"op": "replace", "path": "/fields/System.AssignedTo", "value": "dev@example.com"}]
    # Should NOT call authenticated_user
    assert len([c for c in mock_ado_request.calls if "profile" in c["path"]]) == 0


def test_assign_to_user_resolves_authenticated(tracker, mock_ado_request, ado_route_table):
    """assign_to_user(login=None) resolves via authenticated_user."""
    profile = load_ado_fixture("profile_me.json")
    patch_response = load_ado_fixture("workitem_after_assign.json")

    ado_route_table[("GET", "https://app.vssps.visualstudio.com/_apis/profile")] = profile
    ado_route_table[("PATCH", "https://dev.azure.com/my-org/my-project/_apis/wit/workitems/100")] = patch_response

    tracker.assign_to_user({}, 100, None)

    # Should call Profile API (authenticated_user) then PATCH
    assert len(mock_ado_request.calls) == 2
    assert mock_ado_request.calls[0]["method"] == "GET"
    assert "profile" in mock_ado_request.calls[0]["path"]
    assert mock_ado_request.calls[1]["method"] == "PATCH"
    assert mock_ado_request.calls[1]["body"] == [
        {"op": "replace", "path": "/fields/System.AssignedTo", "value": "natedorr@example.com"}
    ]


# ---------------------------------------------------------------------------
# Bot comment round-trip
# ---------------------------------------------------------------------------

def test_post_comment_bot_uses_markdown_format(tracker, mock_ado_request, ado_route_table):
    """Bot comments (with BOT_MARKER) are posted with format=Markdown, raw body."""
    comment_response = load_ado_fixture("comment_post_response.json")
    ado_route_table[("POST", "https://dev.azure.com/my-org/my-project/_apis/wit/workitems/100/comments")] = comment_response

    tracker.post_comment({}, 100, "Bot message\n\n<!-- autoswe-bot -->")

    assert len(mock_ado_request.calls) == 1
    call = mock_ado_request.calls[0]
    assert call["method"] == "POST"
    assert "format=Markdown" in call["path"]
    assert call["body"]["text"] == "Bot message\n\n<!-- autoswe-bot -->"


def test_post_comment_non_bot_uses_markdown_format(tracker, mock_ado_request, ado_route_table):
    """Non-bot comments are still posted with format=Markdown."""
    comment_response = load_ado_fixture("comment_post_response.json")
    ado_route_table[("POST", "https://dev.azure.com/my-org/my-project/_apis/wit/workitems/100/comments")] = comment_response

    tracker.post_comment({}, 100, "Just a user comment, no bot marker here")

    assert len(mock_ado_request.calls) == 1
    call = mock_ado_request.calls[0]
    assert "format=Markdown" in call["path"]
    assert call["body"]["text"] == "Just a user comment, no bot marker here"


# -- update_comment --

def test_update_comment_markdown(tracker, mock_ado_request, ado_route_table):
    """Non-bot body sends format=Markdown, PATCH to workitems/{n}/comments/{cid}."""
    patch_response = {"id": 42}
    ado_route_table[("PATCH", "https://dev.azure.com/my-org/my-project/_apis/wit/workitems/100/comments/42")] = patch_response

    tracker.update_comment({}, 100, 42, "Updated text, no bot marker")

    assert len(mock_ado_request.calls) == 1
    call = mock_ado_request.calls[0]
    assert call["method"] == "PATCH"
    assert "workitems/100/comments/42" in call["path"]
    assert "format=Markdown" in call["path"]
    assert call["body"] == {"text": "Updated text, no bot marker"}


def test_update_comment_markdown_for_bot(tracker, mock_ado_request, ado_route_table):
    """Body containing BOT_MARKER sends format=Markdown, raw body."""
    patch_response = {"id": 42}
    ado_route_table[("PATCH", "https://dev.azure.com/my-org/my-project/_apis/wit/workitems/100/comments/42")] = patch_response

    tracker.update_comment({}, 100, 42, "Bot update\n\n<!-- autoswe-bot -->")

    assert len(mock_ado_request.calls) == 1
    call = mock_ado_request.calls[0]
    assert call["method"] == "PATCH"
    assert "format=Markdown" in call["path"]
    assert call["body"]["text"] == "Bot update\n\n<!-- autoswe-bot -->"


def test_update_comment_url_encodes_org_and_project():
    """Org/project segments with special chars are URL-encoded."""
    patch_calls = []

    class FakePatchJson:
        def __call__(self, path, pat, body):
            patch_calls.append({"path": path, "body": body})

    import autoswe.providers.azure.tracker as tracker_mod
    original = tracker_mod.ado_patch_json
    tracker_mod.ado_patch_json = FakePatchJson()

    try:
        tracker = AzureTracker({
            "org": "my org",
            "project": "proj#1",
            "pat": "tok",
        })
        tracker.update_comment({}, 5, 99, "body")
    finally:
        tracker_mod.ado_patch_json = original

    assert len(patch_calls) == 1
    assert "my+org" in patch_calls[0]["path"] or "my%20org" in patch_calls[0]["path"]
    assert "proj%231" in patch_calls[0]["path"]


def test_bot_comment_roundtrip(tracker, mock_ado_request, ado_route_table):
    """Post bot comment, fetch back, verify content and author=BOT.

    Bot comments are posted as format=Markdown. ADO strips HTML comments
    from the stored body, so _BOT_CONTENT_PATTERNS (## Plan, etc.) is the
    real identification mechanism. fetch_comments re-appends BOT_MARKER
    for downstream consumers.
    """
    comment_response = load_ado_fixture("comment_post_response.json")
    workitem = load_ado_fixture("workitem_open_with_plan.json")

    ado_route_table[("POST", "https://dev.azure.com/my-org/my-project/_apis/wit/workitems/100/comments")] = comment_response
    ado_route_table[("GET", "https://dev.azure.com/my-org/my-project/_apis/wit/workitems/100/comments")] = {
        "comments": [
            {
                "id": 1,
                "text": "## Plan\n\nBot message",
                "createdBy": {"displayName": "Bot", "uniqueName": "natedorr@example.com"},
                "createdDate": "2026-05-15T10:00:00Z",
            },
        ],
    }
    ado_route_table[("GET", "https://dev.azure.com/my-org/my-project/_apis/wit/workitems/1")] = workitem

    # Post bot comment
    tracker.post_comment({}, 100, "## Plan\n\nBot message\n\n<!-- autoswe-bot -->")

    # Fetch comments back
    comments = tracker.fetch_comments({}, 100)

    assert len(comments) == 1
    # BOT_MARKER re-appended by fetch_comments (ADO strips HTML comments)
    assert BOT_MARKER in comments[0].body
    # Author detected as BOT via _BOT_CONTENT_PATTERNS ("## Plan")
    assert comments[0].author_login == "BOT"
    # Body is clean markdown text
    assert "## Plan" in comments[0].body
    assert "<p>" not in comments[0].body


def test_fetch_comments_mixed_html_and_markdown(tracker, mock_ado_request, ado_route_table):
    """fetch_comments handles both HTML bot comments and markdown user comments."""
    workitem = load_ado_fixture("workitem_open_with_plan.json")

    ado_route_table[("GET", "https://dev.azure.com/my-org/my-project/_apis/wit/workitems/50/comments")] = {
        "comments": [
            {
                "id": 1,
                "text": "/fix",  # User comment (markdown)
                "createdBy": {"displayName": "Nate", "uniqueName": "natedorr@example.com"},
                "createdDate": "2026-05-15T09:00:00Z",
            },
            {
                "id": 2,
                "text": "<p>Completed with command</p><!-- autoswe-bot -->",  # Bot comment (html)
                "createdBy": {"displayName": "Nate", "uniqueName": "natedorr@example.com"},
                "createdDate": "2026-05-15T10:00:00Z",
            },
        ],
    }
    ado_route_table[("GET", "https://dev.azure.com/my-org/my-project/_apis/wit/workitems/1")] = workitem

    comments = tracker.fetch_comments({}, 50)

    assert len(comments) == 2
    # User comment: markdown, no marker → OWNER
    assert comments[0].body == "/fix"
    assert comments[0].author_login == "OWNER"
    # Bot comment: HTML, has marker → BOT, HTML stripped
    assert "Completed with command" in comments[1].body
    assert BOT_MARKER in comments[1].body
    assert comments[1].author_login == "BOT"
    assert "<p>" not in comments[1].body  # HTML tags stripped

