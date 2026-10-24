# Native menu candidate

This is a separate developer bundle. It is not the Windows release, not an
installer, and not evidence that Rocket League showed the menu or started a
match. `gameplay_verified`, `game_verified`, `production_ready`,
`runtime_verified`, and `native_host_probe` stay false. The normal release
plugin is still built with `MCT_ENABLE_NATIVE_MOVIE_TRIAL=OFF` and
`MCT_BUILD_HOST_PROBE=OFF` by `scripts/build_plugin.py`.

The candidate compile uses its own CMake directories:

- `build/native-candidate/plugin`
- `build/native-candidate/native-launcher`

Both are Release x64. The plugin configure line is the only place this
pipeline turns the movie trial on, and it forces the host probe off. The
launcher configure line does not pass those plugin switches. Neither command
uses `build/plugin`, `runtime/plugins`, or `runtime/native`.

## What the player gets

`python scripts/build_native_candidate.py` stages and verifies. It does not
freeze. Add `--freeze` to run PyInstaller into:

`build/native-candidate/dist/MyCareerTrainingNativeCandidate`

That folder contains `MyCareerTraining.exe` and `MyCareerTrainingWorker.exe`.
The candidate has its own small GUI entry point. A normal double-click selects
`--native-menu-trial` automatically. Explicit `--worker`, `--manage`, `--self-test`,
`--smoke-test`, and help modes retain their separate behavior and do not acquire
the native launch flag. The normal release entry point is unchanged.

This bundle's only plugin DLL was compiled with the movie trial on. Packaged
`plugin_binary()` selects that DLL. Do not treat this executable as a
substitute for `dist/MyCareerTraining`.

Self-test and the package smoke do not launch Rocket League. This pipeline
does not run `MctNativeLauncher.exe`, BakkesMod, Steam, or `installer.iss`.

## Stage layout

| Path | Contents |
| --- | --- |
| `build/native-candidate/runtime/plugins` | `MyCareerTraining.dll` and `plugin-build-receipt.json` |
| `build/native-candidate/runtime/native` | helper, file-view DLL, `DETOURS-MIT-LICENSE.txt`, `native-launch-receipt.json` |
| `build/native-candidate/runtime/native-menu` | the allowlist already produced by `scripts/stage_native_runtime.py` |
| `build/native-candidate/source-archives` | ImGui, nlohmann json, and plugin source zips |
| `build/native-candidate/candidate-manifest.json` | source commit, source hashes, dependencies, false flags, staged hashes |

The plugin receipt records `inspect_plugin`, the plugin tree hashes, the git
commit, and `plugin/DEPENDENCIES.json`. `native_movie_trial` is true there
because that is the compile switch `native_offline` requires. The manifest
`flags` object is entirely false. `build.native_movie_trial` records the
switch without calling it verification.

`runtime/native-menu` must already exist. This build copies it after checking
the stage allowlist, receipt flags, UEViewer pins, and file hashes. It does
not fetch UEViewer, run Java or Flex, or read the installed game. Cooked
`.upk`, `.gfx`, `.swf`, and `.swc` files are refused. `MctRootMenu.abc` is the
authored menu bytecode and is part of the allowlist.

The launcher build writes `NOTICE` beside `MctNativeLauncher.exe`. The launch
adapter expects `DETOURS-MIT-LICENSE.txt` to be the pinned Detours 4.0.1
`LICENSE.md` bytes (`native_launch.DETOURS_NOTICE_BYTES`, 1099 bytes,
SHA-256 `b301808b732cfaa60df2b4b422d78cd97d2a15058b207e7e33f0535ba5170dd6`).
Staging writes those exact bytes under that name. The manifest records both
the project `NOTICE` hash and the staged license hash. `build_runtime_receipt`
fills the native receipt; `validate_native_runtime` then checks it. A
candidate path is not one of the two trusted runtime directories, so an
`untrusted_runtime` result is recorded only after the byte checks pass. Any
other validator error refuses the publish and leaves an ambiguous directory
in place.

Existing candidate directories are replaced only when every entry is on that
directory's allowlist. The replacement is a sibling staging directory and a
rename. Unexpected names are not deleted.

The frozen spec packages RLBot core, licenses, the app, the worker, the
package sources, and the three candidate runtime directories. It does not
package the CMake trees, test executables, host probe, BakkesMod SDK, or
`NOTICE` under the wrong filename. Work files go to
`build/native-candidate/pyinstaller`.

## Smoke

```text
python scripts/smoke_native_candidate.py
```

This checks the candidate manifest, allowlists, and AMD64 PE images, then
calls `smoke_package.run_smoke` in an offscreen copy with an isolated data
directory. The helper is not started. The receipt is
`build/native-menu-candidate-smoke-receipt.json`.

## Checks still open

No Rocket League process is launched here, so there is no live evidence for
file-view redirection, menu visibility, BakkesMod load, or match play. A
passing candidate build, a matching hash, and a frozen self-test do not close
that gap. The installer remains held. Publish the normal release only from
`scripts/build_plugin.py`, `packaging/my-career-training.spec`, and
`scripts/package_release.py`.

## Root commands

Stage the menu runtime and RLBot core first. Then:

```text
python scripts/build_native_candidate.py
python scripts/build_native_candidate.py --freeze
python scripts/smoke_native_candidate.py --bundle build/native-candidate/dist/MyCareerTrainingNativeCandidate
```

Do not point those commands at `build/plugin` or the release spec.
