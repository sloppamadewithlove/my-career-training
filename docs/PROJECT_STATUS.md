# Current project status

Updated 5 November 2026. GitHub is canonical. No new release or owner-accepted
Gold playlist is available. The 29 October live receipts below remain historical;
the current changes have source checks and partial native-build evidence,
with no new live acceptance recorded.

| Area | Current evidence |
| --- | --- |
| Defender attribution | `d733917`, receipt clarified by `41d3730`: independently reviewed; all configured opponents participate in latest-contact credit; 232 focused checks passed; no live acceptance |
| Private prerecorded capture | `54fad04` + `cf1a0e4`: independently reviewed provisional experiment; 281 focused checks passed; source-only, private hash-pinned input CSV, lossy eight-action mapping; dispatch follows observed game packets; no successful live demonstration established |
| Native build investigation | Exact `2c08e74`: MSVC SDK include failure reproduced at expanded path length 267; identical-header probe passed at 241; shorter isolated checkout compiled the plugin DLL; remaining candidate checks/packaging pending at checkpoint |
| Gold content | `5258ab3`: twelve reference-derived shots from actual downloaded Poquito/Skogur packs; 269 targeted checks including the final persistence delta; not live accepted |
| Last loaded candidate | `3beada6`: 38 plugin/13 launcher checks; native countdown visible but zero HUD stuck at 0:01; thumbnail fallback and one delayed reset reproduced |
| Native clock | Direct countdown/restoration observed; zero sampled before restoration with no ended/overtime flag; sustained zero hold and production timer unverified |
| Current repair | Grounded reset/floor friction and transient command-read repairs passed repeated live resets; Training Return reached hub with copied Career unchanged |
| Last recorded game | Owned `3beada6` test closed normally; reviewed clock-notification/thumbnail/reset follow-up candidate pending |
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

[Private prerecorded-capture contract](BOT_REFERENCE_CAPTURE.md#private-prerecorded-input-experiment)
records the fixed 120 Hz interpretation and differing reset/origin assumptions.
No external inputs are bundled. Ownership, marker, bot mapping, Human clearance,
strict observation and private persistence gates remain; the new profile cannot
pass the existing reference evaluator or become a teaching ghost automatically.

[Session improvement receipt](evidence/2026-11-05-session-improvement.md) records
the applied dispatch-test, Windows-path and bounded-research workflow changes.
