"""Intercept AskUserQuestion tool calls and post them as issue comments.

Both the planner and coder import this module. It owns the shared formatting
and the can_use_tool callback that pauses the SDK on AskUserQuestion.
"""
from __future__ import annotations

import re
import shlex
from typing import Any, Callable

from autoswe.harness.prompts import BOT_MARKER
from autoswe.providers.factory import get_tracker

# Kept for backwards-compat in existing tests / callers. Prefer _is_git_write.
_GIT_COMMIT_PUSH_RE = re.compile(r"\bgit\s+(?:commit|push|force[-\s]?push)", re.IGNORECASE)

# Git subcommands that mutate the index, working tree, refs, or remote.
# Anything not in this set (log, diff, status, show, rev-parse, ls-files, etc.)
# is treated as read-only and allowed during the plan phase.
_GIT_WRITE_SUBCOMMANDS = frozenset({
    "add", "am", "apply", "branch", "checkout", "cherry-pick", "clean",
    "commit", "filter-branch", "gc", "init", "merge", "mv", "pull", "push",
    "rebase", "reflog", "remote", "repack", "reset", "restore", "revert",
    "rm", "stash", "submodule", "switch", "tag", "update-index",
    "update-ref", "worktree", "force-push",
})

# Top-level git flags that consume the *next* token as their value, e.g.
# `git -c core.autocrlf=input commit` or `git -C /path push`.  Without
# accounting for these, the subcommand parser would think `commit` is the
# value of `-c` instead of the subcommand.
_GIT_FLAGS_WITH_VALUE = frozenset({"-c", "-C", "--exec-path", "--git-dir",
                                   "--work-tree", "--namespace", "--super-prefix"})

# Regex patterns that detect common bash file-mutation commands.
# Used during the plan phase (read_only=True) to block the agent from
# bypassing the plan→fix workflow via Bash (e.g. sed -i, echo >>, curl -o).
_FILE_MUTATING_PATTERNS = [
    r"\bsed\s+-[^\s]*i\b",                                                 # sed -i, sed -i.bak, sed -i ''
    r"(?<!\>)>(?!>)(?!&)(?!\s*/dev/null\b)(?!\s*/dev/std)",               # > file (not >>, not >&, not > /dev/null)
    r">\>(?!\s*/dev/null\b)(?!\s*/dev/std)",                               # >> file (not >> /dev/null)
    r"\btee\s+",                                                           # tee file
    r"(?:^|\s)python\d*\b.*-c.*\bopen\s*\(",                              # python/3 -c "...open(..."
    r"(?:^|\s)python\d*\b.*-c.*\.write\s*\(",                              # python/3 -c "...write(..."
    r"\bperl\b.*-i\b",                                                     # perl -i
    r"\becho\b.*>>",                                                       # echo >> file
    r"\bcurl\b.*\s-o\b",                                                   # curl -o file
    r"\bcurl\b.*\s-O\b",                                                   # curl -O (remote name)
    r"\bwget\b",                                                           # wget
]


def _is_file_mutation(cmd: str) -> bool:
    """Return True if *cmd* appears to mutate files on disk.

    Covers common bypass patterns (sed -i, shell redirects, tee, python
    one-liners with open/write, curl -o, wget, etc.).  Designed to be
    conservative — it may miss exotic patterns, but should not block
    legitimate read-only commands (cat, grep, ls, git log, etc.).
    """
    return any(re.search(pat, cmd) for pat in _FILE_MUTATING_PATTERNS)


def _git_subcommand(cmd: str) -> str | None:
    """Return the git subcommand for a bash command, or None.

    Skips leading flags between ``git`` and the subcommand so things like
    ``git -c core.autocrlf=input commit -am foo`` resolve to ``commit``
    rather than being misread because the regex stopped at ``-c``.
    """
    try:
        tokens = shlex.split(cmd, posix=True)
    except ValueError:
        return None
    if not tokens:
        return None
    # Allow leading env-var assignments (``FOO=bar git commit``)
    i = 0
    while i < len(tokens) and "=" in tokens[i] and not tokens[i].startswith("-"):
        i += 1
    if i >= len(tokens) or tokens[i] != "git":
        return None
    i += 1
    while i < len(tokens):
        t = tokens[i]
        if not t.startswith("-"):
            return t.lower()
        # `-c key=val` / `--exec-path=foo` flags
        if "=" in t or t.startswith("--") and "=" in t:
            i += 1
            continue
        if t in _GIT_FLAGS_WITH_VALUE:
            i += 2  # flag + its value
            continue
        i += 1  # standalone flag like --no-pager
    return None


def _is_git_write(cmd: str) -> bool:
    """Return True if *cmd* invokes a git subcommand that mutates state."""
    sub = _git_subcommand(cmd)
    return sub is not None and sub in _GIT_WRITE_SUBCOMMANDS


def _is_git_commit_push(cmd: str) -> bool:
    """Backwards-compat helper. Returns True for git commit/push specifically."""
    sub = _git_subcommand(cmd)
    return sub in {"commit", "push", "force-push"}


def format_ask_user_question(input_data: dict) -> str:
    """Render the SDK AskUserQuestion input as markdown for an issue comment.

    The SDK passes ``input_data`` with a ``questions`` key containing a list
    of question dicts with ``header``, ``question``, ``options``, and
    ``multiSelect`` fields.
    """
    questions = input_data.get("questions", [])
    if not questions:
        return "## Questions\n\n(no questions)"

    lines = ["## Questions"]

    for q in questions:
        header = q.get("header", "")
        question = q.get("question", "")
        options = q.get("options", [])
        multi_select = q.get("multiSelect", False)

        if header:
            lines.append(f"\n### {header}")
        lines.append("")
        lines.append(question)

        if multi_select:
            lines.append("(select any that apply)")

        for opt in options:
            label = opt.get("label", "")
            description = opt.get("description", "")
            if description:
                lines.append(f"- **{label}** — {description}")
            else:
                lines.append(f"- **{label}**")

        lines.append("")

    lines.append("_Reply in this thread with your answer (free text or option labels)._")

    return "\n".join(lines)


# Type hint for the callback signature expected by the SDK
CanUseToolCallback = Callable[[str, Any, Any], Any]


def make_can_use_tool(
    task: dict,
    repo_cfg: dict,
    state: dict,
    *,
    on_post: Callable[[str], None] = None,
    read_only: bool = False,
) -> CanUseToolCallback:
    """Build the async ``can_use_tool`` callback for the Claude Agent SDK.

    When Claude calls ``AskUserQuestion``, this callback formats the questions
    as markdown, posts them as an issue comment, and returns PermissionResultAllow
    with pre-filled answers so the agent completes its turn naturally.
    The handler then checks ``state["asked_question_md"]`` to detect and return WAITING.
    All other tools are allowed through.

    Args:
        task: The dispatch task dict (mutated to record session_id, last_phase).
        repo_cfg: Repository configuration for provider factory.
        state: Mutable dict shared with handler; gets ``asked_question_md`` key.
        on_post: Optional callback(str) for sticky-progress posting.
            If None, falls back to ``get_tracker(repo_cfg).post_comment()``.
        read_only: When True, blocks Write and Edit tools and Bash
            git write subcommands plus common file-mutation commands (sed -i,
            shell redirects, tee, python -c with open/write, curl -o, wget, etc.).
            TodoWrite and the sub-agent task family (TaskCreate, etc.) are
            allowed — they are progress/orchestration tools that do not mutate
            the repo. Used by plan phase as a safeguard against the CLI exiting
            plan mode via the native ExitPlanMode command or bash-based bypasses.
    """
    from claude_agent_sdk import PermissionResultAllow, PermissionResultDeny

    async def can_use_tool(tool_name: str, input_data: Any, context: Any) -> Any:
        if read_only:
            if tool_name in ("Write", "Edit"):
                return PermissionResultDeny(
                    message="This tool is not available during the planning phase."
                )
            if tool_name == "Bash":
                cmd = input_data.get("command", "")
                if _is_git_write(cmd):
                    return PermissionResultDeny(
                        message="Git write operations are not available during the planning phase."
                    )
                if _is_file_mutation(cmd):
                    return PermissionResultDeny(
                        message="File modifications are not available during the planning phase."
                    )

        if tool_name != "AskUserQuestion":
            return PermissionResultAllow(updated_input=input_data)

        md = format_ask_user_question(input_data)
        state["asked_question_md"] = md

        full_body = md + BOT_MARKER

        try:
            if on_post is not None:
                on_post(full_body)
            else:
                rc = dict(repo_cfg)
                rc.setdefault("owner", task.get("owner", ""))
                rc.setdefault("repo", task.get("repo", ""))
                rc.setdefault("pat", task.get("_token", ""))
                tracker = get_tracker(rc)
                tracker.post_comment(rc, task["issue_number"], full_body)
        except Exception:
            pass

        questions = input_data.get("questions", [])
        answers = {
            q["question"]: "Question posted to issue. User will reply by commenting."
            for q in questions
        }
        return PermissionResultAllow(
            updated_input={
                "questions": questions,
                "answers": answers,
            }
        )

    return can_use_tool
