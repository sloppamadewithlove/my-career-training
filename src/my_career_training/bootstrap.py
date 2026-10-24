"""Launch only an owned, supported offline Steam game and install our plugin."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

from .platforms import (ProcessIdentity, detect_installations, game_processes,
                        native_launcher_pending, offline_launch_arguments)
from .plugin_session import PluginSession, PluginSessionError


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


def _injector_running():
    import psutil
    return any((process.info.get("name") or "").lower() == "bakkesmod.exe"
               for process in psutil.process_iter(["name"]))


def _injector_candidates(root=None):
    from .bakkes_installation import discover_bakkesmod_injectors
    candidates = [Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "BakkesMod/BakkesMod.exe",
                  Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)")) / "BakkesMod/BakkesMod.exe",
                  Path(os.environ.get("LOCALAPPDATA", "")) / "BakkesMod/BakkesMod.exe"]
    if root is not None:
        candidates.extend((root.parent / "BakkesMod.exe", root.parent.parent / "BakkesMod.exe"))
    candidates.extend(discover_bakkesmod_injectors())
    return candidates


def bakkes_ready():
    """Require both the plugin folder and an installed or running injector."""
    root = bakkes_directory()
    if root is None:
        return None
    return root if _injector_running() or any(path.is_file() for path in _injector_candidates(root)) else None


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


def _plugin_session(directory, root=None):
    return PluginSession(directory, root=root, game_running=lambda: bool(game_processes()))


def install_plugin(directory=None):
    """Journal BakkesMod's current plugin files, then stage this launch's copy.

    The documented in-game command is `plugin load`. BakkesMod also autoloads
    cfg/plugins.cfg, and it does not document an external one-shot load. This
    appends that autoload only for the owned launch. restore_plugin_session puts
    the previous bytes back. A load line that was already there is left alone.
    """
    root = bakkes_directory()
    if root is None:
        raise RuntimeError("Install BakkesMod from https://bakkesmod.com, open it once, then launch My Career again.")
    report = _plugin_session(directory, root).begin(plugin_binary())
    install_plugin.last_report = report
    return root


def recover_plugin_session(directory=None):
    """Restore an interrupted plugin session once no Rocket League process is running."""
    from .native_community_binding import recover_native_community
    from .storage import data_dir
    try:
        recover_native_community(directory if directory is not None else data_dir())
    except Exception as exc:
        raise PluginSessionError(f"Community trial recovery is incomplete: {exc}") from exc
    return _plugin_session(directory).recover()


def restore_plugin_session(directory=None):
    """Restore owned plugin files, or keep the receipt while a game process is open."""
    from .native_community_binding import recover_native_community
    from .storage import data_dir
    try:
        recover_native_community(directory if directory is not None else data_dir())
    except Exception as exc:
        raise PluginSessionError(f"Community trial recovery is incomplete: {exc}") from exc
    return _plugin_session(directory).finish()


def plugin_session_notices(directory=None):
    return _plugin_session(directory).notices()


def ensure_injector_running():
    if _injector_running():
        return
    for candidate in _injector_candidates(bakkes_directory()):
        if candidate.is_file():
            subprocess.Popen([str(candidate)], shell=False)
            return
    raise RuntimeError("Open BakkesMod, then launch My Career again. It loads the in-game career interface.")


def preflight_offline(settings):
    """Validate the game and Steam before offering first-run dependencies."""
    if sys.platform != "win32":
        raise RuntimeError("The in-game build runs on Windows with your installed Rocket League.")
    if game_processes():
        raise RuntimeError("Close the existing Rocket League window before launching My Career offline.")
    if native_launcher_pending():
        raise RuntimeError("The offline menu helper is still finishing a session. Wait for it to exit before launching My Career again.")
    if settings.get("launcher") != "steam":
        raise RuntimeError("The in-game launcher currently requires Steam. Epic support needs a separately verified offline launch route.")
    executable = Path(settings.get("install_path", ""))
    if executable.is_dir():
        executable = executable / "Binaries/Win64/RocketLeague.exe"
    if not executable.is_file() or executable.name.lower() != "rocketleague.exe":
        raise RuntimeError("Choose your Rocket League installation in first-run setup.")
    verified = False
    for install in detect_installations():
        if install.get("launcher") != "steam":
            continue
        try:
            if executable.samefile(install["path"]):
                verified = True
                break
        except (KeyError, OSError):
            continue
    if not verified:
        raise RuntimeError("This executable does not match Steam's recorded Rocket League installation. "
                           "Choose the game installed by Steam before launching My Career.")
    import psutil
    if not any((p.info.get("name") or "").lower() == "steam.exe" for p in psutil.process_iter(["name"])):
        raise RuntimeError("Open Steam and sign in, then launch My Career again.")
    return executable


def _usable_timestamp(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def launch_offline(settings, directory=None, *, native_session=None):
    import psutil
    executable = preflight_offline(settings)
    recover_plugin_session(directory)
    if native_session is not None:
        # Preparation writes only a private per-session package. Complete it
        # before any BakkesMod files/config are temporarily staged.
        native_session.prepare(executable, plugin_binary())
    try:
        install_plugin(directory)
        ensure_injector_running()
        # A normal Steam launch may have started while dependencies were staged.
        # Refuse another launch and defer file restoration until that game exits.
        preflight_offline(settings)
        if native_session is not None:
            return native_session.launch(executable)
        # Current RLBot's Steam launcher uses the installed executable and Steam identity.
        # -noeac is the official offline mode, never an online anti-cheat bypass.
        env = dict(os.environ, SteamAppId="252950", SteamGameId="252950")
        process = subprocess.Popen([str(executable), "-noeac", "-rlbot",
            "RLBot_ControllerURL=127.0.0.1:23233", "RLBot_PacketSendRate=240", "-nomovie"],
            cwd=executable.parent, env=env, shell=False)
        owned = psutil.Process(process.pid)
        created = owned.create_time()
        if not _usable_timestamp(created):
            raise RuntimeError("Rocket League did not report a valid process start time.")
        return ProcessIdentity(process.pid, created, str(executable.resolve()))
    except Exception as exc:
        if getattr(exc, "defer_restore", False):
            # The retained helper can still create its child even when no game
            # is enumerable yet. Leave the recovery journal and staged files.
            raise
        try:
            restore_plugin_session(directory)
        except PluginSessionError as restore_error:
            raise RuntimeError(f"{exc} BakkesMod files could not be restored: {restore_error}") from exc
        raise


def verify_owned_offline(identity):
    import psutil
    try:
        if not _usable_timestamp(identity.created):
            return False
        current = psutil.Process(identity.pid)
        live = current.create_time()
        if not _usable_timestamp(live) or abs(live - identity.created) > .01:
            return False
        if Path(current.exe()).resolve() != Path(identity.executable).resolve():
            return False
        return offline_launch_arguments(current.cmdline())
    except (psutil.Error, OSError, ValueError, TypeError, AttributeError):
        return False


def run_service(directory, *, native_movie_trial=False):
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
    try:
        recover_plugin_session(directory)
    except PluginSessionError as exc:
        backend.store.close()
        QMessageBox.critical(None, "My Career plugin recovery", str(exc))
        return 1
    try:
        preflight_offline(backend.document["settings"])
    except Exception as exc:
        backend.store.close()
        QMessageBox.critical(None, "My Career offline startup", str(exc))
        return 1
    if bakkes_ready() is None:
        from .setup_dialog import ensure_bakkes_available
        if not ensure_bakkes_available(Path(directory) / "setup-cache", finder=bakkes_ready):
            backend.store.close()
            return 0
    backend.exitRequested.connect(app.quit)
    bridge = FileBridge(directory, backend.dispatch, lambda: backend.state)
    bridge.poll()
    native_session = None
    try:
        if native_movie_trial:
            from .native_offline import NativeOfflineSession
            native_session = NativeOfflineSession(directory, bridge.session)
            backend.owned_game = launch_offline(backend.document["settings"], directory,
                                               native_session=native_session)
        else:
            backend.owned_game = launch_offline(backend.document["settings"], directory)
    except Exception as exc:
        if not getattr(exc, "defer_restore", False):
            try:
                restore_plugin_session(directory)
            except PluginSessionError as restore_error:
                exc = RuntimeError(f"{exc} BakkesMod files could not be restored: {restore_error}")
        bridge.close()
        backend.store.close()
        QMessageBox.critical(None, "My Career offline startup", str(exc))
        return 1
    notices = plugin_session_notices(directory)
    if notices:
        QMessageBox.warning(None, "BakkesMod plugin setup", "\n".join(notices))
    if native_session is not None:
        from .native_community_binding import NativeCommunityBinding
        backend.native_community = None
        try:
            backend.native_community = NativeCommunityBinding(native_session, bridge, bakkes_directory())
        except Exception as exc:
            # The already owned game remains usable; no community load is offered.
            backend.error = f"Community trial is unavailable: {exc}"
    started = time.monotonic()
    plugin_seen = False
    connection_warning_shown = False
    handoff_error_shown = False
    def tick():
        nonlocal plugin_seen, connection_warning_shown, handoff_error_shown
        try:
            backend.plugin_status = bridge.plugin_status()
            if backend.plugin_status.get("pid") != backend.owned_game.pid:
                backend.plugin_status = {}
            plugin_seen = plugin_seen or bool(backend.plugin_status)
            if native_session is not None:
                if backend.native_community is not None:
                    backend.native_community.refresh()
                warning = native_session.warning()
                if warning:
                    backend.error = warning
            bridge.poll()
            if time.monotonic() - started > 5 and not is_alive(backend.owned_game):
                # The backend's separate timer still needs to restore setup and
                # request the normal launcher after the career process exits.
                if backend.lifecycle.frozen:
                    return
                if native_session is not None and not native_session.finished():
                    return
                if backend.lifecycle.state == "Error/Recovery" and not handoff_error_shown:
                    handoff_error_shown = True
                    QMessageBox.critical(None, "My Career handoff", backend.lifecycle.last_error)
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
    result = 1
    restore_error = None
    try:
        result = app.exec()
    finally:
        try:
            backend.close()
        finally:
            try:
                bridge.close()
            finally:
                try:
                    restoration = restore_plugin_session(directory)
                    if restoration.get("status") not in {"idle", "restored"}:
                        restore_error = PluginSessionError(
                            "Rocket League or its offline menu helper is still open, so My Career's temporary setup could not be restored. "
                            "Wait for the offline session to finish, then open My Career to complete recovery before playing online.")
                except PluginSessionError as exc:
                    restore_error = exc
    if restore_error is not None:
        QMessageBox.critical(None, "My Career plugin recovery", str(restore_error))
        return 1
    return result
