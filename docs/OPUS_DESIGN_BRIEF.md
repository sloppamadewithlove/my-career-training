# My Career Training: visual design handoff for Opus 5.5

**Purpose:** Give Opus 5.5 a precise design assignment for the next My Career
Training iteration. This file is a handoff prompt; it does not mean Opus has
reviewed the project or that the live game integration has passed.

## Current assignment update — 25 October 2026

**Design-only boundary, explicitly corrected by the owner:** Opus supplies visual
mockups, colors, typography, spacing, layout/focus specifications and design
reviews. It does not author implementation code, interactive HTML/CSS/JavaScript,
keyboard/controller event handling, scripts, bug fixes or builds. Main and
DeepSeek implement the design and any corrections. Opus may review their rendered
screenshots for visual fit. This rule supersedes any historical design-engineer
or code/compiled-asset assignments elsewhere in this document.

The owner has now specified the Training/Workshop direction in
[TRAINING_WORKSHOP_DIRECTION.md](TRAINING_WORKSHOP_DIRECTION.md). This supersedes
older requests below for pause/slow playback, ghost placement beside the player,
or another broad requirements interview. First provide visual layouts for
Rows/Grid comparison; a builder turns them into self-contained HTML
previews before native implementation. The ghost is
slightly ahead, left D-pad toggles it, its own controller inputs are visible,
and speed flip is the first lesson. Tutorial video and controlled bot scenarios
are separate lesson actions. Workshop has Training Maps and Mods tabs; content
is downloaded on demand. Gameplay-changing mods remain out of Career and ball
prediction stays off. Do not claim sample preview motions are real lessons.

Opus owns visual design only for the game and website. DeepSeek via RunInfra
is the preferred implementation builder once its connection is verified;
main coordinates, reviews builder work and integrates; Luna max researches/tests. Existing login-based
design access needs no new API key. See DEVELOPMENT_WORKFLOW.md for exact roles.
Another session currently owns a demo recording: no game input or installed
asset/plugin changes until its completion and an ownership handoff are verified.

Use Claude Opus 5.5 **high** through Cursor CLI for new design assignments and
verify the actual model/reasoning output. Earlier ExtraHigh work is historical.
On quota exhaustion stop the designer role; retain unfinished work here instead
of silently substituting a model. See [DEVELOPMENT_WORKFLOW.md](DEVELOPMENT_WORKFLOW.md).

The historical report below explains the original player failures. Current
implementation and live evidence are in [PROJECT_STATUS.md](PROJECT_STATUS.md),
which takes precedence. Authored root/pause/results now exist. Red Forfeit Match,
Back-first confirmation, root focus handling and explicit Forfeit loss history
were integrated through `9d1d433`; later source and e41 frozen evidence is now
recorded in PROJECT_STATUS.md. Do not redesign those from scratch.

Remaining design work, to assign in separate scopes:

Pause update, 25 October: the five results controls and direct one-click
continuation are implemented at e41. Source live checks covered local presets,
Back and Exit; the exact frozen package completed a normal fixture, direct next
fixture and confirmed Forfeit. Do not rebuild those controls from scratch.
The owner's next product focus is Training and Workshop. Their latest choices
are recorded in TRAINING_WORKSHOP_DIRECTION.md. The
12-second continuation target is a performance goal, not a current claim.

- Preserve the owner's results order: Play Next Match, Schedule, Change Preset,
  Settings, Exit. Exit returns to the hub; its close-app label is Quit My Career.
  Schedule stays in the completed game without a time limit. Play Next Match
  immediately continues with the saved lineup, with no extra setup or confirmation
  menu; lineup changes remain in Squad. Use direct typed local preset/Settings controls and hide the
  misleading stock countdown. Follow
  [RESULTS_CONTINUATION_CONTRACT.md](RESULTS_CONTINUATION_CONTRACT.md). This scoped
  assignment is implemented; remaining exact-package and physical-controller
  acceptance is tracked in PROJECT_STATUS.md.
- Inspect the rebuilt Forfeit menu in the actual game: red styling, text fit,
  safe default Back, mouse/keyboard focus, physical DS4 navigation and readable
  saved-loss labels. Main/tester owns game input; designer reviews evidence.
- Improve training input feedback for a USB DualShock 4. Current display uses
  logical actions and placeholder D-pad/right stick. Compare an authorized
  community trial before deciding reuse versus custom rendering; do not claim
  plugin 707 redistribution rights or physical accuracy yet.
- Make lesson instructions and genuine recorded demonstrations understandable;
  do not present placeholders or synthetic movements as expert demonstrations.
- Validate compact Garage, Workshop and Community availability/error states
  against working capabilities, with consistent focus and Back behavior.
- Update the existing Vercel site's Setup instructions and screenshots only
  after exact player-release acceptance. Keep its current repair notice honest.

Each design delivery includes changed files/assets, exact labels, focus/default
states, visual evidence or explicit visual-test limits, and remaining backlog.

Actual Claude Opus 5.5 High subsequently reviewed four live `d95f4cc` screenshots
and the matching source. The coordinator also inspected them. Pause and Forfeit
confirmation were readable, with Back visibly selected. No design blocker was
reported. Keep these concrete follow-ups for a scoped design iteration:

- Add restrained dark navy backing behind Career/Schedule details; white text
  currently crosses the bright car. Preserve native controls and focus.
- Explain in pause copy that unfinished Return requeues the fixture, while
  Forfeit saves a loss and advances the season.
- Consider focusing enabled Play Next Match when entering Career. The current
  New career default opens a setup page and is not an immediate destructive act.
- Optionally clarify that Forfeit counts as a loss even while ahead. Existing
  FORFEIT — LOSS and score-at-forfeit labels already distinguish that outcome;
  this is copy refinement, not evidence of a scoring defect.

The results countdown still displays NEXT MATCH IN while retention refreshes it.
Review that misleading stock label once the results lifecycle is accepted.
Do not change or reload movies during an exact-candidate acceptance session.

**Product status:** The owner reports that the downloaded Windows preview is
currently unusable on their PC. The initial test has already happened: Career
fixtures and Start Practice failed, the menu repeatedly reopened over Rocket
League's menu, and Windows showed an access-denied error. Source repairs are in
progress; the replacement installer is held and no public-ready replacement
exists. Treat the reported failures as real player evidence and release
blockers. Do not present the redesign as a cosmetic pass over a working product
or describe the owner's report as a first game test still waiting to happen.

## Assignment

Act as the **design engineer** for an offline, solo Rocket League career mod.
Read this brief and the current UI and contracts before proposing changes:

- `plugin/src/CareerUI.cpp`
- `plugin/src/MyCareerTraining.cpp`
- `docs/IN_GAME_REBUILD.md`
- `docs/IN_GAME_ACCEPTANCE.md`
- `docs/IN_GAME_PLAYER_GUIDE.md`
- `docs/INTEGRATION_CONTRACT.md`
- `docs/FEATURE_MATRIX.md`

Design the experience the player should encounter after opening the My Career
Training shortcut: Rocket League starts in the supported offline mode and the
player enters a coherent My Career version of the game's menus. The finished
product must feel like a custom offline Rocket League mode, with clear game
actions and the familiar blue/orange sports presentation. The current
full-screen plugin overlay is a development surface, not acceptance of the
owner's native-menu goal. Do not claim that replacing Rocket League's original
menu is technically possible until the exact game build and supported plugin
interfaces prove it.

Return a design specification that an engineer can implement: information
architecture, page layouts, component states, exact button labels, keyboard and
controller focus behavior, loading and error copy, and Windows acceptance
scenarios. Keep it direct and compact. Avoid long explanations in player-facing
screens. Do not redesign the career rules, invent working features, or represent
unverified game capabilities as available.

## Player evidence from the owner

These are observations from the owner testing the GitHub download on a Windows
Steam PC. They have not yet been independently reproduced; retain that label
until a new test produces its own receipt.

- Starting practice fails. The game displays **“Could not publish the local
  career command.”** The surrounding status says **“Starting career, waiting
  for Rocket League to start the offline season.”** The owner reports that
  nothing starts.
- Starting a career fixture also does not start a playable game.
- A Windows access-denied message appears under a per-run path resembling
  `%LOCALAPPDATA%\MyCareerTraining\bridge\...`; the full path needs capture.
- Rocket League's original main menu appears or glitches over the My Career
  screen. The owner does not want two menu surfaces competing for focus.
- The current interface feels hard to understand and move through. The Garage
  makes the owner scroll through hundreds of items.
- The download requires BakkesMod, which the owner did not know about and does
  not want to discover as a surprise extra prerequisite.
- The owner wants training to show an understandable demonstration/ghost and a
  PlayStation-style controller display. A green target box alone was confusing.
- The owner wants Career, fixtures, training, garage, and community maps to be
  straightforward solo offline features.

Design the failed states as carefully as the successful states. Do not soften,
rename, or hide the reported errors before the underlying command/permission
failure is understood.

## Owner decisions and design constraints

Treat these as settled direction:

1. **Offline solo career.** No online matchmaking or social feature belongs in
   the My Career session.
2. **In-game destination.** The end-state is a custom Rocket League menu flow,
   not an external tournament launcher or a popup floating over a still-active
   original menu. If native-menu replacement is not supported, report the
   blocker clearly; do not relabel an overlay as the completed vision.
3. **Preserve the Steam game.** Do not overwrite, patch, or permanently replace
   the user's original Rocket League files, installed assets, settings, or
   saves. My Career saves remain separately managed and recoverable. A reversible
   integration must be proven on Windows before it is described as safe.
4. **Keep the player's club identity fixed.** Career setup may name the club
   once. The player cannot switch to another club/team during that career.
   Teammate lineup changes are allowed before each fixture; they do not change
   the human player's team.
5. **Simplify.** Use large readable type, short labels, fewer top-level choices,
   and direct actions. Put advanced diagnostics behind a separate route.
6. **Training is visual and actionable.** Show the PlayStation-style input
   display during practice and make the ghost modes explicit. A demo must be a
   real compatible recording with honest provenance. Never substitute an
   unexplained marker, synthetic animation, or imaginary expert ghost.
7. **Garage is compact.** Organize by slot with search, useful filters, and a
   compact visual grid. Do not present hundreds of items as an unstructured
   scroll. Clearly distinguish catalog visibility from an item that can
   actually be equipped locally.
8. **Workshop is browsable.** Provide Browse, Favorites, and local/installed
   content with search and explicit availability. A community listing is not
   proof a map can be launched.
9. **The setup should feel like one My Career Training download.** Explain
   BakkesMod in plain language before the player hits a dead end. Research and
   document the lawful, supported way to include or install this third-party
   dependency. Do not silently redistribute BakkesMod or community plugins
   without verified permission and a supported distribution route. Do not
   claim community plugins are compatible just because they exist.

## Proposed information architecture

Use five equally prominent top-level destinations:

| Destination | Player's question | Primary action |
|---|---|---|
| **CAREER** | How is my club doing, and what is next? | Play next fixture |
| **TRAINING** | What can I practice now? | Start the selected lesson |
| **GARAGE** | What local design can I use? | Preview or apply a supported local design |
| **WORKSHOP** | Which installed community map can I use? | Launch a verified local map |
| **SETTINGS** | What should I adjust? | Change a small number of career/display controls |

Career contains its overview/next fixture plus the **Squad**, **Schedule**, and
**League Table** views. Do not repeat those as separate top-level pages. The
player's club and current season should remain visible in the Career hub. Never
show Casual, Competitive, Tournaments, online parties, or online matchmaking
as My Career actions. This is the interim information layout; the ultimate
product goal remains a custom native offline Rocket League menu.

## Screen contracts

### CAREER / My Career home

- Lead with the club name, current season and round, win/loss record, and one
  prominent **PLAY NEXT FIXTURE** action.
- Show opponent, home/away, format, and map in one compact fixture card.
- Provide **CHANGE LINEUP** immediately before the fixture action. Show who is
  selected and the exact number of teammate slots required.
- After a completed match, show the observed score and a clear **CONTINUE CAREER**
  action. The score must come from the actual finished game.
- If a saved attempt is unfinished, say whether **RESUME** or **RESTART FIXTURE**
  is available. Explain whether changing lineup requires restarting the
  attempt. Never silently discard it.
- With no career, ask only for the club name and the minimum valid format, then
  start the career. Do not make the player choose another club after setup.

### CAREER

- **Overview:** season position, next fixture, recent real result, and one route
  each to Schedule and Squad.
- **Schedule:** compact round list. Clearly distinguish played, next, simulated
  rival, and future fixtures. Only the human club's fixtures are actionable.
- **League table:** readable club, position, played, wins, losses, goal
  difference, and points. Mark simulated results as simulated.
- **Squad:** choose the starting teammates for the next fixture; save only when
  the required number is selected. Preserve the career club lock. Make roster
  edits available between games according to the actual save/session rules.
- A finished season has an explicit results/next-season state; do not show a
  mid-season showcase as if it were the whole Career page.

### TRAINING

- Keep the lesson list short, searchable, and grouped by mechanic. Selecting a
  lesson reveals its name, one-line goal, one primary instruction, and the
  **START PRACTICE** action without a wall of explanatory text.
- A running lesson has an identifiable training state, visible reset/retry,
  and a PlayStation-style controller display anchored in a consistent lower
  corner. Label these as observed logical actions; do not imply raw controller
  hardware capture.
- Give the target marker a name and legend. It is a goal location, not a ghost.
- Provide explicit ghost actions: **WATCH DEMO**, **GHOST AHEAD**, **PAUSE**,
  **SLOWER**, **RESTART**, and **HIDE GHOST**, as supported by the recording.
  Do not show disabled actions without saying what is missing.
- Keep source/provenance visible: personal best, imported unverified recording,
  or verified teaching reference. If no compatible recording exists, say so and
  offer the next useful action, such as record an attempt. Do not claim a camera
  perspective or expert tutorial until it is implemented and game-verified.
- Starting practice must have a clear acknowledged state. If the career service
  does not accept the command, show the error immediately and provide Retry,
  Back to Career, and Save Diagnostics. Never leave “waiting” as a permanent
  apparent success.

### GARAGE

- Show a horizontal or compact category selector for supported slots; selecting
  a slot shows a searchable, filterable, virtualized tile grid with names and
  clear current selection. Do not require hundreds of rows of scrolling.
- Include sensible filters such as installed, supported, and selected. Keep
  unsupported/cosmetic catalog-only items visible only with an explicit label.
- Provide a clear local preview, **APPLY DESIGN**, and **RESTORE ORIGINAL**.
  Show which exact changes are local and whether the active game build supports
  them. Never imply that account-locked inventory is unlocked or granted.
- If there are no supported products or the game API is unavailable, state that
  plainly and keep restore available.

### WORKSHOP

- Keep **BROWSE**, **FAVORITES**, and **INSTALLED** as the main views. Search and
  filter by mechanic/category. Show map title, creator/source, availability,
  dependencies, and whether it is installed and launch-tested on this setup.
- Distinguish creator page, map listing, local file, and verified launch as
  different states. Use **PLAY MAP** only when this exact map can be launched.
  For unavailable maps, give one clear next step rather than a dead button.
- If a list is empty, explain how to refresh or install supported local content.
  Do not imply Steam Workshop access on Epic or broader access than was verified.

### SETTINGS

- Keep frequently used controls first: display scale, PlayStation controller
  overlay on/off and corner, training ghost lead/playback speed, and a small set
  of career challenge controls when changing them is valid.
- Put game/plugin versions, save location, installation status, log export, and
  advanced checks under **DIAGNOSTICS**.
- Explain BakkesMod once in plain language during setup, including why it is
  needed by this preview and what version is detected. Avoid exposing plugin
  internals as settings.
- Never promise inactivity-kick protection, a supported native-menu replacement,
  or a cosmetic operation until its exact capability is proven in the current
  Windows game.

## Input, focus, and visual rules

- There must be one visible menu owner at a time. The original Rocket League
  front-end must not flicker through, sit over the My Career menu, or steal
  focus. If the implementation cannot hide/replace the original surface safely,
  call it a known blocker and do not mark visual acceptance complete.
- Keep focus visible at all times. Mouse, keyboard, and controller navigation
  should reach every action. For the PlayStation display, use D-pad/left stick
  to move, Cross to confirm, Circle to back, and the actual game-configured
  controls for driving. Do not silently rebind Rocket League controls.
- On a page change, place focus on its title/first useful action. Back returns
  to the prior view without resetting search, selection, or a draft lineup.
- When a text field opens, direct text input to it; do not allow gameplay/menu
  navigation to trigger underneath. Preserve existing game keybinds and select
  an unused shortcut only when needed.
- Use clear selected, disabled, busy, focused, success, and error states. Keep
  contrast and readable scale at 1080p and 4K. A disabled control includes a
  short reason. Use game-inspired color and spacing without redistributing
  proprietary Rocket League art or fonts.
- One prominent primary action per screen. Use short labels, short status copy,
  and progressive disclosure. Diagnostics and capability explanations should
  not dominate the normal player flow.

## Loading, failure, and recovery contracts

| State | Required player-facing behavior |
|---|---|
| Starting Steam/offline Rocket League | Show a changing, honest launch status; distinguish “starting” from “ready.” If the game is absent or the launch fails, explain the next action and offer retry/diagnostics. |
| Career service not ready or stale | Do not accept a match/training action as successful. Show service unavailable, a retry, and diagnostics. No indefinite “waiting for Rocket League” state. |
| Command could not be published | For the observed “Could not publish the local career command” failure, say the action did not start, keep the page and selection intact, and provide Retry, Return to Career, and Save Diagnostics. Show the specific service/permission detail in diagnostics. |
| Windows access denied | Present a plain-language, actionable error and exact affected My Career data path in diagnostics. Preserve existing career data. Do not ask the player to run as administrator by default or change Steam file permissions. |
| Original Rocket League menu overlaps | Treat as a launch/focus failure. Do not present the career as ready while the original menu can draw over or take input from it. Provide a safe close/retry path that does not alter Steam files. |
| BakkesMod missing/out of date | Explain what it is, why this preview currently depends on it, detected status, and the verified setup path. Do not make the user guess or show an unrelated access-denied message. |
| Plugin/telemetry unavailable | Show the interface state as disconnected or limited; disable only affected actions and explain why. Never display stale input as live. |
| Ghost recording unavailable | Name the missing recording requirement. Keep practice and personal recording available. Do not draw an unlabeled green box and imply it is a ghost. |
| Workshop item unavailable | Keep its listing and favorite state, but disable launch with a concrete reason and a supported next step. |
| Save/result write fails | Preserve the pending result/attempt and show that it was not saved. Offer retry/diagnostics; never report the match as committed until durable save acknowledgment. |

The wording above specifies behavior, not root cause. The reported bridge path
and command error must be investigated by implementation/QA before replacing
them with a friendlier message.

## BakkesMod and community feature boundary

The owner wants the My Career download to feel complete and wants useful ideas
from the BakkesMod community. Make the setup path understandable and as close
to one guided install as the verified distribution route permits. Before
proposing that BakkesMod is bundled, confirm its license, official installer
support, and permission to redistribute. If it cannot legally or technically
ship inside this installer, explain that clearly and route the player to the
official source from the setup flow. Do not repackage random community plugins.

Treat community plugins as inspiration or separate, explicitly reviewed
optional integrations. Any feature adopted into My Career Training must have a
known source/license, a safe offline-only behavior, a tested compatibility
story, and a clear label. The game remains offline; do not pull in online
features or third-party network services.

## Native-menu feasibility and preservation gate

The visual goal is a native Rocket League menu. Current project
documentation says the plugin draws a custom interface inside Rocket League
and that full Scaleform/native-menu replacement has not been demonstrated.
Design the intended native flow now, but keep implementation claims behind a
separate feasibility gate. The design handoff should identify which elements
are game-engine menus versus plugin-rendered surfaces and what proof is still
needed.

Before any implementation claims the original menu has been replaced, the
engineering/QA work must show on the supported Windows Steam build that:

1. Rocket League's shipped game files and installed assets remain intact; the
   mod does not patch or permanently overwrite them.
2. The existing Steam install and unrelated Rocket League settings/saves still
   work after install, update, disable, and uninstall. My Career career saves
   are separately preserved and recoverable.
3. Only the intended offline My Career surface is visible and receives input;
   transitions never leave the game's original menu over it.
4. The behavior is tested in the real game. A DLL build, screenshot mock, or
   local UI test alone does not satisfy this gate.

If a supported, reversible native-menu path cannot be demonstrated, report that
technical boundary plainly and propose concrete options. Do not ship an overlay
under a native-menu claim, and do not risk the owner's Steam installation to
force a visual result.

## Decisions versus assumptions

**Owner decisions:** offline solo focus; My Career should become the game menu
experience; no team switching; lineup changes before each fixture; PlayStation
training controller display; explicit real ghost/demo; compact Garage; browsable
Workshop; simpler readable controls; preserve the original Steam game; explain
the BakkesMod dependency and make setup feel complete.

**Current implementation facts recorded by the repo, not live-game proof:** the
preview uses Steam and BakkesMod; the plugin currently draws an in-game custom
window; Career, Squad, Schedule, Season, Training, Workshop, Garage, and Settings
are separate plugin pages; training/ghost/cosmetic controls are capability
gated; no validated expert recording is bundled; the native-menu replacement
has not been demonstrated. Recheck these against the current branch before
making implementation recommendations.

**Unknowns that must stay labeled:** exact cause of the player's access-denied
and command-publication errors; why the original menu overlaps; current Windows
game/BakkesMod versions on the player's PC; whether native menu replacement is
supported; whether BakkesMod can be redistributed or installed unattended;
whether each community plugin/map/cosmetic call works in the current game.

Do not convert any unknown into a product promise or a design assumption that
the player must work around.

## Windows design acceptance scenarios

Record the exact app commit, installer checksum/version, Windows version,
Rocket League build, Steam state, BakkesMod version, plugin status, and observed
result for each real-PC scenario. Keep build/test evidence separate from game
evidence.

1. **First-time setup:** install from the My Career Training download on a clean
   supported Windows Steam machine. Understand BakkesMod and its role before
   being asked to install it. Complete or clearly stop at each dependency
   requirement. Confirm no Rocket League files/settings were changed
   unexpectedly and no career save was overwritten.
2. **Launch and menu ownership:** use the desktop shortcut. Confirm Rocket
   League starts offline, the My Career destination appears, the original menu
   does not glitch through it, and keyboard/controller focus belongs to exactly
   one surface.
3. **Career progression:** create/continue a career, keep the club fixed, change
   lineup before a fixture, start the next match, complete it, observe the real
   result, return to Career, and confirm the saved record/table. Repeat after
   restarting the app.
4. **Training start/failure:** start a lesson and observe a playable training
   session, real action feedback, reset, and return. Then stop the local career
   service or deny the bridge path in a controlled test and confirm the error is
   immediate, specific, recoverable, and does not claim practice started.
5. **Ghost/controller truth:** use an available compatible real recording;
   compare Watch Demo and Ghost Ahead, pause/restart/seek where supported, and
   inspect PlayStation action labels with actual gameplay telemetry. Also test
   no-recording and missing-telemetry states. No fake expert claim or unlabeled
   target marker passes.
6. **Garage density and safety:** browse a representative large catalog, search
   and filter to an item without long unstructured scrolling, apply one
   supported local override, restore the original, then close/reopen and verify
   original appearance and Steam files.
7. **Workshop truth:** inspect Browse, Favorites, and Installed. Launch a
   supported installed map; attempt an unavailable map and confirm the UI gives
   a truthful explanation rather than a broken Play button.
8. **Save access and recovery:** test an unavailable/locked My Career data path.
   Confirm the original career is retained, no elevation/Steam permission
   change is silently requested, and diagnostics name the affected path.
9. **Input and visual scale:** complete every primary flow using keyboard and a
   PlayStation controller; verify visible focus, Back behavior, text entry,
   disconnect/reconnect handling, readable type, and no accidental gameplay
   action from a menu press.
10. **Disable/uninstall:** disable My Career Training, launch Rocket League
    normally through Steam, and confirm original menus, saves, settings, and
    game files remain usable. Reinstall and continue the existing My Career
    save.

Do not mark a scenario passed from source inspection, unit tests, screenshots,
or a successful Windows package build. The owner will perform the live-game
test on their Windows PC; the developer must provide a short, repeatable test
guide and collect their exact observed failures without guessing at a cause.

## Expected Opus 5.5 design deliverable

Return a concise but implementation-ready proposal containing:

1. A revised five-destination navigation and page map, with Career containing
   its Squad, Schedule, and League Table views and the next-fixture action.
2. A layout contract for each screen above, including primary action, secondary
   actions, empty/busy/error states, short player-facing copy, and focus order.
3. A reusable visual component set for fixture cards, compact item tiles,
   workshop map rows/cards, status banners, PlayStation controller display, and
   real-ghost states.
4. A clear separation between design that can be implemented with current
   plugin APIs and the native-menu replacement feasibility gate. State the
   evidence needed for each unresolved game integration question.
5. A mapped list of Windows acceptance scenarios above and any additional
   observable criteria needed to call the design usable.

Do not edit the game, copy proprietary assets, or claim a review of the live
Windows game as part of this design assignment. Keep any optional polish notes
small and specific; functionality, focus, clarity, and honest state feedback
take priority.
