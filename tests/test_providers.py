"""Integrity, packet adaptation and real learned-model inference checks."""
import copy
import hashlib
import importlib.util
import json
import math
import shutil
import sys

import pytest

from my_career_training.bots.providers import (
    BASELINE_ID, LICENSE_SHA256, MODELS, RESOURCE_DIR, ProviderUnavailable,
    create_controller, ensure_provider, model_self_test, provider_catalog,
)

HAS_RUNTIME = all(importlib.util.find_spec(name) is not None for name in ("torch", "numpy"))
runtime = pytest.mark.skipif(not HAS_RUNTIME and sys.platform != "win32",
                            reason="CPU inference runtime is bundled with the Windows build")


def game_frame(size=3, main_team=0):
    from my_career_training.bots.learned import BOOST_LOCATIONS
    cars = []
    for team in (0, 1):
        sign = 1 if team == 0 else -1
        for slot in range(size):
            cars.append({"index": len(cars), "team": team,
                         "position": [(slot - (size - 1) / 2) * 1400, -sign * 3200, 17],
                         "velocity": [50, sign * 600, 0], "rotation": [.1, sign * math.pi / 2, -.05],
                         "angular_velocity": [.2, -.1, .3], "boost": 66, "wheel_contact": True,
                         "has_jumped": False, "has_dodged": False, "has_double_jumped": False})
    return {"time": 10., "frame_num": 1200, "cars": cars,
            "ball": {"position": [350, 400, 120], "velocity": [200, -400, 20],
                     "angular_velocity": [0, 1, 0]},
            "boosts": [{"position": list(pos), "active": i % 3 != 0, "is_full": pos[2] > 72}
                       for i, pos in enumerate(BOOST_LOCATIONS)]}, main_team * size


def test_pinned_models_license_and_manifest_match_actual_bundled_files():
    receipt = json.loads((RESOURCE_DIR / "manifest.json").read_text())
    assert hashlib.sha256((RESOURCE_DIR / "LICENSE-Necto.txt").read_bytes()).hexdigest() == LICENSE_SHA256
    for provider_id, model in MODELS.items():
        file = RESOURCE_DIR / model["filename"]
        assert hashlib.sha256(file.read_bytes()).hexdigest() == model["sha256"]
        entry = next(item for item in receipt["models"] if item["id"] == provider_id)
        assert entry["sha256"] == model["sha256"] and entry["size"] == file.stat().st_size
    assert receipt["license"] == "CC-BY-NC-SA-4.0"


def test_catalog_does_not_claim_current_rank_evidence_or_scaling():
    result = provider_catalog()
    assert {item["id"] for item in result} == {BASELINE_ID, "necto", "nexto"}
    for item in result[1:]:
        assert item["supported_formats"] == [1, 2, 3]
        assert item["evaluated_formats"] == [] and item["rank_certification"] is None
        assert "historical" in item["rank_claim"]
        assert item["difficulty_scaling"] is False and item["roles"] == []
        assert item["offline_only"] is True


def test_unavailable_unknown_and_unsupported_never_fall_back(tmp_path):
    for provider_id in ("not-a-provider", "../../model", "", None):
        with pytest.raises(ProviderUnavailable):
            create_controller(provider_id)
    for size in (4, 0, True, "3"):
        with pytest.raises(ProviderUnavailable, match="support 1v1"):
            ensure_provider("necto", size)
    with pytest.raises(ProviderUnavailable, match="integrity"):
        ensure_provider("necto", 3, resources=tmp_path)
    assert create_controller(BASELINE_ID).manifest()["id"] == BASELINE_ID


def test_tampered_artifact_and_missing_license_rejected_before_model_load(tmp_path):
    shutil.copy(RESOURCE_DIR / "necto-model.pt", tmp_path / "necto-model.pt")
    shutil.copy(RESOURCE_DIR / "LICENSE-Necto.txt", tmp_path / "LICENSE-Necto.txt")
    with (tmp_path / "necto-model.pt").open("r+b") as stream:
        stream.seek(200)
        stream.write(b"changed")
    with pytest.raises(ProviderUnavailable, match="integrity"):
        create_controller("necto", resources=tmp_path)
    shutil.copy(RESOURCE_DIR / "necto-model.pt", tmp_path / "necto-model.pt")
    (tmp_path / "LICENSE-Necto.txt").unlink()
    with pytest.raises(ProviderUnavailable, match="license"):
        create_controller("necto", resources=tmp_path)
    assert not next(item for item in provider_catalog(tmp_path) if item["id"] == "necto")["available"]


@runtime
def test_real_cpu_models_infer_in_all_supported_formats():
    receipt = model_self_test()
    assert receipt["ok"] and receipt["device"] == "cpu" and receipt["game_tested"] is False
    for item in receipt["providers"]:
        assert item["cpu_inference"] and [sample["format"] for sample in item["samples"]] == [1, 2, 3]
        for sample in item["samples"]:
            controls = sample["controls"]
            assert len(controls) == 8
            assert any(value != 0 for value in controls.values())


@runtime
@pytest.mark.parametrize("provider_id", ["necto", "nexto"])
def test_real_models_load_from_unicode_paths_through_python_binary_stream(tmp_path, monkeypatch, provider_id):
    import torch
    directory = tmp_path / "My Career Training é 球"
    directory.mkdir()
    model = MODELS[provider_id]
    shutil.copy(RESOURCE_DIR / model["filename"], directory / model["filename"])
    shutil.copy(RESOURCE_DIR / "LICENSE-Necto.txt", directory / "LICENSE-Necto.txt")
    original_load = torch.jit.load
    seen = []

    def load_from_stream(file, *args, **kwargs):
        # A path-only success on macOS would miss the Windows regression: this
        # assertion requires the Unicode-safe buffer overload on every platform.
        assert not isinstance(file, (str, bytes))
        assert hasattr(file, "read") and file.readable() and "é 球" in file.name
        seen.append(file.name)
        return original_load(file, *args, **kwargs)

    monkeypatch.setattr(torch.jit, "load", load_from_stream)
    bot = create_controller(provider_id, resources=directory)
    frame, index = game_frame(2)
    assert any(bot.step(frame, index).values())
    assert len(seen) == 1


@runtime
def test_pad_order_player_identity_and_orientation_survive_v5_conversion():
    import numpy as np
    from my_career_training.bots.learned import build_state, rotation_matrix
    frame, index = game_frame(3, 1)
    expected = [float(pad["active"]) for pad in frame["boosts"]]
    frame["boosts"].reverse()
    state, main = build_state(frame, index)
    assert state.boost_pads.tolist() == expected
    assert main.car_id == index and state.players[0] is main
    assert [p.team_num for p in state.players] == [1, 1, 1, 0, 0, 0]
    np.testing.assert_allclose(rotation_matrix([0, math.pi / 2, 0])[:, 0], [0, 1, 0], atol=1e-6)
    np.testing.assert_allclose(main.inverted_car_data.position, main.car_data.position * [-1, -1, 1])
    np.testing.assert_allclose(main.inverted_car_data.rotation_mtx()[:, 0], main.car_data.forward() * [-1, -1, 1])
    assert main.has_flip and main.boost_amount == .66


@runtime
def test_policy_responds_to_real_observation_changes_without_mutating_frames():
    for provider_id in MODELS:
        outputs = set()
        for ball in ([2500, -1800, 93], [-2500, -1800, 93], [0, -4500, 500], [0, 3200, 1200]):
            frame, index = game_frame(2)
            frame["ball"]["position"] = ball
            original = copy.deepcopy(frame)
            controls = create_controller(provider_id).step(frame, index)
            outputs.add(tuple(controls.items()))
            assert frame == original
        assert len(outputs) > 1, provider_id


@runtime
def test_tick_cadence_rewind_terminal_and_demolition():
    for provider_id in MODELS:
        bot = create_controller(provider_id)
        frame, index = game_frame(1)
        first = bot.step(frame, index)
        # The same game packet cannot advance the model or kickoff sequence.
        assert bot.step(frame, index) == first
        frame["frame_num"] += 1
        frame["time"] += 1 / 120
        bot.step(frame, index)
        frame["cars"][index]["is_demolished"] = True
        frame["frame_num"] += 1
        frame["time"] += 1 / 120
        assert not any(bot.step(frame, index).values())
        frame["cars"][index]["is_demolished"] = False
        frame["frame_num"], frame["time"] = 500, 5
        assert any(bot.step(frame, index).values())
        frame["match_ended"] = True
        # A phase transition can arrive without an advancing frame number.
        assert not any(bot.step(frame, index).values())


@runtime
def test_unsupported_observations_fail_explicitly():
    bot = create_controller("nexto")
    frame, index = game_frame(1)
    frame["boosts"].pop()
    with pytest.raises(ProviderUnavailable, match="34 pads"):
        bot.step(frame, index)
    frame, index = game_frame(4)
    with pytest.raises(ProviderUnavailable, match="1v1"):
        create_controller("nexto").step(frame, index)
    frame, index = game_frame(1)
    frame["cars"][0]["velocity"][0] = float("nan")
    with pytest.raises(ProviderUnavailable, match="invalid velocity"):
        create_controller("nexto").step(frame, index)


@runtime
def test_kickoff_control_sequence_and_left_goes():
    for provider_id in MODELS:
        frame, index = game_frame(2)
        frame["is_kickoff"] = True
        frame["ball"]["position"] = [0, 0, 93]
        # Human-like same-distance teammate tie; upstream blue positive X takes kickoff.
        frame["cars"][0]["position"] = [2048, -2560, 17]
        frame["cars"][1]["position"] = [-2048, -2560, 17]
        frame["cars"][2]["position"] = [0, 4608, 17]
        frame["cars"][3]["position"] = [1000, 4000, 17]
        bot = create_controller(provider_id)
        controls = bot.step(frame, 0)
        assert bot.kickoff_index == 0 and controls["throttle"] == 1 and controls["boost"]
        other = create_controller(provider_id)
        other.step(frame, 1)
        assert other.kickoff_index == -2
        frame["frame_num"] += 60
        frame["time"] += .5
        assert bot.step(frame, 0)["jump"] is True
        frame["is_kickoff"] = False
        frame["frame_num"] += 1
        bot.step(frame, 0)
        assert bot.kickoff_index == -1
