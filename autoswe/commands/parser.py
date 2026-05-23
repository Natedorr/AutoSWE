import re

_SLASH_CMD_RE = re.compile(r"/(?:fix|plan|pr|retry|skip|sync|abort|review)", re.IGNORECASE)
_BRANCH_RE = re.compile(r"--branch\s+([\w][\w\-./]+)")
_MENTION_RE = re.compile(r"@" r"([\w-]+)\s+(.+)", re.IGNORECASE)


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
                    branch = branch_m.group(1)
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
