"""Validated atomic local saves with an OS-held single-instance lock."""
from __future__ import annotations

import copy
import json
import math
import os
import sys
import tempfile
from pathlib import Path
from typing import Callable

MAX_SAVE_BYTES = 32 * 1024 * 1024


def data_dir() -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "MyCareerTraining"
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/MyCareerTraining"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "MyCareerTraining"


def default_state() -> dict:
    return {"schema_version": 1, "career": None, "settings": {
        "launcher": "steam", "install_path": "", "text_scale": 1.0,
        "reduced_motion": False, "binding_profile": "actions"},
        "lesson_preferences": {}, "lesson_scenarios": {}, "attempts": [], "recordings": [],
        "browser_favorites": []}


def validate_state(value: dict) -> None:
    if not isinstance(value, dict) or type(value.get("schema_version")) is not int or value["schema_version"] != 1:
        raise ValueError("This save uses an unsupported format. Your existing save has been preserved.")
    for key, kind in (("settings", dict), ("lesson_preferences", dict), ("attempts", list), ("recordings", list)):
        if not isinstance(value.get(key), kind):
            raise ValueError(f"Save is missing valid {key} data.")
    from .training.scenario_setup import validate_lesson_scenarios
    validate_lesson_scenarios(value.get("lesson_scenarios", {}))
    if value.get("career") is not None and not isinstance(value["career"], dict):
        raise ValueError("Career data is malformed.")
    favorites = value.get("browser_favorites", [])
    if not isinstance(favorites, list) or len(favorites) > 512:
        raise ValueError("Training browser favorites are malformed.")
    seen = set()
    for favorite in favorites:
        if (not isinstance(favorite, dict) or set(favorite) != {"type", "id", "title", "subtitle", "detail"}
                or favorite.get("type") not in {"lesson", "workshop", "plugin"}):
            raise ValueError("Training browser favorites are malformed.")
        identity = (favorite["type"], favorite.get("id"))
        if (not isinstance(identity[1], str) or not identity[1] or len(identity[1]) > 128
                or ".." in identity[1] or identity in seen
                or any(char not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_:-"
                       for char in identity[1])):
            raise ValueError("Training browser favorites are malformed.")
        seen.add(identity)
        for key, limit in (("title", 240), ("subtitle", 240), ("detail", 240)):
            if (not isinstance(favorite.get(key), str) or len(favorite[key].encode("utf-8")) > limit
                    or (key == "title" and not favorite[key])
                    or any(ord(char) < 32 or char in "<>&" for char in favorite[key])):
                raise ValueError("Training browser favorite metadata is malformed.")
    settings = value["settings"]
    if settings.get("launcher") not in ("steam", "epic"):
        raise ValueError("Choose a supported launcher: Steam or Epic.")
    scale = settings.get("text_scale", 1)
    if type(scale) not in (int, float) or not 0.8 <= scale <= 1.6:
        raise ValueError("Text size must be between 80% and 160%.")
    def walk(node, depth=0):
        if depth > 40:
            raise ValueError("Save nesting is too deep.")
        if isinstance(node, float) and not math.isfinite(node):
            raise ValueError("Save contains invalid numbers.")
        if isinstance(node, dict):
            for k, v in node.items():
                if not isinstance(k, str):
                    raise ValueError("Save keys must be text.")
                walk(v, depth + 1)
        elif isinstance(node, list):
            for v in node:
                walk(v, depth + 1)
        elif not isinstance(node, (str, int, float, bool, type(None))):
            raise ValueError("Unsupported save value.")
    walk(value)


class Store:
    def __init__(self, path: Path | str, validator: Callable | None = None):
        self.directory = Path(path)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "career.json"
        self.backup_path = self.directory / "career.last-good.json"
        self.validator = validator
        self._lock = os.fdopen(os.open(self.directory / "app.lock", os.O_RDWR | os.O_CREAT, 0o600), "r+b")
        try:
            if os.fstat(self._lock.fileno()).st_size == 0:
                self._lock.write(b"0")
                self._lock.flush()
            self._lock.seek(0)
            if sys.platform == "win32":
                import msvcrt
                msvcrt.locking(self._lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, BlockingIOError) as exc:
            self._lock.close()
            raise RuntimeError("My Career Training is already open. Return to its existing window.") from exc

    def _validate(self, state):
        validate_state(state)
        if self.validator:
            self.validator(state)

    def _read(self, path):
        if Path(path).stat().st_size > MAX_SAVE_BYTES:
            raise ValueError("This save is too large to import safely.")
        try:
            state = json.loads(Path(path).read_text(encoding="utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("The save is damaged. Its original bytes are preserved; restore a backup.") from exc
        self._validate(state)
        return state

    @staticmethod
    def _atomic(path: Path, data: bytes):
        path.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(prefix=".mct-", dir=path.parent)
        try:
            with os.fdopen(handle, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
            if sys.platform != "win32":
                directory_fd = os.open(path.parent, os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def load(self):
        return self._read(self.path) if self.path.exists() else default_state()

    def save(self, state):
        self._validate(state)
        data = json.dumps(state, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
        if len(data) > MAX_SAVE_BYTES:
            raise ValueError("Save exceeds the storage limit. Export or remove older recordings first.")
        if self.path.exists():
            self._read(self.path)  # Never overwrite damaged data implicitly.
            self._atomic(self.backup_path, self.path.read_bytes())
        self._atomic(self.path, data)
        return copy.deepcopy(state)

    def export_file(self, path):
        state = self.load()
        target = Path(path)
        if target.resolve() in (self.path.resolve(), self.backup_path.resolve()):
            raise ValueError("Choose a separate file for your export.")
        self._atomic(target, json.dumps(state, ensure_ascii=False, indent=2, allow_nan=False).encode())
        return target

    def import_file(self, path):
        state = self._read(path)
        if self.path.exists():
            # Preserve even corrupt originals, with collision-free names.
            import time
            preserved = self.directory / f"before-import-{time.time_ns()}.json"
            self._atomic(preserved, self.path.read_bytes())
        self._atomic(self.path, json.dumps(state, ensure_ascii=False, allow_nan=False).encode())
        return copy.deepcopy(state)

    def backup(self):
        self._read(self.path)
        self._atomic(self.backup_path, self.path.read_bytes())
        return self.backup_path

    def close(self):
        if not self._lock.closed:
            self._lock.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
