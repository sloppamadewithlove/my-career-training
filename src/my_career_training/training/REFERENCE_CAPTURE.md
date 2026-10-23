# Teaching recording evidence

Checked 23 October 2026. No successful, permitted pose-and-action capture is
bundled. The transport tests generate fixtures solely to test interpolation and
controls; those fixtures are never installed or represented as demonstrations.

## Supported capture

`TrainingEngine.recording()` captures actual game car/ball poses and logical
actions in game seconds. Export and import use recording schema 1. A personal
attempt stays personal, including after success. The controller graphic maps
logical actions to the player's chosen PlayStation display bindings; it does not
claim to read physical hardware buttons.

A teaching reference requires an actual-execution origin, explicit permission
to distribute with its basis, a successful outcome and success evidence, known
game/framework/hitbox/map metadata, and a complete capture. Comparison also
requires matching reset state, mutators, lesson version and variation. Imported
claims are displayed as unverified. A JSON field claiming certification is not
trusted. A video URL alone cannot produce synchronized controller inputs or an
oriented in-game ghost.

The official [RLBot v5 overview](https://wiki.rlbot.org/v5/framework/v5/) documents
last-known player inputs, air state, dodge details and latest touch. Its
[game data reference](https://wiki.rlbot.org/v5/botmaking/game-data/) documents
live GamePackets and the underlying schema. That is the current capture route
used by this project, subject to the separate real-game compatibility gate.

## Sources investigated

1. [Josef37/KickoffPractice](https://github.com/Josef37/KickoffPractice/tree/7fae0a948bea16515287ef42f07012280b79b1bf/data/kickofftraining)
   has recorded Speedflip input files. The project is GPL-3.0 with some retained
   MIT source notices. At commit `7fae0a948bea16515287ef42f07012280b79b1bf`,
   [the format](https://github.com/Josef37/KickoffPractice/blob/7fae0a948bea16515287ef42f07012280b79b1bf/source/KickoffPractice/KickoffStorage.cpp)
   stores 12 game input values per physics tick plus kickoff position, body and
   control settings. It does not store pose samples, current game version or our
   drill's success evidence. No third-party bytes or code were copied into this
   project. A future independently reviewed capture session could replay a
   permitted input script on a separate offline bot, record actual resulting
   physics, and verify success in the current lesson setup. Never inject the
   script into the human player's controls.
2. [MCopin/rl-input-overlay](https://github.com/MCopin/rl-input-overlay/tree/b456ef6790dcb3f7a0756dac6e0347f5ba47accb)
   is MIT licensed, but its
   [flip-clips tool](https://github.com/MCopin/rl-input-overlay/blob/b456ef6790dcb3f7a0756dac6e0347f5ba47accb/app/tools/flip-clips.js)
   generates scenarios from a documented physics model. Those animations are
   useful HUD tests, not captured successful game executions. They are excluded
   as teaching references. No upstream code or media was copied.

## Runtime contract

`GhostPlayback.update(game_seconds, attempt_seconds=...)` advances a render-only
ghost. Watch mode has its own sampled timeline. Lead mode tracks the active
attempt with a configurable lead. Pause, resume, seek, loop, restart and speed
changes affect ghost playback only. On a new training retry call `restart()`.
Captured gaps suppress pose and coach-input display. Playback returns render
lines and camera target suggestions, never a `PlayerInput` or a player state
change. Camera targets are suggestions until the native plugin verifies support.

`snapshot()` and `controller_display()` produce data for the native in-game UI;
they do not by themselves draw a game overlay. Functional game evidence remains
separate from unit-test and Windows-build evidence.
