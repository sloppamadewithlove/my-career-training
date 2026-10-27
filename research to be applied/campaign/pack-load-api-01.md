# PACK-LOAD-API-01 — Custom Training load API boundary

## Scope

Static review of the frozen MCT candidate, the pinned BakkesModSDK headers, the complete installed `pluginsdk.dll` export-name inventory, and the already-reviewed stock Custom Training browser ActionScript report. No game process was launched or attached, no input or capture was performed, and no network call, compile, or test was run. Hashes identify the inspected bytes; declarations and dispatch code are not runtime acceptance evidence.

## Findings

### The stock browser API is a GFx menu dispatch surface

The game’s Custom Training browser invokes native GFx menu functions through the Scaleform wrappers. A row’s `Play(MapName, true)` forwards its row index, map name and Boolean to `GFxData_TrainingMode_TA.TrainingMode.Play` (`TrainingModeRow.as:265–271`; summarized with source hashes in [NATIVE-PACK-BROWSER-01](native-pack-browser-01.md)). The details actions similarly forward favorite and delete operations to `TrainingModeRow.AddToFavorites()` and `TrainingModeBrowser.DeleteTrainingMode(rowIndex, currentTab)`; browse, local-file and history views call the corresponding `GFxData_TrainingModeBrowser_TA.TrainingModeBrowser` wrappers (`TrainingSequenceDetailsPanel.as:495–520, 600–603`; `TrainingModeBrowser.as:25–113`).

Those ActionScript wrappers expose the UI-to-native dispatch names and arguments. They do not implement the native service, file transfer, favorite persistence, load acknowledgement, or failure/retry semantics. The stock play call is row/map based; it is not a public MCT custom-code loader.

### MCT’s candidate route is disabled in the current Lessons browser

The Lessons tab builds six featured-pack metadata rows. Each row is labeled `Unavailable offline`, has `primaryEnabled = false`, and carries only a fixed app ID in its nominal `start_training_pack` payload (`NativeCareerLayout.h:1600–1632`). The row-action handler refuses a disabled primary control before dispatch (`:655–670`). This matches the documented prior offline `FeatureDisabled` observation in [PACK-01](pack-01.md); it is not evidence that a pack loaded.

If the development host is compiled in, the Python adapter accepts only a pack ID from its fixed catalog, creates session/request UUIDs, and binds them to the current bridge nonce, process ID and process-start identity (`native_packs.py:70–112`; `packs.py:1–26`). The native observer additionally requires an owned offline process, fresh bridge, ready movie, verified build and the frontend; online, replay and existing Custom Training sessions are excluded (`NativeTrainingPackHost.h:65–80, 199–214`; `MyCareerTraining.cpp:1119–1155`). It observes that scope twice immediately before dispatch (`NativeTrainingPackHost.h:324–353`).

The only loader call in this route is a generic `CVarManagerWrapper::executeCommand` with `load_training` plus the catalog’s fixed code. The executor rejects any command that does not exactly match one of the six allowlisted codes (`NativeTrainingPackHost.h:23–35, 350–367`; `MyCareerTraining.cpp:1158–1165`). This is a command request, not an acknowledgement that the native service accepted it. The host is constructed under `MCT_ENABLE_NATIVE_MOVIE_TRIAL`, whose CMake option defaults to `OFF` (`MyCareerTraining.cpp:175–185`; `CMakeLists.txt:44–50`). `maintainTrainingPack()` ticks it and `trainingPackStatus()` exposes its status; when the native trial path is compiled in, bridge status publishes it as `native_training_pack` (`MyCareerTraining.cpp:972–1000, 1400–1410`). The compiled-out branch reports `native_movie_trial_compiled_out`. Source presence therefore does not prove that a shipped or installed MCT build enables it.

### What “loaded” proves

After dispatch, the host reports `pending` until it sees both `IsInCustomTraining()` and a nonempty current training code. It reads that code through `GetGameEventAsServer()` → `TrainingEditorWrapper::GetTrainingData()` → `GameEditorSaveDataWrapper::GetTrainingData()` → `TrainingEditorSaveDataWrapper::GetCode()` (`MyCareerTraining.cpp:1138–1150`). Only an exact normalized code match becomes `loaded` (`NativeTrainingPackHost.h:295–322`). It then rechecks the same request identity, owned-offline scope and exact current code on each tick (`:263–293`).

The receipt is attributed to pack ID, session ID, request ID, nonce, PID and process-start identity, and includes the expected code (`NativeTrainingPackHost.h:222–236`; `native_packs.py:157–185`). A mismatch, changed scope/request, missing heartbeat beyond the bounded freshness window, or timeout fails closed. The native pending timeout is 20 seconds; the Python controller allows a two-second loaded-heartbeat gap before treating the receipt as stale (`NativeTrainingPackHost.h:86, 295–322`; `native_packs.py:20–37, 140–202`). Reasons include `gates_closed`, `scope_changed`, `request_changed`, `confirmation_timeout`, `loaded_code_mismatch`, and `loaded_pack_changed` (`NativeTrainingPackHost.h:255–368`). A failure retires the request for that MCT session; Python marks the activity restart-required and does not resend it (`:334–367`; `native_packs.py:114–138`).

If this observer reaches loaded at runtime, its receipt establishes that the game reported the exact Custom Training code. This source audit did not execute that path. It does not prove that a playlist row is selected, which shot is current, how many shots are complete, the game’s History/Favorites state, or that a shot was attempted. The pack observer does not query a playlist index or progress array (`MyCareerTraining.cpp:1119–1155`; `NativeTrainingPackHost.h:263–368`).

### SDK playlist wrappers are a separate built-in-training surface

The pinned SDK declares `GfxDataTrainingWrapper::PlayTraining(type, difficulty)`, playlist selection/index methods, per-shot progress and completion/perfection queries, and `ResetTrainingProgress()` (`GfxDataTrainingWrapper.h:18–42`). These are built-in training wrapper declarations; they are not calls in the custom-pack host. The candidate’s separate built-in lesson path does call `GetGfxTrainingData()->PlayTraining(mode, difficulty)` and later reads built-in training metadata (`MyCareerTraining.cpp:377–420, 465–490`). That path is distinct from community-pack `load_training <code>`.

The SDK also declares `TrainingEditorWrapper::Load2(SaveName, PlayerController)` alongside editor operations such as `ResetBalls`, `SwitchToRoundNumber` and `RestartPlayTest` (`TrainingEditorWrapper.h:38–85`). This is not evidence of a supported frontend or offline Custom Training loader. No `TrainingModeBrowser`, `TrainingModeRow`, search, or native browser favorite/delete wrapper appears in the pinned SDK headers searched for this audit. The stock browser’s GFx actions should not be inferred to be available as a BakkesMod C++ API.

A bounded comparison against the installed `pluginsdk.dll` found the relevant decorated wrapper symbols in its complete 8,801/8,801 export table. For example, the table contains `GfxDataTrainingWrapper::PlayTraining` (ordinal 3590), `SetCurrentPlaylist` (3961), `StartAtPlaylistIndex` (5070), `GetProgressPerShot` (2331), `HasCompletedTraining` (3160), `HasPerfectedTraining` (3165), and `ResetTrainingProgress` (3693); it also contains `GameWrapper::IsInCustomTraining` (3257), `GetGameEventAsServer` (1816), the two save-data `GetTrainingData` methods (2679–2680), `TrainingEditorSaveDataWrapper::GetCode` (1568), and `CVarManagerWrapper::executeCommand` (5530). Presence establishes symbol-name compatibility only. No MCT plugin import table or runtime call was inspected, so it does not show that the candidate plugin links to or successfully invokes any of these entries.

## Integration boundary for MCT

Keep community training packs as a distinct Lessons catalog route. Preserve the existing Lessons, Workshop, Mods and Favorites tabs and their identities; an MCT favorite snapshot remains separate from the game’s own Favorites and History. Do not route a community pack through the built-in eight-rank `Power Shots` lesson selector. That separation is the intended campaign UX, not proof that an eight-rank picker or a custom-pack play flow is currently accepted by the game.

Before enabling a pack’s primary action, require a verified loader for the actual session context and a positive exact-code receipt. If the available path still depends on the native training service that failed in the recorded offline attempt, the honest state remains unavailable offline. Do not label the stock GFx call, editor `Load2`, or built-in `PlayTraining` declaration as an offline custom-code loader. Keep MCT favorites independent, and do not claim progress/completion from a `loaded` receipt.

## Evidence inventory and hashes

Hashes below are SHA-256 of the inspected candidate/report/header/artifact bytes. All path names are project-relative or sanitized; private absolute paths are omitted.

| Evidence | Bytes | SHA-256 |
|---|---:|---|
| `work/reviewed-training/plugin/include/NativeTrainingPackHost.h` | 15,077 | `baa57d4553dba6d4a184b671030527f4d11a9ee695e54653621517114d1d67f7` |
| `work/reviewed-training/plugin/src/MyCareerTraining.cpp` | 89,835 | `edc7bf5a6dc7ca0cff34ac694fb72fe71fa26dfe1fd4607d512f3b321a1a9279` |
| `work/reviewed-training/plugin/include/NativeCareerLayout.h` | 167,035 | `17d2ec0a82c79fad1949715ad62840bcace4177cbbe137da3aa675289109eb78` |
| `work/reviewed-training/plugin/CMakeLists.txt` | 13,779 | `489e7323fddf44634321a3c341dc34aa54cead9e432c71aa2bff7bb3eea148b7` |
| `work/reviewed-training/src/my_career_training/bridge.py` | 139,135 | `ac502d1f19810baca479a534aa766a6afbea7ba57a405452835cc9dcff379ac2` |
| `work/reviewed-training/src/my_career_training/training/native_packs.py` | 8,786 | `c28c9d7bfa733ad76ac7af206814bb7ab3c0c55f70517fd9c831f2c16fa55880` |
| `work/reviewed-training/src/my_career_training/training/packs.py` | 4,690 | `4597d84c05102df13c107c6722541e30d3d7b70b291f726a13b55ec651f77f8b` |
| Prior report `pack-01.md` | 11,001 | `d958e01c77b8de0733c7e58c9abad87ca93d40f11f389a83dc44751c8abac292` |
| Prior report `native-pack-browser-01.md` | 14,307 | `b63f582bdfa06620c90a5dbe11d27c334ad4dc5d46c9c773a8c41ee1c11522a1` |
| Prior report `sdk-01.md` | 5,063 | `6eccdb0709a1a6287bb4aab5471e26bf9eba8df30c3c4df299750e49a178bb90` |
| Pinned SDK `GameWrapper.h` | 9,834 | `e3fd8da7976fb9e4b2189d69c0619d1c51f59caa859ac0395a3d4fc155e10bf0` |
| Pinned SDK `CVarManagerWrapper.h` | 1,583 | `f73792714d25e9f1bf0531bf44ad94b4c9e24ac973d8b3b4ade7f77750dbda2d` |
| Pinned SDK `GameEvent/TrainingEditorWrapper.h` | 4,095 | `3d28c4e3a7e49d2d668fdcbf7f68909d110e6f6175d8bf356e638ce6234dd40a` |
| Pinned SDK `GameEvent/SaveData/GameEditorSaveDataWrapper.h` | 1,134 | `031ef3fb7f2c738566aa4ef48a87a5ea7d94c23754e2906352c59cecde10ecbe` |
| Pinned SDK `GameEvent/SaveData/TrainingEditorSaveDataWrapper.h` | 1,299 | `3e12b39fb705691f7f24180a354d6db192c8fbf4093f1023e47dc0e6665687b4` |
| Pinned SDK `gfx/GfxDataTrainingWrapper.h` | 1,674 | `e979954086b36a858bf9396da22d345261b74a1a79c4779e213f537762fca907` |
| Installed `pluginsdk.dll` (freshly rehashed) | 1,947,136 | `421df9b1ccb65cc0e316189d824f25f0d00bb05352e0ea4e5219e7f400ec8813` |
| Existing complete export evidence JSON | 2,236,169 | `cdbbdae83398d95f7861561eae0c503f9ea12206dcf13ade0fba4fc458f2da2c` |
| Pinned BakkesModSDK archive, from CMake pin | — | `e4072d2884a432bedfd7a7e8474000137b1649deeea3346de4f1b2a0cb9dd866` |

The SDK pin is commit `479e8f571cf554b25f4eeb64d611dec4133edcaf` (`CMakeLists.txt:26–29`). The installed export evidence is the pre-existing static PE export inventory; this task did not reopen a binary-analysis session or execute the DLL.


Header provenance note: GameWrapper.h is fingerprinted here with CRLF newlines. The 9,648-byte LF copy used by GHOST-VISUAL-01 differs only in line endings; conversion reproduces this report's 9,834-byte hash.
