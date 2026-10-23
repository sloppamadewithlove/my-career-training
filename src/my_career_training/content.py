"""Local bot styles and attributed links; community map files never ship with the app."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import os
from pathlib import Path
import stat
import tempfile


LOADOUT_SOURCE = "https://github.com/RLBot/gui/blob/master/frontend/src/assets/items.csv"
MAP_ROUTE_SOURCE = "https://wiki.rlbot.org/v5/botmaking/config-files/"
BODY_IDS = {23: "Octane", 403: "Dominus", 30: "Merc", 22: "Breakout"}
STOCK_WHEELS_ID = 376  # OEM, verified against RLBot GUI's item catalog.
MAX_MAP_BYTES = 1024 * 1024 * 1024
_PACKAGE_MAGIC = b"\xc1\x83\x2a\x9e"


def garage_catalog() -> list[dict]:
    """Documented bot presets; exact current-game appearance remains unverified."""
    return [
        {
            "id": f"stock-{body_id}",
            "name": f"{name} · stock wheels",
            "title": name,
            "car_id": body_id,
            "primary_color": 27,
            "secondary_color": 0,
            "wheels_id": STOCK_WHEELS_ID,
            "scope": "Local career bots only; does not grant online inventory items",
            "source_url": LOADOUT_SOURCE,
            "status": "Identifiers documented; appearance needs current-game verification",
            "fallback": {"car_id": 23, "primary_color": 27, "secondary_color": 0},
        }
        for body_id, name in BODY_IDS.items()
    ]


def validate_loadout(loadout: dict) -> dict:
    """Return the career's supported three-field style, rejecting unknown IDs/keys."""
    if not isinstance(loadout, dict) or set(loadout) != {
        "car_id", "primary_color", "secondary_color"
    }:
        raise ValueError("Choose a body, team color, and accent from the bot garage.")
    if any(type(value) is not int for value in loadout.values()):
        raise ValueError("Bot appearance choices must use whole-number catalog identifiers.")
    if loadout["car_id"] not in BODY_IDS:
        raise ValueError("That body is not in the supported local bot catalog. Try Octane.")
    # Keep the shared safe portion of the team palettes; accents use the common palette.
    if not 0 <= loadout["primary_color"] <= 69:
        raise ValueError("Team color must be a supported palette index from 0 to 69.")
    if not 0 <= loadout["secondary_color"] <= 104:
        raise ValueError("Accent color must be a supported palette index from 0 to 104.")
    return dict(loadout)


# Creator pages checked 23 October 2026. These are discovery references, not
# compatibility certificates; no page is fetched during offline play.
_MAP_REFERENCES = [
    ("dribble-2-overhaul", "Dribble 2 Overhaul", "0xDigby and Martinn", "Dribbling",
     "Ground ball-control course with staged challenges.", "1694288506"),
    ("speed-jump-rings-3", "Speed Jump: Rings 3", "dmc", "Aerial control",
     "Aerial obstacle course; creator labels it intermediate to hard.", "1671658424"),
    ("giant-rings", "Lethamyr's Giant Rings Map", "Lethamyr", "Aerial control",
     "Rings course for aerial steering; Workshop textures may be required.", "2025564083"),
    ("neon-heights-rings", "Lethamyr's Neon Heights Rings", "Lethamyr", "Aerial control",
     "A separate rings course set above a neon city.", "2468375059"),
    ("noob-dribble", "Noob Dribble", "dmc", "Dribbling",
     "Beginner-friendly ground-control course; creator lists intermediate difficulty.", "1843822064"),
    ("coco-aim", "Aim training", "CoCo", "Shooting",
     "Target shooting with easy, customizable normal, and survival modes.", "1906378036"),
    ("hornets-nest", "Hornets Nest", "dmc", "Recoveries",
     "Obstacle arena; creator lists intermediate difficulty.", "1827631206"),
    ("fractal-funland", "Fractal's Funland", "F r a c t a l and Rocket League Mapmaking", "Recoveries",
     "Course for momentum, recoveries, and handling, with level navigation.", "3109906046"),
    ("speed-jump-boost", "Speed Jump: Boost", "dmc", "Boost management",
     "Community aerial course focused on boost and movement control.", "1421195368"),
    ("speed-jump-2", "Speed Jump 2", "dmc", "Aerial control",
     "Community obstacle course for aerial movement.", "1429288182"),
]

_COMMUNITY = [
    {
        "id": identity, "title": title, "creator": creator, "category": category,
        "description": description, "workshop_id": workshop_id,
        "url": f"https://steamcommunity.com/sharedfiles/filedetails/?id={workshop_id}",
        "license": "Creator's Workshop terms; no redistribution permission established. Link only.",
        "dependency": "Player-owned compatible local map; some maps also need creator-listed textures or plugins",
        "loading_route": "Installed Steam Workshop discovery or permitted local .udk/.upk import",
        "compatibility": "Current-game compatibility unverified; source page displays a compatibility warning.",
        "steam": "Local package discovery supported; exact map runtime unverified",
        "epic": "Launch unavailable in this app; a separately verified local loader is required",
        "status": "Creator reference checked 2026-10-23; no map files included",
        "game_tested": False, "source_checked": "2026-10-23",
    }
    for identity, title, creator, category, description, workshop_id in _MAP_REFERENCES
] + [{
    "id": "immortals-progressive-tower", "title": "The Immortals Progressive Tower",
    "creator": "Lethamyr and credited collaborators", "category": "Mixed mechanics",
    "description": "Twenty levels combining timing, shooting, aerial control, and boost usage.",
    "url": "https://lethamyr.com/maps/173", "workshop_id": None,
    "license": "Read creator terms. No permission to redistribute map or dependencies is established.",
    "dependency": "Workshop textures; Map Expansion Plugin (294) for persistent times, per creator",
    "loading_route": "Creator-provided local package; exact required loader/dependencies need verification",
    "compatibility": "Creator page verified; current-game runtime and dependency compatibility unverified",
    "steam": "Permitted local-file import supported; exact map runtime unverified",
    "epic": "Launch unavailable in this app; creator's loader instructions require separate verification",
    "status": "Creator reference checked 2026-10-23; no map files included",
    "game_tested": False, "source_checked": "2026-10-23",
}]


def community_catalog() -> list[dict]:
    """Return independent JSON-safe entries with no bundled/downloaded content."""
    return deepcopy(_COMMUNITY)


def import_map(source: str | Path, data_directory: str | Path, launcher: str) -> dict:
    """Copy a local Unreal package into private user data and identify it by SHA-256.

    This does not launch a loader, overwrite game files, inspect package scripts,
    establish creator permission, or certify gameplay/security. Steam's documented
    RLBot route is identified for a separately controlled launch operation.
    """
    if not isinstance(launcher, str) or launcher.lower() != "steam":
        raise ValueError("Local map loading is available only for the documented Steam route. Epic is unverified.")
    raw_source = os.fspath(source)
    if raw_source.startswith(("//", "\\\\")) or "\x00" in raw_source:
        raise ValueError("Choose a local map file, not a network path.")
    path = Path(source).expanduser()
    if not path.is_absolute():
        raise ValueError("Choose a map using its complete local file path.")
    if path.suffix.lower() not in {".udk", ".upk"}:
        raise ValueError("Choose a .udk or .upk map file. Archives and programs cannot be imported.")
    if path.is_symlink() or not path.is_file():
        raise ValueError("The selected map must be an existing regular file, not a shortcut or symbolic link.")
    path = path.resolve(strict=True)
    with path.open("rb") as original:
        before = os.fstat(original.fileno())
        if not stat.S_ISREG(before.st_mode) or not 4 <= before.st_size <= MAX_MAP_BYTES:
            raise ValueError("The map must be a nonempty regular file no larger than 1 GiB.")
        if original.read(4) != _PACKAGE_MAGIC:
            raise ValueError("This file does not have a recognized Unreal map package header.")
        original.seek(0)
        map_dir = Path(data_directory).expanduser().resolve() / "maps"
        if map_dir.is_symlink():
            raise ValueError("The saved map directory is a symbolic link. Choose a clean data directory.")
        map_dir.mkdir(parents=True, exist_ok=True)
        # Hash names keep user-provided text out of the eventual game console command.
        digest = hashlib.sha256()
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=map_dir, prefix=".import-", delete=False) as target:
                temporary = Path(target.name)
                copied = 0
                while block := original.read(1024 * 1024):
                    copied += len(block)
                    if copied > MAX_MAP_BYTES:
                        raise ValueError("The map grew beyond the 1 GiB import limit.")
                    digest.update(block)
                    target.write(block)
                target.flush()
                os.fsync(target.fileno())
            after = os.fstat(original.fileno())
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise ValueError("The map changed while importing. Wait for the download to finish and retry.")
            sha256 = digest.hexdigest()
            destination = map_dir / f"{sha256}{path.suffix.lower()}"
            if destination.is_symlink():
                raise ValueError("The saved map location is a symbolic link. Choose a clean data directory.")
            os.replace(temporary, destination)
            temporary = None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    return {
        "path": str(destination),
        "sha256": sha256,
        "size": copied,
        "original_name": path.name,
        "launcher": "steam",
        "route": "rlbot_steam_local_map",
        "source_url": MAP_ROUTE_SOURCE,
        "status": "Imported locally; gameplay and package content not verified",
        "game_tested": False,
        "permission": "The player must have obtained this map with its creator's permission.",
        "loading_note": "RLBot's map route may temporarily replace a built-in game map; import alone changes no game files.",
    }
