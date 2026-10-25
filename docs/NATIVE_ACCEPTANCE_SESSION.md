# One native-menu acceptance session

The source/build checks do not establish that Rocket League loaded the private
movie or that its controls work. Keep the release hold until the following
evidence is captured from one deliberately scheduled owned offline session.
Do not repeatedly open the game for individual source edits. Do not launch it
while the player is unavailable and has asked for source-only work.

## Before opening the game

- Complete both plugin configurations, launcher/file-view fixture tests, Python
  integration checks, private movie round-trip checks, and frozen candidate smoke.
- Record the candidate manifest and executable/plugin hashes. Record installed
  RocketLeague.exe and GFX_MainMenu_SF.upk hashes, the existing BakkesMod plugin
  setup, and the presence of recovery journals. Preserve any existing career.
- Confirm no Rocket League or native launcher process is already running. Use
  the candidate's owned launcher; never attach the file view to another process.

## During the single session

1. Confirm the actual game shows the authored My Career root and that mouse and
   controller selection work. A published view or a HELLO receipt alone is not
   visual proof. Record the game build and the exact owned process identity.
2. Check Career, Training, Garage, Workshop, Community, Settings, Back and Quit
   routes. Check that normal online matchmaking/store/tournament routes are
   absent from this root. Do not start an online match.
3. Check first-career controls on an empty test save, or inspect them without
   replacing an existing player career. Confirm squad/rules choices, current
   selections, completed results, season progression and backups against actual
   saved state. Domain tests remain the authority for simulated fixture outcomes;
   never label a generated score as a real game result.
4. Run a short offline lesson, verify human controls and the selected help/speed
   settings, then return home. Open stock Garage and Options and return; verify
   the custom menu survives the full screen transition and releases input focus.
5. Try one supported local appearance change and restore it. Verify the actual
   car appearance; catalog enumeration and CVar writes are not appearance proof.
   Car bodies remain selected through the game's owned Garage loadout.
6. Try two installed Workshop maps from their original Steam Workshop locations,
   returning to the frontend between them.
   Record actual map identity and verify no installed game map was replaced.
   A return from executeCommand is only dispatch evidence. The current candidate
   retains both maps' file holds until this owned process ends.
7. Community download checks may run independently of the game. An optional
   reviewed plugin trial needs the exact cached artifact and actual PluginManager
   confirmation. Also verify its intended gameplay mode; a loaded DLL alone is
   not proof that the skill works. Speedflip Trainer requires its specific custom
   training pack, and fetching a new pack may need normal account services.
   Unknown/refused trials require closing this session before another activity.

## Return repair acceptance

For the Return repair, first test one coherent source candidate, then the exact
same-run inventoried frozen installer input. Record these as separate results.
Keep the previous installer on hold even if its CI pipeline passed.

1. Start an activity with the actual native Play button. Record the owned game
   PID and creation time, source revision, and matching runtime hashes.
2. Exercise a lesson, Retry, Escape, Game options/Back and Resume. Confirm that
   an unfinished career fixture requires Return confirmation and that Cancel
   leaves that fixture active.
3. Return from a lesson and from an explicitly abandoned unfinished fixture.
   Observe the durable service acknowledgement, navigation attempt, and actual
   arrival separately. Require a fresh frontend READY, `RootMenuMovie`, and a
   foreground screenshot of the authored hub. A screenshot requires a fresh
   identity and foreground check; a blocked input is not a successful test.
4. Exercise Resume while cleanup is delayed. Confirm intent survives the pause
   movie unloading. If `OnOpenPauseMenu` is attempted, record its single attempt
   and whether an actual pause movie plus READY appeared. Do not infer success
   from that SDK method's name or void return.
5. Complete a real career fixture. Verify its actual score saves exactly once,
   its pending fixture clears, and its durable receipt is acknowledged. Use the
   actual results Return button and repeat the hub arrival checks.
6. Start another activity without another game process. Restart the app using
   the copied saved career and verify the completed result persists. Repeat the
   real fixture/save/Return/restart cycle with the exact frozen build.
7. Check mouse, keyboard and a real controller separately. Software key events
   are not physical-controller evidence. Verify the offline menus have no
   actionable matchmaking, tournaments or store routes.

## Restoration and normal launch

- Wait for the owned game and helper to exit. Complete community and base-plugin
  recovery before starting the normal launcher. Preserve conflicting files and
  journals rather than overwriting unrelated changes.
- Recheck installed game hashes and the original plugin setup. Check BakkesMod
  config differences separately; do not overwrite a player's intervening edits.
- A normal-launch check is a separate acceptance boundary: use the ordinary
  Steam entry without offline arguments or the private file view, and confirm
  the original menu and settings. A file comparison does not prove online play.
- Record each observed result separately. Keep unexercised items unverified,
  especially imported Workshop maps, arbitrary community DLL compatibility,
  full stock-screen lifecycle, and online gameplay.
