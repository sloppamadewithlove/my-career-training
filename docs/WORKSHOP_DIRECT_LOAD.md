# Direct Workshop load candidate

`WorkshopLoadPlan` prepares one development command for a package that is already installed under Steam Workshop app `252950`. The command text is `load_workshop` plus the package's absolute path in double quotes. The function reads that file and returns a plan. It does not run the command, load a DLL, copy or rename a map, or write anything under the game.

`gameTested` and `productionAllowed` are false on every plan, including a plan whose `allowed` field is true. The observed executable hash, BakkesMod core, and game build permit this experiment only. They are not proof that the command exists, that it can load the package, or that running it preserves the installation. Real command availability and in-game file preservation are unverified, so the production gate stays closed.

This header does not change `workshop.prepare_launch` or the RLBot match path. That path remains refused because the pinned RLBot core writes `Haunted_TrainStation_P.upk`.

## Evidence

Usage of the command string is taken from [CustomMapsPlugin.cpp](https://raw.githubusercontent.com/Capstoner1/CustomMapsPlugin/main/CustomMapsPlugin.cpp). Lines 379–392 enumerate installed packages. Lines 685–692 pass `load_workshop` and an absolute map path, wrapped in double quotes, to `executeCommand`. This repository does not copy that source and does not adopt its license.

The BakkesMod SDK `CVarManagerWrapper::executeCommand` returns `void`. The SDK has no query for whether a console command is registered. `getCvar` reads a cvar; a cvar lookup does not prove that `load_workshop` is registered.

Reading that plugin does not prove the command's implementation avoids writing cooked assets or other game files. A later trial has to compare a full installation baseline before and after any real execution. This module does not run that comparison and does not execute the command.

## Call

Header-only `plugin/include/WorkshopLoadPlan.h`.

```cpp
mct::WorkshopLoadPlan plan = mct::WorkshopLoadPlan::prepare(scope, selection);
```

`prepare` re-reads the package on every call. It keeps no file handle and no last-file cache. There is no function that accepts an arbitrary console string, bridge action, or command payload.

`WorkshopLoadScope` carries the live session. `developmentTrial` defaults to false. The other gates are a fresh owned offline Steam frontend: `owned`, `offline`, and `fresh` are true; `online`, `inGame`, `replay`, and `busy` are false; `steamFrontend` is true. `executableSha256` must equal `56b499a85ad927c6b5cc47cb4813f956dd9263405fdf4eddc65b669b53185bc7`. `bakkesCore` must equal `229`. `gameBuild` must equal `261013.63066.530866`. A file version, a Steam build id, or a different core does not satisfy those fields. `nonce` is 16 to 128 characters of letters, digits, `_`, and `-`. `generation` is a non-zero value. The selection's nonce and generation must equal the scope.

`WorkshopPackageSelection` carries the host's trusted `contentRoot`, the absolute `packagePath`, the numeric `itemId`, and the same nonce and generation. On a later call, copy `expectedSize` and `expectedIdentity` from the previous plan. Leave both unset the first time. If either is set and the live file differs, the reason is `package_changed`.

An allowed plan has:

| Field | Value |
| --- | --- |
| `allowed` | true |
| `gameTested` | false |
| `productionAllowed` | false |
| `command` | `load_workshop "<canonical path>"` |
| `reason` | `development_trial_only` |
| `packageSize` | byte size read for this call |
| `packageIdentity` | lowercase SHA-256 of those bytes |
| `canonicalPath` | absolute package path used inside the quotes |
| `contentRoot`, `itemId`, `nonce`, `generation` | values the host can pass back in |

A rejected plan has `allowed` false, an empty `command`, size `0`, an empty identity, and the same two gates false. `reason` is a fixed token. Paths are not copied into the reason.

Package bytes must be from 4 bytes through 1 GiB inclusive, the same bounds as `MAX_MAP_BYTES` in `content.py`. The first four bytes must be the Unreal package magic `C1 83 2A 9E` used by `content.py` and `workshop.py`. That minimum and magic are a preview header check only. They are not a parse of a complete UPK and they do not establish that the rest of the package is well formed. The SHA-256 is an identity for the host to notice replacement. It does not mean the package is safe, playable, or free of other files.

Hashing reads the file on the calling thread and can block for the full 1 GiB. The host has to do that work off the interactive thread, then refresh the owned scope before using the plan. Freshness can expire while the hash runs. The content root and the scope are trusted only because the caller supplied them.

## Path rules

`contentRoot` is supplied by the host. It is an absolute directory whose last four components are `steamapps`, `workshop`, `content`, and `252950`. The helper does not read the Steam registry, `libraryfolders.vdf`, or a default Program Files path. A root from a UI field or a bridge action is not trusted. The existing Python discovery in `steam_library_roots` remains the host's source for that directory; this header does not call it.

`packagePath` must be an absolute ordinary file strictly under `contentRoot/<item id>/`. The first component below the root is the item id, it is 1 to 20 digits, and it equals `itemId`. At most seven components may follow the item id, which is the depth `discover_steam_maps` already walks. The filename ends in `.udk` or `.upk`. Spaces are allowed. The Windows command uses backslashes.

The same call rejects `.` and `..` components, a relative path, a UNC path, a `\\?\` or `\\.\` device path, a reserved device name such as `NUL.upk`, an alternate data stream, quotes, control characters, and command separators (`&`, `|`, `;`, and the other characters rejected in the header). That character filter stays broad until the real BakkesMod console parser is observed. It is not a complete quoting model, and it should not be narrowed from source inspection alone.

The call also rejects a directory, a different app id, a file outside the root, and any ancestor or leaf that `GetFileAttributesW` reports as a reparse point. `FILE_FLAG_OPEN_REPARSE_POINT` covers the final component only. `CreateFileW` can still follow an ancestor that was swapped for a junction after the name walk. Before any package byte is accepted, the open handle must be `FILE_TYPE_DISK`, and `GetFinalPathNameByHandleW` (`FILE_NAME_NORMALIZED | VOLUME_NAME_DOS`) must return a fixed-size `\\?\X:\` path whose drive form matches the intended canonical path. The compare is `CompareStringOrdinal` with case ignored. A UNC result, any other prefix, an error, or a buffer that does not fit is `resolved_path_mismatch`. This narrows that ancestor-swap window for this read. Closing the handle does not pin the path a later executor would open. On other platforms the ancestor check is `lstat`. There is no fallback to an imported map, another app id, or a search of the folder.

## Reasons

Scope, in order: `development_trial_required`, `unowned_session`, `stale_session`, `online_session`, `not_offline`, `not_steam_frontend`, `in_game`, `replay`, `busy`, `executable_hash_mismatch`, `bakkes_core_mismatch`, `game_build_mismatch`, `invalid_scope_nonce`, `invalid_scope_generation`, `nonce_mismatch`, `generation_mismatch`.

Path and package: `path_forbidden_characters`, `device_path`, `unc_path`, `alternate_data_stream`, `path_traversal`, `path_not_absolute`, `path_malformed`, `path_too_long`, `content_root_rejected`, `workshop_app_mismatch`, `invalid_item_id`, `item_id_mismatch`, `path_outside_root`, `package_depth`, `package_extension`, `symlink_or_reparse`, `resolved_path_mismatch`, `content_root_missing`, `package_missing`, `package_directory`, `package_not_regular`, `package_unreadable`, `package_too_small`, `package_too_large`, `package_magic`, `package_changed`.

## Host integration

Root owns CMake and any future executor. This module is not wired into the plugin, the bridge, or `prepare_launch`.

1. Build the scope from the live owned offline session (`OwnedSession::ownedSession` or the host's equivalent), the frontend flags, and the current nonce and generation. Set `developmentTrial` only in the development host.
2. Fill the hash, BakkesMod core, and game build from that same process. A match opens the candidate only.
3. Pass the absolute `.../steamapps/workshop/content/252950` directory the host already resolved. Do not accept that path from UI or bridge text.
4. Pass the absolute `.udk` or `.upk` the player selected under `root/<item id>/`, and that item id.
5. Call `prepare`. Keep `packageSize` and `packageIdentity` with the canonical path.
6. Hash off the interactive thread. When it returns, refresh the owned scope and call `prepare` again with `expectedSize` and `expectedIdentity` set. A removed or replaced file is rejected. This header still does not execute. The handle from the read is already closed, so the path can still change before a future executor opens it.
7. An executor, if one is added later, has to show that `load_workshop` is actually registered and that a full file baseline is unchanged. Until that evidence exists, leave the command unrun. `productionAllowed` and `gameTested` stay false.

Suggested registration, for the root build:

```cmake
add_executable(mct_workshop_load_plan_tests tests/workshop_load_plan_tests.cpp)
target_include_directories(mct_workshop_load_plan_tests PRIVATE include)
target_compile_features(mct_workshop_load_plan_tests PRIVATE cxx_std_17)
add_test(NAME workshop_load_plan COMMAND mct_workshop_load_plan_tests)
```

The fixture is `plugin/tests/workshop_load_plan_tests.cpp`. It builds synthetic packages under the test executable's `build` directory, including a path with spaces. It does not read the player's game files and it does not call an executor. The reparse case is a directory junction: `GetFileAttributesW` reports `FILE_ATTRIBUTE_REPARSE_POINT` on that ancestor, so `prepare` rejects it before the open. The same junction path is also passed straight to `readPackage`. The open follows the ancestor, the resolved DOS path is the target, and the read is rejected. The ordinary path of that file is accepted. This environment cannot create an unprivileged file symlink.

A passing test, a matching hash, and an allowed plan are still a development candidate. They are not a game test and they do not authorize production map launch.
