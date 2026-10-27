# Implementation map — research still in progress

This is the builder entry point for the eight-hour campaign. It preserves the
requested Lessons, Workshop, Mods and Favorites organization and separate
lesson → Bronze–Supersonic Legend selection. Reports describe an isolated source
snapshot, not necessarily the current installed plugin; reconcile
[source identity](source-provenance.json) before implementation.

## Player-facing work and its evidence

| Requested behavior | Research established so far | Integration starting point | Next proof needed |
| --- | --- | --- | --- |
| Stock-style training browser | Stock composition, tabs, legend and resize behavior are documented; some stock row/detail class bodies are absent. | [NATIVEUI-01](campaign/nativeui-01.md), native authored menus and NativeCareerLayout | Controller/mouse selection, async refresh, bounds, empty/error states and aspect-ratio checks in the actual movie. |
| Separate rank menu for every lesson | Isolated source offers the separate eight-choice menu for Power Shots; seven lessons lack rank profiles. | [CURRICULUM-01](campaign/curriculum-01.md), catalog, scenario_setup, bridge and NativeCareerLayout | Real setup and criteria for every one of 64 lesson-tier combinations; menu labels alone do not implement ranks. |
| Preserve lesson content and choose exact skills | Existing eight lessons have distinct event contracts; twelve ranked situations currently belong only to Power Shots. | [OUTCOMES-01](campaign/outcomes-01.md), training engine/catalog | Qualifying attempt and near miss for each declared skill/profile; separate target completion from mechanic mastery. |
| Shot setup, ready/go and retry | Whole-actor reset, settled setup, authored feeds and rank pressure are traced. | [PHYSICS-01](campaign/physics-01.md), engine, scenarios, game_worker | Observed car/ball/opponent starting state and timing; request acknowledgement alone is insufficient. |
| Top-left lesson/progress information | Native layout primitives are known; the actual gameplay HUD parent/safe area is not established by menu exports. | [NATIVEUI-01](campaign/nativeui-01.md), [initial native research](initial%20findings/native-training-research.txt) | Locate gameplay HUD anchors, then verify text fit, scaling and timer/progress identity in-game. |
| Timer and ball disappearance | SDK symbols exist; the isolated observer can collect timing/visibility fields. Field names do not establish native shot-clock or fade causality. | [SDK-01](campaign/sdk-01.md), [native clocks](initial%20findings/native-clock-research.txt), [lifecycle research](initial%20findings/shot-lifecycle-rea-wave2.txt) | Correlated shot start, timer expiry, ball flags and actual visible disappearance on the exact built artifact. |
| Native packs, progress and history | Static catalog/favorites work in the app model; current play remains unavailable offline. Stock progress/history and candidate SDK APIs are documented. | [PACK-01](campaign/pack-01.md), training/packs, native_packs, NativeTrainingPackHost | Supported exact-code load followed by shot progression, re-entry and explicit reset. Do not replace unavailable packs with a different drill. |
| Workshop maps | Exact package selection, hashing, pinning and dispatch exist; command return does not prove selected-map arrival. | [MAP-01](campaign/map-01.md), NativeWorkshopLauncher and WorkshopLoadPlan | Request-correlated map identity, dependencies, playable arrival, Pause and Return. |
| Favorites | App-owned stable identities are separate from the game's pack favorites/history. | [Browser identity](initial%20findings/browser-identity-research.txt), [PACK-01](campaign/pack-01.md), bridge/storage | Reopen/remove, missing source, changed title, duplicate identity and exact destination across all four tabs. |
| Download mods | Bounded validated download/cache path is separate from installation, enabling or compatibility. | [DOWNLOAD-01](campaign/download-01.md), community_plugins | Progress, cancellation, failure/retry and cache identity; each activated plugin needs its own verified adapter. |
| Training-first settings with checkboxes | Training preferences, eligibility, pending states and Controller Overlay Pro ownership/restoration are traced. | [SETTINGS-01](campaign/settings-01.md), NativeMatchLayout, ControllerOverlaySession | Toggle → actual effect → saved preference → Return/failure restoration, including user edits while active. |
| Controller information | Recorded logical actions, named-key polling and external overlay data are distinct sources. | [CAMERA-01](campaign/camera-01.md), TrainingLessonInput, training/controller | Prompts match actual owned binds; physical and logical input are labeled correctly; stock remaps remain usable. |
| Ghost car and demonstrations | Recording contains more than current car-only replay displays; validated teaching references are distinct from personal attempts. | [GHOST-01](campaign/ghost-01.md), coach, recordings | Exact profile compatibility, synchronized evidence and honest provenance; ball playback is not established by recording ball samples alone. |
| Garage and cosmetics | Catalog, owned inventory, draft selection and applied local appearance are different states. | [GARAGE-01](campaign/garage-01.md), garage/catalog adapter | Exact product/paint identity, visible preview/apply and restoration. Catalog enumeration does not grant ownership or online visibility. |
| Save and recovery | Per-file atomic writes and acknowledgement gates are traced; successful-path tests pass. Multi-file and lost-ack recovery still need explicit evidence. | [PERSIST-01](campaign/persist-01.md), [focused test run](campaign/persist-test-01.md) | Failed recording/document write, duplicate event, lost acknowledgement, retention and visible recovery. |

## Dependencies before broad implementation

1. Bind observations to exact source, built plugin, staged runtime, game and SDK
   identities. [COMPAT-01](campaign/compat-01.md) explains the unresolved current
   host/game compatibility context. [SDK-02](campaign/sdk-02.md) proves a narrower
   installed import/export-name match only.
2. Define versioned lesson profiles and outcome criteria before generalizing the
   rank UI. Keep the existing lesson choices and allow direct selection of the
   requested tier; no new prerequisite locks are implied by this research.
3. Separate requested, prepared, active, observed-success and durably-saved
   states. A returned command, checkbox or selected item is not evidence that a
   feature took effect in the game.
4. Implement the training display and native controls against those states.
   Preserve player-owned camera, bindings, saves and plugin settings, including
   conflicts caused by a player's later edits.
5. Add each external feature through its own tested adapter. Do not turn a
   successful generic download into a claim that every downloaded plugin works.

## Builder and test handoff

Luna workers research and execute selected existing tests. Separate DeepSeek
workers build and review scoped code. Keep implementation isolated from the
other chat's active checkout/game session. Heavy native compilation and game
input are still deferred while live physics/cadence ownership is unresolved.

Every future game acceptance record should identify the exact feature/profile,
preconditions, input, visible result, durable state and failure/Return behavior.
Retain source and artifact hashes with that record. Existing test totals may
overlap; report each invocation without adding them into a fabricated unique
total. The campaign's [task board](TASKS.md) tracks remaining research, and this
map will be updated as new evidence arrives.

## Additional evidence ready for builders

- [Native getter bodies](campaign/sdk-03.md) distinguish field access from timer/ball lifecycle logic; [shipped defaults](campaign/native-config-01.md) identify stock training action names without claiming effective user bindings.
- [Map-to-lesson fit](campaign/content-01.md) separates standalone Workshop courses from authored lesson geometry. Hidden Steam status notices are not evidence of a removed map.
- [Paired ghost playback](campaign/ghost-02.md) specifies one clock and gap policy for the car, ball and input depiction.
- [Restoration paths](campaign/restore-01.md) distinguish hub return, online handoff and exit, including journal and in-memory ownership limits.
- [Usability settings](campaign/accessibility-01.md) traces text scale, reduced motion, input labels and visible feedback consumers.
- [Performance budgets](campaign/performance-01.md) records configured limits and measurements still needed; no live latency benchmark is claimed.
- [Stats and progress](campaign/stats-01.md) separates attempt evidence, match telemetry and account information.
- [Build provenance](campaign/build-01.md) labels the publication baseline separately from the actual candidate; its addendum verifies twelve selected candidate menu hashes.

## Follow-up evidence

- [Scoring diagnostic](campaign/outcome-probe-01.md): six synthetic cases and 33 checks; a later defender touch reaches the engine but does not enter latest-touch attribution. Includes reviewed diagnostic source and observed JSON, not a production fix.
- [Favorite recovery](campaign/favorites-02.md): exact-ID source resolution, saved unavailable rows, legacy-store differences and base-lesson identity.
- [Input collisions](campaign/input-collisions-01.md): four temporary D-pad bindings, context gates and remaining event-routing questions.
- [Replay integration](campaign/replay-01.md): current attempt JSON versus native replay files and a bounded future adapter.
- [Native event hooks](campaign/native-events-01.md): confirmed public source hooks versus unverified callback candidates.
- [Package inspection](campaign/package-02.md): both stock training menus inventoried; existing portable tools found; browser movie hash matches the current installed artifact.

- [Stock difficulty route](campaign/native-training-flow-01.md): a child menu receives the selected training mode; adapt this pattern to MCT lesson and practice-tier IDs. Stock labels map to Easy/Medium/Hard, not the eight requested tiers.
- [HUD package evidence](campaign/hud-package-01.md): exact training-view and match-info movies identified; positions, timers and controller legends still need focused source tracing.
- [Imported attempt identity](campaign/import-identity-01.md): imported JSON claims can enter automatic personal-best selection; persist application-owned capture origin and filter compatibility before choosing a best.
- [Modifier measurement](campaign/mod-measurement-01.md): distinguish requested settings, applied effects, assistance context and imported claims.

## Required rank-routing correction

[Navigation research](campaign/native-navigation-01.md) found that the frozen candidate routes Power Shots to `Lesson`, where eight ranks appear in a side panel. A `LessonDifficulty` full-page builder exists but no action assigns that page in the inspected native/include/movie paths. Other lesson rows currently dispatch `start_lesson` directly. Wire and verify the requested separate rank-selection route for each supported lesson; merely retaining the unused builder or generic browser rank popup does not satisfy the requested flow. Preserve selected lesson focus on Back and persist the chosen practice tier independently of UI focus. This is a source finding and builder handoff, not a completed fix.

[Ball Prediction research](campaign/ball-prediction-01.md) also shows why its checkbox requires adapter work: ordinary MCT Power Shots uses an RLBot Soccar session, while the stock plugin declares Freeplay/Custom Training contexts and keeps a cached predictor across resets. Test reseeding and cleanup with other overlays before presenting it as supported.

[Shot selection](campaign/custom-shot-flow-01.md) now traces an exact static route: table indices drive the list, displayed shot numbers add one, and the chosen index reaches `StartAtPlaylistIndex` unchanged. Keep MCT scenario IDs independent of this stock host API; preserve the selected practice tier when opening an in-session situation picker. Numeric progress status meanings and actual host-call success remain unverified.
