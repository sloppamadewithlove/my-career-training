# Native offline startup integration

The explicit `--native-menu-trial` development path now connects the authored
movie, the compiled file-view launcher and the in-game plugin. It remains a
candidate: preparation, compilation and process-model tests do not establish
that Rocket League displays the movie or that controller navigation works.

The ordinary startup path remains unchanged. Worker, management and package
test modes reject the native trial flag. The trial currently requires Windows,
the matching Steam installation, the normal My Career data directory, and a
plugin receipt with the native movie trial enabled and the diagnostic host
probe disabled. Candidate packaging is described separately in
`NATIVE_CANDIDATE.md`.

## Launch ordering

1. Refuse an existing game or native launcher helper and recover any completed
   temporary plugin session.
2. Create the normal local bridge and use its session nonce for the entire
   native launch.
3. Verify the candidate plugin, prepare a private menu package under the
   player's My Career data directory, and leave the installed package alone.
4. Journal and temporarily stage the My Career BakkesMod plugin, then repeat
   the offline preflight before requesting a launch.
5. Ask the compiled helper to start only its fixed offline game command. The
   Python adapter returns the validated game identity; the helper PID is a
   separate retained process.

The helper supplies the private package view and session environment only to
its newly created game. Neither preparation nor the adapter replaces the
Steam package on disk. The helper's launch receipt is not evidence that the
game actually read the private view.

## Shutdown and interrupted startup

`NativeOfflineSession` retains both a successful owner and an uncertain-start
exception. A launch timeout cannot be treated as proof that no game will
appear. Both bootstrap exception paths honor `defer_restore` and leave the
existing plugin journal and backups in place.

Every `PluginSession`, including callers that supply their own game probe,
also checks for `MctNativeLauncher.exe`. An incomplete process enumeration
blocks recovery. This conservative name check grants no process ownership and
never terminates anything; it also covers an app crash between creating the
helper and receiving its receipt.

On a successful session, the service waits for both the owned game and helper
to exit. The normal online handoff also waits for the helper before restoring
temporary plugin setup and asking the usual launcher to start. A changed or
ambiguous recovery file remains subject to the existing journal checks.
Private prepared-package caches are retained for development diagnosis; they
are not installed into the game or shipped as redistributable game assets.

## Evidence boundary

Mock-process tests cover preparation before staging, a second game appearing
during preparation, uncertain helper startup before a child exists, app
restart recovery, a helper outliving its game, and ordered online handoff.
They never launch Rocket League or BakkesMod. The staged menu runtime has also
prepared two private sessions from the installed source package without
changing that source, as recorded in
`validation/staged-native-menu-preparation-2026-10-24.json`.

Remaining live evidence includes the private file view, GFx file loading and
callback ABI, visible native controls, full Garage/Options transitions,
controller navigation, gameplay and restoration before normal online play.
The public installer hold and all game-verification flags remain unchanged.
