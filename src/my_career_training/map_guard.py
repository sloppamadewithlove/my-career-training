"""Recover only our verified temporary RLBot map substitution after interruption."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import shutil
from .storage import Store


def digest(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


class MapGuard:
    def __init__(self, directory):
        self.directory = Path(directory) / "map-recovery"
        self.receipt = self.directory / "active.json"

    def prepare(self, executable, custom_map):
        self.recover()
        exe = Path(executable).resolve()
        source = Path(custom_map["path"]).resolve()
        if digest(source) != custom_map["sha256"]:
            raise ValueError("The Workshop map changed since it was checked.")
        original = exe.parent.parent.parent / "TAGame/CookedPCConsole/Haunted_TrainStation_P.upk"
        if not original.is_file() or original.is_symlink():
            raise ValueError("The game's temporary custom-map slot was not found. Verify Rocket League's game files.")
        self.directory.mkdir(parents=True, exist_ok=True)
        backup = self.directory / "Haunted_TrainStation_P.original.upk"
        shutil.copy2(original, backup)
        identity = digest(backup)
        if digest(original) != identity:
            raise ValueError("The game map changed during backup. Close other map loaders and retry.")
        Store._atomic(self.receipt, json.dumps({"original":str(original),"backup":str(backup),
            "original_sha256":identity,"custom_sha256":custom_map["sha256"]}).encode())
        return original

    def recover(self):
        if not self.receipt.exists():
            return
        data = json.loads(self.receipt.read_text())
        original, backup = Path(data["original"]), Path(data["backup"])
        if backup.parent.resolve() != self.directory.resolve() or digest(backup) != data["original_sha256"]:
            raise ValueError("The saved map backup needs manual recovery. It has been preserved.")
        if original.is_symlink() or original.name != "Haunted_TrainStation_P.upk":
            raise ValueError("The game map recovery path is unexpected. Backup preserved.")
        current = digest(original) if original.exists() else None
        if current == data["original_sha256"]:
            self.receipt.unlink()
            return
        if current not in (None, data["custom_sha256"]):
            raise ValueError("Another tool changed the game map. My Career preserved its backup without overwriting that change.")
        Store._atomic(original, backup.read_bytes())
        self.receipt.unlink()
