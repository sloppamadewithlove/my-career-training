# My Career Training

## Download for Windows

**[Download Windows installer (.exe · 50 MB)](https://github.com/sloppamadewithlove/my-career-training/releases/download/v0.1.0/MyCareerTraining-0.1.0-windows-x64-setup.exe)**

[Portable ZIP · 78 MB](https://github.com/sloppamadewithlove/my-career-training/releases/download/v0.1.0/MyCareerTraining-0.1.0-windows-x64-portable.zip)
 · [Setup guide](docs/PLAYER_GUIDE.md)
 · [All downloads and checksums](https://github.com/sloppamadewithlove/my-career-training/releases/tag/v0.1.0)

Close Rocket League, run the installer, then choose Steam or Epic and your game
location in **Settings**. Try the optional calibration match first. The current
download is the unsigned **0.1.0 Windows x64 testing preview**.

A local Windows career and practice companion for your installed **Rocket League**.
Drive your own car, recruit four specialist bots, play a short Soccar season, and
choose optional lessons including speed flips and flip resets.

**0.1.0 is a testing prerelease. Full V1 is incomplete.** The application and
integration are implemented in source, but no real Rocket League session has
been verified for this app on Steam or Epic. Validated expert teaching recordings
are still missing. The original specialist bots are experimental and unranked;
there is no Diamond-strength guarantee.

## Try it on Windows

Use the installer linked above, or extract the entire portable ZIP and open
**MyCareerTraining.exe**. Keep its worker and `_internal` folder beside it.

Follow the [player guide](docs/PLAYER_GUIDE.md) for installation, first setup,
career matches, lessons, backups and Play Online. You need Windows x64, your own
current Rocket League installation, and an existing signed-in Steam or Epic
session. The packaged app needs no Python, Git, Cursor or AI subscription.

Career matches use the supported **EAC-off offline environment**. Official online
play uses the platform's normal **EAC-enabled** entry. The app never asks for your
Steam/Epic password. macOS source/UI checks do not provide Mac gameplay support.

## What's here

- One human captain and four persistent recruits, with 1v1–4v4 formats and
  between-match lineup changes.
- Four-club, six-round seasons, standings, seeded simulated rival fixtures,
  title playoffs when needed, progression and continued careers.
- Eight optional training groups, reset/retry, measured observations, personal
  recordings, wireframe ghost playback and independent help preferences.
- A local bot garage, creator/map links, validated local map import, accessibility
  settings, backups and diagnostics.
- A separate game worker, durable match-result receipts, and an ordered save,
  close and normal-launch Play Online transition.
- Optional match review with timestamped observations and clearly labeled
  positioning suggestions, saved alongside the result.

Features above describe source implementation. Actual game behavior, lesson
accuracy, controller operation and Steam/Epic handoff still need independent
Windows tests. Community map import does not establish a working game loader;
Epic map loading is unavailable. Local rewards never grant account inventory.

## Evidence and development

- [Feature evidence matrix](docs/FEATURE_MATRIX.md)
- [Compatibility and integration findings](docs/COMPATIBILITY.md)
- [Release notes](docs/RELEASE_NOTES.md)
- [Architecture](docs/ARCHITECTURE.md) and [build instructions](docs/BUILDING.md)
- [Future two-captain investigation](docs/MULTIPLAYER.md)
- [Complete assignment](docs/BUILD_SPEC.md)

GitHub is canonical. The Cursor Origin mirror is
[sloppamadewithlove/my-career-training](https://origin.cursor.com/sloppamadewithlove/my-career-training.git).
Its HEAD was verified at repository setup; continuing mirror synchronization
must be checked for the release commit. See [repository setup](docs/REPOSITORY_SETUP.md).

Original project code/artwork is [MIT-licensed](LICENSE). Read
[third-party notices](THIRD_PARTY_NOTICES.md) for Qt, RLBot and other dependencies.
Rocket League and community content have their own owners and permissions.
