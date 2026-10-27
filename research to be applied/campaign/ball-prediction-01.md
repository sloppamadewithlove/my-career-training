# BALL-PREDICTION-01 — BallPrediction compatibility

## Scope and evidence boundary

This is a read-only source audit of `BakkesMod2-Plugins` at commit `f412cd66ce0735be4aeb21ca41325337eb959aa0` and the frozen MCT tree `work/reviewed-training`. It does not identify an installed `BallPredictionPlugin.dll` or prove that the pinned source matches any installed binary. The MCT CMake file pins SDK headers at `479e8f571cf554b25f4eeb64d611dec4133edcaf`; that is a declaration reference, not proof of the SDK used to build the public BallPrediction project.

## Pinned plugin behavior

`BallPredictionPlugin.cpp` declares plugin types `FREEPLAY | CUSTOM_TRAINING` (line 7). On load it registers `cl_soccar_predictball` with default `0`, plus `cl_soccar_predictball_steps` default `480` and `cl_soccar_predictball_stepsize` default `40` (lines 17–27). Only the enable CVar has a value-change callback. The plugin also hooks Freeplay initialization/destruction and Training Editor play-test start/destruction (lines 30–33).

When either load event runs, `OnFreeplayLoad` checks only the bound enable flag, then registers `Render` and hooks `Function TAGame.Car_TA.SetVehicleInput` (lines 36–42). The CVar callback calls that load routine whenever the CVar is true and `IsInGame()` is true; it does not check Freeplay, Training Editor, offline status, match type, or MCT session ownership (lines 51–62). When false, or when a destroy event arrives, cleanup runs unconditionally. The plugin’s `onUnload()` and destructor are empty (lines 9–15, 243–245); no explicit CVar restoration or lifecycle cleanup is present there.

The callback claims in a comment that `SetVehicleInput` is synchronized with physics ticks (lines 95–99), and it steps its local model twice by half of `1/61` second (lines 162–170). Its callback receives only an event-name string, does not inspect that string, and has no caller-aware hook or car filter (lines 101–110). If this event is emitted once per car, MCT scenarios with a keeper could advance the cache more than once per simulation frame; dispatch cadence and caller multiplicity are unverified for the target runtime.

The predictor reads the server ball’s location, velocity, and angular velocity when its global `currentStep` is zero (lines 101–109, 138–159). Otherwise it seeds the next chunk from `predictedPoints` (lines 116–137), advances 40 points per callback at defaults, and wraps after `480/40` callbacks (lines 162–199). `currentStep` is file-global and is not reset by the load/destroy routines. Thus a retry or scenario replacement is not guaranteed to seed the prediction immediately from the new live ball; while `currentStep != 0`, the next chunk comes from cached prediction data. The precise delay depends on callback cadence.

The render path projects points and draws lines/markers (lines 204–240). The visible callback contains no ball, car, or input setters. Apex markers are inferred from a velocity sign change; this source does not read MCT touch, timer, scenario, or mutator state. The required `ball.h`, `vec.h`, and `DynamicState.h` implementation files are absent from the pinned plugin folder, and the project file references external dependencies. Therefore the collision model, constants, arena assumptions, and fidelity under MCT mutators are not established by this pinned source.

## Drawable cleanup scope

BallPrediction calls `gameWrapper->UnregisterDrawables()` on disable and destroy (`BallPredictionPlugin.cpp:45–48, 58–61`). The MCT-pinned SDK header documents `RegisterDrawable` and declares `UnregisterDrawables()` with the comment “Can only unregister every drawable for now, sorry!” (`GameWrapper.h:94–100`). It gives no caller-versus-global scope, and the cached SDK contains only the declaration, not an implementation. The BallPrediction project’s SDK build identity is also not established. Status: drawable cleanup scope is unverified; test effects on other overlays.

The reviewed MCT plugin declares and implements its own `Render()` override (`plugin/include/MyCareerTraining.h:60`, `plugin/src/MyCareerTraining.cpp:1750`); a source search found no explicit MCT call to `RegisterDrawable` or `UnregisterDrawables`. That does not prove whether SDK cleanup could affect MCT drawing or another plugin’s overlays.

## MCT Power Shots context

The native Power Shots route dispatches `start_lesson` with lesson id `power-shots` and a scenario/rank selection (`plugin/include/NativeCareerLayout.h:1827–1830`; `src/my_career_training/bridge.py:1727–1736`). The frozen adapter builds training as `GameMode.Soccar`; ordinary lessons use one Human and optional scenario keeper, unlimited match length, enabled state setting, and `freeplay=training and capture is not None` (`src/my_career_training/adapter.py:55–58, 77–102, 107–119`). The Power Shots launch request does not carry a `reference_capture` field (`bridge.py:1755–1792`); the validator returns None when that key is absent (`reference_capture.py:130–140`), so this expression is false. This is an RLBot-managed Soccar match with app-controlled state, not the stock Freeplay or Training Editor context declared by BallPrediction.

Retry calls the lesson engine reset, converts its returned state into an RLBot desired game state, and sends that state to the runtime (`src/my_career_training/game_worker.py:615–648`; `adapter.py:191–203`). Scenario changes similarly reset and send a replacement state (`game_worker.py:688–770`). BallPrediction has no integration with those reset messages or lesson identity. Its CVar callback’s broad `IsInGame()` check could still try to activate its hook in a MCT match if the plugin is loaded and the user changes the CVar, but that does not establish that its hook or draw callback works there.

## Checkbox contract and integration points

There is no MCT BallPrediction checkbox or CVar integration in the frozen source. If pursued, keep four states separate: **requested** (saved lesson preference), **applied** (the exact supported plugin/CVar accepted the write), **visible** (the line was confirmed in the owned lesson), and **restored** (MCT returned only a value it still owns).

Minimum safe contract:

1. Default request off. Do not write any CVar until the exact loaded plugin build and supported session context are identified; CVar presence alone is not identity or proof of rendering.
2. Restrict activation to the owned offline Power Shots session only after a compatibility probe confirms this hook/draw path there. Do not infer support from `IsInFreeplay()` or `IsInGame()` alone.
3. Snapshot the original enable value, set only `cl_soccar_predictball`, read it back, then report applied separately from visible. Leave step-count and step-size values untouched.
4. Preserve a pre-existing user-enabled value. On Return/session loss/unload, restore only if the current value still equals the value MCT applied; if the user changed it meanwhile, leave it alone.
5. Resolve per-plugin drawable cleanup before offering an MCT-managed off switch. The current disable path calls `UnregisterDrawables()` without a scoped handle, and cleanup effects on other overlays are unknown.
6. Ensure retry and scenario replacement cause prediction to reseed from the live ball, or explicitly defer the feature until that behavior is established. MCT lesson timer, ball, car, and controller input remain owned by the MCT/RLBot session.

Relevant integration sources are `plugin/include/NativeCareerLayout.h` and `src/my_career_training/bridge.py` for the player request, `src/my_career_training/adapter.py` and `game_worker.py` for session identity/reset, plus the external BallPrediction CVar and drawable calls. No such integration is implemented today.

## Minimum future acceptance

- Identify the installed BallPrediction DLL by path, version, and hash; confirm its CVar registration and supported load context instead of treating the public source pin as an installed match.
- In an owned offline Power Shots session, confirm one toggle produces one prediction overlay and that disabling it removes that overlay. Repeat with zero and one keeper and verify callback cadence does not visibly skip/age the path.
- Retry and change scenario while the ball is reset; confirm the first displayed path corresponds to the reset ball rather than a cached chunk.
- With another overlay active, toggle BallPrediction off and verify that other overlays remain. If that cannot be shown, keep the MCT checkbox unavailable.
- Confirm the lesson timer, ball state, car state, and controller input are unchanged by the feature; confirm Return/session loss restores the prior CVar only when MCT still owns the applied value.

## Source references

- Pinned plugin implementation: [BallPredictionPlugin.cpp](https://github.com/bakkesmodorg/BakkesMod2-Plugins/blob/f412cd66ce0735be4aeb21ca41325337eb959aa0/BallPredictionPlugin/BallPredictionPlugin.cpp) and [BallPredictionPlugin.h](https://github.com/bakkesmodorg/BakkesMod2-Plugins/blob/f412cd66ce0735be4aeb21ca41325337eb959aa0/BallPredictionPlugin/BallPredictionPlugin.h).
- MCT-pinned SDK declaration: [GameWrapper.h](https://github.com/bakkesmodorg/BakkesModSDK/blob/479e8f571cf554b25f4eeb64d611dec4133edcaf/include/bakkesmod/wrappers/GameWrapper.h#L94-L100).
- Frozen MCT sources: `work/reviewed-training/plugin/CMakeLists.txt:26–29` (SDK pin), `work/reviewed-training/plugin/include/NativeCareerLayout.h`, `work/reviewed-training/src/my_career_training/bridge.py`, `work/reviewed-training/src/my_career_training/adapter.py`, and `work/reviewed-training/src/my_career_training/game_worker.py` (line references above).
