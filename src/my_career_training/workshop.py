"""Offline Workshop browser. Installed and imported packages can be browsed and favorited.

Custom map launch is unavailable: the pinned RLBot core writes the installed game's
Haunted_TrainStation_P.upk, and no no-write route exists there. This is not a native
Workshop menu. No Steam download, external program, or console command is used here.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import stat
import sys

from .content import MAX_MAP_BYTES, community_catalog
from .map_guard import CUSTOM_MAP_LAUNCH_UNAVAILABLE, digest

_MAGIC = b"\xc1\x83\x2a\x9e"
_SHA = re.compile(r"^[a-f0-9]{64}$")
TABS = ["browse", "favorites", "created", "installed"]
_MAX_FILES = 4096


def _linked(path: Path) -> bool:
    return path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction())


def _regular_package(path: Path, base: Path) -> bool:
    try:
        if path.suffix.lower() not in {".udk", ".upk"}:
            return False
        # Reject linked parents as well as linked leaf files, even links inside base.
        relative = path.relative_to(base)
        cursor = base
        if _linked(cursor):
            return False
        for part in relative.parts:
            cursor = cursor / part
            if _linked(cursor):
                return False
        if not path.resolve(strict=True).is_relative_to(base.resolve(strict=True)):
            return False
        with path.open("rb") as handle:
            info = os.fstat(handle.fileno())
            return (stat.S_ISREG(info.st_mode) and 4 <= info.st_size <= MAX_MAP_BYTES
                    and handle.read(4) == _MAGIC)
    except (OSError, ValueError):
        return False


def steam_library_roots(install_path: str = "", roots=None) -> list[Path]:
    """Resolve configured Steam libraries without requiring Steam to be online.

    Explicit roots are an injectable test/integration boundary; player commands
    must not supply them. install_path is the already configured game executable.
    """
    candidates = list(roots or [])
    if roots is None:
        if install_path:
            game = Path(install_path).expanduser()
            for parent in game.parents:
                if parent.name.lower() == "steamapps":
                    candidates.append(parent.parent)
                    break
        if sys.platform == "win32":
            candidates.append(Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)")) / "Steam")
            try:
                import winreg
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
                    candidates.append(Path(winreg.QueryValueEx(key, "SteamPath")[0]))
            except OSError:
                pass
    found = {}
    for raw in candidates:
        root = Path(raw).expanduser()
        if not root.is_absolute() or _linked(root):
            continue
        found[str(root.resolve())] = root.resolve()
    for root in list(found.values()):
        manifest = root / "steamapps/libraryfolders.vdf"
        try:
            if not _linked(manifest) and manifest.stat().st_size <= 1024 * 1024:
                text = manifest.read_text(encoding="utf-8", errors="replace")
                for value in re.findall(r'"path"\s+"([^"\r\n]+)"', text):
                    library = Path(value.replace("\\\\", "\\"))
                    if library.is_absolute() and not _linked(library):
                        found[str(library.resolve())] = library.resolve()
        except OSError:
            continue
    return list(found.values())


def discover_steam_maps(install_path: str = "", steam_roots=None) -> list[dict]:
    """Inspect downloaded app-252950 packages; presence does not prove subscription.

    We retain each package in multi-file items, allowing explicit player selection
    rather than guessing which .upk is an entry map versus a texture dependency.
    """
    entries = []
    seen = set()
    examined = 0
    for library in steam_library_roots(install_path, steam_roots):
        base = library / "steamapps/workshop/content/252950"
        if any(_linked(parent) for parent in (library / "steamapps", base.parent.parent, base.parent, base)):
            continue
        try:
            folders = sorted(base.iterdir())
        except OSError:
            continue
        for folder in folders:
            if not folder.name.isascii() or not folder.name.isdigit() or _linked(folder) or not folder.is_dir():
                continue
            for parent, directories, filenames in os.walk(folder, followlinks=False):
                parent = Path(parent)
                directories[:] = sorted(d for d in directories if not _linked(parent / d))
                if len(parent.relative_to(folder).parts) >= 6:
                    directories[:] = []
                for name in sorted(filenames):
                    examined += 1
                    if examined > _MAX_FILES:
                        return entries
                    path = parent / name
                    if not _regular_package(path, base):
                        continue
                    resolved = str(path.resolve())
                    if resolved in seen:
                        continue
                    seen.add(resolved)
                    relative = path.relative_to(folder).as_posix()
                    token = hashlib.sha256((folder.name + "/" + relative).encode()).hexdigest()[:16]
                    entries.append({
                        "id": f"steam:{folder.name}:{token}", "workshop_id": folder.name,
                        "title": path.stem, "path": resolved, "size": path.stat().st_size,
                        "original_name": name, "category": "Local maps", "creator": "See creator page",
                        "url": f"https://steamcommunity.com/sharedfiles/filedetails/?id={folder.name}",
                        "source_url": f"https://steamcommunity.com/sharedfiles/filedetails/?id={folder.name}",
                        "origin": "steam_workshop", "installed": True, "game_tested": False,
                        "provenance": "Package found in this Steam library's Rocket League Workshop directory",
                        "compatibility": "Package header recognized; entry-map role, dependencies and gameplay unverified",
                        "status": "Installed locally · needs game verification",
                    })
    return entries


def _imported(data_directory, imported_maps) -> list[dict]:
    base = Path(data_directory).expanduser().resolve() / "maps"
    entries = []
    seen = set()
    for record in imported_maps or []:
        if not isinstance(record, dict):
            continue
        digest = record.get("sha256", "")
        raw_path = record.get("path", "")
        if not isinstance(raw_path, str):
            continue
        path = Path(raw_path)
        if not isinstance(digest, str) or not _SHA.fullmatch(digest):
            continue
        if path.name != digest + path.suffix.lower() or path.parent != base:
            continue
        if not _regular_package(path, base) or digest in seen:
            continue
        seen.add(digest)
        entries.append({**record, "id": f"imported:{digest}", "title": record.get("original_name", path.stem),
                        "origin": "local_import", "category": "Local maps", "creator": "Your local import",
                        "installed": True, "game_tested": False, "status": "Imported · needs game verification"})
    return entries


def library_state(data_directory, launcher="steam", install_path="", favorites=(), imported_maps=(),
                  steam_roots=None, tab="browse", query="", category="all") -> dict:
    """Build JSON-safe browser state. Cache between refreshes; don't scan every tick."""
    if tab not in TABS:
        raise ValueError("Choose Browse, Favorites, Created / imported, or Installed.")
    installed = discover_steam_maps(install_path, steam_roots) if launcher == "steam" else []
    known = community_catalog()
    references = {entry.get("workshop_id"): entry for entry in known if entry.get("workshop_id")}
    for item in installed:
        reference = references.get(item["workshop_id"])
        if reference:
            for key in ("title", "creator", "category", "description", "dependency", "license", "source_checked"):
                item[key] = reference[key]
            item["catalog_id"] = reference["id"]
            item["title"] += f" · {item['original_name']}"
    by_workshop = {}
    for item in installed:
        by_workshop.setdefault(item["workshop_id"], []).append(item)
    rows = []
    for item in known:
        packages = by_workshop.get(item.get("workshop_id"), [])
        # A single package has an unambiguous selection. Multiple packages need the
        # player to select the exact installed file rather than auto-loading textures.
        item.update(origin="catalog", installed=bool(packages), package_ids=[p["id"] for p in packages])
        if len(packages) == 1:
            item["launch_id"] = packages[0]["id"]
        rows.append(item)
    rows.extend(installed)
    rows.extend(_imported(data_directory, imported_maps))
    favorite_ids = set(favorites or [])
    for item in rows:
        item["favorite"] = item["id"] in favorite_ids
        launch_id = item.get("launch_id", item["id"] if item["installed"] else None)
        # A single installed package used to be selectable for RLBot. That route writes
        # the Steam game files on the pinned core, so launch stays closed.
        selectable = bool(launcher == "steam" and launch_id and (
            item["origin"] != "catalog" or item.get("launch_id")))
        item["can_launch"] = False
        if launcher == "epic":
            item["availability"] = "Epic loader unavailable"
            item["launch_reason"] = item["availability"]
        elif selectable:
            item["availability"] = CUSTOM_MAP_LAUNCH_UNAVAILABLE
            item["launch_reason"] = CUSTOM_MAP_LAUNCH_UNAVAILABLE
        elif item["origin"] == "catalog" and item["installed"] and launcher == "steam":
            item["availability"] = "Choose an installed package"
            item["launch_reason"] = CUSTOM_MAP_LAUNCH_UNAVAILABLE
        else:
            item["availability"] = "Not installed"
            item["launch_reason"] = item["availability"]
        item["launch_id"] = launch_id
    categories = sorted({row["category"] for row in rows})
    counts = {"browse": len(rows), "favorites": sum(row["favorite"] for row in rows),
              "created": sum(row["origin"] == "local_import" for row in rows),
              "installed": sum(row["installed"] for row in rows)}
    filtered = rows
    if tab == "favorites":
        filtered = [row for row in filtered if row["favorite"]]
    elif tab == "created":
        filtered = [row for row in filtered if row["origin"] == "local_import"]
    elif tab == "installed":
        filtered = [row for row in filtered if row["installed"]]
    if category != "all":
        filtered = [row for row in filtered if row["category"] == category]
    search = str(query).strip().casefold()[:200]
    if search:
        filtered = [row for row in filtered if search in " ".join(str(row.get(key, "")) for key in
                    ("title", "creator", "category", "description", "workshop_id")).casefold()]
    return {"items": filtered, "categories": categories, "tabs": TABS[:], "counts": counts,
            "tab": tab, "query": search, "category": category, "launcher": launcher,
            "created_label": "Created / imported", "offline": True,
            "launch": {"available": False, "reason": CUSTOM_MAP_LAUNCH_UNAVAILABLE},
            "note": "Browse installed maps and save favorites. Custom map launch is paused while a loader "
                    "that preserves your Steam game is being developed."}


def toggle_favorite(favorites, identity: str, items) -> list[str]:
    if not isinstance(identity, str) or identity not in {item["id"] for item in items}:
        raise ValueError("Choose a map in the current library.")
    result = list(dict.fromkeys(favorites or []))
    if identity in result:
        result.remove(identity)
    else:
        result.append(identity)
    return result


def prepare_launch(identity: str, data_directory, launcher="steam", install_path="", imported_maps=(),
                   steam_roots=None) -> dict:
    """Reject a launch before copying a package into a game slot.

    Discovery and favorites stay available through library_state. This function
    does not import over the Steam game files and does not return a launch payload.
    """
    if launcher != "steam":
        raise ValueError("Epic map launch is unavailable until its local loader is verified.")
    state = library_state(data_directory, launcher, install_path, imported_maps=imported_maps,
                          steam_roots=steam_roots)
    rows = {row["id"]: row for row in state["items"]}
    item = rows.get(identity)
    if item and item.get("launch_id") and item["launch_id"] != item["id"]:
        item = rows.get(item["launch_id"])
    if not item or not item.get("path"):
        raise ValueError("Install this map or choose its exact installed package before playing.")
    if item.get("origin") == "local_import":
        try:
            actual = digest(item["path"])
        except OSError:
            actual = ""
        if actual != item.get("sha256"):
            raise ValueError("Imported map bytes changed. Import the original package again before playing.")
    raise ValueError(CUSTOM_MAP_LAUNCH_UNAVAILABLE)
