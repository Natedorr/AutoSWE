"""autoSWE Inline PR Comment MCP Server — lets Claude leave file-level PR review comments.

When /fix runs against a branch that already has a PR, this server gives Claude
a tool to post inline comments at specific file:line locations — far more
usable than a single big completion comment for PR review workflows.

Reads env vars:
    AUTOSWE_PROVIDER   — "github" or "azure"
    AUTOSWE_OWNER      — repo owner / org
    AUTOSWE_REPO       — repo name / project
    AUTOSWE_PR_NUMBER  — PR number
    AUTOSWE_TOKEN      — PAT for the provider API
    AUTOSWE_COMMIT_SHA — required: the commit SHA to comment on (GitHub-only)

Registered tool name (Claude SDK prefix):
    mcp__autoswe_inline_comment__post_inline_comment
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib import error as url_error
from urllib import request

from mcp.types import TextContent

# The MCP servers run as separate `python -m` processes. Make the repo root
# importable so autoswe.core.constants (the GH API-version pin) resolves even
# when the server is launched from a non-repo cwd.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from autoswe.core.constants import GH_API_VERSION  # noqa: E402

# mcp SDK version tolerance (mirrors autoswe_comment_server.py):
#   mcp >= 2.0 exposes the high-level MCPServer (.tool() decorator, run_stdio_async)
#   mcp 1.x only exposes the low-level Server (.call_tool() decorator, server.run)
try:
    from mcp.server import MCPServer

    server = MCPServer("autoswe-inline-comment")
    _tool = server.tool
    _MCP_V2 = True
except ImportError:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server

    server = Server("autoswe-inline-comment")
    _tool = server.call_tool
    _MCP_V2 = False

# ---- Env ----

PROVIDER = os.environ.get("AUTOSWE_PROVIDER", "github").lower()
OWNER = os.environ.get("AUTOSWE_OWNER", "")
REPO = os.environ.get("AUTOSWE_REPO", "")
PR_NUMBER = int(os.environ.get("AUTOSWE_PR_NUMBER", "0"))
TOKEN = os.environ.get("AUTOSWE_TOKEN", "")
COMMIT_SHA = os.environ.get("AUTOSWE_COMMIT_SHA", "")


# ---- HTTP helpers (no external deps) ----

def _http(method: str, url: str, body: dict | None) -> dict:
    """Minimal HTTP request with provider-specific auth headers."""
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": GH_API_VERSION,
        "Content-Type": "application/json",
    }

    if PROVIDER == "github":
        headers["Authorization"] = f"Bearer {TOKEN}"

    data = json.dumps(body).encode() if body else None
    req = request.Request(url, data=data, method=method, headers=headers)
    try:
        with request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except url_error.HTTPError as e:
        content = e.read().decode() if hasattr(e, "read") else ""
        raise RuntimeError(f"HTTP {e.code}: {content}") from e


def _post_inline_comment(file: str, line: int, body: str) -> str:
    """Post an inline PR review comment. Returns the comment HTML URL."""
    if PROVIDER != "github":
        raise RuntimeError(f"Unsupported provider: {PROVIDER}")
    if not COMMIT_SHA:
        raise RuntimeError("AUTOSWE_COMMIT_SHA env var is required for inline comments")

    url = f"https://api.github.com/repos/{OWNER}/{REPO}/pulls/{PR_NUMBER}/comments"
    result = _http("POST", url, {
        "body": body,
        "path": file,
        "line": line,
        "commit_id": COMMIT_SHA,
    })
    return result.get("html_url", "")


# ---- MCP Server ----


@_tool()
async def post_inline_comment(*, file: str, line: int, body: str) -> list[TextContent]:
    """Post an inline review comment on a specific file and line of the PR.

    Use this to leave file-level feedback at precise locations in the PR diff.
    The comment appears in the PR's Files Changed tab.

    Args:
        file: The file path (e.g. "src/foo.py")
        line: The line number in the file (1-indexed)
        body: The comment text
    """
    try:
        url = _post_inline_comment(file, line, body)
        return [TextContent(type="text", text=f"Inline comment posted at {file}:{line} — {url}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error posting inline comment: {e}")]


# ---- Entry point ----

async def main():
    if _MCP_V2:
        await server.run_stdio_async()
    else:
        async with stdio_server() as (stdin, stdout):
            await server.run(stdin, stdout, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
