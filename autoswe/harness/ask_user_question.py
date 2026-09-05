"""Intercept AskUserQuestion tool calls and post them as issue comments.

Both the planner and coder import this module. It owns the shared formatting
and the can_use_tool callback that pauses the SDK on AskUserQuestion.
"""
from __future__ import annotations

import re
import shlex
from collections.abc import Callable
from typing import Any

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
        if "=" in t or (t.startswith("--") and "=" in t):
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


def _is_valid_question_input(input_data: dict) -> bool:
    """Return True if input_data has at least one question with text and options."""
    return any(
        q.get("question", "").strip() and q.get("options")
        for q in input_data.get("questions", [])
    )


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


def freeze_progress_on_post(progress_callback, body: str) -> None:
    """Freeze the sticky progress comment on *body* (issue #184).

    Called from the AskUserQuestion callback after the standalone question
    comment is posted: no later tool event may clobber the posted question,
    so the sticky must end on it. Works for a bare progress updater (plain
    call, falls back to coalesced update) and for a ProgressComment object,
    which knows about freeze().
    """
    if progress_callback is None:
        return
    freeze = getattr(progress_callback, "freeze", None)
    if callable(freeze):
        freeze(body)
    else:
        progress_callback(body)


def post_question_fallback(task: dict, repo_cfg: dict, question_md: str, progress_callback=None) -> None:
    """Post a question the AskUserQuestion callback failed to post (issue #184).

    The callback records ``state["asked_question_posted"] = False`` when its
    standalone post fails. Handlers call this so the user still sees the
    question: the body is pushed through the sticky progress comment (drain()
    flushes it) and a standalone comment is posted as the durable copy.
    All failures are non-fatal — the session pauses either way.
    """
    body = question_md + BOT_MARKER
    if progress_callback is not None:
        try:
            progress_callback(body)
        except Exception:
            pass
    try:
        rc = dict(repo_cfg)
        rc.setdefault("owner", task.get("owner", ""))
        rc.setdefault("repo", task.get("repo", ""))
        rc.setdefault("pat", task.get("_token", ""))
        get_tracker(rc).post_comment(task["issue_number"], body)
    except Exception:
        pass


# Type hint for the callback signature expected by the SDK
CanUseToolCallback = Callable[[str, Any, Any], Any]


def make_can_use_tool(
    task: dict,
    repo_cfg: dict,
    state: dict,
    *,
    on_post: Callable[[str], None] | None = None,
    read_only: bool = False,
) -> CanUseToolCallback:
    """Build the async ``can_use_tool`` callback for the Claude Agent SDK.

    When Claude calls ``AskUserQuestion``, this callback formats the questions
    as markdown, posts them as a **standalone issue comment** (never into the
    throttled sticky progress comment — issue #184), and returns
    PermissionResultDeny to immediately pause the agent. The denial message
    informs Claude that its session is paused and will resume when the user
    replies. The handler then checks ``state["asked_question_md"]`` to detect
    and return WAITING; ``state["asked_question_posted"]`` records whether
    the standalone post landed so the handler can fall back to posting it.
    All other tools are allowed through.

    Args:
        task: The dispatch task dict (mutated to record session_id, last_phase).
        repo_cfg: Repository configuration for provider factory.
        state: Mutable dict shared with handler; gets ``asked_question_md``
            and ``asked_question_posted`` keys.
        on_post: Optional progress notification hook, called with the full
            question body after the standalone post is attempted. Used to
            freeze the sticky progress comment on the question (see
            freeze_progress_on_post). It does NOT post the question — the
            standalone post above is the only comment path.
        read_only: When True, blocks Write and Edit tools and Bash
            git write subcommands plus common file-mutation commands (sed -i,
            shell redirects, tee, python -c with open/write, curl -o, wget, etc.).
            TodoWrite and the sub-agent task family (TaskCreate, etc.) are
            allowed — they are progress/orchestration tools that do not mutate
            the repo. Used by plan phase as a safeguard against the CLI exiting
            plan mode via the native ExitPlanMode command or bash-based bypasses.
    """
    # Deferred import: SDK may not be installed; only needed when ask_user_question
    # safeguards are active (plan-phase can_use_tool callback).
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

        if not _is_valid_question_input(input_data):
            return PermissionResultDeny(
                message="AskUserQuestion input had no real questions — provide at least one question with options.",
            )

        md = format_ask_user_question(input_data)
        state["asked_question_md"] = md

        full_body = md + BOT_MARKER

        # Idempotent post guard (issue #194): this callback can fire more than
        # once for a single question round — the agent may re-issue
        # AskUserQuestion after the deny, or runner.run's retry re-invokes the
        # backend with the same shared state dict. Re-posting yields a
        # byte-identical duplicate comment (the E2E double-post, ~1 min apart).
        # A previous firing that already landed the post set
        # asked_question_posted=True, which also makes the finalize fallback a
        # true no-op; here we re-pause without posting again.
        if state.get("asked_question_posted") is True:
            if on_post is not None:
                try:
                    freeze_progress_on_post(on_post, full_body)
                except Exception:  # Progress notification is best-effort.
                    pass
            return PermissionResultDeny(
                message=(
                    "Questions were already posted to the issue as a comment. "
                    "Your session is paused — it will resume when the user replies."
                ),
            )

        # Post the question as a STANDALONE issue comment — never into the
        # throttled, latest-wins sticky progress comment (issue #184: the
        # question was coalesced away and clobbered by the next tool event
        # before drain() flushed it, so the user saw no question at all).
        posted = False
        try:
            rc = dict(repo_cfg)
            rc.setdefault("owner", task.get("owner", ""))
            rc.setdefault("repo", task.get("repo", ""))
            rc.setdefault("pat", task.get("_token", ""))
            tracker = get_tracker(rc)
            tracker.post_comment(task["issue_number"], full_body)
            posted = True
        except Exception:  # Post failure is non-fatal; session still pauses via PermissionResultDeny.
            posted = False
        state["asked_question_posted"] = posted

        # Notify the progress system so the sticky comment freezes on the
        # question (never clobbered by a later tool event, issue #184).
        if on_post is not None:
            try:
                freeze_progress_on_post(on_post, full_body)
            except Exception:  # Progress notification is best-effort.
                pass

        return PermissionResultDeny(
            message=(
                "Questions posted to the issue as a comment. "
                "Your session is paused — it will resume when the user replies."
            ),
        )

    return can_use_tool
