# RESTORE-01 — return, recovery and ownership

Static research of the isolated candidate, supplied by DeepSeek and reconciled
against callers. No game, crash experiment, build or execution was performed.
Source ordering is not proof that a restore succeeds at runtime.

## Three different exits

**Return to hub** retains the game process. `bridge.py:1102-1154` validates session
and fixture identity, handles unfinished-work confirmation, then stops or drains
the active worker. `_close_after_stop` keeps the game alive for restart, return
and abandon (`:2240-2245`). Completion passes through `_finish_native_return`.

**Online handoff** saves, stops, saves again, closes the game, restores the owned
files and relaunches (`lifecycle.py:27-75`; `bridge.py:197-202,2215-2223`).
This differs from the in-session hub return.

**Exit** waits for game shutdown and then restores at bootstrap cleanup
(`bridge.py:2387-2403,2246-2248,2351-2378`; `bootstrap.py:370-384`).

The native hub return has a separate durable-state gate. `NativeReturnGate.h`
requires exact session/fixture and nonce identity; fresh, offline, owned state;
an Idle/hub receipt with no active session/worker/busy/error; and arrival at the
frontend root (`:41-136,247-279`). Its authorization is bound to pause/results
and a generation-bound execute view. A 15-second hold expiry does not itself
erase the return intent. An in-memory lifecycle label alone cannot satisfy it.

## What can be restored after a process restart

| Resource | Recovery evidence | Limit |
| --- | --- | --- |
| Owned plugin/config/overlay files | Durable plugin-session journal and prior bytes; unresolved resources remain journaled for retry (`plugin_session.py:322-363,475-586`). | Restore also checks process/helper ownership and whether the file still matches the owned value. |
| Legacy map replacement slot | Map recovery journal (`map_guard.py:82-116`). | Its live-process gate differs from plugin recovery. |
| Result receipts | Outbox JSON recovered during Backend construction (`bridge.py:186,2154-2181`). | An unreadable receipt sets an error and remains present in the inspected path. |
| Community session | Existence and recovery gate inspected (`native_community_binding.py:31-43`). | Journal contents were outside this pass; no conclusion about everything it preserves. |
| Overlay cvars | In-memory ownership snapshots; eligible-scope exit, shutdown and tick failure paths restore them. | No durable snapshot found in the inspected overlay code. Persistence after a game crash/restart is unknown. |
| Four training D-pad bindings | In-memory previous bindings and release/retry handling (`TrainingLessonInput.h:259-305`). | Restore only while the current value still equals the owned command; failed restoration retains retry state. |

Overlay restoration is not unload-only. `ControllerOverlaySession::tick()`
restores on scope exit, reconciles settings while active, and stops owning a
value changed by the user (`ControllerOverlaySession.h:41-67,194-251`). The
plugin tick catch path also releases bindings and overlay/cosmetic ownership
(`MyCareerTraining.cpp:1420-1468`). Whether those callbacks run before an abrupt
process death remains unobserved. Lack of a durable cvar snapshot does not prove
that a cvar survives a full game restart.

## Recovery gates and retry behavior

Plugin and community recovery consider both a live game and a pending native
launcher helper. The map recovery gate checks the game process only
(`plugin_session.py:188-191`; `native_community_binding.py:40`;
`map_guard.py:99-102`). With a live game, both map and plugin recovery refuse;
ordering changes the first error surfaced, not proof that one restore is lost.
With only a live helper, the gates differ. Whether this matters depends on the
helper's future child process behavior and the applicable launch route. That
consequence remains unverified; the legacy map route should not be confused
with every Workshop launch.

A present plugin journal plus a live game/helper blocks startup recovery and
returns an error before UI creation (`bootstrap.py:270-275`). With no live
owner, partial restore retains only unresolved resources for a future retry.
With no journal, the recovery call returns idle without restoring files. This
does **not** mean the rest of a clean launch never installs or writes files.
Exit-time deferral is surfaced after the window closes (`bootstrap.py:378-387`).

`can_retry` belongs to the online-handoff lifecycle error path; it should not be
read as a universal worker retry control. Worker error/disconnection UI behavior
needs a separate caller-to-visible-control trace. This report did not inspect
all community-session contents or every QML/native error surface.

## Application contract

Preserve the distinction between hub return, online handoff and exit. Show
pending/failed restoration separately from training completion, retain durable
receipts until success, and respect user changes to owned settings. Future
acceptance should cover successful hub receipt/arrival, partial file restore,
game/helper deferral, in-session scope exit, binding conflicts, and recovery UI.
Use isolated fixtures for file contracts and an explicitly owned game session
for actual cvar/binding lifetime and frontend arrival. None is claimed passed here.
