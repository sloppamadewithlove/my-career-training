# PAUSE-POLICY-01 — implementation choices for pause, clocks and ghosts

Research contract, not an implemented or approved behavior change. A DeepSeek draft received independent DeepSeek source review; this coordinator synthesis removes misleading remedies and retains the supported coupling. No production source changed and no new test or game run was performed. See [pause source audit](pause-clock-01.md) and [synthetic pause diagnostic](pause-clock-probe-01.md) for the underlying observations.

## Current behavior that an implementation must preserve or deliberately change

| Area | Source-backed behavior | Consequence |
|---|---|---|
| Real pause versus overlay | The default ImGui menu does not pause the game. Worker frames carry the game phase. | Menu visibility cannot substitute for a game pause signal. |
| Power Shots | `engine.py:587–616` handles non-Active phases before elapsed-time accumulation. An active attempt receiving Paused (6) interrupts. Phase 4 processes terminal contact/target/score evidence, returns a completed result if that finishes the attempt, and otherwise interrupts. | Paused scenario time does **not** continue accumulating: that path already ended. A suspend option must alter the Paused branch without removing goal-terminal handling. |
| Seven legacy lessons | No phase-dependent control-flow guard; equal-clock return occurs at `engine.py:621–622`. | Advancing Paused clocks can reach timeout and accumulate carry, as the diagnostic showed. A new phase guard placed after the equal-clock return would miss equal-clock pause edges. |
| Cadence | Worker computes `cadence_details` and combines the derived gap with any supplied `packet_gap` (`game_worker.py:1234,1260–1270`). Engine uses supplied details (`engine.py:300–304`). | Changing only the engine's previous-frame pointer cannot implement a consistent pause boundary. |
| Carry/events | Carry adds `dt` when geometry is inside, `previous_carry` is true and no gap is set (`engine.py:1127–1136`). Other event state includes `was_airborne`, `contact_pending` and `last_touch_time`. | Suppressing a gap without excluding paused duration can falsely earn carry time. Replacing only `last_frame` does not reset all event baselines. |
| Ghost Watch/Lead | `pause()` and `resume()` clear clock anchors; Lead also reanchors its offset (`coach.py:207–219,254–288`). Resume requires a recording. | Existing explicit pause can hold playback. Automatic resume must preserve a player's manual pause and avoid resuming an absent recording. |
| Ghost Practice | `update()` uses the delta from retained `_last_clock`; it has no pause method (`coach.py:438–460,488–505`). | Skipping calls merely defers the elapsed delta to the next update, subject to playback bounds/looping. Toggling off/on restarts the demonstration. Neither is a neutral hold. |
| Terminal persistence/retry | Worker publishes an attempt once by ID; retry requires recording samples and acknowledgement. It reads `engine.preferences["auto_reset"]`, not the completed event's optional `auto_reset` field (`game_worker.py:973–981,1318–1323,1374–1392`). | An interruption can still become retryable. Do not equate the terminal event shape with the retry policy. |
| Retry deadline | One-second monotonic deadline; `_check_auto_reset` defers while telemetry recovery is pending, then rechecks normal retry conditions (`game_worker.py:888–903`). | Freezing attempt time alone does not freeze retry scheduling. Packet silence only defers this path once the recovery gate is actually set. |

`_interrupt` emits a completed summary without an `auto_reset` key (`engine.py:312–315`); the backwards-clock branch also returns a completed summary directly (`:623–626`). Worker deduplication and acknowledgement remain necessary whichever terminal path is used.

## Keep timestamps and elapsed durations separate

The packet clock, game touch timestamps, launch baseline and score-edge ordering are in the raw game-time domain. The scenario chain compares these at `engine.py:512–576`. Never subtract the current pause offset from an older touch: that event may predate the pause. Retaining raw ordering avoids this incorrect conversion.

Recorder sample time is already relative to the first raw frame, not an absolute wall clock (`recordings.py:231–238`). Engine event times are relative to `started_at` (`engine.py:282–296`). `summary().duration` is already different between families: accumulated `active_elapsed` for scenarios and raw elapsed time for legacy lessons (`engine.py:1268–1274`). Recording export receives that summary duration (`:1344–1346`), and personal-best selection compares duration (`recordings.py:175–201`).

A suspend design can preserve observation timestamps while introducing a separate active-duration accumulator. It must specify which duration drives timeout, HUD, Lead alignment, carry metrics and best-attempt comparison. Excluding pause time from one consumer while leaving the others unchanged would produce conflicting feedback.

The current validator accepts extra keys but requires schema 1, `time_base == "game_seconds"`, increasing sample times and the byte/sample bounds (`recordings.py:35–120`). That is syntactic tolerance, not semantic compatibility. Old readers will not automatically understand pause edges or avoid interpolating across them. Any implementation must review playback/interpolation and compatibility rules, and version the lesson/policy identity when outcome or best-time meaning changes—even if raw sample timestamps remain unchanged.

## Two product options, neither chosen here

**A. Suspend the same attempt.** Retain the attempt ID, freeze active-duration consumers, record a suspension boundary, and resume only under a declared validation policy. For Power Shots this replaces the current Paused interruption behavior; for legacy lessons it adds a phase-aware path. Keep finished/interrupted states terminal. Keep other phases, especially goal replay/terminal score processing, distinct from Paused.

This option requires coordinated worker and engine changes:

1. Observe phase edges before equal-clock suppression. Keep an explicit pre-suspension snapshot rather than assuming the worker's continually updated `last_frame` still represents it.
2. Distinguish a known suspension from an interval with no pause evidence and from explicit transport-loss evidence. Never erase a supplied transport gap. A known pause explains elapsed time; it does not prove continuous input or contact during that interval.
3. Exclude suspended duration from carry and other active-time accumulation. Rebaseline input/contact/airborne state so resume cannot invent a dodge, landing, touch or target crossing. Whether a previously earned carry streak survives is a separate mechanic-policy choice.
4. Define preparation behavior. Existing scenario settling/ready handling reanchors or clears preparation state during non-Active phases (`engine.py:592–597`). Reuse the intended behavior, not an arbitrary subtraction from timestamps.
5. Define resume evidence: unchanged versus changed car/ball/score/touch state, backwards clock, missing phase edge and unsupported interval. The ready-state predictor at `engine.py:692–725` extrapolates an authored reset target and has a two-second bound; it is not a ready-made comparison against the pre-pause world.
6. Hold Watch/Lead only when this policy owns the hold. Practice needs an explicit reanchor capability or a separately derived playback clock; skipping `update()` is insufficient.
7. Do not emit `completed` merely to represent suspension. Decide how already-terminal, acknowledged attempts and pending auto-retry behave while the game is paused.

The normal packet-interval threshold is 0.05 seconds; it is not a supported-pause-duration limit. If suspension needs a separate bound, that must be specified explicitly. A short pause with an observed phase edge remains identifiable as a pause; a long unexplained packet gap does not become a pause by assumption.

**B. Interrupt and retry cleanly.** Reuse the current Power Shots outcome distinction (`interrupted`, not a successful or failed mechanic) for active legacy attempts. This avoids preserving a partially observed attempt across pause, but costs the player that attempt. Preparation, ghost behavior and pending retry still need explicit policy. Current auto-retry can be armed by an interrupted attempt with samples, so “interrupt” does not inherently mean “wait for a manual retry” or “wait until unpaused.”

Both options must keep an overlay opened during continuing physics distinct from a real game pause. Choosing a new policy for the overlay is separate from matching the game's pause behavior.

## Acceptance to require after the product choice

Current-behavior baselines and changed-policy assertions must be separate. The existing synthetic diagnostic establishes current behavior; it is not an acceptance test for a future suspend implementation.

- Exercise every lesson family with advancing paused clocks, equal clocks, backwards clocks, and absent packets. Include a supplied transport gap overlapping a known pause; preserve both facts.
- Under A, retain the attempt ID through an accepted suspension and exclude its duration from the chosen active-time consumers. Under B, publish exactly one interrupted attempt and apply the selected retry policy.
- Resume with unchanged state, changed car/ball pose, new score/touch evidence and no observed pause edge. Do not infer intervening actions from endpoint poses.
- Use a carry pose and airborne/contact state across the boundary. No paused duration may earn carry, and no unobserved interval may generate a landing, touch or technique event.
- Validate worker-produced cadence fields as well as engine behavior. A standalone engine fixture cannot prove the worker-to-engine contract.
- Check Watch, Lead and Practice independently, including manual ghost pause, absent recording, loop/end bounds and a long resume delta. Confirm that a hold does not restart or jump the demonstration.
- Check save acknowledgement, telemetry recovery and retry before/during/after pause. Require one terminal save and the chosen retry timing, including a cleanup/Return during suspension.
- Check HUD time, recorded duration, sample timestamps, interpolation and personal-best compatibility together. Acceptance must use the chosen policy/version rather than silently reclassifying historical attempts.

Future owned game acceptance must record the actual deployed artifacts, phase/clock delivery, visible timer and ghost cursor on both overlay and real-pause routes. This campaign has not measured the installed game's pause delivery and does not certify either proposed policy.

## Source identity

The following hashes bind the frozen source used by the diagnostic and this research. They are not deployed-binary or live-session identities.

| Frozen source | Bytes | SHA-256 |
|---|---:|---|
| src/my_career_training/training/engine.py | 63844 | 37028379a268d6f6e19d42b32a9e3c20778ed4f41d87bfbd3bc76955c61c602a |
| src/my_career_training/training/cadence.py | 5228 | fdbcda80e4fadb135713314e0fb65e2bcf2a3cf848f9261413fc2803555ee240 |
| src/my_career_training/training/coach.py | 25430 | 0807fda8daf33ae67a9d1f31ccf93ecb10acccd21bb7efa3d9fb8a7fec905325 |
| src/my_career_training/training/recordings.py | 22459 | 8effb8f438b39c4abe4901d683dc6e5e0424baa7f696dc35143b282cc5aa96f1 |
| src/my_career_training/game_worker.py | 90814 | 2e3982dfc352e4fafcd667898b3cb1f76538b61447c2b6e47adc6d9f862e89c2 |
| src/my_career_training/bridge.py | 139135 | ac502d1f19810baca479a534aa766a6afbea7ba57a405452835cc9dcff379ac2 |
