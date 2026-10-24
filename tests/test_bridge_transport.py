"""Real Windows handle-sharing checks for the local in-game file bridge."""
from __future__ import annotations

import ctypes
import json
import sys
import threading
import time
from ctypes import wintypes

import pytest

from my_career_training.ingame import FileBridge, _read_shared


pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows handle sharing only")


def _open_handle(path, access, sharing):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = (
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
        wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
    )
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.CreateFileW(str(path), access, sharing, None, 3, 0x80, None)
    if handle == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    return kernel, handle


def test_state_publication_recovers_from_short_windows_reader_lock(tmp_path):
    pipe = FileBridge(tmp_path, lambda *_: None, lambda: {"error": ""})
    pipe.poll()
    kernel, handle = _open_handle(pipe.directory / "state.json", 0x80000000, 0x1 | 0x2)
    released = threading.Event()

    def release_after_short_read():
        time.sleep(0.06)
        kernel.CloseHandle(handle)
        released.set()

    reader = threading.Thread(target=release_after_short_read)
    reader.start()
    try:
        pipe.poll()
    finally:
        reader.join(timeout=2)
    assert released.is_set()
    assert json.loads((pipe.directory / "state.json").read_text())["bridge_session"] == pipe.session


def test_plugin_status_reader_allows_writer_delete_access(tmp_path):
    pipe = FileBridge(tmp_path, lambda *_: None, lambda: {}, clock=time.time)
    path = pipe.directory / "plugin-status.json"
    path.write_text(json.dumps({"published_at": time.time(), "bridge_session": pipe.session}))
    kernel, handle = _open_handle(path, 0x00010000, 0x1 | 0x2 | 0x4)
    try:
        status = pipe.plugin_status()
        assert status.get("bridge_session") == pipe.session, {"status": status, "read": _read_shared(path, 4096)}
    finally:
        kernel.CloseHandle(handle)


def test_state_publication_preserves_old_state_and_reports_persistent_denial(tmp_path):
    pipe = FileBridge(tmp_path, lambda *_: None, lambda: {"error": ""})
    pipe.poll()
    path = pipe.directory / "state.json"
    old_state = path.read_bytes()
    kernel, handle = _open_handle(path, 0x80000000, 0x1 | 0x2)
    try:
        with pytest.raises(OSError, match=r"Offline career state could not be published.*WinError (5|32)"):
            pipe.poll()
        assert path.read_bytes() == old_state
    finally:
        kernel.CloseHandle(handle)
    pipe.poll()
    assert json.loads(path.read_text())["bridge_session"] == pipe.session
