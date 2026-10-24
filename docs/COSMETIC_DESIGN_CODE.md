# Local cosmetic design codes

`plugin/include/CosmeticDesignCode.h` formats a garage payload as a BakkesMod item code. The default code is version 4. Version 3 remains available when the caller passes `CosmeticCodeVersion::LegacyV3`.

The format facts come from BakkesModLoadoutLib commit `19575a1206df1d72cb5ae1d91053192956972f26` (2022-10-14), "Ran out of item IDs, now allocating 16 bits for them". That tree's `bmloadout.h` sets `CURRENT_LOADOUT_VERSION` to 4. Its reader uses 16 product bits when the code version is at least 4, and 13 bits otherwise. Its writer emits 16 product bits. The other fields are unchanged. That repository has no general license, so this helper does not copy its implementation. The commit is source evidence for the code layout. It is not a live Rocket League or BakkesMod appearance check. Whether a code shows up in the current game is still unverified.

The helper does not write `cl_itemmod_enabled` or `cl_itemmod_code`, does not read or restore previous cvar values, and does not call the game, the SDK, or the filesystem. An encoded string is a formatting result. It does not show that a design appears in a match, that a product is installed, or that a player's inventory changed.

Body slot 0, catalog-only slots 16, 20, and 21, and every other slot outside the supported set stay unsupported. The code has no body, inventory, entitlement, or physics fields. Extra JSON keys with those names are ignored.

## API for the plugin root

Namespace `mct`. Argument type `mct::Json`. Failures throw `std::runtime_error` with a short player-facing message.

```cpp
enum class CosmeticCodeVersion { LegacyV3 = 3, CurrentV4 = 4 };

inline constexpr int kMaxCosmeticProductId = 65535;
int maxCosmeticProductId(CosmeticCodeVersion version = CosmeticCodeVersion::CurrentV4);

struct CosmeticDesignItem {
    int slot;       // JSON "slot"
    int productId;  // JSON "product_id"
    int paint;      // JSON "paint", or 0 when that key is absent
};

struct CosmeticDesign {
    std::vector<CosmeticDesignItem> items;
    // Both set, or both empty. Channels are 0..255, red then green then blue,
    // from floor(unit * 255 + 0.5) with unit in [0, 1].
    std::optional<std::array<unsigned char, 3>> primary;
    std::optional<std::array<unsigned char, 3>> secondary;
};

CosmeticDesign validateCosmeticDesign(const Json& payload,
    CosmeticCodeVersion version = CosmeticCodeVersion::CurrentV4);
std::string encodeCosmeticDesign(const CosmeticDesign& design,
    CosmeticCodeVersion version = CosmeticCodeVersion::CurrentV4);
```

`kMaxCosmeticProductId` and `maxCosmeticProductId()` are the current 16-bit cap, `65535`. `maxCosmeticProductId(LegacyV3)` is `8191`. Catalog filters should use that helper instead of a hardcoded `8191`. An unknown version value throws.

`payload` is the garage apply object. It is not the bridge envelope. Omitting the version argument selects v4. Pass `LegacyV3` to read or write a 13-bit code.

The plugin validates before the installed-catalog check, then encodes the same struct. It also reuses this validator for saved cosmetic items and validates both saved color triples before loading either one. The typed `slot` and `productId` are already whole numbers in range. Do not call `numberValue` and cast the JSON number before that check: a huge or fractional value can make that cast undefined or turn `1.9` into product `1`.

```cpp
const mct::CosmeticDesign design = mct::validateCosmeticDesign(request.payload);
for (const mct::CosmeticDesignItem& item : design.items) {
    const auto found = std::find_if(products.begin(), products.end(), [&](const MctProduct& product) {
        return product.id == item.productId && product.slot == item.slot;
    });
    if (found == products.end())
        throw std::runtime_error("Refresh the installed cosmetic catalog before applying this item.");
}
const std::string encoded = mct::encodeCosmeticDesign(design);
```

`encodeCosmeticDesign` checks the struct again so a hand-built design cannot emit an out-of-range slot, product, paint, or a duplicate slot. Color override is on only when both channel arrays are present. This header does not know which products the running game has installed. An in-range id is not ownership, a grant, or a promise that the scene will show it.

Capture-before-write bookkeeping for the previous item-mod cvars stays in the plugin runtime. This helper does not participate in that restore path.

## Validation

Supported slots are `1, 2, 3, 4, 5, 7, 12, 13, 14, 15, 18`. v4 product ids are `1` through `65535`. v3 product ids are `1` through `8191`. Paint is `0` through `18` on both versions. Paint `0` is unpainted and omits the 6 paint bits. A missing `paint` key stays `0`. A missing `slot` or `product_id` is rejected. A present paint, slot, or product that is a boolean, a fraction, a string, null, NaN, or infinity is rejected before any conversion to `int`.

Whole-number floats such as `1.0` are accepted. Values that are whole but outside the selected version's range, including `8192` on v3, `65536` on v4, and magnitudes such as `1e308`, are rejected without a narrowing cast. A v4-validated id above `8191` is still rejected if that struct is encoded as `LegacyV3`.

At most 15 items are accepted. Duplicate slots are rejected. The garage stores one product per slot, so its apply payload already has unique slots. Only 11 slots can actually be equipped, so a valid design never fills all 15 positions.

`items`, when present, must be an array of objects. A missing `items` field encodes an empty design. `override_colors`, when present, must be a boolean. Missing means no color override. While the override is off, `primary` and `secondary` are ignored even if they are malformed, because the garage always sends them. While it is on, both keys must be arrays of three finite numbers in `[0, 1]`.

## Wire format

Bits are written least-significant-bit first, and each byte is filled from bit 0 upward. Unused bits in the last byte stay `0`.

| Field | Width | Value |
| --- | --- | --- |
| Version | 6 | `4` by default, or `3` for `LegacyV3` |
| Byte length | 10 | Encoded byte count, written after the payload exists |
| Checksum | 8 | `255` XOR every byte from index 3 through the end |
| Same team | 1 | `1` (one visual design for both teams) |
| Item count | 4 | Number of items |
| Each item | v4: 22 or 28; v3: 19 or 25 | Slot 5, product 16 on v4 or 13 on v3, paint flag 1, and paint 6 only when the flag is 1 |
| Color flag | 1 | `1` when both normalized colors are present |
| Channels | 48 when the flag is 1 | Primary red, green, blue, then secondary red, green, blue, 8 bits each |
| Esports wheel team | 6 | `0` |

The version, length, and checksum occupy the first three bytes. The checksum is stored at byte index 2 and is computed from byte index 3 through the end, excluding the header. Item order is the validated array order, not slot order.

The result is standard base64 with `=` padding.

Checked v3 examples, requested with `LegacyV3`:

| Design | Bytes | Base64 |
| --- | --- | --- |
| Slot 1, product 1, paint 0, no colors | `C3 01 D8 23 04 00 00` | `wwHYIwQAAA==` |
| No items, no colors | `43 01 FE 01 00` | `QwH+AQA=` |
| Slot 1, product 1, paint 1, no colors | `03 02 59 23 04 80 01 00` | `AwJZIwSAAQA=` |
| No items, primary `0,0,0`, secondary `1,1,1` | `C3 02 21 21 00 00 C0 FF FF 3F 00` | `wwIhIQAAwP//PwA=` |

Checked v4 examples, the default:

| Design | Bytes | Base64 |
| --- | --- | --- |
| Slot 1, product 1, paint 0, no colors | `04 02 D8 23 04 00 00 00` | `BALYIwQAAAA=` |
| Slot 1, product 8192, paint 0, no colors | `04 02 5C 23 00 80 00 00` | `BAJcIwCAAAA=` |
| Slot 1, product 65535, paint 0, no colors | `04 02 DC 23 FC FF 03 00` | `BALcI/z/AwA=` |
| Slot 1, product 1, paint 1, no colors | `04 02 D4 23 04 00 0C 00` | `BALUIwQADAA=` |
| No items, primary `0,0,0`, secondary `1,1,1` | `C4 02 21 21 00 00 C0 FF FF 3F 00` | `xAIhIQAAwP//PwA=` |

`0` rounds to channel `0`, `0.5` to `128`, and `1` to `255`. `0.001` rounds to `0` and `0.004` rounds to `1` with the same `floor(unit * 255 + 0.5)` conversion.

## Tests

`plugin/tests/cosmetic_design_code_tests.cpp` is a standalone console fixture. It decodes base64 itself and reads the version, length, checksum, same-team bit, item count, slot, product, paint flag, paint, color channels, esports team, and trailing zero bits. The v3 and v4 one-item byte vectors above are compared directly, and their base64 is also produced from those bytes by the fixture. v3 checks pass `LegacyV3` explicitly. The fixture does not treat the helper as its own decoder, and it does not treat the upstream library as a live code round trip.

It also covers 16-bit ids `8192` and `65535`, rejection of `65536`, huge numbers, fractions, and booleans before conversion, legacy rejection of product `8192` from JSON and from a typed struct, item order, painted and unpainted widths, color rounding, duplicate slots, more than 15 items, malformed payloads and item arrays, body slot 0 and the other unsupported slots, invalid color overrides, and unknown version values. Ignored body, inventory, and physics keys must leave the empty v3 code unchanged.

These checks cover the item-code bytes and rejected input only. They do not equip a product, show an appearance in Rocket League, or restore shared cosmetic cvars. They do not claim that every catalog body or skin can be equipped.

`plugin/CMakeLists.txt` owns the fixture target inside `if(BUILD_TESTING)`. The executable is `mct_cosmetic_design_tests` and the CTest name is `cosmetic_design_code`:

```cmake
add_executable(mct_cosmetic_design_tests tests/cosmetic_design_code_tests.cpp)
target_link_libraries(mct_cosmetic_design_tests PRIVATE mct_bridge)
add_test(NAME cosmetic_design_code COMMAND mct_cosmetic_design_tests)
```

The header is header-only. The executable needs `mct_bridge` so `mct::Json` and the pinned nlohmann header resolve the same way as the other plugin fixtures.
