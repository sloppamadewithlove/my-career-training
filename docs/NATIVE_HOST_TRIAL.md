# Development Windows native host trials

This development target checks whether this plugin can load, read the supported
BakkesMod menu-stack wrapper, and unload in an explicitly owned offline game.
Optional candidate graph and event tracing extend that read-only observation.
A separate `--menu-remap-trial` opt-in tests one callback parameter replacement;
it does not certify navigation changes or compatibility of an Unreal object
layout. The development target is excluded from installation and disabled in
CMake by default. The public installer hold remains in place.

The 24 October 2026 SLAVAPC trial loaded and unloaded successfully. It observed
BakkesMod **229**, game build **261013.63066.530866**, and the startup movie
**StartMenuMovie**. The game was offline and outside a match. The temporary DLL
was removed after the game closed; every inspected BakkesMod configuration file
retained its original SHA-256. The full comparison of 21,409 installation files
reported zero changed, missing, added or unreadable files. These observations do not
verify the home menu, normal online launch, or the actual My Career features.

The follow-up object-header trial matched the three bounded candidate headers
and also loaded/unloaded and removed its temporary DLL. Its BakkesMod settings
and all four inspected game configuration files were unchanged. The game itself
downloaded `RLSaveData` and exported/rotated its normal local save files, so save
bytes were **not** unchanged. The load and save export log reported success;
this is not a semantic comparison of player progression. A verified private
backup of the current seven configuration/save files was made before further
trials. `-noeac -rlbot` establishes the gameplay mode, not network isolation.

## Build and run

Build with MSVC x64 and the repository's pinned SDK:

```powershell
cmake -S plugin -B build/plugin -A x64 -DMCT_BUILD_HOST_PROBE=ON
cmake --build build/plugin --config Release --target MCTNativeHostProbe
```

Create a complete baseline with `scripts/verify_game_files.py` while Rocket
League is closed. Then use the development Python environment:

```powershell
python scripts/native_host_trial.py prepare --game-dir GAME_DIRECTORY --baseline BASELINE_JSON
python scripts/native_host_trial.py launch TRIAL_DIRECTORY
```

`prepare` creates a local plan under `build/plugin/mct-host-probes/UUID` without
changing BakkesMod. `launch` checks the executable and plan again, stages one
new UUID-named DLL, starts the installed injector if needed, and launches the
Steam-recorded executable with its supported offline flags. It never edits
`plugins.cfg` and never replaces the player's existing MyCareerTraining DLL.

The trial does not start the career backend or use its saves. Wait for BakkesMod
to initialize, then load the unique plugin using the command printed by launch.
Where the existing RCON plugin is already enabled, this helper can send the
single fixed command after checking that its localhost listener belongs to the
owned game's exact PID/start-time/executable identity:

```powershell
./scripts/native_host_command.ps1 -Directory TRIAL_DIRECTORY -Action load
./scripts/native_host_command.ps1 -Directory TRIAL_DIRECTORY -Action unload
```

The helper uses the existing configured password without printing or changing
it. It cannot send arbitrary console commands. Sending a command is not success:
verify the matching `loaded.json` and `unloaded.json` receipts. The five-minute
lease is intentionally not renewable; missing or late receipts are inconclusive.

For the button-event trial, prepare with `--menu-event-trace` (optionally also
`--menu-graph-trial`), reach the home menu first, then load the diagnostic. Its
receipt must show `RootMenuMovie` and `menu_event_trace.hooks_requested: true`.
Within 60 seconds, open Garage, return home, open Settings, and return home,
without changing settings. Unload promptly to export the bounded trace and
verify `unloaded.json`; close the game normally before the five-minute lease.
The trace does not change parameters or consume actions. Exact caller classes
are checked as candidates and callbacks must run on the same thread as load.
No queued callback remains to execute after unload. Public SDK declarations
do not prove cross-plugin hook ownership or registration success; missing
events or collisions are inconclusive, not compatibility evidence. Normal
game closure resets this diagnostic session.

## One-parameter remap experiment

The 24 October button observation is recorded in
`validation/native-button-observation-2026-10-24.json`. It matched four
`ButtonTriggered` pre/post pairs with the expected home, garage and options
menus. Both the Garage click and Settings click were observed on
`RootMenuMovie`. Their integer identifiers are process-local evidence, never
a reusable mapping. The fourth trial explicitly unloaded, removed its DLL,
left BakkesMod configuration unchanged, and its full comparison of 21,409
installation files found no changed, missing, added or unreadable files.

`--menu-remap-trial` implies event observation and the object-header check. It
is separate from the production compatibility gate, which remains closed. The
experimental calibrator learns four paired clicks in the current session:
Garage, Back, Settings, Back. Only the next matching Garage click from home
can propose the Settings identifier, once. The host verifies the current
eight-byte callback parameter and writes only an aligned private read/write
slot with the expected original value. It never changes memory protections,
code pages, game assets, or arbitrary object fields.

The exact original value is restored only on the same call's current post-hook
buffer, with matching caller, thread, parameter identity and replacement
bytes. This cleanup remains available when the observation timer or lease
expires. A missing or mismatched post callback is reported as unresolved;
no cached pointer is written later during unload. Unit fixtures test page
protection and comparison behavior in test-owned allocations, not in the game.

Both host receipts and event exports flag write attempts. A verified parameter
replacement/restoration is distinct from a verified destination change. Inspect
the final native menu stack and the user's observed screen before concluding
that navigation changed; `ButtonTriggered` may merely notify another handler.
Restoring the parameter in POST also means code after `ProcessEvent` sees its
original value. An unchanged screen therefore does not, by itself, establish
that the parameter is only a notification. The bounded PushMenu/PopMenu
observations record the following transitions to help locate later routing.
No public installer or general menu-mutation capability is enabled by this test.

Close that game normally and run:

```powershell
python scripts/native_host_trial.py finish TRIAL_DIRECTORY
python scripts/verify_game_files.py compare --game-dir GAME_DIRECTORY --baseline BASELINE_JSON --output NEW_RECEIPT_JSON
```

`finish` refuses while any game is running, removes only the UUID-named DLL if
its bytes still match, and reports configuration differences without overwriting
them. An injector started specifically for the trial should also be closed
normally; leave pre-existing injector processes alone. A failure may leave the
inert, non-autoloaded diagnostic DLL for `finish` to remove after the game closes.
The local plan includes installation paths and should not be uploaded wholesale.
