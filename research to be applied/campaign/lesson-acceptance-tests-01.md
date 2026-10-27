# LESSON-ACCEPTANCE-TESTS-01 — offline lesson and attempt-end checks

## Scope and setup

One bounded pytest run used the existing Python 3.12.13 / pytest 9.0.2 environment and the frozen checkout's `src` as `PYTHONPATH`. The selected modules are pure engine/worker tests: no Qt display setting was needed. The `test_worker.py` module documents that it avoids the Windows SDK and game launch; its selected recovery helpers stub RLBot, packet normalization, hitbox lookup and bot manager behavior. Test fixtures are local helpers plus pytest's built-in `tmp_path` and `monkeypatch`. No `conftest.py` exists in this checkout; `pyproject.toml` sets `pythonpath = ["src"]`.

Git status reports the selected test and implementation files modified relative to HEAD. I did not inspect their diffs; the exact worktree bytes used are pinned below. No source or test files were edited for this task.

## Exact bounded selection and result

From the frozen checkout root, the single executed selection was:

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
& <specified Python 3.12 venv interpreter> -m pytest -q -p no:cacheprovider `
  tests/test_training.py `
  tests/test_worker.py::test_attempt_ack_required_before_reset `
  tests/test_worker.py::test_auto_reset_waits_one_second_after_first_durable_ack_and_duplicate_ack_does_not_extend `
  tests/test_worker.py::test_prestart_attempt_ack_does_not_schedule_automatic_reset `
  tests/test_worker.py::test_finished_acknowledged_attempt_survives_recovery_when_auto_reset_disabled `
  tests/test_worker.py::test_auto_reset_recovery_preserves_acknowledgement_feedback_delay `
  tests/test_worker.py::test_fresh_recovery_waits_for_save_ack_then_resumes_bounded_auto_reset `
  tests/test_worker.py::test_only_attempts_with_recorded_samples_are_eligible_for_auto_retry `
  tests/test_worker.py::test_high_rate_inbox_is_bounded_and_preserves_active_before_terminal `
  tests/test_worker.py::test_stop_return_request_remains_immediate_during_telemetry_recovery `
  tests/test_worker.py::test_stop_request_blocks_bot_controls_before_queued_stop_is_processed `
  tests/test_worker.py::test_stop_request_blocks_reset_engine_and_ghost_work
```

`PYTHONPATH=src` and `PYTHONDONTWRITEBYTECODE=1` were set for that process; `-p no:cacheprovider` avoided pytest cache writes. The interpreter resolved `my_career_training` from this checkout's `src` tree.

**Result:** 40 passed, 0 failed. Pytest reported 0.92 seconds; measured process elapsed time, including interpreter startup, was 3.036 seconds. This is one run's count only.

## What the checks establish

- `test_all_eight_catalog_entries_have_reset_and_honest_reference_boundary` checks the catalog contains eight unique IDs and each entry has success events, steps and a settle state, an empty reference-recording list, seven assistance defaults and controller overlay enabled by default. It also checks catalog data is returned independently after mutation.
- The only explicit `configure_lesson` variant test in this file exercises simplified `flip-reset` and left-side `aerial-air-roll`; it checks the simplified start state retains normal game speed and the mirror changes the target side.
- The Power Shots reset test feeds settle-pose frames until the engine reaches `ready`, then checks an out-of-position frame interrupts; retry clears events and samples and returns to settling. The separate settle test checks jump contamination and a packet gap keep the engine settling until fresh clean samples arrive. `test_transition_gap_does_not_overwrite_an_already_finished_attempt` preserves a finished timeout outcome across an unavailable-telemetry interruption.
- Worker tests reject reset before a matching attempt acknowledgement, ignore a mismatched acknowledgement and accept a matching one; the manual-reset test does not call reset again after the matching acknowledgement. Auto-retry tests schedule one second after the first acknowledgement, avoid scheduling for a pre-start interruption, and prevent duplicate acknowledgements from extending the deadline. Recovery cases preserve a finished attempt with auto-reset disabled and delay automatic reset until telemetry is fresh and the acknowledgement-based deadline arrives.
- The selected queue test retains the latest active packet ahead of a terminal packet. Stop tests show that a Return-style stop request remains immediate during telemetry recovery and blocks bot controls, engine updates, reset and ghost work while stop processing is pending.

## Coverage limits

- The eight-entry test validates catalog shape, not successful `configure_lesson` selection or gameplay behavior for each lesson. Only two named lesson variants are explicitly selected by `configure_lesson` in this file; the Power Shots reset test is an engine-state test, not a successful shot trial.
- These tests do not verify every rank/profile, lesson-to-rank routing, or a full eight-lesson launch/finish/retry cycle. They do not establish that all lessons work in Rocket League.
- The selected worker tests do not exercise next/previous-situation rejection after a finished, acknowledged attempt; that guard remains unverified by this selection. They also do not establish exact-once attempt publication through the native bridge, a durable save in the application, return arrival at the game hub, or resource restoration.
- All terminal/recovery tests use synthetic telemetry and manually initialized terminal state with fakes. They do not observe ball disappearance, ball/car motion, score success, timeout timing in live game packets, native HUD output, or any actual game effect. They cannot resolve ATTEMPT-END-01's live acceptance target.

## Hash-pinned test and source files

| File | SHA-256 |
| --- | --- |
| `tests/test_training.py` | `0da5646aa0c2873287f86d6b2f5c0e0d51e1e9ac06aeb7b550e85fa429dddb9d` |
| `tests/test_worker.py` | `d10ebb2a6e707633a278ed3c93b70de3185db04564ecc3180d6a9d7731e6aa11` |
| `pyproject.toml` | `8f6efedc33f60e9009c007846fcb28f874e4de30c4a11775be615e44a922682b` |
| `src/my_career_training/training/__init__.py` | `35aa775d8a2c5ba61d6a14f3f75d275c3c40640c4092cb6fca397abc46322162` |
| `src/my_career_training/training/engine.py` | `37028379a268d6f6e19d42b32a9e3c20778ed4f41d87bfbd3bc76955c61c602a` |
| `src/my_career_training/training/recordings.py` | `8effb8f438b39c4abe4901d683dc6e5e0424baa7f696dc35143b282cc5aa96f1` |
| `src/my_career_training/game_worker.py` | `2e3982dfc352e4fafcd667898b3cb1f76538b61447c2b6e47adc6d9f862e89c2` |
| `src/my_career_training/adapter.py` | `98d1f4612967eda756b21857dfd198a3a12e4a211684067a248b9a829b74285c` |
