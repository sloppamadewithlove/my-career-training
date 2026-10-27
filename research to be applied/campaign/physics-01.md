research_only

PHYSICS-01 source research (read-only). Scope actually read: training/scenarios.py (full), training/scenario_setup.py (full), training/engine.py (lines 1-330, 330-590, 589-848, 1084-1244, 1244-1346), training/cadence.py (full), training/recordings.py (lines 1-120, 200-260, 270-329), adapter.py (full), game_worker.py (lines 380-560, 560-840, 1180-1374). NOT read: bots/driving.py beyond grep hits, bots/physics.py, bots/tactics.py, bots/providers.py, game_worker.py lines 1-380 / 840-1180 / 1374-1706, tests bodies (only names/grep lines), coach.py, packs.py. No game run, no tests executed, no credentials, no writes.

1. Coordinate axes and units (source-evidenced only)
- Positions/velocities are 3-vectors in Unreal units (uu) and uu/s. Evidence: scenarios.py:24-27 `_SIDE_WALL_X = -4096.0`, `_BACK_WALL_Y = 5120.0`, `_GOAL_MOUTH_HALF_WIDTH = 893.0`, `_BALL_RADIUS = 93.15`; engine.py:531 ball-out test `abs(x)>4096 or abs(y)>5120 or z>2044`; engine.py:1139 goal plane `old[1] < 5120 <= new[1]`. So +Y is toward the opponent goal, X is lateral, Z up. Ball radius 93.15 uu and parked ball z=93.0 (scenarios.py:316) are consistent with a grounded ball resting on z=0.
- Rotations are stored as `[pitch, yaw, roll]` in radians, not native Unreal rotator units. Evidence: adapter.py:129 `"rotation": [p.rotation.pitch, p.rotation.yaw, p.rotation.roll]` (raw SDK fields, no conversion), scenarios.py:48 `"rotation": [0.0, math.pi/2, 0.0]`, scenarios.py:261/286 `-math.pi/2`, and scenarios.py:174-177 mirroring does `yaw = math.pi - value[1]` with `% (2*math.pi)`. The engine compares rotations only through `_rotation_distance` (engine.py:83-86) using `euler_quaternion` (recordings.py:280-290, documented as Rz(yaw) Ry(-pitch) Rx(-roll)), so no rotator-unit (65536-per-turn) arithmetic exists locally. The primary RLBot flatbuffers schema documents `Physics.rotation` as a `Rotator` with radian fields. This confirms the interface contract; the exact installed runtime packet has not been captured in this pass.
- Mirroring math (scenarios.py:169-205): positions/velocities reflect X (`[-x, y, z]`), angular velocity is treated as an axial vector (`[x, -y, -z]`), yaw becomes `pi - yaw` wrapped to (-pi, pi], roll negated. This is internally consistent with a reflection about the YZ plane.

2. Launch math (deterministic, no RNG)
`_launch` (scenarios.py:208-244) builds a straight ground velocity from `origin` to `lane`: `velocity = speed * (lane-origin)/|lane-origin|`, z=0, and returns `arrival_seconds = length/speed`. `speed = data["speed"] * _PRESSURE[rank]["speed"]` (scenarios.py:308). Spin is always zero (`angular_velocity: [0,0,0]`, line 243). No gravity term is applied to the launch itself; gravity appears only in the engine's *expectation* model at engine.py:697-699: if the starting ball is above z=100 or has nonzero vz, it predicts `z -= 325*t^2` and `vz -= 650*t`, i.e. an implied 650 uu/s^2 downward acceleration. That constant agrees with RLBot's documented default gravity; it is still a local prediction assumption for any particular map/mutator/runtime.

Worked example — low-side-pass, Bronze:
- origin [-2200, 3000, 93], lane [-250, 3900, 93] (scenarios.py:59-60); speed 900.0 * 1.00 = 900 uu/s (lines 62, 32).
- dx=1950, dy=900, length=hypot=2147.7 uu; velocity = [817.2, 377.2, 0.0] uu/s; arrival_seconds = 2147.7/900 = 2.386 s.
- timeout 15.0 s, so `shot_window_seconds = 15.0 - 2.386 = 12.61 s` (scenarios.py:354).
- Human at [0, 2250, 17], rotation [0, pi/2, 0], boost 100 (scenarios.py:45-51, 61). Bronze has no keeper/defender (`"keeper" not in profile`, line 249), so `bots={}`, `roles={"human":0}`, `teams={"human":0}`.
- Target: goal zone center_x=-350, half_width=900, min_z=93, max_z=550 (scenarios.py:63, 152, 355-356).

Same scenario, Diamond:
- speed 900.0 * 1.22 = 1098 uu/s (line 36); velocity = [997.0, 460.2, 0.0] uu/s; arrival = 2147.7/1098 = 1.956 s; timeout 12.0 s → shot window 10.04 s.
- Keeper added: `keeper = (4, .42, 1050.0, .85, 4350.0, 4780.0)` → level 4, difficulty .42, speed_limit 1050, reaction_delay .85 s, lane_limit_y 4350, depth 4780. `cover_x = data.get("keeper_x", -620 + 95*RANKS.index("diamond"))` = -620 + 95*4 = -240 (line 257). Keeper pose [-240, 4780, 17], rotation [0, -pi/2, 0], boost 100 (lines 258-264). `later_situation` is False for index 0, so no depth/lane adjustment.
- Defender added: `(3, .34, 900.0, 1.10)` → level 3, difficulty .34, speed_limit 900, reaction_delay 1.10 s; pose copied from `_HUMAN` with position = data["pressure"] = [-950, 3650, 17], rotation [0, -pi/2, 0] (lines 273-290). Roles: keeper→0, defender→1, human→2; teams: bots team 1, human team 0 (lines 348-349).

3. Setup table (per rank, from _PRESSURE, scenarios.py:31-44)
| rank | speed mult | timeout s | keeper (level, skill, speed_limit, reaction s, lane_limit_y, depth) | defender (level, skill, speed_limit, reaction s) |
| bronze | 1.00 | 15 | — | — |
| silver | 1.06 | 14 | — | — |
| gold | 1.11 | 14 | (2,.20,850,1.40,4400,4860) | — |
| platinum | 1.17 | 13 | (3,.30,950,1.10,4380,4830) | — |
| diamond | 1.22 | 12 | (4,.42,1050,.85,4350,4780) | (3,.34,900,1.10) |
| champion | 1.28 | 11 | (5,.55,1150,.65,4320,4720) | (4,.48,1050,.85) |
| grand-champion | 1.33 | 10 | (6,.68,1250,.48,4290,4660) | (5,.62,1200,.62) |
| supersonic-legend | 1.39 | 9 | (7,.80,1350,.34,4260,4600) | (6,.76,1350,.42) |
Roster is fixed per rank, so a rank change inside a match is refused: game_worker.py:736-738 compares `(team, role)` per index and raises "needs a different actor roster". Bronze→Diamond therefore cannot be a `training_scenario_step`; it requires a new match. This is a real constraint, not a bug.

4. Six-part player action contract (traced)
(a) Setup selection: `validate_setup`/`start_setup` (scenario_setup.py:13-29, 94-106) require exactly `{scenario_id, difficulty}` and re-validate through `scenario_definition`; `step_setup` (79-91) moves ±1 in the validated order and keeps rank.
(b) Match layout: adapter.match_config (adapter.py:40-120) builds bots from `scenario_descriptors` then appends `f.Human()` last (line 102), sets `enable_state_setting=bool(lesson_id)` (117), `instant_start`/`skip_replays` for training (113).
(c) Reset write: game_worker.reset (615-667) calls `engine.reset()` → settle_state, then `desired_state(settle_state, training_actor_index, bot_states)` (639) or the two-arg legacy form (642), sends once via `manager.rlbot_interface.send_msg` (643), resets every scenario controller (646-647), clears attempt bookkeeping (649-652).
(d) Settle→ready→go: engine.update settling branch (627-685) requires grounded, clean jump flags, position error <60 uu, speed <25 uu/s, |angular velocity| <0.2, sampled interval ≤0.05 s, `_bots_ready`, `_scenario_ball_ready`; then ≥0.25 s and ≥3 samples → emits `set_state` (starting_state) + `ready` (670-673). Ready branch (686-785) confirms the applied state within 2.0 s and emits `go` with `attempt_id`.
(e) Attempt: `_scenario` (477-579) requires launch baseline, a NEW human touch strictly after `started_at`, human as latest touch of all actors, a goal-target crossing at/after the touch, and a team-0 score edge at/after the crossing.
(f) Retry/next: retry = worker.reset (615) after `attempt_sent`/`attempt_acked` gate (633-634); next = `_change_training_scenario` (669-800) which builds a replacement engine, sends one `desired_state`, then swaps engine/controllers/descriptors (770-800).

5. State packet clock and acknowledgement
- Clock: `frame["time"] = packet.match_info.seconds_elapsed` (adapter.py:161); `frame_num` from `match_info.frame_num`; `game_speed` from `match_info.game_speed`. Cadence (cadence.py:37-114) uses `PHYSICS_STEP_SECONDS = 1/120`, `CLOCK_QUANTIZATION_SECONDS = 0.002`, `MAX_NORMAL_STEPS = 2`, frame-number modulus 2^32; a 1- or 2-step sample with matching dt is continuous, >2 steps or dt>0.05 s is a gap, and an explicit transport gap is never reclassified.
- Acknowledgement: the reset is *not* acked by the core; it is confirmed by observation. engine.py:705-734 compares the observed car/ball against the predicted post-reset state (position 120 uu, ball 200 uu, velocity 40 uu/s, rotation 0.15 rad, angular velocity 0.25, boost 2) within `elapsed < 2.0` s, and only then sets state="active" and freezes baselines (754-776). Attempt save ack is separate: `attempt_sent`/`attempt_acked` (game_worker.py:633-634, 649-651, 1374-1377).

6. Invariants
- Useful pass window: `shot_window_seconds = timeout - arrival_seconds` (scenarios.py:354) is positive for every rank/scenario read (e.g. Bronze 12.61 s, Diamond 10.04 s for low-side-pass). It is a *predicted* window from straight-line travel; it ignores wall bounces, the `bounce`/`drop` vertical offsets (lines 232-239) and any keeper deflection, so it is not a measured window.
- Full-actor reset: `desired_state` writes ball 0 plus every bot index plus the human in one `fill_desired_game_state` call (adapter.py:196-203), and rejects bot indexes that overlap the human (184-185). `_bots_ready` (engine.py:401-432) requires every configured bot to be observed in pose/velocity/rotation/angular-velocity/boost tolerance, so a missing actor fails preparation rather than starting with a fictional actor.
- Chain invalidation: any packet gap sets `chain_valid=False` permanently for the attempt (engine.py:495-498, 613); a non-play phase during active interrupts (587-616); a clock restart interrupts (623-626).

7. State that is NOT reset (traced callers)
- `engine.reset()` (203-267) clears attempt_id, state, timers, events, observations, metrics, recorder, scenario_state, `_emitted`, `_recent_frames`. It does NOT clear `self.scenario` (definition), `self.lesson`, `self.tolerances`, `self.preferences`, `self.metadata`, `self.bot_indices`, `self.human_index`. Callers: game_worker.reset (635) and `_change_training_scenario` (750) both rely on that persistence deliberately (preferences/tolerances are re-passed at 740-741).
- Scenario controllers: `ScenarioKeeperController.reset`/`ScenarioDefenderController.reset` (scenarios.py:424-428, 491-495) clear delegate, started_at, intent, last_decision. Called from game_worker.reset only when `self.scenario is not None` (644-647). On a scenario switch, `self.controllers` is replaced wholesale (780), so old controller state cannot leak.
- Worker fields cleared on reset: `applied_reset`, `attempt_sent`, `attempt_acked`, `attempt_retryable`, `auto_reset_at`, `playback_origin` (648-653). NOT cleared there: `self.last_frame` (cleared only in `_change_training_scenario`, 782), `self.mapping`, `self.ready_teams`, `self.seen_active`, `self.first_packet`, `self.telemetry_recovery_*`. `last_frame` surviving a retry is intentional: the engine's own `last_frame` is reset, and the worker's copy is only used for cadence/telemetry display.
- `scenario_state["seen_touch"]` is populated during settling and ready (engine.py:662, 752) and frozen into `baseline_touch` at go (758), so pre-reset touches cannot be counted. `score_baseline` is set at go (772-776) and also lazily in `_scenario` (502-504).

8. Exclusion guards actually traced (no bug asserted)
- Capture+scenario: rejected in adapter.match_config via `validate_capture_request` (adapter.py:45-52), in `scenario_descriptors` (scenarios.py:380-381), in worker setup (game_worker.py:446-448), and in TrainingEngine.__init__ (engine.py:129-131). Four independent guards; no single-callee claim is made.
- Non-power-shots lesson: `_validate` (scenarios.py:156-157) and `_change_training_scenario` (game_worker.py:681-683).
- Scenario switch while an attempt is pending: `engine.finished or attempt_sent is not None` (684-685); telemetry recovery pending (686-687).
- Bot input during reset: `scenario_idle` gate (game_worker.py:1281-1287) sends neutral controls to scenario bots unless `engine.state == "active"`.
- Human never in bot mapping: `map_team` (589) and `desired_state` (184-185).

9. Relevant existing tests (names only; bodies not read, not run)
tests/test_power_shot_scenarios.py, tests/test_scenario_setup.py, tests/test_training.py, tests/test_training_cadence.py, tests/test_domain_adversarial.py, tests/test_adapter_contract.py, tests/test_worker.py, tests/test_training_ghost_practice.py, tests/test_game_worker_ghost_practice.py. Grep shows scenario tests drive `engine.update(_frame(...))` at 1/120 s and assert `go`/`set_state`/`completed` sequences, and adapter tests assert `desired_state(...).pack()`.

10. Missing actual-game proof (limitations, not defects)
- The primary RLBot schema confirms radian rotation units. A live packet from this exact build remains unobserved.
- The 650 uu/s^2 gravity assumption agrees with RLBot's documented default, but active mutators/map values still need observation. The 2.0 s reset-confirmation deadline is an app policy, not a documented universal application time.
- `arrival_seconds`/`shot_window_seconds` are straight-line predictions; bounce/wall/backboard launches (scenarios.py:217-239) and keeper deflections are not modelled, so the "useful pass window" is unproven in play.
- Rank labels are explicitly "intended difficulty only; not a certified bot rank" (scenarios.py:326, 1302); no source evidence supports any rank-equivalence claim.
- Whether the keeper's `lane_limit_y` boundary override (scenarios.py:455-463) produces sane behaviour, and whether `_bots_ready` tolerances are achievable after a real `desired_state` write, need runtime observation.
- `_scenario` requires `"goal_target" in self._emitted` (engine.py:577), which is only emitted when `"ball_contact" in self._emitted` (1157); the `ball_contact` emitter was not read (engine.py:990-1084 not inspected), so the full success chain is not end-to-end verified here.

Verdict: research_only. Source math for launch geometry, rank pressure, reset/acknowledgement and exclusion guards is internally consistent and traced to callers; the interface units and default gravity are documented, while actual per-run physics and reset behavior remain unverified, and the success-chain emitter and bot controller internals were outside the read budget.

Primary-source cross-check by main (27 October 2026):
- [RLBot v5 schema](https://github.com/RLBot/flatbuffers-schema/blob/main/schema/gamedata.fbs) documents radian Rotator fields and uses that type for Physics.rotation.
- [RLBot useful game values](https://wiki.rlbot.org/v5/botmaking/useful-game-values/) documents +Z up, the Blue goal toward -Y, default gravity 650 uu/s², and a resting ball-center height of 93.15 uu. It separately lists a ball radius of 91.25 uu. The project's `_BALL_RADIUS = 93.15` must therefore be described as its local constant, not a verified collision radius. Use actual ball shape/build evidence for precise collision/ground tests. These documentation values do not certify modified maps or mutators.
