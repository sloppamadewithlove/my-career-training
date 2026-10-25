"""Stage the private native-menu runtime without an end-user compiler.

Build machines may read two pinned UEViewer files, or pass those files locally.
The staged directory keeps the reader, rewrite, and composer sources, the
compiled menu ABC and manifest, a generated 32-byte decoder configuration, and
the UEViewer MIT license. It does not contain a game executable or a cooked
package. ``runtime_verified`` and ``production_ready`` stay false.

The decoder configuration is build output under ``runtime/native-menu``. Do not
print it or commit it. This script does not launch a game or write an
installed package.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import stat
import sys
import uuid
import urllib.request
from pathlib import Path


class StageNativeRuntimeError(RuntimeError):
    """Staging refused. Existing destination contents were not replaced."""


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
FETCH_TIMEOUT = 20.0
SOURCE_CAP = 64 * 1024
LICENSE_CAP = 8 * 1024

EXECUTABLE_SHA256 = "56b499a85ad927c6b5cc47cb4813f956dd9263405fdf4eddc65b669b53185bc7"
EXECUTABLE_RELATIVE = "Binaries/Win64/RocketLeague.exe"
PACKAGE_SHA256 = "d3e0eeadd2766fa1fb10c2d220c22a84ab2f26fb6bbb89b414a26ef1fd6e2f65"
PACKAGE_RELATIVE = "TAGame/CookedPCConsole/GFX_MainMenu_SF.upk"
MOVIE_SHA256 = "57582fb10fe1e2551989bf15d8aec1df8b62392903974a1e8ea40ac2b1734ec0"
EXPORT_NAME = "MainMenu"
RUNTIME_BUILD = "261013.63066.530866"
BAKKESMOD_CORE = 229

SOURCE_RELATIVE = "native_ui/menus/MctRootMenu.as"
SCREEN_RELATIVE = "native_ui/MctMainMenuScreen.as"
ROOT_MOVIE_RELATIVE = "native_ui/MctRootMenuMovie.as"
ABC_RELATIVE = "native_ui/compiled/MctRootMenu.abc"
MANIFEST_RELATIVE = "native_ui/compiled/manifest.json"
MATCH_MANIFEST_RELATIVE = "native_ui/compiled/match-manifest.json"
MATCH_SCENE_IDS = ("midgame", "endgame")
# Match preparation calls this symbol. native_package_rewrite.py does not
# define it until the package-relocation commit is copied into this worktree.
MATCH_REWRITE_SYMBOL = "replace_movie"
READER_RELATIVE = "scripts/native_package_reader.py"
REWRITE_RELATIVE = "scripts/native_package_rewrite.py"
COMPOSE_RELATIVE = "scripts/native_movie_compose.py"
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

PAYLOAD_NAMES = (
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
)
MATCH_SCENES = {
    "midgame": {
        "surface": "pause",
        "package_id": "midgame",
        "package_relative": "TAGame/CookedPCConsole/GFX_MidGameMenu_SF.upk",
        "package_sha256": "25176a42c7990fce5670f2907020a3641a521553a4aa3c583588717b36e40f50",
        "export_name": "MidgameMenu",
        "movie_sha256": "fa1aea999d6fff856c8c522c3a5844fdfd532fac0a23bf70369a2274e38a35b7",
        "movie_bytes": 940852,
        "original_abc_sha256": "71e96360863604a12bb5b53b32f5014beec0ab9fc614b6e03f27c150abe0bba7",
        "abc_file": "MctPauseMenu.abc",
        "abc_sha256": "32ab576566ea8ba60858d930acbaec91ba0265113275f33da694c21ef12acaeb",
        "abc_bytes": 20353,
        "source": "native_ui/menus/MctPauseMenu.as",
        "source_sha256": "bec463eeee3eb8a0cd7a76a27bcf8301b0f5a205b06803718c72f87d899b526e",
        "screen_source": "native_ui/MctPauseMenuScreen.as",
        "screen_source_sha256": "829791dea145b2251faf7a34956c5ed6b47369d531bb36409f51527f8f608062",
        "root_movie_source": "native_ui/MctPauseMenuMovie.as",
        "root_movie_source_sha256": "e83e7c63db253503c677bd2c149d7acf989a682bb0653e2d0895b235cad28653",
        "menu_class": "MctPauseMenu",
        "screen_class": "MctPauseMenuScreen",
        "wrapper_class": "MctPauseMenuMovie",
        "superclass": "menus::MidGameMenu",
        "original_root_name": "MidGameMenuMovie",
        "renamed_original_root": "MctOriginalMidGameMenuMovie",
        "document_character": 0,
        "document_source_name": "MidGameMenuScreen",
        "document_target_name": "MctPauseMenuScreen",
        "symbol_character": 6,
        "symbol_name": "MidGameMenuMovie",
        "method_bodies": 94,
        "class_flags": [9, 8, 9, 11, 9, 9, 11, 9, 11, 9],
        "authored_classes": [
            "menus::MctPauseMenu",
            "MctPauseMenuMovie",
            "MctPauseMenuScreen",
        ],
    },
    "endgame": {
        "surface": "results",
        "package_id": "endgame",
        "package_relative": "TAGame/CookedPCConsole/GFX_EndGameMenu_SF.upk",
        "package_sha256": "dc4735a75d5ec8ffff423c4db92c3fad1f859191bf384e20ad949e4ed757b3cc",
        "export_name": "EndGameMenu",
        "movie_sha256": "94830737b9ee356d5039ecd8f401f0d0734885c22be70e6139b44008e1733b3c",
        "movie_bytes": 1133247,
        "original_abc_sha256": "47c04e221622bf21ecf98b1905ed786b8682f35886e93a9d3b3fb0d4b698c52d",
        "abc_file": "MctResultsMenu.abc",
        "abc_sha256": "cb2aee50fa3dd0bc786413dff2546d9c1b112dd10745781e12e8224b14832a13",
        "abc_bytes": 20382,
        "source": "native_ui/menus/MctResultsMenu.as",
        "source_sha256": "cf84c374387b45d06dc01e4d884d9103e65744a1cbed61167dc492463e3e44aa",
        "screen_source": "native_ui/MctResultsMenuScreen.as",
        "screen_source_sha256": "56788df6ff86bc2c8f6f7c23a3f73cbc964a36c2cc84435394481e2eff4d13f2",
        "root_movie_source": "native_ui/MctResultsMenuMovie.as",
        "root_movie_source_sha256": "15083968df55fc13d0c468336566d080376c8464a70b1a06a464f086db4e792c",
        "menu_class": "MctResultsMenu",
        "screen_class": "MctResultsMenuScreen",
        "wrapper_class": "MctResultsMenuMovie",
        "superclass": "menus::EndGameMenu",
        "original_root_name": "EndGameMenuMovie",
        "renamed_original_root": "MctOriginalEndGameMenuMovie",
        "document_character": 0,
        "document_source_name": "EndGameMenuScreen",
        "document_target_name": "MctResultsMenuScreen",
        "symbol_character": 23,
        "symbol_name": "EndGameMenuMovie",
        "method_bodies": 100,
        "class_flags": [9, 8, 9, 11, 9, 9, 11, 9, 11, 9],
        "authored_classes": [
            "menus::MctResultsMenu",
            "MctResultsMenuMovie",
            "MctResultsMenuScreen",
        ],
    },
}
RECEIPT_NAME = "receipt.json"
STAGED_NAMES = frozenset(PAYLOAD_NAMES) | {RECEIPT_NAME}
FORBIDDEN_SUFFIXES = (".upk", ".gfx", ".swf", ".swc", ".exe", ".dll")
_CLASS = "class FFileReaderRocketLeague"
_ENDIF = "#endif // ROCKET_LEAGUE"
_KEY = "static const byte key[]"
_REPARSE = 0x400
_MAX_MANIFEST = 64 * 1024
_MAX_ABC = 64 * 1024
_MAX_SOURCE = 1024 * 1024
_MAX_HELPER = 1024 * 1024


def normalize_newlines(data: bytes) -> bytes:
    """Convert CRLF pairs to LF. Lone CR bytes are left unchanged."""
    if type(data) is not bytes:
        raise StageNativeRuntimeError("decoder input must be bytes")
    return data.replace(b"\r\n", b"\n")


def extract_rocket_league_key(source: str) -> bytes:
    """Return the one 32-byte key inside ``FFileReaderRocketLeague``.

    A missing, malformed, or duplicated class or key array is refused. Key
    arrays in other classes are ignored.
    """
    if type(source) is not str or source.count(_CLASS) != 1:
        raise StageNativeRuntimeError("Rocket League decoder class is missing or duplicated")
    start = source.find(_CLASS)
    end = source.find(_ENDIF, start)
    if end < 0:
        raise StageNativeRuntimeError("Rocket League decoder class is not closed")
    body = source[start:end]
    if body.count(_KEY) != 1:
        raise StageNativeRuntimeError("Rocket League decoder key is missing or duplicated")
    key_at = body.find(_KEY)
    bracket = body.find("{", key_at)
    close = body.find("}", bracket + 1)
    if bracket < 0 or close < 0:
        raise StageNativeRuntimeError("Rocket League decoder key is malformed")
    parts = []
    for raw in body[bracket + 1:close].split(","):
        token = raw.strip()
        if not token:
            continue
        if len(token) != 4 or not token.startswith("0x"):
            raise StageNativeRuntimeError("Rocket League decoder key is malformed")
        try:
            value = int(token[2:], 16)
        except ValueError:
            raise StageNativeRuntimeError("Rocket League decoder key is malformed") from None
        if value > 255:
            raise StageNativeRuntimeError("Rocket League decoder key is malformed")
        parts.append(value)
    if len(parts) != 32:
        raise StageNativeRuntimeError("Rocket League decoder key is malformed")
    return bytes(parts)


def decoder_key_from_source(data: bytes) -> bytes:
    """Verify the pinned UEViewer source, then derive its Rocket League key."""
    normalized = normalize_newlines(data)
    digest = hashlib.sha256(normalized).hexdigest()
    if len(normalized) != SOURCE_BYTES or digest != SOURCE_SHA256:
        raise StageNativeRuntimeError("decoder source does not match the UEViewer pin")
    try:
        text = normalized.decode("utf-8")
    except UnicodeDecodeError:
        raise StageNativeRuntimeError("decoder source does not match the UEViewer pin") from None
    return extract_rocket_league_key(text)


def stage_native_runtime(
    destination: str | Path | None = None,
    *,
    repo_root: str | Path | None = None,
    source_path: str | Path | None = None,
    license_path: str | Path | None = None,
    timeout: float = FETCH_TIMEOUT,
) -> dict:
    """Stage ``runtime/native-menu`` or an explicit destination.

    Local ``source_path`` and ``license_path`` must be passed together. When
    both are omitted, only the two pinned UEViewer URLs are fetched.
    """
    if (source_path is None) != (license_path is None):
        raise StageNativeRuntimeError("local decoder source and license must be supplied together")
    if type(timeout) not in (int, float) or not 0 < float(timeout) <= 60:
        raise StageNativeRuntimeError("decoder fetch timeout is not allowed")
    repo = _repo_root(repo_root)
    target = _destination(destination, repo)
    if source_path is None:
        source_bytes = _fetch_exact(SOURCE_URL, SOURCE_CAP, float(timeout))
        license_bytes = _fetch_exact(LICENSE_URL, LICENSE_CAP, float(timeout))
    else:
        source_bytes = _read_capped(Path(source_path), SOURCE_CAP)
        license_bytes = _read_capped(Path(license_path), LICENSE_CAP)
    key = decoder_key_from_source(source_bytes)
    license_text = _accept_license(license_bytes)
    files = _repo_payload(repo)
    files["decoder_config.bin"] = key
    files["UEViewer-LICENSE.txt"] = license_text
    receipt = _receipt(files)
    encoded = _dump(receipt)
    if key.hex().encode("ascii") in encoded.lower():
        raise StageNativeRuntimeError("receipt would have included decoder key material")
    files[RECEIPT_NAME] = encoded
    _reject_game_assets(files)
    _publish(target, files)
    return receipt


def main(argv: list[str] | None = None) -> int:
    """Stage the runtime and print a summary that omits decoder key material."""
    parser = argparse.ArgumentParser(description="Stage the private native menu runtime.")
    parser.add_argument("--destination")
    parser.add_argument("--repo-root")
    parser.add_argument("--source")
    parser.add_argument("--license")
    parser.add_argument("--timeout", type=float, default=FETCH_TIMEOUT)
    args = parser.parse_args(argv)
    try:
        receipt = stage_native_runtime(
            args.destination,
            repo_root=args.repo_root,
            source_path=args.source,
            license_path=args.license,
            timeout=args.timeout,
        )
    except StageNativeRuntimeError as exc:
        print(f"native runtime staging refused: {exc}", file=sys.stderr)
        return 1
    print("staged native menu runtime")
    print("runtime_verified=false")
    print("production_ready=false")
    print(f"files={len(receipt['files'])}")
    return 0


def _repo_root(value: str | Path | None) -> Path:
    path = Path(__file__).resolve().parents[1] if value is None else Path(value)
    if not path.is_dir() or _is_reparse(path):
        raise StageNativeRuntimeError("repo root is not a directory")
    return path.resolve()


def _destination(value: str | Path | None, repo: Path) -> Path:
    if value is None:
        path = repo / "runtime" / "native-menu"
        parent = path.parent
        if not parent.exists():
            if _is_reparse(repo):
                raise StageNativeRuntimeError("staging parent does not exist")
            parent.mkdir()
    else:
        path = Path(value)
        if not path.is_absolute():
            raise StageNativeRuntimeError("staging destination must be absolute")
        parent = path.parent
        if not parent.is_dir() or _is_reparse(parent):
            raise StageNativeRuntimeError("staging parent does not exist")
    if path.exists() and (_is_reparse(path) or not path.is_dir()):
        raise StageNativeRuntimeError("staging destination is not a directory")
    return path


def _fetch_exact(url: str, cap: int, timeout: float) -> bytes:
    if url not in (SOURCE_URL, LICENSE_URL):
        raise StageNativeRuntimeError("decoder URL is not one of the two pinned files")
    request = urllib.request.Request(url, headers={"User-Agent": "my-career-training-stage"})
    opener = urllib.request.build_opener(_RefuseRedirect)
    try:
        with opener.open(request, timeout=timeout) as response:
            if response.geturl() != url:
                raise StageNativeRuntimeError("decoder URL changed")
            return _read_limited(response, cap)
    except StageNativeRuntimeError:
        raise
    except Exception as exc:
        raise StageNativeRuntimeError("decoder download failed") from exc


class _RefuseRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise StageNativeRuntimeError("decoder source redirect was refused")


def _read_limited(response, cap: int) -> bytes:
    chunks = []
    total = 0
    while total <= cap:
        part = response.read(min(16 * 1024, cap - total + 1))
        if not part:
            return b"".join(chunks)
        total += len(part)
        if total > cap:
            raise StageNativeRuntimeError("decoder download exceeded the size cap")
        chunks.append(part)
    raise StageNativeRuntimeError("decoder download exceeded the size cap")


def _read_capped(path: Path, cap: int) -> bytes:
    if _is_reparse(path) or not path.is_file():
        raise StageNativeRuntimeError("decoder input is not a regular file")
    info = path.lstat()
    if info.st_size > cap:
        raise StageNativeRuntimeError("decoder input exceeds the size cap")
    return path.read_bytes()


def _accept_license(data: bytes) -> bytes:
    normalized = normalize_newlines(data)
    digest = hashlib.sha256(normalized).hexdigest()
    if len(normalized) != LICENSE_BYTES or digest != LICENSE_SHA256:
        raise StageNativeRuntimeError("decoder license does not match the UEViewer pin")
    if b"MIT License" not in normalized or b"Konstantin Nosov" not in normalized:
        raise StageNativeRuntimeError("decoder license text is not the MIT license")
    return normalized


def _repo_payload(repo: Path) -> dict[str, bytes]:
    manifest_bytes = _repo_file(repo, MANIFEST_RELATIVE, _MAX_MANIFEST)
    manifest = _manifest(manifest_bytes)
    _require_library_files(repo, manifest)
    abc = _repo_file(repo, ABC_RELATIVE, _MAX_ABC)
    source = _repo_file(repo, SOURCE_RELATIVE, _MAX_SOURCE)
    screen = _repo_file(repo, SCREEN_RELATIVE, _MAX_SOURCE)
    root_movie = _repo_file(repo, ROOT_MOVIE_RELATIVE, _MAX_SOURCE)
    if len(abc) != manifest["abc_bytes"] or _sha(abc) != manifest["abc_sha256"]:
        raise StageNativeRuntimeError("compiled ABC does not match the manifest")
    if _sha(source) != manifest["source_sha256"]:
        raise StageNativeRuntimeError("menu source does not match the manifest")
    if _sha(screen) != manifest["screen_source_sha256"]:
        raise StageNativeRuntimeError("screen source does not match the manifest")
    if _sha(root_movie) != manifest["root_movie_source_sha256"]:
        raise StageNativeRuntimeError("root movie source does not match the manifest")
    reader = _repo_file(repo, READER_RELATIVE, _MAX_HELPER)
    rewrite = _repo_file(repo, REWRITE_RELATIVE, _MAX_HELPER)
    compose = _repo_file(repo, COMPOSE_RELATIVE, _MAX_HELPER)
    match_manifest_bytes = _repo_file(repo, MATCH_MANIFEST_RELATIVE, _MAX_MANIFEST)
    match_manifest = _match_manifest(match_manifest_bytes)
    match_files = _require_match_sources(repo, match_manifest)
    _require_surface(repo)
    _require_composer(repo / COMPOSE_RELATIVE, manifest, match_manifest)
    payload = {
        "native_package_reader.py": reader,
        "native_package_rewrite.py": rewrite,
        "native_movie_compose.py": compose,
        "MctRootMenu.abc": abc,
        "manifest.json": manifest_bytes,
        "match-manifest.json": match_manifest_bytes,
    }
    payload.update(match_files)
    return payload


def _require_library_files(repo: Path, manifest: dict) -> None:
    recorded = manifest["library_files"]
    for relative, digest in LIBRARY_FILES.items():
        blob = _repo_file(repo, relative, _MAX_SOURCE)
        actual = _sha(blob)
        if actual != recorded.get(relative) or actual != digest:
            raise StageNativeRuntimeError("vendored library file does not match the manifest")


def _manifest(data: bytes) -> dict:
    try:
        manifest = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise StageNativeRuntimeError("menu manifest could not be read") from None
    if type(manifest) is not dict:
        raise StageNativeRuntimeError("menu manifest could not be read")
    if (
        manifest.get("source") != SOURCE_RELATIVE
        or manifest.get("screen_source") != SCREEN_RELATIVE
        or manifest.get("root_movie_source") != ROOT_MOVIE_RELATIVE
    ):
        raise StageNativeRuntimeError("menu manifest paths are not the authored sources")
    if manifest.get("authored_classes") != AUTHORED_CLASSES:
        raise StageNativeRuntimeError("menu manifest classes are not the authored classes")
    if manifest.get("library_classes") != LIBRARY_CLASSES:
        raise StageNativeRuntimeError("menu manifest classes are not the library classes")
    if manifest.get("classes") != COMPILED_CLASSES:
        raise StageNativeRuntimeError("menu manifest classes are not the compiled classes")
    if manifest.get("library_commit") != LIBRARY_COMMIT:
        raise StageNativeRuntimeError("menu manifest library commit does not match")
    recorded = manifest.get("library_files")
    if type(recorded) is not dict or set(recorded) != set(LIBRARY_FILES):
        raise StageNativeRuntimeError("menu manifest library files are not the vendored closure")
    for digest in recorded.values():
        if type(digest) is not str or len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise StageNativeRuntimeError("menu manifest library files are not the vendored closure")
    if manifest.get("game_classes_linked") is not False:
        raise StageNativeRuntimeError("menu manifest links game classes")
    if manifest.get("runtime_verified") is not False or manifest.get("production_ready") is not False:
        raise StageNativeRuntimeError("menu manifest grants runtime capability")
    if type(manifest.get("abc_bytes")) is not int or type(manifest.get("abc_sha256")) is not str:
        raise StageNativeRuntimeError("menu manifest ABC pin is malformed")
    if (
        type(manifest.get("source_sha256")) is not str
        or type(manifest.get("screen_source_sha256")) is not str
        or type(manifest.get("root_movie_source_sha256")) is not str
    ):
        raise StageNativeRuntimeError("menu manifest source pin is malformed")
    return manifest


def _require_surface(repo: Path) -> None:
    reader = _import_module(repo / READER_RELATIVE, "mct_stage_reader")
    rewrite = _import_module(repo / REWRITE_RELATIVE, "mct_stage_rewrite")
    for module, names in (
        (reader, ("read_movie_bytes", "decrypt_aes256_ecb_cng")),
        (rewrite, ("replace_final_movie", MATCH_REWRITE_SYMBOL, "encrypt_aes256_ecb_cng")),
    ):
        for name in names:
            if not callable(getattr(module, name, None)):
                raise StageNativeRuntimeError("staged helper is missing a required function")


def _require_composer(path: Path, manifest: dict, match_manifest: dict) -> None:
    module = _import_module(path, "mct_stage_compose")
    try:
        movie = module.MOVIE_SHA256
        abc = module.MOD_ABC_SHA256
        source = module.SOURCE_SHA256
        screen = module.SCREEN_SOURCE_SHA256
        new_class = module.NEW_CLASS
        screen_class = module.SCREEN_CLASS
        root_movie_class = module.ROOT_MOVIE_CLASS
        root_movie_source = module.ROOT_MOVIE_SOURCE_SHA256
        original_root = module.ORIGINAL_ROOT_NAME
        renamed_root = module.RENAMED_ORIGINAL_ROOT
        library_commit = module.LIBRARY_COMMIT
        library_classes = list(module.LIBRARY_CLASSES)
        compiled_classes = list(module.COMPILED_CLASSES)
        library_files = module.LIBRARY_FILES
        character = module.DOCUMENT_CHARACTER
        target = module.DOCUMENT_TARGET_NAME
    except AttributeError:
        raise StageNativeRuntimeError("composer pin does not match the manifest") from None
    if movie != MOVIE_SHA256:
        raise StageNativeRuntimeError("composer movie pin does not match")
    if abc != manifest["abc_sha256"]:
        raise StageNativeRuntimeError("composer ABC pin does not match the manifest")
    if (
        source != manifest["source_sha256"]
        or screen != manifest["screen_source_sha256"]
        or root_movie_source != manifest["root_movie_source_sha256"]
    ):
        raise StageNativeRuntimeError("composer source pin does not match the manifest")
    if new_class != "MctRootMenu" or screen_class != "MctMainMenuScreen" or root_movie_class != "MctRootMenuMovie":
        raise StageNativeRuntimeError("composer authored classes do not match")
    if original_root != "RootMenuMovie" or renamed_root != "MctOriginalRootMenuMovie":
        raise StageNativeRuntimeError("composer root alias does not match")
    if library_commit != LIBRARY_COMMIT or library_classes != LIBRARY_CLASSES or compiled_classes != COMPILED_CLASSES:
        raise StageNativeRuntimeError("composer library pin does not match the manifest")
    if library_files != manifest.get("library_files"):
        raise StageNativeRuntimeError("composer library pin does not match the manifest")
    if character != 0 or target != "MctMainMenuScreen":
        raise StageNativeRuntimeError("composer document binding does not match")
    if not callable(getattr(module, "compose_movie", None)) or not callable(getattr(module, "compose_match_movie", None)):
        raise StageNativeRuntimeError("staged helper is missing a required function")
    _require_match_composer(module, match_manifest)


_MATCH_TOP_KEYS = frozenset({
    "abc_version", "compiler", "game_classes_linked", "library_classes", "library_commit",
    "library_files", "production_ready", "runtime_verified", "scenes", "schema", "swf_version",
})
_MATCH_SCENE_KEYS = frozenset({
    "abc_bytes", "abc_file", "abc_sha256", "authored_classes", "classes", "document_character",
    "document_source_name", "document_target_name", "export_name", "menu_class", "method_bodies",
    "movie_bytes", "movie_sha256", "original_abc_sha256", "original_root_name", "package_id",
    "package_relative", "package_sha256", "renamed_original_root", "root_movie_source",
    "root_movie_source_sha256", "screen_class", "screen_source", "screen_source_sha256",
    "source", "source_sha256", "superclass", "surface", "symbol_character", "symbol_name",
    "wrapper_class", "class_flags",
})
_MATCH_FILE_KEYS = (
    "source_sha256", "screen_source_sha256", "root_movie_source_sha256", "abc_sha256", "abc_bytes",
)


def _match_manifest(data: bytes) -> dict:
    try:
        manifest = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise StageNativeRuntimeError("match manifest could not be read") from None
    if type(manifest) is not dict or set(manifest) != _MATCH_TOP_KEYS or manifest.get("schema") != 1:
        raise StageNativeRuntimeError("match manifest could not be read")
    if manifest.get("compiler") != "Apache Flex 4.16.1" or manifest.get("swf_version") != 20:
        raise StageNativeRuntimeError("match manifest compiler pin does not match")
    if manifest.get("abc_version") != "46.16":
        raise StageNativeRuntimeError("match manifest compiler pin does not match")
    if manifest.get("game_classes_linked") is not False:
        raise StageNativeRuntimeError("match manifest links game classes")
    if manifest.get("runtime_verified") is not False or manifest.get("production_ready") is not False:
        raise StageNativeRuntimeError("match manifest grants runtime capability")
    if manifest.get("library_commit") != LIBRARY_COMMIT or manifest.get("library_classes") != LIBRARY_CLASSES:
        raise StageNativeRuntimeError("match manifest library pin does not match")
    if manifest.get("library_files") != LIBRARY_FILES:
        raise StageNativeRuntimeError("match manifest library pin does not match")
    scenes = manifest.get("scenes")
    if type(scenes) is not dict or set(scenes) != set(MATCH_SCENE_IDS):
        raise StageNativeRuntimeError("match manifest scenes are not midgame and endgame")
    codec = COMPILED_CLASSES[len(AUTHORED_CLASSES):]
    for scene_id in MATCH_SCENE_IDS:
        scene = scenes[scene_id]
        expected = MATCH_SCENES[scene_id]
        if type(scene) is not dict or set(scene) != _MATCH_SCENE_KEYS:
            raise StageNativeRuntimeError("match manifest scene is not the fixed record")
        if scene.get("package_id") != scene_id:
            raise StageNativeRuntimeError("match manifest scene id does not match")
        for key, value in expected.items():
            if key in _MATCH_FILE_KEYS:
                continue
            if scene.get(key) != value:
                raise StageNativeRuntimeError("match manifest scene pin does not match")
        classes = list(expected["authored_classes"]) + list(codec)
        if scene.get("classes") != classes or scene.get("authored_classes") != list(expected["authored_classes"]):
            raise StageNativeRuntimeError("match manifest classes are not the authored inventory")
        for key in ("source_sha256", "screen_source_sha256", "root_movie_source_sha256", "abc_sha256"):
            _require_hex(scene.get(key), "match manifest source pin is malformed")
        if type(scene.get("abc_bytes")) is not int or not 0 < scene["abc_bytes"] <= _MAX_ABC:
            raise StageNativeRuntimeError("match manifest ABC pin is malformed")
    return manifest


def _require_hex(value: object, message: str) -> None:
    if type(value) is not str or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise StageNativeRuntimeError(message)


def _require_match_sources(repo: Path, manifest: dict) -> dict[str, bytes]:
    files = {}
    for scene_id in MATCH_SCENE_IDS:
        scene = manifest["scenes"][scene_id]
        blobs = {
            "source_sha256": _repo_file(repo, scene["source"], _MAX_SOURCE),
            "screen_source_sha256": _repo_file(repo, scene["screen_source"], _MAX_SOURCE),
            "root_movie_source_sha256": _repo_file(repo, scene["root_movie_source"], _MAX_SOURCE),
        }
        for key, blob in blobs.items():
            if _sha(blob) != scene[key]:
                raise StageNativeRuntimeError("match source does not match the manifest")
        abc = _repo_file(repo, f"native_ui/compiled/{scene['abc_file']}", _MAX_ABC)
        if len(abc) != scene["abc_bytes"] or _sha(abc) != scene["abc_sha256"]:
            raise StageNativeRuntimeError("match ABC does not match the manifest")
        if scene["abc_file"] in files:
            raise StageNativeRuntimeError("match manifest ABC file is duplicated")
        files[scene["abc_file"]] = abc
    if set(files) != {"MctPauseMenu.abc", "MctResultsMenu.abc"}:
        raise StageNativeRuntimeError("match ABC files are not the pause and results menus")
    return files


def _require_match_composer(module, manifest: dict) -> None:
    try:
        profiles = module.MATCH_PROFILES
        scene_ids = tuple(module.MATCH_SCENE_IDS)
    except AttributeError:
        raise StageNativeRuntimeError("composer match scenes are missing") from None
    if scene_ids != MATCH_SCENE_IDS or type(profiles) is not dict or set(profiles) != set(MATCH_SCENE_IDS):
        raise StageNativeRuntimeError("composer match scenes are not midgame and endgame")
    for scene_id in MATCH_SCENE_IDS:
        scene = manifest["scenes"][scene_id]
        profile = profiles[scene_id]
        pairs = (
            ("scene_id", "package_id"),
            ("movie_sha256", "movie_sha256"),
            ("movie_bytes", "movie_bytes"),
            ("abc_sha256", "original_abc_sha256"),
            ("mod_abc_sha256", "abc_sha256"),
            ("mod_abc_bytes", "abc_bytes"),
            ("source_sha256", "source_sha256"),
            ("screen_source_sha256", "screen_source_sha256"),
            ("root_movie_source_sha256", "root_movie_source_sha256"),
            ("package_sha256", "package_sha256"),
            ("package_relative", "package_relative"),
            ("export_name", "export_name"),
            ("menu_class", "menu_class"),
            ("screen_class", "screen_class"),
            ("wrapper_class", "wrapper_class"),
            ("original_root_name", "original_root_name"),
            ("renamed_original_root", "renamed_original_root"),
            ("document_source_name", "document_source_name"),
            ("document_target_name", "document_target_name"),
            ("symbol_character", "symbol_character"),
            ("symbol_name", "symbol_name"),
        )
        try:
            for attr, key in pairs:
                if getattr(profile, attr) != scene[key]:
                    raise StageNativeRuntimeError("composer match pin does not match the manifest")
            if list(profile.authored_classes) != scene["authored_classes"]:
                raise StageNativeRuntimeError("composer match classes do not match the manifest")
            if list(profile.compiled_classes) != scene["classes"]:
                raise StageNativeRuntimeError("composer match classes do not match the manifest")
        except AttributeError:
            raise StageNativeRuntimeError("composer match pin does not match the manifest") from None


def _import_module(path: Path, prefix: str):
    name = f"{prefix}_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise StageNativeRuntimeError("staged helper could not be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise StageNativeRuntimeError("staged helper could not be loaded") from exc
    finally:
        sys.modules.pop(name, None)
    return module


def _receipt(files: dict[str, bytes]) -> dict:
    listed = {}
    for name in PAYLOAD_NAMES:
        payload = files[name]
        listed[name] = {"bytes": len(payload), "sha256": _sha(payload)}
    manifest = json.loads(files["manifest.json"].decode("utf-8"))
    return {
        "files": listed,
        "installs_package": False,
        "kind": "native_menu_runtime",
        "launches_game": False,
        "loads_runtime": False,
        "network_at_runtime": False,
        "pins": {
            "abc_bytes": listed["MctRootMenu.abc"]["bytes"],
            "abc_sha256": listed["MctRootMenu.abc"]["sha256"],
            "bakkesmod_core": BAKKESMOD_CORE,
            "classes": list(AUTHORED_CLASSES),
            "executable_relative": EXECUTABLE_RELATIVE,
            "executable_sha256": EXECUTABLE_SHA256,
            "export_name": EXPORT_NAME,
            "movie_sha256": MOVIE_SHA256,
            "package_relative": PACKAGE_RELATIVE,
            "package_sha256": PACKAGE_SHA256,
            "runtime_build": RUNTIME_BUILD,
            "screen_source_sha256": manifest["screen_source_sha256"],
            "source_sha256": manifest["source_sha256"],
        },
        "production_ready": False,
        "provenance": {
            "copyright": "Copyright 2022, Konstantin Nosov",
            "license_bytes": LICENSE_BYTES,
            "license_name": "MIT",
            "license_sha256": LICENSE_SHA256,
            "license_url": LICENSE_URL,
            "source_bytes": SOURCE_BYTES,
            "source_sha256": SOURCE_SHA256,
            "source_url": SOURCE_URL,
            "ueviewer_commit": UEVIEWER_COMMIT,
        },
        "runtime_verified": False,
        "schema": 1,
    }


def _dump(receipt: dict) -> bytes:
    return (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _reject_game_assets(files: dict[str, bytes]) -> None:
    if set(files) != STAGED_NAMES:
        raise StageNativeRuntimeError("staged files are not the native-menu allowlist")
    for name in files:
        lower = name.lower()
        if lower.endswith(FORBIDDEN_SUFFIXES) or "/" in name or "\\" in name:
            raise StageNativeRuntimeError("staged files include a game asset")


def _publish(destination: Path, files: dict[str, bytes]) -> None:
    parent = destination.parent
    staging = parent / f".{destination.name}.staging-{uuid.uuid4().hex}"
    staging.mkdir()
    try:
        _write_files(staging, files)
        _swap(staging, destination)
    except StageNativeRuntimeError:
        _discard_quietly(staging)
        raise
    except OSError as exc:
        _discard_quietly(staging)
        raise StageNativeRuntimeError("staging directory could not be published") from exc


def _swap(staging: Path, destination: Path) -> None:
    if not destination.exists():
        os.rename(staging, destination)
        return
    _require_replaceable(destination)
    replaced = destination.parent / f".{destination.name}.replaced-{uuid.uuid4().hex}"
    os.rename(destination, replaced)
    try:
        os.rename(staging, destination)
    except Exception:
        os.rename(replaced, destination)
        raise
    _remove_staged_directory(replaced)


def _write_files(directory: Path, files: dict[str, bytes]) -> None:
    for name, payload in files.items():
        if name not in STAGED_NAMES:
            raise StageNativeRuntimeError("staged files are not the native-menu allowlist")
        _write_exclusive(directory / name, payload)


def _write_exclusive(path: Path, payload: bytes) -> None:
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise StageNativeRuntimeError("staged file could not be written") from exc
    try:
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise StageNativeRuntimeError("staged file could not be written")
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _require_replaceable(path: Path) -> None:
    if _is_reparse(path) or not path.is_dir():
        raise StageNativeRuntimeError("staging destination is not a directory")
    for child in path.iterdir():
        if child.name not in STAGED_NAMES or child.is_dir() or _is_reparse(child):
            raise StageNativeRuntimeError("staging destination has an unexpected entry")
        if not stat.S_ISREG(child.lstat().st_mode):
            raise StageNativeRuntimeError("staging destination has an unexpected entry")


def _remove_staged_directory(path: Path) -> None:
    for child in path.iterdir():
        if child.name not in STAGED_NAMES or child.is_dir() or _is_reparse(child):
            raise StageNativeRuntimeError("staging directory has an unexpected entry; it was left in place")
        os.remove(child)
    path.rmdir()


def _discard_quietly(path: Path) -> None:
    if ".staging-" not in path.name or not path.exists():
        return
    try:
        _remove_staged_directory(path)
    except StageNativeRuntimeError:
        return


def _repo_file(repo: Path, relative: str, cap: int) -> bytes:
    parts = Path(relative).parts
    if relative.startswith(("/", "\\")) or ".." in parts or any(part in ("", ".") for part in parts):
        raise StageNativeRuntimeError("repo path is not allowed")
    path = repo.joinpath(*parts)
    resolved = path.resolve()
    if repo.resolve() not in resolved.parents:
        raise StageNativeRuntimeError("repo path is not allowed")
    if _is_reparse(resolved) or not resolved.is_file():
        raise StageNativeRuntimeError("repo file is missing")
    info = resolved.lstat()
    if info.st_size > cap:
        raise StageNativeRuntimeError("repo file exceeds the size cap")
    return resolved.read_bytes()


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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
    except OSError:
        raise StageNativeRuntimeError("path could not be checked") from None
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", _REPARSE)
    return bool(getattr(info, "st_file_attributes", 0) & flag)


if __name__ == "__main__":
    sys.exit(main())
