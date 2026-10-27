# Implementation map — research still in progress

This is the builder entry point for the eight-hour campaign. It preserves the
requested Lessons, Workshop, Mods and Favorites organization and separate
lesson → Bronze–Supersonic Legend selection. Reports describe an isolated source
snapshot, not necessarily the current installed plugin; reconcile
[source identity](source-provenance.json) before implementation.

## Player-facing work and its evidence

| Requested behavior | Research established so far | Integration starting point | Next proof needed |
| --- | --- | --- | --- |
| Stock-style training browser | Stock composition, tabs, legend, resize behavior and selected row classes are documented; final screen rendering and imported art/font behavior remain unverified. | [NATIVEUI-01](campaign/nativeui-01.md), native authored menus and NativeCareerLayout | Controller/mouse selection, async refresh, bounds, empty/error states and aspect-ratio checks in the actual movie. |
| Separate rank menu for every lesson | The separate page builder is not routed; Power Shots uses side-panel ranks and seven lessons lack rank profiles. See the rank-routing correction below. | [CURRICULUM-01](campaign/curriculum-01.md), catalog, scenario_setup, bridge and NativeCareerLayout | Real setup and criteria for every one of 64 lesson-tier combinations; menu labels alone do not implement ranks. |
| Preserve lesson content and choose exact skills | Existing eight lessons have distinct event contracts; twelve ranked situations currently belong only to Power Shots. | [OUTCOMES-01](campaign/outcomes-01.md), training engine/catalog | Qualifying attempt and near miss for each declared skill/profile; separate target completion from mechanic mastery. |
| Shot setup, ready/go and retry | Whole-actor reset, settled setup, authored feeds and rank pressure are traced. | [PHYSICS-01](campaign/physics-01.md), engine, scenarios, game_worker | Observed car/ball/opponent starting state and timing; request acknowledgement alone is insufficient. |
| Top-left lesson/progress information | Current gameplay HUD source and clip-local timeline geometry are traced; final screen-space placement and visible fit remain unverified. | [NATIVEUI-01](campaign/nativeui-01.md), [initial native research](initial%20findings/native-training-research.txt) | Verify traced HUD anchors, text fit, scaling and timer/progress identity in-game. |
| Timer and ball disappearance | The current terminal path has no ball hide; installed fade wrappers are replay-gated. Generic actor hiding remains an unverified Soccar candidate. | [SDK-01](campaign/sdk-01.md), [native clocks](initial%20findings/native-clock-research.txt), [lifecycle research](initial%20findings/shot-lifecycle-rea-wave2.txt) | Correlated shot start, timer expiry, ball flags and actual visible disappearance on the exact built artifact. |
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

[Installed drawable wrapper](campaign/sdk-drawable-01.md) delegates through an unresolved host interface, so it does not establish per-plugin cleanup scope. [HUD inventory](campaign/hud-inventory-01.md) now provides current-artifact source identity for a focused timer/progress/control trace.

[Training HUD flow](campaign/hud-flow-01.md) traces native time formatting, prompt bindings, visibility and safe-zone transforms. Its timer callback updates the label; ball expiry is a separate native lifecycle question. [GameInfo metadata](campaign/gameinfo-metadata-01.md) identifies editor/tutorial event and ball objects but has no Function/State exports to establish call order. [MCT attempt end](campaign/attempt-end-01.md) shows the app issues no terminal ball hide/freeze/reset write; Retry performs the full state reset after acknowledgement, while post-finish situation navigation remains blocked until retry.

[Import-selection diagnostic](campaign/import-probe-01.md) reproduces imported claims entering automatic best selection using four offline bridge cases and twelve checks. [HUD timeline geometry](campaign/hud-timeline-01.md) supplies authored label positions within the training clip, while leaving runtime screen placement separate.

[Installed fade-wrapper analysis](campaign/sdk-fade-01.md) supersedes the earlier [header-only candidate](campaign/ball-visibility-01.md): both fade operations are replay-gated in the inspected installed DLL. Do not implement that pair as a Power Shots Soccar timeout effect. FadeIn also does not establish exact restoration of the previous material or fade flag.


## Settings, playback and arrival follow-up

- [Stock Training settings](campaign/stock-training-settings-01.md): seventeen selected classes connect Boolean row values, checkbox activation, native write requests, descriptions and reset defaults. Render MCT row help and keep requested/observed values separate.
- [Lesson acceptance checks](campaign/lesson-acceptance-tests-01.md): one offline run passed forty selected tests. Catalog shape and selected variants are not all-lesson game proof.
- [Ghost playback](campaign/ghost-playback-01.md): Watch/Lead/Practice use distinct clock rules; ghost rendering continues after terminal attempts, and an ended clip can retain its last outline. Choose an explicit terminal policy and verify renderer cleanup.
- [Workshop arrival](campaign/map-arrival-01.md): callback return and generic external activity do not prove the requested map arrived; require request-bound map/geometry/roster validation before lesson state writes.
- [BakkesMod shot format](campaign/shot-data-01.md): a legacy JSON supplies partial launch physics, not a full drill. Correctly map rotation/angular velocity, reject executable script, and author MCT targets/outcomes/rank separately.


## Setup, browser and ownership findings

- [Reset readiness](campaign/reset-ready-01.md) traces parked and moving ball writes, settle/confirmation tolerances, and timer start on observed `go`. Ball spin is written but not part of the confirmation gate. [Scenario checks](campaign/scenario-acceptance-tests-01.md) passed 130 selected offline cases, including 96 construction cases; numbered Power Shots multi-bot recovery still needs coverage.
- [Stock pack browser](campaign/native-pack-browser-01.md) traces code search, favorites, update and Play requests and numeric-index selection on refresh. Preserve MCT stable IDs and the requested Lessons/Workshop/Mods/Favorites tabs; native API dispatch does not prove content transfer or arrival.
- [Garage ownership](campaign/garage-restore-01.md) found that cosmetic restore can overwrite later user edits. Track ownership per written field and handle conflicts; a saved design draft is not a durable restore baseline. Return-to-hub currently keeps the offline local appearance.
- [Actor visibility wrapper](campaign/sdk-actor-visibility-01.md) forwards SetHidden2 to Engine.Actor.SetHidden without the replay check seen in ball fade wrappers. Its engine effects/restoration remain unverified; raw self-hidden field writes are a distinct operation, not an equivalent effect.


## Lesson grading and restore reproducer

The [eight-lesson matrix](LESSON_EVIDENCE_MATRIX.md) now links an exact outcome/evidence audit for every lesson. Several instructional technique claims exceed the completion rules; define intended outcome versus technique grading, event ordering, confidence and deadline behavior before adding rank profiles. The individual reports distinguish tested predicates from physically reachable gameplay.

[Cosmetic restore diagnostic](campaign/cosmetic-restore-probe-01.md) compiled and ran against the unchanged production transaction class: six cases and six control checks passed. Later fake-host code/enabled edits were overwritten by Restore, confirming the source behavior. The folder includes the reviewed reproducer, header, CMake input and observed output; no actual cosmetic/game operation occurred.

## Default-plugin control contracts

The [control and ownership matrix](PLUGIN_CONTROL_MATRIX.md) maps six newly audited plugins to suitable actions or toggles. Dribble, Redirect and Rebound are one-shot ball mutations; Recovery repeats car-velocity changes; Defender is a goalkeeper-feed generator; Mechanical transforms intercepted controls. Their ordinary Freeplay gates are not proven compatible with MCT Soccar. Preserve exact context/actor/attempt identity, expose requested versus observed state, stop mutations before resets, and record assistance in result/ghost compatibility. Cvar parser and host cleanup semantics remain separate research questions.

## Workshop naming and garage coverage

[Legacy WorkshopPlugin](campaign/workshop-plugin-01.md) is a deprecated shot/playlist exchange, not a Steam map loader. Its TrainingPlugin reset can execute a script and schedules a mutable, unbound delayed ball write. Do not reuse that command chain as MCT Workshop loading or inert data import.

[Garage catalog coverage](campaign/garage-catalog-01.md) distinguishes 15 browse categories from 11 local-code slots, with bodies catalog-only. The scanner reads catalog templates, not owned instances, and supplies neither equipability/paint-family validation nor visual preview proof. Its 100,000-entry ceiling lacks a truncation signal. Broader cosmetic support needs a build-bound coverage receipt and slot-specific compatibility/appearance checks; current source does not establish all skins available.

## Pause semantics and current native feedback

[Pause and settings](campaign/pause-clock-01.md) distinguishes the default ImGui overlay from the opt-in native pause menu. Opening the overlay does not send a worker pause command; real pause telemetry can interrupt an active Power Shots attempt. Test shortcut Settings and native Pause → Settings separately against the actual deployed build.

[Current native feature leads](campaign/native-feature-delta-01.md) identifies official reset cues, velocity graphs, offline-Freeplay hitbox display, configurable stat counts and updated controls as candidates for integration research. Their publication does not establish a local API or a supported MCT context. Historical reset-indicator and mirrored-spawn fixes strengthen the need for observed state and separate visual/result evidence.

[Controller evidence](campaign/controller-evidence-01.md) separates the third-party overlay, fixed lesson hints and packet-derived action coaching. The current overlay requests a PS4 skin; saved binding-profile labels do not route into that skin or ghost mapping. Display/event thresholds are not hardware deadzones. Show generic logical actions until effective mappings are known.

The [pause follow-up](campaign/pause-clock-01.md#documented-elapsed-clock-contract-coordinator-follow-up) now verifies that the pinned RLBot schema and installed type stub document elapsed time advancing during pause/replay. Legacy lesson timeouts and game-clock ghosts therefore need an explicit pause policy; local packet delivery is still unmeasured. A separate offline reproducer is being prepared, with unchanged production sources.

## Stronger reset candidates and browser row composition

[Reset signal surfaces](campaign/native-reset-signal-01.md) identifies per-wheel contact records and LastWheelsHitBallTime declarations as candidates beyond MCT's current availability/touch/geometry inference. No direct acquisition event or reset count is present in the inspected RLBot schema. Validate contact actor/time semantics before upgrading confidence. The current adapter already copies dodge_timeout.

[Stock browser rows](campaign/native-pack-row-01.md) now have seven-class evidence and local timeline metadata: title/classification at the left, alternate creator or publication/date metadata at the right, favorite/loading states, shrinking text and animated focus backgrounds. The row is locally defined; a generated decompiler Embed reference had initially been mistaken for missing external row art. Shared components/fonts and final screen appearance remain separate. Use the sanitized metadata as a layout reference while retaining MCT stable IDs and explicit progress.

## Build order and CVar boundary

[Implementation waves](IMPLEMENTATION_WAVES.md) turns the accumulated findings into scoped builder tasks and acceptance gates. It is a proposed order, not completed implementation.

[CVar semantics](campaign/cvar-semantics-01.md) proves that installed numeric getters forward to the core. Public parser helpers do not establish the core getter behavior; core analysis timed out. Do not infer range re-sampling, clamping or correlated X/Y values from tuple-looking defaults.
