"""Ghost-practice contracts. Fixtures are generated; none is a real demonstration."""

from copy import deepcopy
import math

import pytest

from my_career_training.training import (
    GhostPractice,
    PRACTICE_FORWARD_OFFSET,
    configure_lesson,
    ghost_lines,
    practice_context,
    practice_support,
    relative_placement,
)
from my_career_training.training.recordings import Recorder, validate_recording


def capture(*, lesson_id="speed-flip", gap=False, reference=False):
    lesson = configure_lesson(lesson_id)
    recorder = Recorder(lesson, {"game_version": "test-only-game", "framework_version": "test-only-core",
                                 "car_hitbox": "octane"})
    for index in range(121):
        actions = {"throttle": 1.0, "steer": 0.0, "pitch": 0.0, "yaw": 0.0, "roll": 0.0,
                   "jump": index >= 30, "boost": True, "handbrake": False}
        recorder.append({"time": index / 60, "car": {"position": [index * 5, 0, 17],
                         "rotation": [0, math.pi / 2, 0], "velocity": [300, 0, 0]},
                         "ball": {"position": [0, 0, 93], "velocity": [0, 0, 0]},
                         "actions": actions, "packet_gap": gap and index == 30})
    result = recorder.export(outcome="success", duration=2,
                             events=[{"name": "target_crossed", "confidence": "observed"}])
    if reference:
        result["metadata"]["source"] = {"kind": "actual_execution", "origin": "Test fixture only"}
        result["metadata"]["permission"] = {"distribute": True, "basis": "Test fixture only"}
    return result


def context_for(lesson_id="speed-flip", **overrides):
    lesson = configure_lesson(lesson_id)
    context = practice_context(lesson, {"game_version": "test-only-game",
                                        "framework_version": "test-only-core",
                                        "car_hitbox": "octane"})
    context.update(overrides)
    return context


def player(position=(0, -2500, 17.01), rotation=(0, math.pi / 2, 0)):
    return {"position": list(position), "rotation": list(rotation)}


def test_constructor_validates_distance_and_defaults_to_owner_distance():
    assert GhostPractice().forward_offset == PRACTICE_FORWARD_OFFSET == 300.0
    assert GhostPractice(forward_offset=0).forward_offset == 0.0
    for bad in (True, -1, math.nan, math.inf, "300", 5000):
        with pytest.raises(ValueError, match="placement distance"):
            GhostPractice(forward_offset=bad)


def test_relative_placement_translates_heading_and_preserves_relative_motion():
    origin = {"position": [0, 0, 0], "rotation": [0, 0, 0]}
    anchor = {"position": [100, 200, 17], "rotation": [0, math.pi / 2, 0]}
    start = {"position": [0, 0, 0], "rotation": [0, 0, 0], "actions": {"jump": False}}
    placed = relative_placement(start, origin=origin, anchor=anchor, forward_offset=300)
    # Player faces +y, so "in front" is +y and the recorded start is the anchor.
    assert placed["position"] == pytest.approx([100, 500, 17])
    later = {"position": [50, 0, 0], "rotation": [0, 0, 0], "actions": {"jump": True}}
    moved = relative_placement(later, origin=origin, anchor=anchor, forward_offset=300)
    # Recorded +x motion becomes +y motion after the yaw-only rotation.
    assert moved["position"] == pytest.approx([100, 550, 17])
    assert moved["actions"] == {"jump": True}


def test_relative_placement_rotates_orientation_and_never_mutates_inputs():
    origin = {"position": [0, 0, 0], "rotation": [0, 0, 0]}
    anchor = {"position": [0, 0, 0], "rotation": [0, math.pi / 2, 0]}
    pose = {"position": [10, 0, 0], "rotation": [0, 0, 0], "actions": {"boost": True}}
    snapshot = deepcopy((origin, anchor, pose))
    placed = relative_placement(pose, origin=origin, anchor=anchor, forward_offset=300)
    assert (origin, anchor, pose) == snapshot
    # A quarter turn about z maps the identity quaternion to yaw +90 degrees.
    w, x, y, z = placed["quaternion"]
    assert (x, y) == pytest.approx((0.0, 0.0))
    assert z == pytest.approx(math.sin(math.pi / 4))
    assert w == pytest.approx(math.cos(math.pi / 4))
    placed["actions"]["boost"] = False
    assert pose["actions"]["boost"] is True


def test_relative_placement_accepts_euler_poses_and_rejects_malformed_ones():
    origin = {"position": [0, 0, 0], "rotation": [0, 0, 0]}
    anchor = {"position": [0, 0, 0], "rotation": [0, 0, 0]}
    placed = relative_placement({"position": [1, 2, 3], "rotation": [0, 0, 0]},
                                origin=origin, anchor=anchor, forward_offset=0)
    assert placed["position"] == pytest.approx([1, 2, 3])
    with pytest.raises(ValueError, match="oriented pose"):
        relative_placement({"position": [1, 2, 3]}, origin=origin, anchor=anchor)
    with pytest.raises(ValueError, match="positions"):
        relative_placement({"position": [1, 2, 3], "rotation": [0, 0, 0]},
                           origin={"rotation": [0, 0, 0]}, anchor=anchor)


def test_practice_starts_disabled_and_requires_a_recording_to_enable():
    practice = GhostPractice()
    assert practice.available is False and practice.enabled is False
    state = practice.snapshot()
    assert state["visible"] is False and state["lines"] == [] and state["pose"] is None
    assert state["controller"]["observed"] is False
    with pytest.raises(ValueError, match="No permitted successful teaching recording"):
        practice.set_enabled(True, player_pose=player())


def test_on_restarts_from_beginning_and_loops_at_normal_speed():
    practice = GhostPractice(capture(), context=context_for())
    assert practice.enabled is False
    state = practice.set_enabled(True, player_pose=player())
    assert state["enabled"] is True and state["speed"] == 1.0 and state["loop"] is True
    assert state["cursor"] == 0.0
    practice.update(10)
    assert practice.update(10.5)["cursor"] == pytest.approx(0.5)
    # Turning On again restarts from the first sample.
    restarted = practice.set_enabled(True, player_pose=player())
    assert restarted["cursor"] == 0.0
    # Normal speed only: the practice flow exposes no rate control.
    assert not hasattr(practice, "set_speed")
    assert restarted["controls"] == ["toggle"]


def test_loop_wraps_to_the_recorded_beginning_and_keeps_the_anchor():
    practice = GhostPractice(capture(), context=context_for())
    practice.set_enabled(True, player_pose=player())
    practice.update(100)
    anchor = deepcopy(practice._anchor)
    wrapped = practice.update(102.5)
    assert wrapped["cursor"] == pytest.approx(0.5)
    assert practice._anchor == anchor
    assert wrapped["visible"] is True


def test_off_hides_pose_lines_and_controller_immediately_before_any_packet():
    practice = GhostPractice(capture(), context=context_for())
    practice.set_enabled(True, player_pose=player())
    practice.update(10)
    assert practice.snapshot()["visible"] is True
    off = practice.set_enabled(False)
    assert off["enabled"] is False and off["visible"] is False
    assert off["pose"] is None and off["lines"] == [] and off["coach_actions"] is None
    assert off["controller"]["observed"] is False
    assert off["controller"]["actions"] is None
    # A later update must not resurrect the hidden ghost.
    assert practice.update(11)["visible"] is False


def test_toggle_flips_state_and_off_then_on_reanchors_to_the_new_player_pose():
    practice = GhostPractice(capture(), context=context_for())
    first = practice.toggle(player_pose=player())
    assert first["enabled"] is True
    practice.update(10)
    practice.toggle()
    assert practice.enabled is False
    moved = player(position=(0, 0, 17.01))
    practice.toggle(player_pose=moved)
    state = practice.update(20)
    assert state["visible"] is True
    # The new anchor is the moved player pose plus the forward offset.
    assert state["pose"]["position"][1] == pytest.approx(300, abs=1e-6)


def test_missing_player_pose_waits_instead_of_inventing_a_placement():
    practice = GhostPractice(capture(), context=context_for())
    state = practice.set_enabled(True)
    assert state["status"] == "waiting_for_player" and state["visible"] is False
    assert practice.update(10)["visible"] is False
    assert practice.update(10.1, player_pose=player())["visible"] is True


def test_packet_gap_hides_pose_and_ghost_inputs_without_inventing_motion():
    practice = GhostPractice(capture(gap=True), context=context_for())
    practice.set_enabled(True, player_pose=player())
    practice.update(100)
    gap = practice.update(100 + 29.5 / 60)
    assert gap["status"] == "capture_gap"
    assert gap["pose"] is None and gap["lines"] == [] and gap["coach_actions"] is None
    assert gap["controller"]["observed"] is False
    assert gap["controller"]["controls"]["cross"] is None


def test_clock_restart_restarts_the_demonstration_from_its_beginning():
    practice = GhostPractice(capture(), context=context_for())
    practice.set_enabled(True, player_pose=player())
    practice.update(10)
    practice.update(11)
    assert practice.cursor > 0
    restarted = practice.update(1)
    assert restarted["cursor"] == 0.0


def test_wrong_lesson_or_setup_is_refused_at_load_even_without_explicit_context():
    practice = GhostPractice(context=context_for())
    other = capture(lesson_id="flip-reset")
    with pytest.raises(ValueError, match="lesson version"):
        practice.load(other)
    assert practice.available is False
    mismatched = capture()
    mismatched["metadata"]["starting_state"]["car"]["position"][0] = 900
    with pytest.raises(ValueError, match="starting_state"):
        GhostPractice(context=context_for()).load(mismatched)


def test_personal_attempt_is_never_labelled_a_validated_demonstration():
    practice = GhostPractice(capture(), context=context_for())
    state = practice.snapshot()
    assert state["provenance"]["personal"] is True
    assert state["provenance"]["independently_validated"] is False
    assert "expert" not in state["label"].lower()
    assert "unverified" not in state["label"].lower() or "imported" in state["label"].lower()
    with pytest.raises(ValueError, match="actual successful"):
        GhostPractice(context=context_for()).load(capture(), kind="reference")


def test_invalid_recording_is_rejected_with_existing_validation():
    value = capture()
    value["schema_version"] = 99
    with pytest.raises(ValueError, match="Unsupported recording version"):
        GhostPractice(context=context_for()).load(value)
    with pytest.raises(ValueError):
        validate_recording(value)


def test_ball_and_wall_drills_expose_unsupported_context_and_car_drills_are_supported():
    assert practice_support("speed-flip")["supported"] is True
    for lesson_id in ("flip-reset", "dribble-flick", "power-shots", "shot-placement"):
        support = practice_support(lesson_id)
        assert support["supported"] is False
        assert "ball" in support["reason"]


def test_ghost_outline_has_car_cues_and_no_collision_actor():
    practice = GhostPractice(capture(), context=context_for())
    practice.set_enabled(True, player_pose=player())
    lines = practice.update(10)["lines"]
    styles = {line["style"] for line in lines}
    assert {"outline", "front", "roof", "underside", "wheel"} <= styles
    assert len([line for line in lines if line["style"] == "wheel"]) == 16
    assert all(set(line) == {"start", "end", "style"} for line in lines)
    assert ghost_lines(None) == []


def test_snapshot_never_claims_player_input_or_raw_controller_capture():
    practice = GhostPractice(capture(), context=context_for())
    practice.set_enabled(True, player_pose=player())
    state = practice.update(10)
    assert state["player_input_applied"] is False
    assert state["controller"]["source"] == "ghost"
    assert state["controller"]["physical_button_capture"] is False
    assert state["controller"]["capture"] == "logical_game_actions"
    assert "PlayerInput" not in state and "set_state" not in state


def test_snapshot_is_a_copy_and_recording_is_not_mutated():
    value = capture()
    original = deepcopy(value)
    practice = GhostPractice(value, context=context_for())
    practice.set_enabled(True, player_pose=player())
    state = practice.update(10)
    state["pose"]["position"][0] = -999
    state["coach_actions"]["boost"] = False
    state["provenance"]["source"]["kind"] = "fake_expert"
    assert value == original
    assert practice.snapshot()["coach_actions"]["boost"] is True
