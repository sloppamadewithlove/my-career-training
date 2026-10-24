#pragma once

#include <array>
#include <cstdint>
#include <map>
#include <memory>
#include <string>
#include <vector>

namespace mct {

// Typed local cosmetic catalog for the authored native menu.
// The plugin fills this from MctRuntime.products and its in-memory draft.
// It is not read from worker JSON, movie JSON, or a bridge payload.
// An in-range product id is not ownership and not evidence the item is visible.

inline constexpr int kNativeCosmeticProductMin = 1;
inline constexpr int kNativeCosmeticProductMax = 65535;
inline constexpr int kNativeCosmeticPaintMax = 18;
inline constexpr int kNativeCosmeticDraftCap = 11;

struct NativeCosmeticProduct {
    int id = 0;
    int slot = 0;
    std::string name;
    bool paintable = false;
};

// One draft override. `paint` 0 is the item's original finish.
struct NativeCosmeticSelection {
    int productId = 0;
    int paint = 0;
};

// One validated draft row retained on an Apply request.
// Slot order is ascending. `paintable` is the catalog fact at validation time.
struct NativeCosmeticDraftEntry {
    int slot = 0;
    int productId = 0;
    int paint = 0;
    bool paintable = false;

    friend bool operator==(const NativeCosmeticDraftEntry& left, const NativeCosmeticDraftEntry& right) {
        return left.slot == right.slot && left.productId == right.productId &&
            left.paint == right.paint && left.paintable == right.paintable;
    }
    friend bool operator!=(const NativeCosmeticDraftEntry& left, const NativeCosmeticDraftEntry& right) {
        return !(left == right);
    }
};

// Closed local request. Scalars only: no action name, console text, or cvar string.
// `restorationPending` is meaningful for Restore. `draft` is meaningful for Apply.
// `name` is not stored here; the menu binds names on the choice stamp instead.
enum class NativeCosmeticRequestKind {
    None = 0,
    SelectItem,
    SelectPaint,
    ClearSlot,
    Apply,
    Restore
};

struct NativeCosmeticRequest {
    NativeCosmeticRequestKind kind = NativeCosmeticRequestKind::None;
    int slot = 0;
    int productId = 0;
    int paint = 0;
    bool paintable = false;
    bool restorationPending = false;
    std::array<NativeCosmeticDraftEntry, kNativeCosmeticDraftCap> draft{};
    int draftCount = 0;

    friend bool operator==(const NativeCosmeticRequest& left, const NativeCosmeticRequest& right) {
        if (left.kind != right.kind || left.slot != right.slot || left.productId != right.productId ||
            left.paint != right.paint || left.paintable != right.paintable ||
            left.restorationPending != right.restorationPending || left.draftCount != right.draftCount)
            return false;
        for (int index = 0; index < kNativeCosmeticDraftCap; ++index)
            if (left.draft[static_cast<std::size_t>(index)] != right.draft[static_cast<std::size_t>(index)])
                return false;
        return true;
    }
};

struct NativeCosmeticCategory {
    int slot;
    const char* label;
};

// Equipable slots only. Bodies (0), banners (16), borders (20), and titles (21)
// stay off these controls. They can be browsed in the ImGui garage.
inline constexpr NativeCosmeticCategory kNativeCosmeticCategories[] = {
    {1, "Decals"},
    {2, "Wheels"},
    {3, "Boosts"},
    {4, "Antennas"},
    {5, "Toppers"},
    {7, "Primary paint finish"},
    {12, "Accent paint finish"},
    {13, "Engine audio"},
    {14, "Trails"},
    {15, "Goal explosions"},
    {18, "Anthems"},
};

inline constexpr const char* kNativeCosmeticPaintNames[] = {
    "Original", "Crimson", "Lime", "Black", "Sky blue", "Cobalt", "Burnt sienna",
    "Forest green", "Purple", "Pink", "Orange", "Grey", "Titanium white", "Saffron",
    "Gold", "Rose gold", "White gold", "Onyx", "Platinum"
};

inline constexpr int kNativeCosmeticCategoryCount =
    static_cast<int>(sizeof(kNativeCosmeticCategories) / sizeof(kNativeCosmeticCategories[0]));
inline constexpr int kNativeCosmeticPaintCount =
    static_cast<int>(sizeof(kNativeCosmeticPaintNames) / sizeof(kNativeCosmeticPaintNames[0]));

constexpr bool nativeCosmeticSlotEquipable(int slot) {
    switch (slot) {
    case 1: case 2: case 3: case 4: case 5:
    case 7: case 12: case 13: case 14: case 15: case 18:
        return true;
    default:
        return false;
    }
}

constexpr bool nativeCosmeticCategoriesCoverEquipableSlots() {
    int equipable = 0;
    for (int slot = 0; slot <= 31; ++slot)
        if (nativeCosmeticSlotEquipable(slot)) ++equipable;
    if (equipable != kNativeCosmeticCategoryCount || equipable != kNativeCosmeticDraftCap) return false;
    for (const auto& category : kNativeCosmeticCategories)
        if (!nativeCosmeticSlotEquipable(category.slot)) return false;
    return kNativeCosmeticPaintCount == kNativeCosmeticPaintMax + 1;
}

static_assert(nativeCosmeticCategoriesCoverEquipableSlots());
static_assert(kNativeCosmeticProductMax == 65535);

inline const char* nativeCosmeticCategoryLabel(int slot) {
    for (const auto& category : kNativeCosmeticCategories)
        if (category.slot == slot) return category.label;
    return "Item";
}

inline const char* nativeCosmeticPaintName(int paint) {
    if (paint < 0 || paint >= kNativeCosmeticPaintCount) return "Paint";
    return kNativeCosmeticPaintNames[paint];
}

inline bool nativeCosmeticListable(const NativeCosmeticProduct& product) {
    return nativeCosmeticSlotEquipable(product.slot) &&
        product.id >= kNativeCosmeticProductMin && product.id <= kNativeCosmeticProductMax &&
        !product.name.empty();
}

inline const NativeCosmeticProduct* findNativeCosmeticProduct(const std::vector<NativeCosmeticProduct>& catalog,
                                                              int slot, int productId) {
    if (!nativeCosmeticSlotEquipable(slot) || productId < kNativeCosmeticProductMin || productId > kNativeCosmeticProductMax)
        return nullptr;
    for (const auto& product : catalog)
        if (product.slot == slot && product.id == productId && nativeCosmeticListable(product)) return &product;
    return nullptr;
}

// Entries the menu is willing to put on Apply. Invalid rows are omitted.
// Root still revalidates through validateCosmeticDesign and the live catalog.
inline std::vector<NativeCosmeticDraftEntry> nativeCosmeticValidatedDraft(const struct NativeCosmeticContext& context);

struct NativeCosmeticContext {
    // Null is an empty catalog. The pointed-to vector is immutable.
    std::shared_ptr<const std::vector<NativeCosmeticProduct>> catalog;
    bool available = false;
    bool scanning = false;
    std::map<int, NativeCosmeticSelection> draft;
    std::string message;
    bool restorationPending = false;
};

inline const std::vector<NativeCosmeticProduct>& nativeCosmeticCatalog(const NativeCosmeticContext& context) {
    static const std::vector<NativeCosmeticProduct> empty;
    return context.catalog ? *context.catalog : empty;
}

inline std::vector<NativeCosmeticDraftEntry> nativeCosmeticValidatedDraft(const NativeCosmeticContext& context) {
    std::vector<NativeCosmeticDraftEntry> entries;
    const auto& catalog = nativeCosmeticCatalog(context);
    for (const auto& item : context.draft) {
        if (!nativeCosmeticSlotEquipable(item.first)) continue;
        if (item.second.paint < 0 || item.second.paint > kNativeCosmeticPaintMax) continue;
        const auto* product = findNativeCosmeticProduct(catalog, item.first, item.second.productId);
        if (!product) continue;
        if (item.second.paint != 0 && !product->paintable) continue;
        NativeCosmeticDraftEntry entry;
        entry.slot = item.first;
        entry.productId = product->id;
        entry.paint = product->paintable ? item.second.paint : 0;
        entry.paintable = product->paintable;
        entries.push_back(entry);
        if (static_cast<int>(entries.size()) == kNativeCosmeticDraftCap) break;
    }
    return entries;
}

inline bool nativeCosmeticRequestTailClear(const NativeCosmeticRequest& request) {
    if (request.draftCount < 0 || request.draftCount > kNativeCosmeticDraftCap) return false;
    for (int index = request.draftCount; index < kNativeCosmeticDraftCap; ++index)
        if (request.draft[static_cast<std::size_t>(index)] != NativeCosmeticDraftEntry{}) return false;
    return true;
}

// True when `request` still describes the catalog and draft the plugin just supplied.
// A movie click never supplies these fields; the menu rebuilds them from `context`.
inline bool nativeCosmeticRequestCurrent(const NativeCosmeticRequest& request, const NativeCosmeticContext& context) {
    if (!nativeCosmeticRequestTailClear(request)) return false;
    const auto& catalog = nativeCosmeticCatalog(context);
    switch (request.kind) {
    case NativeCosmeticRequestKind::None:
        return request.slot == 0 && request.productId == 0 && request.paint == 0 &&
            !request.paintable && !request.restorationPending && request.draftCount == 0;
    case NativeCosmeticRequestKind::SelectItem: {
        if (context.scanning || context.restorationPending || request.restorationPending) return false;
        if (request.paint != 0 || request.draftCount != 0) return false;
        const auto* product = findNativeCosmeticProduct(catalog, request.slot, request.productId);
        return product && product->paintable == request.paintable;
    }
    case NativeCosmeticRequestKind::SelectPaint: {
        if (context.scanning || context.restorationPending || request.restorationPending || request.draftCount != 0)
            return false;
        if (request.paint < 0 || request.paint > kNativeCosmeticPaintMax || !request.paintable) return false;
        const auto* product = findNativeCosmeticProduct(catalog, request.slot, request.productId);
        if (!product || !product->paintable) return false;
        const auto draft = context.draft.find(request.slot);
        if (draft == context.draft.end() || draft->second.productId != request.productId) return false;
        return draft->second.paint >= 0 && draft->second.paint <= kNativeCosmeticPaintMax;
    }
    case NativeCosmeticRequestKind::ClearSlot: {
        if (context.scanning || context.restorationPending || request.restorationPending || request.draftCount != 0)
            return false;
        if (!nativeCosmeticSlotEquipable(request.slot) || request.paintable) return false;
        const auto draft = context.draft.find(request.slot);
        return draft != context.draft.end() && draft->second.productId == request.productId &&
            draft->second.paint == request.paint;
    }
    case NativeCosmeticRequestKind::Apply: {
        if (!context.available || context.scanning || context.restorationPending || request.restorationPending)
            return false;
        if (request.slot != 0 || request.productId != 0 || request.paint != 0 || request.paintable) return false;
        const auto live = nativeCosmeticValidatedDraft(context);
        if (live.empty() || request.draftCount != static_cast<int>(live.size())) return false;
        for (int index = 0; index < request.draftCount; ++index)
            if (request.draft[static_cast<std::size_t>(index)] != live[static_cast<std::size_t>(index)]) return false;
        return true;
    }
    case NativeCosmeticRequestKind::Restore:
        return context.available && !context.scanning && request.draftCount == 0 &&
            request.slot == 0 && request.productId == 0 && request.paint == 0 && !request.paintable &&
            request.restorationPending == context.restorationPending;
    }
    return false;
}

} // namespace mct
