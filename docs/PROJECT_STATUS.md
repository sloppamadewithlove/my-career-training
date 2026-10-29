# Current project status

Updated 29 October 2026. GitHub is canonical. [PR #10](https://github.com/sloppamadewithlove/my-career-training/pull/10) is draft; no new release is accepted.

| Evidence | Exact revision and scope |
| --- | --- |
| Currently loaded source/native candidate | `af8871d1c8703b7d6880648578bfaab0a1cf6974`; replacement Gold session, copied Unicode-path profile; root operated the hub/rank route; inputs now suspended pending owner-control clarification |
| Full native candidate build | `af8871d`; 37 plugin and 13 launcher checks passed; staged inventory verified. Workshop's identical executable used a shorter fixture directory |
| Latest source behavior check | `af0845596f3dd764a1b90646b6e577cb644a7422`; 5 saved-result guard tests and 41 continuation tests passed in an independent clean clone; these changes are not loaded in the current game |
| Broader earlier Python check | `279b7c3f32e1e2a7e335eb123d4bced97236ee83`; 314 focused tests across six files passed; not a full-suite or additive count |
| CI | PR #10 Windows native and Vercel checks passed at `bedcbd1`; newer source has its own pending run |
| Last owner-rejected playtest | `dca381786a8adfd00e436295b2a5d9e623585bee`; controls, clock, goal flow and both provisional feeds rejected |

Implemented: three-tab browser/rank route; saved Career schedules do not block Training; a live Career worker must be left/ended first; saved results await Return or explicit Next before another activity (including Calibration); keyboard arrows join D-pad controls; nonblocking startup notice; clock-consistent three-step ordinary telemetry with strict capture still one; whole-actor retry/step queue through saved-attempt acknowledgement; observed-goal advancement independently of coaching grade. The Power Shots candidate uses RLBot's separate DisableGoalReset match mutator; the SDK ServerWrapper methods are no-op stubs.

Replacement observations: real hub -> Training -> Power Shots -> Gold succeeded. A held OS keyboard Right input changed challenge 1 to 2 with a new attempt and successful acknowledgement. Short WinForms SendKeys pulses did not generate acknowledgements; automatic timeout restarts must not be credited to Up. The game later showed Pause without a recorded pause input; automated input is suspended pending owner clarification. The pause screen lists Disable Goal Reset, which proves configuration display only, not scored-goal behavior.

Still incomplete/unverified: keyboard Up and physical D-pad whole reset, native game countdown/zero-time ball lifecycle, scored-goal transition without stock kickoff, 12 distinct Gold challenges, real thumbnails, Garage/Mods/Options/quit regressions. Native scoreboard still counts upward and a separate drawn countdown remains; that does not meet the owner's requirement. Only two unapproved provisional feeds are loaded.

Owner approved combining Poquito Ground Shots and Skogur Powershot Practice as references for one 12-challenge Gold tier. Actual shot data/selection and tuning remain unaccepted. A bounded read-only `.tem` metadata decoder identified the three cached packs (13, 10 and 9 rounds); none matches either selected reference code. CRCs passed and original file hashes stayed unchanged. The remaining acquisition route is normal in-game Custom Training download; actual target shot geometry is still absent. [Inspection receipt](research/2026-10-29-training-pack-inspection.md). No extracted assets or raw game evidence are published.

REA campaign: branch `research/rocket-league-2026-10-27`, folder `research to be applied/`. [Gold/SDK evidence](evidence/2026-10-29-gold-recovery.md), [replacement/workflow receipt](evidence/2026-10-29-execution-recovery.md).

The desktop 45-minute task is now saved as **Improve My Career Training**, with the execution prompt read back and Run now invoked. Windows scheduling was not used. It published [draft PR #11](https://github.com/sloppamadewithlove/my-career-training/pull/11), a scoped evidence-privacy check. Independent review at `20755a9` passed 25 tests, a clean evidence scan and Ruff; Windows native/installer CI and Vercel subsequently passed; the scheduled worker published its receipt and released the claim. The task is producing work, not just an audit. [Task board](NEXT_TASKS.md) owns remaining assignments.


The caller and reusable native workflow now preserve an active build instead of cancelling it on every update. Only the newest pending run is retained. This prevents repeated interruption; it does not skip checks, reuse a different revision's installer or claim the newest commit is already tested. The latest native CI run must still complete.
