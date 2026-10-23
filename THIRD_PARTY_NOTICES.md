# Third-party notices

The MIT license at the repository root covers original project code and app
artwork, including the My Career Training plugin. It does not relicense the
third-party software, source, or model weights below. Rocket League, Steam,
Epic Games, BakkesMod, community maps, and player recordings remain separate
products or materials with their own owners and permissions.

Rocket League is a required, separately installed game. This project does not
redistribute the game, extracted game assets, account items, credentials, or
platform sessions. Product and platform names are used for identification; no
endorsement or affiliation is implied.

## In-game plugin components

| Component | Version / license | Source and retained notice |
|---|---|---|
| My Career Training plugin | Project code: MIT | Root [LICENSE](LICENSE) |
| Dear ImGui | 1.75, MIT; BakkesMod-ABI-matched source | [`plugin/licenses/imgui-LICENSE.txt`](plugin/licenses/imgui-LICENSE.txt); source is retained separately from the SDK archive |
| nlohmann/json | 3.12.0, MIT | [`plugin/licenses/json-LICENSE.MIT`](plugin/licenses/json-LICENSE.MIT); [pinned upstream source](https://github.com/nlohmann/json/tree/v3.12.0) |
| BakkesMod SDK | Build-time dependency only; pinned commit `479e8f571cf554b25f4eeb64d611dec4133edcaf`, archive SHA-256 `e4072d2884a432bedfd7a7e8474000137b1649deeea3346de4f1b2a0cb9dd866` | [Pinned SDK source](https://github.com/bakkesmodorg/BakkesModSDK/tree/479e8f571cf554b25f4eeb64d611dec4133edcaf). The pinned repository has no `LICENSE` file, so this project makes no license claim for the SDK. Its source archive and the BakkesMod runtime/injector are not included in the product or third-party source bundle. Install BakkesMod separately and follow its applicable terms. |

The plugin requires the separately installed BakkesMod host. The build fetches
the pinned SDK to compile against its API; the dependency URL, commit and archive
hash are kept in [`plugin/DEPENDENCIES.json`](plugin/DEPENDENCIES.json) and in
the plugin build receipt. The SDK's ABI-matched ImGui source has its own MIT
notice above; it is not covered by an assumed SDK license.

## Learned bot models and runtime

The 0.2 Windows implementation includes the original Necto and Nexto TorchScript
weights and adapted observation/action code from Rolv-Arild's Necto repository,
revision `2e6ed7d6ed2b352e8ff529d4a12a0c9c70c28cca`. The work is attributed to
Rolv-Arild and the RLGym/Necto contributors. This separate component is licensed
under **Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International
(CC BY-NC-SA 4.0)**. The license does not grant commercial permission. The full
license and attribution notice are retained at
[`src/my_career_training/bots/resources/LICENSE-Necto.txt`](src/my_career_training/bots/resources/LICENSE-Necto.txt)
and [`src/my_career_training/bots/_vendor/NOTICE`](src/my_career_training/bots/_vendor/NOTICE).
The model checksums and usage limits are recorded in
[`docs/BOT_PROVIDERS.md`](docs/BOT_PROVIDERS.md).

| Bundled Windows runtime | Version / license | Source |
|---|---|---|
| PyTorch CPU | 2.6.0, BSD 3-Clause license and bundled-component notices | [Versioned upstream license](https://github.com/pytorch/pytorch/blob/v2.6.0/LICENSE) |
| NumPy | 2.1.3, BSD 3-Clause | [Versioned upstream license](https://github.com/numpy/numpy/blob/v2.1.3/LICENSE.txt) |

Torch and NumPy are pinned as Windows dependencies and inference is configured
for CPU. The package does not need a GPU for these providers. Their exact wheel
notices and dependency manifests must be retained in the generated package;
these runtimes do not change the Necto/Nexto model license.

## Other packaged software

| Component | Version / license | Source |
|---|---|---|
| RLBot core | v5.0.0-rc18, MIT, copyright 2024 RLBot Contributors | [Pinned source](https://github.com/RLBot/core/tree/v5.0.0-rc18) |
| RLBot Python interface | 2.0.0b56, MIT | [Upstream repository](https://github.com/RLBot/python-interface) |
| RLBot FlatBuffers schema bindings | 0.19.0; retain installed distribution notices | [Upstream repository](https://github.com/RLBot/flatbuffers-schema) |
| Qt for Python / PySide6-Essentials / Shiboken6 | 6.12.0; LGPLv3/GPL/commercial alternatives and module-specific terms | [Pinned PySide source](https://code.qt.io/pyside/pyside-setup.git/tag/?h=v6.12.0) |
| Qt libraries | 6.12.0; module-specific LGPLv3/GPL/BSD and third-party terms | [Qt 6.12.0 source submodules](https://download.qt.io/official_releases/qt/6.12/6.12.0/submodules/) |
| Python | 3.12.13, PSF license and incorporated software notices | [Python release](https://www.python.org/downloads/release/python-31213/) |
| pygame-ce / SDL | pygame-ce 2.5.6, LGPLv2.1-or-later; SDL and incorporated library notices | [pygame-ce source](https://github.com/pygame-community/pygame-ce) |
| psutil | 7.2.2, BSD-3-Clause | [Upstream repository](https://github.com/giampaolo/psutil) |
| PyInstaller bootloader | 6.22.3, GPLv2-or-later with distribution exception | [PyInstaller license](https://pyinstaller.org/en/stable/license.html) |

The Windows packaging workflow collects installed-distribution license files,
dependency metadata, and version-pinned Qt, PySide and pygame source notices.
Check the actual `_internal/licenses/` directory and source manifest in each
release package; a local or CI source pass is not proof that a particular
artifact contains the required notices. Dynamically packaged LGPL libraries
remain replaceable for users' own use, including debugging modifications to
those libraries. This project's license adds no restriction on reverse
engineering for that purpose. Keep the library files and upstream notices when
redistributing the binary package.

The plugin build also retains license text for Dear ImGui and nlohmann/json.
The planned third-party source bundle does not include BakkesMod SDK sources;
its pinned fetch identity is provided for build reproducibility only. Do not
remove upstream notices or apply the app MIT license to third-party material.

## Build tools

Inno Setup 6.7.3 is downloaded by CI with a pinned SHA-256. Its compiler is a
build tool, not copied into the app. Installer technology remains subject to
[Inno Setup's license](https://github.com/jrsoftware/issrc/tree/is-6_7_3).
Review Inno Setup's commercial-use terms before commercial distribution; this
community testing preview is not a commercial license purchase or a claim to
possess one.
