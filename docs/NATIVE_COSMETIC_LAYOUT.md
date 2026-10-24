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
```

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
    case NativeCosmeticRequestKind::Apply:
        // Copy request.draft[0 .. draftCount). Slots are ascending.
        // Revalidate with validateCosmeticDesign and the live catalog, then
        // queue LocalRequest::ApplyCosmetics. This request has no RGB fields;
        // keep the plugin's current override_colors, primary, and secondary.
        break;
    case NativeCosmeticRequestKind::Restore:
        // queue LocalRequest::RestoreCosmetics
        break;
    default:
        break;
    }
}
```

Use the effect from `choose` or `select`, then rebuild the context from plugin state before the next `publish`. An accepted `select` invalidates the movie generation. The next `publish` shows the layout's new page. Do not call `open` again for that click; `open` returns to the root page.

`SelectItem` moves the layout to paints. Paint buttons are offered only after the draft's product for that slot matches the selection and the product is paintable. `Apply` carries the validated draft snapshot so a later draft cannot reuse the old click. Root still revalidates that snapshot with `validateCosmeticDesign` and the installed catalog before writing cvars.

## Pages

Garage → Local appearance (`garage.appearance`) → category (`cosmetic.slot.<slot>`) → item (`cosmetic.item.<page>.<offset>`) → paints (`cosmetic.paint.<0..18>`).

Equipable categories are slots `1, 2, 3, 4, 5, 7, 12, 13, 14, 15, 18`. Bodies, banners, borders, and titles are named in the body and omitted from controls. Product ids outside `1..65535`, empty names, and duplicate slot/id rows are omitted. Paint codes are the nineteen named finishes `0..18` from the existing garage list. There is no RGB field and no search box.

Each server page lists `NativeCareerLayout::kCosmeticItemsPerPage` (16) items, plus previous, next, clear, and back as needed. That stays within the 24-control movie cap. The movie draws seven buttons at a time from the published list; previous/next are how later products stay reachable. The catalog walk is not capped at 24 or 64.

`cosmetic.apply`, `cosmetic.restore`, and `cosmetic.clear` are on the appearance and category pages as labeled. Back remains `nav.back`. Clear removes one draft slot. Apply is disabled while the catalog is scanning, item mod is unavailable, a restore is pending, or the draft has no valid row. Restore is enabled when item mod is available and the catalog is not scanning.

## Evidence

`plugin/tests/native_cosmetic_layout_tests.cpp` covers category paging past the first 64 items, product `65535`, omitted out-of-range ids and unsupported slots, typed select/paint/clear/apply/restore requests, non-paintable paint refusal, empty and scanning catalogs, unavailable item mod, stale catalog or draft clicks that keep the same label, duplicate clicks, foreign scope, forged bridge actions, Unicode names, and unchanged stock-garage and bot-preset routes.

`plugin/tests/native_movie_protocol_tests.cpp` covers the five-field command, rejection of a caller `product_id`, a paintability change with the same label, a stale generation, a duplicate click, and a published document that has no action, payload, or item-mod cvar. `plugin/tests/native_career_layout_tests.cpp` still covers the stock menu and now requires the local-appearance control to be navigation rather than a bridge action.

Passing these tests does not show that Rocket League rendered the menu or that a design appeared in a match.

## Plugin connection

`MyCareerTraining` now supplies this context to `NativeMovieHost` and handles
the typed local requests. It caches the immutable native catalog until the game
catalog snapshot changes. The native menu and existing plugin window share a
locked preferences/draft state; the native callback cannot race a garage edit.
Apply retains the existing color settings and enters the same bounded local
queue as the plugin window. Queue overflow is a refusal. Execution revalidates
the design and live catalog before writing the two existing item-mod cvars;
scope loss and unload still use `CosmeticOverrideState` restoration.

This connection remains behind the default-off native movie trial. Compiling it
does not establish that the game displays the selected items.
