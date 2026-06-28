"""Tests for autoswe.harness.backends.factory — dispatch on backend field."""
import pytest

from autoswe.harness.backends.base import CodingBackend
from autoswe.harness.backends.claude_code import ClaudeCodeBackend
from autoswe.harness.backends.factory import get_backend


def test_get_backend_defaults_to_claude_code():
    """When backend field is missing, factory defaults to Claude Code."""
    backend = get_backend({"model": "claude-sonnet-4-6"})
    assert isinstance(backend, ClaudeCodeBackend)
    assert isinstance(backend, CodingBackend)


def test_get_backend_claude_code_by_name():
    """Explicit backend: claude_code returns ClaudeCodeBackend."""
    backend = get_backend({"backend": "claude_code", "model": "claude-opus-4-8"})
    assert isinstance(backend, ClaudeCodeBackend)


def test_get_backend_claude_code_case_insensitive():
    """backend field is case-insensitive."""
    for val in ("claude_code", "CLAUDE_CODE", "Claude_Code"):
        backend = get_backend({"backend": val})
        assert isinstance(backend, ClaudeCodeBackend)


def test_unknown_backend_raises_value_error():
    """get_backend raises ValueError for unknown backends."""
    with pytest.raises(ValueError, match="Unknown coding backend"):
        get_backend({"backend": "unknown_backend"})


def test_get_backend_passes_with_extra_fields():
    """Extra fields in harness_cfg are tolerated (backend just needs 'backend')."""
    backend = get_backend({
        "backend": "claude_code",
        "model": "claude-sonnet-4-6",
        "timeout": 3600,
        "api_key_env": "ANTHROPIC_API_KEY",
    })
    assert isinstance(backend, ClaudeCodeBackend)


def test_claude_code_capabilities():
    """ClaudeCodeBackend advertises the full capability set."""
    caps = ClaudeCodeBackend.capabilities()
    assert "mcp" in caps
    assert "can_use_tool" in caps
    assert "plan_permission" in caps
    assert "resume" in caps
    assert "progress_stream" in caps
