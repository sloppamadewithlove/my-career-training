# CURRICULUM-01: eight lessons, practice ranks and progression

Read-only review of the training catalog, rank/scenario selection, saved state,
attempt/recording identity, existing coverage, and the prior PHYSICS-01 and
OUTCOMES-01 reports. No game, tests, builds, or source changes were performed.
The report records source contracts, not live performance or calibrated rank
equivalence.

## Current selection model

The native Training browser exposes eight core lessons. Seven rows offer
**Start lesson**; Power Shots offers **Choose rank** and opens a separate
eight-rank menu. All ranks are shown without unlock gating. Selecting one saves
the current Power Shots situation plus its `difficulty` value. Start launches
shot 1 at that selected value, and all twelve situations remain reachable
in-game. The menu labels say the ranks describe intended challenge, not
certified bot rank. (`plugin/include/NativeCareerLayout.h:1600-1616,
1800-1832`; `docs/INTEGRATION_CONTRACT.md:63-74`.)

That menu is not yet a general lesson rank system. `scenario_setup.py` accepts
only the `power-shots` lesson key and exactly `{scenario_id, difficulty}`;
the bridge’s start path permits extra scenario/rank fields only for Power Shots.
The other seven lessons accept only `{id}`. Their catalog definitions are
version 1 and use fixed start state, targets, event requirements and timeouts.
(`src/my_career_training/training/scenario_setup.py:8-50, 94-107`;
`src/my_career_training/bridge.py:1364-1376, 1729-1792`;
`src/my_career_training/training/catalog.py:53-77, 80-190`.)

No training prerequisite or rank-unlock state was found. The build spec says
training is optional and available immediately. `lessonReady()` checks runtime
readiness, active work and setup state, not prior results. Power Shots also
shows every rank while idle. Attempt history is not used to unlock lessons or
ranks. (`docs/BUILD_SPEC.md:107-118`;
`plugin/include/NativeCareerLayout.h:1179-1189, 1811-1823`.)

## Eight-lesson support matrix

| Lesson | Current setup and completion evidence | Rank/progression gap |
| --- | --- | --- |
| **Speed Flip** | One fixed start and finish plane; catalog lists target crossing and landing. OUTCOMES-01 traces required jump, diagonal dodge, opposing pitch, finish crossing and landing order. | No rank-specific setup or time/speed pass criteria. Technique evidence has known limits; opposing pitch is an input observation, not proof of cancellation effectiveness. |
| **Flip Reset** | Fixed raised-ball setup; one optional simplified short-approach variant; reset acquisition event. OUTCOMES-01 says acquisition uses a new flip-availability transition plus approach/contact/geometry evidence. | No rank profiles. No direct per-wheel contact signal; future tiers need explicit approach/contact criteria and must keep reset acquisition separate from optional use of the gained flip. |
| **Ground Dribble & Flick** | Fixed carry-zone and goal targets; sustained carry, flick and goal-target events. | No rank profiles or level-specific carry, recovery, flick or placement criteria. A tier needs to preserve the carry → flick → outcome order while varying a named drill dimension. |
| **Power Shots** | Separate menu; eight intended-difficulty labels; twelve scenarios. Rank changes authored ball-feed/timeout/opponent pressure; scenario and difficulty persist together. | Only lesson with rank coverage. Numeric profiles are authored challenge parameters, not observed player-rank calibration. The success chain is not a per-rank skill grade. |
| **Shot Placement** | Fixed start and marked goal zone; configure variants can choose a goal zone or starting angle. Completion uses contact and target crossing. | Variants are setup choices, not ranked profiles. No tier-specific target precision, approach, distance or shot-evidence contract. |
| **Fast Aerial** | Fixed start and one aerial gate; catalog lists `gate_0`. | No rank profiles. Steps mention two jumps and boost, but the current completion predicate is gate success alone; outcomes review does not certify the full fast-aerial technique. |
| **Aerial & Air-Roll Control** | Three ordered gates and landing; route can be mirrored. | No rank profiles. Current completion does not require observed air-roll input or an upright-landing threshold. |
| **Fast Flight & Recovery** | Two ordered gates and a recovery corridor; `gate_0`, `gate_1`, `recovered`. | No rank profiles. Forward alignment and roof orientation are recorded but not thresholded by the recovery predicate. |

Catalog and per-mechanic completion details are in
`src/my_career_training/training/catalog.py:80-190` and OUTCOMES-01’s lesson
matrix (`work/campaign/outcomes-01.md:8-25`). The exact no-rank variants are
limited to `side`, `target_zone`, `angle`, and Flip Reset’s `simplified` setup
(`catalog.py:206-231`); they do not add a rank or proficiency state. The build
spec’s desired twelve situations per skill is a target, not current support:
the only implemented twelve-situation ranked group is Power Shots
(`docs/BUILD_SPEC.md:107-125`; `training/scenarios.py:12-20`).

## Difficulty labels, saved state and identity

The code uses `difficulty` in requests and persistence but displays **Rank** in
Power Shots. Its eight-value order is Bronze through Supersonic Legend. The
scenario source itself labels these as intended difficulty, not certified bot
rank (`training/scenarios.py:19-44, 294-357`). Build spec says not to infer a
competitive rank from a slider and to label unverified high challenge honestly
(`docs/BUILD_SPEC.md:82, 118`). The current bot capability matrix marks
Diamond–SSL challenge providers partial and untested (`docs/FEATURE_MATRIX.md:28-29`).

So for an eight-lesson menu, keep Bronze–SSL as **practice challenge tiers**,
not an estimate of the player’s competitive rank or a certification that the
bots match those divisions. Each lesson should vary dimensions appropriate to
its mechanic and grade only evidence the engine observes. Do not apply the
Power Shots speed/timeout/opponent values to other lessons or describe them as
calibrated. PHYSICS-01 calls those profiles authored and their predicted timing
windows unmeasured (`work/campaign/physics-01.md:1-3, 6, 10`). No calibration
numbers are established in this research.

Power Shots state is explicit: `lesson_scenarios.power-shots` stores
`scenario_id` and `difficulty`; the default is low-side-pass/Bronze
(`scenario_setup.py:8-40`; `bridge.py:216-223, 1364-1376`). Other lesson IDs
cannot be added to that map today. Extending ranks therefore needs a validated
per-lesson setup/profile schema, an explicit saved selection, and start/return
rules; a UI-only label would not change gameplay.

Attempt and ghost identity must extend with the profiles. Power Shots requests,
summary and recording include scenario ID, difficulty/rank and scenario
version (`training/engine.py:277-280, 1285-1303`). The generic recording matcher
checks lesson/version, variation, environment and full initial state, but does
not explicitly compare those scenario/rank fields; the ghost `practice_context`
does not include them either. Initial-state equality may distinguish today’s
Power Shots profiles, but it is not a substitute for a stable profile identity,
especially if a future tier changes only grading thresholds. Add exact lesson
ID/version, practice tier, profile version and variant/situation ID to both
saved attempt metadata and the current ghost context/compatibility gate before
offering cross-attempt demonstrations. (`training/recordings.py:145-172`;
`training/coach.py:348-368`; corroborated in `work/campaign/ghost-01.md:11,
32-44`.)

## Implementation dependency order

1. Define per-lesson tier dimensions and observable pass/fail evidence, separating
   outcome from technique. Treat any tier thresholds as targets to calibrate;
   source values here are not findings about player skill.
2. Add versioned lesson-profile data: stable profile ID/version, rank label,
   setup/situation identity, target criteria, failure/timeout and reference
   provenance. Keep mechanic-specific setup data separate from the rank label.
3. Generalize validation, saved selection and launch identity from the
   Power-Shots-only `lesson_scenarios` map. Validate a selected profile before
   saving it; require exact acknowledgement for any live setup transition and
   keep setup changes from affecting a running attempt.
4. Feed the chosen profile into reset/setup, engine criteria and evidence-based
   feedback. Preserve existing lesson event contracts unless a new version
   declares and tests a deliberate change.
5. Store the selected profile identity in attempts and recordings; add it to
   ghost compatibility and coaching context. Never offer a replay across tiers
   just because the start state looks similar.
6. Add unlocks only if explicitly desired. Today all lessons and all Power Shots
   ranks are immediately accessible; do not invent hidden locks or present an
   attempt count as demonstrated mastery.

## Measurable acceptance for all eight ranks

Create a definition/contract table for the 8 × 8 lesson-tier combinations. For
each of the 64 profiles, validate a stable identity/version, deterministic
setup, rank-specific mechanic dimension, observable criteria, feedback reason,
and recording/ghost identity. Test each profile’s qualifying attempt and a
near-miss boundary against the declared evidence; verify no result is awarded
for missing or gap-invalid evidence. Across the eight tiers of each lesson,
measure that the intended challenge variable changes in the declared direction
without claiming an MMR equivalence. Use captured references and permitted game
observations to set any numeric thresholds; this report supplies none.

Live acceptance should select each tier from the separate menu, restart the
app to check persistence, start the exact profile, capture both a success and a
near miss, then test Retry and Return. Confirm that attempt summaries and
recordings retain the same tier/profile identity and that a ghost from an
adjacent tier is refused. If ranks are unlocked later, also test locked-state
copy and unlock only after the declared observable criteria. The current
separate menu is source/test evidence only: PROJECT_STATUS says previous
Silver-to-shot-1 game evidence came from the superseded inline layout and the
separate-rank menu still needs gameplay acceptance (`docs/PROJECT_STATUS.md:10-20,
36-54`).

### Existing coverage (inspected, not run)

- Base lesson/catalog and target evidence: `tests/test_training.py:76-98,
  189-330`; named tests cover catalog presence and the current event criteria.
- Power Shots setup validation, default Bronze, and retaining rank while
  stepping/shuffling: `tests/test_scenario_setup.py:20-93`.
- Power Shots scenario definitions exercise all 12 situations across all 8
  ranks, with authored pressure assertions and scenario resets:
  `tests/test_power_shot_scenarios.py:87-195, 384-424, 654-787`.
- Separate native menu publishes eight ranks plus Start and retains the
  selected rank: `plugin/tests/native_career_layout_tests.cpp:508-546`;
  browser row/rank route has corresponding cases at
  `plugin/tests/native_training_browser_tests.cpp:343-408`.
- No test suite covers eight rank profiles for the other seven lessons,
  rank-specific completion criteria across all 64 profiles, unlock state, or
  exact-rank ghost rejection. Existing generic recording identity tests do not
  close the explicit rank/profile comparison gap described above.
