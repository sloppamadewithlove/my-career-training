# SPEED-FLIP-01 — pass evidence, timing and test boundaries

Read-only audit of the Speed Flip catalog, engine, normalized telemetry, worker retry path and focused existing tests. No tests were run; no game, input, build or network activity occurred. Claims below are source contracts and test-fixture behavior, not live gameplay results or calibrated technique validation.

## Setup, clock and pass rule

`catalog.py` defines a single version-1 lesson on `DFHStadium`, with car start at `[0,-2500,17.01]`, yaw `π/2`, zero velocity/angular velocity, boost 100, and one finish plane at `y=0`, width 1000 and maximum `z=300`. The success-event list contains `target_crossed` and `landed`; timeout is 10 seconds (`src/my_career_training/training/catalog.py:53-76, 80-94`). Its steps say accelerate and boost, jump/release/jump diagonally, reverse pitch, cross FINISH and recover on wheels (`catalog.py:83-92`).

The engine settles the car, applies the fixed start state, confirms it from telemetry and then starts `started_at` on the confirming packet (`training/engine.py:627-673, 686-785`; `game_worker.py:615-643, 1306-1317`). Normalized `frame["time"]` is `match_info.seconds_elapsed` (`adapter.py:161-164`). The legacy lesson timeout is checked against `now - started_at >= 10` (`engine.py:818-830`). On a packet at/after the deadline, action and target events are processed first, but timeout is checked before event-based success; meeting the final predicate only on that packet still produces timeout (`engine.py:811-830`). The source has no Speed Flip-specific pause-time accounting; whether the game clock advances during a pause is not established here.

For success, all five events must exist with confidence other than `uncertain`: `first_jump`, `diagonal_dodge`, `opposing_pitch`, `target_crossed`, and `landed` (`engine.py:852-866`). Their observed sample brackets must establish:

`first_jump` → `diagonal_dodge` → `opposing_pitch` → both `target_crossed` and `landed`.

There is **no required order between crossing and landing**. A strict precedence requires the earlier event’s bracket to end no later than the later event’s bracket begins; touching boundaries are allowed, identical brackets are rejected (`engine.py:867-897`).

## What each event proves

- **First jump:** a false-to-true transition in the game-reported `has_jumped` flag. `jump_pressed` is also logged on a rising edge of `last_input.jump`, but it is not required. The engine records a `second_jump` event from `has_double_jumped`, but no success predicate requires it. There is no explicit jump-release event or release interval check (`engine.py:899-906`).
- **Diagonal dodge:** at the false-to-true `has_dodged` edge, either both finite dodge-direction components have absolute value at least 0.15, or the current game-reported pitch and yaw actions both have absolute value at least 0.15. The two inputs need not have an intended sign or alignment with the finish route (`engine.py:907-940`; thresholds `engine.py:162-177`). This proves a diagonal-shaped state vector or input pair, not that the requested forward diagonal speed-flip was executed.
- **Opposing pitch:** the pitch action observed at the dodge edge is nonzero, and a later non-gap sample has pitch of the opposite sign with absolute value at least 0.3. There is no maximum delay or required hold. The event explicitly says cancellation effectiveness is not independently proven (`engine.py:907-919, 952-966`). It records game-reported input, not rotation/velocity correction as a pass condition.
- **Finish crossing:** for non-gap samples, the previous car-center `y` must be below 0 and the current `y` at/above 0. The engine linearly interpolates the center between samples, requiring `|x| <= 500` and `z <= 300` at the plane; there is no lower height bound. It records crossing time and current-frame speed, but applies no minimum speed, boost, or time-to-plane threshold other than the 10-second attempt timeout (`engine.py:1098-1115`).
- **Landing:** the engine must have observed an airborne state, then a transition to grounded. The adapter derives `wheel_contact` from `AirState.OnGround`; `_grounded()` accepts that flag or an OnGround air-state label (`adapter.py:137-142`; `engine.py:43-45, 967-982`). On a non-gap transition it emits `landed` and records roof-up, forward-velocity alignment, speed and angular speed, but none of those metrics has a pass threshold. Grounded is therefore not an upright/wheels-down check.

The action fields are copied from the game packet’s `player.last_input`; car pose, velocity, air state and jump/dodge flags are separate packet values (`adapter.py:127-150`). These are game telemetry, not raw physical controller-button capture. The engine never requires boost input for Speed Flip; generic `boost_seconds` only accumulates non-gap held-input time and is not part of the pass condition (`engine.py:809-810, 826-830`). There is no minimum crossing speed, no speed grade, and no landing alignment/roof-up threshold.

## Source-permitted false-positive and false-negative edges

These are boundaries in the predicate, not verified examples of what a live player can physically produce.

**Potential false positives relative to the wording:**

- A dodge with any two large-enough pitch/yaw axes qualifies as diagonal, including a backward or route-misaligned direction; the dodge-direction path checks component magnitudes but not signs or relation to the finish target.
- A later pitch sign reversal can qualify at any time before the attempt ends. There is no cancellation window and no proof that it changes angular velocity or improves speed.
- Crossing can happen after landing. The catalog says cross then recover, but `_ordered_success()` only requires cancellation before each. The target is a plane, not a landing corridor; feedback nevertheless says to “land in the corridor” (`engine.py:1195-1207`).
- The crossing test has no speed threshold. The existing focused test demonstrates this source boundary: it flags first jump and dodge, then opposing pitch, observes landing at `t+0.08`, and crosses at ground height at `t+0.10`; it passes without setting `has_double_jumped`. Its helper frames also retain default zero velocity while their positions move, so this is a synthetic predicate test, not a physically plausible gameplay demonstration (`tests/test_training.py:22-57, 189-225`).
- “Jump, release, then jump again” is not enforced: the actual success path does not require `jump_pressed`, a release, or `second_jump`/`has_double_jumped` (`engine.py:899-906, 826-830`).

**Potential false negatives / conservative evidence loss:**

- A gap suppresses `diagonal_dodge`, `opposing_pitch` and plane-crossing evidence. A jump transition on a gap is marked uncertain and filtered from ordered success; a landing first seen on a gap emits only uncertain `landing`, not the qualifying `landed` event (`engine.py:899-966, 967-982, 1098-1115`). If the next packet is already grounded, the grounded transition has passed and the engine will not create `landed` later.
- A gap can skip the finish plane; because crossing requires a contiguous non-gap pair straddling `y=0`, later samples beyond it cannot recover that event.
- Real event order inside one coarse observation interval may be correct but unprovable. The engine rejects identical/overlapping brackets; the focused cadence test deliberately checks that shared jump/dodge brackets fail while distinct brackets pass (`tests/test_training_cadence.py:367-395`).
- A qualifying pitch reversal during a gap is ignored. A small/zero pitch at dodge time also prevents the opposing-pitch event (`engine.py:907-919, 952-966`).

The cadence helper permits one- or two-step samples in ordinary training and treats explicit gaps, non-increasing clocks, intervals above 0.05 seconds, excessive steps and clock/frame mismatches as gaps (`training/cadence.py:37-114`). `engine.update()` increments the gap metric and only succeeds from unambiguous events; the summary adds a telemetry-gap limitation notice (`engine.py:793-813, 1228-1231`).

## Retry and current coverage

`TrainingEngine.reset()` creates a new attempt ID and clears events, metrics, prior frame, jump/dodge state and `_emitted` (`engine.py:203-241`). Worker Retry refuses while telemetry recovery is pending or while a previous attempt save is unacknowledged; after acknowledgment it applies the settle state and begins a fresh preparation (`game_worker.py:615-667, 962-981`). Auto Reset defaults on, but is scheduled only after a matching attempt acknowledgment, with a one-second feedback delay, and only for an attempt with recording samples (`game_worker.py:888-903, 973-981, 1374-1387`). These are source facts; no live retry path was exercised.

Tests inspected, not run:

- `tests/test_training.py:189-225`: the one end-to-end engine fixture for Speed Flip. It establishes the permissive landing-before-crossing, ground-plane, no-`has_double_jumped` path described above.
- `tests/test_training_cadence.py:367-395`: order-bracket test; synthetic event records, not action extraction.
- Generic setup/gap/clock cases include `test_settle_waits_for_clean_jump_state_and_restarts_after_gap` (`test_training.py:146-162`), `test_duplicate_and_restarted_clocks_do_not_invent_actions` (`:178-186`), cadence classification and strict-capture cases (`test_training_cadence.py:31-114, 354-364`). They do not validate Speed Flip technique or gap-loss boundaries.
- `test_reset_application_must_be_observed_and_retry_clears_previous_edges` exercises Power Shots, not Speed Flip (`test_training.py:165-175`). No focused Speed Flip test covers timeout’s final-packet precedence, the 10-second boundary, wrong-sign/backward diagonal acceptance, delayed pitch reversal, grounded-orientation thresholds, or a gap exactly at crossing/landing.

## Eight challenge-tier prerequisites

Speed Flip has one fixed setup and one 10-second time limit; no lesson-specific tier/profile selection or grading thresholds exist (`catalog.py:53-76, 80-94`). The project’s curriculum report finds only Power Shots currently has eight authored challenge tiers; its labels are intended difficulty, not competitive-rank certification (`work/campaign/curriculum-01.md`).

Before defining eight Speed Flip tiers, specify a versioned profile identity and deterministic start state per tier, a named mechanic dimension (for example, approach distance/initial momentum, boost budget, finish-zone width, or maximum crossing time), and explicit observable criteria. Keep input observations separate from physical outcomes: a profile that claims effective speed-flip cancellation needs a justified physical response measure in addition to opposite pitch input. If “recover on wheels” is required, declare and validate orientation/landing thresholds; if plane crossing must precede landing, encode that ordering. Define gap policy and near-miss feedback, and include profile identity in attempts/recordings. Treat tier names as intended challenge until captures establish relative difficulty; do not claim Bronze–SSL equivalence from authored values.

Future acceptance should cover all eight profile definitions, each profile’s pass and boundary cases, missing/uncertain events, incorrect dodge direction, pitch reversal outside a declared window, crossing/landing order, timeout on the exact boundary, and gaps at every required event. Use permitted gameplay captures to calibrate values and compare tiers; this report supplies no calibration numbers.

## Provenance

Checkout `HEAD`: `1fe8c85839a5e72166ee1d5cc3066627548d9fa2`. At inspection, catalog, engine, adapter, worker and both cited test files were modified in the shared checkout; cadence helper was clean. Hashes below identify the exact bytes read, not necessarily `HEAD` contents.

| File | SHA-256 |
|---|---|
| `src/my_career_training/training/catalog.py` | `1c05fe5ed75296c5c75848f26e7c01a77160b16938c76c55e15536828f58fe73` |
| `src/my_career_training/training/engine.py` | `37028379a268d6f6e19d42b32a9e3c20778ed4f41d87bfbd3bc76955c61c602a` |
| `src/my_career_training/adapter.py` | `98d1f4612967eda756b21857dfd198a3a12e4a211684067a248b9a829b74285c` |
| `src/my_career_training/game_worker.py` | `2e3982dfc352e4fafcd667898b3cb1f76538b61447c2b6e47adc6d9f862e89c2` |
| `src/my_career_training/training/cadence.py` | `fdbcda80e4fadb135713314e0fb65e2bcf2a3cf848f9261413fc2803555ee240` |
| `tests/test_training.py` | `0da5646aa0c2873287f86d6b2f5c0e0d51e1e9ac06aeb7b550e85fa429dddb9d` |
| `tests/test_training_cadence.py` | `2ca7b33768cc97aafba71ecd02b702bcd4da2edef2929e99e100feb749b42ea0` |
