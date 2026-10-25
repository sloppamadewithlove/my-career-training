"""Synthetic checks for the opt-in native candidate. No compiler or freeze is run."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "src"))

import build_native_candidate as candidate  # noqa: E402
import smoke_native_candidate as smoke  # noqa: E402
from my_career_training import native_launch, native_menu_assets as menu_assets  # noqa: E402

COMMIT = "a" * 40
NOTICE = b"Microsoft Research Detours project notice\n"
CORE = b"MZ synthetic pinned RLBot core fixture"


def test_plan_commands_stay_on_the_candidate_cmake_cache(tmp_path):
    root = tmp_path / "repo"
    commands = candidate.plan_commands(root, freeze=False)
    plugin = commands[0]
    launcher = commands[3]
    assert plugin[plugin.index("-B") + 1] == str(candidate.plugin_build_dir(root))
    assert launcher[launcher.index("-B") + 1] == str(candidate.launcher_build_dir(root))
    assert "-DMCT_ENABLE_NATIVE_MOVIE_TRIAL=ON" in plugin
    assert "-DMCT_BUILD_HOST_PROBE=OFF" in plugin
    assert not any("MCT_" in part for command in commands[1:] for part in command)
    joined = " ".join(" ".join(command) for command in commands)
    assert "--launch-offline" not in joined
    assert "MCT_BUILD_HOST_PROBE=ON" not in joined
    assert "MCT_ENABLE_NATIVE_MOVIE_TRIAL=OFF" not in joined
    assert "installer.iss" not in joined
    assert str(root / "build" / "plugin") not in joined
    assert str(root / "runtime" / "plugins") not in joined
    frozen = candidate.plan_commands(root, freeze=True)
    assert frozen[:-1] == commands
    assert frozen[-1] == candidate.freeze_command(root)
    assert "--clean" not in frozen[-1]
    assert str(root / "packaging" / "my-career-training.spec") not in frozen[-1]
    assert str(root / "packaging" / "my-career-training-native.spec") in frozen[-1]


def test_missing_native_menu_runtime_writes_no_candidate_tree(tmp_path):
    root = _seed(tmp_path, menu=False)
    with pytest.raises(candidate.CandidateBuildError, match="native-menu runtime is missing"):
        candidate.build_candidate(root, runner=_runner(root), source_commit=COMMIT)
    assert not candidate.staged_runtime(root).exists()
    assert not (candidate.candidate_dir(root) / candidate.MANIFEST_NAME).exists()
    assert (root / "runtime" / "plugins" / "SENTINEL.txt").read_text(encoding="utf-8") == "keep"


@pytest.mark.parametrize("problem", ["flag", "hash"])
def test_menu_receipt_flag_and_hash_are_refused(tmp_path, problem):
    root = _seed(tmp_path)
    menu = root / "runtime" / "native-menu"
    if problem == "flag":
        receipt = json.loads((menu / "receipt.json").read_text(encoding="utf-8"))
        receipt["runtime_verified"] = True
        (menu / "receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
        match = "runtime_verified"
    else:
        abc = menu / "MctRootMenu.abc"
        abc.write_bytes(abc.read_bytes() + b"!")
        match = "hash"
    with pytest.raises(candidate.CandidateBuildError, match=match):
        candidate.build_candidate(root, runner=_runner(root), source_commit=COMMIT)
    assert not candidate.staged_runtime(root).exists()


@pytest.mark.parametrize("name", [
    "GFX_MainMenu_SF.upk", "MainMenu.gfx", "menu.swf", "lib.swc",
    "MCTNativeHostProbe.dll", "pluginsdk.lib",
])
def test_menu_forbidden_payload_is_left_in_the_source_tree(tmp_path, name):
    root = _seed(tmp_path)
    extra = root / "runtime" / "native-menu" / name
    extra.write_bytes(b"proprietary")
    with pytest.raises(candidate.CandidateBuildError, match="unexpected entry|forbidden payload"):
        candidate.build_candidate(root, runner=_runner(root), source_commit=COMMIT)
    assert extra.read_bytes() == b"proprietary"
    assert not candidate.staged_runtime(root).exists()


def test_plugin_source_proprietary_payload_is_refused(tmp_path):
    root = _seed(tmp_path)
    (root / "plugin" / "stolen.swf").write_bytes(b"FWS")
    with pytest.raises(candidate.CandidateBuildError, match="forbidden payload"):
        candidate.build_candidate(root, runner=_runner(root), source_commit=COMMIT)
    assert not candidate.staged_runtime(root).exists()
    assert (root / "plugin" / "stolen.swf").is_file()


def test_ambiguous_native_directory_is_left_in_place(tmp_path):
    root = _seed(tmp_path)
    native = candidate.staged_runtime(root) / "native"
    native.mkdir(parents=True)
    extra = native / "extra.upk"
    extra.write_bytes(b"leave-me")
    with pytest.raises(candidate.CandidateBuildError, match="left in place"):
        candidate.build_candidate(root, runner=_runner(root), source_commit=COMMIT)
    assert extra.read_bytes() == b"leave-me"
    assert not (candidate.staged_runtime(root) / "plugins").exists()
    assert not (native / "MctNativeLauncher.exe").exists()
    assert not (candidate.candidate_dir(root) / candidate.MANIFEST_NAME).exists()


def test_host_probe_output_is_refused(tmp_path):
    root = _seed(tmp_path)
    probe = candidate.plugin_build_dir(root) / "Release" / "MCTNativeHostProbe.dll"
    probe.parent.mkdir(parents=True, exist_ok=True)
    probe.write_bytes(b"MZ probe")
    with pytest.raises(candidate.CandidateBuildError, match="host probe"):
        candidate.build_candidate(root, runner=_runner(root), source_commit=COMMIT)
    assert probe.is_file()
    assert not candidate.staged_runtime(root).exists()


def test_native_runtime_validation_error_publishes_nothing(tmp_path, monkeypatch):
    root = _seed(tmp_path)
    seen = []

    def refuse(directory=None):
        seen.append(Path(directory))
        raise native_launch.NativeLaunchError("hash", code="runtime_hash")

    monkeypatch.setattr(native_launch, "validate_native_runtime", refuse)
    with pytest.raises(candidate.CandidateBuildError, match="native runtime validation failed"):
        candidate.build_candidate(root, runner=_runner(root), source_commit=COMMIT)
    assert seen
    assert "native-candidate" in str(seen[0])
    assert seen[0] != root / "runtime" / "native"
    assert not (candidate.staged_runtime(root) / "native").exists()
    assert not (candidate.staged_runtime(root) / "plugins").exists()
    assert not (candidate.candidate_dir(root) / candidate.MANIFEST_NAME).exists()


def test_candidate_build_stages_isolated_runtime_and_exact_notice(tmp_path, monkeypatch):
    world = _build(tmp_path, monkeypatch)
    root = world.root
    runtime = candidate.staged_runtime(root)
    native = runtime / "native"
    assert world.commands == candidate.plan_commands(root, freeze=False)
    assert sorted(path.name for path in native.iterdir()) == sorted(native_launch.RUNTIME_FILENAMES)
    assert (native / "DETOURS-MIT-LICENSE.txt").read_bytes() == native_launch.DETOURS_NOTICE_BYTES
    assert not (native / "NOTICE").exists()
    assert (candidate.launcher_build_dir(root) / "bin" / "NOTICE").read_bytes() == NOTICE
    notice = world.manifest["notice"]
    assert notice["staged_sha256"] == native_launch.DETOURS_NOTICE_SHA256
    assert notice["launcher_output_sha256"] == hashlib.sha256(NOTICE).hexdigest()
    assert notice["launcher_output_sha256"] != notice["staged_sha256"]
    assert world.manifest["flags"] == candidate.FALSE_FLAGS
    assert all(value is False for value in world.manifest["flags"].values())
    assert world.manifest["build"]["native_movie_trial"] is True
    assert world.manifest["build"]["native_host_probe"] is False
    assert world.manifest["distribution"] == "developer_candidate"
    receipt = json.loads((runtime / "plugins" / "plugin-build-receipt.json").read_text(encoding="utf-8"))
    assert receipt["native_movie_trial"] is True
    assert receipt["native_host_probe"] is False
    assert receipt["gameplay_verified"] is False
    assert receipt["source_commit"] == COMMIT
    assert receipt["native"]["machine"] == "AMD64"
    assert "plugin/src/MyCareerTraining.cpp" in receipt["source_files"]
    names = [path.name for path in runtime.rglob("*") if path.is_file()]
    assert "MctRootMenu.abc" in names
    for forbidden in ("dropped.swf", "pluginsdk.lib", "MCTNativeHostProbe.dll",
                      "mct_native_launcher_tests.exe", "extra.upk", "NOTICE"):
        assert forbidden not in names
    entries = candidate.bundle_entries(root)
    packaged = [Path(source).name for source, _dest in entries]
    assert "MctRootMenu.abc" in packaged
    assert candidate.MANIFEST_NAME in packaged
    assert not any(name.lower().endswith((".upk", ".gfx", ".swf", ".swc")) for name in packaged)
    assert (root / "runtime" / "plugins" / "SENTINEL.txt").read_text(encoding="utf-8") == "keep"
    assert (root / "dist" / "MyCareerTraining" / "keep.txt").read_text(encoding="utf-8") == "release"
    assert world.validated
    assert all("native-candidate" in str(path) for path in world.validated)
    assert root / "runtime" / "native" not in world.validated


def test_wrong_plugin_flag_and_hash_fail_verification(tmp_path, monkeypatch):
    world = _build(tmp_path, monkeypatch)
    receipt_path = candidate.staged_runtime(world.root) / "plugins" / "plugin-build-receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["gameplay_verified"] = True
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(candidate.CandidateBuildError, match="gameplay|flags"):
        candidate.verify_candidate(world.root)
    receipt["gameplay_verified"] = False
    receipt["sha256"] = "0" * 64
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(candidate.CandidateBuildError, match="hash"):
        candidate.verify_candidate(world.root)


def test_freeze_is_explicit_and_does_not_launch_or_clean(tmp_path, monkeypatch):
    world = _build(tmp_path, monkeypatch)
    commands = []
    candidate.build_candidate(world.root, freeze=True, runner=_runner(world.root, commands), source_commit=COMMIT)
    assert commands[-1] == candidate.freeze_command(world.root)
    blob = " ".join(" ".join(command) for command in commands)
    assert "--clean" not in blob
    assert "--launch-offline" not in blob
    assert "RocketLeague.exe" not in blob
    assert str(world.root / "packaging" / "my-career-training.spec") not in blob
    assert not (world.root / "dist" / candidate.BUNDLE_NAME).exists()


def test_smoke_rejects_missing_runtime_wrong_flag_hash_and_proprietary_file(tmp_path, monkeypatch):
    monkeypatch.setattr(candidate, "RLBOT_SHA256", hashlib.sha256(CORE).hexdigest())
    world = _build(tmp_path, monkeypatch)
    bundle = tmp_path / "bundle"
    _as_bundle(world, bundle)

    def boom(*_args, **_kwargs):
        raise AssertionError("smoke validation must not start a process")

    monkeypatch.setattr(subprocess, "run", boom)
    monkeypatch.setattr(subprocess, "Popen", boom)
    assert smoke.validate_bundle(bundle)["manifest"]["distribution"] == "developer_candidate"

    missing = tmp_path / "missing-bundle"
    missing.mkdir()
    with pytest.raises(candidate.CandidateBuildError, match="missing"):
        smoke.validate_bundle(missing)

    flagged = tmp_path / "flagged"
    _as_bundle(world, flagged)
    receipt_path = flagged / "_internal" / "my_career_training" / "runtime" / "plugins" / "plugin-build-receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["native_movie_trial"] = False
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(candidate.CandidateBuildError, match="native_movie_trial"):
        smoke.validate_bundle(flagged)

    hashed = tmp_path / "hashed"
    _as_bundle(world, hashed)
    receipt_path = hashed / "_internal" / "my_career_training" / "runtime" / "plugins" / "plugin-build-receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["sha256"] = "0" * 64
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(candidate.CandidateBuildError, match="hash"):
        smoke.validate_bundle(hashed)

    owned = tmp_path / "owned"
    _as_bundle(world, owned)
    extra = owned / "_internal" / "my_career_training" / "runtime" / "native-menu" / "GFX_MainMenu_SF.upk"
    extra.write_bytes(b"game")
    with pytest.raises(candidate.CandidateBuildError, match="unexpected entry"):
        smoke.validate_bundle(owned)
    assert extra.read_bytes() == b"game"

    wrong_core = tmp_path / "wrong-core"
    _as_bundle(world, wrong_core)
    core = wrong_core / "_internal/my_career_training/runtime/RLBotServer.exe"
    core.write_bytes(b"MZ changed core")
    with pytest.raises(candidate.CandidateBuildError, match="RLBot core checksum"):
        smoke.validate_bundle(wrong_core)
    core.unlink()
    with pytest.raises(candidate.CandidateBuildError, match="missing"):
        smoke.validate_bundle(wrong_core)
    # The compile/stage tree remains narrower than the finished player bundle.
    core.write_bytes(CORE)
    with pytest.raises(candidate.CandidateBuildError, match="unexpected entry"):
        candidate.check_runtime_tree(core.parent)


@pytest.mark.parametrize("filename", ["package-smoke-receipt.json", "PACKAGE-SMOKE-RECEIPT.JSON"])
def test_candidate_cannot_overwrite_release_receipt(tmp_path, filename):
    receipt = tmp_path / filename
    receipt.write_text("release sentinel", encoding="utf-8")
    assert smoke.main(["--receipt", str(receipt)]) == 1
    assert receipt.read_text(encoding="utf-8") == "release sentinel"


def test_smoke_main_does_not_run_the_helper_or_the_release_receipt(tmp_path, monkeypatch):
    bundle = tmp_path / "MyCareerTrainingNativeCandidate"
    for relative in smoke.ARTIFACTS:
        path = bundle.joinpath(*Path(relative).parts)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"artifact-" + relative.encode("utf-8"))
    calls = []
    monkeypatch.setattr(smoke, "validate_bundle", lambda _bundle: {"ok": True})
    monkeypatch.setattr(smoke, "run_smoke", lambda packaged, data: calls.append((packaged, data)))

    def boom(*args, **_kwargs):
        raise AssertionError(args)

    monkeypatch.setattr(subprocess, "run", boom)
    monkeypatch.setattr(subprocess, "Popen", boom)
    receipt = tmp_path / "native-menu-candidate-smoke-receipt.json"
    assert smoke.main(["--bundle", str(bundle), "--receipt", str(receipt)]) == 0
    assert calls and "é" in calls[0][0].name and "球" in str(calls[0][0])
    assert "Player data" in calls[0][1].name
    body = json.loads(receipt.read_text(encoding="utf-8"))
    assert body["passed"] is True
    assert body["helper_executed"] is False
    assert body["gameplay_verified"] is False
    assert body["live_rocket_league"] is False
    assert body["native_movie_trial"] is True
    assert smoke.DEFAULT_RECEIPT.name == "native-menu-candidate-smoke-receipt.json"
    assert smoke.DEFAULT_RECEIPT.name != "package-smoke-receipt.json"
    missing = tmp_path / "absent"
    absent_receipt = tmp_path / "absent-receipt.json"
    assert smoke.main(["--bundle", str(missing), "--receipt", str(absent_receipt)]) == 1
    assert not absent_receipt.exists()
    text = (REPO / "scripts" / "smoke_native_candidate.py").read_text(encoding="utf-8")
    assert "--launch-offline" not in text
    assert "RocketLeague.exe" not in text
    assert "installer.iss" not in text


def test_spec_keeps_a_distinct_output():
    text = (REPO / "packaging" / "my-career-training-native.spec").read_text(encoding="utf-8")
    normal = (REPO / "packaging" / "my-career-training.spec").read_text(encoding="utf-8")
    assert candidate.BUNDLE_NAME == "MyCareerTrainingNativeCandidate"
    assert "name=candidate.BUNDLE_NAME" in text
    assert '"native-candidate"' in text
    assert "bundle_entries" in text
    assert 'root / "runtime" / "plugins"' not in text
    assert "installer.iss" not in text
    assert "--launch-offline" not in text
    assert "my-career-training.spec" not in text
    assert 'runtime" / "plugins" / "MyCareerTraining.dll"' in normal
    assert 'runtime" / "plugins" / "MyCareerTraining.dll"' not in text


def test_candidate_double_click_selects_native_but_smoke_and_worker_never_do():
    import runpy
    entry = runpy.run_path(str(REPO / "packaging" / "native_gui_entry.py"))
    arguments = entry["native_arguments"]
    assert arguments([]) == ["--native-menu-trial"]
    assert arguments(["--native-menu-trial"]) == ["--native-menu-trial"]
    for mode in ("--worker", "--manage", "--self-test", "--smoke-test", "--help", "-h"):
        original = [mode]
        assert arguments(original) == original
        assert original == [mode]


def _build(tmp_path: Path, monkeypatch) -> SimpleNamespace:
    root = _seed(tmp_path)
    commands = []
    seen = []
    original = native_launch.validate_native_runtime

    def spy(directory=None):
        seen.append(Path(directory))
        return original(directory)

    monkeypatch.setattr(native_launch, "validate_native_runtime", spy)
    manifest = candidate.build_candidate(root, runner=_runner(root, commands), source_commit=COMMIT)
    return SimpleNamespace(root=root, commands=commands, manifest=manifest, validated=seen)


def _runner(root: Path, commands: list | None = None):
    recorded = commands if commands is not None else []

    def runner(argv, check):
        assert check is True
        recorded.append(list(argv))
        _materialize(root, argv)
        return None

    return runner


def _materialize(root: Path, argv: list[str]) -> None:
    if argv[:2] == ["cmake", "--build"] and argv[2] == str(candidate.plugin_build_dir(root)):
        dest = candidate.plugin_build_dir(root) / "Release"
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "MyCareerTraining.dll").write_bytes(_plugin_pe())
        (dest / "mct_native_layout_tests.exe").write_bytes(b"test")
    if argv[:2] == ["cmake", "--build"] and argv[2] == str(candidate.launcher_build_dir(root)):
        dest = candidate.launcher_build_dir(root) / "bin"
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "MctNativeLauncher.exe").write_bytes(_tiny_pe("exe"))
        (dest / "MctNativeFileView64.dll").write_bytes(_tiny_pe("dll"))
        (dest / "NOTICE").write_bytes((root / "native_launcher" / "NOTICE").read_bytes())
        (dest / "mct_native_launcher_tests.exe").write_bytes(b"test")
        (dest / "MctNativeFileFixture.exe").write_bytes(b"fixture")
        (dest / "dropped.swf").write_bytes(b"FWS")


def _seed(tmp_path: Path, *, menu: bool = True) -> Path:
    root = tmp_path / "repo"
    (root / "plugin" / "src").mkdir(parents=True)
    (root / "plugin" / "src" / "MyCareerTraining.cpp").write_text("int plugin;\n", encoding="utf-8")
    (root / "plugin" / "DEPENDENCIES.json").write_text(
        json.dumps({"json": {"version": "3.12.0"}}) + "\n", encoding="utf-8")
    (root / "native_launcher").mkdir(parents=True)
    (root / "native_launcher" / "NOTICE").write_bytes(NOTICE)
    imgui = candidate.plugin_build_dir(root) / "sdk-imgui" / "imgui"
    imgui.mkdir(parents=True)
    (imgui / "imgui.h").write_text("/* imgui */\n", encoding="utf-8")
    json_dir = candidate.plugin_build_dir(root) / "_deps" / "mct_json-src" / "include" / "nlohmann"
    json_dir.mkdir(parents=True)
    (json_dir / "json.hpp").write_text("// json\n", encoding="utf-8")
    sdk = candidate.plugin_build_dir(root) / "_deps" / "mct_sdk-src"
    sdk.mkdir(parents=True)
    (sdk / "pluginsdk.lib").write_bytes(b"sdk")
    (root / "runtime" / "plugins").mkdir(parents=True)
    (root / "runtime" / "plugins" / "SENTINEL.txt").write_text("keep", encoding="utf-8")
    (root / "dist" / "MyCareerTraining").mkdir(parents=True)
    (root / "dist" / "MyCareerTraining" / "keep.txt").write_text("release", encoding="utf-8")
    if menu:
        _write_menu(root / "runtime" / "native-menu")
    return root


def _write_menu(directory: Path) -> None:
    license_blob = (REPO / "packaging" / "licenses" / "native-menu" / "UEViewer-LICENSE.txt").read_bytes()
    license_blob = license_blob.replace(b"\r\n", b"\n")
    abc = b"original-authored-abc"
    key = bytes([0x5A]) * 32
    source_sha = hashlib.sha256(b"menu-source").hexdigest()
    screen_sha = hashlib.sha256(b"screen-source").hexdigest()
    manifest = {
        "abc_bytes": len(abc),
        "abc_sha256": hashlib.sha256(abc).hexdigest(),
        "authored_classes": list(menu_assets.AUTHORED_CLASSES),
        "classes": list(menu_assets.COMPILED_CLASSES),
        "game_classes_linked": False,
        "library_classes": list(menu_assets.LIBRARY_CLASSES),
        "library_commit": menu_assets.LIBRARY_COMMIT,
        "library_files": dict(menu_assets.LIBRARY_FILES),
        "production_ready": False,
        "runtime_verified": False,
        "screen_source_sha256": screen_sha,
        "source_sha256": source_sha,
    }
    files = {
        "MctRootMenu.abc": abc,
        "UEViewer-LICENSE.txt": license_blob,
        "decoder_config.bin": key,
        "manifest.json": (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        "native_movie_compose.py": b"def compose_movie():\n    raise RuntimeError('not used')\n",
        "native_package_reader.py": b"def read_movie_bytes():\n    raise RuntimeError('not used')\n",
        "native_package_rewrite.py": b"def replace_final_movie():\n    raise RuntimeError('not used')\n",
    }
    match_manifest = json.loads((REPO / "native_ui" / "compiled" / "match-manifest.json").read_text(encoding="utf-8"))
    for scene in match_manifest["scenes"].values():
        payload = ("synthetic authored " + scene["surface"]).encode("ascii")
        files[scene["abc_file"]] = payload
        scene["abc_bytes"] = len(payload)
        scene["abc_sha256"] = hashlib.sha256(payload).hexdigest()
    files["match-manifest.json"] = json.dumps(match_manifest).encode("utf-8")
    listed = {name: {"bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest()} for name, blob in files.items()}
    receipt = {
        "files": listed,
        "installs_package": False,
        "kind": "native_menu_runtime",
        "launches_game": False,
        "loads_runtime": False,
        "network_at_runtime": False,
        "pins": {
            "abc_bytes": len(abc),
            "abc_sha256": hashlib.sha256(abc).hexdigest(),
            "bakkesmod_core": menu_assets.BAKKESMOD_CORE,
            "classes": list(menu_assets.AUTHORED_CLASSES),
            "executable_relative": menu_assets.EXECUTABLE_RELATIVE,
            "executable_sha256": menu_assets.EXECUTABLE_SHA256,
            "export_name": menu_assets.EXPORT_NAME,
            "movie_sha256": menu_assets.MOVIE_SHA256,
            "package_relative": menu_assets.PACKAGE_RELATIVE,
            "package_sha256": menu_assets.PACKAGE_SHA256,
            "runtime_build": menu_assets.RUNTIME_BUILD,
            "screen_source_sha256": screen_sha,
            "source_sha256": source_sha,
        },
        "production_ready": False,
        "provenance": {
            "copyright": "Copyright 2022, Konstantin Nosov",
            "license_bytes": menu_assets.LICENSE_BYTES,
            "license_name": "MIT",
            "license_sha256": menu_assets.LICENSE_SHA256,
            "license_url": menu_assets.LICENSE_URL,
            "source_bytes": menu_assets.SOURCE_BYTES,
            "source_sha256": menu_assets.SOURCE_SHA256,
            "source_url": menu_assets.SOURCE_URL,
            "ueviewer_commit": menu_assets.UEVIEWER_COMMIT,
        },
        "runtime_verified": False,
        "schema": 1,
    }
    encoded = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8")
    if key.hex().encode("ascii") in encoded.lower():
        raise AssertionError("fixture included decoder key material")
    directory.mkdir(parents=True)
    for name, blob in files.items():
        (directory / name).write_bytes(blob)
    (directory / "receipt.json").write_bytes(encoded)


def _as_bundle(world: SimpleNamespace, bundle: Path) -> None:
    runtime = candidate.staged_runtime(world.root)
    destination = bundle / "_internal" / "my_career_training" / "runtime"
    for component in ("plugins", "native", "native-menu"):
        target = destination / component
        target.mkdir(parents=True)
        for path in (runtime / component).iterdir():
            (target / path.name).write_bytes(path.read_bytes())
    manifest = candidate.candidate_dir(world.root) / candidate.MANIFEST_NAME
    (destination / "RLBotServer.exe").write_bytes(CORE)
    (bundle / "_internal" / candidate.MANIFEST_NAME).write_bytes(manifest.read_bytes())


def _plugin_pe() -> bytes:
    exports = ("getPlugin", "deleteMe", "exports", "mct_protocol_version")
    image = bytearray(0xA00)
    image[:2] = b"MZ"
    struct.pack_into("<I", image, 0x3C, 0x80)
    image[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<HHIIIHH", image, 0x84, 0x8664, 1, 0, 0, 0, 240, 0x2002)
    struct.pack_into("<H", image, 0x98, 0x20B)
    struct.pack_into("<II", image, 0x98 + 112, 0x1000, 0x100)
    struct.pack_into("<II", image, 0x98 + 120, 0x1180, 40)
    struct.pack_into("<8sIIII", image, 0x188, b".rdata\0\0", 0x800, 0x1000, 0x800, 0x200)
    struct.pack_into("<I", image, 0x200 + 24, len(exports))
    struct.pack_into("<I", image, 0x200 + 32, 0x1040)
    cursor = 0x280
    for index, name in enumerate(exports):
        struct.pack_into("<I", image, 0x240 + index * 4, cursor + 0xE00)
        encoded = name.encode("ascii") + b"\0"
        image[cursor:cursor + len(encoded)] = encoded
        cursor += len(encoded)
    struct.pack_into("<IIIII", image, 0x380, 0x1200, 0, 0, 0x11C0, 0x1200)
    image[0x3C0:0x3CD] = b"bakkesmod.dll"
    return bytes(image)


def _tiny_pe(kind: str) -> bytes:
    image = bytearray(256)
    image[:2] = b"MZ"
    struct.pack_into("<I", image, 0x3C, 0x80)
    image[0x80:0x84] = b"PE\0\0"
    flags = 0x0002 | (0x2000 if kind == "dll" else 0)
    struct.pack_into("<HHIIIHH", image, 0x84, 0x8664, 0, 0, 0, 0, 0, flags)
    struct.pack_into("<H", image, 0x98, 0x20B)
    return bytes(image)
