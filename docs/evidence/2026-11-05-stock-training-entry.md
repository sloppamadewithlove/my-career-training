# Stock Training entry candidate

5 November 2026. Base: `ef94b24d73033aa52265602d7cf3bf68f801fd3d`.
Status: `1c21770` + `d98ba04` independently reviewed; source and authored-movie
compilation checks only, not packaged or live accepted. The owner prefers native
game training flow, maps, HUD and behavior with custom lesson/ghost additions.

## Route evidence

Read-only inspection of the installed, pinned MainMenu movie found the stock
root's Play callback uses
`MenuManager.getInstance().enterTreeAtRoot(MenuManager.PLAY_MENU)`.
The manager enters the `PlayMenu` tree and opens the `PlayMenuV4` screen.
Its Back handler closes that screen and exits the tree at its root. This is
the current card-menu route; the older `TrainingMenuMovie` is a separate menu.
Original MainMenu package SHA-256:
`d3e0eeadd2766fa1fb10c2d220c22a84ab2f26fb6bbb89b414a26ef1fd6e2f65`;
movie SHA-256:
`57582fb10fe1e2551989bf15d8aec1df8b62392903974a1e8ea40ac2b1734ec0`.
Extracted movies and selected decompilation remain private.

A separate stock-game test reached Play, Training, Custom Training, Created
and Create New Sequence offline. That establishes the native editor route in
that stock session, not integration acceptance of this new authored-menu row.
Creating a sequence wrote a game-owned training file before a manual Save;
menu exploration is not a guarantee of no profile writes.

## Bounded behavior contract

1. The owned offline frontend is fresh and ready, with no active worker or
   pending result choice. The existing shared `lessonReady` gate allows a saved
   inactive Career. Pending Return disables the new control.
2. The player activates the separate **Rocket League Training** hub row. Its
   explanation says it opens Play and the player should then choose Training.
   The existing My Career Training browser remains unchanged.
3. The authored movie calls the exact stock Play action after its current-root,
   generation, enabled-control and modal checks. It rejects an already-open
   Play screen. Rocket League owns the resulting screen, focus and Back.
   Existing off-front polling avoids rebuilding or refocusing authored controls.
4. This action issues no backend request, starts no worker and creates no MCT
   attempt or training pack. The stock game retains its own persistence behavior.
5. The player uses native Back to leave Play; the source route closes its screen
   and reveals the retained hub. Actual visible arrival and return require live
   verification. No automatic navigation retry or fallback is added.
6. Live acceptance must show one activation reaching stock Play, manual Training
   selection, Back to a responsive authored hub, and preserved Career state.
   Native pack/editor play and returning from gameplay are separate checks.

No branch jump, automatic Create, local training-file parser or private asset
redistribution is included. The owned offline mode is not network or game-save
isolation; a copied MCT profile does not isolate Rocket League's own profile.

## Checks

- Apache Flex 4.16.1 compiled against the existing private external SDK.
  The single authored ABC is 62,608 bytes, SHA-256
  `4abf04d3d0c5a06fda801af5057df744911b21df21c65f58f9a07b6838ea7c82`.
  Export inspection found the existing three project classes and seven JSON
  library classes only. Game classes are external, not bundled.
- Composition, asset staging and candidate tests: 110 passed, one skipped.
- Ruff passed for the changed Python pin/test files.
- Five Release CTests passed: native career layout, movie protocol, training
  browser, menu data binding and match movie. Layout/protocol regressions cover
  the typed stock route, unchanged lesson navigation, hidden active/unknown-worker
  choices and blocked pending Return.
- Independent review found the first gate also rejected a saved pending Career
  without a running worker. A new regression reproduced the missing stock control.
  Correction `d98ba04` reuses `lessonReady`; both affected Release layout/protocol
  targets were rebuilt and their CTests passed after the correction. The authored
  movie did not change.

No plugin DLL, frozen app or installer was produced. No game input was sent.
Independent source review is complete. Exact-candidate packaging and live arrival,
Back and native training behavior remain unverified.
