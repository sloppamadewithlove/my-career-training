# DRIBBLE-FLICK-01 — carry, flick, target and evidence limits

## Scope

Read-only trace of the reviewed training source and its existing tests, after reading CURRICULUM-01 and OUTCOMES-01. No tests or game actions were run. These are source predicates, not live validation of Rocket League contact physics or player skill.

## Setup and authored target

`training/catalog.py:109-121` defines the lesson as **Ground dribble & flick** with instructions to catch the ball on the roof, keep it in a carry zone, then flick toward target. The default car starts at `(0,-1800,17.01)` and ball at `(0,-1690,160)`. The carry target is 2.0 seconds in a car-relative box: forward 160, side 110, vertical range 80–220. The second target is a goal-plane rectangle at `center_x=0`, half-width 700, z=93–550. Catalog `success_events` are `carry_sustained`, `flick`, `goal_target`; timeout is 20 seconds.

`configure_lesson` can alter the goal zone when a `target_zone` variant is supplied (`catalog.py:206-230`). This changes target geometry, not a rank/profile. The curriculum confirms there is no separate Dribble & Flick rank system; current profile/difficulty selection is Power-Shots-only.

## What carry observes

For each target update, the engine subtracts car position from ball position and rotates that vector into car-local coordinates using the inverse car quaternion. It calls the ball “inside” when local forward and side offsets are within the target bounds, local height is within `[80,220]`, and `_grounded(car)` is true (`engine.py:43-45,1116-1125`). Grounded means `wheel_contact is True` or an OnGround air-state value.

There is no ball-car collision field, roof/wheel contact event, relative-velocity check, ball-stability check, or dwell-on-roof state in this predicate. It is a position-and-grounded-car proxy. Two successive in-zone observations begin accumulating `dt`; outside the box it resets the streak and may emit `carry_dropped`. The event is emitted once when accumulated `carry_streak >= 2.0` (`engine.py:1127-1136`). The separate cumulative `metrics.carry_seconds` is not reset when the streak breaks, so timeout feedback can show total sampled carry time, while the success gate uses the resettable continuous streak.

A classified packet gap resets `carry_streak` before target processing and a gap packet cannot add time (`engine.py:793-805,1127-1136`; cadence rules are in TELEMETRY-01). The gap packet can still update `previous_carry` from its current pose; accumulation resumes on a subsequent continuous in-zone interval. Once `carry_sustained` has emitted, later dropping the ball does not revoke that one-time stage.

**Inference limit:** an airborne/hovering ball that remains in the local box while the car is grounded can satisfy this dwell test without evidence of roof contact. Conversely, a real touch may be missed if its center offset falls outside the box or sampled poses do not provide two continuous in-zone observations. These are source-derived opportunities, not demonstrated live false positives/negatives.

## What “flick” observes

The adapter copies the player’s `latest_touch`, air state, jump/double-jump/dodge flags and last input from the packet (`adapter.py:133-150`). `_touch` prefers that player-owned touch; fallback to global ball touch requires matching player index (`engine.py:89-96`). A touch is fresh only when its finite timestamp differs from the stored touch time and falls within the previous/current sample bracket with a ±0.02-second allowance (`engine.py:990-1019`).

On a fresh touch, the engine emits `flick` once if `carry_sustained` was already recorded, either `has_dodged` or `has_double_jumped` is truthy, and the current packet is not a gap (`engine.py:1020-1025`). It does not require a fresh jump-button press, new dodge/double-jump transition, directional input, upward ball velocity, speed increase, or a minimum impulse. It stores current ball speed as event detail but applies no threshold. The check is therefore a **touch after observed carry while a jump/dodge flag is set**, rather than a measured flick technique or verified force transfer.

A first contact before carry can emit the once-per-attempt `ball_contact` event, but cannot emit flick. A later distinct fresh touch after carry can emit flick. If the touch arrives on a gap packet, flick is suppressed; the repeated same latest-touch timestamp does not become fresh automatically on the next packet, so another touch may be needed.

## Goal target, order, and completion

The goal predicate watches the ball center cross world `y=5120` in the positive direction. It linearly interpolates the crossing point, tests x/z against the rectangle, and records `shot_location`/`target_hit`. A hit emits `goal_target` only if `ball_contact` exists in `_emitted` (`engine.py:1137-1158`). Its source comment explicitly separates this target crossing from authoritative match score. No team score is read for this legacy lesson.

Gap-marked crossing packets are ignored. If a ball passes the plane during a classified gap, a later packet already beyond the plane will not satisfy the below-to-above crossing predicate; the ball would need to cross again to generate the event. A successful marked-plane crossing can occur without the game awarding a goal, and a real score alone does not establish this configured rectangle event.

The final ordinary-lesson check compares the required names as a set, and `_ordered_success()` imposes special ordering only for Speed Flip (`engine.py:818-830,852-855`). Carry-before-flick is partly enforced because flick checks that carry was already emitted. However, `goal_target` only depends on any prior `ball_contact`; it need not follow flick. A marked crossing can be recorded before carry/flick and a later qualifying carry plus flick can make the set complete. No inspected test checks event order for this lesson.

There is a confidence mismatch between the event log and the goal prerequisite: coaching stages are Carry, Flick and Place, not `ball_contact` (`coaching.py:14-22`). Stage completion counts only `observed` or `strong telemetry evidence` events (`coaching.py:51-75`), while `goal_target` checks only whether the name `ball_contact` is in `_emitted` (`engine.py:1157-1158`). Thus a first contact observed on a gap packet can remain marked uncertain in the event log yet still satisfy the goal event's prerequisite. It cannot complete the drill by itself: success still requires `carry_sustained`, a later fresh non-gap touch that emits `flick`, and `goal_target`. The first `ball_contact` is one-shot and is not upgraded by later contact. This is an event-evidence inconsistency, not an incomplete contact coaching stage, and no inspected test covers it.

## Timeout, retry, progress and difficulty

The timeout branch runs after contacts and targets but before the success-set check (`engine.py:811-830`). Thus events observed at or after `started_at + 20` can be present while the outcome is timeout. Gaps still advance this legacy timeout through game-clock time; the engine only uses separate active-time accounting for scenario lessons. Whether the game clock pauses as expected is not established by this source audit (TELEMETRY-01 records that as a runtime unknown).

Coaching stages are Carry → Flick → Place; they display qualifying events but do not grade technique (`coaching.py:19-22,51-75`). Timeout feedback reports accumulated carry time and encourages keeping the ball in the marked roof zone before flicking (`engine.py:1216-1219`). A retry resets the engine, event set, carry history and recorder and reapplies the lesson’s settle pose; retries are blocked while the prior attempt awaits save acknowledgement. Invalid ball/body telemetry interrupts without credit and recovery resets the whole situation (telemetry-01; `engine.py:323-341,371-388`; `game_worker.py:630-653,833-886`).

No rank-specific Dribble & Flick setup, carry duration, contact/flick evidence, target rectangle or success threshold is wired today. Bridge validation accepts difficulty profiles only for Power Shots; ordinary lesson launch accepts only the lesson ID plus saved variants (`bridge.py:1364-1377,1726-1792`; `scenario_setup.py:8-50,94-107`). Do not reuse Power Shots numeric values or claim Bronze–SSL estimates player rank. Future tiers should be named practice challenges, with their own versioned setup/evidence identity and values calibrated from permitted game captures. Recording currently carries lesson/version and variant/setup but no rank profile (`recordings.py:145-172,204-273`; summarized in CURRICULUM-01).

## Existing tests inspected, not run

`tests/test_training.py:292-300` is the only test mentioning Dribble & Flick or its carry event: it builds synthetic in-zone frames, confirms the streak exceeds one second, inserts a gap, then checks the streak resets and `carry_sustained` is absent. It does not test the two-second completion boundary, actual carry/flick/goal chain, relative-frame rotations, false roof contact, flick direction/impulse, goal-score relation, out-of-order events, uncertain-contact confidence, gap-crossing recovery, timeout edge, or rank-specific profiles. A broader test search found no other carry/flick completion cases.

## Useful acceptance cases

- **Carry evidence:** record car-local ball position and contact observations for stable roof carriage, a ball hovering through the box, a bounce that enters/exits between samples, airborne car, and an out-of-zone interval. Verify the declared evidence semantics and the 2-second boundary.
- **Continuity:** test one accepted continuous cadence, one classified gap at every point in the dwell, gap followed by reacquisition, and missing/invalid ball telemetry. Confirm no dwell time bridges a gap and that interruption produces no credit.
- **Flick:** after carry, test a new jump+touch with target impulse, touch while jump/dodge flags were already true, wrong-direction touch, no impulse, touch before carry, and touch on a gap. Keep event detail separate from claims of flick mastery.
- **Target/order:** test center/edge/height miss, marked plane hit without authoritative score, actual score outside the rectangle, ball crossing during a gap, and crossing before the flick followed by later required events. Decide whether target success is intentionally set-based or require explicit carry → flick → target order.
- **Confidence/deadline:** first touch on a gap, then clear carry/flick/target; verify the result does not present the uncertain prerequisite as a fully observed touch, while the three actual coaching stages reflect their own events. Test qualifying events just before, at and after 20 seconds.
- **Ranks and identity:** for each future Bronze–SSL practice tier, declare its mechanic-specific variable and observable criterion, record successful/near-miss/gap cases, and preserve exact profile ID/version in attempt, recording, and ghost compatibility. No calibration thresholds are supplied here.

## Source fingerprint receipt

SHA-256 (lowercase; byte sizes), measured from the reviewed training source snapshot:

| Source | Bytes | SHA-256 |
| --- | ---: | --- |
| `src/my_career_training/training/engine.py` | 63,844 | `37028379a268d6f6e19d42b32a9e3c20778ed4f41d87bfbd3bc76955c61c602a` |
| `src/my_career_training/training/catalog.py` | 9,097 | `1c05fe5ed75296c5c75848f26e7c01a77160b16938c76c55e15536828f58fe73` |
| `src/my_career_training/adapter.py` | 12,018 | `98d1f4612967eda756b21857dfd198a3a12e4a211684067a248b9a829b74285c` |
| `src/my_career_training/training/coaching.py` | 5,848 | `3b8336a54f4997479f1ce56f787377eb748683a117c8ba24a82e6e3c03b25d3b` |
| `src/my_career_training/game_worker.py` | 90,814 | `2e3982dfc352e4fafcd667898b3cb1f76538b61447c2b6e47adc6d9f862e89c2` |
| `src/my_career_training/bridge.py` | 139,135 | `ac502d1f19810baca479a534aa766a6afbea7ba57a405452835cc9dcff379ac2` |
| `src/my_career_training/training/scenario_setup.py` | 5,265 | `d2421bf8f7ac2508e9f3a65db21b2847a0e147b75cc62a6159a976999536a0fe` |
| `tests/test_training.py` | 17,251 | `0da5646aa0c2873287f86d6b2f5c0e0d51e1e9ac06aeb7b550e85fa429dddb9d` |
