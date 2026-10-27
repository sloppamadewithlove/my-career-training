# COSMETIC-CONFLICT-PROTOTYPE-01

## Status

This is a standalone synthetic prototype of a **proposed conflict-preserving lease**, not a selected production fix. It does not change the production caller or the [unchanged production class](../experiments/cosmetic-conflict-prototype/plugin/include/CosmeticOverrideState.h.txt). The [contract](../experiments/cosmetic-conflict-prototype/docs/contract.md.txt) keeps code and enabled state as one coupled pair. The latest independent source re-review was `accepted_with_scope_limits`; that was source-only acceptance of the declared sequential experiment, not runtime behavior or product integration. See the [review/build/run evidence summary](../evidence/cosmetic-conflict-prototype-01.json) and [prototype artifacts](../experiments/cosmetic-conflict-prototype/).

The actual output JSON contains **22 unique scenarios and 44 records**: each scenario has one `production` observation and one `prototype` record. There are 22 records per side and `failures` is zero. The production records are asserted pins of the unchanged production class’s observed behavior; they are not desired behavior and do not mean production is fixed. The prototype records exercise the proposed lease policy only. No cvar or game API is called.

## Policy and tradeoff

The policy records the first successful baseline, retains it across repeats while the lease is owned, and tracks verified and before-write candidate pairs. It reads back between setters and before restore; an unreadable host returns `Pending` with no blind restore write. If baseline code cannot be restored, it attempts to disable and stays `Pending`; a failed or ignored disable does not prove the host is disabled.

Conflict releases ownership of the **whole pair** to preserve an external change. This can leave a hybrid behind: for example, external code with MCT’s `enabled=true`, or MCT’s requested code with an external `enabled=false`. After relinquishment, Restore is `Noop`, so the leftover MCT-written field is not automatically cleaned up. A new explicit Apply starts a new lease from the current pair; that fresh baseline may include the leftover MCT field. This is the conservative pair-level tradeoff, not a conclusion that per-field ownership is wrong.

The contract also requires caller work before integration: the existing bool restore result and success messages cannot distinguish `Restored`, `ConflictPreserved`, `Pending`, and `Noop`. Apply, explicit restore, scope-loss, unload, and UI retry/reporting paths need separate mappings. Production caller changes and selection of a policy remain unresolved.

## Build and run record

The first configure attempt could not resolve its CMake launcher from `PATH`; it stopped before configuration and is not a source-build failure. The second attempt used the available Visual Studio CMake and succeeded. Configure exited 0 at 13:48:24–13:48:31 UTC on 2026-10-27 with `-S . -B build-prototype -G "Visual Studio 17 2022" -A x64`. Build exited 0 at 13:53:04–13:53:10 UTC for the Release target with one job. The executable ran at 13:53:28 UTC, exited 0, and emitted JSON with zero declared failures.

Toolchain evidence: CMake 3.31.6; Visual Studio 17 2022; MSVC 19.44.35229.0/toolset v143 14.44.35207; Windows SDK 10.0.26100.0; Windows target 10.0.26200; x64 Release, C++17. CMake executable SHA-256: `6fe2e6431b45cf32b9b2f3e50a8efae046a2366eb34d0fb36da027cf56102aec`. Executable SHA-256: `510ee13f2ec42b0547c0b18b938f224dda5ef7e53fa6a9466eacc3a7e1224ae8`; captured run stdout SHA-256: `ab713e95cea53201bff8c8ff70392f723e24efa54a08211b7d88dd3ffc39f8b7`.

## Source identity and limits

The sizes and hashes below identify the original inputs compiled here. Published text copies normalize line endings and trailing whitespace; their separate publication hashes and original paths are in the evidence summary. To reconstruct the experiment, copy those five text artifacts to their recorded original paths in a fresh directory, removing the added `.txt` suffix where present. `CMakeLists.txt` already has its original name. Run the configure/build arguments recorded in the receipt with the listed toolchain; CMake must resolve to that installation. The [observed JSON](../evidence/cosmetic-conflict-prototype-observed.json) is reformatted for publication, so its file hash differs from the raw stdout hash.

The [prototype source](../experiments/cosmetic-conflict-prototype/tools/research_cosmetic_conflict_prototype.cpp.txt) is 34,036 bytes, SHA-256 `b6cc9d2f978e73250903f074f40ff484e3396830eb356b7e67b9631ba4011926`. The [lease header](../experiments/cosmetic-conflict-prototype/tools/ResearchCosmeticLease.h.txt) is 7,406 bytes, SHA-256 `ccf0271dc7351879a9ab38c60bf85a55ce698e522105adcce09f22b250a870b6`. The [unchanged production header copy](../experiments/cosmetic-conflict-prototype/plugin/include/CosmeticOverrideState.h.txt) is 2,830 bytes, SHA-256 `dc2e5183d2b0b8f96b18696dfcd6b509c7a2bf8a9daf03e1f4861cb07382dab7`. Contract SHA-256: `2b7f0de33f8c799b097637203ec3e1ae5dd0314ad3c0af880324744266dc6e3d`; CMakeLists SHA-256: `1762999f53cd6580e21f234b28510ea1e6da9041b0a9dbec061b2794c7a5793b`.

This evidence is limited to synthetic in-memory host values and the declared sequential scenarios. It does not test real cvar behavior, BakkesMod callbacks, settings persistence, unload timing, crashes, rendered cosmetics, or any game session. ABA, reentrant writes, and concurrent writes are excluded; the accepted review also notes there is no direct scenario pinning a post-conflict Restore `Noop` with the hybrid unchanged. A green run supports only the 22 declared scenarios, not general correctness or product readiness.

## Published-source reconstruction

At 14:03:37–14:03:55 UTC, the coordinator restored the five published text artifacts into a fresh private directory, verified their publication hashes, and configured/built/ran the standalone target with one build job. All three stages exited 0. The 22-scenario, 44-record output was byte-identical to the first run, with zero declared failures. Source hashes were unchanged afterward. CMake reports the exact version `3.31.6-msvc6`; the base version above is shortened. This checks the published handoff with the existing installed toolchain, not a clean machine or game. The executable hash changed, so deterministic binary reproduction is not claimed. See the [reconstruction receipt](../evidence/cosmetic-conflict-reconstruction-01.json).
