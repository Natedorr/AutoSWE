# Workflows

## Code Exploration

### IDE
1. Open relevant files
2. Select code of interest
3. Prompt: "Explain how this code works. Include module responsibilities and gotchas."

### CLI
```bash
codex
# In TUI:
I need to understand this protocol. Read @foo.ts @schema.ts and explain the flow.
```

## Bug Fixing

```
Bug: Description of failing behavior

Repro:
1) Step one
2) Step two
3) Observe failure

Constraints:
- Do not change the API shape
- Keep the fix minimal
- Add regression test
```

## Code Review

```
/review                          # Default
/review Focus on security        # Custom
```

## Test Generation

```
Write a unit test for this function. Cover happy path + edge cases.
Follow conventions used in existing tests.
```

## Prototype from Design

```
Create a new page based on this screenshot.
Tech: React + Vite + Tailwind + TypeScript.
Match layout, spacing, typography.
```

## Refactor + Cloud Delegation

1. **Local planning:** `$plan — propose migration plan`
2. **Review & negotiate:** "Revise to specify exact file moves"
3. **Cloud execute:** Delegate milestone to Codex cloud environment
4. **Review diff:** Iterate if needed
5. **Create PR:** From cloud or pull locally

## Documentation Updates

```
Update "advanced features" docs with auth troubleshooting guidance.
Verify all links are valid.
```

## See Also

- [Prompting](./prompting.md)
- [Subagents](./subagents.md)
- [CLI Features](./cli-features.md)
