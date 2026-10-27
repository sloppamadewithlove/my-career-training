# RECOVERY-PLUGIN-01 — pinned BakkesMod RecoveryPlugin and MCT boundary

## Scope and identity

Static source trace only; no plugin load, command execution, install, game interaction, or license assessment. The public source checkout is pinned at commit `f412cd66ce0735be4aeb21ca41325337eb959aa0`.

## What RecoveryPlugin declares

`RecoveryPlugin.cpp:7` registers version 0.1 as `PLUGINTYPE_FREEPLAY`. It does not register a `HookEvent`; its activation loop uses `SetTimeout` callbacks. In `onLoad`, it registers four cvars:

- `recovery_bumpspeed_angular`, default string `(0, 6)`, bounded 0–10;
- `recovery_bumpspeed_linear`, default string `(800, 1100)`, bounded 0–1999.9;
- `recovery_bumpspeed_linear_z`, default string `(400, 700)`, bounded -2000–1999.9;
- `recovery_cooldown`, default string `(3000, 6000)`, bounded 0–120000.

`recovery_start` has `PERMISSION_FREEPLAY`, independently checks `IsInFreeplay()`, logs and returns if false, loads cooldown as a float divided by 1000, sets an in-memory enabled flag and starts the timer loop (`RecoveryPlugin.cpp:17-26`). `recovery_stop` has `PERMISSION_ALL` and only clears the flag (`:28-30`). Start does not reject a repeated call; each call directly starts another timeout chain. There is no plugin-status cvar, change acknowledgement, start/stop UI, or custom-training command.

Cvar defaults are written as range-looking strings, while bump logic obtains values through `getFloatValue()` and does not call a range parser in this translation unit. The project’s included `utils/parser.h` and BakkesMod SDK implementation are outside this pinned checkout. I therefore do not infer actual numeric defaults, random range sampling, or slider semantics from these strings.

## Scheduling and car mutation

`CheckForBump()` returns if disabled or outside Freeplay; otherwise it schedules a timeout that calls `CheckForBump()` again after `GetBumpTimeout()` (`RecoveryPlugin.cpp:39-46`). The timeout calculation reads the current server game time. Once elapsed game seconds since the last bump exceed `lastCooldownTime`, it checks whether the current game car is on the ground or a wall; if so it calls `ExecuteBump()`. While airborne it retries after a random 0.2–1.0 seconds. Before cooldown expiry it schedules the remaining delay plus 0.1 seconds (`:49-67`).

`ExecuteBump()` rechecks Freeplay and enabled, then reads the three speed cvars and makes a vector for angular velocity and a vector for linear velocity. It chooses independent random signs for the three angular components and the X/Y linear components; the Z linear component uses the vertical cvar without a random sign. It calls `car.SetAngularVelocity(...)` and `car.SetVelocity(...)`, then stores current game time and reloads cooldown (`:69-103`). The code does not write car position, boost, ball state, score, match mutators, or a new training start state. It does not save and later restore the prior car velocities. The intended effect is a randomized direct velocity impulse to the game car after the grounded/on-wall condition; exact physics effect and cvar interpretation have not been runtime-verified.

## Deactivation and cleanup

`onUnload()` only clears `recoveryEnabled` (`RecoveryPlugin.cpp:34-37`). Stop/unload do not restore previous car velocity or cancel a timer token. A timeout already queued will call `CheckForBump()` once and then return because the flag is false; actual callback lifetime after plugin unload depends on host behavior and is not established here. Leaving Freeplay likewise causes the next callback to return; no game-event hook is present to restart the loop upon re-entry. The enabled flag itself is not cleared by that early exit. Repeated `recovery_start` calls have no idempotency guard and may leave multiple polling chains until stopped.

## Difference from MCT Flight Recovery

The name is shared, but behavior is different. MCT’s `flight-recovery` catalog lesson starts at `(0,-2500,17.01)`, checks two ordered point-radius gates, then requires an observed landing and a grounded position inside the recovery corridor before emitting `recovered` (`training/catalog.py:174-190`; `training/engine.py:1084-1097,1163-1179`). It does not generate bumps or change car velocity. The recovery predicate records roof-up and forward-alignment values but does not set thresholds for them; success events are gate 0, gate 1 and recovered. Timeout is 25 seconds. Retry resets the engine and reapplies the configured lesson state (`game_worker.py:630-653`).

The lesson measures a route followed by a landing/corridor observation. RecoveryPlugin perturbs the car’s velocities after it lands or contacts a wall. A checkbox for the plugin would be an additional disturbance feature, not an implementation of the Flight Recovery drill.

## Local MCT integration and compatibility boundary

No `recovery_start`, `recovery_stop`, or `recovery_bumpspeed_*` reference exists in the reviewed MCT source. MCT already has pause-menu training checkboxes for Lesson HUD, Instructions, Timing, Retry after attempt and Show controller (`plugin/include/NativeMatchLayout.h:570-616`). Those existing controls use training/assistance and display-preference paths. The bridge’s `training_settings` handler validates against `coaching_preferences` and rejects unknown keys (`bridge.py:1246-1255`; `training/coach.py:44-74`), so a RecoveryPlugin command toggle should have its own explicit state/action adapter rather than being smuggled into a HUD preference.

The MCT plugin itself is `PLUGINTYPE_FREEPLAY`, but its owned-session guard is `ownedOfflineNow()` and does not assert `IsInFreeplay()` (`plugin/src/MyCareerTraining.cpp:28,580-589`). Ordinary lesson configuration is `GameMode.Soccar`, with `freeplay=training and capture is not None`; normal human lessons have `capture is None`, so that field is false (`adapter.py:107-119`). RecoveryPlugin requires both Freeplay plugin context and `IsInFreeplay()` in its notifier/loop. Whether BakkesMod reports an MCT-owned RLBot Soccar lesson as Freeplay is UNKNOWN; source does not establish that its start command will work there.

The existing MCT generic command helpers are not drop-in: community dispatch accepts only a fixed `plugin load MCTCommunity_286_...` form and training-pack dispatch accepts only catalogued `load_training <code>` (`MyCareerTraining.cpp:1110-1117,1158-1165`). A safe minimal adapter, if Freeplay compatibility is first demonstrated, is a dedicated enabled/disabled checkbox in the existing owned-training pause settings, a fresh-session-bound action in MCT’s native bridge, and a narrowly fixed dispatcher for exactly `recovery_start`/`recovery_stop`. Gate it on plugin availability and owned offline lesson state. Because RecoveryPlugin exposes no active-state acknowledgement, show “requested” or unavailable until a reliable state signal exists; do not treat a locally saved checkbox as proof the plugin started.

For owned RLBot Soccar, also coordinate the toggle with MCT state-setting: `desired_state()` can write human car pose, velocity, angular velocity and boost on setup/retry (`adapter.py:167-203`). Stop the bump loop before reset/Return and do not let a pending timeout mutate the car while MCT is applying its clean start pose. Stop on toggle-off, attempt completion if assistance is attempt-scoped, Retry before state reset, Return/worker shutdown, ownership/scope loss, and MCT unload. Do not rewrite plugin cvars unless the adapter snapshots and restores them; simplest is to leave their values untouched. Stopping prevents future bumps but cannot undo an impulse already applied.

## Minimal future measurements and acceptance

1. **Context:** with explicit user-owned test authorization, verify that the exact MCT-owned offline Soccar session reports Freeplay to BakkesMod. Until this is known, keep the checkbox unavailable and issue no start command.
2. **Command/state:** confirm plugin loaded and cvars/commands available, then verify start and stop outcomes. Test repeated start, stop before first callback, leave/re-enter Freeplay, and stop/unload with a pending timeout. Confirm no further bump occurs after stop and check timer lifetime on unload.
3. **Timing/trigger:** log game timestamp/frame before and after each callback; verify cooldown units, delay behavior while airborne, and that bumps only occur on the ground/wall branch. Test whether cvar changes affect the next bump or only the next cooldown cycle.
4. **Physics:** capture car position, velocity, rotation, angular velocity, boost, wheel/air state, player last input, ball position/velocity, match phase and score immediately before and after the command. Confirm which velocity fields change, signs/magnitudes against actual cvar values, and whether any ball or score changes arise from resulting collision rather than a direct write.
5. **Reset/cleanup:** verify checkbox-off, lesson Retry, Return, telemetry interruption, scope loss and plugin unload. Assert stop before MCT’s whole-state reset; ensure return does not silently teleport or rewind residual physics unless the player explicitly retries the lesson.
6. **UX/evidence:** distinguish “bump mode requested/active” from the measured car effect. Do not count an attempted console command as an observed bump, do not grade a landing as a bump success, and keep the separate route-based `flight-recovery` lesson semantics unchanged.

No live measurement, command dispatch, code changes, tests, or external plugin installation were performed for this report.

## Source fingerprint receipt

SHA-256 (lowercase; byte sizes):

| Source | Bytes | SHA-256 |
| --- | ---: | --- |
| Pinned commit | — | `f412cd66ce0735be4aeb21ca41325337eb959aa0` |
| `work/research/bakkesmod-default-plugins/RecoveryPlugin/RecoveryPlugin.cpp` | 3,651 | `7658554c5a121bbd33b5484605ec534920ab8fe1c55b3d9eda2b6867701dc527` |
| `work/research/bakkesmod-default-plugins/RecoveryPlugin/RecoveryPlugin.h` | 414 | `e4d9485091677d55c11d107692e86cd61dfe3cd64ff29ea99476acff33ad0674` |
| `work/research/bakkesmod-default-plugins/RecoveryPlugin/RecoveryPlugin.vcxproj` | 6,195 | `14c7f1b3a5e35bdd28a89761b65ade3ceca78446f7e9e49f8c348f225ea1f223` |
| `work/reviewed-training/plugin/include/NativeMatchLayout.h` | 44,432 | `a986f0ed827f11ef2716c8fc6bb196d55f822cc22c6b5316b0fde0bb278a8d53` |
| `work/reviewed-training/plugin/src/MyCareerTraining.cpp` | 89,835 | `edc7bf5a6dc7ca0cff34ac694fb72fe71fa26dfe1fd4607d512f3b321a1a9279` |
| `work/reviewed-training/src/my_career_training/adapter.py` | 12,018 | `98d1f4612967eda756b21857dfd198a3a12e4a211684067a248b9a829b74285c` |
| `work/reviewed-training/src/my_career_training/training/catalog.py` | 9,097 | `1c05fe5ed75296c5c75848f26e7c01a77160b16938c76c55e15536828f58fe73` |
| `work/reviewed-training/src/my_career_training/training/engine.py` | 63,844 | `37028379a268d6f6e19d42b32a9e3c20778ed4f41d87bfbd3bc76955c61c602a` |
| `work/reviewed-training/src/my_career_training/training/coach.py` | 25,430 | `0807fda8daf33ae67a9d1f31ccf93ecb10acccd21bb7efa3d9fb8a7fec905325` |
| `work/reviewed-training/src/my_career_training/training/coaching.py` | 5,848 | `3b8336a54f4997479f1ce56f787377eb748683a117c8ba24a82e6e3c03b25d3b` |
| `work/reviewed-training/src/my_career_training/game_worker.py` | 90,814 | `2e3982dfc352e4fafcd667898b3cb1f76538b61447c2b6e47adc6d9f862e89c2` |
| `work/reviewed-training/src/my_career_training/bridge.py` | 139,135 | `ac502d1f19810baca479a534aa766a6afbea7ba57a405452835cc9dcff379ac2` |
