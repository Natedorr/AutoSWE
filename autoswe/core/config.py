import json
import os
from pathlib import Path

# Resolve repo root relative to this module (autoswe/core/config.py → repo root)
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
AUTOSWE_DIR = Path(os.environ.get("AUTOSWE_DIR", _REPO_ROOT))
CONFIG_FILE = AUTOSWE_DIR / "config" / "autoswe.env"
REPOS_CONFIG_FILE = AUTOSWE_DIR / "config" / "repos.json"
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
        "SILENT_REPORTING": os.environ.get("SILENT_REPORTING", "false").lower() == "true",
        "MINIMAL_POSTING": os.environ.get("MINIMAL_POSTING", "false").lower() == "true",
        "AUTO_ASSIGN": os.environ.get("AUTO_ASSIGN", "true").lower() == "true",
        "ASSIGN_USER": os.environ.get("ASSIGN_USER", ""),
        "AUTO_CREATE_PR": os.environ.get("AUTO_CREATE_PR", "false").lower() == "true",
        "CLAUDE_CLI_PATH": os.environ.get("CLAUDE_CLI_PATH", ""),
        "PLAN_MODEL": os.environ.get("PLAN_MODEL", ""),
        "FIX_MODEL": os.environ.get("FIX_MODEL", ""),
        "REVIEW_MODEL": os.environ.get("REVIEW_MODEL", ""),
        "ANTHROPIC_AUTH_TOKEN": os.environ.get("ANTHROPIC_AUTH_TOKEN", ""),
        "ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY", ""),
        "ANTHROPIC_BASE_URL": os.environ.get("ANTHROPIC_BASE_URL", ""),
        "BOT_NAME": os.environ.get("BOT_NAME", "autoswe"),
        "ALLOWED_AUTHORS": os.environ.get("ALLOWED_AUTHORS", ""),
        "LINK_BRANCH_TO_ISSUE": os.environ.get("LINK_BRANCH_TO_ISSUE", "true").lower() == "true",
        "SYNC_STRATEGY": os.environ.get("SYNC_STRATEGY", "merge"),  # "merge" | "rebase"
    }
    if CONFIG_FILE.exists():
        for line in CONFIG_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                cfg[k.strip()] = v.strip()
        for int_key in ("AGENT_TIMEOUT", "AGENT_RETRY_ON_FAILURE", "MAX_ATTEMPTS", "MAX_TOTAL_HOURS", "MAX_CONCURRENT", "MAX_DRAIN_CYCLES"):
            try:
                cfg[int_key] = int(cfg.get(int_key, 0))
            except (ValueError, TypeError):
                pass
        cfg["SILENT_REPORTING"] = str(cfg.get("SILENT_REPORTING", "false")).lower() == "true"
        cfg["MINIMAL_POSTING"] = str(cfg.get("MINIMAL_POSTING", "false")).lower() == "true"
        cfg["AUTO_ASSIGN"] = str(cfg.get("AUTO_ASSIGN", "true")).lower() == "true"
        cfg["AUTO_CREATE_PR"] = str(cfg.get("AUTO_CREATE_PR", "false")).lower() == "true"
        cfg["LINK_BRANCH_TO_ISSUE"] = str(cfg.get("LINK_BRANCH_TO_ISSUE", "true")).lower() == "true"
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
    if REPOS_CONFIG_FILE.exists():
        try:
            raw = json.loads(REPOS_CONFIG_FILE.read_text())
        except json.JSONDecodeError:
            return {}
    else:
        raw = {}

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
