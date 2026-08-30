"""Repo-supplied MCP servers, hooks, and skills coexist with autoSWE's injected servers.

Issue #122: the Claude Code backend is intentionally left on the SDK defaults
(``strict_mcp_config`` unset → ``False``, ``setting_sources`` unset → all
sources), so a target repo's ``.mcp.json`` servers and ``.claude/settings.json``
hooks load *alongside* autoSWE's injected ``autoswe_comment`` /
``autoswe_inline_comment`` servers. This is the intended deployment model:
autoSWE runs on a dedicated, isolated machine (see docs/autoswe/safeguards.md),
so untrusted-repo MCP servers and hooks running in the session is by design.

The offline test below pins the option invariants that guarantee that
coexistence: the SDK itself performs the merge of ``options.mcp_servers`` with
the repo ``.mcp.json`` at runtime, so the fake cannot observe the union — it can
only assert that autoSWE's option shape is one that lets the repo servers and
project settings load rather than suppress them.
"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import patch

from claude_agent_sdk import ResultMessage


def _autoswe_servers() -> dict:
    """autoSWE's injected comment server, shaped like mcp_config.build_mcp_comment_server."""
    return {
        "autoswe_comment": {
            "command": "/usr/bin/env python",
            "args": ["-m", "mcp_servers.autoswe_comment_server"],
            "env": {"AUTOSWE_COMMENT_ID": "12345", "AUTOSWE_PROVIDER": "github"},
        },
    }


def _make_fixture_repo(tmp_path) -> tuple[str, str]:
    """Create a fixture repo with a repo-supplied MCP server and a project hook.

    Returns (cwd, repo_server_name). The repo server name is deliberately
    different from autoSWE's to prove there is no name shadowing.
    """
    repo_server = "repo_db"
    (tmp_path / ".mcp.json").write_text(json.dumps({
        "mcpServers": {
            repo_server: {
                "command": "npx",
                "args": ["-y", "@bytebase/dbhub"],
            },
        },
    }))
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "settings.json").write_text(json.dumps({
        "hooks": {
            "PreToolUse": [
                {"matcher": "Bash", "hooks": [{"type": "command", "command": "echo auditing"}]},
            ],
        },
    }))
    return str(tmp_path), repo_server


async def _capture_options(prompt: str, cwd: str, mcp_servers: dict) -> object:
    """Run the Claude Code backend with a fake query that records the options.

    Returns the ClaudeAgentOptions object the backend constructed.
    """
    from autoswe.harness.backends.base import RunSpec
    from autoswe.harness.backends.claude_code import ClaudeCodeBackend

    captured = {}

    async def fake_query(*args, **kwargs):
        captured["options"] = kwargs.get("options", args[1] if len(args) > 1 else None)
        # Single terminal message so the backend's processing loop completes.
        yield ResultMessage(
            subtype="success",
            duration_ms=100,
            duration_api_ms=100,
            is_error=False,
            num_turns=1,
            session_id="sess-repo-mcp",
            stop_reason="end_turn",
            total_cost_usd=0.0,
        )

    spec = RunSpec(
        prompt=prompt,
        cwd=cwd,
        mode="read_only",
        mcp_servers=mcp_servers,
    )
    sdk = __import__("claude_agent_sdk", fromlist=["query"])
    with patch.object(sdk, "query", fake_query):
        await ClaudeCodeBackend().run(spec)
    return captured["options"]


def test_fixture_repo_is_well_formed(tmp_path):
    """The fixture repo carries a repo-supplied MCP server and a project hook,
    exactly the shape issue #122 asks us to exercise: a target repo with its own
    .mcp.json and a .claude/settings.json hook."""
    cwd, repo_server = _make_fixture_repo(tmp_path)

    mcp_cfg = json.loads((tmp_path / ".mcp.json").read_text())
    assert repo_server in mcp_cfg["mcpServers"]

    hooks_cfg = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    assert "PreToolUse" in hooks_cfg["hooks"]
    assert cwd == str(tmp_path)


def test_repo_and_autoswe_servers_coexist(tmp_path):
    """autoSWE's injected servers are present AND repo settings are not suppressed.

    With ``strict_mcp_config=False`` (unset) and ``setting_sources=None`` (unset),
    the SDK loads the repo ``.mcp.json`` and ``.claude/settings.json`` in
    addition to ``options.mcp_servers``. The fake asserts the option shape that
    makes this coexistence happen.
    """
    cwd, repo_server = _make_fixture_repo(tmp_path)
    options = asyncio.run(_capture_options("plan the fix", cwd, _autoswe_servers()))

    # autoSWE's injected comment server is passed to the SDK as-is.
    assert "autoswe_comment" in options.mcp_servers
    # The repo server is *not* in options.mcp_servers — it arrives via the repo
    # .mcp.json, so a name-collision shadow test: it must not appear under
    # autoSWE's namespace either.
    assert repo_server not in options.mcp_servers

    # The critical invariants: repo MCP servers and project settings (hooks,
    # skills, CLAUDE.md) are NOT suppressed.
    assert options.strict_mcp_config is False, (
        "strict_mcp_config=True would ignore the repo .mcp.json and "
        "user/plugin servers — autoSWE intentionally loads them"
    )
    assert options.setting_sources is None, (
        "setting_sources must stay unset (all sources) so the project "
        ".claude/settings.json hooks and skills load"
    )

    # cwd points at the fixture repo, so the SDK resolves its .mcp.json there.
    assert options.cwd == cwd


def test_autoswe_server_names_are_stable_and_unique(tmp_path):
    """autoSWE's injected servers use stable, unique names (`autoswe_comment`
    and `autoswe_inline_comment`), so they are not expected to collide with a
    repo's `.mcp.json` server names.

    This is an offline, name-uniqueness check: it pins that the backend
    forwards autoSWE's own server dict untouched, and that the autoSWE name
    does not overlap the fixture repo's server name. It does NOT assert a
    same-name collision precedence — the shipped SDK docs rank only *file*
    scopes (local > project > user > plugin), so programmatic-vs-`.mcp.json`
    precedence for an identical name is not documented and is not verified here.
    """
    cwd, repo_server = _make_fixture_repo(tmp_path)
    options = asyncio.run(_capture_options("plan the fix", cwd, _autoswe_servers()))

    # The backend forwards autoSWE's server dict untouched.
    assert options.mcp_servers["autoswe_comment"]["env"]["AUTOSWE_COMMENT_ID"] == "12345"
    # autoSWE's name and the repo's name are distinct — no collision by construction.
    assert repo_server != "autoswe_comment"
    assert repo_server not in options.mcp_servers


def test_inline_server_is_mcp_version_tolerant():
    """Issue #122 (review finding): requirements.txt permits mcp<3, so a fresh
    install lands on mcp 2.x, under which the 1.x-only ``Server.call_tool()``
    API no longer exists. The inline comment server must import cleanly under
    whichever mcp major version is installed, selecting the matching API.

    This is an offline import test: it loads the module by path under the
    installed mcp version and asserts (a) it imports without AttributeError,
    (b) the version branch (_MCP_V2) matches whether mcp.server exposes the
    high-level MCPServer, and (c) the post_inline_comment tool is registered.
    """
    import importlib.util
    from pathlib import Path

    import mcp.server

    has_v2 = hasattr(mcp.server, "MCPServer")

    mod_path = Path(__file__).resolve().parent.parent / "mcp_servers" / "autoswe_inline_comment_server.py"
    spec = importlib.util.spec_from_file_location("autoswe_inline_comment_server_under_test", mod_path)
    module = importlib.util.module_from_spec(spec)
    # Loading must not raise AttributeError('Server' object has no attribute 'call_tool')
    # under mcp 2.x — that was the regression this test guards against.
    spec.loader.exec_module(module)

    # The branch chosen must match the installed mcp major version.
    assert module._MCP_V2 is has_v2, (
        f"_MCP_V2={module._MCP_V2} but installed mcp.server.MCPServer exists={has_v2} "
        "— version-tolerance branch selected the wrong API"
    )
    # The tool is registered and exposed on the module.
    assert hasattr(module, "post_inline_comment")


def test_setting_sources_default_loads_project_settings():
    """Directly pin the SDK default that the backend relies on: an unset
    setting_sources means the project settings source (hooks, skills, MCP)
    is active. Guards against a future 'hardening' that silently passes
    setting_sources=[] or strict_mcp_config=True.
    """
    from claude_agent_sdk import ClaudeAgentOptions

    # Mirrors claude_code.py: the backend never sets these two kwargs, so they
    # fall back to the SDK defaults.
    options = ClaudeAgentOptions(cwd="/tmp")
    assert options.strict_mcp_config is False
    assert options.setting_sources is None
