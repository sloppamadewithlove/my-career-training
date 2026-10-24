# My Career Training

A solo career and training mod for **Rocket League on Windows / Steam**.
The goal is a desktop shortcut that starts offline Rocket League with Career,
Training, Garage, Workshop and Settings in the game's own menu style.
Squad, Schedule and League Table belong inside Career.

**The native-menu edition is not available to download yet.** The current
implementation uses an in-game plugin window. Replacing Rocket League's native
buttons and their actions is still under investigation. The next public
installer is held until that integration is verified.

[Project website](https://my-career-training.vercel.app/) ·
[Current development status](docs/RELEASE_NOTES.md) ·
[Native menu investigation](docs/NATIVE_MENU_RESEARCH.md)

The [native-menu implementation plan](docs/NATIVE_MENU_IMPLEMENTATION_PLAN.md)
maps candidate Rocket League menu classes, compares proven techniques in
other games, and defines the tests needed to replace native controls while
preserving the normal Steam installation. This is a researched design, not a
claim that the native-menu edition already works.

## What is implemented, and what remains unverified

The source includes career seasons and lineups, local bot providers, training
lessons, recorded ghost playback, a PlayStation-style action display, a workshop
library, and local cosmetic controls. These are implementation details, not a
claim that every feature works in the player's game.

Earlier repairs fix Windows bridge file-sharing conflicts, replace
repeated menu-open requests with transition-based navigation, simplify the
interface, and add guided setup for the official BakkesMod installer. Windows
source, plugin and frozen-application checks passed for
[PR #2](https://github.com/sloppamadewithlove/my-career-training/pull/2).
Installer creation and upload were deliberately skipped in that run. The 0.3.0
workflow also builds and checks installation, same-version reinstall and
uninstallation while keeping downloadable artifacts on hold. These automated
checks do not verify gameplay, older-version upgrades or native menu replacement.

A supported [native dialog trial](docs/NATIVE_DIALOG_TRIAL.md) now routes Career
and Training buttons through Rocket League dialogs. It is opt-in development
code: it does not replace the full menu, disable stock buttons, or prove
controller and Back/Escape behavior. The installer hold remains in place.

The 0.3.0 source journals temporary BakkesMod plugin setup and restores the
previous files after the game closes. Interrupted sessions keep a recovery
record; conflicting user changes are preserved. The old custom-map substitution
route is disabled because it writes an installed Rocket League map. Workshop
browsing and favorites remain available.

A read-only [menu diagnostic](docs/NATIVE_MENU_PROBE.md) supports investigation
on the player's installed Steam build. It does not edit game memory, replace
menus, or certify compatibility. Native button ownership, click routing,
controller navigation and restoration still need real Windows game evidence.

The development [community plugin library](docs/COMMUNITY_PLUGINS.md) can check
creator releases and download packages into a private cache. Downloads are not
enabled in the game: isolated third-party loading remains unverified. The
[Windows baseline helper](docs/WINDOWS_VALIDATION.md) collects a sanitized game
identity report without launching or changing Steam, Rocket League or BakkesMod.

## Setup direction

BakkesMod is the third-party framework targeted by the current in-game plugin.
Its official [RL2.78/BM229 compatibility release](https://github.com/bakkesmodorg/BakkesModInjectorCpp/releases/tag/2.0.78)
was published on 20 October 2026. Loading this project's plugin on the player's
exact current build still needs verification.
The repaired source offers a guided download of its verified official installer,
followed by the normal Windows installation steps when it is missing. We do not
bundle BakkesMod or install unrelated community plugins. See
[the official BakkesMod site](https://bakkesmod.com/).

The native-menu design must preserve the original Steam installation and saves,
use the player's installed game assets, and run only in an owned offline
session. This repository does not redistribute Rocket League assets or grant
online inventory items. Native integration must refuse an unverified game update
before making any changes.

## Development and evidence

- [Player guide and known issues](docs/IN_GAME_PLAYER_GUIDE.md)
- [Acceptance record](docs/IN_GAME_ACCEPTANCE.md)
- [Native menu investigation and release gate](docs/NATIVE_MENU_RESEARCH.md)
- [Native implementation plan](docs/NATIVE_MENU_IMPLEMENTATION_PLAN.md) and [cross-game precedents](docs/research/NATIVE_MENU_PRECEDENTS.md)
- [Runtime adapter follow-up](docs/research/NATIVE_RUNTIME_ADAPTERS.md)
- [Read-only menu diagnostic](docs/NATIVE_MENU_PROBE.md)
- [Windows Codex handoff and read-only game-file comparison](docs/WINDOWS_CODEX_HANDOFF.md)
- [Design-engineer handoff for Opus 5.5](docs/OPUS_DESIGN_BRIEF.md) — a brief; no completed Opus review is claimed.
- [Bot providers](docs/BOT_PROVIDERS.md) and [workshop library](docs/WORKSHOP_LIBRARY.md)
- [Plugin capabilities and build](plugin/README.md)

GitHub is canonical. The [Cursor Origin mirror](https://origin.cursor.com/sloppamadewithlove/my-career-training.git)
is configured. Project code is MIT-licensed; third-party attribution is in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Historical previews and their
known failures remain documented in the release history; they are not the
requested native-menu edition.
