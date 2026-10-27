# SETTINGS-RESTART-BOUNDARIES-01 — disconnect, reload, restart and lost ACK

Read-only audit of the frozen `work/reviewed-training` snapshot. No tests were
run and there was no game/process interaction. Base Git commit is
`1fe8c85839a5e72166ee1d5cc3066627548d9fa2`; the reviewed tree is dirty, and
several listed files are modified or untracked. Fingerprints below identify
the bytes inspected, not a clean commit artifact.

This focuses on crash/restart and acknowledgement intersections. Normal lesson
settings and Return behavior are described in [`settings-01.md`](settings-01.md)
and [`restore-01.md`](restore-01.md); cosmetic edit ownership and Return policy
are detailed in [`garage-restore-01.md`](garage-restore-01.md).

## What survives each boundary

| State | Normal lesson Return | Service disconnect | Clean plugin reload | App/game restart or crash |
|---|---|---|---|---|
| Training checkbox preferences | Committed to the career store; reused next lesson. The live worker is stopped/reset separately. | Last saved preference remains; active native state becomes stale. | Preferences come from the still-running service’s state file. | Per-lesson/global settings survive because `Store` loads/saves its JSON document. A new `Backend` starts with `process=None`, `request=None`, `session_id=None`; an active lesson is not rehydrated. Reopening while Rocket League is still running is refused by startup recovery or offline preflight. |
| Controller Overlay Pro package files | No package restoration is implied by ending one lesson. | The desktop FileBridge is separate from the plugin-session file journal. | The package may stay staged for the owned game session. | When plugin/config/overlay files need changing, `PluginSession` journals prior bytes and a receipt before replacing them. Startup/finish recovery refuses or defers while Rocket League or its pending launcher helper is alive; it can restore after both close. This journal does **not** store `xco_*` cvar baselines. |
| Controller Overlay Pro `xco_*` cvars | `ControllerOverlaySession::tick` becomes ineligible outside a live training lesson and attempts to restore the saved baseline. | The plugin polls state freshness. When `fresh` becomes false, its overlay scope is ineligible and restoration is attempted. | `onUnload` calls `shutdown()` up to three times; if values remain owned it logs them, then destroys the in-memory session object. | The baseline is held only in the plugin object. A surviving plugin can run the stale-state cleanup path; a clean unload can attempt cleanup. No durable cvar snapshot exists for recovery after the plugin/game stops before cleanup. Whether BakkesMod persists cvar values across a crash/restart is unverified. |
| Cosmetic override cvars | No restore call is made just because the owned offline session returned to its hub. The source calls restore for explicit Restore, stale/unowned scope, tick failure, and plugin unload. The intended Return policy remains unresolved in `garage-restore-01.md`. | Stale/unowned scope reaches `restoreCosmetics()`; retries occur on later ticks while that object remains alive. | `onUnload` attempts restore once and logs failure. The object is then destroyed, so an unsuccessful in-memory retry snapshot is lost. | `CosmeticOverrideState` stores the original code/enabled pair only in memory. No durable recovery record exists; next-process cvars are not joined to the pre-crash baseline. Actual game persistence is unknown. |
| Training attempt save acknowledgement | Parent commits the attempt/recording before sending `attempt_ack`; worker retry/auto-reset waits for matching attempt identity. | A lost ACK leaves that worker’s attempt pending. The missing ACK alone does not start telemetry recovery. | Native plugin reload is separate from desktop worker lifecycle; no worker reset is tied to the plugin unload path. If a worker is independently replaced, its new in-memory state does not resume the old attempt. | The saved attempt remains if the store commit completed, but there is no attempt ACK outbox/replay or active-lesson resume. This differs from career match results, which have a durable result receipt. |

## Source trace and precise limits

### Preferences versus active session state

`Store.load()` validates and reads the persistent document when `Backend` is
constructed (`src/my_career_training/storage.py:144–156`; `bridge.py:112–124`).
Global training-display preferences are committed before an active worker is
sent the update (`bridge.py:1246–1255`). Per-lesson training checkboxes are
normalized, committed to the store, then sent to an active worker
(`bridge.py:1407–1418`; `_commit()` calls `store.save` before replacing the
in-memory document at `bridge.py:734–736`; see
[`settings-01.md`](settings-01.md)). In the same constructor, the active
process, request and session identity are initialized empty
(`bridge.py:137–150`). New startup does not resume the prior worker’s lesson
state.

Startup recovery and launch gates make that boundary explicit. The app calls
`recover_plugin_session()` before it creates a new FileBridge or launches the
game (`bootstrap.py:106–124,270–295`). `preflight_offline()` refuses an already
running Rocket League process or pending native launcher (`bootstrap.py:142–151`).
Thus a relaunch is not an attach/resume mechanism; a retained game must be
closed before the ordinary launch/recovery route proceeds.

### Files versus cvars

`PluginSession.begin()` writes a durable receipt and backups before replacing
plugin/config/overlay files when changes are needed (`plugin_session.py:209–341,460–474`). `recover()`
and `finish()` preserve that receipt while the game/helper is live; the
`PluginSession` guard combines the game probe with the native-helper probe
(`plugin_session.py:180–191,350–363`). Resource restoration checks owned file
content and leaves mismatched replacements for review (`plugin_session.py:544–672`). Existing tests cover recovery using a new
`PluginSession` object and live-game deferral (`tests/test_plugin_session.py:87–126,387–411`).
Those fixtures target the **file** journal contract, not cvar rollback or
actual plugin reload; this research pass inspected them without executing them.

The native plugin’s `LocalBridge::validState` accepts state no older than five
seconds (`plugin/src/LocalBridge.cpp:139–146,209–212`). On each plugin tick,
`offlineReady_` depends on fresh bridge state and owned offline scope;
`maintainControllerOverlay()` receives that freshness every tick
(`plugin/src/MyCareerTraining.cpp:1266–1286,1452–1476`). The overlay session
restores when that scope is not eligible (`plugin/include/ControllerOverlaySession.h:41–66`).
The same plugin tick calls `restoreCosmetics()` in its stale/unowned branch
(`MyCareerTraining.cpp:1387–1400`). An orderly FileBridge close publishes an
invalid session immediately (`src/my_career_training/ingame.py:148–150`); an
abrupt service death leaves the last publication to age out. This gives a
source-level cleanup path if the game/plugin remain alive and ticking; no
runtime cvar effect is claimed.

On clean plugin unload, Controller Overlay Pro receives three shutdown attempts,
then any remaining owned fields are logged before the object is reset
(`MyCareerTraining.cpp:259–275`). Cosmetics receive one restore attempt at
unload (`:286–287`). `ControllerOverlaySession` keeps its prior/applied values
in object fields (`ControllerOverlaySession.h:98–124`); `CosmeticOverrideState`
keeps `original_` and `pending_` in object fields only (`CosmeticOverrideState.h:24–68`).
Neither is written into the plugin-session journal. The overlay unit fixtures
exercise the class shutdown/restore path, and cosmetic fixtures exercise retry
inside the same object; neither simulates a real DLL reload or process crash.

There is no automatic cosmetic restore on ordinary in-game Return in the
inspected caller set: `restoreCosmetics()` is called for explicit Restore,
stale/unowned scope, a tick exception and `onUnload`, not on a transition from
lesson to hub (`MyCareerTraining.cpp:1393,1433–1434,1581–1587,1632–1645,259–287`).
Do not treat Return as a proved cosmetic cleanup boundary. The prior garage
report leaves the intended retention/restoration choice open.

### Stale command IDs and training ACKs are different protocols

The native-menu FileBridge creates a fresh UUID session on construction and
accepts only commands carrying that exact session. It tracks command IDs in an
in-memory set, skips IDs already retained, dispatches valid new IDs, publishes its
current `command_ack` state, and deletes each command file, including stale-session commands
(`src/my_career_training/ingame.py:77–116`). When the set exceeds 4,096 IDs it
is replaced with an arbitrary 2,048 IDs selected through set/list conversion
(`ingame.py:111–113`). Duplicate suppression therefore applies only while an
ID remains retained in that same session; it is neither durable nor unbounded
exactly-once delivery. A new session rejects old-session files. The plugin
writes commands tagged with the current session (`plugin/src/LocalBridge.cpp:272–288`).
The existing test confirms stale-session actions do not dispatch and one
repeated command ID is consumed only once while retained
(`tests/test_ingame.py:24–45`). This does not acknowledge a training attempt.

For training attempts, `Backend._event()` saves the recording and summary, then
sends the exact summary ID (`bridge.py:2087–2091,2183–2201`). The worker ignores
a mismatched ID and marks only `attempt_id == attempt_sent` acknowledged;
matching duplicates do not extend the one-second auto-reset deadline
(`game_worker.py:633–653,973–982`). Manual Retry is blocked while the attempt
lacks its ACK (`game_worker.py:633–635`). A missing ACK by itself does not
initiate telemetry recovery: recovery is entered when packet validation raises
`InvalidTrainingTelemetry`, and the deadline is initialized only for active
phase (`game_worker.py:1239–1250,833–847`). The dedicated missing-save-ACK error
is reachable only if recovery has a deadline, fresh telemetry has been
observed during recovery, and the attempt remains unacknowledged when the
timeout check runs. A timeout before fresh telemetry reports telemetry
unavailability instead
(`game_worker.py:814–826,849–862,1552–1560`). Continued valid frames alone do
not create this timeout. The attempt ID/ACK state lives in the worker object
(`game_worker.py:282–288,1376–1388`). The parent does not persist a
training-attempt ACK receipt or replay it after process restart. If the parent’s
durable save completed, the attempt data remains; whether the old live worker
is still running after an abrupt desktop-process failure is not established
here.

Career match results use a separate path: the worker atomically persists a
per-session result in `outbox` before emitting it (`game_worker.py:55–74,1330–1337`);
the parent commits the career result before deleting that receipt and reloads
pending receipts at Backend construction (`bridge.py:186,2112–2181`). Existing
tests cover the result receipt surviving a simulated save failure and replaying
once (`tests/test_bridge.py:835–884`) and the worker writing its receipt before
emit (`tests/test_worker.py:37–75`). This durable result contract must not be
extended by assumption to attempt ACKs.

## Existing coverage versus restart gaps

Inspected, not executed:

- `test_plugin_session.py:87–126,387–430` covers file-journal recovery, a new
  session reading a crash receipt, and live game/helper gates.
- `test_ingame.py:24–45` covers stale native command session and duplicate ID.
- `test_worker.py:37–75,212–247` covers match-result outbox-before-emit, wrong
  attempt ID rejection, exact attempt ACK, and duplicate-ACK timer behavior.
- `test_bridge.py:835–884,1017–1029` covers match-result receipt retry and the
  parent sending the worker’s exact attempt ID.
- `controller_overlay_session_tests.cpp:154–176,213–227` covers the class
  unload/shutdown and in-memory restore retry fixtures. `cosmetic_override_state_tests.cpp`
  covers partial apply/restore and same-object retry.

I found no test that reloads the actual plugin after failed cvar restoration,
crashes the app/game between apply and restore, persists/replays a training
attempt ACK, or constructs a fresh Backend after a training ACK is lost. The
match-result test retries `_recover_outbox()` on the same backend instance; it
does not by itself prove a full process restart.

## Builder acceptance cases

1. **Return:** use saved On/Off training preferences; return from a lesson and
   verify the preference remains durable and the Controller Overlay lease
   returns to its prior values. Separately assert the chosen cosmetic Return
   policy; do not infer it from the lesson checkbox.
2. **Service disconnect:** stop publishing FileBridge state while the owned
   offline game remains alive. After freshness expires, verify cleanup is
   attempted for both cvar leases; reconnect with a new nonce and prove old
   command files are rejected without a second dispatch.
3. **Clean plugin reload:** apply both leases, invoke normal unload/reload, and
   confirm exact prior cvars plus new-session baseline. Inject restore failures
   and verify the logged/pending outcome is surfaced before claiming cleanup.
4. **App restart with game open:** confirm My Career refuses attach/second
   launch, preserves its file receipt, and does not claim the lesson resumed.
   After closing the game, recover files, reopen, and verify persisted checkbox
   choices while starting a new lesson.
5. **Crash boundary:** independently interrupt before plugin cleanup and after
   the attempt store commit but before worker ACK. Require truthful recovery
   status for files, cvars, saved attempt and worker state. If cvar baselines are
   not journaled, state that crash recovery is unsupported rather than showing
   “restored.”
6. **ACK identity:** wrong/old attempt IDs remain rejected; exact ACK unlocks
   retry once; duplicate exact ACK does not extend feedback time. On restart,
   ensure no ACK from the old worker authorizes a new attempt, and add a separate
   fresh-Backend test for any promised result-receipt recovery.

## Fingerprints (SHA-256)

| File | Bytes | SHA-256 |
|---|---:|---|
| `src/my_career_training/storage.py` | 8,410 | `3a291463f8ffdbab63adc4197a5b957413452aa011d4491895c722c151dd10de` |
| `src/my_career_training/bridge.py` | 139,135 | `ac502d1f19810baca479a534aa766a6afbea7ba57a405452835cc9dcff379ac2` |
| `src/my_career_training/ingame.py` | 7,381 | `40b79ba174318cd906bf3241cc121ee19c79a9814705457e2078b94b83f42b16` |
| `src/my_career_training/game_worker.py` | 90,814 | `2e3982dfc352e4fafcd667898b3cb1f76538b61447c2b6e47adc6d9f862e89c2` |
| `src/my_career_training/bootstrap.py` | 19,049 | `82fef12f0d472ed0927996ff691e4b9babb1884ba9f8c02df4315b49557ca7ec` |
| `src/my_career_training/plugin_session.py` | 32,221 | `27c48c4be089b810c7b4843a6bf5a6d3baf08a8bba5be0d8501de2e6eef2919f` |
| `plugin/src/LocalBridge.cpp` | 13,752 | `284cebdbbb18d1d2571ba28b35003061187be85753d0c2ad5ddaeb7b59335c66` |
| `plugin/src/MyCareerTraining.cpp` | 89,835 | `edc7bf5a6dc7ca0cff34ac694fb72fe71fa26dfe1fd4607d512f3b321a1a9279` |
| `plugin/include/ControllerOverlaySession.h` | 10,805 | `8289082e59c226e08ebe2ec06c42e4f1f848958c916367745fda4a695e992482` |
| `plugin/include/CosmeticOverrideState.h` | 2,830 | `dc2e5183d2b0b8f96b18696dfcd6b509c7a2bf8a9daf03e1f4861cb07382dab7` |
| `tests/test_ingame.py` | 13,312 | `c2b86909ecfced297d6d7a30d603221a09e3e9c3c253b7a762e9ca7275388c18` |
| `tests/test_plugin_session.py` | 18,706 | `bf122ca3b87d26e7acb5498802ce26740b5a79d9e964db9bc8b09cd675826ad1` |
| `tests/test_bridge.py` | 83,171 | `5b3bafe6819319a9b77d332a9c9c0db78dcdc5aaf95781482429d275b1d39cec` |
| `tests/test_worker.py` | 40,440 | `d10ebb2a6e707633a278ed3c93b70de3185db04564ecc3180d6a9d7731e6aa11` |
| `plugin/tests/controller_overlay_session_tests.cpp` | 20,545 | `cb0360d21f3726b1bdfe0263933cd1c96bed9342ae683be5eefb9ac67c52eb71` |
| `plugin/tests/cosmetic_override_state_tests.cpp` | 4,292 | `3fa861f9613fe807b05adee211fa5e61f16930d126bac7f37f80257ecd6e1dda` |
