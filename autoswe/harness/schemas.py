"""JSON Schemas for the plan/review structured-output payloads (issue #159).

The Claude Agent SDK validates an agent's final output against a JSON Schema
when ``output_format`` is set on ``ClaudeAgentOptions``.  The validated data is
delivered on ``ResultMessage.structured_output``.  These schemas are the
machine-readable twin of the fields the planner/reviewer handlers used to scrape
out of free text:

- ``PLAN_SCHEMA``    — mirrors the planner's PLAN_READY / WAITING distinction
                       (the plan body + whether it is final).
- ``REVIEW_SCHEMA``  — mirrors the reviewer's report body (the markdown the
                       handler writes to ``~/.claude/reviews/<slug>.md``).

The Agent SDK validates with JSON Schema **draft-07** and re-prompts on
validation mismatch, so the schemas are intentionally minimal: only the fields a
handler actually reads are required, and everything else is optional so a run
that legitimately lacks the data can still succeed.  The ``format`` keyword is
deliberately avoided (it is an annotation the SDK does not enforce, and older
CLIs rejected any schema containing it).
"""
from __future__ import annotations

from typing import Any

# Fields the planner handler reads (see autoswe/harness/planner.py):
#   plan_markdown      -> the plan body posted under "## Plan"
#   is_plan_ready      -> PLAN_READY vs WAITING: questions
#   question_markdown  -> the clarifying questions (only meaningful when
#                         is_plan_ready is False)
PLAN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "is_plan_ready": {
            "type": "boolean",
            "description": "True when the plan is final and ready to code; false when the planner still needs to ask questions.",
        },
        "plan_markdown": {
            "type": "string",
            "description": "The full implementation plan in markdown. Required when is_plan_ready is true.",
        },
        "question_markdown": {
            "type": "string",
            "description": "Clarifying questions in markdown. Required when is_plan_ready is false; empty or omitted otherwise.",
        },
    },
    "required": ["is_plan_ready"],
    "additionalProperties": False,
}

# Fields the reviewer handler reads (see autoswe/harness/reviewer.py):
#   report_markdown    -> the review report body written to the review file
#   verdict            -> optional short verdict (e.g. "LGTM", "changes")
REVIEW_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "report_markdown": {
            "type": "string",
            "description": "The full review report in markdown (findings, summary, verdict).",
        },
        "verdict": {
            "type": "string",
            "description": "A short one-word-or-phrase verdict, e.g. 'LGTM' or 'changes requested'.",
        },
    },
    "required": ["report_markdown"],
    "additionalProperties": False,
}


def output_format_for(schema: dict[str, Any]) -> dict[str, Any]:
    """Build the ``output_format`` option value for the Agent SDK.

    The SDK expects ``{"type": "json_schema", "schema": <JSON Schema>}`` (Python
    SDK; ``outputFormat`` in the TypeScript SDK).  Returns a fresh dict so
    callers can hand it to ``ClaudeAgentOptions`` without sharing the module
    constant.
    """
    return {"type": "json_schema", "schema": schema}
