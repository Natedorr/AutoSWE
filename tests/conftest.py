"""Shared test fixtures.

Exposes:
- fixture_path / load_fixture: read JSON from tests/fixtures/github/
- fake_token: stable token string for tests
- sample_task: minimal task dict matching queue.json shape
- gh_route_table: empty dict; tests fill it with (method, path) -> response
- mock_gh_request: patches autoswe.tracking.api._gh_request to dispatch via gh_route_table
- mock_gh_post_comment: patches gh_post_comment to capture posted comments
- mock_claude_run: patches autoswe.harness.runner.run with configurable return tuple
- isolated_autoswe_dir: per-test fresh AUTOSWE_DIR (overrides repo-root conftest baseline)
- github_fake: stateful in-memory GitHub API fake (scenario tests)
- azure_fake: stateful in-memory Azure DevOps API fake (scenario tests)
- scripted_claude: scripted multi-turn Claude SDK fake (scenario tests)
- git_fake: scripted worktree operations fake (scenario tests)
- scenario_cfg: pre-configured cfg dict + repos.json for scenario tests
"""
import json
import sys
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _silence_autoswe_log(monkeypatch):
    """Suppress autoswe log() calls during tests to prevent Windows console I/O stalls."""
    import autoswe.core.logging_utils as lu
    monkeypatch.setattr(lu, "log", lambda msg: None)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "github"


def fixture_path(name: str) -> Path:
    return FIXTURE_DIR / name


def load_fixture(name: str):
    return json.loads(fixture_path(name).read_text(encoding="utf-8"))


@pytest.fixture
def fake_token():
    return "ghp_faketoken_for_tests_only"


@pytest.fixture
def sample_task():
    return {
        "id": "gh:natedorr_autoswe_42",
        "owner": "natedorr",
        "repo": "autoswe",
        "issue_number": 42,
        "title": "Test issue",
        "body": "Issue body without slash command.",
        "base_branch": "master",
        "autoswe_status": None,
        "pr_number": None,
        "session_id": None,
        "last_synced": "2026-05-01T00:00:00+00:00",
        "created_at": "2026-05-01T00:00:00+00:00",
        "suppress_welcome": True,
        "attempt_count": 0,
        "_token": "ghp_faketoken_for_tests_only",
    }


@pytest.fixture
def gh_route_table():
    """Empty dict tests fill with (method, path_substring) -> response."""
    return {}


@pytest.fixture
def mock_gh_request(monkeypatch, gh_route_table):
    """Patch autoswe.tracking.api._gh_request.

    Routes match by (method, prefix) where prefix is matched against the
    request path with `startswith`. Tests register paths in gh_route_table
    keyed by tuple. If no route matches, raises RuntimeError so tests fail
    loudly on un-stubbed calls.
    """
    calls = []

    def fake_request(method, path, token, body=None, max_retries=3, timeout=30):
        calls.append({"method": method, "path": path, "body": body, "token": token})
        for (m, prefix), response in gh_route_table.items():
            if m == method and path.startswith(prefix):
                if callable(response):
                    return response(method, path, token, body)
                return response
        raise RuntimeError(f"unstubbed gh request: {method} {path}")

    import autoswe.tracking.api as gh_module
    monkeypatch.setattr(gh_module, "_gh_request", fake_request)
    fake_request.calls = calls
    return fake_request


@pytest.fixture
def mock_gh_post_comment(monkeypatch, gh_route_table):
    """Patch autoswe.tracking.api.gh_post_comment AND gh_post/_gh_request for comments.

    Cooperates with mock_gh_request: comment-specific routes are handled here,
    all others fall through to gh_route_table.
    """
    posted = []

    def fake_post(owner, repo, issue_number, body, token):
        posted.append({
            "owner": owner, "repo": repo,
            "issue_number": issue_number, "body": body,
        })

    def fake_gh_request(method, path, token, body=None, max_retries=3, timeout=30):
        # Intercept POST /repos/{o}/{r}/issues/{n}/comments
        if method == "POST" and "/issues/" in path and "/comments" in path:
            parts = path.split("/")
            owner = parts[3]
            repo = parts[4]
            issue_num = int(parts[5])
            comment_body = (body or {}).get("body", "") if isinstance(body, dict) else ""
            posted.append({
                "owner": owner, "repo": repo,
                "issue_number": issue_num, "body": comment_body,
            })
            return {"id": 10001, "body": comment_body,
                    "created_at": "2026-01-01T00:00:00Z"}
        # Intercept PATCH /repos/{o}/{r}/issues/comments/{id}
        if method == "PATCH" and "/issues/comments/" in path:
            cid = path.split("/issues/comments/")[1].split("/")[0]
            return {"id": int(cid), "body": (body or {}).get("body", "")}
        # Intercept PUT /repos/{o}/{r}/issues/comments/{id} (progress comment update)
        if method == "PUT" and "/issues/comments/" in path:
            cid = path.split("/issues/comments/")[1].split("/")[0]
            return {"id": int(cid), "body": (body or {}).get("body", "")}
        # Fall through to gh_route_table for other routes
        for (m, prefix), response in gh_route_table.items():
            if m == method and path.startswith(prefix):
                if callable(response):
                    return response(method, path, token, body)
                return response
        raise RuntimeError(f"unstubbed gh request: {method} {path}")

    import autoswe.tracking.api as gh_module
    monkeypatch.setattr(gh_module, "gh_post_comment", fake_post)
    monkeypatch.setattr(gh_module, "_gh_request", fake_gh_request)
    # Also patch the names imported into other autoswe modules.
    for mod_name in (
        "autoswe.orch.loop",
        "autoswe.harness.planner", "autoswe.vcs.ship",
    ):
        if mod_name in sys.modules:
            mod = sys.modules[mod_name]
            if hasattr(mod, "gh_post_comment"):
                monkeypatch.setattr(mod, "gh_post_comment", fake_post)

    fake_post.posted = posted
    return fake_post


@pytest.fixture
def mock_claude_run(monkeypatch):
    """Patch autoswe.harness.runner.run.

    Default: returns RunResult("", "session-1", "success"). Override on the
    returned callable via .set_return(text, session_id, subtype) or .set_raises(exc).
    """
    from autoswe.harness.runner import RunResult

    state = {"return_value": RunResult("", "session-1", "success"), "raises": None, "calls": []}

    def fake_run(prompt, *, cwd, cfg, repo_cfg=None, resume=None,
                 permission_mode="default", allowed_tools=None,
                 max_turns=200, model=None, mcp_servers=None,
                 progress_callback=None):
        state["calls"].append({
            "prompt": prompt, "cwd": cwd, "resume": resume,
            "permission_mode": permission_mode, "model": model,
        })
        if state["raises"] is not None:
            raise state["raises"]
        return state["return_value"]

    import autoswe.harness.runner as cr
    monkeypatch.setattr(cr, "run", fake_run)
    # Also patch import sites
    for mod_name in ("autoswe.harness.planner", "autoswe.harness.coder"):
        if mod_name in sys.modules:
            mod = sys.modules[mod_name]
            if hasattr(mod, "runner"):
                monkeypatch.setattr(mod.runner, "run", fake_run)

    def set_return(text, session_id="session-1", subtype="success"):
        state["return_value"] = RunResult(text, session_id, subtype)

    def set_raises(exc):
        state["raises"] = exc

    fake_run.set_return = set_return
    fake_run.set_raises = set_raises
    fake_run.calls = state["calls"]
    return fake_run


@pytest.fixture
def isolated_autoswe_dir(tmp_path, monkeypatch):
    """Per-test isolated AUTOSWE_DIR. Reloads autoswe.config path constants."""
    monkeypatch.setenv("AUTOSWE_DIR", str(tmp_path))
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "running").mkdir(parents=True, exist_ok=True)
    (tmp_path / "config").mkdir(parents=True, exist_ok=True)

    import autoswe.core.config as cfg
    import autoswe.core.queue_store as qs

    monkeypatch.setattr(cfg, "AUTOSWE_DIR", tmp_path)
    monkeypatch.setattr(cfg, "QUEUE_FILE", tmp_path / "data" / "queue.json")
    monkeypatch.setattr(cfg, "RUNNING_DIR", tmp_path / "running")
    monkeypatch.setattr(cfg, "LOGS_DIR", tmp_path / "logs")
    monkeypatch.setattr(cfg, "CONFIG_FILE", tmp_path / "config" / "autoswe.env")
    monkeypatch.setattr(cfg, "REPOS_CONFIG_FILE", tmp_path / "config" / "repos.json")
    monkeypatch.setattr(cfg, "HARNESSES_CONFIG_FILE", tmp_path / "config" / "harnesses.json")

    # Clear the harnesses cache so load_harnesses_config re-reads from the new path
    cfg._harnesses_cache.clear()

    monkeypatch.setattr(qs, "AUTOSWE_DIR", tmp_path)
    monkeypatch.setattr(qs, "QUEUE_FILE", tmp_path / "data" / "queue.json")

    return tmp_path

# ---------------------------------------------------------------------------
# Scenario fixtures — stateful fakes for E2E tests
# ---------------------------------------------------------------------------


@pytest.fixture
def github_fake():
    """Stateful in-memory GitHub API fake."""
    from tests.fakes.github_fake import GitHubFake
    return GitHubFake()


@pytest.fixture
def azure_fake():
    """Stateful in-memory Azure DevOps API fake."""
    from tests.fakes.azure_fake import AzureFake
    return AzureFake()


@pytest.fixture
def scripted_claude():
    """Scripted multi-turn Claude SDK fake."""
    from tests.fakes.claude_fake import ClaudeFake
    return ClaudeFake()


@pytest.fixture
def git_fake():
    """Scripted worktree operations fake."""
    from tests.fakes.git_fake import GitFake
    return GitFake()


@pytest.fixture
def git_world(tmp_path, monkeypatch):
    """Real-git sandboxed universe for git_scenario tests.

    Returns a GitWorld instance with a bare remote, AUTOSWE_DIR tree,
    and monkeypatched clone URLs. Tests call world.init_remote() to seed
    content, then use production worktree functions against real git.
    """
    from tests.git_fixtures import GitWorld
    return GitWorld(tmp_path, monkeypatch)


@pytest.fixture
def scenario_cfg(isolated_autoswe_dir, tmp_path):
    """Pre-configured cfg dict and repos.json for scenario tests.

    Returns (cfg_dict, repos_cfg_dict). The repos.json and autoswe.env files
    are created in the isolated AUTOSWE_DIR config directory.
    """
    import autoswe.core.config as cfg_mod

    cfg_dict = {
        "AGENT_TIMEOUT": 7200,
        "MAX_ATTEMPTS": 3,
        "MAX_TOTAL_HOURS": 2,
        "MAX_CONCURRENT": 1,
        "SILENT_REPORTING": True,
        "AUTO_ASSIGN": False,
        "AUTO_CREATE_PR": False,
        "ASSIGN_USER": "",
        "CLAUDE_CLI_PATH": "",
        "PLAN_MODEL": "",
        "FIX_MODEL": "",
        "REVIEW_MODEL": "",
        "PLAN_HARNESS": "",
        "FIX_HARNESS": "",
        "REVIEW_HARNESS": "",
        "ANTHROPIC_AUTH_TOKEN": "",
        "ANTHROPIC_API_KEY": "",
        "ANTHROPIC_BASE_URL": "",
        "WORKTREE_DIR": str(tmp_path / "worktrees"),
    }

    # Write repos.json so load_repos_config works
    repos_cfg = {}
    repos_path = tmp_path / "config" / "repos.json"
    repos_path.write_text(json.dumps(repos_cfg))

    # Patch the config module path constants for repos
    cfg_mod.REPOS_CONFIG_FILE = tmp_path / "config" / "repos.json"
    cfg_mod.WELCOME_FILE = tmp_path / "config" / "welcome_comment.txt"

    return cfg_dict, repos_cfg


def add_repo_to_scenario(tmp_path, monkeypatch, owner_repo: str, repo_cfg: dict) -> None:
    """Helper: add a repo entry to repos.json for a scenario test."""
    import json
    repos_path = tmp_path / "config" / "repos.json"
    data = json.loads(repos_path.read_text()) if repos_path.exists() else {}
    repo_cfg.setdefault("pat", "test-pat-for-scenario")
    data[owner_repo] = repo_cfg
    repos_path.write_text(json.dumps(data))


def seed_queue_task(isolated_autoswe_dir, task: dict) -> None:
    """Write a task into the queue.json of an isolated AUTOSWE_DIR."""
    from autoswe.core.queue_store import LockedQueue
    task.setdefault("autoswe_status", None)
    with LockedQueue() as lq:
        lq.queue[task["id"]] = dict(task)


# ---------------------------------------------------------------------------
# Azure fixtures
# ---------------------------------------------------------------------------

ADO_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "azure"


def load_ado_fixture(name: str):
    return json.loads(ADO_FIXTURE_DIR.joinpath(name).read_text(encoding="utf-8"))


@pytest.fixture
def ado_route_table():
    """Empty dict tests fill with (method, path_prefix) -> response for ADO."""
    return {}


@pytest.fixture
def mock_ado_request(monkeypatch, ado_route_table):
    """Patch autoswe.providers.azure.api._ado_request.

    Routes match by (method, prefix) where prefix is matched against the
    request path with ``startswith``.  Tests register paths in ado_route_table
    keyed by tuple.  If no route matches, raises RuntimeError so tests fail
    loudly on un-stubbed calls.
    """
    calls = []

    def fake_request(method, path, pat, body=None, content_type="application/json", max_retries=3):
        calls.append({"method": method, "path": path, "body": body, "pat": pat})
        for (m, prefix), response in ado_route_table.items():
            if m == method and path.startswith(prefix):
                if callable(response):
                    return response(method, path, pat, body)
                return response
        raise RuntimeError(f"unstubbed ado request: {method} {path}")

    import autoswe.providers.azure.api as ado_module
    monkeypatch.setattr(ado_module, "_ado_request", fake_request)
    fake_request.calls = calls
    return fake_request


# ---------------------------------------------------------------------------
# Live test fixtures (shared across test files)
# ---------------------------------------------------------------------------

@pytest.fixture
def live_token():
    """Return the GITHUB_TOKEN from env, or skip if not set."""
    import os
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        pytest.skip("GITHUB_TOKEN not set")
    return token


@pytest.fixture
def ado_live_cfg():
    """Return Azure repo_cfg from env or autoswe.env, or skip if not set."""
    import os
    pat = os.environ.get("AZURE_DEVOPS_PAT", "")
    org = os.environ.get("AZURE_DEVOPS_ORG", "")
    project = os.environ.get("AZURE_DEVOPS_PROJECT", "")
    repo = os.environ.get("AZURE_DEVOPS_REPO", "")

    from autoswe.core.config import load_config
    cfg = load_config()

    if not pat:
        pat = cfg.get("AZURE_DEVOPS_PAT", "")
    if not org:
        org = cfg.get("AZURE_DEVOPS_ORG", "natedorr")
    if not project:
        project = cfg.get("AZURE_DEVOPS_PROJECT", "testProject")
    if not repo:
        repo = cfg.get("AZURE_DEVOPS_REPO", "testProject")

    if not pat:
        pytest.skip("AZURE_DEVOPS_PAT not set (env vars or autoswe.env)")

    return {
        "provider": "azure",
        "org": org,
        "project": project,
        "repo": repo,
        "pat": pat,
    }
