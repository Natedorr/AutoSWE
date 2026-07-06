"""Tests for autoswe.harness.initializer — ensure_claude_md."""

import os
from unittest.mock import patch

import pytest


@pytest.fixture
def _sample_task():
    """Minimal task dict for initializer tests."""
    return {
        "id": "gh:owner_repo_1",
        "owner": "owner",
        "repo": "repo",
        "issue_number": 1,
        "base_branch": "main",
        "_token": "ghp_test",
    }


def _make_cfg():
    """Minimal cfg dict sufficient for resolve_harness."""
    return {
        "PLAN_MODEL": "test-model",
        "PLAN_HARNESS": "",
        "FIX_HARNESS": "",
        "REVIEW_HARNESS": "",
        "AGENT_TIMEOUT": 7200,
        "AGENT_RETRY_ON_FAILURE": 0,
        "ANTHROPIC_AUTH_TOKEN": "",
        "ANTHROPIC_API_KEY": "",
        "ANTHROPIC_BASE_URL": "",
        "CLAUDE_CLI_PATH": "",
    }


@pytest.fixture
def _allow_init_session():
    """Temporarily clear AUTOSWE_SKIP_INIT_SESSION so ensure_claude_md can run."""
    orig = os.environ.pop("AUTOSWE_SKIP_INIT_SESSION", None)
    yield
    if orig is not None:
        os.environ["AUTOSWE_SKIP_INIT_SESSION"] = orig


def test_claude_md_already_exists_noop(tmp_path, _sample_task):
    """When CLAUDE.md already exists, ensure_claude_md returns without calling runner."""
    from autoswe.harness.initializer import ensure_claude_md

    wt = tmp_path / "wt"
    wt.mkdir()
    (wt / "CLAUDE.md").write_text("already here")

    cfg = _make_cfg()
    repo_cfg = {"provider": "github"}
    progress_calls: list[str] = []

    ensure_claude_md(
        _sample_task, wt, repo_cfg, cfg, phase="plan",
        progress_callback=lambda msg: progress_calls.append(msg),
    )

    # No progress messages means runner was never invoked
    assert progress_calls == []


def test_claude_md_absent_runs_session_and_commits(tmp_path, _sample_task, _allow_init_session):
    """When CLAUDE.md is absent, ensure_claude_md runs a session then commits."""
    from autoswe.harness.backends.base import RunResult
    from autoswe.harness.initializer import ensure_claude_md

    wt = tmp_path / "wt"
    wt.mkdir()
    # No CLAUDE.md

    cfg = _make_cfg()
    repo_cfg = {"provider": "github"}
    progress_calls: list[str] = []

    # Mock runner.run to write CLAUDE.md and return a result
    fake_result = RunResult(
        text="Wrote CLAUDE.md",
        session_id="init-session",
        subtype="success",
        cost_usd=0.01,
        duration_seconds=2.5,
    )

    commit_calls = []

    def _fake_run_and_write(*args, **kwargs):
        (wt / "CLAUDE.md").write_text("generated content")
        return fake_result

    with patch("autoswe.harness.initializer.runner") as mock_runner, \
         patch("autoswe.harness.initializer.resolve_harness") as mock_resolve, \
         patch("autoswe.harness.initializer.commit_and_push", side_effect=lambda *a, **k: commit_calls.append((a, k))):
        mock_runner.run.side_effect = _fake_run_and_write
        mock_resolve.return_value = {"backend": "claude_code", "model": "test-model"}

        ensure_claude_md(
            _sample_task, wt, repo_cfg, cfg, phase="plan",
            progress_callback=lambda msg: progress_calls.append(msg),
        )

    # Verify runner.run was called
    assert mock_runner.run.called
    call_kwargs = mock_runner.run.call_args[1]
    assert call_kwargs["mode"] == "read_write"

    # Verify commit_and_push was called
    assert len(commit_calls) == 1
    args, _ = commit_calls[0]
    assert args[4] == "Add CLAUDE.md (autoswe init)"


def test_claude_md_session_raises_is_non_fatal(tmp_path, _sample_task, _allow_init_session):
    """When the init session raises, ensure_claude_md does not crash."""
    from autoswe.harness.initializer import ensure_claude_md

    wt = tmp_path / "wt"
    wt.mkdir()

    cfg = _make_cfg()
    repo_cfg = {"provider": "github"}

    with patch("autoswe.harness.initializer.runner") as mock_runner:
        mock_runner.run.side_effect = RuntimeError("backend unavailable")

        # Should not raise
        ensure_claude_md(
            _sample_task, wt, repo_cfg, cfg, phase="plan",
            progress_callback=lambda msg: None,
        )


def test_claude_md_session_returns_but_file_absent(tmp_path, _sample_task, _allow_init_session):
    """When the session returns but didn't write CLAUDE.md, no commit is attempted."""
    from autoswe.harness.backends.base import RunResult
    from autoswe.harness.initializer import ensure_claude_md

    wt = tmp_path / "wt"
    wt.mkdir()

    cfg = _make_cfg()
    repo_cfg = {"provider": "github"}

    fake_result = RunResult(
        text="Didn't write anything",
        session_id="init-session",
        subtype="success",
    )

    with patch("autoswe.harness.initializer.runner") as mock_runner, \
         patch("autoswe.harness.initializer.resolve_harness") as mock_resolve, \
         patch("autoswe.harness.initializer.commit_and_push") as mock_commit:
        mock_runner.run.return_value = fake_result
        mock_resolve.return_value = {"backend": "claude_code"}

        ensure_claude_md(
            _sample_task, wt, repo_cfg, cfg, phase="plan",
            progress_callback=lambda msg: None,
        )

    # commit_and_push should NOT be called (file doesn't exist)
    assert not mock_commit.called
