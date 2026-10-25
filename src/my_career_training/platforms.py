"""Launcher detection and identity-scoped game process operations."""
from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

import psutil


def detect_installations() -> list[dict]:
    if sys.platform != "win32":
        return []
    roots = {Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)")) / "Steam"}
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            roots.add(Path(winreg.QueryValueEx(key, "SteamPath")[0]))
    except OSError:
        pass
    for root in list(roots):
        vdf = root / "steamapps/libraryfolders.vdf"
        if vdf.exists():
            for path in re.findall(r'"path"\s+"([^"]+)"', vdf.read_text(encoding="utf-8", errors="replace")):
                roots.add(Path(path.replace("\\\\", "\\")))
    found = []
    for root in roots:
        manifest = root / "steamapps/appmanifest_252950.acf"
        if manifest.exists():
            matches = re.findall(r'"installdir"\s+"([^"]+)"', manifest.read_text(encoding="utf-8", errors="replace"))
            for folder in matches:
                exe = root / "steamapps/common" / folder / "Binaries/Win64/RocketLeague.exe"
                if exe.is_file():
                    found.append({"launcher": "steam", "path": str(exe), "available": True})
    manifests = Path(os.environ.get("PROGRAMDATA", "C:/ProgramData")) / "Epic/EpicGamesLauncher/Data/Manifests"
    for file in manifests.glob("*.item"):
        try:
            item = json.loads(file.read_text(encoding="utf-8"))
            if item.get("AppName") == "Sugar" or item.get("DisplayName") == "Rocket League":
                exe = Path(item["InstallLocation"]) / item.get("LaunchExecutable", "Binaries/Win64/RocketLeague.exe")
                if exe.is_file():
                    found.append({"launcher": "epic", "path": str(exe), "available": True,
                                  "app_name": item.get("AppName", "Sugar")})
        except (ValueError, KeyError, OSError):
            continue
    return found


@dataclass(frozen=True)
class ProcessIdentity:
    pid: int
    created: float
    executable: str

    def as_dict(self):
        return {"pid": self.pid, "created": self.created, "executable": self.executable}


def game_processes():
    found = []
    for process in psutil.process_iter(["pid", "name", "create_time", "exe", "cmdline"]):
        try:
            if (process.info.get("name") or "").lower() == "rocketleague.exe":
                found.append(process)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return found


def native_launcher_pending() -> bool:
    """Conservatively gate file recovery while a native launch can create a game.

    This is a blocking check, never process ownership or permission to terminate.
    Checking the helper's name also covers a previous app process that exited
    after Popen but before recording its helper identity. Missing process names
    or enumeration failures cannot establish that restoration is safe.
    """
    try:
        for process in psutil.process_iter(["name"]):
            name = process.info.get("name")
            if not isinstance(name, str) or not name:
                return True
            if name.casefold() == "mctnativelauncher.exe":
                return True
    except (psutil.Error, OSError):
        return True
    return False


def offline_launch_arguments(arguments) -> bool:
    """Require RLBot's offline mode and reject conflicting EAC launch modes."""
    tokens = {str(argument).lower() for argument in arguments}
    return "-rlbot" in tokens and not ({"-noeac", "-eac"} & tokens)


def owned_game_since(started: float, expected_path: str = "") -> ProcessIdentity | None:
    candidates = []
    for process in game_processes():
        try:
            command = process.cmdline()
            if process.create_time() < started - 1 or not offline_launch_arguments(command):
                continue
            executable = process.exe()
            if expected_path and Path(executable).resolve() != Path(expected_path).resolve():
                continue
            candidates.append(ProcessIdentity(process.pid, process.create_time(), executable))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    if len(candidates) > 1:
        raise RuntimeError("More than one career game was found. Close extra game windows and retry.")
    return candidates[0] if candidates else None


def is_alive(identity: ProcessIdentity | None) -> bool:
    if identity is None:
        return False
    try:
        process = psutil.Process(identity.pid)
        return process.is_running() and abs(process.create_time() - identity.created) < 0.01
    except psutil.NoSuchProcess:
        return False


def graceful_close(identity: ProcessIdentity | None):
    if identity is None or not is_alive(identity):
        return
    if sys.platform != "win32":
        raise RuntimeError("Graceful game closure requires Windows.")
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    closed = []
    @callback_type
    def callback(hwnd, _):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == identity.pid and user32.IsWindowVisible(hwnd):
            user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE, never terminate a game process.
            closed.append(hwnd)
        return True
    user32.EnumWindows(callback, 0)
    if not closed:
        raise RuntimeError("Close the career Rocket League window yourself, then choose Retry.")


def launch_online(launcher: str):
    if sys.platform != "win32":
        raise RuntimeError("Open the Windows build on your gaming PC to launch Rocket League.")
    if game_processes():
        raise RuntimeError("Rocket League is still running. Close its window before opening online play.")
    if launcher == "steam":
        uri = "steam://run/252950"
    elif launcher == "epic":
        uri = "com.epicgames.launcher://apps/" + quote("Sugar", safe="") + "?action=launch&silent=true"
    else:
        raise ValueError("Choose Steam or Epic first.")
    os.startfile(uri)
    return "Opening Rocket League. Choose its normal EAC-enabled mode if your launcher asks."
