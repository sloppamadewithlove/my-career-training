# Build and package

This is a 0.1.0 testing prerelease. A built package is not proof of Rocket League
runtime compatibility, lesson accuracy, or completed V1 acceptance. Keep Steam
and Epic game-test evidence separate.

## Development

Use Python **3.12.13**, uv **0.11.3**, and the committed `uv.lock`:

```sh
uv sync --frozen --all-groups
uv run --frozen ruff check src tests scripts packaging
uv run --frozen pytest -q
uv run --frozen python -m my_career_training --self-test
uv run --frozen python -m my_career_training
```

macOS can exercise the domain and UI. RLBot is a Windows-only dependency in the
project lock. Building a Windows executable requires Windows; PyInstaller does
not cross-compile it on a Mac. The GitHub workflow uses Windows Server 2025 x64
and Python 3.12.13. `windows-2025` pins the OS generation, not the continuously
maintained runner image; CI records the actual runner version in its logs.
Actions are pinned to immutable commits; dependency versions and hashes are in
the lock. Reproducible here means a repeatable version-controlled build recipe,
not a claim of bit-for-bit identical signed installers.

## Windows artifacts

```powershell
uv sync --frozen --all-groups
uv run --frozen python scripts/fetch_runtime.py
uv run --frozen python scripts/collect_licenses.py
uv run --frozen pyinstaller --noconfirm --clean packaging/my-career-training.spec
uv run --frozen python scripts/smoke_package.py
& 'C:\path\to\Inno Setup 6\ISCC.exe' /DAppVersion=0.1.0 packaging/installer.iss
uv run --frozen python scripts/test_installer.py release/MyCareerTraining-0.1.0-windows-x64-setup.exe
uv run --frozen python scripts/package_release.py
```

The workflow downloads Inno Setup **6.7.3** from its official GitHub release,
verifies SHA-256
`9c73c3bae7ed48d44112a0f48e66742c00090bdb5bef71d9d3c056c66e97b732`,
and installs it only on the disposable build runner. A local Windows developer
may install that compiler normally. No Python, Git, Cursor, uv, compiler, or
terminal is required by the packaged player application.

`fetch_runtime.py` only downloads RLBot core **v5.0.0-rc18**, validates its PE
header and SHA-256
`454986c71bacebfcb923a8eeddba7ea62ecc6c42d28b4cab89f653e2eab1ccd1`,
then places it under `runtime/`. That generated binary is never committed.
The core is MIT-licensed and its full license is retained. Updating it requires
reviewing the release, new hash, interface compatibility, and actual game tests.

The bundle contains a windowless `MyCareerTraining.exe` and a console-mode
`MyCareerTrainingWorker.exe`. The UI starts the latter with piped stdin/stdout
and Windows `CREATE_NO_WINDOW`. This preserves the worker JSON-lines protocol;
a windowless executable alone does not provide usable standard streams.
The source worker remains `python -m my_career_training --worker`.
Read-only QML/icons and runtime are beneath the bundled package; state remains
in per-user AppData. The worker executable is never used as a Python interpreter.

Package checks load QML offscreen, run headless package contracts, exchange real
JSON-line ping/shutdown messages with the frozen worker, verify the bundled core
hash, and run from paths containing spaces and non-ASCII characters. The
installer check installs, loads the package, repeats installation, and uninstalls
while preserving a separate existing-save sentinel. These do not start Rocket
League or establish controller navigation and physical game behavior.

Outputs in `release/`:
- `MyCareerTraining-0.1.0-windows-x64-setup.exe`
- `MyCareerTraining-0.1.0-windows-x64-portable.zip`
- `MyCareerTraining-0.1.0-third-party-sources.zip` (corresponding upstream sources)
- `SHA256SUMS.txt`

Installer defaults to the current user's local Programs directory, provides a
Start menu shortcut and optional desktop shortcut, and requests no administrator
rights. It preserves AppData saves on upgrade and uninstall. The portable ZIP
contains the same runtime and also keeps player data outside the extracted app.
Windows ARM and 32-bit systems are excluded until independently supported.

The workflow uploads actual artifacts, but does not publish a release or assert
game compatibility. Release maintainers download the successful job's artifacts,
verify checksums, attach exact outputs to the versioned GitHub release, and
include test limitations and release notes. These builds are **unsigned** unless
an actual configured signing step and verified signature are documented. Do not
recommend disabling Windows protection to install them.

## Dependency source and licensing

Read `THIRD_PARTY_NOTICES.md` and `_internal/licenses/` in the built package.
The build retains installed upstream license files and dependency metadata.
Because some wheels omit standalone license files, it additionally obtains
immutable-commit Qt, PySide and pygame source archives, extracts upstream license
and attribution material, and includes the original archives in a separate
source ZIP. Publish that source ZIP alongside the binary packages; it is not
bundled into the installer. Its manifest records exact source URLs and SHA-256s.
Qt/PySide libraries stay dynamically replaceable. Matching Qt source is at
https://download.qt.io/official_releases/qt/6.12/6.12.0/submodules/ and PySide source
at https://code.qt.io/pyside/pyside-setup.git/tag/?h=v6.12.0. Rebuild this application
with the same lock using the commands above; rebuilding modified Qt/PySide
itself follows https://doc.qt.io/qtforpython-6/building_from_source/index.html.
Do not redistribute game assets, credentials, personal saves, private recordings,
or third-party map/model content without its own permission.
