# CONTROLLER-EVIDENCE-01 — controller visuals, logical actions, and coaching claims

## Scope and conclusion

Static review of the frozen MCT candidate, after reading INPUT-COLLISIONS-01,
NATIVEUI-01, ACCESSIBILITY-01, MECHANICAL-PLUGIN-01, and OUTCOMES-01. I also
checked the candidate's installed `rlbot_flatbuffers` 0.19.0 type stub and
the public RLBot schema, plus the BakkesMod SDK declaration pinned by the
candidate. No private controller bindings, game input, raw device state,
account data, build, test, or install action was used. Public primary-source
pages and one public repository ref were read; no packages were fetched.

MCT has three separate controller-related surfaces: an optional third-party
Controller Overlay Pro display, fixed lesson control hints, and lesson/ghost
text derived from RLBot packet input fields. The latter is **game-reported
logical action telemetry**, not a raw controller capture. No reviewed MCT path
reads or configures a game deadzone, identifies the physical control that
produced an action, or verifies that a selected prompt profile matches the
player's effective bindings.

## Current MCT paths

| Surface | What the source does | Evidence boundary |
|---|---|---|
| **Controller Overlay Pro (#707)** | MCT's package handler pins a third-party package version 1.0.7; in an eligible owned offline training session, its host reads/writes `xco_x`, `xco_y`, `xco_scale`, `xco_skin`, and `xco_enabled`. The requested skin is hard-coded to `ps4`; the per-lesson “Show controller” preference controls overlay visibility (`controller_overlay.py:18-35`; `ControllerOverlaySession.h:41-54, 109-113, 151-169`; `MyCareerTraining.cpp:1452-1476`; `NativeMatchLayout.h:590-617`). | Career UI describes the external plugin as providing the visual and DS4 raw-input support, and says MCT does not draw or infer a controller (`CareerUI.cpp:649-652`). That comment does not establish what the plugin samples, what its visual means for other device types, or that its values match RLBot `last_input`. MCT itself receives no raw axes/buttons from this integration. |
| **Lesson HUD** | The Power Shots card shows static text for D-pad shuffle/mirror/previous/next, “RESET: EXISTING GAME BINDING,” and “GHOST: PAUSE MENU ONLY.” It does not display current analog axes or choose prompts from controller identity (`CareerUI.cpp:735-750`; `TrainingHudModel::fromState`, `TrainingLessonInput.h:320-388`). The external-overlay checkbox is separate from the Lesson HUD action-prompt toggle (`NativeMatchLayout.h:590-617`). | These hints are not dynamically remapped glyphs. `binding_profile` selects the labels Game actions, Keyboard, PlayStation, or Xbox in settings (`NativeCareerLayout.h:2468-2480`; `Main.qml:599`); the frozen source search found no consumer that sends this choice to the gameplay HUD, external overlay skin, or controller model. The in-game hint remains D-pad text. |
| **Live action summary** | `normalized_packet()` copies `throttle`, `steer`, `pitch`, `yaw`, `roll`, `jump`, `boost`, and `handbrake` directly from `player.last_input` (`adapter.py:137-150`). When the action aid is on and the native Power Shots card is not selected, the RLBot renderer lists field names whose absolute value is greater than 0.2 (`game_worker.py:1426-1429`). | The live line omits sign and magnitude. “Steer” does not say left/right; “Pitch” does not say nose-up/down; “Throttle” does not distinguish reverse/forward. Smaller nonzero analog values are hidden. It is not a physical-button display. |
| **Ghost action summary / controller model** | The recorded-ghost path can show active logical action labels and signed sample values; it explicitly says “Recorded logical actions, not raw controller capture” (`game_worker.py:1473-1490`). `controller_display()` marks `physical_button_capture` false, validates finite analog values in `[-1,1]`, and marks displayed action labels only above 0.05 (`training/controller.py:42-89`). | Its default model is a PlayStation drawing convention: throttle/reverse→R2/L2, jump→Cross, boost→Circle, handbrake→Square, steer/yaw/roll→left-stick X, pitch→left-stick Y (`training/controller.py:13-21`). These are explanatory defaults, not observed hardware mappings. When multiple logical axes share one drawn axis, the strongest absolute value wins instead of combining them. The current worker calls ghost `snapshot()` without a binding map (`game_worker.py:790-792, 1074`); its saved `binding_profile` is not passed into this model. |

The third-party overlay package handler records plugin 707's archive/DLL
identity and expected CVar names, but the plugin's implementation was not
inspected in this task (`controller_overlay.py:18-35`). A checkbox or a
verified CVar readback proves only that MCT requested and read back its
visibility/layout settings. It does not prove the overlay is displaying raw
device state or that MCT's action labels share that data source.

## RLBot input semantics and MCT's thresholds

The official RLBot schema names `PlayerInfo.last_input` as the player's last
controller input and gives the `ControllerState` channel directions: throttle
−1/full reverse to +1/full forward; steer and yaw −1/left to +1/right; pitch
−1/nose-down to +1/nose-up; roll −1/left to +1/right. The schema does not
define the physical device, active binding, deadzone, response curve, raw-vs-
filtered stage, or button that produced those values. The MCT adapter copies
the fields without its own remap or deadzone calculation. The engine rejects
analog values outside `[-1,1]`; the controller model instead marks the input
unobserved if an analog field is outside that range. Both are validation,
not calibration (`adapter.py:148-150`; `engine.py:347-370`;
`training/controller.py:50-59`).

No `deadzone`/`dead zone` read or parameter was found in the reviewed MCT
Python/native code. The numeric cutoffs below are separate display/event
thresholds; none can be described as Rocket League's input deadzone:

| Purpose | Current threshold | What it means |
|---|---:|---|
| Live `You:` line | `abs(value) > 0.2` | Small analog values disappear from this text; it prints only action names. |
| Ghost active-action labels | `abs(value) > 0.05` | Recorded logical values above this display cutoff appear with signed values. |
| Speed Flip diagonal observation | Both components of `dodge_dir` at least `0.15`, **or** both absolute pitch and yaw at least `0.15` | A game-reported dodge direction or two logical axes met MCT's detector cutoff; no physical stick direction is established. |
| Speed Flip opposing-pitch event | Later pitch sign differs from pitch saved at dodge start, and later absolute pitch is at least `0.3` | Opposing game-input pitch was observed; cancellation effectiveness is not proven. |
| Possible-backflip coaching suggestion | Pitch is greater than `0.3` at dodge onset | Heuristic suggestion only; the path does not verify a backward dodge from `dodge_dir`. |

Source: `game_worker.py:1426-1429`; `training/controller.py:63-75`;
`engine.py:163-165, 899-964`. These values are MCT display or event rules,
not measurements of a player's hardware deadzone.

`dodge_dir` is a separate game-state vector. RLBot describes it as the unit
direction of the latest dodge and `(0,0)` for a stall; it is not the player's
raw stick vector. MCT uses it as one way to classify a diagonal dodge and logs
the direction with the dodge event (`adapter.py:143-150`; `engine.py:909-938`).
The schema does not specify a mapping from these components to a named pad
button or physical stick axis, so coaching should say “game-reported diagonal
dodge observed,” not “you pressed the upper-left stick direction.”

MCT's instructions and event evidence are also distinct. Speed Flip stages ask
for a jump, diagonal dodge, and opposing pitch; the event detector observes
logical channels and game state, not physical button order. Its opposing-pitch
note explicitly does not establish cancellation effectiveness. For Aerial &
Air-Roll, `roll` is validated as an action field, but it is not used by the
lesson's success predicate; ordered gates and landing can complete without a
verified air-roll control input (`coaching.py:8-10,37-42`;
`engine.py:347-370,899-964`; OUTCOMES-01). The name “Air roll” in the default
controller drawing is therefore not proof that an air-roll button was pressed
or that the technique was mastered.

## Unsupported assumptions and safe coaching language

- Do not turn `last_input.pitch = +0.4` into “your stick moved up 40%.” It is a
  signed game action channel under the schema's nose-up convention; the
  physical axis, inversion, remap, and curve are unknown.
- Do not use `binding_profile` as evidence of actual binds or controller type.
  It is a label selection. The external overlay's requested `ps4` skin is not
  updated when the profile changes. This is a wrong-glyph risk, not proof that
  a particular runtime image is wrong.
- Do not call the 0.05, 0.15, 0.2, or 0.3 rules deadzones. They serve different
  ghost-display, live-display, and event-classification purposes.
- Do not call a logical `roll` sample an air-roll button press. Air-roll
  controls can be bound to buttons or axes, and MCT does not read the user's
  effective binding map. A default PS layout that assigns roll to left-stick X
  can conflict with a user's layout.
- Do not describe the diagonal detector as the actual physical direction of a
  thumbstick. It accepts either the game's dodge vector or simultaneous
  pitch/yaw action values.
- Phrase input findings as **“Rocket League/RLBot reported [logical action]
  [sign/value] at this sample”** or **“MCT observed [game-state event]”**.
  Do not claim a raw physical press, configured deadzone, correct binding,
  effective dodge cancellation, or mastered technique from those fields.

The Mechanical Plugin review adds a relevant but separate caveat: a third-party
input transformer can modify a `ControllerInput` struct, and that report leaves
the packet's pre-/post-hook relationship unknown. MCT does not record such a
transformer's identity or configuration. Do not assume the packet values are
unmodified physical intent when an external transform may be active
(MECHANICAL-PLUGIN-01).

## Minimal future acceptance matrix

These are future verification cases, not tests or game observations performed
in this research:

| Case | Evidence to collect | Pass condition for coaching |
|---|---|---|
| **Device and label selection** | In an owned offline session, use keyboard/mouse, Xbox/XInput, PlayStation/DS4, and one deliberately remapped control set. For each, record only consented test inputs and the MCT input/profile/overlay outputs. | Show the effective game action or generic wording when type/binding is unknown. Never state that selecting a label profile changed the game bind. Verify external overlay skin/glyph against detected device or show a clear generic fallback. |
| **Signed axes and deadzone sweep** | With a known temporary test bind, sweep each available logical axis from neutral through small positive/negative values to endpoints; separately record raw device values only if a supported, consented source exposes them. Include values around 0.05, 0.15, 0.2, 0.3, and 1.0 in both signs. | Keep raw hardware, game-reported action, and MCT display threshold as separate columns. Measure a deadzone only from the explicit raw-to-game transition; do not infer it from MCT labels. Confirm signs use RLBot's action convention. |
| **Digital actions** | Press/release jump, boost, and handbrake under known mappings; compare packet booleans with MCT labels and separate game-state flags. | Say “jump input reported” separately from “car jumped.” Show no physical button name unless the active mapping was actually resolved. |
| **Dodge direction** | Trigger forward, backward, left, right, diagonal, and stall dodges; record `has_dodged`, `dodge_dir`, pitch/yaw sample values, gaps, and resulting coaching event. | Distinguish game dodge direction from physical stick direction. Mark missing/gapped evidence uncertain and ensure a possible-backflip hint is not presented as a verified backward dodge. |
| **Pitch reversal / Speed Flip** | Sweep the starting dodge pitch and later pitch across zero and the ±0.3 threshold with same-direction and opposite-direction controls; record car motion separately. | Report the current detector as “opposing pitch observed.” Do not claim cancel success from sign reversal alone. Check zero starting pitch, held directional input, and telemetry gap cases. |
| **Roll / air-roll lesson** | Test roll left/right through the user's known button and axis mappings, with and without yaw, and with a route that completes gates but uses no roll input. | Display the logical roll action accurately; keep the lesson result independent until roll/orientation is a declared, measured requirement. Never equate gate completion with air-roll mastery. |
| **Overlay source separation** | Toggle the external overlay while sampling RLBot `last_input`; compare only with a documented overlay data source and known device mapping. | Treat overlay art/state and MCT packet values as separate telemetry until their acquisition stage and mapping are independently established. Verify the hard-coded `ps4` request and all supported device fallbacks. |

## Source fingerprints and primary references

Frozen-candidate SHA-256 values and byte counts used in this report:

| Source | Bytes | SHA-256 |
|---|---:|---|
| `plugin/src/CareerUI.cpp` | 46,493 | `35b9c68b6eaeea0c3a81ca12563508271a390ee407b85b2ec08199dc3603e29c` |
| `plugin/include/ControllerOverlaySession.h` | 10,805 | `8289082e59c226e08ebe2ec06c42e4f1f848958c916367745fda4a695e992482` |
| `plugin/include/TrainingLessonInput.h` | 20,415 | `6cfa4f039ce965d5c9df7d64938ef70b0926b9055951388c2f83395d376d45d5` |
| `plugin/include/NativeCareerLayout.h` | 167,035 | `17d2ec0a82c79fad1949715ad62840bcace4177cbbe137da3aa675289109eb78` |
| `plugin/include/NativeMatchLayout.h` | 44,432 | `a986f0ed827f11ef2716c8fc6bb196d55f822cc22c6b5316b0fde0bb278a8d53` |
| `plugin/src/MyCareerTraining.cpp` | 89,835 | `edc7bf5a6dc7ca0cff34ac694fb72fe71fa26dfe1fd4607d512f3b321a1a9279` |
| `plugin/CMakeLists.txt` | 13,779 | `489e7323fddf44634321a3c341dc34aa54cead9e432c71aa2bff7bb3eea148b7` |
| `src/my_career_training/adapter.py` | 12,018 | `98d1f4612967eda756b21857dfd198a3a12e4a211684067a248b9a829b74285c` |
| `src/my_career_training/training/controller.py` | 4,400 | `899dcb25e1da465af2b1959b02ac66cfd947ee0d5e6864ef79e18ae23ccb6723` |
| `src/my_career_training/training/engine.py` | 63,844 | `37028379a268d6f6e19d42b32a9e3c20778ed4f41d87bfbd3bc76955c61c602a` |
| `src/my_career_training/training/coaching.py` | 5,848 | `3b8336a54f4997479f1ce56f787377eb748683a117c8ba24a82e6e3c03b25d3b` |
| `src/my_career_training/training/coach.py` | 25,430 | `0807fda8daf33ae67a9d1f31ccf93ecb10acccd21bb7efa3d9fb8a7fec905325` |
| `src/my_career_training/training/recordings.py` | 22,459 | `8effb8f438b39c4abe4901d683dc6e5e0424baa7f696dc35143b282cc5aa96f1` |
| `src/my_career_training/game_worker.py` | 90,814 | `2e3982dfc352e4fafcd667898b3cb1f76538b61447c2b6e47adc6d9f862e89c2` |
| `src/my_career_training/controller_overlay.py` | 13,002 | `27b255ac1cbafc37d39358922aa349c217d3012db075d40d5d749f3f38293e95` |
| `src/my_career_training/ui/Main.qml` | 62,388 | `8f9ee7df53346dfc79f3043885b2f9a1d9b38ab8e9757c70d2ad902585978d8c` |
| `src/my_career_training/bridge.py` | 139,135 | `ac502d1f19810baca479a534aa766a6afbea7ba57a405452835cc9dcff379ac2` |
| `src/my_career_training/storage.py` | 8,410 | `3a291463f8ffdbab63adc4197a5b957413452aa011d4491895c722c151dd10de` |
| `src/my_career_training/bootstrap.py` | 19,049 | `82fef12f0d472ed0927996ff691e4b9babb1884ba9f8c02df4315b49557ca7ec` |
| Installed local `rlbot_flatbuffers` 0.19.0 `__init__.pyi` | 162,320 | `5a89d86c709198b9b5748d67cf9fd6045c9c5bc445f13cd7222719fa35e3ca1e` |

Context-report hashes read:

| Report | Bytes | SHA-256 |
|---|---:|---|
| `input-collisions-01.md` | 12,157 | `2bf7b0458bfe3be1e849d117cfa65d2e158bcd08372515dc62676c9f0434bd7f` |
| `nativeui-01.md` | 12,234 | `5dc57bef9d9a9fe03e5061eee0f798551f19d16d39308a721c4d9bb5cbf942d6` |
| `accessibility-01.md` | 10,767 | `3ee5f2101df76d895fca8f83d7d05b7eaa22684d42e4df47cba989193342aac6` |
| `mechanical-plugin-01.md` | 11,381 | `b0a45df2037c5fe59fa7baed75029e1b60417fed852d6beac95e6252828937f3` |
| `outcomes-01.md` | 7,438 | `d50d8ea3dfb57a5788b492af4467681e27cd232e6d126998b46698b83133d2e0` |

Primary references:

- RLBot's [official `gamedata.fbs` schema at commit `e27de77b4ae2cd9fef5bfea53994be7e24454b47`](https://github.com/RLBot/flatbuffers-schema/blob/e27de77b4ae2cd9fef5bfea53994be7e24454b47/schema/gamedata.fbs) documents `ControllerState`, `PlayerInfo.last_input`, and `dodge_dir`. The installed local generated stub is version 0.19.0 and is fingerprinted above.
- MCT pins BakkesModSDK commit `479e8f571cf554b25f4eeb64d611dec4133edcaf` (archive SHA-256 in `plugin/CMakeLists.txt:26-30`). Its public [GameWrapper.h at that exact commit](https://github.com/bakkesmodorg/BakkesModSDK/blob/479e8f571cf554b25f4eeb64d611dec4133edcaf/include/bakkesmod/wrappers/GameWrapper.h) declares `IsKeyPressed(int)`; the declaration alone does not expose raw pad axes or device identity.
- Rocket League's [Season 24 patch notes v2.76](https://www.rocketleague.com/news/rocket-league-s24-patch-notes-v276/) list updated keyboard/mouse defaults and a free-look camera mode available to controller players. They do not reveal any particular player's effective bindings; no such bindings were inspected here.

Static source and API declarations do not prove runtime dispatch order, hardware
filtering/deadzones, controller detection, rendered glyph correctness, or how a
third-party overlay's sampled values relate to RLBot packets.
