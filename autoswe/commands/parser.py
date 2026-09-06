import re

# The trailing lookahead enforces a word boundary: `/fixture` must not match
# `/fix`, `/prod-notes` must not match `/pr`, `/planning` must not match
# `/plan`. The backtick alternative covers `` `/fix` ``-style lines where a
# leading backtick was stripped but a trailing one remains.
_SLASH_CMD_RE = re.compile(
    r"/(?:fix|plan|pr|retry|skip|sync|abort|review)(?=\s|$|`)", re.IGNORECASE
)
_BRANCH_RE = re.compile(r"--branch\s+(\S+)")


# Characters git's ref-name rules reject anywhere in a branch name
# (approximation of `git check-ref-format --branch`). Quotes are rejected on
# top of git's rules: a `--branch` token containing one is almost certainly a
# shell/sentence artifact, and the pre-#184 character-class capture rejected
# them too.
_BRANCH_BAD_CHARS_RE = re.compile(r"[\x00-\x1f\x7f ~^\?:*\"'\\]")


def _is_valid_branch_name(name: str) -> bool:
    """Validate a branch token against git's ref-name rules.

    Approximates `git check-ref-format --branch` plus quotes (see the
    character class above): rejects empty names, names with control
    characters or space, `~`, `^`, `:`, `?`, `*`, `[`, backslash, quotes,
    `..`, `//`, `@{`, a leading `-` or `.`, a trailing `.`, and names ending
    in `.lock`. (git additionally rejects leading `/` and `@{` sequences;
    those are rare enough in user-typed `--branch` values to skip.)
    """
    if not name or name.startswith(("-", ".")) or name.endswith("."):
        return False
    if ".." in name or "//" in name or "@{" in name:
        return False
    if name.endswith(".lock"):
        return False
    return _BRANCH_BAD_CHARS_RE.search(name) is None


def _sanitize_branch_token(raw: str) -> str | None:
    """Validate a `--branch` token, repairing the trailing-period typo.

    The token is the full whitespace-delimited word after `--branch`, so
    sentence punctuation sticks to it: `/plan --branch docs.  what was the
    question` yields the token `docs.` (issue #184). Git rejects branch names
    with a trailing dot, so the common repair is to strip it (`docs.` ->
    `docs`). Surrounding quotes are also stripped (`"docs"` -> `docs`,
    matching the previous character-class capture). Returns None when the
    token is (or stays) invalid — the caller then falls back to the default
    branch.
    """
    if _is_valid_branch_name(raw):
        return raw
    candidate = raw
    if len(candidate) >= 2 and candidate[0] == candidate[-1] and candidate[0] in "\"'":
        candidate = candidate[1:-1]
        if _is_valid_branch_name(candidate):
            return candidate
    repaired = candidate.rstrip(".")
    if repaired and _is_valid_branch_name(repaired):
        return repaired
    return None


def _parse_mention(text: str, bot_name: str) -> tuple[str, str, str] | None:
    """Parse @<bot_name> <guidance> as an alias for /fix.

    Returns ("/fix", guidance, None) if the mention matches the configured bot name,
    or None if no matching mention is found.
    """
    pattern = re.compile(r"@" + re.escape(bot_name) + r"\s+(.+)", re.IGNORECASE)
    for line in text.split("\n"):
        m = pattern.search(line)
        if m:
            return ("/fix", m.group(1).strip(), None)
    return None


def parse_slash_command(text: str, bot_name: str = "autoswe"):
    """Return (command, guidance, branch) from the last slash command found in text, or None.

    Recognized commands: /fix, /plan, /pr, /retry, /skip, /sync, /abort, /review
    Supports ``--branch <name>`` (e.g. ``/plan --branch develop``).
    Guidance text after ``with`` keyword is captured as the second element.

    Also recognizes ``@<bot_name> <guidance>`` as an alias for ``/fix with <guidance>``.
    Only matches commands at the start of a line (optionally preceded by a single backtick).
    Commands embedded in text (e.g. ``Post `/retry` to try again``) are ignored.

    Args:
        text: The comment body or issue text to parse.
        bot_name: The bot name to match for @mention triggers (default: "autoswe").
    """
    if not text:
        return None

    lines = text.split("\n")
    result = None

    for line in lines:
        # Command must be at the start of the line (no leading whitespace)
        # Allow optional backtick before the command
        check_line = line
        if check_line.startswith("`"):
            check_line = check_line[1:]
        m = _SLASH_CMD_RE.match(check_line)
        if m:
            cmd = m.group(0).lower()
            rest = check_line[m.end():].rstrip("`").strip()

            branch = None
            guidance = None

            if rest:
                branch_m = _BRANCH_RE.search(rest)
                if branch_m:
                    branch = _sanitize_branch_token(branch_m.group(1))
                    after_branch = rest[branch_m.end():].strip()
                    if after_branch.lower().startswith("with "):
                        after_branch = after_branch[5:].strip()
                    if after_branch:
                        guidance = after_branch
                else:
                    if rest.lower().startswith("with "):
                        rest = rest[5:].strip()
                    if rest:
                        guidance = rest

            result = (cmd, guidance, branch)

    # Check for @mention as /fix alias (lower priority than slash commands)
    if result is None:
        result = _parse_mention(text, bot_name)

    return result
