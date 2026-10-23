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
    packet.match_info.match_phase = 3
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


def test_high_rate_inbox_is_bounded_and_preserves_active_before_terminal():
    inbox = worker.SessionInbox()
    for index in range(10000):
        packet = NS(match_info=NS(match_phase=3), number=index)
        inbox.put(("packet", packet))
        inbox.put(("prediction", index))
    assert inbox.qsize() == 2
    end = NS(match_info=NS(match_phase=7), number=10000)
    inbox.put(("packet", end))
    inbox.put(("command", {"type": "stop"}))
    inbox.put(("packet", NS(match_info=NS(match_phase=7), number=10001)))
    assert inbox.qsize() == 4
    assert inbox.get()[1].number == 9999
    assert inbox.get() == ("prediction", 9999)
    assert inbox.get() == ("packet", end)
    assert inbox.get() == ("command", {"type": "stop"})


def test_inbox_replacement_keeps_latest_arrival_order():
    inbox = worker.SessionInbox()
    inbox.put(("prediction", 1))
    inbox.put(("command", {"type": "preferences"}))
    inbox.put(("prediction", 2))
    assert inbox.get()[0] == "command"
    assert inbox.get() == ("prediction", 2)
    with pytest.raises(worker.queue.Empty):
        inbox.get(timeout=0)


def test_stop_request_blocks_bot_controls_before_queued_stop_is_processed(tmp_path, monkeypatch):
    events = []
    instance, packet = simulated_session(tmp_path, monkeypatch, events)
    instance.mapping = {1: [0]}
    instance.controllers = {0: NS(intent=None, step=lambda *a: pytest.fail("Bot ran after stop"))}
    instance.relays = {1: NS(send_msg=lambda *a: pytest.fail("Bot input sent after stop"))}
    instance.seen_active = True
    instance.command({"type": "stop", "id": "stop-before-drain"})
    assert not instance.stopping  # Stop event is pending; immediate stop flag still applies.
    instance.process_packet(packet)
    assert any(event["type"] == "result" for event in events)


def test_stop_request_blocks_reset_engine_and_ghost_work(tmp_path, monkeypatch):
    instance, packet = simulated_session(tmp_path, monkeypatch, [])
    instance.engine = NS(update=lambda *a: pytest.fail("Training continued after stop"))
    instance.renderer = NS(can_render=True)
    instance.command({"type": "stop"})
    instance.process_packet(packet)
    instance.reset()
    instance.render({})
    assert not instance.applied_reset


def test_calibration_receipt_retains_calibration_identity(tmp_path, monkeypatch):
    events = []
    instance, packet = simulated_session(tmp_path, monkeypatch, events)
    instance.request["calibration"] = True
    instance.seen_active = True
    instance.process_packet(packet)
    result = next(event for event in events if event["type"] == "result")
    assert result["calibration"] is True
    receipt = json.loads(Path(tmp_path, "outbox", instance.session_id + ".json").read_text())
    assert receipt["calibration"] is True


def test_observed_hitbox_records_real_dimensions_and_offset():
    player = NS(hitbox=NS(length=118.01, width=84.2, height=36.3), hitbox_offset=NS(x=13.9, y=0, z=20.75))
    assert worker.observed_hitbox(player) == {"dimensions": [118.01, 84.2, 36.3], "offset": [13.9, 0, 20.75],
                                             "source": "RLBot game packet"}
    player.hitbox.width = float("nan")
    assert worker.observed_hitbox(player) == "unknown"
    assert worker.observed_hitbox(NS()) == "unknown"


def test_file_version_unknown_outside_windows(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    assert worker.game_file_version("game.exe") == "unknown"


def test_initial_inactive_and_partial_roster_wait_without_controls(tmp_path, monkeypatch):
    events = []
    instance, packet = simulated_session(tmp_path, monkeypatch, events)
    instance.mapping = {1: [0]}
    instance.controllers = {0: NS(intent=None, step=lambda *a: pytest.fail("Bot ran before complete active roster"))}
    packet.players = []
    packet.match_info.match_phase = 0
    monkeypatch.setattr(adapter, "normalized_packet", lambda *a: pytest.fail("Inactive roster normalized"))
    instance.process_packet(packet)
    packet.match_info.match_phase = 1
    instance.process_packet(packet)
    assert not events
    assert not instance.first_packet
    assert not instance.seen_active
    # Once Active arrives, an incomplete roster is an error rather than a waiting state.
    packet.match_info.match_phase = 3
    monkeypatch.setattr(adapter, "normalized_packet", lambda *a: {"cars": []})
    with pytest.raises(RuntimeError, match="human-player"):
        instance.process_packet(packet)


def test_full_roster_before_kickoff_does_not_send_controls(tmp_path, monkeypatch):
    instance, packet = simulated_session(tmp_path, monkeypatch, [])
    instance.mapping = {1: [0]}
    instance.controllers = {0: NS(intent=None, step=lambda *a: pytest.fail("Bot ran during countdown"))}
    packet.match_info.match_phase = 1
    instance.process_packet(packet)
    assert instance.first_packet
    assert not instance.seen_active


@pytest.mark.parametrize("agent_id,expected", [("", False), ("my-career-training/team-0", True)])
def test_core_requires_bot_relay_close_between_matches(tmp_path, agent_id, expected):
    instance = worker.GameSession(request(tmp_path), lambda event: None)
    relay = NS(agent_id=agent_id)
    calls = []
    instance.connect(lambda **kwargs: calls.append(kwargs), relay, 24123)
    assert calls[0]["close_between_matches"] is expected
    assert calls[0]["rlbot_server_port"] == 24123
