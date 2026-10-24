# Native menu data-binding candidate

Read-only discovery of public menu-label coordinates from an SDK menu-stack address. It does not mutate a menu, call the SDK, or resolve an FName index to text. A reported string is a candidate cell in a candidate layout. It is not proof of a visible button, a writable binding, or a safe ABI.

`layout_verified_for_mutation`, `visible_binding_verified`, and `native_mutations` are always false. This module does not change the production build gate.

The prior graph trial matched MenuStack, `GFxShell_TA`, and `GFxDataStore_X` on BakkesMod core 229, executable `56b499a85ad927c6b5cc47cb4813f956dd9263405fdf4eddc65b669b53185bc7`, build `261013.63066.530866`, with 153 tables and capacity 196. Those counts are echoed as `prior_graph_capture`. They are not re-measured here. Table, row, and cell layout remains a candidate.

## Source offsets

The MIT snapshot is ObscuritySRL/rlsdk commit `99c4330f8e26e037f7f343dbe75b6dd5c08c4a01`. Its license is `plugin/licenses/rlsdk-LICENSE.MIT`. Offsets below were checked against that tree before use. They are historical candidates for this build, not a grant to write.

| Candidate | Source | Offset |
| --- | --- | --- |
| UObject header, Name, Class | `packages/steam/offsets/Core.ts` lines 33–50 | header `0x60`, Name `0x48`, Class `0x50` |
| TArray Data, Count, Max | `offsets/Core.ts` lines 24–28 | `0x0`, `0x8`, `0xC`, 16 bytes |
| `GFxDataRow_X.TableName` | `offsets/ProjectX.ts` line 7412; `classes/ProjectX.ts` line 5254 | FName `0x60` |
| `GFxDataRow_X.Shell` | `offsets/ProjectX.ts` line 7417; `classes/ProjectX.ts` line 5259 | pointer `0x88` |
| `GFxDataRow_X.RowIndex` | `offsets/ProjectX.ts` line 7418; `classes/ProjectX.ts` line 5260 | int32 `0x90` |
| `GFxData_MenuStack_TA` | `classes/TAGame.ts` lines 26342–26346 | extends `GFxDataSingleton_X`; own fields start at `0x98`, so the row fields above stay inherited |
| `GFxShell_X.DataStore` | `offsets/ProjectX.ts` line 7586; `classes/ProjectX.ts` line 5454 | pointer `0xD0` |
| `GFxShell_TA` | `classes/TAGame.ts` lines 32063–32067 | extends `GFxShell_X` |
| `GFxDataStore_X.Tables` | `offsets/ProjectX.ts` line 7437; `classes/ProjectX.ts` line 5286 | TArray `0x70` |
| `FGFxDataStoreTable` | `structs/ProjectX.ts` lines 926–935 | stride `0x80`: Name `0x0`, Columns `0x8`, Rows `0x18` |
| `FGFxDataStoreColumn` | `structs/ProjectX.ts` lines 908–914 | stride `0x0C`: ASType byte `0x0`, FName `0x4` |
| `FGFxDataStoreRow` | `structs/ProjectX.ts` lines 917–923 | stride `0x18`: Values `0x0`, BoundObject `0x10` |
| `FASValue` | `structs/GFxUI.ts` lines 53–63 | stride `0x28`: Type `0x0`, FString `0x10` |
| `AS_String` | `enums/GFxUI.ts` line 14 | `4` |

The table header read is 0x28 bytes. `bLevelTransitionPersistent` and `PrimaryKeyMap` are not read. FASValue fields other than the type byte and the FString header (`B`, `N`, `I`, `T`) are not read. FString is a 16-byte inline TArray of UTF-16 units: pointer, count, max. Only `AS_String` column and value cells are decoded, and only when both tags are 4.

Shell class tokens are exact `GFxShell_X` or `GFxShell_TA`. Header and metaclass checks match the object-header trial: class FName number must be zero, the metaclass name must be the `Class` token, and the metaclass class pointer must be itself. Integers from candidate memory are never passed to an SDK name resolver.

## Anchor, then small tables only

`mct::NativeMenuDataBinding::inspect(menuStack, tokens, read)`.

`Tokens` is `menuStack`, `shellX`, `shellTA`, `dataStore`, and `className`. Each must be a positive distinct id. `read` is `bool(address, bytes, size)`. The root read adapter may return an unaligned span, because a column record is 12 bytes and its FName sits at +4. This component still requires object, TArray, and bound-object pointers to be 8-byte aligned userland pointers, and UTF-16 data to be 2-byte aligned. It checks signed counts, capacity, and multiply/add overflow before every element span.

The anchor is refused, with no cell walk, unless all of these hold:

1. Menu stack, shell, and data store match the known class and metaclass.
2. The menu stack's TableName FName and RowIndex are readable, and RowIndex is not negative.
3. The store's Tables header is in range: count `<= 512`, capacity `<= 1024`, count `<=` capacity, and the count span fits. The prior 153/196 observation is inside this cap.
4. Some table's 8-byte Name equals that TableName, `RowIndex < row count`, and that row's BoundObject pointer is exactly the SDK menu stack.
5. That row's column count and value count are structurally valid and equal.

A later table with the same name can still anchor if an earlier one fails the bound-object check. Failure reasons are fixed: `missing_sdk_identity`, `menu_stack_unreadable`, `menu_stack_mismatch`, `shell_field_unreadable`, `shell_pointer_rejected`, `shell_unreadable`, `shell_mismatch`, `data_store_field_unreadable`, `data_store_pointer_rejected`, `data_store_unreadable`, `data_store_mismatch`, `row_identity_unreadable`, `tables_unreadable`, `tables_negative`, `tables_count_limit`, `tables_capacity_limit`, `tables_count_exceeds_capacity`, `tables_pointer_rejected`, `tables_span_overflow`, `anchor_row_out_of_range`, `anchor_table_missing`, `anchor_table_malformed`, `anchor_row_unreadable`, `anchor_bound_object_mismatch`, `anchor_columns_rejected`, `anchor_values_incompatible`.

After the anchor matches, only small tables are scanned. A table whose row or column header is negative, inverted, unaligned, or whose used span overflows is `skipped_malformed` with a fixed reason. A table whose row count or column count is above 64 is `skipped_oversized` with the observed counts. Oversized and malformed tables are not treated as good and their cells are not read. That is what keeps a garage, product, or user table out of the scan. Capacity above the count is allowed for a small table; reads use the count, never the capacity.

## What a label is

This is a store-wide scan after one row establishes the candidate data-store
relationship. A returned label need not belong to that anchored row or its
movie. The row/column limits apply to cell scanning; anchor lookup can inspect
one row in a larger structurally valid array. Separate reads are not an atomic
snapshot and do not establish object lifetime or protection from reallocation.
Bounded string payloads are read before filtering; nonallowlisted text is not
exported.

The only exported text is one of these canonical strings, matched case-insensitively after dropping a single trailing UTF-16 NUL:

`PLAY`, `GARAGE`, `SETTINGS`, `OPTIONS`, `ROCKET PASS`, `ITEM SHOP`, `PROFILE`, `EXTRAS`, `QUIT GAME`, `EXIT GAME`, `TRAINING`, `FREE PLAY`, `CUSTOM TRAINING`, `WORKSHOP`, `TOURNAMENTS`, `CHALLENGES`.

Anything else is counted in `strings_discarded` and dropped, including a longer prefix such as `PLAYLIST`, a trailing space, non-ASCII units, an FString longer than 65 units, or an FString capacity above 256. Those payloads are not read when the count or capacity already fails the cap. Raw decoded text is not stored; a hit is replaced by the canonical literal.

Each hit is a coordinate, not a pointer:

```json
{"text": "PLAY", "table_name": [index, number], "column_name": [index, number], "row_index": 0}
```

`table_name` and `column_name` are the raw FName index and number. At most 32 labels are returned (`labels_truncated`). There is no address, bound-object pointer, or string pointer in the result.

Global budget is 4096 reads and 256 KiB. A single read is at most 256 bytes. `read_budget_exhausted` or `read_failed` stops the walk. Labels already accepted stay in the result and remain unverified. `cell_discovery` is `refused` when the anchor fails, `scanned` when the small-table walk finishes, and `stopped` when the walk starts and does not finish.

`anchor_matched_no_public_labels` means the anchor held and no allowlisted cell was found. `public_label_candidates` means at least one coordinate was recorded. Neither reason authorizes a write.

## Re-resolution later

`GFxDataStore_X.GetValue(Table, Row, Column)` in the same metadata snapshot takes an FName table, an int row, and an FName column. The coordinate above is that candidate key. The public BakkesMod SDK does not expose a callable wrapper for this data-store method; a later adapter still needs a verified engine call boundary and must re-resolve the current store. This module does not call `GetValue`, `SetASValue`, or any other store function.

A later native-label step still has to prove which movie shows the cell, that the string is the visible caption rather than a duplicate in another table, and that a write would refresh the widget. Those proofs are outside this result. Until they exist, the three mutation flags stay false.

## Root integration

Header-only `plugin/include/NativeMenuDataBinding.h`. Synthetic fixture `plugin/tests/native_menu_data_binding_tests.cpp`. Root owns CMake and the process read adapter. The fixture is standalone and links the same way as `native_menu_graph_trial` once a target exists: the test includes the header and needs `mct_bridge` for `nlohmann::json`. No runtime or game test belongs to this module.

Suggested call from the host, after the existing graph identity check and only on the owned offline process:

```text
NativeMenuDataBinding::inspect(menuStack, {menuStackToken, shellXToken, shellTAToken, dataStoreToken, classToken}, read)
```

`read` must reject a short copy. It may accept an unaligned column span. The host should keep the JSON as diagnostics and must not treat `labels` as a mutation plan.
