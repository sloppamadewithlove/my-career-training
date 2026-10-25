# Build and verify the Windows native candidate

Read [PROJECT_STATUS.md](PROJECT_STATUS.md) first. The published 24 October ZIP
failed live startup. A successful build does not mean that failure is fixed.

## Development environment

Windows x64, Python **3.12.13**, uv **0.11.3**, Visual Studio 2022 Build Tools
with C++ desktop tools, and CMake 3.24 or newer. Use a short checkout path
(for example `C:\\work\\my-career-training`): MSVC can reject deeply nested SDK
include paths even when Python supports long paths.

```powershell
uv sync --python 3.12.13 --frozen --all-groups
uv run --frozen ruff check src tests scripts packaging
uv run --frozen pytest -q
```

Tests use temporary fixtures and do not start Rocket League. A process-probe test
must explicitly mock its process state, so an open real game cannot affect it.
macOS can run applicable domain/UI tests; Windows artifacts must be built on Windows.

## Current native bundle

```powershell
uv run --frozen python scripts/fetch_runtime.py
uv run --frozen python scripts/fetch_bot_provider.py
uv run --frozen python scripts/stage_native_runtime.py
uv run --frozen python scripts/build_native_candidate.py
uv run --frozen python scripts/collect_licenses.py
uv run --frozen python scripts/build_native_candidate.py --freeze
uv run --frozen python scripts/smoke_native_candidate.py
```

The first native build stages the plugin source/license evidence before license
collection. The final build enables the native movie trial and disables the host
probe. Output is `build/native-candidate/dist/MyCareerTrainingNativeCandidate/`.
Only `MyCareerTraining.exe` is at the top. The private worker is at
`_internal/MyCareerTrainingWorker.exe`, requires explicit `--worker`, and shares
the support libraries there. Its bootloader hides a console it owns. The app
starts it through QProcess pipes. Smoke checks exchange actual ping/shutdown
messages, load the UI, verify models/runtime hashes, and run from Unicode paths.

The stage fetches only pinned, licensed build dependencies. No installed game,
extracted movie or cooked package is included in the downloadable bundle.
Players do not need developer tools.

## One-file test installer

Use the official Inno Setup **6.7.3** compiler. Its installer SHA-256 is
`9c73c3bae7ed48d44112a0f48e66742c00090bdb5bef71d9d3c056c66e97b732`.
The extracted `ISCC.exe` SHA-256 must be
`0a8757031b33777e4c9cbffee40f11a5062b36d25cbe144c1db73b6102b80ad7`.
For a temporary compiler, its documented `/PORTABLE=1 /CURRENTUSER` mode avoids
a registered installation. See [Inno's notes](https://jrsoftware.org/ishelp/topic_technotes.htm).

Commit reviewed changes, rebuild and rerun the package smoke so the source
commit and artifact receipt match. Then:

```powershell
uv run --frozen python scripts/build_native_installer.py --compiler "C:\\tools\\InnoSetup\\ISCC.exe"
```

Output is `build/native-candidate/installers/MyCareerTraining-Windows-Test-<commit>-Setup.exe`.
It is explicitly a test, uses the native bundle, creates one player shortcut,
removes only the obsolete top-level helper on upgrade, and preserves separate
AppData saves. Missing BakkesMod uses the app's guided official setup; its
runtime is not bundled. No administrator rights are required for My Career.

The installer builder requires a clean source commit, rebuilds the native bundle
with a clean packaging cache, and runs its package smoke check. It compares every
bundled file before and after testing and installer compilation. A unique
output folder ensures an old installer cannot receive a new build receipt. A separate
installer lifecycle test and real game acceptance are
still needed. These executables are unsigned unless a real signing step and
verified signature are recorded.

Inno Setup 6.7.3 is not long-path aware. A script-relative bundle `Source` keeps
a `packaging\..` prefix, so a normalized 247-character license path becomes 260
characters and compression fails with "The system cannot find the path specified"
even though the file exists. Other bundled license paths reach 287 characters.
The builder copies the smoke-verified bundle to an owned temporary directory
(`mct-*/bundle`), passes that absolute path as `/DBundleDir`, and writes the
compiler output to `mct-*/out`. It then copies those new bytes into the unique
staging folder and promotes that file only after the copy, the original bundle,
and the source commit still match. If the temporary directory still cannot hold
every compiler source path and the output file under 260 characters, the build
stops before the compiler starts. Cleanup removes only that temporary copy.
Required licenses stay in the bundle. The stable release remains held.
Gameplay, lifecycle, and production flags stay false.

## Verification and publication

`.github/workflows/native-candidate.yml` builds the native candidate on a clean
GitHub-hosted Windows runner. `scripts/test_native_installer.py` requires that
disposable environment, refuses existing product registrations, checks every
installed payload file, one player shortcut, same-version reinstall, obsolete
Worker cleanup, uninstall and preservation of a separate real-format career.
It retains the exact tested installer and sanitized evidence for live acceptance.
The separate `native-live-acceptance-bundle-<commit>` Actions artifact contains
the exact folder used to create that installer. Before running it on a gaming
PC, compare every extracted file and its SHA-256 with `bundle_files` in the
same run's `native-menu-candidate-smoke-receipt.json`, and reject missing or
extra files. The installer lifecycle already checks its installed payload
against that inventory. Test this bundle in a copied career profile without
replacing an existing registered installation. This is a developer testing
artifact; players receive the single Setup executable.
It does not publish a release or establish gameplay support.

Keep source tests, native fixture tests, frozen package tests, installer
install/reinstall/uninstall checks and live game acceptance separate.
[NATIVE_ACCEPTANCE_SESSION.md](NATIVE_ACCEPTANCE_SESSION.md) defines the game
check. Preserve installed files, player saves and normal launch.

Publish only the exact tested artifacts, checksums, matching project source,
required third-party sources/notices and a sanitized receipt. Review every file
before upload. Never publish game packages, private logs, crash dumps or secrets.

The older `packaging/my-career-training.spec`, `installer.iss` and
`package_release.py` pipeline builds the older interface and must not replace
the native candidate. The registered `.github/workflows/windows.yml` workflow
is the entrypoint wrapper for the reusable
`.github/workflows/native-candidate.yml` workflow. Only tested Actions
artifacts and evidence are retained. These workflows do not publish a GitHub
Release. Publication remains gated on exact-build live acceptance.

## Dependency licensing

See [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md) and the bundle's
`_internal/licenses/`. `collect_licenses.py` retains upstream attributions and
source archives for the exact locked versions. Publish corresponding source
archives alongside binaries. Qt/PySide remain dynamically replaceable.
Local visual overrides do not grant account inventory.
