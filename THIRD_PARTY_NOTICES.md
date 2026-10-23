# Third-party notices

The MIT license at the repository root covers original project code and original
app artwork. It does not license Rocket League, Steam, Epic Games, Qt, RLBot,
community maps, optional community bots, or other third-party material.

Rocket League and its installed assets remain separate prerequisites. This
project does not redistribute the game, extracted game assets, account items,
platform sessions, or community maps. Names identify compatible products; no
endorsement or affiliation is implied.

## Bundled software

| Component | Version / license | Source |
|---|---|---|
| RLBot core | v5.0.0-rc18, MIT, copyright 2024 RLBot Contributors | https://github.com/RLBot/core/tree/v5.0.0-rc18 |
| RLBot Python interface | 2.0.0b56, MIT | https://github.com/RLBot/python-interface |
| RLBot FlatBuffers schema bindings | 0.19.0; see installed distribution notices | https://github.com/RLBot/flatbuffers-schema |
| Qt for Python / PySide6-Essentials / Shiboken6 | 6.12.0; LGPLv3/GPL/commercial alternatives, module-specific terms | https://code.qt.io/pyside/pyside-setup.git/tag/?h=v6.12.0 |
| Qt libraries | 6.12.0; module-specific LGPLv3/GPL/BSD/third-party terms | https://download.qt.io/official_releases/qt/6.12/6.12.0/submodules/ |
| Python | 3.12.13, PSF license and incorporated software notices | https://www.python.org/downloads/release/python-31213/ |
| pygame-ce / SDL | pygame-ce 2.5.6, LGPLv2.1-or-later; SDL and incorporated library notices | https://github.com/pygame-community/pygame-ce |
| psutil | 7.2.2, BSD-3-Clause | https://github.com/giampaolo/psutil |
| PyInstaller bootloader | 6.22.3, GPLv2-or-later with distribution exception | https://pyinstaller.org/en/stable/license.html |

The build collects the actual installed distribution license/copyright files
into `_internal/licenses/` and includes a dependency manifest with exact versions.
The release also includes a `third-party-sources.zip` with immutable-commit Qt,
PySide and pygame source archives, their checksums and upstream URLs.
That manifest and the retained full texts govern incorporated dependencies;
this short table is an index. The exact core MIT copyright and permission text
is included as `_internal/licenses/RLBot-core-LICENSE.txt`.

Qt and pygame libraries are dynamically packaged in an onedir distribution.
Users may inspect, debug, and replace compatible LGPL libraries for their own
use, including debugging modifications to those libraries. This project's
license adds no restriction on reverse engineering for that purpose. Keep the
library files and license material when redistributing the binary package.
Corresponding upstream source is available at the versioned links above and
upstream release tags; rebuild instructions are in `docs/BUILDING.md`. Do not
replace or remove upstream notices or apply the app MIT license to those files.

No optional third-party learned bot weights are included in the base package.
Add providers only after reviewing their source and model-weight permissions.
Community content remains attributed external content; downloading it through
its creator is separate from licensing the app.

## Build tools

Inno Setup 6.7.3 is downloaded by CI with a pinned SHA-256. Its compiler is a
build tool, not copied into the app. Installer technology remains subject to
Inno Setup's license: https://github.com/jrsoftware/issrc/tree/is-6_7_3.
Inno Setup's current commercial-use terms require review before commercial
distribution; this public community testing release is not a commercial license
purchase or a claim to possess one.
