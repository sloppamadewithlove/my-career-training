# FLIGHT-RECOVERY-01 — Fast Flight & Recovery evidence and gaps

Read-only audit of the lesson catalog, telemetry adapter, training engine, retry path and related test inventory. No tests were run and no game, input, build or network activity occurred. This report describes source predicates, not live gameplay or calibrated player performance.

## Fixed setup and required result

The catalog defines one version-1 Fast Flight & Recovery lesson on `DFHStadium`. Car start is `[0,-2500,17.01]`, yaw `π/2`, zero linear/angular velocity, boost 100. Gate 0 is centered at `[0,-1200,500]` with radius 350; gate 1 is `[0,1000,800]` with radius 400. The recovery rectangle is `|x| <= 1100`, `1000 <= y <= 4200`; timeout is 25 seconds. Required events are `gate_0`, `gate_1`, and `recovered` (`src/my_career_training/training/catalog.py:53-76, 174-191`).

The instructions say to boost through gates in order, aim the wheels toward the floor, then land and continue driving in the corridor; the description asks for “useful forward momentum” (`catalog.py:176-182`). The only lesson completion path is these two gate events and the recovery event. For non-Speed-Flip lessons `_ordered_success()` adds no event ordering beyond the event predicates (`training/engine.py:825-830, 852-854`).

## What the engine observes

**Gates.** `_targets()` accepts only the current `next_gate` and increments it when a non-gap packet’s current car-center position has `z > 120` and lies within the gate’s 3D radius. It records the current velocity magnitude as event detail (`engine.py:1084-1097`). This enforces gate-index event order, but it does not check an aperture crossing, entry/exit direction, trajectory, speed, boost, orientation, or a minimum time/speed. Since detection uses a single sampled point, the car can enter a gate sphere from any direction; a fast path between samples can also miss it. The values are spheres, not planar gate openings.

**Landing.** `_actions()` remembers that the car has been airborne, then detects a grounded transition. On a non-gap transition it emits `landed` and records roof-up, forward-velocity alignment, landing speed and angular speed (`engine.py:967-982`). The adapter maps `wheel_contact` from `AirState.OnGround`; `_grounded()` trusts that flag or a recognized OnGround label (`adapter.py:137-142`; `engine.py:43-45`). The lesson does not require roof-up, wheels-down orientation, positive forward alignment, a minimum landing speed, or low angular speed.

**Recovery.** After both gates and a qualifying `landed` event, `_targets()` emits `recovered` if the current sample is grounded and inside the x/y rectangle. It attaches `landing_roof_up` and `landing_forward_alignment` from the landing metrics (`engine.py:1163-1179`). It does not check current velocity, alignment, boost, z, time spent in the corridor, motion after landing, or a second grounded sample. Because `_actions()` runs before `_targets()`, `landed` and `recovered` can be emitted on the same packet if the car lands inside the corridor after both gates. That satisfies the event list without observable “continue driving.”

The roof-up metric is the world-z component of the car’s rotated local roof axis. Forward alignment is the dot product of the rotated local forward axis and velocity divided by speed (or zero at zero speed); landing speed and angular speed are also recorded (`engine.py:973-982`). These are physical-state observations, unlike `last_input` controls. `adapter.py` separately copies analog and button actions from `player.last_input` (`adapter.py:148-149`), but Fast Flight’s gate/recovery predicates do not consult those actions. Generic `boost_seconds` may be accumulated from held boost on continuous packets, but it is not a lesson requirement (`engine.py:809-810`).

A separate bot-reference evaluator has provisional landing gates for roof-up, forward alignment, positive speed and maximum angular speed (`training/bot_reference.py:96-115, 986-1003`), and its tests check angular-speed rejection (`tests/test_bot_reference.py:385-394`). That evaluator is not the Fast Flight lesson predicate; its values must not be presented as current lesson thresholds.

## Gap, timeout and retry behavior

The engine uses the shared cadence classifier: ordinary training treats one/two physics-step observations as continuous and flags explicit gaps, non-increasing clocks, intervals above 0.05 seconds, invalid/excess frame steps and clock/frame mismatches as gaps (`training/cadence.py:37-114`; `engine.py:162-177, 300-310`). Gate events are suppressed on gaps. A landing first observed on a gap emits only uncertain `landing`; `landed` is withheld, and if the next sample is already grounded the transition cannot be recreated (`engine.py:967-982`).

There is a gap-policy difference at recovery: the recovery rectangle branch does not test `not gap`, unlike the gate branch. If both gates and a prior valid `landed` event already exist, a gap sample that reports grounded coordinates in the corridor can emit `recovered` with the default `observed` confidence (`engine.py:1084-1097, 1163-1179`; default event confidence `engine.py:282-293, 317-321`). It can therefore complete a result from a gap packet. That might be acceptable if recovery is intentionally defined as a point-in-time pose, but conflicts with the neighboring policy that gates require continuous evidence. The source does not declare which policy is intended. A gap also may skip a gate sphere completely and leave no later event.

The worker resets the engine and applies the settle state for Retry; the engine clears the attempt ID, prior frames, metrics, events and emitted-event set (`engine.py:203-241`; `game_worker.py:615-667`). Retry is refused while telemetry recovery is pending or while a previous attempt save is not acknowledged. Auto Reset waits for a matching attempt acknowledgement plus a one-second feedback delay and only runs for an attempt with samples (`game_worker.py:615-667, 888-903, 962-981, 1374-1387`). These are source behaviors, not live-tested behavior.

For this legacy lesson, the timeout uses `frame["time"] - started_at >= 25`, where adapter time is `match_info.seconds_elapsed` (`adapter.py:161-164`; `engine.py:754-785, 818-830`). Targets are evaluated before timeout, but timeout is checked before success; reaching the last target only at/after 25 seconds ends as timeout. The source does not special-case pause time for this non-scenario lesson, and game-clock behavior during pause is unknown.

## Instruction versus result and test coverage

The lesson’s title and copy suggest speed, boost use, floor-facing wheels and continued forward recovery. The implemented grade checks two spatial samples inside ordered gate spheres, a grounded transition, and a grounded sample in a corridor after both gates. It records some speed/alignment/orientation data but applies no thresholds; it does not enforce boost, traversal speed, a true crossing of gate planes, wheels-facing-down, or continued driving.

Test inventory inspection found no `TrainingEngine("flight-recovery")` behavior test. The generic gate test constructs `aerial-air-roll` and checks its gate ordering, not this lesson’s recovery predicate (`tests/test_training.py:303-315`). `tests/test_bot_reference.py` exercises a separate evaluator’s landing metrics, not Flight Recovery. The only `flight-recovery` occurrence from the broader test search is a browser-image digest, not a lesson-engine test. No tests were run.

Useful source-permitted false-positive paths relative to the copy include entering each gate sphere from any direction, passing at any speed, and being counted recovered immediately on the landing sample in the corridor without driving further. Recovery can also be emitted from a gap sample as described above. Potential false negatives include a gap that skips a gate volume or hides the only airborne-to-grounded transition; the latter permanently omits `landed` under the current edge detector.

## Eight-tier profile prerequisites

Fast Flight & Recovery currently has one fixed state, route and 25-second timeout; no lesson-specific tiers or graded speed/alignment/roof-up criteria appear in its catalog or engine path (`catalog.py:53-76, 174-191`; `engine.py:1084-1179`). The project curriculum report likewise finds only Power Shots has eight authored challenge tiers; those are intended difficulty labels, not certified competitive ranks (`work/campaign/curriculum-01.md`). No calibration values are supported here.

Before authoring eight challenge tiers, define a versioned profile ID and deterministic start state for each tier, then declare which variable changes: gate spacing/radius, route demand, boost budget, crossing-time or speed target, recovery corridor width/length, or post-landing drive distance/time. Make “forward momentum” measurable with an explicit minimum speed/alignment window; make “wheels toward floor” measurable with an orientation threshold; require actual movement or dwell in the corridor if “continue driving” remains instructional. Specify whether gate checks are point-in-volume or directional plane crossings, and decide whether recovery can be certified on a gap sample. Keep outcome and technique evidence distinct, and identify each profile in attempt and recording metadata. Call the tiers intended challenge until captured gameplay establishes their relative difficulty; do not map labels to player rank.

Future acceptance should cover both gates in sequence, out-of-order gate visits, sphere entry from the reverse side, speed/boost thresholds if added, upright and inverted landings, no-forward-motion landing, post-landing corridor drive, gap at each gate/landing/recovery sample, and the exact 25-second boundary. For each of eight profiles, test a qualifying route and nearby failure cases, then use permitted gameplay captures to tune and compare difficulty. This report supplies no numeric thresholds.

## Provenance

Checkout `HEAD`: `1fe8c85839a5e72166ee1d5cc3066627548d9fa2`. At inspection, catalog, engine, adapter, worker and the two training test files were modified in the shared checkout; cadence helper, bot-reference source and bot-reference tests were clean. `tests/test_browser_images.py` was untracked and supplied only a digest search hit. Hashes identify exact bytes read, not necessarily the committed `HEAD` contents.

| File | SHA-256 |
|---|---|
| `src/my_career_training/training/catalog.py` | `1c05fe5ed75296c5c75848f26e7c01a77160b16938c76c55e15536828f58fe73` |
| `src/my_career_training/training/engine.py` | `37028379a268d6f6e19d42b32a9e3c20778ed4f41d87bfbd3bc76955c61c602a` |
| `src/my_career_training/adapter.py` | `98d1f4612967eda756b21857dfd198a3a12e4a211684067a248b9a829b74285c` |
| `src/my_career_training/game_worker.py` | `2e3982dfc352e4fafcd667898b3cb1f76538b61447c2b6e47adc6d9f862e89c2` |
| `src/my_career_training/training/cadence.py` | `fdbcda80e4fadb135713314e0fb65e2bcf2a3cf848f9261413fc2803555ee240` |
| `src/my_career_training/training/bot_reference.py` | `80c8a4e07294641465fb5dcc450f5de385db9641e4b7b5d002967724864ccd46` |
| `tests/test_training.py` | `0da5646aa0c2873287f86d6b2f5c0e0d51e1e9ac06aeb7b550e85fa429dddb9d` |
| `tests/test_training_cadence.py` | `2ca7b33768cc97aafba71ecd02b702bcd4da2edef2929e99e100feb749b42ea0` |
| `tests/test_bot_reference.py` | `368578811a491708d82730b9b87edf622e1e506ebf26977190e6c6f5794caaa3` |
| `tests/test_browser_images.py` (untracked) | `0e86b46dbe175caa0fbb7fe64b30573859c40fb9363f61a9b2f58c184dbafb86` |
