#include "NativeCareerLayout.h"

#include <algorithm>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

using namespace mct;

namespace {

void require(bool condition, const std::string& message) {
    if (!condition) throw std::runtime_error(message);
}

const CareerLayoutChoice& findChoice(const CareerLayoutView& view, const std::string& id) {
    for (const auto& choice : view.choices)
        if (choice.id == id) return choice;
    throw std::runtime_error("Missing control: " + id);
}

bool hasChoice(const CareerLayoutView& view, const std::string& id) {
    return std::any_of(view.choices.begin(), view.choices.end(), [&](const CareerLayoutChoice& choice) {
        return choice.id == id;
    });
}

std::size_t countPrefix(const CareerLayoutView& view, const std::string& prefix) {
    return static_cast<std::size_t>(std::count_if(view.choices.begin(), view.choices.end(),
        [&](const CareerLayoutChoice& choice) { return choice.id.rfind(prefix, 0) == 0; }));
}

CareerLayoutScope ownedScope() {
    CareerLayoutScope scope;
    scope.owned = true;
    scope.offline = true;
    scope.fresh = true;
    scope.online = false;
    scope.nonce = "0123456789abcdef0123456789abcdef";
    scope.generation = 4;
    return scope;
}

Json readyState(const CareerLayoutScope& scope) {
    return {
        {"protocol", 1},
        {"offline", true},
        {"bridge_session", scope.nonce},
        {"session", {{"state", "Career Ready"}, {"busy", false}, {"worker_running", false}}},
        {"career", {{"id", "career-a"}, {"pending_session", nullptr}}},
        {"community_plugins", {
            {"catalog", Json::array()}, {"selected", nullptr}, {"downloaded", Json::array()},
            {"busy", false}, {"can_activate", false}
        }},
        {"community_catalog", {
            {"source", ""}, {"page", 1}, {"fetched", false}, {"has_next", false},
            {"busy", false}, {"loading", false}, {"status", ""}, {"items", Json::array()}
        }}
    };
}

Json backendReadyState(const CareerLayoutScope& scope) {
    auto state = readyState(scope);
    // Match Backend.catalog_state's actual startup default. The current source
    // is Steam Maps even though no page has been fetched yet.
    state["community_catalog"] = {
        {"source", "steam_maps"}, {"page", 1}, {"query", ""}, {"busy", false},
        {"loading", false}, {"status", "idle"},
        {"message", "Choose a catalog source, then browse one public page."},
        {"items", Json::array()}, {"has_next", false}, {"source_url", ""},
        {"page_item_count", 0}, {"query_scope", "none"}, {"remote_query", false},
        {"truncated", false}, {"fetched", false}, {"generation", 0},
        {"catalog_only", true}, {"can_download", false}, {"can_activate", false}
    };
    return state;
}
Json catalogItem(const std::string& source, std::int64_t sourceId, const std::string& title,
                 const std::string& creator = "Creator", bool includeCreator = true) {
    Json item = {
        {"id", source + ":" + std::to_string(sourceId)},
        {"source", source},
        {"source_id", sourceId},
        {"title", title},
        {"catalog_only", true},
        {"can_activate", false}
    };
    if (includeCreator) item["creator"] = creator;
    return item;
}

Json catalogState(Json state, const std::string& source, int page, bool fetched, bool hasNext,
                  const std::string& status, Json items, bool busy = false, bool loading = false) {
    state["community_catalog"] = {
        {"source", source}, {"page", page}, {"fetched", fetched}, {"has_next", hasNext},
        {"busy", busy}, {"loading", loading}, {"status", status}, {"items", std::move(items)}
    };
    return state;
}

void audit(const CareerLayoutView& view) {
    require(view.choices.size() <= NativeCareerLayout::kMaxChoices, "Catalog view exceeded the choice bound");
    require(view.body.size() <= NativeCareerLayout::kMaxBody, "Catalog body exceeded the bound");
    require(!view.productionGateEnabled && !view.nativeReplacementFinished, "Catalog view opened a production gate");
    require(!view.suppressionEnforced && !view.compatibilityGrant, "Catalog view claimed native suppression or a grant");
    for (const auto& choice : view.choices) {
        require(choice.action != "community_activate", "Catalog exposed plugin activation");
        if (!choice.enabled || choice.kind != CareerLayoutEffectKind::Dispatch)
            require(choice.action.empty() && choice.payload.empty(), "Disabled/non-dispatch choice carried a command");
        if (!choice.action.empty()) require(NativeCareerLayout::supportedAction(choice.action), "Catalog action is unsupported");
    }
}

CareerLayoutEffect choose(NativeCareerLayout& layout, const CareerLayoutView& view, const std::string& id,
                          const CareerLayoutScope& scope, const Json& state, bool consumed) {
    return layout.choose(findChoice(view, id), scope, state, consumed);
}

void enterWorkshop(NativeCareerLayout& layout, const CareerLayoutScope& scope, const Json& state) {
    require(layout.open(scope, state), "Valid offline scope did not open the layout");
    const auto root = layout.view(scope, state);
    const auto effect = choose(layout, root, NativeCareerLayout::kWorkshop, scope, state, false);
    require(effect.accepted && effect.kind == CareerLayoutEffectKind::Navigate &&
            effect.page == CareerLayoutPage::Workshop, "Workshop navigation failed");
}

void enterCatalogFromMaps(NativeCareerLayout& layout, const CareerLayoutScope& scope, const Json& state) {
    enterWorkshop(layout, scope, state);
    const auto workshop = layout.view(scope, state);
    const auto effect = choose(layout, workshop, "workshop.catalog.open", scope, state, false);
    require(effect.accepted && effect.kind == CareerLayoutEffectKind::Navigate &&
            effect.page == CareerLayoutPage::WorkshopCatalog, "Online maps catalog navigation failed");
}

void enterCatalogFromMods(NativeCareerLayout& layout, const CareerLayoutScope& scope, const Json& state) {
    enterWorkshop(layout, scope, state);
    const auto workshop = layout.view(scope, state);
    const auto mods = choose(layout, workshop, "workshop.tab.mods", scope, state, false);
    require(mods.accepted && mods.kind == CareerLayoutEffectKind::Navigate &&
            mods.page == CareerLayoutPage::WorkshopMods, "Mods tab navigation failed");
    const auto modsView = layout.view(scope, state);
    const auto catalog = choose(layout, modsView, "mods.catalog", scope, state, false);
    require(catalog.accepted && catalog.kind == CareerLayoutEffectKind::Navigate &&
            catalog.page == CareerLayoutPage::WorkshopCatalog, "Plugin catalog navigation failed");
}

void testNavigationAndSourceDispatch() {
    const auto scope = ownedScope();
    const auto state = readyState(scope);
    NativeCareerLayout layout;
    enterWorkshop(layout, scope, state);

    auto workshop = layout.view(scope, state);
    audit(workshop);
    require(findChoice(workshop, "workshop.tab.maps").target == CareerLayoutPage::Workshop,
            "Training Maps tab is not reachable");
    require(findChoice(workshop, "workshop.tab.mods").target == CareerLayoutPage::WorkshopMods,
            "Mods tab is not reachable");
    const auto mapsTab = choose(layout, workshop, "workshop.tab.maps", scope, state, false);
    require(mapsTab.accepted && mapsTab.page == CareerLayoutPage::Workshop,
            "Training Maps tab could not be selected");
    workshop = layout.view(scope, state);
    const auto mapsNav = findChoice(workshop, "workshop.catalog.open");
    require(mapsNav.kind == CareerLayoutEffectKind::Navigate && mapsNav.target == CareerLayoutPage::WorkshopCatalog,
            "Maps catalog control is not navigation");
    const auto maps = choose(layout, workshop, "workshop.catalog.open", scope, state, false);
    require(maps.accepted && maps.page == CareerLayoutPage::WorkshopCatalog, "Maps catalog route failed");

    auto initial = layout.view(scope, state);
    audit(initial);
    require(initial.title == "Workshop - Training Maps catalog", "Unexpected Training Maps catalog title");
    require(initial.body.find("Choose a source, then Browse") != std::string::npos, "Initial source prompt is missing");
    for (const auto* source : {"steam_maps", "bakkes_maps"}) {
        const std::string id = std::string("catalog.source.") + source;
        const auto action = choose(layout, initial, id, scope, state, true);
        require(action.accepted && action.kind == CareerLayoutEffectKind::Dispatch &&
                action.action == "community_browse", "Map source did not dispatch a browse");
        require(action.payload == Json({{"source", source}, {"page", 1}, {"query", ""}}),
                "Map source browse payload was incorrect");
        initial = layout.view(scope, state);
    }
    require(!hasChoice(initial, "catalog.browse"), "Browse action appeared without a selected source");

    NativeCareerLayout modsLayout;
    enterWorkshop(modsLayout, scope, state);
    auto workshopView = modsLayout.view(scope, state);
    require(choose(modsLayout, workshopView, "workshop.tab.mods", scope, state, false).page ==
            CareerLayoutPage::WorkshopMods, "Could not open Mods tab");
    auto modsView = modsLayout.view(scope, state);
    audit(modsView);
    const auto pluginSource = findChoice(modsView, "catalog.source.bakkes_plugins");
    require(pluginSource.enabled && pluginSource.kind == CareerLayoutEffectKind::Dispatch,
            "BakkesMod plugin source is not browseable");
    const auto pluginBrowse = choose(modsLayout, modsView, pluginSource.id, scope, state, true);
    require(pluginBrowse.accepted && pluginBrowse.action == "community_browse" &&
            pluginBrowse.payload == Json({{"source", "bakkes_plugins"}, {"page", 1}, {"query", ""}}),
            "Plugin source browse payload was incorrect");

    modsView = modsLayout.view(scope, state);
    const auto activate = findChoice(modsView, "community.activate");
    require(!activate.enabled && activate.kind == CareerLayoutEffectKind::Unavailable &&
            activate.action.empty() && activate.payload.empty() &&
            activate.reason == NativeCareerLayout::kActivationReason, "Plugin activation was not disabled");
    const auto refused = choose(modsLayout, modsView, "community.activate", scope, state, true);
    require(!refused.accepted && refused.action.empty() && refused.refusal == CareerLayoutRefusal::Disabled,
            "Disabled plugin activation dispatched");
    require(!NativeCareerLayout::supportedAction("community_activate"), "Activation became an allowed action");

    const auto modsCatalog = choose(modsLayout, modsView, "mods.catalog", scope, state, false);
    require(modsCatalog.accepted && modsCatalog.page == CareerLayoutPage::WorkshopCatalog,
            "Plugin catalog navigation failed");
    auto pluginState = catalogState(state, "bakkes_plugins", 1, true, true, "ok",
        Json::array({catalogItem("bakkes_plugins", 223, "Training Plugin")}));
    auto pluginView = modsLayout.view(scope, pluginState);
    audit(pluginView);
    require(pluginView.title == "Workshop - Mods catalog", "Plugin catalog did not use the Mods title");
    require(hasChoice(pluginView, "catalog.open.223") && hasChoice(pluginView, "catalog.plugin.223"),
            "Plugin catalog row actions were missing");
    const auto checkPlugin = choose(modsLayout, pluginView, "catalog.plugin.223", scope, pluginState, true);
    require(checkPlugin.accepted && checkPlugin.action == "community_select_plugin" &&
            checkPlugin.payload == Json({{"source", "bakkes_plugins"}, {"id", 223}}) &&
            checkPlugin.payload["id"].is_number_integer(), "Plugin check payload was not numeric");

    NativeCareerLayout legacyCommunity;
    require(legacyCommunity.open(scope, state), "Could not open layout for Community route");
    const auto root = legacyCommunity.view(scope, state);
    require(choose(legacyCommunity, root, NativeCareerLayout::kCommunity, scope, state, false).page ==
            CareerLayoutPage::Community, "Community route failed");
    auto communityView = legacyCommunity.view(scope, state);
    audit(communityView);
    require(hasChoice(communityView, "community.catalog"), "Community map catalog link is missing");
    require(choose(legacyCommunity, communityView, "community.catalog", scope, state, false).page ==
            CareerLayoutPage::WorkshopCatalog, "Community catalog route failed");
}

void testRowsPaginationPayloadAndSanitization() {
    const auto scope = ownedScope();
    const auto base = readyState(scope);
    NativeCareerLayout layout;
    enterCatalogFromMaps(layout, scope, base);

    Json items = Json::array();
    items.push_back(catalogItem("bakkes_maps", 3, "Wrong source"));
    auto activatable = catalogItem("steam_maps", 4, "Activatable");
    activatable["can_activate"] = true;
    items.push_back(activatable);
    auto notCatalogOnly = catalogItem("steam_maps", 5, "Not catalog-only");
    notCatalogOnly["catalog_only"] = false;
    items.push_back(notCatalogOnly);
    auto stringId = catalogItem("steam_maps", 6, "String source id");
    stringId["source_id"] = "6";
    items.push_back(stringId);
    auto booleanId = catalogItem("steam_maps", 10, "Boolean source id");
    booleanId["source_id"] = true;
    items.push_back(booleanId);
    auto floatingId = catalogItem("steam_maps", 11, "Floating source id");
    floatingId["source_id"] = 11.5;
    items.push_back(floatingId);
    items.push_back(catalogItem("steam_maps", 10000000000LL, "Source id above limit"));
    auto mismatch = catalogItem("steam_maps", 7, "Mismatched row id");
    mismatch["id"] = "steam_maps:8";
    items.push_back(mismatch);
    items.push_back(catalogItem("steam_maps", 9, ""));
    const std::string unsafeTitle = "<map>&\n" + std::string(50, 'x');
    items.push_back(catalogItem("steam_maps", 1000, unsafeTitle, "", false));
    const std::vector<std::int64_t> validIds = {
        1000, 1520915243LL, 2147483648LL, 1003, 1004, 1005, 1006,
        1007, 1008, 1009, 1010, 1011, 1012, 1013
    };
    for (std::size_t i = 1; i < validIds.size(); ++i)
        items.push_back(catalogItem("steam_maps", validIds[i], "Map " + std::to_string(i)));
    auto state = catalogState(base, "steam_maps", 7, true, true, "ok", std::move(items));

    std::vector<std::int64_t> seen;
    for (std::size_t localPage = 0; localPage < 3; ++localPage) {
        const auto view = layout.view(scope, state);
        audit(view);
        require(view.page == CareerLayoutPage::WorkshopCatalog, "Local pagination left the catalog");
        require(view.body.find("Page " + std::to_string(localPage + 1) + " of 3") != std::string::npos,
                "Local pagination page count was incorrect");
        require(hasChoice(view, "nav.back"), "Back was not reachable on a catalog page");
        require(countPrefix(view, "catalog.open.") == (localPage < 2 ? 6u : 2u),
                "Catalog did not show the expected number of map rows");
        require(!hasChoice(view, "catalog.open.3") && !hasChoice(view, "catalog.open.4") &&
                !hasChoice(view, "catalog.open.5") && !hasChoice(view, "catalog.open.6") &&
                !hasChoice(view, "catalog.open.7") && !hasChoice(view, "catalog.open.9") &&
                !hasChoice(view, "catalog.open.10") && !hasChoice(view, "catalog.open.11") &&
                !hasChoice(view, "catalog.open.10000000000"),
                "Unsafe or untrusted catalog row was included");
        for (std::size_t offset = 0; offset < (localPage < 2 ? 6u : 2u); ++offset) {
            const std::int64_t sourceId = validIds[localPage * 6 + offset];
            const auto& row = findChoice(view, "catalog.open." + std::to_string(sourceId));
            require(row.enabled && row.action == "community_open_item", "Catalog item was not an open-item dispatch");
            require(row.payload == Json({{"source", "steam_maps"}, {"id", sourceId}}) &&
                    row.payload["id"].is_number_integer() && row.payload["id"].get<std::int64_t>() == sourceId,
                    "Catalog item id was not numeric or lost precision");
            seen.push_back(sourceId);
        }

        if (localPage == 0) {
            const auto& unsafe = findChoice(view, "catalog.open.1000");
            require(unsafe.label.find('<') == std::string::npos && unsafe.label.find('>') == std::string::npos &&
                    unsafe.label.find('&') == std::string::npos && unsafe.label.find('\n') == std::string::npos,
                    "Unsafe title characters reached the menu label");
            require(unsafe.label.find("Unknown creator") != std::string::npos,
                    "Missing creator did not use the safe fallback");
            require(unsafe.label.size() <= NativeCareerLayout::kMaxLabel,
                    "Catalog title exceeded the public label limit");
        }

        if (localPage < 2) {
            const auto& nextRows = findChoice(view, "catalog.page.next");
            require(nextRows.kind == CareerLayoutEffectKind::Navigate && nextRows.enabled,
                    "Next rows control was not reachable");
            require(choose(layout, view, nextRows.id, scope, state, false).page == CareerLayoutPage::WorkshopCatalog,
                    "Next rows navigation failed");
        } else {
            require(!hasChoice(view, "catalog.page.next"), "Last local page still offered Next rows");
            require(hasChoice(view, "catalog.page.previous"), "Previous rows was missing on a later page");
            const auto previousRows = choose(layout, view, "catalog.page.previous", scope, state, false);
            require(previousRows.accepted && previousRows.page == CareerLayoutPage::WorkshopCatalog,
                    "Previous rows navigation failed");
            const auto earlierPage = layout.view(scope, state);
            require(earlierPage.body.find("Page 2 of 3") != std::string::npos,
                    "Previous rows did not restore the earlier local page");
            require(choose(layout, earlierPage, "catalog.page.next", scope, state, false).accepted,
                    "Could not return to the last local page");
            const auto lastPage = layout.view(scope, state);
            const auto& onlineNext = findChoice(view, "catalog.page.online");
            require(onlineNext.enabled && onlineNext.kind == CareerLayoutEffectKind::Dispatch,
                    "Next online page was not reachable");
            const auto effect = choose(layout, lastPage, onlineNext.id, scope, state, true);
            require(effect.accepted && effect.action == "community_browse" &&
                    effect.payload == Json({{"source", "steam_maps"}, {"page", 8}, {"query", ""}}),
                    "Next online page dispatched the wrong source/page");
            const auto afterBrowse = layout.view(scope, state);
            const auto back = choose(layout, afterBrowse, "nav.back", scope, state, false);
            require(back.accepted && back.kind == CareerLayoutEffectKind::Navigate &&
                    back.page == CareerLayoutPage::Workshop, "Catalog Back did not return to Workshop");
        }
    }
    require(seen.size() == 14 && std::adjacent_find(seen.begin(), seen.end()) == seen.end(),
            "Local pagination did not expose every valid row exactly once");
}

void testFallbackLoadingAndStaleChoices() {
    const auto scope = ownedScope();
    const auto base = readyState(scope);
    NativeCareerLayout layout;
    enterCatalogFromMaps(layout, scope, base);

    auto view = layout.view(scope, base);
    audit(view);
    require(view.body.find("Choose a source, then Browse") != std::string::npos,
            "Unselected catalog did not show its fallback prompt");
    require(!hasChoice(view, "catalog.browse") && !hasChoice(view, "catalog.source.open"),
            "Unselected catalog exposed a source-specific action");
    const auto idleCancel = findChoice(view, "catalog.cancel");
    require(!idleCancel.enabled && idleCancel.action.empty(), "Idle catalog cancel was enabled");

    for (const auto& fallback : std::vector<std::pair<std::string, std::string>>{
             {"error", "The catalog page could not be read."},
             {"cancelled", "The catalog read was cancelled."},
             {"empty_page", "This catalog page listed no items."}}) {
        const auto state = catalogState(base, "steam_maps", 1, true, false, fallback.first, Json::array());
        const auto fallbackView = layout.view(scope, state);
        audit(fallbackView);
        require(fallbackView.body.find(fallback.second) != std::string::npos,
                "Catalog status fallback was missing for " + fallback.first);
        require(findChoice(fallbackView, "catalog.browse").enabled,
                "Browse fallback was disabled for " + fallback.first);
    }

    for (const auto& flags : std::vector<std::pair<bool, bool>>{{true, false}, {false, true}}) {
        auto loadingItems = Json::array({catalogItem("steam_maps", 41, "Loading row")});
        const auto loading = catalogState(base, "steam_maps", 1, true, true, "loading", std::move(loadingItems),
                                          flags.first, flags.second);
        const auto loadingView = layout.view(scope, loading);
        audit(loadingView);
        require(loadingView.body.find("Reading one public catalog page. Cancel stops it.") != std::string::npos,
                "Loading status was not visible");
        require(!findChoice(loadingView, "catalog.source.steam_maps").enabled &&
                !findChoice(loadingView, "catalog.browse").enabled &&
                !findChoice(loadingView, "catalog.open.41").enabled,
                "Catalog controls stayed enabled while loading");
        const auto cancel = findChoice(loadingView, "catalog.cancel");
        require(cancel.enabled && cancel.action == "community_browse_cancel" && cancel.payload.empty(),
                "Catalog loading could not be cancelled");
        const auto cancelled = choose(layout, loadingView, "catalog.cancel", scope, loading, true);
        require(cancelled.accepted && cancelled.action == "community_browse_cancel" && cancelled.payload.empty(),
                "Cancel dispatch was not accepted");
    }

    auto untrustedSourceItems = Json::array({catalogItem("steam_maps", 41, "Must not show")});
    const auto unknownSource = catalogState(base, "unknown_source", 1, true, true, "ok", std::move(untrustedSourceItems));
    const auto unknownView = layout.view(scope, unknownSource);
    audit(unknownView);
    require(!hasChoice(unknownView, "catalog.open.41") && !hasChoice(unknownView, "catalog.browse") &&
            !hasChoice(unknownView, "catalog.page.online"), "Unknown source produced catalog actions");

    auto originalItems = Json::array({catalogItem("steam_maps", 52, "Original title")});
    auto originalState = catalogState(base, "steam_maps", 1, true, false, "ok", std::move(originalItems));
    const auto originalView = layout.view(scope, originalState);
    const auto oldChoice = findChoice(originalView, "catalog.open.52");
    auto removedState = catalogState(base, "steam_maps", 1, true, false, "ok", Json::array());
    const auto removed = layout.choose(oldChoice, scope, removedState, true);
    require(!removed.accepted && removed.action.empty() && removed.refusal == CareerLayoutRefusal::StaleChoice,
            "Removed catalog item accepted an old choice");

    auto renamedItems = Json::array({catalogItem("steam_maps", 52, "Changed title")});
    const auto renamedState = catalogState(base, "steam_maps", 1, true, false, "ok", std::move(renamedItems));
    const auto renamed = layout.choose(oldChoice, scope, renamedState, true);
    require(!renamed.accepted && renamed.action.empty() && renamed.refusal == CareerLayoutRefusal::StaleChoice,
            "Renamed catalog item accepted a stale rendered choice");
}

void testMaxChoicesBackAndActivationStayDisabled() {
    const auto scope = ownedScope();
    const auto base = readyState(scope);
    NativeCareerLayout layout;
    enterCatalogFromMods(layout, scope, base);

    Json items = Json::array();
    for (int i = 0; i < 70; ++i)
        items.push_back(catalogItem("bakkes_plugins", 2000 + i, "Plugin " + std::to_string(i)));
    const auto state = catalogState(base, "bakkes_plugins", 1, true, true, "ok", std::move(items));
    std::vector<int> reachable;
    for (std::size_t page = 0; page < 10; ++page) {
        const auto view = layout.view(scope, state);
        audit(view);
        require(view.choices.size() <= NativeCareerLayout::kMaxChoices,
                "Large plugin page exceeded 24 choices");
        require(hasChoice(view, "nav.back"), "Back was dropped from a full plugin page");
        require(countPrefix(view, "catalog.open.") == 6 && countPrefix(view, "catalog.plugin.") == 6,
                "Plugin catalog did not show a complete local slice");
        for (int i = 0; i < 6; ++i) reachable.push_back(2000 + static_cast<int>(page) * 6 + i);
        if (page < 9) {
            const auto& next = findChoice(view, "catalog.page.next");
            require(choose(layout, view, next.id, scope, state, false).accepted,
                    "Could not reach a later local plugin page");
        } else {
            require(!hasChoice(view, "catalog.page.next"), "Last capped local page still had More rows");
            require(findChoice(view, "catalog.open.2059").enabled,
                    "The last row inside the public row cap was unreachable");
            require(!hasChoice(view, "catalog.open.2060"), "Rows beyond the public cap were exposed");
            const auto back = choose(layout, view, "nav.back", scope, state, false);
            require(back.accepted && back.page == CareerLayoutPage::WorkshopMods,
                    "Back from the plugin catalog did not return to Mods at the choice limit");
        }
    }
    require(reachable.size() == 60 && std::adjacent_find(reachable.begin(), reachable.end()) == reachable.end(),
            "Local plugin pagination did not expose every capped row once");

    NativeCareerLayout community;
    require(community.open(scope, base), "Could not open layout for plugin activation safety");
    const auto root = community.view(scope, base);
    require(choose(community, root, NativeCareerLayout::kCommunity, scope, base, false).page ==
            CareerLayoutPage::Community, "Could not open legacy Community page");
    const auto communityView = community.view(scope, base);
    const auto activate = findChoice(communityView, "community.activate");
    require(!activate.enabled && activate.action.empty() && activate.payload.empty() &&
            activate.reason == NativeCareerLayout::kActivationReason,
            "Existing Community activation control was enabled");
}

void testWorkshopCatalogPreservesEntryCategoryAndFiltersOtherSources() {
    const auto scope = ownedScope();
    const auto fresh = backendReadyState(scope);

    // Starting from the real backend default source must not turn the Mods
    // destination into a Training Maps catalog or expose map rows.
    NativeCareerLayout freshMods;
    enterCatalogFromMods(freshMods, scope, fresh);
    const auto freshModsView = freshMods.view(scope, fresh);
    audit(freshModsView);
    require(freshModsView.page == CareerLayoutPage::WorkshopCatalog &&
            freshModsView.title == "Workshop - Mods catalog",
            "Mods entry inherited the fresh backend's default Maps category");
    require(countPrefix(freshModsView, "catalog.open.") == 0 &&
            countPrefix(freshModsView, "catalog.plugin.") == 0,
            "Fresh Mods catalog displayed rows before a plugin source was selected");
    require(hasChoice(freshModsView, "catalog.source.bakkes_plugins"),
            "Mods catalog did not offer its BakkesMod plugin source");

    // A successful prior Maps read may still be in backend state. Its rows
    // stay hidden on the Mods route until the plugin-source result replaces it.
    auto staleMaps = catalogState(fresh, "steam_maps", 1, true, true, "ok",
        Json::array({catalogItem("steam_maps", 91, "Stale map result")}));
    NativeCareerLayout mods;
    enterCatalogFromMods(mods, scope, staleMaps);
    auto modsView = mods.view(scope, staleMaps);
    require(modsView.title == "Workshop - Mods catalog" &&
            !hasChoice(modsView, "catalog.open.91"),
            "Stale Steam map row leaked into the Mods catalog");

    const auto& pluginSource = findChoice(modsView, "catalog.source.bakkes_plugins");
    const auto browsePlugins = choose(mods, modsView, pluginSource.id, scope, staleMaps, true);
    require(browsePlugins.accepted && browsePlugins.action == "community_browse" &&
            browsePlugins.payload == Json({{"source", "bakkes_plugins"}, {"page", 1}, {"query", ""}}),
            "Mods catalog did not request its own source");
    modsView = mods.view(scope, staleMaps);
    require(!hasChoice(modsView, "catalog.open.91"),
            "Stale Maps rows appeared while the plugin-source request was pending");

    const auto pluginState = catalogState(staleMaps, "bakkes_plugins", 1, true, true, "ok",
        Json::array({catalogItem("bakkes_plugins", 223, "Training Plugin")}));
    const auto pluginView = mods.view(scope, pluginState);
    audit(pluginView);
    require(pluginView.title == "Workshop - Mods catalog" &&
            hasChoice(pluginView, "catalog.open.223") && hasChoice(pluginView, "catalog.plugin.223"),
            "BakkesPlugins result did not populate the Mods catalog");
    require(!hasChoice(pluginView, "catalog.open.91"),
            "A stale Maps row remained beside plugin results");

    const auto modsBack = choose(mods, pluginView, "nav.back", scope, pluginState, false);
    require(modsBack.accepted && modsBack.page == CareerLayoutPage::WorkshopMods,
            "Back from the plugin catalog did not return to Mods");
    const auto returnedMods = mods.view(scope, pluginState);
    require(returnedMods.page == CareerLayoutPage::WorkshopMods &&
            returnedMods.title == "Workshop - Mods",
            "Plugin catalog Back returned to a different Workshop category");

    // Switching to Training Maps after plugin results must keep plugin rows
    // out of the Maps catalog until a map source is read.
    const auto workshopBack = choose(mods, returnedMods, "nav.back", scope, pluginState, false);
    require(workshopBack.accepted && workshopBack.page == CareerLayoutPage::Workshop,
            "Back from Mods did not return to Workshop");
    const auto workshop = mods.view(scope, pluginState);
    const auto mapsNav = choose(mods, workshop, "workshop.catalog.open", scope, pluginState, false);
    require(mapsNav.accepted && mapsNav.page == CareerLayoutPage::WorkshopCatalog,
            "Training Maps catalog could not be opened after plugin results");
    const auto mapsView = mods.view(scope, pluginState);
    audit(mapsView);
    require(mapsView.title == "Workshop - Training Maps catalog" &&
            !hasChoice(mapsView, "catalog.open.223") && !hasChoice(mapsView, "catalog.plugin.223"),
            "Plugin rows leaked into the Training Maps catalog");
    require(hasChoice(mapsView, "catalog.source.steam_maps") &&
            hasChoice(mapsView, "catalog.source.bakkes_maps"),
            "Training Maps catalog lost its map-source choices");

    const auto mapsBack = choose(mods, mapsView, "nav.back", scope, pluginState, false);
    require(mapsBack.accepted && mapsBack.page == CareerLayoutPage::Workshop,
            "Back from Training Maps catalog did not return to Workshop maps");

    // The existing Community entry is another Maps route, but Back must return
    // to Community rather than detouring through Workshop.
    NativeCareerLayout community;
    require(community.open(scope, pluginState), "Could not open layout for Community-origin route");
    const auto root = community.view(scope, pluginState);
    require(choose(community, root, NativeCareerLayout::kCommunity, scope, pluginState, false).page ==
            CareerLayoutPage::Community, "Could not open the existing Community page");
    const auto communityView = community.view(scope, pluginState);
    const auto communityCatalog = choose(community, communityView, "community.catalog", scope,
                                         pluginState, false);
    require(communityCatalog.accepted && communityCatalog.page == CareerLayoutPage::WorkshopCatalog,
            "Community did not enter the shared catalog");
    const auto communityCatalogView = community.view(scope, pluginState);
    require(communityCatalogView.title == "Workshop - Training Maps catalog" &&
            !hasChoice(communityCatalogView, "catalog.open.223") &&
            !hasChoice(communityCatalogView, "catalog.plugin.223"),
            "Community Maps route inherited stale plugin results");
    const auto communityBack = choose(community, communityCatalogView, "nav.back", scope,
                                      pluginState, false);
    require(communityBack.accepted && communityBack.page == CareerLayoutPage::Community,
            "Back from Community catalog did not return to its entry page");
}
} // namespace

int main() {
    try {
        static_assert(!NativeCareerLayout::kProductionGateEnabled);
        static_assert(!NativeCareerLayout::kNativeReplacementFinished);
        static_assert(!NativeCareerLayout::kSuppressionEnforced);
        static_assert(!NativeCareerLayout::kCompatibilityGrant);
        testNavigationAndSourceDispatch();
        testRowsPaginationPayloadAndSanitization();
        testFallbackLoadingAndStaleChoices();
        testMaxChoicesBackAndActivationStayDisabled();
        testWorkshopCatalogPreservesEntryCategoryAndFiltersOtherSources();
    } catch (const std::exception& error) {
        std::cerr << "FAIL " << error.what() << "\n";
        return 1;
    }
    std::cout << "native workshop catalog tests passed\n";
    return 0;
}
