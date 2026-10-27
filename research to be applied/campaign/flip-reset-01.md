# FLIP-RESET-01 — setup, inferred acquisition, progress, and rank implications

## Scope and evidence level

Read-only source trace of the reviewed training checkout. The tests listed below were inspected but not executed; there was no game input or runtime observation. Findings describe implemented Python contracts and their synthetic test coverage, not Rocket League’s live wheel-contact or flip-reset behavior.

## Setup and lesson contract

`training/catalog.py:95-108` defines `flip-reset` as versioned lesson setup with car start `(0,-650,17.01)`, raised ball `(0,250,950)` with upward/forward velocity, 12-second timeout, and sole required event `reset_acquired`. The target record contains `minimum_height=300` and `central_space=2800`, but a source search found these fields only in the catalog and coaching label code; the engine does not read them. The visible target/marker is therefore descriptive. The detector has separate hard-coded bounds.

`configure_lesson(..., simplified=True)` changes only car y to `-250`, ball position to `(0,150,600)`, appends a shortened-approach note, updates settle car position, and stores `variant.simplified=true` (`catalog.py:206-230`). It does not change physics, detector tolerances, targets, event requirements, or timeout. The default remains `false`.

The adapter maps RLBot packet fields to the engine: `AirState.OnGround` becomes `wheel_contact`; `air_state`, `has_jumped`, `has_double_jumped`, and `has_dodged` are copied; the player’s `latest_touch` includes timestamp/location/normal/ball index (`adapter.py:133-164`). It does not map a per-wheel contact record or explicit “flip reset acquired” flag. Missing car/ball pose/actions are rejected by frame validation, while the reset flags themselves are not a required-field validation contract (`engine.py:323-370`).

## Acquisition inference and event ordering

1. Spending the original flip is inferred from `has_dodged` changing false→true; this sets `spent_flip_time` and emits `dodge` (`engine.py:899-919`).
2. A touch is accepted from the local player’s `latest_touch`, or from global ball touch only when `player_index` matches (`engine.py:89-96`). Its timestamp must be finite, distinct, and within `[previous.time - 0.02, current.time + 0.02]`. The engine emits one `ball_contact`/`touch` event and records the timestamp (`engine.py:990-1019`).
3. Reset acquisition needs a new transition into `_holding_reset`: `air_state` must be InAir and all three jump/dodge flags must be exactly false; an already-available state does not count (`engine.py:47-50, 1031-1034`). If that transition packet lacks a newly fresh touch, the last touch can qualify only if it is no more than `contact_window=0.08` seconds old (`engine.py:162-175, 1035-1039`).
4. Additional inference filters require the car to be in a hard-coded central air volume (`|x|<2800`, `|y|<3800`, `300<z<1750`), the ball center within 230 units and along the car’s rotated underside direction (dot > 0.5), the original flip already spent, and a touch timestamp strictly later than that spend. Surface evidence must be clear and the current/prior packet-gap tests must pass (`engine.py:1040-1069`).
5. When every condition passes, `reset_acquired` is emitted once with “strong telemetry evidence”; event details explicitly say no per-wheel contact event is exposed (`engine.py:1070-1077`). If a fresh touch and availability transition occur but another filter fails, `reset_uncertain` is emitted and a retry hint is recorded (`engine.py:1078-1082`). If there is no qualifying touch/transition, there is no immediate failure event; the lesson continues until timeout or telemetry interruption.

This is evidence for a newly available flip after an attributed car-ball touch, not proof that a particular wheel contacted the ball. The engine never uses `latest_touch.location` to establish wheel contact; that location is only attached to the contact event. Reset geometry uses the current car/ball centers and car underside orientation. `_grounded` treats either the OnGround/`wheel_contact` value as grounded, and the source comment acknowledges transient grounded state could be ball-wheel contact; “arena surface excluded” is a location heuristic rather than a surface identity signal (`engine.py:43-45, 983-988, 1040-1069`).

## Success, failure, timing, and recovery

After contacts/targets are processed, ordinary lessons time out at `now - started_at >= lesson.timeout`; otherwise the engine succeeds when the catalog’s required event set is present (`engine.py:811-837`). For Flip Reset this means `reset_acquired` alone completes the lesson. “Use the gained flip if you can” is a teaching step, not a success requirement (`catalog.py:101-107`; `coaching.py:14-18`). Consequently the result certifies the detector’s acquisition evidence only, not use of the gained flip or recovery after it.

Timeout takes precedence over success evaluation on the same packet. A reset event first observed at/after the 12-second threshold can therefore be present in events/stages while the attempt outcome is `timeout`; no inspected test covers that boundary (`engine.py:818-830`). A timeout with no reset gets a final “newly gained ball reset was not confirmed” instruction (`engine.py:1208-1211`). `reset_uncertain` details can explain a failed transition only when touch plus transition happened in the same attempt; otherwise the player sees the timeout-level guidance.

A retry calls `engine.reset()`, creates a new attempt ID, clears events/touch/spend/surface/gap/reset evidence, reconstructs recorder, then reapplies the lesson’s settle state through `desired_state` (`engine.py:203-243`; `game_worker.py:630-653`; `adapter.py:167-203`). Manual retry is rejected while the prior attempt is awaiting save acknowledgement (`game_worker.py:631-634, 962-963`). If auto-reset is enabled, a saved sampled attempt resets after acknowledgement plus a one-second feedback delay (`game_worker.py:888-903, 973-981`).

Invalid pose telemetry, including an absent ball, interrupts the attempt with no credit; after fresh telemetry the worker resets the whole situation unless a completed result is still pending acknowledgement (`engine.py:323-341, 371-388`; `game_worker.py:833-886, 1240-1254`). The shared telemetry report documents cadence handling: gaps after spending the flip make `continuous_packets` false until a later spend establishes a newer baseline; gaps before spend can be older than the spend time and therefore do not necessarily block. This is source behavior, not a runtime packet trace.

## Progress, saved identity, and ranks

`coaching.py` presents stages “Use your first flip” (`dodge`), “Meet the ball” (`ball_contact`), and “Acquire a reset” (`reset_acquired`). Only events with observed/strong confidence complete a stage; uncertain events are shown as uncertain (`coaching.py:14-18, 51-75`). The “Meet the ball” progress stage can be marked by the first observed contact even if that touch predates spending the original flip; the separate reset predicate correctly rejects that stale touch. Thus stage completion is instructional progress, not the reset-success predicate.

No Flip Reset rank/profile state exists in the current route. Scenario/difficulty selection and persistence are Power-Shots-only: scenario validation rejects other lesson keys, bridge start accepts only `{id}` for non-Power-Shots, and the engine only loads a difficulty profile when `scenario_id` is present (`scenario_setup.py:8-50, 94-107`; `bridge.py:1364-1377, 1726-1792`; `engine.py:125-153`). Flip Reset’s saved `simplified` setting is a setup variant, not a rank. Attempt summary has `scenario=None`; recordings persist lesson ID/version, variant, and setup, but not a rank. Recording compatibility compares lesson version, environment/setup, and variant, so an eventual difficulty tier that changes only grading criteria needs an explicit profile ID/version in attempts/recordings and ghost matching, not just a menu label (`engine.py:1268-1305`; `recordings.py:145-172, 204-273`). The current design principle is Bronze–SSL as authored practice challenge tiers, not claimed competitive-player equivalence (`curriculum-01.md`).

## Existing tests inspected (not run)

- `tests/test_training.py:228-289`: synthetic successful detector path; rejects no spent flip, gap, near-surface pose, missing touch; verifies an initially available reset does not count.
- `tests/test_training.py:391-398`: simplified start differs from standard while retaining normal game speed.
- `tests/test_training.py:400-423`: rejects a global touch attributed to another player.
- `tests/test_domain_adversarial.py:205-246`: contact before spending the original flip cannot count as new acquisition.
- No inspected test establishes real per-wheel contact, in-game reset detection, timeout-edge priority, a custom surface inside the allowed volume, brief/coalesced flip-availability transitions, or all eight profile/rank criteria. The synthetic fixture directly supplies telemetry fields and therefore validates branch logic only.

## Evidence-backed risks and useful acceptance cases

- **False-positive opportunity:** a normal attributed car touch plus nearby/under-ball geometry and regained-flag transition can satisfy the detector without identifying wheel contact or using contact location. Test a non-wheel contact near the underside with the same flag transition; ensure the result is either explicitly marked inferred or rejected by stronger evidence.
- **Surface false-positive opportunity:** any grounded state inside the allowed central-volume bounds is not recorded as `last_surface_time`; the guard does not query the actual contacted surface. Validate against real map geometry and distinguish ball contact from arena contact.
- **False-negative boundaries:** exact flag names/states, touch timestamp windows, `<230` center-distance and underside-dot threshold, strict post-spend timestamp, fixed central bounds, and any post-spend packet gap can all reject a real attempt. Record raw telemetry around qualifying contacts and calibrate only with captured evidence.
- **Deadline edge:** replay identical qualifying telemetry just before, exactly at, and just after 12 seconds; assert event and final outcome agree with the declared policy.
- **Recovery/reset:** remove ball/body data mid-attempt, restore a valid packet, verify no success credit survives, new attempt identity, and exact standard/simplified starting state. Confirm retry with pending acknowledgement is refused, then permitted after acknowledgement.
- **Progress/ranks:** test that contact-before-spend can complete the contact teaching stage but never reset acquisition; for each future Bronze–SSL tier, record setup/profile identity in attempt, recording and ghost compatibility and exercise success, near-miss and telemetry-gap cases. Do not assign numeric calibration from this source report.

## Source fingerprint receipt

SHA-256 (lowercase; byte sizes):

| Source | Bytes | SHA-256 |
| --- | ---: | --- |
| `src/my_career_training/training/engine.py` | 63,844 | `37028379a268d6f6e19d42b32a9e3c20778ed4f41d87bfbd3bc76955c61c602a` |
| `src/my_career_training/training/catalog.py` | 9,097 | `1c05fe5ed75296c5c75848f26e7c01a77160b16938c76c55e15536828f58fe73` |
| `src/my_career_training/adapter.py` | 12,018 | `98d1f4612967eda756b21857dfd198a3a12e4a211684067a248b9a829b74285c` |
| `src/my_career_training/training/coaching.py` | 5,848 | `3b8336a54f4997479f1ce56f787377eb748683a117c8ba24a82e6e3c03b25d3b` |
| `src/my_career_training/game_worker.py` | 90,814 | `2e3982dfc352e4fafcd667898b3cb1f76538b61447c2b6e47adc6d9f862e89c2` |
| `src/my_career_training/bridge.py` | 139,135 | `ac502d1f19810baca479a534aa766a6afbea7ba57a405452835cc9dcff379ac2` |
| `src/my_career_training/training/scenario_setup.py` | 5,265 | `d2421bf8f7ac2508e9f3a65db21b2847a0e147b75cc62a6159a976999536a0fe` |
| `src/my_career_training/training/recordings.py` | 22,459 | `8effb8f438b39c4abe4901d683dc6e5e0424baa7f696dc35143b282cc5aa96f1` |
| `tests/test_training.py` | 17,251 | `0da5646aa0c2873287f86d6b2f5c0e0d51e1e9ac06aeb7b550e85fa429dddb9d` |
| `tests/test_domain_adversarial.py` | 9,466 | `27f6ec711f2416028ac2ef7c8a8c0aa3d38df57c60f69280de155fa3131759b3` |
| `tests/test_scenario_setup.py` | 4,153 | `f7b60bee78b231245c97ec30692330d14a496984ba74e012512f766bb092df77` |
