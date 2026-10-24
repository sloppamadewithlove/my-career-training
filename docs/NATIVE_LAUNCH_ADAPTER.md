# Native launch adapter

`native_launch.py` starts the compiled helper `MctNativeLauncher.exe` and checks the one launch receipt that helper writes. The helper is the process that creates Rocket League. This module keeps that helper process, reads its stdout, and returns the child identity. It does not build a second game command line, and it does not stop a helper or a game after the helper has been started.

`game_verified` and `production_ready` remain false. A `ready` status means the receipt matched the request and the child process. It does not mean the file view ran inside the game. `view_active` and `lock_active` stay false. `file_view_observed` stays false. After the helper process exits while that child is still alive, `poll()` reports `degraded` and still does not describe the file view or the file lock as active.

The stdout objects match `native_launcher/src/LaunchText.cpp`: `kind` is `launch`, `error`, or `exit`. The launch receipt names the executable hash `source_executable_sha256`. An error receipt has an `error` string and does not include a session or a child-created flag. The helper writes that error and exits 1 when it refuses, including when it has already terminated a suspended process it created. This module treats that refusal as final only when the helper has exited and no Rocket League process is visible.

## Startup integration

1. Stage only the four runtime files into `my_career_training/runtime/native` (the installed package) or `<repo>/runtime/native` (a development tree). `build_runtime_receipt()` returns the receipt object. This module does not copy binaries and does not download Detours.
2. Hold the returned `OwnedNativeLaunch` on the bootstrap service for the whole owned session. The object keeps the helper `Popen`. `retained_helpers()` is a second reference so a dropped exception does not abandon a running helper.
3. Call `launch_native_offline(game_root, private_package, private_package_sha256, session)` only after the existing Steam offline preflight. `session` is a canonical lowercase UUID. The private package is an absolute `.upk` outside the game tree, at most 16 MiB, with a lowercase SHA-256.
4. On `NativeLaunchError`, the helper was not started or it has exited with no visible game remaining (`defer_restore` is false). A refused helper may have already terminated its own suspended child. Every `PluginSession` guard includes any live native helper as well as Rocket League; the bootstrap integration tests cover this recovery ordering.
5. On `NativeLaunchUncertain`, leave the helper and any Rocket League process running (`defer_restore` is true). Both bootstrap exception paths defer restoration. The exception carries `reason`, `helper`, `helper_pid`, `helper_running`, `games`, `receipt`, `session`, and `private_package`. The process-name recovery guard also covers an app restart while the helper is still starting.
6. Poll the owned object. `ready` means the helper and the matched child are alive. `reaping` means the child is gone and the helper is still alive. `degraded` means the helper has exited while the child is still alive. `exited` means both are gone. `release()` drops the Python reference only after the helper has exited. It does not stop the helper or the game.
7. Keep the existing online close and restore flow. This adapter does not close Rocket League, delete the private package, or write key material.

The helper PID is the `Popen.pid`. The game PID is `identity.pid`. They are different processes.

## Runtime directory

Lookup order, first existing directory:

- `<package>/runtime/native` where `<package>` is the `my_career_training` directory
- `<repo>/runtime/native`

An explicit `runtime_directory` must be the same directory as one of those two. Other roots are rejected, including UNC paths, device paths, and reparse points. The directory must contain exactly these names:

- `MctNativeLauncher.exe`
- `MctNativeFileView64.dll`
- `DETOURS-MIT-LICENSE.txt`
- `native-launch-receipt.json`

Both binaries must be AMD64 PE32+. The executable must not be a DLL. The DLL must be a DLL. Sizes and SHA-256 values must match the receipt. The notice file must be the upstream Detours 4.0.1 `LICENSE.md` bytes: 1099 bytes, SHA-256 `b301808b732cfaa60df2b4b422d78cd97d2a15058b207e7e33f0535ba5170dd6`. The receipt is local evidence that these staged files belong together. It is not a publisher signature.

Supported game pins, fixed in this module and required in the receipt:

| File | SHA-256 | Size |
| --- | --- | --- |
| `Binaries/Win64/RocketLeague.exe` | `56b499a85ad927c6b5cc47cb4813f956dd9263405fdf4eddc65b669b53185bc7` | 39727616 |
| `TAGame/CookedPCConsole/GFX_MainMenu_SF.upk` | `d3e0eeadd2766fa1fb10c2d220c22a84ab2f26fb6bbb89b414a26ef1fd6e2f65` | 3418271 |

`build_runtime_receipt(helper_sha256, helper_size, file_view_sha256, file_view_size)` fills every receipt field. Callers pass only the two measured binaries. Source pins, the notice pin, `machine: "AMD64"`, and both false flags are not caller choices. Unknown receipt fields are rejected.

## Helper process

Windows only. The process is:

```text
MctNativeLauncher.exe --launch-offline
```

`shell` is false. The environment and working directory are the parent process environment, unchanged. No `MCT_NATIVE_MOVIE_SESSION` value is written into the parent environment. The window flag is `CREATE_NO_WINDOW`. Stdin and stdout are pipes. Stderr is drained up to 16 KiB and then discarded so a chatty helper cannot fill the pipe. The game does not inherit those pipes. Closing them does not stop the game.

Before `CreateProcess`, launch opens `MctNativeLauncher.exe` again on a read-only Win32 handle (`FILE_READ_DATA | FILE_READ_ATTRIBUTES`, `FILE_SHARE_READ`, reparse point left unfollowed). That handle stays open until `Popen` returns, including when `Popen` fails, and it is not inherited. Size, file identity, SHA-256, and the AMD64 PE32+ check run on the bytes read from the handle. A concurrent write, delete, or replacement of that file is refused while the handle is open. The directory check in `validate_native_runtime()` still reads and closes the file; launch opens this hold afterward. The hold covers an ordinary update that lands between those two steps. Same-user tampering is outside this check.

One JSON object is written to stdin, then stdin is closed:

```json
{
  "protocol": 1,
  "session": "12345678-1234-4234-8234-123456789abc",
  "game_root": "C:\\Games\\Rocket League",
  "private_package": "C:\\Users\\me\\AppData\\Local\\MyCareer\\private\\menu.upk",
  "private_package_sha256": "<64 lowercase hex>"
}
```

There is no executable, DLL, PID, or argument field. The helper owns the game command. The offline child arguments it must use, and that this module requires on the live process, are exactly:

```text
-noeac -rlbot RLBot_ControllerURL=127.0.0.1:23233 RLBot_PacketSendRate=240 -nomovie
```

The child environment remains the helper's responsibility: a copy of the parent environment with `SteamAppId=252950`, `SteamGameId=252950`, and `MCT_NATIVE_MOVIE_SESSION` set to the same session value.

## Stdout receipts

The first line is one JSON object. The helper caps the JSON at 4096 bytes and then writes a newline. This module reads that line with a 15 second timeout. `true`/`false` are booleans and are rejected where a number is required. `Infinity`, `NaN`, and non-finite numbers are rejected. Duplicate keys and unknown fields are rejected. `game_verified`, `production_ready`, and `file_view_observed` must be JSON `false`.

Launch, after the helper has resumed the child:

```json
{
  "protocol": 1,
  "kind": "launch",
  "pid": 424242,
  "create_time": 1735000000.125,
  "executable": "C:\\Games\\Rocket League\\Binaries\\Win64\\RocketLeague.exe",
  "session": "12345678-1234-4234-8234-123456789abc",
  "source_package_sha256": "d3e0eeadd2766fa1fb10c2d220c22a84ab2f26fb6bbb89b414a26ef1fd6e2f65",
  "source_executable_sha256": "56b499a85ad927c6b5cc47cb4813f956dd9263405fdf4eddc65b669b53185bc7",
  "private_package_sha256": "<same hash as the request>",
  "private_package": "C:\\Users\\me\\AppData\\Local\\MyCareer\\private\\menu.upk",
  "production_ready": false,
  "game_verified": false,
  "file_view_observed": false
}
```

`create_time` is seconds since the Unix epoch. The helper uses the same Windows `FILETIME` conversion as psutil (`high * 429.4967296 + low * 1e-7 - 11644473600`). The adapter accepts it when `abs(psutil - receipt) <= 0.01`. The stored `ProcessIdentity.created` is the psutil value. `executable` must be the same file as `<game_root>/Binaries/Win64/RocketLeague.exe`. The receipt PID must not be the helper PID. After the receipt, exactly one `RocketLeague.exe` process may exist, and it must be that PID. The command tail must be the five offline arguments above, and `offline_launch_arguments` must accept the full command.

Error, when the helper refuses:

```json
{
  "protocol": 1,
  "kind": "error",
  "production_ready": false,
  "game_verified": false,
  "file_view_observed": false,
  "error": "private package hash does not match"
}
```

The `error` string is at most 180 UTF-16 code units from the helper. This becomes `NativeLaunchError` with code `helper_refused` only when the helper has exited and process enumeration sees no Rocket League. A still-running helper, a visible game, or a failed enumeration becomes `NativeLaunchUncertain`.

Exit, one later line after the helper has waited for the child:

```json
{
  "protocol": 1,
  "kind": "exit",
  "production_ready": false,
  "game_verified": false,
  "file_view_observed": false,
  "pid": 424242,
  "create_time": 1735000000.125,
  "exit_code": 0,
  "session": "12345678-1234-4234-8234-123456789abc",
  "executable": "C:\\Games\\Rocket League\\Binaries\\Win64\\RocketLeague.exe"
}
```

`poll()` stores that object on `exit_receipt` when the pid, session, start time, and executable match the owned child. `exit_code` is a Windows `DWORD`, including 259 when that is the actual exit value. The helper waits for its process handle to be signaled before reporting exit; the adapter also checks live process identity. An exit number alone does not establish that a process is gone. A bad exit line leaves `exit_receipt` empty and does not change the false verification flags. See Microsoft's [GetExitCodeProcess documentation](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getexitcodeprocess).

The stdin plan is at most 8192 bytes. `session` must be a canonical lowercase UUID whose version nibble is `1` through `8` and whose variant nibble is `8`, `9`, `a`, or `b`. `game_root` and `private_package` are at most 480 characters, without a quotation mark. Those limits are the helper's `kMctLaunchPlanMaxBytes`, `MctIsCanonicalUuid`, and `kMctLaunchPathMaxChars`.

Timeout, an oversized line, invalid UTF-8, or EOF while the helper is still running, or while any Rocket League process is visible, is `NativeLaunchUncertain`. The same read failures become `NativeLaunchError` only when the helper has already exited and no Rocket League process is visible. A launch receipt that does not match the request, the executable, the start time, the command line, or the single-game check is always uncertain: the helper may already own a new game. Uncertain results keep the helper registered. They do not stop it, and they do not delete the private package.

The build receipt in `runtime/native` is separate from these stdout lines. The helper does not write `native-launch-receipt.json`. Root's later stager writes that file with `build_runtime_receipt()`. Its game hash field is `source_exe_sha256`. The stdout launch receipt's field for the same pin is `source_executable_sha256`.

## Receipt fixtures

The initial plan write and first receipt share one 15-second deadline. A
blocked pipe writer or reader cannot make the caller wait indefinitely. Pending
I/O stays on its own thread; the timeout path does not close a buffered stream
from a second thread, which could wait on the first thread's I/O lock. A timeout
retains the helper and defers recovery as described above. Tests cover a blocked
writer and a real anonymous-pipe reader without launching any process.

`build/native-launcher/bin/mct_native_launcher_tests.exe --emit-receipt-fixtures` prints three production receipt lines and does not start a game or `MctNativeLauncher.exe`. The Python test runs that mode only when this exact test binary is present, and skips when it is absent. The lines use these synthetic values:

| Field | Value |
| --- | --- |
| session | `aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee` |
| executable | `C:\Games\rocketleague\Binaries\Win64\RocketLeague.exe` |
| private package | `C:\Users\me\AppData\Local\MyCareerTraining\private\GFX_MainMenu_SF.upk` |
| private package SHA-256 | `0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef` |
| pid | `4242` |
| create_time | `1710000000.25` |
| source hashes | the pinned game hashes in the table above |
| error text | `Rocket League is already running` |
| exit_code | `0` |

Launch uses `kind` `launch` and `source_executable_sha256`. Error uses `kind` `error` and the error text, with no session and no pid. Exit uses `kind` `exit`, the pid, create time, exit code, session, and executable. All three set `protocol` to 1 and `production_ready`, `game_verified`, and `file_view_observed` to false.
