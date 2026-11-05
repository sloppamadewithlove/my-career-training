"""Synthetic input schedules only; none is a teaching demonstration."""

import hashlib
import json

import pytest

from my_career_training.training import prerecorded_inputs as inputs


def _csv(rows=None):
    # Deliberately disagreeing native-only fields make the lossy mapping observable.
    rows = rows or [
        "0,1,0.3,-0.4,0,0,0,1,0.2,0.1,-0.1,1,0.5",
        "1,0,0.1,0.4,1,1,1,0,-0.2,-0.1,0.1,0.5,-0.5",
        "2,0,0,0,0,0,0,0,0,0,0,0,0",
    ]
    return (",".join(inputs.HEADER) + "\n" + "\n".join(rows) + "\n").encode()


def _load(tmp_path, raw=None):
    raw = _csv() if raw is None else raw
    (tmp_path / inputs.INPUT_FILENAME).write_bytes(raw)
    return inputs.load_controller(tmp_path, hashlib.sha256(raw).hexdigest())


def test_maps_only_declared_logical_fields_and_pins_provisional_plan(tmp_path):
    controller = _load(tmp_path)
    first = controller.step(.025)
    assert first == {
        "throttle": 1.0, "steer": -.1, "pitch": .2, "yaw": .5, "roll": .1,
        "jump": False, "boost": False, "handbrake": False,
    }
    second = controller.step(.025 + 1 / 120)
    assert second["jump"] is True and second["boost"] is True and second["handbrake"] is True
    plan = controller.controller_plan()
    assert plan["input_sha256"] == hashlib.sha256(_csv()).hexdigest()
    assert plan["assumed_tick_rate"] == 120 and plan["rows"] == 3
    assert plan["tick_origin"] == "first_control_dispatch_after_engine_go"
    assert plan["lossy"] is True
    assert set(plan["discarded_native_fields"]) == {"ActivateBoost", "DodgeForward", "DodgeStrafe", "Jumped"}
    assert plan["sends_inputs"] is False and plan["chooses_player_index"] is False
    assert str(tmp_path) not in json.dumps(plan)


def test_reset_restarts_tick_zero_and_finish_and_exhaustion_stay_neutral(tmp_path):
    controller = _load(tmp_path)
    first = controller.step(.1)
    controller.step(.1 + 1 / 120)
    controller.reset()
    assert controller.step(2.0) == first
    controller.step(2.0 + 1 / 120)
    controller.step(2.0 + 2 / 120)
    assert controller.step(2.0 + 3 / 120) == inputs._neutral()
    assert controller.finished and not controller.interrupted
    assert controller.step(99.0) == inputs._neutral()
    controller.reset()
    controller.finish()
    assert controller.step(0.0) == inputs._neutral()


@pytest.mark.parametrize("elapsed", [True, None, float("nan"), float("inf"), -1, 0, .001, 2 / 120])
def test_bad_or_skipped_dispatch_is_neutral_and_cannot_resume(tmp_path, elapsed):
    controller = _load(tmp_path)
    controller.step(0.0)
    assert controller.step(elapsed) == inputs._neutral()
    assert controller.finished and controller.interrupted
    assert controller.step(1 / 120) == inputs._neutral()


def test_explicit_gap_stops_even_first_dispatch(tmp_path):
    controller = _load(tmp_path)
    assert controller.step(.02, {"packet_gap": True}) == inputs._neutral()
    assert controller.interrupted


@pytest.mark.parametrize("raw", [
    b"", b"unsupported,header\n", _csv().replace(b"0,1,", b"1,1,", 1),
    _csv().replace(b"1,0,0.1", b"2,0,0.1", 1),
    _csv().replace(b"0.3", b"nan", 1), _csv().replace(b"0.3", b"1.01", 1),
    _csv().replace(b"0,1,0.3", b"0,2,0.3", 1),
    _csv().replace(b"0,1,0.3", b"0,1,private-cell-value", 1),
    _csv().replace(b"0,1,0.3", b"0,1", 1),
    b"\xff", (",".join(inputs.HEADER) + "\n").encode(),
])
def test_malformed_csv_is_refused_without_echoing_private_cell_contents(tmp_path, raw):
    with pytest.raises(ValueError) as error:
        _load(tmp_path, raw)
    assert "private-cell-value" not in str(error.value)
    assert str(tmp_path) not in str(error.value)


def test_bounds_digest_and_missing_file_are_refused(tmp_path, monkeypatch):
    with pytest.raises(ValueError):
        inputs.load_controller(tmp_path, "0" * 64)
    _load(tmp_path)
    for digest in [None, "short", "A" * 64, "0" * 64]:
        with pytest.raises(ValueError):
            inputs.load_controller(tmp_path, digest)
    monkeypatch.setattr(inputs, "MAX_INPUT_BYTES", 1)
    with pytest.raises(ValueError, match="size limit"):
        _load(tmp_path)
    monkeypatch.setattr(inputs, "MAX_INPUT_BYTES", 1024 * 1024)
    monkeypatch.setattr(inputs, "MAX_INPUT_ROWS", 2)
    with pytest.raises(ValueError):
        _load(tmp_path)


def test_loaded_schedule_uses_pinned_in_memory_snapshot(tmp_path):
    controller = _load(tmp_path)
    (tmp_path / inputs.INPUT_FILENAME).write_bytes(b"changed")
    assert controller.step(0.0)["throttle"] == 1.0
    with pytest.raises(ValueError, match="pinned digest"):
        inputs.load_controller(tmp_path, controller.controller_plan()["input_sha256"])
