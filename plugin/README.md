# My Career in-game plugin

`MyCareerTraining.dll` runs in the installed Windows Rocket League through
BakkesMod. The desktop shortcut starts the background career service and the
supported offline game launch. The visible interface is a full-screen in-game
`PluginWindow`, with Career, Squad, Schedule, Season, Training, Workshop, Garage
and Settings. No online navigation is exposed.

The interface is original vector/text artwork. No Rocket League assets, game
executable or BakkesMod injector are redistributed.

## Build

Use Visual Studio 2022 x64 C++ tools and CMake 3.24 or newer:

```powershell
cmake -S plugin -B build/plugin -A x64
cmake --build build/plugin --config Release
ctest --test-dir build/plugin -C Release --output-on-failure
```

Output: `build/plugin/Release/MyCareerTraining.dll`. Packaging stages it at
`runtime/plugins/MyCareerTraining.dll` beside its dependency/build receipt.
It imports BakkesMod host functions and cannot be meaningfully loaded into an
ordinary standalone process. PE/export verification is separate from game tests.

Portable IPC contracts can run without Windows or the game:

```sh
cmake -S plugin -B build/plugin-contracts -DMCT_BUILD_PLUGIN=OFF
cmake --build build/plugin-contracts
ctest --test-dir build/plugin-contracts --output-on-failure
```

All fetched archives have fixed versions and SHA-256 checks in CMake and
`DEPENDENCIES.json`. The SDK supplies its exact patched ImGui 1.75 sources;
substituting a recent upstream ImGui would break the shared-context ABI.

## Runtime boundary

The plugin reads `%LOCALAPPDATA%/MyCareerTraining/bridge/state.json`. A current
protocol-1 service nonce, `offline:true`, heartbeat within five seconds and
`owned_game.pid` equal to this game process are required before showing controls
or issuing mutations. `IsInOnlineGame()` independently disables the interface.
The plugin never edits a career/save. Actions are allowlisted, bounded JSON with
canonical UUID filenames and atomic publication under `commands/`.

Runtime probes are atomically published as `plugin-status.json` with nonce,
timestamp, game PID/build, BakkesMod version, logical actions and applied team
lock status. Stale state removes input capture and restores cosmetic overrides.

The game thread owns all SDK calls. Rendering reads a protected snapshot and
queues fixed local operations. Career team writes additionally require
`session.kind == "career"`, `session.state == "Playing"` and the exact pending
fixture ID. Freeplay, custom training, replays and online games are excluded.
Native logical actions are sampled at 30 Hz; unchanged service files reuse their
parsed snapshot while still enforcing heartbeat expiry. The installed cosmetic
catalog is immutable between scans and shared across render snapshots.

The hub auto-opens in the main menu and after match results. Its full-screen
window covers the native menu and `ShouldBlockInput` prevents clicks reaching
the underlying controls. This is **not** a patched replacement of the native
Scaleform files. Main/pause transitions, native menu focus, controller navigation
and resume behavior still require current-game Windows testing.

Resume closes only the career hub when the game is not paused. When the observed
native pause menu is present, the user-requested Resume action first releases
input capture, then sends one paired Escape down/up to the exact owned foreground
game window. It rechecks the real pause/menu state and reports failure instead
of claiming success. No driving or anti-idle inputs are synthesized. If the native
menu stays open, automatic pause capture is temporarily suppressed so the player
can hide the career hub and close the native menu normally.

The menu observes the first unused F6-F12 key only while the owned offline game
has foreground focus. It never writes a global BakkesMod key binding. An
in-game Settings selector can choose a different unused function key, and the
actual shortcut is shown on the HUD. Existing user `mct_menu` bindings are left
untouched. The prototype borrows ImGui navigation flags only while its menu
owns input, removing only the bits it added on close/unload and preserving
preexisting flags and unrelated changes. Prototype gamepad navigation still needs a physical
controller test; the PlayStation action graphic is a separate feature.

An opt-in [native dialog trial](../docs/NATIVE_DIALOG_TRIAL.md) uses the public
SDK's own dialogs for Career/Training buttons and read-only career details.
It is not the startup interface or a replacement/lock for the stock menus.
Native keyboard/controller, Back/Escape and world-transition behavior still
require a Windows Rocket League test.

## Implemented training controls

- Live graphical PlayStation controller from observed logical game actions;
  configurable labels, size and side, with a second controller for a visible
  recorded ghost. Unknown right-stick camera inputs stay neutral.
- Start, retry, personal best watch, ghost lead, pause/resume, seek, slow playback,
  loop, stop and permitted JSON recording import from the in-game interface.
- Clear unavailable-demonstration status. No synthetic sample is presented as a
  successful expert execution. Imported recordings retain their provenance.

SDK 95 exposes no verified idle-kick disable switch. No movement is fabricated
to keep the player active, and no idle-protection guarantee is claimed.

## Garage capability

`ItemsWrapper::GetAllProducts()` and product labels/slots enumerate the installed
game's current catalog at runtime, 200 entries per game-thread tick. Browse car
bodies, decals, wheels, boosts, paint finishes, trails, goal effects, anthems and
profile cosmetics. The apply control submits original BakkesMod v3 item codes
to the existing `cl_itemmod_enabled` / `cl_itemmod_code` interface only after
runtime capability probes and catalog membership validation.

Supported override slots are cosmetic slots 1,2,3,4,5,7,12,13,14,15,18 and product
IDs up to 8191, the verified 13-bit format limit. Body switching and profile
inventory unlocks are not supported by that format; newer IDs remain browseable.
No entitlement or inventory is modified. Requested appearance and actual scene
appearance are separate checks. Original cvars are restored on unload, service
disconnect, loss of ownership and any online transition. Designs are saved in
the per-user plugin preferences for later local use.

## API evidence

SDK commit `479e8f571cf554b25f4eeb64d611dec4133edcaf`, API 95:

- [Plugin window input capture / overlay interface](https://github.com/bakkesmodorg/BakkesModSDK/blob/479e8f571cf554b25f4eeb64d611dec4133edcaf/include/bakkesmod/plugin/pluginwindow.h)
- [Game state and online guards](https://github.com/bakkesmodorg/BakkesModSDK/blob/479e8f571cf554b25f4eeb64d611dec4133edcaf/include/bakkesmod/wrappers/GameWrapper.h)
- [Native menu stack introspection](https://github.com/bakkesmodorg/BakkesModSDK/blob/479e8f571cf554b25f4eeb64d611dec4133edcaf/include/bakkesmod/wrappers/MenuStackWrapper.h)
- [RemoveTeamSelection](https://github.com/bakkesmodorg/BakkesModSDK/blob/479e8f571cf554b25f4eeb64d611dec4133edcaf/include/bakkesmod/wrappers/GameEvent/ServerWrapper.h)
- [Custom club names](https://github.com/bakkesmodorg/BakkesModSDK/blob/479e8f571cf554b25f4eeb64d611dec4133edcaf/include/bakkesmod/wrappers/GameObject/TeamWrapper.h)
- [ChangeTeam and observed vehicle inputs](https://github.com/bakkesmodorg/BakkesModSDK/blob/479e8f571cf554b25f4eeb64d611dec4133edcaf/include/bakkesmod/wrappers/PlayerControllerWrapper.h)
- [Installed cosmetic catalog](https://github.com/bakkesmodorg/BakkesModSDK/blob/479e8f571cf554b25f4eeb64d611dec4133edcaf/include/bakkesmod/wrappers/items/ItemsWrapper.h)
- [Existing item-code format reference](https://github.com/daftpenguin/StreamAPIPlugin/blob/0bb1c69958e7b77b5b7fef7586ea325fc46fbc7e/StreamAPIPlugin/BMLoadoutLib/bmloadout.h)

Compilation, portable bridge tests and static API review do not demonstrate game
compatibility. Steam launch, menu transitions, actual cosmetics and idle behavior
are acceptance checks to perform in the real installed game.

### Optional visual refinement

Opus 5.5 can refine original typography, blue/orange contrast, focus states and
controller spacing after functional verification. Keep capability labels,
navigation, save semantics and accessibility intact. It is not a runtime
dependency or a prerequisite for compiling this interface.
