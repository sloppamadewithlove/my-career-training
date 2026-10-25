# Native My Career movie

## Pause and results movies

`menus/MctPauseMenu.as` and `menus/MctResultsMenu.as` each have an authored
dynamic movie wrapper and document subclass. Their two compiled ABC files and
`compiled/match-manifest.json` are separate from the unchanged frontend artifact.
The pause document keeps stock pause, resume, and input release behavior while
hiding Friends and matchmaking controls. Both match documents deactivate and
hide the stock party/friends taskbar, including its global input handlers, using
the same shell APIs as the frontend. The results Menu transition reapplies this
guard synchronously; an attached frame listener covers later data callbacks.
Results keeps the stock scoreboard and replaces menu actions. Resume and Options use typed stock callbacks only
for the current validated front menu. Career commands use opaque host control
ids. Return uses the fixed typed `Shell.ExitToMainMenu` only after the service's
durable acknowledgement and a two-stage native authorization exchange. No raw
restart or console navigation command is accepted.

The host first publishes `navigation` with `phase:"authorize"`, a one-shot
`intent`, and the accepted activity and fixture. The current front movie records
that generation locally and sends `return_navigation_consumed`. This log call
has no return value and is not permission to leave. The movie waits for a fresh
host `phase:"execute"` view whose `consumed_generation` matches its own pending
consumption. Only then can that movie issue the fixed exit once. The pause movie
also preserves the stock `m_bExitingMatch` flag. Unloading clears the local
consumption grant; a replacement movie must consume a new authorization.
`return_navigation_issued` records an attempt, not arrival. Completion still
requires the host to observe fresh frontend READY and the real `RootMenuMovie`.

Return retention is explicit: every view carries Boolean `return_pending` and
`return_hold`, and every control carries Boolean `return_commit`. Only an actual
Return commit starts a local hold, limited to two seconds while waiting for the
host. Fresh accepted `return_hold` then keeps Resume, Options, Escape and
controller Back/Start from unloading the movie during cleanup. Stale data,
host error, uncertain navigation or the host's bounded hold deadline releases
normal recovery input; the pending intent remains owned by the host. The
navigation-issued latch prevents another typed exit but does not disable the
host's recovery Quit or ordinary Resume/Options after release.

The authored document screens also consult the current menu's bounded hold
before their own `close(Number)` calls reach stock release/unpause cleanup.
Typed exit and released recovery still use stock teardown. Direct manager or
native removal can bypass that virtual method; fixed diagnostic messages record
whether document close was blocked or the screen disappeared after a held frame.
Removal cleanup is never suppressed, and those messages are not arrival proof.

Rebuilt controls synchronize focus only for the validated front menu, retaining
an enabled matching control and defaulting destructive confirmation to Back.
During a committed hold, pending-only Quit receives no automatic focus. A fresh
arrow or mouse selection can reach it deliberately. Cancel before commit keeps
its normal behavior. These source safeguards still require live keyboard and
controller verification of the exact rebuilt movies.

The two surfaces validate `surface`, session, generation, revisions, and control
types. READY includes the currently validated generation, and continues while
stock Options owns focus. Title/body text explains confirmation, saving, and
error states; bodies are capped at 1536 UTF-8 bytes and wrapped into bounded
native text fields. Real game acceptance must still check text visibility,
scoreboard placement, controller focus, and lifecycle transitions.

Compile each scene with its matching private MidGameMenu or EndGameMenu SDK
plus the MainMenu SDK, all as external libraries. Stage only its three authored
files and the pinned `vendor/as3corelib/src/com` tree into one owned source root.
Use the frontend compiler flags below, substituting the scene's menu entry,
screen and wrapper names. Extract only the resulting DoABC, then verify exactly
three project classes plus seven codec classes, a dynamic wrapper, no linked
game/support classes, no debug paths, and the manifest source/artifact hashes.
The private SDKs and compiler output containers must never be committed.

`menus/MctRootMenu.as`, `MctMainMenuScreen.as`, and `MctRootMenuMovie.as` are original code.
`vendor/as3corelib/` is the unchanged JSON closure from as3corelib commit
`24c6c16aecbf0d8fcc043ae671e689b0d4b4c559`, not project code.
`compiled/MctRootMenu.abc` contains those three classes plus the seven library
classes, intended for a private, version-checked menu composition.
It is not a replacement game file and is not enabled in the release.

Frontend refreshes clear the base menu's callback-based focus restoration before
rebuilding. An enabled control ID is preserved for the same page, including
stable local pagination IDs; title, control-list and explicit pagination changes
choose a fresh safe default. Recovery confirmation defaults to Back. The authored
selection excludes Exit from automatic defaults and synchronizes real focus only
for a validated, attached control in the current front menu. Stock waiting-screen
fallback behavior and physical controller mapping still require live checks.

`MctRootMenuMovie` is a public dynamic, zero-argument wrapper around `menus.MctRootMenu`.
It is compiled under that name because the private SDK already exports
`RootMenuMovie`. The composer renames the compiled string to `RootMenuMovie`
after session binding and renames the original movie's `RootMenuMovie` string
to `MctOriginalRootMenuMovie`. It does not reparent the original class.

`MctRootMenu` imports `com.adobe.serialization.json.JSON` and calls the fully
qualified `encode` and `decode` methods. After the canonical `file:///` guard,
the request uses `decodeURIComponent` of the path. The compiler needs those
classes on one source path. mxmlc drops a source path that sits inside another,
so the reproducible build copies the three authored files and
`native_ui/vendor/as3corelib/src/com` into one owned directory. The tracked
sources stay where they are. The game SDK is only an external library.

```text
mxmlc -debug=false -target-player=32.0 -swf-version=20 -source-path=OWNED_SOURCE
  -includes=MctMainMenuScreen,MctRootMenuMovie
  -external-library-path+=PRIVATE/MainMenu-private-sdk-abc.swc
  -output=PRIVATE/MctRootMenu-only.swf OWNED_SOURCE/menus/MctRootMenu.as
```

`OWNED_SOURCE` contains `MctMainMenuScreen.as`, `MctRootMenuMovie.as`,
`menus/MctRootMenu.as`, and `com/adobe/serialization/json/`. Inspect the
single DoABC before keeping it. The definition order and hashes are in
`compiled/manifest.json`: three project classes and seven library classes,
with no linked game classes. `runtime_verified` and `production_ready` stay
false until that exact ABC is checked in game. The `VIEW_URL` and `SESSION`
placeholders are bound for the owned session when composing the private movie.
See [the composition limits](../docs/NATIVE_MOVIE_COMPOSE.md).

Keep private SDKs and game assets out of this directory. These build tools are
developer dependencies, not player prerequisites.
