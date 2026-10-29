# Current project status

Updated 29 October 2026. GitHub is canonical. PR #10 remains draft; no new release
or owner-accepted Gold playlist is available.

| Area | Current evidence |
| --- | --- |
| Gold content | `5258ab3`: twelve reference-derived shots from actual downloaded Poquito/Skogur packs; 269 targeted checks including the final persistence delta; not live accepted |
| Reset/clock candidate | This commit: bounded early-floor reset verification and opt-in native clock probe; combined Python 1591 passed/15 skipped, 11 fake-wrapper probe cases; rebuild/live proof pending |
| Runtime cleanup/observation | `440f7ce`: hidden-ball cleanup survives unavailable wrappers; adapter exposes native match clock fields; isolated C++ and Python checks passed |
| Last mod playtest | `af8871d` was rejected by the owner and closed normally |
| Current game | Standard reference session closed normally; no candidate is loaded |
| Career boundary | `af08455`: five saved-result guard and 41 continuation checks passed; explicit result choice retained |
| Privacy improvement | Draft PR #11 at `d2e7beb`: 25 privacy checks, scanner, Ruff and Windows native CI passed |

The three-tab/rank route, saved-schedule Training access, live-match exit rule,
keyboard polling, queued retry/step acknowledgements and goal advancement exist
in source. The previous failed playtest remains evidence against readiness.
The latest source has not been proven in the game. Other ranks still contain two
provisional shots each; the ultimate target remains twelve per lesson per rank.

Next runtime blockers: live bounce/reset confirmation, actual native countdown,
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
Windows scheduling was not used. Its delivered change is draft PR #11's privacy
check. Main's build concurrency changes preserve the active build and newest
pending work. Neither is evidence of gameplay readiness. The task board owns
current agent assignments and release blockers.

[Reset and clock verification receipt](evidence/2026-10-29-reset-clock-verification.md) records independent checks and the remaining live boundary.
