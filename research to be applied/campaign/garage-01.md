# GARAGE-01 — Rocket League garage and cosmetic interface research

Follow-up restoration limit: the [cosmetic restore diagnostic](cosmetic-restore-probe-01.md) demonstrates that the current transaction can overwrite later external edits to either cosmetic cvar. Future restore acceptance below must preserve or report conflicts and restore only fields still owned by MCT; a saved snapshot alone is insufficient.


**Date:** 2026-10-27
**Scope:** Research only. No game was launched, no cvars or inventory were changed, and no compatibility test was run.

## Finding

The current “My Garage” is a local-design catalog layered over BakkesMod’s `cl_itemmod_code` / `cl_itemmod_enabled` settings. It does not operate Rocket League’s owned inventory or native saved presets. Its catalog is useful for selecting supported product templates, but it is not evidence that an item is owned, unlocked, rendered, or visible to other players. The source itself says the actual scene appearance still needs game verification.

Compatibility is unresolved for this installed setup. Rocket League’s April 28, 2026 EAC announcement says EAC is required for PC online play and community mods do not run while it is enabled; its Code of Conduct describes compliant third-party mod use in training/offline/LAN/replay contexts with EAC off. BakkesMod’s maintainer posted on April 28 that BakkesMod would not work on game versions released that day or later. That is a maintainer support statement, not a measured property of this installation. The project status records offline game evidence on October 27, and local Steam metadata is consistent with the post-EAC v2.78 release, but the tested run does not identify its Rocket League build ID, BakkesMod runtime version, plugin hash, or EAC launch state. Do not label the adapter unavailable or compatible for the installed runtime until those identities are joined; garage rendering and apply remain unverified.

## What the sources establish

### Native Rocket League garage and account items

Psyonix’s v1.22 release notes documented separate “Equip to Blue” and “Equip to Orange” loadouts and up to ten named car presets, plus a primary-color palette for Blue/Orange cars. This is historical documentation of the stock Garage model; no current UI session was inspected. The SDK also declares current-loadout, equipped-preset, team-specific loadout, and preset-equip surfaces, but declarations alone do not prove their present runtime behavior. [Rocket League v1.22 notes](https://www.rocketleague.com/news/patch-notes-v1-22)

Epic Support describes inventory as account/platform data that synchronizes across linked platforms, with exceptions. Certified items track stats when equipped; for example, Victor tracks online wins. [Inventory sharing and sync](https://www.epicgames.com/help/en-US/rocket-league-c5719357623323/basics-c7261959845275/why-am-i-missing-rocket-league-inventory-across-my-accounts-a5720119540763), [Certified Items](https://www.epicgames.com/help/en-US/c-Category_RocketLeague/c-RocketLeague_Gameplay/what-are-certified-items-in-rocket-league-a000084398?lang=en-US)

### BakkesMod and compatibility policy

Rocket League’s Apr 28, 2026 article says EAC is required for PC online play and community mods do not run while EAC is enabled. Its Code of Conduct describes third-party mod use in training/offline/LAN/replay contexts with EAC off, subject to its rules. BakkesMod maintainer Bakkes posted on Apr 28, 2026 that the mod would not work on game versions released that day or later. The local project also records offline game evidence on Oct 27, but the exact runtime tuple and EAC launch state for that test are not saved in the reviewed status. These sources therefore establish the policy boundary and a maintainer support statement; they do not settle whether the currently installed host works in the tested offline configuration. [EAC announcement](https://www.rocketleague.com/news/easy-anti-cheat-comes-to-rocket-league-on-pc-today?lang=en), [Third-Party Mods policy](https://www.rocketleague.com/code-of-conduct), [BakkesMod maintainer post, Apr 28, 2026](https://bakk.es/articles/bakkesmod-eac.html)

### Local project implementation

- `plugin/CMakeLists.txt:26-29` pins the public BakkesMod SDK tarball to `479e8f571cf554b25f4eeb64d611dec4133edcaf` and a SHA-256. That source pin is not a claim about an installed SDK/DLL or compatibility with current Rocket League.
- `plugin/src/CareerUI.cpp:517-608` presents 15 categories, substring name search, 18 products per page, and a fixed 19-entry paint list. Bodies (slot 0), banners (16), avatar borders (20), and titles (21) are browse-only. Eleven other slots can enter the local design draft when their IDs are within the code limit. The UI has no product thumbnail, rendered car preview, certification filter, or owned-item indicator. Selecting a tile changes the draft; Apply is a separate action.
- `plugin/src/MyCareerTraining.cpp:1504-1524` scans `ItemsWrapper::GetAllProducts()` in batches of 200 and records product ID, slot, label, and `IsPaintable()`. It does not call `GetOwnedProducts()` or `GetCachedUnlockedProducts()`, inspect item attributes, or record an online product instance ID. SDK declarations distinguish `GetAllProducts()` from those owned/unlocked calls (`ItemsWrapper.h:42-55`). **Inference from this call path:** the displayed rows are a local game-build product catalog, not a per-account ownership list. The exact catalog contents depend on the game build.
- `plugin/include/CosmeticDesignCode.h:16-80` limits the current wire format to product IDs through 65535, eleven supported slots, and item/paint data plus optional primary/secondary RGB. It explicitly stores no body, entitlement, inventory, or physics data. It cannot identify an owned certified item instance.
- The UI’s “Override local car colors” controls primary/accent RGB, not separate Blue/Orange saved presets or Rocket League’s team-color selection (`CareerUI.cpp:584-595`).
- `plugin/src/MyCareerTraining.cpp:1572-1605` checks the two item-mod cvars, validates each requested product against the scanned local catalog and paintability, then writes the encoded design. It reports that scene appearance still needs game verification. The native movie action route has an additional owned-offline and not-in-game/not-in-replay gate (`MyCareerTraining.cpp:791-796`).
- `plugin/include/CosmeticOverrideState.h:15-64` snapshots both cvars before first write, verifies readback, and retains pending restoration until both original values read back. Restore is retried on scope loss/tick exception and called on unload (`MyCareerTraining.cpp:1381-1387,1420-1426,1623-1636,258-286`). That proves cvar restoration logic, not that the native loadout or displayed car was restored.
- The native appearance menu is explicitly labeled local and says it does not change inventory or establish match visibility (`plugin/include/NativeCareerLayout.h:2768-2791,2853-2866`). The browser garage visual specification is a design document, not implementation or gameplay evidence (`docs/BROWSER_GARAGE_VISUAL_SPEC.md:1,113-175`).

### SDK surfaces that could support later work

At the pinned SDK declaration level, `ItemsWrapper.h:42-63` exposes product catalog, owned/cached-unlocked items, current loadout, and paint database access. `ProductWrapper.h:25-44` exposes paintability, equipability, attributes, thumbnails, and ID. `OnlineProductWrapper.h:21-38` exposes attributes and a product-instance ID. `ProductAttribute_CertifiedWrapper.h:13-15` exposes certification stat identifiers/values. `LoadoutWrapper.h:14-20` exposes loadout item IDs and primary/accent paint-color IDs; `LoadoutSaveWrapper.h:14-25` and `LoadoutSetWrapper.h:21-26` expose preset read/equip and product-by-instance-ID/team operations. These interfaces make read-only inventory inspection, richer previews, and native owned-preset handling plausible candidates. They do **not** establish that those operations work on current builds, that setters synchronize to Epic services, or that arbitrary product templates are equippable/owned. The current plugin does not call them.

## Capability matrix

| Capability | Current behavior | Safe description |
|---|---|---|
| Catalog discovery/search | Local `GetAllProducts` scan; slot and case-insensitive name filter; 18/page | “Browse product templates found by this game build.” Not “all owned skins.” |
| Preview | Text labels and a draft selection; no thumbnail/3D item preview path found | Call it selection or local-design draft. Rendered appearance is unverified. |
| Categories | 15 shown; 11 supported item-code slots; 4 catalog-only slots; bodies not equippable through this format | Do not imply all categories apply. |
| Paint | Fixed 19-value menu; apply checks `IsPaintable`; code stores paint index | Does not prove every paint variant exists for every item or that it renders. SDK paint DB could improve labels/catalog, pending runtime validation. |
| Certification | No certification/attribute or instance data in current scan/design | Certified-stat variant is not represented. SDK exposes a separate attribute path; do not simulate or claim stat changes. |
| Team colors | Custom RGB primary/accent local override | Not equivalent to native blue/orange team-specific presets. |
| Apply/restore | Writes and restores two BakkesMod cvars; item code is client-side design data | No account entitlement, grant, server inventory, saved native preset, or online-visibility claim. |

## Six-part action contracts

Each row is a future-facing contract, not an authorization to execute it.

| Action | 1. Gate | 2. Operation | 3. Authority/data | 4. Success evidence | 5. Failure/recovery | 6. Claim boundary |
|---|---|---|---|---|---|---|
| Browse/refresh | Owned offline session; supported runtime; valid item wrapper | Scan `GetAllProducts`, then filter locally | Product templates, slot/name/paintability only | Scan complete and selected row matches slot/ID | Null/empty/partial scan stays unavailable; offer retry | “Catalog row found,” never “owned/unlocked.” |
| Select/preview | Row is in current catalog; slot/code range supported | Change draft only; preview is a separate read-only render path if one is built | Product template ID, not account instance | Selection marker; a real preview requires verified in-game render evidence | Stale catalog, unsupported slot, ID >65535, missing image shows unavailable | Do not call a draft a visual or gameplay preview. |
| Paint/colors | Product is paintable; user explicitly edits local design | Choose paint or RGB draft; keep per-team colors separate if native presets are targeted | Existing design format: paint index and primary/accent RGB | UI readback; visual result needs separate offline capture | Reject non-paintable/unknown paint; keep prior draft | No certified stat, team preset, or rendered-color claim from RGB values alone. |
| Apply local design | Explicit Apply; owned offline scope; compatible host/cvars present; no online/EAC session | Validate item against fresh catalog; snapshot then write local cvars | Local BakkesMod override | Exact cvar readback plus independent offline scene verification | Roll back; expose pending restore; disable action if runtime unsupported | No unlock/grant, account write, saved preset, or online visibility claim. |
| Restore | Snapshot pending; supported cvars available | Restore code and enabled flag, then read both back | Captured local cvar baseline | Both values exactly match baseline | Preserve pending state and retry; tell user restore is incomplete | Cvar restoration does not prove native Garage preset or scene appearance. |
| Native owned-preset apply (future) | Explicit user selection and consent; verified owned instance; snapshot current per-team preset | Use native preset/loadout API only after safe semantics and runtime support are established | Online product instance and native saved preset, distinct from local item code | Read current preset/loadout back for each team; independently inspect Garage | Cancel before write on ownership mismatch; restore captured preset if changed | No granting, entitlement change, cross-platform sync, or other-player visibility claim. |

## Failure cases and prioritized candidates

1. **Unresolved host compatibility:** cvar existence is not proof that the plugin host works on the installed build. Keep runtime compatibility unknown until the tested executable, Steam build ID, BakkesMod version, plugin hash, and EAC launch state are tied to the same session; keep account customization in the native Garage.
2. **Catalog-versus-inventory confusion:** a product ID can be present in the product database without an owned instance. Keep catalog and owned-item views explicitly separate.
3. **Preview/apply conflation:** current selection is only a draft; cvar success only confirms the setting readback. Require visual evidence before showing “previewed” or “equipped.”
4. **Unsupported code rows:** bodies and catalog-only categories, out-of-range IDs, stale scans, or unpaintable items must stay browse-only/refused.
5. **Restore failure:** preserve the pending marker and original snapshot; never report success until both settings match. Do not claim native preset restoration.
6. **Certification/team variants:** generic product IDs and primary/accent RGB omit certified instance stats and the stock garage’s Blue/Orange preset split.

**Priority:** (1) keep account customization in Rocket League’s native Garage; (2) resolve the exact offline host/runtime tuple before enabling any cvar-based adapter; (3) if that host is confirmed for the installed build, implement local catalog and thumbnail preview as clearly labeled, read-only browsing before enabling local Apply; (4) add a separate owned-instance inspection mode using SDK owned-product/instance APIs; (5) consider native preset application only with explicit consent, per-team snapshot/restore, and verified current SDK/game behavior. Never offer grants or unlocks.

**Future acceptance:** visually verify each item/paint preview only in an allowed offline runtime; show owned status only from an owned-instance API; preserve separate Blue/Orange preset state; confirm Apply affects only the intended local preview or native preset; restore exact prior state after success, rejection, scope loss, and unload; make unsupported runtime/slot/paint states visibly unavailable; leave inventory entitlement and online visibility explicitly unclaimed.
