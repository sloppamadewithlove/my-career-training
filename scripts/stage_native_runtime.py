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
ABC_RELATIVE = "native_ui/compiled/MctRootMenu.abc"
MANIFEST_RELATIVE = "native_ui/compiled/manifest.json"
READER_RELATIVE = "scripts/native_package_reader.py"
REWRITE_RELATIVE = "scripts/native_package_rewrite.py"
COMPOSE_RELATIVE = "scripts/native_movie_compose.py"
AUTHORED_CLASSES = ["menus::MctRootMenu", "MctMainMenuScreen"]

PAYLOAD_NAMES = (
    "native_package_reader.py",
    "native_package_rewrite.py",
    "native_movie_compose.py",
    "MctRootMenu.abc",
    "manifest.json",
    "decoder_config.bin",
    "UEViewer-LICENSE.txt",
)
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
    abc = _repo_file(repo, ABC_RELATIVE, _MAX_ABC)
    source = _repo_file(repo, SOURCE_RELATIVE, _MAX_SOURCE)
    screen = _repo_file(repo, SCREEN_RELATIVE, _MAX_SOURCE)
    if len(abc) != manifest["abc_bytes"] or _sha(abc) != manifest["abc_sha256"]:
        raise StageNativeRuntimeError("compiled ABC does not match the manifest")
    if _sha(source) != manifest["source_sha256"]:
        raise StageNativeRuntimeError("menu source does not match the manifest")
    if _sha(screen) != manifest["screen_source_sha256"]:
        raise StageNativeRuntimeError("screen source does not match the manifest")
    reader = _repo_file(repo, READER_RELATIVE, _MAX_HELPER)
    rewrite = _repo_file(repo, REWRITE_RELATIVE, _MAX_HELPER)
    compose = _repo_file(repo, COMPOSE_RELATIVE, _MAX_HELPER)
    _require_surface(repo)
    _require_composer(repo / COMPOSE_RELATIVE, manifest)
    return {
        "native_package_reader.py": reader,
        "native_package_rewrite.py": rewrite,
        "native_movie_compose.py": compose,
        "MctRootMenu.abc": abc,
        "manifest.json": manifest_bytes,
    }


def _manifest(data: bytes) -> dict:
    try:
        manifest = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise StageNativeRuntimeError("menu manifest could not be read") from None
    if type(manifest) is not dict:
        raise StageNativeRuntimeError("menu manifest could not be read")
    if manifest.get("source") != SOURCE_RELATIVE or manifest.get("screen_source") != SCREEN_RELATIVE:
        raise StageNativeRuntimeError("menu manifest paths are not the authored sources")
    if manifest.get("classes") != AUTHORED_CLASSES:
        raise StageNativeRuntimeError("menu manifest classes are not the two authored classes")
    if manifest.get("game_classes_linked") is not False:
        raise StageNativeRuntimeError("menu manifest links game classes")
    if manifest.get("runtime_verified") is not False or manifest.get("production_ready") is not False:
        raise StageNativeRuntimeError("menu manifest grants runtime capability")
    if type(manifest.get("abc_bytes")) is not int or type(manifest.get("abc_sha256")) is not str:
        raise StageNativeRuntimeError("menu manifest ABC pin is malformed")
    if type(manifest.get("source_sha256")) is not str or type(manifest.get("screen_source_sha256")) is not str:
        raise StageNativeRuntimeError("menu manifest source pin is malformed")
    return manifest


def _require_surface(repo: Path) -> None:
    reader = _import_module(repo / READER_RELATIVE, "mct_stage_reader")
    rewrite = _import_module(repo / REWRITE_RELATIVE, "mct_stage_rewrite")
    for module, names in (
        (reader, ("read_movie_bytes", "decrypt_aes256_ecb_cng")),
        (rewrite, ("replace_final_movie", "encrypt_aes256_ecb_cng")),
    ):
        for name in names:
            if not callable(getattr(module, name, None)):
                raise StageNativeRuntimeError("staged helper is missing a required function")


def _require_composer(path: Path, manifest: dict) -> None:
    module = _import_module(path, "mct_stage_compose")
    try:
        movie = module.MOVIE_SHA256
        abc = module.MOD_ABC_SHA256
        source = module.SOURCE_SHA256
        screen = module.SCREEN_SOURCE_SHA256
        new_class = module.NEW_CLASS
        screen_class = module.SCREEN_CLASS
        character = module.DOCUMENT_CHARACTER
        target = module.DOCUMENT_TARGET_NAME
    except AttributeError:
        raise StageNativeRuntimeError("composer pin does not match the manifest") from None
    if movie != MOVIE_SHA256:
        raise StageNativeRuntimeError("composer movie pin does not match")
    if abc != manifest["abc_sha256"]:
        raise StageNativeRuntimeError("composer ABC pin does not match the manifest")
    if source != manifest["source_sha256"] or screen != manifest["screen_source_sha256"]:
        raise StageNativeRuntimeError("composer source pin does not match the manifest")
    if new_class != "MctRootMenu" or screen_class != "MctMainMenuScreen":
        raise StageNativeRuntimeError("composer authored classes do not match")
    if character != 0 or target != "MctMainMenuScreen":
        raise StageNativeRuntimeError("composer document binding does not match")
    if not callable(getattr(module, "compose_movie", None)):
        raise StageNativeRuntimeError("staged helper is missing a required function")


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
