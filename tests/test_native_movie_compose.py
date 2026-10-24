"""Synthetic checks for pinned MainMenu composition.

The fixtures are tiny GFX and ABC buffers. They do not include the owned movie.
"""

from __future__ import annotations

import hashlib
import importlib.util
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
STRING_COUNT = 128
MULTINAME_COUNT = 128
OLD_MULTINAME = 200
CLASS_INDEX = 7
CODE_OFFSET = 48
CODE_LENGTH = 73


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


def _code(old: int = OLD_MULTINAME, class_index: int = CLASS_INDEX) -> bytes:
    body = bytearray(b"\x30" * 46)
    body.append(0x60)
    body += _u30(old)
    body.append(0x30)
    body.append(0x60)
    body += _u30(old)
    body.append(0x58)
    body += _u30(class_index)
    if len(body) > 72:
        raise AssertionError(len(body))
    body += b"\x1d" * (72 - len(body))
    body.append(0x47)
    assert len(body) == CODE_LENGTH
    return bytes(body)


def _abc(
    code: bytes | None = None,
    *,
    old: int = OLD_MULTINAME,
    namespace_kind: int = 0x16,
    multiname_count: int = MULTINAME_COUNT,
) -> bytes:
    code = _code(old) if code is None else code
    raw = bytearray(CODE_OFFSET + len(code) + 5)
    raw[0:4] = struct.pack("<HH", 16, 46)
    raw[4:6] = _u30(STRING_COUNT)
    raw[8:14] = b"\x05menus"
    raw[14:20] = b"KEEP!!"
    raw[20] = namespace_kind
    raw[21] = 1
    raw[22:24] = b"NS"
    raw[24:26] = _u30(multiname_count)
    raw[26:40] = b"MULTINAME_PAD!"
    raw[40:45] = b"AFTER"
    encoded = _u30(old)
    raw[45 : 45 + len(encoded)] = encoded
    raw[47] = 0x5A
    raw[CODE_OFFSET : CODE_OFFSET + len(code)] = code
    raw[CODE_OFFSET + len(code)] = 0
    raw[CODE_OFFSET + len(code) + 1 :] = b"TAIL"
    return bytes(raw)


def _mod(strings: list[str] | None = None) -> bytes:
    if strings is None:
        strings = [
            "MctRootMenu",
            "__MCT_VIEW_URL__",
            "__MCT_SESSION__",
            "__MCT_",
            "N" * 130,
            "MctMainMenuScreen",
        ]
    out = bytearray(struct.pack("<HH", 16, 46))
    out += bytes((0, 0, 0))
    out += _u30(len(strings) + 1)
    for item in strings:
        raw = item.encode("utf-8")
        out += _u30(len(raw))
        out += raw
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
    movie: bytes, abc: bytes, mod: bytes, code: bytes, **overrides: object
) -> compose.ComposeProfile:
    values = {
        "movie_sha256": hashlib.sha256(movie).hexdigest(),
        "abc_sha256": hashlib.sha256(abc).hexdigest(),
        "mod_abc_sha256": hashlib.sha256(mod).hexdigest(),
        "source_sha256": "ab" * 32,
        "screen_source_sha256": "cd" * 32,
        "string_count": STRING_COUNT,
        "string_count_offset": 4,
        "string_pool_end": 20,
        "menus_string_offset": 8,
        "namespace_kind_offset": 20,
        "namespace_name_index": 1,
        "namespace_index": 4,
        "multiname_count": MULTINAME_COUNT,
        "multiname_count_offset": 24,
        "multiname_pool_end": 40,
        "super_offset": 45,
        "old_multiname_index": OLD_MULTINAME,
        "class_index": CLASS_INDEX,
        "code_offset": CODE_OFFSET,
        "code_length": CODE_LENGTH,
        "code_sha256": hashlib.sha256(code).hexdigest(),
        "getlex_pcs": (46, 50),
        "pushscope_pc": 49,
        "newclass_pc": 53,
        "method_index": 1,
        "script_index": 1,
        "doabc_index": 1,
        "symbol_character": 83,
        "symbol_name": "RootMenuMovie",
        "preserved_spans": ((14, b"KEEP!!"), (26, b"MULTINAME_PAD!")),
    }
    values.update(overrides)
    return compose.ComposeProfile(**values)


def _ready(abc: bytes | None = None, mod: bytes | None = None, **overrides: object):
    abc = _abc() if abc is None else abc
    mod = _mod() if mod is None else mod
    code = abc[CODE_OFFSET : CODE_OFFSET + CODE_LENGTH]
    movie = _movie(abc)
    return movie, mod, _profile(movie, abc, mod, code, **overrides), abc


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


def _strings(abc: bytes) -> list[str]:
    offset = 7
    count = abc[offset]
    offset += 1
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
    assert profile.mod_abc_sha256 == "fbcedd362034ac360d8b5a7de7c9041f5fbe1604fab99b0ead6a9dc6249e5eaf"
    assert profile.source_sha256 == "dd27703fb36a8959f47b8de68fc7c23dc51f177f1ce4b80470c1bc0b0cc61194"
    assert profile.screen_source_sha256 == "dc074ee1d945a498429ec9d8cbd7892d1eaefe60bb167692474ea26df523ec6a"
    assert profile.string_count == 13849
    assert profile.string_count_offset == 2048
    assert profile.string_pool_end == 274271
    assert profile.menus_string_offset == 113446
    assert profile.namespace_kind_offset == 276629
    assert profile.namespace_name_index == 5806
    assert profile.namespace_index == 814
    assert profile.multiname_count == 12205
    assert profile.multiname_count_offset == 282536
    assert profile.multiname_pool_end == 335281
    assert profile.super_offset == 446019
    assert profile.old_multiname_index == 5940
    assert profile.class_index == 702
    assert profile.code_offset == 1113629
    assert profile.code_length == 73
    assert profile.code_sha256 == "b09ed973afb268ab53aa4c7b9f78e65574da52bcdfc2b7abc590086a8039f174"
    assert profile.getlex_pcs == (46, 50)
    assert profile.pushscope_pc == 49
    assert profile.newclass_pc == 53
    assert profile.method_index == 11548
    assert profile.script_index == 700
    assert profile.doabc_index == 177
    assert profile.symbol_character == 83
    assert profile.symbol_name == "RootMenuMovie"
    assert profile.preserved_spans == ((309137, bytes.fromhex("07ae06982e")),)
    assert compose.MAX_MOVIE_BYTES == 16 * 1024 * 1024
    assert compose.MAX_MOD_ABC_BYTES == 64 * 1024


def test_compose_appends_pools_and_patches_three_references():
    movie, mod, profile, abc = _ready()
    original_tags = _tags(movie)
    result = _compose(movie, mod, profile)
    output = result["data"]
    metadata = result["metadata"]
    assert movie == _movie(abc)
    assert output[:4] == b"GFX\x14"
    assert output[8:13] == movie[8:13]
    assert struct.unpack_from("<I", output, 4)[0] == len(output)
    output_tags = _tags(output)
    assert [raw for code, raw, _payload in output_tags if code not in (82, 76)] == [
        raw for code, raw, _payload in original_tags if code not in (82, 76)
    ]
    original_symbol = next(payload for code, _raw, payload in original_tags if code == 76)
    output_symbol = next(payload for code, _raw, payload in output_tags if code == 76)
    old_document = struct.pack("<H", 0) + b"MainMenuScreen\0"
    new_document = struct.pack("<H", 0) + b"MctMainMenuScreen\0"
    assert original_symbol.count(old_document) == 1
    assert output_symbol == original_symbol.replace(old_document, new_document, 1)
    assert output_symbol.count(struct.pack("<H", 83) + b"RootMenuMovie\0") == 1
    assert output_symbol.count(struct.pack("<H", 1) + b"Other\0") == 1
    assert output_symbol.count(struct.pack("<H", 9) + b"Garage\0") == 1
    payloads = _doabc_payloads(output)
    assert len(payloads) == 2
    assert payloads[0][4] == 0
    spliced = payloads[0][5:]
    shift = 16
    assert spliced[4:6] == _u30(STRING_COUNT + 1)
    assert spliced[20:32] == b"\x0bMctRootMenu"
    assert spliced[36:38] == _u30(MULTINAME_COUNT + 1)
    assert spliced[52:56] == bytes((0x07, 0x04)) + _u30(STRING_COUNT)
    assert spliced[14:20] == b"KEEP!!"
    assert spliced[38:52] == b"MULTINAME_PAD!"
    assert spliced.endswith(b"TAIL")
    code = abc[CODE_OFFSET : CODE_OFFSET + CODE_LENGTH]
    expected = bytearray(code)
    expected[47:49] = _u30(MULTINAME_COUNT)
    expected[51:53] = _u30(MULTINAME_COUNT)
    assert spliced[CODE_OFFSET + shift : CODE_OFFSET + shift + CODE_LENGTH] == bytes(expected)
    assert spliced[45 + shift : 47 + shift] == _u30(MULTINAME_COUNT)
    assert expected[53] == 0x58 and expected[54] == CLASS_INDEX
    added = payloads[1]
    assert added.startswith(struct.pack("<I", 1) + b"MCTNativeMenu\0")
    bound = added[18:]
    assert _strings(bound)[0] == "MctRootMenu"
    assert _strings(bound)[1] == VIEW_URL
    assert _strings(bound)[2] == SESSION
    assert _strings(bound)[3] == "__MCT_"
    assert _strings(bound)[4] == "N" * 130
    assert _strings(bound)[5] == "MctMainMenuScreen"
    assert bound.endswith(b"TAIL__MCT_VIEW_URL____MCT_SESSION__")
    assert bound.count(b"__MCT_VIEW_URL__") == 1
    assert metadata["constructed"] is True
    assert metadata["production_ready"] is False
    assert metadata["runtime_verified"] is False
    assert metadata["gfx_initialization_order_verified"] is False
    assert metadata["bytes_inserted"] == 16
    assert metadata["patched_super_offset"] == 45 + shift
    assert metadata["patched_getlex_operand_offsets"] == [CODE_OFFSET + 47 + shift, CODE_OFFSET + 51 + shift]
    assert metadata["new_string_index"] == STRING_COUNT
    assert metadata["new_multiname_index"] == MULTINAME_COUNT
    assert metadata["doabc_count"] == 2
    assert metadata["output_tag_count"] == 6
    assert metadata["session_utf8_length"] == 36
    assert metadata["authored_class_count"] == 2
    assert metadata["authored_classes"] == ["menus::MctRootMenu", "MctMainMenuScreen"]
    assert metadata["document_character"] == 0
    assert metadata["document_symbol_from"] == "MainMenuScreen"
    assert metadata["document_symbol_to"] == "MctMainMenuScreen"
    assert metadata["online_suppression_verified"] is False
    assert metadata["class_loader_verified"] is False
    assert metadata["screen_source_sha256"] == "cd" * 32


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
    assert strings[2:] == [SESSION, "__MCT_", "N" * 130, "MctMainMenuScreen"]
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


def test_count_mismatch_is_rejected():
    movie, mod, profile, _abc_bytes = _ready()
    profile = replace(profile, string_count=profile.string_count + 1)
    with pytest.raises(compose.ComposeRejected, match="pool count"):
        _compose(movie, mod, profile)


def test_overlapping_splice_is_rejected():
    movie, mod, profile, _abc_bytes = _ready()
    profile = replace(profile, string_pool_end=5)
    with pytest.raises(compose.ComposeRejected, match="overlapping splice"):
        _compose(movie, mod, profile)


def test_operand_width_change_is_rejected():
    code = _code(old=5)
    abc = _abc(code, old=5, multiname_count=200)
    movie = _movie(abc)
    mod = _mod()
    profile = _profile(
        movie,
        abc,
        mod,
        code,
        multiname_count=200,
        old_multiname_index=5,
        getlex_pcs=(46, 49),
        pushscope_pc=48,
        newclass_pc=51,
    )
    with pytest.raises(compose.ComposeRejected, match="operand width"):
        _compose(movie, mod, profile)


def test_nearby_opcode_mismatch_is_rejected():
    abc = bytearray(_abc())
    abc[CODE_OFFSET + 46] = 0x47
    movie, mod, profile, _abc_bytes = _ready(bytes(abc))
    with pytest.raises(compose.ComposeRejected, match="opcode"):
        _compose(movie, mod, profile)


def test_branch_opcode_is_rejected():
    abc = bytearray(_abc())
    abc[CODE_OFFSET] = 0x10
    movie, mod, profile, _abc_bytes = _ready(bytes(abc))
    with pytest.raises(compose.ComposeRejected, match="opcode"):
        _compose(movie, mod, profile)


def test_extra_doabc_is_rejected():
    abc = _abc()
    movie = _movie(abc, extra_doabc=True)
    mod = _mod()
    profile = _profile(movie, abc, mod, abc[CODE_OFFSET : CODE_OFFSET + CODE_LENGTH])
    with pytest.raises(compose.ComposeRejected, match="DoABC count"):
        _compose(movie, mod, profile)


def test_bad_symbol_class_is_rejected():
    abc = _abc()
    movie = _movie(abc, symbol="OtherMovie")
    mod = _mod()
    profile = _profile(movie, abc, mod, abc[CODE_OFFSET : CODE_OFFSET + CODE_LENGTH])
    with pytest.raises(compose.ComposeRejected, match="symbol class"):
        _compose(movie, mod, profile)


def test_symbol_class_must_follow_the_original_doabc():
    abc = _abc()
    movie = _movie(abc, between=True)
    mod = _mod()
    profile = _profile(movie, abc, mod, abc[CODE_OFFSET : CODE_OFFSET + CODE_LENGTH])
    with pytest.raises(compose.ComposeRejected, match="tag order"):
        _compose(movie, mod, profile)


def test_truncated_movie_is_rejected():
    movie, _mod_bytes, profile, _abc_bytes = _ready()
    cut = bytearray(movie[:-5])
    struct.pack_into("<I", cut, 4, len(cut))
    cut_movie = bytes(cut)
    profile = replace(profile, movie_sha256=hashlib.sha256(cut_movie).hexdigest())
    with pytest.raises(compose.ComposeRejected, match="truncated movie"):
        _compose(cut_movie, _mod_bytes, profile)


def test_namespace_must_be_the_menus_package_namespace():
    abc = _abc(namespace_kind=0x08)
    movie, mod, profile, _abc_bytes = _ready(abc)
    with pytest.raises(compose.ComposeRejected, match="namespace"):
        _compose(movie, mod, profile)


def test_duplicate_sentinel_is_rejected():
    movie, _ignored_mod, _ignored_profile, abc = _ready()
    mod = _mod(
        ["MctRootMenu", "__MCT_VIEW_URL__", "__MCT_VIEW_URL__", "__MCT_SESSION__", "MctMainMenuScreen"]
    )
    profile = _profile(movie, abc, mod, abc[CODE_OFFSET : CODE_OFFSET + CODE_LENGTH])
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
    abc = _abc()
    mod = _mod()
    movie = _movie(abc, symbols=symbols)
    code = abc[CODE_OFFSET : CODE_OFFSET + CODE_LENGTH]
    return movie, mod, _profile(movie, abc, mod, code)


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
    profile = _profile(candidate, abc, mod, abc[CODE_OFFSET : CODE_OFFSET + CODE_LENGTH])
    with pytest.raises(compose.ComposeRejected, match="symbol class"):
        _compose(candidate, mod, profile)


def test_compiled_class_requires_both_authored_names():
    movie, _ignored_mod, _ignored_profile, abc = _ready()
    mod = _mod(["MctRootMenu", "__MCT_VIEW_URL__", "__MCT_SESSION__", "__MCT_", "N" * 130])
    profile = _profile(movie, abc, mod, abc[CODE_OFFSET : CODE_OFFSET + CODE_LENGTH])
    with pytest.raises(compose.ComposeRejected, match="compiled class"):
        _compose(movie, mod, profile)


def test_compiled_abc_matches_the_public_pin():
    root = Path(__file__).resolve().parents[1]
    abc = (root / "native_ui" / "compiled" / "MctRootMenu.abc").read_bytes()
    menu = (root / "native_ui" / "menus" / "MctRootMenu.as").read_bytes()
    screen = (root / "native_ui" / "MctMainMenuScreen.as").read_bytes()
    assert hashlib.sha256(abc).hexdigest() == compose.MOD_ABC_SHA256
    assert len(abc) == 8680
    assert hashlib.sha256(menu).hexdigest() == compose.SOURCE_SHA256
    assert hashlib.sha256(screen).hexdigest() == compose.SCREEN_SOURCE_SHA256
