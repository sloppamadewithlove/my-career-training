"""Ghost-practice worker and bridge boundary checks; fixtures are synthetic."""
from __future__ import annotations

import json
import math
import os
import sys
import subprocess
import uuid
from contextlib import nullcontext
from types import SimpleNamespace

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


def recording(lesson_id="speed-flip"):
    lesson = configure_lesson(lesson_id)
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


def lesson_session(lesson_id="speed-flip"):
    events = []
    metadata = {"game_version": "test-only-game", "framework_version": "test-only-core",
                "car_hitbox": "octane"}
    engine = TrainingEngine(lesson_id, metadata=metadata)
    session = GameSession({"session_id": str(uuid.uuid4()), "lesson_id": lesson_id}, events.append)
    session.engine = engine
    session.coaching_preferences = {"mode": "watch", "lead_seconds": 0.75,
                                    "playback_speed": 1.0, "loop": False}
    session.practice_support = practice_support(lesson_id)
    session.practice = GhostPractice(context=practice_context(engine.lesson, metadata))
    session.practice.load(recording(lesson_id), kind="personal")
    session.coach = GhostPlayback()
    session.last_frame = {"car": {"position": [0, -2500, 17], "rotation": [0, 0, 0]}}
    return session, events


def test_worker_flip_reset_recording_load_toggle_and_retry_keep_paired_world_trace():
    session, events = lesson_session("flip-reset")
    session.last_frame["time"] = 10.0
    value = recording("flip-reset")
    session.handle_command({"id": "load-flip", "type": "play_recording", "recording": value,
                            "practice": True, "mode": "watch"})
    assert events[-1]["accepted"] is True and session.practice_snapshot["enabled"] is False
    session.handle_command({"id": "on-flip", "type": "ghost_control", "operation": "toggle", "enabled": True})
    assert events[-1]["accepted"] is True
    session.practice.update(10)
    state = session.practice.update(10.5)
    assert state["pose"]["position"] == value["samples"][30]["position"]
    assert state["pose"]["ball_position"] == value["samples"][30]["ball_position"]
    assert state["pose"]["actions"] == state["coach_actions"] == value["samples"][30]["actions"]
    assert state["provenance"]["independently_validated"] is False
    session.handle_command({"type": "ghost_control", "operation": "toggle", "enabled": False})
    assert session.practice_snapshot["pose"] is None
    assert session.practice_snapshot["coach_actions"] is None


@pytest.mark.skipif(not os.environ.get("MCT_NATIVE_GHOST_RECORDING_TEST"),
                    reason="Native parser test executable is optional outside Windows native checks")
def test_actual_worker_and_backend_payload_reaches_native_recording_parser(backend, tmp_path):
    session, _events = lesson_session("flip-reset")
    session.last_frame["time"] = 10.0
    session.handle_command({"type": "play_recording", "recording": recording("flip-reset"),
                            "practice": True, "mode": "watch"})
    session.handle_command({"type": "ghost_control", "operation": "toggle", "enabled": True})
    session.practice.update(10)
    snapshot = session.practice.update(10.5)
    backend.session_id = session.session_id
    backend.session_state = "training"
    backend.request = {"lesson_id": "flip-reset", "variants": {}}
    backend.process = FakeProcess()
    backend._ghost_practice_enabled = True
    backend._event({"type": "telemetry", "session_id": session.session_id,
                    "ghost_practice": snapshot, "ghost_practice_support": session.practice_support})
    payload = tmp_path / "synthetic-worker-bridge.json"
    payload.write_text(json.dumps(backend.state), encoding="utf-8")
    result = subprocess.run([os.environ["MCT_NATIVE_GHOST_RECORDING_TEST"], str(payload)],
                            capture_output=True, text=True, check=True)
    native = json.loads(result.stdout)
    assert native["time"] == snapshot["pose"]["time"]
    assert native["position"] == pytest.approx(snapshot["pose"]["position"])
    assert native["ball_position"] == pytest.approx(snapshot["pose"]["ball_position"])
    w, x, y, z = snapshot["pose"]["quaternion"]
    assert native["orientation"] == pytest.approx([x, y, z, w])
    assert native["jump"] == snapshot["coach_actions"]["jump"]
    assert native["boost"] == snapshot["coach_actions"]["boost"]


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


class FakeRenderer:
    can_render = True
    yellow = "yellow"
    cyan = "cyan"

    def __init__(self):
        self.text = []
        self.lines = []

    def context(self, _name):
        return nullcontext()

    def draw_string_2d(self, value, *_args):
        self.text.append(value)

    def draw_line_3d(self, start, end, color):
        self.lines.append((start, end, color))


def _render_with_fake_renderer(monkeypatch, session):
    monkeypatch.setitem(sys.modules, "rlbot", SimpleNamespace(
        flat=SimpleNamespace(Vector3=lambda *values: tuple(values))))
    renderer = FakeRenderer()
    session.renderer = renderer
    session.engine.preferences.update({"explanations": False, "actions": False,
                                       "timing": False, "ghost": True})
    session.render({})
    return renderer


def test_explicit_practice_off_never_falls_back_to_legacy_ghost(monkeypatch):
    session, _ = lesson_session()
    session.last_frame["time"] = 10.0
    session.handle_command({"type": "play_recording", "recording": recording(), "mode": "watch"})
    session.handle_command({"type": "ghost_control", "operation": "toggle", "enabled": True})
    session.handle_command({"type": "ghost_control", "operation": "toggle", "enabled": False})
    # Simulate a stale legacy snapshot and a persisted old preference. Explicit
    # practice Off must not reveal the independently maintained coach timeline.
    session.coach_snapshot = {"visible": True, "lines": [], "label": "Legacy fallback ghost"}

    renderer = _render_with_fake_renderer(monkeypatch, session)

    assert session.practice is not None and session.practice_snapshot["visible"] is False
    assert "Legacy fallback ghost" not in renderer.text
    assert renderer.lines == []


def test_legacy_recording_command_still_renders_the_coach_ghost(monkeypatch):
    session, _ = lesson_session()
    session.practice = GhostPractice(
        context=practice_context(session.engine.lesson, session.engine.metadata))
    session.practice_snapshot = session.practice.snapshot()
    session.last_frame["time"] = 10.0

    session.handle_command({"type": "play_recording", "recording": recording(),
                            "practice": False, "mode": "watch", "lead_seconds": 0.75})
    session.coach_snapshot = session.coach.update(10.0)

    renderer = _render_with_fake_renderer(monkeypatch, session)

    assert session.practice is not None and session.practice.available is False
    assert session.coach_snapshot["visible"] is True
    assert any("Your recorded attempt" in item for item in renderer.text)


def test_legacy_load_after_practice_on_renders_only_the_legacy_ghost(monkeypatch):
    session, _ = lesson_session()
    session.last_frame["time"] = 10.0
    session.handle_command({"type": "play_recording", "recording": recording(),
                            "practice": True, "mode": "watch"})
    session.handle_command({"type": "ghost_control", "operation": "toggle", "enabled": True})
    assert session.practice_snapshot["visible"] is True

    session.handle_command({"type": "play_recording", "recording": recording(),
                            "practice": False, "mode": "watch", "lead_seconds": 0.75})
    session.coach_snapshot = session.coach.update(10.0)
    renderer = _render_with_fake_renderer(monkeypatch, session)

    assert session.practice_snapshot["enabled"] is False
    assert session.practice_snapshot["visible"] is False
    assert session.coach_snapshot["visible"] is True
    assert "Your recorded attempt" in renderer.text
    assert not any(item.startswith("GHOST ") for item in renderer.text)


@pytest.mark.parametrize("practice_mode", [None, "false", 0])
def test_worker_rejects_non_boolean_recording_mode_before_loading(practice_mode):
    session, _ = lesson_session()
    session.last_frame["time"] = 10.0
    before_recording = session.recording
    before_coach = session.coach.recording
    before_practice = session.practice.recording
    before_snapshot = json.loads(json.dumps(session.practice_snapshot))

    with pytest.raises(ValueError, match="practice"):
        session.handle_command({"id": str(uuid.uuid4()), "type": "play_recording",
                                "recording": recording(), "practice": practice_mode,
                                "mode": "watch", "lead_seconds": 0.75})

    assert session.recording is before_recording
    assert session.coach.recording is before_coach
    assert session.practice.recording is before_practice
    assert session.practice_snapshot == before_snapshot


@pytest.mark.parametrize("practice_mode", [True, False])
def test_rejected_incompatible_recording_load_leaves_all_prior_state_unchanged(practice_mode):
    session, events = lesson_session()
    session.last_frame["time"] = 10.0
    session.handle_command({"id": str(uuid.uuid4()), "type": "play_recording",
                            "recording": recording(), "practice": True,
                            "mode": "watch", "lead_seconds": 0.75})
    session.handle_command({"type": "ghost_control", "operation": "toggle", "enabled": True})
    before = {
        "recording": json.loads(json.dumps(session.recording)),
        "coach_recording": json.loads(json.dumps(session.coach.recording)),
        "coach_snapshot": json.loads(json.dumps(session.coach_snapshot)),
        "coach_state": json.loads(json.dumps(session.coach.snapshot())),
        "practice_recording": json.loads(json.dumps(session.practice.recording)),
        "practice_snapshot": json.loads(json.dumps(session.practice_snapshot)),
        "practice_context": json.loads(json.dumps(session.practice.context)),
        "playback_origin": session.playback_origin,
        "ghost_preference": session.engine.preferences["ghost"],
        "event_count": len(events),
    }
    incompatible = recording()
    incompatible["metadata"]["starting_state"]["car"]["position"][0] = 900

    with pytest.raises(ValueError, match="starting_state"):
        session.handle_command({"id": str(uuid.uuid4()), "type": "play_recording",
                                "recording": incompatible, "practice": practice_mode,
                                "mode": "watch", "lead_seconds": 0.75})

    assert session.recording == before["recording"]
    assert session.coach.recording == before["coach_recording"]
    assert session.coach_snapshot == before["coach_snapshot"]
    assert session.coach.snapshot() == before["coach_state"]
    assert session.practice.recording == before["practice_recording"]
    assert session.practice_snapshot == before["practice_snapshot"]
    assert session.practice.context == before["practice_context"]
    assert session.playback_origin == before["playback_origin"]
    assert session.engine.preferences["ghost"] is before["ghost_preference"]
    assert len(events) == before["event_count"]


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
    assert command["practice"] is True
    assert backend._ghost_practice_enabled is False
    assert backend.document["lesson_preferences"]["speed-flip"]["ghost"] is False
    assert backend.telemetry["ghost_practice"]["visible"] is False
    assert backend.telemetry["ghost_practice"]["pose"] is None
    assert backend._ghost_pending[command["id"]]["kind"] == "play_recording"

    backend._event({"type": "ghost_ack", "session_id": session_id, "id": command["id"],
                    "accepted": True, "available": True})
    assert backend._ghost_practice_enabled is False
    assert backend.telemetry["ghost_practice"]["visible"] is False


@pytest.mark.parametrize("failure", ["failed", "truncated", "missing_ball"])
def test_backend_native_rows_share_worker_flip_reset_eligibility_and_cache_legacy_files(
        backend, monkeypatch, failure):
    value = recording("flip-reset")
    backend._store_recording(value)
    usable_id = backend.document["recordings"][-1]["id"]
    bad = json.loads(json.dumps(value))
    if failure == "failed":
        bad["outcome"] = "failed"
    elif failure == "truncated":
        bad["truncated"] = True
    else:
        del bad["samples"][-1]["ball_position"]
    backend._store_recording(bad)
    invalid_id = backend.document["recordings"][-1]["id"]
    saved = json.loads(json.dumps(backend.document))
    backend.request = {"lesson_id": "flip-reset", "variants": {}}
    rows = backend.state["recordings"]
    assert rows[-2]["id"] == usable_id and rows[-2]["practice_eligible"] is True
    assert rows[-1]["id"] == invalid_id and rows[-1]["practice_eligible"] is False
    assert backend.document == saved  # Legacy saved indexes are never rewritten.
    with pytest.raises(ValueError, match="successful complete"):
        GhostPractice(bad, context=practice_context(configure_lesson("flip-reset"), {
            "game_version": "test-only-game", "framework_version": "test-only-core", "car_hitbox": "octane"}))
    monkeypatch.setattr(bridge, "import_recording", lambda *_args: pytest.fail("View refresh reread capture bytes"))
    assert backend.state["recordings"] == rows


@pytest.mark.parametrize("failure", ["missing", "invalid", "path"])
def test_backend_native_rows_hide_unreadable_legacy_recordings(backend, monkeypatch, failure):
    backend._store_recording(recording("flip-reset"))
    entry = backend.document["recordings"][-1]
    path = backend.store.directory / "recordings" / entry["filename"]
    if failure == "missing":
        path.unlink()
    elif failure == "invalid":
        path.write_text("not a recording", encoding="utf-8")
    else:
        entry["filename"] = "../private-capture.json"
    backend.request = {"lesson_id": "flip-reset", "variants": {}}
    assert backend.state["recordings"][-1]["practice_eligible"] is False
    monkeypatch.setattr(bridge, "import_recording", lambda *_args: pytest.fail("Invalid capture was reread"))
    assert backend.state["recordings"][-1]["practice_eligible"] is False


@pytest.mark.parametrize("malformed", [None, True, 12, "invalid", []])
def test_backend_native_rows_skip_malformed_index_values_without_changing_save(backend, malformed):
    backend._store_recording(recording("flip-reset"))
    valid = backend.document["recordings"][0]
    backend.document["recordings"] = [malformed, valid]
    saved = json.loads(json.dumps(backend.document))
    backend.request = {"lesson_id": "flip-reset", "variants": {}}
    rows = backend.state["recordings"]
    assert len(rows) == 1 and rows[0]["id"] == valid["id"] and rows[0]["practice_eligible"] is True
    assert backend.document == saved


def test_backend_native_rows_retry_transient_read_failure_for_unchanged_file(backend, monkeypatch):
    backend._store_recording(recording("flip-reset"))
    backend.request = {"lesson_id": "flip-reset", "variants": {}}
    original_import = bridge.import_recording
    calls = []

    def temporarily_locked(path):
        calls.append(path.stat())
        if len(calls) == 1:
            raise PermissionError("Synthetic transient recording lock")
        return original_import(path)

    monkeypatch.setattr(bridge, "import_recording", temporarily_locked)
    assert backend.state["recordings"][-1]["practice_eligible"] is False
    assert backend.state["recordings"][-1]["practice_eligible"] is True
    assert len(calls) == 2 and calls[0] == calls[1]
    assert backend.state["recordings"][-1]["practice_eligible"] is True and len(calls) == 2


@pytest.mark.parametrize("change", ["changed", "removed", "replaced", "same_id_new_file"])
def test_backend_native_eligibility_cache_detects_changed_file_identity(backend, change):
    value = recording("flip-reset")
    backend._store_recording(value)
    backend.request = {"lesson_id": "flip-reset", "variants": {}}
    assert backend.state["recordings"][-1]["practice_eligible"] is True
    entry = backend.document["recordings"][-1]
    path = backend.store.directory / "recordings" / entry["filename"]
    value["outcome"] = "failed"
    if change == "changed":
        path.write_text(json.dumps(value), encoding="utf-8")
    elif change == "removed":
        path.unlink()
    elif change == "replaced":
        replacement = path.with_suffix(".replacement")
        replacement.write_text(json.dumps(value), encoding="utf-8")
        replacement.replace(path)
    else:
        alternate = path.with_name(f"{uuid.uuid4()}.json")
        alternate.write_text(json.dumps(value), encoding="utf-8")
        entry["filename"] = alternate.name
    assert backend.state["recordings"][-1]["practice_eligible"] is False


@pytest.mark.skipif(not os.environ.get("MCT_NATIVE_GHOST_LAYOUT_TEST"),
                    reason="Native menu executable is optional outside native checks")
@pytest.mark.parametrize("failure", ["failed", "truncated", "missing_ball"])
def test_native_menu_selects_older_eligible_flip_trace_from_actual_backend_rows(backend, tmp_path, failure):
    value = recording("flip-reset")
    backend._store_recording(value)
    usable_id = backend.document["recordings"][-1]["id"]
    bad = json.loads(json.dumps(value))
    if failure == "failed":
        bad["outcome"] = "failed"
    elif failure == "truncated":
        bad["truncated"] = True
    else:
        del bad["samples"][-1]["ball_position"]
    backend._store_recording(bad)
    backend.session_id = str(uuid.uuid4())
    backend.session_state = "training"
    backend.request = {"lesson_id": "flip-reset", "variants": {}}
    backend.process = FakeProcess()
    backend.telemetry = {"ghost_practice_support": {"supported": True}}
    payload = tmp_path / "synthetic-flip-menu.json"
    payload.write_text(json.dumps(backend.state), encoding="utf-8")
    result = subprocess.run([os.environ["MCT_NATIVE_GHOST_LAYOUT_TEST"], str(payload)],
                            capture_output=True, text=True, check=True)
    assert json.loads(result.stdout) == {"id": "flip-reset", "recording_id": usable_id}
