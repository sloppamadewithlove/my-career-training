# Session handoff — 25 October 2026

This is the latest pause checkpoint. Read it before the historical
[24 October handoff](SESSION_HANDOFF_2026-10-24.md). Do not restart the project,
reopen completed investigations, merge the old partial Return branch, or call
the current candidate a published release.

## Owner's next direction

The owner paused the session and requested a fresh main agent. Next product
focus: **Training and Workshop**. First inspect the existing capabilities and
known limits, then ask the owner what exactly they want improved in those two
areas. Do not assume the priority is only another menu redesign.

The owner accepted the workflow refinements and set a **12-second target** for
results Play Next Match. The exact frozen e41 observation was about 26 seconds;
the target has not been achieved. Keep direct one-click continuation and all
save, ownership, cancellation and fresh-arrival safeguards. Profile the phases
before changing startup behavior.

## Mission and current player decisions

My Career Training is a Windows offline career/training mod inside the player's
existing Rocket League. Deliver one understandable Setup, one shortcut, the
game's native menu style, and an automatic private worker without a console.
BakkesMod is the bridge and RLBot supplies bots; reuse those frameworks.

Career includes one human with four persistent bot squad members, 1v1–4v4,
editable lineups, clubs, seasons, standings, progression and real saved results.
Training is optional. The broader product includes mechanics practice,
evidence-based coaching, honest ghost demonstrations, PlayStation-style input
feedback, Garage, Workshop and Community. Do not claim arbitrary cosmetics,
expert recordings, certified bot ranks, plugin compatibility or Epic support
without evidence. Ordinary Steam Rocket League must remain available separately.
Offline Career must not offer actionable Casual, Competitive, Tournaments or
store routes.

Latest controls, superseding older preview/confirmation plans:

- Home closes through **Quit My Career**.
- Pause includes Resume, Game options, Return to My Career, and red Forfeit Match.
- Unfinished Return has a Back-first confirmation and leaves the fixture
  replayable without awarding a result.
- Forfeit has a separate Back-first confirmation, saves a labelled loss once,
  advances the schedule, preserves the observed score, and returns to the hub.
- Results order is **Play Next Match, Schedule, Change Preset, Settings, Exit**.
- Results Exit returns to the My Career hub.
- Play Next Match uses the saved lineup and starts from one click, without a
  preview/setup screen or second Start confirmation. Squad remains available
  separately to change lineups.
- Schedule stays on the finished match, without a player-facing time limit.
- Preset uses existing local game presets; Settings opens the actual Settings.

## Canonical locations and reading order

Repository: https://github.com/sloppamadewithlove/my-career-training
Repair branch: fix/windows-startup-and-download
Draft PR: https://github.com/sloppamadewithlove/my-career-training/pull/7
Existing website: https://my-career-training.vercel.app/

Read AGENTS.md, PROJECT_STATUS.md, BUILD_SPEC.md, BUILDING.md,
INTEGRATION_CONTRACT.md, RESULTS_CONTINUATION_CONTRACT.md,
DEVELOPMENT_WORKFLOW.md, NATIVE_ACCEPTANCE_SESSION.md and REPOSITORY_PRIVACY.md.
Paths without a directory prefix in that list are under docs except AGENTS.md.

The previously broken ZIP is held behind the existing site's repair notice.
No replacement Setup was published and this pause does not authorize a
player-ready claim. The tested executable candidate is
e41ad45261af205f7b228e6247e34b271cce7fc9. Later documentation checkpoints do not
change that binary identity; 9d563a4 recorded its first live findings.

## What this session completed

1. Integrated the Return repair across service/host, protocol, authored
   ActionScript, compiled movies/pins and tests. Navigation now uses the verified
   typed Shell.ExitToMainMenu after the exact durable acknowledgement, with
   separate authorization, consumption, attempt and actual arrival states.
   Success requires fresh frontend READY and real RootMenuMovie in the owned
   game. The legacy fullscreen overlay remains blocked during loading gaps.
2. Retained activity-bound intent through cleanup and stale-view rejection.
   A bounded live test found SDK OnOpenPauseMenu did not open the pause movie;
   do not reintroduce that assumption. Ordinary Escape is the known recovery
   route where appropriate.
3. Implemented red Forfeit and durable labelled-loss semantics. Independent
   review corrected team-index, historical receipt and timer-scope issues.
4. Repaired results retention. The intermediate OptionsEndGameMenuMovie had
   exposed an expiry path; the host now covers the actual screen stack.
5. Implemented the ordered five-button results menu, local Schedule paging,
   typed local preset/Settings routes and home Quit My Career.
6. Implemented direct continuation in 9acc305. Results dispatch preparation
   directly using the saved lineup; the extra preview was removed. Exact
   prepare/cleanup/root/one-shot-start checks remain.
7. Integrated the authored menu single-gesture guard at e41ad45 (designer
   implementation d8e8bf2): matching control/input PRESS before CLICK,
   consumption once, disarm on refresh/removal/release-outside, deferred refresh.
   Earlier unexplained page movement included possible player interaction;
   do not claim a previously reproduced click-through bug or proven live cause.
8. Created and exercised the reusable testing skill and workflow. Private
   bounded observers record real milestones. The opt-in OneGoal source harness
   reaches genuine results quickly and explicitly refuses frozen/CI use.
9. Built coherent candidates, verified matching native/ActionScript artifacts,
   checked CI inventories and completed the exact frozen gameplay described below.

Earlier work inherited from 24 October remains repaired: private package sizes,
native menu loading, conflicting launch options, NumPy-before-stdin windowless
startup deadlock, and fixed native argument quoting. Do not repeat those probes
without new contrary evidence.

## Evidence: keep the layers separate

### Source, native and artifacts

- Earlier ff3ee52 full source suite: 1,057 passed, 15 skipped; Ruff passed.
- Coherent e41 native build: 42 checks (29 plugin, 13 launcher/file-view), passed.
- Direct-start independent Luna/max: four focused native tests passed; an
  actual Backend/FileBridge synthetic fixture also passed the native gates.
- Menu artifact revision d8e8bf2, integrated at e41: 109 checks passed, one
  skipped. Independent rebuilds of root/results ABC were byte-identical.
- Fifty private gesture checks execute a supported AS3-method subset with event
  doubles; they are not Flash-runtime or physical-controller tests.
- Requested Grok review of direct-start did not finish within its bound.
  No quota error or fallback occurred. Do not claim Grok approval.
- A nonblocking conditional release-outside/input-index edge remains documented
  in the private menu review. Arbitrary devices are not certified.

### Source gameplay

Earlier source revisions exercised practice/Retry, actual native Play, Escape,
Options/Back, Resume, unfinished Return cancellation/confirmation, delayed
cleanup, Forfeit, real saves and normal home Quit/restoration.

On ff3 OneGoal, Schedule stayed beyond 106 seconds and Settings beyond
175 seconds; their actual Back routes returned to the finished game.
On e41 OneGoal, one actual results click started another fixture in the same
game with no extra input. Two real human 0–1 results saved once and were ACKed.
Existing preset selection/equip and restoring the original worked; mouse Back,
Escape Back, actual results Exit/fresh visible hub, and home Quit passed.
These shortened fixtures are development evidence, not normal timed acceptance.

### Exact frozen e41 gameplay

The package's own app, worker and RLBot server hashes matched the same-run
inventory. Independent actual Luna/max verified owned identities, fresh bridge
scope and the first durable game result. It observed no visible owned console
window at its snapshots; this is not a guarantee about all transient windows.

- Actual native Play started a normal timed offline 1v1 in a Unicode copied career.
- Actual pause, Game options/Settings, Back, Resume and cancelling unfinished
  Return worked. No score was invented or manually written.
- The real human 0–22 result saved once with game provenance; pending cleared
  and durable receipt was acknowledged. It is not a player-skill assessment.
- One actual results click at 23:24:28 UTC initiated exact cleanup, typed travel,
  fresh RootMenuMovie READY and the next Playing state at about 23:24:54.
  Same game process; no setup/preview or second input.
- In the second fixture, Forfeit Back preserved the active fixture. Explicit
  confirmation saved the observed human 0–2 as a labelled forfeited loss and
  reached the visible authored hub with fresh READY. The first result remained.
- Actual home Quit closed the first game/service normally.
- A second package launch copied that saved career and reached the title.
  The owner paused before the visual career/schedule restart check. **Restart
  acceptance is unfinished**; do not convert launching/copying into a pass.
- Current-package practice/Retry/delayed cleanup, standalone results Exit,
  every results subpage, real DS4 routes and final normal-Steam boundary still
  require their appropriate remaining checks. Earlier source evidence is useful
  but must remain attributed.

The first independent runtime probe guessed incorrect record schemas/path and
produced invalid negatives. It was stopped; the corrected exact-schema Luna
pass succeeded. Preserve the invalid probe as a reviewer error, not a game failure.

## Exact package and CI

Native run: https://github.com/sloppamadewithlove/my-career-training/actions/runs/40241444926
Windows run: https://github.com/sloppamadewithlove/my-career-training/actions/runs/40241449730

Both succeeded for exact e41. Independent Luna/max verified all 4,470 bundle
files and nine source archives, plus linked Setup/build/lifecycle records.
Setup is 178,282,685 bytes.
SHA-256: 3d29d1d705827dfbf964b64acc09755534257f91cc44cfb85bac71a909940156

The local gameplay used the verified, identical CI installer-input bundle; the
Setup executable itself was not installed locally. CI installer lifecycle is
separate evidence. Do not offer the developer bundle as the player download.

A transfer appeared stalled, but completed before cancellation; cancellation
interrupted extraction verification. All three completed ZIP digests were
rechecked, interrupted extraction retained, fresh extraction verified, and the
independent audit passed. No mixed/incomplete package was launched.

## Agents, skills and useful working rules

Main owns architecture, integration, privacy, acceptance and GitHub. Main alone
controls the game unless an explicit acknowledged ownership handoff is recorded.
Read-only agents can inspect evidence concurrently; do not compete for focus.

Requested roles:
- GPT-6 Luna max through actual Codex CLI: testing, research, artifact audits.
- Grok 4.7 High through actual Cursor CLI: code/advice/review. Switch to GPT-5.6
  Sol high only after actual Grok quota exhaustion, not an incomplete review.
- Claude Opus 5.5 high through actual Cursor CLI: design/buttons/assets. On quota
  exhaustion stop the designer and maintain OPUS_DESIGN_BRIEF.md.
- GPT-6 Astra low: independent workflow/evidence audit.

Verify actual model/effort in session output; role names and requested flags are
not proof. The local handoff lists receipts. No quota exhaustion was observed.
One workflow review lacked independent runtime model attestation; do not label
that pass as a verified Astra invocation. Do useful bounded work, not quota
burning. Separate files/worktrees and have main integrate once.

Use skills/my-career-training-testing/SKILL.md. Its state routes and
evidence/recovery reference are installed locally too. The skill now includes
12-second timing phases, immutable package reuse, idle-menu recovery and current
evidence. Private helpers stay outside GitHub; their location map is private.

Use copied careers, record PID + creation + executable, and require foreground
before each input/screenshot. Respect physical input takeover. Never blindly
retry inputs or relabel dispatch/Idle as arrival. Keep raw logs, saves, account
screenshots, personal paths and game assets private. Set per-process TEMP/TMP
to a working Windows temporary folder and PYTHONPATH to the intended checkout
when using the older shared venv.

## Training and Workshop: what the fresh agent should ask

The owner uses a **PS4 DualShock 4 by USB**. Physical testing was deferred at
their request. Current training HUD shows logical game actions; D-pad/right
stick are placeholders, and the owner reported insufficient button feedback.
Plugin 707's official archive was inventoried; matching source, redistribution
permission and physical behavior are not established. No new community DLL
was loaded or bundled. Reuse may be appropriate after license/capability review,
not simply because the catalog has a download.

Training already has lessons, assistance/settings, Retry and recording/ghost
machinery. Review BUILD_SPEC.md and current code before selecting improvements.
Do not present synthetic motions or a player's ordinary recording as an expert
demonstration. The prior source practice route works; broader mechanics quality,
instruction clarity and physical input need deliberate testing.

Workshop has browsing, local discovery/import and favorites. Distinguish the
Python library from the native development trial: the RLBot custom-map path is
refused because it replaces an installed map. The native trial prepares a
bound load_workshop route with retained file holds, but its game-tested and
production gates remain false. An accepted console dispatch is not map loading
or proof that installed files stayed untouched. Read WORKSHOP_LIBRARY.md,
WORKSHOP_DIRECT_LOAD.md, NATIVE_WORKSHOP_LAYOUT.md and NATIVE_WORKSHOP_LAUNCHER.md.
Ask which installed maps and which browsing/loading improvements matter first.

Suggested opening after reading: explain these existing capabilities briefly,
then ask which Training changes (input display, lesson instructions, Retry,
real demonstrations or specific mechanics) and Workshop changes (browse,
favorites, importing or verified map launching) the owner wants prioritized.
Ask for their actual goals; do not require them to restate the entire project.

## Pause state and next actions

Owned game/app/worker/core and owned BakkesMod helper are closed. The restart
game closed normally at the title. Its expected "closed before menu" dialog
kept the service alive until normal dismissal; a private orderly quit request
was also issued. This is pause cleanup, not a successful menu Quit test for
that restart. Original career files, checked game/BakkesMod configuration,
plugin and installed game/package hashes match the baseline. Ordinary Rocket
League save rotation/changes were preserved. No live agent should be assumed
to own input on resume; inspect fresh processes.

1. Read this handoff and the private prompt, inspect HEAD/tree/host/processes;
   preserve the exact tested e41 package and current source.
2. Ask the owner for Training/Workshop priorities from the current capability
   picture. Continue independent source review while awaiting their answer.
3. Profile continuation against the 12-second target with stable start/end
   definitions, cold/warm runs and individual phase timings. Do not promise it
   or remove durable save/root barriers to hit a number.
4. Finish the interrupted copied-career visual restart check and the remaining
   exact-package/input/restoration checks when appropriate to the next batch.
   A normal Steam original root was visually checked earlier in this session;
   do not call that online-play/anti-cheat certification or a final e41 check.
5. Implement the chosen Training/Workshop slice in separate scopes, run focused
   checks, integrate one coherent candidate and test its actual native route.
6. Publish only the exact fully accepted Setup with required sources/notices,
   hashes and sanitized evidence, then update the existing Vercel site.

No player release is authorized by partial acceptance. The next agent should
continue from these results, not rerun the original startup/Return research.
