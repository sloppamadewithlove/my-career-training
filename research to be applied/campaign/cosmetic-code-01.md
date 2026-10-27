# COSMETIC-CODE-01 — local item-code format and apply boundary

## Finding

The MCT encoder is structurally aligned with the v4 BakkesMod loadout-code layout described by BakkesMod's public `BakkesModLoadoutLib`: six-bit version, ten-bit byte length, eight-bit XOR checksum, least-significant-bit-first fields, 16-bit v4 product IDs, and Base64 text. MCT emits only a restricted same-loadout design. **This does not prove the installed BakkesMod/Rocket League host accepts its string or renders the chosen appearance.** MCT has no production decoder or external-code import path; successful cvar readback only confirms the text and enable flag were stored.

The strongest public reference is the BakkesMod organization repository at commit `19575a1206df1d72cb5ae1d91053192956972f26` (2022-10-14; commit message says product IDs moved to 16 bits). It describes itself as a library to read/create BakkesMod loadout share codes. It is a reference implementation, not a current formal spec or the installed host parser. Relevant files: [BakkesModLoadoutLib.cpp](https://github.com/bakkesmodorg/BakkesModLoadoutLib/blob/19575a1206df1d72cb5ae1d91053192956972f26/BakkesModLoadoutLib/BakkesModLoadoutLib.cpp), [bmloadout.h](https://github.com/bakkesmodorg/BakkesModLoadoutLib/blob/19575a1206df1d72cb5ae1d91053192956972f26/BakkesModLoadoutLib/bmloadout.h), and [helper_classes.h](https://github.com/bakkesmodorg/BakkesModLoadoutLib/blob/19575a1206df1d72cb5ae1d91053192956972f26/BakkesModLoadoutLib/helper_classes.h).

## MCT apply path

Relative to the audited `work/reviewed-training` source:

1. The Garage builds a local draft from product ID, slot, paint code, and optionally two color triples. A native Apply request is converted back to this JSON payload and queued only while the owned offline frontend is eligible (`plugin/src/MyCareerTraining.cpp:792-835`).
2. The local request handler requires `cl_itemmod_code` and `cl_itemmod_enabled`, validates the payload, then rechecks each `(product_id, slot)` against rows read from `GetAllProducts()`. A nonzero paint is allowed if that row reports `IsPaintable()` (`MyCareerTraining.cpp:1581-1599`). It does not call `CanEquip()` or check whether that particular paint is valid for that product.
3. It encodes the design, snapshots the original code/enabled pair, writes the code then enables the override, and reads both back for exact equality (`MyCareerTraining.cpp:1599-1614`; `CosmeticOverrideState.h:24-39`). On a failed write/readback it attempts restoration; incomplete restoration stays pending and can be retried (`CosmeticOverrideState.h:41-64`). This is a two-cvar transaction, not validation by the BakkesMod code parser.
4. The success text explicitly says the scene appearance still needs game verification. No runtime appearance observation is claimed here.

## Encoded fields and validation limits

| Layer | MCT behavior |
|---|---|
| Versions | Default/apply uses v4 with 16-bit product IDs `1..65535`. Explicit legacy v3 uses 13-bit IDs `1..8191`; unsupported versions throw (`CosmeticDesignCode.h:16-31,138-143,213-216`). |
| Header/check | Version: 6 bits; declared byte length: 10 bits; checksum: 8 bits. Checksum is `0xFF XOR` bytes from offset 3 to the declared end, not a cryptographic integrity check. Fields are packed least-significant bit first and Base64 encoded (`:221-271`). |
| Teams | One same-team bit is always set to true. MCT carries one item list, one primary/accent RGB pair, and a six-bit wheel-team ID fixed to zero. It cannot encode separate Blue/Orange items, separate team colors, or esports wheel-team selections. |
| Items and slots | Four-bit item count; each item contains 5-bit slot, 13/16-bit product ID, paint-present bit, and optional 6-bit paint. JSON accepts at most 15 items, but MCT permits only eleven unique slots: `1,2,3,4,5,7,12,13,14,15,18`; effective design capacity is therefore eleven. Slot 0 (body), banners, avatar borders, titles, and every other unsupported slot are rejected or browse-only (`CosmeticDesignCode.h:74-82,164-200,213-252`; `garage-01.md`). |
| Paint and colors | Paint defaults to 0 and is limited to `0..18`. A nonzero code is additionally gated by the catalog's single `paintable` flag, not product-specific paint availability. The numeric 1–18 paint names match the public library enum, but there is no mapping to SDK paint-database IDs. If colors are enabled, each of primary and secondary must be three finite non-boolean numbers in `[0,1]`, rounded to 8-bit channels (`:116-131,188-209`). |
| Unknown fields | The encoder ignores unrecognized JSON fields. If `override_colors` is absent or false, supplied `primary`/`secondary` values are ignored. The tests explicitly include extra body/inventory/physics properties and expect them not to affect an empty code (`cosmetic_design_code_tests.cpp:187-195`). This is a local apply payload, not a lossless external preset schema. |

The public library confirms the item-slot names, paint values, header widths, product width and same-team flag. Its format can hold distinct Blue and Orange records and color overrides, and its 5-bit slot field can represent more slot values than MCT permits (`BakkesModLoadoutLib.cpp:14-49,90-198,200-279`; `bmloadout.h:3-41`). The public source comments that a body ID is not applied by BakkesMod when loading the share code; MCT also excludes it.

There are implementation details that prevent claiming byte-for-byte parity with the public writer. In the public source, `save()` writes an Orange wheel-team field even when the same-team flag is set, whereas `load()` copies Blue values to Orange and does not consume that field on the same-team branch. Its `ToHex()` helper returns `current_bit / 8 + 1` bytes, which can add a trailing byte when the stream ends exactly on a byte boundary, while the header length uses ceiling division. MCT emits the ceiling-sized stream and one wheel-team field. The reference reader's same-team branch returns without requiring the cursor to reach the declared byte length, so those differences may be tolerated by that reader; this is not evidence of installed-host behavior.

## What malformed codes and tests establish

- **MCT input JSON:** finite whole-number slot/product/paint fields are required; booleans, fractions, missing fields, duplicate slots, unsupported/body slots, invalid paint, product ID 0/out of range, bad color arrays and unknown version enums are rejected. Whole-valued JSON floats are accepted. Unsupported extra fields are ignored. The exact limits and cases are in `CosmeticDesignCode.h:84-123,164-210` and `cosmetic_design_code_tests.cpp:294-365`.
- **Encoded input:** MCT has no decoder, so it cannot import, inspect, or round-trip an arbitrary `cl_itemmod_code`. Its code tests manually unpack the output and check golden v3/v4 byte strings, header size, checksum, fields and zero padding (`cosmetic_design_code_tests.cpp:43-135,161-292`). They do not parse a malformed/truncated external code, compare MCT output to the public library executable, or verify the game host parser.
- **Public reader:** the pinned public reference decodes Base64, reads version/length/checksum and fields, and checks the XOR checksum. The visible code uses a coarse string-length tolerance of six characters and does not show a decoded-buffer-length check before CRC/body reads; it also does not strictly reject unknown versions, unknown slot IDs, paints above 18, or duplicate item slots (duplicates are assigned into a map). Treat this as a useful format reference, not a hardened decoder or proof of Rocket League acceptance (`BakkesModLoadoutLib.cpp:90-198`; `helper_classes.h:63-115`).
- **Partial cvar apply:** existing `cosmetic_override_state_tests.cpp` exercises write/read failures, rollback, restore retry, and preserved original values (`garage-restore-01.md`). Those state tests do not check parser acceptance, appearance, or item-by-item completeness. No test was run for this research task.

## Coordinator follow-up on the public reference

The exact public reader has additional format quirks: a zero item count consumes another four bits using a shadowed local variable; the same-team branch copies items and wheel-team ID but not color fields; and the separate Orange color read is conditional on the Blue color flag. These source paths prevent treating this program as an unquestioned round-trip oracle, particularly for empty and colored designs. They do not establish how the installed host parses a code. The bit-reader also has no retained buffer bound, and the helpers pair malloc/calloc allocation with delete; no public-reference executable was built or run here.

The coordinator fetched the three cited source files at the pinned commit and matched the reported CPP hash. `bmloadout.h` is 722 bytes, SHA-256 `12f33a2e90e312e3e4022c9451186bcb9eb63b26abd28587df89d60515df48f0`; `helper_classes.h` is 2,378 bytes, SHA-256 `c984b6a665011363b7cba4ebeaa52785daf98363bc61a631f50e9fb06701ac08`. The complete pinned repository tree contains no filename matching license/copying. This research treats it as a public format reference and does not redistribute its source or assert a reuse license.

## Concrete identity/validation contract

For a design produced by MCT, the identity should be the exact validated tuple `(slot, product_id, local_paint_code)` for every item, plus versioned color fields and the same-team policy. Before encoding, retain the current catalog check on exact `(product_id, slot)` and `paintable`; do not claim that this means `CanEquip`, ownership, or per-paint compatibility. If external share-code import is added, it needs a separate, bounded decoder that validates Base64, minimum and declared byte length, version, checksum, field bounds, duplicate/unknown slots, paint range and trailing bits before any CVar write. Preserve distinct per-team data or explicitly reject it; never silently convert a two-team preset into MCT's same-team format.

Minimum future proof: first account for the public reference quirks above, then compare a v4 MCT output against a bounded, independently checked interpretation of the reference format for empty, one-item, painted, colored, byte-aligned, maximum-supported-slot and same-team cases; add malformed/truncated/unknown-version/checksum and duplicate-slot input cases; verify an unknown-but-in-range product ID is refused by the current-catalog gate; and in an allowed offline runtime verify one selected item/paint visually, both cvars' readback, and exact restoration. A successful string readback is not a successful cosmetic apply.

## Source identity

| Local source | SHA-256 |
|---|---|
| `plugin/include/CosmeticDesignCode.h` | `55ea534cf36f555dec260f8f1dbd1150b5a3acec8d7a684d57a38c83ec7fd948` |
| `plugin/src/MyCareerTraining.cpp` | `edc7bf5a6dc7ca0cff34ac694fb72fe71fa26dfe1fd4607d512f3b321a1a9279` |
| `plugin/include/CosmeticOverrideState.h` | `dc2e5183d2b0b8f96b18696dfcd6b509c7a2bf8a9daf03e1f4861cb07382dab7` |
| `plugin/tests/cosmetic_design_code_tests.cpp` | `4f98a2f471e4d708d9963a0e7a6aa4a19a187355c02880ba1348edb370afd907` |
| `plugin/tests/cosmetic_override_state_tests.cpp` | `3fa861f9613fe807b05adee211fa5e61f16930d126bac7f37f80257ecd6e1dda` |

Public reference commit: `19575a1206df1d72cb5ae1d91053192956972f26`; `BakkesModLoadoutLib.cpp` 13,459 bytes, SHA-256 `2ea38e14ba2fdfe914c4a4adaa2b63a674622bbc26e80038256178b2cb136430`.

**Evidence boundary:** source and public-reference comparison only. No local game/host parser was invoked, no item/cvar/account state was read or written, and no visual result was tested.
