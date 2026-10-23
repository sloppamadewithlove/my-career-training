"""Local, nonce-bound file bridge between the in-game plugin and career service."""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path

from .storage import Store

ALLOWED_ACTIONS = frozenset({
    "navigate", "new_career", "play_match", "lineup", "replace_recruit", "rename_recruit",
    "set_format", "set_difficulty", "next_season", "abandon_fixture", "select_lesson",
    "start_lesson", "retry_lesson", "stop_session", "assistance", "settings", "setup_finish",
    "diagnostics", "loadout", "restore_explanations", "lesson_variant", "play_recording",
    "return_hub", "quit_game", "workshop_favorite", "play_workshop", "choose_provider",
    "install_provider", "import_recording", "stop_ghost", "training_settings", "ghost_control", "refresh_workshop",
})


def _read_shared(path: Path, limit: int):
    """Read one file version while allowing the other process to replace it."""
    if sys.platform != "win32":
        with path.open("rb") as stream:
            modified = os.fstat(stream.fileno()).st_mtime
            return stream.read(limit + 1), modified

    import ctypes
    import msvcrt
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                   ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.CreateFileW(str(path), 0x80000000, 0x1 | 0x2 | 0x4,
                                None, 3, 0x80, None)
    if handle == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        descriptor = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
    except BaseException:
        kernel.CloseHandle(handle)
        raise
    with os.fdopen(descriptor, "rb") as stream:
        modified = os.fstat(stream.fileno()).st_mtime
        return stream.read(limit + 1), modified


def _publish_state(path: Path, data: bytes):
    # A short-lived reader from another plugin or antivirus can deny the
    # replacement. Keep every attempt atomic and retain the exact OS error if
    # the denial persists; never publish a partially written state file.
    for attempt in range(5):
        try:
            Store._atomic(path, data)
            return
        except OSError as exc:
            if (sys.platform != "win32" or getattr(exc, "winerror", None) not in (5, 32, 33)
                    or attempt == 4):
                raise OSError(f"Offline career state could not be published: {exc}") from exc
            time.sleep(0.01 * (attempt + 1))


class FileBridge:
    def __init__(self, directory, dispatch, snapshot, clock=time.time):
        self.directory = Path(directory) / "bridge"
        self.commands = self.directory / "commands"
        self.commands.mkdir(parents=True, exist_ok=True)
        self.session = str(uuid.uuid4())
        self.dispatch, self.snapshot, self.clock = dispatch, snapshot, clock
        self.ack = {}
        self._last_plugin_status = {}
        self.seen = set()
        self.started = clock()

    def poll(self):
        for path in sorted(self.commands.glob("*.json"))[:32]:
            command_id = ""
            try:
                if path.is_symlink() or path.stat().st_size > 65536:
                    raise ValueError("Invalid command file.")
                command = json.loads(path.read_text(encoding="utf-8"))
                command_id = command.get("id", "")
                if str(uuid.UUID(command_id)) != command_id or path.stem != command_id:
                    raise ValueError("Invalid command identity.")
                if command_id in self.seen:
                    continue
                if command.get("protocol") != 1 or command.get("session") != self.session:
                    raise ValueError("The menu connection expired. Reopen My Career.")
                if command.get("action") not in ALLOWED_ACTIONS or not isinstance(command.get("payload", {}), dict):
                    raise ValueError("Unsupported in-game command.")
                self.seen.add(command_id)
                self.dispatch(command["action"], command.get("payload", {}))
                error = self.snapshot().get("error", "")
                self.ack = {"id": command_id, "ok": not bool(error), "error": error}
            except (ValueError, KeyError, TypeError, OSError, AttributeError) as exc:
                self.ack = {"id": command_id, "ok": False, "error": str(exc)}
            finally:
                path.unlink(missing_ok=True)
        if len(self.seen) > 4096:
            # Commands are consumed; retaining recent identities protects retransmission.
            self.seen = set(list(self.seen)[-2048:])
        state = dict(self.snapshot(), protocol=1, bridge_session=self.session,
                     published_at=self.clock(), offline=True, command_ack=self.ack)
        _publish_state(self.directory / "state.json", json.dumps(state, allow_nan=False).encode())

    def plugin_status(self):
        path = self.directory / "plugin-status.json"
        try:
            if path.is_symlink():
                return {}
            raw, modified = _read_shared(path, 2 * 1024 * 1024)
            if len(raw) > 2 * 1024 * 1024:
                return {}
            value = json.loads(raw)
            if (not isinstance(value, dict) or modified < self.started
                    or value.get("bridge_session") != self.session
                    or not isinstance(value.get("published_at"), (int, float))
                    or not -1 <= self.clock() - value["published_at"] <= 5):
                return {}
            self._last_plugin_status = value
            return value
        except OSError as exc:
            cached = self._last_plugin_status
            if (getattr(exc, "winerror", None) in (5, 32, 33)
                    and cached.get("bridge_session") == self.session
                    and isinstance(cached.get("published_at"), (int, float))
                    and 0 <= self.clock() - cached["published_at"] <= 5):
                return cached
            return {}
        except ValueError:
            return {}

    def close(self):
        _publish_state(self.directory / "state.json", json.dumps({"protocol":1,"offline":True,
            "bridge_session":"", "published_at":0,"error":"My Career is closed."}).encode())
