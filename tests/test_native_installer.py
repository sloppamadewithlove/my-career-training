"""Regression checks for native candidate installer provenance.

All compilers, freezing, smoke processes, and installer compilation are mocked.
No game, real compiler, or installer is started.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tests"))

import build_native_candidate as candidate  # noqa: E402
import build_native_installer as installer  # noqa: E402
import smoke_native_candidate as smoke  # noqa: E402
import test_native_candidate as native_fixtures  # noqa: E402

COMMIT = "a" * 40


@pytest.fixture(autouse=True)
def pin_mock_compiler(monkeypatch):
    monkeypatch.setattr(installer, "COMPILER_SHA256", hashlib.sha256(b"mock compiler marker").hexdigest())


@pytest.fixture
def packaged_world(tmp_path, monkeypatch):
    monkeypatch.setattr(candidate, "RLBOT_SHA256", hashlib.sha256(native_fixtures.CORE).hexdigest())
    world = native_fixtures._build(tmp_path, monkeypatch)
    bundle = candidate.default_bundle(world.root)
    native_fixtures._as_bundle(world, bundle)
    for relative in smoke.ARTIFACTS:
        path = bundle.joinpath(*Path(relative).parts)
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"synthetic player artifact: " + relative.encode("utf-8"))
    return world, bundle


def test_candidate_verification_rejects_dependency_drift(packaged_world):
    world, _bundle = packaged_world
    dependencies = world.root / "plugin" / "DEPENDENCIES.json"
    dependencies.write_text(json.dumps({"json": {"version": "3.13.0"}}) + "\n", encoding="utf-8")

    with pytest.raises(candidate.CandidateBuildError, match="source hashes|dependencies"):
        candidate.verify_candidate(world.root)


def test_candidate_built_from_same_commit_dirty_source_is_rejected_after_revert(tmp_path):
    root = native_fixtures._seed(tmp_path)
    source = root / "plugin" / "src" / "MyCareerTraining.cpp"
    clean_source = source.read_bytes()
    source.write_bytes(b"int plugin; // temporary local edit\n")

    # The native compiler is mocked by the existing fixture runner. The manifest
    # records the dirty source bytes even though the source is reverted below.
    candidate.build_candidate(root, runner=native_fixtures._runner(root), source_commit=COMMIT)
    source.write_bytes(clean_source)

    with pytest.raises(candidate.CandidateBuildError, match="source hashes"):
        candidate.verify_candidate(root)


def test_stale_smoke_receipt_rejects_unlisted_bundle_file(packaged_world, monkeypatch):
    world, bundle = packaged_world
    monkeypatch.setattr(installer, "clean_source_commit", lambda root=world.root: COMMIT)
    receipt = world.root / "build" / "native-menu-candidate-smoke-receipt.json"
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(json.dumps(smoke._evidence(bundle)), encoding="utf-8")

    late_file = bundle / "_internal" / "late-output" / "nested" / "late-helper.dat"
    late_file.parent.mkdir(parents=True)
    late_file.write_bytes(b"added after smoke")

    with pytest.raises(RuntimeError, match="inventory changed"):
        installer.verify_inputs(world.root)


def test_smoke_refuses_helper_outside_documented_internal_path(packaged_world, tmp_path, monkeypatch):
    _world, bundle = packaged_world
    expected = bundle / "_internal" / "MyCareerTrainingWorker.exe"
    misplaced = bundle / "_internal" / "my_career_training" / "MyCareerTrainingWorker.exe"
    expected.unlink()
    misplaced.parent.mkdir(parents=True, exist_ok=True)
    misplaced.write_bytes(b"wrong placement")
    monkeypatch.setattr(smoke, "run_smoke", lambda *_args: None)
    receipt = tmp_path / "smoke-receipt.json"

    result = smoke.main(["--bundle", str(bundle), "--receipt", str(receipt)])

    assert result == 1
    assert not receipt.exists()


def test_bundle_inventory_rejects_reparse_entries(tmp_path, monkeypatch):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    linked = bundle / "redirected-file.bin"
    linked.write_bytes(b"synthetic reparse target")
    real_lstat = Path.lstat

    def report_reparse(path):
        info = real_lstat(path)
        if path == linked:
            return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=0x400)
        return info

    monkeypatch.setattr(Path, "lstat", report_reparse)

    with pytest.raises(candidate.CandidateBuildError, match="linked file or directory"):
        smoke.bundle_inventory(bundle)


def test_freeze_command_clears_isolated_pyinstaller_cache(tmp_path):
    """A reused PyInstaller work path must not supply stale Python payloads."""
    command = candidate.freeze_command(tmp_path, clean=True)

    assert "--clean" in command
    with pytest.raises(candidate.CandidateBuildError, match="not isolated"):
        candidate._assert_isolated([["unrelated-builder", "--clean"]], tmp_path)


@pytest.mark.parametrize("produce_installer", [True, False])
def test_installer_rebuilds_and_smokes_before_compiling(packaged_world, tmp_path, monkeypatch, produce_installer):
    world, bundle = packaged_world
    root = world.root
    compiler = tmp_path / "fake-iscc.exe"
    compiler.write_bytes(b"mock compiler marker")
    (root / "pyproject.toml").write_text('[project]\nversion = "0.1.0"\n', encoding="utf-8")
    monkeypatch.setattr(installer, "ROOT", root)
    monkeypatch.setattr(installer, "clean_source_commit", lambda _root=root: COMMIT)
    real_verify_inputs = installer.verify_inputs
    monkeypatch.setattr(installer, "verify_inputs", lambda: real_verify_inputs(root))
    monkeypatch.setattr(sys, "argv", ["build_native_installer.py", "--compiler", str(compiler)])
    events = []
    previous = root / "build/native-candidate/installers" / f"MyCareerTraining-Windows-Test-{COMMIT[:12]}-Setup.exe"
    previous.parent.mkdir(parents=True, exist_ok=True)
    previous.write_bytes(b"old installer must not be receipted")

    def fresh_build(build_root, *, freeze, clean_freeze):
        assert build_root == root
        assert freeze is True
        assert clean_freeze is True
        events.append("build")
        (bundle / "MyCareerTraining.exe").write_bytes(b"fresh clean-source executable")

    def mocked_smoke(argv):
        events.append("smoke")
        assert (bundle / "MyCareerTraining.exe").read_bytes() == b"fresh clean-source executable"
        assert argv == ["--bundle", str(bundle)]
        receipt = root / "build" / "native-menu-candidate-smoke-receipt.json"
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt.write_text(json.dumps(smoke._evidence(bundle)), encoding="utf-8")
        return 0

    def mocked_compile(argv, *, cwd, check):
        events.append("compile")
        assert cwd == root and check is True
        assert (bundle / "MyCareerTraining.exe").read_bytes() == b"fresh clean-source executable"
        bundle_dir = Path(next(argument.split("=", 1)[1] for argument in argv if argument.startswith("/DBundleDir=")))
        assert bundle_dir.name == "bundle" and bundle_dir.parent.name.startswith("mct-")
        assert bundle_dir != bundle
        assert (bundle_dir / "MyCareerTraining.exe").read_bytes() == b"fresh clean-source executable"
        assert smoke.bundle_inventory(bundle_dir) == smoke.bundle_inventory(bundle)
        fresh_output = Path(next(argument[2:] for argument in argv if argument.startswith("/O")))
        assert fresh_output.name == "out" and fresh_output.parent == bundle_dir.parent
        assert fresh_output != previous.parent
        output = fresh_output / (
            f"MyCareerTraining-Windows-Test-{COMMIT[:12]}-Setup.exe"
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        if produce_installer:
            output.write_bytes(b"fake installer artifact")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(candidate, "build_candidate", fresh_build)
    monkeypatch.setattr(installer, "smoke_main", mocked_smoke)
    monkeypatch.setattr(installer.subprocess, "run", mocked_compile)

    if produce_installer:
        assert installer.main() == 0
        assert previous.read_bytes() == b"fake installer artifact"
        receipt = json.loads(previous.with_suffix(".json").read_text(encoding="utf-8"))
        assert receipt["sha256"] == hashlib.sha256(b"fake installer artifact").hexdigest()
        assert receipt["gameplay_verified"] is False
        assert receipt["production_ready"] is False
        assert receipt["installer_lifecycle_verified"] is False
    else:
        with pytest.raises(RuntimeError, match="did not produce a new"):
            installer.main()
        assert previous.read_bytes() == b"old installer must not be receipted"
        assert not previous.with_suffix(".json").exists()
    assert events == ["build", "smoke", "compile"]


def test_compiler_mutation_of_unlisted_bundle_file_is_rejected(packaged_world, tmp_path, monkeypatch):
    world, bundle = packaged_world
    root = world.root
    compiler = tmp_path / "fake-iscc.exe"
    compiler.write_bytes(b"mock compiler marker")
    (root / "pyproject.toml").write_text('[project]\nversion = "0.1.0"\n', encoding="utf-8")
    monkeypatch.setattr(installer, "ROOT", root)
    monkeypatch.setattr(installer, "clean_source_commit", lambda _root=root: COMMIT)
    real_verify_inputs = installer.verify_inputs
    monkeypatch.setattr(installer, "verify_inputs", lambda: real_verify_inputs(root))
    monkeypatch.setattr(sys, "argv", ["build_native_installer.py", "--compiler", str(compiler)])

    def fresh_build(_build_root, *, freeze, clean_freeze):
        assert freeze is True
        assert clean_freeze is True

    def mocked_smoke(_argv):
        receipt = root / "build" / "native-menu-candidate-smoke-receipt.json"
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt.write_text(json.dumps(smoke._evidence(bundle)), encoding="utf-8")
        return 0

    def mocked_compile(_argv, *, cwd, check):
        bundle_dir = Path(next(argument.split("=", 1)[1] for argument in _argv if argument.startswith("/DBundleDir=")))
        assert smoke.bundle_inventory(bundle_dir) == smoke.bundle_inventory(bundle)
        fresh_output = Path(next(argument[2:] for argument in _argv if argument.startswith("/O")))
        assert fresh_output.name == "out" and fresh_output.parent == bundle_dir.parent
        output = fresh_output / (
            f"MyCareerTraining-Windows-Test-{COMMIT[:12]}-Setup.exe"
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"fake installer artifact")
        (bundle / "compiler-added.dat").write_bytes(b"changed during compile")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(candidate, "build_candidate", fresh_build)
    monkeypatch.setattr(installer, "smoke_main", mocked_smoke)
    monkeypatch.setattr(installer.subprocess, "run", mocked_compile)

    with pytest.raises(RuntimeError, match="inventory changed"):
        installer.main()


def test_source_change_during_candidate_build_is_rejected(tmp_path, monkeypatch):
    root = tmp_path / "git-worktree"
    root.mkdir()
    tracked = root / "source.py"
    tracked.write_text("clean\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "tests@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "External regression test"], check=True)
    subprocess.run(["git", "-C", str(root), "add", "source.py"], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", "seed"], check=True)
    compiler = tmp_path / "fake-iscc.exe"
    compiler.write_bytes(b"mock compiler marker")
    monkeypatch.setattr(installer, "ROOT", root)
    monkeypatch.setattr(sys, "argv", ["build_native_installer.py", "--compiler", str(compiler)])
    real_clean_check = installer.clean_source_commit
    monkeypatch.setattr(installer, "clean_source_commit", lambda _root=root: real_clean_check(root))

    def source_changing_build(_build_root, *, freeze, clean_freeze):
        assert freeze is True
        assert clean_freeze is True
        tracked.write_text("changed while compiling\n", encoding="utf-8")

    monkeypatch.setattr(candidate, "build_candidate", source_changing_build)

    with pytest.raises(RuntimeError, match="Commit reviewed source changes"):
        installer.main()


DEEP_LICENSE = (
    "_internal/licenses/my-career-training/"
    "my_career_training-0.3.0.dist-info/licenses/LICENSE"
)


def _bind_mocked_installer(world, bundle, tmp_path, monkeypatch, compile_run):
    root = world.root
    compiler = tmp_path / "fake-iscc.exe"
    compiler.write_bytes(b"mock compiler marker")
    (root / "pyproject.toml").write_text('[project]\nversion = "0.1.0"\n', encoding="utf-8")
    monkeypatch.setattr(installer, "ROOT", root)
    monkeypatch.setattr(installer, "clean_source_commit", lambda _root=root: COMMIT)
    real_verify_inputs = installer.verify_inputs
    monkeypatch.setattr(installer, "verify_inputs", lambda: real_verify_inputs(root))
    monkeypatch.setattr(sys, "argv", ["build_native_installer.py", "--compiler", str(compiler)])

    def fresh_build(_build_root, *, freeze, clean_freeze):
        assert freeze is True and clean_freeze is True

    def mocked_smoke(_argv):
        receipt = root / "build" / "native-menu-candidate-smoke-receipt.json"
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt.write_text(json.dumps(smoke._evidence(bundle)), encoding="utf-8")
        return 0

    monkeypatch.setattr(candidate, "build_candidate", fresh_build)
    monkeypatch.setattr(installer, "smoke_main", mocked_smoke)
    monkeypatch.setattr(installer.subprocess, "run", compile_run)
    return root


def test_installer_script_requires_short_bundle_directory():
    script = (REPO / "packaging" / "native-candidate.iss").read_text(encoding="utf-8")
    assert "#ifndef BundleDir" in script
    assert 'Source: "{#BundleDir}\\*"' in script
    assert "MyCareerTrainingNativeCandidate\\*" not in script
    assert "LicenseFile=..\\LICENSE" in script


def test_short_copy_tamper_is_refused_before_compiler(packaged_world, tmp_path, monkeypatch):
    world, bundle = packaged_world
    before = smoke.bundle_inventory(bundle)
    real_copy = shutil.copytree

    def tamper(src, dst, *args, **kwargs):
        real_copy(src, dst, *args, **kwargs)
        (Path(dst) / "MyCareerTraining.exe").write_bytes(b"tampered copy")

    monkeypatch.setattr(installer.shutil, "copytree", tamper)

    def fail_compile(*_args, **_kwargs):
        raise AssertionError("compiler started")

    _bind_mocked_installer(world, bundle, tmp_path, monkeypatch, fail_compile)
    with pytest.raises(RuntimeError, match="does not match the smoke-verified bundle"):
        installer.main()
    assert smoke.bundle_inventory(bundle) == before


def test_compiler_tamper_of_short_copy_is_not_promoted(packaged_world, tmp_path, monkeypatch):
    world, bundle = packaged_world
    filename = f"MyCareerTraining-Windows-Test-{COMMIT[:12]}-Setup.exe"
    final = world.root / "build" / "native-candidate" / "installers" / filename
    final.parent.mkdir(parents=True, exist_ok=True)
    final.write_bytes(b"stale installer")

    def mocked_compile(argv, *, cwd, check):
        assert cwd == world.root and check is True
        bundle_dir = Path(next(argument.split("=", 1)[1] for argument in argv if argument.startswith("/DBundleDir=")))
        (bundle_dir / "compiler-added.dat").write_bytes(b"tampered input")
        output = Path(next(argument[2:] for argument in argv if argument.startswith("/O"))) / filename
        output.write_bytes(b"must not be promoted")
        return SimpleNamespace(returncode=0)

    _bind_mocked_installer(world, bundle, tmp_path, monkeypatch, mocked_compile)
    with pytest.raises(RuntimeError, match="Compiler input copy changed"):
        installer.main()
    assert final.read_bytes() == b"stale installer"
    assert not final.with_suffix(".json").exists()


def test_overlong_short_stage_refuses_before_compiler(packaged_world, tmp_path, monkeypatch):
    world, bundle = packaged_world
    deep = bundle.joinpath(*Path(DEEP_LICENSE).parts)
    deep.parent.mkdir(parents=True)
    deep.write_bytes(b"required license")
    monkeypatch.setattr(installer, "COMPILER_PATH_LIMIT", 32)

    def fail_compile(*_args, **_kwargs):
        raise AssertionError("compiler started")

    _bind_mocked_installer(world, bundle, tmp_path, monkeypatch, fail_compile)
    with pytest.raises(RuntimeError, match="temporary directory is still too long") as refused:
        installer.main()
    assert "Refusing to start the installer compiler" in str(refused.value)
    assert deep.read_bytes() == b"required license"


def test_unverified_compiler_is_refused_before_build(tmp_path, monkeypatch):
    compiler = tmp_path / "unverified-iscc.exe"
    compiler.write_bytes(b"unexpected compiler bytes")
    monkeypatch.setattr(sys, "argv", ["build_native_installer.py", "--compiler", str(compiler)])
    monkeypatch.setattr(candidate, "build_candidate", lambda *_args, **_kwargs: pytest.fail("build started"))
    with pytest.raises(RuntimeError, match="verified Inno Setup"):
        installer.main()


@pytest.mark.parametrize("scenario", ["shared_views", "different_target", "absent"])
def test_lifecycle_accepts_only_owned_registry_entries(tmp_path, monkeypatch, scenario):
    spec = importlib.util.spec_from_file_location("_ci_installer", REPO / "scripts/test_native_installer.py")
    lifecycle = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lifecycle)
    target = tmp_path / "owned install"
    owned = (target.resolve(), (target / "unins000.exe").resolve())
    records = {"shared_views": [owned, owned], "different_target": [owned, (tmp_path, tmp_path / "other.exe")],
               "absent": []}[scenario]
    monkeypatch.setattr(lifecycle, "registrations", lambda: records)
    if scenario == "shared_views":
        lifecycle.require_owned_registration(target)
    else:
        with pytest.raises(RuntimeError, match="exclusively belong"):
            lifecycle.require_owned_registration(target)
