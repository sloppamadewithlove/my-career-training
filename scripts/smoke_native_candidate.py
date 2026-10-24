"""Smoke the native-menu candidate bundle without starting a game or helper.

The receipt is ``build/native-menu-candidate-smoke-receipt.json``. The normal
package smoke receipt is left untouched. Frozen UI, self-test, and worker
checks go through ``smoke_package.run_smoke`` with an offscreen isolated data
directory. ``MctNativeLauncher.exe`` is not executed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import uuid

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import build_native_candidate as candidate  # noqa: E402
from smoke_package import run_smoke  # noqa: E402

DEFAULT_RECEIPT = Path(__file__).resolve().parents[1] / "build" / "native-menu-candidate-smoke-receipt.json"
ARTIFACTS = (
    "MyCareerTraining.exe",
    "MyCareerTrainingWorker.exe",
    "_internal/my_career_training/runtime/plugins/MyCareerTraining.dll",
    "_internal/my_career_training/runtime/native/MctNativeLauncher.exe",
    "_internal/my_career_training/runtime/native/MctNativeFileView64.dll",
    "_internal/candidate-manifest.json",
)
CHECKS = (
    "candidate manifest",
    "candidate runtime allowlists",
    "PE AMD64",
    "frozen UI",
    "worker pipes",
    "RLBot checksum",
    "plugin PE exports/imports",
)


def validate_bundle(bundle: Path) -> dict:
    """Check candidate receipts and runtime trees. Does not start a process."""
    bundle = Path(bundle)
    if not bundle.is_dir():
        raise candidate.CandidateBuildError("candidate bundle is missing")
    runtime = bundle / "_internal" / "my_career_training" / "runtime"
    manifest = bundle / "_internal" / "candidate-manifest.json"
    tree = candidate.check_runtime_tree(runtime)
    body = candidate.check_manifest(manifest, runtime)
    if tree["plugin"].get("native_movie_trial") is not True or body["build"].get("native_movie_trial") is not True:
        raise candidate.CandidateBuildError("candidate bundle was not built with the native movie trial")
    if body["flags"] != candidate.FALSE_FLAGS:
        raise candidate.CandidateBuildError("candidate bundle flags must all be false")
    return {"manifest": body, "runtime": tree}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Smoke the staged native menu candidate bundle.")
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args(argv)
    bundle = (args.bundle or candidate.default_bundle()).resolve()
    receipt = args.receipt or DEFAULT_RECEIPT
    if receipt.name.casefold() == "package-smoke-receipt.json":
        print("native candidate smoke failed: refusing to overwrite the release smoke receipt", file=sys.stderr)
        return 1
    try:
        validate_bundle(bundle)
        with tempfile.TemporaryDirectory(prefix="MCT native candidate ") as temp:
            root = Path(temp)
            destination = root / "MCT native candidate é 球"
            shutil.copytree(bundle, destination)
            run_smoke(destination, root / "Player data é 球")
        _write_json(receipt, _evidence(bundle))
    except (candidate.CandidateBuildError, AssertionError, RuntimeError, OSError) as exc:
        print(f"native candidate smoke failed: {exc}", file=sys.stderr)
        return 1
    print("Native candidate smoke passed; helper was not executed and gameplay was not verified")
    return 0


def _evidence(bundle: Path) -> dict:
    artifacts = {}
    for relative in ARTIFACTS:
        path = bundle.joinpath(*Path(relative).parts)
        if not path.is_file():
            raise candidate.CandidateBuildError(f"candidate bundle is missing {relative}")
        artifacts[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "artifacts": artifacts,
        "checks": list(CHECKS),
        "distribution": "developer_candidate",
        "game_verified": False,
        "gameplay_verified": False,
        "helper_executed": False,
        "kind": "native_menu_candidate_smoke",
        "live_rocket_league": False,
        "native_host_probe": False,
        "native_movie_trial": True,
        "passed": True,
        "production_ready": False,
        "runtime_verified": False,
    }


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.staging-{uuid.uuid4().hex}")
    data = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    descriptor = os.open(temporary, flags)
    try:
        os.write(descriptor, data)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.replace(temporary, path)


if __name__ == "__main__":
    raise SystemExit(main())
