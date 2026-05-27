# Source: https://developers.openai.com/codex/use-cases/code-migrations/

Codex use cases[Codex](/assets/OAI_Codex-Lockup_Fallback_Black.svg)

Codex use case

# Run code migrations

Migrate legacy stacks in controlled checkpoints.Difficulty**Advanced**Time horizon**1h**

Use Codex to map a legacy system to a new stack, land the move in milestones, and validate parity before each transition.

## Best for

- Legacy-to-modern stack moves where frameworks, runtimes, build systems, or platform conventions need to change.
- Teams that need compatibility layers, phased transitions, and explicit validation at each migration checkpoint.

# Contents
← All use cases[← All use cases](/codex/use-cases)Copy pageExport as PDF[Export as PDF](/codex/use-cases/code-migrations/?export=pdf)

Use Codex to map a legacy system to a new stack, land the move in milestones, and validate parity before each transition.Advanced1h

Related linksModernizing your Codebase with Codex[Modernizing your Codebase with Codex](/cookbook/examples/codex/code_modernization)Follow a goal[Follow a goal](/codex/use-cases/follow-goals)Worktrees in the Codex app[Worktrees in the Codex app](/codex/app/worktrees)

## Best for

- Legacy-to-modern stack moves where frameworks, runtimes, build systems, or platform conventions need to change.
- Teams that need compatibility layers, phased transitions, and explicit validation at each migration checkpoint.

## Skills & Plugins

- Security Best Practices[Security Best Practices](https://github.com/openai/skills/tree/main/skills/.curated/security-best-practices)Check risky migrations, dependency changes, and exposed surfaces before you merge.
- Gh Fix Ci[Gh Fix Ci](https://github.com/openai/skills/tree/main/skills/.curated/gh-fix-ci)Work through failing CI after each migration milestone instead of leaving cleanup until the end.
- Aspnet Core[Aspnet Core](https://github.com/openai/skills/tree/main/skills/.curated/aspnet-core)Use framework-specific guidance when a migration touches ASP.NET Core app models, `Program.cs`, middleware, testing, performance, or version upgrades.

Skill | Why use it
Security Best Practices[Security Best Practices](https://github.com/openai/skills/tree/main/skills/.curated/security-best-practices) | Check risky migrations, dependency changes, and exposed surfaces before you merge.
Gh Fix Ci[Gh Fix Ci](https://github.com/openai/skills/tree/main/skills/.curated/gh-fix-ci) | Work through failing CI after each migration milestone instead of leaving cleanup until the end.
Aspnet Core[Aspnet Core](https://github.com/openai/skills/tree/main/skills/.curated/aspnet-core) | Use framework-specific guidance when a migration touches ASP.NET Core app models, `Program.cs`, middleware, testing, performance, or version upgrades.

## Starter promptMigrate this codebase from [legacy stack or system] to [target stack or system]. Requirements: - Start by inventorying the legacy assumptions: routing, data models, auth, configuration, build tooling, tests, deployment, and external contracts. - Map the old stack to the new one and call out anything that has no direct equivalent. - Propose an incremental migration plan with compatibility layers or checkpoints instead of one big rewrite. - Keep behavior unchanged unless the migration explicitly requires a user-visible change. - Work in milestones and run lint, type-check, and focused tests after each milestone. - Keep rollback or fallback options visible until the transition is complete. - If validation fails, fix it before continuing. - Start by mapping the migration surface and proposing the checkpoint plan.Open in the Codex app[Open in the Codex app](codex://threads/new?prompt=Migrate+this+codebase+from+%5Blegacy+stack+or+system%5D+to+%5Btarget+stack+or+system%5D.%0A%0ARequirements%3A%0A-+Start+by+inventorying+the+legacy+assumptions%3A+routing%2C+data+models%2C+auth%2C+configuration%2C+build+tooling%2C+tests%2C+deployment%2C+and+external+contracts.%0A-+Map+the+old+stack+to+the+new+one+and+call+out+anything+that+has+no+direct+equivalent.%0A-+Propose+an+incremental+migration+plan+with+compatibility+layers+or+checkpoints+instead+of+one+big+rewrite.%0A-+Keep+behavior+unchanged+unless+the+migration+explicitly+requires+a+user-visible+change.%0A-+Work+in+milestones+and+run+lint%2C+type-check%2C+and+focused+tests+after+each+milestone.%0A-+Keep+rollback+or+fallback+options+visible+until+the+transition+is+complete.%0A-+If+validation+fails%2C+fix+it+before+continuing.%0A-+Start+by+mapping+the+migration+surface+and+proposing+the+checkpoint+plan.)Migrate this codebase from [legacy stack or system] to [target stack or system]. Requirements: - Start by inventorying the legacy assumptions: routing, data models, auth, configuration, build tooling, tests, deployment, and external contracts. - Map the old stack to the new one and call out anything that has no direct equivalent. - Propose an incremental migration plan with compatibility layers or checkpoints instead of one big rewrite. - Keep behavior unchanged unless the migration explicitly requires a user-visible change. - Work in milestones and run lint, type-check, and focused tests after each milestone. - Keep rollback or fallback options visible until the transition is complete. - If validation fails, fix it before continuing. - Start by mapping the migration surface and proposing the checkpoint plan.

## Introduction

When you are moving from one stack to another, you can leverage Codex to map and execute a controlled migration: routing, data models, configuration, auth, background jobs, build tooling, deployment, tests, or even the language and framework conventions themselves.

Codex is useful here because it can inventory the legacy system, map old concepts to new ones, and land the change in checkpoints instead of one giant rewrite. That matters when you are moving off a legacy framework, porting to a new runtime, or incrementally replacing one stack with another while the product still has to keep working.

## How to use

- Start by inventorying the migration surface: legacy packages, framework conventions, routing, data access, auth, configuration, build tooling, tests, deployment assumptions, and any external contracts that must survive the move.
- Ask Codex to map the legacy concepts to the target stack and call out what has no direct match.
- Choose an incremental strategy: compatibility layer, module-by-module port, branch-by-abstraction, or a strangler-style replacement around one boundary at a time.
- Keep behavior stable until the migration itself forces a visible change, and name those exceptions explicitly.
- After each milestone, run the smallest validation that proves parity: lint, type-check, focused tests, contract tests, smoke tests, or a side-by-side check against the legacy path.
- Review the diff and the remaining transition risk after each checkpoint instead of waiting for the full rewrite.

## Leverage ExecPlans

In ourcode modernization cookbook[code modernization cookbook](/cookbook/examples/codex/code_modernization), we introduce ExecPlans: documents that let Codex keep an overview of the cleanup, spell out the intended end state, and log validation after each pass. When you ask Codex to run a complex migration, ask it to create an ExecPlan for each part of the system to make sure every decision and tech stack choice is recorded and can be reviewed later.

## Combine with a goal

For long-running migration slices, use agoal[goal](/codex/use-cases/follow-goals)to guide Codex through the work. Set the goal with a clear end state, parity checks, rollback expectations, and a stopping condition.

## Related use cases

### Add evals to your AI application

Ask Codex to inspect your AI application, identify the behavior you want to evaluate, and...EvaluationQuality[Add evals to your AI applicationAsk Codex to inspect your AI application, identify the behavior you want to evaluate, and...EvaluationQuality](/codex/use-cases/ai-app-evals)

### Build React Native apps with Expo

Use Codex with the Expo plugin to scaffold React Native apps, stay inside Expo Router and...MobileEngineering[Build React Native apps with ExpoUse Codex with the Expo plugin to scaffold React Native apps, stay inside Expo Router and...MobileEngineering](/codex/use-cases/react-native-expo-apps)

### Create a CLI Codex can use

Ask Codex to create a composable CLI it can run from any folder, combine with repo scripts...EngineeringCode[Create a CLI Codex can useAsk Codex to create a composable CLI it can run from any folder, combine with repo scripts...EngineeringCode](/codex/use-cases/agent-friendly-clis)