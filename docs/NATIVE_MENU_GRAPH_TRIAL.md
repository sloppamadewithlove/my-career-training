# Native menu graph trial

Read-only candidate continuation from an SDK menu-stack address. The development host probe runs it only with `--menu-graph-trial`, after the separate object-header check matches. It does not mutate a menu. A counted graph is not lifetime or ABI proof. `native_mutations` and `layout_verified_for_mutation` are always false.

The first home-menu run observed `RootMenuMovie`, matched the menu stack, `GFxShell_TA`, one `GFxMoviePlayer_X`, and `GFxDataStore_X`. Its original shared array rule rejected the table header without recording the raw count/capacity. The rejection therefore does not establish that any particular count was observed. The count-only rule below is a subsequent revision. That run ended through normal game closure after the five-minute lease; its explicit unload request was refused and no separate unload receipt exists. The temporary DLL was removed and BakkesMod configuration hashes were unchanged.

The September 2026 metadata is the MIT-licensed ObscuritySRL/rlsdk snapshot `99c4330f8e26e037f7f343dbe75b6dd5c08c4a01`. Its license is `plugin/licenses/rlsdk-LICENSE.MIT`. These offsets are historical candidates. The separate host observation of executable `56b499a85ad927c6b5cc47cb4813f956dd9263405fdf4eddc65b669b53185bc7`, BakkesMod core 229, and build `261013.63066.530866` does not verify this layout.

## Source offsets

UObject base, `packages/steam/offsets/Core.ts`: Name `0x48` (line 47), Class `0x50` (line 48), archetype `0x58` (line 49). The candidate header used here is `0x60` bytes, the same rule as the object-header trial. TArray is data `0x0`, count `0x8`, capacity `0xC`, size `0x10` (lines 24–28).

| Candidate | Source | Offset |
| --- | --- | --- |
| `GFxDataRow_X.Shell` | `packages/steam/offsets/ProjectX.ts` line 7417; class at `classes/ProjectX.ts` line 5259 | `0x88` pointer |
| `GFxData_MenuStack_TA` | `classes/TAGame.ts` lines 26342–26346, extending `GFxDataSingleton_X` (`classes/ProjectX.ts` lines 5276–5278), which extends `GFxDataRow_X` | inherited `Shell` only |
| `GFxShell_X.Movies` | `offsets/ProjectX.ts` line 7585; `classes/ProjectX.ts` line 5453 | `0xC0` `TArray` |
| `GFxShell_X.DataStore` | `offsets/ProjectX.ts` line 7586; `classes/ProjectX.ts` line 5454 | `0xD0` pointer |
| `GFxShell_TA` | `classes/TAGame.ts` lines 32063–32067, extends `GFxShell_X` | same movie and store fields |
| `GFxDataStore_X.Tables` | `offsets/ProjectX.ts` line 7437; `classes/ProjectX.ts` line 5286 | `0x70` `TArray` |
| `GFxMoviePlayer_X` | `classes/ProjectX.ts` lines 5395–5399, extends `GFxUI.GFxMoviePlayer` (`classes/GFxUI.ts` lines 316–320) | class token only |

`FGFxDataStoreTable` is documented at `packages/steam/structs/ProjectX.ts` lines 926–935, with size `0x80`. That element size is not used. The table check reads only the 16-byte `TArray` header and does not infer an 8-byte pointer stride or walk elements. `UComponent.TemplateOwnerClass` at `0x60` (`classes/Core.ts` lines 751–758) is not read. There is no `GFxMoviePlayer_TA` class in this snapshot, so a movie is recognized only for an exact `GFxMoviePlayer_X` token. Any other movie class is `unrecognized` and its fields are not read. Shell class tokens are only exact `GFxShell_X` or `GFxShell_TA`. No further shell subclass is present in the snapshot.

Name matches use caller-supplied SDK token ids. Integers read from candidate memory are never turned into strings. Header and metaclass checks match the object-header trial: class name high word must be zero, the metaclass name must be the `Class` token, and the metaclass class pointer must be itself. An unknown or mismatched menu stack or shell stops that branch. A mismatched movie header stops the rest of the movie walk.

## API

`mct::NativeMenuGraphTrial::inspect(menuStack, tokens, read)`.

`Tokens` is `menuStack`, `shellX`, `shellTA`, `moviePlayerX`, `dataStore`, and `className`. Each must be a positive distinct id. The read callback is `bool(address, out, size)`. There is no write or call callback.

The result carries counts and fixed categories only: `menu_stack`, `shell.status`, `shell.class_category` (`gfx_shell_x` or `gfx_shell_ta`), `movies.count`, `movies.recognized`, `movies.unrecognized`, `movies.unreadable`, and the data-store fields below. It does not contain addresses or copied object bytes.

Movie arrays stay a pointer list: count `<= 32`, capacity `<= 256`, count `<=` capacity, and a non-empty list is at most 256 bytes of aligned userland pointers. Table headers are separate. A plausible table count is `0 <= count <= 4096`, `capacity >= count`, and `capacity <= 8192`. A non-empty count or capacity needs an aligned userland data pointer. Count 0 and capacity 0 may use a null data pointer or a valid one; any other empty pointer is rejected. Rejection still records signed `observed_count` and `observed_capacity`, plus `tables_reject`: `tables_negative`, `tables_count_limit`, `tables_capacity_limit`, `tables_count_exceeds_capacity`, or `tables_pointer_rejected`. `table_count` stays 0 unless that header was accepted. `table_layout_matched` is always false. An unreadable table header remains `tables_rejected` and has no observed numbers. One budget covers reads (`48`), nodes (`40`), and bytes (`4096`).

`candidate_graph_counted` means those candidate checks passed. It does not authorize plugin calls, launcher writes, or menu mutation. CMake registers the synthetic test as `native_menu_graph_trial`.

Synthetic coverage is `plugin/tests/native_menu_graph_trial_tests.cpp`: a small valid fixture, malformed or overflowing movie arrays, table counts above 32 and at the 4096/8192 bounds without element reads, rejected negative or extreme table headers with their observed numbers, null and garbage table pointers, an unknown class, a failed read, the read budget, and the absence of private bytes and addresses in the report.
