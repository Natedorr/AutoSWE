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

import json
import os
from urllib import error as url_error
from urllib import request

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent

BOT_MARKER = "<!-- autoswe-bot -->"


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




# ---- HTTP helpers (no external deps) ----

def _http(method: str, url: str, body: dict | None) -> dict:
    """Minimal HTTP request with provider-specific auth headers."""
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
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


def _ado_http(method: str, url: str, body: dict | None) -> dict:
    """HTTP request with Azure DevOps Basic auth (empty username, PAT as password)."""
    auth = ("", TOKEN)
    b64 = __import__("base64").b64encode(
        ":".join(auth).encode()
    ).decode()
    headers = {
        "Authorization": f"Basic {b64}",
        "Content-Type": "application/json",
    }
    data = json.dumps(body).encode() if body else None
    req = request.Request(url, data=data, method=method, headers=headers)
    try:
        with request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except url_error.HTTPError as e:
        content = e.read().decode() if hasattr(e, "read") else ""
        raise RuntimeError(f"HTTP {e.code}: {content}") from e


def _post_comment(body: str) -> str:
    """Post a comment. Returns the comment ID as string."""
    if PROVIDER == "github":
        url = f"https://api.github.com/repos/{OWNER}/{REPO}/issues/{ISSUE_NUMBER}/comments"
        result = _http("POST", url, {"body": _tag(body)})
        return str(result.get("id", ""))
    elif PROVIDER == "azure":
        url = (
            f"https://dev.azure.com/{OWNER}/{REPO}/_apis/wit/workItems/"
            f"{ISSUE_NUMBER}/comments?format=Markdown&api-version=7.1-preview.4"
        )
        result = _ado_http("POST", url, {"text": body})
        return str(result.get("id", ""))
    else:
        raise RuntimeError(f"Unsupported provider: {PROVIDER}")


def _update_comment(comment_id: str, body: str) -> None:
    """Edit an existing comment."""
    if PROVIDER == "github":
        url = f"https://api.github.com/repos/{OWNER}/{REPO}/issues/comments/{comment_id}"
        _http("PATCH", url, {"body": _tag(body)})
    elif PROVIDER == "azure":
        url = (
            f"https://dev.azure.com/{OWNER}/{REPO}/_apis/wit/workItems/"
            f"{ISSUE_NUMBER}/comments/{comment_id}?format=Markdown&api-version=7.1-preview.4"
        )
        _ado_http("PATCH", url, {"text": body})
    else:
        raise RuntimeError(f"Unsupported provider: {PROVIDER}")


# ---- MCP Server ----

server = Server("autoswe-comment")


@server.call_tool()
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


@server.call_tool()
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


@server.call_tool()
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


# ---- Entry point ----

async def main():
    async with stdio_server() as (stdin, stdout):
        await server.run(stdin, stdout, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
