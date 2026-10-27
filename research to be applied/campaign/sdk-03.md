# SDK-03: installed wrapper getter bodies

## Scope and identity

Static REA analysis only; no game process, runtime attach, compile, or patch was used. The target was the installed `pluginsdk.dll`, 1,947,136 bytes, SHA-256 `421df9b1ccb65cc0e316189d824f25f0d00bb05352e0ea4e5219e7f400ec8813` (the same artifact identity recorded in SDK-01/02). The smaller same-named DLL under the Steam game directory is a different artifact and was not analyzed.

REA provider: Ghidra 12.1.4, x86-64 PE, immutable ephemeral import. Function-name search Evidence: `ev_3186e3a036749975bab94444618cc7394f655689bdc658a6fcc2ac76f53a05a`. The four complete, single-range function dossiers are listed below. The code descriptions are paraphrases of Ghidra observations, not original source. Ghidra reports an embedded PDB reference with unknown load state; do not assume PDB symbols were loaded.

## Getter behavior observed

| Getter | Evidence ID | Static body observation | What it establishes |
|---|---|---|---|
| `BallWrapper::GetbFadeOut` | `ev_9c828698d431a606f2181f033631573c5458d605a15900ed298d88c21726ca1f` | Reads the wrapper’s underlying flag word and returns one selected bit as `unsigned long`; no outgoing call. | A direct flag accessor. The body contains no fade timing, transition, or write logic. |
| `BallWrapper::GetbEndOfGameHidden` | `ev_ff451bf082cec348f78bf963d6a30076ed3f1c961c67c585f266987500704085` | Reads a different bit of the same underlying flag word and returns it as `unsigned long`; no outgoing call. | A second direct flag accessor. Its body does not hide, show, or destroy a ball. |
| `ServerWrapper::GetGameTimeRemaining` | `ev_a079a8468300bf46515f424ef2114459090e4375743710788ccdfb6fcb348100` | Reads and returns a `float` field from the wrapper’s underlying object; no outgoing call or arithmetic. | It exposes a stored field as-is. This function does not reveal units, countdown direction, phase, or update cadence. |
| `GameEventWrapper::GetGameStateTimeRemaining` | `ev_b0b63de2456a889ade3778875d54565c40991e365029bf8f15b4d4637df1e043` | Reads and returns an `int` field from its underlying object; no outgoing call or arithmetic. | It exposes another stored field as-is. The body does not explain how it relates to the `ServerWrapper` timer. |

All four returned dossiers mark the body range complete and record no callees or unresolved outgoing calls. The direct read patterns mean these getters neither delegate to another helper nor perform their own timer/fade logic. The separate bit reads in the two `BallWrapper` methods are evidence for two stored flags; the names alone do not show when either flag changes or what game lifecycle event causes it.

The pinned SDK declarations previously recorded in [SDK-01](sdk-01.md) agree on the API-level return types: both ball methods return `unsigned long`, the server timer returns `float`, and the game-event timer returns `int`. That header evidence describes the declared API; the DLL-body evidence establishes only the actual read/return pattern in this installed SDK binary.

## Limits and implication

This pass does not identify code that writes these fields, establish whether either timer counts down in seconds, or prove any relationship between a timer value and a ball fade/hide transition. It also does not show whether the underlying object is valid in a particular game phase or which plugin/game version calls these functions. The result is consistent with the SDK wrappers being thin field accessors, not proof of stock-game timer or ball-lifecycle causality.

To establish timing or visibility semantics would require evidence from the relevant field writer or a scoped lifecycle observation of the loaded game/plugin. Neither was part of this static getter pass.
