# Current project status

Updated 6 November 2026. GitHub is canonical. No new release or owner-accepted
Gold playlist is available. The 29 October live receipts below remain historical;
exact `2c08e74` now has source/native/package checks and bounded offline live
observations. Exact `a59c45f` later passed the bounded native Training menu and
Back route; it did not verify editor gameplay or reset. Exact candidate `bd9336d`
was resumed after fresh process/foreground verification and confirmation of a
sole input owner: Escape opened the native pause and Resume returned to training.
End Training → Yes reached a native results screen at 0% waiting for the offline
Career service, with no usable controls and no hub return. The owned session was
closed gracefully; the original Career and local sequence hashes matched their
preflight values, three absent backup saves were restored create-new-only, and
changed current saves/profile files were preserved. This does not establish that
the whole game profile was unchanged. Those live observations do not establish
compatibility with the current executable after a Steam update. A read-only check
identified the installed file at build `26349479`, FileVersion `1.0.10897.0`,
SHA-256 `bcfb3233…`; the native diagnostic guard in source `9ee0c33` remains pinned
to the prior executable/build and fails closed on mismatch. Results repair
`df19252` at `9ee0c33` has candidate build/test/smoke evidence, but that candidate
was not launched after the update. The latest reported Bakkes-only standard Steam launch
without `-rlbot` was inconclusive.
Module access was unavailable and no fresh log was retained.
Plugin-loaded state, active EAC state and cause remain unknown. This does not
establish compatibility with the updated executable. Official BakkesMod release
`2.0.78 / RL2.78 / BM229`, published 20 October as an RL2.78 compatibility
update, provides later version-level metadata than its 28 April post-EAC notice;
it does not establish local plugin loading or compatibility with Steam build
`26349479`. The user prefers Steam stay online and permits gameplay only offline.
The owner now authorizes selecting `Without EAC` for offline mod testing if offered.
Actual EAC state is unverified. Steam Offline Mode is a separate client setting.
Whole-level retry/progression and full lesson/release acceptance remain open.

The owner's first requested playable skill is flip reset, with a toggleable
translucent-looking ghost car demonstrating the aerial approach and wheel
contact with the ball. No successful lesson-specific ghost recording or native
car renderer is accepted yet; see the task board for the current boundary.

| Area | Current evidence |
| --- | --- |
| Defender attribution | `d733917`, receipt clarified by `41d3730`: independently reviewed; all configured opponents participate in latest-contact credit; 232 focused checks passed; no live acceptance |
| Private prerecorded capture | `54fad04` + `cf1a0e4`: independently reviewed provisional experiment; 281 focused checks passed; retained 2c08 recordings had zero one-step clock intervals, so operator-entry expansion is held pending current-runtime cadence proof; no successful demonstration |
| Terminal-score source repair | `eb1be7d` / publication `ef94b24` on a separate branch: independently reviewed, 268 focused checks passed; no established cause or live fix for the earlier scenario transition |
| Native/package candidate | Exact `2c08e74`: shorter checkout resolved SDK include depth; 1654 Python checks passed/15 skipped, Ruff, 38 plugin CTests, 13 launcher checks, backend/native fixture and frozen smoke passed |
| Grand Champion live probe | Exact `2c08e74`: authored hub and GC Power Shots reached; no-input timeout captured defender touch; Up restored observed car/ball but score stayed 0–1; automatic second-scenario transition after timeout observed, cause unestablished |
| Gold content | `5258ab3`: twelve reference-derived shots from actual downloaded Poquito/Skogur packs; 269 targeted checks including the final persistence delta; not live accepted |
| Last GC gameplay probe | Exact `2c08e74`, distinct from later source-only repairs/experiments |
| Native clock | Tested 2c08 already includes integer synchronization; a historical sample showed HUD 0:01 while native SecondsRemaining was zero. Source binds the HUD to GameEvent.TimeRemaining; the same-attempt relationship and cause remain unestablished |
| Native Training handoff | Exact `a59c45f`: packaged/live Play → Training → Custom Training → Created; native Back returned to the responsive authored hub. Epic reconnect declined; no pack was created, but the actual game-profile primary changed and a rotated save was preserved; not byte-identical restoration |
| Native local editor and saves | Separate stock Created-editor visit reached local training without a pack download. Create defaults wrote `.Tem` and rotated the actual game profile before explicit Save; primary changed and was retained. Originals remain private |
| Native local timer/reset | Exact `a59c45f`: `0:10` → `0:07` after movement → later initial `0:10`; expiry is inferred, with no exact zero or native telemetry. Backspace at initial state showed no change; reset not accepted |
| Native pause repair | Reviewed fix `3b9ef72` on base `0bc322b`; exact candidate `bd9336d` passed 1,659 Python checks/15 skipped, 38 plugin and 13 launcher CTests, Return fixture and frozen smoke. Pause ABC hash matched staging/frozen. Live Escape → native pause → Resume passed on the earlier tested setup; updated-executable compatibility is unverified |
| Native results repair | Exact `bd9336d` End Training → Yes reached 0% results waiting for the offline Career service; no usable controls or hub return. Reviewed source repair `df19252` at branch head `9ee0c33`; candidate build, tests and smoke passed, but it has not been launched after the reported Steam update |
| Steam executable compatibility | Steam build `26349479`, FileVersion `1.0.10897.0`, and executable SHA-256 prefix `bcfb3233…` were read locally; three menu-package hashes were reported matching. Official BakkesMod `2.0.78 / RL2.78 / BM229` was released on 20 October with an RL2.78 compatibility update, later version-level metadata than its 28 April post-EAC notice. This does not prove local plugin loading or Steam-build compatibility |
| Launch route and injector check | Latest reported Bakkes-only standard Steam launch without `-rlbot` was inconclusive; module access was unavailable and no fresh log was retained. Plugin-loaded and EAC state are unknown. User prefers Steam online and permits gameplay offline only, including selecting `Without EAC` if offered. Injector graceful close failed; its verified test-owned PID was terminated |
| Config and save recovery | Temporary config override was conditionally restored; four backup saves were restored and one changed/new file preserved. No whole-profile unchanged claim. Cleanup of the exact test-config temporary was blocked by policy and it remains |
| Identity observer | Reviewed default-OFF observer and Windows junction-race correction (`8b6b5bf` + `3b4f34a`, source branch head `d64d5dd`); no live execution, EAC-state or compatibility proof |
| Native session restoration | Owned `bd9336d` session closed gracefully. Original Career and local sequence hashes matched preflight; three absent backup saves restored create-new-only; changed current saves/profile files preserved. Whole-profile unchanged is not claimed |
| Native draw experiment | Branch `8759a83` records independently reviewed source `a983c618`: pure diagnostic frame preparation; dedicated C++ check passed 1/1. SDK owner-scoped uninstall is static evidence only and unload concurrency remains unresolved. No drawable registration, live renderer, ghost, full plugin/package build or live test |
| 29 October repair evidence | Grounded reset/floor friction and transient command-read repairs passed repeated live resets; Training Return reached hub with copied Career unchanged |
| Completed GC-session shutdown | Exact `2c08e74`: Return reached hub; Quit acknowledgement did not establish exit; owned WM_CLOSE eventually closed game/app/helper, and original-save/plugin/config/game-file restoration checks passed; separate clock-run cleanup remains unverified |
| Career boundary | `af08455`: five saved-result guard and 41 continuation checks passed; explicit result choice retained |
| Privacy improvement | PR #11 integrated as `c14cb5d`, same tree as checked `c969569`: 25 privacy tests, scanner, Ruff and Windows CI passed |

The three-tab/rank route, saved-schedule Training access, live-match exit rule,
keyboard polling, queued retry/step acknowledgements and goal advancement exist
in source. The previous failed playtest remains evidence against readiness.
Manual timeout hold and generated-key retry are observed; one rapid retry hit a
command-file read failure; its read-retry repair passed a real Windows lock test. The next reset/Return repair has
160 focused passing checks and independent review. Other ranks still contain two
provisional shots each; the ultimate target remains twelve per lesson per rank.

Next runtime blockers: actual native countdown,
zero-time ball removal/restoration, Up whole retry and goal/Left/Right transitions
without kickoff. Physical controller acceptance is distinct from generated keys.
Thumbnails, Workshop arrival/return, Mods enable/disable, Garage, Options and Quit
regressions remain open. Production Mods is currently download-only.

The approved reference packs were downloaded and all 62 rounds decoded privately.
[Gold catalog and test receipt](evidence/2026-10-29-gold-reference-catalog.md) records
the selected twelve, provenance and limitations. No proprietary pack binaries or
extracted assets are shipped. The original eight-hour research is on branch
`research/rocket-league-2026-10-27`, folder `research to be applied/`.

The owner requests a ten-minute check and a 45-minute workflow improvement review
in this chat, including durable GitHub notes. The current session has no exposed
Codex automation control, so neither recurring schedule has been installed or
verified. On 6 November the owner explicitly approved a persistent goal for the
flip-reset lesson; it is active in the current chat and may continue at idle
boundaries. Active work can track the intervals, but timed or unattended runs
are not claimed without evidence. Earlier active-session history is in the
[active-session restart checkpoint](evidence/2026-11-06-active-session-restart.md)
and [native results checkpoint](evidence/2026-11-06-native-results-live-checkpoint.md),
plus the [Steam update compatibility checkpoint](evidence/2026-11-06-steam-update-compatibility.md)
and [Steam launch/config recovery checkpoint](evidence/2026-11-06-steam-launch-config-recovery.md),
plus the [observer and launch-mode catch-up](evidence/2026-11-06-steam-observer-launch-checkpoint.md).
The [flip-reset workflow review](evidence/2026-11-06-flip-reset-workflow-review.md)
records the 18:49 UTC active-session review and its evidence-based changes.
The [offline observer workflow review](evidence/2026-11-06-offline-observer-workflow-review.md)
records the 20:06 UTC review and the current live-test prerequisites.
Windows scheduling was not used. The earlier scheduled improvement task
delivered the integrated PR #11 privacy check. Main's build concurrency changes
preserve the active build and newest pending work. Neither is evidence of gameplay
readiness. The task board owns current agent assignments and release blockers.

[Reset and clock verification receipt](evidence/2026-10-29-reset-clock-verification.md) records independent checks and the remaining live boundary.

[Gold live retry receipt](evidence/2026-10-29-gold-live-retry.md) separates observed controls from the unresolved native timer, bounce and console-input defects.

[Input/Return follow-up](evidence/2026-10-29-input-return-followup.md) records the latest live defects, corrected source contracts and integrated heartbeat work.

[Reset/Return receipt](evidence/2026-10-29-gold-reset-return.md) records the full twelve-challenge pass, repeat-reset failures, measured response and corrected menu boundary.

[Defender-attribution receipt](evidence/2026-11-05-defender-shot-attribution.md)
records synthetic older/tied/later defender contacts and later Human recontact.
It does not establish real shooting geometry or defender usefulness.

[Private prerecorded-capture contract](BOT_REFERENCE_CAPTURE.md#private-prerecorded-input-experiment)
records the fixed 120 Hz interpretation and differing reset/origin assumptions.
No external inputs are bundled. Ownership, marker, bot mapping, Human clearance,
strict observation and private persistence gates remain; the new profile cannot
pass the existing reference evaluator or become a teaching ghost automatically.

[Session improvement receipt](evidence/2026-11-05-session-improvement.md) records
the applied dispatch-test, Windows-path and bounded-research workflow changes.

[Second-cycle receipt](evidence/2026-11-05-session-improvement-cycle-2.md) records
completed package checks, bounded live observations and the next reset/progression
and shutdown proofs. Source, package and live evidence remain separate.

[Third-cycle receipt](evidence/2026-11-05-session-improvement-cycle-3.md) records
why clock-field correlation and actual packet-cadence screening precede more code.

[Fourth-cycle receipt](evidence/2026-11-06-session-improvement-cycle-4.md) records
the Custom Training route, its save side effect and recovery, the unresolved clock
lead, and the missed-review catch-up.

[Native-training catch-up receipt](evidence/2026-11-06-native-training-catch-up.md)
records the exact native handoff, editor write side effect, timer/reset limits,
reviewed pause fix and packaging prerequisites.

[Native-pause focus checkpoint](evidence/2026-11-06-native-pause-focus-checkpoint.md)
records candidate checks and the live focus stop; it is not native-pause acceptance.

[Active-session restart checkpoint](evidence/2026-11-06-active-session-restart.md)
records the idle-to-active restart, current read-only gate and source-only drawing experiment.

[Native results live checkpoint](evidence/2026-11-06-native-results-live-checkpoint.md)
records the resumed pause/Resume pass, blocked native results route, save recovery,
and the source-only results repair/build boundary.

[Steam update compatibility checkpoint](evidence/2026-11-06-steam-update-compatibility.md)
records the reported upstream executable change, current launch stop and exact
compatibility evidence still required.

[Steam launch/config recovery checkpoint](evidence/2026-11-06-steam-launch-config-recovery.md)
records separate launch-route evidence, configuration/save recovery, and the
pending identity-only probe.

[Steam observer and launch-mode checkpoint](evidence/2026-11-06-steam-observer-launch-checkpoint.md)
records the reviewed junction-race correction, latest inconclusive Bakkes-only
launch, actual-state limits, recovery and the next owner-gated observation.
