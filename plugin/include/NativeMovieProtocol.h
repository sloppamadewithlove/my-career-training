#pragma once

#include "NativeCareerLayout.h"
#include "NativeMatchLayout.h"
#include "NativeReturnGate.h"
#include <cmath>

namespace mct {

// Development transport for the authored native movie. The caller supplies the
// live owned-session scope; a JSON document never grants ownership or freshness.
// Cosmetic authority is the NativeCosmeticContext argument, never movie JSON.
// Workshop authority is the NativeWorkshopContext argument, never movie JSON.
// No engine calls, files, console commands or production gates live here.
class NativeMovieProtocol {
public:
    static constexpr const char* kLogCategory = "MCT_NATIVE_UI_V1";
    static constexpr std::size_t kMaxCommandBytes = 2048;
    static constexpr std::size_t kMaxViewBytes = 65536;
    static constexpr bool kRuntimeVerified = false;
    static constexpr bool kProductionReady = false;

    bool open(const CareerLayoutScope& scope, const Json& state, const NativeCosmeticContext& cosmetics = {},
              const NativeWorkshopContext& workshop = {}) {
        invalidate();
        lastSignature_.clear();
        surface_ = scope.surface;
        return surface_ == NativeMenuSurface::Frontend ? layout_.open(scope, state, cosmetics, workshop) :
            matchLayout_.open(scope, state);
    }

    Json publish(const CareerLayoutScope& scope, const Json& state, double now,
                 const NativeCosmeticContext& cosmetics = {}, const NativeWorkshopContext& workshop = {},
                 bool returnPending = false, const Json& navigation = Json::object(), bool returnReady = false,
                 bool returnHoldAllowed = true) {
        Json wire = {{"protocol", 1}, {"session", scope.nonce}, {"surface", nativeSurfaceName(scope.surface)}, {"published_at", now},
            {"active", false}, {"runtime_verified", kRuntimeVerified}, {"production_ready", kProductionReady},
            {"controls", Json::array()}, {"return_pending", false}, {"return_hold", false}};
        if (!std::isfinite(now) || now <= 0) {
            wire["published_at"] = 0;
            invalidate();
            return wire;
        }
        const bool returnHold = returnPending && returnHoldAllowed && stringValue(state, "error").empty();
        auto view = scope.surface != surface_ ? CareerLayoutView{} :
            surface_ == NativeMenuSurface::Frontend ? layout_.view(scope, state, cosmetics, workshop) :
            matchLayout_.view(scope, state, returnPending, returnHold);
        if (!view.offersReplacement) {
            invalidate();
            return wire;
        }
        if (scope.surface == NativeMenuSurface::Frontend && view.page == CareerLayoutPage::Root) {
            view.choices.erase(std::remove_if(view.choices.begin(), view.choices.end(), [](const CareerLayoutChoice& choice) {
                return choice.id == NativeCareerLayout::kWorkshop || choice.id == NativeCareerLayout::kCommunity;
            }), view.choices.end());
        } else if (view.browser.active) {
            view.choices.erase(std::remove_if(view.choices.begin(), view.choices.end(), [](const CareerLayoutChoice& choice) {
                return choice.id != "nav.back";
            }), view.choices.end());
        }
        for (auto& choice : view.choices) {
            if (returnPending && ((choice.kind == CareerLayoutEffectKind::Dispatch &&
                !NativeReturnGate::permitsAction(choice.action)) || choice.kind == CareerLayoutEffectKind::LocalWorkshop ||
                choice.id == "pause.return" || choice.id == "match.confirm_return")) {
                choice.enabled = false;
                choice.reason = "Wait until My Career has returned to the hub.";
            }
        }
        if (returnPending) {
            view.title = returnHold ? "Leaving..." : "Return needs attention";
            view.body = !stringValue(state, "error").empty()
                ? "Could not finish saving. Retry saving before returning, or choose Quit My Career."
                : !returnHold ? (scope.surface == NativeMenuSurface::Pause
                    ? "Return has not been confirmed. If the menu closes, press Escape or Start to reopen it. You can also choose Quit My Career."
                    : "Return has not been confirmed. You can open Settings or choose Quit My Career.")
                : returnReady ? "Progress saved. Opening My Career..."
                : "Saving progress and stopping bot control. Please wait.";
        }
        const auto authorized = returnPending && validNavigation(navigation) &&
            (scope.surface == NativeMenuSurface::Pause || scope.surface == NativeMenuSurface::Results)
            ? navigation : Json::object();
        Json signature = {{"title", view.title}, {"body", view.body}, {"choices", Json::array()},
            {"browser", browserBinding(view.browser)}};
        signature["navigation"] = authorized;
        signature["return_pending"] = returnPending;
        signature["return_hold"] = returnHold;
        for (const auto& choice : view.choices) {
            // Include the full binding, even when its visible label is unchanged.
            // Cosmetic fields stay in this retained signature. They are not copied
            // onto the controls sent to the movie.
            signature["choices"].push_back(binding(choice));
        }
        const auto encoded = signature.dump();
        if (!published_ || encoded != lastSignature_) {
            if (!advance()) return wire;
            shown_ = std::move(view.choices);
            shownBrowser_ = std::move(view.browser);
            lastSignature_ = encoded;
            published_ = true;
        }
        wire["active"] = true;
        wire["generation"] = std::to_string(generation_);
        wire["title"] = view.title;
        wire["body"] = view.body;
        if (shownBrowser_.active) wire["browser"] = browserWire(shownBrowser_);
        wire["return_pending"] = returnPending_ = returnPending;
        wire["return_hold"] = returnHold_ = returnHold;
        navigation_ = authorized;
        if (!navigation_.empty()) wire["navigation"] = navigation_;
        for (const auto& choice : shown_) {
            wire["controls"].push_back({{"id", choice.id}, {"label", choice.label},
                {"enabled", choice.enabled}, {"reason", choice.reason},
                {"stock", choice.stock == StockRoute::Garage ? "garage" :
                    choice.stock == StockRoute::Options ? "options" : choice.stock == StockRoute::Resume ? "resume" :
                    choice.stock == StockRoute::Preset ? "preset" : choice.stock == StockRoute::Settings ? "settings" : ""},
                {"revision", std::to_string(choice.revision)},
                {"return_commit", choice.kind == CareerLayoutEffectKind::Dispatch &&
                    (choice.action == "return_hub" || choice.action == "forfeit_match" ||
                     choice.action == "prepare_next_match")}});
        }
        nonce_ = scope.nonce;
        scopeGeneration_ = scope.generation;
        return wire;
    }

    CareerLayoutEffect select(const std::string& message, const CareerLayoutScope& live,
                              const Json& state, bool customMovieCallback,
                              const NativeCosmeticContext& cosmetics = {},
                              const NativeWorkshopContext& workshop = {}) {
        CareerLayoutEffect refused;
        refused.reason = "The menu changed. Choose the control again.";
        if (!customMovieCallback || !published_ || message.size() > kMaxCommandBytes) return refused;
        try {
            const auto command = Json::parse(message);
            if (command.is_object() && command.contains("browser_op")) {
                // Exact key set and exact types before any dispatch. A missing or
                // non-string value is refused; it is never read as an empty search.
                if (!exactBrowserCommand(command) || live.surface != surface_ || live.generation != scopeGeneration_ ||
                    stringValue(command, "surface") != nativeSurfaceName(surface_) ||
                    stringValue(command, "session") != nonce_ ||
                    stringValue(command, "generation") != std::to_string(generation_) ||
                    stringValue(command, "revision") != std::to_string(shownBrowser_.revision) || !shownBrowser_.active)
                    return refused;
                const auto op = stringValue(command, "browser_op");
                const auto value = stringValue(command, "value");
                if (op != "tab" && op != "search" && op != "scroll" && op != "primary" && op != "favorite" &&
                    op != "tool")
                    return refused;
                if (value.size() > NativeCareerLayout::kMaxBrowserKey ||
                    (op == "search" && value.size() > NativeCareerLayout::kMaxBrowserQuery)) return refused;
                const TrainingBrowserRow* publishedRow = nullptr;
                const TrainingBrowserTool* publishedTool = nullptr;
                if (op == "primary" || op == "favorite") {
                    for (const auto& row : shownBrowser_.rows) if (row.key == value) { publishedRow = &row; break; }
                    if (!publishedRow) return refused;
                }
                if (op == "tool") {
                    for (const auto& tool : shownBrowser_.tools) if (tool.key == value) { publishedTool = &tool; break; }
                    if (!publishedTool) return refused;
                }
                auto effect = layout_.chooseBrowser(op, value, live, state, workshop, publishedRow, publishedTool);
                if (effect.accepted) invalidate();
                return effect;
            }
            const bool legacy = surface_ == NativeMenuSurface::Frontend && !command.contains("surface");
            if (!command.is_object() || command.size() != (legacy ? 5 : 6) || live.surface != surface_ ||
                live.generation != scopeGeneration_ ||
                (!legacy && stringValue(command, "surface") != nativeSurfaceName(surface_)) ||
                !command.contains("protocol") || !command["protocol"].is_number_integer() ||
                command["protocol"] != 1 || stringValue(command, "session") != nonce_ ||
                stringValue(command, "generation") != std::to_string(generation_)) return refused;
            const auto id = stringValue(command, "control");
            const auto revision = stringValue(command, "revision");
            for (const auto& choice : shown_) {
                if (choice.id != id || std::to_string(choice.revision) != revision) continue;
                // The authored movie calls only its own dispatcher. It has no
                // stock click to replay after this callback returns.
                auto effect = surface_ == NativeMenuSurface::Frontend ?
                    layout_.choose(choice, live, state, true, cosmetics, workshop) :
                    matchLayout_.choose(choice, live, state, true, returnPending_, returnHold_);
                if (effect.accepted) invalidate();
                return effect;
            }
        } catch (const Json::exception&) {
            return refused;
        }
        return refused;
    }

    void invalidate() {
        published_ = false;
        shown_.clear();
        shownBrowser_ = {};
        nonce_.clear();
        navigation_ = Json::object();
    }

    bool navigationConsumedMessage(const std::string& message, const CareerLayoutScope& live) const {
        return navigationMessage(message, live, false);
    }

    bool navigationIssuedMessage(const std::string& message, const CareerLayoutScope& live) const {
        return navigationMessage(message, live, true);
    }

    bool navigationMessage(const std::string& message, const CareerLayoutScope& live, bool issued) const {
        const auto phase = stringValue(navigation_, "phase");
        if (!published_ || navigation_.empty() || message.size() > kMaxCommandBytes ||
            live.surface != surface_ || live.nonce != nonce_ || live.generation != scopeGeneration_ ||
            !live.owned || !live.offline || !live.fresh || live.online ||
            (issued ? phase != "execute" : phase != "authorize" && phase != "execute")) return false;
        const auto expectedGeneration = !issued && phase == "execute"
            ? stringValue(navigation_, "consumed_generation") : std::to_string(generation_);
        try {
            const auto event = Json::parse(message);
            return event.is_object() && event.size() == (issued ? 9 : 8) && event.contains("protocol") &&
                event["protocol"].is_number_integer() && event["protocol"] == 1 &&
                stringValue(event, "event") == (issued ? "return_navigation_issued" : "return_navigation_consumed") &&
                stringValue(event, "session") == nonce_ &&
                stringValue(event, "surface") == nativeSurfaceName(surface_) &&
                stringValue(event, "generation") == expectedGeneration &&
                stringValue(event, "intent") == stringValue(navigation_, "intent") &&
                stringValue(event, "activity") == stringValue(navigation_, "activity") &&
                event.contains("fixture") && event["fixture"].is_string() &&
                event["fixture"] == navigation_["fixture"] &&
                (!issued || (event.contains("consumed_generation") && event["consumed_generation"].is_string() &&
                    event["consumed_generation"] == navigation_["consumed_generation"]));
        } catch (const Json::exception&) { return false; }
    }

    bool readyMessage(const std::string& message, const CareerLayoutScope& live, bool requireGeneration = false) const {
        if (!published_ || live.surface != surface_ || live.nonce != nonce_ ||
            live.generation != scopeGeneration_ || !live.owned ||
            !live.offline || !live.fresh || live.online) return false;
        try {
            const auto command = Json::parse(message);
            if (!command.is_object() || !command.contains("protocol") || !command["protocol"].is_number_integer() ||
                command["protocol"] != 1 || stringValue(command, "session") != nonce_ ||
                stringValue(command, "event") != "ready") return false;
            if (!requireGeneration && surface_ == NativeMenuSurface::Frontend && command.size() == 3) return true;
            return command.size() == 5 && stringValue(command, "surface") == nativeSurfaceName(surface_) &&
                stringValue(command, "generation") == std::to_string(generation_);
        } catch (const Json::exception&) { return false; }
    }

private:
    // Browser commands carry exactly these seven keys with these exact types.
    // Nothing is coerced: a missing or non-string value is refused rather than
    // treated as an empty search, and no extra key is tolerated.
    static bool exactBrowserCommand(const Json& command) {
        if (!command.is_object() || command.size() != 7) return false;
        if (!command.contains("protocol") || !command["protocol"].is_number_integer() ||
            command["protocol"] != 1) return false;
        for (const char* key : {"session", "surface", "generation", "revision", "browser_op", "value"})
            if (!command.contains(key) || !command[key].is_string()) return false;
        return true;
    }
    static const char* browserTab(TrainingBrowserTab tab) {
        switch (tab) {
        case TrainingBrowserTab::Lessons: return "lessons";
        case TrainingBrowserTab::Workshop: return "workshop";
        case TrainingBrowserTab::Mods: return "mods";
        case TrainingBrowserTab::Favorites: return "favorites";
        }
        return "lessons";
    }
    static const char* browserState(TrainingBrowserState state) {
        switch (state) {
        case TrainingBrowserState::Ready: return "ready";
        case TrainingBrowserState::Empty: return "empty";
        case TrainingBrowserState::Loading: return "loading";
        case TrainingBrowserState::Error: return "error";
        }
        return "error";
    }
    static Json browserBinding(const TrainingBrowserView& browser) {
        Json value = {{"active", browser.active}, {"tab", browserTab(browser.tab)}, {"state", browserState(browser.state)},
            {"query", browser.query}, {"offset", browser.offset}, {"total", browser.total},
            {"has_more", browser.hasMore},
            {"revision", std::to_string(browser.revision)}, {"rows", Json::array()}};
        for (const auto& row : browser.rows)
            value["rows"].push_back({{"key", row.key}, {"type", row.type}, {"id", row.itemId}, {"title", row.title},
                {"subtitle", row.subtitle}, {"detail", row.detail}, {"primary_label", row.primaryLabel},
                {"primary_enabled", row.primaryEnabled}, {"favorite", row.favorite}, {"reason", row.reason},
                {"action", row.action}, {"payload", row.payload}, {"workshop_row", row.workshop.rowId},
                {"workshop_path", row.workshop.packagePath}, {"workshop_root", row.workshop.contentRoot},
                {"workshop_id", row.workshop.workshopId}, {"workshop_nonce", row.workshop.nonce},
                {"workshop_generation", std::to_string(row.workshop.generation)},
                {"workshop_stamp", std::to_string(row.workshopStamp)}});
        value["tools"] = Json::array();
        for (const auto& tool : browser.tools)
            value["tools"].push_back({{"key", tool.key}, {"label", tool.label}, {"enabled", tool.enabled},
                {"reason", tool.reason}, {"action", tool.action}, {"payload", tool.payload}});
        return value;
    }
    static Json browserWire(const TrainingBrowserView& browser) {
        Json value = {{"tab", browserTab(browser.tab)}, {"state", browserState(browser.state)}, {"query", browser.query},
            {"offset", browser.offset}, {"total", browser.total}, {"has_more", browser.hasMore}, {"active", browser.active},
            {"revision", std::to_string(browser.revision)},
            {"rows", Json::array()}};
        for (const auto& row : browser.rows)
            value["rows"].push_back({{"key", row.key}, {"title", row.title}, {"subtitle", row.subtitle},
                {"detail", row.detail}, {"primary_label", row.primaryLabel}, {"primary_enabled", row.primaryEnabled},
                {"favorite", row.favorite}, {"reason", row.reason}});
        value["tools"] = Json::array();
        for (const auto& tool : browser.tools)
            value["tools"].push_back({{"key", tool.key}, {"label", tool.label},
                {"enabled", tool.enabled}, {"reason", tool.reason}});
        return value;
    }
    static bool validNavigation(const Json& value) {
        const auto phase = stringValue(value, "phase");
        if (!value.is_object() || (phase != "authorize" && phase != "execute") ||
            value.size() != (phase == "execute" ? 5 : 4) || !value.contains("fixture") ||
            !value["fixture"].is_string()) return false;
        if (phase == "execute") {
            const auto generation = stringValue(value, "consumed_generation");
            if (generation.empty() || generation.size() > 20 || generation.front() == '0' ||
                (generation.size() == 20 && generation > "18446744073709551615")) return false;
            for (const auto c : generation) if (c < '0' || c > '9') return false;
        }
        const auto intent = stringValue(value, "intent");
        const auto activity = stringValue(value, "activity");
        if (intent.size() != 32 || activity.empty() || activity.size() > 128 ||
            value["fixture"].get<std::string>().size() > 128) return false;
        for (const auto c : intent) if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'))) return false;
        return true;
    }
    static Json binding(const CareerLayoutChoice& choice) {
        Json draft = Json::array();
        const int count = choice.cosmetic.draftCount < 0 ? 0
            : (std::min)(choice.cosmetic.draftCount, kNativeCosmeticDraftCap);
        for (int index = 0; index < count; ++index) {
            const auto& item = choice.cosmetic.draft[static_cast<std::size_t>(index)];
            draft.push_back({{"slot", item.slot}, {"product", item.productId},
                {"paint", item.paint}, {"paintable", item.paintable}});
        }
        return {{"id", choice.id}, {"label", choice.label}, {"enabled", choice.enabled},
            {"reason", choice.reason}, {"kind", int(choice.kind)}, {"target", int(choice.target)},
            {"stock", int(choice.stock)}, {"action", choice.action}, {"payload", choice.payload},
            {"page", choice.page}, {"lesson", choice.lessonId}, {"career", choice.careerId},
            {"fixture", choice.fixtureId}, {"recruit", choice.recruitId}, {"item", choice.itemId},
            {"revision", std::to_string(choice.revision)},
            {"cosmetic_kind", int(choice.cosmetic.kind)}, {"cosmetic_slot", choice.cosmetic.slot},
            {"cosmetic_product", choice.cosmetic.productId}, {"cosmetic_paint", choice.cosmetic.paint},
            {"cosmetic_paintable", choice.cosmetic.paintable},
            {"cosmetic_pending", choice.cosmetic.restorationPending},
            {"cosmetic_count", choice.cosmetic.draftCount}, {"cosmetic_draft", std::move(draft)},
            {"cosmetic_override", choice.cosmetic.overrideColors},
            {"cosmetic_palette", choice.cosmetic.paletteIndex},
            {"cosmetic_primary", {choice.cosmetic.primary[0], choice.cosmetic.primary[1], choice.cosmetic.primary[2]}},
            {"cosmetic_secondary", {choice.cosmetic.secondary[0], choice.cosmetic.secondary[1], choice.cosmetic.secondary[2]}},
            {"cosmetic_stamp", std::to_string(choice.cosmeticStamp)},
            {"workshop_row", choice.workshop.rowId}, {"workshop_id", choice.workshop.workshopId},
            {"workshop_root", choice.workshop.contentRoot}, {"workshop_path", choice.workshop.packagePath},
            {"workshop_nonce", choice.workshop.nonce},
            {"workshop_generation", std::to_string(choice.workshop.generation)},
            {"workshop_stamp", std::to_string(choice.workshopStamp)}};
    }

    bool advance() {
        if (generation_ == std::numeric_limits<std::uint64_t>::max()) {
            invalidate();
            return false;
        }
        ++generation_;
        return true;
    }
    NativeCareerLayout layout_;
    NativeMatchLayout matchLayout_;
    NativeMenuSurface surface_ = NativeMenuSurface::None;
    std::vector<CareerLayoutChoice> shown_;
    TrainingBrowserView shownBrowser_;
    std::string nonce_;
    std::string lastSignature_;
    Json navigation_ = Json::object();
    std::uint64_t generation_ = 0;
    std::uint64_t scopeGeneration_ = 0;
    bool published_ = false;
    bool returnPending_ = false;
    bool returnHold_ = false;
};
}
