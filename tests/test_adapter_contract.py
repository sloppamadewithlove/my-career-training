"""High-risk adapter checks against the pinned RLBot v5 wire contract.

The real SDK package is installed only on Windows. Pure relay and packet-shape
checks still run on developer platforms that cannot import its native module.
"""
from __future__ import annotations

import sys
from types import SimpleNamespace as NS
import uuid

import pytest

from my_career_training import adapter, game_worker


def _request(tmp_path):
    return {
        "type": "start",
        "session_id": str(uuid.uuid4()),
        "data_dir": str(tmp_path),
        "fixture": {"id": "adapter-contract"},
        "settings": {"launcher": "steam", "install_path": ""},
    }


def _vec(x=0.0, y=0.0, z=0.0):
    return NS(x=x, y=y, z=z)


def _physics(location, velocity=(0, 0, 0), rotation=(0, 0, 0), angular=(0, 0, 0)):
    return NS(
        location=_vec(*location),
        velocity=_vec(*velocity),
        rotation=NS(pitch=rotation[0], yaw=rotation[1], roll=rotation[2]),
        angular_velocity=_vec(*angular),
    )


def test_connect_uses_the_core_required_close_mode_for_match_managers_and_agents(tmp_path):
    """Core rejects identified agents that set close_between_matches=False."""
    session = game_worker.GameSession(_request(tmp_path), lambda _event: None)
    expected_by_agent_id = {"": False, "my-career-training/team-0": True}

    for agent_id, expected in expected_by_agent_id.items():
        relay = NS(agent_id=agent_id, socket=None, is_connected=False)
        observed = {}

        def connect(**kwargs):
            observed.update(kwargs)

        session.connect(connect, relay, 23999)
        assert observed["close_between_matches"] is expected
        assert observed["rlbot_server_port"] == 23999


def test_normalized_packet_maps_the_sdk_shape_with_small_fake_objects(monkeypatch):
    """Keep the pure adapter usable without importing the Windows native SDK."""
    monkeypatch.setattr(adapter, "flat_module", lambda: NS(AirState=NS(OnGround="ground"), MatchPhase=NS(Kickoff=2)))
    player = NS(
        physics=_physics((1, 2, 3), (4, 5, 6), (0.1, 0.2, 0.3), (7, 8, 9)),
        team=1,
        boost=63.5,
        air_state="ground",
        has_jumped=False,
        has_double_jumped=False,
        has_dodged=False,
        dodge_timeout=1.25,
        is_bot=False,
        dodge_dir=NS(x=0.5, y=-0.5),
        latest_touch=NS(
            game_seconds=4.5,
            location=_vec(10, 11, 12),
            normal=_vec(0, 0, 1),
            ball_index=0,
        ),
        last_input=NS(
            throttle=0.75,
            steer=-0.25,
            pitch=0.1,
            yaw=-0.2,
            roll=0.3,
            jump=True,
            boost=False,
            handbrake=True,
        ),
    )
    ball = NS(physics=_physics((20, 21, 22), (30, 31, 32)))
    packet = NS(
        players=[player],
        boost_pads=[NS(is_active=True)],
        balls=[ball],
        match_info=NS(seconds_elapsed=4.5, frame_num=540, game_speed=1.0, match_phase=3),
    )
    field = NS(boost_pads=[NS(location=_vec(-100, 250, 73), is_full_boost=True)])
    prediction = NS(
        slices=[NS(game_seconds=i / 10, physics=_physics((i, i + 1, i + 2))) for i in range(7)]
    )

    frame = adapter.normalized_packet(packet, prediction, field)

    assert frame["time"] == 4.5
    assert frame["game_time_remaining"] is None
    assert frame["is_unlimited_time"] is None
    assert frame["is_overtime"] is None
    assert frame["frame_num"] == 540
    assert frame["cars"][0]["position"] == [1.0, 2.0, 3.0]
    assert frame["cars"][0]["rotation"] == [0.1, 0.2, 0.3]
    assert frame["cars"][0]["wheel_contact"] is True
    assert frame["cars"][0]["latest_touch"]["position"] == [10.0, 11.0, 12.0]
    assert frame["cars"][0]["dodge_dir"] == [0.5, -0.5]
    assert frame["cars"][0]["actions"] == {
        "throttle": 0.75,
        "steer": -0.25,
        "pitch": 0.1,
        "yaw": -0.2,
        "roll": 0.3,
        "jump": True,
        "boost": False,
        "handbrake": True,
    }
    assert frame["boosts"] == [{"position": [-100.0, 250.0, 73.0], "active": True, "is_full": True}]
    assert frame["ball"]["position"] == [20.0, 21.0, 22.0]
    assert [item["time"] for item in frame["prediction"]] == [0.0, 0.6]


@pytest.mark.skipif(sys.platform != "win32", reason="The pinned RLBot native flatbuffers are Windows-only")
@pytest.mark.parametrize("team_size", [1, 2, 3, 4])
@pytest.mark.parametrize("human_home", [True, False])
def test_match_configuration_roundtrips_human_last_and_maps_bot_indices(team_size, human_home):
    from rlbot import flat
    from my_career_training.career import new_career, next_fixture

    career = new_career("Adapter Contract", format=team_size, seed=101 + team_size)
    fixture = next_fixture(career)
    if not human_home:
        fixture["home"], fixture["away"] = fixture["away"], fixture["home"]
    request = {"fixture": fixture, "settings": {"launcher": "steam"}}

    config, descriptors, human_index = adapter.match_config(request)
    restored = flat.MatchConfiguration.unpack(config.pack())

    assert len(restored.player_configurations) == 2 * team_size
    assert human_index == len(restored.player_configurations) - 1
    assert isinstance(restored.player_configurations[human_index].variety, flat.Human)
    assert set(descriptors) == set(range(human_index))
    assert restored.wait_for_agents is True
    assert restored.auto_start_agents is False
    assert restored.launcher == flat.Launcher.Steam
    assert restored.enable_rendering == flat.DebugRendering.OnByDefault
    assert restored.enable_state_setting is False

    bot_counts = {team: 0 for team in (0, 1)}
    for index, player in enumerate(restored.player_configurations[:-1]):
        assert isinstance(player.variety, flat.CustomBot)
        assert descriptors[index]["team"] == player.team
        bot_counts[player.team] += 1
    expected_human_team = 0 if human_home else 1
    assert restored.player_configurations[human_index].team == expected_human_team
    assert bot_counts[expected_human_team] == team_size - 1
    assert bot_counts[1 - expected_human_team] == team_size


@pytest.mark.skipif(sys.platform != "win32", reason="The pinned RLBot native flatbuffers are Windows-only")
def test_team_hivemind_agent_ids_match_the_controllable_team_mapping(tmp_path):
    from rlbot import flat
    from my_career_training.career import new_career, next_fixture

    fixture = next_fixture(new_career("Adapter Contract", format=4, seed=202))
    config, descriptors, human_index = adapter.match_config(
        {"fixture": fixture, "settings": {"launcher": "steam"}}
    )
    restored = flat.MatchConfiguration.unpack(config.pack())

    ids_by_team = {0: set(), 1: set()}
    for player in restored.player_configurations[:-1]:
        bot = player.variety
        assert isinstance(bot, flat.CustomBot)
        assert bot.hivemind is True
        ids_by_team[player.team].add(bot.agent_id)
    assert all(len(ids) == 1 for ids in ids_by_team.values())
    assert ids_by_team[0].isdisjoint(ids_by_team[1])

    session = game_worker.GameSession(_request(tmp_path), lambda _event: None)
    session.human_index = human_index
    session.descriptors = descriptors
    for team in (0, 1):
        sent = []
        session.relays[team] = NS(send_msg=sent.append)
        indices = [index for index, entry in descriptors.items() if entry["team"] == team]
        info = flat.ControllableTeamInfo(
            team=team,
            controllables=[flat.ControllableInfo(index=index) for index in indices],
        )
        restored_info = flat.ControllableTeamInfo.unpack(info.pack())
        session.map_team(team, restored_info)
        assert len(sent) == 1 and isinstance(sent[0], flat.InitComplete)
        assert session.mapping[team] == indices
        assert human_index not in session.mapping[team]


@pytest.mark.skipif(sys.platform != "win32", reason="The pinned RLBot native flatbuffers are Windows-only")
def test_training_config_and_state_message_roundtrip_the_real_schema():
    from rlbot import flat
    from my_career_training.training.catalog import lesson

    config, descriptors, human_index = adapter.match_config(
        {"lesson_id": "speed-flip", "settings": {"launcher": "epic"}}
    )
    restored_config = flat.MatchConfiguration.unpack(config.pack())
    assert len(restored_config.player_configurations) == 1
    assert isinstance(restored_config.player_configurations[human_index].variety, flat.Human)
    assert descriptors == {}
    assert restored_config.freeplay is False
    assert restored_config.enable_state_setting is True
    assert restored_config.launcher == flat.Launcher.Epic

    state = lesson("speed-flip")["starting_state"]
    desired = adapter.desired_state(state, human_index)
    restored = flat.DesiredGameState.unpack(desired.pack())
    assert len(restored.ball_states) == 1
    assert len(restored.car_states) == human_index + 1
    assert restored.ball_states[0].physics.location.x == state["ball"]["position"][0]
    assert restored.ball_states[0].physics.velocity.z == state["ball"]["velocity"][2]
    assert restored.car_states[human_index].boost_amount == state["car"].get("boost", 100)


@pytest.mark.skipif(sys.platform != "win32", reason="The pinned RLBot native flatbuffers are Windows-only")
def test_worker_outbound_messages_use_the_sdk_interface_packet_framing():
    from rlbot import flat
    from rlbot.interface import SocketRelay
    from rlbot.managers.rendering import Renderer
    from my_career_training.training.catalog import lesson

    class CaptureSocket:
        def __init__(self):
            self.frames = []

        def sendall(self, frame):
            self.frames.append(frame)

        def close(self):
            pass

    relay = SocketRelay("my-career-training/team-0")
    relay.socket = CaptureSocket()
    relay.is_connected = True
    relay.can_render = True
    renderer = Renderer(relay)
    renderer._used_group_ids = set()
    renderer._current_renders = []

    messages = [
        flat.InitComplete(),
        flat.PlayerInput(0, flat.ControllerState(throttle=0.5, steer=-0.25, jump=True)),
        adapter.desired_state(lesson("speed-flip")["starting_state"], 0),
    ]
    for message in messages:
        relay.send_msg(message)
    with renderer.context("adapter-contract"):
        renderer.draw_line_3d(flat.Vector3(0, 0, 0), flat.Vector3(100, 0, 100))

    assert len(relay.socket.frames) == 4
    for message, frame in zip(messages, relay.socket.frames):
        assert int.from_bytes(frame[:2], "big") == len(frame) - 2
        envelope = flat.InterfacePacket.unpack(frame[2:])
        assert isinstance(envelope.message, type(message))
    assert isinstance(flat.InterfacePacket.unpack(relay.socket.frames[-1][2:]).message, flat.RenderGroup)


@pytest.mark.skipif(sys.platform != "win32", reason="The pinned RLBot native flatbuffers are Windows-only")
def test_sdk_game_packet_roundtrip_covers_normalization_and_final_score_gating():
    from rlbot import flat

    human = flat.PlayerInfo(
        physics=flat.Physics(
            location=flat.Vector3(10, 20, 30),
            rotation=flat.Rotator(0.1, 0.2, 0.3),
            velocity=flat.Vector3(40, 50, 60),
            angular_velocity=flat.Vector3(1, 2, 3),
        ),
        air_state=flat.AirState.OnGround,
        is_bot=False,
        team=0,
        boost=75,
        last_input=flat.ControllerState(throttle=0.5, steer=-0.25, jump=True, boost=False),
        dodge_dir=flat.Vector2(0.25, -0.75),
    )
    ball = flat.BallInfo(
        physics=flat.Physics(
            location=flat.Vector3(100, 200, 300),
            velocity=flat.Vector3(400, 500, 600),
            angular_velocity=flat.Vector3(0, 0, 1),
        )
    )
    packet = flat.GamePacket(
        players=[human],
        boost_pads=[flat.BoostPadState(is_active=True)],
        balls=[ball],
        match_info=flat.MatchInfo(
            seconds_elapsed=9.5,
            game_time_remaining=185.5,
            is_unlimited_time=False,
            is_overtime=True,
            frame_num=1140,
            game_speed=1.0,
            match_phase=flat.MatchPhase.Active,
        ),
        teams=[flat.TeamInfo(team_index=0, score=3), flat.TeamInfo(team_index=1, score=1)],
    )
    restored = flat.GamePacket.unpack(packet.pack())

    field = flat.FieldInfo(boost_pads=[flat.BoostPad(location=flat.Vector3(-100, 200, 73), is_full_boost=True)])
    prediction = flat.BallPrediction(
        slices=[
            flat.PredictionSlice(
                game_seconds=i / 10,
                physics=flat.Physics(location=flat.Vector3(i, i + 1, i + 2)),
            )
            for i in range(7)
        ]
    )
    frame = adapter.normalized_packet(restored, prediction, field)

    assert frame["time"] == 9.5
    assert frame["game_time_remaining"] == 185.5
    assert frame["game_time_remaining"] != frame["time"]
    assert frame["is_unlimited_time"] is False
    assert frame["is_overtime"] is True
    assert frame["frame_num"] == 1140
    assert frame["cars"][0]["position"] == [10.0, 20.0, 30.0]
    assert frame["cars"][0]["wheel_contact"] is True
    assert frame["cars"][0]["dodge_dir"] == [0.25, -0.75]
    assert frame["cars"][0]["actions"]["jump"] is True
    assert frame["boosts"] == [{"position": [-100.0, 200.0, 73.0], "active": True, "is_full": True}]
    assert [item["time"] for item in frame["prediction"]] == [0.0, 0.6]
    assert adapter.final_score(restored, seen_active=True) is None

    ended = flat.GamePacket(
        match_info=flat.MatchInfo(match_phase=flat.MatchPhase.Ended),
        teams=restored.teams,
    )
    ended = flat.GamePacket.unpack(ended.pack())
    assert adapter.final_score(ended, seen_active=False) is None
    assert adapter.final_score(ended, seen_active=True) == (3, 1)

    tie = flat.GamePacket(
        match_info=flat.MatchInfo(match_phase=flat.MatchPhase.Ended),
        teams=[flat.TeamInfo(team_index=0, score=2), flat.TeamInfo(team_index=1, score=2)],
    )
    assert adapter.final_score(flat.GamePacket.unpack(tie.pack()), seen_active=True) is None

