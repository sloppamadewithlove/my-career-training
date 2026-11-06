# Current project status

Updated 5 November 2026. GitHub is canonical. No new release or owner-accepted
Gold playlist is available. Exact `2c08e74` has completed developer candidate
checks and a bounded GC live probe. The later terminal-score repair `eb1be7d`
is independently reviewed and source-tested; it has not been built or live-tested.

The owner's current direction is to reuse Rocket League's native training flow,
maps, HUD and behavior, with custom lesson and ghost additions. The additive hub
handoff below is the next candidate; existing Career lessons remain available
while its native arrival and return are unverified.

| Area | Current evidence |
| --- | --- |
| Native Training handoff | `1c21770` + `d98ba04`: independently reviewed source and compiled authored movie; **Rocket League Training** opens stock Play, then the player chooses Training; 110 Python checks/one skip, five Release CTests and two rebuilt correction CTests passed; no plugin/app package or live MCT handoff acceptance |
| Defender attribution | `d733917`, receipt clarified by `41d3730`: independently reviewed; all configured opponents participate in latest-contact credit; 232 focused checks passed; complete live attribution acceptance remains open |
| Terminal-score source repair | `eb1be7d`: independently reviewed; 268 focused checks passed; a later score cannot reopen a completed timeout; original live transition cause remains unverified; no native build or live test of this repair |
| Developer candidate checks | Exact `2c08e74`: 1654 Python checks passed/15 skipped, Ruff, 38 plugin CTests, 13 launcher checks, backend/native fixture and frozen smoke passed after using a shorter exact-commit worktree |
| GC live probe | Exact `2c08e74`: two provisional situations; no-input timeout recorded defender contact; Up restored observed car/ball, score stayed 0–1; automatic 1/2 to 2/2 transition observed without navigation input; cause unestablished |
| Gold content | `5258ab3`: twelve reference-derived shots from actual downloaded Poquito/Skogur packs; 269 targeted checks including the final persistence delta; not live accepted |
| Last loaded candidate | Exact `2c08e74`, distinct from the later source repair; authored hub, GC Power Shots and Return to authored hub observed |
| Native clock | Exact `2c08e74` timed out while the visible native clock remained at 0:01; correct zero display/hold remains unverified |
| 29 October repair evidence | Grounded reset/floor friction and transient command-read repairs passed repeated live resets; Training Return reached hub with copied Career unchanged |
| Shutdown/restoration | Exact `2c08e74`: Quit acknowledged but game remained after seven seconds; owned graceful WM_CLOSE fallback eventually closed game/app/helper; relevant processes gone, original saves and plugin/config/game-file hashes matched pretest baselines; authored Quit completion remains unaccepted |
| Career boundary | `af08455`: five saved-result guard and 41 continuation checks passed; explicit result choice retained |
| Privacy improvement | PR #11 integrated as `c14cb5d`, same tree as checked `c969569`: 25 privacy tests, scanner, Ruff and Windows CI passed |

The three-tab/rank route, saved-schedule Training access, live-match exit rule,
keyboard polling, queued retry/step acknowledgements and goal advancement exist
in source. The previous failed playtest remains evidence against readiness.
Manual timeout hold and generated-key retry are observed; one rapid retry hit a
command-file read failure; its read-retry repair passed a real Windows lock test. The next reset/Return repair has
160 focused passing checks and independent review. Other ranks still contain two
provisional shots each; the ultimate target remains twelve per lesson per rank.

Next runtime priority: build the exact reviewed native handoff, then verify stock
Play arrival, manual Training selection and Back to a responsive authored hub.
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
provenance and remaining live boundary. Stock editor exploration succeeded in a
separate native-game session; that does not validate this new MCT entry.
