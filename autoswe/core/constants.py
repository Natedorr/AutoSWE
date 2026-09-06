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
