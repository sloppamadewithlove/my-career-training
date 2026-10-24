# Current main-menu asset findings

Read-only inspection on 2026-10-24 identified the current installed
`GFX_MainMenu_SF.upk` and its `MainMenu` SwfMovie. Package and movie hashes,
format fields, and inspection limits are recorded in
`validation/native-menu-asset-2026-10-24.json`. No game or injector was launched
for this work. The installed package hash is unchanged after inspection.
Private asset bytes are not included in this repository or distribution.

The movie uses ActionScript 3. The bounded ABC inspection reports selected
method/identifier associations, not decompiled source. Some constructors and
unrelated methods use opcodes the research scanner does not support. The
methods and getters described below decoded successfully; this is not a full
verification of all movie behavior.

## Root captions and controls

`menus::RootMenu` initializes its normal label constants through `LOCTEXT` and
`NSLOCTEXT`, followed by uppercasing. Those script helpers call
`ExternalInterface.call` with the method name `Localize` and three payload
arguments. The ABC omits parameter names, so the inspection does not assign
semantic names to those arguments. These normal root captions are authored/localized by
the movie; they are not established as label cells in `MenuTreeNodesData`.

`RootMenu.generateControls` creates the Play control through
`BranchingMenu.createControl`, supplying label/description data and the
`openPlayMenu` callback. The generic `DynamicMenu.createControl` stores a
control's callback and argument array. `handleControlCallback` retrieves them
and invokes the callback. This establishes a real native control construction
pattern, but not a plugin-callable API for adding or replacing those controls.

The normal captions are class-static values. The observed timer refresh calls
`generateControls` again, consuming the cached strings; it does not rerun the
class initializer. A localization observation attached after this initialization
would therefore miss the original caption requests. That timing must inform any
later focused trial.

Selected root callback associations are `openPlayMenu`, `tryOpenShopMainMenu`,
`tryOpenRocketPassScreen`, `openGarageSelectionMenu`, `openProfileMenu` and
`openOptionsMenu`. Club and esports controls use separate callbacks, and Quit
opens a shell modal. These are movie-side identifiers, not public plugin methods.

The event button has a separate data source:
`ESportEventsEventsRow.ButtonTitle` and `ButtonDescription` read the
`ESportEventsEvents` table by row index and those column names. Finding this
event button's caption in the data store would not establish the binding of the
normal Play/Garage/Settings captions.

## Host action paths

The movie's `MenuStack.ButtonTriggered(String)` wrapper calls
`UIShellHooks.SHELL_CallUnrealFunction` using `GFxData_MenuStack_TA`, `MenuStack`
and `ButtonTriggered`. The menu-tree action wrapper similarly uses
`GFxData_MenuTree_TA`, `MenuTree` and `OnChildNodeClicked`.

The observed shell-call argument order is data class, table, row `0`, function
name, and the button/child name. `UIShellHooks` initialization separately calls
`ExternalInterface.call("InitShellHooks")`. Neither call supplies a verified
plugin-side invocation route.

`MenuTreeNodesDataRow` exposes `NodeID` and `TableName` through `DataAPI.getValue`,
plus its row index. The inspected row wrapper has no title/label getter. Do not
invent a menu-tree label column when implementing the adapter.

These associations explain why a button-event trace alone cannot establish
caption replacement. They also do not prove that changing one native event
parameter consumes every stock route or suppresses ActionScript side effects.

## Implementation boundary

The public BakkesMod SDK exposes event hooks and read-only menu-stack queries.
It does not expose a general GFx movie/data-store wrapper or an established
session-local custom-movie loader. Generated Unreal signatures are candidate
metadata, not a verified current-build invocation ABI.

The next native adapter must establish a bounded host/movie call boundary, the
caption construction or refresh path, and action interception separately. No
native mutation gate is opened by this inspection. The existing small-table
reader remains useful for its actual data-store scope; its results cannot be
treated as the main root captions by default.

Format references: [UEViewer's UE3/Rocket League package reader](https://github.com/gildor2/UEViewer/blob/master/Unreal/UnrealPackage/UnPackageReader.cpp),
[GFx raw-data declaration](https://github.com/gildor2/UEViewer/blob/master/Unreal/UnThirdParty.h),
[AVM2 format overview](https://burgerlib.readthedocs.io/en/latest/avm2overview.pdf),
and [Scaleform host communication](https://help.autodesk.com/cloudhelp/ENU/Scaleform-Help/scaleform_help/game_communication.html).
