"""Synthetic packet receipts through the real worker and native bridge pipeline."""
from __future__ import annotations

import json
import copy
import os
import subprocess

import pytest

from my_career_training import game_worker as worker
from my_career_training.ingame import FileBridge, native_ghost_poll_interval
from test_worker import simulated_session, training_frame, training_recovery_session


@pytest.fixture
def ghost_backend(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication
    from my_career_training import bridge
    app = QApplication.instance() or QApplication(["native-ghost-revocation-test"])
    assert app is not None
    monkeypatch.setattr(bridge, "detect_installations", lambda: [])
    backend = bridge.Backend(tmp_path)
    backend.timer.stop()
    yield backend
    backend.process = None
    backend.close()


@pytest.mark.parametrize("pending_on", [False, True])
@pytest.mark.parametrize("lesson", ["speed-flip", "flip-reset"])
def test_assistance_off_revokes_and_suppresses_delayed_on_without_changing_display_preferences(ghost_backend, pending_on, lesson):
    from test_game_worker_ghost_practice import FakeProcess
    backend = ghost_backend
    backend.session_id = "synthetic-worker"
    backend.request = {"lesson_id": lesson}
    backend.process = FakeProcess()
    backend._ghost_practice_enabled = True
    backend.telemetry = {"ghost_practice": {"available": True, "enabled": True, "visible": True,
                                           "pose": {"time": 1}}, "ghost_practice_support": {"supported": True}}
    on_id = None
    if pending_on:
        backend._ghost_practice_enabled = False
        backend.dispatch("ghost_control", {"operation": "toggle", "enabled": True})
        on_id = json.loads(backend.process.writes[-1])["id"]
    display_before = copy.deepcopy(backend.document["settings"].get("training_display"))
    backend.dispatch("assistance", {"id": lesson, "key": "ghost", "value": False})
    assert backend.error == "" and backend._ghost_practice_enabled is False
    assert backend.state["telemetry"]["ghost_practice"]["pose"] is None
    assert backend.document["lesson_preferences"][lesson]["ghost"] is False
    assert backend.document["settings"].get("training_display") == display_before
    if on_id:
        backend._event({"type": "ghost_ack", "session_id": backend.session_id, "id": on_id,
                        "accepted": True, "enabled": True})
        backend._event({"type": "telemetry", "session_id": backend.session_id,
            "ghost_practice": {"available": True, "enabled": True, "visible": False}})
        assert backend._ghost_practice_enabled is False
    backend._event({"type": "telemetry", "session_id": backend.session_id,
        "ghost_practice": {"available": True, "enabled": True, "visible": True, "pose": {"time": 1}}})
    assert backend.state["telemetry"]["ghost_practice"]["pose"] is None


def test_packet_arrival_receipt_precedes_inbox_delay_and_coalescing(tmp_path, monkeypatch):
    emitted = []
    session, packet = simulated_session(tmp_path, monkeypatch, emitted)
    monkeypatch.setattr(worker, "windows_uptime_ms", lambda: 1000)
    session.receive_packet(packet)
    monkeypatch.setattr(worker, "windows_uptime_ms", lambda: 1016)
    session.receive_packet(packet)
    assert session.events.qsize() == 1
    kind, arrival = session.events.get()
    assert kind == "packet" and arrival.sequence == 1  # First terminal packet retained.
    assert arrival.received_uptime_ms == 1000
    # Dispatch well after the original callback; do not restamp at processing.
    monkeypatch.setattr(worker, "windows_uptime_ms", lambda: 2000)
    packet.match_info.match_phase = 3
    session.process_packet(arrival)
    source = next(event for event in emitted if event["type"] == "telemetry")["native_ghost_source"]
    assert source["received_uptime_ms"] == 1000 and source["sequence"] == 1
    assert source["session_id"] == session.session_id


def test_active_inbox_coalescing_keeps_latest_callback_identity(tmp_path, monkeypatch):
    session, packet = simulated_session(tmp_path, monkeypatch, [])
    packet.match_info.match_phase = 3
    monkeypatch.setattr(worker, "windows_uptime_ms", lambda: 1000)
    session.receive_packet(packet)
    monkeypatch.setattr(worker, "windows_uptime_ms", lambda: 1032)
    session.receive_packet(packet)
    assert session.events.qsize() == 1
    arrival = session.events.get()[1]
    assert arrival.sequence == 2 and arrival.received_uptime_ms == 1032


def test_direct_packet_without_callback_receipt_has_no_native_age_authority(tmp_path, monkeypatch):
    events = []
    session, packet = simulated_session(tmp_path, monkeypatch, events)
    packet.match_info.match_phase = 3
    session.process_packet(packet)
    assert next(event for event in events if event["type"] == "telemetry")["native_ghost_source"] is None


def test_fast_publish_interval_requires_active_same_worker_ghost():
    state = {"session": {"id": "synthetic-worker", "kind": "training", "state": "training", "worker_running": True},
             "telemetry": {"ghost_practice": {"enabled": True, "visible": True},
                           "native_ghost_source": {"session_id": "synthetic-worker"}}}
    assert native_ghost_poll_interval(state) == 33
    for group, key, value in [
        ("session", "kind", "career"), ("session", "state", "Idle"),
        ("session", "worker_running", False), ("session", "id", "other-worker"),
        ("ghost_practice", "enabled", False), ("ghost_practice", "visible", False),
        ("native_ghost_source", "session_id", "old-worker"),
    ]:
        changed = json.loads(json.dumps(state))
        target = changed[group] if group == "session" else changed["telemetry"][group]
        target[key] = value
        assert native_ghost_poll_interval(changed) == 100
    assert native_ghost_poll_interval({}) == 100


@pytest.mark.parametrize("scope", ["missing", "old_worker", "invalid_nonce"])
def test_worker_refuses_actor_reset_without_its_authenticated_bridge(tmp_path, monkeypatch, scope):
    from my_career_training import adapter
    session, _packet, sent = training_recovery_session(tmp_path, monkeypatch, [], [])
    session.request["in_game"] = True
    monkeypatch.setattr(adapter, "desired_state", lambda state, human, *_: (state, human))
    if scope != "missing":
        directory = tmp_path / "bridge"
        directory.mkdir()
        (directory / "state.json").write_text(json.dumps({"protocol": 1, "offline": True,
            "bridge_session": "invalid" if scope == "invalid_nonce" else "00000000-0000-4000-8000-000000000001",
            "session": {"id": "old-worker" if scope == "old_worker" else session.session_id}}))
    with pytest.raises((ValueError, OSError, RuntimeError)):
        session.reset()
    assert sent == [] and session.native_ghost_generation is None


@pytest.mark.skipif(not os.environ.get("MCT_NATIVE_GHOST_PLAYBACK_TEST"),
                    reason="Requires native playback test and companion recorded-pose integration")
def test_actual_worker_backend_file_bridge_and_native_source_age(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication
    from my_career_training import bridge
    from my_career_training.training import practice_support
    from my_career_training import adapter
    from test_game_worker_ghost_practice import FakeProcess, lesson_session

    # Execute the actual Win32 clock in both processes before synthetic timing.
    before = worker.windows_uptime_ms()
    result = subprocess.run([os.environ["MCT_NATIVE_GHOST_PLAYBACK_TEST"], "--clock"],
                            text=True, capture_output=True, check=True)
    native_uptime = json.loads(result.stdout)
    after = worker.windows_uptime_ms()
    assert before is not None and before <= native_uptime <= after

    app = QApplication.instance() or QApplication(["native-ghost-receipt-test"])
    assert app is not None
    monkeypatch.setattr(bridge, "detect_installations", lambda: [])
    backend = bridge.Backend(tmp_path)
    backend.timer.stop()
    try:
        first, second = training_frame(), training_frame()
        second.update(time=1 + 1 / 60, frame_num=122)
        events = []
        session, packet, _sent = training_recovery_session(tmp_path, monkeypatch, events, [first, second])
        session.request["lesson_id"] = "speed-flip"
        session.last_frame = dict(training_frame(), time=1 - 1 / 60, frame_num=118)
        session.last_telemetry = float("-inf")
        teacher, _ = lesson_session()
        session.practice = teacher.practice
        session.practice_support = practice_support("speed-flip")
        session.practice.set_enabled(True, player_pose=first["cars"][1])
        backend.session_id = session.session_id
        backend.session_state = "training"
        backend.request = {"lesson_id": "speed-flip", "variants": {}}
        backend.process = FakeProcess()
        backend._ghost_practice_enabled = True
        published = [2000.0]
        pipe = FileBridge(tmp_path, lambda *_args: None, lambda: backend.state, clock=lambda: published[0])
        pipe.poll()
        session.request["in_game"] = True
        monkeypatch.setattr(adapter, "desired_state", lambda state, human, *_: (state, human))
        session.reset()
        from test_training import activate
        activate(session.engine)

        def dispatch(received):
            monkeypatch.setattr(worker, "windows_uptime_ms", lambda: received)
            session.last_telemetry = float("-inf")
            session.receive_packet(packet)
            session.process_packet(session.events.get()[1])
            event = [event for event in events if event["type"] == "telemetry"][-1]
            backend._event(event)
            assert pipe.poll() == 33
            value = json.loads((pipe.directory / "state.json").read_text())
            assert value["telemetry"]["native_ghost_source"] == event["native_ghost_source"]
            return value

        original = dispatch(1000)
        published[0] = 2100
        assert pipe.poll() == 33
        heartbeat = json.loads((pipe.directory / "state.json").read_text())
        assert heartbeat["published_at"] != original["published_at"]
        assert heartbeat["telemetry"]["native_ghost_source"] == original["telemetry"]["native_ghost_source"]
        recovered = dispatch(1110)
        inputs = [
            {"state": original, "now": 100.01, "uptime_ms": 1010},
            {"state": heartbeat, "now": 100.101, "uptime_ms": 1101},
            {"state": recovered, "now": 100.12, "uptime_ms": 1120},
            {"state": recovered, "now": 100.32, "uptime_ms": 1320},
        ]
        for item in inputs:
            item["bridge_directory"] = str(pipe.directory)
        result = subprocess.run([os.environ["MCT_NATIVE_GHOST_PLAYBACK_TEST"], "--transport"],
                                input=json.dumps(inputs), text=True, capture_output=True, check=True)
        native = json.loads(result.stdout)
        assert [row["visible"] for row in native] == [True, False, True, False]
        assert native[0]["observed_at"] == pytest.approx(100)
        assert native[2]["observed_at"] == pytest.approx(100.11)
        backend._ghost_practice_enabled = False
        backend._clear_ghost_practice_state()
        assert pipe.poll() == 100
    finally:
        backend.process = None
        backend.close()


@pytest.mark.skipif(not os.environ.get("MCT_NATIVE_GHOST_PLAYBACK_TEST"),
                    reason="Requires native playback test and companion recorded-pose integration")
def test_actual_retry_auto_reset_fence_and_assistance_off_revoke_native_ghost(
        ghost_backend, tmp_path, monkeypatch):
    from my_career_training import adapter
    from my_career_training.storage import Store
    from my_career_training.training import practice_support
    from test_game_worker_ghost_practice import FakeProcess, lesson_session
    from test_training import frame as engine_frame

    backend = ghost_backend
    events = []
    session, template, sent = training_recovery_session(tmp_path, monkeypatch, events, [])
    session.request.update(lesson_id="speed-flip", in_game=True)
    teacher, _ = lesson_session()
    session.practice, session.coach = teacher.practice, teacher.coach
    session.practice_support = practice_support("speed-flip")
    session.practice.set_enabled(True, player_pose={"position": [0, -2500, 17], "rotation": [0, 0, 0]})
    backend.session_id = session.session_id
    backend.session_state = "training"
    backend.request = {"lesson_id": "speed-flip", "variants": {}}
    backend.process = FakeProcess()
    backend._ghost_practice_enabled = True
    backend._sync_ghost_assistance("speed-flip", True)
    pipe = FileBridge(tmp_path, backend.dispatch, lambda: backend.state, clock=lambda: 2000)
    pipe.poll()
    monkeypatch.setattr(adapter, "desired_state", lambda state, human, *_: (state, human))
    session.reset()
    monkeypatch.setattr(adapter, "normalized_packet", lambda packet, *_: copy.deepcopy(packet.synthetic_frame))
    serial, uptime = [0], [1000]
    monkeypatch.setattr(worker, "windows_uptime_ms", lambda: uptime[0])

    def tick():
        serial[0] += 1
        uptime[0] += 16
        target = (session.engine.lesson["settle_state"] if session.engine.state == "settling"
                  else session.engine.starting_state)
        frame = engine_frame(1 + serial[0] / 60, target["car"]["position"], target["ball"]["position"],
            car={key: target["car"][key] for key in ("rotation", "velocity", "boost")})
        frame["ball"]["velocity"] = list(target["ball"]["velocity"])
        human = dict(frame["car"], index=1, team=0, is_bot=False, actions=frame["actions"])
        bot = dict(human, index=0, team=1, is_bot=True)
        packet = copy.deepcopy(template)
        packet.synthetic_frame = {"time": frame["time"], "frame_num": serial[0] * 2,
                                  "cars": [bot, human], "ball": frame["ball"]}
        session.last_telemetry = float("-inf")
        session.receive_packet(packet)
        session.process_packet(session.events.get()[1])
        event = [event for event in events if event["type"] == "telemetry"][-1]
        backend._event(event)
        pipe.poll()
        return json.loads((pipe.directory / "state.json").read_text()), packet

    def active():
        for _ in range(80):
            snapshot, packet = tick()
            source = snapshot["telemetry"].get("native_ghost_source") or {}
            if session.engine.state == "active" and source.get("reset_observed") is True:
                return snapshot, packet
        pytest.fail("Synthetic observed actor state never confirmed the actual engine reset")

    cached, packet = active()
    probe = subprocess.Popen([os.environ["MCT_NATIVE_GHOST_PLAYBACK_TEST"], "--live-transport"],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    def visible(snapshot):
        request = {"state": snapshot, "bridge_directory": str(pipe.directory),
                   "now": 100 + uptime[0] / 1000, "uptime_ms": uptime[0]}
        probe.stdin.write(json.dumps(request) + "\n")
        probe.stdin.flush()
        return json.loads(probe.stdout.readline())["visible"]

    try:
        assert visible(cached) is True
        # Keep an actual pre-reset callback in the inbox across the reset.
        session.receive_packet(packet)
        queued = session.events.get()[1]
        prior_attempt = session.engine.attempt_id
        prior_generation = cached["telemetry"]["native_ghost_source"]["reset_generation"]
        checks = []
        def before_actor_write(message):
            fence = json.loads((pipe.directory / "native-ghost-reset.json").read_text())
            assert fence["generation"] != prior_generation
            assert visible(cached) is False  # The native consumer still has the old bridge snapshot.
            checks.append(fence["generation"])
            sent.append(message)
        session.manager.rlbot_interface.send_msg = before_actor_write
        saved_preferences = copy.deepcopy(backend.document["lesson_preferences"])
        backend.dispatch("retry_lesson", {"expected_session_id": backend.session_id})
        assert backend._ghost_practice_enabled is True
        assert backend.state["telemetry"]["ghost_practice"]["pose"] is None
        session.handle_command(json.loads(backend.process.writes[-1]))
        assert checks and session.engine.attempt_id != prior_attempt
        assert session.practice.enabled and session.practice.cursor == 0
        assert backend.document["lesson_preferences"] == saved_preferences
        session.last_telemetry = float("-inf")
        session.process_packet(queued)
        stale = [event for event in events if event["type"] == "telemetry"][-1]
        assert stale["native_ghost_source"]["reset_generation"] == prior_generation
        backend._event(stale)
        pipe.poll()
        assert backend.state["telemetry"]["ghost_practice"]["visible"] is False
        assert visible(cached) is False
        # Real observed settle/launch packets, not a fabricated reset acknowledgement.
        session.manager.rlbot_interface.send_msg = sent.append
        cached, packet = active()
        assert visible(cached) is True
        backend._event(stale)
        pipe.poll()
        assert visible(json.loads((pipe.directory / "state.json").read_text())) is False
        cached, packet = tick()
        assert visible(cached) is True
        prior_generation = cached["telemetry"]["native_ghost_source"]["reset_generation"]

        # Drive the actual saved-attempt acknowledgement before automatic reset.
        session.engine.set_preference("auto_reset", True)
        session.engine._finish("failed")
        session.publish_attempt()
        attempt = [event for event in events if event["type"] == "attempt"][-1]
        backend._event(attempt)
        ack = json.loads(backend.process.writes[-1])
        assert ack["type"] == "attempt_ack"
        session.handle_command(ack)
        assert session.attempt_acked and session.attempt_retryable
        session.auto_reset_at = 0
        session.manager.rlbot_interface.send_msg = before_actor_write
        session._check_auto_reset()
        assert session.engine.state == "settling" and visible(cached) is False
        session.manager.rlbot_interface.send_msg = sent.append
        cached, packet = active()
        assert visible(cached) is True

        display_before = copy.deepcopy(backend.document["settings"]["training_display"])
        backend.dispatch("assistance", {"id": "speed-flip", "key": "ghost", "value": False})
        session.handle_command(json.loads(backend.process.writes[-1]))
        assert session.practice.enabled is False
        assert backend.document["settings"]["training_display"] == display_before
        delayed = [event for event in events if event["type"] == "telemetry"][-1]
        backend._event(delayed)
        pipe.poll()
        assert visible(json.loads((pipe.directory / "state.json").read_text())) is False

        benchmark = subprocess.run([os.environ["MCT_NATIVE_GHOST_PLAYBACK_TEST"], "--fence-benchmark"],
            input=json.dumps({"bridge_directory": str(pipe.directory), "session_id": backend.session_id,
                              "bridge_session": pipe.session}), capture_output=True, text=True, check=True)
        print("Native fixed-fence reader benchmark:", benchmark.stdout.strip())
        # A missing, invalid or old-session fence must fail closed even with cached state.
        fence_path = pipe.directory / "native-ghost-reset.json"
        fence = fence_path.read_bytes()
        for invalid in (b"not json", b"x" * 1025,
                json.dumps({"protocol": 1, "bridge_session": pipe.session,
                    "session_id": "old-worker", "generation": prior_generation}).encode(),
                json.dumps({"protocol": 1, "bridge_session": "old-bridge",
                    "session_id": backend.session_id, "generation": prior_generation}).encode()):
            Store._atomic(fence_path, invalid)
            assert visible(cached) is False
        fence_path.unlink()
        assert visible(cached) is False
        Store._atomic(fence_path, fence)
        pipe.close()
        assert visible(cached) is False
    finally:
        probe.stdin.close()
        probe.wait(timeout=10)
        assert probe.returncode == 0, probe.stderr.read()
