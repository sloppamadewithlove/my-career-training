# RANK-LIFECYCLE-TESTS-01 — focused offline transition checks

Existing-test execution only in frozen `work/reviewed-training`. No code or tests were authored or changed. The selected cases were not present in the exact node lists in LESSON-ACCEPTANCE-TESTS-01, SCENARIO-ACCEPTANCE-TESTS-01, BROWSER-ACCEPTANCE-TESTS-01, or PERSIST-TEST-01. The browser report did run the adjacent whole-setup persistence test, but not the busy-gate or Return/cleanup case below. Their prior totals are not combined with this run.

## Command and result

Python 3.12.13, pytest 9.0.2. `my_career_training` resolved to `work/reviewed-training/src/my_career_training/__init__.py`; `PYTHONPATH` was the absolute `src` directory of that frozen checkout. The explicit interpreter was the existing Python 3.12.13 virtual-environment executable; its private machine path is omitted.

Environment: `PYTHONDONTWRITEBYTECODE=1`, `QT_QPA_PLATFORM=offscreen`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`; pytest cache disabled. Sanitized command from the frozen checkout root (the actual run used the explicit interpreter described above):

```powershell
$env:PYTHONPATH = (Resolve-Path 'src').Path
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:QT_QPA_PLATFORM = 'offscreen'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
python -B -m pytest -q -p no:cacheprovider `
  tests/test_bridge.py::test_power_shots_selection_refuses_busy_state_before_commit `
  tests/test_bridge.py::test_pending_career_is_byte_for_byte_preserved_through_lesson_start_cleanup_and_return `
  tests/test_bridge.py::test_running_power_shots_stop_reason_blocks_late_accepted_ack_save `
  tests/test_worker.py::test_cleanup_failure_does_not_report_stopped `
  tests/test_worker.py::test_dead_session_cleanup_failure_cannot_acknowledge_shutdown `
  tests/test_worker.py::test_shutdown_preserves_post_core_writer_and_rejects_stale_session
```

**Result:** 8 passed, 0 failed; pytest reported 11.74 seconds. The measured process time was about 11.94 seconds, including startup. The captured output is `work/campaign-tests/rank-lifecycle-tests-01-pytest-candidate.txt` (SHA-256 `7d030eb80902c9951c3b4f2003de96c93681fd669a7672c6ca03a62fe95b43ec`). An initial command from the workspace root collected no tests and exited 4 because the node paths were relative to the checkout. That failed pre-collection output is retained separately at `work/campaign-tests/rank-lifecycle-tests-01-pytest.txt`; it is not counted as test execution.

## Covered cases and limits

- `test_power_shots_selection_refuses_busy_state_before_commit` is parameterized across worker, frozen lifecycle, and native training pack. All three reject before document/save commit. It does not individually exercise every busy condition in the bridge guard.
- `test_pending_career_is_byte_for_byte_preserved_through_lesson_start_cleanup_and_return` preserves a nontrivial career save through lesson start and a Return transition, but fakes the worker launch/process and injects a `stopped` event before calling `_tick`.
- `test_running_power_shots_stop_reason_blocks_late_accepted_ack_save` confirms a valid-looking scenario-step ACK received after stop begins does not change the saved setup.
- `test_cleanup_failure_does_not_report_stopped` injects a cancellation and synthetic teardown `OSError`; it expects an error and no stopped event. `test_dead_session_cleanup_failure_cannot_acknowledge_shutdown` makes map-journal recovery fail, verifies shutdown stays open without an ACK, then allows cleanup and sees `stopped`.
- `test_shutdown_preserves_post_core_writer_and_rejects_stale_session` supplies a wrong session ID to a fake running session and verifies rejection before join/stop side effects; the matching session then follows the bounded join path.

The bridge fixture uses `tmp_path` and monkeypatches installation detection, game-process checks, process liveness, game close, and online launch; worker fixtures use `tmp_path`, a synthetic request, and fake thread/core/map-guard objects. `test_worker.py` states it avoids the Windows SDK and game launch. No network call, game process, RLBot runtime, native build, hardware, or live menu was used. These are offline boundary checks, not live Back→rank→Start acceptance.

## Input hashes

| File | SHA-256 |
| --- | --- |
| `tests/test_bridge.py` | `5b3bafe6819319a9b77d332a9c9c0db78dcdc5aaf95781482429d275b1d39cec` |
| `tests/test_worker.py` | `d10ebb2a6e707633a278ed3c93b70de3185db04564ecc3180d6a9d7731e6aa11` |
| `src/my_career_training/bridge.py` | `ac502d1f19810baca479a534aa766a6afbea7ba57a405452835cc9dcff379ac2` |
| `src/my_career_training/game_worker.py` | `2e3982dfc352e4fafcd667898b3cb1f76538b61447c2b6e47adc6d9f862e89c2` |
| `pyproject.toml` | `8f6efedc33f60e9009c007846fcb28f874e4de30c4a11775be615e44a922682b` |
