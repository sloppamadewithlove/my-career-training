"""Small strict PE inspection for our compiled plugin, without executing game code."""
from __future__ import annotations

from pathlib import Path
import struct


def inspect_plugin(path: Path) -> dict:
    data = path.read_bytes()

    def read(fmt: str, offset: int):
        size = struct.calcsize(fmt)
        if offset < 0 or offset + size > len(data):
            raise ValueError('Truncated PE artifact')
        return struct.unpack_from(fmt, data, offset)

    if data[:2] != b'MZ':
        raise ValueError('Plugin is not a Windows PE binary')
    pe, = read('<I', 0x3c)
    if data[pe:pe + 4] != b'PE\0\0':
        raise ValueError('Invalid PE signature')
    machine, sections, _, _, _, optional_size, flags = read('<HHIIIHH', pe + 4)
    if machine != 0x8664 or not flags & 0x2000:
        raise ValueError('Plugin must be an AMD64 DLL')
    optional = pe + 24
    magic, = read('<H', optional)
    if magic != 0x20b or optional_size < 128:
        raise ValueError('Plugin requires a PE32+ optional header')
    export_rva, export_size = read('<II', optional + 112)
    table = optional + optional_size
    mapping = []
    for index in range(sections):
        _, size, address, raw_size, raw_offset = read('<8sIIII', table + index * 40)
        mapping.append((address, max(size, raw_size), raw_offset, raw_size))

    def offset(rva: int) -> int:
        for address, size, raw, raw_size in mapping:
            if address <= rva < address + size and rva - address < raw_size:
                return raw + rva - address
        raise ValueError('PE address lies outside initialized section data')

    if not export_rva or export_size < 40:
        raise ValueError('Plugin has no export directory')
    directory = offset(export_rva)
    names_count, = read('<I', directory + 24)
    names_rva, = read('<I', directory + 32)
    if not 1 <= names_count <= 4096:
        raise ValueError('Unexpected plugin export count')
    names = []
    names_table = offset(names_rva)
    for index in range(names_count):
        name_rva, = read('<I', names_table + index * 4)
        start = offset(name_rva)
        end = data.find(b'\0', start, min(start + 512, len(data)))
        if end < 0:
            raise ValueError('Unterminated plugin export name')
        names.append(data[start:end].decode('ascii'))
    required = {'getPlugin', 'deleteMe', 'exports', 'mct_protocol_version'}
    if not required.issubset(names):
        raise ValueError(f'Missing required plugin exports: {sorted(required.difference(names))}')
    import_rva, import_size = read('<II', optional + 120)
    imports = []
    if import_rva:
        imports_start = offset(import_rva)
        for index in range(min(import_size // 20, 4096)):
            descriptor = read('<IIIII', imports_start + index * 20)
            if not any(descriptor):
                break
            name_offset = offset(descriptor[3])
            end = data.find(b'\0', name_offset, min(name_offset + 512, len(data)))
            if end < 0:
                raise ValueError('Unterminated plugin dependency name')
            imports.append(data[name_offset:end].decode('ascii'))
    return {'machine': 'AMD64', 'dll': True, 'exports': sorted(names),
            'imports': sorted(imports), 'load_context': 'BakkesMod inside Rocket League'}
