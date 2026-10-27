# DRIBBLE-PLUGIN-01 — pinned DribblePlugin effects and MCT boundary

Static source comparison only. No plugin was loaded, enabled or called; no game, network, input, build or product-code activity occurred. Public plugin source is pinned at `f412cd66ce0735be4aeb21ca41325337eb959aa0`. Findings below do not establish that an installed DLL matches this source or that the plugin is present/enabled in the user’s game.

## What the plugin exposes

`DribblePlugin` is declared as version `0.1`, `PLUGINTYPE_FREEPLAY` (`DribblePlugin/DribblePlugin.cpp:6`). `onLoad()` registers two one-shot notifiers, each with `PERMISSION_FREEPLAY | PERMISSION_PAUSEMENU_CLOSED`; both callbacks also return unless `GameWrapper::IsInFreeplay()` is true (`DribblePlugin.cpp:8-32, 43-55`). There is no enable/disable cvar, persistent enabled state, key hook, tick hook, or session/MCT identity check. The four cvars are only `shootatme` position/speed parameters. `onUnload()` is empty (`DribblePlugin.cpp:58-60`; class declares only load/unload in `DribblePlugin.h:5-10`).

| Notifier | Guard and preconditions | Direct write | Scope |
|---|---|---|---|
| `ballontop` | Requires `IsInFreeplay()`, a server with at least one game ball, and non-null first ball/car wrappers (`DribblePlugin.cpp:11-23`). | Reads car velocity; builds offset `(vx, vy, 170)`, clamps offset x to ±20 and y to ±30, then writes ball location to car location plus that world-coordinate offset and ball velocity to car velocity (`:24-31`). | One command invocation. Does not write car controls/pose or restore the ball. |
| `shootatme` | Requires `IsInFreeplay()`; gets server, ball and car, then reads cvars. It has no null checks for those wrappers (`DribblePlugin.cpp:43-53`). | Builds a target from car world location plus `shootatme_bounds_x/y/z`, calls `GenerateShot(ball location, target, shootatme_speed)`, and writes the resulting velocity to the ball (`:49-54`). It does not set ball location or car state. | One command invocation. No ongoing update or restoration. |

`shootatme` defaults are range-shaped strings `(-200, 200)`, `(-200, 200)`, `(-400, 400)`, and `(800, 1000)`; its code asks each cvar for `getFloatValue()` (`DribblePlugin.cpp:38-53`). This file does not establish how those strings are parsed or sampled. The plugin source has no `HookEvent` or input callback; merely loading it registers notifiers, but does not itself run either ball write. There is no persistent feature to toggle, and unloading contains no ball-state rollback.

## MCT context and state ownership

MCT’s ordinary human lesson request sets `training = bool(lesson_id)`, uses Soccar and unlimited match length, and sets RLBot `freeplay = training and capture is not None` (`work/reviewed-training/src/my_career_training/adapter.py:40-56, 107-119`). For a normal lesson, `capture` is absent, so MCT requests `freeplay=False`; a code comment says human drills use an unlimited offline match while development capture retains its existing Free Play context (`adapter.py:115-119`). The lesson path creates a normal `TrainingEngine` (`game_worker.py:495-508`).

This is a likely context mismatch for ordinary MCT lessons: the pinned plugin requires BakkesMod’s `IsInFreeplay()`, while MCT configures its human lesson as non-Free-Play Soccar. These are different APIs; this source review does not prove how the installed host maps RLBot’s `freeplay` field to `IsInFreeplay()`. Therefore the notifier’s availability inside a running MCT lesson remains unverified. The plugin has no MCT session check, and MCT source contains no `ballontop`, `shootatme`, or `DribblePlugin` integration. The public plugin checkout alone proves neither installation nor active availability.

MCT writes the full ball and human-car desired state on reset/Retry and again when the engine emits the authored start state (`game_worker.py:615-643, 1306-1317`; `adapter.py:167-203`). For Dribble & Flick, authored start is car `[0,-1800,17.01]`, zero velocity, boost 100, ball `[0,-1690,160]`; settle temporarily parks the ball at `[3000,0,93.15]` (`training/catalog.py:34-64, 109-120`). Reset confirmation compares the received ball position/velocity with the expected authored state (`training/engine.py:686-723`). Once active, MCT reads ball/car telemetry for scoring; it does not call the plugin or identify externally changed ball state. If a notifier were callable in that session, its ball writes would be an independent state mutation with no MCT ownership token, arbitration, or provenance marker. A write during reset may affect state confirmation; a write during an active attempt changes the observed ball trajectory.

## Effect on dribble-flick scoring

MCT’s `carry_sustained` predicate is geometric: transform ball-minus-car position into car-local coordinates, require forward offset ≤160, side offset ≤110, height 80–220 and grounded state; accumulate two seconds while consecutive samples remain inside and cadence is continuous (`catalog.py:114-120`; `training/engine.py:1116-1136`). It does not require a touch or a measured wheel/roof contact. Thus, **if** `ballontop` runs and its resulting ball pose remains in the zone, it could contribute to the carry timer without proving that the player carried the ball through normal contact. Its direct location is based on car position/velocity in world axes, not a car-rotation transform, so actual zone membership depends on the live pose and is not guaranteed by the plugin’s “on top” label.

That alone cannot complete the lesson. MCT emits `ball_contact` from the human player’s fresh `latest_touch`; after `carry_sustained`, `flick` additionally requires a fresh touch and game-reported `has_dodged` or `has_double_jumped` (`adapter.py:144-149`; `training/engine.py:990-1028`). `goal_target` requires ball center to cross the goal plane at y=5120 in the marked x/z zone **and** a previously observed `ball_contact` (`engine.py:1137-1159`); final required events are carry, flick and goal target (`catalog.py:116-120`). The plugin’s `SetLocation`/`SetVelocity` calls do not themselves write a human touch or car jump/dodge flag. `shootatme` can change ball velocity and therefore trajectory, but whether it later causes a real collision/touch or a credited score chain depends on gameplay; source does not establish that outcome. MCT does not mark such a result as plugin-assisted.

The MCT gap logic resets `carry_streak` before the carry target check, and `carry_sustained` cannot bridge a gap (`engine.py:793-813, 1127-1136`; existing `tests/test_training.py:292-300`). This protects that one measurement from a missed interval, but it does not identify third-party ball writes or prevent an externally launched ball from changing later contact/goal observations.

## Bounded adapter conclusion

The pinned plugin does **not** support a truthful “DribblePlugin enabled” checkbox: it offers two explicit commands, no on/off state, no query, and no acknowledgement. Do not infer activation from download, load, or source presence. If an MCT feature is desired, first define it as an explicit, acknowledged one-shot ball setup/launch with MCT-owned session gating, safe reset/restore semantics and an attempt-integrity policy. A ball mutation during an active scored attempt must either be represented as an authored variant/profile or make that attempt ineligible for the normal lesson result; otherwise the engine cannot distinguish player-produced from plugin-produced ball motion. Preserve separate labels for the source plugin command and any MCT-native setup behavior. Current source does not provide the context handshake or state provenance needed for a reliable adapter.

## Coverage and provenance

MCT test inventory includes a focused gap test for carry dwell (`tests/test_training.py:292-300`), but no DribblePlugin integration/availability, ballontop/shootatme, plugin-written trajectory, or attempt-credit test was found. Tests were inspected only, not run.

Public source: repository checkout `work/research/bakkesmod-default-plugins`, revision `f412cd66ce0735be4aeb21ca41325337eb959aa0`; the two plugin source files were clean at inspection. MCT checkout `work/reviewed-training`, `HEAD 1fe8c85839a5e72166ee1d5cc3066627548d9fa2`; catalog, engine, adapter, game worker and `tests/test_training.py` were modified in the shared worktree; the cadence helper was clean. MCT hashes below identify the exact bytes reviewed, not necessarily `HEAD` contents.

| File | SHA-256 |
|---|---|
| `work/research/bakkesmod-default-plugins/DribblePlugin/DribblePlugin.cpp` | `475203fdcad085d8bee0224f70dc0ebf9557474635766784437371f088bb32ea` |
| `work/research/bakkesmod-default-plugins/DribblePlugin/DribblePlugin.h` | `50d1a077291dc761c10613200afedef2aa19f2785be77a224bbbc76f34965fbf` |
| `work/reviewed-training/src/my_career_training/training/catalog.py` | `1c05fe5ed75296c5c75848f26e7c01a77160b16938c76c55e15536828f58fe73` |
| `work/reviewed-training/src/my_career_training/training/engine.py` | `37028379a268d6f6e19d42b32a9e3c20778ed4f41d87bfbd3bc76955c61c602a` |
| `work/reviewed-training/src/my_career_training/adapter.py` | `98d1f4612967eda756b21857dfd198a3a12e4a211684067a248b9a829b74285c` |
| `work/reviewed-training/src/my_career_training/game_worker.py` | `2e3982dfc352e4fafcd667898b3cb1f76538b61447c2b6e47adc6d9f862e89c2` |
| `work/reviewed-training/src/my_career_training/training/cadence.py` | `fdbcda80e4fadb135713314e0fb65e2bcf2a3cf848f9261413fc2803555ee240` |
| `work/reviewed-training/tests/test_training.py` | `0da5646aa0c2873287f86d6b2f5c0e0d51e1e9ac06aeb7b550e85fa429dddb9d` |
