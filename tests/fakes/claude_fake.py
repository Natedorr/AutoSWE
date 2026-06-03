"""Scripted multi-turn Claude SDK fake.

Replaces ``autoswe.harness.runner.run`` with a scripted response list.
Each call pops the next (text, session_id, subtype, recipe) tuple. Validates
``resume=`` matches the expected session ID when set.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from autoswe.harness.runner import RunResult


class ClaudeFake:
    """Scripted Claude SDK runner fake.

    Attributes (mutable, for assertions):
        calls     - list[dict]  every runner.run invocation with kwargs
    """

    def __init__(self):
        self.script: list[tuple[str, str, str, Any, bool, bool]] = []
        self.calls: list[dict[str, Any]] = []
        self._call_index = 0
        self._raises: list[Exception] = []

    def script_response(self, text: str, session_id: str = "s1",
                        subtype: str = "success", plan_posted: bool = False,
                        question_posted: bool = False) -> None:
        """Add a response to the script.  Order matters — each .run() call pops the next."""
        self.script.append((text, session_id, subtype, None, plan_posted, question_posted))

    def script_recipe(self, text: str, recipe: object,
                      session_id: str = "s1", subtype: str = "success") -> None:
        """Like script_response, but also applies *recipe* in cwd before returning."""
        self.script.append((text, session_id, subtype, recipe, False, False))

    def script_plan(self, plan_text: str, session_id: str = "s1") -> None:
        """Add a plan-phase response wrapping *plan_text* in AUTOSWE_PLAN tags."""
        self.script_response(
            f"<AUTOSWE_PLAN>{plan_text}</AUTOSWE_PLAN>",
            session_id=session_id,
        )

    def script_questions(self, questions: str, session_id: str = "s1") -> None:
        """Add a plan-phase response wrapping *questions* in AUTOSWE_QUESTIONS tags."""
        self.script_response(
            f"<AUTOSWE_QUESTIONS>{questions}</AUTOSWE_QUESTIONS>",
            session_id=session_id,
        )

    def script_fix(self, summary: str = "Changes applied.",
                   session_id: str = "s1", commit_sha: str = "abc1234") -> None:
        """Add a fix-phase response that produces DONE_SUMMARY when processed by coder."""
        self.script_response(
            summary, session_id=session_id, subtype="success"
        )

    def script_fail(self, exc: Exception) -> None:
        """Schedule an exception to be raised on the next .run() call."""
        self._raises.append(exc)

    def run(self, prompt: str, *, cwd: str, cfg: dict, repo_cfg: dict | None = None,
            resume: str | None = None,
            # Phase 3: generic intent
            mode: str | None = None,
            extra_tools: list | None = None,
            disallowed_tools_override: list | None = None,
            # Legacy fields (backward compat)
            permission_mode: str = "default",
            allowed_tools: list | None = None,
            max_turns: int = 200,
            model: str | None = None, mcp_servers: dict | None = None,
            progress_callback=None, disallowed_tools: list | None = None,
            **kwargs) -> RunResult:
        """Replacement for autoswe.harness.runner.run."""
        self.calls.append({
            "cwd": cwd,
            "resume": resume,
            "mode": mode,
            "extra_tools": extra_tools,
            "disallowed_tools_override": disallowed_tools_override,
            "permission_mode": permission_mode,
            "model": model,
            "allowed_tools": allowed_tools,
            "prompt_prefix": (prompt or "")[:80],
        })

        if self._raises and self._call_index < len(self.script) + len(self._raises):
            # Check if next scheduled item is a raise
            raise self._raises.pop(0)

        if self._call_index >= len(self.script):
            # No more scripted responses — return empty success
            return RunResult("", "s-default", "success")

        text, session_id, subtype, recipe, plan_posted, question_posted = self.script[self._call_index]
        self._call_index += 1

        # Apply recipe if present
        if recipe is not None:
            from tests.fakes.claude_recipes import apply_recipe
            apply_recipe(Path(cwd), recipe)

        return RunResult(text, session_id, subtype, plan_posted=plan_posted, question_posted=question_posted)

    _real_run = None  # Class-level cache of the real runner.run

    @classmethod
    def _get_real_run(cls):
        """Return the real runner.run, cached on first call.

        The cache is populated by patch() before it replaces module attributes,
        so it always contains the genuine function.
        """
        if cls._real_run is None:
            import autoswe.harness.runner as runner_mod
            cls._real_run = runner_mod.run
        return cls._real_run

    def patch(self):
        """Patch into autoswe.harness.runner and all import sites.

        Returns (module, original) for unpatching.
        """
        import sys

        import autoswe.harness.runner as runner_mod

        # Cache original BEFORE replacing module attribute
        self.__class__._get_real_run()
        self._saved_original = runner_mod.run
        runner_mod.run = self.run

        # Patch import sites
        for mod_name in ("autoswe.harness.planner", "autoswe.harness.coder"):
            if mod_name in sys.modules:
                mod = sys.modules[mod_name]
                if hasattr(mod, "runner") and hasattr(mod.runner, "run"):
                    mod.runner.run = self.run

        return runner_mod, self._saved_original

    def unpatch(self, module, original) -> None:
        """Restore run, always using the cached real function."""
        module.run = self._get_real_run()
