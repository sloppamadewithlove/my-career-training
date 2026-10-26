"""Development bot-reference capture contracts; no test launches a game."""
from __future__ import annotations

import hashlib
import json
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from my_career_training import adapter, game_worker, reference_capture
from my_career_training.training.bot_reference import SpeedFlipTrialController


def _marker(directory: Path, *, enabled=True, purpose="bot-reference-development", schema=1):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / reference_capture.MARKER_NAME
    path.write_text(json.dumps({"schema": schema, "purpose": purpose, "enabled": enabled}), encoding="utf-8")
    return path


def _capture_request(directory: Path, *, profile="cancel", **changes):
    _marker(directory)
    request = {
        "type": "start",
        "session_id": str(uuid.uuid4()),
        "data_dir": str(directory),
        "owned_game": {"pid": 12345, "created": 1.0, "executable": "RocketLeague.exe"},
        "settings": {"launcher": "steam", "install_path": ""},
        "lesson_id": "speed-flip",
        "reference_capture": {"profile": profile, "trial_id": str(uuid.uuid4())},
    }
    request.update(changes)
    return request


def _enable_profile(directory: Path, monkeypatch):
    monkeypatch.setenv(reference_capture.ENV_PROFILE, str(directory))
    monkeypatch.setattr(sys, "frozen", False, raising=False)


def test_capture_is_disabled_by_default_without_changing_ordinary_requests(tmp_path, monkeypatch):
    monkeypatch.delenv(reference_capture.ENV_PROFILE, raising=False)
    request = {"lesson_id": "speed-flip", "fixture": {"id": "ordinary-career"}}

    assert reference_capture.validate_capture_request(request) is None


def test_unrecognized_capture_flags_cannot_enable_the_reference_path(tmp_path, monkeypatch):
    monkeypatch.delenv(reference_capture.ENV_PROFILE, raising=False)
    request = {
        "lesson_id": "speed-flip",
        "capture_profile": "cancel",
        "capture_trial_id": str(uuid.uuid4()),
        "capture_enabled": True,
    }

    assert reference_capture.validate_capture_request(request) is None


@pytest.mark.parametrize("profile", ["cancel", "baseline"])
def test_capture_request_requires_the_exact_private_source_profile(tmp_path, monkeypatch, profile):
    request = _capture_request(tmp_path, profile=profile)
    _enable_profile(tmp_path, monkeypatch)

    capture = reference_capture.validate_capture_request(request)

    assert capture["profile"] == profile
    assert capture["trial_id"] == request["reference_capture"]["trial_id"]
    assert capture["target_index"] == 0
    assert capture["human_index"] == 1
    assert capture["data_dir"] == str(tmp_path.resolve())
    assert capture["marker_sha256"] == hashlib.sha256(
        (tmp_path / reference_capture.MARKER_NAME).read_bytes()
    ).hexdigest()
    assert capture["label"] == "Development bot trial; not validated"


def test_valid_source_request_does_not_depend_on_sys_frozen_existing(tmp_path, monkeypatch):
    request = _capture_request(tmp_path)
    _enable_profile(tmp_path, monkeypatch)
    monkeypatch.delattr(sys, "frozen", raising=False)

    assert reference_capture.validate_capture_request(request)["target_index"] == 0


def test_frozen_build_and_profile_path_mismatch_refuse_capture(tmp_path, monkeypatch):
    request = _capture_request(tmp_path)
    _enable_profile(tmp_path, monkeypatch)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    with pytest.raises(ValueError):
        reference_capture.validate_capture_request(request)

    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.setenv(reference_capture.ENV_PROFILE, str(tmp_path.parent))
    with pytest.raises(ValueError):
        reference_capture.validate_capture_request(request)


@pytest.mark.parametrize("marker_changes", [
    {"enabled": False},
    {"purpose": "other-development-task"},
    {"schema": 2},
])
def test_missing_or_changed_allow_marker_refuses_capture(tmp_path, monkeypatch, marker_changes):
    request = _capture_request(tmp_path)
    _enable_profile(tmp_path, monkeypatch)
    _marker(tmp_path, **marker_changes)

    with pytest.raises(ValueError):
        reference_capture.validate_capture_request(request)

    (tmp_path / reference_capture.MARKER_NAME).unlink()
    with pytest.raises(ValueError):
        reference_capture.validate_capture_request(request)


@pytest.mark.parametrize("mutation", [
    lambda req: req.update(lesson_id="flick"),
    lambda req: req.update(fixture={"id": "career"}),
    lambda req: req.update(workshop={"id": "workshop"}),
    lambda req: req.update(calibration=True),
    lambda req: req["settings"].update(launcher="epic"),
    lambda req: req.pop("owned_game"),
    lambda req: req["reference_capture"].update(profile="unknown"),
    lambda req: req["reference_capture"].update(trial_id="not-a-canonical-uuid"),
    lambda req: req["reference_capture"].update(fake_capture=True),
    lambda req: req["reference_capture"].update(parameters={"unexpected": 1}),
    lambda req: req["reference_capture"].update(parameters={"timeout_seconds": 1}),
    lambda req: req.update(variants={"side": "left"}),
])
def test_capture_refuses_other_modes_fake_flags_and_nonstandard_setup(tmp_path, monkeypatch, mutation):
    request = _capture_request(tmp_path)
    _enable_profile(tmp_path, monkeypatch)
    mutation(request)

    with pytest.raises(ValueError):
        reference_capture.validate_capture_request(request)


class _Human:
    pass


class _CustomBot:
    def __init__(self, **values):
        self.__dict__.update(values)


class _FlatRecord:
    def __init__(self, **values):
        self.__dict__.update(values)


def _flat_stub():
    return NS(
        Human=_Human,
        CustomBot=_CustomBot,
        PlayerLoadout=_FlatRecord,
        PlayerConfiguration=_FlatRecord,
        MatchConfiguration=_FlatRecord,
        MutatorSettings=_FlatRecord,
        MatchLengthMutator=NS(Unlimited="unlimited", FiveMinutes="five_minutes"),
        MaxScoreMutator=NS(Unlimited="unlimited"),
        OvertimeMutator=NS(Unlimited="unlimited"),
        MultiBallMutator=NS(One="one"),
        BoostAmountMutator=NS(NormalBoost="normal"),
        Launcher=NS(NoLaunch="no_launch", Steam="steam", Epic="epic"),
        GameMode=NS(Soccar="soccar"),
        ExistingMatchBehavior=NS(Restart="restart"),
        DebugRendering=NS(OnByDefault="render"),
        PerformanceMonitor=NS(NeverShow="never"),
    )


def test_capture_match_has_one_known_bot_before_uncontrolled_human(tmp_path, monkeypatch):
    request = _capture_request(tmp_path)
    _enable_profile(tmp_path, monkeypatch)
    monkeypatch.setattr(adapter, "flat_module", _flat_stub)

    config, descriptors, human_index = adapter.match_config(request)

    assert human_index == 1
    assert len(config.player_configurations) == 2
    assert isinstance(config.player_configurations[0].variety, _CustomBot)
    assert isinstance(config.player_configurations[1].variety, _Human)
    assert [player.team for player in config.player_configurations] == [0, 0]
    assert set(descriptors) == {0}
    assert descriptors[0]["capture_trial_id"] == request["reference_capture"]["trial_id"]
    assert {key: descriptors[0][key] for key in ("team", "role", "level", "difficulty", "seed")} == {
        "team": 0, "role": "all-rounder", "level": 1, "difficulty": .5, "seed": 0,
    }
    assert config.player_configurations[0].variety.agent_id == "my-career-training/team-0"
    assert config.launcher == "no_launch"
    assert config.game_map_upk == "Stadium_P"
    assert config.freeplay is True
    assert config.enable_state_setting is True
    assert config.skip_replays is True
    assert config.auto_save_replay is False


def test_normal_training_stays_one_human_and_career_epic_capture_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(adapter, "flat_module", _flat_stub)
    normal, descriptors, human_index = adapter.match_config({
        "lesson_id": "speed-flip",
        "settings": {"launcher": "epic", "install_path": ""},
        "capture_profile": "cancel",
        "capture_enabled": True,
    })
    assert len(normal.player_configurations) == 1
    assert isinstance(normal.player_configurations[human_index].variety, _Human)
    assert descriptors == {}
    assert normal.launcher == "epic"

    request = _capture_request(tmp_path, settings={"launcher": "epic", "install_path": ""})
    _enable_profile(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        adapter.match_config(request)


def test_ordinary_career_epic_layout_still_uses_the_existing_bot_path(monkeypatch):
    from my_career_training import career

    monkeypatch.setattr(adapter, "flat_module", _flat_stub)
    monkeypatch.setattr(career, "bot_runtime_snapshot", lambda _fixture: [{
        "name": "Existing Career Bot", "team": 0, "level": 2, "difficulty": .6, "seed": 9,
        "role": "striker", "loadout": {"car_id": 23, "primary_color": 27, "secondary_color": 0},
    }])

    config, descriptors, human_index = adapter.match_config({
        "fixture": {"id": "career-fixture", "format": 1, "home": "bot", "map": "Stadium_P"},
        "settings": {"launcher": "epic", "install_path": ""},
    })

    assert len(config.player_configurations) == 2
    assert human_index == 1
    assert isinstance(config.player_configurations[0].variety, _CustomBot)
    assert isinstance(config.player_configurations[1].variety, _Human)
    assert config.player_configurations[0].variety.name == "Existing Career Bot"
    assert descriptors == {0: {
        "name": "Existing Career Bot", "team": 0, "level": 2, "difficulty": .6, "seed": 9,
        "role": "striker", "loadout": {"car_id": 23, "primary_color": 27, "secondary_color": 0},
    }}
    assert config.launcher == "epic"


def _capture_worker(tmp_path, monkeypatch, *, human_xy=(0.0, 1000.0), events=None):
    request = _capture_request(tmp_path)
    _enable_profile(tmp_path, monkeypatch)
    session = game_worker.GameSession(request, (events.append if events is not None else lambda _event: None))
    session.capture = reference_capture.validate_capture_request(request)
    session.training_actor_index = 0
    session.human_index = 1
    session.human_team = 0
    session.descriptors = {0: {"team": 0}}
    session.capture_ready = True
    session.mapping = {0: [0]}
    session.capture_controller = SpeedFlipTrialController("cancel")
    session.engine = NS(state="settling", started_at=None)
    session.relays = {}
    session.sent_inputs = []
    flat = NS(
        ControllerState=lambda **actions: NS(**actions),
        PlayerInput=lambda index, controller: NS(index=index, controller=controller),
        InitComplete=lambda: "ready",
        MatchPhase=NS(Active=3, Ended=7),
    )
    monkeypatch.setitem(sys.modules, "rlbot", NS(flat=flat))
    session.relays[0] = NS(send_msg=session.sent_inputs.append)
    frame = {
        "time": 10.0,
        "cars": [
            {"index": 0, "team": 0, "is_bot": True, "position": [0.0, 0.0, 17.0],
             "actions": reference_capture.neutral_actions()},
            {"index": 1, "team": 0, "is_bot": False, "position": [human_xy[0], human_xy[1], 17.0],
             "actions": reference_capture.neutral_actions()},
        ],
    }
    return session, frame, flat


def test_capture_controller_is_neutral_before_go_and_uses_game_time(tmp_path, monkeypatch):
    session, frame, _flat = _capture_worker(tmp_path, monkeypatch)

    before_go = session._capture_actions(frame)
    assert before_go == reference_capture.neutral_actions()

    session.engine.state = "active"
    session.engine.started_at = 10.0
    frame["time"] = 10.36
    actions = session._capture_actions(frame)
    assert actions["throttle"] == 1.0
    assert actions["jump"] is True
    assert actions["boost"] is True


def test_capture_controls_send_only_to_designated_mapped_bot(tmp_path, monkeypatch):
    session, frame, flat = _capture_worker(tmp_path, monkeypatch)
    session.engine.state = "active"
    session.engine.started_at = 10.0

    session._capture_controls(frame, flat)

    assert len(session.sent_inputs) == 1
    assert session.sent_inputs[0].index == 0
    assert not any(message.index == session.human_index for message in session.sent_inputs)


def test_capture_cannot_enable_auto_reset_and_rejects_before_mutating_preferences(tmp_path, monkeypatch):
    session, _frame, _flat = _capture_worker(tmp_path, monkeypatch)
    session.engine.preferences = {"auto_reset": False, "ghost": False}
    changed = []
    session.engine.set_preference = lambda key, value: changed.append((key, value))

    with pytest.raises(ValueError, match="explicit retries"):
        session.handle_command({
            "type": "preferences",
            "preferences": {"auto_reset": True, "explanations": False},
        })

    assert changed == []
    assert session.engine.preferences == {"auto_reset": False, "ghost": False}


def test_capture_controller_receives_mapped_bot_as_primary_frame_car(tmp_path, monkeypatch):
    session, frame, flat = _capture_worker(tmp_path, monkeypatch)
    actual_input = {
        "throttle": .42, "steer": -.1, "pitch": .2, "yaw": -.3, "roll": .4,
        "jump": True, "boost": False, "handbrake": False,
    }
    frame["time"] = 10.4
    frame["cars"][0]["actions"] = actual_input
    seen = {}

    class ControllerSpy:
        def step(self, elapsed_seconds, observed_frame):
            seen["elapsed"] = elapsed_seconds
            seen["frame"] = observed_frame
            return reference_capture.neutral_actions()

    session.capture_controller = ControllerSpy()
    session.engine.state = "active"
    session.engine.started_at = 10.0

    session._capture_controls(frame, flat)

    assert seen["elapsed"] == pytest.approx(.4)
    assert seen["frame"]["car"]["index"] == 0
    assert seen["frame"]["car"]["is_bot"] is True
    assert seen["frame"]["actions"] == actual_input
    assert seen["frame"]["car"]["actions"] == actual_input
    assert session.sent_inputs[0].index == 0


def test_capture_mapping_loss_and_cancellation_fail_closed(tmp_path, monkeypatch):
    session, frame, flat = _capture_worker(tmp_path, monkeypatch)
    session.mapping = {0: [1]}
    session._capture_controls(frame, flat)
    assert session.capture_aborted
    assert session.stopping is True
    assert session.stop_deadline == 0
    assert session.sent_inputs == []

    second, frame, flat = _capture_worker(tmp_path / "second", monkeypatch)
    second.cancel_start.set()
    second._capture_controls(frame, flat)
    assert second.sent_inputs == []


@pytest.mark.parametrize("remove_marker", [False, True])
def test_allow_marker_change_or_removal_stops_capture_before_control(tmp_path, monkeypatch, remove_marker):
    session, frame, flat = _capture_worker(tmp_path, monkeypatch)
    marker = tmp_path / reference_capture.MARKER_NAME
    if remove_marker:
        marker.unlink()
    else:
        _marker(tmp_path, enabled=False)

    session._capture_controls(frame, flat)

    assert session.capture_aborted
    assert session.mapping == {}
    assert session.sent_inputs == []


def test_mapping_change_aborts_capture_instead_of_reusing_stale_bot_mapping(tmp_path, monkeypatch):
    session, frame, flat = _capture_worker(tmp_path, monkeypatch)
    session.map_team(0, NS(team=0, controllables=[NS(index=0)]))
    assert session.capture_ready is True

    with pytest.raises(RuntimeError):
        session.map_team(0, NS(team=0, controllables=[NS(index=1)]))

    session._capture_controls(frame, flat)
    assert session.capture_aborted
    assert session.sent_inputs == ["ready"]


@pytest.mark.parametrize("distance,clear", [(399.0, False), (400.0, True), (401.0, True)])
def test_human_clearance_boundary_is_observed_without_moving_human(tmp_path, monkeypatch, distance, clear):
    session, frame, _flat = _capture_worker(tmp_path, monkeypatch, human_xy=(0, distance))
    assert session._capture_human_clear(frame) is clear
    assert frame["cars"][1]["position"] == [0, distance, 17.0]


def test_retry_state_targets_the_capture_bot_never_the_human(tmp_path, monkeypatch):
    session, _frame, _flat = _capture_worker(tmp_path, monkeypatch)
    from my_career_training import adapter as adapter_module

    states = []
    monkeypatch.setattr(adapter_module, "desired_state", lambda _state, index: states.append(index) or index)
    session.engine.reset = lambda: {"car": {"position": [0, 0, 17]}, "ball": {}}
    session.manager = NS(rlbot_interface=NS(send_msg=lambda value: states.append(value)))

    session.reset()

    assert states[:2] == [0, 0]
    assert session.training_actor_index == 0


@pytest.mark.parametrize("abort_capture", [False, True], ids=["mapping-lost", "already-aborted"])
def test_capture_retry_never_applies_desired_state_after_mapping_loss_or_abort(
    tmp_path, monkeypatch, abort_capture
):
    session, _frame, _flat = _capture_worker(tmp_path, monkeypatch)
    if abort_capture:
        session._abort_capture("synthetic capture abort")
    else:
        session.mapping.clear()
        session.capture_ready = False

    engine_resets, state_messages = [], []
    session.engine.reset = lambda: engine_resets.append(True) or {
        "car": {"position": [0, 0, 17]}, "ball": {},
    }
    session.manager = NS(rlbot_interface=NS(send_msg=state_messages.append))
    monkeypatch.setattr(adapter, "desired_state", lambda _state, index: index)

    try:
        session.reset()
    except RuntimeError as error:
        assert "capture" in str(error).lower() or "mapping" in str(error).lower()

    assert engine_resets == []
    assert state_messages == []


@pytest.mark.parametrize("command", [
    {"type": "ghost_control", "operation": "pause"},
    {"type": "play_recording"},
])
def test_capture_mode_rejects_ghost_practice_and_legacy_playback(tmp_path, monkeypatch, command):
    session, _frame, _flat = _capture_worker(tmp_path, monkeypatch)
    session.coach = NS(pause=lambda: None)
    session.engine = NS()

    with pytest.raises(ValueError, match="capture"):
        session.handle_command(command)


@pytest.mark.parametrize(
    "engine_finished,outcome,expect_candidate",
    [(False, "unfinished", False), (True, "success", True)],
)
def test_attempt_ack_flow_persists_only_a_completed_engine_trial(
    tmp_path, monkeypatch, engine_finished, outcome, expect_candidate
):
    events = []
    session, _frame, _flat = _capture_worker(tmp_path, monkeypatch, events=events)
    attempt_id = str(uuid.uuid4())
    recording = {
        "outcome": "success",  # an imported claim must not complete an unfinished engine attempt
        "samples": [{"time": .1, "position": [0, 0, 17], "actions": {"jump": False}}],
    }
    summary = {"id": attempt_id, "state": "finished" if engine_finished else "active", "outcome": outcome}
    session.engine.finished = engine_finished
    session.engine.summary = lambda: summary
    session.engine.recording = lambda: recording
    session.engine.preferences = {"auto_reset": False}
    session.engine.recorder = NS(metadata={"source": {"kind": "actual_execution", "actor": "bot"}})

    session.publish_attempt()

    candidate_dir = tmp_path / reference_capture.CANDIDATE_DIRECTORY
    candidates = list(candidate_dir.glob("*.json")) if candidate_dir.exists() else []
    assert bool(candidates) is expect_candidate
    if expect_candidate:
        candidate_path = candidate_dir / f"{attempt_id}.json"
        saved = json.loads(candidate_path.read_text(encoding="utf-8"))
        assert saved["summary"]["outcome"] == "success"
        assert saved["recording"]["outcome"] == "success"
        assert saved["gate"] == "not-evaluated"
        assert saved["permission"] == {"distribute": False}
    assert session.attempt_sent == attempt_id
    assert session.attempt_acked is False
    session.handle_command({"type": "attempt_ack", "attempt_id": attempt_id})
    assert session.attempt_acked is True
    assert any(event["type"] == "attempt" for event in events)


def test_packet_capture_records_bot_last_input_not_the_controller_intent(tmp_path, monkeypatch):
    events = []
    session, _unused_frame, flat = _capture_worker(tmp_path, monkeypatch, events=events)
    actual_bot_input = {
        "throttle": .37, "steer": -.12, "pitch": .08, "yaw": .03, "roll": -.04,
        "jump": False, "boost": False, "handbrake": True,
    }
    human_input = {
        "throttle": -.5, "steer": .7, "pitch": 0.0, "yaw": 0.0, "roll": 0.0,
        "jump": True, "boost": True, "handbrake": False,
    }
    bot = {
        "index": 0, "team": 0, "is_bot": True, "position": [11.0, 22.0, 17.0],
        "velocity": [31.0, 42.0, 5.0], "rotation": [.1, .2, .3],
        "angular_velocity": [0.01, .02, .03], "wheel_contact": True, "actions": actual_bot_input,
    }
    human = {
        "index": 1, "team": 0, "is_bot": False, "position": [0.0, 1000.0, 17.0],
        "velocity": [0.0, 0.0, 0.0], "rotation": [0.0, 0.0, 0.0],
        "angular_velocity": [0.0, 0.0, 0.0], "wheel_contact": True, "actions": human_input,
    }
    frame = {
        "time": 10.36, "frame_num": 1243, "game_speed": 1.0,
        "cars": [bot, human],
        "ball": {"position": [100.0, 200.0, 300.0], "velocity": [0.0, 0.0, 0.0]},
    }
    monkeypatch.setattr(adapter, "normalized_packet", lambda *_args: dict(frame, cars=[bot, human]))
    session._discover_game = lambda: None
    session.game_version = "synthetic-game-build"
    session.capture_arena = "Stadium_P"
    session.capture_metadata = {
        "kind": "actual_execution", "actor": "bot", "actor_index": 0,
        "origin": "project-controlled offline bot", "profile": "cancel",
        "trial_id": session.capture["trial_id"], "permission": {"distribute": False},
    }
    session.engine = NS(
        state="active", started_at=10.0, metadata={}, recorder=NS(metadata={
            "source": {"kind": "local_player", "origin": "Observed human game telemetry"},
            "permission": {"distribute": False, "basis": "Private player recording"},
        }),
        preferences={}, finished=False,
        update=lambda observed: observed_frames.append(observed) or [],
        summary=lambda: {"coaching": {}},
        tolerances={"max_packet_interval": 0.05},
    )
    observed_frames = []
    session.applied_reset = True
    session.renderer = NS(can_render=False)
    session.last_controls = float("-inf")
    session.last_telemetry = float("-inf")
    player_template = NS(
        hitbox=NS(length=118.0, width=84.0, height=36.0),
        hitbox_offset=NS(x=0.0, y=0.0, z=20.0),
    )
    packet = NS(
        match_info=NS(match_phase=flat.MatchPhase.Active),
        players=[player_template, player_template], teams=[],
    )

    session.process_packet(packet)

    assert len(observed_frames) == 1
    observed = observed_frames[0]
    assert observed["car"]["index"] == 0
    assert observed["car"]["position"] == [11.0, 22.0, 17.0]
    assert observed["actions"] == actual_bot_input
    assert observed["actions"] != session.sent_inputs[0].controller.__dict__
    assert len(session.sent_inputs) == 1 and session.sent_inputs[0].index == 0
    telemetry_event = next(event for event in events if event["type"] == "telemetry")
    assert telemetry_event["car"]["index"] == 1
    assert telemetry_event["actions"] == human_input
    assert telemetry_event["reference_capture"]["target_index"] == 0
    assert "not validated" in telemetry_event["reference_capture"]["label"].lower()
    metadata_text = json.dumps(session.engine.recorder.metadata).lower()
    for private_key in ("data_dir", "owned_game", "executable", "pid", "account_id", "api_key"):
        assert private_key not in metadata_text
    source = session.engine.recorder.metadata["source"]
    assert source["kind"] == "actual_execution"
    assert source["actor"] == "bot"
    assert source["origin"] == "project-controlled offline bot"
    assert session.engine.recorder.metadata["permission"]["distribute"] is False
    assert session.engine.recorder.metadata["map"] == "Stadium_P"
    assert session.engine.recorder.metadata["framework_version"] == adapter.SDK_VERSION
    assert session.engine.recorder.metadata["game_version"] == "synthetic-game-build"
    assert session.engine.recorder.metadata["observed_game_speed"] == 1.0
    assert session.engine.recorder.metadata["car_hitbox"]["dimensions"] == [118.0, 84.0, 36.0]


def test_human_entering_capture_corridor_aborts_before_any_bot_input(tmp_path, monkeypatch):
    events = []
    session, frame, flat = _capture_worker(tmp_path, monkeypatch, events=events)
    frame.update(time=10.36, frame_num=1243, game_speed=1.0, ball={"position": [0, 0, 93]})
    frame["cars"][1]["position"] = [0.0, reference_capture.HUMAN_CLEARANCE - 1, 17.0]
    monkeypatch.setattr(adapter, "normalized_packet", lambda *_args: frame)
    session._discover_game = lambda: None
    session.capture_arena = "Stadium_P"
    session.engine = NS(
        state="active", started_at=10.0, metadata={}, recorder=NS(metadata={}),
        preferences={}, finished=False, update=lambda _frame: [], summary=lambda: {"coaching": {}},
        tolerances={"max_packet_interval": 0.05},
    )
    session.applied_reset = True
    session.renderer = NS(can_render=False)
    session.last_controls = float("-inf")
    session.last_telemetry = float("-inf")
    hitbox = NS(length=118.0, width=84.0, height=36.0)
    offset = NS(x=0.0, y=0.0, z=20.0)
    packet = NS(match_info=NS(match_phase=flat.MatchPhase.Active),
                players=[NS(hitbox=hitbox, hitbox_offset=offset)] * 2, teams=[])

    session.process_packet(packet)

    assert session.capture_aborted
    assert session.stopping is True
    assert session.mapping == {}
    assert not any(hasattr(message, "index") for message in session.sent_inputs)
    assert not (tmp_path / reference_capture.CANDIDATE_DIRECTORY).exists()


def test_candidate_persistence_is_private_atomic_and_never_marks_permission_or_gate_passed(tmp_path):
    trial_id = str(uuid.uuid4())
    attempt_id = str(uuid.uuid4())
    capture = {
        "trial_id": trial_id,
        "profile": "cancel",
        "label": reference_capture.LABEL,
        "provenance": reference_capture.PROVENANCE_LABEL,
    }
    recording = {"outcome": "success", "samples": [{"time": 0.1, "actions": {"jump": False}}]}

    receipt = reference_capture.persist_candidate(
        tmp_path, capture, attempt_id, recording, {"outcome": "success"},
        {"source": {"kind": "actual_execution", "actor": "bot"}},
    )

    root = tmp_path / reference_capture.CANDIDATE_DIRECTORY
    candidate_path = root / f"{attempt_id}.json"
    receipt_path = root / f"{attempt_id}.receipt.json"
    candidate_bytes = candidate_path.read_bytes()
    candidate = json.loads(candidate_bytes)
    saved_receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt == saved_receipt
    assert saved_receipt["sha256"] == hashlib.sha256(candidate_bytes).hexdigest()
    assert candidate["recording"] == recording
    assert candidate["trial_id"] == trial_id
    assert candidate["attempt_id"] == attempt_id
    assert candidate["permission"] == {"distribute": False}
    assert candidate["gate"] == "not-evaluated"
    assert not list(root.glob("*.tmp")) and not list(root.glob(".*.tmp"))


def test_candidate_persistence_refuses_empty_synthetic_recording(tmp_path):
    capture = {"trial_id": str(uuid.uuid4()), "profile": "cancel", "label": "trial", "provenance": "unvalidated"}
    with pytest.raises(ValueError):
        reference_capture.persist_candidate(tmp_path, capture, str(uuid.uuid4()), {"samples": []}, {}, {})


def test_candidate_persistence_enforces_existing_recording_byte_bound(tmp_path):
    from my_career_training.training.recordings import MAX_RECORDING_BYTES

    capture = {"trial_id": str(uuid.uuid4()), "profile": "cancel", "label": "trial", "provenance": "unvalidated"}
    attempt_id = str(uuid.uuid4())
    recording = {"samples": [{"oversized": "x" * (MAX_RECORDING_BYTES + 1)}]}

    with pytest.raises(ValueError):
        reference_capture.persist_candidate(tmp_path, capture, attempt_id, recording, {}, {})

    candidate_dir = tmp_path / reference_capture.CANDIDATE_DIRECTORY
    assert not list(candidate_dir.glob("*.json"))
    assert not list(candidate_dir.glob(".*.tmp"))


def test_configuration_snapshot_uses_the_local_rlbot_sdk_enum_names(tmp_path, monkeypatch):
    pytest.importorskip("rlbot.flat")
    from my_career_training.training.bot_reference import CAPTURE_CONFIGURATION

    request = _capture_request(tmp_path)
    _enable_profile(tmp_path, monkeypatch)
    config, _descriptors, _human_index = adapter.match_config(request)

    snapshot = reference_capture.configuration_snapshot(config)

    assert snapshot == CAPTURE_CONFIGURATION
    assert snapshot["game_mode"] == "Soccar"
    assert snapshot["mutators"]["match_length"] == "Unlimited"
    assert snapshot["mutators"]["boost_amount"] == "NormalBoost"


def _fake_ack_configuration(*, match_length="Unlimited"):
    class CustomBot:
        name = "Development Capture Bot"
        agent_id = "my-career-training/team-0"

    class Human:
        pass

    return NS(
        game_map_upk="Stadium_P",
        game_mode="GameMode.Soccar",
        freeplay=True,
        mutators=NS(
            game_speed="GameSpeed.Default",
            gravity="Gravity.Default",
            boost_amount="BoostAmountMutator.NormalBoost",
            match_length=f"MatchLengthMutator.{match_length}",
            max_score="MaxScoreMutator.Unlimited",
            multi_ball="MultiBallMutator.One",
            overtime="OvertimeMutator.Unlimited",
        ),
        player_configurations=[
            NS(team=0, variety=CustomBot()),
            NS(team=0, variety=Human()),
        ],
    )


def _capture_handshake_session(tmp_path, expected_config):
    session = game_worker.GameSession(_capture_request(tmp_path), lambda _event: None)
    session.capture = {"profile": "cancel"}
    session.capture_configuration = reference_capture.configuration_snapshot(expected_config)
    master = NS(match_config_handlers=[])
    session.core = NS(poll=lambda: None)
    session.manager = NS(rlbot_interface=master)
    return session, master


def test_capture_match_ack_rejects_same_roster_with_wrong_mutator(tmp_path):
    expected = _fake_ack_configuration()
    received = _fake_ack_configuration(match_length="FiveMinutes")
    session, master = _capture_handshake_session(tmp_path, expected)

    def start_match(_config, **_kwargs):
        for handler in list(master.match_config_handlers):
            handler(received)

    session.manager.start_match = start_match

    with pytest.raises(RuntimeError, match="acknowledge"):
        session.start_acknowledged_match(expected, timeout=0)

    assert session.capture_configuration_ack is None
    assert master.match_config_handlers == []


def test_capture_match_ack_accepts_the_exact_requested_configuration(tmp_path):
    expected = _fake_ack_configuration()
    session, master = _capture_handshake_session(tmp_path, expected)

    def start_match(_config, **_kwargs):
        for handler in list(master.match_config_handlers):
            handler(expected)

    session.manager.start_match = start_match

    session.start_acknowledged_match(expected, timeout=0)

    assert session.capture_configuration_ack == session.capture_configuration
    assert master.match_config_handlers == []


def test_capture_setup_disables_a_saved_auto_reset_preference_and_records_owned_game_version(
    tmp_path, monkeypatch
):
    from my_career_training import map_guard

    request = _capture_request(tmp_path)
    request.update(lesson_id="speed-flip", preferences={"auto_reset": True})
    _enable_profile(tmp_path, monkeypatch)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(game_worker, "preflight", lambda _owned=None: None)
    monkeypatch.setattr(game_worker, "core_path", lambda: Path("verified-runtime.exe"))
    monkeypatch.setattr(game_worker, "free_port", lambda: 24123)
    monkeypatch.setattr(game_worker, "game_file_version", lambda _executable: "test-owned-game-version")
    monkeypatch.setattr(map_guard, "MapGuard", lambda _directory: NS(recover=lambda: None))

    class Relay:
        def __init__(self, agent_id="", **_kwargs):
            self.agent_id = agent_id
            self.socket = None
            self.is_connected = False

        def connect(self, **_kwargs):
            self.is_connected = True

        def send_msg(self, _message):
            pass

    class Manager:
        def __init__(self, _executable):
            self.rlbot_interface = Relay()

        def connect(self, **_kwargs):
            pass

        def start_match(self, config, **_kwargs):
            for handler in list(self.rlbot_interface.match_config_handlers):
                handler(config)

    fake_config = _fake_ack_configuration()
    monkeypatch.setattr(adapter, "match_config", lambda _request: (
        fake_config, {0: {"team": 0, "role": "all-rounder", "level": 1,
                         "difficulty": .5, "seed": 0}}, 1,
    ))
    monkeypatch.setitem(sys.modules, "rlbot", NS(flat=NS()))
    monkeypatch.setitem(sys.modules, "rlbot.interface", NS(SocketRelay=Relay))
    monkeypatch.setitem(sys.modules, "rlbot.managers.match", NS(MatchManager=Manager))
    monkeypatch.setitem(sys.modules, "rlbot.managers.rendering", NS(Renderer=lambda _relay: NS()))

    session = game_worker.GameSession(request, lambda _event: None)
    session.core = NS(poll=lambda: None)
    monkeypatch.setattr(session, "spawn_core", lambda _runtime, _port: Path("verified-runtime.exe"))
    monkeypatch.setattr(session, "connect", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(session, "_relay_thread", lambda _relay: None)

    session.setup()

    assert request["preferences"]["auto_reset"] is True  # the saved request itself is untouched
    assert session.engine.preferences["auto_reset"] is False
    assert session.game_version == "test-owned-game-version"
