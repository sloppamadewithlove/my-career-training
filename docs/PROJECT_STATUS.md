# Current project status

Updated 25 October 2026. Start here; older research and validation notes describe
individual checkpoints, not the current player's complete experience.

## Resume here

Latest live source candidate: `5fbe0c6`, incorporating the exact results Options
stack correction in `351afcd`. Its coherent build passed 41 native checks.
A real 0–21 result saved once; the corrected Options submenu retained the ended
match beyond 60 seconds. A later read-only recording shows results Return
cleanup, typed navigation and fresh `RootMenuMovie` READY in the same process.
The initiating input was not attributed and the arrival screenshot was refused
because the game was not foreground; this is not complete visual acceptance.
Direct Settings/Back and controlled saved-results Exit acceptance remain open.
Restarting the copied career preserved the previous Forfeit and 1–19 results
exactly once. The exact 5fbe CI inventory passed all 4,470 bundle files and nine
source archives; frozen gameplay has not been run and nothing is published.

The owner has now specified a new results flow: **Play Next Match, Schedule,
Change Preset, Settings, Exit**, in that order. Results Exit means return to the
My Career hub; its close-app control becomes **Quit My Career**. Schedule stays
inside the finished game without a time limit. Continuation offers a lineup
preview and starts the next fixture in the same owned game only after durable
cleanup and fresh native-root arrival. Implementation is in progress under
[RESULTS_CONTINUATION_CONTRACT.md](RESULTS_CONTINUATION_CONTRACT.md); it has not
passed live acceptance. Physical DS4 testing remains deferred at the owner's
request. Keep completed evidence below separate from these new controls.

## Download and source

The published `native-candidate-2026-10-24` ZIP from `2fed6cd` failed player
testing. The [correct website](https://my-career-training.vercel.app/) now shows
the repair status instead of offering that broken ZIP. The replacement is one
Windows test Setup executable, one player shortcut, and a private windowless
worker. Its exact frozen build must pass live acceptance before publication.

GitHub is canonical. The repair branch is `fix/windows-startup-and-download`;
[PR #7](https://github.com/sloppamadewithlove/my-career-training/pull/7) tracks it.
The main, pause and results integration is merged into that branch at `7e3338d`.
Repair commits and CI artifacts are not published player releases.

Work resumed from the
[complete session handoff](SESSION_HANDOFF_2026-10-24.md).
The completed native overlay/input-ownership fix is integrated at `3cdaad0`;
the actual Return destination still needs live acceptance. The historical partial
navigation snapshot was `dd1c176`, with an explicit WIP warning at `5c643f1`.
The resumed host implementation and all three rebuilt authored movies are now
integrated into the repair branch for full compilation and testing.
No replacement player release has been published. The resumed repair requires
a two-phase native consumption acknowledgement before typed shell navigation,
followed by current-generation frontend READY and actual `RootMenuMovie`
arrival. See the updated integration contract and acceptance checklist.

The host's four focused Return/protocol/match/session tests passed. Authored
movie composition, asset and candidate checks passed 109 tests with one skipped.
The first combined native build passed 27 plugin tests and 13 launcher/file-view
tests. A follow-up retires stale exit grants and adds negative regressions;
its four focused tests also passed. These are source/build checks only. The final
candidate, independent review and source/frozen gameplay sequence remain release
requirements.

Independent review found and repaired two delivery races before any new game
test: missing READY could resume an old execute grant after the movie discarded
it, and a lost issued log could permit a second exit. The host now revokes a
withdrawn consumption grant and separately latches successful execute publication.
Once delivery is uncertain, it retains Return without issuing another exit.
The final focused tests passed. Source `374c85d` then passed actual native Play,
Escape, keyboard Options/Back/Resume, unfinished Return confirmation cancellation,
and confirmed unfinished Return to a visible authored hub with fresh READY and
`RootMenuMovie`. A practice lesson started afterward in the same game process;
native Retry was accepted. The source tree passed 970 Python tests (15 skipped),
and its coherent native build passed 27 plugin and 13 launcher/file-view tests.
Its [installer pipeline](https://github.com/sloppamadewithlove/my-career-training/actions/runs/40214761643)
also passed, but that superseded artifact has not been downloaded or published.

A bounded delayed-cleanup test exposed a separate failure: Resume unloaded the
pause movie, and one SDK `OnOpenPauseMenu` call did not reopen it. Intent remained
pending. Ordinary Escape reopened pause and completed the typed Return to a
fresh native hub. The integrated follow-up removes that ineffective call and
retains the committed Leaving screen with bounded recovery controls. It also
deactivates the stock Party/Friends taskbar in pause/results, fixes confirmation
focus, and keeps recovery usable after an uncertain exit. Independent source
review, exact authored-binary rebuilds, 109 focused asset checks (one skipped),
and four focused native suites passed. This follow-up still needs a coherent
build and live source/frozen acceptance.

Integrated `714f3c2` passed the coherent 40-test native build, reopened the copied
saved 0–32 career, and visually removed Party/Friends from pause. Mouse Options,
Back and Resume worked. Its delayed-cleanup test still let Escape unload the
pause screen, bypassing the child-menu guard. Manual Escape recovery again
reached fresh READY and `RootMenuMovie`. A follow-up now guards the typed
document-screen close path and records fixed removal diagnostics. Direct
screen-manager/native removal may bypass that method too. Source `24a8bbe`
passed the next controlled test: the owned training worker was temporarily held,
Escape left the committed pause screen present, and resuming the worker completed
the exact acknowledgement and typed Return. A visible native hub, fresh frontend
READY and `RootMenuMovie` arrived in the same game process. This verifies the
observed delayed Escape path, not every possible native removal path. Its coherent
40-test native build and installer pipeline passed; the installer remains
unpublished and has not received live frozen acceptance.

Another real fixture on `374c85d`, started through native Play after practice,
saved its actual 0–32 score once, cleared its pending fixture, and acknowledged
the durable receipt. This mostly unattended score is not a skill assessment.
The later visual inspection found `TeamSelectMenuMovie`, not the authored
results screen. Later private-log review found results READY heartbeats followed
by the game's Finished-state timer expiry and automatic map travel about 68
seconds after EndGame. No results Return was observed. Saved-results Return
therefore remains unverified. The next test must observe the complete end-of-match
screen transition and the actual finished-state timers. Normal game closure restored the temporary
plugin/configuration files and preserved the original My Career files; ordinary
Rocket League save data changed and was not overwritten with the snapshot.

The next candidate adds read-only finished-state timer diagnostics. Sampling runs
on the game thread after owned offline scope and build verification, and status
readers receive a cache that expires after one second. Independent Luna review
found no issues; these diagnostics do not change match timing or scores and
still require coherent compilation and live observation.

Source `e5dec4c` subsequently completed a real fixture with its actual 0–24 result
saved once, pending fixture cleared and durable receipt acknowledged. The new
observations showed `GetbMatchEnded` true, a finished-state countdown from 60 to
1 while `EndGameMenuMovie` had fresh READY, then automatic travel to team
selection. `IsFinished()` stayed false throughout. No results Return click was
completed. A scoped saved-results countdown retention change is now implemented
for independent review and live testing; it does not change goals or match time.

The requested red Forfeit Match flow is also being integrated. It confirms a
permanent forfeited loss, preserves the score observed at that decision, clears
the pending fixture and advances the season before worker cleanup and typed
Return. Ordinary unfinished Return keeps its restart behavior. Domain/service,
menu, native-host and actual-game evidence remain separate; Forfeit and results
retention are not yet live-verified or published.

Integrated source `9d1d433` passed 1,016 tests with 15 skipped and Ruff. Its
coherent native candidate passed 28 plugin and 13 launcher/file-view checks.
These checks include the team-index, historical-receipt, timer scope and shared
fixture corrections; live Forfeit/results retention and exact frozen acceptance
remain open. Independent
review caught and corrected a telemetry team-order assumption, a timer binding
that could survive a stale observation gap, and a missing final READY check before
the timer setter. The native Forfeit handshake also accepted an actual service
snapshot produced with a fake worker; that is a contract check, not gameplay.

A separate normal Steam launch, with the test-owned injector closed and no
offline launch arguments, visibly reached Rocket League's original root menu
and was closed normally. Original My Career and checked plugin/configuration
files were restored. Ordinary game save changes are preserved. An online match
and full anti-cheat behavior remain unverified.

The current training input display uses logical game actions and configured
button labels; its right stick and D-pad are placeholders. A USB DualShock 4
player test reported insufficient visible button feedback. Community controller
display reuse is being investigated separately. Official plugin 707's current
archive has been inventoried, but physical-controller behavior, matching source
and redistribution permission are not established. No new community DLL has
been loaded or bundled.

Source `d95f4cc` passed actual red Forfeit confirmation/cancellation, saved the
observed 0–1 human loss once as a forfeit, advanced the schedule and reached the
visible authored hub with a fresh frontend READY in the same game process.
The next fixture started through native Play in that process. Pause, Options,
Back and Resume worked. That real fixture saved its actual 1–19 human result
once, cleared pending and acknowledged its durable receipt. These test scores
are not player-skill assessments. Forfeit persistence after app restart remains
to be checked on the next candidate.

The natural results screen stayed open beyond 80 seconds with observed countdown
refreshes. The longer results Options check then found an unhandled intermediate
stock screen: `OptionsEndGameMenuMovie` (Change Preset / Settings). The timer
guard recognized only `OptionsMenuMovie`, so it revoked retention and the game
travelled to `TeamSelectMenuMovie` after the remaining countdown. Saved data was
preserved. The actual saved-results Return button remains unverified. A narrowly
scoped classification fix and a repeated live Options/Return check are required.

`351afcd` implements that classifier correction with negative route tests. It
does not change save, event, READY or ownership requirements. Actual stack
contents and the corrected route still need live verification.

The exact `d95f4cc` Windows pipeline passed. Independent Luna verification matched
all 4,470 bundle files, nine source archives and the 178,249,099-byte Setup against
same-run inventories and hashes. That downloaded Setup has not been executed
or published; the observed Options failure supersedes it for frozen acceptance.
Physical USB DualShock 4 testing is deferred because the owner is unavailable;
do not replace that evidence with software key events.

The reusable [game-state skill](../skills/my-career-training-testing/SKILL.md)
and [development workflow](DEVELOPMENT_WORKFLOW.md) now preserve tested routes,
one input owner, explicit model/fallback choices and eight tracked speed
improvements. A private bounded milestone notifier is now implemented and has
observed actual results. Proposed short fixtures and automatic input ownership
remain unimplemented; no measured speedup is claimed.

## Verified observations

- The startup crash came from querying the original menu's file size while
  opening a larger private replacement. Exact-path attributes now describe
  the same private file as the open. Controlled game tests reached the menu
  without changing the installed package.
- The authored menu needed the original root initializer preserved and a
  wrapper around its renamed class. This Scaleform runtime reads the decoded
  Windows view path; its `file:///` loader and native JSON parser did not work.
  The menu now uses that path and a pinned BSD-licensed AS3 JSON codec.
- Live source `5535a2d` displayed all seven My Career routes in a Unicode
  profile. Native unfinished-fixture recovery preserved completed results and
  requeued the fixture. Career Rules changed the copied test career to 1v1.
  Starting the match then failed because no game data reached the worker.
- A controlled comparison isolated that connection failure: both `-noeac`
  and `-rlbot` prevented the game connecting. RLBot's official Steam arguments
  (`-rlbot`, fixed local controller endpoint, rate 240, `-nomovie`) connected
  before the start screen was dismissed. The official SDK opened a one-human
  practice field and received live packets. This proves the diagnostic
  connection, not the complete My Career workflow. See the pinned
  [official launcher](https://github.com/RLBot/core/blob/v5.0.0-rc18/RLBotCS/ManagerTools/LaunchManager/Steam.Windows.cs).
- The [Windows build for `5535a2d`](https://github.com/sloppamadewithlove/my-career-training/actions/runs/40142680788)
  passed its installer pipeline. Install/reinstall/uninstall checks use a
  disposable Windows runner and preserve its test career. That artifact
  predates the connection and pause/results repairs.
- Integrated source `7e3338d` again reached the seven-route native frontend in
  a Unicode test profile. Native recovery and Career Rules worked; a native
  Play Next Match click reached the worker's bot-loading stage. It then hung
  importing NumPy, before loading the Necto model. A read-only stack sample
  showed the session thread inside NumPy extension initialization while the
  command thread blocked on stdin. This matches the trigger described in
  [NumPy issue 24290](https://github.com/numpy/numpy/issues/24290). A controlled
  Pythonw/QProcess test reproduced the late-import hang; loading NumPy before
  reading stdin let the actual Necto controller initialize in about four
  seconds. GPT-6 Luna Max independently repeated both outcomes. `ba0618a`
  applies that worker-only fix and adds real redirected-entry regressions.
  The earlier standalone benchmark did not reproduce the pipe-backed setup.
- Both [native installer checks](https://github.com/sloppamadewithlove/my-career-training/actions/runs/40148712013)
  and [general Windows checks](https://github.com/sloppamadewithlove/my-career-training/actions/runs/40148714700)
  passed for `7e3338d`. The integration tree also passed 952 Python tests
  (15 skipped), 27 plugin tests and 13 native launcher/file-view tests.
  These passes do not resolve the live worker hang or certify match navigation.

The repaired source worker subsequently passed bot loading in the actual app,
but no game-to-core connection was observed and it timed out. A controlled
comparison then isolated another launcher problem: the native helper wraps all
four fixed options in quotes. With the same installed game, Steam identity,
official options, no injector and a ready core, the ordinary unquoted options
connected after 31 seconds; quoting every option produced no connection for
90 seconds. Both tests ran with Windows locked. This establishes the effect of
the overall raw formatting, not which individual option the game misreads.

The same unquoted control connected within half a second when its core started
45 seconds after the game, and reconnected within half a second after the owned
core restarted. Core-first startup and a persistent core are therefore not
required by this evidence. Neither these controls nor model startup by themselves
certify the mod's complete gameplay. `6381456` aligns the native command with the passing control:
the validated executable path stays quoted, the same four fixed options do
not, and the launch guard still requires the exact canonical command. The
independent launcher suite passed 162 checks; raw extra arguments, old quoting,
newlines and stray quotes remain rejected.

Integrated source `68448b7` then completed a real offline 1v1 in a copied Unicode
profile. Necto loaded and played; the actual 0–54 score persisted once with
`provenance: game`, the pending fixture cleared, and the durable receipt was
acknowledged. This mostly unattended test used a private bridge command to
start the match and ordinary replay-skip clicks near the end. Its score is not
a player-skill assessment. Actual Escape opened the authored pause menu;
Options/Back, Resume, and canceling the unfinished-return confirmation worked.
The authored results screen reached READY and displayed the saved-result state.

The actual results Return click exposed another failure: the SDK `disconnect`
left the match at `StartMenuMovie`, before the authored frontend. The legacy
fullscreen overlay then covered that title screen while native READY was false.
Service Idle, saved progress, and leaving the match did not establish a successful
return. The download remains held while this navigation and input-ownership
transition is repaired. No synthetic result or raw console return substitutes
for that missing native-menu acceptance.

The exact [`68448b7` Windows pipeline](https://github.com/sloppamadewithlove/my-career-training/actions/runs/40153114788)
passed source/native checks, frozen smoke, and installer lifecycle. Independent
Luna verification matched all 4,470 downloaded bundle files to the same run's
smoke inventory and verified nine corresponding source archives. Its Setup is
178,305,803 bytes, SHA-256
`bf8c047f2bc6d15144cd83fe101ff613cfff3c62d61329e6076d64a328844bf4`.
It has not passed frozen game acceptance and contains the observed Return bug;
it is not a replacement player release.

The later [`2a3f960` Windows run](https://github.com/sloppamadewithlove/my-career-training/actions/runs/40155909420)
has now completed successfully, including the installer job. Its evidence,
frozen bundle and installer/source artifacts were listed on resume; they were
not downloaded or used for a new gameplay test. CI success does not remove the
Return defect or the publication hold.

## Current integration

The connection fix removes conflicting `-noeac` from owned RLBot launches and
updates the Python, native-launcher and plugin checks. Normal Steam launch and
generic BakkesMod-only guidance remain separate. Fixed endpoint/rate, process
identity, executable hashes and original-file protections remain enforced.

Main, pause and results are separate movies. New pause/results classes retain
stock pause/input cleanup and expose career actions. Both authored bytecodes
were independently rebuilt to identical bytes, containing only project classes
and the public JSON codec. Private game SDKs and movies are not distributed.
Frontend `d426ea1` fits text after sizing its rectangle, preserves standings
rows, and separates an active match from unfinished-fixture recovery. Its
focused layout and preparation checks passed; readability still needs a live
check of the rebuilt movie.

Startup cancellation in `9ad1c8e` latches the timed-out activity, requests
shutdown and rejects late startup/telemetry messages. Models load before the
core is created, and cancellation shares the core-spawn lock. Only retained
owned process handles may be stopped. Real result receipts and failed cleanup
remain recoverable; the worker does not claim completion or disappear during
a post-core receipt write. The change passed 108 focused tests and independent
Luna review, with Grok's source design advice. It still needs frozen/live checks.

The bounded match-package writer preserves other exports and appends the
selected movie's new serial. Tests checked unchanged, grown and subsequently
shortened movies in both actual packages. Three-package composition/preparation
also passed without changing installed files. These are format/code checks;
live loading and native navigation still require acceptance.

Return and Retry bind to the current activity. Final score receipts must save
before the activity clears. Results offers Retry saving after a failure;
automatic receipt recovery also unlocks current results. Final Return navigation
is separate: shutting down RLBot alone does not open the game's frontend.

Actual GPT-6 Luna with max reasoning runs through Codex CLI for research and
independent checks. Actual Grok 4.7 High runs through Cursor CLI for difficult
implementation and review. Coordinators also implement alongside those reviews.
Agent participation is not gameplay evidence.

## Remaining live acceptance

1. Build/freeze one clean integrated revision with matching runtime receipts.
2. Open the player executable: one game, no worker console, readable menus.
3. In that exact frozen revision, complete a real 1v1 career fixture, save it
   once, return home and start the next activity without a second game process.
4. Test practice/retry, native pause/options/resume, unfinished-match
   confirmation, results saving/return, and keyboard/controller controls.
   Replacement menus must not expose online routes.
5. Restart and verify progress. Check installed files, player saves, temporary
   plugin restoration and the normal Steam launch boundary.
6. Publish only the exact tested Setup, hashes, required sources/notices and a
   sanitized receipt; update the existing website to that artifact.

CI retains the exact smoke-inventoried installer input as a separate developer
acceptance artifact. Check its complete inventory against that run's smoke
receipt before a game test. This lets a tester run the installer's files without
replacing an existing registered installation. The player download remains the
single Setup executable; the CI bundle is not the website download.

Target: Steam `25914621`, Rocket League `261013.63066.530866`, BakkesMod `229`.
Unknown builds are refused. Epic has no separate acceptance yet. Full cosmetic
coverage, expert demonstrations, no-idle-kick behavior and arbitrary community
plugins remain open. Necto/Nexto support up to 3v3; 4v4 uses Ground Specialists.
No current bot rank certification is claimed.

Use [BUILDING.md](BUILDING.md), [INTEGRATION_CONTRACT.md](INTEGRATION_CONTRACT.md),
[NATIVE_ACCEPTANCE_SESSION.md](NATIVE_ACCEPTANCE_SESSION.md) and
[REPOSITORY_PRIVACY.md](REPOSITORY_PRIVACY.md). Source tests, private diagnostics
and historical installer receipts are distinct from end-to-end game acceptance.
