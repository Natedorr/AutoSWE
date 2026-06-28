# Source: https://developers.openai.com/codex/use-cases/ios-app-intents/

Codex use cases[Codex](/assets/OAI_Codex-Lockup_Fallback_Black.svg)

Codex use case

# Add iOS app intents

Use Codex to make your app's actions and content available to Shortcuts, Siri, Spotlight, and newer assistant-driven system experiences.Difficulty**Advanced**Time horizon**1h**

Use Codex and the Build iOS Apps plugin to identify the actions and entities your app should expose through App Intents, wire them into system surfaces like Shortcuts and Spotlight, and prepare your app for more assistant-driven workflows over time.

## Best for

- iOS apps that already have useful actions or content but are still invisible to Shortcuts, Siri, Spotlight, or the wider system
- Teams that want to expose a few high-value actions now and build toward more assistant-friendly workflows over time
- Apps with clear objects like accounts, lists, filters, destinations, drafts, or media that can become app entities instead of staying locked inside the UI

# Contents
← All use cases[← All use cases](/codex/use-cases)Copy pageExport as PDF[Export as PDF](/codex/use-cases/ios-app-intents/?export=pdf)

Use Codex and the Build iOS Apps plugin to identify the actions and entities your app should expose through App Intents, wire them into system surfaces like Shortcuts and Spotlight, and prepare your app for more assistant-driven workflows over time.Advanced1h

Related linksApp Intents overview[App Intents overview](https://developer.apple.com/documentation/appintents/making-actions-and-content-discoverable-and-widely-available)Apple system experiences sample[Apple system experiences sample](https://developer.apple.com/documentation/appintents/adopting-app-intents-to-support-system-experiences)

## Best for

- iOS apps that already have useful actions or content but are still invisible to Shortcuts, Siri, Spotlight, or the wider system
- Teams that want to expose a few high-value actions now and build toward more assistant-friendly workflows over time
- Apps with clear objects like accounts, lists, filters, destinations, drafts, or media that can become app entities instead of staying locked inside the UI

## Skills & Plugins

- Build iOS Apps[Build iOS Apps](https://github.com/openai/plugins/tree/main/plugins/build-ios-apps)Use the iOS build and SwiftUI skills to add App Intents, app entities, and App Shortcuts, then validate that the app still builds and routes intent-driven entry points correctly.

Skill | Why use it
Build iOS Apps[Build iOS Apps](https://github.com/openai/plugins/tree/main/plugins/build-ios-apps) | Use the iOS build and SwiftUI skills to add App Intents, app entities, and App Shortcuts, then validate that the app still builds and routes intent-driven entry points correctly.

## Starter promptUse the Build iOS Apps plugin to audit this iOS app and add App Intents for the actions and entities that should be exposed to the system. Constraints: - Start by identifying the app's highest-value user actions and core objects that should be available outside the app in Shortcuts, Siri, Spotlight, widgets, controls, or newer assistant-driven system surfaces. - Keep the first pass focused. Pick a small set of intents that are genuinely useful without opening the full app, plus any open-app intents that should deep-link into a specific screen or workflow. - Define app entities only for the data the system actually needs to understand and route those actions. Do not mirror the entire internal model layer if a smaller entity surface is enough. - Add App Shortcuts where they make the experience more discoverable, and choose titles, phrases, and display representations that would make sense in Siri, Spotlight, and Shortcuts. - If the app needs to handle the intent inside the main UI, route the result back into the app cleanly and explain how the app scene reacts to that handoff. - Build and validate the app after the first pass, then summarize which actions, entities, and system surfaces are now supported. Deliver: - the recommended intent and entity surface for a first release - the implemented intents, entities, and App Shortcuts - how the app routes or handles those intents at runtime - which Apple system experiences this unlocks now and which ones are logical next stepsOpen in the Codex app[Open in the Codex app](codex://threads/new?prompt=Use+the+Build+iOS+Apps+plugin+to+audit+this+iOS+app+and+add+App+Intents+for+the+actions+and+entities+that+should+be+exposed+to+the+system.%0A%0AConstraints%3A%0A-+Start+by+identifying+the+app%27s+highest-value+user+actions+and+core+objects+that+should+be+available+outside+the+app+in+Shortcuts%2C+Siri%2C+Spotlight%2C+widgets%2C+controls%2C+or+newer+assistant-driven+system+surfaces.%0A-+Keep+the+first+pass+focused.+Pick+a+small+set+of+intents+that+are+genuinely+useful+without+opening+the+full+app%2C+plus+any+open-app+intents+that+should+deep-link+into+a+specific+screen+or+workflow.%0A-+Define+app+entities+only+for+the+data+the+system+actually+needs+to+understand+and+route+those+actions.+Do+not+mirror+the+entire+internal+model+layer+if+a+smaller+entity+surface+is+enough.%0A-+Add+App+Shortcuts+where+they+make+the+experience+more+discoverable%2C+and+choose+titles%2C+phrases%2C+and+display+representations+that+would+make+sense+in+Siri%2C+Spotlight%2C+and+Shortcuts.%0A-+If+the+app+needs+to+handle+the+intent+inside+the+main+UI%2C+route+the+result+back+into+the+app+cleanly+and+explain+how+the+app+scene+reacts+to+that+handoff.%0A-+Build+and+validate+the+app+after+the+first+pass%2C+then+summarize+which+actions%2C+entities%2C+and+system+surfaces+are+now+supported.%0A%0ADeliver%3A%0A-+the+recommended+intent+and+entity+surface+for+a+first+release%0A-+the+implemented+intents%2C+entities%2C+and+App+Shortcuts%0A-+how+the+app+routes+or+handles+those+intents+at+runtime%0A-+which+Apple+system+experiences+this+unlocks+now+and+which+ones+are+logical+next+steps)Use the Build iOS Apps plugin to audit this iOS app and add App Intents for the actions and entities that should be exposed to the system. Constraints: - Start by identifying the app's highest-value user actions and core objects that should be available outside the app in Shortcuts, Siri, Spotlight, widgets, controls, or newer assistant-driven system surfaces. - Keep the first pass focused. Pick a small set of intents that are genuinely useful without opening the full app, plus any open-app intents that should deep-link into a specific screen or workflow. - Define app entities only for the data the system actually needs to understand and route those actions. Do not mirror the entire internal model layer if a smaller entity surface is enough. - Add App Shortcuts where they make the experience more discoverable, and choose titles, phrases, and display representations that would make sense in Siri, Spotlight, and Shortcuts. - If the app needs to handle the intent inside the main UI, route the result back into the app cleanly and explain how the app scene reacts to that handoff. - Build and validate the app after the first pass, then summarize which actions, entities, and system surfaces are now supported. Deliver: - the recommended intent and entity surface for a first release - the implemented intents, entities, and App Shortcuts - how the app routes or handles those intents at runtime - which Apple system experiences this unlocks now and which ones are logical next steps

## Make the right parts of your app visible to the system

App Intents are one of the clearest ways to make an iOS app more useful outside its own UI. Instead of treating your app as a sealed destination that only works after someone launches it and taps around, use Codex to expose the actions and objects that should be available to Shortcuts, Siri, Spotlight, widgets, controls, and newer assistant-driven system experiences.

That is useful today for discoverability and automation, and it is a strong preparation step for a more assistant-driven future. If your app already knows how to compose, open, filter, route, or summarize something valuable, App Intents give the system a structured way to ask for that capability.

## Start with actions and entities, not with every screen

The best first App Intents pass is usually not “mirror the whole app.” Ask Codex to identify:

- the few actions a user would want to trigger without navigating the full interface
- the app objects the system needs to understand to route those actions correctly
- the workflows that should open the app in a specific state versus the ones that should complete directly from a system surface

Apple’s App Intents guidance is a good frame here: define the action, define the entity surface the system needs, then make those actions discoverable and reusable across system experiences. The most useful references areMaking actions and content discoverable and widely available[Making actions and content discoverable and widely available](https://developer.apple.com/documentation/appintents/making-actions-and-content-discoverable-and-widely-available),Creating your first app intent[Creating your first app intent](https://developer.apple.com/documentation/appintents/creating-your-first-app-intent), and the system-experience sampleAdopting App Intents to support system experiences[Adopting App Intents to support system experiences](https://developer.apple.com/documentation/appintents/adopting-app-intents-to-support-system-experiences).

## Think in system surfaces, not just in shortcuts

The opportunity is broader than “add one shortcut.” A good App Intents surface can make your app useful in several places:

- Shortcuts, where users can run actions directly or compose them into larger automations
- Siri, where the app can expose meaningful verbs and deep links instead of only opening generically
- Spotlight, where app entities and app shortcuts become discoverable system entry points
- widgets, Live Activities, controls, and other intent-driven UI surfaces
- newer assistant-facing experiences, where structured actions and entities are much easier for the system to understand than arbitrary UI flows

## Follow a real app pattern

This usually works best when the app adopts a structure like this:

- a dedicated App Intents target instead of scattering intent types across unrelated app files
- `AppShortcutsProvider`entries for high-value user actions like composing a post or opening the app on a specific tab
- small`AppEntity`types for things the system needs to reason about, such as accounts, lists, and timeline filters
- intent handling that routes back into the main app scene cleanly, so an invoked intent can open the right compose flow or switch the app to the right tab

That is the pattern I would ask Codex to follow for most apps: start with a small system-facing action layer, keep the entity surface narrow, and wire a predictable runtime handoff back into the app when the intent needs the main UI.

## Ask Codex to design the first intent surface

The strongest prompt here is one that gives Codex your app’s core objects and top user actions, then asks it to choose the smallest useful first App Intents surface instead of blindly exposing everything.

## Practical tips

### Expose verbs users actually want outside the app

Good first intents are usually things like compose, open, find, filter, start, continue, or inspect. If an action is only useful after a long in-app setup flow, it may not belong in the first App Intents pass.

### Keep entities smaller than your model layer

The system usually does not need your full persistence model. Ask Codex to define the smallest app entity surface that still gives Siri, Shortcuts, and Spotlight enough context to route and display the action correctly.

### Treat this as assistant infrastructure, not only a shortcuts feature

Even if your first release only visibly improves Shortcuts or Siri, the deeper win is that your app starts speaking in structured actions and entities. That makes it easier to participate in future system and AI-driven entry points than an app whose capabilities are only encoded in taps and view hierarchies.

## Tech stack

Need

Default options

Why it's needed

Need

Action exposure

Default options

App Intents[App Intents](https://developer.apple.com/documentation/appintents/making-actions-and-content-discoverable-and-widely-available)

Why it's needed

App Intents are the system contract that lets your app’s actions show up in Shortcuts, Siri, Spotlight, widgets, controls, and newer assistant-facing surfaces.

Need

App data surface

Default options

`AppEntity`,`EntityQuery`, and display representations

Why it's needed

A small, well-shaped entity layer makes it possible for the system to understand your app’s objects without exposing your entire model layer.

Need

Discoverability layer

Default options

`AppShortcutsProvider`with clear phrases, titles, and symbols

Why it's needed

App Shortcuts make the first set of exposed actions easier to find and run without asking users to build everything from scratch.

Need

Validation loop

Default options

`xcodebuild`, simulator checks, and focused runtime routing verification

Why it's needed

The hard part is not just compiling the intents target, but proving that the app opens or routes to the right place when the system invokes an intent.

Need | Default options | Why it's needed
Action exposure | App Intents[App Intents](https://developer.apple.com/documentation/appintents/making-actions-and-content-discoverable-and-widely-available) | App Intents are the system contract that lets your app’s actions show up in Shortcuts, Siri, Spotlight, widgets, controls, and newer assistant-facing surfaces.
App data surface | `AppEntity`,`EntityQuery`, and display representations | A small, well-shaped entity layer makes it possible for the system to understand your app’s objects without exposing your entire model layer.
Discoverability layer | `AppShortcutsProvider`with clear phrases, titles, and symbols | App Shortcuts make the first set of exposed actions easier to find and run without asking users to build everything from scratch.
Validation loop | `xcodebuild`, simulator checks, and focused runtime routing verification | The hard part is not just compiling the intents target, but proving that the app opens or routes to the right place when the system invokes an intent.

## Related use cases

### Adopt liquid glass

Use Codex and the Build iOS Apps plugin to audit existing iPhone and iPad UI, replace custom...iOSCode[Adopt liquid glassUse Codex and the Build iOS Apps plugin to audit existing iPhone and iPad UI, replace custom...iOSCode](/codex/use-cases/ios-liquid-glass)

### Build a Mac app shell

Use Codex and the Build macOS Apps plugin to turn an app idea into a desktop-native...macOSCode[Build a Mac app shellUse Codex and the Build macOS Apps plugin to turn an app idea into a desktop-native...macOSCode](/codex/use-cases/macos-sidebar-detail-inspector)

### Build for iOS

Use Codex to scaffold iOS SwiftUI projects, keep the build loop CLI-first with `xcodebuild`...iOSCode[Build for iOSUse Codex to scaffold iOS SwiftUI projects, keep the build loop CLI-first with `xcodebuild`...iOSCode](/codex/use-cases/native-ios-apps)