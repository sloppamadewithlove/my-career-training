# GARAGE-CATALOG-01 — what the local product catalog can establish

## Scope and conclusion

Static review of the frozen MCT catalog reader and both Garage list paths,
after reading GARAGE-01, GARAGE-02, GARAGE-RESTORE-01 and RESTORE-01. The
previously obtained, sanitized SDK-header report is used for the distinction
between catalog templates and online item instances. No game, account,
inventory, save or live catalog data was accessed; no code, tests, network,
download or install action was performed.

The current source cannot support an **“all skins available”** claim. It can
browse a bounded set of product rows returned by the local game catalog API,
then filter those rows for a local item-code format. That is not a complete
owned-inventory list, a guarantee of equipability, a rendered preview, or a
native saved loadout. No catalog population was sampled in this pass, so there
is no measured count or coverage percentage.

## Evidence ladder

| State | What the frozen source establishes | What it does not establish |
|---|---|---|
| **Catalog row present** | `GetAllProducts()` returned a product wrapper with a non-null slot and nonempty label; the parser copied ID, slot, label and `IsPaintable()` (`plugin/src/MyCareerTraining.cpp:1515-1534`). | Ownership, unlock state, account instance, DLC entitlement, current-build completeness, or equipability. |
| **Browseable row** | The legacy Garage filters the in-memory rows by one of 15 hard-coded category slots and a case-insensitive name substring, with 18 rows per page (`plugin/src/CareerUI.cpp:520-552`). | A product thumbnail or 3D/scene preview. The tile is a label and selection marker. |
| **Locally compatible selection** | The native menu's listable predicate requires one of 11 supported slots, product ID 1..65535 and a nonempty name. The design validator also bounds paint to 0..18 and rejects duplicate slots (`NativeCosmeticContext.h:156-230`; `CosmeticDesignCode.h:16-30, 74-81, 165-200`). | SDK `CanEquip()` success, ownership, product-specific paint compatibility or a native team preset. |
| **Local override accepted** | Apply rechecks that the exact product ID and slot are present in the scan and rejects nonzero paint for a product whose single `paintable` flag is false; it writes the local item-mod code/enabled cvars (`MyCareerTraining.cpp:1590-1615`). | That Rocket League rendered the requested item correctly. The apply message explicitly leaves scene appearance for verification. |
| **Owned or equipped** | No owned instance or native saved preset is read by this Garage path. | Account ownership, painted/certified instance identity, equipped Blue/Orange preset or online visibility. |

The SDK distinction and preview boundary were established in the prior
sanitized GARAGE-02 header review: `GetAllProducts()` is a catalog-template
surface; owned/cached-unlocked APIs and `OnlineProductWrapper` instances are
separate data. That review did not inspect or publish user inventory data.

## Catalog parser and coverage ceiling

`scanProducts()` returns early while `result.online` is true, obtains
`ItemsWrapper`, and enumerates `GetAllProducts()`. It scans at most 100,000
entries, processing at most 200 per tick. It skips null products, null slot
wrappers, and empty labels; every other row is copied as only `{id, slot,
name, paintable}` and sorted by name when the scan completes
(`MyCareerTraining.cpp:1515-1534`; `MyCareerTraining.h:31-45`).

The scan does not call `GetOwnedProducts()`, `GetCachedUnlockedProducts()` or
`ProductWrapper::CanEquip()`. It stores no online instance ID, attributes,
paint IDs, product origin, DLC marker or per-item compatibility list. The
current scan also has a hard 100,000-row ceiling and exposes no truncation flag;
if the underlying catalog exceeded it, the code would publish the scanned
prefix as complete. The current runtime catalog size was not read, so this is
a code limit, not a claim that the cap is reached.

There is no source-level DLC exclusion, nor evidence here that the SDK API
includes every DLC, platform-specific, hidden or retired product. The result
must be described as rows returned by this API on a particular build; neither
inclusion nor exclusion of any specific DLC family is proven. The product
record itself does not carry the build ID or scan receipt, even though the
runtime status has a separate build string (`MyCareerTraining.h:31-45`).

## Slot visibility versus local compatibility

The older Garage has 15 fixed categories: body slot 0, decals 1, wheels 2,
boosts 3, antennas 4, toppers 5, primary paint finish 7, accent paint finish
12, engine audio 13, trails 14, goal explosions 15, banners 16, anthems 18,
avatar borders 20 and titles 21 (`CareerUI.cpp:520-543`). Body, banner, border
and title categories are labeled catalog-only and cannot enter the local
design. Decals and wheels are supported item-code slots; the scanner contains
no source-level decal or wheel exclusion. The native Garage exposes the 11
equipable slots and explicitly leaves bodies and the other three catalog-only
categories out (`NativeCosmeticContext.h:156-203`).

The scanner itself does not filter to those 15 slots, so an unknown/new slot
may be retained in the catalog vector without a Garage category. The native
list filters to the 11-slot whitelist and removes duplicate product IDs within
one slot (`NativeCareerLayout.h:2563-2574`). The older ImGui list does not
deduplicate rows. Neither path consults `CanEquip()`.

There is a filter mismatch in the older Garage: its default “Show supported
local items only” filter checks only `product.id <= 65535` (`CareerUI.cpp:527,
540-547`). It does not enforce the lower bound of 1. Selecting a row also
checks only that upper bound (`:559-568`), while the v4 design validator
requires ID 1..65535 (`CosmeticDesignCode.h:23-30, 177-185`). If the catalog
ever returned an ID below 1, the old list could display/mark it for design
selection but Apply would reject it; this audit did not inspect a live ID set.

The local item format supports 11 specific slots, one item per slot, at most
15 encoded entries, and product IDs through 65535 in v4 (8191 in legacy v3).
The present native draft cap is exactly 11, matching its supported slots
(`CosmeticDesignCode.h:16-30, 34-50, 74-81, 165-200`;
`NativeCosmeticContext.h:18-21, 193-203`). This is a product-template
compatibility check for MCT's local code, not the game's full list of
equippable inventory slots.

## Paint, team and appearance limits

The Garage's 19 paint labels use local override codes 0..18; zero means
original finish. The SDK paint-database ID and product-specific painted
instance attributes are not stored or mapped (`CareerUI.cpp:538-539, 584-595`;
`CosmeticDesignCode.h:43-50, 188-200`; prior GARAGE-02 report). In the local
draft, a nonzero code is accepted when `IsPaintable()` is true. There is no
per-product check that each of the 18 named variants is applicable to that
product. It is therefore not evidence that every paint can be used on every
product or that the same painted item exists in the account.

The local color override has one primary and one accent RGB value, not separate
Blue and Orange presets (`CareerUI.cpp:594-595`; `CosmeticDesignCode.h:43-50`).
The wire format stores no body, inventory, entitlement or physics data. It
allows one selected product per slot; it does not represent multiple product
instances or certified stats. Body slot 0 is browse-only and cannot be applied
through this code (`CosmeticDesignCode.h:43-50, 74-81`; `NativeCosmeticContext.h:156-170`).

## Safe wording and evidence needed for a broader claim

The current UI can accurately be described as **“Browse product templates
returned by this game build”** and **“select a supported local design.”**
“All skins available,” “all owned items,” “compatible with every paint,”
“previewed,” and “equipped to your account” exceed the source evidence.

Before claiming complete catalog coverage, capture a sanitized, build-bound
catalog receipt with scan count, returned count, truncation state, duplicate
policy and per-slot counts, then compare UI-exposed slots with the API's slot
set. That still proves catalog presence only. Ownership would require a
separate, consented owned-instance source retaining `ProductInstanceID` and
typed attributes. Compatibility would require an explicit `CanEquip`/runtime
check and product-specific paint validation. A visual preview needs a proven
thumbnail resolver or isolated render capture. Account application needs a
separate native loadout/equip verification. None of those datasets or runtime
checks was read or run here.

## Source fingerprints and prior evidence

The SDK archive identity below is recorded by the earlier sanitized GARAGE-02
report and the frozen `plugin/CMakeLists.txt` pin; SDK headers were not
re-downloaded or read in this task.

| Source | Bytes | SHA-256 |
|---|---:|---|
| `plugin/src/MyCareerTraining.cpp` | 89,835 | `edc7bf5a6dc7ca0cff34ac694fb72fe71fa26dfe1fd4607d512f3b321a1a9279` |
| `plugin/src/CareerUI.cpp` | 46,493 | `35b9c68b6eaeea0c3a81ca12563508271a390ee407b85b2ec08199dc3603e29c` |
| `plugin/include/MyCareerTraining.h` | 9,591 | `e151a44dc9d8f4c28283ccd9629501556a877889518a0a5363b099d51f4fc78d` |
| `plugin/include/CosmeticDesignCode.h` | 12,515 | `55ea534cf36f555dec260f8f1dbd1150b5a3acec8d7a684d57a38c83ec7fd948` |
| `plugin/include/NativeCosmeticContext.h` | 16,539 | `24c9eaba9f659e45197dd8397167ce48fd62ff8791af20cedb9c93d8bcb2382f` |
| `plugin/include/NativeCareerLayout.h` | 167,035 | `17d2ec0a82c79fad1949715ad62840bcace4177cbbe137da3aa675289109eb78` |
| `plugin/CMakeLists.txt` | 13,779 | `489e7323fddf44634321a3c341dc34aa54cead9e432c71aa2bff7bb3eea148b7` |
| Prior sanitized `work/campaign/garage-02.md` | 13,031 | `1567922adb5d0992e72abb062ed370ecbf73c15a5f50348ce29ffd400d513626` |

SDK pin recorded by GARAGE-02: commit
`479e8f571cf554b25f4eeb64d611dec4133edcaf`, archive SHA-256
`e4072d2884a432bedfd7a7e8474000137b1649deeea3346de4f1b2a0cb9dd866`.
