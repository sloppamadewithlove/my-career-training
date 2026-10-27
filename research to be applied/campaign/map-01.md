# MAP-01 — local Workshop map lifecycle

**Scope:** read-only source, installed package metadata, and static artifact research. No game was launched or controlled; no Workshop content was downloaded, installed, copied, or extracted.

## Findings

There are two separate map paths. The Python Workshop browser/import path is intentionally browse-only: `library_state` reports `can_launch=false`, `prepare_launch` always refuses a custom-map launch, and retired `MapGuard.prepare` refuses before writing the old RLBot map slot (`src/my_career_training/workshop.py:1-5, 258-282`; `map_guard.py:82-95`). The native authored Workshop menu has a separate development handoff for one already-installed Steam Workshop `.upk` or `.udk` file. Local imports and Epic maps do not enter that handoff (`NativeCareerLayout.h:697-754`; `NativeCareerLayout.h:2067-2080`).

### Package identity and selection

- Python discovery scans the configured Steam library's `steamapps/workshop/content/252950`, rejects linked paths, follows at most six nested directories, examines at most 4,096 files, and keeps regular `.upk`/`.udk` files with the four-byte Unreal package magic. It creates one row per package, with an identity derived from the numeric Workshop folder plus relative filename; the full resolved filepath is separate metadata. Folder presence is not proof of subscription or compatibility (`workshop.py:94-143`).
- Known catalog rows join to installed packages by exact numeric Workshop ID. One installed file can be aliased automatically; multiple files require an exact package choice. The catalog cannot infer which file is the entry map versus a dependency (`workshop.py:171-199`).
- The native menu derives the Workshop root from the verified game's Steam library, accepts only `steam_workshop` rows, validates the numeric parent folder against `workshop_id`, and canonicalizes the path. A catalog alias is bound only when its `launch_id` matches exactly one package row. The clicked movie control is revalidated against the current package path, item ID, nonce, and generation; a stale choice is refused (`NativeWorkshopContext.h:14-19, 67-120`; `NativeCareerLayout.h:697-754, 544-564, 671-680`).
- Local imports can be listed and favorited but are not bound for native Play. A catalog item with multiple package files has no unique alias until a player selects a specific installed file. That choice still does not identify its role or verify sibling dependencies (`NativeCareerLayout.h:737-752, 2071-2078`; `native_career_layout_tests.cpp:847-879`).

### Prepare, pin, and command dispatch

1. The menu effect is host-local, not the Python `play_workshop` bridge action. The native host requests preparation and reports `workshop_preparing` (`NativeMovieHost.cpp:631-638`).
2. Preparation requires an owned, fresh, offline Steam frontend, no current game/replay/busy activity, matching executable hash, BakkesMod version and game build, valid bridge nonce/generation, and item-ID/path agreement (`WorkshopLoadPlan.h:32-95, 320-372`).
3. The package is read and fully SHA-256 hashed, within 4 bytes–1 GiB, with the expected Unreal magic; paths are bounded, under Workshop app `252950`, and limited to seven components below the item directory. This validates a package header and identity, not full Unreal structure, gameplay, or dependencies (`WorkshopLoadPlan.h:63-78, 342-373, 620-648, 757-790`).
4. A worker rechecks and pins that one package and its ancestor directories against writes/replacement, then repeats package identity validation. The game-thread poll rechecks authority and the held file before dispatch (`NativeWorkshopLauncher.h:426-497, 504-559, 611-685`). The generated command is exactly `load_workshop "<canonical package path>"`; the host validates framing/path and calls `CVarManagerWrapper::executeCommand` (`WorkshopLoadPlan.h:774-789`; `NativeWorkshopDispatch.h:8-27`; `MyCareerTraining.cpp:897-924`).
5. `callbackReturned` means only that the execute callback returned. It is explicitly not map-load evidence. The launcher retains dispatched pins until `release`/DLL shutdown, up to 32 groups; a thrown/unknown callback outcome stays pinned and blocks another request (`NativeWorkshopLauncher.h:3-14, 30-55, 247-257, 390-405`).

### Map arrival, Pause, Return, and cleanup

The launcher has no request-bound map-arrival condition and no expected-map identity field. It does not observe a result from `executeCommand`. The bridge's `native_external_activity` is created when the owned offline session is in-game, the backend is idle, and there is no app request/worker/pack/continuation; it binds only the current bridge nonce, not the requested Workshop ID, filepath, or current map name (`bridge.py:299-309`). Thus a generic already-loaded offline arena can satisfy that activity condition even if a newly dispatched map command did nothing. This is the exact unproven condition.

Pause eligibility is separately observed from the game: offline in-game server state plus paused `MidGameMenuMovie`. `NativeMatchLayout` enables Return for a valid active activity or for the idle external-activity binding. The external Return payload uses the bridge nonce, empty fixture ID, and `abandon=false` (`NativeMovieHost.cpp:225-271`; `NativeMatchLayout.h:41-43, 94-128, 687-702`). The bridge accepts that exact external Return, publishes a durable `native_return_ready` receipt, and preserves career state. The native gate only completes Return after the activity has left the game and the current authored frontend has reached `RootMenuMovie` (`bridge.py:1102-1132`; `NativeReturnGate.h:84-135, 247-279`).

No Steam game-file replacement or map rollback is part of this native route. The old `map-recovery` path is for journals from retired builds; it refuses recovery while Rocket League is running and does not prepare new maps (`map_guard.py:87-116`). Dispatched package pins remain until plugin unload rather than being released on Return.

The project status records one copied-profile game session that loaded **Dribble 2 Overhaul**, opened the authored pause menu, and returned to the visible hub with fresh RootMenuMovie/return-arrived signals; it also says other-map coverage is untested (`docs/PROJECT_STATUS.md:113-121`). Earlier, an owned stock-opened map had Return disabled; the subsequent repair is recorded as verified on Dribble 2 Overhaul (`docs/PROJECT_STATUS.md:133-138`). This is useful single-map manual evidence, but source flags remain `gameTested=false`; the report does not tie that session to an exact dispatched package hash or a per-request map-arrival signal.

## Add-on command evidence

- Public [`CustomMapsPlugin.cpp`](https://raw.githubusercontent.com/Capstoner1/CustomMapsPlugin/main/CustomMapsPlugin.cpp) registers `custommaps_open` (lines 6-14). Its local installed list uses each file's stem as the display name and keeps the full filepath separately (379-392). `LaunchMap` queues the path, and the UI schedules `load_workshop "<path>"` after 0.5 seconds through `SetTimeout`/`executeCommand` (374-377, 685-692). These lines show a caller and dispatch timing, not command registration or loader behavior. Its downloader/extractor also copies files into a `mods` folder; that installation path is distinct from My Career's already-installed Steam package route (255-360).
- Read-only REA inspected installed `WorkshopPlugin.dll` (PE x64, 314,368 bytes, SHA-256 `76ab50107a7d4d6753e6da1ef4bf61b6c695e3b63d7272ef2a38ae28723526da`, Ghidra 12.1.4). Defined-string evidence includes the deprecated training-shot/playlist commands `workshop_shot_load`, `workshop_playlist_load`, and `workshop_playlist_next`. `search_strings("load_workshop")` returned no defined-string match in this DLL; Ghidra's defined-string inventory is not every byte sequence, so that is not proof of absence (Evidence `ev_a77aae72ce472bd5688cce49be3cc98ae46b39a86712f7b4789c50aa10ada618`, `ev_13f5bf04f510ed6a01400054ca876c3a3750cc701b3ae42cd86cf9801aa8a724`). This is the stock training Workshop plugin, not the custom-map add-on.
- Installed BakkesMod core identity was PE x64, 4,638,208 bytes, SHA-256 `1b3226b447606f5552396907e34655de099202f371441bd4ce09bb6c74f20e3e`. A Ghidra `search_strings` query for `load_workshop` did not yield an inspectable result before the exec cell completed without output. The binary session was closed; no conclusion about core command registration is made. Even confirmed registration would not prove successful dispatch, map arrival, or no file mutation.

## Installed Steam Workshop inventory

A bounded read-only scan of the installed Rocket League app-252950 Workshop tree found 7 numeric item directories and 9 `.udk`/`.upk` candidates (7 `.udk`, 2 `.upk`), with candidates in at most 6 directories and 3 package-bearing directories containing multiple files (the aggregate output did not preserve per-directory counts, so the exact empty-directory count is unknown). All 9 candidates had the expected Unreal package magic. The Steam Workshop manifest existed. Counts and headers establish local files only; they do not establish subscription, entry-map role, dependencies, runtime compatibility, or that any map was launched. No package content or item IDs are included here.

## Existing coverage and gaps

- `tests/test_workshop.py:120-160`: exact selection for a multi-package item, explicit launch refusal, imported-path/hash checks, and Epic gating.
- `plugin/tests/native_career_layout_tests.cpp:805-909`: row bounds/pagination, exact catalog alias, ambiguous/missing/foreign/imported rows, stale package path, and busy/preparing/blocked scope.
- `plugin/tests/native_workshop_launcher_tests.cpp:300-330, 472-523` and `native_workshop_dispatch_tests.cpp:6-26`: synthetic scope/package, pinning, exact generated command, and dispatcher allowlist. The callback records text; it does not run BakkesMod or load a map.
- `tests/test_ingame_lifecycle.py:240-309` and `plugin/tests/native_match_movie_tests.cpp:515-548`: generic idle external-activity Return binding, state preservation, and stale/busy rejection. These tests do not bind Return to a selected map identity. No current test observes a Workshop map name after dispatch or detects missing/sibling assets.

## Six-part game acceptance

1. **Precondition:** owned offline Steam frontend, fresh verified build/session, idle bridge, no active worker/pack/continuation; select an exact installed package row.
2. **Input:** select Play for that row once; preserve its Workshop ID, relative filename, canonical path, size, and SHA-256 in the test record.
3. **Visible/state result:** observe the prepared status, then independently establish that the requested package—not merely a generic offline arena—became the current map and that the authored pause surface opens.
4. **Durable state:** verify career/pending-fixture files and selected package bytes remain unchanged; verify the external activity uses only the current owned bridge nonce.
5. **Pause/Return:** issue Return once, observe durable receipt, game exit, and fresh authored RootMenuMovie arrival; confirm career state is unchanged and the held package pin lifecycle is understood.
6. **Failure/recovery evidence:** separately exercise missing package, stale/changed package, ambiguous multi-file item, and absent dependency; each must show an explicit refusal or identified map-load failure, never count generic in-game state as success. Confirm normal plugin unload releases pins.

## Minimum future probe

Use one owner-approved isolated copied profile and one already-installed, known-good Steam Workshop item. Read and record the exact item/package path, package hash, install-file baseline, and bridge nonce before action. Observe only the existing native launcher status, BakkesMod command outcome if available, `IsInGame`/server/menu state, and a trustworthy map/level identity signal correlated with the expected package. Then test Pause → Return → RootMenuMovie arrival and compare the same file/state baseline. Do not accept `callbackReturned`, generic `native_external_activity`, or `IsInGame` alone as map-arrival proof. Add a second multi-package item only after its entry package/dependency expectations are known.
