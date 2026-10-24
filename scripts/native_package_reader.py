"""Read-only development reader for one cooked menu package.

The caller supplies a file path and, when the name tables are encrypted, a
``decrypt_header`` callable. This module does not search for a key, does not
fetch anything, and does not write package bytes or movie bytes anywhere.
``MovieBytes.data`` stays in process memory. Do not redistribute it.

Nothing here loads a game, starts a runtime, or marks the package usable in
production. Capability flags are all false.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import stat
import struct
import sys
import zlib

MAGIC = 0x9E2A83C1
SUPPORTED_VERSION = 868
SUPPORTED_LICENSEES = (32, 34)
CTR_FLAG = 0x800
AES_BLOCK = 16
LICENSEE_32_CHUNK_STRIDE = 24
LICENSEE_34_CHUNK_STRIDE = 36
NONCE_BYTES = 12

MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_HEADER_BYTES = 4 * 1024 * 1024
MAX_TABLE_COUNT = 65536
MAX_STRING_UNITS = 1024
MAX_EXPORT_BYTES = 16 * 1024 * 1024
MAX_LOGICAL_BYTES = 256 * 1024 * 1024
MAX_CHUNK_COUNT = 4096
MAX_CHUNK_BYTES = 16 * 1024 * 1024
MIN_BLOCK_BYTES = 4 * 1024
MAX_BLOCK_BYTES = 4 * 1024 * 1024
MEASURED_BLOCK_BYTES = 131072
MAX_NAME_NUMBER = 1_000_000
MAX_PROPERTIES = 4096
MAX_NET_COUNT = 65536
MAX_CNG_KEY_OBJECT = 64 * 1024

LOADS_RUNTIME = False
WRITES_ASSETS = False
NETWORK_FETCH = False
REDISTRIBUTES_PAYLOAD = False
PRODUCTION_READY = False

_SIMPLE_PROPERTIES = frozenset({
    "ArrayProperty",
    "ClassProperty",
    "ComponentProperty",
    "DelegateProperty",
    "FloatProperty",
    "IntProperty",
    "InterfaceProperty",
    "NameProperty",
    "ObjectProperty",
    "StrProperty",
})
_NAME_BEFORE_PAYLOAD = frozenset({"ByteProperty", "StructProperty"})
_KNOWN_PROPERTIES = _SIMPLE_PROPERTIES | _NAME_BEFORE_PAYLOAD | {"BoolProperty"}
_UNCOMPRESSED_SWF = frozenset({b"FWS", b"GFX"})
_COMPRESSED_SWF = frozenset({b"CWS", b"CFX"})
_REPARSE_POINT = 0x400


class PackageReadError(ValueError):
    """The package is not a supported menu package, or the file changed."""


class MovieBytes:
    """In-memory movie payload plus the small metadata dictionary.

    ``data`` is the RawData byte string and nothing else. Callers keep it in
    memory for local development. This object has no save method.
    """

    __slots__ = ("data", "metadata")

    def __init__(self, data: bytes, metadata: dict):
        self.data = bytes(data)
        self.metadata = dict(metadata)

    def __repr__(self) -> str:
        meta = self.metadata
        return (
            f"MovieBytes(signature={meta.get('signature')!r}, "
            f"raw_length={meta.get('raw_length')!r})"
        )


def capabilities() -> dict:
    """Fresh dictionary. Every production capability stays false."""
    return {
        "loads_runtime": LOADS_RUNTIME,
        "writes_assets": WRITES_ASSETS,
        "network_fetch": NETWORK_FETCH,
        "redistribute_payload": REDISTRIBUTES_PAYLOAD,
        "production_ready": PRODUCTION_READY,
    }


def inspect_menu_package(path, decrypt_header=None) -> dict:
    """Return a JSON-serializable inventory. Payloads are not included."""
    with _open_package(path, decrypt_header) as package:
        return _inventory(package)


def read_movie_bytes(path, exact_export_name, decrypt_header=None) -> MovieBytes:
    """Return one SwfMovie RawData buffer and its small metadata.

    ``exact_export_name`` is matched exactly. There is no output path.
    """
    if not isinstance(exact_export_name, str):
        raise PackageReadError("export name must be a string")
    with _open_package(path, decrypt_header) as package:
        export = _select_export(package, exact_export_name)
        serial = _extract_serial(package, export)
        return _parse_swf_movie(serial, export, package.names)


def decrypt_aes256_ecb_cng(ciphertext: bytes, key: bytes) -> bytes:
    """Decrypt one AES-256-ECB buffer with Windows CNG and an explicit key.

    The key is not stored or searched for. Ciphertext must be a positive
    multiple of 16 bytes and at most the header cap. No padding is applied.
    """
    if isinstance(key, bytearray):
        key = bytes(key)
    if not isinstance(key, bytes) or len(key) != 32:
        raise PackageReadError("AES-256-ECB requires an explicit 32-byte key")
    if isinstance(ciphertext, bytearray):
        ciphertext = bytes(ciphertext)
    if not isinstance(ciphertext, bytes) or not ciphertext:
        raise PackageReadError("AES-256-ECB ciphertext must be bytes")
    if len(ciphertext) % AES_BLOCK != 0:
        raise PackageReadError("AES-256-ECB ciphertext length is not a full block")
    if len(ciphertext) > MAX_HEADER_BYTES:
        raise PackageReadError("AES-256-ECB ciphertext exceeds the 4 MiB cap")
    if sys.platform != "win32":
        raise PackageReadError("CNG AES-256-ECB is only available on Windows")
    return _cng_decrypt(ciphertext, key)


class _Reader:
    def __init__(self, data: bytes, offset: int = 0, limit: int | None = None):
        self.data = data
        self.offset = offset
        self.limit = len(data) if limit is None else limit
        if offset < 0 or self.limit < offset or self.limit > len(data):
            raise PackageReadError("read is outside the bounded buffer")

    def remaining(self) -> int:
        return self.limit - self.offset

    def take(self, size: int) -> bytes:
        if size < 0 or size > self.remaining():
            raise PackageReadError("read is outside the bounded buffer")
        found = self.data[self.offset:self.offset + size]
        self.offset += size
        return found

    def unpack(self, fmt: str):
        pattern = "<" + fmt
        return struct.unpack(pattern, self.take(struct.calcsize(pattern)))

    def fstring(self) -> str:
        (length,) = self.unpack("i")
        if length == 0 or abs(length) > MAX_STRING_UNITS:
            raise PackageReadError("string length is outside 1..1024")
        if length > 0:
            raw = self.take(length)
            if raw[-1:] != b"\x00" or b"\x00" in raw[:-1]:
                raise PackageReadError("ANSI string is not strictly terminated")
            try:
                return raw[:-1].decode("ascii")
            except UnicodeDecodeError as exc:
                raise PackageReadError("ANSI string is not strict ASCII") from exc
        units = -length
        raw = self.take(units * 2)
        if raw[-2:] != b"\x00\x00":
            raise PackageReadError("UTF-16 string is not strictly terminated")
        body = raw[:-2]
        if any(body[index:index + 2] == b"\x00\x00" for index in range(0, len(body), 2)):
            raise PackageReadError("UTF-16 string is not strictly terminated")
        try:
            return body.decode("utf-16-le")
        except UnicodeDecodeError as exc:
            raise PackageReadError("UTF-16 string is not valid") from exc


class _Summary:
    __slots__ = (
        "version", "licensee", "header_size", "flags", "name_count", "name_offset",
        "export_count", "export_offset", "import_count", "import_offset",
        "depends_offset", "summary_end",
    )

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class _Chunk:
    __slots__ = (
        "uncompressed_offset", "uncompressed_size", "compressed_offset", "compressed_size",
    )

    def __init__(self, uncompressed_offset, uncompressed_size, compressed_offset, compressed_size):
        self.uncompressed_offset = uncompressed_offset
        self.uncompressed_size = uncompressed_size
        self.compressed_offset = compressed_offset
        self.compressed_size = compressed_size


class _Package:
    __slots__ = (
        "version", "licensee", "flags", "header_size", "file_size", "logical_size",
        "header_decrypted", "header", "depends_offset", "names", "imports", "exports",
        "chunks", "read_at",
    )

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


def _snapshot(info) -> tuple:
    # Python 3.12 on Windows can expose creation time through lstat's ctime
    # and change time through fstat's ctime. Compare last-write time there;
    # POSIX ctime is comparable and catches additional metadata changes.
    change_time = info.st_ctime_ns if sys.platform != "win32" else None
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, change_time)


def _prepare(path: Path):
    try:
        info = path.lstat()
    except OSError as exc:
        raise PackageReadError(f"package is not readable: {exc.strerror or exc}") from exc
    mode = info.st_mode
    if stat.S_ISLNK(mode):
        raise PackageReadError("symbolic links are not supported")
    if getattr(info, "st_file_attributes", 0) & _REPARSE_POINT:
        raise PackageReadError("reparse points are not supported")
    if not stat.S_ISREG(mode):
        raise PackageReadError("package must be a regular file")
    if info.st_size > MAX_FILE_BYTES:
        raise PackageReadError("package exceeds the 64 MiB cap")
    if info.st_size < 12:
        raise PackageReadError("package is truncated")
    return info


def _read_fd(fd: int, file_len: int, offset: int, size: int) -> bytes:
    if size < 0 or offset < 0 or offset > file_len or size > file_len - offset:
        raise PackageReadError("read is outside the package")
    try:
        os.lseek(fd, offset, os.SEEK_SET)
        found = bytearray()
        remaining = size
        while remaining:
            part = os.read(fd, remaining)
            if not part:
                raise PackageReadError("package is truncated")
            found += part
            remaining -= len(part)
    except PackageReadError:
        raise
    except OSError as exc:
        raise PackageReadError("package is not readable") from exc
    return bytes(found)


def _confirm(fd: int, path: Path, snapshot: tuple) -> None:
    try:
        inside = _snapshot(os.fstat(fd))
        outside = _snapshot(path.lstat())
    except OSError as exc:
        raise PackageReadError("file changed during read") from exc
    if inside != snapshot or outside != snapshot:
        raise PackageReadError("file changed during read")


class _Open:
    def __init__(self, path, decrypt_header):
        self.path = Path(path)
        self.decrypt_header = decrypt_header
        self.fd = None
        self.package = None

    def __enter__(self) -> _Package:
        if self.decrypt_header is not None and not callable(self.decrypt_header):
            raise PackageReadError("decrypt_header must be callable")
        info = _prepare(self.path)
        flags = os.O_RDONLY
        if hasattr(os, "O_BINARY"):
            flags |= os.O_BINARY
        try:
            self.fd = os.open(self.path, flags)
        except OSError as exc:
            raise PackageReadError(f"package is not readable: {exc.strerror or exc}") from exc
        try:
            snapshot = _snapshot(info)
            _confirm(self.fd, self.path, snapshot)
            file_len = info.st_size
            fd = self.fd

            def read_at(offset, size, _fd=fd, _length=file_len):
                return _read_fd(_fd, _length, offset, size)
            prefix = read_at(0, 12)
            summary = _parse_summary(prefix, read_at, file_len)
            package = _decode_header(summary, read_at, self.decrypt_header, file_len)
            _validate_frames(package, read_at)
            package.read_at = read_at
            self.snapshot = snapshot
            return package
        except Exception:
            os.close(self.fd)
            self.fd = None
            raise

    def __exit__(self, exc_type, exc, tb):
        if self.fd is None:
            return False
        try:
            if exc_type is None:
                _confirm(self.fd, self.path, self.snapshot)
        finally:
            os.close(self.fd)
            self.fd = None
        return False


def _open_package(path, decrypt_header):
    return _Open(path, decrypt_header)


def _parse_summary(prefix: bytes, read_at, file_len: int) -> _Summary:
    magic, version, licensee, header_size = struct.unpack_from("<IHHI", prefix)
    if magic != MAGIC:
        raise PackageReadError("package magic is not a UE3 package")
    if version != SUPPORTED_VERSION:
        raise PackageReadError("unsupported package version")
    if licensee not in SUPPORTED_LICENSEES:
        raise PackageReadError("unsupported licensee")
    if header_size > MAX_HEADER_BYTES:
        raise PackageReadError("header exceeds the 4 MiB cap")
    if header_size > file_len or header_size < 12:
        raise PackageReadError("package is truncated")
    header = read_at(0, header_size)
    reader = _Reader(header, 12)
    reader.fstring()
    fields = reader.unpack("8I")
    flags, name_count, name_offset, export_count, export_offset, import_count, import_offset, depends = fields
    if flags & CTR_FLAG:
        raise PackageReadError("full CTR packages are not supported")
    for label, count in (
        ("name", name_count),
        ("import", import_count),
        ("export", export_count),
    ):
        if count > MAX_TABLE_COUNT:
            raise PackageReadError(f"{label} count exceeds 65536")
    return _Summary(
        version=version,
        licensee=licensee,
        header_size=header_size,
        flags=flags,
        name_count=name_count,
        name_offset=name_offset,
        export_count=export_count,
        export_offset=export_offset,
        import_count=import_count,
        import_offset=import_offset,
        depends_offset=depends,
        summary_end=reader.offset,
    )


def _aligned_end(name_offset: int, header_size: int) -> int:
    if name_offset > header_size:
        raise PackageReadError("name table is outside the header")
    span = header_size - name_offset
    aligned = span - (span % AES_BLOCK)
    if aligned <= 0:
        raise PackageReadError("encrypted header region is empty")
    return name_offset + aligned


def _call_decrypt(decrypt_header, region: bytes) -> bytes:
    try:
        returned = decrypt_header(region)
    except PackageReadError:
        raise
    except Exception as exc:
        raise PackageReadError("decrypt callback failed") from exc
    if isinstance(returned, bytearray):
        returned = bytes(returned)
    if not isinstance(returned, bytes):
        raise PackageReadError("decrypt callback returned an unexpected shape")
    if len(returned) != len(region):
        raise PackageReadError("decrypt callback returned an unexpected length")
    return returned


def _decode_header(summary: _Summary, read_at, decrypt_header, file_len: int) -> _Package:
    header = read_at(0, summary.header_size)
    try:
        return _parse_tables(header, summary, file_len, False)
    except PackageReadError:
        if decrypt_header is None:
            raise
    limit = _aligned_end(summary.name_offset, summary.header_size)
    plain = _call_decrypt(decrypt_header, header[summary.name_offset:limit])
    rewritten = bytearray(header)
    rewritten[summary.name_offset:limit] = plain
    try:
        return _parse_tables(bytes(rewritten), summary, file_len, True)
    except PackageReadError as exc:
        raise PackageReadError("decrypted header did not parse") from exc


def _require_inside(start: int, end: int, begin: int, limit: int, label: str) -> None:
    if start < begin or end < start or end > limit:
        raise PackageReadError(f"{label} is outside the decrypted header range")


def _fname(reader: _Reader, names: list[str], *, number_must_be_zero: bool = False) -> str:
    index, number = reader.unpack("ii")
    if index < 0 or index >= len(names) or number < 0 or number > MAX_NAME_NUMBER:
        raise PackageReadError("invalid name reference")
    if number_must_be_zero and number != 0:
        raise PackageReadError("invalid name reference")
    if number == 0:
        return names[index]
    return f"{names[index]}_{number - 1}"


def _check_ref(value: int, import_count: int, export_count: int) -> None:
    if value < -import_count or value > export_count:
        raise PackageReadError("invalid object reference")


def _parse_tables(header: bytes, summary: _Summary, file_len: int, decrypted: bool) -> _Package:
    limit = _aligned_end(summary.name_offset, summary.header_size)
    if not summary.summary_end <= summary.name_offset <= summary.import_offset <= summary.export_offset <= summary.depends_offset <= summary.header_size:
        raise PackageReadError("table order must be names, imports, exports, depends")
    _require_inside(summary.name_offset, summary.import_offset, summary.name_offset, limit, "name table")
    _require_inside(summary.import_offset, summary.export_offset, summary.name_offset, limit, "import table")
    _require_inside(summary.export_offset, summary.depends_offset, summary.name_offset, limit, "export table")

    names = _parse_names(header, summary)
    imports = _parse_imports(header, summary, names)
    exports = _parse_exports(header, summary, names)
    chunks, logical_size = _parse_chunks(header, summary, file_len, limit)
    for export in exports:
        _check_serial(export, logical_size)
        export["class"] = _resolve_class(export.pop("class_ref"), imports, exports)
    return _Package(
        version=summary.version,
        licensee=summary.licensee,
        flags=summary.flags,
        header_size=summary.header_size,
        file_size=file_len,
        logical_size=logical_size,
        header_decrypted=decrypted,
        header=header,
        depends_offset=summary.depends_offset,
        names=names,
        imports=imports,
        exports=exports,
        chunks=chunks,
        read_at=None,
    )


def _parse_names(header: bytes, summary: _Summary) -> list[str]:
    reader = _Reader(header, summary.name_offset, summary.import_offset)
    names = []
    for _ in range(summary.name_count):
        names.append(reader.fstring())
        reader.take(8)
    if reader.offset != summary.import_offset:
        raise PackageReadError("name table does not fill its declared span")
    return names


def _parse_imports(header: bytes, summary: _Summary, names: list[str]) -> list[dict]:
    span = summary.export_offset - summary.import_offset
    if span != summary.import_count * 28:
        raise PackageReadError("import table does not match its count")
    reader = _Reader(header, summary.import_offset, summary.export_offset)
    imports = []
    for _ in range(summary.import_count):
        package = _fname(reader, names)
        class_name = _fname(reader, names)
        (outer,) = reader.unpack("i")
        _check_ref(outer, summary.import_count, summary.export_count)
        name = _fname(reader, names)
        imports.append({
            "package": package,
            "class_name": class_name,
            "outer": outer,
            "name": name,
        })
    if reader.offset != summary.export_offset:
        raise PackageReadError("import table does not fill its declared span")
    return imports


def _parse_exports(header: bytes, summary: _Summary, names: list[str]) -> list[dict]:
    reader = _Reader(header, summary.export_offset, summary.depends_offset)
    exports = []
    for index in range(summary.export_count):
        class_ref, super_ref, outer = reader.unpack("iii")
        for ref in (class_ref, super_ref, outer):
            _check_ref(ref, summary.import_count, summary.export_count)
        name = _fname(reader, names)
        archetype, _object_flags, serial_size, serial_offset, _export_flags, net_count = reader.unpack("iQiQIi")
        _check_ref(archetype, summary.import_count, summary.export_count)
        if net_count < 0 or net_count > MAX_NET_COUNT:
            raise PackageReadError("invalid export net count")
        extra = net_count * 4 + 16 + 4
        if extra > reader.remaining():
            raise PackageReadError("export table does not fill its declared span")
        reader.take(extra)
        if serial_size < 0 or serial_size > MAX_EXPORT_BYTES:
            raise PackageReadError("export serial size exceeds 16 MiB")
        if serial_offset < 0 or serial_offset > MAX_LOGICAL_BYTES:
            raise PackageReadError("export serial offset is outside the logical stream")
        exports.append({
            "index": index,
            "name": name,
            "class_ref": class_ref,
            "serial_offset": serial_offset,
            "serial_size": serial_size,
        })
    if reader.offset != summary.depends_offset:
        raise PackageReadError("export table does not fill its declared span")
    return exports


def _resolve_class(class_ref: int, imports: list[dict], exports: list[dict]) -> str:
    if class_ref == 0:
        return "Class"
    if class_ref < 0:
        return imports[-class_ref - 1]["name"]
    return exports[class_ref - 1]["name"]


def _chunk_stride(licensee: int) -> int:
    if licensee == 34:
        return LICENSEE_34_CHUNK_STRIDE
    if licensee == 32:
        return LICENSEE_32_CHUNK_STRIDE
    raise PackageReadError("unsupported licensee")


def _parse_chunks(header: bytes, summary: _Summary, file_len: int, limit: int):
    if summary.depends_offset > limit or summary.depends_offset + 4 > limit:
        raise PackageReadError("compression table is outside the decrypted header range")
    reader = _Reader(header, summary.depends_offset, summary.header_size)
    (count,) = reader.unpack("i")
    if count < 1 or count > MAX_CHUNK_COUNT:
        raise PackageReadError("chunk count is outside 1..4096")
    stride = _chunk_stride(summary.licensee)
    table_end = summary.depends_offset + 4 + count * stride
    if table_end > limit:
        raise PackageReadError("compression table is outside the decrypted header range")
    if table_end > summary.header_size:
        raise PackageReadError("package is truncated")
    chunks = []
    logical = summary.depends_offset
    physical = summary.header_size
    for _ in range(count):
        uncompressed_offset, uncompressed_size, compressed_offset, compressed_size = reader.unpack("qiqi")
        if summary.licensee == 34:
            nonce = reader.take(NONCE_BYTES)
            if nonce != b"\x00" * NONCE_BYTES:
                raise PackageReadError("nonzero chunk extension is not supported")
        if uncompressed_offset != logical or compressed_offset != physical:
            raise PackageReadError("compression chunks are not contiguous")
        if uncompressed_size < 1 or uncompressed_size > MAX_CHUNK_BYTES:
            raise PackageReadError("chunk size exceeds 16 MiB")
        if compressed_size < 1 or compressed_size > MAX_CHUNK_BYTES:
            raise PackageReadError("chunk size exceeds 16 MiB")
        if logical > MAX_LOGICAL_BYTES or uncompressed_size > MAX_LOGICAL_BYTES - logical:
            raise PackageReadError("logical stream exceeds 256 MiB")
        if compressed_offset > file_len or compressed_size > file_len - compressed_offset:
            raise PackageReadError("chunk is outside the package")
        chunks.append(_Chunk(
            uncompressed_offset, uncompressed_size, compressed_offset, compressed_size,
        ))
        logical += uncompressed_size
        physical += compressed_size
    if physical != file_len:
        raise PackageReadError("compressed bytes do not cover the package")
    if reader.offset != table_end:
        raise PackageReadError("compression table does not match its count")
    return chunks, logical


def _check_serial(export: dict, logical_size: int) -> None:
    start = export["serial_offset"]
    size = export["serial_size"]
    if size == 0:
        if start > logical_size:
            raise PackageReadError("export serial offset is outside the logical stream")
        return
    if start > logical_size or size > logical_size - start:
        raise PackageReadError("export serial span is outside the logical stream")


def _valid_block_size(value: int) -> bool:
    return (
        MIN_BLOCK_BYTES <= value <= MAX_BLOCK_BYTES
        and value & (value - 1) == 0
    )


def _frame_blocks(data: bytes, expected_total: int) -> list[tuple[bytes, int]]:
    reader = _Reader(data)
    magic, block_size, compressed_total, uncompressed_total = reader.unpack("4I")
    if magic != MAGIC:
        raise PackageReadError("chunk magic is not a UE3 package")
    if not _valid_block_size(block_size):
        raise PackageReadError("chunk block size is outside 4 KiB..4 MiB")
    if uncompressed_total != expected_total:
        raise PackageReadError("chunk uncompressed total does not match")
    if compressed_total < 1 or compressed_total > len(data):
        raise PackageReadError("chunk compressed total does not match")
    block_count = (uncompressed_total + block_size - 1) // block_size
    if block_count < 1 or block_count > MAX_CHUNK_BYTES // MIN_BLOCK_BYTES:
        raise PackageReadError("chunk block count is invalid")
    table_bytes = 16 + 8 * block_count
    if table_bytes > len(data) or compressed_total != len(data) - table_bytes:
        raise PackageReadError("chunk totals do not match the framed bytes")
    blocks = []
    running_compressed = 0
    running_plain = 0
    for index in range(block_count):
        compressed_size, plain_size = reader.unpack("II")
        if compressed_size < 1 or plain_size < 1:
            raise PackageReadError("chunk block size is not positive")
        if plain_size > block_size or compressed_size > block_size * 2:
            raise PackageReadError("chunk block size is outside its block")
        expected_plain = block_size if index < block_count - 1 else uncompressed_total - block_size * (block_count - 1)
        if plain_size != expected_plain:
            raise PackageReadError("chunk block sizes are not contiguous")
        running_compressed += compressed_size
        running_plain += plain_size
        if running_compressed > compressed_total:
            raise PackageReadError("chunk compressed total does not match")
        blocks.append((compressed_size, plain_size))
    if running_compressed != compressed_total or running_plain != uncompressed_total:
        raise PackageReadError("chunk totals do not match")
    payloads = []
    for compressed_size, plain_size in blocks:
        payloads.append((reader.take(compressed_size), plain_size))
    if reader.offset != len(data):
        raise PackageReadError("chunk frame was not fully consumed")
    return payloads


def _validate_frames(package: _Package, read_at) -> None:
    for chunk in package.chunks:
        data = read_at(chunk.compressed_offset, chunk.compressed_size)
        _frame_blocks(data, chunk.uncompressed_size)


def _inflate_exact(payload: bytes, expected: int) -> bytes:
    if expected < 1 or expected > MAX_BLOCK_BYTES:
        raise PackageReadError("zlib output length is outside its block")
    decoder = zlib.decompressobj()
    try:
        plain = decoder.decompress(payload, expected + 1)
        extra = decoder.flush()
    except zlib.error as exc:
        raise PackageReadError("zlib stream is invalid") from exc
    if len(plain) != expected or extra or decoder.unconsumed_tail or not decoder.eof:
        raise PackageReadError("zlib stream is invalid")
    if any(decoder.unused_data):
        raise PackageReadError("zlib stream has a non-zero tail")
    return plain


def _extract_serial(package: _Package, export: dict) -> bytes:
    start = export["serial_offset"]
    size = export["serial_size"]
    if size < 1:
        raise PackageReadError("SwfMovie export is empty")
    end = start + size
    out = bytearray(size)
    cursor = start
    if cursor < package.depends_offset:
        take_end = min(end, package.depends_offset)
        out[0:take_end - cursor] = package.header[cursor:take_end]
        cursor = take_end
    for chunk in package.chunks:
        if cursor >= end:
            break
        chunk_end = chunk.uncompressed_offset + chunk.uncompressed_size
        if chunk_end <= cursor or chunk.uncompressed_offset >= end:
            continue
        framed = package.read_at(chunk.compressed_offset, chunk.compressed_size)
        local = chunk.uncompressed_offset
        for payload, plain_size in _frame_blocks(framed, chunk.uncompressed_size):
            block_end = local + plain_size
            if local < end and block_end > cursor:
                plain = _inflate_exact(payload, plain_size)
                lo = max(cursor, local)
                hi = min(end, block_end)
                dest = lo - start
                out[dest:dest + (hi - lo)] = plain[lo - local:hi - local]
                cursor = hi
            local = block_end
    if cursor != end:
        raise PackageReadError("incomplete export span")
    return bytes(out)


def _select_export(package: _Package, exact_export_name: str) -> dict:
    matches = [item for item in package.exports if item["name"] == exact_export_name]
    if not matches:
        raise PackageReadError("export was not found")
    if len(matches) != 1:
        raise PackageReadError("ambiguous export name")
    export = matches[0]
    if export["class"] != "SwfMovie":
        raise PackageReadError("export is not a SwfMovie")
    return export


def _parse_swf_movie(serial: bytes, export: dict, names: list[str]) -> MovieBytes:
    reader = _Reader(serial)
    if reader.remaining() < 4:
        raise PackageReadError("SwfMovie export is truncated")
    reader.unpack("i")
    raw = None
    for _ in range(MAX_PROPERTIES):
        if reader.remaining() == 0:
            raise PackageReadError("property list is unterminated")
        field = _fname(reader, names, number_must_be_zero=True)
        if field == "None":
            break
        kind = _fname(reader, names, number_must_be_zero=True)
        if kind not in _KNOWN_PROPERTIES:
            raise PackageReadError("unknown property metadata")
        length, array_index = reader.unpack("ii")
        if length < 0 or array_index < 0:
            raise PackageReadError("property length is outside the export")
        if kind in _NAME_BEFORE_PAYLOAD:
            _fname(reader, names, number_must_be_zero=True)
        elif kind == "BoolProperty":
            reader.take(1)
        if length > reader.remaining():
            raise PackageReadError("property length is outside the export")
        payload = reader.take(length)
        if field == "RawData":
            if raw is not None:
                raise PackageReadError("duplicate RawData property")
            raw = _raw_movie(kind, payload)
    else:
        raise PackageReadError("property list is unterminated")
    if reader.offset != len(serial):
        raise PackageReadError("SwfMovie export was not fully consumed")
    if raw is None:
        raise PackageReadError("SwfMovie is missing RawData")
    _validate_swf(raw)
    metadata = {
        "export_name": export["name"],
        "class": export["class"],
        "serial_offset": export["serial_offset"],
        "serial_size": export["serial_size"],
        "raw_length": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "signature": raw[:3].decode("ascii"),
    }
    return MovieBytes(raw, metadata)


def _raw_movie(kind: str, payload: bytes) -> bytes:
    if kind != "ArrayProperty" or len(payload) < 4:
        raise PackageReadError("RawData is not a single byte array")
    (count,) = struct.unpack_from("<i", payload)
    if count < 0 or count != len(payload) - 4:
        raise PackageReadError("RawData size does not match its array")
    if count > MAX_EXPORT_BYTES:
        raise PackageReadError("RawData exceeds 16 MiB")
    return payload[4:]


def _validate_swf(movie: bytes) -> None:
    if len(movie) < 8 or len(movie) > MAX_EXPORT_BYTES:
        raise PackageReadError("movie header is outside 8 bytes..16 MiB")
    signature = movie[:3]
    if signature not in _UNCOMPRESSED_SWF and signature not in _COMPRESSED_SWF:
        raise PackageReadError("movie signature is not GFX, FWS, CFX, or CWS")
    version = movie[3]
    declared = struct.unpack_from("<I", movie, 4)[0]
    if version < 1 or declared < 8 or declared > MAX_EXPORT_BYTES:
        raise PackageReadError("movie header length is outside 8 bytes..16 MiB")
    if signature in _UNCOMPRESSED_SWF and declared != len(movie):
        raise PackageReadError("movie header length does not match RawData")
    # FileLength describes the uncompressed SWF. A short or incompressible
    # compressed stream can be longer than that declared length.


def _inventory(package: _Package) -> dict:
    exports = [_public_export(item) for item in package.exports]
    return {
        "version": package.version,
        "licensee": package.licensee,
        "flags": package.flags,
        "header_size": package.header_size,
        "file_size": package.file_size,
        "logical_size": package.logical_size,
        "header_decrypted": package.header_decrypted,
        "name_count": len(package.names),
        "import_count": len(package.imports),
        "export_count": len(exports),
        "chunk_count": len(package.chunks),
        "names": list(package.names),
        "imports": [dict(item) for item in package.imports],
        "exports": exports,
        "chunks": [
            {
                "uncompressed_offset": chunk.uncompressed_offset,
                "uncompressed_size": chunk.uncompressed_size,
                "compressed_offset": chunk.compressed_offset,
                "compressed_size": chunk.compressed_size,
            }
            for chunk in package.chunks
        ],
        "movies": [item for item in exports if item["class"] == "SwfMovie"],
        "capabilities": capabilities(),
    }


def _public_export(item: dict) -> dict:
    return {
        "index": item["index"],
        "name": item["name"],
        "class": item["class"],
        "serial_offset": item["serial_offset"],
        "serial_size": item["serial_size"],
    }


def _cng_decrypt(ciphertext: bytes, key: bytes) -> bytes:
    import ctypes
    from ctypes import wintypes

    try:
        bcrypt = ctypes.WinDLL("bcrypt.dll", use_last_error=True)
    except OSError as exc:
        raise PackageReadError("CNG bcrypt.dll is not available") from exc

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
    bcrypt.BCryptDecrypt.argtypes = [
        wintypes.HANDLE, ctypes.POINTER(ctypes.c_ubyte), wintypes.ULONG, ctypes.c_void_p,
        ctypes.c_void_p, wintypes.ULONG, ctypes.POINTER(ctypes.c_ubyte), wintypes.ULONG,
        ctypes.POINTER(wintypes.ULONG), wintypes.ULONG,
    ]
    bcrypt.BCryptDecrypt.restype = status_type

    algorithm = wintypes.HANDLE()
    sym_key = wintypes.HANDLE()
    try:
        status = bcrypt.BCryptOpenAlgorithmProvider(ctypes.byref(algorithm), "AES", None, 0)
        if status != 0 or not algorithm.value:
            raise PackageReadError("CNG could not open AES")
        mode = "ChainingModeECB\0".encode("utf-16-le")
        mode_buf = (ctypes.c_ubyte * len(mode)).from_buffer_copy(mode)
        status = bcrypt.BCryptSetProperty(algorithm, "ChainingMode", mode_buf, len(mode), 0)
        if status != 0:
            raise PackageReadError("CNG could not set AES-ECB")
        block = _cng_ulong(bcrypt, algorithm, "BlockLength")
        if block != AES_BLOCK:
            raise PackageReadError("CNG AES block length was not 16")
        object_length = _cng_ulong(bcrypt, algorithm, "ObjectLength")
        if object_length < AES_BLOCK or object_length > MAX_CNG_KEY_OBJECT:
            raise PackageReadError("CNG key object length is outside its cap")
        key_object = (ctypes.c_ubyte * object_length)()
        secret = (ctypes.c_ubyte * 32).from_buffer_copy(key)
        status = bcrypt.BCryptGenerateSymmetricKey(
            algorithm, ctypes.byref(sym_key), key_object, object_length, secret, 32, 0,
        )
        if status != 0 or not sym_key.value:
            raise PackageReadError("CNG could not import the explicit key")
        incoming = (ctypes.c_ubyte * len(ciphertext)).from_buffer_copy(ciphertext)
        outgoing = (ctypes.c_ubyte * len(ciphertext))()
        written = wintypes.ULONG()
        status = bcrypt.BCryptDecrypt(
            sym_key, incoming, len(ciphertext), None, None, 0,
            outgoing, len(ciphertext), ctypes.byref(written), 0,
        )
        if status != 0 or written.value != len(ciphertext):
            raise PackageReadError("CNG AES-256-ECB decrypt failed")
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
        raise PackageReadError(f"CNG could not read {name}")
    return int.from_bytes(bytes(out), "little")

