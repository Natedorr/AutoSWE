# Source: https://developers.openai.com/codex/use-cases/native-ios-apps/

Codex use cases[Codex](/assets/OAI_Codex-Lockup_Fallback_Black.svg)

Codex use case

# Build for iOS

Use Codex to scaffold, build, and debug SwiftUI apps for iPhone and iPad.Difficulty**Advanced**Time horizon**1h**

Use Codex to scaffold iOS SwiftUI projects, keep the build loop CLI-first with`xcodebuild`or Tuist, and add XcodeBuildMCP or focused SwiftUI skills when the work gets deeper.

## Best for

- Greenfield iOS SwiftUI apps where you want Codex to scaffold the app and build loop from scratch
- Existing iPhone and iPad projects where Codex needs schemes, simulator output, screenshots, or UI automation before the work is done
- Teams that want long-running iOS UI tasks to stay agentic and CLI-first instead of depending on the Xcode GUI

# Contents
← All use cases[← All use cases](/codex/use-cases)Copy pageExport as PDF[Export as PDF](/codex/use-cases/native-ios-apps/?export=pdf)

Use Codex to scaffold iOS SwiftUI projects, keep the build loop CLI-first with`xcodebuild`or Tuist, and add XcodeBuildMCP or focused SwiftUI skills when the work gets deeper.Advanced1h

Related linksModel Context Protocol[Model Context Protocol](/codex/mcp)Agent skills[Agent skills](/codex/skills)

## Best for

- Greenfield iOS SwiftUI apps where you want Codex to scaffold the app and build loop from scratch
- Existing iPhone and iPad projects where Codex needs schemes, simulator output, screenshots, or UI automation before the work is done
- Teams that want long-running iOS UI tasks to stay agentic and CLI-first instead of depending on the Xcode GUI

## Skills & Plugins

- Build iOS Apps[Build iOS Apps](https://github.com/openai/plugins/tree/main/plugins/build-ios-apps)Build or refactor SwiftUI UI, adopt modern iOS patterns such as Liquid Glass, audit runtime performance, and debug apps on simulators with XcodeBuildMCP-backed workflows.

Skill | Why use it
Build iOS Apps[Build iOS Apps](https://github.com/openai/plugins/tree/main/plugins/build-ios-apps) | Build or refactor SwiftUI UI, adopt modern iOS patterns such as Liquid Glass, audit runtime performance, and debug apps on simulators with XcodeBuildMCP-backed workflows.

## Starter promptScaffold a starter SwiftUI app and add a build-and-launch script I can wire to a `Build` action in my local environment. Constraints: - Stay CLI-first. Prefer Apple's `xcodebuild`; if a cleaner setup helps, it's okay to use Tuist. - If this repo already contains a full Xcode project, use XcodeBuildMCP to list targets, pick the right scheme, build, launch, and capture screenshots while you iterate. - Reuse existing models, navigation patterns, and shared utilities when they already exist. - Keep the app focused on iPhone and iPad unless I explicitly ask for a shared Apple-platform implementation. - Use a small trustworthy validation loop after each change, then expand to broader builds only when the narrower check passes. - Tell me whether you treated this as a greenfield scaffold or an existing-project change. Deliver: - the app scaffold or requested feature slice - a small build-and-launch script with the exact commands - the smallest relevant validation steps you ran - the exact scheme, simulator, and checks you usedOpen in the Codex app[Open in the Codex app](codex://threads/new?prompt=Scaffold+a+starter+SwiftUI+app+and+add+a+build-and-launch+script+I+can+wire+to+a+%60Build%60+action+in+my+local+environment.%0A%0AConstraints%3A%0A-+Stay+CLI-first.+Prefer+Apple%27s+%60xcodebuild%60%3B+if+a+cleaner+setup+helps%2C+it%27s+okay+to+use+Tuist.%0A-+If+this+repo+already+contains+a+full+Xcode+project%2C+use+XcodeBuildMCP+to+list+targets%2C+pick+the+right+scheme%2C+build%2C+launch%2C+and+capture+screenshots+while+you+iterate.%0A-+Reuse+existing+models%2C+navigation+patterns%2C+and+shared+utilities+when+they+already+exist.%0A-+Keep+the+app+focused+on+iPhone+and+iPad+unless+I+explicitly+ask+for+a+shared+Apple-platform+implementation.%0A-+Use+a+small+trustworthy+validation+loop+after+each+change%2C+then+expand+to+broader+builds+only+when+the+narrower+check+passes.%0A-+Tell+me+whether+you+treated+this+as+a+greenfield+scaffold+or+an+existing-project+change.%0A%0ADeliver%3A%0A-+the+app+scaffold+or+requested+feature+slice%0A-+a+small+build-and-launch+script+with+the+exact+commands%0A-+the+smallest+relevant+validation+steps+you+ran%0A-+the+exact+scheme%2C+simulator%2C+and+checks+you+used)Scaffold a starter SwiftUI app and add a build-and-launch script I can wire to a `Build` action in my local environment. Constraints: - Stay CLI-first. Prefer Apple's `xcodebuild`; if a cleaner setup helps, it's okay to use Tuist. - If this repo already contains a full Xcode project, use XcodeBuildMCP to list targets, pick the right scheme, build, launch, and capture screenshots while you iterate. - Reuse existing models, navigation patterns, and shared utilities when they already exist. - Keep the app focused on iPhone and iPad unless I explicitly ask for a shared Apple-platform implementation. - Use a small trustworthy validation loop after each change, then expand to broader builds only when the narrower check passes. - Tell me whether you treated this as a greenfield scaffold or an existing-project change. Deliver: - the app scaffold or requested feature slice - a small build-and-launch script with the exact commands - the smallest relevant validation steps you ran - the exact scheme, simulator, and checks you used

## Scaffold the app and build loop

For greenfield work, start with plain prompting. Ask Codex to scaffold a starter iOS SwiftUI app and write a small build-and-launch script you can wire to a`Build`action in alocal environment[local environment](/codex/app/local-environments).

Keep the loop CLI-first. Apple’s`xcodebuild`can list schemes and handle build, test, archive,`build-for-testing`, and`test-without-building`actions from the terminal, which lets Codex stay in an agentic loop instead of bouncing into the Xcode GUI.

If you want a cleaner project generator and you’re comfortable with third-party tooling,Tuist[Tuist](https://tuist.dev/)is a good next step. It can generate and build Xcode projects without needing the GUI, while still letting Codex build and launch the app from the terminal.

UseXcodeBuildMCP[XcodeBuildMCP](https://www.xcodebuildmcp.com/)once you’re inside a full Xcode project and need deeper automation. That’s when schemes, targets, simulator control, screenshots, logs, and UI interaction matter enough that plain shell commands stop being the whole story.

## Leverage skills

For the first pass, you often don’t need a skill or MCP server. Add skills once the work gets specialized or you want stronger SwiftUI conventions baked into the run.

- 

SwiftUI expert[SwiftUI expert](https://github.com/AvdLee/SwiftUI-Agent-Skill)is a strong general-purpose SwiftUI skill with a lot of best practices already baked in.
- 

SwiftUI Pro[SwiftUI Pro](https://github.com/twostraws/SwiftUI-Agent-Skill/blob/main/swiftui-pro/SKILL.md)is a broad SwiftUI review skill for modern APIs, maintainability, accessibility, and performance.
- 

Liquid Glass expert[Liquid Glass expert](https://github.com/Dimillian/Skills/blob/main/swiftui-liquid-glass/SKILL.md)helps Codex adopt the new iOS 26 Liquid Glass APIs and tune custom components so they fit the latest system design.
- 

SwiftUI performance[SwiftUI performance](https://github.com/Dimillian/Skills/blob/main/swiftui-performance-audit/SKILL.md)helps when a feature feels slow or a SwiftUI view update path looks suspicious. It scans for common SwiftUI mistakes and produces a prioritized report of what to fix and where the biggest gains are.
- 

Swift concurrency expert[Swift concurrency expert](https://github.com/Dimillian/Skills/blob/main/swift-concurrency-expert/SKILL.md)helps when cryptic errors and compiler warnings start fighting the change you want to make. On GPT-5.4, you may need it less often, but it’s still useful when Swift concurrency diagnostics get noisy.
- 

SwiftUI view refactor[SwiftUI view refactor](https://github.com/Dimillian/Skills/blob/main/swiftui-view-refactor/SKILL.md)helps keep files smaller and make SwiftUI code more consistent across the repo.
- 

SwiftUI patterns[SwiftUI patterns](https://github.com/Dimillian/Skills/blob/main/swiftui-ui-patterns/SKILL.md)helps reach for predictable`@Observable`and`@Environment`architecture patterns as the app grows.

To learn more about how to install and use skills, see ourskills documentation[skills documentation](/codex/skills).

## Iterate

Once you have a first pass working, or if you’re starting from an existing project, you can start iterating on the UI or behavior.

For this part, be specific about what you want to change and how you want to change it.

Make that prompting layer explicit: tell Codex whether it’s working in a greenfield repo or an existing Xcode project, which iOS devices or deployment targets must keep working, and what validation loop you expect.

### Example prompt

For example, if you want to add a feature to an existing app, you can ask Codex for a change like this:Add the onboarding flow for this SwiftUI app. Constraints: - Reuse existing models, navigation patterns, and shared utilities. - Use XcodeBuildMCP to list the right targets or schemes, build the app, launch it, and capture screenshots if you need visual verification. - Keep the implementation focused on iPhone and iPad unless I explicitly ask for a shared iOS/macOS abstraction. - Tell me exactly which scheme, simulator, and checks you used. Implement the slice, verify it with the smallest relevant build or run loop, and summarize what changed.

## Practical tips

### Start with basics

Start with plain prompting for greenfield work. Ask Codex to scaffold a starter SwiftUI app and write a small build-and-launch script you can wire to a`Build`action in alocal environment[local environment](/codex/app/local-environments). For that first pass, you often don’t need any skill or MCP server.

### Use a small trustworthy validation loop

After each change, tell Codex to run the narrowest command that actually proves the contract you touched. Expand to broader builds later. This keeps Codex fast without pretending a full app build is required for every edit.

### Keep the loop CLI-first

Keep the loop CLI-first. Apple’s`xcodebuild`tool can list schemes and run build, test, archive,`build-for-testing`, and`test-without-building`actions from the terminal, which lets Codex stay in an agentic loop instead of bouncing into the Xcode GUI.

### Leverage XcodeBuildMCP

Use XcodeBuildMCP as soon as you are inside a full Xcode project and need deeper automation. That’s the point where schemes, targets, simulator control, screenshots, logs, and UI interaction matter enough that plain shell commands stop being the whole story.

## Tech stack

Need

Default options

Why it's needed

Need

UI framework

Default options

SwiftUI[SwiftUI](https://developer.apple.com/documentation/swiftui/)

Why it's needed

The fastest way to prototype views, navigation, and shared state for iPhone and iPad while keeping the UI code readable.

Need

Build tooling

Default options

xcodebuild orTuist[Tuist](https://docs.tuist.dev/)

Why it's needed

Both keep the native build loop in the terminal instead of depending on the Xcode GUI.

Need

Project automation

Default options

XcodeBuildMCP[XcodeBuildMCP](https://www.xcodebuildmcp.com/)

Why it's needed

A strong option once you need Codex to inspect schemes and targets, launch the app, capture screenshots, and keep iterating without leaving the agentic loop.

Need

Distribution tooling

Default options

App Store Connect CLI[App Store Connect CLI](https://asccli.sh/)

Why it's needed

Keep your agent fully in the loop and send your app build directly to the App Store.

Need | Default options | Why it's needed
UI framework | SwiftUI[SwiftUI](https://developer.apple.com/documentation/swiftui/) | The fastest way to prototype views, navigation, and shared state for iPhone and iPad while keeping the UI code readable.
Build tooling | xcodebuild orTuist[Tuist](https://docs.tuist.dev/) | Both keep the native build loop in the terminal instead of depending on the Xcode GUI.
Project automation | XcodeBuildMCP[XcodeBuildMCP](https://www.xcodebuildmcp.com/) | A strong option once you need Codex to inspect schemes and targets, launch the app, capture screenshots, and keep iterating without leaving the agentic loop.
Distribution tooling | App Store Connect CLI[App Store Connect CLI](https://asccli.sh/) | Keep your agent fully in the loop and send your app build directly to the App Store.

## Related use cases

### Add iOS app intents

Use Codex and the Build iOS Apps plugin to identify the actions and entities your app should...iOSCode[Add iOS app intentsUse Codex and the Build iOS Apps plugin to identify the actions and entities your app should...iOSCode](/codex/use-cases/ios-app-intents)

### Adopt liquid glass

Use Codex and the Build iOS Apps plugin to audit existing iPhone and iPad UI, replace custom...iOSCode[Adopt liquid glassUse Codex and the Build iOS Apps plugin to audit existing iPhone and iPad UI, replace custom...iOSCode](/codex/use-cases/ios-liquid-glass)

### Debug in iOS simulator

Use Codex to discover the right Xcode scheme and simulator, launch the app, inspect the UI...iOSCode[Debug in iOS simulatorUse Codex to discover the right Xcode scheme and simulator, launch the app, inspect the UI...iOSCode](/codex/use-cases/ios-simulator-bug-debugging)