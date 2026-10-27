# SCENARIO-ACCEPTANCE-TESTS-01 — bounded Power Shots source tests

Date: 2026-10-27
Candidate: frozen `work/reviewed-training`, HEAD `1fe8c85839a5e72166ee1d5cc3066627548d9fa2` plus dirty/untracked scenario files pinned below. This is test execution evidence only; it does not review or validate those changes for gameplay.

## Prior-run check

I searched the current campaign reports and receipts before running. `lesson-acceptance-tests-01.md` ran `tests/test_training.py` plus selected `tests/test_worker.py` nodes; it explicitly left every-rank/profile coverage open. `physics-01.md` listed `test_power_shot_scenarios.py` by name only and said test bodies were not read/run. No previous report or receipt recorded this selection, so this was not a duplicate run.

## Inspection before execution

Read the selected test bodies, their local helpers, `pyproject.toml`, and the cadence helper tests before running. There is no `conftest.py` at the candidate root or under `tests/`. The selected tests use synthetic frames and local test helpers, plus pytest's built-in `monkeypatch`; the adapter-facing tests replace RLBot's flat module with a local fake. No Qt, game, network, SDK, or compiler path is used by this selection.

The scenario module supplies a reusable `_frame`/`_prepare` helper that feeds authored settle/starting state back as observed telemetry. The cadence supplement separately exercises the generic readiness logic with `speed-flip` and frame-number pairs. Those helpers clarify that this run tests declared state-machine behavior, not engine-applied physical state.

## Command and result

Interpreter: the previously supplied Python 3.12 venv; observed version Python 3.12.13. Pytest version 9.0.2. Absolute interpreter path is omitted from this workspace report.

From the frozen checkout root, with `PYTHONPATH=src`, `PYTHONDONTWRITEBYTECODE=1`, and `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, the command was:

```powershell
& <existing Python 3.12 venv interpreter> -m pytest -q -p no:cacheprovider @selectedNodes
```

`selectedNodes` contained these existing node IDs:

```text
tests/test_power_shot_scenarios.py::test_all_situations_and_ranks_build_dynamic_roster_and_controllers
tests/test_power_shot_scenarios.py::test_adapter_supports_zero_or_one_scenario_bot
tests/test_power_shot_scenarios.py::test_launch_state_is_emitted_once_per_attempt_and_never_forces_active_physics
tests/test_power_shot_scenarios.py::test_retry_and_telemetry_recovery_reset_the_entire_dynamic_roster
tests/test_power_shot_scenarios.py::test_worker_scenario_step_wraps_same_rank_and_resets_engine_controllers_and_request
tests/test_power_shot_scenarios.py::test_worker_shuffle_and_mirror_keep_all_shots_and_rank_reset_every_actor_and_drop_mismatched_trace
tests/test_power_shot_scenarios.py::test_telemetry_recovery_budget_waits_for_active_phase
tests/test_power_shot_scenarios.py::test_settle_requires_configured_ball_and_every_configured_actor
tests/test_power_shot_scenarios.py::test_bouncing_beginner_settles_earlier_than_gold_low_volley
tests/test_power_shot_scenarios.py::test_bouncing_launch_is_confirmed_in_the_pre_bounce_next_packet_window
tests/test_power_shot_scenarios.py::test_ready_confirmation_waits_for_active_play_phase_without_spending_two_seconds
tests/test_power_shot_scenarios.py::test_active_clock_really_times_out_without_advancing_the_situation
tests/test_training_cadence.py::test_60hz_samples_can_settle_confirm_reset_and_start_training
tests/test_training_cadence.py::test_ordinary_reset_confirmation_uses_complete_pose_across_cadence_gap
tests/test_training_cadence.py::test_ordinary_reset_confirmation_rejects_corrupt_cadence
tests/test_training_cadence.py::test_ordinary_preparation_accepts_stationary_samples_with_explicit_packet_gaps
tests/test_training_cadence.py::test_ordinary_preparation_does_not_stitch_across_long_intervals_or_invalid_pose
```

**Result:** 130 passed, 0 failed. Pytest reported 1.13 seconds; measured process elapsed time, including interpreter startup, was 2.043 seconds. This is one selection's count only; it is not aggregated with any earlier 21/40/133/other report.

Case distribution: 96 scenario/rank constructor cases (12 situations × 8 ranks), 4 Human-slot adapter cases, 12 once-only launch cases, 2 Bronze/Gold recovery-roster cases, 3 Diamond scenario-step cases, 1 Diamond shuffle/mirror case, and 6 shared cadence/readiness cases, plus the remaining single-case Power Shots settle/phase/timer checks. Total: 130.

## What passed

- **96 scenario/rank constructions:** all 12 situation IDs × eight ranks produce the expected bot descriptors/controllers, role/team layout, Human index, no passer, and positive authored arrival/shot-window metadata. This is construction coverage only, not 96 game sessions.
- **State writes and slot mapping:** the adapter tests check Human indexes 0/1/2 for Bronze/Silver, Gold, and Diamond using a fake flat module. The once-per-attempt test exercises all 12 situations at Bronze: `_prepare` observes one start-state write, later active samples do not re-emit it, and an engine reset yields a parked ball followed by one new launch write.
- **Readiness gates:** tests reject a wrong parked-ball pose and missing configured keeper; distinguish beginner settled bounce from Gold low volley; accept a synthetic next-packet launch confirmation; and verify countdown/kickoff/goal-scored phases do not spend READY's two-second confirmation budget. A separate test confirms a synthetic active clock can time out without moving to another situation.
- **Roster reset/recovery:** the telemetry-recovery test verifies a whole parked-state write and controller reset for Bronze's empty bot roster and Gold's one-keeper roster. Three Diamond scenario-step cases and one Diamond shuffle/mirror case verify scenario replacement writes both bot indexes `{0,1}` along with the Human-selected reset. These use fake `desired_state` and manager interfaces.
- **Cadence supplement:** the generic engine accepts numbered 60 Hz/two-step samples; complete state can confirm ordinary reset despite a known coalescing gap; invalid-frame-number/physics-step-mismatch confirmation stays READY; explicit transport gaps can still contribute to ordinary *settling* samples; and long intervals or invalid poses break the sampled settle run. These cadence cases use the legacy `speed-flip` lesson rather than a Power Shots scenario.

## Coverage limits

- The 96 cases validate generated data and controller construction, not successful ball delivery, keeper behavior, defender behavior, shot opportunity, or outcomes in Rocket League. The once-only launch test covers all situations at Bronze only.
- The Power Shots `1/60` launch-confirmation helper omits `frame_num`; it exercises legacy clock-only cadence, not a numbered two-step sample. The actual numbered-coalescing tests in this selection use the generic `speed-flip` path, with no Power Shots-specific keeper/defender roster.
- Recovery coverage is not complete for the whole roster. `test_retry_and_telemetry_recovery_reset_the_entire_dynamic_roster` uses only Bronze (zero bots) and Gold (one keeper); the Diamond two-bot checks cover scenario-step or mirror writes, not retry/telemetry recovery. No selected test proves a Diamond two-bot recovery reset.
- The scenario `_frame` helper feeds desired positions/velocities back as observed packets. The tests cannot prove that RLBot or the game accepted either write, that a ball actually moves or bounces as predicted, that the map/mutators match the authored geometry, that contacts occur, or that any rank is enjoyable or calibrated.
- No test here covers online play, a Workshop map, native UI input, save durability, actual attempt acknowledgements, or a live match. The result is offline unit evidence only.

## Hashes and provenance

The tests/sources were not edited for this task. These are SHA-256 hashes of the exact bytes used. The scenario source/test files are untracked and several other selected implementation/test files are modified relative to HEAD in this candidate; the hash pins, not HEAD alone, identify the test inputs.

| File | SHA-256 |
|---|---|
| `tests/test_power_shot_scenarios.py` | `c1e7c9af2b2d46db3fb8e0531668332cedb9e71f8be5c05e597a10fcb0e7dc26` |
| `tests/test_training_cadence.py` | `2ca7b33768cc97aafba71ecd02b702bcd4da2edef2929e99e100feb749b42ea0` |
| `src/my_career_training/training/scenarios.py` | `35714a224aa8765ae62be6fde3df6dc87c088c32d297adcda3795d0bc682d979` |
| `src/my_career_training/training/engine.py` | `37028379a268d6f6e19d42b32a9e3c20778ed4f41d87bfbd3bc76955c61c602a` |
| `src/my_career_training/game_worker.py` | `2e3982dfc352e4fafcd667898b3cb1f76538b61447c2b6e47adc6d9f862e89c2` |
| `src/my_career_training/adapter.py` | `98d1f4612967eda756b21857dfd198a3a12e4a211684067a248b9a829b74285c` |
| `src/my_career_training/training/cadence.py` | `fdbcda80e4fadb135713314e0fb65e2bcf2a3cf848f9261413fc2803555ee240` |
| `pyproject.toml` | `8f6efedc33f60e9009c007846fcb28f874e4de30c4a11775be615e44a922682b` |

No code/tests were authored or changed. No game, network, download, install, or native compile action was performed. No pytest cache or Python bytecode was requested (`-p no:cacheprovider`, `PYTHONDONTWRITEBYTECODE=1`).
