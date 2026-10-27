# IMPORT-PROBE-01 — observed bridge import and best-attempt selection

The coordinator executed a separately built and source-reviewed DeepSeek diagnostic against the frozen candidate's actual Backend import, storage, reload and legacy automatic personal-best path. The final invocation exited 0: four synthetic cases, five imported fixture files and twelve diagnostic checks. It used temporary storage, offscreen Qt and fake worker transport. No game process, physics, rendering or live ghost load was exercised.

| Synthetic case | Observed automatic selection |
| --- | --- |
| Successful imported `local_player` claim, starting and sample game-speed fields omitted | Selected; label rewritten to `Your Best Attempt`; import status retained |
| Same kind of imported claim with explicit speed 1.0 | Selected normal-speed control |
| Explicit speed 0.5 | Imported but not selected; bridge reported no matching successful recording |
| Two same-lesson/same-variant imports, duration 2.0 versus 0.5 seconds, second declaring different setup | Shorter second import selected and labeled `Your Best Attempt` |

The last case uses synthetic setup metadata, not a real current game context. A separate call to the production `compatible_recordings` function confirmed the two fixtures differ in game version, hitbox, map, mutators and starting state. It does not prove that a real worker would accept the selected recording. The bridge supplies no compatibility candidate during this legacy selection; later worker compatibility checks were outside the fake-transport diagnostic.

The actual route was `dispatch(import_recording)` through the desktop dialog branch, application storage, `_recordings`, and `dispatch(play_recording, kind=personal_best)`. It did not exercise the native explicit-recording-ID path, in-game path-based import, an event loop, lifecycle timer ticks, or game acknowledgements. All source claims were intentionally hand-authored test data and are not evidence of any real player's recording.

The stored index kept the claimed `source.kind` and had no application-owned `capture_origin` field. Imported status remained present in the selected payload even while the personal-best label changed. Identity comparison excluded only this derived label; every other selected field matched the stored recording. Dialog invocation counts were 1, 1, 1 and 2 for the four cases. No launch was requested and the game-process stub was not consulted in this run. These counters describe this traced diagnostic, not arbitrary Backend paths.

## Provenance and checks

The [observed JSON](../evidence/import-probe-01.json) records fixture/storage hashes, cases, controls, observations and implementation-file hashes. The [diagnostic source](../experiments/research_import_probe.py.txt) is a research artifact, not a product patch. The coordinator verified the three implementation modules match the frozen candidate byte for byte. Separate DeepSeek builder/reviewer passes corrected reporting defects before the successful run; review acceptance is source review, not an independent execution.

An earlier successful run omitted sample speeds but inherited starting-state speed 1.0 from the lesson. A supplemental assertion exposed that narrower fixture. The builder then explicitly removed starting-state speed in the omitted case, the reviewer checked that delta, and the final run reproduced selection with both kinds of speed fields absent. Only that corrected run is the evidence published here; no claim is made that the earlier case tested both defaults.

The twelve checks verify route execution, fixture imports, normal/slow controls, payload identity, isolated storage and the bounded output/transport conditions. Selection of the shorter different-setup import is recorded separately as an observation, not asserted as correct product behavior. No test totals from other reports are added to these counts.

## Builder consequence

[IMPORT-IDENTITY-01](import-identity-01.md) is now supported by an executable bridge-path reproduction. Preserve imported playback, while distinguishing application-observed capture origin from JSON claims. Filter compatible candidates before selecting a best, and treat missing speed as unknown if normal-speed comparability is required. Do not present this diagnostic as proof of real ghost playback or a completed production fix.
