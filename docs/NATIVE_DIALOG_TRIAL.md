# Native career dialog trial

This development path uses Rocket League's own modal dialogs through the
pinned BakkesMod SDK. It is **not a replacement for the main menu** and is not
the finished public download. The installer hold remains in place.

The native buttons can navigate Career, Training, Schedule, Season and Squad.
Career can send a request for the displayed next fixture. Training can select
a lesson and send Start Practice. The backend still owns saves, game sessions
and outcomes. Schedule, Season and Squad are read-only in this first trial.
Creating a career, editing a lineup, Garage and Settings still use the existing
prototype controls. No expert ghost recording is supplied by this trial.

## Why this route

The public SDK exposes `GameWrapper::CreateModal` and
[`ModalWrapper::SetBody`, `AddButton`, `ShowModal` and `CloseModal`](https://github.com/bakkesmodorg/BakkesModSDK/blob/479e8f571cf554b25f4eeb64d611dec4133edcaf/include/bakkesmod/wrappers/modals/ModalWrapper.h).
These provide real native dialog buttons with callbacks, without replacing
game files, inspecting event parameters, copying generated engine layouts or
calling undocumented memory addresses.

The SDK does not expose a documented way to disable Escape/Back dismissal or
replace the stock main-menu tree. The trial deliberately leaves stock menus
available and does not reopen itself repeatedly to claim a menu lock.

## Developer test entry

Build the Windows plugin from this source, run the offline My Career service,
and stay in Rocket League's frontend. In the prototype's Settings → Diagnostics,
choose **Try Native Career Dialog**, or use `mct_native_hub` in the BakkesMod
console. This is an explicit development action, not the default startup UI.
The existing menu key returns to the prototype controls.

Native dialog clicks are deferred to the game thread. Every click must match
the displayed dialog generation and current bridge session. The plugin checks
the actual process ID, creation time, executable identity, Steam runtime,
`-noeac` and `-rlbot` arguments, fresh service state and offline status before
using the native interface. Match requests include the displayed career and
fixture IDs; the backend checks them again before changing a save or starting
a worker. Losing scope invalidates pending clicks.

## What must be observed on Windows

Automated tests verify the model and request guards. They do **not** verify the
native dialog's appearance, engine lifetime or game behavior. Record the exact
plugin hash, game executable hash, game build and BakkesMod version with these
results:

1. Open the native trial; navigate each page with keyboard and PlayStation
   controller. Verify focus, labels, Back, Escape and repeated entry/exit.
2. Select a lesson and start practice. Confirm the car can be controlled and
   that the service reports the selected lesson, not merely a queued request.
3. Start the displayed next fixture and verify the actual teams, human club,
   results and return to the frontend. Repeat after finishing a match.
4. Close the service or change its session while a dialog is open. Check that
   old buttons cannot start a game or change career progress.
5. Test plugin unload and world transitions for stale dialogs or callbacks.
6. Close the offline game and launch normally from Steam. Verify ordinary menus,
   settings, saves and EAC-enabled online play remain intact.

A successful trial would prove a supported native-dialog route. It would still
not establish inaccessible stock menu options, the full requested native layout,
or a complete native career release. Those remain separate release conditions.
