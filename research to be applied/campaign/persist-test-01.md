# PERSIST-TEST-01 — Focused existing persistence/import/ack checks

## Scope

Executed existing tests only in the isolated `work/reviewed-training` checkout (base `1fe8c85`; it already had a dirty working tree). No code or test files were authored or changed. The specified Python 3.12.13 virtual environment was used. `QT_QPA_PLATFORM=offscreen` kept the bridge tests’ `QApplication` fixture headless; the selected bridge file-dialog test monkeypatches the dialog. No Rocket League launch, game process attachment, or game input occurred.

## Exact pytest selection

The one invocation was `python -m pytest -q -p no:cacheprovider` with these node selectors, from `work/reviewed-training`:

```text
tests/test_storage.py::test_failed_replace_keeps_previous_save_and_cleans_temporary_file
tests/test_storage.py::test_repeated_import_replaces_with_same_single_result_without_duplication
tests/test_storage.py::test_invalid_import_preserves_current_save_bytes_and_rejects_before_archiving
tests/test_storage.py::test_corrupt_existing_save_is_preserved_and_never_implicitly_overwritten
tests/test_storage.py::test_last_good_backup_can_restore_over_a_later_valid_save
tests/test_content.py::test_import_identity_spaces_unicode_and_source_preservation
tests/test_content.py::test_import_size_limit_and_linked_destination_do_not_escape_user_data
tests/test_content.py::test_invalid_inputs_do_not_create_data_or_run_loaders
tests/test_training.py::test_recording_bound_import_rejection_and_private_provenance
tests/test_reference_capture.py::test_candidate_persistence_is_private_atomic_and_never_marks_permission_or_gate_passed
tests/test_reference_capture.py::test_attempt_ack_flow_persists_only_a_completed_engine_trial
tests/test_worker.py::test_attempt_ack_required_before_reset
tests/test_worker.py::test_auto_reset_waits_one_second_after_first_durable_ack_and_duplicate_ack_does_not_extend
tests/test_bridge.py::test_import_recording_uses_real_dialog_action_and_preserves_fixture_provenance
tests/test_bridge.py::test_attempt_event_acknowledges_the_worker_summary_id
tests/test_bridge.py::test_optional_match_review_persists_once_across_restart_and_rejects_late_score
tests/test_bridge.py::test_result_receipt_survives_save_failure_and_replays_exactly_once
```

Run command used the designated venv executable and PowerShell environment variables `QT_QPA_PLATFORM=offscreen`, `PYTHONDONTWRITEBYTECODE=1`; output is retained privately at `work/campaign-tests/persist-test-01-pytest.txt`.

## Result

**21 passed, 0 failed, 0 skipped; 12.72 seconds; exit code 0.** The parametrized selections account for 21 collected cases. This is the result of this invocation only; several selected bridge/storage checks may overlap prior reported preference/bridge runs, so do not add this count to prior totals as a unique-test count.

## What the checks establish

- `test_failed_replace_keeps_previous_save...` confirms a failed replacement leaves the previously committed live save and the saved backup bytes intact and removes the temporary file. It does not establish that the backup holds the proposed next save: the observed backup content is the prior live bytes.
- `test_last_good_backup_can_restore...` explicitly backs up one live state, saves a newer live state, imports the backup, and verifies the restored old state plus a `before-import-*` copy of the newer state. Repeated and invalid imports check idempotency and that rejected content does not mutate the current save or archive it.
- `test_content.py` checks a Unicode/space-containing source and Unicode destination path for map import identity/preservation, plus map-import rejection for linked destinations, bad path forms and size limits. This is map-import path validation, not a career-save or recording-export guard.
- The recording checks exercise bounded recorder output, malformed schema rejection without changing the source, private atomic candidate persistence, and candidate eligibility only for a completed engine trial. The bridge import test uses a monkeypatched file-picker result and verifies imported fixture provenance/status.
- Worker tests require a matching `attempt_ack` before reset and verify a duplicate matching acknowledgement does not extend the one-second auto-reset delay. The bridge test verifies it sends the worker summary ID in `attempt_ack`.
- Duplicate-event coverage: the optional-review bridge test ignores altered review text on a duplicate result and rejects a conflicting final score without changing persisted state. The result-receipt test verifies recovery/replay commits one completed fixture and one reward after a simulated save failure.

## Coverage limits

The focused search found no dedicated personal-recording **export path containment** test. The career storage test exports to a caller-supplied path containing spaces, but that is not a path-guard assertion. The map-import containment cases do not prove a save/recording export guard. No runtime filesystem behavior outside pytest temporary directories was exercised.
