# Source: https://developers.openai.com/codex/use-cases/react-native-expo-apps/

Codex use cases[Codex](/assets/OAI_Codex-Lockup_Fallback_Black.svg)

Codex use case

# Build React Native apps with Expo

Go from a mobile-app idea to a working Expo app with the dedicated plugin.Difficulty**Intermediate**Time horizon**1h**

Use Codex with the Expo plugin to scaffold React Native apps, stay inside Expo Router and Expo-native package conventions, test quickly with Expo Go, and move to dev clients or EAS builds only when the app needs them.

## Best for

- Developers who want to prototype or ship a React Native app with Expo before reaching for native IDE workflows.
- Expo Router projects where Codex should follow Expo conventions for routing, UI, package installs, builds, and deployment.
- Developers that need to migrate a web app to a mobile app.

# Contents
← All use cases[← All use cases](/codex/use-cases)Copy pageExport as PDF[Export as PDF](/codex/use-cases/react-native-expo-apps/?export=pdf)

Use Codex with the Expo plugin to scaffold React Native apps, stay inside Expo Router and Expo-native package conventions, test quickly with Expo Go, and move to dev clients or EAS builds only when the app needs them.Intermediate1h

Related linksExpo plugin[Expo plugin](https://docs.expo.dev/skills/)Expo MCP Server setup[Expo MCP Server setup](https://docs.expo.dev/eas/ai/mcp/)

## Best for

- Developers who want to prototype or ship a React Native app with Expo before reaching for native IDE workflows.
- Expo Router projects where Codex should follow Expo conventions for routing, UI, package installs, builds, and deployment.
- Developers that need to migrate a web app to a mobile app.

## Skills & Plugins

- Expo[Expo](https://docs.expo.dev/skills/)Use Expo-authored skills for Expo Router UI, native-feeling components, data fetching, dev clients, deployment, upgrades, modules, and Codex Run action wiring.

Skill | Why use it
Expo[Expo](https://docs.expo.dev/skills/) | Use Expo-authored skills for Expo Router UI, native-feeling components, data fetching, dev clients, deployment, upgrades, modules, and Codex Run action wiring.

## Starter promptUse the Expo plugin to build a React Native app with Expo for this idea: [describe the app idea, target users, and the main workflow] Requirements: - Start with Expo Router and Expo-native project conventions. - Try `npx expo start` and Expo Go first before creating a custom build. - Use `npx expo install` for Expo packages so dependencies stay compatible. - Use native-feeling UI patterns for navigation, forms, lists, empty states, and loading states. Deliver: - the working app slice - the run command - the verification path you used, including Expo Go, device, simulator, dev client, or EASOpen in the Codex app[Open in the Codex app](codex://threads/new?prompt=Use+the+Expo+plugin+to+build+a+React+Native+app+with+Expo+for+this+idea%3A%0A%0A%5Bdescribe+the+app+idea%2C+target+users%2C+and+the+main+workflow%5D%0A%0ARequirements%3A%0A-+Start+with+Expo+Router+and+Expo-native+project+conventions.%0A-+Try+%60npx+expo+start%60+and+Expo+Go+first+before+creating+a+custom+build.%0A-+Use+%60npx+expo+install%60+for+Expo+packages+so+dependencies+stay+compatible.%0A-+Use+native-feeling+UI+patterns+for+navigation%2C+forms%2C+lists%2C+empty+states%2C+and+loading+states.%0A%0ADeliver%3A%0A-+the+working+app+slice%0A-+the+run+command%0A-+the+verification+path+you+used%2C+including+Expo+Go%2C+device%2C+simulator%2C+dev+client%2C+or+EAS)Use the Expo plugin to build a React Native app with Expo for this idea: [describe the app idea, target users, and the main workflow] Requirements: - Start with Expo Router and Expo-native project conventions. - Try `npx expo start` and Expo Go first before creating a custom build. - Use `npx expo install` for Expo packages so dependencies stay compatible. - Use native-feeling UI patterns for navigation, forms, lists, empty states, and loading states. Deliver: - the working app slice - the run command - the verification path you used, including Expo Go, device, simulator, dev client, or EAS

## Start with Expo Go

Expo is a strong default when you want Codex to move from a mobile-app idea to a tested React Native app. The useful loop is`expo start`first, Expo Go on a device next, and then a dev client or EAS build only when the app needs custom native code, store distribution, or a capability that Expo Go can’t run.

That keeps Codex focused on the app workflow instead of spending the first pass on native IDE setup, simulator setup, provisioning, or build configuration.

## Use the Expo plugin

Expo published anExpo plugin[Expo plugin](https://docs.expo.dev/skills/)that gives Codex Expo-native guidance for Expo Router, native UI, forms, navigation, animations, data fetching, NativeWind setup, Expo modules, dev clients, deployment, upgrades, and Codex Run action wiring.

Use it when Codex is building new Expo screens, adding packages, wiring API calls, preparing a dev client, or getting an app ready for TestFlight, App Store, Play Store, or EAS Hosting.

Optionally, add theExpo MCP Server[Expo MCP Server](https://docs.expo.dev/eas/ai/mcp/)when the task needs current Expo documentation lookup, compatible package installation, EAS build and workflow operations, screenshots, simulator interaction, React Native DevTools, or TestFlight data.

## Iteration process

- Ask Codex to inspect the repo and confirm whether it is a new Expo app or an existing Expo project.
- Start with Expo Router and Expo Go, and use`npx expo install`when adding Expo packages.
- Ask Codex to build one complete workflow with native-feeling navigation, loading states, empty states, and error states.
- Verify on the fastest available path, such as Expo Go on a device or a simulator, then move to a dev client or EAS only when needed.

## Suggested follow-up promptUse the Expo plugin to add the following [feature/screen/flow] to this app: [describe one feature, screen or user flow] Constraints: - Keep Expo Router as the routing layer. - Use Expo-compatible package installs. - Test with Expo Go first. - Move to dev client or EAS only if this feature requires it. After implementing, tell me the exact run path you used and what you verified.

## Tech stack

Need

Default options

Why it's needed

Need

Mobile framework

Default options

Expo[Expo](https://expo.dev/)andReact Native[React Native](https://reactnative.dev/)

Why it's needed

Expo gives Codex a managed React Native path with fast iteration, compatible packages, and deployment tooling.

Need

Routing

Default options

Expo Router[Expo Router](https://docs.expo.dev/router/introduction/)

Why it's needed

Expo Router keeps navigation file-based and predictable, which helps Codex add screens and flows without inventing a custom routing layer.

Need | Default options | Why it's needed
Mobile framework | Expo[Expo](https://expo.dev/)andReact Native[React Native](https://reactnative.dev/) | Expo gives Codex a managed React Native path with fast iteration, compatible packages, and deployment tooling.
Routing | Expo Router[Expo Router](https://docs.expo.dev/router/introduction/) | Expo Router keeps navigation file-based and predictable, which helps Codex add screens and flows without inventing a custom routing layer.

## Related use cases

### Get from idea to proof of concept

Use Codex with ImageGen to turn a rough idea into a visual direction, implement the smallest...Front-endEngineering[Get from idea to proof of conceptUse Codex with ImageGen to turn a rough idea into a visual direction, implement the smallest...Front-endEngineering](/codex/use-cases/idea-to-proof-of-concept)

### Create browser-based games

Use Codex to turn a game brief into first a well-defined plan, and then a real browser-based...EngineeringCode[Create browser-based gamesUse Codex to turn a game brief into first a well-defined plan, and then a real browser-based...EngineeringCode](/codex/use-cases/browser-games)

### Add iOS app intents

Use Codex and the Build iOS Apps plugin to identify the actions and entities your app should...iOSCode[Add iOS app intentsUse Codex and the Build iOS Apps plugin to identify the actions and entities your app should...iOSCode](/codex/use-cases/ios-app-intents)