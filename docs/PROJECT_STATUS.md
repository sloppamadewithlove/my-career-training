# Current project status

Updated 6 November 2026. GitHub is canonical. No new release or owner-accepted
Gold playlist is available. Exact `2c08e74` has completed developer candidate
checks and a bounded GC live probe. Exact `a59c45f` was subsequently packaged and
passed the bounded native Training menu handoff. Exact `bd9336d` later proved
stock native pause/Resume, then exposed a blocked training-results screen after
End Training. Reviewed results repair `df19252` is source-only. These native
probes did not exercise the included MCT terminal-score repair `eb1be7d`.

Steam has since updated the installation to build 26349479 and a new executable
hash. The three menu package pins still match, but normal MCT correctly refuses
the executable. A reviewed, default-OFF identity observer with a protected fixed
per-process rendezvous is available; this new candidate has not been loaded and
proves no compatibility or anti-cheat state.

The owner's current direction is to reuse Rocket League's native training flow,
maps, HUD and behavior, with custom lesson and ghost additions. The additive hub
handoff below now has live menu arrival/return evidence; existing Career lessons
remain available. The full native gameplay/reset/exit loop and controller
acceptance remain open.

| Area | Current evidence |
| --- | --- |
| Native Training handoff | Exact packaged `a59c45f`: first menu-only run reached stock Play, Training, Custom Training Created and responsive authored-hub Back; no pack created/saved; physical controller untested |
| Native-entry package | Exact `a59c45f` candidate and frozen smoke passed; source `1c21770` + `d98ba04` independently reviewed; authored ABC hash and package provenance verified |
| Native local sequence probe | Exact `a59c45f`: existing local sequence entered native Striker; W moved car/ball with 0:07 shown, later initial scene at 0:10 suggests timeout reset; Backspace at initial state gave no reset proof; Escape showed MCT pause with disabled Return and no native exit |
| Native stock pause | Reviewed source `3b9ef72`; exact packaged `bd9336d` showed stock native pause and Resume; End Training/Yes reached results, not the hub; Career pause regression remains open |
| Native results blocker/repair | Exact `bd9336d`: training 0% results had no usable controls and waited for the offline Career service while backend Idle; reviewed `df19252` delegates offline native TRAINING/editor results to stock; 112 Python checks/one skip, compiled selector and three native test binaries passed; new repair not packaged/live tested |
| Updated Steam build | Build 26349479, executable `bcfb3233…bd1c`; embedded Psy-build hypothesis `261031.63733.533021`; official Bakkes 229 updater lists the build; actual SDK result and MCT compatibility remain unverified |
| Development identity observer | Reviewed `7f3a9a5`, following `8b6b5bf` + `3b4f34a`; default-OFF DLL uses a protected OS-known-folder/PID/FILETIME rendezvous without inherited environment; exact identity/argv/nonce lease and four getters retained; 3 native CTests/27 Python checks passed; new candidate not loaded, no compatibility/readiness/anti-cheat proof |
| Defender attribution | `d733917`, receipt clarified by `41d3730`: independently reviewed; all configured opponents participate in latest-contact credit; 232 focused checks passed; complete live attribution acceptance remains open |
| Terminal-score source repair | `eb1be7d`: independently reviewed; 268 focused checks passed; included in packaged `a59c45f` but not exercised by its native UI/sequence probes; original live transition cause remains unverified |
| Developer candidate checks | Exact `2c08e74`: 1654 Python checks passed/15 skipped, Ruff, 38 plugin CTests, 13 launcher checks, backend/native fixture and frozen smoke passed after using a shorter exact-commit worktree |
| GC live probe | Exact `2c08e74`: two provisional situations; no-input timeout recorded defender contact; Up restored observed car/ball, score stayed 0–1; automatic 1/2 to 2/2 transition observed without navigation input; cause unestablished |
| Gold content | `5258ab3`: twelve reference-derived shots from actual downloaded Poquito/Skogur packs; 269 targeted checks including the final persistence delta; not live accepted |
| Last tested candidate | Exact `bd9336d`: native pause/Resume passed, End Training exposed blocked results; run closed/restored; later results repair and docs are not this tested binary |
| Native clock | Exact `2c08e74` timed out while the visible native clock remained at 0:01; correct zero display/hold remains unverified |
| 29 October repair evidence | Grounded reset/floor friction and transient command-read repairs passed repeated live resets; Training Return reached hub with copied Career unchanged |
| Shutdown/restoration | Exact `2c08e74`: Quit acknowledged but game remained after seven seconds; owned graceful WM_CLOSE fallback eventually closed game/app/helper; relevant processes gone, original saves and plugin/config/game-file hashes matched pretest baselines; authored Quit completion remains unaccepted |
| Native-entry restoration | `a59c45f` game exited; original MCT Career, game Training/Config, BakkesMod plugin/config and checked game assets matched baselines; game profile rotation was preserved and missing backups restored without overwriting new saves; no byte-identical profile claim |
| Native-pause restoration | `bd9336d` owned processes exited; original/isolated MCT careers, sequence, checked plugin/config and game assets matched preflight; changed game saves/new profile files preserved, three absent backups restored create-new-only; no unchanged whole-profile claim |
| Career boundary | `af08455`: five saved-result guard and 41 continuation checks passed; explicit result choice retained |
| Privacy improvement | PR #11 integrated as `c14cb5d`, same tree as checked `c969569`: 25 privacy tests, scanner, Ruff and Windows CI passed |

The three-tab/rank route, saved-schedule Training access, live-match exit rule,
keyboard polling, queued retry/step acknowledgements and goal advancement exist
in source. The previous failed playtest remains evidence against readiness.
Manual timeout hold and generated-key retry are observed; one rapid retry hit a
command-file read failure; its read-retry repair passed a real Windows lock test. The next reset/Return repair has
160 focused passing checks and independent review. Other ranks still contain two
provisional shots each; the ultimate target remains twelve per lesson per rank.

Next runtime priority: obtain a fresh owned identity observation with the reviewed
observer, then review that evidence before a new native-menu compatibility trial.
Normal executable gates remain unchanged. See the
[fixed-rendezvous receipt](evidence/2026-11-06-observer-fixed-rendezvous.md)
for the protected owner/ACL preparation and observation limits.
After compatibility is established, stage/build results repair `df19252`, prove
native End Training results controls and the chosen restart/browser/main-menu
destination, plus Career results/Return and pause regressions. Observe a
displaced-state native reset separately; retain the accepted stock Play/Training
handoff and bounded `bd9336d` pause/Resume evidence. See the
[results receipt](evidence/2026-11-06-native-training-stock-results.md).
Retained custom-lesson blockers: actual native countdown,
zero-time ball removal/restoration, Up whole retry and goal/Left/Right transitions
without kickoff. Physical controller acceptance is distinct from generated keys.
Thumbnails, Workshop arrival/return, Mods enable/disable, Garage, Options and Quit
regressions remain open. Production Mods is currently download-only.

The approved reference packs were downloaded and all 62 rounds decoded privately.
[Gold catalog and test receipt](evidence/2026-10-29-gold-reference-catalog.md) records
the selected twelve, provenance and limitations. No proprietary pack binaries or
extracted assets are shipped. The original eight-hour research is on branch
`research/rocket-league-2026-10-27`, folder `research to be applied/`.

The saved desktop task **Improve My Career Training** runs every 45 minutes;
Windows scheduling was not used. Its delivered change is the integrated PR #11 privacy
check. Main's build concurrency changes preserve the active build and newest
pending work. Neither is evidence of gameplay readiness. The task board owns
current agent assignments and release blockers.

[Reset and clock verification receipt](evidence/2026-10-29-reset-clock-verification.md) records independent checks and the remaining live boundary.

[Gold live retry receipt](evidence/2026-10-29-gold-live-retry.md) separates observed controls from the unresolved native timer, bounce and console-input defects.

[Input/Return follow-up](evidence/2026-10-29-input-return-followup.md) records the latest live defects, corrected source contracts and integrated heartbeat work.

[Reset/Return receipt](evidence/2026-10-29-gold-reset-return.md) records the full twelve-challenge pass, repeat-reset failures, measured response and corrected menu boundary.

[Defender-attribution receipt](evidence/2026-11-05-defender-shot-attribution.md)
records synthetic older/tied/later defender contacts and later Human recontact.
It does not establish real shooting geometry or defender usefulness.

[Terminal-score repair receipt](evidence/2026-11-05-terminal-goal-progression.md)
separates the reproduced source defect from the unexplained live transition.
The stored live attempts had equal starting/terminal scores; per-command and
post-completion score chronology was not retained. Cumulative scoreboard
persistence is unchanged and is not established as a separate product defect.

[Stock Training entry receipt](evidence/2026-11-05-stock-training-entry.md)
records the exact stock callback, saved inactive Career correction, authored ABC
provenance and exact `a59c45f` live menu/return proof. Earlier separate stock editor
exploration and this menu-only run do not establish MCT native lesson gameplay.

[Native stock-pause receipt](evidence/2026-11-05-native-custom-training-stock-pause.md)
records the separate local sequence probe, its timer/reset limits and the reviewed
source-only delegation repair. Its actual native exit destination is unverified.
