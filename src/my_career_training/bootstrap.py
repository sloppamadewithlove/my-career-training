"""Launch only an owned, supported offline Steam game and install our plugin."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from .platforms import ProcessIdentity, game_processes
from .storage import Store


def bakkes_directory():
    candidates = []
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\BakkesMod\AppPath") as key:
                value, _ = winreg.QueryValueEx(key, "BakkesModPath")
                candidates.append(Path(value))
        except OSError:
            pass
    candidates.append(Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming")) / "bakkesmod/bakkesmod")
    return next((p for p in candidates if (p / "plugins").is_dir()), None)


def plugin_binary():
    package = Path(__file__).resolve().parent
    for path in (package / "runtime/plugins/MyCareerTraining.dll", package.parent.parent / "runtime/plugins/MyCareerTraining.dll"):
        if path.is_file():
            receipt_path = path.with_name("plugin-build-receipt.json")
            if not receipt_path.is_file():
                raise RuntimeError("The in-game plugin build receipt is missing. Install the complete package.")
            receipt = json.loads(receipt_path.read_text())
            expected = receipt.get("sha256") or receipt.get("dll_sha256")
            if expected != hashlib.sha256(path.read_bytes()).hexdigest():
                raise RuntimeError("The in-game plugin failed its integrity check. Reinstall this build.")
            return path
    raise RuntimeError("The in-game plugin is not built here. Install the Windows package from this release.")


def install_plugin():
    root = bakkes_directory()
    if root is None:
        raise RuntimeError("Install BakkesMod from https://bakkesmod.com, open it once, then launch My Career again.")
    source = plugin_binary()
    target = root / "plugins/MyCareerTraining.dll"
    if target.exists() and target.read_bytes() != source.read_bytes():
        shutil.copy2(target, target.with_suffix(".dll.previous"))
    if not target.exists() or target.read_bytes() != source.read_bytes():
        Store._atomic(target, source.read_bytes())
    config = root / "cfg/plugins.cfg"
    content = config.read_text(encoding="utf-8-sig") if config.exists() else ""
    command = "plugin load MyCareerTraining"
    active = [line.split("//", 1)[0].strip().rstrip(";").lower() for line in content.splitlines()]
    if command.lower() not in active:
        if config.exists():
            shutil.copy2(config, config.with_suffix(".cfg.mct-backup"))
        Store._atomic(config, (content.rstrip() + "\n" + command + "\n").encode())
    return root


def ensure_injector_running():
    import psutil
    for process in psutil.process_iter(["name"]):
        if (process.info.get("name") or "").lower() == "bakkesmod.exe":
            return
    candidates = [Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "BakkesMod/BakkesMod.exe",
                  Path(os.environ.get("LOCALAPPDATA", "")) / "BakkesMod/BakkesMod.exe"]
    for candidate in candidates:
        if candidate.is_file():
            subprocess.Popen([str(candidate)], shell=False)
            return
    raise RuntimeError("Open BakkesMod, then launch My Career again. It loads the in-game career interface.")


def launch_offline(settings):
    if sys.platform != "win32":
        raise RuntimeError("The in-game build runs on Windows with your installed Rocket League.")
    if game_processes():
        raise RuntimeError("Close the existing Rocket League window before launching My Career offline.")
    if settings.get("launcher") != "steam":
        raise RuntimeError("The in-game launcher currently requires Steam. Epic support needs a separately verified offline launch route.")
    executable = Path(settings.get("install_path", ""))
    if executable.is_dir():
        executable = executable / "Binaries/Win64/RocketLeague.exe"
    if not executable.is_file() or executable.name.lower() != "rocketleague.exe":
        raise RuntimeError("Choose your Rocket League installation in first-run setup.")
    import psutil
    if not any((p.info.get("name") or "").lower() == "steam.exe" for p in psutil.process_iter(["name"])):
        raise RuntimeError("Open Steam and sign in, then launch My Career again.")
    install_plugin()
    ensure_injector_running()
    # Current RLBot's Steam launcher uses the installed executable and Steam identity.
    # -noeac is the official offline mode, never an online anti-cheat bypass.
    env = dict(os.environ, SteamAppId="252950", SteamGameId="252950")
    process = subprocess.Popen([str(executable), "-noeac", "-rlbot",
        "RLBot_ControllerURL=127.0.0.1:23233", "RLBot_PacketSendRate=240", "-nomovie"],
        cwd=executable.parent, env=env, shell=False)
    owned = psutil.Process(process.pid)
    return ProcessIdentity(process.pid, owned.create_time(), str(executable.resolve()))


def verify_owned_offline(identity):
    import psutil
    try:
        current = psutil.Process(identity.pid)
        if abs(current.create_time() - identity.created) > .01 or Path(current.exe()).resolve() != Path(identity.executable).resolve():
            return False
        args = [arg.lower() for arg in current.cmdline()]
        return "-rlbot" in args and "-noeac" in args
    except (psutil.Error, OSError):
        return False


def run_service(directory):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QMessageBox
    from .bridge import Backend
    from .ingame import FileBridge
    from .platforms import is_alive
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    try:
        backend = Backend(directory)
    except Exception as exc:
        QMessageBox.critical(None, "My Career startup", str(exc))
        return 1
    backend.in_game = True
    if backend.document["settings"].get("binding_profile") in (None, "actions"):
        backend.document["settings"]["binding_profile"] = "playstation"
    backend.document["settings"].setdefault("bot_provider",
        "necto" if not backend.document["career"] or backend.document["career"]["format"] <= 3 else "mct-specialist-baseline")
    from .map_guard import MapGuard
    try:
        MapGuard(directory).recover()
    except Exception as exc:
        backend.store.close()
        QMessageBox.critical(None, "Workshop map recovery", str(exc))
        return 1
    backend._refresh_workshop()
    if backend.setup_required:
        if not backend.installations:
            backend.store.close()
            QMessageBox.critical(None, "My Career setup", "Rocket League was not found. Use MyCareerTraining.exe --manage for setup.")
            return 1
        found = next((i for i in backend.installations if i["launcher"] == "steam"), backend.installations[0])
        backend.document["settings"].update(launcher=found["launcher"], install_path=found["path"], setup_complete=True)
        backend.setup_required = False
        backend._save_current()
    backend.exitRequested.connect(app.quit)
    bridge = FileBridge(directory, backend.dispatch, lambda: backend.state)
    bridge.poll()
    try:
        backend.owned_game = launch_offline(backend.document["settings"])
    except Exception as exc:
        bridge.close()
        backend.store.close()
        QMessageBox.critical(None, "My Career offline startup", str(exc))
        return 1
    started = time.monotonic()
    plugin_seen = False
    connection_warning_shown = False
    def tick():
        nonlocal plugin_seen, connection_warning_shown
        try:
            backend.plugin_status = bridge.plugin_status()
            if backend.plugin_status.get("pid") != backend.owned_game.pid:
                backend.plugin_status = {}
            plugin_seen = plugin_seen or bool(backend.plugin_status)
            bridge.poll()
            if time.monotonic() - started > 5 and not is_alive(backend.owned_game):
                app.quit()
            elif time.monotonic() - started > 90 and not plugin_seen and not connection_warning_shown:
                connection_warning_shown = True
                backend.error = "The in-game menu has not connected. Check BakkesMod supports this game update and press F6."
                QMessageBox.warning(None, "My Career menu connection", backend.error)
        except Exception as exc:
            backend.error = str(exc)
    timer = QTimer()
    timer.timeout.connect(tick)
    timer.start(100)
    result = app.exec()
    backend.close()
    bridge.close()
    return result
