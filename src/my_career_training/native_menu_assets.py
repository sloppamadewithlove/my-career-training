"""Prepare one private native menu package from the pinned installation.

The staged helpers under ``runtime/native-menu`` run in the existing Python
process and use Windows CNG through those helpers. This module does not fetch
data, start a process, set ``MCT_NATIVE_MOVIE_SESSION``, or copy the result
over the installed package. ``runtime_verified`` and ``production_ready`` stay
false. A prepared file is not a live game proof.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import stat
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path


class NativeMenuAssetsError(RuntimeError):
    """Preparation refused. Installed files were not modified."""


EXECUTABLE_SHA256 = "56b499a85ad927c6b5cc47cb4813f956dd9263405fdf4eddc65b669b53185bc7"
EXECUTABLE_RELATIVE = "Binaries/Win64/RocketLeague.exe"
PACKAGE_SHA256 = "d3e0eeadd2766fa1fb10c2d220c22a84ab2f26fb6bbb89b414a26ef1fd6e2f65"
PACKAGE_RELATIVE = "TAGame/CookedPCConsole/GFX_MainMenu_SF.upk"
MOVIE_SHA256 = "57582fb10fe1e2551989bf15d8aec1df8b62392903974a1e8ea40ac2b1734ec0"
EXPORT_NAME = "MainMenu"
RUNTIME_BUILD = "261013.63066.530866"
BAKKESMOD_CORE = 229
ENVIRONMENT_VARIABLE = "MCT_NATIVE_MOVIE_SESSION"
PRIVATE_PACKAGE_NAME = "GFX_MainMenu_SF.upk"
PREPARE_RECEIPT_NAME = "prepare-receipt.json"

UEVIEWER_COMMIT = "a0bfb468d42be831b126632fd8a0ae6b3614f981"
SOURCE_URL = (
    "https://raw.githubusercontent.com/gildor2/UEViewer/"
    f"{UEVIEWER_COMMIT}/Unreal/UnrealPackage/UnPackageReader.cpp"
)
LICENSE_URL = f"https://raw.githubusercontent.com/gildor2/UEViewer/{UEVIEWER_COMMIT}/LICENSE.txt"
SOURCE_SHA256 = "72e7700ea05b937b473451e05db873b8eb8dd9e4b41c329d6e9a0d2e7e56132d"
SOURCE_BYTES = 15390
LICENSE_SHA256 = "23831a13a99f726e62388efade7f0b8a778f1b84e40dec8a4bf4a1e481ccbdfe"
LICENSE_BYTES = 1080
AUTHORED_CLASSES = ["menus::MctRootMenu", "MctMainMenuScreen"]

PAYLOAD_NAMES = frozenset({
    "native_package_reader.py",
    "native_package_rewrite.py",
    "native_movie_compose.py",
    "MctRootMenu.abc",
    "manifest.json",
    "decoder_config.bin",
    "UEViewer-LICENSE.txt",
})
RECEIPT_NAME = "receipt.json"
_CAPS = {
    "native_package_reader.py": 1024 * 1024,
    "native_package_rewrite.py": 1024 * 1024,
    "native_movie_compose.py": 1024 * 1024,
    "MctRootMenu.abc": 64 * 1024,
    "manifest.json": 64 * 1024,
    "decoder_config.bin": 32,
    "UEViewer-LICENSE.txt": 8192,
}
_MAX_EXE = 512 * 1024 * 1024
_MAX_PACKAGE = 64 * 1024 * 1024
_MAX_MOVIE = 16 * 1024 * 1024
_MAX_RECEIPT = 64 * 1024
_REPARSE = 0x400
_DEVICES = frozenset({
    "con", "prn", "aux", "nul",
    *(f"com{index}" for index in range(1, 10)),
    *(f"lpt{index}" for index in range(1, 10)),
})
_UNRESERVED = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")
_RECEIPT_KEYS = frozenset({
    "files", "installs_package", "kind", "launches_game", "loads_runtime",
    "network_at_runtime", "pins", "production_ready", "provenance",
    "runtime_verified", "schema",
})
_PIN_KEYS = frozenset({
    "abc_bytes", "abc_sha256", "bakkesmod_core", "classes", "executable_relative",
    "executable_sha256", "export_name", "movie_sha256", "package_relative",
    "package_sha256", "runtime_build", "screen_source_sha256", "source_sha256",
})
_PROVENANCE_KEYS = frozenset({
    "copyright", "license_bytes", "license_name", "license_sha256", "license_url",
    "source_bytes", "source_sha256", "source_url", "ueviewer_commit",
})
_FALSE_FLAGS = (
    "installs_package", "launches_game", "loads_runtime", "network_at_runtime",
    "production_ready", "runtime_verified",
)


@dataclass(frozen=True)
class PreparedNativeMenu:
    """Private package prepared outside the game install. It is not installed."""

    private_package: str
    private_package_sha256: str
    source_package_sha256: str
    source_movie_sha256: str
    session: str
    environment_variable: str
    environment_value: str
    view_url: str
    runtime_build: str
    supported_bakkesmod_core: int
    bakkesmod_queried: bool
    runtime_verified: bool
    production_ready: bool
    installed: bool
    launched: bool

    def environment(self) -> dict[str, str]:
        return {self.environment_variable: self.environment_value}

    def receipt(self) -> dict:
        return {
            "bakkesmod_queried": self.bakkesmod_queried,
            "environment": self.environment(),
            "installed": self.installed,
            "launched": self.launched,
            "note": (
                "Private package prepared in player data. It is not installed and the game "
                "was not launched. runtime_verified and production_ready are false."
            ),
            "private_package": self.private_package,
            "private_package_sha256": self.private_package_sha256,
            "production_ready": self.production_ready,
            "runtime_build": self.runtime_build,
            "runtime_verified": self.runtime_verified,
            "session": self.session,
            "source_movie_sha256": self.source_movie_sha256,
            "source_package_sha256": self.source_package_sha256,
            "supported_bakkesmod_core": self.supported_bakkesmod_core,
            "view_url": self.view_url,
        }


def default_runtime_directory() -> Path:
    """Source-checkout location ``<repo>/runtime/native-menu``.

    Frozen packaging must pass ``runtime_directory`` when the checkout layout
    is not the layout next to this module.
    """
    return Path(__file__).resolve().parent.parent.parent / "runtime" / "native-menu"


def prepare_native_menu(
    game_root,
    session,
    bridge_directory,
    private_root,
    runtime_directory=None,
) -> PreparedNativeMenu:
    """Prepare ``private_root/<session>/GFX_MainMenu_SF.upk`` from the pinned install.

    ``session`` is the service bridge nonce. The returned environment value is
    that nonce; this function does not write it into the process environment.
    ``BakkesMod`` is not queried. A different executable or package hash is
    refused as a different build.
    """
    if os.name != "nt":
        raise NativeMenuAssetsError("native menu preparation requires Windows")
    nonce = _session(session)
    game = _real_directory(game_root)
    bridge = _real_directory(bridge_directory)
    private = _real_directory(private_root)
    runtime = _real_directory(default_runtime_directory() if runtime_directory is None else runtime_directory)
    _require_disjoint(game, private, "private directory overlaps the game installation")
    _require_disjoint(game, bridge, "bridge directory overlaps the game installation")
    _require_disjoint(game, runtime, "runtime directory overlaps the game installation")
    _require_disjoint(private, bridge, "private directory overlaps the bridge directory")
    _require_disjoint(private, runtime, "private directory overlaps the runtime directory")
    view_url = _native_view_url(bridge)
    session_dir = private / nonce
    if _exists(session_dir):
        raise NativeMenuAssetsError("session directory already exists")
    receipt, payloads = _validated_runtime(runtime)
    reader, rewrite, composer = _import_helpers(runtime)
    _require_composer(composer, receipt, payloads["MctRootMenu.abc"])
    executable = _installed_file(game, EXECUTABLE_RELATIVE, _MAX_EXE, "installed executable was not found")
    package = _installed_file(game, PACKAGE_RELATIVE, _MAX_PACKAGE, "installed package was not found")
    if _hash_file(executable, _MAX_EXE) != EXECUTABLE_SHA256:
        raise NativeMenuAssetsError(f"installed executable is not runtime build {RUNTIME_BUILD}")
    source_hash = _hash_file(package, _MAX_PACKAGE)
    if source_hash != PACKAGE_SHA256:
        raise NativeMenuAssetsError("installed package is not the supported GFX_MainMenu_SF.upk pin")
    package_bytes = _read_file(package, _MAX_PACKAGE)
    if hashlib.sha256(package_bytes).hexdigest() != source_hash:
        raise NativeMenuAssetsError("installed package changed during preparation")
    private_bytes, movie_hash = _compose_private(
        reader, rewrite, composer, package, package_bytes, payloads["MctRootMenu.abc"],
        payloads["decoder_config.bin"], nonce, view_url,
    )
    if _hash_file(package, _MAX_PACKAGE) != source_hash:
        raise NativeMenuAssetsError("installed package changed during preparation")
    result = _result(session_dir / PRIVATE_PACKAGE_NAME, private_bytes, source_hash, movie_hash, nonce, view_url)
    _publish_private(session_dir, private_bytes, result)
    if _hash_file(package, _MAX_PACKAGE) != source_hash:
        raise NativeMenuAssetsError("installed package changed during preparation")
    return result


def _session(value: object) -> str:
    if type(value) is not str:
        raise NativeMenuAssetsError("session nonce must be a canonical lowercase UUID")
    try:
        parsed = uuid.UUID(value)
    except ValueError:
        raise NativeMenuAssetsError("session nonce must be a canonical lowercase UUID") from None
    if str(parsed) != value:
        raise NativeMenuAssetsError("session nonce must be a canonical lowercase UUID")
    return value


def _native_view_url(bridge: Path) -> str:
    final = bridge / "native-view.json"
    if _exists(final) and _is_reparse(final):
        raise NativeMenuAssetsError("native-view.json is a reparse point")
    letter = bridge.drive[:1].upper()
    parts = final.parts[1:]
    if not letter or not parts or parts[-1] != "native-view.json":
        raise NativeMenuAssetsError("view url is not the fixed native-view.json location")
    url = f"file:///{letter}:/" + "/".join(_encode_segment(part) for part in parts)
    if len(url) > 4096 or any(char in "\\?#@" for char in url) or not url.endswith("/native-view.json"):
        raise NativeMenuAssetsError("view url is not the fixed native-view.json location")
    return url


def _encode_segment(text: str) -> str:
    encoded = []
    for byte in text.encode("utf-8"):
        character = chr(byte)
        if byte < 128 and character in _UNRESERVED:
            encoded.append(character)
        else:
            encoded.append(f"%{byte:02X}")
    return "".join(encoded)


def _validated_runtime(runtime: Path) -> tuple[dict, dict[str, bytes]]:
    names = []
    for entry in runtime.iterdir():
        if entry.name != RECEIPT_NAME and entry.name not in PAYLOAD_NAMES:
            raise NativeMenuAssetsError("staged runtime contains an unexpected file")
        if entry.is_dir() or _is_reparse(entry):
            raise NativeMenuAssetsError("staged runtime contains an unexpected file")
        names.append(entry.name)
    if set(names) != PAYLOAD_NAMES | {RECEIPT_NAME}:
        raise NativeMenuAssetsError("staged runtime is missing a file")
    receipt = _receipt(runtime / RECEIPT_NAME)
    payloads = {}
    for name, meta in receipt["files"].items():
        payloads[name] = _payload(runtime / name, name, meta)
    _require_license(payloads["UEViewer-LICENSE.txt"], receipt)
    _require_manifest(payloads["manifest.json"], receipt)
    key = payloads["decoder_config.bin"]
    if len(key) != 32:
        raise NativeMenuAssetsError("staged decoder configuration is malformed")
    return receipt, payloads


def _receipt(path: Path) -> dict:
    data = _read_file(path, _MAX_RECEIPT)
    try:
        receipt = json.loads(data.decode("utf-8"), object_pairs_hook=_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError, NativeMenuAssetsError):
        raise NativeMenuAssetsError("staged receipt could not be read") from None
    if type(receipt) is not dict or set(receipt) != _RECEIPT_KEYS or receipt.get("schema") != 1:
        raise NativeMenuAssetsError("staged receipt could not be read")
    if receipt.get("kind") != "native_menu_runtime":
        raise NativeMenuAssetsError("staged receipt could not be read")
    for flag in _FALSE_FLAGS:
        if receipt.get(flag) is not False:
            raise NativeMenuAssetsError("staged receipt grants runtime capability")
    pins = receipt["pins"]
    provenance = receipt["provenance"]
    files = receipt["files"]
    if type(pins) is not dict or set(pins) != _PIN_KEYS:
        raise NativeMenuAssetsError("staged receipt pins are malformed")
    if type(provenance) is not dict or set(provenance) != _PROVENANCE_KEYS:
        raise NativeMenuAssetsError("staged receipt provenance is malformed")
    if type(files) is not dict or set(files) != PAYLOAD_NAMES:
        raise NativeMenuAssetsError("staged receipt files are malformed")
    _require_pin_values(pins, provenance)
    return receipt


def _pairs(pairs: list) -> dict:
    receipt = {}
    for key, value in pairs:
        if type(key) is not str or key in receipt:
            raise NativeMenuAssetsError("staged receipt could not be read")
        receipt[key] = value
    return receipt


def _require_pin_values(pins: dict, provenance: dict) -> None:
    _exact(pins, "executable_sha256", EXECUTABLE_SHA256)
    _exact(pins, "package_sha256", PACKAGE_SHA256)
    _exact(pins, "movie_sha256", MOVIE_SHA256)
    _exact(pins, "executable_relative", EXECUTABLE_RELATIVE)
    _exact(pins, "package_relative", PACKAGE_RELATIVE)
    _exact(pins, "export_name", EXPORT_NAME)
    _exact(pins, "runtime_build", RUNTIME_BUILD)
    if pins.get("bakkesmod_core") != BAKKESMOD_CORE or pins.get("classes") != AUTHORED_CLASSES:
        raise NativeMenuAssetsError("staged receipt pins do not match")
    if type(pins.get("abc_bytes")) is not int or not 0 < pins["abc_bytes"] <= _CAPS["MctRootMenu.abc"]:
        raise NativeMenuAssetsError("staged receipt pins do not match")
    _hex_field(pins, "abc_sha256")
    _hex_field(pins, "source_sha256")
    _hex_field(pins, "screen_source_sha256")
    _exact(provenance, "ueviewer_commit", UEVIEWER_COMMIT)
    _exact(provenance, "source_url", SOURCE_URL)
    _exact(provenance, "license_url", LICENSE_URL)
    _exact(provenance, "source_sha256", SOURCE_SHA256)
    _exact(provenance, "license_sha256", LICENSE_SHA256)
    _exact(provenance, "license_name", "MIT")
    _exact(provenance, "copyright", "Copyright 2022, Konstantin Nosov")
    if provenance.get("source_bytes") != SOURCE_BYTES or provenance.get("license_bytes") != LICENSE_BYTES:
        raise NativeMenuAssetsError("staged receipt provenance does not match")


def _exact(record: dict, key: str, expected: str) -> None:
    if record.get(key) != expected:
        raise NativeMenuAssetsError("staged receipt pins do not match")


def _hex_field(record: dict, key: str) -> None:
    value = record.get(key)
    if type(value) is not str or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise NativeMenuAssetsError("staged receipt pins are malformed")


def _payload(path: Path, name: str, meta: object) -> bytes:
    if type(meta) is not dict or set(meta) != {"bytes", "sha256"}:
        raise NativeMenuAssetsError("staged receipt files are malformed")
    size = meta["bytes"]
    digest = meta["sha256"]
    cap = _CAPS[name]
    if type(size) is not int or type(digest) is not str or size < 0 or size > cap:
        raise NativeMenuAssetsError(f"{name} exceeds the staged file cap")
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise NativeMenuAssetsError("staged receipt files are malformed")
    try:
        info = path.lstat()
    except OSError as exc:
        raise NativeMenuAssetsError("staged runtime is missing a file") from exc
    if _is_reparse(path) or not stat.S_ISREG(info.st_mode) or info.st_size > cap:
        raise NativeMenuAssetsError(f"{name} exceeds the staged file cap")
    data = _read_file(path, cap)
    if len(data) != size or hashlib.sha256(data).hexdigest() != digest:
        raise NativeMenuAssetsError(f"{name} does not match the staged receipt")
    return data


def _require_license(data: bytes, receipt: dict) -> None:
    meta = receipt["files"]["UEViewer-LICENSE.txt"]
    if meta["bytes"] != LICENSE_BYTES or meta["sha256"] != LICENSE_SHA256:
        raise NativeMenuAssetsError("staged license does not match the UEViewer pin")
    if hashlib.sha256(data).hexdigest() != LICENSE_SHA256 or len(data) != LICENSE_BYTES:
        raise NativeMenuAssetsError("staged license does not match the UEViewer pin")
    if b"MIT License" not in data or b"Konstantin Nosov" not in data:
        raise NativeMenuAssetsError("staged license does not match the UEViewer pin")


def _require_manifest(data: bytes, receipt: dict) -> None:
    try:
        manifest = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise NativeMenuAssetsError("staged manifest could not be read") from None
    if type(manifest) is not dict:
        raise NativeMenuAssetsError("staged manifest could not be read")
    if manifest.get("runtime_verified") is not False or manifest.get("production_ready") is not False:
        raise NativeMenuAssetsError("staged manifest grants runtime capability")
    if manifest.get("game_classes_linked") is not False or manifest.get("classes") != AUTHORED_CLASSES:
        raise NativeMenuAssetsError("staged manifest classes are not the two authored classes")
    pins = receipt["pins"]
    if manifest.get("abc_sha256") != pins["abc_sha256"] or manifest.get("abc_bytes") != pins["abc_bytes"]:
        raise NativeMenuAssetsError("staged ABC does not match the manifest")
    if manifest.get("source_sha256") != pins["source_sha256"]:
        raise NativeMenuAssetsError("staged manifest source pin does not match")
    if manifest.get("screen_source_sha256") != pins["screen_source_sha256"]:
        raise NativeMenuAssetsError("staged manifest source pin does not match")


def _import_helpers(runtime: Path):
    reader = _import_one(runtime / "native_package_reader.py", "mct_native_package_reader")
    rewrite = _import_one(runtime / "native_package_rewrite.py", "mct_native_package_rewrite")
    composer = _import_one(runtime / "native_movie_compose.py", "mct_native_movie_compose")
    required = (
        (reader, ("read_movie_bytes", "decrypt_aes256_ecb_cng")),
        (rewrite, ("replace_final_movie", "encrypt_aes256_ecb_cng")),
        (composer, ("compose_movie",)),
    )
    for module, names in required:
        for name in names:
            if not callable(getattr(module, name, None)):
                raise NativeMenuAssetsError("staged helper is missing a required function")
    return reader, rewrite, composer


def _import_one(path: Path, prefix: str):
    name = f"{prefix}_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise NativeMenuAssetsError("staged helper could not be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        # Packaged runtime files are read-only inputs. Importing a source helper
        # through SourceFileLoader would create __pycache__ here, violating the
        # exact runtime allowlist on the next session.
        exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
    except Exception as exc:
        sys.modules.pop(name, None)
        raise NativeMenuAssetsError("staged helper could not be loaded") from exc
    return module


def _require_composer(composer, receipt: dict, abc: bytes) -> None:
    abc_hash = hashlib.sha256(abc).hexdigest()
    try:
        movie = composer.MOVIE_SHA256
        mod_abc = composer.MOD_ABC_SHA256
        source = composer.SOURCE_SHA256
        screen = composer.SCREEN_SOURCE_SHA256
        new_class = composer.NEW_CLASS
        screen_class = composer.SCREEN_CLASS
        character = composer.DOCUMENT_CHARACTER
        target = composer.DOCUMENT_TARGET_NAME
    except AttributeError:
        raise NativeMenuAssetsError("staged composer pin does not match") from None
    pins = receipt["pins"]
    if movie != MOVIE_SHA256 or mod_abc != abc_hash or mod_abc != pins["abc_sha256"]:
        raise NativeMenuAssetsError("staged composer pin does not match")
    if source != pins["source_sha256"] or screen != pins["screen_source_sha256"]:
        raise NativeMenuAssetsError("staged composer pin does not match")
    if new_class != "MctRootMenu" or screen_class != "MctMainMenuScreen":
        raise NativeMenuAssetsError("staged composer pin does not match")
    if character != 0 or target != "MctMainMenuScreen":
        raise NativeMenuAssetsError("staged composer document binding does not match")
    if getattr(composer, "runtime_verified", False) is True or getattr(composer, "production_ready", False) is True:
        raise NativeMenuAssetsError("staged composer grants runtime capability")


def _compose_private(reader, rewrite, composer, package, package_bytes, abc, key, session, view_url):
    decrypt_header, encrypt_header = _callbacks(reader, rewrite, key)
    try:
        movie = reader.read_movie_bytes(os.fspath(package), EXPORT_NAME, decrypt_header)
    except NativeMenuAssetsError:
        raise
    except Exception as exc:
        raise NativeMenuAssetsError("installed movie could not be read") from exc
    data = getattr(movie, "data", None)
    if type(data) is not bytes or not data or len(data) > _MAX_MOVIE:
        raise NativeMenuAssetsError("installed movie could not be read")
    movie_hash = hashlib.sha256(data).hexdigest()
    if movie_hash != MOVIE_SHA256:
        raise NativeMenuAssetsError("installed movie is not the supported MainMenu pin")
    try:
        composed = composer.compose_movie(data, abc, session=session, view_url=view_url)
    except Exception as exc:
        raise NativeMenuAssetsError("menu movie could not be prepared") from exc
    if type(composed) is not dict or type(composed.get("data")) is not bytes:
        raise NativeMenuAssetsError("menu movie could not be prepared")
    if not composed["data"] or len(composed["data"]) > _MAX_MOVIE:
        raise NativeMenuAssetsError("menu movie could not be prepared")
    try:
        rewritten = rewrite.replace_final_movie(
            package_bytes,
            composed["data"],
            expected_package_sha256=PACKAGE_SHA256,
            expected_movie_sha256=MOVIE_SHA256,
            export_name=EXPORT_NAME,
            decrypt_header=decrypt_header,
            encrypt_header=encrypt_header,
        )
    except Exception as exc:
        raise NativeMenuAssetsError("private package could not be prepared") from exc
    private = getattr(rewritten, "data", None)
    if type(private) is not bytes or not private or len(private) > _MAX_PACKAGE:
        raise NativeMenuAssetsError("private package could not be prepared")
    return private, movie_hash


def _callbacks(reader, rewrite, key: bytes):
    def decrypt_header(region: bytes) -> bytes:
        return reader.decrypt_aes256_ecb_cng(region, key)

    def encrypt_header(region: bytes) -> bytes:
        return rewrite.encrypt_aes256_ecb_cng(region, key)

    return decrypt_header, encrypt_header


def _result(path: Path, private: bytes, source_hash: str, movie_hash: str, session: str, view_url: str):
    return PreparedNativeMenu(
        private_package=str(path),
        private_package_sha256=hashlib.sha256(private).hexdigest(),
        source_package_sha256=source_hash,
        source_movie_sha256=movie_hash,
        session=session,
        environment_variable=ENVIRONMENT_VARIABLE,
        environment_value=session,
        view_url=view_url,
        runtime_build=RUNTIME_BUILD,
        supported_bakkesmod_core=BAKKESMOD_CORE,
        bakkesmod_queried=False,
        runtime_verified=False,
        production_ready=False,
        installed=False,
        launched=False,
    )


def _publish_private(session_dir: Path, package: bytes, result: PreparedNativeMenu) -> None:
    try:
        os.mkdir(session_dir)
    except FileExistsError:
        raise NativeMenuAssetsError("session directory already exists") from None
    except OSError as exc:
        raise NativeMenuAssetsError("private package could not be written") from exc
    _write_exclusive(session_dir / f".{PRIVATE_PACKAGE_NAME}.partial", package, session_dir / PRIVATE_PACKAGE_NAME)
    encoded = (json.dumps(result.receipt(), indent=2, sort_keys=True) + "\n").encode("utf-8")
    _write_exclusive(session_dir / f".{PREPARE_RECEIPT_NAME}.partial", encoded, session_dir / PREPARE_RECEIPT_NAME)


def _write_exclusive(partial: Path, payload: bytes, final: Path) -> None:
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(partial, flags)
    except OSError as exc:
        raise NativeMenuAssetsError("private package could not be written") from exc
    try:
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise NativeMenuAssetsError("private package could not be written")
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    try:
        os.rename(partial, final)
    except OSError as exc:
        raise NativeMenuAssetsError("private package could not be written") from exc


def _installed_file(root: Path, relative: str, cap: int, missing: str) -> Path:
    path = root.joinpath(*Path(relative).parts)
    if _is_reparse(path) or not _exists(path):
        raise NativeMenuAssetsError(missing)
    resolved = path.resolve()
    if root not in resolved.parents or _is_reparse(resolved):
        raise NativeMenuAssetsError(missing)
    info = resolved.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_size > cap:
        raise NativeMenuAssetsError(missing)
    if os.path.normcase(str(resolved)) != os.path.normcase(os.path.abspath(path)):
        raise NativeMenuAssetsError("path is a reparse alias")
    return resolved


def _hash_file(path: Path, limit: int) -> str:
    if _is_reparse(path):
        raise NativeMenuAssetsError("path is not a regular file")
    flags = os.O_RDONLY
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise NativeMenuAssetsError("path could not be read") from exc
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise NativeMenuAssetsError("path is not a regular file")
        digest = hashlib.sha256()
        remaining = info.st_size
        while remaining:
            part = os.read(descriptor, min(1024 * 1024, remaining))
            if not part:
                raise NativeMenuAssetsError("file changed during read")
            digest.update(part)
            remaining -= len(part)
        if os.fstat(descriptor).st_size != info.st_size:
            raise NativeMenuAssetsError("file changed during read")
    finally:
        os.close(descriptor)
    return digest.hexdigest()


def _read_file(path: Path, limit: int) -> bytes:
    if _is_reparse(path):
        raise NativeMenuAssetsError("path is not a regular file")
    flags = os.O_RDONLY
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise NativeMenuAssetsError("path could not be read") from exc
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise NativeMenuAssetsError("path is not a regular file")
        chunks = []
        remaining = info.st_size
        while remaining:
            part = os.read(descriptor, min(1024 * 1024, remaining))
            if not part:
                raise NativeMenuAssetsError("file changed during read")
            chunks.append(part)
            remaining -= len(part)
        if os.fstat(descriptor).st_size != info.st_size:
            raise NativeMenuAssetsError("file changed during read")
    finally:
        os.close(descriptor)
    return b"".join(chunks)


def _real_directory(value: object) -> Path:
    path = _drive_path(value)
    _reject_reparse_chain(path)
    try:
        info = path.lstat()
    except OSError as exc:
        raise NativeMenuAssetsError("path is not a directory") from exc
    if not stat.S_ISDIR(info.st_mode) or _is_reparse(path):
        raise NativeMenuAssetsError("path is not a directory")
    resolved = path.resolve()
    if os.path.normcase(str(resolved)) != os.path.normcase(os.path.abspath(path)):
        raise NativeMenuAssetsError("path is a reparse alias")
    return resolved


def _drive_path(value: object) -> Path:
    if type(value) is str:
        path = Path(value)
    elif isinstance(value, Path):
        path = value
    else:
        raise NativeMenuAssetsError("path is not an absolute drive path")
    text = str(path)
    if "\x00" in text or not path.is_absolute():
        raise NativeMenuAssetsError("path is not an absolute drive path")
    if text.startswith("\\\\") or text.startswith("//") or text.startswith("\\"):
        raise NativeMenuAssetsError("path is a device or UNC path")
    if re.match(r"^[A-Za-z]:[\\/]", text) is None:
        raise NativeMenuAssetsError("path is not an absolute drive path")
    for part in path.parts[1:]:
        if part in ("", ".", "..") or part.endswith((" ", ".")) or ":" in part:
            raise NativeMenuAssetsError("path is not an absolute drive path")
        if part.casefold().split(".", 1)[0] in _DEVICES:
            raise NativeMenuAssetsError("path is a device or UNC path")
    return path


def _reject_reparse_chain(path: Path) -> None:
    current = path
    while True:
        if _exists(current) and _is_reparse(current):
            raise NativeMenuAssetsError("path is a reparse alias")
        if current.parent == current:
            return
        current = current.parent


def _require_disjoint(left: Path, right: Path, message: str) -> None:
    if left == right or left in right.parents or right in left.parents:
        raise NativeMenuAssetsError(message)


def _exists(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise NativeMenuAssetsError("path could not be checked") from exc
    return True


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
        raise NativeMenuAssetsError("path could not be checked") from exc
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", _REPARSE)
    return bool(getattr(info, "st_file_attributes", 0) & flag)
