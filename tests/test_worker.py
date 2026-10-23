"""Worker contracts exercised without importing the Windows SDK or launching a game."""
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace as NS
import uuid

import pytest

from my_career_training import adapter, game_worker as worker


def request(tmp_path):
    return {"type": "start", "session_id": str(uuid.uuid4()), "data_dir": str(tmp_path),
            "fixture": {"id": "fixture-1"}, "settings": {"launcher": "steam", "install_path": ""}}


def test_json_transport_and_no_lazy_sdk_imports():
    output = io.StringIO()
    instance = worker.Worker(output)
    instance.run(io.StringIO('{"type":"ping","id":17}\n{bad\n{"type":"shutdown","id":19}\n'))
    events = [json.loads(line) for line in output.getvalue().splitlines()]
    assert events[0] == {"type": "ready", "protocol": 1, "session_id": None}
    assert events[1] == {"type": "pong", "id": 17, "session_id": None}
    assert events[2]["type"] == "error"
    assert events[3] == {"type": "stopped", "id": 19, "session_id": None}


def test_session_uuid_rejects_path_traversal():
    for value in ("../../save", "..", "", None, str(uuid.uuid4()).upper()):
        with pytest.raises(ValueError):
            worker.session_uuid(value)


def test_outbox_receipt_atomic_and_durable_before_emit(tmp_path, monkeypatch):
    events = []
    instance, packet = simulated_session(tmp_path, monkeypatch, events)
    original = instance.emit
    def emit(event):
        if event["type"] == "result":
            receipt = Path(tmp_path, "outbox", instance.session_id + ".json")
            assert json.loads(receipt.read_text()) == event
        original(event)
    instance.emit = emit
    packet.match_info.match_phase = 3
    instance.process_packet(packet)
    packet.match_info.match_phase = 7
    instance.process_packet(packet)
    instance.process_packet(packet)
    results = [event for event in events if event["type"] == "result"]
    assert len(results) == 1
    assert (results[0]["home_score"], results[0]["away_score"]) == (4, 3)
    assert results[0]["provenance"] == "game"
    assert not list(Path(tmp_path, "outbox").glob("*.tmp"))


def test_no_result_without_observed_active_match(tmp_path, monkeypatch):
    events = []
    instance, packet = simulated_session(tmp_path, monkeypatch, events)
    instance.process_packet(packet)
    assert not any(event["type"] == "result" for event in events)
    assert not Path(tmp_path, "outbox").exists()


def simulated_session(tmp_path, monkeypatch, events):
    flat = NS(MatchPhase=NS(Active=3, Ended=7), ControllerState=lambda **kw: kw,
              PlayerInput=lambda index, state: (index, state))
    monkeypatch.setitem(sys.modules, "rlbot", NS(flat=flat))
    instance = worker.GameSession(request(tmp_path), events.append)
    instance.human_index = 1
    instance.human_team = 0
    instance.owned = object()
    instance.descriptors = {0: {"team": 1}}
    instance._discover_game = lambda: None
    car = {"index": 1, "team": 0, "is_bot": False,
           "actions": {"jump": False, "boost": False, "handbrake": False}}
    frame = {"time": 1., "frame_num": 3, "cars": [{"index": 0, "team": 1, "is_bot": True}, car], "ball": {}}
    monkeypatch.setattr(adapter, "normalized_packet", lambda *a: dict(frame))
    packet = NS(match_info=NS(match_phase=7), teams=[NS(team_index=0, score=4), NS(team_index=1, score=3)])
    return instance, packet


def test_unowned_game_packets_never_processed(tmp_path, monkeypatch):
    events = []
    instance, packet = simulated_session(tmp_path, monkeypatch, events)
    instance.owned = None
    instance.process_packet(packet)
    assert not events
    assert not instance.first_packet


def test_bot_controls_cannot_target_human(tmp_path):
    instance = worker.GameSession(request(tmp_path), lambda event: None)
    instance.descriptors = {0: {"team": 1}}
    instance.human_index = 1
    with pytest.raises(RuntimeError, match="mapping"):
        instance.map_team(1, NS(team=1, controllables=[NS(index=1)]))
    assert not instance.mapping
    instance.map_team(1, NS(team=1, controllables=[NS(index=0)]))
    assert instance.mapping == {1: [0]}


def test_unexpected_packet_human_mapping_fails_before_controls(tmp_path, monkeypatch):
    instance, packet = simulated_session(tmp_path, monkeypatch, [])
    monkeypatch.setattr(adapter, "normalized_packet", lambda *a: {"cars": [{"index": 0, "team": 0, "is_bot": False}]})
    with pytest.raises(RuntimeError, match="human-player"):
        instance.process_packet(packet)


def test_relay_mutable_lists_are_isolated():
    class Relay:
        pass
    for name in worker.HANDLER_NAMES:
        setattr(Relay, name, [])
    first, second = worker.isolated_relay(Relay()), worker.isolated_relay(Relay())
    first.packet_handlers.append("first")
    assert second.packet_handlers == []
    assert Relay.packet_handlers == []


def test_attempt_ack_required_before_reset(tmp_path):
    instance = worker.GameSession(request(tmp_path), lambda event: None)
    instance.engine = NS(preferences={"auto_reset": False})
    instance.attempt_sent = "attempt-1"
    with pytest.raises(RuntimeError, match="saved"):
        instance.reset()
    instance.handle_command({"type": "attempt_ack", "attempt_id": "different"})
    assert not instance.attempt_acked
    instance.handle_command({"type": "attempt_ack", "attempt_id": "attempt-1"})
    assert instance.attempt_acked


def test_preflight_refuses_preexisting_game_and_core(monkeypatch):
    import psutil
    for name in ("RocketLeague.exe", "RLBotServer.exe"):
        monkeypatch.setattr(psutil, "process_iter", lambda *args: iter([NS(info={"name": name})]))
        with pytest.raises(RuntimeError, match="Close Rocket League"):
            worker.preflight()


def test_windows_start_fails_cleanly_on_other_platforms(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    events = []
    instance = worker.GameSession(request(tmp_path), events.append)
    instance.run()
    assert events[-1]["type"] == "stopped"
    assert any(event["type"] == "error" and "Windows" in event["message"] for event in events)
    assert all(event["session_id"] == instance.session_id for event in events)


def test_stop_drains_and_echoes_command_id(tmp_path):
    instance = worker.GameSession(request(tmp_path), lambda event: None)
    instance.handle_command({"type": "stop", "id": "stop-1"})
    assert instance.stopping
    assert instance.stop_id == "stop-1"
    assert instance.stop_deadline > 0


def test_stop_cancels_startup_without_creating_runtime(tmp_path):
    instance = worker.GameSession(request(tmp_path), lambda event: None)
    instance.command({"type": "stop", "id": 2})
    with pytest.raises(worker.SessionCancelled):
        instance.connect(lambda **kwargs: pytest.fail("Cancelled session connected"), NS(), 12345)
    assert instance.stop_id == 2


def test_sdk_contract_roundtrip_on_windows():
    if sys.platform != "win32":
        pytest.skip("Native RLBot flatbuffers is packaged for the Windows game worker")
    from rlbot import flat
    from rlbot.managers.rendering import Renderer
    from my_career_training.career import new_career, next_fixture
    from my_career_training.training import lesson
    config, descriptors, human = adapter.match_config({"fixture": next_fixture(new_career("Test", format=3)),
                                                     "settings": {"launcher": "steam"}})
    restored = flat.MatchConfiguration.unpack(config.pack())
    assert len(restored.player_configurations) == 6
    assert isinstance(restored.player_configurations[human].variety, flat.Human)
    assert len(descriptors) == 5
    assert restored.auto_start_agents is False
    state = flat.ControllerState(throttle=1, steer=.25, jump=True)
    message = flat.PlayerInput(0, state)
    assert flat.PlayerInput.unpack(message.pack()).controller_state.jump is True
    assert adapter.desired_state(lesson("speed-flip")["starting_state"], human).pack()
    emitted = []
    relay = NS(send_msg=emitted.append, can_render=True)
    renderer = Renderer(relay)
    renderer._used_group_ids = set()
    renderer._current_renders = []
    with renderer.context("test-contract"):
        renderer.draw_line_3d(flat.Vector3(0, 0, 0), flat.Vector3(100, 0, 100))
    assert emitted[0].pack()
