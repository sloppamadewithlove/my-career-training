# GARAGE-RESTORE-01 — cosmetic apply and restoration ownership

## Scope and source state

Read-only trace of local item-mod apply/restore from both the plugin-window Garage and native Garage menu. It focuses on write validation, cleanup ownership, app Return, online handoff, unload, user edits, and crash recovery. It does not claim a product rendered correctly or interact with the account/game.

The inspected `work/reviewed-training` HEAD was `1fe8c85839a5e72166ee1d5cc3066627548d9fa2`. The current shared worktree has modifications to `plugin/src/MyCareerTraining.cpp`, `plugin/src/CareerUI.cpp`, `plugin/src/NativeMovieHost.cpp`, `plugin/include/NativeCareerLayout.h`, `src/my_career_training/bridge.py`, and `src/my_career_training/bootstrap.py`; references describe those working-tree contents. The transaction and schema headers, `OwnedSession.h`, and cited C++ tests were clean. Hashes are at the end.

## Current ownership model

The Garage stores a **local design draft** separately from the **active two-cvar override**. `loadPreferences()` / `savePreferences()` persist `cosmetic_items`, the paint codes, and color choices in `plugin-preferences.json` (`plugin/src/MyCareerTraining.cpp:1680–1720`). They do not persist `CosmeticOverrideState::original_` or `pending_`; those belong to a `MyCareerTraining` object in memory (`plugin/include/CosmeticOverrideState.h:17–68`). A saved draft is not an applied design, a saved Rocket League loadout, or an ownership record.

Both Garage UIs offer an explicit Apply and Restore. The old plugin window saves the draft and queues Apply; the native menu builds a typed local effect and `NativeMovieHost` calls `applyNativeCosmetic` directly (`plugin/src/CareerUI.cpp:517–608`; `plugin/include/NativeCareerLayout.h:2506–2715,2768–2791`; `plugin/src/NativeMovieHost.cpp:624–629`). Navigating Back or closing the native movie is not a restore operation. The native “Restore original” control is enabled whenever the item-mod cvars exist, even with no pending lease; in that case the restore handler is a no-op success but the UI reports “Original cosmetic overrides restored” (`NativeCareerLayout.h:2701–2711`; `MyCareerTraining.cpp:1585–1588,1632–1644`).

## Apply validation and readback

The native route is limited to an owned, fresh offline session in the frontend, outside a match and replay (`MyCareerTraining.cpp:580–590,792–838`; `OwnedSession.h:61–74`). The movie host also requires the current live menu session nonce before invoking the local effect (`NativeMovieHost.cpp:624–629`). The plugin-window request is queued and only processed from the owned-offline tick path (`MyCareerTraining.cpp:1285–1347,1543–1585`).

The validator accepts at most 15 unique supported slots; this local code supports eleven slots, product IDs 1–65535, and paint codes 0–18. It rejects fractional, boolean, non-finite, duplicate-slot, unsupported-slot, and out-of-range values. Native UI additionally requires a current catalog row matching the **same product ID and slot**, and a paint code above zero requires the catalog’s `paintable` flag (`CosmeticDesignCode.h:74–82,164–211`; `NativeCosmeticContext.h:217–278,299–345`; `MyCareerTraining.cpp:1590–1599`). Stale saved entries are shown as outside the current local catalog and omitted from the native Apply draft rather than represented as valid (`NativeCareerLayout.h:2617–2636,2662–2698`).

Limits: the paint field is the project’s fixed local item-mod code, not the SDK paint database ID; the code only checks a per-product `paintable` boolean, not each paint/product combination (`garage-02.md`; `plugin/include/NativeCosmeticContext.h:20–24,82–86`). The body slot is catalog-only. The current color override validates both RGB triples when enabled, then writes them inside the encoded local code; it does not change Blue/Orange saved presets. A successful cvar readback is not evidence of visible appearance.

The low-level apply transaction snapshots the original code and enabled flag before its first setter, marks a lease pending, writes `cl_itemmod_code` then enables `cl_itemmod_enabled`, and reads both back for exact equality. If a setter throws or readback differs, it immediately attempts restoration and distinguishes restored failure from still-pending restoration (`CosmeticOverrideState.h:24–43`; `MyCareerTraining.cpp:1581–1615`). The native movie host counts the local effect after `applyNativeCosmetic()` accepts/queues it; the actual cvar transaction runs in `processLocalRequests()` later in the plugin tick, so that effect count alone is not cvar readback (`NativeMovieHost.cpp:624–629`; `MyCareerTraining.cpp:792–838,1285–1347,1543–1615`). The eventual caller message says the design was sent to BakkesMod and explicitly says scene appearance still needs verification (`MyCareerTraining.cpp:1613`).

Partial failure handling is deliberate. Restore attempts the original code first and verifies it; it enables the original enabled flag only if the original code is back, otherwise it disables the override. It then reads both values and clears the snapshot only after exact match. A failed restore remains pending for retry (`CosmeticOverrideState.h:45–64`). While the native menu lease is pending, its Apply and selection controls are blocked and it asks the player to restore first (`NativeCosmeticContext.h:307–360`; `NativeCareerLayout.h:2586–2605,2679–2701`). The plugin-window Apply control has no equivalent `restorationPending` disable; a later Apply can replace the active code while retaining the original pre-first-apply baseline.

## Return, online transition, unload, and crash limits

`ownedOfflineNow()` remains true while the bridge reports offline ownership, the same launched process/executable is present, and the game reports not online (`MyCareerTraining.cpp:580–590`; `OwnedSession.h:61–74`). On a lost/stale/online scope, `tick()` calls `restoreCosmetics()` and retries on later ticks if the original values do not read back. A tick exception also attempts restore (`MyCareerTraining.cpp:1285–1449`).

**Return to the MCT hub retains the game.** The in-game bootstrap sets `backend.in_game = True`, and the app exposes that as `offline` (`src/my_career_training/bootstrap.py:248`; `bridge.py:264`). For a Return-to-hub stop, `_close_after_stop()` waits for the worker without closing the game; the completion branch clears the activity request/session but leaves the launched-game ownership state intact (`bridge.py:2240–2245,2320–2340`). On this source path, the native plugin’s owned-offline scope remains eligible at the hub, and neither native Back/Return nor that app state transition calls `restoreCosmetics()`. The current local override can remain active after Return. This is a static path inference, not a live observation, and is distinct from explicit Restore or a transition that actually becomes online or loses ownership.

For an online handoff, the Python lifecycle stops the offline worker/game; the native plugin’s cleanup path is scope loss (`IsInOnlineGame()` makes `ownedSession()` false) or `onUnload()`. The latter attempts restoration once and logs if it cannot complete (`bridge.py:2217–2225`; `OwnedSession.h:61–74`; `MyCareerTraining.cpp:259–292,1381–1394`). The source does not prove that restoration completes before an online launch or that cvar setters remain available during shutdown; this ordering has not been observed in game.

There is no durable cosmetic baseline journal in the inspected MCT code. An abrupt game/plugin crash can bypass tick and `onUnload`, destroying the only copy of the original values. Whether BakkesMod persists either cvar across a crash/restart is unknown. If the item-mod values survive but MCT’s snapshot does not, a later Apply would snapshot the then-current values as its new “original”; the old pre-crash baseline is unavailable to this code. The persisted Garage draft does not repair that loss.

## User edits after Apply

The restoration class stores `original_` and a pending bit, but not the exact value last written by MCT or per-field ownership (`CosmeticOverrideState.h:17–68`). The traced MCT path registers no notifier for the two item-mod cvars; its reads occur during apply/restore and availability reporting (`MyCareerTraining.cpp:1343–1345,1581–1644`). If the player or another tool changes either cvar after a successful Apply, a later explicit Restore, scope-loss cleanup, or unload blindly writes the pre-Apply code and enabled flag over that edit. I found no compare-before-restore/relinquish policy for cosmetics. This differs from the controller-overlay lease’s user-change reconciliation described in `restore-01.md`.

The existing cosmetic transaction test checks no-host behavior, partial apply failure, repeated applies retaining the first baseline, failed restore/retry, and safe disable when the original code cannot be restored. Its final `player-updated` fixture changes values **after** a previous lease has ended, then verifies a new transaction snapshots that new baseline. It does not test an external edit while MCT’s override is still pending (`plugin/tests/cosmetic_override_state_tests.cpp:9–72`). The design-code tests cover serialization/validation fixtures; neither they nor the native movie protocol fixtures prove game rendering or external-edit preservation. Tests were inspected only; none were run.

## Future acceptance cases

- Decide whether Return-to-hub should retain the local appearance or restore it. Assert that policy after the worker stops while the owned Rocket League frontend stays open; distinguish menu Back from session Return.
- On Apply, use a valid current product/slot/paint combination and verify both cvars read back exactly. Reject stale catalog rows, wrong-slot IDs, catalog-only body slot, non-paintable products with a paint, invalid numeric ranges, and unsupported combinations if the item-mod mapping can enumerate them. Keep “cvars accepted” separate from rendered verification.
- Inject failure at code write, enabled write, and each readback; require restoration-pending status until the exact original pair returns. Confirm every retry is idempotent and no success message appears on an incomplete restore.
- While a lease is pending, externally edit code only, enabled only, and both. Restore, scope loss, online handoff, and unload must preserve values no longer owned by MCT, or show a conflict rather than overwriting. For partial writes, compare ownership per field so an external edit is not mistaken for an MCT value to roll back.
- Apply twice and verify the first baseline remains owned until Restore. Compare behavior across the legacy plugin window and native menu; currently the former permits another Apply while pending and the latter blocks it.
- Restart with a saved draft and separately test clean unload versus abrupt termination. Either persist a process-bound recovery snapshot safely or state that crash recovery is unsupported; never treat a recovered draft as the old cvar baseline.
- With no pending override, Restore should report “nothing to restore” rather than claim that original settings were restored.

## Source hashes (SHA-256)

| File | SHA-256 |
|---|---|
| `plugin/include/CosmeticOverrideState.h` | `DC2E5183D2B0B8F96B18696DFCD6B509C7A2BF8A9DAF03E1F4861CB07382DAB7` |
| `plugin/include/CosmeticDesignCode.h` | `55EA534CF36F555DEC260F8F1DBD1150B5A3ACEC8D7A684D57A38C83EC7FD948` |
| `plugin/include/NativeCosmeticContext.h` | `24C9EABA9F659E45197DD8397167CE48FD62FF8791AF20CEDB9C93D8BCB2382F` |
| `plugin/include/NativeCareerLayout.h` | `17D2EC0A82C79FAD1949715AD62840BCACE4177CBBE137DA3AA675289109EB78` |
| `plugin/include/OwnedSession.h` | `CF7F58BD302A1FA94974F734388DC473E66E664660FC429D794A229538013628` |
| `plugin/src/MyCareerTraining.cpp` | `EDC7BF5A6DC7CA0CFF34AC694FB72FE71FA26DFE1FD4607D512F3B321A1A9279` |
| `plugin/src/CareerUI.cpp` | `35B9C68B6EAEEA0C3A81CA12563508271A390EE407B85B2EC08199DC3603E29C` |
| `plugin/src/NativeMovieHost.cpp` | `D336DC9958403791E7BA14779F29C719E45E6642A0644092934746E189A0A282` |
| `src/my_career_training/bridge.py` | `AC502D1F19810BACA479A534AA766A6AFBEA7BA57A405452835CC9DCFF379AC2` |
| `src/my_career_training/bootstrap.py` | `82FEF12F0D472ED0927996FF691E4B9BABB1884BA9F8C02DF4315B49557CA7EC` |
| `plugin/tests/cosmetic_override_state_tests.cpp` | `3FA861F9613FE807B05ADEE211FA5E61F16930D126BAC7F37F80257ECD6E1DDA` |
| `plugin/tests/cosmetic_design_code_tests.cpp` | `4F98A2F471E4D708D9963A0E7A6AA4A19A187355C02880BA1348EDB370AFD907` |
