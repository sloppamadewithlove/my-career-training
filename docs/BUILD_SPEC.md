my-career-training — product build specification
Product scope updated: 24 October 2026. Recheck current game and dependency versions when building.
How to use this prompt
Open the canonical my-career-training GitHub repository in the coding workspace. The current requested team is the primary coding agent working alongside exact Grok 4.7 High builders, with GPT-6 Luna Max for research/discovery. Do not claim a requested model was used when it was unavailable. This document is self-contained; the reference starter is optional.
Everything below is the build assignment. Product defaults are already chosen so implementation can proceed without a long clarification round.
1. Assignment and definition of success
Build My Career Training, an offline career and training mod for the player's real, current Rocket League installation, with a local service for careers, training and saves. The canonical repository is sloppamadewithlove/my-career-training. The implementation includes interface design, integration, testing, debugging, and packaging.
The player drives their own car, manages a five-member squad, plays short seasons with bot teammates and opponents, and optionally practices specific skills. Preserve normal Rocket League movement, physics, rules, controls, arenas, and the installed game's visual assets. This is an addition around the real game, not a recreated driving game or a browser simulation.
The intended player understands Rocket League but is not a programmer. The first user plays through Steam, is around Diamond, and particularly wants to learn speed flips and flip resets. Support Epic Games installations as an equal product target, with separate runtime verification.
One-shot means one complete implementation run: inspect, build the whole specified release, exercise it, repair concrete failures, and package it. Use internal milestones to control the work, but do not stop after a plan, attractive mockup, generated match file, or one working lesson. Continue through all deliverables that the available environment allows.
A detailed prompt cannot guarantee an integration will work without access to the game. If a live Windows installation, platform sign-in, distribution credential, licensed reference recording, or external service is unavailable, complete all independent code and tests, identify the precise remaining dependency, and report its status accurately. Never replace missing evidence with a fake successful run.
If a required first-release feature, teaching reference, or runtime acceptance check remains unavailable, deliver the completed independent work and mark the full V1 release incomplete. Do not call source-only delivery, an untested adapter, or missing required lesson content a finished playable release.
2. Product architecture and launch environment
Use a local desktop application with an isolated RLBot v5 game worker connecting to the installed Rocket League game. The application owns careers, fixtures, squad management, training definitions, preferences, and saves. Rocket League remains responsible for the actual match and physics.
The documented bot/mod route uses the current game's supported EAC-off environment. Epic documents offline matches, training, LAN matches, and replays in that environment. Ordinary official online play uses an EAC-enabled launch. Both environments can exist on the same computer and use the same installed game; switch sessions cleanly. Do not require an old game version or a second account. [1–3]
Use the existing Steam or Epic signed-in session. Do not collect platform passwords, invent an account-linking service, or promise an inventory API. The app remembers the selected launcher. Detect both installations and ask once if the choice is ambiguous; prefer Steam for the initial user's setup.
The required release interface customizes Rocket League's native offline main menu: its buttons, destinations, options and settings must serve My Career. Preserve the game's visual language, native controls, animations, controller navigation and Back behavior. Remove online/store routes from the My Career session, or make them non-clickable if removal cannot be verified. A desktop window, plugin overlay or modal dialog does not satisfy native menu replacement. The normal Steam/Epic online launch must retain its original behavior and menu. Native integration is required for completion; it is not an optional enhancement. See docs/NATIVE_MENU_IMPLEMENTATION_PLAN.md and the current acceptance evidence.

The home close-app control is **Quit My Career**. Finished career matches show,
in order, **Play Next Match**, **Schedule**, **Change Preset**, **Settings**, and
**Exit**. Results Exit returns to the career hub. Schedule stays inside the
finished game without a time limit. Play Next Match immediately starts the next
scheduled fixture with the saved lineup after saving and cleanup, in the same
game process. It has no extra preview or confirmation menu; lineup changes stay
available separately in Squad.
Use existing local car presets and the game's Settings directly. See
[the results contract](RESULTS_CONTINUATION_CONTRACT.md) for exact persistence
and navigation rules; current status records what is actually tested.
No runtime AI subscription is needed by players. Bots, detectors, coaching rules, season management, and saves run locally. Do not make cloud accounts or internet access to a career server mandatory. Steam/Epic may have their own launch and authentication requirements; distinguish those from the app's local operation.
Use the game's supported offline launch route and validate any native adapter against the exact installed build. Undocumented signatures or generated offsets alone do not authorize production writes. Do not hide modifications from anti-cheat, patch protected online behavior, or send career bot control into ordinary official matches.
3. Full first-release scope
Implement all of the following:
1. A Windows desktop application with original icon, installer, portable package, shortcut, settings, diagnostics, and clear first-run setup.
2. Real career matches in 1v1, 2v2, 3v3, and 4v4 Soccar, using built-in arenas and normal match rules.
3. Team creation, a five-member squad, specialist bot behavior, lineup selection, between-match substitutions, difficulty settings, and progression.
4. A complete short league season, standings, results, a season conclusion, continued careers, and reliable saves.
5. A complete optional training catalog described below, repeatable scenarios, useful measured feedback, demonstration playback, and independently configurable assistance.
6. Bot appearance customization, career-local cosmetic rewards, and BakkesMod-style local human cosmetic designs from the installed catalog. Validate supported items and restore the player's ordinary appearance on leaving My Career; do not grant online ownership or inventory.
7. Workshop browsing, settings and verified offline map loading without substituting an installed game asset. Community BakkesPlugins links should support downloading creator releases into My Career and enabling compatible reviewed helpers in an owned offline session. Cached downloads alone do not satisfy activation; site verification alone does not establish compatibility or cleanup.
8. The complete Play Online confirmation, save, close, and normal-launch transition.
9. Automated checks, a Windows build workflow, versioned release artifacts, and a precise implementation/game-test report.
The first release has one human captain and bot teammates. This is a deliberate release boundary, not a claim that mods or Rocket League custom-bot matches cannot be multiplayer. Keep the match adapter separable so a private two-captain version can be developed without rewriting the career engine. Section 14 defines the investigation and acceptance requirements for that extension.
The enlarged-map/22-player lobby is a separate project and must not enter this repository's scope. Extra modes such as Hoops, Rumble, and Dropshot are also outside this first Soccar release.
4. Native game interface and desktop management
Build a polished, readable sports-career interface. Use original artwork and an original icon rather than copied EA or Rocket League branding. Use a dark neutral background, restrained blue/orange accents, large readable labels, clear selected states, and consistent spacing. Do not show decorative controls that do nothing.
Main destinations:
- Native home: My Career, Training, Garage, Workshop, Community, Settings, Exit. My Career includes Continue Career and New Career. Online/store destinations are disabled or removed for this session. Any separate return-to-normal-game command must complete the save, close, restore and normal-launch sequence first.
- Career Hub: next fixture, team, recent result, standings summary, and one prominent Play Match button.
- Squad: human plus four bots, starter/bench positions, role, level, appearance, and recruitment choices.
- Season: schedule, complete league table, match history, and season awards.
- Training: skill catalog with independent lessons and saved assistance settings.
- Garage: supported bot appearance choices and clearly identified career rewards.
- Settings: launcher, install location, accessibility, controls/binding display, game connection, diagnostics, and backups.
After a match, show the result and Continue. Training and review remain optional secondary choices. Never force a lesson or a "Practice This Moment" flow between fixtures.
Support mouse, keyboard, and controller navigation in the app. Use visible focus, consistent Back/Cancel behavior, configurable text scale, reduced motion, and cues that do not depend only on color. Handle controller disconnects without losing progress. The player must always be able to restore skipped tutorial explanations from the lesson's Help settings.
The desktop shortcut launches the app, checks the selected game installation, restores the career hub, and starts the supported game session when ready. On first run, setup may need the install/launcher choice; subsequent starts should not require a terminal or repeated setup. Avoid creating a match before the player has selected the fixture or lesson.
A verified non-invasive shortcut may bring the career app to the foreground during the offline session. Do not intercept gameplay controls unexpectedly or depend on an unverified global-hook implementation.
5. Team, roster, and substitutions
The squad always has five total members: one human plus four recruited bots. There are five archetypes available for recruitment; that does not mean the squad contains five bots.
Format	Human	Active teammate bots	Bot substitutes
1v1	1	0	4
2v2	1	1	3
3v3	1	2	2
4v4	1	3	1


Provide a starter recruit pool with memorable editable names:
- Anchor — keeper: prioritizes goal protection and difficult saves while rotating normally when the situation changes.
- Shield — defender: covers dangerous space, supports recovery, and clears pressure with sensible placement.
- Relay — passer: looks for reachable teammates and useful setups, while still taking an open shot.
- Comet — attacker: emphasizes offensive positioning, shot opportunities, and pressure without blindly chasing.
- Orbit — all-rounder: balanced abilities without the same peak specialty.
Choose four at career creation; use the first four as the default. The unselected recruit remains available. Replacing a recruit occurs between matches. Preserve each recruit's identity, earned level, appearance, and statistics in the career's recruit records so dismissing and rehiring cannot duplicate rewards or silently reset progress.
The human always controls the human car. Do not switch human control to teammates after kickoff or perform mid-match substitutions. Block lineup/recruit changes while a fixture is active or pending recovery.
Bots must respond to the whole match. Roles are preferences and strengths, not permanent parking spots. Opponents use the same honest capability system as teammates.
6. Actual bot behavior, difficulty, and progression
Do not implement specialties by changing names above identical built-in bots. Build a bot-provider interface and a functioning baseline specialist controller, or adapt a suitably licensed existing controller whose behavior can actually be modified.
For the baseline, separate perception, tactical choice, and driving execution. Use game state and ball prediction where supported to select among reachable intercepts, saves, clears, passes, shots, support positions, recoveries, and boost collection. Roles change those decisions through documented weights or rules. Share enough intent between teammates to reduce unnecessary double commits; do not assume the human will follow a bot's plan.
Give each specialty several meaningful levels. For example, progression may improve defensive positioning, reachable-intercept estimation, decision consistency, pass selection, recovery, or execution accuracy. Implement the parameter or policy changes and verify their effect in representative scenarios. A level counter alone is not progression. Do not give bots altered car physics or invisible extra boost in normal career matches.
Use existing community bots where useful, checking their license, model-weight permissions, version, runtime requirements, and supported formats. Keep optional large bot downloads out of the base package when practical. A packaged bot must never execute a remote arbitrary install script just because a catalog entry points to it.
Difficulty: allow an initial baseline and a visible season curve of Flat, Gentle, or Steep. Default Gentle. Difficulty follows that setting and the stage of the season, not hidden adjustments after wins or losses. Mid-season edits apply only to future fixtures and appear in the career settings/history.
Bronze–Supersonic Legend is the desired target range, not a fact created by a slider. Include a provider/capability model that can represent that range. Expose playable tiers backed by the installed controllers and actual evaluation. Unverified high-rank targets must say unavailable/experimental and identify the actual bot used; never relabel the same weak bot as SSL. Different modes, especially 4v4 and mixed human/bot teams, need separate assessment. Creator estimates for Nexto are useful evidence, but not a universal rank certification or proof that adding roles preserves its strength. [10–11]
Select opponents and teammate starting capability that make the chosen baseline understandable. Offer a short calibration exhibition without requiring it. Record provider/version, role, parameters, seed, and starting level for each fixture.
Progress all squad members through match participation and team experience, with a modest bench share so substitutes do not become unusable. Use bounded, explicit progression rules. Training does not have to be completed to level the team. Human rewards affect appearance, trophies, and records, never the ability to jump, boost, air roll, speed flip, or access lessons.
7. Complete short-season rules
Default to four clubs in a double round-robin: the human's club plus three fictional clubs. Each club faces the others twice, producing six rounds and six ordinary fixtures for the human's team. Every round contains two matches.
Use normal five-minute Soccar and Rocket League overtime. Do not allow a tied completed result. A win earns three league points, a loss earns zero. Sort by points, goal difference, goals scored, then head-to-head points among tied clubs. If the title remains tied, use single-match title playoffs: two clubs play a final; three clubs use a semifinal and a final with one bye; four clubs use two semifinals and a final. Use a persisted season draw only to seed this bracket, never to award the title. Play every fixture involving the human club in the real game and clearly label simulations between the other clubs. Playoff results determine the title without changing the completed league table. Explain that these exceptional title playoffs can extend the usual six-match season.
Play the user's fixture in real Rocket League. Resolve the other fixture using a seeded, bounded season simulation that reflects recorded opponent strength. Mark these results as simulated; they are league bookkeeping, not claimed live bot matches. Persist the random seed and resolved result so reopening the app cannot reroll it.
Allow the player to choose 1v1–4v4 at creation and change the format between completed rounds. Apply changes only to future unstarted rounds, including their simulated fixture. Store the exact format, map, lineup, opponent, and difficulty on every fixture/result. Never validate old lineups against a new global format.
After the season, show the table, champion, team record, and earned rewards. Offer Start Next Season while preserving the squad, progression, garage presets, trophies, lesson preferences, and historical seasons. Create new fixtures and seeds explicitly. Do not restart or wipe the career merely because the app closes.
An abandoned fixture remains unfinished and can restart from kickoff. Give no final score, XP, league points, or reward for that incomplete attempt. Preserve completed fixtures and training results before any launch or mode transition.
Automatic result capture is the normal release path. Detect the actual final match state and authoritative score, including overtime, reconnects, and repeated packets. Commit each result and its rewards exactly once using stable fixture/session identifiers. A clearly labeled manual recovery screen may repair a missing result with provenance; it must not silently become the main gameplay loop.
8. Save model and recovery
Use a versioned local data model with atomic writes or transactions. Keep per-user data in the appropriate Windows AppData location, separate from installed read-only program resources. Saves, settings, generated match configurations, recordings, cache, and logs must not be written into Program Files or the source package.
Persist at least:
- Career identity/name, selected platform, schema version, and creation/update times.
- Team name/colors, recruit records, four active recruits, starting lineup, bot levels, and supported loadouts.
- Seasons, fixtures, round format, maps, seeds, difficulty decisions, simulation outcomes, and table inputs.
- Completed results, unique result/reward IDs, rewards, season history, and pending session details.
- Per-lesson assistance preferences, completed attempts, best recordings, recording metadata, and tutorial state.
- User control-display binding profile, accessibility settings, and compatibility observations.
Preserve the last valid save and support backup/export/import. Validate before replacing a valid file. Reject unsupported schema versions and malformed imports with a useful recovery screen, preserving the original bytes. Migrate the existing starter's schema if importing it, without losing pending fixtures or old results.
Test crashes between result receipt and save completion, duplicate end events, app restart during a fixture, corrupted saves, and repeated import. Prevent concurrent application instances from racing writes. Do not overwrite a player's existing career during installation or upgrade. Uninstall preserves user saves by default.
9. Training system and launch catalog
All training is optional, independently selectable, and available immediately. Build useful lessons on standard built-in arenas so Steam and Epic players can use the core training without downloading Workshop maps.
Implement these eight lesson groups, each with at least one functioning resettable drill and several approachable steps where useful:
Lesson	Required practice and feedback
Speed flip	Repeatable start and target crossing; show jump, diagonal dodge, opposing pitch/cancel, recovery, and landing events. Measure actual time and speed.
Flip reset	Approach, car orientation, underside/wheel contact with the ball, reset acquisition, then optional use of the gained flip. Include a setup that reduces the approach difficulty.
Ground dribble and flick	Controlled carry zone, sustained control, recoveries, and a chosen flick/target attempt.
Power shots	Repeatable incoming ball, contact timing, measured ball speed, and a clear target.
Shot placement	Selectable goal target zones, varied starting angles, measured hit/miss and shot location.
Fast aerial	Reach a defined aerial target, track jump sequence and boost use, distinguish an accidental backflip when evidence supports it.
Aerial and air-roll control	Reach ordered airborne gates and recover; left/right practice and selectable assistance.
Fast flight and recovery	Controlled route through standard-arena gates, time/completion, landing orientation, and a useful recovery observation.


These are skill drills, not claims that a single technique is mandatory in every match. Train ordinary physics. A special slowed demonstration or simplified starting setup must be identified and must not contaminate normal-speed records.
Use a data-driven lesson format containing a stable ID/version, description, required capabilities, starting state, reset/settle conditions, steps, target objects, success events, feedback rules, timeout, reference recordings, and assistance defaults.
For each attempt:
1. Establish the car/ball state, boost, orientation, and relevant velocity using supported state setting.
2. Wait until the reset has settled; clear any prior recording and stale input-edge state.
3. Start on a clear Ready/Go event or a defined first input.
4. Capture real game data/actions and timestamped skill events.
5. Show one specific, evidence-based observation and a useful next adjustment.
6. Allow immediate manual retry, or automatic retry when enabled.
Do not take control of the human car to make their attempt succeed. If demonstration mode drives a separate bot, clearly enter and leave that mode before the human attempt.
10. Assistance settings, input display, timing, and ghosts
Every lesson must independently remember:
- Ghost demonstration on/off.
- Step-by-step explanations on/off.
- Action/controller display on/off.
- Timing feedback on/off.
- Automatic reset on/off.
- Demonstration playback speed.
Include Skip Explanation and Restore Explanations. Changing one toggle must not implicitly enable another. Default settings should make the first attempt understandable and keep subsequent retries fast.
Input display: the documented game data exposes game actions such as jump, boost, pitch, yaw, roll, steer, throttle, and handbrake. These are not automatically the physical buttons or raw hardware stick values. Show action labels first. Offer Xbox/PlayStation/keyboard glyphs only after the user selects or calibrates a binding profile. Do not guess their custom air-roll/boost binding. [4–5]
Timing: compare actual action and movement events against a validated reference from equivalent initial conditions. For example, explain that an opposing pitch input occurred later than in the reference and show the measured times. Account for missing packets and sampling precision. Prefer game timestamps to arbitrary render frames. A successful alternative execution is not a failure merely because it differs from one demonstration.
Ghost: implement a genuine recorded-pose ghost with an oriented wireframe car through the documented rendering API; an optional path can supplement it. A path alone is insufficient because the player needs to see the car's pitch, yaw, and roll. Make the front, roof, and underside of the outline distinguishable. It must not collide with the player or ball. Synchronize its action display with recorded poses, allow replay and slower demonstration, and interpolate carefully. Rendering supports useful primitives; a textured translucent car mesh is not established by those primitives alone. Add mesh fidelity only if a supported mechanism is proven. [6]
Every recording stores its source, permission to distribute, game/framework version, car/hitbox, map, mutators, starting state, time base, action samples, pose samples, and success evidence. Compare only compatible attempts or clearly explain a mismatch.
A teaching reference must come from an actual successful execution and meet that lesson's conditions. Generate and validate one in the real game or import a permitted real recording. The player's recorded best attempt must be labeled Your Best Attempt, not Expert Demonstration. A mathematical animation or guessed button script is not proof that the technique works in Rocket League.
For flip resets, observing an available dodge is insufficient by itself. Establish evidence of the relevant ball contact and the transition that grants the reset; reject wall/ground-contact explanations. Where the API cannot prove the event confidently, report the observed contact/timing and uncertainty instead of a false pass.
Do not invent universal millisecond thresholds for speed flips. Keep tolerances configurable and validate them against multiple successful and unsuccessful attempts. Lesson completion should evaluate the intended outcome as well as the technique evidence. Save repeated attempts so improvement is visible without requiring a perfect score.
11. Optional review and coaching
Include a small optional review of measured training attempts and supported match events. Show the moment, observed evidence, and one actionable suggestion. Training review can replay the recorded reference and the player's path with input timing side by side or overlaid.
A chess-style perfect-move evaluator is not a first-release claim. Rocket League contains multiple reasonable actions and uncertain opponent decisions. Do not show fabricated centipawn-like scores, an "optimal play" label, or causality inferred from insufficient data. If a heuristic flags a likely double commit or risky challenge, explain what it observed and label the recommendation as a coaching suggestion.
The normal career loop always allows the next match immediately. Review and training never gate progress. Live feedback during ordinary official online matches is outside this release.
12. Cars, cosmetics, and community content
Use the installed game's ordinary car assets and physics. Do not bundle Rocket League executables, extracted models/textures, paid item packs, or EA assets in GitHub or the installer.
Provide a functioning bot garage based on verified supported loadout IDs and combinations. Show a practical curated catalog, validate selections, and fall back gracefully if the current game rejects an item. Human appearance defaults to the player's normal in-game garage. The documented bot loadout system does not establish a human inventory-grant or arbitrary human override API. [9,12]
Career cosmetic rewards can include original app badges, team themes, trophies, saved style presets, and supported local bot appearances. Label a local career reward as local. Never imply it becomes an item owned by the Steam/Epic account or usable in official online play. If a supported local human cosmetic route is independently verified, isolate it as an optional adapter and clearly describe its scope.
Provide a community content page with creator, skill category, original source/download link, license/permission note, supported launcher/loading route, dependency, and compatibility status. Promote creators rather than rehosting their work without permission. A Workshop link is not proof of Epic compatibility. The documented direct RLBot custom-map path has a Steam/Epic difference; check it against the current release and clearly label the actual supported route. [9]
Allow import of a locally obtained compatible map through a verified loader, with path and extension validation and a useful failure message. Do not bypass Workshop ownership or distribution controls. Missing external maps must never prevent core lessons or the career from working.
13. Play Online — exact behavior
Add a visible Play Online button to the app menu and career hub. Use the exact confirmation text:
Are you sure you want to close this and play online?

Provide Yes and No. Closing the dialog is No. Supporting text may explain that completed progress will be saved and an unfinished match will restart later.
No must leave the game session, career, and fixture unchanged. Do not begin shutdown unless completed progress has been durably saved. On save failure, leave the career session recoverable and show Retry. Handle an authoritative final-result event received during the transition exactly once, without losing it or converting it into an abandonment. Yes performs this ordered transition:
1. Freeze further career transitions and save completed progress, settings, and the current unfinished-fixture state.
2. Stop lesson resets, ghost rendering, input recording, and bot-control work for the career session.
3. Close the owned RLBot session appropriately.
4. Request normal, graceful closure of the Rocket League process associated with this career launch using a verified supported method or normal window-close behavior.
5. Wait for that actual game process to exit. RLBot framework shutdown alone is not evidence that Rocket League exited. [13]
6. Launch the selected platform's normal Rocket League entry with its normal EAC-enabled route and without the app's offline/bot launch arguments.
7. Report the observed transition honestly. A successful launch request means Opening Rocket League, not proof that matchmaking is available.
If closure times out, keep the save and offer Retry or an instruction to close the game. Do not launch a second conflicting session. Do not silently force-kill unrelated Steam/Epic/game processes. Do not change permanent platform launch options unnecessarily; if user settings prevent the normal launch, explain the specific issue without overwriting unrelated options.
Detect an already-running game at startup. Distinguish an owned career process from an unrelated or official-online session; do not attach career control to it automatically. Handle a launcher that returns immediately or spawns a child process. Track actual session ownership and process lifetime rather than assuming the launcher PID is Rocket League.
Implement and test a state machine covering Idle, Checking, Starting Career, Career Ready, Playing, Stopping Career, Waiting for Game Exit, Starting Online, Online Launch Requested, and Error/Recovery. The UI remains responsive and shows cancellable steps where cancellation is actually safe.
The confirmation is app-owned unless native integration is demonstrated. Preserve the user's exact wording without claiming that Epic supplies the dialog.
14. Multiplayer meaning and extension boundary
Mods are not inherently single-player. Minecraft lets users run server software, and community frameworks can modify server behavior, client behavior, or both. That enables shared modded worlds. Some server-only mods do not require matching client mods. [14–15]
For Rocket League, distinguish three layers:
1. The real game connection between human clients and the match host.
2. The bot-control connection receiving game state and issuing bot actions.
3. The career app's coordination of squads, settings, persistence, and results.
A remote RLBot socket addresses bot control; it does not by itself provide a multiplayer game server. The documented RocketHost service and RLBot LAN capabilities show that human-plus-custom-bot play is a real community direction. RocketHost currently documents a curated bot selection; that does not establish permission or APIs to upload our own bots, training scripts, or career logic. Its page alone does not prove our proposed integration's EAC behavior. [16–17]
Write a concise multiplayer investigation document grounded in current sources. A later two-captain mode would let each human control one car and choose bot teammates. Specify a host-authoritative fixture, compatible versions and bot manifests, one result commit, disconnect recovery, and clear save ownership. Validate an actual two-PC match on the current supported route before advertising it.
Do not make a hosted service, paid server, network relay, open firewall port, or account system a dependency of this first personal-career release. Do not call LAN-only documentation proof of a frictionless internet join-code system. Do not silently enable or charge for external hosting.
15. Implementation structure
Recommended starting stack: Python 3.11 or newer as required by the verified RLBot package, PySide6 with Qt Quick/QML for the desktop interface, an isolated RLBot worker process, and local versioned persistence. Resolve and lock actual compatible versions; do not treat an example pin as a compatibility guarantee. A different desktop stack is acceptable only if it materially improves the tested package and keeps the same requirements.
Separate modules for career rules/persistence, UI, launcher lifecycle, RLBot adapter, bot providers, training definitions/metrics/recordings, cosmetics/content catalog, and diagnostics. Keep most domain logic testable without the game. Use typed messages between the UI and worker, with clear request IDs, timeouts, cancellation, session ownership, and error reporting.
The packaged worker must use its own entry point, explicit worker mode, or a separate executable. In a frozen application, sys.executable may refer to the app executable rather than a Python interpreter; do not blindly run a .py file with it. Separate read-only resources from mutable data and test paths containing spaces and non-ASCII characters.
Inspect current v5 API signatures and schemas. Do not mix v4 and v5 examples. The reference starter's rlbot==2.0.0b56 is only a previously selected candidate; verify the current supported interface/core combination before using it. Read the SDK implementation when wiki examples are incomplete. [2–9,13]
Keep high-frequency telemetry and drawing from blocking the UI or disk. Bound recording memory, rotate logs, and handle dropped packets. Make a compatibility report containing app, game, core/interface, bot provider, launcher, and OS versions. Capture minimal useful diagnostics; omit credentials and private account identifiers from logs and exported reports.
Persist useful checkpoints during the build. Preserve unrelated existing work. Do not introduce placeholder buttons, fabricated SDK methods, fake success messages, or simulated match results in a screen that claims to show a real completed game.
16. Repository, Cursor Origin, and Windows distribution
Create or use the actual authenticated GitHub repository my-career-training. Discover the account/organization rather than inventing its name. Default to a public community code repository unless an existing private repository or explicit account restriction dictates otherwise. Do not overwrite an unrelated existing repository.
Cursor Origin is a repository-hosting/mirroring service, separate from the ordinary Git remote name origin. Keep public GitHub as the canonical community download/source location and create an inbound Cursor Origin mirror when the user's access permits it. Cursor documents origin repo create-mirrored OWNER/REPO; use the actual authenticated owner and returned clone URL. Do not replace a working GitHub remote with an invented Origin URL. Follow docs/REPOSITORY_SETUP.md and current official instructions. [18–20]
If GitHub/Origin authentication or access is missing, prepare the complete local checkout, source archive, and precise setup steps. Do not claim the remote or mirror exists. Never commit credentials, platform sessions, player saves, recordings without permission, .env files, game assets, generated environments, or downloaded proprietary binaries.
Include a Windows build pipeline with pinned dependencies, meaningful tests, and installer/portable packaging. Choose and document an appropriate license for original project code while preserving third-party notices and dependency obligations. Do not apply the project's license to Rocket League assets or community content it does not own.
A release must include a versioned Windows x64 installer and portable archive, original icon, desktop shortcut option, uninstall behavior, checksums, release notes, and installation instructions ordinary players can follow. Bundle permitted runtime dependencies so the player does not need Python, Git, Cursor, or a developer terminal. Rocket League and Steam/Epic remain separate prerequisites.
Do not rename a source ZIP to .exe or call it a ready-to-play release. Build Windows artifacts on Windows using a reproducible workflow. Treat unsigned builds honestly; do not claim a signature or publisher verification without it. Never tell users to disable operating-system protection as the default installation procedure.
Game updates can require adapter updates. Detect and explain actual incompatibility, preserve saves, and keep the app functional for management/review where possible. Do not guarantee all future Rocket League versions or install unsupported downgrades to conceal a compatibility problem.
17. Reference starter and existing work
The optional reference/terminal-starter directory contains a small Python integration reference. It is not the finished app.
It implements local roster selection, four recruited bots from five archetypes, a six-opponent schedule, manual result entry, pending-match handling, save validation/migration, built-in Psyonix bot configurations, and a candidate RLBot match launch. Its sixteen local tests cover save/configuration behavior; they do not establish Windows or game compatibility.
It has no implemented specialist brains, complete league table, training engine, ghost coach, desktop GUI, Play Online lifecycle, packaged installer, or verified human cosmetic override. Its old paths and subprocess assumptions need adaptation for an installed application. Reuse valid logic while replacing the product architecture where necessary. Never let the presence of the starter narrow this assignment to that starter's features.
18. Build order — continue through all steps
1. Inspect repository instructions, existing files, execution environment, game access, launchers, available SDK versions, and authenticated distribution access. Produce a compact capability checklist and proceed.
2. Establish the actual game adapter: one real human-plus-bots match and live telemetry on an accessible Windows installation. If game access is absent, build the adapter and test its contracts without pretending to have exercised the game.
3. Build the complete season/squad/save domain, UI, and launcher lifecycle. Keep fixture IDs and persistence semantics correct from the start.
4. Implement functional specialist bots and progression; integrate a challenging compatible provider where available.
5. Build the reusable training engine, all eight lesson groups, recording/ghost playback, settings, and feedback. Obtain and validate real teaching references where the environment permits.
6. Complete garage, local rewards, community content, accessibility, diagnostics, and optional review.
7. Verify the Play Online transition on each accessible launcher, including failure and cancellation paths.
8. Package Windows releases, run meaningful checks, fix failures, and update evidence/status documents.
9. Publish the actual source/release and configure the Cursor Origin mirror when authenticated access is available. Otherwise leave the complete local deliverable and exact remaining connection step.
Do not end after step 2 just because the first match worked. Do not spend the whole run on interface polish while leaving gameplay unconnected. Internal iteration is expected; claiming completion without evidence is not.
19. Acceptance checks and release evidence
Maintain a feature matrix with separate columns for Implemented, Locally Tested, Game Tested on Steam, Game Tested on Epic, and Remaining Dependency. Use dates and versions. A source link is documentation evidence, not a test result.
Required meaningful checks:
- Exactly one human and the correct number of teammates/opponents for each format; correct bench counts and between-match substitutions.
- Distinct role decisions in representative scenarios; general recovery/rotation remains functional; progression changes actual behavior.
- Full schedule/table/season conclusion; simulated fixtures are stable across restarts; mode changes preserve historical lineups.
- Normal match, overtime, disconnect, abandoned match, repeated result packet, and reward/save crash recovery; no duplicate results or rewards.
- Corrupt save preservation, supported migration, backup restore, import validation, and concurrent-launch handling.
- Every lesson resets to a defined state, captures the human's real actions, produces useful observed feedback, and retries without stale input/motion.
- Ghost synchronization and non-collision; teaching-reference provenance; personal-best labels; all six lesson assistance choices remain independent across relaunch.
- Flip-reset false positives and speed-flip timing under packet gaps and alternate successful execution.
- Play Online Yes/No/window-close, failed save, final-result arrival during transition, already-running game, failed graceful close, failed launcher start, and confirmed game exit before relaunch.
- Fresh Windows installation without Python; packaged worker starts correctly; paths with spaces; controller/mouse/keyboard access; installation upgrade preserves AppData saves.
- Steam and Epic runtime tests recorded independently. One successful launcher does not validate the other.
Do not create repetitive tests that merely restate the implementation. Stop expanding a test category once the concrete risk is sufficiently covered; spend the remaining effort completing unimplemented requirements.
20. Final deliverables and communication
Deliver:
1. The complete source checkout and actual GitHub URL if created.
2. A verified Cursor Origin mirror URL if created, otherwise its exact access/setup blocker.
3. Windows installer/portable artifacts if actually built, with checksums and release notes; a source archive labeled as source if no Windows build was possible.
4. A short player guide: install, start career, change lineup, choose training help, retry, save, and Play Online.
5. Architecture/build instructions, locked dependency versions, licenses/notices, compatibility report, and the feature evidence matrix.
6. A concise account of what worked in the real game, what only passed local tests, what needs access or recordings, and the next executable step for each remaining item.
Use short, plain progress updates. Explain choices in words a sixth grader could understand when talking to the player; keep engineering detail in repository documents. Ask only questions that materially block execution after inspecting the available context. Do not ask again about already-decided squad size, optional training, repository name, or the separate 22-player idea.
Begin implementation now and carry the full assignment as far as the actual tools and environment allow.
Primary references
These support integration facts and design research; product requirements above are decisions for this project. Recheck their current versions during implementation.
1. Epic EAC modes: https://www.epicgames.com/help/c-37599050/c-32343914/easy-anti-cheat-is-now-available-in-rocket-league-a10791900
2. RLBot core and releases: https://github.com/RLBot/core/releases
3. RLBot platform support: https://wiki.rlbot.org/v5/framework/operating-system-support/ and https://rlbot.org/faq/
4. Game data: https://wiki.rlbot.org/v5/botmaking/game-data/
5. Game-data schema: https://github.com/RLBot/flatbuffers-schema/blob/main/schema/gamedata.fbs
6. Rendering: https://wiki.rlbot.org/v5/botmaking/rendering/
7. State setting: https://wiki.rlbot.org/v5/botmaking/manipulating-game-state/
8. Python interface: https://github.com/RLBot/python-interface
9. Match configuration: https://wiki.rlbot.org/v5/botmaking/config-files/
10. Necto/Nexto creator documentation: https://github.com/Rolv-Arild/Necto
11. Current botpack: https://wiki.rlbot.org/v5/community/rlbot-pack/
12. Bot loadouts: https://wiki.rlbot.org/v5/botmaking/bot-loadouts/
13. Match lifecycle implementation: https://github.com/RLBot/python-interface/blob/master/rlbot/managers/match.py
14. Minecraft Java server: https://www.minecraft.net/en-us/download/server
15. Fabric client/server distinction: https://wiki.fabricmc.net/tutorial:side and https://wiki.fabricmc.net/community:serverside_mods
16. RocketHost: https://wiki.rlbot.org/v5/miscellaneous/rocket-host/
17. Remote bot-control distinction: https://wiki.rlbot.org/v5/framework/remote-rlbot/
18. Cursor Origin repository creation: https://cursor.com/docs/origin/create-repository
19. Cursor Origin GitHub mirroring: https://cursor.com/docs/origin/mirror-github
20. Cursor Origin CLI: https://cursor.com/docs/origin/cli/reference/commands
21. EA Player/Manager Career inspiration: https://help.ea.com/en/articles/ea-sports-fc/career-mode/
22. EA FC 26 career design examples: https://www.ea.com/games/ea-sports-fc/fc-26/news/pitch-notes-fc26-career-mode-deep-dive
Design inspiration from EA's documented distinction: Player Career follows one player; Manager Career manages the squad and development. This project's human-driver-plus-team-management design deliberately combines those ideas. Optional ungated training, six-round seasons, and bot personalities are our requirements, not claims that EA implements those exact rules. [21–22]
