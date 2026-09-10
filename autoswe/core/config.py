from __future__ import annotations

import json
import os
from pathlib import Path

from autoswe.core.logging_utils import get_debug_logger

# Expands ${VAR} and ${VAR:-default} inside JSON string values.


def _expand_env(value: str) -> str:
    """Expand ``${VAR}`` and ``${VAR:-default}`` inside a string.

    Supports nested references (e.g. ``${OUTER:-${INNER}}``) via recursive
    expansion of the inner content.
    """
    result: list[str] = []
    i = 0
    while i < len(value):
        if value[i] == "$" and i + 1 < len(value) and value[i + 1] == "{":
            # Find matching closing brace by tracking depth
            depth = 1
            j = i + 2
            while j < len(value) and depth > 0:
                if value[j] == "{":
                    depth += 1
                elif value[j] == "}":
                    depth -= 1
                j += 1
            inner = value[i + 2: j - 1]
            # Recursively expand inner content first (handles ${VAR:-${INNER}})
            expanded_inner = _expand_env(inner)
            if ":-" in expanded_inner:
                var, default = expanded_inner.split(":-", 1)
                result.append(os.environ.get(var, default))
            else:
                result.append(os.environ.get(expanded_inner, ""))
            i = j
        else:
            result.append(value[i])
            i += 1
    return "".join(result)


def _expand_env_dict(obj: dict) -> dict:
    """Recursively expand ``${VAR}`` env references in dict string values.

    List values are recursed into: string elements are expanded, non-string
    elements (booleans, numbers, nested dicts) are passed through unchanged.
    """
    result = {}
    for key, value in obj.items():
        if isinstance(value, str):
            result[key] = _expand_env(value)
        elif isinstance(value, dict):
            result[key] = _expand_env_dict(value)
        elif isinstance(value, list):
            result[key] = [_expand_env(item) if isinstance(item, str)
                           else _expand_env_dict(item) if isinstance(item, dict)
                           else item for item in value]
        else:
            result[key] = value
    return result


# Resolve repo root relative to this module (autoswe/core/config.py → repo root)
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
AUTOSWE_DIR = Path(os.environ.get("AUTOSWE_DIR", _REPO_ROOT))


# ---------------------------------------------------------------------------
# Helpers — shared coercion logic so bool/int parsing isn't repeated inline
# ---------------------------------------------------------------------------


def _as_bool(value: str | None, default: str = "false") -> bool:
    """Coerce a config value to bool.

    Accepts the common truthy spellings ``true`` / ``1`` / ``yes`` / ``on``
    (case-insensitive); everything else — including a blank that falls back to
    *default* — is falsy. Used by both the defaults dict and the file-override
    loop so the coercion logic lives in one place.
    """
    return str(value or default).strip().lower() in ("true", "1", "yes", "on")


def _load_json_config(filepath: Path) -> dict:
    """Read a JSON config file, returning ``{}`` on missing/corrupt file."""
    if filepath.exists():
        try:
            return json.loads(filepath.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


CONFIG_FILE = AUTOSWE_DIR / "config" / "autoswe.env"
REPOS_CONFIG_FILE = AUTOSWE_DIR / "config" / "repos.json"
HARNESSES_CONFIG_FILE = AUTOSWE_DIR / "config" / "harnesses.json"
WELCOME_FILE = AUTOSWE_DIR / "config" / "welcome_comment.txt"
QUEUE_FILE = AUTOSWE_DIR / "data" / "queue.json"
RUNNING_DIR = AUTOSWE_DIR / "running"
LOGS_DIR = AUTOSWE_DIR / "logs"
# Backend-neutral root for handler-owned artifacts (S6 / issue #169 F-10).
# The reviewer persists its report under ARTIFACT_DIR / "reviews"; native
# Claude-SDK plan files still live in the SDK's own ~/.claude/plans/ (owned by
# the backend, not the handler).
ARTIFACT_DIR = AUTOSWE_DIR / "artifacts"
PLAN_PROMPT_FILE = AUTOSWE_DIR / "config" / "prompts" / "plan.txt"
FIX_PROMPT_FILE = AUTOSWE_DIR / "config" / "prompts" / "fix.txt"
REVIEW_PROMPT_FILE = AUTOSWE_DIR / "config" / "prompts" / "review.txt"
INIT_PROMPT_FILE = AUTOSWE_DIR / "config" / "prompts" / "init.txt"


def load_config() -> dict:
    """Load autoswe.env with defaults."""
    cfg = {
        "AGENT_TIMEOUT": int(os.environ.get("AGENT_TIMEOUT", 7200)),
        "AGENT_RETRY_ON_FAILURE": int(os.environ.get("AGENT_RETRY_ON_FAILURE", 0)),
        "MAX_ATTEMPTS": int(os.environ.get("MAX_ATTEMPTS", 3)),
        "MAX_TOTAL_HOURS": int(os.environ.get("MAX_TOTAL_HOURS", 2)),
        "MAX_CONCURRENT": int(os.environ.get("MAX_CONCURRENT", 1)),
        "MAX_DRAIN_CYCLES": int(os.environ.get("MAX_DRAIN_CYCLES", 50)),
        "WORKTREE_DIR": os.environ.get("WORKTREE_DIR", "worktrees"),
        "SILENT_REPORTING": _as_bool(os.environ.get("SILENT_REPORTING")),
        "MINIMAL_POSTING": _as_bool(os.environ.get("MINIMAL_POSTING")),
        "AUTO_ASSIGN": _as_bool(os.environ.get("AUTO_ASSIGN"), "true"),
        "ASSIGN_USER": os.environ.get("ASSIGN_USER", ""),
        "AUTO_CREATE_PR": _as_bool(os.environ.get("AUTO_CREATE_PR")),
        "CLAUDE_CLI_PATH": os.environ.get("CLAUDE_CLI_PATH", ""),
        "PLAN_MODEL": os.environ.get("PLAN_MODEL", ""),
        "FIX_MODEL": os.environ.get("FIX_MODEL", ""),
        "REVIEW_MODEL": os.environ.get("REVIEW_MODEL", ""),
        "PLAN_HARNESS": os.environ.get("PLAN_HARNESS", ""),
        "FIX_HARNESS": os.environ.get("FIX_HARNESS", ""),
        "REVIEW_HARNESS": os.environ.get("REVIEW_HARNESS", ""),
        "ANTHROPIC_AUTH_TOKEN": os.environ.get("ANTHROPIC_AUTH_TOKEN", ""),
        "ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY", ""),
        "ANTHROPIC_BASE_URL": os.environ.get("ANTHROPIC_BASE_URL", ""),
        "BOT_NAME": os.environ.get("BOT_NAME", "autoswe"),
        "ALLOWED_AUTHORS": os.environ.get("ALLOWED_AUTHORS", ""),
        "LINK_BRANCH_TO_ISSUE": _as_bool(os.environ.get("LINK_BRANCH_TO_ISSUE"), "true"),
        "SYNC_STRATEGY": os.environ.get("SYNC_STRATEGY", "merge"),  # "merge" | "rebase"
        "PR_REQUIRE_SYNC": _as_bool(os.environ.get("PR_REQUIRE_SYNC"), "true"),
        "PR_REQUIRE_CI": _as_bool(os.environ.get("PR_REQUIRE_CI"), "true"),
        "PR_CI_ERROR_POLICY": os.environ.get("PR_CI_ERROR_POLICY", "block"),
        "AGENT_RETRY_ON_SUBTYPE": os.environ.get("AGENT_RETRY_ON_SUBTYPE", ""),
        "WORKTREE_ORPHAN_POLICY": os.environ.get("WORKTREE_ORPHAN_POLICY", "commit"),
        "AUTO_PURGE_BRANCHES": _as_bool(os.environ.get("AUTO_PURGE_BRANCHES")),
        "TEST_GATE": _as_bool(os.environ.get("TEST_GATE"), "true"),
        "TEST_GATE_TIMEOUT": int(os.environ.get("TEST_GATE_TIMEOUT", 600)),
        "TEST_COMMAND": os.environ.get("TEST_COMMAND", ""),
        "MAX_TURNS": int(os.environ.get("MAX_TURNS", 200)),
        "REVIEW_MAX_TURNS": int(os.environ.get("REVIEW_MAX_TURNS", 80)),
    }
    if CONFIG_FILE.exists():
        # Snapshot the defaults before the file-parse loop overwrites the
        # values — a coercion failure must fall back to these defaults.
        int_defaults = {
            int_key: cfg[int_key]
            for int_key in (
                "AGENT_TIMEOUT", "AGENT_RETRY_ON_FAILURE", "MAX_ATTEMPTS",
                "MAX_TOTAL_HOURS", "MAX_CONCURRENT", "MAX_DRAIN_CYCLES",
                "TEST_GATE_TIMEOUT", "MAX_TURNS", "REVIEW_MAX_TURNS",
            )
        }
        for line in CONFIG_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                v = v.strip()
                # Strip matched surrounding quotes so BOT_NAME="bot" -> bot.
                if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
                    v = v[1:-1]
                cfg[k.strip()] = v
        for int_key in ("AGENT_TIMEOUT", "AGENT_RETRY_ON_FAILURE", "MAX_ATTEMPTS", "MAX_TOTAL_HOURS", "MAX_CONCURRENT", "MAX_DRAIN_CYCLES", "TEST_GATE_TIMEOUT", "MAX_TURNS", "REVIEW_MAX_TURNS"):
            raw = cfg.get(int_key)
            if raw is None:
                continue
            try:
                cfg[int_key] = int(raw)
            except (ValueError, TypeError):
                # Malformed value (e.g. MAX_ATTEMPTS=thre): keep the default
                # rather than a string that would blow up later in a compare.
                default = int_defaults[int_key]
                cfg[int_key] = default
                get_debug_logger().warning(
                    "config: %s=%r is not a valid integer, using default %r",
                    int_key, raw, default,
                )
        cfg["SILENT_REPORTING"] = _as_bool(cfg.get("SILENT_REPORTING"))
        cfg["MINIMAL_POSTING"] = _as_bool(cfg.get("MINIMAL_POSTING"))
        cfg["AUTO_ASSIGN"] = _as_bool(cfg.get("AUTO_ASSIGN"), "true")
        cfg["AUTO_CREATE_PR"] = _as_bool(cfg.get("AUTO_CREATE_PR"))
        cfg["LINK_BRANCH_TO_ISSUE"] = _as_bool(cfg.get("LINK_BRANCH_TO_ISSUE"), "true")
        cfg["PR_REQUIRE_SYNC"] = _as_bool(cfg.get("PR_REQUIRE_SYNC"), "true")
        cfg["PR_REQUIRE_CI"] = _as_bool(cfg.get("PR_REQUIRE_CI"), "true")
        cfg["AUTO_PURGE_BRANCHES"] = _as_bool(cfg.get("AUTO_PURGE_BRANCHES"))
        cfg["TEST_GATE"] = _as_bool(cfg.get("TEST_GATE"), "true")
    # Parse ALLOWED_AUTHORS as a set for O(1) lookup
    _raw = str(cfg.get("ALLOWED_AUTHORS", "")).strip()
    cfg["ALLOWED_AUTHORS"] = {a.strip() for a in _raw.split(",") if a.strip()} if _raw else set()
    _normalise_ci_error_policy(cfg)
    return cfg


def _normalise_ci_error_policy(cfg: dict) -> None:
    """Normalise and validate ``PR_CI_ERROR_POLICY`` (``block`` | ``open``).

    Case-insensitive; an unknown value logs a warning and falls back to
    ``block`` — the fail-safe default, so a typo can't silently open the
    gate on unconsultable CI.
    """
    valid = {"block", "open"}
    raw = str(cfg.get("PR_CI_ERROR_POLICY", "block")).strip().lower()
    if raw not in valid:
        get_debug_logger().warning(
            "config: PR_CI_ERROR_POLICY=%r is not %s, using 'block'",
            cfg.get("PR_CI_ERROR_POLICY"), sorted(valid),
        )
        raw = "block"
    cfg["PR_CI_ERROR_POLICY"] = raw


def load_repos_config() -> dict:
    """Load per-repo settings from repos.json.

    Keys are ``owner/repo`` for GitHub, ``org/project/repo`` for Azure.

    Requires the ``provider`` field on each entry (``"github"`` or ``"azure"``).
    Rejects Azure DevOps entries that lack a ``pat`` field.
    Validates Azure entries have required fields.
    """
    raw = _load_json_config(REPOS_CONFIG_FILE)

    validated = {}
    for key, entry in raw.items():
        if key.startswith("_"):
            continue
        provider = entry.get("provider", "").lower()
        if not provider:
            raise ValueError(
                f"repos.json entry '{key}' is missing the required 'provider' field. "
                "Use 'github' or 'azure'."
            )
        entry = dict(entry)
        entry["provider"] = provider
        if not entry.get("pat"):
            raise ValueError(
                f"repos.json entry '{key}' is missing the required 'pat' field. "
                "Run 'python autoswe.py setup' to configure credentials."
            )
        if provider == "azure":
            parts = key.split("/")
            if len(parts) != 3:
                raise ValueError(
                    f"repos.json entry '{key}' has provider='azure' but key has "
                    f"{len(parts)} part(s). Azure entries need 'org/project/repo' format."
                )
            entry["org"] = parts[0]
            entry["project"] = parts[1]
            entry["repo"] = parts[2]
        validated[key] = entry
    return validated


# Recognized backend names (populated as new backends are added).
KNOWN_BACKENDS = {"claude_code", "codex", "pi"}

# Module-level cache for harnesses config — avoids re-reading harnesses.json
# on every handler invocation.  Clear with ``_harnesses_cache.clear()`` in tests.
_harnesses_cache: dict = {}


def load_harnesses_config() -> dict:
    """Load named harness profiles from ``harnesses.json`` (memoized).

    Mirrors ``load_repos_config()``: skip ``_``-prefixed keys, require a
    ``backend`` field per entry, validate the backend is known.

    The result is cached after the first call so that repeated handler
    invocations in a single poll don't re-read the file.  Call
    ``_harnesses_cache.clear()`` (or ``autoswe.core.config._harnesses_cache.clear()``)
    to force a reload during testing.
    """
    if _harnesses_cache:
        return dict(_harnesses_cache)

    raw = _load_json_config(HARNESSES_CONFIG_FILE)

    validated = {}
    for key, entry in raw.items():
        if key.startswith("_"):
            continue
        backend = entry.get("backend", "").lower()
        if not backend:
            raise ValueError(
                f"harnesses.json entry '{key}' is missing the required 'backend' field. "
                f"Use one of: {', '.join(sorted(KNOWN_BACKENDS))}."
            )
        if backend not in KNOWN_BACKENDS:
            raise ValueError(
                f"harnesses.json entry '{key}' has unknown backend '{backend}'. "
                f"Use one of: {', '.join(sorted(KNOWN_BACKENDS))}."
            )
        # Expand ${VAR} and ${VAR:-default} env references in string values
        profile = _expand_env_dict(dict(entry, backend=backend))
        # Optional per-profile turn cap (issue #222). Backends that honor
        # RunSpec.max_turns (claude_code) use it; codex/pi treat it as a
        # documented no-op. Fail fast on a non-positive value — a silent
        # "no cap" from a typo would defeat the anti-runaway guard.
        if "max_turns" in profile:
            try:
                profile["max_turns"] = int(str(profile["max_turns"]))
            except (TypeError, ValueError):
                raise ValueError(
                    f"harnesses.json entry '{key}' has a non-integer 'max_turns' "
                    f"({profile['max_turns']!r}); it must be a positive integer."
                ) from None
            if profile["max_turns"] < 1:
                raise ValueError(
                    f"harnesses.json entry '{key}' has max_turns={profile['max_turns']}, "
                    f"which must be >= 1."
                )
        validated[key] = profile

    _harnesses_cache.update(validated)
    return dict(validated)


def resolve_harness(phase: str, repo_cfg: dict, cfg: dict, harnesses: dict | None = None) -> dict:
    """Resolve the harness profile for a coding phase (plan, fix, review).

    Resolution order (highest → lowest priority):
    1. ``repo_cfg`` phase-specific harness: ``{phase}_harness`` (e.g. ``plan_harness``)
    2. ``cfg`` phase-specific harness: ``{PHASE}_HARNESS`` (e.g. ``PLAN_HARNESS``)
    3. Synthesized default: ``{"backend": "claude_code", "model": <phase_model>, ...}``

    The synthesized default preserves the legacy model resolution chain
    (``{phase}_model`` in repos.json → ``PHASE_MODEL`` in autoswe.env) so
    existing configurations work without any ``harnesses.json``.  It also
    carries the Anthropic credentials and ``cli_path`` needed by
    ``ClaudeCodeBackend``, so the dispatcher (``runner.run``) stays
    backend-agnostic.

    Returns a harness profile dict with at least ``backend`` and ``model`` keys.
    """
    if harnesses is None:
        harnesses = load_harnesses_config()

    cfg = cfg or {}
    repo_cfg = repo_cfg or {}

    # Determine the phase key (e.g. "plan" → "plan_harness" / "PLAN_HARNESS" / "plan_model" / "PLAN_MODEL")
    phase_key = phase.lower()

    # 1. Check repo_cfg for a harness profile reference
    profile_name = repo_cfg.get(f"{phase_key}_harness") or cfg.get(f"{phase_key.upper()}_HARNESS", "")

    if profile_name:
        profile = harnesses.get(profile_name)
        if profile is None:
            raise ValueError(
                f"Harness profile '{profile_name}' referenced for phase '{phase}' "
                f"was not found in harnesses.json."
            )
        return dict(profile)

    # 2. Synthesize from legacy model + credential resolution (backward compatibility).
    #    Include cli_path and Anthropic credentials so ClaudeCodeBackend has everything
    #    it needs and the dispatcher stays backend-agnostic.
    model = repo_cfg.get(f"{phase_key}_model") or cfg.get(f"{phase_key.upper()}_MODEL") or None
    return {
        "backend": "claude_code",
        "model": model,
        "cli_path": cfg.get("CLAUDE_CLI_PATH") or None,
        "anthropic_base_url": repo_cfg.get("anthropic_base_url") or cfg.get("ANTHROPIC_BASE_URL"),
        "anthropic_auth_token": repo_cfg.get("anthropic_auth_token") or cfg.get("ANTHROPIC_AUTH_TOKEN"),
        "anthropic_api_key": repo_cfg.get("anthropic_api_key") or cfg.get("ANTHROPIC_API_KEY"),
    }


# Per-phase default turn caps (issue #222). Review is deliberately lower — it is
# a read-only pass and needs far fewer round trips than a coding phase.
_DEFAULT_MAX_TURNS = 200
_DEFAULT_REVIEW_MAX_TURNS = 80


def resolve_max_turns(phase: str, repo_cfg: dict | None, cfg: dict | None, harness_cfg: dict | None = None) -> int:
    """Resolve the agent turn cap for a coding phase (issue #222).

    Resolution order (highest → lowest priority):

    1. ``harness_cfg["max_turns"]`` — the per-profile cap from
       ``harnesses.json`` (validated as a positive int on load).
    2. ``repo_cfg["agent_max_turns"]`` — a per-repo override.
    3. ``cfg`` global: ``REVIEW_MAX_TURNS`` for the review phase, ``MAX_TURNS``
       otherwise (defaults ``80`` / ``200``).

    Review keeps its separate lower default (80) unless a profile or per-repo
    override bumps it; the coding phases default to 200. Backends that do not
    honor ``RunSpec.max_turns`` (codex, pi) treat the value as a documented
    no-op — it is still resolved and passed for consistency.
    """
    cfg = cfg or {}
    repo_cfg = repo_cfg or {}
    harness_cfg = harness_cfg or {}

    candidate = harness_cfg.get("max_turns")
    if candidate is None:
        candidate = repo_cfg.get("agent_max_turns")
    if candidate is None:
        if (phase or "").lower() == "review":
            return int(cfg.get("REVIEW_MAX_TURNS", _DEFAULT_REVIEW_MAX_TURNS))
        return int(cfg.get("MAX_TURNS", _DEFAULT_MAX_TURNS))

    try:
        value = int(str(candidate))
    except (TypeError, ValueError):
        return (
            _DEFAULT_REVIEW_MAX_TURNS
            if (phase or "").lower() == "review"
            else _DEFAULT_MAX_TURNS
        )
    return value if value >= 1 else (
        _DEFAULT_REVIEW_MAX_TURNS
        if (phase or "").lower() == "review"
        else _DEFAULT_MAX_TURNS
    )
