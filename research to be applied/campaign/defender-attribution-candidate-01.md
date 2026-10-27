# DEFENDER-ATTRIBUTION-CANDIDATE-01

An isolated candidate fixes the reproduced Power Shots omission: a fresh defender touch now participates in the existing latest-human-touch comparison. The patch extends attribution to every configured opponent while retaining the human/keeper first-touch events, baseline/future-time exclusions and strict tie handling. A DeepSeek builder authored it, a separate DeepSeek reviewer accepted it with scope limits, and a Luna worker executed the reviewed tests. The shared product checkout and installed game were not patched.

## Recorded checks

The [candidate receipt](../evidence/defender-attribution-candidate-01.json) binds source hashes, arguments, environments, timestamps and output hashes. The candidate differs from the 55-file published Python archive in `training/engine.py` only; its source edit adds nine lines and removes three, including comments. It also supplies a new regression-test file.

| Invocation | Observed result | Meaning |
| --- | --- | --- |
| New focused tests | 15 passed | Seven phase-paired cases plus one Gold control, using full synthetic rosters |
| Four existing regression files | 298 passed | Selected Power Shots, training, cadence and adapter checks; may overlap earlier campaign runs |
| Original outcome probe | Six cases, 33 checks passed | Human controls succeed; later keeper and defender touches prevent success in both tested phase paths |
| Same new tests with original engine | 6 failed, 9 passed | Expected `KeyError: 1` at missing defender attribution in later-touch, tie and retouch cases; confirms the baseline omission |
| Reconstructed published source plus patch | 15 passed | Same focused suite after exact source reconstruction, not additional unique coverage |

The [observed probe JSON](../evidence/defender-attribution-probe-observed.json) records the post-patch results. On the Active path, later keeper/defender cases end in timeout; on the GoalScored path they interrupt. The baseline failures alone do not prove every negative outcome—the separately executed probe supplies that comparison with the [original observation](outcome-probe-01.md).

## Reconstruct and apply in an isolated checkout

First restore the archived source using the [existing reconstruction instructions](reproducibility-handoff-01.md). The original engine must match SHA-256 `37028379a268d6f6e19d42b32a9e3c20778ed4f41d87bfbd3bc76955c61c602a`. The [patch JSON](../experiments/defender-attribution.patch.json) stores the exact unified-diff bytes in its `utf8_text` field, with their byte count and SHA-256. Decode that string as UTF-8 to a private `defender-attribution.patch`, verify the recorded hash, then run from the reconstructed source root:

```powershell
git -c core.autocrlf=false apply --check <path-to-defender-attribution.patch>
git -c core.autocrlf=false apply <path-to-defender-attribution.patch>
python -B -m pytest tests/test_defender_attribution.py -q --tb=short
```

Replace the angle-bracket path placeholder with the actual quoted path. The recorded environment used pytest 9.0.2, `PYTHONDONTWRITEBYTECODE=1`, `PYTEST_ADDOPTS=-p no:cacheprovider` and `QT_QPA_PLATFORM=offscreen`. The coordinator applied the exact patch to the published archive and verified that engine/test bytes matched the reviewed candidate before the successful reconstruction run. Default Git line-ending conversion changed byte hashes on the first reconstruction; the explicit configuration above avoids that mismatch.

The [builder contract](../experiments/defender-attribution-builder-contract.md.txt) is retained as authored before test execution; its unexecuted status describes that earlier stage. This report and the receipts record the subsequent results.

## Integration limits

Only `low-side-pass` at Diamond and a Gold positive control are in the new focused suite. Packets, contacts and trajectories are synthetic; no game, physics simulation or full native build occurred. Passing checks do not establish 96 situation/tier game cases or certify the grading policy.

`latest_touch` now contains qualifying defender entries. The engine copies this state into summary evidence, and the observed JSON proves it serializes in this diagnostic. Older recordings, results and personal bests are not regraded or invalidated. Reconcile outcome-policy/version compatibility before production integration; the patch implements the existing stated latest-human rule rather than a new technique detector.

The shared `work/reviewed-training` worker source changed during packaging. This patch and its checks remain bound to the exact published archive, not to the later mutable checkout. Compare both source identity and companion lifecycle changes before applying it elsewhere.
