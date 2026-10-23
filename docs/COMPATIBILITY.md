# Compatibility and evidence

Research checked 22 October 2026. This document records source-level integration evidence, not a successful game session. App 0.1.0 is a testing prerelease; full V1 acceptance requires the independent Steam/Epic checks in the feature matrix and real teaching references.

## Version baseline

| Component | Candidate/build baseline | Evidence and limits |
| --- | --- | --- |
| Application | 0.1.0 | This source tree; record exact commit in each test report |
| Python | 3.12 x64 | Project build target; SDK requires at least 3.11 |
| Desktop | PySide6 6.12.0 | Locked project dependency; packaged Windows validation required |
| Python interface | rlbot 2.0.0b56 | Published v5 prerelease from 2 October 2026 |
| FlatBuffers interface | rlbot-flatbuffers 0.19.0 | SDK requirement; Windows/Linux x64 wheels; no macOS wheel |
| Process inspection | psutil 7.2.2 | Satisfies SDK's 7.x requirement |
| Core | v5.0.0-rc18 | Latest GitHub release checked; published 22 October 2026 |
| Rocket League | Installed version must be measured | Official known-issues page references v2.78 on 20 October; that does not identify the player's executable |
| Specialist provider | Original baseline controller | Experimental; no certified rank claim or universal 4v4 evaluation |
| Steam / Epic | Separate Windows acceptance targets | Documentation supports both; one launcher test never validates the other |
| Native macOS | Management/UI checks only | Current RLBot/game runtime has no native macOS support |

Never install an unqualified `rlbot`: the default stable PyPI release is currently legacy v4 (1.68.0), while the required v5 interface is an explicitly pinned prerelease. Core and interface version numbers differ. Version pins establish reproducibility, not demonstrated game compatibility.

Sources: [published SDK](https://pypi.org/project/rlbot/2.0.0b56/), [SDK dependencies](https://github.com/RLBot/python-interface/blob/master/pyproject.toml), [core releases](https://github.com/RLBot/core/releases/tag/v5.0.0-rc18), [operating-system support](https://wiki.rlbot.org/v5/framework/operating-system-support/), [official game issues/version context](https://www.rocketleague.com/known-issues).

## Exact artifacts

The build must verify these before packaging; the runtime core is an upstream binary, not original app code.

| Artifact | SHA-256 |
| --- | --- |
| rlbot-2.0.0b56-py3-none-any.whl | `d5ca879e4fc0fdeef591413d56d24797a005a8c7af03e734ce2795dde2ffa2df` |
| rlbot_flatbuffers-0.19.0-cp310-abi3-win_amd64.whl | `e9ae909cdcaf259719992eeeb77f96b813f0c20a2a5a9241423376d5f754ee70` |
| RLBotServer.exe v5.0.0-rc18 | `454986c71bacebfcb923a8eeddba7ea62ecc6c42d28b4cab89f653e2eab1ccd1` |

Sources: [PyPI SDK metadata](https://pypi.org/pypi/rlbot/2.0.0b56/json), [PyPI FlatBuffers metadata](https://pypi.org/pypi/rlbot-flatbuffers/0.19.0/json), [core release assets](https://github.com/RLBot/core/releases/tag/v5.0.0-rc18). Run `RLBotServer.exe --version` and record its actual reported core/bridge versions during Windows testing.

## Concrete adapter contract and upstream hazards

The published b56 wheel was inspected directly during the build. `MatchManager` accepts a core executable path, exposes its `rlbot_interface`, starts either a `Path` config or `flat.MatchConfiguration`, and offers connect/run/disconnect/stop/shutdown methods. Start with `wait_for_start=False` and enforce an application timeout: its first-packet wait is otherwise unbounded. Natural match completion must be detected from telemetry, not server exit. SDK shutdown does not establish that Rocket League exited. [Implementation](https://github.com/RLBot/python-interface/blob/master/rlbot/managers/match.py).

The b56 convenience `set_game_state()` methods contain an upstream signature mismatch: they pass a removed fourth `commands` argument to `fill_desired_game_state`, which accepts only balls, cars, and match info. Send the helper's returned state through `rlbot_interface.send_msg()` instead. DesiredCarState supports physics and boost, not fabricated jump-reset or input-release fields. [Helper](https://github.com/RLBot/python-interface/blob/master/rlbot/utils/__init__.py).

Core normalizes player configuration by moving the single human to the last index. Build configurations in that order and verify received identities. Explicitly set relevant configuration defaults. Python's TOML parser does not expose every current schema field; direct FlatBuffer configurations avoid relying on omitted fields. [Core validator](https://github.com/RLBot/core/blob/v5.0.0-rc18/RLBotCS/ManagerTools/ConfigValidator.cs), [SDK parser](https://github.com/RLBot/python-interface/blob/master/rlbot/config.py).

Hivemind convenience fields and relay handler arrays include class-level mutable lists. Use separate subprocesses or explicitly isolate instance state. Core's automatic Hivemind process grouping includes original names, so distinct recruit names need deliberate grouping or manual launch ownership. [SDK Hivemind](https://github.com/RLBot/python-interface/blob/master/rlbot/managers/hivemind.py), [core match starter](https://github.com/RLBot/core/blob/v5.0.0-rc18/RLBotCS/ManagerTools/MatchStarter.cs).

Telemetry supplies the human's last controller inputs, physics, jump/dodge flags, touches, frame number, match phase, overtime, and team scores. Commit a result from a genuine Ended packet for the active session/fixture once. Regulation time zero, transport loss, and stopping the worker are not final results. Frame gaps must weaken timing/flip-reset conclusions. A held flip can also come from falling off a surface, so the flag alone does not prove a ball flip reset. [Game-data schema](https://github.com/RLBot/flatbuffers-schema/blob/main/schema/gamedata.fbs).

## Offline and Play Online

EAC-off supports offline games, training, LAN and replays. Official matchmaking requires EAC. Current RLBot launches target the offline environment; Steam core starts RocketLeague.exe directly with the Steam game identity, and the maintainer reports no-EAC launcher support after June changes. [Epic policy](https://www.epicgames.com/help/c-37599050/c-32343914/easy-anti-cheat-is-now-available-in-rocket-league-a10791900), [maintainer history](https://github.com/RLBot/core/issues/156), [Steam implementation](https://github.com/RLBot/core/blob/v5.0.0-rc18/RLBotCS/ManagerTools/LaunchManager/Steam.Windows.cs).

Steam can remember an EAC launch choice; Epic may have persistent `-noeac` options. A normal launch request therefore means only that the platform was asked to open the game. It does not prove online readiness. Explain conflicting existing preferences without overwriting unrelated launch options. [Official launch instructions](https://www.epicgames.com/help/c-37599050/c-42869540/a16737879).

Important Epic core hazard: its current launcher first obtains platform authentication from game launch logs, then calls a broad kill helper before restarting offline. Debug logging includes auth arguments. Refuse pre-existing Rocket League sessions, never copy raw auth logs into diagnostics, and separately verify actual process ownership and clean handoff. The app's normal online transition must close only its owned game gracefully and wait for its exit. It must not reuse core's blanket kill helper. [Epic implementation](https://github.com/RLBot/core/blob/v5.0.0-rc18/RLBotCS/ManagerTools/LaunchManager/Epic.Windows.cs), [process helper](https://github.com/RLBot/core/blob/v5.0.0-rc18/RLBotCS/ManagerTools/LaunchManager/ProcessUtils.cs).

## Garage and community maps

The curated catalog uses documented Octane 23, Dominus 403, Merc 30, Breakout 22 and OEM wheels 376. These are bot loadout identifiers, not inventory grants or verified human overrides. Current-game visual acceptance is still needed, with Octane as the fallback. App presets validate the supported IDs and palette ranges. [RLBot item catalog](https://github.com/RLBot/gui/blob/master/frontend/src/assets/items.csv), [loadout API](https://wiki.rlbot.org/v5/botmaking/bot-loadouts/).

Community entries link to original creators and retain separate permission, dependency and launcher notes. No downloaded map is shipped. Import accepts a locally obtained regular .udk/.upk file, checks its Unreal package header/size, copies to AppData under a SHA-256 name, and returns its identity. This is file validation, not a package security review or gameplay test. It runs no arbitrary loader or install script.

The documented direct local-map RLBot route differs by launcher: custom files are documented for Steam; Epic's documented map field is limited to built-in maps. Epic imports remain unavailable. Current core custom-map loading temporarily substitutes Haunted_TrainStation_P.upk and restores it after loading; a crash could interrupt restoration. Import alone never changes game files. Any launch integration must verify write permission, preserve the original, and document recovery before claiming the route tested. [Configuration documentation](https://wiki.rlbot.org/v5/botmaking/config-files/), [actual substitution implementation](https://github.com/RLBot/core/blob/v5.0.0-rc18/RLBotCS/ManagerTools/CustomMap.cs).

## Required runtime receipt

For each launcher independently record OS/build, launcher, installed game version, app commit, core `--version`, Python/interface versions, provider/version, mode and fixture ID, actual owned process identity, and timestamp. Omit credentials/account identifiers. Attach observed checks for human control, correct lineup, ordinary physics, complete match/overtime result, lesson input/reset/ghost, and Play Online save/exit/relaunch. Windows packaging smoke tests and SDK serialization tests are useful but cannot fill the game-tested columns.
