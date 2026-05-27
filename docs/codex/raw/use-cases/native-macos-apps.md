# Source: https://developers.openai.com/codex/use-cases/native-macos-apps/

Codex use cases[Codex](/assets/OAI_Codex-Lockup_Fallback_Black.svg)

Codex use case

# Build for macOS

Use Codex to scaffold, build, and debug native Mac apps with SwiftUI.Difficulty**Advanced**Time horizon**1h**

Use Codex to build macOS SwiftUI apps, wire a shell-first build-and-run loop, and add desktop-native scene, window, AppKit, and signing workflows as the app matures.

## Best for

- Greenfield macOS SwiftUI apps where you want Codex to scaffold a desktop-native app shell and repeatable build script
- Existing Mac apps where Codex needs to work on windows, menus, sidebars, settings, AppKit interop, or signing issues
- Teams that want macOS work to stay shell-first while still respecting native desktop UX conventions

# Contents
← All use cases[← All use cases](/codex/use-cases)Copy pageExport as PDF[Export as PDF](/codex/use-cases/native-macos-apps/?export=pdf)

Use Codex to build macOS SwiftUI apps, wire a shell-first build-and-run loop, and add desktop-native scene, window, AppKit, and signing workflows as the app matures.Advanced1h

Related linksModel Context Protocol[Model Context Protocol](/codex/mcp)Agent skills[Agent skills](/codex/skills)

## Best for

- Greenfield macOS SwiftUI apps where you want Codex to scaffold a desktop-native app shell and repeatable build script
- Existing Mac apps where Codex needs to work on windows, menus, sidebars, settings, AppKit interop, or signing issues
- Teams that want macOS work to stay shell-first while still respecting native desktop UX conventions

## Skills & Plugins

- Build macOS Apps[Build macOS Apps](https://github.com/openai/plugins/tree/main/plugins/build-macos-apps)Build and debug macOS apps with shell-first workflows, design desktop-native SwiftUI scenes and windows, bridge to AppKit where needed, and prepare signing and notarization paths.

Skill | Why use it
Build macOS Apps[Build macOS Apps](https://github.com/openai/plugins/tree/main/plugins/build-macos-apps) | Build and debug macOS apps with shell-first workflows, design desktop-native SwiftUI scenes and windows, bridge to AppKit where needed, and prepare signing and notarization paths.

## Starter promptUse the Build macOS Apps plugin to scaffold a starter macOS SwiftUI app and add a project-local `script/build_and_run.sh` entrypoint I can wire to a `Run` action. Constraints: - Stay shell-first. Prefer `xcodebuild` for Xcode projects and `swift build` for package-first apps. - Model Mac scenes explicitly with a main window plus `Settings`, `MenuBarExtra`, or utility windows only when they fit the product. - Prefer desktop-native sidebars, toolbars, menus, keyboard shortcuts, and system materials over iOS-style push navigation. - Use a narrow AppKit bridge only when SwiftUI cannot express the desktop behavior cleanly. - Keep one small validation loop for each change and tell me exactly which build, launch, or log commands you ran. Deliver: - the app scaffold or requested Mac feature slice - a reusable build-and-run script - the smallest validation steps you ran - any desktop-specific follow-up work you recommendOpen in the Codex app[Open in the Codex app](codex://threads/new?prompt=Use+the+Build+macOS+Apps+plugin+to+scaffold+a+starter+macOS+SwiftUI+app+and+add+a+project-local+%60script%2Fbuild_and_run.sh%60+entrypoint+I+can+wire+to+a+%60Run%60+action.%0A%0AConstraints%3A%0A-+Stay+shell-first.+Prefer+%60xcodebuild%60+for+Xcode+projects+and+%60swift+build%60+for+package-first+apps.%0A-+Model+Mac+scenes+explicitly+with+a+main+window+plus+%60Settings%60%2C+%60MenuBarExtra%60%2C+or+utility+windows+only+when+they+fit+the+product.%0A-+Prefer+desktop-native+sidebars%2C+toolbars%2C+menus%2C+keyboard+shortcuts%2C+and+system+materials+over+iOS-style+push+navigation.%0A-+Use+a+narrow+AppKit+bridge+only+when+SwiftUI+cannot+express+the+desktop+behavior+cleanly.%0A-+Keep+one+small+validation+loop+for+each+change+and+tell+me+exactly+which+build%2C+launch%2C+or+log+commands+you+ran.%0A%0ADeliver%3A%0A-+the+app+scaffold+or+requested+Mac+feature+slice%0A-+a+reusable+build-and-run+script%0A-+the+smallest+validation+steps+you+ran%0A-+any+desktop-specific+follow-up+work+you+recommend)Use the Build macOS Apps plugin to scaffold a starter macOS SwiftUI app and add a project-local `script/build_and_run.sh` entrypoint I can wire to a `Run` action. Constraints: - Stay shell-first. Prefer `xcodebuild` for Xcode projects and `swift build` for package-first apps. - Model Mac scenes explicitly with a main window plus `Settings`, `MenuBarExtra`, or utility windows only when they fit the product. - Prefer desktop-native sidebars, toolbars, menus, keyboard shortcuts, and system materials over iOS-style push navigation. - Use a narrow AppKit bridge only when SwiftUI cannot express the desktop behavior cleanly. - Keep one small validation loop for each change and tell me exactly which build, launch, or log commands you ran. Deliver: - the app scaffold or requested Mac feature slice - a reusable build-and-run script - the smallest validation steps you ran - any desktop-specific follow-up work you recommend

## Scaffold the app and build loop

For a new Mac app, ask Codex to choose the right scene model first:`WindowGroup`,`Window`,`Settings`,`MenuBarExtra`, or`DocumentGroup`. That keeps the app desktop-native from the first pass instead of growing from an iOS-style`ContentView`.

Keep the execution loop shell-first. For Xcode projects, use`xcodebuild`. For package-first apps, use`swift build`and a project-local`script/build_and_run.sh`wrapper that stops the old process, builds the app, launches the new artifact, and can optionally expose logs or telemetry.

If a pure SwiftPM app is a GUI app, bundle and launch it as a`.app`instead of running the raw executable directly. That avoids missing Dock, activation, and bundle-identity issues during local validation.

## Leverage skills

Add theBuild macOS Apps plugin[Build macOS Apps plugin](https://github.com/openai/plugins/tree/main/plugins/build-macos-apps)once the work gets more desktop-specific. It covers shell-first build and debug loops, SwiftPM app packaging, native SwiftUI scene and window patterns, AppKit interop, unified logging, test triage, and signing/notarization workflows.

To learn more about how to install and use plugins and skills, see theCodex plugins documentation[Codex plugins documentation](/codex/plugins)andskills documentation[skills documentation](/codex/skills).

## Build desktop-native UI

Prefer Mac conventions over iOS navigation patterns. Use`NavigationSplitView`for sidebar/detail layouts, explicit`Settings`scenes for preferences, toolbars and commands for discoverable actions, and menu bar extras for lightweight always-available utilities.

Use system materials, semantic colors, and standard controls first. Add custom window styling, drag regions, or Liquid Glass surfaces only when the product needs a distinct desktop surface.

If SwiftUI gets close but not all the way there, add the smallest possible AppKit bridge. Good examples are open/save panels, first-responder control, menu validation, drag-and-drop edges, and a wrapped`NSView`for one specialized control.

## Debug, test, and prepare for shipping

For runtime behavior, ask Codex to add a few`Logger`events around window opening, sidebar selection, menu commands, or background sync, then verify those events with`log stream`after the app launches.

For failing tests, have Codex run the smallest useful`xcodebuild test`or`swift test`scope first and classify whether the issue is compilation, an assertion failure, a crash, a flake, or an environment/setup problem.

When the work shifts from local iteration to distribution, ask Codex to prepare both a manual archive path in Xcode and a script-based archive and notarization path for repeatable shipping. Have it inspect the app bundle, entitlements, and hardened runtime with`codesign`and`plutil`, and useApp Store Connect CLI[App Store Connect CLI](https://asccli.sh/)when you want uploads to stay in the terminal too.

## Example promptUse the Build macOS Apps plugin to build a native macOS SwiftUI version of this app feature. Constraints: - Use a desktop-native scene structure with a main window, settings, and toolbar/command actions where they make sense. - Prefer a sidebar/detail layout over iOS-style push navigation if the feature benefits from always-visible structure. - Add a tiny AppKit bridge only if SwiftUI cannot express one specific desktop behavior cleanly. - Create or update `script/build_and_run.sh` so the build/run loop stays shell-first. - Tell me which build, launch, test, and log commands you used. Ship the feature slice, verify it with the smallest relevant build or test loop, and summarize any signing or packaging follow-up needed before distribution.

## Practical tips

### Keep scenes explicit

Model the main window, settings window, utility windows, and menu bar extras as separate scene roots instead of hiding the whole app inside one giant view.

### Let system chrome do more of the work

Before creating custom sidebars, toolbars, or materials, check whether standard SwiftUI scene and window APIs already give you the Mac behavior you want.

### Treat AppKit as a narrow edge

Use`NSViewRepresentable`,`NSViewControllerRepresentable`, or a focused`NSWindow`helper for one missing desktop capability, but keep SwiftUI as the source of truth for selection and app state.

### Validate signing and notarization separately from local build success

A successful local launch does not prove the app is signed or notarization-ready. Keep a manual Xcode archive flow for one-off release checks, add a scripted archive and notarization flow for repeatable distribution, and run`codesign`and`plutil`checks when the task is about shipping, not just local iteration.

## Tech stack

Need

Default options

Why it's needed

Need

UI framework

Default options

SwiftUI[SwiftUI](https://developer.apple.com/documentation/swiftui/)

Why it's needed

A strong default for windows, sidebars, toolbars, settings, and scene-driven Mac app structure.

Need

AppKit bridge

Default options

AppKit[AppKit](https://developer.apple.com/documentation/appkit)

Why it's needed

Use small`NSViewRepresentable`,`NSViewControllerRepresentable`, or`NSWindow`bridges when SwiftUI stops short of a desktop behavior you need.

Need

Build and packaging

Default options

`xcodebuild`,`swift build`, andApp Store Connect CLI[App Store Connect CLI](https://asccli.sh/)

Why it's needed

Keep local builds, manual archives, script-based notarization, and App Store uploads in a repeatable terminal-first loop.

Need | Default options | Why it's needed
UI framework | SwiftUI[SwiftUI](https://developer.apple.com/documentation/swiftui/) | A strong default for windows, sidebars, toolbars, settings, and scene-driven Mac app structure.
AppKit bridge | AppKit[AppKit](https://developer.apple.com/documentation/appkit) | Use small`NSViewRepresentable`,`NSViewControllerRepresentable`, or`NSWindow`bridges when SwiftUI stops short of a desktop behavior you need.
Build and packaging | `xcodebuild`,`swift build`, andApp Store Connect CLI[App Store Connect CLI](https://asccli.sh/) | Keep local builds, manual archives, script-based notarization, and App Store uploads in a repeatable terminal-first loop.

## Related use cases

### Build a Mac app shell

Use Codex and the Build macOS Apps plugin to turn an app idea into a desktop-native...macOSCode[Build a Mac app shellUse Codex and the Build macOS Apps plugin to turn an app idea into a desktop-native...macOSCode](/codex/use-cases/macos-sidebar-detail-inspector)

### Add iOS app intents

Use Codex and the Build iOS Apps plugin to identify the actions and entities your app should...iOSCode[Add iOS app intentsUse Codex and the Build iOS Apps plugin to identify the actions and entities your app should...iOSCode](/codex/use-cases/ios-app-intents)

### Add Mac telemetry

Use Codex and the Build macOS Apps plugin to add a few high-signal `Logger` events around...macOSCode[Add Mac telemetryUse Codex and the Build macOS Apps plugin to add a few high-signal `Logger` events around...macOSCode](/codex/use-cases/macos-telemetry-logs)