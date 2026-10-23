# My Career Training 0.2.0 — in-game Windows preview

This is an early technical preview. Full V1 is incomplete. The in-game source is
being prepared for a Windows build; a successful DLL/package build and a live
Rocket League session have not yet been verified. Treat the controls below as
the intended test flow until the acceptance report records a real result.

## What you need

- Windows x64 and the current Rocket League installation launched through Steam.
- Steam signed in, plus BakkesMod installed and opened at least once.
- Rocket League fully closed before starting My Career Training. This build
  refuses to attach to an already-running game.

Version 0.2 starts Rocket League in its supported offline/EAC-off mode and
opens a custom BakkesMod interface inside the game. It does not replace the
game's native Scaleform menus. Epic launch is not supported in this preview.
Do not use this session for online matchmaking; the in-game experience has no
online actions. To play online, close My Career Training and the game, then
launch Rocket League normally through Steam.

The first launch installs the My Career Training plugin into the existing
BakkesMod folder and adds its load command to `plugins.cfg`. If a plugin DLL or
configuration file already exists, the installer keeps a backup beside it.
Your career saves remain under `%LOCALAPPDATA%\MyCareerTraining`, outside the
program folder. Before testing, close the app and make a separate copy of that
folder if you want an extra backup.

## Start the in-game menu

1. Close every Rocket League window and open the **My Career Training** desktop
   or Start menu shortcut. It starts the offline game and its local career
   service together.
2. Wait for Rocket League to reach its offline front end. The plugin should
   open the **MY CAREER** custom interface. F6 toggles the hub when that key was
   unused; the plugin will not replace an existing F6 binding. If the menu does
   not appear, check that BakkesMod is open and supports the installed game
   build, then use the setup/diagnostics shortcut and record the error.
3. Use the on-screen tabs and Back controls to move between Career, Training,
   Schedule, Season, Squad, Workshop, Garage, and Settings. Mouse and keyboard
   are expected; controller navigation and focus behavior still need a Windows
   game test.

## Career and matches

Create or continue a local career, choose a 1v1–4v4 format, review the schedule
and standings, and manage the four recruited teammates. The human remains the
player-controlled car. A match result should appear only after the game reports
the actual final score; confirm the career is saved before starting another
fixture. If the game or app closes during a match, do not invent a score. Use
the saved career state and report the exact recovery screen shown.

The in-game view uses the same player save directory as the earlier desktop
preview. Do not delete or replace `%LOCALAPPDATA%\MyCareerTraining` when
upgrading. The setup/diagnostics shortcut is separate from the in-game shortcut.

## Training, recordings, and controller display

The intended training menu exposes the built-in lesson catalog, lesson help,
retry/reset, and playback controls for successful personal recordings. The
current in-game menu does not expose recording-file import; use the desktop
management app to import a permitted recording, then reopen the in-game
session. A ghost is a non-colliding wireframe
playback of recorded car poses. It must not steer the car or affect the ball.
There is no validated expert teaching recording bundled. Your own recording
must be labeled as your attempt; imported files keep an unverified label unless
independently checked. If no compatible recording exists, the menu should say
that the demonstration is unavailable rather than inventing one.

The controller graphic defaults to a PlayStation-style display. Its inputs are
observed Rocket League logical actions, not direct DualShock/DualSense button
capture. Display mappings can be changed separately; your actual controls stay
in Rocket League's own controller settings. The default display mapping is:

| Game action | PlayStation display |
|---|---|
| Jump | Cross |
| Boost | Circle |
| Powerslide / handbrake | Square |
| Accelerate / reverse | R2 / L2 |
| Steering and aerial axes | Configurable stick-axis display |

If telemetry is missing, the display should say actions are unavailable. Do
not read the graphic as proof that a particular physical button was pressed.

## Workshop, Garage, and Settings

Workshop entries are creator references and locally discovered Steam content;
a listing or favorite does not prove that a map loaded. No Epic Workshop route
is available in this preview. The in-game menu does not currently expose map
file import. Local file import through the desktop management app validates
and copies a selected file, but does not certify its contents or prove game
compatibility.

Garage entries can describe local bot styles. The optional BakkesMod item
override is limited to supported installed cosmetic products and must be
restorable. It does not grant account inventory, and the current game appearance
still needs verification. If an option is unavailable, keep it labeled as
unavailable rather than reporting success.

Settings and diagnostics should identify the active Steam installation, game
build, BakkesMod version, plugin connection, and whether observed input or
cosmetic capabilities are actually present. Do not include Steam credentials
or private account identifiers in a report.

## Please report

Use [IN_GAME_ACCEPTANCE.md](IN_GAME_ACCEPTANCE.md) for the test checklist. For a
failure, include app version/commit, Windows version, Rocket League build,
Steam, BakkesMod and plugin versions, the exact screen/action, and what the game
actually did. Keep source tests, Windows packaging results, and game observations
separate. A successful build is not proof of gameplay.
