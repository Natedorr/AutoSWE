"""Framework-agnostic autoSWE constants shared across entry points.

This module is a dependency-free leaf: it must stay importable from any
entry point (poller, setup wizard, and the standalone ``mcp_servers``
subprocesses) without pulling in the provider SDKs or the agent harness.
"""

#: Pinned GitHub REST API version sent as the ``X-GitHub-Api-Version`` header on
#: every autoSWE GitHub call. Bump here (in one place) only when an endpoint
#: autoSWE uses starts *requiring* a newer version — see docs/autoswe/config.md
#: ("GitHub API version pin") for the re-check cadence.
GH_API_VERSION = "2022-11-28"

#: Subprocess text-mode decoding kwargs (issue #238). ``text=True`` without an
#: explicit ``encoding`` decodes child output with the platform locale — CP1252
#: on Windows — and a single UTF-8 byte undefined in CP1252 (e.g. the em dash's
#: 0x9D) kills subprocess's internal reader thread: stdout stays None and the
#: next .strip() raises TypeError, hiding the real traceback. Pin UTF-8 +
#: replace so any byte sequence yields a str instead of a dead thread. Git and
#: gh emit UTF-8, so this is the right codec on every platform.
GIT_TEXT_ARGS: dict[str, str] = {"encoding": "utf-8", "errors": "replace"}
