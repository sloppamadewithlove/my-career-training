"""Forfeit transaction tests; scores are synthetic fixtures, never gameplay evidence."""
from __future__ import annotations

import copy
import json
import uuid

import pytest
from PySide6.QtCore import QProcess

from my_career_training import bridge, career
from test_bridge import FakeProcess, backend, qt_app  # noqa: F401


def running(instance, scores=(0, 0)):
    session = str(uuid.uuid4())
    state = copy.deepcopy(instance.document)
    state["career"] = career.start_fixture(career.new_career("Forfeit tests", format=1, seed=41), session)
    instance._commit(state)
    fixture = career.next_fixture(state["career"])
    instance.in_game = True
    instance.session_id = session
    instance.request = {"fixture": copy.deepcopy(fixture), "session_id": session}
    instance.process = FakeProcess()
    instance.session_state = "Playing"
    instance._event({"type": "telemetry", "session_id": session,
                     "scores": list(scores), "phase": "MatchPhase.Active"})
    return {"expected_session_id": session, "expected_fixture_id": fixture["id"],
            "confirm": True, "return_intent": "a" * 32}


def natural(payload, **changes):
    return {"type": "result", "session_id": payload["expected_session_id"],
            "fixture_id": payload["expected_fixture_id"], "home_score": 2,
            "away_score": 1, "provenance": "game", **changes}


def receipt(instance, event):
    path = instance.store.directory / "outbox" / f"{event['session_id']}.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(event), encoding="utf-8")
    return path


@pytest.mark.parametrize("scores", [(0, 0), (8, 1), (1, 8)])
def test_forfeit_saves_observed_score_before_shutdown_and_ack_waits_for_cleanup(backend, scores):
    instance, _, _ = backend
    payload = running(instance, scores)
    process = instance.process
    instance.dispatch("forfeit_match", payload)
    assert not instance.error
    saved = instance.store.load()["career"]
    assert saved["pending_session"] is None
    result = instance.latest_result
    assert (result["home_score"], result["away_score"]) == scores
    assert result["outcome"] == "forfeited" and result["winner"] != "human"
    assert result["forfeited_by"] == "human" and result["provenance"] == "forfeit"
    assert instance.native_return_ready is None and instance.native_forfeit_rejected is None
    assert len(process.writes) == 1 and json.loads(process.writes[0])["type"] == "shutdown"
    instance._event({"type": "stopped", "session_id": instance.session_id})
    instance._tick()
    assert instance.native_return_ready is None
    process.current_state = QProcess.NotRunning
    instance._tick()
    assert instance.native_return_ready == {"session_id": payload["expected_session_id"],
                                           "fixture_id": payload["expected_fixture_id"]}
    assert instance.session_id is None and instance.state["session"]["kind"] == "hub"


def test_forfeit_duplicate_does_not_advance_or_stop_twice(backend):
    instance, _, _ = backend
    payload = running(instance, (7, 1))
    instance.dispatch("forfeit_match", payload)
    saved = instance.store.load()
    instance.dispatch("forfeit_match", payload)
    assert not instance.error and instance.native_forfeit_rejected is None
    assert instance.store.load() == saved and len(instance.process.writes) == 1


def test_ordinary_unfinished_return_survives_late_telemetry_after_stop_ack(backend):
    instance, _, _ = backend
    payload = running(instance, (3, 1))
    instance.dispatch("return_hub", {"expected_session_id": payload["expected_session_id"],
        "expected_fixture_id": payload["expected_fixture_id"], "abandon": True})
    instance._event({"type": "stopped", "session_id": instance.session_id})
    assert instance.session_state == "Waiting for Worker"
    instance._event({"type": "telemetry", "session_id": instance.session_id,
                     "scores": [3, 1], "phase": "MatchPhase.Active"})
    assert instance.session_state == "Waiting for Worker"
    instance.process.current_state = QProcess.NotRunning
    instance._tick()
    assert instance.session_state == "Idle" and instance.native_return_ready is not None
    fixture = career.next_fixture(instance.store.load()["career"])
    assert fixture["id"] == payload["expected_fixture_id"]
    assert fixture["result"] is None and fixture["status"] == "scheduled"


@pytest.mark.parametrize("change", ["fixture", "session", "lesson", "calibration", "workshop", "score", "ended"])
def test_forfeit_rejection_keeps_pending_and_reports_exact_intent(backend, change):
    instance, _, _ = backend
    payload = running(instance)
    if change in {"fixture", "session"}:
        payload[f"expected_{change}_id"] = "other"
    elif change in {"lesson", "calibration", "workshop"}:
        instance.request[{"lesson": "lesson_id"}.get(change, change)] = True
    elif change == "score":
        instance._event({"type": "telemetry", "session_id": instance.session_id,
                         "scores": [True, 0], "phase": "MatchPhase.Active"})
    else:
        instance._event({"type": "telemetry", "session_id": instance.session_id,
                         "scores": [2, 1], "phase": "MatchPhase.Ended"})
    before = instance.store.load()
    instance.dispatch("forfeit_match", payload)
    assert instance.error
    assert instance.native_forfeit_rejected == {"session_id": payload["expected_session_id"],
        "fixture_id": payload["expected_fixture_id"], "intent": payload["return_intent"]}
    assert instance.store.load() == before
    assert not instance.process.writes and instance.native_return_ready is None


def test_save_failure_keeps_playing_pending_and_allows_new_intent_retry(backend, monkeypatch):
    instance, _, _ = backend
    payload = running(instance, (4, 1))
    before = instance.store.load()
    commit = instance._commit
    monkeypatch.setattr(instance, "_commit", lambda _state: (_ for _ in ()).throw(OSError("test save failure")))
    instance.dispatch("forfeit_match", payload)
    assert instance.error == "test save failure"
    assert instance.store.load() == before and instance.document == before
    assert instance.session_state == "Playing" and instance.stop_reason is None
    assert not instance.process.writes and instance.native_return_ready is None
    assert instance.native_forfeit_rejected["intent"] == "a" * 32
    monkeypatch.setattr(instance, "_commit", commit)
    instance.dispatch("forfeit_match", {**payload, "return_intent": "b" * 32})
    assert not instance.error and instance.native_forfeit_rejected is None
    assert instance.latest_result["outcome"] == "forfeited"


def test_already_completed_receipt_wins_before_forfeit(backend):
    instance, _, _ = backend
    payload = running(instance, (2, 0))
    path = receipt(instance, natural(payload))
    instance.dispatch("forfeit_match", payload)
    assert "already finished" in instance.error
    assert instance.latest_result["provenance"] == "game"
    assert (instance.latest_result["home_score"], instance.latest_result["away_score"]) == (2, 1)
    assert instance.native_forfeit_rejected["intent"] == payload["return_intent"]
    assert not instance.process.writes and not path.exists()


def test_queued_natural_result_is_drained_before_forfeit_decision(backend, monkeypatch):
    instance, _, _ = backend
    payload = running(instance, (4, 0))
    monkeypatch.setattr(instance, "_read_worker", lambda: instance._event(natural(payload)))
    instance.dispatch("forfeit_match", payload)
    assert "already finished" in instance.error
    assert instance.latest_result["provenance"] == "game"
    assert not instance.process.writes and instance.native_return_ready is None


@pytest.mark.parametrize("replacement", [{"confirm": False}, {"confirm": 1}, {"home_score": 999},
                                         {"return_intent": "not-a-token"}])
def test_forfeit_rejects_unconfirmed_or_caller_score_payload(backend, replacement):
    instance, _, _ = backend
    payload = running(instance)
    before = instance.store.load()
    instance.dispatch("forfeit_match", {**payload, **replacement})
    assert instance.error and not instance.process.writes
    assert instance.store.load() == before and instance.native_return_ready is None


def test_stale_forfeit_cannot_change_new_attempt(backend):
    instance, _, _ = backend
    previous = running(instance)
    current = running(instance, (3, 0))
    before = instance.store.load()
    instance.dispatch("forfeit_match", previous)
    assert instance.error and instance.store.load() == before
    assert instance.session_id == current["expected_session_id"]
    assert not instance.process.writes


def test_late_exact_receipt_is_acknowledged_without_replacing_forfeit_or_blocking_cleanup(backend):
    instance, _, _ = backend
    payload = running(instance, (0, 0))
    instance.dispatch("forfeit_match", payload)
    saved = instance.store.load()
    instance._event({"type": "stopped", "session_id": instance.session_id})
    path = receipt(instance, natural(payload))
    instance._event(natural(payload))
    instance._event({"type": "session", "session_id": instance.session_id, "state": "completed"})
    assert instance.session_state == "Waiting for Worker"
    assert instance.store.load() == saved and not path.exists()
    instance.process.current_state = QProcess.NotRunning
    instance._tick()
    assert instance.native_return_ready is not None


def test_forfeit_restart_consumes_only_exact_late_receipt(backend):
    instance, _, _ = backend
    payload = running(instance)
    instance.dispatch("forfeit_match", payload)
    saved = instance.store.load()
    exact = receipt(instance, natural(payload))
    foreign_event = natural(payload, session_id=str(uuid.uuid4()))
    foreign = receipt(instance, foreign_event)
    instance.process = None
    instance.timer.stop()
    instance.close()
    restarted = bridge.Backend(instance.store.directory)
    try:
        assert restarted.store.load() == saved
        assert restarted.latest_result["outcome"] == "forfeited"
        assert not exact.exists() and foreign.exists()
        assert restarted.error and restarted.native_return_ready is None
    finally:
        restarted.timer.stop()
        restarted.close()


@pytest.mark.parametrize("changes", [{"fixture_id": "other"}, {"provenance": "manual"},
                                      {"calibration": True}, {"home_score": True}, {"away_score": 2}])
def test_late_foreign_or_invalid_result_cannot_replace_forfeit(backend, changes):
    instance, _, _ = backend
    payload = running(instance)
    instance.dispatch("forfeit_match", payload)
    saved = instance.store.load()
    with pytest.raises((ValueError, KeyError)):
        instance._commit_result(natural(payload, **changes))
    assert instance.store.load() == saved


def test_postcommit_cleanup_failure_never_rejects_durable_forfeit(backend, monkeypatch):
    instance, _, _ = backend
    payload = running(instance)
    monkeypatch.setattr(instance, "_begin_stop", lambda _reason: (_ for _ in ()).throw(OSError("cleanup failure")))
    instance.dispatch("forfeit_match", payload)
    assert instance.error == "cleanup failure"
    assert instance.latest_result["outcome"] == "forfeited"
    assert instance.store.load()["career"]["pending_session"] is None
    assert instance.native_forfeit_rejected is None and instance.native_return_ready is None


def test_result_arriving_at_commit_boundary_cannot_overwrite_forfeit(backend, monkeypatch):
    instance, _, _ = backend
    payload = running(instance, (5, 0))
    commit = instance._commit
    def race(state):
        receipt(instance, natural(payload))
        commit(state)
    monkeypatch.setattr(instance, "_commit", race)
    instance.dispatch("forfeit_match", payload)
    instance._recover_outbox()
    assert not instance.error
    assert instance.latest_result["outcome"] == "forfeited"
    assert instance.latest_result["home_score"] == 5
    assert not list((instance.store.directory / "outbox").glob("*.json"))
