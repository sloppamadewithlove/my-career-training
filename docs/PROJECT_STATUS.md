# Current project status

Updated 29 October 2026. GitHub is canonical. [PR #10](https://github.com/sloppamadewithlove/my-career-training/pull/10) is a draft; there is no accepted new release.

| Evidence | Exact revision and scope |
| --- | --- |
| Last loaded source/native candidate | `dca381786a8adfd00e436295b2a5d9e623585bee`; owner-operated Gold playtest rejected controls, timer, goal flow and both provisional feeds |
| Latest tested source | `6f7c342fca96a9a20a7ae3aa7408f9835ea89424`; 282 Python tests across scenario, cadence, worker, bridge and bootstrap passed; not a full-suite count |
| Keyboard/Career native header tests | `66a24aaab02efae13aa6376749914721f5f82cff`; 3/3 scoped native tests passed; SDK-facing plugin still requires compilation and live verification |
| Earlier Career bridge check | `f6c564c3ab67e28df7fd807bdac23f66e44b4d21`; 90 bridge tests passed; included in the newer 282 count, not additive |
| Last full native build | `dca3817`; 37 plugin and 13 launcher tests passed. One identical Workshop test executable needed a shorter fixture directory. These do not certify later source changes |

Implemented in later source: saved Career schedules do not block Training; live workers cannot be replaced by starting Training; unrelated Career saves survive lesson start/return; keyboard arrows join D-pad controls; nonblocking startup notices; clock-consistent three-step ordinary telemetry; retry/step queue through save acknowledgement; automatic next challenge after an observed team goal, independent of coaching grade.

Still unverified or incomplete: native game countdown, zero-time ball lifecycle, removal of the stock kickoff between challenges, physical-controller acceptance, 12 distinct Gold challenges, real thumbnails, broader Garage/Mods/Options/quit regressions. The new queue waits for Active play; it does **not** itself prevent the stock kickoff. A saved-result-awaiting-choice regression check is now queued before the replacement build.

Owner approved combining Poquito Ground Shots and Skogur Powershot Practice as references for one 12-challenge Gold tier. Actual shot selection/data and feed tuning are not yet accepted. Three local downloaded pack files exist, but their identity and parser are unverified. Native offline pack retrieval previously returned FeatureDisabled.

The recovered eight-hour REA campaign is branch `research/rocket-league-2026-10-27`, folder `research to be applied/`. New body analysis proves the shipped ServerWrapper goal-reset toggles are no-op stubs; do not implement against their names. [Playtest and SDK receipt](evidence/2026-10-29-gold-recovery.md).

The 45-minute desktop heartbeat has executed, but its first reported audit made no GitHub write or improvement. It is being replaced with the [action contract](IMPROVEMENT_HEARTBEAT.md). Windows scheduling is not used. [Task board](NEXT_TASKS.md) owns current assignments; older status is [archived](archive/2026-10-29/pre-playtest-status.md).
