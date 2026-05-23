"""Tests for autoswe/commands/setup.py."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from autoswe.commands.setup import (
    _ENV_SCHEMA,
    _gh_verify,
    _wizard_env,
    _write_env,
    cmd_setup,
)

# ---------------------------------------------------------------------------
# _write_env
# ---------------------------------------------------------------------------

def test_write_env_renders_non_defaults(tmp_path):
    path = tmp_path / "autoswe.env"
    _write_env(path, {"MAX_CONCURRENT": "4", "MAX_ATTEMPTS": "5"})
    text = path.read_text(encoding="utf-8")
    assert "MAX_CONCURRENT=4" in text
    assert "MAX_ATTEMPTS=5" in text


def test_write_env_includes_comments(tmp_path):
    path = tmp_path / "autoswe.env"
    _write_env(path, {"MAX_CONCURRENT": "2"})
    text = path.read_text(encoding="utf-8")
    # Comment from _ENV_SCHEMA
    assert "# Max simultaneous agent jobs" in text


def test_write_env_skips_entries_not_passed(tmp_path):
    path = tmp_path / "autoswe.env"
    _write_env(path, {"MAX_CONCURRENT": "2"})
    text = path.read_text(encoding="utf-8")
    assert "MAX_ATTEMPTS" not in text


def test_write_env_creates_parent_dirs(tmp_path):
    path = tmp_path / "nested" / "dir" / "autoswe.env"
    _write_env(path, {"MAX_CONCURRENT": "1"})
    assert path.exists()


# ---------------------------------------------------------------------------
# _wizard_env
# ---------------------------------------------------------------------------

def test_wizard_env_returns_only_changed_values():
    schema_defaults = {k: d for k, d, _ in _ENV_SCHEMA}

    inputs_iter = iter(
        ["n"]           # no custom Anthropic endpoint
        + ["4"]         # MAX_CONCURRENT (changed from default "1")
        + [""] * (len(_ENV_SCHEMA) - 4)  # keep defaults for everything else (skip ANTHROPIC keys)
    )

    with patch("autoswe.commands.setup._prompt", side_effect=lambda label, default="", **kw: next(inputs_iter)):
        with patch("autoswe.commands.setup._prompt_yes_no", return_value=False):
            result = _wizard_env()

    # Only non-default values are returned
    for k, v in result.items():
        assert v != schema_defaults.get(k), f"key {k!r} should not equal its default"


def test_wizard_env_skips_anthropic_keys_when_no_custom_endpoint():
    with patch("autoswe.commands.setup._prompt_yes_no", return_value=False):
        with patch("autoswe.commands.setup._prompt", return_value="") as mock_prompt:
            _wizard_env()

    prompted_labels = [call.args[0] for call in mock_prompt.call_args_list]
    assert not any("ANTHROPIC" in lbl for lbl in prompted_labels)


def test_wizard_env_includes_anthropic_keys_when_custom_endpoint():
    with patch("autoswe.commands.setup._prompt_yes_no", return_value=True):
        with patch("autoswe.commands.setup._prompt", return_value="") as mock_prompt:
            _wizard_env()

    prompted_labels = [call.args[0] for call in mock_prompt.call_args_list]
    assert any("ANTHROPIC_API_KEY" in lbl for lbl in prompted_labels)


# ---------------------------------------------------------------------------
# _gh_verify
# ---------------------------------------------------------------------------

def test_gh_verify_returns_login_on_success():
    mock_resp = MagicMock()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_resp.headers.get.return_value = "repo,workflow"
    mock_resp.read.return_value = json.dumps({"login": "octocat"}).encode()

    with patch("autoswe.commands.setup.request.urlopen", return_value=mock_resp):
        login = _gh_verify("ghp_fake_token")

    assert login == "octocat"


def test_gh_verify_returns_none_on_http_error():
    from urllib.error import HTTPError
    with patch("autoswe.commands.setup.request.urlopen", side_effect=HTTPError(None, 401, "Unauthorized", {}, None)):
        login = _gh_verify("bad_token")

    assert login is None


# ---------------------------------------------------------------------------
# cmd_setup — repos.json merge + smoke test path
# ---------------------------------------------------------------------------

def _make_args(force=False):
    args = MagicMock()
    args.force = force
    return args


def test_cmd_setup_writes_repos_json(tmp_path, monkeypatch):
    """Happy path: one GitHub repo added, repos.json written."""
    monkeypatch.setattr("autoswe.commands.setup.REPOS_CONFIG_FILE", tmp_path / "repos.json")
    monkeypatch.setattr("autoswe.commands.setup._ENV_FILE", tmp_path / "autoswe.env")

    new_entry = {
        "owner/repo": {
            "provider": "github",
            "base_branch": "main",
            "pat": "ghp_test",
            "auto_dispatch_new": False,
        }
    }

    with patch("autoswe.commands.setup._prompt_choice", return_value="github"):
        with patch("autoswe.commands.setup._wizard_github", return_value=new_entry):
            with patch("autoswe.commands.setup._wizard_env", return_value={}):
                with patch("autoswe.commands.setup._write_env"):
                    with patch("autoswe.commands.setup._prompt_yes_no", return_value=False):
                        cmd_setup(_make_args(), cfg={})

    written = json.loads((tmp_path / "repos.json").read_text(encoding="utf-8"))
    assert "owner/repo" in written
    assert written["owner/repo"]["pat"] == "ghp_test"


def test_cmd_setup_merges_existing_repos(tmp_path, monkeypatch):
    """New repos are merged with, not replacing, existing repos.json."""
    existing = {"existing/repo": {"provider": "github", "pat": "old_pat", "base_branch": "main"}}
    repos_file = tmp_path / "repos.json"
    repos_file.write_text(json.dumps(existing), encoding="utf-8")

    monkeypatch.setattr("autoswe.commands.setup.REPOS_CONFIG_FILE", repos_file)
    monkeypatch.setattr("autoswe.commands.setup._ENV_FILE", tmp_path / "autoswe.env")

    new_entry = {
        "new/repo": {
            "provider": "github",
            "base_branch": "main",
            "pat": "ghp_new",
            "auto_dispatch_new": False,
        }
    }

    with patch("autoswe.commands.setup._prompt_choice", return_value="github"):
        with patch("autoswe.commands.setup._wizard_github", return_value=new_entry):
            with patch("autoswe.commands.setup._wizard_env", return_value={}):
                with patch("autoswe.commands.setup._write_env"):
                    with patch("autoswe.commands.setup._prompt_yes_no", return_value=True):
                        cmd_setup(_make_args(), cfg={})

    written = json.loads(repos_file.read_text(encoding="utf-8"))
    assert "existing/repo" in written
    assert "new/repo" in written


def test_cmd_setup_force_overwrites_without_prompting(tmp_path, monkeypatch):
    """--force flag skips 'add more repos?' prompt."""
    existing = {"old/repo": {"provider": "github", "pat": "tok", "base_branch": "main"}}
    repos_file = tmp_path / "repos.json"
    repos_file.write_text(json.dumps(existing), encoding="utf-8")

    monkeypatch.setattr("autoswe.commands.setup.REPOS_CONFIG_FILE", repos_file)
    monkeypatch.setattr("autoswe.commands.setup._ENV_FILE", tmp_path / "autoswe.env")

    new_entry = {"new/repo": {"provider": "github", "pat": "tok2", "base_branch": "main", "auto_dispatch_new": False}}

    prompt_yes_no_calls = []

    def fake_yes_no(label, default=False):
        prompt_yes_no_calls.append(label)
        return False  # decline smoke test

    with patch("autoswe.commands.setup._prompt_choice", return_value="github"):
        with patch("autoswe.commands.setup._wizard_github", return_value=new_entry):
            with patch("autoswe.commands.setup._wizard_env", return_value={}):
                with patch("autoswe.commands.setup._write_env"):
                    with patch("autoswe.commands.setup._prompt_yes_no", side_effect=fake_yes_no):
                        cmd_setup(_make_args(force=True), cfg={})

    # Should not have been asked about merging
    assert not any("Add more repos" in lbl for lbl in prompt_yes_no_calls)


def test_cmd_setup_no_repos_returns_early(tmp_path, monkeypatch, capsys):
    """Wizard exits gracefully when no repos are configured."""
    monkeypatch.setattr("autoswe.commands.setup.REPOS_CONFIG_FILE", tmp_path / "repos.json")
    monkeypatch.setattr("autoswe.commands.setup._ENV_FILE", tmp_path / "autoswe.env")

    with patch("autoswe.commands.setup._prompt_choice", return_value="github"):
        with patch("autoswe.commands.setup._wizard_github", return_value={}):
            cmd_setup(_make_args(), cfg={})

    captured = capsys.readouterr()
    assert "No repos configured" in captured.out
    assert not (tmp_path / "repos.json").exists()


# ---------------------------------------------------------------------------
# Provider / repo selection parsing (unit-level)
# ---------------------------------------------------------------------------

def test_wizard_github_adds_entry(monkeypatch):
    """_wizard_github returns a properly shaped entry."""
    inputs = iter([
        "ghp_fake",     # PAT
        "1",            # select repo #1 from list
        "",             # accept default base branch
        "n",            # no auto_dispatch
    ])

    with patch("autoswe.commands.setup._prompt", side_effect=lambda lbl, default="", **kw: next(inputs)):
        with patch("autoswe.commands.setup._prompt_yes_no", return_value=False):
            with patch("autoswe.commands.setup._gh_verify", return_value="octocat"):
                with patch("autoswe.commands.setup._gh_list_repos", return_value=["octocat/myrepo"]):
                    with patch("autoswe.commands.setup._gh_default_branch", return_value="main"):
                        from autoswe.commands.setup import _wizard_github
                        result = _wizard_github()

    assert "octocat/myrepo" in result
    assert result["octocat/myrepo"]["pat"] == "ghp_fake"
    assert result["octocat/myrepo"]["provider"] == "github"
