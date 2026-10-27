# COMPAT-01 — Current Rocket League/BakkesMod compatibility

**Date:** 2026-10-27
**Scope:** Read-only source, documentation, and installed-file metadata research. No process inspection/attach, game launch/input, EAC setting change, or test was performed.

## Resolution

Do not describe BakkesMod as categorically unavailable on this machine. EAC-on online play and EAC-off offline mod use are separate cases. Official Rocket League policy says community mods do not run with EAC enabled and describes compliant mods in training/offline/LAN/replay contexts when EAC is off. The BakkesMod maintainer’s dated post says BakkesMod would not work on Rocket League versions released April 28, 2026 or later. The project also has real offline gameplay evidence from October 27. The evidence does not connect that run to a recorded Rocket League runtime build ID, BakkesMod runtime version, or EAC launch state. As a result, the maintainer’s support statement conflicts with observed project gameplay, and the exact installed-runtime tuple remains unresolved. It does not establish that the garage’s cosmetic cvars visibly apply.

## Mode and evidence matrix

| Context | Supported statement | Evidence and limit |
|---|---|---|
| EAC enabled, online PC play | Community mods do not run; EAC is required for online PC play. The project must not claim a BakkesMod feature or online cosmetic visibility in this mode. | Rocket League’s [Apr 28, 2026 EAC article](https://www.rocketleague.com/news/easy-anti-cheat-comes-to-rocket-league-on-pc-today?lang=en) and [Code of Conduct](https://www.rocketleague.com/code-of-conduct). This is official mode policy, not proof about the installed files. |
| EAC disabled, training/offline/LAN/replay | Rocket League says compliant third-party mods may run in these contexts. This is policy permission, not a BakkesMod compatibility guarantee. | Same official sources above. The Code of Conduct leaves the user’s EAC setting in the user’s control. |
| BakkesMod on post-Apr-28 game releases | Maintainer Bakkes’s Apr 28 post says BakkesMod “will not work” on versions released that day or later and says active updates are stopping. | [Bakkes’ Blog, “BakkesMod post-eac update,” Apr 28, 2026](https://bakk.es/articles/bakkesmod-eac.html), lines 4–10 on the public page. This is a primary maintainer compatibility/support statement. It is not a diagnostic of this installation. |
| Current local Steam installation | Disk metadata strongly suggests a post-EAC build; it does not alone identify the game runtime used by the recorded test. | Read-only local metadata: AppID `252950`, Steam `buildid` `25914621`, manifest last-updated `2026-10-21 01:15:11 UTC`; `RocketLeague.exe` product version `1.0.10897.0`, SHA-256 `56b499a85ad927c6b5cc47cb4813f956dd9263405fdf4eddc65b669b53185bc7`. Official Rocket League v2.78 is dated Oct 20 ([patch notes](https://www.rocketleague.com/news/rocket-league-s24-patch-notes-v278)); SteamDB associates build ID 25914621 with an Oct 20 update ([depot history](https://steamdb.info/app/252950/depots/)). The build-ID mapping is secondary evidence; no Psyonix mapping from this local ID to `GetPsyBuildID()` was obtained. |
| BakkesMod installation | The files are present; presence is not successful injection, and the numeric version files do not identify an exact compatible host build by themselves. | Read-only local metadata: BakkesMod `version.txt=229`, `injectorversion.txt=32`; `MyCareerTraining.dll` has no PE file-version resource, last-write `2026-10-27 06:41:59 UTC`, SHA-256 prefix `18569d2b321f30f2…`. No BakkesMod log was read. |
| Project offline gameplay | The project records a successful offline game session where the authored menu/plugin path loaded and the lesson launch reached shot 1. Preserve that as actual evidence; do not erase it based on a general support statement. | `docs/PROJECT_STATUS.md:85-115`, updated Oct 27. It does not record `GetPsyBuildID()`, `GetBakkesModVersion()`, EAC launch mode, or the loaded DLL hash, so it cannot yet prove this was the same tuple as the current Steam manifest and installed plugin file. |

**Binary cross-check:** `src/my_career_training/native_launch.py:43-45` pins the expected RocketLeague.exe SHA-256 and size. Both match the read-only installed executable metadata above. This proves that the current installed executable bytes match the app’s pinned executable bytes; it does not identify the rest of the install’s build or the EAC mode of the gameplay session.

## Host architecture and current checks

- `plugin/src/MyCareerTraining.cpp:27-28` declares an ordinary BakkesMod plugin (`BAKKESMOD_PLUGIN`, version `0.3.0`); it is loaded by the BakkesMod host. The project plugin does not implement a BakkesMod injector or an EAC switch.
- A separate `MctNativeLauncher` path exists for the owned offline file-view feature. Its docs say it uses Detours to create a suspended, pinned `RocketLeague.exe` with `MctNativeFileView64.dll`, then resumes only that owned process; it does not use an `OpenProcess` injection path and does not launch online (`native_launcher/docs/NATIVE_LAUNCHER.md:48-62,114`). The document labels it `production_ready: false` and says it is not game-verified (`:1,98`). This is separate from BakkesMod plugin loading; source inspection does not establish EAC compatibility.
- `plugin/CMakeLists.txt:26-47` fetches BakkesModSDK commit `479e8f571cf554b25f4eeb64d611dec4133edcaf` with a pinned archive hash, links its `pluginsdk.lib`, and builds the DLL. This is a compile-time dependency, not a version identity for the installed BakkesMod host or proof of compatibility with the full current game build. The source status reports SDK API 95.
- `plugin/src/MyCareerTraining.cpp:579-587` gates the owned session on fresh bridge state, executable identity, offline status, and Steam build. The gate does not detect EAC mode. `docs/ARCHITECTURE.md:101-118` says the shipped code targets EAC-off offline use and leaves the user’s EAC settings unchanged.
- The offline launch helper declares RLBot-specific game arguments (`src/my_career_training/native_launch.py:56-61`); no EAC preference change or EAC-state verification was found in the reviewed launch/plugin path.
- At runtime the plugin reads `GetPsyBuildID()` and `GetBakkesModVersion()` and publishes `game_build`, `bakkesmod_version`, and `sdk_api` (`MyCareerTraining.cpp:1266-1285,1359-1375`). No value tuple from the Oct 27 game test is saved in the reviewed project status.
- For cosmetics, `itemModAvailable` means only that both `cl_itemmod_enabled` and `cl_itemmod_code` cvars are present (`MyCareerTraining.cpp:1343-1345`). It is not a compatibility probe, write/readback result, or appearance confirmation.

## Checks needed before another adapter claims compatibility

Record a sanitized, read-only compatibility tuple for each real offline session:

1. Game path identity from the owned process: Steam AppID/build ID, `RocketLeague.exe` file version and SHA-256, and BakkesMod `GetPsyBuildID()` value.
2. Host identity: `GetBakkesModVersion()`, injector/runtime version if separately available, plugin API version, MyCareerTraining DLL hash/version, source revision, and SDK commit pin.
3. Launch mode: record the user-selected EAC state or an authoritative runtime signal. If no signal is available, store `unknown`; do not infer EAC-off from `IsInOnlineGame()==false`.
4. Adapter state as distinct fields: cvars found, write accepted/read back, and scene appearance independently verified. A present cvar is not sufficient.
5. Preserve the project’s existing offline ownership guard and fail closed when the game is online, the bridge is stale, the executable/build identity is unexpected, or host compatibility is unknown.

Use the recorded tuple to qualify each adapter separately: lesson spawning, native-menu capture, cosmetics, and ghost rendering do not inherit support from one successful plugin load. Keep online play under EAC and third-party offline operation as distinct rows in future acceptance evidence.

## Source references

- Official Rocket League: [EAC launch article](https://www.rocketleague.com/news/easy-anti-cheat-comes-to-rocket-league-on-pc-today?lang=en); [Third-Party Mods policy](https://www.rocketleague.com/code-of-conduct); [v2.78 patch notes](https://www.rocketleague.com/news/rocket-league-s24-patch-notes-v278).
- Primary maintainer source: [Bakkes’ post-EAC update](https://bakk.es/articles/bakkesmod-eac.html), dated `2026-04-28`.
- Secondary build-ID cross-check: [SteamDB Rocket League depots](https://steamdb.info/app/252950/depots/).
- Local source evidence: `plugin/CMakeLists.txt:26-47`; `plugin/src/MyCareerTraining.cpp:27-28,579-587,1266-1285,1343-1375`; `src/my_career_training/native_launch.py:43-61`; `docs/ARCHITECTURE.md:101-118`; `docs/PROJECT_STATUS.md:61-64,85-115`.
