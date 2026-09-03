import asyncio
import re
import subprocess
from pathlib import Path

from autoswe.core.config import resolve_harness
from autoswe.core.logging_utils import get_debug_logger, log
from autoswe.harness import runner
from autoswe.harness.ask_user_question import make_can_use_tool, post_question_fallback
from autoswe.harness.mcp_config import build_mcp_comment_server, build_mcp_inline_comment_server
from autoswe.harness.prompts import build_conflict_resolution_prompt, build_fix_prompt
from autoswe.harness.runner import HandlerResult
from autoswe.harness.test_gate import run_test_gate
from autoswe.providers.factory import get_vcs
from autoswe.vcs.worktree import (
    commit_and_push,
    create_worktree,
    fast_forward_worktree,
    get_merge_conflict_files,
    worktree_path,
)

dbg = get_debug_logger()


_MCP_COMMENT_TOOL_PREFIX = "mcp__autoswe_comment__"
_MCP_COMMENT_TOOLS = [
    f"{_MCP_COMMENT_TOOL_PREFIX}update_progress",
    f"{_MCP_COMMENT_TOOL_PREFIX}post_plan",
    f"{_MCP_COMMENT_TOOL_PREFIX}post_question",
]

_MCP_INLINE_COMMENT_TOOLS = [
    "mcp__autoswe_inline_comment__post_inline_comment",
]

# Tolerant extractor for the fix agent's structured commit message.
# The agent ends its response with a fenced <AUTOSWE_COMMIT> block carrying a
# one-line `subject:` and a multi-line `body:` — see config/prompts/fix.txt.
_COMMIT_RE = re.compile(r"<AUTOSWE_COMMIT>\s*(.*?)</AUTOSWE_COMMIT>", re.DOTALL)


# git's soft limit for a single-line commit subject; longer lines wrap poorly
# in `git log`/GitHub. We only truncate when the agent exceeds it.
_MAX_SUBJECT_LEN = 72


def _clean_commit_subject(subject: str) -> str:
    """Reduce an agent/fallback subject to a single, git-friendly line.

    Collapses internal newlines (an LLM sometimes wraps the subject) to spaces
    and truncates to git's ~72-char soft limit. The commit trailer already
    carries the ``Fixes #N`` attribution, so a trimmed subject stays readable.
    """
    one_line = " ".join(subject.split())
    if len(one_line) > _MAX_SUBJECT_LEN:
        one_line = one_line[: _MAX_SUBJECT_LEN - 1].rstrip() + "…"
    return one_line


def _strip_commit_block(text: str) -> str:
    """Remove the <AUTOSWE_COMMIT> block from an agent response.

    Used for the human-facing fix summary: the block is internal scaffolding
    that should not be posted to the issue or PR body. Removes every block and
    collapses the whitespace gap it leaves so the remaining prose reads cleanly.
    """
    if not text:
        return ""
    stripped = _COMMIT_RE.sub("\n", text)
    # Collapse the 3+ newlines the removal can leave (block sat on its own lines).
    stripped = re.sub(r"\n{3,}", "\n\n", stripped)
    return stripped.strip()


# Matches a key line with optional leading indentation and an optional inline
# value: ``subject: ...`` / ``body: ...`` (case-insensitive). Detecting and
# slicing the value off the *same* representation avoids the indented-key bug
# where a raw-line slice grabbed the wrong characters.
_COMMIT_KEY_RE = re.compile(r"^\s*(subject|body)\s*:\s*(.*)$", re.IGNORECASE)


def _parse_commit_message(text: str) -> tuple[str | None, str | None]:
    """Parse the <AUTOSWE_COMMIT> block from an agent response.

    Returns ``(subject, body)`` with both stripped. ``subject`` is the inline
    value of the first ``subject:`` line (single-line by contract); ``body`` is
    everything from the ``body:`` line to the closing tag. Leading indentation
    on the keys is tolerated. When the block is missing or has no usable
    subject, the corresponding value is ``None`` so the caller can fall back.
    """
    m = _COMMIT_RE.search(text or "")
    if not m:
        return None, None
    block = m.group(1)

    # A subject that itself contains the literal text "body:" must not be
    # mistaken for the body key — so only a line that *starts* with the
    # ``body`` key (case-insensitive, any leading indent) opens the body.
    subject = None
    body_lines: list[str] = []
    in_body = False
    for line in block.split("\n"):
        key_m = _COMMIT_KEY_RE.match(line)
        if in_body:
            # Drop the block's leading indentation so an indented block still
            # yields a clean, non-indented commit body.
            body_lines.append(line.lstrip())
        elif key_m and key_m.group(1).lower() == "body":
            rest = key_m.group(2).strip()
            if rest:
                body_lines.append(rest)
            in_body = True
        elif key_m and key_m.group(1).lower() == "subject" and subject is None:
            subject = key_m.group(2).strip() or None

    body = "\n".join(body_lines).strip() or None
    return subject, body


def _get_branch_head_sha(wt, branch: str) -> str | None:
    """Get the latest commit SHA on a branch."""
    try:
        result = subprocess.run(
            ["git", "-C", str(wt), "rev-parse", branch],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception as e:  # Best-effort branch SHA lookup; returns None on failure.
        dbg.debug("_get_branch_head_sha failed: %s", e)

    return None


def _run_fix_session(
    task: dict,
    prompt: str,
    wt: Path,
    cfg: dict,
    rc: dict,
    *,
    resume_id: str | None,
    extra_tools: list[str],
    mcp_servers: dict,
    fix_model: str | None,
    timeout_msg: str,
    error_prefix: str,
    progress_callback=None,
    fork_session: bool = False,
) -> HandlerResult:
    """Shared execution tail for run_fix and resume_fix.

    Resolves the harness, runs the agent, checks post-run state, and
    finalises (commit/push) on success.

    *extra_tools* holds only the genuinely-extra tools (e.g. the inline-comment
    tool) — the base read-write tool set comes from ``mode="read_write"``.
    """
    owner, repo, issue_num = task["owner"], task["repo"], task["issue_number"]
    base_branch = task.get("base_branch", "main")
    token = task["_token"]
    provider = rc.get("provider", "github")

    state = {}
    cut = make_can_use_tool(task, rc, state, on_post=progress_callback)

    harness = resolve_harness("fix", rc, cfg or {})
    fix_model = harness.get("model") or fix_model

    try:
        run_result = runner.run(
            prompt,
            cwd=str(wt),
            cfg=cfg or {},
            repo_cfg=rc,
            resume=resume_id,
            fork_session=fork_session,
            model=fix_model,
            mode="read_write",
            extra_tools=extra_tools,
            mcp_servers=mcp_servers,
            progress_callback=progress_callback,
            can_use_tool=cut,
            state=state,
            harness_cfg=harness,
        )
    except asyncio.TimeoutError:
        return HandlerResult(f"FAILED: {timeout_msg}")
    except Exception as e:  # State-machine boundary — any SDK failure becomes a FAILED result.
        dbg.error(f"{error_prefix}: SDK error: %s", e, exc_info=True)
        return HandlerResult(f"FAILED: {e}")

    log(f"[FIX] {task['id']} sdk subtype={run_result.subtype} session={run_result.session_id} duration={run_result.duration_seconds:.1f}s cost=${run_result.cost_usd or 0:.4f} text_chars={len(run_result.text or '')}")
    dbg.debug("FIX: sdk returned subtype=%s session=%s", run_result.subtype, run_result.session_id)
    dbg.debug("FIX OUTPUT (%d chars):\n%s", len(run_result.text or ""), (run_result.text or "")[:4000])

    if state.get("asked_question_md"):
        # The callback posts a standalone question comment and records
        # whether it landed; fall back to posting it when the post failed
        # (issue #184 — never trust "already posted" blindly).
        if state.get("asked_question_posted") is False:
            post_question_fallback(
                task, rc,
                state["asked_question_md"], progress_callback,
            )
        return HandlerResult(
            "WAITING: questions",
            cost_usd=run_result.cost_usd,
            duration_seconds=run_result.duration_seconds,
            session_id=run_result.session_id,
        )

    if not run_result.ok:
        return HandlerResult(
            f"FAILED: agent ended with subtype={run_result.subtype}",
            session_id=run_result.session_id,
        )

    return _finalize_fix(
        task, run_result, wt, owner, repo, issue_num,
        base_branch, provider, token, rc, cfg or {},
        session_id=run_result.session_id,
        progress_callback=progress_callback,
    )


def run_fix(task: dict, guidance: str | None = None, repo_cfg: dict | None = None, cfg: dict | None = None, *, progress_callback=None, wt=None, fork_session: bool = False, fork_session_id: str | None = None) -> HandlerResult:
    """Run fix phase with bypassPermissions. Returns done-file content.

    Return format on success:
      - "DONE: no changes detected"  (no staged changes)
      - "DONE_SUMMARY\t<claude_summary_lines>\t<commit_sha>"  (committed changes)

    If *wt* is provided (pre-synced worktree path from the orchestrator),
    reuse it instead of calling create_worktree. The orchestrator may have
    already run sync_branch + conflict resolution before handing off here.

    ``fork_session_id`` is the checkpoint session id validated by the retry
    gate (``_fork_session_for_retry``). When forking, it is the authoritative
    resume source so the gate and the resumed value can never diverge
    (issue #173 F-15); the gate passes the exact id it checked.
    """
    owner, repo, issue_num = task["owner"], task["repo"], task["issue_number"]
    base_branch = task.get("base_branch", "main")
    plan_branch = task.get("plan_branch") or base_branch
    token = task["_token"]
    session_id = task.get("session_id")
    provider = (repo_cfg or {}).get("provider", "github")

    if wt is not None:
        # Orchestrator already created/synced the worktree
        dbg.debug("FIX: reusing pre-synced worktree=%s", wt)
    else:
        wt = create_worktree(
            owner, repo, issue_num, plan_branch, token, cfg or {}, provider,
            default_branch=base_branch, pull_strategy="merge", push_new=True,
        )
        dbg.debug("FIX: worktree=%s", wt)

    # Check for merge conflicts produced by pull_strategy="merge"
    branch = get_vcs(
        {"owner": owner, "repo": repo, "token": token, "provider": provider}
    ).branch_name(issue_num)
    conflict_files = get_merge_conflict_files(wt)

    # Build MCP server config: comment server (always) + inline comment server (if PR exists)
    rc = repo_cfg or {}
    mcp_servers = build_mcp_comment_server(task, rc) or {}
    # The fix phase runs in mode="read_write": the backend supplies the full
    # read-write tool set (Read/Edit/Write/Bash/Glob/Grep/AskUserQuestion, the
    # MCP comment tools, and the agent/progress tools). The ONLY genuinely
    # extra tool is the inline-comment tool, appended here when a PR exists
    # (S6 / issue #169 F-10 — the handler no longer re-builds the base tool
    # list on top of mode="read_write").
    extra_tools: list[str] = []

    # Register inline comment server if an existing PR exists for this branch
    pr_number = task.get("pr_number")
    if not pr_number:
        try:
            _link_rc = dict(rc, token=token)
            existing_pr = get_vcs(_link_rc).find_existing_pr(branch)
            if existing_pr and existing_pr.number:
                pr_number = existing_pr.number
        except Exception as e:  # Best-effort PR lookup — missing inline comment server is non-fatal.
            dbg.debug("find_existing_pr failed: %s", e)

    if pr_number:
        head_sha = _get_branch_head_sha(wt, branch)
        if head_sha:
            inline_cfg = build_mcp_inline_comment_server(task, rc, head_sha, pr_number)
            if inline_cfg:
                mcp_servers.update(inline_cfg)
                extra_tools.extend(_MCP_INLINE_COMMENT_TOOLS)
                dbg.debug("FIX: inline comment server registered (pr=%d sha=%s)", pr_number, head_sha[:8])

    plan_file_path = task.pop("plan_file_path", None)
    plan_text_override = None
    use_fresh_session = False
    if plan_file_path:
        try:
            plan_text_override = Path(plan_file_path).read_text(encoding="utf-8")
            use_fresh_session = True
            dbg.debug("FIX: starting fresh session with plan from %s", plan_file_path)
        except OSError as e:
            dbg.warning("FIX: plan file %s unreadable (%s); recovering plan from comments", plan_file_path, e)
            use_fresh_session = True

    prompt = build_fix_prompt(task, guidance, repo_root=str(wt), plan_text=plan_text_override, repo_cfg=rc)

    if conflict_files:
        files_block = "\n".join(f"  - {f}" for f in conflict_files)
        prompt += (
            "\n\n## Merge conflicts to resolve first\n\n"
            f"Pulling `origin/{branch}` produced conflicts in:\n{files_block}\n\n"
            "Before doing anything else, read each conflicted file, reconcile the changes "
            "(remove all `<<<<<<<` / `=======` / `>>>>>>>` markers), then run:\n\n"
            "    git add -A && git commit --no-edit\n\n"
            "to complete the merge. Then proceed with the user's request."
        )

    fix_model = rc.get("fix_model") or cfg.get("FIX_MODEL") or None

    # Fork-on-retry: when *fork_session* is set, branch from the surviving
    # known-good checkpoint — which the FAILED path preserves — instead of
    # session_id (nulled out on failure). With no good checkpoint yet
    # (first-ever failure) there is nothing to fork from, so we fall back to a
    # fresh session. use_fresh_session (plan-file seeding) still wins: it always
    # starts a new session, no fork.
    #
    # The resumed id comes from fork_session_id — the exact checkpoint the
    # retry gate validated — when available, so the gate and the value handed
    # to the SDK can never diverge (issue #173 F-15). We fall back to
    # last_good_session_id only for callers that set fork_session without
    # threading the id.
    if fork_session and not use_fresh_session:
        resume_source = fork_session_id or task.get("last_good_session_id") or session_id
        effective_fork = resume_source is not None
    else:
        resume_source = None if use_fresh_session else session_id
        effective_fork = False

    _sess_lbl = (
        "NEW" if use_fresh_session
        else ("FORK" if effective_fork else "RESUME")
    )
    log(f"[FIX] {task['id']} session={_sess_lbl} resume_from={resume_source or 'none'} plan_file={plan_file_path or 'none'}")
    log(f"[FIX] {task['id']} model={fix_model or 'default'} guidance={str(guidance or '')[:200]!r} prompt_len={len(prompt)} conflict_files={len(conflict_files or [])}")
    dbg.debug("FIX: model=%s guidance=%s", fix_model or "default", guidance)

    return _run_fix_session(
        task, prompt, wt, cfg, rc,
        resume_id=resume_source,
        extra_tools=extra_tools,
        mcp_servers=mcp_servers,
        fix_model=fix_model,
        timeout_msg="timeout during fix phase",
        error_prefix="run_fix",
        progress_callback=progress_callback,
        fork_session=effective_fork,
    )


def resume_fix(task: dict, user_text: str, repo_cfg: dict, cfg: dict, *, progress_callback=None) -> HandlerResult:
    """Resume fix session after user replies to an AskUserQuestion.

    Reattaches the prior session, feeds the user reply, and runs Claude
    until it either asks another question (WAITING again) or finishes
    the code changes (DONE_SUMMARY).
    """
    owner, repo, issue_num = task["owner"], task["repo"], task["issue_number"]
    base_branch = task.get("base_branch", "main")
    plan_branch = task.get("plan_branch") or base_branch
    token = task["_token"]
    session_id = task.get("session_id")
    provider = (repo_cfg or {}).get("provider", "github")

    wt = create_worktree(
        owner, repo, issue_num, plan_branch, token, cfg or {}, provider,
        default_branch=base_branch, pull_strategy="merge", push_new=True,
    )
    dbg.debug("FIX_RESUME: worktree=%s session=%s", wt, session_id)

    # Fast-forward worktree to origin/branch so the session operates on current state
    ff_branch = get_vcs(
        {"owner": owner, "repo": repo, "token": "", "provider": provider}
    ).branch_name(issue_num)
    fast_forward_worktree(wt, ff_branch)

    resume_prompt = (
        f"The user replied to your question(s):\n\n{user_text}\n\n"
        "Continue implementing the fix. You may call AskUserQuestion again "
        "if needed, or proceed to make the code changes.\n\n"
        "When done, summarize what you changed."
    )

    rc = repo_cfg or {}
    mcp_servers = build_mcp_comment_server(task, rc) or {}
    # No genuinely-extra tools on a resume (no PR inline-comment server here) —
    # the full read-write tool set comes from mode="read_write" (S6 / #169 F-10).
    extra_tools: list[str] = []

    fix_model = rc.get("fix_model") or cfg.get("FIX_MODEL") or None
    log(f"[FIX] {task['id']} session=RESUME from={session_id} user_reply_chars={len(user_text)}")

    return _run_fix_session(
        task, resume_prompt, wt, cfg, rc,
        resume_id=session_id,
        extra_tools=extra_tools,
        mcp_servers=mcp_servers,
        fix_model=fix_model,
        timeout_msg="timeout during fix resume",
        error_prefix="resume_fix",
        progress_callback=progress_callback,
    )


def _finalize_fix(
    task: dict,
    run_result,
    wt: Path,
    owner: str,
    repo: str,
    issue_num: int,
    base_branch: str,
    provider: str,
    token: str,
    repo_cfg: dict,
    cfg: dict,
    *,
    session_id: str | None = None,
    progress_callback=None,
) -> HandlerResult:
    """Commit, push, run the post-fix test gate, and return the final HandlerResult.

    Shared by run_fix and resume_fix to avoid duplicating the commit/push flow.
    """
    # Build the human-facing summary from the response WITHOUT the internal
    # <AUTOSWE_COMMIT> block, so the "Summary:" issue comment and the PR body
    # show the agent's prose rather than the commit-message scaffold.
    prose = _strip_commit_block(run_result.text or "")
    summary_lines = [line.strip() for line in prose.split("\n") if line.strip()]
    summary_text = "\n".join(summary_lines[-10:]) if summary_lines else "Changes applied."

    # Build the commit message from the agent's structured <AUTOSWE_COMMIT>
    # block. Fall back to the issue title as the subject (and the raw summary
    # as the body) when the agent omitted or malformed the block.
    parsed_subject, parsed_body = _parse_commit_message(run_result.text or "")
    # Screen the subject to a single, git-friendly line (collapse any internal
    # newlines the LLM may have introduced; truncate past git's ~72-char soft
    # limit). Applied to both the agent-generated subject and the issue-title
    # fallback so the subject line is always clean.
    subject = _clean_commit_subject(parsed_subject or task.get("title") or f"Issue #{issue_num}")
    body_text = parsed_body or "\n".join(summary_lines[-15:])
    if body_text:
        commit_msg = f"{subject}\n\n{body_text}\n\nFixes #{issue_num}"
    else:
        commit_msg = f"{subject}\n\nFixes #{issue_num}"

    log(f"[FIX] {task['id']} committing subject={subject!r}")
    dbg.debug("FIX: committing with subject=%r", subject)
    try:
        commit_result = commit_and_push(wt, owner, repo, issue_num, commit_msg, base_branch, provider)
    except Exception as e:  # Commit/push boundary — any provider or git error surfaces to the task result.
        dbg.error("_finalize_fix: commit/push failed: %s", e, exc_info=True)
        return HandlerResult(f"FAILED: commit/push error: {e}")

    if not commit_result["committed"]:
        log(f"[FIX] {task['id']} NO CHANGES DETECTED — worktree unmodified by session")
        return HandlerResult(
            "DONE: no changes detected",
            cost_usd=run_result.cost_usd,
            duration_seconds=run_result.duration_seconds,
            session_id=session_id,
        )

    log(f"[FIX] {task['id']} committed sha={commit_result['commit_sha']} branch={commit_result['branch']}")

    # Post-fix test gate (Natedorr/testProject#20): run the repo's suite on the
    # committed work before this task can reach the terminal `fixed` state.
    # It runs AFTER commit_and_push so the work is never lost — a red suite
    # lands in the non-terminal `test_failed` state with a comment carrying
    # the failure, and /pr stays blocked until a /fix re-runs it green.
    gate = run_test_gate(wt, cfg, repo_cfg, progress_callback=progress_callback)
    if not gate.ok:
        log(f"[FIX] {task['id']} test gate RED: {gate.reason} — refusing terminal `fixed`")
        detail = gate.reason + (f"\n{gate.output}" if gate.output else "")
        return HandlerResult(
            f"TESTS_FAILED\t{detail}\t{commit_result['commit_sha']}",
            cost_usd=run_result.cost_usd,
            duration_seconds=run_result.duration_seconds,
            session_id=session_id,
        )
    if not gate.ran:
        log(f"[FIX] {task['id']} test gate skipped: {gate.reason}")

    return HandlerResult(
        f"DONE_SUMMARY\t{summary_text}\t{commit_result['commit_sha']}",
        cost_usd=run_result.cost_usd,
        duration_seconds=run_result.duration_seconds,
        session_id=session_id,
    )


def resolve_sync_conflicts(
    task: dict,
    conflict_files: list[str],
    *,
    repo_cfg: dict,
    cfg: dict,
    progress_callback=None,
) -> HandlerResult:
    """Resolve merge conflicts in an existing worktree using Claude.

    Operates on an already-conflicted worktree (left by sync_branch).
    Uses a focused conflict-resolution prompt seeded with the plan.
    Resumes the prior session for continuity.
    After Claude commits the merge, pushes and returns DONE_SUMMARY.

    Does NOT call create_worktree — resolves the existing path.
    Does NOT call fast_forward_worktree — would clobber conflicted state.
    Does NOT pop plan_file_path — only reads it; plan must persist for /fix.
    """
    owner, repo, issue_num = task["owner"], task["repo"], task["issue_number"]
    base_branch = task.get("base_branch", "main")
    # The branch that was actually merged into this one (issue #187):
    # plan_branch when /plan --branch pinned it, else the repo default.
    sync_base = task.get("plan_branch") or base_branch
    session_id = task.get("session_id")
    provider = (repo_cfg or {}).get("provider", "github")
    rc = repo_cfg or {}

    # Resolve existing worktree — do NOT create a new one
    wt = worktree_path(owner, repo, issue_num, cfg or {}, provider)
    if not wt.exists():
        return HandlerResult(f"FAILED: worktree missing at {wt}; cannot resolve conflicts")

    dbg.debug("RESOLVE: worktree=%s session=%s conflicts=%d", wt, session_id, len(conflict_files))

    # Read plan file if available — do NOT pop it (persist for downstream /fix)
    plan_text = None
    plan_file_path = task.get("plan_file_path")
    if plan_file_path:
        try:
            plan_text = Path(plan_file_path).read_text(encoding="utf-8")
            dbg.debug("RESOLVE: plan from %s", plan_file_path)
        except OSError as e:
            dbg.warning("RESOLVE: plan file %s unreadable (%s)", plan_file_path, e)

    prompt = build_conflict_resolution_prompt(
        task, conflict_files, plan_text=plan_text, base_branch=sync_base, repo_cfg=rc,
    )

    # No genuinely-extra tools — the full read-write set comes from
    # mode="read_write"; AskUserQuestion is held via disallowed_tools_override
    # to keep conflict resolution autonomous (S6 / #169 F-10).
    mcp_servers = build_mcp_comment_server(task, rc) or {}
    extra_tools: list[str] = []

    log(
        f"[RESOLVE] {task['id']} session={'RESUME' if session_id else 'NEW'} "
        f"session_id={session_id or 'none'} conflicts={len(conflict_files)}"
    )

    fix_model = rc.get("fix_model") or cfg.get("FIX_MODEL") or None
    dbg.debug("RESOLVE: model=%s", fix_model or "default")

    state = {}
    cut = make_can_use_tool(task, rc, state, on_post=progress_callback)

    harness = resolve_harness("fix", rc, cfg or {})
    fix_model = harness.get("model") or fix_model

    try:
        run_result = runner.run(
            prompt,
            cwd=str(wt),
            cfg=cfg or {},
            repo_cfg=rc,
            resume=session_id,  # None if first conflict with no prior session
            model=fix_model,
            mode="read_write",
            extra_tools=extra_tools,
            disallowed_tools_override=["AskUserQuestion"],
            mcp_servers=mcp_servers,
            progress_callback=progress_callback,
            can_use_tool=cut,
            state=state,
            harness_cfg=harness,
        )
    except asyncio.TimeoutError:
        return HandlerResult("FAILED: timeout during conflict resolution")
    except Exception as e:  # State-machine boundary — any SDK failure becomes a FAILED result.
        dbg.error("resolve_sync_conflicts: SDK error: %s", e, exc_info=True)
        return HandlerResult(f"FAILED: {e}")

    log(
        f"[RESOLVE] {task['id']} sdk subtype={run_result.subtype} "
        f"session={run_result.session_id} duration={run_result.duration_seconds:.1f}s"
    )

    if not run_result.ok:
        return HandlerResult(
            f"FAILED: conflict resolution ended subtype={run_result.subtype}",
            cost_usd=run_result.cost_usd,
            duration_seconds=run_result.duration_seconds,
            session_id=run_result.session_id,
        )

    # Verify conflicts are actually cleared
    remaining = get_merge_conflict_files(wt)
    if remaining:
        files_list = ", ".join(remaining)
        return HandlerResult(
            f"FAILED: unresolved conflicts: {files_list}",
            cost_usd=run_result.cost_usd,
            duration_seconds=run_result.duration_seconds,
            session_id=run_result.session_id,
        )

    # Push the resolved merge commit
    repo_cfg_for_vcs = {"owner": owner, "repo": repo, "token": "", "provider": provider}
    branch = get_vcs(repo_cfg_for_vcs).branch_name(issue_num)
    try:
        subprocess.run(
            ["git", "-C", str(wt), "push", "origin", branch],
            capture_output=True, text=True, timeout=60, check=True,
        )
    except Exception as e:  # subprocess can raise TimeoutExpired, CalledProcessError, OSError
        return HandlerResult(
            f"FAILED: push after resolution failed: {e}",
            cost_usd=run_result.cost_usd,
            duration_seconds=run_result.duration_seconds,
            session_id=run_result.session_id,
        )

    # Compute summary stats
    try:
        short_sha_result = subprocess.run(
            ["git", "-C", str(wt), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=10, check=True,
        )
        short_sha = short_sha_result.stdout.strip()
    except Exception:  # Subprocess call (git rev-parse) is best-effort; fallback to "unknown".
        short_sha = "unknown"

    try:
        ahead_result = subprocess.run(
            ["git", "-C", str(wt), "log", f"origin/{sync_base}..HEAD", "--oneline"],
            capture_output=True, text=True, timeout=10, check=False,
        )
        ahead_count = len(ahead_result.stdout.strip().split("\n")) if ahead_result.stdout.strip() else 0
    except Exception:  # Subprocess call (git log) is best-effort; fallback to 0.
        ahead_count = 0

    summary = (
        f"Resolved merge conflicts in {len(conflict_files)} file(s) "
        f"and merged origin/{sync_base} into {branch}. "
        f"{ahead_count} commits ahead."
    )

    return HandlerResult(
        f"DONE_SUMMARY\t{summary}\t{short_sha}",
        cost_usd=run_result.cost_usd,
        duration_seconds=run_result.duration_seconds,
        session_id=run_result.session_id,
    )
