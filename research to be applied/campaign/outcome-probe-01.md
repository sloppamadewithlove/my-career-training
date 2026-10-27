# OUTCOME-PROBE-01 — defender-touch attribution experiment

Follow-up: a [reviewed isolated candidate](defender-attribution-candidate-01.md) now includes the defender in attribution and passes its recorded offline checks. The original reproduction below remains evidence for the archived baseline; it is not a claim that the candidate is deployed.

The isolated Power Shots engine still awards success when a newer defender
touch is supplied before the goal. A corresponding newer keeper touch prevents
success. This was reproduced with synthetic input on both the Active and
GoalScored phase paths; it is not a Rocket League gameplay reproduction.

## Experiment and result

A DeepSeek builder wrote a standalone diagnostic against a copy of the research
candidate. A separate DeepSeek reviewer requested stronger input evidence and
phase coverage, then approved the revised diagnostic by source inspection.
The coordinator executed the final script with `--self-test`: exit 0, six cases,
33 passing checks. The reviewer also inspected part of the recorded output;
it did not independently execute the script or rederive every output value.

All cases use `power-shots / low-side-pass / diamond`, with keeper index 0,
defender index 1 and human index 2. Each follows the public constructor/update
flow through settle, ready, observed launch, human touch, target and score edge.
No engine-owned state, method, metric or event list is overwritten.

| Goal-edge phase | Human-only control | Later keeper touch | Later defender touch |
| --- | --- | --- | --- |
| Active (3) | Success | Timeout; no success | Success |
| GoalScored (4) | Success | Interrupted; no success | Success |

The injected human touch is at approximately 1.275 game seconds and the
opponent touch at 1.325. The final JSON preserves the raw floating-point stamps
alongside the input role/index, engine `seen_touch`, attribution `latest_touch`,
goal-target time and score edge. In both defender cases, `seen_touch` contains
the newer defender stamp but the attribution set contains only the human.
The self-test verifies delivery and ordering of that defender input; it does
not require defender success or omission as desired behavior.

The [recorded output](../evidence/outcome-probe-01.json) contains the six cases
and source hashes. The [diagnostic source](../experiments/research_outcome_probe.py.txt)
is supplied as text for an isolated source checkout. Save it as
`tools/research_outcome_probe.py` beside the matching `src/` tree and run
`python -B tools/research_outcome_probe.py --self-test`. It uses the standard
library and the project's existing Python modules. Optional non-default
scenario/rank arguments remain exploratory; this receipt covers the default only.

Final diagnostic SHA-256:
`8e87a42cdb2738e3078bbd64e491995616db7ec2743bcc220d3af1370cc74e7e`.
The JSON also pins `engine.py`, `scenarios.py`, `cadence.py` and `adapter.py`.
Those selected hashes are not a full dependency/build manifest.

## Why this happens in the inspected source

`TrainingEngine._scenario_observe_touches()` observes every configured bot and
the human into `seen_touch` (`training/engine.py:447-460`). However, `_scenario()`
constructs the attribution list from the human and optional keeper only
(`:507-524`). Its later strict latest-human comparison therefore cannot compare
the defender stamp (`:555-563`). The source comment describes the human as the
latest attributed toucher of every actor, which is broader than the list built
by the implementation.

The result narrows the earlier [OUTCOMES-01](outcomes-01.md) source concern:
the defender input reaches the engine, but it does not enter this comparison.
It does not establish the frequency or reachability of such a situation in an
actual game, nor does it validate the current keeper-based grading policy.

## Limits and next implementation proof

The ball follows an authored linear path, not simulated physics. Contacts are
timestamp injections without car/ball proximity; cars remain at their supplied
poses. The touch detail retains the legacy `location` key while the current
adapter uses `position`; the engine accepts both for details and uses the time
for attribution. Production packet scheduling between phases 3 and 4 was not
observed. `chain_valid` concerns continuity/roster state and is not equivalent
to satisfying the full latest-human goal predicate.

If the intended rule is that the human must be the latest toucher among every
configured actor, the implementation should apply its baseline, finite-time,
not-in-the-future and strict ordering rules to every relevant actor. Preserve
gap invalidation and exact roster identity. Before accepting that change,
exercise a later defender, equal-time opponent tie, pre-reset/stale touch,
future stamp, human recontact, missing actor and both phase paths. Retain a
positive control. Then validate the selected rule with an owned game trace.
No production scoring fix or game acceptance is claimed by this experiment.
