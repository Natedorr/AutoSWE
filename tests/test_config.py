"""Tests for autoswe.core.config — load_config defaults and override parsing."""



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
