# Source: https://developers.openai.com/codex/changelog/

All updates[All updates](/codex/changelog)General[General](/codex/changelog?type=general)Codex app[Codex app](/codex/changelog?type=codex-app)Codex CLI[Codex CLI](/codex/changelog?type=codex-cli)May 2026[May 2026](#month-2026-05)April 2026[April 2026](#month-2026-04)March 2026[March 2026](#month-2026-03)February 2026[February 2026](#month-2026-02)January 2026[January 2026](#month-2026-01)December 2025[December 2025](#month-2025-12)November 2025[November 2025](#month-2025-11)October 2025[October 2025](#month-2025-10)September 2025[September 2025](#month-2025-09)August 2025[August 2025](#month-2025-08)June 2025[June 2025](#month-2025-06)May 2025[May 2025](#month-2025-05)

## May 2026

- 2026-05-21

### Appshots, goal mode, and more26.519

Appshots[Appshots](/codex/appshots)are now available in the Codex app on macOS. Press both Command keys to send the frontmost app window to Codex with a screenshot and available text, so Codex can work from context in another app without you copying, pasting, or describing it manually.

This launch also includes:

- Goal mode[Goal mode](/codex/prompting#goal-mode)is no longer an experimental feature and is available in the Codex app, IDE extension, and CLI. With Goal mode, you can have Codex drive toward a specific objective for hours or even days.
- Remote computer use[Remote computer use](/codex/app/computer-use#locked-use), so Codex can use desktop apps after your Mac locks, including remotely via Codex Mobile. Codex scopes locked use to active, trusted computer use turns and includes safeguards such as short-lived authorization, covered displays, relock on local input, and manual-unlock fallback.
- Plugin sharing[Plugin sharing](/codex/plugins/build#share-a-local-plugin-with-your-workspace)through marketplace sources is available for ChatGPT Business. Enterprise support is coming soon. Teams can distribute reusable plugin bundles that include skills, app integrations, MCP servers, and lifecycle hooks.
- Advanced in-app browser annotations[Advanced in-app browser annotations](/codex/app/browser#styling-feedback)let you tweak styling such as font size, colors, and spacing directly using annotations. This gives Codex a clearer signal for changes.
- Browser-use improvements across in-app browser & Chrome:

- Codex can now download and extract all image assets from a page much more quickly.
- Codex can now extract structured data from pages more effectively and find information more quickly with a read-only JS sandbox.
- Chrome extension will create less clutter when using it. Codex will no longer create tab groups when taking over existing tabs, and at the end of a task for handoff. Instead, it uses tab icons to indicate status.
- Significantly improved reliability for browser use. We fixed bugs on Windows, flaky availability of the plugin to non geo-blocked regions, and many other issues impacting performance.
- 2026-05-21

### Codex CLI0.133.0
````$npminstall-g@openai/codex@0.133.0````
View details

## New Features

- Goals are now enabled by default, backed by dedicated storage, and track progress across active turns. (#23300[#23300](https://github.com/openai/codex/pull/23300),#23685[#23685](https://github.com/openai/codex/pull/23685),#23696[#23696](https://github.com/openai/codex/pull/23696),#23732[#23732](https://github.com/openai/codex/pull/23732))
- `codex remote-control`now runs like a foreground command, waits for readiness, reports machine status, and keeps explicit daemon-style`start`/`stop`commands. (#22878[#22878](https://github.com/openai/codex/pull/22878))
- Permission profiles gained list APIs, inheritance, managed`requirements.toml`support, runtime refresh behavior, and stronger Windows sandbox integration. (#22928[#22928](https://github.com/openai/codex/pull/22928),#23412[#23412](https://github.com/openai/codex/pull/23412),#22270[#22270](https://github.com/openai/codex/pull/22270),#23433[#23433](https://github.com/openai/codex/pull/23433),#22931[#22931](https://github.com/openai/codex/pull/22931),#23715[#23715](https://github.com/openai/codex/pull/23715))
- Plugin discovery is easier to inspect, with marketplace-aware list output, installed versions, visible marketplace roots, and remote collection support. (#23372[#23372](https://github.com/openai/codex/pull/23372),#23584[#23584](https://github.com/openai/codex/pull/23584),#23727[#23727](https://github.com/openai/codex/pull/23727),#23730[#23730](https://github.com/openai/codex/pull/23730))
- Extensions can observe more lifecycle events, including subagent start/stop, tool execution, turn metadata, and async approval/turn processing. (#22782[#22782](https://github.com/openai/codex/pull/22782),#22873[#22873](https://github.com/openai/codex/pull/22873),#23309[#23309](https://github.com/openai/codex/pull/23309),#23688[#23688](https://github.com/openai/codex/pull/23688),#23690[#23690](https://github.com/openai/codex/pull/23690),#23692[#23692](https://github.com/openai/codex/pull/23692))

## Bug Fixes

- Fixed TUI startup choosing the wrong working directory when reusing a local app-server socket. (#23538[#23538](https://github.com/openai/codex/pull/23538))
- Fixed plan-mode free-form answers so modified Enter keys, like Shift+Enter, no longer submit unexpectedly. (#23536[#23536](https://github.com/openai/codex/pull/23536))
- Removed stale background terminal poll events after a process exits. (#23231[#23231](https://github.com/openai/codex/pull/23231))
- Preserved raw code-mode exec output unless an explicit output token limit is requested. (#23564[#23564](https://github.com/openai/codex/pull/23564))
- Made AGENTS instruction loading more reliable, including local global reads and warnings for invalid UTF-8 instead of silent drops. (#23343[#23343](https://github.com/openai/codex/pull/23343),#23232[#23232](https://github.com/openai/codex/pull/23232))
- Fixed app-server startup/shutdown races, empty resume/fork paths, plugin upgrade failures, and realtime v1 websocket compatibility. (#23516[#23516](https://github.com/openai/codex/pull/23516),#23578[#23578](https://github.com/openai/codex/pull/23578),#23400[#23400](https://github.com/openai/codex/pull/23400),#23356[#23356](https://github.com/openai/codex/pull/23356),#23771[#23771](https://github.com/openai/codex/pull/23771))

## Documentation

- Added clearer plugin-creator guidance for updating and reinstalling local personal plugins. (#23542[#23542](https://github.com/openai/codex/pull/23542))
- Expanded app-server/API docs and schema coverage around managed permission profile requirements. (#23433[#23433](https://github.com/openai/codex/pull/23433),#23555[#23555](https://github.com/openai/codex/pull/23555))

## Chores

- Added a canonical Codex package archive pipeline and moved installers, npm packages, DotSlash, and SDK runtimes toward that shared layout. (#23513[#23513](https://github.com/openai/codex/pull/23513),#23582[#23582](https://github.com/openai/codex/pull/23582),#23586[#23586](https://github.com/openai/codex/pull/23586),#23596[#23596](https://github.com/openai/codex/pull/23596),#23635[#23635](https://github.com/openai/codex/pull/23635),#23636[#23636](https://github.com/openai/codex/pull/23636),#23637[#23637](https://github.com/openai/codex/pull/23637),#23638[#23638](https://github.com/openai/codex/pull/23638),#23786[#23786](https://github.com/openai/codex/pull/23786))
- Fixed Linux Python runtime wheel tags so glibc-based systems can install the runtime artifacts. (#21812[#21812](https://github.com/openai/codex/pull/21812))
- Improved release and CI reliability with package-builder tests, prebuilt resource packaging, DotSlash zstd handling, platform-sharded Rust tests, and Codex Linux release runners. (#23760[#23760](https://github.com/openai/codex/pull/23760),#23759[#23759](https://github.com/openai/codex/pull/23759),#23752[#23752](https://github.com/openai/codex/pull/23752),#23358[#23358](https://github.com/openai/codex/pull/23358),#23761[#23761](https://github.com/openai/codex/pull/23761))

## Changelog

Full Changelog:rust-v0.132.0...rust-v0.133.0[rust-v0.132.0...rust-v0.133.0](https://github.com/openai/codex/compare/rust-v0.132.0...rust-v0.133.0)

- #23343[#23343](https://github.com/openai/codex/pull/23343)codex: route global AGENTS reads through LOCAL_FS@starr-openai[@starr-openai](https://github.com/starr-openai)
- #22380[#22380](https://github.com/openai/codex/pull/22380)fix: default unknown tool schemas to empty schemas@celia-oai[@celia-oai](https://github.com/celia-oai)
- #23309[#23309](https://github.com/openai/codex/pull/23309)Add tool lifecycle extension contributor@jif-oai[@jif-oai](https://github.com/jif-oai)
- #23253[#23253](https://github.com/openai/codex/pull/23253)Reduce rust-ci-full Windows nextest timeout flakes@starr-openai[@starr-openai](https://github.com/starr-openai)
- #22878[#22878](https://github.com/openai/codex/pull/22878)Improve`codex remote-control`CLI UX@owenlin0[@owenlin0](https://github.com/owenlin0)
- #21812[#21812](https://github.com/openai/codex/pull/21812)Publish Linux runtime wheels with glibc-compatible tags@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #22709[#22709](https://github.com/openai/codex/pull/22709)[codex] Trim unused TurnContextItem fields@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #23353[#23353](https://github.com/openai/codex/pull/23353)Include plugin id in plugin MCP tool metadata@mzeng-openai[@mzeng-openai](https://github.com/mzeng-openai)
- #22728[#22728](https://github.com/openai/codex/pull/22728)[codex] Move pending input into input queue@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #23371[#23371](https://github.com/openai/codex/pull/23371)fix(tui): warn on unsupported iTerm2 pet versions@fcoury-oai[@fcoury-oai](https://github.com/fcoury-oai)
- #23376[#23376](https://github.com/openai/codex/pull/23376)[codex-analytics] preserve user thread source for exec threads@marksteinbrick-oai[@marksteinbrick-oai](https://github.com/marksteinbrick-oai)
- #23360[#23360](https://github.com/openai/codex/pull/23360)app-server: use profile ids in v2 permission params@bolinfest[@bolinfest](https://github.com/bolinfest)
- #23384[#23384](https://github.com/openai/codex/pull/23384)[codex] Remove external websocket session resets@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #22721[#22721](https://github.com/openai/codex/pull/22721)cleanup: Remove skill env var dependency prompting@xl-openai[@xl-openai](https://github.com/xl-openai)
- #23389[#23389](https://github.com/openai/codex/pull/23389)Remove ToolSearch feature toggle@sayan-oai[@sayan-oai](https://github.com/sayan-oai)
- #23080[#23080](https://github.com/openai/codex/pull/23080)[1 of 7] Add thread settings to UserInput@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #23081[#23081](https://github.com/openai/codex/pull/23081)[2 of 7] Remove UserInputWithTurnContext@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #23075[#23075](https://github.com/openai/codex/pull/23075)[3 of 7] Remove UserTurn@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #23396[#23396](https://github.com/openai/codex/pull/23396)[codex] Extract turn skill and plugin injections@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #23356[#23356](https://github.com/openai/codex/pull/23356)fix(plugins): keep version upgrades additive@iceweasel-oai[@iceweasel-oai](https://github.com/iceweasel-oai)
- #22508[#22508](https://github.com/openai/codex/pull/22508)[5 of 7] Replace OverrideTurnContext with ThreadSettings@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #22086[#22086](https://github.com/openai/codex/pull/22086)CI: Customize v8 building@cconger[@cconger](https://github.com/cconger)
- #23390[#23390](https://github.com/openai/codex/pull/23390)Remove explicit connector tool undeferral@sayan-oai[@sayan-oai](https://github.com/sayan-oai)
- #22928[#22928](https://github.com/openai/codex/pull/22928)core: expose permission profile picker metadata@viyatb-oai[@viyatb-oai](https://github.com/viyatb-oai)
- #23352[#23352](https://github.com/openai/codex/pull/23352)Preserve context baselines for full-history agent forks@jif-oai[@jif-oai](https://github.com/jif-oai)
- #23300[#23300](https://github.com/openai/codex/pull/23300)feat: dedicated goal DB@jif-oai[@jif-oai](https://github.com/jif-oai)
- #22835[#22835](https://github.com/openai/codex/pull/22835)Remove ToolsConfig from tool planning@jif-oai[@jif-oai](https://github.com/jif-oai)
- #22870[#22870](https://github.com/openai/codex/pull/22870)Add`body_after_prefix`auto-compact token limit scope@jif-oai[@jif-oai](https://github.com/jif-oai)
- #23144[#23144](https://github.com/openai/codex/pull/23144)Defer v1 multi-agent tools behind tool search@jif-oai[@jif-oai](https://github.com/jif-oai)
- #23409[#23409](https://github.com/openai/codex/pull/23409)[codex] Allow empty turn/start requests@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #23388[#23388](https://github.com/openai/codex/pull/23388)[codex] Move hook request plumbing into hook runtime@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #23405[#23405](https://github.com/openai/codex/pull/23405)[codex] Preserve steer input as user input@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #22914[#22914](https://github.com/openai/codex/pull/22914)[2 of 4] tui: route app and skill enablement through app server@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #23397[#23397](https://github.com/openai/codex/pull/23397)[codex] Make contextual user fragments dyn-renderable@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #23475[#23475](https://github.com/openai/codex/pull/23475)chore: namespace v1 sub-agent tools@jif-oai[@jif-oai](https://github.com/jif-oai)
- #23493[#23493](https://github.com/openai/codex/pull/23493)Make`deny`canonical for filesystem permission entries@viyatb-oai[@viyatb-oai](https://github.com/viyatb-oai)
- #22929[#22929](https://github.com/openai/codex/pull/22929)Harden CLI rate limit window labels@ase-openai[@ase-openai](https://github.com/ase-openai)
- #22782[#22782](https://github.com/openai/codex/pull/22782)Add SubagentStart hook@abhinav-oai[@abhinav-oai](https://github.com/abhinav-oai)
- #23513[#23513](https://github.com/openai/codex/pull/23513)build: add Codex package builder@bolinfest[@bolinfest](https://github.com/bolinfest)
- #23369[#23369](https://github.com/openai/codex/pull/23369)Make local environment optional in EnvironmentManager@starr-openai[@starr-openai](https://github.com/starr-openai)
- #23327[#23327](https://github.com/openai/codex/pull/23327)Refactor exec-server websocket pump@starr-openai[@starr-openai](https://github.com/starr-openai)
- #23536[#23536](https://github.com/openai/codex/pull/23536)fix(tui): preserve modified enter in plan questions@fcoury-oai[@fcoury-oai](https://github.com/fcoury-oai)
- #23400[#23400](https://github.com/openai/codex/pull/23400)Fix empty rollout path app-server handling@wiltzius-openai[@wiltzius-openai](https://github.com/wiltzius-openai)
- #23551[#23551](https://github.com/openai/codex/pull/23551)Route local-only app-server gating through processors@starr-openai[@starr-openai](https://github.com/starr-openai)
- #23372[#23372](https://github.com/openai/codex/pull/23372)Split plugin install discovery into list and request tools@mzeng-openai[@mzeng-openai](https://github.com/mzeng-openai)
- #23516[#23516](https://github.com/openai/codex/pull/23516)fix: serialize unix app-server startup@efrazer-oai[@efrazer-oai](https://github.com/efrazer-oai)
- #22169[#22169](https://github.com/openai/codex/pull/22169)[codex] Honor role-defined spawn service tiers@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #23555[#23555](https://github.com/openai/codex/pull/23555)Add CUA requirements subsection for locked computer use@adams-oai[@adams-oai](https://github.com/adams-oai)
- #23538[#23538](https://github.com/openai/codex/pull/23538)Fix: TUI starting in wrong CWD@canvrno-oai[@canvrno-oai](https://github.com/canvrno-oai)
- #23526[#23526](https://github.com/openai/codex/pull/23526)build: fetch rg for Codex packages@bolinfest[@bolinfest](https://github.com/bolinfest)
- #23573[#23573](https://github.com/openai/codex/pull/23573)Remove unused ARC monitor path@mzeng-openai[@mzeng-openai](https://github.com/mzeng-openai)
- #23576[#23576](https://github.com/openai/codex/pull/23576)test: fix multi-agent service tier assertion@bolinfest[@bolinfest](https://github.com/bolinfest)
- #23541[#23541](https://github.com/openai/codex/pull/23541)build: default Codex package target and output@bolinfest[@bolinfest](https://github.com/bolinfest)
- #23358[#23358](https://github.com/openai/codex/pull/23358)Fan out rust-ci-full nextest by platform@starr-openai[@starr-openai](https://github.com/starr-openai)
- #23593[#23593](https://github.com/openai/codex/pull/23593)feat: expose codex-app-server version flag@bolinfest[@bolinfest](https://github.com/bolinfest)
- #23412[#23412](https://github.com/openai/codex/pull/23412)feat: add permission profile list api@viyatb-oai[@viyatb-oai](https://github.com/viyatb-oai)
- #23535[#23535](https://github.com/openai/codex/pull/23535)Move plugin and skill warmup into session startup@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #23231[#23231](https://github.com/openai/codex/pull/23231)Fix stale background terminal poll events@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #23564[#23564](https://github.com/openai/codex/pull/23564)[codex] Preserve raw code-mode exec output by default@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #23232[#23232](https://github.com/openai/codex/pull/23232)Warn on invalid UTF-8 in AGENTS.md files@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #23584[#23584](https://github.com/openai/codex/pull/23584)feat: Add vertical remote plugin collection support@xl-openai[@xl-openai](https://github.com/xl-openai)
- #23586[#23586](https://github.com/openai/codex/pull/23586)build: package prebuilt Codex entrypoints@bolinfest[@bolinfest](https://github.com/bolinfest)
- #23582[#23582](https://github.com/openai/codex/pull/23582)ci: build Codex package archives in release workflow@bolinfest[@bolinfest](https://github.com/bolinfest)
- #23596[#23596](https://github.com/openai/codex/pull/23596)runtime: detect Codex package layout@bolinfest[@bolinfest](https://github.com/bolinfest)
- #23500[#23500](https://github.com/openai/codex/pull/23500)add encryptedcontent to functioncalloutput@sayan-oai[@sayan-oai](https://github.com/sayan-oai)
- #23633[#23633](https://github.com/openai/codex/pull/23633)Migrate exec-server remote registration to environments@richardopenai[@richardopenai](https://github.com/richardopenai)
- #23451[#23451](https://github.com/openai/codex/pull/23451)Add timeout for remote compaction requests@jif-oai[@jif-oai](https://github.com/jif-oai)
- #23667[#23667](https://github.com/openai/codex/pull/23667)feat: rename 1@jif-oai[@jif-oai](https://github.com/jif-oai)
- #23669[#23669](https://github.com/openai/codex/pull/23669)feat: rename 3@jif-oai[@jif-oai](https://github.com/jif-oai)
- #23668[#23668](https://github.com/openai/codex/pull/23668)feat: rename 2@jif-oai[@jif-oai](https://github.com/jif-oai)
- #23675[#23675](https://github.com/openai/codex/pull/23675)fix: main@jif-oai[@jif-oai](https://github.com/jif-oai)
- #23685[#23685](https://github.com/openai/codex/pull/23685)feat: wire goal extension tools to the dedicated goal store@jif-oai[@jif-oai](https://github.com/jif-oai)
- #23690[#23690](https://github.com/openai/codex/pull/23690)feat: async approval contrib@jif-oai[@jif-oai](https://github.com/jif-oai)
- #23692[#23692](https://github.com/openai/codex/pull/23692)feat: async turn item process@jif-oai[@jif-oai](https://github.com/jif-oai)
- #23688[#23688](https://github.com/openai/codex/pull/23688)feat: expose turn-start metadata to extensions@jif-oai[@jif-oai](https://github.com/jif-oai)
- #23605[#23605](https://github.com/openai/codex/pull/23605)[codex] Hide deferred tools from code mode prompt@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #23634[#23634](https://github.com/openai/codex/pull/23634)runtime: use install context for bundled bwrap@bolinfest[@bolinfest](https://github.com/bolinfest)
- #23635[#23635](https://github.com/openai/codex/pull/23635)release: publish Codex package archive checksums@bolinfest[@bolinfest](https://github.com/bolinfest)
- #23592[#23592](https://github.com/openai/codex/pull/23592)feat: Add btw alias for side slash command@anp-oai[@anp-oai](https://github.com/anp-oai)
- #23696[#23696](https://github.com/openai/codex/pull/23696)feat: account active goal progress in the goal extension@jif-oai[@jif-oai](https://github.com/jif-oai)
- #23176[#23176](https://github.com/openai/codex/pull/23176)[2 of 2] Start fresh TUI thread in background@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #23578[#23578](https://github.com/openai/codex/pull/23578)fix(app-server): speed up shutdown@fcoury-oai[@fcoury-oai](https://github.com/fcoury-oai)
- #22896[#22896](https://github.com/openai/codex/pull/22896)windows-sandbox: add resolved permissions helper@bolinfest[@bolinfest](https://github.com/bolinfest)
- #23502[#23502](https://github.com/openai/codex/pull/23502)Add thread/settings/update app-server API@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #23507[#23507](https://github.com/openai/codex/pull/23507)Sync TUI thread settings through app server@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #23666[#23666](https://github.com/openai/codex/pull/23666)feat: add turn_id and truncation_policy to extension tool calls@jif-oai[@jif-oai](https://github.com/jif-oai)
- #23636[#23636](https://github.com/openai/codex/pull/23636)install: consume Codex package archives@bolinfest[@bolinfest](https://github.com/bolinfest)
- #23717[#23717](https://github.com/openai/codex/pull/23717)[codex] Preserve failed goal accounting flushes@jif-oai[@jif-oai](https://github.com/jif-oai)
- #23655[#23655](https://github.com/openai/codex/pull/23655)add standalone websearch api client@sayan-oai[@sayan-oai](https://github.com/sayan-oai)
- #23724[#23724](https://github.com/openai/codex/pull/23724)Fix thread settings clippy failure@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #23637[#23637](https://github.com/openai/codex/pull/23637)npm: ship platform packages in Codex package layout@bolinfest[@bolinfest](https://github.com/bolinfest)
- #23729[#23729](https://github.com/openai/codex/pull/23729)fix(config): resolve cloud requirements deny-read globs@viyatb-oai[@viyatb-oai](https://github.com/viyatb-oai)
- #23638[#23638](https://github.com/openai/codex/pull/23638)dotslash: publish Codex entrypoints from package archives@bolinfest[@bolinfest](https://github.com/bolinfest)
- #22918[#22918](https://github.com/openai/codex/pull/22918)windows-sandbox: send permission profiles to elevated runner@bolinfest[@bolinfest](https://github.com/bolinfest)
- #23735[#23735](https://github.com/openai/codex/pull/23735)windows-sandbox: share bundled helper lookup@bolinfest[@bolinfest](https://github.com/bolinfest)
- #18868[#18868](https://github.com/openai/codex/pull/18868)Add MITM hook config model@evawong-oai[@evawong-oai](https://github.com/evawong-oai)
- #22270[#22270](https://github.com/openai/codex/pull/22270)feat(permissions): resolve permission profile inheritance@viyatb-oai[@viyatb-oai](https://github.com/viyatb-oai)
- #23719[#23719](https://github.com/openai/codex/pull/23719)cli: add strict config to exec-server@bolinfest[@bolinfest](https://github.com/bolinfest)
- #23542[#23542](https://github.com/openai/codex/pull/23542)[skills] Create a personal update flow for plugin creator@caseychow-oai[@caseychow-oai](https://github.com/caseychow-oai)
- #21272[#21272](https://github.com/openai/codex/pull/21272)Support compact SessionStart hooks@abhinav-oai[@abhinav-oai](https://github.com/abhinav-oai)
- #20659[#20659](https://github.com/openai/codex/pull/20659)Wire MITM hooks into runtime enforcement@evawong-oai[@evawong-oai](https://github.com/evawong-oai)
- #23752[#23752](https://github.com/openai/codex/pull/23752)release: use DotSlash zstd for package archives@bolinfest[@bolinfest](https://github.com/bolinfest)
- #22923[#22923](https://github.com/openai/codex/pull/22923)windows-sandbox: drive write roots from resolved permissions@bolinfest[@bolinfest](https://github.com/bolinfest)
- #23761[#23761](https://github.com/openai/codex/pull/23761)chore: use Codex Linux runners for Rust releases@bolinfest[@bolinfest](https://github.com/bolinfest)
- #23759[#23759](https://github.com/openai/codex/pull/23759)release: package prebuilt resource binaries@bolinfest[@bolinfest](https://github.com/bolinfest)
- #23167[#23167](https://github.com/openai/codex/pull/23167)windows-sandbox: feed setup from resolved permissions@bolinfest[@bolinfest](https://github.com/bolinfest)
- #22931[#22931](https://github.com/openai/codex/pull/22931)core: refresh active permission profiles at runtime@viyatb-oai[@viyatb-oai](https://github.com/viyatb-oai)
- #22873[#22873](https://github.com/openai/codex/pull/22873)Add SubagentStop hook@abhinav-oai[@abhinav-oai](https://github.com/abhinav-oai)
- #23727[#23727](https://github.com/openai/codex/pull/23727)feat(plugins): tabulate plugin list output@caseychow-oai[@caseychow-oai](https://github.com/caseychow-oai)
- #23732[#23732](https://github.com/openai/codex/pull/23732)Make goals feature on by default and no longer experimental@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #23537[#23537](https://github.com/openai/codex/pull/23537)Honor client-resolved service tier defaults@shijie-oai[@shijie-oai](https://github.com/shijie-oai)
- #23771[#23771](https://github.com/openai/codex/pull/23771)[codex] Fix realtime v1 websocket compatibility@guinness-oai[@guinness-oai](https://github.com/guinness-oai)
- #23764[#23764](https://github.com/openai/codex/pull/23764)Remove Windows sandbox resource stamping@iceweasel-oai[@iceweasel-oai](https://github.com/iceweasel-oai)
- #23730[#23730](https://github.com/openai/codex/pull/23730)[codex] List marketplaces considered by plugin discovery@caseychow-oai[@caseychow-oai](https://github.com/caseychow-oai)
- #23760[#23760](https://github.com/openai/codex/pull/23760)ci: run Codex package builder tests@bolinfest[@bolinfest](https://github.com/bolinfest)
- #23737[#23737](https://github.com/openai/codex/pull/23737)[codex] Add plugin id to MCP tool call items@mzeng-openai[@mzeng-openai](https://github.com/mzeng-openai)
- #18240[#18240](https://github.com/openai/codex/pull/18240)Use named MITM permissions config@evawong-oai[@evawong-oai](https://github.com/evawong-oai)
- #23774[#23774](https://github.com/openai/codex/pull/23774)[codex] Reject read-only fallback with approvals disabled@viyatb-oai[@viyatb-oai](https://github.com/viyatb-oai)
- #23714[#23714](https://github.com/openai/codex/pull/23714)windows-sandbox: add profile-native elevated APIs@bolinfest[@bolinfest](https://github.com/bolinfest)
- #23433[#23433](https://github.com/openai/codex/pull/23433)feat: support managed permission profiles in requirements.toml@viyatb-oai[@viyatb-oai](https://github.com/viyatb-oai)
- #23715[#23715](https://github.com/openai/codex/pull/23715)core: pass permission profiles to Windows runner@bolinfest[@bolinfest](https://github.com/bolinfest)
- #23786[#23786](https://github.com/openai/codex/pull/23786)sdk: launch packaged Codex runtimes@bolinfest[@bolinfest](https://github.com/bolinfest)

Full release on Github[Full release on Github](https://github.com/openai/codex/releases/tag/rust-v0.133.0)
- 2026-05-20

### Codex CLI0.132.0
````$npminstall-g@openai/codex@0.132.0````
View details

## New Features

- The Python SDK now supports first-class authentication, including API key login, ChatGPT browser and device-code flows, account inspection, and logout APIs. (#23093[#23093](https://github.com/openai/codex/pull/23093))
- Python turn APIs are easier to use for text-only workflows: you can pass a plain string as input, and handle-based runs now return a richer`TurnResult`with collected items, timing, and usage data. (#23151[#23151](https://github.com/openai/codex/pull/23151),#23162[#23162](https://github.com/openai/codex/pull/23162))
- `codex exec resume`now accepts`--output-schema`, so resumed automations can keep session context while still enforcing structured JSON output. (#23123[#23123](https://github.com/openai/codex/pull/23123))
- TUI startup is faster because terminal capability probes are now batched instead of waiting on several serial checks before the first interactive frame. (#23175[#23175](https://github.com/openai/codex/pull/23175))
- Remote executor registration can now use standard Codex auth instead of a separate registry credential flow. (#22769[#22769](https://github.com/openai/codex/pull/22769))
- App-server turns can preserve requested image fidelity, including original-resolution local images, across user inputs and image-producing tools. (#20693[#20693](https://github.com/openai/codex/pull/20693))

## Bug Fixes

- Goal continuations now stop when they hit usage limits or a repeated blocker instead of looping and burning more tokens, and completion responses phrase usage more naturally. (#23094[#23094](https://github.com/openai/codex/pull/23094),#22907[#22907](https://github.com/openai/codex/pull/22907))
- The session picker is easier to trust: renamed threads now show`name (thread-id)`in resume hints, and pasted text works in the picker search box. (#23234[#23234](https://github.com/openai/codex/pull/23234),#23338[#23338](https://github.com/openai/codex/pull/23338))
- Multi-session TUI flows are more reliable: in-progress MCP calls stay marked as active during replay, and elicitation replies are sent back to the thread that requested them. (#23236[#23236](https://github.com/openai/codex/pull/23236),#23241[#23241](https://github.com/openai/codex/pull/23241))
- Remote sessions now keep websocket connections alive and show repo-relative diff paths again instead of`/tmp/...`-prefixed paths. (#23226[#23226](https://github.com/openai/codex/pull/23226),#23261[#23261](https://github.com/openai/codex/pull/23261))
- Windows installs are more robust:`codex doctor`now detects npm-managed installs correctly, and MSVC release binaries no longer depend on separately installed VC++ runtime DLLs. (#22967[#22967](https://github.com/openai/codex/pull/22967),#22905[#22905](https://github.com/openai/codex/pull/22905))
- TUI polish fixes include immediate shutdown feedback on exit, hiding the ChatGPT usage link for non-OpenAI providers, and keeping a cleared Fast tier from reappearing after side-thread resume. (#23323[#23323](https://github.com/openai/codex/pull/23323),#23127[#23127](https://github.com/openai/codex/pull/23127),#23121[#23121](https://github.com/openai/codex/pull/23121))

## Documentation

- The Python SDK docs, FAQ, and examples were refreshed around the new auth flow and turn APIs, with clearer setup guidance and simpler text-only examples. (#22941[#22941](https://github.com/openai/codex/pull/22941),#23093[#23093](https://github.com/openai/codex/pull/23093),#23151[#23151](https://github.com/openai/codex/pull/23151),#23162[#23162](https://github.com/openai/codex/pull/23162))

## Chores

- Memory summaries are now versioned and rebuilt when the stored format is stale, which should keep long-lived memory context leaner and more predictable. (#23148[#23148](https://github.com/openai/codex/pull/23148))

## Changelog

Full Changelog:rust-v0.131.0...rust-v0.132.0[rust-v0.131.0...rust-v0.132.0](https://github.com/openai/codex/compare/rust-v0.131.0...rust-v0.132.0)

- #20693[#20693](https://github.com/openai/codex/pull/20693)Preserve image detail in app-server inputs@fjord-oai[@fjord-oai](https://github.com/fjord-oai)
- #22891[#22891](https://github.com/openai/codex/pull/22891)tui: pass active permission profiles through app commands@bolinfest[@bolinfest](https://github.com/bolinfest)
- #22924[#22924](https://github.com/openai/codex/pull/22924)app-server-protocol: remove PermissionProfile from API@bolinfest[@bolinfest](https://github.com/bolinfest)
- #22941[#22941](https://github.com/openai/codex/pull/22941)[codex] Refine Python SDK user-facing docs@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #22967[#22967](https://github.com/openai/codex/pull/22967)Fix Windows doctor npm root probe@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #22920[#22920](https://github.com/openai/codex/pull/22920)core: set permission profiles from snapshots@bolinfest[@bolinfest](https://github.com/bolinfest)
- #22939[#22939](https://github.com/openai/codex/pull/22939)[codex] Split Python SDK helper logic@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #22907[#22907](https://github.com/openai/codex/pull/22907)Improve goal completion usage reporting@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #23030[#23030](https://github.com/openai/codex/pull/23030)test: construct permission profiles directly@bolinfest[@bolinfest](https://github.com/bolinfest)
- #22769[#22769](https://github.com/openai/codex/pull/22769)exec-server: support auth-backed remote executor registration@miz-openai[@miz-openai](https://github.com/miz-openai)
- #22946[#22946](https://github.com/openai/codex/pull/22946)[codex] preserve MCP result meta in McpToolCallItemResult@miaolin-oai[@miaolin-oai](https://github.com/miaolin-oai)
- #23069[#23069](https://github.com/openai/codex/pull/23069)multiagent: trim model-visible description, cap to 5 models@sayan-oai[@sayan-oai](https://github.com/sayan-oai)
- #22913[#22913](https://github.com/openai/codex/pull/22913)[1 of 4] tui: route primary settings writes through app server@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #23093[#23093](https://github.com/openai/codex/pull/23093)sdk/python: add first-class login support@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #23151[#23151](https://github.com/openai/codex/pull/23151)[codex] Return TurnResult from Python turn handles@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #23147[#23147](https://github.com/openai/codex/pull/23147)Make multi-agent v2 tool namespace configurable@jif-oai[@jif-oai](https://github.com/jif-oai)
- #23036[#23036](https://github.com/openai/codex/pull/23036)test: reduce core sandbox policy test setup@bolinfest[@bolinfest](https://github.com/bolinfest)
- #23162[#23162](https://github.com/openai/codex/pull/23162)[codex] Accept string input for Python turns@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #23226[#23226](https://github.com/openai/codex/pull/23226)Add exec-server websocket keepalive@starr-openai[@starr-openai](https://github.com/starr-openai)
- #23148[#23148](https://github.com/openai/codex/pull/23148)Densify and version memory summaries@jif-oai[@jif-oai](https://github.com/jif-oai)
- #22448[#22448](https://github.com/openai/codex/pull/22448)[codex] Add installed-plugin mention API@xli-oai[@xli-oai](https://github.com/xli-oai)
- #23288[#23288](https://github.com/openai/codex/pull/23288)chore: goal ext skeleton@jif-oai[@jif-oai](https://github.com/jif-oai)
- #23291[#23291](https://github.com/openai/codex/pull/23291)Make extension lifecycle hooks async@jif-oai[@jif-oai](https://github.com/jif-oai)
- #23293[#23293](https://github.com/openai/codex/pull/23293)feat: add extension event sink capability@jif-oai[@jif-oai](https://github.com/jif-oai)
- #23295[#23295](https://github.com/openai/codex/pull/23295)chore: isolate thread goal storage behind GoalStore@jif-oai[@jif-oai](https://github.com/jif-oai)
- #23301[#23301](https://github.com/openai/codex/pull/23301)chore: goal resumed metrics@jif-oai[@jif-oai](https://github.com/jif-oai)
- #23305[#23305](https://github.com/openai/codex/pull/23305)chore: make token usage async@jif-oai[@jif-oai](https://github.com/jif-oai)
- #23306[#23306](https://github.com/openai/codex/pull/23306)Emit goal update events from goal extension tools@jif-oai[@jif-oai](https://github.com/jif-oai)
- #23121[#23121](https://github.com/openai/codex/pull/23121)tui: keep cleared Fast tier from reappearing after side-thread resume@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #23123[#23123](https://github.com/openai/codex/pull/23123)Support --output-schema for exec resume@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #23128[#23128](https://github.com/openai/codex/pull/23128)Fix TUI stream cleanup after turn errors@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #23127[#23127](https://github.com/openai/codex/pull/23127)Hide ChatGPT usage link for non-OpenAI status@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #23175[#23175](https://github.com/openai/codex/pull/23175)[1 of 2] Optimize TUI startup terminal probes@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #22706[#22706](https://github.com/openai/codex/pull/22706)[codex] Remove legacy shell output formatting paths@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #23332[#23332](https://github.com/openai/codex/pull/23332)nit: read prompt@jif-oai[@jif-oai](https://github.com/jif-oai)
- #22905[#22905](https://github.com/openai/codex/pull/22905)windows: link MSVC release binaries with static CRT@iceweasel-oai[@iceweasel-oai](https://github.com/iceweasel-oai)
- #23323[#23323](https://github.com/openai/codex/pull/23323)fix(tui): show shutdown feedback on exit@fcoury-oai[@fcoury-oai](https://github.com/fcoury-oai)
- #23261[#23261](https://github.com/openai/codex/pull/23261)Fix remote turn diff display roots@starr-openai[@starr-openai](https://github.com/starr-openai)
- #22569[#22569](https://github.com/openai/codex/pull/22569)Simplify legacy Windows sandbox ACL persistence@iceweasel-oai[@iceweasel-oai](https://github.com/iceweasel-oai)
- #23273[#23273](https://github.com/openai/codex/pull/23273)Upload rust full CI JUnit reports@starr-openai[@starr-openai](https://github.com/starr-openai)
- #22893[#22893](https://github.com/openai/codex/pull/22893)fix: harden plugin creator sharing validation@efrazer-oai[@efrazer-oai](https://github.com/efrazer-oai)
- #23094[#23094](https://github.com/openai/codex/pull/23094)goal: pause continuation loops on usage limits and blockers@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #23234[#23234](https://github.com/openai/codex/pull/23234)Clarify resume hints for renamed threads@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #23241[#23241](https://github.com/openai/codex/pull/23241)TUI: route elicitation responses to request thread@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #23236[#23236](https://github.com/openai/codex/pull/23236)TUI: replay in-progress MCP calls as started@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #23088[#23088](https://github.com/openai/codex/pull/23088)goals: keep pause transitions explicit@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #23338[#23338](https://github.com/openai/codex/pull/23338)feat(tui): handle paste in session picker@fcoury-oai[@fcoury-oai](https://github.com/fcoury-oai)
- #23335[#23335](https://github.com/openai/codex/pull/23335)feat(app-server): add optional thread_id to experimentalFeature/list@owenlin0[@owenlin0](https://github.com/owenlin0)

Full release on Github[Full release on Github](https://github.com/openai/codex/releases/tag/rust-v0.132.0)
- 2026-05-18

### Codex CLI0.131.0
````$npminstall-g@openai/codex@0.131.0````
View details

## New Features

- The TUI now offers richer session controls and display: data-driven service-tier commands, blended token usage, permissions/approval mode, effective workspace roots, and responsive Markdown tables. (#21745[#21745](https://github.com/openai/codex/pull/21745),#21906[#21906](https://github.com/openai/codex/pull/21906),#21991[#21991](https://github.com/openai/codex/pull/21991),#21669[#21669](https://github.com/openai/codex/pull/21669),#21677[#21677](https://github.com/openai/codex/pull/21677),#22052[#22052](https://github.com/openai/codex/pull/22052),#22612[#22612](https://github.com/openai/codex/pull/22612))
- `@`mentions now search files, directories, plugins, and skills in one picker, backed by app-server plugin metadata. (#19068[#19068](https://github.com/openai/codex/pull/19068),#22375[#22375](https://github.com/openai/codex/pull/22375))
- Plugin workflows gained marketplace CLI commands, version-aware sharing, share checkout, clearer shared-workspace buckets, and default-enabled plugin hooks. (#21396[#21396](https://github.com/openai/codex/pull/21396),#22397[#22397](https://github.com/openai/codex/pull/22397),#22425[#22425](https://github.com/openai/codex/pull/22425),#22435[#22435](https://github.com/openai/codex/pull/22435),#22549[#22549](https://github.com/openai/codex/pull/22549))
- Remote workflows now support daemon-managed`codex remote-control`, runtime enable/disable APIs, status reads, and registry-backed/configured remote environments. (#20718[#20718](https://github.com/openai/codex/pull/20718),#22218[#22218](https://github.com/openai/codex/pull/22218),#22562[#22562](https://github.com/openai/codex/pull/22562),#22578[#22578](https://github.com/openai/codex/pull/22578),#22877[#22877](https://github.com/openai/codex/pull/22877),#20667[#20667](https://github.com/openai/codex/pull/20667),#21323[#21323](https://github.com/openai/codex/pull/21323))
- The Python SDK moved to`openai-codex`/`openai_codex`, with pinned runtime-generated types, concurrent turn routing, approval modes, and integration coverage. (#21778[#21778](https://github.com/openai/codex/pull/21778),#21891[#21891](https://github.com/openai/codex/pull/21891),#21893[#21893](https://github.com/openai/codex/pull/21893),#21896[#21896](https://github.com/openai/codex/pull/21896),#21905[#21905](https://github.com/openai/codex/pull/21905),#21910[#21910](https://github.com/openai/codex/pull/21910),#22014[#22014](https://github.com/openai/codex/pull/22014))
- Added`codex doctor`for support-ready diagnostics across runtime, auth, terminal, network, config, and local state. (#22336[#22336](https://github.com/openai/codex/pull/22336))

## Bug Fixes

- Fixed several TUI interaction and rendering issues, including URL wrapping, light-mode selection contrast, Shift+Enter in tmux,`/review`MCP startup status,`/side`Esc handling, and network approval history text. (#21760[#21760](https://github.com/openai/codex/pull/21760),#21950[#21950](https://github.com/openai/codex/pull/21950),#21943[#21943](https://github.com/openai/codex/pull/21943),#21624[#21624](https://github.com/openai/codex/pull/21624),#22710[#22710](https://github.com/openai/codex/pull/22710),#22229[#22229](https://github.com/openai/codex/pull/22229))
- Hardened Windows sandbox behavior around deny-read rules, scoped write roots, ineffective firewall policy, and PowerShell edge cases. (#18202[#18202](https://github.com/openai/codex/pull/18202),#21479[#21479](https://github.com/openai/codex/pull/21479),#22353[#22353](https://github.com/openai/codex/pull/22353),#21400[#21400](https://github.com/openai/codex/pull/21400),#22643[#22643](https://github.com/openai/codex/pull/22643))
- Preserved managed read restrictions during permission escalation and cleaned up workspace-root permission profile resolution. (#15977[#15977](https://github.com/openai/codex/pull/15977),#22624[#22624](https://github.com/openai/codex/pull/22624),#22683[#22683](https://github.com/openai/codex/pull/22683))
- Made app-server and local state startup safer by preserving SQLite data, failing closed when state cannot open, adding recovery paths, and softening optional metadata sync failures. (#21831[#21831](https://github.com/openai/codex/pull/21831),#21847[#21847](https://github.com/openai/codex/pull/21847),#22580[#22580](https://github.com/openai/codex/pull/22580),#22734[#22734](https://github.com/openai/codex/pull/22734),#22899[#22899](https://github.com/openai/codex/pull/22899))
- Improved Git and auth reliability by using root worktree hooks consistently, ignoring repo hook/fsmonitor config in helper commands, binding local MCP OAuth callbacks, and revoking superseded login tokens. (#21969[#21969](https://github.com/openai/codex/pull/21969),#22843[#22843](https://github.com/openai/codex/pull/22843),#22652[#22652](https://github.com/openai/codex/pull/22652),#20237[#20237](https://github.com/openai/codex/pull/20237),#21747[#21747](https://github.com/openai/codex/pull/21747))
- Reduced remote and Windows cleanup friction with longer exec-server transport timeouts, quieter`taskkill`cleanup, and non-queued plugin reads. (#21825[#21825](https://github.com/openai/codex/pull/21825),#21759[#21759](https://github.com/openai/codex/pull/21759),#22058[#22058](https://github.com/openai/codex/pull/22058),#22703[#22703](https://github.com/openai/codex/pull/22703))

## Documentation

- Clarified that general Codex product docs should not be added to this repo, while app-server API docs remain in scope. (#21772[#21772](https://github.com/openai/codex/pull/21772))
- Updated plugin-creator guidance for the simplified local plugin handoff links. (#22240[#22240](https://github.com/openai/codex/pull/22240))
- Documented new app-server/API contracts for remote environments and the desktop-owned config namespace. (#21323[#21323](https://github.com/openai/codex/pull/21323),#22584[#22584](https://github.com/openai/codex/pull/22584))

## Chores

- Improved CI and release reliability across Rust CI, exact PR-head checkout, Windows Bazel sharding, unsigned macOS artifacts, and signed macOS promotion. (#21604[#21604](https://github.com/openai/codex/pull/21604),#21628[#21628](https://github.com/openai/codex/pull/21628),#21835[#21835](https://github.com/openai/codex/pull/21835),#22408[#22408](https://github.com/openai/codex/pull/22408),#22559[#22559](https://github.com/openai/codex/pull/22559),#22649[#22649](https://github.com/openai/codex/pull/22649),#22737[#22737](https://github.com/openai/codex/pull/22737),#22788[#22788](https://github.com/openai/codex/pull/22788),#22900[#22900](https://github.com/openai/codex/pull/22900))
- Split large TUI ChatWidget, history, and composer code into focused modules without intended behavior changes. (#21866[#21866](https://github.com/openai/codex/pull/21866),#22269[#22269](https://github.com/openai/codex/pull/22269),#22407[#22407](https://github.com/openai/codex/pull/22407),#22433[#22433](https://github.com/openai/codex/pull/22433),#22518[#22518](https://github.com/openai/codex/pull/22518),#22537[#22537](https://github.com/openai/codex/pull/22537),#22704[#22704](https://github.com/openai/codex/pull/22704),#22581[#22581](https://github.com/openai/codex/pull/22581),#22656[#22656](https://github.com/openai/codex/pull/22656))
- Continued extracting extension and tool internals, including shared tool contracts plus guardian and memory extension plumbing. (#21736[#21736](https://github.com/openai/codex/pull/21736),#21737[#21737](https://github.com/openai/codex/pull/21737),#21738[#21738](https://github.com/openai/codex/pull/21738),#22138[#22138](https://github.com/openai/codex/pull/22138),#22147[#22147](https://github.com/openai/codex/pull/22147),#22216[#22216](https://github.com/openai/codex/pull/22216),#22258[#22258](https://github.com/openai/codex/pull/22258),#22344[#22344](https://github.com/openai/codex/pull/22344),#22476[#22476](https://github.com/openai/codex/pull/22476),#22480[#22480](https://github.com/openai/codex/pull/22480),#22485[#22485](https://github.com/openai/codex/pull/22485),#22498[#22498](https://github.com/openai/codex/pull/22498))
- Removed obsolete tool paths, feature flags, config gates, and legacy hooks as defaults stabilized. (#21651[#21651](https://github.com/openai/codex/pull/21651),#21805[#21805](https://github.com/openai/codex/pull/21805),#22173[#22173](https://github.com/openai/codex/pull/22173),#22246[#22246](https://github.com/openai/codex/pull/22246),#22565[#22565](https://github.com/openai/codex/pull/22565),#22711[#22711](https://github.com/openai/codex/pull/22711),#22717[#22717](https://github.com/openai/codex/pull/22717),#22724[#22724](https://github.com/openai/codex/pull/22724),#22730[#22730](https://github.com/openai/codex/pull/22730))

## Changelog

Full Changelog:rust-v0.130.0...rust-v0.131.0[rust-v0.130.0...rust-v0.131.0](https://github.com/openai/codex/compare/rust-v0.130.0...rust-v0.131.0)

- #21550[#21550](https://github.com/openai/codex/pull/21550)[codex] make shutdown pending-touch test deterministic@jif-oai[@jif-oai](https://github.com/jif-oai)
- #21697[#21697](https://github.com/openai/codex/pull/21697)Allow string service tiers in config TOML@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #21687[#21687](https://github.com/openai/codex/pull/21687)[codex] Enable apply_patch freeform by default@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #19896[#19896](https://github.com/openai/codex/pull/19896)Update models.json @github-actions
- #21669[#21669](https://github.com/openai/codex/pull/21669)Display blended token count in status line@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #21677[#21677](https://github.com/openai/codex/pull/21677)Show permissions and approval mode in the TUI status line@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #21757[#21757](https://github.com/openai/codex/pull/21757)api: send hyphenated session and thread headers@jif-oai[@jif-oai](https://github.com/jif-oai)
- #21763[#21763](https://github.com/openai/codex/pull/21763)nit: comment@jif-oai[@jif-oai](https://github.com/jif-oai)
- #21749[#21749](https://github.com/openai/codex/pull/21749)codex-otel: validate provider span attributes consistently@bbrown-oai[@bbrown-oai](https://github.com/bbrown-oai)
- #21767[#21767](https://github.com/openai/codex/pull/21767)chore: thread tui@jif-oai[@jif-oai](https://github.com/jif-oai)
- #21443[#21443](https://github.com/openai/codex/pull/21443)[sandboxing] Remove Darwin user cache write from Seatbelt network policy@evawong-oai[@evawong-oai](https://github.com/evawong-oai)
- #21604[#21604](https://github.com/openai/codex/pull/21604)Fix`rust-ci-full`failures due to missing`bwrap`@zanie-oai[@zanie-oai](https://github.com/zanie-oai)
- #21628[#21628](https://github.com/openai/codex/pull/21628)Use`CARGO_NET_GIT_FETCH_WITH_CLI`in`rust-ci-full`for more reliable git fetches@zanie-oai[@zanie-oai](https://github.com/zanie-oai)
- #21745[#21745](https://github.com/openai/codex/pull/21745)[codex] Generalize service tier slash commands@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #21772[#21772](https://github.com/openai/codex/pull/21772)Clarify docs folder guidance in AGENTS.md@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #21622[#21622](https://github.com/openai/codex/pull/21622)[codex] Address some more GHA hygiene issues@ww-oai[@ww-oai](https://github.com/ww-oai)
- #21662[#21662](https://github.com/openai/codex/pull/21662)feat: Use installation ID in remote enrollments@ddr-oai[@ddr-oai](https://github.com/ddr-oai)
- #20667[#20667](https://github.com/openai/codex/pull/20667)Load configured environments from CODEX_HOME@starr-openai[@starr-openai](https://github.com/starr-openai)
- #21776[#21776](https://github.com/openai/codex/pull/21776)Update models.json @github-actions
- #21787[#21787](https://github.com/openai/codex/pull/21787)Support resource binaries in Python runtime staging@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #21784[#21784](https://github.com/openai/codex/pull/21784)Publish Python runtime wheels on release@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #21601[#21601](https://github.com/openai/codex/pull/21601)Emit accepted line fingerprint analytics@alexsong-oai[@alexsong-oai](https://github.com/alexsong-oai)
- #21465[#21465](https://github.com/openai/codex/pull/21465)Remove ToolName display helper@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #20619[#20619](https://github.com/openai/codex/pull/20619)[codex] request desktop attestation from app@jiamingz42[@jiamingz42](https://github.com/jiamingz42)
- #21810[#21810](https://github.com/openai/codex/pull/21810)Revert "Publish Python runtime wheels on release"@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #21651[#21651](https://github.com/openai/codex/pull/21651)[codex] Delete function-style apply_patch@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #21805[#21805](https://github.com/openai/codex/pull/21805)[codex] Remove legacy after tool use hooks@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #21616[#21616](https://github.com/openai/codex/pull/21616)Enable`--deny-warnings`for`cargo shear`@charliemarsh-oai[@charliemarsh-oai](https://github.com/charliemarsh-oai)
- #21497[#21497](https://github.com/openai/codex/pull/21497)Using cached connector directory for discoverable tools list@mzeng-openai[@mzeng-openai](https://github.com/mzeng-openai)
- #21835[#21835](https://github.com/openai/codex/pull/21835)ci: check out PR head commits in workflows@bolinfest[@bolinfest](https://github.com/bolinfest)
- #21794[#21794](https://github.com/openai/codex/pull/21794)Make environment provider snapshots path-free@starr-openai[@starr-openai](https://github.com/starr-openai)
- #21831[#21831](https://github.com/openai/codex/pull/21831)app-server: support daemon-safe restart handling@euroelessar[@euroelessar](https://github.com/euroelessar)
- #20293[#20293](https://github.com/openai/codex/pull/20293)Support openai library tool@lt-oai[@lt-oai](https://github.com/lt-oai)
- #21323[#21323](https://github.com/openai/codex/pull/21323)[codex] support executor registry remote environments@miz-openai[@miz-openai](https://github.com/miz-openai)
- #21825[#21825](https://github.com/openai/codex/pull/21825)Increase exec-server environment transport timeouts@starr-openai[@starr-openai](https://github.com/starr-openai)
- #20718[#20718](https://github.com/openai/codex/pull/20718)[daemon] Add app-server daemon lifecycle management@euroelessar[@euroelessar](https://github.com/euroelessar)
- #21840[#21840](https://github.com/openai/codex/pull/21840)feat: add Bedrock Mantle client agent header@celia-oai[@celia-oai](https://github.com/celia-oai)
- #21847[#21847](https://github.com/openai/codex/pull/21847)sqlite: no more destructive version bumps@owenlin0[@owenlin0](https://github.com/owenlin0)
- #21652[#21652](https://github.com/openai/codex/pull/21652)Reapply "Move skills watcher to app-server"@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #21290[#21290](https://github.com/openai/codex/pull/21290)Move file watcher out of core@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #21867[#21867](https://github.com/openai/codex/pull/21867)feat: Add role-aware plugin share context APIs@xl-openai[@xl-openai](https://github.com/xl-openai)
- #21875[#21875](https://github.com/openai/codex/pull/21875)[codex] compact network context rendering@sayan-oai[@sayan-oai](https://github.com/sayan-oai)
- #21778[#21778](https://github.com/openai/codex/pull/21778)Route Python SDK turn notifications by ID@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #21906[#21906](https://github.com/openai/codex/pull/21906)[codex] Lowercase TUI service tier commands@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #21819[#21819](https://github.com/openai/codex/pull/21819)tests: cover sandbox link write behavior@bolinfest[@bolinfest](https://github.com/bolinfest)
- #21760[#21760](https://github.com/openai/codex/pull/21760)fix(tui): preserve wrapped prose beside URLs@fcoury-oai[@fcoury-oai](https://github.com/fcoury-oai)
- #21950[#21950](https://github.com/openai/codex/pull/21950)fix(tui): improve light-mode selection contrast@fcoury-oai[@fcoury-oai](https://github.com/fcoury-oai)
- #21755[#21755](https://github.com/openai/codex/pull/21755)Improve hooks trust flow in TUI@abhinav-oai[@abhinav-oai](https://github.com/abhinav-oai)
- #21870[#21870](https://github.com/openai/codex/pull/21870)Avoid blocking TUI on agent metadata hydration@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #21866[#21866](https://github.com/openai/codex/pull/21866)Split ChatWidget state into focused modules@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #21991[#21991](https://github.com/openai/codex/pull/21991)Persist 'priority' service tier as fast in config@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #21943[#21943](https://github.com/openai/codex/pull/21943)fix(tui): preserve Shift+Enter in tmux csi-u panes@fcoury-oai[@fcoury-oai](https://github.com/fcoury-oai)
- #21759[#21759](https://github.com/openai/codex/pull/21759)fix(tui): suppress taskkill output for MCP teardown on Windows@fcoury-oai[@fcoury-oai](https://github.com/fcoury-oai)
- #22039[#22039](https://github.com/openai/codex/pull/22039)Deduplicate issue digest interactions by user@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #22052[#22052](https://github.com/openai/codex/pull/22052)feat(tui): render responsive Markdown tables in TUI@fcoury-oai[@fcoury-oai](https://github.com/fcoury-oai)
- #20825[#20825](https://github.com/openai/codex/pull/20825)Read cached metadata for installed Git plugins@xli-oai[@xli-oai](https://github.com/xli-oai)
- #21736[#21736](https://github.com/openai/codex/pull/21736)extension: add initial typed extension API@jif-oai[@jif-oai](https://github.com/jif-oai)
- #21737[#21737](https://github.com/openai/codex/pull/21737)extension: wire extension registries into sessions@jif-oai[@jif-oai](https://github.com/jif-oai)
- #21738[#21738](https://github.com/openai/codex/pull/21738)extension: move git attribution into an extension@jif-oai[@jif-oai](https://github.com/jif-oai)
- #22138[#22138](https://github.com/openai/codex/pull/22138)refactor: extract executable tool contracts into codex-tool-api@jif-oai[@jif-oai](https://github.com/jif-oai)
- #22140[#22140](https://github.com/openai/codex/pull/22140)feat: drop`CodexExtension`@jif-oai[@jif-oai](https://github.com/jif-oai)
- #22143[#22143](https://github.com/openai/codex/pull/22143)[codex] default unknown contributed tools to mutating@jif-oai[@jif-oai](https://github.com/jif-oai)
- #22147[#22147](https://github.com/openai/codex/pull/22147)feat: wire extension tool bundles into core@jif-oai[@jif-oai](https://github.com/jif-oai)
- #22163[#22163](https://github.com/openai/codex/pull/22163)feat: move extensions tool@jif-oai[@jif-oai](https://github.com/jif-oai)
- #22113[#22113](https://github.com/openai/codex/pull/22113)Add x-codex-ws-stream-request-start-ms@andmis[@andmis](https://github.com/andmis)
- #21860[#21860](https://github.com/openai/codex/pull/21860)Persist /goal commands in history@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #22141[#22141](https://github.com/openai/codex/pull/22141)[codex] Harden overflow auto-compaction recovery@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #22170[#22170](https://github.com/openai/codex/pull/22170)Revert "[codex] Harden overflow auto-compaction recovery"@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #22106[#22106](https://github.com/openai/codex/pull/22106)Fix side conversation config inheritance@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #22045[#22045](https://github.com/openai/codex/pull/22045)Improve goal continuation based on feedback@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #21981[#21981](https://github.com/openai/codex/pull/21981)Use goal preview metadata for goal-first threads@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #21843[#21843](https://github.com/openai/codex/pull/21843)app-server: remove TCP websocket listener@euroelessar[@euroelessar](https://github.com/euroelessar)
- #22173[#22173](https://github.com/openai/codex/pull/22173)chore: drop built-in MCPs@jif-oai[@jif-oai](https://github.com/jif-oai)
- #21954[#21954](https://github.com/openai/codex/pull/21954)Fix goal update and add`/goal edit`command in TUI@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #22110[#22110](https://github.com/openai/codex/pull/22110)Make auto-review denial short-circuit use a rolling review window@won-openai[@won-openai](https://github.com/won-openai)
- #21431[#21431](https://github.com/openai/codex/pull/21431)[codex-analytics] add turn tool counts to turn events@rhan-oai[@rhan-oai](https://github.com/rhan-oai)
- #22154[#22154](https://github.com/openai/codex/pull/22154)Add process-scoped SQLite telemetry@jif-oai[@jif-oai](https://github.com/jif-oai)
- #19068[#19068](https://github.com/openai/codex/pull/19068)Unified mentions in TUI@canvrno-oai[@canvrno-oai](https://github.com/canvrno-oai)
- #20305[#20305](https://github.com/openai/codex/pull/20305)fix(exec-policy) use is_known_safe_command less@dylan-hurd-oai[@dylan-hurd-oai](https://github.com/dylan-hurd-oai)
- #22058[#22058](https://github.com/openai/codex/pull/22058)fix(exec-server): suppress Windows taskkill output@fcoury-oai[@fcoury-oai](https://github.com/fcoury-oai)
- #22178[#22178](https://github.com/openai/codex/pull/22178)fix(app-server): thread history redaction for remote clients@owenlin0[@owenlin0](https://github.com/owenlin0)
- #15977[#15977](https://github.com/openai/codex/pull/15977)fix(permissions): preserve managed deny-read during escalation@viyatb-oai[@viyatb-oai](https://github.com/viyatb-oai)
- #21061[#21061](https://github.com/openai/codex/pull/21061)feat(connectors): support managed app tool approval requirements@viyatb-oai[@viyatb-oai](https://github.com/viyatb-oai)
- #22188[#22188](https://github.com/openai/codex/pull/22188)[elicitation] Advertise new url elicitation capability when auth_elicitation is enabled.@mzeng-openai[@mzeng-openai](https://github.com/mzeng-openai)
- #22192[#22192](https://github.com/openai/codex/pull/22192)config: accept`minus`in TUI keymap config@fcoury-oai[@fcoury-oai](https://github.com/fcoury-oai)
- #21853[#21853](https://github.com/openai/codex/pull/21853)daemon: refresh updater after validated binary rollout@euroelessar[@euroelessar](https://github.com/euroelessar)
- #21747[#21747](https://github.com/openai/codex/pull/21747)[login] revoke superseded auth tokens on relogin@cooper-oai[@cooper-oai](https://github.com/cooper-oai)
- #20147[#20147](https://github.com/openai/codex/pull/20147)feat: add network proxy feature flag@viyatb-oai[@viyatb-oai](https://github.com/viyatb-oai)
- #21891[#21891](https://github.com/openai/codex/pull/21891)[1/8] Pin Python SDK runtime dependency@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #21893[#21893](https://github.com/openai/codex/pull/21893)[2/8] Generate Python SDK types from pinned runtime@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #21895[#21895](https://github.com/openai/codex/pull/21895)[3/8] Run Python SDK tests in CI@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #21896[#21896](https://github.com/openai/codex/pull/21896)[4/8] Define Python SDK public API surface@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #21905[#21905](https://github.com/openai/codex/pull/21905)[5/8] Rename Python SDK package to openai-codex@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #21910[#21910](https://github.com/openai/codex/pull/21910)[6/8] Add high-level Python SDK approval mode@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #22014[#22014](https://github.com/openai/codex/pull/22014)[7/8] Add Python SDK app-server integration harness@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #22021[#22021](https://github.com/openai/codex/pull/22021)[8/8] Add Python SDK Ruff formatting@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #18748[#18748](https://github.com/openai/codex/pull/18748)[codex-analytics] emit terminal review events@rhan-oai[@rhan-oai](https://github.com/rhan-oai)
- #22159[#22159](https://github.com/openai/codex/pull/22159)Add Windows hook command overrides@abhinav-oai[@abhinav-oai](https://github.com/abhinav-oai)
- #22218[#22218](https://github.com/openai/codex/pull/22218)Update codex remote-control to start the daemon@owenlin0[@owenlin0](https://github.com/owenlin0)
- #22180[#22180](https://github.com/openai/codex/pull/22180)Stop uploading accepted line fingerprints@alexsong-oai[@alexsong-oai](https://github.com/alexsong-oai)
- #21617[#21617](https://github.com/openai/codex/pull/21617)Support multi-environment apply_patch selection@starr-openai[@starr-openai](https://github.com/starr-openai)
- #22198[#22198](https://github.com/openai/codex/pull/22198)Add production startup and TTFT telemetry@mzeng-openai[@mzeng-openai](https://github.com/mzeng-openai)
- #21963[#21963](https://github.com/openai/codex/pull/21963)[exec-server] serve websocket listener via HTTP upgrade@euroelessar[@euroelessar](https://github.com/euroelessar)
- #21946[#21946](https://github.com/openai/codex/pull/21946)fix(tui): handle hidden app git directives@fcoury-oai[@fcoury-oai](https://github.com/fcoury-oai)
- #21595[#21595](https://github.com/openai/codex/pull/21595)Simplify MCP tool handler plumbing@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #22221[#22221](https://github.com/openai/codex/pull/22221)feat(skills): default plugin creator to personal share flow@efrazer-oai[@efrazer-oai](https://github.com/efrazer-oai)
- #21861[#21861](https://github.com/openai/codex/pull/21861)Apply sandbox context to local view_image reads@starr-openai[@starr-openai](https://github.com/starr-openai)
- #20527[#20527](https://github.com/openai/codex/pull/20527)Support PreToolUse updatedInput rewrites@abhinav-oai[@abhinav-oai](https://github.com/abhinav-oai)
- #22243[#22243](https://github.com/openai/codex/pull/22243)[codex] Filter legacy warning messages during compaction@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #22254[#22254](https://github.com/openai/codex/pull/22254)[codex] Make handlers own parallel tool support@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #18202[#18202](https://github.com/openai/codex/pull/18202)feat(sandbox): add Windows deny-read parity@viyatb-oai[@viyatb-oai](https://github.com/viyatb-oai)
- #22265[#22265](https://github.com/openai/codex/pull/22265)feat: Normalize remote plugin summary identities.@xl-openai[@xl-openai](https://github.com/xl-openai)
- #22216[#22216](https://github.com/openai/codex/pull/22216)feat: guardian as an extension (contributors part)@jif-oai[@jif-oai](https://github.com/jif-oai)
- #22311[#22311](https://github.com/openai/codex/pull/22311)[rollout-trace] Add x-codex-inference-call-id header to inference calls.@cassirer-openai[@cassirer-openai](https://github.com/cassirer-openai)
- #21206[#21206](https://github.com/openai/codex/pull/21206)feat(tui): add ambient terminal pets@fcoury-oai[@fcoury-oai](https://github.com/fcoury-oai)
- #22323[#22323](https://github.com/openai/codex/pull/22323)fix: uv lock@jif-oai[@jif-oai](https://github.com/jif-oai)
- #22207[#22207](https://github.com/openai/codex/pull/22207)[codex] Tighten unified exec sandbox setup@bookholt-oai[@bookholt-oai](https://github.com/bookholt-oai)
- #22382[#22382](https://github.com/openai/codex/pull/22382)tools: remove is_mutating dispatch gating@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #22383[#22383](https://github.com/openai/codex/pull/22383)chore(config) include_collaboration_mode_instructions@dylan-hurd-oai[@dylan-hurd-oai](https://github.com/dylan-hurd-oai)
- #22377[#22377](https://github.com/openai/codex/pull/22377)code-mode: carry nested tool kind through runtime@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #22392[#22392](https://github.com/openai/codex/pull/22392)test(tui): relax configured pet load timeout@fcoury-oai[@fcoury-oai](https://github.com/fcoury-oai)
- #22343[#22343](https://github.com/openai/codex/pull/22343)feat(exec-server): use protobuf relay frames@apanasenko-oai[@apanasenko-oai](https://github.com/apanasenko-oai)
- #20509[#20509](https://github.com/openai/codex/pull/20509)[codex] Remove workspace owner usage nudge gate@richardopenai[@richardopenai](https://github.com/richardopenai)
- #22256[#22256](https://github.com/openai/codex/pull/22256)Refactor namespaced tool spec registration@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #22280[#22280](https://github.com/openai/codex/pull/22280)code-mode: Add pending-aware code mode execution@cconger[@cconger](https://github.com/cconger)
- #22266[#22266](https://github.com/openai/codex/pull/22266)core: box multi-agent handler futures@bolinfest[@bolinfest](https://github.com/bolinfest)
- #22398[#22398](https://github.com/openai/codex/pull/22398)[codex] Add search term coverage for tool_search@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #22236[#22236](https://github.com/openai/codex/pull/22236)Unify thread metadata updates above store@wiltzius-openai[@wiltzius-openai](https://github.com/wiltzius-openai)
- #22269[#22269](https://github.com/openai/codex/pull/22269)Refactor chatwidget state into modules@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #22381[#22381](https://github.com/openai/codex/pull/22381)[codex] Remove tool search bucket limit override@sayan-oai[@sayan-oai](https://github.com/sayan-oai)
- #22386[#22386](https://github.com/openai/codex/pull/22386)mark Feature::RemoteControl as removed@owenlin0[@owenlin0](https://github.com/owenlin0)
- #22240[#22240](https://github.com/openai/codex/pull/22240)docs(skills): simplify plugin creator deeplink shape@efrazer-oai[@efrazer-oai](https://github.com/efrazer-oai)
- #22397[#22397](https://github.com/openai/codex/pull/22397)feat: Expose plugin versions and gate plugin sharing@xl-openai[@xl-openai](https://github.com/xl-openai)
- #22404[#22404](https://github.com/openai/codex/pull/22404)Restore app-server websocket listener with auth guard@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #22258[#22258](https://github.com/openai/codex/pull/22258)feat: route guardian review model selection through providers@celia-oai[@celia-oai](https://github.com/celia-oai)
- #22268[#22268](https://github.com/openai/codex/pull/22268)hooks: use new session IDs instead of thread IDs for hooks, apply parent's session ID to subagents' hooks@eternal-openai[@eternal-openai](https://github.com/eternal-openai)
- #20319[#20319](https://github.com/openai/codex/pull/20319)Add allow_managed_hooks_only hook requirement@eternal-openai[@eternal-openai](https://github.com/eternal-openai)
- #22413[#22413](https://github.com/openai/codex/pull/22413)Remove CODEX_RS_SSE_FIXTURE test hook@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #22406[#22406](https://github.com/openai/codex/pull/22406)tools: infer code-mode namespace descriptions from specs@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #22261[#22261](https://github.com/openai/codex/pull/22261)Encapsulate tool search entries in handlers@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #22425[#22425](https://github.com/openai/codex/pull/22425)feat: Split shared workspace plugins by discoverability@xl-openai[@xl-openai](https://github.com/xl-openai)
- #22414[#22414](https://github.com/openai/codex/pull/22414)Add support for UDS in`codex --remote`@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #22407[#22407](https://github.com/openai/codex/pull/22407)Refactor chatwidget input flow into modules@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #22439[#22439](https://github.com/openai/codex/pull/22439)Remove unavailable MCP placeholder tool backfill@sayan-oai[@sayan-oai](https://github.com/sayan-oai)
- #21969[#21969](https://github.com/openai/codex/pull/21969)Use root repo hooks in linked worktrees@abhinav-oai[@abhinav-oai](https://github.com/abhinav-oai)
- #21768[#21768](https://github.com/openai/codex/pull/21768)add --dangerously-bypass-hook-trust CLI flag@abhinav-oai[@abhinav-oai](https://github.com/abhinav-oai)
- #22435[#22435](https://github.com/openai/codex/pull/22435)feat: Add plugin share checkout@xl-openai[@xl-openai](https://github.com/xl-openai)
- #22355[#22355](https://github.com/openai/codex/pull/22355)chore: Keep view_image sandbox test in temp dir@jif-oai[@jif-oai](https://github.com/jif-oai)
- #22344[#22344](https://github.com/openai/codex/pull/22344)extension-api: add approval review contributor flow@jif-oai[@jif-oai](https://github.com/jif-oai)
- #22359[#22359](https://github.com/openai/codex/pull/22359)feat: extract shared tool executor interface@jif-oai[@jif-oai](https://github.com/jif-oai)
- #22369[#22369](https://github.com/openai/codex/pull/22369)Refactor extension tools onto shared ToolExecutor@jif-oai[@jif-oai](https://github.com/jif-oai)
- #22338[#22338](https://github.com/openai/codex/pull/22338)[app-server] Gate login issuer override constant@cassirer-openai[@cassirer-openai](https://github.com/cassirer-openai)
- #22437[#22437](https://github.com/openai/codex/pull/22437)[codex] isolate plugin/list from config serialization queue@xli-oai[@xli-oai](https://github.com/xli-oai)
- #22476[#22476](https://github.com/openai/codex/pull/22476)feat: add thread lifecycle contributor hooks@jif-oai[@jif-oai](https://github.com/jif-oai)
- #22479[#22479](https://github.com/openai/codex/pull/22479)nit: codeowners@jif-oai[@jif-oai](https://github.com/jif-oai)
- #22480[#22480](https://github.com/openai/codex/pull/22480)feat: add turn lifecycle contributors@jif-oai[@jif-oai](https://github.com/jif-oai)
- #22482[#22482](https://github.com/openai/codex/pull/22482)fix: emit thread stop lifecycle on implicit shutdown@jif-oai[@jif-oai](https://github.com/jif-oai)
- #22485[#22485](https://github.com/openai/codex/pull/22485)feat: add token usage contributor hook@jif-oai[@jif-oai](https://github.com/jif-oai)
- #22443[#22443](https://github.com/openai/codex/pull/22443)Scope macOS signing secrets to release environment@shijie-oai[@shijie-oai](https://github.com/shijie-oai)
- #22490[#22490](https://github.com/openai/codex/pull/22490)feat: move extension scope ids into ExtensionData@jif-oai[@jif-oai](https://github.com/jif-oai)
- #22491[#22491](https://github.com/openai/codex/pull/22491)Make context contributors async@jif-oai[@jif-oai](https://github.com/jif-oai)
- #22214[#22214](https://github.com/openai/codex/pull/22214)feat(tui): remove Zellij TUI workarounds@fcoury-oai[@fcoury-oai](https://github.com/fcoury-oai)
- #22139[#22139](https://github.com/openai/codex/pull/22139)Add service tier overrides to spawned agents@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #22488[#22488](https://github.com/openai/codex/pull/22488)feat: add config-change extension contributor@jif-oai[@jif-oai](https://github.com/jif-oai)
- #22498[#22498](https://github.com/openai/codex/pull/22498)feat: memories ext@jif-oai[@jif-oai](https://github.com/jif-oai)
- #22503[#22503](https://github.com/openai/codex/pull/22503)fix: main@jif-oai[@jif-oai](https://github.com/jif-oai)
- #22347[#22347](https://github.com/openai/codex/pull/22347)feat(tui): standardize picker navigation keys@fcoury-oai[@fcoury-oai](https://github.com/fcoury-oai)
- #22500[#22500](https://github.com/openai/codex/pull/22500)refactor: split memories extension crate modules@jif-oai[@jif-oai](https://github.com/jif-oai)
- #22433[#22433](https://github.com/openai/codex/pull/22433)Refactor chatwidget protocol flows into modules (phase 3)@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #22505[#22505](https://github.com/openai/codex/pull/22505)fix: prevent fmt from updating Python SDK lockfile@jif-oai[@jif-oai](https://github.com/jif-oai)
- #22326[#22326](https://github.com/openai/codex/pull/22326)[rollout-trace] Add a trace ID to MCP calls.@cassirer-openai[@cassirer-openai](https://github.com/cassirer-openai)
- #20559[#20559](https://github.com/openai/codex/pull/20559)config: add strict config parsing@bolinfest[@bolinfest](https://github.com/bolinfest)
- #22489[#22489](https://github.com/openai/codex/pull/22489)Introduce tool exposure for deferred registration@jif-oai[@jif-oai](https://github.com/jif-oai)
- #22193[#22193](https://github.com/openai/codex/pull/22193)fix: drop underscored id headers@jif-oai[@jif-oai](https://github.com/jif-oai)
- #22246[#22246](https://github.com/openai/codex/pull/22246)[codex] Remove unused legacy shell tools@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #22520[#22520](https://github.com/openai/codex/pull/22520)revert: mark Feature::RemoteControl as removed@owenlin0[@owenlin0](https://github.com/owenlin0)
- #22513[#22513](https://github.com/openai/codex/pull/22513)Revert "Scope macOS signing secrets to release environment"@shijie-oai[@shijie-oai](https://github.com/shijie-oai)
- #22514[#22514](https://github.com/openai/codex/pull/22514)feat: expose multi-agent v2 as model-only tools@jif-oai[@jif-oai](https://github.com/jif-oai)
- #22366[#22366](https://github.com/openai/codex/pull/22366)Pass Codex product SKU to ChatGPT backend@ericning-o[@ericning-o](https://github.com/ericning-o)
- #22519[#22519](https://github.com/openai/codex/pull/22519)Deprecate TurnContext cwd and resolve_path@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #22518[#22518](https://github.com/openai/codex/pull/22518)Refactor chatwidget settings surfaces into modules (phase 4)@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #21479[#21479](https://github.com/openai/codex/pull/21479)[codex] Scope Windows sandbox write-root capability SIDs@adrianbravo-oai[@adrianbravo-oai](https://github.com/adrianbravo-oai)
- #22353[#22353](https://github.com/openai/codex/pull/22353)windows-sandbox: fail elevated setup when firewall policy is ineffective@iceweasel-oai[@iceweasel-oai](https://github.com/iceweasel-oai)
- #22527[#22527](https://github.com/openai/codex/pull/22527)[codex] Reuse Apps MCP path override for plugin-service rollout@adaley-openai[@adaley-openai](https://github.com/adaley-openai)
- #22412[#22412](https://github.com/openai/codex/pull/22412)chore(config) rm Feature::CodexGitCommit@dylan-hurd-oai[@dylan-hurd-oai](https://github.com/dylan-hurd-oai)
- #22501[#22501](https://github.com/openai/codex/pull/22501)chore(config) rm tools.view_image@dylan-hurd-oai[@dylan-hurd-oai](https://github.com/dylan-hurd-oai)
- #22533[#22533](https://github.com/openai/codex/pull/22533)fix: prevent codex-backend from stealing originator@owenlin0[@owenlin0](https://github.com/owenlin0)
- #22408[#22408](https://github.com/openai/codex/pull/22408)Shard Bazel Windows tests across jobs@starr-openai[@starr-openai](https://github.com/starr-openai)
- #22542[#22542](https://github.com/openai/codex/pull/22542)Use selected environment cwd for filesystem helpers@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #20237[#20237](https://github.com/openai/codex/pull/20237)Add callback ids to local MCP OAuth redirects@stevenlee-oai[@stevenlee-oai](https://github.com/stevenlee-oai)
- #22549[#22549](https://github.com/openai/codex/pull/22549)Enable plugin hooks by default@abhinav-oai[@abhinav-oai](https://github.com/abhinav-oai)
- #22375[#22375](https://github.com/openai/codex/pull/22375)Use plugin/list to get list of plugins for mentions@canvrno-oai[@canvrno-oai](https://github.com/canvrno-oai)
- #21235[#21235](https://github.com/openai/codex/pull/21235)[codex] Fix TUI wrapping for external borrowed slices@canvrno-oai[@canvrno-oai](https://github.com/canvrno-oai)
- #22336[#22336](https://github.com/openai/codex/pull/22336)feat(cli): add codex doctor diagnostics@fcoury-oai[@fcoury-oai](https://github.com/fcoury-oai)
- #22543[#22543](https://github.com/openai/codex/pull/22543)clean up instructions@sayan-oai[@sayan-oai](https://github.com/sayan-oai)
- #21400[#21400](https://github.com/openai/codex/pull/21400)Avoid PowerShell profiles in elevated Windows sandbox@iceweasel-oai[@iceweasel-oai](https://github.com/iceweasel-oai)
- #22528[#22528](https://github.com/openai/codex/pull/22528)Make multi_agent_v2 wait_agent timeouts configurable@andmis[@andmis](https://github.com/andmis)
- #22529[#22529](https://github.com/openai/codex/pull/22529)Spill oversized PreToolUse additionalContext@abhinav-oai[@abhinav-oai](https://github.com/abhinav-oai)
- #22556[#22556](https://github.com/openai/codex/pull/22556)feat: namespace in ext@jif-oai[@jif-oai](https://github.com/jif-oai)
- #22535[#22535](https://github.com/openai/codex/pull/22535)Remove resurrected`/collab`slash command@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #22537[#22537](https://github.com/openai/codex/pull/22537)Refactor chatwidget orchestration into modules (phase 5)@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #22564[#22564](https://github.com/openai/codex/pull/22564)[codex] Canonicalize shared workspace plugin IDs@xl-openai[@xl-openai](https://github.com/xl-openai)
- #22559[#22559](https://github.com/openai/codex/pull/22559)Add unsigned macOS release artifacts@shijie-oai[@shijie-oai](https://github.com/shijie-oai)
- #22574[#22574](https://github.com/openai/codex/pull/22574)Deprecate issue labeler@maxb-openai[@maxb-openai](https://github.com/maxb-openai)
- #22555[#22555](https://github.com/openai/codex/pull/22555)Remove connector_openai prefix filtering@ericning-o[@ericning-o](https://github.com/ericning-o)
- #22580[#22580](https://github.com/openai/codex/pull/22580)fix: Block appserver startup if state db can't be opened@ddr-oai[@ddr-oai](https://github.com/ddr-oai)
- #22565[#22565](https://github.com/openai/codex/pull/22565)chore(config) rm experimental_use_freeform_apply_patch@dylan-hurd-oai[@dylan-hurd-oai](https://github.com/dylan-hurd-oai)
- #22562[#22562](https://github.com/openai/codex/pull/22562)Improve remote-control daemon UX@owenlin0[@owenlin0](https://github.com/owenlin0)
- #22578[#22578](https://github.com/openai/codex/pull/22578)enable/disable remote control at runtime, not via features@owenlin0[@owenlin0](https://github.com/owenlin0)
- #22573[#22573](https://github.com/openai/codex/pull/22573)Simplify TUI startup test coverage@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #22594[#22594](https://github.com/openai/codex/pull/22594)Relax remote plugin sync gate@xli-oai[@xli-oai](https://github.com/xli-oai)
- #22587[#22587](https://github.com/openai/codex/pull/22587)Defer startup NUX impressions until startup succeeds@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #22560[#22560](https://github.com/openai/codex/pull/22560)feat: make ToolExecutor an async trait@jif-oai[@jif-oai](https://github.com/jif-oai)
- #22494[#22494](https://github.com/openai/codex/pull/22494)Wire turn item contributors into stream output@jif-oai[@jif-oai](https://github.com/jif-oai)
- #17141[#17141](https://github.com/openai/codex/pull/17141)feat: add layered --profile-v2 config files@jif-oai[@jif-oai](https://github.com/jif-oai)
- #22643[#22643](https://github.com/openai/codex/pull/22643)[codex] treat PowerShell stop-parsing forms as unsupported@bookholt-oai[@bookholt-oai](https://github.com/bookholt-oai)
- #22646[#22646](https://github.com/openai/codex/pull/22646)Fix abort-path turn extension data plumbing@jif-oai[@jif-oai](https://github.com/jif-oai)
- #22624[#22624](https://github.com/openai/codex/pull/22624)permissions: canonicalize workspace_roots and danger-full-access names@bolinfest[@bolinfest](https://github.com/bolinfest)
- #22649[#22649](https://github.com/openai/codex/pull/22649)Chore: better published unsigned artifacts@shijie-oai[@shijie-oai](https://github.com/shijie-oai)
- #22581[#22581](https://github.com/openai/codex/pull/22581)tui: split composer attachment and popup state@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #21396[#21396](https://github.com/openai/codex/pull/21396)[codex] add plugin marketplace CLI commands@caseychow-oai[@caseychow-oai](https://github.com/caseychow-oai)
- #22576[#22576](https://github.com/openai/codex/pull/22576)tests: avoid ambient temp sandbox roots@starr-openai[@starr-openai](https://github.com/starr-openai)
- #22652[#22652](https://github.com/openai/codex/pull/22652)[codex] Ignore fsmonitor config in Git metadata reads@bookholt-oai[@bookholt-oai](https://github.com/bookholt-oai)
- #22229[#22229](https://github.com/openai/codex/pull/22229)fix(tui): render network approval history by target@fcoury-oai[@fcoury-oai](https://github.com/fcoury-oai)
- #22547[#22547](https://github.com/openai/codex/pull/22547)Prefer the model list fetched from the backend for SIWC users@jeevnayak[@jeevnayak](https://github.com/jeevnayak)
- #22666[#22666](https://github.com/openai/codex/pull/22666)[codex] fix plugin CLI active user layer compile@caseychow-oai[@caseychow-oai](https://github.com/caseychow-oai)
- #22575[#22575](https://github.com/openai/codex/pull/22575)Support explicit MCP OAuth client IDs@mzeng-openai[@mzeng-openai](https://github.com/mzeng-openai)
- #22512[#22512](https://github.com/openai/codex/pull/22512)test: isolate exec review policy config test@bolinfest[@bolinfest](https://github.com/bolinfest)
- #22572[#22572](https://github.com/openai/codex/pull/22572)Fix remote environment test fixtures@starr-openai[@starr-openai](https://github.com/starr-openai)
- #22563[#22563](https://github.com/openai/codex/pull/22563)tests: isolate codex home for live cli@starr-openai[@starr-openai](https://github.com/starr-openai)
- #18161[#18161](https://github.com/openai/codex/pull/18161)[codex] Support multiple forced ChatGPT workspaces@rreichel3-oai[@rreichel3-oai](https://github.com/rreichel3-oai)
- #22702[#22702](https://github.com/openai/codex/pull/22702)make rust-release-prepare use env secret@sayan-oai[@sayan-oai](https://github.com/sayan-oai)
- #22703[#22703](https://github.com/openai/codex/pull/22703)Unqueue plugin list and read requests@xli-oai[@xli-oai](https://github.com/xli-oai)
- #22687[#22687](https://github.com/openai/codex/pull/22687)Fix Windows sandbox clippy clones@starr-openai[@starr-openai](https://github.com/starr-openai)
- #22711[#22711](https://github.com/openai/codex/pull/22711)chore(features) rm Feature::ApplyPatchFreeform@dylan-hurd-oai[@dylan-hurd-oai](https://github.com/dylan-hurd-oai)
- #22717[#22717](https://github.com/openai/codex/pull/22717)chore(config) rm windows_wsl_setup_acknowledged@dylan-hurd-oai[@dylan-hurd-oai](https://github.com/dylan-hurd-oai)
- #22695[#22695](https://github.com/openai/codex/pull/22695)Trim TUI legacy core helper usage@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #21624[#21624](https://github.com/openai/codex/pull/21624)Fix /review mode MCP startup render issue@canvrno-oai[@canvrno-oai](https://github.com/canvrno-oai)
- #22684[#22684](https://github.com/openai/codex/pull/22684)Remove SSE fixture loaders@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #22730[#22730](https://github.com/openai/codex/pull/22730)[codex] Group removed feature flags@dylan-hurd-oai[@dylan-hurd-oai](https://github.com/dylan-hurd-oai)
- #22724[#22724](https://github.com/openai/codex/pull/22724)[codex] Remove experimental instructions file config@dylan-hurd-oai[@dylan-hurd-oai](https://github.com/dylan-hurd-oai)
- #22237[#22237](https://github.com/openai/codex/pull/22237)Add`user_input_requested_during_turn`to MCP turn metadata@mchen-oai[@mchen-oai](https://github.com/mchen-oai)
- #22737[#22737](https://github.com/openai/codex/pull/22737)ci: support signed macOS release promotion@bolinfest[@bolinfest](https://github.com/bolinfest)
- #22303[#22303](https://github.com/openai/codex/pull/22303)Stabilize compact rollback follow-up test@dylan-hurd-oai[@dylan-hurd-oai](https://github.com/dylan-hurd-oai)
- #22683[#22683](https://github.com/openai/codex/pull/22683)permissions: resolve profile identity with constraints@bolinfest[@bolinfest](https://github.com/bolinfest)
- #22734[#22734](https://github.com/openai/codex/pull/22734)tui: recover local state db startup failures@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #22584[#22584](https://github.com/openai/codex/pull/22584)[codex] Add opaque desktop config namespace@guinness-oai[@guinness-oai](https://github.com/guinness-oai)
- #22710[#22710](https://github.com/openai/codex/pull/22710)Prevent Esc from dismissing or rewinding`/side`@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #22704[#22704](https://github.com/openai/codex/pull/22704)TUI: split history cells into focused modules@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #22611[#22611](https://github.com/openai/codex/pull/22611)app-server: use permission ids and runtime workspace roots@bolinfest[@bolinfest](https://github.com/bolinfest)
- #22612[#22612](https://github.com/openai/codex/pull/22612)tui/exec: show effective workspace roots in summaries@bolinfest[@bolinfest](https://github.com/bolinfest)
- #22788[#22788](https://github.com/openai/codex/pull/22788)Fix signed macOS release promotion follow-up jobs@shijie-oai[@shijie-oai](https://github.com/shijie-oai)
- #22647[#22647](https://github.com/openai/codex/pull/22647)Reject legacy [profiles] when using profile-v2@jif-oai[@jif-oai](https://github.com/jif-oai)
- #22809[#22809](https://github.com/openai/codex/pull/22809)[codex] Use compaction_trigger item for remote compaction v2@jif-oai[@jif-oai](https://github.com/jif-oai)
- #22636[#22636](https://github.com/openai/codex/pull/22636)Simplify tool executor and registry plumbing@jif-oai[@jif-oai](https://github.com/jif-oai)
- #22820[#22820](https://github.com/openai/codex/pull/22820)Remove zombie tools spec module@jif-oai[@jif-oai](https://github.com/jif-oai)
- #22828[#22828](https://github.com/openai/codex/pull/22828)Run compact hooks for remote compaction v2@jif-oai[@jif-oai](https://github.com/jif-oai)
- #22841[#22841](https://github.com/openai/codex/pull/22841)Move memory prompt injection to app-server extension@jif-oai[@jif-oai](https://github.com/jif-oai)
- #22789[#22789](https://github.com/openai/codex/pull/22789)guardian: use permission profile for review sandbox@bolinfest[@bolinfest](https://github.com/bolinfest)
- #22656[#22656](https://github.com/openai/codex/pull/22656)tui: split remaining composer draft and footer state@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #22843[#22843](https://github.com/openai/codex/pull/22843)Ignore configured hooks in git helpers@bookholt-oai[@bookholt-oai](https://github.com/bookholt-oai)
- #22790[#22790](https://github.com/openai/codex/pull/22790)context: remove legacy permissions instructions helper@bolinfest[@bolinfest](https://github.com/bolinfest)
- #22791[#22791](https://github.com/openai/codex/pull/22791)telemetry: tag sandboxes from permission profiles@bolinfest[@bolinfest](https://github.com/bolinfest)
- #22872[#22872](https://github.com/openai/codex/pull/22872)Forward apps MCP product SKU from Codex config@kumquatexpress[@kumquatexpress](https://github.com/kumquatexpress)
- #22582[#22582](https://github.com/openai/codex/pull/22582)Workflow updates@viyatb-oai[@viyatb-oai](https://github.com/viyatb-oai)
- #22792[#22792](https://github.com/openai/codex/pull/22792)app-server: stop returning thread permission profiles@bolinfest[@bolinfest](https://github.com/bolinfest)
- #22795[#22795](https://github.com/openai/codex/pull/22795)core: construct test permission profiles directly@bolinfest[@bolinfest](https://github.com/bolinfest)
- #22900[#22900](https://github.com/openai/codex/pull/22900)Disable DMG staging for signed macOS promotion@shijie-oai[@shijie-oai](https://github.com/shijie-oai)
- #22877[#22877](https://github.com/openai/codex/pull/22877)feat(app-server): update remote control APIs for better UX@owenlin0[@owenlin0](https://github.com/owenlin0)
- #22899[#22899](https://github.com/openai/codex/pull/22899)[codex] Soften SQLite metadata sync failures@wiltzius-openai[@wiltzius-openai](https://github.com/wiltzius-openai)

Full release on Github[Full release on Github](https://github.com/openai/codex/releases/tag/rust-v0.131.0)
- 2026-05-14

### Work with Codex from anywhere

You can now use Codex from the ChatGPT mobile app by connecting it to a Mac running the Codex app. Codex runs from the connected host, so the same projects, files, credentials, plugins, skills, and configuration are available from your phone.

SeeRemote connections[Remote connections](/codex/remote-connections)for mobile setup, choosing a host, what comes from the connected machine, and SSH hosts. This launch also includesHooks[Hooks](/codex/hooks)general availability,Codex access tokens[Codex access tokens](/codex/enterprise/access-tokens)for trusted automation, andEnterprise admin setup[Enterprise admin setup](/codex/enterprise/admin-setup)guidance.
- 2026-05-11

### Expanded Auto-review documentation

Added a dedicatedAuto-review[Auto-review](/codex/concepts/sandboxing/auto-review)page covering the reviewer lifecycle, trigger conditions, failure behavior, and local or managed configuration.

Also updated theAgent approvals & security[Agent approvals & security](/codex/agent-approvals-security)andSandbox[Sandbox](/codex/concepts/sandboxing)docs so they explain more clearly how Auto-review relates to the sandbox boundary.
- 2026-05-08

### Codex app26.506

### New features

- Added an in-app trust review flow for hooks and kept Hooks settings reachable even before hooks are fully configured.

### Performance improvements and bug fixes

- Restored tooltip-wrapped dropdowns that could stop opening after the tooltip rewrite.
- Preserved in-progress message edits across thread switches.
- Fixed several desktop workflow regressions, including`Ctrl+V`paste in the Windows terminal, opening modified external links outside the in-app browser, and keeping feedback slash commands attached to the right thread.
- Improved loading and panel polish by showing model loading while a thread resumes, hiding unavailable model controls during load, and bundling summary-panel layout and hover fixes.
- Kept the Computer Use settings control visible even when uninstalled and disabled problematic extension hover panels.
- Additional performance improvements and bug fixes.
- 2026-05-08

### Codex CLI0.130.0
````$npminstall-g@openai/codex@0.130.0````
View details

## New Features

- Plugin details now show bundled hooks, and plugin sharing exposes link metadata plus discoverability controls. (#21447[#21447](https://github.com/openai/codex/pull/21447),#21495[#21495](https://github.com/openai/codex/pull/21495),#21637[#21637](https://github.com/openai/codex/pull/21637))
- Added`codex remote-control`as a simpler entrypoint for starting a headless, remotely controllable app-server. (#21424[#21424](https://github.com/openai/codex/pull/21424))
- App-server clients can page large threads with unloaded, summary, or full turn item views. (#21566[#21566](https://github.com/openai/codex/pull/21566))
- Bedrock auth can now use AWS console-login credentials from`aws login`profiles. (#21623[#21623](https://github.com/openai/codex/pull/21623))
- `view_image`can resolve files through the selected environment for multi-environment sessions. (#21143[#21143](https://github.com/openai/codex/pull/21143))

## Bug Fixes

- Live app-server threads now pick up config changes without requiring a restart. (#21187[#21187](https://github.com/openai/codex/pull/21187))
- Turn diffs stay accurate across apply-patch operations, including partial failures that still mutated files. (#21180[#21180](https://github.com/openai/codex/pull/21180),#21518[#21518](https://github.com/openai/codex/pull/21518))
- Thread summaries, renames, resume, and fork paths work better through`ThreadStore`, including threads without local rollout paths. (#21264[#21264](https://github.com/openai/codex/pull/21264),#21265[#21265](https://github.com/openai/codex/pull/21265),#21266[#21266](https://github.com/openai/codex/pull/21266))
- Remote compaction now emits`response.processed`for v2 streams and avoids sending`service_tier`on API-key compact requests. (#21642[#21642](https://github.com/openai/codex/pull/21642),#21676[#21676](https://github.com/openai/codex/pull/21676))
- Windows sandbox setup now grants sandbox users access to the desktop runtime binary cache. (#21564[#21564](https://github.com/openai/codex/pull/21564))
- Removed stale “research preview” wording from the`codex exec`startup banner. (#21683[#21683](https://github.com/openai/codex/pull/21683))

## Documentation

- Fixed issue templates so CLI reports keep the intended guidance, labels apply correctly, and feature requests link to the right contributing docs. (#21685[#21685](https://github.com/openai/codex/pull/21685),#21686[#21686](https://github.com/openai/codex/pull/21686),#21688[#21688](https://github.com/openai/codex/pull/21688))
- Updated install and tooling docs to consistently use`cargo install --locked`. (#21592[#21592](https://github.com/openai/codex/pull/21592))

## Chores

- Added a faster Cargo profiling build profile and disabled empty doctest targets to speed up Rust development loops. (#21574[#21574](https://github.com/openai/codex/pull/21574),#21584[#21584](https://github.com/openai/codex/pull/21584))
- Hardened dependency and CI hygiene with fully qualified GitHub Action pins, a Dependabot cooldown, and a`cargo-shear`upgrade. (#21436[#21436](https://github.com/openai/codex/pull/21436),#21547[#21547](https://github.com/openai/codex/pull/21547),#21599[#21599](https://github.com/openai/codex/pull/21599))
- Simplified internal surfaces by removing unused device-key APIs, extra skills roots, the remote thread-store implementation, and string-keyed MCP tool maps. (#21487[#21487](https://github.com/openai/codex/pull/21487),#21485[#21485](https://github.com/openai/codex/pull/21485),#21596[#21596](https://github.com/openai/codex/pull/21596),#21454[#21454](https://github.com/openai/codex/pull/21454))
- Added configurable OpenTelemetry trace metadata and richer review/feedback analytics for better debugging and triage. (#21556[#21556](https://github.com/openai/codex/pull/21556),#18747[#18747](https://github.com/openai/codex/pull/18747),#21434[#21434](https://github.com/openai/codex/pull/21434),#21498[#21498](https://github.com/openai/codex/pull/21498))

## Changelog

Full Changelog:rust-v0.129.0...rust-v0.130.0[rust-v0.129.0...rust-v0.130.0](https://github.com/openai/codex/compare/rust-v0.129.0...rust-v0.130.0)

- #21494[#21494](https://github.com/openai/codex/pull/21494)[codex] fix PluginListParams test initializer@xli-oai[@xli-oai](https://github.com/xli-oai)
- #21447[#21447](https://github.com/openai/codex/pull/21447)Show plugin hooks in plugin details@abhinav-oai[@abhinav-oai](https://github.com/abhinav-oai)
- #21356[#21356](https://github.com/openai/codex/pull/21356)feat: make built-in MCPs first-class runtime servers@jif-oai[@jif-oai](https://github.com/jif-oai)
- #21180[#21180](https://github.com/openai/codex/pull/21180)Make turn diff tracking operation backed@jif-oai[@jif-oai](https://github.com/jif-oai)
- #21498[#21498](https://github.com/openai/codex/pull/21498)[codex] add account id to feedback uploads@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #21487[#21487](https://github.com/openai/codex/pull/21487)device-key: clean up unused crate@euroelessar[@euroelessar](https://github.com/euroelessar)
- #21518[#21518](https://github.com/openai/codex/pull/21518)fix: preserve exact turn diffs after partial apply_patch failures@jif-oai[@jif-oai](https://github.com/jif-oai)
- #18747[#18747](https://github.com/openai/codex/pull/18747)[codex-analytics] add tool review event schema@rhan-oai[@rhan-oai](https://github.com/rhan-oai)
- #21495[#21495](https://github.com/openai/codex/pull/21495)feat: Expose plugin share metadata in shareContext@xl-openai[@xl-openai](https://github.com/xl-openai)
- #21454[#21454](https://github.com/openai/codex/pull/21454)[codex] Remove string-keyed MCP tool maps@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #21424[#21424](https://github.com/openai/codex/pull/21424)add top-level remote-control command@owenlin0[@owenlin0](https://github.com/owenlin0)
- #21187[#21187](https://github.com/openai/codex/pull/21187)app-server: refresh live threads from latest config snapshot@jif-oai[@jif-oai](https://github.com/jif-oai)
- #21461[#21461](https://github.com/openai/codex/pull/21461)[codex] Move tool specs onto handlers@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #21547[#21547](https://github.com/openai/codex/pull/21547)Upgrade`cargo-shear`to 1.11.2@charliemarsh-oai[@charliemarsh-oai](https://github.com/charliemarsh-oai)
- #21264[#21264](https://github.com/openai/codex/pull/21264)Move thread name edits to ThreadStore@wiltzius-openai[@wiltzius-openai](https://github.com/wiltzius-openai)
- #21266[#21266](https://github.com/openai/codex/pull/21266)[codex] Fix pathless thread summaries@wiltzius-openai[@wiltzius-openai](https://github.com/wiltzius-openai)
- #21265[#21265](https://github.com/openai/codex/pull/21265)Route ThreadManager rollout path reads through thread store@wiltzius-openai[@wiltzius-openai](https://github.com/wiltzius-openai)
- #21564[#21564](https://github.com/openai/codex/pull/21564)Grant sandbox users access to desktop runtime bin@iceweasel-oai[@iceweasel-oai](https://github.com/iceweasel-oai)
- #21582[#21582](https://github.com/openai/codex/pull/21582)Use descriptive names for Cargo profile options@zanie-oai[@zanie-oai](https://github.com/zanie-oai)
- #21574[#21574](https://github.com/openai/codex/pull/21574)Add a Cargo build profile for benchmarking@zanie-oai[@zanie-oai](https://github.com/zanie-oai)
- #21436[#21436](https://github.com/openai/codex/pull/21436)[codex] Fully qualify hash-pins in GitHub Actions@ww-oai[@ww-oai](https://github.com/ww-oai)
- #21592[#21592](https://github.com/openai/codex/pull/21592)Ensure all mentions of cargo-install are --locked@gankra-oai[@gankra-oai](https://github.com/gankra-oai)
- #21584[#21584](https://github.com/openai/codex/pull/21584)Disable empty Cargo test targets@charliemarsh-oai[@charliemarsh-oai](https://github.com/charliemarsh-oai)
- #21566[#21566](https://github.com/openai/codex/pull/21566)feat(app-server, threadstore): Thread pagination APIs and ThreadStore contract@owenlin0[@owenlin0](https://github.com/owenlin0)
- #21556[#21556](https://github.com/openai/codex/pull/21556)codex-otel: add configurable trace metadata@bbrown-oai[@bbrown-oai](https://github.com/bbrown-oai)
- #21599[#21599](https://github.com/openai/codex/pull/21599)[codex] Apply a Dependabot cooldown of 7 days@ww-oai[@ww-oai](https://github.com/ww-oai)
- #21602[#21602](https://github.com/openai/codex/pull/21602)Use`--locked`in cargo build and lint invocations@zanie-oai[@zanie-oai](https://github.com/zanie-oai)
- #20664[#20664](https://github.com/openai/codex/pull/20664)Add stdio exec-server client transport@starr-openai[@starr-openai](https://github.com/starr-openai)
- #21596[#21596](https://github.com/openai/codex/pull/21596)[codex] Remove remote thread store implementation@wiltzius-openai[@wiltzius-openai](https://github.com/wiltzius-openai)
- #20665[#20665](https://github.com/openai/codex/pull/20665)Make environment providers own default selection@starr-openai[@starr-openai](https://github.com/starr-openai)
- #21143[#21143](https://github.com/openai/codex/pull/21143)Route view_image through selected environments@starr-openai[@starr-openai](https://github.com/starr-openai)
- #20666[#20666](https://github.com/openai/codex/pull/20666)Add CODEX_HOME environments TOML provider@starr-openai[@starr-openai](https://github.com/starr-openai)
- #21642[#21642](https://github.com/openai/codex/pull/21642)Send response.processed after remote compaction v2@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #21646[#21646](https://github.com/openai/codex/pull/21646)Revert "Use`--locked`in cargo build and lint invocations"@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #21434[#21434](https://github.com/openai/codex/pull/21434)[codex-analytics] plumb protocol-native review timing@rhan-oai[@rhan-oai](https://github.com/rhan-oai)
- #21485[#21485](https://github.com/openai/codex/pull/21485)Remove skills list extra roots@xli-oai[@xli-oai](https://github.com/xli-oai)
- #21623[#21623](https://github.com/openai/codex/pull/21623)feat: enable AWS login credentials for Bedrock auth@celia-oai[@celia-oai](https://github.com/celia-oai)
- #21637[#21637](https://github.com/openai/codex/pull/21637)feat: Update plugin share settings with discoverability@xl-openai[@xl-openai](https://github.com/xl-openai)
- #21685[#21685](https://github.com/openai/codex/pull/21685)Fix duplicate CLI issue template description@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #21686[#21686](https://github.com/openai/codex/pull/21686)Fix issue template labels@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #21688[#21688](https://github.com/openai/codex/pull/21688)Fix feature request Contributing link@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #21683[#21683](https://github.com/openai/codex/pull/21683)Remove exec research preview banner wording@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #21676[#21676](https://github.com/openai/codex/pull/21676)Omit service_tier from remote /responses/compact requests under API auth@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)

Full release on Github[Full release on Github](https://github.com/openai/codex/releases/tag/rust-v0.130.0)
- 2026-05-07

### Codex for Chrome

With the new extension for Chrome, Codex is even better at working with apps and websites in your browser. It works in parallel across tabs in the background without taking over your browser, and you stay in control of which websites Codex can use.

Learn more in theCodex Chrome extension documentation[Codex Chrome extension documentation](/codex/app/chrome-extension).
- 2026-05-07

### Codex CLI0.129.0
````$npminstall-g@openai/codex@0.129.0````
View details

## New Features

- The TUI now supports modal Vim editing in the composer, including`/vim`, default-mode config, and Vim-specific keymap contexts. (#18595[#18595](https://github.com/openai/codex/pull/18595))
- TUI workflows are easier to resume and copy from with a redesigned resume/fork picker, raw scrollback mode,`/ide`context injection, and workspace-aware`/diff`. (#20065[#20065](https://github.com/openai/codex/pull/20065),#20819[#20819](https://github.com/openai/codex/pull/20819),#20294[#20294](https://github.com/openai/codex/pull/20294),#21001[#21001](https://github.com/openai/codex/pull/21001))
- The status line can show theme-aware colors plus optional PR and branch-change summaries, and`/keymap debug`helps inspect terminal key events. (#19631[#19631](https://github.com/openai/codex/pull/19631),#20892[#20892](https://github.com/openai/codex/pull/20892),#20794[#20794](https://github.com/openai/codex/pull/20794))
- Plugin management now supports workspace sharing, share access controls, source filtering, local share path tracking, marketplace removal/upgrades, remote bundle sync, and admin-disabled status handling. (#20278[#20278](https://github.com/openai/codex/pull/20278),#21124[#21124](https://github.com/openai/codex/pull/21124),#21419[#21419](https://github.com/openai/codex/pull/21419),#20560[#20560](https://github.com/openai/codex/pull/20560),#19843[#19843](https://github.com/openai/codex/pull/19843),#20478[#20478](https://github.com/openai/codex/pull/20478),#20268[#20268](https://github.com/openai/codex/pull/20268),#20298[#20298](https://github.com/openai/codex/pull/20298))
- Hooks can be browsed and toggled from`/hooks`, can run before/after compaction, and can add`PreToolUse`context; Codex Apps auth and eligible MCP elicitations now surface through TUI/Guardian flows. (#19882[#19882](https://github.com/openai/codex/pull/19882),#19905[#19905](https://github.com/openai/codex/pull/19905),#20692[#20692](https://github.com/openai/codex/pull/20692),#19193[#19193](https://github.com/openai/codex/pull/19193),#19431[#19431](https://github.com/openai/codex/pull/19431))
- Experimental goals are now discoverable, stay paused across resume unless the user opts back in, and show clearer validation and multi-day duration output. (#20083[#20083](https://github.com/openai/codex/pull/20083),#20790[#20790](https://github.com/openai/codex/pull/20790),#20746[#20746](https://github.com/openai/codex/pull/20746),#20558[#20558](https://github.com/openai/codex/pull/20558))

## Bug Fixes

- `/copy`works better in tmux, Alt+Enter and modified Delete/Backspace keys behave correctly, and Windows typing/paste latency was reduced. (#20207[#20207](https://github.com/openai/codex/pull/20207),#20535[#20535](https://github.com/openai/codex/pull/20535),#21058[#21058](https://github.com/openai/codex/pull/21058),#18914[#18914](https://github.com/openai/codex/pull/18914))
- Large paste placeholders and Ctrl+C-stashed drafts now survive clear/editor workflows without corrupting draft history. (#21091[#21091](https://github.com/openai/codex/pull/21091),#21190[#21190](https://github.com/openai/codex/pull/21190),#21351[#21351](https://github.com/openai/codex/pull/21351),#21397[#21397](https://github.com/openai/codex/pull/21397))
- TUI startup and accessibility were tightened by bounding terminal probes, clearing the first inline viewport render, and honoring`animations = false`for live rows. (#20654[#20654](https://github.com/openai/codex/pull/20654),#21450[#21450](https://github.com/openai/codex/pull/21450),#20564[#20564](https://github.com/openai/codex/pull/20564))
- Linux sandbox startup is more reliable across older`bwrap`, slow mount probes, symlink-protected paths, and shared`/tmp`setups. (#20628[#20628](https://github.com/openai/codex/pull/20628),#20111[#20111](https://github.com/openai/codex/pull/20111),#21127[#21127](https://github.com/openai/codex/pull/21127),#21234[#21234](https://github.com/openai/codex/pull/21234))
- Windows sandbox and exec policy now handle named pipes, ConPTY teardown, PowerShell-wrapped allow rules, worktree`safe.directory`, and unsafe Git options more reliably. (#20270[#20270](https://github.com/openai/codex/pull/20270),#20685[#20685](https://github.com/openai/codex/pull/20685),#20336[#20336](https://github.com/openai/codex/pull/20336),#21409[#21409](https://github.com/openai/codex/pull/21409),#21275[#21275](https://github.com/openai/codex/pull/21275))
- Fixed custom CA login behind TLS-inspecting proxies, Bedrock runtime endpoint reporting, dangerous project config keys, heredoc redirect approval matching, and unbounded MCP/hook output growth. (#20676,#20275[#20275](https://github.com/openai/codex/pull/20275),#20098[#20098](https://github.com/openai/codex/pull/20098),#20113[#20113](https://github.com/openai/codex/pull/20113),#20260[#20260](https://github.com/openai/codex/pull/20260),#21069[#21069](https://github.com/openai/codex/pull/21069))

## Documentation

- Updated the embedded OpenAI Docs sample skill so API-key setup guidance stays aligned with other docs variants. (#21263[#21263](https://github.com/openai/codex/pull/21263))
- Documented how generated git commit attribution is gated by`codex_git_commit`and configured in`config.toml`. (#21379[#21379](https://github.com/openai/codex/pull/21379))
- Removed local-only planning/spec docs and redirected config docs toward the maintained external documentation surface. (#20896[#20896](https://github.com/openai/codex/pull/20896))

## Chores

- Linux releases now build, publish, bundle, and verify a standalone`bwrap`fallback for npm and DotSlash installs. (#21255[#21255](https://github.com/openai/codex/pull/21255),#21256[#21256](https://github.com/openai/codex/pull/21256),#21257[#21257](https://github.com/openai/codex/pull/21257),#21312[#21312](https://github.com/openai/codex/pull/21312),#21285[#21285](https://github.com/openai/codex/pull/21285))
- Vendored Bubblewrap was updated to 0.11.2, including upstream security changes around setuid support. (#21389[#21389](https://github.com/openai/codex/pull/21389))
- Windows Bazel CI now uses faster cross-compilation for tests, clippy, and release-build checks, and Bazel now runs sharded Rust integration tests. (#20585[#20585](https://github.com/openai/codex/pull/20585),#20701[#20701](https://github.com/openai/codex/pull/20701),#21057[#21057](https://github.com/openai/codex/pull/21057))
- App-server and protocol internals were split and slimmed down, including transport extraction, protocol module decomposition, thread/message history moves, and tool-handler cleanup. (#20324[#20324](https://github.com/openai/codex/pull/20324),#20325[#20325](https://github.com/openai/codex/pull/20325),#20348[#20348](https://github.com/openai/codex/pull/20348),#20545[#20545](https://github.com/openai/codex/pull/20545),#21251[#21251](https://github.com/openai/codex/pull/21251),#21278[#21278](https://github.com/openai/codex/pull/21278),#21395[#21395](https://github.com/openai/codex/pull/21395))
- Analytics and diagnostics coverage expanded for tool lifecycles, goals, plugin skills, thread sources, service tiers, and PR issue labeling. (#17089[#17089](https://github.com/openai/codex/pull/17089),#17090[#17090](https://github.com/openai/codex/pull/17090),#20799[#20799](https://github.com/openai/codex/pull/20799),#20923[#20923](https://github.com/openai/codex/pull/20923),#20949[#20949](https://github.com/openai/codex/pull/20949),#20969[#20969](https://github.com/openai/codex/pull/20969),#20893[#20893](https://github.com/openai/codex/pull/20893))

## Changelog

Full Changelog:rust-v0.128.0...rust-v0.129.0[rust-v0.128.0...rust-v0.129.0](https://github.com/openai/codex/compare/rust-v0.128.0...rust-v0.129.0)

- #20278[#20278](https://github.com/openai/codex/pull/20278)feat: Add workspace plugin sharing APIs@xl-openai[@xl-openai](https://github.com/xl-openai)
- #20334[#20334](https://github.com/openai/codex/pull/20334)Make missing config clears no-ops@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #20246[#20246](https://github.com/openai/codex/pull/20246)Gate multi-agent v2 tools independently of collab@jif-oai[@jif-oai](https://github.com/jif-oai)
- #20361[#20361](https://github.com/openai/codex/pull/20361)realtime: rename provider session ids@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #20260[#20260](https://github.com/openai/codex/pull/20260)fix(core): truncate large mcp tool outputs in rollouts@owenlin0[@owenlin0](https://github.com/owenlin0)
- #20083[#20083](https://github.com/openai/codex/pull/20083)Mark goals feature as experimental@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #19843[#19843](https://github.com/openai/codex/pull/19843)/plugins: remove marketplace@canvrno-oai[@canvrno-oai](https://github.com/canvrno-oai)
- #20458[#20458](https://github.com/openai/codex/pull/20458)[Extension] Allowlist Chrome Extension in the tool_suggest tool@teddywyly-oai[@teddywyly-oai](https://github.com/teddywyly-oai)
- #20324[#20324](https://github.com/openai/codex/pull/20324)Remove core protocol dependency [1/2]@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #20299[#20299](https://github.com/openai/codex/pull/20299)Move item event mapping into app-server-protocol@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #20325[#20325](https://github.com/openai/codex/pull/20325)Remove core protocol dependency [2/2]@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #20471[#20471](https://github.com/openai/codex/pull/20471)Stop emitting item/fileChange/outputDelta output delta notifications@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #20245[#20245](https://github.com/openai/codex/pull/20245)[Codex] Add browser use external feature flag@khoi-oai[@khoi-oai](https://github.com/khoi-oai)
- #19882[#19882](https://github.com/openai/codex/pull/19882)Add /hooks browser for lifecycle hooks@abhinav-oai[@abhinav-oai](https://github.com/abhinav-oai)
- #20275[#20275](https://github.com/openai/codex/pull/20275)fix: show correct Bedrock runtime endpoint in /status@celia-oai[@celia-oai](https://github.com/celia-oai)
- #20270[#20270](https://github.com/openai/codex/pull/20270)[codex] Fix elevated Windows sandbox named-pipe access@iceweasel-oai[@iceweasel-oai](https://github.com/iceweasel-oai)
- #20463[#20463](https://github.com/openai/codex/pull/20463)feat(rollouts): store EventMsg::ApplyPatchEnd in limited history mode@owenlin0[@owenlin0](https://github.com/owenlin0)
- #20101[#20101](https://github.com/openai/codex/pull/20101)install WFP filters for Windows sandbox setup@iceweasel-oai[@iceweasel-oai](https://github.com/iceweasel-oai)
- #20474[#20474](https://github.com/openai/codex/pull/20474)[plugin] Add Canva to suggesteable list.@mzeng-openai[@mzeng-openai](https://github.com/mzeng-openai)
- #20379[#20379](https://github.com/openai/codex/pull/20379)Send external import completion for sync imports@alexsong-oai[@alexsong-oai](https://github.com/alexsong-oai)
- #19280[#19280](https://github.com/openai/codex/pull/19280)[codex] Migrate thread turns list to thread store@wiltzius-openai[@wiltzius-openai](https://github.com/wiltzius-openai)
- #20348[#20348](https://github.com/openai/codex/pull/20348)Move plugin out of core.@xl-openai[@xl-openai](https://github.com/xl-openai)
- #19160[#19160](https://github.com/openai/codex/pull/19160)Make apply_patch streaming parser stateful@akshaynathan[@akshaynathan](https://github.com/akshaynathan)
- #20504[#20504](https://github.com/openai/codex/pull/20504)fix flaky test falls_back_to_registered_fallback_port_when_default_po…@owenlin0[@owenlin0](https://github.com/owenlin0)
- #20098[#20098](https://github.com/openai/codex/pull/20098)fix: ignore dangerous project-level config keys@owenlin0[@owenlin0](https://github.com/owenlin0)
- #20268[#20268](https://github.com/openai/codex/pull/20268)Sync remote installed plugin bundles@xli-oai[@xli-oai](https://github.com/xli-oai)
- #20502[#20502](https://github.com/openai/codex/pull/20502)fix(tui): set persist_extended_history: false@owenlin0[@owenlin0](https://github.com/owenlin0)
- #20069[#20069](https://github.com/openai/codex/pull/20069)Bypass review for always-allow MCP tools in auto-review@maja-openai[@maja-openai](https://github.com/maja-openai)
- #18595[#18595](https://github.com/openai/codex/pull/18595)feat(tui): add vim composer mode@fcoury-oai[@fcoury-oai](https://github.com/fcoury-oai)
- #20267[#20267](https://github.com/openai/codex/pull/20267)Emit analytics for remote plugin installs@xli-oai[@xli-oai](https://github.com/xli-oai)
- #20499[#20499](https://github.com/openai/codex/pull/20499)fix(app-server): mark thread/turns/list and exclude_turns as experime…@owenlin0[@owenlin0](https://github.com/owenlin0)
- #20522[#20522](https://github.com/openai/codex/pull/20522)Alias codex_hooks feature as hooks@abhinav-oai[@abhinav-oai](https://github.com/abhinav-oai)
- #20336[#20336](https://github.com/openai/codex/pull/20336)execpolicy: unwrap PowerShell -Command wrappers on Windows@iceweasel-oai[@iceweasel-oai](https://github.com/iceweasel-oai)
- #20113[#20113](https://github.com/openai/codex/pull/20113)fix(exec_policy) heredoc parsing file_redirect@dylan-hurd-oai[@dylan-hurd-oai](https://github.com/dylan-hurd-oai)
- #20341[#20341](https://github.com/openai/codex/pull/20341)app-server: switch remote control to protocol v3 segmentation@euroelessar[@euroelessar](https://github.com/euroelessar)
- #20300[#20300](https://github.com/openai/codex/pull/20300)[codex-analytics] centralize thread analytics state@rhan-oai[@rhan-oai](https://github.com/rhan-oai)
- #20484[#20484](https://github.com/openai/codex/pull/20484)[codex] Improve PR babysitter CI diagnostics and guardrails@wiltzius-openai[@wiltzius-openai](https://github.com/wiltzius-openai)
- #20298[#20298](https://github.com/openai/codex/pull/20298)Surface admin-disabled remote plugin status@xli-oai[@xli-oai](https://github.com/xli-oai)
- #20511[#20511](https://github.com/openai/codex/pull/20511)[codex] Remove unused event messages@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #19474[#19474](https://github.com/openai/codex/pull/19474)Make thread store process-scoped@wiltzius-openai[@wiltzius-openai](https://github.com/wiltzius-openai)
- #20558[#20558](https://github.com/openai/codex/pull/20558)Format multi-day goal durations in the TUI@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #19631[#19631](https://github.com/openai/codex/pull/19631)Color TUI statusline from active theme@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #20265[#20265](https://github.com/openai/codex/pull/20265)Refresh remote plugin cache on auth changes@xli-oai[@xli-oai](https://github.com/xli-oai)
- #20150[#20150](https://github.com/openai/codex/pull/20150)Add remote plugin skill read API@xli-oai[@xli-oai](https://github.com/xli-oai)
- #20560[#20560](https://github.com/openai/codex/pull/20560)feat: Track local paths for shared plugins@xl-openai[@xl-openai](https://github.com/xl-openai)
- #20600[#20600](https://github.com/openai/codex/pull/20600)chore: allow memories edition@jif-oai[@jif-oai](https://github.com/jif-oai)
- #20602[#20602](https://github.com/openai/codex/pull/20602)feat: ad-hoc instructions@jif-oai[@jif-oai](https://github.com/jif-oai)
- #20610[#20610](https://github.com/openai/codex/pull/20610)chore: improve remember prompt@jif-oai[@jif-oai](https://github.com/jif-oai)
- #20606[#20606](https://github.com/openai/codex/pull/20606)feat: seed ad-hoc memory extension instructions@jif-oai[@jif-oai](https://github.com/jif-oai)
- #20405[#20405](https://github.com/openai/codex/pull/20405)feat: export and replay effective config locks@jif-oai[@jif-oai](https://github.com/jif-oai)
- #20540[#20540](https://github.com/openai/codex/pull/20540)Move apply-patch file changes into turn items@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #20564[#20564](https://github.com/openai/codex/pull/20564)Enforce`animations = false`for screen readers@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #20523[#20523](https://github.com/openai/codex/pull/20523)Remove no-tool goal continuation suppression@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #20627[#20627](https://github.com/openai/codex/pull/20627)fix: cargo deny@jif-oai[@jif-oai](https://github.com/jif-oai)
- #20545[#20545](https://github.com/openai/codex/pull/20545)app-server: move transport into dedicated crate@euroelessar[@euroelessar](https://github.com/euroelessar)
- #20294[#20294](https://github.com/openai/codex/pull/20294)Add /ide context support to the TUI@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #20630[#20630](https://github.com/openai/codex/pull/20630)[codex] Add Codex environment config@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #20524[#20524](https://github.com/openai/codex/pull/20524)deprecate legacy notify@abhinav-oai[@abhinav-oai](https://github.com/abhinav-oai)
- #20486[#20486](https://github.com/openai/codex/pull/20486)[codex] Migrate loaded thread/read history to ThreadStore@wiltzius-openai[@wiltzius-openai](https://github.com/wiltzius-openai)
- #20281[#20281](https://github.com/openai/codex/pull/20281)Use selected turn environments for runtime context@starr-openai[@starr-openai](https://github.com/starr-openai)
- #20535[#20535](https://github.com/openai/codex/pull/20535)fix(tui): restore alt-enter newline alias@fcoury-oai[@fcoury-oai](https://github.com/fcoury-oai)
- #20650[#20650](https://github.com/openai/codex/pull/20650)fix: reduce ConfigBuilder::build stack usage@jif-oai[@jif-oai](https://github.com/jif-oai)
- #20478[#20478](https://github.com/openai/codex/pull/20478)/plugins: add marketplace upgrade flow@canvrno-oai[@canvrno-oai](https://github.com/canvrno-oai)
- #20512[#20512](https://github.com/openai/codex/pull/20512)[codex] Emit image view as core item@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #20562[#20562](https://github.com/openai/codex/pull/20562)Use the 2025-06-18 elicitation capability shape@abhinav-oai[@abhinav-oai](https://github.com/abhinav-oai)
- #20674[#20674](https://github.com/openai/codex/pull/20674)Clear live hook rows when turns finalize@abhinav-oai[@abhinav-oai](https://github.com/abhinav-oai)
- #20646[#20646](https://github.com/openai/codex/pull/20646)Surface multi-environment choices in environment context@starr-openai[@starr-openai](https://github.com/starr-openai)
- #20542[#20542](https://github.com/openai/codex/pull/20542)Prune unused code-mode globals@cconger[@cconger](https://github.com/cconger)
- #20585[#20585](https://github.com/openai/codex/pull/20585)ci: cross-compile Windows Bazel tests@bolinfest[@bolinfest](https://github.com/bolinfest)
- #20701[#20701](https://github.com/openai/codex/pull/20701)ci: cross-compile Windows Bazel clippy@bolinfest[@bolinfest](https://github.com/bolinfest)
- #20676 Fix custom CA login behind TLS-inspecting proxies@jgershen-oai[@jgershen-oai](https://github.com/jgershen-oai)
- #20654[#20654](https://github.com/openai/codex/pull/20654)fix(tui): bound startup terminal probes@fcoury-oai[@fcoury-oai](https://github.com/fcoury-oai)
- #20566[#20566](https://github.com/openai/codex/pull/20566)[tool_suggest] More prompt polishes.@mzeng-openai[@mzeng-openai](https://github.com/mzeng-openai)
- #20751[#20751](https://github.com/openai/codex/pull/20751)Bound websocket request sends with idle timeout@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #20893[#20893](https://github.com/openai/codex/pull/20893)[codex] Add issue labeler area labels@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #20896[#20896](https://github.com/openai/codex/pull/20896)Remove local docs and specs@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #20897[#20897](https://github.com/openai/codex/pull/20897)[codex] Refactor app-server dispatch result flow@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #20677[#20677](https://github.com/openai/codex/pull/20677)[codex] Emit MCP tool calls as turn items@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #20973[#20973](https://github.com/openai/codex/pull/20973)feat: support template interpolation in multi-agent usage hints@jif-oai[@jif-oai](https://github.com/jif-oai)
- #20622[#20622](https://github.com/openai/codex/pull/20622)feat: memories mcp v1@jif-oai[@jif-oai](https://github.com/jif-oai)
- #20773[#20773](https://github.com/openai/codex/pull/20773)feat: add remote compaction v2 Responses client path@jif-oai[@jif-oai](https://github.com/jif-oai)
- #20986[#20986](https://github.com/openai/codex/pull/20986)feat: add line offsets to memory read MCP@jif-oai[@jif-oai](https://github.com/jif-oai)
- #20991[#20991](https://github.com/openai/codex/pull/20991)feat: add max_lines to memories MCP read@jif-oai[@jif-oai](https://github.com/jif-oai)
- #20993[#20993](https://github.com/openai/codex/pull/20993)feat: paginate MCP memories list@jif-oai[@jif-oai](https://github.com/jif-oai)
- #20994[#20994](https://github.com/openai/codex/pull/20994)feat: make memories MCP list shallow@jif-oai[@jif-oai](https://github.com/jif-oai)
- #20996[#20996](https://github.com/openai/codex/pull/20996)feat: paginate memories MCP search results@jif-oai[@jif-oai](https://github.com/jif-oai)
- #20997[#20997](https://github.com/openai/codex/pull/20997)feat: add context lines to memories MCP search@jif-oai[@jif-oai](https://github.com/jif-oai)
- #20998[#20998](https://github.com/openai/codex/pull/20998)nit: renaming@jif-oai[@jif-oai](https://github.com/jif-oai)
- #21004[#21004](https://github.com/openai/codex/pull/21004)feat: support multi-query memories search@jif-oai[@jif-oai](https://github.com/jif-oai)
- #21006[#21006](https://github.com/openai/codex/pull/21006)nit: legacy@jif-oai[@jif-oai](https://github.com/jif-oai)
- #20815[#20815](https://github.com/openai/codex/pull/20815)Speed up /side parent restore replay@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #20790[#20790](https://github.com/openai/codex/pull/20790)Keep paused goals paused on thread resume@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #20940[#20940](https://github.com/openai/codex/pull/20940)[codex] Split app-server request processors@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #21023[#21023](https://github.com/openai/codex/pull/21023)typo@jif-oai[@jif-oai](https://github.com/jif-oai)
- #21012[#21012](https://github.com/openai/codex/pull/21012)memories/mcp: generate tool schemas with schemars@jif-oai[@jif-oai](https://github.com/jif-oai)
- #21010[#21010](https://github.com/openai/codex/pull/21010)memories-mcp: reject symlink traversal in local backend@jif-oai[@jif-oai](https://github.com/jif-oai)
- #20989[#20989](https://github.com/openai/codex/pull/20989)core: share responses request builder with compact requests@jif-oai[@jif-oai](https://github.com/jif-oai)
- #20853[#20853](https://github.com/openai/codex/pull/20853)[mcp-apps] Persist MCP Apps specific tool call end event.@mzeng-openai[@mzeng-openai](https://github.com/mzeng-openai)
- #20750[#20750](https://github.com/openai/codex/pull/20750)Unify skip-review handling for approval_mode = "approve"@mzeng-openai[@mzeng-openai](https://github.com/mzeng-openai)
- #20682[#20682](https://github.com/openai/codex/pull/20682)feat(app-server): always return limited thread history@owenlin0[@owenlin0](https://github.com/owenlin0)
- #20628[#20628](https://github.com/openai/codex/pull/20628)fix(linux-sandbox): fall back when system bwrap lacks perms@viyatb-oai[@viyatb-oai](https://github.com/viyatb-oai)
- #20794[#20794](https://github.com/openai/codex/pull/20794)feat(tui): add keymap debug inspector@fcoury-oai[@fcoury-oai](https://github.com/fcoury-oai)
- #21034[#21034](https://github.com/openai/codex/pull/21034)tui: retire /approvals and rename /autoreview to /approve@won-openai[@won-openai](https://github.com/won-openai)
- #20669[#20669](https://github.com/openai/codex/pull/20669)Prepare selected environment plumbing@starr-openai[@starr-openai](https://github.com/starr-openai)
- #20685[#20685](https://github.com/openai/codex/pull/20685)Fix Windows PTY teardown by preserving ConPTY ownership@iceweasel-oai[@iceweasel-oai](https://github.com/iceweasel-oai)
- #20663[#20663](https://github.com/openai/codex/pull/20663)Add stdio exec-server listener@starr-openai[@starr-openai](https://github.com/starr-openai)
- #20561[#20561](https://github.com/openai/codex/pull/20561)state: pass state db handles through consumers@euroelessar[@euroelessar](https://github.com/euroelessar)
- #21054[#21054](https://github.com/openai/codex/pull/21054)rollout: store web search and mcp tool calls@owenlin0[@owenlin0](https://github.com/owenlin0)
- #20892[#20892](https://github.com/openai/codex/pull/20892)feat(tui): add PR summary statusline items@fcoury-oai[@fcoury-oai](https://github.com/fcoury-oai)
- #20798[#20798](https://github.com/openai/codex/pull/20798)feat(tui): improve TUI keymap coverage@fcoury-oai[@fcoury-oai](https://github.com/fcoury-oai)
- #21053[#21053](https://github.com/openai/codex/pull/21053)Use MCP server instructions in deferred namespace descriptions@sayan-oai[@sayan-oai](https://github.com/sayan-oai)
- #21026[#21026](https://github.com/openai/codex/pull/21026)core: preserve last model ids in feedback tags@sayan-oai[@sayan-oai](https://github.com/sayan-oai)
- #21060[#21060](https://github.com/openai/codex/pull/21060)core: fix apply_patch request permissions test@bolinfest[@bolinfest](https://github.com/bolinfest)
- #20060[#20060](https://github.com/openai/codex/pull/20060)Add reasoning effort to turn tracing spans@charley-openai[@charley-openai](https://github.com/charley-openai)
- #21058[#21058](https://github.com/openai/codex/pull/21058)fix(tui): support modified backspace/delete keys@fcoury-oai[@fcoury-oai](https://github.com/fcoury-oai)
- #21057[#21057](https://github.com/openai/codex/pull/21057)bazel: run sharded rust integration tests@bolinfest[@bolinfest](https://github.com/bolinfest)
- #18914[#18914](https://github.com/openai/codex/pull/18914)fix(tui): use shared paste burst interval on Windows@fcoury-oai[@fcoury-oai](https://github.com/fcoury-oai)
- #20715[#20715](https://github.com/openai/codex/pull/20715)Make realtime sideband startup async@kmeelu-oai[@kmeelu-oai](https://github.com/kmeelu-oai)
- #20514[#20514](https://github.com/openai/codex/pull/20514)[codex-analytics] add item lifecycle timing@rhan-oai[@rhan-oai](https://github.com/rhan-oai)
- #20722[#20722](https://github.com/openai/codex/pull/20722)Remove remote plugin uninstall prefix gate@xli-oai[@xli-oai](https://github.com/xli-oai)
- #19040[#19040](https://github.com/openai/codex/pull/19040)[codex] Add unsandboxed process exec API@euroelessar[@euroelessar](https://github.com/euroelessar)
- #21105[#21105](https://github.com/openai/codex/pull/21105)[network-proxy] Cover DNS timeout blocking@evawong-oai[@evawong-oai](https://github.com/evawong-oai)
- #21059[#21059](https://github.com/openai/codex/pull/21059)Rename agent identity login surface to access token@shijie-oai[@shijie-oai](https://github.com/shijie-oai)
- #20576[#20576](https://github.com/openai/codex/pull/20576)codex: route metadata updates through ThreadStore@wiltzius-openai[@wiltzius-openai](https://github.com/wiltzius-openai)
- #20923[#20923](https://github.com/openai/codex/pull/20923)Add plugin ID to skill analytics@alexsong-oai[@alexsong-oai](https://github.com/alexsong-oai)
- #21122[#21122](https://github.com/openai/codex/pull/21122)Add turn_id to Codex skill invocation analytics@edwardysun3[@edwardysun3](https://github.com/edwardysun3)
- #20575[#20575](https://github.com/openai/codex/pull/20575)codex: migrate (more) app-server thread history reads to ThreadStore@wiltzius-openai[@wiltzius-openai](https://github.com/wiltzius-openai)
- #21069[#21069](https://github.com/openai/codex/pull/21069)Spill large hook outputs from context@abhinav-oai[@abhinav-oai](https://github.com/abhinav-oai)
- #20969[#20969](https://github.com/openai/codex/pull/20969)1- Add model service tiers metadata@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #21170[#21170](https://github.com/openai/codex/pull/21170)tools: remove unused experimental`list_dir`tool@jif-oai[@jif-oai](https://github.com/jif-oai)
- #21201[#21201](https://github.com/openai/codex/pull/21201)memories-mcp: hide dot paths from list, read, and search@jif-oai[@jif-oai](https://github.com/jif-oai)
- #21204[#21204](https://github.com/openai/codex/pull/21204)feat: support windowed multi-query memory search@jif-oai[@jif-oai](https://github.com/jif-oai)
- #21205[#21205](https://github.com/openai/codex/pull/21205)feat: add normalized matching to memory search@jif-oai[@jif-oai](https://github.com/jif-oai)
- #20207[#20207](https://github.com/openai/codex/pull/20207)fix(tui): make /copy work inside tmux without passthrough@fcoury-oai[@fcoury-oai](https://github.com/fcoury-oai)
- #20799[#20799](https://github.com/openai/codex/pull/20799)Add goal lifecycle metrics@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #20746[#20746](https://github.com/openai/codex/pull/20746)Validate /goal objective length in TUI@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #20708[#20708](https://github.com/openai/codex/pull/20708)Add Windows sandbox readiness RPC@iceweasel-oai[@iceweasel-oai](https://github.com/iceweasel-oai)
- #20692[#20692](https://github.com/openai/codex/pull/20692)Support PreToolUse additionalContext@abhinav-oai[@abhinav-oai](https://github.com/abhinav-oai)
- #21091[#21091](https://github.com/openai/codex/pull/21091)[codex] Fix TUI large paste placeholder numbering after Ctrl+C@canvrno-oai[@canvrno-oai](https://github.com/canvrno-oai)
- #21089[#21089](https://github.com/openai/codex/pull/21089)[codex] Fix fork --last cwd filtering@canvrno-oai[@canvrno-oai](https://github.com/canvrno-oai)
- #21152[#21152](https://github.com/openai/codex/pull/21152)revert legacy notify deprecation@abhinav-oai[@abhinav-oai](https://github.com/abhinav-oai)
- #21190[#21190](https://github.com/openai/codex/pull/21190)fix(tui): external editor expansion for same-size large pastes@fcoury-oai[@fcoury-oai](https://github.com/fcoury-oai)
- #20111[#20111](https://github.com/openai/codex/pull/20111)fix(sandboxing): Bound advisory system bwrap startup probe@viyatb-oai[@viyatb-oai](https://github.com/viyatb-oai)
- #21220[#21220](https://github.com/openai/codex/pull/21220)chore: add minimal proxy egress diagnostics@viyatb-oai[@viyatb-oai](https://github.com/viyatb-oai)
- #20819[#20819](https://github.com/openai/codex/pull/20819)feat(tui): add raw scrollback mode@fcoury-oai[@fcoury-oai](https://github.com/fcoury-oai)
- #21225[#21225](https://github.com/openai/codex/pull/21225)app-server: ignore persist_extended_history param@owenlin0[@owenlin0](https://github.com/owenlin0)
- #17089[#17089](https://github.com/openai/codex/pull/17089)[codex-analytics] add tool item event schemas@rhan-oai[@rhan-oai](https://github.com/rhan-oai)
- #20647[#20647](https://github.com/openai/codex/pull/20647)Route process tools to selected environments@starr-openai[@starr-openai](https://github.com/starr-openai)
- #20321[#20321](https://github.com/openai/codex/pull/20321)hook trust metadata and enforcement@abhinav-oai[@abhinav-oai](https://github.com/abhinav-oai)
- #21221[#21221](https://github.com/openai/codex/pull/21221)[codex] Use shared app-server JSON-RPC error helpers@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #21063[#21063](https://github.com/openai/codex/pull/21063)add turn items view to app-server turns@rhan-oai[@rhan-oai](https://github.com/rhan-oai)
- #21001[#21001](https://github.com/openai/codex/pull/21001)feat(tui): route /diff through workspace commands@fcoury-oai[@fcoury-oai](https://github.com/fcoury-oai)
- #20065[#20065](https://github.com/openai/codex/pull/20065)feat(tui): redesign session picker@fcoury-oai[@fcoury-oai](https://github.com/fcoury-oai)
- #21127[#21127](https://github.com/openai/codex/pull/21127)fix(linux-sandbox): avoid panic on bwrap build failures@viyatb-oai[@viyatb-oai](https://github.com/viyatb-oai)
- #21234[#21234](https://github.com/openai/codex/pull/21234)fix(linux-sandbox): isolate Linux sandbox synthetic mount registry per user for shared codex use case@viyatb-oai[@viyatb-oai](https://github.com/viyatb-oai)
- #20687[#20687](https://github.com/openai/codex/pull/20687)[codex] Split tool handlers by tool name@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #21113[#21113](https://github.com/openai/codex/pull/21113)Auto-deny MCP elicitations for Xcode 26.4 clients@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #21243[#21243](https://github.com/openai/codex/pull/21243)[codex] fix TUI turn items view fixtures@fcoury-oai[@fcoury-oai](https://github.com/fcoury-oai)
- #21146[#21146](https://github.com/openai/codex/pull/21146)Enable V8 sandboxing for source-built builds@cconger[@cconger](https://github.com/cconger)
- #20689[#20689](https://github.com/openai/codex/pull/20689)Inject state DB, agent graph store@rasmusrygaard[@rasmusrygaard](https://github.com/rasmusrygaard)
- #19575[#19575](https://github.com/openai/codex/pull/19575)Add cloud executor registration to exec-server@miz-openai[@miz-openai](https://github.com/miz-openai)
- #20577[#20577](https://github.com/openai/codex/pull/20577)codex: use ThreadStore history for core review forks@wiltzius-openai[@wiltzius-openai](https://github.com/wiltzius-openai)
- #21261[#21261](https://github.com/openai/codex/pull/21261)fix build@bolinfest[@bolinfest](https://github.com/bolinfest)
- #21251[#21251](https://github.com/openai/codex/pull/21251)chore(app-server-protocol): split v2 API definitions into modules@owenlin0[@owenlin0](https://github.com/owenlin0)
- #21259[#21259](https://github.com/openai/codex/pull/21259)ci: trigger rusty-v8 releases from tags@cconger[@cconger](https://github.com/cconger)
- #21255[#21255](https://github.com/openai/codex/pull/21255)linux-sandbox: use standalone bundled bwrap@bolinfest[@bolinfest](https://github.com/bolinfest)
- #21256[#21256](https://github.com/openai/codex/pull/21256)release: publish standalone bwrap artifacts@bolinfest[@bolinfest](https://github.com/bolinfest)
- #21260[#21260](https://github.com/openai/codex/pull/21260)[codex] Move thread naming to app server@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #21219[#21219](https://github.com/openai/codex/pull/21219)Add model and reasoning effort to MCP turn metadata@mchen-oai[@mchen-oai](https://github.com/mchen-oai)
- #21275[#21275](https://github.com/openai/codex/pull/21275)Share Git safe-command logic on Windows@iceweasel-oai[@iceweasel-oai](https://github.com/iceweasel-oai)
- #21257[#21257](https://github.com/openai/codex/pull/21257)release/npm: bundle standalone bwrap on Linux@bolinfest[@bolinfest](https://github.com/bolinfest)
- #21276[#21276](https://github.com/openai/codex/pull/21276)[codex] Remove unused ListModels op@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #21282[#21282](https://github.com/openai/codex/pull/21282)[codex] Remove legacy ListSkills op@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #21271[#21271](https://github.com/openai/codex/pull/21271)Expose plugin manifest keywords in app server@alfozan[@alfozan](https://github.com/alfozan)
- #20949[#20949](https://github.com/openai/codex/pull/20949)[codex-analytics] rework thread_source for thread analytics@rhan-oai[@rhan-oai](https://github.com/rhan-oai)
- #21124[#21124](https://github.com/openai/codex/pull/21124)feat: Add plugin share access controls@xl-openai[@xl-openai](https://github.com/xl-openai)
- #20724[#20724](https://github.com/openai/codex/pull/20724)app-server: align dynamic tool identifiers with Responses API@eternal-openai[@eternal-openai](https://github.com/eternal-openai)
- #21055[#21055](https://github.com/openai/codex/pull/21055)Preserve session MCP config on refresh@aaronl-openai[@aaronl-openai](https://github.com/aaronl-openai)
- #21277[#21277](https://github.com/openai/codex/pull/21277)[mcp] Return Accept early per feedback.@mzeng-openai[@mzeng-openai](https://github.com/mzeng-openai)
- #21285[#21285](https://github.com/openai/codex/pull/21285)fix(bwrap): emit libcap after standalone archive@viyatb-oai[@viyatb-oai](https://github.com/viyatb-oai)
- #21312[#21312](https://github.com/openai/codex/pull/21312)release: bundle bwrap with Linux codex DotSlash artifact@bolinfest[@bolinfest](https://github.com/bolinfest)
- #19193[#19193](https://github.com/openai/codex/pull/19193)Support Codex Apps auth elicitations@mzeng-openai[@mzeng-openai](https://github.com/mzeng-openai)
- #20437[#20437](https://github.com/openai/codex/pull/20437)feat: add`session_id`@jif-oai[@jif-oai](https://github.com/jif-oai)
- #21328[#21328](https://github.com/openai/codex/pull/21328)test: isolate app-server-client in-process test state@jif-oai[@jif-oai](https://github.com/jif-oai)
- #21329[#21329](https://github.com/openai/codex/pull/21329)feat: include thread ID in MCP turn metadata@jif-oai[@jif-oai](https://github.com/jif-oai)
- #21332[#21332](https://github.com/openai/codex/pull/21332)feat: return session ID from thread/fork@jif-oai[@jif-oai](https://github.com/jif-oai)
- #21337[#21337](https://github.com/openai/codex/pull/21337)Revert "feat: support template interpolation in multi-agent usage hints"@jif-oai[@jif-oai](https://github.com/jif-oai)
- #21249[#21249](https://github.com/openai/codex/pull/21249)Propagate cache key and service tiers in compact@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #21182[#21182](https://github.com/openai/codex/pull/21182)Move installation ID resolution out of core startup@jif-oai[@jif-oai](https://github.com/jif-oai)
- #21214[#21214](https://github.com/openai/codex/pull/21214)chore: spawn MCP for memories@jif-oai[@jif-oai](https://github.com/jif-oai)
- #21336[#21336](https://github.com/openai/codex/pull/21336)feat(app-server): move v2`sessionId`onto`Thread`@jif-oai[@jif-oai](https://github.com/jif-oai)
- #21350[#21350](https://github.com/openai/codex/pull/21350)[codex] fix builtin MCP Windows path test@jif-oai[@jif-oai](https://github.com/jif-oai)
- #20971[#20971](https://github.com/openai/codex/pull/20971)2- Use string service tiers in session protocol@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #21278[#21278](https://github.com/openai/codex/pull/21278)Move message history out of core@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #21284[#21284](https://github.com/openai/codex/pull/21284)[codex] Add response.processed websocket request@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #21367[#21367](https://github.com/openai/codex/pull/21367)rollout: coalesce thread updated_at touches@jif-oai[@jif-oai](https://github.com/jif-oai)
- #21378[#21378](https://github.com/openai/codex/pull/21378)feat: move auto vaccum@jif-oai[@jif-oai](https://github.com/jif-oai)
- #21263[#21263](https://github.com/openai/codex/pull/21263)[codex] Coordinate OpenAI docs sample with API key setup@mifan-oai[@mifan-oai](https://github.com/mifan-oai)
- #21351[#21351](https://github.com/openai/codex/pull/21351)fix(tui): keep Ctrl-C stashed drafts after /clear@fcoury-oai[@fcoury-oai](https://github.com/fcoury-oai)
- #21389[#21389](https://github.com/openai/codex/pull/21389)vendor: update bubblewrap to 0.11.2@bolinfest[@bolinfest](https://github.com/bolinfest)
- #21281[#21281](https://github.com/openai/codex/pull/21281)Remove core MCP list tools op@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #21381[#21381](https://github.com/openai/codex/pull/21381)[codex] Handle git pagination flags by position@iceweasel-oai[@iceweasel-oai](https://github.com/iceweasel-oai)
- #21397[#21397](https://github.com/openai/codex/pull/21397)fix(tui): persist ctrl-c draft via app event@fcoury-oai[@fcoury-oai](https://github.com/fcoury-oai)
- #19431[#19431](https://github.com/openai/codex/pull/19431)Route opted-in MCP elicitations through Guardian@cd-oai[@cd-oai](https://github.com/cd-oai)
- #21107[#21107](https://github.com/openai/codex/pull/21107)Avoid noisy OTEL diagnostics in codex exec@cpaasch-oai[@cpaasch-oai](https://github.com/cpaasch-oai)
- #21390[#21390](https://github.com/openai/codex/pull/21390)Avoid hard-coded environment context shell@starr-openai[@starr-openai](https://github.com/starr-openai)
- #21090[#21090](https://github.com/openai/codex/pull/21090)[codex] Dedupe fallback model metadata warnings@canvrno-oai[@canvrno-oai](https://github.com/canvrno-oai)
- #21395[#21395](https://github.com/openai/codex/pull/21395)[codex] Split tool handlers into separate files@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #21401[#21401](https://github.com/openai/codex/pull/21401)[codex-tui] pass thread source for tui threads@rhan-oai[@rhan-oai](https://github.com/rhan-oai)
- #17090[#17090](https://github.com/openai/codex/pull/17090)[codex-analytics] emit tool item events from item lifecycle@rhan-oai[@rhan-oai](https://github.com/rhan-oai)
- #21409[#21409](https://github.com/openai/codex/pull/21409)[codex] Fix Windows sandbox git safe.directory for worktrees@iceweasel-oai[@iceweasel-oai](https://github.com/iceweasel-oai)
- #21379[#21379](https://github.com/openai/codex/pull/21379)Document Codex git commit attribution config@henzelmann-oai[@henzelmann-oai](https://github.com/henzelmann-oai)
- #21287[#21287](https://github.com/openai/codex/pull/21287)Move skills watcher to app-server@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #21416[#21416](https://github.com/openai/codex/pull/21416)[codex] Move tool specs into core handlers@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #21419[#21419](https://github.com/openai/codex/pull/21419)feat: Add marketplace source filtering and plugin share context@xl-openai[@xl-openai](https://github.com/xl-openai)
- #19905[#19905](https://github.com/openai/codex/pull/19905)Add compact lifecycle hooks (started by vincentkoc - external contrib)@eternal-openai[@eternal-openai](https://github.com/eternal-openai)
- #21460[#21460](https://github.com/openai/codex/pull/21460)Revert "Move skills watcher to app-server"@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #21450[#21450](https://github.com/openai/codex/pull/21450)fix(tui): clear first inline viewport render@fcoury-oai[@fcoury-oai](https://github.com/fcoury-oai)
- #21427[#21427](https://github.com/openai/codex/pull/21427)[codex] Delete tool handler plan indirection@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #21423[#21423](https://github.com/openai/codex/pull/21423)[codex] Add OpenAI Developers to tool suggest allowlist@mifan-oai[@mifan-oai](https://github.com/mifan-oai)
- #21340[#21340](https://github.com/openai/codex/pull/21340)[codex] allow shared config reads in app-server queue@xli-oai[@xli-oai](https://github.com/xli-oai)
- #21441[#21441](https://github.com/openai/codex/pull/21441)[codex] Parallelize skills list cwd loading@xli-oai[@xli-oai](https://github.com/xli-oai)
- #21481[#21481](https://github.com/openai/codex/pull/21481)Revert state DB injection and agent graph store@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)

Full release on Github[Full release on Github](https://github.com/openai/codex/releases/tag/rust-v0.129.0)
- 2026-05-06

### Codex analytics governance docs update

Updated the Codex enterprise governance guide with more detailed coverage of the Analytics dashboard charts, data export options, and enterprise Analytics API endpoints.
- 2026-05-05

### Create Codex access tokens

ChatGPT Enterprise workspace owners and admins can allow permitted members to create Codex access tokens for trusted, non-interactive Codex local workflows. Members can use access tokens to run Codex from scripts, schedulers, and private CI runners with their ChatGPT workspace identity.

Learn more inAccess tokens[Access tokens](/codex/enterprise/access-tokens).
- 2026-05-05

### Codex app26.429

### New features

- Added dictation cleanup plus a configurable dictation dictionary for names, file paths, and code symbols.
- Added zoom and download controls to the image lightbox.

### Performance improvements and bug fixes

- Improved voice and dictation error messages for microphone, connection, and quota failures.
- Fixed in-app browser comment markers so they stay aligned across scrolling, zoom, and responsive layout changes.
- Made pull request creation and recovery flows more reliable by preserving newly created pull request state, classifying more app-server failures as restart-required, and stopping exhausted remote reconnect loops.
- Additional performance improvements and bug fixes.

## April 2026

- 2026-04-30

### Codex CLI0.128.0
````$npminstall-g@openai/codex@0.128.0````
View details

## New Features

- Added persisted`/goal`workflows with app-server APIs, model tools, runtime continuation, and TUI controls for create, pause, resume, and clear. (#18073[#18073](https://github.com/openai/codex/pull/18073),#18074[#18074](https://github.com/openai/codex/pull/18074),#18075[#18075](https://github.com/openai/codex/pull/18075),#18076[#18076](https://github.com/openai/codex/pull/18076),#18077[#18077](https://github.com/openai/codex/pull/18077),#20082[#20082](https://github.com/openai/codex/pull/20082))
- Added`codex update`, configurable TUI keymaps, plan-mode nudges, action-required terminal titles, and active-turn`/statusline`and`/title`edits. (#19933[#19933](https://github.com/openai/codex/pull/19933),#18593[#18593](https://github.com/openai/codex/pull/18593),#19901[#19901](https://github.com/openai/codex/pull/19901),#18372[#18372](https://github.com/openai/codex/pull/18372),#19917[#19917](https://github.com/openai/codex/pull/19917))
- Expanded permission profiles with built-in defaults, sandbox CLI profile selection, cwd controls, and active-profile metadata for clients. (#19900[#19900](https://github.com/openai/codex/pull/19900),#20117[#20117](https://github.com/openai/codex/pull/20117),#20118[#20118](https://github.com/openai/codex/pull/20118),#20095[#20095](https://github.com/openai/codex/pull/20095))
- Improved plugin workflows with marketplace installation, remote bundle caching, remote uninstall, plugin-bundled hooks, hook enablement state, and external-agent config import. (#18704[#18704](https://github.com/openai/codex/pull/18704),#19914[#19914](https://github.com/openai/codex/pull/19914),#19456[#19456](https://github.com/openai/codex/pull/19456),#19705[#19705](https://github.com/openai/codex/pull/19705),#19840[#19840](https://github.com/openai/codex/pull/19840),#19949[#19949](https://github.com/openai/codex/pull/19949))
- Added external agent session import, including background imports and imported-session title handling. (#19895[#19895](https://github.com/openai/codex/pull/19895),#20284[#20284](https://github.com/openai/codex/pull/20284),#20261[#20261](https://github.com/openai/codex/pull/20261))
- Made MultiAgentV2 configuration more explicit with thread caps, wait-time controls, root/subagent hints, and v2-specific depth handling. (#19360[#19360](https://github.com/openai/codex/pull/19360),#19792[#19792](https://github.com/openai/codex/pull/19792),#19805[#19805](https://github.com/openai/codex/pull/19805),#20052[#20052](https://github.com/openai/codex/pull/20052),#20180[#20180](https://github.com/openai/codex/pull/20180))

## Bug Fixes

- Fixed several resume and interruption issues, including stale interrupt hangs, persisted provider restoration, large remote resume responses, and slow filtered resume lists. (#18392[#18392](https://github.com/openai/codex/pull/18392),#19287[#19287](https://github.com/openai/codex/pull/19287),#19920[#19920](https://github.com/openai/codex/pull/19920),#19591[#19591](https://github.com/openai/codex/pull/19591))
- Improved TUI reliability around terminal resize reflow, markdown list spacing, slash-command popup layout, keyboard cleanup, shell-mode escape, and working status updates. (#18575[#18575](https://github.com/openai/codex/pull/18575),#19706[#19706](https://github.com/openai/codex/pull/19706),#19511[#19511](https://github.com/openai/codex/pull/19511),#19625[#19625](https://github.com/openai/codex/pull/19625),#19986[#19986](https://github.com/openai/codex/pull/19986),#19939[#19939](https://github.com/openai/codex/pull/19939))
- Hardened managed network behavior for deferred denials, proxy bypass defaults, resolved target checks, IPv6 host matching, and`git -C`approval handling. (#19184[#19184](https://github.com/openai/codex/pull/19184),#20002[#20002](https://github.com/openai/codex/pull/20002),#19999[#19999](https://github.com/openai/codex/pull/19999),#19995[#19995](https://github.com/openai/codex/pull/19995),#20085[#20085](https://github.com/openai/codex/pull/20085))
- Fixed Windows sandbox and PTY edge cases, including pseudoconsole startup, elevated runner process handling, core shell environment inheritance, and named-pipe validation. (#20042[#20042](https://github.com/openai/codex/pull/20042),#19211[#19211](https://github.com/openai/codex/pull/19211),#20089[#20089](https://github.com/openai/codex/pull/20089),#19283[#19283](https://github.com/openai/codex/pull/19283))
- Fixed Bedrock model support for`apply_patch`, GPT-5.4 reasoning levels, and updated Bedrock GPT-5.4 endpoint/model metadata. (#19416[#19416](https://github.com/openai/codex/pull/19416),#19461[#19461](https://github.com/openai/codex/pull/19461),#20109[#20109](https://github.com/openai/codex/pull/20109))
- Fixed MCP/plugin edge cases around stdio server cleanup, plugin MCP approval persistence, and custom MCP metadata isolation. (#19753[#19753](https://github.com/openai/codex/pull/19753),#19537[#19537](https://github.com/openai/codex/pull/19537),#19836[#19836](https://github.com/openai/codex/pull/19836),#19875[#19875](https://github.com/openai/codex/pull/19875))

## Documentation

- Updated the bundled OpenAI Docs skill for GPT-5.5,`gpt-image-2`, and clearer upgrade guidance. (#19407[#19407](https://github.com/openai/codex/pull/19407),#19443[#19443](https://github.com/openai/codex/pull/19443),#19422[#19422](https://github.com/openai/codex/pull/19422))
- Clarified contributor-facing docs, including the PR template, Rust async trait guidance, and README wording. (#19912[#19912](https://github.com/openai/codex/pull/19912),#20242[#20242](https://github.com/openai/codex/pull/20242),#19514[#19514](https://github.com/openai/codex/pull/19514))
- Added a checked-in`codex-core`public API listing and a ThreadManager sample crate. (#20243[#20243](https://github.com/openai/codex/pull/20243),#20141[#20141](https://github.com/openai/codex/pull/20141))

## Chores

- Published`codex-app-server`release artifacts, stopped publishing GNU Linux binaries, and increased release workflow timeouts. (#19447[#19447](https://github.com/openai/codex/pull/19447),#19445[#19445](https://github.com/openai/codex/pull/19445),#20271[#20271](https://github.com/openai/codex/pull/20271),#20343[#20343](https://github.com/openai/codex/pull/20343))
- Added Codex-pinned versioning for the Python app-server SDK package. (#18996[#18996](https://github.com/openai/codex/pull/18996))
- Deprecated`--full-auto`while steering users toward explicit permission profiles and trust flows. (#20133[#20133](https://github.com/openai/codex/pull/20133))
- Stabilized CI and release plumbing with Bazel setup migration, release smoke-test pinning, and updated workflow pins/timeouts. (#19851[#19851](https://github.com/openai/codex/pull/19851),#19854[#19854](https://github.com/openai/codex/pull/19854),#19472[#19472](https://github.com/openai/codex/pull/19472),#19609[#19609](https://github.com/openai/codex/pull/19609))

## Changelog

Full Changelog:rust-v0.125.0...rust-v0.128.0[rust-v0.125.0...rust-v0.128.0](https://github.com/openai/codex/compare/rust-v0.125.0...rust-v0.128.0)

- #19124[#19124](https://github.com/openai/codex/pull/19124)Make MultiAgentV2 interruption markers assistant-authored@jif-oai[@jif-oai](https://github.com/jif-oai)
- #19354[#19354](https://github.com/openai/codex/pull/19354)chore: alias max_concurrent_threads_per_session@jif-oai[@jif-oai](https://github.com/jif-oai)
- #19360[#19360](https://github.com/openai/codex/pull/19360)feat: surface multi-agent thread limit in spawn description@jif-oai[@jif-oai](https://github.com/jif-oai)
- #19351[#19351](https://github.com/openai/codex/pull/19351)Add agents.interrupt_message for interruption markers@jif-oai[@jif-oai](https://github.com/jif-oai)
- #18392[#18392](https://github.com/openai/codex/pull/18392)Fix hang on turn/interrupt@danwang-oai[@danwang-oai](https://github.com/danwang-oai)
- #19380[#19380](https://github.com/openai/codex/pull/19380)chore: drop MCP Plugins and App from Morpheus@jif-oai[@jif-oai](https://github.com/jif-oai)
- #18907[#18907](https://github.com/openai/codex/pull/18907)respect workspace option for disabling plugins@zamoshchin-openai[@zamoshchin-openai](https://github.com/zamoshchin-openai)
- #19283[#19283](https://github.com/openai/codex/pull/19283)check PID of named pipe consumer@iceweasel-oai[@iceweasel-oai](https://github.com/iceweasel-oai)
- #19407[#19407](https://github.com/openai/codex/pull/19407)Update bundled OpenAI Docs skill for GPT-5.5@kkahadze-oai[@kkahadze-oai](https://github.com/kkahadze-oai)
- #19163[#19163](https://github.com/openai/codex/pull/19163)Harden package-manager install policy@mcgrew-oai[@mcgrew-oai](https://github.com/mcgrew-oai)
- #19416[#19416](https://github.com/openai/codex/pull/19416)Fix: use function apply_patch tool for Bedrock model@celia-oai[@celia-oai](https://github.com/celia-oai)
- #19093[#19093](https://github.com/openai/codex/pull/19093)[codex] Omit fork turns from thread started notifications@euroelessar[@euroelessar](https://github.com/euroelessar)
- #19244[#19244](https://github.com/openai/codex/pull/19244)Update unix socket transport to use WebSocket upgrade@willwang-openai[@willwang-openai](https://github.com/willwang-openai)
- #19170[#19170](https://github.com/openai/codex/pull/19170)Skip disabled rows in selection menu numbering and default focus@canvrno-oai[@canvrno-oai](https://github.com/canvrno-oai)
- #19414[#19414](https://github.com/openai/codex/pull/19414)permissions: make legacy profile conversion cwd-free@bolinfest[@bolinfest](https://github.com/bolinfest)
- #18900[#18900](https://github.com/openai/codex/pull/18900)Migrate fork and resume reads to thread store@wiltzius-openai[@wiltzius-openai](https://github.com/wiltzius-openai)
- #19445[#19445](https://github.com/openai/codex/pull/19445)ci: stop publishing GNU Linux release artifacts@bolinfest[@bolinfest](https://github.com/bolinfest)
- #19443[#19443](https://github.com/openai/codex/pull/19443)Add gpt-image-2 to bundled OpenAI Docs skill@kkahadze-oai[@kkahadze-oai](https://github.com/kkahadze-oai)
- #18584[#18584](https://github.com/openai/codex/pull/18584)[4/4] Honor Streamable HTTP MCP placement@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #19447[#19447](https://github.com/openai/codex/pull/19447)ci: publish codex-app-server release artifacts@bolinfest[@bolinfest](https://github.com/bolinfest)
- #19422[#19422](https://github.com/openai/codex/pull/19422)Clarify bundled OpenAI Docs upgrade guide wording@kkahadze-oai[@kkahadze-oai](https://github.com/kkahadze-oai)
- #19266[#19266](https://github.com/openai/codex/pull/19266)[codex] add non-local thread store regression harness@wiltzius-openai[@wiltzius-openai](https://github.com/wiltzius-openai)
- #19098[#19098](https://github.com/openai/codex/pull/19098)feat: Compress skill paths with root aliases@xl-openai[@xl-openai](https://github.com/xl-openai)
- #19207[#19207](https://github.com/openai/codex/pull/19207)[codex] Forward Codex Apps tool call IDs to backend metadata@rreichel3-oai[@rreichel3-oai](https://github.com/rreichel3-oai)
- #19453[#19453](https://github.com/openai/codex/pull/19453)Serialize legacy Windows PowerShell sandbox tests@dylan-hurd-oai[@dylan-hurd-oai](https://github.com/dylan-hurd-oai)
- #19234[#19234](https://github.com/openai/codex/pull/19234)Refactor log DB into LogWriter interface@rasmusrygaard[@rasmusrygaard](https://github.com/rasmusrygaard)
- #19461[#19461](https://github.com/openai/codex/pull/19461)fix: Bedrock GPT-5.4 reasoning levels@celia-oai[@celia-oai](https://github.com/celia-oai)
- #19449[#19449](https://github.com/openai/codex/pull/19449)permissions: remove legacy read-only access modes@bolinfest[@bolinfest](https://github.com/bolinfest)
- #19472[#19472](https://github.com/openai/codex/pull/19472)ci: pin codex-action v1.7@viyatb-oai[@viyatb-oai](https://github.com/viyatb-oai)
- #19468[#19468](https://github.com/openai/codex/pull/19468)Fix Bazel cargo_bin runfiles paths@fjord-oai[@fjord-oai](https://github.com/fjord-oai)
- #19410[#19410](https://github.com/openai/codex/pull/19410)Remove js_repl feature@fjord-oai[@fjord-oai](https://github.com/fjord-oai)
- #18073[#18073](https://github.com/openai/codex/pull/18073)Add goal persistence foundation (1 / 5)@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #18074[#18074](https://github.com/openai/codex/pull/18074)Add goal app-server API (2 / 5)@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #18075[#18075](https://github.com/openai/codex/pull/18075)Add goal model tools (3 / 5)@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #18076[#18076](https://github.com/openai/codex/pull/18076)Add goal core runtime (4 / 5)@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #18077[#18077](https://github.com/openai/codex/pull/18077)Add goal TUI UX (5 / 5)@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #19454[#19454](https://github.com/openai/codex/pull/19454)Split approval matrix test groups@dylan-hurd-oai[@dylan-hurd-oai](https://github.com/dylan-hurd-oai)
- #19514[#19514](https://github.com/openai/codex/pull/19514)Fix codex-rs README grammar@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #19459[#19459](https://github.com/openai/codex/pull/19459)Enable unavailable dummy tools by default@mzeng-openai[@mzeng-openai](https://github.com/mzeng-openai)
- #19524[#19524](https://github.com/openai/codex/pull/19524)[codex] Prune unused codex-mcp API and duplicate helpers@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #19526[#19526](https://github.com/openai/codex/pull/19526)[codex] Order codex-mcp items by visibility@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #19578[#19578](https://github.com/openai/codex/pull/19578)fix: increase Bazel timeout to 45 minutes@bolinfest[@bolinfest](https://github.com/bolinfest)
- #19287[#19287](https://github.com/openai/codex/pull/19287)Restore persisted model provider on thread resume@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #19593[#19593](https://github.com/openai/codex/pull/19593)test: isolate remote thread store regression from plugin warmups@bolinfest[@bolinfest](https://github.com/bolinfest)
- #19511[#19511](https://github.com/openai/codex/pull/19511)Keep slash command popup columns stable while scrolling@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #19595[#19595](https://github.com/openai/codex/pull/19595)[codex] Bypass managed network for escalated exec@viyatb-oai[@viyatb-oai](https://github.com/viyatb-oai)
- #19604[#19604](https://github.com/openai/codex/pull/19604)test: stabilize app-server path assertions on Windows@bolinfest[@bolinfest](https://github.com/bolinfest)
- #19609[#19609](https://github.com/openai/codex/pull/19609)fix: restore 30-minute timeout for Bazel builds@bolinfest[@bolinfest](https://github.com/bolinfest)
- #19389[#19389](https://github.com/openai/codex/pull/19389)Guard npm update readiness@shijie-oai[@shijie-oai](https://github.com/shijie-oai)
- #18575[#18575](https://github.com/openai/codex/pull/18575)fix(tui): reflow scrollback on terminal resize@fcoury-oai[@fcoury-oai](https://github.com/fcoury-oai)
- #19610[#19610](https://github.com/openai/codex/pull/19610)Support end_turn in response.completed@andmis[@andmis](https://github.com/andmis)
- #19640[#19640](https://github.com/openai/codex/pull/19640)[codex] remove responses command@tibo-openai[@tibo-openai](https://github.com/tibo-openai)
- #19683[#19683](https://github.com/openai/codex/pull/19683)test: harden app-server integration tests@bolinfest[@bolinfest](https://github.com/bolinfest)
- #18904[#18904](https://github.com/openai/codex/pull/18904)feat: load AgentIdentity from JWT login/env@efrazer-oai[@efrazer-oai](https://github.com/efrazer-oai)
- #19606[#19606](https://github.com/openai/codex/pull/19606)permissions: make runtime config profile-backed@bolinfest[@bolinfest](https://github.com/bolinfest)
- #19392[#19392](https://github.com/openai/codex/pull/19392)permissions: derive compatibility policies from profiles@bolinfest[@bolinfest](https://github.com/bolinfest)
- #19484[#19484](https://github.com/openai/codex/pull/19484)Lift app-server JSON-RPC error handling to request boundary@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #19487[#19487](https://github.com/openai/codex/pull/19487)[codex] Move config loading into codex-config@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #19393[#19393](https://github.com/openai/codex/pull/19393)permissions: migrate approval and sandbox consumers to profiles@bolinfest[@bolinfest](https://github.com/bolinfest)
- #19726[#19726](https://github.com/openai/codex/pull/19726)Fix codex-core config test type paths@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #19727[#19727](https://github.com/openai/codex/pull/19727)test: increase core-all-test shard count to 16@bolinfest[@bolinfest](https://github.com/bolinfest)
- #19725[#19725](https://github.com/openai/codex/pull/19725)Split MCP connection modules@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #19605[#19605](https://github.com/openai/codex/pull/19605)Delete unused ResponseItem::Message.end_turn@andmis[@andmis](https://github.com/andmis)
- #19394[#19394](https://github.com/openai/codex/pull/19394)permissions: remove core legacy policy round trips@bolinfest[@bolinfest](https://github.com/bolinfest)
- #19733[#19733](https://github.com/openai/codex/pull/19733)Allow agents.max_threads to work with multi_agent_v2@andmis[@andmis](https://github.com/andmis)
- #19395[#19395](https://github.com/openai/codex/pull/19395)permissions: finish profile-backed app surfaces@bolinfest[@bolinfest](https://github.com/bolinfest)
- #19739[#19739](https://github.com/openai/codex/pull/19739)inline hostname resolution for remote sandbox config@abhinav-oai[@abhinav-oai](https://github.com/abhinav-oai)
- #19734[#19734](https://github.com/openai/codex/pull/19734)permissions: centralize legacy sandbox projection@bolinfest[@bolinfest](https://github.com/bolinfest)
- #19058[#19058](https://github.com/openai/codex/pull/19058)Add /auto-review-denials retry approval flow@won-openai[@won-openai](https://github.com/won-openai)
- #19735[#19735](https://github.com/openai/codex/pull/19735)permissions: store only constrained permission profiles@bolinfest[@bolinfest](https://github.com/bolinfest)
- #19736[#19736](https://github.com/openai/codex/pull/19736)permissions: constrain requirements as profiles@bolinfest[@bolinfest](https://github.com/bolinfest)
- #19737[#19737](https://github.com/openai/codex/pull/19737)permissions: derive legacy exec policies at boundaries@bolinfest[@bolinfest](https://github.com/bolinfest)
- #19779[#19779](https://github.com/openai/codex/pull/19779)Add Codex issue digest skill@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #19792[#19792](https://github.com/openai/codex/pull/19792)multi_agent_v2: move thread cap into feature config@jif-oai[@jif-oai](https://github.com/jif-oai)
- #18982[#18982](https://github.com/openai/codex/pull/18982)feat: use git-backed workspace diffs for memory consolidation@jif-oai[@jif-oai](https://github.com/jif-oai)
- #19809[#19809](https://github.com/openai/codex/pull/19809)Allow Phase 2 memory claims after retry exhaustion@jif-oai[@jif-oai](https://github.com/jif-oai)
- #19812[#19812](https://github.com/openai/codex/pull/19812)Avoid rewriting Phase 2 selection on clean workspace@jif-oai[@jif-oai](https://github.com/jif-oai)
- #19813[#19813](https://github.com/openai/codex/pull/19813)nit: one more fix@jif-oai[@jif-oai](https://github.com/jif-oai)
- #19818[#19818](https://github.com/openai/codex/pull/19818)chore: split memories part 1@jif-oai[@jif-oai](https://github.com/jif-oai)
- #19510[#19510](https://github.com/openai/codex/pull/19510)Hide rewind preview when no user message exists@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #19618[#19618](https://github.com/openai/codex/pull/19618)Persist shell mode commands in prompt history@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #19709[#19709](https://github.com/openai/codex/pull/19709)Render delegated patch approval details@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #19490[#19490](https://github.com/openai/codex/pull/19490)Streamline plugin, apps, and skills handlers@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #19762[#19762](https://github.com/openai/codex/pull/19762)refactor: make auth loading async@efrazer-oai[@efrazer-oai](https://github.com/efrazer-oai)
- #19854[#19854](https://github.com/openai/codex/pull/19854)ci: pin npm staging smoke test to a recent rust-release run@bolinfest[@bolinfest](https://github.com/bolinfest)
- #19851[#19851](https://github.com/openai/codex/pull/19851)ci: migrate Bazel setup away from archived setup-bazelisk@bolinfest[@bolinfest](https://github.com/bolinfest)
- #19491[#19491](https://github.com/openai/codex/pull/19491)Streamline account and command handlers@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #19771[#19771](https://github.com/openai/codex/pull/19771)fix: filter dynamic deferred tools from model_visible_specs@sayan-oai[@sayan-oai](https://github.com/sayan-oai)
- #19863[#19863](https://github.com/openai/codex/pull/19863)[codex-analytics] remove ga flag@rhan-oai[@rhan-oai](https://github.com/rhan-oai)
- #19865[#19865](https://github.com/openai/codex/pull/19865)Cap original-detail image token estimates@fjord-oai[@fjord-oai](https://github.com/fjord-oai)
- #19591[#19591](https://github.com/openai/codex/pull/19591)Fix filtered thread-list resume regression in TUI@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #19513[#19513](https://github.com/openai/codex/pull/19513)Delay approval prompts while typing@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #19706[#19706](https://github.com/openai/codex/pull/19706)Preserve TUI markdown list spacing after code blocks@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #19841[#19841](https://github.com/openai/codex/pull/19841)permissions: remove cwd special path@bolinfest[@bolinfest](https://github.com/bolinfest)
- #19492[#19492](https://github.com/openai/codex/pull/19492)Streamline thread start handler@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #19874[#19874](https://github.com/openai/codex/pull/19874)[codex-backend] Prefer state git metadata in filtered thread lists@joeytrasatti-openai[@joeytrasatti-openai](https://github.com/joeytrasatti-openai)
- #19493[#19493](https://github.com/openai/codex/pull/19493)Streamline thread mutation handlers@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #19862[#19862](https://github.com/openai/codex/pull/19862)[codex] Shard exec Bazel integration test@starr-openai[@starr-openai](https://github.com/starr-openai)
- #18996[#18996](https://github.com/openai/codex/pull/18996)Publish Python SDK with Codex-pinned versioning@sdcoffey[@sdcoffey](https://github.com/sdcoffey)
- #19494[#19494](https://github.com/openai/codex/pull/19494)Streamline thread read handlers@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #19839[#19839](https://github.com/openai/codex/pull/19839)[codex] Trace cancelled inference streams@cassirer-openai[@cassirer-openai](https://github.com/cassirer-openai)
- #19495[#19495](https://github.com/openai/codex/pull/19495)Streamline thread resume and fork handlers@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #19497[#19497](https://github.com/openai/codex/pull/19497)Streamline turn and realtime handlers@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #18372[#18372](https://github.com/openai/codex/pull/18372)Show action required in terminal title@canvrno-oai[@canvrno-oai](https://github.com/canvrno-oai)
- #19884[#19884](https://github.com/openai/codex/pull/19884)Add MCP app feature flag@mzeng-openai[@mzeng-openai](https://github.com/mzeng-openai)
- #19498[#19498](https://github.com/openai/codex/pull/19498)Streamline review and feedback handlers@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #19772[#19772](https://github.com/openai/codex/pull/19772)permissions: derive config defaults as profiles@bolinfest[@bolinfest](https://github.com/bolinfest)
- #19836[#19836](https://github.com/openai/codex/pull/19836)disallow fileparams metadata for custom mcps@colby-oai[@colby-oai](https://github.com/colby-oai)
- #19892[#19892](https://github.com/openai/codex/pull/19892)Refactor exec-server filesystem API into codex-file-system@miz-openai[@miz-openai](https://github.com/miz-openai)
- #19452[#19452](https://github.com/openai/codex/pull/19452)Stabilize plugin MCP fixture tests@dylan-hurd-oai[@dylan-hurd-oai](https://github.com/dylan-hurd-oai)
- #19481[#19481](https://github.com/openai/codex/pull/19481)Remove ghost snapshots@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #19773[#19773](https://github.com/openai/codex/pull/19773)permissions: require profiles in TUI thread state@bolinfest[@bolinfest](https://github.com/bolinfest)
- #19917[#19917](https://github.com/openai/codex/pull/19917)Allow /statusline and /title slash commands during active turns@canvrno-oai[@canvrno-oai](https://github.com/canvrno-oai)
- #19763[#19763](https://github.com/openai/codex/pull/19763)refactor: load agent identity runtime eagerly@efrazer-oai[@efrazer-oai](https://github.com/efrazer-oai)
- #17689[#17689](https://github.com/openai/codex/pull/17689)[codex-analytics] include user agent in default headers@marksteinbrick-oai[@marksteinbrick-oai](https://github.com/marksteinbrick-oai)
- #19912[#19912](https://github.com/openai/codex/pull/19912)Clarify PR template invitation requirement@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #19630[#19630](https://github.com/openai/codex/pull/19630)Avoid persisting ShutdownComplete after thread shutdown@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #19774[#19774](https://github.com/openai/codex/pull/19774)permissions: make SessionConfigured profile-only@bolinfest[@bolinfest](https://github.com/bolinfest)
- #19775[#19775](https://github.com/openai/codex/pull/19775)permissions: derive snapshot sandbox projections@bolinfest[@bolinfest](https://github.com/bolinfest)
- #19920[#19920](https://github.com/openai/codex/pull/19920)Allow large remote app-server resume responses@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #19776[#19776](https://github.com/openai/codex/pull/19776)permissions: store thread sessions as profiles@bolinfest[@bolinfest](https://github.com/bolinfest)
- #19899[#19899](https://github.com/openai/codex/pull/19899)app-server-protocol: mark permission profiles experimental@bolinfest[@bolinfest](https://github.com/bolinfest)
- #19933[#19933](https://github.com/openai/codex/pull/19933)Add`codex update`command@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #19914[#19914](https://github.com/openai/codex/pull/19914)feat: Cache remote plugin bundles on install@xl-openai[@xl-openai](https://github.com/xl-openai)
- #19456[#19456](https://github.com/openai/codex/pull/19456)Add remote plugin uninstall API@xli-oai[@xli-oai](https://github.com/xli-oai)
- #19805[#19805](https://github.com/openai/codex/pull/19805)Add MultiAgentV2 root and subagent context hints@jif-oai[@jif-oai](https://github.com/jif-oai)
- #19860[#19860](https://github.com/openai/codex/pull/19860)feat: split memories part 2@jif-oai[@jif-oai](https://github.com/jif-oai)
- #19961[#19961](https://github.com/openai/codex/pull/19961)feat: fix hinting 2@jif-oai[@jif-oai](https://github.com/jif-oai)
- #19963[#19963](https://github.com/openai/codex/pull/19963)feat: fix hinting 3@jif-oai[@jif-oai](https://github.com/jif-oai)
- #19967[#19967](https://github.com/openai/codex/pull/19967)Stabilize memory Phase 2 input ordering@jif-oai[@jif-oai](https://github.com/jif-oai)
- #19970[#19970](https://github.com/openai/codex/pull/19970)feat: trigger memories from user turns with cooldown@jif-oai[@jif-oai](https://github.com/jif-oai)
- #19904[#19904](https://github.com/openai/codex/pull/19904)fix: configure AgentIdentity AuthAPI base URL@efrazer-oai[@efrazer-oai](https://github.com/efrazer-oai)
- #19990[#19990](https://github.com/openai/codex/pull/19990)feat: skip memory startup when Codex rate limits are low@jif-oai[@jif-oai](https://github.com/jif-oai)
- #19998[#19998](https://github.com/openai/codex/pull/19998)feat: house-keeping memories 1@jif-oai[@jif-oai](https://github.com/jif-oai)
- #20000[#20000](https://github.com/openai/codex/pull/20000)feat: house-keeping memories 2@jif-oai[@jif-oai](https://github.com/jif-oai)
- #19832[#19832](https://github.com/openai/codex/pull/19832)Preserve assistant phase for replayed messages@friel-openai[@friel-openai](https://github.com/friel-openai)
- #19625[#19625](https://github.com/openai/codex/pull/19625)Reset TUI keyboard reporting on exit@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #18593[#18593](https://github.com/openai/codex/pull/18593)feat(tui): add configurable keymap support@fcoury-oai[@fcoury-oai](https://github.com/fcoury-oai)
- #19846[#19846](https://github.com/openai/codex/pull/19846)[sandbox] Enforce protected workspace metadata paths@evawong-oai[@evawong-oai](https://github.com/evawong-oai)
- #20005[#20005](https://github.com/openai/codex/pull/20005)feat: house-keeping memories 3@jif-oai[@jif-oai](https://github.com/jif-oai)
- #19929[#19929](https://github.com/openai/codex/pull/19929)TUI: use cumulative turn duration for worked-for separator@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #19753[#19753](https://github.com/openai/codex/pull/19753)Terminate stdio MCP servers on shutdown to avoid process leaks@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #19473[#19473](https://github.com/openai/codex/pull/19473)Add turn start timestamp to turn metadata@mchen-oai[@mchen-oai](https://github.com/mchen-oai)
- #19875[#19875](https://github.com/openai/codex/pull/19875)Strip connector provenance metadata from custom MCP tools@colby-oai[@colby-oai](https://github.com/colby-oai)
- #19764[#19764](https://github.com/openai/codex/pull/19764)feat: verify agent identity JWTs with JWKS@efrazer-oai[@efrazer-oai](https://github.com/efrazer-oai)
- #19847[#19847](https://github.com/openai/codex/pull/19847)Enforce workspace metadata protections in Seatbelt@evawong-oai[@evawong-oai](https://github.com/evawong-oai)
- #19509[#19509](https://github.com/openai/codex/pull/19509)Record MCP result telemetry on mcp.tools.call spans@mchen-oai[@mchen-oai](https://github.com/mchen-oai)
- #19907[#19907](https://github.com/openai/codex/pull/19907)Clarify network approval auto-review prompts@maja-openai[@maja-openai](https://github.com/maja-openai)
- #19901[#19901](https://github.com/openai/codex/pull/19901)feat(tui): suggest plan mode from composer drafts@fcoury-oai[@fcoury-oai](https://github.com/fcoury-oai)
- #19931[#19931](https://github.com/openai/codex/pull/19931)Move local /resume cwd filtering into thread/list@canvrno-oai[@canvrno-oai](https://github.com/canvrno-oai)
- #19986[#19986](https://github.com/openai/codex/pull/19986)fix(tui): let esc exit empty shell mode@fcoury-oai[@fcoury-oai](https://github.com/fcoury-oai)
- #19895[#19895](https://github.com/openai/codex/pull/19895)External agent session support@stefanstokic-oai[@stefanstokic-oai](https://github.com/stefanstokic-oai)
- #20002[#20002](https://github.com/openai/codex/pull/20002)fix(network-proxy): tighten network proxy bypass defaults@viyatb-oai[@viyatb-oai](https://github.com/viyatb-oai)
- #19900[#19900](https://github.com/openai/codex/pull/19900)permissions: add built-in default profiles@bolinfest[@bolinfest](https://github.com/bolinfest)
- #20045[#20045](https://github.com/openai/codex/pull/20045)Fix plan mode nudge test after task completion signature change@canvrno-oai[@canvrno-oai](https://github.com/canvrno-oai)
- #19432[#19432](https://github.com/openai/codex/pull/19432)[codex] Add token usage to turn tracing spans@charley-openai[@charley-openai](https://github.com/charley-openai)
- #20001[#20001](https://github.com/openai/codex/pull/20001)fix(network-proxy): harden linux proxy bridge helpers@viyatb-oai[@viyatb-oai](https://github.com/viyatb-oai)
- #19959[#19959](https://github.com/openai/codex/pull/19959)Fix log db batch flush flake@dylan-hurd-oai[@dylan-hurd-oai](https://github.com/dylan-hurd-oai)
- #17373[#17373](https://github.com/openai/codex/pull/17373)app-server: run initialized rpcs with keyed serialization@euroelessar[@euroelessar](https://github.com/euroelessar)
- #19708[#19708](https://github.com/openai/codex/pull/19708)Load cloud requirements for agent identity@shijie-oai[@shijie-oai](https://github.com/shijie-oai)
- #19999[#19999](https://github.com/openai/codex/pull/19999)fix(network-proxy): recheck network proxy connect targets@viyatb-oai[@viyatb-oai](https://github.com/viyatb-oai)
- #20047[#20047](https://github.com/openai/codex/pull/20047)app-server: allow remote_control runtime feature override@euroelessar[@euroelessar](https://github.com/euroelessar)
- #20052[#20052](https://github.com/openai/codex/pull/20052)Make MultiAgentV2 wait minimum configurable@jif-oai[@jif-oai](https://github.com/jif-oai)
- #20008[#20008](https://github.com/openai/codex/pull/20008)tui: use permission profiles for sandbox state@bolinfest[@bolinfest](https://github.com/bolinfest)
- #20068[#20068](https://github.com/openai/codex/pull/20068)app-server: disable remote control without sqlite@euroelessar[@euroelessar](https://github.com/euroelessar)
- #20066[#20066](https://github.com/openai/codex/pull/20066)[rollout-trace] Include x-request-id in rollout trace.@cassirer-openai[@cassirer-openai](https://github.com/cassirer-openai)
- #19705[#19705](https://github.com/openai/codex/pull/19705)Discover hooks bundled with plugins@abhinav-oai[@abhinav-oai](https://github.com/abhinav-oai)
- #18704[#18704](https://github.com/openai/codex/pull/18704)/plugins: add marketplace install flow@canvrno-oai[@canvrno-oai](https://github.com/canvrno-oai)
- #20085[#20085](https://github.com/openai/codex/pull/20085)fix: don't auto approve git -C ...@owenlin0[@owenlin0](https://github.com/owenlin0)
- #20088[#20088](https://github.com/openai/codex/pull/20088)Fix flaky plugin hook env test@abhinav-oai[@abhinav-oai](https://github.com/abhinav-oai)
- #19995[#19995](https://github.com/openai/codex/pull/19995)fix(network-proxy): normalize network proxy host matching@viyatb-oai[@viyatb-oai](https://github.com/viyatb-oai)
- #20010[#20010](https://github.com/openai/codex/pull/20010)core tests: submit turns with permission profiles@bolinfest[@bolinfest](https://github.com/bolinfest)
- #20092[#20092](https://github.com/openai/codex/pull/20092)Return None when auth refresh fails@gpeal[@gpeal](https://github.com/gpeal)
- #19919[#19919](https://github.com/openai/codex/pull/19919)app-server: notify clients of remote-control status changes@euroelessar[@euroelessar](https://github.com/euroelessar)
- #20097[#20097](https://github.com/openai/codex/pull/20097)Refine Codex issue digest summaries@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #20011[#20011](https://github.com/openai/codex/pull/20011)core tests: build user turns from permission profiles@bolinfest[@bolinfest](https://github.com/bolinfest)
- #20013[#20013](https://github.com/openai/codex/pull/20013)core tests: migrate more turns to permission profiles@bolinfest[@bolinfest](https://github.com/bolinfest)
- #20015[#20015](https://github.com/openai/codex/pull/20015)core tests: configure profiles directly@bolinfest[@bolinfest](https://github.com/bolinfest)
- #20016[#20016](https://github.com/openai/codex/pull/20016)core tests: send model turns with permission profiles@bolinfest[@bolinfest](https://github.com/bolinfest)
- #20100[#20100](https://github.com/openai/codex/pull/20100)Increase plugin hook env test timeout@abhinav-oai[@abhinav-oai](https://github.com/abhinav-oai)
- #20018[#20018](https://github.com/openai/codex/pull/20018)core tests: migrate model/personality turns to profiles@bolinfest[@bolinfest](https://github.com/bolinfest)
- #20021[#20021](https://github.com/openai/codex/pull/20021)core tests: migrate view image turns to profiles@bolinfest[@bolinfest](https://github.com/bolinfest)
- #20024[#20024](https://github.com/openai/codex/pull/20024)core tests: migrate safety check turns to profiles@bolinfest[@bolinfest](https://github.com/bolinfest)
- #20026[#20026](https://github.com/openai/codex/pull/20026)core tests: migrate plan item turns to profiles@bolinfest[@bolinfest](https://github.com/bolinfest)
- #20027[#20027](https://github.com/openai/codex/pull/20027)core tests: migrate tools tests to permission profiles@bolinfest[@bolinfest](https://github.com/bolinfest)
- #20028[#20028](https://github.com/openai/codex/pull/20028)core tests: migrate permissions message tests to profiles@bolinfest[@bolinfest](https://github.com/bolinfest)
- #20030[#20030](https://github.com/openai/codex/pull/20030)core tests: migrate exec policy turns to profiles@bolinfest[@bolinfest](https://github.com/bolinfest)
- #20032[#20032](https://github.com/openai/codex/pull/20032)core tests: migrate prompt caching turns to profiles@bolinfest[@bolinfest](https://github.com/bolinfest)
- #20033[#20033](https://github.com/openai/codex/pull/20033)core tests: migrate request permissions tool turns to profiles@bolinfest[@bolinfest](https://github.com/bolinfest)
- #20034[#20034](https://github.com/openai/codex/pull/20034)core tests: migrate zsh-fork permissions to profiles@bolinfest[@bolinfest](https://github.com/bolinfest)
- #20035[#20035](https://github.com/openai/codex/pull/20035)core tests: migrate compact turns to profiles@bolinfest[@bolinfest](https://github.com/bolinfest)
- #20037[#20037](https://github.com/openai/codex/pull/20037)core tests: migrate rmcp turns to profiles@bolinfest[@bolinfest](https://github.com/bolinfest)
- #20040[#20040](https://github.com/openai/codex/pull/20040)core tests: migrate apply patch turns to profiles@bolinfest[@bolinfest](https://github.com/bolinfest)
- #20041[#20041](https://github.com/openai/codex/pull/20041)core tests: migrate hook turns to profiles@bolinfest[@bolinfest](https://github.com/bolinfest)
- #20072[#20072](https://github.com/openai/codex/pull/20072)Support disabling tool suggest for specific tools.@mzeng-openai[@mzeng-openai](https://github.com/mzeng-openai)
- #19949[#19949](https://github.com/openai/codex/pull/19949)Support detect and import MCP, Subagents, hooks, commands from external@alexsong-oai[@alexsong-oai](https://github.com/alexsong-oai)
- #19442[#19442](https://github.com/openai/codex/pull/19442)feat: disable capabilities by model provider@celia-oai[@celia-oai](https://github.com/celia-oai)
- #20108[#20108](https://github.com/openai/codex/pull/20108)fix: restore live event submit path for apply patch tests@bolinfest[@bolinfest](https://github.com/bolinfest)
- #19939[#19939](https://github.com/openai/codex/pull/19939)Restore TUI working status after steer message is set@canvrno-oai[@canvrno-oai](https://github.com/canvrno-oai)
- #20086[#20086](https://github.com/openai/codex/pull/20086)Fix plugin list workspace settings test isolation@canvrno-oai[@canvrno-oai](https://github.com/canvrno-oai)
- #20049[#20049](https://github.com/openai/codex/pull/20049)feat: expose provider capability bounds to app server clients@celia-oai[@celia-oai](https://github.com/celia-oai)
- #20109[#20109](https://github.com/openai/codex/pull/20109)feat: update Bedrock Mantle endpoint and GPT-5.4 model ID@celia-oai[@celia-oai](https://github.com/celia-oai)
- #20106[#20106](https://github.com/openai/codex/pull/20106)linux-sandbox: switch helper plumbing to PermissionProfile@bolinfest[@bolinfest](https://github.com/bolinfest)
- #20112[#20112](https://github.com/openai/codex/pull/20112)Soften skill description budget warnings@xl-openai[@xl-openai](https://github.com/xl-openai)
- #20058[#20058](https://github.com/openai/codex/pull/20058)Add environment provider snapshot@starr-openai[@starr-openai](https://github.com/starr-openai)
- #20133[#20133](https://github.com/openai/codex/pull/20133)chore(cli) deprecate --full-auto@dylan-hurd-oai[@dylan-hurd-oai](https://github.com/dylan-hurd-oai)
- #20117[#20117](https://github.com/openai/codex/pull/20117)feat(cli): add explicit sandbox permission profiles@viyatb-oai[@viyatb-oai](https://github.com/viyatb-oai)
- #20139[#20139](https://github.com/openai/codex/pull/20139)Delete multi_agent_v2 followup_task interrupt parameter@andmis[@andmis](https://github.com/andmis)
- #20118[#20118](https://github.com/openai/codex/pull/20118)feat(cli): add sandbox profile config controls@viyatb-oai[@viyatb-oai](https://github.com/viyatb-oai)
- #20144[#20144](https://github.com/openai/codex/pull/20144)Fix migrated hook path rewriting@alexsong-oai[@alexsong-oai](https://github.com/alexsong-oai)
- #20042[#20042](https://github.com/openai/codex/pull/20042)Fix Windows pseudoconsole attribute handling for sandboxed PTY sessions@iceweasel-oai[@iceweasel-oai](https://github.com/iceweasel-oai)
- #20186[#20186](https://github.com/openai/codex/pull/20186)nit: drop old memories things@jif-oai[@jif-oai](https://github.com/jif-oai)
- #20180[#20180](https://github.com/openai/codex/pull/20180)Make multi-agent v2 ignore agents.max_depth@jif-oai[@jif-oai](https://github.com/jif-oai)
- #20082[#20082](https://github.com/openai/codex/pull/20082)Use /goal resume for paused goals@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #20172[#20172](https://github.com/openai/codex/pull/20172)TUI: Remove core protocol dependency [1/7]@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #19211[#19211](https://github.com/openai/codex/pull/19211)Improve Windows process management edge cases@iceweasel-oai[@iceweasel-oai](https://github.com/iceweasel-oai)
- #20123[#20123](https://github.com/openai/codex/pull/20123)[rollout-tracer] Match analysis messages on encrypted id.@cassirer-openai[@cassirer-openai](https://github.com/cassirer-openai)
- #20173[#20173](https://github.com/openai/codex/pull/20173)TUI: Remove core protocol dependency [2/7]@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #20174[#20174](https://github.com/openai/codex/pull/20174)TUI: Remove core protocol dependency [3/7]@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #20228[#20228](https://github.com/openai/codex/pull/20228)[codex-backend] Prefer sqlite git info for rollout-path reads@joeytrasatti-openai[@joeytrasatti-openai](https://github.com/joeytrasatti-openai)
- #20141[#20141](https://github.com/openai/codex/pull/20141)Add ThreadManager sample crate@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #20046[#20046](https://github.com/openai/codex/pull/20046)test protocol: lock inter-agent commentary phase@friel-openai[@friel-openai](https://github.com/friel-openai)
- #20064[#20064](https://github.com/openai/codex/pull/20064)Include auto-review rollout in feedback uploads@won-openai[@won-openai](https://github.com/won-openai)
- #20096[#20096](https://github.com/openai/codex/pull/20096)feat: Use remote installed plugin cache for skills and MCP@xl-openai[@xl-openai](https://github.com/xl-openai)
- #19184[#19184](https://github.com/openai/codex/pull/19184)fix: handle deferred network proxy denials@viyatb-oai[@viyatb-oai](https://github.com/viyatb-oai)
- #20089[#20089](https://github.com/openai/codex/pull/20089)expand the set of core shell env vars for Windows.@iceweasel-oai[@iceweasel-oai](https://github.com/iceweasel-oai)
- #17088[#17088](https://github.com/openai/codex/pull/17088)[codex-analytics] ingest server requests and responses@rhan-oai[@rhan-oai](https://github.com/rhan-oai)
- #20091[#20091](https://github.com/openai/codex/pull/20091)[tool_suggest] Improve tool_suggest triggering conditions.@mzeng-openai[@mzeng-openai](https://github.com/mzeng-openai)
- #20258[#20258](https://github.com/openai/codex/pull/20258)app-server: fix outgoing sender test setup@sayan-oai[@sayan-oai](https://github.com/sayan-oai)
- #20050[#20050](https://github.com/openai/codex/pull/20050)[app-server] type client response payloads@rhan-oai[@rhan-oai](https://github.com/rhan-oai)
- #19966[#19966](https://github.com/openai/codex/pull/19966)Require remote plugin detail before uninstall@xli-oai[@xli-oai](https://github.com/xli-oai)
- #20059[#20059](https://github.com/openai/codex/pull/20059)[app-server] centralize client response analytics@rhan-oai[@rhan-oai](https://github.com/rhan-oai)
- #19334[#19334](https://github.com/openai/codex/pull/19334)Fallback login callback port when default is busy@xli-oai[@xli-oai](https://github.com/xli-oai)
- #20231[#20231](https://github.com/openai/codex/pull/20231)[apps] Add apps MCP path override@adaley-openai[@adaley-openai](https://github.com/adaley-openai)
- #20242[#20242](https://github.com/openai/codex/pull/20242)docs: discourage`#[async_trait]`and`#[allow(async_fn_in_trait)]`@bolinfest[@bolinfest](https://github.com/bolinfest)
- #19620[#19620](https://github.com/openai/codex/pull/19620)Escape turn metadata headers as ASCII JSON@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #19537[#19537](https://github.com/openai/codex/pull/19537)[mcp] Fix plugin MCP approval policy.@mzeng-openai[@mzeng-openai](https://github.com/mzeng-openai)
- #19229[#19229](https://github.com/openai/codex/pull/19229)Add agent graph store interface@rasmusrygaard[@rasmusrygaard](https://github.com/rasmusrygaard)
- #20243[#20243](https://github.com/openai/codex/pull/20243)Add codex-core public API listing@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #19435[#19435](https://github.com/openai/codex/pull/19435)stop blocking unified_exec on Windows@iceweasel-oai[@iceweasel-oai](https://github.com/iceweasel-oai)
- #19852[#19852](https://github.com/openai/codex/pull/19852)Enforce workspace metadata protections in Linux sandbox@evawong-oai[@evawong-oai](https://github.com/evawong-oai)
- #20136[#20136](https://github.com/openai/codex/pull/20136)Update Codex login success page UX@rafael-jac[@rafael-jac](https://github.com/rafael-jac)
- #20271[#20271](https://github.com/openai/codex/pull/20271)chore: increase release build timeout from 60 min to 90@bolinfest[@bolinfest](https://github.com/bolinfest)
- #19778[#19778](https://github.com/openai/codex/pull/19778)Add hooks/list app-server RPC@abhinav-oai[@abhinav-oai](https://github.com/abhinav-oai)
- #20261[#20261](https://github.com/openai/codex/pull/20261)Consume ai-title from external sessions and add end marker@alexsong-oai[@alexsong-oai](https://github.com/alexsong-oai)
- #20284[#20284](https://github.com/openai/codex/pull/20284)Import external agent sessions in background@stefanstokic-oai[@stefanstokic-oai](https://github.com/stefanstokic-oai)
- #20149[#20149](https://github.com/openai/codex/pull/20149)Reduce the surface of collaboration modes@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #20282[#20282](https://github.com/openai/codex/pull/20282)tui: return from side chat on Ctrl-D@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #20250[#20250](https://github.com/openai/codex/pull/20250)update codex_plugins_beta_setting (from workspace settings)@zamoshchin-openai[@zamoshchin-openai](https://github.com/zamoshchin-openai)
- #20080[#20080](https://github.com/openai/codex/pull/20080)[codex-analytics] prevent stale guardian events from satisfying reused reviews@rhan-oai[@rhan-oai](https://github.com/rhan-oai)
- #20291[#20291](https://github.com/openai/codex/pull/20291)app-server: remove dead api version handling from bespoke events@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #20304[#20304](https://github.com/openai/codex/pull/20304)[plugins] Allow MSFT curated plugins in tool_suggest@mzeng-openai[@mzeng-openai](https://github.com/mzeng-openai)
- #20095[#20095](https://github.com/openai/codex/pull/20095)permissions: expose active profile metadata@bolinfest[@bolinfest](https://github.com/bolinfest)
- #19840[#19840](https://github.com/openai/codex/pull/19840)Add persisted hook enablement state@abhinav-oai[@abhinav-oai](https://github.com/abhinav-oai)
- #20343[#20343](https://github.com/openai/codex/pull/20343)ci: increase Windows release workflow timeouts@bolinfest[@bolinfest](https://github.com/bolinfest)

Full release on Github[Full release on Github](https://github.com/openai/codex/releases/tag/rust-v0.128.0)
- 2026-04-24

### Codex app26.423

### New features

- Added a tooltip on realtime delegation messages to clarify that Codex uses the surrounding voice conversation as context.

### Performance improvements and bug fixes

- Fixed search in long review files so next and previous results reliably jump to off-screen matches.
- Kept embedded MCP app panels from restarting or losing state during fullscreen changes and thread reloads.
- Fixed several desktop regressions, including tray crashes when the local connection is missing, duplicate macOS fullscreen menu entries, and broken global dictation hotkeys on older macOS versions.
- Additional performance improvements and bug fixes.
- 2026-04-24

### Codex CLI0.125.0
````$npminstall-g@openai/codex@0.125.0````
View details

## New Features

- App-server integrations now support Unix socket transport, pagination-friendly resume/fork, sticky environments, and remote thread config/store plumbing. (#18255[#18255](https://github.com/openai/codex/pull/18255),#18892[#18892](https://github.com/openai/codex/pull/18892),#18897[#18897](https://github.com/openai/codex/pull/18897),#18908[#18908](https://github.com/openai/codex/pull/18908),#19008[#19008](https://github.com/openai/codex/pull/19008),#19014[#19014](https://github.com/openai/codex/pull/19014))
- App-server plugin management can install remote plugins and upgrade configured marketplaces. (#18917[#18917](https://github.com/openai/codex/pull/18917),#19074[#19074](https://github.com/openai/codex/pull/19074))
- Permission profiles now round-trip across TUI sessions, user turns, MCP sandbox state, shell escalation, and app-server APIs. (#18284[#18284](https://github.com/openai/codex/pull/18284),#18285[#18285](https://github.com/openai/codex/pull/18285),#18286[#18286](https://github.com/openai/codex/pull/18286),#18287[#18287](https://github.com/openai/codex/pull/18287),#19231[#19231](https://github.com/openai/codex/pull/19231))
- Model providers now own model discovery, with AWS/Bedrock account state exposed to app clients. (#18950[#18950](https://github.com/openai/codex/pull/18950),#19048[#19048](https://github.com/openai/codex/pull/19048))
- `codex exec --json`now reports reasoning-token usage for programmatic consumers. (#19308[#19308](https://github.com/openai/codex/pull/19308))
- Rollout tracing now records tool, code-mode, session, and multi-agent relationships, with a debug reducer command for inspection. (#18878[#18878](https://github.com/openai/codex/pull/18878),#18879[#18879](https://github.com/openai/codex/pull/18879),#18880[#18880](https://github.com/openai/codex/pull/18880))

## Bug Fixes

- Interrupting`/review`and exiting the TUI no longer leaves the interface wedged on delegate startup or unsubscribe. (#18921[#18921](https://github.com/openai/codex/pull/18921))
- Exec-server no longer drops buffered output after process exit and now waits correctly for stream closure. (#18946[#18946](https://github.com/openai/codex/pull/18946),#19130[#19130](https://github.com/openai/codex/pull/19130))
- App-server now respects explicitly untrusted project config instead of auto-persisting trust. (#18626[#18626](https://github.com/openai/codex/pull/18626))
- WebSocket app-server clients are less likely to disconnect during bursts of turn and tool-output notifications. (#19246[#19246](https://github.com/openai/codex/pull/19246))
- Windows sandbox startup handles multiple CLI versions and installed app directories better, and background`Start-Process`calls avoid visible PowerShell windows. (#19044[#19044](https://github.com/openai/codex/pull/19044),#19180[#19180](https://github.com/openai/codex/pull/19180),#19214[#19214](https://github.com/openai/codex/pull/19214))
- Config/schema handling now rejects conflicting MultiAgentV2 thread limits, resolves relative agent-role config paths, hides unsupported MCP bearer-token fields, and rejects invalid`js_repl`image MIME types. (#19129[#19129](https://github.com/openai/codex/pull/19129),#19261[#19261](https://github.com/openai/codex/pull/19261),#19294[#19294](https://github.com/openai/codex/pull/19294),#19292[#19292](https://github.com/openai/codex/pull/19292))

## Documentation

- App-server docs and generated schemas were refreshed for the new transport, thread, marketplace, sticky environment, and permission-profile APIs. (#18255[#18255](https://github.com/openai/codex/pull/18255),#18897[#18897](https://github.com/openai/codex/pull/18897),#19014[#19014](https://github.com/openai/codex/pull/19014),#19074[#19074](https://github.com/openai/codex/pull/19074),#19231[#19231](https://github.com/openai/codex/pull/19231))
- Rollout-trace documentation now covers the debug trace reduction workflow. (#18880[#18880](https://github.com/openai/codex/pull/18880))

## Chores

- Refreshed`models.json`and related core, app-server, SDK, and TUI fixtures for the latest model catalog and reasoning defaults. (#19323[#19323](https://github.com/openai/codex/pull/19323))
- Windows Bazel CI now uses a stable PATH and shared query startup path for better cache reuse. (#19161[#19161](https://github.com/openai/codex/pull/19161),#19232[#19232](https://github.com/openai/codex/pull/19232))
- Plugin marketplace add/remove/startup-sync internals moved out of`codex-core`, and curated plugin cache versions now use short SHAs. (#19099[#19099](https://github.com/openai/codex/pull/19099),#19095[#19095](https://github.com/openai/codex/pull/19095))
- Reverted a macOS signing entitlement change after it caused alpha startup failures. (#19167[#19167](https://github.com/openai/codex/pull/19167),#19350[#19350](https://github.com/openai/codex/pull/19350))
- Stabilized flaky approval-popup and plugin MCP tool-discovery tests. (#19178[#19178](https://github.com/openai/codex/pull/19178),#19191[#19191](https://github.com/openai/codex/pull/19191))

## Changelog

Full Changelog:rust-v0.124.0...rust-v0.125.0[rust-v0.124.0...rust-v0.125.0](https://github.com/openai/codex/compare/rust-v0.124.0...rust-v0.125.0)

- #19129[#19129](https://github.com/openai/codex/pull/19129)Reject agents.max_threads with multi_agent_v2@jif-oai[@jif-oai](https://github.com/jif-oai)
- #19130[#19130](https://github.com/openai/codex/pull/19130)exec-server: wait for close after observed exit@jif-oai[@jif-oai](https://github.com/jif-oai)
- #19149[#19149](https://github.com/openai/codex/pull/19149)Update safety check wording@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #18284[#18284](https://github.com/openai/codex/pull/18284)tui: sync session permission profiles@bolinfest[@bolinfest](https://github.com/bolinfest)
- #18710[#18710](https://github.com/openai/codex/pull/18710)[codex] Fix plugin marketplace help usage@xli-oai[@xli-oai](https://github.com/xli-oai)
- #19127[#19127](https://github.com/openai/codex/pull/19127)feat: drop spawned-agent context instructions@jif-oai[@jif-oai](https://github.com/jif-oai)
- #18892[#18892](https://github.com/openai/codex/pull/18892)Add remote thread config loader protos@rasmusrygaard[@rasmusrygaard](https://github.com/rasmusrygaard)
- #19014[#19014](https://github.com/openai/codex/pull/19014)Add excludeTurns parameter to thread/resume and thread/fork@ddr-oai[@ddr-oai](https://github.com/ddr-oai)
- #18882[#18882](https://github.com/openai/codex/pull/18882)[codex] Route live thread writes through ThreadStore@wiltzius-openai[@wiltzius-openai](https://github.com/wiltzius-openai)
- #19008[#19008](https://github.com/openai/codex/pull/19008)[codex] Implement remote thread store methods@wiltzius-openai[@wiltzius-openai](https://github.com/wiltzius-openai)
- #18626[#18626](https://github.com/openai/codex/pull/18626)Respect explicit untrusted project config@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #18255[#18255](https://github.com/openai/codex/pull/18255)app-server: add Unix socket transport@euroelessar[@euroelessar](https://github.com/euroelessar)
- #19167[#19167](https://github.com/openai/codex/pull/19167)ci: add macOS keychain entitlements@euroelessar[@euroelessar](https://github.com/euroelessar)
- #19099[#19099](https://github.com/openai/codex/pull/19099)Move marketplace add/remove and startup sync out of core.@xl-openai[@xl-openai](https://github.com/xl-openai)
- #19168[#19168](https://github.com/openai/codex/pull/19168)Use Auto-review wording for fallback rationale@maja-openai[@maja-openai](https://github.com/maja-openai)
- #18908[#18908](https://github.com/openai/codex/pull/18908)Add remote thread config endpoint@rasmusrygaard[@rasmusrygaard](https://github.com/rasmusrygaard)
- #18285[#18285](https://github.com/openai/codex/pull/18285)tui: carry permission profiles on user turns@bolinfest[@bolinfest](https://github.com/bolinfest)
- #18286[#18286](https://github.com/openai/codex/pull/18286)mcp: include permission profiles in sandbox state@bolinfest[@bolinfest](https://github.com/bolinfest)
- #18878[#18878](https://github.com/openai/codex/pull/18878)[rollout_trace] Trace tool and code-mode boundaries@cassirer-openai[@cassirer-openai](https://github.com/cassirer-openai)
- #18287[#18287](https://github.com/openai/codex/pull/18287)shell-escalation: carry resolved permission profiles@bolinfest[@bolinfest](https://github.com/bolinfest)
- #18946[#18946](https://github.com/openai/codex/pull/18946)fix(exec-server): retain output until streams close@bolinfest[@bolinfest](https://github.com/bolinfest)
- #19074[#19074](https://github.com/openai/codex/pull/19074)Add app-server marketplace upgrade RPC@xli-oai[@xli-oai](https://github.com/xli-oai)
- #19180[#19180](https://github.com/openai/codex/pull/19180)use a version-specific suffix for command runner binary in .sandbox-bin@iceweasel-oai[@iceweasel-oai](https://github.com/iceweasel-oai)
- #19178[#19178](https://github.com/openai/codex/pull/19178)Stabilize approvals popup disabled-row test@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #18921[#18921](https://github.com/openai/codex/pull/18921)Fix /review interrupt and TUI exit wedges@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #19191[#19191](https://github.com/openai/codex/pull/19191)Stabilize plugin MCP tools test@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #19194[#19194](https://github.com/openai/codex/pull/19194)Mark hooks schema fixtures as generated@abhinav-oai[@abhinav-oai](https://github.com/abhinav-oai)
- #18288[#18288](https://github.com/openai/codex/pull/18288)tests: isolate approval fixtures from host rules@bolinfest[@bolinfest](https://github.com/bolinfest)
- #19044[#19044](https://github.com/openai/codex/pull/19044)guide Windows to use -WindowStyle Hidden for Start-Process calls@iceweasel-oai[@iceweasel-oai](https://github.com/iceweasel-oai)
- #19214[#19214](https://github.com/openai/codex/pull/19214)do not attempt ACLs on installed codex dir@iceweasel-oai[@iceweasel-oai](https://github.com/iceweasel-oai)
- #19161[#19161](https://github.com/openai/codex/pull/19161)ci: derive cache-stable Windows Bazel PATH@bolinfest[@bolinfest](https://github.com/bolinfest)
- #18811[#18811](https://github.com/openai/codex/pull/18811)refactor: route Codex auth through AuthProvider@efrazer-oai[@efrazer-oai](https://github.com/efrazer-oai)
- #19246[#19246](https://github.com/openai/codex/pull/19246)Increase app-server WebSocket outbound buffer@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #19048[#19048](https://github.com/openai/codex/pull/19048)feat: expose AWS account state from account/read@celia-oai[@celia-oai](https://github.com/celia-oai)
- #18880[#18880](https://github.com/openai/codex/pull/18880)[rollout_trace] Add debug trace reduction command@cassirer-openai[@cassirer-openai](https://github.com/cassirer-openai)
- #18897[#18897](https://github.com/openai/codex/pull/18897)Add sticky environment API and thread state@starr-openai[@starr-openai](https://github.com/starr-openai)
- #18879[#18879](https://github.com/openai/codex/pull/18879)[rollout_trace] Trace sessions and multi-agent edges@cassirer-openai[@cassirer-openai](https://github.com/cassirer-openai)
- #19095[#19095](https://github.com/openai/codex/pull/19095)feat: Use short SHA versions for curated plugin cache entries@xl-openai[@xl-openai](https://github.com/xl-openai)
- #18950[#18950](https://github.com/openai/codex/pull/18950)feat: let model providers own model discovery@celia-oai[@celia-oai](https://github.com/celia-oai)
- #19206[#19206](https://github.com/openai/codex/pull/19206)app-server: persist device key bindings in sqlite@euroelessar[@euroelessar](https://github.com/euroelessar)
- #18917[#18917](https://github.com/openai/codex/pull/18917)[codex] Support remote plugin install writes@xli-oai[@xli-oai](https://github.com/xli-oai)
- #19231[#19231](https://github.com/openai/codex/pull/19231)permissions: make profiles represent enforcement@bolinfest[@bolinfest](https://github.com/bolinfest)
- #19261[#19261](https://github.com/openai/codex/pull/19261)Resolve relative agent role config paths from layers@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #19232[#19232](https://github.com/openai/codex/pull/19232)ci: reuse Bazel CI startup for target-discovery queries@bolinfest[@bolinfest](https://github.com/bolinfest)
- #19292[#19292](https://github.com/openai/codex/pull/19292)Reject unsupported js_repl image MIME types@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #19247[#19247](https://github.com/openai/codex/pull/19247)chore: apply truncation policy to unified_exec@sayan-oai[@sayan-oai](https://github.com/sayan-oai)
- #19294[#19294](https://github.com/openai/codex/pull/19294)Hide unsupported MCP bearer_token from config schema@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #19308[#19308](https://github.com/openai/codex/pull/19308)Surface reasoning tokens in exec JSON usage@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #19323[#19323](https://github.com/openai/codex/pull/19323)Update models.json and related fixtures@sayan-oai[@sayan-oai](https://github.com/sayan-oai)
- #19350[#19350](https://github.com/openai/codex/pull/19350)fix alpha build@jif-oai[@jif-oai](https://github.com/jif-oai)

Full release on Github[Full release on Github](https://github.com/openai/codex/releases/tag/rust-v0.125.0)
- 2026-04-23

### GPT-5.5 and Codex app updates

GPT-5.5 is now available in Codex[GPT-5.5 is now available in Codex](https://openai.com/index/introducing-gpt-5-5/)as OpenAI’s newest frontier model for complex coding, computer use, knowledge work, and research workflows.

#### GPT-5.5 in Codex

GPT-5.5 is the recommended choice for most Codex tasks when it appears in your model picker. It’s especially useful for implementation, refactors, debugging, testing, validation, and knowledge-work artifacts.

To switch to GPT-5.5:

- In the CLI, start a new thread with:
````codex--modelgpt-5.5````
Or use`/model`during a session.
- In the IDE extension, choose GPT-5.5 from the model selector in the composer.
- In the Codex app, choose GPT-5.5 from the model selector in the composer.

If you don’t see GPT-5.5 yet, update the CLI, IDE extension, or Codex app to the latest version. During the rollout, continue using GPT-5.4 if GPT-5.5 is not yet available.

#### Browser use in the Codex app

The Codex app can now let Codex operate the in-app browser for local development servers and file-backed pages. Ask Codex to use the browser when it needs to click through a rendered UI, reproduce a visual bug, or verify a local fix inside the app.

Browser use runs through the bundled Browser plugin. In settings, you can manage the plugin and review allowed or blocked websites.

#### Automatic approval reviews

Codex can route eligible approval prompts through an automatic reviewer agent before the request runs. When configured, the Codex app shows an automatic review item with the review status and risk level, so you can see whether the reviewer approved, denied, stopped, or timed out before deciding.
- 2026-04-23

### Codex CLI0.124.0
````$npminstall-g@openai/codex@0.124.0````
View details

## New Features

- The TUI now has quick reasoning controls:`Alt+,`lowers reasoning,`Alt+.`raises it, and accepted model upgrades now reset reasoning to the new model’s default instead of carrying over stale settings. (#18866[#18866](https://github.com/openai/codex/pull/18866),#19085[#19085](https://github.com/openai/codex/pull/19085))
- App-server sessions can now manage multiple environments and choose an environment and working directory per turn, which makes multi-workspace and remote setups easier to target precisely. (#18401[#18401](https://github.com/openai/codex/pull/18401),#18416[#18416](https://github.com/openai/codex/pull/18416))
- Added first-class Amazon Bedrock support for OpenAI-compatible providers, including AWS SigV4 signing and AWS credential-based auth. (#17820[#17820](https://github.com/openai/codex/pull/17820))
- Remote plugin marketplaces can now be listed and read directly, with more reliable detail lookups and larger result pages. (#18452[#18452](https://github.com/openai/codex/pull/18452),#19079[#19079](https://github.com/openai/codex/pull/19079))
- Hooks are now stable, can be configured inline in`config.toml`and managed`requirements.toml`, and can observe MCP tools as well as`apply_patch`and long-running Bash sessions. (#18893[#18893](https://github.com/openai/codex/pull/18893),#18385[#18385](https://github.com/openai/codex/pull/18385),#18391[#18391](https://github.com/openai/codex/pull/18391),#18888[#18888](https://github.com/openai/codex/pull/18888),#19012[#19012](https://github.com/openai/codex/pull/19012))
- Eligible ChatGPT plans now default to the Fast service tier unless you explicitly opt out. (#19053[#19053](https://github.com/openai/codex/pull/19053))

## Bug Fixes

- Preserved Cloudflare cookies across approved ChatGPT hosts, reducing auth breakage in HTTP-backed ChatGPT flows. (#17783[#17783](https://github.com/openai/codex/pull/17783))
- Fixed remote app-server reliability issues so websocket events keep draining under load and shutdown no longer fails when the remote worker exits during cleanup. (#18932[#18932](https://github.com/openai/codex/pull/18932),#18936[#18936](https://github.com/openai/codex/pull/18936))
- Fixed permission-mode drift so`/permissions`changes survive side conversations and updated Full Access state is correctly reflected in MCP approval handling. (#18924[#18924](https://github.com/openai/codex/pull/18924),#19033[#19033](https://github.com/openai/codex/pull/19033))
- Fixed`wait_agent`so it returns promptly when mailbox work is already queued instead of waiting for a fresh notification or timing out. (#18968[#18968](https://github.com/openai/codex/pull/18968))
- Fixed local stdio MCP launches for relative commands without an explicit`cwd`, bringing fallback path resolution in line with CLI behavior. (#19031[#19031](https://github.com/openai/codex/pull/19031))
- Startup now fails less often on managed config edge cases: unknown feature requirements warn instead of aborting, and cloud-requirements errors are clearer about what failed. (#19038[#19038](https://github.com/openai/codex/pull/19038),#19078[#19078](https://github.com/openai/codex/pull/19078))

## Changelog

Full Changelog:rust-v0.123.0...rust-v0.124.0[rust-v0.123.0...rust-v0.124.0](https://github.com/openai/codex/compare/rust-v0.123.0...rust-v0.124.0)

- #18870[#18870](https://github.com/openai/codex/pull/18870)Load app-server config through ConfigManager@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #18866[#18866](https://github.com/openai/codex/pull/18866)feat(tui): shortcuts to change reasoning level temporarily@fcoury-oai[@fcoury-oai](https://github.com/fcoury-oai)
- #18430[#18430](https://github.com/openai/codex/pull/18430)app-server: implement device key v2 methods@euroelessar[@euroelessar](https://github.com/euroelessar)
- #18757[#18757](https://github.com/openai/codex/pull/18757)fix: fully revert agent identity runtime wiring@efrazer-oai[@efrazer-oai](https://github.com/efrazer-oai)
- #17783[#17783](https://github.com/openai/codex/pull/17783)Preserve Cloudfare HTTP cookies in codex@shijie-oai[@shijie-oai](https://github.com/shijie-oai)
- #18876[#18876](https://github.com/openai/codex/pull/18876)[rollout_trace] Add rollout trace crate@cassirer-openai[@cassirer-openai](https://github.com/cassirer-openai)
- #18401[#18401](https://github.com/openai/codex/pull/18401)Support multiple managed environments@starr-openai[@starr-openai](https://github.com/starr-openai)
- #18797[#18797](https://github.com/openai/codex/pull/18797)Allow guardian bare allow output@maja-openai[@maja-openai](https://github.com/maja-openai)
- #18886[#18886](https://github.com/openai/codex/pull/18886)Normalize /statusline & /title items@canvrno-oai[@canvrno-oai](https://github.com/canvrno-oai)
- #18768[#18768](https://github.com/openai/codex/pull/18768)[codex] Tighten external migration prompt tests@alexsong-oai[@alexsong-oai](https://github.com/alexsong-oai)
- #18909[#18909](https://github.com/openai/codex/pull/18909)Update /statusline and /title snapshots@canvrno-oai[@canvrno-oai](https://github.com/canvrno-oai)
- #18867[#18867](https://github.com/openai/codex/pull/18867)sandboxing: materialize cwd-relative permission globs@bolinfest[@bolinfest](https://github.com/bolinfest)
- #18915[#18915](https://github.com/openai/codex/pull/18915)fix: windows snapshot for external_agent_config_migration::tests::prompt_snapshot did not match windows output@bolinfest[@bolinfest](https://github.com/bolinfest)
- #18416[#18416](https://github.com/openai/codex/pull/18416)Add turn-scoped environment selections@starr-openai[@starr-openai](https://github.com/starr-openai)
- #18391[#18391](https://github.com/openai/codex/pull/18391)fix(core): emit hooks for apply_patch edits@fcoury-oai[@fcoury-oai](https://github.com/fcoury-oai)
- #18916[#18916](https://github.com/openai/codex/pull/18916)test(core): move prompt debug coverage to integration suite@bolinfest[@bolinfest](https://github.com/bolinfest)
- #17820[#17820](https://github.com/openai/codex/pull/17820)feat: add AWS SigV4 auth for OpenAI-compatible model providers@celia-oai[@celia-oai](https://github.com/celia-oai)
- #18913[#18913](https://github.com/openai/codex/pull/18913)bazel: run wrapped Rust unit test shards@bolinfest[@bolinfest](https://github.com/bolinfest)
- #18452[#18452](https://github.com/openai/codex/pull/18452)feat: Support remote plugin list/read.@xl-openai[@xl-openai](https://github.com/xl-openai)
- #18936[#18936](https://github.com/openai/codex/pull/18936)Fix remote app-server shutdown race@bolinfest[@bolinfest](https://github.com/bolinfest)
- #18871[#18871](https://github.com/openai/codex/pull/18871)refactor: add agent identity crate@efrazer-oai[@efrazer-oai](https://github.com/efrazer-oai)
- #18276[#18276](https://github.com/openai/codex/pull/18276)exec-server: carry filesystem sandbox profiles@bolinfest[@bolinfest](https://github.com/bolinfest)
- #18926[#18926](https://github.com/openai/codex/pull/18926)ci: keep argument comment lint checks materialized@bolinfest[@bolinfest](https://github.com/bolinfest)
- #18935[#18935](https://github.com/openai/codex/pull/18935)Keep TUI status surfaces in sync@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #18923[#18923](https://github.com/openai/codex/pull/18923)chore(tui) debug-config guardian_policy_config@dylan-hurd-oai[@dylan-hurd-oai](https://github.com/dylan-hurd-oai)
- #18943[#18943](https://github.com/openai/codex/pull/18943)tests: serialize process-heavy Windows CI suites@bolinfest[@bolinfest](https://github.com/bolinfest)
- #18934[#18934](https://github.com/openai/codex/pull/18934)[codex] Clean guardian instructions@dylan-hurd-oai[@dylan-hurd-oai](https://github.com/dylan-hurd-oai)
- #18948[#18948](https://github.com/openai/codex/pull/18948)chore: remove unused Bedrock auth lazy loading@celia-oai[@celia-oai](https://github.com/celia-oai)
- #18277[#18277](https://github.com/openai/codex/pull/18277)core: derive active permission profiles@bolinfest[@bolinfest](https://github.com/bolinfest)
- #18785[#18785](https://github.com/openai/codex/pull/18785)feat: add explicit AgentIdentity auth mode@efrazer-oai[@efrazer-oai](https://github.com/efrazer-oai)
- #18953[#18953](https://github.com/openai/codex/pull/18953)use long-lived sessions for codex sandbox windows@iceweasel-oai[@iceweasel-oai](https://github.com/iceweasel-oai)
- #18278[#18278](https://github.com/openai/codex/pull/18278)app-server: expose thread permission profiles@bolinfest[@bolinfest](https://github.com/bolinfest)
- #17693[#17693](https://github.com/openai/codex/pull/17693)[codex-analytics] guardian review analytics events emission@rhan-oai[@rhan-oai](https://github.com/rhan-oai)
- #17695[#17695](https://github.com/openai/codex/pull/17695)[codex-analytics] guardian review truncation@rhan-oai[@rhan-oai](https://github.com/rhan-oai)
- #17696[#17696](https://github.com/openai/codex/pull/17696)[codex-analytics] guardian review TTFT plumbing and emission@rhan-oai[@rhan-oai](https://github.com/rhan-oai)
- #18962[#18962](https://github.com/openai/codex/pull/18962)nit: expose lib@jif-oai[@jif-oai](https://github.com/jif-oai)
- #18502[#18502](https://github.com/openai/codex/pull/18502)Support multiple cwd filters for thread list@acrognale-oai[@acrognale-oai](https://github.com/acrognale-oai)
- #18968[#18968](https://github.com/openai/codex/pull/18968)fix: wait_agent timeout for queued mailbox mail@jif-oai[@jif-oai](https://github.com/jif-oai)
- #18971[#18971](https://github.com/openai/codex/pull/18971)fix: cargo deny@jif-oai[@jif-oai](https://github.com/jif-oai)
- #18973[#18973](https://github.com/openai/codex/pull/18973)chore: prep memories for AB@jif-oai[@jif-oai](https://github.com/jif-oai)
- #18852[#18852](https://github.com/openai/codex/pull/18852)[codex] Update imagegen system skill@vb-openai[@vb-openai](https://github.com/vb-openai)
- #18865[#18865](https://github.com/openai/codex/pull/18865)Stage publishable Python runtime wheels@sdcoffey[@sdcoffey](https://github.com/sdcoffey)
- #18932[#18932](https://github.com/openai/codex/pull/18932)TUI: Keep remote app-server events draining@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #18877[#18877](https://github.com/openai/codex/pull/18877)[rollout_trace] Record core session rollout traces@cassirer-openai[@cassirer-openai](https://github.com/cassirer-openai)
- #18959[#18959](https://github.com/openai/codex/pull/18959)feat(auto-review) policy config@dylan-hurd-oai[@dylan-hurd-oai](https://github.com/dylan-hurd-oai)
- #18955[#18955](https://github.com/openai/codex/pull/18955)Add plumbing to approve stored Auto-Review denials@won-openai[@won-openai](https://github.com/won-openai)
- #18999[#18999](https://github.com/openai/codex/pull/18999)arg0: keep dispatch aliases alive during async main@bolinfest[@bolinfest](https://github.com/bolinfest)
- #18925[#18925](https://github.com/openai/codex/pull/18925)feat: Fairly trim skill descriptions within context budget@xl-openai[@xl-openai](https://github.com/xl-openai)
- #18890[#18890](https://github.com/openai/codex/pull/18890)feat(auto-review) short-circuit@dylan-hurd-oai[@dylan-hurd-oai](https://github.com/dylan-hurd-oai)
- #18279[#18279](https://github.com/openai/codex/pull/18279)app-server: accept permission profile overrides@bolinfest[@bolinfest](https://github.com/bolinfest)
- #18582[#18582](https://github.com/openai/codex/pull/18582)[2/4] Implement executor HTTP request runner@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #18197[#18197](https://github.com/openai/codex/pull/18197)feat: add guardian network approval trigger context@viyatb-oai[@viyatb-oai](https://github.com/viyatb-oai)
- #19033[#19033](https://github.com/openai/codex/pull/19033)Fix MCP permission policy sync@leoshimo-oai[@leoshimo-oai](https://github.com/leoshimo-oai)
- #19016[#19016](https://github.com/openai/codex/pull/19016)exec-server: expose arg0 alias root to fs sandbox@bolinfest[@bolinfest](https://github.com/bolinfest)
- #19036[#19036](https://github.com/openai/codex/pull/19036)Overlay state DB git metadata for filtered thread lists@joeytrasatti-openai[@joeytrasatti-openai](https://github.com/joeytrasatti-openai)
- #18956[#18956](https://github.com/openai/codex/pull/18956)[Codex] Register browser requirements feature keys@khoi-oai[@khoi-oai](https://github.com/khoi-oai)
- #19043[#19043](https://github.com/openai/codex/pull/19043)Update bundled OpenAI Docs skill freshness check@kkahadze-oai[@kkahadze-oai](https://github.com/kkahadze-oai)
- #18504[#18504](https://github.com/openai/codex/pull/18504)Rebrand approvals reviewer config to auto-review@won-openai[@won-openai](https://github.com/won-openai)
- #19046[#19046](https://github.com/openai/codex/pull/19046)exec-server: require explicit filesystem sandbox cwd@bolinfest[@bolinfest](https://github.com/bolinfest)
- #18280[#18280](https://github.com/openai/codex/pull/18280)clients: send permission profiles to app-server@bolinfest[@bolinfest](https://github.com/bolinfest)
- #18281[#18281](https://github.com/openai/codex/pull/18281)rollout: persist turn permission profiles@bolinfest[@bolinfest](https://github.com/bolinfest)
- #18888[#18888](https://github.com/openai/codex/pull/18888)hooks: emit Bash PostToolUse when exec_command completes via write_stdin@eternal-openai[@eternal-openai](https://github.com/eternal-openai)
- #19056[#19056](https://github.com/openai/codex/pull/19056)Rename approvals reviewer variant to auto-review@won-openai[@won-openai](https://github.com/won-openai)
- #18583[#18583](https://github.com/openai/codex/pull/18583)[3/4] Add executor-backed RMCP HTTP client@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #19059[#19059](https://github.com/openai/codex/pull/19059)core: box multi-agent wrapper futures@bolinfest[@bolinfest](https://github.com/bolinfest)
- #19031[#19031](https://github.com/openai/codex/pull/19031)Fix relative stdio MCP cwd fallback@mzeng-openai[@mzeng-openai](https://github.com/mzeng-openai)
- #19063[#19063](https://github.com/openai/codex/pull/19063)chore(auto-review) feature => stable@dylan-hurd-oai[@dylan-hurd-oai](https://github.com/dylan-hurd-oai)
- #19050[#19050](https://github.com/openai/codex/pull/19050)feat(request-permissions) approve with strict review@dylan-hurd-oai[@dylan-hurd-oai](https://github.com/dylan-hurd-oai)
- #19067[#19067](https://github.com/openai/codex/pull/19067)test: set Rust test thread stack size@bolinfest[@bolinfest](https://github.com/bolinfest)
- #19072[#19072](https://github.com/openai/codex/pull/19072)tui: fix approvals popup disabled shortcut test@bolinfest[@bolinfest](https://github.com/bolinfest)
- #18893[#18893](https://github.com/openai/codex/pull/18893)codex: support hooks in config.toml and requirements.toml@eternal-openai[@eternal-openai](https://github.com/eternal-openai)
- #18282[#18282](https://github.com/openai/codex/pull/18282)protocol: report session permission profiles@bolinfest[@bolinfest](https://github.com/bolinfest)
- #19053[#19053](https://github.com/openai/codex/pull/19053)Default Fast service tier for eligible ChatGPT plans@shijie-oai[@shijie-oai](https://github.com/shijie-oai)
- #19055[#19055](https://github.com/openai/codex/pull/19055)Add safety check notification and error handling@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #18283[#18283](https://github.com/openai/codex/pull/18283)app-server: accept command permission profiles@bolinfest[@bolinfest](https://github.com/bolinfest)
- #19012[#19012](https://github.com/openai/codex/pull/19012)Mark codex_hooks stable@abhinav-oai[@abhinav-oai](https://github.com/abhinav-oai)
- #18924[#18924](https://github.com/openai/codex/pull/18924)TUI: preserve permission state after side conversations@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #19071[#19071](https://github.com/openai/codex/pull/19071)Add computer_use feature requirement key@leoshimo-oai[@leoshimo-oai](https://github.com/leoshimo-oai)
- #19079[#19079](https://github.com/openai/codex/pull/19079)Use remote plugin IDs for detail reads and enlarge list pages@xl-openai[@xl-openai](https://github.com/xl-openai)
- #19038[#19038](https://github.com/openai/codex/pull/19038)feat: Warn and continue on unknown feature requirements@xl-openai[@xl-openai](https://github.com/xl-openai)
- #19078[#19078](https://github.com/openai/codex/pull/19078)Clarify cloud requirements error messages@gverma-openai[@gverma-openai](https://github.com/gverma-openai)
- #19085[#19085](https://github.com/openai/codex/pull/19085)Persist target default reasoning on model upgrade@shijie-oai[@shijie-oai](https://github.com/shijie-oai)
- #19086[#19086](https://github.com/openai/codex/pull/19086)app-server: include filesystem entries in permission requests@bolinfest[@bolinfest](https://github.com/bolinfest)
- #18385[#18385](https://github.com/openai/codex/pull/18385)Support MCP tools in hooks@abhinav-oai[@abhinav-oai](https://github.com/abhinav-oai)
- #19113[#19113](https://github.com/openai/codex/pull/19113)Fix auto-review config compatibility across protocol and SDK@won-openai[@won-openai](https://github.com/won-openai)

Full release on Github[Full release on Github](https://github.com/openai/codex/releases/tag/rust-v0.124.0)
- 2026-04-23

### Codex CLI0.123.0
````$npminstall-g@openai/codex@0.123.0````
View details

## New Features

- Added a built-in`amazon-bedrock`model provider with configurable AWS profile support (#18744[#18744](https://github.com/openai/codex/pull/18744)).
- Added`/mcp verbose`for full MCP server diagnostics, resources, and resource templates while keeping plain`/mcp`fast (#18610[#18610](https://github.com/openai/codex/pull/18610)).
- Made plugin MCP loading accept both`mcpServers`and top-level server maps in`.mcp.json`(#18780[#18780](https://github.com/openai/codex/pull/18780)).
- Improved realtime handoffs so background agents receive transcript deltas and can explicitly stay silent when appropriate (#18597[#18597](https://github.com/openai/codex/pull/18597),#18761[#18761](https://github.com/openai/codex/pull/18761),#18635[#18635](https://github.com/openai/codex/pull/18635)).
- Added host-specific`remote_sandbox_config`requirements for remote environments (#18763[#18763](https://github.com/openai/codex/pull/18763)).
- Refreshed bundled model metadata, including the current`gpt-5.4`default (#18586[#18586](https://github.com/openai/codex/pull/18586),#18388[#18388](https://github.com/openai/codex/pull/18388),#18719[#18719](https://github.com/openai/codex/pull/18719)).

## Bug Fixes

- Fixed`/copy`after rollback so it copies the latest visible assistant response, not a pre-rollback response (#18739[#18739](https://github.com/openai/codex/pull/18739)).
- Queued normal follow-up text submitted while a manual shell command is running, preventing stuck`Working`states (#18820[#18820](https://github.com/openai/codex/pull/18820)).
- Fixed Unicode/dead-key input in VS Code WSL terminals by disabling the enhanced keyboard mode there (#18741[#18741](https://github.com/openai/codex/pull/18741)).
- Prevented stale proxy environment variables from being restored from shell snapshots (#17271[#17271](https://github.com/openai/codex/pull/17271)).
- Made`codex exec`inherit root-level shared flags such as sandbox and model options (#18630[#18630](https://github.com/openai/codex/pull/18630)).
- Removed leaked review prompts from TUI transcripts (#18659[#18659](https://github.com/openai/codex/pull/18659)).

## Documentation

- Added and tightened the Code Review skill instructions used by Codex-driven reviews (#18746[#18746](https://github.com/openai/codex/pull/18746),#18818[#18818](https://github.com/openai/codex/pull/18818)).
- Documented intentional await-across-lock cases and enabled Clippy linting for them (#18423[#18423](https://github.com/openai/codex/pull/18423),#18698[#18698](https://github.com/openai/codex/pull/18698)).
- Updated app-server protocol docs for threadless MCP resource reads and namespaced dynamic tools (#18292[#18292](https://github.com/openai/codex/pull/18292),#18413[#18413](https://github.com/openai/codex/pull/18413)).

## Chores

- Fixed high-severity dependency alerts by pinning patched JS and Rust dependencies (#18167[#18167](https://github.com/openai/codex/pull/18167)).
- Reduced Rust dev build debug-info overhead while preserving useful backtraces (#18844[#18844](https://github.com/openai/codex/pull/18844)).
- Refreshed generated Python app-server SDK types from the current schema (#18862[#18862](https://github.com/openai/codex/pull/18862)).

## Changelog

Full Changelog:rust-v0.122.0...rust-v0.123.0[rust-v0.122.0...rust-v0.123.0](https://github.com/openai/codex/compare/rust-v0.122.0...rust-v0.123.0)

- #18662[#18662](https://github.com/openai/codex/pull/18662)feat: add metric to track the number of turns with memory usage@jif-oai[@jif-oai](https://github.com/jif-oai)
- #18659[#18659](https://github.com/openai/codex/pull/18659)chore: drop review prompt from TUI UX@jif-oai[@jif-oai](https://github.com/jif-oai)
- #18661[#18661](https://github.com/openai/codex/pull/18661)feat: log client use min log level@jif-oai[@jif-oai](https://github.com/jif-oai)
- #18094[#18094](https://github.com/openai/codex/pull/18094)[codex] Use background agent task auth for backend calls@adrian-openai[@adrian-openai](https://github.com/adrian-openai)
- #18441[#18441](https://github.com/openai/codex/pull/18441)Avoid false shell snapshot cleanup warnings@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #18260[#18260](https://github.com/openai/codex/pull/18260)[codex] Use background task auth for additional backend calls@adrian-openai[@adrian-openai](https://github.com/adrian-openai)
- #18657[#18657](https://github.com/openai/codex/pull/18657)fix: auth.json leak in tests@jif-oai[@jif-oai](https://github.com/jif-oai)
- #18610[#18610](https://github.com/openai/codex/pull/18610)Add verbose diagnostics for /mcp@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #18633[#18633](https://github.com/openai/codex/pull/18633)Use app server thread names in TUI picker@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #18591[#18591](https://github.com/openai/codex/pull/18591)Surface parent thread status in side conversations@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #18361[#18361](https://github.com/openai/codex/pull/18361)codex: move thread/name/set and thread/memoryModeSet into ThreadStore@wiltzius-openai[@wiltzius-openai](https://github.com/wiltzius-openai)
- #18274[#18274](https://github.com/openai/codex/pull/18274)protocol: canonicalize file system permissions@bolinfest[@bolinfest](https://github.com/bolinfest)
- #18403[#18403](https://github.com/openai/codex/pull/18403)refactor: use semaphores for async serialization gates@bolinfest[@bolinfest](https://github.com/bolinfest)
- #18586[#18586](https://github.com/openai/codex/pull/18586)Update models.json@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #18289[#18289](https://github.com/openai/codex/pull/18289)Wire the PatchUpdated events through app_server@akshaynathan[@akshaynathan](https://github.com/akshaynathan)
- #18631[#18631](https://github.com/openai/codex/pull/18631)Remove simple TUI legacy_core reexports@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #18697[#18697](https://github.com/openai/codex/pull/18697)[codex] Fix agent identity auth test fixture@adrian-openai[@adrian-openai](https://github.com/adrian-openai)
- #18388[#18388](https://github.com/openai/codex/pull/18388)Update models.json @github-actions
- #18167[#18167](https://github.com/openai/codex/pull/18167)[codex] Fix high severity dependency alerts@caseysilver-oai[@caseysilver-oai](https://github.com/caseysilver-oai)
- #17692[#17692](https://github.com/openai/codex/pull/17692)[codex-analytics] guardian review analytics schema polishing@rhan-oai[@rhan-oai](https://github.com/rhan-oai)
- #18722[#18722](https://github.com/openai/codex/pull/18722)chore(guardian) disable mcps and plugins@dylan-hurd-oai[@dylan-hurd-oai](https://github.com/dylan-hurd-oai)
- #18597[#18597](https://github.com/openai/codex/pull/18597)Update realtime handoff transcript handling@guinness-oai[@guinness-oai](https://github.com/guinness-oai)
- #18627[#18627](https://github.com/openai/codex/pull/18627)Surface TUI skills refresh failures@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #18719[#18719](https://github.com/openai/codex/pull/18719)Fix stale model test fixtures@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #18714[#18714](https://github.com/openai/codex/pull/18714)Add experimental remote thread store config@wiltzius-openai[@wiltzius-openai](https://github.com/wiltzius-openai)
- #18739[#18739](https://github.com/openai/codex/pull/18739)fix(tui): keep /copy aligned with rollback@fcoury-oai[@fcoury-oai](https://github.com/fcoury-oai)
- #18701[#18701](https://github.com/openai/codex/pull/18701)[codex] prefer inherited spawn agent model@tibo-openai[@tibo-openai](https://github.com/tibo-openai)
- #18632[#18632](https://github.com/openai/codex/pull/18632)Use app server metadata for fork parent titles@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #18112[#18112](https://github.com/openai/codex/pull/18112)feat: cascade thread archive@jif-oai[@jif-oai](https://github.com/jif-oai)
- #18716[#18716](https://github.com/openai/codex/pull/18716)Read conversation summaries through thread store@wiltzius-openai[@wiltzius-openai](https://github.com/wiltzius-openai)
- #18635[#18635](https://github.com/openai/codex/pull/18635)Add realtime silence tool@guinness-oai[@guinness-oai](https://github.com/guinness-oai)
- #18254[#18254](https://github.com/openai/codex/pull/18254)uds: add async Unix socket crate@euroelessar[@euroelessar](https://github.com/euroelessar)
- #18746[#18746](https://github.com/openai/codex/pull/18746)Add Code Review skill@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #18208[#18208](https://github.com/openai/codex/pull/18208)Add session config loader interface@rasmusrygaard[@rasmusrygaard](https://github.com/rasmusrygaard)
- #18753[#18753](https://github.com/openai/codex/pull/18753)Refactor TUI app module into submodules@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #18630[#18630](https://github.com/openai/codex/pull/18630)Fix exec inheritance of root shared flags@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #18027[#18027](https://github.com/openai/codex/pull/18027)[6/6] Fail exec client operations after disconnect@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #17271[#17271](https://github.com/openai/codex/pull/17271)fix: fix stale proxy env restoration after shell snapshots@viyatb-oai[@viyatb-oai](https://github.com/viyatb-oai)
- #18602[#18602](https://github.com/openai/codex/pull/18602)Warn when trusting Git subdirectories@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #18761[#18761](https://github.com/openai/codex/pull/18761)[codex] Send realtime transcript deltas on handoff@guinness-oai[@guinness-oai](https://github.com/guinness-oai)
- #18435[#18435](https://github.com/openai/codex/pull/18435)/statusline & /title - Shared preview values@canvrno-oai[@canvrno-oai](https://github.com/canvrno-oai)
- #18744[#18744](https://github.com/openai/codex/pull/18744)feat: add a built-in Amazon Bedrock model provider@celia-oai[@celia-oai](https://github.com/celia-oai)
- #18581[#18581](https://github.com/openai/codex/pull/18581)[1/4] Add executor HTTP request protocol@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #18418[#18418](https://github.com/openai/codex/pull/18418)refactor: narrow async lock scopes@bolinfest[@bolinfest](https://github.com/bolinfest)
- #18780[#18780](https://github.com/openai/codex/pull/18780)feat: Support more plugin MCP file shapes.@xl-openai[@xl-openai](https://github.com/xl-openai)
- #18713[#18713](https://github.com/openai/codex/pull/18713)protocol: preserve glob scan depth in permission profiles@bolinfest[@bolinfest](https://github.com/bolinfest)
- #18795[#18795](https://github.com/openai/codex/pull/18795)fix(guardian) Dont hard error on feature disable@dylan-hurd-oai[@dylan-hurd-oai](https://github.com/dylan-hurd-oai)
- #18292[#18292](https://github.com/openai/codex/pull/18292)Make MCP resource read threadless@mzeng-openai[@mzeng-openai](https://github.com/mzeng-openai)
- #18786[#18786](https://github.com/openai/codex/pull/18786)Fallback display names for TUI skill mentions@canvrno-oai[@canvrno-oai](https://github.com/canvrno-oai)
- #18807[#18807](https://github.com/openai/codex/pull/18807)chore(app-server) linguist-generated@dylan-hurd-oai[@dylan-hurd-oai](https://github.com/dylan-hurd-oai)
- #18393[#18393](https://github.com/openai/codex/pull/18393)feat(auto-review) Handle request_permissions calls@dylan-hurd-oai[@dylan-hurd-oai](https://github.com/dylan-hurd-oai)
- #18763[#18763](https://github.com/openai/codex/pull/18763)Add remote_sandbox_config to our config requirements@abhinav-oai[@abhinav-oai](https://github.com/abhinav-oai)
- #18794[#18794](https://github.com/openai/codex/pull/18794)Organize context fragments@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #18423[#18423](https://github.com/openai/codex/pull/18423)chore: document intentional await-holding cases@bolinfest[@bolinfest](https://github.com/bolinfest)
- #18698[#18698](https://github.com/openai/codex/pull/18698)chore: enable await-holding clippy lints@bolinfest[@bolinfest](https://github.com/bolinfest)
- #18413[#18413](https://github.com/openai/codex/pull/18413)[tool search] support namespaced deferred dynamic tools@pash-openai[@pash-openai](https://github.com/pash-openai)
- #18818[#18818](https://github.com/openai/codex/pull/18818)[codex] Tighten code review skill wording@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #18271[#18271](https://github.com/openai/codex/pull/18271)show bash mode in the TUI@abhinav-oai[@abhinav-oai](https://github.com/abhinav-oai)
- #18741[#18741](https://github.com/openai/codex/pull/18741)fix(tui): disable enhanced keys for VS Code WSL@fcoury-oai[@fcoury-oai](https://github.com/fcoury-oai)
- #18850[#18850](https://github.com/openai/codex/pull/18850)Move external agent config out of core@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #18844[#18844](https://github.com/openai/codex/pull/18844)build: reduce Rust dev debuginfo@bolinfest[@bolinfest](https://github.com/bolinfest)
- #18848[#18848](https://github.com/openai/codex/pull/18848)feat: baseline lib@jif-oai[@jif-oai](https://github.com/jif-oai)
- #18846[#18846](https://github.com/openai/codex/pull/18846)core: make test-log a dev dependency@bolinfest[@bolinfest](https://github.com/bolinfest)
- #18428[#18428](https://github.com/openai/codex/pull/18428)app-server: define device key v2 protocol@euroelessar[@euroelessar](https://github.com/euroelessar)
- #18093[#18093](https://github.com/openai/codex/pull/18093)Propagate thread id in MCP tool metadata@rennie-openai[@rennie-openai](https://github.com/rennie-openai)
- #17836[#17836](https://github.com/openai/codex/pull/17836)[codex] Add tmux-aware OSC 9 notifications@caseychow-oai[@caseychow-oai](https://github.com/caseychow-oai)
- #18820[#18820](https://github.com/openai/codex/pull/18820)Queue follow-up input during user shell commands@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #18858[#18858](https://github.com/openai/codex/pull/18858)Stabilize debug clear memories integration test@jif-oai[@jif-oai](https://github.com/jif-oai)
- #18799[#18799](https://github.com/openai/codex/pull/18799)Move TUI app tests to modules they cover@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #18442[#18442](https://github.com/openai/codex/pull/18442)Refactor app-server config loading into ConfigManager@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #18813[#18813](https://github.com/openai/codex/pull/18813)Split DeveloperInstructions into individual fragments.@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #18275[#18275](https://github.com/openai/codex/pull/18275)sandboxing: intersect permission profiles semantically@bolinfest[@bolinfest](https://github.com/bolinfest)
- #18862[#18862](https://github.com/openai/codex/pull/18862)Refresh generated Python app-server SDK types@sdcoffey[@sdcoffey](https://github.com/sdcoffey)
- #15578[#15578](https://github.com/openai/codex/pull/15578)Add Windows sandbox unified exec runtime support@iceweasel-oai[@iceweasel-oai](https://github.com/iceweasel-oai)
- #18429[#18429](https://github.com/openai/codex/pull/18429)app-server: add codex-device-key crate@euroelessar[@euroelessar](https://github.com/euroelessar)
- #18872[#18872](https://github.com/openai/codex/pull/18872)app-server: fix Bazel clippy in tracing tests@euroelessar[@euroelessar](https://github.com/euroelessar)
- #18885[#18885](https://github.com/openai/codex/pull/18885)skip busted tests while I fix them@iceweasel-oai[@iceweasel-oai](https://github.com/iceweasel-oai)
- #18873[#18873](https://github.com/openai/codex/pull/18873)chore: default multi-agent v2 fork to all@jif-oai[@jif-oai](https://github.com/jif-oai)

Full release on Github[Full release on Github](https://github.com/openai/codex/releases/tag/rust-v0.123.0)
- 2026-04-20

### Codex app26.417

### New features

- Added local branch search and non-image file pasting in the composer.
- Added collapsible sidebar sections, tray usage-limit surfacing, and a command-palette theme switcher.

### Performance improvements and bug fixes

- Made review faster and more stable with better diff batching and preserved diff and search state.
- Fixed projectless cwd and permissions handling, default file opening, spreadsheet suggestions, and remote-control reconnect issues.
- Additional performance improvements and bug fixes.
- 2026-04-20

### Codex CLI0.122.0
````$npminstall-g@openai/codex@0.122.0````
View details

## New Features

- Standalone installs are more self-contained, and`codex app`now opens or installs Desktop correctly on Windows and Intel Macs (#17022[#17022](https://github.com/openai/codex/pull/17022),#18500[#18500](https://github.com/openai/codex/pull/18500)).
- The TUI can open`/side`conversations for quick side questions, and queued input now supports slash commands and`!`shell prompts while work is running (#18190[#18190](https://github.com/openai/codex/pull/18190),#18542[#18542](https://github.com/openai/codex/pull/18542)).
- Plan Mode can start implementation in a fresh context, with context-usage shown before deciding whether to carry the planning thread forward (#17499[#17499](https://github.com/openai/codex/pull/17499),#18573[#18573](https://github.com/openai/codex/pull/18573)).
- Plugin workflows now include tabbed browsing, inline enable/disable toggles, marketplace removal, and remote, cross-repo, or local marketplace sources (#18222[#18222](https://github.com/openai/codex/pull/18222),#18395[#18395](https://github.com/openai/codex/pull/18395),#17752[#17752](https://github.com/openai/codex/pull/17752),#17751[#17751](https://github.com/openai/codex/pull/17751),#17277[#17277](https://github.com/openai/codex/pull/17277),#18017[#18017](https://github.com/openai/codex/pull/18017),#18246[#18246](https://github.com/openai/codex/pull/18246)).
- Filesystem permissions now support deny-read glob policies, managed deny-read requirements, platform sandbox enforcement, and isolated`codex exec`runs that ignore user config or rules (#15979[#15979](https://github.com/openai/codex/pull/15979),#17740[#17740](https://github.com/openai/codex/pull/17740),#18096[#18096](https://github.com/openai/codex/pull/18096),#18646[#18646](https://github.com/openai/codex/pull/18646)).
- Tool discovery and image generation are now enabled by default, with higher-detail image handling and original-detail metadata support for MCP and`js_repl`image outputs (#17854[#17854](https://github.com/openai/codex/pull/17854),#17153[#17153](https://github.com/openai/codex/pull/17153),#17714[#17714](https://github.com/openai/codex/pull/17714),#18386[#18386](https://github.com/openai/codex/pull/18386)).

## Bug Fixes

- App-server approvals, user-input prompts, and MCP elicitations now disappear from the TUI when another client resolves them, instead of leaving stale prompts behind (#15134[#15134](https://github.com/openai/codex/pull/15134)).
- Remote-control startup now tolerates missing ChatGPT auth, and MCP startup cancellation works again through app-server sessions (#18117[#18117](https://github.com/openai/codex/pull/18117),#18078[#18078](https://github.com/openai/codex/pull/18078)).
- Resumed and forked app-server threads now replay token usage immediately so context/status UI starts with the restored state (#18023[#18023](https://github.com/openai/codex/pull/18023)).
- Security-sensitive flows were tightened: logout revokes managed ChatGPT tokens, project hooks and exec policies require trusted workspaces, and Windows sandbox setup avoids broad user-profile and SSH-root grants (#17825[#17825](https://github.com/openai/codex/pull/17825),#14718[#14718](https://github.com/openai/codex/pull/14718),#18443[#18443](https://github.com/openai/codex/pull/18443),#18493[#18493](https://github.com/openai/codex/pull/18493)).
- Sandboxed`apply_patch`writes work correctly with split filesystem policies, and file watchers now notice files created after watching begins (#18296[#18296](https://github.com/openai/codex/pull/18296),#18492[#18492](https://github.com/openai/codex/pull/18492)).
- Several TUI rough edges were fixed, including fatal skills-list failures, invalid resume hints, duplicate context statusline entries,`/model`menu loops, redundant memory notices, and terminal title quoting in iTerm2 (#18061[#18061](https://github.com/openai/codex/pull/18061),#18059[#18059](https://github.com/openai/codex/pull/18059),#18054[#18054](https://github.com/openai/codex/pull/18054),#18154[#18154](https://github.com/openai/codex/pull/18154),#18580[#18580](https://github.com/openai/codex/pull/18580),#18261[#18261](https://github.com/openai/codex/pull/18261)).

## Documentation

- Added a security-boundaries reference to`SECURITY.md`for sandboxing, approvals, and network controls (#17848[#17848](https://github.com/openai/codex/pull/17848),#18004[#18004](https://github.com/openai/codex/pull/18004)).
- Documented custom MCP server approval defaults and exec-server stdin behavior (#17843[#17843](https://github.com/openai/codex/pull/17843),#18086[#18086](https://github.com/openai/codex/pull/18086)).
- Updated app-server docs for plugin API changes, marketplace removal, resume/fork token-usage replay, and warning notifications (#17277[#17277](https://github.com/openai/codex/pull/17277),#17751[#17751](https://github.com/openai/codex/pull/17751),#18023[#18023](https://github.com/openai/codex/pull/18023),#18298[#18298](https://github.com/openai/codex/pull/18298)).
- Added a short guide for the responses API proxy (#18604[#18604](https://github.com/openai/codex/pull/18604)).

## Chores

- Split plugin and marketplace code into`codex-core-plugins`, moved more connector code into`connectors`, and continued breaking up the large core session/turn modules (#18070[#18070](https://github.com/openai/codex/pull/18070),#18158[#18158](https://github.com/openai/codex/pull/18158),#18200[#18200](https://github.com/openai/codex/pull/18200),#18206[#18206](https://github.com/openai/codex/pull/18206),#18244[#18244](https://github.com/openai/codex/pull/18244),#18249[#18249](https://github.com/openai/codex/pull/18249)).
- Refactored config loading and`AGENTS.md`discovery behind narrower filesystem and manager abstractions (#18209[#18209](https://github.com/openai/codex/pull/18209),#18035[#18035](https://github.com/openai/codex/pull/18035)).
- Stabilized Bazel and CI with flake fixes, native Rust test sharding, scoped repository caches, stronger Windows clippy coverage, and updated`rules_rs`/LLVM pins (#17791[#17791](https://github.com/openai/codex/pull/17791),#18082[#18082](https://github.com/openai/codex/pull/18082),#18366[#18366](https://github.com/openai/codex/pull/18366),#18350[#18350](https://github.com/openai/codex/pull/18350),#18397[#18397](https://github.com/openai/codex/pull/18397)).
- Added core CODEOWNERS and a smaller development build profile (#18362[#18362](https://github.com/openai/codex/pull/18362),#18612[#18612](https://github.com/openai/codex/pull/18612)).
- Removed the stale core`models.json`and updated release preparation to refresh the active model catalog (#18585[#18585](https://github.com/openai/codex/pull/18585)).

## Changelog

Full Changelog:rust-v0.121.0...rust-v0.122.0[rust-v0.121.0...rust-v0.122.0](https://github.com/openai/codex/compare/rust-v0.121.0...rust-v0.122.0)

- #17958[#17958](https://github.com/openai/codex/pull/17958)Support remote compaction for Azure responses providers@ivanmurashko[@ivanmurashko](https://github.com/ivanmurashko)
- #17848[#17848](https://github.com/openai/codex/pull/17848)[docs] Add security boundaries reference in SECURITY.md@evawong-oai[@evawong-oai](https://github.com/evawong-oai)
- #17990[#17990](https://github.com/openai/codex/pull/17990)Auto install start-codex-exec.sh dependencies@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #17892[#17892](https://github.com/openai/codex/pull/17892)Migrate archive/unarchive to local ThreadStore@wiltzius-openai[@wiltzius-openai](https://github.com/wiltzius-openai)
- #17989[#17989](https://github.com/openai/codex/pull/17989)[codex] Restore remote exec-server filesystem tests@starr-openai[@starr-openai](https://github.com/starr-openai)
- #15134[#15134](https://github.com/openai/codex/pull/15134)Dismiss stale app-server requests after remote resolution@ebrevdo[@ebrevdo](https://github.com/ebrevdo)
- #18002[#18002](https://github.com/openai/codex/pull/18002)Re-enable it@jif-oai[@jif-oai](https://github.com/jif-oai)
- #17885[#17885](https://github.com/openai/codex/pull/17885)feat: Support alternate marketplace manifests and local string@xl-openai[@xl-openai](https://github.com/xl-openai)
- #18003[#18003](https://github.com/openai/codex/pull/18003)[docs] Revert extra changes from PR 17848@evawong-oai[@evawong-oai](https://github.com/evawong-oai)
- #17714[#17714](https://github.com/openai/codex/pull/17714)Support original-detail metadata on MCP image outputs@fjord-oai[@fjord-oai](https://github.com/fjord-oai)
- #17022[#17022](https://github.com/openai/codex/pull/17022)Significantly improve standalone installer@efrazer-oai[@efrazer-oai](https://github.com/efrazer-oai)
- #17853[#17853](https://github.com/openai/codex/pull/17853)[mcp] Add dummy tools for previously called but currently missing tools.@mzeng-openai[@mzeng-openai](https://github.com/mzeng-openai)
- #18004[#18004](https://github.com/openai/codex/pull/18004)[docs] Restore SECURITY.md update from PR 17848@evawong-oai[@evawong-oai](https://github.com/evawong-oai)
- #17896[#17896](https://github.com/openai/codex/pull/17896)Clarify realtime v2 context and handoff messages@bxie-openai[@bxie-openai](https://github.com/bxie-openai)
- #17742[#17742](https://github.com/openai/codex/pull/17742)removing network proxy for yolo@won-openai[@won-openai](https://github.com/won-openai)
- #17999[#17999](https://github.com/openai/codex/pull/17999)[codex] Make command exec delta tests chunk tolerant@euroelessar[@euroelessar](https://github.com/euroelessar)
- #18033[#18033](https://github.com/openai/codex/pull/18033)feat: introduce codex-pr-body skill@bolinfest[@bolinfest](https://github.com/bolinfest)
- #17877[#17877](https://github.com/openai/codex/pull/17877)Display YOLO mode permissions if set when launching TUI@canvrno-oai[@canvrno-oai](https://github.com/canvrno-oai)
- #18022[#18022](https://github.com/openai/codex/pull/18022)Async config loading@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #17854[#17854](https://github.com/openai/codex/pull/17854)Update ToolSearch to be enabled by default@mzeng-openai[@mzeng-openai](https://github.com/mzeng-openai)
- #17831[#17831](https://github.com/openai/codex/pull/17831)[codex][mcp] Add resource uri meta to tool call item.@mzeng-openai[@mzeng-openai](https://github.com/mzeng-openai)
- #18070[#18070](https://github.com/openai/codex/pull/18070)Extract plugin loading and marketplace logic into codex-core-plugins@xl-openai[@xl-openai](https://github.com/xl-openai)
- #18078[#18078](https://github.com/openai/codex/pull/18078)Fix MCP startup cancellation through app server@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #17151[#17151](https://github.com/openai/codex/pull/17151)[codex] Route Fed ChatGPT auth through Fed edge@jackz-oai[@jackz-oai](https://github.com/jackz-oai)
- #18006[#18006](https://github.com/openai/codex/pull/18006)fix: more flake@jif-oai[@jif-oai](https://github.com/jif-oai)
- #18127[#18127](https://github.com/openai/codex/pull/18127)fix: windows flake@jif-oai[@jif-oai](https://github.com/jif-oai)
- #18137[#18137](https://github.com/openai/codex/pull/18137)nit: add min values for memories@jif-oai[@jif-oai](https://github.com/jif-oai)
- #18135[#18135](https://github.com/openai/codex/pull/18135)debug: windows flake@jif-oai[@jif-oai](https://github.com/jif-oai)
- #18138[#18138](https://github.com/openai/codex/pull/18138)chore: more pollution filtering@jif-oai[@jif-oai](https://github.com/jif-oai)
- #18134[#18134](https://github.com/openai/codex/pull/18134)chore: unify memory drop endpoints@jif-oai[@jif-oai](https://github.com/jif-oai)
- #18144[#18144](https://github.com/openai/codex/pull/18144)nit: get rid of an expect@jif-oai[@jif-oai](https://github.com/jif-oai)
- #17791[#17791](https://github.com/openai/codex/pull/17791)Stabilize Bazel tests (timeout tweaks and flake fixes)@ddr-oai[@ddr-oai](https://github.com/ddr-oai)
- #18117[#18117](https://github.com/openai/codex/pull/18117)fix: auth preflight@jif-oai[@jif-oai](https://github.com/jif-oai)
- #18146[#18146](https://github.com/openai/codex/pull/18146)chore: use`justfile_directory`in just file@jif-oai[@jif-oai](https://github.com/jif-oai)
- #18085[#18085](https://github.com/openai/codex/pull/18085)[1/8] Add MCP server environment config@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #18054[#18054](https://github.com/openai/codex/pull/18054)fix(tui): remove duplicate context statusline item@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #17287[#17287](https://github.com/openai/codex/pull/17287)[code mode] defer mcp tools from exec description@sayan-oai[@sayan-oai](https://github.com/sayan-oai)
- #18057[#18057](https://github.com/openai/codex/pull/18057)Prefill rename prompt with current thread name@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #18059[#18059](https://github.com/openai/codex/pull/18059)Fix invalid TUI resume hints@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #17153[#17153](https://github.com/openai/codex/pull/17153)Launch image generation by default@won-openai[@won-openai](https://github.com/won-openai)
- #18042[#18042](https://github.com/openai/codex/pull/18042)Make yolo skip managed-network tool enforcement@won-openai[@won-openai](https://github.com/won-openai)
- #18154[#18154](https://github.com/openai/codex/pull/18154)fix: model menu pop@jif-oai[@jif-oai](https://github.com/jif-oai)
- #17826[#17826](https://github.com/openai/codex/pull/17826)[codex] Add remote thread store implementation@wiltzius-openai[@wiltzius-openai](https://github.com/wiltzius-openai)
- #18086[#18086](https://github.com/openai/codex/pull/18086)[2/8] Support piped stdin in exec process API@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #18061[#18061](https://github.com/openai/codex/pull/18061)Avoid fatal TUI errors on skills list failure@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #15979[#15979](https://github.com/openai/codex/pull/15979)feat(permissions): add glob deny-read policy support@viyatb-oai[@viyatb-oai](https://github.com/viyatb-oai)
- #18055[#18055](https://github.com/openai/codex/pull/18055)Improve external agent plugin migration for configured marketplaces@alexsong-oai[@alexsong-oai](https://github.com/alexsong-oai)
- #17425[#17425](https://github.com/openai/codex/pull/17425)Auto-upgrade configured marketplaces@xli-oai[@xli-oai](https://github.com/xli-oai)
- #18035[#18035](https://github.com/openai/codex/pull/18035)Refactor AGENTS.md discovery into AgentsMdManager@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #18158[#18158](https://github.com/openai/codex/pull/18158)Move more connector logic into connectors crate@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #17843[#17843](https://github.com/openai/codex/pull/17843)Add server-level approval defaults for custom MCP servers@mzeng-openai[@mzeng-openai](https://github.com/mzeng-openai)
- #18178[#18178](https://github.com/openai/codex/pull/18178)fix: drop lock earlier; was held across send_event().await unnecessarily@bolinfest[@bolinfest](https://github.com/bolinfest)
- #18000[#18000](https://github.com/openai/codex/pull/18000)Make thread unsubscribe test deterministic@starr-openai[@starr-openai](https://github.com/starr-openai)
- #17996[#17996](https://github.com/openai/codex/pull/17996)Add codex_hook_run analytics event@abhinav-oai[@abhinav-oai](https://github.com/abhinav-oai)
- #18184[#18184](https://github.com/openai/codex/pull/18184)fix: fix clippy issue in examples/ folder@bolinfest[@bolinfest](https://github.com/bolinfest)
- #18023[#18023](https://github.com/openai/codex/pull/18023)fix(app-server): replay token usage after resume and fork@fcoury-oai[@fcoury-oai](https://github.com/fcoury-oai)
- #18172[#18172](https://github.com/openai/codex/pull/18172)[codex] Make realtime startup context truncation deterministic@bxie-openai[@bxie-openai](https://github.com/bxie-openai)
- #18192[#18192](https://github.com/openai/codex/pull/18192)Throttle Windows Bazel test concurrency@starr-openai[@starr-openai](https://github.com/starr-openai)
- #18200[#18200](https://github.com/openai/codex/pull/18200)[codex] Split codex op handlers@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #17387[#17387](https://github.com/openai/codex/pull/17387)Register agent tasks behind use_agent_identity@adrian-openai[@adrian-openai](https://github.com/adrian-openai)
- #18026[#18026](https://github.com/openai/codex/pull/18026)Add OTEL metrics for hook runs@abhinav-oai[@abhinav-oai](https://github.com/abhinav-oai)
- #18092[#18092](https://github.com/openai/codex/pull/18092)[codex] Update realtime V2 VAD silence delay and 1.5 prompt@bxie-openai[@bxie-openai](https://github.com/bxie-openai)
- #18188[#18188](https://github.com/openai/codex/pull/18188)Add tabbed lists, single line rendering, col width changes@canvrno-oai[@canvrno-oai](https://github.com/canvrno-oai)
- #18206[#18206](https://github.com/openai/codex/pull/18206)[codex] Split codex turn logic@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #18169[#18169](https://github.com/openai/codex/pull/18169)Use codex-auto-review for guardian reviews@jeffsharris[@jeffsharris](https://github.com/jeffsharris)
- #18196[#18196](https://github.com/openai/codex/pull/18196)Use in-process app-server for unknown-thread MCP read test@mzeng-openai[@mzeng-openai](https://github.com/mzeng-openai)
- #18116[#18116](https://github.com/openai/codex/pull/18116)Move marketplace add under plugin command@xli-oai[@xli-oai](https://github.com/xli-oai)
- #18096[#18096](https://github.com/openai/codex/pull/18096)feat(sandbox): add glob deny-read platform enforcement@viyatb-oai[@viyatb-oai](https://github.com/viyatb-oai)
- #17971[#17971](https://github.com/openai/codex/pull/17971)fix: deprecate use_legacy_landlock feature flag@viyatb-oai[@viyatb-oai](https://github.com/viyatb-oai)
- #18209[#18209](https://github.com/openai/codex/pull/18209)Refactor config loading to use filesystem abstraction@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #17862[#17862](https://github.com/openai/codex/pull/17862)Stream apply_patch changes@akshaynathan[@akshaynathan](https://github.com/akshaynathan)
- #18244[#18244](https://github.com/openai/codex/pull/18244)Split codex session modules@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #17713[#17713](https://github.com/openai/codex/pull/17713)feat: add opt-in provider runtime abstraction@celia-oai[@celia-oai](https://github.com/celia-oai)
- #18182[#18182](https://github.com/openai/codex/pull/18182)feat: Handle alternate plugin manifest paths@xl-openai[@xl-openai](https://github.com/xl-openai)
- #18219[#18219](https://github.com/openai/codex/pull/18219)Move Computer Use tool suggestion to core@leoshimo-oai[@leoshimo-oai](https://github.com/leoshimo-oai)
- #18231[#18231](https://github.com/openai/codex/pull/18231)codex: split thread/read view loading@wiltzius-openai[@wiltzius-openai](https://github.com/wiltzius-openai)
- #18126[#18126](https://github.com/openai/codex/pull/18126)fix(exec-policy) rules parsing@dylan-hurd-oai[@dylan-hurd-oai](https://github.com/dylan-hurd-oai)
- #17825[#17825](https://github.com/openai/codex/pull/17825)[codex] Revoke ChatGPT tokens on logout@sashank-oai[@sashank-oai](https://github.com/sashank-oai)
- #18304[#18304](https://github.com/openai/codex/pull/18304)Fix Windows exec policy test flake@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #17947[#17947](https://github.com/openai/codex/pull/17947)fix: reduce writable root@jif-oai[@jif-oai](https://github.com/jif-oai)
- #18246[#18246](https://github.com/openai/codex/pull/18246)Sync local plugin imports, async remote imports, refresh caches after…@alexsong-oai[@alexsong-oai](https://github.com/alexsong-oai)
- #18097[#18097](https://github.com/openai/codex/pull/18097)defer all tools behind feature flag@sayan-oai[@sayan-oai](https://github.com/sayan-oai)
- #17563[#17563](https://github.com/openai/codex/pull/17563)Add PermissionRequest hooks support@abhinav-oai[@abhinav-oai](https://github.com/abhinav-oai)
- #18338[#18338](https://github.com/openai/codex/pull/18338)nit: phase 2 ephemeral@jif-oai[@jif-oai](https://github.com/jif-oai)
- #18267[#18267](https://github.com/openai/codex/pull/18267)Support Ctrl+P/Ctrl+N in resume picker@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #18261[#18261](https://github.com/openai/codex/pull/18261)fix(tui): use BEL for terminal title updates@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #17740[#17740](https://github.com/openai/codex/pull/17740)feat(config): support managed deny-read requirements@viyatb-oai[@viyatb-oai](https://github.com/viyatb-oai)
- #18249[#18249](https://github.com/openai/codex/pull/18249)Move codex module under session@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #18351[#18351](https://github.com/openai/codex/pull/18351)Fix config-loader tests after filesystem abstraction race@bolinfest[@bolinfest](https://github.com/bolinfest)
- #18021[#18021](https://github.com/openai/codex/pull/18021)Guardian -> Auto-Review@won-openai[@won-openai](https://github.com/won-openai)
- #18140[#18140](https://github.com/openai/codex/pull/18140)feat: config aliases@jif-oai[@jif-oai](https://github.com/jif-oai)
- #17232[#17232](https://github.com/openai/codex/pull/17232)Make app tool hint defaults pessimistic for app policies@colby-oai[@colby-oai](https://github.com/colby-oai)
- #17499[#17499](https://github.com/openai/codex/pull/17499)feat(tui): add clear-context plan implementation@fcoury-oai[@fcoury-oai](https://github.com/fcoury-oai)
- #18352[#18352](https://github.com/openai/codex/pull/18352)codex: route thread/read persistence through thread store@wiltzius-openai[@wiltzius-openai](https://github.com/wiltzius-openai)
- #18263[#18263](https://github.com/openai/codex/pull/18263)enable tool search over dynamic tools@sayan-oai[@sayan-oai](https://github.com/sayan-oai)
- #18350[#18350](https://github.com/openai/codex/pull/18350)ci: make Windows Bazel clippy catch core test imports@bolinfest[@bolinfest](https://github.com/bolinfest)
- #18362[#18362](https://github.com/openai/codex/pull/18362)Add core CODEOWNERS@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #18366[#18366](https://github.com/openai/codex/pull/18366)ci: scope Bazel repository cache by job@bolinfest[@bolinfest](https://github.com/bolinfest)
- #17305[#17305](https://github.com/openai/codex/pull/17305)Add sorting/backwardsCursor to thread/list and new thread/turns/list api@ddr-oai[@ddr-oai](https://github.com/ddr-oai)
- #18020[#18020](https://github.com/openai/codex/pull/18020)[3/6] Add pushed exec process events@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #12640[#12640](https://github.com/openai/codex/pull/12640)Update models.json @github-actions
- #18373[#18373](https://github.com/openai/codex/pull/18373)Show default reasoning in /status@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #18379[#18379](https://github.com/openai/codex/pull/18379)Attribute automated PR Babysitter review replies@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #18087[#18087](https://github.com/openai/codex/pull/18087)[4/6] Abstract MCP stdio server launching@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #18370[#18370](https://github.com/openai/codex/pull/18370)perf(tui): defer startup skills refresh@fcoury-oai[@fcoury-oai](https://github.com/fcoury-oai)
- #18222[#18222](https://github.com/openai/codex/pull/18222)/plugins: Add v2 tabbed marketplace menu@canvrno-oai[@canvrno-oai](https://github.com/canvrno-oai)
- #18227[#18227](https://github.com/openai/codex/pull/18227)[codex] Propagate rate limit reached type@richardopenai[@richardopenai](https://github.com/richardopenai)
- #18380[#18380](https://github.com/openai/codex/pull/18380)exec-server: preserve fs helper runtime env@starr-openai[@starr-openai](https://github.com/starr-openai)
- #18381[#18381](https://github.com/openai/codex/pull/18381)Remove the tier constraint from connectors directory requests@xl-openai[@xl-openai](https://github.com/xl-openai)
- #18211[#18211](https://github.com/openai/codex/pull/18211)refactor: narrow async lock guard lifetimes@bolinfest[@bolinfest](https://github.com/bolinfest)
- #18017[#18017](https://github.com/openai/codex/pull/18017)[codex] Add cross-repo plugin sources to marketplace manifests@xli-oai[@xli-oai](https://github.com/xli-oai)
- #18398[#18398](https://github.com/openai/codex/pull/18398)refactor: use cloneable async channels for shared receivers@bolinfest[@bolinfest](https://github.com/bolinfest)
- #18296[#18296](https://github.com/openai/codex/pull/18296)fix: fix fs sandbox helper for apply_patch@viyatb-oai[@viyatb-oai](https://github.com/viyatb-oai)
- #18397[#18397](https://github.com/openai/codex/pull/18397)[codex] Upgrade rules_rs and llvm to latest BCR versions@zbarsky-openai[@zbarsky-openai](https://github.com/zbarsky-openai)
- #18082[#18082](https://github.com/openai/codex/pull/18082)bazel: use native rust test sharding@bolinfest[@bolinfest](https://github.com/bolinfest)
- #18384[#18384](https://github.com/openai/codex/pull/18384)Update image resizing to fit 2048 square bounds@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #17277[#17277](https://github.com/openai/codex/pull/17277)feat: Add remote plugin fields to plugin API@xl-openai[@xl-openai](https://github.com/xl-openai)
- #18395[#18395](https://github.com/openai/codex/pull/18395)/plugins: Add inline enablement toggles@canvrno-oai[@canvrno-oai](https://github.com/canvrno-oai)
- #14718[#14718](https://github.com/openai/codex/pull/14718)fix: trust-gate project hooks and exec policies@viyatb-oai[@viyatb-oai](https://github.com/viyatb-oai)
- #17891[#17891](https://github.com/openai/codex/pull/17891)[TUI] add external config migration prompt when start TUI@alexsong-oai[@alexsong-oai](https://github.com/alexsong-oai)
- #18369[#18369](https://github.com/openai/codex/pull/18369)Feat/auto review dev message marker@won-openai[@won-openai](https://github.com/won-openai)
- #18298[#18298](https://github.com/openai/codex/pull/18298)feat: Budget skill metadata and surface trimming as a warning@xl-openai[@xl-openai](https://github.com/xl-openai)
- #18449[#18449](https://github.com/openai/codex/pull/18449)[codex] Describe uninstalled cross-repo plugin reads@xli-oai[@xli-oai](https://github.com/xli-oai)
- #18220[#18220](https://github.com/openai/codex/pull/18220)[codex] Add owner nudge app-server API@richardopenai[@richardopenai](https://github.com/richardopenai)
- #17752[#17752](https://github.com/openai/codex/pull/17752)[codex] Add marketplace remove command and shared logic@xli-oai[@xli-oai](https://github.com/xli-oai)
- #18382[#18382](https://github.com/openai/codex/pull/18382)Add max context window model metadata@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #18325[#18325](https://github.com/openai/codex/pull/18325)Revert "[codex] drain mailbox only at request boundaries"@jif-oai[@jif-oai](https://github.com/jif-oai)
- #18386[#18386](https://github.com/openai/codex/pull/18386)Update image outputs to default to high detail@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #18499[#18499](https://github.com/openai/codex/pull/18499)Fix plugin cache panic when cwd is unavailable@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #18212[#18212](https://github.com/openai/codex/pull/18212)[5/6] Wire executor-backed MCP stdio@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #18573[#18573](https://github.com/openai/codex/pull/18573)feat(tui): show context used in plan implementation prompt@fcoury-oai[@fcoury-oai](https://github.com/fcoury-oai)
- #18500[#18500](https://github.com/openai/codex/pull/18500)Support`codex app`on macOS (Intel) and Windows@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #18542[#18542](https://github.com/openai/codex/pull/18542)Queue slash and shell prompts in the TUI@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #18524[#18524](https://github.com/openai/codex/pull/18524)Add fallback source for external official marketplace@alexsong-oai[@alexsong-oai](https://github.com/alexsong-oai)
- #18571[#18571](https://github.com/openai/codex/pull/18571)Log realtime session id@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #18585[#18585](https://github.com/openai/codex/pull/18585)Remove unused models.json@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #18190[#18190](https://github.com/openai/codex/pull/18190)Add`/side`conversations@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #18580[#18580](https://github.com/openai/codex/pull/18580)Avoid redundant memory enable notice@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #18443[#18443](https://github.com/openai/codex/pull/18443)Do not grant Windows sandbox ACLs on USERPROFILE@efrazer-oai[@efrazer-oai](https://github.com/efrazer-oai)
- #18493[#18493](https://github.com/openai/codex/pull/18493)Filter Windows sandbox roots from SSH config dependencies@efrazer-oai[@efrazer-oai](https://github.com/efrazer-oai)
- #17978[#17978](https://github.com/openai/codex/pull/17978)Persist and prewarm agent tasks per thread@adrian-openai[@adrian-openai](https://github.com/adrian-openai)
- #18604[#18604](https://github.com/openai/codex/pull/18604)Add tldr docs for responses-api-proxy@andmis[@andmis](https://github.com/andmis)
- #18601[#18601](https://github.com/openai/codex/pull/18601)Soften Fast mode plan usage copy@pash-openai[@pash-openai](https://github.com/pash-openai)
- #18596[#18596](https://github.com/openai/codex/pull/18596)chore(multiagent) skills instructions toggle@dylan-hurd-oai[@dylan-hurd-oai](https://github.com/dylan-hurd-oai)
- #18599[#18599](https://github.com/openai/codex/pull/18599)fix(guardian) disable skills message in guardian thread@dylan-hurd-oai[@dylan-hurd-oai](https://github.com/dylan-hurd-oai)
- #18612[#18612](https://github.com/openai/codex/pull/18612)Create dev-small build profile@andmis[@andmis](https://github.com/andmis)
- #18440[#18440](https://github.com/openai/codex/pull/18440)Use thread IDs in TUI resume hints@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #18605[#18605](https://github.com/openai/codex/pull/18605)TUI: remove simple legacy_core re-exports@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #18625[#18625](https://github.com/openai/codex/pull/18625)Add`codex debug models`to show model catalog@andmis[@andmis](https://github.com/andmis)
- #18221[#18221](https://github.com/openai/codex/pull/18221)[codex] Add workspace owner usage nudge UI@richardopenai[@richardopenai](https://github.com/richardopenai)
- #17980[#17980](https://github.com/openai/codex/pull/17980)[codex] Use AgentAssertion downstream behind use_agent_identity@adrian-openai[@adrian-openai](https://github.com/adrian-openai)
- #17751[#17751](https://github.com/openai/codex/pull/17751)[codex] Add marketplace/remove app-server RPC@xli-oai[@xli-oai](https://github.com/xli-oai)
- #18644[#18644](https://github.com/openai/codex/pull/18644)feat: add mem 2 agent header@jif-oai[@jif-oai](https://github.com/jif-oai)
- #18353[#18353](https://github.com/openai/codex/pull/18353)chore: morpheus to path@jif-oai[@jif-oai](https://github.com/jif-oai)
- #18649[#18649](https://github.com/openai/codex/pull/18649)fix: main 2@jif-oai[@jif-oai](https://github.com/jif-oai)
- #17721[#17721](https://github.com/openai/codex/pull/17721)Stabilize marketplace/remove installedRoot test@xli-oai[@xli-oai](https://github.com/xli-oai)
- #18492[#18492](https://github.com/openai/codex/pull/18492)fix: FS watcher when file does not exist yet@jif-oai[@jif-oai](https://github.com/jif-oai)
- #18646[#18646](https://github.com/openai/codex/pull/18646)feat: add`--ignore-user-config`and`--ignore-rules`@jif-oai[@jif-oai](https://github.com/jif-oai)
- #18652[#18652](https://github.com/openai/codex/pull/18652)nit: telepathy to chronicle in tests@jif-oai[@jif-oai](https://github.com/jif-oai)
- #18654[#18654](https://github.com/openai/codex/pull/18654)fix: exec policy loading for sub-agents@jif-oai[@jif-oai](https://github.com/jif-oai)
- #18651[#18651](https://github.com/openai/codex/pull/18651)feat: chronicle alias@jif-oai[@jif-oai](https://github.com/jif-oai)

Full release on Github[Full release on Github](https://github.com/openai/codex/releases/tag/rust-v0.122.0)
- 2026-04-16

### Codex can now help with more of your work26.415

Codex is becoming a broader workspace for getting work done with AI. This update makes it easier to start work with less setup, verify what Codex is building, create richer outputs, and keep momentum across longer-running tasks.

#### Verify more of your work

The Codex app now includes an early**in-app browser**[in-app browser](/codex/app/browser). You can open local or public pages that don’t require sign-in, comment directly on the rendered page, and ask Codex to address page-level feedback.[Codex app showing a browser comment on a local web app preview](/images/codex/app/in-app-browser-light.webp)[Codex app showing a browser comment on a local web app preview](/images/codex/app/in-app-browser-dark.webp)[Codex app showing a browser comment on a local web app preview](/images/codex/app/in-app-browser-light.webp)[Codex app showing a browser comment on a local web app preview](/images/codex/app/in-app-browser-dark.webp)

**Computer use**[Computer use](/codex/app/computer-use)lets Codex operate macOS apps by seeing, clicking, and typing, which helps with native app testing, simulator flows, low-risk app settings, and GUI-only bugs.

The feature isn’t available in the European Economic Area, the United Kingdom, or Switzerland at launch.

#### Start, follow, and steer work

**Chats**[Chats](/codex/app/features#projectless-threads)are threads you can start without choosing a project folder first. They’re useful for research, writing, planning, analysis, source gathering, and tool-driven work that doesn’t begin in a codebase.

For work that needs a later check-in,**thread automations**[thread automations](/codex/app/automations#thread-automations)can wake up the same thread on a schedule while preserving the conversation context. Use them to check a long-running process, watch for updates, or continue a follow-up loop without starting from scratch.

**The task sidebar**[The task sidebar](/codex/app/features#task-sidebar)makes plans, sources, generated artifacts, and summaries easier to follow while Codex works.**Context-aware suggestions**[Context-aware suggestions](/codex/app/settings#context-aware-suggestions)can also help you pick up relevant follow-ups when you start or return to Codex.

#### Stronger for software development

Codex now brings more of the**pull request workflow**into the app. You can inspect**GitHub pull requests**[GitHub pull requests](/codex/app/review#pull-request-reviews)in the sidebar, review comments in the diff, review changed files, then ask Codex to explain feedback, make changes, check them, and keep the review moving.

#### Review richer outputs

The**artifact viewer**[artifact viewer](/codex/app/features#artifact-viewer)can preview generated files such as PDF files, spreadsheets, documents, and presentations in the sidebar before you commit or share them.**Memories**[Memories](/codex/memories), where available, can also carry useful context from past tasks into future threads, including stable preferences, project conventions, and recurring work patterns.

#### Other features

- Remote connections[Remote connections](/codex/remote-connections)- We are gradually rolling out SSH remote connections in alpha
- Support formultiple terminals[multiple terminals](/codex/app/features#integrated-terminal)
- macOS menu bar andWindows system tray[Windows system tray](/codex/app/windows)support
- Multi-window support[Multi-window support](/codex/app/features#floating-pop-out-window)
- Intel Mac support[Intel Mac support](/codex/app)
- New plugins[New plugins](/codex/plugins)
- Improved thread and tool rendering
- 2026-04-15

### Codex CLI0.121.0
````$npminstall-g@openai/codex@0.121.0````
View details

## New Features

- Added`codex marketplace add`and app-server support for installing plugin marketplaces from GitHub, git URLs, local directories, and direct`marketplace.json`URLs (#17087[#17087](https://github.com/openai/codex/pull/17087),#17717[#17717](https://github.com/openai/codex/pull/17717),#17756[#17756](https://github.com/openai/codex/pull/17756)).
- Added TUI prompt history improvements, including`Ctrl+R`reverse search and local recall for accepted slash commands (#17550[#17550](https://github.com/openai/codex/pull/17550),#17336[#17336](https://github.com/openai/codex/pull/17336)).
- Added TUI and app-server controls for memory mode, memory reset/deletion, and memory-extension cleanup (#17632[#17632](https://github.com/openai/codex/pull/17632),#17626[#17626](https://github.com/openai/codex/pull/17626),#17913[#17913](https://github.com/openai/codex/pull/17913),#17937[#17937](https://github.com/openai/codex/pull/17937),#17844[#17844](https://github.com/openai/codex/pull/17844)).
- Expanded MCP/plugin support with MCP Apps tool calls, namespaced MCP registration, parallel-call opt-in, and sandbox-state metadata for MCP servers (#17364[#17364](https://github.com/openai/codex/pull/17364),#17404[#17404](https://github.com/openai/codex/pull/17404),#17667[#17667](https://github.com/openai/codex/pull/17667),#17763[#17763](https://github.com/openai/codex/pull/17763)).
- Added realtime and app-server APIs for output modality, transcript completion events, raw turn item injection, and symlink-aware filesystem metadata (#17701[#17701](https://github.com/openai/codex/pull/17701),#17703[#17703](https://github.com/openai/codex/pull/17703),#17719[#17719](https://github.com/openai/codex/pull/17719)).
- Added a secure devcontainer profile with bubblewrap support, plus macOS sandbox allowlists for Unix sockets (#10431[#10431](https://github.com/openai/codex/pull/10431),#17547[#17547](https://github.com/openai/codex/pull/17547),#17654[#17654](https://github.com/openai/codex/pull/17654)).

## Bug Fixes

- Fixed macOS sandbox/proxy handling for private DNS and removed the`danger-full-access`denylist-only network mode (#17370[#17370](https://github.com/openai/codex/pull/17370),#17732[#17732](https://github.com/openai/codex/pull/17732)).
- Fixed Windows cwd/session matching so`resume --last`and`thread/list`work when paths use verbatim prefixes (#17414[#17414](https://github.com/openai/codex/pull/17414)).
- Fixed rate-limit/account handling for`prolite`plans and made unknown WHAM plan values decodable (#17419[#17419](https://github.com/openai/codex/pull/17419)).
- Made Guardian timeouts distinct from policy denials, with timeout-specific guidance and visible TUI history entries (#17381[#17381](https://github.com/openai/codex/pull/17381),#17486[#17486](https://github.com/openai/codex/pull/17486),#17521[#17521](https://github.com/openai/codex/pull/17521),#17557[#17557](https://github.com/openai/codex/pull/17557)).
- Stabilized app-server behavior by avoiding premature thread unloads, tolerating failed trust persistence on startup, and skipping broken symlinks in`fs/readDirectory`(#17398[#17398](https://github.com/openai/codex/pull/17398),#17595[#17595](https://github.com/openai/codex/pull/17595),#17907[#17907](https://github.com/openai/codex/pull/17907)).
- Fixed MCP/tool-call edge cases including flattened deferred tool names, elicitation timeout accounting, and empty namespace descriptions (#17556[#17556](https://github.com/openai/codex/pull/17556),#17566[#17566](https://github.com/openai/codex/pull/17566),#17946[#17946](https://github.com/openai/codex/pull/17946)).

## Documentation

- Documented the secure devcontainer profile and its bubblewrap requirements (#10431[#10431](https://github.com/openai/codex/pull/10431),#17547[#17547](https://github.com/openai/codex/pull/17547)).
- Added TUI composer documentation for history search behavior (#17550[#17550](https://github.com/openai/codex/pull/17550)).
- Updated app-server docs for new MCP, marketplace, turn injection, memory reset, filesystem metadata, external-agent migration, and websocket token-hash APIs (#17364[#17364](https://github.com/openai/codex/pull/17364),#17717[#17717](https://github.com/openai/codex/pull/17717),#17703[#17703](https://github.com/openai/codex/pull/17703),#17913[#17913](https://github.com/openai/codex/pull/17913),#17719[#17719](https://github.com/openai/codex/pull/17719),#17855[#17855](https://github.com/openai/codex/pull/17855),#17871[#17871](https://github.com/openai/codex/pull/17871)).
- Documented WSL1 bubblewrap limitations and WSL2 behavior (#17559[#17559](https://github.com/openai/codex/pull/17559)).
- Added memory pipeline documentation for extension cleanup (#17844[#17844](https://github.com/openai/codex/pull/17844)).

## Chores

- Hardened supply-chain and CI inputs by pinning GitHub Actions, cargo installs, git dependencies, V8 checksums, and cargo-deny source allowlists (#17471[#17471](https://github.com/openai/codex/pull/17471)).
- Added Bazel release-build verification so release-only Rust code is compiled in PR CI (#17704[#17704](https://github.com/openai/codex/pull/17704),#17705[#17705](https://github.com/openai/codex/pull/17705)).
- Introduced the`codex-thread-store`crate/interface and moved local thread listing behind it (#17659[#17659](https://github.com/openai/codex/pull/17659),#17824[#17824](https://github.com/openai/codex/pull/17824)).
- Required reviewed pnpm dependency build scripts for workspace installs (#17558[#17558](https://github.com/openai/codex/pull/17558)).
- Reduced Rust maintenance surface with broader absolute-path types and removal of unused helper APIs (#17407[#17407](https://github.com/openai/codex/pull/17407),#17792[#17792](https://github.com/openai/codex/pull/17792),#17146[#17146](https://github.com/openai/codex/pull/17146)).

## Changelog

Full Changelog:rust-v0.120.0...rust-v0.121.0[rust-v0.120.0...rust-v0.121.0](https://github.com/openai/codex/compare/rust-v0.120.0...rust-v0.121.0)

- #17087[#17087](https://github.com/openai/codex/pull/17087)Add marketplace command@xli-oai[@xli-oai](https://github.com/xli-oai)
- #17409[#17409](https://github.com/openai/codex/pull/17409)Fix Windows exec-server output test flake@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #17381[#17381](https://github.com/openai/codex/pull/17381)representing guardian review timeouts in protocol types@won-openai[@won-openai](https://github.com/won-openai)
- #17399[#17399](https://github.com/openai/codex/pull/17399)TUI: enforce core boundary@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #17370[#17370](https://github.com/openai/codex/pull/17370)fix: unblock private DNS in macOS sandbox@viyatb-oai[@viyatb-oai](https://github.com/viyatb-oai)
- #17396[#17396](https://github.com/openai/codex/pull/17396)update cloud requirements parse failure msg@alexsong-oai[@alexsong-oai](https://github.com/alexsong-oai)
- #17364[#17364](https://github.com/openai/codex/pull/17364)[mcp] Support MCP Apps part 3 - Add mcp tool call support.@mzeng-openai[@mzeng-openai](https://github.com/mzeng-openai)
- #17424[#17424](https://github.com/openai/codex/pull/17424)Stabilize marketplace add local source test@ningyi-oai[@ningyi-oai](https://github.com/ningyi-oai)
- #17414[#17414](https://github.com/openai/codex/pull/17414)Fix thread/list cwd filtering for Windows verbatim paths@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #10431[#10431](https://github.com/openai/codex/pull/10431)feat(devcontainer): add separate secure customer profile@viyatb-oai[@viyatb-oai](https://github.com/viyatb-oai)
- #17314[#17314](https://github.com/openai/codex/pull/17314)Pass turn id with feedback uploads@ningyi-oai[@ningyi-oai](https://github.com/ningyi-oai)
- #17336[#17336](https://github.com/openai/codex/pull/17336)fix(tui): recall accepted slash commands locally@fcoury-oai[@fcoury-oai](https://github.com/fcoury-oai)
- #17430[#17430](https://github.com/openai/codex/pull/17430)Handle closed TUI input stream as shutdown@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #17385[#17385](https://github.com/openai/codex/pull/17385)Add use_agent_identity feature flag@adrian-openai[@adrian-openai](https://github.com/adrian-openai)
- #17483[#17483](https://github.com/openai/codex/pull/17483)Update issue labeler agent labels@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #17493[#17493](https://github.com/openai/codex/pull/17493)fix@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #17419[#17419](https://github.com/openai/codex/pull/17419)Support prolite plan type@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #17416[#17416](https://github.com/openai/codex/pull/17416)Clear /ps after /stop@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #17415[#17415](https://github.com/openai/codex/pull/17415)Restore codex-tui resume hint on exit@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #17402[#17402](https://github.com/openai/codex/pull/17402)chore: refactor name and namespace to single type@sayan-oai[@sayan-oai](https://github.com/sayan-oai)
- #17486[#17486](https://github.com/openai/codex/pull/17486)changing decision semantics after guardian timeout@won-openai[@won-openai](https://github.com/won-openai)
- #17521[#17521](https://github.com/openai/codex/pull/17521)Clarify guardian timeout guidance@won-openai[@won-openai](https://github.com/won-openai)
- #17547[#17547](https://github.com/openai/codex/pull/17547)[codex] Support bubblewrap in secure Docker devcontainer@viyatb-oai[@viyatb-oai](https://github.com/viyatb-oai)
- #17519[#17519](https://github.com/openai/codex/pull/17519)Budget realtime current thread context@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #17556[#17556](https://github.com/openai/codex/pull/17556)[codex] Support flattened deferred MCP tool calls@fc-oai[@fc-oai](https://github.com/fc-oai)
- #17558[#17558](https://github.com/openai/codex/pull/17558)build(pnpm): require reviewed dependency build scripts@mcgrew-oai[@mcgrew-oai](https://github.com/mcgrew-oai)
- #17559[#17559](https://github.com/openai/codex/pull/17559)fix(sandboxing): reject WSL1 bubblewrap sandboxing@viyatb-oai[@viyatb-oai](https://github.com/viyatb-oai)
- #17520[#17520](https://github.com/openai/codex/pull/17520)Mirror user text into realtime@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #17550[#17550](https://github.com/openai/codex/pull/17550)feat(tui): add reverse history search to composer@fcoury-oai[@fcoury-oai](https://github.com/fcoury-oai)
- #17420[#17420](https://github.com/openai/codex/pull/17420)Remove context status-line meter@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #17506[#17506](https://github.com/openai/codex/pull/17506)Expose instruction sources (AGENTS.md) via app server@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #17566[#17566](https://github.com/openai/codex/pull/17566)fix(mcp) pause timer for elicitations@dylan-hurd-oai[@dylan-hurd-oai](https://github.com/dylan-hurd-oai)
- #17406[#17406](https://github.com/openai/codex/pull/17406)Add MCP tool wall time to model output@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #17294[#17294](https://github.com/openai/codex/pull/17294)Run exec-server fs operations through sandbox helper@starr-openai[@starr-openai](https://github.com/starr-openai)
- #17605[#17605](https://github.com/openai/codex/pull/17605)Stabilize exec-server process tests@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #17221[#17221](https://github.com/openai/codex/pull/17221)feat: ignore keyring on 0.0.0@jif-oai[@jif-oai](https://github.com/jif-oai)
- #17216[#17216](https://github.com/openai/codex/pull/17216)Build remote exec env from exec-server policy@jif-oai[@jif-oai](https://github.com/jif-oai)
- #17633[#17633](https://github.com/openai/codex/pull/17633)nit: change consolidation model@jif-oai[@jif-oai](https://github.com/jif-oai)
- #17640[#17640](https://github.com/openai/codex/pull/17640)fix: stability exec server@jif-oai[@jif-oai](https://github.com/jif-oai)
- #17643[#17643](https://github.com/openai/codex/pull/17643)fix: dedup compact@jif-oai[@jif-oai](https://github.com/jif-oai)
- #17247[#17247](https://github.com/openai/codex/pull/17247)Make forked agent spawns keep parent model config@friel-openai[@friel-openai](https://github.com/friel-openai)
- #17470[#17470](https://github.com/openai/codex/pull/17470)Fix custom tool output cleanup on stream failure@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #17417[#17417](https://github.com/openai/codex/pull/17417)Emit plan-mode prompt notifications for questionnaires@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #17481[#17481](https://github.com/openai/codex/pull/17481)Wrap status reset timestamps in narrow layouts@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #17601[#17601](https://github.com/openai/codex/pull/17601)Suppress duplicate compaction and terminal wait events@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #17657[#17657](https://github.com/openai/codex/pull/17657)Fix TUI compaction item replay@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #17595[#17595](https://github.com/openai/codex/pull/17595)Do not fail thread start when trust persistence fails@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #17407[#17407](https://github.com/openai/codex/pull/17407)Use AbsolutePathBuf in skill loading and codex_home@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #17626[#17626](https://github.com/openai/codex/pull/17626)feat: disable memory endpoint@jif-oai[@jif-oai](https://github.com/jif-oai)
- #17365[#17365](https://github.com/openai/codex/pull/17365)Include legacy deny paths in elevated Windows sandbox setup@iceweasel-oai[@iceweasel-oai](https://github.com/iceweasel-oai)
- #17638[#17638](https://github.com/openai/codex/pull/17638)feat: Avoid reloading curated marketplaces for tool-suggest discovera…@jif-oai[@jif-oai](https://github.com/jif-oai)
- #17398[#17398](https://github.com/openai/codex/pull/17398)app-server: Only unload threads which were unused for some time@euroelessar[@euroelessar](https://github.com/euroelessar)
- #17669[#17669](https://github.com/openai/codex/pull/17669)only specify remote ports when the rule needs them@iceweasel-oai[@iceweasel-oai](https://github.com/iceweasel-oai)
- #17691[#17691](https://github.com/openai/codex/pull/17691)Fix tui compilation@davidhao3300[@davidhao3300](https://github.com/davidhao3300)
- #17384[#17384](https://github.com/openai/codex/pull/17384)Update phase 2 memory model to gpt-5.4@kliu128[@kliu128](https://github.com/kliu128)
- #17395[#17395](https://github.com/openai/codex/pull/17395)Remove unnecessary tests@kliu128[@kliu128](https://github.com/kliu128)
- #17685[#17685](https://github.com/openai/codex/pull/17685)Cap realtime mirrored user turns@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #17699[#17699](https://github.com/openai/codex/pull/17699)change realtime tool description@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #17667[#17667](https://github.com/openai/codex/pull/17667)Add`supports_parallel_tool_calls`flag to included mcps@josiah-openai[@josiah-openai](https://github.com/josiah-openai)
- #17703[#17703](https://github.com/openai/codex/pull/17703)Add turn item injection API@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #17671[#17671](https://github.com/openai/codex/pull/17671)Stabilize exec-server filesystem tests in CI@starr-openai[@starr-openai](https://github.com/starr-openai)
- #17557[#17557](https://github.com/openai/codex/pull/17557)guardian timeout fix pr 3 - ux touch for timeouts@won-openai[@won-openai](https://github.com/won-openai)
- #17719[#17719](https://github.com/openai/codex/pull/17719)[codex] Add symlink flag to fs metadata@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #17146[#17146](https://github.com/openai/codex/pull/17146)[codex] Remove unused Rust helpers@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #17471[#17471](https://github.com/openai/codex/pull/17471)fix: pin inputs@viyatb-oai[@viyatb-oai](https://github.com/viyatb-oai)
- #17717[#17717](https://github.com/openai/codex/pull/17717)[codex] Refactor marketplace add into shared core flow@xli-oai[@xli-oai](https://github.com/xli-oai)
- #17747[#17747](https://github.com/openai/codex/pull/17747)Refactor plugin loading to async@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #17709[#17709](https://github.com/openai/codex/pull/17709)[codex] Initialize ICU data for code mode V8@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #17749[#17749](https://github.com/openai/codex/pull/17749)[codex] drain mailbox only at request boundaries@tibo-openai[@tibo-openai](https://github.com/tibo-openai)
- #16640[#16640](https://github.com/openai/codex/pull/16640)[codex-analytics] feature plumbing and emittance@rhan-oai[@rhan-oai](https://github.com/rhan-oai)
- #17761[#17761](https://github.com/openai/codex/pull/17761)Tighten realtime handoff finalization@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #17701[#17701](https://github.com/openai/codex/pull/17701)Add realtime output modality and transcript events@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #17777[#17777](https://github.com/openai/codex/pull/17777)nit: feature flag@jif-oai[@jif-oai](https://github.com/jif-oai)
- #17637[#17637](https://github.com/openai/codex/pull/17637)feat: add context percent to status line@jif-oai[@jif-oai](https://github.com/jif-oai)
- #17665[#17665](https://github.com/openai/codex/pull/17665)Always enable original image detail on supported models@fjord-oai[@fjord-oai](https://github.com/fjord-oai)
- #17374[#17374](https://github.com/openai/codex/pull/17374)[codex-analytics] add session source to client metadata@marksteinbrick-oai[@marksteinbrick-oai](https://github.com/marksteinbrick-oai)
- #17489[#17489](https://github.com/openai/codex/pull/17489)Moving updated-at timestamps to unique millisecond times@ddr-oai[@ddr-oai](https://github.com/ddr-oai)
- #17784[#17784](https://github.com/openai/codex/pull/17784)feat: codex sampler@jif-oai[@jif-oai](https://github.com/jif-oai)
- #17732[#17732](https://github.com/openai/codex/pull/17732)fix: Revert danger-full-access denylist-only mode@viyatb-oai[@viyatb-oai](https://github.com/viyatb-oai)
- #17234[#17234](https://github.com/openai/codex/pull/17234)Redirect debug client output to a file@rasmusrygaard[@rasmusrygaard](https://github.com/rasmusrygaard)
- #17803[#17803](https://github.com/openai/codex/pull/17803)Keep image_detail_original as a removed feature flag@fjord-oai[@fjord-oai](https://github.com/fjord-oai)
- #17372[#17372](https://github.com/openai/codex/pull/17372)app-server: prepare to run initialized rpcs concurrently@euroelessar[@euroelessar](https://github.com/euroelessar)
- #17704[#17704](https://github.com/openai/codex/pull/17704)Refactor Bazel CI job setup@bolinfest[@bolinfest](https://github.com/bolinfest)
- #17674[#17674](https://github.com/openai/codex/pull/17674)Route apply_patch through the environment filesystem@starr-openai[@starr-openai](https://github.com/starr-openai)
- #17702[#17702](https://github.com/openai/codex/pull/17702)Fix remote skill popup loading@starr-openai[@starr-openai](https://github.com/starr-openai)
- #17830[#17830](https://github.com/openai/codex/pull/17830)[codex] Fix app-server initialized request analytics build@etraut-openai[@etraut-openai](https://github.com/etraut-openai)
- #17389[#17389](https://github.com/openai/codex/pull/17389)[codex-analytics] enable general analytics by default@rhan-oai[@rhan-oai](https://github.com/rhan-oai)
- #17659[#17659](https://github.com/openai/codex/pull/17659)thread store interface@wiltzius-openai[@wiltzius-openai](https://github.com/wiltzius-openai)
- #17792[#17792](https://github.com/openai/codex/pull/17792)Spread AbsolutePathBuf@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #17808[#17808](https://github.com/openai/codex/pull/17808)fix: apply patch bin refresh@jif-oai[@jif-oai](https://github.com/jif-oai)
- #17838[#17838](https://github.com/openai/codex/pull/17838)Add realtime wire trace logs@aibrahim-oai[@aibrahim-oai](https://github.com/aibrahim-oai)
- #17684[#17684](https://github.com/openai/codex/pull/17684)Adjust default tool search result caps@malone-oai[@malone-oai](https://github.com/malone-oai)
- #17705[#17705](https://github.com/openai/codex/pull/17705)Add Bazel verify-release-build job@bolinfest[@bolinfest](https://github.com/bolinfest)
- #17720[#17720](https://github.com/openai/codex/pull/17720)Make skill loading filesystem-aware@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #17756[#17756](https://github.com/openai/codex/pull/17756)[codex] Support local marketplace sources@xli-oai[@xli-oai](https://github.com/xli-oai)
- #17846[#17846](https://github.com/openai/codex/pull/17846)Fix for Guardian CI Tests stack overflow, applying Box to reduce stack pressure@won-openai[@won-openai](https://github.com/won-openai)
- #17855[#17855](https://github.com/openai/codex/pull/17855)support plugins in external agent config migration@alexsong-oai[@alexsong-oai](https://github.com/alexsong-oai)
- #17872[#17872](https://github.com/openai/codex/pull/17872)Disable hooks in guardian review sessions@abhinav-oai[@abhinav-oai](https://github.com/abhinav-oai)
- #17868[#17868](https://github.com/openai/codex/pull/17868)Wrap delegated input text@guinness-oai[@guinness-oai](https://github.com/guinness-oai)
- #17884[#17884](https://github.com/openai/codex/pull/17884)Fix clippy warnings in external agent config migration@canvrno-oai[@canvrno-oai](https://github.com/canvrno-oai)
- #17837[#17837](https://github.com/openai/codex/pull/17837)Reuse remote exec-server in core tests@starr-openai[@starr-openai](https://github.com/starr-openai)
- #17859[#17859](https://github.com/openai/codex/pull/17859)sandbox: remove dead seatbelt helper and update tests@bolinfest[@bolinfest](https://github.com/bolinfest)
- #17870[#17870](https://github.com/openai/codex/pull/17870)fix: cleanup the contract of the general-purpose exec() function@bolinfest[@bolinfest](https://github.com/bolinfest)
- #17871[#17871](https://github.com/openai/codex/pull/17871)fix: add websocket capability token hash support@viyatb-oai[@viyatb-oai](https://github.com/viyatb-oai)
- #17763[#17763](https://github.com/openai/codex/pull/17763)Send sandbox state through MCP tool metadata@aaronl-openai[@aaronl-openai](https://github.com/aaronl-openai)
- #17654[#17654](https://github.com/openai/codex/pull/17654)Support Unix socket allowlists in macOS sandbox@aaronl-openai[@aaronl-openai](https://github.com/aaronl-openai)
- #17915[#17915](https://github.com/openai/codex/pull/17915)fix: cargo deny@jif-oai[@jif-oai](https://github.com/jif-oai)
- #17913[#17913](https://github.com/openai/codex/pull/17913)feat: add endpoint to delete memories@jif-oai[@jif-oai](https://github.com/jif-oai)
- #17844[#17844](https://github.com/openai/codex/pull/17844)feat: cleaning of memories extension@jif-oai[@jif-oai](https://github.com/jif-oai)
- #17921[#17921](https://github.com/openai/codex/pull/17921)chore: exp flag@jif-oai[@jif-oai](https://github.com/jif-oai)
- #17917[#17917](https://github.com/openai/codex/pull/17917)[codex] Fix current main CI blockers@sayan-oai[@sayan-oai](https://github.com/sayan-oai)
- #17919[#17919](https://github.com/openai/codex/pull/17919)chore: do not disable memories for past rollouts on reset@jif-oai[@jif-oai](https://github.com/jif-oai)
- #17924[#17924](https://github.com/openai/codex/pull/17924)nit: stable test@jif-oai[@jif-oai](https://github.com/jif-oai)
- #17632[#17632](https://github.com/openai/codex/pull/17632)feat: memories menu@jif-oai[@jif-oai](https://github.com/jif-oai)
- #17404[#17404](https://github.com/openai/codex/pull/17404)register all mcp tools with namespace@sayan-oai[@sayan-oai](https://github.com/sayan-oai)
- #17941[#17941](https://github.com/openai/codex/pull/17941)nit: doc@jif-oai[@jif-oai](https://github.com/jif-oai)
- #17938[#17938](https://github.com/openai/codex/pull/17938)feat: sanitize rollouts before phase 1@jif-oai[@jif-oai](https://github.com/jif-oai)
- #17937[#17937](https://github.com/openai/codex/pull/17937)feat: reset memories button@jif-oai[@jif-oai](https://github.com/jif-oai)
- #17883[#17883](https://github.com/openai/codex/pull/17883)Remove exec-server fs sandbox request preflight@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #17386[#17386](https://github.com/openai/codex/pull/17386)Register agent identities behind use_agent_identity@adrian-openai[@adrian-openai](https://github.com/adrian-openai)
- #17907[#17907](https://github.com/openai/codex/pull/17907)Fix fs/readDirectory to skip broken symlinks@willwang-openai[@willwang-openai](https://github.com/willwang-openai)
- #17960[#17960](https://github.com/openai/codex/pull/17960)chore(features) codex dependencies feat@dylan-hurd-oai[@dylan-hurd-oai](https://github.com/dylan-hurd-oai)
- #17965[#17965](https://github.com/openai/codex/pull/17965)fix: rename is_azure_responses_wire_base_url to is_azure_responses_provider@bolinfest[@bolinfest](https://github.com/bolinfest)
- #17946[#17946](https://github.com/openai/codex/pull/17946)Fix empty tool descriptions@shijie-oai[@shijie-oai](https://github.com/shijie-oai)
- #17824[#17824](https://github.com/openai/codex/pull/17824)[codex] Add local thread store listing@wiltzius-openai[@wiltzius-openai](https://github.com/wiltzius-openai)
- #17942[#17942](https://github.com/openai/codex/pull/17942)Add CLI update announcement@shijie-oai[@shijie-oai](https://github.com/shijie-oai)
- #17866[#17866](https://github.com/openai/codex/pull/17866)Refactor auth providers to mutate request headers@pakrym-oai[@pakrym-oai](https://github.com/pakrym-oai)
- #17902[#17902](https://github.com/openai/codex/pull/17902)app-server: track remote-control seq IDs per stream@euroelessar[@euroelessar](https://github.com/euroelessar)
- #17957[#17957](https://github.com/openai/codex/pull/17957)mcp: remove codex/sandbox-state custom request support@bolinfest[@bolinfest](https://github.com/bolinfest)
- #17953[#17953](https://github.com/openai/codex/pull/17953)fix: propagate log db@jif-oai[@jif-oai](https://github.com/jif-oai)
- #17920[#17920](https://github.com/openai/codex/pull/17920)chore(tui) cleanup@dylan-hurd-oai[@dylan-hurd-oai](https://github.com/dylan-hurd-oai)
- #17981[#17981](https://github.com/openai/codex/pull/17981)chore: tmp disable@jif-oai[@jif-oai](https://github.com/jif-oai)

Full release on Github[Full release on Github](https://github.com/openai/codex/releases/tag/rust-v0.121.0)
- 2026-04-12

### Codex app26.410

### New features

- Added command-menu file search, including`Cmd+P`routing into workspace file search.
- Added rich previews in the sidebar file viewer for images, PDFs, and Markdown.
- Added terminal tabs per thread, a selected-text Ask Codex overlay, and a Help menu feedback entry.

### Performance improvements and bug fixes

- Improved review diff whitespace handling and search highlighting.
- Fixed in-app browser address bar and external-open issues, plus several file viewer and side-panel bugs.
- Additional performance improvements and bug fixes.
- 2026-04-10

### Codex app26.409

### New features

- Added Windows Store updater support.
- Expanded pull request workflows with an activity timeline, PR-page commenting, and push choices in the push modal.
- Added workspace file tabs in the thread side panel, drag-and-drop tab reordering, run action editing, and a logout confirmation dialog.

### Performance improvements and bug fixes

- Improved pull request board performance and comment flyouts.
- Improved update and navigation resilience, and fixed projectless visibility, unread-state, and pinned-row edge cases.
- Additional performance improvements and bug fixes.
- 2026-04-09

### Codex app26.406

### New features

- Added collapsible inline review comments and inline or detached review modes.
- Added a Git summary and Sources section in the thread side panel.
- Added a New Quick Chat command and local video embeds in the app.

### Performance improvements and bug fixes

- Preserved thread scroll position per conversation and unread state across windows.
- Improved review refresh reliability, and fixed dictation loss, right-panel reset, and GitHub reconnect messaging.
- Additional performance improvements and bug fixes.
- 2026-04-07

### Codex model availability update

We’re updating model availability for users who sign in with ChatGPT. Starting April 7, the model picker no longer shows`gpt-5.2-codex`,`gpt-5.1-codex-mini`,`gpt-5.1-codex-max`,`gpt-5.1-codex`,`gpt-5.1`, or`gpt-5`. On April 14, we’ll remove those models from Codex for ChatGPT sign-in.

Users can still choose from`gpt-5.4`,`gpt-5.4-mini`,`gpt-5.3-codex`, and`gpt-5.2`. ChatGPT Pro users can also choose`gpt-5.3-codex-spark`.

To use another API-supported model in Codex, sign in with an API key or configure a model provider.
- 2026-04-01

### Codex app26.325, 26.331, 26.401

### New features

- Added workspace settings to the app.
- Added “Don’t ask again” handling and polish for custom MCP approval panels.
- Added native Windows updater support, including MSIX support, plus a Windows system tray menu so Codex can stay resident after the last window closes.
- Added app and file`@`mentions in the automation composer, surfaced subagent diff stats in the composer, and added artifact cards for generated file citations.
- Added a Quick Chat app-menu shortcut, a review file tree open menu, early heartbeat automation affordances in threads, and image support for remote connections.

### Performance improvements and bug fixes

- Fixed review panel scroll jumps and PR status actions while a conversation is still running.
- Fixed several multi-window issues, plus`@`-mention results, duplicate project labeling, Windows`runGit`behavior, and revert, unstage, and stage-all actions.
- Improved remote-thread and sidebar polish, Windows update recovery, unsupported-version guidance, and overall thread search speed.
- Fixed sticky review issues such as diff hunk expansion, header overlap, archive-thread crashes, and window-zoom shell sizing.
- Additional performance improvements and bug fixes.

## March 2026

- 2026-03-25

### Build and install plugins in Codex

Codex now supports**plugins**: installable bundles that package skills, app integrations, and MCP server configuration for reusable workflows.

Plugins are available in the Codex app, CLI, and IDE extensions.

You can install curated plugins from the plugin directory, or scaffold a local plugin with`@plugin-creator`and test it with workspace-scoped or home-scoped marketplaces.

Learn more in theplugins documentation[plugins documentation](/codex/plugins).

#### Plugin structure

Every plugin is a folder with a required`.codex-plugin/plugin.json`manifest and optional supporting files:
````my-plugin/.codex-plugin/plugin.json   # Required: plugin manifestskills/         # Optional: packaged skills.app.json       # Optional: app or connector mappings.mcp.json       # Optional: MCP server configurationassets/         # Optional: icons, logos, screenshots````

#### Install plugins per-user or per-repo

You can install plugins for just yourself with`~/.agents/plugins/marketplace.json`and`~/.codex/plugins/`, or for everyone on a project with`.agents/plugins/marketplace.json`and a repo-local plugin directory such as`./plugins/`.

#### Curated plugins and local development

Codex surfaces curated public plugins in the plugin directory. Codex also ships with the built-in`@plugin-creator`skill to help you scaffold a plugin, add a local marketplace entry, and test it before sharing it with teammates.
- 2026-03-25

### Codex app26.324

### New features

- Redesigned the skills and plugins browse and manage pages.
- Added per-window zoom and a clearer edited-files state in review.
- Added automation titles and icons in the sidebar, plus bundled Raycast themes.

### Performance improvements and bug fixes

- Kept loaded threads and projects visible during reconnects and made navigation feel faster.
- Fixed archive freezes, markdown wrapping, hotkey-window regressions, and several permissions, terminal, and worktree issues.
- Additional performance improvements and bug fixes.
- 2026-03-24

### Codex app26.323

### New features

- Added search for past Codex app threads, including a sidebar shortcut and keyboard shortcuts for jumping to recent threads.
- Added a one-click option to archive all local threads in a project.
- Synced key settings between the Codex app and the VS Code extension, and added a settings entry point in the extension.

### Performance improvements and bug fixes

- Additional performance improvements and bug fixes.
- 2026-03-20

### Codex app26.320

### New features

- Added Floating Composer v2.
- Added terminal shortcuts for jumping by word and line.
- Improved plugin discovery surfaces and file-path rendering for saved images.

### Performance improvements and bug fixes

- Fixed sidebar crashes when subagent turn items are missing.
- Fixed pop-out thread routing and preserved local paths for composer image attachments.
- Additional performance improvements and bug fixes.
- 2026-03-19

### Codex app26.318, 26.319

### New features

- Added skills to the`@`menu so you can insert them from the composer alongside other mentions.
- `Cmd/Ctrl+F`now starts with your current text selection, which makes searching reviews and diffs faster, alongside broader review navigation improvements such as a refreshed file tree and percentage-based file tree resizing.
- Added a branded loading shimmer while the app starts.

### Performance improvements and bug fixes

- Improved collapsed diff summaries in review.
- Fixed slash-command focus and composer alignment issues, and polished plugin cards and step details.
- Additional performance improvements and bug fixes.
- 2026-03-18

### Codex app26.317

### New features

- You can now fork a conversation from an earlier message, not just the latest turn.
- Added slash commands for switching models and reasoning levels, and made slash commands work in the middle of a draft prompt.
- Added notifications for plan mode questions so it’s easier to notice when Codex needs input.

### Performance improvements and bug fixes

- Fixed thread handoff and subagent navigation issues across worktrees and the VS Code extension.
- Additional performance improvements and bug fixes.
- 2026-03-17

### Introducing GPT-5.4 mini in Codex

GPT-5.4 mini is now available in Codex as a fast, efficient model for lighter coding tasks and subagents.

It improves over GPT-5 mini across coding, reasoning, image understanding, and tool use while running more than 2x faster. In Codex, GPT-5.4 mini uses 30% as much of your included limits as GPT-5.4, so comparable tasks can last about 3.3x longer before you hit those limits.

GPT-5.4 mini is available in the Codex app, the CLI, the IDE extension, and Codex on the web. GPT-5.4 mini is also available in the API.

Use GPT-5.4 mini for codebase exploration, large-file review, processing supporting documents, and other less reasoning-intensive subagent work. For more complex planning, coordination, and final judgment, start with GPT-5.4.

To switch to GPT-5.4 mini:

- In the CLI, start a new thread with:
````codex--modelgpt-5.4-mini````
Or use`/model`during a session.
- In the IDE extension, choose GPT-5.4 mini from the model selector in the composer.
- In the Codex app, choose GPT-5.4 mini from the model selector in the composer.

If you don’t see GPT-5.4 mini yet, update the CLI, IDE extension, or Codex app to the latest version.
- 2026-03-16

### Codex app26.313

### New features

- Added back and forward buttons in the header so you can move between recent screens more quickly.
- Added an**Open in Finder**,**Open in Explorer**, or**Open in File Manager**action from thread menus to jump straight to a thread’s project folder.

### Performance improvements and bug fixes

- Improved resume and thread error toasts with clearer details when something goes wrong.
- Additional performance improvements and bug fixes.
- 2026-03-12

### Codex app26.312

### Themes

Change the Codex app appearance in**Settings**by choosing a base theme, adjusting accent, background, and foreground colors, and changing the UI and code fonts. You can also share your custom theme with friends.[Codex app theme settings showing custom themes, color controls, and font settings](/images/codex/app/themes-side-by-side.webp)[Codex app theme settings showing custom themes, color controls, and font settings](/images/codex/app/themes-side-by-side.webp)[Codex app theme settings showing custom themes, color controls, and font settings](/images/codex/app/themes-side-by-side.webp)[Codex app theme settings showing custom themes, color controls, and font settings](/images/codex/app/themes-side-by-side.webp)

### Revamped Automations

You can now choose whether automations run locally or on a worktree, define custom reasoning levels and models, and use templates to find inspiration for new automations.[Automations settings showing local and worktree options alongside scheduling controls](/images/codex/app/codex-automations-light.webp)[Automations settings showing local and worktree options alongside scheduling controls](/images/codex/app/codex-automations-dark.webp)[Automations settings showing local and worktree options alongside scheduling controls](/images/codex/app/codex-automations-light.webp)[Automations settings showing local and worktree options alongside scheduling controls](/images/codex/app/codex-automations-dark.webp)

### Performance improvements and bug fixes

Various bug fixes and performance improvements.
- 2026-03-11

### Codex app26.311

### New features

- Codex can now read the integrated terminal for the current thread, so it can check the status of a running development server or refer back to failed build output while it works with you.

### Performance improvements and bug fixes

- Additional performance improvements and bug fixes.
- 2026-03-05

### Introducing GPT-5.4 in Codex

GPT-5.4 is now available in Codex as OpenAI’s most capable and efficient frontier model for professional work.

It combines recent advances in reasoning, coding, and agentic workflows in one model, and it’s the recommended choice for most Codex tasks.

In Codex, GPT-5.4 is the first general-purpose model with native computer-use capabilities. GPT-5.4 in Codex includes experimental support for the 1M context window. It supports complex workflows across applications and long-horizon tasks, with stronger tool use and tool search that help agents find and use the right tools more efficiently.

GPT-5.4 is available everywhere you can use Codex: the Codex app, the CLI, the IDE extension, and Codex Cloud on the web. GPT-5.4 is also available in the API.

To switch to GPT-5.4:

- In the CLI, start a new thread with:
````codex--modelgpt-5.4````
Or use`/model`during a session.
- In the IDE extension, choose GPT-5.4 from the model selector in the composer.
- In the Codex app, choose GPT-5.4 from the model selector in the composer.

If you don’t see GPT-5.4 yet, update the CLI, IDE extension, or Codex app to the latest version.
- 2026-03-05

### Codex app26.305

### Performance improvements and bug fixes

- Improved remote connections with clearer connection errors, better status updates, and clearer host labels in thread and settings views.
- Fixed copy and paste shortcuts in the integrated terminal on Windows.
- Fixed an issue where archived pinned threads could reappear in the sidebar.
- Fixed an issue where repeated`codex://new`links could stop prefilling a new conversation when the app was already open.
- Additional performance improvements and bug fixes.
- 2026-03-04

### Codex app26.304

#### Codex app for Windows[Codex app for Windows showing a project sidebar, active thread, and review pane](/images/codex/windows/codex-windows-light.webp)[Codex app for Windows showing a project sidebar, active thread, and review pane](/images/codex/windows/codex-windows-dark.webp)[Codex app for Windows showing a project sidebar, active thread, and review pane](/images/codex/windows/codex-windows-light.webp)[Codex app for Windows showing a project sidebar, active thread, and review pane](/images/codex/windows/codex-windows-dark.webp)

The Codex app is now available on Windows. The app gives you one interface for working across projects, running parallel agent threads, and reviewing results in one place.

The Codex app runs natively on Windows using PowerShell and a native Windows sandbox for bounded permissions, so you can use Codex on Windows without moving your workflow into WSL, onto a virtual machine, or by deactivating the sandbox.

The Windows app includes the same core features as the rest of the Codex app:

- Skills[Skills](/codex/app/features#skills-support)to discover and extend Codex capabilities.
- Automations[Automations](/codex/app/automations)to run work in the background.
- Worktrees[Worktrees](/codex/app/worktrees)to handle independent tasks in the same project.

If you prefer to develop in WSL, you can also switch the Codex agent and the integrated terminal to run there.

Download it from theMicrosoft Store[Microsoft Store](https://get.microsoft.com/installer/download/9PLM9XGG6VKS?cid=website_cta_psi)and sign in with your ChatGPT account or an API key. For setup and configuration details, seeSetup[Setup](/codex/app/windows#setup),Use WSL with the Codex app[Use WSL with the
Codex app](/codex/app/windows#use-wsl-with-the-codex-app), andCustomize the app for your development setup[Customize the
app for your development setup](/codex/app/windows#customize-the-app-for-your-development-setup).
- 2026-03-03

### Codex app26.303

### New features

- Added a Worktrees setting to turn automatic cleanup of Codex-managed worktrees on or off.
- Added Handoff support for moving a thread between Local andWorktree[Worktree](/codex/app/worktrees).
- Added an explicit English option in the language menu.

### Performance improvements and bug fixes

- Improved GitHub and pull request workflows.
- Improved approval prompts and app connection sign-in flows.
- Additional performance improvements and bug fixes.

## February 2026

- 2026-02-28

### Codex app26.228

### Performance improvements and bug fixes

- Fixed a regression where conversation and task views could stop updating while Codex was streaming a response.
- Additional performance improvements and bug fixes.
- 2026-02-27

### Codex app26.227

### New features

- Added pull request status badges in task rows and PR buttons, including draft, open, merged, and closed states.
- Added a Worktrees setting to choose how many Codex-managed worktrees to keep before older ones are cleaned up.

### Performance improvements and bug fixes

- Improved scrolling and navigation in long conversations and code review, including fixes for thread jumpiness, sidebar jitter, and diff scrolling.
- Improved app startup reliability and keyboard zoom behavior.
- Additional performance improvements and bug fixes.
- 2026-02-26

### Codex app26.226

### New features

- Added new MCP shortcuts in the composer, including install keyword suggestions and an MCP server submenu in**Add context**.
- Added support for`@mentions`and skill mentions in inline review comments.

### Performance improvements and bug fixes

- Improved rendering of MCP tool calls and Mermaid diagram error handling.
- Fixed an issue where stopped terminal commands could continue appearing as running.
- Additional performance improvements and bug fixes.
- 2026-02-17

### Codex app26.217

### New features

- Added drag-and-drop support to reorder queued messages.
- Added a warning when the selected model is downgraded.

### Improvements and bug fixes

- Improved file workflows with fuzzy file search and better attachment recovery after restart.
- Additional performance improvements and bug fixes.
- 2026-02-12

### Introducing GPT-5.3-Codex-Spark

Today, we’re releasing a research preview of GPT-5.3-Codex-Spark[Today, we’re releasing a research preview of GPT-5.3-Codex-Spark](https://openai.com/index/introducing-gpt-5-3-codex-spark/), a smaller version of GPT-5.3-Codex and our first model designed for real-time coding. Codex-Spark is optimized to feel near-instant, delivering more than 1000 tokens per second while remaining highly capable for real-world coding tasks.

Codex-Spark is available in research preview for ChatGPT Pro users in the latest Codex app, CLI, and IDE extension. This release also marks the first milestone in our partnership with Cerebras.

At launch, Codex-Spark is text-only with a 128k context window. During the research preview, usage has separate model-specific limits and doesn’t count against standard Codex limits. During high demand, access may slow down or queue while we balance reliability across users.

To switch to GPT-5.3-Codex-Spark:

- In the CLI, start a new thread with:
````codex--modelgpt-5.3-codex-spark````
Or use`/model`during a session.
- In the IDE extension, choose GPT-5.3-Codex-Spark from the model selector in the composer.
- In the Codex app, choose GPT-5.3-Codex-Spark from the model selector in the composer.

If you don’t see GPT-5.3-Codex-Spark yet, update the CLI, IDE extension, or Codex app to the latest version.

GPT-5.3-Codex-Spark isn’t available in the API at launch. For API-key workflows, continue using`gpt-5.2-codex`.
- 2026-02-12

### Codex app26.212

### New features

- Support for GPT-5.3-Codex-Spark
- Added conversation forking
- Addedfloating pop-out window[floating pop-out window](/codex/app/features#floating-pop-out-window)to take a conversation with you

### Bug fixes

- Improved performance and bug fixes

Alpha testing for the Codex app on Windows is also starting.Sign up here[Sign up here](https://openai.com/form/codex-app/)to be a potential alpha tester.
- 2026-02-10

### Codex app26.210

### New features

- Added branch search in the branch picker.
- Added clearer guidance for entering plan mode when you type`plan`in the composer.
- Added support for parallel approvals.

### Improvements and bug fixes

- Additional performance improvements and bug fixes.
- 2026-02-09

### GPT-5.3-Codex in Cursor and VS Code

Starting today, GPT-5.3-Codex is available natively in Cursor and VS Code.

API access is starting with a small set of customers as part of a phased release.

This is the first model treated as a high security capability under the Preparedness Framework.

Safety controls will continue to scale, and API access will expand over the next few weeks.
- 2026-02-08

### Codex app26.208

### New features

- Added MCP and personality actions to the command palette.
- Updated follow-up behavior to queue by default.

### Improvements and bug fixes

- Additional performance improvements and bug fixes.
- 2026-02-06

### Codex app26.206

### New features

- Added a file-reference action to reveal files directly in your OS file manager.

### Improvements and bug fixes

- Improved handling of large reviews by removing the overall diff-size cap in the review pane.
- Additional performance improvements and bug fixes.
- 2026-02-05

### Introducing GPT-5.3-Codex

Today we’re releasing GPT-5.3-Codex[Today we’re releasing GPT-5.3-Codex](https://openai.com/index/introducing-gpt-5-3-codex/), the most capable agentic coding model to date for complex, real-world software engineering.

GPT-5.3-Codex combines the frontier coding performance of GPT-5.2-Codex with stronger reasoning and professional knowledge capabilities, and runs 25% faster for Codex users. It’s also better at collaboration while the agent is working—delivering more frequent progress updates and responding to steering in real time.

GPT-5.3-Codex is available with paid ChatGPT plans everywhere you can use Codex: the Codex app, the CLI, the IDE extension, and Codex Cloud on the web. API access for the model will come soon.

To switch to GPT-5.3-Codex:

- In the CLI, start a new thread with:
````codex--modelgpt-5.3-codex````
Or use`/model`during a session.
- In the IDE extension, make sure you are signed in with ChatGPT, then choose GPT-5.3-Codex from the model selector in the composer.
- In the Codex app, make sure you are signed in with ChatGPT, then choose GPT-5.3-Codex from the model selector in the composer.
- If you don’t see GPT-5.3-Codex, update the CLI, IDE extension, or Codex app to the latest version.

For API-key workflows, continue using`gpt-5.2-codex`while API support rolls out.
- 2026-02-05

### Codex app26.205

### New features

- Support for**GPT-5.3-Codex[GPT-5.3-Codex](https://openai.com/index/introducing-gpt-5-3-codex/)**.
- Added mid-turn steering. Submit a message while Codex is working to direct its behavior.
- Attach or drop any file type.

### Bug fixes

- Fix flickering of the app.
- 2026-02-04

### Codex app26.204

### New features

- Added**Zed**and**Textmate**as options to open files and folders.
- Added PDF preview in the review panel.

### Bug fixes

- Performance improvements.
- 2026-02-03

### Codex app26.203

### New features

- Added thread renaming on double-click in the thread list.

### Improvements and bug fixes

- Renamed**Sync**to**Handoff**and added clearer source/destination stats in the handoff UI.
- Additional performance improvements and bug fixes.
- 2026-02-02

### Introducing the Codex app

#### Codex app[Codex app showing a project sidebar, thread list, and review pane](/images/codex/app/codex-app-basic-light.webp)[Codex app showing a project sidebar, thread list, and review pane](/images/codex/app/codex-app-basic-dark.webp)[Codex app showing a project sidebar, thread list, and review pane](/images/codex/app/codex-app-basic-light.webp)[Codex app showing a project sidebar, thread list, and review pane](/images/codex/app/codex-app-basic-dark.webp)

The Codex app for macOS is a desktop interface for running agent threads in parallel and collaborating with agents on long-running tasks. It includes a project sidebar, thread list, and review pane for tracking work across projects.

Key features:

- Multitask across projects[Multitask across projects](/codex/app/features#multitask-across-projects)
- Built-in worktree support[Built-in worktree support](/codex/app/worktrees)
- Voice dictation[Voice dictation](/codex/app/features#voice-dictation)
- Built-in Git tooling[Built-in Git tooling](/codex/app/features#built-in-git-tools)
- Skills[Skills](/codex/app/features#skills-support)
- Automations[Automations](/codex/app/automations)

For a limited time,**ChatGPT Free and Go include Codex**, and**Plus, Pro, Business, Enterprise, and Edu**plans get**double rate limits**. Those higher limits apply in the app, the CLI, your IDE, and the cloud.

Learn more in theIntroducing the Codex app[Introducing the Codex app](https://openai.com/index/introducing-the-codex-app/)blog post.

Check out theCodex app documentation[Codex app documentation](/codex/app)for more.Get started with the Codex app[Get started with the Codex app](https://persistent.oaistatic.com/codex-app-prod/Codex.dmg)

## January 2026

- 2026-01-28

### Web search is now enabled by default

Codex now enables web search for local tasks in the Codex CLI and IDE Extension. By default, Codex uses a web search cache, which is an OpenAI-maintained index of web results. Cached mode returns pre-indexed results instead of fetching live pages, while live mode fetches the most recent data from the web. If you are using`--yolo`or anotherfull access sandbox setting[full access sandbox setting](/codex/agent-approvals-security), web search defaults to live results. To disable this behavior or switch modes, use the`web_search`configuration option:

- `web_search = "cached"`(default; serves results from the web search cache)
- `web_search = "live"`(fetches the most recent data from the web; same as`--search`)
- `web_search = "disabled"`to remove the tool

To learn more, check out theconfiguration documentation[configuration documentation](/codex/config-basic).
- 2026-01-23

### Team Config for shared configuration

Team Config groups the files teams use to standardize Codex across repositories and machines. Use it to share:

- `config.toml`defaults
- `rules/`for command controls outside the sandbox
- `skills/`for reusable workflows

Codex loads these layers from`.codex/`folders in the current working directory, parent folders, and the repo root, plus user (`~/.codex/`) and system (`/etc/codex/`) locations. Higher-precedence locations override lower-precedence ones.

Admins can still enforce constraints with`requirements.toml`, which overrides defaults regardless of location.

Learn more inTeam Config[Team Config](/codex/enterprise/admin-setup#team-config).
- 2026-01-22

### Custom prompts deprecated

Custom prompts are now deprecated. Useskills[skills](/codex/skills)for reusable instructions and workflows instead.
- 2026-01-14

### GPT-5.2-Codex API availability

GPT-5.2-Codex is now available in the API and for users who sign into Codex with the API.

To learn more about using GPT-5.2-Codex check out ourAPI documentation[API documentation](https://platform.openai.com/docs/models/gpt-5.2-codex).

## December 2025

- 2025-12-19

### Agent skills in Codex

Codex now supports**agent skills**: reusable bundles of instructions (plus optional scripts and resources) that help Codex reliably complete specific tasks.

Skills are available in both the Codex CLI and IDE extensions.

You can invoke a skill explicitly by typing`$skill-name`(for example,`$skill-installer`or the experimental`$create-plan`skill after installing it), or let Codex select a skill automatically based on your prompt.

Learn more in theskills documentation[skills documentation](/codex/skills).

#### Folder-based standard (agentskills.io)

Following the openagent skills specification[agent skills specification](https://agentskills.io/specification), a skill is a folder with a required`SKILL.md`and optional supporting files:
````my-skill/SKILL.md       # Required: instructions + metadatascripts/       # Optional: executable codereferences/    # Optional: documentationassets/        # Optional: templates, resources````

#### Install skills per-user or per-repo

You can install skills for just yourself in`~/.codex/skills`, or for everyone on a project by checking them into`.codex/skills`in the repository.

Codex also ships with a few built-in system skills to get started, including`$skill-creator`and`$skill-installer`. The`$create-plan`skill is experimental and needs to be installed (for example:`$skill-installer install the create-plan skill from the .experimental folder`).

#### Curated skills directory

Codex ships with asmall curated set of skills[small curated set of skills](https://github.com/openai/skills)inspired by popular workflows at OpenAI. Install them with`$skill-installer`, and expect more over time.
- 2025-12-18

### Introducing GPT-5.2-Codex

Today we are releasing GPT-5.2-Codex[Today we are releasing GPT-5.2-Codex](https://openai.com/index/gpt-5-2-codex), the most advanced agentic coding model yet for complex, real-world software engineering.

GPT-5.2-Codex is a version ofGPT-5.2[GPT-5.2](https://openai.com/index/introducing-gpt-5-2/)further optimized for agentic coding in Codex, including improvements on long-horizon work through context compaction, stronger performance on large code changes like refactors and migrations, improved performance in Windows environments, and significantly stronger cybersecurity capabilities.

Starting today, the CLI and IDE Extension will default to`gpt-5.2-codex`for users who are signed in with ChatGPT. API access for the model will come soon.

If you have a model specified in your`config.toml`configuration file[config.tomlconfiguration file](/codex/local-config), you can instead try out`gpt-5.2-codex`for a new Codex CLI session using:
````codex--modelgpt-5.2-codex````

You can also use the`/model`slash command in the CLI. In the Codex IDE Extension you can select GPT-5.2-Codex from the dropdown menu.

If you want to switch for all sessions, you can change your default model to`gpt-5.2-codex`by updating your`config.toml`configuration file[configuration file](/codex/local-config):
````model ="gpt-5.2-codex”````

- 2025-12-04

### Introducing Codex for Linear

Assign or mention @Codex in an issue to kick-off a Codex cloud task. As Codex works, it posts updates back to Linear, providing a link to the completed task so you can review, open a PR, or keep working.

[Screenshot of a successful Codex task started in Linear](/images/codex/integrations/linear-codex-example.png)

To learn more about how to connect Codex to Linear both locally through MCP and through the new integration, check out theCodex for Linear documentation[Codex for Linear documentation](/codex/integrations/linear).

## November 2025

- 2025-11-24

### Usage and credits fixes

Minor updates to address a few issues with Codex usage and credits:

- Adjusted all usage dashboards to show “limits remaining” for consistency. The CLI previously displayed “limits used.”
- Fixed an issue preventing users from buying credits if their ChatGPT subscription was purchased via iOS or Google Play.
- Fixed an issue where the CLI could display stale usage information; it now refreshes without needing to send a message first.
- Optimized the backend to help smooth out usage throughout the day, irrespective of overall Codex load or how traffic is routed. Before, users could get unlucky and hit a few cache misses in a row, leading to much less usage.
- 2025-11-18

### Introducing GPT-5.1-Codex-Max

Today we are releasing GPT-5.1-Codex-Max[Today we are releasing GPT-5.1-Codex-Max](https://openai.com/index/gpt-5-1-codex-max), our new frontier agentic coding model.

GPT‑5.1-Codex-Max is built on an update to our foundational reasoning model, which is trained on agentic tasks across software engineering, math, research, and more. GPT‑5.1-Codex-Max is faster, more intelligent, and more token-efficient at every stage of the development cycle–and a new step towards becoming a reliable coding partner.

Starting today, the CLI and IDE Extension will default to`gpt-5.1-codex-max`for users that are signed in with ChatGPT. API access for the model will come soon.

For non-latency-sensitive tasks, we’ve also added a new Extra High (`xhigh`) reasoning effort, which lets the model think for an even longer period of time for a better answer. We still recommend medium as your daily driver for most tasks.

If you have a model specified in your`config.toml`configuration file[config.tomlconfiguration file](/codex/local-config), you can instead try out`gpt-5.1-codex-max`for a new Codex CLI session using:
````codex--modelgpt-5.1-codex-max````

You can also use the`/model`slash command in the CLI. In the Codex IDE Extension you can select GPT-5.1-Codex from the dropdown menu.

If you want to switch for all sessions, you can change your default model to`gpt-5.1-codex-max`by updating your`config.toml`configuration file[configuration file](/codex/local-config):
````model ="gpt-5.1-codex-max”````

- 2025-11-13

### Introducing GPT-5.1-Codex and GPT-5.1-Codex-Mini

Along with theGPT-5.1 launch in the API[GPT-5.1 launch in the API](https://openai.com/index/gpt-5-1-for-developers/), we are introducing new`gpt-5.1-codex-mini`and`gpt-5.1-codex`model options in Codex, a version of GPT-5.1 optimized for long-running, agentic coding tasks and use in coding agent harnesses in Codex or Codex-like harnesses.

Starting today, the CLI and IDE Extension will default to`gpt-5.1-codex`on macOS and Linux and`gpt-5.1`on Windows.

If you have a model specified in your`config.toml`configuration file[config.tomlconfiguration file](/codex/local-config), you can instead try out`gpt-5.1-codex`for a new Codex CLI session using:
````codex--modelgpt-5.1-codex````

You can also use the`/model`slash command in the CLI. In the Codex IDE Extension you can select GPT-5.1-Codex from the dropdown menu.

If you want to switch for all sessions, you can change your default model to`gpt-5.1-codex`by updating your`config.toml`configuration file[configuration file](/codex/local-config):
````model ="gpt-5.1-codex”````

- 2025-11-07

### Introducing GPT-5-Codex-Mini

Today we are introducing a new`gpt-5-codex-mini`model option to Codex CLI and the IDE Extension. The model is a smaller, more cost-effective, but less capable version of`gpt-5-codex`that provides approximately 4x more usage as part of your ChatGPT subscription.

Starting today, the CLI and IDE Extension will automatically suggest switching to`gpt-5-codex-mini`when you reach 90% of your 5-hour usage limit, to help you work longer without interruptions.

You can try the model for a new Codex CLI session using:
````codex--modelgpt-5-codex-mini````

You can also use the`/model`slash command in the CLI. In the Codex IDE Extension you can select GPT-5-Codex-Mini from the dropdown menu.

Alternatively, you can change your default model to`gpt-5-codex-mini`by updating your`config.toml`configuration file[configuration file](/codex/local-config):
````model ="gpt-5-codex-mini”````

- 2025-11-06

### GPT-5-Codex model update

We’ve shipped a minor update to GPT-5-Codex:

- More reliable file edits with`apply_patch`.
- Fewer destructive actions such as`git reset`.
- More collaborative behavior when encountering user edits in files.
- 3% more efficient in time and usage.

## October 2025

- 2025-10-30

### Credits on ChatGPT Pro and Plus

Codex users on ChatGPT Plus and Pro can now use on-demand credits for more Codex usage beyond what’s included in your plan.Learn more.[Learn more.](/codex/pricing)
- 2025-10-22

### Tag @Codex on GitHub Issues and PRs

You can now tag`@codex`on a teammate’s pull request to ask clarifying questions, request a follow-up, or ask Codex to make changes. GitHub Issues now also support`@codex`mentions, so you can kick off tasks from any issue, without leaving your workflow.

[Codex responding to a GitHub pull request and issue after an @Codex mention.](/images/codex/integrations/github-example.png)
- 2025-10-06

### Codex is now GA

Codex is now generally available with 3 new features — @Codex in Slack, Codex SDK, and new admin tools.

#### @Codex in Slack

You can now questions and assign tasks to Codex directly from Slack. See theSlack guide[Slack guide](/codex/integrations/slack)to get started.

#### Codex SDK

Integrate the same agent that powers the Codex CLI inside your own tools and workflows with the Codex SDK in Typescript. With the new Codex GitHub Action, you can easily add Codex to CI/CD workflows. See theCodex SDK guide[Codex SDK guide](/codex/sdk)to get started.
````import{ Codex }from"@openai/codex-sdk";constagent=newCodex();constthread=awaitagent.startThread();constresult=awaitthread.run("Explore this repo");console.log(result);constresult2=awaitthread.run("Propose changes");console.log(result2);````

#### New admin controls and analytics

ChatGPT workspace admins can now edit or delete Codex Cloud environments. With managed config files, they can set safe defaults for CLI and IDE usage and monitor how Codex uses commands locally. New analytics dashboards help you track Codex usage and code review feedback. Learn more in theenterprise admin guide.[enterprise admin guide.](/codex/enterprise/admin-setup)

#### Availability and pricing updates

The Slack integration and Codex SDK are available to developers on ChatGPT Plus, Pro, Business, Edu, and Enterprise plans starting today, while the new admin features will be available to Business, Edu, and Enterprise. Beginning October 20, Codex Cloud tasks will count toward your Codex usage. Review theCodex pricing guide[Codex pricing guide](/codex/pricing)for plan-specific details.

## September 2025

- 2025-09-23

### GPT-5-Codex in the API

GPT-5-Codex is now available in the Responses API, and you can also use it with your API Key in the Codex CLI. We plan on regularly updating this model snapshot. It is available at the same price as GPT-5. You can learn more about pricing and rate limits for this model on ourmodel page[model page](https://platform.openai.com/docs/models/gpt-5-codex).
- 2025-09-15

### Introducing GPT-5-Codex

#### New model: GPT-5-Codex

[codex-switch-model](https://cdn.openai.com/devhub/docs/codex-switch-model.png)

GPT-5-Codex is a version of GPT-5 further optimized for agentic coding in Codex. It’s available in the IDE extension and CLI when you sign in with your ChatGPT account. It also powers the cloud agent and Code Review in GitHub.

To learn more about GPT-5-Codex and how it performs compared to GPT-5 on software engineering tasks, see ourannouncement blog post[announcement blog post](https://openai.com/index/introducing-upgrades-to-codex/).

#### Image outputs

[codex-image-outputs](https://cdn.openai.com/devhub/docs/codex-image-output.png)

When working in the cloud on front-end engineering tasks, GPT-5-Codex can now display screenshots of the UI in Codex web for you to review. With image output, you can iterate on the design without needing to check out the branch locally.

#### New in Codex CLI

- You can now resume sessions where you left off with`codex resume`.
- Context compaction automatically summarizes the session as it approaches the context window limit.

Learn more in thelatest release notes[latest release notes](https://github.com/openai/codex/releases/tag/rust-v0.36.0)

## August 2025

- 2025-08-27

### Late August update

#### IDE extension (Compatible with VS Code, Cursor, Windsurf)

Codex now runs in your IDE with an interactive UI for fast local iteration. Easily switch between modes and reasoning efforts.

#### Sign in with ChatGPT (IDE & CLI)

One-click authentication that removes API keys and uses ChatGPT Enterprise credits.

#### Move work between local ↔ cloud

Hand off tasks to Codex web from the IDE with the ability to apply changes locally so you can delegate jobs without leaving your editor.

#### Code Reviews

Codex goes beyond static analysis. It checks a PR against its intent, reasons across the codebase and dependencies, and can run code to validate the behavior of changes.
- 2025-08-21

### Mid August update

#### Image inputs

You can now attach images to your prompts in Codex web. This is great for asking Codex to implement frontend changes or follow up on whiteboarding sessions.

#### Container caching

Codex now caches containers to start new tasks and followups 90% faster, dropping the median start time from 48 seconds to 5 seconds. You can optionally configure a maintenance script to update the environment from its cached state to prepare for new tasks. See the docs for more.

#### Automatic environment setup

Now, environments without manual setup scripts automatically run the standard installation commands for common package managers like yarn, pnpm, npm, go mod, gradle, pip, poetry, uv, and cargo. This reduces test failures for new environments by 40%.

## June 2025

- 2025-06-13

### Best of N

Codex can now generate multiple responses simultaneously for a single task, helping you quickly explore possible solutions to pick the best approach.

#### Fixes & improvements

- 

Added some keyboard shortcuts and a page to explore them. Open it by pressing ⌘-/ on macOS and Ctrl+/ on other platforms.
- 

Added a “branch” query parameter in addition to the existing “environment”, “prompt” and “tab=archived” parameters.
- 

Added a loading indicator when downloading a repo during container setup.
- 

Added support for cancelling tasks.
- 

Fixed issues causing tasks to fail during setup.
- 

Fixed issues running followups in environments where the setup script changes files that are gitignored.
- 

Improved how the agent understands and reacts to network access restrictions.
- 

Increased the update rate of text describing what Codex is doing.
- 

Increased the limit for setup script duration to 20 minutes for Pro and Business users.
- 

Polished code diffs: You can now option-click a code diff header to expand/collapse all of them.
- 2025-06-03

### June update

#### Agent internet access

Now you can give Codex access to the internet during task execution to install dependencies, upgrade packages, run tests that need external resources, and more.

Internet access is off by default. Plus, Pro, and Business users can enable it for specific environments, with granular control of which domains and HTTP methods Codex can access. Internet access for Enterprise users is coming soon.

Learn more about usage and risks in thedocs[docs](/codex/cloud/agent-internet).

#### Update existing PRs

Now you can update existing pull requests when following up on a task.

#### Voice dictation

Now you can dictate tasks to Codex.

#### Fixes & improvements

- 

Added a link to this changelog from the profile menu.
- 

Added support for binary files: When applying patches, all file operations are supported. When using PRs, only deleting or renaming binary files is supported for now.
- 

Fixed an issue on iOS where follow up tasks where shown duplicated in the task list.
- 

Fixed an issue on iOS where pull request statuses were out of date.
- 

Fixed an issue with follow ups where the environments were incorrectly started with the state from the first turn, rather than the most recent state.
- 

Fixed internationalization of task events and logs.
- 

Improved error messages for setup scripts.
- 

Increased the limit on task diffs from 1 MB to 5 MB.
- 

Increased the limit for setup script duration from 5 to 10 minutes.
- 

Polished GitHub connection flow.
- 

Re-enabled Live Activities on iOS after resolving an issue with missed notifications.
- 

Removed the mandatory two-factor authentication requirement for users using SSO or social logins.

## May 2025

- 2025-05-22

### Reworked environment page

It’s now easier and faster to set up code execution.

#### Fixes & improvements

- 

Added a button to retry failed tasks
- 

Added indicators to show that the agent runs without network access after setup
- 

Added options to copy git patches after pushing a PR
- 

Added support for unicode branch names
- 

Fixed a bug where secrets were not piped to the setup script
- 

Fixed creating branches when there’s a branch name conflict.
- 

Fixed rendering diffs with multi-character emojis.
- 

Improved error messages when starting tasks, running setup scripts, pushing PRs, or disconnected from GitHub to be more specific and indicate how to resolve the error.
- 

Improved onboarding for teams.
- 

Polished how new tasks look while loading.
- 

Polished the followup composer.
- 

Reduced GitHub disconnects by 90%.
- 

Reduced PR creation latency by 35%.
- 

Reduced tool call latency by 50%.
- 

Reduced task completion latency by 20%.
- 

Started setting page titles to task names so Codex tabs are easier to tell apart.
- 

Tweaked the system prompt so that agent knows it’s working without network, and can suggest that the user set up dependencies.
- 

Updated the docs.
- 2025-05-19

### Codex in the ChatGPT iOS app

Start tasks, view diffs, and push PRs—while you’re away from your desk.