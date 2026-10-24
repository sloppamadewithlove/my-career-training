"""Fixture tests for native menu staging and private package preparation.

These tests do not read an installed game. Decoder key material from a real
UEViewer checkout is compared without placing those bytes in assertion text.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

import pytest

from my_career_training import native_menu_assets as assets


REPO = Path(__file__).resolve().parents[1]
RESEARCH = REPO.parent / "research" / "UEViewer-src"
SESSION = "123e4567-e89b-12d3-a456-426614174000"
MOVIE = b"synthetic-movie"
PACKAGE = b"synthetic-package"
EXE = b"synthetic-exe"
_STAGE_PATH = REPO / "scripts" / "stage_native_runtime.py"
_STAGE_SPEC = importlib.util.spec_from_file_location("mct_stage_native_runtime", _STAGE_PATH)
assert _STAGE_SPEC is not None and _STAGE_SPEC.loader is not None
stage = importlib.util.module_from_spec(_STAGE_SPEC)
_STAGE_SPEC.loader.exec_module(stage)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _assert_key_absent(text: str, key: bytes) -> None:
    if key.hex() in text.lower():
        raise AssertionError("decoder key material was recorded")


def _license_bytes() -> bytes:
    data = (REPO / "packaging/licenses/native-menu/UEViewer-LICENSE.txt").read_bytes().replace(b"\r\n", b"\n")
    if len(data) != assets.LICENSE_BYTES or _sha(data) != assets.LICENSE_SHA256:
        raise AssertionError("UEViewer license pin does not match the checkout")
    return data


def _rocket_source(key: bytes, *, copies: int = 1, keys: int = 1, close: bool = True) -> str:
    tokens = ", ".join(f"0x{byte:02X}" for byte in key)
    arrays = "\n".join(
        f"\tstatic const byte key[] = {{\n\t\t{tokens}\n\t}};" for _ in range(keys)
    )
    body = (
        "#if ROCKET_LEAGUE\n"
        "class FFileReaderRocketLeague : public FReaderWrapper\n"
        "{\n"
        f"{arrays}\n"
        "};\n"
    )
    if close:
        body += "#endif // ROCKET_LEAGUE\n"
    return body * copies


def _pin_decoder(monkeypatch, source: bytes, license_text: bytes) -> None:
    normalized_source = source.replace(b"\r\n", b"\n")
    normalized_license = license_text.replace(b"\r\n", b"\n")
    monkeypatch.setattr(stage, "SOURCE_BYTES", len(normalized_source))
    monkeypatch.setattr(stage, "SOURCE_SHA256", _sha(normalized_source))
    monkeypatch.setattr(stage, "LICENSE_BYTES", len(normalized_license))
    monkeypatch.setattr(stage, "LICENSE_SHA256", _sha(normalized_license))


def _library_lines(module) -> str:
    return (
        f"LIBRARY_COMMIT = {module.LIBRARY_COMMIT!r}\n"
        f"LIBRARY_CLASSES = {list(module.LIBRARY_CLASSES)!r}\n"
        f"COMPILED_CLASSES = {list(module.COMPILED_CLASSES)!r}\n"
        f"LIBRARY_FILES = {module.LIBRARY_FILES!r}\n"
    )


def _copy_vendor(root: Path) -> None:
    for relative in stage.LIBRARY_FILES:
        source = REPO.joinpath(*Path(relative).parts)
        target = root.joinpath(*Path(relative).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())


def _write_repo(root: Path, *, abc_hash: str | None = None) -> dict:
    abc = b"abc-fixture"
    source = b"menu-source"
    screen = b"screen-source"
    wrapper = b"wrapper-source"
    manifest = {
        "abc_bytes": len(abc),
        "abc_sha256": _sha(abc),
        "authored_classes": list(stage.AUTHORED_CLASSES),
        "classes": list(stage.COMPILED_CLASSES),
        "game_classes_linked": False,
        "library_classes": list(stage.LIBRARY_CLASSES),
        "library_commit": stage.LIBRARY_COMMIT,
        "library_files": dict(stage.LIBRARY_FILES),
        "production_ready": False,
        "root_movie_source": "native_ui/MctRootMenuMovie.as",
        "root_movie_source_sha256": _sha(wrapper),
        "runtime_verified": False,
        "screen_source": "native_ui/MctMainMenuScreen.as",
        "screen_source_sha256": _sha(screen),
        "source": "native_ui/menus/MctRootMenu.as",
        "source_sha256": _sha(source),
    }
    (root / "native_ui" / "menus").mkdir(parents=True)
    (root / "native_ui" / "compiled").mkdir(parents=True)
    (root / "scripts").mkdir()
    (root / "native_ui" / "menus" / "MctRootMenu.as").write_bytes(source)
    (root / "native_ui" / "MctMainMenuScreen.as").write_bytes(screen)
    (root / "native_ui" / "MctRootMenuMovie.as").write_bytes(wrapper)
    _copy_vendor(root)
    (root / "native_ui" / "compiled" / "MctRootMenu.abc").write_bytes(abc)
    manifest_path = root / "native_ui" / "compiled" / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    reader = (
        "def read_movie_bytes(*args, **kwargs):\n"
        "    raise RuntimeError('stage must not read a movie')\n"
        "def decrypt_aes256_ecb_cng(*args, **kwargs):\n"
        "    raise RuntimeError('stage must not decrypt')\n"
    )
    rewrite = (
        "def replace_final_movie(*args, **kwargs):\n"
        "    raise RuntimeError('stage must not rewrite')\n"
        "def encrypt_aes256_ecb_cng(*args, **kwargs):\n"
        "    raise RuntimeError('stage must not encrypt')\n"
    )
    compose = (
        f"MOVIE_SHA256 = {stage.MOVIE_SHA256!r}\n"
        f"MOD_ABC_SHA256 = {(abc_hash or manifest['abc_sha256'])!r}\n"
        f"SOURCE_SHA256 = {manifest['source_sha256']!r}\n"
        f"SCREEN_SOURCE_SHA256 = {manifest['screen_source_sha256']!r}\n"
        f"ROOT_MOVIE_SOURCE_SHA256 = {manifest['root_movie_source_sha256']!r}\n"
        "NEW_CLASS = 'MctRootMenu'\n"
        "SCREEN_CLASS = 'MctMainMenuScreen'\n"
        "ROOT_MOVIE_CLASS = 'MctRootMenuMovie'\n"
        "ORIGINAL_ROOT_NAME = 'RootMenuMovie'\n"
        "RENAMED_ORIGINAL_ROOT = 'MctOriginalRootMenuMovie'\n"
        "DOCUMENT_CHARACTER = 0\n"
        "DOCUMENT_TARGET_NAME = 'MctMainMenuScreen'\n"
        f"{_library_lines(stage)}"
        "def compose_movie(*args, **kwargs):\n"
        "    raise RuntimeError('stage must not compose')\n"
    )
    (root / "scripts" / "native_package_reader.py").write_text(reader, encoding="utf-8")
    (root / "scripts" / "native_package_rewrite.py").write_text(rewrite, encoding="utf-8")
    (root / "scripts" / "native_movie_compose.py").write_text(compose, encoding="utf-8")
    return manifest


def _decoder_files(root: Path, key: bytes = bytes(range(32))) -> tuple[Path, Path, bytes]:
    source = _rocket_source(key).encode("ascii")
    license_text = b"MIT License\nCopyright 2022, Konstantin Nosov\nfixture\n"
    source_path = root / "UnPackageReader.cpp"
    license_path = root / "LICENSE.txt"
    source_path.write_bytes(source)
    license_path.write_bytes(license_text)
    return source_path, license_path, key


def _stage_ready(monkeypatch, tmp_path: Path, *, abc_hash: str | None = None):
    repo = tmp_path / "repo"
    repo.mkdir()
    manifest = _write_repo(repo, abc_hash=abc_hash)
    source_path, license_path, key = _decoder_files(tmp_path)
    _pin_decoder(monkeypatch, source_path.read_bytes(), license_path.read_bytes())
    destination = tmp_path / "out" / "native-menu"
    destination.parent.mkdir()
    return repo, source_path, license_path, destination, key, manifest


def _forbid_side_effects(monkeypatch) -> None:
    def boom(*args, **kwargs):
        raise AssertionError("process or network used")

    monkeypatch.setattr(subprocess, "run", boom)
    monkeypatch.setattr(subprocess, "Popen", boom)
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    monkeypatch.setattr(os, "system", boom)


def _reader_source(movie: bytes) -> str:
    return (
        "class MovieBytes:\n"
        "    def __init__(self, data, metadata=None):\n"
        "        self.data = data\n"
        "        self.metadata = metadata or {}\n"
        "def read_movie_bytes(path, exact_export_name, decrypt_header=None):\n"
        "    if exact_export_name != 'MainMenu':\n"
        "        raise RuntimeError('export')\n"
        "    if decrypt_header is not None:\n"
        "        decrypt_header(b'0123456789abcdef')\n"
        f"    return MovieBytes({movie!r})\n"
        "def decrypt_aes256_ecb_cng(data, key):\n"
        "    if len(key) != 32:\n"
        "        raise RuntimeError('key')\n"
        "    return bytes(data)\n"
    )


def _rewrite_source(movie_hash: str) -> str:
    return (
        "import hashlib\n"
        "class Rewritten:\n"
        "    def __init__(self, data):\n"
        "        self.data = data\n"
        "        self.metadata = {'runtime_verified': False, 'production_ready': False}\n"
        "def replace_final_movie(package_bytes, replacement_movie, **kwargs):\n"
        "    if kwargs.get('export_name') != 'MainMenu':\n"
        "        raise RuntimeError('export')\n"
        "    actual = hashlib.sha256(package_bytes).hexdigest()\n"
        "    if kwargs.get('expected_package_sha256') != actual:\n"
        "        raise RuntimeError('package pin')\n"
        f"    if kwargs.get('expected_movie_sha256') != {movie_hash!r}:\n"
        "        raise RuntimeError('movie pin')\n"
        "    if not callable(kwargs.get('decrypt_header')) or not callable(kwargs.get('encrypt_header')):\n"
        "        raise RuntimeError('callbacks')\n"
        "    return Rewritten(b'private-package-bytes')\n"
        "def encrypt_aes256_ecb_cng(data, key):\n"
        "    if len(key) != 32:\n"
        "        raise RuntimeError('key')\n"
        "    return bytes(data)\n"
    )


def _compose_source(
    movie_pin: str,
    abc_hash: str,
    source_hash: str,
    screen_hash: str,
    root_hash: str,
    mutate: Path | None,
) -> str:
    mutation = ""
    if mutate is not None:
        mutation = (
            "    from pathlib import Path\n"
            f"    target = Path({os.fspath(mutate)!r})\n"
            "    target.write_bytes(target.read_bytes() + b'-mutated')\n"
        )
    return (
        f"MOVIE_SHA256 = {movie_pin!r}\n"
        f"MOD_ABC_SHA256 = {abc_hash!r}\n"
        f"SOURCE_SHA256 = {source_hash!r}\n"
        f"SCREEN_SOURCE_SHA256 = {screen_hash!r}\n"
        f"ROOT_MOVIE_SOURCE_SHA256 = {root_hash!r}\n"
        "NEW_CLASS = 'MctRootMenu'\n"
        "SCREEN_CLASS = 'MctMainMenuScreen'\n"
        "ROOT_MOVIE_CLASS = 'MctRootMenuMovie'\n"
        "ORIGINAL_ROOT_NAME = 'RootMenuMovie'\n"
        "RENAMED_ORIGINAL_ROOT = 'MctOriginalRootMenuMovie'\n"
        "DOCUMENT_CHARACTER = 0\n"
        "DOCUMENT_TARGET_NAME = 'MctMainMenuScreen'\n"
        f"{_library_lines(assets)}"
        "def compose_movie(original_gfx, mod_abc, *, session, view_url):\n"
        f"{mutation}"
        "    return {'data': b'composed-movie', 'metadata': {'runtime_verified': False, 'production_ready': False}}\n"
    )


def _write_runtime(directory: Path, movie: bytes, *, mutate: Path | None = None) -> bytes:
    directory.mkdir()
    abc = b"authored-abc"
    source = b"root-source"
    screen = b"screen-source"
    wrapper = b"wrapper-source"
    key = bytes(range(32))
    license_text = _license_bytes()
    manifest = {
        "abc_bytes": len(abc),
        "abc_sha256": _sha(abc),
        "authored_classes": list(assets.AUTHORED_CLASSES),
        "classes": list(assets.COMPILED_CLASSES),
        "game_classes_linked": False,
        "library_classes": list(assets.LIBRARY_CLASSES),
        "library_commit": assets.LIBRARY_COMMIT,
        "library_files": dict(assets.LIBRARY_FILES),
        "production_ready": False,
        "root_movie_source": "native_ui/MctRootMenuMovie.as",
        "root_movie_source_sha256": _sha(wrapper),
        "runtime_verified": False,
        "screen_source": "native_ui/MctMainMenuScreen.as",
        "screen_source_sha256": _sha(screen),
        "source": "native_ui/menus/MctRootMenu.as",
        "source_sha256": _sha(source),
    }
    files = {
        "MctRootMenu.abc": abc,
        "UEViewer-LICENSE.txt": license_text,
        "decoder_config.bin": key,
        "manifest.json": (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        "native_movie_compose.py": _compose_source(
            assets.MOVIE_SHA256, _sha(abc), _sha(source), _sha(screen), _sha(wrapper), mutate
        ).encode("utf-8"),
        "native_package_reader.py": _reader_source(movie).encode("utf-8"),
        "native_package_rewrite.py": _rewrite_source(assets.MOVIE_SHA256).encode("utf-8"),
    }
    receipt = {
        "files": {name: {"bytes": len(payload), "sha256": _sha(payload)} for name, payload in files.items()},
        "installs_package": False,
        "kind": "native_menu_runtime",
        "launches_game": False,
        "loads_runtime": False,
        "network_at_runtime": False,
        "pins": {
            "abc_bytes": len(abc),
            "abc_sha256": _sha(abc),
            "bakkesmod_core": assets.BAKKESMOD_CORE,
            "classes": list(assets.AUTHORED_CLASSES),
            "executable_relative": assets.EXECUTABLE_RELATIVE,
            "executable_sha256": assets.EXECUTABLE_SHA256,
            "export_name": assets.EXPORT_NAME,
            "movie_sha256": assets.MOVIE_SHA256,
            "package_relative": assets.PACKAGE_RELATIVE,
            "package_sha256": assets.PACKAGE_SHA256,
            "runtime_build": assets.RUNTIME_BUILD,
            "screen_source_sha256": _sha(screen),
            "source_sha256": _sha(source),
        },
        "production_ready": False,
        "provenance": {
            "copyright": "Copyright 2022, Konstantin Nosov",
            "license_bytes": assets.LICENSE_BYTES,
            "license_name": "MIT",
            "license_sha256": assets.LICENSE_SHA256,
            "license_url": assets.LICENSE_URL,
            "source_bytes": assets.SOURCE_BYTES,
            "source_sha256": assets.SOURCE_SHA256,
            "source_url": assets.SOURCE_URL,
            "ueviewer_commit": assets.UEVIEWER_COMMIT,
        },
        "runtime_verified": False,
        "schema": 1,
    }
    for name, payload in files.items():
        (directory / name).write_bytes(payload)
    (directory / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return key


def _layout(root: Path, *, exe: bytes = EXE, package: bytes = PACKAGE):
    game = root / "game"
    executable = game / "Binaries" / "Win64" / "RocketLeague.exe"
    cooked = game / "TAGame" / "CookedPCConsole" / "GFX_MainMenu_SF.upk"
    executable.parent.mkdir(parents=True)
    cooked.parent.mkdir(parents=True)
    executable.write_bytes(exe)
    cooked.write_bytes(package)
    bridge = root / "bridge"
    private = root / "private"
    bridge.mkdir()
    private.mkdir()
    return game, bridge, private, executable, cooked


def _prepare(monkeypatch, root: Path, runtime: Path, **kwargs):
    _forbid_side_effects(monkeypatch)
    game, bridge, private, executable, cooked = _layout(root)
    return assets.prepare_native_menu(game, SESSION, bridge, private, runtime), executable, cooked, private, bridge


def test_documented_pins_match():
    assert assets.EXECUTABLE_SHA256 == stage.EXECUTABLE_SHA256
    assert assets.EXECUTABLE_SHA256 == "56b499a85ad927c6b5cc47cb4813f956dd9263405fdf4eddc65b669b53185bc7"
    assert assets.PACKAGE_SHA256 == stage.PACKAGE_SHA256
    assert assets.PACKAGE_SHA256 == "d3e0eeadd2766fa1fb10c2d220c22a84ab2f26fb6bbb89b414a26ef1fd6e2f65"
    assert assets.MOVIE_SHA256 == stage.MOVIE_SHA256
    assert assets.MOVIE_SHA256 == "57582fb10fe1e2551989bf15d8aec1df8b62392903974a1e8ea40ac2b1734ec0"
    assert assets.EXECUTABLE_RELATIVE == "Binaries/Win64/RocketLeague.exe"
    assert assets.PACKAGE_RELATIVE == "TAGame/CookedPCConsole/GFX_MainMenu_SF.upk"
    assert assets.RUNTIME_BUILD == "261013.63066.530866"
    assert assets.BAKKESMOD_CORE == 229
    assert assets.ENVIRONMENT_VARIABLE == "MCT_NATIVE_MOVIE_SESSION"
    assert stage.SOURCE_SHA256 == "72e7700ea05b937b473451e05db873b8eb8dd9e4b41c329d6e9a0d2e7e56132d"
    assert stage.SOURCE_BYTES == 15390
    assert stage.LICENSE_SHA256 == "23831a13a99f726e62388efade7f0b8a778f1b84e40dec8a4bf4a1e481ccbdfe"
    assert stage.LICENSE_BYTES == 1080
    assert stage.SOURCE_URL.endswith("/Unreal/UnrealPackage/UnPackageReader.cpp")
    assert stage.LICENSE_URL.endswith("/LICENSE.txt")
    assert stage.UEVIEWER_COMMIT in stage.SOURCE_URL
    assert assets.AUTHORED_CLASSES == stage.AUTHORED_CLASSES
    assert assets.AUTHORED_CLASSES == ["menus::MctRootMenu", "MctMainMenuScreen", "MctRootMenuMovie"]
    assert assets.LIBRARY_CLASSES == stage.LIBRARY_CLASSES
    assert assets.COMPILED_CLASSES == stage.COMPILED_CLASSES
    assert assets.LIBRARY_COMMIT == stage.LIBRARY_COMMIT == "24c6c16aecbf0d8fcc043ae671e689b0d4b4c559"
    assert assets.LIBRARY_FILES == stage.LIBRARY_FILES
    assert set(assets.COMPILED_CLASSES) == set(assets.AUTHORED_CLASSES) | set(assets.LIBRARY_CLASSES)
    assert len(assets.COMPILED_CLASSES) == 10
    assert assets.default_runtime_directory().name == "native-menu"
    assert assets.default_runtime_directory().parent.name == "runtime"


_CRLF_VENDOR = {
    "native_ui/vendor/as3corelib/src/com/adobe/serialization/json/JSON.as",
    "native_ui/vendor/as3corelib/src/com/adobe/serialization/json/JSONDecoder.as",
    "native_ui/vendor/as3corelib/src/com/adobe/serialization/json/JSONEncoder.as",
    "native_ui/vendor/as3corelib/src/com/adobe/serialization/json/JSONParseError.as",
    "native_ui/vendor/as3corelib/src/com/adobe/serialization/json/JSONToken.as",
}


def test_vendored_json_bytes_survive_git_checkout(tmp_path):
    spec = importlib.util.spec_from_file_location("mct_compose_pins", REPO / "scripts" / "native_movie_compose.py")
    assert spec is not None and spec.loader is not None
    compose = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = compose
    try:
        spec.loader.exec_module(compose)
    finally:
        sys.modules.pop(spec.name, None)
    assert compose.LIBRARY_FILES == stage.LIBRARY_FILES == assets.LIBRARY_FILES
    assert compose.COMPILED_CLASSES == stage.COMPILED_CLASSES
    for relative, digest in stage.LIBRARY_FILES.items():
        raw = (REPO / relative).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == digest
        if relative in _CRLF_VENDOR:
            assert b"\r\n" in raw
        else:
            assert b"\r\n" not in raw
        blob = hashlib.sha1(f"blob {len(raw)}\0".encode("ascii") + raw).hexdigest()
        recorded = subprocess.run(
            ["git", "hash-object", "--path", relative, "--", relative],
            cwd=REPO, check=True, capture_output=True, text=True,
        ).stdout.strip()
        assert recorded == blob
    env = os.environ.copy()
    env["GIT_INDEX_FILE"] = str(tmp_path / "index")
    subprocess.run(["git", "add", "--", "native_ui/vendor/as3corelib"], cwd=REPO, env=env, check=True)
    listed = subprocess.run(
        ["git", "ls-files", "--eol", "--", "native_ui/vendor/as3corelib"],
        cwd=REPO, env=env, check=True, capture_output=True, text=True,
    )
    rows = {}
    for line in listed.stdout.splitlines():
        index_eol, work_eol, _attr, path = line.split(None, 3)
        rows[path.replace("\\", "/")] = (index_eol, work_eol)
    assert set(rows) == set(stage.LIBRARY_FILES)
    for path, (index_eol, work_eol) in rows.items():
        ending = "crlf" if path in _CRLF_VENDOR else "lf"
        assert index_eol == f"i/{ending}"
        assert work_eol == f"w/{ending}"
    notices = (REPO / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    for required in (
        "Copyright (c) 2008, Adobe Systems Incorporated",
        "Redistribution and use in source and binary forms",
        "Neither the name of Adobe Systems Incorporated",
        "THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS",
    ):
        assert required in notices
    for name in ("my-career-training.spec", "my-career-training-native.spec"):
        packaged = (REPO / "packaging" / name).read_text(encoding="utf-8")
        assert 'THIRD_PARTY_NOTICES.md' in packaged


@pytest.mark.parametrize("relative", [
    "native_ui/vendor/as3corelib/src/com/adobe/serialization/json/JSON.as",
    "native_ui/vendor/as3corelib/README",
    "native_ui/vendor/as3corelib/PROVENANCE.json",
])
def test_stage_refuses_a_changed_vendor_file(monkeypatch, tmp_path, relative):
    repo, source_path, license_path, destination, _key, _manifest = _stage_ready(monkeypatch, tmp_path)
    target = repo.joinpath(*Path(relative).parts)
    target.write_bytes(target.read_bytes() + b" ")
    with pytest.raises(stage.StageNativeRuntimeError, match="vendored library"):
        stage.stage_native_runtime(
            destination, repo_root=repo, source_path=source_path, license_path=license_path,
        )


def test_runtime_module_does_not_import_network_or_processes():
    text = (REPO / "src" / "my_career_training" / "native_menu_assets.py").read_text(encoding="utf-8")
    for banned in ("subprocess", "urllib", "socket", "os.system", "Popen"):
        assert banned not in text


def test_key_is_not_derived_before_the_source_pin(monkeypatch):
    def explode(text):
        raise AssertionError("derived")

    monkeypatch.setattr(stage, "extract_rocket_league_key", explode)
    with pytest.raises(stage.StageNativeRuntimeError, match="pin"):
        stage.decoder_key_from_source(b"x" * stage.SOURCE_BYTES)


def test_only_crlf_pairs_are_normalized(monkeypatch):
    key = bytes(range(32))
    lf = _rocket_source(key).encode("ascii")
    monkeypatch.setattr(stage, "SOURCE_BYTES", len(lf))
    monkeypatch.setattr(stage, "SOURCE_SHA256", _sha(lf))
    assert stage.decoder_key_from_source(lf.replace(b"\n", b"\r\n")) == key
    monkeypatch.setattr(stage, "extract_rocket_league_key", lambda text: (_ for _ in ()).throw(AssertionError("derived")))
    with pytest.raises(stage.StageNativeRuntimeError, match="pin"):
        stage.decoder_key_from_source(lf.replace(b"\n", b"\r"))


def test_malformed_and_duplicated_keys_are_refused():
    key = bytes(range(32))
    with pytest.raises(stage.StageNativeRuntimeError, match="malformed"):
        stage.extract_rocket_league_key(_rocket_source(bytes(range(33))))
    with pytest.raises(stage.StageNativeRuntimeError, match="malformed"):
        stage.extract_rocket_league_key(_rocket_source(key).replace("0x00", "0xGG", 1))
    with pytest.raises(stage.StageNativeRuntimeError, match="duplicated"):
        stage.extract_rocket_league_key(_rocket_source(key, copies=2))
    with pytest.raises(stage.StageNativeRuntimeError, match="duplicated"):
        stage.extract_rocket_league_key(_rocket_source(key, keys=2))
    with pytest.raises(stage.StageNativeRuntimeError, match="not closed"):
        stage.extract_rocket_league_key(_rocket_source(key, close=False))
    nurien = "class FFileReaderNurien {\nstatic const byte key[] = { 0x11 };\n};\n"
    assert stage.extract_rocket_league_key(nurien + _rocket_source(key)) == key


def test_fetch_is_limited_to_the_two_pinned_urls(monkeypatch):
    def explode(*args, **kwargs):
        raise AssertionError("opened")

    monkeypatch.setattr(stage.urllib.request, "build_opener", explode)
    with pytest.raises(stage.StageNativeRuntimeError, match="pinned"):
        stage._fetch_exact("https://example.com/UnPackageReader.cpp", 64, 1)
    handler = stage._RefuseRedirect()
    with pytest.raises(stage.StageNativeRuntimeError, match="redirect"):
        handler.redirect_request(None, None, 302, "moved", {}, "https://example.com/")

    seen = {}

    class Response:
        def __init__(self, payload: bytes):
            self.payload = payload

        def geturl(self):
            return stage.SOURCE_URL

        def read(self, count):
            part = self.payload[:count]
            self.payload = self.payload[count:]
            return part

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    class Opener:
        def open(self, request, timeout=None):
            seen["url"] = request.full_url
            seen["timeout"] = timeout
            return Response(b"x" * 1000)

    monkeypatch.setattr(stage.urllib.request, "build_opener", lambda *args, **kwargs: Opener())
    with pytest.raises(stage.StageNativeRuntimeError, match="size cap"):
        stage._fetch_exact(stage.SOURCE_URL, 64, 3.5)
    assert seen == {"url": stage.SOURCE_URL, "timeout": 3.5}


def test_local_decoder_inputs_do_not_fetch(monkeypatch, tmp_path):
    def explode(*args, **kwargs):
        raise AssertionError("fetched")

    monkeypatch.setattr(stage, "_fetch_exact", explode)
    source = tmp_path / "source.cpp"
    license_path = tmp_path / "LICENSE.txt"
    source.write_bytes(b"nope")
    license_path.write_bytes(b"nope")
    destination = tmp_path / "out" / "native-menu"
    destination.parent.mkdir()
    with pytest.raises(stage.StageNativeRuntimeError, match="together"):
        stage.stage_native_runtime(destination, repo_root=tmp_path, source_path=source)
    with pytest.raises(stage.StageNativeRuntimeError, match="pin"):
        stage.stage_native_runtime(
            destination, repo_root=tmp_path, source_path=source, license_path=license_path
        )


def test_composer_mismatch_refuses_without_editing_sources(monkeypatch, tmp_path):
    repo, source_path, license_path, destination, _key, _manifest = _stage_ready(
        monkeypatch, tmp_path, abc_hash="0" * 64
    )
    composer = repo / "scripts" / "native_movie_compose.py"
    before = composer.read_bytes()
    with pytest.raises(stage.StageNativeRuntimeError, match="composer ABC pin"):
        stage.stage_native_runtime(
            destination, repo_root=repo, source_path=source_path, license_path=license_path
        )
    assert composer.read_bytes() == before
    assert not destination.exists()
    assert not list(destination.parent.iterdir())


def test_stage_writes_only_the_allowlist(monkeypatch, tmp_path):
    repo, source_path, license_path, destination, key, _manifest = _stage_ready(monkeypatch, tmp_path)
    receipt = stage.stage_native_runtime(
        destination, repo_root=repo, source_path=source_path, license_path=license_path
    )
    assert receipt["runtime_verified"] is False
    assert receipt["production_ready"] is False
    assert receipt["launches_game"] is False
    assert receipt["network_at_runtime"] is False
    names = {path.name for path in destination.iterdir()}
    assert names == stage.STAGED_NAMES
    for name in names:
        assert not name.lower().endswith((".upk", ".gfx", ".swf", ".swc", ".exe", ".dll"))
    assert (destination / "native_package_reader.py").read_bytes() == (
        repo / "scripts" / "native_package_reader.py"
    ).read_bytes()
    license_text = (destination / "UEViewer-LICENSE.txt").read_bytes()
    assert license_text == license_path.read_bytes()
    assert b"Konstantin Nosov" in license_text
    recorded = (destination / "receipt.json").read_text(encoding="utf-8")
    _assert_key_absent(recorded, key)
    assert (destination / "decoder_config.bin").read_bytes() == key
    assert "decoder_config.bin" not in recorded or "32" in recorded


def test_stage_replaces_an_allowlisted_directory_without_rmtree(monkeypatch, tmp_path):
    def explode(*args, **kwargs):
        raise AssertionError("rmtree")

    monkeypatch.setattr("shutil.rmtree", explode)
    repo, source_path, license_path, destination, _key, _manifest = _stage_ready(monkeypatch, tmp_path)
    stage.stage_native_runtime(destination, repo_root=repo, source_path=source_path, license_path=license_path)
    reader = repo / "scripts" / "native_package_reader.py"
    reader.write_text(reader.read_text(encoding="utf-8") + "\nvalue = 1\n", encoding="utf-8")
    stage.stage_native_runtime(destination, repo_root=repo, source_path=source_path, license_path=license_path)
    assert (destination / "native_package_reader.py").read_bytes() == reader.read_bytes()
    assert {path.name for path in destination.iterdir()} == stage.STAGED_NAMES
    assert [path.name for path in destination.parent.iterdir()] == ["native-menu"]


def test_stage_refuses_unexpected_destination_entries(monkeypatch, tmp_path):
    repo, source_path, license_path, destination, _key, _manifest = _stage_ready(monkeypatch, tmp_path)
    destination.mkdir()
    (destination / "notes.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(stage.StageNativeRuntimeError, match="unexpected"):
        stage.stage_native_runtime(
            destination, repo_root=repo, source_path=source_path, license_path=license_path
        )
    assert (destination / "notes.txt").read_text(encoding="utf-8") == "keep"
    assert [path.name for path in destination.parent.iterdir()] == ["native-menu"]


def test_failed_publish_removes_only_the_staging_directory(monkeypatch, tmp_path):
    repo, source_path, license_path, destination, _key, _manifest = _stage_ready(monkeypatch, tmp_path)

    def boom(source, target):
        raise OSError("rename failed")

    monkeypatch.setattr(stage.os, "rename", boom)
    with pytest.raises(stage.StageNativeRuntimeError, match="published"):
        stage.stage_native_runtime(
            destination, repo_root=repo, source_path=source_path, license_path=license_path
        )
    assert list(destination.parent.iterdir()) == []


def test_real_ueviewer_source_stages_without_recording_the_key(tmp_path):
    source_path = RESEARCH / "Unreal" / "UnrealPackage" / "UnPackageReader.cpp"
    license_path = RESEARCH / "LICENSE.txt"
    if not source_path.is_file() or not license_path.is_file():
        pytest.skip("UEViewer checkout is not present")
    key = stage.decoder_key_from_source(source_path.read_bytes())
    if len(key) != 32:
        raise AssertionError("derived decoder key was not 32 bytes")
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_repo(repo)
    destination = tmp_path / "out" / "native-menu"
    destination.parent.mkdir()
    stage.stage_native_runtime(destination, repo_root=repo, source_path=source_path, license_path=license_path)
    staged = (destination / "decoder_config.bin").read_bytes()
    if staged != key or len(staged) != 32:
        raise AssertionError("staged decoder configuration does not match the derived key")
    _assert_key_absent((destination / "receipt.json").read_text(encoding="utf-8"), key)
    assert (destination / "UEViewer-LICENSE.txt").read_bytes() == license_path.read_bytes().replace(b"\r\n", b"\n")


def test_cli_summary_omits_the_decoder_key(monkeypatch, tmp_path, capsys):
    repo, source_path, license_path, destination, key, _manifest = _stage_ready(monkeypatch, tmp_path)
    code = stage.main([
        "--destination", str(destination),
        "--repo-root", str(repo),
        "--source", str(source_path),
        "--license", str(license_path),
    ])
    captured = capsys.readouterr()
    assert code == 0
    assert "runtime_verified=false" in captured.out
    assert "production_ready=false" in captured.out
    _assert_key_absent(captured.out + captured.err, key)


def test_view_url_matches_the_composer_rules(tmp_path):
    bridge = tmp_path / "bridge dir"
    bridge.mkdir()
    url = assets._native_view_url(assets._real_directory(bridge))
    spec = importlib.util.spec_from_file_location(
        "mct_compose_url_check", REPO / "scripts" / "native_movie_compose.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module._require_view_url(url)
    assert url.startswith("file:///")
    assert url.endswith("/native-view.json")
    assert " " not in url and "%20" in url
    assert not (bridge / "native-view.json").exists()


def test_missing_tampered_and_oversized_runtime_refuses_before_import(monkeypatch, tmp_path):
    def explode(*args, **kwargs):
        raise AssertionError("imported")

    monkeypatch.setattr(assets, "_import_helpers", explode)
    _forbid_side_effects(monkeypatch)
    game, bridge, private, _executable, _cooked = _layout(tmp_path)

    missing = tmp_path / "missing-runtime"
    _write_runtime(missing, MOVIE)
    (missing / "native_package_reader.py").unlink()
    with pytest.raises(assets.NativeMenuAssetsError, match="missing"):
        assets.prepare_native_menu(game, SESSION, bridge, private, missing)

    tampered = tmp_path / "tampered-runtime"
    _write_runtime(tampered, MOVIE)
    reader = tampered / "native_package_reader.py"
    reader.write_bytes(reader.read_bytes() + b"\n")
    with pytest.raises(assets.NativeMenuAssetsError, match="does not match"):
        assets.prepare_native_menu(game, SESSION, bridge, private, tampered)

    oversized = tmp_path / "oversized-runtime"
    _write_runtime(oversized, MOVIE)
    blob = b"x" * (assets._CAPS["native_package_reader.py"] + 1)
    (oversized / "native_package_reader.py").write_bytes(blob)
    receipt_path = oversized / "receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["files"]["native_package_reader.py"] = {"bytes": len(blob), "sha256": _sha(blob)}
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(assets.NativeMenuAssetsError, match="exceeds"):
        assets.prepare_native_menu(game, SESSION, bridge, private, oversized)

    granted = tmp_path / "granted-runtime"
    _write_runtime(granted, MOVIE)
    granted_receipt = json.loads((granted / "receipt.json").read_text(encoding="utf-8"))
    granted_receipt["runtime_verified"] = True
    (granted / "receipt.json").write_text(json.dumps(granted_receipt) + "\n", encoding="utf-8")
    with pytest.raises(assets.NativeMenuAssetsError, match="capability"):
        assets.prepare_native_menu(game, SESSION, bridge, private, granted)
    assert list(private.iterdir()) == []


def test_wrong_build_package_nonce_and_overlap_do_not_write(monkeypatch, tmp_path):
    _forbid_side_effects(monkeypatch)
    runtime = tmp_path / "runtime"
    _write_runtime(runtime, MOVIE)
    game, bridge, private, executable, cooked = _layout(tmp_path / "trees")
    original_package = cooked.read_bytes()
    with pytest.raises(assets.NativeMenuAssetsError, match="runtime build"):
        assets.prepare_native_menu(game, SESSION, bridge, private, runtime)
    assert cooked.read_bytes() == original_package
    assert list(private.iterdir()) == []

    monkeypatch.setattr(assets, "EXECUTABLE_SHA256", _sha(EXE))
    package_runtime = tmp_path / "package-runtime"
    _write_runtime(package_runtime, MOVIE)
    cooked.write_bytes(b"other-package")
    with pytest.raises(assets.NativeMenuAssetsError, match="GFX_MainMenu_SF"):
        assets.prepare_native_menu(game, SESSION, bridge, private, package_runtime)
    assert executable.read_bytes() == EXE
    assert list(private.iterdir()) == []

    with pytest.raises(assets.NativeMenuAssetsError, match="UUID"):
        assets.prepare_native_menu(game, "123E4567-E89B-12D3-A456-426614174000", bridge, private, runtime)
    with pytest.raises(assets.NativeMenuAssetsError, match="absolute drive path"):
        assets.prepare_native_menu("relative-game", SESSION, bridge, private, runtime)
    with pytest.raises(assets.NativeMenuAssetsError, match="UNC"):
        assets.prepare_native_menu(game, SESSION, "\\\\server\\share\\bridge", private, runtime)
    with pytest.raises(assets.NativeMenuAssetsError, match="device"):
        assets.prepare_native_menu(game, SESSION, bridge, r"C:\CON", runtime)

    nested = game / "private"
    nested.mkdir()
    (game / "sentinel.txt").write_text("stay", encoding="utf-8")
    with pytest.raises(assets.NativeMenuAssetsError, match="overlaps"):
        assets.prepare_native_menu(game, SESSION, bridge, nested, runtime)
    assert (game / "sentinel.txt").read_text(encoding="utf-8") == "stay"
    assert list(private.iterdir()) == []


def test_successful_preparation_writes_only_the_private_package(monkeypatch, tmp_path):
    monkeypatch.setattr(assets, "MOVIE_SHA256", _sha(MOVIE))
    monkeypatch.setattr(assets, "PACKAGE_SHA256", _sha(PACKAGE))
    monkeypatch.setattr(assets, "EXECUTABLE_SHA256", _sha(EXE))
    runtime = tmp_path / "runtime"
    key = _write_runtime(runtime, MOVIE)
    result, executable, cooked, private, bridge = _prepare(monkeypatch, tmp_path / "trees", runtime)
    # A second session must accept the same immutable runtime. Source-loader
    # bytecode caches used to add an unexpected directory after the first use.
    before_runtime = {path.name: path.read_bytes() for path in runtime.iterdir()}
    again = assets.prepare_native_menu(executable.parent.parent.parent,
        "123e4567-e89b-42d3-a456-426614174001", bridge, private, runtime)
    assert again.private_package != result.private_package
    assert {path.name: path.read_bytes() for path in runtime.iterdir()} == before_runtime
    session_dir = private / SESSION
    assert result.private_package == str(session_dir / "GFX_MainMenu_SF.upk")
    assert result.private_package_sha256 == _sha(b"private-package-bytes")
    assert result.source_package_sha256 == _sha(PACKAGE)
    assert result.source_movie_sha256 == _sha(MOVIE)
    assert result.session == SESSION
    assert result.environment_variable == "MCT_NATIVE_MOVIE_SESSION"
    assert result.environment_value == SESSION
    assert result.environment() == {"MCT_NATIVE_MOVIE_SESSION": SESSION}
    assert result.view_url.startswith("file:///") and result.view_url.endswith("/native-view.json")
    assert result.runtime_build == "261013.63066.530866"
    assert result.supported_bakkesmod_core == 229
    assert result.bakkesmod_queried is False
    assert result.runtime_verified is False
    assert result.production_ready is False
    assert result.installed is False
    assert result.launched is False
    assert sorted(path.name for path in session_dir.iterdir()) == ["GFX_MainMenu_SF.upk", "prepare-receipt.json"]
    assert (session_dir / "GFX_MainMenu_SF.upk").read_bytes() == b"private-package-bytes"
    receipt_text = (session_dir / "prepare-receipt.json").read_text(encoding="utf-8")
    receipt = json.loads(receipt_text)
    assert receipt["runtime_verified"] is False
    assert receipt["installed"] is False
    assert receipt["launched"] is False
    assert receipt["environment"]["MCT_NATIVE_MOVIE_SESSION"] == SESSION
    _assert_key_absent(receipt_text, key)
    assert executable.read_bytes() == EXE
    assert cooked.read_bytes() == PACKAGE
    assert not (bridge / "native-view.json").exists()
    assert assets.ENVIRONMENT_VARIABLE not in os.environ
    assert game_parent_unchanged(tmp_path / "trees" / "game")


def game_parent_unchanged(game: Path) -> bool:
    names = {path.name for path in game.iterdir()}
    return names == {"Binaries", "TAGame"}


def test_preexisting_session_files_are_retained(monkeypatch, tmp_path):
    monkeypatch.setattr(assets, "MOVIE_SHA256", _sha(MOVIE))
    monkeypatch.setattr(assets, "PACKAGE_SHA256", _sha(PACKAGE))
    monkeypatch.setattr(assets, "EXECUTABLE_SHA256", _sha(EXE))
    runtime = tmp_path / "runtime"
    _write_runtime(runtime, MOVIE)
    game, bridge, private, _executable, _cooked = _layout(tmp_path / "trees")
    session_dir = private / SESSION
    session_dir.mkdir()
    (session_dir / "keep.txt").write_text("stay", encoding="utf-8")
    _forbid_side_effects(monkeypatch)
    with pytest.raises(assets.NativeMenuAssetsError, match="already exists"):
        assets.prepare_native_menu(game, SESSION, bridge, private, runtime)
    assert (session_dir / "keep.txt").read_text(encoding="utf-8") == "stay"
    assert not (session_dir / "GFX_MainMenu_SF.upk").exists()


def test_source_mutation_during_preparation_refuses(monkeypatch, tmp_path):
    monkeypatch.setattr(assets, "MOVIE_SHA256", _sha(MOVIE))
    monkeypatch.setattr(assets, "PACKAGE_SHA256", _sha(PACKAGE))
    monkeypatch.setattr(assets, "EXECUTABLE_SHA256", _sha(EXE))
    game, _bridge, private, executable, cooked = _layout(tmp_path / "trees")
    runtime = tmp_path / "runtime"
    _write_runtime(runtime, MOVIE, mutate=cooked)
    _forbid_side_effects(monkeypatch)
    with pytest.raises(assets.NativeMenuAssetsError, match="changed during preparation"):
        assets.prepare_native_menu(game, SESSION, tmp_path / "trees" / "bridge", private, runtime)
    assert not (private / SESSION).exists()
    assert executable.read_bytes() == EXE
    assert cooked.read_bytes() == PACKAGE + b"-mutated"


def test_mutation_after_private_write_is_not_cleaned_up(monkeypatch, tmp_path):
    monkeypatch.setattr(assets, "MOVIE_SHA256", _sha(MOVIE))
    monkeypatch.setattr(assets, "PACKAGE_SHA256", _sha(PACKAGE))
    monkeypatch.setattr(assets, "EXECUTABLE_SHA256", _sha(EXE))
    runtime = tmp_path / "runtime"
    _write_runtime(runtime, MOVIE)
    game, bridge, private, _executable, cooked = _layout(tmp_path / "trees")
    package_key = os.path.normcase(str(cooked.resolve()))
    real_hash = assets._hash_file
    seen = {"n": 0}

    def fake(path, limit):
        digest = real_hash(path, limit)
        if os.path.normcase(str(path)) == package_key:
            seen["n"] += 1
            if seen["n"] >= 3:
                return "f" * 64
        return digest

    monkeypatch.setattr(assets, "_hash_file", fake)
    _forbid_side_effects(monkeypatch)
    with pytest.raises(assets.NativeMenuAssetsError, match="changed during preparation"):
        assets.prepare_native_menu(game, SESSION, bridge, private, runtime)
    assert seen["n"] >= 3
    session_dir = private / SESSION
    assert (session_dir / "GFX_MainMenu_SF.upk").read_bytes() == b"private-package-bytes"
    assert cooked.read_bytes() == PACKAGE
