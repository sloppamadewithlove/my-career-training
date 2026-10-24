"""In-memory development rewrite for one menu package.

``replace_final_movie`` returns new package bytes. It does not open a path,
write a file, fetch a key, launch a game, or install anything. The edit is a
container change of the selected ``SwfMovie`` RawData when that export is the
entire final chunk. SWF tags, ABC, and menu behavior are not validated.
Runtime compatibility is unproven.

Parsing is delegated to ``native_package_reader``. This module calls that
file's private summary, table, frame, export, and RawData functions. It does
not copy the parser. A change to those private functions can break this file.
"""
from __future__ import annotations

import hashlib
import importlib.util
import struct
import sys
import zlib
from pathlib import Path


def _load_reader():
    path = Path(__file__).with_name("native_package_reader.py")
    spec = importlib.util.spec_from_file_location("_native_package_reader_for_rewrite", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load native package reader from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


reader = _load_reader()

BLOCK_BYTES = 131072
MAX_RETAINED_EXPORT_BYTES = 64 * 1024 * 1024
LICENSEE = 34
_HEX = frozenset("0123456789abcdef")
_UNCOMPRESSED_SWF = frozenset({b"FWS", b"GFX"})

RUNTIME_VERIFIED = False
PRODUCTION_READY = False
WRITES_FILES = False
LOADS_RUNTIME = False
NETWORK_FETCH = False
REDISTRIBUTES_PAYLOAD = False
SWF_TAGS_VALIDATED = False


class PackageRewriteError(ValueError):
    """The package cannot be rewritten in the one supported container shape."""


class RewrittenPackage:
    """In-memory package bytes plus a small JSON-serializable metadata dict.

    ``data`` is the rewritten package. This object has no save method.
    """

    __slots__ = ("data", "metadata")

    def __init__(self, data: bytes, metadata: dict):
        self.data = bytes(data)
        self.metadata = dict(metadata)

    def __repr__(self) -> str:
        meta = self.metadata
        return (
            f"RewrittenPackage(export_name={meta.get('export_name')!r}, "
            f"after_package_length={meta.get('after_package_length')!r})"
        )


def capabilities() -> dict:
    """Fresh dictionary. Every production capability stays false."""
    return {
        "loads_runtime": LOADS_RUNTIME,
        "runtime_verified": RUNTIME_VERIFIED,
        "writes_files": WRITES_FILES,
        "network_fetch": NETWORK_FETCH,
        "redistribute_payload": REDISTRIBUTES_PAYLOAD,
        "production_ready": PRODUCTION_READY,
        "swf_tags_validated": SWF_TAGS_VALIDATED,
    }


def replace_final_movie(
    package_bytes,
    replacement_movie,
    *,
    expected_package_sha256,
    expected_movie_sha256,
    export_name,
    decrypt_header=None,
    encrypt_header=None,
) -> RewrittenPackage:
    """Replace one final-chunk SwfMovie RawData and return the new package.

    Both digests are lowercase SHA-256 hex of the source package and of its
    current RawData. The source must already satisfy the reader. Licensee 34,
    version 868, a zero 12-byte chunk extension, and no full-CTR flag are
    required. The named export must be the only ``SwfMovie`` of that name and
    must occupy the entire last chunk. Other export spans stay put.

    ``decrypt_header`` and ``encrypt_header`` are required together when the
    reader had to decrypt the header. A plaintext header does not use them.
    """
    try:
        return _replace_final_movie(
            package_bytes,
            replacement_movie,
            expected_package_sha256=expected_package_sha256,
            expected_movie_sha256=expected_movie_sha256,
            export_name=export_name,
            decrypt_header=decrypt_header,
            encrypt_header=encrypt_header,
        )
    except PackageRewriteError:
        raise
    except reader.PackageReadError as exc:
        raise PackageRewriteError(str(exc)) from exc


def encrypt_aes256_ecb_cng(plaintext: bytes, key: bytes) -> bytes:
    """Encrypt one AES-256-ECB buffer with Windows CNG and an explicit key.

    The key is not stored, searched for, or fetched. Plaintext must be a
    positive multiple of 16 bytes and at most the header cap. No padding is
    applied. This helper is optional. ``replace_final_movie`` does not call it.
    """
    if isinstance(key, bytearray):
        key = bytes(key)
    if not isinstance(key, bytes) or len(key) != 32:
        raise PackageRewriteError("AES-256-ECB requires an explicit 32-byte key")
    if isinstance(plaintext, bytearray):
        plaintext = bytes(plaintext)
    if not isinstance(plaintext, bytes) or not plaintext:
        raise PackageRewriteError("AES-256-ECB plaintext must be non-empty bytes")
    if len(plaintext) % reader.AES_BLOCK != 0:
        raise PackageRewriteError("AES-256-ECB plaintext length is not a full block")
    if len(plaintext) > reader.MAX_HEADER_BYTES:
        raise PackageRewriteError("AES-256-ECB plaintext exceeds the 4 MiB cap")
    if sys.platform != "win32":
        raise PackageRewriteError("CNG AES-256-ECB is only available on Windows")
    return _cng_encrypt(plaintext, key)


def _replace_final_movie(
    package_bytes,
    replacement_movie,
    *,
    expected_package_sha256,
    expected_movie_sha256,
    export_name,
    decrypt_header,
    encrypt_header,
) -> RewrittenPackage:
    package_digest = _require_sha256(expected_package_sha256, "package SHA-256")
    movie_digest = _require_sha256(expected_movie_sha256, "movie SHA-256")
    _require_callback(decrypt_header, "decrypt_header")
    _require_callback(encrypt_header, "encrypt_header")
    if not isinstance(export_name, str):
        raise PackageRewriteError("export name must be a string")
    source = _as_bytes(package_bytes, "package")
    replacement = _as_bytes(replacement_movie, "replacement movie")
    if len(source) < 12:
        raise PackageRewriteError("package is truncated")
    if len(source) > reader.MAX_FILE_BYTES:
        raise PackageRewriteError("package exceeds the 64 MiB cap")
    if len(replacement) < 8 or len(replacement) > reader.MAX_EXPORT_BYTES:
        raise PackageRewriteError("replacement movie length is outside 8 bytes..16 MiB")
    actual_package = hashlib.sha256(source).hexdigest()
    if actual_package != package_digest:
        raise PackageRewriteError("package SHA-256 does not match")

    summary, package = _load_package(source, decrypt_header)
    if summary.version != reader.SUPPORTED_VERSION:
        raise PackageRewriteError("rewrite only supports package version 868")
    if summary.licensee != LICENSEE:
        raise PackageRewriteError("rewrite only supports licensee 34")
    if summary.flags & reader.CTR_FLAG:
        raise PackageRewriteError("full CTR packages are not supported")
    if reader.MEASURED_BLOCK_BYTES != BLOCK_BYTES:
        raise PackageRewriteError("rewrite compresses 131072-byte blocks")

    export = reader._select_export(package, export_name)
    last = _require_last_chunk(package, export)
    _reject_logical_overlap(package.exports, export)
    serials = _export_serials(package, export["index"])
    serial = serials[export["index"]]
    parsed = reader._parse_swf_movie(serial, export, package.names)
    if hashlib.sha256(parsed.data).hexdigest() != movie_digest:
        raise PackageRewriteError("movie SHA-256 does not match")
    _require_replacement(replacement, parsed.data)

    span = _rawdata_span(serial, package.names, parsed.data)
    new_serial = _splice_rawdata(serial, span, replacement)
    if len(new_serial) > reader.MAX_EXPORT_BYTES or len(new_serial) > reader.MAX_CHUNK_BYTES:
        raise PackageRewriteError("export serial size exceeds 16 MiB")
    _require_logical_fit(last.uncompressed_offset, len(new_serial))
    probe = {
        "name": export["name"],
        "class": export["class"],
        "serial_offset": export["serial_offset"],
        "serial_size": len(new_serial),
    }
    rewritten = reader._parse_swf_movie(new_serial, probe, package.names)
    if rewritten.data != replacement:
        raise PackageRewriteError("rewritten serial did not contain the replacement movie")

    framed = _frame_serial(new_serial)
    if last.compressed_offset > reader.MAX_FILE_BYTES or len(framed) > reader.MAX_FILE_BYTES - last.compressed_offset:
        raise PackageRewriteError("package exceeds the 64 MiB cap")

    plain_header = bytearray(package.header)
    fields = _patch_sizes(plain_header, summary, package, export, len(new_serial), len(framed))
    _reject_header_overlap(package.exports, export["index"], summary.depends_offset, fields)
    _only_these_bytes_changed(bytes(package.header), bytes(plain_header), fields)

    final_header = _seal_header(
        plain_header, summary, package.header_decrypted, decrypt_header, encrypt_header, source,
    )
    if len(final_header) != summary.header_size or last.compressed_offset < summary.header_size:
        raise PackageRewriteError("rewrite changed the header length")
    produced = bytearray(source[:last.compressed_offset])
    produced[:summary.header_size] = final_header
    produced.extend(framed)
    output = bytes(produced)
    _assert_reparsed(
        source, output, summary, package, export, serials, replacement, new_serial, framed,
        bytes(plain_header), decrypt_header,
    )
    metadata = _metadata(export_name, source, output, parsed.data, replacement, serial, new_serial)
    return RewrittenPackage(output, metadata)


def _require_sha256(value, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(char not in _HEX for char in value):
        raise PackageRewriteError(f"{label} must be a lowercase SHA-256 hex digest")
    return value


def _require_callback(callback, label: str) -> None:
    if callback is not None and not callable(callback):
        raise PackageRewriteError(f"{label} must be callable")


def _as_bytes(value, label: str) -> bytes:
    if isinstance(value, bytearray):
        return bytes(value)
    if not isinstance(value, bytes):
        raise PackageRewriteError(f"{label} must be bytes")
    return value


def _bind_read(data: bytes):
    file_len = len(data)

    def read_at(offset: int, size: int) -> bytes:
        if size < 0 or offset < 0 or offset > file_len or size > file_len - offset:
            raise reader.PackageReadError("read is outside the package")
        return data[offset:offset + size]

    return read_at


def _load_package(data: bytes, decrypt_header):
    read_at = _bind_read(data)
    summary = reader._parse_summary(read_at(0, 12), read_at, len(data))
    package = reader._decode_header(summary, read_at, decrypt_header, len(data))
    reader._validate_frames(package, read_at)
    package.read_at = read_at
    return summary, package


def _require_last_chunk(package, export):
    last = package.chunks[-1]
    same_span = (
        export["serial_offset"] == last.uncompressed_offset
        and export["serial_size"] == last.uncompressed_size
    )
    if not same_span:
        raise PackageRewriteError("selected export must occupy the entire last chunk")
    ends_at_eof = last.compressed_offset + last.compressed_size == package.file_size
    if not ends_at_eof or last.compressed_offset < package.header_size:
        raise PackageRewriteError("last chunk must end at EOF")
    return last


def _spans_overlap(start: int, end: int, other_start: int, other_end: int) -> bool:
    return start < other_end and other_start < end


def _reject_logical_overlap(exports, selected) -> None:
    start = selected["serial_offset"]
    end = start + selected["serial_size"]
    for export in exports:
        if export["index"] == selected["index"] or export["serial_size"] <= 0:
            continue
        other_start = export["serial_offset"]
        other_end = other_start + export["serial_size"]
        if _spans_overlap(start, end, other_start, other_end):
            raise PackageRewriteError("another export overlaps the selected export")


def _reject_header_overlap(exports, selected_index: int, depends_offset: int, fields) -> None:
    ranges = [(field, field + 4) for field in fields]
    for export in exports:
        if export["index"] == selected_index or export["serial_size"] <= 0:
            continue
        start = export["serial_offset"]
        if start >= depends_offset:
            continue
        physical_end = min(start + export["serial_size"], depends_offset)
        for field_start, field_end in ranges:
            if _spans_overlap(start, physical_end, field_start, field_end):
                raise PackageRewriteError("another export overlaps a rewritten header field")


def _export_serials(package, selected_index: int) -> dict:
    # Export spans can alias one another. The logical stream cap alone does
    # not bound cumulative allocations or repeated decompression work.
    total = sum(export["serial_size"] for export in package.exports)
    if total > MAX_RETAINED_EXPORT_BYTES:
        raise PackageRewriteError("aggregate export serials exceed the 64 MiB budget")
    serials = {}
    for export in package.exports:
        if export["serial_size"] <= 0:
            continue
        serials[export["index"]] = reader._extract_serial(package, export)
        if export["index"] == selected_index and not serials[export["index"]]:
            raise PackageRewriteError("SwfMovie export is empty")
    if selected_index not in serials:
        raise PackageRewriteError("SwfMovie export is empty")
    return serials


def _require_replacement(replacement: bytes, original: bytes) -> None:
    signature = replacement[:3]
    if signature not in _UNCOMPRESSED_SWF:
        raise PackageRewriteError("replacement movie must be uncompressed GFX or FWS")
    if replacement[3] != original[3]:
        raise PackageRewriteError("replacement SWF version does not match the source movie")
    if replacement[3] < 1:
        raise PackageRewriteError("replacement movie header length is outside 8 bytes..16 MiB")
    declared = struct.unpack_from("<I", replacement, 4)[0]
    if declared != len(replacement):
        raise PackageRewriteError("replacement movie header length does not match its bytes")


def _rawdata_span(serial: bytes, names, movie: bytes):
    """Return the RawData length-field offset, payload offset, and payload length.

    The walk matches ``_parse_swf_movie``. Net index, every other property,
    the RawData name and type, its array index, and the terminator stay outside
    the replaced count and movie bytes.
    """
    cursor = reader._Reader(serial)
    if cursor.remaining() < 4:
        raise reader.PackageReadError("SwfMovie export is truncated")
    cursor.unpack("i")
    found = None
    for _ in range(reader.MAX_PROPERTIES):
        if cursor.remaining() == 0:
            raise reader.PackageReadError("property list is unterminated")
        field = reader._fname(cursor, names, number_must_be_zero=True)
        if field == "None":
            break
        kind = reader._fname(cursor, names, number_must_be_zero=True)
        if kind not in reader._KNOWN_PROPERTIES:
            raise reader.PackageReadError("unknown property metadata")
        length_at = cursor.offset
        length, array_index = cursor.unpack("ii")
        if length < 0 or array_index < 0:
            raise reader.PackageReadError("property length is outside the export")
        if kind in reader._NAME_BEFORE_PAYLOAD:
            reader._fname(cursor, names, number_must_be_zero=True)
        elif kind == "BoolProperty":
            cursor.take(1)
        if length > cursor.remaining():
            raise reader.PackageReadError("property length is outside the export")
        payload_at = cursor.offset
        payload = cursor.take(length)
        if field == "RawData":
            if found is not None:
                raise reader.PackageReadError("duplicate RawData property")
            found = (length_at, payload_at, length, payload, kind)
    else:
        raise reader.PackageReadError("property list is unterminated")
    if cursor.offset != len(serial) or found is None:
        raise PackageRewriteError("RawData property span was not found")
    length_at, payload_at, length, payload, kind = found
    if kind != "ArrayProperty" or length < 4 or payload_at < length_at + 8:
        raise PackageRewriteError("RawData property span was not found")
    if struct.unpack_from("<i", serial, length_at)[0] != length:
        raise PackageRewriteError("RawData property span was not found")
    if payload[4:] != movie or struct.unpack_from("<i", payload)[0] != len(movie):
        raise PackageRewriteError("RawData property span was not found")
    if payload_at + length > len(serial):
        raise PackageRewriteError("RawData property span was not found")
    return length_at, payload_at, length


def _splice_rawdata(serial: bytes, span, replacement: bytes) -> bytes:
    length_at, payload_at, length = span
    new_payload = struct.pack("<i", len(replacement)) + replacement
    return (
        serial[:length_at]
        + struct.pack("<i", len(new_payload))
        + serial[length_at + 4:payload_at]
        + new_payload
        + serial[payload_at + length:]
    )


def _require_logical_fit(offset: int, size: int) -> None:
    if offset > reader.MAX_LOGICAL_BYTES or size > reader.MAX_LOGICAL_BYTES - offset:
        raise PackageRewriteError("logical stream exceeds 256 MiB")


def _frame_serial(plain: bytes) -> bytes:
    if len(plain) < 1 or len(plain) > reader.MAX_CHUNK_BYTES:
        raise PackageRewriteError("chunk size exceeds 16 MiB")
    blocks = []
    for offset in range(0, len(plain), BLOCK_BYTES):
        part = plain[offset:offset + BLOCK_BYTES]
        compressed = zlib.compress(part)
        if len(compressed) < 1 or len(compressed) > BLOCK_BYTES * 2:
            raise PackageRewriteError("chunk block size is outside its block")
        blocks.append((compressed, len(part)))
    compressed_total = sum(len(payload) for payload, _size in blocks)
    header = struct.pack("<4I", reader.MAGIC, BLOCK_BYTES, compressed_total, len(plain))
    table = b"".join(struct.pack("<II", len(payload), size) for payload, size in blocks)
    framed = header + table + b"".join(payload for payload, _size in blocks)
    if len(framed) > reader.MAX_CHUNK_BYTES or compressed_total > reader.MAX_CHUNK_BYTES:
        raise PackageRewriteError("chunk size exceeds 16 MiB")
    try:
        reader._frame_blocks(framed, len(plain))
    except reader.PackageReadError as exc:
        raise PackageRewriteError("rewritten chunk failed frame validation") from exc
    return framed


def _patch_sizes(header: bytearray, summary, package, export, serial_size: int, compressed_size: int):
    serial_at, found_size, found_offset = _serial_size_at(header, summary, package.names, export["index"])
    if found_size != export["serial_size"] or found_offset != export["serial_offset"]:
        raise PackageRewriteError("export serial size field does not match the parsed export")
    usize_at, csize_at, found_u, found_c = _last_chunk_sizes_at(header, summary, package.chunks[-1])
    if found_u != package.chunks[-1].uncompressed_size or found_c != package.chunks[-1].compressed_size:
        raise PackageRewriteError("chunk size field does not match the parsed chunk")
    limit = reader._aligned_end(summary.name_offset, summary.header_size)
    fields = (serial_at, usize_at, csize_at)
    for field in fields:
        if field < summary.name_offset or field + 4 > limit:
            raise PackageRewriteError("rewritten field is outside the aligned header")
    struct.pack_into("<i", header, serial_at, serial_size)
    struct.pack_into("<i", header, usize_at, serial_size)
    struct.pack_into("<i", header, csize_at, compressed_size)
    return fields


def _serial_size_at(header: bytes, summary, names, export_index: int):
    cursor = reader._Reader(header, summary.export_offset, summary.depends_offset)
    found = None
    for index in range(summary.export_count):
        cursor.unpack("iii")
        reader._fname(cursor, names)
        size_at = cursor.offset + 12
        _archetype, _flags, serial_size, serial_offset, _export_flags, net_count = cursor.unpack("iQiQIi")
        if net_count < 0 or net_count > reader.MAX_NET_COUNT:
            raise reader.PackageReadError("invalid export net count")
        cursor.take(net_count * 4 + 16 + 4)
        if index == export_index:
            found = (size_at, serial_size, serial_offset)
    if cursor.offset != summary.depends_offset or found is None:
        raise PackageRewriteError("export serial size field was not found")
    return found


def _last_chunk_sizes_at(header: bytes, summary, last):
    cursor = reader._Reader(header, summary.depends_offset, summary.header_size)
    (count,) = cursor.unpack("i")
    found = None
    for index in range(count):
        base = cursor.offset
        uncompressed_offset, uncompressed_size, compressed_offset, compressed_size = cursor.unpack("qiqi")
        if summary.licensee == LICENSEE:
            nonce = cursor.take(reader.NONCE_BYTES)
            if nonce != b"\x00" * reader.NONCE_BYTES:
                raise reader.PackageReadError("nonzero chunk extension is not supported")
        if index == count - 1:
            found = (base + 8, base + 20, uncompressed_size, compressed_size, uncompressed_offset, compressed_offset)
    if found is None:
        raise PackageRewriteError("chunk size field was not found")
    usize_at, csize_at, uncompressed_size, compressed_size, uncompressed_offset, compressed_offset = found
    if uncompressed_offset != last.uncompressed_offset or compressed_offset != last.compressed_offset:
        raise PackageRewriteError("chunk size field does not match the parsed chunk")
    return usize_at, csize_at, uncompressed_size, compressed_size


def _only_these_bytes_changed(before: bytes, after: bytes, fields) -> None:
    if len(before) != len(after):
        raise PackageRewriteError("rewrite changed the header length")
    allowed = set()
    for field in fields:
        allowed.update(range(field, field + 4))
    for index, (left, right) in enumerate(zip(before, after, strict=True)):
        if left != right and index not in allowed:
            raise PackageRewriteError("rewrite changed an unrelated header byte")


def _seal_header(plain_header, summary, encrypted: bool, decrypt_header, encrypt_header, source: bytes) -> bytes:
    limit = reader._aligned_end(summary.name_offset, summary.header_size)
    header = bytearray(plain_header)
    if bytes(header[:summary.name_offset]) != source[:summary.name_offset]:
        raise PackageRewriteError("rewrite changed an unrelated header byte")
    if bytes(header[limit:summary.header_size]) != source[limit:summary.header_size]:
        raise PackageRewriteError("rewrite changed an unrelated header byte")
    if not encrypted:
        if encrypt_header is not None:
            raise PackageRewriteError("plaintext header does not use encrypt_header")
        return bytes(header)
    if encrypt_header is None or decrypt_header is None:
        raise PackageRewriteError("encrypted header requires encrypt_header")
    region = bytes(header[summary.name_offset:limit])
    sealed = _call_encrypt(encrypt_header, region)
    try:
        opened = reader._call_decrypt(decrypt_header, sealed)
    except reader.PackageReadError as exc:
        raise PackageRewriteError("decrypt callback did not round-trip the new header") from exc
    if opened != region:
        raise PackageRewriteError("decrypt callback did not round-trip the new header")
    header[summary.name_offset:limit] = sealed
    if bytes(header[limit:summary.header_size]) != source[limit:summary.header_size]:
        raise PackageRewriteError("rewrite changed an unrelated header byte")
    return bytes(header)


def _call_encrypt(encrypt_header, region: bytes) -> bytes:
    try:
        returned = encrypt_header(region)
    except PackageRewriteError:
        raise
    except reader.PackageReadError:
        raise
    except Exception as exc:
        raise PackageRewriteError("encrypt callback failed") from exc
    if isinstance(returned, bytearray):
        returned = bytes(returned)
    if not isinstance(returned, bytes):
        raise PackageRewriteError("encrypt callback returned an unexpected shape")
    if len(returned) != len(region):
        raise PackageRewriteError("encrypt callback returned an unexpected length")
    return returned


def _assert_reparsed(
    source, output, summary, package, export, serials, replacement, new_serial, framed,
    plain_header, decrypt_header,
) -> None:
    try:
        summary2, package2 = _load_package(output, decrypt_header if package.header_decrypted else None)
        _compare_reparse(
            source, output, summary, summary2, package, package2, export, serials,
            replacement, new_serial, framed, plain_header,
        )
    except reader.PackageReadError as exc:
        raise PackageRewriteError("rewritten package failed reader validation") from exc


def _compare_reparse(
    source, output, summary, summary2, package, package2, export, serials,
    replacement, new_serial, framed, plain_header,
) -> None:
    if summary2.version != summary.version or summary2.licensee != summary.licensee:
        raise PackageRewriteError("rewritten package failed reader validation")
    if summary2.header_size != summary.header_size or summary2.flags != summary.flags:
        raise PackageRewriteError("rewritten package failed reader validation")
    if summary2.name_offset != summary.name_offset or summary2.depends_offset != summary.depends_offset:
        raise PackageRewriteError("rewritten package failed reader validation")
    if package2.names != package.names or package2.header_decrypted != package.header_decrypted:
        raise PackageRewriteError("rewritten package failed reader validation")
    if bytes(package2.header) != plain_header:
        raise PackageRewriteError("rewritten package failed reader validation")
    limit = reader._aligned_end(summary.name_offset, summary.header_size)
    if output[:summary.name_offset] != source[:summary.name_offset]:
        raise PackageRewriteError("rewritten package failed reader validation")
    if output[limit:summary.header_size] != source[limit:summary.header_size]:
        raise PackageRewriteError("rewritten package failed reader validation")
    if len(package2.chunks) != len(package.chunks) or len(package2.exports) != len(package.exports):
        raise PackageRewriteError("rewritten package failed reader validation")

    last = package.chunks[-1]
    last2 = package2.chunks[-1]
    if output[last.compressed_offset:] != framed:
        raise PackageRewriteError("rewritten package failed reader validation")
    if last2.uncompressed_offset != last.uncompressed_offset or last2.compressed_offset != last.compressed_offset:
        raise PackageRewriteError("rewritten package failed reader validation")
    if last2.uncompressed_size != len(new_serial) or last2.compressed_size != len(framed):
        raise PackageRewriteError("rewritten package failed reader validation")
    if last2.compressed_offset + last2.compressed_size != len(output):
        raise PackageRewriteError("rewritten package failed reader validation")
    for old, new in zip(package.chunks[:-1], package2.chunks[:-1], strict=True):
        if old.uncompressed_offset != new.uncompressed_offset or old.uncompressed_size != new.uncompressed_size:
            raise PackageRewriteError("rewritten package failed reader validation")
        if old.compressed_offset != new.compressed_offset or old.compressed_size != new.compressed_size:
            raise PackageRewriteError("rewritten package failed reader validation")
        old_bytes = source[old.compressed_offset:old.compressed_offset + old.compressed_size]
        new_bytes = output[new.compressed_offset:new.compressed_offset + new.compressed_size]
        if old_bytes != new_bytes:
            raise PackageRewriteError("a non-final chunk changed")

    selected = reader._select_export(package2, export["name"])
    if selected["serial_offset"] != export["serial_offset"] or selected["serial_size"] != len(new_serial):
        raise PackageRewriteError("rewritten package failed reader validation")
    movie = reader._parse_swf_movie(reader._extract_serial(package2, selected), selected, package2.names)
    if movie.data != replacement or movie.metadata["sha256"] != hashlib.sha256(replacement).hexdigest():
        raise PackageRewriteError("reparsed movie does not match the replacement")
    for old in package.exports:
        if old["index"] == export["index"]:
            continue
        new = package2.exports[old["index"]]
        if new["name"] != old["name"] or new["class"] != old["class"]:
            raise PackageRewriteError("rewritten package failed reader validation")
        if new["serial_offset"] != old["serial_offset"] or new["serial_size"] != old["serial_size"]:
            raise PackageRewriteError("rewritten package failed reader validation")
        if old["serial_size"] <= 0:
            continue
        if reader._extract_serial(package2, new) != serials[old["index"]]:
            raise PackageRewriteError("another export serial changed")


def _metadata(export_name, source, output, original_movie, replacement, serial, new_serial) -> dict:
    return {
        "export_name": export_name,
        "before_package_sha256": hashlib.sha256(source).hexdigest(),
        "after_package_sha256": hashlib.sha256(output).hexdigest(),
        "before_movie_sha256": hashlib.sha256(original_movie).hexdigest(),
        "after_movie_sha256": hashlib.sha256(replacement).hexdigest(),
        "before_package_length": len(source),
        "after_package_length": len(output),
        "before_movie_length": len(original_movie),
        "after_movie_length": len(replacement),
        "before_serial_size": len(serial),
        "after_serial_size": len(new_serial),
        "runtime_verified": RUNTIME_VERIFIED,
        "production_ready": PRODUCTION_READY,
        "writes_files": WRITES_FILES,
        "swf_tags_validated": SWF_TAGS_VALIDATED,
    }


def _cng_encrypt(plaintext: bytes, key: bytes) -> bytes:
    import ctypes
    from ctypes import wintypes

    try:
        bcrypt = ctypes.WinDLL("bcrypt.dll", use_last_error=True)
    except OSError as exc:
        raise PackageRewriteError("CNG bcrypt.dll is not available") from exc

    status_type = ctypes.c_long
    bcrypt.BCryptOpenAlgorithmProvider.argtypes = [
        ctypes.POINTER(wintypes.HANDLE), wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.ULONG,
    ]
    bcrypt.BCryptOpenAlgorithmProvider.restype = status_type
    bcrypt.BCryptCloseAlgorithmProvider.argtypes = [wintypes.HANDLE, wintypes.ULONG]
    bcrypt.BCryptCloseAlgorithmProvider.restype = status_type
    bcrypt.BCryptGetProperty.argtypes = [
        wintypes.HANDLE, wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_ubyte),
        wintypes.ULONG, ctypes.POINTER(wintypes.ULONG), wintypes.ULONG,
    ]
    bcrypt.BCryptGetProperty.restype = status_type
    bcrypt.BCryptSetProperty.argtypes = [
        wintypes.HANDLE, wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_ubyte),
        wintypes.ULONG, wintypes.ULONG,
    ]
    bcrypt.BCryptSetProperty.restype = status_type
    bcrypt.BCryptGenerateSymmetricKey.argtypes = [
        wintypes.HANDLE, ctypes.POINTER(wintypes.HANDLE), ctypes.POINTER(ctypes.c_ubyte),
        wintypes.ULONG, ctypes.POINTER(ctypes.c_ubyte), wintypes.ULONG, wintypes.ULONG,
    ]
    bcrypt.BCryptGenerateSymmetricKey.restype = status_type
    bcrypt.BCryptDestroyKey.argtypes = [wintypes.HANDLE]
    bcrypt.BCryptDestroyKey.restype = status_type
    bcrypt.BCryptEncrypt.argtypes = [
        wintypes.HANDLE, ctypes.POINTER(ctypes.c_ubyte), wintypes.ULONG, ctypes.c_void_p,
        ctypes.c_void_p, wintypes.ULONG, ctypes.POINTER(ctypes.c_ubyte), wintypes.ULONG,
        ctypes.POINTER(wintypes.ULONG), wintypes.ULONG,
    ]
    bcrypt.BCryptEncrypt.restype = status_type

    algorithm = wintypes.HANDLE()
    sym_key = wintypes.HANDLE()
    try:
        status = bcrypt.BCryptOpenAlgorithmProvider(ctypes.byref(algorithm), "AES", None, 0)
        if status != 0 or not algorithm.value:
            raise PackageRewriteError("CNG could not open AES")
        mode = "ChainingModeECB\0".encode("utf-16-le")
        mode_buf = (ctypes.c_ubyte * len(mode)).from_buffer_copy(mode)
        status = bcrypt.BCryptSetProperty(algorithm, "ChainingMode", mode_buf, len(mode), 0)
        if status != 0:
            raise PackageRewriteError("CNG could not set AES-ECB")
        block = _cng_ulong(bcrypt, algorithm, "BlockLength")
        if block != reader.AES_BLOCK:
            raise PackageRewriteError("CNG AES block length was not 16")
        object_length = _cng_ulong(bcrypt, algorithm, "ObjectLength")
        if object_length < reader.AES_BLOCK or object_length > reader.MAX_CNG_KEY_OBJECT:
            raise PackageRewriteError("CNG key object length is outside its cap")
        key_object = (ctypes.c_ubyte * object_length)()
        secret = (ctypes.c_ubyte * 32).from_buffer_copy(key)
        status = bcrypt.BCryptGenerateSymmetricKey(
            algorithm, ctypes.byref(sym_key), key_object, object_length, secret, 32, 0,
        )
        if status != 0 or not sym_key.value:
            raise PackageRewriteError("CNG could not import the explicit key")
        incoming = (ctypes.c_ubyte * len(plaintext)).from_buffer_copy(plaintext)
        outgoing = (ctypes.c_ubyte * len(plaintext))()
        written = wintypes.ULONG()
        status = bcrypt.BCryptEncrypt(
            sym_key, incoming, len(plaintext), None, None, 0,
            outgoing, len(plaintext), ctypes.byref(written), 0,
        )
        if status != 0 or written.value != len(plaintext):
            raise PackageRewriteError("CNG AES-256-ECB encrypt failed")
        return bytes(outgoing)
    finally:
        if sym_key.value:
            bcrypt.BCryptDestroyKey(sym_key)
            sym_key.value = None
        if algorithm.value:
            bcrypt.BCryptCloseAlgorithmProvider(algorithm, 0)
            algorithm.value = None


def _cng_ulong(bcrypt, handle, name: str) -> int:
    import ctypes
    from ctypes import wintypes

    out = (ctypes.c_ubyte * 4)()
    written = wintypes.ULONG()
    status = bcrypt.BCryptGetProperty(handle, name, out, 4, ctypes.byref(written), 0)
    if status != 0 or written.value != 4:
        raise PackageRewriteError(f"CNG could not read {name}")
    return int.from_bytes(bytes(out), "little")
