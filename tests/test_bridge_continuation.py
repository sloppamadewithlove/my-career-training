"""Continuation transaction checks with synthetic matches, not gameplay evidence."""
from __future__ import annotations

import copy
import uuid

import pytest
from PySide6.QtCore import QProcess

from my_career_training import bridge, career
from test_bridge import FakeProcess, backend as backend_fixture, qt_app as qt_app_fixture

backend = backend_fixture
qt_app = qt_app_fixture


def finished(backend, monkeypatch, format=3):
    instance, game, _ = backend
    game["value"] = True
    session = str(uuid.uuid4())
    state = copy.deepcopy(instance.document)
    state["career"] = career.start_fixture(career.new_career("Continuation test", format=format, seed=42), session)
    instance._commit(state)
    fixture = copy.deepcopy(career.next_fixture(state["career"]))
    instance.in_game = True
    instance.owned_game = bridge.ProcessIdentity(1234, 123.0, "C:/SyntheticGame/RocketLeague.exe")
    monkeypatch.setattr("my_career_training.bootstrap.verify_owned_offline", lambda identity: bool(game["value"]))
    instance.request = {"fixture": fixture, "session_id": session}
    instance.session_id = session
    instance.session_state = "Playing"
    instance.process = FakeProcess()
    instance.setup_required = False
    instance._event({"type": "result", "session_id": session, "fixture_id": fixture["id"],
                     "home_score": 2, "away_score": 1, "provenance": "game"})
    instance.process.writes.clear()
    return instance, {"expected_session_id": session, "expected_fixture_id": fixture["id"],
        "expected_next_fixture_id": career.next_fixture(instance.document["career"])["id"],
        "lineup_ids": instance.document["career"]["lineup"], "continuation_intent": "a" * 32}


def cleanup(instance):
    instance._event({"type": "stopped", "session_id": instance.session_id})
    instance.process.current_state = QProcess.NotRunning
    instance._tick()


def start_payload(payload):
    return {key: value for key, value in payload.items() if key != "lineup_ids"}


def test_prepare_saves_only_lineup_then_ack_waits_for_stopped_worker(backend, monkeypatch):
    instance, payload = finished(backend, monkeypatch)
    before = copy.deepcopy(instance.document["career"])
    payload["lineup_ids"] = before["squad"][-2:]
    instance.dispatch("prepare_next_match", payload)
    assert not instance.error
    saved = instance.store.load()["career"]
    assert saved["lineup"] == payload["lineup_ids"] and saved["pending_session"] is None
    assert saved["rewards"] == before["rewards"] and saved["recruits"] == before["recruits"]
    assert instance.pending_launch is None and instance.native_next_ready is None
    assert len(instance.process.writes) == 1
    instance.dispatch("prepare_next_match", payload)
    assert not instance.error and len(instance.process.writes) == 1
    cleanup(instance)
    assert instance.session_state == "Idle" and instance.session_id is None
    assert instance.native_next_ready == {"session_id": payload["expected_session_id"],
        "fixture_id": payload["expected_fixture_id"], "next_fixture_id": payload["expected_next_fixture_id"], "intent": "a" * 32}
    assert instance.native_return_ready and instance.pending_launch is None
    assert instance.store.load()["career"] == saved


@pytest.mark.parametrize("change", ["session", "fixture", "next_fixture", "lineup", "extra", "intent",
                                    "pending_launch", "stop", "lifecycle", "confirming", "worker_stopping", "game", "training"])
def test_prepare_rejects_invalid_or_conflicting_request_without_save_or_stop(backend, monkeypatch, change):
    instance, payload = finished(backend, monkeypatch)
    if change in {"session", "fixture", "next_fixture"}:
        payload[f"expected_{change}_id"] = "different"
    elif change == "lineup":
        payload["lineup_ids"] = ["not-recruited", "not-recruited"]
    elif change == "extra":
        payload["abandon"] = True
    elif change == "intent":
        payload["continuation_intent"] = "invalid"
    elif change == "pending_launch":
        instance.pending_launch = {"lesson_id": "speed-flip"}
    elif change == "stop":
        instance.stop_reason = "restart"
    elif change == "lifecycle":
        instance.lifecycle.state = "Error/Recovery"
    elif change == "confirming":
        instance.lifecycle.confirming = True
    elif change == "worker_stopping":
        instance.stopping_worker = True
    elif change == "game":
        backend[1]["value"] = False
    else:
        instance.request["lesson_id"] = "speed-flip"
    before = instance.store.load()
    instance.dispatch("prepare_next_match", payload)
    assert instance.error and instance.store.load() == before
    assert not instance.process.writes and instance._prepared_next is None
    assert instance.native_next_ready is None
    if change not in {"extra", "intent"}:
        assert instance.native_next_rejected["intent"] == "a" * 32


def test_failed_lineup_save_rejects_before_cleanup_and_can_retry(backend, monkeypatch):
    instance, payload = finished(backend, monkeypatch)
    before = instance.store.load()
    commit = instance._commit
    monkeypatch.setattr(instance, "_commit", lambda _value: (_ for _ in ()).throw(OSError("save refused")))
    instance.dispatch("prepare_next_match", payload)
    assert instance.error == "save refused" and instance.native_next_rejected["intent"] == "a" * 32
    assert instance.store.load() == before and not instance.process.writes
    monkeypatch.setattr(instance, "_commit", commit)
    instance.dispatch("prepare_next_match", {**payload, "continuation_intent": "b" * 32})
    assert not instance.error and instance.native_next_rejected is None


def test_postcommit_cleanup_error_and_changed_payload_do_not_reject_accepted_token(backend, monkeypatch):
    instance, payload = finished(backend, monkeypatch)
    monkeypatch.setattr(instance, "_begin_stop", lambda _reason: (_ for _ in ()).throw(OSError("cleanup refused")))
    instance.dispatch("prepare_next_match", payload)
    assert instance._prepared_next and instance.error == "cleanup refused"
    assert instance.native_next_rejected is None
    instance.dispatch("prepare_next_match", payload)
    assert instance.error == "cleanup refused" and instance.native_next_rejected is None
    instance.dispatch("prepare_next_match", {**payload, "lineup_ids": []})
    assert instance.error and instance.native_next_rejected is None
    instance.dispatch("prepare_next_match", {**payload, "expected_next_fixture_id": "changed"})
    assert instance.error and instance.native_next_rejected is None


@pytest.mark.parametrize("action,payload", [("play_match", {}), ("start_lesson", {"id": "speed-flip"}),
    ("lineup", {"ids": []}), ("new_career", {"team_name": "Replacement"})])
def test_prepared_token_blocks_competing_actions_after_cleanup(backend, monkeypatch, action, payload):
    instance, preparation = finished(backend, monkeypatch)
    instance.dispatch("prepare_next_match", preparation)
    cleanup(instance)
    before = instance.store.load()
    instance.dispatch(action, payload)
    assert "next match" in instance.error and instance.store.load() == before
    assert instance.pending_launch is None and instance._prepared_next


@pytest.mark.parametrize("format", [1, 2, 3, 4])
def test_exact_start_uses_existing_launch_path_and_duplicate_cannot_reserve_twice(backend, monkeypatch, format):
    instance, payload = finished(backend, monkeypatch, format)
    instance.dispatch("prepare_next_match", payload)
    cleanup(instance)
    launches = []
    monkeypatch.setattr(bridge.sys, "platform", "win32")
    monkeypatch.setattr("my_career_training.bots.providers.ensure_provider", lambda *_: None)
    monkeypatch.setattr(instance, "_launch", lambda request: launches.append(request))
    instance.dispatch("start_prepared_match", start_payload(payload))
    assert not instance.error and len(launches) == 1
    assert launches[0]["fixture"]["id"] == payload["expected_next_fixture_id"]
    saved = instance.store.load()
    instance.session_state = "Starting Career"
    instance.dispatch("start_prepared_match", start_payload(payload))
    assert not instance.error and len(launches) == 1 and instance.store.load() == saved
    assert instance._prepared_next is None and instance.native_next_ready is None


@pytest.mark.parametrize("change", ["early", "worker", "game_closed", "identity", "mode", "lineup",
                                    "pending_launch", "stop", "lifecycle", "token", "next_fixture"])
def test_start_refuses_drift_before_any_launch_or_save(backend, monkeypatch, change):
    instance, payload = finished(backend, monkeypatch)
    instance.dispatch("prepare_next_match", payload)
    if change != "early":
        cleanup(instance)
    if change == "worker":
        instance.process.current_state = QProcess.Running
    elif change == "game_closed":
        backend[1]["value"] = False
    elif change == "identity":
        instance.owned_game = bridge.ProcessIdentity(5678, 456.0, "C:/SyntheticGame/RocketLeague.exe")
    elif change == "mode":
        instance.in_game = False
    elif change == "lineup":
        instance.document["career"]["lineup"] = instance.document["career"]["squad"][-2:]
    elif change == "pending_launch":
        instance.pending_launch = {"lesson_id": "speed-flip"}
    elif change == "stop":
        instance.stop_reason = "exit"
    elif change == "lifecycle":
        instance.lifecycle.frozen = True
    elif change == "token":
        payload["continuation_intent"] = "b" * 32
    elif change == "next_fixture":
        payload["expected_next_fixture_id"] = "different"
    calls = []
    monkeypatch.setattr(instance, "_prepare_launch", lambda *_: calls.append(True))
    before = instance.store.load()
    instance.dispatch("start_prepared_match", start_payload(payload))
    assert instance.error and not calls and instance.store.load() == before


def test_failed_launch_consumes_token_and_offers_manual_recovery(backend, monkeypatch):
    instance, payload = finished(backend, monkeypatch)
    instance.dispatch("prepare_next_match", payload)
    cleanup(instance)
    calls = []

    def fail(*_):
        calls.append(True)
        raise OSError("provider unavailable")

    monkeypatch.setattr(instance, "_prepare_launch", fail)
    for _ in range(2):
        instance.dispatch("start_prepared_match", start_payload(payload))
        assert "Open Career" in instance.error
    assert len(calls) == 1 and instance._prepared_next is None


@pytest.mark.parametrize("after_cleanup", [False, True])
def test_quit_cancels_continuation_before_shutdown_even_during_cleanup(backend, monkeypatch, after_cleanup):
    instance, payload = finished(backend, monkeypatch)
    instance.dispatch("prepare_next_match", payload)
    if after_cleanup:
        cleanup(instance)
    assert instance.state["session"]["can_exit"]
    shutdown = []
    monkeypatch.setattr(instance, "_begin_stop", lambda reason: shutdown.append(
        (reason, instance._prepared_next, instance.native_next_ready)))
    instance.dispatch("quit_game", {})
    assert shutdown == [("exit", None, None)] and not instance.error
    instance.dispatch("start_prepared_match", start_payload(payload))
    assert "cancelled" in instance.error and instance.document["career"]["pending_session"] is None


def test_restart_discards_unstarted_token_but_retains_progress(backend, monkeypatch):
    instance, payload = finished(backend, monkeypatch)
    instance.dispatch("prepare_next_match", payload)
    cleanup(instance)
    saved = instance.store.load()
    directory = instance.store.directory
    instance.close()
    restarted = bridge.Backend(directory)
    try:
        assert restarted.document == saved
        assert restarted._prepared_next is None and restarted.native_next_ready is None
        restarted.dispatch("start_prepared_match", start_payload(payload))
        assert restarted.error and restarted.document["career"]["pending_session"] is None
    finally:
        restarted.timer.stop()
        restarted.close()


def test_no_next_fixture_disables_preparation_without_creating_season(backend, monkeypatch):
    instance, payload = finished(backend, monkeypatch)
    before = instance.store.load()
    monkeypatch.setattr(career, "next_fixture", lambda _career: None)
    instance.dispatch("prepare_next_match", payload)
    assert instance.error and instance.native_next_rejected
    assert instance.store.load() == before and not instance.process.writes


def test_late_duplicate_result_does_not_award_again_or_replace_continuation(backend, monkeypatch):
    instance, payload = finished(backend, monkeypatch)
    instance.dispatch("prepare_next_match", payload)
    saved = instance.store.load()
    instance._event({"type": "result", "session_id": payload["expected_session_id"],
        "fixture_id": payload["expected_fixture_id"], "home_score": 2, "away_score": 1, "provenance": "game"})
    assert instance.store.load() == saved and instance._prepared_next
    assert instance.session_state == "Stopping Career"
    cleanup(instance)
    assert instance.native_next_ready and instance.store.load() == saved
