# Native pause focus checkpoint — 6 November 2026

Checkpoint target was 04:15:49 UTC; this catch-up started at 04:16:00 UTC, eleven
seconds later. No other review point elapsed since the prior checkpoint. The next
active-chat target is 05:01:00 UTC. This is one checkpoint record; no persistent
timer or unattended review is claimed. Documentation base:
`bc4fed1f23891b67444835dece548e5e59b2c725`.

## Exact candidate and limits

Candidate `bd9336d869363c51375bb9c35f0ae351aea74bb0` compiled with 1,659 passed
and 15 skipped; 38 plugin CTests, 13 launcher CTests, the Return fixture and
frozen smoke passed. The pause ABC hash matched between staging and the frozen
candidate. These checks establish candidate consistency and smoke behavior, not
live native pause acceptance.

The live handoff reached stock Play. The game then lost foreground. The helper
refused the next input, so no click was dispatched. The game remains open and the
test is suspended pending owner foreground. No live native pause result was
observed. Do not count the refused input as an attempted click or infer a pause
failure from it.

The owner reaffirmed the continue direction and model requests and asked for
honest timer reporting. Earlier `a59c45f` stock menu/shot observations and the
game-profile save mutation remain as recorded in the
[native-training catch-up receipt](2026-11-06-native-training-catch-up.md); they
do not establish this candidate's native pause behavior. The prior
`0:10` → `0:07` → `0:10` sequence still suggests expiry only. This checkpoint
produced no new timer or reset evidence.

## Applied practice

- On foreground loss or helper refusal, stop immediately. Resume only after the
  owner restores the intended game foreground and a fresh process/foreground
  check passes; never retry the refused click or use stale focus state.
- Reuse the exact candidate's compiled, CTest, Return-fixture, smoke and
  stage/frozen hash results while its source, dependencies and staged assets are
  unchanged. Repeat build/preflight work only after an input changes or a
  specific failed check requires it.
- Keep source, frozen smoke and live pause claims separate. The next live proof
  is the stock pause route on this exact candidate after focus is safely restored.

No game input, build or source edit was performed for this documentation
checkpoint. No personal paths, account identifiers, save contents, raw logs or
game assets are included.
