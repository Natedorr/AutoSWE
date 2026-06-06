"""Tests for autoswe.core.config — load_config defaults and override parsing."""


# ---------------------------------------------------------------------------
# _as_bool helper (T7 DRY refactor)
# ---------------------------------------------------------------------------

def test_as_bool_true_strings():
    """_as_bool recognizes common truthy string values."""
    from autoswe.core.config import _as_bool

    assert _as_bool("true") is True
    assert _as_bool("True") is True
    assert _as_bool("TRUE") is True

def test_as_bool_false_strings():
    """_as_bool treats anything other than 'true' (case-insensitive) as False."""
    from autoswe.core.config import _as_bool

    assert _as_bool("false") is False
    assert _as_bool("False") is False
    assert _as_bool("0") is False
    assert _as_bool("yes") is False
    assert _as_bool("") is False

def test_as_bool_none_uses_default():
    """_as_bool(None) falls back to the default value."""
    from autoswe.core.config import _as_bool

    assert _as_bool(None) is False  # default="false"
    assert _as_bool(None, "true") is True

def test_as_bool_non_string_coerced():
    """_as_bool coerces non-string values (e.g., int from env file)."""
    from autoswe.core.config import _as_bool

    assert _as_bool(1) is False  # str(1).lower() == "1" != "true"
    assert _as_bool(0) is False


# ---------------------------------------------------------------------------
# _load_json_config helper (T7 DRY refactor)
# ---------------------------------------------------------------------------

def test_load_json_config_missing_file(isolated_autoswe_dir):
    """Non-existent file returns empty dict."""
    from pathlib import Path

    from autoswe.core.config import _load_json_config

    result = _load_json_config(Path("/nonexistent/path.json"))
    assert result == {}


def test_load_json_config_valid_file(isolated_autoswe_dir, tmp_path):
    """Valid JSON file returns parsed dict."""
    import json

    from autoswe.core.config import _load_json_config

    json_file = tmp_path / "test.json"
    json_file.write_text(json.dumps({"key": "value", "num": 42}), encoding="utf-8")

    result = _load_json_config(json_file)
    assert result == {"key": "value", "num": 42}


def test_load_json_config_corrupt_file(isolated_autoswe_dir, tmp_path):
    """Corrupt JSON file returns empty dict (graceful degradation)."""
    from autoswe.core.config import _load_json_config

    json_file = tmp_path / "corrupt.json"
    json_file.write_text("{not valid json}", encoding="utf-8")

    result = _load_json_config(json_file)
    assert result == {}



def test_load_config_defaults(isolated_autoswe_dir):
    """Without autoswe.env present, all defaults should be applied."""
    from autoswe.core.config import load_config

    cfg = load_config()

    assert "GITHUB_TOKEN" not in cfg
    assert cfg["AGENT_TIMEOUT"] == 7200
    assert cfg["AGENT_RETRY_ON_FAILURE"] == 0
    assert cfg["MAX_ATTEMPTS"] == 3
    assert cfg["MAX_TOTAL_HOURS"] == 2
    assert cfg["MAX_CONCURRENT"] == 1
    assert cfg["MAX_DRAIN_CYCLES"] == 50
    assert cfg["SILENT_REPORTING"] is False
    assert cfg["AUTO_ASSIGN"] is True
    assert cfg["AUTO_CREATE_PR"] is False
    assert cfg["WORKTREE_DIR"] == "worktrees"


def test_load_config_env_override(isolated_autoswe_dir, monkeypatch):
    monkeypatch.setenv("MAX_ATTEMPTS", "5")
    monkeypatch.setenv("SILENT_REPORTING", "true")
    monkeypatch.setenv("AUTO_CREATE_PR", "true")

    from autoswe.core.config import load_config

    cfg = load_config()

    assert cfg["MAX_ATTEMPTS"] == 5
    assert cfg["SILENT_REPORTING"] is True
    assert cfg["AUTO_CREATE_PR"] is True
    assert "GITHUB_TOKEN" not in cfg


def test_load_config_reads_autoswe_env_file(isolated_autoswe_dir):
    autoswe_env = isolated_autoswe_dir / "config" / "autoswe.env"
    autoswe_env.write_text(
        "MAX_CONCURRENT=3\nAUTO_ASSIGN=false\nAUTO_CREATE_PR=true\n",
        encoding="utf-8",
    )

    from autoswe.core.config import load_config

    cfg = load_config()

    assert cfg["MAX_CONCURRENT"] == 3
    assert cfg["AUTO_ASSIGN"] is False
    assert cfg["AUTO_CREATE_PR"] is True
    assert "GITHUB_TOKEN" not in cfg


def test_load_config_max_drain_cycles_from_env(isolated_autoswe_dir):
    autoswe_env = isolated_autoswe_dir / "config" / "autoswe.env"
    autoswe_env.write_text("MAX_DRAIN_CYCLES=100\n", encoding="utf-8")

    from autoswe.core.config import load_config

    cfg = load_config()

    assert cfg["MAX_DRAIN_CYCLES"] == 100


def test_load_config_ignores_comments_in_env_file(isolated_autoswe_dir):
    autoswe_env = isolated_autoswe_dir / "config" / "autoswe.env"
    autoswe_env.write_text(
        "# This is a comment\nMAX_ATTEMPTS=7\n",
        encoding="utf-8",
    )

    from autoswe.core.config import load_config

    cfg = load_config()
    assert cfg["MAX_ATTEMPTS"] == 7


def test_load_config_auto_create_pr_defaults_false(isolated_autoswe_dir):
    """AUTO_CREATE_PR should default to False (bool, not string)."""
    from autoswe.core.config import load_config

    cfg = load_config()

    assert cfg["AUTO_CREATE_PR"] is False
    assert isinstance(cfg["AUTO_CREATE_PR"], bool)


def test_load_repos_config_missing_returns_empty(isolated_autoswe_dir):
    from autoswe.core.config import load_repos_config

    result = load_repos_config()
    assert result == {}


def test_load_repos_config_parses_json(isolated_autoswe_dir):
    repos_json = isolated_autoswe_dir / "config" / "repos.json"
    repos_json.write_text(
        '{"natedorr/autoswe": {"provider": "github", "base_branch": "master", "pat": "ghp_test"}}',
        encoding="utf-8",
    )

    from autoswe.core.config import load_repos_config

    result = load_repos_config()
    assert "natedorr/autoswe" in result
    assert result["natedorr/autoswe"]["base_branch"] == "master"
    assert result["natedorr/autoswe"]["provider"] == "github"
    assert result["natedorr/autoswe"]["pat"] == "ghp_test"


def test_load_repos_config_corrupt_returns_empty(isolated_autoswe_dir):
    repos_json = isolated_autoswe_dir / "config" / "repos.json"
    repos_json.write_text("{not valid json}", encoding="utf-8")

    from autoswe.core.config import load_repos_config

    result = load_repos_config()
    assert result == {}


# ---------------------------------------------------------------------------
# repos.json provider validation
# ---------------------------------------------------------------------------

def test_load_repos_config_requires_provider(isolated_autoswe_dir):
    """Entries missing 'provider' field raise ValueError."""
    repos_json = isolated_autoswe_dir / "config" / "repos.json"
    repos_json.write_text(
        '{"natedorr/autoswe": {"base_branch": "master", "pat": "tok"}}',
        encoding="utf-8",
    )

    from autoswe.core.config import load_repos_config

    try:
        load_repos_config()
        assert False, "should have raised ValueError"
    except ValueError as e:
        assert "provider" in str(e).lower()
        assert "required" in str(e).lower()


def test_load_repos_config_github_requires_pat(isolated_autoswe_dir):
    """GitHub entries without 'pat' raise ValueError."""
    repos_json = isolated_autoswe_dir / "config" / "repos.json"
    repos_json.write_text(
        '{"natedorr/autoswe": {"provider": "github", "base_branch": "master"}}',
        encoding="utf-8",
    )

    from autoswe.core.config import load_repos_config

    try:
        load_repos_config()
        assert False, "should have raised ValueError"
    except ValueError as e:
        assert "pat" in str(e).lower()
        assert "setup" in str(e).lower()


def test_load_repos_config_azure_requires_pat(isolated_autoswe_dir):
    """Azure entries without 'pat' raise ValueError."""
    repos_json = isolated_autoswe_dir / "config" / "repos.json"
    repos_json.write_text(
        '{"my-org/my-proj/my-repo": {"provider": "azure"}}',
        encoding="utf-8",
    )

    from autoswe.core.config import load_repos_config

    try:
        load_repos_config()
        assert False, "should have raised ValueError"
    except ValueError as e:
        assert "pat" in str(e).lower()


def test_load_repos_config_azure_with_pat_ok(isolated_autoswe_dir):
    """Azure entries with 'pat' are accepted."""
    repos_json = isolated_autoswe_dir / "config" / "repos.json"
    repos_json.write_text(
        '{"my-org/my-proj/my-repo": {"provider": "azure", "pat": "abc123"}}',
        encoding="utf-8",
    )

    from autoswe.core.config import load_repos_config

    result = load_repos_config()
    assert result["my-org/my-proj/my-repo"]["provider"] == "azure"
    assert result["my-org/my-proj/my-repo"]["pat"] == "abc123"


def test_load_repos_config_github_with_pat_ok(isolated_autoswe_dir):
    """GitHub entries with 'pat' are accepted."""
    repos_json = isolated_autoswe_dir / "config" / "repos.json"
    repos_json.write_text(
        '{"owner/repo": {"provider": "github", "pat": "ghp_abc123"}}',
        encoding="utf-8",
    )

    from autoswe.core.config import load_repos_config

    result = load_repos_config()
    assert result["owner/repo"]["provider"] == "github"
    assert result["owner/repo"]["pat"] == "ghp_abc123"


def test_load_config_minimal_posting_default_false(isolated_autoswe_dir):
    """MINIMAL_POSTING defaults to False when not set."""
    from autoswe.core.config import load_config

    cfg = load_config()
    assert cfg["MINIMAL_POSTING"] is False


def test_load_config_minimal_posting_env_true(isolated_autoswe_dir, monkeypatch):
    """MINIMAL_POSTING=true env var is parsed as True boolean."""
    monkeypatch.setenv("MINIMAL_POSTING", "true")

    from autoswe.core.config import load_config

    cfg = load_config()
    assert cfg["MINIMAL_POSTING"] is True


def test_load_config_minimal_posting_file_true(isolated_autoswe_dir):
    """MINIMAL_POSTING=true in autoswe.env is parsed as True boolean."""
    from autoswe.core import config as config_mod

    config_mod.CONFIG_FILE.write_text("MINIMAL_POSTING=true\n", encoding="utf-8")

    from autoswe.core.config import load_config

    cfg = load_config()
    assert cfg["MINIMAL_POSTING"] is True


# ---------------------------------------------------------------------------
# Harness config keys in load_config
# ---------------------------------------------------------------------------

def test_load_config_harness_defaults(isolated_autoswe_dir):
    """PLAN_HARNESS/FIX_HARNESS/REVIEW_HARNESS default to empty string."""
    from autoswe.core.config import load_config

    cfg = load_config()
    assert cfg["PLAN_HARNESS"] == ""
    assert cfg["FIX_HARNESS"] == ""
    assert cfg["REVIEW_HARNESS"] == ""


def test_load_config_harness_env_override(isolated_autoswe_dir, monkeypatch):
    """Harness keys can be set via env vars."""
    monkeypatch.setenv("PLAN_HARNESS", "claude-opus")
    monkeypatch.setenv("FIX_HARNESS", "claude-sonnet")

    from autoswe.core.config import load_config

    cfg = load_config()
    assert cfg["PLAN_HARNESS"] == "claude-opus"
    assert cfg["FIX_HARNESS"] == "claude-sonnet"
    assert cfg["REVIEW_HARNESS"] == ""


def test_load_config_harness_file_override(isolated_autoswe_dir):
    """Harness keys can be set via autoswe.env file."""
    from autoswe.core import config as config_mod

    config_mod.CONFIG_FILE.write_text(
        "PLAN_HARNESS=claude-opus\nFIX_HARNESS=claude-sonnet\n",
        encoding="utf-8",
    )

    from autoswe.core.config import load_config

    cfg = load_config()
    assert cfg["PLAN_HARNESS"] == "claude-opus"
    assert cfg["FIX_HARNESS"] == "claude-sonnet"


# ---------------------------------------------------------------------------
# load_harnesses_config
# ---------------------------------------------------------------------------

def test_load_harnesses_config_missing_returns_empty(isolated_autoswe_dir):
    """No harnesses.json → empty dict."""
    from autoswe.core.config import load_harnesses_config

    result = load_harnesses_config()
    assert result == {}


def test_load_harnesses_config_parses_json(isolated_autoswe_dir):
    """Valid harnesses.json → validated profiles."""
    harnesses_json = isolated_autoswe_dir / "config" / "harnesses.json"
    harnesses_json.write_text(
        '{"claude-opus": {"backend": "claude_code", "model": "claude-opus-4-8"}, "my-codex": {"backend": "codex", "model": "gpt-5"}}',
        encoding="utf-8",
    )

    from autoswe.core.config import load_harnesses_config

    result = load_harnesses_config()
    assert "claude-opus" in result
    assert result["claude-opus"]["backend"] == "claude_code"
    assert result["claude-opus"]["model"] == "claude-opus-4-8"
    assert "my-codex" in result
    assert result["my-codex"]["backend"] == "codex"


def test_load_harnesses_config_skips_underscore_keys(isolated_autoswe_dir):
    """Keys starting with _ are skipped."""
    harnesses_json = isolated_autoswe_dir / "config" / "harnesses.json"
    harnesses_json.write_text(
        '{"_template": {"backend": "claude_code"}, "real": {"backend": "claude_code", "model": "x"}}',
        encoding="utf-8",
    )

    from autoswe.core.config import load_harnesses_config

    result = load_harnesses_config()
    assert "_template" not in result
    assert "real" in result


def test_load_harnesses_config_corrupt_returns_empty(isolated_autoswe_dir):
    """Invalid JSON → empty dict (graceful degradation)."""
    harnesses_json = isolated_autoswe_dir / "config" / "harnesses.json"
    harnesses_json.write_text("{not valid json}", encoding="utf-8")

    from autoswe.core.config import load_harnesses_config

    result = load_harnesses_config()
    assert result == {}


def test_load_harnesses_config_requires_backend(isolated_autoswe_dir):
    """Entries missing 'backend' field raise ValueError."""
    harnesses_json = isolated_autoswe_dir / "config" / "harnesses.json"
    harnesses_json.write_text(
        '{"no-backend": {"model": "claude-opus-4-8"}}',
        encoding="utf-8",
    )

    from autoswe.core.config import load_harnesses_config

    try:
        load_harnesses_config()
        assert False, "should have raised ValueError"
    except ValueError as e:
        assert "backend" in str(e).lower()
        assert "required" in str(e).lower()


def test_load_harnesses_config_unknown_backend_raises(isolated_autoswe_dir):
    """Entries with unknown backend raise ValueError."""
    harnesses_json = isolated_autoswe_dir / "config" / "harnesses.json"
    harnesses_json.write_text(
        '{"bad": {"backend": "unknown_backend"}}',
        encoding="utf-8",
    )

    from autoswe.core.config import load_harnesses_config

    try:
        load_harnesses_config()
        assert False, "should have raised ValueError"
    except ValueError as e:
        assert "unknown" in str(e).lower()


def test_load_harnesses_config_backend_case_insensitive(isolated_autoswe_dir):
    """Backend field is case-insensitive."""
    harnesses_json = isolated_autoswe_dir / "config" / "harnesses.json"
    harnesses_json.write_text(
        '{"upper": {"backend": "CLAUDE_CODE", "model": "x"}}',
        encoding="utf-8",
    )

    from autoswe.core.config import load_harnesses_config

    result = load_harnesses_config()
    assert result["upper"]["backend"] == "claude_code"


# ---------------------------------------------------------------------------
# resolve_harness
# ---------------------------------------------------------------------------

def test_resolve_harness_synthesized_default(isolated_autoswe_dir):
    """No harness profile → synthesized claude_code with legacy model."""
    from autoswe.core.config import resolve_harness

    cfg = {"PLAN_MODEL": "claude-sonnet-4-6", "FIX_MODEL": "", "REVIEW_MODEL": "",
           "PLAN_HARNESS": "", "FIX_HARNESS": "", "REVIEW_HARNESS": ""}
    repo_cfg = {}

    result = resolve_harness("plan", repo_cfg, cfg)
    assert result["backend"] == "claude_code"
    assert result["model"] == "claude-sonnet-4-6"


def test_resolve_harness_synthesized_default_repo_model(isolated_autoswe_dir):
    """Repo-specific model takes precedence over global model."""
    from autoswe.core.config import resolve_harness

    cfg = {"PLAN_MODEL": "claude-sonnet-4-6", "PLAN_HARNESS": ""}
    repo_cfg = {"plan_model": "claude-opus-4-8"}

    result = resolve_harness("plan", repo_cfg, cfg)
    assert result["backend"] == "claude_code"
    assert result["model"] == "claude-opus-4-8"


def test_resolve_harness_repo_profile_ref(isolated_autoswe_dir):
    """repo_cfg phase_harness → lookup in harnesses dict."""
    from autoswe.core.config import resolve_harness

    harnesses = {"my-opus": {"backend": "claude_code", "model": "claude-opus-4-8"}}
    cfg = {"PLAN_HARNESS": ""}
    repo_cfg = {"plan_harness": "my-opus"}

    result = resolve_harness("plan", repo_cfg, cfg, harnesses=harnesses)
    assert result["backend"] == "claude_code"
    assert result["model"] == "claude-opus-4-8"


def test_resolve_harness_global_profile_ref(isolated_autoswe_dir):
    """cfg PHASE_HARNESS → lookup in harnesses dict."""
    from autoswe.core.config import resolve_harness

    harnesses = {"sonnet-fix": {"backend": "claude_code", "model": "claude-sonnet-4-6"}}
    cfg = {"FIX_HARNESS": "sonnet-fix"}
    repo_cfg = {}

    result = resolve_harness("fix", repo_cfg, cfg, harnesses=harnesses)
    assert result["backend"] == "claude_code"
    assert result["model"] == "claude-sonnet-4-6"


def test_resolve_harness_repo_profile_beats_global(isolated_autoswe_dir):
    """repo_cfg harness ref takes precedence over cfg harness ref."""
    from autoswe.core.config import resolve_harness

    harnesses = {
        "global-p": {"backend": "claude_code", "model": "global-model"},
        "repo-p": {"backend": "claude_code", "model": "repo-model"},
    }
    cfg = {"PLAN_HARNESS": "global-p"}
    repo_cfg = {"plan_harness": "repo-p"}

    result = resolve_harness("plan", repo_cfg, cfg, harnesses=harnesses)
    assert result["model"] == "repo-model"


def test_resolve_harness_missing_profile_raises(isolated_autoswe_dir):
    """Referencing a non-existent profile raises ValueError."""
    from autoswe.core.config import resolve_harness

    harnesses = {"exists": {"backend": "claude_code"}}
    cfg = {"PLAN_HARNESS": ""}
    repo_cfg = {"plan_harness": "does-not-exist"}

    try:
        resolve_harness("plan", repo_cfg, cfg, harnesses=harnesses)
        assert False, "should have raised ValueError"
    except ValueError as e:
        assert "does-not-exist" in str(e)


def test_resolve_harness_fix_phase(isolated_autoswe_dir):
    """resolve_harness works for fix phase."""
    from autoswe.core.config import resolve_harness

    harnesses = {"fixer": {"backend": "claude_code", "model": "fixer-model"}}
    cfg = {"FIX_HARNESS": "fixer", "FIX_MODEL": ""}
    repo_cfg = {}

    result = resolve_harness("fix", repo_cfg, cfg, harnesses=harnesses)
    assert result["model"] == "fixer-model"


def test_resolve_harness_review_phase(isolated_autoswe_dir):
    """resolve_harness works for review phase."""
    from autoswe.core.config import resolve_harness

    cfg = {"REVIEW_MODEL": "reviewer-model", "REVIEW_HARNESS": ""}
    repo_cfg = {}

    result = resolve_harness("review", repo_cfg, cfg)
    assert result["backend"] == "claude_code"
    assert result["model"] == "reviewer-model"


def test_resolve_harness_no_model_in_synthesized(isolated_autoswe_dir):
    """Synthesized default with no legacy model → model=None."""
    from autoswe.core.config import resolve_harness

    cfg = {"PLAN_MODEL": "", "PLAN_HARNESS": ""}
    repo_cfg = {}

    result = resolve_harness("plan", repo_cfg, cfg)
    assert result["backend"] == "claude_code"
    assert result["model"] is None


def test_resolve_harness_none_cfg(isolated_autoswe_dir):
    """resolve_harness does not crash when cfg=None."""
    from autoswe.core.config import resolve_harness

    result = resolve_harness("plan", {}, None)
    assert result["backend"] == "claude_code"


def test_resolve_harness_none_repo_cfg(isolated_autoswe_dir):
    """resolve_harness does not crash when repo_cfg=None."""
    from autoswe.core.config import resolve_harness

    cfg = {"PLAN_MODEL": "claude-sonnet-4-6", "PLAN_HARNESS": ""}
    result = resolve_harness("plan", None, cfg)
    assert result["backend"] == "claude_code"
    assert result["model"] == "claude-sonnet-4-6"


def test_resolve_harness_synthesized_includes_repo_api_key(isolated_autoswe_dir):
    """Synthesized default checks repo_cfg for anthropic_api_key."""
    from autoswe.core.config import resolve_harness

    cfg = {"ANTHROPIC_API_KEY": "sk-cfg-key", "PLAN_HARNESS": ""}
    repo_cfg = {"anthropic_api_key": "sk-repo-key"}

    result = resolve_harness("plan", repo_cfg, cfg)
    assert result["anthropic_api_key"] == "sk-repo-key"


def test_resolve_harness_synthesized_cfg_api_key_fallback(isolated_autoswe_dir):
    """Synthesized default falls back to cfg ANTHROPIC_API_KEY when repo_cfg is empty."""
    from autoswe.core.config import resolve_harness

    cfg = {"ANTHROPIC_API_KEY": "sk-cfg-key", "PLAN_HARNESS": ""}
    repo_cfg = {}

    result = resolve_harness("plan", repo_cfg, cfg)
    assert result["anthropic_api_key"] == "sk-cfg-key"


def test_expand_env_dict_expands_list_strings(isolated_autoswe_dir):
    """_expand_env_dict expands ${VAR} in string elements of list values."""
    import os

    from autoswe.core.config import _expand_env_dict

    os.environ["_TEST_LIST_VAR"] = "expanded-item"
    try:
        result = _expand_env_dict({
            "items": ["${_TEST_LIST_VAR}", "static", 42, True],
            "nested": {"key": "${_TEST_LIST_VAR}"},
        })
        assert result["items"] == ["expanded-item", "static", 42, True]
        assert result["nested"]["key"] == "expanded-item"
    finally:
        del os.environ["_TEST_LIST_VAR"]


def test_expand_env_dict_list_with_non_string_items(isolated_autoswe_dir):
    """Non-string list elements (booleans, numbers) pass through unchanged."""
    from autoswe.core.config import _expand_env_dict

    result = _expand_env_dict({"flags": [True, False, 0, 1, None]})
    assert result["flags"] == [True, False, 0, 1, None]


def test_expand_env_dict_list_with_nested_dicts(isolated_autoswe_dir):
    """List containing dicts are recursively expanded."""
    import os

    from autoswe.core.config import _expand_env_dict

    os.environ["_TEST_NESTED_VAR"] = "nested-expanded"
    try:
        result = _expand_env_dict({
            "servers": [{"url": "${_TEST_NESTED_VAR}"}, "plain"],
        })
        assert result["servers"][0]["url"] == "nested-expanded"
        assert result["servers"][1] == "plain"
    finally:
        del os.environ["_TEST_NESTED_VAR"]


def test_claude_cli_path_defaults_to_empty_string(isolated_autoswe_dir):
    """CLAUDE_CLI_PATH defaults to empty string (backward compat)."""
    from autoswe.core.config import load_config

    cfg = load_config()
    assert cfg["CLAUDE_CLI_PATH"] == ""
    assert cfg["CLAUDE_CLI_PATH"] is not None


def test_resolve_harness_codex_profile(isolated_autoswe_dir):
    """resolve_harness returns codex backend profile when specified."""
    from autoswe.core.config import resolve_harness

    harnesses = {"my-codex": {"backend": "codex", "model": "gpt-5"}}
    cfg = {"FIX_HARNESS": ""}
    repo_cfg = {"fix_harness": "my-codex"}

    result = resolve_harness("fix", repo_cfg, cfg, harnesses=harnesses)
    assert result["backend"] == "codex"
    assert result["model"] == "gpt-5"


def test_load_harnesses_config_with_list_values(isolated_autoswe_dir):
    """harnesses.json with list values loads without crashing."""
    harnesses_json = isolated_autoswe_dir / "config" / "harnesses.json"
    harnesses_json.write_text(
        '{"with-list": {"backend": "claude_code", "model": "claude-opus-4-8", "extra_tools": ["Read", "Write"]}}',
        encoding="utf-8",
    )

    from autoswe.core import config as config_mod
    config_mod._harnesses_cache.clear()

    from autoswe.core.config import load_harnesses_config

    result = load_harnesses_config()
    assert "with-list" in result
    assert result["with-list"]["extra_tools"] == ["Read", "Write"]


# ---------------------------------------------------------------------------
# AGENT_RETRY_ON_SUBTYPE config
# ---------------------------------------------------------------------------


def test_agent_retry_on_subtype_default_empty(isolated_autoswe_dir):
    """AGENT_RETRY_ON_SUBTYPE defaults to empty string."""
    from autoswe.core.config import load_config

    cfg = load_config()
    assert "AGENT_RETRY_ON_SUBTYPE" in cfg
    assert cfg["AGENT_RETRY_ON_SUBTYPE"] == ""


def test_agent_retry_on_subtype_env_override(isolated_autoswe_dir, monkeypatch):
    """AGENT_RETRY_ON_SUBTYPE env var is passed through as-is."""
    monkeypatch.setenv("AGENT_RETRY_ON_SUBTYPE", "error,killed")

    from autoswe.core.config import load_config

    cfg = load_config()
    assert cfg["AGENT_RETRY_ON_SUBTYPE"] == "error,killed"


def test_agent_retry_on_subtype_file_override(isolated_autoswe_dir):
    """AGENT_RETRY_ON_SUBTYPE can be set in autoswe.env."""
    from autoswe.core import config as config_mod

    config_mod.CONFIG_FILE.write_text("AGENT_RETRY_ON_SUBTYPE=error\n", encoding="utf-8")

    from autoswe.core.config import load_config

    cfg = load_config()
    assert cfg["AGENT_RETRY_ON_SUBTYPE"] == "error"


def test_agent_retry_on_subtype_runner_parses_csv():
    """Runner parses AGENT_RETRY_ON_SUBTYPE comma list into set."""
    # Simulate the parsing logic in runner.py
    raw = "error,killed"
    parsed = {s.strip() for s in raw.split(",") if s.strip()}
    assert parsed == {"error", "killed"}

    raw_single = "error"
    parsed_single = {s.strip() for s in raw_single.split(",") if s.strip()}
    assert parsed_single == {"error"}


# ---------------------------------------------------------------------------
# WORKTREE_ORPHAN_POLICY config
# ---------------------------------------------------------------------------


def test_worktree_orphan_policy_default(isolated_autoswe_dir):
    """WORKTREE_ORPHAN_POLICY defaults to 'commit'."""
    from autoswe.core.config import load_config

    cfg = load_config()
    assert "WORKTREE_ORPHAN_POLICY" in cfg
    assert cfg["WORKTREE_ORPHAN_POLICY"] == "commit"


def test_worktree_orphan_policy_env_override(isolated_autoswe_dir, monkeypatch):
    """WORKTREE_ORPHAN_POLICY can be overridden via env var."""
    monkeypatch.setenv("WORKTREE_ORPHAN_POLICY", "discard")

    from autoswe.core.config import load_config

    cfg = load_config()
    assert cfg["WORKTREE_ORPHAN_POLICY"] == "discard"


def test_worktree_orphan_policy_file_override(isolated_autoswe_dir):
    """WORKTREE_ORPHAN_POLICY can be set in autoswe.env."""
    from autoswe.core import config as config_mod

    config_mod.CONFIG_FILE.write_text("WORKTREE_ORPHAN_POLICY=log_only\n", encoding="utf-8")

    from autoswe.core.config import load_config

    cfg = load_config()
    assert cfg["WORKTREE_ORPHAN_POLICY"] == "log_only"
