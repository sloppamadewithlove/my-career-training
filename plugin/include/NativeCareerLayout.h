#pragma once

#include "LocalBridge.h"

#include <algorithm>
#include <cstdint>
#include <limits>
#include <string>
#include <vector>

namespace mct {

// Presentation and routing plan for a future engine binding adapter.
// This class does not draw, write memory, send bridge commands, or launch the game.
// It is not a finished native menu replacement and it does not enable a production gate.
// A consumed-original acknowledgement is only a precondition for a custom dispatch.
// Route suppression is a binding plan; this model does not claim clicks are blocked.

enum class CareerLayoutPage {
    Root, Career, Training, Lesson, Schedule, Standings, Squad, Garage, Workshop, Community, Settings
};

enum class CareerLayoutEffectKind {
    None, Navigate, PreserveStockRoute, Dispatch, Unavailable
};

enum class CareerLayoutRefusal {
    None, NoPlan, StaleScope, StaleChoice, NotConsumed, Disabled, UnknownControl
};

enum class StockRoute { None, Garage, Options };

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
    static constexpr std::size_t kMaxBody = 2000;
    static constexpr std::size_t kMaxLabel = 80;
    static constexpr std::size_t kMaxReason = 240;
    static constexpr std::size_t kLessonsPerPage = 4;
    static constexpr std::size_t kMaxLessons = 96;
    static constexpr std::size_t kMaxRows = 8;
    static constexpr std::size_t kMaxSquad = 4;
    static constexpr std::size_t kScanCap = 64;
    static constexpr const char* kCareer = "career.open";
    static constexpr const char* kTraining = "training.open";
    static constexpr const char* kGarage = "garage.open";
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

    // Actions this layout may put on an effect. A subset of the bridge allowlist.
    // play_workshop and any activation command are intentionally absent.
    static bool supportedAction(const std::string& action) {
        return action == "play_match" || action == "select_lesson" || action == "start_lesson" ||
            action == "assistance" || action == "lesson_variant" || action == "restore_explanations" ||
            action == "loadout" || action == "refresh_workshop" || action == "workshop_favorite" ||
            action == "community_lookup" || action == "community_download" || action == "community_library" ||
            action == "community_cancel" || action == "training_settings" || action == "quit_game";
    }

    bool open(const CareerLayoutScope& scope, const Json& state) {
        page_ = CareerLayoutPage::Root;
        lessonPage_ = 0;
        lessonId_.clear();
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
    [[nodiscard]] CareerLayoutView view(const CareerLayoutScope& current, const Json& state) const {
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
        case CareerLayoutPage::Training: buildTraining(out, state); break;
        case CareerLayoutPage::Lesson: buildLesson(out, state); break;
        case CareerLayoutPage::Schedule: buildSchedule(out, state); break;
        case CareerLayoutPage::Standings: buildStandings(out, state); break;
        case CareerLayoutPage::Squad: buildSquad(out, state); break;
        case CareerLayoutPage::Garage: buildGarage(out, state); break;
        case CareerLayoutPage::Workshop: buildWorkshop(out, state); break;
        case CareerLayoutPage::Community: buildCommunity(out, state); break;
        case CareerLayoutPage::Settings: buildSettings(out, state); break;
        }
        if (out.body.size() > kMaxBody) out.body.resize(kMaxBody);
        for (auto& choice : out.choices) choice.revision = revision_;
        return out;
    }

    // originalConsumed must already be true before a Dispatch effect is returned.
    // Navigate and PreserveStockRoute never carry a bridge action.
    // A refusal does not ask the adapter to swallow unrelated native callbacks.
    [[nodiscard]] CareerLayoutEffect choose(const CareerLayoutChoice& shown, const CareerLayoutScope& click,
                                            const Json& latestState, bool originalConsumed) {
        CareerLayoutEffect effect;
        if (!opened_ || !scopeOk(openedScope_)) return refuse(effect, CareerLayoutRefusal::NoPlan, kNoPlan);
        if (!sameScope(click, openedScope_) || !stateMatches(latestState, openedScope_))
            return refuse(effect, CareerLayoutRefusal::StaleScope, kStaleScope);
        if (!revisionUsable()) return refuse(effect, CareerLayoutRefusal::StaleChoice, kStaleChoice);
        const auto current = view(click, latestState);
        const CareerLayoutChoice* match = nullptr;
        for (const auto& choice : current.choices)
            if (choice.id == shown.id) { match = &choice; break; }
        if (!match) {
            if (shown.revision != 0 && shown.revision != revision_)
                return refuse(effect, CareerLayoutRefusal::StaleChoice, kStaleChoice);
            const bool wasSpecific = !shown.lessonId.empty() || !shown.fixtureId.empty() ||
                shown.kind == CareerLayoutEffectKind::Dispatch || shown.kind == CareerLayoutEffectKind::Unavailable;
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
        return refuse(effect, CareerLayoutRefusal::UnknownControl, kUnknown);
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
            return page_;
        }
        if (choice->action == "select_lesson") {
            lessonId_ = choice->lessonId;
            page_ = CareerLayoutPage::Lesson;
        }
        return page_;
    }

    // Live ownership, offline, freshness, online, nonce, and generation come from
    // current. state.offline is the backend in-game flag, not that live status.
    bool planActive(const CareerLayoutScope& current, const Json& state) const {
        return opened_ && revisionUsable() && sameScope(current, openedScope_) &&
            stateMatches(state, openedScope_);
    }

    static bool scopeOk(const CareerLayoutScope& scope) {
        return scope.owned && scope.offline && scope.fresh && !scope.online &&
            scope.generation != 0 && validNonce(scope.nonce);
    }

    static bool sameScope(const CareerLayoutScope& click, const CareerLayoutScope& opened) {
        return scopeOk(click) && click.owned == opened.owned && click.offline == opened.offline &&
            click.fresh == opened.fresh && click.online == opened.online &&
            click.generation == opened.generation && click.nonce == opened.nonce;
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

    static std::string plain(const std::string& value, std::size_t limit) {
        if (limit == 0) return {};
        std::size_t count = (std::min)(limit, value.size());
        while (count > 0 && count < value.size() && (static_cast<unsigned char>(value[count]) & 0xc0) == 0x80) --count;
        std::string out;
        out.reserve((std::min)(count + 3, limit));
        for (std::size_t i = 0; i < count && out.size() < limit; ++i) {
            const auto c = static_cast<unsigned char>(value[i]);
            out.push_back(c < 32 || c == 127 || c == '<' || c == '>' || c == '&' ? ' ' : static_cast<char>(c));
        }
        if (count < value.size()) {
            const std::string mark = "...";
            if (out.size() + mark.size() > limit) out.resize(limit - mark.size());
            out += mark;
        }
        if (out.size() > limit) out.resize(limit);
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
        if (body.size() + text.size() > kMaxBody) text.resize(kMaxBody - body.size());
        body += text;
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
        addLine(view.body, "Offline career, training, workshop, and community.");
        addLine(view.body, "Your garage and game options stay the game's own screens.");
        navigate(view, kCareer, "My Career", CareerLayoutPage::Career);
        navigate(view, kTraining, "Training", CareerLayoutPage::Training);
        navigate(view, kGarage, "Garage", CareerLayoutPage::Garage);
        navigate(view, kWorkshop, "Workshop", CareerLayoutPage::Workshop);
        navigate(view, kCommunity, "Community", CareerLayoutPage::Community);
        navigate(view, kSettings, "Settings", CareerLayoutPage::Settings);
        const bool canExit = !busy(state);
        dispatch(view, kExit, "Exit", canExit, kWait, "quit_game", Json::object());
    }

    void buildCareer(CareerLayoutView& view, const Json& state) const {
        view.title = "My Career";
        const auto career = careerOf(state);
        const auto fixture = object(state, "next_fixture");
        if (career.empty()) addLine(view.body, "No career exists yet.");
        else addLine(view.body, plain(text(career, "team_name", "My club"), 48));
        CareerLayoutChoice play;
        play.id = "career.play";
        play.label = "Play Next Match";
        play.kind = CareerLayoutEffectKind::Dispatch;
        play.action = "play_match";
        if (career.empty()) play.reason = "Create a career before playing a match.";
        else if (fixture.empty()) play.reason = "No next match is on the schedule.";
        else if (!validId(text(career, "id")) || !validId(text(fixture, "id"))) play.reason = "That match is not ready.";
        else if (text(fixture, "home") != "human" && text(fixture, "away") != "human")
            play.reason = "That match does not include your club.";
        else if (text(fixture, "status") != "scheduled") play.reason = "That match is already finished.";
        else if (flag(state, "setup_required", true)) play.reason = "Finish setup before playing a match.";
        else if (!ready(state)) play.reason = kRecover;
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
        back(view, CareerLayoutPage::Root);
    }

    void buildTraining(CareerLayoutView& view, const Json& state) const {
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
                choice.id = "training.lesson." + id;
                choice.label = plain(text(lessons[i], "title", "Lesson"), 64);
                choice.enabled = canSelect;
                choice.reason = canSelect ? "" : kWait;
                choice.kind = CareerLayoutEffectKind::Dispatch;
                choice.action = "select_lesson";
                choice.lessonId = id;
                choice.payload = {{"id", id}};
                push(view, std::move(choice));
            }
            if (pages > 1) navigate(view, "training.next", "Next page", CareerLayoutPage::Training, (page + 1) % pages);
        }
        back(view, CareerLayoutPage::Root);
    }

    void buildLesson(CareerLayoutView& view, const Json& state) const {
        view.title = "Training";
        const auto lessons = lessonsOf(state);
        const auto lesson = findLesson(lessons, lessonId_);
        const auto page = shownLessonPage(lessons.size());
        if (lesson.empty()) addLine(view.body, "This lesson is no longer available.");
        else {
            addLine(view.body, plain(text(lesson, "title", "Lesson"), 80));
            addLine(view.body, plain(text(lesson, "description"), 180));
            const auto steps = array(lesson, "steps");
            const auto stop = (std::min)(steps.size(), static_cast<std::size_t>(6));
            for (std::size_t i = 0; i < stop; ++i)
                if (steps[i].is_string()) addLine(view.body, std::to_string(i + 1) + ". " + plain(steps[i].get<std::string>(), 120));
            const bool canPractice = ready(state);
            CareerLayoutChoice start;
            start.id = "training.practice";
            start.label = "Start practice";
            start.kind = CareerLayoutEffectKind::Dispatch;
            start.action = "start_lesson";
            start.lessonId = lessonId_;
            start.enabled = canPractice;
            start.reason = canPractice ? "" : "Practice is unavailable until the session is ready and any unfinished match is resolved.";
            start.payload = {{"id", lessonId_}};
            push(view, std::move(start));
            const char* helpKeys[] = {"ghost", "explanations", "actions", "timing", "auto_reset"};
            const char* helpLabels[] = {"Ghost demonstration", "Step-by-step explanations", "Action input display",
                "Timing feedback", "Automatic reset"};
            const bool helpDefaults[] = {true, true, true, true, false};
            const bool canEdit = !busy(state);
            for (std::size_t i = 0; i < 5; ++i) {
                const bool current = assist(state, lessonId_, helpKeys[i], helpDefaults[i]);
                dispatch(view, std::string("training.help.") + helpKeys[i],
                    std::string(current ? "Turn off " : "Turn on ") + helpLabels[i], canEdit, kWait,
                    "assistance", {{"id", lessonId_}, {"key", helpKeys[i]}, {"value", !current}});
            }
            struct Speed { const char* id; const char* label; double value; };
            const Speed speeds[] = {{"quarter", "Practice speed: quarter", 0.25}, {"half", "Practice speed: half", 0.5},
                {"three-quarter", "Practice speed: three quarters", 0.75}, {"normal", "Practice speed: normal", 1.0}};
            for (const auto& speed : speeds)
                dispatch(view, std::string("training.speed.") + speed.id, speed.label, canEdit, kWait, "assistance",
                    {{"id", lessonId_}, {"key", "playback_speed"}, {"value", speed.value}});
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
        back(view, CareerLayoutPage::Career);
    }

    void buildStandings(CareerLayoutView& view, const Json& state) const {
        view.title = "Season";
        const auto career = careerOf(state);
        if (career.empty()) addLine(view.body, "No career exists yet.");
        else {
            const auto season = currentSeason(career);
            std::string heading = "League table.";
            if (!season.empty() && career.contains("current_season") && career["current_season"].is_number_integer()) {
                const auto index = career["current_season"];
                std::uint64_t number = index.is_number_unsigned() ? index.get<std::uint64_t>() : static_cast<std::uint64_t>(index.get<std::int64_t>());
                if (number < 1000) heading = "Season " + std::to_string(number + 1) + " league table.";
            }
            addLine(view.body, heading);
        }
        const auto rows = array(state, "standings");
        const auto stop = (std::min)(rows.size(), kMaxRows);
        if (!stop) addLine(view.body, "No standings are published yet.");
        for (std::size_t i = 0; i < stop; ++i) {
            int points = 0;
            std::string line = std::to_string(i + 1) + ". " + plain(text(rows[i], "name", "Club"), 48);
            if (whole(rows[i], "points", points, 0, 1000000)) line += " - " + std::to_string(points) + " points";
            addLine(view.body, line);
        }
        back(view, CareerLayoutPage::Career);
    }

    void buildSquad(CareerLayoutView& view, const Json& state) const {
        view.title = "Squad";
        const auto career = careerOf(state);
        if (career.empty()) addLine(view.body, "No career exists yet.");
        else addLine(view.body, plain(text(career, "team_name", "My club"), 48));
        const auto squad = array(career, "squad");
        const auto lineup = array(career, "lineup");
        const auto recruits = object(career, "recruits");
        std::size_t shown = 0;
        const auto stop = (std::min)(squad.size(), kScanCap);
        for (std::size_t i = 0; i < stop && shown < kMaxSquad; ++i) {
            if (!squad[i].is_string()) continue;
            const auto id = squad[i].get<std::string>();
            if (!validId(id)) continue;
            const auto recruit = objectKey(recruits, id);
            if (recruit.empty()) continue;
            bool starter = false;
            const auto lineupStop = (std::min)(lineup.size(), kScanCap);
            for (std::size_t n = 0; n < lineupStop; ++n)
                if (lineup[n].is_string() && lineup[n].get<std::string>() == id) starter = true;
            addLine(view.body, plain(text(recruit, "name", "Bot"), 48) + " - " + plain(text(recruit, "role", "bot"), 32) +
                (starter ? " - starter" : " - bench"));
            ++shown;
        }
        if (career.empty() || !shown) addLine(view.body, "No squad is published yet.");
        else addLine(view.body, "Lineup changes stay in the current squad controls.");
        back(view, CareerLayoutPage::Career);
    }

    void buildGarage(CareerLayoutView& view, const Json& state) const {
        view.title = "Garage";
        addLine(view.body, "Your car stays in the game's garage.");
        addLine(view.body, "Bot presets below are local career appearances. They do not add items to your garage.");
        CareerLayoutChoice stock;
        stock.id = "garage.player";
        stock.label = "Your car";
        stock.enabled = true;
        stock.kind = CareerLayoutEffectKind::PreserveStockRoute;
        stock.stock = StockRoute::Garage;
        push(view, std::move(stock));
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

    void buildWorkshop(CareerLayoutView& view, const Json& state) const {
        view.title = "Workshop";
        const auto workshop = object(state, "workshop");
        const auto note = text(workshop, "note");
        const char* published =
            "Browse installed maps and save favorites. Custom map launch is paused while a loader "
            "that preserves your Steam game is being developed.";
        addLine(view.body, note == published ? published : "Browse installed maps and save favorites.");
        const bool canEdit = !busy(state);
        dispatch(view, "workshop.refresh", "Refresh library", canEdit, kWait, "refresh_workshop", Json::object());
        const auto items = array(workshop, "items");
        std::size_t shown = 0;
        const auto stop = (std::min)(items.size(), kScanCap);
        for (std::size_t i = 0; i < stop && shown < kMaxRows; ++i) {
            const auto& item = items[i];
            const auto id = text(item, "id");
            if (!safeId(id)) continue;
            const auto title = plain(text(item, "title", "Map"), 48);
            const bool favorite = flag(item, "favorite", false);
            dispatch(view, "workshop.favorite." + id, (favorite ? "Remove " : "Save ") + title + (favorite ? " from favorites" : " to favorites"),
                canEdit, kWait, "workshop_favorite", {{"id", id}});
            CareerLayoutChoice play;
            play.id = "workshop.play." + id;
            play.label = "Play " + title;
            play.enabled = false;
            play.kind = CareerLayoutEffectKind::Unavailable;
            play.reason = mapReason(item);
            play.itemId = id;
            push(view, std::move(play));
            ++shown;
        }
        if (!shown) addLine(view.body, "No workshop maps are in the library yet.");
        back(view, CareerLayoutPage::Root);
    }

    void buildCommunity(CareerLayoutView& view, const Json& state) const {
        view.title = "Community";
        addLine(view.body, "Core lessons work without community downloads.");
        const auto plugins = object(state, "community_plugins");
        const auto message = text(plugins, "message");
        if (!message.empty()) addLine(view.body, message);
        const bool waiting = flag(plugins, "busy", false) || busy(state);
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
        dispatch(view, "settings.mode.lead", "Show the ghost ahead", canEdit, kWait, "training_settings",
            {{"key", "mode"}, {"value", "lead"}});
        dispatch(view, "settings.mode.watch", "Watch the ghost", canEdit, kWait, "training_settings",
            {{"key", "mode"}, {"value", "watch"}});
        dispatch(view, "settings.loop.on", "Repeat the ghost", canEdit, kWait, "training_settings",
            {{"key", "loop"}, {"value", true}});
        dispatch(view, "settings.loop.off", "Play the ghost once", canEdit, kWait, "training_settings",
            {{"key", "loop"}, {"value", false}});
        struct ViewChoice { const char* id; const char* label; const char* value; };
        const ViewChoice views[] = {{"player", "Ghost view: from your car", "player"}, {"chase", "Ghost view: chase", "chase"},
            {"side", "Ghost view: side", "side"}, {"top", "Ghost view: above", "top"}};
        for (const auto& item : views)
            dispatch(view, std::string("settings.view.") + item.id, item.label, canEdit, kWait, "training_settings",
                {{"key", "ghost_view"}, {"value", item.value}});
        back(view, CareerLayoutPage::Root);
    }
};

} // namespace mct
