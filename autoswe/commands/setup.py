"""Interactive first-run setup wizard for autoSWE.

Stdlib only (getpass, input, json, pathlib).  Collects repo credentials,
writes config/repos.json and config/autoswe.env, and offers a smoke-test sync.
"""
from __future__ import annotations

import getpass
import json
import sys
from pathlib import Path
from urllib import error as url_error
from urllib import request

from autoswe.core.config import AUTOSWE_DIR, REPOS_CONFIG_FILE
from autoswe.core.logging_utils import mask_sensitive

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_ENV_FILE = AUTOSWE_DIR / "config" / "autoswe.env"

_ENV_SCHEMA = [
    ("MAX_CONCURRENT",    "1",       "Max simultaneous agent jobs"),
    ("MAX_ATTEMPTS",      "3",       "Max restart attempts per issue before failing"),
    ("MAX_TOTAL_HOURS",   "2",       "Max total time per issue in hours"),
    ("AGENT_TIMEOUT",     "7200",    "Max Claude session runtime in seconds"),
    ("AGENT_RETRY_ON_FAILURE", "0", "Retry agent on timeout/SDK error (0=no retry, 1=retry once; useful for Ollama)"),
    ("WORKTREE_DIR",      "worktrees", "Worktree root directory (relative or absolute)"),
    ("SILENT_REPORTING",  "false",   "Suppress welcome comments (true/false)"),
    ("MINIMAL_POSTING",   "false",   "Two API calls per dispatch: start post + final result (true/false)"),
    ("AUTO_ASSIGN",       "true",    "Auto-assign issues to authenticated user (true/false)"),
    ("ASSIGN_USER",       "",        "Override assignee login (blank = token owner)"),
    ("AUTO_CREATE_PR",    "false",   "Automatically open a PR after /fix succeeds (true/false)"),
    ("CLAUDE_CLI_PATH",   "",        "Path to claude binary (blank = use PATH)"),
    ("PLAN_MODEL",        "",        "Model for /plan phase (blank = SDK default)"),
    ("FIX_MODEL",         "",        "Model for /fix phase (blank = SDK default)"),
    ("REVIEW_MODEL",      "",        "Model for /review phase (blank = SDK default)"),
    ("ANTHROPIC_AUTH_TOKEN", "",     "Auth token (e.g. 'ollama' for local server)"),
    ("ANTHROPIC_API_KEY",    "",     "Anthropic API key"),
    ("ANTHROPIC_BASE_URL",   "",     "API endpoint (e.g. http://localhost:11434)"),
]

_ANTHROPIC_KEYS = {"ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL"}


def _prompt(label: str, default: str = "", secret: bool = False) -> str:
    display = f"{label} [{default}]: " if default else f"{label}: "
    try:
        val = getpass.getpass(display) if secret else input(display)
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)
    return val.strip() if val.strip() else default


def _prompt_yes_no(label: str, default: bool = False) -> bool:
    hint = "Y/n" if default else "y/N"
    val = _prompt(f"{label} ({hint})", default="y" if default else "n")
    return val.lower() in ("y", "yes")


def _prompt_choice(label: str, choices: list[str]) -> str:
    numbered = "  ".join(f"[{i+1}] {c}" for i, c in enumerate(choices))
    while True:
        val = _prompt(f"{label} {numbered}", default="1")
        if val.isdigit() and 1 <= int(val) <= len(choices):
            return choices[int(val) - 1]
        val_lower = val.lower()
        for c in choices:
            if c.lower().startswith(val_lower):
                return c
        print(f"  Please enter a number 1–{len(choices)} or one of: {', '.join(choices)}")


# ---------------------------------------------------------------------------
# GitHub flow
# ---------------------------------------------------------------------------

def _gh_verify(token: str) -> str | None:
    """Return the authenticated login, or None on failure."""
    try:
        req = request.Request(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        with request.urlopen(req, timeout=10) as resp:
            scopes = resp.headers.get("X-OAuth-Scopes", "")
            data = json.loads(resp.read())
            login = data.get("login", "")
            if scopes and "repo" not in scopes and "workflow" not in scopes:
                print(f"  Warning: token scopes are '{scopes}' — 'repo' scope may be needed.")
            return login
    except (url_error.HTTPError, url_error.URLError, Exception):
        return None


def _gh_list_repos(token: str) -> list[str]:
    """Return list of 'owner/repo' strings for repos the token can access."""
    try:
        from autoswe.tracking.api import fetch_owned_repos
        return fetch_owned_repos(token)
    except Exception:
        return []


def _wizard_github() -> dict:
    """Run the GitHub PAT + repo selection flow. Returns new repos_cfg entries."""
    print("\n--- GitHub ---")
    while True:
        token = _prompt("GitHub PAT (repo scope)", secret=True)
        if not token:
            print("  PAT is required.")
            continue
        login = _gh_verify(token)
        if login:
            print(f"  Authenticated as {login}")
            break
        print("  Could not authenticate — check the token and try again.")

    repos_by_name = _gh_list_repos(token)

    entries: dict[str, dict] = {}

    if repos_by_name:
        print(f"\n  Found {len(repos_by_name)} accessible repo(s):")
        for i, r in enumerate(repos_by_name[:30]):
            print(f"    [{i+1}] {r}")
        if len(repos_by_name) > 30:
            print(f"    … and {len(repos_by_name)-30} more")
        val = _prompt(
            "\n  Enter numbers to add (comma-separated), 'all', or type 'owner/repo' manually",
            default="",
        )
    else:
        print("  Could not list repos automatically.")
        val = ""

    selected: list[str] = []
    if val.lower() == "all":
        selected = repos_by_name
    elif val:
        for part in val.split(","):
            part = part.strip()
            if part.isdigit():
                idx = int(part) - 1
                if 0 <= idx < len(repos_by_name):
                    selected.append(repos_by_name[idx])
            elif "/" in part:
                selected.append(part)
    if not selected:
        manual = _prompt("  Enter repo as owner/repo (or blank to skip)", default="")
        if manual:
            selected = [manual]

    for repo_path in selected:
        default_branch = _gh_default_branch(token, repo_path) or "main"
        base_branch = _prompt(f"  Base branch for {repo_path}", default=default_branch)
        auto_dispatch = _prompt_yes_no(
            f"  Auto-dispatch new issues in {repo_path} without a slash command?",
            default=False,
        )
        entries[repo_path] = {
            "provider": "github",
            "base_branch": base_branch,
            "pat": token,
            "auto_dispatch_new": auto_dispatch,
        }
        print(f"  Added {repo_path}")

    return entries


def _gh_default_branch(token: str, repo_path: str) -> str | None:
    try:
        req = request.Request(
            f"https://api.github.com/repos/{repo_path}",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        with request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return data.get("default_branch")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Azure DevOps flow
# ---------------------------------------------------------------------------

def _ado_verify(org: str, pat: str) -> bool:
    """Return True if the PAT can list projects in the org."""
    try:
        from autoswe.providers.azure.api import _ado_request
        _ado_request(
            "GET",
            f"https://dev.azure.com/{org}/_apis/projects?api-version=7.1",
            pat,
            max_retries=1,
        )
        return True
    except Exception:
        return False


def _wizard_azure() -> dict:
    """Run the Azure DevOps flow. Returns new repos_cfg entries."""
    print("\n--- Azure DevOps ---")
    org = _prompt("Azure DevOps organization name")
    if not org:
        print("  Skipping Azure.")
        return {}

    while True:
        pat = _prompt(f"Azure PAT for {org}", secret=True)
        if not pat:
            print("  PAT is required.")
            continue
        if _ado_verify(org, pat):
            print("  Azure PAT verified.")
            break
        print("  Could not authenticate — check the PAT and organization name.")

    entries: dict[str, dict] = {}

    projects = _ado_list_projects(org, pat)
    selected_repos: list[tuple[str, str, str]] = []

    if projects:
        print(f"\n  Found {len(projects)} project(s):")
        for i, p in enumerate(projects[:20]):
            print(f"    [{i+1}] {p}")
        val = _prompt("  Enter project numbers or names (comma-separated, or blank to type manually)", default="")
        chosen_projects: list[str] = []
        if val:
            for part in val.split(","):
                part = part.strip()
                if part.isdigit():
                    idx = int(part) - 1
                    if 0 <= idx < len(projects):
                        chosen_projects.append(projects[idx])
                elif part:
                    chosen_projects.append(part)
        else:
            manual_project = _prompt("  Project name (blank to skip)", default="")
            if manual_project:
                chosen_projects = [manual_project]

        for project in chosen_projects:
            repos = _ado_list_repos(org, project, pat)
            if repos:
                print(f"\n  Repos in {project}:")
                for i, r in enumerate(repos):
                    print(f"    [{i+1}] {r}")
                rv = _prompt(f"  Add repos from {project} (numbers, 'all', or blank to skip)", default="")
                if rv.lower() == "all":
                    selected_repos.extend((org, project, r) for r in repos)
                elif rv:
                    for part in rv.split(","):
                        part = part.strip()
                        if part.isdigit():
                            idx = int(part) - 1
                            if 0 <= idx < len(repos):
                                selected_repos.append((org, project, repos[idx]))
            else:
                manual_repo = _prompt(f"  Repo name in {project} (blank to skip)", default="")
                if manual_repo:
                    selected_repos.append((org, project, manual_repo))
    else:
        project = _prompt("  Project name (blank to skip)", default="")
        repo_name = _prompt("  Repo name (blank to skip)", default="") if project else ""
        if project and repo_name:
            selected_repos.append((org, project, repo_name))

    for (org_, project_, repo_) in selected_repos:
        key = f"{org_}/{project_}/{repo_}"
        base_branch = _prompt(f"  Base branch for {key}", default="main")
        entries[key] = {
            "provider": "azure",
            "base_branch": base_branch,
            "pat": pat,
        }
        print(f"  Added {key}")

    return entries


def _ado_list_projects(org: str, pat: str) -> list[str]:
    try:
        from autoswe.providers.azure.api import _ado_request
        data = _ado_request(
            "GET",
            f"https://dev.azure.com/{org}/_apis/projects?api-version=7.1",
            pat,
        )
        return [p["name"] for p in data.get("value", [])]
    except Exception:
        return []


def _ado_list_repos(org: str, project: str, pat: str) -> list[str]:
    try:
        from autoswe.providers.azure.api import _ado_request
        data = _ado_request(
            "GET",
            f"https://dev.azure.com/{org}/{project}/_apis/git/repositories?api-version=7.1",
            pat,
        )
        return [r["name"] for r in data.get("value", [])]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# autoswe.env wizard
# ---------------------------------------------------------------------------

def _wizard_env() -> dict[str, str]:
    """Ask autoswe.env questions. Returns only non-default values."""
    print("\n--- autoswe.env settings (press Enter to keep default) ---")

    use_custom_anthropic = _prompt_yes_no(
        "Do you use a custom Anthropic endpoint (e.g. Ollama)?", default=False
    )

    values: dict[str, str] = {}
    for key, default, description in _ENV_SCHEMA:
        if key in _ANTHROPIC_KEYS and not use_custom_anthropic:
            continue
        val = _prompt(f"  {key} — {description}", default=default)
        if val != default:
            values[key] = val

    return values


def _write_env(path: Path, values: dict[str, str]) -> None:
    """Write autoswe.env with comments carried from the schema."""
    key_to_comment = {k: desc for k, _, desc in _ENV_SCHEMA}
    lines = [
        "# autoSWE Poller configuration",
        "# Repository credentials live in config/repos.json — one 'pat' per entry.",
        "",
    ]
    for key, val in values.items():
        comment = key_to_comment.get(key, "")
        if comment:
            lines.append(f"# {comment}")
        lines.append(f"{key}={val}")
        lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------

def _run_smoke_test(repo_path: str, cfg: dict) -> None:
    """Run a single poll cycle (sync-only) to verify credentials work."""
    print(f"\n  Running sync smoke test for {repo_path} …")
    try:
        from autoswe.orch.loop import poll as orch_poll
        orch_poll(cfg, mode="sync", repo_filter=repo_path)
        print("  Smoke test passed.")
    except Exception as e:
        print(f"  Smoke test failed: {mask_sensitive(str(e))}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def cmd_setup(args, cfg: dict) -> None:
    """Interactive first-run setup wizard."""
    force = getattr(args, "force", False)

    print("autoSWE Setup Wizard")
    print("=" * 40)
    print("This wizard creates config/repos.json (credentials + repo settings)")
    print("and config/autoswe.env (runtime settings).")
    print()

    # Load existing repos to merge
    existing_repos: dict = {}
    if REPOS_CONFIG_FILE.exists() and not force:
        try:
            existing_repos = json.loads(REPOS_CONFIG_FILE.read_text(encoding="utf-8"))
            non_comment = {k: v for k, v in existing_repos.items() if not k.startswith("_")}
            if non_comment:
                print(f"Found existing repos.json with {len(non_comment)} repo(s).")
                if not _prompt_yes_no("Add more repos (merging with existing)?", default=True):
                    print("Keeping existing repos.json unchanged.")
                    existing_repos = {}  # skip repo phase
                    _do_repo_phase = False
                else:
                    _do_repo_phase = True
            else:
                _do_repo_phase = True
        except (json.JSONDecodeError, OSError):
            _do_repo_phase = True
    else:
        _do_repo_phase = True

    new_repos: dict = {}
    if _do_repo_phase:
        provider_choice = _prompt_choice(
            "Which provider(s) do you want to configure?",
            ["github", "azure", "both"],
        )

        if provider_choice in ("github", "both"):
            new_repos.update(_wizard_github())

        if provider_choice in ("azure", "both"):
            new_repos.update(_wizard_azure())

        if not new_repos:
            print("\nNo repos configured. Run setup again when ready.")
            return

        merged = {**existing_repos, **new_repos}
        REPOS_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        REPOS_CONFIG_FILE.write_text(json.dumps(merged, indent=2), encoding="utf-8")
        print(f"\nWrote {REPOS_CONFIG_FILE} ({len(merged)} repo(s)).")

    # autoswe.env
    env_path = _ENV_FILE
    if env_path.exists() and not force:
        if not _prompt_yes_no(f"\n{env_path} already exists — overwrite settings?", default=False):
            print("Keeping existing autoswe.env.")
        else:
            env_values = _wizard_env()
            _write_env(env_path, env_values)
            print(f"Wrote {env_path}.")
    else:
        env_values = _wizard_env()
        _write_env(env_path, env_values)
        print(f"Wrote {env_path}.")

    # Smoke test
    first_repo = next(iter(new_repos.keys())) if new_repos else None
    if first_repo and _prompt_yes_no(
        f"\nRun a sync smoke test against {first_repo}?", default=True
    ):
        _run_smoke_test(first_repo, cfg)

    # Next steps
    print("\nSetup complete!")
    print("Next: schedule the poller to run every 10 minutes:")
    print("  Linux/macOS:  crontab -e  →  */10 * * * * /path/to/poller.sh >> logs/poller.log 2>&1")
    print("  Windows:      Run 'poller.ps1' as a Task Scheduler job (see poller.ps1 header).")
