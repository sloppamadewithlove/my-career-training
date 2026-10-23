# My Career Training

## Current public download: 0.1.0 desktop preview

The public Windows download is still **0.1.0**. These links are unchanged; they
install the earlier desktop-interface preview, not the new in-game interface.
There is no 0.2 installer linked until its Windows package checks pass.

**[Download the Windows installer (.exe · 50 MB)](https://github.com/sloppamadewithlove/my-career-training/releases/download/v0.1.0/MyCareerTraining-0.1.0-windows-x64-setup.exe)**

[Portable ZIP · 78 MB](https://github.com/sloppamadewithlove/my-career-training/releases/download/v0.1.0/MyCareerTraining-0.1.0-windows-x64-portable.zip)
 · [0.1 setup guide](docs/PLAYER_GUIDE.md)
 · [0.1 release and checksums](https://github.com/sloppamadewithlove/my-career-training/releases/tag/v0.1.0)

The 0.1.0 download is an unsigned Windows x64 testing preview. It needs your
own Rocket League installation and signed-in Steam or Epic account. It does not
need Python, Git, Cursor, or an AI subscription. Full V1 is incomplete, and no
real Rocket League session has been verified for this app on Steam or Epic.

## 0.2 in-game rebuild — implementation and testing in progress

The 0.2 development work is rebuilding the experience around an in-game My Career
interface. The current target is Windows x64, Steam Rocket League, and a
separately installed BakkesMod. It starts the game in its supported offline,
EAC-off mode. This preview has no online matchmaking flow, and Epic launch is
not supported by the in-game bootstrap. These are source-level targets; a
successful Windows build and live-game test are still separate acceptance gates.

The 0.2 build is **not yet the public download above**. Use the 0.2 documents
for its intended setup and acceptance checks; they do not describe the 0.1
installer:

- [In-game player guide](docs/IN_GAME_PLAYER_GUIDE.md)
- [In-game Windows and game acceptance record](docs/IN_GAME_ACCEPTANCE.md)
- [In-game rebuild notes](docs/IN_GAME_REBUILD.md)

Full V1 remains incomplete until the Windows package, actual Steam game session,
and outstanding launcher/provider/reference requirements are verified. A source
test or successful package build is not proof of gameplay.

## Legacy 0.1 desktop preview

The current public 0.1 app is a separate desktop UI. Its source includes a local
career with one human captain and four recruits, 1v1–4v4 formats, seasons,
standings, simulated rival fixtures, progression, training lessons, personal
recordings and ghost playback. It also includes local bot presets, creator/map
references, settings, backups, diagnostics, and an ordered save/close/normal
launch flow for returning to online play.

Those are 0.1 source features, not proof of behavior in a real Rocket League
session. The specialist bots are experimental and unranked; learned bot weights
and the new in-game plugin are part of the 0.2 development work. Map-file import
does not establish that a map can load in the game. Local rewards do not grant
account inventory. See the [0.1 player guide](docs/PLAYER_GUIDE.md) for that
preview's own requirements and limitations.

## Project and evidence

- [Feature evidence matrix](docs/FEATURE_MATRIX.md)
- [Compatibility and integration findings](docs/COMPATIBILITY.md)
- [Release notes](docs/RELEASE_NOTES.md)
- [Architecture](docs/ARCHITECTURE.md) and [build instructions](docs/BUILDING.md)
- [Bot providers and model attribution](docs/BOT_PROVIDERS.md)
- [Future two-captain investigation](docs/MULTIPLAYER.md)
- [Complete assignment](docs/BUILD_SPEC.md)

GitHub is canonical. The Cursor Origin mirror is
[sloppamadewithlove/my-career-training](https://origin.cursor.com/sloppamadewithlove/my-career-training.git).
Its HEAD was verified at repository setup; synchronization must be checked for
the release commit. See [repository setup](docs/REPOSITORY_SETUP.md).

Original project code and app artwork are [MIT-licensed](LICENSE), subject to
the separate third-party terms in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
Rocket League, BakkesMod, platform software, and community content remain their
owners' separate products and materials.
