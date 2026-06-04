import os
import re
from pathlib import Path

from autoswe.core.config import AUTOSWE_DIR, FIX_PROMPT_FILE, LOGS_DIR, PLAN_PROMPT_FILE, REVIEW_PROMPT_FILE
from autoswe.core.logging_utils import init_debug_logger
from autoswe.providers.base import NormalizedComment

dbg = init_debug_logger(LOGS_DIR)

CONFLICT_RESOLUTION_PROMPT_FILE = AUTOSWE_DIR / "config" / "prompts" / "conflict_resolution.txt"

BOT_MARKER = "\n<!-- autoswe-bot -->"


# Mapping of repos.json keys to the bundled prompt file constants
_PROMPT_KEY_MAP = {
    "plan_prompt": PLAN_PROMPT_FILE,
    "fix_prompt": FIX_PROMPT_FILE,
    "review_prompt": REVIEW_PROMPT_FILE,
    "conflict_resolution_prompt": CONFLICT_RESOLUTION_PROMPT_FILE,
}


def _resolve_prompt_path(repo_cfg: dict | None, key: str) -> Path:
    """Return the prompt file path for a given repos.json override key.

    Resolution order:
    1. If *repo_cfg* contains *key* (e.g. ``"plan_prompt"``), interpret the
       value as a file path.  Relative paths are resolved against ``AUTOSWE_DIR``.
    2. Otherwise return the bundled default from ``_PROMPT_KEY_MAP``.
    """
    if repo_cfg and key in repo_cfg:
        override = repo_cfg[key]
        p = Path(override)
        if not p.is_absolute():
            p = AUTOSWE_DIR / p
        return p
    return _PROMPT_KEY_MAP[key]


def _sanitize_paths(text: str, repo_root: str) -> str:
    """Replace absolute repo paths with relative paths in prompt text."""
    if not text or not repo_root:
        return text
    root = repo_root.replace(os.sep, "/")
    text_normalized = text.replace(os.sep, "/")

    def _replace(m: re.Match) -> str:
        rel = m.group("rel") or ""
        if rel:
            return rel.lstrip("/")
        return "."

    pattern = re.compile(
        re.escape(root) + r"(?![\w\-])((?:/(?P<rel>[\w/_.\-+]*)))?",
    )
    return pattern.sub(_replace, text_normalized)


def _format_comments(comments: list[NormalizedComment]) -> str:
    """Format comments for display in prompts (works with NormalizedComment)."""
    if not comments:
        return "(no comments yet)"
    lines = []
    for c in comments:
        author = c.author_login or "unknown"
        created = c.created_at[:10] if c.created_at else ""
        body = (c.body or "").strip()
        lines.append(f"[{created}] @{author}:\n{body}")
    return "\n\n---\n\n".join(lines)


def load_plan_prompt(repo_cfg: dict | None = None) -> str:
    prompt_file = _resolve_prompt_path(repo_cfg, "plan_prompt")
    if prompt_file.exists():
        return prompt_file.read_text()
    # Fall back to bundled default if override path was specified but missing
    bundled = _PROMPT_KEY_MAP["plan_prompt"]
    if prompt_file != bundled and bundled.exists():
        return bundled.read_text()
    return (
        "You are planning a fix for GitHub issue {{OWNER}}/{{REPO}}#{{ISSUE_NUMBER}}: {{TITLE}}\n\n"
        "Issue body:\n{{BODY}}\n\nComments so far:\n{{COMMENTS}}\n\n"
        "{{GUIDANCE_BLOCK}}\n{{REVIEW_BLOCK}}\n"
        "Repo is checked out at the current working directory on branch {{BASE_BRANCH}}.\n"
        "Read the relevant code to understand the issue.\n\n"
        "When you have a plan, call the `mcp__autoswe_comment__post_plan` tool with the plan as markdown.\n"
        "When you need clarification before proceeding, call the `AskUserQuestion` tool with\n"
        "structured questions. autoSWE will post them as a comment, end your turn,\n"
        "and resume this session when the user replies.\n\n"
        "Fallback (only if MCP tools are unavailable):\n\n"
        "<AUTOSWE_QUESTIONS>\n1. First question?\n</AUTOSWE_QUESTIONS>\n\nOR:\n\n"
        "<AUTOSWE_PLAN>\nStep-by-step plan.\n</AUTOSWE_PLAN>\n\n"
        "Read the code for implementation facts; ask the user for intent, scope, and"
        " approach decisions the code cannot answer."
    )


def load_fix_prompt(repo_cfg: dict | None = None) -> str:
    prompt_file = _resolve_prompt_path(repo_cfg, "fix_prompt")
    if prompt_file.exists():
        return prompt_file.read_text()
    bundled = _PROMPT_KEY_MAP["fix_prompt"]
    if prompt_file != bundled and bundled.exists():
        return bundled.read_text()
    return (
        "Fix GitHub issue {{OWNER}}/{{REPO}}#{{ISSUE_NUMBER}}: {{TITLE}}\n\n"
        "Issue body:\n{{BODY}}\n\nDiscussion and plan:\n{{COMMENTS}}\n\n"
        "{{GUIDANCE_BLOCK}}\n\n{{PLAN}}\n\n{{REVIEW_BLOCK}}\n"
        "The repo is checked out at the current working directory on branch autoswe/issue-{{ISSUE_NUMBER}}.\n"
        "Read the relevant code, make the necessary changes to fix the issue, and verify your changes are correct.\n"
        "The `AskUserQuestion` tool is available mid-fix if you need clarification.\n"
        "Do NOT open a pull request — that will be handled separately.\n"
        "Summarize what you changed at the end of your response."
    )


def build_plan_prompt(
    task: dict, repo_root: str | None = None, comments: list[NormalizedComment] | None = None,
    repo_cfg: dict | None = None, guidance: str | None = None,
) -> str:
    """Build the plan prompt from template + task data."""
    # Deferred import: avoids circular dependency (prompts <- factory <-> providers).
    from autoswe.providers.factory import get_tracker

    owner, repo = task["owner"], task["repo"]
    issue_num = task["issue_number"]
    base_branch = task.get("plan_branch") or task.get("base_branch", "main")
    template = load_plan_prompt(repo_cfg=repo_cfg)

    if comments is None:
        rcfg = repo_cfg or {"owner": owner, "repo": repo, "token": task.get("_token", "")}
        tracker = get_tracker(rcfg)
        comments = tracker.fetch_comments(rcfg, issue_num)

    guidance_block = f"Guidance from the issue author:\n{guidance}\n" if guidance else ""

    # Pop review file — inject review findings into the plan prompt, then clear
    review_text = _pop_review_file(task)
    review_block = f"Latest code review findings (address in your plan):\n{review_text}\n" if review_text else ""

    body = _sanitize_paths(task.get("body", "") or "(no description)", repo_root)
    comments_text = _sanitize_paths(_format_comments(comments), repo_root)
    replacements = {
        "{{OWNER}}": owner,
        "{{REPO}}": repo,
        "{{ISSUE_NUMBER}}": str(issue_num),
        "{{TITLE}}": task.get("title", f"Issue #{issue_num}"),
        "{{BODY}}": body,
        "{{COMMENTS}}": comments_text,
        "{{GUIDANCE_BLOCK}}": guidance_block,
        "{{BASE_BRANCH}}": base_branch,
        "{{REVIEW_BLOCK}}": review_block,
    }
    prompt = template
    for k, v in replacements.items():
        prompt = prompt.replace(k, v)
    return prompt


def _find_plan_in_comments(comments: list[NormalizedComment] | None) -> str:
    """Find the plan text from comments.

    Supports both formats:
    1. MCP-posted plan: comment body starting with "## Plan"
    2. Legacy tag format: <AUTOSWE_PLAN>...</AUTOSWE_PLAN>
    """
    # Deferred import: avoids circular dependency (prompts <- tracking.comments).
    from autoswe.tracking.comments import _PLAN_RE

    for comment in reversed(comments or []):
        body = comment.body or ""

        # MCP-posted plan: starts with "## Plan"
        stripped = body.strip()
        if stripped.startswith("## Plan"):
            # Extract everything after "## Plan\n\n"
            after_header = stripped[len("## Plan"):].lstrip("\n")
            # Strip trailing "_Reply with `/fix`..." line if present
            reply_idx = after_header.find("_Reply with")
            if reply_idx > 0:
                after_header = after_header[:reply_idx].rstrip()
            return after_header

        # Legacy tag format
        m = _PLAN_RE.search(body)
        if m:
            return m.group(1).strip()

    return ""


def build_fix_prompt(
    task: dict, guidance: str | None = None, repo_root: str | None = None,
    comments: list[NormalizedComment] | None = None, repo_cfg: dict | None = None,
    plan_text: str | None = None,
) -> str:
    """Build the fix prompt from template + task data."""
    # Deferred import: avoids circular dependency (prompts <- factory <-> providers).
    from autoswe.providers.factory import get_tracker

    owner, repo = task["owner"], task["repo"]
    issue_num = task["issue_number"]
    guidance_block = f"Guidance: {guidance}" if guidance else ""

    if comments is None:
        rcfg = repo_cfg or {"owner": owner, "repo": repo, "token": task.get("_token", "")}
        tracker = get_tracker(rcfg)
        comments = tracker.fetch_comments(rcfg, issue_num)

    if not plan_text:
        plan_text = _find_plan_in_comments(comments)
    plan_block = f"Plan to implement:\n{plan_text}" if plan_text else ""

    # Pop review file — inject review findings into the fix prompt, then clear
    review_text = _pop_review_file(task)
    review_block = f"Latest code review findings (address before continuing):\n{review_text}\n" if review_text else ""

    template = load_fix_prompt(repo_cfg=repo_cfg)
    body = _sanitize_paths(task.get("body", "") or "(no description)", repo_root)
    comments_text = _sanitize_paths(_format_comments(comments), repo_root)
    replacements = {
        "{{OWNER}}": owner,
        "{{REPO}}": repo,
        "{{ISSUE_NUMBER}}": str(issue_num),
        "{{TITLE}}": task.get("title", f"Issue #{issue_num}"),
        "{{BODY}}": body,
        "{{COMMENTS}}": comments_text,
        "{{GUIDANCE_BLOCK}}": guidance_block,
        "{{PLAN}}": plan_block,
        "{{REVIEW_BLOCK}}": review_block,
    }
    prompt = template
    for k, v in replacements.items():
        prompt = prompt.replace(k, v)
    return prompt


def load_conflict_resolution_prompt(repo_cfg: dict | None = None) -> str:
    prompt_file = _resolve_prompt_path(repo_cfg, "conflict_resolution_prompt")
    if prompt_file.exists():
        return prompt_file.read_text()
    bundled = _PROMPT_KEY_MAP["conflict_resolution_prompt"]
    if prompt_file != bundled and bundled.exists():
        return bundled.read_text()
    return (
        "Resolve merge conflicts for GitHub issue {{OWNER}}/{{REPO}}#{{ISSUE_NUMBER}}: {{TITLE}}\n\n"
        "Issue body:\n{{BODY}}\n\n"
        "{{PLAN}}\n\n"
        "Merging `origin/{{BASE_BRANCH}}` into this branch produced conflicts in these files:\n\n"
        "{{CONFLICT_FILES}}\n\n"
        "Read each conflicted file, reconcile both sides while preserving the fix intent of this branch,\n"
        "and remove all `<<<<<<<` / `=======` / `>>>>>>>` markers.\n\n"
        "When all conflicts are resolved, run:\n\n"
        "    git add -A && git commit --no-edit\n\n"
        "to complete the merge. Do not start new work. Do not push (the handler pushes).\n"
        "Summarize which files you resolved and how."
    )


def build_conflict_resolution_prompt(
    task: dict,
    conflict_files: list[str],
    *,
    plan_text: str | None = None,
    base_branch: str = "main",
    repo_cfg: dict | None = None,
) -> str:
    """Build the conflict-resolution prompt from template + task data."""
    owner, repo = task["owner"], task["repo"]
    issue_num = task["issue_number"]
    template = load_conflict_resolution_prompt(repo_cfg=repo_cfg)

    plan_block = ""
    if plan_text:
        plan_block = (
            "This is the active plan for this branch. "
            "The merge must preserve its intent.\n\n"
            f"{plan_text}\n"
        )

    conflict_files_text = "\n".join(f"- {f}" for f in conflict_files)

    replacements = {
        "{{OWNER}}": owner,
        "{{REPO}}": repo,
        "{{ISSUE_NUMBER}}": str(issue_num),
        "{{TITLE}}": task.get("title", f"Issue #{issue_num}"),
        "{{BODY}}": task.get("body", "") or "(no description)",
        "{{PLAN}}": plan_block,
        "{{CONFLICT_FILES}}": conflict_files_text,
        "{{BASE_BRANCH}}": base_branch,
    }
    prompt = template
    for k, v in replacements.items():
        prompt = prompt.replace(k, v)
    return prompt


def load_review_prompt(repo_cfg: dict | None = None) -> str:
    prompt_file = _resolve_prompt_path(repo_cfg, "review_prompt")
    if prompt_file.exists():
        return prompt_file.read_text()
    bundled = _PROMPT_KEY_MAP["review_prompt"]
    if prompt_file != bundled and bundled.exists():
        return bundled.read_text()
    return (
        "Review code for GitHub issue {{OWNER}}/{{REPO}}#{{ISSUE_NUMBER}}: {{TITLE}}\n\n"
        "Issue body:\n{{BODY}}\n\nPlan:\n{{PLAN}}\n\n"
        "Diff summary:\n{{DIFF_STAT}}\n\nFull diff:\n{{DIFF}}\n\n"
        "{{GUIDANCE_BLOCK}}\n"
        "Produce a structured review report with these sections:\n"
        "- Summary (1-3 sentences)\n- Correctness (bugs, edge cases)\n"
        "- Security (auth, injection, secrets)\n- Tests (coverage)\n"
        "- Style & consistency\n- Suggestions\n- Verdict: LGTM / Needs changes / Blocked\n"
    )


def _pop_review_file(task: dict) -> str:
    """Read and clear task['review_file_path']. Returns review text or empty string."""
    review_path = task.get("review_file_path")
    if review_path:
        p = Path(review_path)
        if p.exists():
            review_text = p.read_text()
            task["review_file_path"] = None  # POP after first use
            return review_text
    return ""


def build_review_prompt(
    task: dict,
    repo_root: str | None = None,
    comments: list[NormalizedComment] | None = None,
    repo_cfg: dict | None = None,
    plan_text: str | None = None,
    diff_stat: str | None = None,
    diff_text: str | None = None,
    guidance: str | None = None,
) -> str:
    """Build the review prompt from template + task data."""
    owner, repo = task["owner"], task["repo"]
    issue_num = task["issue_number"]
    base_branch = task.get("base_branch", "main")
    template = load_review_prompt(repo_cfg=repo_cfg)

    guidance_block = f"Reviewer guidance: {guidance}\n" if guidance else ""
    body = _sanitize_paths(task.get("body", "") or "(no description)", repo_root)
    plan = plan_text or "(no plan posted)"

    replacements = {
        "{{OWNER}}": owner,
        "{{REPO}}": repo,
        "{{ISSUE_NUMBER}}": str(issue_num),
        "{{TITLE}}": task.get("title", f"Issue #{issue_num}"),
        "{{BODY}}": body,
        "{{PLAN}}": plan,
        "{{DIFF_STAT}}": diff_stat or "(empty)",
        "{{DIFF}}": diff_text or "(empty)",
        "{{GUIDANCE_BLOCK}}": guidance_block,
        "{{BASE_BRANCH}}": base_branch,
    }
    prompt = template
    for k, v in replacements.items():
        prompt = prompt.replace(k, v)
    return prompt
