"""Tests for pure-logic helpers — no mocking needed."""

from autoswe.commands.parser import parse_slash_command
from autoswe.core.slug import make_slug, slug_to_filename
from autoswe.tracking.comments import (
    _find_last_bot_comment_ts,
    _find_last_completion,
    _get_body,
    _get_id,
    _get_is_bot,
    _is_autoswe_bot_comment,
    _normalize_body,
)
from autoswe.tracking.labels import _get_autoswe_status
from tests.conftest import load_fixture

# ---------------------------------------------------------------------------
# parse_slash_command
# ---------------------------------------------------------------------------

def test_parse_plan():
    assert parse_slash_command("/plan") == ("/plan", None, None)


def test_parse_fix_no_guidance():
    assert parse_slash_command("/fix") == ("/fix", None, None)


def test_parse_fix_with_guidance():
    cmd, guidance, branch = parse_slash_command("/fix with performance focus")
    assert cmd == "/fix"
    assert guidance == "performance focus"
    assert branch is None


def test_parse_fix_guidance_without_with_keyword():
    cmd, guidance, branch = parse_slash_command("/fix some additional notes")
    assert cmd == "/fix"
    assert guidance == "some additional notes"
    assert branch is None


def test_parse_retry():
    assert parse_slash_command("/retry") == ("/retry", None, None)


def test_parse_skip():
    assert parse_slash_command("/skip") == ("/skip", None, None)


def test_parse_pr():
    assert parse_slash_command("/pr") == ("/pr", None, None)


def test_parse_sync():
    assert parse_slash_command("/sync") == ("/sync", None, None)


def test_parse_abort():
    assert parse_slash_command("/abort") == ("/abort", None, None)


def test_parse_review():
    assert parse_slash_command("/review") == ("/review", None, None)


def test_parse_review_with_guidance():
    cmd, guidance, branch = parse_slash_command("/review with focus on auth")
    assert cmd == "/review"
    assert guidance == "focus on auth"
    assert branch is None


def test_parse_review_case_insensitive():
    cmd, _, _ = parse_slash_command("/REVIEW")
    assert cmd == "/review"


def test_parse_case_insensitive():
    cmd, _, _ = parse_slash_command("/FIX")
    assert cmd == "/fix"


def test_parse_case_insensitive_abort():
    cmd, _, _ = parse_slash_command("/ABORT")
    assert cmd == "/abort"


def test_parse_last_command_wins():
    # When commands are separated by non-command lines, finditer finds both;
    # parse_slash_command returns the last match.
    text = "Let's start.\n/plan\nReasoning here.\n/fix with extra focus"
    cmd, guidance, branch = parse_slash_command(text)
    assert cmd == "/fix"
    assert guidance == "extra focus"
    assert branch is None


def test_parse_no_command_returns_none():
    assert parse_slash_command("Just a regular comment.") is None
    assert parse_slash_command("") is None
    assert parse_slash_command(None) is None


def test_parse_unknown_command_returns_none():
    assert parse_slash_command("/unknown") is None


# ---------------------------------------------------------------------------
# _is_autoswe_bot_comment
# ---------------------------------------------------------------------------

def test_autoswe_bot_comment_new_marker():
    comment = {"body": "Some text\n<!-- autoswe-bot -->"}
    assert _is_autoswe_bot_comment(comment) is True


def test_autoswe_bot_comment_completion_marker():
    """'Completed with command' IS detected as a bot comment via content pattern.

    This is the fix for issue #182: Azure DevOps strips HTML comments (BOT_MARKER),
    so content-based pattern detection is needed to identify bot comments.
    """
    assert _is_autoswe_bot_comment({"body": "Completed with command `/fix`"}) is True


def test_autoswe_bot_comment_user_comment():
    assert _is_autoswe_bot_comment({"body": "/fix with focus on tests"}) is False


def test_autoswe_bot_comment_empty_body():
    assert _is_autoswe_bot_comment({"body": ""}) is False
    assert _is_autoswe_bot_comment({"body": None}) is False


# ---------------------------------------------------------------------------
# _find_last_completion
# ---------------------------------------------------------------------------

def test_find_last_completion_present():
    comments = load_fixture("comments_done_state.json")
    ts = _find_last_completion(comments)
    assert ts is not None
    assert "2026" in ts


def test_find_last_completion_absent():
    comments = load_fixture("comments_waiting_state.json")
    # waiting_state has no "Completed with command" comment
    ts = _find_last_completion(comments)
    assert ts is None


def test_find_last_completion_empty():
    assert _find_last_completion([]) is None


# ---------------------------------------------------------------------------
# _find_last_bot_comment_ts
# ---------------------------------------------------------------------------

def test_find_last_bot_comment_ts():
    comments = load_fixture("comments_waiting_state.json")
    ts = _find_last_bot_comment_ts(comments)
    assert ts is not None
    # The second comment (questions) is the latest autoswe comment
    assert ts == comments[-1]["created_at"]


def test_find_last_bot_comment_ts_no_bot_comments():
    comments = [
        {"body": "Just a user comment", "created_at": "2026-01-01T00:00:00Z"},
    ]
    assert _find_last_bot_comment_ts(comments) is None


# ---------------------------------------------------------------------------
# _get_autoswe_status
# ---------------------------------------------------------------------------

def test_get_autoswe_status_pending():
    labels = load_fixture("labels_list_issue_pending.json")
    assert _get_autoswe_status(labels) == "pending"


def test_get_autoswe_status_no_autoswe_label():
    labels = [{"name": "bug"}, {"name": "enhancement"}]
    assert _get_autoswe_status(labels) is None


def test_get_autoswe_status_string_labels():
    # Dispatch passes label name strings sometimes
    assert _get_autoswe_status(["bug", "autoswe:fixed"]) == "fixed"


def test_get_autoswe_status_all_types():
    for status in ("pending", "fixing", "fixed", "failed", "waiting", "planned", "skipped"):
        assert _get_autoswe_status([{"name": f"autoswe:{status}"}]) == status


# ---------------------------------------------------------------------------
# make_slug
# ---------------------------------------------------------------------------

def test_make_slug_github():
    slug = make_slug("github", ("natedorr", "autoswe"), 42)
    assert slug == "gh:natedorr_autoswe_42"


# ---------------------------------------------------------------------------
# Edge cases for parse_slash_command
# ---------------------------------------------------------------------------

def test_parse_fix_with_with_keyword():
    """/fix with <text> should strip 'with' keyword."""
    cmd, guidance, branch = parse_slash_command("/fix with better error handling")
    assert cmd == "/fix"
    assert guidance == "better error handling"
    assert branch is None


def test_parse_fix_without_with_keyword():
    """/fix <text> without 'with' should include all text as guidance."""
    cmd, guidance, branch = parse_slash_command("/fix improve performance")
    assert cmd == "/fix"
    assert guidance == "improve performance"
    assert branch is None


def test_parse_plan_with_extra_text():
    """/plan with trailing text (no --branch) should capture text as guidance."""
    cmd, guidance, branch = parse_slash_command("/plan please")
    assert cmd == "/plan"
    assert guidance == "please"
    assert branch is None


def test_parse_plan_with_branch():
    """/plan --branch develop should extract branch."""
    cmd, guidance, branch = parse_slash_command("/plan --branch develop")
    assert cmd == "/plan"
    assert guidance is None
    assert branch == "develop"


def test_parse_plan_with_branch_and_guidance():
    """/plan --branch develop with API focus should extract both."""
    cmd, guidance, branch = parse_slash_command("/plan --branch develop with API focus")
    assert cmd == "/plan"
    assert guidance == "API focus"
    assert branch == "develop"


def test_parse_plan_branch_with_hyphens():
    """/plan --branch feature/my-feature should parse hyphenated branch."""
    cmd, _, branch = parse_slash_command("/plan --branch feature/my-feature")
    assert cmd == "/plan"
    assert branch == "feature/my-feature"


def test_parse_command_in_multiline():
    """Slash command at start of a line in multiline text should be found."""
    text = "Here is some context.\n/fix with tests\nMore text after."
    cmd, guidance, branch = parse_slash_command(text)
    assert cmd == "/fix"
    assert guidance == "tests"
    assert branch is None


def test_parse_command_at_end_of_line():
    """Slash command not at start of line should return None."""
    result = parse_slash_command("Let's do this /retry")
    assert result is None  # SLASH_RE requires ^ at start of line


def test_parse_command_indented():
    """Indented slash command should return None (^ anchor)."""
    result = parse_slash_command("    /fix with tests")
    assert result is None


def test_parse_skip_with_extra():
    """/skip with extra text should still parse as /skip."""
    cmd, guidance, branch = parse_slash_command("/skip this issue")
    assert cmd == "/skip"
    assert branch is None


def test_parse_pr_with_extra():
    """/pr with extra text should parse."""
    cmd, guidance, branch = parse_slash_command("/pr to main")
    assert cmd == "/pr"
    assert branch is None


def test_parse_abort_with_extra():
    """/abort with extra text should parse as /abort."""
    cmd, guidance, branch = parse_slash_command("/abort this task")
    assert cmd == "/abort"
    assert branch is None


def test_parse_only_whitespace():
    """Whitespace-only text should return None."""
    assert parse_slash_command("   \n  \t  ") is None


def test_parse_unicode_command():
    """Unicode text should not interfere with parsing."""
    cmd, guidance, branch = parse_slash_command("/fix \u0192\u015b\u00e9\u017a\u0107\u017a\u00f3\u0142")
    assert cmd == "/fix"
    assert branch is None


def test_parse_fix_with_branch():
    """/fix --branch develop should extract branch."""
    cmd, guidance, branch = parse_slash_command("/fix --branch develop")
    assert cmd == "/fix"
    assert guidance is None
    assert branch == "develop"


def test_parse_fix_with_branch_and_guidance():
    """/fix --branch develop with tests should extract both."""
    cmd, guidance, branch = parse_slash_command("/fix --branch develop with tests")
    assert cmd == "/fix"
    assert guidance == "tests"
    assert branch == "develop"


def test_parse_fix_with_branch_and_with_guidance():
    """/fix --branch develop with API focus should extract both."""
    cmd, guidance, branch = parse_slash_command("/fix --branch develop with API focus")
    assert cmd == "/fix"
    assert guidance == "API focus"
    assert branch == "develop"


def test_parse_fix_branch_with_slash():
    """/fix --branch feature/my-feature handles slashes in branch names."""
    cmd, _, branch = parse_slash_command("/fix --branch feature/my-feature")
    assert cmd == "/fix"
    assert branch == "feature/my-feature"


def test_parse_fix_branch_after_html_unescape():
    """Parser correctly extracts branch from decoded text (post-html.unescape).

    Regression test for issue #181: after html.unescape decodes
    &#45;&#45;branch to --branch, the parser must still match.
    """
    decoded = "/fix --branch test-branch-6"
    cmd, guidance, branch = parse_slash_command(decoded)
    assert cmd == "/fix"
    assert branch == "test-branch-6"
    assert guidance is None


def test_parse_slash_command_with_encoded_entities_returns_none():
    """HTML-encoded text without decoding will NOT be parsed.

    This documents the raw behavior: if html.unescape is not applied,
    the parser cannot match HTML-encoded commands. This is why the
    Azure tracker must decode entities before returning comment bodies.
    """
    encoded = "&#47;fix &#45;&#45;branch test-branch-6"
    assert parse_slash_command(encoded) is None


# ---------------------------------------------------------------------------
# Edge cases for make_slug
# ---------------------------------------------------------------------------

def test_make_slug_with_hyphens():
    slug = make_slug("github", ("my-org", "my-repo-name"), 123)
    assert slug == "gh:my-org_my-repo-name_123"


# ---------------------------------------------------------------------------
# slug_to_filename — sanitize slugs for use as filenames
# ---------------------------------------------------------------------------

def test_slug_to_filename_github_basic():
    """GitHub slug colon is replaced, producing a valid filename."""
    assert slug_to_filename("gh:owner_repo_42") == "gh_owner_repo_42"


def test_slug_to_filename_ado_with_slash():
    """Azure slug with : and / produces a flat valid filename."""
    result = slug_to_filename("ado:natedorr_testProject/testProject_70")
    assert ":" not in result
    assert "/" not in result
    assert result == "ado_natedorr_testProject_testProject_70"


def test_slug_to_filename_ado_standard():
    """Standard Azure slug (no slash) only replaces the colon."""
    assert slug_to_filename("ado:my-org_my-proj_my-repo_7") == "ado_my-org_my-proj_my-repo_7"


def test_slug_to_filename_idempotent():
    """Calling slug_to_filename twice should produce the same result."""
    slug = "ado:org/proj/repo_5"
    assert slug_to_filename(slug_to_filename(slug)) == slug_to_filename(slug)


def test_slug_to_filename_no_special_chars():
    """Slug without : or / should pass through unchanged."""
    assert slug_to_filename("plain_slug_123") == "plain_slug_123"


# ---------------------------------------------------------------------------
# Edge cases for _get_autoswe_status
# ---------------------------------------------------------------------------

def test_get_autoswe_status_multiple_autoswe_labels():
    """If multiple autoswe: labels exist, return the first one found."""
    labels = [{"name": "autoswe:pending"}, {"name": "autoswe:fixed"}]
    assert _get_autoswe_status(labels) == "pending"


def test_get_autoswe_status_only_non_autoswe_labels():
    labels = [{"name": "bug"}, {"name": "autoswe-old"}, {"name": "enhancement"}]
    assert _get_autoswe_status(labels) is None


def test_get_autoswe_status_empty_labels():
    assert _get_autoswe_status([]) is None


# ---------------------------------------------------------------------------
# @mention trigger (Feature D)
# ---------------------------------------------------------------------------

def test_parse_mention_default_bot():
    """@autoswe <guidance> should be parsed as /fix with guidance."""
    result = parse_slash_command("@autoswe make tests pass")
    assert result == ("/fix", "make tests pass", None)


def test_parse_mention_custom_bot():
    """@mybot <guidance> should match when bot_name='mybot'."""
    result = parse_slash_command("@mybot fix the bug", bot_name="mybot")
    assert result == ("/fix", "fix the bug", None)


def test_parse_mention_wrong_bot_name():
    """@otherbot should not match when bot_name='autoswe'."""
    result = parse_slash_command("@otherbot fix this")
    assert result is None


def test_parse_mention_case_insensitive():
    """@AUTOSWE should match (case insensitive)."""
    result = parse_slash_command("@AUTOSWE fix the thing")
    assert result == ("/fix", "fix the thing", None)


def test_parse_mention_in_multiline():
    """@mention in a multiline comment should be found."""
    text = "This is broken.\n@autoswe please fix the tests\nThanks!"
    result = parse_slash_command(text)
    assert result == ("/fix", "please fix the tests", None)


def test_parse_mention_lower_priority_than_slash():
    """Slash command takes priority over @mention."""
    text = "/plan\n@autoswe fix it"
    result = parse_slash_command(text)
    assert result == ("/plan", None, None)


def test_parse_mention_no_guidance():
    """@autoswe alone without guidance should not match."""
    result = parse_slash_command("@autoswe")
    assert result is None


def test_parse_mention_with_hyphenated_bot():
    """@my-bot should match when bot_name='my-bot'."""
    result = parse_slash_command("@my-bot do the thing", bot_name="my-bot")
    assert result == ("/fix", "do the thing", None)


# ---------------------------------------------------------------------------
# Batch 1 — Slash-command parsing edge cases (roadmap hole-closing)
# ---------------------------------------------------------------------------

def test_parse_backtick_wrapped_command_ignored():
    """Commands in inline code (backtick-wrapped) parsing behavior.

    The parser strips a single leading backtick and tries to match.
    - `` `/fix` `` (single backtick) → stripped to `/fix`, matches
    - `` Post `/retry` to try again `` → not at line start, ignored
    - `` ```/retry ``` `` (triple backtick) → stripped one ` → `` `/retry `` → no match
    """
    # Single backtick prefix: stripped, command matches
    result = parse_slash_command("`/fix`")
    assert result == ("/fix", None, None)

    # Embedded in text: correctly ignored (not at line start)
    result = parse_slash_command("Post `/retry` to try again")
    assert result is None

    # Triple backtick: after stripping one ` still starts with ` → no match
    result = parse_slash_command("```/retry```")
    assert result is None

    # Backtick-wrapped command at line start with closing backtick
    result = parse_slash_command("`/plan`")
    assert result == ("/plan", None, None)


def test_parse_multiline_guidance():
    """Guidance text spanning multiple lines: only the command line is parsed."""
    text = "/fix with performance focus\n\nAlso check memory usage.\nLook at CPU too."
    cmd, guidance, branch = parse_slash_command(text)
    assert cmd == "/fix"
    assert guidance == "performance focus"
    assert branch is None


def test_parse_guidance_with_special_chars():
    """Guidance containing special characters should be preserved."""
    cmd, guidance, _ = parse_slash_command("/fix with <special> & 'chars' \\and/slashes")
    assert cmd == "/fix"
    assert "<special>" in guidance
    assert "&" in guidance


def test_parse_guidance_with_unicode():
    """Guidance with unicode emojis and symbols should pass through."""
    cmd, guidance, _ = parse_slash_command("/fix with 🚀 rocket and 中文")
    assert cmd == "/fix"
    assert "🚀" in guidance
    assert "中文" in guidance


def test_parse_branch_only_no_guidance():
    """/plan --branch develop with nothing after should have no guidance."""
    cmd, guidance, branch = parse_slash_command("/plan --branch develop")
    assert cmd == "/plan"
    assert guidance is None
    assert branch == "develop"


def test_parse_branch_with_dots():
    """/plan --branch my.feature/branch handles dots and slashes."""
    cmd, _, branch = parse_slash_command("/plan --branch my.feature/branch")
    assert branch == "my.feature/branch"


def test_parse_command_only_backtick_no_closing():
    """/plan with unclosed backtick should still parse."""
    cmd, _, _ = parse_slash_command("`/plan")
    assert cmd == "/plan"


def test_multiple_backticks_at_start():
    """Multiple leading backticks: only first is stripped, second prevents match."""
    result = parse_slash_command("```/retry")
    # After stripping first backtick, line starts with ` which prevents regex match
    assert result is None


def test_parse_command_trailing_spaces():
    """Command with trailing whitespace should parse cleanly."""
    cmd, guidance, branch = parse_slash_command("/fix   ")
    assert cmd == "/fix"
    assert guidance is None
    assert branch is None


def test_parse_fix_with_literal_word_as_guidance():
    """/fix with (no space after 'with') treats 'with' as guidance text, not keyword.

    The 'with' keyword only strips when followed by a space. Bare 'with'
    is captured as guidance — documents the actual behavior.
    """
    cmd, guidance, _ = parse_slash_command("/fix with")
    assert cmd == "/fix"
    assert guidance == "with"


def test_parse_fix_with_space_after_with():
    """/fix with <text> correctly strips the 'with' keyword."""
    cmd, guidance, _ = parse_slash_command("/fix with some text")
    assert cmd == "/fix"
    assert guidance == "some text"


def test_parse_fix_with_only_space_after():
    """/fix with  (trailing spaces) treats 'with' as guidance.

    The parser strips rest before checking 'with ' keyword, so trailing
    spaces are lost. 'with' becomes guidance text. Only 'with <text>'
    triggers the keyword strip.
    """
    cmd, guidance, _ = parse_slash_command("/fix with  ")
    assert cmd == "/fix"
    assert guidance == "with"


def test_parse_fix_with_keyword_case_insensitive():
    """The 'with' keyword check is case-insensitive."""
    cmd, guidance, _ = parse_slash_command("/fix With some guidance")
    assert cmd == "/fix"
    assert guidance == "some guidance"


def test_parse_command_in_code_block():
    """Commands inside markdown code blocks are still matched line-by-line.

    The parser doesn't understand code block fencing — it matches any line
    starting with a command. This documents the current behavior.
    """
    text = "```\n/plan\n```"
    cmd, _, _ = parse_slash_command(text)
    # /plan is at line start, so it matches even inside a code block
    assert cmd == "/plan"


def test_parse_last_command_wins_across_lines():
    """When multiple commands appear on different lines, last one wins."""
    text = "/plan\n/fix\n/pr"
    cmd, _, _ = parse_slash_command(text)
    assert cmd == "/pr"


def test_parse_retry_with_extra_text():
    """/retry with trailing text captures text as guidance."""
    cmd, guidance, _ = parse_slash_command("/retry with different approach")
    assert cmd == "/retry"
    assert guidance == "different approach"


def test_parse_sync_with_extra_text():
    """/sync with trailing text captures text as guidance."""
    cmd, guidance, _ = parse_slash_command("/sync to main")
    assert cmd == "/sync"
    assert guidance == "to main"


def test_parse_command_tab_separator():
    """Command with tab separator should still parse guidance."""
    cmd, guidance, _ = parse_slash_command("/fix\tsome guidance")
    assert cmd == "/fix"
    assert guidance == "some guidance"


def test_parse_plan_branch_on_subsequent_lines_ignored():
    """--branch on a separate line from /plan is NOT picked up.

    The parser looks for --branch on the same line as the command.
    """
    text = "/plan\n--branch develop"
    cmd, guidance, branch = parse_slash_command(text)
    assert cmd == "/plan"
    assert branch is None  # --branch is on a different line


# ---------------------------------------------------------------------------
# _normalize_body (T7 DRY refactor)
# ---------------------------------------------------------------------------

def test_normalize_body_strips_formatting():
    """_normalize_body removes backticks, asterisks, underscores, tildes."""
    assert _normalize_body("`bold` *italic* _under~_ ~strike~") == "bold italic under strike"


def test_normalize_body_lowercase():
    """_normalize_body lowercases the input."""
    assert _normalize_body("HELLO World") == "hello world"


def test_normalize_body_collapses_whitespace():
    """_normalize_body collapses runs of whitespace into a single space."""
    assert _normalize_body("hello   world\n\nfoo") == "hello world foo"


def test_normalize_body_empty():
    """_normalize_body handles empty string."""
    assert _normalize_body("") == ""


def test_normalize_body_combined():
    """_normalize_body handles the real-world completion pattern."""
    body = "``Completed with command `/fix```"
    result = _normalize_body(body)
    assert "completed with command" in result


# ---------------------------------------------------------------------------
# Accessors with CommentLike type alias (T8 typing)
# ---------------------------------------------------------------------------

def test_get_body_dict():
    """_get_body works with dict-shaped comment."""
    assert _get_body({"body": "hello"}) == "hello"
    assert _get_body({"body": None}) == ""
    assert _get_body({}) == ""


def test_get_id_dict():
    """_get_id works with dict-shaped comment."""
    assert _get_id({"id": 42}) == 42
    assert _get_id({}) is None


def test_get_is_bot_dict():
    """_get_is_bot works with dict-shaped comment."""
    assert _get_is_bot({"is_bot": True}) is True
    assert _get_is_bot({}) is False
