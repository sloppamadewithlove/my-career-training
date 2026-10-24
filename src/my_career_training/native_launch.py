"""Own the compiled native offline helper and check its launch receipt.

This module starts ``MctNativeLauncher.exe`` from the package or repository
``runtime/native`` directory. The helper is the process that creates Rocket
League. End-user code cannot supply an executable, a DLL, a PID, or game
arguments. ``game_verified`` and ``production_ready`` stay false.

The build receipt is local integrity evidence for files that were staged
together. It is not a signature and it does not establish a trusted publisher.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import stat
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import NoReturn, TYPE_CHECKING

if TYPE_CHECKING:
    from .platforms import ProcessIdentity


PROTOCOL = 1
RECEIPT_TIMEOUT_SECONDS = 15.0
PLAN_MAX_BYTES = 8192
RECEIPT_MAX_BYTES = 4096
LINE_LIMIT = RECEIPT_MAX_BYTES + 1
PATH_MAX_CHARS = 480
STDERR_CAP = 16 * 1024
PRIVATE_PACKAGE_MAX = 16 * 1024 * 1024
HELPER_MAX = 32 * 1024 * 1024
FILE_VIEW_MAX = 16 * 1024 * 1024
BUILD_RECEIPT_MAX = 64 * 1024

SOURCE_EXE_RELATIVE = "Binaries/Win64/RocketLeague.exe"
SOURCE_EXE_SHA256 = "56b499a85ad927c6b5cc47cb4813f956dd9263405fdf4eddc65b669b53185bc7"
SOURCE_EXE_SIZE = 39727616
SOURCE_PACKAGE_RELATIVE = "TAGame/CookedPCConsole/GFX_MainMenu_SF.upk"
SOURCE_PACKAGE_SHA256 = "d3e0eeadd2766fa1fb10c2d220c22a84ab2f26fb6bbb89b414a26ef1fd6e2f65"
SOURCE_PACKAGE_SIZE = 3418271

OFFLINE_ARGUMENTS = (
    "-noeac",
    "-rlbot",
    "RLBot_ControllerURL=127.0.0.1:23233",
    "RLBot_PacketSendRate=240",
    "-nomovie",
)

HELPER_FILENAME = "MctNativeLauncher.exe"
FILE_VIEW_FILENAME = "MctNativeFileView64.dll"
NOTICE_FILENAME = "DETOURS-MIT-LICENSE.txt"
BUILD_RECEIPT_FILENAME = "native-launch-receipt.json"
RUNTIME_FILENAMES = (
    HELPER_FILENAME,
    FILE_VIEW_FILENAME,
    NOTICE_FILENAME,
    BUILD_RECEIPT_FILENAME,
)

# Upstream Detours 4.0.1 LICENSE.md (LF). Local evidence only; nothing is downloaded.
DETOURS_NOTICE_TEXT = """# Copyright (c) Microsoft Corporation

All rights reserved.

# MIT License

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
of the Software, and to permit persons to whom the Software is furnished to do
so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
DETOURS_NOTICE_BYTES = DETOURS_NOTICE_TEXT.encode("utf-8")
DETOURS_NOTICE_SHA256 = "b301808b732cfaa60df2b4b422d78cd97d2a15058b207e7e33f0535ba5170dd6"
DETOURS_NOTICE_SIZE = 1099

BUILD_RECEIPT_KIND = "mct_native_launch_runtime"
BUILD_RECEIPT_FIELDS = frozenset({
    "schema", "kind", "protocol", "machine",
    "helper_sha256", "helper_size",
    "file_view_sha256", "file_view_size",
    "detours_notice_sha256", "detours_notice_size",
    "source_exe_sha256", "source_exe_size",
    "source_package_sha256", "source_package_size",
    "game_verified", "production_ready",
})
PLAN_FIELDS = frozenset({
    "protocol", "session", "game_root", "private_package", "private_package_sha256",
})
LAUNCH_RECEIPT_FIELDS = frozenset({
    "protocol", "kind", "pid", "create_time", "executable", "session",
    "private_package", "private_package_sha256",
    "source_executable_sha256", "source_package_sha256",
    "game_verified", "production_ready", "file_view_observed",
})
ERROR_RECEIPT_FIELDS = frozenset({
    "protocol", "kind", "error", "game_verified", "production_ready", "file_view_observed",
})
EXIT_RECEIPT_FIELDS = frozenset({
    "protocol", "kind", "pid", "create_time", "exit_code", "session", "executable",
    "game_verified", "production_ready", "file_view_observed",
})

_SHA = re.compile(r"[0-9a-f]{64}\Z")
_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z")
_DRIVE = re.compile(r"[A-Za-z]:\\")
_DEVICES = frozenset({
    "con", "prn", "aux", "nul",
    *(f"com{index}" for index in range(1, 10)),
    *(f"lpt{index}" for index in range(1, 10)),
})
_AMD64 = 0x8664
_PE32_PLUS = 0x20B
_IMAGE_EXE = 0x0002
_IMAGE_DLL = 0x2000
# Same access, share, and flags as native_launcher kMctHoldAccess / kMctHoldShare / kMctHoldFlags.
_HOLD_ACCESS = 0x0001 | 0x0080  # FILE_READ_DATA | FILE_READ_ATTRIBUTES
_HOLD_SHARE = 0x00000001  # FILE_SHARE_READ; write (0x2) and delete (0x4) stay off
_HOLD_FLAGS = 0x00000080 | 0x00200000 | 0x08000000
_FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
_FILE_ATTRIBUTE_DIRECTORY = 0x00000010
_FILE_ATTRIBUTE_DEVICE = 0x00000040
_FILE_TYPE_DISK = 0x0001
_HANDLE_FLAG_INHERIT = 0x00000001
_OPEN_EXISTING = 3
_ERROR_HANDLE_EOF = 38
_VOLUME_NAME_DOS = 0x0
_FILE_NAME_OPENED = 0x8
_FILE_NAME_NORMALIZED = 0x0
_RETAINED: list[subprocess.Popen] = []
_RETAINED_LOCK = threading.Lock()


class NativeLaunchError(RuntimeError):
    """The helper was not started, or it exited and no game remains visible."""

    defer_restore = False

    def __init__(
        self,
        message: str,
        *,
        code: str = "refused",
        helper: subprocess.Popen | None = None,
        receipt: dict | None = None,
        session: str = "",
        private_package: str = "",
    ):
        super().__init__(message)
        self.code = code
        self.helper = helper
        self.receipt = receipt
        self.session = session
        self.private_package = private_package
        self.game_verified = False
        self.production_ready = False
        self.child_created = False
        if helper is not None:
            _retain(helper)

    def helper_exited(self) -> bool:
        return _helper_exited(self.helper)

    def release(self) -> bool:
        """Drop a helper that has already exited. Leave a running helper registered."""
        return _release_helper(self.helper)


class NativeLaunchUncertain(RuntimeError):
    """A child game may exist. Leave the helper running and defer plugin restore."""

    defer_restore = True

    def __init__(
        self,
        message: str,
        *,
        reason: str,
        helper: subprocess.Popen,
        helper_pid: int | None,
        helper_running: bool,
        games: tuple[int, ...] | None,
        receipt: dict | None,
        session: str,
        private_package: str,
    ):
        super().__init__(message)
        self.reason = reason
        self.code = reason
        self.helper = helper
        self.helper_pid = helper_pid
        self.helper_running = helper_running
        self.games = games
        self.receipt = receipt
        self.session = session
        self.private_package = private_package
        self.game_verified = False
        self.production_ready = False
        self.defer_restore = True
        _retain(helper)

    def helper_exited(self) -> bool:
        return _helper_exited(self.helper)

    def release(self) -> bool:
        return _release_helper(self.helper)


class _Signal(Exception):
    def __init__(self, reason: str):
        self.reason = reason


@dataclass
class OwnedNativeLaunch:
    """Helper plus the Rocket League child identity the receipt named.

    ``status`` is ``ready`` while the helper and that child are both alive,
    ``reaping`` after the child exits while the helper is still alive,
    ``degraded`` when the helper has exited and the child is still alive, and
    ``exited`` after both are gone. ``ready`` means the receipt matched. It
    does not mean the file view ran inside the game.
    """

    identity: ProcessIdentity
    helper: subprocess.Popen
    receipt: dict
    status: str = "ready"
    exit_receipt: dict | None = None
    game_verified: bool = False
    production_ready: bool = False
    file_view_observed: bool = False
    _exit_thread: threading.Thread | None = field(default=None, repr=False)
    _exit_box: dict = field(default_factory=dict, repr=False)

    def poll(self) -> str:
        """Refresh helper and child status. Does not stop either process."""
        self._collect_exit_receipt()
        helper_running = not _helper_exited(self.helper)
        owned = _identity_still_owned(self.identity)
        if helper_running and owned is not False:
            self.status = "ready"
        elif helper_running and owned is False:
            self.status = "reaping"
        elif not helper_running and owned is not False:
            self.status = "degraded"
        else:
            self.status = "exited"
        self.game_verified = False
        self.production_ready = False
        self.file_view_observed = False
        return self.status

    def helper_exited(self) -> bool:
        return _helper_exited(self.helper)

    def release(self) -> bool:
        """Drop the helper after it has exited. A running helper stays registered."""
        if not _release_helper(self.helper):
            return False
        return True

    @property
    def view_active(self) -> bool:
        return False

    @property
    def lock_active(self) -> bool:
        return False

    def _collect_exit_receipt(self) -> None:
        thread = self._exit_thread
        if thread is None or self.exit_receipt is not None or self._exit_box.get("done"):
            return
        if thread.is_alive() and not _helper_exited(self.helper):
            return
        thread.join(0.2)
        self._exit_box["done"] = True
        raw = self._exit_box.get("raw")
        if type(raw) is not bytes:
            return
        try:
            self.exit_receipt = _parse_exit_receipt(raw, self.identity, self.receipt["session"])
        except _Signal:
            self.exit_receipt = None


def trusted_runtime_directories() -> tuple[Path, ...]:
    """Package ``runtime/native``, then the development repository copy."""
    package = Path(__file__).resolve().parent
    return (
        package / "runtime" / "native",
        package.parent.parent / "runtime" / "native",
    )


def retained_helpers() -> tuple[subprocess.Popen, ...]:
    """Helpers this process must keep alive until they exit on their own."""
    with _RETAINED_LOCK:
        return tuple(_RETAINED)


def build_runtime_receipt(
    helper_sha256: str,
    helper_size: int,
    file_view_sha256: str,
    file_view_size: int,
) -> dict:
    """Return the exact build-receipt object a later stager can write.

    Source hashes, the Detours notice, and both ready flags are fixed here.
    """
    _sha_text(helper_sha256, "Helper hash")
    _sha_text(file_view_sha256, "File-view hash")
    _positive_size(helper_size, HELPER_MAX, "Helper size")
    _positive_size(file_view_size, FILE_VIEW_MAX, "File-view size")
    return {
        "schema": 1,
        "kind": BUILD_RECEIPT_KIND,
        "protocol": PROTOCOL,
        "machine": "AMD64",
        "helper_sha256": helper_sha256,
        "helper_size": helper_size,
        "file_view_sha256": file_view_sha256,
        "file_view_size": file_view_size,
        "detours_notice_sha256": DETOURS_NOTICE_SHA256,
        "detours_notice_size": DETOURS_NOTICE_SIZE,
        "source_exe_sha256": SOURCE_EXE_SHA256,
        "source_exe_size": SOURCE_EXE_SIZE,
        "source_package_sha256": SOURCE_PACKAGE_SHA256,
        "source_package_size": SOURCE_PACKAGE_SIZE,
        "game_verified": False,
        "production_ready": False,
    }


def validate_native_runtime(directory: str | Path | None = None) -> dict:
    """Check one trusted runtime directory and return its build receipt."""
    runtime = _load_runtime(directory)
    receipt = dict(runtime.receipt)
    receipt["game_verified"] = False
    receipt["production_ready"] = False
    return receipt


def launch_native_offline(
    game_root: str | Path,
    private_package: str | Path,
    private_package_sha256: str,
    session: str,
    *,
    runtime_directory: str | Path | None = None,
) -> OwnedNativeLaunch:
    """Start the pinned helper with one JSON plan and accept only its child."""
    if sys.platform != "win32":
        raise NativeLaunchError(
            "Native offline launch requires Windows.",
            code="not_windows",
        )
    canonical = _canonical_session(session)
    digest = _sha_text(private_package_sha256, "Private package hash")
    root = _real_directory(_as_path(game_root, "Game root"), "Game root")
    private = _real_file(_as_path(private_package, "Private package"), "Private package", PRIVATE_PACKAGE_MAX)
    _reject_package_layout(root, private)
    if len(str(root)) > PATH_MAX_CHARS or len(str(private)) > PATH_MAX_CHARS:
        raise NativeLaunchError("Path is too long.", code="bad_path", session=canonical, private_package=str(private))
    if _hash_file(private, PRIVATE_PACKAGE_MAX) != digest:
        raise NativeLaunchError(
            "Private package hash does not match the launch request.",
            code="private_hash_mismatch",
            session=canonical,
            private_package=str(private),
        )
    _require_quiet_games()
    runtime = _load_runtime(runtime_directory)
    plan = {
        "protocol": PROTOCOL,
        "session": canonical,
        "game_root": str(root),
        "private_package": str(private),
        "private_package_sha256": digest,
    }
    if set(plan) != PLAN_FIELDS:
        raise NativeLaunchError("Launch plan fields are not the fixed set.", code="plan")
    payload = json.dumps(plan, ensure_ascii=True, separators=(",", ":")).encode("ascii") + b"\n"
    if len(payload) > PLAN_MAX_BYTES:
        raise NativeLaunchError("Launch plan is too large.", code="plan_too_large", session=canonical)
    _require_quiet_games()
    held = _open_held_helper(
        runtime.helper,
        runtime.receipt["helper_size"],
        runtime.receipt["helper_sha256"],
    )
    try:
        try:
            process = _popen([str(held.path), "--launch-offline"], **_spawn_kwargs())
        except OSError as exc:
            raise NativeLaunchError(
                "Native launcher did not start.",
                code="helper_start_failed",
                session=canonical,
                private_package=str(private),
            ) from exc
    finally:
        held.close()
    _retain(process)
    _drain_stderr(getattr(process, "stderr", None))
    context = {
        "process": process,
        "session": canonical,
        "private_package": str(private),
        "root": root,
        "private": private,
        "exe": root / SOURCE_EXE_RELATIVE,
        "digest": digest,
    }
    deadline = time.monotonic() + RECEIPT_TIMEOUT_SECONDS
    try:
        _write_plan(process, payload, max(0.0, deadline - time.monotonic()))
        raw = _read_bounded_line(process.stdout, max(0.0, deadline - time.monotonic()))
        receipt = _parse_wire_object(raw)
    except _Signal as signal:
        _fail_after_start(signal.reason, **context)
    except OSError:
        _fail_after_start("malformed", **context)
    try:
        return _accept_receipt(receipt, **context)
    except _Signal as signal:
        _fail_after_start(signal.reason, receipt=receipt, **context)


class _HeldHelper:
    """Read-only handle kept open until CreateProcess has mapped the helper."""

    def __init__(self, path: Path, handle: int):
        self.path = path
        self._handle = handle

    def close(self) -> None:
        handle = self._handle
        self._handle = 0
        if handle:
            _close_held_handle(handle)


def _open_held_helper(path: Path, expected_size: int, expected_digest: str) -> _HeldHelper:
    """Re-check the helper on a share-read handle and keep that handle for the caller."""
    if sys.platform != "win32":
        raise NativeLaunchError("Native offline launch requires Windows.", code="not_windows")
    if _HOLD_SHARE & 0x6:
        raise NativeLaunchError("Native launcher hold must deny write and delete.", code="runtime_hash")
    if type(expected_size) is not int or not 0 < expected_size <= HELPER_MAX:
        raise NativeLaunchError("Native runtime file size does not match its receipt.", code="runtime_hash")
    if type(expected_digest) is not str or _SHA.fullmatch(expected_digest) is None:
        raise NativeLaunchError("Native runtime file hash does not match its receipt.", code="runtime_hash")
    return _win32_hold_helper(path, expected_size, expected_digest)


def _win32_hold_helper(path: Path, expected_size: int, expected_digest: str) -> _HeldHelper:
    kernel, ctypes = _win32_kernel()
    handle = _create_held_handle(kernel, ctypes, path)
    owned = False
    try:
        _clear_inherit(kernel, handle)
        _require_opened_path(kernel, ctypes, handle, path)
        before = _held_identity(kernel, ctypes, handle, expected_size)
        blob = _read_held_bytes(kernel, ctypes, handle, expected_size)
        after = _held_identity(kernel, ctypes, handle, expected_size)
        if after != before:
            raise NativeLaunchError(
                "Native launcher file changed while it was checked.",
                code="runtime_hash",
            )
        if hashlib.sha256(blob).hexdigest() != expected_digest:
            raise NativeLaunchError("Native runtime file hash does not match its receipt.", code="runtime_hash")
        _require_pe(blob, "exe")
        _require_opened_path(kernel, ctypes, handle, path)
        held = _HeldHelper(path, handle)
        owned = True
        return held
    finally:
        if not owned:
            _close_held_handle(handle)


def _win32_kernel():
    cached = getattr(_win32_kernel, "bound", None)
    if cached is not None:
        return cached
    import ctypes
    from ctypes import wintypes

    class _FileTime(ctypes.Structure):
        _fields_ = (("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD))

    class _ByHandle(ctypes.Structure):
        _fields_ = (
            ("dwFileAttributes", wintypes.DWORD),
            ("ftCreationTime", _FileTime),
            ("ftLastAccessTime", _FileTime),
            ("ftLastWriteTime", _FileTime),
            ("dwVolumeSerialNumber", wintypes.DWORD),
            ("nFileSizeHigh", wintypes.DWORD),
            ("nFileSizeLow", wintypes.DWORD),
            ("nNumberOfLinks", wintypes.DWORD),
            ("nFileIndexHigh", wintypes.DWORD),
            ("nFileIndexLow", wintypes.DWORD),
        )

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
        wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
    ]
    kernel.CreateFileW.restype = ctypes.c_void_p
    kernel.SetHandleInformation.argtypes = [ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD]
    kernel.SetHandleInformation.restype = wintypes.BOOL
    kernel.GetFinalPathNameByHandleW.argtypes = [ctypes.c_void_p, wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD]
    kernel.GetFinalPathNameByHandleW.restype = wintypes.DWORD
    kernel.GetFileInformationByHandle.argtypes = [ctypes.c_void_p, ctypes.POINTER(_ByHandle)]
    kernel.GetFileInformationByHandle.restype = wintypes.BOOL
    kernel.GetFileSizeEx.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_longlong)]
    kernel.GetFileSizeEx.restype = wintypes.BOOL
    kernel.GetFileType.argtypes = [ctypes.c_void_p]
    kernel.GetFileType.restype = wintypes.DWORD
    kernel.ReadFile.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p,
    ]
    kernel.ReadFile.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel.CloseHandle.restype = wintypes.BOOL
    kernel.by_handle = _ByHandle
    _win32_kernel.bound = (kernel, ctypes)
    return _win32_kernel.bound


def _hold_open_name(path: Path) -> str:
    text = str(path)
    if text.startswith("\\\\?\\") or _DRIVE.match(text) is None:
        return text
    return "\\\\?\\" + text


def _invalid_handle(ctypes) -> int:
    return ctypes.c_void_p(-1).value


def _create_held_handle(kernel, ctypes, path: Path) -> int:
    handle = kernel.CreateFileW(
        _hold_open_name(path),
        _HOLD_ACCESS,
        _HOLD_SHARE,
        None,
        _OPEN_EXISTING,
        _HOLD_FLAGS,
        None,
    )
    if not handle or handle == _invalid_handle(ctypes):
        err = ctypes.get_last_error()
        raise NativeLaunchError(
            "Native launcher file could not be opened.",
            code="runtime_hash",
        ) from OSError(err, "CreateFileW")
    return handle


def _clear_inherit(kernel, handle: int) -> None:
    if not kernel.SetHandleInformation(handle, _HANDLE_FLAG_INHERIT, 0):
        raise NativeLaunchError("Native launcher file could not be opened.", code="runtime_hash")


def _close_held_handle(handle: int) -> None:
    if not handle or sys.platform != "win32":
        return
    kernel, _ctypes = _win32_kernel()
    kernel.CloseHandle(handle)


def _final_dos_path(kernel, ctypes, handle: int, flags: int) -> str:
    buffer = ctypes.create_unicode_buffer(1024)
    length = kernel.GetFinalPathNameByHandleW(handle, buffer, 1024, flags)
    if length <= 0 or length >= 1024:
        return ""
    return buffer.value


def _dos_body(text: str) -> str:
    body = text
    if body.startswith("\\\\?\\"):
        body = body[4:]
        if body[:4].casefold() == "unc\\":
            return ""
    return os.path.normcase(os.path.normpath(body))


def _dos_body_matches(final: str, requested: Path) -> bool:
    left = _dos_body(final)
    right = _dos_body(str(requested))
    return bool(left) and left == right


def _require_opened_path(kernel, ctypes, handle: int, path: Path) -> None:
    opened = _VOLUME_NAME_DOS | _FILE_NAME_OPENED
    normalized = _VOLUME_NAME_DOS | _FILE_NAME_NORMALIZED
    for flags in (opened, normalized):
        final = _final_dos_path(kernel, ctypes, handle, flags)
        if final and _dos_body_matches(final, path):
            return
    raise NativeLaunchError("Native launcher file is not the opened path.", code="runtime_hash")


def _held_identity(kernel, ctypes, handle: int, expected_size: int) -> tuple:
    info = kernel.by_handle()
    if not kernel.GetFileInformationByHandle(handle, ctypes.byref(info)):
        raise NativeLaunchError("Native launcher file could not be read.", code="runtime_hash")
    size = ctypes.c_longlong(0)
    if not kernel.GetFileSizeEx(handle, ctypes.byref(size)) or size.value < 0:
        raise NativeLaunchError("Native launcher file could not be read.", code="runtime_hash")
    indexed = (int(info.nFileSizeHigh) << 32) | int(info.nFileSizeLow)
    if int(size.value) != indexed:
        raise NativeLaunchError("Native launcher file changed while it was checked.", code="runtime_hash")
    attributes = int(info.dwFileAttributes)
    if attributes & _FILE_ATTRIBUTE_REPARSE_POINT or attributes & _FILE_ATTRIBUTE_DIRECTORY:
        raise NativeLaunchError("Native launcher file is not a regular file.", code="reparse")
    if attributes & _FILE_ATTRIBUTE_DEVICE or kernel.GetFileType(handle) != _FILE_TYPE_DISK:
        raise NativeLaunchError("Native launcher file is not a regular file.", code="reparse")
    if int(size.value) != expected_size:
        raise NativeLaunchError("Native runtime file size does not match its receipt.", code="runtime_hash")
    return (
        int(info.dwVolumeSerialNumber),
        int(info.nFileIndexHigh),
        int(info.nFileIndexLow),
        int(size.value),
        attributes,
    )


def _read_held_bytes(kernel, ctypes, handle: int, expected_size: int) -> bytes:
    from ctypes import wintypes
    remaining = expected_size
    chunks = []
    while remaining:
        chunk = min(1024 * 1024, remaining)
        buf = ctypes.create_string_buffer(chunk)
        got = wintypes.DWORD(0)
        ok = kernel.ReadFile(handle, buf, chunk, ctypes.byref(got), None)
        if not ok or got.value != chunk:
            raise NativeLaunchError("Native launcher file could not be read.", code="runtime_hash")
        chunks.append(buf.raw[:got.value])
        remaining -= got.value
    extra = ctypes.create_string_buffer(1)
    got = wintypes.DWORD(0)
    ok = kernel.ReadFile(handle, extra, 1, ctypes.byref(got), None)
    if ok and got.value == 0:
        return b"".join(chunks)
    if not ok and ctypes.get_last_error() == _ERROR_HANDLE_EOF and got.value == 0:
        return b"".join(chunks)
    raise NativeLaunchError("Native runtime file size does not match its receipt.", code="runtime_hash")


def _popen(args, **kwargs):
    return subprocess.Popen(args, **kwargs)


def _spawn_kwargs() -> dict:
    kwargs = {
        "stdin": subprocess.PIPE,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "shell": False,
        "cwd": None,
        "env": None,
        "close_fds": True,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    return kwargs


def _game_processes():
    from .platforms import game_processes
    return game_processes()


def _process(pid: int):
    import psutil
    return psutil.Process(pid)


def _retain(process: subprocess.Popen | None) -> None:
    if process is None:
        return
    with _RETAINED_LOCK:
        if process not in _RETAINED:
            _RETAINED.append(process)


def _drop(process: subprocess.Popen) -> None:
    with _RETAINED_LOCK:
        _RETAINED[:] = [item for item in _RETAINED if item is not process]


def _helper_exited(process: subprocess.Popen | None) -> bool:
    if process is None:
        return True
    try:
        return process.poll() is not None
    except OSError:
        return False


def _release_helper(process: subprocess.Popen | None) -> bool:
    if process is None:
        return True
    if not _helper_exited(process):
        return False
    _close_pipes(process)
    _drop(process)
    return True


def _close_pipes(process: subprocess.Popen) -> None:
    for name in ("stdin", "stdout", "stderr"):
        stream = getattr(process, name, None)
        if stream is None:
            continue
        try:
            stream.close()
        except OSError:
            continue


def _as_path(value: object, label: str) -> Path:
    if type(value) is not str and not isinstance(value, Path):
        raise NativeLaunchError(f"{label} is not a path.", code="bad_path")
    if type(value) is str and ("\x00" in value or "\n" in value or "\r" in value):
        raise NativeLaunchError(f"{label} is not a path.", code="bad_path")
    return Path(value) if type(value) is str else value


def _syntax(path: Path, label: str) -> None:
    text = str(path)
    if "\x00" in text or "\n" in text or "\r" in text or '"' in text or len(text) > PATH_MAX_CHARS:
        raise NativeLaunchError(f"{label} is not allowed.", code="bad_path")
    if not path.is_absolute():
        raise NativeLaunchError(f"{label} must be absolute.", code="bad_path")
    raw = text.replace("/", "\\")
    if raw.startswith("\\\\") or raw.startswith("\\"):
        raise NativeLaunchError(f"{label} must be a local drive path.", code="bad_path")
    if _DRIVE.match(raw) is None:
        raise NativeLaunchError(f"{label} must be a local drive path.", code="bad_path")
    for part in path.parts[1:]:
        if part in ("", ".", "..") or part.endswith((" ", ".")) or ":" in part or "/" in part or "\\" in part:
            raise NativeLaunchError(f"{label} is not allowed.", code="bad_path")
        if part.casefold().split(".", 1)[0] in _DEVICES:
            raise NativeLaunchError(f"{label} uses a device name.", code="bad_path")


def _is_reparse(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        checker = getattr(path, "is_junction", None)
        if checker is not None and checker():
            return True
        info = path.lstat()
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise NativeLaunchError("Path could not be checked.", code="reparse") from exc
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(getattr(info, "st_file_attributes", 0) & flag)


def _reject_reparse_chain(path: Path) -> None:
    current = path
    seen: list[Path] = []
    while True:
        seen.append(current)
        if current.parent == current:
            break
        current = current.parent
    for candidate in reversed(seen):
        if _is_reparse(candidate):
            raise NativeLaunchError("A symlink or reparse point is not allowed.", code="reparse")


def _real_directory(path: Path, label: str) -> Path:
    _syntax(path, label)
    _reject_reparse_chain(path)
    try:
        info = path.lstat()
    except OSError as exc:
        raise NativeLaunchError(f"{label} is not a directory.", code="bad_path") from exc
    if not stat.S_ISDIR(info.st_mode) or _is_reparse(path):
        raise NativeLaunchError(f"{label} is not a directory.", code="bad_path")
    try:
        resolved = path.resolve()
    except OSError as exc:
        raise NativeLaunchError(f"{label} is not a directory.", code="bad_path") from exc
    if os.path.normcase(str(resolved)) != os.path.normcase(str(Path(os.path.abspath(path)))):
        raise NativeLaunchError(f"{label} is a path alias.", code="bad_path")
    return resolved


def _real_file(path: Path, label: str, limit: int) -> Path:
    _syntax(path, label)
    _reject_reparse_chain(path)
    if path.suffix.casefold() != ".upk":
        raise NativeLaunchError(f"{label} must be a private .upk package.", code="bad_path")
    try:
        info = path.lstat()
    except OSError as exc:
        raise NativeLaunchError(f"{label} is not a regular file.", code="bad_path") from exc
    if not stat.S_ISREG(info.st_mode) or _is_reparse(path):
        raise NativeLaunchError(f"{label} is not a regular file.", code="bad_path")
    if type(info.st_size) is not int or not 0 < info.st_size <= limit:
        raise NativeLaunchError(f"{label} size is not allowed.", code="bad_size")
    try:
        resolved = path.resolve()
    except OSError as exc:
        raise NativeLaunchError(f"{label} is not a regular file.", code="bad_path") from exc
    if os.path.normcase(str(resolved)) != os.path.normcase(str(Path(os.path.abspath(path)))):
        raise NativeLaunchError(f"{label} is a path alias.", code="bad_path")
    return resolved


def _same_file(left: Path, right: Path) -> bool:
    try:
        left_resolved = left.resolve()
        right_resolved = right.resolve()
    except OSError:
        return False
    if os.path.normcase(str(left_resolved)) != os.path.normcase(str(right_resolved)):
        return False
    try:
        return bool(left.samefile(right))
    except OSError:
        return False


def _reject_package_layout(root: Path, private: Path) -> None:
    if _is_inside(private, root) or _same_file(private, root):
        raise NativeLaunchError(
            "Private package must be outside the installed game.",
            code="private_inside_game",
        )
    exe = _source_file(root, SOURCE_EXE_RELATIVE, SOURCE_EXE_SIZE, "Rocket League executable", "source_exe")
    package = _source_file(
        root, SOURCE_PACKAGE_RELATIVE, SOURCE_PACKAGE_SIZE, "Menu package", "source_package",
    )
    if _same_file(private, package) or _same_file(private, exe):
        raise NativeLaunchError(
            "Private package must be a different file from the installed game files.",
            code="private_overlaps_source",
        )


def _source_file(root: Path, relative: str, expected: int, label: str, code: str) -> Path:
    path = root.joinpath(*relative.split("/"))
    _syntax(path, label)
    _reject_reparse_chain(path)
    try:
        info = path.lstat()
    except OSError as exc:
        raise NativeLaunchError(f"{label} was not found.", code=f"{code}_missing") from exc
    if not stat.S_ISREG(info.st_mode) or _is_reparse(path):
        raise NativeLaunchError(f"{label} is not a regular file.", code=f"{code}_missing")
    if info.st_size != expected:
        raise NativeLaunchError(f"{label} size is not the supported build.", code=f"{code}_size")
    return path.resolve()


def _is_inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except (OSError, ValueError):
        return False
    return True


def _hash_file(path: Path, limit: int) -> str:
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise NativeLaunchError("File could not be read.", code="bad_path") from exc
    try:
        info = os.fstat(descriptor)
        flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        if not stat.S_ISREG(info.st_mode) or getattr(info, "st_file_attributes", 0) & flag:
            raise NativeLaunchError("File is not a regular file.", code="reparse")
        if info.st_size > limit:
            raise NativeLaunchError("File size is not allowed.", code="bad_size")
        digest = hashlib.sha256()
        remaining = info.st_size
        while remaining:
            chunk = os.read(descriptor, min(1024 * 1024, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            digest.update(chunk)
        if remaining:
            raise NativeLaunchError("File could not be read.", code="bad_path")
        return digest.hexdigest()
    finally:
        os.close(descriptor)


def _read_exact(path: Path, expected: int) -> bytes:
    if type(expected) is not int or expected < 0:
        raise NativeLaunchError("Native runtime file size does not match its receipt.", code="runtime_hash")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise NativeLaunchError("Native runtime file could not be read.", code="runtime_hash") from exc
    try:
        info = os.fstat(descriptor)
        flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        if not stat.S_ISREG(info.st_mode) or getattr(info, "st_file_attributes", 0) & flag:
            raise NativeLaunchError("Native runtime file is not a regular file.", code="reparse")
        if info.st_size != expected:
            raise NativeLaunchError("Native runtime file size does not match its receipt.", code="runtime_hash")
        blob = os.read(descriptor, expected + 1)
    except OSError as exc:
        raise NativeLaunchError("Native runtime file could not be read.", code="runtime_hash") from exc
    finally:
        os.close(descriptor)
    if len(blob) != expected:
        raise NativeLaunchError("Native runtime file size does not match its receipt.", code="runtime_hash")
    return blob


def _canonical_session(value: object) -> str:
    if type(value) is not str or _UUID.fullmatch(value) is None:
        raise NativeLaunchError("Session must be a canonical lowercase UUID.", code="bad_session")
    return value


def _sha_text(value: object, label: str) -> str:
    if type(value) is not str or _SHA.fullmatch(value) is None:
        raise NativeLaunchError(f"{label} must be lowercase SHA-256.", code="bad_hash")
    return value


def _positive_size(value: object, limit: int, label: str) -> int:
    if type(value) is not int or not 0 < value <= limit:
        raise NativeLaunchError(f"{label} is not allowed.", code="bad_size")
    return value


def _pairs(items: list[tuple[str, object]]) -> dict:
    keys = []
    for key, _value in items:
        if type(key) is not str or key in keys:
            raise NativeLaunchError("JSON object repeats a field.", code="runtime_receipt")
        keys.append(key)
    return dict(items)


def _bad_token(token: str):
    raise NativeLaunchError(f"JSON value {token} is not allowed.", code="runtime_receipt")


def _finite_float(text: str) -> float:
    value = float(text)
    if not math.isfinite(value):
        raise NativeLaunchError("JSON number is not finite.", code="runtime_receipt")
    return value


def _json_object(text: str) -> dict:
    try:
        value = json.loads(
            text,
            object_pairs_hook=_pairs,
            parse_constant=_bad_token,
            parse_float=_finite_float,
        )
    except NativeLaunchError:
        raise
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        raise NativeLaunchError("JSON object is not valid.", code="runtime_receipt") from exc
    if type(value) is not dict:
        raise NativeLaunchError("JSON value is not an object.", code="runtime_receipt")
    return value


def _load_runtime(directory: str | Path | None) -> _Runtime:
    chosen = _select_runtime(directory)
    names = {item.name for item in chosen.iterdir()}
    if names != set(RUNTIME_FILENAMES):
        raise NativeLaunchError(
            "Native runtime directory must contain only the helper, file view, notice, and receipt.",
            code="runtime_allowlist",
        )
    for name in RUNTIME_FILENAMES:
        path = chosen / name
        if path.parent != chosen or _is_reparse(path) or not path.is_file():
            raise NativeLaunchError("Native runtime file is not a regular file.", code="runtime_allowlist")
    receipt_path = chosen / BUILD_RECEIPT_FILENAME
    try:
        receipt_size = receipt_path.lstat().st_size
    except OSError as exc:
        raise NativeLaunchError("Native runtime receipt is not valid.", code="runtime_receipt") from exc
    if type(receipt_size) is not int or not 0 < receipt_size <= BUILD_RECEIPT_MAX:
        raise NativeLaunchError("Native runtime receipt is not valid.", code="runtime_receipt")
    receipt_blob = _read_exact(receipt_path, receipt_size)
    if receipt_blob.startswith(b"\xef\xbb\xbf"):
        raise NativeLaunchError("Native runtime receipt is not valid.", code="runtime_receipt")
    try:
        text = receipt_blob.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise NativeLaunchError("Native runtime receipt is not valid.", code="runtime_receipt") from exc
    try:
        receipt = _json_object(text)
    except NativeLaunchError as exc:
        raise NativeLaunchError("Native runtime receipt is not valid.", code="runtime_receipt") from exc
    _validate_build_receipt(receipt)
    helper = _validate_image(
        chosen / HELPER_FILENAME, receipt["helper_sha256"], receipt["helper_size"], "exe",
    )
    file_view = _validate_image(
        chosen / FILE_VIEW_FILENAME, receipt["file_view_sha256"], receipt["file_view_size"], "dll",
    )
    notice = _validate_notice(chosen / NOTICE_FILENAME, receipt)
    return _Runtime(chosen, helper, file_view, notice, receipt)


def _select_runtime(directory: str | Path | None) -> Path:
    trusted = []
    for candidate in trusted_runtime_directories():
        try:
            trusted.append(_real_directory(candidate, "Runtime directory"))
        except NativeLaunchError:
            continue
    if directory is None:
        if not trusted:
            raise NativeLaunchError("Native launcher runtime is not installed.", code="runtime_missing")
        return trusted[0]
    chosen = _real_directory(_as_path(directory, "Runtime directory"), "Runtime directory")
    if not any(_same_file(chosen, item) for item in trusted):
        raise NativeLaunchError(
            "Native launcher runtime is not in a trusted location.",
            code="untrusted_runtime",
        )
    return chosen


def _validate_build_receipt(receipt: dict) -> None:
    if set(receipt) != BUILD_RECEIPT_FIELDS:
        raise NativeLaunchError("Native runtime receipt fields are not the fixed set.", code="runtime_receipt")
    if (receipt["schema"] != 1 or receipt["kind"] != BUILD_RECEIPT_KIND
            or receipt["protocol"] != PROTOCOL or receipt["machine"] != "AMD64"):
        raise NativeLaunchError("Native runtime receipt identity is not supported.", code="runtime_receipt")
    if type(receipt["schema"]) is not int or type(receipt["protocol"]) is not int:
        raise NativeLaunchError("Native runtime receipt identity is not supported.", code="runtime_receipt")
    _flag_pair(receipt)
    _sha_text(receipt["helper_sha256"], "Helper hash")
    _sha_text(receipt["file_view_sha256"], "File-view hash")
    _positive_size(receipt["helper_size"], HELPER_MAX, "Helper size")
    _positive_size(receipt["file_view_size"], FILE_VIEW_MAX, "File-view size")
    if (receipt["detours_notice_sha256"] != DETOURS_NOTICE_SHA256
            or receipt["detours_notice_size"] != DETOURS_NOTICE_SIZE):
        raise NativeLaunchError("Detours notice pin does not match this build.", code="runtime_notice")
    if (receipt["source_exe_sha256"] != SOURCE_EXE_SHA256 or receipt["source_exe_size"] != SOURCE_EXE_SIZE
            or receipt["source_package_sha256"] != SOURCE_PACKAGE_SHA256
            or receipt["source_package_size"] != SOURCE_PACKAGE_SIZE):
        raise NativeLaunchError("Supported game pins do not match this build.", code="runtime_receipt")


def _flag_pair(receipt: dict) -> None:
    if receipt.get("game_verified") is not False or receipt.get("production_ready") is not False:
        raise NativeLaunchError("Native runtime cannot claim a verified game.", code="runtime_receipt")


def _validate_image(path: Path, digest: str, size: int, kind: str) -> Path:
    blob = _read_exact(path, size)
    if hashlib.sha256(blob).hexdigest() != digest:
        raise NativeLaunchError("Native runtime file hash does not match its receipt.", code="runtime_hash")
    _require_pe(blob, kind)
    return path.resolve()


def _validate_notice(path: Path, receipt: dict) -> Path:
    blob = _read_exact(path, receipt["detours_notice_size"])
    if hashlib.sha256(blob).hexdigest() != receipt["detours_notice_sha256"] or blob != DETOURS_NOTICE_BYTES:
        raise NativeLaunchError("Detours notice does not match the pinned license.", code="runtime_notice")
    return path.resolve()


def _require_pe(blob: bytes, kind: str) -> None:
    if len(blob) < 64 or blob[:2] != b"MZ":
        raise NativeLaunchError("Native runtime binary is not a Windows executable.", code="runtime_pe")
    offset = int.from_bytes(blob[60:64], "little")
    if offset < 64 or offset > 4096 or offset + 26 > len(blob) or blob[offset:offset + 4] != b"PE\0\0":
        raise NativeLaunchError("Native runtime binary is not a Windows executable.", code="runtime_pe")
    machine = int.from_bytes(blob[offset + 4:offset + 6], "little")
    characteristics = int.from_bytes(blob[offset + 22:offset + 24], "little")
    magic = int.from_bytes(blob[offset + 24:offset + 26], "little")
    if machine != _AMD64 or magic != _PE32_PLUS:
        raise NativeLaunchError("Native runtime binary is not AMD64 PE32+.", code="runtime_pe")
    if characteristics & _IMAGE_EXE == 0:
        raise NativeLaunchError("Native runtime binary is not executable.", code="runtime_pe")
    is_dll = bool(characteristics & _IMAGE_DLL)
    if kind == "dll" and not is_dll:
        raise NativeLaunchError("Native file view is not a DLL.", code="runtime_pe")
    if kind == "exe" and is_dll:
        raise NativeLaunchError("Native launcher must be an executable.", code="runtime_pe")


def _require_quiet_games() -> None:
    observed = _observed_game_pids()
    if observed is None:
        raise NativeLaunchError(
            "Rocket League processes could not be checked. Launch was not started.",
            code="game_enumeration",
        )
    if observed:
        raise NativeLaunchError(
            "Close Rocket League before native offline launch.",
            code="game_already_running",
        )


def _observed_game_pids() -> tuple[int, ...] | None:
    try:
        found = []
        for process in _game_processes():
            pid = getattr(process, "pid", None)
            if type(pid) is not int:
                return None
            found.append(pid)
        return tuple(found)
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        return None


def _write_plan(process: subprocess.Popen, payload: bytes, timeout: float) -> None:
    stream = process.stdin
    if stream is None:
        raise _Signal("malformed")
    errors = []
    def run() -> None:
        try:
            if stream.write(payload) != len(payload):
                raise OSError("incomplete plan write")
            stream.flush()
        except Exception as exc:
            errors.append(exc)
        finally:
            try:
                stream.close()
            except Exception as exc:
                errors.append(exc)
    thread = threading.Thread(target=run, name="mct-native-launch-stdin", daemon=True)
    thread.start()
    thread.join(timeout)
    if thread.is_alive():
        # The writer owns this stream. Closing a buffered pipe from another
        # thread can wait on its I/O lock and defeat the startup deadline.
        raise _Signal("timeout")
    if errors:
        raise _Signal("malformed")


def _read_bounded_line(stream, timeout: float) -> bytes:
    if stream is None:
        raise _Signal("eof")
    box: dict[str, object] = {}

    def run() -> None:
        try:
            box["line"] = stream.readline(LINE_LIMIT + 1)
        except Exception as exc:
            box["error"] = exc

    thread = threading.Thread(target=run, name="mct-native-launch-stdout", daemon=True)
    thread.start()
    thread.join(timeout)
    if thread.is_alive():
        # Keep the pending reader and helper alive. In particular, do not call
        # BufferedReader.close here: readline may hold its lock until data/EOF.
        raise _Signal("timeout")
    if "error" in box or type(box.get("line")) is not bytes:
        raise _Signal("malformed")
    return box["line"]  # type: ignore[return-value]


def _drain_stderr(stream) -> None:
    if stream is None:
        return

    def run() -> None:
        kept = 0
        try:
            while True:
                chunk = stream.read(4096)
                if not chunk:
                    return
                kept += len(chunk)
                if kept > STDERR_CAP:
                    continue
        except Exception:
            return

    threading.Thread(target=run, name="mct-native-launch-stderr", daemon=True).start()


def _parse_wire_object(raw: bytes) -> dict:
    if raw == b"":
        raise _Signal("eof")
    if raw.startswith(b"\xef\xbb\xbf") or b"\x00" in raw:
        raise _Signal("malformed")
    if len(raw) > LINE_LIMIT or not raw.endswith(b"\n"):
        if len(raw) >= LINE_LIMIT:
            raise _Signal("oversized")
        raise _Signal("eof")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise _Signal("invalid_utf8") from None
    if text.endswith("\n"):
        text = text[:-1]
    if text.endswith("\r"):
        text = text[:-1]
    try:
        return _json_object(text)
    except NativeLaunchError:
        raise _Signal("malformed") from None


def _accept_receipt(receipt: dict, **context) -> OwnedNativeLaunch:
    kind = receipt.get("kind")
    protocol = receipt.get("protocol")
    if type(protocol) is not int or protocol != PROTOCOL:
        raise _Signal("malformed")
    if type(kind) is not str or kind not in {"launch", "error", "exit"}:
        raise _Signal("unexpected_event")
    if kind == "error":
        _accept_error(receipt, **context)
    if kind != "launch":
        raise _Signal("unexpected_event")
    return _confirm_child(receipt, **context)


def _accept_error(receipt: dict, **context) -> None:
    if set(receipt) != ERROR_RECEIPT_FIELDS:
        raise _Signal("extra_field" if not set(receipt) <= ERROR_RECEIPT_FIELDS else "malformed")
    if receipt.get("kind") != "error":
        raise _Signal("unexpected_event")
    _false_flags(receipt)
    message = receipt.get("error")
    if type(message) is not str or not 1 <= len(message) <= 720 or any(ord(char) < 32 for char in message):
        raise _Signal("malformed")
    observed = _observed_game_pids()
    if not _helper_exited(context["process"]) or observed is None or observed:
        raise _Signal("helper_error")
    raise NativeLaunchError(
        f"Native launcher refused the launch: {message}",
        code="helper_refused",
        helper=context["process"],
        receipt=receipt,
        session=context["session"],
        private_package=context["private_package"],
    )


def _confirm_child(receipt: dict, **context) -> OwnedNativeLaunch:
    session = context["session"]
    private = context["private"]
    process = context["process"]
    exe = context["exe"]
    digest = context["digest"]
    if receipt.get("kind") != "launch":
        raise _Signal("unexpected_event")
    if set(receipt) != LAUNCH_RECEIPT_FIELDS:
        raise _Signal("extra_field" if not set(receipt) <= LAUNCH_RECEIPT_FIELDS else "malformed")
    _echo_session(receipt.get("session"), session)
    try:
        current_hash = _hash_file(private, PRIVATE_PACKAGE_MAX)
    except NativeLaunchError:
        raise _Signal("hash_mismatch") from None
    if current_hash != digest:
        raise _Signal("hash_mismatch")
    _echo_hash(receipt.get("private_package_sha256"), digest)
    _echo_hash(receipt.get("source_executable_sha256"), SOURCE_EXE_SHA256)
    _echo_hash(receipt.get("source_package_sha256"), SOURCE_PACKAGE_SHA256)
    _false_flags(receipt)
    _echo_private_path(receipt.get("private_package"), private)
    pid = _pid_value(receipt.get("pid"))
    created = _time_value(receipt.get("create_time"))
    helper_pid = getattr(process, "pid", None)
    if type(helper_pid) is not int or pid == helper_pid:
        raise _Signal("helper_pid")
    _echo_executable(receipt.get("executable"), exe)
    live_created = _match_live_process(pid, created, exe)
    observed = _observed_game_pids()
    if observed is None:
        raise _Signal("game_enumeration")
    if observed != (pid,):
        raise _Signal("other_game" if observed else "game_not_found")
    from .platforms import ProcessIdentity
    identity = ProcessIdentity(pid, live_created, str(exe.resolve()))
    owned = OwnedNativeLaunch(identity=identity, helper=process, receipt=dict(receipt))
    _arm_exit_reader(owned)
    _retain(process)
    return owned


def _match_live_process(pid: int, created: float, exe: Path) -> float:
    import psutil
    try:
        process = _process(pid)
        live_created = process.create_time()
        live_exe = process.exe()
        command = list(process.cmdline())
    except psutil.NoSuchProcess:
        raise _Signal("game_not_found") from None
    except _Signal:
        raise
    except Exception:
        raise _Signal("identity_mismatch") from None
    if type(live_created) is bool or type(live_created) not in (int, float) or not math.isfinite(float(live_created)):
        raise _Signal("starttime_mismatch")
    if abs(float(live_created) - created) > 0.01:
        raise _Signal("starttime_mismatch")
    try:
        same_exe = _same_file(Path(live_exe), exe)
    except OSError:
        same_exe = False
    if not same_exe:
        raise _Signal("exe_mismatch")
    try:
        flags = tuple(command[1:])
        name = Path(str(command[0])).name.casefold() if command else ""
        from .platforms import offline_launch_arguments
        whole = bool(offline_launch_arguments(command))
    except (TypeError, ValueError, IndexError, OSError):
        raise _Signal("cmdline_mismatch") from None
    if flags != OFFLINE_ARGUMENTS or not whole:
        raise _Signal("cmdline_mismatch")
    if name != "rocketleague.exe":
        try:
            argv_same = bool(command) and _same_file(Path(str(command[0])), exe)
        except OSError:
            argv_same = False
        if not argv_same:
            raise _Signal("cmdline_mismatch")
    return float(live_created)


def _identity_still_owned(identity) -> bool | None:
    import psutil
    try:
        process = _process(identity.pid)
        live_created = process.create_time()
        live_exe = process.exe()
    except psutil.NoSuchProcess:
        return False
    except Exception:
        return None
    if type(live_created) is bool or type(live_created) not in (int, float) or not math.isfinite(float(live_created)):
        return False
    if abs(float(live_created) - float(identity.created)) > 0.01:
        return False
    try:
        return _same_file(Path(live_exe), Path(identity.executable))
    except OSError:
        return None


def _echo_session(value: object, expected: str) -> None:
    if type(value) is not str or _UUID.fullmatch(value) is None:
        raise _Signal("malformed")
    if value != expected:
        raise _Signal("session_mismatch")


def _echo_hash(value: object, expected: object) -> None:
    if type(value) is not str or _SHA.fullmatch(value) is None or type(expected) is not str:
        raise _Signal("malformed")
    if value != expected:
        raise _Signal("hash_mismatch")


def _echo_private_path(value: object, expected: Path) -> None:
    if type(value) is not str:
        raise _Signal("malformed")
    try:
        path = _real_file(Path(value), "Private package", PRIVATE_PACKAGE_MAX)
    except NativeLaunchError:
        raise _Signal("path_mismatch") from None
    if not _same_file(path, expected):
        raise _Signal("path_mismatch")


def _echo_executable(value: object, expected: Path) -> None:
    if type(value) is not str:
        raise _Signal("malformed")
    try:
        path = Path(value)
        _syntax(path, "Executable")
        _reject_reparse_chain(path)
    except NativeLaunchError:
        raise _Signal("exe_mismatch") from None
    if path.name.casefold() != "rocketleague.exe" or not _same_file(path, expected):
        raise _Signal("exe_mismatch")


def _false_flags(receipt: dict) -> None:
    for key in ("game_verified", "production_ready", "file_view_observed"):
        if type(receipt.get(key)) is not bool:
            raise _Signal("malformed")
        if receipt.get(key) is not False:
            raise _Signal("claimed_verified")


def _pid_value(value: object) -> int:
    if type(value) is not int or not 0 < value < 2**32:
        raise _Signal("malformed")
    return value


def _time_value(value: object) -> float:
    if type(value) is bool or type(value) not in (int, float) or not math.isfinite(float(value)) or float(value) <= 0:
        raise _Signal("malformed")
    return float(value)


def _parse_exit_receipt(raw: bytes, identity, session: str) -> dict:
    receipt = _parse_wire_object(raw)
    if set(receipt) != EXIT_RECEIPT_FIELDS:
        raise _Signal("extra_field")
    if type(receipt.get("protocol")) is not int or receipt.get("protocol") != PROTOCOL:
        raise _Signal("malformed")
    if receipt.get("kind") != "exit":
        raise _Signal("unexpected_event")
    _echo_session(receipt.get("session"), session)
    if _pid_value(receipt.get("pid")) != identity.pid:
        raise _Signal("identity_mismatch")
    created = _time_value(receipt.get("create_time"))
    if abs(created - float(identity.created)) > 0.01:
        raise _Signal("starttime_mismatch")
    code = receipt.get("exit_code")
    if type(code) is not int or not 0 <= code <= 0xFFFFFFFF:
        raise _Signal("malformed")
    _false_flags(receipt)
    _echo_executable(receipt.get("executable"), Path(identity.executable))
    return dict(receipt)


def _arm_exit_reader(owned: OwnedNativeLaunch) -> None:
    stream = owned.helper.stdout
    box = owned._exit_box

    def run() -> None:
        if stream is None:
            box["error"] = "unreadable"
            return
        try:
            box["raw"] = stream.readline(LINE_LIMIT + 1)
        except Exception:
            box["error"] = "unreadable"

    thread = threading.Thread(target=run, name="mct-native-launch-exit", daemon=True)
    thread.start()
    owned._exit_thread = thread


_DEFINITE_WHEN_IDLE = frozenset({"eof", "malformed", "invalid_utf8", "oversized"})


def _fail_after_start(reason: str, receipt: dict | None = None, **context) -> NoReturn:
    """A finished helper with no game is a refusal. Anything else may own a new game."""
    process = context["process"]
    games = _observed_game_pids()
    running = not _helper_exited(process)
    if reason in _DEFINITE_WHEN_IDLE and not running and games == ():
        raise NativeLaunchError(
            f"Native launcher ended without a game ({reason}).",
            code=reason,
            helper=process,
            receipt=receipt,
            session=context["session"],
            private_package=context["private_package"],
        )
    _raise_uncertain(reason, receipt=receipt, **context)


def _raise_uncertain(reason: str, receipt: dict | None = None, **context) -> NoReturn:
    process = context["process"]
    games = _observed_game_pids()
    running = not _helper_exited(process)
    helper_pid = getattr(process, "pid", None)
    if type(helper_pid) is not int:
        helper_pid = None
    seen = "unknown" if games is None else (", ".join(str(pid) for pid in games) or "none")
    state = "still running" if running else "already exited"
    raise NativeLaunchUncertain(
        "Native launcher result is uncertain "
        f"({reason}). Helper {helper_pid} is {state}. Observed Rocket League pids: {seen}. "
        "Leave the helper and any Rocket League process running. "
        "Defer plugin restore until no Rocket League process remains.",
        reason=reason,
        helper=process,
        helper_pid=helper_pid,
        helper_running=running,
        games=games,
        receipt=receipt,
        session=context["session"],
        private_package=context["private_package"],
    )


@dataclass(frozen=True)
class _Runtime:
    directory: Path
    helper: Path
    file_view: Path
    notice: Path
    receipt: dict
