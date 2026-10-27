# GARAGE-02 — Catalog identity, paint variants, and preview limits

Follow-up restoration limit: the [cosmetic restore diagnostic](cosmetic-restore-probe-01.md) demonstrates that the current transaction can overwrite later external edits to either cosmetic cvar. Future restore acceptance below must preserve or report conflicts and restore only fields still owned by MCT; a saved snapshot alone is insufficient.


**Date:** 2026-10-27
**Scope:** Static source/header research only. No game, inventory, account, asset extraction, code, or runtime action.

## Finding

The pinned public BakkesMod SDK separates a **product catalog entry** (`ProductWrapper`, keyed by base product ID) from an **online product instance** (`OnlineProductWrapper`, keyed by a two-part `ProductInstanceID`). The SDK declares useful metadata for catalog entries, item attributes, paints, and thumbnail asset names. It does not declare a documented product-package-to-texture loader or a read-only 3D preview API. The project currently reduces each catalog row to `id, slot, name, paintable`; it does not retain thumbnail references, SDK paint IDs/colors, item attributes, or online instance identity.

These are declaration-level facts from the cached SDK archive selected by `plugin/CMakeLists.txt` (BakkesModSDK commit `479e8f571cf554b25f4eeb64d611dec4133edcaf`, SHA-256 `e4072d2884a432bedfd7a7e8474000137b1649deeea3346de4f1b2a0cb9dd866`). The archive has no independent Git identity in this workspace. Headers and names do not establish current-runtime behavior, ownership correctness, asset loading, or online visibility.

## Identity and current schema

- `ItemsWrapper::GetAllProducts()` returns `ProductWrapper` rows; `ProductWrapper` inherits `ProductTemplateWrapper` and exposes a base product ID, slot, labels, `IsPaintable`, `CanEquip`, attributes, asset metadata, and thumbnail metadata. The separate `GetOwnedProducts()` / `GetCachedUnlockedProducts()` APIs return different wrapper types/data. `GetUnlockedProducts()` is explicitly deprecated with a crash warning and should not be used. API names are not proof of successful account synchronization or complete ownership results.
- `OnlineProductWrapper` has `GetProductID()` plus `GetInstanceIDV2()`, attributes, and a route back to the base `ProductWrapper`. `ProductInstanceID` is `{upper_bits, lower_bits}` (two 64-bit fields). It is not interchangeable with the integer product ID. Two owned instances can refer to the same base product while carrying different attributes; retain the instance identity whenever representing a specific owned variant.
- Painted and certified metadata are distinct attribute types. `ProductAttribute_PaintedWrapper::GetPaintID()` returns an SDK paint-database ID. `ProductAttribute_CertifiedWrapper` exposes stat key/ID/value and rank/description labels. `ProductAttributeWrapper` also exposes type and label metadata. Never copy these instance attributes onto a generic catalog template row.
- `PaintDatabaseWrapper::GetPaints()` returns `ProductPaintWrapper` records with ID, label, visibility flag, finish type, and colors. The finish type is an enum byte and the header directs callers to the SDK enum wrapper for interpretation. This is a richer paint source than the project’s fixed list, but the declarations do not establish which paint applies to which product.

**Current project distinction:** `MctProduct` and `NativeCosmeticProduct` store only `id`, `slot`, `name`, and `paintable` (`plugin/include/MyCareerTraining.h:31-45`, `plugin/include/NativeCosmeticContext.h:75-80`). `scanProducts` fills those fields from `GetAllProducts()` (`plugin/src/MyCareerTraining.cpp:1504-1524`). No owned product or instance API is called in the garage path. Thus the rows are a locally read product catalog, not an ownership view.

The project’s `paint` integer is also not the SDK paint database ID. Current UI labels a fixed 0–18 item-mod code choice list (`plugin/src/CareerUI.cpp:538-539`; `plugin/include/NativeCosmeticContext.h:20,82-86,172-181`). Zero means original finish; values 1–18 are local override codes. No conversion table between those values and `ProductPaintWrapper::GetId()` is present. Keep `override_paint_code` and `sdk_paint_id` separate until a supported, verified mapping exists.

## Thumbnail and preview surfaces

- `ProductWrapper` exposes the product `GetAssetPackageName` / `GetAssetPath` and thumbnail `GetThumbnailAssetPath`, `GetThumbnailPackageNameForLoad`, package name, and asset name (`ProductWrapper.h:17-18,39-42`). These are asset-reference metadata; no `ProductWrapper` method returns a texture or image.
- `GfxProductsWrapper::GetLoadingProducs()` returns loading records with product/hash IDs, referenced views, and an online product (`GfxProductsWrapper.h:15`; `LoadingProductWrapper.h:15-18`). It is a loading/status relationship, not a thumbnail pixel/texture accessor.
- `ImageWrapper` accepts a filesystem/string path and can load/draw that image; `CanvasWrapper` draws an `ImageWrapper`. `GameWrapper::LoadToastTexture` is documented for loading a texture from a file path into BakkesMod toasts. These declarations do not document how to resolve a product’s Unreal package/asset name to a local file or GPU texture. Do not guess a filesystem path, unpack game assets, or advertise thumbnail display based on these names alone.
- No declared API found in the pinned item wrappers constructs a temporary car/product scene, applies an arbitrary catalog template or paint to it, or renders a 3D preview without changing a loadout. `LoadoutSaveWrapper::SetPreviewTeam` changes team selection context, but its meaning is only the team field; it is not a product preview operation. `EquipPreset` and `LoadoutSetWrapper::EquipProduct` are loadout-changing operations and should not be repurposed as preview calls without verified semantics and explicit user intent.
- The current project does have a separate local item-mod route that writes BakkesMod cosmetic cvars, snapshots/restores them, and labels the feature “Local appearance only” (`plugin/src/CareerUI.cpp:517-520,597-608`; `plugin/src/MyCareerTraining.cpp:1572-1605`). This is a reversible **local setting change**, not an SDK read-only preview. Its actual scene appearance remains unverified. Body slot 0 is explicitly catalog-only; local code supports only its declared item-code slots (`CosmeticDesignCode.h:74-81`, `NativeCosmeticContext.h:150-170`). Do not imply that every catalog product or car body can be previewed.

## Rendering and wrapper lifetime

The SDK wrappers derive from `ObjectWrapper`, which carries a raw `memory_address`; `ArrayWrapper` provides count/get access. Header declarations do not document wrapper ownership, lifetime, or thread safety. `GameWrapper::Execute` says to use it when calling from another thread, and drawable rendering is callback-based (`GameWrapper.h:92-95`). The conservative integration boundary is to enumerate and dereference game wrappers through the existing `GameWrapper`-driven tick/callback path (the project scans products from `tick`, `MyCareerTraining.cpp:1266-1347`) or dispatch with `GameWrapper::Execute` when crossing threads; immediately copy primitive/string metadata into immutable application records, then use only those copied records for search/paging. Do not retain product/attribute/paint wrapper handles in UI or worker state.

For file-backed `ImageWrapper` thumbnails, preserve the noncopyable wrapper for as long as drawing can reference it, and respect its load-completion state/callback. This says nothing about loading Rocket League package assets; no supported package resolver was found in these headers.

## Ready-to-apply data shape

Keep catalog rows, account instances, paint definitions, and local design selections as separate records. Suggested shape (conceptual, not existing JSON/API):

```json
{
  "catalog_product": {
    "source": "game_catalog",
    "game_build": "observed-build-id-or-unknown",
    "product_id": 123,
    "slot_id": 2,
    "label": "...",
    "paintable": true,
    "can_equip": true,
    "thumbnail": {
      "asset_path": "metadata only",
      "package_name_for_load": "metadata only",
      "asset_name": "metadata only",
      "load_state": "unsupported_or_unverified"
    }
  },
  "owned_instance": {
    "source": "owned_instance_api",
    "instance_id": {"upper_bits": 0, "lower_bits": 0},
    "product_id": 123,
    "attributes": [{"type": "Painted", "sdk_paint_id": 7}]
  },
  "paint_definition": {
    "source": "sdk_paint_database",
    "sdk_paint_id": 7,
    "label": "...",
    "visible": true,
    "finish_type": "enum_value_unmapped",
    "colors": []
  },
  "local_design_selection": {
    "product_id": 123,
    "slot_id": 2,
    "override_paint_code": 4
  }
}
```

Do not populate `owned_instance` from `GetAllProducts()`. Do not mark `thumbnail.load_state` successful from an asset path alone. Keep paint-code mapping null/unverified until a safe supported mapping is established. For selection, validate the current catalog row by `(product_id, slot_id)`, recheck paintability against a fresh scan, and reject unsupported body/catalog-only slots and out-of-range IDs. If an owned-item screen is later added, construct it only from a successful owned-instance result and preserve the two-part instance key and typed attributes.

## Preview acceptance and explicit gaps

1. Catalog browsing must say “product catalog found for this game build”; it must not claim exhaustive skin coverage, ownership, unlocked status or equip availability without the corresponding evidence. The requested comprehensive cosmetics browser remains the target; coverage must be measured.
2. A row is a selection/draft until either a file-backed thumbnail is loaded through a supported path or an offline scene capture proves the local item-mod result. Show a placeholder when resolution/loading fails.
3. Display a painted/certified variant as account-owned only when sourced from a specific online instance and its attributes. A separate catalog preview may offer authored paint choices without claiming ownership. Show paint-database colors/labels as database metadata; do not imply product compatibility unless a validated selection path confirms it.
4. Keep the current local override paint code distinct from SDK paint IDs. Do not translate by array order or label similarity.
5. A no-ownership-mutation preview must not call `EquipProduct`, `EquipPreset`, or inventory writes. If using the project’s local item-mod cvars, identify it as a local setting change, take/verify a restoration snapshot, gate to a supported offline runtime, and independently verify rendered appearance. Body preview remains unsupported by the current local format.
6. Any thumbnail provider needs an identified supported package resolver, correct image lifetime/load handling, and a missing-image fallback. The pinned SDK declarations alone do not provide this.

**Not established:** actual completeness of `GetAllProducts`; semantics/freshness of `GetOwnedProducts`; compatibility of these declarations with the installed runtime; exact paint-ID-to-item-mod-code mapping; product-specific paint applicability; thumbnail package resolution or runtime loading; arbitrary 3D preview without loadout mutation; whether `SetPreviewTeam` changes only transient display state; visibility of local overrides to any other player.

## Source references

Local line references are relative to the SDK archive selected by the project CMake pin and `work/reviewed-training` source:

- SDK: `include/bakkesmod/wrappers/items/ItemsWrapper.h:42-67`; `ProductTemplateWrapper.h:12-18`; `ProductWrapper.h:17-44`; `OnlineProductWrapper.h:21-38`; `wrapperstructs.h:1019-1034`.
- Attributes/paint: `items/attributes/ProductAttributeWrapper.h:12-17`; `ProductAttribute_PaintedWrapper.h:12-17`; `ProductAttribute_CertifiedWrapper.h:12-22`; `items/dbs/PaintDatabaseWrapper.h:12-24`; `ProductPaintWrapper.h:11-21`.
- Thumbnail/render/loadout: `items/GfxProductsWrapper.h:15`; `items/LoadingProductWrapper.h:15-18`; `ImageWrapper.h:10-46`; `canvaswrapper.h:30-34`; `GameWrapper.h:92-121`; `items/LoadoutWrapper.h:14-20`; `items/LoadoutSaveWrapper.h:14-25`; `items/LoadoutSetWrapper.h:21-26`.
- Project: `plugin/include/MyCareerTraining.h:31-45`; `plugin/include/NativeCosmeticContext.h:13-21,75-95,150-181`; `plugin/include/CosmeticDesignCode.h:34-51,74-81`; `plugin/src/MyCareerTraining.cpp:1504-1524,1572-1605`; `plugin/src/CareerUI.cpp:517-608`.
- Pinned public SDK source: [ItemsWrapper.h](https://github.com/bakkesmodorg/BakkesModSDK/blob/479e8f571cf554b25f4eeb64d611dec4133edcaf/include/bakkesmod/wrappers/items/ItemsWrapper.h), [ProductWrapper.h](https://github.com/bakkesmodorg/BakkesModSDK/blob/479e8f571cf554b25f4eeb64d611dec4133edcaf/include/bakkesmod/wrappers/items/ProductWrapper.h), [OnlineProductWrapper.h](https://github.com/bakkesmodorg/BakkesModSDK/blob/479e8f571cf554b25f4eeb64d611dec4133edcaf/include/bakkesmod/wrappers/items/OnlineProductWrapper.h), [PaintDatabaseWrapper.h](https://github.com/bakkesmodorg/BakkesModSDK/blob/479e8f571cf554b25f4eeb64d611dec4133edcaf/include/bakkesmod/wrappers/items/dbs/PaintDatabaseWrapper.h), [ImageWrapper.h](https://github.com/bakkesmodorg/BakkesModSDK/blob/479e8f571cf554b25f4eeb64d611dec4133edcaf/include/bakkesmod/wrappers/ImageWrapper.h).
