"""Build, smoke-check, and compile a Windows test installer from clean source."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tomllib
import uuid

import build_native_candidate as candidate
from smoke_native_candidate import ARTIFACTS, bundle_inventory, main as smoke_main, validate_bundle


ROOT = Path(__file__).resolve().parents[1]
# ISCC.exe from the SHA-256-pinned official Inno Setup 6.7.3 installer.
COMPILER_SHA256 = "0a8757031b33777e4c9cbffee40f11a5062b36d25cbe144c1db73b6102b80ad7"


def clean_source_commit(root: Path = ROOT) -> str:
    source = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    changed = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=normal"],
                                      cwd=root, text=True)
    if changed.strip():
        raise RuntimeError("Commit reviewed source changes before building a traceable installer")
    return source


def verify_inputs(root: Path = ROOT) -> tuple[Path, str]:
    source = clean_source_commit(root)
    bundle = candidate.default_bundle(root)
    validated = validate_bundle(bundle)
    current = candidate.verify_candidate(root)
    if validated["manifest"] != current or current["source_commit"] != source:
        raise RuntimeError("Candidate bundle must match the current source and staged runtime")
    smoke = json.loads((root / "build/native-menu-candidate-smoke-receipt.json").read_text(encoding="utf-8"))
    if smoke.get("passed") is not True or smoke.get("distribution") != "developer_candidate":
        raise RuntimeError("A successful native candidate package smoke receipt is required")
    if set(smoke.get("artifacts", {})) != set(ARTIFACTS):
        raise RuntimeError("The smoke receipt must identify every candidate artifact")
    for relative, expected in smoke["artifacts"].items():
        if hashlib.sha256((bundle / relative).read_bytes()).hexdigest() != expected:
            raise RuntimeError(f"Candidate changed after its smoke check: {relative}")
    if smoke.get("bundle_files") != bundle_inventory(bundle):
        raise RuntimeError("Candidate file inventory changed after its smoke check")
    if {item.name for item in bundle.glob("*.exe")} != {"MyCareerTraining.exe"}:
        raise RuntimeError("The candidate must expose only one player application")
    return bundle, source


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, required=True, help="Verified Inno Setup 6.7.3 ISCC.exe")
    args = parser.parse_args()
    compiler = args.compiler.resolve(strict=True)
    if hashlib.sha256(compiler.read_bytes()).hexdigest() != COMPILER_SHA256:
        raise RuntimeError("Use the verified Inno Setup 6.7.3 compiler from the build guide")
    source_before = clean_source_commit()
    # Always rebuild here: an old frozen Python executable can otherwise carry
    # dirty source even after those edits were reverted and HEAD is clean.
    candidate.build_candidate(ROOT, freeze=True, clean_freeze=True)
    if clean_source_commit() != source_before:
        raise RuntimeError("Source commit changed during the installer build")
    if smoke_main(["--bundle", str(candidate.default_bundle(ROOT))]):
        raise RuntimeError("Fresh candidate failed its package smoke check")
    _, source = verify_inputs()
    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    output = ROOT / "build/native-candidate/installers"
    staging = output / (".staging-" + uuid.uuid4().hex)
    staging.mkdir(parents=True, exist_ok=False)
    subprocess.run([str(compiler), f"/DAppVersion={version}",
                    f"/DBuildId={source[:12]}", f"/O{staging}", str(ROOT / "packaging/native-candidate.iss")],
                   cwd=ROOT, check=True)
    if verify_inputs()[1] != source:
        raise RuntimeError("Source commit changed while compiling the installer")
    filename = f"MyCareerTraining-Windows-Test-{source[:12]}-Setup.exe"
    produced = staging / filename
    if not produced.is_file() or produced.is_symlink() or getattr(produced.lstat(), "st_file_attributes", 0) & 0x400:
        raise RuntimeError("Compiler did not produce a new regular installer file")
    if produced.stat().st_size == 0:
        raise RuntimeError("Compiler produced an empty installer")
    installer = output / filename
    produced.replace(installer)
    staging.rmdir()
    receipt = {"source_commit": source, "installer": installer.name,
               "sha256": hashlib.sha256(installer.read_bytes()).hexdigest(),
               "bytes": installer.stat().st_size, "package_smoke_passed": True,
               "compiler_sha256": COMPILER_SHA256, "compiler_version": "6.7.3",
               "installer_lifecycle_verified": False, "gameplay_verified": False,
               "production_ready": False}
    installer.with_suffix(".json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
