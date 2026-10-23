import copy
import math

import pytest

from my_career_training.training import (
    TrainingEngine,
    assistance_preferences,
    catalog,
    compatible_recordings,
    configure_lesson,
    ghost_lines,
    import_recording,
    interpolate_pose,
    personal_best,
    validate_recording,
)
from my_career_training.training.recordings import Recorder


def frame(t, position=(0, -2500, 17.01), ball=(0, 0, 93.15), **changes):
    value = {
        "time": t,
        "dt": 1 / 120,
        "car": {
            "position": list(position),
            "rotation": [0, math.pi / 2, 0],
            "velocity": [0, 0, 0],
            "angular_velocity": [0, 0, 0],
            "boost": 100,
            "wheel_contact": True,
            "has_jumped": False,
            "has_double_jumped": False,
            "has_dodged": False,
            "dodge_timeout": -1,
            "air_state": "OnGround",
        },
        "ball": {"position": list(ball), "velocity": [0, 0, 0]},
        "actions": {
            "throttle": 0.0,
            "steer": 0.0,
            "pitch": 0.0,
            "yaw": 0.0,
            "roll": 0.0,
            "jump": False,
            "boost": False,
            "handbrake": False,
        },
        "packet_gap": False,
    }
    for key, item in changes.items():
        if key in ("car", "ball", "actions"):
            value[key].update(item)
        else:
            value[key] = item
    return value


def activate(engine):
    position = engine.lesson["settle_state"]["car"]["position"]
    for i in range(35):
        events = engine.update(frame(i / 120, position))
        if engine.state == "ready":
            break
    assert events[0]["type"] == "set_state"
    start = engine.starting_state
    t = (i + 1) / 120
    first = frame(t, start["car"]["position"], start["ball"]["position"])
    first["ball"]["velocity"] = start["ball"]["velocity"]
    result = engine.update(first)
    assert result[0]["type"] == "go"
    return t


def test_all_eight_catalog_entries_have_reset_and_honest_reference_boundary():
    lessons = catalog()
    assert len(lessons) == 8 and len({x["id"] for x in lessons}) == 8
    for entry in lessons:
        assert entry["success_events"] and entry["steps"] and entry["settle_state"]
        assert entry["reference_recordings"] == []
        assert len(entry["assistance_defaults"]) == 6
    lessons[0]["steps"].clear()
    assert catalog()[0]["steps"]


def test_help_preferences_independent_and_validated():
    prefs = assistance_preferences({"ghost": False, "explanations": False, "playback_speed": 0.5})
    changed = assistance_preferences({**prefs, "explanations": True})
    assert changed["ghost"] is False and changed["playback_speed"] == 0.5
    with pytest.raises(ValueError):
        assistance_preferences({"actions": "false"})
    with pytest.raises(ValueError):
        assistance_preferences({"playback_speed": float("nan")})


def test_settle_waits_for_clean_jump_state_and_restarts_after_gap():
    engine = TrainingEngine("speed-flip")
    for i in range(60):
        engine.update(frame(i / 120, car={"has_dodged": True}))
    assert engine.state == "settling"
    engine.reset()
    for i in range(20):
        engine.update(frame(i / 120))
    engine.update(frame(0.5, packet_gap=True))
    for i in range(1, 20):
        engine.update(frame(0.5 + i / 120))
    assert engine.state == "settling"
    for i in range(20, 40):
        engine.update(frame(0.5 + i / 120))
        if engine.state == "ready":
            break
    assert engine.state == "ready"


def test_reset_application_must_be_observed_and_retry_clears_previous_edges():
    engine = TrainingEngine("power-shots")
    for i in range(35):
        engine.update(frame(i / 120, engine.lesson["settle_state"]["car"]["position"], (3000, 0, 93.15)))
        if engine.state == "ready":
            break
    assert engine.state == "ready"
    engine.update(frame(3, (3000, 0, 17.01)))
    assert engine.outcome == "interrupted"
    engine.reset()
    assert engine.events == [] and engine.recording()["samples"] == [] and engine.state == "settling"


def test_duplicate_and_restarted_clocks_do_not_invent_actions():
    engine = TrainingEngine("speed-flip")
    t = activate(engine)
    engine.update(frame(t + 0.01, actions={"jump": True}, car={"has_jumped": True}))
    count = len(engine.events)
    engine.update(frame(t + 0.01, actions={"jump": False}))
    assert len(engine.events) == count
    engine.update(frame(t - 0.1))
    assert engine.outcome == "interrupted"


def test_speed_flip_passes_only_with_technique_before_crossing_and_recovery():
    engine = TrainingEngine("speed-flip")
    # Short fixture isolates the sequence without teleporting across a full arena.
    engine.lesson["starting_state"]["car"]["position"] = [0, -40, 17.01]
    engine.lesson["settle_state"]["car"]["position"] = [0, -40, 17.01]
    engine.reset()
    t = activate(engine)
    engine.update(
        frame(
            t + 0.02,
            position=(0, -35, 25),
            car={"wheel_contact": False, "air_state": "Jumping", "has_jumped": True},
            actions={"jump": True, "boost": True},
        )
    )
    engine.update(
        frame(
            t + 0.04,
            position=(0, -30, 35),
            car={"wheel_contact": False, "air_state": "Dodging", "has_jumped": True, "has_dodged": True},
            actions={"pitch": -1.0, "yaw": 0.5, "boost": True},
        )
    )
    engine.update(
        frame(
            t + 0.06,
            position=(0, -20, 40),
            car={"wheel_contact": False, "air_state": "Dodging", "has_jumped": True, "has_dodged": True},
            actions={"pitch": 1.0, "boost": True},
        )
    )
    assert engine.outcome != "success"
    engine.update(frame(t + 0.08, position=(0, -10, 17.01)))
    assert "landed" in engine._emitted and engine.outcome != "success"
    engine.update(frame(t + 0.10, position=(0, 10, 17.01)))
    assert engine.outcome == "success"
    assert engine.summary()["metrics"]["crossing_seconds"] == pytest.approx(0.09)


def reset_contact_case(*, consumed=True, gap=False, near_surface=False, touch=True):
    engine = TrainingEngine("flip-reset")
    t = activate(engine)
    height = 200 if near_surface else 800
    pose = {
        "position": [0, 0, height],
        "rotation": [0, 0, math.pi],
        "wheel_contact": False,
        "air_state": "InAir",
    }
    engine.update(frame(t + 0.01, car={**pose, "has_jumped": True}))
    if consumed:
        engine.update(
            frame(
                t + 0.02,
                car={**pose, "air_state": "Dodging", "has_jumped": True, "has_dodged": True},
                actions={"pitch": -1.0},
            )
        )
    contact = {
        "game_seconds": t + 0.03,
        "location": [0, 0, height + 40],
        "normal": [0, 0, 1],
        "ball_index": 0,
    }
    engine.update(
        frame(
            t + 0.03,
            ball=(0, 0, height + 130),
            car={**pose, "latest_touch": contact if touch else None},
            packet_gap=gap,
        )
    )
    return engine


def test_flip_reset_requires_spent_flip_touch_clear_surface_and_continuous_packets():
    assert reset_contact_case().outcome == "success"
    for options in ({"consumed": False}, {"gap": True}, {"near_surface": True}, {"touch": False}):
        result = reset_contact_case(**options)
        assert result.outcome != "success", options
        assert "reset_acquired" not in result._emitted


def test_airborne_reset_available_at_start_is_not_acquisition():
    engine = TrainingEngine("flip-reset")
    t = activate(engine)
    for i in range(1, 5):
        engine.update(
            frame(
                t + i / 120,
                ball=(0, 0, 930),
                car={
                    "position": [0, 0, 800],
                    "rotation": [0, 0, math.pi],
                    "wheel_contact": False,
                    "air_state": "InAir",
                    "latest_touch": {"game_seconds": t + i / 120},
                },
            )
        )
    assert "reset_acquired" not in engine._emitted


def test_carry_dwell_cannot_bridge_telemetry_gap():
    engine = TrainingEngine("dribble-flick")
    t = activate(engine)
    for i in range(1, 150):
        engine.update(frame(t + i / 120, position=(0, 0, 17), ball=(0, 0, 150)))
    assert engine.carry_streak > 1
    engine.update(frame(t + 1.5, position=(0, 0, 17), ball=(0, 0, 150), packet_gap=True))
    assert engine.carry_streak == 0
    assert "carry_sustained" not in engine._emitted


def test_gates_are_ordered_and_goal_location_interpolates_observed_samples():
    engine = TrainingEngine("aerial-air-roll")
    t = activate(engine)
    engine.update(frame(t + 0.01, position=(700, 0, 850), car={"wheel_contact": False}))
    assert engine.metrics["gates"] == 0
    engine.update(frame(t + 0.02, position=(0, -1000, 500), car={"wheel_contact": False}))
    assert engine.metrics["gates"] == 1
    shot = TrainingEngine("shot-placement")
    t = activate(shot)
    shot.update(frame(t + 0.01, ball=(400, 5000, 300), car={"latest_touch": {"game_seconds": t + 0.01}}))
    shot.update(frame(t + 0.02, ball=(560, 5240, 400)))
    assert shot.outcome == "success"
    assert shot.metrics["shot_location"] == pytest.approx([480, 5120, 350])


def recording():
    entry = catalog()[0]
    recorder = Recorder(
        entry, {"game_version": "test-game", "framework_version": "test-core", "car_hitbox": "octane"}
    )
    recorder.append(frame(0))
    recorder.append(frame(1 / 120, position=(0, -2490, 17)))
    return recorder.export(
        outcome="success", events=[{"name": "target_crossed", "confidence": "observed"}], duration=1
    )


def test_recording_bound_import_rejection_and_private_provenance(tmp_path):
    recorder = Recorder(catalog()[0], max_samples=2)
    for i in range(5):
        recorder.append(frame(i / 120))
    assert len(recorder.samples) == 2 and recorder.truncated
    value = recording()
    assert validate_recording(value) == []
    with pytest.raises(ValueError, match="actual successful"):
        validate_recording(value, require_reference=True)
    value["samples"][1]["time"] = value["samples"][0]["time"]
    with pytest.raises(ValueError, match="increase"):
        validate_recording(value)
    path = tmp_path / "bad recording.json"
    path.write_text('{"schema_version": 500}', encoding="utf-8")
    original = path.read_bytes()
    with pytest.raises(ValueError):
        import_recording(path)
    assert path.read_bytes() == original


def test_personal_bests_require_compatibility_and_never_become_expert():
    candidate = recording()
    old = copy.deepcopy(candidate)
    old["duration"] = 0.5
    assert personal_best([old], candidate)["label"] == "Your Best Attempt"
    assert personal_best([old], candidate)["duration"] == 0.5
    old["metadata"]["game_version"] = "different-game"
    assert not compatible_recordings(old, candidate)[0]
    assert personal_best([old], candidate)["duration"] == 1
    candidate["metadata"]["game_version"] = "unknown"
    assert personal_best([], candidate) is None


def test_pose_interpolation_wraps_yaw_and_does_not_bridge_gaps():
    value = recording()
    value["samples"][0]["rotation"] = [0, math.pi - 0.01, 0]
    value["samples"][1]["rotation"] = [0, -math.pi + 0.01, 0]
    pose = interpolate_pose(value, 1 / 240)
    lines = ghost_lines(pose)
    assert len(lines) >= 18
    front = next(x for x in lines if x["style"] == "front")
    # The halfway nose still points toward negative x, not across a 360-degree spin.
    assert front["end"][0] < front["start"][0]
    assert {line["style"] for line in lines} == {"outline", "front", "roof", "underside"}
    assert interpolate_pose(value, 1 / 240, speed=0.5)["time"] == pytest.approx(1 / 480)
    value["samples"][1]["packet_gap"] = True
    assert interpolate_pose(value, 1 / 240) is None
    assert interpolate_pose(value, 10) is None


def test_variants_are_explicit_and_do_not_change_physics():
    standard = configure_lesson("flip-reset")
    short = configure_lesson("flip-reset", simplified=True)
    assert short["starting_state"] != standard["starting_state"]
    assert short["starting_state"]["game_speed"] == 1
    mirrored = configure_lesson("aerial-air-roll", side="left")
    assert mirrored["targets"][1]["position"][0] == -700


def test_global_ball_touch_is_not_misattributed_to_human_reset():
    engine = TrainingEngine("flip-reset")
    t = activate(engine)
    engine.update(
        frame(
            t + 0.01,
            car={"position": [0, 0, 800], "wheel_contact": False, "air_state": "Dodging", "has_dodged": True},
            actions={"pitch": -1.0},
        )
    )
    f = frame(
        t + 0.02,
        ball=(0, 0, 930),
        car={
            "position": [0, 0, 800],
            "rotation": [0, 0, math.pi],
            "wheel_contact": False,
            "air_state": "InAir",
            "player_index": 0,
        },
    )
    f["ball"]["latest_touch"] = {"game_seconds": t + 0.02, "player_index": 1}
    engine.update(f)
    assert "ball_contact" not in engine._emitted and "reset_acquired" not in engine._emitted


def test_runtime_slow_motion_cannot_become_normal_speed_personal_best():
    value = recording()
    value["samples"][1]["game_speed"] = 0.5
    assert personal_best([], value) is None


def test_event_timing_comparison_reports_sampling_uncertainty_without_failure_grade():
    from my_career_training.training import compare_attempts

    first, second = recording(), recording()
    first["events"] = [
        {"name": "opposing_pitch", "time": 0.05, "precision": [0.04, 0.05], "confidence": "observed"}
    ]
    second["events"] = [
        {"name": "opposing_pitch", "time": 0.045, "precision": [0.035, 0.045], "confidence": "observed"}
    ]
    result = compare_attempts(first, second)
    assert result["timing"][0]["observation"] == "Within sampling uncertainty"
    assert result["timing"][0]["difference_interval"] == pytest.approx([-0.005, 0.015])
    assert "grade" not in result


@pytest.mark.parametrize("duration", [-1, float("nan"), float("inf"), True])
def test_recording_duration_must_be_a_finite_nonnegative_number(duration):
    value = recording()
    value["duration"] = duration
    with pytest.raises(ValueError, match="duration"):
        validate_recording(value)
    assert personal_best([], value) is None


def test_ready_rotation_check_handles_equivalent_wrapped_orientation():
    engine = TrainingEngine("speed-flip")
    for index in range(50):
        engine.update(frame(index / 120))
        if engine.state == "ready":
            break
    start = engine.starting_state
    packet = frame(engine.reset_requested_at + 0.01, start["car"]["position"], start["ball"]["position"])
    packet["car"]["rotation"][1] += 2 * math.pi
    assert engine.update(packet)[0]["type"] == "go"
