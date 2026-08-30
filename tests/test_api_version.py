"""Tests for the pinned GitHub REST API version (``GH_API_VERSION``).

Issue #133 asks for a single source of truth for the ``X-GitHub-Api-Version``
header value so that bumping the pin when GitHub's recommended version moves
is a one-line change. These tests guard that invariant:

- the constant holds the expected value,
- every call site references the constant (no duplicate string literal),
- the documented pin in docs/autoswe/config.md matches the constant.

The MCP servers can't be imported offline (they need the ``mcp`` SDK), so they
are checked by source scan rather than import.
"""
from __future__ import annotations

import re
from pathlib import Path

import autoswe.core.constants as constants
import autoswe.tracking.api as tracking_api

REPO_ROOT = Path(__file__).resolve().parent.parent

# The string literal that must NOT appear at any call site — only in the
# constant definition and in vendored/docs/fixtures (checked separately).
_PIN = "2022-11-28"

# Python source files that must use the constant (no bare literal).
_CALL_SITE_SOURCES = [
    REPO_ROOT / "autoswe" / "tracking" / "api.py",
    REPO_ROOT / "autoswe" / "commands" / "setup.py",
    REPO_ROOT / "mcp_servers" / "autoswe_comment_server.py",
    REPO_ROOT / "mcp_servers" / "autoswe_inline_comment_server.py",
]


def test_constant_value():
    """The pin holds the expected value; guards against accidental bumps."""
    assert constants.GH_API_VERSION == _PIN


def test_tracking_api_reexports_constant():
    """autoswe.tracking.api.GH_API_VERSION is the same object as the leaf constant."""
    assert tracking_api.GH_API_VERSION is constants.GH_API_VERSION
    assert tracking_api.GH_API_VERSION == _PIN


def test_no_duplicate_literal_at_call_sites():
    """No call-site source file contains the bare version literal."""
    for path in _CALL_SITE_SOURCES:
        text = path.read_text(encoding="utf-8")
        assert _PIN not in text, f"{path.relative_to(REPO_ROOT)} still pins the literal {_PIN!r}"


def test_call_sites_reference_constant():
    """Each call site references GH_API_VERSION (not just avoids the literal)."""
    for path in _CALL_SITE_SOURCES:
        text = path.read_text(encoding="utf-8")
        assert "GH_API_VERSION" in text, (
            f"{path.relative_to(REPO_ROOT)} does not reference GH_API_VERSION"
        )


def test_call_sites_send_header_with_constant():
    """The X-GitHub-Api-Version header value is the constant at every site."""
    header_pattern = re.compile(r'"X-GitHub-Api-Version":\s*GH_API_VERSION')
    for path in _CALL_SITE_SOURCES:
        text = path.read_text(encoding="utf-8")
        assert header_pattern.search(text), (
            f"{path.relative_to(REPO_ROOT)} does not set X-GitHub-Api-Version from GH_API_VERSION"
        )


def test_docs_pin_matches_constant():
    """docs/autoswe/config.md documents the current pinned value."""
    doc = (REPO_ROOT / "docs" / "autoswe" / "config.md").read_text(encoding="utf-8")
    assert constants.GH_API_VERSION in doc, (
        "docs/autoswe/config.md does not mention the pinned value "
        f"{constants.GH_API_VERSION!r} — update the pin section"
    )
