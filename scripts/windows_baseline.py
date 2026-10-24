"""Read-only Windows identification baseline. Python 3.12, standard library only.

Writes one new JSON file describing a local Steam Rocket League install: the
app 252950 build id, a stable hash of RocketLeague.exe, candidate native-menu
package filenames and sizes, and BakkesMod file versions when a bounded known
file supplies them.

This does not launch, stop, install, or modify Steam, Rocket League, or
BakkesMod. It does not prove native menus, gameplay, Easy Anti-Cheat, or Steam
preservation, and it does not hash the rest of the install. A loaded BakkesMod
DLL or plugin version is always unknown. Injector file metadata is never
reported as a loaded module.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
from datetime import datetime, timezone

MAX_VDF_BYTES = 1_048_576
MAX_VDF_TOKENS = 100_000
MAX_VDF_DEPTH = 8
MAX_VDF_STRING = 4_096
MAX_LIBRARIES = 64
MAX_EXE_BYTES = 512 * 1024 * 1024
MAX_VERSION_TARGET_BYTES = 256 * 1024 * 1024
MAX_VERSION_TEXT_BYTES = 256
MAX_PACKAGE_ENTRIES = 20_000
MAX_PACKAGE_MATCHES = 100
APP_ID = "252950"
EXE_RELATIVE = "Binaries/Win64/RocketLeague.exe"
PACKAGE_DIRS = ("TAGame/CookedPCConsole", "Engine/CookedPCConsole")
PACKAGE_CANDIDATES = (
    "GFX_MainMenu_SF.upk",
    "GFX_PlayMenuV4_SF.upk",
    "GFX_SettingsMenu_SF.upk",
    "GFX_TrainingBrowserMenu_SF.upk",
    "GFxShell_SF.upk",
)
TASKLIST_ARGV = ["tasklist", "/FI", "IMAGENAME eq RocketLeague.exe", "/FO", "CSV", "/NH"]
_CODE = re.compile(r"[a-z0-9_]{1,64}")
_BUILD_ID = re.compile(r"[0-9]{1,20}")
_INSTALLDIR = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ._-]{0,79}")
_VERSION_TOKEN = re.compile(r"[0-9A-Za-z][0-9A-Za-z._+-]{0,63}")
_LIBRARY_STATUSES = ("read", "absent", "malformed", "inaccessible", "symlink", "too_large", "not_regular", "read_error")
_VERIFIER = None
_INJECTOR_MEANING = (
    "File version resource of BakkesMod.exe. Injector file metadata only; "
    "not a loaded DLL version and not a loaded plugin version."
)
_DLL_MEANING = (
    "File version resource of bakkesmod.dll. File metadata only; "
    "this does not show that the DLL is loaded."
)
_VERSION_FILE_MEANING = (
    "Bounded text from a known BakkesMod version file. "
    "This is not a loaded DLL version and not a loaded plugin version."
)
_LIMITS_NOTE = (
    "Identification evidence only. The executable hash and file version are separate reads. "
    "Other install files were not hashed. This report does not prove native menus, gameplay, "
    "Easy Anti-Cheat, or Steam preservation."
)


class ReportWriteError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code if _CODE.fullmatch(code) else "internal_error"


class MalformedVDF(Exception):
    pass


class _Gaps:
    def __init__(self):
        self.unknowns: set[str] = set()
        self._errors: set[tuple[str, str]] = set()

    def unknown(self, code: str) -> None:
        self.unknowns.add(code if _CODE.fullmatch(code) else "read_error")

    def error(self, code: str, subject: str) -> None:
        safe_code = code if _CODE.fullmatch(code) else "read_error"
        safe_subject = subject if _CODE.fullmatch(subject) else "report"
        self._errors.add((safe_subject, safe_code))

    def lists(self) -> tuple[list[str], list[dict]]:
        errors = [{"code": code, "subject": subject} for subject, code in sorted(self._errors)]
        return sorted(self.unknowns), errors


def _verifier():
    global _VERIFIER
    if _VERIFIER is None:
        location = Path(__file__).resolve().with_name("verify_game_files.py")
        spec = importlib.util.spec_from_file_location("mct_verify_game_files", location)
        if spec is None or spec.loader is None:
            raise ImportError(location.name)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _VERIFIER = module
    return _VERIFIER


def _code_from_message(message: str) -> str:
    text = message.lower()
    if "symlink" in text or "reparse" in text:
        return "symlink"
    if "changed" in text or "shrank" in text or "grew" in text:
        return "unstable"
    if "directory" in text:
        return "not_a_directory"
    return "read_error"


def _too_broad(path: Path) -> bool:
    try:
        resolved = path.resolve()
    except OSError:
        return True
    return resolved.parent == resolved


def _classify_dir(path: Path | None) -> tuple[str, Path | None]:
    if path is None or not str(path).strip():
        return "absent", None
    try:
        resolved = _verifier()._root(path.expanduser())
    except ValueError as error:
        return _code_from_message(str(error)), None
    except FileNotFoundError:
        return "absent", None
    except OSError:
        return "inaccessible", None
    if _too_broad(resolved):
        return "too_broad", None
    return "ok", resolved


def _add_root(roots: list[Path], seen: set[str], path: Path | None, gaps: _Gaps) -> None:
    if path is None:
        return
    try:
        resolved = path.resolve()
    except OSError:
        gaps.unknown("protected_root_unresolved")
        return
    if _too_broad(resolved):
        gaps.unknown("protected_root_ignored_as_too_broad")
        return
    key = os.path.normcase(str(resolved))
    if key in seen:
        return
    seen.add(key)
    roots.append(resolved)


def _within(child: Path, parent: Path) -> bool:
    try:
        child_resolved = os.path.normcase(str(child.resolve()))
        parent_resolved = os.path.normcase(str(parent.resolve()))
    except OSError:
        return True
    if _too_broad(Path(parent_resolved)):
        return True
    try:
        Path(child_resolved).relative_to(parent_resolved)
    except ValueError:
        return False
    return True


def _chain_has_link(path: Path) -> bool:
    verifier = _verifier()
    absolute = path if path.is_absolute() else path.absolute()
    for component in (absolute, *absolute.parents):
        try:
            info = component.lstat()
        except FileNotFoundError:
            continue
        except OSError:
            return True
        if verifier._linked(info):
            return True
    return False


def _destination(path: Path) -> Path:
    destination = path.expanduser()
    if not destination.is_absolute():
        destination = Path.cwd() / destination
    return destination


def _refuse_output_location(path: Path, roots: list[Path]) -> Path:
    destination = _destination(path)
    if not destination.parent.is_dir():
        raise ReportWriteError("output_parent_missing")
    if _chain_has_link(destination.parent):
        raise ReportWriteError("output_parent_symlink")
    try:
        destination.lstat()
    except FileNotFoundError:
        pass
    else:
        raise ReportWriteError("output_exists")
    resolved = destination.resolve(strict=False)
    for root in roots:
        if _too_broad(root) or _within(resolved, root):
            raise ReportWriteError("output_inside_protected_root")
    return destination


def _tokenize(text: str) -> list:
    tokens: list = []
    index = 0
    length = len(text)
    while index < length:
        char = text[index]
        if char.isspace():
            index += 1
            continue
        if char in "{}":
            tokens.append(char)
            index += 1
        elif char == '"':
            index += 1
            chars: list[str] = []
            closed = False
            while index < length:
                current = text[index]
                if current == "\\":
                    index += 1
                    if index >= length:
                        raise MalformedVDF
                    chars.append({"n": "\n", "t": "\t", "r": "\r"}.get(text[index], text[index]))
                    index += 1
                elif current == '"':
                    index += 1
                    closed = True
                    break
                else:
                    chars.append(current)
                    index += 1
                if len(chars) > MAX_VDF_STRING:
                    raise MalformedVDF
            if not closed:
                raise MalformedVDF
            tokens.append("".join(chars))
        elif char == "/" and index + 1 < length and text[index + 1] == "/":
            newline = text.find("\n", index)
            index = length if newline < 0 else newline + 1
        else:
            raise MalformedVDF
        if len(tokens) > MAX_VDF_TOKENS:
            raise MalformedVDF
    return tokens


def _parse_vdf(text: str) -> dict:
    tokens = _tokenize(text)
    position = 0

    def value(depth: int):
        nonlocal position
        if depth > MAX_VDF_DEPTH or position >= len(tokens):
            raise MalformedVDF
        token = tokens[position]
        if token == "{":
            position += 1
            mapping: dict = {}
            while position < len(tokens) and tokens[position] != "}":
                key = tokens[position]
                if not isinstance(key, str):
                    raise MalformedVDF
                position += 1
                mapping[key] = value(depth + 1)
            if position >= len(tokens) or tokens[position] != "}":
                raise MalformedVDF
            position += 1
            return mapping
        if not isinstance(token, str) or token == "}":
            raise MalformedVDF
        position += 1
        return token

    if not tokens or not isinstance(tokens[0], str):
        raise MalformedVDF
    root_key = tokens[0]
    position = 1
    tree = {root_key: value(0)}
    if position != len(tokens):
        raise MalformedVDF
    return tree


def _ci_get(mapping, key: str):
    if not isinstance(mapping, dict):
        return None
    folded = key.casefold()
    for candidate, item in mapping.items():
        if isinstance(candidate, str) and candidate.casefold() == folded:
            return item
    return None


def _library_paths(tree: dict) -> list[str]:
    root = _ci_get(tree, "libraryfolders")
    if not isinstance(root, dict):
        raise MalformedVDF
    paths = []
    for key, item in root.items():
        if isinstance(item, dict):
            raw = _ci_get(item, "path")
            if isinstance(raw, str):
                paths.append(raw)
        elif isinstance(item, str) and isinstance(key, str) and key.isdigit():
            paths.append(item)
    return paths


def _is_absolute_library_path(value: str) -> bool:
    if not value or len(value) > 1024 or "\x00" in value or "\n" in value or "\r" in value:
        return False
    if re.match(r"^[A-Za-z]:[\\/]", value):
        return True
    if value.startswith("\\\\") and not value.startswith("\\\\\\"):
        return True
    return value.startswith("/") and not value.startswith("//")


def _as_library_path(value: str) -> Path | None:
    if not _is_absolute_library_path(value):
        return None
    path = Path(value)
    if os.name == "nt":
        return path if path.is_absolute() else None
    if value.startswith("/") and path.is_absolute():
        return path
    return None


def _decode_text(data: bytes) -> str:
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    if data.startswith(b"\xef\xbb\xbf"):
        return data.decode("utf-8-sig")
    if b"\x00" in data[:64]:
        return data.decode("utf-16")
    return data.decode("utf-8")


def _read_text_file(path: Path, limit: int) -> tuple[str, str]:
    try:
        info = path.absolute().lstat()
    except FileNotFoundError:
        return "absent", ""
    except OSError:
        return "inaccessible", ""
    verifier = _verifier()
    if verifier._linked(info):
        return "symlink", ""
    if not stat.S_ISREG(info.st_mode):
        return "not_regular", ""
    try:
        verifier._root(path.absolute().parent)
    except ValueError:
        return "symlink", ""
    except OSError:
        return "inaccessible", ""
    try:
        with verifier._open_readonly(path.absolute()) as stream:
            data = stream.read(limit + 1)
    except ValueError:
        return "symlink", ""
    except OSError:
        return "inaccessible", ""
    if len(data) > limit:
        return "too_large", ""
    try:
        return "ok", _decode_text(data)
    except (UnicodeError, ValueError):
        return "malformed", ""


def _relative_status(root: Path, relative: str) -> tuple[str, Path | None, os.stat_result | None]:
    verifier = _verifier()
    cursor = root
    parts = PurePosixPath(relative).parts
    info = None
    for index, part in enumerate(parts):
        cursor = cursor / part
        try:
            info = cursor.lstat()
        except FileNotFoundError:
            return "absent", None, None
        except OSError:
            return "inaccessible", None, None
        if verifier._linked(info):
            return "symlink", None, None
        last = index == len(parts) - 1
        if not last and not stat.S_ISDIR(info.st_mode):
            return "not_a_directory", None, None
        if last and not stat.S_ISREG(info.st_mode):
            return "not_regular", None, None
    return "ok", cursor, info


def _valid_installdir(value: str | None) -> str | None:
    if value is None or len(value) > 80 or any(mark in value for mark in ("..", "/", "\\", ":")):
        return None
    if not _INSTALLDIR.fullmatch(value):
        return None
    return value


def _field_status(value, validator) -> tuple[str, str | None]:
    if value is None:
        return "absent", None
    if not isinstance(value, str):
        return "malformed", None
    cleaned = validator(value)
    if cleaned is None:
        return "malformed", None
    return "read", cleaned


def _manifest_fields(tree: dict) -> tuple[str | None, str | None]:
    state = _ci_get(tree, "AppState")
    if not isinstance(state, dict):
        raise MalformedVDF
    build = _ci_get(state, "buildid")
    install = _ci_get(state, "installdir")
    return (build if isinstance(build, str) else None, install if isinstance(install, str) else None)


def _unavailable_registry() -> dict:
    return {
        "steam_paths": {"status": "unavailable", "paths": []},
        "bakkes_path": {"status": "unavailable", "path": None},
    }


def _registry_value(key, name: str) -> str | None:
    import winreg
    try:
        raw, kind = winreg.QueryValueEx(key, name)
    except FileNotFoundError:
        return None
    if kind not in (winreg.REG_SZ, winreg.REG_EXPAND_SZ) or not isinstance(raw, str):
        return None
    text = os.path.expandvars(raw).strip().strip('"')
    return text or None


def _live_registry() -> dict:
    if sys.platform != "win32":
        return _unavailable_registry()
    import winreg
    steam_paths: list[str] = []
    steam_status = "absent"
    inaccessible = False
    queries = (
        (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath"),
    )
    for hive, subkey, name in queries:
        try:
            with winreg.OpenKey(hive, subkey, 0, winreg.KEY_READ) as key:
                value = _registry_value(key, name)
        except FileNotFoundError:
            continue
        except OSError as error:
            if getattr(error, "winerror", None) == 2 or getattr(error, "errno", None) == 2:
                continue
            inaccessible = True
            continue
        if value:
            steam_paths.append(value)
            steam_status = "read"
    if inaccessible and steam_status != "read":
        steam_status = "inaccessible"
    bakkes_status = "absent"
    bakkes_path = None
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\BakkesMod\AppPath", 0, winreg.KEY_READ) as key:
            bakkes_path = _registry_value(key, "BakkesModPath")
        if bakkes_path:
            bakkes_status = "read"
        else:
            bakkes_path = None
    except FileNotFoundError:
        pass
    except OSError as error:
        if getattr(error, "winerror", None) not in (None, 2) and getattr(error, "errno", None) != 2:
            bakkes_status = "inaccessible"
    return {
        "steam_paths": {"status": steam_status, "paths": steam_paths},
        "bakkes_path": {"status": bakkes_status, "path": bakkes_path},
    }


def _normalize_registry(payload) -> dict:
    if not isinstance(payload, dict):
        return {
            "steam_paths": {"status": "unknown", "paths": []},
            "bakkes_path": {"status": "unknown", "path": None},
        }
    steam = payload.get("steam_paths") if isinstance(payload.get("steam_paths"), dict) else {}
    bakkes = payload.get("bakkes_path") if isinstance(payload.get("bakkes_path"), dict) else {}
    allowed = {"read", "absent", "unavailable", "inaccessible", "unknown"}
    steam_status = steam.get("status")
    bakkes_status = bakkes.get("status")
    paths = [item for item in steam.get("paths") or [] if isinstance(item, str)]
    bakkes_path = bakkes.get("path") if isinstance(bakkes.get("path"), str) else None
    return {
        "steam_paths": {"status": steam_status if steam_status in allowed else "unknown", "paths": paths},
        "bakkes_path": {"status": bakkes_status if bakkes_status in allowed else "unknown", "path": bakkes_path},
    }


def _interpret_tasklist(returncode: int, text: str):
    if re.search(r'(?i)"RocketLeague\.exe"', text):
        return True
    if "RocketLeague.exe" in text or "rocketleague.exe" in text.lower():
        return "unknown"
    if returncode == 0:
        return False
    return "unknown"


def _live_process() -> dict:
    if sys.platform != "win32":
        return {"running": "unknown", "source": "not_windows"}
    try:
        completed = subprocess.run(
            TASKLIST_ARGV,
            shell=False,
            capture_output=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {"running": "unknown", "source": "tasklist_error"}
    text = completed.stdout.decode("utf-8", "replace")
    running = _interpret_tasklist(completed.returncode, text)
    source = "tasklist" if running in (True, False) else "tasklist_error"
    return {"running": running, "source": source}


def _normalize_process(payload) -> dict:
    running = payload.get("running") if isinstance(payload, dict) else "unknown"
    if running not in (True, False, "unknown"):
        running = "unknown"
    return {"running": running, "source": "injected"}


def _windows_file_version(executable: Path) -> str | None:
    if sys.platform != "win32":
        return None
    import ctypes
    from ctypes import wintypes
    version = ctypes.WinDLL("version", use_last_error=True)
    version.GetFileVersionInfoSizeW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
    version.GetFileVersionInfoSizeW.restype = wintypes.DWORD
    version.GetFileVersionInfoW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID]
    version.GetFileVersionInfoW.restype = wintypes.BOOL
    version.VerQueryValueW.argtypes = [
        wintypes.LPCVOID, wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.UINT),
    ]
    version.VerQueryValueW.restype = wintypes.BOOL
    ignored = wintypes.DWORD()
    size = version.GetFileVersionInfoSizeW(str(executable), ctypes.byref(ignored))
    if not size or size > 1_048_576:
        return None
    buffer = ctypes.create_string_buffer(size)
    if not version.GetFileVersionInfoW(str(executable), 0, size, buffer):
        return None
    pointer, length = ctypes.c_void_p(), wintypes.UINT()
    if not version.VerQueryValueW(buffer, "\\", ctypes.byref(pointer), ctypes.byref(length)) or length.value < 52:
        return None
    fields = ctypes.cast(pointer, ctypes.POINTER(wintypes.DWORD * 13)).contents
    if fields[0] != 0xFEEF04BD:
        return None
    return ".".join(str(part) for part in (
        fields[2] >> 16, fields[2] & 65535, fields[3] >> 16, fields[3] & 65535,
    ))


def _version_lookup(path: Path, reader) -> dict:
    if reader is not None:
        source = "injected"
        try:
            value = reader(path)
        except OSError:
            return {"status": "inaccessible", "version": None, "source": source}
    elif sys.platform != "win32":
        return {"status": "unavailable", "version": None, "source": "not_windows"}
    else:
        source = "windows_api"
        try:
            value = _windows_file_version(path)
        except (OSError, AttributeError, ValueError):
            return {"status": "inaccessible", "version": None, "source": source}
    if value is None or value == "":
        return {"status": "unknown", "version": None, "source": source}
    if not isinstance(value, str) or not _VERSION_TOKEN.fullmatch(value):
        return {"status": "malformed", "version": None, "source": source}
    return {"status": "read", "version": value, "source": source}


def _blank_executable(status: str) -> dict:
    return {
        "status": status,
        "relative": EXE_RELATIVE,
        "size": None,
        "sha256": None,
        "file_version": None,
        "file_version_status": "not_checked",
        "file_version_source": "not_checked",
        "associated_steam_build_id": None,
    }


def _inspect_executable(root: Path, reader, gaps: _Gaps) -> tuple[dict, list[str]]:
    status, path, info = _relative_status(root, EXE_RELATIVE)
    record = _blank_executable(status)
    if status != "ok" or path is None or info is None:
        if status not in {"ok", "absent"}:
            gaps.error(status, "rocket_league_exe")
            gaps.unknown("rocket_league_exe")
        return record, []
    if info.st_size > MAX_EXE_BYTES:
        record["status"] = "too_large"
        record["size"] = info.st_size
        gaps.error("too_large", "rocket_league_exe")
        return record, []
    try:
        hashed = _verifier()._hash_file(path, info)
    except ValueError as error:
        code = _code_from_message(str(error))
        record["status"] = code
        gaps.error(code, "rocket_league_exe")
        gaps.unknown("rocket_league_exe")
        return record, []
    except OSError:
        record["status"] = "inaccessible"
        gaps.error("inaccessible", "rocket_league_exe")
        gaps.unknown("rocket_league_exe")
        return record, []
    size = hashed.get("size") if isinstance(hashed, dict) else None
    sha = hashed.get("sha256") if isinstance(hashed, dict) else None
    if (type(size) is not int or size < 0 or not isinstance(sha, str) or len(sha) != 64
            or any(char not in "0123456789abcdef" for char in sha)):
        record["status"] = "read_error"
        gaps.error("read_error", "rocket_league_exe")
        return record, []
    record.update(status="hashed", size=size, sha256=sha)
    version = _version_lookup(path, reader)
    record["file_version"] = version["version"]
    record["file_version_status"] = version["status"]
    record["file_version_source"] = version["source"]
    if version["status"] not in {"read", "unavailable"}:
        gaps.unknown("rocket_league_file_version")
    return record, [EXE_RELATIVE]


def _steam_build_association(game_path: Path | None, discovered: Path | None) -> str:
    """Say whether the selected executable folder matches Steam's one discovered install."""
    if game_path is None or discovered is None:
        return "unverified"
    game_key = os.path.normcase(str(game_path.resolve()))
    discovered_key = os.path.normcase(str(discovered.resolve()))
    return "matched" if game_key == discovered_key else "mismatched"


def _menu_package_name(name: str) -> bool:
    if not re.fullmatch(r"[A-Za-z0-9_.+-]{1,120}", name):
        return False
    folded = name.casefold()
    return folded.endswith(".upk") and folded.startswith("gfx") and ("menu" in folded or "shell" in folded)


def _blank_packages(status: str) -> dict:
    missing = list(PACKAGE_CANDIDATES)
    return {
        "status": status,
        "search": "top_level_of_known_cooked_directories",
        "observation": "filenames_and_sizes_only",
        "size_source": "single_stat",
        "directories": [{"relative": relative, "status": status} for relative in PACKAGE_DIRS],
        "found": [],
        "not_observed": missing if status == "absent" else [],
        "not_confirmed": missing if status == "unknown" else [],
        "skipped": [],
    }


def _scan_packages(root: Path, gaps: _Gaps) -> dict:
    found = []
    skipped = []
    directories = []
    seen: set[str] = set()
    finished = True
    unsafe = False
    verifier = _verifier()
    for relative_dir in PACKAGE_DIRS:
        directory = root.joinpath(*PurePosixPath(relative_dir).parts)
        entry = {"relative": relative_dir, "status": "listed"}
        try:
            info = directory.lstat()
        except FileNotFoundError:
            entry["status"] = "absent"
            directories.append(entry)
            continue
        except OSError:
            entry["status"] = "inaccessible"
            finished = False
            directories.append(entry)
            continue
        if verifier._linked(info):
            entry["status"] = "symlink"
            finished = False
            directories.append(entry)
            continue
        parent_linked = False
        cursor = root
        for part in PurePosixPath(relative_dir).parts:
            cursor = cursor / part
            try:
                part_info = cursor.lstat()
            except OSError:
                parent_linked = True
                break
            if verifier._linked(part_info):
                parent_linked = True
                break
        if parent_linked:
            entry["status"] = "symlink"
            finished = False
            directories.append(entry)
            continue
        if not stat.S_ISDIR(info.st_mode):
            entry["status"] = "not_a_directory"
            finished = False
            directories.append(entry)
            continue
        count = 0
        try:
            with os.scandir(directory) as children:
                for child in children:
                    count += 1
                    if count > MAX_PACKAGE_ENTRIES:
                        entry["status"] = "capped"
                        finished = False
                        gaps.unknown("package_listing_capped")
                        break
                    name = child.name
                    if not _menu_package_name(name):
                        continue
                    relative = f"{relative_dir}/{name}"
                    try:
                        child_info = Path(child.path).lstat()
                    except OSError:
                        skipped.append({"relative": relative, "reason": "inaccessible"})
                        unsafe = True
                        seen.add(name.casefold())
                        continue
                    if verifier._linked(child_info):
                        skipped.append({"relative": relative, "reason": "symlink"})
                        unsafe = True
                        seen.add(name.casefold())
                        continue
                    if not stat.S_ISREG(child_info.st_mode):
                        skipped.append({"relative": relative, "reason": "not_regular"})
                        unsafe = True
                        seen.add(name.casefold())
                        continue
                    if len(found) >= MAX_PACKAGE_MATCHES:
                        entry["status"] = "capped"
                        finished = False
                        gaps.unknown("package_listing_capped")
                        break
                    found.append({"relative": relative, "size": child_info.st_size})
                    seen.add(name.casefold())
        except OSError:
            entry["status"] = "inaccessible"
            finished = False
        directories.append(entry)
    found.sort(key=lambda item: item["relative"].casefold())
    skipped.sort(key=lambda item: item["relative"].casefold())
    missing = [name for name in PACKAGE_CANDIDATES if name.casefold() not in seen]
    if not finished:
        status = "partial"
        not_observed: list[str] = []
        not_confirmed = missing
        gaps.unknown("package_listing_incomplete")
    elif unsafe:
        status = "partial"
        not_observed = missing
        not_confirmed = []
    elif all(item["status"] == "absent" for item in directories):
        status = "absent"
        not_observed = missing
        not_confirmed = []
    else:
        status = "listed"
        not_observed = missing
        not_confirmed = []
    return {
        "status": status,
        "search": "top_level_of_known_cooked_directories",
        "observation": "filenames_and_sizes_only",
        "size_source": "single_stat",
        "directories": directories,
        "found": found,
        "not_observed": not_observed,
        "not_confirmed": not_confirmed,
        "skipped": skipped,
    }


def _combine(statuses: list[str], values: list[str | None]) -> tuple[str, str | None]:
    if not statuses:
        return "unknown", None
    reads = [value for status, value in zip(statuses, values) if status == "read" and value is not None]
    failures = [status for status in statuses if status not in {"read", "absent"}]
    unique = sorted(set(reads))
    if reads and failures:
        return ("partial", unique[0]) if len(unique) == 1 else ("ambiguous", None)
    if failures and not reads:
        return (failures[0], None) if len(set(failures)) == 1 and "absent" not in statuses else ("partial", None)
    if unique:
        return ("read", unique[0]) if len(unique) == 1 else ("ambiguous", None)
    if statuses and all(status == "absent" for status in statuses):
        return "absent", None
    return "unknown", None


def _inspect_steam(explicit: Path | None, registry: dict, gaps: _Gaps) -> tuple[dict, list[Path], Path | None]:
    seen: set[str] = set()
    counts = {status: 0 for status in _LIBRARY_STATUSES}
    queue: list[Path] = []
    if explicit is not None:
        queue.append(explicit.expanduser())
    steam_registry = registry["steam_paths"]
    if steam_registry["status"] == "read":
        for raw in steam_registry["paths"]:
            queue.append(Path(raw))
    elif steam_registry["status"] in {"unavailable", "unknown", "inaccessible"}:
        gaps.unknown("steam_registry_" + steam_registry["status"])
    accepted: list[Path] = []
    capped = False
    while queue and len(seen) < MAX_LIBRARIES:
        raw = queue.pop(0)
        status, root = _classify_dir(raw)
        if status != "ok" or root is None:
            if status not in {"ok", "absent"}:
                gaps.error(status if status != "too_broad" else "protected_root_ignored_as_too_broad", "steam_root")
                if status == "too_broad":
                    gaps.unknown("protected_root_ignored_as_too_broad")
            continue
        key = os.path.normcase(str(root))
        if key in seen:
            continue
        seen.add(key)
        accepted.append(root)
        text_status, text = _read_text_file(root / "steamapps" / "libraryfolders.vdf", MAX_VDF_BYTES)
        extra: list[str] = []
        if text_status == "ok":
            try:
                extra = _library_paths(_parse_vdf(text))
                text_status = "read"
            except MalformedVDF:
                text_status = "malformed"
        if text_status not in counts:
            text_status = "read_error"
        counts[text_status] += 1
        if text_status == "malformed":
            gaps.error("malformed", "libraryfolders")
            gaps.unknown("libraryfolders_malformed")
        elif text_status not in {"read", "absent"}:
            gaps.error(text_status, "libraryfolders")
            gaps.unknown("libraryfolders_" + text_status)
        for raw_path in extra:
            library = _as_library_path(raw_path)
            if library is None:
                continue
            if len(seen) + len(queue) >= MAX_LIBRARIES:
                capped = True
                break
            queue.append(library)
    if capped:
        gaps.unknown("library_list_capped")
    roots = []
    root_seen: set[str] = set()
    for root in accepted:
        _add_root(roots, root_seen, root, gaps)
    build_statuses: list[str] = []
    build_values: list[str | None] = []
    install_statuses: list[str] = []
    install_values: list[str | None] = []
    manifest_failures = 0
    game_folders: list[Path] = []
    for root in accepted:
        text_status, text = _read_text_file(root / "steamapps" / f"appmanifest_{APP_ID}.acf", MAX_VDF_BYTES)
        if text_status == "absent":
            build_statuses.append("absent")
            build_values.append(None)
            install_statuses.append("absent")
            install_values.append(None)
            continue
        if text_status != "ok":
            manifest_failures += 1
            failure = text_status if text_status in _LIBRARY_STATUSES else "read_error"
            build_statuses.append(failure)
            build_values.append(None)
            install_statuses.append(failure)
            install_values.append(None)
            gaps.error(failure, "appmanifest_252950")
            continue
        try:
            build_raw, install_raw = _manifest_fields(_parse_vdf(text))
        except MalformedVDF:
            manifest_failures += 1
            build_statuses.append("malformed")
            build_values.append(None)
            install_statuses.append("malformed")
            install_values.append(None)
            gaps.error("malformed", "appmanifest_252950")
            continue
        build_status, build_value = _field_status(build_raw, lambda item: item if _BUILD_ID.fullmatch(item) else None)
        install_status, install_value = _field_status(install_raw, _valid_installdir)
        build_statuses.append(build_status)
        build_values.append(build_value)
        install_statuses.append(install_status)
        install_values.append(install_value)
        if install_status == "read" and install_value is not None:
            folder_status, folder = _classify_dir(root / "steamapps" / "common" / install_value)
            if folder_status == "ok" and folder is not None:
                game_folders.append(folder)
                _add_root(roots, root_seen, folder, gaps)
    if not accepted:
        build_status, build_id = "unknown", None
        install_status = "unknown"
        gaps.unknown("steam_build_id")
        gaps.unknown("game_install_folder")
    else:
        build_status, build_id = _combine(build_statuses, build_values)
        install_status, _install_name = _combine(install_statuses, install_values)
        if build_status != "read":
            gaps.unknown("steam_build_id")
        if install_status != "read":
            gaps.unknown("game_install_folder")
        if manifest_failures:
            gaps.unknown("appmanifest_unread")
    unique_folders = []
    folder_seen: set[str] = set()
    for folder in game_folders:
        key = os.path.normcase(str(folder))
        if key not in folder_seen:
            folder_seen.add(key)
            unique_folders.append(folder)
    discovered = unique_folders[0] if len(unique_folders) == 1 else None
    if len(unique_folders) > 1:
        discovered = None
        gaps.unknown("multiple_game_folders")
    manifests_read = sum(1 for status in build_statuses if status == "read")
    if not accepted:
        manifest_status = "unknown"
    elif manifests_read and manifest_failures:
        manifest_status = "partial"
    elif manifests_read:
        manifest_status = "read"
    elif manifest_failures:
        manifest_status = "partial"
    else:
        manifest_status = "absent"
    section = {
        "registry_status": steam_registry["status"],
        "registry_source": registry["source"],
        "explicit_root": explicit is not None,
        "libraries_checked": len(accepted),
        "libraryfolders": counts,
        "app_252950": {
            "manifest_status": manifest_status,
            "manifests_read": manifests_read,
            "build_id": build_id if build_status in {"read", "partial"} else None,
            "build_id_status": build_status,
            "installdir_status": install_status,
        },
    }
    return section, roots, discovered


def _injector_candidates(bakkes: Path | None) -> list[Path]:
    candidates = []
    if bakkes is not None:
        candidates.append(bakkes.parent / "BakkesMod.exe")
        candidates.append(bakkes.parent.parent / "BakkesMod.exe")
    if sys.platform == "win32":
        program = os.environ.get("PROGRAMFILES", r"C:\Program Files")
        program_x86 = os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")
        candidates.append(Path(program) / "BakkesMod" / "BakkesMod.exe")
        candidates.append(Path(program_x86) / "BakkesMod" / "BakkesMod.exe")
        local = os.environ.get("LOCALAPPDATA")
        if local:
            candidates.append(Path(local) / "BakkesMod" / "BakkesMod.exe")
    return candidates


def _classify_file(path: Path, limit: int) -> tuple[str, Path | None]:
    try:
        info = path.absolute().lstat()
    except FileNotFoundError:
        return "absent", None
    except OSError:
        return "inaccessible", None
    verifier = _verifier()
    if verifier._linked(info):
        return "symlink", None
    if not stat.S_ISREG(info.st_mode):
        return "not_regular", None
    if info.st_size > limit:
        return "too_large", None
    try:
        _verifier()._root(path.absolute().parent)
        resolved = path.absolute().resolve(strict=True)
    except ValueError:
        return "symlink", None
    except OSError:
        return "inaccessible", None
    return "ok", resolved


def _version_file(bakkes: Path) -> dict:
    selected = None
    for relative in ("version.txt", "data/version.txt"):
        status, text = _read_text_file(bakkes / relative, MAX_VERSION_TEXT_BYTES)
        if status == "absent":
            continue
        token = None
        file_status = status if status != "ok" else "malformed"
        if status == "ok":
            stripped = text.strip()
            if _VERSION_TOKEN.fullmatch(stripped):
                token = stripped
                file_status = "read"
        selected = {
            "status": file_status,
            "file": relative,
            "version": token,
            "meaning": _VERSION_FILE_MEANING,
        }
        break
    if selected is None:
        selected = {"status": "absent", "file": None, "version": None, "meaning": _VERSION_FILE_MEANING}
    return selected


def _component_versions(paths: list[Path], reader, limit: int) -> tuple[dict, list[Path]]:
    present: list[Path] = []
    versions = []
    sources = []
    blocked = []
    for path in paths:
        status, resolved = _classify_file(path, limit)
        if status == "absent":
            continue
        if status != "ok" or resolved is None:
            blocked.append(status)
            continue
        present.append(resolved)
        found = _version_lookup(resolved, reader)
        sources.append(found["source"])
        if found["status"] == "read" and found["version"] is not None:
            versions.append(found["version"])
        elif found["status"] not in {"unavailable", "not_checked"}:
            blocked.append(found["status"])
    if not present and not blocked:
        file_status = "absent"
    elif blocked and not present:
        file_status = blocked[0]
    elif blocked:
        file_status = "partial"
    elif len(present) > 1 and len(set(versions)) > 1:
        file_status = "ambiguous"
    else:
        file_status = "present"
    unique = sorted(set(versions))
    if len(unique) == 1 and file_status in {"present", "partial"}:
        version_status = "read"
        version = unique[0]
    elif len(unique) > 1:
        version_status = "ambiguous"
        version = None
        file_status = "ambiguous"
    elif present and sources and sources[0] == "not_windows":
        version_status = "unavailable"
        version = None
    elif present:
        version_status = "unknown"
        version = None
    else:
        version_status = "not_checked"
        version = None
    source = sources[0] if sources else "not_checked"
    return {
        "file_status": file_status,
        "file_version": version,
        "file_version_status": version_status,
        "file_version_source": source,
    }, present


def _inspect_bakkes(registry: dict, reader, roots: list[Path], seen: set[str], gaps: _Gaps) -> dict:
    bakkes_registry = registry["bakkes_path"]
    bakkes_root = None
    directory_status = bakkes_registry["status"]
    if directory_status == "read" and isinstance(bakkes_registry.get("path"), str):
        classified, bakkes_root = _classify_dir(Path(bakkes_registry["path"]))
        if classified != "ok":
            directory_status = classified
            bakkes_root = None
            gaps.error(classified, "bakkes_directory")
            gaps.unknown("bakkes_directory")
        else:
            _add_root(roots, seen, bakkes_root, gaps)
    elif directory_status in {"unavailable", "unknown", "inaccessible"}:
        gaps.unknown("bakkes_directory")
    version_file = (
        _version_file(bakkes_root) if bakkes_root is not None
        else {"status": "unknown" if directory_status != "absent" else "absent", "file": None,
              "version": None, "meaning": _VERSION_FILE_MEANING}
    )
    if version_file["status"] in {"malformed", "inaccessible", "symlink", "too_large", "not_regular", "read_error"}:
        gaps.error(version_file["status"], "bakkes_version_file")
    if version_file["status"] != "read":
        gaps.unknown("bakkes_version_file")
    if bakkes_root is not None or sys.platform == "win32":
        injector, injector_files = _component_versions(
            _injector_candidates(bakkes_root), reader, MAX_VERSION_TARGET_BYTES,
        )
    else:
        injector = {
            "file_status": "unknown", "file_version": None,
            "file_version_status": "not_checked", "file_version_source": "not_checked",
        }
        injector_files = []
        gaps.unknown("bakkes_injector_file")
    if bakkes_root is not None:
        dll, _dll_files = _component_versions(
            [bakkes_root / "bakkesmod.dll", bakkes_root / "dll" / "bakkesmod.dll"],
            reader, MAX_VERSION_TARGET_BYTES,
        )
    else:
        dll = {
            "file_status": "absent" if directory_status == "absent" else "unknown",
            "file_version": None,
            "file_version_status": "not_checked",
            "file_version_source": "not_checked",
        }
        if dll["file_status"] != "absent":
            gaps.unknown("bakkes_dll_file")
    for path in injector_files:
        _add_root(roots, seen, path.parent, gaps)
    injector["meaning"] = _INJECTOR_MEANING
    dll["meaning"] = _DLL_MEANING
    if injector["file_status"] not in {"present", "absent", "unknown"}:
        gaps.unknown("bakkes_injector_file")
    if injector["file_version_status"] not in {"read", "unavailable", "not_checked", "absent"}:
        gaps.unknown("bakkes_injector_file_version")
    if dll["file_status"] not in {"present", "absent", "unknown"}:
        gaps.unknown("bakkes_dll_file")
    gaps.unknown("loaded_bakkes_dll_version")
    gaps.unknown("loaded_bakkes_plugin_version")
    return {
        "directory_status": directory_status,
        "directory_source": registry["source"],
        "version_file": version_file,
        "injector": injector,
        "dll_file": dll,
        "loaded_dll_version": "unknown",
        "loaded_plugin_version": "unknown",
    }


def _assert_public(document: dict) -> None:
    def strings(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for key, item in value.items():
                yield from strings(key)
                yield from strings(item)
        elif isinstance(value, list):
            for item in value:
                yield from strings(item)

    for text in strings(document):
        if text.startswith("/") or text.startswith("\\\\") or re.match(r"^[A-Za-z]:[\\/]", text):
            raise ReportWriteError("report_failed_privacy_check")
        if ".." in PurePosixPath(text).parts:
            raise ReportWriteError("report_failed_privacy_check")
        folded = text.casefold()
        if "lastowner" in folded or "steamid" in folded:
            raise ReportWriteError("report_failed_privacy_check")


def _explicit_protected(game_root: Path | None, steam_root: Path | None) -> list[Path]:
    roots = []
    seen: set[str] = set()
    gaps = _Gaps()
    for candidate in (game_root, steam_root):
        status, root = _classify_dir(candidate)
        if status == "ok":
            _add_root(roots, seen, root, gaps)
    return roots


def collect(
    game_root: Path | None = None,
    steam_root: Path | None = None,
    *,
    registry_reader=None,
    process_probe=None,
    version_reader=None,
) -> tuple[dict, list[Path]]:
    """Collect an identification report. Reader hooks are test-only and labeled injected."""
    gaps = _Gaps()
    if sys.platform != "win32":
        gaps.unknown("windows_only_checks_not_run")
    if registry_reader is not None:
        registry = _normalize_registry(registry_reader())
        registry["source"] = "injected"
    elif sys.platform != "win32":
        registry = _unavailable_registry()
        registry["source"] = "not_windows"
    else:
        try:
            registry = _live_registry()
        except OSError:
            registry = {
                "steam_paths": {"status": "inaccessible", "paths": []},
                "bakkes_path": {"status": "inaccessible", "path": None},
            }
        registry["source"] = "windows_registry"
    if process_probe is not None:
        try:
            process = _normalize_process(process_probe())
        except OSError:
            process = {"running": "unknown", "source": "injected"}
    else:
        process = _live_process()
    if process["running"] == "unknown":
        gaps.unknown("rocket_league_process")
    steam, roots, discovered = _inspect_steam(
        Path(steam_root) if steam_root is not None else None, registry, gaps,
    )
    seen = {os.path.normcase(str(path)) for path in roots}
    explicit_game = Path(game_root) if game_root is not None else None
    game_status, game_path = _classify_dir(explicit_game) if explicit_game is not None else ("unset", None)
    if explicit_game is not None:
        if game_status == "ok" and game_path is not None:
            root_status = "explicit"
            _add_root(roots, seen, game_path, gaps)
        else:
            root_status = game_status
            game_path = None
            gaps.error(game_status, "game_root")
            gaps.unknown("game_root")
    elif discovered is not None:
        root_status = "manifest"
        game_path = discovered
    elif "multiple_game_folders" in gaps.unknowns:
        root_status = "ambiguous"
        game_path = None
    elif steam["libraries_checked"] == 0:
        root_status = "unknown"
        game_path = None
        gaps.unknown("game_root")
    else:
        root_status = "absent"
        game_path = None
    if game_path is not None:
        executable, hashed = _inspect_executable(game_path, version_reader, gaps)
        packages = _scan_packages(game_path, gaps)
    else:
        # No install directory was opened, so package names stay unconfirmed.
        exe_status = "absent" if root_status == "absent" else "unknown"
        executable = _blank_executable(exe_status)
        packages = _blank_packages("unknown")
        hashed = []
        if exe_status == "unknown":
            gaps.unknown("rocket_league_exe")
    build_association = _steam_build_association(game_path, discovered)
    app_manifest = steam["app_252950"]
    if build_association == "matched" and app_manifest["build_id_status"] == "read":
        executable["associated_steam_build_id"] = app_manifest["build_id"]
    elif build_association == "matched":
        gaps.unknown("executable_steam_build_id")
    elif build_association == "unverified":
        gaps.unknown("steam_build_association")
    bakkes = _inspect_bakkes(registry, version_reader, roots, seen, gaps)
    unknowns, errors = gaps.lists()
    document = {
        "format": "mct-windows-baseline-v1",
        "platform": sys.platform,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "limits": {
            "proves_native_menus": False,
            "proves_gameplay": False,
            "proves_eac": False,
            "proves_steam_preservation": False,
            "entire_install_hashed": False,
            "files_hashed": hashed,
            "note": _LIMITS_NOTE,
        },
        "steam": steam,
        "game": {
            "root_status": root_status if root_status != "unset" else "unknown",
            "steam_build_association": build_association,
            "executable": executable,
        },
        "packages": packages,
        "bakkesmod": bakkes,
        "rocket_league_process": process,
        "unknowns": unknowns,
        "errors": errors,
        "containment": {"protected_roots_checked": len(roots), "output_path_recorded": False},
    }
    _assert_public(document)
    return document, roots


def _write_new(path: Path, document: dict) -> None:
    _assert_public(document)
    destination = _destination(path)
    payload = json.dumps(document, indent=2, sort_keys=True) + "\n"
    try:
        with destination.open("x", encoding="utf-8") as stream:
            stream.write(payload)
    except FileExistsError as error:
        raise ReportWriteError("output_exists") from error


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True,
                        help="New JSON file outside Steam, Rocket League, and BakkesMod folders")
    parser.add_argument("--game-root", type=Path,
                        help="Optional install folder that contains Binaries/Win64/RocketLeague.exe")
    parser.add_argument("--steam-root", type=Path,
                        help="Optional Steam folder that contains steamapps")
    args = parser.parse_args(argv)
    try:
        early = _explicit_protected(args.game_root, args.steam_root)
        _refuse_output_location(args.output, early)
        document, protected = collect(args.game_root, args.steam_root)
        _refuse_output_location(args.output, protected)
        _write_new(args.output, document)
    except ReportWriteError as error:
        print(f"Cannot write identification report: {error.code}", file=sys.stderr)
        return 2
    except (OSError, ValueError, TypeError, ImportError):
        print("Cannot write identification report: internal_error", file=sys.stderr)
        return 2
    print(
        "Wrote an identification report. This does not prove native menus, gameplay, EAC, "
        "or Steam preservation, and it does not hash the entire install."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
