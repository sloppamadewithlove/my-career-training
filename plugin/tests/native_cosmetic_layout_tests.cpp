#include "CosmeticDesignCode.h"
#include "NativeCareerLayout.h"
#include "NativeMovieProtocol.h"

#include <iostream>
#include <limits>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

using namespace mct;

static void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}

static CareerLayoutChoice findChoice(const CareerLayoutView& view, const std::string& id) {
    for (const auto& choice : view.choices)
        if (choice.id == id) return choice;
    throw std::runtime_error("Missing control: " + id);
}

static bool hasChoice(const CareerLayoutView& view, const std::string& id) {
    for (const auto& choice : view.choices)
        if (choice.id == id) return true;
    return false;
}

static CareerLayoutChoice findProduct(const CareerLayoutView& view, int productId) {
    for (const auto& choice : view.choices)
        if (choice.cosmetic.kind == NativeCosmeticRequestKind::SelectItem && choice.cosmetic.productId == productId)
            return choice;
    throw std::runtime_error("Missing product " + std::to_string(productId));
}

static bool hasProduct(const CareerLayoutView& view, int productId) {
    for (const auto& choice : view.choices)
        if (choice.cosmetic.kind == NativeCosmeticRequestKind::SelectItem && choice.cosmetic.productId == productId)
            return true;
    return false;
}

static void audit(const CareerLayoutView& view) {
    require(view.body.size() <= NativeCareerLayout::kMaxBody, "Body exceeds the bound");
    require(view.choices.size() <= NativeCareerLayout::kMaxChoices, "Too many controls");
    require(!view.productionGateEnabled && !view.nativeReplacementFinished, "Production or replacement flag set");
    for (const auto& choice : view.choices) {
        require(choice.action != "apply_cosmetics" && choice.action != "restore_cosmetics", "Cosmetic bridge action shown");
        if (choice.kind == CareerLayoutEffectKind::LocalCosmetic)
            require(choice.action.empty() && choice.payload.empty() && choice.stock == StockRoute::None,
                "Local cosmetic control carries a bridge action");
        if (!choice.action.empty()) require(NativeCareerLayout::supportedAction(choice.action), "Action is not supported");
    }
}

static bool validUtf8(const std::string& value) {
    for (std::size_t index = 0; index < value.size();) {
        const auto lead = static_cast<unsigned char>(value[index]);
        const std::size_t width = lead < 0x80 ? 1 : (lead >> 5) == 0x6 ? 2 : (lead >> 4) == 0xe ? 3 : (lead >> 3) == 0x1e ? 4 : 0;
        if (width == 0 || index + width > value.size()) return false;
        for (std::size_t extra = 1; extra < width; ++extra)
            if ((static_cast<unsigned char>(value[index + extra]) & 0xc0) != 0x80) return false;
        index += width;
    }
    return true;
}

static CareerLayoutScope ownedScope() {
    CareerLayoutScope scope;
    scope.owned = true;
    scope.offline = true;
    scope.fresh = true;
    scope.online = false;
    scope.nonce = "0123456789abcdef0123456789abcdef";
    scope.generation = 4;
    return scope;
}

static Json readyState() {
    return {{"protocol", 1}, {"offline", true}, {"bridge_session", "0123456789abcdef0123456789abcdef"},
        {"setup_required", false}, {"session", {{"state", "Career Ready"}, {"busy", false}}},
        {"career", {{"id", "career-a"}, {"team_name", "Orbit"}, {"pending_session", nullptr},
            {"squad", {"anchor"}}, {"recruits", {{"anchor", {{"name", "Anchor"}, {"role", "keeper"}}}}}}},
        {"garage", {{{"id", "stock-23"}, {"title", "Octane"}, {"car_id", 23}, {"primary_color", 27}, {"secondary_color", 0}}}}};
}

static CareerLayoutEffect choose(NativeCareerLayout& layout, const CareerLayoutChoice& choice,
                                 const CareerLayoutScope& scope, const Json& state,
                                 const NativeCosmeticContext& cosmetics, bool consumed = true) {
    auto effect = layout.choose(choice, scope, state, consumed, cosmetics);
    require(!effect.compatibilityGrant && !effect.consumesUnlistedCallback, "Effect claims a grant");
    require(effect.action.empty() || NativeCareerLayout::supportedAction(effect.action), "Effect action is not supported");
    if (effect.kind != CareerLayoutEffectKind::LocalCosmetic)
        require(effect.cosmetic.kind == NativeCosmeticRequestKind::None && effect.cosmetic.draftCount == 0,
            "Non-cosmetic effect carried a local cosmetic request");
    if (!effect.accepted)
        require(effect.action.empty() && effect.cosmetic.kind == NativeCosmeticRequestKind::None && effect.cosmetic.draftCount == 0,
            "Refused effect still dispatches");
    return effect;
}

static std::shared_ptr<const std::vector<NativeCosmeticProduct>> share(std::vector<NativeCosmeticProduct> products) {
    return std::make_shared<const std::vector<NativeCosmeticProduct>>(std::move(products));
}

static std::vector<NativeCosmeticProduct> sampleProducts() {
    std::vector<NativeCosmeticProduct> products;
    products.push_back({3, 2, "Halo", true});
    products.push_back({7, 2, "Matte wheel", false});
    for (int index = 0; index < 80; ++index)
        products.push_back({1000 + index, 2, "Bulk " + std::to_string(index), true});
    products.push_back({65535, 2, "Wide wheel", true});
    products.push_back({65536, 2, "Too wide", true});
    products.push_back({0, 2, "Zero", true});
    products.push_back({-1, 2, "Negative", true});
    products.push_back({4, 0, "Octane body", true});
    products.push_back({5, 6, "Unsupported slot", true});
    products.push_back({6, 16, "Banner", true});
    products.push_back({8, 20, "Border", true});
    products.push_back({9, 21, "Title", false});
    products.push_back({11, 1, "Stripes", true});
    std::string unicode;
    for (int index = 0; index < 40; ++index) unicode += u8"\u754c\U0001f680";
    products.push_back({12, 1, unicode, true});
    products.push_back({13, 2, "", true});
    products.push_back({3, 2, "Halo duplicate", true});
    return products;
}

static void openGarage(NativeCareerLayout& layout, const CareerLayoutScope& scope, const Json& state) {
    require(layout.open(scope, state), "Layout did not open");
    auto root = layout.view(scope, state);
    require(choose(layout, findChoice(root, NativeCareerLayout::kGarage), scope, state, {}).accepted, "Garage did not open");
}

static void openAppearance(NativeCareerLayout& layout, const CareerLayoutScope& scope, const Json& state,
                           const NativeCosmeticContext& cosmetics) {
    openGarage(layout, scope, state);
    auto garage = layout.view(scope, state, cosmetics);
    require(choose(layout, findChoice(garage, NativeCareerLayout::kAppearance), scope, state, cosmetics).accepted,
        "Local appearance did not open");
}

static int namedPalette(const char* name) {
    for (int index = 0; index < kNativeCosmeticPaletteCount; ++index)
        if (std::string(kNativeCosmeticPalette[index].name) == name) return index;
    throw std::runtime_error(std::string("Missing palette color ") + name);
}

static void checkColorEditor(const CareerLayoutScope& scope, const Json& state, NativeCosmeticContext cosmetics) {
    require(std::string(kNativeCosmeticPalette[0].name) == "White", "Palette index 0 must stay a real color");
    require(kNativeCosmeticPaletteCount >= 12 && kNativeCosmeticPaletteCount <= 16, "Palette size left the closed range");
    const int white = namedPalette("White");
    const int black = namedPalette("Black");
    const int red = namedPalette("Red");
    const int blue = namedPalette("Blue");
    const int orange = namedPalette("Orange");
    const int pink = namedPalette("Pink");
    cosmetics.message = "saved locally";
    cosmetics.draft.clear();
    cosmetics.draft[1] = {11, 0};
    cosmetics.primary = kNativeCosmeticPalette[white].rgb;
    cosmetics.secondary = kNativeCosmeticPalette[black].rgb;

    NativeCareerLayout layout;
    openAppearance(layout, scope, state, cosmetics);
    auto appearance = layout.view(scope, state, cosmetics);
    audit(appearance);
    require(appearance.body.find("Last cosmetic action: saved locally") != std::string::npos,
        "Cosmetic status prefix changed");
    require(appearance.body.find("Primary: White") != std::string::npos, "Current primary was hidden");
    require(hasChoice(appearance, "cosmetic.colors") && hasChoice(appearance, "cosmetic.slot.2") &&
        hasChoice(appearance, "cosmetic.apply"), "Appearance lost an existing route");
    auto kept = findChoice(appearance, "cosmetic.apply");
    require(kept.enabled && kept.cosmetic.draftCount == 1 && kept.cosmetic.draft[0].productId == 11 &&
        !kept.cosmetic.overrideColors && kept.cosmetic.primary == cosmetics.primary,
        "Item draft was dropped before a color edit");

    require(choose(layout, findChoice(appearance, "cosmetic.colors"), scope, state, cosmetics).accepted,
        "Colors page did not open");
    auto colors = layout.view(scope, state, cosmetics);
    audit(colors);
    require(colors.body.find("Choosing a color does not apply it.") != std::string::npos, "Apply warning missing");
    require(colors.body.find("Color override is off.") != std::string::npos, "Override state was hidden");
    auto enable = findChoice(colors, "cosmetic.colors.override");
    require(enable.label == "Turn on color override" && enable.enabled && enable.action.empty() && enable.payload.empty() &&
        enable.cosmetic.kind == NativeCosmeticRequestKind::SetColorOverride && enable.cosmetic.overrideColors &&
        enable.cosmetic.paletteIndex == -1 && enable.cosmetic.draftCount == 0, "Override toggle was not typed");
    auto turnedOn = choose(layout, enable, scope, state, cosmetics);
    require(turnedOn.accepted && turnedOn.kind == CareerLayoutEffectKind::LocalCosmetic &&
        turnedOn.cosmetic.kind == NativeCosmeticRequestKind::SetColorOverride && turnedOn.cosmetic.overrideColors &&
        turnedOn.action.empty() && turnedOn.payload.empty() && turnedOn.cosmetic.draftCount == 0,
        "Turning color override on was not a local request");
    require(cosmetics.draft[1].productId == 11, "Toggle cleared the item draft");
    cosmetics.overrideColors = true;
    require(choose(layout, enable, scope, state, cosmetics).refusal == CareerLayoutRefusal::StaleChoice,
        "Old override click stayed current");
    require(findChoice(layout.view(scope, state, cosmetics), "cosmetic.colors.override").label == "Turn off color override",
        "Disable label missing");

    require(choose(layout, findChoice(layout.view(scope, state, cosmetics), "cosmetic.colors.primary"),
        scope, state, cosmetics).accepted, "Primary page did not open");
    auto primary = layout.view(scope, state, cosmetics);
    audit(primary);
    require(primary.choices.size() > 7 && primary.choices.size() <= NativeCareerLayout::kMaxChoices,
        "Primary palette missed the movie paging bounds");
    require(primary.body.find("Current primary: White") != std::string::npos, "Current primary missing on its page");
    auto redChoice = findChoice(primary, "cosmetic.primary." + std::to_string(red));
    require(redChoice.label == "Red" && redChoice.cosmetic.kind == NativeCosmeticRequestKind::SelectPrimaryColor &&
        redChoice.cosmetic.paletteIndex == red && redChoice.cosmetic.primary == std::array<float, 3>{} &&
        redChoice.cosmetic.secondary == std::array<float, 3>{} && redChoice.cosmetic.draftCount == 0 &&
        redChoice.action.empty() && redChoice.payload.empty(), "Primary color carried RGB or the item draft");
    require(findChoice(primary, "cosmetic.primary." + std::to_string(white)).label == "Selected: White",
        "Current primary was not marked");
    cosmetics.primary = kNativeCosmeticPalette[blue].rgb;
    require(choose(layout, redChoice, scope, state, cosmetics).refusal == CareerLayoutRefusal::StaleChoice,
        "Same Red label reused an older primary");
    auto redAgain = findChoice(layout.view(scope, state, cosmetics), redChoice.id);
    require(redAgain.label == "Red", "Red label changed after another color became current");
    auto picked = choose(layout, redAgain, scope, state, cosmetics);
    require(picked.accepted && picked.cosmetic.kind == NativeCosmeticRequestKind::SelectPrimaryColor &&
        picked.cosmetic.paletteIndex == red && picked.cosmetic.primary == std::array<float, 3>{} &&
        picked.cosmetic.draftCount == 0 && picked.action.empty(), "Primary selection was not a palette index");
    require(cosmetics.draft[1].productId == 11, "Primary selection cleared the item draft");
    cosmetics.primary = kNativeCosmeticPalette[red].rgb;

    require(choose(layout, findChoice(layout.view(scope, state, cosmetics), "nav.back"), scope, state, cosmetics).accepted,
        "Primary back failed");
    require(choose(layout, findChoice(layout.view(scope, state, cosmetics), "cosmetic.colors.accent"),
        scope, state, cosmetics).accepted, "Accent page did not open");
    auto accent = layout.view(scope, state, cosmetics);
    audit(accent);
    require(accent.body.find("Current accent: Black") != std::string::npos, "Current accent missing");
    auto accentChoice = findChoice(accent, "cosmetic.accent." + std::to_string(orange));
    require(accentChoice.cosmetic.kind == NativeCosmeticRequestKind::SelectSecondaryColor &&
        accentChoice.cosmetic.paletteIndex == orange && accentChoice.cosmetic.draftCount == 0 &&
        accentChoice.action.empty(), "Accent selection was not typed");
    auto accented = choose(layout, accentChoice, scope, state, cosmetics);
    require(accented.accepted && accented.cosmetic.paletteIndex == orange &&
        accented.cosmetic.secondary == std::array<float, 3>{}, "Accent selection supplied RGB");
    cosmetics.secondary = kNativeCosmeticPalette[orange].rgb;
    require(choose(layout, findChoice(layout.view(scope, state, cosmetics), "nav.back"), scope, state, cosmetics).accepted,
        "Accent back failed");
    require(choose(layout, findChoice(layout.view(scope, state, cosmetics), "nav.back"), scope, state, cosmetics).accepted,
        "Colors back failed");
    auto mixed = findChoice(layout.view(scope, state, cosmetics), "cosmetic.apply");
    require(mixed.enabled && mixed.label == "Apply local design" && mixed.cosmetic.draftCount == 1 &&
        mixed.cosmetic.draft[0].slot == 1 && mixed.cosmetic.draft[0].productId == 11 && mixed.cosmetic.overrideColors &&
        mixed.cosmetic.primary == cosmetics.primary && mixed.cosmetic.secondary == cosmetics.secondary &&
        mixed.cosmetic.paletteIndex == -1, "Apply dropped the item draft or the color snapshot");

    NativeCosmeticContext only = cosmetics;
    only.draft.clear();
    NativeCareerLayout colorOnly;
    openAppearance(colorOnly, scope, state, only);
    auto colorApply = findChoice(colorOnly.view(scope, state, only), "cosmetic.apply");
    require(colorApply.enabled && colorApply.cosmetic.draftCount == 0 && colorApply.cosmetic.overrideColors &&
        colorApply.cosmetic.primary == only.primary && colorApply.cosmetic.secondary == only.secondary,
        "Color-only Apply was disabled");
    require(nativeCosmeticRequestCurrent(colorApply.cosmetic, only), "Color-only snapshot was rejected");
    only.primary = kNativeCosmeticPalette[pink].rgb;
    require(choose(colorOnly, colorApply, scope, state, only).refusal == CareerLayoutRefusal::StaleChoice,
        "Same Apply label reused an older color");
    auto freshColor = findChoice(colorOnly.view(scope, state, only), "cosmetic.apply");
    require(freshColor.label == colorApply.label && freshColor.cosmetic.primary == only.primary,
        "Fresh color snapshot was not retained");
    require(!nativeCosmeticRequestCurrent(colorApply.cosmetic, only), "Old color snapshot stayed current");
    require(nativeCosmeticRequestCurrent(freshColor.cosmetic, only), "Fresh color snapshot was rejected");
    auto tainted = freshColor.cosmetic;
    tainted.paletteIndex = 0;
    require(!nativeCosmeticRequestCurrent(tainted, only), "Apply kept a palette index");

    NativeCosmeticContext off = only;
    off.overrideColors = false;
    off.draft.clear();
    NativeCareerLayout offLayout;
    openAppearance(offLayout, scope, state, off);
    require(!findChoice(offLayout.view(scope, state, off), "cosmetic.apply").enabled,
        "Apply was enabled with override off and no items");

    NativeCosmeticContext unavailable = only;
    unavailable.available = false;
    NativeCareerLayout unavailableLayout;
    openAppearance(unavailableLayout, scope, state, unavailable);
    require(!findChoice(unavailableLayout.view(scope, state, unavailable), "cosmetic.apply").enabled,
        "Color-only Apply ignored an unavailable item mod");
    require(choose(unavailableLayout, findChoice(unavailableLayout.view(scope, state, unavailable), "cosmetic.colors"),
        scope, state, unavailable).accepted, "Colors stayed closed while item mod is unavailable");
    require(findChoice(unavailableLayout.view(scope, state, unavailable), "cosmetic.colors.override").enabled,
        "Color draft editing was blocked while item mod is unavailable");

    NativeCosmeticContext scanning = only;
    scanning.scanning = true;
    NativeCareerLayout scanningLayout;
    openAppearance(scanningLayout, scope, state, scanning);
    require(choose(scanningLayout, findChoice(scanningLayout.view(scope, state, scanning), "cosmetic.colors"),
        scope, state, scanning).accepted, "Colors page closed while scanning");
    require(!findChoice(scanningLayout.view(scope, state, scanning), "cosmetic.colors.override").enabled,
        "Override stayed enabled while scanning");
    require(choose(scanningLayout, findChoice(scanningLayout.view(scope, state, scanning), "cosmetic.colors.primary"),
        scope, state, scanning).accepted, "Primary page closed while scanning");
    require(!findChoice(scanningLayout.view(scope, state, scanning), "cosmetic.primary." + std::to_string(red)).enabled,
        "Primary color stayed enabled while scanning");

    NativeCosmeticContext pending = only;
    pending.restorationPending = true;
    pending.draft[1] = {11, 0};
    NativeCareerLayout pendingLayout;
    openAppearance(pendingLayout, scope, state, pending);
    auto pendingView = pendingLayout.view(scope, state, pending);
    require(!findChoice(pendingView, "cosmetic.apply").enabled && findChoice(pendingView, "cosmetic.restore").enabled,
        "Pending restoration changed the restore route");
    require(choose(pendingLayout, findChoice(pendingView, "cosmetic.colors"), scope, state, pending).accepted,
        "Colors page closed during restoration");
    require(!findChoice(pendingLayout.view(scope, state, pending), "cosmetic.colors.override").enabled,
        "Color editing stayed enabled during restoration");

    NativeCosmeticContext custom = only;
    custom.primary = {0.04f, 0.36f, 0.85f};
    custom.secondary = {1.0f, 0.53f, 0.18f};
    NativeCareerLayout customLayout;
    openAppearance(customLayout, scope, state, custom);
    require(choose(customLayout, findChoice(customLayout.view(scope, state, custom), "cosmetic.colors"),
        scope, state, custom).accepted, "Custom colors did not open");
    auto customColors = customLayout.view(scope, state, custom);
    require(customColors.body.find("Primary: Custom") != std::string::npos &&
        customColors.body.find("Accent: Custom") != std::string::npos, "Unlisted host colors were renamed");

    NativeCosmeticRequest unused = redAgain.cosmetic;
    unused.productId = 11;
    require(!nativeCosmeticRequestCurrent(unused, cosmetics), "A color request kept an item field");
    NativeCosmeticRequest badIndex;
    badIndex.kind = NativeCosmeticRequestKind::SelectPrimaryColor;
    badIndex.paletteIndex = 99;
    require(!nativeCosmeticRequestCurrent(badIndex, cosmetics), "Palette index 99 was accepted");
    badIndex.paletteIndex = -1;
    require(!nativeCosmeticRequestCurrent(badIndex, cosmetics), "Unused palette index was accepted as a color");
    badIndex.paletteIndex = red;
    badIndex.primary = kNativeCosmeticPalette[red].rgb;
    require(!nativeCosmeticRequestCurrent(badIndex, cosmetics), "A color selection carried RGB");
    badIndex.primary = {};
    require(nativeCosmeticRequestCurrent(badIndex, cosmetics), "A current palette selection was rejected");
    NativeCosmeticRequest mode;
    mode.kind = static_cast<NativeCosmeticRequestKind>(40);
    require(!nativeCosmeticRequestCurrent(mode, cosmetics), "An unsupported cosmetic mode was accepted");
    auto nan = cosmetics;
    nan.primary[0] = std::numeric_limits<float>::quiet_NaN();
    require(!nativeCosmeticRequestCurrent(freshColor.cosmetic, nan), "A nonfinite primary was accepted");
    nan.primary[0] = std::numeric_limits<float>::infinity();
    require(!nativeCosmeticRequestCurrent(badIndex, nan), "An infinite primary was accepted");
    nan.primary = {1.5f, 0.f, 0.f};
    require(!nativeCosmeticRequestCurrent(freshColor.cosmetic, nan), "A color above 1 was accepted");
    nan.primary = {-0.01f, 0.f, 0.f};
    require(!nativeCosmeticRequestCurrent(enable.cosmetic, nan), "A negative color was accepted");
    NativeCosmeticRequest item;
    item.kind = NativeCosmeticRequestKind::SelectItem;
    item.slot = 2;
    item.productId = 3;
    item.paintable = true;
    item.paletteIndex = 0;
    require(!nativeCosmeticRequestCurrent(item, cosmetics), "An item request kept a palette index");
    NativeCosmeticRequest sameOverride;
    sameOverride.kind = NativeCosmeticRequestKind::SetColorOverride;
    sameOverride.overrideColors = cosmetics.overrideColors;
    require(!nativeCosmeticRequestCurrent(sameOverride, cosmetics), "An old override snapshot stayed current");

    NativeCareerLayout routeLayout;
    openGarage(routeLayout, scope, state);
    auto garage = routeLayout.view(scope, state, cosmetics);
    require(findChoice(garage, "garage.player").kind == CareerLayoutEffectKind::PreserveStockRoute, "Stock garage route changed");
    require(findChoice(garage, "garage.bot.anchor.stock-23").action == "loadout", "Bot preset route changed");
}

static void openSlot(NativeCareerLayout& layout, const CareerLayoutScope& scope, const Json& state,
                     const NativeCosmeticContext& cosmetics, int slot) {
    openAppearance(layout, scope, state, cosmetics);
    auto appearance = layout.view(scope, state, cosmetics);
    require(choose(layout, findChoice(appearance, "cosmetic.slot." + std::to_string(slot)), scope, state, cosmetics).accepted,
        "Category did not open");
}

int main() {
    try {
        require(!NativeCareerLayout::kProductionGateEnabled && !NativeMovieProtocol::kRuntimeVerified &&
            !NativeMovieProtocol::kProductionReady, "Verification flags were enabled");
        require(!NativeCareerLayout::supportedAction("apply_cosmetics") && !NativeCareerLayout::supportedAction("restore_cosmetics"),
            "Local cosmetic requests were marked as bridge actions");
        require(kNativeCosmeticProductMax == kMaxCosmeticProductId, "Product cap drifted from the v4 code");
        for (int slot = 0; slot <= 31; ++slot)
            require(nativeCosmeticSlotEquipable(slot) == cosmetic_design_detail::supportedCosmeticSlot(slot),
                "Equipable slots drifted from the design code");

        const auto scope = ownedScope();
        const auto state = readyState();
        NativeCosmeticContext cosmetics;
        cosmetics.available = true;
        cosmetics.catalog = share(sampleProducts());

        NativeCareerLayout stockLayout;
        openGarage(stockLayout, scope, state);
        auto garage = stockLayout.view(scope, state, cosmetics);
        audit(garage);
        require(garage.body.find("do not add items") != std::string::npos, "Garage entitlement copy missing");
        auto player = findChoice(garage, "garage.player");
        auto stock = choose(stockLayout, player, scope, state, cosmetics, true);
        require(stock.accepted && stock.kind == CareerLayoutEffectKind::PreserveStockRoute && stock.stock == StockRoute::Garage &&
            stock.action.empty() && stock.payload.empty(), "Stock garage route changed");
        auto preset = findChoice(garage, "garage.bot.anchor.stock-23");
        auto saved = choose(stockLayout, preset, scope, state, cosmetics, true);
        require(saved.accepted && saved.action == "loadout" &&
            saved.payload == Json({{"id", "anchor"}, {"car_id", 23}, {"primary_color", 27}, {"secondary_color", 0}}),
            "Bot preset route changed");
        require(findChoice(garage, NativeCareerLayout::kAppearance).kind == CareerLayoutEffectKind::Navigate, "Local appearance missing");

        NativeCareerLayout emptyLayout;
        NativeCosmeticContext empty;
        empty.available = true;
        openAppearance(emptyLayout, scope, state, empty);
        auto emptyView = emptyLayout.view(scope, state, empty);
        audit(emptyView);
        require(emptyView.body.find("No local cosmetic catalog") != std::string::npos, "Empty catalog was not explained");
        require(!findChoice(emptyView, "cosmetic.apply").enabled, "Apply was enabled without a catalog");
        require(findChoice(emptyView, "cosmetic.restore").enabled, "Restore was disabled while item mod is available");
        openSlot(emptyLayout, scope, state, empty, 2);
        auto emptyWheels = emptyLayout.view(scope, state, empty);
        require(emptyWheels.body.find("No supported items") != std::string::npos, "Empty category was not explained");
        for (const auto& choice : emptyWheels.choices)
            require(choice.cosmetic.kind != NativeCosmeticRequestKind::SelectItem, "Empty catalog offered an item");

        NativeCareerLayout scanningLayout;
        auto scanning = cosmetics;
        scanning.scanning = true;
        openAppearance(scanningLayout, scope, state, scanning);
        auto scanningView = scanningLayout.view(scope, state, scanning);
        require(scanningView.body.find("still loading") != std::string::npos, "Scanning catalog was not explained");
        require(!findChoice(scanningView, "cosmetic.apply").enabled && !findChoice(scanningView, "cosmetic.restore").enabled,
            "Apply or restore stayed enabled while scanning");
        openSlot(scanningLayout, scope, state, scanning, 2);
        for (const auto& choice : scanningLayout.view(scope, state, scanning).choices)
            require(choice.cosmetic.kind != NativeCosmeticRequestKind::SelectItem, "Scanning catalog offered an item");

        NativeCareerLayout unavailableLayout;
        auto unavailable = cosmetics;
        unavailable.available = false;
        unavailable.draft[2] = {3, 0};
        openAppearance(unavailableLayout, scope, state, unavailable);
        auto unavailableView = unavailableLayout.view(scope, state, unavailable);
        require(unavailableView.body.find("does not expose the local cosmetic override") != std::string::npos,
            "Missing item mod was not explained");
        auto blockedApply = findChoice(unavailableView, "cosmetic.apply");
        require(!blockedApply.enabled, "Apply stayed enabled without item mod");
        auto blocked = choose(unavailableLayout, blockedApply, scope, state, unavailable);
        require(!blocked.accepted && blocked.cosmetic.kind == NativeCosmeticRequestKind::None, "Unavailable apply returned a payload");
        require(!findChoice(unavailableLayout.view(scope, state, unavailable), "cosmetic.restore").enabled,
            "Restore stayed enabled without item mod");

        NativeCareerLayout wheelsLayout;
        openSlot(wheelsLayout, scope, state, cosmetics, 2);
        auto firstPage = wheelsLayout.view(scope, state, cosmetics);
        audit(firstPage);
        require(firstPage.body.find("Page 1 of 6") != std::string::npos, "Wheel pages were capped");
        require(hasProduct(firstPage, 3) && hasProduct(firstPage, 7), "First page lost its first items");
        require(!hasProduct(firstPage, 1062) && !hasProduct(firstPage, 65535) && !hasProduct(firstPage, 65536),
            "Later or unsupported products were on the first page");
        std::size_t firstItems = 0;
        for (const auto& choice : firstPage.choices) {
            if (choice.cosmetic.kind != NativeCosmeticRequestKind::SelectItem) continue;
            ++firstItems;
            require(choice.cosmetic.slot == 2 && choice.cosmetic.productId >= 1 &&
                choice.cosmetic.productId <= kNativeCosmeticProductMax, "Unsupported product was selectable");
        }
        require(firstItems == NativeCareerLayout::kCosmeticItemsPerPage, "First page did not fill a server page");
        auto halo = findProduct(firstPage, 3);
        require(halo.label == "Halo" && halo.cosmetic.paint == 0 && halo.cosmetic.paintable, "Halo binding changed");
        auto selected = choose(wheelsLayout, halo, scope, state, cosmetics, false);
        require(selected.accepted && selected.kind == CareerLayoutEffectKind::LocalCosmetic && selected.action.empty() &&
            selected.payload.empty() && !selected.leaveMenu && !selected.originalConsumptionRequired, "Item selection dispatched");
        require(selected.cosmetic.kind == NativeCosmeticRequestKind::SelectItem && selected.cosmetic.slot == 2 &&
            selected.cosmetic.productId == 3 && selected.cosmetic.paint == 0 && selected.cosmetic.paintable &&
            selected.cosmetic.draftCount == 0, "Item selection was not a fixed request");
        require(selected.page == CareerLayoutPage::CosmeticPaints, "Selecting an item did not open paints");
        require(choose(wheelsLayout, halo, scope, state, cosmetics).refusal == CareerLayoutRefusal::StaleChoice,
            "Duplicate item click was accepted");

        cosmetics.draft[2] = {3, 0};
        auto paints = wheelsLayout.view(scope, state, cosmetics);
        audit(paints);
        require(paints.choices.size() <= NativeCareerLayout::kMaxChoices, "Paint page exceeded the movie cap");
        auto crimson = findChoice(paints, "cosmetic.paint.1");
        require(crimson.label == "Crimson" && crimson.cosmetic.paint == 1 && crimson.cosmetic.productId == 3, "Crimson binding changed");
        cosmetics.draft[2].paint = 2;
        auto staleCrimson = wheelsLayout.view(scope, state, cosmetics);
        require(findChoice(staleCrimson, "cosmetic.paint.1").label == "Crimson", "Unselected paint label changed");
        require(choose(wheelsLayout, crimson, scope, state, cosmetics).refusal == CareerLayoutRefusal::StaleChoice,
            "Same paint label applied a previous draft");
        cosmetics.draft[2].paint = 0;
        auto freshCrimson = findChoice(wheelsLayout.view(scope, state, cosmetics), "cosmetic.paint.1");
        auto painted = choose(wheelsLayout, freshCrimson, scope, state, cosmetics);
        require(painted.accepted && painted.cosmetic.kind == NativeCosmeticRequestKind::SelectPaint &&
            painted.cosmetic.slot == 2 && painted.cosmetic.productId == 3 && painted.cosmetic.paint == 1 &&
            painted.action.empty() && painted.payload.empty() && painted.cosmetic.draftCount == 0, "Paint request changed");
        require(choose(wheelsLayout, freshCrimson, scope, state, cosmetics).refusal == CareerLayoutRefusal::StaleChoice,
            "Duplicate paint click was accepted");

        NativeCareerLayout matteLayout;
        openSlot(matteLayout, scope, state, cosmetics, 2);
        auto matteChoice = findProduct(matteLayout.view(scope, state, cosmetics), 7);
        auto matte = choose(matteLayout, matteChoice, scope, state, cosmetics);
        require(matte.accepted && matte.cosmetic.kind == NativeCosmeticRequestKind::SelectItem && !matte.cosmetic.paintable &&
            matte.cosmetic.paint == 0, "Non-paintable item was not selectable as original");
        cosmetics.draft[2] = {7, 0};
        auto mattePaints = matteLayout.view(scope, state, cosmetics);
        require(mattePaints.body.find("does not support paint") != std::string::npos, "Non-paintable paint copy missing");
        for (const auto& choice : mattePaints.choices)
            require(choice.cosmetic.kind != NativeCosmeticRequestKind::SelectPaint, "Non-paintable item offered a paint");
        CareerLayoutChoice forgedPaint;
        forgedPaint.id = "cosmetic.paint.1";
        forgedPaint.label = "Crimson";
        forgedPaint.enabled = true;
        forgedPaint.kind = CareerLayoutEffectKind::LocalCosmetic;
        forgedPaint.cosmetic.kind = NativeCosmeticRequestKind::SelectPaint;
        forgedPaint.cosmetic.slot = 2;
        forgedPaint.cosmetic.productId = 7;
        forgedPaint.cosmetic.paint = 1;
        forgedPaint.cosmetic.paintable = true;
        require(choose(matteLayout, forgedPaint, scope, state, cosmetics).refusal == CareerLayoutRefusal::StaleChoice,
            "Forged paint was accepted for a non-paintable item");

        cosmetics.draft[2] = {3, 1};
        cosmetics.draft[1] = {11, 0};
        NativeCareerLayout clearLayout;
        openSlot(clearLayout, scope, state, cosmetics, 2);
        auto clearChoice = findChoice(clearLayout.view(scope, state, cosmetics), "cosmetic.clear");
        require(clearChoice.label == "Clear Wheels", "Clear label changed");
        auto cleared = choose(clearLayout, clearChoice, scope, state, cosmetics);
        require(cleared.accepted && cleared.cosmetic.kind == NativeCosmeticRequestKind::ClearSlot &&
            cleared.cosmetic.slot == 2 && cleared.cosmetic.productId == 3 && cleared.cosmetic.paint == 1 &&
            cleared.cosmetic.draftCount == 0 && cleared.action.empty(), "Clear slot was not limited to that draft");

        NativeCareerLayout applyLayout;
        openAppearance(applyLayout, scope, state, cosmetics);
        auto applyChoice = findChoice(applyLayout.view(scope, state, cosmetics), "cosmetic.apply");
        require(applyChoice.label == "Apply local design" && applyChoice.enabled, "Apply was not offered");
        require(applyChoice.cosmetic.draftCount == 2, "Apply snapshot dropped a valid slot");
        require(applyChoice.cosmetic.draft[0] == NativeCosmeticDraftEntry{1, 11, 0, true}, "Decal snapshot changed");
        require(applyChoice.cosmetic.draft[1] == NativeCosmeticDraftEntry{2, 3, 1, true}, "Wheel snapshot changed");
        cosmetics.draft[2].paint = 5;
        require(choose(applyLayout, applyChoice, scope, state, cosmetics).refusal == CareerLayoutRefusal::StaleChoice,
            "Same Apply label reused a stale draft");
        auto freshApply = findChoice(applyLayout.view(scope, state, cosmetics), "cosmetic.apply");
        require(freshApply.label == applyChoice.label && freshApply.cosmetic.draft[1].paint == 5, "Fresh draft was not retained");
        auto applied = choose(applyLayout, freshApply, scope, state, cosmetics);
        require(applied.accepted && applied.cosmetic == freshApply.cosmetic && applied.action.empty() && applied.payload.empty() &&
            applied.cosmetic.kind == NativeCosmeticRequestKind::Apply, "Apply was not the retained snapshot");
        cosmetics.draft[0] = {4, 0};
        cosmetics.draft[2].paint = 99;
        auto skipped = applyLayout.view(scope, state, cosmetics);
        require(skipped.body.find("outside this local catalog") != std::string::npos, "Invalid draft rows were hidden");
        require(findChoice(skipped, "cosmetic.apply").cosmetic.draftCount == 1, "Invalid rows were included in Apply");
        require(findChoice(skipped, "cosmetic.apply").cosmetic.draft[0].slot == 1, "The valid decal was dropped");

        auto pending = cosmetics;
        pending.draft.clear();
        pending.draft[2] = {3, 0};
        pending.restorationPending = true;
        NativeCareerLayout pendingLayout;
        openAppearance(pendingLayout, scope, state, pending);
        auto pendingView = pendingLayout.view(scope, state, pending);
        require(!findChoice(pendingView, "cosmetic.apply").enabled && findChoice(pendingView, "cosmetic.restore").enabled,
            "Restore was not the available control while restoration is pending");
        require(findChoice(pendingView, "cosmetic.restore").cosmetic.restorationPending, "Restore lost the pending flag");
        auto restored = choose(pendingLayout, findChoice(pendingView, "cosmetic.restore"), scope, state, pending);
        require(restored.accepted && restored.cosmetic.kind == NativeCosmeticRequestKind::Restore &&
            restored.cosmetic.restorationPending && restored.action.empty() && restored.payload.empty(),
            "Restore was not a fixed local request");

        auto renamed = cosmetics;
        renamed.restorationPending = false;
        renamed.draft.clear();
        cosmetics.draft.clear();
        auto renamedProducts = sampleProducts();
        renamedProducts[0].id = 99;
        renamed.catalog = share(renamedProducts);
        NativeCareerLayout staleLayout;
        openSlot(staleLayout, scope, state, cosmetics, 2);
        auto oldHalo = findProduct(staleLayout.view(scope, state, cosmetics), 3);
        require(oldHalo.label == "Halo", "Halo label changed before the catalog edit");
        require(choose(staleLayout, oldHalo, scope, state, renamed).refusal == CareerLayoutRefusal::StaleChoice,
            "Same label accepted a different product");
        auto moved = sampleProducts();
        moved[0].slot = 1;
        renamed.catalog = share(std::move(moved));
        require(choose(staleLayout, oldHalo, scope, state, renamed).refusal == CareerLayoutRefusal::StaleChoice,
            "A product that changed slots stayed selectable");
        renamed.catalog = share(sampleProducts());
        renamed.catalog.reset();
        auto withoutHalo = sampleProducts();
        withoutHalo.erase(withoutHalo.begin());
        renamed.catalog = share(std::move(withoutHalo));
        require(choose(staleLayout, oldHalo, scope, state, renamed).refusal == CareerLayoutRefusal::StaleChoice,
            "A removed catalog entry stayed selectable");
        auto dull = sampleProducts();
        dull[0].paintable = false;
        renamed.catalog = share(std::move(dull));
        require(findProduct(staleLayout.view(scope, state, renamed), 3).label == "Halo", "Paintability change renamed Halo");
        require(choose(staleLayout, oldHalo, scope, state, renamed).refusal == CareerLayoutRefusal::StaleChoice,
            "Changed paintability reused the old item click");

        auto foreign = scope;
        foreign.online = true;
        require(choose(staleLayout, oldHalo, foreign, state, cosmetics).refusal == CareerLayoutRefusal::StaleScope,
            "Online scope accepted a cosmetic click");
        foreign = scope;
        foreign.nonce = "fedcba9876543210fedcba9876543210";
        require(choose(staleLayout, oldHalo, foreign, state, cosmetics).refusal == CareerLayoutRefusal::StaleScope,
            "Foreign scope accepted a cosmetic click");
        auto forged = oldHalo;
        forged.kind = CareerLayoutEffectKind::Dispatch;
        forged.action = "loadout";
        forged.payload = {{"id", "anchor"}, {"car_id", 23}, {"primary_color", 1}, {"secondary_color", 1}};
        require(!choose(staleLayout, forged, scope, state, cosmetics).accepted, "Forged bridge action was accepted");

        NativeCareerLayout pageLayout;
        openSlot(pageLayout, scope, state, cosmetics, 2);
        std::vector<int> seen;
        CareerLayoutChoice wide;
        bool foundWide = false;
        for (int guard = 0; guard < 20; ++guard) {
            auto page = pageLayout.view(scope, state, cosmetics);
            audit(page);
            require(validUtf8(page.body), "Category body was not valid UTF-8");
            for (const auto& choice : page.choices) {
                require(validUtf8(choice.label), "Choice label was not valid UTF-8");
                if (choice.cosmetic.kind != NativeCosmeticRequestKind::SelectItem) continue;
                require(choice.cosmetic.slot == 2, "Another slot was mixed into wheels");
                require(choice.cosmetic.productId != 65536 && choice.cosmetic.productId != 0 && choice.cosmetic.productId > 0,
                    "Out-of-range product was offered");
                seen.push_back(choice.cosmetic.productId);
                if (choice.cosmetic.productId == 65535) { wide = choice; foundWide = true; }
            }
            if (!hasChoice(page, "cosmetic.next")) break;
            require(choose(pageLayout, findChoice(page, "cosmetic.next"), scope, state, cosmetics).accepted, "Next page failed");
        }
        require(seen.size() == 83, "Wheel catalog was truncated");
        require(seen[64] == 1062, "Item past the first 64 was not reachable in order");
        require(foundWide, "Product 65535 was omitted");
        int haloCount = 0;
        for (int id : seen) haloCount += id == 3;
        require(haloCount == 1, "Duplicate catalog id was offered twice");
        require(!hasProduct(pageLayout.view(scope, state, cosmetics), 1062), "The last page still showed an earlier item");
        auto previous = choose(pageLayout, findChoice(pageLayout.view(scope, state, cosmetics), "cosmetic.previous"),
            scope, state, cosmetics);
        require(previous.accepted && pageLayout.view(scope, state, cosmetics).body.find("Page 5 of 6") != std::string::npos,
            "Previous page did not move back");
        require(!hasProduct(pageLayout.view(scope, state, cosmetics), 65535), "Previous page kept the last item");
        auto wideEffect = choose(pageLayout, wide, scope, state, cosmetics);
        require(!wideEffect.accepted, "A wide-wheel choice from another page was accepted");

        NativeCareerLayout wideLayout;
        openSlot(wideLayout, scope, state, cosmetics, 2);
        for (int guard = 0; guard < 20 && !hasProduct(wideLayout.view(scope, state, cosmetics), 65535); ++guard)
            require(choose(wideLayout, findChoice(wideLayout.view(scope, state, cosmetics), "cosmetic.next"),
                scope, state, cosmetics).accepted, "Could not reach product 65535");
        auto wideChoice = findProduct(wideLayout.view(scope, state, cosmetics), 65535);
        auto wideSelected = choose(wideLayout, wideChoice, scope, state, cosmetics);
        require(wideSelected.accepted && wideSelected.cosmetic.productId == 65535 && wideSelected.cosmetic.slot == 2,
            "In-range product 65535 was rejected");

        NativeCareerLayout appearanceLayout;
        openAppearance(appearanceLayout, scope, state, cosmetics);
        auto appearance = appearanceLayout.view(scope, state, cosmetics);
        audit(appearance);
        require(appearance.body.find("does not change Rocket League inventory") != std::string::npos, "Inventory copy missing");
        require(appearance.body.find("Bodies, banners, borders, and titles") != std::string::npos, "Browse-only copy missing");
        for (int slot : {0, 6, 16, 20, 21})
            require(!hasChoice(appearance, "cosmetic.slot." + std::to_string(slot)), "Unsupported slot was editable");
        require(hasChoice(appearance, "cosmetic.slot.1") && hasChoice(appearance, "cosmetic.slot.18"), "Equipable category missing");

        NativeCareerLayout unicodeLayout;
        openSlot(unicodeLayout, scope, state, cosmetics, 1);
        auto decals = unicodeLayout.view(scope, state, cosmetics);
        bool foundUnicode = false;
        for (const auto& choice : decals.choices) {
            require(validUtf8(choice.label) && choice.label.size() <= NativeCareerLayout::kMaxLabel, "Unicode label was not bounded");
            foundUnicode = foundUnicode || choice.label.find(u8"\u754c") != std::string::npos;
        }
        require(foundUnicode, "Unicode cosmetic name was lost");
        require(hasProduct(decals, 12) && !hasProduct(decals, 6), "Decal page mixed in another slot");

        NativeCosmeticContext colorBase;
        colorBase.available = true;
        colorBase.catalog = cosmetics.catalog;
        checkColorEditor(scope, state, colorBase);

        std::cout << "Native cosmetic layout checks passed; no game was launched.\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
