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


def test_reversed_team_array_keeps_canonical_telemetry_and_final_score(tmp_path, monkeypatch):
    events = []
    instance, packet = simulated_session(tmp_path, monkeypatch, events)
    packet.teams.reverse()
    packet.match_info.match_phase = 3
    instance.process_packet(packet)
    telemetry = next(event for event in events if event["type"] == "telemetry")
    assert telemetry["scores"] == [4, 3]
    packet.match_info.match_phase = 7
    instance.process_packet(packet)
    result = next(event for event in events if event["type"] == "result")
    assert (result["home_score"], result["away_score"]) == (4, 3)


@pytest.mark.parametrize("teams", [[], [NS(team_index=0, score=4)],
    [NS(team_index=0, score=4), NS(team_index=0, score=3)],
    [NS(team_index=0, score=4), NS(team_index=2, score=3)],
    [NS(team_index=0, score=4), NS(team_index=True, score=3)],
    [NS(team_index=0, score=4), NS(score=3)],
    [NS(team_index=0, score=4), NS(team_index=1, score=True)]])
def test_invalid_team_mapping_never_fabricates_observed_or_final_goals(tmp_path, monkeypatch, teams):
    events = []
    instance, packet = simulated_session(tmp_path, monkeypatch, events)
    packet.teams = teams
    packet.match_info.match_phase = 3
    instance.process_packet(packet)
    assert next(event for event in events if event["type"] == "telemetry")["scores"] == []
    packet.match_info.match_phase = 7
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


def test_bot_controls_cannot_target_human(tmp_path, monkeypatch):
    instance = worker.GameSession(request(tmp_path), lambda event: None)
    instance.descriptors = {0: {"team": 1}}
    instance.human_index = 1
    with pytest.raises(RuntimeError, match="mapping"):
        instance.map_team(1, NS(team=1, controllables=[NS(index=1)]))
    assert not instance.mapping
    sent = []
    monkeypatch.setitem(sys.modules, "rlbot", NS(flat=NS(InitComplete=lambda: "ready")))
    instance.relays[1] = NS(send_msg=sent.append)
    instance.map_team(1, NS(team=1, controllables=[NS(index=0)]))
    assert instance.mapping == {1: [0]}
    assert sent == ["ready"]
    instance.map_team(1, NS(team=1, controllables=[NS(index=0)]))
    assert sent == ["ready"]  # Repeated reservation notifications are idempotent.


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


def test_auto_reset_waits_one_second_after_first_durable_ack_and_duplicate_ack_does_not_extend(
    tmp_path, monkeypatch
):
    instance = worker.GameSession(request(tmp_path), lambda event: None)
    instance.engine = NS(preferences={"auto_reset": True})
    instance.attempt_sent = "attempt-with-samples"
    instance.attempt_retryable = True
    now = [100.0]
    resets = []
    instance.reset = lambda: resets.append(now[0])
    monkeypatch.setattr(worker.time, "monotonic", lambda: now[0])

    instance.handle_command({"type": "attempt_ack", "attempt_id": "attempt-with-samples"})
    deadline = instance.auto_reset_at
    assert instance.attempt_acked is True
    assert deadline == pytest.approx(101.0)
    assert resets == []

    now[0] = 100.75
    instance.handle_command({"type": "attempt_ack", "attempt_id": "attempt-with-samples"})

    assert instance.auto_reset_at == deadline
    assert resets == []


def test_prestart_attempt_ack_does_not_schedule_automatic_reset(tmp_path, monkeypatch):
    instance = worker.GameSession(request(tmp_path), lambda event: None)
    instance.engine = NS(preferences={"auto_reset": True})
    instance.attempt_sent = "prestart-interruption"
    instance.attempt_retryable = False
    resets = []
    instance.reset = lambda: resets.append(True)
    monkeypatch.setattr(worker.time, "monotonic", lambda: 100.0)

    instance.handle_command({"type": "attempt_ack", "attempt_id": "prestart-interruption"})

    assert instance.attempt_acked is True
    assert instance.auto_reset_at is None
    assert resets == []


def test_only_attempts_with_recorded_samples_are_eligible_for_auto_retry(tmp_path):
    instance = worker.GameSession(request(tmp_path), lambda _event: None)
    summary = {"id": "prestart", "state": "interrupted", "outcome": "interrupted"}
    recording = {"samples": []}
    instance.engine = NS(summary=lambda: dict(summary), recording=lambda: dict(recording))

    instance.publish_attempt()
    assert instance.attempt_retryable is False

    summary["id"] = "ran-attempt"
    recording["samples"] = [{"time": 0.0}]
    instance.publish_attempt()
    assert instance.attempt_retryable is True


def test_worker_accepts_two_step_training_samples_but_keeps_capture_strict(tmp_path, monkeypatch):
    def processed_frames(*, capture):
        events = []
        instance, packet = simulated_session(tmp_path, monkeypatch, events)
        observed = []
        instance.engine = NS(
            tolerances={"max_packet_interval": 0.05},
            metadata={}, recorder=NS(metadata={}), preferences={}, finished=False,
            update=lambda frame: observed.append(frame) or [],
            summary=lambda: {"coaching": {}},
        )
        instance.applied_reset = True
        instance.training_actor_index = 0 if capture else 1
        instance.renderer = NS(can_render=False)
        instance.last_controls = float("inf")
        instance.last_render = float("inf")
        instance.last_telemetry = float("inf")
        instance.game_version = "test-build"
        packet.players = [NS(), NS()]
        monkeypatch.setattr(worker, "observed_hitbox", lambda _player: {})
        if capture:
            instance.capture = {"target_index": 0}
            instance.capture_ready = True
            instance._capture_metadata = lambda *_args: {}

        samples = iter((
            {"time": 1.0, "frame_num": 120},
            {"time": 1.0 + 1 / 60, "frame_num": 122},
        ))

        def normalized_packet(*_args):
            tick = next(samples)
            bot = {
                "index": 0, "team": 1, "is_bot": True,
                "position": [0, 0, 17], "rotation": [0, 0, 0],
                "actions": {"throttle": 0.0, "steer": 0.0, "pitch": 0.0, "yaw": 0.0,
                            "roll": 0.0, "jump": False, "boost": False, "handbrake": False},
            }
            human = {
                "index": 1, "team": 0, "is_bot": False,
                "position": [0, 0, 17], "rotation": [0, 0, 0],
                "actions": {"throttle": 0.0, "steer": 0.0, "pitch": 0.0, "yaw": 0.0,
                            "roll": 0.0, "jump": False, "boost": False, "handbrake": False},
            }
            return {
                **tick,
                "cars": [bot, human],
                "ball": {"position": [0, 0, 93], "velocity": [0, 0, 0]},
            }

        monkeypatch.setattr(adapter, "normalized_packet", normalized_packet)
        instance.process_packet(packet)
        instance.process_packet(packet)
        return observed

    ordinary = processed_frames(capture=False)
    assert len(ordinary) == 2
    assert ordinary[1]["packet_gap"] is False
    assert ordinary[1]["cadence"] == "coarse_continuous"

    strict_capture = processed_frames(capture=True)
    assert len(strict_capture) == 2
    assert strict_capture[1]["packet_gap"] is True
    assert strict_capture[1]["cadence"] == "step_count_exceeded"


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
    instance.engine = NS(
        update=lambda *a: pytest.fail("Training continued after stop"),
        tolerances={"max_packet_interval": 0.05},
    )
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


def handshake_config(arena="Stadium_P"):
    class Human:
        pass
    class CustomBot:
        name = "Rival"
        agent_id = "my-career-training/team-1"
    return NS(game_map_upk=arena, player_configurations=[NS(team=1, variety=CustomBot()), NS(team=0, variety=Human())])


@pytest.mark.parametrize("cancel_during_model", [False, True])
def test_match_configuration_ack_precedes_bot_connections(tmp_path, monkeypatch, cancel_during_model):
    import threading
    from my_career_training.bots import providers
    configuration = handshake_config()
    order = []
    acknowledged = threading.Event()
    class Relay:
        def __init__(self, agent_id, **kwargs):
            if agent_id:
                assert acknowledged.is_set(), "Bot connection preceded asynchronous match acknowledgement"
            self.agent_id = agent_id
        def connect(self, **kwargs):
            order.append("team-connect" if self.agent_id else "manager-connect")
        def send_msg(self, value):
            order.append("init")
    class Manager:
        def __init__(self, executable):
            self.rlbot_interface = Relay("")
        def connect(self, **kwargs):
            self.rlbot_interface.connect(**kwargs)
        def start_match(self, config, **kwargs):
            order.append("start")
            def acknowledge():
                order.append("ack")
                acknowledged.set()
                for handler in self.rlbot_interface.match_config_handlers:
                    handler(config)
            timer = threading.Timer(.01, acknowledge)
            timer.daemon = True
            timer.start()
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setitem(sys.modules, "rlbot", NS(flat=NS(InitComplete=lambda: "init")))
    monkeypatch.setitem(sys.modules, "rlbot.interface", NS(SocketRelay=Relay))
    monkeypatch.setitem(sys.modules, "rlbot.managers.match", NS(MatchManager=Manager))
    monkeypatch.setitem(sys.modules, "rlbot.managers.rendering", NS(Renderer=lambda relay: NS()))
    monkeypatch.setattr(worker, "preflight", lambda owned=None: None)
    monkeypatch.setattr(worker, "core_path", lambda: Path("verified-runtime.exe"))
    monkeypatch.setattr(worker.subprocess, "Popen", lambda *a, **k: order.append("core") or NS(poll=lambda: None))
    def model(*args):
        order.append("model")
        if cancel_during_model:
            instance.command({"type": "shutdown"})
        return object()
    monkeypatch.setattr(providers, "create_controller", model)
    monkeypatch.setattr(adapter, "match_config", lambda req: (configuration,
        {0: {"team": 1, "level": 1, "difficulty": .5, "seed": 1}}, 1))
    instance = worker.GameSession(request(tmp_path), lambda event: None)
    monkeypatch.setattr(instance, "_relay_thread", lambda relay: None)
    if cancel_during_model:
        with pytest.raises(worker.SessionCancelled):
            instance.setup()
        assert order == ["model"]
        assert not (tmp_path / "runtime").exists()
        return
    instance.setup()
    assert order == ["model", "core", "manager-connect", "start", "ack", "team-connect"]
    order.append("mapping")
    instance.map_team(1, NS(team=1, controllables=[NS(index=0)]))
    assert order == ["model", "core", "manager-connect", "start", "ack", "team-connect", "mapping", "init"]


def test_match_handshake_rejects_wrong_configuration_and_times_out(tmp_path):
    instance = worker.GameSession(request(tmp_path), lambda event: None)
    master = NS(match_config_handlers=[])
    instance.core = NS(poll=lambda: None)
    def start(config, **kwargs):
        for handler in master.match_config_handlers:
            handler(handshake_config("wrong-arena"))
    instance.manager = NS(rlbot_interface=master, start_match=start)
    with pytest.raises(RuntimeError, match="acknowledge"):
        instance.start_acknowledged_match(handshake_config(), timeout=0)
    assert master.match_config_handlers == []


def test_stop_cancels_match_handshake_before_team_connections(tmp_path):
    instance = worker.GameSession(request(tmp_path), lambda event: None)
    master = NS(match_config_handlers=[])
    instance.core = NS(poll=lambda: None)
    def start(config, **kwargs):
        instance.command({"type": "stop"})
    instance.manager = NS(rlbot_interface=master, start_match=start)
    with pytest.raises(worker.SessionCancelled):
        instance.start_acknowledged_match(handshake_config())
    assert master.match_config_handlers == []


def test_cancelled_or_expired_start_never_creates_core(tmp_path, monkeypatch):
    instance = worker.GameSession(request(tmp_path), lambda event: None)
    calls = []
    monkeypatch.setattr(worker.subprocess, "Popen", lambda *a, **k: calls.append("spawn"))
    instance.command({"type": "shutdown"})
    with pytest.raises(worker.SessionCancelled):
        instance.spawn_core(tmp_path, 12345)
    instance.cancel_start.clear()
    instance.started_monotonic -= 121
    with pytest.raises(RuntimeError, match="two minutes"):
        instance.spawn_core(tmp_path, 12345)
    assert calls == []


def test_spawn_wins_race_then_stop_uses_only_created_handle(tmp_path, monkeypatch):
    import threading
    instance = worker.GameSession(request(tmp_path), lambda event: None)
    entered, release = threading.Event(), threading.Event()
    actions = []
    core = NS(poll=lambda: None, wait=lambda timeout: actions.append("wait"))
    def spawn(*args, **kwargs):
        entered.set()
        assert release.wait(2)
        return core
    monkeypatch.setattr(worker, "preflight", lambda owned: None)
    monkeypatch.setattr(worker, "core_path", lambda: Path("verified-runtime.exe"))
    monkeypatch.setattr(worker.subprocess, "Popen", spawn)
    loader = threading.Thread(target=instance.spawn_core, args=(tmp_path, 12345))
    stopper = threading.Thread(target=instance.command, args=({"type": "shutdown"},))
    loader.start()
    assert entered.wait(2)
    stopper.start()
    release.set()
    loader.join(2)
    stopper.join(2)
    assert not loader.is_alive() and not stopper.is_alive()
    assert instance.cancel_start.is_set() and instance.core is core
    instance.stop_owned_core()
    assert actions == ["wait"]


def test_blocked_pre_core_worker_exits_under_spawn_lock(tmp_path, monkeypatch):
    events = []
    instance = worker.GameSession(request(tmp_path), events.append)
    instance.stop_id = "timeout-stop"
    def exit_worker(code):
        assert code == 2 and instance.cancel_start.is_set()
        assert instance.core_lock.locked()
        raise SystemExit(code)
    monkeypatch.setattr(worker.os, "_exit", exit_worker)
    with pytest.raises(SystemExit):
        instance.exit_blocked_pre_core_worker()
    assert events == [{"type": "stopped", "session_id": instance.session_id, "id": "timeout-stop"}]
    instance.core = object()
    assert instance.exit_blocked_pre_core_worker() is False
    instance.core = None
    instance.result_sent = True
    assert instance.exit_blocked_pre_core_worker() is False


def test_cleanup_failure_does_not_report_stopped(tmp_path, monkeypatch):
    events = []
    instance = worker.GameSession(request(tmp_path), events.append)
    def cancelled():
        raise worker.SessionCancelled()
    def cleanup_failure():
        raise OSError("synthetic cleanup failure")
    monkeypatch.setattr(instance, "setup", cancelled)
    monkeypatch.setattr(instance, "teardown", cleanup_failure)
    instance.run()
    assert not any(event["type"] == "stopped" for event in events)
    assert events[-1]["type"] == "error"


def test_dead_session_cleanup_failure_cannot_acknowledge_shutdown(tmp_path, monkeypatch):
    output = io.StringIO()
    instance = worker.Worker(output)
    session = worker.GameSession(request(tmp_path), instance.emit)
    session.thread = NS(is_alive=lambda: False)
    session.core = NS(poll=lambda: 0)
    session.map_guard = NS(recover=lambda: (_ for _ in ()).throw(OSError("synthetic journal busy")))
    instance.session = session
    with pytest.raises(OSError, match="journal busy"):
        instance.command({"type": "shutdown"})
    assert not session.cleanup_complete and not instance.closed
    assert output.getvalue() == ""
    monkeypatch.setattr(session.map_guard, "recover", lambda: None)
    instance.command({"type": "shutdown"})
    assert session.cleanup_complete and instance.closed
    assert json.loads(output.getvalue())["type"] == "stopped"


def test_shutdown_preserves_post_core_writer_and_rejects_stale_session(tmp_path, monkeypatch):
    output = io.StringIO()
    instance = worker.Worker(output)
    session = worker.GameSession(request(tmp_path), instance.emit)
    calls = []
    session.core = NS(poll=lambda: None, wait=lambda timeout: calls.append("core-stop"))
    session.thread = NS(is_alive=lambda: True, join=lambda timeout=None: calls.append(("join", timeout)))
    instance.session = session
    with pytest.raises(ValueError, match="different session"):
        instance.command({"type": "shutdown", "session_id": str(uuid.uuid4())})
    assert calls == [] and not session.cancel_start.is_set()
    instance.command({"type": "shutdown", "session_id": session.session_id})
    assert calls == [("join", 28), "core-stop"]
    assert instance.closed is False
    assert "still finishing" in json.loads(output.getvalue())["message"]


def test_eof_waits_for_post_core_receipt_writer(tmp_path):
    instance = worker.Worker(io.StringIO())
    session = worker.GameSession(request(tmp_path), instance.emit)
    joins = []
    session.core = NS(poll=lambda: 0)
    session.thread = NS(is_alive=lambda: True, join=lambda timeout=None: joins.append(timeout))
    instance.session = session
    assert instance.run(io.StringIO("")) == 0
    assert joins == [28, None]


def test_eof_retries_failed_cleanup_even_after_session_thread_exited(tmp_path, monkeypatch):
    instance = worker.Worker(io.StringIO())
    session = worker.GameSession(request(tmp_path), instance.emit)
    calls = []
    session.thread = NS(is_alive=lambda: False, join=lambda timeout: calls.append("join"))
    session.core = NS(poll=lambda: None, wait=lambda timeout: calls.append("core-stop"))
    original = session.teardown
    def teardown():
        calls.append("cleanup")
        if calls.count("cleanup") == 1:
            raise OSError("synthetic cleanup busy")
        original()
    monkeypatch.setattr(session, "teardown", teardown)
    monkeypatch.setattr(worker.time, "sleep", lambda delay: calls.append(("retry", delay)))
    instance.session = session
    assert instance.run(io.StringIO("")) == 0
    assert instance.closed and session.cleanup_complete
    assert calls.count("cleanup") == 2 and ("retry", 1) in calls
    assert calls.count("core-stop") >= 1
    assert not any(json.loads(line)["type"] == "stopped" for line in instance.output.getvalue().splitlines())
