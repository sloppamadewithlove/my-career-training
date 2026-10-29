"""A first telemetry packet can follow a floor bounce during a valid reset."""
import copy
import math

import pytest

from my_career_training.training.engine import TrainingEngine
from test_power_shot_scenarios import _frame


def _ready(scenario_id):
    engine = TrainingEngine("power-shots", scenario_id=scenario_id, difficulty="gold")
    for index in range(1, 80):
        engine.update(_frame(engine, index / 120))
        if engine.state == "ready":
            break
    assert engine.state == "ready"
    return engine


def _bounce(engine, elapsed=.04):
    start = engine.lesson["starting_state"]["ball"]
    p, v = start["position"], start["velocity"]
    impact = (v[2] + math.sqrt(v[2]**2 + 1300 * (p[2] - 93.15))) / 650
    assert impact < elapsed
    after = elapsed - impact
    # Synthetic coefficient exercises the verifier; not a claim of measured physics.
    rebound = .6 * (-v[2] + 650 * impact)
    ball = {"position": [p[0]+v[0]*elapsed, p[1]+v[1]*elapsed,
                          93.15 + rebound*after - 325*after*after],
            "velocity": [v[0], v[1], rebound - 650*after]}
    frame = _frame(engine, engine.reset_requested_at + elapsed, setup="starting", ball=ball)
    return frame


@pytest.mark.parametrize("scenario_id", ["left-diagonal-pass", "midfield-cross", "left-cutback"])
def test_first_post_bounce_packet_starts_one_verified_attempt(scenario_id):
    engine = _ready(scenario_id)
    frame = _bounce(engine)
    events = engine.update(frame)
    assert [event["type"] for event in events] == ["go"]
    assert engine.state == "active" and engine.active_elapsed == 0
    assert engine.preparation["ready"]["early_floor_response"] is True
    assert engine.scenario_state["launch_baseline"]["velocity"] == frame["ball"]["velocity"]


@pytest.mark.parametrize("fault", ["parked", "horizontal_velocity", "horizontal_position",
                                  "excess_energy", "small_energy_gain", "height_energy_gain",
                                  "airborne", "wrong_car", "late", "strict"])
def test_bounce_exception_does_not_accept_an_unrelated_or_unapplied_reset(fault):
    engine = _ready("left-diagonal-pass")
    frame = _bounce(engine, .06 if fault == "late" else .04)
    if fault == "parked":
        frame["ball"] = copy.deepcopy(engine.lesson["settle_state"]["ball"])
    elif fault == "horizontal_velocity":
        frame["ball"]["velocity"][0] += 100
    elif fault == "horizontal_position":
        frame["ball"]["position"][0] += 500
    elif fault == "excess_energy":
        frame["ball"]["velocity"][2] = 3000
    elif fault in {"small_energy_gain", "height_energy_gain"}:
        start = engine.lesson["starting_state"]["ball"]
        p, v = start["position"], start["velocity"]
        impact = (v[2] + math.sqrt(v[2]**2 + 1300 * (p[2] - 93.15))) / 650
        after = .04 - impact
        rebound = -v[2] + 650*impact + (7 if fault == "small_energy_gain" else 0)
        frame["ball"]["velocity"][2] = rebound - 650*after
        frame["ball"]["position"][2] = 93.15 + rebound*after - 325*after*after
        if fault == "height_energy_gain":
            frame["ball"]["position"][2] += 20
    elif fault == "airborne":
        frame["ball"]["position"][2] = 350
    elif fault == "wrong_car":
        frame["car"]["position"][0] += 500
    elif fault == "strict":
        engine.strict_capture = True
    assert not engine.update(frame)
    assert engine.state == "ready"
    assert engine.scenario_state.get("launch_baseline") is None


@pytest.mark.parametrize("scenario_id", ["left-diagonal-pass", "lifted-left-feed"])
def test_preimpact_and_upward_launch_still_use_original_confirmation(scenario_id):
    engine = _ready(scenario_id)
    frame = _frame(engine, engine.reset_requested_at + 1/120, setup="starting")
    assert [event["type"] for event in engine.update(frame)] == ["go"]
    assert engine.preparation["ready"]["early_floor_response"] is False


def test_failed_first_launch_snapshot_survives_later_packets_and_clears_on_retry():
    engine = _ready("midfield-cross")
    first = _bounce(engine)
    first["ball"]["velocity"][0] += 170
    first["ball"]["angular_velocity"] = [-1.9, 4.75, 0.0]
    assert not engine.update(first)
    saved = copy.deepcopy(engine.preparation["first_ready"])
    assert saved["observed_ball"]["angular_velocity"] == [-1.9, 4.75, 0.0]
    assert saved["observed_state_applied"] is False
    later = _bounce(engine, .045)
    later["ball"]["velocity"][0] += 175
    later["ball"]["angular_velocity"] = [-2.0, 4.8, 0.0]
    assert not engine.update(later)
    assert engine.preparation["first_ready"] == saved
    assert engine.preparation["ready"]["elapsed"] > saved["elapsed"]
    assert engine.preparation["ready"]["observed_ball"]["angular_velocity"] == [-2.0, 4.8, 0.0]
    engine.reset()
    assert "first_ready" not in engine.preparation


@pytest.mark.parametrize("scenario_id", ["left-diagonal-pass", "midfield-cross", "left-cutback"])
def test_first_floor_packet_accepts_bounded_opposing_friction(scenario_id):
    engine = _ready(scenario_id)
    frame = _bounce(engine)
    velocity = engine.starting_state["ball"]["velocity"]
    normal = frame["ball"]["velocity"][2] - (velocity[2] - 650*.04)
    speed = math.hypot(*velocity[:2])
    for i in range(2):
        frame["ball"]["velocity"][i] -= .355 * normal * velocity[i] / speed
    assert [event["type"] for event in engine.update(frame)] == ["go"]
    assert engine.preparation["ready"]["early_floor_response"] is True


@pytest.mark.parametrize("fault", ["stale_zero", "excess_friction", "wrong_direction", "energy_gain", "strict"])
def test_floor_friction_does_not_accept_unrelated_ball_state(fault):
    engine = _ready("midfield-cross")
    frame = _bounce(engine)
    velocity = engine.starting_state["ball"]["velocity"]
    normal = frame["ball"]["velocity"][2] - (velocity[2] - 650*.04)
    speed = math.hypot(*velocity[:2])
    coefficient = .6 if fault == "excess_friction" else .355
    for i in range(2):
        frame["ball"]["velocity"][i] -= coefficient * normal * velocity[i] / speed
    if fault == "stale_zero":
        frame["ball"]["velocity"] = [0., 0., 0.]
    elif fault == "wrong_direction":
        frame["ball"]["velocity"][0] = velocity[0]
        frame["ball"]["velocity"][1] = velocity[1] - .355*normal
    elif fault == "energy_gain":
        frame["ball"]["velocity"][:2] = [v*1.1 for v in velocity[:2]]
    elif fault == "strict":
        engine.strict_capture = True
    assert not engine.update(frame)
    assert engine.state == "ready"


@pytest.mark.parametrize("excluded", [None, "strict", "airborne", "moving", "tilted"])
def test_ground_launch_uses_verified_settled_height_only(excluded):
    engine = TrainingEngine("power-shots", scenario_id="left-diagonal-pass", difficulty="gold")
    if excluded == "strict":
        engine.strict_capture = True
    elif excluded == "airborne":
        engine.lesson["starting_state"]["car"]["position"][2] = 300
    elif excluded == "moving":
        engine.lesson["starting_state"]["car"]["velocity"][0] = 100
    elif excluded == "tilted":
        engine.lesson["starting_state"]["car"]["rotation"][0] = .3
    engine.reset()
    authored = copy.deepcopy(engine.lesson["starting_state"])
    for index in range(1, 80):
        frame = _frame(engine, index/120)
        frame["frame_num"] = index
        frame["car"]["position"][2] = 17.01
        events = engine.update(frame)
        if engine.state == "ready":
            break
    assert engine.state == "ready"
    expected = copy.deepcopy(authored)
    if excluded is None:
        expected["car"]["position"][2] = 17.01
    assert engine.starting_state == expected
    assert events[0] == {"type": "set_state", "state": expected}
    assert engine.lesson["starting_state"] == authored
    if excluded is None:
        frame = _bounce(engine, 5/120)
        frame["frame_num"] = index + 5
        frame["car"] = {**frame["car"], **copy.deepcopy(expected["car"])}
        assert [event["type"] for event in engine.update(frame)] == ["go"]
    engine.reset()
    assert engine.starting_state == authored
