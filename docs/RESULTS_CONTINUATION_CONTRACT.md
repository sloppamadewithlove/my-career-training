# Results menu and continuous career play

Owner decisions, 25 October 2026. This is the implemented behavior contract;
see PROJECT_STATUS.md for revision-specific source checks and remaining packaged
gameplay acceptance. Preserve the current Return acknowledgement and fresh
native-root arrival requirements.

## Player behavior

The finished career-match menu has exactly this normal top-level order:

1. Play Next Match
2. Schedule
3. Change Preset
4. Settings
5. Exit

Exit returns to the My Career hub. The hub's close-app control is labelled
**Quit My Career**, replacing Exit there. Error/recovery controls may be shown
when necessary, without pretending that an unsaved result is ready to continue.

Schedule is a read-only view of the player's career schedule on the existing
results screen. It includes completed/forfeited and upcoming fixtures, supports
bounded paging when needed, and returns to the same results menu. It must not
stop the worker, navigate to the hub, alter a result or start another fixture.
There is no player-facing time limit on the results or schedule views.

Play Next Match immediately begins continuation using the current saved lineup.
There is no preview, extra setup menu or second Start confirmation. The player
can change the lineup separately in Squad before playing. A completed season with no next fixture disables
continuation with an explanation; it must not silently create a new season.
After that single click, continue using the same owned Rocket League process. Internal
frontend travel needed by the verified engine path is allowed; another manual
hub/Play click and another game process are not required.

Change Preset uses only the game's existing local presets and typed preset API.
Settings opens the game's own Settings directly. Do not route either through a
combined Game options submenu. Do not claim arbitrary cosmetic unlocks. Use
verified game API signatures; keep extracted game source/assets private.

## Service/native boundary

Keep continuation separate from result persistence. The completed result must
already be durably saved, its pending fixture clear and its exact session/fixture
matched. Neither Schedule nor duplicate continuation requests may award it again.

The native host creates a fresh 32-character lower-case hexadecimal intent.
`prepare_next_match` takes exactly:

```json
{
  "expected_session_id": "finished-session",
  "expected_fixture_id": "finished-fixture",
  "expected_next_fixture_id": "next-fixture",
  "lineup_ids": [],
  "continuation_intent": "0123456789abcdef0123456789abcdef"
}
```

Before preparation, reject an existing `pending_launch`, active stop or lifecycle
transition; another queued launch must not cross the continuation barrier.
The service validates its current finished career activity, stored result,
current next fixture and the complete lineup before stopping anything. Persist
the valid lineup preference atomically without rewriting the completed result.
Prepare cleanup through the existing return lifecycle. Before commit, an exact
rejection may restore usable results controls. After commit, cleanup errors must
not be misreported as an uncommitted rejection. Repeated identical preparation
is idempotent; stale or different bindings cannot replace an accepted intent.
Keep this preparation separate from `pending_launch`: do not call
`_prepare_launch` or create a pending fixture before native arrival. Existing
cleanup can automatically run `pending_launch`, so it is not this feature's queue.
Retain the exact confirmed lineup in the prepared token and revalidate it at
start; an intervening edit must not silently substitute another lineup.
While prepared continuation is armed, block competing launches and career edits,
including the short Idle/root interval before automatic start. Quit stays usable
and cancels the unstarted token and next-match ACK before shutdown begins.

After durable cleanup, retain the existing exact `native_return_ready` ACK and
publish `native_next_ready` with exactly `session_id`, `fixture_id`,
`next_fixture_id`, and `intent`. A precommit `native_next_rejected` contains
exactly `session_id`, `fixture_id`, and `intent`. No generic error alone revokes
an accepted Return/continuation intent.

The host uses the existing typed `Shell.ExitToMainMenu` authorization,
consumption, attempted-navigation and arrival sequence. Store continuation in a
separate gate bound to the owned game, nonce, finished activity/fixture, target
fixture and intent. Movie unload must not erase it. Do not weaken the Return
gate to permit a new match merely because service state is Idle.

The exact `native_next_ready` also qualifies the existing Return authorization;
an unrelated ordinary Return acknowledgement alone cannot authorize this intent.
Only after the exact ready acknowledgement and **fresh frontend READY plus real
RootMenuMovie arrival** may the host send `start_prepared_match`, once, with
exactly `expected_session_id`, `expected_fixture_id`,
`expected_next_fixture_id`, and `continuation_intent`. The service rechecks its
prepared token, the saved result, no active worker/pending fixture, and current
target fixture. Reverify in-game mode and the same still-running owned game
identity captured at preparation before any launch/save side effect. If that
game closed, reject without reserving a fixture or launching a replacement.
Reject an active stop, lifecycle transition or existing `pending_launch` too.
Then use the existing `play_match` launch path. Keep token
consumption idempotent, including a duplicate during startup. Failures must
leave an understandable recovery route without automatically replaying a launch.
Process restart cancels unstarted continuation; it preserves saved progress and
does not silently launch a match on startup.

## Native layout and retention

Use local native page state for Schedule; bind it
to the current finished activity. Preserve stale-generation/consumption checks,
safe Back focus, and the exact binding represented by each visible control.
The results root contains the five requested controls only. Secondary pages may
contain their own Back and paging controls. The root Play Next Match is a
committing dispatch, so the existing immediate Return hold applies to that click.

Hide the misleading stock NEXT MATCH IN countdown in the authored results view.
Retain the proven, scoped finished-state timer refresh internally. Do not modify
the Soccar play clock, revive an expired timer, or preserve retention over an
unrelated stock screen. The direct Settings route still requires live stack
verification; Change Preset and Schedule must retain the current results scope.

## Required checks

- Source/domain: duplicate preparation/start, stale session/fixture/next fixture,
  invalid lineup, save failure before stop, late result receipts, cleanup error,
  no next fixture and restart cancellation.
- Native: exact five-button order; local Schedule/Back without dispatch;
  fresh matching continuation ACK and root arrival before one launch;
  no launch on title/Idle/stale READY; preserved intent across movie unload;
  scoped rejection and existing Return/Forfeit regressions.
- Assets: compiled authored movie and synchronized hashes; no proprietary files.
- Live: real saved match → Schedule for more than the old timeout → Back;
  Change Preset/Settings/Back; one Play Next Match activation starts the next
  fixture with the saved lineup in the same game process; Exit reaches the hub; Quit My Career
  closes normally; exact frozen save/continue/exit/restart and restoration.

Keep source, native, frozen, installer and actual game evidence separate. The
physical USB DualShock 4 check remains deferred until the owner is available.
