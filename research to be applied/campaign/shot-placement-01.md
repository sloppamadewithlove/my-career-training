# SHOT-PLACEMENT-01 — legacy shot placement evidence and tier boundary

## Scope and result

This is a static audit of the frozen My Career Training source and its existing
tests. No tests or game actions were run. The built-in **Shot Placement** lesson
is a legacy single-setup drill: a fresh player-attributed touch plus the ball
center crossing its selected world-space goal rectangle is enough for success.
The detector does not require the game to award a goal, does not measure shot
quality or technique, and does not grade a rank.

This is separate from both nearby paths:

- **Power Shots scenarios** use an authored launch → fresh Human touch → target
  crossing → team-score increase chain, with scenario attribution rules
  (`training/engine.py:477-579, 815-830`). The prior outcome-probe report studies
  defender/keeper attribution on that scenario path; it is not evidence about
  Shot Placement.
- **Ground Dribble & Flick** requires sustained carry, a qualifying later touch
  while jump/dodge state is observed, and a goal target event. It has a carry
  and flick-specific contract absent from Shot Placement
  (`training/catalog.py:109-121`; `training/engine.py:1116-1158`).

## Setup and selectable variants

`training/catalog.py:53-77, 132-141` defines Shot Placement as catalog version 1
on `DFHStadium`, with a 15-second timeout. Its default car starts at
`(-650,-2100,17.01)` with rotation `[0, π/2, 0]`, zero velocity and angular
velocity, and 100 boost. The ball starts at `(-400,-900,93.15)` at rest. The
default target rectangle is centered at world X=480 with half-width 300 and
vertical bounds Z=93..500; the engine tests the goal plane at world Y=5120.

`_lesson()` creates a settle state using the lesson's car start but parks the
ball at `(3000,0,93.15)` (`catalog.py:53-77`). After sampled readiness, the
engine applies the starting state and only begins the 15-second attempt clock
when it observes that state (`training/engine.py:627-785`). This distinction
matters for a reproducible tier profile: the settle pose is not the shot setup.

The native lesson page offers a target-zone choice and an approach-angle choice
(`plugin/include/NativeCareerLayout.h:1835-1884`). For this lesson,
`configure_lesson()` maps zones as follows: left X=-480, center X=0, right
X=480 (each half-width 300), and whole X=0 (half-width 750); it leaves the
vertical range unchanged (`catalog.py:206-230`). The approach-angle choice
sets the car's starting X to -900 or +900, while center preserves the default
-650; it does not change the ball or target. The separate `side` option only
reflects targets with an explicit `position`, so it has no effect on this
lesson's goal target or starting state. These are setup variants, not difficulty
tiers.

## Contact, target crossing, confidence and score authority

The adapter copies each player's own `latest_touch` time and position into that
player record (`adapter.py:133-150`); the worker supplies the sole non-bot Human
as the legacy lesson's observed car (`game_worker.py:1205-1236`). `_touch()`
prefers that player's touch and falls back to a global ball touch only when its
player index matches (`training/engine.py:89-96`). `_contacts()` accepts a finite
touch timestamp if it is new and falls within the previous/current sample
bracket with a ±0.02-second allowance. It emits `ball_contact` once, with
`observed` confidence on continuous cadence or `uncertain` confidence on a gap
packet (`engine.py:990-1025`). This is attributed game touch telemetry; there is
no independent collision/proximity test for this lesson.

For a goal target, `_targets()` only considers a positive-direction crossing
from old Y<5120 to new Y>=5120 on a non-gap packet. It linearly interpolates the
ball-center crossing location, tests X against `center_x ± half_width` and Z
against the configured bounds, and records `shot_location` and `target_hit` for
that crossing (`engine.py:1137-1156`). A hit emits `goal_target` if the
`ball_contact` name has already entered the attempt event set
(`engine.py:1157-1162`). The target check is about the ball center at the marked
plane; it does not model goal collision geometry or ball radius.

For ordinary lessons, completion checks that the configured event names are in
`_emitted`; `_ordered_success()` applies chronology only to Speed Flip
(`engine.py:818-830, 852-855`). Shot Placement therefore requires the contact
and target names but has no explicit timestamp comparison proving that the
contact preceded the interpolated crossing. `_contacts()` runs before
`_targets()` within an update, so a contact and crossing in one coarse packet
can be accepted even when their ordering inside that packet is unknown. A
crossing handled in an earlier packet before any contact does not itself emit
`goal_target`; a later qualifying crossing would be needed.

There is also a confidence mismatch: a gap-packet contact is uncertain but
still enters `_emitted`; a later clear target crossing can then complete the
lesson because the final check tests event names, not event confidence. The
coaching stage counts only observed or strong-confidence events, so the result
can be successful while its Contact stage remains unconfirmed
(`engine.py:990-1019, 818-830`; `training/coaching.py:49-75`). A gap-marked
target crossing itself is ignored.

The authoritative evidence here is the engine's observed ball-center crossing
against the selected rectangle, conditioned on an attributed touch event. The
legacy path does not consult match scores for completion; authoritative score
gating belongs to the distinct Power Shots scenario branch. Consequently a
rectangle hit can succeed without a scored goal, and a goal score outside the
rectangle is not sufficient (`engine.py:825-830, 1137-1162`).

## Instruction versus measured success

The catalog says to aim at a chosen zone, strike, and review the goal-plane
crossing (`catalog.py:132-141`). Coaching presents Contact then Target stages
and describes them as observations, not technique grades
(`training/coaching.py:28-33, 49-75`). The detector does not grade aim direction,
car orientation at contact, contact impulse, shot trajectory, or target margin.
The generic engine does record `sampled_outgoing_ball_speed` and
`outgoing_speed_sample_after_contact_seconds` from observed ball velocity for
up to 0.1 seconds after the sampled contact packet (`engine.py:1019-1028`), but
Shot Placement does not use those metrics as completion criteria or compare
them to a shot-quality threshold. A miss can record its interpolated location,
but only the inside/outside rectangle predicate affects `goal_target`. Generic
timeout feedback recommends aiming the next contact and reviewing the measured
crossing; it is not a diagnosis of why the shot missed
(`engine.py:1216-1228`). No validated equivalent teaching reference is
installed (`catalog.py:53-77`; `engine.py:1286-1288`).

The deadline is 15 game-clock seconds from the observed start packet. Each
update processes events before checking the timeout, but timeout is checked
before the ordinary success-set decision. Thus an otherwise qualifying event
set first seen on or after the deadline finishes as timeout
(`engine.py:754-785, 811-830`). Retry assigns a new attempt ID, clears the
start clock, events, event-name set and recorder, then returns the settle state; the worker
applies a whole-state reset and blocks retry until a sent result is acknowledged
(`engine.py:203-267`; `game_worker.py:627-655`). This is source behavior, not a
claim about observed in-game outcomes.

## Existing test coverage inspected (not run)

`tests/test_training.py:22-73` provides a synthetic frame helper and activation
helper. Its only direct Shot Placement case is
`test_gates_are_ordered_and_goal_location_interpolates_observed_samples`
(`tests/test_training.py:303-316`): it injects a touch timestamp and two ball
positions crossing the default target, then asserts success and the
interpolated location. It does not test a target-zone variant, miss/edge
geometry, goal-score disagreement, contact confidence on a gap, contact/crossing
order within a packet, deadline boundaries, or retry state clearing.
`tests/test_training_ghost_practice.py:232-236` also includes Shot Placement in
a loop asserting that ghost practice is unsupported for ball-dependent lessons;
it does not exercise the outcome detector. A search found no other Shot
Placement or target-zone outcome cases. These synthetic unit inputs do not
represent a gameplay result.

## Requirements for future eight-tier profiles

The current eight-rank selector is Power Shots-specific. The bridge accepts
scenario and difficulty together only for Power Shots; other lesson start
requests accept the lesson ID, with saved setup variants passed separately
(`bridge.py:1726-1792`; `training/scenario_setup.py:8-50, 94-107`). Existing
recordings identify the lesson/version and setup variant, but have no practice
rank/profile identity (`training/recordings.py:145-172, 204-273`). The
curriculum report likewise classifies Shot Placement's zone and angle as
variants, not ranks (`work/campaign/curriculum-01.md`).

If Shot Placement receives Bronze-through-Supersonic-Legend practice tiers,
keep them as MCT challenge labels rather than estimates of competitive rank.
Each tier needs a stable lesson/profile ID and profile version, an exact
deterministic setup (including starting pose, ball state, target rectangle,
map and mutators), declared challenge dimensions, timeout, and a measurable
outcome contract. State explicitly whether passing means a marked-zone crossing
or an actual score. Specify fresh Human-touch attribution, timestamp ordering,
gap/confidence policy, miss reasons, and the evidence needed for any technique
claim. Potential challenge dimensions include target offset/width, approach
angle/distance, or ball-feed trajectory; set no tier values until they are
authored and separately validated. Store the tier ID/version with selection,
attempt, recording and ghost compatibility so a result cannot silently move
between profiles. Existing
Power Shots numeric speed, timeout, or opponent settings do not calibrate these
profiles; authoring eight values requires separate evidence and should not
invent thresholds.

Useful acceptance cases include one target-center hit and controlled misses at
each horizontal/vertical boundary; a marked crossing with no score and a score
outside the marked zone; stale/non-Human touch; uncertain gap touch followed by
a clean crossing; contact and crossing in one sample with unresolved timestamp
order; gap crossing; just-before/at/after-deadline events; and retry proving
that the next attempt has no old touch, target, metrics, or event state. For
every future profile, repeat selection/persistence and compatibility checks
against its exact version. These cases are requirements, not tests run here.

## Source fingerprint receipt

SHA-256 and byte lengths measured from the frozen source snapshot inspected for
this report:

| Source | Bytes | SHA-256 |
|---|---:|---|
| `src/my_career_training/training/catalog.py` | 9,097 | `1c05fe5ed75296c5c75848f26e7c01a77160b16938c76c55e15536828f58fe73` |
| `src/my_career_training/training/engine.py` | 63,844 | `37028379a268d6f6e19d42b32a9e3c20778ed4f41d87bfbd3bc76955c61c602a` |
| `src/my_career_training/training/coaching.py` | 5,848 | `3b8336a54f4997479f1ce56f787377eb748683a117c8ba24a82e6e3c03b25d3b` |
| `src/my_career_training/adapter.py` | 12,018 | `98d1f4612967eda756b21857dfd198a3a12e4a211684067a248b9a829b74285c` |
| `src/my_career_training/game_worker.py` | 90,814 | `2e3982dfc352e4fafcd667898b3cb1f76538b61447c2b6e47adc6d9f862e89c2` |
| `src/my_career_training/bridge.py` | 139,135 | `ac502d1f19810baca479a534aa766a6afbea7ba57a405452835cc9dcff379ac2` |
| `src/my_career_training/training/recordings.py` | 22,459 | `8effb8f438b39c4abe4901d683dc6e5e0424baa7f696dc35143b282cc5aa96f1` |
| `src/my_career_training/training/scenario_setup.py` | 5,265 | `d2421bf8f7ac2508e9f3a65db21b2847a0e147b75cc62a6159a976999536a0fe` |
| `plugin/include/NativeCareerLayout.h` | 167,035 | `17d2ec0a82c79fad1949715ad62840bcace4177cbbe137da3aa675289109eb78` |
| `tests/test_training.py` | 17,251 | `0da5646aa0c2873287f86d6b2f5c0e0d51e1e9ac06aeb7b550e85fa429dddb9d` |
| `tests/test_training_ghost_practice.py` | 12,501 | `37e742abbeeebd1c102d04ccc1af9620d4dd3f7955c8d5cf97a07c97e27b50ef` |
