# Native movie host

Development-only connection between the authored `MctRootMenu` movie and the
existing career layout. It lives in `plugin/src/NativeMovieHost.cpp`. The
plugin already constructs it, ticks it, and stops it. It does not render a
modal, execute a console command, or write arbitrary game memory.

This is not a compatibility result. `parameter_abi_verified`,
`runtime_verified`, and `production_ready` stay false. A handshake only means
a candidate log callback decoded. It does not mean the movie was visible or
that a controller worked.

## Gate

`MCT_ENABLE_NATIVE_MOVIE_TRIAL` defaults to 0. While it is 0, `tick` and
`stop` do not hash, hook, publish, or call the SDK. `movieReady` stays false
and `status().reason` is `trial_compiled_out`.

In the native candidate (`MCT_ENABLE_NATIVE_MOVIE_TRIAL=1`), the authored
menus own navigation even while their handshake is absent or being renewed.
The legacy fullscreen PluginWindow does not open, draw, bind its shortcut,
or capture input at the title screen, frontend, pause screen or results.
Its nonblocking training HUD remains available during gameplay. The ordinary
overlay build retains its existing menu behavior.

This ownership rule matters when returning from a match: `!IsInGame()` can
describe the title screen before the authored root has loaded. A published
frontend view without a fresh movie handshake does not establish arrival at
the career menu, and must not enable the legacy fullscreen fallback.

When the macro is 1, a host still does nothing until every live check passes:

- `MCT_NATIVE_MOVIE_SESSION` is a canonical lowercase UUID.
- That value equals the current `bridge_session`.
- The `ownedOffline` callback is true.
- The bridge is fresh.
- The game is not online, in a match, or in a replay.
- `GetBakkesModVersion()` is 229.
- `GetPsyBuildID()` is `261013.63066.530866`.
- The running executable SHA-256 is
  `56b499a85ad927c6b5cc47cb4813f956dd9263405fdf4eddc65b669b53185bc7`.

The executable is hashed once for that host attempt. Later ticks recheck
scope and do not hash again. A hash or build mismatch is remembered, and the
log hook is not installed. The fixed output path is
`bridge.directory()/native-view.json`. No command or environment variable
chooses a path.

## API

```cpp
mct::NativeMovieHost(std::shared_ptr<GameWrapper> game, LocalBridge& bridge,
                     std::function<bool()> ownedOffline,
                     std::function<NativeCosmeticContext()> cosmeticContext = {},
                     std::function<bool(const NativeCosmeticRequest&)> applyCosmetic = {});
void tick();
void stop();
bool movieReady() const;
Json status() const;
```

`tick` runs on the plugin's existing game thread. `stop` runs before unload.
The bridge and `GameWrapper` must outlive the host. `ownedOffline` is the
plugin's existing `ownedOfflineNow` check.

`status` contains `trial_enabled`, `view_published`, `movie_callback_seen`,
`commands_accepted`, `commands_rejected`, `parameter_abi_verified`,
`runtime_verified`, `production_ready`, and a short `reason`. It does not
contain the session nonce or command text.

## View and choices

On a live scope the host opens `NativeMovieProtocol` once, with owned,
offline, fresh, `online == false`, the session nonce, and generation 1.
The first active view is written immediately. Every later successful active
write waits at least 250ms of monotonic time, including after a choice. A
backward clock reading does not freeze the next write. `published_at` in the
file stays UTC Unix time. Heartbeats keep the scope generation and do not
reopen the layout, so navigation is not reset by a heartbeat. The movie's
five-second URLLoader limit is why the file is refreshed.
Losing scope invalidates the model and clears readiness. The host overwrites
`native-view.json` with an inactive document only when it previously published
that same nonce. A different session's file is left alone.

When the environment and the bridge agree on a new nonce, the host clears the
queue, the handshake, and the open layout before opening that nonce. It does
not apply a message captured for the previous nonce. The publish interval is
not reset by that change.

The callback checks the current session, owned-offline state, and that the
game is not online, in a match, or in a replay before it reads the caller
header or the parameter block. It still runs only on the recorded game thread.

Drained messages are passed to `select(..., customMovieCallback: true)`, at
most one choice per 250ms. Further choices in that interval are dropped.
Navigate updates the layout model. `PreserveStockRoute` and `LocalCosmetic`
stay off the bridge. The plugin supplies the live cosmetic context on open,
publish and select. A local cosmetic effect invokes its typed callback, which
rechecks the draft/catalog and queues the existing local apply or restore path.
A missing or refusing callback is counted as refused. `Dispatch` calls
`bridge.send` with the effect's own action and payload, after another
ownership and freshness check. Any other effect kind is not sent. A refused,
duplicate, or malformed choice does not clear readiness and does not
invalidate the live view. The queue holds at most eight messages.

## Handshake

The movie can send exactly:

```json
{"protocol": 1, "session": "<nonce>", "event": "ready"}
```

Only a decoded `MCT_NATIVE_UI_V1` callback whose caller passed the historical
object-header check, on the recorded game thread, while the scope is live,
can make `movieReady` true. The exact HELLO is
`{"protocol":1,"session":"<nonce>","event":"ready"}`. Readiness lasts five
monotonic seconds from that HELLO. Later view writes do not extend it, and a
rejected or duplicate choice does not clear it. The authored root keeps sending
HELLO while retained in the menu stack behind a submenu. Its actual Garage and
Options lifecycle still needs game verification. Readiness resets on scope loss, nonce rotation,
stop, or a lost host. Root hides the old overlay only while `movieReady` is
true, and clears that suppression during gameplay. Without the handshake the
old UI stays available.

## Unverified callback

The authored movie calls `tagame.api.DevUtil.Log(String, String)`. The host
registers only `Function TAGame.GFxData_DevUtil_TA.Log` through
`HookEventWithCaller<ActorWrapper>`. `ActorWrapper` is used as an address.
Its methods are not called. `stop` unhooks that one event. The hook captures a
weak lifetime token and returns before touching the host when the token is
gone.

The parameter reader treats the arguments as two unverified 16-byte Win64
`FString` descriptors (`pointer u64`, `count i32`, `capacity i32`) at offsets
0 and 16. The 32-byte header must be 8-aligned. String pointers must be
2-aligned. `count` includes one trailing UTF-16 NUL and no embedded NUL.
Counts and capacities are capped before any string read. Category text is at
most 64 chars. The message is at most 2048 UTF-8 bytes. Invalid surrogate
pairs are rejected. This ABI has not been observed live.
`parameter_abi_verified` remains false even after a decode.

Caller identity uses `NativeMenuIdentityTrial` with the SDK name tokens
`GFxData_DevUtil_TA` and `Class`, resolved with `GetFNameIndexByString` and
checked by a `GetFNameByIndex` round trip. A failed probe is a rejected
callback. It is not an exception escaping into the game. The callback does not
publish, send bridge commands, or do other SDK work.

URLLoader access to the local view file is also unverified. The protocol
document describes that limit.

## Tests

`plugin/tests/native_movie_command_reader_tests.cpp` packs synthetic UTF-16
and descriptor bytes. It covers ASCII and Unicode JSON, exact category
refusal, alignment, unreadable headers, pointer range and overflow, count and
capacity and UTF-8 caps, terminators, surrogate pairs, and failed reads. An
unrelated category does not read the second string.

`plugin/tests/native_movie_session_tests.cpp` exercises handshake expiry while
publishing continues, a backward time reading, nonce rotation without an
invalid gap, stale queued commands, and the 250ms choice and publish caps.
Both test targets are included in CMake. Neither test launches a game.

## Wiring

Root wiring is already in the plugin, not pending. `MyCareerTraining`
constructs `NativeMovieHost` with `gameWrapper`, the local bridge, and
`ownedOfflineNow`. Its game-thread tick calls `tick` and copies `movieReady()`
into the flag that hides the old overlay. Gameplay clears that suppression.
`onUnload` calls `stop` and destroys the host. CMake already compiles
`src/NativeMovieHost.cpp` into `MyCareerTraining` and defines
`MCT_ENABLE_NATIVE_MOVIE_TRIAL` from an option that defaults to OFF. The
command-reader test target is `mct_native_movie_command_reader_tests`. The
session test target is `mct_native_movie_session_tests` and has no SDK dependency.

Leave that option off for a normal build. Turning it on does not by itself
publish a view: the process still needs `MCT_NATIVE_MOVIE_SESSION` set to the
current bridge session UUID, and every live check above has to pass. No CVar
selects the view path.
