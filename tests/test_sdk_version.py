"""Guard: the installed claude-agent-sdk must not fall below the pinned floor.

``requirements.txt`` declares ``claude-agent-sdk>=0.2.137``. This test makes a
regressed/old install fail with an actionable message instead of surfacing later as
an opaque SDK error deep in a dispatch. It is offline (no network, no fake) and
skips — rather than fails — when the SDK is not installed, so Codex-only or no-SDK
deploy environments don't break the suite.

Only the stdlib is used (no third-party ``packaging`` dependency): the version
floor is a plain dotted integer triple, so tuple comparison is sufficient and
keeps the module collectable in minimal environments.

Bumping the floor is a one-line change: update ``MIN_SDK_VERSION`` here and the
pin in ``requirements.txt`` to match.
"""

import importlib.metadata
import re

import pytest

# Keep in lockstep with the pin in requirements.txt.
MIN_SDK_VERSION = "0.2.137"
_DISTRIBUTION_NAME = "claude-agent-sdk"


def _vtuple(version: str) -> tuple[int, ...]:
    """Parse a PEP 440-ish version into a comparable integer tuple.

    ``"0.2.137"`` → ``(0, 2, 137)``.  Non-numeric segments are ignored so a
    suffix such as ``"0.2.137rc1"`` still parses cleanly; comparison remains
    correct for the numeric prefix, which is all the floor check needs.
    """
    return tuple(int(part) for part in re.findall(r"\d+", version))


def _installed_version() -> str | None:
    """Return the installed claude-agent-sdk version, or None if not installed."""
    try:
        return importlib.metadata.version(_DISTRIBUTION_NAME)
    except importlib.metadata.PackageNotFoundError:
        pass
    # Fallback: the module exposes __version__ in older installs where the
    # distribution metadata name differs.
    try:
        import claude_agent_sdk

        return getattr(claude_agent_sdk, "__version__", None)
    except Exception:
        return None


def test_sdk_meets_pinned_floor():
    """Installed claude-agent-sdk must be >= MIN_SDK_VERSION."""
    installed = _installed_version()
    if installed is None:
        pytest.skip(
            f"{_DISTRIBUTION_NAME} is not installed in this environment — "
            "version floor not applicable (e.g. Codex-only deploy)."
        )
    assert _vtuple(installed) >= _vtuple(MIN_SDK_VERSION), (
        f"{_DISTRIBUTION_NAME}=={installed} is below the pinned floor "
        f"{MIN_SDK_VERSION} (see requirements.txt). "
        f"Run: pip install -U '{_DISTRIBUTION_NAME}>={MIN_SDK_VERSION}'"
    )
