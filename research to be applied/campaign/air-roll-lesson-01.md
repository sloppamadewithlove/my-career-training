# AIR-ROLL-LESSON-01 — setup, completion evidence, and limits

## Scope

Read-only trace of the reviewed training source, existing curriculum/outcomes reports, and matching tests. Tests were inspected but not run; there was no game interaction. These findings describe the source contract, not live course or control performance.

## Lesson setup and instructional contract

`training/catalog.py:156-173` defines **Aerial & air-roll control** with a centered car start at `(0,-2200,17.01)` and three ordered gate targets: `(0,-1000,500)` radius 300; `(700,0,850)` radius 300; `(0,1000,500)` radius 350. The lesson has a 25-second timeout and requires `gate_0`, `gate_1`, `gate_2`, and `landed` (`catalog.py:165-172`). Instructions say take off toward gate 1, use air roll to steer orientation through each gate, then return to the floor on the wheels (`catalog.py:161-164`). Coaching stages are Gate 1, Gate 2/orientation, Gate 3, and Recovery (`coaching.py:37-42`).

## What completion actually checks

`_targets` considers only `next_gate`, so gate progress is sequential. A gate event requires a non-gap packet, car center z greater than 120, and Euclidean distance from the car center to that gate’s point within its radius (`engine.py:1084-1097`). It does not require crossing a gate plane in a direction, passing through a ring-shaped opening, minimum speed, a rotation/orientation, jump, boost, or air-roll input. The points act as spheres around car-center positions rather than geometric gate planes.

The adapter forwards car position/rotation, air-state, player `last_input` fields (including roll, jump and boost), boost amount, and angular velocity (`adapter.py:127-150`). Engine frame validation requires finite analog action values including roll and boolean button values including boost and jump (`engine.py:347-370`), but the air-roll lesson’s gate predicate does not use them. A source search finds `roll` in the engine only in validation; it is not used by the lesson’s success logic. Boost input contributes to the generic `boost_seconds` metric on non-gap packets (`engine.py:809-810`), but no boost threshold is required by this lesson. “Use air roll” is therefore instruction, not completion evidence.

Landing is detected after at least one observed airborne sample, when the current car is grounded and the previous car was not (`engine.py:967-982`). If the landing packet is gap-marked, it emits a `landing` event with uncertain confidence but does not emit required `landed`. On a non-gap landing it records `landing_roof_up`, `landing_forward_alignment`, speed and angular speed. The success set does not threshold those values or check a floor/corridor position. Thus the “on your wheels” instruction is stronger than the condition, which is simply a transition into the adapter’s grounded state; any landing orientation is accepted if telemetry reports grounded.

The required event names are tested as a set after the timeout check (`engine.py:818-830`). Only Speed Flip has special event ordering (`engine.py:852-855`). Gate order is enforced by `next_gate`, but the lesson does not require landing after the final gate: a qualifying landed event can be emitted earlier, remain in `_emitted`, and combine with gates reached later. At or after 25 seconds the timeout branch runs before success evaluation, so final gate/landing events can be present while the result is still timeout. Neither boundary is covered by matching tests.

## Orientation and input confidence

Position and grounded state come from live packet telemetry, while input values come from the game packet’s logical `last_input`; this is not raw physical-controller capture (`adapter.py:133-150`; OUTCOMES-01). Car rotation is used to derive vertical roof orientation and forward-velocity alignment on a valid landing, but those metrics are descriptive and not part of success. There is no `air_roll` event, roll-sign/duration test, orientation-at-gate test, upright-landing threshold, or use of boost amount in the completion predicate. A player could meet the positional gate sequence without air roll or boost and still satisfy the required events; source alone cannot establish how that feels in the game.

## Mirroring, retry, gaps, and identity

`configure_lesson(side="left")` flips the x coordinate of every target containing `position`; it does not move the centered start car. For this route, gate 2 changes from x=700 to x=-700 while gates 1 and 3 remain centered. The helper stores the full variation tuple including `side` (`catalog.py:206-230`). The existing test checks that the second gate’s x coordinate is negated (`tests/test_training.py:391-398`).

The bridge persists selected `lesson_variants`, supplies them to the request, and refuses to change a variant while the worker is active (`bridge.py:205-212,1419-1426,1726-1792`). Retry calls `engine.reset()` and reapplies that engine’s existing settle state (`game_worker.py:630-653`); engine reset clears emitted events, `next_gate`, `was_airborne`, metrics and recorder while preserving the configured lesson object (`engine.py:203-243`). Invalid body telemetry interrupts without credit; after fresh telemetry, the worker resets the whole situation unless a saved result still awaits acknowledgement (`engine.py:323-341,371-388`; `game_worker.py:833-886`).

A recording contains lesson ID/version, full `variant`, initial setup and observed samples; compatibility compares variant and starting state (`recordings.py:145-172,204-273`). The ordinary engine attempt summary has lesson ID/title and outcome but no explicit top-level variant/profile (`engine.py:1268-1305`). No rank profile is wired for this lesson: bridge/schema scenario difficulty is restricted to Power Shots and ordinary lesson start accepts only its ID (`scenario_setup.py:8-50,94-107`; `bridge.py:1726-1792`). A future eight-rank design needs stable profile identity in attempt summaries/recordings/ghost compatibility; Bronze–SSL should remain authored practice challenge labels unless calibrated, not estimates of player rank (CURRICULUM-01).

## Existing tests inspected, not run

- `tests/test_training.py:303-309` sends the car to gate 2 before gate 1 and confirms no progress, then sends it to gate 1 and confirms one gate. It establishes basic next-gate ordering only; it does not test gate passage shape, later gates or completion.
- `tests/test_training.py:391-398` checks that left-side configuration mirrors the second aerial gate’s x coordinate.
- A repository test search found no matching full aerial-air-roll success test or assertions for air roll, boost, gate orientation, landing orientation, post-gate recovery order, timeout boundary, or rank profiles. Other tests exercise generic landing/cadence or other lessons, not this lesson’s full contract.

## Useful acceptance cases

- **Gate semantics:** reach each gate point in order; approach the sphere from multiple directions; pass through the visual ring without entering the radius; enter the radius without passing through the intended opening; test near-radius/height boundaries and skipped packets. Decide whether the sphere is the intended target or replace it with a passage-plane criterion.
- **Mechanic evidence:** compare a no-roll route, roll-only route, pitch/yaw route and boost/no-boost route against the lesson label. If air roll or boost is a requirement, define its observable action/effect and do not equate a recorded input with a successful orientation change.
- **Recovery:** land upright, sideways, inverted, on a non-floor surface if supported by the map, and land before/after the final gate. Declare whether completion requires a post-route upright floor landing; test angle and velocity thresholds only after calibration.
- **Continuity and deadline:** mark gaps at each gate and at landing; verify gate progress is not awarded from a gap, and a gap landing cannot silently satisfy `landed`. Test completed route just before, exactly at, and just after 25 seconds.
- **Mirror/retry/identity:** verify left route target x positions, unchanged starting pose, selected variant persistence across restart/retry, distinct recording compatibility for left/right, and presence of profile identity in future rank-specific results and ghost checks.

No numeric thresholds for ranking, roll input, landing angle or speed are established by this source review.

## Source fingerprint receipt

SHA-256 (lowercase; byte sizes), measured from the reviewed training source snapshot:

| Source | Bytes | SHA-256 |
| --- | ---: | --- |
| `src/my_career_training/training/catalog.py` | 9,097 | `1c05fe5ed75296c5c75848f26e7c01a77160b16938c76c55e15536828f58fe73` |
| `src/my_career_training/training/engine.py` | 63,844 | `37028379a268d6f6e19d42b32a9e3c20778ed4f41d87bfbd3bc76955c61c602a` |
| `src/my_career_training/training/coaching.py` | 5,848 | `3b8336a54f4997479f1ce56f787377eb748683a117c8ba24a82e6e3c03b25d3b` |
| `src/my_career_training/adapter.py` | 12,018 | `98d1f4612967eda756b21857dfd198a3a12e4a211684067a248b9a829b74285c` |
| `src/my_career_training/game_worker.py` | 90,814 | `2e3982dfc352e4fafcd667898b3cb1f76538b61447c2b6e47adc6d9f862e89c2` |
| `src/my_career_training/bridge.py` | 139,135 | `ac502d1f19810baca479a534aa766a6afbea7ba57a405452835cc9dcff379ac2` |
| `src/my_career_training/training/recordings.py` | 22,459 | `8effb8f438b39c4abe4901d683dc6e5e0424baa7f696dc35143b282cc5aa96f1` |
| `src/my_career_training/training/scenario_setup.py` | 5,265 | `d2421bf8f7ac2508e9f3a65db21b2847a0e147b75cc62a6159a976999536a0fe` |
| `tests/test_training.py` | 17,251 | `0da5646aa0c2873287f86d6b2f5c0e0d51e1e9ac06aeb7b550e85fa429dddb9d` |
