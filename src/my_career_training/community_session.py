"""Stage one reviewed community DLL for an explicit development trial.

The private cache keeps the original ZIP and its receipt. This module does not
change that receipt, write ``plugins.cfg`` or other BakkesMod config, autoload a
plugin, load a binary, or read the installed game. Production eligibility is
empty. A host-supplied ``verify_scope`` callback is the live lease; recovery
after a crash uses the local journal and does not need that lease once every
Rocket League process is gone. A prepared journal is intent only. Deletion
requires a staged journal that records the Windows file id captured from the
exclusive create, plus a matching hash. The same bytes in a different file are
not ownership. The journal is trusted local state: its shape is checked, and it
is not authenticated against another process running as the same user.

A plausible PE/COFF header is a file-shape check only. It is not ABI,
compatibility, or behavior proof. Source URL and license are records, not proof
either. Returned console text is derived here and is not an app-bridge action.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import stat
import urllib.parse
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import community_plugins


class CommunitySessionError(RuntimeError):
    """A community development trial could not be staged or recovered safely."""


SCHEMA = 1
KIND = "community_plugin_development_trial"
JOURNAL_DIRNAME = "community-session"
RECEIPT_NAME = "active.json"
PE_SHAPE_NOTE = (
    "A plausible Windows PE AMD64 DLL header is a file-shape check only. "
    "It is not ABI compatibility, behavior, or safety proof, and this module does not load the DLL."
)
_MAX_JOURNAL_BYTES = 64 * 1024
_SHA = re.compile(r"^[a-f0-9]{64}$")
_SITE_ID = re.compile(r"[1-9][0-9]{0,9}\Z")
_COMMIT = re.compile(r"[0-9a-f]{40}\Z")
_PLUGIN_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,63}\Z")
_LICENSE = re.compile(r"[A-Za-z0-9.+-]{1,64}\Z")
_LABEL = re.compile(r"[A-Za-z0-9._+-]{1,128}\Z")
_STEM = re.compile(r"MCTCommunity_[1-9][0-9]{0,9}_[0-9a-f]{32}\Z")
_FILENAME = re.compile(r"MCTCommunity_[1-9][0-9]{0,9}_[0-9a-f]{32}\.dll\Z")
_FILE_ID = re.compile(r"[0-9a-f]{8}:[0-9a-f]{16}\Z")
_DEVICES = frozenset({
    "con", "prn", "aux", "nul",
    *(f"com{index}" for index in range(1, 10)),
    *(f"lpt{index}" for index in range(1, 10)),
})
_INERT_NAMES = frozenset({
    "license", "license.md", "license.txt",
    "copying", "copying.md", "copying.txt",
    "readme", "readme.md", "readme.txt", "readme.rst",
})
_JOURNAL_KEYS = frozenset({
    "schema", "kind", "state", "development_trial", "production_eligible",
    "autoload_modified", "cfg_modified", "can_activate", "site_id", "api_version",
    "archive_sha256", "member", "member_sha256", "plugin_name", "source_url",
    "source_commit", "license", "download_url", "game_exe_sha256", "core_identity",
    "build_identity", "nonce", "pid", "start_identity", "fresh", "offline", "steam",
    "frontend", "filename", "stem", "load_command", "unload_command", "bakkes_root",
    "destination", "owned_file_id", "pe_note",
})
_IMAGE_FILE_MACHINE_AMD64 = 0x8664
_IMAGE_FILE_EXECUTABLE_IMAGE = 0x0002
_IMAGE_FILE_DLL = 0x2000
_IMAGE_NT_OPTIONAL_HDR64_MAGIC = 0x20B
_SCOPE_LOST = "Live trial scope was not verified."


def production_profiles() -> tuple[ReviewedPluginProfile, ...]:
    """Return the production allowlist. It is empty until a real review exists."""
    return ()


def production_eligible(profile: object = None) -> bool:
    """Return whether a profile may be staged for a normal player session."""
    return False


def derived_plugin_filename(site_id: str, nonce: str) -> str:
    """Return the only DLL name this module will create for this id and nonce."""
    return f"MCTCommunity_{_site_id(site_id)}_{_nonce(nonce).replace('-', '')}.dll"


def derived_plugin_commands(site_id: str, nonce: str) -> DerivedPluginCommand:
    """Return the fixed load and unload text for the generated stem.

    The text is not executed and is not a ``Backend.dispatch`` action.
    """
    filename = derived_plugin_filename(site_id, nonce)
    return DerivedPluginCommand(filename[:-4], f"plugin load {filename[:-4]}", f"plugin unload {filename[:-4]}")


@dataclass(frozen=True, slots=True)
class DerivedPluginCommand:
    stem: str
    load_command: str
    unload_command: str

    def __post_init__(self) -> None:
        if _STEM.fullmatch(self.stem) is None:
            raise CommunitySessionError("The generated plugin name is not valid.")
        if (self.load_command != f"plugin load {self.stem}"
                or self.unload_command != f"plugin unload {self.stem}"):
            raise CommunitySessionError("The generated plugin command is not valid.")

    @property
    def app_bridge_action(self) -> None:
        """Community trial commands are not app-bridge actions."""
        return None


@dataclass(frozen=True, slots=True)
class ReviewedPluginProfile:
    """Complete development profile. There is no production instance of this type."""

    site_id: str
    api_version: int
    archive_sha256: str
    member: str
    member_sha256: str
    plugin_name: str
    source_url: str
    source_commit: str
    license: str
    download_url: str
    game_exe_sha256: str
    core_identity: str
    build_identity: str

    def __post_init__(self) -> None:
        _validate_profile_shape(self)


@dataclass(frozen=True, slots=True)
class RuntimeIdentity:
    """Host-observed game, core, and build identity. This module does not read those files."""

    game_exe_sha256: str
    core_identity: str
    build_identity: str

    def __post_init__(self) -> None:
        _sha256_text(self.game_exe_sha256, "Game executable hash")
        _label(self.core_identity, "Core identity")
        _label(self.build_identity, "Build identity")


@dataclass(frozen=True, slots=True)
class OwnedTrialScope:
    """Identity of one owned development trial. Flags record the host's claim."""

    nonce: str
    pid: int
    start_identity: str
    fresh: bool
    offline: bool
    steam: bool
    frontend: bool
    development_trial: bool

    def __post_init__(self) -> None:
        _nonce(self.nonce)
        _pid(self.pid)
        _label(self.start_identity, "Start identity")
        for name in ("fresh", "offline", "steam", "frontend", "development_trial"):
            if type(getattr(self, name)) is not bool:
                raise CommunitySessionError("Development trial scope is not valid.")


@dataclass(frozen=True, slots=True)
class StagedCommunityTrial:
    filename: str
    dll_path: Path
    command: DerivedPluginCommand
    member_sha256: str
    production_eligible: bool
    autoload_modified: bool
    pe_shape_is_abi_proof: bool
    pe_note: str

    def __post_init__(self) -> None:
        if (self.production_eligible is not False or self.autoload_modified is not False
                or self.pe_shape_is_abi_proof is not False or self.pe_note != PE_SHAPE_NOTE):
            raise CommunitySessionError("This trial does not grant production eligibility or compatibility.")
        if self.filename != f"{self.command.stem}.dll" or self.dll_path.name != self.filename:
            raise CommunitySessionError("The generated plugin name is not valid.")
        if _SHA.fullmatch(self.member_sha256) is None:
            raise CommunitySessionError("Reviewed member hash is not valid.")


@dataclass(frozen=True, slots=True)
class RecoveryReport:
    status: str
    dll_removed: bool
    journal_kept: bool
    reason: str


@dataclass(frozen=True, slots=True)
class _StagePlan:
    profile: ReviewedPluginProfile
    scope: OwnedTrialScope
    destination: Path
    command: DerivedPluginCommand
    dll_bytes: bytes


def _site_id(value: object) -> str:
    if type(value) is not str or _SITE_ID.fullmatch(value) is None:
        raise CommunitySessionError("Plugin id is not valid.")
    return value


def _nonce(value: object) -> str:
    if type(value) is not str:
        raise CommunitySessionError("Trial nonce is not valid.")
    try:
        parsed = uuid.UUID(value)
    except ValueError:
        raise CommunitySessionError("Trial nonce is not valid.") from None
    if str(parsed) != value:
        raise CommunitySessionError("Trial nonce is not valid.")
    return value


def _pid(value: object) -> int:
    if type(value) is not int or not 1 <= value <= 4_294_967_295:
        raise CommunitySessionError("Trial process id is not valid.")
    return value


def _sha256_text(value: object, label: str) -> str:
    if type(value) is not str or _SHA.fullmatch(value) is None:
        raise CommunitySessionError(f"{label} is not valid.")
    return value


def _label(value: object, label: str) -> str:
    if type(value) is not str or _LABEL.fullmatch(value) is None:
        raise CommunitySessionError(f"{label} is not valid.")
    return value


def _https_record(value: object, label: str) -> str:
    if type(value) is not str or not 12 <= len(value) <= 400 or any(ord(char) < 33 or ord(char) > 126 for char in value):
        raise CommunitySessionError(f"{label} is not valid.")
    parts = urllib.parse.urlsplit(value)
    host = parts.hostname
    if (parts.scheme != "https" or host is None or parts.username or parts.password
            or parts.query or parts.fragment or "\\" in value or parts.netloc.casefold() != host.casefold()):
        raise CommunitySessionError(f"{label} is not valid.")
    return value


def _member_name(value: object) -> str:
    if type(value) is not str:
        raise CommunitySessionError("Reviewed member path is not allowed.")
    try:
        canonical, is_dir = community_plugins._entry_name(value)
    except community_plugins.CommunityPluginError:
        raise CommunitySessionError("Reviewed member path is not allowed.") from None
    base = canonical.rsplit("/", 1)[-1]
    if is_dir or canonical != value or not base.casefold().endswith(".dll") or base.casefold() == ".dll":
        raise CommunitySessionError("Reviewed member path is not allowed.")
    return canonical


def _validate_profile_shape(profile: ReviewedPluginProfile) -> None:
    _site_id(profile.site_id)
    if type(profile.api_version) is not int or not 0 <= profile.api_version <= 1_000_000:
        raise CommunitySessionError("Plugin API version is not valid.")
    _sha256_text(profile.archive_sha256, "Archive hash")
    _sha256_text(profile.member_sha256, "Reviewed member hash")
    _member_name(profile.member)
    if _PLUGIN_NAME.fullmatch(profile.plugin_name) is None:
        raise CommunitySessionError("Expected plugin name is not valid.")
    _https_record(profile.source_url, "Source URL")
    if _COMMIT.fullmatch(profile.source_commit) is None:
        raise CommunitySessionError("Source commit is not valid.")
    if _LICENSE.fullmatch(profile.license) is None:
        raise CommunitySessionError("License record is not valid.")
    try:
        community_plugins._validate_download_url(profile.download_url)
    except community_plugins.CommunityPluginError:
        raise CommunitySessionError("Download URL is not a cache identity.") from None
    _sha256_text(profile.game_exe_sha256, "Game executable hash")
    _label(profile.core_identity, "Core identity")
    _label(profile.build_identity, "Build identity")


def _require_profile(profile: object) -> ReviewedPluginProfile:
    if isinstance(profile, (str, Path, bytes, os.PathLike)):
        raise CommunitySessionError("A reviewed profile must come from developer code, not a path or URL.")
    if not isinstance(profile, ReviewedPluginProfile):
        raise CommunitySessionError("A complete reviewed profile is required before any trial file is written.")
    _validate_profile_shape(profile)
    return profile


def _require_scope(scope: object) -> OwnedTrialScope:
    if not isinstance(scope, OwnedTrialScope):
        raise CommunitySessionError("Development trial scope is not valid.")
    if scope.development_trial is not True:
        raise CommunitySessionError("Production community staging is not available.")
    if scope.fresh is not True or scope.offline is not True or scope.steam is not True or scope.frontend is not True:
        raise CommunitySessionError("Development trial scope is not valid.")
    _nonce(scope.nonce)
    _pid(scope.pid)
    _label(scope.start_identity, "Start identity")
    return scope


def _require_runtime(runtime: object, profile: ReviewedPluginProfile) -> RuntimeIdentity:
    if not isinstance(runtime, RuntimeIdentity):
        raise CommunitySessionError("Runtime identity is required before any trial file is written.")
    if (runtime.game_exe_sha256 != profile.game_exe_sha256 or runtime.core_identity != profile.core_identity
            or runtime.build_identity != profile.build_identity):
        raise CommunitySessionError("Runtime identity does not match the reviewed profile.")
    return runtime


def _paths_equal(left: Path, right: Path) -> bool:
    return os.path.normcase(os.path.abspath(left)) == os.path.normcase(os.path.abspath(right))


def _chain(path: Path) -> list[Path]:
    items = []
    current = path
    while True:
        items.append(current)
        if current.parent == current:
            break
        current = current.parent
    items.reverse()
    return items


def _syntax_path(path: object) -> Path:
    if not isinstance(path, Path):
        raise CommunitySessionError("Trial path is not allowed.")
    if not path.is_absolute():
        raise CommunitySessionError("Trial path is not allowed.")
    text = str(path)
    if "\x00" in text or text.startswith("\\\\") or text.startswith("//") or text.startswith("\\"):
        raise CommunitySessionError("Trial path is not allowed.")
    if os.name == "nt" and re.match(r"[A-Za-z]:[\\/]", text) is None:
        raise CommunitySessionError("Trial path is not allowed.")
    for part in path.parts[1:]:
        if part in ("", ".", "..") or part.endswith((" ", ".")) or ":" in part:
            raise CommunitySessionError("Trial path is not allowed.")
        if part.casefold().split(".", 1)[0] in _DEVICES:
            raise CommunitySessionError("Trial path uses a device name.")
    return path


def _is_reparse(path: Path) -> bool:
    if path.is_symlink():
        return True
    checker = getattr(path, "is_junction", None)
    try:
        if checker is not None and checker():
            return True
        info = path.lstat()
    except FileNotFoundError:
        return False
    except OSError:
        raise CommunitySessionError("Trial path could not be checked.") from None
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(getattr(info, "st_file_attributes", 0) & flag)


def _reject_reparse(path: Path) -> None:
    for candidate in _chain(path):
        if _is_reparse(candidate):
            raise CommunitySessionError("A symlink or reparse point is not allowed on the trial path.")


def _exists_nofollow(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    except OSError:
        raise CommunitySessionError("Trial path could not be checked.") from None
    return True


def _require_real_dir(path: Path) -> Path:
    path = _syntax_path(path)
    _reject_reparse(path)
    try:
        info = path.lstat()
    except OSError:
        raise CommunitySessionError("Trial directory is not a real directory.") from None
    if not stat.S_ISDIR(info.st_mode) or _is_reparse(path):
        raise CommunitySessionError("Trial directory is not a real directory.")
    resolved = path.resolve()
    if os.path.normcase(str(resolved)) != os.path.normcase(os.path.abspath(path)):
        raise CommunitySessionError("Trial path is a path alias.")
    return resolved


def _assert_disjoint(left: Path, right: Path) -> None:
    left_real = left.resolve()
    right_real = right.resolve()
    if left_real == right_real or left_real in right_real.parents or right_real in left_real.parents:
        raise CommunitySessionError("The trial journal and BakkesMod folder must be separate directories.")


def _read_regular(path: Path, limit: int) -> bytes:
    path = _syntax_path(path)
    if _is_reparse(path):
        raise CommunitySessionError("Trial path is not a regular file.")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        raise CommunitySessionError("Trial path could not be read.") from None
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise CommunitySessionError("Trial path is not a regular file.")
        chunks = []
        remaining = info.st_size
        while remaining:
            blob = os.read(descriptor, min(64 * 1024, remaining))
            if not blob:
                raise CommunitySessionError("Trial path could not be read.")
            chunks.append(blob)
            remaining -= len(blob)
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _write_exclusive(path: Path, data: bytes) -> str:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except FileExistsError:
        raise CommunitySessionError("The generated plugin file already exists and was left unchanged.") from None
    except OSError:
        raise CommunitySessionError("The staged plugin file could not be created.") from None
    try:
        view = memoryview(data)
        offset = 0
        while offset < len(view):
            count = os.write(descriptor, view[offset:])
            if count <= 0:
                raise CommunitySessionError("The staged plugin write did not finish.")
            offset += count
        os.fsync(descriptor)
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_size != len(data):
            raise CommunitySessionError("The staged plugin file could not be created.")
        return _identity_from_fd(descriptor)
    finally:
        os.close(descriptor)


def _win32():
    """Kernel32 entry points. Handles use the full pointer width and are closed by the caller."""
    if os.name != "nt":
        raise CommunitySessionError("File ownership is recorded with the Windows file id.")
    cached = getattr(_win32, "api", None)
    if cached is not None:
        return cached
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)

    class _FileTime(ctypes.Structure):
        _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]

    class _ByHandle(ctypes.Structure):
        _fields_ = [
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
        ]

    class _Disposition(ctypes.Structure):
        _fields_ = [("DeleteFile", wintypes.BOOLEAN)]

    kernel.CreateFileW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
        wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
    ]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.GetFileInformationByHandle.argtypes = [wintypes.HANDLE, ctypes.POINTER(_ByHandle)]
    kernel.GetFileInformationByHandle.restype = wintypes.BOOL
    kernel.SetFileInformationByHandle.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD]
    kernel.SetFileInformationByHandle.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    kernel.ReadFile.argtypes = [
        wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID,
    ]
    kernel.ReadFile.restype = wintypes.BOOL
    kernel.WriteFile.argtypes = [
        wintypes.HANDLE, wintypes.LPCVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID,
    ]
    kernel.WriteFile.restype = wintypes.BOOL
    kernel.SetFilePointerEx.argtypes = [
        wintypes.HANDLE, ctypes.c_longlong, ctypes.POINTER(ctypes.c_longlong), wintypes.DWORD,
    ]
    kernel.SetFilePointerEx.restype = wintypes.BOOL
    kernel.SetEndOfFile.argtypes = [wintypes.HANDLE]
    kernel.SetEndOfFile.restype = wintypes.BOOL
    kernel.FlushFileBuffers.argtypes = [wintypes.HANDLE]
    kernel.FlushFileBuffers.restype = wintypes.BOOL
    _win32.api = (kernel, ctypes, wintypes, _ByHandle, _Disposition)
    return _win32.api


def _format_identity(info) -> str:
    index = (int(info.nFileIndexHigh) << 32) | int(info.nFileIndexLow)
    return f"{int(info.dwVolumeSerialNumber):08x}:{index:016x}"


def _identity_from_handle(handle) -> str:
    kernel, ctypes, _wintypes, by_handle, _disposition = _win32()
    info = by_handle()
    if not kernel.GetFileInformationByHandle(handle, ctypes.byref(info)):
        raise CommunitySessionError("The staged plugin file could not be identified.")
    if int(info.dwFileAttributes) & 0x400 or int(info.nNumberOfLinks) != 1:
        raise CommunitySessionError("The staged plugin file could not be identified.")
    identity = _format_identity(info)
    if _FILE_ID.fullmatch(identity) is None:
        raise CommunitySessionError("The staged plugin file could not be identified.")
    return identity


def _identity_from_fd(descriptor: int) -> str:
    import msvcrt
    # The C runtime owns this handle. Closing it here would break the Python file.
    return _identity_from_handle(msvcrt.get_osfhandle(descriptor))


def _open_handle(path: Path, access: int, share: int):
    kernel, ctypes, _wintypes, _by_handle, _disposition = _win32()
    handle = kernel.CreateFileW(
        str(path), access, share, None, 3, 0x80 | 0x00200000, None,
    )
    invalid = ctypes.c_void_p(-1).value
    if handle is None or handle == invalid:
        error = ctypes.get_last_error()
        if error in (2, 3):
            return None
        if error == 32:
            return "busy"
        raise CommunitySessionError("The staged plugin path was left in place.")
    return handle


def _close_handle(handle) -> None:
    kernel, _ctypes, _wintypes, _by_handle, _disposition = _win32()
    kernel.CloseHandle(handle)


def _handle_info(handle):
    kernel, ctypes, _wintypes, by_handle, _disposition = _win32()
    info = by_handle()
    if not kernel.GetFileInformationByHandle(handle, ctypes.byref(info)):
        raise CommunitySessionError("The staged plugin path was left in place.")
    return info


def _read_handle(handle, size: int) -> bytes:
    kernel, ctypes, wintypes, _by_handle, _disposition = _win32()
    chunks = []
    remaining = size
    while remaining:
        buf = ctypes.create_string_buffer(min(64 * 1024, remaining))
        got = wintypes.DWORD(0)
        if not kernel.ReadFile(handle, buf, len(buf), ctypes.byref(got), None) or got.value <= 0:
            raise CommunitySessionError("The staged plugin path was left in place.")
        chunks.append(buf.raw[:got.value])
        remaining -= got.value
    return b"".join(chunks)


def _seek_zero(handle) -> None:
    kernel, ctypes, _wintypes, _by_handle, _disposition = _win32()
    new = ctypes.c_longlong(0)
    if not kernel.SetFilePointerEx(handle, 0, ctypes.byref(new), 0):
        raise CommunitySessionError("The trial journal was left in place.")


def _identity_of_path(path: Path) -> str:
    # Share read, write, and delete so a probe does not disturb another opener.
    handle = _open_handle(path, 0x80000000, 0x1 | 0x2 | 0x4)
    if handle is None or handle == "busy":
        raise CommunitySessionError("The staged plugin path was left in place.")
    try:
        info = _handle_info(handle)
        if int(info.dwFileAttributes) & 0x400:
            raise CommunitySessionError("The staged plugin path is a link and was left in place.")
        return _format_identity(info)
    finally:
        _close_handle(handle)


def _unlink_name_if_identity(path: Path, identity: str) -> None:
    """Delete one scratch file on the handle that confirmed its file id.

    Disposition is set before that handle is closed. A replacement at the same
    path has a different id and is left in place. This is scratch cleanup only.
    It does not authorize plugin DLL deletion, and it is not a non-Windows guarantee.
    """
    if os.name != "nt" or type(identity) is not str or _FILE_ID.fullmatch(identity) is None:
        return
    if not _exists_nofollow(path) or _is_reparse(path):
        return
    try:
        kernel, ctypes, _wintypes, _by_handle, disposition = _win32()
        # Read and delete, share read only, so a replacement cannot land on this file.
        handle = _open_handle(path, 0x80000000 | 0x00010000, 0x1)
    except CommunitySessionError:
        return
    if handle is None or handle == "busy":
        return
    try:
        info = _handle_info(handle)
        attributes = int(info.dwFileAttributes)
        ordinary = int(info.nNumberOfLinks) == 1 and attributes & 0x410 == 0
        if not ordinary or _format_identity(info) != identity:
            return
        marker = disposition(1)
        kernel.SetFileInformationByHandle(handle, 4, ctypes.byref(marker), ctypes.sizeof(marker))
    except CommunitySessionError:
        return
    finally:
        _close_handle(handle)


def _rewrite_identified(path: Path, identity: str, expected: bytes, replacement: bytes) -> None:
    """Rewrite one journal file while its handle denies writers and deleters."""
    kernel, ctypes, wintypes, _by_handle, _disposition = _win32()
    handle = _open_handle(path, 0x80000000 | 0x40000000, 0x1)
    if handle is None or handle == "busy":
        raise CommunitySessionError("The trial journal changed and was left in place.")
    try:
        info = _handle_info(handle)
        if _format_identity(info) != identity or int(info.nNumberOfLinks) != 1 or int(info.dwFileAttributes) & 0x400:
            raise CommunitySessionError("The trial journal changed and was left in place.")
        size = (int(info.nFileSizeHigh) << 32) | int(info.nFileSizeLow)
        if size != len(expected) or size > _MAX_JOURNAL_BYTES:
            raise CommunitySessionError("The trial journal changed and was left in place.")
        if _read_handle(handle, size) != expected:
            raise CommunitySessionError("The trial journal changed and was left in place.")
        _seek_zero(handle)
        view = memoryview(replacement)
        offset = 0
        while offset < len(view):
            chunk = view[offset:offset + 64 * 1024]
            got = wintypes.DWORD(0)
            buffer = ctypes.create_string_buffer(chunk.tobytes())
            if not kernel.WriteFile(handle, buffer, len(chunk), ctypes.byref(got), None) or got.value != len(chunk):
                raise CommunitySessionError("The trial journal could not be updated.")
            offset += got.value
        if not kernel.SetEndOfFile(handle) or not kernel.FlushFileBuffers(handle):
            raise CommunitySessionError("The trial journal could not be updated.")
    finally:
        _close_handle(handle)


def _dispose_identified(
    path: Path,
    identity: str,
    *,
    limit: int,
    game_running: Callable[[], bool],
    expected_hash: str | None = None,
    expected_bytes: bytes | None = None,
    strict: bool = False,
) -> str:
    """Delete one ordinary file from the handle that passed the id and byte check.

    The handle is opened for read and delete and shares only read, so a writer or
    another deleter cannot proceed while the check runs. This is the Windows path.
    A missing Windows file id is not treated as a portable atomic delete.
    """
    kernel, ctypes, _wintypes, _by_handle, disposition = _win32()
    if _is_reparse(path):
        raise CommunitySessionError("The staged plugin path is a link and was left in place.")
    handle = _open_handle(path, 0x80000000 | 0x00010000, 0x1)
    if handle is None:
        return "absent"
    if handle == "busy":
        return "left"
    try:
        info = _handle_info(handle)
        ordinary = int(info.nNumberOfLinks) == 1 and int(info.dwFileAttributes) & 0x410 == 0
        same = _format_identity(info) == identity
        if not ordinary or not same:
            if strict:
                raise CommunitySessionError("The trial journal changed and was left in place.")
            return "identity"
        size = (int(info.nFileSizeHigh) << 32) | int(info.nFileSizeLow)
        if size > limit:
            if strict:
                raise CommunitySessionError("The trial journal changed and was left in place.")
            return "bytes"
        data = _read_handle(handle, size)
        if expected_bytes is not None and data != expected_bytes:
            if strict:
                raise CommunitySessionError("The trial journal changed and was left in place.")
            return "bytes"
        if expected_hash is not None and hashlib.sha256(data).hexdigest() != expected_hash:
            return "bytes"
        running = game_running()
        if running is True:
            return "deferred"
        if running is not False:
            raise CommunitySessionError("Rocket League state could not be checked. Files were left in place.")
        marker = disposition(1)
        if not kernel.SetFileInformationByHandle(handle, 4, ctypes.byref(marker), ctypes.sizeof(marker)):
            raise CommunitySessionError("The staged plugin path was left in place.")
    finally:
        _close_handle(handle)
    if _exists_nofollow(path):
        raise CommunitySessionError("The staged plugin path was left in place.")
    return "removed"


def _require_pe_amd64_dll(data: bytes) -> None:
    """Check a bounded header window. This is not ABI or behavior proof and does not load the file."""
    if len(data) < 0x40 or data[:2] != b"MZ":
        raise CommunitySessionError(PE_SHAPE_NOTE)
    e_lfanew = int.from_bytes(data[0x3C:0x40], "little")
    if e_lfanew < 0x40 or e_lfanew > 1024 or e_lfanew % 4 != 0 or e_lfanew + 24 > len(data):
        raise CommunitySessionError(PE_SHAPE_NOTE)
    if data[e_lfanew:e_lfanew + 4] != b"PE\0\0":
        raise CommunitySessionError(PE_SHAPE_NOTE)
    coff = e_lfanew + 4
    machine = int.from_bytes(data[coff:coff + 2], "little")
    sections = int.from_bytes(data[coff + 2:coff + 4], "little")
    size_optional = int.from_bytes(data[coff + 16:coff + 18], "little")
    characteristics = int.from_bytes(data[coff + 18:coff + 20], "little")
    if machine != _IMAGE_FILE_MACHINE_AMD64 or not 1 <= sections <= 96:
        raise CommunitySessionError(PE_SHAPE_NOTE)
    if not 112 <= size_optional <= 1024 or coff + 20 + size_optional > len(data):
        raise CommunitySessionError(PE_SHAPE_NOTE)
    if characteristics & _IMAGE_FILE_DLL == 0 or characteristics & _IMAGE_FILE_EXECUTABLE_IMAGE == 0:
        raise CommunitySessionError(PE_SHAPE_NOTE)
    magic = int.from_bytes(data[coff + 20:coff + 22], "little")
    if magic != _IMAGE_NT_OPTIONAL_HDR64_MAGIC:
        raise CommunitySessionError(PE_SHAPE_NOTE)
    if coff + 20 + size_optional + sections * 40 > len(data):
        raise CommunitySessionError(PE_SHAPE_NOTE)


def _archive_policy(package: dict, member: str) -> int:
    entries = package.get("entries")
    if type(entries) is not list:
        raise CommunitySessionError("Plugin archive was rejected.")
    files = []
    directories = []
    for entry in entries:
        if type(entry) is not dict or type(entry.get("name")) is not str or type(entry.get("directory")) is not bool:
            raise CommunitySessionError("Plugin archive was rejected.")
        if entry["directory"]:
            directories.append(entry["name"])
        else:
            files.append(entry)
    dlls = [entry["name"] for entry in files if entry["name"].casefold().endswith(".dll")]
    if dlls != [member]:
        raise CommunitySessionError("Plugin archive must contain exactly one reviewed DLL.")
    allowed_dirs: set[str] = set()
    member_size = None
    for entry in files:
        name = entry["name"]
        if name != member:
            base = name.rsplit("/", 1)[-1].casefold()
            if base not in _INERT_NAMES:
                raise CommunitySessionError("Plugin archive contains a resource this pilot cannot stage.")
        else:
            member_size = entry.get("bytes")
        parent = name
        while "/" in parent:
            parent = parent.rsplit("/", 1)[0]
            allowed_dirs.add(parent)
    for name in directories:
        if name not in allowed_dirs:
            raise CommunitySessionError("Plugin archive contains a resource this pilot cannot stage.")
    if type(member_size) is not int or not 0 < member_size <= community_plugins._MAX_ENTRY_BYTES:
        raise CommunitySessionError("Reviewed DLL member is not in the cached archive.")
    return member_size


def _extract_member(blob: bytes, member: str, size: int) -> bytes:
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as bundle:
            info = bundle.getinfo(member)
            if info.file_size != size or info.is_dir():
                raise CommunitySessionError("Reviewed DLL member is not in the cached archive.")
            with bundle.open(info, "r") as handle:
                data = handle.read(size + 1)
    except CommunitySessionError:
        raise
    except (KeyError, zipfile.BadZipFile, zipfile.LargeZipFile, EOFError, RuntimeError, OSError):
        raise CommunitySessionError("Reviewed DLL member is not in the cached archive.") from None
    if len(data) != size:
        raise CommunitySessionError("Reviewed DLL member is not in the cached archive.")
    return data


def _pairs(message: str):
    def hook(items):
        obj = {}
        for key, value in items:
            if type(key) is not str or key in obj:
                raise CommunitySessionError(message)
            obj[key] = value
        return obj
    return hook


class CommunitySession:
    """Journal and stage one generated DLL, then remove it only when it is unchanged."""

    def __init__(self, app_state: Path, bakkes_root: Path, *, game_running: Callable[[], bool]):
        if not callable(game_running):
            raise CommunitySessionError("Rocket League state could not be checked.")
        self._game_running = game_running
        self.app_state = _require_real_dir(Path(app_state))
        self.bakkes_root = _require_real_dir(Path(bakkes_root))
        self.plugins = _require_real_dir(self.bakkes_root / "plugins")
        if not _paths_equal(self.plugins.parent, self.bakkes_root):
            raise CommunitySessionError("Trial path is a path alias.")
        self.journal_dir = self.app_state / JOURNAL_DIRNAME
        self.receipt_path = self.journal_dir / RECEIPT_NAME
        self._prepared_payload: bytes | None = None
        self._prepared_identity: str | None = None
        _syntax_path(self.journal_dir)
        _assert_disjoint(self.journal_dir, self.bakkes_root)

    def outstanding(self) -> bool:
        return self.receipt_path.is_file() and not _is_reparse(self.receipt_path)

    def stage(
        self,
        profile: object,
        scope: object,
        runtime: object,
        cache_directory: Path,
        *,
        verify_scope: Callable[[OwnedTrialScope], bool],
    ) -> StagedCommunityTrial:
        """Validate, journal, and exclusive-create one development DLL.

        ``verify_scope`` runs before the journal write, again immediately before
        the DLL create, and again after the bytes are confirmed. A failure keeps
        the journal once it exists. A file is removed only after the staged
        journal records the id captured from the exclusive create.
        """
        plan = self._prepare(profile, scope, runtime, cache_directory)
        if not callable(verify_scope) or verify_scope(plan.scope) is not True:
            raise CommunitySessionError(_SCOPE_LOST)
        self._recheck_before_create(plan)
        self._publish_prepared(plan)
        owned = None
        try:
            self._recheck_before_create(plan)
            if verify_scope(plan.scope) is not True:
                raise CommunitySessionError(_SCOPE_LOST)
            owned = _exclusive_write(plan.destination, plan.dll_bytes)
            self._confirm_staged(plan, owned)
            if verify_scope(plan.scope) is not True:
                raise CommunitySessionError(_SCOPE_LOST)
            self._mark_staged(plan, owned)
        except Exception:
            if owned is not None:
                self._best_effort_remove(plan.destination, owned)
            raise
        return StagedCommunityTrial(
            filename=plan.destination.name,
            dll_path=plan.destination,
            command=plan.command,
            member_sha256=plan.profile.member_sha256,
            production_eligible=False,
            autoload_modified=False,
            pe_shape_is_abi_proof=False,
            pe_note=PE_SHAPE_NOTE,
        )

    def recover(self) -> RecoveryReport:
        """Remove the owned DLL after every Rocket League process has exited.

        The target path is recomputed from the trusted BakkesMod root plus the
        validated id and nonce. A prepared journal never authorizes deletion.
        A staged journal deletes only the recorded Windows file id when the hash
        still matches. A journal destination that disagrees is refused.
        """
        if not _exists_nofollow(self.receipt_path):
            return RecoveryReport("idle", False, False, "No community trial journal is present.")
        if _is_reparse(self.receipt_path):
            raise CommunitySessionError("The trial journal is a link and was left in place.")
        if self._game_is_running():
            return self._deferred()
        record = self._read_journal(self.receipt_path)
        destination = self._destination_from_record(record)
        if record["state"] == "prepared":
            return self._recover_prepared(record, destination)
        if self._game_is_running():
            return self._deferred()
        outcome = _dispose_identified(
            destination, record["owned_file_id"], limit=community_plugins._MAX_ENTRY_BYTES,
            game_running=self._game_is_running, expected_hash=record["member_sha256"],
        )
        return self._finish_staged(record, outcome)

    def _prepare(self, profile: object, scope: object, runtime: object, cache_directory: Path) -> _StagePlan:
        checked = _require_profile(profile)
        checked_scope = _require_scope(scope)
        _require_runtime(runtime, checked)
        if self.outstanding():
            raise CommunitySessionError("A community trial journal already exists.")
        command = derived_plugin_commands(checked.site_id, checked_scope.nonce)
        destination = self.plugins / command.stem
        destination = destination.with_name(f"{command.stem}.dll")
        _syntax_path(destination)
        if destination.name != derived_plugin_filename(checked.site_id, checked_scope.nonce):
            raise CommunitySessionError("The generated plugin name is not valid.")
        cache = _require_real_dir(Path(cache_directory))
        _assert_disjoint(cache, self.bakkes_root)
        if _exists_nofollow(self.journal_dir):
            _require_real_dir(self.journal_dir)
        _assert_disjoint(self.journal_dir, self.bakkes_root)
        dll_bytes = self._reviewed_dll(cache, checked)
        plan = _StagePlan(checked, checked_scope, destination, command, dll_bytes)
        self._recheck_before_create(plan)
        return plan

    def _reviewed_dll(self, cache: Path, profile: ReviewedPluginProfile) -> bytes:
        blob = self._read_cached_archive(cache, profile.archive_sha256)
        if hashlib.sha256(blob).hexdigest() != profile.archive_sha256:
            raise CommunitySessionError("Cached archive hash does not match the reviewed profile.")
        try:
            package = community_plugins._inspect_zip(blob)
        except community_plugins.CommunityPluginError as exc:
            raise CommunitySessionError(f"Plugin archive was rejected: {exc}") from exc
        size = _archive_policy(package, profile.member)
        try:
            listed = community_plugins.cached_plugins(cache)
        except community_plugins.CommunityPluginError as exc:
            raise CommunitySessionError(f"Plugin archive was rejected: {exc}") from exc
        receipts = [item for item in listed if item.get("artifact_sha256") == profile.archive_sha256]
        if len(receipts) != 1 or receipts[0].get("package") != package:
            raise CommunitySessionError("Cached receipt does not match the archive bytes.")
        receipt = receipts[0]
        if (receipt.get("id") != profile.site_id or receipt.get("version") != profile.api_version
                or receipt.get("download_url") != profile.download_url
                or receipt.get("archive") != f"objects/{profile.archive_sha256}/archive.zip"):
            raise CommunitySessionError("Cached plugin identity does not match the reviewed profile.")
        if receipt.get("can_activate") is not False or receipt.get("status") != "downloaded_not_enabled":
            raise CommunitySessionError("Cached community plugins cannot be activated.")
        data = _extract_member(blob, profile.member, size)
        if hashlib.sha256(data).hexdigest() != profile.member_sha256:
            raise CommunitySessionError("Reviewed member hash does not match the cached archive.")
        _require_pe_amd64_dll(data)
        return data

    def _read_cached_archive(self, cache: Path, digest: str) -> bytes:
        objects = cache / "objects"
        folder = objects / digest
        archive = folder / "archive.zip"
        for candidate in (objects, folder, archive):
            _syntax_path(candidate)
        if not _exists_nofollow(folder):
            raise CommunitySessionError("No validated cache record matches this profile.")
        _require_real_dir(objects)
        _require_real_dir(folder)
        if folder.name != digest or archive.name != "archive.zip":
            raise CommunitySessionError("Cached archive hash does not match the reviewed profile.")
        blob = _read_regular(archive, community_plugins._MAX_ARCHIVE_BYTES)
        if hashlib.sha256(blob).hexdigest() != digest:
            raise CommunitySessionError("Cached archive hash does not match the reviewed profile.")
        return blob

    def _recheck_before_create(self, plan: _StagePlan) -> None:
        root = _require_real_dir(self.bakkes_root)
        plugins = _require_real_dir(root / "plugins")
        if not _paths_equal(root, self.bakkes_root) or not _paths_equal(plugins, self.plugins):
            raise CommunitySessionError("Trial path is a path alias.")
        if not _paths_equal(plan.destination.parent, plugins) or plan.destination.name != derived_plugin_filename(
                plan.profile.site_id, plan.scope.nonce):
            raise CommunitySessionError("The generated plugin name is not valid.")
        _reject_reparse(plan.destination)
        if _exists_nofollow(plan.destination):
            raise CommunitySessionError("The generated plugin file already exists and was left unchanged.")
        journal = self.app_state / JOURNAL_DIRNAME
        if _exists_nofollow(journal):
            _require_real_dir(journal)
        _assert_disjoint(journal, root)

    def _journal_directory(self) -> Path:
        directory = self.app_state / JOURNAL_DIRNAME
        _syntax_path(directory)
        if _exists_nofollow(directory):
            directory = _require_real_dir(directory)
        else:
            _reject_reparse(directory.parent)
            try:
                os.mkdir(directory, 0o700)
            except OSError:
                raise CommunitySessionError("The trial journal could not be created.") from None
            directory = _require_real_dir(directory)
        _assert_disjoint(directory, self.bakkes_root)
        return directory

    def _publish_prepared(self, plan: _StagePlan) -> None:
        directory = self._journal_directory()
        payload = self._document(plan, "prepared", None)
        self._create_receipt(directory, payload)
        final = directory / RECEIPT_NAME
        self._prepared_payload = _read_regular(final, _MAX_JOURNAL_BYTES)
        self._prepared_identity = _identity_of_path(final)
        record = self._read_journal(final)
        if record["state"] != "prepared" or record["owned_file_id"] is not None:
            raise CommunitySessionError("The trial journal could not be created.")

    def _mark_staged(self, plan: _StagePlan, identity: str) -> None:
        directory = _require_real_dir(self.journal_dir)
        payload = self._document(plan, "staged", identity)
        self._replace_receipt(directory, payload, self._prepared_payload, self._prepared_identity)
        record = self._read_journal(directory / RECEIPT_NAME)
        if record["state"] != "staged" or record["owned_file_id"] != identity:
            raise CommunitySessionError("The trial journal could not be updated.")

    def _document(self, plan: _StagePlan, state: str, owned_file_id: str | None) -> bytes:
        profile = plan.profile
        scope = plan.scope
        body = {
            "schema": SCHEMA,
            "kind": KIND,
            "state": state,
            "development_trial": True,
            "production_eligible": False,
            "autoload_modified": False,
            "cfg_modified": False,
            "can_activate": False,
            "site_id": profile.site_id,
            "api_version": profile.api_version,
            "archive_sha256": profile.archive_sha256,
            "member": profile.member,
            "member_sha256": profile.member_sha256,
            "plugin_name": profile.plugin_name,
            "source_url": profile.source_url,
            "source_commit": profile.source_commit,
            "license": profile.license,
            "download_url": profile.download_url,
            "game_exe_sha256": profile.game_exe_sha256,
            "core_identity": profile.core_identity,
            "build_identity": profile.build_identity,
            "nonce": scope.nonce,
            "pid": scope.pid,
            "start_identity": scope.start_identity,
            "fresh": True,
            "offline": True,
            "steam": True,
            "frontend": True,
            "filename": plan.destination.name,
            "stem": plan.command.stem,
            "load_command": plan.command.load_command,
            "unload_command": plan.command.unload_command,
            "bakkes_root": str(self.bakkes_root),
            "destination": str(plan.destination),
            "owned_file_id": owned_file_id,
            "pe_note": PE_SHAPE_NOTE,
        }
        if state == "prepared" and owned_file_id is not None:
            raise CommunitySessionError("The trial journal could not be created.")
        if state == "staged" and (type(owned_file_id) is not str or _FILE_ID.fullmatch(owned_file_id) is None):
            raise CommunitySessionError("The trial journal could not be created.")
        if set(body) != _JOURNAL_KEYS or state not in {"prepared", "staged"}:
            raise CommunitySessionError("The trial journal could not be created.")
        encoded = json.dumps(body, ensure_ascii=True, allow_nan=False, indent=2, sort_keys=True).encode("ascii")
        if len(encoded) > _MAX_JOURNAL_BYTES:
            raise CommunitySessionError("The trial journal could not be created.")
        return encoded

    def _create_receipt(self, directory: Path, data: bytes) -> None:
        final = directory / RECEIPT_NAME
        if final.name != RECEIPT_NAME or not _paths_equal(final.parent, directory):
            raise CommunitySessionError("The trial journal path is not valid.")
        if _exists_nofollow(final):
            raise CommunitySessionError("A community trial journal already exists.")
        if os.name != "nt":
            raise CommunitySessionError("File ownership is recorded with the Windows file id.")
        temporary = directory / f".receipt-{uuid.uuid4().hex}.json"
        identity = _write_exclusive(temporary, data)
        try:
            # Same-directory rename does not replace an existing file on Windows,
            # and the published file keeps a single link.
            os.rename(temporary, final)
        except FileExistsError:
            _unlink_name_if_identity(temporary, identity)
            raise CommunitySessionError("A community trial journal already exists.") from None
        except OSError:
            _unlink_name_if_identity(temporary, identity)
            if _exists_nofollow(final):
                raise CommunitySessionError("A community trial journal already exists.") from None
            raise CommunitySessionError("The trial journal could not be created.") from None
        if _is_reparse(final) or _identity_of_path(final) != identity:
            raise CommunitySessionError("The trial journal could not be created.")
        handle = _open_handle(final, 0x80000000, 0x1 | 0x2 | 0x4)
        if handle is None or handle == "busy":
            raise CommunitySessionError("The trial journal could not be created.")
        try:
            if int(_handle_info(handle).nNumberOfLinks) != 1:
                raise CommunitySessionError("The trial journal could not be created.")
        finally:
            _close_handle(handle)

    def _replace_receipt(self, directory: Path, data: bytes, expected: bytes | None, identity: str | None) -> None:
        final = directory / RECEIPT_NAME
        if expected is None or identity is None or _is_reparse(final):
            raise CommunitySessionError("The trial journal changed and was left in place.")
        if not _paths_equal(final.parent, directory) or final.name != RECEIPT_NAME:
            raise CommunitySessionError("The trial journal path is not valid.")
        _rewrite_identified(final, identity, expected, data)

    def _read_journal(self, path: Path) -> dict:
        if path.name != RECEIPT_NAME or _is_reparse(path):
            raise CommunitySessionError("The trial journal was left in place.")
        raw = _read_regular(path, _MAX_JOURNAL_BYTES)
        try:
            parsed = json.loads(raw.decode("ascii"), object_pairs_hook=_pairs("The trial journal was left in place."))
        except CommunitySessionError:
            raise
        except (UnicodeError, json.JSONDecodeError):
            raise CommunitySessionError("The trial journal was left in place.") from None
        self._require_journal(parsed)
        return parsed

    def _require_journal(self, record: object) -> None:
        if type(record) is not dict or set(record) != _JOURNAL_KEYS:
            raise CommunitySessionError("The trial journal was left in place.")
        if (record["schema"] != SCHEMA or record["kind"] != KIND or record["state"] not in {"prepared", "staged"}
                or record["development_trial"] is not True or record["production_eligible"] is not False
                or record["autoload_modified"] is not False or record["cfg_modified"] is not False
                or record["can_activate"] is not False or record["pe_note"] != PE_SHAPE_NOTE):
            raise CommunitySessionError("The trial journal was left in place.")
        try:
            filename = derived_plugin_filename(record["site_id"], record["nonce"])
            command = derived_plugin_commands(record["site_id"], record["nonce"])
        except CommunitySessionError:
            raise CommunitySessionError("Trial journal does not match the owned plugin path.") from None
        _sha256_text(record["archive_sha256"], "Archive hash")
        _sha256_text(record["member_sha256"], "Reviewed member hash")
        _member_name(record["member"])
        if type(record["api_version"]) is not int or not 0 <= record["api_version"] <= 1_000_000:
            raise CommunitySessionError("The trial journal was left in place.")
        if _PLUGIN_NAME.fullmatch(record["plugin_name"]) is None or _COMMIT.fullmatch(record["source_commit"]) is None:
            raise CommunitySessionError("The trial journal was left in place.")
        if _LICENSE.fullmatch(record["license"]) is None:
            raise CommunitySessionError("The trial journal was left in place.")
        _https_record(record["source_url"], "Source URL")
        try:
            community_plugins._validate_download_url(record["download_url"])
        except community_plugins.CommunityPluginError:
            raise CommunitySessionError("The trial journal was left in place.") from None
        _sha256_text(record["game_exe_sha256"], "Game executable hash")
        _label(record["core_identity"], "Core identity")
        _label(record["build_identity"], "Build identity")
        _pid(record["pid"])
        _label(record["start_identity"], "Start identity")
        if any(record[name] is not True for name in ("fresh", "offline", "steam", "frontend")):
            raise CommunitySessionError("The trial journal was left in place.")
        owned = record["owned_file_id"]
        if record["state"] == "prepared":
            if owned is not None:
                raise CommunitySessionError("The trial journal was left in place.")
        elif type(owned) is not str or _FILE_ID.fullmatch(owned) is None:
            raise CommunitySessionError("The trial journal was left in place.")
        if (record["filename"] != filename or record["stem"] != command.stem
                or record["load_command"] != command.load_command
                or record["unload_command"] != command.unload_command):
            raise CommunitySessionError("Trial journal does not match the owned plugin path.")
        if type(record["bakkes_root"]) is not str or type(record["destination"]) is not str:
            raise CommunitySessionError("Trial journal does not match the owned plugin path.")
        if os.path.normcase(record["bakkes_root"]) != os.path.normcase(str(self.bakkes_root)):
            raise CommunitySessionError("Trial journal does not match the owned plugin path.")
        expected = self.plugins / filename
        if os.path.normcase(record["destination"]) != os.path.normcase(str(expected)):
            raise CommunitySessionError("Trial journal does not match the owned plugin path.")

    def _destination_from_record(self, record: dict) -> Path:
        self._require_journal(record)
        root = _require_real_dir(self.bakkes_root)
        plugins = _require_real_dir(root / "plugins")
        if not _paths_equal(plugins, self.plugins):
            raise CommunitySessionError("Trial path is a path alias.")
        filename = derived_plugin_filename(record["site_id"], record["nonce"])
        destination = plugins / filename
        _syntax_path(destination)
        if os.path.normcase(record["destination"]) != os.path.normcase(str(destination)):
            raise CommunitySessionError("Trial journal does not match the owned plugin path.")
        if not _paths_equal(destination.parent, plugins):
            raise CommunitySessionError("Trial journal does not match the owned plugin path.")
        return destination

    def _confirm_staged(self, plan: _StagePlan, identity: str) -> None:
        if _is_reparse(plan.destination) or _identity_of_path(plan.destination) != identity:
            raise CommunitySessionError("The staged plugin file could not be confirmed.")
        data = _read_regular(plan.destination, community_plugins._MAX_ENTRY_BYTES)
        if data != plan.dll_bytes or hashlib.sha256(data).hexdigest() != plan.profile.member_sha256:
            raise CommunitySessionError("The staged plugin file could not be confirmed.")

    def _deferred(self) -> RecoveryReport:
        return RecoveryReport(
            "deferred", False, True, "Rocket League is running. The staged plugin was left in place.")

    def _recover_prepared(self, record: dict, destination: Path) -> RecoveryReport:
        """Prepared means intent. An existing file is ambiguous and is not deleted."""
        if _is_reparse(destination) or _exists_nofollow(destination):
            return RecoveryReport(
                "ambiguous", False, True,
                "A prepared trial has no ownership record for the plugin file. The file was left for review.",
            )
        self._drop_journal(record)
        return RecoveryReport("recovered", False, False, "The prepared trial created no plugin file.")

    def _finish_staged(self, record: dict, outcome: str) -> RecoveryReport:
        if outcome == "deferred":
            return self._deferred()
        if outcome == "removed":
            self._drop_journal(record)
            return RecoveryReport("recovered", True, False, "The unchanged staged plugin was removed.")
        if outcome == "absent":
            self._drop_journal(record)
            return RecoveryReport("recovered", False, False, "The staged plugin file was already absent.")
        if outcome == "identity":
            return RecoveryReport(
                "retained", False, True, "Staged plugin file identity changed and was left in place.")
        if outcome == "bytes":
            return RecoveryReport(
                "retained", False, True, "Staged plugin bytes changed and were left in place.")
        return RecoveryReport("retained", False, True, "The staged plugin file was left in place.")

    def _drop_journal(self, record: dict) -> None:
        path = self.receipt_path
        if path.name != RECEIPT_NAME or not _paths_equal(path.parent, self.journal_dir) or _is_reparse(path):
            raise CommunitySessionError("The trial journal was left in place.")
        raw = _read_regular(path, _MAX_JOURNAL_BYTES)
        parsed = json.loads(raw.decode("ascii"), object_pairs_hook=_pairs("The trial journal was left in place."))
        self._require_journal(parsed)
        if parsed != record:
            raise CommunitySessionError("The trial journal changed and was left in place.")
        identity = _identity_of_path(path)
        if self._game_is_running():
            raise CommunitySessionError("Rocket League is running. The staged plugin was left in place.")
        outcome = _dispose_identified(
            path, identity, limit=_MAX_JOURNAL_BYTES, game_running=self._game_is_running,
            expected_bytes=raw, strict=True,
        )
        if outcome != "removed":
            raise CommunitySessionError("The trial journal was left in place.")

    def _best_effort_remove(self, destination: Path, identity: str) -> None:
        """Remove a DLL only when the staged journal already binds this create."""
        try:
            if self._game_is_running():
                return
            record = self._read_journal(self.receipt_path)
            if record["state"] != "staged" or record["owned_file_id"] != identity:
                return
            if self._game_is_running():
                return
            _dispose_identified(
                destination, identity, limit=community_plugins._MAX_ENTRY_BYTES,
                game_running=self._game_is_running, expected_hash=record["member_sha256"],
            )
        except Exception:
            return

    def _game_is_running(self) -> bool:
        result = self._game_running()
        if result is True:
            return True
        if result is False:
            return False
        raise CommunitySessionError("Rocket League state could not be checked. Files were left in place.")


def _exclusive_write(path: Path, data: bytes) -> str:
    _syntax_path(path)
    if _is_reparse(path):
        raise CommunitySessionError("A symlink or reparse point is not allowed on the trial path.")
    return _write_exclusive(path, data)
