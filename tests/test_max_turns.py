"""Tests for configurable per-harness/per-repo max_turns (issue #222).

Covers:
  * ``resolve_max_turns`` precedence (harness profile > per-repo > global > default),
    with the review phase keeping its separate lower default (80 vs 200).
  * ``load_harnesses_config`` validation of the optional per-profile ``max_turns``.
  * ``load_config`` env defaults for ``MAX_TURNS`` / ``REVIEW_MAX_TURNS``.
"""

import json

from autoswe.core import config

# ---------------------------------------------------------------------------
# resolve_max_turns precedence
# ---------------------------------------------------------------------------


def test_resolve_max_turns_defaults_when_unset():
    """No profile / per-repo / global override → 200 for fix, 80 for review."""
    assert config.resolve_max_turns("fix", {}, {}, None) == 200
    assert config.resolve_max_turns("review", {}, {}, None) == 80


def test_resolve_max_turns_global_env_override():
    """cfg MAX_TURNS / REVIEW_MAX_TURNS override the defaults per phase."""
    cfg = {"MAX_TURNS": 120, "REVIEW_MAX_TURNS": 40}
    assert config.resolve_max_turns("fix", {}, cfg, None) == 120
    assert config.resolve_max_turns("review", {}, cfg, None) == 40
    # An absent key still falls back to the phase default.
    assert config.resolve_max_turns("plan", {}, {"MAX_TURNS": 120}, None) == 120


def test_resolve_max_turns_per_repo_beats_global():
    """repo_cfg agent_max_turns wins over the global env value."""
    cfg = {"MAX_TURNS": 120}
    assert config.resolve_max_turns("fix", {"agent_max_turns": 300}, cfg, None) == 300


def test_resolve_max_turns_profile_beats_per_repo():
    """A harness profile's max_turns wins over everything below it."""
    harness = {"backend": "claude_code", "model": "m", "max_turns": 500}
    assert config.resolve_max_turns("fix", {"agent_max_turns": 300}, {"MAX_TURNS": 120}, harness) == 500


def test_resolve_max_turns_profile_applies_to_review():
    """A review profile's max_turns overrides the review default (80)."""
    harness = {"backend": "claude_code", "model": "m", "max_turns": 150}
    assert config.resolve_max_turns("review", {}, {}, harness) == 150
    # No profile → the separate lower review default still applies.
    assert config.resolve_max_turns("review", {}, {}, {"backend": "claude_code"}) == 80


def test_resolve_max_turns_string_value_coerced():
    """Profile / per-repo values are string-tolerant (JSON may carry "150")."""
    assert config.resolve_max_turns("fix", {}, {}, {"backend": "claude_code", "max_turns": "150"}) == 150
    assert config.resolve_max_turns("fix", {"agent_max_turns": "75"}, {}, None) == 75


def test_resolve_max_turns_bad_value_falls_back_to_default():
    """A non-numeric override is ignored → phase default, never a crash."""
    assert config.resolve_max_turns("fix", {"agent_max_turns": "many"}, {}, None) == 200
    assert config.resolve_max_turns("review", {"agent_max_turns": None}, {}, None) == 80


def test_resolve_max_turns_zero_or_negative_falls_back():
    """A cap of 0 / negative is not "no cap" — it degrades to the default."""
    assert config.resolve_max_turns("fix", {"agent_max_turns": 0}, {}, None) == 200
    assert config.resolve_max_turns("fix", {}, {}, {"backend": "claude_code", "max_turns": -5}) == 200


# ---------------------------------------------------------------------------
# load_harnesses_config validation of per-profile max_turns
# ---------------------------------------------------------------------------


def _write_harnesses(isolated_autoswe_dir, profiles: dict):
    (isolated_autoswe_dir / "config" / "harnesses.json").write_text(
        json.dumps(profiles), encoding="utf-8"
    )
    config._harnesses_cache.clear()


def test_harness_profile_max_turns_accepted(isolated_autoswe_dir):
    _write_harnesses(isolated_autoswe_dir, {"p": {"backend": "claude_code", "model": "m", "max_turns": 300}})
    profiles = config.load_harnesses_config()
    assert profiles["p"]["max_turns"] == 300
    # Round-trips into resolution for its phase.
    assert config.resolve_max_turns("fix", {}, {}, profiles["p"]) == 300


def test_harness_profile_max_turns_string_coerced_on_load(isolated_autoswe_dir):
    _write_harnesses(isolated_autoswe_dir, {"p": {"backend": "claude_code", "model": "m", "max_turns": "250"}})
    profiles = config.load_harnesses_config()
    assert profiles["p"]["max_turns"] == 250
    assert isinstance(profiles["p"]["max_turns"], int)


def test_harness_profile_max_turns_non_integer_rejected(isolated_autoswe_dir):
    _write_harnesses(isolated_autoswe_dir, {"p": {"backend": "claude_code", "model": "m", "max_turns": "lots"}})
    import pytest
    with pytest.raises(ValueError, match="max_turns"):
        config.load_harnesses_config()


def test_harness_profile_max_turns_zero_rejected(isolated_autoswe_dir):
    _write_harnesses(isolated_autoswe_dir, {"p": {"backend": "claude_code", "model": "m", "max_turns": 0}})
    import pytest
    with pytest.raises(ValueError, match="max_turns"):
        config.load_harnesses_config()


def test_harness_profile_without_max_turns_still_valid(isolated_autoswe_dir):
    """Omitting max_turns is the default — the profile still loads and resolves to 200."""
    _write_harnesses(isolated_autoswe_dir, {"p": {"backend": "claude_code", "model": "m"}})
    profiles = config.load_harnesses_config()
    assert "max_turns" not in profiles["p"]
    assert config.resolve_max_turns("fix", {}, {}, profiles["p"]) == 200


# ---------------------------------------------------------------------------
# load_config env defaults
# ---------------------------------------------------------------------------


def test_load_config_max_turns_defaults(isolated_autoswe_dir):
    cfg = config.load_config()
    assert cfg["MAX_TURNS"] == 200
    assert cfg["REVIEW_MAX_TURNS"] == 80


def test_load_config_max_turns_env_override(isolated_autoswe_dir, monkeypatch):
    monkeypatch.setenv("MAX_TURNS", "555")
    monkeypatch.setenv("REVIEW_MAX_TURNS", "44")
    cfg = config.load_config()
    assert cfg["MAX_TURNS"] == 555
    assert cfg["REVIEW_MAX_TURNS"] == 44
    assert isinstance(cfg["MAX_TURNS"], int)


def test_load_config_max_turns_bad_int_falls_back(isolated_autoswe_dir):
    env = isolated_autoswe_dir / "config" / "autoswe.env"
    env.write_text("MAX_TURNS=thre\n", encoding="utf-8")
    cfg = config.load_config()
    # Malformed → the default, not a string that would break the runner.
    assert cfg["MAX_TURNS"] == 200
    assert isinstance(cfg["MAX_TURNS"], int)
