# 0.1.0 — Windows testing prerelease

Prepared 22 October 2026. **Full V1 is incomplete.** No real Rocket League match
has been verified for this application on Steam or Epic. This release is intended
for a first test on the owner's own Windows computer and current game.

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
Unicode paths and installation/upgrade/uninstallation. It preserves AppData saves.
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

## First test and reporting

Follow [PLAYER_GUIDE.md](PLAYER_GUIDE.md). Close existing Rocket League/RLBot
sessions, select the signed-in launcher in Settings, check the installation and
try an optional calibration before your first league match. Record the actual
connection and errors; do not use manual score recovery as the normal match loop.

Report app commit, Windows/game/launcher versions, mode, observed final result,
training setup/feedback and Play Online behavior. Exclude private launcher auth
logs. Use [FEATURE_MATRIX.md](FEATURE_MATRIX.md) for remaining acceptance work and
[COMPATIBILITY.md](COMPATIBILITY.md) for exact adapter/version limits.
