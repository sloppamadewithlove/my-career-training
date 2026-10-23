"""Adversarial persistence and drill cases with no Rocket League runtime claims."""
from __future__ import annotations

import math

import pytest

from my_career_training import career as rules
from my_career_training.training import TrainingEngine, catalog, personal_best, validate_recording
from my_career_training.training.recordings import Recorder


def _play_next(career, home_score=3, away_score=1):
    fixture = rules.next_fixture(career)
    session_id = f"test:{fixture['id']}"
    pending = rules.start_fixture(career, session_id)
    return rules.complete_fixture(pending, fixture["id"], session_id, home_score, away_score)


def _frame(time, position, ball_position, *, car=None, ball=None, actions=None, packet_gap=False):
    value = {
        "time": time,
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
            "air_state": "OnGround",
        },
        "ball": {"position": list(ball_position), "velocity": [0, 0, 0]},
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
        "packet_gap": packet_gap,
    }
    value["car"].update(car or {})
    value["ball"].update(ball or {})
    value["actions"].update(actions or {})
    return value


def _ready(engine):
    settle_position = engine.lesson["settle_state"]["car"]["position"]
    for index in range(50):
        engine.update(_frame(index / 120, settle_position, (3000, 0, 93.15)))
        if engine.state == "ready":
            break
    assert engine.state == "ready"
    return engine.reset_requested_at


def _confirmed_start_packet(engine, elapsed=0.01):
    target = engine.starting_state
    ball = target["ball"]
    expected_ball = [p + v * elapsed for p, v in zip(ball["position"], ball["velocity"])]
    expected_ball[2] -= 325 * elapsed * elapsed
    packet = _frame(
        engine.reset_requested_at + elapsed,
        target["car"]["position"],
        expected_ball,
        car=target["car"],
        ball=ball,
    )
    return packet


def _valid_local_recording():
    recorder = Recorder(
        catalog()[0],
        {"game_version": "test-game", "framework_version": "test-core", "car_hitbox": "octane"},
    )
    for time in (0.0, 1 / 120):
        recorder.append(_frame(time, (0, -2500, 17), (0, 0, 93)))
    return recorder.export(
        outcome="success",
        events=[{"name": "target_crossed", "confidence": "observed", "time": 0.01}],
        duration=0.01,
    )


def test_two_format_swaps_preserve_completed_snapshots_and_update_only_future_rounds():
    state = rules.new_career("Mode History", format=3, seed=602)
    state = _play_next(state)
    state = rules.set_format(state, 1)
    state = _play_next(state)
    state = rules.set_format(state, 4)

    by_round = {
        f["round"]: f
        for f in state["seasons"][0]["fixtures"]
        if "human" in (f["home"], f["away"])
    }
    assert (by_round[1]["format"], by_round[1]["lineup"]) == (3, ["anchor", "shield"])
    assert (by_round[2]["format"], by_round[2]["lineup"]) == (1, [])
    assert all((by_round[r]["format"], len(by_round[r]["lineup"])) == (4, 3) for r in range(3, 7))
    assert by_round[1]["result"]["format"] == 3
    assert by_round[2]["result"]["format"] == 1
    assert [item["format"] for item in state["seasons"][0]["settings_history"]] == [3, 1, 4]
    assert rules.validate_career(state)


def test_import_rejects_global_format_that_disagrees_with_all_unstarted_fixtures():
    forged = rules.new_career("Forged Mode", format=3, seed=603)
    forged["format"] = 4
    forged["lineup"] = forged["squad"][:3]

    with pytest.raises(ValueError):
        rules.validate_career(forged)


def test_three_nonhuman_tie_resolves_seeded_playoffs_without_simulating_a_human_fixture(monkeypatch):
    def simulate(_season, fixture):
        assert "human" not in (fixture["home"], fixture["away"])
        fixture["session_id"] = f"sim:{fixture['seed']}"
        fixture["result"] = rules._result(fixture, fixture["session_id"], 1, 0, "simulated")
        fixture["status"] = "completed"

    monkeypatch.setattr(rules, "_simulate", simulate)
    state = rules.new_career("Fourth Place", seed=604)
    for _ in range(6):
        fixture = rules.next_fixture(state)
        if fixture["home"] == "human":
            score = (0, 1)
        else:
            score = (1, 0)
        pending = rules.start_fixture(state, f"real:{fixture['id']}")
        state = rules.complete_fixture(pending, fixture["id"], f"real:{fixture['id']}", *score)

    season = state["seasons"][0]
    assert set(season["title_contenders"]) == {"aurora", "cinder", "tidal"}
    assert all("human" not in (f["home"], f["away"]) for f in season["playoffs"])
    assert all(f["status"] == "completed" and f["result"]["simulated"] for f in season["playoffs"])
    assert season["champion"] in {"aurora", "cinder", "tidal"}
    assert rules.next_fixture(state) is None
    assert state["record"]["played"] == 6
    assert rules.validate_career(state)


@pytest.mark.parametrize(
    ("section", "field", "wrong_value"),
    [
        ("car", "rotation", [0, 0, 0]),
        ("car", "velocity", [600, 0, 0]),
        ("car", "boost", 0),
        ("ball", "velocity", [0, 0, 0]),
    ],
)
def test_reset_confirmation_rejects_position_only_match_with_other_state_wrong(
    section, field, wrong_value
):
    engine = TrainingEngine("flip-reset")
    _ready(engine)
    packet = _confirmed_start_packet(engine)
    packet[section][field] = wrong_value

    events = engine.update(packet)

    assert engine.state == "ready"
    assert not any(event["type"] == "go" for event in events)


def test_speed_flip_cannot_pass_when_dodge_and_cancel_happen_after_target_crossing():
    engine = TrainingEngine("speed-flip")
    # Use a close, controlled start so the test checks event ordering rather than
    # impossible travel through a large arena in a few synthetic packets.
    engine.lesson["starting_state"]["car"]["position"] = [0, -40, 17.01]
    engine.lesson["settle_state"]["car"]["position"] = [0, -40, 17.01]
    engine.reset()
    _ready(engine)
    t = engine.reset_requested_at + 0.01
    engine.update(_confirmed_start_packet(engine))

    engine.update(_frame(t + 0.02, (0, -10, 200), (0, 0, 93), car={
        "wheel_contact": False, "air_state": "InAir", "has_jumped": True,
    }))
    engine.update(_frame(t + 0.03, (0, 10, 210), (0, 0, 93), car={
        "wheel_contact": False, "air_state": "InAir", "has_jumped": True,
    }))
    assert "target_crossed" in engine._emitted
    engine.update(_frame(t + 0.04, (0, 20, 220), (0, 0, 93), car={
        "wheel_contact": False, "air_state": "Dodging", "has_jumped": True, "has_dodged": True,
    }, actions={"pitch": -1.0, "yaw": 0.5}))
    engine.update(_frame(t + 0.05, (0, 30, 230), (0, 0, 93), car={
        "wheel_contact": False, "air_state": "Dodging", "has_jumped": True, "has_dodged": True,
    }, actions={"pitch": 1.0}))
    engine.update(_frame(t + 0.06, (0, 40, 17.01), (0, 0, 93)))

    assert "diagonal_dodge" in engine._emitted and "opposing_pitch" in engine._emitted
    assert "landed" in engine._emitted
    assert engine.outcome != "success"


def test_flip_reset_contact_before_spending_original_flip_cannot_count_as_new_acquisition():
    engine = TrainingEngine("flip-reset")
    _ready(engine)
    engine.update(_confirmed_start_packet(engine))
    contact_time = engine.started_at + 0.01
    pose = {
        "position": [0, 0, 800],
        "rotation": [0, 0, math.pi],
        "wheel_contact": False,
        "air_state": "InAir",
    }
    stale_touch = {
        "game_seconds": contact_time,
        "location": [0, 0, 840],
        "normal": [0, 0, 1],
        "ball_index": 0,
    }
    engine.update(_frame(
        contact_time,
        pose["position"],
        (0, 0, 930),
        car={**pose, "has_jumped": True, "latest_touch": stale_touch},
    ))
    engine.update(_frame(
        contact_time + 0.01,
        pose["position"],
        (0, 0, 930),
        car={**pose, "has_jumped": True, "has_dodged": True,
             "air_state": "Dodging", "latest_touch": stale_touch},
        actions={"pitch": -1.0},
    ))
    engine.update(_frame(
        contact_time + 0.02,
        pose["position"],
        (0, 0, 930),
        car={**pose, "latest_touch": stale_touch},
    ))

    assert engine.spent_flip_time is not None
    assert engine.last_touch_time < engine.spent_flip_time
    assert "reset_acquired" not in engine._emitted
    assert engine.outcome != "success"


def test_recording_schema_version_rejects_boolean_that_compares_equal_to_one():
    forged = _valid_local_recording()
    forged["schema_version"] = True

    with pytest.raises(ValueError, match="version"):
        validate_recording(forged)


def test_negative_duration_import_cannot_become_a_personal_best():
    forged = _valid_local_recording()
    forged["duration"] = -100.0

    with pytest.raises(ValueError, match="duration"):
        validate_recording(forged)
    assert personal_best([], forged) is None
