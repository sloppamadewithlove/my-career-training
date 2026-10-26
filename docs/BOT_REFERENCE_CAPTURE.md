# Bot teaching-reference capture

Checked 26 October 2026. No bot reference recording is bundled. The foundation in
`src/my_career_training/training/bot_reference.py` defines a candidate controller,
an evidence evaluator and a benchmark selector. It contains no SDK, network or
game calls, no learned weights and no third-party input arrays.

## What exists

`SpeedFlipTrialController(profile='cancel'|'baseline', parameters=None)` is an
original, parameterised timing candidate. `step(elapsed_seconds, frame=None)`
takes **game seconds since the engine's Go event** and returns all eight logical
actions. There is no wall-clock or step-count assumption. Invalid, non-finite or
backward time returns neutral actions and marks the attempt interrupted. Declared
phases must finish inside a 3 s bound; after that the candidate holds positive
throttle and boost until the 10 s timeout, unless the caller calls `finish()`.
The controller never chooses a player index and never sends inputs.

The schedule is: accelerate/boost, short steering compensation, first jump, a
genuine jump release gap (default 0.025 s, never below one 120 Hz packet), the
diagonal dodge (negative pitch, configured yaw side), immediate opposing pitch,
grounded recovery, then boost through the finish. The release gap keeps the two
jump presses as distinct True–False–True edges at 120 Hz. Profile `baseline`
keeps the same schedule and setup but emits no opposing pitch.

`controller_plan()` exists both as a method and as a module-level helper
`controller_plan(profile='cancel', parameters=None)` for the parallel capture
worker. It returns JSON-safe identity, revision, default timing, phase bounds and
the explicit statement that this is a candidate, not a proven clean speed flip.
Capture workers should store that plan with the recording for provenance.

## Claim limits

- The candidate is **not** claimed to perform a clean speed flip. Its timing is a
  starting point for real capture, not a validated demonstration.
- `evaluate_bot_trial()` reports **provisional** gates only. It never certifies an
  expert attempt or a world record, and it never promotes a teaching bundle.
- Engine success alone is insufficient. A passing candidate needs the matching
  speed-flip lesson/version/variant, ordered `first_jump`, `diagonal_dodge`,
  `opposing_pitch`, `target_crossed` and `landed` events, zero packet gaps, no
  truncation, normal game speed, finite matching metrics, and independent
  corroboration from the recorded pose, velocity and action samples.
- An opposing pitch before the line is not proof by itself. The dodge-to-cancel
  delay is measured against the declared candidate window (0.05 s) and,
  separately, against the declared delay plus one 120 Hz packet plus a float
  epsilon. The recorded actions must corroborate the reported cancel time at
  packet precision; the looser event tolerance is not a loophole for a fake
  cancel metric.
- The crossing must be a positive-Y crossing of the finish plane within
  |X| ≤ 500 and Z ≤ 300, with a positive recorded crossing time and speed.
- Landing requires roof-up ≥ 0.7, forward alignment ≥ 0.7, positive speed and
  angular speed ≤ 2 rad/s. The angular-speed gate is **PROVISIONAL**. Landing
  angular speed and actual wheel contact must come from the recorded samples
  (the optional `angular_velocity` and `wheel_contact` sample fields). A summary
  value alone is not physical evidence: if the samples lack it, the trial is not
  eligible for teaching review.
- Runtime metadata must be known: game version, framework version, car hitbox,
  map, exact mutators and exact starting state. Empty objects, empty strings and
  `unknown`/`unavailable` values are rejected, and normal game speed must be
  declared explicitly in the starting state and in every sample rather than
  defaulted. The source must be `kind='actual_execution'` with `actor='bot'`;
  `local_player` and imported sources are rejected. The evaluator never mutates a
  recording, never changes permission and never fabricates execution metadata.
  Runtime origin is supplied by the real capture worker only.
- A no-cancel baseline cannot succeed in the real engine, because engine success
  requires `opposing_pitch`. `evaluate_bot_baseline()` therefore accepts a
  genuine `timeout` outcome only when the recorded samples independently show a
  complete crossing and landing with no missing or gapped records. It never
  fabricates a successful baseline outcome. A baseline is also rejected if an
  actual cancel appears in the summary events or in the recorded samples.
- `select_bot_benchmark()` requires at least three passing candidate repetitions
  and at least three complete same-setup no-cancel baselines, compares median
  `crossing_seconds`, and returns `status='eligible_for_review'` at most.
  Distribution permission is separate and defaults to false.
- The setup fingerprint covers game version, framework version, hitbox, map,
  mutators, starting state and lesson/version/variant. It deliberately excludes
  the actor, the control-script profile and per-run hashes so a baseline and a
  candidate of the same setup compare directly.

## Development capture path

The source-only `reference_capture` request is unavailable in normal menus and
packaged builds. It requires an owned offline Steam session, the canonical
speed-flip variation, an exact process-local copied-profile binding and an
operator-written allow marker. One known bot precedes the Human in the roster.
Only that mapped bot receives controller inputs or lesson resets; ordinary
sessions still observe/reset the Human. Loss of mapping, marker or Human
clearance stops capture and tears down its owned runtime. Playback commands
are refused during capture.

The worker records actual packet physics and `last_input`, including observed
wheel contact and angular velocity. Source metadata identifies a bot execution;
it never substitutes intended controller output for observations. Runtime
configuration evidence contains matching requested and core-acknowledged
snapshots for the map, mode, freeplay and seven relevant mutators. This proves
core acceptance of the configuration, not direct measurement of each physics
parameter. Every recorded sample must independently report normal game speed.

Completed candidates and hash receipts go only to the copied profile's
`reference-candidates` directory, with a distinct attempt UUID on retries.
They remain `gate: not-evaluated` and `permission.distribute: false`. No
automatic import, benchmark promotion or bundled reference is implemented.
Tests use synthetic data and do not establish a working in-game speed flip.

## Next capture workflow

1. Run the candidate in the real offline game through the existing isolated
   worker, with the engine's own settle/ready/go sequence.
2. Record with `TrainingEngine.recording()` and set `metadata.source` to
   `{"kind": "actual_execution", "actor": "bot", "origin": ...}` from the real
   worker, plus known game/framework/hitbox/map/mutators/starting-state values.
   Store `controller_plan()` alongside the recording.
3. Capture at least three candidate repetitions and at least three no-cancel
   baseline repetitions on the identical setup.
4. Run `evaluate_bot_trial()` on each candidate and `evaluate_bot_baseline()` on
   each control, then `select_bot_benchmark()`.
5. Only after main's real-game review may a built-in reference be pinned by
   manifest hash. Until then nothing is installed, shared or labelled validated.

Tests for this module use synthetic fixtures only; no fixture is shipped as a
reference recording.
