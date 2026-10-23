"""Fetch the pinned official BakkesMod setup for an explicit, interactive install.

Downloading and verifying never executes the setup program. The caller presents
the install step to the player and invokes ``launch_verified_bakkes_setup`` only
after that player clicks Install.
"""

from __future__ import annotations

import hashlib
import os
import stat
import sys
import tempfile
import time
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Callable


class PrerequisiteError(RuntimeError):
    """The official setup could not be safely prepared."""


class DownloadCancelled(PrerequisiteError):
    """The player cancelled the download."""


@dataclass(frozen=True)
class _AssetSpec:
    url: str
    version: str
    zip_size: int
    zip_sha256: str
    exe_size: int
    exe_sha256: str


_BAKKES_SETUP = _AssetSpec(
    url="https://github.com/bakkesmodorg/BakkesModInjectorCpp/releases/download/2.0.78/BakkesModSetup.zip",
    version="2.0.78",
    zip_size=10_346_429,
    zip_sha256="cda33c89671b95c156be05d015c2a9dcf04c18b09e0c0c78ce51e879ade0c157",
    exe_size=10_920_928,
    exe_sha256="e52e391e897a361f379ed631c1e7f7bf1ae866d0da171cdb27a1e642eee9d8e5",
)
_CHUNK = 128 * 1024
_SOCKET_TIMEOUT = 20
_TOTAL_TIMEOUT = 90


def _check_cancelled(cancelled: Callable[[], bool] | None) -> None:
    if cancelled is not None and cancelled():
        raise DownloadCancelled("BakkesMod setup download cancelled.")


def _hash_and_size(stream: BinaryIO, limit: int, cancelled: Callable[[], bool] | None = None) -> tuple[int, str]:
    digest = hashlib.sha256()
    count = 0
    while True:
        _check_cancelled(cancelled)
        chunk = stream.read(min(_CHUNK, limit - count + 1))
        if not chunk:
            break
        count += len(chunk)
        if count > limit:
            raise PrerequisiteError("BakkesMod setup size exceeds the verified release size.")
        digest.update(chunk)
    return count, digest.hexdigest()


def _is_pe(path: Path) -> bool:
    with path.open("rb") as source:
        header = source.read(64)
        if len(header) != 64 or header[:2] != b"MZ":
            return False
        offset = int.from_bytes(header[60:64], "little")
        if not 64 <= offset <= 4096:
            return False
        source.seek(offset)
        return source.read(4) == b"PE\0\0"


def _valid_exe(path: Path, spec: _AssetSpec) -> bool:
    if path.is_symlink() or not path.is_file():
        return False
    if path.stat().st_size != spec.exe_size or not _is_pe(path):
        return False
    with path.open("rb") as source:
        return _hash_and_size(source, spec.exe_size) == (spec.exe_size, spec.exe_sha256)


def _download_archive(
    target: Path,
    spec: _AssetSpec,
    opener: Callable[..., object],
    progress: Callable[[int, int], None] | None,
    cancelled: Callable[[], bool] | None,
) -> None:
    _check_cancelled(cancelled)
    request = urllib.request.Request(spec.url, headers={"User-Agent": "MyCareerTraining/0.2"})
    started = time.monotonic()
    digest = hashlib.sha256()
    count = 0
    try:
        with opener(request, timeout=_SOCKET_TIMEOUT) as response, target.open("wb") as output:
            final_url = response.geturl()
            if not final_url.startswith("https://"):
                raise PrerequisiteError("BakkesMod setup download did not stay on HTTPS.")
            if getattr(response, "status", 200) != 200:
                raise PrerequisiteError("BakkesMod setup server returned an error.")
            declared = response.headers.get("Content-Length")
            if declared is not None and int(declared) != spec.zip_size:
                raise PrerequisiteError("BakkesMod setup size does not match the verified release.")
            if progress:
                progress(0, spec.zip_size)
            while True:
                _check_cancelled(cancelled)
                if time.monotonic() - started > _TOTAL_TIMEOUT:
                    raise PrerequisiteError("BakkesMod setup download timed out.")
                chunk = response.read(min(_CHUNK, spec.zip_size - count + 1))
                if not chunk:
                    break
                count += len(chunk)
                if count > spec.zip_size:
                    raise PrerequisiteError("BakkesMod setup size exceeds the verified release size.")
                output.write(chunk)
                digest.update(chunk)
                if progress:
                    progress(count, spec.zip_size)
    except (OSError, TimeoutError) as exc:
        raise PrerequisiteError(f"Could not download BakkesMod setup: {exc}") from exc
    if count != spec.zip_size or digest.hexdigest() != spec.zip_sha256:
        raise PrerequisiteError("BakkesMod setup verification failed; download was discarded.")


def _extract_executable(archive: Path, target: Path, spec: _AssetSpec) -> None:
    try:
        with zipfile.ZipFile(archive) as bundle:
            entries = bundle.infolist()
            if len(entries) != 1 or entries[0].filename != "BakkesModSetup.exe":
                raise PrerequisiteError("BakkesMod setup archive contains unexpected entries.")
            entry = entries[0]
            mode = entry.external_attr >> 16
            if (entry.is_dir() or entry.flag_bits & 1
                    or (entry.create_system == 3 and stat.S_IFMT(mode) not in (0, stat.S_IFREG))):
                raise PrerequisiteError("BakkesMod setup archive contains an unsafe entry.")
            if entry.file_size != spec.exe_size:
                raise PrerequisiteError("BakkesMod setup archive executable size changed.")
            with bundle.open(entry) as source, target.open("wb") as output:
                digest = hashlib.sha256()
                count = 0
                while True:
                    chunk = source.read(min(_CHUNK, spec.exe_size - count + 1))
                    if not chunk:
                        break
                    count += len(chunk)
                    if count > spec.exe_size:
                        raise PrerequisiteError("BakkesMod setup archive exceeds the verified size.")
                    output.write(chunk)
                    digest.update(chunk)
            if count != spec.exe_size or digest.hexdigest() != spec.exe_sha256 or not _is_pe(target):
                raise PrerequisiteError("BakkesMod setup executable verification failed.")
    except (zipfile.BadZipFile, EOFError, OSError) as exc:
        raise PrerequisiteError(f"BakkesMod setup archive could not be read: {exc}") from exc


def _prepare(
    cache_dir: Path,
    spec: _AssetSpec,
    *,
    opener: Callable[..., object] = urllib.request.urlopen,
    progress: Callable[[int, int], None] | None = None,
    cancelled: Callable[[], bool] | None = None,
) -> Path:
    if sys.platform != "win32":
        raise PrerequisiteError("BakkesMod setup is supported on Windows only.")
    _check_cancelled(cancelled)
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    installer = cache_dir / f"BakkesModSetup-{spec.version}.exe"
    if _valid_exe(installer, spec):
        if progress:
            progress(spec.zip_size, spec.zip_size)
        return installer

    archive_name = executable_name = None
    try:
        with tempfile.NamedTemporaryFile(dir=cache_dir, suffix=".zip", delete=False) as archive_tmp:
            archive_name = Path(archive_tmp.name)
        with tempfile.NamedTemporaryFile(dir=cache_dir, suffix=".exe", delete=False) as executable_tmp:
            executable_name = Path(executable_tmp.name)
        _download_archive(archive_name, spec, opener, progress, cancelled)
        _check_cancelled(cancelled)
        _extract_executable(archive_name, executable_name, spec)
        _check_cancelled(cancelled)
        os.replace(executable_name, installer)
        return installer
    finally:
        for temporary in (archive_name, executable_name):
            if temporary is not None:
                temporary.unlink(missing_ok=True)


def prepare_bakkes_setup(
    cache_dir: Path,
    *,
    progress: Callable[[int, int], None] | None = None,
    cancelled: Callable[[], bool] | None = None,
    opener: Callable[..., object] = urllib.request.urlopen,
) -> Path:
    """Return a verified local copy of the pinned official installer; do not run it."""
    return _prepare(cache_dir, _BAKKES_SETUP, opener=opener, progress=progress, cancelled=cancelled)


def launch_verified_bakkes_setup(installer: Path) -> None:
    """Show normal Windows UAC for the verified setup after the player clicks Install."""
    if sys.platform != "win32":
        raise PrerequisiteError("BakkesMod setup is supported on Windows only.")
    installer = Path(installer)
    if not _valid_exe(installer, _BAKKES_SETUP):
        raise PrerequisiteError("BakkesMod setup verification failed; download it again.")
    # The official setup requests administrator rights. Popen can fail with
    # WinError 740; ShellExecute's runas verb shows the normal Windows prompt.
    # No silent switches or pre-accepted terms are supplied.
    os.startfile(str(installer), "runas")
