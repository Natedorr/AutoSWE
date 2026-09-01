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

from unittest.mock import MagicMock, patch

import pytest

from autoswe.orch.types import Effect
from autoswe.providers.adapter import apply_effect, read_api
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
    return mock


def _run_read(tracker, provider: str, **kwargs) -> dict:
    """Run the single shared read_api. create_pr is the only effect that
    resolves a VCS, and read_api never does, so this needs no patching."""
    return read_api(tracker, _repo_cfg(provider), {}, **kwargs)


# ---------------------------------------------------------------------------
# read_api -- comment body normalisation (the one provider-specific hook)
# ---------------------------------------------------------------------------

def test_azure_div_wrapped_comment_unwrapped():
    """Bug 1 regression: ADO rich-text wraps user comments in <div>.

    After read_api, the comment body should have the <div> stripped so
    slash-command parsing sees clean text.
    """
    comments = [_make_comment(_AZURE_DIV_WRAPPED)]
    api_states = _run_read(_make_tracker("azure", comments), "azure")
    body = api_states[42].comments[0].body
    assert "/plan --branch dev" in body
    assert "<div>" not in body


def test_azure_html_entities_decoded():
    """ADO rich-text may encode characters as HTML entities."""
    comments = [_make_comment(_AZURE_ENTITIES)]
    api_states = _run_read(_make_tracker("azure", comments), "azure")
    body = api_states[42].comments[0].body
    assert "/fix with --focus" in body
    assert "&#45;" not in body
    assert "&#47;" not in body


def test_azure_bot_marker_preserved():
    """Bot comments should keep the autoswe-bot marker after HTML strip."""
    bot_body = "<div>## Plan\n\nSome plan text\n</div>\n" + BOT_MARKER
    comments = [_make_comment(bot_body, author_login="BOT")]
    api_states = _run_read(_make_tracker("azure", comments), "azure")
    body = api_states[42].comments[0].body
    assert BOT_MARKER in body
    assert "<div>" not in body


@pytest.mark.parametrize("provider", PROVIDERS)
def test_clean_comment_passthrough(provider):
    """A comment that is already clean text should come out unchanged."""
    clean = "/plan --branch main"
    comments = [_make_comment(clean)]
    api_states = _run_read(_make_tracker(provider, comments), provider)
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
    """When prev_updated matches, comments should be skipped."""
    t = _single_issue_tracker(provider, "2026-01-01T00:00:00Z")
    api_states = _run_read(t, provider, prev_updated={42: "2026-01-01T00:00:00Z"})
    assert api_states[42].comments_fetched is False
    assert api_states[42].comments == ()
    t.fetch_comments.assert_not_called()


@pytest.mark.parametrize("provider", PROVIDERS)
def test_read_api_fetch_when_timestamp_changed(provider):
    """When prev_updated differs from issue.last_updated, fetch comments."""
    t = _single_issue_tracker(provider, "2026-01-02T00:00:00Z")
    api_states = _run_read(t, provider, prev_updated={42: "2026-01-01T00:00:00Z"})
    assert api_states[42].comments_fetched is True
    t.fetch_comments.assert_called_once()


@pytest.mark.parametrize("provider", PROVIDERS)
def test_read_api_force_fetch_overrides_skip(provider):
    """force_fetch set overrides a matching timestamp."""
    t = _single_issue_tracker(provider, "2026-01-01T00:00:00Z")
    api_states = _run_read(t, provider,
                           prev_updated={42: "2026-01-01T00:00:00Z"},
                           force_fetch={42})
    assert api_states[42].comments_fetched is True
    t.fetch_comments.assert_called_once()


@pytest.mark.parametrize("provider", PROVIDERS)
def test_read_api_new_issue_always_fetched(provider):
    """An issue not in prev_updated should always be fetched."""
    t = _single_issue_tracker(provider, "2026-01-01T00:00:00Z")
    api_states = _run_read(t, provider, prev_updated={})
    assert api_states[42].comments_fetched is True
    t.fetch_comments.assert_called_once()


@pytest.mark.parametrize("provider", PROVIDERS)
def test_read_api_no_last_updated_always_fetched(provider):
    """When issue has no last_updated, always fetch comments."""
    t = _single_issue_tracker(provider, None)
    api_states = _run_read(t, provider, prev_updated={42: "2026-01-01T00:00:00Z"})
    assert api_states[42].comments_fetched is True
    t.fetch_comments.assert_called_once()


@pytest.mark.parametrize("provider", PROVIDERS)
def test_read_api_backward_compat_no_prev_updated(provider):
    """Without prev_updated, all issues are fetched (backward compat)."""
    t = _single_issue_tracker(provider, "2026-01-01T00:00:00Z")
    api_states = _run_read(t, provider)
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
# apply_effect -- create_pr CI gate (no sync gate; already synced)
# ---------------------------------------------------------------------------

def _queue_with_entry(provider: str, slug: str) -> dict:
    return {slug: {"owner": "o", "repo": "r", "issue_number": 1}}


def _run_create_pr_ci(provider: str, ci_state, cfg):
    """Drive a create_pr through the CI gate; returns (vcs, tracker)."""
    tracker = MagicMock()
    vcs = MagicMock()
    vcs.find_existing_pr.return_value = None
    vcs.get_ci_status.return_value = CIStatus(state=ci_state)
    slug = "gh__owner_repo_1"
    queue = _queue_with_entry(provider, slug)
    with patch("autoswe.providers.adapter.get_vcs", return_value=vcs):
        _run_apply(provider, tracker, _create_pr_effect(), queue, 1, slug, cfg)
    return vcs, tracker


@pytest.mark.parametrize("provider", PROVIDERS)
def test_apply_effect_create_pr_deferred_when_ci_pending(provider):
    """CI pending -> PR creation deferred, deferral comment posted instead."""
    vcs, tracker = _run_create_pr_ci(provider, "pending", {"PR_REQUIRE_CI": True})
    vcs.open_pull_request.assert_not_called()
    tracker.post_comment.assert_called_once()
    assert "deferred" in tracker.post_comment.call_args[0][1].lower()


@pytest.mark.parametrize("provider", PROVIDERS)
def test_apply_effect_create_pr_deferred_when_ci_failing(provider):
    """CI failing -> PR creation deferred."""
    vcs, tracker = _run_create_pr_ci(provider, "failure", {"PR_REQUIRE_CI": True})
    vcs.open_pull_request.assert_not_called()
    tracker.post_comment.assert_called_once()


@pytest.mark.parametrize("provider", PROVIDERS)
def test_apply_effect_create_pr_proceeds_when_ci_success(provider):
    """CI success -> PR created as normal."""
    vcs, tracker = _run_create_pr_ci(provider, "success", {"PR_REQUIRE_CI": True})
    vcs.open_pull_request.assert_called_once()
    tracker.post_comment.assert_not_called()


@pytest.mark.parametrize("provider", PROVIDERS)
def test_apply_effect_create_pr_proceeds_when_no_ci_configured(provider):
    """CI state 'none' (no checks configured) -> treated as pass, PR created."""
    vcs, tracker = _run_create_pr_ci(provider, "none", {"PR_REQUIRE_CI": True})
    vcs.open_pull_request.assert_called_once()


@pytest.mark.parametrize("provider", PROVIDERS)
def test_apply_effect_create_pr_ci_gate_disabled_ignores_failure(provider):
    """PR_REQUIRE_CI=False -> CI failure does not block PR creation."""
    vcs, tracker = _run_create_pr_ci(provider, "failure", {"PR_REQUIRE_CI": False})
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
