# Source: https://developers.openai.com/codex/use-cases/ios-liquid-glass/

Codex use cases[Codex](/assets/OAI_Codex-Lockup_Fallback_Black.svg)

Codex use case

# Adopt liquid glass

Use Codex to migrate an existing SwiftUI app to Liquid Glass with iOS 26 APIs and Xcode 26.Difficulty**Advanced**Time horizon**1h**

Use Codex and the Build iOS Apps plugin to audit existing iPhone and iPad UI, replace custom blur or material stacks with native Liquid Glass, and keep the migration safe with iOS 26 availability checks and simulator-driven validation.

## Best for

- Existing SwiftUI apps that need a practical iOS 26 Liquid Glass migration plan, not a vague redesign brief
- Teams that want Codex to audit custom cards, sheets, tab bars, toolbars, and action buttons and then implement the migration slice by slice
- Apps that still support older iOS versions and need `#available(iOS 26, *)` fallbacks instead of a one-way visual rewrite

# Contents
← All use cases[← All use cases](/codex/use-cases)Copy pageExport as PDF[Export as PDF](/codex/use-cases/ios-liquid-glass/?export=pdf)

Use Codex and the Build iOS Apps plugin to audit existing iPhone and iPad UI, replace custom blur or material stacks with native Liquid Glass, and keep the migration safe with iOS 26 availability checks and simulator-driven validation.Advanced1h

Related linksCodex plugins[Codex plugins](/codex/plugins)Agent skills[Agent skills](/codex/skills)

## Best for

- Existing SwiftUI apps that need a practical iOS 26 Liquid Glass migration plan, not a vague redesign brief
- Teams that want Codex to audit custom cards, sheets, tab bars, toolbars, and action buttons and then implement the migration slice by slice
- Apps that still support older iOS versions and need `#available(iOS 26, *)` fallbacks instead of a one-way visual rewrite

## Skills & Plugins

- Build iOS Apps[Build iOS Apps](https://github.com/openai/plugins/tree/main/plugins/build-ios-apps)Use the SwiftUI Liquid Glass, SwiftUI UI patterns, and simulator debugging skills to modernize iOS screens, adopt native glass effects, and verify the result on iOS 26 simulators.

Skill | Why use it
Build iOS Apps[Build iOS Apps](https://github.com/openai/plugins/tree/main/plugins/build-ios-apps) | Use the SwiftUI Liquid Glass, SwiftUI UI patterns, and simulator debugging skills to modernize iOS screens, adopt native glass effects, and verify the result on iOS 26 simulators.

## Starter promptUse the Build iOS Apps plugin and its SwiftUI Liquid Glass skill to migrate one high-traffic flow in this app to Liquid Glass. Constraints: - Treat this as an iOS 26 + Xcode 26 migration, but preserve a non-glass fallback for earlier deployment targets with `#available(iOS 26, *)`. - Audit the flow first. Call out custom backgrounds, blur stacks, chips, buttons, sheets, and toolbars that should become native Liquid Glass and call out surfaces that should stay plain content. - Prefer system controls and native APIs like `glassEffect`, `GlassEffectContainer`, `glassEffectID`, `.buttonStyle(.glass)`, and `.buttonStyle(.glassProminent)` over custom blurs. Use `glassEffectID` with `@Namespace` only when a real morphing transition improves the flow. - Apply `glassEffect` after layout and visual modifiers, keep shapes consistent, and use `.interactive()` only on controls that actually respond to touch. - Use XcodeBuildMCP to build and run on an iOS 26 simulator, capture screenshots for the migrated flow, and mention exactly which scheme, simulator, and checks you used. Deliver: - a concise migration plan for the flow - the implemented Liquid Glass slice - the fallback behavior for pre-iOS 26 devices - the simulator validation steps and screenshots you usedOpen in the Codex app[Open in the Codex app](codex://threads/new?prompt=Use+the+Build+iOS+Apps+plugin+and+its+SwiftUI+Liquid+Glass+skill+to+migrate+one+high-traffic+flow+in+this+app+to+Liquid+Glass.%0A%0AConstraints%3A%0A-+Treat+this+as+an+iOS+26+%2B+Xcode+26+migration%2C+but+preserve+a+non-glass+fallback+for+earlier+deployment+targets+with+%60%23available%28iOS+26%2C+*%29%60.%0A-+Audit+the+flow+first.+Call+out+custom+backgrounds%2C+blur+stacks%2C+chips%2C+buttons%2C+sheets%2C+and+toolbars+that+should+become+native+Liquid+Glass+and+call+out+surfaces+that+should+stay+plain+content.%0A-+Prefer+system+controls+and+native+APIs+like+%60glassEffect%60%2C+%60GlassEffectContainer%60%2C+%60glassEffectID%60%2C+%60.buttonStyle%28.glass%29%60%2C+and+%60.buttonStyle%28.glassProminent%29%60+over+custom+blurs.+Use+%60glassEffectID%60+with+%60%40Namespace%60+only+when+a+real+morphing+transition+improves+the+flow.%0A-+Apply+%60glassEffect%60+after+layout+and+visual+modifiers%2C+keep+shapes+consistent%2C+and+use+%60.interactive%28%29%60+only+on+controls+that+actually+respond+to+touch.%0A-+Use+XcodeBuildMCP+to+build+and+run+on+an+iOS+26+simulator%2C+capture+screenshots+for+the+migrated+flow%2C+and+mention+exactly+which+scheme%2C+simulator%2C+and+checks+you+used.%0A%0ADeliver%3A%0A-+a+concise+migration+plan+for+the+flow%0A-+the+implemented+Liquid+Glass+slice%0A-+the+fallback+behavior+for+pre-iOS+26+devices%0A-+the+simulator+validation+steps+and+screenshots+you+used)Use the Build iOS Apps plugin and its SwiftUI Liquid Glass skill to migrate one high-traffic flow in this app to Liquid Glass. Constraints: - Treat this as an iOS 26 + Xcode 26 migration, but preserve a non-glass fallback for earlier deployment targets with `#available(iOS 26, *)`. - Audit the flow first. Call out custom backgrounds, blur stacks, chips, buttons, sheets, and toolbars that should become native Liquid Glass and call out surfaces that should stay plain content. - Prefer system controls and native APIs like `glassEffect`, `GlassEffectContainer`, `glassEffectID`, `.buttonStyle(.glass)`, and `.buttonStyle(.glassProminent)` over custom blurs. Use `glassEffectID` with `@Namespace` only when a real morphing transition improves the flow. - Apply `glassEffect` after layout and visual modifiers, keep shapes consistent, and use `.interactive()` only on controls that actually respond to touch. - Use XcodeBuildMCP to build and run on an iOS 26 simulator, capture screenshots for the migrated flow, and mention exactly which scheme, simulator, and checks you used. Deliver: - a concise migration plan for the flow - the implemented Liquid Glass slice - the fallback behavior for pre-iOS 26 devices - the simulator validation steps and screenshots you used

## Start from the iOS 26 baseline

Treat Liquid Glass as an iOS 26 and Xcode 26 migration project first. Rebuild the app with the iOS 26 SDK, inspect what you get automatically from standard SwiftUI controls, and only then ask Codex to redesign the custom parts that still look too flat, too heavy, or too detached from system chrome.

If the app still supports earlier iOS versions, make that constraint explicit up front. The SwiftUI Liquid Glass skill in theBuild iOS Apps plugin[Build iOS Apps plugin](https://github.com/openai/plugins/tree/main/plugins/build-ios-apps)should gate new glass-only APIs with`#available(iOS 26, *)`and keep a fallback path that still reads well on older devices.

## Leverage the iOS plugin

Use theBuild iOS Apps plugin[Build iOS Apps plugin](https://github.com/openai/plugins/tree/main/plugins/build-ios-apps)when you want Codex to combine SwiftUI UI changes with simulator-backed verification. For Liquid Glass work, the useful move is to ask Codex to audit one flow, migrate a small set of surfaces, launch the result on an iOS 26 simulator, and capture screenshots before expanding the scope.

That plugin includes a SwiftUI Liquid Glass skill with a simple set of defaults worth carrying into your prompt:

- Prefer native`glassEffect`,`GlassEffectContainer`, glass button styles, and`glassEffectID`transitions over custom blur views.
- Apply`.glassEffect(...)`after layout and visual modifiers so the material wraps the final shape you actually want.
- Wrap related glass elements in`GlassEffectContainer`when multiple surfaces appear together.
- Use`.interactive()`only on buttons, chips, and controls that actually respond to touch.
- Keep corner shapes, tinting, and spacing consistent across the feature instead of mixing one-off glass treatments.
- Preserve a non-glass fallback for pre-iOS 26 targets.

To learn more about installing plugins and skills, see ourplugins[plugins](/codex/plugins)andskills[skills](/codex/skills)docs.

## Watch the WWDC sessions

These WWDC25 sessions are a good reference set before you ask Codex to refactor a real production flow:

- Meet Liquid Glass[Meet Liquid Glass](https://developer.apple.com/videos/play/wwdc2025/219/)
- Get to know the new design system[Get to know the new design system](https://developer.apple.com/videos/play/wwdc2025/356/)
- Build a SwiftUI app with the new design[Build a SwiftUI app with the new design](https://developer.apple.com/videos/play/wwdc2025/323/)
- Build a UIKit app with the new design[Build a UIKit app with the new design](https://developer.apple.com/videos/play/wwdc2025/284/)
- What’s new in SwiftUI[What’s new in SwiftUI](https://developer.apple.com/videos/play/wwdc2025/256/)

## Prompt a migration plan, then a slice

Liquid Glass migrations go better when Codex separates “where should glass appear?” from “write all the code now.” Ask for a quick audit first, then let the agent implement one self-contained slice with simulator verification.

## Practical tips

### Do not glass everything

Liquid Glass should create a clear control layer above content, not turn every card into a glowing panel. Ask Codex to remove decorative backgrounds that fight system materials, preserve plain content where readability matters most, and reserve tinting for semantic emphasis or primary actions.

### Start with one high-traffic flow

A tab root, detail screen, sheet, search surface, or onboarding flow is usually a better first migration target than a full app-wide sweep. That keeps review easier and makes it clear which Liquid Glass decisions should become reusable component patterns.

### Review fallback behavior deliberately

If your deployment target is below iOS 26, ask Codex to show the fallback implementation alongside the Liquid Glass version. That review step catches accidental API availability regressions and avoids shipping a migration that only works on the latest simulator.

## Tech stack

Need

Default options

Why it's needed

Need

Liquid Glass UI APIs

Default options

SwiftUI[SwiftUI](https://developer.apple.com/documentation/swiftui/)with`glassEffect`,`GlassEffectContainer`, and glass button styles

Why it's needed

These are the native APIs the skill should reach for first, so Codex removes custom blur layers instead of reinventing the material system.

Need

Platform baseline

Default options

iOS 26 and Xcode 26

Why it's needed

Liquid Glass lands with the iOS 26 SDK. Codex should compile with Xcode 26 and add explicit fallbacks for earlier OS support.

Need

Simulator validation

Default options

XcodeBuildMCP[XcodeBuildMCP](https://www.xcodebuildmcp.com/)

Why it's needed

Build, launch, screenshot, and log inspection matter during a visual migration, especially when reviewing multiple states and device sizes.

Need | Default options | Why it's needed
Liquid Glass UI APIs | SwiftUI[SwiftUI](https://developer.apple.com/documentation/swiftui/)with`glassEffect`,`GlassEffectContainer`, and glass button styles | These are the native APIs the skill should reach for first, so Codex removes custom blur layers instead of reinventing the material system.
Platform baseline | iOS 26 and Xcode 26 | Liquid Glass lands with the iOS 26 SDK. Codex should compile with Xcode 26 and add explicit fallbacks for earlier OS support.
Simulator validation | XcodeBuildMCP[XcodeBuildMCP](https://www.xcodebuildmcp.com/) | Build, launch, screenshot, and log inspection matter during a visual migration, especially when reviewing multiple states and device sizes.

## Related use cases

### Add iOS app intents

Use Codex and the Build iOS Apps plugin to identify the actions and entities your app should...iOSCode[Add iOS app intentsUse Codex and the Build iOS Apps plugin to identify the actions and entities your app should...iOSCode](/codex/use-cases/ios-app-intents)

### Build a Mac app shell

Use Codex and the Build macOS Apps plugin to turn an app idea into a desktop-native...macOSCode[Build a Mac app shellUse Codex and the Build macOS Apps plugin to turn an app idea into a desktop-native...macOSCode](/codex/use-cases/macos-sidebar-detail-inspector)

### Build for iOS

Use Codex to scaffold iOS SwiftUI projects, keep the build loop CLI-first with `xcodebuild`...iOSCode[Build for iOSUse Codex to scaffold iOS SwiftUI projects, keep the build loop CLI-first with `xcodebuild`...iOSCode](/codex/use-cases/native-ios-apps)