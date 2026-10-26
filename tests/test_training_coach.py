"""Transport tests use generated fixtures; none are distributable teaching demos."""

from copy import deepcopy
import math

import pytest

from my_career_training.training import (
    GhostPlayback,
    TrainingEngine,
    coaching_preferences,
    configure_lesson,
    controller_display,
    lesson_coaching,
    recording_provenance,
    reference_availability,
)
from my_career_training.training.recordings import Recorder, validate_recording


def capture(*, reference=False, gap=False):
    lesson = configure_lesson("speed-flip")
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
        result["metadata"]["source"] = {"kind": "actual_execution", "origin": "Test fixture only, not a real demo"}
        result["metadata"]["permission"] = {"distribute": True, "basis": "Test fixture only"}
    return result


def test_watch_playback_holds_buttons_while_interpolating_pose_and_handles_gaps():
    value = capture(gap=True)
    player = GhostPlayback(value)
    player.update(100)
    sampled = player.update(100 + 29.5 / 60)
    assert sampled["status"] == "capture_gap"
    assert sampled["pose"] is None and sampled["coach_actions"] is None
    assert sampled["controller"]["controls"]["cross"] is None
    value["samples"][30]["packet_gap"] = False
    player.load(value)
    player.update(100)
    sampled = player.update(100 + 29.5 / 60)
    assert sampled["pose"]["position"][0] == pytest.approx(147.5)
    assert sampled["coach_actions"]["jump"] is False
    after_edge = player.update(100.5)
    assert after_edge["coach_actions"]["jump"] is True


def test_watch_pause_resume_seek_rate_and_loop_have_no_clock_catchup():
    player = GhostPlayback(capture())
    player.update(10)
    assert player.update(10.2)["cursor"] == pytest.approx(.2)
    player.pause()
    assert player.update(20)["cursor"] == pytest.approx(.2)
    player.resume()
    assert player.update(30)["cursor"] == pytest.approx(.2)
    assert player.update(30.2)["cursor"] == pytest.approx(.4)
    player.seek(1)
    player.set_speed(.25)
    player.update(40)
    assert player.update(40.4)["cursor"] == pytest.approx(1.1)
    player.set_loop(True)
    player.seek(1.95)
    player.update(50)
    assert player.update(50.4)["cursor"] == pytest.approx(.05)


def test_lead_mode_tracks_attempt_clock_restarts_and_pause_is_stable():
    player = GhostPlayback(capture(), mode="lead", lead_seconds=.3, loop=True)
    assert player.update(5, attempt_seconds=0)["cursor"] == pytest.approx(.3)
    assert player.update(5.2, attempt_seconds=.2)["cursor"] == pytest.approx(.5)
    player.pause()
    assert player.update(6, attempt_seconds=1)["cursor"] == pytest.approx(.5)
    player.resume()
    assert player.update(6.1, attempt_seconds=1.1)["cursor"] == pytest.approx(.5)
    assert player.update(6.2, attempt_seconds=1.2)["cursor"] == pytest.approx(.6)
    assert player.update(6.3, attempt_seconds=0)["cursor"] == pytest.approx(.3)


def test_lead_waits_for_an_actual_attempt_clock_and_clock_restart_pauses():
    player = GhostPlayback(capture(), mode="lead")
    assert player.update(10)["status"] == "waiting_for_attempt"
    assert player.update(11, attempt_seconds=0)["cursor"] == pytest.approx(.75)
    reset = player.update(1, attempt_seconds=.1)
    assert reset["status"] == "clock_restarted" and reset["playing"] is False


def test_exact_loop_boundary_keeps_playing_and_ended_lead_follows_new_retry():
    player = GhostPlayback(capture(), loop=True)
    player.update(1)
    at_boundary = player.update(3)
    assert at_boundary["cursor"] == 0 and at_boundary["playing"] is True
    player = GhostPlayback(capture(), mode="lead", lead_seconds=.25)
    player.update(1, attempt_seconds=0)
    assert player.update(3, attempt_seconds=2)["status"] == "ended"
    retry = player.update(3.1, attempt_seconds=0)
    assert retry["playing"] is True and retry["cursor"] == .25


def test_stop_hides_coach_and_clamps_timeline_to_real_samples_not_claimed_duration():
    value = capture()
    value["duration"] = 20
    player = GhostPlayback(value)
    end = player.seek(30)
    assert end["duration"] == 2 and end["cursor"] == 2
    player.stop()
    stopped = player.snapshot()
    assert stopped["pose"] is None and stopped["coach_actions"] is None and stopped["lines"] == []
    assert stopped["controller"]["observed"] is False


@pytest.mark.parametrize("command,value", [("set_speed", True), ("set_speed", .1),
                                           ("seek", -1), ("seek", math.nan),
                                           ("set_loop", "false")])
def test_playback_controls_reject_invalid_values(command, value):
    player = GhostPlayback(capture())
    with pytest.raises(ValueError):
        getattr(player, command)(value)


def test_playback_never_mutates_recordings_or_applies_replayed_actions_to_human():
    value = capture()
    original = deepcopy(value)
    player = GhostPlayback(value)
    state = player.update(10)
    assert state["player_input_applied"] is False
    assert "PlayerInput" not in state and "set_state" not in state
    assert set(state["view_targets"]) == {"chase", "side", "top"}
    state["coach_actions"]["boost"] = False
    state["pose"]["position"][0] = -999
    state["provenance"]["source"]["kind"] = "fake_expert"
    assert value == original
    assert player.snapshot()["coach_actions"]["boost"] is True


def test_no_reference_is_honest_and_personal_success_is_not_an_expert():
    empty = GhostPlayback().snapshot()
    assert empty["available"] is False and "unavailable" in empty["label"]
    assert reference_availability([capture()])["available"] is False
    with pytest.raises(ValueError, match="actual successful"):
        GhostPlayback().load(capture(), kind="reference")
    provenance = recording_provenance(capture())
    assert provenance["personal"] is True and provenance["reference_eligible"] is False
    assert provenance["independently_validated"] is False
    assert "expert" not in provenance["label"].lower()


def test_imported_reference_claim_is_not_a_certificate_and_permission_requires_true():
    value = capture(reference=True)
    value["independently_validated"] = True
    value["label"] = "Verified expert world champion"
    reference = GhostPlayback()
    state = reference.load(value, kind="reference")
    assert state["provenance"]["reference_eligible"] is True
    assert state["provenance"]["independently_validated"] is False
    assert "unverified" in state["label"]
    availability = reference_availability([value])
    assert availability["available"] is True and availability["validated_demo_available"] is False
    value["metadata"]["permission"]["distribute"] = "false"
    with pytest.raises(ValueError, match="distribution permission"):
        validate_recording(value, require_reference=True)


def test_compatibility_rejects_a_different_start_and_unknown_version():
    value, context = capture(), capture()
    context["metadata"]["starting_state"]["car"]["position"][0] = 900
    with pytest.raises(ValueError, match="starting_state"):
        GhostPlayback().load(value, context=context)
    assert reference_availability([capture(reference=True)], context=context)["available"] is False


def test_ps_model_shows_configurable_logical_actions_never_raw_hardware_claim():
    actions = capture()["samples"][30]["actions"]
    model = controller_display(actions, {"boost": "r1", "jump": "square", "handbrake": "l1"})
    assert model["layout"] == "playstation" and model["observed"] is True
    assert model["physical_button_capture"] is False
    assert model["controls"]["r1"] == model["controls"]["square"] == 1
    assert model["controls"]["circle"] == model["controls"]["cross"] == 0
    assert model["controls"]["r2"] == 1 and model["controls"]["l2"] == 0
    reverse = controller_display({**actions, "throttle": -.5})
    assert reverse["controls"]["l2"] == .5 and reverse["controls"]["r2"] == 0


def test_axes_are_sample_held_and_shared_axes_never_sum_past_the_observed_value():
    actions = {**capture()["samples"][0]["actions"], "steer": .6, "yaw": .6, "roll": .6, "pitch": -.8}
    model = controller_display(actions)
    assert model["sticks"]["left"] == {"x": .6, "y": -.8}
    actions["steer"] = float("nan")
    missing = controller_display(actions)
    assert missing["actions"] is None and missing["controls"]["cross"] is None
    assert controller_display(None)["observed"] is False


def test_coaching_preferences_are_independent_and_invalid_settings_do_not_change_defaults():
    prefs = coaching_preferences({"ghost": False, "loop": False, "lead_seconds": .5,
                                  "controller_position": "bottom_left", "bindings": {"boost": "r1"}})
    assert prefs["ghost"] is False and prefs["loop"] is False
    assert prefs["bindings"]["boost"] == "r1"
    assert coaching_preferences()["bindings"]["boost"] == "circle"
    with pytest.raises(ValueError):
        coaching_preferences({"lead_seconds": 99})
    with pytest.raises(ValueError):
        coaching_preferences({"bindings": {"boost": "made_up_button"}})


def test_finish_rectangle_is_labelled_and_stage_checks_require_observed_evidence():
    lesson = configure_lesson("speed-flip")
    events = [{"name": "first_jump", "confidence": "observed"},
              {"name": "diagonal_dodge", "confidence": "uncertain"}]
    feedback = lesson_coaching(lesson, events)
    assert feedback["targets"][0]["label"] == "FINISH"
    assert "rectangle" in feedback["targets"][0]["purpose"]
    assert feedback["stages"][0]["complete"] is True
    assert feedback["stages"][1]["complete"] is False and feedback["stages"][1]["uncertain"] is True
    assert feedback["next_stage"] == 1
    assert "Confirming" in lesson_coaching(lesson, state="ready")["message"]
    assert TrainingEngine("speed-flip").summary()["coaching"]["targets"][0]["label"] == "FINISH"


def test_flip_reset_stage_accepts_plain_dodge_instead_of_requiring_diagonal_dodge():
    feedback = lesson_coaching(configure_lesson("flip-reset"), [{"name": "dodge", "confidence": "observed"}])
    assert feedback["stages"][0]["complete"] is True


def test_persisted_playback_settings_initialize_and_update_actual_coach():
    from my_career_training.game_worker import GameSession
    from types import SimpleNamespace
    prefs = coaching_preferences()
    coach = GhostPlayback(mode=prefs["mode"], speed=prefs["playback_speed"],
                          lead_seconds=prefs["lead_seconds"], loop=prefs["loop"])
    assert coach.speed == 1
    session = SimpleNamespace(coach=coach, coaching_preferences=prefs)
    GameSession.handle_command(session, {"type": "coaching", "preferences": {"playback_speed": .25}})
    assert session.coaching_preferences["playback_speed"] == .25 and coach.speed == .25
    with pytest.raises(ValueError, match="speed must"):
        coaching_preferences({"playback_speed": True})


def _legacy_playback_backend(recordings):
    from types import SimpleNamespace
    sent, pending, cleared = [], [], []
    backend = SimpleNamespace(
        _worker_active=lambda: True, request={"lesson_id": "speed-flip", "variants": {}},
        _recordings=lambda _id: recordings,
        document={"settings": {"training_display": {"mode": "lead", "lead_seconds": 1.25}}},
        session_id="test-session", _ghost_practice_enabled=True, _ghost_pending={},
        telemetry={"ghost_practice": {"available": True, "enabled": True, "visible": True}})

    def send(kind, **data):
        sent.append((kind, data))
        return f"command-{len(sent)}"

    backend._send = send
    def remember(command_id, kind, lesson_id, *args, **kwargs):
        practice = kwargs.get("practice", args[0] if args else None)
        pending.append((command_id, kind, lesson_id, practice))

    backend._remember_ghost_command = remember
    backend._clear_ghost_practice_state = lambda **kwargs: cleared.append(kwargs)
    backend._sync_ghost_assistance = lambda *_args: None
    return backend, sent, pending, cleared


def test_legacy_qml_and_imgui_playback_payloads_keep_best_compatible_recording():
    from my_career_training.bridge import Backend
    value = capture()
    other_variant = deepcopy(value)
    other_variant["variant"]["side"] = "left"
    other_variant["duration"] = 0.5  # A shorter incompatible attempt must not win.
    cases = [
        ({"id": "speed-flip", "kind": "personal_best"}, "lead", 1.25),
        ({"id": "speed-flip", "mode": "watch"}, "watch", 1.25),
        ({"id": "speed-flip", "mode": "lead", "lead_seconds": 0.5}, "lead", 0.5),
    ]

    for payload, expected_mode, expected_lead in cases:
        backend, sent, pending, cleared = _legacy_playback_backend([other_variant, value])
        Backend._action(backend, "play_recording", payload)

        assert len(sent) == 1 and sent[0][0] == "play_recording"
        command = sent[0][1]
        assert command["recording"]["variant"] == value["variant"]
        assert command["recording"]["duration"] == value["duration"]
        assert command["mode"] == expected_mode and command["lead_seconds"] == expected_lead
        assert command["practice"] is False
        assert pending == [("command-1", "play_recording", "speed-flip", False)]
        assert cleared == []
        assert backend._ghost_practice_enabled is True


@pytest.mark.parametrize("payload", [
    {"id": "speed-flip", "mode": "slow"},
    {"id": "speed-flip", "mode": "watch", "lead_seconds": math.nan},
    {"id": "speed-flip", "kind": "unrecognized"},
])
def test_legacy_playback_rejects_unsupported_mode_and_values_without_dispatch(payload):
    from my_career_training.bridge import Backend
    backend, sent, pending, cleared = _legacy_playback_backend([capture()])

    with pytest.raises(ValueError):
        Backend._action(backend, "play_recording", payload)

    assert sent == []
    assert pending == []
    assert cleared == []
