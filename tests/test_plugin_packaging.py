"""Reject non-native, wrong-architecture and incomplete in-game plugin artifacts."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import struct

import pytest

spec = importlib.util.spec_from_file_location(
    'plugin_artifact', Path(__file__).resolve().parents[1] / 'scripts/plugin_artifact.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
inspect_plugin = module.inspect_plugin


def pe_fixture(exports=('getPlugin', 'deleteMe', 'exports', 'mct_protocol_version')) -> bytearray:
    image = bytearray(0xa00)
    image[:2] = b'MZ'
    struct.pack_into('<I', image, 0x3c, 0x80)
    image[0x80:0x84] = b'PE\0\0'
    struct.pack_into('<HHIIIHH', image, 0x84, 0x8664, 1, 0, 0, 0, 240, 0x2000)
    struct.pack_into('<H', image, 0x98, 0x20b)
    struct.pack_into('<II', image, 0x98 + 112, 0x1000, 0x100)
    struct.pack_into('<II', image, 0x98 + 120, 0x1180, 40)
    struct.pack_into('<8sIIII', image, 0x188, b'.rdata\0\0', 0x800, 0x1000, 0x800, 0x200)
    struct.pack_into('<I', image, 0x200 + 24, len(exports))
    struct.pack_into('<I', image, 0x200 + 32, 0x1040)
    cursor = 0x280
    for index, name in enumerate(exports):
        struct.pack_into('<I', image, 0x240 + index * 4, cursor + 0xe00)
        encoded = name.encode('ascii') + b'\0'
        image[cursor:cursor + len(encoded)] = encoded
        cursor += len(encoded)
    struct.pack_into('<IIIII', image, 0x380, 0x1200, 0, 0, 0x11c0, 0x1200)
    image[0x3c0:0x3cd] = b'bakkesmod.dll'
    return image


def test_valid_native_plugin_export_and_load_dependency_inspection(tmp_path):
    path = tmp_path / 'MyCareerTraining.dll'
    path.write_bytes(pe_fixture())
    result = inspect_plugin(path)
    assert result['machine'] == 'AMD64'
    assert result['imports'] == ['bakkesmod.dll']
    assert 'mct_protocol_version' in result['exports']
    assert result['load_context'] == 'BakkesMod inside Rocket League'


@pytest.mark.parametrize('change', ['text', 'x86', 'truncated', 'no-plugin-export', 'bad-export-address'])
def test_invalid_plugin_is_rejected(tmp_path, change):
    image = pe_fixture()
    if change == 'text':
        image = b'not a compiled Windows DLL'
    elif change == 'x86':
        struct.pack_into('<H', image, 0x84, 0x14c)
    elif change == 'truncated':
        image = image[:100]
    elif change == 'no-plugin-export':
        image = pe_fixture(('getPlugin', 'deleteMe', 'exports'))
    else:
        struct.pack_into('<I', image, 0x240, 0xffffff00)
    path = tmp_path / 'MyCareerTraining.dll'
    path.write_bytes(image)
    with pytest.raises(ValueError):
        inspect_plugin(path)


def test_windowless_self_test_failure_is_nonzero_and_has_a_durable_traceback(tmp_path, monkeypatch):
    from my_career_training import __main__ as entry
    monkeypatch.setattr(entry.sys, "argv", ["MyCareerTraining", "--self-test", "--data-dir", str(tmp_path)])
    monkeypatch.setattr(entry.sys, "stderr", None)
    def broken_runtime():
        raise RuntimeError("missing test runtime")
    monkeypatch.setattr(entry, "self_test", broken_runtime)
    assert entry.main() == 1
    assert "missing test runtime" in (tmp_path / "self-test-error.txt").read_text()
