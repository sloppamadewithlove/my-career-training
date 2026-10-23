# Native Rocket League menu: evidence and release gate

Evidence reviewed **23 October 2026**. The target is a solo offline career
inside Rocket League's own menu flow, using its current Steam build and leaving
the player's game files and saves intact. This document records research and
remaining proof; it does not claim that native-menu replacement has been
validated.

## Current implementation status

The current in-game interface is still a BakkesMod `PluginWindow` rendered with
ImGui over Rocket League. The repair changed it to an opaque window and removed
the old repeated 30 Hz `openmenu` loop. It now requests the window on lifecycle
transitions or an explicit menu key, so a dismissal stays dismissed until a new
transition. These changes make the existing overlay less disruptive; they do
not replace Rocket League's native buttons or menu tree.

The source includes an opt-in, bounded, read-only probe for menu names and
allowlisted event occurrences. No trace from the player's current Windows
installation has been captured. The probe does not dereference event
parameters, identify native movie ownership, or prove button routing. The new
diagnostic hashes the executable file identified by the running process when
capture starts; no actual player-game hash or trace has been collected yet.
A hash identifies file bytes, not compatible object layouts. There is no
verified native-menu Windows build, so the installer remains on hold.

## Native integration candidates

The source now includes an opt-in [native dialog trial](NATIVE_DIALOG_TRIAL.md)
using the public `CreateModal`/`AddButton` SDK. Its buttons route real Career and
Training commands, with stale-click and backend fixture checks. It has not run
inside the player's Windows game and does not replace or lock stock menus.
This supported route is narrower than the two full-menu candidates below.

Two approaches to full menu replacement still merit investigation. Neither is
validated for the current Rocket League process.

| Candidate | Evidence and potential | What remains unknown |
|---|---|---|
| **Live GFx/menu-tree adapter — preferred** | The current generated SDK snapshot describes `GFxShell_X.Movies` and `GFxShell_X.DataStore`, `GFxMoviePlayer.Invoke` and `SetVariableString`, and `MenuTreeBranch.SetChildren`. It also documents build-specific function invocation details including a fixed RVA and `ProcessEvent` at vtable slot 67. If verified in the running game, a process-local adapter could change the native menu while leaving Steam package files untouched. | The generated descriptions are not proof that these objects own the desired top-level buttons in the player's process. The exact executable hash, object lifetime/ownership, current call layout, safe invocation method, and a route that invokes career actions without also starting the original action are unverified. Fixed RVAs and vtable slots must not be used without exact-build validation. |
| **Per-process local package redirection — alternate** | [Reloaded II documents supported injection methods](https://reloaded-project.github.io/Reloaded-II/InjectionMethods/), and the [Reloaded file redirector](https://github.com/Reloaded-Project/reloaded.universal.redirector/blob/7c7cfae07e80cc9fb1c5f39f10cca2d49dc7eee3/README-REDIRECTOR.md) describes mapping replacement files by game-relative path. A locally generated menu package could, in principle, be supplied to the running process through a virtual file layer. | There is no verified Rocket League loader/redirector integration, no proven current menu package mapping, and no evidence that Rocket League accepts a generated package in this flow. It must remain process-local and must not alter the Steam installation. |

## Source evidence and limits

| Source | What it establishes | Limit |
|---|---|---|
| [RLSDK generated C++ snapshot at `8867776`](https://github.com/smallest-cock/RLSDK/tree/8867776ced2fdc39eca38733e6989213029905a5) | The commit is dated **22 October 2026**; its generated metadata targets Steam Rocket League **2.78**, build `261013.63066.530866`. It describes the GFx shell/movie/data store and menu-tree/function surfaces listed above. | The source repository snapshot has no license grant. Use it as a research reference only: do not copy or bundle its code, generated data, or Rocket League assets. It does not provide a hash or live receipt from the player's installed executable, establish object ownership in that process, or prove native click routing. |
| [Pinned BakkesMod SDK `MenuStackWrapper.h`](https://github.com/bakkesmodorg/BakkesModSDK/blob/479e8f571cf554b25f4eeb64d611dec4133edcaf/include/bakkesmod/wrappers/MenuStackWrapper.h), [pinned `GameWrapper.h`](https://github.com/bakkesmodorg/BakkesModSDK/blob/479e8f571cf554b25f4eeb64d611dec4133edcaf/include/bakkesmod/wrappers/GameWrapper.h), and [plugin-window interface](https://github.com/bakkesmodorg/BakkesModSDK/blob/479e8f571cf554b25f4eeb64d611dec4133edcaf/include/bakkesmod/plugin/pluginwindow.h) | Menu-stack reads, named event hooks, and an ImGui plugin window are available through the public SDK. | These interfaces do not expose a supported native button/tree editor or Scaleform movie replacement API. Hook event names alone do not provide safe cancellation or routing. |
| [Reloaded II injection methods](https://reloaded-project.github.io/Reloaded-II/InjectionMethods/) and [redirector source at `7c7cfae`](https://github.com/Reloaded-Project/reloaded.universal.redirector/blob/7c7cfae07e80cc9fb1c5f39f10cca2d49dc7eee3/README-REDIRECTOR.md) | A general loader can initialize mods in a process, and the redirector describes virtual replacement files. | Generic tooling is not evidence of Rocket League compatibility, a working native menu, or safe restoration. |
| [Rocket League EAC announcement](https://www.rocketleague.com/news/easy-anti-cheat-comes-to-rocket-league-on-pc-today/) and [Code of Conduct](https://www.rocketleague.com/code-of-conduct) | Epic describes offline play, training, LAN, and replays as mod-compatible when EAC is off, subject to the game's rules. | Offline permission does not establish a menu-edit API or certify a particular loader, hook, or package. The mod must remain fail-closed outside its owned offline session. |

## Proof required before calling a build native or downloadable

1. On the player's actual Windows Steam installation, capture the exact game
   build and executable hash, confirm the launcher-owned process and offline
   no-EAC state, and observe the native menus in that same process.
2. Identify which current-build movie and objects own the main-menu buttons and
   relevant submenus. Verify function signatures and object lifetimes against
   that exact executable; do not infer them from old offsets or names alone.
3. Demonstrate that the native button action can safely enter the career flow
   without running the original matchmaking action, and that normal Rocket
   League menus return after career exit, plugin unload, process exit, and any
   stale/online state.
4. Verify controller and keyboard navigation, match/pause/results transitions,
   repeated entry/exit, an update/hash mismatch refusal, and an ordinary Steam
   launch after the test. No test may change or replace Steam's original game
   files, and no proprietary Rocket League assets may be copied into the
   project or installer.

CI can check the probe, guards, and adapter code. It cannot prove native GFx
ownership, live button routing, visual stability, or restoration inside the
current Windows game. Until those are demonstrated on the exact build, the
ImGui interface remains a prototype and the Windows installer must stay held.
