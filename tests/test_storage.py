"""Persistence failure contracts using local files only; no game/runtime claims."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from my_career_training import career, storage


def _single_completed_result_state():
    state = storage.default_state()
    saved_career = career.new_career("Storage Test", seed=812)
    fixture = career.next_fixture(saved_career)
    session_id = "storage-result-session"
    pending = career.start_fixture(saved_career, session_id)
    state["career"] = career.complete_fixture(
        pending, fixture["id"], session_id, 3, 2
    )
    return state


def _result_and_reward_counts(state):
    current = state["career"]["seasons"][state["career"]["current_season"]]
    completed = [f for f in current["fixtures"] if f["status"] == "completed"]
    human_results = [
        f for f in completed
        if "human" in (f["home"], f["away"]) and f["result"]["provenance"] == "game"
    ]
    rewards = [r for r in state["career"]["rewards"] if r["type"] == "match_experience"]
    return len(human_results), len(rewards)


def test_failed_replace_keeps_previous_save_and_cleans_temporary_file(tmp_path, monkeypatch):
    with storage.Store(tmp_path) as store:
        original = storage.default_state()
        original["settings"]["text_scale"] = 1.1
        store.save(original)
        original_bytes = store.path.read_bytes()
        updated = storage.default_state()
        updated["settings"]["text_scale"] = 1.4

        real_replace = storage.os.replace

        def fail_current_replace(source, destination):
            if Path(destination).resolve() == store.path.resolve():
                raise OSError("simulated failure before the new save is installed")
            return real_replace(source, destination)

        monkeypatch.setattr(storage.os, "replace", fail_current_replace)
        with pytest.raises(OSError, match="simulated failure"):
            store.save(updated)

        assert store.path.read_bytes() == original_bytes
        assert store.backup_path.read_bytes() == original_bytes
        assert store.load() == original
        assert list(tmp_path.glob(".mct-*")) == []


def test_failed_result_save_can_be_retried_after_restart_without_duplicate_award(tmp_path, monkeypatch):
    state = storage.default_state()
    started = career.new_career("Crash Test", seed=991)
    fixture = career.next_fixture(started)
    session_id = "result-durable-retry"
    started = career.start_fixture(started, session_id)
    state["career"] = started

    store = storage.Store(tmp_path)
    store.save(state)
    completed = dict(state)
    completed["career"] = career.complete_fixture(
        started, fixture["id"], session_id, 4, 2
    )
    real_replace = storage.os.replace

    def fail_new_save(source, destination):
        if Path(destination).resolve() == store.path.resolve():
            raise OSError("simulated crash before completed state replacement")
        return real_replace(source, destination)

    monkeypatch.setattr(storage.os, "replace", fail_new_save)
    with pytest.raises(OSError, match="simulated crash"):
        store.save(completed)
    store.close()

    monkeypatch.setattr(storage.os, "replace", real_replace)
    with storage.Store(tmp_path) as restarted:
        recovered = restarted.load()
        assert recovered == state
        recovered_career = career.complete_fixture(
            recovered["career"], fixture["id"], session_id, 4, 2
        )
        repeated = career.complete_fixture(
            recovered_career, fixture["id"], session_id, 4, 2
        )
        recovered["career"] = repeated
        restarted.save(recovered)
        after_restart = restarted.load()
        assert _result_and_reward_counts(after_restart) == (1, 1)
        assert after_restart["career"]["record"]["played"] == 1


def test_error_after_replace_is_recovered_as_already_committed_result(tmp_path, monkeypatch):
    state = storage.default_state()
    started = career.new_career("Uncertain Commit", seed=130)
    fixture = career.next_fixture(started)
    session_id = "post-replace-failure"
    state["career"] = career.start_fixture(started, session_id)
    completed = dict(state)
    completed["career"] = career.complete_fixture(
        state["career"], fixture["id"], session_id, 2, 1
    )

    store = storage.Store(tmp_path)
    store.save(state)
    real_replace = storage.os.replace
    def replace_and_mark(source, destination):
        result = real_replace(source, destination)
        if Path(destination).resolve() == store.path.resolve():
            # Inject immediately after the atomic commit on every platform.
            # Windows has no POSIX directory-fsync step to intercept.
            raise OSError("simulated uncertainty after atomic replace")
        return result

    monkeypatch.setattr(storage.os, "replace", replace_and_mark)
    with pytest.raises(OSError, match="after atomic replace"):
        store.save(completed)
    store.close()

    monkeypatch.setattr(storage.os, "replace", real_replace)
    with storage.Store(tmp_path) as restarted:
        recovered = restarted.load()
        # The caller could not know whether the replace committed. Replaying the
        # same final packet against the recovered save must be a no-op.
        recovered["career"] = career.complete_fixture(
            recovered["career"], fixture["id"], session_id, 2, 1
        )
        restarted.save(recovered)
        assert _result_and_reward_counts(restarted.load()) == (1, 1)


def test_repeated_import_replaces_with_same_single_result_without_duplication(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    source = storage.Store(source_dir)
    exported_state = _single_completed_result_state()
    source.save(exported_state)
    source_file = source.export_file(tmp_path / "career export.json")
    source.close()

    with storage.Store(tmp_path / "destination") as destination:
        first = destination.import_file(source_file)
        second = destination.import_file(source_file)
        assert first == second == destination.load()
        assert _result_and_reward_counts(destination.load()) == (1, 1)


@pytest.mark.parametrize(
    "bad_bytes",
    [
        b"{broken json",
        json.dumps({**storage.default_state(), "schema_version": 99}).encode("utf-8"),
        b"\xff\xfe",
    ],
)
def test_invalid_import_preserves_current_save_bytes_and_rejects_before_archiving(
    tmp_path, bad_bytes
):
    with storage.Store(tmp_path / "destination") as store:
        original = storage.default_state()
        original["settings"]["text_scale"] = 1.2
        store.save(original)
        original_bytes = store.path.read_bytes()
        invalid = tmp_path / "invalid.json"
        invalid.write_bytes(bad_bytes)

        with pytest.raises(ValueError):
            store.import_file(invalid)

        assert store.path.read_bytes() == original_bytes
        assert store.load() == original
        assert list(store.directory.glob("before-import-*.json")) == []


def test_corrupt_existing_save_is_preserved_and_never_implicitly_overwritten(tmp_path):
    with storage.Store(tmp_path) as store:
        damaged_bytes = b'{"schema_version":1,"career":'
        store.path.write_bytes(damaged_bytes)

        with pytest.raises(ValueError, match="damaged"):
            store.load()
        with pytest.raises(ValueError, match="damaged"):
            store.save(storage.default_state())

        assert store.path.read_bytes() == damaged_bytes
        assert not store.backup_path.exists()


def test_last_good_backup_can_restore_over_a_later_valid_save(tmp_path):
    with storage.Store(tmp_path) as store:
        original = storage.default_state()
        original["settings"]["text_scale"] = 0.9
        store.save(original)
        store.backup()

        newer = storage.default_state()
        newer["settings"]["text_scale"] = 1.5
        store.save(newer)
        assert store.load() == newer

        restored = store.import_file(store.backup_path)

        assert restored == original
        assert store.load() == original
        # Import preserves the previously active save before replacing it.
        preserved = list(store.directory.glob("before-import-*.json"))
        assert len(preserved) == 1
        assert json.loads(preserved[0].read_text(encoding="utf-8")) == newer


def test_single_instance_lock_rejects_second_store_and_releases_on_close(tmp_path):
    first = storage.Store(tmp_path)
    try:
        lock_size = (tmp_path / "app.lock").stat().st_size
        with pytest.raises(RuntimeError, match="already open"):
            storage.Store(tmp_path)
        assert (tmp_path / "app.lock").stat().st_size == lock_size
    finally:
        first.close()

    with storage.Store(tmp_path):
        pass
