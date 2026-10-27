# RedirectPlugin static integration research

## Provenance and scope

- The public default-plugins checkout is pinned at `f412cd66ce0735be4aeb21ca41325337eb959aa0`.
- `RedirectPlugin/redirectplugin.cpp` is 3,019 bytes, SHA-256 `bb77172ef93626c931d976535269993e068524a22607a66813756260e8718afb`.
- MCT source examined from the `work/reviewed-training` checkout at commit `1fe8c85839a5e72166ee1d5cc3066627548d9fa2`. File hashes below pin the audited contents independently of the checkout commit.
- Static source review only. No game process, inputs, commands, build, test run, or plugin activation. Findings describe source paths and do not prove runtime cvar conversion, context acceptance, or ball physics.

## RedirectPlugin behavior in the pinned source

The plugin registers as version `0.2`, type `PLUGINTYPE_FREEPLAY` at `RedirectPlugin/redirectplugin.cpp:8`. Its `onLoad` registers cvars and one notifier, `redirect_shoot` (`:10-21`).

| Cvar | Source default | Use in notifier |
|---|---|---|
| `redirect_shot_speed` | `(850, 1100)` | Read with `getIntValue()` and passed to `GenerateShot` (`:34,54`). |
| `redirect_pass_offset` | `(-50, 50)` | Read with `getIntValue()` for both X and Y (`:45-46`). |
| `redirect_pass_offset_z` | `200` | Read with `getIntValue()`; one random Z offset is requested from one-third to the configured value (`:35,47-48`). |
| `redirect_pass_predict` | `1` | Read as bool (`:37`). |
| `redirect_predict_multiplier_x/y` | `2` each | Read as floats and multiply current player velocity X/Y when prediction is enabled (`:40-41,50-53`). |
| `redirect_on_ground` | `0` | When enabled, generated shot Z velocity is set to zero (`:43,55-56`). |

The notifier exits unless `IsInFreeplay()` is true, then obtains the current server, car, and ball; it returns if car or ball is null (`:21-31`). It computes a target point as current player position plus the offset vector, calls `GenerateShot(current ball position, target point, speed)`, optionally zeros the generated Z velocity, and writes the result directly to the current ball with `SetVelocity` (`:47-57`). It does not set ball position or car state.

The callback receives a command-argument vector but does not inspect it. The only explicit random call in this file is for the Z offset. Despite the parenthesized range-looking defaults for speed and X/Y offset, the callback reads those cvars via `getIntValue()`; it has no visible range unpacking or random selection for them. X and Y read the same cvar in two separate calls; equality and correlation of the returned values are not established here. The file includes `utils/parser.h`, but that helper is not present in this pinned repository view, so actual cvar parsing and the meaning of those defaults remain unverified. The behavior of the imported `random` overload, `GenerateShot`, and default-constructed `Vector velMultiplied` when prediction is off is also not established by this source file.

The notifier is gated by `PERMISSION_FREEPLAY | PERMISSION_PAUSEMENU_CLOSED` (`:58`) as well as the explicit `IsInFreeplay()` check. There is no timer, hook, delay, cooldown, state machine, command acknowledgement, or completion signal in this file. `onUnload` is empty (`:61-64`). No explicit ball-velocity restoration is implemented; the direct effect is a one-time velocity write.

## MCT Power Shots launch and attribution

MCT builds a scenario definition with a deterministic `starting_state`, a parked `settle_state`, a rank/difficulty profile, target, timeout, and versioned scenario identity (`src/my_career_training/training/scenarios.py:208-244,294-363`). The scenario launch is generated from its configured origin/lane and profile speed; RedirectPlugin instead aims from the ball's current position toward the current car plus offsets. These are different launch contracts.

The ordinary Human drill match is offline Soccar with `freeplay=False`; only reference capture sets `freeplay=True` (`src/my_career_training/adapter.py:107-119`). RedirectPlugin's required BakkesMod Freeplay context therefore cannot be assumed to accept a Power Shots session. Whether a particular RLBot-owned match satisfies the BakkesMod `IsInFreeplay()` predicate and notifier permission is a runtime question.

For each attempt, MCT resets to the parked situation, checks that the Human is grounded, settled, and has clean jump flags, and checks configured bots and ball. After readiness holds, it writes the configured `starting_state` (`training/engine.py:627-685`). It then waits for observed car, ball, boost, and bot state to match the expected post-reset state before entering active state; failure to confirm within two seconds interrupts the attempt (`:686-754`). On activation, it records an observed ball position/velocity/time as `launch_baseline` and emits `launch_observed` (`:754-770`).

During preparation, MCT records the latest attributed touch for each scenario actor. At activation it freezes those as the pre-attempt baseline; only a changed, finite touch timestamp at or after active start can become the Human touch (`training/engine.py:434-460,754-761,505-527`). Scenario success requires a valid launch baseline, a fresh Human touch, the Human being the latest attributed actor touch, a target crossing after that touch, and a fresh team-0 score edge after the target crossing (`:554-579`). A telemetry gap invalidates the chain (`:494-499,533-534`). Here, latest attributed actor means the inspected Human/keeper chain; the current chain omits defender touches even when that role exists. See [Defender audit](defender-plugin-01.md) and [outcome diagnostic](outcome-probe-01.md).

MCT carries a UUID `session_id` and the selected `scenario_id` and `difficulty` in the start request (`src/my_career_training/bridge.py:1755,1788-1792`). Each engine reset creates a new `attempt_id` and clears launch/touch/score state (`training/engine.py:203-259`). The scenario recording metadata includes scenario ID, difficulty, scenario version, and mirrored flag (`:273-280`), but the scenario code shown has no RedirectPlugin command identity, cvars, launch source, or plugin acknowledgement.

## Integration requirements

1. **Choose one launch owner.** Current MCT sends a whole-actor settle state and then its own whole-actor launch state. Calling `redirect_shoot` as an extra effect on the same transition would race or overwrite the expected ball velocity. If RedirectPlugin owns the feed, MCT must stop treating its configured launch velocity as the applied launch and must validate the plugin-produced result instead.
2. **Bind the action to an attempt.** The existing notifier accepts no request or attempt identifier and returns no acknowledgement. An adapter needs a single-flight request bound to MCT `session_id`, fresh `attempt_id`, scenario ID/version, selected difficulty, and an explicit pending/accepted/failed result. A command invocation alone must not produce `launch_observed`.
3. **Gate by owned state and menu context.** Permit a request only in the intended owned offline training activity and at the correct transition. The Freeplay and pause-menu-closed requirements must be confirmed for the actual MCT match. A UI click while the pause menu is open cannot directly satisfy the notifier permission.
4. **Observe the resulting launch before opening attribution.** Establish the live ball position/velocity after the plugin write, then set the attempt launch baseline and start the freshness window. Do not timestamp the pre-command ball as the plugin launch. If the plugin can change the ball only after MCT has already emitted `GO`, the attempt lifecycle needs a distinct launch-confirmation step.
5. **Record assistance and effective parameters.** Persist launch source, request/attempt identity, selected cvar values or profile, observed ball state, and whether the notifier actually changed state with the attempt record. Existing scenario identity alone cannot explain a randomized or externally supplied feed.
6. **Reconcile target and timing.** Current target and arrival/window values derive from MCT scenario geometry and configured speed. RedirectPlugin computes a target from the live player position, cvar offsets, and optionally scaled current velocity. Validate that result against the selected scenario, or derive target/arrival timing from the observed launch. Do not claim the existing scenario profile calibrated the external randomization.

## Existing source-level tests inspected (not run)

`tests/test_power_shot_scenarios.py` covers configured ball and bot readiness (`:453-460`), one launch-state write per attempt and no active-physics forcing (`:331-343`), success from a fresh Human touch plus observed target/score (`:463-490`), and rejection of stale, keeper, untouched, gap, or ambiguous-score chains (`:492-540`). These tests exercise MCT's current deterministic launch path; they do not exercise RedirectPlugin, its cvar parsing, Freeplay permission, command idempotency, or an external launch acknowledgement.

## Source identity receipt

| File | Bytes | SHA-256 |
|---|---:|---|
| `RedirectPlugin/redirectplugin.cpp` | 3,019 | `bb77172ef93626c931d976535269993e068524a22607a66813756260e8718afb` |
| `src/my_career_training/training/scenarios.py` | 23,706 | `35714a224aa8765ae62be6fde3df6dc87c088c32d297adcda3795d0bc682d979` |
| `src/my_career_training/training/engine.py` | 63,844 | `37028379a268d6f6e19d42b32a9e3c20778ed4f41d87bfbd3bc76955c61c602a` |
| `src/my_career_training/adapter.py` | 12,018 | `98d1f4612967eda756b21857dfd198a3a12e4a211684067a248b9a829b74285c` |
| `src/my_career_training/game_worker.py` | 90,814 | `2e3982dfc352e4fafcd667898b3cb1f76538b61447c2b6e47adc6d9f862e89c2` |
| `src/my_career_training/bridge.py` | 139,135 | `ac502d1f19810baca479a534aa766a6afbea7ba57a405452835cc9dcff379ac2` |
| `tests/test_power_shot_scenarios.py` | 38,173 | `c1e7c9af2b2d46db3fb8e0531668332cedb9e71f8be5c05e597a10fcb0e7dc26` |
