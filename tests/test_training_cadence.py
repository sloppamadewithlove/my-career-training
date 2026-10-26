"""Training cadence contracts; no test launches or controls a game."""

from copy import deepcopy

import pytest

from my_career_training.training.cadence import classify_cadence
from my_career_training.training import TrainingEngine, assistance_preferences


PHYSICS_STEP = 1 / 120


def _frame(time, frame_num=None, **extra):
    value = {"time": time}
    if frame_num is not None:
        value["frame_num"] = frame_num
    value.update(extra)
    return value


@pytest.mark.parametrize(
    ("steps", "strict", "expected_gap", "expected_coarse"),
    [
        (1, False, False, False),
        (1, True, False, False),
        (2, False, False, True),
        (2, True, True, False),
    ],
)
def test_supported_training_cadence_matches_physics_steps(
    steps, strict, expected_gap, expected_coarse
):
    previous = _frame(3.0, 300)
    current = _frame(3.0 + steps * PHYSICS_STEP, 300 + steps)

    result = classify_cadence(previous, current, strict=strict)

    assert result["gap"] is expected_gap
    assert result["steps"] == steps
    assert result["coarse"] is expected_coarse
    if expected_gap:
        assert result["reason"] == "step_count_exceeded"
    else:
        assert result["reason"] == ("coarse_continuous" if steps == 2 else "continuous")


@pytest.mark.parametrize(
    ("current", "reason"),
    [
        (_frame(3 * PHYSICS_STEP, 3), "step_count_exceeded"),
        (_frame(2 * PHYSICS_STEP, 1), "physics_step_mismatch"),
        (_frame(3 * PHYSICS_STEP, 2), "physics_step_mismatch"),
        (_frame(0.0, 0), "non_increasing_clock"),
        (_frame(-PHYSICS_STEP, -1), "non_increasing_clock"),
    ],
)
def test_unexpected_frame_steps_and_clock_relationships_remain_gaps(current, reason):
    previous = _frame(0.0, 0)

    result = classify_cadence(previous, current)

    assert result["gap"] is True
    assert result["reason"] == reason


def test_explicit_transport_gap_is_never_hidden_by_expected_coarse_clock():
    previous = _frame(1.0, 120)
    current = _frame(1.0 + 2 * PHYSICS_STEP, 122, packet_gap=True)

    result = classify_cadence(previous, current)

    assert result["gap"] is True
    assert result["reason"] == "explicit_packet_gap"


def test_legacy_frames_without_frame_numbers_use_bounded_game_clock_cadence():
    previous = _frame(4.0)
    current = _frame(4.0 + 2 * PHYSICS_STEP)

    result = classify_cadence(previous, current)

    assert result["gap"] is False
    assert result["steps"] is None
    assert result["coarse"] is False
    assert result["reason"] == "legacy_clock_continuous"

    too_late = classify_cadence(previous, _frame(4.0 + 0.06))
    assert too_late["gap"] is True
    assert too_late["reason"] == "interval_exceeded"


def test_strict_capture_does_not_guess_when_frame_numbers_are_missing_or_partial():
    missing = classify_cadence(
        _frame(2.0), _frame(2.0 + PHYSICS_STEP), strict=True
    )
    assert missing["gap"] is True
    assert missing["reason"] == "cadence_unavailable"

    partial = classify_cadence(
        _frame(2.0, 100), _frame(2.0 + PHYSICS_STEP), strict=True
    )
    assert partial["gap"] is True
    assert partial["reason"] == "frame_number_unavailable"


def test_first_frame_needs_no_previous_clock_but_strict_mode_is_validated():
    first = classify_cadence(None, _frame(0.0, 0))
    assert first["gap"] is False
    assert first["reason"] == "first_frame"

    with pytest.raises(ValueError, match="strictness"):
        classify_cadence(None, _frame(0.0), strict=1)


def _engine_frame(engine, game_time, frame_num, *, starting=False):
    state = engine.lesson["starting_state" if starting else "settle_state"]
    car = deepcopy(state["car"])
    car.update(
        wheel_contact=True,
        air_state="OnGround",
        has_jumped=False,
        has_double_jumped=False,
        has_dodged=False,
    )
    return {
        "time": game_time,
        "frame_num": frame_num,
        "car": car,
        "ball": deepcopy(state["ball"]),
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


def test_60hz_samples_can_settle_confirm_reset_and_start_training():
    engine = TrainingEngine("speed-flip")
    first_frame_num = 1_000

    ready_events = []
    for index in range(20):
        ready_events = engine.update(
            _engine_frame(engine, index / 60, first_frame_num + 2 * index)
        )
        if engine.state == "ready":
            break

    assert engine.state == "ready"
    assert [event["type"] for event in ready_events] == ["set_state", "ready"]

    start_index = index + 1
    go_events = engine.update(
        _engine_frame(
            engine,
            start_index / 60,
            first_frame_num + 2 * start_index,
            starting=True,
        )
    )

    assert engine.state == "active"
    assert [event["type"] for event in go_events] == ["go"]


def test_strict_capture_engine_rejects_coarse_samples_and_disables_auto_reset():
    ordinary = TrainingEngine("speed-flip")
    strict = TrainingEngine("speed-flip", strict_capture=True)
    previous = _frame(0.0, 1_000)
    one_step = _frame(PHYSICS_STEP, 1_001)
    two_steps = _frame(2 * PHYSICS_STEP, 1_002)

    assert ordinary.cadence(previous, two_steps)["gap"] is False
    assert strict.cadence(previous, one_step)["gap"] is False
    assert strict.cadence(previous, two_steps)["gap"] is True
    assert strict.preferences["auto_reset"] is False


def _ordered_speed_flip_events(*, coarse_jump_and_dodge):
    shared = [0.0, 2 * PHYSICS_STEP]
    jump_bracket = shared if coarse_jump_and_dodge else [0.0, PHYSICS_STEP]
    dodge_bracket = shared if coarse_jump_and_dodge else [PHYSICS_STEP, 2 * PHYSICS_STEP]
    cancel_bracket = [2 * PHYSICS_STEP, 3 * PHYSICS_STEP]
    crossing_bracket = [3 * PHYSICS_STEP, 4 * PHYSICS_STEP]
    landing_bracket = [4 * PHYSICS_STEP, 5 * PHYSICS_STEP]
    return [
        {"name": "first_jump", "time": jump_bracket[1], "precision": jump_bracket,
         "confidence": "observed"},
        {"name": "diagonal_dodge", "time": dodge_bracket[1], "precision": dodge_bracket,
         "confidence": "observed"},
        {"name": "opposing_pitch", "time": cancel_bracket[1], "precision": cancel_bracket,
         "confidence": "observed"},
        {"name": "target_crossed", "time": crossing_bracket[1], "precision": crossing_bracket,
         "confidence": "observed", "details": {"crossing_time": 3.5 * PHYSICS_STEP}},
        {"name": "landed", "time": landing_bracket[1], "precision": landing_bracket,
         "confidence": "observed"},
    ]


def test_coarse_packet_cannot_claim_jump_before_dodge_when_brackets_overlap():
    engine = TrainingEngine("speed-flip")
    engine.events = _ordered_speed_flip_events(coarse_jump_and_dodge=True)

    assert engine._ordered_success() is False

    engine.events = _ordered_speed_flip_events(coarse_jump_and_dodge=False)
    assert engine._ordered_success() is True


def test_auto_reset_defaults_on_but_strict_capture_overrides_it():
    assert assistance_preferences()["auto_reset"] is True
    assert TrainingEngine("speed-flip", strict_capture=True).preferences["auto_reset"] is False


def test_strict_capture_settle_timeout_interrupts_once_with_actionable_reason():
    engine = TrainingEngine("speed-flip", strict_capture=True)
    completed = []
    for index in range(301):
        events = engine.update(
            _engine_frame(engine, index / 60, 2_000 + 2 * index)
        )
        if events and events[0]["type"] == "completed":
            completed = events
            break

    assert engine.state == "interrupted"
    assert len(completed) == 1
    assert "continuous telemetry cadence" in completed[0]["summary"]["feedback"].lower()
    assert engine.update(_engine_frame(engine, (index + 1) / 60, 2_000 + 2 * (index + 1))) == []
    assert len(engine.observations) == 1
