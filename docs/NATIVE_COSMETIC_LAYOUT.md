# Native local appearance

The authored menu can edit this machine's cosmetic draft. That draft is not a bot preset and it is not `state.garage`. `NativeCareerLayout` still keeps **Your car** on the game's garage route and still dispatches bot presets with bridge `loadout`.

Local appearance reads a `NativeCosmeticContext` supplied by the plugin on every `open`, `view`, `choose`, `publish`, and `select`. The context is not stored. Movie JSON stays five fields: `protocol`, `session`, `generation`, `revision`, `control`. A click resolves the retained server choice and is checked against the context passed into that call. `runtime_verified` and `production_ready` stay false.

No game was launched to produce this menu. An in-range product id is not ownership and not evidence that the item is visible.

## Context the plugin fills

`plugin/include/NativeCosmeticContext.h`

```cpp
struct NativeCosmeticProduct { int id; int slot; std::string name; bool paintable; };
struct NativeCosmeticSelection { int productId; int paint; }; // paint 0 is original

struct NativeCosmeticContext {
    std::shared_ptr<const std::vector<NativeCosmeticProduct>> catalog; // null means empty
    bool available;            // MctRuntime.itemModAvailable
    bool scanning;             // scanningProducts_
    std::map<int, NativeCosmeticSelection> draft; // cosmeticItems_: slot -> product, paint
    std::string message;       // MctRuntime.cosmeticMessage, display only
    bool restorationPending;   // cosmeticOverride_.restorationPending()
    bool overrideColors;       // overrideColors_
    std::array<float, 3> primary;   // primaryColor_, each channel finite in [0,1]
    std::array<float, 3> secondary; // secondaryColor_, each channel finite in [0,1]
};
```

```cpp
NativeCosmeticContext cosmetics;
cosmetics.available = runtime.itemModAvailable;
cosmetics.scanning = scanningProducts_;
cosmetics.restorationPending = cosmeticOverride_.restorationPending();
cosmetics.message = runtime.cosmeticMessage;
std::vector<NativeCosmeticProduct> products;
products.reserve(runtime.products->size());
for (const MctProduct& product : *runtime.products)
    products.push_back({product.id, product.slot, product.name, product.paintable});
cosmetics.catalog = std::make_shared<const std::vector<NativeCosmeticProduct>>(std::move(products));
for (const auto& item : cosmeticItems_)
    cosmetics.draft.emplace(item.first, NativeCosmeticSelection{item.second.first, item.second.second});
cosmetics.overrideColors = overrideColors_;
cosmetics.primary = {primaryColor_[0], primaryColor_[1], primaryColor_[2]};
cosmetics.secondary = {secondaryColor_[0], secondaryColor_[1], secondaryColor_[2]};
```

Copy the color fields inside the existing `preferencesMutex_` lock, beside the draft. Supply only finite channels in `[0,1]`. A channel outside that range disables color editing and Apply. The plugin's current default blue and orange are not palette entries, so the menu shows them as `Custom` until the user picks a named color.

Pass that object into both publication and selection:

```cpp
protocol.open(scope, state, cosmetics);
const Json wire = protocol.publish(scope, state, now, cosmetics);
const CareerLayoutEffect effect = protocol.select(message, scope, state, true, cosmetics);
```

`NativeCareerLayout::view` and `choose` take the same trailing argument. Existing call sites keep compiling: the default context is empty.

## Effect root handles

Accepted local edits use `CareerLayoutEffectKind::LocalCosmetic`. `action` and `payload` stay empty. This is not a bridge command and it does not require original-click consumption. `supportedAction` does not grow.

```cpp
if (effect.kind == CareerLayoutEffectKind::LocalCosmetic) {
    const NativeCosmeticRequest& request = effect.cosmetic;
    switch (request.kind) {
    case NativeCosmeticRequestKind::SelectItem:
        // request.slot, request.productId, request.paint == 0, request.paintable
        cosmeticItems_[request.slot] = {request.productId, 0};
        break;
    case NativeCosmeticRequestKind::SelectPaint:
        // Apply only if cosmeticItems_[slot].first == request.productId,
        // the live product is paintable, and request.paint is 0..18.
        cosmeticItems_[request.slot].second = request.paint;
        break;
    case NativeCosmeticRequestKind::ClearSlot:
        // Erase only this slot, and only if product id and paint still match.
        cosmeticItems_.erase(request.slot);
        break;
    case NativeCosmeticRequestKind::SetColorOverride:
        // Desired new value. It is not itself an Apply.
        overrideColors_ = request.overrideColors;
        break;
    case NativeCosmeticRequestKind::SelectPrimaryColor: {
        // Palette index only. Do not read RGB from the movie command.
        const auto color = nativeCosmeticPaletteRgb(request.paletteIndex);
        primaryColor_[0] = color[0];
        primaryColor_[1] = color[1];
        primaryColor_[2] = color[2];
        break;
    }
    case NativeCosmeticRequestKind::SelectSecondaryColor: {
        const auto color = nativeCosmeticPaletteRgb(request.paletteIndex);
        secondaryColor_[0] = color[0];
        secondaryColor_[1] = color[1];
        secondaryColor_[2] = color[2];
        break;
    }
    case NativeCosmeticRequestKind::Apply: {
        // Copy request.draft[0 .. draftCount). Slots are ascending and may be empty.
        // Use the color snapshot on the request, not the live member arrays:
        // a newer color edit must not reuse this click.
        Json items = Json::array();
        for (int index = 0; index < request.draftCount; ++index) {
            const auto& item = request.draft[static_cast<std::size_t>(index)];
            items.push_back({{"slot", item.slot}, {"product_id", item.productId}, {"paint", item.paint}});
        }
        Json payload = {{"items", std::move(items)}, {"override_colors", request.overrideColors},
            {"primary", {request.primary[0], request.primary[1], request.primary[2]}},
            {"secondary", {request.secondary[0], request.secondary[1], request.secondary[2]}}};
        validateCosmeticDesign(payload);
        queueLocal(LocalRequest::ApplyCosmetics, std::move(payload));
        break;
    }
    case NativeCosmeticRequestKind::Restore:
        // queue LocalRequest::RestoreCosmetics
        break;
    default:
        break;
    }
}
```

Use the effect from `choose` or `select`, then rebuild the context from plugin state before the next `publish`. An accepted `select` invalidates the movie generation. The next `publish` shows the layout's new page. Do not call `open` again for that click; `open` returns to the root page.

`SelectItem` moves the layout to paints. Paint buttons are offered only after the draft's product for that slot matches the selection and the product is paintable. `Apply` carries the validated draft snapshot and the color snapshot, so a later draft or color cannot reuse the old click. Root still revalidates that snapshot with `validateCosmeticDesign` and the installed catalog before writing cvars. `validateCosmeticDesign` quantizes finite `[0,1]` channels; the menu compares the host floats exactly and does not quantize them first.

`SetColorOverride`, `SelectPrimaryColor`, and `SelectSecondaryColor` only change the in-memory color draft. They do not queue `ApplyCosmetics`. Call `savePreferences()` after those edits, as the existing item edits do. `nativeCosmeticRequestCurrent` already runs before the switch and rejects an unknown kind, so the three new kinds must be handled there or they fail closed.

## Pages

Garage → Local appearance (`garage.appearance`) → category (`cosmetic.slot.<slot>`) → item (`cosmetic.item.<page>.<offset>`) → paints (`cosmetic.paint.<0..18>`).

Local appearance also opens Colors (`cosmetic.colors`) → Primary color (`cosmetic.primary.<index>`) or Accent color (`cosmetic.accent.<index>`). Accent is the plugin's secondary color. The palette has 16 named colors, index `0..15`, and index 0 is White rather than an unused value. A host color that is not an exact palette float is labeled `Custom`. There is no text field and the movie cannot send RGB.

Equipable categories are slots `1, 2, 3, 4, 5, 7, 12, 13, 14, 15, 18`. Bodies, banners, borders, and titles are named in the body and omitted from controls. Product ids outside `1..65535`, empty names, and duplicate slot/id rows are omitted. Paint codes are the nineteen named finishes `0..18` from the existing garage list. There is no search box.

Each server page lists `NativeCareerLayout::kCosmeticItemsPerPage` (16) items, plus previous, next, clear, and back as needed. That stays within the 24-control movie cap. The movie draws seven buttons at a time from the published list; previous/next are how later products stay reachable. The catalog walk is not capped at 24 or 64.

`cosmetic.apply`, `cosmetic.restore`, and `cosmetic.clear` are on the appearance and category pages as labeled. The color page uses `cosmetic.colors.override` with the labels `Turn on color override` and `Turn off color override`. Back remains `nav.back`. Clear removes one draft slot. Apply is disabled while the catalog is scanning, item mod is unavailable, a restore is pending, either saved color is nonfinite or outside `[0,1]`, or color override is off and the draft has no valid row. Apply is enabled for a color-only design when override is on, both colors are valid, item mod is available, the catalog is not scanning, and no restore is pending; its item snapshot is then empty. Restore is enabled when item mod is available and the catalog is not scanning. Color choices are disabled while scanning, while a restore is pending, or while the saved colors are unusable. They stay available when item mod itself is unavailable, because choosing a color does not apply it.

## Evidence

`plugin/tests/native_cosmetic_layout_tests.cpp` covers category paging past the first 64 items, product `65535`, omitted out-of-range ids and unsupported slots, typed select/paint/clear/apply/restore requests, non-paintable paint refusal, empty and scanning catalogs, unavailable item mod, stale catalog or draft clicks that keep the same label, duplicate clicks, foreign scope, forged bridge actions, Unicode names, and unchanged stock-garage and bot-preset routes. It also covers primary and accent palette selection, the override toggle, a color-only Apply, an item draft kept beside a color edit, a same-label Apply refused after the color changes, and malformed palette indexes, unused fields, and nonfinite colors.

`plugin/tests/native_movie_protocol_tests.cpp` covers the five-field command, rejection of a caller `product_id` or a caller `primary` color, a paintability change with the same label, a stale generation, a duplicate click, and a published document that has no action, payload, RGB snapshot, or item-mod cvar. `plugin/tests/native_career_layout_tests.cpp` still covers the stock menu, requires the local-appearance control to be navigation rather than a bridge action, and returns from Colors to the same garage routes.

Passing these tests does not show that Rocket League rendered the menu or that a design appeared in a match.

## Plugin connection

`MyCareerTraining` now supplies this context to `NativeMovieHost` and handles
the typed local requests. It caches the immutable native catalog until the game
catalog snapshot changes. The native menu and existing plugin window share a
locked preferences/draft state; the native callback cannot race a garage edit.
Apply must now take `override_colors`, `primary`, and `secondary` from the
request snapshot above, including a color-only design whose `items` array is
empty. Selecting a palette color or toggling the override only updates the
locked preference fields and does not enter that queue. Queue overflow is a
refusal. Execution revalidates the design and live catalog before writing the
two existing item-mod cvars; scope loss and unload still use
`CosmeticOverrideState` restoration.

This connection remains behind the default-off native movie trial. Compiling it
does not establish that the game displays the selected items.
