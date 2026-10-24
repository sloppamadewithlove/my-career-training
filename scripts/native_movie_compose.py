"""Compose the owned MctRootMenu ABC into the pinned MainMenu movie.

The public entry accepts one development GFX and the compiled class ABC.
It returns a new movie in memory. It does not write files, launch a game,
or claim that Scaleform has initialized the added class.
"""

from __future__ import annotations

import hashlib
import re
import struct
from dataclasses import dataclass
from typing import NamedTuple

MAX_MOVIE_BYTES = 16 * 1024 * 1024
MAX_MOD_ABC_BYTES = 64 * 1024
MAX_URL_CHARS = 4096
MAX_TAGS = 4096
MAX_POOL = 100_000
NEW_CLASS = "MctRootMenu"
VIEW_SENTINEL = "__MCT_VIEW_URL__"
SESSION_SENTINEL = "__MCT_SESSION__"
ADDED_DOABC_NAME = "MCTNativeMenu"
MOVIE_SHA256 = "57582fb10fe1e2551989bf15d8aec1df8b62392903974a1e8ea40ac2b1734ec0"
ORIGINAL_ABC_SHA256 = "97b8910be821762b36567497ee2a2e94cd05540f3536bdc7e7ac4d1411b78f42"
MOD_ABC_SHA256 = "9d423d2e39743473bec792c0ca38f3b28946238183b03bbfb0a4681767721768"
SOURCE_SHA256 = "1ba9168d4a32e9c0c3ea4c7d7bbe29fda9aae35d3a985d9f3a6c382d91a49600"
_SESSION_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_NO_OPERAND = {0x1D, 0x30, 0x47, 0xD0}
_U8_OPERAND = {0x65}
_U30_OPERAND = {0x58, 0x60, 0x68}
_UNRESERVED = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")


class ComposeRejected(ValueError):
    """The movie, class ABC, or caller binding is outside the pinned composition."""


class _Tag(NamedTuple):
    code: int
    raw: bytes
    payload: bytes


@dataclass(frozen=True)
class ComposeProfile:
    """Pinned offsets for one movie version. This is not a general ABC rewriter."""

    movie_sha256: str
    abc_sha256: str
    mod_abc_sha256: str
    source_sha256: str
    string_count: int
    string_count_offset: int
    string_pool_end: int
    menus_string_offset: int
    namespace_kind_offset: int
    namespace_name_index: int
    namespace_index: int
    multiname_count: int
    multiname_count_offset: int
    multiname_pool_end: int
    super_offset: int
    old_multiname_index: int
    class_index: int
    code_offset: int
    code_length: int
    code_sha256: str
    getlex_pcs: tuple[int, int]
    pushscope_pc: int
    newclass_pc: int
    method_index: int
    script_index: int
    doabc_index: int
    symbol_character: int
    symbol_name: str
    preserved_spans: tuple[tuple[int, bytes], ...] = ()


PRODUCTION_PROFILE = ComposeProfile(
    movie_sha256=MOVIE_SHA256,
    abc_sha256=ORIGINAL_ABC_SHA256,
    mod_abc_sha256=MOD_ABC_SHA256,
    source_sha256=SOURCE_SHA256,
    string_count=13849,
    string_count_offset=2048,
    string_pool_end=274271,
    menus_string_offset=113446,
    namespace_kind_offset=276629,
    namespace_name_index=5806,
    namespace_index=814,
    multiname_count=12205,
    multiname_count_offset=282536,
    multiname_pool_end=335281,
    super_offset=446019,
    old_multiname_index=5940,
    class_index=702,
    code_offset=1113629,
    code_length=73,
    code_sha256="b09ed973afb268ab53aa4c7b9f78e65574da52bcdfc2b7abc590086a8039f174",
    getlex_pcs=(46, 50),
    pushscope_pc=49,
    newclass_pc=53,
    method_index=11548,
    script_index=700,
    doabc_index=177,
    symbol_character=83,
    symbol_name="RootMenuMovie",
    preserved_spans=((309137, bytes.fromhex("07ae06982e")),),
)


def compose_movie(original_gfx: bytes, mod_abc: bytes, *, session: str, view_url: str) -> dict:
    """Return the pinned development movie with MctRootMenu attached and bound."""

    _require_inputs(original_gfx, mod_abc)
    if _sha256(original_gfx) != MOVIE_SHA256:
        raise ComposeRejected("movie hash mismatch")
    if _sha256(mod_abc) != MOD_ABC_SHA256:
        raise ComposeRejected("abc hash mismatch")
    return _compose(original_gfx, mod_abc, session=session, view_url=view_url, profile=PRODUCTION_PROFILE)


def compose_with_profile(
    original_gfx: bytes,
    mod_abc: bytes,
    *,
    session: str,
    view_url: str,
    profile: ComposeProfile,
) -> dict:
    """Same composition as the public entry, for a fixture that carries its own profile."""

    _require_inputs(original_gfx, mod_abc)
    if _sha256(original_gfx) != profile.movie_sha256:
        raise ComposeRejected("movie hash mismatch")
    if _sha256(mod_abc) != profile.mod_abc_sha256:
        raise ComposeRejected("abc hash mismatch")
    return _compose(original_gfx, mod_abc, session=session, view_url=view_url, profile=profile)


def _compose(
    original_gfx: bytes,
    mod_abc: bytes,
    *,
    session: str,
    view_url: str,
    profile: ComposeProfile,
) -> dict:
    _require_session(session)
    _require_view_url(view_url)
    header_end, tags = _parse_movie(original_gfx)
    _require_tag_shape(tags, profile)
    original_abc = _abc_from_doabc(tags[profile.doabc_index].payload)
    if _sha256(original_abc) != profile.abc_sha256:
        raise ComposeRejected("abc hash mismatch")
    spliced, splice = _splice_abc(original_abc, profile)
    bound = _bind_mod_abc(mod_abc, session=session, view_url=view_url)
    output = _assemble(original_gfx, header_end, tags, profile.doabc_index, spliced, bound)
    _require_output(original_gfx, output, header_end, tags, profile, spliced, bound)
    metadata = _metadata(
        original_gfx,
        original_abc,
        mod_abc,
        bound,
        output,
        profile,
        splice,
        session,
        view_url,
        len(tags),
    )
    return {"data": output, "metadata": metadata}


def _require_inputs(original_gfx: object, mod_abc: object) -> None:
    if type(original_gfx) is not bytes or type(mod_abc) is not bytes:
        raise ComposeRejected("movie bytes")
    if len(original_gfx) > MAX_MOVIE_BYTES or len(mod_abc) > MAX_MOD_ABC_BYTES:
        raise ComposeRejected("size limit")


def _require_session(session: object) -> None:
    if type(session) is not str or _SESSION_RE.fullmatch(session) is None:
        raise ComposeRejected("session nonce")


def _require_view_url(view_url: object) -> None:
    if type(view_url) is not str:
        raise ComposeRejected("view url")
    if not 26 <= len(view_url) <= MAX_URL_CHARS or any(
        ord(char) < 33 or ord(char) > 126 for char in view_url
    ):
        raise ComposeRejected("view url")
    if any(char in "\\?#@" for char in view_url) or not view_url.startswith("file:///"):
        raise ComposeRejected("view url")
    rest = view_url[len("file:///") :]
    if len(rest) < 3 or rest[0] not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" or rest[1:3] != ":/":
        raise ComposeRejected("view url")
    segments = rest[2:].split("/")
    if len(segments) < 2 or segments[0] != "" or segments[-1] != "native-view.json":
        raise ComposeRejected("view url")
    if any(segment == "" for segment in segments[1:]):
        raise ComposeRejected("view url")
    for segment in segments[1:]:
        decoded = _decode_segment(segment)
        if decoded in {".", ".."} or _canonical_segment(decoded) != segment:
            raise ComposeRejected("view url")


def _decode_segment(segment: str) -> str:
    raw = bytearray()
    index = 0
    while index < len(segment):
        if segment[index] == "%":
            hexpart = segment[index + 1 : index + 3]
            if len(hexpart) != 2 or any(char not in "0123456789ABCDEF" for char in hexpart):
                raise ComposeRejected("view url")
            raw.append(int(hexpart, 16))
            index += 3
            continue
        if segment[index] not in _UNRESERVED:
            raise ComposeRejected("view url")
        raw.append(ord(segment[index]))
        index += 1
    try:
        text = bytes(raw).decode("utf-8")
    except UnicodeDecodeError:
        raise ComposeRejected("view url") from None
    if any(ord(char) < 32 or ord(char) == 127 or char in "/\\\x00" for char in text):
        raise ComposeRejected("view url")
    return text


def _canonical_segment(text: str) -> str:
    encoded = []
    for byte in text.encode("utf-8"):
        character = chr(byte)
        if byte < 128 and character in _UNRESERVED:
            encoded.append(character)
        else:
            encoded.append(f"%{byte:02X}")
    return "".join(encoded)


def _parse_movie(movie: bytes) -> tuple[int, list[_Tag]]:
    if len(movie) < 9 or movie[:3] != b"GFX" or movie[3] != 20:
        raise ComposeRejected("truncated movie")
    if struct.unpack_from("<I", movie, 4)[0] != len(movie):
        raise ComposeRejected("truncated movie")
    rect_bits = movie[8] >> 3
    header_end = 8 + (5 + 4 * rect_bits + 7) // 8 + 4
    if header_end > len(movie) or struct.unpack_from("<H", movie, header_end - 2)[0] != 1:
        raise ComposeRejected("truncated movie")
    tags: list[_Tag] = []
    pos = header_end
    while pos < len(movie):
        if len(tags) >= MAX_TAGS or pos + 2 > len(movie):
            raise ComposeRejected("truncated movie")
        start = pos
        header = struct.unpack_from("<H", movie, pos)[0]
        pos += 2
        code, length = header >> 6, header & 63
        if length == 63:
            if pos + 4 > len(movie):
                raise ComposeRejected("truncated movie")
            length = struct.unpack_from("<I", movie, pos)[0]
            pos += 4
        if pos + length > len(movie):
            raise ComposeRejected("truncated movie")
        payload = movie[pos : pos + length]
        pos += length
        tags.append(_Tag(code, movie[start:pos], payload))
        if code == 0:
            break
    if not tags or tags[-1].code != 0 or pos != len(movie):
        raise ComposeRejected("truncated movie")
    return header_end, tags


def _require_tag_shape(tags: list[_Tag], profile: ComposeProfile) -> None:
    doabc_indexes = [index for index, tag in enumerate(tags) if tag.code == 82]
    if len(doabc_indexes) != 1:
        raise ComposeRejected("DoABC count")
    index = doabc_indexes[0]
    if index != profile.doabc_index or index + 1 >= len(tags) or tags[index + 1].code != 76:
        raise ComposeRejected("tag order")
    symbols = _symbol_names(tags[index + 1].payload)
    if symbols.get(profile.symbol_character) != profile.symbol_name:
        raise ComposeRejected("symbol class")


def _symbol_names(payload: bytes) -> dict[int, str]:
    if len(payload) < 2:
        raise ComposeRejected("truncated movie")
    count = struct.unpack_from("<H", payload, 0)[0]
    pos = 2
    names: dict[int, str] = {}
    for _ in range(count):
        if pos + 3 > len(payload):
            raise ComposeRejected("truncated movie")
        character = struct.unpack_from("<H", payload, pos)[0]
        pos += 2
        end = payload.find(b"\0", pos)
        if end < 0 or end - pos > 1024:
            raise ComposeRejected("symbol class")
        try:
            name = payload[pos:end].decode("utf-8")
        except UnicodeDecodeError:
            raise ComposeRejected("symbol class") from None
        pos = end + 1
        if character in names:
            raise ComposeRejected("symbol class")
        names[character] = name
    if pos != len(payload):
        raise ComposeRejected("symbol class")
    return names


def _abc_from_doabc(payload: bytes) -> bytes:
    if len(payload) < 5 or struct.unpack_from("<I", payload, 0)[0] != 1 or payload[4] != 0:
        raise ComposeRejected("DoABC count")
    return payload[5:]


def _splice_abc(abc: bytes, profile: ComposeProfile) -> tuple[bytes, dict]:
    string_end = _require_count(abc, profile.string_count_offset, profile.string_count)
    multiname_end = _require_count(abc, profile.multiname_count_offset, profile.multiname_count)
    _require_namespace(abc, profile)
    super_end, super_width = _require_operand(abc, profile.super_offset, profile.old_multiname_index)
    code_end = profile.code_offset + profile.code_length
    if code_end > len(abc):
        raise ComposeRejected("truncated movie")
    code = abc[profile.code_offset : code_end]
    instructions = _walk_initializer(code)
    operand_spans = _require_initializer(code, instructions, profile)
    if code_end >= len(abc):
        raise ComposeRejected("truncated movie")
    exception, exception_end = _read_u30(abc, code_end)
    if exception != 0 or exception_end != code_end + 1:
        raise ComposeRejected("opcode")
    getlex_spans = []
    for pc, width in operand_spans:
        start = profile.code_offset + pc + 1
        getlex_spans.append((start, start + width))
    new_string_index = profile.string_count
    new_multiname_index = profile.multiname_count
    _require_same_width(super_width, new_multiname_index)
    for start, end in getlex_spans:
        _require_same_width(end - start, new_multiname_index)
    string_entry = _u30(len(NEW_CLASS.encode("ascii"))) + NEW_CLASS.encode("ascii")
    qname = bytes((0x07,)) + _u30(profile.namespace_index) + _u30(new_string_index)
    _require_layout(abc, profile, string_end, multiname_end, super_end, getlex_spans, string_entry, qname)
    patched = _join_splices(
        abc,
        profile,
        string_end,
        multiname_end,
        super_end,
        getlex_spans,
        string_entry,
        qname,
        new_multiname_index,
    )
    _require_exact_splices(
        abc, patched, profile, string_entry, qname, getlex_spans, super_end, string_end, multiname_end
    )
    return patched, {
        "string_entry": string_entry,
        "qname": qname,
        "string_count_end": string_end,
        "multiname_count_end": multiname_end,
        "super_end": super_end,
        "getlex_spans": tuple(getlex_spans),
        "new_string_index": new_string_index,
        "new_multiname_index": new_multiname_index,
    }


def _require_count(abc: bytes, offset: int, expected: int) -> int:
    value, end = _read_u30(abc, offset)
    if value != expected or end - offset != len(_u30(value)):
        raise ComposeRejected("pool count")
    if len(_u30(value + 1)) != end - offset:
        raise ComposeRejected("operand width")
    return end


def _require_namespace(abc: bytes, profile: ComposeProfile) -> None:
    if profile.namespace_kind_offset >= len(abc) or abc[profile.namespace_kind_offset] != 0x16:
        raise ComposeRejected("namespace")
    name_index, _end = _read_u30(abc, profile.namespace_kind_offset + 1)
    menus = b"\x05menus"
    start = profile.menus_string_offset
    if name_index != profile.namespace_name_index or abc[start : start + len(menus)] != menus:
        raise ComposeRejected("namespace")


def _require_operand(abc: bytes, offset: int, expected: int) -> tuple[int, int]:
    value, end = _read_u30(abc, offset)
    width = end - offset
    if value != expected or width != len(_u30(value)):
        raise ComposeRejected("pool count")
    return end, width


def _require_same_width(width: int, new_index: int) -> None:
    if width != len(_u30(new_index)):
        raise ComposeRejected("operand width")


def _walk_initializer(code: bytes) -> list[tuple[int, int, int | None]]:
    instructions = []
    pos = 0
    while pos < len(code):
        start = pos
        opcode = code[pos]
        pos += 1
        if opcode in range(0x0C, 0x1C):
            raise ComposeRejected("opcode")
        if opcode in _NO_OPERAND:
            instructions.append((start, opcode, None))
        elif opcode in _U8_OPERAND:
            if pos >= len(code):
                raise ComposeRejected("truncated movie")
            instructions.append((start, opcode, code[pos]))
            pos += 1
        elif opcode in _U30_OPERAND:
            value, pos = _read_u30(code, pos)
            instructions.append((start, opcode, value))
        else:
            raise ComposeRejected("opcode")
    return instructions


def _require_initializer(
    code: bytes,
    instructions: list[tuple[int, int, int | None]],
    profile: ComposeProfile,
) -> list[tuple[int, int]]:
    if len(profile.getlex_pcs) != 2:
        raise ComposeRejected("opcode")
    by_pc = {pc: (index, opcode, operand) for index, (pc, opcode, operand) in enumerate(instructions)}
    try:
        first = by_pc[profile.getlex_pcs[0]]
        second = by_pc[profile.getlex_pcs[1]]
        scope = by_pc[profile.pushscope_pc]
        newclass = by_pc[profile.newclass_pc]
    except KeyError:
        raise ComposeRejected("opcode") from None
    if (first[1], scope[1], second[1], newclass[1]) != (0x60, 0x30, 0x60, 0x58):
        raise ComposeRejected("opcode")
    if (first[0] + 1, scope[0] + 1, second[0] + 1) != (scope[0], second[0], newclass[0]):
        raise ComposeRejected("opcode")
    if first[2] != profile.old_multiname_index or second[2] != profile.old_multiname_index:
        raise ComposeRejected("opcode")
    if newclass[2] != profile.class_index:
        raise ComposeRejected("opcode")
    spans = []
    for pc, _opcode, operand in (instructions[first[0]], instructions[second[0]]):
        if type(operand) is not int:
            raise ComposeRejected("opcode")
        width = instructions[by_pc[pc][0] + 1][0] - (pc + 1)
        if width != len(_u30(operand)):
            raise ComposeRejected("operand width")
        spans.append((pc, width))
    if b"".join(_instruction_bytes(instructions)) != code or _sha256(code) != profile.code_sha256:
        raise ComposeRejected("opcode")
    return spans


def _instruction_bytes(instructions: list[tuple[int, int, int | None]]) -> list[bytes]:
    rendered = []
    for _pc, opcode, operand in instructions:
        if opcode in _NO_OPERAND:
            rendered.append(bytes((opcode,)))
        elif opcode in _U8_OPERAND and type(operand) is int:
            rendered.append(bytes((opcode, operand)))
        elif opcode in _U30_OPERAND and type(operand) is int:
            rendered.append(bytes((opcode,)) + _u30(operand))
        else:
            raise ComposeRejected("opcode")
    return rendered


def _require_layout(
    abc: bytes,
    profile: ComposeProfile,
    string_end: int,
    multiname_end: int,
    super_end: int,
    getlex_spans: list[tuple[int, int]],
    string_entry: bytes,
    qname: bytes,
) -> None:
    code_end = profile.code_offset + profile.code_length
    mutations = [
        (profile.string_count_offset, string_end),
        (profile.multiname_count_offset, multiname_end),
        (profile.super_offset, super_end),
        getlex_spans[0],
        getlex_spans[1],
    ]
    for start, end in mutations:
        if start < 0 or end > len(abc) or start >= end:
            raise ComposeRejected("truncated movie")
    ordered = sorted(mutations)
    if ordered != mutations or any(left[1] > right[0] for left, right in zip(ordered, ordered[1:])):
        raise ComposeRejected("overlapping splice")
    if not string_end <= profile.string_pool_end <= profile.multiname_count_offset:
        raise ComposeRejected("overlapping splice")
    if not multiname_end <= profile.multiname_pool_end <= profile.super_offset:
        raise ComposeRejected("overlapping splice")
    if not super_end <= getlex_spans[0][0] <= getlex_spans[0][1] <= getlex_spans[1][0]:
        raise ComposeRejected("overlapping splice")
    if getlex_spans[1][1] > code_end:
        raise ComposeRejected("overlapping splice")
    inserts = (profile.string_pool_end, profile.multiname_pool_end)
    read_only = [(profile.menus_string_offset, profile.menus_string_offset + len(b"\x05menus"))]
    name_index, name_end = _read_u30(abc, profile.namespace_kind_offset + 1)
    if name_index != profile.namespace_name_index:
        raise ComposeRejected("namespace")
    read_only.append((profile.namespace_kind_offset, name_end))
    for start, blob in profile.preserved_spans:
        read_only.append((start, start + len(blob)))
        if abc[start : start + len(blob)] != blob:
            raise ComposeRejected("preserved bytes")
    for start, end in read_only:
        if start < 0 or end > len(abc):
            raise ComposeRejected("truncated movie")
        if any(start < insert < end for insert in inserts) or any(
            _overlaps((start, end), mutation) for mutation in mutations
        ):
            raise ComposeRejected("overlapping splice")
    if not string_entry or not qname:
        raise ComposeRejected("splice")


def _join_splices(
    abc: bytes,
    profile: ComposeProfile,
    string_end: int,
    multiname_end: int,
    super_end: int,
    getlex_spans: list[tuple[int, int]],
    string_entry: bytes,
    qname: bytes,
    new_multiname_index: int,
) -> bytes:
    first, second = getlex_spans
    parts = (
        abc[: profile.string_count_offset],
        _u30(profile.string_count + 1),
        abc[string_end : profile.string_pool_end],
        string_entry,
        abc[profile.string_pool_end : profile.multiname_count_offset],
        _u30(profile.multiname_count + 1),
        abc[multiname_end : profile.multiname_pool_end],
        qname,
        abc[profile.multiname_pool_end : profile.super_offset],
        _u30(new_multiname_index),
        abc[super_end : first[0]],
        _u30(new_multiname_index),
        abc[first[1] : second[0]],
        _u30(new_multiname_index),
        abc[second[1] :],
    )
    return b"".join(parts)


def _require_exact_splices(
    original: bytes,
    patched: bytes,
    profile: ComposeProfile,
    string_entry: bytes,
    qname: bytes,
    getlex_spans: list[tuple[int, int]],
    super_end: int,
    string_end: int,
    multiname_end: int,
) -> None:
    qname_at = profile.multiname_pool_end + len(string_entry)
    if patched[qname_at : qname_at + len(qname)] != qname:
        raise ComposeRejected("splice")
    without_qname = patched[:qname_at] + patched[qname_at + len(qname) :]
    string_at = profile.string_pool_end
    if without_qname[string_at : string_at + len(string_entry)] != string_entry:
        raise ComposeRejected("splice")
    restored = bytearray(without_qname[:string_at] + without_qname[string_at + len(string_entry) :])
    spans = (
        (profile.string_count_offset, string_end),
        (profile.multiname_count_offset, multiname_end),
        (profile.super_offset, super_end),
        getlex_spans[0],
        getlex_spans[1],
    )
    for start, end in spans:
        restored[start:end] = original[start:end]
    if bytes(restored) != original:
        raise ComposeRejected("splice")
    for start, blob in profile.preserved_spans:
        shifted = _shift(
            start, profile.string_pool_end, len(string_entry), profile.multiname_pool_end, len(qname)
        )
        if patched[shifted : shifted + len(blob)] != blob:
            raise ComposeRejected("preserved bytes")


def _shift(offset: int, string_end: int, string_len: int, multiname_end: int, qname_len: int) -> int:
    shifted = offset
    if offset >= string_end:
        shifted += string_len
    if offset >= multiname_end:
        shifted += qname_len
    return shifted


def _bind_mod_abc(mod_abc: bytes, *, session: str, view_url: str) -> bytes:
    if len(mod_abc) < 4 or mod_abc[:4] != struct.pack("<HH", 16, 46):
        raise ComposeRejected("mod abc")
    pool_end, entries = _string_entries(mod_abc)
    replacements = {
        VIEW_SENTINEL: view_url.encode("ascii"),
        SESSION_SENTINEL: session.encode("ascii"),
    }
    found = {text: [] for text in (VIEW_SENTINEL, SESSION_SENTINEL, NEW_CLASS)}
    for start, end, text in entries:
        if text in found:
            found[text].append((start, end))
    if len(found[NEW_CLASS]) != 1 or any(len(found[text]) != 1 for text in replacements):
        raise ComposeRejected("sentinel")
    out = bytearray()
    cursor = 0
    for start, end, text in entries:
        out += mod_abc[cursor:start]
        if text in replacements:
            raw = replacements[text]
            out += _u30(len(raw))
            out += raw
        else:
            out += mod_abc[start:end]
        cursor = end
    out += mod_abc[cursor:]
    if bytes(out[:pool_end]) == mod_abc[:pool_end]:
        raise ComposeRejected("sentinel")
    if bytes(out[len(out) - (len(mod_abc) - pool_end) :]) != mod_abc[pool_end:]:
        raise ComposeRejected("sentinel")
    return bytes(out)


def _string_entries(mod_abc: bytes) -> tuple[int, list[tuple[int, int, str]]]:
    offset = 4
    for kind in ("int", "uint", "double"):
        count, offset = _read_u30(mod_abc, offset)
        if count > MAX_POOL:
            raise ComposeRejected("mod abc")
        if kind == "double":
            offset += max(0, count - 1) * 8
            if offset > len(mod_abc):
                raise ComposeRejected("truncated movie")
            continue
        for _ in range(max(0, count - 1)):
            _value, offset = _read_varint(mod_abc, offset, 0xFFFFFFFF)
    count, offset = _read_u30(mod_abc, offset)
    if count > MAX_POOL:
        raise ComposeRejected("mod abc")
    entries = []
    for _ in range(1, count):
        start = offset
        length, offset = _read_u30(mod_abc, offset)
        if length > len(mod_abc) - offset:
            raise ComposeRejected("truncated movie")
        raw = mod_abc[offset : offset + length]
        offset += length
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise ComposeRejected("mod abc") from None
        entries.append((start, offset, text))
    return offset, entries


def _assemble(
    original: bytes,
    header_end: int,
    tags: list[_Tag],
    doabc_index: int,
    spliced_abc: bytes,
    bound_abc: bytes,
) -> bytes:
    patched = _encode_tag(82, struct.pack("<I", 1) + b"\0" + spliced_abc)
    added = _encode_tag(82, struct.pack("<I", 1) + ADDED_DOABC_NAME.encode("ascii") + b"\0" + bound_abc)
    ordered = [tag.raw for tag in tags]
    ordered[doabc_index] = patched
    ordered.insert(doabc_index + 1, added)
    body = b"".join(ordered)
    output = bytearray(original[:4] + b"\0\0\0\0" + original[8:header_end] + body)
    if len(output) > MAX_MOVIE_BYTES:
        raise ComposeRejected("size limit")
    struct.pack_into("<I", output, 4, len(output))
    return bytes(output)


def _encode_tag(code: int, payload: bytes) -> bytes:
    if len(payload) < 63:
        return struct.pack("<H", (code << 6) | len(payload)) + payload
    return struct.pack("<HI", (code << 6) | 63, len(payload)) + payload


def _require_output(
    original: bytes,
    output: bytes,
    header_end: int,
    original_tags: list[_Tag],
    profile: ComposeProfile,
    spliced: bytes,
    bound: bytes,
) -> None:
    if output[:4] != original[:4] or output[8:header_end] != original[8:header_end]:
        raise ComposeRejected("output")
    if struct.unpack_from("<I", output, 4)[0] != len(output):
        raise ComposeRejected("output")
    _header_end, tags = _parse_movie(output)
    if len(tags) != len(original_tags) + 1:
        raise ComposeRejected("output")
    original_raw = [tag.raw for tag in original_tags if tag.code != 82]
    output_raw = [tag.raw for tag in tags if tag.code != 82]
    if original_raw != output_raw:
        raise ComposeRejected("output")
    if [tag.code for tag in tags].count(82) != 2:
        raise ComposeRejected("output")
    if tags[profile.doabc_index + 1].code != 82 or tags[profile.doabc_index + 2].code != 76:
        raise ComposeRejected("output")
    if _abc_from_doabc(tags[profile.doabc_index].payload) != spliced:
        raise ComposeRejected("output")
    added = tags[profile.doabc_index + 1].payload
    prefix = struct.pack("<I", 1) + ADDED_DOABC_NAME.encode("ascii") + b"\0"
    if not added.startswith(prefix) or added[len(prefix) :] != bound:
        raise ComposeRejected("output")
    if (
        _symbol_names(tags[profile.doabc_index + 2].payload).get(profile.symbol_character)
        != profile.symbol_name
    ):
        raise ComposeRejected("symbol class")


def _metadata(
    original: bytes,
    original_abc: bytes,
    mod_abc: bytes,
    bound: bytes,
    output: bytes,
    profile: ComposeProfile,
    splice: dict,
    session: str,
    view_url: str,
    input_tag_count: int,
) -> dict:
    string_len = len(splice["string_entry"])
    qname_len = len(splice["qname"])
    super_offset = _shift(
        profile.super_offset, profile.string_pool_end, string_len, profile.multiname_pool_end, qname_len
    )
    getlex_offsets = [
        _shift(start, profile.string_pool_end, string_len, profile.multiname_pool_end, qname_len)
        for start, _end in splice["getlex_spans"]
    ]
    return {
        "constructed": True,
        "production_ready": False,
        "runtime_verified": False,
        "gfx_initialization_order_verified": False,
        "file_view_verified": False,
        "devutil_log_verified": False,
        "movie_sha256": profile.movie_sha256,
        "original_abc_sha256": _sha256(original_abc),
        "mod_abc_sha256": _sha256(mod_abc),
        "bound_mod_abc_sha256": _sha256(bound),
        "output_sha256": _sha256(output),
        "source_sha256": profile.source_sha256,
        "class_name": f"menus::{NEW_CLASS}",
        "timeline_character": profile.symbol_character,
        "timeline_name": profile.symbol_name,
        "script_index": profile.script_index,
        "method_index": profile.method_index,
        "class_index": profile.class_index,
        "old_multiname_index": profile.old_multiname_index,
        "new_string_index": splice["new_string_index"],
        "new_multiname_index": splice["new_multiname_index"],
        "namespace_index": profile.namespace_index,
        "namespace_kind": 0x16,
        "string_record_bytes": string_len,
        "qname_record_bytes": qname_len,
        "bytes_inserted": string_len + qname_len,
        "patched_super_offset": super_offset,
        "patched_getlex_operand_offsets": getlex_offsets,
        "doabc_count": 2,
        "added_doabc_name": ADDED_DOABC_NAME,
        "input_tag_count": input_tag_count,
        "output_tag_count": input_tag_count + 1,
        "input_bytes": len(original),
        "output_bytes": len(output),
        "session_utf8_length": len(session.encode("ascii")),
        "view_url_utf8_length": len(view_url.encode("ascii")),
    }


def _overlaps(left: tuple[int, int], right: tuple[int, int]) -> bool:
    return left[0] < right[1] and right[0] < left[1]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _u30(value: int) -> bytes:
    if value < 0 or value > 0x3FFFFFFF:
        raise ComposeRejected("operand width")
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def _read_u30(data: bytes, offset: int) -> tuple[int, int]:
    value = 0
    for shift in range(0, 35, 7):
        if offset >= len(data):
            raise ComposeRejected("truncated movie")
        byte = data[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            if value > 0x3FFFFFFF:
                raise ComposeRejected("truncated movie")
            return value, offset
    raise ComposeRejected("truncated movie")


def _read_varint(data: bytes, offset: int, limit: int) -> tuple[int, int]:
    value = 0
    start = offset
    for shift in range(0, 35, 7):
        if offset >= len(data):
            raise ComposeRejected("truncated movie")
        byte = data[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            if offset - start > 5 or value > limit:
                raise ComposeRejected("mod abc")
            return value, offset
    raise ComposeRejected("truncated movie")
