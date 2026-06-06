from __future__ import annotations

import contextlib
import json
import os
from pathlib import Path

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
    """Coerce a config value to bool via the ``.lower() == "true"`` idiom.

    Used by both the defaults dict and the file-override loop so the coercion
    logic lives in one place.
    """
    return str(value or default).lower() == "true"


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
PLAN_PROMPT_FILE = AUTOSWE_DIR / "config" / "prompts" / "plan.txt"
FIX_PROMPT_FILE = AUTOSWE_DIR / "config" / "prompts" / "fix.txt"
REVIEW_PROMPT_FILE = AUTOSWE_DIR / "config" / "prompts" / "review.txt"


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
        "LINK_BRANCH_TO_ISSUE": _as_bool(os.environ.get("LINK_BRANCH_TO_ISSUE"), "false"),
        "SYNC_STRATEGY": os.environ.get("SYNC_STRATEGY", "merge"),  # "merge" | "rebase"
    }
    if CONFIG_FILE.exists():
        for line in CONFIG_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                cfg[k.strip()] = v.strip()
        for int_key in ("AGENT_TIMEOUT", "AGENT_RETRY_ON_FAILURE", "MAX_ATTEMPTS", "MAX_TOTAL_HOURS", "MAX_CONCURRENT", "MAX_DRAIN_CYCLES"):
            with contextlib.suppress(ValueError, TypeError):
                cfg[int_key] = int(cfg.get(int_key, 0))
        cfg["SILENT_REPORTING"] = _as_bool(cfg.get("SILENT_REPORTING"))
        cfg["MINIMAL_POSTING"] = _as_bool(cfg.get("MINIMAL_POSTING"))
        cfg["AUTO_ASSIGN"] = _as_bool(cfg.get("AUTO_ASSIGN"), "true")
        cfg["AUTO_CREATE_PR"] = _as_bool(cfg.get("AUTO_CREATE_PR"))
        cfg["LINK_BRANCH_TO_ISSUE"] = _as_bool(cfg.get("LINK_BRANCH_TO_ISSUE"), "false")
    # Parse ALLOWED_AUTHORS as a set for O(1) lookup
    _raw = str(cfg.get("ALLOWED_AUTHORS", "")).strip()
    cfg["ALLOWED_AUTHORS"] = {a.strip() for a in _raw.split(",") if a.strip()} if _raw else set()
    return cfg


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
KNOWN_BACKENDS = {"claude_code", "codex"}

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
