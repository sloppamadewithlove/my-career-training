# Native menu diagnostic: source-only research tool

This probe is a diagnostic step toward the requested native Rocket League
offline menu. It does **not** change Rocket League's menu, button actions,
files, or assets. The player asked to hold the next installer until a native
menu solution is verified; adding this source code does not lift that hold.

## Using the diagnostic in a developer build

Open **Settings → Diagnostics → Start menu capture** in an owned offline
session. The career window closes so Rocket League's own menus can be observed.
Navigate its menu and submenus with the normal mouse or controller. The capture
saves locally after two minutes or 1,000 events. Reopen the career window and
return to Diagnostics to read the result, stop and save sooner, or cancel.
The current public preview does not contain these controls.

The diagnostic does not change native buttons or route clicks. It records the
menu names and supported event names that actually occur; missing events are
also useful evidence. No report is uploaded automatically.

## Collection contract

- The player must explicitly start capture in Settings or issue
  `mct_probe_start` while the My Career launcher owns the Steam Rocket League
  process, the bridge state is fresh, and the game is offline. UI requests
  enter the game's thread through the existing local request queue.
  `mct_probe_stop` saves early; `mct_probe_cancel` discards the capture.
- The plugin supplies the current bridge session nonce, `GetPsyBuildID()`,
  BakkesMod version, and an SHA-256 computed from the running process's
  executable file using Windows SHA-256 support. Hashing happens only at
  explicit capture start, never on each tick. It streams a read-only handle,
  rejects files over 2 GiB, checks a ten-second deadline between chunks, and
  rechecks the session after hashing. A hash failure prevents capture. A slow
  operating-system read may itself outlast the between-chunk deadline.
  The hash is file identity, not proof that any native memory layout is safe.
  The portable collector still permits a missing hash for legacy callers; the
  Windows plugin requires a computed hash before it starts.
- `MyCareerTraining.cpp` registers both commands and the allowlisted named
  BakkesMod hooks. Each game tick checks ownership, bridge freshness, offline
  state, session nonce, and build ID. A failed check immediately erases the
  in-memory trace and prevents export. Hooks do not bypass this gate.
- Schema 2 records the current top-menu name, the full SDK menu-stack vector
  (at most 32 short identifiers), an `in_game` boolean, UTC
  timestamp, and the occurrence of an allowlisted named event. The initial
  event list is `menu_stack_transition`,
  `Function TAGame.GFxData_MenuStack_TA.ButtonTriggered`,
  `Function TAGame.GFxData_MenuStack_TA.PushMenu`,
  `Function TAGame.GFxData_MenuStack_TA.PopMenu`, and
  `Function TAGame.GFxData_MenuTree_TA.OnChildNodeClicked`. The current
  integration uses named BakkesMod hooks without interpreting `void*`
  parameters. A named hook's presence in source does not prove the current
  game fires it.
  A stack change is recorded even when its top entry stays the same. Stack
  order is preserved exactly as the SDK returned it; the collector does not
  infer parent/child ownership of rendered buttons from these names.
- Collection stops after 120 seconds or 1,000 events and automatically saves
  only if the owned offline scope is still valid. The operator may stop sooner
  or cancel. A failed guard immediately erases the in-memory trace and removes
  the event hooks without exporting. The interface distinguishes a saved
  report, a cancelled capture, lost scope and an export error.
- Export uses `LocalBridge::atomicWrite` to the fixed filename
  `native-menu-probe.json` inside the bridge's per-user directory. The command
  accepts no output path. Each successful save replaces the previous report;
  cancellation or a failed capture does not delete an older report. Check its
  timestamps and session before using it as evidence. The probe does not request account/profile fields,
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
