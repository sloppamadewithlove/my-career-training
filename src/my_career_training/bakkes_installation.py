"""Read-only discovery of BakkesMod's Windows injector installation."""
from __future__ import annotations

import ntpath
from pathlib import Path
import re
import sys
from collections.abc import Callable, Iterable, Mapping


_UNINSTALL_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
_BAKKESMOD_NAME = re.compile(r"^\s*bakkesmod(?:\s|$)", re.IGNORECASE)
_UNRESOLVED_VARIABLE = re.compile(r"%[^%]+%")
_LOCAL_DRIVE = re.compile(r"^[A-Za-z]:$")
_EXE_COMPONENT = re.compile(r"(?:^|[\\/])[^\\/]*\.exe(?:[\\/]|\s|$)", re.IGNORECASE)
_MAX_REGISTRY_ENTRIES_PER_VIEW = 4096
_MAX_RECORD_BYTES = 4096

RegistryRecord = Mapping[str, object]
RecordsReader = Callable[[], Iterable[RegistryRecord]]


def _text_bytes(value: str) -> int | None:
    if len(value) > _MAX_RECORD_BYTES // 2:
        return None
    try:
        return len(value.encode("utf-16-le"))
    except UnicodeEncodeError:
        return None


def injector_candidate_from_record(record: RegistryRecord) -> Path | None:
    """Resolve a BakkesMod uninstall record to its expected injector path.

    Only a BakkesMod ``DisplayName`` and an absolute ``InstallLocation`` are
    accepted. Command strings and executable paths for other products are
    deliberately ignored.
    """
    display_name = record.get("DisplayName")
    if not isinstance(display_name, str) or _text_bytes(display_name) is None:
        return None
    if not _BAKKESMOD_NAME.match(display_name):
        return None

    install_location = record.get("InstallLocation")
    if not isinstance(install_location, str) or _text_bytes(install_location) is None:
        return None
    install_location = install_location.strip()
    if not install_location or "\x00" in install_location:
        return None

    if install_location.startswith(('"', "'")) or install_location.endswith(('"', "'")):
        if (len(install_location) < 2 or install_location[0] not in ('"', "'")
                or install_location[-1] != install_location[0]):
            return None
        install_location = install_location[1:-1].strip()
    if (not install_location or '"' in install_location
            or any(ord(char) < 32 for char in install_location)):
        return None
    combined_text_bytes = _text_bytes(display_name) + _text_bytes(install_location)
    if combined_text_bytes > _MAX_RECORD_BYTES:
        return None
    if _UNRESOLVED_VARIABLE.search(install_location):
        return None

    drive, tail = ntpath.splitdrive(install_location)
    if not _LOCAL_DRIVE.fullmatch(drive) or not tail.startswith(("\\", "/")):
        return None
    if ":" in tail or any(char in tail for char in "<>|?*"):
        return None

    location = ntpath.normpath(install_location)
    basename = ntpath.basename(location)
    if basename.casefold() == "bakkesmod.exe":
        candidate = location
    elif basename.casefold().endswith(".exe") or _EXE_COMPONENT.search(location):
        # InstallLocation should be a directory, or the exact injector itself.
        # Never reinterpret a command string or another executable as a directory.
        return None
    else:
        candidate = ntpath.join(location, "BakkesMod.exe")
    return Path(candidate)


def discover_bakkesmod_injectors(*, records_reader: RecordsReader | None = None) -> list[Path]:
    """Return unique injector candidates from BakkesMod uninstall metadata.

    ``records_reader`` is an injection point for callers and tests. The default
    reader is read-only and returns no candidates when the Windows registry is
    unavailable or the process is not running on Windows.
    """
    reader = records_reader or _read_uninstall_records
    try:
        records = reader()
    except (ImportError, OSError):
        return []

    candidates: list[Path] = []
    seen: set[str] = set()
    try:
        for record in records:
            if not isinstance(record, Mapping):
                continue
            candidate = injector_candidate_from_record(record)
            if candidate is None:
                continue
            normalized = ntpath.normcase(ntpath.normpath(str(candidate)))
            if normalized not in seen:
                seen.add(normalized)
                candidates.append(candidate)
    except (OSError, TypeError):
        return candidates
    return candidates


def _read_uninstall_records(registry=None) -> Iterable[RegistryRecord]:
    """Read only matching uninstall metadata from supported Windows views."""
    if registry is None:
        if sys.platform != "win32":
            return ()
        try:
            import winreg as registry
        except ImportError:
            return ()

    records: list[RegistryRecord] = []
    access_modes = (
        registry.KEY_READ,
        registry.KEY_READ | registry.KEY_WOW64_64KEY,
        registry.KEY_READ | registry.KEY_WOW64_32KEY,
    )
    hives = (registry.HKEY_LOCAL_MACHINE, registry.HKEY_CURRENT_USER)
    for hive in hives:
        for access in access_modes:
            try:
                uninstall_key = registry.OpenKey(hive, _UNINSTALL_KEY, 0, access)
            except OSError:
                continue
            with uninstall_key:
                try:
                    subkey_count = min(
                        registry.QueryInfoKey(uninstall_key)[0],
                        _MAX_REGISTRY_ENTRIES_PER_VIEW,
                    )
                except OSError:
                    continue
                for index in range(subkey_count):
                    try:
                        subkey_name = registry.EnumKey(uninstall_key, index)
                        entry = registry.OpenKey(uninstall_key, subkey_name, 0, access)
                    except OSError:
                        continue
                    with entry:
                        try:
                            display_name, _ = registry.QueryValueEx(entry, "DisplayName")
                        except OSError:
                            continue
                        if (not isinstance(display_name, str) or _text_bytes(display_name) is None
                                or not _BAKKESMOD_NAME.match(display_name)):
                            continue
                        try:
                            install_location, _ = registry.QueryValueEx(entry, "InstallLocation")
                        except OSError:
                            continue
                        records.append({"DisplayName": display_name, "InstallLocation": install_location})
    return records
