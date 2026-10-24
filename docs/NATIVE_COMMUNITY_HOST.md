# Native community host

This is a compile-gated developer trial for one staged Speedflip Trainer file. It is not a general plugin executor. `MCT_ENABLE_NATIVE_MOVIE_TRIAL` must be on or the host is not constructed, does not hash, and does not call `plugin load`. The normal build publishes `native_community_status.status = idle` with reason `trial_compiled_out`.

`game_verified` and `production_allowed` stay false. The source tree at commit `8a4a94fc120db4919c3155052dbd7099ef834ba7` has not been shown to be the same bytes as the staged DLL. A loaded acknowledgement means the PluginManager listed the generated filename and the three trainer cvars read back as zero. It does not mean the DLL is safe, current, or allowed online.

## Request

Python `NativeCommunityController.request()` publishes exactly these 10 keys under `native_community_request`. The host rejects any other size or key. A note that said "11 keys" does not match that controller; an eleventh key would be refused.

| Key | Required value |
| --- | --- |
| `site_id` | `286` |
| `nonce` | lowercase UUID, `8-4-4-4-12` |
| `stem` | `MCTCommunity_286_` plus the nonce with hyphens removed |
| `archive_sha256` | `b75ff28a86e4d54b0083b4ea09068a93b409bc18746b150b70030cab1d4f795d` |
| `member_sha256` | `2203874a6921df54d06c1042a4281c7694d3e415b9c6b0618e33769db401ef11` |
| `pid` | integer, equal to this process |
| `start_identity` | three decimal places, within 0.001 of the owned process start |
| `game_exe_sha256` | `56b499a85ad927c6b5cc47cb4813f956dd9263405fdf4eddc65b669b53185bc7` |
| `core_identity` | `Bakkes229` |
| `build_identity` | `261013.63066.530866` |

The profile constants are compiled in. A request cannot change the 691200-byte size or either hash. The host builds the path itself: trusted plugins directory plus `stem.dll`. No path, URL, or command is read from the request or from movie JSON.

## When a load may run

`tick` reads the pending request only from the bridge state on the game thread. The observation must be an owned offline frontend (`!IsInGame && !IsInReplay && !IsInOnlineGame`), a fresh bridge, a ready native movie, and a verified build. The live `bridge_session` must be a canonical UUID and equal both `observation.nonce` and `request.nonce`. `verifiedBuild` fills core `229`; only that exact string is treated as `Bakkes229`. The plugins directory comes from `GameWrapper::GetBakkesModPath()` / `plugins`, or from the parent of `GetDataFolder()` / `plugins` when the first path is empty. The host does not search the disk.

`loadedPluginsKnown` is true only after `GetPluginManager()` and `GetLoadedPlugins()` both succeed. A null manager, a null list, or an exception is unknown, not an empty plugin list, and blocks the load and any acknowledgement. The same frontend, nonce, and plugin-list facts are read again immediately before `plugin load`. A nonce change or a lost frontend at that point releases the file pin and does not dispatch.

The file is opened with a read-only share that denies writers and deleters. Ancestors must be real directories, the final path must match the normalized DOS path, the size must be exactly 691200, the bytes must be a PE32+ AMD64 image, and the SHA-256 must match the member pin. The same scope is read again after that check and immediately before the command. The only command is `plugin load` plus the stem, passed to `executeCommand(command, false)`.

An original `SpeedFlipTrainer` / `SpeedFlipTrainer.dll`, or the generated stem, already present in `PluginManager::GetLoadedPlugins` (`_filename`, `fileName`, `pluginName`, or `className`, leaf or full path) refuses the load. `executeCommand` returning is not confirmation. A later tick must see the generated stem on a known plugin list, and the nonce, pid, and process start must still be the attempt's identity. Frontend is not required again after dispatch, so an owned custom-training match can still be confirmed. The wait is 5 seconds. After that the heartbeat is `unknown` / `confirmation_timeout`, the pin stays, and a plugin that appears later stays unconfirmed. A throw from the command callback is `unknown` / `request_outcome_unknown`, keeps the pin, and is not repeated. A scope change or unreadable gamespeed or a missing executor before the callback releases the pin. Once the callback was entered, the pin stays until this plugin unloads.

## Loaded acknowledgement

Published only after PluginManager confirmation and live safeguard success, on `native_community_status`, with exactly these nine keys:

`status` (`loaded`), `site_id`, `nonce`, `stem`, `filename` (`stem.dll`), `pid`, `start_identity`, `member_sha256`, `archive_sha256`.

Pending, refused, and unknown heartbeats use the same key and add `reason`, `pid`, `start_identity`, `game_verified: false`, and `production_allowed: false` when the request was parsed. Root matches `nonce`, `pid`, `stem`, and `start_identity` before showing that host error. Those records are not the nine-key acknowledgement.

Before the command, the host snapshots `sv_soccar_gamespeed` only so a change during the load can be undone once. After a successful safeguard, or on timeout, callback failure, or scope loss, that snapshot is restored if it drifted and then dropped. Later training-speed changes are left alone. `sf_remember_speed`, `sf_change_speed`, and `sf_save_attempts` are forced to zero only while this attempt's owned identity is still current. On scope loss or unload, a flag is written back to its captured value only when it is still the zero this host wrote. If the user or the core changed it, the host stops owning it and does not write again. A partial safeguard write is rolled back the same way. A failed read or write does not mark the flag released. The host never calls `plugin unload`, `writeconfig`, or `exec config.cfg`, and it does not delete speedflip data.

After the load callback has been entered, the pin stays until this plugin's unload, including after scope loss or an unknown result. Unload joins no extra thread; the load is synchronous on the game thread. Restoring the three cvars while the other DLL remains loaded can turn that plugin's saved-speed behavior back on. Whether the core unloads the other DLL with this one is unknown.

## Menu

The button exists only when `native_community_trial.available` and `can_prepare` are true, `site_id` is `286`, the selected community id is `286`, the session is not busy, and the trial status is not `loaded`, `refused`, or `unknown`. Label: `Try Speedflip Trainer`. Action: `community_trial_prepare` with payload `{}`. Any other payload is refused. `community_activate` stays unsupported. `can_activate: true` does not enable "Enable in game".

Status text is plain. A message that contains a slash, `plugin load`, or `.dll` is replaced with a fixed sentence. Root publishes `native_community_trial` and `native_community_request`, and reads `native_community_status`. The Python command allowlist already accepts `community_trial_prepare` and calls `prepare`. This change allows that same empty payload in `LocalBridge` and `NativeCareerLayout`.

## Heartbeat fields

`native_movie_trial.movie_ready` is the live movie session ready flag. `executable_sha256`, `bakkes_core` (`229`, not `Bakkes229`), and `game_build` appear only when `verifiedBuild` succeeds. `runtime_verified` and `production_ready` stay false. The plugin status also includes top-level `in_replay` and `frontend` (`!in_game && !replay && !online`). `movie_ready` is copied under the movie mutex; `verifiedBuild` runs after that lock is released.

## Tests and build

`plugin/tests/native_community_host_tests.cpp` is registered in CMake as `mct_native_community_host_tests` for both configurations. It uses a 256-byte synthetic PE and an injected profile. The production-constant case still refuses that file with `member_size`. `--emit-receipt-fixtures` prints one nine-key loaded acknowledgement for nonce `12345678-1234-4234-8234-123456789abc`, pid `4242`, and start `1740000000.125`, using the production hashes. This emitted record was checked against the actual Python parser and pinned profile. It does not open a DLL. No community DLL is loaded and no game, Steam, or injector is started.

The target links `mct_bridge` and Windows `bcrypt`. It also checks a successful safeguard write followed by failed readback: cleanup ownership survives, and a later closed-state tick restores only a still-owned zero. The layout target covers the button and exit availability. Build the trial DLL from the existing `build/plugin-native-movie` cache without `-A`. Build the normal DLL from `build/plugin`. Do not copy either DLL into the game or BakkesMod.
