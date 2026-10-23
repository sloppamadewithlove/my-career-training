# Native Rocket League menu: evidence and release gate

Evidence reviewed **23 October 2026**. The player asked for My Career to change
Rocket League's own offline Play and main-menu buttons, while leaving their
Steam installation intact. They rejected the full-screen BakkesMod window as
the final interface and chose to **hold the next installer until a native menu
path is verified**. This document records a research path, not a claim that
native menu editing works in the current game.

## What the current build does

`plugin/src/CareerUI.cpp` renders an ImGui window over the whole display.
`plugin/src/MyCareerTraining.cpp` opens it with BakkesMod's `openmenu`
command and blocks input while that window is active. The game's menu remains
underneath. The window background alpha is `0.99`, so the underlying menu can
show through. The plugin also requests `openmenu` on every 30 Hz tick while
`windowOpen_` is false; `OnClose` clears both `windowOpen_` and `menuOpen_`,
then main-menu detection sets `menuOpen_` again. This is a concrete potential
reopen/flicker loop, not proof of the exact visual sequence on the player's PC.
The player reported the native menu glitching over My Career; no Windows render
trace has yet been captured.

## Verified API and upstream evidence

| Source | What it establishes | Limit |
|---|---|
| [Pinned BakkesMod SDK `MenuStackWrapper.h`](https://github.com/bakkesmodorg/BakkesModSDK/blob/479e8f571cf554b25f4eeb64d611dec4133edcaf/include/bakkesmod/wrappers/MenuStackWrapper.h) | `GetTopMenu()` and `GetMenuStack()` read menu names; the header lists the game's `PushMenu` and `PopMenu` events. | The header provides no setters for buttons, labels, layout, or actions. Event names are not callable wrapper methods. |
| [Pinned SDK `GameWrapper.h`](https://github.com/bakkesmodorg/BakkesModSDK/blob/479e8f571cf554b25f4eeb64d611dec4133edcaf/include/bakkesmod/wrappers/GameWrapper.h) and [plugin-window interface](https://github.com/bakkesmodorg/BakkesModSDK/blob/479e8f571cf554b25f4eeb64d611dec4133edcaf/include/bakkesmod/plugin/pluginwindow.h) | Expose menu state, named Unreal event hooks, and an ImGui window with input blocking. | They do not expose a native main-menu button tree or a Scaleform movie-editing interface. `GuiManagerWrapper` covers ImGui styling and fonts, not Rocket League's GFx buttons. |
| Generated `@rlsdk/steam` [classes](https://github.com/ObscuritySRL/rlsdk/blob/99c4330f8e26e037f7f343dbe75b6dd5c08c4a01/packages/steam/classes/TAGame.ts), [offsets](https://github.com/ObscuritySRL/rlsdk/blob/99c4330f8e26e037f7f343dbe75b6dd5c08c4a01/packages/steam/offsets/TAGame.ts), [parameter shapes](https://github.com/ObscuritySRL/rlsdk/blob/99c4330f8e26e037f7f343dbe75b6dd5c08c4a01/packages/steam/parameters/TAGame.ts), and [README](https://github.com/ObscuritySRL/rlsdk/blob/99c4330f8e26e037f7f343dbe75b6dd5c08c4a01/packages/steam/README.md) | Identify game types such as `GFxData_MenuStack_TA.ButtonTriggered(ButtonName: FName)`, `GFxData_MenuTree_TA.OnChildNodeClicked`, and `MenuTreeNode_TA` with `NodeID`, `Title`, `Description`, and `OnClicked`. | MIT-licensed generated **memory descriptions**, not a tested C++ menu-edit API. The checked-in generation was 12 September 2026, before the 20 October game update; its README says offsets can change with each game build. It provides no current executable hash or proof that the top-level Play screen uses the editable tree. Do not copy old offsets into the plugin. |
| [BakkesPlugins function-hook guide](https://bakkesplugins.com/wiki/bakkesmod-sdk/functions/using-function-hooks) and [any-caller example](https://bakkesplugins.com/wiki/bakkesmod-sdk/functions/hook-event-with-any-caller) | Named game functions can be observed; hooks with a caller expose untyped `void*` parameters. | The guide warns that guessed parameter casts or blind caller casts can crash. Hooking does not by itself safely cancel a native button action or replace its visuals. |
| [VelocityRL's `TAGame.upk` editor](https://github.com/bitsfdb/VelocityRL/blob/d8d167bd992f618f2cef100c575d74f6a810ffbd/src-tauri/src/upk/tagame_swapper.rs), [Reloaded file redirector](https://github.com/Reloaded-Project/reloaded.universal.redirector/blob/master/README-REDIRECTOR.md), and [historical Rocket League graphics](https://github.com/ItsBranK/RocketLeague-Graphics) | VelocityRL demonstrates backed-up `.upk` edits; Reloaded offers generic game-file read redirection; the graphics archive identifies historical `GFX_MainMenu_SF` and `GFX_PlayMenuV4_SF` packages. | VelocityRL writes `TAGame.upk` in the game install. The redirector has no verified Rocket League menu integration, needs another loader, and is [GPL-3](https://github.com/Reloaded-Project/reloaded.universal.redirector/blob/master/LICENSE.md). The graphics are from a 2023 game build; their repository's license cannot grant rights to distribute Psyonix assets. None proves current native menu replacement without touching Steam files. |
| [Rocket League's EAC announcement](https://www.rocketleague.com/news/easy-anti-cheat-comes-to-rocket-league-on-pc-today/) and [mod rules](https://www.rocketleague.com/code-of-conduct) | Third-party mods may run when EAC is off for offline play, training, LAN, and replays, subject to the game's terms. | Permission for offline mods does not supply a menu-edit API or certify a specific technique. This project must remain fail-closed outside the owned offline session. |

The generated SDK makes the game's **Play-menu tree** a plausible research
target. Its top-level main-menu buttons may instead be owned by a separate GFx
movie. That ownership is an inference requiring a live current-build trace.
Neither a raw `ObjectWrapper::memory_address`, an untyped event parameter, nor
an old `.upk` is a verified integration point.

## Minimum reversible architecture to investigate

1. Add an **opt-in, read-only Windows probe** to the existing plugin. Run it
   only in the launcher-owned Steam process with EAC off and a fresh bridge
   nonce. Record the actual `GetPsyBuildID()`, executable SHA-256, BakkesMod
   version, menu stack transitions, and occurrence/timing of the named
   `GFxData_MenuStack_TA.ButtonTriggered` and menu-tree events. Do not
   dereference hook parameters, write game memory, suppress actions, or alter
   files in this probe. Keep the log local and omit account IDs and paths.
2. On the player's Windows installation, identify which current-build native
   objects and movie own the top-level Play button and the Play submenus.
   Validate function names, parameter layouts, and object lifetimes against
   the **exact executable hash**. Confirm how a native button's click could
   invoke an allowlisted career action while the game's original action does
   not also run. Observation alone is insufficient.
3. Only after that evidence, implement a small build-gated adapter. At entry,
   require the exact approved Steam build, owned process, EAC-off offline state,
   and fresh bridge. Snapshot every native object/property it would change;
   change the minimum buttons; restore them on return to ordinary play, stale
   bridge, online transition, plugin unload, and game exit. Unknown builds or
   failed validation must make **zero native writes**. The native-menu feature
   must not modify Steam's game files or bundle extracted game assets.
4. Record real-game proof for display, controller/mouse navigation, every
   button action, pause/results transitions, repeated open/close, clean
   restoration, normal Steam launch afterward, and an online-boundary check.
   Test a game update/mismatched hash to confirm refusal before any write.

The read-only probe, build/hash gate, state machine, and restoration contract
can be compiled and unit tested on CI. CI cannot prove actual GFx ownership,
native click routing, visual stability, or safe restoration in Rocket League.
Those require a dated Windows game receipt from the current build. If the
probe cannot establish a safe native edit and route, leave the installer on
hold and state that limitation plainly. Do not relabel the existing ImGui
window as a native menu or publish a release that claims the requested native
button replacement.
