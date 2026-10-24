"""Synthetic fixtures for the read-only menu package reader.

Every package byte in this file is packed with struct. The reader under test
does not build fixtures, and these tests never open an installed game package.
"""
from __future__ import annotations

import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import struct
import sys
import zlib

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "native_package_reader.py"
SPEC = importlib.util.spec_from_file_location("native_package_reader", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
reader = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reader)

MAGIC = 0x9E2A83C1
MEASURED_BLOCK = 131072
NAMES = (
    "None", "Class", "Core", "SwfMovie", "MainMenu", "Width", "IntProperty",
    "Enabled", "BoolProperty", "Margin", "StructProperty", "Vector", "SourceFile",
    "StrProperty", "RawData", "ArrayProperty", "Tag", "MysteryMeta", "ByteProperty",
    "OtherMenu",
)


def fstr_ansi(text: str) -> bytes:
    raw = text.encode("ascii") + b"\x00"
    return struct.pack("<i", len(raw)) + raw


def fstr_utf16(text: str) -> bytes:
    raw = text.encode("utf-16-le") + b"\x00\x00"
    return struct.pack("<i", -(len(raw) // 2)) + raw


def fname(index: int, number: int = 0) -> bytes:
    return struct.pack("<ii", index, number)


def name_entry(text: str, *, utf16: bool = False) -> bytes:
    return (fstr_utf16(text) if utf16 else fstr_ansi(text)) + struct.pack("<Q", 0)


def gfx_bytes(body: bytes, signature: bytes = b"GFX", version: int = 20, declared=None) -> bytes:
    if declared is None:
        declared = 8 + len(body)
    return signature + bytes([version & 0xFF]) + struct.pack("<I", declared) + body


def frame_blocks(block_size: int, blocks: list[tuple[bytes, int]]) -> bytes:
    compressed_total = sum(len(payload) for payload, _size in blocks)
    plain_total = sum(size for _payload, size in blocks)
    header = struct.pack("<4I", MAGIC, block_size, compressed_total, plain_total)
    table = b"".join(struct.pack("<II", len(payload), size) for payload, size in blocks)
    return header + table + b"".join(payload for payload, _size in blocks)


def frame_plain(plain: bytes, block_size: int, suffix: bytes = b"") -> bytes:
    blocks = []
    for offset in range(0, len(plain), block_size):
        part = plain[offset:offset + block_size]
        blocks.append((zlib.compress(part) + suffix, len(part)))
    return frame_blocks(block_size, blocks)


def xor_crypt(key: bytes):
    def crypt(data: bytes) -> bytes:
        return bytes(value ^ key[index % len(key)] for index, value in enumerate(data))
    return crypt


def _movie_object(index: dict[str, int], movie: bytes, *, extra: bool, raw_count, duplicate_raw: bool,
                  unknown: bool, omit_raw: bool, omit_none: bool, raw_type: str) -> bytes:
    def fn(name: str) -> bytes:
        return fname(index[name])

    parts = [struct.pack("<i", 0)]
    if unknown:
        parts.append(fn("Tag") + fn("MysteryMeta") + struct.pack("<ii", 0, 0))
    if extra:
        secret = b"HIDDEN_SOURCE_VALUE"
        parts.append(fn("Width") + fn("IntProperty") + struct.pack("<ii", 4, 0) + struct.pack("<i", 7))
        parts.append(fn("Enabled") + fn("BoolProperty") + struct.pack("<ii", 0, 0) + b"\x01")
        parts.append(fn("Margin") + fn("StructProperty") + struct.pack("<ii", 0, 0) + fn("Vector"))
        parts.append(fn("Tag") + fn("ByteProperty") + struct.pack("<ii", 0, 0) + fn("None"))
        parts.append(fn("SourceFile") + fn("StrProperty") + struct.pack("<ii", len(secret), 0) + secret)
    if not omit_raw:
        count = len(movie) if raw_count is None else raw_count
        payload = struct.pack("<i", count) + movie
        raw = fn("RawData") + fn(raw_type) + struct.pack("<ii", len(payload), 0) + payload
        parts.append(raw)
        if duplicate_raw:
            parts.append(raw)
    if not omit_none:
        parts.append(fn("None"))
    return b"".join(parts)


def _export_bytes(class_ref: int, name_index: int, serial_size: int, serial_offset: int, net_count: int) -> bytes:
    body = b"".join((
        struct.pack("<iii", class_ref, 0, 0),
        fname(name_index),
        struct.pack("<i", 0),
        struct.pack("<Q", 0),
        struct.pack("<i", serial_size),
        struct.pack("<Q", serial_offset),
        struct.pack("<I", 0),
        struct.pack("<i", net_count),
        b"\xAB" * (net_count * 4),
        b"\x00" * 16,
        struct.pack("<I", 0),
    ))
    if len(body) != 72 + net_count * 4:
        raise RuntimeError("export fixture layout drifted")
    return body


def build_package(**kwargs):
    extra_names: list[str] = []
    built = _assemble(extra_names, **kwargs)
    if kwargs.get("align", True) or built.table_span % 16 != 0:
        return built
    extra_names.append("P")
    return _assemble(extra_names, **kwargs)


def _assemble(
    extra_names,
    *,
    version=868,
    licensee=34,
    flags=0x0288028D,
    folder="Synthetic",
    movie_name="MainMenu",
    movie_body=b"menu",
    signature=b"GFX",
    swf_version=20,
    declared=None,
    utf16_movie_name=False,
    block_size=4096,
    nonce=None,
    header_tail=0,
    align=True,
    after_table=b"",
    encrypt=None,
    net_count=0,
    logical_gap=0,
    physical_gap=0,
    raw_count=None,
    duplicate_raw=False,
    unknown_property=False,
    omit_raw=False,
    omit_none=False,
    raw_type="ArrayProperty",
    extra_properties=True,
    second_body=None,
    duplicate_name=False,
    class_ref=-1,
    bad_name_index=False,
    name_gap=0,
    custom_name_entries=None,
    frames=None,
    serial_size=None,
    export_skip=0,
    tail_plain=None,
    split_object=False,
    bad_leading_block=False,
    zlib_suffix=b"",
):
    labels = list(NAMES)
    labels[4] = movie_name
    labels.extend(extra_names)
    if custom_name_entries is None:
        blobs = [
            name_entry(label, utf16=utf16_movie_name and label == movie_name)
            for label in labels
        ]
        index = {label: position for position, label in enumerate(labels)}
    else:
        blobs = list(custom_name_entries)
        index = {label: 0 for label in labels}
    movie = gfx_bytes(movie_body, signature, swf_version, declared)
    first_object = _movie_object(
        index, movie, extra=extra_properties, raw_count=raw_count, duplicate_raw=duplicate_raw,
        unknown=unknown_property, omit_raw=omit_raw, omit_none=omit_none, raw_type=raw_type,
    )
    second_movie = None
    second_object = b""
    if second_body is not None:
        second_movie = gfx_bytes(second_body)
        second_object = _movie_object(
            index, second_movie, extra=extra_properties, raw_count=None, duplicate_raw=False,
            unknown=False, omit_raw=False, omit_none=False, raw_type="ArrayProperty",
        )
    logical_objects = first_object + second_object
    first_size = len(first_object) if serial_size is None else serial_size
    first_skip = export_skip
    if bad_leading_block:
        if len(first_object) > block_size:
            raise RuntimeError("leading-block fixture is larger than one block")
        first_skip = block_size
        first_size = len(first_object)

    folder_bytes = fstr_ansi(folder)
    names_blob = b"".join(blobs)
    import_blob = fname(index["Core"]) + fname(index["Class"]) + struct.pack("<i", 0) + fname(index["SwfMovie"])
    export_plan = [(
        999 if bad_name_index else index[movie_name],
        first_size,
        first_skip,
        class_ref,
        net_count,
    )]
    if second_object:
        export_plan.append((index["OtherMenu"], len(second_object), len(first_object), -1, 0))
    if duplicate_name:
        export_plan.append((index[movie_name], 0, 0, -1, 0))
    export_len = sum(72 + item[4] * 4 for item in export_plan)
    name_offset = 12 + len(folder_bytes) + 32
    import_offset = name_offset + len(names_blob) + name_gap
    export_offset = import_offset + len(import_blob)
    depends_offset = export_offset + export_len
    stride = 36 if licensee == 34 else 24

    if frames is not None:
        chunk_frames = list(frames)
    elif bad_leading_block:
        bad = b"\x7f" * 24
        good = zlib.compress(first_object)
        framed = frame_blocks(block_size, [(bad, block_size), (good, len(first_object))])
        chunk_frames = [(framed, block_size + len(first_object))]
    elif split_object:
        midpoint = max(1, len(logical_objects) // 2)
        if midpoint >= len(logical_objects):
            midpoint = len(logical_objects) - 1
        parts = [logical_objects[:midpoint], logical_objects[midpoint:]]
        chunk_frames = [(frame_plain(part, block_size, zlib_suffix), len(part)) for part in parts]
    else:
        parts = [logical_objects]
        if tail_plain is not None:
            parts.append(tail_plain)
        chunk_frames = [(frame_plain(part, block_size, zlib_suffix), len(part)) for part in parts]

    table_len = 4 + len(chunk_frames) * stride
    table_end = depends_offset + table_len
    body_end = table_end + len(after_table)
    table_span = table_end - name_offset
    if align:
        pad = (16 - ((body_end - name_offset) % 16)) % 16
        header_size = body_end + pad + header_tail
    else:
        header_size = table_end

    records = []
    logical = depends_offset
    physical = header_size
    file_chunks = []
    for position, (framed, plain_size) in enumerate(chunk_frames):
        if position and logical_gap:
            logical += logical_gap
        gap = physical_gap if position else 0
        physical += gap
        records.append((logical, plain_size, physical, len(framed)))
        file_chunks.append((gap, framed))
        logical += plain_size
        physical += len(framed)

    nonce_bytes = b"\x00" * 12 if nonce is None else nonce
    compression = struct.pack("<i", len(records))
    for uncompressed_offset, uncompressed_size, compressed_offset, compressed_size in records:
        compression += struct.pack("<qiqi", uncompressed_offset, uncompressed_size, compressed_offset, compressed_size)
        if licensee == 34:
            compression += nonce_bytes
    if len(compression) != table_len and licensee in (32, 34):
        # Licensees outside 32/34 still need a deterministic table for early rejection.
        if licensee == 34 or licensee == 32:
            raise RuntimeError("compression table fixture drifted")

    summary = struct.pack("<IHHI", MAGIC, version, licensee, header_size)
    summary += folder_bytes
    summary += struct.pack(
        "<8I",
        flags & 0xFFFFFFFF,
        len(blobs),
        name_offset,
        len(export_plan),
        export_offset,
        1,
        import_offset,
        depends_offset,
    )
    exports = b""
    for name_index, size, skip, ref, nets in export_plan:
        exports += _export_bytes(ref, name_index, size, depends_offset + skip, nets)
    header = bytearray(header_size)
    cursor = 0
    for piece in (summary, names_blob, b"\x00" * name_gap, import_blob, exports, compression, after_table):
        header[cursor:cursor + len(piece)] = piece
        cursor += len(piece)
    if header_tail:
        header[-header_tail:] = b"\xA5" * header_tail
    if encrypt is not None:
        region = ((header_size - name_offset) // 16) * 16
        start = name_offset
        header[start:start + region] = encrypt(bytes(header[start:start + region]))

    blob = bytearray(header)
    for gap, framed in file_chunks:
        if gap:
            blob += b"\x00" * gap
        blob += framed
    return _fixture(
        bytes(blob), movie, second_movie, first_object, movie_name, depends_offset + first_skip,
        first_size, depends_offset, header_size, name_offset, export_offset, name_offset - 28,
        labels if custom_name_entries is None else [], table_span,
    )


def _fixture(blob, movie, second_movie, object_bytes, movie_name, serial_offset, serial_size,
             depends_offset, header_size, name_offset, export_offset, name_count_at, names, table_span):
    return type("Fixture", (), {
        "blob": blob,
        "movie": movie,
        "second_movie": second_movie,
        "object_bytes": object_bytes,
        "movie_name": movie_name,
        "serial_offset": serial_offset,
        "serial_size": serial_size,
        "depends_offset": depends_offset,
        "header_size": header_size,
        "name_offset": name_offset,
        "export_offset": export_offset,
        "name_count_at": name_count_at,
        "names": names,
        "table_span": table_span,
    })()


def save(tmp_path: Path, built, name: str = "menu.upk") -> Path:
    path = tmp_path / name
    path.write_bytes(built.blob)
    return path


def test_plain_package_returns_movie_metadata_without_payloads(tmp_path):
    built = build_package(folder="HIDDEN_FOLDER_PATH")
    path = save(tmp_path, built)
    before = path.read_bytes()
    inventory = reader.inspect_menu_package(path)
    movie = reader.read_movie_bytes(path, "MainMenu")

    assert inventory["version"] == 868
    assert inventory["licensee"] == 34
    assert inventory["flags"] == 0x0288028D
    assert inventory["header_decrypted"] is False
    assert inventory["chunk_count"] == 1
    assert inventory["file_size"] == len(built.blob)
    assert inventory["chunks"][0]["uncompressed_offset"] == built.depends_offset
    assert inventory["chunks"][0]["compressed_offset"] == built.header_size
    assert inventory["exports"][0]["class"] == "SwfMovie"
    assert inventory["exports"][0]["serial_offset"] == built.serial_offset
    assert inventory["exports"][0]["serial_size"] == built.serial_size
    assert inventory["logical_size"] == built.serial_offset + built.serial_size
    assert inventory["movies"][0]["name"] == "MainMenu"
    assert inventory["capabilities"] == {
        "loads_runtime": False,
        "writes_assets": False,
        "network_fetch": False,
        "redistribute_payload": False,
        "production_ready": False,
    }
    encoded = json.dumps(inventory)
    assert "HIDDEN_FOLDER_PATH" not in encoded
    assert "HIDDEN_SOURCE_VALUE" not in encoded
    assert set(movie.metadata) == {
        "export_name", "class", "serial_offset", "serial_size", "raw_length", "sha256", "signature",
    }
    assert movie.metadata["export_name"] == "MainMenu"
    assert movie.metadata["class"] == "SwfMovie"
    assert movie.metadata["signature"] == "GFX"
    assert movie.metadata["raw_length"] == len(built.movie)
    assert movie.metadata["sha256"] == hashlib.sha256(built.movie).hexdigest()
    assert movie.metadata["serial_offset"] == built.serial_offset
    assert movie.metadata["serial_size"] == built.serial_size
    assert movie.data == built.movie
    assert b"HIDDEN_SOURCE_VALUE" not in movie.data
    assert json.dumps(movie.metadata)
    assert path.read_bytes() == before
    assert list(tmp_path.iterdir()) == [path]
    assert reader.LOADS_RUNTIME is False
    assert reader.WRITES_ASSETS is False
    assert reader.NETWORK_FETCH is False
    assert reader.REDISTRIBUTES_PAYLOAD is False
    assert reader.PRODUCTION_READY is False


def test_api_has_no_output_path():
    assert list(inspect.signature(reader.inspect_menu_package).parameters) == ["path", "decrypt_header"]
    assert list(inspect.signature(reader.read_movie_bytes).parameters) == [
        "path", "exact_export_name", "decrypt_header",
    ]
    source = SCRIPT.read_text(encoding="utf-8")
    for banned in ("subprocess", "urllib", "requests", "CookedPCConsole", "powershell", "D:/Steam", "D:\\Steam"):
        assert banned not in source


def test_utf16_name_and_exact_second_movie(tmp_path):
    built = build_package(movie_name="Menü", utf16_movie_name=True, second_body=b"other-menu")
    path = save(tmp_path, built)
    first = reader.read_movie_bytes(path, "Menü")
    second = reader.read_movie_bytes(path, "OtherMenu")
    assert first.data == built.movie
    assert second.data == built.second_movie
    assert first.data != second.data
    with pytest.raises(reader.PackageReadError, match="not found"):
        reader.read_movie_bytes(path, "Menu")
    with pytest.raises(reader.PackageReadError, match="not found"):
        reader.read_movie_bytes(path, "mainmenu")


def test_licensee32_two_chunk_stride_and_padding(tmp_path):
    built = build_package(licensee=32, tail_plain=b"padding!", after_table=b"\xFF" * 12)
    path = save(tmp_path, built)
    inventory = reader.inspect_menu_package(path)
    movie = reader.read_movie_bytes(path, "MainMenu")
    assert inventory["licensee"] == 32
    assert inventory["chunk_count"] == 2
    assert movie.data == built.movie


def test_licensee34_split_across_two_chunks(tmp_path):
    built = build_package(split_object=True, movie_body=b"span-me")
    path = save(tmp_path, built)
    inventory = reader.inspect_menu_package(path)
    movie = reader.read_movie_bytes(path, "MainMenu")
    assert inventory["chunk_count"] == 2
    assert movie.data == built.movie


def test_block_span_and_selective_inflate(tmp_path):
    spanned = build_package(movie_body=b"B" * 5000, block_size=4096)
    path = save(tmp_path, spanned)
    assert reader.read_movie_bytes(path, "MainMenu").data == spanned.movie

    selected = build_package(bad_leading_block=True, block_size=4096)
    selected_path = save(tmp_path, selected, "selected.upk")
    movie = reader.read_movie_bytes(selected_path, "MainMenu")
    assert movie.data == selected.movie
    assert movie.metadata["serial_offset"] == selected.depends_offset + 4096


def test_measured_and_bounded_block_sizes(tmp_path):
    assert reader.MEASURED_BLOCK_BYTES == MEASURED_BLOCK
    for block_size in (MEASURED_BLOCK, 4 * 1024 * 1024):
        path = save(tmp_path, build_package(block_size=block_size), f"block-{block_size}.upk")
        assert reader.read_movie_bytes(path, "MainMenu").metadata["signature"] == "GFX"
    for block_size in (1024, 6144, 8 * 1024 * 1024):
        path = save(tmp_path, build_package(block_size=block_size), f"bad-{block_size}.upk")
        with pytest.raises(reader.PackageReadError, match="block size"):
            reader.inspect_menu_package(path)


def test_zero_zlib_tail_is_allowed_and_nonzero_is_not(tmp_path):
    allowed = build_package(zlib_suffix=b"\x00\x00")
    path = save(tmp_path, allowed)
    assert reader.read_movie_bytes(path, "MainMenu").data == allowed.movie
    rejected = save(tmp_path, build_package(zlib_suffix=b"\x01"), "nonzero.upk")
    with pytest.raises(reader.PackageReadError, match="zlib"):
        reader.read_movie_bytes(rejected, "MainMenu")


def test_malicious_zlib_output_is_refused(tmp_path):
    framed = frame_blocks(4096, [(zlib.compress(b"A" * 50), 8)])
    built = build_package(frames=[(framed, 8)], serial_size=8)
    path = save(tmp_path, built)
    assert reader.inspect_menu_package(path)["chunk_count"] == 1
    with pytest.raises(reader.PackageReadError, match="zlib"):
        reader.read_movie_bytes(path, "MainMenu")
    short = frame_blocks(4096, [(zlib.compress(b"A" * 40)[:-1], 40)])
    short_path = save(tmp_path, build_package(frames=[(short, 40)], serial_size=40), "short.upk")
    with pytest.raises(reader.PackageReadError, match="zlib"):
        reader.read_movie_bytes(short_path, "MainMenu")


def test_encrypted_callback_and_plaintext_skips_it(tmp_path):
    plain = save(tmp_path, build_package())

    def boom(_data):
        raise AssertionError("plaintext header must not be decrypted")

    assert reader.inspect_menu_package(plain, decrypt_header=boom)["header_decrypted"] is False

    key = b"synthetic-test-key!"
    crypt = xor_crypt(key)
    built = build_package(encrypt=crypt, header_tail=4, folder="HIDDEN_FOLDER_PATH")
    path = save(tmp_path, built, "encrypted.upk")
    seen = {}

    def decrypt(data: bytes) -> bytes:
        seen["length"] = len(data)
        return crypt(data)

    inventory = reader.inspect_menu_package(path, decrypt_header=decrypt)
    movie = reader.read_movie_bytes(path, "MainMenu", decrypt_header=decrypt)
    assert inventory["header_decrypted"] is True
    assert movie.data == built.movie
    assert seen["length"] % 16 == 0
    assert built.name_offset + seen["length"] == built.header_size - 4
    assert built.blob[built.header_size - 4:built.header_size] == b"\xA5" * 4
    with pytest.raises(reader.PackageReadError):
        reader.inspect_menu_package(path)


def test_decrypt_callback_errors(tmp_path):
    crypt = xor_crypt(b"synthetic-test-key!")
    path = save(tmp_path, build_package(encrypt=crypt))
    with pytest.raises(reader.PackageReadError, match="length"):
        reader.inspect_menu_package(path, decrypt_header=lambda data: data[:-1])
    with pytest.raises(reader.PackageReadError, match="shape"):
        reader.inspect_menu_package(path, decrypt_header=lambda _data: "nope")
    with pytest.raises(reader.PackageReadError, match="decrypt callback failed"):
        reader.inspect_menu_package(path, decrypt_header=lambda _data: (_ for _ in ()).throw(RuntimeError("no")))
    with pytest.raises(reader.PackageReadError, match="did not parse"):
        reader.inspect_menu_package(path, decrypt_header=lambda data: data)
    with pytest.raises(reader.PackageReadError, match="callable"):
        reader.inspect_menu_package(path, decrypt_header=b"not-callable")


def test_ctr_flag_is_refused_before_decrypt(tmp_path):
    crypt = xor_crypt(b"synthetic-test-key!")
    path = save(tmp_path, build_package(flags=0x0288028D | 0x800, encrypt=crypt))

    def boom(_data):
        raise AssertionError("CTR packages must be refused before decrypt")

    with pytest.raises(reader.PackageReadError, match="CTR"):
        reader.inspect_menu_package(path, decrypt_header=boom)


def test_version_and_licensee_limits(tmp_path):
    cases = (
        ({"version": 867}, "version"),
        ({"licensee": 33}, "licensee"),
        ({"licensee": 22}, "licensee"),
        ({"licensee": 35}, "licensee"),
    )
    for number, (kwargs, message) in enumerate(cases):
        path = save(tmp_path, build_package(**kwargs), f"variant-{number}.upk")
        with pytest.raises(reader.PackageReadError, match=message):
            reader.inspect_menu_package(path)


def test_nonzero_extension_is_refused(tmp_path):
    path = save(tmp_path, build_package(nonce=b"\x11" * 12))
    with pytest.raises(reader.PackageReadError, match="extension"):
        reader.inspect_menu_package(path)


def test_unaligned_table_and_header_tail(tmp_path):
    rejected = save(tmp_path, build_package(align=False))
    with pytest.raises(reader.PackageReadError, match="decrypted header range"):
        reader.inspect_menu_package(rejected)
    kept = build_package(header_tail=4)
    path = save(tmp_path, kept, "tail.upk")
    assert kept.blob[kept.header_size - 4:kept.header_size] == b"\xA5" * 4
    assert reader.read_movie_bytes(path, "MainMenu").data == kept.movie


def test_property_and_rawdata_refusals(tmp_path):
    cases = (
        ({"unknown_property": True}, "unknown property"),
        ({"duplicate_raw": True}, "duplicate RawData"),
        ({"raw_count": 3}, "RawData"),
        ({"raw_type": "IntProperty"}, "RawData"),
        ({"omit_raw": True}, "RawData"),
        ({"omit_none": True}, "unterminated"),
        ({"signature": b"BAD"}, "signature"),
        ({"declared": 99999}, "movie header"),
        ({"swf_version": 0}, "movie header"),
        ({"class_ref": 0}, "SwfMovie"),
        ({"duplicate_name": True}, "ambiguous"),
    )
    for kwargs, message in cases:
        path = save(tmp_path, build_package(**kwargs), f"{message}.upk".replace(" ", "-"))
        with pytest.raises(reader.PackageReadError, match=message):
            reader.read_movie_bytes(path, "MainMenu")


def test_compressed_swf_signature_is_not_decompressed(tmp_path):
    # Declared uncompressed length may be larger; this reader must not inflate it.
    built = build_package(signature=b"CWS", declared=8 + len(b"wrapped") + 40, movie_body=b"wrapped")
    path = save(tmp_path, built)
    movie = reader.read_movie_bytes(path, "MainMenu")
    assert movie.metadata["signature"] == "CWS"
    assert movie.data[:3] == b"CWS"
    assert movie.data == built.movie


@pytest.mark.parametrize("signature", [b"CWS", b"CFX"])
def test_compressed_swf_may_exceed_uncompressed_length(tmp_path, signature):
    plain = b"\x08\x00\x00\x01\x00\x00"
    compressed = zlib.compress(plain)
    assert len(compressed) > len(plain)
    built = build_package(signature=signature, declared=8 + len(plain), movie_body=compressed)
    path = save(tmp_path, built)
    assert reader.read_movie_bytes(path, "MainMenu").data == built.movie


def test_same_size_in_place_change_is_detected(tmp_path):
    crypt = xor_crypt(b"synthetic-test-key!")
    path = save(tmp_path, build_package(encrypt=crypt))
    original = path.stat()

    def mutate(data):
        with path.open("r+b") as handle:
            handle.seek(-1, os.SEEK_END)
            final = handle.read(1)
            handle.seek(-1, os.SEEK_END)
            handle.write(bytes([final[0] ^ 1]))
        # Make the metadata change deterministic even on coarse filesystems.
        os.utime(path, ns=(original.st_atime_ns, original.st_mtime_ns + 2_000_000_000))
        return crypt(data)

    with pytest.raises(reader.PackageReadError, match="changed"):
        reader.inspect_menu_package(path, decrypt_header=mutate)


def test_fws_length_must_match(tmp_path):
    good = build_package(signature=b"FWS", movie_body=b"plain")
    path = save(tmp_path, good)
    assert reader.read_movie_bytes(path, "MainMenu").metadata["signature"] == "FWS"
    bad = save(tmp_path, build_package(signature=b"FWS", declared=40, movie_body=b"plain"), "bad-fws.upk")
    with pytest.raises(reader.PackageReadError, match="movie header"):
        reader.read_movie_bytes(bad, "MainMenu")


def test_table_corruption_is_refused(tmp_path):
    gap = save(tmp_path, build_package(name_gap=4))
    with pytest.raises(reader.PackageReadError, match="name table"):
        reader.inspect_menu_package(gap)
    ref = save(tmp_path, build_package(bad_name_index=True), "ref.upk")
    with pytest.raises(reader.PackageReadError, match="name reference"):
        reader.inspect_menu_package(ref)
    net = save(tmp_path, build_package(net_count=2), "net.upk")
    assert reader.read_movie_bytes(net, "MainMenu").data == build_package(net_count=2).movie

    built = build_package()
    oversized = bytearray(built.blob)
    struct.pack_into("<I", oversized, built.name_count_at, 65537)
    count_path = tmp_path / "counts.upk"
    count_path.write_bytes(oversized)
    with pytest.raises(reader.PackageReadError, match="name count"):
        reader.inspect_menu_package(count_path)

    chunks = bytearray(built.blob)
    struct.pack_into("<i", chunks, built.depends_offset, 4097)
    chunk_path = tmp_path / "chunks.upk"
    chunk_path.write_bytes(chunks)
    with pytest.raises(reader.PackageReadError, match="chunk count"):
        reader.inspect_menu_package(chunk_path)

    reference = bytearray(built.blob)
    struct.pack_into("<i", reference, built.export_offset, 99)
    ref_path = tmp_path / "object-ref.upk"
    ref_path.write_bytes(reference)
    with pytest.raises(reader.PackageReadError, match="object reference"):
        reader.inspect_menu_package(ref_path)

    huge = bytearray(built.blob)
    struct.pack_into("<i", huge, built.export_offset + 32, 17_000_000)
    huge_path = tmp_path / "huge-export.upk"
    huge_path.write_bytes(huge)
    with pytest.raises(reader.PackageReadError, match="16 MiB"):
        reader.inspect_menu_package(huge_path)

    gapped = save(tmp_path, build_package(logical_gap=1, tail_plain=b"more"), "gap.upk")
    with pytest.raises(reader.PackageReadError, match="contiguous"):
        reader.inspect_menu_package(gapped)
    physical = save(tmp_path, build_package(physical_gap=8, tail_plain=b"more"), "physical.upk")
    with pytest.raises(reader.PackageReadError, match="contiguous"):
        reader.inspect_menu_package(physical)


def test_string_terminators_are_strict(tmp_path):
    samples = (
        struct.pack("<i", 4) + b"ABCD" + struct.pack("<Q", 0),
        struct.pack("<i", 4) + b"A\x00B\x00" + struct.pack("<Q", 0),
        struct.pack("<i", 0) + struct.pack("<Q", 0),
        struct.pack("<i", 1025) + b"A" + struct.pack("<Q", 0),
        struct.pack("<i", -1025) + b"\x00\x00" + struct.pack("<Q", 0),
        struct.pack("<i", -3) + "AbC".encode("utf-16-le") + struct.pack("<Q", 0),
    )
    for number, entry in enumerate(samples):
        path = save(tmp_path, build_package(custom_name_entries=[entry]), f"string-{number}.upk")
        with pytest.raises(reader.PackageReadError, match="string"):
            reader.inspect_menu_package(path)


def test_file_identity_and_ordinary_file_checks(tmp_path):
    path = tmp_path / "big.upk"
    with path.open("wb") as handle:
        handle.seek(64 * 1024 * 1024)
        handle.write(b"\x00")
    with pytest.raises(reader.PackageReadError, match="64 MiB"):
        reader.inspect_menu_package(path)

    header = struct.pack("<IHHI", MAGIC, 868, 34, 4 * 1024 * 1024 + 1)
    capped = tmp_path / "header.upk"
    capped.write_bytes(header + b"\x00" * 16)
    with pytest.raises(reader.PackageReadError, match="4 MiB"):
        reader.inspect_menu_package(capped)

    truncated = tmp_path / "truncated.upk"
    truncated.write_bytes(struct.pack("<IHHI", MAGIC, 868, 34, 1000))
    with pytest.raises(reader.PackageReadError, match="truncated"):
        reader.inspect_menu_package(truncated)

    partial = save(tmp_path, build_package(), "partial.upk")
    partial.write_bytes(partial.read_bytes()[:80])
    with pytest.raises(reader.PackageReadError):
        reader.inspect_menu_package(partial)

    with pytest.raises(reader.PackageReadError, match="regular file"):
        reader.inspect_menu_package(tmp_path)
    with pytest.raises(reader.PackageReadError, match="not readable"):
        reader.inspect_menu_package(tmp_path / "missing.upk")

    crypt = xor_crypt(b"synthetic-test-key!")
    mutable = save(tmp_path, build_package(encrypt=crypt), "mutable.upk")

    def grow(data: bytes) -> bytes:
        with mutable.open("ab") as handle:
            handle.write(b"x")
        return crypt(data)

    with pytest.raises(reader.PackageReadError, match="changed"):
        reader.inspect_menu_package(mutable, decrypt_header=grow)


def test_symlink_is_refused(tmp_path):
    target = tmp_path / "target.upk"
    target.write_bytes(b"not-a-package")
    link = tmp_path / "link.upk"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlink creation is not permitted")
    with pytest.raises(reader.PackageReadError, match="symbolic link"):
        reader.inspect_menu_package(link)


@pytest.mark.skipif(sys.platform != "win32", reason="CNG AES-256-ECB is Windows-only")
def test_cng_nist_aes256_ecb_known_answer():
    key = bytes.fromhex("000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f")
    plain = bytes.fromhex("00112233445566778899aabbccddeeff")
    cipher = bytes.fromhex("8ea2b7ca516745bfeafc49904b496089")
    for _ in range(20):
        assert reader.decrypt_aes256_ecb_cng(cipher, key) == plain
    assert reader.decrypt_aes256_ecb_cng(cipher + cipher, key) == plain + plain


def test_cng_length_bounds_are_portable():
    key = b"\x11" * 32
    with pytest.raises(reader.PackageReadError, match="32-byte"):
        reader.decrypt_aes256_ecb_cng(b"\x00" * 16, b"\x22" * 16)
    with pytest.raises(reader.PackageReadError, match="full block"):
        reader.decrypt_aes256_ecb_cng(b"\x00" * 15, key)
    with pytest.raises(reader.PackageReadError, match="ciphertext"):
        reader.decrypt_aes256_ecb_cng(b"", key)
    with pytest.raises(reader.PackageReadError, match="4 MiB"):
        reader.decrypt_aes256_ecb_cng(b"\x00" * (4 * 1024 * 1024 + 16), key)
    if sys.platform != "win32":
        with pytest.raises(reader.PackageReadError, match="Windows"):
            reader.decrypt_aes256_ecb_cng(b"\x00" * 16, key)
