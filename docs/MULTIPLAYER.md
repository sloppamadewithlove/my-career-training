# Two-captain extension investigation

Checked against current first-party/community-maintainer sources on 22 October 2026. This release has one human captain and locally controlled bot teammates. No two-PC acceptance test has been performed for this app. Network hosting, firewall changes, accounts and paid services are not first-release dependencies.

## Three distinct connections

1. **Game connection.** Rocket League connects the real human clients to a match host. This carries the actual cars, ball, physics, and human input.
2. **Bot-control connection.** RLBot transfers game state to custom agents and returns actions for their assigned bot cars. A remote RLBot socket is not a Rocket League multiplayer server.
3. **Career coordination.** A future app protocol would agree fixtures, squads, manifests, settings and result ownership. It must not pretend to replace the game's network connection.

Mods are not inherently single-player. Minecraft publishes server software, and Fabric distinguishes client/server/common code and server-side mods. That architecture explains the general possibility of shared modded worlds; it establishes no Rocket League API compatibility. [Minecraft server](https://www.minecraft.net/en-us/download/server), [Fabric logical sides](https://wiki.fabricmc.net/tutorial:side), [Fabric server-side mods](https://wiki.fabricmc.net/community:serverside_mods).

## Routes that have documentation

The RLBot LAN guide describes private LAN matches and distinguishes the host, which spawns bots, from other humans joining through the game/plugin route. It uses additional tools and ContinueAndSpawn configuration. This is evidence of a human-plus-custom-bot workflow, not an app-tested seamless internet join code. Its documented console limitation must not be hidden. [Current LAN guide](https://wiki.rlbot.org/v5/miscellaneous/lan-setup/).

Remote RLBot can connect bot processes on different computers, using the server address, port and agent ID. Its defaults listen on all interfaces; remote bot launch requires manual/custom management. Agent allocation limits whose car inputs are accepted, but extra connections can read game state. The first release neither opens firewall ports nor exposes this interface as a public service. [Remote-control documentation](https://wiki.rlbot.org/v5/framework/remote-rlbot/).

RocketHost documents cloud-hosted real matches with a curated set of community bots and current GUI integration. It is a real extension candidate, but that description does not grant permission or an upload API for our specialist brains, training scripts or career coordinator. Verify provider rules, bot permissions, versions, pricing and EAC behavior before choosing it. Do not activate hosting or charge for it silently. [RocketHost documentation](https://wiki.rlbot.org/v5/miscellaneous/rocket-host/).

Epic permits mods in the EAC-off offline/training/LAN environment. Ordinary online matchmaking uses EAC. An external hosting page does not settle the exact launch mode required for our integration. Verify both clients on the supported current route without anti-cheat evasion or modified official matchmaking. [Official EAC scope](https://www.epicgames.com/help/c-37599050/c-32343914/easy-anti-cheat-is-now-available-in-rocket-league-a10791900).

## Proposed protocol boundary

Keep career state independent of the game adapter. A future host owns an immutable fixture ID and session attempt ID, expected human slots, locked lineups and exact game/app/core/provider manifests with content hashes. Both peers acknowledge compatible manifests before the host starts the match. Remote user input controls only that user's real car; the host remains responsible for bot allocation. Configuration changes are forbidden while the fixture is active or awaiting recovery.

The host records the authoritative final game packet and commits one result under the fixture ID using the existing idempotent persistence rule. Guest records reference that host receipt rather than award a second result. No score supplied by an untrusted guest may override a host observation. If the host crashes after saving but before acknowledging, the same receipt can be resent without granting duplicate progression.

For the initial extension, the host owns the season save. The guest owns only their local preferences and may retain a read-only session receipt. Supporting two independently persistent careers is a separate explicit product decision, since rewards, substitutions and schedule ownership otherwise conflict. Bot recruit identities and cosmetic rewards remain bound to their original career.

On human disconnect or uncertain host state, freeze the fixture in recovery, preserve its recorded inputs/result evidence, and offer reconnect or restart/abandon under an agreed policy. Never fabricate a win from socket loss. Reconnecting players must present the original session ID and manifest; stale or divergent sessions cannot continue writing the save. Stop bot output before any transition to an official-online session.

## Acceptance before advertising two captains

Use two actual Windows PCs with licensed current game installs on the chosen supported host route. Record exact versions, launchers and EAC state independently. Demonstrate each human driving a separate car, selected bot teammates and no unauthorized input crossover, correct 2v2/3v3 lineups, and one observed completed result persisted exactly once.

Repeat with disconnect/reconnect, host crash around result commit, incompatible provider manifest, unavailable hosting, and normal online transition. Confirm the guest cannot change host squads/saves. Measure connection reliability rather than assuming LAN instructions provide internet reachability. Obtain explicit approval for any proposed hosting account, paid service, relay or firewall change. Until these receipts exist the UI must describe two-captain play as unavailable, with this document as research rather than a shipped capability.

The 22-player/enlarged-map project and extra game modes remain outside this repository.
