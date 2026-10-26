"""Synthetic-only contracts for bot-reference capture; no fixture is real or shippable."""

from copy import deepcopy
import inspect
import math

import pytest

from my_career_training.training.bot_reference import (
    DEFAULT_GATES,
    DEFAULT_PARAMETERS,
    NEUTRAL_ACTIONS,
    SpeedFlipTrialController,
    controller_plan,
    evaluate_bot_baseline,
    evaluate_bot_trial,
    select_bot_benchmark,
)
from my_career_training.training.catalog import configure_lesson
from my_career_training.training.recordings import Recorder, validate_recording


TICK = 1 / 120
MATCH_CONFIGURATION = {
    "map": "Stadium_P",
    "game_mode": "Soccar",
    "freeplay": True,
    "mutators": {
        "game_speed": "Default",
        "gravity": "Default",
        "boost_amount": "NormalBoost",
        "match_length": "Unlimited",
        "max_score": "Unlimited",
        "multi_ball": "One",
        "overtime": "Unlimited",
    },
}


def _actions(*, jump=False, pitch=0.0, yaw=0.0, throttle=1.0, boost=True):
    return {
        "throttle": throttle,
        "steer": 0.0,
        "pitch": pitch,
        "yaw": yaw,
        "roll": 0.0,
        "jump": jump,
        "boost": boost,
        "handbrake": False,
    }


def _fixture(
    profile="cancel",
    *,
    outcome=None,
    include_cancel=None,
    cancel_index=33,
    crossing_time=1.246,
    crossing_x=0.0,
    crossing_z=280.0,
    bad_landing=None,
    game_version="test-only-game-build",
):
    """Build a clearly synthetic, deterministic test recording and matching summary."""
    if include_cancel is None:
        include_cancel = profile == "cancel"
    lesson = configure_lesson("speed-flip")
    source = {
        "kind": "actual_execution",
        "actor": "bot",
        "origin": "TEST-ONLY synthetic fixture; not a game capture",
        "profile": profile,
        "script_id": "test-only-script",
    }
    metadata = {
        "game_version": game_version,
        "framework_version": "test-only-RLBot",
        "car_hitbox": "test-only-octane",
        "map": "DFHStadium",
        "mutators": {
            "source": "rlbot_match_configuration",
            "requested": deepcopy(MATCH_CONFIGURATION),
            "acknowledged": deepcopy(MATCH_CONFIGURATION),
        },
        "starting_state": deepcopy(lesson["starting_state"]),
        "time_base": "game_seconds",
        "source": source,
        "permission": {"distribute": False, "basis": "TEST-ONLY fixture"},
        "success_evidence": [],
    }
    recorder = Recorder(lesson, metadata)

    # 120 Hz packets, with a real recorded jump/release/diagonal-jump edge. These
    # are test values only; they do not describe a Rocket League execution.
    first_crossing_index = 149
    crossing_fraction = (crossing_time - first_crossing_index * TICK) / TICK
    assert 0 < crossing_fraction < 1
    previous_y = -200.0 * crossing_fraction
    current_y = 200.0 * (1.0 - crossing_fraction)
    duration = 10.0 if profile == "baseline" else 1.5
    last_index = round(duration / TICK)

    for index in range(last_index + 1):
        time = index * TICK
        y = -2500.0 + 2000.0 * time
        z = 17.01
        if 0.30 <= time < 0.50:
            z = 17.01 + 700.0 * (time - 0.30)
        elif 0.50 <= time < 1.20:
            z = 157.01 + 100.0 * (time - 0.50)
        elif 1.20 <= time < 1.35:
            z = 227.01 + (280.0 - 227.01) * ((time - 1.20) / 0.15)
        elif 1.35 <= time < 1.50:
            z = 280.0 + (17.01 - 280.0) * ((time - 1.35) / 0.15)
        elif time >= 1.50:
            z = 17.01

        if index == first_crossing_index:
            y = previous_y
        elif index == first_crossing_index + 1:
            y = current_y
        x = crossing_x if index in (first_crossing_index, first_crossing_index + 1) else 0.0
        if index in (first_crossing_index, first_crossing_index + 1):
            z = crossing_z

        jump = 24 <= index < 27 or 30 <= index < 33
        pitch = yaw = 0.0
        if 30 <= index < 33:
            pitch, yaw = -0.7, 1.0
        elif include_cancel and cancel_index <= index < cancel_index + 12:
            pitch = 1.0

        rotation = [0.0, math.pi / 2, 0.0]
        if bad_landing == "upside_down" and index == last_index:
            rotation = [0.0, math.pi / 2, math.pi]
        if bad_landing == "misaligned" and index >= round(1.50 / TICK):
            velocity = [2000.0, 0.0, 0.0]
        else:
            velocity = [0.0, 2000.0, 0.0]
        if index == 0:
            # The first observed sample is also the recorded spawn state.
            # Keep it exactly canonical; subsequent samples model test-only motion.
            velocity = [0.0, 0.0, 0.0]
        angular_velocity = [0.0, 0.0, 0.0] if index == 0 else [0.0, 0.0, 0.5]
        frame = {
            "time": 40.0 + time,
            "game_speed": 1.0,
            "car": {
                "position": [x, y, z],
                "rotation": rotation,
                "velocity": velocity,
                "angular_velocity": angular_velocity,
                "wheel_contact": time < 0.30 or time >= 1.50,
                "boost": 100.0,
            },
            "ball": {
                "position": [0.0, 0.0, 93.15],
                "velocity": [0.0, 0.0, 0.0],
            },
            "actions": _actions(jump=jump, pitch=pitch, yaw=yaw),
            "packet_gap": False,
        }
        recorder.append(frame)

    if bad_landing == "upside_down":
        # The evaluator derives landing orientation from the first sample at or
        # below grounded height; make that sample, not just a trailing frame, bad.
        recorder.samples[-1]["rotation"] = [0.0, math.pi / 2, math.pi]

    outcome = outcome or ("success" if profile == "cancel" else "timeout")
    recording = recorder.export(outcome=outcome, events=[], duration=duration)
    events = [
        {"type": "skill", "name": "first_jump", "time": 0.20, "confidence": "observed", "details": {}},
        {"type": "skill", "name": "diagonal_dodge", "time": 0.25, "confidence": "observed", "details": {}},
    ]
    if include_cancel:
        cancel_time = cancel_index * TICK
        events.append({
            "type": "skill",
            "name": "opposing_pitch",
            "time": cancel_time,
            "confidence": "observed",
            "details": {"delay_seconds": cancel_time - 0.25},
        })
    event_cross_time = first_crossing_index * TICK + crossing_fraction * TICK
    event_packet_time = (first_crossing_index + 1) * TICK
    events.extend([
        {
            "type": "skill",
            "name": "target_crossed",
            "time": event_packet_time,
            "confidence": "observed",
            "details": {"crossing_time": event_cross_time},
        },
        {"type": "skill", "name": "landed", "time": 1.50, "confidence": "observed", "details": {}},
    ])
    recording["events"] = deepcopy(events)
    if outcome != "success":
        recording["metadata"]["success_evidence"] = []
    else:
        recording["metadata"]["success_evidence"] = deepcopy(events)

    roof_up = -1.0 if bad_landing == "upside_down" else 1.0
    forward_alignment = 0.0 if bad_landing == "misaligned" else 1.0
    speed = 2000.0
    summary = {
        "outcome": outcome,
        "profile": profile,
        "events": events,
        "metrics": {
            "crossing_seconds": event_cross_time,
            "crossing_speed": speed,
            "landing_roof_up": roof_up,
            "landing_forward_alignment": forward_alignment,
            "landing_speed": speed,
            "landing_angular_speed": 0.5,
            "packet_gaps": 0,
        },
    }
    return recording, summary


def _set_crossing_time(case, crossing_time):
    recording, summary = case
    index = 149
    previous_time = index * TICK
    fraction = (crossing_time - previous_time) / TICK
    assert 0 < fraction < 1
    recording["samples"][index]["position"][1] = -200.0 * fraction
    recording["samples"][index + 1]["position"][1] = 200.0 * (1.0 - fraction)
    summary["metrics"]["crossing_seconds"] = crossing_time
    summary["events"][-2]["details"]["crossing_time"] = crossing_time
    recording["metadata"]["success_evidence"] = deepcopy(summary["events"])
    return recording, summary


def _reasons(result):
    return " ".join(result["reasons"]).lower()


def test_controller_uses_game_time_and_returns_all_eight_controls():
    controller = SpeedFlipTrialController("cancel")
    at_start = controller.step(0.0)
    assert set(at_start) == set(NEUTRAL_ACTIONS)
    assert at_start["throttle"] == 1.0
    assert at_start["boost"] is True
    assert at_start["jump"] is False
    assert controller.step(0.1)["throttle"] == 1.0
    assert controller.step(0.1) == controller.step(0.1)


def test_controller_has_explicit_two_tick_jump_release_between_jumps():
    controller = SpeedFlipTrialController("cancel")
    plan = controller.controller_plan()
    phases = {phase["name"]: phase for phase in plan["phases"]}
    release = phases["jump_release"]
    assert release["end_seconds"] - release["start_seconds"] >= 2 * TICK
    assert controller.step(phases["first_jump"]["start_seconds"])["jump"] is True
    assert controller.step(release["start_seconds"])["jump"] is False
    assert controller.step(release["start_seconds"] + TICK)["jump"] is False
    dodge = controller.step(phases["diagonal_dodge"]["start_seconds"])
    assert dodge["jump"] is True
    assert abs(dodge["pitch"]) >= DEFAULT_GATES["diagonal_action"]
    assert abs(dodge["yaw"]) >= DEFAULT_GATES["diagonal_action"]


def test_controller_cancel_and_baseline_profiles_are_same_except_opposing_pitch():
    cancel = SpeedFlipTrialController("cancel")
    baseline = SpeedFlipTrialController("baseline")
    cancel_plan = cancel.controller_plan()
    baseline_plan = baseline.controller_plan()
    assert cancel_plan["time_base"] == "game_seconds_since_go"
    assert cancel_plan["chooses_player_index"] is False
    assert cancel_plan["sends_inputs"] is False
    assert cancel_plan["external_weights"] is False
    assert "not claimed" in cancel_plan["claim"].lower()
    phase = next(x for x in cancel_plan["phases"] if x["name"] == "opposing_pitch")
    control_phase = next(x for x in baseline_plan["phases"] if x["name"] == "no_cancel_control")
    assert phase["start_seconds"] == control_phase["start_seconds"]
    assert phase["end_seconds"] == control_phase["end_seconds"]
    assert cancel.step(phase["start_seconds"])["pitch"] > 0
    assert baseline.step(control_phase["start_seconds"])["pitch"] == 0
    route_probe = SpeedFlipTrialController("cancel")
    assert route_probe.step(0.2, {"player_index": 999, "is_human": True})["throttle"] == 1.0
    assert "player_index" not in inspect.signature(cancel.step).parameters


@pytest.mark.parametrize("bad_time", [-1.0, math.nan, math.inf, -math.inf, True, "0.2"])
def test_controller_invalid_clock_returns_neutral_and_interrupts(bad_time):
    controller = SpeedFlipTrialController()
    assert controller.step(bad_time) == NEUTRAL_ACTIONS
    assert controller.interrupted is True
    assert controller.finished is True


def test_controller_backward_time_interrupts_and_reset_recovers():
    controller = SpeedFlipTrialController()
    assert controller.step(0.2)["throttle"] == 1.0
    assert controller.step(0.19) == NEUTRAL_ACTIONS
    assert controller.interrupted is True
    controller.reset()
    assert controller.interrupted is False
    assert controller.finished is False
    assert controller.step(0.0)["throttle"] == 1.0


def test_controller_timeout_finish_and_phase_bounds_are_bounded():
    controller = SpeedFlipTrialController()
    assert controller.step(DEFAULT_PARAMETERS["timeout_seconds"] + 0.01) == NEUTRAL_ACTIONS
    assert controller.timed_out is True
    assert controller.finished is True
    controller.reset()
    controller.finish()
    assert controller.step(0.0) == NEUTRAL_ACTIONS
    with pytest.raises(ValueError, match="phase bound"):
        SpeedFlipTrialController(parameters={"phase_max_seconds": 0.1})


@pytest.mark.parametrize("profile", ["cancel", "baseline"])
def test_controller_plan_is_json_safe_and_contains_no_game_routing(profile):
    import json

    plan = SpeedFlipTrialController(profile).controller_plan()
    assert json.loads(json.dumps(plan)) == plan
    assert plan["chooses_player_index"] is False
    assert plan["sends_inputs"] is False
    assert "player_index" not in plan
    assert controller_plan(profile) == plan


def test_evaluator_accepts_only_corroborated_test_candidate_and_never_mutates_it():
    recording, summary = _fixture()
    before = deepcopy((recording, summary))
    result = evaluate_bot_trial(recording, summary)
    assert result["eligible"] is True
    assert result["label"] == "Passing bot trial (this setup)"
    assert result["metrics"]["crossing_seconds"] == pytest.approx(1.246)
    assert result["metrics"]["landing_roof_up"] == pytest.approx(1.0)
    assert result["certification"] == "none"
    assert result["provisional"] is True
    with pytest.raises(ValueError, match="permission"):
        validate_recording(recording, require_reference=True)
    assert (recording, summary) == before


def test_fake_success_strings_cannot_replace_missing_recorded_jump_edges():
    recording, summary = _fixture()
    for sample in recording["samples"][30:33]:
        sample["actions"]["jump"] = False
    result = evaluate_bot_trial(recording, summary)
    assert result["eligible"] is False
    assert "second jump" in _reasons(result) or "diagonal dodge" in _reasons(result)


def test_cancel_summary_time_must_match_independent_recorded_opposing_input_time():
    recording, summary = _fixture()
    event = next(x for x in summary["events"] if x["name"] == "opposing_pitch")
    event["time"] = 0.60  # Still before the line; sample actions prove cancel at 0.275.
    event["details"]["delay_seconds"] = 0.025
    result = evaluate_bot_trial(recording, summary)
    assert result["eligible"] is False
    assert "opposing_pitch" in _reasons(result) or "cancel" in _reasons(result)


def test_late_opposing_input_is_rejected_even_when_before_finish():
    recording, summary = _fixture(cancel_index=48)  # 0.40 s: late, but before crossing.
    result = evaluate_bot_trial(recording, summary)
    assert result["eligible"] is False
    assert "delay" in _reasons(result) or "candidate window" in _reasons(result)


@pytest.mark.parametrize("bad_landing", ["upside_down", "misaligned"])
def test_bad_rotation_or_forward_recovery_is_rejected(bad_landing):
    recording, summary = _fixture(bad_landing=bad_landing)
    result = evaluate_bot_trial(recording, summary)
    assert result["eligible"] is False
    assert "landing" in _reasons(result) or "align" in _reasons(result)


def test_excessive_landing_angular_speed_is_rejected():
    recording, summary = _fixture()
    angular_speed = DEFAULT_GATES["max_landing_angular_speed"] + 0.1
    for sample in recording["samples"]:
        if sample["time"] >= 1.50:
            sample["angular_velocity"] = [0.0, 0.0, angular_speed]
    summary["metrics"]["landing_angular_speed"] = angular_speed
    result = evaluate_bot_trial(recording, summary)
    assert result["eligible"] is False
    assert "angular speed" in _reasons(result)


@pytest.mark.parametrize(
    ("crossing_x", "crossing_z"),
    [(DEFAULT_GATES["crossing_half_width"] + 1, 280.0), (0.0, DEFAULT_GATES["crossing_max_height"] + 1)],
)
def test_finish_rectangle_requires_measured_crossing_inside_width_and_height(crossing_x, crossing_z):
    recording, summary = _fixture(crossing_x=crossing_x, crossing_z=crossing_z)
    result = evaluate_bot_trial(recording, summary)
    assert result["eligible"] is False
    assert "finish rectangle" in _reasons(result)


def test_packet_gap_in_samples_or_summary_invalidates_candidate():
    recording, summary = _fixture()
    recording["samples"][50]["packet_gap"] = True
    assert evaluate_bot_trial(recording, summary)["eligible"] is False
    recording, summary = _fixture()
    summary["metrics"]["packet_gaps"] = 1
    assert evaluate_bot_trial(recording, summary)["eligible"] is False


def test_sample_clock_has_120hz_evidence_and_cancel_tolerance_is_one_packet():
    recording, _ = _fixture()
    intervals = [b["time"] - a["time"] for a, b in zip(recording["samples"], recording["samples"][1:])]
    assert max(intervals) == pytest.approx(TICK)
    assert DEFAULT_GATES["packet_tolerance_seconds"] <= TICK + 1e-6
    assert max(intervals) <= DEFAULT_GATES["max_sample_interval_seconds"]


def test_recorder_retains_only_observed_wheel_contact_and_angular_velocity():
    recording, _ = _fixture()
    airborne = recording["samples"][50]
    landed = recording["samples"][round(1.50 / TICK)]
    assert airborne["wheel_contact"] is False
    assert landed["wheel_contact"] is True
    assert airborne["angular_velocity"] == [0.0, 0.0, 0.5]
    assert landed["angular_velocity"] == [0.0, 0.0, 0.5]


@pytest.mark.parametrize("evidence", ["wheel_contact", "angular_velocity"])
def test_reference_rejects_missing_ground_contact_or_rotation_rate_samples(evidence):
    recording, summary = _fixture()
    recording["samples"][round(1.50 / TICK)].pop(evidence)
    result = evaluate_bot_trial(recording, summary)
    assert result["eligible"] is False
    assert evidence.replace("_", " ") in _reasons(result) or "samples" in _reasons(result)


def test_truncated_recording_and_non_normal_speed_are_rejected():
    recording, summary = _fixture()
    recording["truncated"] = True
    assert evaluate_bot_trial(recording, summary)["eligible"] is False
    recording, summary = _fixture()
    recording["samples"][20]["game_speed"] = 0.5
    assert evaluate_bot_trial(recording, summary)["eligible"] is False
    recording, summary = _fixture()
    recording["samples"][20].pop("game_speed")
    assert evaluate_bot_trial(recording, summary)["eligible"] is False


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("game_version", "unknown"),
        ("framework_version", "unavailable"),
        ("car_hitbox", "unknown"),
        ("map", "unknown"),
        ("starting_state", {}),
        ("mutators", {}),
    ],
)
def test_unknown_or_undeclared_runtime_metadata_is_rejected(field, value):
    recording, summary = _fixture()
    recording["metadata"][field] = value
    result = evaluate_bot_trial(recording, summary)
    assert result["eligible"] is False
    assert field in _reasons(result) or "starting state" in _reasons(result)


def test_metadata_must_match_exact_speedflip_start_state():
    recording, summary = _fixture()
    recording["metadata"]["starting_state"]["car"]["position"][1] -= 100
    result = evaluate_bot_trial(recording, summary)
    assert result["eligible"] is False
    assert "starting state" in _reasons(result) or "setup" in _reasons(result)


def test_metadata_must_match_speedflip_map():
    recording, summary = _fixture()
    recording["metadata"]["map"] = "Mannfield"
    result = evaluate_bot_trial(recording, summary)
    assert result["eligible"] is False
    assert "map" in _reasons(result) or "setup" in _reasons(result)


def test_unknown_mutator_values_are_not_a_declared_exact_setup():
    recording, summary = _fixture()
    recording["metadata"]["mutators"]["acknowledged"]["mutators"]["gravity"] = "unknown"
    result = evaluate_bot_trial(recording, summary)
    assert result["eligible"] is False
    assert "mutator" in _reasons(result) or "setup" in _reasons(result)


@pytest.mark.parametrize("acknowledgement", ["not measured", "not observed"])
def test_mutator_acknowledgement_markers_do_not_count_as_runtime_evidence(acknowledgement):
    recording, summary = _fixture()
    recording["metadata"]["mutators"]["acknowledged"] = acknowledgement

    result = evaluate_bot_trial(recording, summary)

    assert result["eligible"] is False
    assert "mutator" in _reasons(result)


def test_requested_only_mutators_do_not_count_as_acknowledged_setup():
    recording, summary = _fixture()
    recording["metadata"]["mutators"] = {
        "source": "rlbot_match_configuration",
        "requested": deepcopy(MATCH_CONFIGURATION),
    }

    result = evaluate_bot_trial(recording, summary)

    assert result["eligible"] is False
    assert "mutator" in _reasons(result)


def test_acknowledged_mutators_must_match_the_requested_match_configuration():
    recording, summary = _fixture()
    recording["metadata"]["mutators"]["acknowledged"]["mutators"]["boost_amount"] = "UnlimitedBoost"

    result = evaluate_bot_trial(recording, summary)

    assert result["eligible"] is False
    assert "mutator" in _reasons(result)


@pytest.mark.parametrize(
    ("kind", "actor"),
    [("local_player", "bot"), ("actual_execution", "local_player"), ("imported", "bot")],
)
def test_local_player_or_imported_execution_cannot_become_bot_reference(kind, actor):
    recording, summary = _fixture()
    recording["metadata"]["source"].update(kind=kind, actor=actor)
    result = evaluate_bot_trial(recording, summary)
    assert result["eligible"] is False
    assert "bot" in _reasons(result) or "actual bot execution" in _reasons(result)


def test_wrong_lesson_version_missing_variant_and_non_observed_events_are_rejected():
    recording, summary = _fixture()
    recording["lesson_version"] += 1
    assert evaluate_bot_trial(recording, summary)["eligible"] is False
    recording, summary = _fixture()
    recording["variant"] = None
    assert evaluate_bot_trial(recording, summary)["eligible"] is False
    recording, summary = _fixture()
    next(x for x in summary["events"] if x["name"] == "diagonal_dodge")["confidence"] = "estimated"
    result = evaluate_bot_trial(recording, summary)
    assert result["eligible"] is False
    assert "observed" in _reasons(result)


def test_fake_crossing_metric_must_match_the_recorded_geometry():
    recording, summary = _fixture()
    summary["metrics"]["crossing_seconds"] += 0.5
    result = evaluate_bot_trial(recording, summary)
    assert result["eligible"] is False
    assert "crossing time" in _reasons(result)
    recording, summary = _fixture()
    summary["metrics"]["crossing_speed"] += 500
    result = evaluate_bot_trial(recording, summary)
    assert result["eligible"] is False
    assert "crossing speed" in _reasons(result)


def test_controller_profile_mismatch_and_fake_baseline_cancel_are_rejected():
    recording, summary = _fixture(profile="baseline")
    assert evaluate_bot_trial(recording, summary)["eligible"] is False

    recording, summary = _fixture(profile="baseline", outcome="success", include_cancel=True)
    result = evaluate_bot_baseline(recording, summary)
    assert result["eligible"] is False
    assert "cancel" in _reasons(result) or "opposing" in _reasons(result)


def test_complete_no_cancel_baseline_is_measurable_despite_engine_timeout():
    recording, summary = _fixture(profile="baseline")
    assert recording["outcome"] == "timeout"
    assert not any(event["name"] == "opposing_pitch" for event in summary["events"])
    result = evaluate_bot_baseline(recording, summary)
    assert result["eligible"] is True
    assert result["label"] == "Baseline bot trial (unvalidated)"
    assert result["metrics"]["crossing_seconds"] == pytest.approx(1.246)


def _trial(case):
    recording, summary = case
    return {"recording": recording, "summary": summary}


def test_selector_requires_three_repetitions_and_selects_fastest_passing_run():
    candidate_times = (1.242, 1.243, 1.244)
    baseline_times = (1.247, 1.248, 1.249)
    candidates = [_trial(_set_crossing_time(_fixture(), value)) for value in candidate_times]
    baselines = [
        _trial(_set_crossing_time(_fixture("baseline"), value)) for value in baseline_times
    ]

    not_enough = select_bot_benchmark(candidates[:2], baselines)
    assert not_enough["eligible"] is False
    assert "2 distinct passing candidate repetitions" in " ".join(not_enough["reasons"])

    result = select_bot_benchmark(candidates, baselines)
    assert result["eligible"] is True
    assert result["status"] == "eligible_for_review"
    assert result["candidate_repetitions"] == 3
    assert result["baseline_repetitions"] == 3
    assert result["candidate_median_crossing_seconds"] == pytest.approx(1.243)
    assert result["baseline_median_crossing_seconds"] == pytest.approx(1.248)
    assert result["improvement_seconds"] == pytest.approx(0.005)
    assert result["candidate"]["crossing_seconds"] == pytest.approx(1.242)
    assert result["distribution_permission"] is False
    assert result["certification"] == "none"


def test_selector_rejects_setup_mismatch_and_non_improving_median():
    candidates = [_trial(_set_crossing_time(_fixture(), t)) for t in (1.242, 1.243, 1.244)]
    baselines = [
        _trial(_set_crossing_time(_fixture("baseline"), t)) for t in (1.247, 1.248, 1.249)
    ]
    baselines[-1]["recording"]["metadata"]["game_version"] = "test-only-other-build"
    mismatch = select_bot_benchmark(candidates, baselines)
    assert mismatch["eligible"] is False
    assert "setup fingerprint" in " ".join(mismatch["reasons"]).lower()

    slow_candidates = [_trial(_set_crossing_time(_fixture(), t)) for t in (1.247, 1.248, 1.249)]
    faster_baselines = [
        _trial(_set_crossing_time(_fixture("baseline"), t)) for t in (1.242, 1.243, 1.244)
    ]
    no_improvement = select_bot_benchmark(slow_candidates, faster_baselines)
    assert no_improvement["eligible"] is False
    assert "does not improve" in " ".join(no_improvement["reasons"]).lower()


def test_selector_does_not_count_reused_capture_bytes_as_three_repetitions():
    candidate = _trial(_set_crossing_time(_fixture(), 1.242))
    baseline = _trial(_set_crossing_time(_fixture("baseline"), 1.248))
    result = select_bot_benchmark([candidate] * 3, [baseline] * 3)
    assert result["eligible"] is False
    assert "distinct" in " ".join(result["reasons"]).lower() or "repeated" in " ".join(
        result["reasons"]
    ).lower()
