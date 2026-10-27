# MECHANICAL-PLUGIN-01 — input-transform plugin and MCT boundary

## Scope and result

Static review of the public `BakkesMod2-Plugins` checkout at
`f412cd66ce0735be4aeb21ca41325337eb959aa0` (clean at that commit), limited to
`MechanicalPlugin/mechanicalplugin.cpp` and `.h`, plus the frozen MCT sources
listed in the receipt. The plugin is an optional controller-input transformer
gated to BakkesMod Freeplay. It changes `ControllerInput` fields in a
`Car_TA.SetVehicleInput` hook; it does not set car physics or ball state.

The plugin does not provide a command, status event, session handshake, or
outcome record. MCT's current training configuration is an owned Soccar match,
not Freeplay. Its visible assistance preferences control presentation and
workflow, not mechanical inputs. Setting `mech_enabled` alone therefore cannot
support an MCT checkbox that claims mechanical assistance is active.

No code, build, test, network, install, or game action was performed. Hook
delivery, BakkesMod teardown, and the relationship between intercepted inputs
and packet `last_input` remain runtime questions.

## Registration, hooks and actual gates

The plugin declares version `0.1` and `PLUGINTYPE_FREEPLAY`
(`MechanicalPlugin/mechanicalplugin.cpp:8`). It registers no `registerNotifier`
command; its exposed settings are cvars and event hooks. On load it initializes
`mech_enabled` false, registers and binds the control cvars, then hooks the
Tutorial event names
`TAGame.GameEvent_Tutorial_TA.OnInit` and `.Destroyed` (`:15-46`).

There are three distinct gates for input changes:

1. `OnFreeplayLoad` installs the `TAGame.Car_TA.SetVehicleInput` caller hook
   only if `mech_enabled` is true (`:107-112`).
2. A `mech_enabled` value change installs the caller hook only when the new
   value is true **and** `IsInFreeplay()` is true; otherwise it calls
   `UnhookEvent` (`:119-129`).
3. The callback itself returns unless `IsInFreeplay()` is true (`:53-55`).

`PLUGINTYPE_FREEPLAY` is plugin classification; there is no per-command
permission flag here. The actual gates are the hook-installation conditions and
the callback's explicit Freeplay test. The input hook receives a `CarWrapper`
caller, but the callback does not inspect it; it edits the supplied
`ControllerInput*` for any invocation that reaches the hook while the gate
passes (`:53-105`). It does not explicitly restrict changes to the local Human
actor.

`OnFreeplayDestroy` unhooks `Car_TA.SetVehicleInput` (`:114-117`). `onUnload()`
is empty (`:49-50`): the plugin shows no explicit hook removal or restoration
there. It also has no local hook-installed flag, so deduplication of repeated
hook attempts depends on BakkesMod behavior. Those lifecycle semantics require
runtime verification; no leak or duplicate-hook outcome is asserted here.

## Cvars and implemented control changes

All cvars are registered with default values shown below; the control limits
are registered with a 0..1 range (`:33-46`). The table lists the available controls (`:64-105`); execution order is
described below it:

| Cvar | Default | Effect in `ControllerInput` |
|---|---:|---|
| `mech_enabled` | `0` | Installs/uninstalls the input hook through its value-change callback. |
| `mech_steer_limit` | `1` | Clamps analog steer to `±abs(limit)`. |
| `mech_throttle_limit` | `1` | Clamps analog throttle. |
| `mech_yaw_limit` | `1` | Clamps analog yaw. |
| `mech_pitch_limit` | `1` | Clamps analog pitch. |
| `mech_roll_limit` | `1` | Clamps analog roll; also bounds roll produced by `mech_hold_roll`. |
| `mech_disable_handbrake` | `0` | Forces Handbrake false. |
| `mech_disable_jump` | `0` | Forces Jump and Jumped false. |
| `mech_disable_boost` | `0` | Forces ActivateBoost and HoldingBoost false. |
| `mech_hold_boost` | `0` | Forces ActivateBoost and HoldingBoost true. |
| `mech_hold_roll` | `0` | Copies bounded Yaw into Roll, then sets Yaw to zero. |

The analog clamp uses `max(lower, min(value, upper))`; the limit is wrapped in
`abs()` (`:11-13, 95-103`). `mech_hold_boost` is processed after
`mech_disable_boost`, so if both are enabled the later hold operation wins.
There is no `hold_jump` option. `mech_hold_roll` repurposes the current Yaw
value as Roll; it does not set a car rotation directly. The final analog
clamps run after the button and yaw-to-roll edits.

The code writes no car location, velocity, orientation, boost amount, or ball
field. It only edits the intercepted input struct; any movement or ball change
is an indirect consequence of the game's later physics. No timer or delayed
work is registered. The transform is reapplied on each hooked
`SetVehicleInput` call, but there is no scheduled repeat or reset trigger.

## MCT lesson, assistance and recording effects

The MCT catalog's default assistance settings are ghost, explanations, action
display, controller overlay, timing, auto-reset and playback speed
(`training/catalog.py:5-13, 16-45`). The bridge persists those settings and
sends preference updates (`bridge.py:1407-1418`); they do not install this
plugin or transform player controls. A source search of the frozen MCT Python
and native UI/host sources found no `mech_*` or `MechanicalPlugin` integration.

MCT's mechanic lessons can be affected by these transforms even though the
plugin does not author their scenarios. Speed Flip observes jump and game
actions such as pitch/yaw for diagonal dodge and opposing pitch
(`training/engine.py:899-965`); clamping, disabling jump, or changing yaw/roll
can alter the observed sequence. Fast Aerial, Flip Reset, and Ground Dribble &
Flick depend on jump/boost and physical outcomes; disabling or forcing those
inputs changes the opportunity to perform the lesson. Aerial & Air-Roll and
Flight Recovery can be materially altered by axis clipping or yaw-to-roll
mapping. Power Shots still grades its launch/touch/target/score path, but input
changes can change whether the Human reaches that outcome. These are effects
on a player's controls and opportunity, not new MCT lesson evidence.

The MCT adapter copies `player.last_input` into the observed action map
(`adapter.py:133-150`), and the recorder stores that map with car/ball samples
(`training/recordings.py:204-260`). The source does not establish whether the
packet field reflects the pre-hook or post-hook value for this BakkesMod
callback. Either way, MCT recording metadata has no Mechanical plugin version
or cvar snapshot (`recordings.py:204-277`). Recording compatibility compares
lesson version, game/framework, hitbox, map, mutators, start state, time base
and lesson variant but not mechanical assistance (`:145-172`); personal-best
selection does not filter it either (`:175-198`). An external transform could
therefore make an assisted run appear compatible with an unassisted run unless
the setting is captured and included in compatibility.

The owned MCT training match is configured as `GameMode.Soccar` and sets
`freeplay=training and capture is not None` (`adapter.py:107-119`). Ordinary
lesson training has no capture, and the capture path is separate. Do not infer
that the plugin's Freeplay hooks or `IsInFreeplay()` gate are active in the
owned MCT match merely because the plugin type says Freeplay. The correct
runtime state has not been observed.

## Smallest bounded adapter contract

Before a checkbox can say **Active**, it needs a session-scoped acknowledgement
from the component that actually owns the input transform. The minimum
contract should carry the MCT `session_id`, validated Human actor index, a
fixed assistance profile ID/version, and explicit effective values. It should
return an acknowledgement with the same session and actor, the profile
version, and the effective setting snapshot only after the handler is armed
in a supported owned session. A requested cvar value, plugin-loaded flag, or
`PLUGINTYPE_FREEPLAY` tag is not an activation acknowledgement.

Keep the transform bounded to an enumerated profile with a documented order
for conflicting options; apply it only to the Human in the owned session;
default it off; and clear/unhook it on disable, session change, Return and
unload. If the Freeplay-only host cannot confirm the owned Soccar context, show
the option as unavailable rather than active. Record the profile identity and
effective values with each attempt, retain observed input separately from any
requested transform, and include that identity in replay/ghost compatibility.
Keep these controls distinct from current display/help assistance.

## Tests and acceptance evidence needed before activation

These are future checks, not tests run in this research pass:

- Unit-test pass-through defaults, each axis bound, disabled buttons, held
  boost, yaw-to-roll conversion, and conflicts such as disable-boost plus
  hold-boost. Include exact lower/upper inputs and values outside the range.
- Test the lifecycle state machine: enabled while outside Freeplay, entering
  Freeplay while already enabled, enable/disable while in Freeplay, Tutorial
  destruction, unload, repeated load notifications, and no post-cleanup input
  mutation. Verify one handler only.
- Test actor scoping with a Human and a bot: only the requested Human input is
  transformed. The current callback ignores its `CarWrapper` caller.
- In an isolated owned Soccar session, require an acknowledgement proving the
  transform is actually active; verify unsupported context cannot report
  Active and that Return/retry/new session clears stale state.
- Record an assisted and an unassisted trace with the same setup. Verify the
  effective profile is stored, compatibility rejects unlike assistance
  profiles, and MCT's observed actions/outcome are not presented as raw
  physical controller input or unaided technique evidence.
- Recheck lesson-specific event claims under the selected profile, especially
  Speed Flip input order, Fast Aerial jumps/boost, and Air-Roll axis mapping.

## Source fingerprint receipt

The public plugin checkout is pinned at
`f412cd66ce0735be4aeb21ca41325337eb959aa0`; selected files are unchanged at
that commit. SHA-256 and byte lengths:

| Source | Bytes | SHA-256 |
|---|---:|---|
| `BakkesMod2-Plugins@f412cd66/MechanicalPlugin/mechanicalplugin.cpp` | 5,200 | `76e196e857c62b46afc4d2086e9295d3326b7691fa34143ce353ecb6817b01a0` |
| `BakkesMod2-Plugins@f412cd66/MechanicalPlugin/mechanicalplugin.h` | 893 | `74424cdd07e9e1653d404cda2e2372d166cf0e0587b9cb976762b1786c6fa945` |
| `src/my_career_training/training/catalog.py` | 9,097 | `1c05fe5ed75296c5c75848f26e7c01a77160b16938c76c55e15536828f58fe73` |
| `src/my_career_training/training/engine.py` | 63,844 | `37028379a268d6f6e19d42b32a9e3c20778ed4f41d87bfbd3bc76955c61c602a` |
| `src/my_career_training/adapter.py` | 12,018 | `98d1f4612967eda756b21857dfd198a3a12e4a211684067a248b9a829b74285c` |
| `src/my_career_training/training/recordings.py` | 22,459 | `8effb8f438b39c4abe4901d683dc6e5e0424baa7f696dc35143b282cc5aa96f1` |
| `src/my_career_training/bridge.py` | 139,135 | `ac502d1f19810baca479a534aa766a6afbea7ba57a405452835cc9dcff379ac2` |
| `src/my_career_training/game_worker.py` | 90,814 | `2e3982dfc352e4fafcd667898b3cb1f76538b61447c2b6e47adc6d9f862e89c2` |
