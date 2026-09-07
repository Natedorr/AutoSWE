"""autoSWE Comment MCP Server — lets Claude post/update comments via MCP tools.

Replaces the fragile <AUTOSWE_PLAN> regex protocol. Claude calls tools instead
of emitting XML tags, so the orchestrator doesn't need to parse output text.

Reads env vars:
    AUTOSWE_PROVIDER   — "github" or "azure"
    AUTOSWE_OWNER      — repo owner / org
    AUTOSWE_REPO       — repo name / project
    AUTOSWE_ISSUE_NUMBER — issue number
    AUTOSWE_TOKEN      — PAT for the provider API
    AUTOSWE_COMMENT_ID — optional; when set, update_claude_comment edits this
                         comment in-place (sticky progress).

Registered tool names (Claude SDK prefix):
    mcp__autoswe_comment__update_progress
    mcp__autoswe_comment__post_plan
    mcp__autoswe_comment__post_question
"""
from __future__ import annotations

import os
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path

from mcp.types import TextContent

# The MCP servers run as separate `python -m` processes. Make the repo root
# importable so the provider stack resolves even when the server is launched
# from a non-repo cwd.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from autoswe.providers.factory import get_tracker  # noqa: E402

# mcp SDK version tolerance:
#   mcp >= 2.0 exposes the high-level MCPServer (.tool() decorator, run_stdio_async)
#   mcp 1.x only exposes the low-level Server (.call_tool() decorator, server.run)
try:
    from mcp.server import MCPServer

    server = MCPServer("autoswe-comment")
    _tool = server.tool
    _MCP_V2 = True
except ImportError:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server

    server = Server("autoswe-comment")
    _tool = server.call_tool
    _MCP_V2 = False

BOT_MARKER = "<!-- autoswe-bot -->"

# The three tools all take a single `body: str`.  Used by the low-level mcp 1.x
# path's hand-rolled tools/list + dispatching tools/call handler (see the
# _MCP_V2 gate below): the 1.x Server registers neither from the @tool()
# decorator the way the high-level MCPServer does.
_BODY_SCHEMA = {
    "type": "object",
    "properties": {"body": {"type": "string"}},
    "required": ["body"],
}


def _tag(body: str) -> str:
    """Idempotently append BOT_MARKER so every outbound comment is detectable."""
    if BOT_MARKER not in body:
        body = body.rstrip() + "\n" + BOT_MARKER
    return body


# ---- Env ----

PROVIDER = os.environ.get("AUTOSWE_PROVIDER", "github").lower()
OWNER = os.environ.get("AUTOSWE_OWNER", "")
REPO = os.environ.get("AUTOSWE_REPO", "")
ISSUE_NUMBER = int(os.environ.get("AUTOSWE_ISSUE_NUMBER", "0"))
TOKEN = os.environ.get("AUTOSWE_TOKEN", "")
COMMENT_ID = os.environ.get("AUTOSWE_COMMENT_ID", "")
SUPPRESS_POSTING = os.environ.get("AUTOSWE_SUPPRESS_POSTING", "0") == "1"


def _repo_cfg() -> dict:
    """Build the repo_cfg the provider tracker is constructed from."""
    return {
        "provider": PROVIDER,
        "owner": OWNER,
        "repo": REPO,
        "token": TOKEN,
    }


def _post_comment(body: str) -> str:
    """Post a comment. Returns the comment ID as string.

    Routed through the provider tracker so the MCP path shares the same
    redaction, retry, and auth handling as the rest of the poller
    (issue #168 F-06).
    """
    tracker = get_tracker(_repo_cfg())
    comment_id = tracker.post_comment(ISSUE_NUMBER, _tag(body))
    return str(comment_id) if comment_id is not None else ""


def _update_comment(comment_id: str, body: str) -> None:
    """Edit an existing comment via the provider tracker (F-06)."""
    if not comment_id:
        return
    tracker = get_tracker(_repo_cfg())
    tracker.update_comment(ISSUE_NUMBER, int(comment_id), _tag(body))


# ---- MCP Tools ----


async def update_progress(*, body: str) -> list[TextContent]:
    """Update the sticky progress comment with current tool-use status.

    Call this as you work through the task. Example:
    - "Running: pytest tests/"
    - "Editing: src/foo.py"
    - "Writing: tests/bar.py"
    """
    if SUPPRESS_POSTING:
        return [TextContent(type="text", text="suppressed (minimal posting)")]
    try:
        if COMMENT_ID:
            _update_comment(COMMENT_ID, body)
            return [TextContent(type="text", text=f"Updated progress: {body[:60]}")]
        else:
            return [TextContent(type="text", text="No sticky comment ID set; skipping")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error updating progress: {e}")]


async def post_plan(*, body: str) -> list[TextContent]:
    """Post the implementation plan as a comment on the issue.

    Call this when you have a complete plan. The plan should include the
    approach, files to modify, and any questions for the user.
    """
    if not body or not body.strip():
        return [TextContent(type="text", text="Error: body cannot be empty — provide the plan content")]
    if SUPPRESS_POSTING:
        return [TextContent(type="text", text="suppressed (minimal posting)")]
    try:
        cid = _post_comment(body)
        return [TextContent(type="text", text=f"Plan posted (comment_id={cid})")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error posting plan: {e}")]


async def post_question(*, body: str) -> list[TextContent]:
    """Post a question to the user as a comment on the issue.

    Call this when you need clarification before proceeding. The comment
    will signal that autoSWE is waiting for a user reply.
    """
    if not body or not body.strip():
        return [TextContent(type="text", text="Error: body cannot be empty — provide the question text")]
    if SUPPRESS_POSTING:
        return [TextContent(type="text", text="suppressed (minimal posting)")]
    try:
        cid = _post_comment(body)
        return [TextContent(type="text", text=f"Question posted (comment_id={cid})")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error posting question: {e}")]


# The name -> (handler, description) map.  The three tools all share the
# ``_BODY_SCHEMA`` input shape, so one dispatch table covers registration and
# dispatch on the low-level 1.x path.
_TOOLS: dict[str, tuple[Callable[..., Awaitable[list[TextContent]]], str]] = {
    "update_progress": (update_progress, "Update the sticky progress comment with current tool-use status."),
    "post_plan": (post_plan, "Post the implementation plan as a comment on the issue."),
    "post_question": (post_question, "Post a question to the user as a comment on the issue."),
}


# ---- Registration ----
#
# The mcp 2.x high-level server auto-registers both tools/list and tools/call
# from the @server.tool() decorators, so register each tool individually there.
#
# The mcp 1.x low-level Server is different in two ways, both of which break a
# tools/list-based client like pi-mcp-adapter, so the 1.x path registers by hand:
#   * it does NOT answer tools/list from the @call_tool() decorator — clients
#     that discover tools that way see zero tools.
#   * @call_tool() overwrites the single CallToolRequest handler slot on every
#     registration, so three separate @call_tool() tools leave only the LAST
#     one reachable (every call routes to it) — the others are silently dropped.
# So on 1.x we register one dispatching tools/call handler (routed via _TOOLS)
# plus a hand-rolled tools/list, instead of three colliding decorators.
if _MCP_V2:
    for _name in _TOOLS:
        @_tool()
        async def _v2_tool(name=_name, *, body: str) -> list[TextContent]:
            return await _TOOLS[name][0](body)
else:
    @server.list_tools()
    async def _list_tools() -> list:
        from mcp.types import Tool

        return [
            Tool(name=name, description=desc, inputSchema=_BODY_SCHEMA)
            for name, (_, desc) in _TOOLS.items()
        ]

    @server.call_tool()
    async def _dispatch_call_tool(name: str, arguments: dict) -> list[TextContent]:
        handler = _TOOLS.get(name, (None,))[0]
        if handler is None:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
        return await handler(body=str(arguments.get("body", "")))


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
