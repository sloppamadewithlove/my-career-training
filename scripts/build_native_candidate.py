"""Stage an opt-in developer native-menu candidate without touching the release.

Outputs stay under ``build/native-candidate``. The normal plugin cache,
``runtime/plugins``, ``runtime/native``, installer, and release spec are not
inputs or outputs. This script does not launch Rocket League, BakkesMod,
Steam, the installer, or ``MctNativeLauncher.exe --launch-offline``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import uuid

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import plugin_artifact  # noqa: E402
import stage_native_runtime as stage_menu  # noqa: E402
from fetch_runtime import SHA256 as RLBOT_SHA256  # noqa: E402
from my_career_training import native_launch, native_menu_assets as menu_assets  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BUNDLE_NAME = "MyCareerTrainingNativeCandidate"
MANIFEST_NAME = "candidate-manifest.json"
PLUGIN_DLL = "MyCareerTraining.dll"
PLUGIN_RECEIPT = "plugin-build-receipt.json"
SOURCE_NOTICE = "NOTICE"
PROPRIETARY_SUFFIXES = (".upk", ".gfx", ".swf", ".swc")
FORBIDDEN_BASENAMES = frozenset({
    "MCTNativeHostProbe.dll",
    "MctNativeFileFixture.exe",
    "RocketLeague.exe",
    "BakkesMod.exe",
    "ffdec.jar",
    "java.exe",
    "javaw.exe",
    "mct_native_file_view_tests.exe",
    "mct_native_launcher_tests.exe",
    "pluginsdk.lib",
    "steam.exe",
})
ARCHIVE_COMPONENTS = (
    ("imgui-bakkesmod", ("sdk-imgui", "imgui")),
    ("nlohmann-json", ("_deps", "mct_json-src")),
    ("my-career-training-plugin", None),
)
FALSE_FLAGS = {
    "file_view_observed": False,
    "game_verified": False,
    "gameplay_verified": False,
    "helper_executed": False,
    "installer_included": False,
    "installs_package": False,
    "launches_game": False,
    "live_rocket_league": False,
    "native_host_probe": False,
    "production_ready": False,
    "published_release": False,
    "runtime_verified": False,
}
BUILD_SWITCHES = {
    "architecture": "x64",
    "configuration": "Release",
    "native_host_probe": False,
    "native_movie_trial": True,
}
MENU_FALSE_FLAGS = (
    "installs_package", "launches_game", "loads_runtime", "network_at_runtime",
    "production_ready", "runtime_verified",
)
MENU_RECEIPT_KEYS = frozenset({
    "files", "installs_package", "kind", "launches_game", "loads_runtime",
    "network_at_runtime", "pins", "production_ready", "provenance",
    "runtime_verified", "schema",
})
MENU_PIN_KEYS = frozenset({
    "abc_bytes", "abc_sha256", "bakkesmod_core", "classes", "executable_relative",
    "executable_sha256", "export_name", "movie_sha256", "package_relative",
    "package_sha256", "runtime_build", "screen_source_sha256", "source_sha256",
})
MENU_PROVENANCE_KEYS = frozenset({
    "copyright", "license_bytes", "license_name", "license_sha256", "license_url",
    "source_bytes", "source_sha256", "source_url", "ueviewer_commit",
})
MENU_FILE_CAPS = {
    "native_package_reader.py": 1024 * 1024,
    "native_package_rewrite.py": 1024 * 1024,
    "native_movie_compose.py": 1024 * 1024,
    "MctRootMenu.abc": 64 * 1024,
    "manifest.json": 64 * 1024,
    "decoder_config.bin": 32,
    "UEViewer-LICENSE.txt": 8192,
}
MAX_SOURCE_FILE = 2 * 1024 * 1024
MAX_PLUGIN_DLL = 32 * 1024 * 1024
MAX_PLUGIN_RECEIPT = 1024 * 1024
MAX_MENU_RECEIPT = 64 * 1024
_REPARSE = 0x400
_FORBIDDEN_ARGUMENTS = (
    "--launch-offline",
    "--clean",
    "installer.iss",
    "RocketLeague.exe",
    "BakkesMod.exe",
    "steam.exe",
)


class CandidateBuildError(RuntimeError):
    """The candidate was refused. Ambiguous staged directories were left in place."""


def candidate_dir(root: Path | None = None) -> Path:
    return _root(root) / "build" / "native-candidate"


def plugin_build_dir(root: Path | None = None) -> Path:
    return candidate_dir(root) / "plugin"


def launcher_build_dir(root: Path | None = None) -> Path:
    return candidate_dir(root) / "native-launcher"


def staged_runtime(root: Path | None = None) -> Path:
    return candidate_dir(root) / "runtime"


def menu_source_dir(root: Path | None = None) -> Path:
    return _root(root) / "runtime" / "native-menu"


def default_bundle(root: Path | None = None) -> Path:
    return candidate_dir(root) / "dist" / BUNDLE_NAME


def freeze_command(root: Path | None = None) -> list[str]:
    root = _root(root)
    command = [
        sys.executable, "-m", "PyInstaller", "--noconfirm",
        "--distpath", str(candidate_dir(root) / "dist"),
        "--workpath", str(candidate_dir(root) / "pyinstaller"),
        str(root / "packaging" / "my-career-training-native.spec"),
    ]
    _assert_isolated([command], root)
    return command


def plan_commands(root: Path | None = None, *, freeze: bool = False) -> list[list[str]]:
    """Exact compiler commands. The candidate CMake cache is not ``build/plugin``."""
    root = _root(root)
    plugin_build = plugin_build_dir(root)
    launcher_build = launcher_build_dir(root)
    commands = [
        ["cmake", "-S", str(root / "plugin"), "-B", str(plugin_build), "-A", "x64",
         "-DMCT_ENABLE_NATIVE_MOVIE_TRIAL=ON", "-DMCT_BUILD_HOST_PROBE=OFF"],
        ["cmake", "--build", str(plugin_build), "--config", "Release", "--parallel", "2"],
        ["ctest", "--test-dir", str(plugin_build), "-C", "Release", "--output-on-failure"],
        ["cmake", "-S", str(root / "native_launcher"), "-B", str(launcher_build), "-A", "x64"],
        ["cmake", "--build", str(launcher_build), "--config", "Release", "--parallel", "2"],
        ["ctest", "--test-dir", str(launcher_build), "-C", "Release", "--output-on-failure"],
    ]
    if freeze:
        commands.append(freeze_command(root))
    _assert_isolated(commands, root)
    return commands


def build_candidate(
    root: Path | None = None,
    *,
    freeze: bool = False,
    runner=None,
    source_commit: str | None = None,
) -> dict:
    """Compile, stage, and verify. PyInstaller runs only when ``freeze`` is true."""
    root = _root(root)
    if os.name != "nt":
        raise CandidateBuildError("Build the native candidate on Windows x64")
    if runner is None:
        runner = subprocess.run
    _run(plan_commands(root, freeze=False), runner, root)
    require_host_probe_off(plugin_build_dir(root))
    images = _compiled_images(root)
    menu_files = load_menu_runtime(menu_source_dir(root))
    _preflight_runtime(staged_runtime(root))
    archives = _source_archives(root)
    commit = _commit(root, source_commit)
    sources = _source_files(root)
    dependencies = _dependencies(root)
    payloads = _payloads(root, images, menu_files, commit, sources, dependencies, archives)
    _publish_runtime(staged_runtime(root), payloads)
    manifest = _manifest(root, images, commit, sources, dependencies, archives, menu_files)
    _write_json(candidate_dir(root) / MANIFEST_NAME, manifest)
    verified = verify_candidate(root)
    if freeze:
        _run([freeze_command(root)], runner, root)
    return verified


def verify_candidate(root: Path | None = None) -> dict:
    """Re-read the staged tree, receipts, source hashes, and manifest."""
    root = _root(root)
    runtime = staged_runtime(root)
    checked = check_runtime_tree(runtime)
    manifest = check_manifest(candidate_dir(root) / MANIFEST_NAME, runtime)
    plugin = checked["plugin"]
    if manifest["source_commit"] != plugin.get("source_commit"):
        raise CandidateBuildError("candidate manifest commit does not match the plugin receipt")
    if manifest["source_files"] != plugin.get("source_files") or manifest["source_files"] != _source_files(root):
        raise CandidateBuildError("candidate manifest source hashes do not match the plugin tree")
    if manifest["dependencies"] != plugin.get("dependencies") or manifest["dependencies"] != _dependencies(root):
        raise CandidateBuildError("candidate manifest dependencies do not match plugin/DEPENDENCIES.json")
    _check_archives(root, manifest["source_archives"])
    _check_built_notice(root, manifest["notice"])
    return manifest


def bundle_entries(root: Path | None = None) -> list[tuple[str, str]]:
    """Allowlisted candidate datas for the native PyInstaller spec."""
    root = _root(root)
    verify_candidate(root)
    runtime = staged_runtime(root)
    entries: list[tuple[str, str]] = []
    for component, destination in (
        ("plugins", "my_career_training/runtime/plugins"),
        ("native", "my_career_training/runtime/native"),
        ("native-menu", "my_career_training/runtime/native-menu"),
    ):
        for path in sorted((runtime / component).iterdir(), key=lambda item: item.name):
            if path.name.lower().endswith(PROPRIETARY_SUFFIXES) or path.name in FORBIDDEN_BASENAMES:
                raise CandidateBuildError(f"refusing to package {path.name}")
            entries.append((str(path), destination))
    entries.append((str(candidate_dir(root) / MANIFEST_NAME), "."))
    return entries


def check_runtime_tree(runtime: Path, *, bundled_core: bool = False) -> dict:
    """Allowlists, image hashes, PE machine, and false capability flags."""
    runtime = Path(runtime)
    _runtime_listing(runtime, bundled_core=bundled_core)
    plugin = _check_plugin(runtime / "plugins")
    native = confirm_native_runtime(runtime / "native")
    menu = load_menu_runtime(runtime / "native-menu")
    return {"plugin": plugin, "native": native, "native_menu": _menu_receipt(menu)}


def check_manifest(path: Path, runtime: Path, *, bundled_core: bool = False) -> dict:
    manifest = _load_json(Path(path), MAX_PLUGIN_RECEIPT)
    if set(manifest) != _MANIFEST_KEYS or manifest.get("schema") != 1:
        raise CandidateBuildError("candidate manifest is not the fixed record")
    if manifest.get("kind") != "mct_native_menu_candidate":
        raise CandidateBuildError("candidate manifest kind is not a developer candidate")
    if manifest.get("distribution") != "developer_candidate":
        raise CandidateBuildError("candidate manifest distribution is not a developer candidate")
    if manifest.get("flags") != FALSE_FLAGS:
        raise CandidateBuildError("candidate manifest flags must all be false")
    if manifest.get("build") != BUILD_SWITCHES:
        raise CandidateBuildError("candidate build switches are not the native menu candidate")
    if not manifest.get("source_commit") or not manifest.get("source_files") or not manifest.get("dependencies"):
        raise CandidateBuildError("candidate manifest is missing source provenance")
    staged = _runtime_hashes(runtime, bundled_core=bundled_core)
    if manifest.get("staged_hashes") != staged:
        raise CandidateBuildError("candidate manifest hashes do not match the staged runtime")
    _check_notice_record(manifest.get("notice"), runtime)
    _check_image_record(manifest.get("images"), runtime)
    if manifest.get("receipts") != _RECEIPT_PATHS:
        raise CandidateBuildError("candidate manifest receipt paths are not the staged receipts")
    _reject_key_material(runtime, _dump(manifest))
    return manifest


def confirm_native_runtime(directory: Path) -> dict:
    """Check image bytes with ``build_runtime_receipt``, then the adapter validator."""
    receipt = _native_content(Path(directory))
    try:
        checked = native_launch.validate_native_runtime(directory)
    except native_launch.NativeLaunchError as exc:
        if exc.code != "untrusted_runtime":
            raise CandidateBuildError("native runtime validation failed") from exc
        return receipt
    if checked != receipt:
        raise CandidateBuildError("native runtime validation disagreed with the staged receipt")
    return receipt


def load_menu_runtime(directory: Path) -> dict[str, bytes]:
    """Copy inputs from an existing ``stage_native_runtime`` directory. Do not rebuild it."""
    _require_menu_contract()
    directory = Path(directory)
    if not directory.is_dir() or _is_reparse(directory):
        raise CandidateBuildError(
            "native-menu runtime is missing. Run scripts/stage_native_runtime.py before this candidate build"
        )
    names = []
    for entry in directory.iterdir():
        if entry.name not in stage_menu.STAGED_NAMES or entry.is_dir() or _is_reparse(entry):
            raise CandidateBuildError(f"native-menu runtime has an unexpected entry: {entry.name}")
        if entry.name.lower().endswith(stage_menu.FORBIDDEN_SUFFIXES) or entry.name in FORBIDDEN_BASENAMES:
            raise CandidateBuildError(f"native-menu runtime includes a forbidden payload: {entry.name}")
        names.append(entry.name)
    if set(names) != set(stage_menu.STAGED_NAMES):
        raise CandidateBuildError("native-menu runtime is missing an allowlisted file")
    files = {name: _read_file(directory / name, _menu_cap(name)) for name in stage_menu.STAGED_NAMES}
    _validate_menu_files(files)
    return files


def require_host_probe_off(plugin_build: Path) -> None:
    plugin_build = Path(plugin_build)
    if not plugin_build.is_dir() or _is_reparse(plugin_build):
        raise CandidateBuildError("candidate plugin build directory is missing")
    for path in plugin_build.rglob("MCTNativeHostProbe.dll"):
        if path.is_file() and not _is_reparse(path):
            raise CandidateBuildError("host probe was built; MCT_BUILD_HOST_PROBE must stay OFF")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stage the opt-in native menu candidate.")
    parser.add_argument("--freeze", action="store_true",
                        help="Also freeze build/native-candidate/dist. Omit this to stage and verify only.")
    args = parser.parse_args(argv)
    try:
        manifest = build_candidate(freeze=args.freeze)
    except CandidateBuildError as exc:
        print(f"native candidate build refused: {exc}", file=sys.stderr)
        return 1
    print("staged native menu candidate")
    print("distribution=developer_candidate")
    print("gameplay_verified=false")
    print("game_verified=false")
    print("production_ready=false")
    print("runtime_verified=false")
    print(f"files={len(manifest['staged_hashes'])}")
    if args.freeze:
        print(f"bundle={BUNDLE_NAME}")
    return 0


def _root(root: Path | None) -> Path:
    return ROOT if root is None else Path(root)


def _run(commands: list[list[str]], runner, root: Path) -> None:
    for command in commands:
        _assert_isolated([command], root)
        try:
            result = runner(command, check=True)
        except CandidateBuildError:
            raise
        except (OSError, subprocess.CalledProcessError) as exc:
            raise CandidateBuildError("candidate build command failed") from exc
        if result is not None and getattr(result, "returncode", 0) not in (0, None):
            raise CandidateBuildError("candidate build command failed")


def _assert_isolated(commands: list[list[str]], root: Path) -> None:
    reserved = {
        str(root / "build" / "plugin"),
        str(root / "packaging" / "my-career-training.spec"),
        str(root / "packaging" / "installer.iss"),
        str(root / "runtime" / "plugins"),
        str(root / "runtime" / "native"),
        str(root / "dist"),
    }
    for command in commands:
        if command[:2] == ["cmake", "-S"] and "-B" in command:
            build_dir = command[command.index("-B") + 1]
            if not build_dir.startswith(str(candidate_dir(root))):
                raise CandidateBuildError("candidate CMake build directory is not isolated")
        for part in command:
            if part in reserved or any(token in part for token in _FORBIDDEN_ARGUMENTS):
                raise CandidateBuildError("candidate command is not isolated from the normal release")
            if "MCT_BUILD_HOST_PROBE=ON" in part or "MCT_ENABLE_NATIVE_MOVIE_TRIAL=OFF" in part:
                raise CandidateBuildError("candidate command uses the normal-release native switches")


def _compiled_images(root: Path) -> dict[str, bytes]:
    plugin = plugin_build_dir(root) / "Release" / PLUGIN_DLL
    launcher = launcher_build_dir(root) / "bin"
    helper = launcher / native_launch.HELPER_FILENAME
    view = launcher / native_launch.FILE_VIEW_FILENAME
    built_notice = launcher / SOURCE_NOTICE
    source_notice = root / "native_launcher" / SOURCE_NOTICE
    images = {
        "plugin": _read_file(plugin, MAX_PLUGIN_DLL),
        "helper": _read_file(helper, native_launch.HELPER_MAX),
        "file_view": _read_file(view, native_launch.FILE_VIEW_MAX),
    }
    notice = _read_file(built_notice, 64 * 1024)
    source = _read_file(source_notice, 64 * 1024)
    if notice != source:
        raise CandidateBuildError("built NOTICE does not match native_launcher/NOTICE")
    _require_amd64_pe(images["plugin"], "dll")
    _require_amd64_pe(images["helper"], "exe")
    _require_amd64_pe(images["file_view"], "dll")
    plugin_artifact.inspect_plugin(plugin)
    images["notice_output"] = notice
    return images


def _payloads(root, images, menu_files, commit, sources, dependencies, archives) -> dict[str, dict[str, bytes]]:
    plugin_receipt = _plugin_receipt(root, images["plugin"], commit, sources, dependencies, archives)
    native_receipt = native_launch.build_runtime_receipt(
        hashlib.sha256(images["helper"]).hexdigest(), len(images["helper"]),
        hashlib.sha256(images["file_view"]).hexdigest(), len(images["file_view"]),
    )
    return {
        "plugins": {
            PLUGIN_DLL: images["plugin"],
            PLUGIN_RECEIPT: _dump(plugin_receipt),
        },
        "native": {
            native_launch.HELPER_FILENAME: images["helper"],
            native_launch.FILE_VIEW_FILENAME: images["file_view"],
            native_launch.NOTICE_FILENAME: native_launch.DETOURS_NOTICE_BYTES,
            native_launch.BUILD_RECEIPT_FILENAME: _dump(native_receipt),
        },
        "native-menu": menu_files,
    }


def _plugin_receipt(root, dll: bytes, commit, sources, dependencies, archives) -> dict:
    path = plugin_build_dir(root) / "Release" / PLUGIN_DLL
    return {
        "architecture": "x64",
        "artifact": PLUGIN_DLL,
        "configuration": "Release",
        "dependencies": dependencies,
        "gameplay_verified": False,
        "native": plugin_artifact.inspect_plugin(path),
        "native_host_probe": False,
        "native_movie_trial": True,
        "protocol": 1,
        "sha256": hashlib.sha256(dll).hexdigest(),
        "source_archives": archives,
        "source_commit": commit,
        "source_files": sources,
    }


def _manifest(root, images, commit, sources, dependencies, archives, menu_files) -> dict:
    runtime = staged_runtime(root)
    notice = images["notice_output"]
    manifest = {
        "build": dict(BUILD_SWITCHES),
        "dependencies": dependencies,
        "distribution": "developer_candidate",
        "flags": dict(FALSE_FLAGS),
        "images": {
            "file_view": _image_record(images["file_view"]),
            "helper": _image_record(images["helper"]),
            "plugin": _image_record(images["plugin"]),
        },
        "kind": "mct_native_menu_candidate",
        "notice": {
            "launcher_output_bytes": len(notice),
            "launcher_output_name": SOURCE_NOTICE,
            "launcher_output_sha256": hashlib.sha256(notice).hexdigest(),
            "source_bytes": len(notice),
            "source_name": "native_launcher/NOTICE",
            "source_sha256": hashlib.sha256(notice).hexdigest(),
            "staged_bytes": native_launch.DETOURS_NOTICE_SIZE,
            "staged_name": native_launch.NOTICE_FILENAME,
            "staged_sha256": native_launch.DETOURS_NOTICE_SHA256,
        },
        "receipts": dict(_RECEIPT_PATHS),
        "schema": 1,
        "source_archives": archives,
        "source_commit": commit,
        "source_files": sources,
        "staged_hashes": _runtime_hashes(runtime),
    }
    _reject_key_material(runtime, _dump(manifest), menu_files.get("decoder_config.bin"))
    return manifest


def _image_record(blob: bytes) -> dict:
    return {"bytes": len(blob), "machine": "AMD64", "sha256": hashlib.sha256(blob).hexdigest()}


def _check_plugin(directory: Path) -> dict:
    dll = directory / PLUGIN_DLL
    receipt = _load_json(directory / PLUGIN_RECEIPT, MAX_PLUGIN_RECEIPT)
    blob = _read_file(dll, MAX_PLUGIN_DLL)
    _require_amd64_pe(blob, "dll")
    native = plugin_artifact.inspect_plugin(dll)
    if native.get("machine") != "AMD64" or native.get("dll") is not True:
        raise CandidateBuildError("candidate plugin is not an AMD64 DLL")
    if hashlib.sha256(blob).hexdigest() != receipt.get("sha256"):
        raise CandidateBuildError("candidate plugin receipt hash does not match the DLL")
    if receipt.get("native") != native:
        raise CandidateBuildError("candidate plugin PE inspection does not match its receipt")
    if receipt.get("native_movie_trial") is not True:
        raise CandidateBuildError("candidate plugin native_movie_trial must be true")
    if receipt.get("native_host_probe") is not False or receipt.get("gameplay_verified") is not False:
        raise CandidateBuildError("candidate plugin flags claim a host probe or verified gameplay")
    if receipt.get("architecture") != "x64" or receipt.get("configuration") != "Release":
        raise CandidateBuildError("candidate plugin is not the Release x64 build")
    if not receipt.get("source_commit") or not receipt.get("source_files") or not receipt.get("dependencies"):
        raise CandidateBuildError("candidate plugin receipt is missing source provenance")
    return receipt


def _native_content(directory: Path) -> dict:
    names = []
    for entry in directory.iterdir():
        if entry.name == SOURCE_NOTICE:
            raise CandidateBuildError("native runtime must stage DETOURS-MIT-LICENSE.txt, not NOTICE")
        if entry.name not in native_launch.RUNTIME_FILENAMES or entry.is_dir() or _is_reparse(entry):
            raise CandidateBuildError(f"native runtime has an unexpected entry: {entry.name}")
        if entry.name.lower().endswith(PROPRIETARY_SUFFIXES) or (
            entry.name in FORBIDDEN_BASENAMES and entry.name not in native_launch.RUNTIME_FILENAMES
        ):
            raise CandidateBuildError(f"native runtime includes a forbidden payload: {entry.name}")
        names.append(entry.name)
    if set(names) != set(native_launch.RUNTIME_FILENAMES):
        raise CandidateBuildError("native runtime is missing an allowlisted file")
    helper = _read_file(directory / native_launch.HELPER_FILENAME, native_launch.HELPER_MAX)
    view = _read_file(directory / native_launch.FILE_VIEW_FILENAME, native_launch.FILE_VIEW_MAX)
    notice = _read_file(directory / native_launch.NOTICE_FILENAME, native_launch.DETOURS_NOTICE_SIZE)
    _require_amd64_pe(helper, "exe")
    _require_amd64_pe(view, "dll")
    if notice != native_launch.DETOURS_NOTICE_BYTES:
        raise CandidateBuildError("Detours notice bytes do not match the launch adapter")
    expected = native_launch.build_runtime_receipt(
        hashlib.sha256(helper).hexdigest(), len(helper),
        hashlib.sha256(view).hexdigest(), len(view),
    )
    parsed = _load_json(directory / native_launch.BUILD_RECEIPT_FILENAME, native_launch.BUILD_RECEIPT_MAX)
    if parsed != expected:
        raise CandidateBuildError("native runtime receipt does not match the staged images")
    return parsed


def _validate_menu_files(files: dict[str, bytes]) -> None:
    receipt_blob = files[stage_menu.RECEIPT_NAME]
    key = files["decoder_config.bin"]
    if key.hex().encode("ascii") in receipt_blob.lower():
        raise CandidateBuildError("native-menu receipt would have included decoder key material")
    try:
        receipt = json.loads(receipt_blob.decode("utf-8"), object_pairs_hook=_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError, CandidateBuildError):
        raise CandidateBuildError("native-menu receipt could not be read") from None
    if set(receipt) != MENU_RECEIPT_KEYS or receipt.get("schema") != 1:
        raise CandidateBuildError("native-menu receipt is not the staged native menu record")
    if receipt.get("kind") != "native_menu_runtime":
        raise CandidateBuildError("native-menu receipt kind is not native_menu_runtime")
    for flag in MENU_FALSE_FLAGS:
        if receipt.get(flag) is not False:
            raise CandidateBuildError(f"native-menu receipt flag is not false: {flag}")
    pins = receipt.get("pins")
    provenance = receipt.get("provenance")
    listed = receipt.get("files")
    if type(pins) is not dict or set(pins) != MENU_PIN_KEYS:
        raise CandidateBuildError("native-menu receipt pins are malformed")
    if type(provenance) is not dict or set(provenance) != MENU_PROVENANCE_KEYS:
        raise CandidateBuildError("native-menu receipt provenance is malformed")
    if type(listed) is not dict or set(listed) != set(stage_menu.PAYLOAD_NAMES):
        raise CandidateBuildError("native-menu receipt files are not the allowlist")
    _require_fixed_pins(pins, provenance)
    for name, meta in listed.items():
        if type(meta) is not dict or set(meta) != {"bytes", "sha256"}:
            raise CandidateBuildError("native-menu receipt files are malformed")
        blob = files[name]
        if meta["bytes"] != len(blob) or meta["sha256"] != hashlib.sha256(blob).hexdigest():
            raise CandidateBuildError(f"native-menu file hash does not match its receipt: {name}")
    if len(key) != 32:
        raise CandidateBuildError("staged decoder configuration is malformed")
    license_blob = files["UEViewer-LICENSE.txt"]
    if len(license_blob) != menu_assets.LICENSE_BYTES or _sha(license_blob) != menu_assets.LICENSE_SHA256:
        raise CandidateBuildError("staged license does not match the UEViewer pin")
    manifest = _load_manifest(files["manifest.json"])
    if manifest.get("runtime_verified") is not False or manifest.get("production_ready") is not False:
        raise CandidateBuildError("native-menu manifest grants runtime capability")
    if manifest.get("game_classes_linked") is not False or manifest.get("classes") != list(menu_assets.AUTHORED_CLASSES):
        raise CandidateBuildError("native-menu manifest classes are not the authored classes")
    if pins["abc_sha256"] != _sha(files["MctRootMenu.abc"]) or pins["abc_bytes"] != len(files["MctRootMenu.abc"]):
        raise CandidateBuildError("staged ABC does not match the native-menu receipt")
    _require_hex(pins.get("abc_sha256"), "native-menu receipt pins are malformed")
    _require_hex(pins.get("source_sha256"), "native-menu receipt pins are malformed")
    _require_hex(pins.get("screen_source_sha256"), "native-menu receipt pins are malformed")
    if pins["source_sha256"] != manifest.get("source_sha256"):
        raise CandidateBuildError("native-menu manifest source pin does not match")
    if pins["screen_source_sha256"] != manifest.get("screen_source_sha256"):
        raise CandidateBuildError("native-menu manifest screen pin does not match")


def _require_fixed_pins(pins: dict, provenance: dict) -> None:
    expected = {
        "executable_relative": menu_assets.EXECUTABLE_RELATIVE,
        "executable_sha256": menu_assets.EXECUTABLE_SHA256,
        "export_name": menu_assets.EXPORT_NAME,
        "movie_sha256": menu_assets.MOVIE_SHA256,
        "package_relative": menu_assets.PACKAGE_RELATIVE,
        "package_sha256": menu_assets.PACKAGE_SHA256,
        "runtime_build": menu_assets.RUNTIME_BUILD,
    }
    for key, value in expected.items():
        if pins.get(key) != value:
            raise CandidateBuildError("native-menu receipt pins do not match the current adapter")
    if pins.get("bakkesmod_core") != menu_assets.BAKKESMOD_CORE:
        raise CandidateBuildError("native-menu receipt pins do not match the current adapter")
    if pins.get("classes") != list(menu_assets.AUTHORED_CLASSES):
        raise CandidateBuildError("native-menu receipt pins do not match the current adapter")
    if provenance.get("ueviewer_commit") != menu_assets.UEVIEWER_COMMIT:
        raise CandidateBuildError("native-menu receipt provenance does not match the UEViewer pin")
    if provenance.get("source_sha256") != menu_assets.SOURCE_SHA256 or provenance.get("source_bytes") != menu_assets.SOURCE_BYTES:
        raise CandidateBuildError("native-menu receipt provenance does not match the UEViewer pin")
    if provenance.get("license_sha256") != menu_assets.LICENSE_SHA256 or provenance.get("license_bytes") != menu_assets.LICENSE_BYTES:
        raise CandidateBuildError("native-menu receipt provenance does not match the UEViewer pin")
    if provenance.get("license_name") != "MIT" or provenance.get("copyright") != "Copyright 2022, Konstantin Nosov":
        raise CandidateBuildError("native-menu receipt provenance does not match the UEViewer pin")
    if provenance.get("source_url") != menu_assets.SOURCE_URL or provenance.get("license_url") != menu_assets.LICENSE_URL:
        raise CandidateBuildError("native-menu receipt provenance does not match the UEViewer pin")


def _require_menu_contract() -> None:
    if set(stage_menu.PAYLOAD_NAMES) != set(menu_assets.PAYLOAD_NAMES):
        raise CandidateBuildError("native menu allowlists disagree")
    if stage_menu.RECEIPT_NAME != menu_assets.RECEIPT_NAME:
        raise CandidateBuildError("native menu receipt names disagree")
    if stage_menu.STAGED_NAMES != set(stage_menu.PAYLOAD_NAMES) | {stage_menu.RECEIPT_NAME}:
        raise CandidateBuildError("native menu allowlist is not the staged receipt set")
    pairs = (
        (stage_menu.EXECUTABLE_SHA256, menu_assets.EXECUTABLE_SHA256),
        (stage_menu.PACKAGE_SHA256, menu_assets.PACKAGE_SHA256),
        (stage_menu.MOVIE_SHA256, menu_assets.MOVIE_SHA256),
        (stage_menu.LICENSE_SHA256, menu_assets.LICENSE_SHA256),
        (stage_menu.SOURCE_SHA256, menu_assets.SOURCE_SHA256),
    )
    if any(left != right for left, right in pairs):
        raise CandidateBuildError("native menu pins disagree between the stage helper and the runtime module")


def _menu_receipt(files: dict[str, bytes]) -> dict:
    return json.loads(files[stage_menu.RECEIPT_NAME].decode("utf-8"))


def _load_manifest(blob: bytes) -> dict:
    try:
        manifest = json.loads(blob.decode("utf-8"), object_pairs_hook=_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError, CandidateBuildError):
        raise CandidateBuildError("native-menu manifest could not be read") from None
    if type(manifest) is not dict:
        raise CandidateBuildError("native-menu manifest could not be read")
    return manifest


def _check_built_notice(root: Path, notice: dict) -> None:
    built = _read_file(launcher_build_dir(root) / "bin" / SOURCE_NOTICE, 64 * 1024)
    source = _read_file(root / "native_launcher" / SOURCE_NOTICE, 64 * 1024)
    if built != source or notice.get("launcher_output_sha256") != _sha(built):
        raise CandidateBuildError("built NOTICE does not match native_launcher/NOTICE")
    if notice.get("source_sha256") != _sha(source) or notice.get("launcher_output_bytes") != len(built):
        raise CandidateBuildError("candidate notice provenance does not match the launcher NOTICE bytes")


def _check_notice_record(notice: object, runtime: Path) -> None:
    if type(notice) is not dict:
        raise CandidateBuildError("candidate notice provenance is missing")
    staged = _read_file(runtime / "native" / native_launch.NOTICE_FILENAME, native_launch.DETOURS_NOTICE_SIZE)
    if staged != native_launch.DETOURS_NOTICE_BYTES:
        raise CandidateBuildError("Detours notice bytes do not match the launch adapter")
    if notice.get("staged_name") != native_launch.NOTICE_FILENAME:
        raise CandidateBuildError("candidate notice was not staged under the launch adapter name")
    if notice.get("staged_sha256") != native_launch.DETOURS_NOTICE_SHA256 or notice.get("staged_bytes") != native_launch.DETOURS_NOTICE_SIZE:
        raise CandidateBuildError("candidate notice pin does not match the launch adapter")
    if notice.get("launcher_output_name") != SOURCE_NOTICE or notice.get("source_name") != "native_launcher/NOTICE":
        raise CandidateBuildError("candidate notice provenance does not name the launcher NOTICE output")
    if notice.get("source_sha256") != notice.get("launcher_output_sha256"):
        raise CandidateBuildError("built NOTICE does not match native_launcher/NOTICE")
    if type(notice.get("launcher_output_bytes")) is not int or notice["launcher_output_bytes"] < 1:
        raise CandidateBuildError("candidate notice provenance is missing the launcher NOTICE hash")


def _check_image_record(images: object, runtime: Path) -> None:
    if type(images) is not dict or set(images) != {"file_view", "helper", "plugin"}:
        raise CandidateBuildError("candidate image hashes are missing")
    paths = {
        "plugin": runtime / "plugins" / PLUGIN_DLL,
        "helper": runtime / "native" / native_launch.HELPER_FILENAME,
        "file_view": runtime / "native" / native_launch.FILE_VIEW_FILENAME,
    }
    for name, path in paths.items():
        blob = path.read_bytes()
        if images.get(name) != _image_record(blob):
            raise CandidateBuildError(f"candidate {name} image hash does not match the staged file")


def _runtime_listing(runtime: Path, *, bundled_core: bool = False) -> None:
    if not runtime.is_dir() or _is_reparse(runtime):
        raise CandidateBuildError("candidate runtime directory is missing")
    names = {item.name for item in runtime.iterdir()}
    expected = set(_COMPONENT_ALLOWLISTS)
    if bundled_core:
        expected.add("RLBotServer.exe")
        core = _read_file(runtime / "RLBotServer.exe", 100 * 1024 * 1024)
        if _sha(core) != RLBOT_SHA256:
            raise CandidateBuildError("bundled RLBot core checksum does not match the pinned runtime")
    if names != expected:
        unexpected = sorted(names - expected)
        if unexpected:
            raise CandidateBuildError(f"candidate runtime has an unexpected entry: {unexpected[0]}")
        raise CandidateBuildError("candidate runtime is missing plugins, native, or native-menu")
    for component, allowlist in _COMPONENT_ALLOWLISTS.items():
        directory = runtime / component
        seen = set()
        for entry in directory.iterdir():
            if entry.name not in allowlist or entry.is_dir() or _is_reparse(entry) or not stat.S_ISREG(entry.lstat().st_mode):
                raise CandidateBuildError(f"candidate {component} runtime has an unexpected entry: {entry.name}")
            if entry.name.lower().endswith(PROPRIETARY_SUFFIXES) or entry.name in FORBIDDEN_BASENAMES:
                raise CandidateBuildError(f"candidate runtime includes a forbidden payload: {entry.name}")
            seen.add(entry.name)
        if seen != set(allowlist):
            raise CandidateBuildError(f"candidate {component} runtime is not the allowlist")


def _runtime_hashes(runtime: Path, *, bundled_core: bool = False) -> dict[str, dict[str, int | str]]:
    _runtime_listing(runtime, bundled_core=bundled_core)
    found = {}
    for component, allowlist in _COMPONENT_ALLOWLISTS.items():
        for name in sorted(allowlist):
            blob = (runtime / component / name).read_bytes()
            found[f"runtime/{component}/{name}"] = {"bytes": len(blob), "sha256": _sha(blob)}
    return found


def _reject_key_material(runtime: Path, encoded: bytes, key: bytes | None = None) -> None:
    if key is None:
        path = runtime / "native-menu" / "decoder_config.bin"
        if path.is_file():
            key = path.read_bytes()
    if key and key.hex().encode("ascii") in encoded.lower():
        raise CandidateBuildError("candidate manifest would have included decoder key material")


def _source_files(root: Path) -> dict[str, str]:
    plugin = root / "plugin"
    found = {}
    for path in _iter_files(plugin):
        if path.suffix.lower() in PROPRIETARY_SUFFIXES or path.name in FORBIDDEN_BASENAMES:
            raise CandidateBuildError(f"plugin source includes a forbidden payload: {path.name}")
        found[path.relative_to(root).as_posix()] = _sha(_read_file(path, MAX_SOURCE_FILE))
    if not found:
        raise CandidateBuildError("plugin source directory is empty")
    return dict(sorted(found.items()))


def _dependencies(root: Path) -> dict:
    payload = _load_json(root / "plugin" / "DEPENDENCIES.json", MAX_MENU_RECEIPT)
    if type(payload) is not dict or not payload:
        raise CandidateBuildError("plugin dependencies are missing")
    return payload


def _source_archives(root: Path) -> list[dict]:
    sources = []
    for component, parts in ARCHIVE_COMPONENTS:
        source = root / "plugin" if parts is None else plugin_build_dir(root).joinpath(*parts)
        sources.append((component, source, list(_iter_files(source))))
    destination = candidate_dir(root) / "source-archives"
    destination.mkdir(parents=True, exist_ok=True)
    records = []
    for component, source, _files in sources:
        archive = Path(shutil.make_archive(str(destination / component), "zip", root_dir=source))
        if archive.parent != destination or archive.suffix.lower() != ".zip":
            raise CandidateBuildError("candidate source archive escaped its directory")
        records.append({
            "archive": archive.name,
            "component": component,
            "sha256": _sha(archive.read_bytes()),
        })
    if [item["component"] for item in records] != [name for name, _parts in ARCHIVE_COMPONENTS]:
        raise CandidateBuildError("candidate source archives are not the plugin redistribution set")
    return records


def _check_archives(root: Path, records: object) -> None:
    if type(records) is not list or [item.get("component") for item in records if type(item) is dict] != [
        name for name, _parts in ARCHIVE_COMPONENTS
    ]:
        raise CandidateBuildError("candidate source archives are not the plugin redistribution set")
    destination = candidate_dir(root) / "source-archives"
    for record in records:
        name = record.get("archive")
        if type(name) is not str or name != Path(name).name or not name.endswith(".zip"):
            raise CandidateBuildError("candidate source archive name is not allowed")
        blob = _read_file(destination / name, 64 * 1024 * 1024)
        if _sha(blob) != record.get("sha256"):
            raise CandidateBuildError("candidate source archive hash does not match")


def _commit(root: Path, source_commit: str | None) -> str:
    if source_commit is None:
        try:
            source_commit = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=root, text=True,
            ).strip()
        except (OSError, subprocess.CalledProcessError) as exc:
            raise CandidateBuildError("candidate source commit could not be read") from exc
    if type(source_commit) is not str or len(source_commit) != 40 or any(char not in "0123456789abcdef" for char in source_commit):
        raise CandidateBuildError("candidate source commit must be 40 lowercase hex characters")
    return source_commit


def _preflight_runtime(runtime: Path) -> None:
    if not runtime.exists():
        return
    if _is_reparse(runtime) or not runtime.is_dir():
        raise CandidateBuildError("candidate runtime directory is not a directory; it was left in place")
    for entry in runtime.iterdir():
        if entry.name not in _COMPONENT_ALLOWLISTS:
            raise CandidateBuildError(f"candidate runtime has an unexpected entry: {entry.name}")
        allowlist = _COMPONENT_ALLOWLISTS[entry.name]
        if _unexpected(entry, allowlist):
            raise CandidateBuildError(f"candidate {entry.name} directory has an unexpected entry; it was left in place")


def _publish_runtime(runtime: Path, payloads: dict[str, dict[str, bytes]]) -> None:
    _preflight_runtime(runtime)
    runtime_existed = runtime.exists()
    prepared: list[tuple[Path | None, Path, frozenset[str]]] = []
    try:
        for component, files in payloads.items():
            allowlist = _COMPONENT_ALLOWLISTS[component]
            if set(files) != set(allowlist):
                raise CandidateBuildError("publish set is not the allowlist")
            destination = runtime / component
            if _matches(destination, files):
                prepared.append((None, destination, allowlist))
                continue
            prepared.append((_write_staging(destination, files, allowlist), destination, allowlist))
        for staging, destination, _allowlist in prepared:
            if destination.name == "native":
                confirm_native_runtime(destination if staging is None else staging)
        for staging, destination, allowlist in prepared:
            if staging is not None:
                _swap(staging, destination, allowlist)
    except Exception:
        for staging, _destination, allowlist in prepared:
            if staging is not None:
                _discard_staging(staging, allowlist)
        if not runtime_existed and runtime.exists() and not any(runtime.iterdir()):
            runtime.rmdir()
        raise


def _matches(destination: Path, files: dict[str, bytes]) -> bool:
    if not destination.exists():
        return False
    for name, payload in files.items():
        path = destination / name
        if not path.is_file() or _is_reparse(path) or path.read_bytes() != payload:
            return False
    return True


def _unexpected(destination: Path, allowlist: frozenset[str]) -> bool:
    if not destination.exists():
        return False
    if _is_reparse(destination) or not destination.is_dir():
        return True
    for child in destination.iterdir():
        if child.name not in allowlist or child.is_dir() or _is_reparse(child):
            return True
        if not stat.S_ISREG(child.lstat().st_mode):
            return True
    return False


def _write_staging(destination: Path, files: dict[str, bytes], allowlist: frozenset[str]) -> Path:
    parent = destination.parent
    if not parent.exists():
        parent.mkdir(parents=True)
    elif not parent.is_dir() or _is_reparse(parent):
        raise CandidateBuildError("candidate runtime parent is not a directory")
    staging = parent / f".{destination.name}.staging-{uuid.uuid4().hex}"
    staging.mkdir()
    for name, payload in files.items():
        if name not in allowlist:
            raise CandidateBuildError("refusing to stage a file outside the allowlist")
        _write_exclusive(staging / name, payload)
    return staging


def _swap(staging: Path, destination: Path, allowlist: frozenset[str]) -> None:
    if not destination.exists():
        os.rename(staging, destination)
        return
    if _unexpected(destination, allowlist):
        raise CandidateBuildError("candidate directory has an unexpected entry; it was left in place")
    replaced = destination.parent / f".{destination.name}.replaced-{uuid.uuid4().hex}"
    os.rename(destination, replaced)
    try:
        os.rename(staging, destination)
    except Exception:
        os.rename(replaced, destination)
        raise
    _remove_allowlisted_directory(replaced, allowlist)


def _write_exclusive(path: Path, payload: bytes) -> None:
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise CandidateBuildError("candidate file could not be written") from exc
    try:
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise CandidateBuildError("candidate file could not be written")
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _discard_staging(path: Path, allowlist: frozenset[str]) -> None:
    if ".staging-" not in path.name or not path.exists():
        return
    try:
        _remove_allowlisted_directory(path, allowlist)
    except CandidateBuildError:
        return


def _remove_allowlisted_directory(path: Path, allowlist: frozenset[str]) -> None:
    for child in path.iterdir():
        if child.name not in allowlist or child.is_dir() or _is_reparse(child):
            raise CandidateBuildError("staging directory has an unexpected entry; it was left in place")
        os.remove(child)
    path.rmdir()


def _write_json(path: Path, payload: dict) -> None:
    temporary = path.with_name(f".{path.name}.staging-{uuid.uuid4().hex}")
    _write_exclusive(temporary, _dump(payload))
    os.replace(temporary, path)


def _iter_files(directory: Path):
    if _is_reparse(directory) or not directory.is_dir():
        raise CandidateBuildError(f"source dependency is missing: {directory.name}")
    root = directory.resolve()
    found = False
    for path in sorted(directory.rglob("*")):
        if _is_reparse(path):
            raise CandidateBuildError(f"source dependency has a reparse point: {path.name}")
        if not path.is_file():
            continue
        resolved = path.resolve()
        if root not in resolved.parents:
            raise CandidateBuildError(f"source dependency escaped its directory: {path.name}")
        if path.name in FORBIDDEN_BASENAMES or path.suffix.lower() in PROPRIETARY_SUFFIXES:
            raise CandidateBuildError(f"source dependency includes a forbidden payload: {path.name}")
        found = True
        yield path
    if not found:
        raise CandidateBuildError(f"source dependency is empty: {directory.name}")


def _require_amd64_pe(blob: bytes, kind: str) -> None:
    if kind not in {"exe", "dll"} or len(blob) < 64 or blob[:2] != b"MZ":
        raise CandidateBuildError("image is not a Windows executable")
    offset = int.from_bytes(blob[60:64], "little")
    if offset < 64 or offset > 4096 or offset + 26 > len(blob) or blob[offset:offset + 4] != b"PE\0\0":
        raise CandidateBuildError("image is not a Windows executable")
    machine = int.from_bytes(blob[offset + 4:offset + 6], "little")
    characteristics = int.from_bytes(blob[offset + 22:offset + 24], "little")
    magic = int.from_bytes(blob[offset + 24:offset + 26], "little")
    if machine != 0x8664 or magic != 0x20B:
        raise CandidateBuildError("image is not AMD64 PE32+")
    if characteristics & 0x0002 == 0:
        raise CandidateBuildError("image is not executable")
    is_dll = bool(characteristics & 0x2000)
    if kind == "dll" and not is_dll:
        raise CandidateBuildError("image is not a DLL")
    if kind == "exe" and is_dll:
        raise CandidateBuildError("helper must be an executable")


def _menu_cap(name: str) -> int:
    if name == stage_menu.RECEIPT_NAME:
        return MAX_MENU_RECEIPT
    return MENU_FILE_CAPS[name]


def _read_file(path: Path, limit: int) -> bytes:
    if _is_reparse(path) or not path.is_file():
        raise CandidateBuildError(f"required candidate file is missing: {path.name}")
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode):
        raise CandidateBuildError(f"required candidate file is missing: {path.name}")
    if info.st_size > limit:
        raise CandidateBuildError(f"{path.name} exceeds the size cap")
    if info.st_size < 1:
        raise CandidateBuildError(f"required candidate file is empty: {path.name}")
    blob = path.read_bytes()
    if len(blob) != info.st_size:
        raise CandidateBuildError(f"required candidate file changed while it was read: {path.name}")
    return blob


def _load_json(path: Path, limit: int) -> dict:
    blob = _read_file(path, limit)
    if blob.startswith(b"\xef\xbb\xbf"):
        raise CandidateBuildError(f"{path.name} is not valid JSON")
    try:
        value = json.loads(blob.decode("utf-8"), object_pairs_hook=_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError, CandidateBuildError):
        raise CandidateBuildError(f"{path.name} is not valid JSON") from None
    if type(value) is not dict:
        raise CandidateBuildError(f"{path.name} is not a JSON object")
    return value


def _pairs(items: list) -> dict:
    result = {}
    for key, value in items:
        if type(key) is not str or key in result:
            raise CandidateBuildError("JSON object repeats a field")
        result[key] = value
    return result


def _dump(payload: dict) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _require_hex(value: object, message: str) -> None:
    if type(value) is not str or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise CandidateBuildError(message)


def _sha(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def _is_reparse(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        checker = getattr(path, "is_junction", None)
        if checker is not None and checker():
            return True
        info = path.lstat()
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise CandidateBuildError("path could not be checked") from exc
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", _REPARSE)
    return bool(getattr(info, "st_file_attributes", 0) & flag)


_COMPONENT_ALLOWLISTS = {
    "plugins": frozenset({PLUGIN_DLL, PLUGIN_RECEIPT}),
    "native": frozenset(native_launch.RUNTIME_FILENAMES),
    "native-menu": stage_menu.STAGED_NAMES,
}
_RECEIPT_PATHS = {
    "native": "runtime/native/native-launch-receipt.json",
    "native_menu": "runtime/native-menu/receipt.json",
    "plugin": "runtime/plugins/plugin-build-receipt.json",
}
_MANIFEST_KEYS = frozenset({
    "build", "dependencies", "distribution", "flags", "images", "kind", "notice",
    "receipts", "schema", "source_archives", "source_commit", "source_files", "staged_hashes",
})


if __name__ == "__main__":
    raise SystemExit(main())
