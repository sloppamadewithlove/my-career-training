# Native workshop launcher

`NativeWorkshopLauncher` is a development-only handoff around `WorkshopLoadPlan::prepare`. It is inert unless the constructor is called with `developmentEnabled == true`. A successful poll means the injected callback was entered with one prepared `load_workshop` command. It does not mean the map loaded, the command is registered, or any game file stayed unchanged.

`gameTested` and `productionAllowed` stay false on the launcher and on every result. The compiled-in native movie trial in `MyCareerTraining` owns one launcher. A build with `MCT_ENABLE_NATIVE_MOVIE_TRIAL` off does not construct it. The launcher does not call RLBot and does not copy, edit, or delete a map or game file. `docs/WORKSHOP_DIRECT_LOAD.md` records that the pinned RLBot core writes `Haunted_TrainStation_P.upk`.

## Evidence

BakkesPlugins plugin 223 is Workshop Map Loader & Downloader. In the public source [WorkshopMapLoaderGUI.cpp](https://github.com/Vyncc/Workshop-Map-Loader-Downloader/blob/master/Pluginx64/WorkshopMapLoaderGUI.cpp), `Pluginx64::renderLaunchModePopup` handles the Start button by scheduling this call on `gameWrapper->Execute`:

```cpp
cvarManager->executeCommand("load_workshop \"" + curMap.Folder.string() + "/" + curMap.UpkFile.filename().string() + "\"");
```

That is evidence of the command shape a workshop loader passes to BakkesMod. The same file is not the BakkesMod core. It does not show how `load_workshop` is implemented and it does not show that stock cooked files stay unchanged. The BakkesMod SDK `executeCommand` returns `void` and has no registration query.

That plugin joins a folder and a filename with `/`. `WorkshopLoadPlan` quotes its own canonical Windows path, which uses backslashes. The launcher passes that plan string through and does not rebuild it with the plugin's join.

## Interface

Header-only `plugin/include/NativeWorkshopLauncher.h`.

```cpp
mct::NativeWorkshopLauncher launcher(scope, execute, false);

mct::WorkshopLaunchResult started = launcher.begin(selection);
mct::WorkshopLaunchResult result = launcher.poll();
launcher.waitForPreparation();
launcher.shutdown();
bool held = launcher.holding();
```

`scope` is `std::function<mct::WorkshopLoadScope()>`. `execute` is `std::function<void(const std::string&)>`. `developmentEnabled` defaults to false. Copy and move are deleted. The destructor calls `shutdown()`.

`begin` and `poll` run on the game thread. `begin` snapshots scope and starts one worker. The worker calls `prepare` and pins the package. It does not call `scope` or `execute`, and it does not call into BakkesMod or the game. `poll` is non-blocking. It dispatches only after the worker has finished, and only on the thread that calls `poll`. `waitForPreparation` joins the worker and does not dispatch. `shutdown` joins the worker and then closes handles. Call it before the DLL unloads. There is no detached thread.

`WorkshopPackageSelection` is trusted host data. It is not movie JSON, bridge text, or a console line. There is no method that takes a command string, an executable path, or a PID.

`WorkshopLaunchResult` fields:

| Field | Meaning |
| --- | --- |
| `preparing` | The worker has been started and `poll` has not finished the request. |
| `requested` | The execute callback was entered. This is not a load. |
| `callbackReturned` | The execute callback returned. False when it threw. |
| `held` | This object still has the package pin. |
| `gameTested` | Always false. |
| `productionAllowed` | Always false. |
| `reason` | A fixed token. Paths are not copied into it. |

`begin` returns `preparing` / reason `preparing` without reading the package. A second `begin` while a request is preparing, ready, or held returns `request_held`.

`cancelPending()` is the nonblocking game-tick path for scope loss or nonce
rotation. It cancels a pending dispatch and preserves any already-dispatched
pin. `poll()` collects completed cancelled work without issuing a command.
Only plugin unload uses the joining shutdown path. The final host command
framing is shared with `native_workshop_dispatch_tests`; invalid framing is an
observable refusal, rather than a callback that silently returns as success.

`release` and `shutdown` drop a pin that is not inside the execute callback. A `release` from inside that callback returns without dropping the pin and does not schedule a later drop. After `poll` returns, a later `release` may drop it. A second `release` is a no-op.

On Windows the package handle is `GENERIC_READ` with `FILE_SHARE_READ` only, opened with `FILE_FLAG_OPEN_REPARSE_POINT`. The worker also holds the `252950` directory and the item directory the same way, with `FILE_FLAG_BACKUP_SEMANTICS`. Writers and deleters of the package fail until `release`, `shutdown`, or destruction. `poll` reads four header bytes plus size and the resolved path. It does not hash the package. Ancestor reparse points are checked again on the game thread after the latest scope callback, through the plan's `parsePath` and `walkAncestors` helpers.

The worker calls `prepare` twice, off the game thread: once to build the plan, then again with `expectedSize` and `expectedIdentity` from that plan while the handle is held. `prepare` can read up to 1 GiB through its own 64 KiB buffer. That work blocks the worker, not the game thread. `shutdown` still joins it. The launcher allocates no package-sized buffer and runs no hash of its own.

Other platforms return `unsupported_platform` and do not call either callback.

## Sequence

1. `developmentEnabled == false` returns `development_disabled` without calling either callback.
2. A pin, a worker, or a result waiting for `poll` returns `request_held` without calling either callback.
3. An empty scope or execute callback returns `scope_missing` or `executor_missing`.
4. `begin` calls scope once and starts the worker. The worker runs `prepare`. The command must be exactly `load_workshop "<canonical path>"` from that plan. The worker opens the read-only handles and calls `prepare` again with the captured scope. A changed file stores the plan's reason and closes the handles.
5. `poll` on the game thread, after the worker finishes, calls scope again. Nonce, generation, executable hash, BakkesMod core, game build, and the owned-session flags (`owned`, `offline`, `fresh`, `online`, `steamFrontend`, `inGame`, `replay`, `busy`, `developmentTrial`) must match the captured scope. Any difference returns `scope_changed` and releases the not-yet-dispatched pin.
6. `poll` checks ancestor reparse points, the resolved path, the size, and the four-byte magic. Then it marks the pin held and calls execute. The success and unknown result objects are built before that call.
7. If execute returns, the pin stays open for the owned offline session. If execute throws, the pin stays open, `requested` is true, `callbackReturned` is false, `held` is true, and the reason is `request_outcome_unknown`. A `release` inside that callback does not drop the pin.

The host retains a dispatched pin until plugin unload, including if the frontend becomes an in-game map or the session nonce changes. Scope loss and nonce rotation only cancel preparation that has not dispatched. A second map request stays refused for the rest of this owned process.

A thrown scope callback becomes `scope_exception`. Any other exception becomes `request_exception`. Those results leave `requested` false. Exceptions from the callbacks do not leave `begin` or `poll`.

## Reasons introduced here

`development_disabled`, `request_held`, `scope_missing`, `executor_missing`, `unsupported_platform`, `scope_exception`, `scope_changed`, `command_rejected`, `request_exception`, `request_outcome_unknown`, `preparing`, `cancelled`, `idle`, and `development_trial_only` on a handoff.

Plan refusals pass through unchanged, including `executable_hash_mismatch`, `bakkes_core_mismatch`, `game_build_mismatch`, `stale_session`, `unowned_session`, `nonce_mismatch`, `generation_mismatch`, `path_forbidden_characters`, `path_traversal`, `package_changed`, and `symlink_or_reparse`.

## Plugin wiring

When `MCT_ENABLE_NATIVE_MOVIE_TRIAL` is on, `MyCareerTraining` constructs the launcher with `developmentEnabled` true. The scope callback reads the movie host's verified executable hash, BakkesMod version, and Psyonix build only after that host has compared them. It also reads the live owned offline session, the bridge nonce, and a plugin generation that starts at 1 and increments when that nonce changes. The execute callback calls `cvarManager->executeCommand(command, false)` with the launcher's string. `tick` calls `poll` on the game thread. `onUnload` calls `shutdown` before the launcher is destroyed.

A build with the trial macro off does not construct the launcher and does not hash, hook, or prepare a workshop package for this route.

Suggested registration, for the root build. It is not in `plugin/CMakeLists.txt` yet.

```cmake
add_executable(mct_native_workshop_launcher_tests tests/native_workshop_launcher_tests.cpp)
target_include_directories(mct_native_workshop_launcher_tests PRIVATE include)
target_compile_features(mct_native_workshop_launcher_tests PRIVATE cxx_std_17)
add_test(NAME native_workshop_launcher COMMAND mct_native_workshop_launcher_tests)
```

The fixture is `plugin/tests/native_workshop_launcher_tests.cpp`. It compiles as C++17 with MSVC and writes synthetic packages under the test executable's `build` directory. The callback only records the string. It does not call BakkesMod. From the repository root in PowerShell, create the output directory and run:

```text
New-Item -ItemType Directory -Force -Path build\native-workshop-launcher | Out-Null
cmd /c 'call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" && cl /nologo /std:c++17 /EHsc /W4 /permissive- /utf-8 /I plugin\include plugin\tests\native_workshop_launcher_tests.cpp /Fe:build\native-workshop-launcher\mct_native_workshop_launcher_tests.exe /Fo:build\native-workshop-launcher\ && build\native-workshop-launcher\mct_native_workshop_launcher_tests.exe'
```

`cl` does not create the `/Fo` directory.

## Unknowns

- Whether this BakkesMod core registers `load_workshop` is unverified. Plugin 223 shows a caller, not the core.
- Whether a real `load_workshop` leaves the installation unchanged is unverified. No install baseline is taken here.
- The core's own open flags are unverified. These handles allow other readers and deny writers and deleters. An open that requests write access, or exclusive access, fails while a handle is held.
- `prepare` still hashes up to 1 GiB. That blocks the worker until `shutdown` joins it. It does not run on the game thread.
- The four-byte magic and the SHA-256 identity are not a parse of the package.
- Directory handles cover `252950` and the item directory. They do not pin the rest of the Steam library.
- Non-Windows builds refuse the request. The Windows share mode is the runtime behavior.
- A passing fixture is a synthetic file test. It is not a game test and it does not authorize production map launch.
