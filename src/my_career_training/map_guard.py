"""Restore a map journal from an older build. New launches do not replace game files.

Pinned RLBot core v5.0.0-rc18 (source commit 11d5d863ec2f8b2647741cff22a2c59c6b6ad08e,
RLBotServer.exe sha256 454986c71bacebfcb923a8eeddba7ea62ecc6c42d28b4cab89f653e2eab1ccd1)
loads a custom map only in FlatToCommand.MakeOpenCommand: CustomMap.IsCustomMap is true
when game_map_upk already exists and ends in .upk or .udk, and the CustomMap constructor
then copies that file over TAGame/CookedPCConsole/Haunted_TrainStation_P.upk. The other
branch only appends the string to an Open console command. It does not load an external
package, and no other file in that commit writes a cooked game map.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from .storage import Store

CUSTOM_MAP_LAUNCH_UNAVAILABLE = (
    "Custom map launch is unavailable because the current loader changes an "
    "installed Rocket League file. To preserve your Steam game, this route is "
    "disabled. You can still browse maps and save favorites."
)
_BUILTIN_MAPS = {
    "DFHStadium", "DFHStadium_P", "Mannfield", "EuroStadium_P", "ChampionsField", "CS_P",
    "UtopiaColiseum", "UtopiaStadium_P", "BeckwithPark", "Park_P", "Stadium_P",
}


def digest(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def _external_map_specifier(value):
    """True for a path the pinned core would treat as a custom file, or any file path.

    Built-in arena names stay false so career and lesson matches are unchanged.
    A missing file is not treated as safe: MakeOpenCommand would only emit Open
    plus that string, which is not a proven package load.
    """
    if not isinstance(value, str):
        return False
    text = value.strip()
    if not text or text in _BUILTIN_MAPS:
        return False
    normalized = text.replace("\\", "/")
    leaf = normalized.rsplit("/", 1)[-1]
    if leaf.lower().endswith((".upk", ".udk")):
        return True
    if "/" in normalized or text.startswith("\\\\"):
        return True
    return len(text) >= 3 and text[0].isalpha() and text[1] == ":"


def _map_specifiers(request):
    values = []
    workshop = request.get("workshop")
    if isinstance(workshop, dict):
        values.append(workshop.get("path"))
        values.append(workshop.get("game_map_upk"))
    fixture = request.get("fixture")
    if isinstance(fixture, dict):
        values.append(fixture.get("map"))
    values.append(request.get("game_map_upk"))
    return values


def custom_map_requested(request) -> bool:
    """A Workshop payload or a file-like arena is a custom-map launch attempt."""
    if not isinstance(request, dict):
        return False
    if request.get("workshop", None) not in (None, False):
        return True
    return any(_external_map_specifier(value) for value in _map_specifiers(request))


def refuse_custom_map_launch(request):
    """Reject before any match config, map transaction, or game process exists."""
    if custom_map_requested(request):
        raise ValueError(CUSTOM_MAP_LAUNCH_UNAVAILABLE)


class MapGuard:
    def __init__(self, directory):
        self.directory = Path(directory) / "map-recovery"
        self.receipt = self.directory / "active.json"

    def prepare(self, executable, custom_map):
        """Retired. Older builds backed up and exposed Haunted_TrainStation_P.upk here.

        This does not read the game, copy a map, write a journal, or clear an
        older journal. Call recover() for a journal an older version already wrote.
        """
        del executable, custom_map
        raise ValueError(CUSTOM_MAP_LAUNCH_UNAVAILABLE)

    def recover(self):
        if not self.receipt.exists():
            return
        # A live game may have the cooked slot open. Leave the journal untouched.
        from . import platforms
        if platforms.game_processes():
            raise RuntimeError("Close Rocket League before restoring the original map. The backup was preserved.")
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
