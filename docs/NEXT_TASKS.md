# Next work and acceptance board

Updated 6 November 2026. Current source/check evidence is in [PROJECT_STATUS](PROJECT_STATUS.md). Do not confuse the current PR head with the last loaded candidate.

## Owner priority: flip-reset teaching ghost

The owner wants the first playable skill to be a flip-reset lesson with a
toggleable ghost that looks like a translucent car. It should approach the ball
in the air and demonstrate gaining the flip by contacting the ball with its
wheels. Keep the car, ball and observed inputs on one fixed-start timeline.
The ghost must not affect the player's car, ball, scoring or physics. An actual,
permitted successful demonstration and the native renderer remain unverified;
the existing diagnostic crosses do not satisfy this request.

An isolated reviewed source candidate adds recorded-ball interpolation on the same
timeline as the car, while retaining missing-data and packet-gap boundaries.
The author and an independent tester each ran 50 focused Python checks; Ruff
passed. GPT-6 Astra max found no blocking defects and reported 98 passing tests.
Branch `feat/ghost-ball-timeline-2026-11-06` is published but not integrated.
It does not draw a ghost, create a successful recording, or establish gameplay
acceptance. GhostPractice still drops ball coordinates during placement.

On 6 November the owner authorized selecting Rocket League's official
`Without EAC` option for offline mod testing if offered, while keeping Steam
online. This does not establish the current EAC state or grant game-input
ownership. Continue the compatibility and ownership checks below.

## Current priority: native Custom Training

Native-first direction remains in force. Exact packaged candidate `a59c45f` passed
the bounded native Play → Training → Custom Training → Created → Back menu route;
it did not prove editor gameplay or reset. A separate local Created-editor visit
showed that Create defaults write `.Tem` and rotate the actual Rocket League game
profile before explicit Save. Keep original game saves private and preflight them
separately from the copied MCT Career.

Native Striker timer/reset behavior remains unverified: `0:10` changed to `0:07`
after movement and later returned to initial `0:10`; expiry is inferred, not
captured at zero. Backspace at the initial state did not prove reset. Exact
candidate `bd9336d` has now passed Escape → native pause → Resume after fresh
process/foreground checks and sole-owner confirmation. End Training → Yes reached
a 0% native results screen waiting for the offline Career service, without usable
controls or a hub return. Reviewed results repair `df19252` is at source branch
head `9ee0c33`; candidate build, tests and smoke passed. It has not been launched
after the reported Steam executable update.

Exact candidate `bd9336d` now passes 1,659 Python checks/15 skipped, 38 plugin and
13 launcher CTests, the Return fixture and frozen smoke; pause ABC hashes matched
between staging and frozen output. Reuse these results while source and package
inputs stay unchanged.

The earlier handoff reached stock Play, then lost foreground; the helper refused
the next input and dispatched no click. After fresh same-process/foreground checks
and sole-owner confirmation, the run resumed: native pause/Resume passed, while
End Training remained blocked as described above. Graceful close preserved the
original Career and local sequence hashes; three absent backup saves were restored
create-new-only, and changed saves/profile files were preserved. The whole game
profile was not proven unchanged. Keep the earlier
[native-training catch-up receipt](evidence/2026-11-06-native-training-catch-up.md)
for save and timer limits, and the
[focus checkpoint](evidence/2026-11-06-native-pause-focus-checkpoint.md) for the
initial refused-input boundary, plus the
[results checkpoint](evidence/2026-11-06-native-results-live-checkpoint.md) for
this later run.

The installed Rocket League executable has been re-read: Steam build ID
`26349479`, FileVersion `1.0.10897.0`, and SHA-256 recorded in the
[Steam update checkpoint](evidence/2026-11-06-steam-update-compatibility.md).
The `9ee0c33` diagnostic gate is still keyed to the previous executable hash and
Steam build `25914621`; its source is fail-closed and diagnostic-only. A separate
standard Steam launch without `-rlbot` was inconclusive: module enumeration was
denied, so loaded-plugin state is unknown and no cause is established. Candidate
`9ee0c33` itself was not launched after the update. Keep this route distinct from
prior `-rlbot` testing. Steam Offline Mode is separate from Rocket League's EAC
setting. The user prefers Steam online and permits gameplay offline only.
The owner now authorizes selecting `Without EAC` for offline testing if offered;
actual EAC state is unknown. Official BakkesMod metadata for
`2.0.78 / RL2.78 / BM229` is a later version-level compatibility signal than
the April 28 post-EAC notice, not proof of local plugin load or Steam-build
compatibility. Do not change
the MCT guard based on version/build ID alone or matching menu packages. First
establish the exact compatibility contract for the updated binary and supported
launcher/plugin path. Then, after the gate passes, test the `9ee0c33` candidate's
results controls and chosen restart/browser/main-menu path, followed by a Career
results/Return regression. Reuse prior checks when inputs are unchanged; keep
same-process/foreground and owned-save checks fresh for each live run. See the
[Steam launch/config recovery checkpoint](evidence/2026-11-06-steam-launch-config-recovery.md)
for the distinct standard-Steam attempt and recovery limits.

The temporary config override was conditionally restored; four missing backup
saves were restored and changed/new saves were preserved. This does not prove the
whole profile unchanged. The test-started injector did not close gracefully; only
its verified test-owned PID was terminated. Cleanup of the exact test-config
temporary remains blocked by automatic review with the reported reason
`blocked by policy`; no more specific reason is available and cleanup was not
broadened or retried.

The default-OFF identity observer (`8b6b5bf` plus Windows junction-race
correction `3b4f34a`, source branch head `d64d5dd`) is independently reviewed and
approved for isolated identity observation. The real ancestor-junction swap
race found during review now has a Windows regression; this is still source and
test evidence, with no live execution, EAC-state or compatibility proof. The
next live observation requires exact owned process identity, a fresh short lease, exact
config staging and a rollback plan, with ordinary MCT excluded. Keep Steam online
as requested and gameplay offline only. If the launcher offers `Without EAC`,
the owner permits selecting it for offline testing. Record the actual choice; do not infer EAC state from the observer.
Review the exact identity output before any separate compatibility test.

The experimental drawing core on `8759a83` (`a983c618`) prepares diagnostic
frames only. SDK owner-scoped uninstall is static evidence; unload concurrency
remains unresolved. No renderer, drawable registration, live draw or ghost is
proven; keep this source experiment separate from teaching-feature acceptance.

The defender-attribution source fix is independently reviewed (`d733917`, receipt
correction `41d3730`), with 232 focused checks passing. Exact `2c08e74` has now
passed source/native/package checks. Its GC no-input probe captured a defender
touch; Human-shot attribution and whole-level retry still need live acceptance.

The private prerecorded-capture experiment (`54fad04` + `cf1a0e4`) is independently
reviewed with 281 source checks passing. Operator-supplied inputs remain private;
the adapter is source-only and explicitly lossy. It dispatches on observed game
packets and aborts on a real gap. Passive inspection of the three retained 2c08
recordings found zero 1/120-second intervals within the existing 2 ms tolerance.
Hold operator-entry/bootstrap expansion; first measure current raw cadence with
existing ordinary telemetry/recordings. A clean timestamp screen still needs
frame-number corroboration for strict capture. No successful demonstration or
teaching eligibility is established; do not relax the capture gates.

The exact `2c08e74` native build needed a shorter isolated worktree: the pinned
SDK header existed, but its expanded include path exceeded the observed MSVC
limit. Full Python/Ruff, plugin/launcher/fixture checks and frozen smoke passed.
The [improvement receipt](evidence/2026-11-05-session-improvement.md) records the
reproducer and the required production-dispatch and bounded-research practices.

Next live proof: preserve settled rank/scenario, attempt identity, score, actor
poses and acknowledgements around retry/timeout/progression. The first GC probe
observed car/ball retry with score 0–1 retained, then an automatic second-scenario
transition after timeout; its live cause remains unexplained. Separately reviewed
source repair `eb1be7d` (`ef94b24` published) passed 268 checks and prevents a
reproduced late-score-after-timeout case; it is not a verified live diagnosis.
Return reached the hub. The prior session eventually exited through owned
WM_CLOSE and restoration checks passed; authored Quit completion remains open.
The 2c08 HUD/SecondsRemaining mismatch still has no established cause; the later
`a59c45f` `0:10` → `0:07` → `0:10` sequence lacks exact-zero/native telemetry and
only suggests expiry. Correlate fresh same-attempt native clock fields with HUD
and state before proposing another write; tested 2c08 already contains the
integer-sync/notification repair.
See the [second-cycle receipt](evidence/2026-11-05-session-improvement-cycle-2.md).
The [third-cycle receipt](evidence/2026-11-05-session-improvement-cycle-3.md)
records the current matched-clock and cadence-first next actions.

The assignments and game ownership below are the prior 29 October record;
re-establish current ownership before any input.

## Active assignments

| Owner | Bounded work | Acceptance / next action |
| --- | --- | --- |
| Main builder/operator | Integrate manual retry and repair lifecycle; sole game input owner | 0a879 repeated reset/navigation 26/26 passed; Return preserved Career and reached hub; production clock and goal-transition proof next |
| DeepSeek builder/research | Manual retry proposal reviewed and corrected; native training/bot route investigated | Native Tutorial/TrainingEditor bot inheritance is plausible source evidence, not live compatibility; bounded floor-response follow-up pending |
| Luna career_test_investigation | Independent manual-retry review complete | Actual Backend/native gate runner added to candidate pipeline; wrong Training confirmation fixed and tested; missed retry traced to transient command read failure |
| Luna browser_investigation | Console/input ownership investigation active | Console open/closed retry distinction observed; embedded real gameplay thumbnail route reviewed for small offline package |
| Luna rea_research | Floor-friction reset investigation active | 23 replacement first-worker snapshots reviewed; three post-bounce samples on one geometry; zero probe reviewed, sustained zero hold remains open |
| Scheduled improvement worker | PR #11 privacy check delivered | PR #11 integrated at c14cb5d after exact combined c969569 checks; privacy tool is available on this branch |

The owner is away and has authorized continued testing. Root is the sole input
operator. Standard-game pack inspection is complete and that session was closed
normally. The bounded DeepSeek REA campaign finished nine training/eight lifecycle
topics; no idle agent is reported as doing new research. Follow-ups must name an
unresolved question and use the retained evidence before a new analysis run.

## Next proof sequence

1. Repair measured early-floor friction and console input capture, then build the
   reviewed manual-retry/clock diagnostic candidate. Establish native clock readback
   and safe zero behavior separately from the 90-second probe.
2. Build the current GitHub candidate and prove Up retry, Left/Right including
   1/12 and 12/12, timeout disappearance/restoration and scored-goal advancement.
3. Test actual Gold shooting geometry and keeper interference; do not ask for
   owner acceptance until those mechanics work together.
4. Expand the proven flow to other ranks and remaining product functions. Keep
   the downloadable mod small; update the website for verified major releases.

## Product backlog

| ID | Outcome / state | First proof / next action |
| --- | --- | --- |
| T01 | Power Shot situation — planned | Rework the rejected provisional feeds and prove useful pass geometry; Bronze/Silver solo, Gold/Platinum ground keeper, Diamond/Champion one advancing defender, GC/SSL two; verify human shot, feedback, whole-level retry and Return |
| T02 | Scenario lifecycle — planned | Stable IDs, actor roles, reset/settle, seeds, success/failure; prove switching removes old bots/timers |
| T03 | DS4 controls — planned | Adjustable Left previous/Right next/Up retry/Down supported ghost only in lessons; physical USB DS4, stock-conflict suppression, boundaries 1/12 and 12/12, restore outside |
| T04 | Ghost — blocked on valid trace | Capture successful actual skill; validate car/ball/action trace. For shots/flip resets render at fixed lesson start with faint non-contact demonstration ball/controller; prove no effect on real attempt/physics/scoring |
| T05 | Twelve situations per skill — planned | Review distinct scenario cards after first full loop; flip reset 1–4 solo/5–8 keeper/9–12 two defenders; no cosmetic duplicates |
| T06 | Thumbnails — planned | Parallel builder after item/image contract; real gameplay lesson thumbnails and correct map/mod images, bounded cache, honest fallback |
| T07 | Browser — partial | Three tabs compiled and native-tested; verify search/scroll/details/primary/Back via mouse/keyboard/DS4; fix redraw flicker |
| T08 | Workshop use — browsing only | One legitimately obtained compatible map loads/plays/returns/restores without replacing stock assets; then download/cache; Epic separately |
| T09 | Mods — browsing only | One compatible helper download/enable/disable, training-only scope and cleanup; no arbitrary auto-execution/career gameplay changes |
| T10 | Garage — planned | Opus design, builders implement installed catalog/search/filter/images/preview/apply/restore; one full equip path before expansion |
| T11 | Controller/tutorial — partial/planned | Opus reviews DS4 silhouette avoiding boost HUD; builder fixes; distinguish human/ghost inputs; permitted in-game tutorial |
| T12 | Career/release regression — partial | Changed-boundary checks; exact frozen match/result/save/next/Return/install/recovery before release; 12-second continuation target unachieved |
| T13 | Build/startup efficiency — partial | Both CI concurrency layers preserve the active candidate and retain newest pending work; validate completion under subsequent updates. Further runtime-input equivalence/cache work must preserve exact provenance |
| T14 | Privacy/security — unresolved | Privately classify historical path/email and source literals; propose cleanup without automatic history rewrite; separately audit dependencies/workflows/releases |


Ghosts remain lesson-specific and require valid recordings. Browser tabs are Lessons / Workshop / Mods; Favorites is removed. Up retries, Down toggles a supported ghost, Left/Right selects challenges. A live Career match must be left/ended before Training; a saved schedule does not restrict it. Results await explicit Next or Return. Major verified releases update the Vercel website; draft source changes are not public release claims.
