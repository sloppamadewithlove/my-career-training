# Offline community map library

The in-game Workshop browser uses a bundled list of creator references and packages already present on the player's computer. It performs no online search, subscription, download, or authentication. Nothing from a map creator is redistributed in the installer.

Browse, Favorites, Created / imported, and Installed are separate tabs. Search covers title, creator, category, description and Workshop ID. Favorites are per-user save data. Created / imported means packages the player imported; it does not claim that the player authored a downloaded map. Category filters cover aerial control, dribbling, shooting, recoveries, boost management, mixed mechanics, and unknown local maps.

## Python integration

`workshop.library_state(data_directory, launcher="steam", install_path="", favorites=(), imported_maps=(), steam_roots=None, tab="browse", query="", category="all")` returns JSON-safe `{items,categories,tabs,counts,tab,query,category,launcher,created_label,offline,note}`. Rows contain `id,title,creator,category,origin,installed,favorite,can_launch,launch_id,availability,game_tested`, plus source/dependency information where known. `origin` is `catalog`, `steam_workshop`, or `local_import`. `steam_roots` is a trusted integration/test injection, never a player command payload.

Cache this result outside the 100ms state publisher; refresh when the player opens or refreshes Workshop, imports a map, or changes the launcher/install path. Discovery inspects package headers and a bounded number of directory entries. It is unsuitable for every frame.

`toggle_favorite(favorites, identity, items)` returns a new ID list; persist it in the user's document and republish state. Unknown IDs are rejected.

`prepare_launch(identity, data_directory, launcher="steam", install_path="", imported_maps=(), steam_roots=None)` now rejects custom-map startup. It does not return a launch payload or copy a map. All `can_launch` values are false, and the library exposes the unavailable reason. This applies to Steam as well as Epic. Browsing, importing into private AppData and favorites remain available.

A curated row identifies its installed package only if exactly one package was found. Multi-package items expose their exact package IDs: some `.upk` files are texture dependencies rather than entry maps. A recognized Unreal header is not proof of package safety, role, or compatibility.

## Steam discovery

`steam_library_roots` uses the configured installed game path, Windows Steam registry/default location, and local `steamapps/libraryfolders.vdf`. `discover_steam_maps` scans `steamapps/workshop/content/252950/<numeric-workshop-id>/` for bounded-depth `.udk` / `.upk` packages with recognized Unreal headers. Linked directories, junctions, linked files, packages outside the app's directory, and non-package files are excluded.

The provenance describes a downloaded package in the local Steam Workshop directory. Directory presence does **not** prove an active subscription, legal permission, compatibility, dependencies installed, or security review. The catalog joins exact Workshop IDs to attributed creator metadata; unknown downloaded items remain usable local candidates with their source page and package filename visible.

## Launch and restoration contract

The pinned RLBot core `v5.0.0-rc18` accepts a custom file through `game_map_upk`, but its [CustomMap implementation](https://github.com/RLBot/core/blob/v5.0.0-rc18/RLBotCS/ManagerTools/CustomMap.cs) replaces the installed `Haunted_TrainStation_P.upk`. Passing an absolute path does not avoid that write. Therefore this integration refuses custom-map requests before creating a worker session or sending a match configuration. Built-in career and training arenas remain available. A future custom-map loader must demonstrate a route that does not modify the Steam installation.

`MapGuard.prepare` is retired and cannot begin another substitution. Recovery exists only for a journal created by an older version. It must preserve the backup on conflict, restore only exact recorded bytes, and refuse to replace a file while any Rocket League process is running. Restoring a legacy file is still a write to the Steam installation; it is not a new map-loading mechanism. No alternative BakkesMod console-map-open route has been verified.

Map-specific textures or plugins remain creator dependencies. Do not execute a map directory's scripts or automatically install those dependencies. Exact current Rocket League loading, map controls, return-to-hub, texture availability and recovery require Steam Windows game tests.

## Epic

Imported private maps can be displayed in an Epic user's library, but `can_launch` is false and `prepare_launch` rejects Epic. A creator-permitted local download is a possible source for a future independently verified loader. A Steam page is not evidence of an Epic entitlement or permission to redistribute a map. No account bypass, Workshop downloader, or Epic loader is provided by this module.

## Creator references checked 23 October 2026

The following exact creator publication pages were read. These entries are discovery metadata, not current-game playtest results. Steam page renderings displayed compatibility/removal notices alongside creator descriptions; the catalog preserves an unverified compatibility state rather than treating those pages as a current compatibility certificate.

| Map | Creator | Category | Primary publication |
| --- | --- | --- | --- |
| Dribble 2 Overhaul | 0xDigby, Martinn | Dribbling | [Workshop 1694288506](https://steamcommunity.com/sharedfiles/filedetails/?id=1694288506) |
| Speed Jump: Rings 3 | dmc | Aerial control | [Workshop 1671658424](https://steamcommunity.com/sharedfiles/filedetails/?id=1671658424) |
| Giant Rings | Lethamyr | Aerial control | [Workshop 2025564083](https://steamcommunity.com/sharedfiles/filedetails/?id=2025564083) |
| Neon Heights Rings | Lethamyr | Aerial control | [Workshop 2468375059](https://steamcommunity.com/sharedfiles/filedetails/?id=2468375059) |
| Noob Dribble | dmc | Dribbling | [Workshop 1843822064](https://steamcommunity.com/sharedfiles/filedetails/?id=1843822064) |
| Aim training | CoCo | Shooting | [Workshop 1906378036](https://steamcommunity.com/sharedfiles/filedetails/?id=1906378036) |
| Hornets Nest | dmc | Recoveries | [Workshop 1827631206](https://steamcommunity.com/sharedfiles/filedetails/?id=1827631206) |
| Fractal's Funland | F r a c t a l, Rocket League Mapmaking | Recoveries | [Workshop 3109906046](https://steamcommunity.com/sharedfiles/filedetails/?id=3109906046) |
| Speed Jump: Boost | dmc | Boost management | [Workshop 1421195368](https://steamcommunity.com/sharedfiles/filedetails/?id=1421195368) |
| Speed Jump 2 | dmc | Aerial control | [Workshop 1429288182](https://steamcommunity.com/sharedfiles/filedetails/?id=1429288182) |
| The Immortals Progressive Tower | Lethamyr and credited collaborators | Mixed mechanics | [Creator map 173](https://lethamyr.com/maps/173) |

The Progressive Tower creator lists Workshop textures and Map Expansion Plugin 294 for saved times. Giant Rings mentions Workshop textures. These requirements are shown as dependencies, not silently installed. Neither these 11 references nor every discovered package has been game-tested by this module.

## Design refinement

Optional Opus 5.5 handoff after functional verification: refine the original vertical map list, selected-map detail panel, favorites mark, controller focus and category spacing to fit the My Career blue/orange sports style. Keep unavailable reasons, creator credit, exact package selection and accessibility intact. Do not copy proprietary Rocket League menu assets into the repository.
