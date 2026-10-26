"""Build, smoke-check, and compile a Windows test installer from clean source.

Inno Setup 6.7.3 is not long-path aware. A script-relative bundle source keeps a
``packaging\\..`` prefix, so a 247-character license file becomes a 260-character
compiler path and compression fails with "The system cannot find the path
specified" even though the file exists. Deeper license paths reach 287 characters.
The compiler therefore reads a short temporary copy and a short output file.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import tomllib
import uuid

import build_native_candidate as candidate
from smoke_native_candidate import ARTIFACTS, bundle_inventory, main as smoke_main, validate_bundle


ROOT = Path(__file__).resolve().parents[1]
# ISCC.exe from the SHA-256-pinned official Inno Setup 6.7.3 installer.
COMPILER_SHA256 = "0a8757031b33777e4c9cbffee40f11a5062b36d25cbe144c1db73b6102b80ad7"
# A 260-character source path is already too long for ISCC 6.7.3.
COMPILER_PATH_LIMIT = 260


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


def _is_new_regular_file(path: Path) -> bool:
    if not path.exists():
        return False
    info = getattr(path.lstat(), "st_file_attributes", 0)
    return path.is_file() and not path.is_symlink() and not (info & 0x400)


@contextmanager
def short_compile_inputs(bundle: Path, output_name: str):
    """Copy the smoke-verified bundle into an owned short temporary directory.

    Yields the copy, its inventory, and ``<temp>/out``. Only this temporary
    directory is removed on exit. The original bundle is left in place.
    """
    expected = bundle_inventory(bundle)
    with tempfile.TemporaryDirectory(prefix="mct-") as raw:
        root = Path(raw)
        staged = root / "bundle"
        shutil.copytree(bundle, staged)
        if bundle_inventory(staged) != expected:
            raise RuntimeError("Short bundle copy does not match the smoke-verified bundle")
        compile_output = root / "out"
        compile_output.mkdir()
        longest = str(compile_output / output_name)
        longest_name = output_name
        for relative in expected:
            text = str(staged.joinpath(*Path(relative).parts))
            if len(text) > len(longest):
                longest, longest_name = text, relative
        if len(longest) >= COMPILER_PATH_LIMIT:
            raise RuntimeError(
                "Refusing to start the installer compiler: "
                f"{longest_name} is {len(longest)} characters. "
                "Inno Setup 6.7.3 cannot open source paths of 260 characters or more "
                "('The system cannot find the path specified' even when the file exists). "
                "The temporary directory is still too long."
            )
        yield staged, expected, compile_output


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
    bundle, source = verify_inputs()
    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    output = ROOT / "build/native-candidate/installers"
    staging = output / (".staging-" + uuid.uuid4().hex)
    staging.mkdir(parents=True, exist_ok=False)
    filename = f"MyCareerTraining-Windows-Test-{source[:12]}-Setup.exe"
    with short_compile_inputs(bundle, filename) as (staged_bundle, expected, compile_output):
        subprocess.run(
            [str(compiler), f"/DAppVersion={version}", f"/DBuildId={source[:12]}",
             f"/DBundleDir={staged_bundle}", f"/O{compile_output}",
             str(ROOT / "packaging/native-candidate.iss")],
            cwd=ROOT, check=True)
        if bundle_inventory(staged_bundle) != expected:
            raise RuntimeError("Compiler input copy changed during compilation")
        if verify_inputs()[1] != source:
            raise RuntimeError("Source commit changed while compiling the installer")
        short_produced = compile_output / filename
        if not _is_new_regular_file(short_produced):
            raise RuntimeError("Compiler did not produce a new regular installer file")
        if short_produced.stat().st_size == 0:
            raise RuntimeError("Compiler produced an empty installer")
        (staging / filename).write_bytes(short_produced.read_bytes())
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
