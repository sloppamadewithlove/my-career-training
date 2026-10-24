#include "NativeCareerLayout.h"

#include <iostream>
#include <stdexcept>
#include <string>

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

static void audit(const CareerLayoutView& view) {
    require(view.body.size() <= NativeCareerLayout::kMaxBody, "Body exceeds the bound");
    require(view.choices.size() <= NativeCareerLayout::kMaxChoices, "Too many controls");
    require(!view.productionGateEnabled && !view.nativeReplacementFinished, "Production or replacement flag set");
    require(!view.suppressionEnforced && !view.compatibilityGrant, "Suppression or compatibility claimed");
    require(view.offersReplacement ? view.suppress.size() == 6 : view.suppress.empty(), "Suppression list size");
    for (const auto& choice : view.choices) {
        require(choice.action != "play_workshop" && choice.action != "community_activate", "Unsupported action shown");
        require(choice.action != "open_link" && choice.action != "import_map" && choice.action != "settings", "Out of menu action");
        if (!choice.enabled || choice.kind != CareerLayoutEffectKind::Dispatch)
            require(choice.action.empty() && choice.payload.empty(), "Disabled or non-dispatch control carries an action");
        if (!choice.action.empty()) require(NativeCareerLayout::supportedAction(choice.action), "Action is not supported");
        if (choice.kind == CareerLayoutEffectKind::PreserveStockRoute) {
            require(choice.enabled && choice.action.empty() && choice.payload.empty(), "Stock route is paired with a dispatch");
            require(choice.stock == StockRoute::Garage || choice.stock == StockRoute::Options, "Stock route is not typed");
        }
    }
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
        {"career", {{"id", "career-a"}, {"team_name", "Orbit"}, {"current_season", 0}, {"pending_session", nullptr},
            {"squad", {"anchor", "shield", "relay", "comet"}}, {"lineup", {"anchor", "shield"}},
            {"recruits", {{"anchor", {{"name", "Anchor"}, {"role", "keeper"}}},
                {"shield", {{"name", "Shield"}, {"role", "defender"}}},
                {"relay", {{"name", "Relay"}, {"role", "passer"}}},
                {"comet", {{"name", "Comet"}, {"role", "attacker"}}}}},
            {"seasons", {{{"clubs", {{{"id", "human"}, {"name", "Orbit"}}, {{"id", "rival"}, {"name", "Nova"}}}},
                {"fixtures", {{{"id", "fixture-a"}, {"home", "human"}, {"away", "rival"}, {"round", 1}, {"status", "scheduled"}}}}}}}}},
        {"next_fixture", {{"id", "fixture-a"}, {"home", "human"}, {"away", "rival"}, {"round", 1}, {"status", "scheduled"}}},
        {"standings", {{{"name", "Orbit"}, {"points", 9}}}},
        {"lessons", {{{"id", "speed-flip"}, {"title", "Speed flip"}, {"description", "A timed kickoff lesson."},
                {"steps", {"Drive", "Jump"}}},
            {{"id", "flip-reset"}, {"title", "Flip reset"}, {"description", "Meet the ball."}},
            {{"id", "power-shots"}, {"title", "Power shots"}, {"description", "Place a shot."},
                {"targets", {{{"type", "goal"}}}}}}},
        {"garage", {{{"id", "stock-23"}, {"title", "Octane"}, {"car_id", 23}, {"primary_color", 27},
                {"secondary_color", 0}, {"wheels_id", 376}},
            {{"id", "stock-999"}, {"title", "Unlisted"}, {"car_id", 999}, {"primary_color", 1}, {"secondary_color", 1}}}},
        {"workshop", {{"items", {{{"id", "dribble-2-overhaul"}, {"title", "Dribble 2 Overhaul"}, {"favorite", false},
                {"installed", true}, {"can_launch", true}, {"launch_reason", "launch it anyway"}}}}}},
        {"community_plugins", {{"catalog", {{{"id", "223"}, {"title", "Workshop Map Loader & Downloader"}}}},
            {"selected", {{"id", "223"}, {"title", "Workshop Map Loader & Downloader"}, {"can_activate", false}}},
            {"downloaded", Json::array()}, {"busy", false}, {"can_activate", false},
            {"message", "Current release found. Downloading does not enable it."}}},
        {"content", {{{"title", "Aim training"}, {"creator", "CoCo"}, {"url", "https://example.invalid/map"}}}}};
}

static CareerLayoutEffect choose(NativeCareerLayout& layout, const CareerLayoutChoice& choice,
                                 const CareerLayoutScope& scope, const Json& state, bool consumed,
                                 const NativeWorkshopContext& workshop = {}) {
    auto effect = layout.choose(choice, scope, state, consumed, {}, workshop);
    require(!effect.compatibilityGrant && !effect.consumesUnlistedCallback, "Effect claims a grant or a global swallow");
    require(effect.action.empty() || NativeCareerLayout::supportedAction(effect.action), "Effect action is not supported");
    if (effect.kind == CareerLayoutEffectKind::PreserveStockRoute)
        require(effect.action.empty() && effect.payload.empty(), "Stock effect also dispatches");
    if (effect.kind != CareerLayoutEffectKind::LocalCosmetic)
        require(effect.cosmetic.kind == NativeCosmeticRequestKind::None && effect.cosmetic.draftCount == 0,
            "Non-cosmetic effect carried a local cosmetic request");
    if (effect.kind != CareerLayoutEffectKind::LocalWorkshop)
        require(effect.workshop.rowId.empty() && effect.workshop.packagePath.empty(),
            "Non-workshop effect carried a map");
    if (!effect.accepted) {
        require(effect.action.empty() && !effect.leaveMenu, "Refused effect still dispatches");
        require(effect.cosmetic.kind == NativeCosmeticRequestKind::None && effect.cosmetic.draftCount == 0,
            "Refused effect kept a cosmetic request");
        require(effect.workshop.packagePath.empty(), "Refused effect kept a map path");
    }
    return effect;
}

int main() {
    try {
        require(!NativeCareerLayout::kProductionGateEnabled && !NativeCareerLayout::kNativeReplacementFinished, "Gate constants");
        require(!NativeCareerLayout::kSuppressionEnforced && !NativeCareerLayout::kCompatibilityGrant, "Proof constants");
        require(!NativeCareerLayout::kWritesMemory && !NativeCareerLayout::kTerminatesProcess, "Side-effect constants");
        require(NativeCareerLayout::supportedAction("quit_game") && NativeCareerLayout::supportedAction("loadout"), "Supported actions");
        require(!NativeCareerLayout::supportedAction("play_workshop") && !NativeCareerLayout::supportedAction("community_activate"),
            "Missing capabilities were marked supported");
        require(!NativeCareerLayout::supportedAction("open_link") && !NativeCareerLayout::supportedAction("import_map"),
            "Non-bridge actions were marked supported");
        require(!NativeCareerLayout::supportedAction("settings") && !NativeCareerLayout::supportedAction("navigate"),
            "Stock or local navigation was marked as a bridge action");
        require(!NativeCareerLayout::supportedAction("apply_cosmetics") && !NativeCareerLayout::supportedAction("restore_cosmetics"),
            "Local cosmetic requests were marked as bridge actions");
        require(!NativeCareerLayout::supportedAction("") && !NativeCareerLayout::supportedAction("PLAY_MATCH"), "Unknown action accepted");

        const auto scope = ownedScope();
        auto state = readyState();
        NativeCareerLayout offline;
        require(!offline.open(CareerLayoutScope{}, state), "Default scope opened a plan");
        require(!offline.view(scope, state).offersReplacement && offline.view(scope, state).choices.empty(), "Default scope shows a menu");
        require(offline.view(scope, state).suppress.empty(), "Default scope suppresses routes");
        CareerLayoutChoice forged;
        forged.id = "career.play";
        forged.kind = CareerLayoutEffectKind::Dispatch;
        forged.action = "play_match";
        forged.enabled = true;
        forged.payload = {{"expected_career_id", "career-a"}, {"expected_fixture_id", "fixture-a"}};
        auto refused = choose(offline, forged, scope, state, true);
        require(!refused.accepted && refused.action.empty() && refused.refusal == CareerLayoutRefusal::NoPlan, "Unopened click dispatched");

        using ScopeMutator = void (*)(CareerLayoutScope&);
        const ScopeMutator mutators[] = {
            [](CareerLayoutScope& value) { value.online = true; },
            [](CareerLayoutScope& value) { value.owned = false; },
            [](CareerLayoutScope& value) { value.offline = false; },
            [](CareerLayoutScope& value) { value.fresh = false; },
            [](CareerLayoutScope& value) { value.generation = 0; },
            [](CareerLayoutScope& value) { value.nonce.clear(); },
            [](CareerLayoutScope& value) { value.nonce = "../bridge/session"; },
        };
        for (const auto mutated : mutators) {
            auto blockedScope = scope;
            mutated(blockedScope);
            NativeCareerLayout blocked;
            require(!blocked.open(blockedScope, state), "Invalid scope opened a plan");
            require(!blocked.view(blockedScope, state).offersReplacement && blocked.route(NativeRouteId::OnlineMatchmaking, blockedScope, state).plan == NativeRoutePlan::Passthrough,
                "Invalid scope still suppresses matchmaking");
            auto effect = choose(blocked, forged, blockedScope, state, true);
            require(!effect.accepted && effect.action.empty() && effect.refusal == CareerLayoutRefusal::NoPlan, "Invalid scope dispatched");
        }
        auto badState = state;
        badState["offline"] = false;
        require(!offline.open(scope, badState), "Online state opened a plan");
        badState = state;
        badState["protocol"] = 2;
        require(!offline.open(scope, badState), "Wrong protocol opened a plan");
        badState = state;
        badState["bridge_session"] = "fedcba9876543210fedcba9876543210";
        require(!offline.open(scope, badState), "Mismatched nonce opened a plan");

        NativeCareerLayout layout;
        require(layout.open(scope, state), "Owned offline scope did not open");
        auto root = layout.view(scope, state);
        audit(root);
        require(root.offersReplacement && root.page == CareerLayoutPage::Root, "Root plan missing");
        require(root.choices.size() == 7, "Top menu must have seven controls");
        const char* ids[] = {NativeCareerLayout::kCareer, NativeCareerLayout::kTraining, NativeCareerLayout::kGarage,
            NativeCareerLayout::kWorkshop, NativeCareerLayout::kCommunity, NativeCareerLayout::kSettings, NativeCareerLayout::kExit};
        const char* labels[] = {"My Career", "Training", "Garage", "Workshop", "Community", "Settings", "Exit"};
        for (std::size_t i = 0; i < 7; ++i) {
            require(root.choices[i].id == ids[i] && root.choices[i].label == labels[i], "Top menu order");
        }
        require(root.suppress.size() == 6, "Suppression plan missing");
        require(root.suppress[0] == NativeRouteId::OnlineMatchmaking && root.suppress[1] == NativeRouteId::TournamentJoin, "Suppress order");
        require(root.suppress[2] == NativeRouteId::Store && root.suppress[3] == NativeRouteId::RocketPass, "Store and pass");
        require(root.suppress[4] == NativeRouteId::Account && root.suppress[5] == NativeRouteId::Party, "Account and party");
        for (const auto route : root.suppress)
            require(route != NativeRouteId::AccountCloudSync && route != NativeRouteId::Garage && route != NativeRouteId::Options,
                "Preserved route was suppressed");
        for (const auto route : {NativeRouteId::OnlineMatchmaking, NativeRouteId::TournamentJoin, NativeRouteId::Store,
                 NativeRouteId::RocketPass, NativeRouteId::Account, NativeRouteId::Party}) {
            auto decision = layout.route(route, scope, state);
            require(decision.plan == NativeRoutePlan::Suppress && decision.suppressionRequired, "Listed route was not a suppression plan");
            require(!decision.enforcementVerified && !decision.consumesUnlisted, "Suppression claimed as enforced");
        }
        auto cloud = layout.route(NativeRouteId::AccountCloudSync, scope, state);
        require(cloud.plan == NativeRoutePlan::Passthrough && !cloud.suppressionRequired && !cloud.consumesUnlisted, "Cloud sync was suppressed");
        require(layout.route(NativeRouteId::Garage, scope, state).plan == NativeRoutePlan::PreserveStock, "Garage route was not preserved");
        require(layout.route(NativeRouteId::Options, scope, state).plan == NativeRoutePlan::PreserveStock, "Options route was not preserved");
        auto unlisted = layout.route(NativeRouteId::Unlisted, scope, state);
        require(unlisted.plan == NativeRoutePlan::Passthrough && !unlisted.suppressionRequired && !unlisted.consumesUnlisted, "Unlisted route was swallowed");
        auto unknownRoute = layout.route(static_cast<NativeRouteId>(400), scope, state);
        require(unknownRoute.route == NativeRouteId::Unlisted && unknownRoute.plan == NativeRoutePlan::Passthrough, "Unknown route was classified");
        require(!unknownRoute.suppressionRequired && !unknownRoute.enforcementVerified && !unknownRoute.consumesUnlisted, "Unknown route was consumed");

        const ScopeMutator liveChanges[] = {
            [](CareerLayoutScope& value) { value.online = true; },
            [](CareerLayoutScope& value) { value.fresh = false; },
            [](CareerLayoutScope& value) { value.owned = false; },
            [](CareerLayoutScope& value) { value.offline = false; },
            [](CareerLayoutScope& value) { value.generation += 1; },
        };
        for (const auto live : liveChanges) {
            auto changed = scope;
            live(changed);
            auto hidden = layout.view(changed, state);
            require(!hidden.offersReplacement && hidden.choices.empty() && hidden.suppress.empty(), "Changed live scope still shows a menu");
            auto decision = layout.route(NativeRouteId::Party, changed, state);
            require(decision.plan == NativeRoutePlan::Passthrough && !decision.suppressionRequired && !decision.enforcementVerified,
                "Changed live scope still suppresses");
            auto effect = choose(layout, findChoice(root, NativeCareerLayout::kExit), changed, state, true);
            require(!effect.accepted && effect.action.empty() && effect.refusal == CareerLayoutRefusal::StaleScope, "Changed live scope dispatched");
        }
        require(layout.view(scope, state).offersReplacement && layout.route(NativeRouteId::Store, scope, state).suppressionRequired,
            "Original live scope lost its plan");

        auto careerNav = findChoice(root, NativeCareerLayout::kCareer);
        auto careerMove = choose(layout, careerNav, scope, state, false);
        require(careerMove.accepted && careerMove.kind == CareerLayoutEffectKind::Navigate && careerMove.action.empty(), "Career navigation dispatched");
        require(!careerMove.originalConsumptionRequired, "Navigation required consumption");
        auto career = layout.view(scope, state);
        audit(career);
        require(career.body.find("Orbit vs Nova") != std::string::npos, "Next match text missing");
        auto play = findChoice(career, "career.play");
        require(play.enabled && play.action == "play_match", "Play Next Match was not executable");
        require(play.payload == Json({{"expected_career_id", "career-a"}, {"expected_fixture_id", "fixture-a"}}), "Match payload");
        auto notConsumed = choose(layout, play, scope, state, false);
        require(!notConsumed.accepted && notConsumed.action.empty() && notConsumed.payload.empty(), "Match fired before consumption");
        require(notConsumed.refusal == CareerLayoutRefusal::NotConsumed && notConsumed.originalConsumptionRequired, "Consumption precondition missing");
        require(!notConsumed.originalConsumptionSatisfied && layout.view(scope, state).page == CareerLayoutPage::Career, "Unconsumed match changed the menu");
        auto played = choose(layout, play, scope, state, true);
        require(played.accepted && played.action == "play_match" && played.leaveMenu && played.originalConsumptionSatisfied, "Match dispatch");
        require(played.payload == play.payload && played.stock == StockRoute::None && !played.compatibilityGrant, "Match effect shape");

        layout.open(scope, state);
        choose(layout, findChoice(layout.view(scope, state), NativeCareerLayout::kCareer), scope, state, false);
        play = findChoice(layout.view(scope, state), "career.play");
        auto movedFixture = state;
        movedFixture["next_fixture"]["id"] = "fixture-b";
        auto staleFixture = choose(layout, play, scope, movedFixture, true);
        require(!staleFixture.accepted && staleFixture.action.empty() && staleFixture.refusal == CareerLayoutRefusal::StaleChoice, "Stale fixture dispatched");
        require(staleFixture.payload.empty(), "Stale fixture leaked a payload");
        auto otherCareer = state;
        otherCareer["career"]["id"] = "career-b";
        require(choose(layout, play, scope, otherCareer, true).refusal == CareerLayoutRefusal::StaleChoice, "Stale career dispatched");
        auto busy = state;
        busy["session"]["busy"] = true;
        auto busyCareer = layout.view(scope, busy);
        require(hasChoice(busyCareer, "career.play") && !findChoice(busyCareer, "career.play").enabled, "Busy match still enabled");
        require(findChoice(busyCareer, "career.play").action.empty(), "Busy match still has an action");
        auto finished = state;
        finished["next_fixture"]["status"] = "completed";
        require(!findChoice(layout.view(scope, finished), "career.play").enabled, "Finished match still enabled");
        auto botsOnly = state;
        botsOnly["next_fixture"]["home"] = "rival";
        botsOnly["next_fixture"]["away"] = "other";
        require(findChoice(layout.view(scope, botsOnly), "career.play").reason.find("does not include your club") != std::string::npos, "Bot match reason");
        auto noCareer = state;
        noCareer["career"] = nullptr;
        require(findChoice(layout.view(scope, noCareer), "career.play").reason.find("Create a career") != std::string::npos, "Missing career reason");

        auto staleClick = scope;
        staleClick.generation = 5;
        require(choose(layout, play, staleClick, state, true).refusal == CareerLayoutRefusal::StaleScope, "Stale generation dispatched");
        staleClick = scope;
        staleClick.nonce = "abcdefabcdefabcdefabcdefabcdefab";
        require(choose(layout, play, staleClick, state, true).action.empty(), "Stale nonce dispatched");
        staleClick = scope;
        staleClick.fresh = false;
        require(choose(layout, play, staleClick, state, true).refusal == CareerLayoutRefusal::StaleScope, "Stale freshness dispatched");
        staleClick = scope;
        staleClick.online = true;
        require(choose(layout, play, staleClick, state, true).action.empty(), "Online click dispatched");
        auto rotated = state;
        rotated["bridge_session"] = "abcdefabcdefabcdefabcdefabcdefab";
        require(choose(layout, play, scope, rotated, true).refusal == CareerLayoutRefusal::StaleScope, "Rotated session dispatched");
        require(!layout.view(scope, rotated).offersReplacement && layout.route(NativeRouteId::Store, scope, rotated).plan == NativeRoutePlan::Passthrough,
            "Rotated session still suppresses");

        layout.open(scope, state);
        choose(layout, findChoice(layout.view(scope, state), NativeCareerLayout::kCareer), scope, state, false);
        choose(layout, findChoice(layout.view(scope, state), "career.schedule"), scope, state, false);
        auto schedule = layout.view(scope, state);
        audit(schedule);
        require(schedule.body.find("Round 1: Orbit vs Nova") != std::string::npos, "Schedule row missing");
        require(schedule.choices.size() == 1 && schedule.choices[0].id == "nav.back", "Schedule is not read-only");
        choose(layout, schedule.choices[0], scope, state, false);
        choose(layout, findChoice(layout.view(scope, state), "career.standings"), scope, state, false);
        auto season = layout.view(scope, state);
        audit(season);
        require(season.body.find("Season 1 league table.") != std::string::npos, "Season heading missing");
        require(season.body.find("1. Orbit - 9 points") != std::string::npos, "Standings row missing");
        require(season.choices.size() == 1, "Standings offered a command");
        choose(layout, season.choices[0], scope, state, false);
        choose(layout, findChoice(layout.view(scope, state), "career.squad"), scope, state, false);
        auto squad = layout.view(scope, state);
        audit(squad);
        require(squad.body.find("Anchor - keeper - starter") != std::string::npos, "Squad row missing");
        require(squad.body.find("Comet - attacker - bench") != std::string::npos, "Bench row missing");
        require(squad.choices.size() == 1, "Squad offered a lineup command");

        auto wide = state;
        wide["career"]["seasons"][0]["fixtures"] = Json::array();
        wide["standings"] = Json::array();
        wide["career"]["squad"] = Json::array();
        for (int i = 1; i <= 12; ++i) {
            wide["career"]["seasons"][0]["fixtures"].push_back({{"id", "fixture-" + std::to_string(i)}, {"home", "human"},
                {"away", "rival"}, {"round", i}, {"status", "scheduled"}});
            wide["standings"].push_back({{"name", "Club" + std::to_string(i)}, {"points", i}});
        }
        wide["career"]["seasons"][0]["fixtures"].push_back({{"home", "rival"}, {"away", "other"}, {"round", 1}, {"status", "scheduled"}});
        wide["career"]["seasons"][0]["fixtures"].push_back({{"home", "human"}, {"away", "rival"}, {"round", 2}, {"status", "completed"}});
        for (const char* id : {"anchor", "shield", "relay", "comet", "orbit", "extra"})
            wide["career"]["squad"].push_back(id);
        wide["career"]["recruits"]["orbit"] = {{"name", "Orbit Bot"}, {"role", "all-rounder"}};
        wide["career"]["recruits"]["extra"] = {{"name", "Extra"}, {"role", "attacker"}};
        layout.open(scope, wide);
        choose(layout, findChoice(layout.view(scope, wide), NativeCareerLayout::kCareer), scope, wide, false);
        choose(layout, findChoice(layout.view(scope, wide), "career.schedule"), scope, wide, false);
        auto boundedSchedule = layout.view(scope, wide);
        require(boundedSchedule.body.find("Round 8:") != std::string::npos && boundedSchedule.body.find("Round 9:") == std::string::npos,
            "Schedule was not capped at eight");
        require(boundedSchedule.body.find("completed") == std::string::npos, "Completed fixture was listed");
        choose(layout, boundedSchedule.choices[0], scope, wide, false);
        choose(layout, findChoice(layout.view(scope, wide), "career.standings"), scope, wide, false);
        auto boundedSeason = layout.view(scope, wide);
        require(boundedSeason.body.find("8. Club8 - 8 points") != std::string::npos, "Eighth standing missing");
        require(boundedSeason.body.find("9. Club9") == std::string::npos, "Standings were not capped");
        choose(layout, boundedSeason.choices[0], scope, wide, false);
        choose(layout, findChoice(layout.view(scope, wide), "career.squad"), scope, wide, false);
        auto boundedSquad = layout.view(scope, wide);
        require(boundedSquad.body.find("Comet") != std::string::npos && boundedSquad.body.find("Extra") == std::string::npos, "Squad was not capped at four");
        require(boundedSquad.body.find("Orbit Bot") == std::string::npos, "Fifth squad member was shown");

        layout.open(scope, state);
        auto trainingMove = choose(layout, findChoice(layout.view(scope, state), NativeCareerLayout::kTraining), scope, state, false);
        require(trainingMove.accepted && trainingMove.action.empty(), "Training navigation dispatched");
        auto training = layout.view(scope, state);
        audit(training);
        auto lessonChoice = findChoice(training, "training.lesson.speed-flip");
        auto blockedLesson = choose(layout, lessonChoice, scope, state, false);
        require(blockedLesson.refusal == CareerLayoutRefusal::NotConsumed && blockedLesson.action.empty(), "Lesson selection fired early");
        require(layout.view(scope, state).page == CareerLayoutPage::Training, "Unconsumed lesson selection changed page");
        auto selected = choose(layout, lessonChoice, scope, state, true);
        require(selected.accepted && selected.action == "select_lesson" && selected.payload == Json({{"id", "speed-flip"}}), "Lesson selection payload");
        require(!selected.leaveMenu && layout.view(scope, state).page == CareerLayoutPage::Lesson, "Lesson page did not open");
        auto lesson = layout.view(scope, state);
        audit(lesson);
        require(lesson.body.find("A timed kickoff lesson.") != std::string::npos, "Lesson description missing");
        auto practice = findChoice(lesson, "training.practice");
        require(practice.enabled && practice.payload == Json({{"id", "speed-flip"}}), "Practice payload");
        require(choose(layout, practice, scope, state, false).action.empty(), "Practice fired before consumption");
        auto started = choose(layout, practice, scope, state, true);
        require(started.accepted && started.action == "start_lesson" && started.leaveMenu && started.payload == Json({{"id", "speed-flip"}}), "Practice dispatch");

        layout.open(scope, state);
        choose(layout, findChoice(layout.view(scope, state), NativeCareerLayout::kTraining), scope, state, false);
        choose(layout, findChoice(layout.view(scope, state), "training.lesson.speed-flip"), scope, state, true);
        practice = findChoice(layout.view(scope, state), "training.practice");
        auto removed = state;
        removed["lessons"].erase(0);
        auto staleLesson = choose(layout, practice, scope, removed, true);
        require(!staleLesson.accepted && staleLesson.action.empty() && staleLesson.refusal == CareerLayoutRefusal::StaleChoice, "Removed lesson dispatched");
        require(layout.view(scope, removed).body.find("no longer available") != std::string::npos, "Missing lesson copy");
        auto help = findChoice(layout.view(scope, state), "training.help.ghost");
        auto ghost = choose(layout, help, scope, state, true);
        require(ghost.accepted && ghost.action == "assistance" && ghost.payload == Json({{"id", "speed-flip"}, {"key", "ghost"}, {"value", false}}),
            "Ghost setting payload");
        auto speed = choose(layout, findChoice(layout.view(scope, state), "training.speed.quarter"), scope, state, true);
        require(speed.accepted && speed.payload["key"] == "playback_speed" && speed.payload["value"] == 0.25, "Playback speed payload");
        auto side = choose(layout, findChoice(layout.view(scope, state), "training.side.left"), scope, state, true);
        require(side.action == "lesson_variant" && side.payload == Json({{"id", "speed-flip"}, {"key", "side"}, {"value", "left"}}), "Side payload");
        require(!hasChoice(layout.view(scope, state), "training.zone.left") && !hasChoice(layout.view(scope, state), "training.simple.on"), "Wrong lesson settings");
        choose(layout, findChoice(layout.view(scope, state), "nav.back"), scope, state, false);
        choose(layout, findChoice(layout.view(scope, state), "training.lesson.flip-reset"), scope, state, true);
        require(hasChoice(layout.view(scope, state), "training.simple.on") && !hasChoice(layout.view(scope, state), "training.zone.whole"), "Flip reset settings");
        auto simplified = choose(layout, findChoice(layout.view(scope, state), "training.simple.on"), scope, state, true);
        require(simplified.payload == Json({{"id", "flip-reset"}, {"key", "simplified"}, {"value", true}}), "Simplified payload");
        choose(layout, findChoice(layout.view(scope, state), "nav.back"), scope, state, false);
        choose(layout, findChoice(layout.view(scope, state), "training.lesson.power-shots"), scope, state, true);
        auto zone = choose(layout, findChoice(layout.view(scope, state), "training.zone.left"), scope, state, true);
        require(zone.payload["key"] == "target_zone" && zone.payload["value"] == "left", "Target zone payload");
        auto running = state;
        running["session"]["kind"] = "training";
        require(!findChoice(layout.view(scope, running), "training.zone.left").enabled, "In-progress lesson still changes setup");
        require(findChoice(layout.view(scope, running), "training.help.ghost").enabled, "Lesson help was blocked during practice");

        auto paged = state;
        paged["lessons"] = Json::array();
        for (int i = 0; i < 5; ++i)
            paged["lessons"].push_back({{"id", "lesson-" + std::to_string(i)}, {"title", "Lesson " + std::to_string(i)}});
        layout.open(scope, paged);
        choose(layout, findChoice(layout.view(scope, paged), NativeCareerLayout::kTraining), scope, paged, false);
        require(layout.view(scope, paged).body.find("Page 1 of 2") != std::string::npos, "Lesson page size");
        require(!hasChoice(layout.view(scope, paged), "training.lesson.lesson-4"), "Fifth lesson was on the first page");
        auto next = choose(layout, findChoice(layout.view(scope, paged), "training.next"), scope, paged, false);
        require(next.accepted && next.action.empty() && layout.view(scope, paged).body.find("Page 2 of 2") != std::string::npos, "Next page");
        require(hasChoice(layout.view(scope, paged), "training.lesson.lesson-4"), "Second page lesson missing");

        auto huge = state;
        huge["lessons"] = Json::array();
        huge["career"]["team_name"] = "<script>&\"'";
        for (int i = 0; i < 1000; ++i)
            huge["lessons"].push_back({{"id", "lesson-" + std::to_string(i)}, {"title", std::string(400, '<')},
                {"description", std::string(100000, '<')}});
        huge["lessons"][0] = {{"id", "../bad"}, {"title", "Bad"}};
        huge["lessons"][1] = {{"id", std::string(129, 'a')}, {"title", "Long"}};
        huge["lessons"][2] = {{"id", "lesson-3"}, {"title", "Duplicate"}};
        layout.open(scope, huge);
        choose(layout, findChoice(layout.view(scope, huge), NativeCareerLayout::kTraining), scope, huge, false);
        auto hugeTraining = layout.view(scope, huge);
        audit(hugeTraining);
        require(hugeTraining.body.find("of 24") != std::string::npos, "Lesson catalog was not capped at 96");
        require(hugeTraining.body.find('<') == std::string::npos && hugeTraining.choices.size() <= 6, "Lesson page bounds");
        require(!hasChoice(hugeTraining, "training.lesson.../bad") && !hasChoice(hugeTraining, std::string("training.lesson.") + std::string(129, 'a')),
            "Invalid lesson id was addressable");
        choose(layout, findChoice(hugeTraining, "nav.back"), scope, huge, false);
        choose(layout, findChoice(layout.view(scope, huge), NativeCareerLayout::kCareer), scope, huge, false);
        require(layout.view(scope, huge).body.find("<script>") == std::string::npos && layout.view(scope, huge).body.find('&') == std::string::npos,
            "Career text was not plain");

        layout.open(scope, state);
        choose(layout, findChoice(layout.view(scope, state), NativeCareerLayout::kGarage), scope, state, false);
        auto garage = layout.view(scope, state);
        audit(garage);
        auto appearanceChoice = findChoice(garage, NativeCareerLayout::kAppearance);
        require(appearanceChoice.enabled && appearanceChoice.kind == CareerLayoutEffectKind::Navigate &&
            appearanceChoice.target == CareerLayoutPage::Appearance && appearanceChoice.action.empty() &&
            appearanceChoice.cosmetic.kind == NativeCosmeticRequestKind::None, "Local appearance was not a local page");
        auto player = findChoice(garage, "garage.player");
        auto stock = choose(layout, player, scope, state, true);
        require(stock.accepted && stock.kind == CareerLayoutEffectKind::PreserveStockRoute && stock.stock == StockRoute::Garage, "Garage stock route");
        require(stock.action.empty() && stock.payload.empty() && !stock.originalConsumptionRequired && !stock.leaveMenu, "Garage stock route dispatched");
        auto preset = findChoice(garage, "garage.bot.anchor.stock-23");
        require(!hasChoice(garage, "garage.bot.anchor.stock-999"), "Unlisted body was offered");
        auto saved = choose(layout, preset, scope, state, true);
        require(saved.accepted && saved.action == "loadout", "Loadout dispatch");
        require(saved.payload == Json({{"id", "anchor"}, {"car_id", 23}, {"primary_color", 27}, {"secondary_color", 0}}), "Loadout payload");
        require(!saved.payload.contains("wheels_id") && saved.stock == StockRoute::None, "Loadout claimed wheels or stock route");
        require(garage.body.find("do not add items") != std::string::npos, "Garage entitlement copy missing");
        auto garageNow = layout.view(scope, state);
        require(choose(layout, findChoice(garageNow, NativeCareerLayout::kAppearance), scope, state, true).accepted,
            "Local appearance did not open");
        auto colorEntry = findChoice(layout.view(scope, state), "cosmetic.colors");
        require(colorEntry.kind == CareerLayoutEffectKind::Navigate && colorEntry.target == CareerLayoutPage::CosmeticColors &&
            colorEntry.action.empty(), "Colors was not a local page");
        require(choose(layout, colorEntry, scope, state, true).accepted, "Colors page did not open");
        auto colorPage = layout.view(scope, state);
        require(hasChoice(colorPage, "cosmetic.colors.primary") && hasChoice(colorPage, "cosmetic.colors.accent") &&
            hasChoice(colorPage, "cosmetic.colors.override"), "Color editor removed a control");
        require(choose(layout, findChoice(colorPage, "nav.back"), scope, state, true).accepted, "Colors back failed");
        require(choose(layout, findChoice(layout.view(scope, state), "nav.back"), scope, state, true).accepted,
            "Appearance back failed");
        auto restoredGarage = layout.view(scope, state);
        require(hasChoice(restoredGarage, "garage.player") && hasChoice(restoredGarage, "garage.bot.anchor.stock-23"),
            "Garage routes missing after the color editor");

        layout.open(scope, state);
        choose(layout, findChoice(layout.view(scope, state), NativeCareerLayout::kWorkshop), scope, state, false);
        auto workshop = layout.view(scope, state);
        audit(workshop);
        auto playMap = findChoice(workshop, "workshop.play.dribble-2-overhaul");
        require(!playMap.enabled && playMap.action.empty() && playMap.kind == CareerLayoutEffectKind::Unavailable, "Map launch was offered");
        require(playMap.reason == NativeCareerLayout::kMapLaunchReason, "Map launch reason");
        auto forced = choose(layout, playMap, scope, state, true);
        require(!forced.accepted && forced.action.empty() && forced.refusal == CareerLayoutRefusal::Disabled, "Map launch dispatched");
        playMap.action = "play_workshop";
        playMap.enabled = true;
        playMap.kind = CareerLayoutEffectKind::Dispatch;
        playMap.payload = {{"id", "dribble-2-overhaul"}};
        require(choose(layout, playMap, scope, state, true).action.empty(), "Forged map launch dispatched");
        auto favorite = choose(layout, findChoice(workshop, "workshop.favorite.dribble-2-overhaul"), scope, state, true);
        require(favorite.accepted && favorite.action == "workshop_favorite" && favorite.payload == Json({{"id", "dribble-2-overhaul"}}), "Favorite payload");
        auto refresh = choose(layout, findChoice(layout.view(scope, state), "workshop.refresh"), scope, state, true);
        require(refresh.accepted && refresh.action == "refresh_workshop" && refresh.payload.empty(), "Refresh payload");
        auto manyMaps = state;
        manyMaps["workshop"]["items"] = Json::array();
        for (int i = 0; i < 30; ++i)
            manyMaps["workshop"]["items"].push_back({{"id", "map-" + std::to_string(i)}, {"title", "Map " + std::to_string(i)},
                {"installed", false}, {"can_launch", true}});
        auto mapView = layout.view(scope, manyMaps);
        audit(mapView);
        std::size_t favorites = 0;
        std::size_t plays = 0;
        for (const auto& choice : mapView.choices) {
            favorites += choice.id.rfind("workshop.favorite.", 0) == 0;
            plays += choice.id.rfind("workshop.play.", 0) == 0;
            if (choice.id.rfind("workshop.play.", 0) == 0) require(!choice.enabled && choice.action.empty(), "Extra map launch");
        }
        require(favorites == 8 && plays == 8, "Workshop list was not capped");
        require(findChoice(mapView, "workshop.play.map-0").reason == std::string("Not installed"), "Missing map reason");

        layout.open(scope, state);
        choose(layout, findChoice(layout.view(scope, state), NativeCareerLayout::kCommunity), scope, state, false);
        auto community = layout.view(scope, state);
        audit(community);
        auto activate = findChoice(community, "community.activate");
        require(!activate.enabled && activate.action.empty() && activate.reason == NativeCareerLayout::kActivationReason, "Activation was offered");
        require(choose(layout, activate, scope, state, true).action.empty(), "Activation dispatched after consumption");
        activate.action = "community_activate";
        activate.enabled = true;
        activate.kind = CareerLayoutEffectKind::Dispatch;
        require(choose(layout, activate, scope, state, true).action.empty(), "Forged activation dispatched");
        require(community.body.find("https://example.invalid") == std::string::npos, "Community URL was shown");
        auto paste = choose(layout, findChoice(community, "community.paste"), scope, state, true);
        require(paste.accepted && paste.action == "community_paste_link" && paste.payload.empty(), "Paste link payload");
        community = layout.view(scope, state);
        auto lookup = choose(layout, findChoice(community, "community.lookup.223"), scope, state, true);
        require(lookup.accepted && lookup.action == "community_lookup" && lookup.payload == Json({{"id", "223"}}), "Lookup payload");
        auto download = choose(layout, findChoice(layout.view(scope, state), "community.download"), scope, state, true);
        require(download.accepted && download.action == "community_download" && download.payload.empty(), "Download payload");
        auto library = choose(layout, findChoice(layout.view(scope, state), "community.library"), scope, state, true);
        require(library.accepted && library.action == "community_library", "Library payload");
        auto blockedDownload = state;
        blockedDownload["community_plugins"]["selected"] = nullptr;
        blockedDownload["community_plugins"]["can_activate"] = true;
        auto blockedCommunity = layout.view(scope, blockedDownload);
        require(!findChoice(blockedCommunity, "community.download").enabled, "Download without a release was enabled");
        require(findChoice(blockedCommunity, "community.activate").action.empty(), "Root activation flag enabled a command");
        auto unsafeSelected = state;
        unsafeSelected["community_plugins"]["selected"]["can_activate"] = true;
        require(!findChoice(layout.view(scope, unsafeSelected), "community.download").enabled, "Activatable record was downloadable");
        require(findChoice(layout.view(scope, unsafeSelected), "community.activate").action.empty(), "Activatable record gained an action");
        auto downloading = state;
        downloading["community_plugins"]["busy"] = true;
        auto busyCommunity = layout.view(scope, downloading);
        audit(busyCommunity);
        require(!findChoice(busyCommunity, "community.lookup.223").enabled, "Lookup stayed enabled while downloading");
        require(!findChoice(busyCommunity, "community.paste").enabled, "Paste stayed enabled while downloading");
        require(!findChoice(busyCommunity, "community.download").enabled, "Download stayed enabled while downloading");
        auto cancel = findChoice(busyCommunity, "community.cancel");
        require(cancel.enabled, "Cancel was disabled while downloading");
        require(choose(layout, cancel, scope, downloading, false).action.empty(), "Cancel fired before consumption");
        auto cancelled = choose(layout, cancel, scope, downloading, true);
        require(cancelled.accepted && cancelled.action == "community_cancel" && cancelled.payload.empty(), "Cancel payload");
        auto catalogs = state;
        catalogs["community_plugins"]["catalog"] = Json::array();
        catalogs["community_plugins"]["catalog"].push_back({{"id", "abc"}, {"title", "Bad"}});
        for (int i = 0; i < 20; ++i)
            catalogs["community_plugins"]["catalog"].push_back({{"id", std::to_string(100 + i)}, {"title", "Plugin " + std::to_string(i)}});
        std::size_t lookups = 0;
        for (const auto& choice : layout.view(scope, catalogs).choices)
            lookups += choice.id.rfind("community.lookup.", 0) == 0;
        require(lookups == 8 && !hasChoice(layout.view(scope, catalogs), "community.lookup.abc"), "Community catalog was not capped");

        layout.open(scope, state);
        choose(layout, findChoice(layout.view(scope, state), NativeCareerLayout::kSettings), scope, state, false);
        auto settings = layout.view(scope, state);
        audit(settings);
        auto options = choose(layout, findChoice(settings, "settings.options"), scope, state, true);
        require(options.accepted && options.kind == CareerLayoutEffectKind::PreserveStockRoute && options.stock == StockRoute::Options, "Options route");
        require(options.action.empty() && options.payload.empty(), "Options route dispatched a setting");
        auto mode = choose(layout, findChoice(settings, "settings.mode.lead"), scope, state, true);
        require(mode.accepted && mode.action == "training_settings" && mode.payload == Json({{"key", "mode"}, {"value", "lead"}}), "Training mode payload");
        require(mode.stock == StockRoute::None, "Training setting preserved a stock route");
        auto loop = choose(layout, findChoice(layout.view(scope, state), "settings.loop.off"), scope, state, true);
        require(loop.payload == Json({{"key", "loop"}, {"value", false}}), "Loop payload");
        auto viewName = choose(layout, findChoice(layout.view(scope, state), "settings.view.top"), scope, state, true);
        require(viewName.payload == Json({{"key", "ghost_view"}, {"value", "top"}}), "Ghost view payload");
        require(!hasChoice(settings, "settings.launcher") && !hasChoice(settings, "settings.install_path"), "App setup was exposed as a game setting");

        auto stopping = state;
        stopping["session"]["busy"] = true;
        layout.open(scope, stopping);
        auto stoppingRoot = layout.view(scope, stopping);
        require(stoppingRoot.choices.size() == 7 && !findChoice(stoppingRoot, NativeCareerLayout::kExit).enabled, "Exit stayed enabled while busy");
        require(findChoice(stoppingRoot, NativeCareerLayout::kExit).action.empty(), "Busy exit still has an action");
        choose(layout, findChoice(stoppingRoot, NativeCareerLayout::kSettings), scope, stopping, false);
        require(findChoice(layout.view(scope, stopping), "settings.options").enabled, "Game options were disabled while busy");
        require(!findChoice(layout.view(scope, stopping), "settings.mode.watch").enabled, "Training setting stayed enabled while busy");

        layout.open(scope, state);
        auto exitChoice = findChoice(layout.view(scope, state), NativeCareerLayout::kExit);
        require(choose(layout, exitChoice, scope, state, false).refusal == CareerLayoutRefusal::NotConsumed, "Exit fired before consumption");
        auto exited = choose(layout, exitChoice, scope, state, true);
        require(exited.accepted && exited.action == "quit_game" && exited.payload.empty() && exited.leaveMenu, "Exit dispatch");
        require(exited.stock == StockRoute::None && !exited.compatibilityGrant, "Exit was treated as a stock or verified route");

        auto unknown = CareerLayoutChoice{};
        unknown.id = "Function Online.Join";
        auto unknownEffect = choose(layout, unknown, scope, state, true);
        require(!unknownEffect.accepted && unknownEffect.action.empty() && unknownEffect.refusal == CareerLayoutRefusal::UnknownControl, "Unknown control dispatched");
        require(!unknownEffect.consumesUnlistedCallback, "Unknown control swallowed other callbacks");

        NativeCareerLayout revisions;
        require(revisions.open(scope, state), "Revision layout did not open");
        auto firstRoot = revisions.view(scope, state);
        auto careerButton = findChoice(firstRoot, NativeCareerLayout::kCareer);
        require(choose(revisions, careerButton, scope, state, false).accepted, "Career page did not open");
        auto repeatedNav = choose(revisions, careerButton, scope, state, false);
        require(!repeatedNav.accepted && repeatedNav.action.empty() && repeatedNav.refusal == CareerLayoutRefusal::StaleChoice,
            "Repeated navigation used the same rendered control");
        require(revisions.view(scope, state).page == CareerLayoutPage::Career, "Repeated navigation left the page");
        auto matchButton = findChoice(revisions.view(scope, state), "career.play");
        require(choose(revisions, matchButton, scope, state, false).refusal == CareerLayoutRefusal::NotConsumed, "Match consumption was skipped");
        require(findChoice(revisions.view(scope, state), "career.play").revision == matchButton.revision, "Rejected match consumed a revision");
        require(choose(revisions, matchButton, scope, state, true).action == "play_match", "Fresh match did not dispatch");
        auto replayedMatch = choose(revisions, matchButton, scope, state, true);
        require(!replayedMatch.accepted && replayedMatch.action.empty() && replayedMatch.refusal == CareerLayoutRefusal::StaleChoice,
            "Match dispatched twice from one rendered control");
        auto laterMatch = findChoice(revisions.view(scope, state), "career.play");
        require(laterMatch.revision != matchButton.revision && laterMatch.id == matchButton.id, "Re-render did not mint a new match control");
        require(choose(revisions, laterMatch, scope, state, true).payload == matchButton.payload, "Later match lost the current payload");

        require(revisions.open(scope, state), "Same scope did not open again");
        auto staleExit = findChoice(firstRoot, NativeCareerLayout::kExit);
        require(choose(revisions, staleExit, scope, state, true).action.empty(), "Re-open revived an old Exit control");
        auto exitButton = findChoice(revisions.view(scope, state), NativeCareerLayout::kExit);
        require(exitButton.revision != staleExit.revision, "Re-open kept the old revision");
        require(choose(revisions, exitButton, scope, state, false).refusal == CareerLayoutRefusal::NotConsumed, "Exit consumption was skipped");
        require(findChoice(revisions.view(scope, state), NativeCareerLayout::kExit).revision == exitButton.revision, "Rejected Exit consumed a revision");
        require(choose(revisions, exitButton, scope, state, true).action == "quit_game", "Exit did not dispatch");
        require(choose(revisions, exitButton, scope, state, true).action.empty(), "Exit dispatched twice from one rendered control");

        require(revisions.open(scope, state), "Workshop revision layout did not open");
        auto workshopButton = findChoice(revisions.view(scope, state), NativeCareerLayout::kWorkshop);
        require(choose(revisions, workshopButton, scope, state, false).accepted, "Workshop page did not open");
        auto favoriteButton = findChoice(revisions.view(scope, state), "workshop.favorite.dribble-2-overhaul");
        require(choose(revisions, favoriteButton, scope, state, false).refusal == CareerLayoutRefusal::NotConsumed, "Favorite consumption was skipped");
        require(findChoice(revisions.view(scope, state), favoriteButton.id).revision == favoriteButton.revision, "Rejected favorite consumed a revision");
        auto savedFavorite = choose(revisions, favoriteButton, scope, state, true);
        require(savedFavorite.accepted && savedFavorite.action == "workshop_favorite", "Favorite did not dispatch");
        auto toggledBack = choose(revisions, favoriteButton, scope, state, true);
        require(!toggledBack.accepted && toggledBack.action.empty() && toggledBack.refusal == CareerLayoutRefusal::StaleChoice,
            "Favorite toggled twice from one rendered control");
        auto laterFavorite = findChoice(revisions.view(scope, state), favoriteButton.id);
        require(laterFavorite.revision != favoriteButton.revision, "Re-render did not mint a new favorite");
        require(choose(revisions, laterFavorite, scope, state, true).payload == favoriteButton.payload, "Later favorite lost its id");

        const std::string exe = "C:\\Steam Library\\steamapps\\common\\rocketleague\\Binaries\\Win64\\RocketLeague.exe";
        const std::string content = "C:\\Steam Library\\steamapps\\workshop\\content\\252950";
        const auto packageFor = [&](const std::string& workshopId) {
            return content + "\\" + workshopId + "\\Map.upk";
        };
        auto installedMaps = state;
        installedMaps["workshop"]["items"] = Json::array();
        for (int index = 0; index < 70; ++index) {
            const auto workshopId = std::to_string(1000000000 + index);
            installedMaps["workshop"]["items"].push_back({{"id", "steam:library:" + workshopId}, {"workshop_id", workshopId},
                {"title", "Map " + std::to_string(index)}, {"path", packageFor(workshopId)},
                {"origin", "steam_workshop"}, {"installed", true}, {"can_launch", true}});
        }
        auto ready = NativeCareerLayout::bindWorkshop(installedMaps, exe, scope.nonce, 7, true, false, false);
        require(ready.bound && ready.libraryConfirmed && ready.packages.size() == 70, "Installed maps past the old scan were dropped");
        NativeCareerLayout pages;
        require(pages.open(scope, installedMaps, {}, ready), "Workshop pages did not open");
        require(choose(pages, findChoice(pages.view(scope, installedMaps, {}, ready), NativeCareerLayout::kWorkshop), scope, installedMaps, false, ready).accepted,
            "Bound workshop page did not open");
        for (int page = 0; page < 8; ++page) {
            auto current = pages.view(scope, installedMaps, {}, ready);
            audit(current);
            require(hasChoice(current, "workshop.page.next"), "More maps was missing");
            require(choose(pages, findChoice(current, "workshop.page.next"), scope, installedMaps, false, ready).accepted, "More maps did not advance");
        }
        auto lastPage = pages.view(scope, installedMaps, {}, ready);
        audit(lastPage);
        require(hasChoice(lastPage, "workshop.play.steam:library:1000000064"), "A map past the first 64 was unreachable");
        require(!hasChoice(lastPage, "workshop.play.steam:library:1000000000"), "The first page stayed on screen");
        auto latePlay = findChoice(lastPage, "workshop.play.steam:library:1000000064");
        require(latePlay.enabled && latePlay.kind == CareerLayoutEffectKind::LocalWorkshop && latePlay.action.empty() &&
            latePlay.payload.empty() && latePlay.workshop.packagePath == packageFor("1000000064"),
            "A later installed map was not a typed play request");
        auto lateEffect = choose(pages, latePlay, scope, installedMaps, true, ready);
        require(lateEffect.accepted && lateEffect.kind == CareerLayoutEffectKind::LocalWorkshop && lateEffect.action.empty() &&
            lateEffect.payload.empty() && lateEffect.workshop.packagePath == packageFor("1000000064") &&
            lateEffect.workshop.workshopId == "1000000064" && lateEffect.workshop.generation == 7, "Typed play did not bind the row");
        latePlay.action = "play_workshop";
        latePlay.kind = CareerLayoutEffectKind::Dispatch;
        latePlay.payload = {{"path", latePlay.workshop.packagePath}};
        require(choose(pages, latePlay, scope, installedMaps, true, ready).action.empty(), "Forged workshop command dispatched");

        auto aliasState = state;
        aliasState["workshop"]["items"] = Json::array({
            {{"id", "steam:library:4242424242"}, {"workshop_id", "4242424242"}, {"title", "Installed file"},
                {"path", packageFor("4242424242")}, {"origin", "steam_workshop"}, {"installed", true}},
            {{"id", "dribble-challenge"}, {"title", "Dribble Challenge"}, {"origin", "catalog"}, {"installed", true},
                {"launch_id", "steam:library:4242424242"}},
            {{"id", "local-map"}, {"title", "Imported"}, {"origin", "local_import"}, {"installed", true},
                {"workshop_id", "1"}, {"path", packageFor("1")}},
            {{"id", "steam:other:11"}, {"workshop_id", "11"}, {"title", "Other library"},
                {"path", "D:\\Other Library\\steamapps\\workshop\\content\\252950\\11\\Map.upk"},
                {"origin", "steam_workshop"}, {"installed", true}},
            {{"id", "steam:library:77"}, {"workshop_id", "77"}, {"title", "One"}, {"path", packageFor("77")},
                {"origin", "steam_workshop"}, {"installed", true}},
            {{"id", "steam:library:77"}, {"workshop_id", "78"}, {"title", "Two"}, {"path", packageFor("78")},
                {"origin", "steam_workshop"}, {"installed", true}},
            {{"id", "ambiguous"}, {"title", "Ambiguous"}, {"origin", "catalog"}, {"installed", true},
                {"launch_id", "steam:library:77"}}
        });
        auto bound = NativeCareerLayout::bindWorkshop(aliasState, exe, scope.nonce, 7, true, false, false);
        NativeCareerLayout aliasLayout;
        require(aliasLayout.open(scope, aliasState, {}, bound), "Alias workshop did not open");
        require(choose(aliasLayout, findChoice(aliasLayout.view(scope, aliasState, {}, bound), NativeCareerLayout::kWorkshop),
            scope, aliasState, false, bound).accepted, "Alias page did not open");
        auto aliasView = aliasLayout.view(scope, aliasState, {}, bound);
        audit(aliasView);
        auto aliasPlay = findChoice(aliasView, "workshop.play.dribble-challenge");
        require(aliasPlay.enabled && aliasPlay.workshop.rowId == "dribble-challenge" &&
            aliasPlay.workshop.packagePath == packageFor("4242424242") && aliasPlay.workshop.workshopId == "4242424242",
            "A unique curated row did not use the installed file");
        require(findChoice(aliasView, "workshop.play.local-map").reason == "Imported maps cannot be played from this menu yet.",
            "Imported map reason");
        require(findChoice(aliasView, "workshop.play.steam:other:11").reason == "This map is in another Steam library.",
            "Foreign library reason");
        require(findChoice(aliasView, "workshop.play.ambiguous").reason == "Choose the installed map file.",
            "Ambiguous alias reason");
        require(choose(aliasLayout, findChoice(aliasView, "workshop.favorite.dribble-challenge"), scope, aliasState, true, bound).action ==
            "workshop_favorite", "Favorite stopped working for a curated row");
        require(choose(aliasLayout, findChoice(aliasLayout.view(scope, aliasState, {}, bound), "workshop.refresh"), scope, aliasState, true, bound).action ==
            "refresh_workshop", "Refresh stopped working");
        auto stalePlay = findChoice(aliasLayout.view(scope, aliasState, {}, bound), "workshop.play.dribble-challenge");
        auto moved = aliasState;
        moved["workshop"]["items"][0]["path"] = packageFor("4242424243");
        moved["workshop"]["items"][0]["workshop_id"] = "4242424243";
        auto movedContext = NativeCareerLayout::bindWorkshop(moved, exe, scope.nonce, 7, true, false, false);
        require(choose(aliasLayout, stalePlay, scope, moved, true, movedContext).refusal == CareerLayoutRefusal::StaleChoice,
            "A changed package reused the old play control");

        auto waiting = aliasState;
        waiting["session"]["busy"] = true;
        auto waitingView = aliasLayout.view(scope, waiting, {}, bound);
        require(findChoice(waitingView, "workshop.play.dribble-challenge").reason ==
            std::string("Wait for the current game transition to finish."), "Busy play reason");
        auto held = NativeCareerLayout::bindWorkshop(aliasState, exe, scope.nonce, 7, true, false, true);
        require(findChoice(aliasLayout.view(scope, aliasState, {}, held), "workshop.play.dribble-challenge").reason ==
            "A map is open for this offline session.", "Held play reason");
        auto preparing = NativeCareerLayout::bindWorkshop(aliasState, exe, scope.nonce, 7, true, true, false);
        require(findChoice(aliasLayout.view(scope, aliasState, {}, preparing), "workshop.play.dribble-challenge").reason ==
            "Preparing this map.", "Preparing play reason");
        auto offlineContext = NativeCareerLayout::bindWorkshop(aliasState, exe, scope.nonce, 7, false, false, false);
        require(findChoice(aliasLayout.view(scope, aliasState, {}, offlineContext), "workshop.play.dribble-challenge").reason ==
            "Play is available during an offline career session.", "Offline play reason");
        auto unconfirmed = NativeCareerLayout::bindWorkshop(aliasState, "C:\\Games\\RocketLeague.exe", scope.nonce, 7, true, false, false);
        require(!unconfirmed.libraryConfirmed, "A non-Steam executable confirmed a library");
        require(findChoice(aliasLayout.view(scope, aliasState, {}, unconfirmed), "workshop.play.steam:library:4242424242").reason ==
            "This game's Steam library could not be confirmed.", "Unconfirmed library reason");

        std::cout << "Native career layout: passthrough, menu mapping, consumption, stale scope, and supported actions passed.\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
