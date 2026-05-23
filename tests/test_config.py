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
