# OUTCOMES-01 — lesson outcomes, feedback and acknowledgement

DeepSeek source research, reconciled by the coordinator against the relevant
engine, adapter, worker and bridge callers. No tests or game actions were run.
References describe the isolated research source snapshot; see the folder's
source-provenance manifest before applying changes to a different checkout.

## What the lessons actually measure

Legacy lessons require their named events in `_emitted`; Speed Flip also checks
their observed order. Power Shots scenarios use a different score chain.
`training/catalog.py:83-189`, `training/engine.py:826-897`:

| Lesson | Current completion evidence | Teaching boundary |
| --- | --- | --- |
| Speed Flip | Observed first jump, diagonal dodge, opposing pitch, finish-plane crossing and landing in the required order | Opposing pitch is an input observation; the event explicitly does not prove cancellation effectiveness. Landing orientation is measured separately. |
| Flip Reset | A new flip-availability transition with the required approach, contact and geometry evidence | No per-wheel contact event is available; the inference is stronger than proximity alone but is not direct wheel-contact instrumentation. |
| Dribble Flick | Sustained carry, subsequent dodge/double-jump touch and marked goal-plane crossing | Does not grade flick direction or style. |
| Power Shots, legacy path | Player contact and marked goal-plane crossing | Outgoing speed is sampled within 0.1 seconds of contact; this is not a fitted trajectory or a rank-specific speed grade. |
| Shot Placement | Player contact and marked goal-plane crossing | Marked-zone geometry is distinct from an authoritative match score. |
| Fast Aerial | Reaching the elevated gate without a gap at its detection | Gate success alone does not establish two jumps plus correct boost technique. |
| Aerial Air Roll | Three ordered gates and landing | Completion does not require an observed roll input or a minimum upright-landing metric. |
| Flight Recovery | Ordered gates, an observed landing and a grounded car inside the recovery corridor | Forward alignment and roof orientation are recorded but are not thresholded in the recovery predicate. |

The adapter exposes the game's `last_input`, attributed per-player touch, air
state and dodge direction. These are game observations, not physical controller
button capture (`adapter.py:133-153`). Presentation should describe the measured
target separately from a claim that the named mechanic was mastered.

## Scenario attribution and feedback

Scenario success requires an observed launch baseline, a fresh human touch after
launch, a target crossing after that touch, an observed team-0 score increase,
and a valid attribution chain. A telemetry gap permanently invalidates the
scenario chain (`engine.py:477-579`). Mirroring/actor-team setup belongs to the
separate scenario research; the hard-coded score team must be checked against
that setup before reusing this detector for another team.

There is a concrete coverage gap to reproduce: the current `actor_keys` includes
the human and keeper, while `latest_is_human` compares only entries added to that
map (`engine.py:507-527,561-563`). A defender exists in higher-rank scenario
rosters. Recording all actors into `seen_touch` is not the same as comparing all
actors in `latest_touch`. A future test should observe human shot → defender
touch → score and verify the intended attribution policy before changing it.

Feedback priority is success, keeper-after-human, ball-out, missing launch,
missing human touch, then timeout/general no-score. Crossing beyond the standard
field limits sets `ball_out` (`engine.py:529-532,1233-1266`). Consequently, do not
assume every failed goal-chain case displays the no-score message: earlier
branches can win. Future feedback should distinguish an observed score, a missed
marked zone and an unproven attribution chain using the evidence actually held.

`summary().feedback` uses the first observation. Coaching derives stages from
qualifying observed events; its messages and terminal summary are separate
channels (`engine.py:1285`; `training/coaching.py:53-75`). Verify the visible
terminal result with explanations both enabled and disabled before promising
that every result is always shown in the gameplay HUD.

## Attempt completion and durability

1. Each reset creates a fresh attempt UUID. Named events are emitted once per
   attempt, and update stops processing an already-finished engine.
2. The worker publishes completion from either the completed event or the
   finished-state check. `publish_attempt` deduplicates those calls by attempt ID.
3. A sample-less attempt retains its summary but does not supply a recording.
4. The bridge writes a recording when present, adds the summary if its ID is
   absent, then commits the document before sending the acknowledgement.
5. The worker accepts an acknowledgement only for its currently published ID.
6. Reset refuses while publication is unacknowledged. Automatic retry additionally
   needs the preference, an acknowledgement and a retryable sampled attempt.

Sources: `engine.py:204,317-321,583-584`; `game_worker.py:633-634,888-903,973-981,
1318-1323,1374-1392`; `bridge.py:2086-2090,2183-2200`.

This is the successful path, not a transaction across all files and transport.
Recording writes precede document commit; recording IDs are freshly generated
while summaries deduplicate by attempt ID. Storage failures and lost
acknowledgements require the separate persistence investigation. A worker emit
exception must be traced through `run()` cleanup before claiming that it leaves
a live session stuck (`game_worker.py:1583-1594`).

## Corrections and remaining questions

- Carry does **not** preserve its streak across a classified gap:
  `engine.py:800-804` explicitly resets `carry_streak` before target processing.
  A narrower reading of the carry target alone produced a false finding; it is
  excluded from the backlog.
- Zero sampled dodge pitch supplies no sign for an opposing-pitch comparison.
  A diagonal direction can be observed independently, but a yaw-only input is
  not evidence of a valid speed flip. Investigate captured input timing before
  labeling this a legitimate-maneuver false negative.
- Recovery's corridor predicate has no local `not gap` condition, although it
  requires a previously observed landing and gates. Reproduce a gap-marked
  corridor-entry packet to decide whether point-state completion is acceptable
  or continuity must be required (`engine.py:1163-1179`).
- `side=left` mirrors target `position` fields, not goal `center_x` fields.
  Determine which callers offer that option before changing variant semantics
  or existing recording compatibility (`catalog.py:205-229`).

## Minimum acceptance sequence

For each lesson, record the exact lesson/variant, rank where supported, source
and artifact identities; start once from an observed reset; perform both a
qualifying target and a near miss; compare visible feedback with emitted evidence;
confirm one durable summary and matching acknowledgement; then exercise Retry
and Return. Include same-packet event ordering, telemetry gaps, defender contact,
missing recording data and save failure as separate cases. Keep measured target
completion distinct from mechanic mastery, and never infer live success from
these source predicates alone.
