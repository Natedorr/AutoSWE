"""Provider adapter tests -- the single read_api / apply_effect pair.

issue #168 (F-04): there is now one autoswe/providers/adapter.py with a single
read_api and apply_effect for every provider. The only provider-specific
behaviour is comment-body normalisation, delegated to
tracker.normalize_comment_body (GitHub: identity; Azure: HTML/entity stripping
+ content-based bot detection). These tests exercise that real hook while
mocking only list_open_issues / fetch_comments, and are parametrised over both
providers so the shared read/write path stays covered.

Coverage:
  read_api (input shape lockdown)
    - azure_div_wrapped_comment_unwrapped  - Bug 1 regression
    - azure_html_entities_decoded          - entity-encoded text decoded
    - azure_bot_marker_preserved           - bot comments keep marker after strip
    - clean_comment_passthrough            - clean text passes through unchanged
    - fetch policy (skip/changed/force/new/no-timestamp) - both providers

  apply_effect (output shape lockdown)
    - set_status / post_comment / patch_queue - both providers
    - create_pr idempotency (existing -> skip) - both providers
    - create_pr CI gate (defer on pending/failing, pass on success/none,
      gate disabled, no-cfg) - both providers
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from autoswe.orch.types import Effect
from autoswe.providers.adapter import apply_effect, read_api, read_ci, render_ci_status
from autoswe.providers.azure.tracker import AzureTracker
from autoswe.providers.base import CIStatus, NormalizedComment, NormalizedIssue, PRResult
from autoswe.providers.github.tracker import GitHubTracker
from autoswe.tracking.comments import BOT_MARKER

PROVIDERS = ["github", "azure"]

# Simulated raw comment body from Azure DevOps rich-text comment editor.
# ADO wraps the text in <div> tags when the user posts from the rich editor.
_AZURE_DIV_WRAPPED = "<div>/plan --branch dev</div>"
# Simulated comment with HTML entities (ADO rich-text encoding).
_AZURE_ENTITIES = "&#47;fix with &#45;&#45;focus"


def _repo_cfg(provider: str) -> dict:
    """Minimal repo_cfg for the named provider."""
    if provider == "azure":
        return {"provider": "azure", "org": "natedorr", "project": "testProject",
                "repo": "testProject", "pat": "fake"}
    return {"provider": "github", "owner": "owner", "repo": "repo", "pat": "fake"}


def _make_issue(number: int, last_updated: str | None = None) -> NormalizedIssue:
    owner, repo = ("natedorr", "testProject") if last_updated is None else ("o", "r")
    return NormalizedIssue(
        number=number, title="Test issue", body="Body",
        owner=owner, repo=repo, last_updated=last_updated,
    )


def _make_comment(body: str, author_login: str = "AUTHOR") -> NormalizedComment:
    return NormalizedComment(body=body, created_at="2026-01-01T00:00:00Z",
                             author_login=author_login)


def _make_tracker(provider: str, comments: list[NormalizedComment]) -> MagicMock:
    """A real tracker whose read side returns canned data; its real
    normalize_comment_body hook is what we want to exercise."""
    repo_cfg = _repo_cfg(provider)
    tracker = (AzureTracker if provider == "azure" else GitHubTracker)(repo_cfg)
    mock = MagicMock(wraps=tracker)
    mock.list_open_issues = MagicMock(return_value=[_make_issue(42)])
    mock.fetch_comments = MagicMock(return_value=comments)
    # Class attributes are not proxied by wraps; copy the real capability so
    # read_api's comment-fetch policy is exercised per-provider.
    mock.comments_bump_updated = tracker.comments_bump_updated
    return mock


def _run_read(tracker, **kwargs) -> dict:
    """Run the single shared read_api. read_api never resolves a VCS, so this
    needs no patching."""
    return read_api(tracker, **kwargs)


# ---------------------------------------------------------------------------
# read_api -- comment body normalisation (the one provider-specific hook)
# ---------------------------------------------------------------------------

def test_azure_div_wrapped_comment_unwrapped():
    """Bug 1 regression: ADO rich-text wraps user comments in <div>.

    After read_api, the comment body should have the <div> stripped so
    slash-command parsing sees clean text.
    """
    comments = [_make_comment(_AZURE_DIV_WRAPPED)]
    api_states = _run_read(_make_tracker("azure", comments))
    body = api_states[42].comments[0].body
    assert "/plan --branch dev" in body
    assert "<div>" not in body


def test_azure_html_entities_decoded():
    """ADO rich-text may encode characters as HTML entities."""
    comments = [_make_comment(_AZURE_ENTITIES)]
    api_states = _run_read(_make_tracker("azure", comments))
    body = api_states[42].comments[0].body
    assert "/fix with --focus" in body
    assert "&#45;" not in body
    assert "&#47;" not in body


def test_azure_bot_marker_preserved():
    """Bot comments should keep the autoswe-bot marker after HTML strip."""
    bot_body = "<div>## Plan\n\nSome plan text\n</div>\n" + BOT_MARKER
    comments = [_make_comment(bot_body, author_login="BOT")]
    api_states = _run_read(_make_tracker("azure", comments))
    body = api_states[42].comments[0].body
    assert BOT_MARKER in body
    assert "<div>" not in body


@pytest.mark.parametrize("provider", PROVIDERS)
def test_clean_comment_passthrough(provider):
    """A comment that is already clean text should come out unchanged."""
    clean = "/plan --branch main"
    comments = [_make_comment(clean)]
    api_states = _run_read(_make_tracker(provider, comments))
    assert api_states[42].comments[0].body == clean


# ---------------------------------------------------------------------------
# read_api -- fetch policy (provider-agnostic, run on both)
# ---------------------------------------------------------------------------

def _single_issue_tracker(provider: str, last_updated: str | None,
                          comments: list | None = None) -> MagicMock:
    issue = _make_issue(42, last_updated=last_updated)
    tracker = _make_tracker(provider, comments or [])
    tracker.list_open_issues = MagicMock(return_value=[issue])
    return tracker


@pytest.mark.parametrize("provider", PROVIDERS)
def test_read_api_skip_unchanged_issue(provider):
    """When prev_updated matches, comments are skipped — but ONLY on providers
    where a comment bumps the updated timestamp (GitHub)."""
    t = _single_issue_tracker(provider, "2026-01-01T00:00:00Z")
    api_states = _run_read(t, prev_updated={42: "2026-01-01T00:00:00Z"})
    if provider == "github":
        assert api_states[42].comments_fetched is False
        assert api_states[42].comments == ()
        t.fetch_comments.assert_not_called()
    else:
        # Azure: a comment does not bump System.ChangedDate, so an unchanged
        # timestamp must NOT suppress the fetch or a new slash command is lost.
        assert api_states[42].comments_fetched is True
        t.fetch_comments.assert_called_once()


def test_read_api_azure_comment_after_tag_write_still_fetched():
    """Regression: on Azure the poller stalls if a comment-only change is
    treated as "unchanged".

    Sequence that reproduced the live bug (issues 188/189/190): autoSWE writes
    a status tag -> ADO advances System.ChangedDate -> the poller stores it as
    last_updated -> the user posts a new `/fix` -> ADO does NOT advance
    ChangedDate again -> read_api sees last_updated == stored and skips the
    comment fetch -> the command is never seen and the task never moves.

    With comments_bump_updated=False the fetch must happen even though the
    timestamp is unchanged, so the new comment (and its slash command) is read.
    """
    t = _single_issue_tracker(
        "azure", "2026-09-11T16:53:09.207Z",
        comments=[_make_comment("/fix", author_login="OWNER")],
    )
    api_states = _run_read(t, prev_updated={42: "2026-09-11T16:53:09.207Z"})
    assert api_states[42].comments_fetched is True
    t.fetch_comments.assert_called_once()
    assert api_states[42].comments[0].body == "/fix"


@pytest.mark.parametrize("provider", PROVIDERS)
def test_read_api_fetch_when_timestamp_changed(provider):
    """When prev_updated differs from issue.last_updated, fetch comments."""
    t = _single_issue_tracker(provider, "2026-01-02T00:00:00Z")
    api_states = _run_read(t, prev_updated={42: "2026-01-01T00:00:00Z"})
    assert api_states[42].comments_fetched is True
    t.fetch_comments.assert_called_once()


@pytest.mark.parametrize("provider", PROVIDERS)
def test_read_api_force_fetch_overrides_skip(provider):
    """force_fetch set overrides a matching timestamp."""
    t = _single_issue_tracker(provider, "2026-01-01T00:00:00Z")
    api_states = _run_read(t,
                           prev_updated={42: "2026-01-01T00:00:00Z"},
                           force_fetch={42})
    assert api_states[42].comments_fetched is True
    t.fetch_comments.assert_called_once()


@pytest.mark.parametrize("provider", PROVIDERS)
def test_read_api_new_issue_always_fetched(provider):
    """An issue not in prev_updated should always be fetched."""
    t = _single_issue_tracker(provider, "2026-01-01T00:00:00Z")
    api_states = _run_read(t, prev_updated={})
    assert api_states[42].comments_fetched is True
    t.fetch_comments.assert_called_once()


@pytest.mark.parametrize("provider", PROVIDERS)
def test_read_api_no_last_updated_always_fetched(provider):
    """When issue has no last_updated, always fetch comments."""
    t = _single_issue_tracker(provider, None)
    api_states = _run_read(t, prev_updated={42: "2026-01-01T00:00:00Z"})
    assert api_states[42].comments_fetched is True
    t.fetch_comments.assert_called_once()


@pytest.mark.parametrize("provider", PROVIDERS)
def test_read_api_backward_compat_no_prev_updated(provider):
    """Without prev_updated, all issues are fetched (backward compat)."""
    t = _single_issue_tracker(provider, "2026-01-01T00:00:00Z")
    api_states = _run_read(t)
    assert api_states[42].comments_fetched is True
    t.fetch_comments.assert_called_once()


# ---------------------------------------------------------------------------
# apply_effect -- output shape lockdown (provider-agnostic, run on both)
# ---------------------------------------------------------------------------

def _run_apply(provider: str, tracker, effect, queue, issue_num, slug, cfg=None):
    """Run the single shared apply_effect. set_status/post_comment/patch_queue
    never resolve a VCS; only create_pr does (patched by the CI-gate tests)."""
    apply_effect(tracker, effect, _repo_cfg(provider), issue_num, queue, slug, cfg)


@pytest.mark.parametrize("provider", PROVIDERS)
def test_apply_effect_set_status(provider):
    """Effect(set_status) -> tracker.set_status with autoswe: prefix."""
    tracker = MagicMock()
    queue = {}
    effect = Effect(kind="set_status", status="planned")
    _run_apply(provider, tracker, effect, queue, 7, "gh__owner_repo_7")
    tracker.set_status.assert_called_once_with(7, "autoswe:planned")


@pytest.mark.parametrize("provider", PROVIDERS)
def test_apply_effect_post_comment(provider):
    """Effect(post_comment) -> tracker.post_comment called with the body."""
    tracker = MagicMock()
    queue = {}
    effect = Effect(kind="post_comment", body="Plan posted.\n" + BOT_MARKER)
    _run_apply(provider, tracker, effect, queue, 7, "gh__owner_repo_7")
    tracker.post_comment.assert_called_once_with(7, "Plan posted.\n" + BOT_MARKER)


@pytest.mark.parametrize("provider", PROVIDERS)
def test_apply_effect_patch_queue(provider):
    """Effect(patch_queue) -> queue[slug] updated in place."""
    tracker = MagicMock()
    queue = {"gh__owner_repo_7": {"autoswe_status": "pending", "last_consumed_reply_ts": ""}}
    effect = Effect(
        kind="patch_queue",
        queue_patch={"autoswe_status": "planned",
                     "last_consumed_reply_ts": "2026-01-01T00:00:00Z"},
    )
    _run_apply(provider, tracker, effect, queue, 7, "gh__owner_repo_7")
    assert queue["gh__owner_repo_7"]["autoswe_status"] == "planned"
    assert queue["gh__owner_repo_7"]["last_consumed_reply_ts"] == "2026-01-01T00:00:00Z"


# ---------------------------------------------------------------------------
# apply_effect -- create_pr idempotency (existing PR -> skip)
# ---------------------------------------------------------------------------

def _create_pr_effect():
    return Effect(
        kind="create_pr",
        pr_title="Fixes #1: Test",
        pr_body="Fixes #1",
        pr_head="autoswe/issue-1",
        pr_base="main",
    )


@pytest.mark.parametrize("provider", PROVIDERS)
def test_apply_effect_create_pr_no_existing(provider):
    """When no PR exists, apply_effect calls open_pull_request."""
    tracker = MagicMock()
    vcs = MagicMock()
    vcs.find_existing_pr.return_value = None
    with patch("autoswe.providers.adapter.get_vcs", return_value=vcs):
        _run_apply(provider, tracker, _create_pr_effect(), {}, 1, "gh__owner_repo_1")
    vcs.find_existing_pr.assert_called_once()
    vcs.open_pull_request.assert_called_once()


@pytest.mark.parametrize("provider", PROVIDERS)
def test_apply_effect_create_pr_existing_skipped(provider):
    """When a PR exists, apply_effect skips open_pull_request."""
    tracker = MagicMock()
    vcs = MagicMock()
    vcs.find_existing_pr.return_value = PRResult(
        url="https://github.com/o/r/pull/15", number=15,
    )
    with patch("autoswe.providers.adapter.get_vcs", return_value=vcs):
        _run_apply(provider, tracker, _create_pr_effect(), {}, 1, "gh__owner_repo_1")
    vcs.find_existing_pr.assert_called_once()
    vcs.open_pull_request.assert_not_called()


# ---------------------------------------------------------------------------
# apply_effect -- create_pr persists pr_number/pr_url on the queue entry
# (issue #193: the auto-PR path used to discard the PRResult entirely)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("provider", PROVIDERS)
def test_apply_effect_create_pr_new_persists_pr_identity(provider):
    """New PR created → pr_number/pr_url land on the queue entry."""
    tracker = MagicMock()
    vcs = MagicMock()
    vcs.find_existing_pr.return_value = None
    vcs.open_pull_request.return_value = PRResult(
        number=7, url="https://github.com/o/r/pull/7",
    )
    slug = "gh__owner_repo_1"
    queue = _queue_with_entry(provider, slug)
    with patch("autoswe.providers.adapter.get_vcs", return_value=vcs):
        _run_apply(provider, tracker, _create_pr_effect(), queue, 1, slug)
    vcs.open_pull_request.assert_called_once()
    assert queue[slug]["pr_number"] == 7
    assert queue[slug]["pr_url"] == "https://github.com/o/r/pull/7"


@pytest.mark.parametrize("provider", PROVIDERS)
def test_apply_effect_create_pr_existing_re_caches_pr_identity(provider):
    """Existing PR + empty queue identity (crash recovery) → re-cached."""
    tracker = MagicMock()
    vcs = MagicMock()
    vcs.find_existing_pr.return_value = PRResult(
        number=15, url="https://github.com/o/r/pull/15",
    )
    slug = "gh__owner_repo_1"
    queue = _queue_with_entry(provider, slug)
    queue[slug]["pr_number"] = None
    with patch("autoswe.providers.adapter.get_vcs", return_value=vcs):
        _run_apply(provider, tracker, _create_pr_effect(), queue, 1, slug)
    vcs.open_pull_request.assert_not_called()
    assert queue[slug]["pr_number"] == 15
    assert queue[slug]["pr_url"] == "https://github.com/o/r/pull/15"


@pytest.mark.parametrize("provider", PROVIDERS)
def test_apply_effect_create_pr_missing_identity_is_noop(provider):
    """PRResult without number/url must not write None over the queue entry."""
    tracker = MagicMock()
    vcs = MagicMock()
    vcs.find_existing_pr.return_value = PRResult(number=None, url="")
    slug = "gh__owner_repo_1"
    queue = _queue_with_entry(provider, slug)
    with patch("autoswe.providers.adapter.get_vcs", return_value=vcs):
        _run_apply(provider, tracker, _create_pr_effect(), queue, 1, slug)
    assert "pr_number" not in queue[slug]
    assert "pr_url" not in queue[slug]


# ---------------------------------------------------------------------------
# apply_effect -- create_pr calls ensure_links (issue #245 §1.4, edge E3)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("provider", PROVIDERS)
def test_apply_effect_create_pr_new_calls_ensure_links(provider):
    """A freshly-created PR triggers ensure_links(phase='pr_open')."""
    tracker = MagicMock()
    vcs = MagicMock()
    vcs.find_existing_pr.return_value = None
    vcs.open_pull_request.return_value = PRResult(number=7, url="https://x/pull/7")
    slug = "gh__owner_repo_1"
    queue = _queue_with_entry(provider, slug)
    with patch("autoswe.providers.adapter.get_vcs", return_value=vcs), \
         patch("autoswe.providers.adapter.ensure_links") as mock_ensure_links:
        _run_apply(provider, tracker, _create_pr_effect(), queue, 1, slug)
    mock_ensure_links.assert_called_once()
    _, kwargs = mock_ensure_links.call_args
    assert kwargs["phase"] == "pr_open"
    assert kwargs["vcs"] is vcs


@pytest.mark.parametrize("provider", PROVIDERS)
def test_apply_effect_create_pr_existing_calls_ensure_links(provider):
    """The idempotent existing-PR path also self-heals via ensure_links."""
    tracker = MagicMock()
    vcs = MagicMock()
    vcs.find_existing_pr.return_value = PRResult(number=15, url="https://x/pull/15")
    slug = "gh__owner_repo_1"
    queue = _queue_with_entry(provider, slug)
    with patch("autoswe.providers.adapter.get_vcs", return_value=vcs), \
         patch("autoswe.providers.adapter.ensure_links") as mock_ensure_links:
        _run_apply(provider, tracker, _create_pr_effect(), queue, 1, slug)
    mock_ensure_links.assert_called_once()


# ---------------------------------------------------------------------------
# apply_effect -- create_pr CI gate (no sync gate; already synced)
# ---------------------------------------------------------------------------

def _queue_with_entry(provider: str, slug: str) -> dict:
    return {slug: {"owner": "o", "repo": "r", "issue_number": 1}}


def _run_create_pr_ci(provider: str, ci_state, cfg):
    """Drive a create_pr through the CI gate; returns (vcs, tracker, queue, slug)."""
    tracker = MagicMock()
    vcs = MagicMock()
    vcs.find_existing_pr.return_value = None
    vcs.get_ci_status.return_value = CIStatus(state=ci_state)
    slug = "gh__owner_repo_1"
    queue = _queue_with_entry(provider, slug)
    with patch("autoswe.providers.adapter.get_vcs", return_value=vcs):
        _run_apply(provider, tracker, _create_pr_effect(), queue, 1, slug, cfg)
    return vcs, tracker, queue, slug


@pytest.mark.parametrize("provider", PROVIDERS)
def test_apply_effect_create_pr_deferred_when_ci_pending(provider):
    """CI pending -> PR creation deferred, deferral comment posted instead."""
    vcs, tracker, queue, slug = _run_create_pr_ci(provider, "pending", {"PR_REQUIRE_CI": True})
    vcs.open_pull_request.assert_not_called()
    tracker.post_comment.assert_called_once()
    assert "deferred" in tracker.post_comment.call_args[0][1].lower()
    # issue #245 §2.6: pr_deferred is recorded instead of asking for /pr again.
    assert queue[slug]["pr_deferred"] is True
    assert "Post `/pr` when ready" not in tracker.post_comment.call_args[0][1]


@pytest.mark.parametrize("provider", PROVIDERS)
def test_apply_effect_create_pr_deferred_when_ci_failing(provider):
    """CI failing -> PR creation deferred."""
    vcs, tracker, queue, slug = _run_create_pr_ci(provider, "failure", {"PR_REQUIRE_CI": True})
    vcs.open_pull_request.assert_not_called()
    tracker.post_comment.assert_called_once()
    assert queue[slug]["pr_deferred"] is True


@pytest.mark.parametrize("provider", PROVIDERS)
def test_apply_effect_create_pr_deferred_when_ci_error(provider):
    """CI state 'error' (API unconsultable) -> PR deferred, not shipped blind.

    Fail-safe: the default PR_CI_ERROR_POLICY=block refuses to open a PR when
    the CI status could not be read.
    """
    vcs, tracker, queue, slug = _run_create_pr_ci(provider, "error", {"PR_REQUIRE_CI": True})
    vcs.open_pull_request.assert_not_called()
    tracker.post_comment.assert_called_once()
    assert "PR_CI_ERROR_POLICY=block" in tracker.post_comment.call_args[0][1]
    assert queue[slug]["pr_deferred"] is True


@pytest.mark.parametrize("provider", PROVIDERS)
def test_apply_effect_create_pr_proceeds_when_ci_success(provider):
    """CI success -> PR created as normal."""
    vcs, tracker, queue, slug = _run_create_pr_ci(provider, "success", {"PR_REQUIRE_CI": True})
    vcs.open_pull_request.assert_called_once()
    tracker.post_comment.assert_not_called()
    assert "pr_deferred" not in queue[slug]


@pytest.mark.parametrize("provider", PROVIDERS)
def test_apply_effect_create_pr_proceeds_when_no_ci_configured(provider):
    """CI state 'none' (no checks configured) -> treated as pass, PR created."""
    vcs, tracker, queue, slug = _run_create_pr_ci(provider, "none", {"PR_REQUIRE_CI": True})
    vcs.open_pull_request.assert_called_once()


@pytest.mark.parametrize("provider", PROVIDERS)
def test_apply_effect_create_pr_ci_gate_disabled_ignores_failure(provider):
    """PR_REQUIRE_CI=False -> CI failure does not block PR creation."""
    vcs, tracker, queue, slug = _run_create_pr_ci(provider, "failure", {"PR_REQUIRE_CI": False})
    vcs.open_pull_request.assert_called_once()


@pytest.mark.parametrize("provider", PROVIDERS)
def test_apply_effect_create_pr_no_gate_without_cfg(provider):
    """cfg=None skips gating entirely (legacy call signature) -- backward compatible."""
    tracker = MagicMock()
    vcs = MagicMock()
    vcs.find_existing_pr.return_value = None
    vcs.get_ci_status.return_value = CIStatus(state="failure")
    slug = "gh__owner_repo_1"
    queue = _queue_with_entry(provider, slug)
    with patch("autoswe.providers.adapter.get_vcs", return_value=vcs):
        _run_apply(provider, tracker, _create_pr_effect(), queue, 1, slug)
    vcs.get_ci_status.assert_not_called()
    vcs.open_pull_request.assert_called_once()


# ---------------------------------------------------------------------------
# read_ci -- eligibility, throttle, queue plumbing (issue #245 plan §2.2)
# ---------------------------------------------------------------------------

def _task_entry(status: str = "fixed", **overrides) -> dict:
    entry = {
        "id": "o/r#1", "issue_number": 1, "autoswe_status": status,
        "plan_branch": "autoswe/issue-1",
    }
    entry.update(overrides)
    return entry


def _now() -> datetime:
    return datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_read_ci_eligible_and_due_calls_api_and_caches():
    vcs = MagicMock()
    vcs.get_ci_status.return_value = CIStatus(state="success", summary="ok")
    task = _task_entry()
    result = read_ci(vcs, task, {}, {}, now=_now())
    assert result == CIStatus(state="success", summary="ok")
    vcs.get_ci_status.assert_called_once_with("autoswe/issue-1")
    assert task["ci_last_checked"] == "2026-01-01T00:00:00Z"
    assert task["ci_status"] == {
        "state": "success", "head_sha": None, "stale": False, "url": None,
        "total": 0, "failing": [], "neutral": 0, "pending_count": 0, "summary": "ok",
    }


@pytest.mark.parametrize("status", ["pending", "planning", "fixing", "reviewed", "waiting"])
def test_read_ci_ineligible_status_returns_none_no_call(status):
    vcs = MagicMock()
    task = _task_entry(status=status)
    assert read_ci(vcs, task, {}, {}, now=_now()) is None
    vcs.get_ci_status.assert_not_called()
    assert "ci_last_checked" not in task


def test_read_ci_no_branch_returns_none_no_call():
    vcs = MagicMock()
    vcs.branch_name.side_effect = RuntimeError("boom")
    task = _task_entry(plan_branch=None)
    assert read_ci(vcs, task, {}, {}, now=_now()) is None
    vcs.get_ci_status.assert_not_called()


def test_read_ci_falls_back_to_vcs_branch_name_when_no_plan_branch():
    vcs = MagicMock()
    vcs.branch_name.return_value = "autoswe/issue-1"
    vcs.get_ci_status.return_value = CIStatus(state="none")
    task = _task_entry(plan_branch=None)
    read_ci(vcs, task, {}, {}, now=_now())
    vcs.branch_name.assert_called_once_with(1)
    vcs.get_ci_status.assert_called_once_with("autoswe/issue-1")


def test_read_ci_disabled_by_cfg_returns_none():
    vcs = MagicMock()
    task = _task_entry()
    assert read_ci(vcs, task, {"CI_WATCH": False}, {}, now=_now()) is None
    vcs.get_ci_status.assert_not_called()


def test_read_ci_disabled_by_repo_override():
    vcs = MagicMock()
    task = _task_entry()
    assert read_ci(vcs, task, {"CI_WATCH": True}, {"ci_watch": False}, now=_now()) is None
    vcs.get_ci_status.assert_not_called()


def test_read_ci_throttled_within_interval_skips_api_call():
    vcs = MagicMock()
    task = _task_entry(ci_last_checked="2026-01-01T00:00:00Z")
    later = _now() + timedelta(seconds=60)
    result = read_ci(vcs, task, {"CI_POLL_INTERVAL_SEC": 120}, {}, now=later)
    assert result is None
    vcs.get_ci_status.assert_not_called()
    # Consecutive polls within the interval must not call the API repeatedly.
    result2 = read_ci(vcs, task, {"CI_POLL_INTERVAL_SEC": 120}, {}, now=later + timedelta(seconds=30))
    assert result2 is None
    vcs.get_ci_status.assert_not_called()


def test_read_ci_calls_again_once_interval_elapsed():
    vcs = MagicMock()
    vcs.get_ci_status.return_value = CIStatus(state="failure", summary="boom")
    task = _task_entry(ci_last_checked="2026-01-01T00:00:00Z")
    later = _now() + timedelta(seconds=121)
    result = read_ci(vcs, task, {"CI_POLL_INTERVAL_SEC": 120}, {}, now=later)
    assert result == CIStatus(state="failure", summary="boom")
    vcs.get_ci_status.assert_called_once()


def test_read_ci_repo_override_interval_beats_cfg():
    vcs = MagicMock()
    task = _task_entry(ci_last_checked="2026-01-01T00:00:00Z")
    later = _now() + timedelta(seconds=90)
    # cfg says 60s (would be due); repo override says 300s (not due yet).
    result = read_ci(vcs, task, {"CI_POLL_INTERVAL_SEC": 60}, {"ci_poll_interval_sec": 300}, now=later)
    assert result is None
    vcs.get_ci_status.assert_not_called()


def test_read_ci_malformed_watermark_treated_as_due():
    vcs = MagicMock()
    vcs.get_ci_status.return_value = CIStatus(state="none")
    task = _task_entry(ci_last_checked="not-a-timestamp")
    assert read_ci(vcs, task, {}, {}, now=_now()) is not None
    vcs.get_ci_status.assert_called_once()


def test_read_ci_get_ci_status_exception_returns_none_no_crash():
    vcs = MagicMock()
    vcs.get_ci_status.side_effect = RuntimeError("network down")
    task = _task_entry()
    assert read_ci(vcs, task, {}, {}, now=_now()) is None
    assert "ci_last_checked" not in task


def test_render_ci_status_empty_when_never_checked():
    assert render_ci_status({}) == ""


def test_render_ci_status_renders_cached_observation():
    task = {
        "ci_status": {"state": "failure", "summary": "1 check(s) failing: build",
                       "url": "https://x/run/1", "stale": False},
        "ci_last_checked": "2026-01-01T00:00:00Z",
    }
    rendered = render_ci_status(task)
    assert "CI watch: failure" in rendered
    assert "1 check(s) failing: build" in rendered
    assert "https://x/run/1" in rendered
    assert "2026-01-01T00:00:00Z" in rendered


def test_render_ci_status_flags_stale():
    task = {"ci_status": {"state": "pending", "stale": True}}
    assert "CI watch: pending (stale)" in render_ci_status(task)
