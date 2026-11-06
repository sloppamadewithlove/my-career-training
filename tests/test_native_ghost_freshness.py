"""Synthetic packet receipts through the real worker and native bridge pipeline."""
from __future__ import annotations

import json
import os
import subprocess

import pytest

from my_career_training import game_worker as worker
from my_career_training.ingame import FileBridge, native_ghost_poll_interval
from test_worker import simulated_session, training_frame, training_recovery_session


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


@pytest.mark.skipif(not os.environ.get("MCT_NATIVE_GHOST_PLAYBACK_TEST"),
                    reason="Requires native playback test and companion recorded-pose integration")
def test_actual_worker_backend_file_bridge_and_native_source_age(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication
    from my_career_training import bridge
    from my_career_training.training import practice_support
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
