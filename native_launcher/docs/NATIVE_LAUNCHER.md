# Owned offline launcher

`production_ready: false`

`game_verified: false`

`file_view_observed: false`

This directory builds `MctNativeLauncher.exe`, the helper that can start one pinned offline Rocket League process with the existing file-view DLL. It does not prove that Rocket League called `CreateFileW`, and it does not prove that a menu package was visible in game. The synthetic file-view fixture already covered that read in a benign process.

The helper does not accept an executable, a DLL, a process id, or extra arguments. A run without exactly `--launch-offline` prints usage and exits 2. `--launch-offline` reads one UTF-8 JSON object from stdin, at most 8192 bytes, then stops reading. Closing that pipe does not stop the game. The helper does not change the parent environment, services, firewall, or any other process that was already running.

## Plan

```json
{
  "protocol": 1,
  "session": "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
  "game_root": "D:\\Games\\rocketleague",
  "private_package": "C:\\Users\\me\\AppData\\Local\\MyCareerTraining\\private\\GFX_MainMenu_SF.upk",
  "private_package_sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
}
```

`session` is a canonical lowercase UUID. It is the nonce written to `MCT_NATIVE_MOVIE_SESSION`. `game_root` is the absolute installation directory that contains `Binaries` and `TAGame`. `private_package` is an absolute regular file outside that directory. Unknown fields, nested values, duplicate keys, uppercase hashes, and uppercase UUIDs are rejected. Strings are UTF-8; the helper does not fetch a URL.

Two optional flat pairs may be added without replacing the main fields. Both members of a pair are required together, and at most these two extras are accepted:

- `private_midgame_package` and `private_midgame_package_sha256`
- `private_endgame_package` and `private_endgame_package_sha256`

The plan cannot name a source path, a source hash, an executable, or a package id outside this fixed set. Source paths are derived from `game_root` and the compiled relative pins. With both extra pairs absent, the plan and the launch receipt keep the original fields.

These pins are compiled into the helper. The plan cannot replace them.

| File | Relative path | Size | SHA-256 |
| --- | --- | --- | --- |
| Executable | `Binaries/Win64/RocketLeague.exe` | 39727616 | `56b499a85ad927c6b5cc47cb4813f956dd9263405fdf4eddc65b669b53185bc7` |
| Source package | `TAGame/CookedPCConsole/GFX_MainMenu_SF.upk` | 3418271 | `d3e0eeadd2766fa1fb10c2d220c22a84ab2f26fb6bbb89b414a26ef1fd6e2f65` |
| Midgame source | `TAGame/CookedPCConsole/GFX_MidGameMenu_SF.upk` | 814718 | `25176a42c7990fce5670f2907020a3641a521553a4aa3c583588717b36e40f50` |
| Endgame source | `TAGame/CookedPCConsole/GFX_EndGameMenu_SF.upk` | 4348661 | `dc4735a75d5ec8ffff423c4db92c3fad1f859191bf384e20ad949e4ed757b3cc` |
| Private package | caller path, outside the game | 1 byte through 16 MiB | caller SHA-256, checked from the held handle |

The adjacent DLL is `MctNativeFileView64.dll`. Its SHA-256 is generated from the linked binary and checked from a read-only handle. A plan cannot name a different DLL. The DLL path must round-trip through the process ANSI code page with `WC_NO_BEST_FIT_CHARS`; a lossy substitution is rejected because Detours takes that path as `LPCSTR`.

Paths are canonical drive paths from `native_file_view/include/FileViewPath.h`. UNC, device, drive-relative, and non-absolute inputs are rejected. Reparse ancestors, directories, and non-regular files are rejected. After a file is opened, its DOS final path must match the requested canonical path, so a parent replaced by a junction between the walk and the open is not held. The same canonical path or the same file id is rejected, including a hard link. The private file cannot be the game root or anything inside it.

## Process

The helper holds read-only handles to the executable, every approved source package, every approved private package, and the DLL, sharing only `FILE_SHARE_READ`, until the owned process exits. A repeated path or file id across those files is rejected. Hashes are read from those handles. It refuses the launch when a Toolhelp snapshot shows any `RocketLeague.exe`. That snapshot does not open those processes. It creates only the pinned executable with `DetourCreateProcessWithDllExW` and `CREATE_SUSPENDED`.

The command line is exactly:

`RocketLeague.exe -rlbot RLBot_ControllerURL=127.0.0.1:23233 RLBot_PacketSendRate=240 -nomovie`

The launch mode follows the pinned [RLBot v5.0.0-rc18 Steam launcher](https://github.com/RLBot/core/blob/v5.0.0-rc18/RLBotCS/ManagerTools/LaunchManager/Steam.Windows.cs), which supplies the RLBot arguments and Steam environment without adding `-noeac`.

`-rlbot` selects RLBot's offline mode. Do not combine it with `-noeac`: the supported game build connected to RLBot and produced live packets with the official RLBot argument set, while adding `-noeac` prevented that connection in the controlled test. Manual BakkesMod-only `-noeac` guidance is a separate mode. The working directory is the executable's parent. Child handles are not inherited. The game is not started hidden; the helper itself is a windowless program. The child environment is a copy of the parent block with `SteamAppId=252950`, `SteamGameId=252950`, and `MCT_NATIVE_MOVIE_SESSION` set to the session. The parent process environment is unchanged.

While the new process is suspended, the helper checks its pid, creation time, Win32 image path, and NT image path against the held executable. With no extra package it copies one `MctFileViewScopeV1`. With one or both extras it copies one fixed `MctFileViewScopeV2` (count 2 or 3, three slots, ids main=1, midgame=2, endgame=3). Both use `DetourCopyPayloadToProcess` and GUID `{7B1E6A14-2C4F-4A8E-9D33-5F0B8C2E71A6}`. The scope names only those approved packages. It checks again for any other `RocketLeague.exe` and resumes only after that check. On a failure before resume, it calls `TerminateProcess` only on the new process handle and waits up to 5 seconds. It does not open or kill a process by pid, and it does not kill a game that was already running.

If that wait confirms the child has exited, the helper closes the process and thread handles and then drops the file holds. If `TerminateProcess` fails and the child is still alive, or the wait times out, the helper keeps those CreateProcess handles and the file holds. It writes the error receipt, does not write a launch receipt, and stays alive until the owned process handle is signaled. A partial create that returned a handle is handled the same way. After a confirmed exit, process handles are closed. They are not closed while the child may still be running.

`MctNativeFileView64.dll` detours `CreateFileW` only. A read-only `OPEN_EXISTING` of the canonical source package path is redirected to the private file. Writes are denied by the hook. `CreateFileA`, `NtCreateFile`, and other package readers are not intercepted. Nothing in this helper observes which calls the game made.

## Receipts

Stdout is one JSON object per line. After resume the helper writes a launch receipt and stays alive:

```json
{
  "protocol": 1,
  "kind": "launch",
  "pid": 0,
  "create_time": 0.0,
  "executable": "D:\\Games\\rocketleague\\Binaries\\Win64\\RocketLeague.exe",
  "session": "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
  "source_package_sha256": "d3e0eeadd2766fa1fb10c2d220c22a84ab2f26fb6bbb89b414a26ef1fd6e2f65",
  "source_executable_sha256": "56b499a85ad927c6b5cc47cb4813f956dd9263405fdf4eddc65b669b53185bc7",
  "private_package_sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "private_package": "C:\\Users\\me\\AppData\\Local\\MyCareerTraining\\private\\GFX_MainMenu_SF.upk",
  "production_ready": false,
  "game_verified": false,
  "file_view_observed": false
}
```

`create_time` is seconds since the Unix epoch, using the same Windows `FILETIME` conversion as psutil (`high * 429.4967296 + low * 1e-7 - 11644473600`). Root can compare it with `psutil.Process.create_time()` within 0.01 seconds, together with the pid and executable, using the existing `ProcessIdentity` check.

When the owned process exits, the helper writes one exit receipt with `kind` `exit` and `exit_code`, then releases its handles. It does not delete the source package or the private package. Private-cache cleanup belongs to a later root change. A refusal with no live child writes `kind` `error` and exits 1. A refusal whose child is still alive also writes that error line first, keeps running, and after the child exits writes an exit receipt only when the pid and create time were already known. The helper then exits 1. The helper's own exit after a normal resumed launch is 0 even when the game's exit code is not.

## Receipt fixtures

`mct_native_launcher_tests.exe --emit-receipt-fixtures` prints three JSON lines and creates no process: a launch receipt, an error receipt, and an exit receipt. The serializers are the same functions the helper uses. The values are synthetic: pid `4242`, create time `1710000000.25`, session `aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee`, executable `C:\Games\rocketleague\Binaries\Win64\RocketLeague.exe`, and the private path under `AppData\Local\MyCareerTraining\private`. They are not a launch and not game evidence. `MctNativeLauncher.exe` does not accept this flag.

## Limits

This helper is not game-verified. The file-view DLL still intercepts only `CreateFileW`. A final-path comparison rejects an open that no longer names the requested path; it does not freeze every ancestor for the life of the process. Termination uses only the handle from create. A child that survives `TerminateProcess` and the 5-second wait stays owned until that process handle is signaled. The helper does not adopt a game it did not create and does not open a process by pid. An uncertain child with a process handle but no captured create time produces the error line only, then exit code 1 after that handle is signaled, with no exit receipt. A create that returns a thread handle and no process handle is left open; the helper keeps the file holds and does not exit, because it has no owned process handle to wait on. The pure tests do not start Rocket League or this helper's launch command.

## How root should call it

The integrated bootstrap requires Steam, the recorded installation, and no game or native helper already running. `NativeOfflineSession` prepares the private movie with the bridge nonce before staging the plugin, then uses the bounded adapter:

```python
from my_career_training.native_launch import launch_native_offline

owner = launch_native_offline(game_root, private_package, private_sha256, session)
# optional: additional_packages={"midgame": {"private_package": path, "private_package_sha256": digest}}
game_identity = owner.identity
```

The adapter reads bounded receipts with a deadline and retains the helper. An uncertain launch leaves plugin recovery deferred, including when the helper has not created its child yet. The shared plugin-session guard blocks recovery while a native helper remains. Do not kill the helper when the desktop app exits or put the game in a kill-on-close job. `production_ready`, `game_verified`, and `file_view_observed` remain false. A requested extra adds `private_midgame_package`, `private_midgame_package_sha256`, and `source_midgame_package_sha256`, and the same three names for endgame. The receipt limit is 8192 bytes. The build runtime receipt is unchanged and still pins the helper and file-view DLL only.

The online handoff stays the existing lifecycle: save, stop the worker, save, `graceful_close` of the owned window (`WM_CLOSE` only), wait until no Rocket League process remains, `restore_plugin_session`, recheck that no game started during cleanup, then the normal Steam online launch. The helper only waits for the process it created. It does not restore BakkesMod files or launch online.

The Detours 4.0.1 MIT license is copied beside `MctNativeLauncher.exe` as `DETOURS-MIT-LICENSE.txt`, with separate provenance in `NOTICE`. Build this directory with the Windows MSVC build tools. A local pinned Detours archive may be reused; a fresh checkout downloads the same hash-pinned source. The launcher and file-view DLL link their C/C++ runtime statically. Their Release import tables contain only Windows system libraries. Do not point the helper at a synthetic executable; the create path is hard-gated to the pinned game image.
