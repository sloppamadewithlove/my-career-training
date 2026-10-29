# Gold reset and Training Return

Candidate observed: `6424b12`. Owned source/native offline run, copied Career,
29 October 2026. The test was closed normally; no original Career was changed.

## Observed

- Keyboard Up retried after timeout. A full Right traversal reached all twelve
  Gold challenges, wrapped 12 to 1, and Left returned 1 to 12. Each was observed
  active; transition observations ranged from 0.48 to 1.05 seconds.
- Up inside the open BakkesMod console did not change the attempt. Closing it
  restored ordinary retry. This is generated-key evidence, not physical DS4 proof.
- The native clock probe visibly counted down from 90 seconds and restored the
  original clock/flag, confirmed by direct wrapper readback and visible game HUD.
  RLBot packet time/unlimited fields did not reflect that temporary change.
  This is not yet a production lesson timer or zero-expiry acceptance.
- Repeated Gold 3/5/7 resets exposed floor-contact rejection and one missed retry.
  In nineteen retained first-worker reset snapshots, five resolved contacts had
  opposing tangential/normal impulse ratio 0.35229–0.35454. Stale parked-ball
  snapshots were excluded. Original spawn Z near 30 also caused a second car drop
  after the car had already settled near Z 17.
- Training Return incorrectly opened the unfinished Career confirmation when an
  unrelated saved Career had a pending fixture. The operator selected Back and
  closed normally, preserving the Career. This disproved Return readiness even
  though the earlier backend/native gate fixture passed.

## Repair and checks

The reset clones the authored launch state per attempt. Only a stationary,
flat, grounded scenario car retains its verified settled Z; authored lesson data,
ball, bots and other car fields remain unchanged. Strict capture is excluded.
First-floor confirmation permits bounded opposing friction (ratio at most 0.38,
six units integration margin, opposition cosine at least 0.9, no XY energy gain).
Existing 50 ms, predicted-impact, position, vertical-energy and strict gates remain.

Training Return requests abandonment only for an actual Career activity whose
session and fixture both match its pending fixture. Native menu regression first
failed on the old source, then passed. A real Backend/FileBridge state now also
feeds the native Return test in every candidate build, preserving the saved Career
byte-for-byte. This closes a testing gap between synthetic native and Python tests.

Focused floor/scenario/cadence checks: 160 passed. Full Python run: 1,636 passed,
15 skipped, one checkout-attribute test failed in a tar-only temporary source.
After initializing that temporary Git test context with its existing attributes,
the isolated failing check passed. Native menu and actual-backend fixture checks
passed; planner checks 23 passed; changed Python files passed Ruff.

These repairs still require the replacement live candidate. Native zero timeout,
scored-goal advancement, physical controller, useful shooting/keeper difficulty,
remaining ranks, images, Workshop, Mods, Garage, Options and Quit remain open.

## Command read and next clock experiment

The missed retry had an unreadable Windows command file, not an absent key edge.
The service previously acknowledged a blank ID and deleted that unread command.
Read PermissionError now leaves it for the next poll without manufacturing an ACK;
later commands still progress. A real Windows sharing-lock test verifies retry and
exactly-once handling after unlock; malformed JSON remains rejected and removed.
Combined bridge/ingame/candidate-planner checks: 44 passed, Ruff passed.

The existing development-only 90-second probe is retained. A separate explicit
`mct_probe_training_clock_zero` starts at two seconds in an owned active Power Shots
attempt, observes native zero/end/overtime flags, then restores the same-event
clock fields under the existing five-second lease. A resulting ended match is a
possible diagnostic outcome, not lesson-timer acceptance. No online/gameplay
release behavior is enabled by this command's presence.
