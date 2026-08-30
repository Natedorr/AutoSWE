"""Tests for the agent-generated commit message (issue #139).

Covers two things:
1. ``_parse_commit_message`` — the tolerant parser for the <AUTOSWE_COMMIT> block.
2. ``run_fix`` / ``resume_fix`` — that the parsed subject becomes the commit
   subject (no ``autoswe:`` prefix) with a ``Fixes #N`` trailer, and that the
   issue-title fallback kicks in when the block is missing or malformed.
"""

from contextlib import ExitStack
from unittest.mock import patch

from autoswe.harness.coder import _parse_commit_message
from autoswe.harness.runner import RunResult


def _r(text, session_id="sess", subtype="success"):
    return RunResult(text, session_id, subtype)


def make_task(title="Fix pagination bug"):
    return {
        "id": "o_r_1",
        "owner": "o",
        "repo": "r",
        "issue_number": 1,
        "title": title,
        "body": "/fix",
        "base_branch": "master",
        "session_id": None,
        "_token": "ghp_fake",
    }


# ---------------------------------------------------------------------------
# _parse_commit_message
# ---------------------------------------------------------------------------


def test_parse_commit_message_happy_path():
    text = (
        "Did some things.\n\n"
        "<AUTOSWE_COMMIT>\n"
        "subject: Add retry backoff to poller\n"
        "body:\n"
        "Adds a bounded retry loop with exponential backoff.\n"
        "Gives up after 5 attempts.\n"
        "</AUTOSWE_COMMIT>\n"
    )
    subject, body = _parse_commit_message(text)
    assert subject == "Add retry backoff to poller"
    assert "bounded retry loop" in body
    assert "5 attempts" in body


def test_parse_commit_message_missing_block():
    assert _parse_commit_message("just prose, no block") == (None, None)


def test_parse_commit_message_empty_input():
    assert _parse_commit_message("") == (None, None)
    assert _parse_commit_message(None) == (None, None)


def test_parse_commit_message_empty_subject_falls_to_none():
    text = (
        "<AUTOSWE_COMMIT>\n"
        "subject:\n"
        "body:\n"
        "some body\n"
        "</AUTOSWE_COMMIT>\n"
    )
    subject, body = _parse_commit_message(text)
    # Empty subject → None (caller falls back to issue title); body preserved.
    assert subject is None
    assert body == "some body"


def test_parse_commit_message_whitespace_subject_falls_to_none():
    text = (
        "<AUTOSWE_COMMIT>\n"
        "subject:    \n"
        "body:\n"
        "body only\n"
        "</AUTOSWE_COMMIT>\n"
    )
    subject, body = _parse_commit_message(text)
    assert subject is None
    assert body == "body only"


def test_parse_commit_message_subject_only_no_body():
    text = "<AUTOSWE_COMMIT>\nsubject: Fix off-by-one\n</AUTOSWE_COMMIT>\n"
    subject, body = _parse_commit_message(text)
    assert subject == "Fix off-by-one"
    assert body is None


def test_parse_commit_message_body_inline_and_multiline():
    # `body:` with content on the same line, then more lines.
    text = (
        "<AUTOSWE_COMMIT>\n"
        "subject: Inline body test\n"
        "body: first line after the key\n"
        "second line\n"
        "</AUTOSWE_COMMIT>\n"
    )
    subject, body = _parse_commit_message(text)
    assert subject == "Inline body test"
    assert body == "first line after the key\nsecond line"


def test_parse_commit_message_case_insensitive_keys():
    text = "<AUTOSWE_COMMIT>\nSubject: Fix it\nBODY:\nthe body\n</AUTOSWE_COMMIT>\n"
    subject, body = _parse_commit_message(text)
    assert subject == "Fix it"
    assert body == "the body"


def test_parse_commit_message_subject_containing_body_colon():
    # Regression: a subject that contains the literal substring "body:" must
    # not corrupt the extracted body. Only a line that STARTS with "body:"
    # opens the body.
    text = (
        "<AUTOSWE_COMMIT>\n"
        "subject: Add body:logging to the request layer\n"
        "body:\n"
        "Real body line one.\n"
        "Real body line two.\n"
        "</AUTOSWE_COMMIT>\n"
    )
    subject, body = _parse_commit_message(text)
    assert subject == "Add body:logging to the request layer"
    assert body == "Real body line one.\nReal body line two."
    assert "body:" not in (body or "").split("\n")[0]  # no stray key line leaked in


# ---------------------------------------------------------------------------
# run_fix / resume_fix integration — commit message via commit_and_push spy
# ---------------------------------------------------------------------------

COMMIT_RESULT = {"committed": True, "commit_sha": "abc1234", "branch": "autoswe/issue-1"}


def _commit_msg_spy(commit_msgs):
    def _spy(wt, owner, repo, issue_num, msg, *args, **kwargs):
        commit_msgs.append(msg)
        return COMMIT_RESULT

    return _spy


def _fetch_comments_patch():
    return patch("autoswe.tracking.api._fetch_comments", return_value=[])


def test_run_fix_uses_generated_subject_no_autoswe_prefix(tmp_path):
    task = make_task(title="Fix pagination bug")
    agent_text = (
        "Fixed the off-by-one.\n"
        "<AUTOSWE_COMMIT>\n"
        "subject: Fix off-by-one in pagination cursor\n"
        "body:\n"
        "The cursor skipped the last page when total % page_size == 0.\n"
        "Clamps the offset to the available range.\n"
        "</AUTOSWE_COMMIT>\n"
    )
    commit_msgs = []

    def fake_run(prompt, **kwargs):
        return _r(agent_text)

    with ExitStack() as stack:
        stack.enter_context(patch("autoswe.harness.coder.create_worktree", return_value=tmp_path))
        stack.enter_context(patch("autoswe.harness.coder.fast_forward_worktree", return_value=True))
        stack.enter_context(_fetch_comments_patch())
        stack.enter_context(patch("autoswe.harness.runner.run", side_effect=fake_run))
        stack.enter_context(patch("autoswe.harness.coder.commit_and_push", side_effect=_commit_msg_spy(commit_msgs)))
        from autoswe.harness.coder import run_fix
        run_fix(task, cfg={})

    assert len(commit_msgs) == 1
    msg = commit_msgs[0]
    first_line = msg.splitlines()[0]
    assert first_line == "Fix off-by-one in pagination cursor"
    assert not msg.startswith("autoswe:")
    assert "Fixes #1" in msg
    assert "skipped the last page" in msg


def test_run_fix_falls_back_to_issue_title_when_block_missing(tmp_path):
    task = make_task(title="Fix pagination bug")
    agent_text = "I made the change. No commit block emitted."
    commit_msgs = []

    def fake_run(prompt, **kwargs):
        return _r(agent_text)

    with ExitStack() as stack:
        stack.enter_context(patch("autoswe.harness.coder.create_worktree", return_value=tmp_path))
        stack.enter_context(patch("autoswe.harness.coder.fast_forward_worktree", return_value=True))
        stack.enter_context(_fetch_comments_patch())
        stack.enter_context(patch("autoswe.harness.runner.run", side_effect=fake_run))
        stack.enter_context(patch("autoswe.harness.coder.commit_and_push", side_effect=_commit_msg_spy(commit_msgs)))
        from autoswe.harness.coder import run_fix
        run_fix(task, cfg={})

    assert len(commit_msgs) == 1
    msg = commit_msgs[0]
    assert msg.splitlines()[0] == "Fix pagination bug"
    assert not msg.startswith("autoswe:")
    assert "Fixes #1" in msg
    # Body falls back to the agent's raw summary.
    assert "I made the change" in msg


def test_run_fix_falls_back_to_issue_title_when_subject_empty(tmp_path):
    task = make_task(title="Fix pagination bug")
    agent_text = (
        "<AUTOSWE_COMMIT>\n"
        "subject:\n"
        "body:\n"
        "a body with no subject\n"
        "</AUTOSWE_COMMIT>\n"
    )
    commit_msgs = []

    def fake_run(prompt, **kwargs):
        return _r(agent_text)

    with ExitStack() as stack:
        stack.enter_context(patch("autoswe.harness.coder.create_worktree", return_value=tmp_path))
        stack.enter_context(patch("autoswe.harness.coder.fast_forward_worktree", return_value=True))
        stack.enter_context(_fetch_comments_patch())
        stack.enter_context(patch("autoswe.harness.runner.run", side_effect=fake_run))
        stack.enter_context(patch("autoswe.harness.coder.commit_and_push", side_effect=_commit_msg_spy(commit_msgs)))
        from autoswe.harness.coder import run_fix
        run_fix(task, cfg={})

    assert commit_msgs[0].splitlines()[0] == "Fix pagination bug"


def test_resume_fix_uses_generated_subject(tmp_path):
    task = make_task(title="Fix pagination bug")
    task["session_id"] = "sess-previous"
    agent_text = (
        "<AUTOSWE_COMMIT>\n"
        "subject: Add cursor clamping to paginator\n"
        "body:\n"
        "Clamps the offset before the query.\n"
        "</AUTOSWE_COMMIT>\n"
    )
    commit_msgs = []

    def fake_run(prompt, **kwargs):
        return _r(agent_text, "sess-new")

    with ExitStack() as stack:
        stack.enter_context(patch("autoswe.harness.coder.create_worktree", return_value=tmp_path))
        stack.enter_context(patch("autoswe.harness.coder.fast_forward_worktree", return_value=True))
        stack.enter_context(_fetch_comments_patch())
        stack.enter_context(patch("autoswe.harness.runner.run", side_effect=fake_run))
        stack.enter_context(patch("autoswe.harness.coder.commit_and_push", side_effect=_commit_msg_spy(commit_msgs)))
        from autoswe.harness.coder import resume_fix
        resume_fix(task, "Use the cursor approach.", {}, {})

    assert len(commit_msgs) == 1
    msg = commit_msgs[0]
    assert msg.splitlines()[0] == "Add cursor clamping to paginator"
    assert not msg.startswith("autoswe:")
    assert "Fixes #1" in msg


def test_resume_fix_falls_back_to_issue_title(tmp_path):
    task = make_task(title="Fix pagination bug")
    task["session_id"] = "sess-previous"
    agent_text = "Continued and finished. No block."
    commit_msgs = []

    def fake_run(prompt, **kwargs):
        return _r(agent_text, "sess-new")

    with ExitStack() as stack:
        stack.enter_context(patch("autoswe.harness.coder.create_worktree", return_value=tmp_path))
        stack.enter_context(patch("autoswe.harness.coder.fast_forward_worktree", return_value=True))
        stack.enter_context(_fetch_comments_patch())
        stack.enter_context(patch("autoswe.harness.runner.run", side_effect=fake_run))
        stack.enter_context(patch("autoswe.harness.coder.commit_and_push", side_effect=_commit_msg_spy(commit_msgs)))
        from autoswe.harness.coder import resume_fix
        resume_fix(task, "proceed", {}, {})

    assert commit_msgs[0].splitlines()[0] == "Fix pagination bug"
