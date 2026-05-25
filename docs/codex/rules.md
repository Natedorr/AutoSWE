# Rules (Command Execution Policy)

Rules control which commands Codex can run outside the sandbox. Experimental.

## File Location

Create `.rules` files under a `rules/` folder next to an active config layer:

| Scope | Location |
|---|---|
| User | `~/.codex/rules/default.rules` |
| Project | `<repo>/.codex/rules/default.rules` |

## Rule Format (Starlark)

```starlark
prefix_rule(
  pattern = ["gh", "pr", "view"],       # Command prefix to match
  decision = "prompt",                  # "allow" | "prompt" | "forbidden"
  justification = "Viewing PRs is allowed with approval",
  match = [                             # Inline unit tests (commands that should match)
    "gh pr view 7888",
    "gh pr view --repo openai/codex",
  ],
  not_match = [                         # Commands that should NOT match
    "gh pr --repo openai/codex view 7888",
  ],
)
```

## Pattern Matching

Each pattern element can be:
- **Literal string:** `"pr"` — exact match at that position
- **Union of literals:** `["view", "list"]` — match any alternative at that position

```starlark
# Allow `gh pr view` or `gh pr list`
prefix_rule(
  pattern = ["gh", "pr", ["view", "list"]],
  decision = "allow",
)
```

## Decision Priority

When multiple rules match, the **most restrictive** wins: `forbidden` > `prompt` > `allow`

## Shell Script Handling

Codex treats shell invocations specially:

### Split (safe scripts)

If the script is a linear chain of plain commands joined by `&&`, `||`, `;`, or `|`:

```bash
bash -lc "git add . && rm -rf /"
```

Codex splits this into `["git", "add", "."]` and `["rm", "-rf", "/"]`, evaluating each separately. The most restrictive result wins.

### Not Split (advanced shell features)

Scripts with variable expansion, redirection (`>`, `>>`, `<`), or other advanced features are treated as a single invocation.

## Testing Rules

```bash
codex execpolicy check --pretty \
  --rules ~/.codex/rules/default.rules \
  -- gh pr view 7888 --json title,body,comments
```

Use multiple `--rules` flags to combine files.

## Smart Approvals

When enabled (default), Codex may propose `prefix_rule` suggestions during escalation requests. Review carefully before accepting.

## Admin Requirements

Admins can enforce restrictive `prefix_rule` entries via `requirements.toml` in managed configuration.

## See Also

- [Sandboxing & Security](./sandboxing.md)
- [Configuration](./configuration.md)
