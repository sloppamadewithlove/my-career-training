# GHOST-PLAYBACK-01 — runtime playback trace

## Scope and source state

This is a read-only trace of the selected-recording playback path, not an import-eligibility review or a live-game verification. Source references are relative to `work/reviewed-training`. Its HEAD at inspection was `1fe8c85839a5e72166ee1d5cc3066627548d9fa2`. Both `game_worker.py` and `training/engine.py` were modified in the shared worktree; their line references below describe their audited working-tree contents and their SHA-256 hashes are recorded below. `coach.py`, `recordings.py`, and the cited tests were clean at inspection. No tests were run.

## Runtime path and time bases

`Recorder.append()` makes each recording’s `sample.time` relative to the first observed frame (`frame.time - origin`), and stores `time_base: game_seconds`, car pose/actions, packet-gap markers, and ball position/velocity (`src/my_career_training/training/recordings.py:204–260`). Ball telemetry exists in the recording schema, but the ghost pose interpolator returns only car position, quaternion, and the left sample’s logical actions (`:307–324`).

Once the bridge supplies a recording to the worker, `GameSession.handle_command(play_recording)` validates it and constructs a `GhostPlayback`; the same implementation is used regardless of local/imported provenance metadata. The handler currently passes `kind="personal"` to both playback loaders, stores the recording, resumes the coach, and optionally creates a separately disabled `GhostPractice` (`src/my_career_training/game_worker.py:1034–1087`). Selection and import authorization happen upstream and are out of scope here.

| Runtime path | Clock and placement | Reset/end behavior |
|---|---|---|
| **Watch** (`GhostPlayback`) | Starts at the recording’s first sample. Its first update establishes a game-clock anchor; subsequent `game_seconds` deltas advance the cursor at the chosen rate. Pause/resume clears clock anchors, so there is no wall-time catch-up. Seek clamps to the actual sampled interval; loop wraps only between first and last sample (`training/coach.py:137–312`). | Non-loop playback stops at its last sample with status `ended`; that endpoint still has a valid pose and is therefore still marked visible. Explicit stop moves to the first sample and hides the pose/lines. Restart begins at the first sample. |
| **Lead** (`GhostPlayback`) | Uses `attempt_seconds * speed + lead_seconds + seek_offset`. It reports `waiting_for_attempt` when the worker has no engine start time. Seek adjusts the offset. A backwards attempt clock resets the lead offset; if it had ended, it resumes, but an intentional pause remains paused (`coach.py:254–312`). | Same sampled end and loop bounds as Watch. A backwards game clock pauses playback with `clock_restarted` and leaves the current pose available to render. |
| **Practice** (`GhostPractice`) | Explicit On starts from sample zero at normal speed and anchors the first recorded car pose to the supplied player pose plus the configured forward offset (default `300` game units). Later relative car motion is transformed by the yaw difference; the ghost does not follow the player again. It advances on game-time deltas and loops at the last sample while keeping its anchor (`coach.py:371–535`; `recordings.py:379–405`). | Off immediately returns no pose/lines/actions. A backwards game clock restarts its cursor at sample zero while retaining the anchor. It has no seek, pause, rate, or clip-end stop controls. |

The worker writes `playback_origin` when a recording loads and clears it on reset, but `rg` finds no read of that field beyond those assignments (`game_worker.py:276, 653, 787, 1066`). Effective Watch origin is the first subsequent `GhostPlayback.update()` anchor; effective Lead origin is the lesson engine’s `started_at`; Practice origin is its first update after enable. The engine sets `started_at` when the attempt becomes active (`training/engine.py:754`).

## Retry, terminal state, and visibility

`GameSession.reset()` is gated while a published attempt lacks its acknowledgement. Once allowed, it resets the engine and sends the desired lesson state, restarts the coach, and—if practice was enabled—restarts and re-anchors practice using `settle_state["car"]` (`game_worker.py:615–671`). That anchor is the intended reset pose sent to RLBot, not a later packet confirming where the game actually placed the car; live alignment is unverified. Auto-reset additionally requires the preference, acknowledgement, retryable samples, and its feedback delay (`game_worker.py:888–907`).

There is no source-level terminal transition for either ghost. The engine’s `update()` returns early after `finished` (`training/engine.py:581–585`), and `_finish()` changes state/outcome without clearing `started_at` (`:1181–1190`). But the worker still calls both ghost updates on each subsequent packet (`game_worker.py:1341–1344`), including after publishing the attempt. Thus Watch keeps following game time, Lead keeps following elapsed time since the retained `started_at`, and Practice continues looping while enabled until a user turns it off, resets, or stops the session. This is a source inference from the caller and engine paths; there is no test or game observation of the terminal screen.

When a non-looping Watch/Lead clip reaches its end, `GhostPlayback.snapshot()` excludes only `unavailable` and `stopped` from visibility; an `ended` pose can remain drawn at the last sample (`coach.py:290–312`). Practice loops instead. `render()` emits 3D line draws and HUD text from those snapshots; `ghost_lines()` is explicitly a render-only car outline, and the ghost path does not send recorded actions to the Human or create a physics actor (`game_worker.py:1406–1472`; `recordings.py:407–438`; `coach.py:290–312, 507–535`). There is no ghost ball rendering, despite recorded ball position/velocity. The outline’s non-collision behavior is statically supported, not confirmed in a live session.

Stop/Return makes the worker stop rendering while stopping and tears down the owned RLBot match/relay (`game_worker.py:946–955, 1517–1540`). Teardown contains no explicit `coach.stop()`, practice Off, or snapshot clear. Since the implementation uses draw calls rather than an actor, there is no ghost actor to destroy; whether a last submitted line persists until the game/render layer’s next clear is not established by this Python source.

The later [Core cleanup trace](render-cleanup-01.md) establishes additional per-client removal and handler-wide clear requests outside this Python path. It also identifies a conditional clear-queue progress concern. Thus the gap is unverified end-to-end disappearance, not a total absence of cleanup requests.

## Gaps and useful acceptance checks

- Define a terminal policy for each playback mode: pause/freeze, hide, or keep demonstrating while the result waits for acknowledgement. Current code implicitly continues; ended Watch/Lead can leave a visible last-frame outline.
- For retry, verify the practice ghost against an observed post-reset pose (or explicitly accept the intended reset pose anchor). Verify Watch starts on the first post-command game packet and Lead starts at the configured lead when `started_at` becomes available.
- Check a packet gap longer than 100 ms: the interpolator refuses to bridge it, and snapshots hide pose, lines, and logical actions with `capture_gap`; it does not extrapolate (`recordings.py:307–324`; `coach.py:290–312, 507–535`). Then check that playback resumes when a valid sample interval returns.
- Verify no collision, input mutation, ball state change, or stale outline after Off, Stop, session Return, or replacement with another recording. The static code supports a line-only, non-input path, but the fake renderer tests cannot establish in-game renderer clearing or collision behavior.
- If a teaching demonstration must show the ball as well as the car, implement a separate ball timeline and placement/synchronization rule. The existing pose interpolator discards recorded ball fields; moving only the car outline cannot demonstrate car–ball contact geometry.

## Existing tests inspected (not run)

- `tests/test_training_coach.py:40–134`: Watch pose interpolation and held actions, gap refusal, pause/resume/seek/rate/loop, Lead attempt-clock behavior, clock restart, clip end, stop hiding, and no replayed input.
- `tests/test_training_ghost_practice.py:113–255`: normal-speed restart/loop, stable anchor, immediate Off, re-anchor, missing-player wait, packet gaps, backwards clock, outline geometry, and no collision actor/input claim.
- `tests/test_game_worker_ghost_practice.py:98–230, 313–329`: worker toggle/load acknowledgements, fake-renderer line path, practice/legacy display exclusivity, and retry re-anchor.

These tests are unit-level; the ghost-focused suites contain no finished-attempt/terminal visibility assertion, and the worker render test uses a fake renderer. No live game, renderer lifecycle, physics collision, or post-timeout visual result was observed.

## File hashes at inspection (SHA-256)

| File | SHA-256 |
|---|---|
| `src/my_career_training/training/coach.py` | `0807FDA8DAF33AE67A9D1F31CCF93ECB10ACCCD21BB7EFA3D9FB8A7FEC905325` |
| `src/my_career_training/training/recordings.py` | `8EFFB8F438B39C4ABE4901D683DC6E5E0424BAA7F696DC35143B282CC5AA96F1` |
| `src/my_career_training/game_worker.py` | `2E3982DFC352E4FAFCD667898B3CB1F76538B61447C2B6E47ADC6D9F862E89C2` |
| `src/my_career_training/training/engine.py` | `37028379A268D6F6E19D42B32A9E3C20778ED4F41D87BFBD3BC76955C61C602A` |
| `tests/test_training_coach.py` | `D096F3761983F685C5274A3DBD7B6E603FDB5988C895F6522C6DBB932E670D10` |
| `tests/test_training_ghost_practice.py` | `37E742ABBEEEBD1C102D04CCC1AF9620D4DD3F7955C8D5CF97A07C97E27B50EF` |
| `tests/test_game_worker_ghost_practice.py` | `56C1FEDDD0F2B2A319C9EAEB8F8C74DA4E8E774D118746CA496D7BCAFEEE3B5D` |
