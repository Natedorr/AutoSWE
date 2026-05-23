"""Tests for autoswe.harness.ask_user_question formatting and callback."""
from unittest.mock import MagicMock, patch

from autoswe.harness.ask_user_question import format_ask_user_question


def test_format_ask_user_question_single():
    """Single question renders with header, question, and options."""
    input_data = {
        "questions": [
            {
                "header": "Database",
                "question": "Which database should we use?",
                "options": [
                    {"label": "Postgres", "description": "Relational, SQL"},
                    {"label": "MongoDB", "description": "Document, NoSQL"},
                ],
                "multiSelect": False,
            }
        ]
    }
    md = format_ask_user_question(input_data)
    assert "## Questions" in md
    assert "### Database" in md
    assert "Which database should we use?" in md
    assert "**Postgres** — Relational, SQL" in md
    assert "**MongoDB** — Document, NoSQL" in md
    assert "(select any that apply)" not in md
    assert "Reply in this thread" in md


def test_format_ask_user_question_multi_select():
    """Multi-select question gets the (select any that apply) note."""
    input_data = {
        "questions": [
            {
                "header": "Features",
                "question": "Which features to enable?",
                "options": [
                    {"label": "Caching", "description": "Redis-backed"},
                    {"label": "Metrics", "description": "Prometheus export"},
                ],
                "multiSelect": True,
            }
        ]
    }
    md = format_ask_user_question(input_data)
    assert "(select any that apply)" in md


def test_format_ask_user_question_multiple_questions():
    """Multiple questions are rendered sequentially."""
    input_data = {
        "questions": [
            {
                "header": "Q1",
                "question": "First question?",
                "options": [{"label": "A", "description": ""}],
                "multiSelect": False,
            },
            {
                "header": "Q2",
                "question": "Second question?",
                "options": [{"label": "B", "description": ""}],
                "multiSelect": False,
            },
        ]
    }
    md = format_ask_user_question(input_data)
    assert "### Q1" in md
    assert "First question?" in md
    assert "### Q2" in md
    assert "Second question?" in md


def test_format_ask_user_question_empty():
    """Empty questions list renders a fallback."""
    input_data = {"questions": []}
    md = format_ask_user_question(input_data)
    assert "## Questions" in md
    assert "(no questions)" in md


def test_format_option_without_description():
    """Options without descriptions are rendered as just the label."""
    input_data = {
        "questions": [
            {
                "header": "Choice",
                "question": "Pick one?",
                "options": [{"label": "Option A", "description": ""}],
                "multiSelect": False,
            }
        ]
    }
    md = format_ask_user_question(input_data)
    assert "- **Option A**" in md


def test_make_can_use_tool_allows_non_ask():
    """Non-AskUserQuestion tools get PermissionResultAllow."""
    import asyncio

    from autoswe.harness.ask_user_question import make_can_use_tool

    task = {"owner": "o", "repo": "r", "issue_number": 1, "_token": "tok"}
    repo_cfg = {"provider": "github"}
    state = {}

    callback = make_can_use_tool(task, repo_cfg, state)
    result = asyncio.run(
        callback("Read", {"file_path": "foo.py"}, None)
    )
    from claude_agent_sdk import PermissionResultAllow

    assert isinstance(result, PermissionResultAllow)


def test_make_can_use_tool_allows_ask_with_answers():
    """AskUserQuestion gets PermissionResultAllow with answers and sets state."""
    import asyncio

    from autoswe.harness.ask_user_question import make_can_use_tool

    task = {"owner": "o", "repo": "r", "issue_number": 1, "_token": "tok"}
    repo_cfg = {"provider": "github"}
    state = {}

    input_data = {
        "questions": [
            {
                "header": "Q",
                "question": "Which approach?",
                "options": [{"label": "A", "description": "desc"}],
                "multiSelect": False,
            }
        ]
    }

    callback = make_can_use_tool(task, repo_cfg, state)

    with patch("autoswe.harness.ask_user_question.get_tracker") as mock_get:
        mock_tracker = MagicMock()
        mock_get.return_value = mock_tracker

        result = asyncio.run(
            callback("AskUserQuestion", input_data, None)
        )

        from claude_agent_sdk import PermissionResultAllow

        assert isinstance(result, PermissionResultAllow)
        assert "asked_question_md" in state
        assert "Which approach?" in state["asked_question_md"]
        # Check the updated_input has answers
        updated = result.updated_input
        assert "answers" in updated
        assert "Which approach?" in updated["answers"]
        mock_tracker.post_comment.assert_called_once()
        body = mock_tracker.post_comment.call_args[0][2]
        assert "<!-- autoswe-bot -->" in body


def test_make_can_use_tool_uses_on_post():
    """When on_post is provided, it is used instead of get_tracker."""
    import asyncio

    from autoswe.harness.ask_user_question import make_can_use_tool

    task = {"owner": "o", "repo": "r", "issue_number": 1, "_token": "tok"}
    repo_cfg = {"provider": "github"}
    state = {}

    posted_bodies = []

    def on_post(body):
        posted_bodies.append(body)

    input_data = {
        "questions": [
            {
                "header": "H",
                "question": "Question?",
                "options": [{"label": "X", "description": ""}],
                "multiSelect": False,
            }
        ]
    }

    callback = make_can_use_tool(task, repo_cfg, state, on_post=on_post)

    with patch("autoswe.harness.ask_user_question.get_tracker") as mock_get:
        asyncio.run(
            callback("AskUserQuestion", input_data, None)
        )

        assert len(posted_bodies) == 1
        assert "Question?" in posted_bodies[0]
        assert "<!-- autoswe-bot -->" in posted_bodies[0]
        mock_get.assert_not_called()
