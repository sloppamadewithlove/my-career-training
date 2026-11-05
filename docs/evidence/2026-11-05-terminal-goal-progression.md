# Power Shots terminal-score progression source repair

5 November 2026. Base: `2c08e740c1cbaa93a17df34e0f69145e6fbc4977`.
Status: source-tested; not packaged or live accepted.

## Diagnosis and live-evidence limit

The product contract says timeout waits for Up retry or Left/Right selection,
while an actual scored goal advances the challenge. Production packet handling
continued calling `_queue_goal_progression` after an attempt finished. That helper
compared the attempt's starting score with each new live packet, so a later team0
goal could advance an already timed-out attempt.

This defect was reproduced through `GameSession.process_packet` with a real
`TrainingEngine`: start from cumulative score 0–1, finish by timeout at 0–1,
acknowledge the saved attempt, then deliver a later 1–1 score packet. Before the
repair, the request changed from Low side pass to Bouncing side pass.

The repair instead uses `scenario_state.score_after`, the completed attempt's
observed terminal score. `_scenario` updates that field during the active/goal
packet before finishing; `TrainingEngine.update` returns without observing new
scores once finished. This preserves actual-goal advancement even when the
technique trace is interrupted, without letting a later goal reopen a timeout.
Existing save acknowledgement, phase, cancellation and manual-control precedence
remain in place.

The earlier live GC transition remains unexplained. The operator reported no
Left/Right input; the two Low side pass attempts and the later Bouncing side pass
attempt all stored equal starting/terminal scores within each attempt. Per-command
history and the score chronology between completion and transition were not
retained. The source reproducer does not prove what caused that live transition,
and this patch must not be described as its verified fix.

## Score persistence is a separate question

Current retry resets actor/scenario state rather than the cumulative native
scoreboard. `adapter.desired_state` writes car, ball and bot physics/boost with
`match_info=None`; the next engine Go captures the then-current score as a fresh
baseline. The current product contract requires actor/scenario reset but does not
explicitly require setting the scoreboard to zero. The observed retained 0–1 score
therefore does not establish a separate defect. This patch leaves that behavior
unchanged and makes no new product decision about scoreboard presentation.

## Player-action contract and checks

1. Preconditions: an owned Power Shots scenario has finished and its attempt
   has the engine's observed starting/terminal scores.
2. Input: a subsequent game packet, plus the existing durable attempt acknowledgement.
3. Outcome: a goal observed during the completed attempt may advance once;
   timeout with no such goal remains on its challenge despite a later score.
4. Persist: normal attempt saving and accepted challenge-selection persistence;
   no schema, score write or save path changes.
5. Failure/recovery: existing wait-for-save/active-play controls, manual retry,
   selection override and Return remain available through their existing gates.
6. Proof: four production-packet cases cover unchanged timeout, a late score after
   timeout, a successful Human goal and an unattributed actual team goal. The late
   case failed on the base while the other three passed. All pass with the repair,
   and verify that the completed engine's terminal scores remain frozen.

Python 3.12.13 / pytest 9.0.2; import root verified from this isolated checkout:

```text
python -m pytest -q tests/test_power_shot_scenarios.py tests/test_timeout_without_score_no_goal_progression.py tests/test_worker.py tests/test_training.py tests/test_training_cadence.py tests/test_scenario_setup.py
268 passed
python -m ruff check src/my_career_training/game_worker.py tests/test_power_shot_scenarios.py
All checks passed
```

No game input, loaded asset replacement, native/frozen build or live acceptance
was performed for this source repair. A future bounded live trace still needs
attempt identity, score packets and automatic/manual command acknowledgements
around timeout and transition to diagnose the original observation.
