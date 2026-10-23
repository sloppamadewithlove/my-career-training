# My Career Training

**Status: the published v0.2.0 Windows preview has owner-reported launch and
menu failures. A replacement installer is on hold while source repairs are in
progress and the native-menu direction is verified. There is no public-ready
replacement build yet.**

## What the owner reported

In the Windows Steam test of v0.2.0, the owner reported that a Career
fixture and **Start Practice** did not start. The game showed **“Could not
publish the local career command”** and **“Starting career, waiting for Rocket
League to start the offline season.”** They also reported that the My Career
menu repeatedly reopened and the original Rocket League menu glitched over it.
A Windows **Access is denied** error was reported under local AppData. The
complete error path has not been captured, so its exact filename is unverified.

These are observed owner reports, not a completed diagnosis. Windows packaging
and automated tests do not override the failed live-game experience. Source
repairs are underway; the old installer remains available only as the previous
known-issues preview.

## Repository and previous preview

[Open the GitHub repository](https://github.com/sloppamadewithlove/my-career-training) ·
[Archived v0.2.0 release and downloads (known issues)](https://github.com/sloppamadewithlove/my-career-training/releases/tag/v0.2.0) ·
[Release notes](docs/RELEASE_NOTES.md) ·
[Player guide and current status](docs/IN_GAME_PLAYER_GUIDE.md)

The archived v0.2.0 setup and portable files are still downloadable for
reference or controlled reproduction. They are not a repaired build, and a
replacement installer is not ready to test.

## BakkesMod requirement

The v0.2.0 preview requires BakkesMod to be installed and running separately.
BakkesMod is a third-party plugin framework that this preview uses to load its
in-game interface; it is not included in the My Career Training download. The
player must install it from the [official BakkesMod site](https://bakkesmod.com/)
before using the old preview. The repaired source includes a guided download of
the verified official setup, followed by the player's normal Windows installation
steps. It is not included in the published v0.2.0 download. BakkesMod binaries
and community plugins are not bundled.

## Intended experience

The owner wants a solo offline My Career mode that becomes part of Rocket
League's menu flow, while preserving the original Steam game and saves. The
v0.2.0 interface is a plugin overlay; native Rocket League menu replacement has
not been demonstrated. That gap is a release blocker for the intended direction,
not a completed feature.

The simplified design direction has five main destinations: **Career** (with
Squad, Schedule, and League Table views), **Training**, **Garage**, **Workshop**,
and **Settings**. This is the planned information layout, not a claim that the
current build works. The long-term goal remains a coherent native
offline menu, with only verified game capabilities exposed.

## Project links

- [Known-issues v0.2.0 release](https://github.com/sloppamadewithlove/my-career-training/releases/tag/v0.2.0)
- [Current acceptance record](docs/IN_GAME_ACCEPTANCE.md)
- [Native menu investigation and release gate](docs/NATIVE_MENU_RESEARCH.md)
- [Read-only developer probe](docs/NATIVE_MENU_PROBE.md)
- [Design-engineer handoff](docs/OPUS_DESIGN_BRIEF.md) — a brief for Opus 5.5; it does not claim Opus has reviewed the project.
- [Bot providers and attribution](docs/BOT_PROVIDERS.md)
- [Workshop library](docs/WORKSHOP_LIBRARY.md)
- [Plugin capabilities and build](plugin/README.md)
- [Rebuild architecture](docs/IN_GAME_REBUILD.md)

The repo is canonical. A [Cursor Origin mirror](https://origin.cursor.com/sloppamadewithlove/my-career-training.git)
is also configured. Project code is MIT-licensed; third-party licenses and
attribution are listed in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
Rocket League assets, account inventory, BakkesMod, and community plugins are
not redistributed by this repository.

## Older desktop preview

The [v0.1.0 desktop preview](https://github.com/sloppamadewithlove/my-career-training/releases/tag/v0.1.0)
is retained separately. It is not the intended in-game menu experience.
