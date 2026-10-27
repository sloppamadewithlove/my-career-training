# COSMETIC-RESTORE-PROBE-01 — external edits overwritten by the current transaction

## Observed result

A standalone C++17 diagnostic compiled and ran against the unchanged production `CosmeticOverrideState` header. **All six control checks passed.** In three active-override experiments, Restore overwrote a later external code edit, enabled-state edit, and both edits. This reproduces [GARAGE-RESTORE-01](garage-restore-01.md)'s source finding in the actual transaction class, using in-memory callbacks. It is not a game/cvar observation or a production fix.

| Case | Observed result |
| --- | --- |
| Apply then Restore without external change | Returned the original pair; pending state cleared. |
| External code edit during active override | External code replaced by the pre-Apply original. |
| External enabled edit during active override | External `false` replaced by original `true`. |
| External edits to both fields | Both external values replaced by originals. |
| Enabled setter throws after code was written | `FailedRestored`; the originally disabled pair restored and pending state cleared. |
| Restore without any Apply | Success/no-op; zero write attempts. |

The active-override cases independently checked that Apply returned `Applied`, the pending flag was true before the external edit, and the intended fields actually changed. Their overwrite results are observations, not assertions defining desired behavior. The partial-failure control records the code present at the throwing setter, establishing that the code write preceded the failure.

## Build, review and identity

Separate DeepSeek builder and reviewer. The first review required clearer stage labels, explicit active-override preconditions, and removal of an unverified header-identity claim. Those changes were re-reviewed and accepted before execution. Main verified the copied header against the frozen candidate, the compiled probe against the review copy, parsed the observed JSON and checked all six results.

One isolated x64 Release executable; MSVC 19.44.35229.0, Visual Studio 17 2022 generator. Configure exited 0 in 7.00 seconds; single-job build exited 0 in 5.31 seconds; diagnostic exited 0. No plugin DLL, native menu, game or installed component was compiled or changed.

- Production header SHA-256: `dc2e5183d2b0b8f96b18696dfcd6b509c7a2bf8a9daf03e1f4861cb07382dab7`.
- Diagnostic source SHA-256: `8c24f36e7899b61602614ec4d88d2f2d8f31974624e9ea45ae55a8889d406445`.
- Diagnostic executable SHA-256: `ea06186f594770b1ff4579c84e458261c86d237a4d96e5d7db264364e5507069`.
- [Observed output and build/source receipt](../evidence/cosmetic-restore-probe-01.json). The program's empty hash placeholders are retained; measured identities are in the enclosing coordinator receipt.

## Reproducer and next implementation boundary

The research folder contains text copies of the [diagnostic source](../experiments/research_cosmetic_restore_probe.cpp.txt), [standalone CMake project](../experiments/cosmetic_restore_probe_CMakeLists.txt), and [unchanged transaction header](../experiments/cosmetic_restore_probe_CosmeticOverrideState.h.txt). Recreate `tools/research_cosmetic_restore_probe.cpp`, `CMakeLists.txt`, and `plugin/include/CosmeticOverrideState.h` in a separate directory before building; the receipt pins each source. These are application-owned diagnostic inputs, not extracted game code.

A future fix should track which field values MCT actually wrote, detect later external changes, and preserve or explicitly report conflicts. Partial writes/readback failure need a defined ownership rule rather than unconditional rollback. Keep the first original baseline across repeated applies only while that baseline remains relevant to the same owned override.

The diagnostic does not cover unavailable hosts, `RestorePending`, repeated Apply, reentrant or concurrent writes, crash recovery, actual BakkesMod callback behavior, online transition timing or rendered cosmetics. It demonstrates the sequential transaction behavior under the six declared fake-host cases only.
