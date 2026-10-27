# TELEMETRY-01 — clocks, cadence, recovery and HUD timer

SCOPE READ
Full: training/cadence.py. engine.py 1–420, 420–540, 539–620, 600–720, 700–1000, 1000–1200, 1199–1318, 1318–1346 (now complete). game_worker.py 600–720, 800–920, 950–1010, 1180–1320, 1320–1560, 1556–1594. adapter.py 1–220. coach.py 230–350. plugin/include/TrainingLessonInput.h 320–440. docs/INTEGRATION_CONTRACT.md 80–140.
NOT read: game_worker.py 1–600, 720–800, 920–950, 1010–1180, 1594–1706; bridge.py bodies; scenarios.py, scenario_setup.py, recordings.py bodies; the ghost-practice module behind `self.practice`. Grep-only for tests and plugin/src. This is not approval of unread paths.

CLOCK TABLE (source refs, semantics from consuming code, not field names)
| Clock | Origin | Consumers | Deadline role |
|---|---|---|---|
| Game seconds | adapter.py:161 `match_info.seconds_elapsed` | every engine dt/deadline; coach.py:254; practice update game_worker.py:1344 | settle 5.0 s (engine.py:19,674), ready 2.0 s (723,747), lesson timeout (818–820), `active_elapsed` (796) |
| Monotonic host | game_worker.py:1227 | controls 1/120 (1271–1272), render 1/30 (1324–1326), telemetry 1/30 (1345), auto-reset +1.0 (981), recovery +5.0 (843,858) | wall-time bounds only |
| Frame counter | adapter.py:161 `frame_num` | cadence.py:102–111; capture diagnostics 1358 | none |
| Render cadence | host 1/30 | HUD text | display sampling only; live duration is game seconds (1441), finished duration is `summary["duration"]` (1439) |

Consequence: a 30 Hz render can show a jump larger than one physics step; that is display sampling, not a telemetry gap. SDK names (`seconds_elapsed`, `game_speed`, `frame_num`) are carried through, not interpreted; no timer semantics are claimed from them.

CADENCE CONTRACT (cadence.py, single source of truth)
Order: explicit `packet_gap` (58) → missing/non-finite clock (64–73) → `dt<=0` (76–79) → `dt>0.05` interval_exceeded (80–82) → invalid frame number (84–87) → both absent = legacy clock-only, strict rejects (88–97) → partial = gap (98–101) → `observed=(new−old)%2**32`, limit 1 strict / 2 normal (102–107) → `|dt − observed/120| > 0.002` physics_step_mismatch (108–111) → `coarse` (112–113). `dt` is set at 75, so gap results still carry a numeric dt. `game_speed` is not an input.

CORRECTED TIMELINES (derived from source, not measurements)
A. 60 Hz observation, Active: t=10.0000/fn=1200 → t=10.0167/fn=1202. dt=0.01667, observed=2, expected=0.016667, diff≈0 → `coarse_continuous`, gap False, `carry_streak += 0.01667` (1128). Same game seconds as 120 Hz with half the packets.
B. One missing 120 Hz packet: t=20.0000/fn=2400 → t=20.00833/fn=2401 continuous → t=20.0250/fn=2403. dt=0.01667, observed=2, expected=0.016667, diff≈0 → `coarse_continuous`. Ordinary training accepts and continues; strict capture rejects (`step_count_exceeded`, limit 1). No gap, no `carry_streak` reset, no `chain_valid` invalidation.
C. True >2-step gap, clock consistent: t=20.0000/fn=2400 → t=20.0250/fn=2403. dt=0.025, observed=3, expected=0.025, diff≈0, but observed 3 > 2 → `step_count_exceeded`. Effects in engine order: `packet_gaps += 1`, `last_gap_time = 20.025`, `carry_streak = 0.0` (801–804) before `_targets` (813); gate, plane, carry accumulation and goal-crossing predicates suppressed (1091, 1102, 1127, 1139); the recovery corridor has different guards (see OUTCOMES-01); scenario `chain_valid = False` permanently (495–498). Same shape at 60 Hz observation with one dropped packet: dt=0.0333, observed=4 → `step_count_exceeded`.
D. Interval-only gap: t=30.0000/fn=3600 → t=30.0600/fn=3601. dt=0.06 > 0.05 → `interval_exceeded` before any frame-number check.
E. Scenario pause: t=40.0 Active → t=40.5 Paused(6). engine.py:587–618: `chain_valid=False`, `_interrupt`, `completed` event, `publish_attempt` (1322–1323). Retry refused until acknowledged (633–634).
F. Recovery: host T0 invalid at Active → interrupted, deadline T0+5.0; T0+3.0 valid at Active → `fresh=True` but `attempt_sent and not attempt_acked` keeps waiting (860–862); ack (973–981) then next valid packet clears recovery and emits `telemetry_recovered` without reset (870–879). No valid packet by T0+5.0 → RuntimeError naming phase and fields (820–831), raised inside `process_packet` (1562) or the empty-queue branch (1559), caught by `except Exception` (1583–1586) → `error` + `session state=error` + teardown.

GAP ORDERING — main's claim confirmed
engine.py:793–804 zeroes `carry_streak` on gap strictly before `_targets` (813); the carry branch requires `not gap` (1127), so a gap packet cannot add to the streak and `carry_streak >= target["seconds"]` (1135) needs post-gap continuous time. No false carry-gap bug; not repeated. Consequence recorded: carry time is under-counted across a gap (conservative).

PAUSE / ADVANCE / DIE
- Scenario attempts: any `phase != 3` is not attempt time (587–618). settling → settle counters cleared (592–595); ready → `reset_requested_at = now` (596–597) so the 2 s confirmation budget restarts only after Active resumes; active + phase 4 → one terminal `_contacts/_targets/_scenario` pass with cadence (600–609); active + any other phase → `chain_valid=False` + `_interrupt` (613–616). `active_elapsed` (796) uses the raw game-clock delta and is skipped entirely on non-Active packets, so pause time neither spends the shot timer nor the timeout (818–820). After a phase transition `last_frame=None` (617), so the first Active packet takes the `previous is None` branch (787–792) and adds nothing.
- Legacy lessons (`scenario is None`) skip that block. A frozen game clock hits `now == last_frame["time"]` → silent `[]` (621–622) with no gap counted; a resumed packet whose game-clock delta exceeds 0.05 seconds yields an `interval_exceeded` gap, resets `carry_streak`, and marks affected events uncertain. A frozen clock resuming with a normal delta need not take that path. Whether `seconds_elapsed` freezes during Paused/Replay is a runtime UNKNOWN.
- Backwards clock → interrupted "game clock restarted" (623–626).
- Divergence worth recording (not a severity call): for a duplicate-clock packet the worker already sets `packet_gap=True` (1267) while the engine returns `[]` at 621–622 without counting it and without recording it.

GAME SPEED — what the source does and does not say
`game_speed` is carried (adapter.py:163), recorded (recordings.py:249–250), and required to be exactly 1.0 for reference material (bot_reference.py:876–885, recordings.py:190–191). cadence.py hard-codes `PHYSICS_STEP_SECONDS = 1/120` (23) and ignores speed; engine.py never checks it. Training mutators do not set game speed (adapter.py:107–109) and catalog starting state is 1.0 (catalog.py:49). Whether a real speed change alters the `seconds_elapsed`↔`frame_num` relation is UNKNOWN here; the classifier alone cannot detect it, and a synthetic speed change with unchanged dt/frame is accepted. No claim that changed-speed packets are gaps.

TELEMETRY RECOVERY — six-part acceptance (game_worker.py:833–886, 1240–1254, 1556–1594)
(a) First invalid packet: `telemetry_recovery_pending=True`, `engine.interrupt_unavailable_telemetry(fields)` (engine.py:371–388) marks the attempt interrupted with no credit; event carries `packet_phase` (838–840).
(b) Deadline armed only when `phase == Active`: `time.monotonic() + 5.0` (841–843; constant at 26). Host wall time, not game seconds.
(c) Further invalid packets refresh fields/phase, neutralize scenario bots, re-check the deadline (844–847).
(d) Resolution needs a packet passing `_validate_frame` AND `_reset_after_training_telemetry` True; a non-Active phase returns True at 855–856 without arming, so fresh telemetry outside Active does not resolve.
(e) A published-but-unacknowledged attempt blocks completion (860–862); the timeout message distinguishes "fresh telemetry returned but save unacked" (815–819) from "remained unavailable" (820–826).
(f) On success: pending/fields/phase/fresh cleared, `last_frame=None` (864–869); if `attempt_sent`, emit `telemetry_recovered` preserving the result and do not reset (870–879); otherwise `self.reset()` (880–886). The proving packet is consumed and never reaches `engine.update` (1251–1254).
Outside-Active distinction: if the deadline was ALREADY armed during Active, it survives a later pause and is enforced both on the next packet (847) and by the loop's empty-queue check (1559), which runs even when no packets arrive. If it was NEVER armed (invalid telemetry first seen while non-Active), `_check_telemetry_recovery_timeout` (828–831) is a no-op and the loop check is also a no-op, so the wait is bounded only by the 120 s first-packet timeout (1550), which no longer applies after `first_packet`. Whether that pause-wait is intentional (waiting for play to resume) is not established by source; recorded as an open question, not a defect.

BALL DISAPPEARANCE vs BALL-OUT
`ball_out` (engine.py:530–532) is a coordinate condition: |x|>4096, |y|>5120, or z>2044, feeding feedback at 1248–1249. It is not disappearance detection. A genuinely absent ball arrives as `frame["ball"] = {}` (adapter.py:164) and fails `_validate_frame` (engine.py:336–338) → `InvalidTrainingTelemetry` → the recovery path above. A missing configured bot sets `chain_valid=False` (489–493).

HUD TIMER FORMULA (engine.py:1318–1346, now read)
`time_limit_seconds = scenario["timeout"]` (1331); `time_remaining_seconds = round(max(0.0, timeout − active_elapsed), 3)` (1332–1333); `phase` mapped from engine state (1323–1325); `countdown` = SETTLE/READY/GO by phase (1335); `match_phase` (1336). These fields exist only when `self.scenario is not None` (1321), so the native card timer is scenario-only; legacy lessons publish no limit/remaining. `active_elapsed` accumulates raw game-clock deltas (796), so a gap still spends timer while a pause does not. Plugin side: TrainingLessonInput.h:383–389 requires `limit > 0 && remaining >= 0`, clamps to [0, limit]; 413–418 computes elapsed as `limit − remaining`; 390–395 drops active-phase `countdown="GO"` so the live timer wins. The native card is the RLBot lesson clock, not the stock training timer: MyCareerTraining.cpp:388 disclaims shot-clock semantics for `server.GetGameTimeRemaining()`, NativeMovieHost.cpp:817–828 calls its value the post-match state timer, and training launches with `match_length=Unlimited` (adapter.py:107).

GHOST / PRACTICE — only paths actually read
game_worker.py:660–666 re-anchors practice to the reset pose on retry; 992–997 toggles practice with the `ghost` preference; 1343–1344 feeds `frame["time"]` and the last observed pose. coach.py:259–261 pauses on a backwards game clock (`clock_restarted`); 263–270 and 276–282 re-anchor lead mode when the attempt clock goes backwards; 285–286 advances by `(now − last_clock) * speed`. Gaps are written into the trace (`frame["packet_gap"]`, 799/805), so the trace retains gap evidence; playback consumers must still honor it, and storage alone is not proof they do. I did not read the practice module, so I make no claim about its internal interruption handling beyond these call sites.

INTEGRATION HOOKS
- HUD timer: `coaching.time_limit_seconds/time_remaining_seconds/phase/countdown` (engine.py:1326–1341) → TrainingLessonInput.h:383–419; `native_hud` gating game_worker.py:1417–1457; fallback text from `started_at`/`finished`/`summary["duration"]` (1434–1442).
- Setup: `engine.reset()` returns `settle_state`; worker sends `desired_state` (635–643); `set_state` event (engine.py:671) applied at 1307–1317; scenario controllers reset (644–647); practice re-anchors (660–666). Scenario commands refused while finished, published, or in recovery (684–687), acknowledged with id + accepted (969–972); shuffle changes future navigation only (714–719).
- Ball-out/telemetry: engine.py:530–532 + 1248–1249; recovery events 874–885.

UNKNOWNS
- Whether `seconds_elapsed` freezes during Paused/Replay (drives the legacy-lesson pause behaviour).
- Whether a real game-speed change alters the `seconds_elapsed`↔`frame_num` relation.
- Whether the never-armed non-Active recovery wait is intentional.
- game_worker.py 1–600 / 720–800 / 920–950 / 1010–1180 / 1594–1706 unread (setup, capture wiring, practice toggles, scenario persistence); bridge.py acknowledgement persistence grep-only; practice module unread.
- No runtime behaviour, no test execution, no game/network/credential access.

These are source contracts and explicitly listed unknowns. They do not establish native gameplay timing or acceptance of unread paths.

## Coordinator executable cross-check

Four calls to the existing classify_cadence function were executed with synthetic frames (no game or product edits). At a base time of 20 seconds/frame 2400: +2/120 seconds and +2 frames returned coarse_continuous in ordinary mode, but step_count_exceeded in strict reference mode; +3/120 and +3 returned step_count_exceeded in ordinary mode; +1/120 and +1 with only game_speed changed to 0.5 returned continuous. This checks the classifier and arithmetic only, not real changed-speed packet behavior.
