# Prompting Codex

## Thread Model

A **thread** is a single session: your prompt + model outputs + tool calls. Threads can include multiple prompts and run locally or in the cloud.

## Prompt Tips

- **Include verification steps:** repro steps, tests, linting commands
- **Break complex work into focused steps**
- **Be specific about constraints:** "Do not change the API shape"
- **Attach context:** files (`@path`), images, selected text

## Goal Mode

Give Codex a persistent objective:

```
/goal Migrate to TypeScript. App should compile in strict mode without `any`.
```

Good goals are measurable and include success criteria.

```
/goal          # View current goal
/goal pause    # Pause
/goal resume   # Resume
/goal clear    # Remove
```

Enable with `features.goals = true` if not visible.

## Effective Prompt Patterns

### Code Exploration

```
Explain how the transform module works and how other modules use it.
Trace the request flow from entry point to database call.
```

### Bug Fix

```
Bug: Clicking "Save" shows "Saved" but doesn't persist.

Repro:
1. npm run dev
2. Go to /settings
3. Toggle "Enable alerts"
4. Click Save
5. Refresh — toggle resets

Constraints:
- Do not change the API shape
- Keep the fix minimal
- Add a regression test
```

### Code Review

```
/review Focus on security vulnerabilities and edge cases
```

### Refactoring

```
$plan

Refactor the auth subsystem to:
- Split token parsing / session loading / permissions
- Reduce circular imports
- Improve testability

Constraints:
- No user-visible behavior changes
- Keep public APIs stable
- Step-by-step migration plan
```

### UI from Design

```
Create a dashboard based on this image.
Constraints: React + Vite + Tailwind, TypeScript.
Match spacing, typography, and layout.
Deliver: new route/page + README with run instructions.
```

## Context Management

- `/compact` — Summarize conversation to free tokens
- `/mention` — Attach specific files
- `@` — Fuzzy file search
- `!cmd` — Run shell commands inline

## Follow-up Control

- `Enter` while running — inject instructions
- `Tab` — queue for next turn
- `/side` — focused detour without disrupting main thread
- `/fork` — explore alternative approach

## See Also

- [AGENTS.md](./agents-md.md)
- [Workflows](./workflows.md)
- [CLI Features](./cli-features.md)
