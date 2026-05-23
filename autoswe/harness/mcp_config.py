"""Shared MCP server config for planner and coder."""
from __future__ import annotations

import sys


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
