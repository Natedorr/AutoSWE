"""Shared recoverable-gate policy (issue #245 plan §2.5).

``RECOVERABLE_GATE_STATUSES`` — ``test_failed`` (the local post-fix test
gate, ``harness/test_gate.py``) and ``ci_failed`` (the remote CI watch) are
two signals behind one policy: the same attempt counter
(``task.gate_attempt_count``), the same reset rule (cleared on a green
signal or any human-dispatched Claude action, never on a push the agent
itself made), the same config switch (``AUTO_FIX_ON_GATE_FAILURE``), and the
same prompt-assembly helper that turns a failure — local pytest output or a
CI failure list — into the fix prompt's failure section. Cheap local gate
first, remote gate second.
"""
from __future__ import annotations

from autoswe.core.config import resolve_flag


def gate_max_fix_attempts(cfg: dict, repo_cfg: dict) -> int:
    """Resolve GATE_MAX_FIX_ATTEMPTS: a per-repo override beats cfg (default 2)."""
    for source in (repo_cfg.get("gate_max_fix_attempts"), cfg.get("GATE_MAX_FIX_ATTEMPTS")):
        if source is None:
            continue
        try:
            return int(source)
        except (TypeError, ValueError):
            continue
    return 2


def auto_fix_on_gate_failure(cfg: dict, repo_cfg: dict) -> bool:
    """Resolve AUTO_FIX_ON_GATE_FAILURE: a per-repo override beats cfg (default on)."""
    return resolve_flag("AUTO_FIX_ON_GATE_FAILURE", cfg, repo_cfg, default=True)


def build_gate_guidance(
    header: str,
    *,
    failing: list[str] | None = None,
    summary: str = "",
    excerpt: str = "",
) -> str:
    """Turn one gate failure (CI or local test output) into fix-prompt guidance.

    *failing* names failing checks (CI); *excerpt* carries raw failure text
    (local pytest tail, or a CI annotation/log excerpt). Both are optional and
    independent so either signal can supply whichever it has.
    """
    lines = [header]
    if failing:
        lines.append("")
        lines.append("Failing checks:")
        lines.extend(f"- {name}" for name in failing)
    if summary:
        lines.append("")
        lines.append(summary)
    if excerpt:
        lines.append("")
        lines.append("```")
        lines.append(excerpt)
        lines.append("```")
    return "\n".join(lines)
