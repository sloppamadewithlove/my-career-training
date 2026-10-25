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
MATCH_SCENE_IDS = ("midgame", "endgame")
# scripts/native_package_rewrite.py grows replace_movie in the package-relocation
# commit. Match packages call that symbol and do not fall back to replace_final_movie.
MATCH_REWRITE_SYMBOL = "replace_movie"
MIDGAME_MOVIE_SHA256 = "fa1aea999d6fff856c8c522c3a5844fdfd532fac0a23bf70369a2274e38a35b7"
MIDGAME_PACKAGE_SHA256 = "25176a42c7990fce5670f2907020a3641a521553a4aa3c583588717b36e40f50"
MIDGAME_PACKAGE_RELATIVE = "TAGame/CookedPCConsole/GFX_MidGameMenu_SF.upk"
MIDGAME_EXPORT_NAME = "MidgameMenu"
MIDGAME_PRIVATE_NAME = "GFX_MidGameMenu_SF.upk"
ENDGAME_MOVIE_SHA256 = "94830737b9ee356d5039ecd8f401f0d0734885c22be70e6139b44008e1733b3c"
ENDGAME_PACKAGE_SHA256 = "dc4735a75d5ec8ffff423c4db92c3fad1f859191bf384e20ad949e4ed757b3cc"
ENDGAME_PACKAGE_RELATIVE = "TAGame/CookedPCConsole/GFX_EndGameMenu_SF.upk"
ENDGAME_EXPORT_NAME = "EndGameMenu"
ENDGAME_PRIVATE_NAME = "GFX_EndGameMenu_SF.upk"
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
AUTHORED_CLASSES = ["menus::MctRootMenu", "MctMainMenuScreen", "MctRootMenuMovie"]
LIBRARY_COMMIT = "24c6c16aecbf0d8fcc043ae671e689b0d4b4c559"
LIBRARY_CLASSES = [
    "com.adobe.serialization.json::JSON",
    "com.adobe.serialization.json::JSONDecoder",
    "com.adobe.serialization.json::JSONEncoder",
    "com.adobe.serialization.json::JSONParseError",
    "com.adobe.serialization.json::JSONToken",
    "com.adobe.serialization.json::JSONTokenType",
    "com.adobe.serialization.json::JSONTokenizer",
]
COMPILED_CLASSES = [
    "menus::MctRootMenu",
    "MctMainMenuScreen",
    "MctRootMenuMovie",
    "com.adobe.serialization.json::JSON",
    "com.adobe.serialization.json::JSONDecoder",
    "com.adobe.serialization.json::JSONEncoder",
    "com.adobe.serialization.json::JSONTokenType",
    "com.adobe.serialization.json::JSONTokenizer",
    "com.adobe.serialization.json::JSONToken",
    "com.adobe.serialization.json::JSONParseError",
]
LIBRARY_FILES = {
    "native_ui/vendor/as3corelib/PROVENANCE.json": "f4f0d2420b305100cf2c0ae1d36e0be3ab7a77f8cba201dc1d874491b4662ea7",
    "native_ui/vendor/as3corelib/README": "d2085963bde4505f6de3d3760b53d30777b482ed443b205736f74da3c3fbc756",
    "native_ui/vendor/as3corelib/src/com/adobe/serialization/json/JSON.as": "9414b8263250237f8671f5e05ad86c92536cdbd840f52bf47ee5367b99fae5c8",
    "native_ui/vendor/as3corelib/src/com/adobe/serialization/json/JSONDecoder.as": "4f11d1427099c93135d818c70cc1f7201faa02d5375aaeaef12874531d6dfb65",
    "native_ui/vendor/as3corelib/src/com/adobe/serialization/json/JSONEncoder.as": "ae997d2e420d4115b6c9b6a2ee449879b0fdf4c67bd9f2433e3ef58d9f277c31",
    "native_ui/vendor/as3corelib/src/com/adobe/serialization/json/JSONParseError.as": "83cbdd7157d513cbc81a6c564e4f4e5e14daa58d98bafbab05ed4df4418e3638",
    "native_ui/vendor/as3corelib/src/com/adobe/serialization/json/JSONToken.as": "80ee91dbdebac33f6739d3b6026a59ff9ea14fd8bd906a1e06e83988ed9c34a8",
    "native_ui/vendor/as3corelib/src/com/adobe/serialization/json/JSONTokenType.as": "b29490ba39abb965a4b691b5693453a2b561d24bc44f47a2960a89b5845ab595",
    "native_ui/vendor/as3corelib/src/com/adobe/serialization/json/JSONTokenizer.as": "e3749db0046d7dc0f4542fa76d439b29f9100a60c8380c0c03963c191b4e16f2",
}

PAYLOAD_NAMES = frozenset({
    "native_package_reader.py",
    "native_package_rewrite.py",
    "native_movie_compose.py",
    "MctRootMenu.abc",
    "manifest.json",
    "MctPauseMenu.abc",
    "MctResultsMenu.abc",
    "match-manifest.json",
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
    "MctPauseMenu.abc": 64 * 1024,
    "MctResultsMenu.abc": 64 * 1024,
    "match-manifest.json": 64 * 1024,
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
    additional_packages: dict

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
            "additional_packages": self.additional_packages,
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
    _require_composer(
        composer, receipt, payloads["MctRootMenu.abc"], payloads["manifest.json"],
        payloads["match-manifest.json"],
        {"MctPauseMenu.abc": payloads["MctPauseMenu.abc"], "MctResultsMenu.abc": payloads["MctResultsMenu.abc"]},
    )
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
    decrypt_header, encrypt_header = _callbacks(reader, rewrite, payloads["decoder_config.bin"])
    private_bytes, movie_hash = _compose_one(
        reader, rewrite, composer.compose_movie, package, package_bytes, payloads["MctRootMenu.abc"],
        source_hash, MOVIE_SHA256, EXPORT_NAME, nonce, view_url, decrypt_header, encrypt_header,
        "replace_final_movie",
    )
    if _hash_file(package, _MAX_PACKAGE) != source_hash:
        raise NativeMenuAssetsError("installed package changed during preparation")
    match_rows = []
    for scene_id in MATCH_SCENE_IDS:
        pin = _match_pins()[scene_id]
        match_path = _installed_file(game, pin["package_relative"], _MAX_PACKAGE, "installed package was not found")
        match_hash = _hash_file(match_path, _MAX_PACKAGE)
        if match_hash != pin["package_sha256"]:
            raise NativeMenuAssetsError(f"installed package is not the supported {pin['private_name']} pin")
        match_bytes = _read_file(match_path, _MAX_PACKAGE)
        if hashlib.sha256(match_bytes).hexdigest() != match_hash:
            raise NativeMenuAssetsError("installed package changed during preparation")
        rewritten, seen_movie = _compose_one(
            reader, rewrite, _match_composer(composer, scene_id), match_path, match_bytes,
            payloads[pin["abc_name"]], match_hash, pin["movie_sha256"], pin["export_name"],
            nonce, view_url, decrypt_header, encrypt_header, MATCH_REWRITE_SYMBOL,
        )
        match_rows.append((scene_id, pin, match_path, match_hash, rewritten, seen_movie))
    for _scene_id, pin, match_path, match_hash, _rewritten, _seen in match_rows:
        if _hash_file(match_path, _MAX_PACKAGE) != match_hash:
            raise NativeMenuAssetsError("installed package changed during preparation")
    additional = {
        scene_id: _match_receipt(session_dir / pin["private_name"], rewritten, match_hash, seen_movie, pin["package_relative"])
        for scene_id, pin, _path, match_hash, rewritten, seen_movie in match_rows
    }
    result = _result(
        session_dir / PRIVATE_PACKAGE_NAME, private_bytes, source_hash, movie_hash, nonce, view_url, additional,
    )
    files = [(PRIVATE_PACKAGE_NAME, private_bytes)]
    files.extend((pin["private_name"], rewritten) for _scene_id, pin, _path, _hash, rewritten, _seen in match_rows)
    _publish_private(session_dir, files, result)
    if _hash_file(package, _MAX_PACKAGE) != source_hash:
        raise NativeMenuAssetsError("installed package changed during preparation")
    for _scene_id, _pin, match_path, match_hash, _rewritten, _seen in match_rows:
        if _hash_file(match_path, _MAX_PACKAGE) != match_hash:
            raise NativeMenuAssetsError("installed package changed during preparation")
    return result


def _match_pins() -> dict[str, dict]:
    """Live package pins. Tests can patch the hash constants before preparation."""

    codec = COMPILED_CLASSES[len(AUTHORED_CLASSES):]
    pause = ("menus::MctPauseMenu", "MctPauseMenuMovie", "MctPauseMenuScreen")
    results = ("menus::MctResultsMenu", "MctResultsMenuMovie", "MctResultsMenuScreen")
    return {
        "midgame": {
            "surface": "pause",
            "package_relative": MIDGAME_PACKAGE_RELATIVE,
            "package_sha256": MIDGAME_PACKAGE_SHA256,
            "export_name": MIDGAME_EXPORT_NAME,
            "movie_sha256": MIDGAME_MOVIE_SHA256,
            "private_name": MIDGAME_PRIVATE_NAME,
            "abc_name": "MctPauseMenu.abc",
            "menu_class": "MctPauseMenu",
            "screen_class": "MctPauseMenuScreen",
            "wrapper_class": "MctPauseMenuMovie",
            "original_root_name": "MidGameMenuMovie",
            "renamed_original_root": "MctOriginalMidGameMenuMovie",
            "document_target_name": "MctPauseMenuScreen",
            "symbol_character": 6,
            "symbol_name": "MidGameMenuMovie",
            "method_bodies": 85,
            "class_flags": (9, 8, 9, 11, 9, 9, 11, 9, 11, 9),
            "authored_classes": pause,
            "compiled_classes": pause + tuple(codec),
        },
        "endgame": {
            "surface": "results",
            "package_relative": ENDGAME_PACKAGE_RELATIVE,
            "package_sha256": ENDGAME_PACKAGE_SHA256,
            "export_name": ENDGAME_EXPORT_NAME,
            "movie_sha256": ENDGAME_MOVIE_SHA256,
            "private_name": ENDGAME_PRIVATE_NAME,
            "abc_name": "MctResultsMenu.abc",
            "menu_class": "MctResultsMenu",
            "screen_class": "MctResultsMenuScreen",
            "wrapper_class": "MctResultsMenuMovie",
            "original_root_name": "EndGameMenuMovie",
            "renamed_original_root": "MctOriginalEndGameMenuMovie",
            "document_target_name": "MctResultsMenuScreen",
            "symbol_character": 23,
            "symbol_name": "EndGameMenuMovie",
            "method_bodies": 87,
            "class_flags": (9, 8, 9, 11, 9, 9, 11, 9, 11, 9),
            "authored_classes": results,
            "compiled_classes": results + tuple(codec),
        },
    }


def _match_composer(composer, scene_id: str):
    if scene_id not in MATCH_SCENE_IDS:
        raise NativeMenuAssetsError("match scene is not midgame or endgame")

    def compose(original_gfx, mod_abc, *, session, view_url):
        return composer.compose_match_movie(
            scene_id, original_gfx, mod_abc, session=session, view_url=view_url,
        )

    return compose


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
    if manifest.get("game_classes_linked") is not False or manifest.get("authored_classes") != AUTHORED_CLASSES:
        raise NativeMenuAssetsError("staged manifest classes are not the authored classes")
    if manifest.get("library_classes") != LIBRARY_CLASSES or manifest.get("classes") != COMPILED_CLASSES:
        raise NativeMenuAssetsError("staged manifest classes are not the compiled classes")
    if manifest.get("library_commit") != LIBRARY_COMMIT or manifest.get("library_files") != LIBRARY_FILES:
        raise NativeMenuAssetsError("staged manifest library pin does not match")
    if manifest.get("root_movie_source") != "native_ui/MctRootMenuMovie.as":
        raise NativeMenuAssetsError("staged manifest source pin does not match")
    root_hash = manifest.get("root_movie_source_sha256")
    if type(root_hash) is not str or len(root_hash) != 64 or any(char not in "0123456789abcdef" for char in root_hash):
        raise NativeMenuAssetsError("staged manifest source pin does not match")
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
        (composer, ("compose_movie", "compose_match_movie")),
    )
    for module, names in required:
        for name in names:
            if not callable(getattr(module, name, None)):
                raise NativeMenuAssetsError("staged helper is missing a required function")
    if not callable(getattr(rewrite, MATCH_REWRITE_SYMBOL, None)):
        raise NativeMenuAssetsError(
            "match package rewrite requires replace_movie from scripts/native_package_rewrite.py"
        )
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


def _require_composer(composer, receipt: dict, abc: bytes, manifest_bytes: bytes, match_bytes: bytes, match_abc: dict) -> None:
    abc_hash = hashlib.sha256(abc).hexdigest()
    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
        movie = composer.MOVIE_SHA256
        mod_abc = composer.MOD_ABC_SHA256
        source = composer.SOURCE_SHA256
        screen = composer.SCREEN_SOURCE_SHA256
        root_source = composer.ROOT_MOVIE_SOURCE_SHA256
        new_class = composer.NEW_CLASS
        screen_class = composer.SCREEN_CLASS
        root_class = composer.ROOT_MOVIE_CLASS
        original_root = composer.ORIGINAL_ROOT_NAME
        renamed_root = composer.RENAMED_ORIGINAL_ROOT
        library_commit = composer.LIBRARY_COMMIT
        library_classes = list(composer.LIBRARY_CLASSES)
        compiled_classes = list(composer.COMPILED_CLASSES)
        library_files = composer.LIBRARY_FILES
        character = composer.DOCUMENT_CHARACTER
        target = composer.DOCUMENT_TARGET_NAME
    except (AttributeError, UnicodeDecodeError, json.JSONDecodeError):
        raise NativeMenuAssetsError("staged composer pin does not match") from None
    pins = receipt["pins"]
    if movie != MOVIE_SHA256 or mod_abc != abc_hash or mod_abc != pins["abc_sha256"]:
        raise NativeMenuAssetsError("staged composer pin does not match")
    if source != pins["source_sha256"] or screen != pins["screen_source_sha256"]:
        raise NativeMenuAssetsError("staged composer pin does not match")
    if root_source != manifest.get("root_movie_source_sha256"):
        raise NativeMenuAssetsError("staged composer pin does not match")
    if new_class != "MctRootMenu" or screen_class != "MctMainMenuScreen" or root_class != "MctRootMenuMovie":
        raise NativeMenuAssetsError("staged composer pin does not match")
    if original_root != "RootMenuMovie" or renamed_root != "MctOriginalRootMenuMovie":
        raise NativeMenuAssetsError("staged composer pin does not match")
    if library_commit != LIBRARY_COMMIT or library_classes != LIBRARY_CLASSES or compiled_classes != COMPILED_CLASSES:
        raise NativeMenuAssetsError("staged composer pin does not match")
    if library_files != LIBRARY_FILES or library_files != manifest.get("library_files"):
        raise NativeMenuAssetsError("staged composer pin does not match")
    if character != 0 or target != "MctMainMenuScreen":
        raise NativeMenuAssetsError("staged composer document binding does not match")
    if getattr(composer, "runtime_verified", False) is True or getattr(composer, "production_ready", False) is True:
        raise NativeMenuAssetsError("staged composer grants runtime capability")
    _require_match_composer(composer, match_bytes, match_abc)


def _require_match_composer(composer, match_bytes: bytes, match_abc: dict) -> None:
    try:
        manifest = json.loads(match_bytes.decode("utf-8"))
        profiles = composer.MATCH_PROFILES
        scene_ids = tuple(composer.MATCH_SCENE_IDS)
    except (AttributeError, UnicodeDecodeError, json.JSONDecodeError):
        raise NativeMenuAssetsError("staged composer pin does not match") from None
    if scene_ids != MATCH_SCENE_IDS or type(manifest) is not dict or type(profiles) is not dict:
        raise NativeMenuAssetsError("staged composer pin does not match")
    if manifest.get("runtime_verified") is not False or manifest.get("production_ready") is not False:
        raise NativeMenuAssetsError("staged manifest grants runtime capability")
    if manifest.get("game_classes_linked") is not False or manifest.get("library_files") != LIBRARY_FILES:
        raise NativeMenuAssetsError("staged manifest library pin does not match")
    if manifest.get("library_classes") != LIBRARY_CLASSES or manifest.get("library_commit") != LIBRARY_COMMIT:
        raise NativeMenuAssetsError("staged manifest library pin does not match")
    scenes = manifest.get("scenes")
    pins = _match_pins()
    if type(scenes) is not dict or set(scenes) != set(MATCH_SCENE_IDS) or set(profiles) != set(MATCH_SCENE_IDS):
        raise NativeMenuAssetsError("match scene is not midgame or endgame")
    for scene_id in MATCH_SCENE_IDS:
        scene = scenes[scene_id]
        profile = profiles[scene_id]
        pin = pins[scene_id]
        if type(scene) is not dict:
            raise NativeMenuAssetsError("staged manifest could not be read")
        try:
            if profile.scene_id != scene_id or scene.get("package_id") != scene_id or scene.get("surface") != pin["surface"]:
                raise NativeMenuAssetsError("match scene is not midgame or endgame")
            if profile.movie_sha256 != pin["movie_sha256"] or profile.movie_sha256 != scene.get("movie_sha256"):
                raise NativeMenuAssetsError("staged composer pin does not match")
            if profile.package_sha256 != pin["package_sha256"] or profile.package_relative != pin["package_relative"]:
                raise NativeMenuAssetsError("staged composer pin does not match")
            if profile.export_name != pin["export_name"] or scene.get("export_name") != pin["export_name"]:
                raise NativeMenuAssetsError("staged composer pin does not match")
            if profile.menu_class != pin["menu_class"] or profile.screen_class != pin["screen_class"]:
                raise NativeMenuAssetsError("staged composer pin does not match")
            if profile.wrapper_class != pin["wrapper_class"] or profile.original_root_name != pin["original_root_name"]:
                raise NativeMenuAssetsError("staged composer pin does not match")
            if profile.renamed_original_root != pin["renamed_original_root"]:
                raise NativeMenuAssetsError("staged composer pin does not match")
            if profile.symbol_character != pin["symbol_character"] or profile.symbol_name != pin["symbol_name"]:
                raise NativeMenuAssetsError("staged composer pin does not match")
            if profile.document_target_name != pin["document_target_name"] or scene.get("document_character") != 0:
                raise NativeMenuAssetsError("staged composer document binding does not match")
            if tuple(profile.authored_classes) != pin["authored_classes"]:
                raise NativeMenuAssetsError("staged manifest classes are not the authored classes")
            if tuple(profile.compiled_classes) != pin["compiled_classes"]:
                raise NativeMenuAssetsError("staged manifest classes are not the compiled classes")
            if list(profile.authored_classes) != scene.get("authored_classes"):
                raise NativeMenuAssetsError("staged manifest classes are not the authored classes")
            if list(profile.compiled_classes) != scene.get("classes"):
                raise NativeMenuAssetsError("staged manifest classes are not the compiled classes")
            if scene.get("method_bodies") != pin["method_bodies"] or tuple(scene.get("class_flags") or ()) != pin["class_flags"]:
                raise NativeMenuAssetsError("staged manifest classes are not the authored classes")
        except AttributeError:
            raise NativeMenuAssetsError("staged composer pin does not match") from None
        abc = match_abc[pin["abc_name"]]
        abc_hash = hashlib.sha256(abc).hexdigest()
        if profile.mod_abc_sha256 != abc_hash or scene.get("abc_sha256") != abc_hash or scene.get("abc_bytes") != len(abc):
            raise NativeMenuAssetsError("staged ABC does not match the manifest")
        if scene.get("abc_file") != pin["abc_name"]:
            raise NativeMenuAssetsError("staged ABC does not match the manifest")


def _compose_one(
    reader, rewrite, compose, package, package_bytes, abc, package_sha, movie_sha, export_name,
    session, view_url, decrypt_header, encrypt_header, rewrite_name,
):
    try:
        movie = reader.read_movie_bytes(os.fspath(package), export_name, decrypt_header)
    except NativeMenuAssetsError:
        raise
    except Exception as exc:
        raise NativeMenuAssetsError("installed movie could not be read") from exc
    data = getattr(movie, "data", None)
    if type(data) is not bytes or not data or len(data) > _MAX_MOVIE:
        raise NativeMenuAssetsError("installed movie could not be read")
    movie_hash = hashlib.sha256(data).hexdigest()
    if movie_hash != movie_sha:
        raise NativeMenuAssetsError(f"installed movie is not the supported {export_name} pin")
    try:
        composed = compose(data, abc, session=session, view_url=view_url)
    except Exception as exc:
        raise NativeMenuAssetsError("menu movie could not be prepared") from exc
    if type(composed) is not dict or type(composed.get("data")) is not bytes:
        raise NativeMenuAssetsError("menu movie could not be prepared")
    if not composed["data"] or len(composed["data"]) > _MAX_MOVIE:
        raise NativeMenuAssetsError("menu movie could not be prepared")
    method = getattr(rewrite, rewrite_name, None)
    if not callable(method) or rewrite_name not in ("replace_final_movie", MATCH_REWRITE_SYMBOL):
        raise NativeMenuAssetsError(
            "match package rewrite requires replace_movie from scripts/native_package_rewrite.py"
        )
    try:
        rewritten = method(
            package_bytes,
            composed["data"],
            expected_package_sha256=package_sha,
            expected_movie_sha256=movie_sha,
            export_name=export_name,
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


def _match_receipt(path: Path, private: bytes, source_hash: str, movie_hash: str, relative: str) -> dict:
    return {
        "private_package": str(path),
        "private_package_sha256": hashlib.sha256(private).hexdigest(),
        "source_package_relative": relative,
        "source_package_sha256": source_hash,
        "source_movie_sha256": movie_hash,
    }


def _result(path: Path, private: bytes, source_hash: str, movie_hash: str, session: str, view_url: str, additional: dict):
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
        additional_packages=additional,
    )


def _publish_private(session_dir: Path, files: list[tuple[str, bytes]], result: PreparedNativeMenu) -> None:
    names = [name for name, _payload in files]
    expected = {PRIVATE_PACKAGE_NAME, MIDGAME_PRIVATE_NAME, ENDGAME_PRIVATE_NAME}
    if len(names) != len(expected) or set(names) != expected:
        raise NativeMenuAssetsError("private package could not be written")
    encoded = (json.dumps(result.receipt(), indent=2, sort_keys=True) + "\n").encode("utf-8")
    try:
        os.mkdir(session_dir)
    except FileExistsError:
        raise NativeMenuAssetsError("session directory already exists") from None
    except OSError as exc:
        raise NativeMenuAssetsError("private package could not be written") from exc
    directory_identity = session_dir.lstat()
    written: list[tuple[Path, os.stat_result]] = []
    try:
        for name, payload in [*files, (PREPARE_RECEIPT_NAME, encoded)]:
            final = session_dir / name
            _write_exclusive(session_dir / f".{name}.partial", payload, final)
            written.append((final, final.lstat()))
    except (NativeMenuAssetsError, OSError):
        # Remove only files this call published, and only while their identities
        # and the newly created directory still match. Never remove foreign files.
        try:
            current = session_dir.lstat()
            if not _is_reparse(session_dir) and os.path.samestat(directory_identity, current):
                for final, identity in reversed(written):
                    try:
                        if not _is_reparse(final) and os.path.samestat(identity, final.lstat()):
                            final.unlink()
                    except OSError:
                        pass
                try:
                    session_dir.rmdir()
                except OSError:
                    pass
        except OSError:
            pass
        raise


def _write_exclusive(partial: Path, payload: bytes, final: Path) -> None:
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    published = False
    try:
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
        except NativeMenuAssetsError:
            raise
        except OSError as exc:
            raise NativeMenuAssetsError("private package could not be written") from exc
        finally:
            os.close(descriptor)
        try:
            os.rename(partial, final)
        except OSError as exc:
            raise NativeMenuAssetsError("private package could not be written") from exc
        published = True
    finally:
        if not published:
            try:
                os.remove(partial)
            except OSError:
                pass


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
