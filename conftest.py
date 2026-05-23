"""Repo-root conftest.

Sets AUTOSWE_DIR to a writable temp dir BEFORE any test module imports
autoswe.* — most autoswe modules call init_debug_logger(LOGS_DIR) at import
time and would otherwise touch ~/.autoswe on the user's
machine (~/.autoswe by default). This module is loaded by pytest before test collection, so
the env var is in place when test files do `from autoswe import ...`.
"""
import os
import shutil
import tempfile
from pathlib import Path

_AUTOSWE_DIR = Path(tempfile.mkdtemp(prefix="autoswe-test-"))
os.environ["AUTOSWE_DIR"] = str(_AUTOSWE_DIR)
(_AUTOSWE_DIR / "data").mkdir(parents=True, exist_ok=True)
(_AUTOSWE_DIR / "logs").mkdir(parents=True, exist_ok=True)
(_AUTOSWE_DIR / "running").mkdir(parents=True, exist_ok=True)
(_AUTOSWE_DIR / "config").mkdir(parents=True, exist_ok=True)

# Copy prompt templates from project config into temp AUTOSWE_DIR
# so that load_fix_prompt() / load_plan_prompt() / load_review_prompt()
# find the same templates the production code uses.
_project_dir = Path(__file__).parent
_prompt_src = _project_dir / "config" / "prompts"
if _prompt_src.exists():
    _prompt_dst = _AUTOSWE_DIR / "config" / "prompts"
    _prompt_dst.mkdir(parents=True, exist_ok=True)
    for f in _prompt_src.iterdir():
        shutil.copy2(f, _prompt_dst / f.name)
