"""Synthetic checks for the private RootMenu candidate generator.

These tests build tiny ActionScript and SWF fixtures in memory. They do not
open an installed game, and they do not require FFDec.
"""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import struct
import subprocess
import sys
import zlib

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "native_menu_patch.py"
SPEC = importlib.util.spec_from_file_location("native_menu_patch", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
patch = importlib.util.module_from_spec(SPEC)
sys.modules["native_menu_patch"] = patch
SPEC.loader.exec_module(patch)

PRIVATE_AS = Path(
    r"C:\Users\aporo\Documents\Codex\2026-10-24\nam\work\research"
    r"\private-menu-methods\scripts\menus\RootMenu.as"
)
PRIVATE_PCODE = Path(
    r"C:\Users\aporo\Documents\Codex\2026-10-24\nam\work\research"
    r"\private-menu-pcode\scripts\menus\RootMenu.pcode"
)


def _method_header(name: str, maxstack: int, localcount: int, *, optional: bool = False) -> str:
    flags = "flag OVERRIDE" if name == "generateControls" else "flag FINAL"
    namespace = (
        'ProtectedNamespace("menus:RootMenu")' if name == "generateControls" else patch.PINNED_PRIVATE_NS
    )
    optional_lines = ""
    if optional:
        flags = ""
        namespace = 'ProtectedNamespace("menus:RootMenu")'
        optional_lines = (
            "            flag HAS_OPTIONAL\n"
            '            param QName(PackageNamespace("flash.events"),"Event")\n'
            "            optional Null()\n"
        )
    flag_line = f"         {flags}\n" if flags else ""
    return (
        f"      function {name}() : void\n"
        "      {\n"
        f'         trait method QName({namespace},"{name}")\n'
        f"{flag_line}"
        "         dispid 0\n"
        "         method\n"
        "            name null\n"
        f"{optional_lines}"
        '            returns QName(PackageNamespace(""),"void")\n'
        "            body\n"
        f"               maxstack {maxstack}\n"
        f"               localcount {localcount}\n"
        "               initscopedepth 15\n"
        "               maxscopedepth 16\n"
        "               code\n"
        '                  pushstring "STOCK_MARKER"\n'
        "                  returnvoid\n"
        "               end ; code\n"
        "            end ; body\n"
        "         end ; method\n"
        "      }\n"
    )


def owned_fixture(*, play_body: int | None = None) -> tuple[str, str]:
    labels = " ".join(f'"{item["label"]}"' for item in patch.CONTROLS)
    functions = []
    blocks = [
        "package menus\n{\npublic class RootMenu\n{\n",
        f"// {patch.PINNED_PRIVATE_NS}\n// {patch.PINNED_CREATE_NS}\n",
    ]
    for name, (body, method, stack, locals_) in patch.PINNED_METHODS.items():
        if name == "openPlayMenu" and play_body is not None:
            body = play_body
        functions.append(
            "      function "
            f"{name}() : void\n      {{\n"
            f"         // method body index: {body} method index: {method}\n"
            + (f"         // {labels}\n" if name == "generateControls" else "")
            + "      }\n"
        )
        blocks.append(_method_header(name, stack, locals_, optional=name == "updateClubButton"))
    actionscript = "package menus\n{\npublic class RootMenu\n{\n" + "".join(functions) + "}\n}\n"
    pcode = "".join(blocks) + "}\n}\n"
    return actionscript, pcode


def wrap_plans(plans: dict) -> str:
    parts = ["package menus\n{\npublic class RootMenu\n{\n"]
    for name, plan in plans.items():
        parts.append(f"function {name}() : void\n{{\n{plan['pcode']}}}\n")
    parts.append(
        "function openGarageSelectionMenu() : void\n{\n"
        'trait method QName(PrivateNamespace(null,"67"),"openGarageSelectionMenu")\n'
        'method\nname null\nreturns QName(PackageNamespace(""),"void")\nbody\n'
        "maxstack 4\nlocalcount 1\ninitscopedepth 15\nmaxscopedepth 16\ncode\n"
        'getproperty QName(PackageNamespace(""),"GARAGE_MAIN")\nreturnvoid\n'
        "end ; code\nend ; body\nend ; method\n}\n"
        "function openOptionsMenu() : void\n{\n"
        'trait method QName(PrivateNamespace(null,"67"),"openOptionsMenu")\n'
        'method\nname null\nreturns QName(PackageNamespace(""),"void")\nbody\n'
        "maxstack 2\nlocalcount 1\ninitscopedepth 15\nmaxscopedepth 16\ncode\n"
        'getlex QName(PackageNamespace("tagame.api"),"System")\n'
        'pushstring "Options"\n'
        'callpropvoid QName(PackageNamespace(""),"SetSharedUIState"), 1\n'
        "returnvoid\nend ; code\nend ; body\nend ; method\n}\n"
        "}\n}\n"
    )
    return "".join(parts)


def gfx(doabc: bytes, background: bytes = b"\x11\x22\x33") -> bytes:
    rect = bytes([0x00])
    frame = struct.pack("<HH", 1, 1)
    tags = struct.pack("<H", (9 << 6) | len(background)) + background
    if len(doabc) < 63:
        tags += struct.pack("<H", (patch.DOABC << 6) | len(doabc)) + doabc
    else:
        tags += struct.pack("<HI", (patch.DOABC << 6) | 63, len(doabc)) + doabc
    tags += struct.pack("<H", 0)
    body = rect + frame + tags
    return b"GFX" + bytes([20]) + struct.pack("<I", 8 + len(body)) + body


def test_capabilities_stay_closed():
    flags = patch.capabilities()
    assert flags["runtime_verified"] is False
    assert flags["production"] is False
    assert flags["launches_game"] is False
    assert flags["writes_installed_package"] is False


def test_default_cli_prints_help_without_reading_a_movie(capsys):
    assert patch.main([]) == 0
    help_text = capsys.readouterr().out
    assert "--source" in help_text
    assert "does not read a movie" in help_text


def test_pinned_hash_is_the_owned_movie_digest():
    assert patch.PINNED_SHA256 == "57582fb10fe1e2551989bf15d8aec1df8b62392903974a1e8ea40ac2b1734ec0"
    assert len(patch.PINNED_METHODS) == 13
    assert len({item[0] for item in patch.PINNED_METHODS.values()}) == 13


def test_fixture_identity_resolves_unique_body_ids_and_replaces_only_code():
    actionscript, pcode = owned_fixture()
    plans = patch.plan_replacements(actionscript, pcode)
    assert set(plans) == set(patch.PINNED_METHODS)
    controls = plans["generateControls"]
    assert controls["body_index"] == 11257
    assert controls["stack_peak"] == 9
    assert controls["maxstack"] == 11
    assert controls["localcount"] == 5
    assert controls["initscopedepth"] == 15
    assert controls["maxscopedepth"] == 16
    assert "STOCK_MARKER" not in controls["pcode"]
    assert 'pushstring "My Career"' in controls["pcode"]
    assert "setlocal" not in controls["pcode"]
    shop = plans["tryOpenShopMainMenu"]
    assert shop["maxstack"] == 2
    assert shop["stack_peak"] == 2
    assert 'pushstring "MCT_TRAINING"' in shop["pcode"]
    assert "TryToPlayOnline" not in shop["pcode"]
    assert "flag FINAL" in shop["pcode"]
    profile = plans["openProfileMenu"]
    assert profile["maxstack"] == 4
    assert profile["stack_peak"] == 2
    club = plans["updateClubButton"]
    assert "HAS_OPTIONAL" in club["pcode"]
    assert club["localcount"] == 7
    assert "STOCK_MARKER" not in club["pcode"]


def test_trigger_mapping_is_one_to_one_and_stock_routes_are_absent():
    _actionscript, pcode = owned_fixture()
    plans = patch.plan_replacements(_actionscript, pcode)
    expected = {
        "openPlayMenu": "MCT_CAREER",
        "tryOpenShopMainMenu": "MCT_TRAINING",
        "openProfileMenu": "MCT_WORKSHOP",
        "tryOpenRocketPassScreen": "MCT_COMMUNITY",
    }
    for name, code in expected.items():
        rendered = plans[name]["pcode"]
        assert f'pushstring "{code}"' in rendered
        assert "MenuStack" in rendered
        assert "ButtonTriggered" in rendered
        for other in expected.values():
            if other != code:
                assert other not in rendered
        for banned in ("TryToPlayOnline", "openShopMainMenu", "PLAY_MENU", "PrivilegesManager"):
            assert banned not in rendered
    controls = plans["generateControls"]["pcode"]
    assert "openGarageSelectionMenu" in controls
    assert "openOptionsMenu" in controls
    assert "ExitGame" in controls
    assert "MCT_" not in controls
    for banned in (
        "openPlayNow",
        "openEsportsLink",
        "openShopMainMenu",
        "openRocketPassScreen",
        "handleClubButtonClicked",
        "syncLocalClub",
        "updateEsportEvents",
        "s_stringPlay",
        "MTXGarage",
    ):
        assert banned not in controls
    for name in patch.NO_OP_REASONS:
        text = plans[name]["pcode"]
        assert "pushstring" not in text
        assert "callpropvoid" not in text


def test_wrong_body_id_and_duplicate_ids_fail_before_a_write(tmp_path):
    actionscript, pcode = owned_fixture()
    broken = actionscript.replace(
        "method body index: 11273 method index: 11413",
        "method body index: 11270 method index: 11413",
        1,
    )
    with pytest.raises(patch.CandidateRejected, match="openPlayMenu"):
        patch.plan_replacements(broken, pcode)
    duplicate_as, duplicate_pcode = owned_fixture(play_body=11257)
    with pytest.raises(patch.CandidateRejected, match="not unique"):
        patch.plan_replacements(duplicate_as, duplicate_pcode)
    alien = actionscript.replace("package menus", "package other", 1)
    with pytest.raises(patch.CandidateRejected, match="menus.RootMenu"):
        patch.plan_replacements(alien, pcode)
    output = tmp_path / "candidate.gfx"
    assert not output.exists()


def test_missing_path_is_not_treated_as_a_reparse(tmp_path):
    missing = tmp_path / "no-such-directory" / "candidate.gfx"
    assert patch._is_reparse(missing) is False
    assert patch._is_reparse(tmp_path / "no-such-directory") is False


def test_hash_mismatch_does_not_create_the_candidate(tmp_path):
    source = tmp_path / "movie.gfx"
    source.write_bytes(b"GFX-not-the-owned-movie")
    output = tmp_path / "out" / "candidate.gfx"
    with pytest.raises(patch.CandidateRejected, match="hash"):
        patch.build_candidate(
            source,
            source,
            source,
            output,
            tmp_path / "java.exe",
            tmp_path / "ffdec.jar",
            tmp_path / "ffdec-home",
            tmp_path / "work",
        )
    assert not output.exists()
    assert hashlib.sha256(source.read_bytes()).hexdigest() != patch.PINNED_SHA256


def test_inplace_install_and_junction_outputs_are_rejected(tmp_path):
    source = tmp_path / "source.gfx"
    source.write_bytes(b"GFX")
    with pytest.raises(patch.CandidateRejected, match="in place"):
        patch.reject_paths(source, source, tmp_path / "work")
    install = tmp_path / "game" / "Binaries" / "Win64"
    install.mkdir(parents=True)
    (install.parent.parent / "RocketLeague.exe").write_bytes(b"")
    with pytest.raises(patch.CandidateRejected, match="installed"):
        patch.reject_paths(source, install / "candidate.gfx", tmp_path / "work")
    assert not (install / "candidate.gfx").exists()
    target = tmp_path / "real-dir"
    target.mkdir()
    link = tmp_path / "linked-dir"
    created = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        check=False,
        capture_output=True,
        text=True,
    )
    if created.returncode != 0:
        pytest.skip("this process cannot create a directory junction")
    with pytest.raises(patch.CandidateRejected, match="reparse"):
        patch.reject_paths(source, link / "candidate.gfx", tmp_path / "work")
    assert not (link / "candidate.gfx").exists()


def test_swf_comparison_allows_only_doabc_and_rejects_other_tag_edits():
    original = gfx(b"A" * 70)
    edited = gfx(b"B" * 80)
    allowed = patch.compare_swf_tags(original, edited)
    assert allowed["only_doabc_and_header_length_changed"] is True
    assert allowed["header_length_changed"] is True
    assert allowed["changed_tag_types"] == [patch.DOABC]
    assert allowed["signature"] == "GFX"
    other = patch.compare_swf_tags(original, gfx(b"A" * 70, b"\x11\x22\x44"))
    assert other["only_doabc_and_header_length_changed"] is False
    compressed = b"CFX" + original[3:8] + zlib.compress(original[8:])
    assert patch.compare_swf_tags(original, compressed)["only_doabc_and_header_length_changed"] is False


def test_verifier_accepts_the_rendered_bodies_and_rejects_a_stock_callback():
    actionscript, pcode = owned_fixture()
    plans = patch.plan_replacements(actionscript, pcode)
    exported = wrap_plans(plans)
    report = patch.verify_exported_candidate(actionscript, exported)
    assert report == {
        "seven_labels": True,
        "trigger_callbacks": True,
        "helpers_noop": True,
        "garage_preserved": True,
        "options_preserved": True,
        "body_ids_preserved": True,
    }
    swapped = exported.replace(
        'pushstring "MCT_TRAINING"',
        'pushstring "MCT_CAREER"\ncallpropvoid QName(PackageNamespace(""),"TryToPlayOnline"), 1',
        1,
    )
    with pytest.raises(patch.CandidateRejected, match="stock route|wrong trigger|trigger"):
        patch.verify_exported_candidate(actionscript, swapped)


@pytest.mark.skipif(
    not (PRIVATE_AS.is_file() and PRIVATE_PCODE.is_file()),
    reason="owned RootMenu exports are not on this machine",
)
def test_owned_exports_match_pinned_method_bodies():
    plans = patch.plan_replacements(
        PRIVATE_AS.read_text(encoding="utf-8"),
        PRIVATE_PCODE.read_text(encoding="utf-8"),
    )
    assert plans["generateControls"]["stack_peak"] <= plans["generateControls"]["original_maxstack"]
    assert plans["openPlayMenu"]["pcode"].count("MCT_CAREER") == 1
    assert "TryToPlayOnline" not in plans["tryOpenRocketPassScreen"]["pcode"]
    assert "HAS_OPTIONAL" in plans["updateClubButton"]["pcode"]
    for plan in plans.values():
        assert plan["stack_peak"] <= plan["maxstack"]
        assert (plan["initscopedepth"], plan["maxscopedepth"]) == patch.PINNED_SCOPE
