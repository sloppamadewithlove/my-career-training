# Read-only Windows host trial

This development target checks whether this plugin can load, read the supported
BakkesMod menu-stack wrapper, and unload in an explicitly owned offline game.
It does not replace any menu, consume any native action, or certify compatibility
of an Unreal object layout. It is excluded from installation and disabled in
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
