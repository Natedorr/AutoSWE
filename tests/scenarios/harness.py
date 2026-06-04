"""Consolidated test harness for scenario and transition tests.

Replaces ~170 lines of duplicated monkeypatching in both
``test_scenarios_github.py`` and ``test_scenarios_azure.py``.

Usage::

    state, expected = load_scenario(scenario_dir)

    with patched_world(
        "github",
        state=state,
        claude_responses=state.get("claude_responses", []),
        scripted_git=expected.get("git_calls", []),
    ) as hw:
        run_one_turn(owner, repo, cfg, hw.autoswe_dir)

    assert_label_is(hw.fake, issue_number, expected["label_after"])
    assert_comments_posted(hw.fake, expected.get("comments_posted", []))
    assert_claude_calls(hw.claude, expected.get("claude_calls", []))
    assert_queue_task(hw.autoswe_dir, task_id, expected.get("queue_task_after", {}))
"""
from __future__ import annotations

import os
import subprocess as _subproc
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tests.fakes.azure_fake import AzureFake
from tests.fakes.claude_fake import ClaudeFake
from tests.fakes.codex_fake import CodexFake
from tests.fakes.git_fake import GitFake
from tests.fakes.github_fake import GitHubFake
from tests.scenarios.runner import (  # noqa: F401
    assert_claude_calls,
    assert_codex_calls,
    assert_comments_posted,
    assert_git_calls,
    assert_label_is,
    assert_no_git_calls,
    assert_queue_task,
    discover_scenarios,
    load_scenario,
    run_one_turn,
    seed_queue,
    setup_repos_json,
)

# ---------------------------------------------------------------------------
# Data class returned by patched_world

@dataclass
class HarnessWorld:
    """Objects exposed to tests inside a ``patched_world`` block."""

    fake: GitHubFake | AzureFake
    claude: ClaudeFake | None
    codex: CodexFake | None
    git: GitFake
    autoswe_dir: Path
    concurrent: bool = False
    backend: str = "claude_code"


# ---------------------------------------------------------------------------
# Import site lists — centralized so fakes don't need to know about callers

_gh_post_comment_modules = frozenset((
    "autoswe.orch.loop",
    "autoswe.harness.planner",
    "autoswe.vcs.ship",
))

_direct_worktree_imports: dict[str, list[str]] = {
    "autoswe.harness.planner": ["create_worktree"],
    "autoswe.harness.coder": ["create_worktree", "commit_and_push", "worktree_path", "get_merge_conflict_files"],
    "autoswe.harness.reviewer": ["create_worktree", "worktree_path"],
    "autoswe.orch.run": ["worktree_path", "create_worktree", "sync_branch", "get_merge_conflict_files"],
}


# ---------------------------------------------------------------------------
# _PatchManager — tracks and restores all monkeypatches


class _PatchManager:
    """Collect monkeypatches and restore them in __exit__."""

    def __init__(self):
        self._restorers: list[Any] = []

    def add(self, restorer) -> None:
        """Prepend a restorer function (so they unwind in LIFO order)."""
        self._restorers.insert(0, restorer)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        for restore in self._restorers:
            restore()
        self._restorers.clear()
        return False

    def patch_api_fake(self, fake: GitHubFake | AzureFake) -> None:
        """Patch the API fake (_gh_request or _ado_request)."""
        mod, orig = fake.patch()
        self.add(lambda: fake.unpatch(mod, orig))

    def patch_gh_post_comment(self, fake: GitHubFake | AzureFake) -> None:
        """Route gh_post_comment through the fake."""
        import autoswe.tracking.api as api_mod

        gh_post_orig = api_mod.gh_post_comment

        def fake_post_comment(o, r, n, body, token):
            fake.handle_request("POST",
                f"/repos/{o}/{r}/issues/{n}/comments", token, body={"body": body})

        api_mod.gh_post_comment = fake_post_comment
        patched_mods = []
        for mod_name in _gh_post_comment_modules:
            if mod_name in sys.modules:
                mod = sys.modules[mod_name]
                if hasattr(mod, "gh_post_comment"):
                    patched_mods.append(mod)
                    mod.gh_post_comment = fake_post_comment

        def restore():
            api_mod.gh_post_comment = gh_post_orig
            def _no_op(*_a, **_k):
                pass
            for mod in patched_mods:
                mod.gh_post_comment = _no_op

        self.add(restore)

    def patch_git(self, gt_fake: GitFake) -> None:
        """Patch worktree functions and direct imports."""
        gt_mod, gt_originals = gt_fake.patch()

        # Also patch direct imports (from X import Y)
        direct_origs = {}
        for mod_name, func_names in _direct_worktree_imports.items():
            if mod_name in sys.modules:
                mod = sys.modules[mod_name]
                for fn in func_names:
                    if hasattr(mod, fn):
                        direct_origs.setdefault(mod, {})
                        direct_origs[mod][fn] = getattr(mod, fn)
                        setattr(mod, fn, getattr(gt_fake, fn))

        def restore():
            gt_fake.unpatch(gt_mod, gt_originals)
            for mod, fn_map in direct_origs.items():
                for fn, orig in fn_map.items():
                    setattr(mod, fn, orig)

        self.add(restore)

    def patch_claude(self, cl_fake: ClaudeFake) -> None:
        """Patch runner.run and import sites."""
        cl_mod, cl_orig = cl_fake.patch()
        self.add(lambda: cl_fake.unpatch(cl_mod, cl_orig))

    def patch_codex(self, cx_fake: CodexFake) -> None:
        """Patch asyncio.create_subprocess_exec for Codex backend."""

        orig = cx_fake._get_real_create()
        asyncio_mod, _ = cx_fake.patch()

        def restore():
            asyncio_mod.create_subprocess_exec = orig

        self.add(restore)

    def patch_concurrent(self, force: bool) -> None:
        """Stub _is_task_running to simulate a concurrent dispatch."""
        import autoswe.orch.loop as loop_mod

        orig_is_task_running = loop_mod._is_task_running
        if force:
            loop_mod._is_task_running = lambda slug: True

        def restore():
            loop_mod._is_task_running = orig_is_task_running

        self.add(restore)

    def patch_subprocess(self, fake_it: bool) -> None:
        """Optionally stub subprocess.run."""
        if not fake_it:
            return
        orig = _subproc.run

        def fake_subprocess_run(*a, **kw):
            class FakeResult:
                returncode = 0
                stdout = ""
                stderr = ""
            return FakeResult()

        _subproc.run = fake_subprocess_run
        self.add(lambda: setattr(_subproc, "run", orig))

    def patch_plan_file(self) -> None:
        """Suppress plan file detection in scenario tests."""
        import autoswe.harness.planner as planner_mod
        orig = planner_mod._find_latest_plan_file
        planner_mod._find_latest_plan_file = lambda: None

        def restore():
            planner_mod._find_latest_plan_file = orig

        self.add(restore)


# ---------------------------------------------------------------------------
# Codex harness setup


def _setup_codex_harness(isolated_dir: Path) -> None:
    """Write harnesses.json with a codex profile for scenario tests.

    Creates ``config/harnesses.json`` with a ``"codex"`` profile so that
    ``resolve_harness`` returns a codex backend for all phases.
    """
    import json

    harnesses_dir = isolated_dir / "config"
    harnesses_dir.mkdir(parents=True, exist_ok=True)

    harnesses_cfg = {
        "codex": {
            "backend": "codex",
            "model": "gpt-5.4",
        }
    }

    harnesses_path = harnesses_dir / "harnesses.json"
    harnesses_path.write_text(json.dumps(harnesses_cfg, indent=2), encoding="utf-8")

    # Clear the harnesses cache so the next load picks up our file
    import autoswe.core.config as cfg_mod

    cfg_mod.HARNESSES_CONFIG_FILE = harnesses_path
    cfg_mod._harnesses_cache.clear()


@contextmanager
def patched_world(
    provider: str,
    *,
    state: dict,
    claude_responses: list[dict] | None = None,
    scripted_git: list[str] | None = None,
    concurrent: bool = False,
    fake_subprocess: bool | None = None,
    isolated_dir: Path,
    row_meta: dict | None = None,
    backend: str = "claude_code",
):
    """Patch all fakes into autoswe modules for one test turn.

    :param provider: ``"github"`` or ``"azure"``.
    :param state: Scenario state dict (will be passed to ``fake.load()``).
    :param claude_responses: List of ``{"text", "session_id?", "subtype?"}`` dicts.
    :param scripted_git: List of git function names to script (``"commit_and_push"``,
        ``"sync_branch"``).  If present, the corresponding scripted results are
        pre-configured on the git fake.
    :param row_meta: Optional dict from transition row ``"meta"`` field, used to
        pass extra scripting flags (e.g. ``script_sync_conflict``).
    :param concurrent: If True, stub ``count_running_jobs`` to return 1.
    :param fake_subprocess: If True, stub ``subprocess.run`` to succeed silently.
        When ``None`` (default), auto-fakes subprocess if any scripted git call
        involves ``resolve_sync_conflicts`` (the resolver invokes subprocess
        directly for the post-resolution push).
    :param isolated_dir: The per-test AUTOSWE_DIR path.
    :param backend: ``"claude_code"`` (default, patches ``runner.run``) or
        ``"codex"`` (patches ``asyncio.create_subprocess_exec`` so the real
        CodexBackend runs end-to-end).  When ``"codex"``, the existing
        ``claude_responses`` dicts are fed through ``CodexFake``.
    :yields: ``HarnessWorld`` with access to all fakes.
    """
    claude_responses = claude_responses or []
    scripted_git = scripted_git or []

    # ---- Create fakes ----
    fake = (GitHubFake() if provider.lower() == "github" else AzureFake())
    gt_fake = GitFake()

    if backend == "codex":
        cx_fake = CodexFake()
        cl_fake = None
        # Feed the existing claude_responses dicts through CodexFake
        for resp in claude_responses:
            cx_fake.script_response(
                resp["text"],
                session_id=resp.get("session_id", "s1"),
                subtype=resp.get("subtype", "success"),
            )
    else:
        cx_fake = None
        cl_fake = ClaudeFake()
        for resp in claude_responses:
            cl_fake.script_response(
                resp["text"],
                session_id=resp.get("session_id", "s1"),
                subtype=resp.get("subtype", "success"),
                plan_posted=resp.get("plan_posted", False),
                question_posted=resp.get("question_posted", False),
            )

    # Load state into the API fake
    fake.load(state)

    # Script git operations
    _script_git_ops(gt_fake, scripted_git, state, row_meta or {})

    # Auto-fake subprocess when resolve_sync_conflicts is in scripted git calls,
    # or when script_sync_conflict is set (the resolver invokes subprocess
    # directly for the post-resolution push)
    # Also auto-fake for review transitions (reviewer._run_git uses subprocess.run)
    if fake_subprocess is None and (
        "resolve_sync_conflicts" in scripted_git
        or (row_meta and row_meta.get("script_sync_conflict"))
        or (row_meta and row_meta.get("script_review"))
    ):
        fake_subprocess = True

    # For codex backend, write harnesses.json and set cfg harness vars
    if backend == "codex":
        _setup_codex_harness(isolated_dir)

    # ---- Apply all patches ----
    with _PatchManager() as pm:
        pm.patch_subprocess(fake_subprocess)
        pm.patch_concurrent(concurrent)
        pm.patch_plan_file()

        if backend == "codex":
            pm.patch_codex(cx_fake)
        else:
            pm.patch_claude(cl_fake)

        pm.patch_git(gt_fake)
        pm.patch_gh_post_comment(fake)
        pm.patch_api_fake(fake)

        yield HarnessWorld(
            fake=fake,
            claude=cl_fake,
            codex=cx_fake,
            git=gt_fake,
            autoswe_dir=isolated_dir,
            concurrent=concurrent,
            backend=backend,
        )


# ---------------------------------------------------------------------------
# Git operation scripting


def _script_git_ops(
    gt_fake: GitFake,
    git_calls: list[str],
    state: dict,
    row_meta: dict | None = None,
) -> None:
    """Pre-configure git fake based on expected git calls and transition meta."""
    row_meta = row_meta or {}
    issue_number = state.get("issue", {}).get("number", 1)
    if "issue" not in state:
        issue_number = state.get("work_item", {}).get("id", 1)
    branch = f"autoswe/issue-{issue_number}"

    # commit_and_push always needs a scripted commit result
    if "commit_and_push" in git_calls:
        gt_fake.script_commit({
            "committed": True,
            "commit_sha": "abc1234",
            "branch": branch,
        })

    # sync_branch scripting: conflict scenarios get a conflict result;
    # everything else gets a clean sync result
    if row_meta.get("script_sync_conflict"):
        # Conflict resolution scenario — sync_branch returns a merge conflict
        gt_fake.script_sync({
            "synced": False,
            "conflict": True,
            "rebase": False,
            "branch": branch,
            "conflict_files": ["src/main.py"],
        })
    elif "sync_branch" in git_calls or "commit_and_push" in git_calls:
        # Fix scenarios always run sync before fix via _run_fix_with_sync
        gt_fake.script_sync({
            "synced": True,
            "conflict": False,
            "branch": branch,
            "ahead": 1,
            "commit_sha": "abc1234",
            "changed": True,
        })


# ---------------------------------------------------------------------------
# Config helpers


def build_test_cfg(isolated_dir: Path, provider: str = "github", backend: str = "claude_code") -> dict:
    """Build a standard config dict for scenario tests.

    When *backend* is ``"codex"``, the returned config sets ``PLAN_HARNESS``,
    ``FIX_HARNESS``, and ``REVIEW_HARNESS`` to ``"codex"`` so that all three
    phases resolve to the Codex backend.
    """
    cfg: dict[str, Any] = {
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
        "ANTHROPIC_AUTH_TOKEN": "",
        "ANTHROPIC_API_KEY": "",
        "ANTHROPIC_BASE_URL": "",
        "WORKTREE_DIR": str(isolated_dir / "worktrees"),
    }
    if backend == "codex":
        cfg["PLAN_HARNESS"] = "codex"
        cfg["FIX_HARNESS"] = "codex"
        cfg["REVIEW_HARNESS"] = "codex"
    return cfg


def setup_repos(isolated_dir: Path, provider: str, state: dict) -> None:
    """Write repos.json for a scenario test."""
    import json

    if provider.lower() == "azure":
        repo_key = f"{state['org']}/{state['project']}/{state['repo']}"
        repos_cfg = {
            "provider": "azure",
            "org": state["org"],
            "project": state["project"],
            "pat": "azure_pat_test",
            "base_branch": "main",
        }
    else:
        repo_key = f"{state['owner']}/{state['repo']}"
        repos_cfg = {"provider": "github", "base_branch": "main", "pat": "ghp_scenario_token"}

    repos_data = {repo_key: repos_cfg}
    repos_path = isolated_dir / "config" / "repos.json"
    repos_path.write_text(json.dumps(repos_data, indent=2), encoding="utf-8")


def make_task_id(provider: str, state: dict) -> str:
    """Build the task slug for a scenario."""
    if provider.lower() == "azure":
        wi_number = state["work_item"]["id"]
        return f"ado:{state['org']}_{state['project']}/{state['repo']}_{wi_number}"
    issue_number = state["issue"]["number"]
    return f"gh:{state['owner']}_{state['repo']}_{issue_number}"


@contextmanager
def scenario_env(state: dict, cfg: dict | None = None):
    """Manage cfg/env vars that scenarios may need."""
    auto_create_pr = bool(state.get("auto_create_pr"))
    orig_cfg_val = cfg.get("AUTO_CREATE_PR") if cfg is not None else None
    if auto_create_pr:
        if cfg is not None:
            cfg["AUTO_CREATE_PR"] = True
        os.environ["AUTO_CREATE_PR"] = "true"
    try:
        yield
    finally:
        os.environ.pop("AUTO_CREATE_PR", None)
        if cfg is not None and auto_create_pr:
            cfg["AUTO_CREATE_PR"] = orig_cfg_val
