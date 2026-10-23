# My Career Training

**[Download the Windows in-game preview](https://github.com/sloppamadewithlove/my-career-training/releases/download/v0.2.0/MyCareerTraining-0.2.0-windows-x64-setup.exe)** · [Portable ZIP](https://github.com/sloppamadewithlove/my-career-training/releases/download/v0.2.0/MyCareerTraining-0.2.0-windows-x64-portable.zip) · [Release and checksums](https://github.com/sloppamadewithlove/my-career-training/releases/tag/v0.2.0)

An offline career and training interface inside Rocket League. **0.2.0 is an unsigned Windows Steam testing preview**, requiring your installed game and [BakkesMod](https://bakkesmod.com/). It has no online matchmaking flow. Epic launch is not supported by this build.

Close Rocket League, keep Steam and BakkesMod open, install the app, then use the **My Career Training** shortcut. It installs our plugin and launches an owned offline game. Existing saves remain in `%LOCALAPPDATA%/MyCareerTraining`. No Python, Git, Cursor or AI subscription is needed.

[Setup and player guide](docs/IN_GAME_PLAYER_GUIDE.md) · [Website](https://my-career-training.vercel.app/)

## In this preview

- Career, Squad, Schedule, Season, Training, Workshop, Garage and Settings in a full-screen in-game menu.
- Local seasons, standings, durable results, between-match lineup changes, custom club names and active career-side locking.
- Actual Necto and Nexto CPU policies for 1v1–3v3, with their original licenses. Their historical Diamond/GC1 estimates are not current rank certifications. Ground specialists support 4v4.
- A PlayStation graphic for observed logical actions, configurable labels and placement, and personal/imported ghost playback with watch, lead, slow motion, seek and loop controls.
- An expanded attributed Workshop browser, local Steam map discovery, favorites and controlled map loading/recovery.
- Installed cosmetic browsing and the supported BakkesMod local visual override categories.

## Verification and remaining work

Published installers require successful Windows tests, native DLL compilation/export checks, frozen model inference, Unicode-path checks and install/upgrade/uninstall checks. The release's `RELEASE_RECEIPT.json` identifies the exact compiled source and artifacts. These checks do not prove gameplay.

**Full V1 is incomplete.** This new in-game build still needs a real Steam game test. The custom screen covers native menus; it does not replace the game's menu files. No validated expert ghost is bundled. Ghost camera spectating, guaranteed inactivity protection, unrestricted garage/body/profile customization and Epic bootstrap remain unfinished. Learned bots do not learn from your training sessions.

- [Game acceptance checklist](docs/IN_GAME_ACCEPTANCE.md)
- [Bot providers and attribution](docs/BOT_PROVIDERS.md)
- [Workshop library](docs/WORKSHOP_LIBRARY.md)
- [Plugin capabilities and build](plugin/README.md)
- [Rebuild architecture](docs/IN_GAME_REBUILD.md) and [release notes](docs/RELEASE_NOTES.md)
- [Original assignment](docs/BUILD_SPEC.md)

## Earlier desktop preview

[0.1.0 installer](https://github.com/sloppamadewithlove/my-career-training/releases/download/v0.1.0/MyCareerTraining-0.1.0-windows-x64-setup.exe) · [0.1.0 portable ZIP](https://github.com/sloppamadewithlove/my-career-training/releases/download/v0.1.0/MyCareerTraining-0.1.0-windows-x64-portable.zip) · [Legacy guide](docs/PLAYER_GUIDE.md)

The earlier preview used a separate desktop interface. The owner reported playing a Steam match and identified the interface, bot and training issues that prompted this rebuild; those observations do not validate the new plugin.

GitHub is canonical. The connected [Cursor Origin mirror](https://origin.cursor.com/sloppamadewithlove/my-career-training.git) carries the development branch too. Original code/artwork is [MIT-licensed](LICENSE); [third-party notices](THIRD_PARTY_NOTICES.md) cover the separately licensed models and dependencies. Rocket League assets, account inventory and community maps are not redistributed.
