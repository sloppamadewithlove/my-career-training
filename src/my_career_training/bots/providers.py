"""Installed bot catalog and the integrity boundary for learned policies.

Only the allowlisted, pinned models below are loadable. No arbitrary model,
Python module, command line or user-supplied Torch file is accepted.
"""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

BASELINE_ID = "mct-specialist-baseline"
SOURCE_REPOSITORY = "https://github.com/Rolv-Arild/Necto"
SOURCE_REVISION = "2e6ed7d6ed2b352e8ff529d4a12a0c9c70c28cca"
RESOURCE_DIR = Path(__file__).resolve().parent / "resources"
LICENSE_SHA256 = "1349a4b6148492b44f629e64eed676612e234fe9a839e4f3b277c1482c8849f1"
MODELS = {
    "necto": {
        "name": "Necto · Diamond practice",
        "filename": "necto-model.pt",
        "sha256": "137f94924afb0402af7ae9f12b7f2d7e47adff962afad4dbed7bf864c34c542b",
        "source_path": "rlbot-support/Necto/necto-model.pt",
        "rank_claim": "Creator's historical estimate: around Diamond; this integration is unranked",
    },
    "nexto": {
        "name": "Nexto · advanced challenge",
        "filename": "nexto-model.pt",
        "sha256": "bf5343b5eeacac6bf7cdb75dac4a5c14ba0f94d820eae75f00a211b6119d69fa",
        "source_path": "rlbot-support/Nexto/nexto-model.pt",
        "rank_claim": "Creator's historical estimate: around GC1; this integration is unranked",
    },
}
_verified_files = {}


class ProviderUnavailable(RuntimeError):
    """A selected policy cannot be used; callers must not silently substitute."""


def _verified(path, digest, force=False):
    try:
        stat = path.stat()
        key = (str(path), stat.st_size, stat.st_mtime_ns, digest)
        if not force and key in _verified_files:
            return _verified_files[key]
        with path.open("rb") as stream:
            valid = hashlib.file_digest(stream, "sha256").hexdigest() == digest
        _verified_files[key] = valid
        return valid
    except OSError:
        return False


def model_path(provider_id, resources=None):
    if provider_id not in MODELS:
        raise ProviderUnavailable(f"Unknown learned bot provider: {provider_id}")
    return Path(resources or RESOURCE_DIR) / MODELS[provider_id]["filename"]


def _runtime_present():
    try:
        return all(importlib.util.find_spec(name) is not None for name in ("numpy", "torch"))
    except (ImportError, ValueError):
        return False


def provider_catalog(resources=None):
    """JSON-safe capabilities; does not import Torch into the visible UI process."""
    from . import provider_manifest

    baseline = provider_manifest()
    baseline.update(available=True, reason="", training_target="Beginner ground practice")
    result = [baseline]
    root = Path(resources or RESOURCE_DIR)
    licensed = _verified(root / "LICENSE-Necto.txt", LICENSE_SHA256)
    runtime_present = _runtime_present()
    for provider_id, model in MODELS.items():
        installed = licensed and _verified(root / model["filename"], model["sha256"])
        reason = ""
        if not installed:
            reason = "The verified model or its license is missing. Reinstall the complete Windows build."
        elif not runtime_present:
            reason = "The bundled CPU inference runtime is missing. Reinstall the complete Windows build."
        result.append({
            "id": provider_id, "provider": provider_id, "name": model["name"],
            "version": SOURCE_REVISION, "installed": installed,
            "available": installed and runtime_present,
            "status": "ready" if installed and runtime_present else "unavailable", "reason": reason,
            "rank_certification": None, "rank_claim": model["rank_claim"],
            "supported_formats": [1, 2, 3], "evaluated_formats": [],
            "roles": [], "level_range": None, "difficulty_scaling": False,
            "capabilities": ["trained_neural_policy", "ground_play", "aerial_play", "team_play"],
            "limitations": ["Current Windows game behavior has not been evaluated",
                            "No 4v4 or nonstandard arena support", "Fixed pretrained policy; no live learning",
                            "Recruit role and level do not alter this model's decisions"],
            "source": SOURCE_REPOSITORY, "source_revision": SOURCE_REVISION,
            "license": "CC-BY-NC-SA-4.0", "model_sha256": model["sha256"],
            "offline_only": True,
        })
    return result


def ensure_provider(provider_id, format=None, resources=None):
    """Validate a selection before entering a fixture, without launching a model."""
    if type(provider_id) is not str:
        raise ProviderUnavailable("Choose an installed bot provider.")
    if provider_id == BASELINE_ID:
        if format is not None and (type(format) is not int or format not in (1, 2, 3, 4)):
            raise ProviderUnavailable("Choose 1v1, 2v2, 3v3 or 4v4.")
        return provider_catalog(resources)[0]
    if provider_id not in MODELS:
        raise ProviderUnavailable(f"Unknown bot provider: {provider_id}")
    if format is not None and (type(format) is not int or format not in (1, 2, 3)):
        raise ProviderUnavailable("Necto and Nexto support 1v1, 2v2 and 3v3. Choose a smaller format or Ground Specialists for 4v4.")
    root = Path(resources or RESOURCE_DIR)
    if not _verified(model_path(provider_id, root), MODELS[provider_id]["sha256"], force=True):
        raise ProviderUnavailable("The selected bot model failed its integrity check. Reinstall this Windows build.")
    if not _verified(root / "LICENSE-Necto.txt", LICENSE_SHA256, force=True):
        raise ProviderUnavailable("The bot model's required license is missing or changed. Reinstall this Windows build.")
    manifest = next(item for item in provider_catalog(root) if item["id"] == provider_id)
    if not manifest["available"]:
        raise ProviderUnavailable(manifest["reason"])
    return manifest


def create_controller(provider_id=BASELINE_ID, role="all-rounder", level=1, difficulty=.5, seed=0,
                      resources=None):
    """Same step(frame, player_index, intents) interface for every shipped provider."""
    ensure_provider(provider_id, resources=resources)
    if provider_id == BASELINE_ID:
        from . import SpecialistController
        return SpecialistController(role, level, difficulty, seed)
    from .learned import LearnedController
    try:
        return LearnedController(provider_id, model_path(provider_id, resources), seed=seed)
    except (ImportError, OSError, RuntimeError) as exc:
        raise ProviderUnavailable(f"{MODELS[provider_id]['name']} could not start: {exc}. Reinstall the complete Windows build.") from exc


def model_self_test():
    """Real CPU inference receipt for source and frozen Windows package checks.

    This is deliberately distinct from a Rocket League game evaluation.
    """
    import math
    import torch
    import numpy as np
    from .learned import BOOST_LOCATIONS

    receipts = []
    for provider_id in MODELS:
        manifest = ensure_provider(provider_id)
        samples = []
        for size in (1, 2, 3):
            bot = create_controller(provider_id)
            cars = []
            for team in (0, 1):
                sign = 1 if team == 0 else -1
                for slot in range(size):
                    cars.append({"index": len(cars), "team": team,
                                 "position": [(slot - (size - 1) / 2) * 1100, -sign * 3200, 17],
                                 "velocity": [0, sign * 600, 0],
                                 "rotation": [0, sign * math.pi / 2, 0],
                                 "angular_velocity": [0, 0, 0], "boost": 66,
                                 "wheel_contact": True, "has_jumped": False,
                                 "has_dodged": False, "has_double_jumped": False})
            frame = {"time": 10., "frame_num": 1200, "cars": cars,
                     "ball": {"position": [350, 400, 120], "velocity": [200, -400, 20],
                              "angular_velocity": [0, 1, 0]},
                     "boosts": [{"position": list(pos), "active": True,
                                 "is_full": pos[2] > 72} for pos in BOOST_LOCATIONS]}
            controls = bot.step(frame, 0)
            if set(controls) != {"throttle", "steer", "pitch", "yaw", "roll", "jump", "boost", "handbrake"}:
                raise ProviderUnavailable("Learned policy self-test returned incomplete controls.")
            samples.append({"format": size, "controls": controls})
        receipts.append({"id": provider_id, "model_sha256": manifest["model_sha256"],
                         "cpu_inference": True, "samples": samples})
    return {"ok": True, "device": "cpu", "torch": torch.__version__, "numpy": np.__version__,
            "game_tested": False, "providers": receipts}
