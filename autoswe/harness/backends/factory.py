"""Factory — dispatch harness_cfg to the correct CodingBackend implementation.

Mirrors the provider factory pattern (``providers/factory.py``):
dispatch on the ``backend`` field in the harness profile dict.
"""
from __future__ import annotations

from autoswe.harness.backends.base import CodingBackend
from autoswe.harness.backends.claude_code import ClaudeCodeBackend

# -- Public API --


def get_backend(harness_cfg: dict) -> CodingBackend:
    """Return a CodingBackend for the given harness profile configuration.

    The ``backend`` field in *harness_cfg* selects the implementation::

        {"backend": "claude_code", "model": "claude-sonnet-4-6"}
        {"backend": "codex", "model": "gpt-5.4"}

    Raises ``ValueError`` on unknown backend names.
    """
    backend_name = harness_cfg.get("backend", "claude_code").lower()
    if backend_name == "claude_code":
        return ClaudeCodeBackend()
    if backend_name == "codex":
        # Deferred import: only loads the codex submodule when a codex profile is configured,
        # avoiding ImportError on deploys that use claude_code exclusively.
        from autoswe.harness.backends.codex import CodexBackend

        return CodexBackend()

    raise ValueError(
        f"Unknown coding backend: '{backend_name}'. "
        "Supported backends: claude_code, codex"
    )
