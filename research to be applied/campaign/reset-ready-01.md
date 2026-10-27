# RESET-READY-01 — Power Shots ball setup and ready gate

Date: 2026-10-27
Scope: static trace of the frozen `work/reviewed-training` Power Shots candidate from scenario selection through ball/car writes, sampled settling, observed state confirmation, and `go`. This complements `physics-01`, `telemetry-01`, and `attempt-end-01`; it does not repeat their launch-math, timer, telemetry-recovery, or post-terminal audits.

## Finding

Power Shots sets up the ball with two whole-state writes. First, retry/reset parks the ball at the selected launch XY coordinate and writes a stationary ball plus the desired Human and scenario-bot poses. After the observed car/ball/actors settle, the engine writes the moving launch state. It becomes active only after a later game packet matches that launch state within source-configured tolerances. No fixed sleep or `arrival_seconds` delay gates `go`.

This is a source-level readiness protocol for the built-in Soccar training path. It does not prove that the game accepted either state write, that Rocket League applies the assumed gravity/trajectory on the installed build, or that a custom map would share the same geometry.

## What the scenario writes into the level

The app-level default, when no saved Power Shots setup exists, is `low-side-pass` at `bronze` (`scenario_setup.py:8-24`). A saved selection replaces that default. Note that `scenario_definition` itself has a function default of `gold`; the normal start path resolves and passes the app setup explicitly, so the function default is not the persisted UI default (`scenarios.py:294-311`; `bridge.py:1782-1793`).

The worker configures a regular one-ball Soccar training match on the built-in `Stadium_P` fallback. It sets unlimited match length, max score, and overtime, one ball, Normal Boost, instant start, and state-setting; there is no gravity mutator in this configuration (`adapter.py:40-43, 78-118`). The custom-map guard rejects custom-map requests before a training match config is built (`map_guard.py:76-81`; `adapter.py:40-43`).

For the default `low-side-pass` / Bronze setup, the source defines:

- ball launch origin `[-2200, 3000, 93]` and receiving lane `[-250, 3900, 93]`;
- the player car at `[0, 2250, 17]`, zero velocity and angular velocity, rotation `[0, π/2, 0]`, and boost `100`;
- launch speed `900` uu/s, with the ball velocity computed as the normalized origin-to-lane vector times that speed (about `[817.2, 377.2, 0]` uu/s);
- no opponent bots at Bronze. At higher profiles, a keeper and then a defender are added at authored poses; bot indices/roles are assigned before the Human slot (`scenarios.py:20-76, 208-290, 294-357`).

The scenario's `settle_state` places the ball at the launch XY, `z=93`, with zero linear and angular velocity. Its `starting_state` replaces that parked ball with the computed launch position, velocity, and zero angular velocity (`scenarios.py:310-351`). For the bounce/drop variants, the launch state uses authored vertical values: Bronze/Silver start at `z=125`, `vz=-260`; higher bounce starts at `z=260`, `vz=-80`; higher drop starts at `z=520`, `vz=-140` (`scenarios.py:208-245`). The horizontal component is computed at the selected speed before the vertical component is added, so for those variants that speed value is not the total 3D velocity magnitude. Wall/backboard variants alter the horizontal launch vector toward a reflected lane. These are desired-state declarations and predicted trajectories, not measured in-game launches.

## Reset → settling → ready → active

1. **Reset and parked write.** `TrainingEngine.reset()` creates a new attempt ID, clears timers/baselines, sets `state="settling"`, leaves `started_at=None`, and returns the lesson's `settle_state` (`engine.py:203-267`). `GameWorker.reset()` refuses while start is canceled/stopping, telemetry is recovering, or an earlier attempt is awaiting acknowledgement; then it sends the entire settle state through `adapter.desired_state` (`game_worker.py:615-667`).
2. **Whole-actor write.** `desired_state` validates a non-negative Human index and non-overlapping bot indices, builds the ball and car `Desired*State` objects, and makes one `fill_desired_game_state` call for ball 0, the Human, and every configured bot (`adapter.py:167-203`). `match_config` appends the Human after the bots and returns its index; the worker uses that same config index as its training actor (`adapter.py:54-112`; `game_worker.py:465-476`). The worker sends neutral controller inputs to scenario bots while the engine is not active (`game_worker.py:1275-1288`). It does not control the Human's buttons.
3. **Settling gate.** Scenario settling is evaluated only on `MatchPhase.Active`; non-active phases clear settle samples/timers and return without counting attempt time (`engine.py:581-627`). A valid sample requires the Human car grounded (`wheel_contact` or an OnGround air state), `has_jumped`, `has_double_jumped`, and `has_dodged` all false, car position within `<60` uu of settle pose, speed `<25` uu/s, angular speed `<0.2`, the ordinary sampled interval within `(0, 0.05]` seconds, every configured bot ready, and the parked ball within `<200` uu and `<40` uu/s of its expected settle position/velocity (`engine.py:43-61, 628-656`). It needs at least 3 valid samples spanning at least `0.25` game seconds, then emits both `set_state(starting_state)` and a `ready` event (`engine.py:657-673`). If settling reaches 5 game seconds without completion, it interrupts with a cadence or pose message (`engine.py:674-685`).
4. **Moving launch write and observation.** The worker handles the `set_state` event by sending the second whole-state write (`game_worker.py:1303-1318`). Engine state is now `ready`, and `reset_requested_at` records the state-write request time. On later active packets, the gate predicts car position from its target velocity and ball position/velocity from the launch state. For elevated or vertically moving balls, it applies a source model of `z -= 325 * elapsed²`, `vz -= 650 * elapsed` (`engine.py:669-704`).
5. **Ready confirmation.** A matching observed packet must arrive before `elapsed` reaches `2.0` game seconds. One passing packet is sufficient; there is no multi-sample hold after the start-state write. Human checks: position `<120` uu, rotation difference `<0.15`, velocity error `<40` uu/s, finite angular velocity within `<0.25`, boost within `<2` of requested value, grounded, jump/double-jump/dodge flags false. Ball checks: position `<200` uu and velocity `<40` uu/s from the elapsed-time prediction. All scenario bots must also match their expected pose/velocity/rotation/angular velocity/boost. A failed sample keeps waiting until the two-second boundary, then interrupts without creating a fictional active attempt (`engine.py:401-432, 691-752`).
6. **Go and timer start.** On the first accepted observed launch packet, the engine sets `state="active"`, `started_at=now`, and `active_elapsed=0`; it freezes touch/score baselines, records the observed launch baseline, creates the attempt recorder, and emits `go` with the attempt ID (`engine.py:752-785`). Later active samples add game-clock deltas to `active_elapsed`; the timeout is based on that active elapsed clock, not the `arrival_seconds` metadata (`engine.py:796-820`; see also `telemetry-01`).

The first observed launch packet is normally expected within the `0.05`-second packet-interval contract. That is a cadence expectation, not a sleep: the source does not wait `arrival_seconds` before starting the clock. `arrival_seconds` and `shot_window_seconds` are generated scenario metadata (`scenarios.py:310-357`); a repository search finds no engine/worker consumer that delays `go` until the ball reaches the receiving lane.

## Readiness details and boundaries

- **Observed packet shape:** `_validate_frame` requires a finite, nonnegative game timestamp; finite Human car position/velocity/rotation and ball position/velocity; finite car angular velocity if supplied; bounded analog controls; and boolean jump/boost/handbrake action values (`engine.py:323-379`). The worker classifies cadence from game time, frame number, explicit transport gap, maximum interval, and the configured 1/120-second step/2 ms quantization (`game_worker.py:1250-1273`; `cadence.py:23-116`).
- **Settling is sampled pose readiness, not continuous-cadence certification.** For normal Power Shots, `_sampled_interval_ok` checks only that consecutive game times increase by at most `0.05`; this branch does not require `cadence["gap"] == false`. Thus a transport gap or frame-number mismatch can still contribute a settle sample if its time interval and poses pass. The state machine records the gap, but the ordinary settle gate is not strict-capture cadence (`engine.py:60-74, 628-656`).
- **Ready has a narrower coalescing exception.** It may accept a fully matching actor/ball observation despite a cadence gap only when the classifier reason is `step_count_exceeded` or `interval_exceeded` and this is not strict capture. An explicit transport gap or physics-step mismatch does not satisfy that exception (`engine.py:729-752`). Power Shots scenarios cannot run in strict reference capture (`engine.py:126-132`).
- **Jump and boost semantics:** observed action buttons must be present and correctly typed, but the gate does not require the Human's jump or boost button to be false. Instead it requires the physical jump/dodge flags false and checks the boost *meter* against the requested 100. Bot inputs are explicitly neutralized before active. The state writer sets car physics/boost but does not set jump buttons (`engine.py:323-379, 628-656, 691-752`; `game_worker.py:1275-1288`; `adapter.py:167-203`).
- **Ball angular velocity is written but not acknowledged.** Both scenario ball states specify zero angular velocity and the adapter writes it, but `_scenario_ball_ready` and the `ready` observation gate compare ball position/linear velocity only. The settle gate also substitutes zero for a missing Human car angular-velocity field, while the ready gate requires a finite observed car angular velocity; bot readiness requires one explicitly (`scenarios.py:310-351`; `adapter.py:183-203`; `engine.py:323-379, 401-478, 691-752`).
- **Bot roster matters.** `scenario_definition` sets bot indices/roles/teams and the Human index from the generated roster. `match_config` builds bots in sorted order then appends Human; `desired_state` rejects a bot index that overlaps Human. The readiness gate checks each bot's observed pose and boost; it does not accept an absent configured actor (`scenarios.py:247-290, 294-357`; `adapter.py:54-112, 167-203`; `engine.py:401-432`).

## Future acceptance cases

1. Inspect a real offline Power Shots launch and record the exact selected scenario/rank, active map, match mode/mutators, Human index/team, bot indices/teams, and current car hitboxes. Confirm they match the declared setup before scoring readiness.
2. For the default low-side-pass/Bronze setup, observe both writes: parked ball at the authored launch XY with z=93 and zero velocity, then the moving launch vector after settle. Confirm no duplicate Human/bot index and no partial actor write.
3. Exercise bounce/drop, side-wall, and backboard scenarios in their actual target arena. Compare observed ball trajectory to the injected velocity, actual gravity, wall/backboard collision, and the engine's expected-position model. Decide support from measured fit, not `arrival_seconds` alone.
4. Force Human movement, airborne state, residual jump/dodge flags, low boost, excessive angular velocity, stale/missing bot telemetry, incorrect ball position/velocity, and mismatched game phase. Verify none emits `go`; then verify a corrected state must pass the full settling and ready sequence.
5. Exercise explicit transport gaps, frame-number skips, interval gaps, and physics-step mismatch during settling and READY. Confirm the documented normal-mode coalescing policy, and reject any packet the product considers stale before starting the attempt timer.
6. Check whether ball angular velocity must be part of readiness. If it matters, require finite near-zero spin after both writes; current source writes it but does not verify it.
7. Measure when the first accepted ready packet arrives after the second write. Confirm `started_at` and the visible timer begin on the emitted `go`, not at reset, `ready`, a fixed delay, or predicted lane-arrival time. Verify pause/countdown packets do not spend the Power Shots active timer.

## Evidence boundary

This report reads source only; no game, live telemetry, network, test execution, downloads, or code changes were used. Coordinate values, launch velocities, gravity prediction, tolerances, and phase logic above are source declarations. They do not verify actual collisions, map dimensions, packet freshness on a live build, state-write acceptance, the `650 uu/s²` gravity assumption under runtime mutators, or the practical two-second confirmation limit. In particular, source `_BALL_RADIUS=93.15` is a local scenario constant used for backboard clearance and must not be presented as a verified physical collision radius (`scenarios.py:24-27, 224-229`; see `physics-01` for the independent docs caveat).

## Source hashes

SHA-256 of the exact candidate files used for these line references.

| Source | SHA-256 |
|---|---|
| `src/my_career_training/training/scenarios.py` | `35714a224aa8765ae62be6fde3df6dc87c088c32d297adcda3795d0bc682d979` |
| `src/my_career_training/training/scenario_setup.py` | `d2421bf8f7ac2508e9f3a65db21b2847a0e147b75cc62a6159a976999536a0fe` |
| `src/my_career_training/training/engine.py` | `37028379a268d6f6e19d42b32a9e3c20778ed4f41d87bfbd3bc76955c61c602a` |
| `src/my_career_training/game_worker.py` | `2e3982dfc352e4fafcd667898b3cb1f76538b61447c2b6e47adc6d9f862e89c2` |
| `src/my_career_training/adapter.py` | `98d1f4612967eda756b21857dfd198a3a12e4a211684067a248b9a829b74285c` |
| `src/my_career_training/training/cadence.py` | `fdbcda80e4fadb135713314e0fb65e2bcf2a3cf848f9261413fc2803555ee240` |
| `src/my_career_training/bridge.py` | `ac502d1f19810baca479a534aa766a6afbea7ba57a405452835cc9dcff379ac2` |
