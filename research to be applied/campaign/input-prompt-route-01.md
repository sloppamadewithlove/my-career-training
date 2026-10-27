# INPUT-PROMPT-ROUTE-01 — stock Training prompt binding route

## Scope and conclusion

This static review follows the selected `GFX_Hud_SF` ActionScript export used by
HUD-FLOW-01 and the frozen MCT candidate. It reads no player binding file,
controller state, account data, or live game state. The reviewed HUD movie is
1,145,308 bytes (SHA-256
`65535317cbc36b2added175b2ff3c817b9093a2ea83951e08d7349c15c1073ef`); its
containing package is 1,260,419 bytes (SHA-256
`1a6c92191333c5612711b84fa4570d4f088bc977feb7cad58f4ec4343d0e5a59`). These
are the same selected exports fingerprinted in HUD-FLOW-01. No new export was
made for this report.

`TrainingView` declares stock action identifiers, chooses the PC or gamepad
lookup flag from Rocket League's current UI input type, and passes each action
ID to the native `GFxShell_TA.Shell.GetKeyForAction` host call. A returned
string is inserted into localized prompt text; an empty string hides that
whole row. A later text-field pass replaces recognized binding markup with
platform-suffixed gamepad images or a small set of PC images. ActionScript
establishes this call path, but the host resolver's effective-bind choice,
alternate-bind policy, and runtime update timing are native behavior not
verified by these files.

MCT has no corresponding reader for Rocket League's effective `Controls`
binding map. Its existing BakkesMod API usage reads and writes BakkesMod
command binds for MCT's own named keys, while the settings `binding_profile`
only selects how labels are presented. It must not be described as a game-bind
resolver or remapper.

## Stock prompt call chain

| Stage | Source-backed behavior | Evidence |
|---|---|---|
| Build prompt rows | `TrainingView.configUI` adds `ResetTraining`; conditionally adds editor `EditorTestShot`, the paired `TrainingPreviousShot`/`TrainingNextShot` row and `TrainingOpenShotSelectionMenu`, then optional `TrainingToggleShuffle` and `TrainingMirrorShot`. The text templates identify the paired navigation labels and single-action labels. | `TrainingView.as:62-68,227-255` |
| Choose binding family | The HUD passes `isGamepad = (ShellAPI.inputType != InputTypes.PC)`. The enum distinguishes PC, several controller families, and single-controller Switch mode. It does not choose a physical key based on raw device identity in ActionScript. | `TrainingView.as:325-335`; `InputTypes.as:3-18` |
| Resolve action | For each action ID, `TrainingView.updateControlsText` calls `Shell.GetKeyForAction(action, isGamepad)`. The wrapper forwards those two arguments to native `GFxShell_TA.Shell.GetKeyForAction` and returns its string, or `null` if the hook is unavailable. No `ControlsPCBindings` or `ControlsGamepadBindings` row is read on this rendering path. | `TrainingView.as:316-365`; `Shell.as:351-358` |
| Build visible text | Returned strings are tinted and substituted into the localized text template. One action ID fills one placeholder; two IDs fill two placeholders. An empty binding suppresses the entire row, including the paired navigation row if either side is empty. | `TrainingView.as:343-364,722-725` |
| Replace recognized markup | Each prompt text field is registered with `SystemIconManager`. That manager recognizes controller tokens such as `GP_A`, `GP_DPad_L`, trigger, stick, and shoulder names; known PC tokens include mouse buttons, scroll, and Backspace. Controller suffix selection follows the input-type/platform branch, and the manager refreshes text-field substitutions when that type changes. Unrecognized text remains text; these token names are display markup, not action IDs. | `TrainingView.as:299-308`; `SystemIconManager.as:55-66,144-225,228-245,352-440` |

The input-type event originates at the `UIShellHooks` callback into
`ShellAPI`; `InteractionManager` changes its PC/controller interaction mode
and dispatches `INPUT_TYPE_CHANGED`. A visible `TrainingView` responds by
refreshing its controls, and `SystemIconManager` rebuilds the icon suffix map
and reapplies substitutions (`ShellAPI.as:12-16,82-87`;
`InteractionManager.as:360-372`; `TrainingView.as:154-164,642-652`). This is a
source-backed refresh path for an input-type change. It does not prove the
host reports every binding edit as an input-type change or that the selected
art matches a particular physical controller.

There is a special Switch single-controller string for ResetTraining assigned
to `m_resetKeyBinding` during input-type handling (`TrainingView.as:642-652`).
In the selected class, the reset row is later rendered through the same
`GetKeyForAction` loop as the other rows, and `m_resetKeyBinding` is only
assigned and compared, not read into the template. The visible effect of that
special value therefore remains unresolved from this selected source; do not
claim the combined trigger token is what the player sees.

## Rebinding, alternatives, and unresolved native behavior

`TrainingView` subscribes to PC and gamepad binding-update events while
visible and calls `updateControlsText` when either arrives
(`TrainingView.as:181-184,685-688`). The selected `ControlBindingsManager`
builds separate PC and gamepad action-to-row maps. It dispatches those update
events only when a binding table's row count differs from the count it last
stored (`ControlBindingsManager.as:28-39,75-90`). Binding-record completion
instead dispatches `BINDING_COMPLETE` (`:161-165`), and the HUD does not
subscribe to that event. Consequently, these sources do not establish prompt
refresh when an existing row changes but row count stays constant. A new row,
input-type change, becoming visible, or closing the shot-selection menu can
refresh the text; the menu-stack handler refreshes only if the ResetTraining
binding string changed (`TrainingView.as:311-314,642-688`).

The standalone ActionScript helper is not the prompt renderer's resolver. Its
`getKeyForAction` reads a single row's `UIKey` (or `UIAxisKey` for a requested
gamepad axis), and the row map assignment means duplicate rows with the same
action name leave the last encountered row in the helper map
(`ControlBindingsManager.as:51-68,93-133`). The stock HUD never calls this
helper for prompts. The helper therefore cannot establish what the native
`Shell.GetKeyForAction` host call does with multiple binds or duplicate rows.

What can be concluded about alternatives:

- The ActionScript caller requests one family at a time: PC or gamepad. It
  does not render keyboard and controller alternatives side by side.
- It supplies one action ID per lookup and consumes one returned string per
  action. For shot navigation it combines the two different action IDs
  Previous and Next into a single localized row.
- If the host returns an empty string, the corresponding prompt row is hidden.
- If the wrapper cannot call the host it returns `null`; the HUD checks for an
  empty string, not `null`, so the resulting fallback display is unresolved.
- The native resolver's primary-versus-alternate bind policy, its treatment
  of multiple bindings for one action, and how it formats unbound keys are not
  visible in this export. No conclusion is made about those policies.

## MCT adapter boundary

The MCT settings menu offers “Game actions,” “Keyboard,” “PlayStation,” and
“Xbox” under `binding_profile`; its description says this changes only labels
(`NativeCareerLayout.h:2467-2480`). The reviewed lesson input path does not
pass this choice to the HUD or to Rocket League's native resolver (consistent
with CONTROLLER-EVIDENCE-01).

The pinned public BakkesMod SDK declares `CVarManagerWrapper::getBindStringForKey`,
`setBind`, and `removeBind` for BakkesMod key-command strings
(`cvarmanagerwrapper.h:30-32`), plus `GameWrapper::IsKeyPressed(int)` for a
named key query (`GameWrapper.h:122`)
([pinned SDK headers](https://github.com/bakkesmodorg/BakkesModSDK/tree/479e8f571cf554b25f4eeb64d611dec4133edcaf/include/bakkesmod/wrappers)).
MCT uses the first group to snapshot, install, verify, and restore its own
D-pad command bindings, then polls named D-pad keys in its lesson scope
(`TrainingLessonInput.h:244-315`; `MyCareerTraining.cpp:1195-1263`). Those
interfaces do not expose the stock `ControlsPCBindings` / `ControlsGamepadBindings`
action-to-UI-key map or the native shell formatter. The source comment about
logical gamepad polling is an MCT implementation note, not a public SDK promise
that the query identifies a physical input.

If MCT needs to show the exact stock prompt for a Rocket League action, it
needs a separately specified read-only adapter to the game-owned effective
binding source, including input type, action ID, alternate-bind policy, and a
reliable invalidation signal. A BakkesMod command-bind string can remain useful
for MCT's own ownership/conflict check, but it is a different data source.
Until that adapter exists, use a generic action label or clearly identified
display preset; do not present `binding_profile` as verified effective binds.

## Future acceptance cases

These are proposed checks, not performed here:

1. For PC and each supported controller input type, resolve a known binding
   and compare action ID, returned string, chosen icon family, and rendered
   label. Check absent bindings and verify that an unbound half of the
   Previous/Next pair hides the whole row.
2. Change an existing binding in place without changing table row count while
   the Training view stays open. Confirm whether the native UI emits an event
   that refreshes the displayed string; repeat with a newly added row and with
   a device-type switch.
3. Assign multiple bindings to one action and record the host resolver's
   chosen display convention. Keep the separate Previous and Next actions
   distinct from multiple binds for a single action.
4. Change only MCT `binding_profile` and verify that neither Rocket League's
   effective bind nor MCT's D-pad command ownership changes. Separately verify
   that MCT's BakkesMod bind readback is reported as a BakkesMod command bind,
   not a game-action binding.

## Source fingerprints

Hashes below identify the selected movie classes and frozen MCT source read
for this report. The movie/package hashes above identify the containing stock
artifact. The SDK commit is the one pinned by `plugin/CMakeLists.txt:26-29`;
local header hashes identify the reviewed declarations.

| Source | Bytes | SHA-256 |
|---|---:|---|
| `tagame/hud/TrainingView.as` | 30,691 | `95bb46f99e46b7bbe6e44d6fa641fd22058d4160a4f39180adee3c758fd60528` |
| `tagame/api/Shell.as` | 16,475 | `b542ad5cc406290ff85cb2c556da7a448ba50cda11a70c34b77449aa4bf4eff6` |
| `projectx/api/ShellAPI.as` | 2,887 | `7faf82cda315fff00825cf3a63b8345e419aae8eef6d9ad2f4c086f3eb014c9a` |
| `projectx/api/InputTypes.as` | 526 | `0ee9c21e6c63688e2e388d80d96698e5e4fe01ed71cb780804c0a2903133b747` |
| `tagame/managers/ControlBindingsManager.as` | 5,899 | `1d42c5179abe61f00b3a08b60046f4e317361f780e56871d49cfb9d359782c63` |
| `tagame/events/ControlBindingEvent.as` | 843 | `d50dc4aa543e175457a0b23a91baf173969bf4677410ba65b5b6db70121d1bf1` |
| `projectx/managers/SystemIconManager.as` | 17,107 | `384e8cdf3b6c309dfadab4be245c80bae7d6eafa8e1d148fc17bb7734efbde39` |
| `projectx/managers/InteractionManager.as` | 26,686 | `0353bf514d1afce294ef426f4dcd9f2ddefb2fb1d7eb5dfe0cb644dcb9bcbbbd` |
| MCT `plugin/include/NativeCareerLayout.h` | 167,035 | `17d2ec0a82c79fad1949715ad62840bcace4177cbbe137da3aa675289109eb78` |
| MCT `plugin/include/TrainingLessonInput.h` | 20,415 | `6cfa4f039ce965d5c9df7d64938ef70b0926b9055951388c2f83395d376d45d5` |
| MCT `plugin/src/MyCareerTraining.cpp` | 89,835 | `edc7bf5a6dc7ca0cff34ac694fb72fe71fa26dfe1fd4607d512f3b321a1a9279` |
| MCT `plugin/CMakeLists.txt` | 13,779 | `489e7323fddf44634321a3c341dc34aa54cead9e432c71aa2bff7bb3eea148b7` |
| Pinned SDK `cvarmanagerwrapper.h` | 1,583 | `f73792714d25e9f1bf0531bf44ad94b4c9e24ac973d8b3b4ade7f77750dbda2d` |
| Pinned SDK `GameWrapper.h` | 9,834 | `e3fd8da7976fb9e4b2189d69c0619d1c51f59caa859ac0395a3d4fc155e10bf0` |

The AS classes are the selected `GFX_Hud_SF` export and exact dependencies
listed in HUD-FLOW-01. Static decompiler output and public API declarations do
not prove native binding dispatch, runtime refresh events, icon artwork, or
what a player actually sees.

Coordinator provenance check: the inspected GameWrapper header hash in this report uses CRLF newlines. The LF copy fingerprinted in GHOST-VISUAL-01 is 9,648 bytes (`cae959eb403b56e907132b52d2e3cf3f4ce5bef04446c99e4f8c7f8b4b5446a9`); converting only LF to CRLF reproduces the 9,834-byte hash above. This is a newline difference, not evidence of a different API revision.
