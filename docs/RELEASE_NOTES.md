# Release history

For current instructions and evidence, read [PROJECT_STATUS.md](PROJECT_STATUS.md).
The 24 October native candidate ZIP was published for testing and failed player
startup. The stable installer remains held. The repair is tracked separately;
source checks alone do not establish a working download.

## Earlier 0.3.0 development snapshot (historical)

The following describes an earlier revision, before the native candidate was
published. It does not supersede current status or the candidate source.

The development community library now separates downloading from enabling a
plugin. A player can check an official BakkesPlugins ID and cache its archive
through a cancellable request; no third-party code is extracted or loaded.
See [the community download boundary](COMMUNITY_PLUGINS.md). The read-only
[Windows baseline collector](WINDOWS_VALIDATION.md) identifies the user's
installed game without launching it, and menu diagnostic schema 2 records the
full bounded SDK menu stack. These prepare Windows testing; they do not implement
native button replacement or lift the installer hold.

The current source adds an opt-in [native dialog trial](NATIVE_DIALOG_TRIAL.md)
for Career and Training actions, with read-only Schedule, Season and Squad
views. It uses supported SDK dialogs and checks stale clicks and fixture IDs.
It does not replace the original menu tree or establish an input lock. No
successful Windows Rocket League trial has been recorded.

Steam preservation work retires the RLBot custom-map substitution route;
Workshop browsing and favorites remain, but custom-map startup is unavailable.
The plugin checks process creation time, executable identity and exact offline
flags. Its session shortcut observes a free key without writing BakkesMod
bindings. It removes borrowed ImGui navigation bits when its menu closes,
preserving preexisting flags and unrelated changes.

Temporary BakkesMod plugin files are journaled before the offline launch.
Cleanup restores their prior bytes/existence after Rocket League exits; a crash
leaves a recovery record for the next launch. Changed DLLs and ambiguous config
edits require review rather than being overwritten. Preexisting autoload entries
remain user-owned. See the [Windows Codex handoff](WINDOWS_CODEX_HANDOFF.md) for
a read-only before/after comparison of the separate Steam game installation.

[PR #2](https://github.com/sloppamadewithlove/my-career-training/pull/2) is merged.
It repairs atomic bridge file sharing on Windows, removes repeated menu-open
requests, simplifies the plugin window and garage, and adds a guided official
BakkesMod setup flow. The Windows checks passed, including plugin compilation
and frozen-app smoke checks. Installer build, installation lifecycle checks,
packaging and artifact upload were skipped by the explicit installer hold.
The repaired source still renders an ImGui window; it does not replace native
Rocket League buttons. Its gameplay fixes need a fresh Windows game test.

The latest source adds easier opt-in native-menu diagnostics and
removes old-preview download promotion from the project website. See
[the probe contract](NATIVE_MENU_PROBE.md) and
[native integration research](NATIVE_MENU_RESEARCH.md) for the precise evidence
boundary. No native-menu runtime verification or new release is claimed.

## Previous preview: owner-reported failures

**A replacement installer is on hold.** In the owner's Windows Steam test of
the published v0.2.0 package, starting a Career fixture and **Start Practice**
failed. The owner saw **“Could not publish the local career command”** and
**“Starting career, waiting for Rocket League to start the offline season.”**
They also reported the My Career menu repeatedly reopening while Rocket
League's original menu glitched over it, plus a Windows **Access is denied**
error under a per-run folder beneath `%LOCALAPPDATA%`. These are actual player
reports; they are not a pending first test or a diagnosis.

Source repairs have merged, but no replacement build is public-ready. Existing
v0.2.0 artifacts remain accessible as the [known-issues previous preview](https://github.com/sloppamadewithlove/my-career-training/releases/tag/v0.2.0),
not as a fixed download. See the [current player guide](IN_GAME_PLAYER_GUIDE.md)
and [GitHub repository](https://github.com/sloppamadewithlove/my-career-training)
for status.

The old package requires the player to manually install and run [BakkesMod](https://bakkesmod.com/)
from its official source. BakkesMod is a third-party plugin framework used by
v0.2.0 to load the My Career plugin; the My Career Training installer does not
include it. A guided official setup is implemented in the repaired source but
has not been released in an installer. No bundling or redistribution rights are
claimed.

The intended destination is a native My Career flow in the offline
game, while preserving the original Steam installation and saves. The v0.2.0
custom screen is an overlay and native menu replacement has not been
demonstrated. The interim design has five main destinations: **Career** (with
Squad, Schedule, and League Table views), **Training**, **Garage**,
**Workshop**, and **Settings**. This is planned navigation, not a claim that the
published package works.

## v0.2.0 package record

The archived v0.2.0 package contains the following source/features, but the
owner's live test failed and these entries do not certify working gameplay:

- The Career, Squad, Schedule, Season, Training, Workshop, Garage, and Settings
  plugin pages, plus local career and result persistence logic.
- Necto and Nexto CPU policy files with their original licenses. Historical
  rank estimates are not current certifications, and the policies do not learn
  from the player's sessions.
- A PlayStation-style display for observed logical actions and personal or
  imported ghost-playback code. No validated expert recording is bundled.
- Workshop catalog and local Steam map discovery/launch code; compatibility
  still requires a real successful map launch.
- Limited BakkesMod local cosmetic override code; supported appearance and
  restore behavior have not been accepted in a live game.

The v0.2.0 release receipt records the source and automated Windows package
checks. Those checks do not override the owner's reported live failures. The
custom screen does not replace Rocket League's native menu. Idle-kick
protection, expert ghosts, ghost camera spectating, unrestricted garage
customization, Epic launch, and verified compatibility for every map or plugin
remain unavailable or unverified.

[Previous v0.2.0 release](https://github.com/sloppamadewithlove/my-career-training/releases/tag/v0.2.0) ·
[Player guide](IN_GAME_PLAYER_GUIDE.md) ·
[Design handoff](OPUS_DESIGN_BRIEF.md) ·
[Older v0.1.0 preview](https://github.com/sloppamadewithlove/my-career-training/releases/tag/v0.1.0)

---

# 0.1.0 — Windows testing prerelease

Prepared 22 October 2026. **Full V1 is incomplete.** At publication, the in-game
integration had no Steam or Epic acceptance receipt. The owner later reported
playing a Steam match with the earlier desktop preview; that experience is not
evidence that the v0.2.0 plugin works. The v0.2.0 owner test and current failures
are recorded at the top of this file.

## Available in source

The app combines a human-driven 1v1–4v4 career with four recruited specialist
bots, a four-club six-round league, standings/title playoffs, future-round format
and difficulty changes, local progression and continued careers. Rival fixtures
use persisted seeded simulations and are labeled accordingly.

Eight optional lesson groups provide defined setups, retry/reset logic, measured
observations, real-action recording, personal bests and wireframe ghost playback.
Help settings are independent by lesson. The UI includes squad/garage management,
creator links, local Steam map import, backups, diagnostics and accessibility
settings. A separate worker isolates game integration from the desktop UI.

Final results use fixture/session identities and a durable outbox before career
save/acknowledgment. Play Online implements the exact confirmation, saves first,
stops career work, waits for the owned game to exit, and requests normal launch.
These implementation statements do not claim successful game execution.

## Download and build status

Canonical source and releases:
https://github.com/sloppamadewithlove/my-career-training.
Verified Origin mirror was created at
https://origin.cursor.com/sloppamadewithlove/my-career-training.git;
release-commit sync must still be checked.

The published release receipt records the exact source commit, Windows workflow,
checksums and mirror verification. Only attached binary assets establish that
downloads exist; the workflow must succeed before these artifacts are published:

- `MyCareerTraining-0.1.0-windows-x64-setup.exe`
- `MyCareerTraining-0.1.0-windows-x64-portable.zip`
- `MyCareerTraining-0.1.0-third-party-sources.zip`
- `SHA256SUMS.txt`

The Windows recipe targets Python 3.12.13, PySide6-Essentials 6.12.0, RLBot
2.0.0b56/FlatBuffers 0.19.0 and core v5.0.0-rc18. It tests the frozen GUI/worker,
Unicode paths and installation, same-version reinstall and uninstallation. It preserves AppData saves. Older-version upgrade behavior is not yet verified.
Builds are unsigned unless an actual verified signing receipt is published.
A source ZIP is labeled source and requires development tools; it is never an
installer substitute.

## Verified locally and still pending

Source-rule, save-failure, training-metric, bot-policy and lifecycle tests use
constructed inputs. Native SDK wire-contract checks run on Windows. The exact
final test count and Windows job result are recorded in the release receipt.
The pinned core download hash and dependency license/source collection passed
locally. None of these checks establishes Steam/Epic runtime acceptance.

Known boundaries:

- No validated expert teaching demonstrations are bundled. Import/playback and
  personal recordings exist; personal bests are never presented as expert proof.
- Baseline specialist bots are experimental and unranked. Diamond/SSL strength
  and complete 4v4 behavior have not been established.
- All real-game matches, lessons, controller behavior, bot appearance and online
  handoffs need Windows testing. Steam and Epic results must be recorded separately.
- Community map import validates and copies a local file. It does not certify
  content security or demonstrate loading. Epic map import is unavailable.
- No human inventory grants or online item ownership changes are provided.
- Optional match review records observed score changes and human touches, plus
  bounded, explicitly labeled positioning suggestions. These are not optimal-play
  claims and need real-match validation.
- Save exports preserve JSON state/recording metadata; retain the separate
  `recordings` folder to move actual recordings to another computer.
- No native Mac gameplay, two-captain network mode, extra game modes or enlarged
  22-player project is included.

## Historical v0.1.0 test guidance

Follow [PLAYER_GUIDE.md](PLAYER_GUIDE.md). Close existing Rocket League/RLBot
sessions, select the signed-in launcher in Settings, check the installation and
try an optional calibration before your first league match. Record the actual
connection and errors; do not use manual score recovery as the normal match loop.

Report app commit, Windows/game/launcher versions, mode, observed final result,
training setup/feedback and Play Online behavior. Exclude private launcher auth
logs. Use [FEATURE_MATRIX.md](FEATURE_MATRIX.md) for remaining acceptance work and
[COMPATIBILITY.md](COMPATIBILITY.md) for exact adapter/version limits.
