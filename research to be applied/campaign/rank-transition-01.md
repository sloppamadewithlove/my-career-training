# RANK-TRANSITION-01: changing a practice rank safely

Read-only source and existing-test audit of `work/reviewed-training`. Tests were inspected but not run; no live menu/session was exercised. Claims below describe the bound source artifact, not runtime acceptance.

## Finding

Power Shots rank changes are an idle preflight selection. The source does not switch rank inside an active match, even when the old and new ranks use the same bot roster. The supported route is: pause → **Return to My Career** → wait for worker cleanup and hub readiness → Lessons → Power Shots **Choose rank** → select rank → **Start shot 1**. This route is the same for Bronze↔Silver, Gold↔Platinum, and changes across roster boundaries.

| Selection | Current roster grouping | Supported transition |
| --- | --- | --- |
| Bronze ↔ Silver | no scenario bots | Return, stop old worker, select, start a new worker |
| Gold ↔ Platinum | keeper | same full return/restart path |
| Silver ↔ Gold | adds keeper | same full return/restart path |
| Platinum ↔ Diamond | adds defender | same full return/restart path |

The roster groups follow the scenario descriptors in `src/my_career_training/training/scenarios.py:247-291,377-401` and the all-ranks roster test `tests/test_power_shot_scenarios.py:88-128`. An in-session `training_scenario_step` carries direction, not difficulty; `_change_training_scenario` retains the current difficulty and refuses a changed actor/team/role roster (`src/my_career_training/game_worker.py:669-738`). It is a shot transition, not a rank transition.

## Route and state boundaries

1. **Enter the rank page.** The Lessons row presents Power Shots as “Choose rank” and dispatches `select_lesson`; selecting it sets the page to `Lesson` (`plugin/include/NativeCareerLayout.h:1600-1616,688-692`). The page exposes eight ranks and a Start shot 1 action. Choosing a rank dispatches `lesson_scenario`, preserving the selected scenario ID and changing its difficulty; Start uses that saved difficulty (`:1793-1832`). The native layout test checks eight rows, current selection, Start, and that rank/Start are disabled while the lesson is running (`plugin/tests/native_career_layout_tests.cpp:504-546`).
2. **Return from the active lesson.** Pause binds Return to the active `expected_session_id` and fixture (`plugin/include/NativeMatchLayout.h:681-701`); the Python bridge rejects a changed binding and sets `return_hub` (`src/my_career_training/bridge.py:1106-1154`). A lesson has no career fixture to abandon. The native host treats `return_hub` as a gated native navigation action (`plugin/src/NativeMovieHost.cpp:575-615`); this source path is not a live menu observation.
3. **Wait for the old activity.** `_begin_stop` saves current data and sends `shutdown`. The worker validates any supplied session ID, stops the session, and reports `stopped` only after cleanup succeeds; cleanup failures produce an error instead (`src/my_career_training/bridge.py:2225-2248`; `src/my_career_training/game_worker.py:304-312,958-962,1588-1595,1610-1652`). In the in-game return branch, the game stays open while the bridge waits for the worker process to exit, drains activity results, clears the old session, and only then marks the hub ready (`bridge.py:2264-2276,2315-2350`).
4. **Select and persist.** `lesson_scenario` validates the selection and refuses it while a worker/request/session, launch/stop transition, non-Idle state, training pack, or relevant background operation is active. It then commits only `lesson_scenarios["power-shots"] = {scenario_id, difficulty}` (`bridge.py:1361-1377`). This is why even a same-roster rank change goes through the idle gate.
5. **Start a fresh profile.** `start_lesson` resolves the saved scenario and difficulty, allocates a new UUID session request, and forwards both to the worker. If a worker is still active, a pending launch waits behind `_begin_stop`; `_launch` resets transition state and starts the new session (`bridge.py:1726-1808,1819-1835`). The selected setup creates new scenario state and bot descriptors from the chosen difficulty (`training/scenarios.py:294-355,377-390`).
6. **Keep identities separate.** Worker commands reject a different session ID (`game_worker.py:1625-1652`); bridge events with a different session ID are discarded (`bridge.py:1911-1921`). Stop events include the session ID and stop command ID, but the bridge's `stopped` branch checks the session ID filter and does not compare the echoed command ID before cleanup (`game_worker.py:304-312,1594`; `bridge.py:2098-2110`). Session/process serialization prevents the next launch until the old worker exits, but exact stop-ID acknowledgement is not enforced by this branch.

The `career` object is not modified by a training start/return. Completed attempts and recordings are saved through their own event/ack path; Power Shots summaries and recording metadata include scenario, difficulty/rank, and scenario version (`training/engine.py:269-280,1268-1305`; `bridge.py:2086-2090,2187-2200`). There is no per-rank unlock or mastery state in the save contract. `test_pending_career_is_byte_for_byte_preserved_through_lesson_start_cleanup_and_return` checks a nontrivial unfinished career fixture remains byte-for-byte unchanged (`tests/test_bridge.py:505-566`).

## Existing coverage and remaining acceptance

Inspected, not run:

- `tests/test_bridge.py:152-163` verifies durable Power Shots setup selection; `:403-446` checks busy selection refusal, persisted setup forwarding, and that ordinary lesson starts remain rank-free.
- `tests/test_bridge.py:505-590` covers career preservation and Power Shots launch identity. `:1840-1857` prevents a late in-session scenario acknowledgement from persisting after stop begins.
- `tests/test_power_shot_scenarios.py:654-708,765-787` covers same-rank shot stepping, invalid commands, and retained results. The all-ranks tests at `:88-128` cover descriptors/rosters.
- `tests/test_worker.py:846-890` covers cleanup failure, refusal to acknowledge incomplete cleanup, and rejection of a shutdown for a different session. `tests/test_bridge.py:1159-1168` covers return priority after startup timeout.
- `plugin/tests/native_training_browser_tests.cpp:343-408` and `plugin/tests/native_career_layout_tests.cpp:504-546` cover the separate rank page and rank-view protocol behavior.

Not established by those tests: a live pause→return→rank→start journey, old-worker non-control in Rocket League after the transition, eight-rank end-to-end transitions on both same-roster and changed-roster boundaries, or stop command-ID correlation in the bridge. Add a transition test that feeds a wrong stop ID for the current session and confirms it cannot authorize Return/new launch, or explicitly document session-only acknowledgement as the intended contract. Live acceptance should run all four transitions in the table, confirm the old worker exits before the new request starts, check the selected rank and scenario in the new session/attempt, verify attempts and career state remain intact, and retry after a cleanup error.

## Reuse for the other seven lessons

The shared Return/stop/new-session path can be reused, but the profile model cannot: current `lesson_scenario` validation and difficulty setup are Power Shots-only; the other seven accept `{id}` and use their existing fixed or variant setups (`bridge.py:1729-1792`; `training/scenario_setup.py:8-50,94-107`; `training/catalog.py:80-190`). For each future practice tier, keep the selected lesson/profile immutable during an attempt, persist a versioned profile identity per lesson, create a new session for an idle rank change, and attach that identity to attempt/recording/ghost compatibility. Treat Bronze–SSL as intended practice challenge labels unless separately calibrated; do not interpret them as player MMR.

## Artifact binding

Source hashes (SHA-256): `NativeCareerLayout.h` `17d2ec0a82c79fad1949715ad62840bcace4177cbbe137da3aa675289109eb78`; `NativeMatchLayout.h` `a986f0ed827f11ef2716c8fc6bb196d55f822cc22c6b5316b0fde0bb278a8d53`; `NativeMovieProtocol.h` `596422f6d2e07946678188257ba7e75cc21c8a7fa40b98a49d1736868e97600b`; `bridge.py` `ac502d1f19810baca479a534aa766a6afbea7ba57a405452835cc9dcff379ac2`; `game_worker.py` `2e3982dfc352e4fafcd667898b3cb1f76538b61447c2b6e47adc6d9f862e89c2`; `scenarios.py` `35714a224aa8765ae62be6fde3df6dc87c088c32d297adcda3795d0bc682d979`; `scenario_setup.py` `d2421bf8f7ac2508e9f3a65db21b2847a0e147b75cc62a6159a976999536a0fe`.
