# Power Shots defender attribution source check

5 November 2026. Base: `282db0d17e9f8c5ad304b0206ee375e9f54a2e16`.
Status: implemented and source-tested; no native build or live-game acceptance.

The Power Shots engine observed every scenario actor during preparation but
included only the Human and keeper in its active latest-contact comparison.
Grand Champion and Supersonic Legend also configure a defender. A defender's
tied or later contact could therefore be omitted and the goal credited as a
verified player shot.

The active comparison now includes every configured bot index. Existing
`human_touch` and `keeper_touch` events, pre-reset filtering and strict
latest-contact ordering remain. No new event name or interface is introduced.

## Player-action contract

1. Preconditions: an active Power Shots scenario with its configured actors and
   continuous attributed touch/score telemetry.
2. Input: the Human contacts the ball; an opponent may contact it before a goal.
3. Outcome: a tied or later defender contact prevents technique-success credit.
   An earlier defender contact, or a fresh later Human contact, still permits
   credit when the existing target-crossing and score checks also pass.
4. Persist: Existing attempt-summary and recording paths remain; attempt
   summaries now include valid defender observations in `latest_touch`.
5. Recovery: the existing interrupted-attempt feedback and manual retry route
   remain. A scored goal and technique credit remain separate observations.
6. Proof: eight synthetic scenarios across both two-opponent ranks cover older,
   tied and later defender contact plus a later Human recontact. Before the fix,
   tied/later cases incorrectly succeeded and the other cases omitted defender
   evidence. All eight pass with the fix.

## Checks

Python 3.12.13, pytest 9.0.2; import root explicitly selected from this checkout.

```text
python -m pytest -q tests/test_power_shot_scenarios.py tests/test_training.py tests/test_training_cadence.py tests/test_scenario_setup.py tests/test_scenario_floor_reset.py
232 passed
python -m ruff check src/my_career_training/training/engine.py tests/test_power_shot_scenarios.py
All checks passed
```

These checks do not establish defender usefulness, real shooting geometry,
physical controller operation, native timer behavior, or complete lesson
readiness. No game process, personal save, installed asset or binary was changed.
