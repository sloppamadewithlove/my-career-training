# REBOUND-PLUGIN-01 — pinned BakkesMod rebound command

## Scope and result

Read-only inspection of the public `BakkesMod2-Plugins` checkout at commit
`f412cd66ce0735be4aeb21ca41325337eb959aa0`, limited to `ReboundPlugin.cpp` and
`ReboundPlugin.h`. The checkout was clean at that commit. The plugin is a
manual Freeplay shot generator: the `rebound_shoot` notifier aims the current
ball at a high point near one of two goals, then writes the ball's velocity
and angular velocity. It does not define an MCT lesson, a timed repeat, a
retry/reset lifecycle, a success condition, or a measurement result.

No build, test, game launch, plugin installation, network action, or runtime
command was performed. Conclusions about wrapper calls and Freeplay gating are
source-only; behavior delegated to the BakkesMod SDK or Rocket League physics
is not certified here.

## Registration, command context, and host calls

`BAKKESMOD_PLUGIN` declares plugin version `0.1` and type `PLUGINTYPE_FREEPLAY`
(`ReboundPlugin.cpp:8`). `onLoad()` registers five cvars and the
`rebound_shoot` notifier (`:10-18`). The notifier has
`PERMISSION_FREEPLAY | PERMISSION_PAUSEMENU_CLOSED` and an explicit
`GameWrapper::IsInFreeplay()` early return (`:18-21, 68`). It obtains the
current `ServerWrapper` from `GetGameEventAsServer()`; it subscribes to no
match event or tick callback.

The command returns without a shot if there are fewer than two goals, no cars,
a null first car, or a null ball (`:23-29`). Otherwise it uses car index 0 and
the current ball location. It does not check a MCT session ID, actor/team
identity, map identity, match phase, or caller-supplied shot identity.

## Goal selection and generated shot

The plugin estimates which goal the car is driving toward by computing
`player location + velocity * 200`; it compares the sum of absolute XYZ
differences to the first two goal locations and chooses the closer one
(`:33-48`). It does not use the car's rotation. The stationary fallback sets
the comparison point to the ball location, but its condition checks
`abs(velocity.X) < 1` twice rather than checking both horizontal components
(`:34-42`). This is a source observation; whether it causes a visible wrong
goal choice depends on the runtime state.

The selected target starts with `GenerateGoalAimLocation(target, ballLoc)`.
The plugin replaces target Z with the goal's Z extent plus
`rebound_addedheight`, then adds `rebound_side_offset` to global X, and asks
`GenerateShot(ballLoc, goalTarget, reboundSpeed)` for the new velocity
(`:49-58`). The height cvar description says “above the backboard,” while the
implementation uses the selected goal extent; there is no explicit backboard
surface intersection test. X offset is always added in the positive global X
direction, independent of selected goal or approach side (`:51-58`).

| Cvar | Default string | Use in the command |
|---|---|---|
| `rebound_shotspeed` | `780` | Passed as the speed to `GenerateShot` (`:12, 56-58`). |
| `rebound_addedheight` | `(300, 1400)` | Added to selected goal Z extent (`:13, 53`). |
| `rebound_side_offset` | `(0, 500)` | Added to target X (`:14, 49, 54`). |
| `rebound_addedspin` | `(-6, 6)` | Read for each of the three angular-velocity components (`:15, 62-64`). |
| `rebound_resetspin` | `0` | When true, calls `BallWrapper::Stop()` before setting new velocities (`:16, 59-60`). |

The height, side-offset and spin defaults are tuple-like strings; the plugin
reads them with `getFloatValue()`. The plugin itself contains no RNG call or
seed. Any random-range interpretation is delegated to the CVar wrapper and is
not established by these two plugin files. In particular, the spin cvar is
read three separate times, so component correlation also depends on wrapper
semantics. The resolved values and any random seed are not logged.

## Mutation, timers, reset, and unload

The notifier does not set a car state or ball position. It optionally calls
`Stop()` on the current ball, then sets its generated linear velocity and
sets angular velocity to a vector whose X/Y/Z values each come from the spin
cvar (`:58-67`). The second `SetAngularVelocity` argument is `true`; its exact
SDK meaning is not declared in this plugin. `Stop()` is called only when
`rebound_resetspin` is enabled; no other existing ball state is explicitly
restored.

The only trigger is explicit invocation of `rebound_shoot`. There is no timer,
automatic repeat, goal/bounce detector, attempt clock, post-shot reset, or
position restoration in this class. `onUnload()` is empty (`:71-73`), so the
plugin supplies no code-side rollback or cleanup action. The plugin source
does not show whether framework-managed notifier/cvar teardown occurs.

## Outcome and measurement boundary

The command produces a velocity write and returns without emitting an outcome
event. It does not observe whether the ball hits a backboard, crosses a marked
target, enters the goal, or changes a team score; it does not timestamp a
touch, retain an attempt record, or compare shot quality. Subsequent movement
is left to the active game's physics. A successful invocation therefore means
only that the source path reached its ball-write calls, not that a playable or
scorable rebound was produced.

## Comparison with MCT Power Shots

MCT's related stable situations are `bouncing-side-pass` and `second-chance`
(`training/scenarios.py:66-79, 123-129`). The first declares a `bounce` launch;
its generated initial state lowers the ball to Z=125 with Vz=-260 for Bronze
and Silver, or uses Z=260 and Vz=-80 for Gold and above (`:232-239`). The
second declares a `backboard` launch; `_launch()` reflects its receiving lane
across the authored back-wall plane, rejects an impact X within the goal mouth
plus the local ball-radius constant, and calculates a velocity toward that
reflected lane (`:223-231`). These are authored initial conditions intended
for the owned match's physics to create the bounce/rebound; they are not proof
that a real ball follows the predicted path. Both scenarios then proceed
through MCT's separate touch, target and team-score success chain
(`training/scenarios.py:328-362`; `training/engine.py:477-579`).

The reset ownership differs. MCT builds a Soccar match with state setting and
writes a full requested ball/car state through its RLBot adapter
(`adapter.py:77-119, 167-203`; `game_worker.py:627-655`). Its normal lesson
configuration sets `freeplay=training and capture is not None`; scenario
training rejects capture and therefore requests `freeplay=False`
(`adapter.py:45-52, 107-119`; `game_worker.py:443-453`). The BakkesMod plugin
is declared Freeplay-only and also exits unless `IsInFreeplay()` is true. The
source does not establish that `rebound_shoot` is available in MCT's owned
Soccar session; do not treat the plugin notifier as a supported scenario
launcher there.

MCT selection carries a stable `scenario_id` and `difficulty` pair. The bridge
persists and forwards that pair, the setup validator requires exactly those
fields, and the worker resolves it to scenario version 3 before match state is
applied (`training/scenario_setup.py:13-22, 94-106`; `bridge.py:1364-1376,
1729-1792`; `game_worker.py:446-453`). The resolved scenario and recording
retain the scenario ID, difficulty and scenario version (`scenarios.py:328-362`;
`training/engine.py:269-280, 1290-1304`). ReboundPlugin has only current-game
state plus cvars; it has no stable scenario, rank, request or attempt identity.

## Requirements before adapting this idea

- Keep the launch inside MCT's owned Soccar state-setting contract. Do not
  depend on a Freeplay-only notifier unless an owned-session runtime check
  explicitly demonstrates that its context is supported.
- Define each bounce/backboard variant with a stable scenario ID/version,
  exact ball and Human starting state, map/mutators, target geometry and
  attempt timeout. Preserve the existing `{scenario_id, difficulty}` request
  identity and recording metadata, rather than importing unversioned cvar
  values as hidden setup.
- Make all variability explicit and reproducible. Resolve any range-valued
  inputs once at setup, record the selected values and seed, and avoid relying
  on undocumented `getFloatValue()` tuple semantics. Specify whether a reset
  replaces ball position, velocity and angular velocity, and ensure retry
  reapplies the whole state.
- Measure the result in the MCT engine: fresh Human touch, ordered target
  crossing and score evidence must remain distinct. A ball launch helper must
  not claim success from a write or from an unverified predicted rebound.

Static acceptance limits remain: verify CVar range behavior and call-level
randomness against the pinned SDK; determine `Stop()` and the boolean
`SetAngularVelocity` semantics; test goal selection with stationary, moving,
and near-zero-X/nonzero-Y cars; and demonstrate the selected ball trajectory,
target crossing and score under the exact owned map/mutators. None of those
runtime checks was performed here.

## Source fingerprint receipt

SHA-256 and bytes for the pinned plugin files and the MCT candidate sources
used above:

| Source | Bytes | SHA-256 |
|---|---:|---|
| `BakkesMod2-Plugins@f412cd66/ReboundPlugin/ReboundPlugin.cpp` | 3,280 | `d4a02c59e13219b78249b180239e36ef52a3f15ca64e9d9b8a287c3ba74c6d9f` |
| `BakkesMod2-Plugins@f412cd66/ReboundPlugin/ReboundPlugin.h` | 237 | `1489e64af53f90fc8575accbc081f843cfad6bef6cc3bb95fc038da1a53d8cf9` |
| `src/my_career_training/training/scenarios.py` | 23,706 | `35714a224aa8765ae62be6fde3df6dc87c088c32d297adcda3795d0bc682d979` |
| `src/my_career_training/training/scenario_setup.py` | 5,265 | `d2421bf8f7ac2508e9f3a65db21b2847a0e147b75cc62a6159a976999536a0fe` |
| `src/my_career_training/adapter.py` | 12,018 | `98d1f4612967eda756b21857dfd198a3a12e4a211684067a248b9a829b74285c` |
| `src/my_career_training/bridge.py` | 139,135 | `ac502d1f19810baca479a534aa766a6afbea7ba57a405452835cc9dcff379ac2` |
| `src/my_career_training/game_worker.py` | 90,814 | `2e3982dfc352e4fafcd667898b3cb1f76538b61447c2b6e47adc6d9f862e89c2` |
| `src/my_career_training/training/engine.py` | 63,844 | `37028379a268d6f6e19d42b32a9e3c20778ed4f41d87bfbd3bc76955c61c602a` |
