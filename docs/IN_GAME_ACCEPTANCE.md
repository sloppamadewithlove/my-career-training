# 0.2.0 in-game acceptance record

Evidence date: **23 October 2026**. This is a test plan and status sheet, not a
gameplay receipt. Full V1 remains incomplete. Record source, Windows build, and
live game evidence separately; do not convert source code or mocks into a game
pass.

## Current status

| Area | Source status | Windows build status | Live game status |
|---|---|---|---|
| In-game UI and local bridge | Python service and BakkesMod plugin source are present; game integration needs a live test | See the published release receipt for DLL/package build evidence | Not tested |
| Launch mode | Source restricts this preview to Steam and requests the supported offline/EAC-off route | Needs Windows launch and ownership verification | Not tested |
| Epic Games | Not supported by the 0.2 in-game bootstrap | Out of scope for this preview; original V1 target remains unmet | Not tested |
| Career saves and existing AppData | Existing local store is reused; bridge rejects stale sessions and arbitrary actions | Upgrade/first-install Windows checks pending | No observed match receipt |
| Career, squad, schedule, and standings | Domain logic is present; in-game controls still require integration/build verification | Pending | Not tested |
| Match completion and result persistence | Worker/result logic exists in source; no live match or overtime evidence | Pending | Not tested |
| Training lessons and reset | Training engine/catalog exists in source | Pending | Not tested |
| Personal recording and ghost | Playback is pose-based and non-colliding by design; no validated expert recording is bundled. Successful personal recordings can be played in-game; an import control and action are present in source, but the picker-to-service flow is not yet verified | Pending | Not tested |
| PlayStation controller graphic | Source maps observed game actions to a configurable PlayStation display; it is not raw hardware capture | Pending | Physical controller and mapping behavior not tested |
| Workshop and local maps | Steam library/catalog and desktop import boundaries are in source; the in-game UI does not expose map-file import, and import alone does not prove a map loads | Pending | Not tested |
| Garage/item override | Limited local BakkesMod override code exists and reports appearance as unverified | Pending | Not tested |
| Online behavior | In-game bridge is intended to reject online commands; this preview has no online flow | Pending fail-closed checks | Not tested in the live game |

The in-game build requires Windows x64, Steam, an installed Rocket League copy,
and BakkesMod. This version does not support Epic launch. No Steam or Epic game
session has been accepted as tested until a dated receipt records the exact app,
game, launcher, and BakkesMod versions and observed outcomes.

## Windows source and package checks

Before handing the preview to a player, record the exact commit and complete
these checks on Windows x64:

- Build the plugin with the pinned BakkesMod SDK and MSVC; inspect the produced
  DLL and its build receipt. A portable bridge test is not a DLL build.
- Build installer and portable packages; verify the plugin is included and its
  hash matches the receipt. Confirm setup/diagnostics shortcut and uninstall
  behavior, and confirm existing `%LOCALAPPDATA%\MyCareerTraining` data remains.
- Launch a clean packaged install without Python, Git, Cursor, or a developer
  terminal. Verify paths with spaces and a Unicode Windows profile.
- Confirm startup refuses an already-running Rocket League process, uses the
  Steam offline launch arguments, starts or detects BakkesMod, and fails closed
  if the plugin or bridge does not connect.
- Run the Python and C++ contract tests. Report the test command and result;
  these checks do not count as live-game verification.

**Windows build evidence:** each published release includes `RELEASE_RECEIPT.json`
and `plugin-build-receipt.json`, with exact source/hash identities and passing
package, model inference, install/upgrade/uninstall checks. Table entries marked
pending describe real-game checks unless identified as a build requirement.
**Plugin DLL runtime compatibility:** not yet verified inside Rocket League.

## Steam game test checklist

Use a real Windows Steam installation and a copy of the player's existing save.
Record a separate outcome for every item; use **Pass**, **Fail**, or **Not
tested**, with a short observation. Do not infer a pass from a screen rendering.

1. **Startup and safety:** close Rocket League; start from the My Career
   shortcut; verify the intended installed game opens offline, the plugin
   connects, and the custom menu appears. Confirm an already-running game is
   refused rather than controlled. Check that no online controls are offered
   and that commands stop when the bridge goes stale or the game enters online.
2. **Menu and bindings:** open, close, and reopen the menu; test F6 when free and
   confirm an existing F6 binding is preserved. Test pause-menu behavior,
   Escape/Back, mouse, keyboard, controller navigation, focus, and game input
   capture. Confirm menu input never steers the car and HUD input never locks it.
3. **Save preservation:** open an existing career, inspect team, roster, fixture,
   standings, and settings, close the app, reopen, and compare. Verify the
   original AppData save survives package upgrade. Exercise new career creation
   without overwriting the prior career.
4. **Career loop:** create or resume a career; confirm team names and human side;
   check 1v1–4v4 roster counts, bench and between-match lineup rules, schedule,
   season standings, playoff routing, and next-season continuity. Play a fixture
   to a real final score, including overtime if available. Confirm result,
   progression, and rewards are saved exactly once after UI/worker restart.
5. **Training and ghost:** launch each supported lesson; verify setup, reset,
   retry, observed feedback, and that ordinary game physics remain intact. Check
   that no expert demonstration appears when none is installed. Test the
   in-game recording-import flow with a permitted file: it must import the
   selected file without an extra picker, preserve its unverified provenance,
   and never certify an imported success claim. Until that flow works in the
   Windows package, mark import **Not tested**. Record a real
   personal attempt; replay, pause/seek/stop and slow it down if those controls
   are present. Confirm its source label says personal/imported, the ghost does
   not collide, and recorded controller actions stay synchronized.
6. **PlayStation display:** press Cross, Circle, Square, triggers, and stick
   axes during a lesson and compare the overlay with observed in-game logical
   actions. Change display mappings and verify gameplay bindings do not change.
   Disconnect/reconnect the controller and confirm progress is preserved.
7. **Workshop and Garage:** inspect Steam Workshop discovery, favorites, and
   compatibility labels. Launch only a map with a verified route; otherwise
   confirm unsupported items fail safely and built-in lessons remain available.
   Apply a supported local cosmetic, inspect it in-game, restore original
   settings, and verify no account inventory or online loadout is changed.
   Then enter the online boundary using the normal Steam launcher and confirm
   the local item override is cleared before any online session can use it.
8. **Shutdown and offline boundary:** leave/stop a fixture safely, close the
   custom menu, then quit the game. Confirm the service and plugin stop without
   terminating unrelated processes. Start Rocket League normally from Steam
   afterward and verify no career bot or training control is active.

## Result receipt

For each run, record:

- UTC timestamp, app commit/version, Windows edition/build, Steam, Rocket League,
  BakkesMod and plugin versions.
- Which checklist numbers were tested and their observed outcome. Include the
  fixture/session identifier for a match, but omit account names and credentials.
- Exact errors, whether the result was durably saved, and whether the behavior
  was source-only, Windows-package-tested, or observed in Rocket League.

No Epic game-test row can pass for this preview because the 0.2 bootstrap
rejects Epic. Restore Epic as a separate implementation and verification task;
do not treat the Steam test as Epic evidence. Do not call V1 complete until the
remaining source, package, game, teaching-reference, provider, and launcher
acceptance requirements are resolved.
