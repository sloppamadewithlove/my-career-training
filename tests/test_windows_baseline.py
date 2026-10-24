"""Identification baseline: schema, privacy, and read-only fixtures. Not a Windows success."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys

import pytest

spec = importlib.util.spec_from_file_location(
    "windows_baseline", Path(__file__).resolve().parents[1] / "scripts/windows_baseline.py")
baseline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)

PAYLOAD = b"rocket-league-executable"
PACKAGE_BYTES = b"PKGBYTES_SECRET"
LAST_OWNER = "76561198000000000"


@pytest.fixture(autouse=True)
def isolate_live_registry(monkeypatch):
    """Keep pytest from reading a real Windows Steam registry."""
    monkeypatch.setattr(baseline, "_live_registry", lambda: baseline._unavailable_registry())


def write_libraries(path: Path, libraries: list[Path]) -> None:
    lines = ['"libraryfolders"', "{"]
    for index, library in enumerate(libraries):
        lines.extend([
            f'"{index}"', "{", f'"path" "{library}"',
            '"contentid" "sentinel-content-id"', '"AccountName" "secret-user"', "}",
        ])
    lines.append("}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_manifest(path: Path, build_id="25914621", installdir="secret-user", last_owner=LAST_OWNER) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join([
        '"AppState"', "{", '"appid" "252950"', f'"installdir" "{installdir}"',
        f'"buildid" "{build_id}"', f'"LastOwner" "{last_owner}"',
        '"UserConfig"', "{", '"language" "english"', "}", "}", "",
    ]), encoding="utf-8")


def make_game(root: Path, payload=PAYLOAD) -> Path:
    executable = root / "Binaries" / "Win64" / "RocketLeague.exe"
    executable.parent.mkdir(parents=True, exist_ok=True)
    executable.write_bytes(payload)
    cooked = root / "TAGame" / "CookedPCConsole"
    cooked.mkdir(parents=True, exist_ok=True)
    (cooked / "GFX_MainMenu_SF.upk").write_bytes(PACKAGE_BYTES)
    (cooked / "unrelated_secret.upk").write_bytes(b"not-a-menu")
    return executable


def steam_fixture(tmp_path: Path, build_id="25914621", installdir="secret-user"):
    steam = tmp_path / "Steam"
    library = tmp_path / "library-two"
    game = library / "steamapps" / "common" / installdir
    write_libraries(steam / "steamapps" / "libraryfolders.vdf", [steam, library])
    write_manifest(library / "steamapps" / f"appmanifest_{baseline.APP_ID}.acf", build_id, installdir)
    make_game(game)
    return steam, library, game


def fingerprint(root: Path):
    rows = []
    for directory, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames.sort()
        for name in sorted(filenames):
            path = Path(directory) / name
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode):
                rows.append(("link", str(path.relative_to(root)), info.st_mtime_ns))
            elif stat.S_ISREG(info.st_mode):
                rows.append((str(path.relative_to(root)), info.st_mtime_ns,
                             hashlib.sha256(path.read_bytes()).hexdigest()))
    return rows


def assert_private(document, extra=()):
    blob = json.dumps(document)
    for secret in (LAST_OWNER, "LastOwner", "sentinel-content-id", "secret-user",
                   "PKGBYTES_SECRET", "unrelated_secret", "PLUGIN_SECRET", "LINK_TARGET_SECRET",
                   "link-target-secret", *extra):
        assert secret not in blob
    assert '"pid"' not in blob
    assert "cmdline" not in blob
    assert document["limits"]["proves_native_menus"] is False
    assert document["limits"]["proves_gameplay"] is False
    assert document["limits"]["proves_eac"] is False
    assert document["limits"]["proves_steam_preservation"] is False
    assert document["limits"]["entire_install_hashed"] is False
    assert document["containment"]["output_path_recorded"] is False


def test_schema_privacy_and_explicit_unknowns(tmp_path):
    steam, _library, _game = steam_fixture(tmp_path)
    document, _roots = baseline.collect(steam_root=steam)
    blob = json.dumps(document)
    assert_private(document, (str(tmp_path),))
    assert document["format"] == "mct-windows-baseline-v1"
    assert document["platform"] == sys.platform
    assert document["steam"]["app_252950"]["build_id"] == "25914621"
    assert document["steam"]["app_252950"]["build_id_status"] == "read"
    assert document["steam"]["app_252950"]["installdir_status"] == "read"
    assert document["steam"]["registry_source"] == "not_windows" or document["steam"]["registry_source"] == "windows_registry"
    assert document["game"]["root_status"] == "manifest"
    executable = document["game"]["executable"]
    assert executable["status"] == "hashed"
    assert executable["relative"] == baseline.EXE_RELATIVE
    assert executable["size"] == len(PAYLOAD)
    assert executable["sha256"] == hashlib.sha256(PAYLOAD).hexdigest()
    assert document["limits"]["files_hashed"] == [baseline.EXE_RELATIVE]
    found = document["packages"]["found"]
    assert found == [{
        "relative": "TAGame/CookedPCConsole/GFX_MainMenu_SF.upk",
        "size": len(PACKAGE_BYTES),
    }]
    assert "GFX_PlayMenuV4_SF.upk" in document["packages"]["not_observed"]
    assert document["packages"]["observation"] == "filenames_and_sizes_only"
    assert document["bakkesmod"]["loaded_dll_version"] == "unknown"
    assert document["bakkesmod"]["loaded_plugin_version"] == "unknown"
    assert "loaded_bakkes_dll_version" in document["unknowns"]
    assert "loaded_bakkes_plugin_version" in document["unknowns"]
    assert "entire install" in document["limits"]["note"].lower() or "were not hashed" in document["limits"]["note"]
    if sys.platform != "win32":
        assert executable["file_version"] is None
        assert executable["file_version_source"] == "not_windows"
        assert document["rocket_league_process"] == {"running": "unknown", "source": "not_windows"}
        assert "windows_only_checks_not_run" in document["unknowns"]
        assert document["bakkesmod"]["injector"]["file_status"] == "unknown"
    assert "secret-user" not in blob


def test_malformed_vdf_is_partial_and_does_not_leak(tmp_path):
    steam = tmp_path / "Steam"
    game = tmp_path / "game"
    (steam / "steamapps").mkdir(parents=True)
    (steam / "steamapps" / "libraryfolders.vdf").write_text(
        '"libraryfolders" { "0" { "path" "unterminated \n LastOwner secret-user ' + LAST_OWNER,
        encoding="utf-8",
    )
    make_game(game)
    document, _roots = baseline.collect(game_root=game, steam_root=steam)
    assert document["steam"]["libraryfolders"]["malformed"] == 1
    assert document["game"]["executable"]["sha256"] == hashlib.sha256(PAYLOAD).hexdigest()
    assert "libraryfolders_malformed" in document["unknowns"]
    assert_private(document, (str(tmp_path), "unterminated"))


def test_old_libraryfolders_uses_only_absolute_library_paths(tmp_path):
    steam = tmp_path / "Steam"
    library = tmp_path / "library-two"
    game = library / "steamapps" / "common" / "rocketleague"
    (steam / "steamapps").mkdir(parents=True)
    (steam / "steamapps" / "libraryfolders.vdf").write_text(
        "\n".join([
            '"LibraryFolders"', "{",
            '"TimeNextStatsReport" "111"',
            '"ContentStatsID" "sentinel-content-id"',
            f'"1" "{library}"',
            "}", "",
        ]),
        encoding="utf-8",
    )
    write_manifest(library / "steamapps" / "appmanifest_252950.acf", installdir="rocketleague")
    make_game(game)
    document, _roots = baseline.collect(steam_root=steam)
    assert document["steam"]["app_252950"]["build_id"] == "25914621"
    assert document["game"]["executable"]["status"] == "hashed"
    assert_private(document, (str(tmp_path), "library-two", "rocketleague"))


def test_disagreeing_build_ids_are_not_guessed(tmp_path):
    steam = tmp_path / "Steam"
    first = tmp_path / "library-one"
    second = tmp_path / "library-two"
    write_libraries(steam / "steamapps" / "libraryfolders.vdf", [first, second])
    write_manifest(first / "steamapps" / "appmanifest_252950.acf", "11111111", "rocketleague")
    write_manifest(second / "steamapps" / "appmanifest_252950.acf", "22222222", "rocketleague")
    make_game(first / "steamapps" / "common" / "rocketleague")
    make_game(second / "steamapps" / "common" / "rocketleague")
    document, _roots = baseline.collect(steam_root=steam)
    blob = json.dumps(document)
    assert document["steam"]["app_252950"]["build_id"] is None
    assert document["steam"]["app_252950"]["build_id_status"] == "ambiguous"
    assert document["game"]["steam_build_association"] == "unverified"
    assert document["game"]["executable"]["sha256"] is None
    assert document["game"]["executable"]["associated_steam_build_id"] is None
    assert document["limits"]["files_hashed"] == []
    assert "11111111" not in blob and "22222222" not in blob
    assert_private(document, (str(tmp_path),))


def test_explicit_game_root_matching_manifest_gets_associated_build_id(tmp_path):
    steam, _library, game = steam_fixture(tmp_path)
    document, _roots = baseline.collect(game_root=game, steam_root=steam)

    assert document["steam"]["app_252950"]["build_id"] == "25914621"
    assert document["game"]["steam_build_association"] == "matched"
    assert document["game"]["executable"]["associated_steam_build_id"] == "25914621"
    assert_private(document, (str(tmp_path),))


def test_matched_folder_does_not_claim_unusable_manifest_build_id(tmp_path):
    steam, _library, game = steam_fixture(tmp_path, build_id="not-a-build-id")

    document, _roots = baseline.collect(game_root=game, steam_root=steam)

    assert document["game"]["steam_build_association"] == "matched"
    assert document["steam"]["app_252950"]["build_id"] is None
    assert document["steam"]["app_252950"]["build_id_status"] == "partial"
    assert document["game"]["executable"]["associated_steam_build_id"] is None
    assert_private(document, (str(tmp_path),))


def test_explicit_game_root_different_from_manifest_has_no_associated_build_id(tmp_path):
    steam, _library, _installed_game = steam_fixture(tmp_path)
    other_game = tmp_path / "separate-copy"
    different_payload = b"different RocketLeague.exe bytes"
    executable_path = make_game(other_game, different_payload)

    document, _roots = baseline.collect(game_root=other_game, steam_root=steam)

    assert document["steam"]["app_252950"]["build_id"] == "25914621"
    assert document["game"]["root_status"] == "explicit"
    assert document["game"]["steam_build_association"] == "mismatched"
    assert document["game"]["executable"]["sha256"] == hashlib.sha256(different_payload).hexdigest()
    assert document["game"]["executable"]["associated_steam_build_id"] is None
    assert str(executable_path) not in json.dumps(document)
    assert_private(document, (str(tmp_path),))


def test_missing_manifest_game_folder_keeps_build_association_unverified(tmp_path):
    steam = tmp_path / "Steam"
    write_libraries(steam / "steamapps" / "libraryfolders.vdf", [steam])
    write_manifest(steam / "steamapps" / f"appmanifest_{baseline.APP_ID}.acf")

    document, _roots = baseline.collect(steam_root=steam)

    assert document["steam"]["app_252950"]["build_id"] == "25914621"
    assert document["game"]["root_status"] == "absent"
    assert document["game"]["steam_build_association"] == "unverified"
    assert document["game"]["executable"]["associated_steam_build_id"] is None
    assert_private(document, (str(tmp_path),))


def test_no_overwrite_and_output_must_stay_outside_roots(tmp_path, monkeypatch, capsys):
    steam, library, game = steam_fixture(tmp_path)
    calls = {"count": 0}
    real_collect = baseline.collect

    def counting(*args, **kwargs):
        calls["count"] += 1
        return real_collect(*args, **kwargs)

    monkeypatch.setattr(baseline, "collect", counting)
    before_steam = fingerprint(steam)
    before_library = fingerprint(library)
    output = tmp_path / "receipt.json"
    assert baseline.main(["--output", str(output), "--steam-root", str(steam)]) == 0
    message = capsys.readouterr()
    assert "does not prove native menus" in message.out
    assert "secret-user" not in message.out + message.err
    assert "PASS" not in message.out
    original = output.read_bytes()
    assert json.loads(original)["limits"]["entire_install_hashed"] is False
    assert baseline.main(["--output", str(output), "--steam-root", str(steam)]) == 2
    refused = capsys.readouterr()
    assert "output_exists" in refused.err
    assert "secret-user" not in refused.err
    assert output.read_bytes() == original
    assert calls["count"] == 1
    assert fingerprint(steam) == before_steam
    assert fingerprint(library) == before_library

    def fail(*args, **kwargs):
        raise AssertionError("collect must not start")

    monkeypatch.setattr(baseline, "collect", fail)
    assert baseline.main(["--output", str(game / "inside.json"), "--game-root", str(game)]) == 2
    assert not (game / "inside.json").exists()
    assert "output_inside_protected_root" in capsys.readouterr().err
    assert baseline.main(["--output", str(steam / "inside.json"), "--steam-root", str(steam)]) == 2
    assert not (steam / "inside.json").exists()
    missing = tmp_path / "missing-parent" / "out.json"
    assert baseline.main(["--output", str(missing)]) == 2
    assert not missing.parent.exists()
    with pytest.raises(SystemExit) as caught:
        baseline.main([])
    assert caught.value.code == 2


def test_process_unknown_is_not_false_and_drops_pid(monkeypatch):
    if sys.platform != "win32":
        def fail(*args, **kwargs):
            raise AssertionError("tasklist should not run")
        monkeypatch.setattr(baseline.subprocess, "run", fail)
        document, _roots = baseline.collect()
        assert document["rocket_league_process"] == {"running": "unknown", "source": "not_windows"}
    document, _roots = baseline.collect(process_probe=lambda: {
        "running": "unknown", "pid": 4321, "cmdline": "secret-user", "path": "/Users/secret-user",
    })
    assert document["rocket_league_process"] == {"running": "unknown", "source": "injected"}
    blob = json.dumps(document)
    assert "4321" not in blob
    assert "secret-user" not in blob
    assert "cmdline" not in blob


def test_tasklist_parser_does_not_treat_text_as_a_process_list():
    assert baseline._interpret_tasklist(
        0, '"RocketLeague.exe","4321","Console","1","99 K"\r\n') is True
    assert baseline._interpret_tasklist(
        0, "INFO: No tasks are running which match the specified criteria.\r\n") is False
    assert baseline._interpret_tasklist(1, "secret-user account failure") == "unknown"
    assert baseline._interpret_tasklist(0, "RocketLeague.exe mentioned without a csv field") == "unknown"
    assert baseline.TASKLIST_ARGV[0] == "tasklist"
    assert "shell=True" not in Path(baseline.__file__).read_text(encoding="utf-8")


def test_package_listing_skips_links_and_caps_names(tmp_path, monkeypatch):
    game = tmp_path / "game"
    cooked = game / "TAGame" / "CookedPCConsole"
    cooked.mkdir(parents=True)
    (cooked / "GFX_MainMenu_SF.upk").write_bytes(PACKAGE_BYTES)
    outside = tmp_path / "link-target-secret"
    outside.mkdir()
    (outside / "payload").write_bytes(b"LINK_TARGET_SECRET")
    try:
        (cooked / "GFX_PlayMenuV4_SF.upk").symlink_to(outside / "payload")
    except OSError:
        pytest.skip("symlinks are unavailable")
    document, _roots = baseline.collect(game_root=game)
    skipped = document["packages"]["skipped"]
    assert skipped == [{
        "relative": "TAGame/CookedPCConsole/GFX_PlayMenuV4_SF.upk",
        "reason": "symlink",
    }]
    assert document["packages"]["status"] == "partial"
    assert "GFX_PlayMenuV4_SF.upk" not in document["packages"]["not_observed"]
    assert_private(document, (str(tmp_path),))
    monkeypatch.setattr(baseline, "MAX_PACKAGE_ENTRIES", 1)
    (cooked / "GFX_PlayMenuV4_SF.upk").unlink()
    (cooked / "unrelated_secret.upk").write_bytes(b"hidden")
    capped, _roots = baseline.collect(game_root=game)
    assert "package_listing_capped" in capped["unknowns"]
    assert "unrelated_secret" not in json.dumps(capped)


def test_inaccessible_package_directory_is_not_confirmed_absent(tmp_path, monkeypatch):
    game = tmp_path / "game"
    make_game(game)
    real_scandir = os.scandir

    def denied(path):
        if Path(path).name == "CookedPCConsole":
            raise PermissionError("hidden /Users/secret-user")
        return real_scandir(path)

    monkeypatch.setattr(baseline.os, "scandir", denied)
    document, _roots = baseline.collect(game_root=game)
    assert document["packages"]["status"] == "partial"
    assert document["packages"]["not_observed"] == []
    assert "GFX_MainMenu_SF.upk" in document["packages"]["not_confirmed"]
    assert document["packages"]["found"] == []
    assert_private(document, (str(tmp_path), "/Users/secret-user"))


def test_bakkes_file_versions_are_not_loaded_module_versions(tmp_path):
    bakkes = tmp_path / "install" / "bakkesmod" / "bakkesmod"
    (bakkes / "plugins").mkdir(parents=True)
    (bakkes / "plugins" / "secret-plugin.dll").write_bytes(b"PLUGIN_SECRET")
    (bakkes / "version.txt").write_text("2.0.78\n", encoding="utf-8")
    (bakkes / "bakkesmod.dll").write_bytes(b"DLL_SECRET")
    (bakkes.parent / "BakkesMod.exe").write_bytes(b"injector-bytes")

    def reader(path: Path):
        if path.name == "BakkesMod.exe":
            return "2.0.78.0"
        if path.name.lower() == "bakkesmod.dll":
            return "229.0.0.0"
        if path.name == "RocketLeague.exe":
            return "/Users/secret-user/version"
        return None

    def registry():
        return {
            "steam_paths": {"status": "absent", "paths": []},
            "bakkes_path": {"status": "read", "path": str(bakkes)},
        }

    document, _roots = baseline.collect(registry_reader=registry, version_reader=reader)
    injector = document["bakkesmod"]["injector"]
    dll = document["bakkesmod"]["dll_file"]
    assert injector["file_version"] == "2.0.78.0"
    assert injector["file_version_source"] == "injected"
    assert "not a loaded" in injector["meaning"]
    assert dll["file_version"] == "229.0.0.0"
    assert "does not show that the DLL is loaded" in dll["meaning"]
    assert document["bakkesmod"]["version_file"]["version"] == "2.0.78"
    assert document["bakkesmod"]["version_file"]["file"] == "version.txt"
    assert document["bakkesmod"]["loaded_dll_version"] == "unknown"
    assert document["bakkesmod"]["loaded_plugin_version"] == "unknown"
    assert injector["file_version"] != document["bakkesmod"]["loaded_dll_version"]
    assert dll["file_version"] != document["bakkesmod"]["loaded_plugin_version"]
    assert document["bakkesmod"]["directory_source"] == "injected"
    if sys.platform != "win32":
        assert "windows_only_checks_not_run" in document["unknowns"]
    assert_private(document, (str(tmp_path), "DLL_SECRET", "injector-bytes"))

    (bakkes / "version.txt").write_text("C:\\Users\\secret-user\\Bakkes\n", encoding="utf-8")
    hidden, _roots = baseline.collect(registry_reader=registry, version_reader=reader)
    assert hidden["bakkesmod"]["version_file"]["status"] == "malformed"
    assert hidden["bakkesmod"]["version_file"]["version"] is None
    assert_private(hidden, (str(tmp_path), "DLL_SECRET"))


def test_missing_resources_stay_unknown():
    document, _roots = baseline.collect()
    assert document["game"]["root_status"] == "unknown"
    assert document["game"]["executable"]["status"] == "unknown"
    assert document["game"]["executable"]["sha256"] is None
    assert document["limits"]["files_hashed"] == []
    assert document["packages"]["status"] == "unknown"
    assert document["packages"]["not_confirmed"]
    assert document["steam"]["app_252950"]["build_id_status"] == "unknown"
    assert document["bakkesmod"]["loaded_dll_version"] == "unknown"
    if sys.platform != "win32":
        assert document["rocket_league_process"]["running"] == "unknown"
    else:
        assert document["rocket_league_process"]["running"] in (True, False, "unknown")
    assert document["limits"]["proves_steam_preservation"] is False
    if sys.platform != "win32":
        assert document["bakkesmod"]["directory_status"] == "unavailable"
        assert document["bakkesmod"]["injector"]["file_status"] == "unknown"
        assert document["steam"]["registry_source"] == "not_windows"


def test_executable_symlink_and_change_during_hash(tmp_path, monkeypatch):
    game = tmp_path / "game"
    executable = make_game(game)
    outside = tmp_path / "link-target-secret"
    outside.mkdir()
    target = outside / "RocketLeague.exe"
    target.write_bytes(b"LINK_TARGET_SECRET")
    executable.unlink()
    try:
        executable.symlink_to(target)
    except OSError:
        pytest.skip("symlinks are unavailable")
    linked, _roots = baseline.collect(game_root=game)
    assert linked["game"]["executable"]["status"] == "symlink"
    assert linked["game"]["executable"]["sha256"] is None
    assert_private(linked, (str(tmp_path),))

    executable.unlink()
    executable.write_bytes(PAYLOAD)
    verifier = baseline._verifier()
    original = verifier._open_readonly

    def replace(path):
        stream = original(path)
        if Path(path).name == "RocketLeague.exe":
            Path(path).unlink()
            Path(path).write_bytes(b"replaced-during-hash")
        return stream

    monkeypatch.setattr(verifier, "_open_readonly", replace)
    changed, _roots = baseline.collect(game_root=game)
    assert changed["game"]["executable"]["status"] == "unstable"
    assert changed["game"]["executable"]["sha256"] is None
    assert "replaced-during-hash" not in json.dumps(changed)

    def denied(_path, _info):
        raise PermissionError("hidden /Users/secret-user/RocketLeague.exe")

    monkeypatch.setattr(verifier, "_hash_file", denied)
    blocked, _roots = baseline.collect(game_root=game)
    assert blocked["game"]["executable"]["status"] == "inaccessible"
    assert_private(blocked, (str(tmp_path), "/Users/secret-user"))


def test_source_has_no_network_shell_or_writes():
    text = Path(baseline.__file__).read_text(encoding="utf-8")
    for banned in ("shell=True", "os.startfile", "urlopen", "urllib", "requests", "socket",
                   "CreateKey", "SetValue", "DeleteValue", "shutil", "Popen", ".mkdir(", ".unlink(",
                   "write_text", "write_bytes", "os.remove"):
        assert banned not in text
    assert "subprocess.run" in text
    assert "tasklist" in text
    assert '.open("x"' in text
