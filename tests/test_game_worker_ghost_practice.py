"""Ghost-practice worker and bridge boundary checks; fixtures are synthetic."""
from __future__ import annotations

import json
import math
import os
import uuid

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QProcess
from PySide6.QtWidgets import QApplication
import pytest

from my_career_training import bridge
from my_career_training.game_worker import GameSession
from my_career_training.training import (
    GhostPlayback,
    GhostPractice,
    TrainingEngine,
    configure_lesson,
    practice_context,
    practice_support,
)
from my_career_training.training.recordings import Recorder


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication(["ghost-practice-tests"])


class FakeProcess:
    def __init__(self, state=QProcess.Running):
        self.current_state = state
        self.writes = []

    def state(self):
        return self.current_state

    def write(self, value):
        self.writes.append(bytes(value))
        return len(value)

    def waitForFinished(self, _timeout):
        self.current_state = QProcess.NotRunning
        return True


@pytest.fixture
def backend(tmp_path, monkeypatch, qt_app):
    monkeypatch.setattr(bridge, "detect_installations", lambda: [])
    instance = bridge.Backend(tmp_path)
    instance.timer.stop()
    yield instance
    if instance.process is not None:
        instance.process.current_state = QProcess.NotRunning
        instance.process = None
    instance.close()


def recording():
    lesson = configure_lesson("speed-flip")
    metadata = {"game_version": "test-only-game", "framework_version": "test-only-core",
                "car_hitbox": "octane"}
    recorder = Recorder(lesson, metadata)
    for index in range(121):
        actions = {"throttle": 1.0, "steer": 0.0, "pitch": 0.0, "yaw": 0.0, "roll": 0.0,
                   "jump": index >= 30, "boost": True, "handbrake": False}
        recorder.append({"time": index / 60, "car": {"position": [index * 5, 0, 17],
                         "rotation": [0, 0, 0], "velocity": [300, 0, 0]},
                         "ball": {"position": [0, 0, 93], "velocity": [0, 0, 0]},
                         "actions": actions})
    return recorder.export(outcome="success", duration=2,
                           events=[{"name": "target_crossed", "confidence": "observed"}])


def lesson_session():
    events = []
    metadata = {"game_version": "test-only-game", "framework_version": "test-only-core",
                "car_hitbox": "octane"}
    engine = TrainingEngine("speed-flip", metadata=metadata)
    session = GameSession({"session_id": str(uuid.uuid4()), "lesson_id": "speed-flip"}, events.append)
    session.engine = engine
    session.coaching_preferences = {"mode": "watch", "lead_seconds": 0.75,
                                    "playback_speed": 1.0, "loop": False}
    session.practice_support = practice_support("speed-flip")
    session.practice = GhostPractice(context=practice_context(engine.lesson, metadata))
    session.practice.load(recording(), kind="personal")
    session.coach = GhostPlayback()
    session.last_frame = {"car": {"position": [0, -2500, 17], "rotation": [0, 0, 0]}}
    return session, events


def test_worker_toggle_synchronizes_logical_actions_and_off_clears_snapshot():
    session, _ = lesson_session()
    session.handle_command({"type": "ghost_control", "operation": "toggle", "enabled": True})

    visible = session.practice_snapshot
    assert visible["enabled"] is True and visible["visible"] is True
    assert visible["player_input_applied"] is False
    assert visible["coach_actions"] == visible["controller"]["actions"]
    assert visible["coach_actions"] == session.practice.recording["samples"][0]["actions"]
    assert visible["controller"]["source"] == "ghost"
    assert session.engine.preferences["ghost"] is True

    session.handle_command({"type": "ghost_control", "operation": "toggle", "enabled": False})
    off = session.practice_snapshot
    assert off["enabled"] is False and off["visible"] is False
    assert off["pose"] is None and off["lines"] == [] and off["coach_actions"] is None
    assert off["controller"]["observed"] is False and off["controller"]["actions"] is None
    assert session.engine.preferences["ghost"] is False


def test_worker_acknowledges_only_after_toggle_and_recording_state_is_applied():
    session, events = lesson_session()
    session.last_frame["time"] = 10.0
    toggle_id = str(uuid.uuid4())

    session.handle_command({"id": toggle_id, "type": "ghost_control", "operation": "toggle",
                            "enabled": True})

    toggle_ack = events[-1]
    assert toggle_ack == {"type": "ghost_ack", "session_id": session.session_id,
                          "id": toggle_id, "accepted": True, "enabled": True}
    assert session.practice_snapshot["enabled"] is True

    load_id = str(uuid.uuid4())
    session.handle_command({"id": load_id, "type": "play_recording", "recording": recording(),
                            "mode": "watch", "lead_seconds": 0.75})

    load_ack = events[-1]
    assert load_ack["type"] == "ghost_ack" and load_ack["session_id"] == session.session_id
    assert load_ack["id"] == load_id and load_ack["accepted"] is True
    assert load_ack["available"] is True
    assert session.practice_snapshot["available"] is True
    assert session.practice_snapshot["enabled"] is False
    assert session.engine.preferences["ghost"] is False


def test_career_worker_refuses_ghost_toggle_and_recording_load():
    session = GameSession({"session_id": str(uuid.uuid4()), "fixture": {"id": "fixture-a"}}, lambda _event: None)
    # Setup creates the legacy coach for either activity; practice remains lesson-only.
    session.coach = GhostPlayback()
    with pytest.raises(ValueError, match="only during a training lesson"):
        session.handle_command({"type": "ghost_control", "operation": "toggle", "enabled": True})
    with pytest.raises(ValueError, match="only during a training lesson"):
        session.handle_command({"type": "play_recording", "recording": recording()})


def test_worker_can_turn_off_after_lesson_support_is_lost():
    session, events = lesson_session()
    session.handle_command({"type": "ghost_control", "operation": "toggle", "enabled": True})
    session.practice_support = {"supported": False, "reason": "Lesson support was lost."}

    session.handle_command({"id": "off-after-support-loss", "type": "ghost_control",
                            "operation": "toggle", "enabled": False})

    assert session.practice_snapshot["enabled"] is False
    assert session.practice_snapshot["visible"] is False
    assert session.engine.preferences["ghost"] is False
    assert events[-1]["accepted"] is True and events[-1]["enabled"] is False


def test_retry_restarts_at_the_new_reset_pose(monkeypatch):
    session, _ = lesson_session()
    session.handle_command({"type": "ghost_control", "operation": "toggle", "enabled": True})
    original_anchor = dict(session.practice._anchor)

    class ResetEngine:
        preferences = {"ghost": True}

        @staticmethod
        def reset():
            return {"car": {"position": [100, 200, 17], "rotation": [0, math.pi / 2, 0]}}

    messages = []
    session.engine = ResetEngine()
    session.manager = type("Manager", (), {"rlbot_interface": type("Relay", (), {
        "send_msg": staticmethod(messages.append)})()})()
    session.human_index = 0
    monkeypatch.setattr("my_career_training.adapter.desired_state", lambda state, index: (state, index))

    session.reset()

    assert messages and session.practice._anchor != original_anchor
    assert session.practice._anchor == {"position": [100.0, 200.0, 17.0],
                                       "rotation": [0.0, math.pi / 2, 0.0]}
    assert session.practice_snapshot["cursor"] == 0.0


def test_actual_backend_dispatch_toggle_validates_and_persists_matching_preferences(backend):
    backend.request = {"lesson_id": "speed-flip"}
    backend.process = FakeProcess()
    backend.telemetry = {"ghost_practice": {"available": True},
                         "ghost_practice_support": {"supported": True}}

    backend.dispatch("ghost_control", {"operation": "toggle", "enabled": True})

    assert backend.error == ""
    sent = json.loads(backend.process.writes[-1])
    assert sent["type"] == "ghost_control" and sent["operation"] == "toggle" and sent["enabled"] is True
    assert backend.document["lesson_preferences"]["speed-flip"]["ghost"] is True
    assert backend.document["settings"]["training_display"]["ghost"] is True
    assert backend._ghost_practice_enabled is True

    before = len(backend.process.writes)
    backend.dispatch("ghost_control", {"operation": "toggle", "enabled": True})
    assert backend.error == "" and len(backend.process.writes) == before
    backend.dispatch("ghost_control", {"operation": "toggle", "enabled": "yes"})
    assert "must be on or off" in backend.error
    backend.dispatch("ghost_control", {"operation": "toggle", "enabled": False, "value": 1})
    assert "without extra fields" in backend.error
    assert len(backend.process.writes) == before


def test_actual_backend_dispatch_refuses_career_toggle_and_recording_load(backend):
    backend.request = {"fixture": {"id": "fixture-a"}}
    backend.process = FakeProcess()
    backend.telemetry = {"ghost_practice": {"available": True},
                         "ghost_practice_support": {"supported": True}}

    backend.dispatch("ghost_control", {"operation": "toggle", "enabled": True})
    assert "only during a training lesson" in backend.error
    backend.dispatch("play_recording", {"id": "speed-flip"})
    assert "Start this lesson" in backend.error
    assert backend.process.writes == []


@pytest.mark.parametrize("action,payload", [("stop_ghost", {}),
                                            ("ghost_control", {"operation": "stop"})])
def test_stop_ghost_clears_bridge_telemetry_immediately(backend, action, payload):
    backend.request = {"lesson_id": "speed-flip"}
    backend.process = FakeProcess()
    backend._ghost_practice_enabled = True
    backend.telemetry = {"ghost_practice": {"available": True, "enabled": True, "playing": True,
                         "visible": True, "pose": {"position": [1, 2, 3]}, "lines": [{"line": 1}],
                         "coach_actions": {"boost": True}, "controller": {"observed": True,
                         "actions": {"boost": True}}}}

    backend.dispatch(action, payload)

    practice = backend.telemetry["ghost_practice"]
    assert practice["visible"] is False and practice["pose"] is None
    assert practice["lines"] == [] and practice["coach_actions"] is None
    assert practice["controller"]["observed"] is False and practice["controller"]["actions"] is None
    assert backend._ghost_practice_enabled is False


def test_worker_off_telemetry_after_recording_load_clears_bridge_intent(backend):
    backend.session_id = str(uuid.uuid4())
    backend.request = {"lesson_id": "speed-flip"}
    backend._ghost_practice_enabled = True
    backend.telemetry = {"ghost_practice": {"available": True, "enabled": True, "visible": True}}

    backend._event({"type": "telemetry", "session_id": backend.session_id,
        "ghost_practice": {"available": True, "enabled": False, "playing": False,
                            "visible": False, "status": "off", "pose": None, "lines": [],
                            "coach_actions": None},
        "ghost_practice_support": {"supported": True, "reason": ""}})

    assert backend._ghost_practice_enabled is False


def _begin_bridge_ghost_toggle(backend, enabled=True):
    backend.session_id = str(uuid.uuid4())
    backend.request = {"lesson_id": "speed-flip", "variants": {}}
    backend.process = FakeProcess()
    backend.telemetry = {"ghost_practice": {"available": True, "enabled": False, "visible": False},
                         "ghost_practice_support": {"supported": True, "reason": ""}}
    backend.dispatch("ghost_control", {"operation": "toggle", "enabled": enabled})
    assert backend.error == ""
    return backend.session_id, json.loads(backend.process.writes[-1])["id"]


def test_worker_rejection_acknowledgement_reverts_optimistic_on(backend):
    session_id, command_id = _begin_bridge_ghost_toggle(backend)
    assert backend._ghost_practice_enabled is True
    assert backend.state["telemetry"]["ghost_practice_pending"] is True

    backend._event({"type": "ghost_ack", "session_id": session_id, "id": command_id,
                    "accepted": False, "error": "Recording is no longer available."})

    assert backend._ghost_pending == {}
    assert backend._ghost_practice_enabled is False
    assert backend.telemetry["ghost_practice"]["visible"] is False
    assert backend.telemetry["ghost_practice"]["pose"] is None
    assert "no longer available" in backend.error
    assert backend.state["telemetry"]["ghost_practice_pending"] is False


def test_late_on_ack_cannot_override_a_newer_off_command(backend):
    session_id, on_id = _begin_bridge_ghost_toggle(backend, True)
    backend.dispatch("ghost_control", {"operation": "toggle", "enabled": False})
    off_id = json.loads(backend.process.writes[-1])["id"]

    backend._event({"type": "ghost_ack", "session_id": session_id, "id": off_id,
                    "accepted": True, "enabled": False})
    assert backend._ghost_practice_enabled is False
    backend._event({"type": "ghost_ack", "session_id": session_id, "id": on_id,
                    "accepted": True, "enabled": True})

    assert backend._ghost_practice_enabled is False
    assert backend.document["lesson_preferences"]["speed-flip"]["ghost"] is False
    assert backend.telemetry["ghost_practice"]["visible"] is False


def test_backend_can_turn_off_after_lesson_support_is_lost(backend):
    _session_id, _on_id = _begin_bridge_ghost_toggle(backend, True)
    backend.telemetry["ghost_practice_support"]["supported"] = False
    backend.telemetry["ghost_practice"]["available"] = False

    backend.dispatch("ghost_control", {"operation": "toggle", "enabled": False})

    assert backend.error == ""
    command = json.loads(backend.process.writes[-1])
    assert command["type"] == "ghost_control" and command["enabled"] is False
    assert backend._ghost_practice_enabled is False


def test_wrong_session_ack_does_not_consume_current_pending_command(backend):
    session_id, command_id = _begin_bridge_ghost_toggle(backend)

    backend._ghost_ack({"id": command_id, "session_id": str(uuid.uuid4()),
                        "accepted": True, "enabled": True})

    assert backend.session_id == session_id
    assert command_id in backend._ghost_pending
    assert backend._ghost_practice_enabled is True


def test_loading_a_recording_turns_off_an_already_enabled_ghost(backend):
    recording_value = recording()
    recording_id = str(uuid.uuid4())
    filename = f"{recording_id}.json"
    directory = backend.store.directory / "recordings"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / filename).write_text(json.dumps(recording_value), encoding="utf-8")
    backend.document["recordings"].append({"id": recording_id, "lesson_id": "speed-flip",
        "filename": filename, "label": "Your attempt", "outcome": "success",
        "variant": recording_value["variant"], "source": {"kind": "local_player"}})
    backend._commit(backend.document)
    session_id, _on_id = _begin_bridge_ghost_toggle(backend)
    backend.telemetry["ghost_practice"].update(enabled=True, visible=True,
        pose={"position": [1, 2, 3]}, lines=[{"start": [0, 0, 0], "end": [1, 1, 1]}],
        coach_actions={"boost": True})

    backend.dispatch("play_recording", {"id": "speed-flip", "recording_id": recording_id})

    assert backend.error == ""
    command = json.loads(backend.process.writes[-1])
    assert command["type"] == "play_recording"
    assert command["recording"]["lesson_id"] == "speed-flip"
    assert backend._ghost_practice_enabled is False
    assert backend.document["lesson_preferences"]["speed-flip"]["ghost"] is False
    assert backend.telemetry["ghost_practice"]["visible"] is False
    assert backend.telemetry["ghost_practice"]["pose"] is None
    assert backend._ghost_pending[command["id"]]["kind"] == "play_recording"

    backend._event({"type": "ghost_ack", "session_id": session_id, "id": command["id"],
                    "accepted": True, "available": True})
    assert backend._ghost_practice_enabled is False
    assert backend.telemetry["ghost_practice"]["visible"] is False
