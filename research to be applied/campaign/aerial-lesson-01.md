# AERIAL-LESSON-01 — Fast Aerial evidence and profile gaps

Read-only source and test-inventory inspection of the frozen `work/reviewed-training` checkout. No tests were run, and there was no game, input, build, or network activity. This report describes the checked source snapshot, not live gameplay or calibrated performance.

## Current setup and launch clock

`catalog.py` defines Fast Aerial as version 1 on `DFHStadium`: car start `[0, -1800, 17.01]`, rotation `[0, π/2, 0]`, zero linear/angular velocity, boost 100; ball start `[0, 0, 93.15]`, zero velocity; target gate center `[0, -600, 850]`, radius 250; success event `gate_0`; timeout 12 seconds (`src/my_career_training/training/catalog.py:34-76, 142-155`). The shared lesson helper makes the settle state use the car start position but parks the ball at `[3000, 0, 93.15]`; the authored start restores the ball to center (`catalog.py:53-64`).

On Retry/start, `TrainingEngine.reset()` clears attempt events/metrics and returns the settle state (`training/engine.py:203-237, 267`). The worker sends that car/ball state through `desired_state()` (`game_worker.py:615-643`; `adapter.py:167-203`). The engine then waits for a grounded, non-spinning, low-speed car with clean jump/dodge flags near the settle pose; ordinary preparation needs at least three samples over 0.25 game seconds (`engine.py:627-667`). It emits the lesson start state only after settling (`engine.py:668-673`), and the worker applies that state (`game_worker.py:1306-1317`). The engine confirms the applied car pose, motion, boost, flags, and ball pose/velocity against reset tolerances before setting `started_at` and emitting Go (`engine.py:686-785`).

Thus the 12-second timeout starts on the packet that confirms the reset, not when the reset is requested. The legacy lesson deadline is `now - started_at >= timeout` using packet `time` (`engine.py:818-830`); the adapter sources `time` from `match_info.seconds_elapsed` (`adapter.py:161-164`). The first packet after Go establishes a recording/cadence baseline without testing actions or target evidence (`engine.py:754-792`). On a packet at or beyond 12 seconds, timeout is checked before the success-event completion check; a gate event on that same late packet would still leave `outcome="timeout"` (`engine.py:811-830`).

## What is actually measured

The sole required success event is `gate_0`. `_targets()` awards it when a non-gap packet’s current car position is above z=120 and within 250 Unreal units of the gate center; it stores current car speed as event detail (`engine.py:1084-1097`). For this lesson `_ordered_success()` imposes no additional ordering or technique criteria: it returns true for every lesson except Speed Flip (`engine.py:852-854`). Therefore success means the observed car sample entered the 3D gate sphere before the deadline. The code does not require a plane crossing, approach direction, orientation, minimum speed, height-gain rate, successful landing, or any particular boost consumption. The z>120 check is present, though the sphere centered at z=850 with radius 250 already bounds qualifying positions to z≥600 (mathematical consequence of this target geometry).

The instructional copy is stronger than the grade:

- “two jumps” is not required for success. The engine records `first_jump` and `second_jump` on observed `has_jumped` / `has_double_jumped` false-to-true transitions (`engine.py:899-906`), but `success_events` does not include either.
- “Release jump” is not checked. The action stream logs a `jump_pressed` rising edge but no release event or minimum release interval (`engine.py:899-906`; no `jump_released` code found in the inspected engine/tests).
- “pitch upward” is not checked during takeoff. Pitch is available as an analog action, but the Fast Aerial path does not gate success on pitch.
- “controlled boost” is not checked. `boost_seconds` accumulates non-gap time while the boost action is true (`engine.py:809-810`); no Fast Aerial criterion reads it. This is held-input time, not a measure of boost resource consumed or height gained. Current boost is read for reset confirmation and boost amount is written at state setup (`engine.py:703-716`; `adapter.py:196-202`).
- “without a backward dodge” is not a failure predicate. The engine observes a dodge flag edge and stores dodge direction/input, but the Fast Aerial-specific `possible_backflip` suggestion fires only if a dodge begins on a non-gap packet while `pitch > 0.3`. Its own detail says direction should be verified in playback (`engine.py:907-949`). It does not inspect whether `dodge_dir` is backward. On timeout, this may add a coaching message; otherwise timeout feedback falls through to the generic ordered-gate count (`engine.py:1181-1231`).

Normalized action values come from the player packet’s `last_input` fields; car position, velocity, rotation, angular velocity, boost, and jump/dodge flags are separate packet observations (`adapter.py:127-150`). Input values support statements about game-reported control state, not independent proof of a physical controller button press or of the intended maneuver’s physical effect. Likewise `first_jump`/`second_jump` are game state flag transitions; they are useful evidence but do not establish correct takeoff timing, air acceleration, or the full technique.

## Packet gaps and evidence confidence

The shared cadence classifier treats explicit gaps, non-increasing clocks, intervals above 0.05 seconds, invalid/partial frame numbering, more than two physics steps, and clock/frame-step mismatches as gaps; ordinary training accepts one- or two-step continuous samples (`training/cadence.py:37-114`; `engine.py:162-177, 300-310`). The engine increments `packet_gaps`; it accumulates boost time only on non-gap frames (`engine.py:793-810`). Jump and dodge transitions on a gap are marked uncertain; `possible_backflip` is not emitted on a gap (`engine.py:899-949`). Gate evidence is explicitly suppressed on gap packets (`engine.py:1089-1097`). A later valid sample inside the gate can still earn success, but the current-position-only check can miss a fast crossing that occurs between observations. Summaries add a warning that telemetry gaps limit technique/timing conclusions (`engine.py:1228-1231`).

This is conservative for a gate outcome, but it does not make the current drill a technique grader. Valid packets may support observed inputs/flags and physical state; the lesson does not combine them into pass/fail requirements for a fast aerial.

## Tests inspected, not run

No Fast Aerial engine test was found in the inspected `tests/test_training.py` and `tests/test_training_cadence.py` search. Existing adjacent coverage includes catalog-wide reset/reference assertions (`test_training.py:76-85`), generic cadence and setup cases, and an ordered-gate test explicitly instantiated with `aerial-air-roll` (`test_training.py:303-315`). Those tests do not establish Fast Aerial’s success semantics, jump sequence, boost use, pitch, timeout boundary, or gap behavior in this lesson.

## Eight-tier authoring implications

There is only one Fast Aerial profile today: fixed version 1 with one state, one spherical gate, one gate event, and a 12-second timeout. The catalog contains no tier/profile identity or tier-specific evidence (`catalog.py:53-76, 142-155`); the curriculum report also finds the other non-Power-Shots lessons have no rank profiles (`work/campaign/curriculum-01.md`). Do not label eight authored challenge levels as calibrated competitive ranks.

Before authoring eight tiers, define a versioned profile schema with stable lesson/profile IDs, deterministic setup, declared challenge dimensions, measurable success and near-miss criteria, timeout, gap policy, feedback reasons, and recording identity. Decide which claims are outcomes (for example, reaching a target in a time window) and which are technique evidence (first jump, release interval, second jump, dodge direction, pitch window, boost input/resource delta, upward velocity/height gain). Use only packet fields with explicit confidence and avoid treating `last_input` as physical proof. A target crossing alone can remain a useful outcome but should not silently certify the instructed sequence.

For each of eight authored tiers, define values from actual permitted gameplay captures and label them “practice challenge” or “intended difficulty” until measured. Keep rank values mechanic-specific rather than copying Power Shots pressure. Acceptance should include a qualifying run, each important near-miss (gate reached with a missing step, wrong dodge, insufficient boost or height evidence), timeout edge, and a gap that skips the gate; verify event confidence and saved profile identity. No threshold or rank-equivalence number is supported by this source review.

## Provenance

Checkout `HEAD`: `1fe8c85839a5e72166ee1d5cc3066627548d9fa2`. Git status at inspection showed the catalog, engine, adapter, worker, and two listed test files modified; `training/cadence.py` was clean. The SHA-256 values identify the exact bytes read, not necessarily the committed `HEAD` contents.

| File | SHA-256 |
|---|---|
| `src/my_career_training/training/catalog.py` | `1c05fe5ed75296c5c75848f26e7c01a77160b16938c76c55e15536828f58fe73` |
| `src/my_career_training/training/engine.py` | `37028379a268d6f6e19d42b32a9e3c20778ed4f41d87bfbd3bc76955c61c602a` |
| `src/my_career_training/adapter.py` | `98d1f4612967eda756b21857dfd198a3a12e4a211684067a248b9a829b74285c` |
| `src/my_career_training/game_worker.py` | `2e3982dfc352e4fafcd667898b3cb1f76538b61447c2b6e47adc6d9f862e89c2` |
| `src/my_career_training/training/cadence.py` | `fdbcda80e4fadb135713314e0fb65e2bcf2a3cf848f9261413fc2803555ee240` |
| `tests/test_training.py` | `0da5646aa0c2873287f86d6b2f5c0e0d51e1e9ac06aeb7b550e85fa429dddb9d` |
| `tests/test_training_cadence.py` | `2ca7b33768cc97aafba71ecd02b702bcd4da2edef2929e99e100feb749b42ea0` |
