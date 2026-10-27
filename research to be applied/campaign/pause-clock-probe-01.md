# PAUSE-CLOCK-PROBE-01 — synthetic pause delivery observations

The reviewed standalone diagnostic ran against 55 unchanged copied Python source files. It exited 0 in 3.172 seconds, with valid JSON, no stderr, eleven fixture/precondition checks and two active-phase baseline controls passing. Source-origin, import, method-identity and phase-name checks also passed. No game, worker, Qt, network connection or physics simulation was started.

This is an observation experiment, not a production fix. Its successful exit validates the fixtures and controls; it does not endorse the observed pause behavior as the desired behavior.

## Observed results

Every lesson traversed the real public engine update path from settling through ready to active before the measured packets were delivered. Frames were explicitly synthetic, with a 120 Hz game clock, one-step frame numbering and authored stable poses. No private engine state was assigned or patched.

| Case | Observed result |
| --- | --- |
| Seven legacy lessons, advancing clocks with `MatchPhase.Paused` | All reached `finished` / `timeout`: Speed Flip 10 s, Flip Reset 12 s, Dribble & Flick 20 s, Shot Placement 15 s, Fast Aerial 12 s, Aerial Air Roll 25 s, Flight Recovery 25 s. No lesson reported success. |
| Dribble & Flick within that synthetic case | The stationary authored carry pose accumulated a `carry_sustained` event while the packet phase remained Paused. This is predicate behavior under synthetic input, not a physically performed carry. |
| Bronze Power Shots / Low side pass | The scenario activated, remained active over the baseline packets, then one Paused packet produced `interrupted`. The recorded duration remained 0.258333 s. Bronze's authored roster intentionally has no opponent bots. |
| Speed Flip, repeated timestamp followed by a delivery gap | The equal-time Paused packet left state and duration unchanged. A later Paused packet ten game seconds ahead caused timeout at 10.108333 s and recorded one packet gap. This models resumed delivery, not unpausing the game. |
| Synthetic private Watch recording | Advancing supplied clocks moved the cursor from 0 to 0.25 to 0.5 s. Explicit `pause()` held at 0.5; resume re-anchoring and an equal-clock packet also held. |
| Synthetic private Practice recording | Advancing clocks moved the cursor from 0 to 0.25 to 0.5 s. An equal-clock packet held at 0.5. The sample remained visible. |
| Active-phase controls | Speed Flip timed out normally; Bronze Power Shots stayed active/unfinished over 30 active packets. |

The ghost APIs receive clocks, not a match-phase argument. Their case is labelled **simulated paused delivery**: it demonstrates progression with advancing clocks and the explicit Watch pause control. The recording is synthetic and private, with `reference_eligible=false`; its ordinary personal-attempt UI label does not make it a real capture or teaching reference.

## Implication for implementation

The [pause source audit](pause-clock-01.md) distinguishes opening MCT's overlay from pausing the game. The pinned public RLBot schema documents elapsed time advancing during pause, but this campaign has not measured installed packet delivery during an owned pause. If advancing Paused packets reach these legacy engines, their timeout and some skill predicates keep evaluating. The Power Shots engine takes a different path and interrupts. Watch and Practice need an explicit caller policy if their clocks should stop with a real pause.

Define the intended player behavior before changing these paths: suspend the same attempt, interrupt and require a clean reset, or another explicitly specified policy. Preserve attempt identity, setup confirmation, ghost alignment and save acknowledgement consistently. A frozen timestamp and a period of absent packets followed by an advanced timestamp are distinct cases.

## Reproduction and evidence

The diagnostic imports from its adjacent repository's `src`, verifies module origins and uses only the public engine/ghost APIs for observations. Run the published text copy as `tools/research_pause_clock_probe.py` beside the exact source snapshot identified by the [source manifest](../evidence/pause-clock-probe-source-manifest.json), with Python 3.12 and `-B`. The publication branch itself is not that complete product-source snapshot.

- [Reviewed diagnostic source](../experiments/research_pause_clock_probe.py.txt): publication SHA-256 `22b0b0eb98e3d565dba376ab3d6e1fe3ef600c161ad93ac770ea5b6a8fd19fa2`. Publication normalizes trailing whitespace only; the parsed AST equals the reviewed/executed source (`22b0b0eb98e3d565dba376ab3d6e1fe3ef600c161ad93ac770ea5b6a8fd19fa2`).
- [Observed JSON](../evidence/pause-clock-probe-observed.json): 22,238 bytes, SHA-256 `250e563c94ec832744153dd84152b22f20e438fd2889caeaf3cc819cf28085ef`.
- [Execution receipt](../evidence/pause-clock-probe-01.json) records the reviewed file, unchanged source, interpreter, process outcome and prior failed fixture run.

Separate DeepSeek workers built and reviewed the diagnostic. The first execution returned exit 1 because two control call sites omitted a required helper argument, despite source-review acceptance. The builder corrected those two call sites, a separate delta review accepted the fix, and the coordinator reran the complete diagnostic successfully. No production source changed. This failed first run is retained as a fixture defect, not a product failure or passing experiment.

## Limits

The poses deliberately stay fixed after activation to isolate clock/phase handling; they are not a physics simulation or proof of a reachable maneuver. The experiment does not measure game packet scheduling, actual pause/resume input, renderer output, ball disappearance, mod activation, controller hardware or persistence/transport acknowledgements. It does not implement the user-requested pause policy. Later game observations must identify their own source/runtime artifact and actual packet delivery.
