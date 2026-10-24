"""Owned native-menu development session; never prepares the installed game in place."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .platforms import game_processes, native_launcher_pending
from .storage import data_dir


def runtime_directory(component: str) -> Path:
    if component not in {"native", "native-menu"}:
        raise ValueError("Unknown native runtime component.")
    package = Path(__file__).resolve().parent
    candidates = (package / "runtime" / component, package.parent.parent / "runtime" / component)
    return next((path for path in candidates if path.is_dir()), candidates[0])


class NativeOfflineSession:
    """Retain the prepared package and launcher for one FileBridge nonce.

    Constructing this object has no side effects. The bootstrap calls prepare
    before staging BakkesMod, then launch only after its second offline preflight.
    The external helper owns the game's lifetime and file holds; dropping this
    Python object must never terminate that game.
    """

    def __init__(self, directory, session):
        self.directory = Path(directory)
        self.session = session
        self.prepared = None
        self.owner = None
        self.uncertain = None
        self.executable = None

    def prepare(self, executable, plugin):
        from .native_menu_assets import prepare_native_menu

        if self.prepared is not None or self.owner is not None:
            raise RuntimeError("This native menu session was already prepared.")
        # The current plugin intentionally uses the normal local bridge path.
        # Do not compose a movie for a different --data-dir and silently point
        # its host at the player's unrelated normal bridge.
        if self.directory.resolve() != data_dir().resolve():
            raise RuntimeError("The native menu trial requires the normal My Career data folder.")
        executable = Path(executable).resolve(strict=True)
        if (executable.name.lower() != "rocketleague.exe" or executable.parent.name.lower() != "win64"
                or executable.parent.parent.name.lower() != "binaries"):
            raise RuntimeError("The native menu requires the matching Steam game layout.")
        plugin = Path(plugin)
        if not plugin.is_file() or plugin.is_symlink() or not 0 < plugin.stat().st_size <= 16 * 1024 * 1024:
            raise RuntimeError("The native plugin candidate is invalid.")
        receipt_path = plugin.with_name("plugin-build-receipt.json")
        if receipt_path.stat().st_size > 1024 * 1024:
            raise RuntimeError("The native plugin build receipt is invalid.")
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if (not isinstance(receipt, dict) or receipt.get("native_movie_trial") is not True
                or receipt.get("native_host_probe") is not False
                or receipt.get("gameplay_verified") is not False
                or receipt.get("sha256") != hashlib.sha256(plugin.read_bytes()).hexdigest()):
            raise RuntimeError("Build the matching native menu candidate before starting this trial.")
        private = self.directory / "native-menu-sessions"
        private.mkdir(exist_ok=True)
        self.prepared = prepare_native_menu(
            executable.parent.parent.parent, self.session, self.directory / "bridge", private,
            runtime_directory=runtime_directory("native-menu"),
        )
        self.executable = executable

    def launch(self, executable):
        from .native_launch import NativeLaunchUncertain, launch_native_offline

        if (self.prepared is None or self.owner is not None or self.uncertain is not None
                or Path(executable).resolve() != self.executable):
            raise RuntimeError("Prepare this native menu session before launching it.")
        try:
            self.owner = launch_native_offline(
                self.executable.parent.parent.parent, self.prepared.private_package,
                self.prepared.private_package_sha256, self.session,
                runtime_directory=runtime_directory("native"),
            )
        except NativeLaunchUncertain as exc:
            self.uncertain = exc
            raise
        return self.owner.identity

    def warning(self) -> str:
        if self.owner is None:
            return ""
        if self.owner.poll() == "degraded":
            return ("The offline menu helper stopped while Rocket League is still open. "
                    "Save your progress and close My Career before starting another session.")
        return ""

    def finished(self) -> bool:
        """Wait for both game and helper; release only already-exited helpers."""
        if self.owner is not None:
            return self.owner.poll() == "exited" and self.owner.release()
        if self.uncertain is not None:
            return (self.uncertain.helper_exited() and not game_processes()
                    and not native_launcher_pending() and self.uncertain.release())
        return True
