"""Shared MCP server config for planner and coder."""
from __future__ import annotations

import sys
from pathlib import Path


def build_mcp_comment_server(task: dict, repo_cfg: dict) -> dict | None:
    """Build the MCP server config dict for the comment server.

    Returns None if no comment_id is set (dispatch ran without sticky comment).
    """
    comment_id = task.get("_comment_id")
    if comment_id is None:
        return None

    provider = (repo_cfg or {}).get("provider", "github")
    return {
        "autoswe_comment": {
            "command": sys.executable,
            "args": ["-m", "mcp_servers.autoswe_comment_server"],
            "env": {
                "AUTOSWE_COMMENT_ID": str(comment_id),
                "AUTOSWE_PROVIDER": provider,
                "AUTOSWE_OWNER": task.get("owner", ""),
                "AUTOSWE_REPO": task.get("repo", ""),
                "AUTOSWE_ISSUE_NUMBER": str(task.get("issue_number", 0)),
                "AUTOSWE_TOKEN": task.get("_token", ""),
                "AUTOSWE_SUPPRESS_POSTING": "1" if task.get("_minimal_posting") else "0",
            },
        },
    }


def build_mcp_inline_comment_server(task: dict, repo_cfg: dict, commit_sha: str, pr_number: int) -> dict | None:
    """Build the MCP server config dict for the inline PR comment server.

    Only useful when an existing PR exists and we have a commit SHA to comment on.
    Returns None if provider is not github or parameters are missing.
    """
    provider = (repo_cfg or {}).get("provider", "github")
    if provider != "github":
        return None
    if not commit_sha or not pr_number:
        return None

    return {
        "autoswe_inline_comment": {
            "command": sys.executable,
            "args": ["-m", "mcp_servers.autoswe_inline_comment_server"],
            "env": {
                "AUTOSWE_PROVIDER": provider,
                "AUTOSWE_OWNER": task.get("owner", ""),
                "AUTOSWE_REPO": task.get("repo", ""),
                "AUTOSWE_PR_NUMBER": str(pr_number),
                "AUTOSWE_TOKEN": task.get("_token", ""),
                "AUTOSWE_COMMIT_SHA": commit_sha,
            },
        },
    }


def build_pi_mcp_json(python_path: str, repo_root: str) -> dict:
    """Build the agent-dir ``mcp.json`` dict that wires pi to the comment server.

    Phase 1 of ``docs/autoswe/PLAN-pi-mcp.md``: pi reaches the comment MCP server
    through the pi-mcp-adapter, which reads ``<agent dir>/mcp.json`` (NOT a
    ``.mcp.json`` in the target worktree, which would pollute the repo under
    test and trip project trust). The shape is per the plan, with two
    adaptations forced by the adapter (verified against pi-mcp-adapter 2.31.0):

    - ``command`` is used **verbatim** — the adapter does not interpolate
      ``${VAR}`` in ``command`` (only in ``args``/``env``/``cwd``/``url``). So
      the resolved Python path is baked in directly instead of a
      ``${AUTOSWE_PYTHON}`` token.
    - ``cwd`` *is* interpolated, but we bake the repo root in anyway: it is a
      stable value and keeps the file env-independent (the server itself adds
      the repo root to ``sys.path``, so the module resolves regardless).

    Only stable values are baked here (python path, repo root). The per-task
    values live in the MCP server's own env — the pi backend routes that into
    the subprocess env rather than this file, so the file never changes between
    issues and is written once per host. ``toolPrefix`` is ``"mcp"`` so the
    direct tools surface as ``mcp__autoswe_comment_<tool>``; the three
    ``body``-only tools are the ones the planner/coder/reviewer use. The
    settings freeze direct-tool registration and disable sampling/elicitation
    (a non-interactive run must not block on an approval dialog).
    """
    return {
        "mcpServers": {
            "autoswe_comment": pi_mcp_comment_server(python_path, repo_root),
        },
        "settings": {"freezeDirectTools": True, "sampling": False, "elicitation": False},
    }


def pi_mcp_comment_server(python_path: str, repo_root: str) -> dict:
    """The ``autoswe_comment`` server entry alone (the ``mcpServers`` value).

    Exposed so the pi backend can merge just this entry into an existing
    ``mcp.json`` without clobbering other operators' servers.
    """
    return {
        "command": python_path,
        "args": ["-m", "mcp_servers.autoswe_comment_server"],
        "cwd": repo_root,
        "toolPrefix": "mcp",
        "directTools": ["post_plan", "post_question", "update_progress"],
    }


def pi_mcp_json_path(agent_dir: str) -> Path:
    """Path to the agent-dir ``mcp.json`` (``<agent dir>/mcp.json``)."""
    return Path(agent_dir).expanduser() / "mcp.json"


def pi_mcp_cache_path(agent_dir: str) -> Path:
    """Path to the pi-mcp-adapter metadata cache (``<agent dir>/mcp-cache.json``).

    Phase 4 of ``docs/autoswe/PLAN-pi-mcp.md``: on a cold start (no valid
    ``autoswe_comment`` entry in this cache) the adapter falls back to the
    generic proxy shapes rather than the direct ``mcp__autoswe_comment_*``
    tools, so the first run against a new server degrades. The cache path is
    where PiBackend's preflight and the setup-time warm-up look for a
    pre-populated entry.
    """
    return Path(agent_dir).expanduser() / "mcp-cache.json"


def autoswe_repo_root() -> str:
    """The autoSWE checkout root — where the ``mcp_servers`` package lives.

    ``python -m mcp_servers.autoswe_comment_server`` must start from a cwd that
    can *locate* the ``mcp_servers`` package, so the MCP server's ``cwd`` is
    this checkout root, NOT the target worktree (pi's subprocess cwd). This is
    the only repo-root reference the pi path needs; it is stable for the host.
    """
    return str(Path(__file__).resolve().parent.parent.parent)
