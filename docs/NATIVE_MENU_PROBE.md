# Native menu probe: source-only research tool

This probe is a diagnostic step toward the requested native Rocket League
offline menu. It does **not** change Rocket League's menu, button actions,
files, or assets. The player asked to hold the next installer until a native
menu solution is verified; adding this source code does not lift that hold.

## Collection contract

- The player must explicitly issue `mct_probe_start` while the My Career
  launcher owns the Steam Rocket League process, the bridge state is fresh,
  and the game is offline. `mct_probe_stop` is the only export action.
- The plugin supplies the current bridge session nonce, `GetPsyBuildID()`,
  BakkesMod version, and the executable SHA-256 if the launcher has actually
  computed one. An unknown executable hash is recorded as JSON `null`, never
  guessed. The start command fails when session or build identity is absent.
- `MyCareerTraining.cpp` registers both commands and the allowlisted named
  BakkesMod hooks. Each game tick checks ownership, bridge freshness, offline
  state, session nonce, and build ID. A failed check immediately erases the
  in-memory trace and prevents export. Hooks do not bypass this gate.
- Allowed records are the current top-menu name, an `in_game` boolean, UTC
  timestamp, and the occurrence of an allowlisted named event. The initial
  event list is `menu_stack_transition`,
  `Function TAGame.GFxData_MenuStack_TA.ButtonTriggered`,
  `Function TAGame.GFxData_MenuStack_TA.PushMenu`,
  `Function TAGame.GFxData_MenuStack_TA.PopMenu`, and
  `Function TAGame.GFxData_MenuTree_TA.OnChildNodeClicked`. The current
  integration uses named BakkesMod hooks without interpreting `void*`
  parameters. A named hook's presence in source does not prove the current
  game fires it.
- Collection stops after 120 seconds or 1,000 events. The operator may stop
  sooner. A bounded trace is retained in memory until explicit stop, but is
  erased if the offline guard fails before then.
- Export uses `LocalBridge::atomicWrite` to the fixed filename
  `native-menu-probe.json` inside the bridge's per-user directory. The command
  accepts no output path. The probe does not request account/profile fields,
  controller input, chat, arbitrary event strings, game memory addresses,
  hook parameters, or filesystem paths. Menu names and identity strings are
  restricted to short printable identifiers. Review the local trace before
  sharing it because the game's own menu names have not been verified on the
  player's current build.

The source contract and limits are in
`plugin/include/NativeMenuProbe.h`; portable scope, input filtering, bounds,
and export tests are in `plugin/tests/native_menu_probe_tests.cpp`. The plugin
hook and command wiring is in `plugin/src/MyCareerTraining.cpp`.

## What the trace can establish

An opt-in trace from the player's current Steam build can show which
menu-stack transitions and named functions occur around Play, a submenu,
pause, and returning to the main menu. It may show that the expected hooks
never fire, which is useful evidence too. A read-only trace cannot prove who
owns the rendered GFx buttons, whether a click can be safely rerouted, or
that a future build can restore the original menu. Those still need direct
current-build inspection and Windows gameplay tests before any installer is
released as the requested native-menu mod.

The implementation and evidence boundary are documented in
`docs/NATIVE_MENU_RESEARCH.md`. No trace exists until a real Windows game run
records one; portable tests only verify the probe's own behavior.
