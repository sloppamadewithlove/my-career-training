"""Compose owned menu ABCs into pinned development movies.

``compose_movie`` accepts the pinned MainMenu GFX and the frontend class ABC.
``compose_match_movie`` accepts only the fixed ``midgame`` and ``endgame``
scenes. Both return a new movie in memory. They do not write files, launch a
game, or claim that Scaleform has initialized the added classes.
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
SCREEN_CLASS = "MctMainMenuScreen"
ROOT_MOVIE_CLASS = "MctRootMenuMovie"
ORIGINAL_ROOT_NAME = "RootMenuMovie"
RENAMED_ORIGINAL_ROOT = "MctOriginalRootMenuMovie"
AUTHORED_CLASSES = [f"menus::{NEW_CLASS}", SCREEN_CLASS, ROOT_MOVIE_CLASS]
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
    f"menus::{NEW_CLASS}",
    SCREEN_CLASS,
    ROOT_MOVIE_CLASS,
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
VIEW_SENTINEL = "__MCT_VIEW_URL__"
SESSION_SENTINEL = "__MCT_SESSION__"
ADDED_DOABC_NAME = "MCTNativeMenu"
DOCUMENT_CHARACTER = 0
DOCUMENT_SOURCE_NAME = "MainMenuScreen"
DOCUMENT_TARGET_NAME = "MctMainMenuScreen"
MOVIE_SHA256 = "57582fb10fe1e2551989bf15d8aec1df8b62392903974a1e8ea40ac2b1734ec0"
ORIGINAL_ABC_SHA256 = "97b8910be821762b36567497ee2a2e94cd05540f3536bdc7e7ac4d1411b78f42"
MOD_ABC_SHA256 = "6baead2b41601108dbfa2699ed2bd78d1c1f40e78b72499b07afba5a8b407973"
SOURCE_SHA256 = "f5fa6c5309342d03e69638abbb26bc901e583ce7d97dab44f4b8c2bb84d6b4a5"
SCREEN_SOURCE_SHA256 = "d4d824dc4e62963cdeab65c3f20fd30c1e49bb86cd1a3a923b8b1f8c0c1bfabd"
ROOT_MOVIE_SOURCE_SHA256 = "9791d1371d8a0b9d1cc2f936e1a30b8cfb0ba9add9dfc289e7443bfc27404432"
_CODEC_COMPILED = (
    "com.adobe.serialization.json::JSON",
    "com.adobe.serialization.json::JSONDecoder",
    "com.adobe.serialization.json::JSONEncoder",
    "com.adobe.serialization.json::JSONTokenType",
    "com.adobe.serialization.json::JSONTokenizer",
    "com.adobe.serialization.json::JSONToken",
    "com.adobe.serialization.json::JSONParseError",
)
PAUSE_AUTHORED = (
    "menus::MctPauseMenu",
    "MctPauseMenuMovie",
    "MctPauseMenuScreen",
)
RESULTS_AUTHORED = (
    "menus::MctResultsMenu",
    "MctResultsMenuMovie",
    "MctResultsMenuScreen",
)
PAUSE_COMPILED = PAUSE_AUTHORED + _CODEC_COMPILED
RESULTS_COMPILED = RESULTS_AUTHORED + _CODEC_COMPILED
MIDGAME_MOVIE_SHA256 = "fa1aea999d6fff856c8c522c3a5844fdfd532fac0a23bf70369a2274e38a35b7"
MIDGAME_MOVIE_BYTES = 940852
MIDGAME_PACKAGE_SHA256 = "25176a42c7990fce5670f2907020a3641a521553a4aa3c583588717b36e40f50"
MIDGAME_PACKAGE_RELATIVE = "TAGame/CookedPCConsole/GFX_MidGameMenu_SF.upk"
MIDGAME_EXPORT_NAME = "MidgameMenu"
MIDGAME_ORIGINAL_ABC_SHA256 = "71e96360863604a12bb5b53b32f5014beec0ab9fc614b6e03f27c150abe0bba7"
MIDGAME_ABC_SHA256 = "8eb6f2422e5da9c860bd8accad579b99d77d12b41c91c069b62e94e59d293e59"
MIDGAME_ABC_BYTES = 21539
MIDGAME_SOURCE_SHA256 = "afee3dcc68df6ce7f151b49a641378797278f714b973d91f784d9e12d6815e75"
MIDGAME_SCREEN_SOURCE_SHA256 = "829791dea145b2251faf7a34956c5ed6b47369d531bb36409f51527f8f608062"
MIDGAME_ROOT_SOURCE_SHA256 = "e83e7c63db253503c677bd2c149d7acf989a682bb0653e2d0895b235cad28653"
ENDGAME_MOVIE_SHA256 = "94830737b9ee356d5039ecd8f401f0d0734885c22be70e6139b44008e1733b3c"
ENDGAME_MOVIE_BYTES = 1133247
ENDGAME_PACKAGE_SHA256 = "dc4735a75d5ec8ffff423c4db92c3fad1f859191bf384e20ad949e4ed757b3cc"
ENDGAME_PACKAGE_RELATIVE = "TAGame/CookedPCConsole/GFX_EndGameMenu_SF.upk"
ENDGAME_EXPORT_NAME = "EndGameMenu"
ENDGAME_ORIGINAL_ABC_SHA256 = "47c04e221622bf21ecf98b1905ed786b8682f35886e93a9d3b3fb0d4b698c52d"
ENDGAME_ABC_SHA256 = "cb2aee50fa3dd0bc786413dff2546d9c1b112dd10745781e12e8224b14832a13"
ENDGAME_ABC_BYTES = 20382
ENDGAME_SOURCE_SHA256 = "cf84c374387b45d06dc01e4d884d9103e65744a1cbed61167dc492463e3e44aa"
ENDGAME_SCREEN_SOURCE_SHA256 = "56788df6ff86bc2c8f6f7c23a3f73cbc964a36c2cc84435394481e2eff4d13f2"
ENDGAME_ROOT_SOURCE_SHA256 = "15083968df55fc13d0c468336566d080376c8464a70b1a06a464f086db4e792c"
MATCH_SCENE_IDS = ("midgame", "endgame")
_OLD_SUPER_MULTINAME = 5940
_SESSION_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
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
    screen_source_sha256: str
    root_movie_source_sha256: str
    super_offset: int
    super_bytes: bytes
    old_multiname_index: int
    class_index: int
    code_offset: int
    code_length: int
    code_sha256: str
    method_index: int
    script_index: int
    doabc_index: int
    symbol_character: int
    symbol_name: str
    menu_class: str = NEW_CLASS
    screen_class: str = SCREEN_CLASS
    wrapper_class: str = ROOT_MOVIE_CLASS
    original_root_name: str = ORIGINAL_ROOT_NAME
    renamed_original_root: str = RENAMED_ORIGINAL_ROOT
    document_source_name: str = DOCUMENT_SOURCE_NAME
    document_target_name: str = DOCUMENT_TARGET_NAME
    scene_id: str = "frontend"
    package_sha256: str = ""
    package_relative: str = ""
    export_name: str = ""
    movie_bytes: int = 0
    mod_abc_bytes: int = 0
    authored_classes: tuple[str, ...] = tuple(AUTHORED_CLASSES)
    compiled_classes: tuple[str, ...] = tuple(COMPILED_CLASSES)


PRODUCTION_PROFILE = ComposeProfile(
    movie_sha256=MOVIE_SHA256,
    abc_sha256=ORIGINAL_ABC_SHA256,
    mod_abc_sha256=MOD_ABC_SHA256,
    source_sha256=SOURCE_SHA256,
    screen_source_sha256=SCREEN_SOURCE_SHA256,
    root_movie_source_sha256=ROOT_MOVIE_SOURCE_SHA256,
    super_offset=446019,
    super_bytes=bytes.fromhex("b42e"),
    old_multiname_index=_OLD_SUPER_MULTINAME,
    class_index=702,
    code_offset=1113629,
    code_length=73,
    code_sha256="b09ed973afb268ab53aa4c7b9f78e65574da52bcdfc2b7abc590086a8039f174",
    method_index=11548,
    script_index=700,
    doabc_index=177,
    symbol_character=83,
    symbol_name=ORIGINAL_ROOT_NAME,
)

MIDGAME_PROFILE = ComposeProfile(
    movie_sha256=MIDGAME_MOVIE_SHA256,
    abc_sha256=MIDGAME_ORIGINAL_ABC_SHA256,
    mod_abc_sha256=MIDGAME_ABC_SHA256,
    source_sha256=MIDGAME_SOURCE_SHA256,
    screen_source_sha256=MIDGAME_SCREEN_SOURCE_SHA256,
    root_movie_source_sha256=MIDGAME_ROOT_SOURCE_SHA256,
    super_offset=373395,
    super_bytes=bytes.fromhex("c021"),
    old_multiname_index=4288,
    class_index=494,
    code_offset=917990,
    code_length=63,
    code_sha256="2a1fc566e90d22d42f1a36d8500187bdbee0f5d912ec309e8bbd5be3dd621fb9",
    method_index=9421,
    script_index=492,
    doabc_index=35,
    symbol_character=6,
    symbol_name="MidGameMenuMovie",
    menu_class="MctPauseMenu",
    screen_class="MctPauseMenuScreen",
    wrapper_class="MctPauseMenuMovie",
    original_root_name="MidGameMenuMovie",
    renamed_original_root="MctOriginalMidGameMenuMovie",
    document_source_name="MidGameMenuScreen",
    document_target_name="MctPauseMenuScreen",
    scene_id="midgame",
    package_sha256=MIDGAME_PACKAGE_SHA256,
    package_relative=MIDGAME_PACKAGE_RELATIVE,
    export_name=MIDGAME_EXPORT_NAME,
    movie_bytes=MIDGAME_MOVIE_BYTES,
    mod_abc_bytes=MIDGAME_ABC_BYTES,
    authored_classes=PAUSE_AUTHORED,
    compiled_classes=PAUSE_COMPILED,
)

ENDGAME_PROFILE = ComposeProfile(
    movie_sha256=ENDGAME_MOVIE_SHA256,
    abc_sha256=ENDGAME_ORIGINAL_ABC_SHA256,
    mod_abc_sha256=ENDGAME_ABC_SHA256,
    source_sha256=ENDGAME_SOURCE_SHA256,
    screen_source_sha256=ENDGAME_SCREEN_SOURCE_SHA256,
    root_movie_source_sha256=ENDGAME_ROOT_SOURCE_SHA256,
    super_offset=436424,
    super_bytes=bytes.fromhex("b728"),
    old_multiname_index=5175,
    class_index=652,
    code_offset=1101107,
    code_length=73,
    code_sha256="d52dea42400109a102650c7369f167c7bd502032732906594c255c90a0589df7",
    method_index=11075,
    script_index=650,
    doabc_index=148,
    symbol_character=23,
    symbol_name="EndGameMenuMovie",
    menu_class="MctResultsMenu",
    screen_class="MctResultsMenuScreen",
    wrapper_class="MctResultsMenuMovie",
    original_root_name="EndGameMenuMovie",
    renamed_original_root="MctOriginalEndGameMenuMovie",
    document_source_name="EndGameMenuScreen",
    document_target_name="MctResultsMenuScreen",
    scene_id="endgame",
    package_sha256=ENDGAME_PACKAGE_SHA256,
    package_relative=ENDGAME_PACKAGE_RELATIVE,
    export_name=ENDGAME_EXPORT_NAME,
    movie_bytes=ENDGAME_MOVIE_BYTES,
    mod_abc_bytes=ENDGAME_ABC_BYTES,
    authored_classes=RESULTS_AUTHORED,
    compiled_classes=RESULTS_COMPILED,
)

MATCH_PROFILES = {
    "midgame": MIDGAME_PROFILE,
    "endgame": ENDGAME_PROFILE,
}


def compose_movie(original_gfx: bytes, mod_abc: bytes, *, session: str, view_url: str) -> dict:
    """Return the pinned development movie with the authored classes attached."""

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


def compose_match_movie(scene: str, original_gfx: bytes, mod_abc: bytes, *, session: str, view_url: str) -> dict:
    """Compose one fixed match scene. Scene ids are only ``midgame`` and ``endgame``."""

    if type(scene) is not str or scene not in MATCH_PROFILES:
        raise ComposeRejected("scene")
    profile = MATCH_PROFILES[scene]
    _require_inputs(original_gfx, mod_abc)
    if len(original_gfx) != profile.movie_bytes or _sha256(original_gfx) != profile.movie_sha256:
        raise ComposeRejected("movie hash mismatch")
    if len(mod_abc) != profile.mod_abc_bytes or _sha256(mod_abc) != profile.mod_abc_sha256:
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
    renamed_original, original_rename = _rename_original_root(original_abc, profile)
    bound = _bind_mod_abc(mod_abc, session=session, view_url=view_url, profile=profile)
    bound, authored_rename = _rename_unique_string(bound, profile.wrapper_class, profile.original_root_name)
    document_symbol = _rebind_document_symbol(tags[profile.doabc_index + 1].payload, profile)
    output = _assemble(
        original_gfx, header_end, tags, profile.doabc_index, renamed_original, bound, document_symbol
    )
    _require_output(original_gfx, output, header_end, tags, profile, renamed_original, bound)
    metadata = _metadata(
        original_gfx,
        original_abc,
        mod_abc,
        bound,
        output,
        profile,
        original_rename,
        authored_rename,
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
    entries = _symbol_entries(tags[index + 1].payload)
    names = dict(entries)
    if names.get(profile.symbol_character) != profile.symbol_name:
        raise ComposeRejected("symbol class")
    _require_document_binding(entries, profile)


def _symbol_entries(payload: bytes) -> list[tuple[int, str]]:
    if len(payload) < 2:
        raise ComposeRejected("truncated movie")
    count = struct.unpack_from("<H", payload, 0)[0]
    pos = 2
    entries: list[tuple[int, str]] = []
    seen: set[int] = set()
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
        if character in seen:
            if character == DOCUMENT_CHARACTER:
                raise ComposeRejected("document class")
            raise ComposeRejected("symbol class")
        seen.add(character)
        entries.append((character, name))
    if pos != len(payload):
        raise ComposeRejected("symbol class")
    return entries


def _require_document_binding(entries: list[tuple[int, str]], profile: ComposeProfile) -> None:
    names = [name for _character, name in entries]
    source_name = profile.document_source_name
    target_name = profile.document_target_name
    document = [name for character, name in entries if character == DOCUMENT_CHARACTER]
    if len(document) != 1:
        raise ComposeRejected("document class")
    if document[0] == target_name or target_name in names:
        raise ComposeRejected("document class")
    if document[0] != source_name or names.count(source_name) != 1:
        raise ComposeRejected("document class")
    if any(character != DOCUMENT_CHARACTER and name == source_name for character, name in entries):
        raise ComposeRejected("document class")


def _rebind_document_symbol(payload: bytes, profile: ComposeProfile) -> bytes:
    entries = _symbol_entries(payload)
    _require_document_binding(entries, profile)
    source_name = profile.document_source_name
    target_name = profile.document_target_name
    old = struct.pack("<H", DOCUMENT_CHARACTER) + source_name.encode("ascii") + b"\0"
    new = struct.pack("<H", DOCUMENT_CHARACTER) + target_name.encode("ascii") + b"\0"
    if payload.count(old) != 1:
        raise ComposeRejected("document class")
    expected = payload.replace(old, new, 1)
    rebuilt = bytearray(struct.pack("<H", len(entries)))
    for character, name in entries:
        if character == DOCUMENT_CHARACTER:
            name = target_name
        rebuilt += struct.pack("<H", character) + name.encode("utf-8") + b"\0"
    if bytes(rebuilt) != expected or expected.count(new) != 1 or expected.count(old) != 0:
        raise ComposeRejected("document class")
    return expected


def _abc_from_doabc(payload: bytes) -> bytes:
    if len(payload) < 5 or struct.unpack_from("<I", payload, 0)[0] != 1 or payload[4] != 0:
        raise ComposeRejected("DoABC count")
    return payload[5:]


def _rename_original_root(abc: bytes, profile: ComposeProfile) -> tuple[bytes, dict]:
    renamed, info = _rename_unique_string(abc, profile.original_root_name, profile.renamed_original_root)
    _require_original_bodies(abc, renamed, profile, info)
    return renamed, info


def _rename_unique_string(abc: bytes, old: str, new: str) -> tuple[bytes, dict]:
    """Replace one parsed string-pool entry. Later bytes stay intact aside from the length shift."""

    if old == new or not old or not new:
        raise ComposeRejected("class alias")
    try:
        raw_old = old.encode("ascii")
        raw_new = new.encode("ascii")
    except UnicodeEncodeError:
        raise ComposeRejected("class alias") from None
    pool_end, entries = _string_entries(abc)
    old_hits = [(start, end) for start, end, text in entries if text == old]
    if len(old_hits) != 1 or any(text == new for _start, _end, text in entries):
        raise ComposeRejected("class alias")
    start, end = old_hits[0]
    encoded_old = _u30(len(raw_old)) + raw_old
    encoded_new = _u30(len(raw_new)) + raw_new
    if not 4 <= start < end <= pool_end <= len(abc) or abc[start:end] != encoded_old:
        raise ComposeRejected("class alias")
    renamed = abc[:start] + encoded_new + abc[end:]
    if renamed[:start] != abc[:start] or renamed[start + len(encoded_new) :] != abc[end:]:
        raise ComposeRejected("class alias")
    new_pool_end, new_entries = _string_entries(renamed)
    delta = len(encoded_new) - len(encoded_old)
    if new_pool_end != pool_end + delta:
        raise ComposeRejected("class alias")
    expected = [new if text == old else text for _start, _end, text in entries]
    if [text for _start, _end, text in new_entries] != expected:
        raise ComposeRejected("class alias")
    if sum(text == new for _start, _end, text in new_entries) != 1 or any(
        text == old for _start, _end, text in new_entries
    ):
        raise ComposeRejected("class alias")
    return renamed, {"start": start, "end": end, "delta": delta, "pool_end": pool_end, "old": old, "new": new}


def _require_original_bodies(original: bytes, renamed: bytes, profile: ComposeProfile, rename: dict) -> None:
    if profile.super_bytes != _u30(profile.old_multiname_index) or not profile.super_bytes:
        raise ComposeRejected("preserved bytes")
    super_end = profile.super_offset + len(profile.super_bytes)
    code_end = profile.code_offset + profile.code_length
    delta = rename["delta"]
    if not (
        rename["end"] <= profile.super_offset < super_end <= profile.code_offset < code_end <= len(original)
    ):
        raise ComposeRejected("preserved bytes")
    if code_end + delta > len(renamed):
        raise ComposeRejected("preserved bytes")
    superclass = original[profile.super_offset : super_end]
    code = original[profile.code_offset : code_end]
    if superclass != profile.super_bytes or _sha256(code) != profile.code_sha256:
        raise ComposeRejected("preserved bytes")
    if renamed[profile.super_offset + delta : super_end + delta] != superclass:
        raise ComposeRejected("preserved bytes")
    if renamed[profile.code_offset + delta : code_end + delta] != code:
        raise ComposeRejected("preserved bytes")


def _require_root_names(original_abc: bytes, authored_abc: bytes, profile: ComposeProfile) -> None:
    _require_pool_name(original_abc, profile.renamed_original_root, profile.original_root_name)
    _require_pool_name(authored_abc, profile.original_root_name, profile.wrapper_class)
    _pool_end, entries = _string_entries(authored_abc)
    texts = [text for _start, _end, text in entries]
    if texts.count(profile.menu_class) != 1 or texts.count(profile.screen_class) != 1:
        raise ComposeRejected("compiled class")


def _require_pool_name(abc: bytes, present: str, absent: str) -> None:
    _pool_end, entries = _string_entries(abc)
    texts = [text for _start, _end, text in entries]
    if texts.count(present) != 1 or texts.count(absent) != 0:
        raise ComposeRejected("class alias")


def _bind_mod_abc(mod_abc: bytes, *, session: str, view_url: str, profile: ComposeProfile) -> bytes:
    if len(mod_abc) < 4 or mod_abc[:4] != struct.pack("<HH", 16, 46):
        raise ComposeRejected("mod abc")
    pool_end, entries = _string_entries(mod_abc)
    replacements = {
        VIEW_SENTINEL: view_url.encode("ascii"),
        SESSION_SENTINEL: session.encode("ascii"),
    }
    found = {
        text: []
        for text in (
            VIEW_SENTINEL,
            SESSION_SENTINEL,
            profile.menu_class,
            profile.screen_class,
            profile.wrapper_class,
        )
    }
    for start, end, text in entries:
        if text in found:
            found[text].append((start, end))
    if (
        len(found[profile.menu_class]) != 1
        or len(found[profile.screen_class]) != 1
        or len(found[profile.wrapper_class]) != 1
    ):
        raise ComposeRejected("compiled class")
    if any(len(found[text]) != 1 for text in replacements):
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
    renamed_abc: bytes,
    bound_abc: bytes,
    document_symbol: bytes,
) -> bytes:
    patched = _encode_tag(82, struct.pack("<I", 1) + b"\0" + renamed_abc)
    added = _encode_tag(82, struct.pack("<I", 1) + ADDED_DOABC_NAME.encode("ascii") + b"\0" + bound_abc)
    ordered = [tag.raw for tag in tags]
    ordered[doabc_index] = patched
    ordered[doabc_index + 1] = _encode_tag(76, document_symbol)
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
    renamed_abc: bytes,
    bound: bytes,
) -> None:
    if output[:4] != original[:4] or output[8:header_end] != original[8:header_end]:
        raise ComposeRejected("output")
    if struct.unpack_from("<I", output, 4)[0] != len(output):
        raise ComposeRejected("output")
    _header_end, tags = _parse_movie(output)
    if len(tags) != len(original_tags) + 1:
        raise ComposeRejected("output")
    original_raw = [tag.raw for tag in original_tags if tag.code not in (82, 76)]
    output_raw = [tag.raw for tag in tags if tag.code not in (82, 76)]
    if original_raw != output_raw:
        raise ComposeRejected("output")
    original_symbols = [tag for tag in original_tags if tag.code == 76]
    output_symbols = [tag for tag in tags if tag.code == 76]
    if len(original_symbols) != 1 or len(output_symbols) != 1:
        raise ComposeRejected("output")
    if output_symbols[0].payload != _rebind_document_symbol(original_symbols[0].payload, profile):
        raise ComposeRejected("document class")
    if [tag.code for tag in tags].count(82) != 2:
        raise ComposeRejected("output")
    if tags[profile.doabc_index + 1].code != 82 or tags[profile.doabc_index + 2].code != 76:
        raise ComposeRejected("output")
    if _abc_from_doabc(tags[profile.doabc_index].payload) != renamed_abc:
        raise ComposeRejected("output")
    added = tags[profile.doabc_index + 1].payload
    prefix = struct.pack("<I", 1) + ADDED_DOABC_NAME.encode("ascii") + b"\0"
    if not added.startswith(prefix) or added[len(prefix) :] != bound:
        raise ComposeRejected("output")
    rebound = _symbol_entries(tags[profile.doabc_index + 2].payload)
    if dict(rebound).get(profile.symbol_character) != profile.symbol_name:
        raise ComposeRejected("symbol class")
    if dict(rebound).get(DOCUMENT_CHARACTER) != profile.document_target_name:
        raise ComposeRejected("document class")
    _require_root_names(renamed_abc, bound, profile)


def _metadata(
    original: bytes,
    original_abc: bytes,
    mod_abc: bytes,
    bound: bytes,
    output: bytes,
    profile: ComposeProfile,
    original_rename: dict,
    authored_rename: dict,
    session: str,
    view_url: str,
    input_tag_count: int,
) -> dict:
    metadata = {
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
        "screen_source_sha256": profile.screen_source_sha256,
        "root_movie_source_sha256": profile.root_movie_source_sha256,
        "authored_class_count": len(profile.authored_classes),
        "authored_classes": list(profile.authored_classes),
        "library_classes": list(LIBRARY_CLASSES),
        "compiled_classes": list(profile.compiled_classes),
        "class_name": f"menus::{profile.menu_class}",
        "runtime_root_class": profile.original_root_name,
        "original_root_alias": profile.renamed_original_root,
        "timeline_character": profile.symbol_character,
        "timeline_name": profile.symbol_name,
        "document_character": DOCUMENT_CHARACTER,
        "document_symbol_from": profile.document_source_name,
        "document_symbol_to": profile.document_target_name,
        "online_suppression_verified": False,
        "class_loader_verified": False,
        "script_index": profile.script_index,
        "method_index": profile.method_index,
        "class_index": profile.class_index,
        "old_multiname_index": profile.old_multiname_index,
        "superclass_offset": profile.super_offset,
        "script_code_offset": profile.code_offset,
        "script_code_sha256": profile.code_sha256,
        "original_string_delta": original_rename["delta"],
        "authored_string_delta": authored_rename["delta"],
        "doabc_count": 2,
        "added_doabc_name": ADDED_DOABC_NAME,
        "input_tag_count": input_tag_count,
        "output_tag_count": input_tag_count + 1,
        "input_bytes": len(original),
        "output_bytes": len(output),
        "session_utf8_length": len(session.encode("ascii")),
        "view_url_utf8_length": len(view_url.encode("ascii")),
    }
    if profile.scene_id != "frontend":
        metadata["scene_id"] = profile.scene_id
        metadata["export_name"] = profile.export_name
        metadata["package_relative"] = profile.package_relative
    return metadata


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
