"""Guard: the Claude Code CLI autoSWE would actually invoke must not fall below its floor.

Sibling of ``test_sdk_version.py``, which guards the *Python* package. That guard is
not sufficient on its own: the binary is resolved at dispatch time, either from an
operator-pinned ``CLAUDE_CLI_PATH`` or from ``PATH``, so it can drift independently of
anything pip controls — and a too-old CLI surfaces as an opaque failure deep inside a
run rather than as a clear "upgrade your CLI".

Floor rationale (see ``docs/autoswe/config.md``): **v2.1.233** is the
``CLAUDE_CODE_ENABLE_TODO_TOOLS`` floor — the tools the Claude backend enables by default
to drive the sticky progress comment — and it also clears the Opus 5 floor (v2.1.219) and
the Sonnet 5 floor (v2.1.197).

Resolution mirrors production (``core/config.py`` → ``ClaudeCodeBackend``): the pinned
``CLAUDE_CLI_PATH`` wins, else whatever ``claude`` is on ``PATH``. When neither resolves,
the test **skips** rather than fails — the SDK ships its own bundled CLI, and a
Codex-only deploy has no ``claude`` binary at all. Same posture as the SDK guard.

Bumping the floor is a one-line change: update ``MIN_CLI_VERSION`` here and the version
quoted in ``docs/autoswe/config.md`` to match.
"""

import re
import shutil
import subprocess
import sys

import pytest

# Keep in lockstep with the floor documented in docs/autoswe/config.md.
MIN_CLI_VERSION = "2.1.233"

_VERSION_TIMEOUT_S = 30


def _vtuple(version: str) -> tuple[int, ...]:
    """Parse a dotted version into a comparable integer tuple.

    ``"2.1.259 (Claude Code)"`` → ``(2, 1, 259)``. Only the leading numeric run is
    taken, so the trailing product name in the CLI's own output is ignored. Stdlib
    only, for the same reason as the SDK guard: no ``packaging`` dependency, so the
    module stays collectable in minimal environments.
    """
    return tuple(int(part) for part in re.findall(r"\d+", version.split("(")[0]))


def _resolve_cli() -> str | None:
    """The binary a dispatch would invoke: pinned CLAUDE_CLI_PATH, else PATH."""
    try:
        from autoswe.core.config import load_config

        pinned = (load_config().get("CLAUDE_CLI_PATH") or "").strip()
    except Exception:
        pinned = ""
    if pinned:
        return pinned
    return shutil.which("claude")


def _installed_version(cli: str) -> str | None:
    """Return the CLI's reported version string, or None if it cannot be queried."""
    try:
        proc = subprocess.run(
            [cli, "--version"],
            capture_output=True,
            text=True,
            timeout=_VERSION_TIMEOUT_S,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return (proc.stdout or proc.stderr).strip() or None


def test_cli_meets_pinned_floor():
    """The resolvable Claude Code CLI must be >= MIN_CLI_VERSION."""
    cli = _resolve_cli()
    if cli is None:
        pytest.skip(
            "no claude binary resolved (CLAUDE_CLI_PATH unset and none on PATH) — "
            "CLI floor not applicable (e.g. Codex-only deploy, or the SDK's bundled CLI)."
        )

    reported = _installed_version(cli)
    if reported is None:
        pytest.skip(f"could not query `{cli} --version` — CLI floor not enforceable here.")

    parsed = _vtuple(reported)
    assert parsed, f"could not parse a version out of `{cli} --version` output: {reported!r}"
    assert parsed >= _vtuple(MIN_CLI_VERSION), (
        f"Claude Code CLI {reported!r} (resolved to {cli}) is below the pinned floor "
        f"{MIN_CLI_VERSION} (see docs/autoswe/config.md). "
        f"Run: npm install -g @anthropic-ai/claude-code@latest "
        f"(or clear CLAUDE_CLI_PATH to use the SDK's bundled CLI)."
    )


# --- The guard's own tests -------------------------------------------------
# A version guard that can only ever pass or skip is not a guard. These pin the
# three behaviours that matter: it parses the CLI's real output format, it fails
# on a too-old binary, and it skips (never fails) when there is nothing to check.


def _self():
    """This module, for monkeypatching its own module-level helpers."""
    return sys.modules[__name__]


@pytest.mark.parametrize(
    "reported,expected",
    [
        ("2.1.259 (Claude Code)", (2, 1, 259)),
        ("2.1.233", (2, 1, 233)),
        ("  2.10.4 (Claude Code)\n", (2, 10, 4)),
    ],
)
def test_vtuple_parses_cli_output(reported, expected):
    assert _vtuple(reported) == expected


def test_vtuple_orders_by_component_not_lexically():
    """2.1.9 < 2.1.233 — the trap a string comparison would fall into."""
    assert _vtuple("2.1.9") < _vtuple("2.1.233")
    assert _vtuple("2.2.0") > _vtuple("2.1.259")


def test_guard_fails_on_cli_below_floor(monkeypatch):
    monkeypatch.setattr(_self(), "_resolve_cli", lambda: "/usr/bin/claude")
    monkeypatch.setattr(_self(), "_installed_version", lambda cli: "2.1.200 (Claude Code)")
    with pytest.raises(AssertionError, match="below the pinned floor"):
        test_cli_meets_pinned_floor()


def test_guard_passes_on_cli_at_floor(monkeypatch):
    monkeypatch.setattr(_self(), "_resolve_cli", lambda: "/usr/bin/claude")
    monkeypatch.setattr(_self(), "_installed_version", lambda cli: MIN_CLI_VERSION)
    test_cli_meets_pinned_floor()


def test_guard_skips_when_no_cli_resolves(monkeypatch):
    """Codex-only deploys have no `claude` binary — that is not a failure."""
    monkeypatch.setattr(_self(), "_resolve_cli", lambda: None)
    with pytest.raises(pytest.skip.Exception):
        test_cli_meets_pinned_floor()


def test_guard_skips_when_version_cannot_be_queried(monkeypatch):
    monkeypatch.setattr(_self(), "_resolve_cli", lambda: "/usr/bin/claude")
    monkeypatch.setattr(_self(), "_installed_version", lambda cli: None)
    with pytest.raises(pytest.skip.Exception):
        test_cli_meets_pinned_floor()


def test_pinned_cli_path_wins_over_path(monkeypatch):
    """Resolution mirrors production: CLAUDE_CLI_PATH beats whatever is on PATH."""
    monkeypatch.setattr(
        "autoswe.core.config.load_config", lambda: {"CLAUDE_CLI_PATH": "/opt/pinned/claude"}
    )
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/claude")
    assert _resolve_cli() == "/opt/pinned/claude"


def test_falls_back_to_path_when_unpinned(monkeypatch):
    monkeypatch.setattr("autoswe.core.config.load_config", lambda: {"CLAUDE_CLI_PATH": ""})
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/claude")
    assert _resolve_cli() == "/usr/bin/claude"


def test_resolution_survives_unloadable_config(monkeypatch):
    """A broken/absent autoswe.env must not turn the guard into an error."""
    def boom():
        raise RuntimeError("no config")

    monkeypatch.setattr("autoswe.core.config.load_config", boom)
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/claude")
    assert _resolve_cli() == "/usr/bin/claude"
