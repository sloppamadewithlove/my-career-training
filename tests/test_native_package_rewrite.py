"""Synthetic fixtures for the in-memory menu package rewrite.

Packages are packed with struct, including layouts borrowed from the reader
fixtures. These tests do not open an installed game package or write anywhere
except pytest's temporary directory.
"""
from __future__ import annotations

import hashlib
import importlib.util
import inspect
import json
from pathlib import Path
import struct
import sys
from types import SimpleNamespace
import zlib

import pytest


ROOT = Path(__file__).resolve().parents[1]
REWRITE_PATH = ROOT / "scripts" / "native_package_rewrite.py"
READER_PATH = ROOT / "scripts" / "native_package_reader.py"
FIXTURE_PATH = Path(__file__).resolve().parent / "test_native_package_reader.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rewrite = _load(REWRITE_PATH, "native_package_rewrite")
reader = _load(READER_PATH, "native_package_reader_for_rewrite_tests")
fixtures = _load(FIXTURE_PATH, "native_package_reader_fixtures")

MAGIC = 0x9E2A83C1
BLOCK = 131072
FLAGS = 0x0288028D


def test_alias_exports_cannot_amplify_extraction_budget(monkeypatch):
    # Small metadata can alias the same span many times. Refuse before the
    # first allocation/decompression rather than after accumulating buffers.
    package = SimpleNamespace(exports=[
        {"index": index, "serial_offset": 1000, "serial_size": 16 * 1024 * 1024}
        for index in range(5)
    ])

    def must_not_extract(*_args):
        raise AssertionError("budget must be checked before extracting any export")

    monkeypatch.setattr(rewrite.reader, "_extract_serial", must_not_extract)
    with pytest.raises(rewrite.PackageRewriteError, match="aggregate export"):
        rewrite._export_serials(package, 4)


def movie_of(body: bytes, signature: bytes = b"GFX", version: int = 20, declared=None) -> bytes:
    return fixtures.gfx_bytes(body, signature, version, declared)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run(blob: bytes, movie: bytes, source_movie: bytes, export_name: str = "MainMenu", **kwargs):
    return rewrite.replace_final_movie(
        blob,
        movie,
        expected_package_sha256=digest(blob),
        expected_movie_sha256=digest(source_movie),
        export_name=export_name,
        **kwargs,
    )


def save(tmp_path: Path, data: bytes, name: str) -> Path:
    path = tmp_path / name
    path.write_bytes(data)
    return path


def inflate_frame(framed: bytes) -> bytes:
    magic, block_size, _compressed_total, plain_total = struct.unpack_from("<4I", framed)
    assert magic == MAGIC
    assert block_size == BLOCK
    count = (plain_total + block_size - 1) // block_size
    offset = 16
    sizes = []
    for _ in range(count):
        compressed_size, plain_size = struct.unpack_from("<II", framed, offset)
        offset += 8
        sizes.append((compressed_size, plain_size))
    parts = []
    for compressed_size, plain_size in sizes:
        parts.append(zlib.decompress(framed[offset:offset + compressed_size]))
        offset += compressed_size
        assert len(parts[-1]) == plain_size
    assert offset == len(framed)
    assert sum(len(part) for part in parts) == plain_total
    return b"".join(parts)


def plain_header(blob: bytes, header_size: int, name_offset: int, crypt) -> bytes:
    header = bytearray(blob[:header_size])
    if crypt is not None:
        span = ((header_size - name_offset) // 16) * 16
        start = name_offset
        header[start:start + span] = crypt(bytes(header[start:start + span]))
    return bytes(header)


def changed_header_bytes(before: bytes, after: bytes) -> set[int]:
    return {index for index, (left, right) in enumerate(zip(before, after, strict=True)) if left != right}


def assert_only_size_fields_changed(before: bytes, after: bytes, fields: tuple[int, int, int]) -> None:
    allowed = set()
    for field in fields:
        allowed.update(range(field, field + 4))
    changed = changed_header_bytes(before, after)
    assert changed
    assert changed <= allowed


def assert_reader_movie(tmp_path: Path, data: bytes, name: str, export_name: str, expected: bytes, decrypt=None):
    path = save(tmp_path, data, name)
    movie = reader.read_movie_bytes(path, export_name, decrypt_header=decrypt)
    inventory = reader.inspect_menu_package(path, decrypt_header=decrypt)
    assert movie.data == expected
    assert movie.metadata["sha256"] == digest(expected)
    return inventory


def _serial(index, movie: bytes, *, net_index: int, marker: int, bool_byte: int):
    def fn(name: str) -> bytes:
        return fixtures.fname(index[name])

    payload = struct.pack("<i", len(movie)) + movie
    prefix = struct.pack("<i", net_index) + fn("Width") + fn("IntProperty") + struct.pack("<ii", 4, 0)
    prefix += struct.pack("<i", marker) + fn("RawData") + fn("ArrayProperty")
    suffix = fn("Enabled") + fn("BoolProperty") + struct.pack("<ii", 0, 0) + bytes([bool_byte]) + fn("None")
    serial = prefix + struct.pack("<ii", len(payload), 0) + payload + suffix
    return serial, prefix, suffix


def build_shaped(*, movie_body=b"menu", other_body=b"OTHER_EXPORT_BYTES", encrypt=None, header_tail=4,
                 net_count=2, overlap=False, net_index=0x11223344, marker=0x0A0B0C0D, bool_byte=0x5A):
    labels = (
        "None", "Class", "Core", "SwfMovie", "OtherMenu", "MainMenu", "Width", "IntProperty",
        "Enabled", "BoolProperty", "RawData", "ArrayProperty",
    )
    index = {label: position for position, label in enumerate(labels)}
    movie = movie_of(movie_body)
    other_movie = movie_of(other_body, b"FWS")
    movie_serial, prefix, suffix = _serial(index, movie, net_index=net_index, marker=marker, bool_byte=bool_byte)
    other_serial, _other_prefix, _other_suffix = _serial(
        index, other_movie, net_index=7, marker=9, bool_byte=0x3C,
    )
    folder = fixtures.fstr_ansi("HIDDEN_FOLDER_PATH")
    names = b"".join(fixtures.name_entry(label) for label in labels)
    imports = fixtures.fname(index["Core"]) + fixtures.fname(index["Class"]) + struct.pack("<i", 0)
    imports += fixtures.fname(index["SwfMovie"])
    if overlap:
        objects = (movie_serial,)
        export_plan = (
            (index["MainMenu"], len(movie_serial), 0, net_count),
            (index["OtherMenu"], len(movie_serial), 0, 0),
        )
    else:
        objects = (other_serial, movie_serial)
        export_plan = (
            (index["OtherMenu"], len(other_serial), 0, 0),
            (index["MainMenu"], len(movie_serial), len(other_serial), net_count),
        )
    export_len = sum(72 + nets * 4 for _name, _size, _skip, nets in export_plan)
    name_offset = 12 + len(folder) + 32
    import_offset = name_offset + len(names)
    export_offset = import_offset + len(imports)
    depends_offset = export_offset + export_len
    frames = [(fixtures.frame_plain(plain, 4096), len(plain)) for plain in objects]
    table_len = 4 + len(frames) * 36
    table_end = depends_offset + table_len
    pad = (16 - ((table_end - name_offset) % 16)) % 16
    header_size = table_end + pad + header_tail

    logical = depends_offset
    physical = header_size
    records = []
    for framed, plain_size in frames:
        records.append((logical, plain_size, physical, len(framed)))
        logical += plain_size
        physical += len(framed)
    compression = struct.pack("<i", len(records))
    for record in records:
        compression += struct.pack("<qiqi", *record) + b"\x00" * 12
    summary = struct.pack("<IHHI", MAGIC, 868, 34, header_size) + folder
    summary += struct.pack(
        "<8I", FLAGS, len(labels), name_offset, len(export_plan), export_offset, 1, import_offset, depends_offset,
    )
    exports = b""
    for name_index, size, skip, nets in export_plan:
        exports += fixtures._export_bytes(-1, name_index, size, depends_offset + skip, nets)
    header = bytearray(header_size)
    cursor = 0
    for piece in (summary, names, imports, exports, compression):
        header[cursor:cursor + len(piece)] = piece
        cursor += len(piece)
    if cursor != table_end or len(summary) != name_offset or len(compression) != table_len:
        raise RuntimeError("shaped package fixture drifted")
    if header_tail:
        header[-header_tail:] = b"\xA5" * header_tail
    if encrypt is not None:
        span = ((header_size - name_offset) // 16) * 16
        start = name_offset
        header[start:start + span] = encrypt(bytes(header[start:start + span]))
    blob = bytes(header) + b"".join(framed for framed, _plain in frames)
    serial_at = export_offset + (0 if overlap else 72) + 32
    chunk_index = 0 if overlap else 1
    usize_at = depends_offset + 4 + chunk_index * 36 + 8
    csize_at = depends_offset + 4 + chunk_index * 36 + 20
    return type("Shaped", (), {
        "blob": blob,
        "movie": movie,
        "movie_name": "MainMenu",
        "other_movie": other_movie,
        "other_serial": other_serial,
        "movie_serial": movie_serial,
        "prefix": prefix,
        "suffix": suffix,
        "header_size": header_size,
        "name_offset": name_offset,
        "export_offset": export_offset,
        "depends_offset": depends_offset,
        "serial_offset": depends_offset + (0 if overlap else len(other_serial)),
        "serial_size": len(movie_serial),
        "chunk0": records[0],
        "fields": (serial_at, usize_at, csize_at),
        "net_index": net_index,
        "marker": marker,
        "bool_byte": bool_byte,
        "overlap": overlap,
    })()


def test_plaintext_grow_shrink_and_second_pass(tmp_path):
    built = fixtures.build_package(
        folder="HIDDEN_FOLDER_PATH", header_tail=4, net_count=2, block_size=4096,
    )

    def boom(_data):
        raise AssertionError("plaintext header must not be encrypted or decrypted")

    grown_movie = movie_of(b"G" * 140000)
    grown = run(built.blob, grown_movie, built.movie, decrypt_header=boom)
    assert grown.metadata["after_package_length"] > grown.metadata["before_package_length"]
    assert grown.metadata["after_serial_size"] > grown.metadata["before_serial_size"]
    assert grown.metadata["after_movie_sha256"] == digest(grown_movie)
    assert grown.metadata["writes_files"] is False
    _assert_simple_shape(tmp_path, built, grown, grown_movie, crypt=None, name="grown.upk")

    large = fixtures.build_package(movie_body=b"S" * 140000, header_tail=4, net_count=2)
    shrunk_movie = movie_of(b"")
    shrunk = run(large.blob, shrunk_movie, large.movie)
    assert shrunk.metadata["after_package_length"] < shrunk.metadata["before_package_length"]
    assert shrunk.metadata["after_movie_length"] == 8
    _assert_simple_shape(tmp_path, large, shrunk, shrunk_movie, crypt=None, name="shrunk.upk")

    again_movie = movie_of(b"second-pass")
    again = run(grown.data, again_movie, grown_movie)
    inventory = assert_reader_movie(tmp_path, again.data, "again.upk", "MainMenu", again_movie)
    assert inventory["header_size"] == built.header_size
    assert inventory["exports"][0]["serial_offset"] == built.serial_offset
    assert b"HIDDEN_SOURCE_VALUE" in inflate_frame(again.data[built.header_size:])
    assert grown_movie not in inflate_frame(again.data[built.header_size:])


def test_encrypted_xor_grow_shrink_preserves_tail(tmp_path):
    crypt = fixtures.xor_crypt(b"synthetic-test-key!")
    built = fixtures.build_package(encrypt=crypt, header_tail=4, net_count=2, folder="HIDDEN_FOLDER_PATH")
    seen = {"encrypt": 0, "decrypt": 0}

    def decrypt(data: bytes) -> bytes:
        seen["decrypt"] += 1
        return crypt(data)

    def encrypt(data: bytes) -> bytes:
        seen["encrypt"] += 1
        return crypt(data)

    replacement = movie_of(b"E" * 500)
    result = run(built.blob, replacement, built.movie, decrypt_header=decrypt, encrypt_header=encrypt)
    assert seen["encrypt"] == 1
    assert seen["decrypt"] == 3
    assert result.data[built.header_size - 4:built.header_size] == b"\xA5" * 4
    assert result.data[:built.name_offset] == built.blob[:built.name_offset]
    _assert_simple_shape(tmp_path, built, result, replacement, crypt=crypt, name="encrypted.upk")

    small = fixtures.build_package(
        encrypt=crypt, header_tail=4, movie_body=b"S" * 20000, signature=b"FWS",
    )
    tiny = movie_of(b"z", signature=b"GFX")
    shrunk = run(small.blob, tiny, small.movie, decrypt_header=crypt, encrypt_header=crypt)
    assert shrunk.metadata["after_movie_length"] < shrunk.metadata["before_movie_length"]
    assert shrunk.data[small.header_size - 4:small.header_size] == b"\xA5" * 4
    inventory = assert_reader_movie(tmp_path, shrunk.data, "enc-small.upk", "MainMenu", tiny, crypt)
    assert inventory["header_decrypted"] is True
    assert inventory["header_size"] == small.header_size


def test_prior_export_chunk_and_tail_byte_stay(tmp_path):
    crypt = fixtures.xor_crypt(b"synthetic-test-key!")
    for number, encrypt in enumerate((None, crypt)):
        built = build_shaped(encrypt=encrypt, movie_body=b"menu", other_body=b"OTHER_EXPORT_BYTES")
        replacement = movie_of(b"R" * 180000)
        kwargs = {}
        if encrypt is not None:
            kwargs = {"decrypt_header": encrypt, "encrypt_header": encrypt}
        result = run(built.blob, replacement, built.movie, **kwargs)
        before = plain_header(built.blob, built.header_size, built.name_offset, encrypt)
        after = plain_header(result.data, built.header_size, built.name_offset, encrypt)
        for field in built.fields:
            assert struct.unpack_from("<i", before, field)[0] in {built.serial_size, len(built.blob) - records_end(built)}
        assert_only_size_fields_changed(before, after, built.fields)
        _uoff, usize, coff, csize = built.chunk0
        assert result.data[coff:coff + csize] == built.blob[coff:coff + csize]
        assert result.data[built.header_size - 4:built.header_size] == b"\xA5" * 4
        assert result.data[:built.name_offset] == built.blob[:built.name_offset]

        inventory = assert_reader_movie(
            tmp_path, result.data, f"prior-{number}.upk", "MainMenu", replacement, encrypt,
        )
        other = reader.read_movie_bytes(save(tmp_path, result.data, f"prior-src-{number}.upk"), "OtherMenu", encrypt)
        assert other.data == built.other_movie
        assert inventory["chunks"][0]["compressed_offset"] == built.chunk0[2]
        assert inventory["chunks"][0]["compressed_size"] == built.chunk0[3]
        assert inventory["exports"][1]["serial_offset"] == built.serial_offset
        assert inventory["header_size"] == built.header_size
        last = inventory["chunks"][-1]
        framed = result.data[last["compressed_offset"]:last["compressed_offset"] + last["compressed_size"]]
        plain = inflate_frame(framed)
        assert plain.startswith(built.prefix)
        assert plain.endswith(built.suffix)
        assert bytes([built.bool_byte]) in built.suffix
        body = plain[len(built.prefix):-len(built.suffix)]
        length, array_index, count = struct.unpack_from("<iii", body)
        assert array_index == 0
        assert count == len(replacement)
        assert length == 4 + len(replacement)
        assert body[12:] == replacement
        assert struct.unpack_from("<i", plain)[0] == built.net_index
        assert struct.pack("<i", built.marker) in plain[:len(built.prefix)]
        encoded = json.dumps(result.metadata)
        assert "HIDDEN_FOLDER_PATH" not in encoded
        assert "OTHER_EXPORT_BYTES" not in encoded


def records_end(built) -> int:
    return built.chunk0[2] + built.chunk0[3]


def test_source_hash_must_match():
    built = fixtures.build_package()
    movie = movie_of(b"next")
    package_hash = digest(built.blob)
    movie_hash = digest(built.movie)
    with pytest.raises(rewrite.PackageRewriteError, match="package SHA-256 does not match"):
        rewrite.replace_final_movie(
            built.blob, movie, expected_package_sha256="ab" * 32,
            expected_movie_sha256=movie_hash, export_name="MainMenu",
        )
    with pytest.raises(rewrite.PackageRewriteError, match="movie SHA-256 does not match"):
        rewrite.replace_final_movie(
            built.blob, movie, expected_package_sha256=package_hash,
            expected_movie_sha256="cd" * 32, export_name="MainMenu",
        )
    with pytest.raises(rewrite.PackageRewriteError, match="lowercase"):
        rewrite.replace_final_movie(
            built.blob, movie, expected_package_sha256=package_hash.upper(),
            expected_movie_sha256=movie_hash, export_name="MainMenu",
        )
    for bad in ("ab" * 31, "ab" * 33, "zz" * 32, "", None, b"ab" * 32):
        with pytest.raises(rewrite.PackageRewriteError, match="lowercase"):
            rewrite.replace_final_movie(
                built.blob, movie, expected_package_sha256=bad,
                expected_movie_sha256=movie_hash, export_name="MainMenu",
            )


def test_selected_export_must_fill_the_last_chunk():
    trailing = fixtures.build_package(tail_plain=b"TAILBYTES")
    shared = fixtures.build_package(second_body=b"other-menu")
    for built in (trailing, shared):
        with pytest.raises(rewrite.PackageRewriteError, match="entire last chunk"):
            run(built.blob, movie_of(b"next"), built.movie)


def test_overlapping_export_is_refused(tmp_path):
    built = build_shaped(overlap=True)
    path = save(tmp_path, built.blob, "overlap.upk")
    assert reader.read_movie_bytes(path, "MainMenu").data == built.movie
    with pytest.raises(rewrite.PackageRewriteError, match="overlaps the selected export"):
        run(built.blob, movie_of(b"next"), built.movie)


def test_reader_refusals():
    cases = (
        (fixtures.build_package(class_ref=0), "SwfMovie"),
        (fixtures.build_package(duplicate_raw=True), "duplicate RawData"),
        (fixtures.build_package(version=867), "version"),
        (fixtures.build_package(licensee=32), "licensee 34"),
        (fixtures.build_package(licensee=35), "licensee"),
        (fixtures.build_package(nonce=b"\x11" * 12), "extension"),
        (fixtures.build_package(duplicate_name=True), "ambiguous"),
    )
    for built, message in cases:
        with pytest.raises(rewrite.PackageRewriteError, match=message):
            run(built.blob, movie_of(b"next"), built.movie)

    crypt = fixtures.xor_crypt(b"synthetic-test-key!")
    ctr = fixtures.build_package(flags=FLAGS | 0x800, encrypt=crypt)

    def boom(_data):
        raise AssertionError("CTR packages must be refused before decrypt")

    with pytest.raises(rewrite.PackageRewriteError, match="CTR"):
        run(ctr.blob, movie_of(b"next"), ctr.movie, decrypt_header=boom)

    malformed = bytearray(fixtures.build_package().blob)
    header_size = fixtures.build_package().header_size
    malformed[header_size] ^= 0xFF
    with pytest.raises(rewrite.PackageRewriteError, match="chunk magic"):
        run(bytes(malformed), movie_of(b"next"), fixtures.build_package().movie)

    framed = fixtures.frame_blocks(4096, [(b"\x02" * 16, 8)])
    bad_zlib = fixtures.build_package(frames=[(framed, 8)], serial_size=8)
    with pytest.raises(rewrite.PackageRewriteError, match="zlib"):
        run(bad_zlib.blob, movie_of(b"next"), bad_zlib.movie)


def test_encrypt_callback_contracts():
    crypt = fixtures.xor_crypt(b"synthetic-test-key!")
    built = fixtures.build_package(encrypt=crypt, header_tail=4)
    movie = movie_of(b"next")

    def refuse(callback_encrypt, message):
        with pytest.raises(rewrite.PackageRewriteError, match=message):
            run(built.blob, movie, built.movie, decrypt_header=crypt, encrypt_header=callback_encrypt)

    refuse(lambda data: data[:-1], "length")
    refuse(lambda data: data + b"\x00", "length")
    refuse(lambda _data: "nope", "shape")
    refuse(lambda data: b"\x00" * len(data), "round-trip")
    refuse(None, "encrypt_header")

    def crash(_data):
        raise RuntimeError("no")

    refuse(crash, "encrypt callback failed")

    plain = fixtures.build_package()
    with pytest.raises(rewrite.PackageRewriteError, match="plaintext header does not use encrypt_header"):
        run(plain.blob, movie, plain.movie, encrypt_header=crypt)
    with pytest.raises(rewrite.PackageRewriteError, match="callable"):
        run(plain.blob, movie, plain.movie, decrypt_header=b"not-callable")


def test_replacement_movie_must_be_uncompressed_same_version(tmp_path):
    gfx = fixtures.build_package(signature=b"GFX", swf_version=21, movie_body=b"menu")
    fws = fixtures.build_package(signature=b"FWS", movie_body=b"plain")
    cws = fixtures.build_package(signature=b"CWS", declared=40, movie_body=b"wrapped")
    gfx_next = movie_of(b"gfx-next", version=21)
    fws_next = movie_of(b"fws-next", b"FWS")
    from_cws = movie_of(b"from-cws")
    assert_reader_movie(tmp_path, run(gfx.blob, gfx_next, gfx.movie).data, "gfx.upk", "MainMenu", gfx_next)
    assert_reader_movie(tmp_path, run(fws.blob, fws_next, fws.movie).data, "fws.upk", "MainMenu", fws_next)
    assert_reader_movie(tmp_path, run(cws.blob, from_cws, cws.movie).data, "cws.upk", "MainMenu", from_cws)

    with pytest.raises(rewrite.PackageRewriteError, match="SWF version"):
        run(gfx.blob, movie_of(b"other-version", version=20), gfx.movie)
    with pytest.raises(rewrite.PackageRewriteError, match="GFX or FWS"):
        run(gfx.blob, movie_of(b"wrapped", b"CWS", 21, 40), gfx.movie)
    with pytest.raises(rewrite.PackageRewriteError, match="does not match its bytes"):
        run(gfx.blob, movie_of(b"abc", version=21, declared=50), gfx.movie)
    with pytest.raises(rewrite.PackageRewriteError, match="8 bytes"):
        run(gfx.blob, b"GFX\x15\x00\x00", gfx.movie)


def test_size_caps():
    blob = b"\x00" * (64 * 1024 * 1024 + 1)
    with pytest.raises(rewrite.PackageRewriteError, match="64 MiB"):
        rewrite.replace_final_movie(
            blob, movie_of(b"menu"), expected_package_sha256="ab" * 32,
            expected_movie_sha256="cd" * 32, export_name="MainMenu",
        )
    built = fixtures.build_package()
    huge = b"G" * (16 * 1024 * 1024 + 1)
    with pytest.raises(rewrite.PackageRewriteError, match="16 MiB"):
        run(built.blob, huge, built.movie)
    exact = movie_of(b"\x00" * (16 * 1024 * 1024 - 8))
    assert len(exact) == 16 * 1024 * 1024
    with pytest.raises(rewrite.PackageRewriteError, match="16 MiB"):
        run(built.blob, exact, built.movie)
    with pytest.raises(rewrite.PackageRewriteError, match="package must be bytes"):
        rewrite.replace_final_movie(
            "nope", movie_of(b"menu"), expected_package_sha256="ab" * 32,
            expected_movie_sha256="cd" * 32, export_name="MainMenu",
        )


def test_api_is_in_memory_and_gates_are_false(tmp_path):
    params = inspect.signature(rewrite.replace_final_movie).parameters
    assert list(params) == [
        "package_bytes", "replacement_movie", "expected_package_sha256", "expected_movie_sha256",
        "export_name", "decrypt_header", "encrypt_header",
    ]
    assert params["expected_package_sha256"].kind is inspect.Parameter.KEYWORD_ONLY
    assert "path" not in params
    source = REWRITE_PATH.read_text(encoding="utf-8")
    for banned in ("subprocess", "urllib", "requests", "CookedPCConsole", "powershell", "D:/Steam", "D:\\Steam", "open(", "__main__"):
        assert banned not in source
    built = fixtures.build_package(folder="HIDDEN_FOLDER_PATH")
    before = list(tmp_path.iterdir())
    result = run(built.blob, movie_of(b"idle"), built.movie)
    assert list(tmp_path.iterdir()) == before
    assert isinstance(result.data, bytes)
    assert not hasattr(result, "save")
    assert result.metadata["runtime_verified"] is False
    assert result.metadata["production_ready"] is False
    assert result.metadata["writes_files"] is False
    assert result.metadata["swf_tags_validated"] is False
    assert json.dumps(result.metadata)
    assert "HIDDEN" not in json.dumps(result.metadata)
    flags = rewrite.capabilities()
    assert flags == {key: False for key in flags}
    assert rewrite.RUNTIME_VERIFIED is False
    assert rewrite.PRODUCTION_READY is False
    assert rewrite.WRITES_FILES is False
    assert rewrite.LOADS_RUNTIME is False
    assert rewrite.NETWORK_FETCH is False
    assert rewrite.REDISTRIBUTES_PAYLOAD is False
    assert rewrite.SWF_TAGS_VALIDATED is False


@pytest.mark.skipif(sys.platform != "win32", reason="CNG AES-256-ECB is Windows-only")
def test_cng_nist_aes256_ecb_encrypt_known_answer():
    key = bytes.fromhex("000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f")
    plain = bytes.fromhex("00112233445566778899aabbccddeeff")
    cipher = bytes.fromhex("8ea2b7ca516745bfeafc49904b496089")
    for _ in range(20):
        assert rewrite.encrypt_aes256_ecb_cng(plain, key) == cipher
        assert rewrite.encrypt_aes256_ecb_cng(bytearray(plain), bytearray(key)) == cipher
    assert rewrite.encrypt_aes256_ecb_cng(plain + plain, key) == cipher + cipher
    assert reader.decrypt_aes256_ecb_cng(rewrite.encrypt_aes256_ecb_cng(plain, key), key) == plain


def test_cng_encrypt_bounds_are_portable():
    key = b"\x11" * 32
    with pytest.raises(rewrite.PackageRewriteError, match="32-byte"):
        rewrite.encrypt_aes256_ecb_cng(b"\x00" * 16, b"\x22" * 16)
    with pytest.raises(rewrite.PackageRewriteError, match="full block"):
        rewrite.encrypt_aes256_ecb_cng(b"\x00" * 15, key)
    with pytest.raises(rewrite.PackageRewriteError, match="plaintext"):
        rewrite.encrypt_aes256_ecb_cng(b"", key)
    with pytest.raises(rewrite.PackageRewriteError, match="4 MiB"):
        rewrite.encrypt_aes256_ecb_cng(b"\x00" * (4 * 1024 * 1024 + 16), key)
    if sys.platform != "win32":
        with pytest.raises(rewrite.PackageRewriteError, match="Windows"):
            rewrite.encrypt_aes256_ecb_cng(b"\x00" * 16, key)


def _assert_simple_shape(tmp_path, built, result, replacement, crypt, name):
    before = plain_header(built.blob, built.header_size, built.name_offset, crypt)
    after = plain_header(result.data, built.header_size, built.name_offset, crypt)
    serial_at = built.export_offset + 32
    usize_at = built.depends_offset + 4 + 8
    csize_at = built.depends_offset + 4 + 20
    assert struct.unpack_from("<i", before, serial_at)[0] == built.serial_size
    assert struct.unpack_from("<i", before, usize_at)[0] == built.serial_size
    assert struct.unpack_from("<i", before, csize_at)[0] == len(built.blob) - built.header_size
    assert_only_size_fields_changed(before, after, (serial_at, usize_at, csize_at))
    assert result.data[:built.name_offset] == built.blob[:built.name_offset]
    assert result.data[built.header_size - 4:built.header_size] == b"\xA5" * 4
    inventory = assert_reader_movie(tmp_path, result.data, name, "MainMenu", replacement, crypt)
    assert inventory["version"] == 868
    assert inventory["licensee"] == 34
    assert inventory["header_size"] == built.header_size
    assert inventory["exports"][0]["serial_offset"] == built.serial_offset
    assert inventory["exports"][0]["serial_size"] == result.metadata["after_serial_size"]
    assert inventory["chunks"][0]["compressed_offset"] == built.header_size
    assert inventory["chunks"][0]["uncompressed_offset"] == built.depends_offset
    assert inventory["chunks"][0]["uncompressed_size"] == inventory["exports"][0]["serial_size"]
    assert inventory["file_size"] == len(result.data)
    chunk = inventory["chunks"][0]
    framed = result.data[chunk["compressed_offset"]:chunk["compressed_offset"] + chunk["compressed_size"]]
    plain = inflate_frame(framed)
    assert replacement in plain
    assert built.movie not in plain
    assert b"HIDDEN_SOURCE_VALUE" in plain
    assert "HIDDEN_SOURCE_VALUE" not in json.dumps(result.metadata)
    assert "HIDDEN_FOLDER_PATH" not in json.dumps(result.metadata)
    assert result.metadata["before_package_sha256"] == digest(built.blob)
    assert result.metadata["after_package_sha256"] == digest(result.data)
    assert result.metadata["runtime_verified"] is False
    assert result.metadata["production_ready"] is False
    assert result.metadata["writes_files"] is False
