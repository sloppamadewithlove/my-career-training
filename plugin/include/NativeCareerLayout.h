#pragma once

#include "LocalBridge.h"
#include "NativeCareerManagement.h"
#include "NativeCosmeticContext.h"
#include "NativeWorkshopContext.h"

#include <algorithm>
#include <cstring>
#include <cstdint>
#include <limits>
#include <string>
#include <unordered_set>
#include <vector>

namespace mct {

// Presentation and routing plan for a future engine binding adapter.
// This class does not draw, write memory, send bridge commands, or launch the game.
// Local appearance reads NativeCosmeticContext on each call and returns a typed
// request. It does not read that catalog from worker JSON or movie JSON.
// It is not a finished native menu replacement and it does not enable a production gate.
// A consumed-original acknowledgement is only a precondition for a custom dispatch.
// Route suppression is a binding plan; this model does not claim clicks are blocked.

enum class CareerLayoutPage {
    Root, Career, Training, Lesson, Schedule, Standings, Squad, Garage, Workshop, Community, Settings,
    Appearance, CosmeticItems, CosmeticPaints, CosmeticColors, CosmeticPrimary, CosmeticAccent,
    CreateCareer, CareerRules, RecoverCareer, WorkshopMods, WorkshopCatalog
};

enum class TrainingBrowserTab { Lessons, Workshop, Mods };
enum class TrainingBrowserState { Ready, Empty, Loading, Error };

struct TrainingBrowserRow {
    std::string key;
    std::string type;
    std::string itemId;
    std::string title;
    std::string subtitle;
    std::string detail;
    std::string primaryLabel;
    bool primaryEnabled = false;
    bool favorite = false;
    std::string reason;
    std::string action;
    Json payload = Json::object();
    NativeWorkshopRequest workshop;
    std::uint64_t workshopStamp = 0;
};

struct TrainingBrowserTool {
    std::string key;
    std::string label;
    bool enabled = false;
    std::string reason;
    std::string action;
    Json payload = Json::object();
};

struct TrainingBrowserView {
    bool active = false;
    TrainingBrowserTab tab = TrainingBrowserTab::Lessons;
    TrainingBrowserState state = TrainingBrowserState::Ready;
    std::string query;
    std::size_t offset = 0;
    std::size_t total = 0;
    std::vector<TrainingBrowserRow> rows;
    std::vector<TrainingBrowserTool> tools;
    // True only when the current catalog tab has a next page that a user scroll
    // at the last row may request. Never a background or per-poll read.
    bool hasMore = false;
    std::uint64_t revision = 0;
};

// Fixed public catalog sources. There is no string parser and no arbitrary URL.
enum class CatalogSource { None, SteamMaps, BakkesMaps, BakkesPlugins };

inline const char* catalogSourceName(CatalogSource source) {
    switch (source) {
    case CatalogSource::SteamMaps: return "steam_maps";
    case CatalogSource::BakkesMaps: return "bakkes_maps";
    case CatalogSource::BakkesPlugins: return "bakkes_plugins";
    default: return "";
    }
}

inline CatalogSource catalogSourceOf(const std::string& name) {
    if (name == "steam_maps") return CatalogSource::SteamMaps;
    if (name == "bakkes_maps") return CatalogSource::BakkesMaps;
    if (name == "bakkes_plugins") return CatalogSource::BakkesPlugins;
    return CatalogSource::None;
}

// Which Workshop entry opened the catalog. The backend community_catalog.source
// is shared and may still hold the other entry's result, so the intended
// category is kept in layout navigation state instead.
enum class CatalogCategory { None, Maps, Plugins };

inline bool catalogCategoryHas(CatalogCategory category, CatalogSource source) {
    if (source == CatalogSource::None) return false;
    if (category == CatalogCategory::Maps)
        return source == CatalogSource::SteamMaps || source == CatalogSource::BakkesMaps;
    if (category == CatalogCategory::Plugins) return source == CatalogSource::BakkesPlugins;
    // No category was recorded (legacy Community entry): any fixed source is allowed.
    return true;
}

enum class CareerLayoutEffectKind {
    None, Navigate, PreserveStockRoute, Dispatch, Unavailable, LocalCosmetic, LocalWorkshop
};

enum class CareerLayoutRefusal {
    None, NoPlan, StaleScope, StaleChoice, NotConsumed, Disabled, UnknownControl
};

enum class StockRoute { None, Garage, Options, Resume, Preset, Settings };

enum class NativeMenuSurface { None, Frontend, Pause, Results };

inline const char* nativeSurfaceName(NativeMenuSurface surface) {
    switch (surface) {
    case NativeMenuSurface::Frontend: return "frontend";
    case NativeMenuSurface::Pause: return "pause";
    case NativeMenuSurface::Results: return "results";
    default: return "";
    }
}

// Fixed native routes. There is no string parser and no catch-all callback sink.
enum class NativeRouteId : int {
    OnlineMatchmaking = 1,
    TournamentJoin = 2,
    Store = 3,
    RocketPass = 4,
    Account = 5,
    Party = 6,
    AccountCloudSync = 7,
    Garage = 8,
    Options = 9,
    Unlisted = 10
};

enum class NativeRoutePlan { Passthrough, Suppress, PreserveStock };

struct CareerLayoutScope {
    bool owned = false;
    bool offline = false;
    bool fresh = false;
    bool online = true;
    std::string nonce;
    std::uint64_t generation = 0;
    NativeMenuSurface surface = NativeMenuSurface::Frontend;
    bool matchInProgress = false;  // Fresh owned-server observation; never supplied by the movie.
};

struct CareerLayoutChoice {
    std::string id;
    std::string label;
    bool enabled = false;
    std::string reason;
    CareerLayoutEffectKind kind = CareerLayoutEffectKind::None;
    CareerLayoutPage target = CareerLayoutPage::Root;
    StockRoute stock = StockRoute::None;
    std::string action;
    Json payload = Json::object();
    std::size_t page = 0;
    std::string lessonId;
    std::string careerId;
    std::string fixtureId;
    std::string recruitId;
    std::string itemId;
    // Local appearance binding. Navigate choices may carry a slot here with kind None.
    // LocalCosmetic choices carry the request the plugin should apply after revalidation.
    NativeCosmeticRequest cosmetic;
    // Catalog and draft stamp. Same visible label with a different stamp is stale.
    std::uint64_t cosmeticStamp = 0;
    // Local workshop binding. The movie never receives the path or command.
    NativeWorkshopRequest workshop;
    std::uint64_t workshopStamp = 0;
    // Catalog navigation state. Set on a Navigate choice that opens the catalog
    // so the intended category and Back target do not depend on the backend
    // community_catalog.source, which is shared between entries.
    CatalogCategory catalog = CatalogCategory::None;
    CareerLayoutPage catalogBack = CareerLayoutPage::Workshop;
    // Monotonic render generation. Logical ids stay stable; this value does not.
    std::uint64_t revision = 0;
};

struct CareerLayoutView {
    bool offersReplacement = false;
    bool suppressionEnforced = false;
    bool productionGateEnabled = false;
    bool nativeReplacementFinished = false;
    bool compatibilityGrant = false;
    CareerLayoutPage page = CareerLayoutPage::Root;
    std::string title;
    std::string body;
    std::vector<CareerLayoutChoice> choices;
    std::vector<NativeRouteId> suppress;
    TrainingBrowserView browser;
};

struct CareerLayoutEffect {
    bool accepted = false;
    CareerLayoutEffectKind kind = CareerLayoutEffectKind::None;
    CareerLayoutRefusal refusal = CareerLayoutRefusal::None;
    StockRoute stock = StockRoute::None;
    std::string action;
    Json payload = Json::object();
    CareerLayoutPage page = CareerLayoutPage::Root;
    bool leaveMenu = false;
    bool originalConsumptionRequired = false;
    bool originalConsumptionSatisfied = false;
    bool compatibilityGrant = false;
    bool consumesUnlistedCallback = false;
    std::string reason;
    // Set only for an accepted LocalCosmetic effect. Refusals leave this empty.
    NativeCosmeticRequest cosmetic;
    // Set only for an accepted LocalWorkshop effect. Refusals leave this empty.
    NativeWorkshopRequest workshop;
};

struct NativeRouteDecision {
    NativeRouteId route = NativeRouteId::Unlisted;
    NativeRoutePlan plan = NativeRoutePlan::Passthrough;
    bool suppressionRequired = false;
    bool enforcementVerified = false;
    bool consumesUnlisted = false;
};

class NativeCareerLayout {
public:
    static constexpr bool kProductionGateEnabled = false;
    static constexpr bool kNativeReplacementFinished = false;
    static constexpr bool kSuppressionEnforced = false;
    static constexpr bool kCompatibilityGrant = false;
    static constexpr bool kWritesMemory = false;
    static constexpr bool kTerminatesProcess = false;
    static constexpr std::size_t kMaxChoices = 24;
    static constexpr std::size_t kMaxBrowserRows = 32;
    static constexpr std::size_t kMaxBrowserTools = 8;
    static constexpr std::size_t kMaxBrowserQuery = 80;
    static constexpr std::size_t kMaxBrowserKey = 128;
    static constexpr std::size_t kMaxBrowserDisplay = 240;
    static constexpr std::size_t kMaxBody = 2000;
    static constexpr std::size_t kMaxLabel = 80;
    static constexpr std::size_t kMaxReason = 240;
    static constexpr std::size_t kLessonsPerPage = 4;
    static constexpr std::size_t kCosmeticItemsPerPage = 16;
    static constexpr std::size_t kMaxLessons = 96;
    static constexpr std::size_t kMaxRows = 8;
    static constexpr std::size_t kMaxSquad = 4;
    static constexpr std::size_t kScanCap = 64;
    static constexpr std::size_t kMaxWorkshopRows = 512;
    // Local page slice for one online catalog page. Previous/Next rows move
    // within this slice; the online page itself only changes on an explicit
    // Browse button, never while building a view.
    static constexpr std::size_t kCatalogRowsPerPage = 6;
    static constexpr std::size_t kMaxCatalogRows = 60;
    // The native browser appends bounded public catalog pages, so it scans up to
    // the backend's own 512-row cap. The legacy catalog page keeps 60.
    static constexpr std::size_t kMaxPublicCatalogRows = 512;
    static constexpr int kMaxCatalogPage = 50;
    // The discovery parser accepts source ids from 1 to 9999999999.
    static constexpr std::int64_t kMaxCatalogSourceId = 9999999999LL;
    static constexpr const char* kCareer = "career.open";
    static constexpr const char* kTraining = "training.open";
    static constexpr const char* kGarage = "garage.open";
    static constexpr const char* kAppearance = "garage.appearance";
    static constexpr const char* kWorkshop = "workshop.open";
    static constexpr const char* kCommunity = "community.open";
    static constexpr const char* kSettings = "settings.open";
    static constexpr const char* kExit = "session.exit";
    static constexpr const char* kMapLaunchReason =
        "Custom map launch is unavailable because the current loader changes an installed Rocket League file. "
        "To preserve your Steam game, this route is disabled. You can still browse maps and save favorites.";
    static constexpr const char* kActivationReason =
        "Community plugins stay in this private cache. My Career Training does not install, load, or autoload them.";

    static_assert(!kProductionGateEnabled);
    static_assert(!kNativeReplacementFinished);
    static_assert(!kSuppressionEnforced);
    static_assert(!kCompatibilityGrant);
    static_assert(!kWritesMemory);
    static_assert(!kTerminatesProcess);
    static_assert(std::char_traits<char>::length(kMapLaunchReason) <= kMaxReason);
    static_assert(std::char_traits<char>::length(kActivationReason) <= kMaxReason);
    static_assert(kCosmeticItemsPerPage >= 1);
    static_assert(kCosmeticItemsPerPage + 4 <= kMaxChoices);
    static_assert(kNativeCosmeticPaintCount + 2 <= static_cast<int>(kMaxChoices));
    static_assert(kNativeCosmeticPaletteCount + 1 <= static_cast<int>(kMaxChoices));
    static_assert(kNativeCosmeticCategoryCount + 4 <= static_cast<int>(kMaxChoices));
    // One catalog page: 6 rows + source buttons + page rows + Back.
    static_assert(kCatalogRowsPerPage + 12 <= kMaxChoices);

    // Actions this layout may put on an effect. A subset of the bridge allowlist.
    // play_workshop and any activation command are intentionally absent.
    static bool supportedAction(const std::string& action) {
        return NativeCareerManagement::allowedAction(action) ||
            action == "choose_provider" || action == "settings" || action == "backup_save" ||
            action == "open_data" || action == "diagnostics" ||
            action == "play_match" || action == "select_lesson" || action == "start_lesson" ||
            action == "start_training_pack" ||
            action == "browser_favorite" ||
            action == "assistance" || action == "lesson_variant" || action == "restore_explanations" ||
            action == "loadout" || action == "refresh_workshop" || action == "workshop_favorite" ||
            action == "community_lookup" || action == "community_paste_link" ||
            action == "community_download" || action == "community_library" ||
            action == "community_cancel" || action == "community_trial_prepare" ||
            action == "community_browse" || action == "community_browse_more" ||
            action == "community_browse_cancel" ||
            action == "community_open_item" || action == "community_select_plugin" ||
            action == "community_open_source" ||
            action == "training_settings" || action == "ghost_control" || action == "play_recording" ||
            action == "quit_game" || action == "abandon_fixture" ||
            action == "retry_lesson" || action == "return_hub" || action == "retry_result_save" ||
            action == "forfeit_match" || action == "prepare_next_match";
    }

    // `cosmetics` is not stored. Publication and selection receive a fresh context.
    bool open(const CareerLayoutScope& scope, const Json& state, const NativeCosmeticContext& cosmetics = {},
              const NativeWorkshopContext& workshop = {}) {
        (void)cosmetics;
        (void)workshop;
        page_ = CareerLayoutPage::Root;
        lessonPage_ = 0;
        lessonId_.clear();
        cosmeticSlot_ = -1;
        cosmeticPage_ = 0;
        cosmeticProductId_ = 0;
        workshopPage_ = 0;
        browserTab_ = TrainingBrowserTab::Lessons;
        browserQuery_.clear();
        browserOffset_ = 0;
        catalogPage_ = 0;
        catalogCategory_ = CatalogCategory::None;
        catalogBack_ = CareerLayoutPage::Workshop;
        opened_ = false;
        if (!scopeOk(scope) || !stateMatches(state, scope)) return false;
        // Advance even when the supplied scope is unchanged, so a choice captured
        // before this open cannot be replayed. Never wrap the counter.
        if (!advanceRevision()) return false;
        openedScope_ = scope;
        opened_ = true;
        return true;
    }

    // current is the live owned-session scope. state.offline is not that signal.
    // There is no overload that plans from the captured open scope alone.
    [[nodiscard]] CareerLayoutView view(const CareerLayoutScope& current, const Json& state,
                                       const NativeCosmeticContext& cosmetics = {},
                                       const NativeWorkshopContext& workshop = {}) const {
        if (!planActive(current, state)) return passthrough();
        CareerLayoutView out;
        out.offersReplacement = true;
        out.suppressionEnforced = false;
        out.productionGateEnabled = false;
        out.nativeReplacementFinished = false;
        out.compatibilityGrant = false;
        out.page = page_;
        out.suppress = {NativeRouteId::OnlineMatchmaking, NativeRouteId::TournamentJoin, NativeRouteId::Store,
            NativeRouteId::RocketPass, NativeRouteId::Account, NativeRouteId::Party};
        switch (page_) {
        case CareerLayoutPage::Root: buildRoot(out, state); break;
        case CareerLayoutPage::Career: buildCareer(out, state); break;
        case CareerLayoutPage::Training: buildTraining(out, state, workshop); break;
        case CareerLayoutPage::Lesson: buildLesson(out, state); break;
        case CareerLayoutPage::Schedule: buildSchedule(out, state); break;
        case CareerLayoutPage::Standings: buildStandings(out, state); break;
        case CareerLayoutPage::Squad: buildSquad(out, state); break;
        case CareerLayoutPage::Garage: buildGarage(out, state); break;
        case CareerLayoutPage::Appearance: buildAppearance(out, cosmetics); break;
        case CareerLayoutPage::CosmeticItems: buildCosmeticItems(out, cosmetics); break;
        case CareerLayoutPage::CosmeticPaints: buildCosmeticPaints(out, cosmetics); break;
        case CareerLayoutPage::CosmeticColors: buildCosmeticColors(out, cosmetics); break;
        case CareerLayoutPage::CosmeticPrimary: buildCosmeticChannel(out, cosmetics, true); break;
        case CareerLayoutPage::CosmeticAccent: buildCosmeticChannel(out, cosmetics, false); break;
        case CareerLayoutPage::Workshop: buildWorkshop(out, state, workshop); break;
        case CareerLayoutPage::WorkshopMods: buildWorkshopMods(out, state); break;
        case CareerLayoutPage::WorkshopCatalog: buildWorkshopCatalog(out, state); break;
        case CareerLayoutPage::Community: buildCommunity(out, state); break;
        case CareerLayoutPage::Settings: buildSettings(out, state); break;
        case CareerLayoutPage::CreateCareer: buildCreate(out, state); break;
        case CareerLayoutPage::CareerRules: buildRules(out, state); break;
        case CareerLayoutPage::RecoverCareer: buildRecovery(out, state); break;
        }
        // Keep action failures and save/launch feedback visible in the native
        // menu, just as they are in the service UI. Put feedback before long
        // page descriptions so the body limit cannot hide it.
        auto feedback = plain(text(state, "error"), 320);
        if (!feedback.empty()) feedback = "Could not finish: " + feedback;
        else if (busy(state)) feedback = plain(text(sessionOf(state), "message"), 240);
        else feedback = plain(text(state, "notice"), 240);
        if (!feedback.empty()) out.body = feedback + "\n\n" + out.body;
        if (out.body.size() > kMaxBody) out.body.resize(utf8Prefix(out.body, kMaxBody));
        for (auto& choice : out.choices) choice.revision = revision_;
        return out;
    }

    // originalConsumed must already be true before a Dispatch effect is returned.
    // Navigate and PreserveStockRoute never carry a bridge action.
    // A refusal does not ask the adapter to swallow unrelated native callbacks.
    [[nodiscard]] CareerLayoutEffect choose(const CareerLayoutChoice& shown, const CareerLayoutScope& click,
                                            const Json& latestState, bool originalConsumed,
                                            const NativeCosmeticContext& cosmetics = {},
                                            const NativeWorkshopContext& workshop = {}) {
        CareerLayoutEffect effect;
        if (!opened_ || !scopeOk(openedScope_)) return refuse(effect, CareerLayoutRefusal::NoPlan, kNoPlan);
        if (!sameScope(click, openedScope_) || !stateMatches(latestState, openedScope_))
            return refuse(effect, CareerLayoutRefusal::StaleScope, kStaleScope);
        if (!revisionUsable()) return refuse(effect, CareerLayoutRefusal::StaleChoice, kStaleChoice);
        const auto current = view(click, latestState, cosmetics, workshop);
        const CareerLayoutChoice* match = nullptr;
        for (const auto& choice : current.choices)
            if (choice.id == shown.id) { match = &choice; break; }
        if (!match) {
            if (shown.revision != 0 && shown.revision != revision_)
                return refuse(effect, CareerLayoutRefusal::StaleChoice, kStaleChoice);
            const bool wasSpecific = !shown.lessonId.empty() || !shown.fixtureId.empty() ||
                shown.kind == CareerLayoutEffectKind::Dispatch || shown.kind == CareerLayoutEffectKind::Unavailable ||
                shown.kind == CareerLayoutEffectKind::LocalCosmetic ||
                shown.kind == CareerLayoutEffectKind::LocalWorkshop ||
                shown.cosmetic.kind != NativeCosmeticRequestKind::None ||
                !shown.workshop.rowId.empty() ||
                shown.target == CareerLayoutPage::Appearance || shown.target == CareerLayoutPage::CosmeticItems ||
                shown.target == CareerLayoutPage::CosmeticPaints || shown.target == CareerLayoutPage::CosmeticColors ||
                shown.target == CareerLayoutPage::CosmeticPrimary || shown.target == CareerLayoutPage::CosmeticAccent ||
                shown.target == CareerLayoutPage::WorkshopMods || shown.target == CareerLayoutPage::WorkshopCatalog;
            return refuse(effect, wasSpecific ? CareerLayoutRefusal::StaleChoice : CareerLayoutRefusal::UnknownControl,
                wasSpecific ? kStaleChoice : kUnknown);
        }
        if (!sameChoice(shown, *match)) return refuse(effect, CareerLayoutRefusal::StaleChoice, kStaleChoice);
        if (!match->enabled || match->kind == CareerLayoutEffectKind::Unavailable)
            return refuse(effect, CareerLayoutRefusal::Disabled, match->reason.empty() ? kUnknown : match->reason);
        if (match->kind == CareerLayoutEffectKind::Dispatch) {
            effect.originalConsumptionRequired = true;
            if (!supportedAction(match->action) || !match->payload.is_object() || match->stock != StockRoute::None)
                return refuse(effect, CareerLayoutRefusal::UnknownControl, kUnknown);
            if (match->action == "community_trial_prepare" && !match->payload.empty())
                return refuse(effect, CareerLayoutRefusal::UnknownControl, kUnknown);
            if (!originalConsumed) return refuse(effect, CareerLayoutRefusal::NotConsumed, kNotReady);
            if (!advanceRevision()) return refuse(effect, CareerLayoutRefusal::StaleChoice, kStaleChoice);
            effect.originalConsumptionSatisfied = true;
            effect.accepted = true;
            effect.kind = CareerLayoutEffectKind::Dispatch;
            effect.action = match->action;
            effect.payload = match->payload;
            effect.leaveMenu = leavesMenu(match->action);
            effect.page = apply(match);
            effect.reason.clear();
            return effect;
        }
        if (match->kind == CareerLayoutEffectKind::PreserveStockRoute) {
            if ((match->stock != StockRoute::Garage && match->stock != StockRoute::Options) || !match->action.empty())
                return refuse(effect, CareerLayoutRefusal::UnknownControl, kUnknown);
            effect.accepted = true;
            effect.kind = CareerLayoutEffectKind::PreserveStockRoute;
            effect.stock = match->stock;
            effect.page = page_;
            return effect;
        }
        if (match->kind == CareerLayoutEffectKind::Navigate) {
            if (!match->action.empty() || match->stock != StockRoute::None)
                return refuse(effect, CareerLayoutRefusal::UnknownControl, kUnknown);
            if (!advanceRevision()) return refuse(effect, CareerLayoutRefusal::StaleChoice, kStaleChoice);
            effect.accepted = true;
            effect.kind = CareerLayoutEffectKind::Navigate;
            effect.page = apply(match);
            return effect;
        }
        if (match->kind == CareerLayoutEffectKind::LocalCosmetic) {
            // Not a bridge action. The movie does not send the request; this
            // rebuild already compared it, and the live context is checked again.
            if (!match->action.empty() || !match->payload.empty() || match->stock != StockRoute::None ||
                !supportedCosmeticChoice(*match))
                return refuse(effect, CareerLayoutRefusal::UnknownControl, kUnknown);
            if (!nativeCosmeticRequestCurrent(match->cosmetic, cosmetics))
                return refuse(effect, CareerLayoutRefusal::StaleChoice, kStaleChoice);
            if (!advanceRevision()) return refuse(effect, CareerLayoutRefusal::StaleChoice, kStaleChoice);
            effect.accepted = true;
            effect.kind = CareerLayoutEffectKind::LocalCosmetic;
            effect.cosmetic = match->cosmetic;
            effect.action.clear();
            effect.payload = Json::object();
            effect.stock = StockRoute::None;
            effect.leaveMenu = false;
            effect.page = acceptLocal(match);
            effect.reason.clear();
            return effect;
        }
        if (match->kind == CareerLayoutEffectKind::LocalWorkshop) {
            // Not a bridge action and not play_workshop. The live context is checked
            // again here; the movie click does not carry the package path.
            const auto* live = findNativeWorkshopPackage(workshop, match->workshop.rowId);
            if (!match->action.empty() || !match->payload.empty() || match->stock != StockRoute::None || !live ||
                live->packagePath != match->workshop.packagePath || live->contentRoot != match->workshop.contentRoot ||
                live->workshopId != match->workshop.workshopId || workshop.nonce != match->workshop.nonce ||
                workshop.generation != match->workshop.generation || !workshop.scopeReady || workshop.preparing ||
                workshop.blocked)
                return refuse(effect, CareerLayoutRefusal::StaleChoice, kStaleChoice);
            if (!advanceRevision()) return refuse(effect, CareerLayoutRefusal::StaleChoice, kStaleChoice);
            effect.accepted = true;
            effect.kind = CareerLayoutEffectKind::LocalWorkshop;
            effect.workshop = match->workshop;
            effect.action.clear();
            effect.payload = Json::object();
            effect.stock = StockRoute::None;
            effect.leaveMenu = false;
            effect.page = page_;
            effect.reason.clear();
            return effect;
        }
        return refuse(effect, CareerLayoutRefusal::UnknownControl, kUnknown);
    }

    [[nodiscard]] CareerLayoutEffect chooseBrowser(const std::string& op, const std::string& value,
                                                   const CareerLayoutScope& live, const Json& state,
                                                   const NativeWorkshopContext& workshop = {},
                                                   const TrainingBrowserRow* publishedRow = nullptr,
                                                   const TrainingBrowserTool* publishedTool = nullptr) {
        CareerLayoutEffect effect;
        if (!planActive(live, state) || page_ != CareerLayoutPage::Training)
            return refuse(effect, CareerLayoutRefusal::StaleScope, kStaleScope);
        if (op == "tab") {
            if (value == "lessons") browserTab_ = TrainingBrowserTab::Lessons;
            else if (value == "workshop") browserTab_ = TrainingBrowserTab::Workshop;
            else if (value == "mods") browserTab_ = TrainingBrowserTab::Mods;
            else return refuse(effect, CareerLayoutRefusal::UnknownControl, kUnknown);
            browserOffset_ = 0;
            if (!advanceRevision()) return refuse(effect, CareerLayoutRefusal::StaleChoice, kStaleChoice);
            effect.accepted = true; effect.kind = CareerLayoutEffectKind::Navigate; effect.page = page_;
            return effect;
        }
        if (op == "search") {
            if (value.size() > kMaxBrowserQuery)
                return refuse(effect, CareerLayoutRefusal::UnknownControl, kUnknown);
            browserQuery_ = plain(value, kMaxBrowserQuery);
            browserOffset_ = 0;
            if (!advanceRevision()) return refuse(effect, CareerLayoutRefusal::StaleChoice, kStaleChoice);
            effect.accepted = true; effect.kind = CareerLayoutEffectKind::Navigate; effect.page = page_;
            return effect;
        }
        if (op == "scroll") {
            if (value != "up" && value != "down")
                return refuse(effect, CareerLayoutRefusal::UnknownControl, kUnknown);
            const auto current = view(live, state, {}, workshop).browser;
            if (value == "up") browserOffset_ = browserOffset_ > 0 ? browserOffset_ - 1 : 0;
            else if (browserOffset_ + 8 < current.total) ++browserOffset_;
            else if (current.hasMore) {
                // The user scrolled past the last displayed row of a catalog that
                // still has a next page. One explicit append request, no payload.
                if (!advanceRevision()) return refuse(effect, CareerLayoutRefusal::StaleChoice, kStaleChoice);
                effect.accepted = true; effect.kind = CareerLayoutEffectKind::Dispatch;
                effect.originalConsumptionRequired = true; effect.originalConsumptionSatisfied = true;
                effect.action = "community_browse_more"; effect.payload = Json::object();
                effect.page = page_; return effect;
            }
            if (!advanceRevision()) return refuse(effect, CareerLayoutRefusal::StaleChoice, kStaleChoice);
            effect.accepted = true; effect.kind = CareerLayoutEffectKind::Navigate; effect.page = page_;
            return effect;
        }
        if (op == "tool") {
            const auto current = view(live, state, {}, workshop).browser;
            const TrainingBrowserTool* tool = nullptr;
            for (const auto& candidate : current.tools) if (candidate.key == value) { tool = &candidate; break; }
            if (!tool || !publishedTool || !sameBrowserTool(*tool, *publishedTool))
                return refuse(effect, CareerLayoutRefusal::StaleChoice, kStaleChoice);
            if (!tool->enabled)
                return refuse(effect, CareerLayoutRefusal::Disabled, tool->reason.empty() ? kUnknown : tool->reason);
            if (!advanceRevision()) return refuse(effect, CareerLayoutRefusal::StaleChoice, kStaleChoice);
            effect.accepted = true; effect.kind = CareerLayoutEffectKind::Dispatch;
            effect.originalConsumptionRequired = true; effect.originalConsumptionSatisfied = true;
            effect.action = tool->action; effect.payload = tool->payload; effect.page = page_;
            return effect;
        }
        if (op != "primary" || value.empty() || value.size() > kMaxBrowserKey)
            return refuse(effect, CareerLayoutRefusal::UnknownControl, kUnknown);
        const auto current = view(live, state, {}, workshop).browser;
        const TrainingBrowserRow* row = nullptr;
        for (const auto& candidate : current.rows) if (candidate.key == value) { row = &candidate; break; }
        if (!row || !publishedRow || !sameBrowserRow(*row, *publishedRow))
            return refuse(effect, CareerLayoutRefusal::StaleChoice, kStaleChoice);
        if (!row->primaryEnabled)
            return refuse(effect, CareerLayoutRefusal::Disabled, row->reason.empty() ? kUnknown : row->reason);
        if (!row->workshop.rowId.empty()) {
            const auto* package = findNativeWorkshopPackage(workshop, row->workshop.rowId);
            if (!package || package->packagePath != row->workshop.packagePath ||
                package->contentRoot != row->workshop.contentRoot || package->workshopId != row->workshop.workshopId ||
                workshop.nonce != row->workshop.nonce || workshop.generation != row->workshop.generation ||
                !workshop.scopeReady || workshop.preparing || workshop.blocked)
                return refuse(effect, CareerLayoutRefusal::StaleChoice, kStaleChoice);
            if (!advanceRevision()) return refuse(effect, CareerLayoutRefusal::StaleChoice, kStaleChoice);
            effect.accepted = true; effect.kind = CareerLayoutEffectKind::LocalWorkshop;
            effect.workshop = row->workshop; effect.page = page_; return effect;
        }
        if (!supportedAction(row->action) || !row->payload.is_object())
            return refuse(effect, CareerLayoutRefusal::UnknownControl, kUnknown);
        if (!advanceRevision()) return refuse(effect, CareerLayoutRefusal::StaleChoice, kStaleChoice);
        effect.accepted = true; effect.kind = CareerLayoutEffectKind::Dispatch;
        effect.originalConsumptionRequired = true; effect.originalConsumptionSatisfied = true;
        effect.action = row->action; effect.payload = row->payload; effect.leaveMenu = leavesMenu(row->action);
        if (row->action == "select_lesson") {
            lessonId_ = row->itemId;
            page_ = CareerLayoutPage::Lesson;
        }
        effect.page = page_; return effect;
    }

    // Host-side binding. Rows come from the bridge workshop object. Paths outside
    // the executable's own Steam library are left unbound.
    static NativeWorkshopContext bindWorkshop(const Json& state, const std::string& executablePath,
                                              const std::string& nonce, std::uint64_t generation, bool scopeReady,
                                              bool preparing, bool blocked) {
        NativeWorkshopContext context;
        context.bound = true;
        context.scopeReady = scopeReady;
        context.preparing = preparing;
        context.blocked = blocked;
        context.nonce = nonce;
        context.generation = generation;
        context.libraryRoot = nativeWorkshopLibraryRoot(executablePath);
        context.libraryConfirmed = !context.libraryRoot.empty();
        const auto contentRoot = nativeWorkshopContentRoot(context.libraryRoot);
        if (blocked) context.status = "Close this session before loading another map.";
        else if (preparing) context.status = "Preparing this map.";
        else if (!scopeReady) context.status = "Play is available during an offline career session.";
        else if (!context.libraryConfirmed) context.status = "This game's Steam library could not be confirmed.";
        if (!context.libraryConfirmed) return context;
        const auto items = array(object(state, "workshop"), "items");
        const auto stop = (std::min)(items.size(), kMaxWorkshopRows);
        std::vector<NativeWorkshopPackage> steam;
        for (std::size_t index = 0; index < stop; ++index) {
            const auto& item = items[index];
            if (text(item, "origin") != "steam_workshop" || !flag(item, "installed", false)) continue;
            const auto id = text(item, "id");
            const auto workshopId = text(item, "workshop_id");
            if (!safeId(id) || !digitsOnly(workshopId)) continue;
            const auto parsed = workshop_load_detail::parsePath(text(item, "path"));
            if (parsed.reason || !nativeWorkshopPackageTrusted(contentRoot, parsed.canonical, workshopId)) continue;
            NativeWorkshopPackage package;
            package.rowId = id;
            package.workshopId = workshopId;
            package.title = text(item, "title", "Map");
            package.contentRoot = contentRoot;
            package.packagePath = parsed.canonical;
            steam.push_back(std::move(package));
        }
        context.packages = steam;
        for (std::size_t index = 0; index < stop; ++index) {
            const auto& item = items[index];
            if (text(item, "origin") != "catalog" || !flag(item, "installed", false)) continue;
            const auto id = text(item, "id");
            const auto launchId = text(item, "launch_id");
            if (!safeId(id) || launchId.empty() || launchId == id) continue;
            const NativeWorkshopPackage* match = nullptr;
            int matches = 0;
            for (const auto& package : steam) {
                if (package.rowId != launchId) continue;
                match = &package;
                ++matches;
            }
            if (matches != 1 || !match) continue;
            NativeWorkshopPackage alias = *match;
            alias.rowId = id;
            alias.title = text(item, "title", match->title);
            context.packages.push_back(std::move(alias));
        }
        return context;
    }

    [[nodiscard]] NativeRouteDecision route(NativeRouteId id, const CareerLayoutScope& current, const Json& state) const {
        NativeRouteDecision decision;
        decision.enforcementVerified = false;
        decision.consumesUnlisted = false;
        if (!knownRoute(id)) {
            decision.route = NativeRouteId::Unlisted;
            decision.plan = NativeRoutePlan::Passthrough;
            return decision;
        }
        decision.route = id;
        if (!planActive(current, state)) {
            decision.plan = NativeRoutePlan::Passthrough;
            return decision;
        }
        switch (id) {
        case NativeRouteId::OnlineMatchmaking:
        case NativeRouteId::TournamentJoin:
        case NativeRouteId::Store:
        case NativeRouteId::RocketPass:
        case NativeRouteId::Account:
        case NativeRouteId::Party:
            decision.plan = NativeRoutePlan::Suppress;
            decision.suppressionRequired = true;
            break;
        case NativeRouteId::Garage:
        case NativeRouteId::Options:
            decision.plan = NativeRoutePlan::PreserveStock;
            break;
        case NativeRouteId::AccountCloudSync:
        case NativeRouteId::Unlisted:
            decision.plan = NativeRoutePlan::Passthrough;
            break;
        }
        return decision;
    }

private:
    static constexpr const char* kNoPlan = "My Career is available in an offline career session.";
    static constexpr const char* kStaleScope = "This menu is out of date. Open My Career again.";
    static constexpr const char* kStaleChoice = "That choice changed. Review the current list.";
    static constexpr const char* kNotReady = "That choice is not ready yet.";
    static constexpr const char* kUnknown = "That choice is not available.";
    static constexpr const char* kWait = "Wait for the current game transition to finish.";
    static constexpr const char* kRecover = "Finish or recover the current attempt, then try again.";

    CareerLayoutPage page_ = CareerLayoutPage::Root;
    std::size_t lessonPage_ = 0;
    std::string lessonId_;
    int cosmeticSlot_ = -1;
    std::size_t cosmeticPage_ = 0;
    int cosmeticProductId_ = 0;
    std::size_t workshopPage_ = 0;
    TrainingBrowserTab browserTab_ = TrainingBrowserTab::Lessons;
    std::string browserQuery_;
    std::size_t browserOffset_ = 0;
    bool workshopMods_ = false;
    std::size_t catalogPage_ = 0;
    // Intended catalog category and Back target, captured when the catalog was
    // entered. Never derived from the shared backend community_catalog.source.
    CatalogCategory catalogCategory_ = CatalogCategory::None;
    CareerLayoutPage catalogBack_ = CareerLayoutPage::Workshop;
    bool opened_ = false;
    CareerLayoutScope openedScope_{};
    std::uint64_t revision_ = 0;

    bool revisionUsable() const {
        return revision_ != 0 && revision_ != (std::numeric_limits<std::uint64_t>::max)();
    }

    // False only when the counter is already saturated. The value never wraps.
    bool advanceRevision() {
        if (revision_ == (std::numeric_limits<std::uint64_t>::max)()) return false;
        ++revision_;
        return true;
    }

    static CareerLayoutView passthrough() {
        CareerLayoutView out;
        out.offersReplacement = false;
        out.suppressionEnforced = false;
        out.productionGateEnabled = false;
        out.nativeReplacementFinished = false;
        out.compatibilityGrant = false;
        return out;
    }

    static CareerLayoutEffect refuse(CareerLayoutEffect effect, CareerLayoutRefusal refusal, const std::string& reason) {
        effect.accepted = false;
        effect.kind = CareerLayoutEffectKind::None;
        effect.refusal = refusal;
        effect.stock = StockRoute::None;
        effect.action.clear();
        effect.payload = Json::object();
        effect.leaveMenu = false;
        effect.originalConsumptionSatisfied = false;
        effect.compatibilityGrant = false;
        effect.consumesUnlistedCallback = false;
        effect.cosmetic = {};
        effect.workshop = {};
        if (refusal != CareerLayoutRefusal::NotConsumed) effect.originalConsumptionRequired = false;
        effect.reason = reason.empty() ? kUnknown : reason;
        return effect;
    }

    static bool leavesMenu(const std::string& action) {
        return action == "play_match" || action == "start_lesson" || action == "quit_game";
    }

    CareerLayoutPage apply(const CareerLayoutChoice* choice) {
        if (!choice) return page_;
        if (choice->kind == CareerLayoutEffectKind::Navigate) {
            page_ = choice->target;
            if (choice->target == CareerLayoutPage::Training) lessonPage_ = choice->page;
            if (choice->target == CareerLayoutPage::Workshop) workshopPage_ = choice->page;
            if (choice->target == CareerLayoutPage::Workshop) workshopMods_ = false;
            if (choice->target == CareerLayoutPage::WorkshopMods) workshopMods_ = true;
            if (choice->target == CareerLayoutPage::WorkshopCatalog) {
                workshopMods_ = true;
                catalogPage_ = choice->page;
                // Only an entry choice carries a category. Local row paging
                // keeps the category and Back target captured on entry.
                if (choice->catalog != CatalogCategory::None) {
                    catalogCategory_ = choice->catalog;
                    catalogBack_ = choice->catalogBack;
                }
            }
            if (choice->target == CareerLayoutPage::CosmeticItems) {
                cosmeticSlot_ = choice->cosmetic.slot;
                cosmeticPage_ = choice->page;
                cosmeticProductId_ = 0;
            } else if (choice->target == CareerLayoutPage::Appearance ||
                       choice->target == CareerLayoutPage::Garage ||
                       choice->target == CareerLayoutPage::Root) {
                cosmeticSlot_ = -1;
                cosmeticPage_ = 0;
                cosmeticProductId_ = 0;
            }
            return page_;
        }
        if (choice->action == "select_lesson") {
            lessonId_ = choice->lessonId;
            page_ = CareerLayoutPage::Lesson;
        }
        if (choice->action == "new_career" || choice->action == "next_season" || choice->action == "abandon_fixture")
            page_ = CareerLayoutPage::Career;
        return page_;
    }

    // Live ownership, offline, freshness, online, nonce, and generation come from
    // current. state.offline is the backend in-game flag, not that live status.
    bool planActive(const CareerLayoutScope& current, const Json& state) const {
        return opened_ && revisionUsable() && sameScope(current, openedScope_) &&
            stateMatches(state, openedScope_);
    }

    static bool scopeOk(const CareerLayoutScope& scope) {
        return scope.surface == NativeMenuSurface::Frontend &&
            scope.owned && scope.offline && scope.fresh && !scope.online &&
            scope.generation != 0 && validNonce(scope.nonce);
    }

    static bool sameScope(const CareerLayoutScope& click, const CareerLayoutScope& opened) {
        return scopeOk(click) && click.owned == opened.owned && click.offline == opened.offline &&
            click.fresh == opened.fresh && click.online == opened.online &&
            click.generation == opened.generation && click.nonce == opened.nonce && click.surface == opened.surface;
    }

    static bool stateMatches(const Json& state, const CareerLayoutScope& scope) {
        return state.is_object() && flag(state, "offline", false) && protocolOne(state) &&
            text(state, "bridge_session") == scope.nonce;
    }

    static bool knownRoute(NativeRouteId id) {
        switch (id) {
        case NativeRouteId::OnlineMatchmaking:
        case NativeRouteId::TournamentJoin:
        case NativeRouteId::Store:
        case NativeRouteId::RocketPass:
        case NativeRouteId::Account:
        case NativeRouteId::Party:
        case NativeRouteId::AccountCloudSync:
        case NativeRouteId::Garage:
        case NativeRouteId::Options:
        case NativeRouteId::Unlisted:
            return true;
        }
        return false;
    }

    static bool sameChoice(const CareerLayoutChoice& a, const CareerLayoutChoice& b) {
        return a.id == b.id && a.label == b.label && a.enabled == b.enabled && a.reason == b.reason &&
            a.kind == b.kind && a.action == b.action && a.payload == b.payload && a.stock == b.stock &&
            a.target == b.target && a.page == b.page && a.lessonId == b.lessonId && a.careerId == b.careerId &&
            a.fixtureId == b.fixtureId && a.recruitId == b.recruitId && a.itemId == b.itemId &&
            a.cosmetic == b.cosmetic && a.cosmeticStamp == b.cosmeticStamp &&
            a.workshop == b.workshop && a.workshopStamp == b.workshopStamp &&
            a.catalog == b.catalog && a.catalogBack == b.catalogBack &&
            a.revision == b.revision;
    }

    static bool validNonce(const std::string& value) {
        if (value.size() < 16 || value.size() > 128) return false;
        return std::all_of(value.begin(), value.end(), [](unsigned char c) {
            return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '_' || c == '-';
        });
    }

    static bool validId(const std::string& value) {
        if (value.empty() || value.size() > 128) return false;
        return std::all_of(value.begin(), value.end(), [](unsigned char c) {
            return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '_' || c == '-';
        });
    }

    static bool safeId(const std::string& value) {
        if (value.empty() || value.size() > 128 || value.find("..") != std::string::npos) return false;
        return std::all_of(value.begin(), value.end(), [](unsigned char c) {
            return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') ||
                c == '_' || c == '-' || c == ':';
        });
    }

    static bool pluginId(const std::string& value) {
        if (value.empty() || value.size() > 10 || value[0] < '1' || value[0] > '9') return false;
        return std::all_of(value.begin(), value.end(), [](unsigned char c) { return c >= '0' && c <= '9'; });
    }

    // A saved favorite id is a decimal string. It is converted to the same
    // bounded numeric source id the catalog parser accepts, so a saved id can
    // never widen the accepted range.
    static bool savedCatalogId(const std::string& value, std::int64_t& out) {
        if (!pluginId(value)) return false;
        std::int64_t number = 0;
        for (const auto c : value) {
            number = number * 10 + (c - '0');
            if (number > kMaxCatalogSourceId) return false;
        }
        if (number < 1) return false;
        out = number;
        return true;
    }

    static bool supportedBody(int id) { return id == 23 || id == 403 || id == 30 || id == 22; }

    static std::string text(const Json& value, const char* key, const std::string& fallback = "") {
        if (!value.is_object()) return fallback;
        const auto it = value.find(key);
        return it != value.end() && it->is_string() ? it->get<std::string>() : fallback;
    }

    static bool flag(const Json& value, const char* key, bool fallback) {
        if (!value.is_object()) return fallback;
        const auto it = value.find(key);
        return it != value.end() && it->is_boolean() ? it->get<bool>() : fallback;
    }

    static Json object(const Json& value, const char* key) {
        if (!value.is_object()) return Json::object();
        const auto it = value.find(key);
        return it != value.end() && it->is_object() ? *it : Json::object();
    }

    static Json objectKey(const Json& value, const std::string& key) {
        if (!value.is_object()) return Json::object();
        const auto it = value.find(key);
        return it != value.end() && it->is_object() ? *it : Json::object();
    }

    static Json array(const Json& value, const char* key) {
        if (!value.is_object()) return Json::array();
        const auto it = value.find(key);
        return it != value.end() && it->is_array() ? *it : Json::array();
    }

    static bool protocolOne(const Json& state) {
        if (!state.is_object()) return false;
        const auto it = state.find("protocol");
        if (it == state.end() || !it->is_number_integer()) return false;
        if (it->is_number_unsigned()) return it->get<std::uint64_t>() == 1;
        return it->get<std::int64_t>() == 1;
    }

    static bool whole(const Json& value, const char* key, int& out, int low, int high) {
        if (!value.is_object()) return false;
        const auto it = value.find(key);
        if (it == value.end() || !it->is_number_integer()) return false;
        std::int64_t number = 0;
        if (it->is_number_unsigned()) {
            const auto wide = it->get<std::uint64_t>();
            if (wide > static_cast<std::uint64_t>((std::numeric_limits<std::int64_t>::max)())) return false;
            number = static_cast<std::int64_t>(wide);
        } else number = it->get<std::int64_t>();
        if (number < low || number > high) return false;
        out = static_cast<int>(number);
        return true;
    }

    static std::size_t utf8Prefix(const std::string& value, std::size_t limit) {
        std::size_t count = (std::min)(limit, value.size());
        while (count > 0 && count < value.size() && (static_cast<unsigned char>(value[count]) & 0xc0) == 0x80) --count;
        return count;
    }

    static std::string plain(const std::string& value, std::size_t limit) {
        if (limit == 0) return {};
        const bool shortened = value.size() > limit;
        // Reserve the ellipsis before cutting the UTF-8 text. Cutting it again
        // afterwards can split a character and make JSON publication fail.
        const std::size_t markSize = shortened ? (std::min)(limit, std::size_t{3}) : 0;
        const auto count = utf8Prefix(value, limit - markSize);
        std::string out;
        out.reserve(count + markSize);
        for (std::size_t i = 0; i < count; ++i) {
            const auto c = static_cast<unsigned char>(value[i]);
            out.push_back(c < 32 || c == 127 || c == '<' || c == '>' || c == '&' ? ' ' : static_cast<char>(c));
        }
        out.append(markSize, '.');
        return out;
    }

    static void addLine(std::string& body, const std::string& line) {
        auto text = plain(line, 180);
        if (text.empty()) return;
        if (!body.empty()) {
            if (body.size() + 1 >= kMaxBody) return;
            body.push_back('\n');
        }
        if (body.size() >= kMaxBody) return;
        if (body.size() + text.size() > kMaxBody) text.resize(utf8Prefix(text, kMaxBody - body.size()));
        body += text;
    }

    static void addSummary(std::string& body, const std::string& summary) {
        // Management summaries already contain rows. Sanitize each row without
        // flattening the standings or truncating the whole summary as one line.
        std::size_t start = 0;
        while (start < summary.size() && body.size() < kMaxBody) {
            const auto end = summary.find('\n', start);
            addLine(body, summary.substr(start, end == std::string::npos ? end : end - start));
            if (end == std::string::npos) break;
            start = end + 1;
        }
    }

    static void push(CareerLayoutView& view, CareerLayoutChoice choice) {
        if (view.choices.size() >= kMaxChoices) return;
        if (choice.id.empty() || choice.id.size() > 160) return;
        for (const auto& existing : view.choices)
            if (existing.id == choice.id) return;
        choice.label = plain(choice.label, kMaxLabel);
        choice.reason = plain(choice.reason, kMaxReason);
        if (choice.label.empty()) return;
        if (choice.kind == CareerLayoutEffectKind::PreserveStockRoute) {
            if (!choice.enabled || (choice.stock != StockRoute::Garage && choice.stock != StockRoute::Options)) return;
            choice.action.clear();
            choice.payload = Json::object();
        } else if (!choice.enabled || choice.kind != CareerLayoutEffectKind::Dispatch) {
            choice.action.clear();
            choice.payload = Json::object();
        } else if (!supportedAction(choice.action) || !choice.payload.is_object() || choice.stock != StockRoute::None) {
            return;
        }
        view.choices.push_back(std::move(choice));
    }

    static void navigate(CareerLayoutView& view, const char* id, const std::string& label, CareerLayoutPage target,
                         std::size_t page = 0) {
        CareerLayoutChoice choice;
        choice.id = id;
        choice.label = label;
        choice.enabled = true;
        choice.kind = CareerLayoutEffectKind::Navigate;
        choice.target = target;
        choice.page = page;
        push(view, std::move(choice));
    }

    static void back(CareerLayoutView& view, CareerLayoutPage target, std::size_t page = 0) {
        navigate(view, "nav.back", "Back", target, page);
    }

    // Catalog entry navigation. The intended category and Back target travel in
    // the choice so they survive a stale or shared backend catalog source.
    static void navigateCatalog(CareerLayoutView& view, const char* id, const std::string& label,
                                CatalogCategory category, CareerLayoutPage backTarget) {
        CareerLayoutChoice choice;
        choice.id = id;
        choice.label = label;
        choice.enabled = true;
        choice.kind = CareerLayoutEffectKind::Navigate;
        choice.target = CareerLayoutPage::WorkshopCatalog;
        choice.page = 0;
        choice.catalog = category;
        choice.catalogBack = backTarget;
        push(view, std::move(choice));
    }

    static Json sessionOf(const Json& state) { return object(state, "session"); }
    static Json careerOf(const Json& state) { return object(state, "career"); }

    static bool busy(const Json& state) { return flag(sessionOf(state), "busy", true); }

    static bool pending(const Json& career) {
        if (!career.is_object()) return true;
        const auto it = career.find("pending_session");
        if (it == career.end() || it->is_null()) return false;
        return !(it->is_object() && it->empty());
    }

    static bool ready(const Json& state) {
        const auto session = sessionOf(state);
        const auto phase = text(session, "state");
        const bool phaseOk = phase == "Career Ready" || phase == "Idle" || phase == "training";
        return phaseOk && !busy(state) && !flag(state, "setup_required", true) && !pending(careerOf(state));
    }

    static bool lessonReady(const Json& state) {
        const auto session = sessionOf(state);
        const auto phase = text(session, "state");
        return (phase == "Career Ready" || phase == "Idle" || phase == "training") &&
            !busy(state) && !flag(session, "worker_running", true) &&
            !flag(state, "setup_required", true);
    }

    static bool workerLikely(const Json& state) {
        const auto session = sessionOf(state);
        const auto kind = text(session, "kind");
        const auto phase = text(session, "state");
        return kind == "training" || kind == "workshop" || kind == "career" || kind == "calibration" ||
            phase == "Playing" || phase == "playing" || phase == "training" || phase == "Starting Career";
    }

    static Json currentSeason(const Json& career) {
        const auto seasons = array(career, "seasons");
        if (!career.is_object()) return Json::object();
        const auto it = career.find("current_season");
        if (it == career.end() || !it->is_number_integer()) return Json::object();
        std::uint64_t index = 0;
        if (it->is_number_unsigned()) index = it->get<std::uint64_t>();
        else {
            const auto signedIndex = it->get<std::int64_t>();
            if (signedIndex < 0) return Json::object();
            index = static_cast<std::uint64_t>(signedIndex);
        }
        if (index >= seasons.size()) return Json::object();
        const auto& season = seasons[static_cast<std::size_t>(index)];
        return season.is_object() ? season : Json::object();
    }

    static std::string clubName(const Json& state, const std::string& id) {
        const auto career = careerOf(state);
        if (id == "human") return plain(text(career, "team_name", "My club"), 48);
        const auto clubs = array(currentSeason(career), "clubs");
        const auto stop = (std::min)(clubs.size(), kScanCap);
        for (std::size_t i = 0; i < stop; ++i)
            if (text(clubs[i], "id") == id) return plain(text(clubs[i], "name", "Club"), 48);
        return id == "human" ? std::string("My club") : std::string("Club");
    }

    static std::vector<Json> lessonsOf(const Json& state) {
        const auto lessons = array(state, "lessons");
        std::vector<Json> result;
        const auto stop = (std::min)(lessons.size(), kMaxLessons);
        for (std::size_t i = 0; i < stop; ++i) {
            const auto id = text(lessons[i], "id");
            if (!validId(id)) continue;
            if (std::any_of(result.begin(), result.end(), [&](const Json& lesson) { return text(lesson, "id") == id; }))
                continue;
            result.push_back(lessons[i]);
        }
        return result;
    }

    static Json findLesson(const std::vector<Json>& lessons, const std::string& id) {
        for (const auto& lesson : lessons)
            if (text(lesson, "id") == id) return lesson;
        return Json::object();
    }

    static bool goalLesson(const Json& lesson) {
        const auto targets = array(lesson, "targets");
        const auto stop = (std::min)(targets.size(), kScanCap);
        for (std::size_t i = 0; i < stop; ++i)
            if (text(targets[i], "type") == "goal") return true;
        return false;
    }

    static Json lessonPrefs(const Json& state, const std::string& id) {
        return objectKey(object(state, "lesson_preferences"), id);
    }

    static bool assist(const Json& state, const std::string& lessonId, const char* key, bool fallback) {
        const auto prefs = lessonPrefs(state, lessonId);
        return flag(prefs, key, fallback);
    }

    std::size_t shownLessonPage(std::size_t count) const {
        if (count == 0) return 0;
        const auto pages = (count + kLessonsPerPage - 1) / kLessonsPerPage;
        return (std::min)(lessonPage_, pages - 1);
    }

    static const char* mapReason(const Json& item) {
        const auto reason = text(item, "launch_reason");
        const auto availability = text(item, "availability");
        const char* known[] = {kMapLaunchReason, "Epic loader unavailable", "Choose an installed package", "Not installed"};
        for (const char* entry : known)
            if (reason == entry || availability == entry) return entry;
        if (item.is_object() && item.contains("installed") && item["installed"].is_boolean() && !item["installed"].get<bool>())
            return "Not installed";
        return kMapLaunchReason;
    }

    static void dispatch(CareerLayoutView& view, const std::string& id, const std::string& label, bool enabled,
                         const std::string& reason, const std::string& action, Json payload) {
        CareerLayoutChoice choice;
        choice.id = id;
        choice.label = label;
        choice.enabled = enabled;
        choice.reason = enabled ? "" : reason;
        choice.kind = CareerLayoutEffectKind::Dispatch;
        choice.action = action;
        choice.payload = std::move(payload);
        push(view, std::move(choice));
    }

    void buildRoot(CareerLayoutView& view, const Json& state) const {
        view.title = "My Career";
        addLine(view.body, "Offline career and one Training browser for lessons, workshop items, and mods.");
        addLine(view.body, "Your garage and game options stay the game's own screens.");
        navigate(view, kCareer, "My Career", CareerLayoutPage::Career);
        navigate(view, kTraining, "Training", CareerLayoutPage::Training);
        navigate(view, kGarage, "Garage", CareerLayoutPage::Garage);
        // Retained as internal typed routes for compatibility tests and direct
        // host planning. NativeMovieProtocol does not publish these legacy root
        // entries; all player access is through Training tabs.
        navigate(view, kWorkshop, "Workshop", CareerLayoutPage::Workshop);
        navigate(view, kCommunity, "Community", CareerLayoutPage::Community);
        navigate(view, kSettings, "Settings", CareerLayoutPage::Settings);
        const bool canExit = flag(object(state, "session"), "can_exit", !busy(state));
        dispatch(view, kExit, "Quit My Career", canExit, kWait, "quit_game", Json::object());
    }

    void buildCareer(CareerLayoutView& view, const Json& state) const {
        view.title = "My Career";
        const auto career = careerOf(state);
        const auto fixture = object(state, "next_fixture");
        if (career.empty()) addLine(view.body, "No career exists yet.");
        else addLine(view.body, plain(text(career, "team_name", "My club"), 48));
        addSummary(view.body, NativeCareerManagement::careerSummary(state));
        if (pending(career)) {
            const auto session = sessionOf(state);
            const bool active = busy(state) || flag(session, "worker_running", true);
            if (active) {
                const auto phase = text(session, "state");
                if (phase == "Starting Career") addLine(view.body, "Your match is starting. Please wait for Rocket League.");
                else if (phase == "Playing") addLine(view.body, "Your match is in progress.");
                else addLine(view.body, "Return from the current activity before restarting this match.");
            } else {
                addLine(view.body, "Your last match did not finish. Restart it before playing another Career match.");
                navigate(view, "career.recover", "Restart unfinished match", CareerLayoutPage::RecoverCareer);
            }
        }
        navigate(view, "career.create", "New career", CareerLayoutPage::CreateCareer);
        CareerLayoutChoice play;
        play.id = "career.play";
        play.label = "Play Next Match";
        play.kind = CareerLayoutEffectKind::Dispatch;
        play.action = "play_match";
        if (career.empty()) play.reason = "Create a career before playing a match.";
        else if (fixture.empty()) play.reason = "No next match is on the schedule.";
        // Domain fixture IDs include season/phase separators, for example
        // career-a:s1:league:1:0. They are opaque JSON identifiers, not paths.
        else if (!validId(text(career, "id")) || !safeId(text(fixture, "id"))) play.reason = "That match is not ready.";
        else if (text(fixture, "home") != "human" && text(fixture, "away") != "human")
            play.reason = "That match does not include your club.";
        else if (text(fixture, "status") != "scheduled") play.reason = "That match is already finished.";
        else if (flag(state, "setup_required", true)) play.reason = "Finish setup before playing a match.";
        else if (!ready(state)) play.reason = kRecover;
        else if (career.value("format", Json()) == 4 && text(state, "selected_provider") != "mct-specialist-baseline")
            play.reason = "Choose Ground Specialists in Career rules for 4v4.";
        else {
            play.enabled = true;
            play.careerId = text(career, "id");
            play.fixtureId = text(fixture, "id");
            play.payload = {{"expected_career_id", play.careerId}, {"expected_fixture_id", play.fixtureId}};
            addLine(view.body, "Next match: " + clubName(state, text(fixture, "home")) + " vs " +
                clubName(state, text(fixture, "away")));
        }
        push(view, play);
        navigate(view, "career.squad", "Squad", CareerLayoutPage::Squad);
        navigate(view, "career.schedule", "Schedule", CareerLayoutPage::Schedule);
        navigate(view, "career.standings", "Season", CareerLayoutPage::Standings);
        navigate(view, "career.rules", "Career rules", CareerLayoutPage::CareerRules);
        back(view, CareerLayoutPage::Root);
    }

    void buildRecovery(CareerLayoutView& view, const Json& state) const {
        view.title = "Restart unfinished match";
        addLine(view.body, "The unfinished match will return to the schedule, ready to play from kickoff.");
        addLine(view.body, "No score or reward will be added. Completed matches and your squad stay saved.");
        const auto career = careerOf(state);
        const auto unfinished = object(career, "pending_session");
        const auto careerId = text(career, "id");
        const auto fixtureId = text(unfinished, "fixture_id");
        const auto sessionId = text(unfinished, "session_id");
        const bool canRestart = !busy(state) && !flag(sessionOf(state), "worker_running", true) && validId(careerId) &&
            safeId(fixtureId) && validId(sessionId);
        dispatch(view, "career.recover.confirm", "Confirm restart", canRestart,
            "Return from the current activity first. If no unfinished match remains, go Back.",
            "abandon_fixture", {{"expected_career_id", careerId}, {"expected_fixture_id", fixtureId},
                {"expected_session_id", sessionId}});
        back(view, CareerLayoutPage::Career);
    }

    static bool browserFavorite(const Json& state, const std::string& type, const std::string& id) {
        const auto favorites = array(state, "browser_favorites");
        for (const auto& favorite : favorites)
            if (text(favorite, "type") == type && text(favorite, "id") == id) return true;
        return false;
    }

    static bool queryMatches(const TrainingBrowserRow& row, const std::string& query) {
        if (query.empty()) return true;
        auto fold = [](std::string value) {
            std::transform(value.begin(), value.end(), value.begin(), [](unsigned char c) {
                return c >= 'A' && c <= 'Z' ? static_cast<char>(c + ('a' - 'A')) : static_cast<char>(c);
            });
            return value;
        };
        const auto needle = fold(query);
        return fold(row.title).find(needle) != std::string::npos ||
            fold(row.subtitle).find(needle) != std::string::npos || fold(row.detail).find(needle) != std::string::npos;
    }

    static bool sameBrowserRow(const TrainingBrowserRow& left, const TrainingBrowserRow& right) {
        return left.key == right.key && left.type == right.type && left.itemId == right.itemId &&
            left.title == right.title && left.subtitle == right.subtitle && left.detail == right.detail &&
            left.primaryLabel == right.primaryLabel && left.primaryEnabled == right.primaryEnabled &&
            left.favorite == right.favorite && left.reason == right.reason && left.action == right.action &&
            left.payload == right.payload && left.workshop == right.workshop && left.workshopStamp == right.workshopStamp;
    }

    static bool sameBrowserTool(const TrainingBrowserTool& left, const TrainingBrowserTool& right) {
        return left.key == right.key && left.label == right.label && left.enabled == right.enabled &&
            left.reason == right.reason && left.action == right.action && left.payload == right.payload;
    }

    static void browserTool(TrainingBrowserView& browser, const std::string& key, const std::string& label,
                            bool enabled, const std::string& reason, const std::string& action, Json payload) {
        if (browser.tools.size() >= kMaxBrowserTools || key.empty() || key.size() > kMaxBrowserKey ||
            !supportedAction(action) || !payload.is_object()) return;
        TrainingBrowserTool tool;
        tool.key = key; tool.label = plain(label, kMaxLabel); tool.enabled = enabled;
        tool.reason = enabled ? "" : plain(reason, kMaxReason); tool.action = action; tool.payload = std::move(payload);
        browser.tools.push_back(std::move(tool));
    }

    std::vector<TrainingBrowserRow> browserRows(TrainingBrowserTab tab, const Json& state,
                                                const NativeWorkshopContext& workshop) const {
        std::vector<TrainingBrowserRow> rows;
        auto add = [&](TrainingBrowserRow row) {
            if (row.itemId.empty() || row.itemId.size() > kMaxBrowserKey || row.key.empty() ||
                row.key.size() > kMaxBrowserKey ||
                rows.size() >= kMaxWorkshopRows + kMaxLessons + kMaxPublicCatalogRows) return;
            row.title = plain(row.title, kMaxBrowserDisplay);
            row.subtitle = plain(row.subtitle, kMaxBrowserDisplay);
            row.detail = plain(row.detail, kMaxBrowserDisplay);
            row.primaryLabel = plain(row.primaryLabel, kMaxLabel);
            row.reason = plain(row.reason, kMaxReason);
            if (!row.title.empty()) rows.push_back(std::move(row));
        };
        if (tab == TrainingBrowserTab::Lessons) {
            const auto lessons = lessonsOf(state);
            const auto stop = (std::min)(lessons.size(), kMaxLessons);
            for (std::size_t i = 0; i < stop; ++i) {
                const auto id = text(lessons[i], "id"); if (!safeId(id)) continue;
                TrainingBrowserRow row;
                row.key = "lesson:" + id; row.type = "lesson"; row.itemId = id;
                row.title = text(lessons[i], "title", "Lesson"); row.subtitle = "Training lesson";
                row.detail = text(lessons[i], "description"); row.primaryLabel = "Start lesson";
                row.primaryEnabled = lessonReady(state); row.reason = row.primaryEnabled ? "" : kRecover;
                row.action = "start_lesson"; row.payload = {{"id", id}};
                if (id == "power-shots") {
                    row.primaryLabel = "Choose rank";
                    row.action = "select_lesson";
                    row.primaryEnabled = !busy(state);
                    row.reason = row.primaryEnabled ? "" : kWait;
                }
                row.favorite = browserFavorite(state, row.type, id); add(std::move(row));
            }
            return rows;
        }
        if (tab == TrainingBrowserTab::Workshop) {
            const auto items = array(object(state, "workshop"), "items");
            const auto stop = (std::min)(items.size(), kMaxWorkshopRows);
            for (std::size_t i = 0; i < stop; ++i) {
                const auto id = text(items[i], "id"); if (!safeId(id)) continue;
                TrainingBrowserRow row;
                row.key = "workshop:" + id; row.type = "workshop"; row.itemId = id;
                row.title = text(items[i], "title", "Training map");
                row.subtitle = text(items[i], "creator", text(items[i], "origin", "Workshop"));
                row.detail = text(items[i], "description", text(items[i], "availability"));
                row.primaryLabel = "Play";
                if (const auto* package = findNativeWorkshopPackage(workshop, id)) {
                    const char* block = workshopBlock(items[i], workshop, busy(state));
                    row.primaryEnabled = block == nullptr; row.reason = block ? block : "";
                    row.workshop.rowId = package->rowId; row.workshop.workshopId = package->workshopId;
                    row.workshop.title = row.title; row.workshop.contentRoot = package->contentRoot;
                    row.workshop.packagePath = package->packagePath; row.workshop.nonce = workshop.nonce;
                    row.workshop.generation = workshop.generation; row.workshopStamp = stampWorkshop(row.workshop);
                } else row.reason = mapReason(items[i]);
                row.favorite = browserFavorite(state, row.type, id) || flag(items[i], "favorite", false);
                add(std::move(row));
            }
            const auto catalog = catalogOf(state);
            const auto source = catalogSourceOf(text(catalog, "source"));
            if (source == CatalogSource::SteamMaps || source == CatalogSource::BakkesMaps) {
                const auto items = array(catalog, "items");
                const auto stop = (std::min)(items.size(), kMaxPublicCatalogRows);
                for (std::size_t i = 0; i < stop; ++i) {
                    std::int64_t sourceId = 0; if (!catalogRow(items[i], source, sourceId)) continue;
                    TrainingBrowserRow row;
                    row.key = "workshop:" + text(items[i], "id"); row.type = "workshop"; row.itemId = text(items[i], "id");
                    row.title = text(items[i], "title", "Training map"); row.subtitle = text(items[i], "creator");
                    row.detail = catalogDetail(items[i], source); row.primaryLabel = "Open source";
                    row.primaryEnabled = !catalogBusy(catalog); row.reason = row.primaryEnabled ? "" : kWait;
                    row.action = "community_open_item"; row.payload = {{"source", catalogSourceName(source)}, {"id", sourceId}};
                    row.favorite = browserFavorite(state, row.type, row.itemId); add(std::move(row));
                }
            }
            return rows;
        }
        const auto plugins = object(state, "community_plugins");
        const bool waiting = flag(plugins, "busy", false) || busy(state);
        const auto known = array(plugins, "catalog");
        const auto knownStop = (std::min)(known.size(), kScanCap);
        for (std::size_t i = 0; i < knownStop; ++i) {
            const auto id = text(known[i], "id"); if (!pluginId(id)) continue;
            TrainingBrowserRow row;
            row.key = "plugin:" + id; row.type = "plugin"; row.itemId = id;
            row.title = text(known[i], "title", "Plugin"); row.subtitle = "BakkesMod plugin";
            row.detail = "Check the current release. Activation remains unavailable."; row.primaryLabel = "Check release";
            row.primaryEnabled = !waiting; row.reason = waiting ? kWait : "";
            row.action = "community_lookup"; row.payload = {{"id", id}};
            row.favorite = browserFavorite(state, row.type, id); add(std::move(row));
        }
        const auto catalog = catalogOf(state);
        if (catalogSourceOf(text(catalog, "source")) == CatalogSource::BakkesPlugins) {
            const auto items = array(catalog, "items");
            const auto stop = (std::min)(items.size(), kMaxPublicCatalogRows);
            for (std::size_t i = 0; i < stop; ++i) {
                std::int64_t sourceId = 0; if (!catalogRow(items[i], CatalogSource::BakkesPlugins, sourceId)) continue;
                const auto id = std::to_string(sourceId); bool duplicate = false;
                for (const auto& existing : rows) if (existing.itemId == id) { duplicate = true; break; }
                if (duplicate) continue;
                TrainingBrowserRow row;
                row.key = "plugin:" + id; row.type = "plugin"; row.itemId = id;
                row.title = text(items[i], "title", "Plugin"); row.subtitle = text(items[i], "creator");
                row.detail = catalogDetail(items[i], CatalogSource::BakkesPlugins); row.primaryLabel = "Check release";
                row.primaryEnabled = !catalogBusy(catalog) && !waiting;
                row.reason = row.primaryEnabled ? "" : kWait;
                row.action = "community_select_plugin";
                row.payload = {{"source", "bakkes_plugins"}, {"id", sourceId}};
                row.favorite = browserFavorite(state, row.type, id); add(std::move(row));
            }
        }
        return rows;
    }

    void buildTraining(CareerLayoutView& view, const Json& state, const NativeWorkshopContext& workshop) const {
        view.title = "Training";
        const auto lessons = lessonsOf(state);
        if (lessons.empty()) addLine(view.body, "No training lessons are available.");
        else {
            const auto pages = (lessons.size() + kLessonsPerPage - 1) / kLessonsPerPage;
            const auto page = shownLessonPage(lessons.size());
            addLine(view.body, "Choose a lesson. Page " + std::to_string(page + 1) + " of " + std::to_string(pages) + ".");
            const auto first = page * kLessonsPerPage;
            const bool canSelect = !busy(state);
            for (std::size_t i = first; i < (std::min)(first + kLessonsPerPage, lessons.size()); ++i) {
                const auto id = text(lessons[i], "id");
                CareerLayoutChoice choice;
                choice.id = "training.lesson." + id; choice.label = plain(text(lessons[i], "title", "Lesson"), 64);
                choice.enabled = canSelect; choice.reason = canSelect ? "" : kWait;
                choice.kind = CareerLayoutEffectKind::Dispatch; choice.action = "select_lesson";
                choice.lessonId = id; choice.payload = {{"id", id}}; push(view, std::move(choice));
            }
            if (pages > 1) navigate(view, "training.next", "Next page", CareerLayoutPage::Training, (page + 1) % pages);
        }
        view.browser.active = true; view.browser.tab = browserTab_; view.browser.query = browserQuery_;
        auto rows = browserRows(browserTab_, state, workshop);
        rows.erase(std::remove_if(rows.begin(), rows.end(), [&](const TrainingBrowserRow& row) {
            return !queryMatches(row, browserQuery_);
        }), rows.end());
        view.browser.total = rows.size();
        const auto maximum = rows.size() > 8 ? rows.size() - 8 : 0;
        view.browser.offset = (std::min)(browserOffset_, maximum);
        const auto last = (std::min)(rows.size(), view.browser.offset + kMaxBrowserRows);
        for (std::size_t i = view.browser.offset; i < last; ++i) view.browser.rows.push_back(std::move(rows[i]));
        const auto catalog = catalogOf(state);
        const auto source = catalogSourceOf(text(catalog, "source"));
        const bool catalogWaiting = catalogBusy(catalog) || busy(state);
        int sourcePage = 1;
        if (!whole(catalog, "page", sourcePage, 1, kMaxCatalogPage)) sourcePage = 1;
        const auto sourceAllowed = browserTab_ == TrainingBrowserTab::Workshop
            ? source == CatalogSource::SteamMaps || source == CatalogSource::BakkesMaps
            : browserTab_ == TrainingBrowserTab::Mods ? source == CatalogSource::BakkesPlugins : false;
        if (browserTab_ == TrainingBrowserTab::Workshop) {
            browserTool(view.browser, "refresh-workshop", "Refresh library", !busy(state), kWait,
                "refresh_workshop", Json::object());
            browserTool(view.browser, "source-steam", "Browse Steam Maps", !catalogWaiting, kWait,
                "community_browse", {{"source", "steam_maps"}, {"page", 1}, {"query", ""}});
            browserTool(view.browser, "source-bakkes-maps", "Browse Bakkes Maps", !catalogWaiting, kWait,
                "community_browse", {{"source", "bakkes_maps"}, {"page", 1}, {"query", ""}});
        } else if (browserTab_ == TrainingBrowserTab::Mods) {
            const auto plugins = object(state, "community_plugins");
            const bool pluginWaiting = flag(plugins, "busy", false) || busy(state);
            const auto selected = object(plugins, "selected");
            browserTool(view.browser, "source-bakkes-plugins", "Browse BakkesMod plugins", !catalogWaiting, kWait,
                "community_browse", {{"source", "bakkes_plugins"}, {"page", 1}, {"query", ""}});
            browserTool(view.browser, "plugin-paste", "Paste plugin link", !pluginWaiting, kWait,
                "community_paste_link", Json::object());
            browserTool(view.browser, "plugin-download", "Download to private library",
                !pluginWaiting && !selected.empty() && !flag(selected, "can_activate", true),
                selected.empty() ? "Check a plugin's current release first." : kActivationReason,
                "community_download", Json::object());
            browserTool(view.browser, "plugin-library", "Check downloaded files", !pluginWaiting, kWait,
                "community_library", Json::object());
            browserTool(view.browser, "plugin-cancel", "Cancel plugin request", flag(plugins, "busy", false),
                "Nothing is downloading.", "community_cancel", Json::object());
        }
        if (browserTab_ == TrainingBrowserTab::Workshop || browserTab_ == TrainingBrowserTab::Mods) {
            if (sourceAllowed)
                browserTool(view.browser, "source-open", "Open official catalog page", !catalogWaiting, kWait,
                    "community_open_source", {{"source", catalogSourceName(source)}});
            if (sourceAllowed && flag(catalog, "has_next", false) && sourcePage < kMaxCatalogPage)
                view.browser.hasMore = !catalogWaiting;
            browserTool(view.browser, "source-cancel", "Cancel catalog read", catalogBusy(catalog),
                "Nothing is loading.", "community_browse_cancel", Json::object());
        }
        if ((browserTab_ == TrainingBrowserTab::Workshop || browserTab_ == TrainingBrowserTab::Mods) && catalogBusy(catalog))
            view.browser.state = TrainingBrowserState::Loading;
        else if ((browserTab_ == TrainingBrowserTab::Workshop || browserTab_ == TrainingBrowserTab::Mods) &&
                 text(catalog, "status") == "error" && view.browser.rows.empty())
            view.browser.state = TrainingBrowserState::Error;
        else if (view.browser.rows.empty()) view.browser.state = TrainingBrowserState::Empty;
        view.browser.revision = revision_;
        back(view, CareerLayoutPage::Root);
    }

    void buildLesson(CareerLayoutView& view, const Json& state) const {
        view.title = "Training";
        const auto lessons = lessonsOf(state);
        const auto lesson = findLesson(lessons, lessonId_);
        const auto page = shownLessonPage(lessons.size());
        if (!lesson.empty() && lessonId_ == "power-shots") {
            view.title = "Power Shots";
            addLine(view.body, "Choose your rank.");
            struct Rank { const char* id; const char* label; };
            const Rank ranks[] = {{"bronze", "Bronze"}, {"silver", "Silver"},
                {"gold", "Gold"}, {"platinum", "Platinum"}, {"diamond", "Diamond"},
                {"champion", "Champion"}, {"grand-champion", "Grand Champion"},
                {"supersonic-legend", "Supersonic Legend"}};
            for (const auto& rank : ranks)
                dispatch(view, std::string("training.rank.") + rank.id, rank.label,
                    lessonReady(state), kRecover, "start_lesson",
                    {{"id", lessonId_}, {"scenario_id", "low-side-pass"}, {"difficulty", rank.id}});
            back(view, CareerLayoutPage::Training, page);
            return;
        }
        if (lesson.empty()) addLine(view.body, "This lesson is no longer available.");
        else {
            addLine(view.body, plain(text(lesson, "title", "Lesson"), 80));
            addLine(view.body, plain(text(lesson, "description"), 180));
            const auto steps = array(lesson, "steps");
            const auto stop = (std::min)(steps.size(), static_cast<std::size_t>(6));
            for (std::size_t i = 0; i < stop; ++i)
                if (steps[i].is_string()) addLine(view.body, std::to_string(i + 1) + ". " + plain(steps[i].get<std::string>(), 120));
            const bool canPractice = lessonReady(state);
            CareerLayoutChoice start;
            start.id = "training.practice";
            start.label = "Start practice";
            start.kind = CareerLayoutEffectKind::Dispatch;
            start.action = "start_lesson";
            start.lessonId = lessonId_;
            start.enabled = canPractice;
            start.reason = canPractice ? "" : "Leave the current activity before starting another lesson.";
            start.payload = {{"id", lessonId_}};
            push(view, std::move(start));
            const char* helpKeys[] = {"explanations", "actions", "timing", "auto_reset"};
            const char* helpLabels[] = {"Step-by-step explanations", "Action input display",
                "Timing feedback", "Automatic reset"};
            const bool helpDefaults[] = {true, true, true, false};
            const bool canEdit = !busy(state);
            for (std::size_t i = 0; i < 4; ++i) {
                const bool current = assist(state, lessonId_, helpKeys[i], helpDefaults[i]);
                dispatch(view, std::string("training.help.") + helpKeys[i],
                    std::string(current ? "Turn off " : "Turn on ") + helpLabels[i], canEdit, kWait,
                    "assistance", {{"id", lessonId_}, {"key", helpKeys[i]}, {"value", !current}});
            }
            addLine(view.body, "Recorded ghost practice is controlled from the pause menu during practice. "
                "It plays at normal speed, slightly ahead of your car, and loops. It has no pause or slow-motion option.");
            const bool canVariant = canEdit && !workerLikely(state);
            const char* variantWait = workerLikely(state) ? "Stop the lesson before changing its starting setup." : kWait;
            dispatch(view, "training.side.left", "Start from the left", canVariant, variantWait, "lesson_variant",
                {{"id", lessonId_}, {"key", "side"}, {"value", "left"}});
            dispatch(view, "training.side.right", "Start from the right", canVariant, variantWait, "lesson_variant",
                {{"id", lessonId_}, {"key", "side"}, {"value", "right"}});
            dispatch(view, "training.angle.center", "Approach from the center", canVariant, variantWait, "lesson_variant",
                {{"id", lessonId_}, {"key", "angle"}, {"value", "center"}});
            dispatch(view, "training.angle.left", "Approach from the left", canVariant, variantWait, "lesson_variant",
                {{"id", lessonId_}, {"key", "angle"}, {"value", "left"}});
            dispatch(view, "training.angle.right", "Approach from the right", canVariant, variantWait, "lesson_variant",
                {{"id", lessonId_}, {"key", "angle"}, {"value", "right"}});
            if (goalLesson(lesson)) {
                struct Zone { const char* id; const char* label; const char* value; };
                const Zone zones[] = {{"left", "Target the left of the goal", "left"}, {"center", "Target the center of the goal", "center"},
                    {"right", "Target the right of the goal", "right"}, {"whole", "Target the whole goal", "whole"}};
                for (const auto& zone : zones)
                    dispatch(view, std::string("training.zone.") + zone.id, zone.label, canVariant, variantWait, "lesson_variant",
                        {{"id", lessonId_}, {"key", "target_zone"}, {"value", zone.value}});
            }
            if (lessonId_ == "flip-reset") {
                dispatch(view, "training.simple.on", "Shortened approach", canVariant, variantWait, "lesson_variant",
                    {{"id", lessonId_}, {"key", "simplified"}, {"value", true}});
                dispatch(view, "training.simple.off", "Full approach", canVariant, variantWait, "lesson_variant",
                    {{"id", lessonId_}, {"key", "simplified"}, {"value", false}});
            }
            dispatch(view, "training.restore", "Restore explanations", canEdit, kWait, "restore_explanations", {{"id", lessonId_}});
        }
        back(view, CareerLayoutPage::Training, page);
    }

    void buildSchedule(CareerLayoutView& view, const Json& state) const {
        view.title = "Schedule";
        const auto fixtures = array(currentSeason(careerOf(state)), "fixtures");
        addLine(view.body, "Upcoming matches.");
        std::size_t shown = 0;
        const auto stop = (std::min)(fixtures.size(), static_cast<std::size_t>(256));
        for (std::size_t i = 0; i < stop && shown < kMaxRows; ++i) {
            const auto& fixture = fixtures[i];
            if (text(fixture, "status") == "completed") continue;
            const auto home = text(fixture, "home");
            const auto away = text(fixture, "away");
            if (home != "human" && away != "human") continue;
            int round = 0;
            std::string prefix = "Match";
            if (whole(fixture, "round", round, 1, 64)) prefix = "Round " + std::to_string(round);
            addLine(view.body, prefix + ": " + clubName(state, home) + " vs " + clubName(state, away));
            ++shown;
        }
        if (!shown) addLine(view.body, "No upcoming matches.");
        addSummary(view.body, NativeCareerManagement::recentHumanResults(state));
        back(view, CareerLayoutPage::Career);
    }

    static void management(CareerLayoutView& view, const Json& state, const NativeManagementView& source) {
        view.title = source.title;
        view.body = source.body;
        for (const auto& item : source.choices) {
            CareerLayoutChoice choice;
            choice.id = item.id;
            choice.label = item.label;
            choice.enabled = item.enabled;
            choice.reason = item.reason;
            choice.kind = CareerLayoutEffectKind::Dispatch;
            choice.action = item.action;
            choice.payload = item.payload;
            choice.careerId = text(careerOf(state), "id");
            push(view, std::move(choice));
        }
    }

    void buildCreate(CareerLayoutView& view, const Json& state) const {
        management(view, state, NativeCareerManagement::create(state));
        back(view, CareerLayoutPage::Career);
    }

    void buildStandings(CareerLayoutView& view, const Json& state) const {
        management(view, state, NativeCareerManagement::season(state));
        back(view, CareerLayoutPage::Career);
    }

    void buildSquad(CareerLayoutView& view, const Json& state) const {
        management(view, state, NativeCareerManagement::squad(state));
        back(view, CareerLayoutPage::Career);
    }

    void buildRules(CareerLayoutView& view, const Json& state) const {
        management(view, state, NativeCareerManagement::rules(state));
        addLine(view.body, "Ground Specialists use the difficulty settings. Necto and Nexto use fixed trained policies.");
        addLine(view.body, "For 4v4, choose Ground Specialists.");
        const auto career = careerOf(state);
        int format = 0;
        const bool canEdit = ready(state) && whole(career, "format", format, 1, 4);
        const auto providers = array(state, "providers");
        struct Provider { const char* id; const char* name; };
        const Provider known[] = {{"mct-specialist-baseline", "Ground Specialists"}, {"necto", "Necto"}, {"nexto", "Nexto"}};
        for (const auto& item : known) {
            Json provider = Json::object();
            for (std::size_t index = 0; index < (std::min)(providers.size(), kScanCap); ++index)
                if (text(providers[index], "id") == item.id) { provider = providers[index]; break; }
            const auto formats = array(provider, "supported_formats");
            bool supports = false;
            for (std::size_t index = 0; index < (std::min)(formats.size(), kScanCap); ++index)
                if (formats[index].is_number_integer() && formats[index] == format) supports = true;
            const bool available = flag(provider, "available", false);
            const bool enabled = canEdit && available && supports;
            std::string reason = !canEdit ? kRecover : !available ? text(provider, "reason", "This bot provider is unavailable.") :
                "This provider does not support the current format.";
            const std::string label = std::string(text(state, "selected_provider") == item.id ? "Selected: " : "Bots: ") + item.name;
            dispatch(view, std::string("rules.provider.") + item.id, label, enabled, reason,
                "choose_provider", {{"id", item.id}});
        }
        back(view, CareerLayoutPage::Career);
    }

    void buildGarage(CareerLayoutView& view, const Json& state) const {
        view.title = "Garage";
        addSummary(view.body, NativeCareerManagement::rewardSummary(state));
        addLine(view.body, "Your car stays in the game's garage.");
        addLine(view.body, "Bot presets below are local career appearances. They do not add items to your garage.");
        addLine(view.body, "Local appearance is a separate machine override, not a bot preset.");
        CareerLayoutChoice stock;
        stock.id = "garage.player";
        stock.label = "Your car";
        stock.enabled = true;
        stock.kind = CareerLayoutEffectKind::PreserveStockRoute;
        stock.stock = StockRoute::Garage;
        push(view, std::move(stock));
        navigate(view, kAppearance, "Local appearance", CareerLayoutPage::Appearance);
        const auto career = careerOf(state);
        const auto recruits = object(career, "recruits");
        const auto squad = array(career, "squad");
        const auto catalog = array(state, "garage");
        const bool canSave = ready(state) && !career.empty();
        const auto squadStop = (std::min)(squad.size(), kMaxSquad);
        const auto catalogStop = (std::min)(catalog.size(), kScanCap);
        for (std::size_t s = 0; s < squadStop; ++s) {
            if (!squad[s].is_string()) continue;
            const auto recruitId = squad[s].get<std::string>();
            if (!validId(recruitId) || objectKey(recruits, recruitId).empty()) continue;
            const auto recruitName = plain(text(objectKey(recruits, recruitId), "name", "Bot"), 32);
            for (std::size_t g = 0; g < catalogStop && view.choices.size() + 1 < kMaxChoices; ++g) {
                const auto& entry = catalog[g];
                const auto catalogId = text(entry, "id");
                int car = 0, primary = 0, secondary = 0;
                if (!validId(catalogId) || !whole(entry, "car_id", car, 0, 99999) || !supportedBody(car)) continue;
                if (!whole(entry, "primary_color", primary, 0, 69) || !whole(entry, "secondary_color", secondary, 0, 104)) continue;
                CareerLayoutChoice choice;
                choice.id = "garage.bot." + recruitId + "." + catalogId;
                choice.label = "Use " + plain(text(entry, "title", text(entry, "name", "Bot appearance")), 32) + " for " + recruitName;
                choice.kind = CareerLayoutEffectKind::Dispatch;
                choice.action = "loadout";
                choice.recruitId = recruitId;
                choice.itemId = catalogId;
                choice.enabled = canSave;
                choice.reason = canSave ? "" : (career.empty() ? "Create a career before choosing a bot appearance." : kRecover);
                choice.payload = {{"id", recruitId}, {"car_id", car}, {"primary_color", primary}, {"secondary_color", secondary}};
                push(view, std::move(choice));
            }
        }
        if (career.empty()) addLine(view.body, "Create a career before choosing a bot appearance.");
        back(view, CareerLayoutPage::Root);
    }

    static bool digitsOnly(const std::string& value) {
        if (value.empty() || value.size() > 20) return false;
        for (unsigned char character : value)
            if (character < '0' || character > '9') return false;
        return true;
    }

    static std::uint64_t stampWorkshop(const NativeWorkshopRequest& request) {
        std::uint64_t hash = kStampBasis;
        hash = mixStamp(hash, request.rowId);
        hash = mixStamp(hash, request.workshopId);
        hash = mixStamp(hash, request.contentRoot);
        hash = mixStamp(hash, request.packagePath);
        hash = mixStamp(hash, request.nonce);
        hash = mixStamp(hash, request.generation);
        return hash;
    }

    static const char* workshopBlock(const Json& item, const NativeWorkshopContext& workshop, bool waiting) {
        if (waiting) return kWait;
        if (workshop.blocked) return "Close this session before loading another map.";
        if (workshop.preparing) return "Preparing this map.";
        if (!workshop.scopeReady) return "Play is available during an offline career session.";
        if (findNativeWorkshopPackage(workshop, text(item, "id"))) return nullptr;
        const auto origin = text(item, "origin");
        if (origin == "local_import") return "Imported maps cannot be played from this menu yet.";
        if (item.is_object() && item.contains("installed") && item["installed"].is_boolean() &&
            !item["installed"].get<bool>())
            return "Not installed";
        if (origin == "catalog") return "Choose the installed map file.";
        if (!workshop.libraryConfirmed) return "This game's Steam library could not be confirmed.";
        return "This map is in another Steam library.";
    }

    void buildWorkshop(CareerLayoutView& view, const Json& state, const NativeWorkshopContext& workshop) const {
        view.title = "Workshop";
        const auto library = object(state, "workshop");
        const auto note = text(library, "note");
        const char* published =
            "Browse installed maps and save favorites. Custom map launch is paused while a loader "
            "that preserves your Steam game is being developed.";
        if (workshop.bound && !workshop.status.empty()) addLine(view.body, workshop.status);
        else addLine(view.body, note == published ? published : "Browse installed maps and save favorites.");
        // Workshop has exactly two content tabs: Training Maps and Mods.
        navigate(view, "workshop.tab.maps", "Training Maps", CareerLayoutPage::Workshop, 0);
        navigate(view, "workshop.tab.mods", "Mods", CareerLayoutPage::WorkshopMods);
        const bool canEdit = !busy(state);
        dispatch(view, "workshop.refresh", "Refresh library", canEdit, kWait, "refresh_workshop", Json::object());
        navigateCatalog(view, "workshop.catalog.open", "Browse online maps", CatalogCategory::Maps,
            CareerLayoutPage::Workshop);
        const auto items = array(library, "items");
        const auto stop = (std::min)(items.size(), workshop.bound ? kMaxWorkshopRows : kScanCap);
        std::vector<std::size_t> rows;
        for (std::size_t index = 0; index < stop; ++index)
            if (safeId(text(items[index], "id"))) rows.push_back(index);
        const std::size_t pages = rows.empty() ? 1 : (rows.size() + kMaxRows - 1) / kMaxRows;
        const std::size_t page = workshopPage_ < pages ? workshopPage_ : pages - 1;
        const std::size_t first = page * kMaxRows;
        const std::size_t last = (std::min)(rows.size(), first + kMaxRows);
        for (std::size_t slot = first; slot < last; ++slot) {
            const auto& item = items[rows[slot]];
            const auto id = text(item, "id");
            const auto title = plain(text(item, "title", "Map"), 48);
            const bool favorite = flag(item, "favorite", false);
            dispatch(view, "workshop.favorite." + id, (favorite ? "Remove " : "Save ") + title + (favorite ? " from favorites" : " to favorites"),
                canEdit, kWait, "workshop_favorite", {{"id", id}});
            CareerLayoutChoice play;
            play.id = "workshop.play." + id;
            play.label = "Play " + title;
            play.itemId = id;
            if (!workshop.bound) {
                play.enabled = false;
                play.kind = CareerLayoutEffectKind::Unavailable;
                play.reason = mapReason(item);
            } else if (const char* block = workshopBlock(item, workshop, !canEdit)) {
                play.enabled = false;
                play.kind = CareerLayoutEffectKind::Unavailable;
                play.reason = block;
            } else {
                const auto* package = findNativeWorkshopPackage(workshop, id);
                play.enabled = package != nullptr;
                play.kind = package ? CareerLayoutEffectKind::LocalWorkshop : CareerLayoutEffectKind::Unavailable;
                if (!package) {
                    play.reason = "Not installed";
                } else {
                    play.workshop.rowId = package->rowId;
                    play.workshop.workshopId = package->workshopId;
                    play.workshop.title = title;
                    play.workshop.contentRoot = package->contentRoot;
                    play.workshop.packagePath = package->packagePath;
                    play.workshop.nonce = workshop.nonce;
                    play.workshop.generation = workshop.generation;
                    play.workshopStamp = stampWorkshop(play.workshop);
                }
            }
            push(view, std::move(play));
        }
        if (page > 0)
            navigate(view, "workshop.page.previous", "Previous maps", CareerLayoutPage::Workshop, page - 1);
        if (last < rows.size())
            navigate(view, "workshop.page.next", "More maps", CareerLayoutPage::Workshop, page + 1);
        if (rows.empty()) addLine(view.body, "No workshop maps are in the library yet.");
        back(view, CareerLayoutPage::Root);
    }

    // ---- Workshop Mods tab and public catalog browsing ------------------- //

    static Json catalogOf(const Json& state) { return object(state, "community_catalog"); }

    static bool catalogBusy(const Json& catalog) {
        return flag(catalog, "busy", false) || flag(catalog, "loading", false);
    }

    // Strict JSON integer for a catalog source id. Booleans, floating point
    // numbers, and out-of-range values are refused. The parser accepts ids up
    // to 9999999999, so a 32-bit int would drop real Steam map ids.
    static bool catalogId(const Json& value, const char* key, std::int64_t& out) {
        if (!value.is_object()) return false;
        const auto it = value.find(key);
        if (it == value.end() || !it->is_number_integer()) return false;
        std::int64_t number = 0;
        if (it->is_number_unsigned()) {
            const auto wide = it->get<std::uint64_t>();
            if (wide > static_cast<std::uint64_t>(kMaxCatalogSourceId)) return false;
            number = static_cast<std::int64_t>(wide);
        } else {
            number = it->get<std::int64_t>();
        }
        if (number < 1 || number > kMaxCatalogSourceId) return false;
        out = number;
        return true;
    }

    // One displayed catalog row. Only rows the backend marked catalog-only and
    // non-activatable are accepted, and the numeric source id must be present.
    static bool catalogRow(const Json& item, CatalogSource source, std::int64_t& sourceId) {
        if (!item.is_object()) return false;
        if (catalogSourceOf(text(item, "source")) != source || source == CatalogSource::None) return false;
        if (!flag(item, "catalog_only", false) || flag(item, "can_activate", true)) return false;
        if (!catalogId(item, "source_id", sourceId)) return false;
        if (text(item, "id") != std::string(catalogSourceName(source)) + ":" + std::to_string(sourceId)) return false;
        return !text(item, "title").empty();
    }

    // Bounded, meaningful detail for one public catalog row. Only fields the
    // backend already validated and bounded are used; nothing is invented and no
    // generic placeholder replaces real metadata.
    static std::string catalogDetail(const Json& item, CatalogSource source) {
        std::string detail;
        const auto description = plain(text(item, "description"), 160);
        if (!description.empty()) detail = description;
        const auto creator = plain(text(item, "creator"), 48);
        if (!creator.empty() && creator != "Unknown creator") {
            if (!detail.empty()) detail += " - ";
            detail += "By " + creator;
        }
        const auto category = plain(text(item, "kind"), 24);
        const auto label = category.empty()
            ? (source == CatalogSource::BakkesPlugins ? "BakkesMod plugin" : "Workshop map") : category;
        if (!detail.empty()) detail += " - ";
        detail += label + " - public listing, not installed or enabled.";
        return plain(detail, kMaxBrowserDisplay);
    }

    static std::size_t catalogPages(std::size_t count) {
        return count == 0 ? 1 : (count + kCatalogRowsPerPage - 1) / kCatalogRowsPerPage;
    }

    void pushCatalogSource(CareerLayoutView& view, CatalogSource source, const char* label,
                           CatalogSource current, bool waiting) const {
        const bool selected = source == current;
        dispatch(view, std::string("catalog.source.") + catalogSourceName(source),
            std::string(selected ? "Selected: " : "Browse ") + label, !waiting, kWait, "community_browse",
            {{"source", catalogSourceName(source)}, {"page", 1}, {"query", ""}});
    }

    void buildWorkshopMods(CareerLayoutView& view, const Json& state) const {
        view.title = "Workshop - Mods";
        addLine(view.body, "Mods lists community plugins and maps. Listing is not a compatibility claim.");
        addLine(view.body, "Downloaded plugins stay in this private cache and are not enabled.");
        const auto plugins = object(state, "community_plugins");
        const auto message = text(plugins, "message");
        if (!message.empty()) addLine(view.body, message);
        const bool waiting = flag(plugins, "busy", false) || busy(state);
        const auto catalog = catalogOf(state);
        const auto catalogWaiting = catalogBusy(catalog) || waiting;
        pushCatalogSource(view, CatalogSource::BakkesPlugins, "BakkesMod plugins", CatalogSource::None, catalogWaiting);
        dispatch(view, "mods.paste", "Paste plugin link", !waiting, kWait, "community_paste_link", Json::object());
        const auto known = array(plugins, "catalog");
        std::size_t shown = 0;
        const auto stop = (std::min)(known.size(), kScanCap);
        for (std::size_t i = 0; i < stop && shown < kMaxRows; ++i) {
            const auto id = text(known[i], "id");
            if (!pluginId(id)) continue;
            const auto title = plain(text(known[i], "title", "Plugin"), 48);
            dispatch(view, "community.lookup." + id, "Check " + title, !waiting, kWait, "community_lookup", {{"id", id}});
            ++shown;
        }
        const auto selected = object(plugins, "selected");
        const auto selectedId = text(selected, "id");
        const bool selectedOk = !selected.empty() && pluginId(selectedId) && !flag(selected, "can_activate", false);
        std::string downloadReason = "Check a plugin's current release before downloading it.";
        if (waiting) downloadReason = kWait;
        else if (!selected.empty() && flag(selected, "can_activate", false)) downloadReason = kActivationReason;
        dispatch(view, "community.download", "Download to library", selectedOk && !waiting, downloadReason,
            "community_download", Json::object());
        dispatch(view, "community.library", "Check downloaded files", !waiting, kWait, "community_library", Json::object());
        dispatch(view, "community.cancel", "Cancel download", flag(plugins, "busy", false), "Nothing is downloading.",
            "community_cancel", Json::object());
        CareerLayoutChoice activate;
        activate.id = "community.activate";
        activate.label = "Enable in game";
        activate.enabled = false;
        activate.kind = CareerLayoutEffectKind::Unavailable;
        activate.reason = kActivationReason;
        push(view, std::move(activate));
        navigateCatalog(view, "mods.catalog", "Browse plugin catalog", CatalogCategory::Plugins,
            CareerLayoutPage::WorkshopMods);
        back(view, CareerLayoutPage::Workshop);
    }

    void buildWorkshopCatalog(CareerLayoutView& view, const Json& state) const {
        const auto catalog = catalogOf(state);
        const auto backendSource = catalogSourceOf(text(catalog, "source"));
        const bool plugins = catalogCategory_ == CatalogCategory::Plugins;
        // The backend catalog source is shared between the Maps and Mods entries.
        // A result that does not belong to this entry's category is not this
        // catalog's result: no rows, no download, and no check actions.
        const bool matching = catalogCategoryHas(catalogCategory_, backendSource);
        const auto source = matching ? backendSource : CatalogSource::None;
        view.title = plugins ? "Workshop - Mods catalog" : "Workshop - Training Maps catalog";
        const auto status = text(catalog, "status");
        const bool waiting = catalogBusy(catalog);
        int onlinePage = 1;
        if (!whole(catalog, "page", onlinePage, 1, kMaxCatalogPage)) onlinePage = 1;
        addLine(view.body, "Catalog links only. Nothing is downloaded, installed, or enabled.");
        addLine(view.body, "Details open the creator's own page in your browser.");
        // A message from the other entry's read is not this catalog's message.
        const auto message = matching ? text(catalog, "message") : std::string();
        if (!message.empty()) addLine(view.body, message);
        if (waiting) addLine(view.body, "Reading one public catalog page. Cancel stops it.");
        else if (backendSource != CatalogSource::None && !matching)
            addLine(view.body, "The last catalog read was for a different source. Choose a source, then Browse.");
        else if (status == "error") addLine(view.body, "The catalog page could not be read. Nothing was downloaded.");
        else if (status == "cancelled") addLine(view.body, "The catalog read was cancelled. Nothing was downloaded.");
        else if (status == "empty_page") addLine(view.body, "This catalog page listed no items.");
        else if (!flag(catalog, "fetched", false)) addLine(view.body, "Choose a source, then Browse to read one page.");
        // Only this entry's own sources are offered. Browsing one page is an
        // explicit click; building the view never dispatches a network read.
        if (plugins) {
            pushCatalogSource(view, CatalogSource::BakkesPlugins, "BakkesMod plugins", source, waiting);
        } else {
            pushCatalogSource(view, CatalogSource::SteamMaps, "Steam Maps", source, waiting);
            pushCatalogSource(view, CatalogSource::BakkesMaps, "Bakkes Maps", source, waiting);
        }
        if (source != CatalogSource::None) {
            dispatch(view, "catalog.browse", "Browse page " + std::to_string(onlinePage), !waiting, kWait,
                "community_browse", {{"source", catalogSourceName(source)}, {"page", onlinePage}, {"query", ""}});
            dispatch(view, "catalog.source.open", "Open official page", !waiting, kWait, "community_open_source",
                {{"source", catalogSourceName(source)}});
        }
        dispatch(view, "catalog.cancel", "Cancel catalog read", waiting, "Nothing is loading.", "community_browse_cancel",
            Json::object());
        // Local page slice over the rows of the one online page that was read.
        std::vector<Json> rows;
        if (source != CatalogSource::None) {
            const auto items = array(catalog, "items");
            const auto stop = (std::min)(items.size(), kMaxCatalogRows);
            for (std::size_t index = 0; index < stop; ++index) {
                std::int64_t sourceId = 0;
                if (catalogRow(items[index], source, sourceId)) rows.push_back(items[index]);
            }
        }
        const auto pages = catalogPages(rows.size());
        const auto page = catalogPage_ < pages ? catalogPage_ : pages - 1;
        if (!rows.empty())
            addLine(view.body, "Page " + std::to_string(page + 1) + " of " + std::to_string(pages) + " on this catalog page.");
        const auto first = page * kCatalogRowsPerPage;
        const auto last = (std::min)(first + kCatalogRowsPerPage, rows.size());
        for (std::size_t index = first; index < last; ++index) {
            std::int64_t sourceId = 0;
            if (!catalogRow(rows[index], source, sourceId)) continue;
            const auto title = plain(text(rows[index], "title", "Item"), 48);
            const auto creator = plain(text(rows[index], "creator", "Unknown creator"), 32);
            dispatch(view, "catalog.open." + std::to_string(sourceId), "Open " + title + " by " + creator, !waiting, kWait,
                "community_open_item", {{"source", catalogSourceName(source)}, {"id", sourceId}});
            if (source == CatalogSource::BakkesPlugins)
                dispatch(view, "catalog.plugin." + std::to_string(sourceId), "Check " + title, !waiting, kWait,
                    "community_select_plugin", {{"source", catalogSourceName(source)}, {"id", sourceId}});
        }
        if (page > 0) navigate(view, "catalog.page.previous", "Previous rows", CareerLayoutPage::WorkshopCatalog, page - 1);
        if (page + 1 < pages) navigate(view, "catalog.page.next", "More rows", CareerLayoutPage::WorkshopCatalog, page + 1);
        if (source != CatalogSource::None && flag(catalog, "has_next", false) && onlinePage < kMaxCatalogPage)
            dispatch(view, "catalog.page.online", "Next catalog page", !waiting, kWait, "community_browse",
                {{"source", catalogSourceName(source)}, {"page", onlinePage + 1}, {"query", ""}});
        // Back returns to the entry that opened this catalog, not to whatever
        // source the shared backend catalog currently holds.
        back(view, catalogBack_);
    }

    void buildCommunity(CareerLayoutView& view, const Json& state) const {
        view.title = "Community";
        addLine(view.body, "Core lessons work without community downloads.");
        const auto plugins = object(state, "community_plugins");
        const auto message = text(plugins, "message");
        if (!message.empty()) addLine(view.body, message);
        const bool waiting = flag(plugins, "busy", false) || busy(state);
        addLine(view.body, "Copy a plugin page link, then choose Paste plugin link.");
        navigateCatalog(view, "community.catalog", "Browse online maps", CatalogCategory::Maps,
            CareerLayoutPage::Community);
        dispatch(view, "community.paste", "Paste plugin link", !waiting, kWait,
            "community_paste_link", Json::object());
        const auto catalog = array(plugins, "catalog");
        std::size_t shown = 0;
        const auto stop = (std::min)(catalog.size(), kScanCap);
        for (std::size_t i = 0; i < stop && shown < kMaxRows; ++i) {
            const auto id = text(catalog[i], "id");
            if (!pluginId(id)) continue;
            const auto title = plain(text(catalog[i], "title", "Plugin"), 48);
            dispatch(view, "community.lookup." + id, "Check " + title, !waiting, kWait, "community_lookup", {{"id", id}});
            ++shown;
        }
        const auto selected = object(plugins, "selected");
        const auto selectedId = text(selected, "id");
        const bool selectedOk = !selected.empty() && pluginId(selectedId) && !flag(selected, "can_activate", false);
        std::string downloadReason = "Check a plugin's current release before downloading it.";
        if (waiting) downloadReason = kWait;
        else if (!selected.empty() && flag(selected, "can_activate", false)) downloadReason = kActivationReason;
        dispatch(view, "community.download", "Download to library", selectedOk && !waiting, downloadReason,
            "community_download", Json::object());
        dispatch(view, "community.library", "Check downloaded files", !waiting, kWait, "community_library", Json::object());
        const bool cancelling = flag(plugins, "busy", false);
        dispatch(view, "community.cancel", "Cancel download", cancelling, "Nothing is downloading.", "community_cancel", Json::object());
        CareerLayoutChoice activate;
        activate.id = "community.activate";
        activate.label = "Enable in game";
        activate.enabled = false;
        activate.kind = CareerLayoutEffectKind::Unavailable;
        activate.reason = kActivationReason;
        push(view, std::move(activate));
        const auto trial = object(state, "native_community_trial");
        const auto trialStatus = text(trial, "status");
        const auto trialMessage = text(trial, "message");
        if (!trialStatus.empty() || !trialMessage.empty()) {
            std::string trialShown = trialMessage;
            const bool unsafe = trialShown.find('\\') != std::string::npos || trialShown.find('/') != std::string::npos ||
                                trialShown.find("plugin load") != std::string::npos || trialShown.find(".dll") != std::string::npos;
            if (unsafe || trialShown.empty()) {
                if (trialStatus == "loaded") trialShown = "Speedflip Trainer is loaded for this offline session.";
                else if (trialStatus == "staged" || trialStatus == "pending")
                    trialShown = "The trial file is staged and is not loaded yet.";
                else if (trialStatus == "refused" || trialStatus == "unknown")
                    trialShown = "The Speedflip Trainer trial did not load.";
                else trialShown.clear();
            }
            if (!trialShown.empty()) addLine(view.body, plain(trialShown, 160));
        }
        const bool trialReady = flag(trial, "available", false) && flag(trial, "can_prepare", false) &&
                                text(trial, "site_id") == "286" && selectedId == "286" && !waiting &&
                                trialStatus != "loaded" && trialStatus != "refused" && trialStatus != "unknown";
        if (trialReady)
            dispatch(view, "community.trial.286", "Try Speedflip Trainer", true, "", "community_trial_prepare",
                     Json::object());
        const auto downloaded = array(plugins, "downloaded");
        const auto downloadedStop = (std::min)(downloaded.size(), kMaxRows);
        for (std::size_t i = 0; i < downloadedStop; ++i) {
            const auto id = text(downloaded[i], "id");
            if (!pluginId(id)) continue;
            addLine(view.body, "Plugin " + id + " is downloaded, not enabled.");
        }
        const auto content = array(state, "content");
        const auto contentStop = (std::min)(content.size(), kMaxRows);
        for (std::size_t i = 0; i < contentStop; ++i) {
            const auto title = text(content[i], "title");
            if (title.empty()) continue;
            addLine(view.body, plain(title, 48) + " by " + plain(text(content[i], "creator", "the creator"), 48));
        }
        back(view, CareerLayoutPage::Root);
    }

    void buildSettings(CareerLayoutView& view, const Json& state) const {
        view.title = "Settings";
        addLine(view.body, "Game options stay the game's own screen.");
        addLine(view.body, "Training help below uses the saved training display.");
        CareerLayoutChoice options;
        options.id = "settings.options";
        options.label = "Game options";
        options.enabled = true;
        options.kind = CareerLayoutEffectKind::PreserveStockRoute;
        options.stock = StockRoute::Options;
        push(view, std::move(options));
        const bool canEdit = !busy(state);
        addLine(view.body, "Recorded ghost practice runs at normal speed and loops while you practice. "
            "It cannot be paused, slowed, or played once from here; turn it on or off in the pause menu.");
        struct ViewChoice { const char* id; const char* label; const char* value; };
        const ViewChoice views[] = {{"player", "Ghost view: from your car", "player"}, {"chase", "Ghost view: chase", "chase"},
            {"side", "Ghost view: side", "side"}, {"top", "Ghost view: above", "top"}};
        for (const auto& item : views)
            dispatch(view, std::string("settings.view.") + item.id, item.label, canEdit, kWait, "training_settings",
                {{"key", "ghost_view"}, {"value", item.value}});
        navigate(view, "settings.career.rules", "Career rules", CareerLayoutPage::CareerRules);
        const char* profiles[] = {"actions", "keyboard", "playstation", "xbox"};
        const char* labels[] = {"Game actions", "Keyboard", "PlayStation", "Xbox"};
        for (std::size_t index = 0; index < 4; ++index) {
            const bool selected = text(object(state, "settings"), "binding_profile", "actions") == profiles[index];
            dispatch(view, std::string("settings.bindings.") + profiles[index],
                std::string("Input labels: ") + labels[index] + (selected ? " (selected)" : ""),
                canEdit, kWait, "settings", {{"key", "binding_profile"}, {"value", profiles[index]}});
        }
        dispatch(view, "settings.backup", "Back up career", canEdit, kWait, "backup_save", Json::object());
        dispatch(view, "settings.data", "Open save folder", canEdit, kWait, "open_data", Json::object());
        dispatch(view, "settings.diagnostics", "Refresh diagnostics", canEdit, kWait, "diagnostics", Json::object());
        back(view, CareerLayoutPage::Root);
    }

    static constexpr std::uint64_t kStampBasis = 14695981039346656037ull;
    static constexpr const char* kCatalogLoading = "The local catalog is still loading.";
    static constexpr const char* kItemModUnavailable = "This game build does not expose the local cosmetic override.";
    static constexpr const char* kRestoreFirst = "Restore the original cosmetic settings before applying another design.";
    static constexpr const char* kChooseItem = "Choose an item before applying a local design.";
    static constexpr const char* kColorsUnusable = "The saved colors are not usable.";

    static std::uint64_t mixStamp(std::uint64_t hash, std::uint64_t value) {
        for (int index = 0; index < 8; ++index) {
            hash ^= value & 0xffu;
            hash *= 1099511628211ull;
            value >>= 8;
        }
        return hash;
    }

    static std::uint64_t mixStamp(std::uint64_t hash, const std::string& text) {
        for (unsigned char character : text) {
            hash ^= character;
            hash *= 1099511628211ull;
        }
        return hash;
    }

    static std::uint64_t stampValue(std::uint64_t hash, int value) {
        return mixStamp(hash, static_cast<std::uint64_t>(static_cast<std::int64_t>(value)));
    }

    static std::uint64_t stampProduct(std::uint64_t hash, const NativeCosmeticProduct& product) {
        hash = stampValue(hash, product.slot);
        hash = stampValue(hash, product.id);
        hash = mixStamp(hash, product.paintable ? 1ull : 0ull);
        return mixStamp(hash, product.name);
    }

    static bool supportedCosmeticChoice(const CareerLayoutChoice& choice) {
        switch (choice.cosmetic.kind) {
        case NativeCosmeticRequestKind::SelectItem:
        case NativeCosmeticRequestKind::SelectPaint:
        case NativeCosmeticRequestKind::ClearSlot:
        case NativeCosmeticRequestKind::Apply:
        case NativeCosmeticRequestKind::Restore:
        case NativeCosmeticRequestKind::SetColorOverride:
        case NativeCosmeticRequestKind::SelectPrimaryColor:
        case NativeCosmeticRequestKind::SelectSecondaryColor:
            return choice.action.empty() && choice.payload.empty() && choice.stock == StockRoute::None;
        default:
            return false;
        }
    }

    CareerLayoutPage acceptLocal(const CareerLayoutChoice* choice) {
        if (choice && choice->cosmetic.kind == NativeCosmeticRequestKind::SelectItem) {
            cosmeticSlot_ = choice->cosmetic.slot;
            cosmeticProductId_ = choice->cosmetic.productId;
            page_ = CareerLayoutPage::CosmeticPaints;
        }
        return page_;
    }

    // Every listable product in this slot. Not capped at 24 or 64.
    static void listSlotProducts(const NativeCosmeticContext& cosmetics, int slot,
                                 std::vector<const NativeCosmeticProduct*>& out) {
        out.clear();
        if (cosmetics.scanning || !nativeCosmeticSlotEquipable(slot)) return;
        std::unordered_set<int> seen;
        for (const auto& product : nativeCosmeticCatalog(cosmetics)) {
            if (product.slot != slot || !nativeCosmeticListable(product)) continue;
            if (!seen.insert(product.id).second) continue;
            out.push_back(&product);
        }
    }

    static std::string productName(const NativeCosmeticContext& cosmetics, int slot, int productId) {
        const auto* product = findNativeCosmeticProduct(nativeCosmeticCatalog(cosmetics), slot, productId);
        return product ? product->name : std::string("Item");
    }

    static void describeCosmeticStatus(CareerLayoutView& view, const NativeCosmeticContext& cosmetics) {
        if (cosmetics.scanning) addLine(view.body, kCatalogLoading);
        else if (!cosmetics.catalog || cosmetics.catalog->empty())
            addLine(view.body, "No local cosmetic catalog is available yet.");
        if (!cosmetics.available) addLine(view.body, kItemModUnavailable);
        if (cosmetics.restorationPending) addLine(view.body, "Original cosmetic settings still need to be restored.");
        if (!cosmetics.message.empty()) addLine(view.body, "Last cosmetic action: " + cosmetics.message);
    }

    static void describeColors(CareerLayoutView& view, const NativeCosmeticContext& cosmetics) {
        if (!nativeCosmeticColorsValid(cosmetics)) {
            addLine(view.body, kColorsUnusable);
            return;
        }
        addLine(view.body, cosmetics.overrideColors ? "Color override is on." : "Color override is off.");
        addLine(view.body, std::string("Primary: ") + nativeCosmeticColorName(cosmetics.primary));
        addLine(view.body, std::string("Accent: ") + nativeCosmeticColorName(cosmetics.secondary));
    }

    static const char* colorEditBlock(const NativeCosmeticContext& cosmetics) {
        if (cosmetics.scanning) return kCatalogLoading;
        if (cosmetics.restorationPending) return kRestoreFirst;
        if (!nativeCosmeticColorsValid(cosmetics)) return kColorsUnusable;
        return nullptr;
    }

    static std::uint64_t stampChannel(std::uint64_t hash, float value) {
        static_assert(sizeof(float) == 4, "Color stamp expects a 32-bit float");
        std::uint32_t bits = 0;
        std::memcpy(&bits, &value, sizeof(bits));
        return mixStamp(hash, bits);
    }

    static std::uint64_t stampRgb(std::uint64_t hash, const std::array<float, 3>& rgb) {
        hash = stampChannel(hash, rgb[0]);
        hash = stampChannel(hash, rgb[1]);
        return stampChannel(hash, rgb[2]);
    }

    static void describeDraft(CareerLayoutView& view, const NativeCosmeticContext& cosmetics) {
        const auto live = nativeCosmeticValidatedDraft(cosmetics);
        if (live.empty() && cosmetics.draft.empty()) {
            addLine(view.body, "No local design is selected.");
            return;
        }
        for (const auto& entry : live) {
            std::string line = std::string(nativeCosmeticCategoryLabel(entry.slot)) + ": " +
                productName(cosmetics, entry.slot, entry.productId);
            if (entry.paintable && entry.paint != 0)
                line += ", " + std::string(nativeCosmeticPaintName(entry.paint));
            addLine(view.body, line);
        }
        if (live.size() != cosmetics.draft.size())
            addLine(view.body, "Some saved entries are outside this local catalog and are not part of Apply.");
    }

    static std::uint64_t stampApply(const NativeCosmeticContext& cosmetics, const NativeCosmeticRequest& request) {
        auto hash = kStampBasis;
        hash = stampValue(hash, request.draftCount);
        hash = mixStamp(hash, cosmetics.available ? 1ull : 0ull);
        hash = mixStamp(hash, cosmetics.scanning ? 1ull : 0ull);
        hash = mixStamp(hash, cosmetics.restorationPending ? 1ull : 0ull);
        const auto& catalog = nativeCosmeticCatalog(cosmetics);
        const int count = request.draftCount < 0 ? 0 : (std::min)(request.draftCount, kNativeCosmeticDraftCap);
        for (int index = 0; index < count; ++index) {
            const auto& entry = request.draft[static_cast<std::size_t>(index)];
            hash = stampValue(hash, entry.slot);
            hash = stampValue(hash, entry.productId);
            hash = stampValue(hash, entry.paint);
            hash = mixStamp(hash, entry.paintable ? 1ull : 0ull);
            const auto* product = findNativeCosmeticProduct(catalog, entry.slot, entry.productId);
            hash = mixStamp(hash, product ? product->name : std::string{});
        }
        hash = stampValue(hash, request.paletteIndex);
        hash = mixStamp(hash, request.overrideColors ? 1ull : 0ull);
        hash = mixStamp(hash, cosmetics.overrideColors ? 1ull : 0ull);
        hash = mixStamp(hash, nativeCosmeticColorsValid(cosmetics) ? 1ull : 0ull);
        hash = stampRgb(hash, request.primary);
        return stampRgb(hash, request.secondary);
    }

    void pushApply(CareerLayoutView& view, const NativeCosmeticContext& cosmetics) const {
        CareerLayoutChoice choice;
        choice.id = "cosmetic.apply";
        choice.label = "Apply local design";
        choice.kind = CareerLayoutEffectKind::LocalCosmetic;
        choice.target = CareerLayoutPage::Appearance;
        choice.cosmetic.kind = NativeCosmeticRequestKind::Apply;
        const auto live = nativeCosmeticValidatedDraft(cosmetics);
        choice.cosmetic.draftCount = static_cast<int>(live.size());
        for (int index = 0; index < choice.cosmetic.draftCount; ++index)
            choice.cosmetic.draft[static_cast<std::size_t>(index)] = live[static_cast<std::size_t>(index)];
        const bool colorsOk = nativeCosmeticColorsValid(cosmetics);
        if (colorsOk) {
            choice.cosmetic.overrideColors = cosmetics.overrideColors;
            choice.cosmetic.primary = cosmetics.primary;
            choice.cosmetic.secondary = cosmetics.secondary;
        }
        const bool ready = cosmetics.available && !cosmetics.scanning && !cosmetics.restorationPending &&
            colorsOk && (cosmetics.overrideColors || !live.empty());
        choice.enabled = ready;
        if (!ready) {
            if (cosmetics.scanning) choice.reason = kCatalogLoading;
            else if (!cosmetics.available) choice.reason = kItemModUnavailable;
            else if (cosmetics.restorationPending) choice.reason = kRestoreFirst;
            else if (!colorsOk) choice.reason = kColorsUnusable;
            else choice.reason = kChooseItem;
        }
        choice.cosmeticStamp = stampApply(cosmetics, choice.cosmetic);
        push(view, std::move(choice));
    }

    static std::uint64_t stampRestore(const NativeCosmeticContext& cosmetics) {
        auto hash = kStampBasis;
        hash = mixStamp(hash, cosmetics.available ? 1ull : 0ull);
        hash = mixStamp(hash, cosmetics.scanning ? 1ull : 0ull);
        hash = mixStamp(hash, cosmetics.restorationPending ? 1ull : 0ull);
        return mixStamp(hash, cosmetics.message);
    }

    void pushRestore(CareerLayoutView& view, const NativeCosmeticContext& cosmetics) const {
        CareerLayoutChoice choice;
        choice.id = "cosmetic.restore";
        choice.label = "Restore original";
        choice.kind = CareerLayoutEffectKind::LocalCosmetic;
        choice.target = CareerLayoutPage::Appearance;
        choice.cosmetic.kind = NativeCosmeticRequestKind::Restore;
        choice.cosmetic.restorationPending = cosmetics.restorationPending;
        choice.enabled = cosmetics.available && !cosmetics.scanning;
        if (!choice.enabled) choice.reason = cosmetics.scanning ? kCatalogLoading : kItemModUnavailable;
        choice.cosmeticStamp = stampRestore(cosmetics);
        push(view, std::move(choice));
    }

    static std::uint64_t stampClear(const NativeCosmeticContext& cosmetics, int slot, const NativeCosmeticSelection& selection) {
        auto hash = stampValue(kStampBasis, slot);
        hash = stampValue(hash, selection.productId);
        hash = stampValue(hash, selection.paint);
        const auto* product = findNativeCosmeticProduct(nativeCosmeticCatalog(cosmetics), slot, selection.productId);
        if (product) hash = stampProduct(hash, *product);
        return hash;
    }

    void pushClear(CareerLayoutView& view, const NativeCosmeticContext& cosmetics, CareerLayoutPage where) const {
        if (cosmetics.scanning || cosmetics.restorationPending || !nativeCosmeticSlotEquipable(cosmeticSlot_)) return;
        const auto drafted = cosmetics.draft.find(cosmeticSlot_);
        if (drafted == cosmetics.draft.end()) return;
        CareerLayoutChoice choice;
        choice.id = "cosmetic.clear";
        choice.label = std::string("Clear ") + nativeCosmeticCategoryLabel(cosmeticSlot_);
        choice.enabled = true;
        choice.kind = CareerLayoutEffectKind::LocalCosmetic;
        choice.target = where;
        choice.cosmetic.kind = NativeCosmeticRequestKind::ClearSlot;
        choice.cosmetic.slot = cosmeticSlot_;
        choice.cosmetic.productId = drafted->second.productId;
        choice.cosmetic.paint = drafted->second.paint;
        choice.cosmeticStamp = stampClear(cosmetics, cosmeticSlot_, drafted->second);
        push(view, std::move(choice));
    }

    void pushPage(CareerLayoutView& view, const char* id, const char* label, std::size_t page) const {
        CareerLayoutChoice choice;
        choice.id = id;
        choice.label = label;
        choice.enabled = true;
        choice.kind = CareerLayoutEffectKind::Navigate;
        choice.target = CareerLayoutPage::CosmeticItems;
        choice.page = page;
        choice.cosmetic.slot = cosmeticSlot_;
        choice.cosmeticStamp = mixStamp(stampValue(kStampBasis, cosmeticSlot_), static_cast<std::uint64_t>(page));
        push(view, std::move(choice));
    }

    void pushItemsBack(CareerLayoutView& view) const {
        CareerLayoutChoice choice;
        choice.id = "nav.back";
        choice.label = "Back";
        choice.enabled = true;
        choice.kind = CareerLayoutEffectKind::Navigate;
        choice.target = CareerLayoutPage::CosmeticItems;
        choice.page = cosmeticPage_;
        choice.cosmetic.slot = cosmeticSlot_;
        choice.cosmeticStamp = mixStamp(stampValue(kStampBasis, cosmeticSlot_), static_cast<std::uint64_t>(cosmeticPage_));
        push(view, std::move(choice));
    }

    void buildAppearance(CareerLayoutView& view, const NativeCosmeticContext& cosmetics) const {
        view.title = "Local appearance";
        addLine(view.body, "Local appearance uses this machine's cosmetic override.");
        addLine(view.body, "It does not change Rocket League inventory or show that an item is visible in a match.");
        addLine(view.body, "Bodies, banners, borders, and titles are not equipped here.");
        describeCosmeticStatus(view, cosmetics);
        describeDraft(view, cosmetics);
        describeColors(view, cosmetics);
        for (const auto& category : kNativeCosmeticCategories) {
            CareerLayoutChoice choice;
            choice.id = std::string("cosmetic.slot.") + std::to_string(category.slot);
            choice.label = category.label;
            choice.enabled = true;
            choice.kind = CareerLayoutEffectKind::Navigate;
            choice.target = CareerLayoutPage::CosmeticItems;
            choice.page = 0;
            choice.cosmetic.slot = category.slot;
            choice.cosmeticStamp = stampValue(kStampBasis, category.slot);
            push(view, std::move(choice));
        }
        navigate(view, "cosmetic.colors", "Colors", CareerLayoutPage::CosmeticColors);
        pushApply(view, cosmetics);
        pushRestore(view, cosmetics);
        back(view, CareerLayoutPage::Garage);
    }

    void buildCosmeticItems(CareerLayoutView& view, const NativeCosmeticContext& cosmetics) const {
        view.title = nativeCosmeticCategoryLabel(cosmeticSlot_);
        if (!nativeCosmeticSlotEquipable(cosmeticSlot_)) {
            addLine(view.body, "That category cannot be equipped by the local override.");
            back(view, CareerLayoutPage::Appearance);
            return;
        }
        describeCosmeticStatus(view, cosmetics);
        std::vector<const NativeCosmeticProduct*> listed;
        listSlotProducts(cosmetics, cosmeticSlot_, listed);
        const std::size_t pageCount = listed.empty() ? 1 : (listed.size() + kCosmeticItemsPerPage - 1) / kCosmeticItemsPerPage;
        const std::size_t page = cosmeticPage_ < pageCount ? cosmeticPage_ : pageCount - 1;
        addLine(view.body, "Page " + std::to_string(page + 1) + " of " + std::to_string(pageCount) + ".");
        const auto drafted = cosmetics.draft.find(cosmeticSlot_);
        if (drafted != cosmetics.draft.end()) {
            std::string selected = std::string("Selected: ") + productName(cosmetics, cosmeticSlot_, drafted->second.productId);
            if (drafted->second.paint > 0 && drafted->second.paint <= kNativeCosmeticPaintMax)
                selected += ", " + std::string(nativeCosmeticPaintName(drafted->second.paint));
            addLine(view.body, selected);
        }
        if (!cosmetics.scanning && listed.empty()) addLine(view.body, "No supported items are in this category.");
        if (page > 0) pushPage(view, "cosmetic.previous", "Previous page", page - 1);
        const bool canSelect = !cosmetics.restorationPending;
        const auto first = page * kCosmeticItemsPerPage;
        const auto last = (std::min)(first + kCosmeticItemsPerPage, listed.size());
        for (std::size_t index = first; index < last; ++index) {
            const auto* product = listed[index];
            CareerLayoutChoice choice;
            choice.id = "cosmetic.item." + std::to_string(page) + "." + std::to_string(index - first);
            choice.label = drafted != cosmetics.draft.end() && drafted->second.productId == product->id
                ? "Design: " + product->name : product->name;
            choice.enabled = canSelect;
            choice.reason = canSelect ? "" : "Restore the original cosmetic settings before choosing another item.";
            choice.kind = CareerLayoutEffectKind::LocalCosmetic;
            choice.target = CareerLayoutPage::CosmeticItems;
            choice.cosmetic.kind = NativeCosmeticRequestKind::SelectItem;
            choice.cosmetic.slot = product->slot;
            choice.cosmetic.productId = product->id;
            choice.cosmetic.paint = 0;
            choice.cosmetic.paintable = product->paintable;
            choice.cosmeticStamp = stampProduct(mixStamp(kStampBasis, static_cast<std::uint64_t>(index)), *product);
            push(view, std::move(choice));
        }
        if (page + 1 < pageCount) pushPage(view, "cosmetic.next", "Next page", page + 1);
        pushClear(view, cosmetics, CareerLayoutPage::CosmeticItems);
        back(view, CareerLayoutPage::Appearance);
    }

    void buildCosmeticPaints(CareerLayoutView& view, const NativeCosmeticContext& cosmetics) const {
        view.title = "Paint";
        const auto* product = cosmetics.scanning ? nullptr
            : findNativeCosmeticProduct(nativeCosmeticCatalog(cosmetics), cosmeticSlot_, cosmeticProductId_);
        if (!product) {
            addLine(view.body, cosmetics.scanning ? kCatalogLoading : "This item is no longer in the local catalog.");
            describeCosmeticStatus(view, cosmetics);
            pushClear(view, cosmetics, CareerLayoutPage::CosmeticPaints);
            pushItemsBack(view);
            return;
        }
        addLine(view.body, product->name);
        addLine(view.body, "Choosing a paint does not show that this item is visible in a match.");
        describeCosmeticStatus(view, cosmetics);
        const auto drafted = cosmetics.draft.find(cosmeticSlot_);
        const bool draftMatches = drafted != cosmetics.draft.end() && drafted->second.productId == product->id &&
            drafted->second.paint >= 0 && drafted->second.paint <= kNativeCosmeticPaintMax;
        if (!product->paintable) addLine(view.body, "This item does not support paint.");
        else if (cosmetics.restorationPending)
            addLine(view.body, "Restore the original cosmetic settings before choosing a paint.");
        else if (!draftMatches) addLine(view.body, "Choose this item before choosing a paint.");
        else {
            const int currentPaint = drafted->second.paint;
            addLine(view.body, std::string("Current paint: ") + nativeCosmeticPaintName(currentPaint));
            for (int paint = 0; paint < kNativeCosmeticPaintCount; ++paint) {
                CareerLayoutChoice choice;
                choice.id = "cosmetic.paint." + std::to_string(paint);
                choice.label = std::string(paint == currentPaint ? "Selected: " : "") + nativeCosmeticPaintName(paint);
                choice.enabled = true;
                choice.kind = CareerLayoutEffectKind::LocalCosmetic;
                choice.target = CareerLayoutPage::CosmeticPaints;
                choice.cosmetic.kind = NativeCosmeticRequestKind::SelectPaint;
                choice.cosmetic.slot = product->slot;
                choice.cosmetic.productId = product->id;
                choice.cosmetic.paint = paint;
                choice.cosmetic.paintable = true;
                choice.cosmeticStamp = stampValue(stampProduct(stampValue(kStampBasis, paint), *product), currentPaint);
                push(view, std::move(choice));
            }
        }
        pushClear(view, cosmetics, CareerLayoutPage::CosmeticPaints);
        pushItemsBack(view);
    }

    static std::uint64_t stampColorState(std::uint64_t hash, const NativeCosmeticContext& cosmetics) {
        hash = mixStamp(hash, cosmetics.overrideColors ? 1ull : 0ull);
        hash = mixStamp(hash, cosmetics.scanning ? 1ull : 0ull);
        hash = mixStamp(hash, cosmetics.restorationPending ? 1ull : 0ull);
        hash = mixStamp(hash, nativeCosmeticColorsValid(cosmetics) ? 1ull : 0ull);
        if (!nativeCosmeticColorsValid(cosmetics)) return hash;
        hash = stampRgb(hash, cosmetics.primary);
        return stampRgb(hash, cosmetics.secondary);
    }

    void buildCosmeticColors(CareerLayoutView& view, const NativeCosmeticContext& cosmetics) const {
        view.title = "Colors";
        addLine(view.body, "Choosing a color does not apply it.");
        describeCosmeticStatus(view, cosmetics);
        describeColors(view, cosmetics);
        const char* blocked = colorEditBlock(cosmetics);
        CareerLayoutChoice toggle;
        toggle.id = "cosmetic.colors.override";
        toggle.label = cosmetics.overrideColors ? "Turn off color override" : "Turn on color override";
        toggle.enabled = blocked == nullptr;
        if (blocked) toggle.reason = blocked;
        toggle.kind = CareerLayoutEffectKind::LocalCosmetic;
        toggle.target = CareerLayoutPage::CosmeticColors;
        toggle.cosmetic.kind = NativeCosmeticRequestKind::SetColorOverride;
        toggle.cosmetic.overrideColors = !cosmetics.overrideColors;
        toggle.cosmeticStamp = stampColorState(mixStamp(kStampBasis, toggle.cosmetic.overrideColors ? 1ull : 0ull), cosmetics);
        push(view, std::move(toggle));
        navigate(view, "cosmetic.colors.primary", "Primary color", CareerLayoutPage::CosmeticPrimary);
        navigate(view, "cosmetic.colors.accent", "Accent color", CareerLayoutPage::CosmeticAccent);
        back(view, CareerLayoutPage::Appearance);
    }

    void buildCosmeticChannel(CareerLayoutView& view, const NativeCosmeticContext& cosmetics, bool primary) const {
        view.title = primary ? "Primary color" : "Accent color";
        addLine(view.body, "Choosing a color does not apply it.");
        describeCosmeticStatus(view, cosmetics);
        const bool colorsOk = nativeCosmeticColorsValid(cosmetics);
        const auto& current = primary ? cosmetics.primary : cosmetics.secondary;
        const int selected = colorsOk ? nativeCosmeticPaletteIndex(current) : -1;
        if (colorsOk)
            addLine(view.body, std::string(primary ? "Current primary: " : "Current accent: ") + nativeCosmeticColorName(current));
        else addLine(view.body, kColorsUnusable);
        const char* blocked = colorEditBlock(cosmetics);
        for (int index = 0; index < kNativeCosmeticPaletteCount; ++index) {
            CareerLayoutChoice choice;
            choice.id = std::string(primary ? "cosmetic.primary." : "cosmetic.accent.") + std::to_string(index);
            const char* name = kNativeCosmeticPalette[index].name;
            choice.label = index == selected ? std::string("Selected: ") + name : name;
            choice.enabled = blocked == nullptr;
            if (blocked) choice.reason = blocked;
            choice.kind = CareerLayoutEffectKind::LocalCosmetic;
            choice.target = primary ? CareerLayoutPage::CosmeticPrimary : CareerLayoutPage::CosmeticAccent;
            choice.cosmetic.kind = primary ? NativeCosmeticRequestKind::SelectPrimaryColor
                                           : NativeCosmeticRequestKind::SelectSecondaryColor;
            choice.cosmetic.paletteIndex = index;
            choice.cosmeticStamp = stampColorState(stampValue(kStampBasis, index + (primary ? 0 : 32)), cosmetics);
            push(view, std::move(choice));
        }
        back(view, CareerLayoutPage::CosmeticColors);
    }
};

} // namespace mct
