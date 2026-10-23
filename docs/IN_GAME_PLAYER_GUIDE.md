# My Career Training: v0.2.0 known-issues preview

**The published v0.2.0 download is not a working replacement for the failures
reported by the owner.** In the first Windows Steam test, a Career fixture and
Start Practice failed to start, the menu repeatedly reopened or appeared under
Rocket League's original menu, and Windows reported **Access is denied** in a
per-run folder beneath `%LOCALAPPDATA%`. The on-screen command error was **“Could
not publish the local career command.”** The startup message was **“Starting
career, waiting for Rocket League to start the offline season.”**

Source repairs are in progress. A replacement installer is being held until the
launch/practice failures are fixed and the native-menu direction is verified.
No public-ready replacement build exists yet. The previous v0.2.0 installer and
portable ZIP remain on the [GitHub release page](https://github.com/sloppamadewithlove/my-career-training/releases/tag/v0.2.0)
as a known-issues preview; they are not a repaired download. This is an actual
owner-reported failed test, not a first test still waiting to happen.

## BakkesMod requirement in v0.2.0

The old v0.2.0 preview requires BakkesMod to be installed and running
separately. BakkesMod is a third-party community plugin framework; My Career
Training uses it to load its in-game plugin. The v0.2.0 installer does not
include BakkesMod, so it is an extra prerequisite. If you are reproducing this
old build, get BakkesMod from its [official site](https://bakkesmod.com/) and
check that it supports your installed Rocket League build.

The replacement setup is planned to explain and guide the official BakkesMod
setup before attempting to launch My Career Training. That guided flow is not
in the published v0.2.0 package. No BakkesMod bundling or redistribution is
claimed.

## Intended design direction

The owner wants a solo offline My Career experience integrated into Rocket
League's menu flow, while preserving the original Steam game and saves. The
v0.2.0 screen is an overlay; native Rocket League menu replacement has not been
demonstrated and remains a release blocker for that direction.

The interim information layout has five main destinations: **Career** (with
Squad, Schedule, and League Table views), **Training**, **Garage**, **Workshop**,
and **Settings**. This is the design direction, not a statement that those
screens currently work. The old preview has no online features and does not
support Epic launch.

## If you already installed v0.2.0

- Close My Career Training and Rocket League before trying any recovery.
- Keep your career data under `%LOCALAPPDATA%\MyCareerTraining`; do not delete
  it to address the bridge access error.
- Do not assume that restarting, reinstalling, a green build result, or an
  automated package check fixed the live-game failures.
- If reporting a reproduction, include the exact screen/action, the full error
  text, Windows version, app version, Rocket League build, Steam status, and
  BakkesMod status. Do not include account credentials.

## Package evidence and remaining limits

The existing release receipt identifies the source commit and Windows package
checks for the old artifacts. Build, native plugin compilation, and automated
tests do not prove that Rocket League gameplay works; the owner's report shows
the published build failed in the live session.

The old source also does not demonstrate native-menu replacement, inactivity
protection, an expert ghost recording, ghost camera spectating, unrestricted
garage customization, Epic support, or verified compatibility for every
community map or plugin. Do not treat these as working features.

For the design and repair status, see [the GitHub repository](https://github.com/sloppamadewithlove/my-career-training),
[the Opus 5.5 design handoff](OPUS_DESIGN_BRIEF.md), and [the acceptance
record](IN_GAME_ACCEPTANCE.md). The handoff does not claim Opus 5.5 has reviewed
the project.
