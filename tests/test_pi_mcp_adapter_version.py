"""Guard: the pi-mcp-adapter autoSWE's pi backend depends on must not fall below its floor.

Sibling of ``test_cli_version.py`` (the Claude Code CLI) and ``test_sdk_version.py``
(the Claude Agent SDK), which guard the *Python* side. The pi backend reaches the
autoswe_comment MCP server through the pi-mcp-adapter (an npm package installed in
pi's agent dir), and Phase 1 of ``docs/autoswe/PLAN-pi-mcp.md`` depends on three
adapter internals — its tool **naming** (``mcp__<server>_<tool>``), its metadata
**cache hashing** (the ``mcp-cache.json`` cold-start path), and **env passthrough**
into the MCP server child. A too-old adapter drifts on any of those and surfaces
as a run that silently reverts to tag-scraping rather than a clear "upgrade your
adapter".

Floor rationale: **v2.31.0** is the version every Phase 0-4 spike was verified
against (``docs/autoswe/spike-pi-mcp.md``). Bumping the floor is a one-line change:
update ``MIN_ADAPTER_VERSION`` here.

Resolution mirrors production: the agent dir is ``PI_CODING_AGENT_DIR`` when set
(that is where a harness profile's ``agent_dir`` points pi), else pi's default
``~/.pi/agent``. The adapter's version is read from
``<agent dir>/npm/node_modules/pi-mcp-adapter/package.json``. When the package is
not installed (no pi backend in use, or a host without npm packages vendored into
the agent dir) the test **skips** rather than fails — same posture as the CLI and
SDK guards.
"""

import json
import os
import re
from pathlib import Path

import pytest

# Keep in lockstep with the version verified in docs/autoswe/spike-pi-mcp.md.
MIN_ADAPTER_VERSION = "2.31.0"

_ADAPTER_PACKAGE = "npm/node_modules/pi-mcp-adapter/package.json"


def _vtuple(version: str) -> tuple[int, ...]:
    """Parse a dotted version into a comparable integer tuple.

    ``"2.31.0"`` → ``(2, 31, 0)``. Only the numeric run is taken. Stdlib only, so
    the module stays collectable in minimal environments (no ``packaging`` dep) —
    the same reason as the CLI/SDK guards.
    """
    return tuple(int(part) for part in re.findall(r"\d+", version))


def _resolve_agent_dir() -> Path:
    """The agent dir a pi run would use: PI_CODING_AGENT_DIR, else pi's default."""
    override = (os.environ.get("PI_CODING_AGENT_DIR") or "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".pi" / "agent"


def _adapter_package_json(agent_dir: Path) -> Path:
    return agent_dir / _ADAPTER_PACKAGE


def _installed_version(agent_dir: Path) -> str | None:
    """Return the installed pi-mcp-adapter version string, or None if absent."""
    package = _adapter_package_json(agent_dir)
    try:
        data = json.loads(package.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    version = data.get("version") if isinstance(data, dict) else None
    if version is None:
        return None
    version = str(version).strip()
    return version or None


def test_pi_mcp_adapter_meets_pinned_floor():
    """The resolvable pi-mcp-adapter must be >= MIN_ADAPTER_VERSION."""
    agent_dir = _resolve_agent_dir()
    version = _installed_version(agent_dir)
    if version is None:
        pytest.skip(
            f"no pi-mcp-adapter found at {_adapter_package_json(agent_dir)} — "
            "MCP adapter floor not applicable (no pi backend in use, or packages "
            "not vendored into the agent dir)."
        )

    parsed = _vtuple(version)
    assert parsed, f"could not parse a version out of pi-mcp-adapter {version!r}"
    assert parsed >= _vtuple(MIN_ADAPTER_VERSION), (
        f"pi-mcp-adapter {version!r} (in {agent_dir}) is below the pinned floor "
        f"{MIN_ADAPTER_VERSION} (see docs/autoswe/PLAN-pi-mcp.md). "
        f"Reinstall the latest: pi install npm:pi-mcp-adapter "
        f"(or refresh the agent dir's npm packages)."
    )


# --- The guard's own tests -------------------------------------------------
# A version guard that can only ever pass or skip is not a guard. These pin the
# three behaviours that matter: it parses the package.json version, it fails on a
# too-old adapter, and it skips (never fails) when there is nothing to check.


def _self():
    """This module, for monkeypatching its own module-level helpers."""
    import sys

    return sys.modules[__name__]


@pytest.mark.parametrize(
    "reported,expected",
    [
        ("2.31.0", (2, 31, 0)),
        ("2.31.1", (2, 31, 1)),
        ("3.0.0", (3, 0, 0)),
    ],
)
def test_vtuple_parses_adapter_version(reported, expected):
    assert _vtuple(reported) == expected


def test_vtuple_orders_by_component_not_lexically():
    """2.9 < 2.31.0 — the trap a string comparison would fall into."""
    assert _vtuple("2.9") < _vtuple("2.31.0")
    assert _vtuple("2.32.0") > _vtuple("2.31.0")


def test_guard_fails_on_adapter_below_floor(monkeypatch):
    monkeypatch.setattr(_self(), "_resolve_agent_dir", lambda: Path("/agent"))
    monkeypatch.setattr(_self(), "_installed_version", lambda agent_dir: "2.20.0")
    with pytest.raises(AssertionError, match="below the pinned floor"):
        test_pi_mcp_adapter_meets_pinned_floor()


def test_guard_passes_on_adapter_at_floor(monkeypatch):
    monkeypatch.setattr(_self(), "_resolve_agent_dir", lambda: Path("/agent"))
    monkeypatch.setattr(_self(), "_installed_version", lambda agent_dir: MIN_ADAPTER_VERSION)
    test_pi_mcp_adapter_meets_pinned_floor()


def test_guard_skips_when_no_adapter_installed(monkeypatch):
    """No pi-mcp-adapter in the agent dir — that is not a failure."""
    monkeypatch.setattr(_self(), "_resolve_agent_dir", lambda: Path("/agent"))
    monkeypatch.setattr(_self(), "_installed_version", lambda agent_dir: None)
    with pytest.raises(pytest.skip.Exception):
        test_pi_mcp_adapter_meets_pinned_floor()


def test_resolution_prefers_env_agent_dir(monkeypatch):
    """PI_CODING_AGENT_DIR beats pi's default agent dir."""
    monkeypatch.setenv("PI_CODING_AGENT_DIR", "/custom/agent")
    assert _resolve_agent_dir() == Path("/custom/agent")


def test_resolution_defaults_to_pi_agent_dir(monkeypatch):
    monkeypatch.delenv("PI_CODING_AGENT_DIR", raising=False)
    assert _resolve_agent_dir() == Path.home() / ".pi" / "agent"


def test_installed_version_reads_package_json(tmp_path):
    """The guard reads the version from the vendored package.json on disk."""
    package = _adapter_package_json(tmp_path)
    package.parent.mkdir(parents=True)
    package.write_text(json.dumps({"name": "pi-mcp-adapter", "version": "2.31.0"}), encoding="utf-8")
    assert _installed_version(tmp_path) == "2.31.0"


def test_installed_version_none_when_missing(tmp_path):
    assert _installed_version(tmp_path) is None


def test_installed_version_none_on_malformed(tmp_path):
    package = _adapter_package_json(tmp_path)
    package.parent.mkdir(parents=True)
    package.write_text("{not json", encoding="utf-8")
    assert _installed_version(tmp_path) is None
