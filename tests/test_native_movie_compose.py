"""Synthetic checks for pinned MainMenu composition.

The fixtures are tiny GFX and ABC buffers. They do not include the owned movie.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import struct
import sys
from dataclasses import replace
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "native_movie_compose.py"
SPEC = importlib.util.spec_from_file_location("native_movie_compose", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
compose = importlib.util.module_from_spec(SPEC)
sys.modules["native_movie_compose"] = compose
SPEC.loader.exec_module(compose)

SESSION = "550e8400-e29b-41d4-a716-446655440000"
VIEW_URL = "file:///C:/sessions/native-view.json"
UNICODE_URL = "file:///C:/My%20Career/%E2%82%ACview/native-view.json"
OLD_MULTINAME = 5940
SUPER_BYTES = bytes((0xB4, 0x2E))
SCRIPT_CODE = b"SCRIPT700" + b"\x60" + SUPER_BYTES + b"\x30\x60" + SUPER_BYTES + b"\x58\x07"
ORIGINAL_NAMES = ["menus", "RootMenu", "RootMenuMovie", "MainMenuScreen", "Garage"]
MOD_NAMES = [
    "MctRootMenu",
    "__MCT_VIEW_URL__",
    "__MCT_SESSION__",
    "__MCT_",
    "N" * 130,
    "MctMainMenuScreen",
    "MctRootMenuMovie",
]
WRAPPER_INDEX = 7


def _u30(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def _pool(names: list[str]) -> bytearray:
    out = bytearray(struct.pack("<HH", 16, 46))
    out += bytes((0, 0, 0))
    out += _u30(len(names) + 1)
    for item in names:
        raw = item.encode("utf-8")
        out += _u30(len(raw))
        out += raw
    return out


def _original_abc(
    names: list[str] | None = None,
    *,
    code: bytes = SCRIPT_CODE,
    super_bytes: bytes = SUPER_BYTES,
    tail: bytes = b"",
) -> tuple[bytes, int, int]:
    out = _pool(ORIGINAL_NAMES if names is None else names)
    super_offset = len(out)
    out += super_bytes
    out += b"GAP"
    code_offset = len(out)
    out += code
    out += b"TAIL"
    out += tail
    return bytes(out), super_offset, code_offset


def _mod(strings: list[str] | None = None) -> bytes:
    names = MOD_NAMES if strings is None else strings
    out = _pool(names)
    if "MctRootMenuMovie" in names:
        out += b"QNAME" + _u30(names.index("MctRootMenuMovie") + 1)
    out += b"TAIL__MCT_VIEW_URL____MCT_SESSION__"
    return bytes(out)


def _tag(code: int, payload: bytes) -> bytes:
    if len(payload) < 63:
        return struct.pack("<H", (code << 6) | len(payload)) + payload
    return struct.pack("<HI", (code << 6) | 63, len(payload)) + payload


def _movie(
    abc: bytes,
    *,
    symbol: str = "RootMenuMovie",
    between: bool = False,
    extra_doabc: bool = False,
    symbols: list[tuple[int, str]] | None = None,
) -> bytes:
    if symbols is None:
        symbols = [(0, "MainMenuScreen"), (83, symbol), (1, "Other"), (9, "Garage")]
    symbol_payload = struct.pack("<H", len(symbols))
    for character, name in symbols:
        symbol_payload += struct.pack("<H", character) + name.encode("ascii") + b"\0"
    tags = [
        _tag(21, b"RAW-NON-ABC-01"),
        _tag(82, struct.pack("<I", 1) + b"\0" + abc),
    ]
    if between:
        tags.append(_tag(21, b"BETWEEN"))
    tags.append(_tag(76, symbol_payload))
    tags.append(_tag(1, b""))
    if extra_doabc:
        tags.append(_tag(82, struct.pack("<I", 1) + b"\0" + b"second"))
    tags.append(_tag(0, b""))
    body = b"".join(tags)
    header = b"GFX" + bytes((20,)) + b"\0\0\0\0" + bytes((0,)) + struct.pack("<HH", 0x0100, 1)
    movie = header + body
    return movie[:4] + struct.pack("<I", len(movie)) + movie[8:]


def _profile(
    movie: bytes,
    abc: bytes,
    mod: bytes,
    code: bytes,
    super_offset: int,
    code_offset: int,
    **overrides: object,
) -> compose.ComposeProfile:
    values = {
        "movie_sha256": hashlib.sha256(movie).hexdigest(),
        "abc_sha256": hashlib.sha256(abc).hexdigest(),
        "mod_abc_sha256": hashlib.sha256(mod).hexdigest(),
        "source_sha256": "ab" * 32,
        "screen_source_sha256": "cd" * 32,
        "root_movie_source_sha256": "ef" * 32,
        "super_offset": super_offset,
        "super_bytes": SUPER_BYTES,
        "old_multiname_index": OLD_MULTINAME,
        "class_index": 702,
        "code_offset": code_offset,
        "code_length": len(code),
        "code_sha256": hashlib.sha256(code).hexdigest(),
        "method_index": 11548,
        "script_index": 700,
        "doabc_index": 1,
        "symbol_character": 83,
        "symbol_name": "RootMenuMovie",
    }
    values.update(overrides)
    return compose.ComposeProfile(**values)


def _ready(
    names: list[str] | None = None,
    mod_strings: list[str] | None = None,
    *,
    code: bytes = SCRIPT_CODE,
    super_bytes: bytes = SUPER_BYTES,
    tail: bytes = b"",
    **overrides: object,
):
    abc, super_offset, code_offset = _original_abc(names, code=code, super_bytes=super_bytes, tail=tail)
    mod = _mod(mod_strings)
    movie = _movie(abc)
    profile = _profile(movie, abc, mod, code, super_offset, code_offset, **overrides)
    return movie, mod, profile, abc


def _compose(movie: bytes, mod: bytes, profile: compose.ComposeProfile, *, view_url: str = VIEW_URL):
    return compose.compose_with_profile(movie, mod, session=SESSION, view_url=view_url, profile=profile)


def _tags(movie: bytes) -> list[tuple[int, bytes, bytes]]:
    rect_bits = movie[8] >> 3
    pos = 8 + (5 + 4 * rect_bits + 7) // 8 + 4
    tags = []
    while pos < len(movie):
        start = pos
        header = struct.unpack_from("<H", movie, pos)[0]
        pos += 2
        code, length = header >> 6, header & 63
        if length == 63:
            length = struct.unpack_from("<I", movie, pos)[0]
            pos += 4
        payload = movie[pos : pos + length]
        pos += length
        tags.append((code, movie[start:pos], payload))
        if code == 0:
            break
    return tags


def _doabc_payloads(movie: bytes) -> list[bytes]:
    return [payload for code, _raw, payload in _tags(movie) if code == 82]


def _symbol_names(payload: bytes) -> list[tuple[int, str]]:
    count = struct.unpack_from("<H", payload, 0)[0]
    pos = 2
    found = []
    for _ in range(count):
        character = struct.unpack_from("<H", payload, pos)[0]
        pos += 2
        end = payload.index(b"\0", pos)
        found.append((character, payload[pos:end].decode("ascii")))
        pos = end + 1
    return found


def _strings(abc: bytes) -> list[str]:
    offset = 7
    count, width = _read_u30(abc, offset)
    offset += width
    found = []
    for _ in range(1, count):
        length, width = _read_u30(abc, offset)
        offset += width
        found.append(abc[offset : offset + length].decode("utf-8"))
        offset += length
    return found


def _read_u30(data: bytes, offset: int) -> tuple[int, int]:
    value = 0
    width = 0
    while True:
        byte = data[offset + width]
        value |= (byte & 0x7F) << (7 * width)
        width += 1
        if not byte & 0x80:
            return value, width


def test_production_profile_pins_the_measured_layout():
    profile = compose.PRODUCTION_PROFILE
    assert profile.movie_sha256 == "57582fb10fe1e2551989bf15d8aec1df8b62392903974a1e8ea40ac2b1734ec0"
    assert profile.abc_sha256 == "97b8910be821762b36567497ee2a2e94cd05540f3536bdc7e7ac4d1411b78f42"
    assert profile.mod_abc_sha256 == "d8d0b35d1b15268f7ef39880202f22d363410a615c15ce6161585272f908a3fd"
    assert profile.source_sha256 == "836a2e812d7131b99e2719b6afc7d8237174d11112e65819901003b00bc043f1"
    assert profile.screen_source_sha256 == "d4d824dc4e62963cdeab65c3f20fd30c1e49bb86cd1a3a923b8b1f8c0c1bfabd"
    assert profile.root_movie_source_sha256 == "9791d1371d8a0b9d1cc2f936e1a30b8cfb0ba9add9dfc289e7443bfc27404432"
    assert profile.super_offset == 446019
    assert profile.super_bytes == _u30(OLD_MULTINAME) == SUPER_BYTES
    assert profile.old_multiname_index == OLD_MULTINAME
    assert profile.class_index == 702
    assert profile.code_offset == 1113629
    assert profile.code_length == 73
    assert profile.code_sha256 == "b09ed973afb268ab53aa4c7b9f78e65574da52bcdfc2b7abc590086a8039f174"
    assert profile.method_index == 11548
    assert profile.script_index == 700
    assert profile.doabc_index == 177
    assert profile.symbol_character == 83
    assert profile.symbol_name == "RootMenuMovie"
    assert compose.AUTHORED_CLASSES == ["menus::MctRootMenu", "MctMainMenuScreen", "MctRootMenuMovie"]
    assert compose.MAX_MOVIE_BYTES == 16 * 1024 * 1024
    assert compose.MAX_MOD_ABC_BYTES == 64 * 1024


@pytest.mark.parametrize("scene_id", ["midgame", "endgame"])
def test_match_composition_preserves_stock_abc_and_other_symbol_bindings(monkeypatch, scene_id):
    measured = compose.MATCH_PROFILES[scene_id]
    names = ["menus", "BaseMenu", measured.original_root_name, measured.document_source_name, "Other"]
    abc, super_offset, code_offset = _original_abc(names)
    mod = _mod([measured.menu_class, "__MCT_VIEW_URL__", "__MCT_SESSION__",
                measured.screen_class, measured.wrapper_class])
    symbols = [(0, measured.document_source_name), (measured.symbol_character, measured.symbol_name), (99, "Other")]
    movie = _movie(abc, symbols=symbols)
    profile = replace(measured, movie_sha256=hashlib.sha256(movie).hexdigest(), movie_bytes=len(movie),
                      abc_sha256=hashlib.sha256(abc).hexdigest(), mod_abc_sha256=hashlib.sha256(mod).hexdigest(),
                      mod_abc_bytes=len(mod), super_offset=super_offset, super_bytes=SUPER_BYTES,
                      old_multiname_index=OLD_MULTINAME,
                      code_offset=code_offset, code_length=len(SCRIPT_CODE),
                      code_sha256=hashlib.sha256(SCRIPT_CODE).hexdigest(), doabc_index=1)
    monkeypatch.setitem(compose.MATCH_PROFILES, scene_id, profile)
    result = compose.compose_match_movie(scene_id, movie, mod, session=SESSION, view_url=UNICODE_URL)
    output_tags = _tags(result["data"])
    originals = _tags(movie)
    assert [raw for code, raw, _ in output_tags if code not in (82, 76)] == [
        raw for code, raw, _ in originals if code not in (82, 76)]
    bound_symbols = _symbol_names(next(payload for code, _, payload in output_tags if code == 76))
    assert bound_symbols == [(0, measured.document_target_name), *symbols[1:]]
    payloads = _doabc_payloads(result["data"])
    old = _u30(len(measured.original_root_name)) + measured.original_root_name.encode()
    new = _u30(len(measured.renamed_original_root)) + measured.renamed_original_root.encode()
    assert payloads[0][5:] == abc.replace(old, new)
    assert len(payloads) == 2
    assert UNICODE_URL.encode() in payloads[1] and SESSION.encode() in payloads[1]
    assert measured.wrapper_class.encode() not in payloads[1]
    with pytest.raises(compose.ComposeRejected, match="movie hash mismatch"):
        compose.compose_match_movie(scene_id, movie + b"x", mod, session=SESSION, view_url=VIEW_URL)
    with pytest.raises(compose.ComposeRejected, match="abc hash mismatch"):
        compose.compose_match_movie(scene_id, movie, mod + b"x", session=SESSION, view_url=VIEW_URL)


@pytest.mark.parametrize("scene", ["pause", "results", "frontend", "../midgame", None])
def test_match_entry_refuses_other_scene_identifiers(scene):
    with pytest.raises(compose.ComposeRejected, match="scene"):
        compose.compose_match_movie(scene, b"", b"", session=SESSION, view_url=VIEW_URL)


def test_root_rename_preserves_superclass_and_script_bytes():
    movie, mod, profile, abc = _ready()
    original_tags = _tags(movie)
    result = _compose(movie, mod, profile)
    output = result["data"]
    metadata = result["metadata"]
    output_tags = _tags(output)
    assert [raw for code, raw, _payload in output_tags if code not in (82, 76)] == [
        raw for code, raw, _payload in original_tags if code not in (82, 76)
    ]
    original_symbol = next(payload for code, _raw, payload in original_tags if code == 76)
    output_symbol = next(payload for code, _raw, payload in output_tags if code == 76)
    original_entries = _symbol_names(original_symbol)
    output_entries = _symbol_names(output_symbol)
    assert original_entries[0] == (0, "MainMenuScreen")
    assert output_entries[0] == (0, "MctMainMenuScreen")
    assert output_entries[1:] == original_entries[1:]
    assert output_entries[1:] == [(83, "RootMenuMovie"), (1, "Other"), (9, "Garage")]
    payloads = _doabc_payloads(output)
    assert len(payloads) == 2
    renamed = payloads[0][5:]
    encoded_old = b"\x0dRootMenuMovie"
    encoded_new = b"\x18MctOriginalRootMenuMovie"
    assert abc.count(encoded_old) == 1
    start = abc.find(encoded_old)
    assert renamed == abc[:start] + encoded_new + abc[start + len(encoded_old) :]
    delta = len(encoded_new) - len(encoded_old)
    assert delta == 11
    assert renamed[profile.super_offset + delta : profile.super_offset + delta + len(SUPER_BYTES)] == SUPER_BYTES
    code = abc[profile.code_offset : profile.code_offset + len(SCRIPT_CODE)]
    assert code == SCRIPT_CODE
    assert code.count(SUPER_BYTES) == 2
    assert renamed[profile.code_offset + delta : profile.code_offset + delta + len(code)] == code
    added = payloads[1]
    assert added.startswith(struct.pack("<I", 1) + b"MCTNativeMenu\0")
    bound = added[18:]
    assert _strings(bound) == [
        "MctRootMenu",
        VIEW_URL,
        SESSION,
        "__MCT_",
        "N" * 130,
        "MctMainMenuScreen",
        "RootMenuMovie",
    ]
    assert b"QNAME" + _u30(WRAPPER_INDEX) in bound
    assert b"MctRootMenuMovie" not in bound
    assert bound.endswith(b"TAIL__MCT_VIEW_URL____MCT_SESSION__")
    assert metadata["constructed"] is True
    assert metadata["production_ready"] is False
    assert metadata["runtime_verified"] is False
    assert metadata["gfx_initialization_order_verified"] is False
    assert metadata["file_view_verified"] is False
    assert metadata["devutil_log_verified"] is False
    assert metadata["online_suppression_verified"] is False
    assert metadata["class_loader_verified"] is False
    assert metadata["original_string_delta"] == 11
    assert metadata["authored_string_delta"] == -3
    assert metadata["authored_class_count"] == 3
    assert metadata["authored_classes"] == ["menus::MctRootMenu", "MctMainMenuScreen", "MctRootMenuMovie"]
    assert metadata["library_classes"] == compose.LIBRARY_CLASSES
    assert metadata["compiled_classes"] == compose.COMPILED_CLASSES
    assert metadata["runtime_root_class"] == "RootMenuMovie"
    assert metadata["original_root_alias"] == "MctOriginalRootMenuMovie"
    assert metadata["timeline_character"] == 83
    assert metadata["timeline_name"] == "RootMenuMovie"
    assert metadata["document_character"] == 0
    assert metadata["document_symbol_to"] == "MctMainMenuScreen"
    assert metadata["doabc_count"] == 2
    assert metadata["script_index"] == 700
    assert metadata["superclass_offset"] == profile.super_offset
    assert metadata["script_code_sha256"] == profile.code_sha256


def test_non_pool_copy_of_the_original_name_is_not_renamed():
    tail = b"\x0dRootMenuMovie"
    movie, mod, profile, abc = _ready(tail=tail)
    renamed = _doabc_payloads(_compose(movie, mod, profile)["data"])[0][5:]
    encoded_old = b"\x0dRootMenuMovie"
    assert abc.count(encoded_old) == 2
    start = abc.find(encoded_old)
    assert renamed == abc[:start] + b"\x18MctOriginalRootMenuMovie" + abc[start + len(encoded_old) :]
    assert renamed.endswith(tail)


@pytest.mark.parametrize(
    "names",
    [
        ["menus", "RootMenu", "MainMenuScreen"],
        ["menus", "RootMenuMovie", "RootMenuMovie"],
        ["menus", "RootMenuMovie", "MctOriginalRootMenuMovie"],
    ],
)
def test_original_root_alias_must_be_exact(names: list[str]):
    movie, mod, profile, _abc_bytes = _ready(names)
    with pytest.raises(compose.ComposeRejected, match="class alias"):
        _compose(movie, mod, profile)


def test_authored_root_name_collision_is_rejected():
    movie, _ignored, base, abc = _ready()
    mod = _mod(MOD_NAMES + ["RootMenuMovie"])
    profile = _profile(movie, abc, mod, SCRIPT_CODE, base.super_offset, base.code_offset)
    with pytest.raises(compose.ComposeRejected, match="class alias"):
        _compose(movie, mod, profile)


def test_duplicate_or_missing_wrapper_name_is_rejected():
    movie, _ignored, base, abc = _ready()
    for names in (
        [name for name in MOD_NAMES if name != "MctRootMenuMovie"],
        MOD_NAMES + ["MctRootMenuMovie"],
        [name for name in MOD_NAMES if name != "MctRootMenu"],
    ):
        mod = _mod(names)
        profile = _profile(movie, abc, mod, SCRIPT_CODE, base.super_offset, base.code_offset)
        with pytest.raises(compose.ComposeRejected, match="compiled class"):
            _compose(movie, mod, profile)


def test_changed_script_bytes_are_rejected():
    abc, super_offset, code_offset = _original_abc()
    mutated = bytearray(abc)
    mutated[code_offset] ^= 0x01
    mutated = bytes(mutated)
    mod = _mod()
    movie = _movie(mutated)
    profile = _profile(movie, mutated, mod, SCRIPT_CODE, super_offset, code_offset)
    with pytest.raises(compose.ComposeRejected, match="preserved bytes"):
        _compose(movie, mod, profile)


def test_superclass_bytes_before_the_string_are_rejected():
    movie, mod, profile, _abc_bytes = _ready()
    profile = replace(profile, super_offset=0)
    with pytest.raises(compose.ComposeRejected, match="preserved bytes"):
        _compose(movie, mod, profile)


def test_unicode_and_space_encoded_view_url():
    movie, mod, profile, _abc_bytes = _ready()
    result = _compose(movie, mod, profile, view_url=UNICODE_URL)
    bound = _doabc_payloads(result["data"])[1][18:]
    assert _strings(bound)[1] == UNICODE_URL
    assert UNICODE_URL.encode("ascii") in bound


def test_long_view_url_widens_its_length_prefix():
    movie, mod, profile, _abc_bytes = _ready()
    url = "file:///C:/" + ("a" * 120) + "/native-view.json"
    assert len(url) > 127
    result = _compose(movie, mod, profile, view_url=url)
    bound = _doabc_payloads(result["data"])[1][18:]
    strings = _strings(bound)
    assert strings[1] == url
    assert strings[2:] == [SESSION, "__MCT_", "N" * 130, "MctMainMenuScreen", "RootMenuMovie"]
    assert b"QNAME" + _u30(WRAPPER_INDEX) in bound
    assert bound.endswith(b"TAIL__MCT_VIEW_URL____MCT_SESSION__")


def test_public_entry_rejects_a_movie_other_than_the_pin():
    movie, mod, _profile, _abc_bytes = _ready()
    with pytest.raises(compose.ComposeRejected, match="movie hash mismatch"):
        compose.compose_movie(movie, mod, session=SESSION, view_url=VIEW_URL)


def test_wrong_mod_hash_is_rejected_before_sentinel_binding():
    movie, mod, profile, _abc_bytes = _ready()
    with pytest.raises(compose.ComposeRejected, match="abc hash mismatch"):
        compose.compose_with_profile(
            movie, b"not-the-class", session=SESSION, view_url=VIEW_URL, profile=profile
        )
    assert mod.startswith(struct.pack("<HH", 16, 46))


def test_extra_doabc_is_rejected():
    abc, super_offset, code_offset = _original_abc()
    movie = _movie(abc, extra_doabc=True)
    mod = _mod()
    profile = _profile(movie, abc, mod, SCRIPT_CODE, super_offset, code_offset)
    with pytest.raises(compose.ComposeRejected, match="DoABC count"):
        _compose(movie, mod, profile)


def test_bad_symbol_class_is_rejected():
    abc, super_offset, code_offset = _original_abc()
    movie = _movie(abc, symbol="OtherMovie")
    mod = _mod()
    profile = _profile(movie, abc, mod, SCRIPT_CODE, super_offset, code_offset)
    with pytest.raises(compose.ComposeRejected, match="symbol class"):
        _compose(movie, mod, profile)


def test_symbol_class_must_follow_the_original_doabc():
    abc, super_offset, code_offset = _original_abc()
    movie = _movie(abc, between=True)
    mod = _mod()
    profile = _profile(movie, abc, mod, SCRIPT_CODE, super_offset, code_offset)
    with pytest.raises(compose.ComposeRejected, match="tag order"):
        _compose(movie, mod, profile)


def test_truncated_movie_is_rejected():
    movie, mod, profile, _abc_bytes = _ready()
    cut = bytearray(movie[:-5])
    struct.pack_into("<I", cut, 4, len(cut))
    cut_movie = bytes(cut)
    profile = replace(profile, movie_sha256=hashlib.sha256(cut_movie).hexdigest())
    with pytest.raises(compose.ComposeRejected, match="truncated movie"):
        _compose(cut_movie, mod, profile)


def test_duplicate_sentinel_is_rejected():
    movie, _ignored, base, abc = _ready()
    mod = _mod(
        [
            "MctRootMenu",
            "__MCT_VIEW_URL__",
            "__MCT_VIEW_URL__",
            "__MCT_SESSION__",
            "MctMainMenuScreen",
            "MctRootMenuMovie",
        ]
    )
    profile = _profile(movie, abc, mod, SCRIPT_CODE, base.super_offset, base.code_offset)
    with pytest.raises(compose.ComposeRejected, match="sentinel"):
        _compose(movie, mod, profile)


@pytest.mark.parametrize(
    "view_url",
    [
        "http://127.0.0.1/native-view.json",
        "file://localhost/C:/native-view.json",
        "file:///c:/native-view.json",
        "file:///C:/a/../native-view.json",
        "file:///C:/a/./native-view.json",
        "file:///C:/a/%2E%2E/native-view.json",
        "file:///C:/my file/native-view.json",
        "file:///C:/a%2Fb/native-view.json",
        "file:///C:/a%2fb/native-view.json",
        "file:///C:/%41/native-view.json",
        "file:///C:/native-view.json?session=1",
        "file:///C:/native-view.json#part",
        "file:///C:/user:secret@host/native-view.json",
        "file:///C:/native-view.json/" + "a" * 5000,
    ],
)
def test_view_url_must_be_a_canonical_local_file(view_url: str):
    movie, mod, profile, _abc_bytes = _ready()
    with pytest.raises(compose.ComposeRejected, match="view url"):
        _compose(movie, mod, profile, view_url=view_url)


@pytest.mark.parametrize(
    "session",
    [
        "550E8400-E29B-41D4-A716-446655440000",
        "550e8400e29b41d4a716446655440000",
        "550e8400-e29b-41d4-a716-44665544000",
        "not-a-nonce",
        "550e8400-e29b-41d4-a716-446655440000\n",
    ],
)
def test_session_must_be_a_lowercase_uuid(session: str):
    movie, mod, profile, _abc_bytes = _ready()
    with pytest.raises(compose.ComposeRejected, match="session nonce"):
        compose.compose_with_profile(movie, mod, session=session, view_url=VIEW_URL, profile=profile)


def test_size_limits_and_non_bytes_are_rejected():
    with pytest.raises(compose.ComposeRejected, match="size limit"):
        compose.compose_movie(b"x" * (compose.MAX_MOVIE_BYTES + 1), b"", session=SESSION, view_url=VIEW_URL)
    with pytest.raises(compose.ComposeRejected, match="size limit"):
        compose.compose_movie(
            b"GFX", b"y" * (compose.MAX_MOD_ABC_BYTES + 1), session=SESSION, view_url=VIEW_URL
        )
    with pytest.raises(compose.ComposeRejected, match="movie bytes"):
        compose.compose_movie(bytearray(b"GFX"), b"", session=SESSION, view_url=VIEW_URL)


def test_header_without_rect_is_a_controlled_refusal():
    _movie_bytes, mod, profile, _abc_bytes = _ready()
    movie = b"GFX\x14" + struct.pack("<I", 8)
    profile = replace(profile, movie_sha256=hashlib.sha256(movie).hexdigest())
    with pytest.raises(compose.ComposeRejected, match="truncated movie"):
        _compose(movie, mod, profile)


def _ready_symbols(symbols: list[tuple[int, str]]):
    abc, super_offset, code_offset = _original_abc()
    mod = _mod()
    movie = _movie(abc, symbols=symbols)
    return movie, mod, _profile(movie, abc, mod, SCRIPT_CODE, super_offset, code_offset)


def test_missing_document_character_is_rejected():
    movie, mod, profile = _ready_symbols([(83, "RootMenuMovie"), (1, "Other"), (9, "Garage")])
    with pytest.raises(compose.ComposeRejected, match="document class"):
        _compose(movie, mod, profile)


def test_duplicate_document_character_is_rejected():
    movie, mod, profile = _ready_symbols(
        [(0, "MainMenuScreen"), (0, "MainMenuScreen"), (83, "RootMenuMovie")]
    )
    with pytest.raises(compose.ComposeRejected, match="document class"):
        _compose(movie, mod, profile)


def test_wrong_document_name_is_rejected():
    movie, mod, profile = _ready_symbols(
        [(0, "MainMenu"), (83, "RootMenuMovie"), (1, "Other"), (9, "Garage")]
    )
    with pytest.raises(compose.ComposeRejected, match="document class"):
        _compose(movie, mod, profile)


def test_nonzero_document_binding_is_rejected():
    movie, mod, profile = _ready_symbols(
        [(0, "Hud"), (4, "MainMenuScreen"), (83, "RootMenuMovie"), (1, "Other")]
    )
    with pytest.raises(compose.ComposeRejected, match="document class"):
        _compose(movie, mod, profile)


def test_document_class_already_bound_is_rejected():
    movie, mod, profile = _ready_symbols(
        [(0, "MainMenuScreen"), (2, "MctMainMenuScreen"), (83, "RootMenuMovie"), (1, "Other")]
    )
    with pytest.raises(compose.ComposeRejected, match="document class"):
        _compose(movie, mod, profile)


def test_extra_symbol_bytes_are_rejected():
    movie, mod, _ignored, abc = _ready()
    rebuilt = []
    for code, _raw, payload in _tags(movie):
        if code == 76:
            payload += b"\x00"
        rebuilt.append(_tag(code, payload))
    body = b"".join(rebuilt)
    candidate = movie[:13] + body
    candidate = candidate[:4] + struct.pack("<I", len(candidate)) + candidate[8:]
    _abc_bytes, super_offset, code_offset = _original_abc()
    profile = _profile(candidate, abc, mod, SCRIPT_CODE, super_offset, code_offset)
    with pytest.raises(compose.ComposeRejected, match="symbol class"):
        _compose(candidate, mod, profile)


def _take(data: bytes, offset: int) -> tuple[int, int]:
    value, width = _read_u30(data, offset)
    return value, offset + width


def _skip_trait(data: bytes, offset: int) -> int:
    _name, offset = _take(data, offset)
    kind = data[offset]
    offset += 1
    low = kind & 0x0F
    if low in (0, 6):
        _slot, offset = _take(data, offset)
        _type_name, offset = _take(data, offset)
        value_index, offset = _take(data, offset)
        if value_index:
            offset += 1
    elif low in (1, 2, 3, 4, 5):
        _disp, offset = _take(data, offset)
        _method, offset = _take(data, offset)
    else:
        raise AssertionError(kind)
    if kind & 0x40:
        count, offset = _take(data, offset)
        for _ in range(count):
            _meta, offset = _take(data, offset)
    return offset


def _instance_flags(abc: bytes) -> tuple[dict[str, int], list[str]]:
    """Return instance flags and definition order from parsed class multinames."""

    offset = 4
    for kind in ("int", "uint", "double"):
        count, offset = _take(abc, offset)
        if kind == "double":
            offset += max(0, count - 1) * 8
        else:
            for _ in range(max(0, count - 1)):
                while abc[offset] & 0x80:
                    offset += 1
                offset += 1
    string_count, offset = _take(abc, offset)
    strings = [""]
    for _ in range(1, string_count):
        length, offset = _take(abc, offset)
        strings.append(abc[offset : offset + length].decode("utf-8"))
        offset += length
    namespace_count, offset = _take(abc, offset)
    namespaces = [""]
    for _ in range(1, namespace_count):
        offset += 1
        name, offset = _take(abc, offset)
        namespaces.append(strings[name])
    set_count, offset = _take(abc, offset)
    for _ in range(1, set_count):
        inner, offset = _take(abc, offset)
        for _ in range(inner):
            _item, offset = _take(abc, offset)
    multiname_count, offset = _take(abc, offset)
    multinames = [""]
    for _ in range(1, multiname_count):
        kind = abc[offset]
        offset += 1
        if kind in (0x07, 0x0D):
            namespace, offset = _take(abc, offset)
            name, offset = _take(abc, offset)
            package = namespaces[namespace]
            multinames.append(f"{package}::{strings[name]}" if package else strings[name])
        elif kind in (0x0F, 0x10, 0x1B, 0x1C):
            _value, offset = _take(abc, offset)
            multinames.append("")
        elif kind in (0x11, 0x12):
            multinames.append("")
        elif kind in (0x09, 0x0E):
            name, offset = _take(abc, offset)
            _namespace_set, offset = _take(abc, offset)
            multinames.append(strings[name])
        elif kind == 0x1D:
            _name, offset = _take(abc, offset)
            count, offset = _take(abc, offset)
            for _ in range(count):
                _param, offset = _take(abc, offset)
            multinames.append("")
        else:
            raise AssertionError(kind)
    method_count, offset = _take(abc, offset)
    for _ in range(method_count):
        params, offset = _take(abc, offset)
        _return_type, offset = _take(abc, offset)
        for _ in range(params):
            _param, offset = _take(abc, offset)
        _name, offset = _take(abc, offset)
        flags = abc[offset]
        offset += 1
        if flags & 0x08:
            options, offset = _take(abc, offset)
            for _ in range(options):
                _value, offset = _take(abc, offset)
                offset += 1
        if flags & 0x80:
            for _ in range(params):
                _name, offset = _take(abc, offset)
    metadata_count, offset = _take(abc, offset)
    for _ in range(metadata_count):
        _name, offset = _take(abc, offset)
        items, offset = _take(abc, offset)
        for _ in range(items):
            _key, offset = _take(abc, offset)
            _value, offset = _take(abc, offset)
    class_count, offset = _take(abc, offset)
    found = {}
    ordered = []
    for _ in range(class_count):
        name_index, offset = _take(abc, offset)
        _super, offset = _take(abc, offset)
        flags = abc[offset]
        offset += 1
        if flags & 0x08:
            _protected, offset = _take(abc, offset)
        interfaces, offset = _take(abc, offset)
        for _ in range(interfaces):
            _interface, offset = _take(abc, offset)
        _initializer, offset = _take(abc, offset)
        offset = _skip_trait_list(abc, offset)
        ordered.append(multinames[name_index])
        found[multinames[name_index]] = flags
    return found, ordered


def _skip_trait_list(data: bytes, offset: int) -> int:
    count, offset = _take(data, offset)
    for _ in range(count):
        offset = _skip_trait(data, offset)
    return offset


def test_compiled_abc_matches_the_public_pin():
    root = Path(__file__).resolve().parents[1]
    abc = (root / "native_ui" / "compiled" / "MctRootMenu.abc").read_bytes()
    menu = (root / "native_ui" / "menus" / "MctRootMenu.as").read_bytes()
    screen = (root / "native_ui" / "MctMainMenuScreen.as").read_bytes()
    wrapper = (root / "native_ui" / "MctRootMenuMovie.as").read_bytes()
    manifest = json.loads((root / "native_ui" / "compiled" / "manifest.json").read_text(encoding="utf-8"))
    assert hashlib.sha256(abc).hexdigest() == compose.MOD_ABC_SHA256 == manifest["abc_sha256"]
    assert len(abc) == manifest["abc_bytes"] == 32262
    assert manifest["method_bodies"] == 132
    assert manifest["classes"] == compose.COMPILED_CLASSES
    assert manifest["authored_classes"] == compose.AUTHORED_CLASSES
    assert manifest["library_classes"] == compose.LIBRARY_CLASSES
    assert manifest["library_files"] == compose.LIBRARY_FILES
    assert manifest["game_classes_linked"] is False
    assert manifest["runtime_verified"] is False
    assert manifest["production_ready"] is False
    assert hashlib.sha256(menu).hexdigest() == compose.SOURCE_SHA256 == manifest["source_sha256"]
    assert hashlib.sha256(screen).hexdigest() == compose.SCREEN_SOURCE_SHA256 == manifest["screen_source_sha256"]
    assert hashlib.sha256(wrapper).hexdigest() == compose.ROOT_MOVIE_SOURCE_SHA256
    assert manifest["root_movie_source_sha256"] == compose.ROOT_MOVIE_SOURCE_SHA256
    _pool_end, entries = compose._string_entries(abc)
    texts = [text for _start, _end, text in entries]
    assert texts.count("MctRootMenuMovie") == 1
    assert texts.count("RootMenuMovie") == 0
    assert texts.count("MctRootMenu") == 1
    assert texts.count("MctMainMenuScreen") == 1
    assert texts.count("__MCT_VIEW_URL__") == 1
    assert texts.count("__MCT_SESSION__") == 1
    renamed, info = compose._rename_unique_string(abc, "MctRootMenuMovie", "RootMenuMovie")
    assert info["delta"] == -3
    assert renamed[: info["start"]] == abc[: info["start"]]
    assert renamed[info["start"] + 14 :] == abc[info["end"] :]
    assert renamed[info["start"] : info["start"] + 14] == b"\x0dRootMenuMovie"
    flags, defined = _instance_flags(abc)
    sealed = 0x01
    assert defined == compose.COMPILED_CLASSES
    assert set(defined) == set(compose.AUTHORED_CLASSES) | set(compose.LIBRARY_CLASSES)
    assert len(defined) == len(compose.AUTHORED_CLASSES) + len(compose.LIBRARY_CLASSES)
    assert flags["MctRootMenuMovie"] & sealed == 0
    assert flags["menus::MctRootMenu"] & sealed == sealed
    assert flags["MctMainMenuScreen"] & sealed == sealed
    assert all(flags[name] & sealed == sealed for name in compose.LIBRARY_CLASSES)
    assert texts.count("file:///") == 1
    assert b"debugfile" not in abc.lower()
    assert b":\\" not in abc
    for relative, digest in compose.LIBRARY_FILES.items():
        assert hashlib.sha256((root / relative).read_bytes()).hexdigest() == digest


def test_training_browser_uses_the_authored_panel_instead_of_the_branching_stack():
    root = Path(__file__).resolve().parents[1]
    source = (root / "native_ui" / "menus" / "MctRootMenu.as").read_text(encoding="utf-8")
    browser = source.split("private function generateBrowser()", 1)[1].split(
        "private function browserCommand", 1
    )[0]

    assert "createControl(" not in browser
    assert "showBrowser(true)" in browser
    assert 'browserLayer = new Sprite()' in source
    assert 'm_controlContainer.visible = !visible' in source
    assert 'TextFieldType.INPUT' in source and 'browserSearch.maxChars = 80' in source
    assert 'var tabs:Array = ["lessons", "workshop", "mods", "favorites"]' in source
    assert 'var last:int = Math.min(rows.length, browserTop + BROWSER_ROWS)' in source
    assert 'browserZone = "primary"' in source and 'browserZone = "favorite"' in source
    assert 'browserCommand("primary", String(selected.key))' in source
    assert 'browserCommand("tool", String(tool.key))' in source
    assert 'state == "loading"' in source and 'state == "error"' in source
