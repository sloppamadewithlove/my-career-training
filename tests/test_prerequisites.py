"""The optional BakkesMod setup is fetched as data, never run by the fetcher."""

import hashlib
import io
import struct
import zipfile
from pathlib import Path

import pytest

from my_career_training import prerequisites as setup


def _pe_bytes() -> bytes:
    content = bytearray(256)
    content[:2] = b"MZ"
    struct.pack_into("<I", content, 0x3C, 128)
    content[128:132] = b"PE\0\0"
    return bytes(content)


def _archive(name="BakkesModSetup.exe", content=None, *, extra=None, mode=None):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        entry = zipfile.ZipInfo(name)
        if mode is not None:
            entry.create_system = 3
            entry.external_attr = mode << 16
        archive.writestr(entry, _pe_bytes() if content is None else content)
        if extra is not None:
            archive.writestr("surprise.txt", extra)
    return buffer.getvalue()


def _spec(data: bytes, exe=None):
    expected_exe = _pe_bytes() if exe is None else exe
    return setup._AssetSpec(
        url="https://github.com/bakkesmodorg/BakkesModInjectorCpp/releases/download/test/BakkesModSetup.zip",
        version="test",
        zip_size=len(data),
        zip_sha256=hashlib.sha256(data).hexdigest(),
        exe_size=len(expected_exe),
        exe_sha256=hashlib.sha256(expected_exe).hexdigest(),
    )


class _Response(io.BytesIO):
    status = 200
    headers = {}

    def geturl(self):
        return "https://release-assets.githubusercontent.com/test"


def test_fetch_verifies_then_caches_without_running(tmp_path, monkeypatch):
    monkeypatch.setattr(setup.sys, "platform", "win32")
    data = _archive()
    opened = []
    progress = []

    def open_url(request, timeout):
        opened.append((request.full_url, timeout))
        return _Response(data)

    path = setup._prepare(tmp_path, _spec(data), opener=open_url, progress=lambda n, t: progress.append((n, t)))
    assert path.read_bytes() == _pe_bytes()
    assert len(opened) == 1
    assert opened[0][0].startswith("https://github.com/bakkesmodorg/")
    assert progress[-1] == (len(data), len(data))

    again = setup._prepare(tmp_path, _spec(data), opener=lambda *_: pytest.fail("cache should be used"))
    assert again == path


def test_tampered_download_and_existing_cache_are_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(setup.sys, "platform", "win32")
    data = _archive()
    expected = _spec(data)
    with pytest.raises(setup.PrerequisiteError, match="verification"):
        setup._prepare(tmp_path, expected, opener=lambda *_, **__: _Response(data[:-1] + b"X"))
    assert list(tmp_path.iterdir()) == []

    good = setup._prepare(tmp_path, expected, opener=lambda *_, **__: _Response(data))
    good.write_bytes(b"tampered")
    repaired = setup._prepare(tmp_path, expected, opener=lambda *_, **__: _Response(data))
    assert repaired.read_bytes() == _pe_bytes()


@pytest.mark.parametrize("name,extra,mode", [
    ("../BakkesModSetup.exe", None, None),
    ("folder/BakkesModSetup.exe", None, None),
    ("BakkesModSetup.exe", b"extra", None),
    ("BakkesModSetup.exe", None, 0o120777),
])
def test_unsafe_archive_rejected(tmp_path, monkeypatch, name, extra, mode):
    monkeypatch.setattr(setup.sys, "platform", "win32")
    data = _archive(name=name, extra=extra, mode=mode)
    with pytest.raises(setup.PrerequisiteError, match="archive"):
        setup._prepare(tmp_path, _spec(data), opener=lambda *_, **__: _Response(data))
    assert list(tmp_path.iterdir()) == []


def test_oversize_and_cancel_leave_no_partial_files(tmp_path, monkeypatch):
    monkeypatch.setattr(setup.sys, "platform", "win32")
    data = _archive()
    expected = _spec(data)
    with pytest.raises(setup.PrerequisiteError, match="size"):
        setup._prepare(tmp_path, expected, opener=lambda *_, **__: _Response(data + b"extra"))
    assert list(tmp_path.iterdir()) == []

    with pytest.raises(setup.DownloadCancelled):
        setup._prepare(tmp_path, expected, opener=lambda *_, **__: _Response(data), cancelled=lambda: True)
    assert list(tmp_path.iterdir()) == []


def test_invalid_executable_and_platform_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(setup.sys, "platform", "win32")
    bad_exe = b"not a PE image"
    data = _archive(content=bad_exe)
    with pytest.raises(setup.PrerequisiteError, match="executable"):
        setup._prepare(tmp_path, _spec(data, exe=bad_exe), opener=lambda *_, **__: _Response(data))
    assert list(tmp_path.iterdir()) == []

    monkeypatch.setattr(setup.sys, "platform", "darwin")
    with pytest.raises(setup.PrerequisiteError, match="Windows"):
        setup.prepare_bakkes_setup(Path(tmp_path), opener=lambda *_, **__: pytest.fail("network must not start"))
